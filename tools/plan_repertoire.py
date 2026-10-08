#!/usr/bin/env python3
"""Print an offline repertoire decision from a JSON snapshot; execute nothing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hold_music.repertoire import plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="JSON snapshot to inspect (read only)")
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
        decision = plan(snapshot)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Cannot plan repertoire: {exc}\n")
    print(json.dumps(decision, ensure_ascii=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
