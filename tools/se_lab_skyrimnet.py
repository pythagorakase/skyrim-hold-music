"""Review, install, or explicitly launch and locally inspect the disabled SkyrimNet tier."""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from hold_music import se_lab_skyrimnet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "preflight", "install-plan", "install", "install-status", "recover",
                                            "launch-plan", "launch", "collect"))
    parser.add_argument("--show-files", action="store_true", help="Include individual payload files and snapshots")
    parser.add_argument("--review-token")
    parser.add_argument("--recovery-action", choices=("retain_partial", "acknowledge_published"))
    parser.add_argument("--apply", action="store_true", help="Apply the reviewed recovery action only")
    parser.add_argument("--baseline-evidence", type=Path, help="JSON references to accepted baseline captures")
    parser.add_argument("--run-id", help="Exact retained SkyrimNet first-boot run ID for local collection")
    parser.add_argument("--timeout-seconds", type=float, default=None, help="Bound process observation to 1–60 seconds")
    args = parser.parse_args(argv)
    if args.command in {"install", "launch"} and not args.review_token:
        parser.error(args.command + " requires --review-token from its plan")
    if args.command == "recover":
        if not args.recovery_action or bool(args.review_token) != args.apply:
            parser.error("recover requires --recovery-action; --apply and --review-token must be supplied together")
    elif args.recovery_action or args.apply or (args.review_token and args.command not in {"install", "launch"}):
        parser.error("Recovery flags require recover; action tokens require install or launch")
    if (args.command in {"launch-plan", "launch"}) != bool(args.baseline_evidence):
        parser.error("--baseline-evidence is required only for launch-plan and launch")
    if (args.command == "collect") != bool(args.run_id):
        parser.error("--run-id is required only for collect")
    if args.timeout_seconds is not None and args.command != "launch":
        parser.error("--timeout-seconds is only accepted with launch")
    runtime = args.command in {"launch-plan", "launch", "collect"}
    if runtime and args.show_files:
        parser.error("Runtime commands expose only their sanitized summaries")
    try:
        if args.command in {"launch-plan", "launch"}:
            if args.baseline_evidence.stat().st_size > 65536:
                raise ValueError("Baseline reference file exceeds its bound")
            references = se_lab_skyrimnet._json(args.baseline_evidence.read_bytes())
            if args.command == "launch-plan":
                report = se_lab_skyrimnet.launch_plan(references)
            else:
                report = se_lab_skyrimnet.launch(references, args.review_token,
                    timeout_seconds=30 if args.timeout_seconds is None else args.timeout_seconds)
        elif args.command == "collect":
            report = se_lab_skyrimnet.collect(args.run_id)
        elif args.command == "install":
            report = se_lab_skyrimnet.install(args.review_token)
        elif args.command == "recover":
            report = se_lab_skyrimnet.recover_installation(args.recovery_action,
                review_token=args.review_token, apply=args.apply)
        else:
            function = {"plan": se_lab_skyrimnet.preparation_plan, "preflight": se_lab_skyrimnet.preflight,
                "install-plan": se_lab_skyrimnet.installation_plan, "install-status": se_lab_skyrimnet.installation_status}
            report = function[args.command]()
        if runtime:
            inputs = report.pop("inputs", None)
            if inputs is not None:
                report["accepted_baselines"] = inputs["acceptance"]
            report.pop("baseline_evidence", None)
            report.pop("processes", None)
        elif not args.show_files:
            if "files" in report:
                report["file_count"] = len(report.pop("files"))
                report["shared_game_file_count"] = len(report.pop("shared_game_inventory"))
                report.pop("snapshot")
            if "inputs" in report:
                inputs = report.pop("inputs")
                report["file_count"] = len(inputs["files"])
                report["application_archive"] = inputs["application_archive"]
                report["inputs_token"] = inputs["inputs_token"]
                report.pop("before")
            report.pop("observation", None)
        print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
        if runtime:
            return 0 if report["status"] in {"ready_for_explicit_launch", "launched_attributed", "local_evidence_collected"} else 1
        return 1 if report["blockers"] else 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Runtime parsing/process errors can involve generated private state.
        detail = "Runtime review/action failed; retained evidence is preserved." if runtime else str(error)
        print("Cannot prepare SkyrimNet SE lab: " + detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
