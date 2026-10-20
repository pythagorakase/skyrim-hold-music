"""Review explicit performer-contract upserts without writing the installed library."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.contract_migration import review_contract_migration


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mo2-root", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--proposal", dest="proposal_path", required=True, type=Path,
                        help="Explicit version-1 runtime_selection upserts; unmentioned contracts stay")
    parser.add_argument("--game-data", type=Path)
    parser.add_argument("--vfs-report", type=Path, help="Existing capture only; no launch")
    parser.add_argument("--session-receipt-index", type=int,
                        help="Established process-session boundary; otherwise preserve all receipt reservations")
    args = parser.parse_args(argv)
    try:
        report = review_contract_migration(**vars(args))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Cannot review contract migration: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
