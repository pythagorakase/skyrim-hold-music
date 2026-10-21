"""Review or collect a bounded MCP tool inventory from the attributed SkyrimNet lab."""
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
    parser.add_argument("--review-token")
    args = parser.parse_args(argv)
    if args.operation == "collect":
        if not args.review_token or not args.review_token.strip():
            parser.error("collect requires --review-token from its discovery plan")
    elif args.review_token is not None:
        parser.error("--review-token is accepted only for collect")

    try:
        from hold_music.se_lab_mcp_discovery import collect_discovery, discovery_plan

        if args.operation == "plan":
            report = discovery_plan(args.run_id, args.smoke_capture)
            expected_status = "ready_for_bounded_discovery"
        else:
            report = collect_discovery(args.run_id, args.smoke_capture, args.review_token)
            expected_status = "tools_discovered"
        succeeded = report["status"] == expected_status
        output = json.dumps(report, indent=2, allow_nan=False)
    except Exception:
        # Runtime/import/serialization errors may contain private session or payload data.
        output = json.dumps({
            "status": "incomplete",
            "reason": "MCP discovery preflight or bounded observation did not complete.",
        })
        succeeded = False
    print(output)
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
