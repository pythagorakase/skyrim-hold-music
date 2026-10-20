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

    def shared_profile(self, report, name="other"):
        return next(row for row in report["shared_profiles"] if row["profile"] == name)

    def assert_incomplete_equivalence(self, report, virtual_path):
        self.assertIn("affected_profile_validation_incomplete", self.codes(report))
        other = self.shared_profile(report)
        self.assertFalse(other["projected_library_validated"])
        proof = other["content_equivalence"]
        self.assertFalse(proof["verified"])
        mismatch = next(row for row in proof["files"] if row["virtual_path"] == virtual_path)
        self.assertFalse(mismatch["before_equal"])
        self.assertFalse(mismatch["after_equal"])
        self.assert_readonly(report)

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

    def test_byte_identical_shared_library_can_have_distinct_untouched_winners(self):
        alternate = self.mo2 / "mods/Alternate"
        copy(self.flat / "hm_slot_01.wav", alternate / AUDIO / "hm_slot_01.wav")
        copy(self.flat / "receipts.json", alternate / STORAGE / "receipts.json")
        self.add_profile("other", "+Alternate\n+Meta\n+Audio\n")
        before = snapshot(self.root)
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        other = self.shared_profile(report)
        self.assertTrue(other["projected_library_validated"])
        self.assertTrue(other["affected_scope_complete"])
        self.assertEqual(other["validation_scope"], "mapped_loose_library_content")
        self.assertEqual(other["validation_basis"], "complete_before_after_equivalence")
        proof = other["content_equivalence"]
        self.assertEqual(proof["basis"], "mapped-loose-library-before-and-after-v1")
        self.assertTrue(proof["verified"])
        self.assertTrue(proof["before_equal"])
        self.assertTrue(proof["after_equal"])
        self.assertEqual(len(proof["files"]), 51)
        receipt = next(row for row in proof["files"]
                       if row["virtual_path"] == STORAGE + "/receipts.json")
        self.assertNotEqual(receipt["selected_before"]["path"], receipt["profile_before"]["path"])
        self.assert_readonly(report)
        self.assertEqual(snapshot(self.root), before)

    def test_untouched_other_profile_orphan_prevents_equivalence(self):
        alternate = self.mo2 / "mods/Alternate"
        orphan = alternate / AUDIO / "hm_slot_04.wav"
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(b"retain this unreferenced alternate-profile asset")
        self.add_profile("other", "+Alternate\n+Meta\n+Audio\n")
        before = snapshot(self.root)
        report = self.plan()
        self.assert_incomplete_equivalence(report, AUDIO + "/hm_slot_04.wav")
        self.assertEqual(snapshot(self.root), before)

    def test_missing_other_profile_receipts_do_not_equal_selected_empty_history(self):
        receipts_mod = self.mo2 / "mods/Receipts"
        copy(self.flat / "receipts.json", receipts_mod / STORAGE / "receipts.json")
        (self.meta / STORAGE / "receipts.json").unlink()
        self.add_profile("pilot", "+Receipts\n+Meta\n+Audio\n")
        self.add_profile("other", "-Receipts\n+Meta\n+Audio\n")
        before = snapshot(self.root)
        report = self.plan()
        self.assert_incomplete_equivalence(report, STORAGE + "/receipts.json")
        self.assertEqual(snapshot(self.root), before)

    def test_other_profile_trace_difference_blocks_without_disclosing_its_body(self):
        write_json(self.flat / "trace.json", {"version": 1, "entries": []})
        copy(self.flat / "trace.json", self.meta / STORAGE / "trace.json")
        alternate = self.mo2 / "mods/Alternate"
        write_json(alternate / STORAGE / "trace.json", {
            "version": 1, "entries": [{"private": "alternate-profile-private-trace-sentinel"}],
        })
        self.add_profile("other", "+Alternate\n+Meta\n+Audio\n")
        before = snapshot(self.root)
        report = self.plan()
        self.assert_incomplete_equivalence(report, STORAGE + "/trace.json")
        self.assertNotIn("alternate-profile-private-trace-sentinel", json.dumps(report))
        self.assertEqual(snapshot(self.root), before)

    def test_other_profile_out_of_range_asset_blocks_even_when_all_mapped_bytes_match(self):
        alternate = self.mo2 / "mods/Alternate"
        extra = alternate / AUDIO / "hm_slot_25.wav"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(b"noncanonical alternate-profile reservation")
        self.add_profile("other", "+Alternate\n+Meta\n+Audio\n")
        before = snapshot(self.root)
        report = self.plan()
        self.assertIn("affected_profile_validation_incomplete", self.codes(report))
        other = self.shared_profile(report)
        self.assertFalse(other["projected_library_validated"])
        proof = other["content_equivalence"]
        self.assertTrue(proof["before_equal"])
        self.assertTrue(proof["after_equal"])
        self.assertFalse(proof["verified"])
        self.assertIn("unexpected_slot_asset", {item["code"] for item in proof["inspection_blockers"]})
        self.assertEqual(snapshot(self.root), before)

    def test_untouched_other_only_winner_drift_after_final_merge_is_rejected(self):
        alternate = self.mo2 / "mods/Alternate"
        audio = alternate / AUDIO / "hm_slot_01.wav"
        copy(self.flat / "hm_slot_01.wav", audio)
        self.add_profile("other", "+Alternate\n+Meta\n+Audio\n")
        original = library_publication.plan_library_merge
        calls = 0

        def merge_then_edit(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 2:
                stamp = audio.stat()
                raw = bytearray(audio.read_bytes())
                raw[-1] ^= 1
                audio.write_bytes(raw)
                os.utime(audio, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            return result

        with patch.object(library_publication, "plan_library_merge", side_effect=merge_then_edit):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.plan()
        self.assertEqual(calls, 2)

    def test_invalid_selected_route_cannot_supply_shared_validation(self):
        higher = self.mo2 / "mods/Higher"
        copy(self.flat / "library.json", higher / MANIFEST)
        self.add_profile("pilot", "+Higher\n+Meta\n+Audio\n")
        self.add_profile("other", "+Higher\n+Meta\n+Audio\n")
        report = self.plan()
        self.assertIn("higher_priority_override", self.codes(report))
        self.assertIn("affected_profile_validation_incomplete", self.codes(report))
        other = self.shared_profile(report)
        self.assertFalse(other["projected_library_validated"])
        proof = other["content_equivalence"]
        self.assertFalse(proof["selected_reference_valid"])
        self.assertFalse(proof["verified"])
        self.assert_readonly(report)

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
