"""Run the candidate selector fixtures and emit artifact-bound offline evidence."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import importlib.util
import json
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from hold_music.runtime_capability import (
    REPORT_FILENAME, capture_inputs, create_report, _json, _same, _sha,
)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids = []
        self.passed_ids = []

    def startTest(self, test):
        self.started_ids.append(test.id())
        super().startTest(test)

    def addSuccess(self, test):
        self.passed_ids.append(test.id())
        super().addSuccess(test)

    def evidence(self):
        return {
            "tests_run": self.testsRun, "started": sorted(self.started_ids),
            "passed": sorted(self.passed_ids), "failures": len(self.failures),
            "errors": len(self.errors), "skipped": len(self.skipped),
            "expected_failures": len(self.expectedFailures),
            "unexpected_successes": len(self.unexpectedSuccesses),
        }


def run_required_tests(source_root, expected_ids):
    tests = Path(source_root) / "tests"
    sys.path.insert(0, str(tests))
    if "pex_vm" in sys.modules or "test_runtime_selection" in sys.modules:
        raise ValueError("Verification requires a fresh interpreter")
    spec = importlib.util.spec_from_file_location(
        "test_runtime_selection", tests / "test_runtime_selection.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    suite = unittest.TestLoader().loadTestsFromNames(expected_ids)
    return unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite).evidence()


def verify(build_dir, source_root, decompiler):
    build, source = Path(build_dir).resolve(), Path(source_root).resolve()
    if source != ROOT:
        raise ValueError("Verifier must run from the explicitly selected source checkout")
    selected = os.environ.get("HOLD_MUSIC_TEST_BUILD")
    if selected is None or Path(selected).resolve() != build:
        raise ValueError("HOLD_MUSIC_TEST_BUILD must select the explicit candidate build")
    target = build / REPORT_FILENAME
    if target.exists():
        raise ValueError("Use a fresh candidate verification report")
    plan = _json((build / "build-plan.json").read_bytes())
    inputs = capture_inputs(build, source, plan)
    tool = Path(decompiler).resolve()
    declared = inputs["disassembler"]
    if Path(declared["path"]).resolve() != tool or _sha(tool.read_bytes()) != declared["sha256"]:
        raise ValueError("Explicit disassembler differs from the build plan")
    result = run_required_tests(source, inputs["required_test_ids"])
    after = capture_inputs(build, source, plan)
    if not _same(inputs, after) or _sha(tool.read_bytes()) != declared["sha256"]:
        raise ValueError("Runtime verification inputs changed during testing")
    report = create_report(inputs, result)
    # Exclusive creation: failure cannot replace a previous successful report.
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--decompiler", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify(args.build_dir, args.source_root, args.decompiler)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"Verified {report['tests']['tests_run']} candidate runtime tests offline; nothing installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
