"""Review or collect one get_plugins query from the attributed disabled SE lab."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "collect"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--smoke-capture", required=True, type=Path)
    parser.add_argument("--discovery-capture", required=True, type=Path)
    parser.add_argument("--review-token")
    args = parser.parse_args(argv)
    if args.operation == "collect":
        if not args.review_token or not args.review_token.strip():
            parser.error("collect requires --review-token from its plugin inspection plan")
    elif args.review_token is not None:
        parser.error("--review-token is accepted only for collect")
    try:
        from hold_music.se_lab_mcp_plugins import plugins_plan, collect_plugins
        common = (args.run_id, args.smoke_capture, args.discovery_capture)
        if args.operation == "plan":
            report = plugins_plan(*common)
            expected = "ready_for_one_plugin_query"
        else:
            report = collect_plugins(*common, args.review_token)
            expected = "expected_plugins_observed"
        succeeded = report["status"] == expected
        output = json.dumps(report, indent=2, allow_nan=False)
    except Exception:
        output = json.dumps({"status": "incomplete", "reason": "Plugin inspection preflight or bounded observation did not complete."})
        succeeded = False
    print(output)
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
