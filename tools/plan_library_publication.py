"""Plan explicit split-library destinations without writing any installation file."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.library_publication import plan_library_publication


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged-library", required=True, type=Path)
    parser.add_argument("--destination-snapshot", required=True, type=Path,
                        help="Explicit flat snapshot that must match the fresh installed loose files")
    parser.add_argument("--mo2-root", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--metadata-mod", required=True, help="Existing active managed mod for manifest/lyrics")
    parser.add_argument("--audio-mod", required=True, help="Existing active managed mod for WAVs")
    parser.add_argument("--game-data", type=Path)
    parser.add_argument("--vfs-report", type=Path)
    parser.add_argument("--session-receipt-index", type=int)
    args = parser.parse_args(argv)
    try:
        report = plan_library_publication(**vars(args))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Cannot plan library publication: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
