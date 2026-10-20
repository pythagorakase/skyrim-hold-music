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
from hold_music.executor import execute, plan_work, recover_publication
from hold_music.job_store import inspect_jobs, repair_journal
from hold_music.job_review import continue_job, reconcile_job
from hold_music.library import Library
from hold_music.registry import load_registry
from hold_music.runtime_paths import DEFAULT_MOD_NAME, resolve_receipts


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
    parser.add_argument('--registry', type=Path, help='required for planning or generation')
    journal_group = parser.add_mutually_exclusive_group()
    journal_group.add_argument('--job-status', action='store_true',
                              help='read private-journal summaries without writing or calling a provider')
    journal_group.add_argument('--recover-job', metavar='ID',
                              help='inspect a retained audio result for provider-free publication')
    journal_group.add_argument('--repair-journal', action='store_true',
                              help='explicitly recover a crashed local SQLite journal; no generation or publication')
    journal_group.add_argument('--continue-job', metavar='ID',
                              help='review retained lyrics for one music request; requires --spend to dispatch')
    journal_group.add_argument('--reconcile-job', metavar='ID',
                              help='review an uncertain outcome using a private operator attestation')
    parser.add_argument('--apply-recovery', action='store_true',
                        help='publish --recover-job from saved audio; no provider requests')
    parser.add_argument('--review-token',
                        help='exact token from the matching continuation/reconciliation review')
    parser.add_argument('--resolution-json', type=Path,
                        help='private reconciliation evidence JSON; never posted to a provider')
    parser.add_argument('--apply-reconciliation', action='store_true',
                        help='record --reconcile-job evidence and close the attempt without resubmitting it')
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
    receipts_group = parser.add_mutually_exclusive_group()
    receipts_group.add_argument('--receipts', type=Path, help='explicit performance receipts file')
    receipts_group.add_argument('--mo2-root', type=Path, help='discover newest MO2 performance receipts')
    parser.add_argument('--mod-name', default=None, help=f'MO2 mod (default: {DEFAULT_MOD_NAME})')
    parser.add_argument('--data-mod', help='additional MO2 data mod to search')
    args = parser.parse_args(argv)
    if args.apply_recovery and not args.recover_job:
        parser.error('--apply-recovery requires --recover-job')
    if args.apply_reconciliation and not args.reconcile_job:
        parser.error('--apply-reconciliation requires --reconcile-job')
    if args.reconcile_job and args.resolution_json is None:
        parser.error('--reconcile-job requires --resolution-json')
    if args.resolution_json is not None and not args.reconcile_job:
        parser.error('--resolution-json requires --reconcile-job')
    if args.review_token is not None and not (args.continue_job or args.reconcile_job):
        parser.error('--review-token requires --continue-job or --reconcile-job')
    if ((args.continue_job and args.spend) or args.apply_reconciliation) and not args.review_token:
        parser.error('Applying continuation or reconciliation requires --review-token from a prior review')
    if (args.job_status or args.recover_job or args.repair_journal or args.reconcile_job) and args.spend:
        parser.error('Job inspection/recovery cannot be combined with --spend')
    if not (args.job_status or args.recover_job or args.repair_journal or
            args.continue_job or args.reconcile_job) and args.registry is None:
        parser.error('--registry is required for planning or generation')
    if args.mo2_root is None and (args.mod_name is not None or args.data_mod is not None):
        parser.error('--mod-name and --data-mod require --mo2-root')
    args.mod_name = args.mod_name or DEFAULT_MOD_NAME
    try:
        if args.repair_journal:
            print(json.dumps(repair_journal(args.library), ensure_ascii=False, indent=2, allow_nan=False))
            return 0
        if args.job_status:
            print(json.dumps(dict(status='job_status', jobs=inspect_jobs(args.library)),
                             ensure_ascii=False, indent=2, allow_nan=False))
            return 0
        receipts_path = (resolve_receipts(args.mo2_root, args.mod_name, args.data_mod)
                         if args.mo2_root is not None else args.receipts)
        print(f'Receipts: {receipts_path}' if receipts_path is not None else
              f'Receipts: none found or selected; library default applies: {args.library / "receipts.json"}',
              file=sys.stderr)
        library = Library(args.library, receipts_path=receipts_path)
        if args.continue_job:
            report = continue_job(args.continue_job, library=library,
                client=_Client(args.bardsinging), ffmpeg=args.ffmpeg,
                max_jobs=args.max_jobs, max_usd=args.max_usd, review_token=args.review_token,
                dry_run=not args.spend, spend=args.spend, show_briefs=args.show_briefs)
            print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
            return 1 if report['status'] in ('failed', 'blocked', 'budget_exceeded', 'recovery_required') \
                or report.get('can_continue') is False else 0
        if args.reconcile_job:
            try:
                resolution = json.loads(args.resolution_json.read_text(encoding='utf-8-sig'))
            except (OSError, ValueError):
                raise ValueError('Cannot read private resolution JSON') from None
            report = reconcile_job(args.reconcile_job, library=library, resolution=resolution,
                review_token=args.review_token, apply=args.apply_reconciliation)
            print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
            return 1 if report['status'] in ('failed', 'blocked', 'recovery_required') \
                or report.get('can_reconcile') is False else 0
        if args.recover_job:
            report = recover_publication(args.recover_job, library=library,
                                         ffmpeg=args.ffmpeg, apply=args.apply_recovery)
            print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
            return 1 if report['status'] == 'failed' else 0
        jobs = plan_work(load_registry(args.registry), library,
                         performer_ids=args.performers, target_per_performer=args.target,
                         modes=args.modes, db_path=args.db, now_hours=args.now_hours,
                         allow_name_match=args.allow_name_match)
        report = execute(jobs, client=_Client(args.bardsinging), library=library,
                         ffmpeg=args.ffmpeg, max_jobs=args.max_jobs, max_usd=args.max_usd,
                         dry_run=not args.spend, spend=args.spend,
                         lyric_model=args.lyric_model, show_briefs=args.show_briefs)
    except sqlite3.Error as exc:
        parser.exit(1, f'Cannot access knowledge database or job journal: {type(exc).__name__}\n')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Cannot prepare library: {exc}\n')
    if args.spend:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if report['status'] in ('failed', 'budget_exceeded', 'recovery_required') else 0


if __name__ == '__main__':
    raise SystemExit(main())
