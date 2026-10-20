"""Independent adversarial checks using synthetic installation trees only."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hold_music.promotion import SETTINGS, STATIC_FILES, STORAGE
from hold_music import promotion_transaction as transaction
from hold_music.promotion_transaction import (
    promote_static, promotion_status, rollback_static,
)
from promotion_fixtures import create_promotion_fixture, closed_processes


def file_state(root):
    """Capture bytes and timestamps so accidental rewrites are also visible."""
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


class PromotionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name).resolve()
        self.fixture = create_promotion_fixture(self.workspace / "first")
        self.arguments = self.fixture["arguments"]
        self.target = self.fixture["target"]
        self.mo2 = Path(self.arguments["mo2_root"])
        self.profile = self.fixture["profile_dir"]

    def preview(self):
        return promote_static(**self.arguments, process_probe=closed_processes)

    def apply(self, token=None, probe=closed_processes):
        expects_success = token is None
        if token is None:
            token = self.preview()["review_token"]
        result = promote_static(
            **self.arguments, process_probe=probe, apply=True, review_token=token)
        if expects_success:
            self.assertEqual(result["status"], "static_applied", result)
        return result

    def rollback(self, *, apply=False, token=None, probe=closed_processes):
        return rollback_static(
            self.mo2, mod_name=self.arguments.get("mod_name"),
            process_probe=probe, apply=apply, review_token=token)

    def assert_refused(self, operation):
        try:
            report = operation()
        except (ValueError, RuntimeError, OSError):
            return
        self.assertTrue(
            report.get("status") in {"blocked", "interrupted"}
            or (bool(report.get("blockers")) and (
                report.get("can_apply") is False or report.get("can_rollback") is False)),
            report)

    def static_bytes(self):
        return {
            relative: (self.target / relative).read_bytes()
            if (self.target / relative).is_file() else None
            for relative in STATIC_FILES
        }

    def test_protected_file_change_invalidates_apply_token_without_static_writes(self):
        token = self.preview()["review_token"]
        path = self.target / (STORAGE + "/receipts.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"version":1,"performances":[{"later":"event"}]}', encoding="utf-8")
        before = file_state(self.target)
        self.assert_refused(lambda: self.apply(token))
        self.assertEqual(file_state(self.target), before)

    def test_cross_target_token_cannot_authorize_matching_candidate(self):
        token = self.preview()["review_token"]
        other = create_promotion_fixture(self.workspace / "second")
        before = file_state(other["target"])
        self.assert_refused(lambda: promote_static(
            **other["arguments"], process_probe=closed_processes,
            apply=True, review_token=token))
        self.assertEqual(file_state(other["target"]), before)

    def test_apply_token_cannot_authorize_rollback(self):
        token = self.preview()["review_token"]
        self.assertEqual(self.apply(token)["status"], "static_applied")
        before = file_state(self.target)
        self.assert_refused(lambda: self.rollback(apply=True, token=token))
        self.assertEqual(file_state(self.target), before)

    def test_rollback_preserves_later_gameplay_files_and_restores_static_bytes(self):
        original = self.static_bytes()
        self.apply()
        updates = {
            self.target / (STORAGE + "/receipts.json"):
                b'{"version":1,"performances":[{"after":"gameplay"}]}',
            self.target / (STORAGE + "/trace.json"):
                b'{"version":1,"entries":[{"after":"gameplay"}]}',
            self.target / "Sound/fx/holdmusic/new-after-play.wav": b"new private audio",
            self.target / SETTINGS: b"[General]\nuser_customized=1\n",
            self.profile / "saves/after-play.ess": b"new save bytes",
            self.profile / "saves/after-play.skse": b"new co-save bytes",
        }
        for path, raw in updates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        preserved = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in updates}
        review = self.rollback()
        self.assertFalse(review.get("blockers"), review)
        self.rollback(apply=True, token=review["review_token"])
        self.assertEqual(self.static_bytes(), original)
        self.assertEqual(
            {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in updates},
            preserved)

    def test_rollback_remains_available_after_candidate_and_source_are_removed(self):
        original = self.static_bytes()
        self.apply()
        for key in ("build_dir", "source_root"):
            path = Path(self.arguments[key]).resolve()
            self.assertTrue(path.is_relative_to(self.workspace))
            shutil.rmtree(path)
        review = self.rollback()
        self.assertFalse(review.get("blockers"), review)
        self.rollback(apply=True, token=review["review_token"])
        self.assertEqual(self.static_bytes(), original)

    def test_later_static_edit_refuses_all_rollback_before_other_files_are_restored(self):
        self.apply()
        edited = self.target / "Scripts/HM_Library.pex"
        edited.write_bytes(b"later independently installed library")
        before = file_state(self.target)
        self.assert_refused(lambda: self.rollback())
        self.assertEqual(file_state(self.target), before)

    def test_corrupt_backup_refuses_all_rollback_without_restoring_other_targets(self):
        self.apply()
        review = self.rollback()
        backups = review["backups"]
        self.assertTrue(backups)
        backup = Path(next(iter(backups.values()))["path"])
        self.assertTrue(backup.resolve().is_relative_to(self.workspace))
        backup.write_bytes(b"damaged original bytes")
        before = file_state(self.target)
        self.assert_refused(lambda: self.rollback())
        self.assert_refused(lambda: self.rollback(apply=True, token=review["review_token"]))
        self.assertEqual(file_state(self.target), before)

    def test_later_runtime_change_invalidates_rollback_token_without_restoration(self):
        self.apply()
        token = self.rollback()["review_token"]
        path = self.target / (STORAGE + "/trace.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"version":1,"entries":[{"later":"edit"}]}', encoding="utf-8")
        before = file_state(self.target)
        self.assert_refused(lambda: self.rollback(apply=True, token=token))
        self.assertEqual(file_state(self.target), before)

    def test_process_appearing_after_review_prevents_apply(self):
        token = self.preview()["review_token"]
        before = file_state(self.target)

        def running():
            raise RuntimeError("Synthetic Skyrim process is running")

        self.assert_refused(lambda: self.apply(token, probe=running))
        self.assertEqual(file_state(self.target), before)

    def test_process_appearing_after_rollback_review_prevents_restoration(self):
        self.apply()
        token = self.rollback()["review_token"]
        before = file_state(self.target)

        def running():
            raise RuntimeError("Synthetic MO2 process is running")

        self.assert_refused(lambda: self.rollback(apply=True, token=token, probe=running))
        self.assertEqual(file_state(self.target), before)

    def test_competing_process_writer_cannot_enter_same_target_transaction(self):
        token = self.preview()["review_token"]
        state = promotion_status(self.mo2, mod_name=self.arguments["mod_name"])
        lock = Path(state["journal_path"]).parent / "writer.lock"
        lock.parent.mkdir(parents=True)
        code = (
            "from pathlib import Path\n"
            "import sys\n"
            "from hold_music.job_store import _writer_lock\n"
            "with _writer_lock(Path(sys.argv[1])):\n"
            "    print('LOCKED', flush=True)\n"
            "    sys.stdin.readline()\n"
        )
        child = subprocess.Popen(
            [sys.executable, "-B", "-c", code, str(lock)],
            cwd=Path(__file__).resolve().parents[1],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "LOCKED")
            before = file_state(self.target)
            self.assert_refused(lambda: self.apply(token))
            self.assertEqual(file_state(self.target), before)
        finally:
            child.communicate("\n", timeout=10)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(self.apply(token)["status"], "static_applied")

    def test_journal_protected_path_cannot_escape_through_parent_segments(self):
        result = self.apply()
        journal_path = Path(result["journal_path"])
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        outside = self.mo2.parent / "outside-private-fixture.txt"
        outside.write_bytes(b"synthetic bytes outside installation")
        journal["protected_before"].append({
            "path": str(self.mo2 / ".." / outside.name), "exists": False,
            "kind": "installed_runtime_or_other",
        })
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        before = file_state(self.target)
        real_observe = transaction._observe
        reads_outside = []

        def observed(path):
            if Path(path).resolve() == outside.resolve():
                reads_outside.append(str(path))
            return real_observe(path)

        with patch.object(transaction, "_observe", side_effect=observed):
            self.assert_refused(lambda: self.rollback())
        self.assertEqual(reads_outside, [])
        self.assertEqual(file_state(self.target), before)

    def test_new_static_override_after_first_replacement_stops_next_write(self):
        token = self.preview()["review_token"]
        shadow = self.mo2 / "overwrite/Scripts/HM_Library.pex"
        real_write = transaction._atomic_write
        target_writes = []

        def write_with_external_override(path, raw, **options):
            real_write(path, raw, **options)
            if Path(path).is_relative_to(self.target):
                target_writes.append(Path(path))
                if len(target_writes) == 1:
                    shadow.parent.mkdir(parents=True, exist_ok=True)
                    shadow.write_bytes(b"external static override")

        with patch.object(transaction, "_atomic_write", side_effect=write_with_external_override):
            result = self.apply(token)
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(len(target_writes), 1)
        self.assertEqual(shadow.read_bytes(), b"external static override")

    def test_protected_change_after_final_replacement_cannot_report_success(self):
        review = self.preview()
        changes = [row for row in review["plan"]["files"]
                   if row["action"] in {"add_static", "replace_static"}]
        self.assertTrue(changes)
        final_target = self.target / changes[-1]["relative_path"]
        changed_runtime = self.target / (STORAGE + "/receipts.json")
        real_write = transaction._atomic_write

        def write_with_final_change(path, raw, **options):
            real_write(path, raw, **options)
            if Path(path) == final_target:
                changed_runtime.write_bytes(b'{"later":"external runtime change"}')

        with patch.object(transaction, "_atomic_write", side_effect=write_with_final_change):
            result = self.apply(review["review_token"])
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(changed_runtime.read_bytes(), b'{"later":"external runtime change"}')

    def test_edit_immediately_after_restore_is_not_adopted_as_successful_rollback(self):
        original = (self.target / "Scripts/HM_Controller.pex").read_bytes()
        self.apply()
        token = self.rollback()["review_token"]
        restored_target = self.target / "Scripts/HM_Controller.pex"
        real_write = transaction._atomic_write
        injections = []

        def restore_with_external_edit(path, raw, **options):
            real_write(path, raw, **options)
            if Path(path) == restored_target and raw == original:
                injections.append(str(path))
                restored_target.write_bytes(b"external edit immediately after restore")

        with patch.object(transaction, "_atomic_write", side_effect=restore_with_external_edit):
            result = self.rollback(apply=True, token=token)
        self.assertEqual(len(injections), 1)
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(restored_target.read_bytes(), b"external edit immediately after restore")


if __name__ == "__main__":
    unittest.main()
