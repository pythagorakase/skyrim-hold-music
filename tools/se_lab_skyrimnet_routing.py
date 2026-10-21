"""Review or collect four read-only attributed SkyrimNet routing GETs."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hold_music.se_lab_skyrimnet_routing import routing_plan, collect_routing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "collect"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--smoke-capture", required=True)
    parser.add_argument("--review-token")
    args = parser.parse_args(argv)
    if (args.operation == "collect") != (args.review_token is not None):
        parser.error("Only collect requires --review-token")
    try:
        report = (routing_plan(args.run_id, args.smoke_capture) if args.operation == "plan"
                  else collect_routing(args.run_id, args.smoke_capture, args.review_token))
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, RecursionError):
        print(json.dumps({"status": "blocked", "reason": "Routing preflight or bounded observation failed; no settings were changed."}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["status"] in ("ready_for_bounded_get", "configured_graph_fake_only_observed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
