#!/usr/bin/env python3
"""Prepare instrumental, wordless or actor-known lyrical recordings; dry run by default."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music import lyria_client
from hold_music.lyricist import MODEL as LYRIC_MODEL
from hold_music.executor import execute, plan_work
from hold_music.library import Library
from hold_music.registry import load_registry


class _Client:
    def __init__(self, bardsinging):
        self.bardsinging = bardsinging

    def generate(self, prompt):
        return lyria_client.generate(prompt, key=lyria_client.read_openrouter_key(self.bardsinging))

    def chat_completion(self, **kwargs):
        return lyria_client.chat_completion(**kwargs,
            key=lyria_client.read_openrouter_key(self.bardsinging))


def _csv(value):
    result = [item.strip() for item in value.split(',')]
    if not all(result):
        raise argparse.ArgumentTypeError('Supply comma-separated nonempty values')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, type=Path)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--performers', type=_csv)
    parser.add_argument('--target', type=int, default=1)
    parser.add_argument('--modes', type=_csv, default=['instrumental'],
                        help='instrumental,wordless,lyrical; lyrical requires --db')
    parser.add_argument('--db', type=Path, help='read-only SkyrimNet database for lyrical mode')
    parser.add_argument('--now-hours', type=float, help='override last known in-game time')
    parser.add_argument('--allow-name-match', action='store_true',
                        help='allow exact actor name matching within the performer plugin')
    parser.add_argument('--lyric-model', default=LYRIC_MODEL)
    parser.add_argument('--show-briefs', action='store_true',
                        help='include PRIVATE memory summaries and lyrics in dry-run output')
    parser.add_argument('--max-jobs', type=int, default=1)
    parser.add_argument('--max-usd', default='0.10', help='USD budget (default: 0.10)')
    parser.add_argument('--ffmpeg', help='ffmpeg executable path (default: search PATH)')
    parser.add_argument('--bardsinging', type=Path, help='read-only YAML credential source')
    parser.add_argument('--spend', action='store_true', help='allow paid generation; never retry')
    args = parser.parse_args(argv)
    try:
        library = Library(args.library)
        jobs = plan_work(load_registry(args.registry), library,
                         performer_ids=args.performers, target_per_performer=args.target,
                         modes=args.modes, db_path=args.db, now_hours=args.now_hours,
                         allow_name_match=args.allow_name_match)
        report = execute(jobs, client=_Client(args.bardsinging), library=library,
                         ffmpeg=args.ffmpeg, max_jobs=args.max_jobs, max_usd=args.max_usd,
                         dry_run=not args.spend, spend=args.spend,
                         lyric_model=args.lyric_model, show_briefs=args.show_briefs)
    except sqlite3.Error as exc:
        parser.exit(1, f'Cannot read knowledge database: {type(exc).__name__}\n')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Cannot prepare library: {exc}\n')
    if args.spend:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if report['status'] in ('failed', 'budget_exceeded') else 0


if __name__ == '__main__':
    raise SystemExit(main())
