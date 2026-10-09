#!/usr/bin/env python3
"""Write a private actor snapshot to an explicitly named path; print counts only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.knowledge_bridge import snapshot
from hold_music.library import Library
from hold_music.lyria_client import MODEL
from hold_music.registry import load_registry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--performer', required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True,
                        help='explicitly named private output path; never commit this snapshot')
    parser.add_argument('--now-hours', type=float)
    parser.add_argument('--since-hours', type=float)
    parser.add_argument('--max-observations', type=int, default=40)
    parser.add_argument('--allow-name-match', action='store_true')
    args = parser.parse_args(argv)
    try:
        performer = next((p for p in load_registry(args.registry).performers if p['id'] == args.performer), None)
        if performer is None:
            raise ValueError('Unknown performer')
        region = performer['region'] or 'nord'
        request = dict(tradition=region, arrangement='solo_lute_and_voice', mode='lyrical',
                       voice=performer['gender'], recipe_id=f'{region}/vocal', model_id=MODEL)
        data, report = snapshot(performer, args.db, Library(args.library), args.now_hours,
            request, max_observations=args.max_observations, since_hours=args.since_hours,
            allow_name_match=args.allow_name_match)
        if args.out.resolve() == args.db.resolve():
            raise ValueError('Snapshot output cannot replace the database')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation avoids replacing a database, manifest, or previous export.
        with args.out.open('x', encoding='utf-8') as output:
            json.dump(dict(snapshot=data, bridge_report=report), output,
                      ensure_ascii=False, indent=2, allow_nan=False)
            output.write('\n')
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f'Cannot write knowledge snapshot: {type(exc).__name__}\n')
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
