"""Inspect a selected profile's loose Hold Music library without changing files."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.installed_library import inspect_installed_library


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mo2-root", required=True, type=Path)
    parser.add_argument("--profile", required=True, help="Explicit selected MO2 profile directory name")
    parser.add_argument("--game-data", type=Path, help="Explicit base-game Data layer, below active mods")
    parser.add_argument("--vfs-report", type=Path, help="Existing captured file-handle observations; no launch")
    parser.add_argument("--session-receipt-index", type=int,
                        help="Established process-session boundary; otherwise reserve all receipt slots")
    args = parser.parse_args(argv)
    try:
        report = inspect_installed_library(**vars(args))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Cannot inspect installed library: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
