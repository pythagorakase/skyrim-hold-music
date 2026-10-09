"""Offline slot library. Standard library only; no game or provider calls.

Readers reject malformed JSON as a whole and report content problems via
validate(). A single helper writer must coordinate publication with the game.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import wave

REGIONS = ('haafingar', 'eastmarch', 'whiterun', 'reach', 'falkreath',
           'rift', 'winterhold', 'pale', 'hjaalmarch')
MODES = ('vocal', 'wordless', 'instrumental')
SLOTS = 24


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _utc(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be ISO UTC text')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError('timestamp must include UTC timezone')
    return dt


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def wav_info(path):
    """Read a PCM WAV header and check that all declared frames are present."""
    with wave.open(str(path), 'rb') as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(),
                stream.getcomptype()) != (1, 2, 44100, 'NONE'):
            raise ValueError('WAV must be mono 16-bit PCM at 44100 Hz')
        frames = stream.getnframes()
        if frames <= 0:
            raise ValueError('WAV must contain audio frames')
        remaining = frames * 2
        while remaining:
            chunk = stream.readframes(min(65536, remaining // 2))
            if not chunk or len(chunk) > remaining or len(chunk) % 2:
                raise ValueError('WAV has truncated or invalid frame data')
            remaining -= len(chunk)
        return {'duration_seconds': frames / 44100, 'frames': frames,
                'channels': 1, 'sample_width': 2, 'sample_rate': 44100}


def _recording_errors(row, slots):
    if not isinstance(row, dict):
        return ['must be an object']
    errors = []
    slot = row.get('slot')
    if type(slot) is not int or not 1 <= slot <= slots:
        errors.append('slot out of range')
    elif row.get('file') != f'hm_slot_{slot:02d}.wav':
        errors.append('file must be the exact slot filename')
    for key in ('performer_id', 'composition_id', 'recipe_id', 'model_id'):
        if not _text(row.get(key)):
            errors.append(f'{key} must be nonempty text')
    if row.get('region') not in REGIONS:
        errors.append('unknown region')
    if row.get('mode') not in MODES:
        errors.append('unknown mode')
    if row.get('gender') not in ('male', 'female'):
        errors.append('unknown gender')
    if not _number(row.get('duration_seconds')) or row.get('duration_seconds', 0) <= 0:
        errors.append('duration_seconds must be positive and finite')
    if type(row.get('playable')) is not bool:
        errors.append('playable must be boolean')
    if 'lyrics_sha256' not in row or (row['lyrics_sha256'] is not None and not _sha(row['lyrics_sha256'])):
        errors.append('lyrics_sha256 must be a lowercase SHA256 or null')
    if row.get('mode') != 'vocal' and row.get('lyrics_sha256') is not None:
        errors.append('only vocal recordings may have lyrics')
    try:
        _utc(row.get('created_at'))
    except (ValueError, TypeError, OverflowError):
        errors.append('created_at must be ISO UTC')
    source = row.get('source')
    if not isinstance(source, dict) or source.get('kind') not in ('import', 'generated') or not _text(source.get('path_or_request_id')):
        errors.append('source must contain kind and path_or_request_id')
    elif 'sha256' in source and not _sha(source['sha256']):
        errors.append('source.sha256 must be a lowercase SHA256')
    for key in ('arrangement', 'voice'):
        if key in row and not _text(row[key]):
            errors.append(f'{key} must be nonempty text')
    if row.get('mode') == 'instrumental' and row.get('voice', 'none') != 'none':
        errors.append('instrumental voice must be none')
    if 'created_at_hours' in row and not _number(row['created_at_hours']):
        errors.append('created_at_hours must be finite and nonnegative')
    if 'save_id' in row or 'world_id' in row:
        if not _text(row.get('save_id')) or not _text(row.get('world_id')):
            errors.append('save_id and world_id must both be supplied')
    return errors


def _receipt_errors(row, slots, generation=False):
    if not isinstance(row, dict):
        return ['must be an object']
    errors = []
    for key in ('id', 'performer_id', 'save_id') + (('world_id',) if generation else ('composition_id',)):
        if not _text(row.get(key)):
            errors.append(f'{key} must be nonempty text')
    if not _number(row.get('at_hours')):
        errors.append('at_hours must be finite and nonnegative')
    if generation:
        if row.get('action') not in ('compose_lyrics', 'generate_recording'):
            errors.append('unknown generation action')
    else:
        if type(row.get('slot')) is not int or not 1 <= row['slot'] <= slots:
            errors.append('slot out of range')
        if not isinstance(row.get('world_id'), str):
            errors.append('world_id must be text (empty is allowed)')
        if row.get('outcome') not in ('completed', 'interrupted'):
            errors.append('unknown outcome')
        if 'written_at' in row:
            try:
                _utc(row['written_at'])
            except (ValueError, TypeError, OverflowError):
                errors.append('written_at must be ISO UTC')
    return errors


def _atomic_json(path, data):
    """Replace only after the complete UTF-8 JSON document is flushed to disk."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix='.library-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Library:
    def __init__(self, root, session_receipt_index=None):
        self.root = Path(root)
        self.session_receipt_index = session_receipt_index
        if session_receipt_index is not None:
            if type(session_receipt_index) is not int or session_receipt_index < 0:
                raise ValueError('session_receipt_index must be a nonnegative integer')
        self.manifest = {}
        self.recordings = []
        self.performances = []
        self.generation_receipts = []
        self.problems = []
        self._write_errors = []
        self._locked_slots = set()

    def _problem(self, message, blocks_write=True):
        self.problems.append(message)
        if blocks_write:
            self._write_errors.append(message)

    def _read(self, filename, default):
        try:
            return json.loads((self.root / filename).read_text(encoding='utf-8-sig'))
        except FileNotFoundError:
            return deepcopy(default)
        except (OSError, ValueError, UnicodeError) as exc:
            self._problem(f'{filename}: {exc}')
            return deepcopy(default)

    def _receipts(self, rows, generation=False):
        label = 'generation_receipts' if generation else 'receipts.json performances'
        if not isinstance(rows, list):
            self._problem(f'{label}: must be a list')
            return []
        valid, seen = [], set()
        for i, row in enumerate(rows):
            errors = _receipt_errors(row, self.slots, generation)
            if not errors:
                key = (row['save_id'], row['world_id'], row['id'])
                if key in seen:
                    errors.append('duplicate scoped receipt id')
                seen.add(key)
            if errors:
                self._problem(f'{label}[{i}]: ' + '; '.join(errors))
            else:
                valid.append(row)
                if not generation and self.session_receipt_index is not None and i >= self.session_receipt_index:
                    self._locked_slots.add(row['slot'])
        return valid

    def load(self, session_receipt_index=None):
        """Refresh disk state. Bad content is reported, never silently repaired."""
        if session_receipt_index is not None:
            if type(session_receipt_index) is not int or session_receipt_index < 0:
                raise ValueError('session_receipt_index must be a nonnegative integer')
            self.session_receipt_index = session_receipt_index
        self.problems, self._write_errors = [], []
        self._locked_slots = set()
        self.recordings = []
        data = self._read('library.json', {'version': 1, 'slots': SLOTS, 'recordings': []})
        if not isinstance(data, dict):
            self._problem('library.json: must be an object')
            data = {}
        self.manifest = data
        self.slots = data.get('slots')
        if type(self.slots) is not int or self.slots != SLOTS:
            self._problem('library.json: slots must be 24')
            self.slots = SLOTS
        if type(data.get('version')) is not int or data.get('version') != 1:
            self._problem('library.json: version must be 1')
        rows = data.get('recordings')
        if not isinstance(rows, list):
            self._problem('library.json: recordings must be a list')
            rows = []
        receipts = self._read('receipts.json', {'version': 1, 'performances': []})
        if not isinstance(receipts, dict) or type(receipts.get('version')) is not int or receipts.get('version') != 1:
            self._problem('receipts.json: expected an object with version 1')
            receipts = {}
        self.performances = self._receipts(receipts.get('performances'))
        self.generation_receipts = self._receipts(data.get('generation_receipts', []), True)
        seen, compositions = set(), {}
        for i, raw in enumerate(rows):
            errors = _recording_errors(raw, self.slots)
            if errors:
                self._problem(f'recordings[{i}]: ' + '; '.join(errors))
                continue
            row = deepcopy(raw)
            slot = row['slot']
            if slot in seen:
                self._problem(f'recordings[{i}]: duplicate slot {slot}')
                continue
            seen.add(slot)
            cid = row['composition_id']
            previous = compositions.get(cid)
            if previous and (previous[0] != row['region'] or
                             (previous[1] is not None and row['lyrics_sha256'] is not None
                              and previous[1] != row['lyrics_sha256'])):
                self._problem(f'recordings[{i}]: composition {cid} has conflicting content')
                continue
            compositions[cid] = (row['region'], row['lyrics_sha256'] or (previous[1] if previous else None))
            row['session_locked'] = slot in self._locked_slots
            row['playable'] = False
            try:
                info = wav_info(self.root / row['file'])
                if not math.isclose(info['duration_seconds'], row['duration_seconds'], rel_tol=0, abs_tol=1 / 44100):
                    raise ValueError('WAV duration differs from manifest')
                row['playable'] = True
            except (OSError, ValueError, EOFError, wave.Error) as exc:
                self._problem(f"{row['file']}: {exc}", False)
            lyrics_path = self.root / f'hm_slot_{slot:02d}.lyrics.txt'
            try:
                if lyrics_path.exists():
                    raw_lyrics = lyrics_path.read_bytes()
                    lyrics = raw_lyrics.decode('utf-8')
                    if row['mode'] != 'vocal':
                        raise ValueError('non-vocal recording has a lyrics sidecar')
                    if not lyrics.strip() or hashlib.sha256(raw_lyrics).hexdigest() != row['lyrics_sha256']:
                        raise ValueError('lyrics sidecar is empty or its hash differs from manifest')
                elif row['lyrics_sha256'] is not None:
                    raise ValueError('lyrics sidecar is missing')
            except (OSError, ValueError, UnicodeError) as exc:
                self._problem(f'{lyrics_path.name}: {exc}', False)
            self.recordings.append(row)
        return self

    def validate(self):
        """Return all current content/asset problems without raising for them."""
        self.load()
        return list(self.problems)

    def free_slots(self):
        """Unoccupied, unreserved slots only; never evict automatically."""
        self.load()
        if self._write_errors:
            return []
        occupied = {r['slot'] for r in self.recordings} | self._locked_slots
        return [s for s in range(1, self.slots + 1) if s not in occupied
                and not (self.root / f'hm_slot_{s:02d}.wav').exists()
                and not (self.root / f'hm_slot_{s:02d}.lyrics.txt').exists()]

    def recordings_for(self, performer_id=None, region=None, mode=None, gender=None):
        self.load()
        filters = dict(performer_id=performer_id, region=region, mode=mode, gender=gender)
        return [deepcopy(r) for r in self.recordings
                if all(value is None or r[key] == value for key, value in filters.items())]

    def add_recording(self, wav_path, *, performer_id, region, mode, gender,
                      composition_id, recipe_id, model_id, source, lyrics=None,
                      slot=None, created_at=None, generation_receipts=(), **extra):
        """Publish a WAV and optional lyrics, then atomically replace the manifest.

        Explicit slot replacement requires a session boundary and no session lock.
        Serial writer API: the caller must pause the game writer during replacement.
        """
        self.load()
        if self._write_errors:
            raise ValueError('Cannot write invalid library: ' + '; '.join(self._write_errors))
        if slot is None:
            free = self.free_slots()
            if not free:
                raise ValueError('No free library slots')
            slot = free[0]
        if type(slot) is not int or not 1 <= slot <= self.slots:
            raise ValueError('slot out of range')
        if slot in self._locked_slots:
            raise ValueError(f'slot {slot} is session locked')
        existing = next((r for r in self.recordings if r['slot'] == slot), None)
        target = self.root / f'hm_slot_{slot:02d}.wav'
        sidecar = target.with_suffix('.lyrics.txt')
        if (existing or target.exists() or sidecar.exists()) and self.session_receipt_index is None:
            raise ValueError('slot replacement requires session_receipt_index')
        if lyrics is not None and (mode != 'vocal' or not _text(lyrics)):
            raise ValueError('lyrics must be nonempty text for a vocal recording')
        info = wav_info(wav_path)
        reserved = {'slot', 'file', 'duration_seconds', 'lyrics_sha256', 'playable', 'session_locked'}
        if reserved.intersection(extra):
            raise ValueError('cannot override derived recording fields')
        row = dict(extra, slot=slot, file=target.name, performer_id=performer_id,
                   region=region, mode=mode, gender=gender, duration_seconds=info['duration_seconds'],
                   composition_id=composition_id, lyrics_sha256=(hashlib.sha256(lyrics.encode('utf-8')).hexdigest()
                                                               if lyrics is not None else None),
                   recipe_id=recipe_id, model_id=model_id,
                   created_at=created_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                   source=deepcopy(source), playable=True)
        errors = _recording_errors(row, self.slots)
        updated = deepcopy(self.manifest)
        updated['recordings'] = [deepcopy(r) for r in updated['recordings'] if r['slot'] != slot] + [row]
        for other in updated['recordings']:
            if other['composition_id'] == composition_id and (
                    other['region'] != row['region'] or
                    (other['lyrics_sha256'] is not None and row['lyrics_sha256'] is not None
                     and other['lyrics_sha256'] != row['lyrics_sha256'])):
                errors.append('composition_id must identify immutable content')
        history = deepcopy(updated.get('generation_receipts', [])) + list(generation_receipts)
        checked = self._receipts(history, True)
        if len(checked) != len(history):
            errors.append('invalid generation receipts')
        if errors:
            raise ValueError('; '.join(errors))
        if history:
            updated['generation_receipts'] = history
        updated['recordings'].sort(key=lambda r: r['slot'])
        self.root.mkdir(parents=True, exist_ok=True)
        # Stage and retain backups so ordinary publication errors restore old files.
        with tempfile.TemporaryDirectory(prefix='.publish-', dir=self.root) as temp:
            stage = Path(temp)
            staged_wav = stage / 'new.wav'
            shutil.copyfile(wav_path, staged_wav)
            wav_info(staged_wav)
            backups = {}
            for path in (target, sidecar):
                if path.exists():
                    backup = stage / (path.name + '.bak')
                    shutil.copyfile(path, backup)
                    backups[path] = backup
            try:
                os.replace(staged_wav, target)
                if lyrics is not None:
                    staged_lyrics = stage / 'new.txt'
                    staged_lyrics.write_bytes(lyrics.encode('utf-8'))
                    os.replace(staged_lyrics, sidecar)
                else:
                    sidecar.unlink(missing_ok=True)
                _atomic_json(self.root / 'library.json', updated)
            except BaseException:
                for path in (target, sidecar):
                    if path in backups:
                        os.replace(backups[path], path)
                    else:
                        path.unlink(missing_ok=True)
                raise
        self.load()
        return next(deepcopy(r) for r in self.recordings if r['slot'] == slot)

    def snapshot(self, performer_id, save_id, world_id, now_hours, request):
        """Adapt this performer's library to repertoire.Snapshot.from_dict().

        Prepared offline material is baseline knowledge at game hour zero. Optional
        save_id/world_id and created_at_hours preserve executor timeline scope.
        UTC timestamps are never interpreted as in-game hours.
        """
        self.load()
        scope = {'save_id': save_id, 'world_id': world_id}
        result = dict(scope, performer_id=performer_id, now_hours=now_hours,
                      request=deepcopy(request), compositions=[], recordings=[],
                      recent_performances=[], generation_history=[])
        compositions = {}
        for row in self.recordings:
            if row['performer_id'] != performer_id:
                continue
            if 'save_id' in row and (row['save_id'], row['world_id']) != (save_id, world_id):
                continue
            created = row.get('created_at_hours', 0)
            if created > now_hours:
                continue
            mode = 'lyrical' if row['mode'] == 'vocal' else row['mode']
            lyrics = None
            if mode == 'lyrical':
                path = self.root / f"hm_slot_{row['slot']:02d}.lyrics.txt"
                try:
                    raw = path.read_bytes()
                    lyrics = raw.decode('utf-8')
                    if not lyrics.strip() or hashlib.sha256(raw).hexdigest() != row['lyrics_sha256']:
                        raise ValueError('lyrics hash mismatch or empty lyrics')
                except (OSError, UnicodeError, ValueError) as exc:
                    self._problem(f'snapshot omitted slot {row["slot"]}: {exc}', False)
                    continue
            cid = row['composition_id']
            if cid not in compositions:
                compositions[cid] = dict(scope, id=cid, title=cid, tradition=row['region'],
                    mode=mode, known_by=[performer_id], composer_id=performer_id,
                    created_at=created, lyrics=lyrics)
            else:
                compositions[cid]['created_at'] = min(created, compositions[cid]['created_at'])
                if mode == 'lyrical':
                    compositions[cid].update(mode=mode, lyrics=lyrics)
            recording_request = dict(tradition=row['region'], mode=mode,
                arrangement=row.get('arrangement', 'solo_lute' if mode == 'instrumental' else 'solo_lute_and_voice'),
                voice=row.get('voice', 'none' if mode == 'instrumental' else row['gender']),
                recipe_id=row['recipe_id'], model_id=row['model_id'])
            result['recordings'].append(dict(scope, id=f"slot:{row['slot']:02d}", composition_id=cid,
                performer_id=performer_id, request=recording_request, playable=row['playable'], created_at=created))
        result['compositions'] = list(compositions.values())
        for receipt in self.performances:
            result['recent_performances'].append({key: receipt[key] for key in
                ('id', 'performer_id', 'composition_id', 'save_id', 'world_id')})
            result['recent_performances'][-1].update(at=receipt['at_hours'], recording_id=f"slot:{receipt['slot']:02d}")
        for receipt in self.generation_receipts:
            result['generation_history'].append({key: receipt[key] for key in
                ('id', 'performer_id', 'action', 'save_id', 'world_id')})
            result['generation_history'][-1]['at'] = receipt['at_hours']
        return result
