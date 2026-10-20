"""READ ONLY. Orchestrator runs this Python process THROUGH MO2 later.

No MO2/game launcher is embedded. Emits observed Windows file-handle destinations
and SHA256 values. Outside MO2 this observes ordinary filesystem resolution only.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'game_adapter/hold_music_adapter'))
from engine import get_scalar

BARD_CONFIG = 'SKSE/Plugins/SkyrimNet/config/BardSinging.yaml'
LIBRARY_STORAGE = 'SKSE/Plugins/StorageUtilData/HoldMusic'
AUDIO_STORAGE = 'Sound/fx/holdmusic'


def virtual_path(name):
    """Require canonical relative Data paths before any requested file is opened."""
    if not isinstance(name, str) or not name:
        raise ValueError('Virtual path must be nonempty text')
    for part in name.split('/'):
        if (not part or part in ('.', '..') or part[-1] in ' .'
                or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
                or part.split('.')[0].upper() in {
                    'CON', 'PRN', 'AUX', 'NUL',
                    *(f'COM{i}' for i in range(1, 10)),
                    *(f'LPT{i}' for i in range(1, 10))}):
            raise ValueError('Unsafe virtual path')
    return name


def validate_manifest(manifest):
    """Validate the complete package inventory before beginning virtual reads."""
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError('Package manifest must be a nonempty object')
    seen = set()
    for name, digest in manifest.items():
        virtual_path(name)
        if name.casefold() in seen:
            raise ValueError('Duplicate case-insensitive virtual path')
        seen.add(name.casefold())
        if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
            raise ValueError('Package hash must be a lowercase SHA256')
    return manifest


def load_manifest(raw):
    """Reject duplicate keys instead of silently choosing one expected hash."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate package-manifest key')
            result[key] = value
        return result
    return validate_manifest(json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique))


def library_targets():
    """Virtual library observations; values distinguish required from optional.

    Lyrics live alongside JsonUtil library metadata. WAVs use the fixed sound
    descriptors. Missing receipts/trace or unused slots are observations, not
    evidence that an otherwise partial library's required inputs are missing.
    """
    targets = {
        f'{LIBRARY_STORAGE}/library.json': True,
        f'{LIBRARY_STORAGE}/receipts.json': False,
        f'{LIBRARY_STORAGE}/trace.json': False,
    }
    for slot in range(1, 25):
        targets[f'{AUDIO_STORAGE}/hm_slot_{slot:02d}.wav'] = False
        targets[f'{LIBRARY_STORAGE}/hm_slot_{slot:02d}.lyrics.txt'] = False
    return targets


def probe_targets(manifest):
    """Package inputs are required even when they overlap optional library paths."""
    validate_manifest(manifest)
    targets = {name: True for name in sorted(manifest)}
    for name, required in {BARD_CONFIG: True, **library_targets()}.items():
        aliases = [existing for existing in targets
                   if existing.casefold() == name.casefold() and existing != name]
        if aliases:
            raise ValueError('Package path aliases a canonical probe target')
        targets[name] = targets.get(name, False) or required
    return targets


def bard_enabled(raw):
    """Return only the ownership flag, never any provider credentials."""
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = raw.decode('utf-16')
    else:
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('cp1252')
    enabled = get_scalar(text, ('bard_singing', 'enabled'))
    if type(enabled) is not bool:
        raise ValueError('Bard enabled field is not a boolean')
    return enabled


def observe_file(data_root, name, *, resolve_handle, expected=None, required=True):
    """Read the observed handle's bytes and destination in the same open."""
    virtual_path(name)
    if type(required) is not bool:
        raise ValueError('required must be boolean')
    if expected is not None:
        validate_manifest({name: expected})
    row = {'virtual_path': name, 'required': required}
    try:
        with (Path(data_root) / name).open('rb') as stream:
            row['exists'] = True
            row['opened_path'] = resolve_handle(stream)
            if name == BARD_CONFIG:
                raw = stream.read()
                row['sha256'] = hashlib.sha256(raw).hexdigest()
                try:
                    row['bard_enabled'] = bard_enabled(raw)
                except (UnicodeError, ValueError) as exc:
                    row['bard_enabled'] = None
                    row['configuration_error'] = type(exc).__name__
            else:
                row['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if expected is not None:
            row['matches_package'] = row['sha256'] == expected
    except FileNotFoundError:
        if 'exists' not in row:
            row['exists'] = False
        row['error'] = 'FileNotFoundError'
    except OSError as exc:
        row['error'] = type(exc).__name__
    return row


def observe_targets(data_root, manifest, *, resolve_handle):
    """Collect fixture-testable read observations without a launcher or writer."""
    targets = probe_targets(manifest)
    return [observe_file(data_root, name, resolve_handle=resolve_handle,
                         expected=manifest.get(name), required=required)
            for name, required in targets.items()]


def probe_failed(rows):
    """Optional absence is allowed; unknown/unreadable optional files still fail."""
    return any('configuration_error' in row or row.get('matches_package') is False
               or ('error' in row and not (
                   row['error'] == 'FileNotFoundError' and row.get('required') is False
                   and row.get('exists') is False))
               for row in rows)


def final_path(handle):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=kernel.GetFinalPathNameByHandleW
    fn.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
    fn.restype=wintypes.DWORD
    buf=ctypes.create_unicode_buffer(32768)
    n=fn(handle,buf,len(buf),0)
    if not n or n>=len(buf): raise ctypes.WinError(ctypes.get_last_error())
    return buf.value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,required=True,help='SkyrimVR Data as visible inside the MO2-launched process')
    parser.add_argument('--manifest',type=Path,required=True,help='Offline build/package-hashes.json')
    parser.add_argument('--profile', help='Operator-supplied profile label for the observation; not proof of MO2 injection')
    args=parser.parse_args(argv)
    if os.name!='nt': raise SystemExit('Windows file-handle probe only; run later through MO2')
    import msvcrt
    try:
        manifest=load_manifest(args.manifest.read_bytes())
        result=observe_targets(args.data_root, manifest,
                               resolve_handle=lambda stream: final_path(msvcrt.get_osfhandle(stream.fileno())))
    except (OSError, ValueError, UnicodeError):
        parser.exit(2, 'Cannot read a valid package manifest or safe probe targets. No files were changed.\n')
    print(json.dumps({'version':2, 'observed_at':datetime.now(timezone.utc).isoformat(),
                      'profile':args.profile, 'data_root':str(args.data_root),
                      'scope':'Observed reads only; no write-location proof and no automated claim that MO2 injection succeeded. Review opened_path against intended profile mod/overwrite.',
                      'files':result},indent=2))
    return int(probe_failed(result))

if __name__=='__main__': raise SystemExit(main())
