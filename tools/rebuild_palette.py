#!/usr/bin/env python3
"""Rebuild the dashboard and local game-package palette from canonical documents.

The editorial date defaults to the spec's ISO Reconciled field. No wall-clock
date, deployment, provider request or Obsidian setting is changed by this tool.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

import build_dashboard
import build_game_adapter
from build_palette_data import BuildError, snapshot_date


def source_date(path):
    source = Path(path).read_text(encoding="utf-8-sig")
    match = re.search(r"^\*\*Reconciled:\*\*\s*(\d{4}-\d{2}-\d{2})\s*$", source, re.M)
    if not match:
        raise BuildError("Add an ISO Reconciled date (YYYY-MM-DD) to the spec or supply --date.")
    return snapshot_date(match.group(1))


def main(argv=None):
    cli = build_dashboard.parser(default_date=None)
    cli.description = __doc__
    args = cli.parse_args(argv)
    try:
        editorial_date = args.date or source_date(args.spec)
    except (BuildError, OSError, argparse.ArgumentTypeError) as exc:
        cli.exit(1, f"Palette rebuild failed: {exc}\n")
    build_args = ["--spec", str(args.spec), "--bank", str(args.bank), "--date", editorial_date]
    if args.output:
        build_args.extend(["--output", str(args.output)])
    if args.skip_node_check:
        build_args.append("--skip-node-check")
    result = build_dashboard.main(build_args)
    if result:
        return result
    build_game_adapter.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
