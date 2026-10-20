#!/usr/bin/env python3
"""Explicit, resumable preparation of a private blind-clip pool.

Dry-run is the default. Stop the workshop server before using --execute.
This tool never invents answers or retries a failed/unknown paid attempt.
"""

import argparse
import json
from pathlib import Path

try:
    from .workshop_blind import FORMATS, MODES, StorageBusy, storage_lock
    from .workshop_server import ROOT, Workshop, WorkshopError
except ImportError:
    from workshop_blind import FORMATS, MODES, StorageBusy, storage_lock
    from workshop_server import ROOT, Workshop, WorkshopError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=tuple(MODES), default="canonical")
    parser.add_argument("--format", choices=tuple(FORMATS), default="clip")
    parser.add_argument("--clips-per-style", type=int, default=3)
    parser.add_argument("--max-clips", type=int, default=33, help="Hard limit on new paid calls in this invocation (default: 33)")
    parser.add_argument("--include-challenger", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Explicitly authorize paid generation of the reported deficit")
    parser.add_argument("--root", type=Path, default=ROOT, help="Workshop repository root (default: this checkout)")
    args = parser.parse_args(argv)
    if not 1 <= args.clips_per_style <= 100 or not 1 <= args.max_clips <= 1000:
        parser.error("clips-per-style must be 1–100 and max-clips must be 1–1000")
    try:
        # Both CLIs hold this lock for their entire lifetime. This also prevents
        # a dry-run constructor from interrupting a receipt in a live seeder.
        with storage_lock(args.root):
            workshop = Workshop(args.root)
            report = workshop.blind.seed(mode=args.mode, clips_per_style=args.clips_per_style,
                                         max_clips=args.max_clips, include_challenger=args.include_challenger, format=args.format,
                                         execute=args.execute,
                                         on_event=lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
        print(json.dumps({"event": "report", **report}, ensure_ascii=False, indent=2), flush=True)
        return 1 if report.get("stopped") else 0
    except (WorkshopError, StorageBusy) as error:
        print(json.dumps({"event": "error", "error": str(error), "stopped": True, "executed": args.execute, "attempted": 0}), flush=True)
        return 1
    except (OSError, ValueError):
        print(json.dumps({"event": "error", "error": "Local workshop storage could not be read or written. No automatic retry was made.", "stopped": True}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
