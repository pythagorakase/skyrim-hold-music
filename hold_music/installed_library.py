"""Read-only inspection of a profile's split, layered Hold Music library.

This is a loose-file model, not a VFS, archive or running-save attestation. Every
path read comes from explicit roots and the selected profile, never a capture's
untrusted opened_path. No directories, flat copies or output files are created.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import wave

from hold_music.library import SLOTS, _receipt_errors, _recording_errors, wav_info
from hold_music.library_merge import _json
from hold_music.promotion import _component, _no_alias, _relative, _root
from hold_music.runtime_contract import manifest_runtime_selection_errors
from hold_music.runtime_paths import STORAGE

STORAGE_PATH = STORAGE.as_posix()
AUDIO_PATH = 'Sound/fx/holdmusic'
MANIFEST_PATH = STORAGE_PATH + '/library.json'
RECEIPTS_PATH = STORAGE_PATH + '/receipts.json'
TRACE_PATH = STORAGE_PATH + '/trace.json'


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


class _Snapshot:
    def __init__(self):
        self.directories = {}
        self.files = {}
        self.names = {}

    def directory(self, path):
        path = _no_alias(path)
        key = str(path)
        try:
            info = path.stat()
        except FileNotFoundError:
            row, names = {'path': key, 'exists': False}, []
        else:
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('Expected directory: ' + key)
            names = sorted(item.name for item in path.iterdir())
            after = path.stat()
            if (info.st_dev, info.st_ino, info.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mtime_ns):
                raise ValueError('Directory changed during inspection: ' + key)
            row = dict(path=key, exists=True, device=info.st_dev, inode=info.st_ino,
                       mtime_ns=info.st_mtime_ns, inventory_sha256=_digest(names))
        previous = self.directories.get(key)
        if previous is not None and previous != row:
            raise ValueError('Directory changed during inspection: ' + key)
        self.directories[key], self.names[key] = row, names
        return row, names

    def resolve(self, root, relative):
        """Model Windows lookup on every platform; ambiguous case is rejected."""
        parts = _relative(relative).split('/')
        path = root
        for index, part in enumerate(parts):
            key = str(path)
            if key not in self.directories:
                self.directory(path)
            if not self.directories[key]['exists']:
                return path.joinpath(*parts[index:]), False
            matches = [name for name in self.names[key] if name.casefold() == part.casefold()]
            if len(matches) > 1:
                raise ValueError('Ambiguous case-insensitive path: ' + str(path / part))
            if not matches:
                return path.joinpath(*parts[index:]), False
            path = _no_alias(path / matches[0])
        return path, True

    def read(self, path, *, content=False):
        path = _no_alias(path)
        key = str(path)
        try:
            before = path.stat()
        except FileNotFoundError:
            row, raw = {'path': key, 'exists': False}, None
        else:
            if not stat.S_ISREG(before.st_mode) or before.st_nlink > 1:
                raise ValueError('Expected an unaliased regular file: ' + key)
            digest, chunks = hashlib.sha256(), [] if content else None
            with path.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    if chunks is not None:
                        chunks.append(chunk)
            after = path.stat()
            stamp = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                   value.st_mtime_ns, value.st_ctime_ns)
            if stamp(before) != stamp(after):
                raise ValueError('File changed during inspection: ' + key)
            row = dict(path=key, exists=True, device=after.st_dev, inode=after.st_ino,
                       size=after.st_size, mtime_ns=after.st_mtime_ns,
                       ctime_ns=after.st_ctime_ns, sha256=digest.hexdigest())
            raw = b''.join(chunks) if chunks is not None else None
        if key in self.files and self.files[key] != row:
            raise ValueError('File changed during inspection: ' + key)
        self.files[key] = row
        return (row, raw) if content else row

    def finish(self):
        for path in list(self.files):
            self.read(Path(path))
        for path in list(self.directories):
            self.directory(Path(path))
        return dict(files=[self.files[key] for key in sorted(self.files)],
                    directories=[self.directories[key] for key in sorted(self.directories)])


def _profile_text(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeError:
        return raw.decode('cp1252')


def _opened_key(value):
    """Normalize a captured path lexically, without stat/resolve/open on it."""
    if not isinstance(value, str) or not value:
        raise ValueError('VFS opened_path must be absolute text')
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    path = Path(value)
    if not path.is_absolute() or any(part in ('.', '..') for part in re.split(r'[/\\]', value)):
        raise ValueError('VFS opened_path must be an unambiguous absolute path')
    return os.path.normcase(str(path))


def inspect_installed_library(mo2_root, profile, *, game_data=None, vfs_report=None,
                              session_receipt_index=None):
    """Inspect current loose winners and preserve all source locations in memory.

    Omitted receipt boundary reserves every valid observed performance slot.
    Neither that boundary nor a matching historical capture establishes current
    game locks. Case aliases are resolved only when unique; unsafe paths raise.
    """
    mo2 = _root(mo2_root)
    _component(profile)
    if session_receipt_index is not None and (type(session_receipt_index) is not int or session_receipt_index < 0):
        raise ValueError('session_receipt_index must be a nonnegative integer')
    boundary = 0 if session_receipt_index is None else session_receipt_index
    snapshot = _Snapshot()
    blockers, conflicts, warnings = [], [], []

    def block(code, detail):
        row = dict(code=code, detail=detail)
        if row not in blockers:
            blockers.append(row)

    profile_dir, _ = snapshot.resolve(mo2, 'profiles/' + profile)
    modlist, _ = snapshot.resolve(profile_dir, 'modlist.txt')
    _, raw = snapshot.read(modlist, content=True)
    active, unmanaged, seen = [], [], set()
    if raw is None:
        block('missing_profile', 'Selected profile modlist.txt is missing')
    else:
        for index, line in enumerate(_profile_text(raw).splitlines()):
            if not line.strip() or line.startswith('#'):
                continue
            # Profile::doWriteModlist emits "*" for ModInfoForeign. These
            # English labels describe content in game Data, not MO2 mod dirs.
            foreign = re.fullmatch(r'\*(DLC|Creation Club|Unmanaged): (.+)', line)
            if foreign:
                kind, name = foreign.groups()
                _component(name)
                if line[1:].casefold() in seen:
                    block('duplicate_mod_entry', 'Duplicate case-insensitive unmanaged profile entry')
                seen.add(line[1:].casefold())
                unmanaged.append(dict(kind=kind, name=name))
                continue
            if line[0] not in '+-':
                block('invalid_modlist', f'modlist line {index + 1} has no enabled/disabled prefix')
                continue
            name = _component(line[1:])
            if name.casefold() in seen:
                block('duplicate_mod_entry', 'Duplicate case-insensitive profile entry: ' + name)
            seen.add(name.casefold())
            if line[0] == '+' and name.casefold() not in {item.casefold() for item in active}:
                active.append(name)

    layers = []

    def layer(kind, name, path, required):
        state, _ = snapshot.directory(path)
        if required and not state['exists']:
            block('missing_active_directory', 'Active layer directory is missing: ' + str(path))
        layers.append(dict(priority=len(layers), kind=kind, name=name, path=str(path), exists=state['exists']))

    overwrite, _ = snapshot.resolve(mo2, 'overwrite')
    layer('overwrite', 'overwrite', overwrite, False)
    for name in active:
        folder, _ = snapshot.resolve(mo2, 'mods/' + name)
        layer('mod', name, folder, True)
    base = _root(game_data) if game_data is not None else None
    if base is None:
        warnings.append(dict(code='base_data_omitted',
                             detail='No explicit game Data root was supplied; base/unmanaged loose files were not inspected'))
    if base is not None:
        if any(base.is_relative_to(Path(item['path'])) or Path(item['path']).is_relative_to(base) for item in layers):
            raise ValueError('Explicit game Data must not overlap a mod or overwrite layer')
        layer('game_data', 'game_data', base, True)

    targets = {MANIFEST_PATH, RECEIPTS_PATH, TRACE_PATH}
    targets.update(AUDIO_PATH + f'/hm_slot_{slot:02d}.wav' for slot in range(1, SLOTS + 1))
    targets.update(STORAGE_PATH + f'/hm_slot_{slot:02d}.lyrics.txt' for slot in range(1, SLOTS + 1))
    # Only inspect the two relevant immediate directories, not entire mod trees.
    unexpected, layer_directories = set(), {}
    for item in layers:
        layer_directories[item['priority']] = {}
        for relative in (STORAGE_PATH, AUDIO_PATH):
            directory, _ = snapshot.resolve(Path(item['path']), relative)
            layer_directories[item['priority']][relative] = directory
            _, names = snapshot.directory(directory)
            for name in names:
                if name.casefold().startswith('hm_slot_') and name.casefold().endswith(('.wav', '.lyrics.txt')):
                    _component(name)
                    virtual = relative + '/' + name.lower()
                    if virtual not in targets:
                        unexpected.add(virtual)
    targets.update(unexpected)
    for virtual in sorted(unexpected):
        block('unexpected_slot_asset', 'Noncanonical or out-of-range slot asset: ' + virtual)

    files, documents = {}, {}
    for virtual in sorted(targets):
        candidates, winner, hashes = [], None, set()
        for item in layers:
            folder, filename = virtual.rsplit('/', 1)
            path, found = snapshot.resolve(layer_directories[item['priority']][folder], filename)
            if not found:
                if winner is None:
                    candidates.append(dict(layer=item['name'], priority=item['priority'], path=str(path), exists=False))
                continue
            is_json = virtual in (MANIFEST_PATH, RECEIPTS_PATH, TRACE_PATH)
            if is_json:
                state, content = snapshot.read(path, content=True)
            else:
                state, content = snapshot.read(path), None
            if not state['exists']:
                raise ValueError('Input presence changed during inspection: ' + str(path))
            candidate = dict(state, layer=item['name'], priority=item['priority'])
            if is_json:
                try:
                    documents[str(path)] = _json(content)
                    candidate['json_valid'] = True
                except (ValueError, UnicodeError):
                    documents[str(path)] = None
                    candidate['json_valid'] = False
                    if winner is not None:
                        warnings.append(dict(code='shadowed_invalid_json', virtual_path=virtual, path=str(path)))
            candidates.append(candidate)
            if winner is None:
                winner = candidate
            hashes.add(state['sha256'])
        conflict = len(hashes) > 1
        files[virtual] = dict(virtual_path=virtual, candidates=candidates, winner=winner,
                              shadowed_conflict=conflict)
        if conflict:
            conflicts.append(dict(virtual_path=virtual, winner=winner['path'],
                                  shadowed=[row['path'] for row in candidates if row['exists'] and row['path'] != winner['path']]))

    def document(virtual, required=False):
        winner = files[virtual]['winner']
        if winner is None:
            if required:
                block('missing_manifest', virtual + ' has no loose-file candidate')
            return None
        if not winner['json_valid']:
            block('invalid_json', 'Effective JSON is malformed: ' + virtual)
            return None
        return documents[winner['path']]

    def history(rows, label, generation=False):
        if not isinstance(rows, list):
            block('invalid_history', label + ' must be a list')
            return [], 0
        valid, seen = [], set()
        for index, row in enumerate(rows):
            errors = _receipt_errors(row, SLOTS, generation)
            if not errors:
                key = (row['save_id'], row['world_id'], row['id'])
                if key in seen:
                    errors.append('duplicate scoped receipt id')
                seen.add(key)
            for error in errors:
                block('invalid_history', f'{label}[{index}]: {error}')
            if not errors:
                valid.append((index, row))
        return valid, len(rows)

    manifest = document(MANIFEST_PATH, True)
    recordings, occupied, reserved, required_vfs = [], set(), {}, {MANIFEST_PATH}

    def reserve(slot, reason):
        reserved.setdefault(slot, set()).add(reason)

    generations, generation_count = [], 0
    if not isinstance(manifest, dict):
        if files[MANIFEST_PATH]['winner'] is not None:
            block('invalid_manifest', 'Effective library.json must be an object')
        rows = []
    else:
        if type(manifest.get('version')) is not int or manifest['version'] != 1 or type(manifest.get('slots')) is not int or manifest['slots'] != SLOTS:
            block('invalid_manifest', 'Effective library requires version 1 and 24 slots')
        rows = manifest.get('recordings')
        if not isinstance(rows, list):
            block('invalid_manifest', 'Effective recordings must be a list')
            rows = []
        for problem in manifest_runtime_selection_errors(manifest):
            block('invalid_runtime_selection', problem)
        generations, generation_count = history(manifest.get('generation_receipts', []), 'generation_receipts', True)
        for field in ('reserved_slots', 'locked_slots'):
            if field not in manifest:
                continue
            values = manifest[field]
            if (not isinstance(values, list) or any(type(slot) is not int or not 1 <= slot <= SLOTS for slot in values)
                    or len(set(values)) != len(values)):
                block('invalid_reservations', field + ' must contain unique valid slot numbers')
            else:
                for slot in values:
                    reserve(slot, field)

    compositions, performers = {}, {}
    for index, row in enumerate(rows):
        errors = _recording_errors(row, SLOTS)
        if isinstance(row, dict) and type(row.get('slot')) is int and 1 <= row['slot'] <= SLOTS:
            slot = row['slot']
            if slot in occupied:
                block('duplicate_slot', f'Effective library repeats slot {slot}')
            occupied.add(slot)
            reserve(slot, 'occupied_recording')
            if 'session_locked' in row and type(row['session_locked']) is not bool:
                errors.append('session_locked must be boolean')
            elif row.get('session_locked'):
                reserve(slot, 'manifest_session_lock')
        for error in errors:
            block('invalid_recording', f'recordings[{index}]: {error}')
        if errors:
            continue
        slot = row['slot']
        performer = row['performer_id']
        previous = performers.setdefault(performer.casefold(), performer)
        if previous != performer:
            block('performer_alias', 'Performer IDs differ only in case')
        cid = row['composition_id']
        for other in compositions.setdefault(cid.casefold(), []):
            if (cid != other['composition_id'] or row['region'] != other['region'] or
                    (row['lyrics_sha256'] is not None and other['lyrics_sha256'] is not None
                     and row['lyrics_sha256'] != other['lyrics_sha256'])):
                block('composition_conflict', 'Composition identity has conflicting immutable content: ' + cid)
        compositions[cid.casefold()].append(row)
        audio_virtual = AUDIO_PATH + '/' + row['file']
        lyrics_virtual = STORAGE_PATH + f'/hm_slot_{slot:02d}.lyrics.txt'
        audio, lyrics = files[audio_virtual]['winner'], files[lyrics_virtual]['winner']
        required_vfs.add(audio_virtual)
        if row['lyrics_sha256'] is not None:
            required_vfs.add(lyrics_virtual)
        audio_ok, lyrics_ok = False, True
        if audio is None:
            block('missing_audio', f'Slot {slot} has no effective WAV')
        else:
            try:
                info = wav_info(audio['path'])
                if not math.isclose(info['duration_seconds'], row['duration_seconds'], rel_tol=0, abs_tol=1 / 44100):
                    raise ValueError('duration differs from manifest')
                audio_ok = True
            except (OSError, ValueError, EOFError, wave.Error) as exc:
                block('invalid_audio', f'Slot {slot}: {exc}')
            snapshot.read(Path(audio['path']))
        if lyrics is not None:
            _, content = snapshot.read(Path(lyrics['path']), content=True)
            try:
                if row['mode'] != 'vocal' or not content.decode('utf-8').strip() or lyrics['sha256'] != row['lyrics_sha256']:
                    raise ValueError('lyrics mode, content or hash differs from manifest')
            except (UnicodeError, ValueError):
                lyrics_ok = False
                block('invalid_lyrics', f'Slot {slot} effective lyrics do not match its manifest')
        elif row['lyrics_sha256'] is not None:
            lyrics_ok = False
            block('missing_lyrics', f'Slot {slot} has no effective lyrics sidecar')
        recordings.append(dict(metadata=deepcopy(row), slot=slot, performer_id=performer,
                               region=row['region'], mode=row['mode'], asset_valid=audio_ok and lyrics_ok,
                               playable=row['playable'] and audio_ok and lyrics_ok,
                               audio=audio, lyrics=lyrics))

    receipt_doc = document(RECEIPTS_PATH)
    performances, performance_count = [], 0
    if files[RECEIPTS_PATH]['winner'] is not None:
        required_vfs.add(RECEIPTS_PATH)
        if not isinstance(receipt_doc, dict) or type(receipt_doc.get('version')) is not int or receipt_doc['version'] != 1:
            block('invalid_history', 'Effective receipts require an object with version 1')
        else:
            performances, performance_count = history(receipt_doc.get('performances'), 'performances')
    if boundary > performance_count:
        block('invalid_session_boundary', 'session_receipt_index exceeds raw receipt count')
    for index, row in performances:
        if index >= boundary:
            reserve(row['slot'], 'receipt_at_or_after_boundary')
    trace_doc = document(TRACE_PATH)
    trace_count = None
    if files[TRACE_PATH]['winner'] is not None:
        if (not isinstance(trace_doc, dict) or type(trace_doc.get('version')) is not int
                or trace_doc['version'] != 1 or not isinstance(trace_doc.get('entries'), list)):
            block('invalid_trace', 'Effective trace requires version 1 and an entries list')
        else:
            trace_count = len(trace_doc['entries'])
    orphans = []
    for slot in range(1, SLOTS + 1):
        for kind, virtual in (('audio', AUDIO_PATH + f'/hm_slot_{slot:02d}.wav'),
                              ('lyrics', STORAGE_PATH + f'/hm_slot_{slot:02d}.lyrics.txt')):
            winner = files[virtual]['winner']
            if winner is not None:
                reserve(slot, 'existing_' + kind)
                if slot not in occupied:
                    orphans.append(dict(slot=slot, kind=kind, virtual_path=virtual, source=winner))

    vfs = dict(provided=vfs_report is not None, capture_complete=False, matched=[], missing=[], ignored_paths=[])
    if vfs_report is not None:
        evidence_path = _no_alias(Path(os.path.abspath(vfs_report)))
        _, raw = snapshot.read(evidence_path, content=True)
        try:
            captured = _json(raw) if raw is not None else None
            if (not isinstance(captured, dict) or type(captured.get('version')) is not int
                    or captured['version'] != 2 or captured.get('profile') != profile):
                raise ValueError('Capture must be version 2 for the selected profile')
            timestamp = datetime.fromisoformat(captured['observed_at'])
            if timestamp.tzinfo is None or timestamp.utcoffset() is None or timestamp > datetime.now(timezone.utc):
                raise ValueError('Capture timestamp must be timezone-aware and not in the future')
            captured_rows = captured['files']
            if not isinstance(captured_rows, list):
                raise ValueError('Capture files must be a list')
            vfs['observed_at'] = timestamp.isoformat()
            seen, matched, issues_before = set(), set(), len(blockers)
            known = {key.casefold(): key for key in files}
            for row in captured_rows:
                if not isinstance(row, dict):
                    raise ValueError('Capture file row must be an object')
                virtual = _relative(row.get('virtual_path'))
                key = virtual.casefold()
                if key in seen:
                    raise ValueError('Capture contains duplicate case-insensitive virtual paths')
                seen.add(key)
                for flag in ('exists', 'required'):
                    if flag in row and type(row[flag]) is not bool:
                        raise ValueError('Capture presence/required fields must be boolean')
                if key not in known:
                    vfs['ignored_paths'].append(virtual)
                    continue
                virtual = known[key]
                current = files[virtual]
                winner = current['winner']
                if row.get('exists') is False:
                    if row.get('opened_path') is not None or row.get('sha256') is not None or row.get('error') != 'FileNotFoundError':
                        raise ValueError('Captured absence must only report FileNotFoundError')
                    if winner is not None:
                        block('vfs_evidence_mismatch', 'Captured absence differs from current loose files: ' + virtual)
                    continue
                if row.get('error') or row.get('configuration_error'):
                    # Older v2 probes did not distinguish absence from an
                    # unreadable file. Unselected absent optional paths remain
                    # unproven; they cannot satisfy a required selected read.
                    if (row.get('error') == 'FileNotFoundError' and 'exists' not in row
                            and winner is None and virtual not in required_vfs):
                        continue
                    block('vfs_evidence_error', 'Captured read failed: ' + virtual)
                    continue
                opened = _opened_key(row.get('opened_path'))
                candidates = {_opened_key(item['path']): item for item in current['candidates'] if item['exists']}
                selected = candidates.get(opened)
                if selected is None:
                    block('vfs_evidence_path', 'Captured opened_path is not a current candidate for ' + virtual)
                    continue
                if not isinstance(row.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', row['sha256']) or row['sha256'] != selected['sha256']:
                    block('vfs_evidence_hash', 'Captured hash differs from current candidate: ' + virtual)
                    continue
                matches_winner = selected['path'] == winner['path']
                vfs['matched'].append(dict(virtual_path=virtual, opened_path=selected['path'],
                                           sha256=selected['sha256'], matches_loose_winner=matches_winner))
                if not matches_winner:
                    block('vfs_evidence_priority', 'Capture opened a different layer than the current loose winner: ' + virtual)
                else:
                    matched.add(virtual)
            vfs['missing'] = sorted(required_vfs - matched)
            if vfs['missing']:
                block('incomplete_vfs_evidence', 'Capture lacks matching current reads for required/selected library assets')
            vfs['capture_complete'] = not vfs['missing'] and len(blockers) == issues_before
        except (ValueError, UnicodeError, KeyError, TypeError, OverflowError):
            block('invalid_vfs_evidence', 'Cannot validate capture schema, timestamp or virtual paths')

    observed = snapshot.finish()
    result = dict(
        version=1, status='blocked' if blockers else 'inspected', scope='installed_loose_library_snapshot',
        mo2_root=str(mo2), profile=profile, game_data=str(base) if base is not None else None,
        installed=False, vfs_verified=False, runtime_verified=False, writes_performed=False,
        layers=layers, unmanaged_entries=unmanaged, files=files,
        manifest=deepcopy(manifest), recordings=recordings,
        history=dict(performance_count=performance_count, generation_count=generation_count,
                     valid_performance_count=len(performances), valid_generation_count=len(generations),
                     receipts_present=files[RECEIPTS_PATH]['winner'] is not None,
                     session_receipt_index=boundary, trace_count=trace_count),
        reservations=[dict(slot=slot, reasons=sorted(reserved[slot])) for slot in sorted(reserved)],
        unreserved_slots=[slot for slot in range(1, SLOTS + 1) if slot not in reserved],
        orphans=orphans, conflicts=conflicts, warnings=warnings, blockers=blockers,
        vfs_evidence=vfs, snapshot=observed,
        limitations=[
            'Loose-file priority only: overwrite, active mods in modlist order, then optional explicit game Data.',
            'Archive contents, custom VFS mappings, active saves, running processes and write destinations are not verified.',
            'DLC, Creation Club and Unmanaged markers are informational; archives and secondary game data directories are not inspected.',
            'Historical matching reads and the operator-supplied profile label do not prove MO2 injection.',
            'Reservations describe captured files and the supplied boundary, not live game locks or authorization to write.',
            'Lower-priority differences are reported; only effective assets are validated against the effective manifest.',
            'No files were flattened, imported, installed, rewritten or deleted.',
        ])
    if base is None:
        result['limitations'].append('Base/unmanaged loose-file coverage is omitted because no explicit game Data root was supplied.')
    result['review_token'] = _digest(result)
    return result
