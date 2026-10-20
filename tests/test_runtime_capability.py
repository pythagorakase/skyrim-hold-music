"""Capability evidence uses fixture trees and never launches Skyrim or a provider."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from hold_music.runtime_capability import (
    REPORT_FILENAME, SCRIPT_NAMES, VERIFICATION_FILES, HELPER_FILES,
    capture_inputs, create_report, descriptor, receipt_capability,
    required_test_ids, validate_capability,
)

REPO = Path(__file__).resolve().parents[1]
TEST_SOURCE = """import unittest
class RuntimeSelectionTests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(1, 1)
    def test_legacy(self):
        self.assertTrue(True)
"""


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode("utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "checkout/game_package"
        self.build = self.root / "isolated/build"
        self.package = self.build / "package"
        for folder in ("src", "data", "imports"):
            (self.source / folder).mkdir(parents=True)
        for name in SCRIPT_NAMES:
            text = "fixture source " + name
            write(self.source / f"src/Scripts/Source/{name}.psc", text)
            write(self.package / f"Scripts/Source/{name}.psc", text)
            write(self.package / f"Scripts/{name}.pex", "fixture PEX " + name)
            write(self.build / f"disassembly/{name}.pas", "fixture PAS " + name)
        for relative in VERIFICATION_FILES:
            write(self.source / relative, "fixture verification " + relative)
        for relative in HELPER_FILES:
            write(self.source.parent / relative, "fixture helper " + relative)
        write(self.source / "tests/test_runtime_selection.py", TEST_SOURCE)
        self.decompiler = self.root / "tools/Champollion.exe"
        write(self.decompiler, "fixture tool")
        self.hashes = {path.relative_to(self.package).as_posix(): sha(path)
                       for path in self.package.rglob("*") if path.is_file()}
        self.plan = {
            "inputs": {"decompiler": {"path": str(self.decompiler), "sha256": sha(self.decompiler)}},
            "source_files": {path.relative_to(self.source).as_posix(): sha(path)
                             for folder in ("src", "data", "imports")
                             for path in (self.source / folder).rglob("*") if path.is_file()},
        }
        write(self.build / "package-hashes.json", json.dumps(self.hashes))
        write(self.build / "build-plan.json", json.dumps(self.plan))
        self.inputs = capture_inputs(self.build, self.source, self.plan)
        ids = self.inputs["required_test_ids"]
        self.result = dict(tests_run=len(ids), started=ids, passed=ids,
                           failures=0, errors=0, skipped=0,
                           expected_failures=0, unexpected_successes=0)
        self.report = create_report(self.inputs, self.result)
        self.receipt = {"plan": self.plan, "package_hashes": self.hashes}
        self.save_report()

    def save_report(self):
        raw = json.dumps(self.report).encode("utf-8")
        write(self.build / REPORT_FILENAME, raw)
        self.receipt["runtime_selection_capability"] = receipt_capability(raw)

    def validate(self):
        return validate_capability(self.receipt, self.build, self.source)

    def tree(self):
        return {str(path.relative_to(self.root)): (path.stat().st_mtime_ns, sha(path))
                for path in self.root.rglob("*") if path.is_file()}

    def test_valid_evidence_is_read_only_and_only_claims_offline_candidate(self):
        before = self.tree()
        report = self.validate()
        self.assertEqual(report["status"], "verified_offline")
        self.assertEqual(report["tests_run"], 2)
        self.assertFalse(report["installed"])
        self.assertFalse(report["runtime_verified"])
        self.assertEqual(self.tree(), before)

    def test_missing_capability_is_legacy_but_arbitrary_flags_are_not(self):
        self.receipt.pop("runtime_selection_capability")
        self.assertIsNone(self.validate())
        for value in (True, None, {"supported": True}, descriptor()):
            self.receipt["runtime_selection_capability"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate()

    def test_receipt_schema_descriptor_and_report_location_are_exact(self):
        original = deepcopy(self.receipt["runtime_selection_capability"])
        for changes in ({"schema_version": True}, {"verification_file": "../outside.json"},
                        {"verification_sha256": "0" * 64}, {"extra": True},
                        {"descriptor": dict(descriptor(), runtime_verified=True)}):
            self.receipt["runtime_selection_capability"] = dict(original, **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.validate()

    def test_all_measured_artifacts_helpers_and_sources_are_bound(self):
        paths = [
            self.package / "Scripts/HM_Library.pex",
            self.build / "disassembly/HM_Library.pas",
            self.source / "src/Scripts/Source/HM_Library.psc",
            self.source / "tests/pex_vm.py",
            self.source / "tools/verify_runtime_selection.py",
            self.source.parent / "hold_music/runtime_contract.py",
        ]
        for path in paths:
            original = path.read_bytes()
            with self.subTest(path=path):
                path.write_bytes(original + b"\nchanged")
                with self.assertRaises(ValueError):
                    self.validate()
                path.write_bytes(original)

    def test_source_and_package_added_files_do_not_escape_inventory(self):
        for path in (self.source / "src/new.psc", self.package / "new.pex"):
            write(path, "new")
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validate()
            path.unlink()

    def test_package_receipt_and_duplicated_json_keys_are_rejected(self):
        self.receipt["package_hashes"] = {"different": "0" * 64}
        with self.assertRaises(ValueError):
            self.validate()
        raw = (self.build / REPORT_FILENAME).read_bytes()
        bad = b'{"schema_version":1,"schema_version":1}'
        write(self.build / REPORT_FILENAME, bad)
        self.receipt["runtime_selection_capability"]["verification_sha256"] = hashlib.sha256(bad).hexdigest()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.validate()
        write(self.build / REPORT_FILENAME, raw)

    def test_complete_named_test_set_must_pass_without_skips_or_failures(self):
        changes = [
            {"tests_run": 0}, {"tests_run": True}, {"passed": []},
            {"started": self.result["started"] * 2}, {"passed": ["different.test"]},
            *({name: 1} for name in (
                "failures", "errors", "skipped", "expected_failures", "unexpected_successes")),
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                create_report(self.inputs, dict(self.result, **change))

    def test_test_source_and_named_method_inventory_are_bound(self):
        path = self.source / "tests/test_runtime_selection.py"
        write(path, TEST_SOURCE + "    def test_new_case(self):\n        pass\n")
        with self.assertRaises(ValueError):
            self.validate()
        for source in ("pass", "class X(Base):\n def test_x(self): pass",
                       "class X(unittest.TestCase):\n async def test_x(self): pass",
                       "class X(unittest.TestCase):\n def test_x(self): pass\n def test_x(self): pass"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                required_test_ids(source.encode())

    def test_extra_report_claims_and_tampered_evidence_cannot_be_self_asserted(self):
        for change in ({"runtime_verified": True}, {"status": "passed_in_game"},
                       {"extra": True}, {"installed": 0}):
            report = dict(self.report, **change)
            raw = json.dumps(report).encode()
            write(self.build / REPORT_FILENAME, raw)
            self.receipt["runtime_selection_capability"] = receipt_capability(raw)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate()

    def test_disassembler_provenance_is_bound_but_never_opened_from_a_receipt(self):
        self.receipt["plan"] = deepcopy(self.plan)
        self.receipt["plan"]["inputs"]["decompiler"]["path"] = str(self.root / "must-not-read")
        with self.assertRaises(ValueError):
            self.validate()
        self.assertFalse((self.root / "must-not-read").exists())

    def test_reader_injection_observes_fixed_inputs(self):
        seen = []
        def reader(path):
            seen.append(path)
            return path.read_bytes()
        validate_capability(self.receipt, self.build, self.source, read_bytes=reader)
        self.assertIn(self.build / REPORT_FILENAME, seen)
        self.assertIn(self.build / "disassembly/HM_Controller.pas", seen)
        self.assertIn(self.source.parent / "hold_music/runtime_contract.py", seen)
        self.assertNotIn(self.decompiler, seen)

    def test_byte_identical_relocated_artifacts_keep_valid_evidence(self):
        copied = self.root / "relocated"
        shutil.copytree(self.root / "checkout", copied / "checkout")
        shutil.copytree(self.build, copied / "build")
        report = validate_capability(
            self.receipt, copied / "build", copied / "checkout/game_package")
        self.assertEqual(report["status"], "verified_offline")

    def test_invalid_build_plan_is_cleanly_rejected(self):
        for plan in (None, {}, {"inputs": []}, {"inputs": {"decompiler": True}}):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                capture_inputs(self.build, self.source, plan)

    def prepare_runner(self, test_source=TEST_SOURCE):
        for relative in ("tools/verify_runtime_selection.py",):
            shutil.copyfile(REPO / "game_package" / relative, self.source / relative)
        shutil.copyfile(REPO / "hold_music/runtime_capability.py",
                        self.source.parent / "hold_music/runtime_capability.py")
        write(self.source / "tests/test_runtime_selection.py", test_source)
        (self.build / REPORT_FILENAME).unlink(missing_ok=True)
        args = [sys.executable, "-X", "utf8", "-B",
                str(self.source / "tools/verify_runtime_selection.py"),
                "--build-dir", str(self.build), "--source-root", str(self.source),
                "--decompiler", str(self.decompiler)]
        env = dict(os.environ, HOLD_MUSIC_TEST_BUILD=str(self.build),
                   PYTHONDONTWRITEBYTECODE="1")
        return args, env

    def test_runner_records_real_named_test_outcomes_for_explicit_candidate(self):
        args, env = self.prepare_runner()
        run = subprocess.run(args, env=env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        raw = (self.build / REPORT_FILENAME).read_bytes()
        self.receipt["runtime_selection_capability"] = receipt_capability(raw)
        self.assertEqual(self.validate()["tests_run"], 2)
        repeat = subprocess.run(args, env=env, capture_output=True, text=True)
        self.assertNotEqual(repeat.returncode, 0)
        self.assertEqual((self.build / REPORT_FILENAME).read_bytes(), raw)

    def test_runner_refuses_wrong_build_failed_skipped_and_mutated_inputs(self):
        cases = {
            "failure": TEST_SOURCE.replace("self.assertEqual(1, 1)", "self.assertEqual(1, 2)"),
            "skip": TEST_SOURCE.replace("self.assertEqual(1, 1)", "self.skipTest('fixture')"),
            "change": TEST_SOURCE.replace(
                "self.assertEqual(1, 1)",
                "from pathlib import Path\n        Path(__file__).write_text('changed')"),
            "wrong_build": TEST_SOURCE,
        }
        for label, source in cases.items():
            args, env = self.prepare_runner(source)
            if label == "wrong_build":
                env["HOLD_MUSIC_TEST_BUILD"] = str(self.root / "other")
            with self.subTest(label=label):
                run = subprocess.run(args, env=env, capture_output=True, text=True)
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse((self.build / REPORT_FILENAME).exists())

if __name__ == "__main__":
    unittest.main()
