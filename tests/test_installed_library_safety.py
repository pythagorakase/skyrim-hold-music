"""Independent layered-library checks using synthetic files, never an MO2 launch."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music import installed_library

STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusic"
AUDIO = "Sound/fx/holdmusic"
MANIFEST = STORAGE + "/library.json"
RECEIPTS = STORAGE + "/receipts.json"
LYRICS = STORAGE + "/hm_slot_01.lyrics.txt"
WAV = AUDIO + "/hm_slot_01.wav"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def write_wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 4410)


def snapshot(root):
    return {
        path.relative_to(root).as_posix():
        (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
        for path in root.rglob("*") if path.is_file()
    }


class InstalledLibrarySafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.mo2 = self.root / "mo2"
        self.high = self.mo2 / "mods/High"
        self.low = self.mo2 / "mods/Low"
        self.overwrite = self.mo2 / "overwrite"
        self.profile = self.mo2 / "profiles/pilot"
        for folder in (self.high, self.low, self.overwrite, self.profile):
            folder.mkdir(parents=True)
        (self.profile / "modlist.txt").write_text("+High\n+Low\n", encoding="utf-8")
        self.words = b"Synthetic words that must not appear in an inspection report.\n"
        self.row = dict(
            slot=1, file="hm_slot_01.wav", performer_id="sven", region="whiterun",
            mode="vocal", gender="male", duration_seconds=0.1,
            composition_id="fixture-song", lyrics_sha256=hashlib.sha256(self.words).hexdigest(),
            recipe_id="legacy-fixture", model_id="unknown",
            created_at="2026-10-20T00:00:00Z",
            source={"kind": "import", "path_or_request_id": "synthetic-fixture"},
            playable=True)
        self.manifest = dict(version=1, slots=24, recordings=[self.row])
        write_json(self.low / MANIFEST, self.manifest)
        (self.low / LYRICS).write_bytes(self.words)
        write_wav(self.low / WAV)

    def inspect(self, **kwargs):
        return installed_library.inspect_installed_library(self.mo2, "pilot", **kwargs)

    def assert_blocked(self, report, code):
        self.assertEqual(report["status"], "blocked")
        self.assertIn(code, {row["code"] for row in report["blockers"]})
        for field in ("installed", "vfs_verified", "runtime_verified", "writes_performed"):
            self.assertIs(report[field], False)

    def capture(self, rows):
        path = self.root / "capture.json"
        write_json(path, dict(version=2, profile="pilot", data_root=str(self.root / "not-read"),
                             observed_at=datetime.now(timezone.utc).isoformat(), files=rows))
        return path

    def test_bad_higher_manifest_never_falls_through_to_valid_lower_bytes(self):
        upper = self.high / MANIFEST
        upper.parent.mkdir(parents=True)
        for raw in (b"truncated {", b'{"version":1,"version":2,"slots":24,"recordings":[]}'):
            with self.subTest(raw=raw):
                upper.write_bytes(raw)
                before = snapshot(self.root)
                report = self.inspect()
                self.assert_blocked(report, "invalid_json")
                self.assertEqual(Path(report["files"][MANIFEST]["winner"]["path"]), upper)
                self.assertEqual(snapshot(self.root), before)

    def test_bad_effective_lyrics_block_instead_of_borrowing_lower_sidecar(self):
        upper = self.high / LYRICS
        upper.parent.mkdir(parents=True)
        upper.write_bytes(b"Different higher-priority words.")
        before = snapshot(self.root)
        report = self.inspect()
        self.assert_blocked(report, "invalid_lyrics")
        self.assertEqual(Path(report["files"][LYRICS]["winner"]["path"]), upper)
        self.assertNotIn(self.words.decode().strip(), json.dumps(report))
        self.assertEqual(snapshot(self.root), before)

    def test_missing_installed_lyrics_are_not_filled_from_offline_source(self):
        (self.low / LYRICS).unlink()
        scratch = self.root / "offline-source"
        scratch.mkdir()
        (scratch / "hm_slot_01.lyrics.txt").write_bytes(self.words)
        before = snapshot(self.root)
        report = self.inspect()
        self.assert_blocked(report, "missing_lyrics")
        self.assertIsNone(report["files"][LYRICS]["winner"])
        self.assertEqual(snapshot(self.root), before)

    def test_newer_lower_receipts_cannot_replace_malformed_effective_receipts(self):
        lower = self.low / RECEIPTS
        write_json(lower, {"version": 1, "performances": []})
        os.utime(lower, (2000000000, 2000000000))
        upper = self.overwrite / RECEIPTS
        upper.parent.mkdir(parents=True)
        upper.write_bytes(b'{"version":1,"performances":[')
        os.utime(upper, (1000000000, 1000000000))
        report = self.inspect()
        self.assert_blocked(report, "invalid_json")
        self.assertEqual(Path(report["files"][RECEIPTS]["winner"]["path"]), upper)
        self.assertTrue(report["files"][RECEIPTS]["shadowed_conflict"])

    def test_capture_opened_path_never_authorizes_reading_an_unknown_file(self):
        private = self.root / "must-not-be-opened.txt"
        private.write_bytes(b"synthetic private content")
        capture = self.capture([{
            "virtual_path": MANIFEST, "opened_path": str(private), "exists": True,
            "sha256": hashlib.sha256((self.low / MANIFEST).read_bytes()).hexdigest(),
        }])
        original_open = Path.open

        def guarded_open(path, *args, **kwargs):
            if path == private:
                raise AssertionError("Capture must not authorize a private-path read")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", guarded_open):
            report = self.inspect(vfs_report=capture)
        self.assert_blocked(report, "vfs_evidence_path")
        self.assertNotIn("synthetic private content", json.dumps(report))

    def test_old_matching_lower_capture_does_not_override_new_current_priority(self):
        upper = self.high / MANIFEST
        upper.parent.mkdir(parents=True)
        # Identical bytes still do not make the physical source/priority equivalent.
        upper.write_bytes((self.low / MANIFEST).read_bytes())
        capture = self.capture([{
            "virtual_path": MANIFEST, "opened_path": str(self.low / MANIFEST),
            "sha256": hashlib.sha256(upper.read_bytes()).hexdigest(),
        }])
        report = self.inspect(vfs_report=capture)
        self.assert_blocked(report, "vfs_evidence_priority")
        self.assertEqual(Path(report["files"][MANIFEST]["winner"]["path"]), upper)
        self.assertFalse(report["vfs_evidence"]["matched"][0]["matches_loose_winner"])

    def test_duplicate_virtual_capture_aliases_cannot_choose_a_second_observation(self):
        row = {
            "virtual_path": MANIFEST, "opened_path": str(self.low / MANIFEST),
            "sha256": hashlib.sha256((self.low / MANIFEST).read_bytes()).hexdigest(),
        }
        capture = self.capture([row, dict(row, virtual_path=MANIFEST.upper())])
        self.assert_blocked(self.inspect(vfs_report=capture), "invalid_vfs_evidence")

    def test_new_higher_override_during_validation_invalidates_the_snapshot(self):
        original = installed_library.wav_info
        upper = self.high / WAV

        def after_wav_read(path):
            info = original(path)
            write_wav(upper)
            return info

        with patch.object(installed_library, "wav_info", side_effect=after_wav_read):
            with self.assertRaisesRegex(ValueError, "changed during inspection"):
                self.inspect()
        self.assertTrue(upper.is_file(), "Inspector must preserve the externally added file")

    def test_same_size_edit_with_restored_timestamp_is_not_a_stable_snapshot(self):
        original = installed_library.wav_info
        audio = self.low / WAV

        def after_wav_read(path):
            info = original(path)
            before = audio.stat()
            raw = bytearray(audio.read_bytes())
            raw[-1] ^= 1
            audio.write_bytes(raw)
            os.utime(audio, ns=(before.st_atime_ns, before.st_mtime_ns))
            return info

        with patch.object(installed_library, "wav_info", side_effect=after_wav_read):
            with self.assertRaisesRegex(ValueError, "changed during inspection"):
                self.inspect()

    def test_candidate_removed_between_lookup_and_read_fails_cleanly(self):
        write_json(self.low / RECEIPTS, {"version": 1, "performances": []})
        original = installed_library._Snapshot.read
        for relative in (MANIFEST, WAV, RECEIPTS):
            target = self.low / relative
            raw = target.read_bytes()
            removed = False

            def disappearing_read(observation, path, **kwargs):
                nonlocal removed
                if path == target and not removed:
                    target.unlink()
                    removed = True
                return original(observation, path, **kwargs)

            try:
                with self.subTest(relative=relative), \
                        patch.object(installed_library._Snapshot, "read", disappearing_read):
                    with self.assertRaisesRegex(ValueError, "changed|disappeared|missing"):
                        self.inspect()
                self.assertTrue(removed)
            finally:
                target.write_bytes(raw)

    def test_duplicate_active_mod_aliases_block_without_reading_a_second_tree(self):
        (self.profile / "modlist.txt").write_text("+High\n+HIGH\n+Low\n", encoding="utf-8")
        report = self.inspect()
        self.assert_blocked(report, "duplicate_mod_entry")
        self.assertEqual(len([row for row in report["layers"] if row["kind"] == "mod"]), 2)


if __name__ == "__main__":
    unittest.main()
