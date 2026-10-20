"""Print a read-only game-package promotion review; there is no apply option."""
import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hold_music.promotion import DEFAULT_DATA_MOD, DEFAULT_MOD, plan_promotion


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path,
                        help="Explicit game_package source directory used for the build")
    parser.add_argument("--mo2-root", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--mod-name", default=DEFAULT_MOD)
    parser.add_argument("--data-mod", default=DEFAULT_DATA_MOD)
    parser.add_argument("--library", type=Path, help="Optional library metadata inspection; never merged")
    args = parser.parse_args(argv)
    try:
        result = plan_promotion(**vars(args))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
