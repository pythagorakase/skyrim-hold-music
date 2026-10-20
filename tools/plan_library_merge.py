"""Review additive library merging without writing files or deploying audio."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.library_merge import plan_library_merge


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged-library", required=True, type=Path,
                        help="Explicit source library containing existing recordings")
    parser.add_argument("--destination-library", required=True, type=Path,
                        help="Library to inspect; never modified by this command")
    parser.add_argument("--receipts", dest="receipts_path", type=Path,
                        help="Explicit current destination performance receipts")
    parser.add_argument("--session-receipt-index", type=int,
                        help="Established process-session boundary; otherwise reserve all receipt slots")
    args = parser.parse_args(argv)
    try:
        report = plan_library_merge(**vars(args))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Cannot review library merge: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
