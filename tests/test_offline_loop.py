"""End-to-end offline proof and fail-closed staging/receipt regression checks."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hold_music.library import Library
from tools.verify_offline_loop import (
    CONTRACT_FIELDS, compatible_recording, reconcile_receipt, run, sha, stage_selection,
)

ROOT = Path(__file__).resolve().parents[1]


class OfflineLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "proof"
        with patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")), \
                patch("subprocess.run", side_effect=AssertionError("process launch forbidden")):
            self.report = run(self.root)
        self.library = Library(self.root / "source-library")
        self.decision = self.report["decisions"]["cached"]
        self.contract = self.report["staging"]["contract"]

    def test_end_to_end_proof_carries_scope_contract_and_readonly_evidence(self):
        self.assertEqual(self.report["status"], "passed")
        self.assertTrue(all(self.report["checks"].values()))
        self.assertEqual(self.report["provider_calls"], 0)
        self.assertFalse(self.report["installed"])
        self.assertFalse(self.report["runtime_tested"])
        self.assertEqual(self.report["bridge"]["resolution"], "plugin_base_form")
        self.assertEqual(self.report["decisions"]["topical"]["subject"]["kind"], "quest_success")
        self.assertEqual(self.report["decisions"]["topical"]["fallback"]["recording_id"], "slot:01")
        self.assertEqual(self.report["decisions"]["already_pending"]["pending_job_id"], "fixture:pending-job")
        cooldown = self.report["decisions"]["generation_cooldown"]
        self.assertEqual(cooldown["action"], "play_recording")
        self.assertIsNone(cooldown["lyric_brief"])
        self.assertTrue(any("generation cooldown" in reason for reason in cooldown["reasons"]))
        self.assertEqual(self.report["scope"]["save_id"], "offline-loop-fixture")
        self.assertEqual(json.loads((self.root / "report.json").read_text()), self.report)

    def test_stage_hashes_match_files_and_preserve_recording_metadata(self):
        receipt = self.report["staging"]
        self.assertFalse(receipt["runtime_receipts_in_payload"])
        self.assertEqual(receipt["status"], "staged_only")
        self.assertEqual(receipt["provenance"]["kind"], "synthetic_test_fixture")
        for entry in receipt["files"]:
            path = self.root / "staged/Data" / entry["path"]
            self.assertEqual(sha(path), entry["sha256"])
            self.assertEqual(path.stat().st_size, entry["bytes"])
        self.assertFalse(any(path.name == "receipts.json" for path in (self.root / "staged/Data").rglob("*")))
        staged = Library(self.root / "staged/library").load()
        self.assertEqual(compatible_recording(staged.recordings[0], self.contract), [])
        self.assertEqual(staged.recordings[0]["source"], self.library.load().recordings[0]["source"])
        for path, digest in self.report["source_code_sha256"].items():
            self.assertEqual(sha(ROOT / path), digest)

    def test_all_contract_changes_and_missing_metadata_fail_before_staging(self):
        for field in CONTRACT_FIELDS:
            with self.subTest(field=field):
                altered = deepcopy(self.contract)
                altered[field] += "-different"
                destination = self.root / ("reject-" + field)
                with self.assertRaises(ValueError):
                    stage_selection(self.library, self.decision, altered, destination)
                self.assertFalse(destination.exists())
        manifest = self.library.load().manifest
        del manifest["recordings"][0]["instrument_family"]
        (self.library.root / "library.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "instrument_family"):
            stage_selection(self.library, self.decision, self.contract, self.root / "legacy")
        self.assertFalse((self.root / "legacy").exists())

    def test_stage_rejects_wrong_actor_save_and_selection(self):
        for field, value in (("performer_id", "someone-else"), ("save_id", "other-save"),
                             ("world_id", "other-world"), ("composition_id", "other-song"),
                             ("recording_id", "slot:02"), ("action", "compose_lyrics")):
            with self.subTest(field=field):
                decision = dict(self.decision, **{field: value})
                destination = self.root / ("wrong-" + field)
                with self.assertRaises(ValueError):
                    stage_selection(self.library, decision, self.contract, destination)
                self.assertFalse(destination.exists())

    def test_truncated_audio_fails_before_staging(self):
        (self.library.root / "hm_slot_01.wav").write_bytes(b"RIFF")
        with self.assertRaisesRegex(ValueError, "invalid library"):
            stage_selection(self.library, self.decision, self.contract, self.root / "bad-wav")
        self.assertFalse((self.root / "bad-wav").exists())

    def test_stage_and_run_refuse_existing_destinations(self):
        marker = self.root / "precious.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            run(self.root)
        with self.assertRaises(FileExistsError):
            stage_selection(self.library, self.decision, self.contract, self.root / "staged")
        self.assertEqual(marker.read_text(), "keep")

    def test_receipt_replay_is_idempotent_and_conflicts_do_not_overwrite(self):
        branch = Library(self.root / "receipt-completed")
        receipt = self.report["receipt_reconciliation"]["completed"]["receipt"]
        before = branch.receipts_source.read_bytes()
        self.assertEqual(reconcile_receipt(branch, receipt, self.decision), "already_reconciled")
        for field, value in (("outcome", "interrupted"), ("at_hours", 101)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Conflicting replay"):
                reconcile_receipt(branch, dict(receipt, **{field: value}), self.decision)
        self.assertEqual(branch.receipts_source.read_bytes(), before)

    def test_bad_receipts_never_change_persisted_history(self):
        branch = Library(self.root / "receipt-completed")
        receipt = self.report["receipt_reconciliation"]["completed"]["receipt"]
        before = branch.receipts_source.read_bytes()
        for field, value in (("save_id", "other"), ("world_id", "other"),
                             ("performer_id", "other"), ("composition_id", "other"),
                             ("slot", 2), ("slot", True), ("at_hours", -1),
                             ("at_hours", float("nan")), ("outcome", "started"),
                             ("written_at", "not-a-timestamp"), ("id", "")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconcile_receipt(branch, dict(receipt, **{field: value}), self.decision)
        self.assertEqual(branch.receipts_source.read_bytes(), before)

    def test_completed_and_interrupted_receipts_apply_song_and_topic_windows(self):
        for outcome in ("completed", "interrupted"):
            with self.subTest(outcome=outcome):
                history = self.report["receipt_reconciliation"][outcome]
                self.assertEqual(history["repeated_reconciliation"], "already_reconciled")
                self.assertEqual(history["decisions"]["immediate"]["action"], "no_selection")
                self.assertEqual(history["decisions"]["after_song_window"]["action"], "no_selection")
                self.assertEqual(history["decisions"]["after_topic_window"]["action"], "play_recording")

    def test_other_owned_pilot_and_unowned_performer(self):
        other = run(self.root / "lynly", "lynly_star_sung")
        self.assertEqual(other["status"], "passed")
        self.assertEqual(other["staging"]["request"]["voice"], "female")
        self.assertEqual(other["staging"]["request"]["tradition"], "rift")
        with self.assertRaisesRegex(ValueError, "owned|registered"):
            run(self.root / "mikael", "mikael")
        self.assertFalse((self.root / "mikael").exists())

    def test_cli_works_from_outside_checkout_and_returns_machine_readable_summary(self):
        result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools/verify_offline_loop.py"),
                                 "--output", str(Path(self.temp.name) / "cli")],
                                cwd=self.temp.name, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["provider_calls"], 0)
        self.assertTrue(Path(summary["report"]).is_file())


if __name__ == "__main__":
    unittest.main()
