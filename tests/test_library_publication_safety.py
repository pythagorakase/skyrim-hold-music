"""Independent read-only route-planning regressions with synthetic installations."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music import library_publication
from hold_music.runtime_contract import project_runtime_contract

STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusic"
AUDIO = "Sound/fx/holdmusic"
MANIFEST = STORAGE + "/library.json"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def wav(path):
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


class LibraryPublicationSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.mo2 = self.root / "mo2"
        self.base = self.root / "game/Data"
        self.meta = self.mo2 / "mods/Meta"
        self.audio = self.mo2 / "mods/Audio"
        self.flat = self.root / "flat"
        self.staged = self.root / "staged"
        for path in (self.base, self.meta, self.audio, self.flat, self.staged):
            path.mkdir(parents=True)
        self.add_profile("pilot", "+Meta\n+Audio\n")
        old = dict(
            slot=1, file="hm_slot_01.wav", performer_id="sven", region="whiterun",
            mode="instrumental", gender="male", duration_seconds=0.1,
            composition_id="existing-legacy", lyrics_sha256=None,
            recipe_id="historical-label", model_id="unknown", playable=True,
            created_at="2026-10-20T00:00:00Z",
            source={"kind": "import", "path_or_request_id": "synthetic-existing"},
            operator_extension={"keep": [None, "unknown"]})
        self.original = dict(version=1, slots=24, recordings=[old])
        write_json(self.flat / "library.json", self.original)
        write_json(self.flat / "receipts.json", {"version": 1, "performances": []})
        wav(self.flat / "hm_slot_01.wav")
        copy(self.flat / "library.json", self.meta / MANIFEST)
        copy(self.flat / "receipts.json", self.meta / STORAGE / "receipts.json")
        copy(self.flat / "hm_slot_01.wav", self.audio / AUDIO / "hm_slot_01.wav")
        self.contract = project_runtime_contract({
            "performer_id": "mikael", "request": dict(
                tradition="whiterun", recipe_id="fixture/cittern", recipe_revision="r1",
                model_id="synthetic-fixture", instrument_family="plucked_string",
                instrument_name="cittern", arrangement="solo_lute", mode="instrumental", voice="none"),
        })
        row = dict(deepcopy(old), **self.contract)
        row["composition_id"] = "new-fixture"
        row["source"] = {"kind": "import", "path_or_request_id": "synthetic-staged"}
        write_json(self.staged / "library.json", {
            "version": 1, "slots": 24, "recordings": [row],
            "runtime_selection": {"version": 1, "contracts": [self.contract]},
        })
        wav(self.staged / "hm_slot_01.wav")
        self.arguments = dict(staged_library=self.staged, destination_snapshot=self.flat,
                              mo2_root=self.mo2, profile="pilot", metadata_mod="Meta",
                              audio_mod="Audio", game_data=self.base)
        self.assertEqual(self.plan()["blockers"], [], "Fixture must begin with a valid clean plan")

    def add_profile(self, name, modlist):
        path = self.mo2 / "profiles" / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "modlist.txt").write_text(modlist, encoding="utf-8")
        return path

    def plan(self, **changes):
        return library_publication.plan_library_publication(**dict(self.arguments, **changes))

    def codes(self, report):
        return {item["code"] for item in report["blockers"]}

    def assert_readonly(self, report):
        for field in ("can_apply", "installed", "vfs_verified", "runtime_verified", "writes_performed"):
            self.assertIs(report[field], False)

    def test_raw_manifest_equivalence_does_not_normalize_unknown_metadata(self):
        changed = deepcopy(self.original)
        changed["recordings"][0]["operator_extension"]["keep"] = ["inferred"]
        write_json(self.flat / "library.json", changed)
        before = snapshot(self.root)
        report = self.plan()
        self.assertIn("snapshot_mismatch", self.codes(report))
        self.assertIsNone(report["proposed_manifest"])
        self.assert_readonly(report)
        self.assertEqual(snapshot(self.root), before)

    def test_empty_receipts_are_not_equivalent_to_missing_receipts(self):
        (self.flat / "receipts.json").unlink()
        report = self.plan()
        self.assertIn("snapshot_mismatch", self.codes(report))
        item = next(row for row in report["snapshot_equivalence"]["files"]
                    if row["virtual_path"].endswith("/receipts.json"))
        self.assertFalse(item["flat_file"]["exists"])
        self.assertTrue(item["installed_winner"]["exists"])

    def test_flat_snapshot_cannot_omit_effective_orphan_assets(self):
        orphan = self.audio / AUDIO / "hm_slot_04.wav"
        orphan.write_bytes(b"reserved synthetic orphan")
        before = snapshot(self.root)
        report = self.plan()
        self.assertIn("snapshot_mismatch", self.codes(report))
        self.assertFalse(report["snapshot_equivalence"]["matches"])
        self.assertEqual(snapshot(self.root), before)

    def test_same_bytes_in_higher_manifest_override_still_block_selected_route(self):
        higher = self.mo2 / "mods/Higher"
        copy(self.flat / "library.json", higher / MANIFEST)
        self.add_profile("pilot", "+Higher\n+Meta\n+Audio\n")
        report = self.plan()
        self.assertTrue(report["snapshot_equivalence"]["matches"])
        self.assertIn("higher_priority_override", self.codes(report))
        route = next(row for row in report["routes"] if row["virtual_path"] == MANIFEST)
        self.assertEqual(Path(route["physical_target"]), self.meta / MANIFEST)
        self.assertEqual(Path(route["simulated_winner"]["path"]), higher / MANIFEST)
        self.assert_readonly(report)

    def test_disabled_target_is_not_implicitly_enabled_or_rerouted(self):
        inactive = self.mo2 / "mods/Disabled"
        inactive.mkdir()
        self.add_profile("pilot", "+Meta\n+Audio\n-Disabled\n")
        before = snapshot(self.root)
        report = self.plan(metadata_mod="Disabled")
        self.assertIn("invalid_target_mod", self.codes(report))
        self.assertEqual(snapshot(self.root), before)

    def test_other_profile_with_both_targets_disabled_has_no_effective_change(self):
        self.add_profile("other", "-Meta\n-Audio\n")
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        other = next(row for row in report["shared_profiles"] if row["profile"] == "other")
        self.assertTrue(other["affected_scope_complete"])
        self.assertTrue(all(not row["effective_change"] for row in other["effects"]))
        self.assertTrue(all(not row["target_enabled"] for row in other["effects"]))

    def test_other_profile_fully_shadowing_both_routes_has_no_effective_change(self):
        shadow = self.mo2 / "mods/Shadow"
        copy(self.flat / "library.json", shadow / MANIFEST)
        wav(shadow / AUDIO / "hm_slot_02.wav")
        self.add_profile("other", "+Shadow\n+Meta\n+Audio\n")
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        other = next(row for row in report["shared_profiles"] if row["profile"] == "other")
        self.assertTrue(other["affected_scope_complete"])
        self.assertTrue(all(row["target_enabled"] for row in other["effects"]))
        self.assertTrue(all(row["higher_override"] for row in other["effects"]))
        self.assertTrue(all(not row["effective_change"] for row in other["effects"]))

    def test_other_profile_audio_only_visibility_still_requires_validation(self):
        other_meta = self.mo2 / "mods/OtherMeta"
        copy(self.flat / "library.json", other_meta / MANIFEST)
        self.add_profile("other", "+OtherMeta\n-Meta\n+Audio\n")
        before = snapshot(self.root)
        report = self.plan()
        self.assertIn("affected_profile_validation_incomplete", self.codes(report))
        other = next(row for row in report["shared_profiles"] if row["profile"] == "other")
        changed = [row for row in other["effects"] if row["effective_change"]]
        self.assertEqual([row["virtual_path"] for row in changed], [AUDIO + "/hm_slot_02.wav"])
        self.assertFalse(other["affected_scope_complete"])
        self.assertEqual(snapshot(self.root), before)

    def test_malformed_other_profile_is_not_assumed_unaffected(self):
        self.add_profile("other", "-Meta\n-Audio\nunparsed-entry\n")
        report = self.plan()
        self.assertIn("invalid_profile_scope", self.codes(report))
        other = next(row for row in report["shared_profiles"] if row["profile"] == "other")
        self.assertFalse(other["affected_scope_complete"])
        self.assert_readonly(report)

    def test_staged_audio_drift_after_merge_is_rejected(self):
        original = library_publication.plan_library_merge
        audio = self.staged / "hm_slot_01.wav"
        changed = False

        def merge_then_edit(*args, **kwargs):
            nonlocal changed
            result = original(*args, **kwargs)
            if not changed:
                changed = True
                stamp = audio.stat()
                raw = bytearray(audio.read_bytes())
                raw[-1] ^= 1
                audio.write_bytes(raw)
                os.utime(audio, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            return result

        with patch.object(library_publication, "plan_library_merge", side_effect=merge_then_edit):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.plan()

    def test_profile_added_after_scope_inventory_is_not_silently_omitted(self):
        original = library_publication._profiles

        def inventory_then_add(*args, **kwargs):
            result = original(*args, **kwargs)
            self.add_profile("late-profile", "+Meta\n+Audio\n")
            return result

        with patch.object(library_publication, "_profiles", side_effect=inventory_then_add):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.plan()
        self.assertTrue((self.mo2 / "profiles/late-profile/modlist.txt").exists())

    def test_unsafe_explicit_destination_name_and_overlapping_snapshot_are_rejected(self):
        before = snapshot(self.root)
        with self.assertRaises(ValueError):
            self.plan(metadata_mod="../outside")
        with self.assertRaises(ValueError):
            self.plan(destination_snapshot=self.meta)
        self.assertEqual(snapshot(self.root), before)


if __name__ == "__main__":
    unittest.main()
