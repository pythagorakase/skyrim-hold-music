"""Review or explicitly install the isolated disabled SkyrimNet tier; never launch it."""
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
    parser.add_argument("command", choices=("plan", "preflight", "install-plan", "install", "install-status", "recover"))
    parser.add_argument("--show-files", action="store_true", help="Include individual payload files and snapshots")
    parser.add_argument("--review-token")
    parser.add_argument("--recovery-action", choices=("retain_partial", "acknowledge_published"))
    parser.add_argument("--apply", action="store_true", help="Apply the reviewed recovery action only")
    args = parser.parse_args(argv)
    if args.command == "install" and not args.review_token:
        parser.error("install requires --review-token from install-plan")
    if args.command == "recover":
        if not args.recovery_action or bool(args.review_token) != args.apply:
            parser.error("recover requires --recovery-action; --apply and --review-token must be supplied together")
    elif args.recovery_action or args.apply or (args.review_token and args.command != "install"):
        parser.error("Recovery flags are only accepted with recover; install tokens only with install")
    try:
        if args.command == "install":
            report = se_lab_skyrimnet.install(args.review_token)
        elif args.command == "recover":
            report = se_lab_skyrimnet.recover_installation(args.recovery_action,
                review_token=args.review_token, apply=args.apply)
        else:
            function = {"plan": se_lab_skyrimnet.preparation_plan, "preflight": se_lab_skyrimnet.preflight,
                "install-plan": se_lab_skyrimnet.installation_plan, "install-status": se_lab_skyrimnet.installation_status}
            report = function[args.command]()
        if not args.show_files:
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
        return 1 if report["blockers"] else 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("Cannot prepare SkyrimNet SE lab: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
