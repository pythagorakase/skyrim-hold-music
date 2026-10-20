"""Durability and review boundaries using temporary fake installations only."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import hold_music.promotion_transaction as tx
from hold_music.promotion import STATIC_FILES
from promotion_fixtures import create_promotion_fixture, closed_processes


class ProcessCrash(BaseException):
    pass


def file_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def snapshot(root):
    return {str(path.relative_to(root)): (path.is_dir(), path.stat().st_mtime_ns,
            None if path.is_dir() else path.read_bytes()) for path in root.rglob("*")}


class PromotionTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = create_promotion_fixture(self.temp.name)
        self.args = self.fixture["arguments"]
        self.target = self.fixture["target"]
        self.mo2 = self.args["mo2_root"]
        self.original = file_bytes(self.target)

    def apply(self, token=None, **kwargs):
        if token is None:
            token = tx.promote_static(**self.args)["review_token"]
        return tx.promote_static(**self.args, review_token=token, apply=True,
                                 process_probe=kwargs.pop("process_probe", closed_processes), **kwargs)

    def rollback(self, token=None, **kwargs):
        if token is None:
            token = tx.rollback_static(self.mo2)["review_token"]
        return tx.rollback_static(self.mo2, review_token=token, apply=True,
                                  process_probe=kwargs.pop("process_probe", closed_processes), **kwargs)

    def journal(self):
        path = Path(tx.promotion_status(self.mo2)["journal_path"])
        return path, json.loads(path.read_text())

    def test_preview_and_status_write_nothing_or_probe_processes(self):
        before = snapshot(self.fixture["root"])
        probe = Mock(side_effect=AssertionError("Preview cannot run process inventory"))
        first = tx.promote_static(**self.args, process_probe=probe)
        self.assertTrue(first["can_apply"])
        self.assertEqual(first, tx.promote_static(**self.args, process_probe=probe))
        self.assertEqual(tx.promotion_status(self.mo2)["status"], "no_transaction")
        self.assertFalse(tx.rollback_static(self.mo2)["can_rollback"])
        self.assertEqual(snapshot(self.fixture["root"]), before)
        probe.assert_not_called()

    def test_static_only_apply_and_exact_byte_rollback_preserve_other_files(self):
        all_before = file_bytes(self.mo2)
        review = tx.promote_static(**self.args)
        result = self.apply(review["review_token"])
        self.assertEqual(result["status"], "static_applied")
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["installed"])
        after = file_bytes(self.mo2)
        target_prefix = self.target.relative_to(self.mo2).as_posix() + "/"
        for path, raw in all_before.items():
            if path.startswith(target_prefix) and path[len(target_prefix):] in STATIC_FILES:
                continue
            self.assertEqual(after[path], raw, path)
        for row in review["plan"]["files"]:
            if row["action"] in {"add_static", "replace_static"}:
                self.assertEqual((self.target / row["relative_path"]).read_bytes(),
                                 Path(row["source"]["path"]).read_bytes())
        path, journal = self.journal()
        controller = path.parent / "backups" / journal["transaction_id"] / "Scripts/HM_Controller.pex"
        self.assertEqual(controller.read_bytes(), self.original["Scripts/HM_Controller.pex"])
        self.assertEqual(self.rollback()["status"], "rolled_back")
        self.assertEqual(file_bytes(self.target), self.original)
        self.assertEqual(controller.read_bytes(), self.original["Scripts/HM_Controller.pex"])
        self.assertFalse(tx.promotion_status(self.mo2)["recovery_required"])

    def test_absent_and_stale_review_tokens_never_write(self):
        review = tx.promote_static(**self.args)
        for token in ("", "wrong", "invalid-☃"):
            before = snapshot(self.fixture["root"])
            self.assertEqual(self.apply(token)["status"], "blocked")
            self.assertEqual(snapshot(self.fixture["root"]), before)
        (self.target / "unrelated.txt").write_text("a later edit")
        before = snapshot(self.fixture["root"])
        self.assertEqual(self.apply(review["review_token"])["status"], "blocked")
        self.assertEqual(snapshot(self.fixture["root"]), before)

    def test_process_proof_requires_true_booleans_and_empty_inventory(self):
        review = tx.promote_static(**self.args)
        before = snapshot(self.fixture["root"])
        for result in (None, True, {}, dict(verified=1, quiescent=True, processes=[]),
                       dict(verified=True, quiescent=1, processes=[]),
                       dict(verified=True, quiescent=True, processes=["SkyrimVR.exe"])):
            self.assertEqual(self.apply(review["review_token"], process_probe=lambda: result)["status"], "blocked")
        self.assertEqual(snapshot(self.fixture["root"]), before)

    def test_default_probe_rejects_empty_malformed_and_failed_tasklist(self):
        with patch.object(tx.os, "name", "nt"):
            for output in ("", "INFO: not available", '"a.exe","123","Console"\n'):
                with patch.object(tx.subprocess, "run", return_value=Mock(stdout=output)):
                    self.assertFalse(tx.default_process_probe()["verified"])
            for output, expected in (
                ('"other.exe","123","Console","1","2 K"\n', True),
                ('"SkyrimVR.exe","123","Console","1","2 K"\n', False),
            ):
                with patch.object(tx.subprocess, "run", return_value=Mock(stdout=output)):
                    result = tx.default_process_probe()
                    self.assertTrue(result["verified"])
                    self.assertEqual(result["quiescent"], expected)
            with patch.object(tx.subprocess, "run", side_effect=subprocess.TimeoutExpired("tasklist", 15)):
                self.assertFalse(tx.default_process_probe()["verified"])

    def test_writer_lock_serializes_same_target(self):
        token = tx.promote_static(**self.args)["review_token"]
        loc = tx._locations(self.mo2, self.args["mod_name"])
        with tx._lock(loc):
            with self.assertRaisesRegex(ValueError, "writer"):
                self.apply(token)
        self.assertEqual(file_bytes(self.target), self.original)

    def test_crash_after_first_replace_is_observable_and_only_reviewed_rollback_recovers(self):
        original = tx._atomic_write
        writes = []
        def crash(path, raw, **kwargs):
            original(path, raw, **kwargs)
            if path.is_relative_to(self.target):
                writes.append(path)
                raise ProcessCrash()
        with patch.object(tx, "_atomic_write", side_effect=crash), self.assertRaises(ProcessCrash):
            self.apply()
        self.assertEqual(len(writes), 1)
        status = tx.promotion_status(self.mo2)
        self.assertEqual(status["state"], "applying")
        self.assertTrue(status["recovery_required"])
        self.assertFalse(tx.promote_static(**self.args)["can_apply"])
        self.assertEqual(self.rollback()["status"], "rolled_back")
        self.assertEqual(file_bytes(self.target), self.original)

    def test_crash_before_backup_leaves_original_target_and_guarded_rollback(self):
        original = tx._atomic_write
        def crash(path, raw, **kwargs):
            if "backups" in path.parts:
                raise ProcessCrash()
            return original(path, raw, **kwargs)
        with patch.object(tx, "_atomic_write", side_effect=crash), self.assertRaises(ProcessCrash):
            self.apply()
        self.assertEqual(file_bytes(self.target), self.original)
        self.assertEqual(tx.promotion_status(self.mo2)["state"], "preparing")
        self.assertEqual(self.rollback()["status"], "rolled_back")
        self.assertEqual(file_bytes(self.target), self.original)
        self.assertFalse(tx.promotion_status(self.mo2)["recovery_required"])

    def test_crash_after_restore_does_not_repeat_or_overwrite_later_edit(self):
        self.apply()
        original = tx._atomic_write
        def crash(path, raw, **kwargs):
            original(path, raw, **kwargs)
            if path.is_relative_to(self.target):
                raise ProcessCrash()
        with patch.object(tx, "_atomic_write", side_effect=crash), self.assertRaises(ProcessCrash):
            self.rollback()
        self.assertEqual(tx.promotion_status(self.mo2)["state"], "rolling_back")
        self.assertEqual(self.rollback()["status"], "rolled_back")
        self.assertEqual(file_bytes(self.target), self.original)

    def test_final_boundary_checks_processes_and_every_static_file(self):
        stable = self.target / "HoldMusic.esp"
        stable.write_bytes((self.fixture["package"] / "HoldMusic.esp").read_bytes())
        original = tx._atomic_write
        def edit(path, raw, **kwargs):
            original(path, raw, **kwargs)
            if path.is_relative_to(self.target):
                stable.write_text("external edit of an unchanged static file")
        with patch.object(tx, "_atomic_write", side_effect=edit):
            report = self.apply()
        self.assertEqual(report["status"], "interrupted")
        self.assertEqual(stable.read_text(), "external edit of an unchanged static file")
        self.assertFalse(tx.rollback_static(self.mo2)["can_rollback"])

    def test_new_static_shadow_during_apply_interrupts_without_touching_it(self):
        shadow = self.mo2 / "overwrite/Scripts/HM_Library.pex"
        original = tx._atomic_write
        def edit(path, raw, **kwargs):
            original(path, raw, **kwargs)
            if path.is_relative_to(self.target):
                shadow.parent.mkdir(parents=True, exist_ok=True)
                shadow.write_text("external shadow")
        with patch.object(tx, "_atomic_write", side_effect=edit):
            result = self.apply()
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(shadow.read_text(), "external shadow")

    def test_external_journal_edit_is_not_overwritten_by_error_reporting(self):
        original = tx._atomic_write
        altered = []
        def edit(path, raw, **kwargs):
            original(path, raw, **kwargs)
            if path.is_relative_to(self.target):
                journal_path = tx._locations(self.mo2, self.args["mod_name"])["journal"]
                data = json.loads(journal_path.read_text())
                data["external_note"] = "keep this edit"
                journal_path.write_text(json.dumps(data))
                altered.append(journal_path.read_bytes())
        with patch.object(tx, "_atomic_write", side_effect=edit):
            report = self.apply()
        self.assertEqual(report["status"], "interrupted")
        self.assertFalse(report["journal_update_recorded"])
        self.assertEqual(Path(report["journal_path"]).read_bytes(), altered[0])

    def test_invalid_journal_paths_and_context_fail_closed_without_writes(self):
        self.apply()
        path, journal = self.journal()
        cases = [
            lambda j: j["entries"][0].update(relative_path="../outside"),
            lambda j: j["context"].update(profile_lists={}),
            lambda j: j["context"].update(profile="../other-profile"),
            lambda j: j["entries"][0].update(before=dict(exists=True, sha256="0" * 64, size=0)),
            lambda j: j["protected_before"].append(dict(path=str(self.mo2 / "../escape"), exists=False)),
        ]
        for edit in cases:
            modified = deepcopy(journal)
            edit(modified)
            path.write_text(json.dumps(modified))
            before = snapshot(self.fixture["root"])
            with self.assertRaises(ValueError):
                tx.rollback_static(self.mo2)
            self.assertEqual(snapshot(self.fixture["root"]), before)
        path.write_text(json.dumps(journal))

    def test_no_change_package_creates_no_transaction(self):
        for relative in STATIC_FILES:
            source = self.fixture["package"] / relative
            if source.exists():
                target = self.target / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        before = snapshot(self.fixture["root"])
        report = tx.promote_static(**self.args)
        self.assertFalse(report["can_apply"])
        self.assertTrue(any(row["code"] == "no_static_changes" for row in report["blockers"]))
        self.assertEqual(snapshot(self.fixture["root"]), before)

    def test_prior_terminal_journals_and_backups_survive_new_transaction(self):
        first = self.apply()
        self.rollback()
        second = self.apply()
        self.assertNotEqual(first["transaction_id"], second["transaction_id"])
        root = Path(second["journal_path"]).parent
        old = json.loads((root / "history" / (first["transaction_id"] + ".json")).read_text())
        self.assertEqual(old["state"], "rolled_back")
        self.assertEqual((root / "backups" / first["transaction_id"] /
                          "Scripts/HM_Controller.pex").read_bytes(), self.original["Scripts/HM_Controller.pex"])

    def test_actual_process_death_releases_lock_and_retains_reviewed_recovery_evidence(self):
        code = r"""
import json, os, sys
from pathlib import Path
import hold_music.promotion_transaction as tx
arguments = json.loads(sys.argv[1])
target = Path(sys.argv[2])
mode = sys.argv[3]
original = tx._atomic_write
def crash_after_replace(path, raw, **kwargs):
    original(path, raw, **kwargs)
    if path.is_relative_to(target):
        os._exit(73)
tx._atomic_write = crash_after_replace
proof = lambda: dict(verified=True, quiescent=True, processes=[])
if mode == 'apply':
    token = tx.promote_static(**arguments)['review_token']
    tx.promote_static(**arguments, apply=True, review_token=token, process_probe=proof)
else:
    token = tx.rollback_static(arguments['mo2_root'])['review_token']
    tx.rollback_static(arguments['mo2_root'], apply=True, review_token=token, process_probe=proof)
raise AssertionError('Crash boundary was not reached')
"""
        arguments = json.dumps({key: str(value) if isinstance(value, Path) else value
                                for key, value in self.args.items()})
        command = [sys.executable, "-B", "-X", "utf8", "-c", code, arguments, str(self.target)]
        result = subprocess.run(command + ["apply"], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual(tx.promotion_status(self.mo2)["state"], "applying")
        # The dead process's kernel lock must not prevent a fresh reviewed recovery.
        self.assertEqual(self.rollback()["status"], "rolled_back")
        self.assertEqual(file_bytes(self.target), self.original)
        self.apply()
        result = subprocess.run(command + ["rollback"], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual(tx.promotion_status(self.mo2)["state"], "rolling_back")
        self.assertEqual(self.rollback()["status"], "rolled_back")
        self.assertEqual(file_bytes(self.target), self.original)


if __name__ == "__main__":
    unittest.main()
