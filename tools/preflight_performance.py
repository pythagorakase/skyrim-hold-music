#!/usr/bin/env python3
"""Inspect a closed game's prepared Hold Music pilot without changing any inputs."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import configparser
import json
import math
from pathlib import Path
import re
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'game_adapter/hold_music_adapter'))
from engine import get_scalar
from hold_music.library import MODES, REGIONS, SLOTS, wav_info
from hold_music.runtime_paths import DEFAULT_MOD_NAME, locate, storage_dirs


def _name(value):
    if not value or value in ('.', '..') or re.search(r'[<>:"/\\|?*\x00-\x1f]', value):
        raise ValueError('Expected one profile or mod directory name')
    return value


def _text(path):
    raw = Path(path).read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252')


def inspect(mo2_root, profile, *, performer='sven', mod_name=DEFAULT_MOD_NAME,
            data_mod='MGO Experimental - Profile Data'):
    """Resolve loose files by MO2 priority; never claim a running-game VFS view."""
    root = Path(mo2_root).resolve()
    for value in (profile, mod_name, data_mod):
        _name(value)
    if not re.fullmatch(r'[a-z][a-z0-9_]*', performer):
        raise ValueError('Expected a performer registry ID')
    profile_dir = root / 'profiles' / profile
    report = {
        'version': 1, 'scope': 'prepared_loose_files', 'profile': profile,
        'performer_id': performer, 'checks': [], 'recordings': [],
        'runtime_evidence': {}, 'bard_setting_sources': [],
        'limitations': [
            'Run after Skyrim exits. Process state is not inferred by this tool.',
            'Loose-file priority is inspected; archives and plugin file mappings need a VFS probe.',
            'MCM files describe prepared values, not globals already stored in a running save.',
            'Runtime eligibility, slot locks, sound, animation and interruption still need the game test.',
            'A successful pilot preflight does not approve full-roster takeover or musical styles.',
        ],
    }

    def check(code, passed, message, **details):
        report['checks'].append(dict(code=code, passed=bool(passed), message=message, **details))

    try:
        active = [line[1:] for line in _text(profile_dir / 'modlist.txt').splitlines()
                  if line.startswith('+')]
        for name in active:
            _name(name)
        plugins = _text(profile_dir / 'plugins.txt').splitlines()
    except (OSError, UnicodeError, ValueError):
        check('profile', False, 'Cannot read a valid profile mod list and plugin list.')
        report['status'] = 'blocked'
        return report
    check('package_enabled', mod_name.casefold() in {s.casefold() for s in active}
          and '*holdmusic.esp' in {s.casefold() for s in plugins},
          'The performance mod and HoldMusic.esp must both be enabled.')
    # MO2 stores highest-priority mods first; overwrite wins over all of them.
    roots = [root / 'overwrite'] + [root / 'mods' / name for name in active]

    def candidates(relative):
        return [base / relative for base in roots if (base / relative).is_file()]

    def winner(relative):
        found = candidates(relative)
        if not found:
            raise FileNotFoundError(relative)
        return found[0]

    required = ['HoldMusic.esp', 'SEQ/HoldMusic.seq', 'mcm/config/HoldMusic/config.json']
    required += ['Scripts/' + name + '.pex' for name in ('HM_Config', 'HM_Controller', 'HM_Library')]
    missing = [relative for relative in required if not candidates(relative)]
    check('package_files', not missing, 'Plugin, startup file, scripts and MCM definition must be present.',
          missing=missing)

    runtime = profile_dir / 'hold-music-runtime'
    check('overlay_reconciled', not (runtime / 'BardSinging.baseline.yaml').exists(),
          'An outstanding adapter overlay needs reconciliation before an offline preflight is conclusive.')
    try:
        source = winner('SKSE/Plugins/SkyrimNet/config/BardSinging.yaml')
        enabled = get_scalar(_text(source), ('bard_singing', 'enabled'))
        report['bard_setting_sources'].append(dict(role='loose_file_winner', source=str(source),
                                                   enabled=enabled if type(enabled) is bool else None))
        check('skyrimnet_music_disabled', enabled is False,
              'The loose-file Bard Singing setting must be off; an adapter mapping can override this view.',
              enabled=enabled if type(enabled) is bool else None, source=str(source))
    except (OSError, ValueError):
        check('skyrimnet_music_disabled', False, 'Cannot establish the SkyrimNet Bard Singing setting.')

    # The current adapter deliberately reads its configured data mod, even if
    # overwrite supplies a different loose file. Inspect that launch input too.
    adapter_record = root / 'plugins/hold_music_adapter/local.json'
    if adapter_record.is_file():
        try:
            adapter = json.loads(_text(adapter_record))
            if adapter['profile'] == profile and adapter['mod'].casefold() in {s.casefold() for s in active}:
                source_mod = _name(adapter['data_mod'])
                source = root / 'mods' / source_mod / 'SKSE/Plugins/SkyrimNet/config/BardSinging.yaml'
                enabled = get_scalar(_text(source), ('bard_singing', 'enabled'))
                report['bard_setting_sources'].append(dict(role='adapter_launch_input', source=str(source),
                                                           enabled=enabled if type(enabled) is bool else None))
                check('adapter_music_disabled', enabled is False,
                      'The configured adapter launch input must also keep Bard Singing off.',
                      enabled=enabled if type(enabled) is bool else None, source=str(source))
                check('bard_settings_agree', all(row['enabled'] is False for row in report['bard_setting_sources']),
                      'Resolve conflicting launch inputs or verify the VFS mapping before the next test.')
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            check('adapter_music_disabled', False, 'Cannot establish the installed adapter launch input.')

    try:
        defaults = winner('mcm/config/HoldMusic/settings.ini')
        custom = candidates('mcm/settings/HoldMusic.ini')
        settings = configparser.ConfigParser(interpolation=None)
        settings.read_string(_text(defaults))
        if custom:
            settings.read_string(_text(custom[0]))
        enabled = settings.getboolean('General', 'bEnabled')
        cap = settings.getint('General', 'iSessionCap')
        chance = settings.getint('General', 'iInstrumentalPercent')
        check('hold_music_enabled', enabled, 'Hold Music must be enabled in its MCM settings.',
              enabled=enabled, defaults=str(defaults), override=str(custom[0]) if custom else None)
        check('performance_settings', 1 <= cap <= SLOTS and 0 <= chance <= 100,
              'The session cap must allow a performance and instrumental chance must be valid.',
              session_cap=cap, instrumental_chance=chance)
    except (OSError, ValueError, configparser.Error):
        check('hold_music_enabled', False, 'Cannot establish valid Hold Music MCM settings.')

    selected = None
    try:
        source = winner('SKSE/Plugins/HoldMusic/registry.json')
        registry = json.loads(_text(source))
        rows = registry['performers']
        if registry.get('schema_version') != 2 or not isinstance(rows, list):
            raise ValueError('Invalid registry')
        ids = [row['id'] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate performers')
        selected = next((row for row in rows if row['id'] == performer), None)
        if selected is None:
            raise ValueError('Performer missing')
        form = selected.get('form')
        valid_form = (isinstance(form, dict) and isinstance(form.get('plugin'), str)
                      and bool(form['plugin']) and type(form.get('id')) is int and form['id'] > 0)
        check('performer_owned', selected.get('owner') == 'hold_music' and valid_form
              and selected.get('region') in REGIONS,
              'The selected performer needs Hold Music ownership, a resolved base form and a supported region.',
              source=str(source), region=selected.get('region'), owner=selected.get('owner'))
        report['coverage'] = {'registered': len(rows),
                              'hold_music_owned': sum(row.get('owner') == 'hold_music' for row in rows)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        check('performer_owned', False, 'Cannot resolve the selected performer from the installed registry.')

    try:
        source = winner('SKSE/Plugins/StorageUtilData/HoldMusic/library.json')
        manifest = json.loads(_text(source))
        rows = manifest['recordings']
        if manifest.get('version') != 1 or manifest.get('slots') != SLOTS or not isinstance(rows, list):
            raise ValueError('Invalid library')
        slots = [row['slot'] for row in rows]
        if any(type(slot) is not int or not 1 <= slot <= SLOTS for slot in slots) or len(slots) != len(set(slots)):
            raise ValueError('Invalid or repeated slot')
        matched = [row for row in rows if selected and row.get('performer_id') == performer
                   and row.get('region') == selected.get('region')]
        for row in matched:
            slot, duration = row['slot'], row.get('duration_seconds')
            good = (row.get('file') == f'hm_slot_{slot:02d}.wav' and row.get('mode') in MODES
                    and isinstance(row.get('composition_id'), str) and bool(row['composition_id'].strip())
                    and type(duration) in (int, float) and math.isfinite(duration) and duration > 0)
            item = {'slot': slot, 'mode': row.get('mode'), 'playable': False}
            try:
                if not good:
                    raise ValueError('Invalid recording metadata')
                audio = winner('Sound/fx/holdmusic/' + row['file'])
                actual = wav_info(audio)
                good = abs(actual['duration_seconds'] - duration) <= 1 / 44100
                item.update(source=str(audio), duration_seconds=actual['duration_seconds'], playable=good)
            except (OSError, ValueError, EOFError, wave.Error):
                good = False
            report['recordings'].append(item)
            check(f'slot_{slot:02d}', good, 'The slot must contain complete mono PCM audio matching its manifest.')
        check('matching_recording', bool(matched), 'At least one recording must match the performer and region.',
              source=str(source))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        check('matching_recording', False, 'Cannot establish a valid installed recording library.')

    for filename, array in [('trace.json', 'entries'), ('receipts.json', 'performances')]:
        found = locate(filename, storage_dirs(root, mod_name, data_mod))
        summaries = []
        for item in found:
            try:
                data = json.loads(_text(item.path))
                count = len(data[array]) if isinstance(data[array], list) else None
            except (OSError, ValueError, KeyError, TypeError):
                count = None
            summaries.append({'source': str(item.path), 'entries': count})
        report['runtime_evidence'][filename] = summaries
        # Game writes go to the VFS winner, not necessarily the newest copy.
        try:
            source = winner('SKSE/Plugins/StorageUtilData/HoldMusic/' + filename)
            data = json.loads(_text(source))
            valid = isinstance(data[array], list) and data.get('version') == 1
        except (OSError, ValueError, KeyError, TypeError):
            valid = False
        check(filename, valid, 'A valid runtime evidence file must be available; zero entries is not a failed test.')

    report['status'] = ('prepared_for_headset_test' if all(row['passed'] for row in report['checks'])
                        else 'blocked')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mo2-root', required=True, type=Path)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--performer', default='sven')
    parser.add_argument('--mod-name', default=DEFAULT_MOD_NAME)
    parser.add_argument('--data-mod', default='MGO Experimental - Profile Data')
    parser.add_argument('--json', action='store_true')
    args = vars(parser.parse_args(argv))
    as_json = args.pop('json')
    try:
        report = inspect(**args)
    except (OSError, ValueError):
        parser.exit(2, 'Cannot inspect the requested profile. No settings were changed.\n')
    if as_json:
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        print(f"{report['performer_id']}: {report['status']}")
        for row in report['checks']:
            print(f"{'PASS' if row['passed'] else 'CHECK'} {row['code']}: {row['message']}")
        print('This checks prepared files only. Playback and interruption remain unverified.')
    return 0 if report['status'] == 'prepared_for_headset_test' else 2


if __name__ == '__main__':
    raise SystemExit(main())
