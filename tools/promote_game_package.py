"""Review a static package update or rollback; writes require --apply and a token."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hold_music.promotion import DEFAULT_DATA_MOD, DEFAULT_MOD
from hold_music.promotion_transaction import (
    promote_static, promotion_status, rollback_static,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mo2-root", type=Path, required=True)
    parser.add_argument("--mod-name", default=DEFAULT_MOD)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--rollback", action="store_true",
                           help="Review recovery of the current transaction; add --apply to restore")
    operation.add_argument("--status", action="store_true",
                           help="Inspect durable transaction state without creating files")
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--data-mod")
    parser.add_argument("--apply", action="store_true",
                        help="Execute this reviewed operation after fresh checks")
    parser.add_argument("--review-token",
                        help="Exact token from this operation's current read-only review")
    args = parser.parse_args(argv)
    promotion_options = (args.build_dir, args.source_root, args.profile, args.data_mod)
    if args.status or args.rollback:
        if any(value is not None for value in promotion_options):
            parser.error("--status/--rollback cannot be combined with promotion inputs")
    elif args.build_dir is None or args.source_root is None or args.profile is None:
        parser.error("promotion requires --build-dir, --source-root and --profile")
    if args.status and (args.apply or args.review_token is not None):
        parser.error("--status is read-only and accepts no execution token")
    if args.apply and not args.review_token:
        parser.error("--apply requires the exact --review-token from a prior review")
    if args.review_token is not None and not args.apply:
        parser.error("--review-token requires --apply")
    try:
        shared = dict(mo2_root=args.mo2_root, mod_name=args.mod_name)
        if args.status:
            result = promotion_status(**shared)
        elif args.rollback:
            result = rollback_static(**shared, apply=args.apply, review_token=args.review_token)
        else:
            result = promote_static(
                **shared, build_dir=args.build_dir, source_root=args.source_root,
                profile=args.profile,
                data_mod=args.data_mod if args.data_mod is not None else DEFAULT_DATA_MOD,
                apply=args.apply, review_token=args.review_token,
            )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 2 if result.get("blockers") or result.get("status") in {"blocked", "interrupted"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
