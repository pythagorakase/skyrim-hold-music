from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import reconcile_bard_ownership as ownership
from engine import ConfigOverlay, get_scalar


CONFIG = """bard_singing:
  enabled: true # preserve this comment
  provider: openrouter
  openrouter:
    api_key: synthetic-private-key
    model: google/lyria-3-pro-preview
  acestep_local:
    base_url: http://localhost:8002/v1/chat/completions
    model: acemusic/acestep-v1.5-turbo
  playback:
    volume: 0.7
"""


class BardOwnershipTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        # macOS exposes /var through /private/var; use the tool's canonical path
        # identity so fault injection and dictionary lookups target the same file.
        self.parent = Path(temp.name).resolve()
        self.root = self.parent / "MO2"
        self.profile = self.root / "profiles/Test"
        self.source = self.root / "mods/Data" / ownership.CONFIG
        self.overwrite = self.root / "overwrite" / ownership.CONFIG
        self.runtime = self.profile / "hold-music-runtime"
        self.receipt_dir = self.parent / "private-recovery"
        self.write(self.profile / "modlist.txt", "+Adapter\n+Data\n-Inactive\n")
        self.write(self.source, CONFIG.replace("\n", "\r\n"))
        self.write(self.overwrite, CONFIG.replace("volume: 0.7", "volume: 0.6"))
        self.adapter = self.root / "plugins/hold_music_adapter/local.json"
        self.write(self.adapter, json.dumps({"profile": "Test", "mod": "Adapter", "data_mod": "Data"}))
        self.closed = mock.patch.object(ownership, "require_closed")
        self.require_closed = self.closed.start()
        self.addCleanup(self.closed.stop)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def state(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def plan(self):
        return ownership.plan_handoff(self.root, "Test")

    def apply(self):
        return ownership.apply_handoff(self.plan(), self.receipt_dir)

    def test_dry_run_never_writes_or_exposes_credentials(self):
        before = self.state()
        plan = self.plan()
        summary = plan.summary()
        self.assertEqual(before, self.state())
        self.assertEqual(len(summary["changes"]), 2)
        self.assertNotIn("synthetic-private-key", json.dumps(summary))
        self.assertNotIn("synthetic-private-key", repr(plan))
        self.assertFalse(self.receipt_dir.exists())
        self.require_closed.assert_not_called()

    def test_apply_disables_winner_and_adapter_then_rollback_restores_exact_bytes(self):
        before = self.state()
        result = self.apply()
        self.require_closed.assert_called_once()
        self.assertEqual(result["status"], "applied")
        for path in (self.source, self.overwrite):
            self.assertIn(b"enabled: false # preserve this comment", path.read_bytes())
            original = before[str(path.relative_to(self.root))][0]
            self.assertEqual(path.read_bytes(), original.replace(b"enabled: true", b"enabled: false"))
        receipt = Path(result["receipt"])
        self.assertNotIn("synthetic-private-key", receipt.read_text())
        self.assertEqual(ownership.rollback_handoff(receipt)["status"], "rolled_back")
        self.assertEqual({p: raw for p, (raw, _) in before.items()},
                         {p: raw for p, (raw, _) in self.state().items()})
        # Rollback is idempotent, including when a previous run was interrupted.
        self.assertEqual(ownership.rollback_handoff(receipt)["status"], "rolled_back")

    def test_no_op_and_bom_encoding_comment_preservation(self):
        for encoding, bom in (("utf-8", b"\xef\xbb\xbf"), ("utf-16-le", b"\xff\xfe"),
                              ("cp1252", b"")):
            with self.subTest(encoding=encoding):
                raw = bom + CONFIG.replace("preserve", "café preserve").encode(encoding)
                self.source.write_bytes(raw)
                after = self.plan().changes[self.source]
                self.assertEqual(after, bom + CONFIG.replace("preserve", "café preserve")
                                 .replace("enabled: true", "enabled: false").encode(encoding))
        self.source.write_bytes(ownership._disabled(self.source.read_bytes()))
        self.overwrite.write_bytes(ownership._disabled(self.overwrite.read_bytes()))
        self.assertEqual(self.plan().summary()["changes"], [])

    def test_pending_overlay_merges_dashboard_edits_and_restores_route(self):
        original = self.source.read_bytes()
        bridge = ConfigOverlay(self.source, self.runtime)
        bridge.prepare("http://127.0.0.1:1234/temporary-secret-route")
        bridge.overlay.write_bytes(bridge.overlay.read_bytes().replace(b"volume: 0.7", b"volume: 0.4"))
        before = {p: raw for p, (raw, _) in self.state().items()}
        result = self.apply()
        after = self.source.read_bytes()
        self.assertIn(b"volume: 0.4", after)
        self.assertIn(b"enabled: false", after)
        self.assertNotIn(b"temporary-secret-route", after)
        self.assertEqual(get_scalar(after.decode(), ("bard_singing", "provider")), "openrouter")
        self.assertFalse(bridge.baseline.exists())
        self.assertFalse(bridge.overlay.exists())
        ownership.rollback_handoff(result["receipt"])
        self.assertEqual(before, {p: raw for p, (raw, _) in self.state().items()})
        self.assertEqual(original, self.source.read_bytes())

    def test_overlay_only_enabled_edit_cannot_reenable_disabled_source(self):
        self.source.write_bytes(self.source.read_bytes().replace(b"enabled: true", b"enabled: false"))
        bridge = ConfigOverlay(self.source, self.runtime)
        bridge.prepare("http://127.0.0.1:1234/temporary")
        bridge.overlay.write_bytes(bridge.overlay.read_bytes().replace(b"enabled: false", b"enabled: true"))
        plan = self.plan()
        self.assertNotIn(self.source, plan.changes)
        self.apply()
        self.assertFalse(get_scalar(self.source.read_text(), ("bard_singing", "enabled")))

    def test_changed_source_survives_when_overlay_has_no_dashboard_edits(self):
        bridge = ConfigOverlay(self.source, self.runtime)
        bridge.prepare("http://127.0.0.1:1234/temporary")
        self.source.write_bytes(self.source.read_bytes().replace(b"volume: 0.7", b"volume: 0.2"))
        self.apply()
        self.assertIn(b"volume: 0.2", self.source.read_bytes())

    def test_ambiguous_pending_overlay_blocks_without_any_write(self):
        bridge = ConfigOverlay(self.source, self.runtime)
        bridge.prepare("http://127.0.0.1:1234/temporary")
        bridge.overlay.write_bytes(bridge.overlay.read_bytes().replace(b"volume: 0.7", b"volume: 0.4"))
        self.source.write_bytes(self.source.read_bytes().replace(b"volume: 0.7", b"volume: 0.2"))
        before = self.state()
        with self.assertRaisesRegex(ValueError, "both changed"):
            self.plan()
        self.assertEqual(before, self.state())

    def test_conflict_and_orphaned_baseline_require_review(self):
        self.write(self.runtime / "BardSinging.conflict.yaml", CONFIG)
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.plan()
        (self.runtime / "BardSinging.conflict.yaml").unlink()
        self.write(self.runtime / "BardSinging.baseline.yaml", CONFIG)
        with self.assertRaisesRegex(ValueError, "orphaned"):
            self.plan()

    def test_changed_guard_or_new_overwrite_invalidates_plan_before_backups(self):
        self.overwrite.unlink()
        plan = self.plan()
        self.write(self.overwrite, CONFIG)
        with self.assertRaisesRegex(ValueError, "since planning"):
            ownership.apply_handoff(plan, self.receipt_dir)
        self.assertFalse(self.receipt_dir.exists())
        plan = self.plan()
        self.adapter.write_text(self.adapter.read_text().replace('"Test"', '"Other"'))
        with self.assertRaisesRegex(ValueError, "since planning"):
            ownership.apply_handoff(plan, self.receipt_dir)

    def test_rollback_refuses_changed_target_before_restoring_other_files(self):
        result = self.apply()
        self.source.write_bytes(self.source.read_bytes().replace(b"volume: 0.7", b"volume: 0.5"))
        before = self.state()
        with self.assertRaisesRegex(ValueError, "will not overwrite"):
            ownership.rollback_handoff(result["receipt"])
        self.assertEqual(before, self.state())

    def test_rollback_refuses_corrupt_backup(self):
        result = self.apply()
        backup = next(self.receipt_dir.glob("*.before"))
        backup.write_bytes(b"damaged")
        before = self.state()
        with self.assertRaisesRegex(ValueError, "backup hash"):
            ownership.rollback_handoff(result["receipt"])
        self.assertEqual(before, self.state())

    def test_rollback_rejects_changed_profile_context(self):
        result = self.apply()
        self.write(self.profile / "modlist.txt", "+Other\n+Data\n")
        before = self.state()
        with self.assertRaisesRegex(ValueError, "context changed"):
            ownership.rollback_handoff(result["receipt"])
        self.assertEqual(before, self.state())

    def test_change_during_apply_keeps_recovery_and_does_not_overwrite_new_input(self):
        real_write = ownership._atomic_write
        def concurrent_edit(path, raw):
            real_write(path, raw)
            if path == self.source:
                self.overwrite.write_bytes(CONFIG.replace("volume: 0.7", "volume: 0.2").encode())
        with mock.patch.object(ownership, "_atomic_write", side_effect=concurrent_edit):
            with self.assertRaisesRegex(ValueError, "since planning"):
                self.apply()
        self.assertIn(b"volume: 0.2", self.overwrite.read_bytes())
        receipt = self.receipt_dir / "receipt.json"
        self.assertEqual(json.loads(receipt.read_text())["status"], "incomplete")
        with self.assertRaisesRegex(ValueError, "will not overwrite"):
            ownership.rollback_handoff(receipt)

    def test_partial_apply_has_recovery_receipt_and_can_be_rolled_back(self):
        before = {p: raw for p, (raw, _) in self.state().items()}
        real_write = ownership._atomic_write
        def interrupted(path, raw):
            if path == self.overwrite:
                raise OSError("synthetic interruption")
            return real_write(path, raw)
        with mock.patch.object(ownership, "_atomic_write", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.apply()
        receipt = self.receipt_dir / "receipt.json"
        self.assertEqual(json.loads(receipt.read_text())["status"], "incomplete")
        self.assertFalse(get_scalar(self.source.read_text(), ("bard_singing", "enabled")))
        ownership.rollback_handoff(receipt)
        self.assertEqual(before, {p: raw for p, (raw, _) in self.state().items()})

    def test_rollback_recovers_replace_before_checkpoint_was_saved(self):
        before = {p: raw for p, (raw, _) in self.state().items()}
        real_save = ownership._save_receipt
        def lost_checkpoint(path, receipt):
            if any(row["state"] == "applied" for row in receipt["files"]):
                raise KeyboardInterrupt("simulated process termination")
            real_save(path, receipt)
        with mock.patch.object(ownership, "_save_receipt", side_effect=lost_checkpoint):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        receipt = self.receipt_dir / "receipt.json"
        self.assertEqual(json.loads(receipt.read_text())["status"], "prepared")
        self.assertNotEqual(before, {p: raw for p, (raw, _) in self.state().items()})
        ownership.rollback_handoff(receipt)
        self.assertEqual(before, {p: raw for p, (raw, _) in self.state().items()})

    def test_apply_and_rollback_require_closed_game_and_mo2(self):
        self.require_closed.side_effect = RuntimeError("Close Skyrim and MO2")
        before = self.state()
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(before, self.state())
        self.assertFalse(self.receipt_dir.exists())

    def test_unknown_boolean_and_invalid_names_fail_closed(self):
        for value in ('"false"', "yes", "false\n  enabled: true"):
            self.write(self.source, CONFIG.replace("true # preserve this comment", value))
            with self.assertRaises(ValueError):
                self.plan()
        for profile in ("../Test", "Test.", "CON"):
            with self.assertRaises(ValueError):
                ownership.plan_handoff(self.root, profile)

    def test_cli_dry_run_and_errors_do_not_leak_private_config(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ownership.main(["--mo2-root", str(self.root), "--profile", "Test"]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "dry_run")
        self.write(self.adapter, '{"secret": "synthetic-private-key", broken')
        with redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit):
                ownership.main(["--mo2-root", str(self.root), "--profile", "Test"])
        self.assertNotIn("synthetic-private-key", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
