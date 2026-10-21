"""Explicit read-only GET smoke checks for the attributed disabled SkyrimNet lab."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hold_music.se_lab_skyrimnet_smoke import collect_smoke, smoke_plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "collect"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--review-token")
    args = parser.parse_args(argv)
    if (args.operation == "collect") != (args.review_token is not None):
        parser.error("Only collect requires --review-token")
    try:
        report = smoke_plan(args.run_id) if args.operation == "plan" else collect_smoke(args.run_id, args.review_token)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        print(json.dumps({"status": "blocked", "reason": "Smoke preflight or bounded observation failed; no settings were changed."}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["status"] in ("ready_for_bounded_get", "disabled_controls_observed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
