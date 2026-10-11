#!/usr/bin/env python3
"""Collect local, redacted Hold Music runtime evidence without changing MO2."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.runtime_paths import DEFAULT_MOD_NAME, locate, storage_dirs

REDACT = re.compile(r'key|token|secret|bearer|password', re.I)
SKYRIMNET = re.compile(r"BardSinging|Hold Music|HoldMusic|Generation check|Playing '|Playback started|Starting song generation")
PRIVATE = re.compile(r'dialogue|memor(?:y|ies)', re.I)
TIMESTAMP = re.compile(
    r'\b(?:\d{4}-\d{2}-\d{2}[T ]|\d{2}/\d{2}/\d{4} - )?'
    r'\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?\b')


def redact(text):
    """Drop entire physical lines, including in copied JSON and report metadata."""
    return ''.join(line for line in text.splitlines(keepends=True) if not REDACT.search(line))


def _cell(value):
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('|', '\\|').replace('`', '\\`')


def _table(lines, counts, label):
    lines.extend([f'| {label} | Count |', '|---|---:|'])
    for value, count in sorted(counts.items()):
        lines.append(f'| {_cell(value)} | {count} |')
    if not counts:
        lines.append('| (none) | 0 |')
    lines.append('')


def _newest(folder, pattern):
    files = [p for p in folder.rglob(pattern) if p.is_file()]
    return max(files, key=lambda p: (p.stat().st_mtime_ns, str(p))) if files else None


def _log(path, limit, pattern=None, private=False):
    selected = deque(maxlen=limit)
    first = last = None
    with path.open(encoding='utf-8-sig', errors='replace') as stream:
        for line in stream:
            if REDACT.search(line) or (private and PRIVATE.search(line)):
                # For unfiltered logs, preserve the last-N-physical-lines window.
                if pattern is None:
                    selected.append(None)
                continue
            stamp = TIMESTAMP.search(line)
            if stamp:
                first = first or stamp[0]
                last = stamp[0]
            if pattern is None or pattern.search(line):
                selected.append(line.rstrip('\r\n'))
    return [line for line in selected if line is not None], first, last


def collect(mo2_root, profile, *, mod_name=DEFAULT_MOD_NAME, data_mod=None, out=None):
    """Create a new evidence bundle; never overwrite an earlier bundle or source."""
    root = Path(mo2_root).resolve()
    output = (Path(out) if out is not None else
              ROOT / 'local/evidence' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError('Evidence output must be outside the MO2 tree')
    if not profile or profile in ('.', '..') or '/' in profile or '\\' in profile:
        raise ValueError('Expected one profile directory name')
    # Collect before creating output, so ordinary input errors leave no partial bundle.
    lines = ['# Hold Music evidence', '', f'MO2: `{_cell(root)}`',
             f'Profile: `{_cell(profile)}`', '', '## Runtime JSON', '']
    missing, copies = [], {}
    dirs = storage_dirs(root, mod_name, data_mod)
    for filename, array, label in (('receipts.json', 'performances', 'Receipt outcomes'),
                                   ('trace.json', 'entries', 'Trace events')):
        found = locate(filename, dirs)
        existing = {item.path for item in found}
        missing.extend(str(folder / filename) for folder in dirs if folder / filename not in existing)
        for index, item in enumerate(found, 1):
            raw = item.path.read_bytes()
            content = raw.decode('utf-8-sig', errors='replace')
            clean = redact(content)
            name = f'{filename[:-5]}-{index:02d}.json'
            # Preserve bytes exactly when no redaction is needed.
            copies[name] = raw if clean == content else clean.encode('utf-8')
            lines.extend([f'### {filename} — candidate {index}', '',
                          f'Path: `{_cell(item.path)}`',
                          f'Mtime (Unix seconds): {item.mtime}', f'Size (bytes): {item.size}',
                          f'Copy: [{name}]({name})',
                          f'Redacted lines: {len(content.splitlines()) - len(clean.splitlines())}', ''])
            try:
                data = json.loads(content)
                rows = data[array]
                if not isinstance(rows, list):
                    raise ValueError('Expected an array')
            except (ValueError, TypeError, KeyError):
                lines.extend(['Entry count: unavailable (invalid JSON or missing array).', ''])
                continue
            lines.extend([f'Entry count: {len(rows)}', '', f'#### {label}', ''])
            field = 'outcome' if array == 'performances' else 'event'
            counts = Counter()
            for row in rows:
                # No suppressed content is recovered into the report from parsed JSON.
                if REDACT.search(json.dumps(row, ensure_ascii=False)):
                    continue
                value = row.get(field) if isinstance(row, dict) else None
                if isinstance(value, str):
                    counts[value] += 1
            _table(lines, counts, 'Outcome' if field == 'outcome' else 'Event')

    def add_log(title, path, expected, limit, pattern=None, private=False, timestamps=False):
        lines.extend([f'## {title}', ''])
        if path is None or not path.is_file():
            missing.append(str(expected))
            lines.extend(['Missing.', ''])
            return
        excerpt, first, last = _log(path, limit, pattern, private)
        lines.extend([f'File: `{_cell(path)}`', ''])
        if timestamps:
            lines.extend([f'First timestamp: {first or "not found"}',
                          f'Last timestamp: {last or "not found"}', ''])
        if excerpt:
            # Indentation renders literal log text, including any Markdown fences.
            lines.extend('    ' + line for line in excerpt)
        else:
            lines.append('No retained lines.')
        lines.append('')

    for filename in ('HoldMusic.log', 'HoldMusic-Service.log'):
        path = root / 'logs' / filename
        add_log(filename, path, path, 80)
    documents = root / 'profiles' / profile / 'experimental-documents'
    folder = documents / 'SKSE'
    add_log('SkyrimNet', _newest(folder, 'SkyrimNet*.log'), folder / 'SkyrimNet*.log',
            120, SKYRIMNET, private=True, timestamps=True)
    folder = documents / 'Logs/Script'
    add_log('Papyrus', _newest(folder, 'Papyrus.0.log'), folder / 'Papyrus.0.log',
            120, re.compile('HoldMusic'))
    lines.extend(['## Missing inputs', ''])
    lines.extend(f'- `{_cell(path)}`' for path in missing)
    if not missing:
        lines.append('None.')
    output.mkdir(parents=True, exist_ok=False)
    for name, data in copies.items():
        (output / name).write_bytes(data)
    report = output / 'report.md'
    report.write_text(redact('\n'.join(lines) + '\n'), encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mo2-root', required=True, type=Path)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--mod-name', default=DEFAULT_MOD_NAME)
    parser.add_argument('--data-mod')
    parser.add_argument('--out', type=Path, help='new output directory (default: local/evidence/<UTC timestamp>)')
    args = parser.parse_args(argv)
    try:
        report = collect(**vars(args))
    except (OSError, ValueError) as exc:
        # Exception messages can contain unredacted source paths.
        parser.exit(1, f'Cannot collect evidence: {type(exc).__name__}\n')
    print(redact(str(report)), end='\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
