#!/usr/bin/env python3
"""Convert an existing recording to an offline Hold Music library slot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.library import Library, MODES, REGIONS


def ffmpeg_arguments(ffmpeg, source, destination):
    return [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-i', str(source), '-vn', '-ac', '1', '-ar', '44100',
            '-sample_fmt', 's16', '-c:a', 'pcm_s16le', str(destination)]


def import_recording(library, performer, region, mode, gender, source, lyrics=None, ffmpeg=None):
    source = Path(source)
    if not source.is_file():
        raise ValueError(f'Source recording does not exist: {source}')
    executable = shutil.which(str(ffmpeg or 'ffmpeg'))
    if executable is None:
        raise ValueError('ffmpeg was not found; supply --ffmpeg <path> to the ffmpeg executable')
    words = Path(lyrics).read_text(encoding='utf-8-sig') if lyrics is not None else None
    if words is not None and (mode != 'vocal' or not words.strip()):
        raise ValueError('--lyrics requires vocal mode and a nonempty text file')
    cache = Library(library)
    if not cache.free_slots():
        raise ValueError('No free library slots' + (': ' + '; '.join(cache.problems) if cache.problems else ''))
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    source_hash = digest.hexdigest()
    composition_key = json.dumps([region, mode, words if words is not None else source_hash], ensure_ascii=False)
    composition_id = 'import:' + hashlib.sha256(composition_key.encode('utf-8')).hexdigest()
    cache.root.mkdir(parents=True, exist_ok=True)
    # Place conversion scratch beside the library: the remote proof writes only
    # inside the caller's explicitly selected scratch root, including temp files.
    with tempfile.TemporaryDirectory(prefix='.import-', dir=cache.root) as temp:
        wav = Path(temp) / 'converted.wav'
        try:
            subprocess.run(ffmpeg_arguments(executable, source, wav), check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise ValueError('ffmpeg was not found; supply --ffmpeg <path>') from exc
        except subprocess.CalledProcessError as exc:
            raise ValueError(f'ffmpeg conversion failed: {exc.stderr.strip()}') from exc
        return cache.add_recording(wav, performer_id=performer, region=region, mode=mode,
            gender=gender, composition_id=composition_id, recipe_id=f'{region}/{mode}',
            model_id='google/lyria-3-pro-preview', lyrics=words,
            source={'kind': 'import', 'path_or_request_id': str(source.resolve()), 'sha256': source_hash})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, type=Path, help='library root directory')
    parser.add_argument('--performer', required=True, help='authored performer id')
    parser.add_argument('--region', required=True, choices=REGIONS)
    parser.add_argument('--mode', required=True, choices=MODES)
    parser.add_argument('--gender', required=True, choices=('male', 'female'))
    parser.add_argument('--source', required=True, type=Path, help='existing MP3 recording')
    parser.add_argument('--lyrics', type=Path, help='UTF-8 vocal lyrics sidecar')
    parser.add_argument('--ffmpeg', help='ffmpeg executable path (default: search PATH)')
    args = parser.parse_args(argv)
    try:
        entry = import_recording(**vars(args))
    except (OSError, ValueError, EOFError, wave.Error) as exc:
        parser.exit(1, f'Cannot import recording: {exc}\n')
    print(json.dumps(entry, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
