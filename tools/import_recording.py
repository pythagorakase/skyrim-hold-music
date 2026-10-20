#!/usr/bin/env python3
"""Review an existing recording import, then apply its exact source-bound plan."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.job_store import _writer_lock
from hold_music.library import Library, MODES, REGIONS, SLOTS
from hold_music.recording_identity import CONTRACT_FIELDS, identity_errors

_METADATA_FIELDS = {
    'version', 'source_sha256', 'lyrics_sha256', 'performer_id', 'region', 'mode',
    'gender', *CONTRACT_FIELDS,
}


def ffmpeg_arguments(ffmpeg, source, destination):
    return [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-i', str(source), '-vn', '-ac', '1', '-ar', '44100',
            '-sample_fmt', 's16', '-c:a', 'pcm_s16le', str(destination)]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw, label):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'{label} has duplicate JSON keys')
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f'{label} has a nonfinite JSON value')

    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                          parse_constant=constant)
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f'{label} is not strict UTF-8 JSON: {exc}') from None


def _path(value):
    """Reject redirected paths, including Windows junctions, before resolving."""
    path = Path(value).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Import paths must not traverse symbolic links or junctions')
    return path.resolve()


def _read(path, *, required=False):
    """Return bytes and a stable, token-safe observation of one regular file."""
    path = _path(path)
    try:
        before = path.stat()
    except FileNotFoundError:
        if required:
            raise ValueError(f'Required import input is missing: {path}') from None
        return None, {'path': str(path), 'exists': False}
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f'Expected a regular file: {path}')
    raw = path.read_bytes()
    after = path.stat()
    stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    if stamp(before) != stamp(after) or len(raw) != after.st_size:
        raise ValueError('An import input changed while it was being read')
    return raw, dict(path=str(path), exists=True, sha256=_sha(raw),
                     size=len(raw), device=after.st_dev, inode=after.st_ino,
                     mtime_ns=after.st_mtime_ns, ctime_ns=after.st_ctime_ns)


def _library_observations(cache):
    paths = [cache.root / 'library.json', cache.receipts_source]
    paths += [cache.root / f'hm_slot_{slot:02d}{suffix}'
              for slot in range(1, SLOTS + 1) for suffix in ('.wav', '.lyrics.txt')]
    observations = []
    for index, path in enumerate(paths):
        raw, observed = _read(path)
        if raw is not None and index < 2:
            _json(raw, 'Library manifest' if index == 0 else 'Performance receipts')
        observations.append(observed)
    return observations


def _metadata(path, *, source_sha, lyrics_sha, performer, region, mode, gender):
    if path is None:
        return None, None
    raw, observed = _read(path, required=True)
    data = _json(raw, 'Import metadata')
    if not isinstance(data, dict) or set(data) != _METADATA_FIELDS:
        raise ValueError('Import metadata must contain exactly the documented version, hashes and identity fields')
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError('Import metadata version must be integer 1')
    expected = dict(source_sha256=source_sha, lyrics_sha256=lyrics_sha,
                    performer_id=performer, region=region, mode=mode, gender=gender)
    for key, value in expected.items():
        if type(data[key]) is not type(value) or data[key] != value:
            raise ValueError(f'Import metadata {key} does not match the supplied input')
    for key in CONTRACT_FIELDS:
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f'Import metadata requires nonempty {key}')
    errors = identity_errors(data)
    if mode == 'instrumental' and data['voice'] != 'none':
        errors.append('instrumental metadata voice must be none')
    if mode in ('vocal', 'wordless') and data['voice'] != gender:
        errors.append('sung metadata voice must match the supplied gender')
    if ((mode == 'instrumental' and data['arrangement'] == 'solo_lute_and_voice')
            or (mode != 'instrumental' and data['arrangement'] == 'solo_lute')):
        errors.append('metadata arrangement contradicts the supplied mode')
    if errors:
        raise ValueError('; '.join(errors))
    return {key: data[key] for key in CONTRACT_FIELDS}, observed


def _prepare(library, performer, region, mode, gender, source, lyrics, ffmpeg,
             metadata, receipts_path, session_receipt_index):
    if not isinstance(performer, str) or not performer.strip():
        raise ValueError('performer must be nonempty text')
    if region not in REGIONS or mode not in MODES or gender not in ('male', 'female'):
        raise ValueError('Unknown region, mode or gender')
    root = _path(library)
    if root.exists() and not root.is_dir():
        raise ValueError('Library root must be a directory')
    cache = Library(root, receipts_path=_path(receipts_path) if receipts_path is not None else None,
                    session_receipt_index=0 if session_receipt_index is None else session_receipt_index)
    if receipts_path is not None:
        _read(cache.receipts_source, required=True)
    source_bytes, source_observed = _read(source, required=True)
    if not source_bytes:
        raise ValueError('Source recording must not be empty')
    lyrics_observed = None
    words = None
    if lyrics is not None:
        raw, lyrics_observed = _read(lyrics, required=True)
        try:
            words = raw.decode('utf-8-sig')
        except UnicodeError:
            raise ValueError('Lyrics must be UTF-8 text') from None
        if mode != 'vocal' or not words.strip():
            raise ValueError('--lyrics requires vocal mode and a nonempty text file')
    identity, metadata_observed = _metadata(
        metadata, source_sha=source_observed['sha256'],
        lyrics_sha=lyrics_observed['sha256'] if lyrics_observed else None,
        performer=performer, region=region, mode=mode, gender=gender)
    if identity is None:
        # A regional filing label is not evidence of a production recipe.
        identity = {'recipe_id': f'{region}/{mode}', 'model_id': 'unknown', 'mode': mode}
    executable = shutil.which(str(ffmpeg or 'ffmpeg'))
    if executable is None:
        raise ValueError('ffmpeg was not found; supply --ffmpeg <path> to the ffmpeg executable')
    # Homebrew commonly exposes ffmpeg through a symlink. Resolve this one
    # executable explicitly, then bind both lookup path and exact target bytes.
    executable_lookup = str(Path(executable).absolute())
    _, executable_observed = _read(Path(executable).resolve(strict=True), required=True)
    observations = _library_observations(cache)
    free = cache.free_slots()
    if cache.problems:
        raise ValueError('Cannot import into an invalid library: ' + '; '.join(cache.problems))
    if cache.session_receipt_index > len(cache.performances):
        raise ValueError('session_receipt_index exceeds the current performance receipt count')
    if 'runtime_selection' in cache.manifest:
        raise ValueError('Import into an offline source library; runtime_selection requires separate reviewed staging')
    if not free:
        raise ValueError('No free library slots')
    if observations != _library_observations(cache):
        raise ValueError('Library changed during import review')
    composition_key = json.dumps([region, mode, words if words is not None else source_observed['sha256']],
                                 ensure_ascii=False)
    composition_id = 'import:' + _sha(composition_key.encode('utf-8'))
    lyrics_hash = _sha(words.encode('utf-8')) if words is not None else None
    for row in cache.recordings:
        if row['composition_id'] == composition_id and (
            row['region'] != region or (row['lyrics_sha256'] is not None and lyrics_hash is not None
                                       and row['lyrics_sha256'] != lyrics_hash)
        ):
            raise ValueError('Import composition conflicts with existing immutable content')
    plan = dict(
        version=1, operation='import_existing_recording', library=str(root),
        performer_id=performer, region=region, mode=mode, gender=gender,
        identity=identity, composition_id=composition_id, slot=free[0],
        source=source_observed, lyrics=lyrics_observed, metadata=metadata_observed,
        published_lyrics_sha256=lyrics_hash, ffmpeg_requested=str(ffmpeg or 'ffmpeg'),
        ffmpeg_lookup=executable_lookup, ffmpeg=executable_observed,
        receipts_source=str(cache.receipts_source),
        session_receipt_index=cache.session_receipt_index, locked_slots=sorted(cache._locked_slots),
        free_slots=free, library_observations=observations,
    )
    token = _sha(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'), allow_nan=False).encode('utf-8'))
    return plan, token, cache, source_bytes, words


def _matches(given, expected):
    return isinstance(given, str) and given.isascii() and hmac.compare_digest(given, expected)


def review_import_recording(library, performer, region, mode, gender, source, lyrics=None, ffmpeg=None,
                            *, metadata=None, receipts_path=None, session_receipt_index=None,
                            review_token=None, apply=False):
    """Default read-only review; apply requires the exact freshly recomputed token.

    This coordinates this import tool's writers only. The caller must keep other
    library/game writers stopped. No provider, deployment or runtime validation
    is performed, and asserted metadata is not provider-authenticated evidence.
    """
    if type(apply) is not bool:
        raise ValueError('apply must be boolean')
    if not apply and review_token is not None:
        raise ValueError('review_token is only accepted with apply')
    args = (library, performer, region, mode, gender, source, lyrics, ffmpeg,
            metadata, receipts_path, session_receipt_index)
    plan, token, cache, source_bytes, words = _prepare(*args)
    report = dict(status='import_dry_run', can_apply=True, review_token=token, blockers=[],
                  writes_performed=False, runtime_verified=False,
                  metadata_provenance='operator_asserted' if metadata is not None else 'unknown',
                  plan=plan)
    if not apply:
        return report
    if not _matches(review_token, token):
        report.update(status='blocked', can_apply=False,
                      blockers=[{'code': 'stale_review', 'detail': 'Review token is missing, invalid or stale'}])
        return report
    lock = cache.root / '.import.lock'
    _path(lock)
    cache.root.mkdir(parents=True, exist_ok=True)
    with _writer_lock(lock):
        _, fresh_token, cache, source_bytes, words = _prepare(*args)
        if fresh_token != token:
            raise ValueError('Import inputs changed before conversion; review again')
        with tempfile.TemporaryDirectory(prefix='.import-', dir=cache.root) as temp:
            stage = Path(temp)
            frozen = stage / ('source' + Path(plan['source']['path']).suffix)
            frozen.write_bytes(source_bytes)
            wav = stage / 'converted.wav'
            try:
                subprocess.run(ffmpeg_arguments(plan['ffmpeg']['path'], frozen, wav),
                               check=True, capture_output=True, text=True)
            except FileNotFoundError:
                raise ValueError('ffmpeg was not found; supply --ffmpeg <path>') from None
            except subprocess.CalledProcessError as exc:
                raise ValueError(f'ffmpeg conversion failed: {(exc.stderr or "").strip()}') from exc
            if _sha(frozen.read_bytes()) != plan['source']['sha256']:
                raise ValueError('Frozen conversion input changed; no recording was published')
            _, after_token, cache, _, _ = _prepare(*args)
            if after_token != token:
                raise ValueError('Import inputs or library changed during conversion; review again')
            identity = {key: value for key, value in plan['identity'].items() if key != 'mode'}
            provenance = {'kind': 'import', 'path_or_request_id': plan['source']['path'],
                          'sha256': plan['source']['sha256']}
            if metadata is not None:
                provenance.update(metadata_sha256=plan['metadata']['sha256'],
                                  metadata_provenance='operator_asserted')
            row = cache.add_recording(
                wav, performer_id=performer, region=region, mode=mode, gender=gender,
                composition_id=plan['composition_id'], slot=plan['slot'], lyrics=words,
                source=provenance, require_unoccupied=True, **identity)
    report.update(status='imported', can_apply=False, writes_performed=True, recording=row)
    return report


def import_recording(library, performer, region, mode, gender, source, lyrics=None, ffmpeg=None,
                     *, metadata=None, receipts_path=None, session_receipt_index=None):
    """Compatibility API for an explicitly requested immediate offline import.

    CLI users always review first. Programmatic callers still get the same
    preflight, frozen-source conversion and guarded publication as reviewed apply.
    """
    args = dict(library=library, performer=performer, region=region, mode=mode, gender=gender,
                source=source, lyrics=lyrics, ffmpeg=ffmpeg, metadata=metadata,
                receipts_path=receipts_path, session_receipt_index=session_receipt_index)
    review = review_import_recording(**args)
    result = review_import_recording(**args, apply=True, review_token=review['review_token'])
    if result['status'] != 'imported':
        raise ValueError('Import review became stale; no recording was published')
    return result['recording']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, type=Path, help='offline library root directory')
    parser.add_argument('--performer', required=True, help='authored performer id')
    parser.add_argument('--region', required=True, choices=REGIONS)
    parser.add_argument('--mode', required=True, choices=MODES)
    parser.add_argument('--gender', required=True, choices=('male', 'female'))
    parser.add_argument('--source', required=True, type=Path, help='existing audio recording')
    parser.add_argument('--lyrics', type=Path, help='UTF-8 vocal lyrics sidecar')
    parser.add_argument('--metadata', type=Path, help='complete source-bound version 1 metadata JSON')
    parser.add_argument('--receipts', dest='receipts_path', type=Path, help='existing performance receipt source')
    parser.add_argument('--session-receipt-index', type=int, help='session boundary; default reserves all receipt slots')
    parser.add_argument('--ffmpeg', help='ffmpeg executable path (default: search PATH)')
    parser.add_argument('--apply', action='store_true', help='convert and publish the reviewed import')
    parser.add_argument('--review-token', help='token returned by the same read-only review')
    args = parser.parse_args(argv)
    if args.apply != (args.review_token is not None):
        parser.error('--apply and --review-token must be supplied together')
    try:
        result = review_import_recording(**vars(args))
    except (OSError, ValueError, RuntimeError, EOFError, wave.Error) as exc:
        parser.exit(1, f'Cannot import recording: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if result['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
