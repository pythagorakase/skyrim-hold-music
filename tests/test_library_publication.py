"""Synthetic loose-layer publication routes; no installed folders are touched."""
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

from hold_music.installed_library import (
    AUDIO_PATH, MANIFEST_PATH, RECEIPTS_PATH, STORAGE_PATH, TRACE_PATH,
)
from hold_music.library import Library
from hold_music.library_merge import plan_library_merge
from hold_music.library_publication import plan_library_publication
from hold_music.runtime_contract import runtime_identity_key


class LibraryPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.mo2 = self.root / "MO2"
        self.meta, self.audio_mod = self.mo2 / "mods/Meta", self.mo2 / "mods/Audio"
        self.base = self.root / "game/Data"
        self.staged, self.flat = self.root / "staged", self.root / "snapshot"
        for path in (self.meta, self.audio_mod, self.base, self.staged, self.flat):
            path.mkdir(parents=True)
        self.write(self.mo2 / "profiles/Pilot/modlist.txt", b"+Meta\n+Audio\n")
        self.write(self.mo2 / "profiles/Other/modlist.txt", b"-Meta\n-Audio\n")
        self.audio = self.root / "fixture.wav"
        with wave.open(str(self.audio), "wb") as wav:
            wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0" * 441)
        self.old = self.add(self.flat, "mikael", strict=False)
        self.new = self.add(self.staged, "sven")
        value = self.read_json(self.flat / "library.json")
        self.old = deepcopy(value["recordings"][0])
        value["custom"] = {"preserved": ["unknown", None]}
        self.json(self.flat / "library.json", value)
        self.install_snapshot()

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def json(self, path, value):
        self.write(path, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def add(self, root, performer, *, strict=True, lyrics=None, revision="fixture-v1"):
        identity = dict(performer_id=performer, region="whiterun", recipe_id="fixture/cittern",
                        model_id="fixture-model", mode="vocal" if lyrics is not None else "instrumental")
        extra = {}
        if strict:
            identity.update(recipe_revision=revision, instrument_family="plucked_string",
                            instrument_name="cittern",
                            arrangement="solo_lute_and_voice" if lyrics is not None else "solo_lute",
                            voice="male" if lyrics is not None else "none")
            identity["identity_key"] = runtime_identity_key(identity)
        row = Library(root).add_recording(
            self.audio, gender="male", composition_id=performer + ":fixture",
            source={"kind": "import", "path_or_request_id": "synthetic"},
            lyrics=lyrics, created_at="2026-10-20T00:00:00Z", **identity, **extra)
        if strict:
            value = self.read_json(root / "library.json")
            value["runtime_selection"] = {"version": 1, "contracts": [identity]}
            self.json(root / "library.json", value)
        return row

    def install_snapshot(self):
        for path in self.flat.iterdir():
            if path.is_file():
                target = self.audio_mod / AUDIO_PATH if path.suffix == ".wav" else self.meta / STORAGE_PATH
                self.write(target / path.name, path.read_bytes())

    def plan(self, **kwargs):
        args = dict(staged_library=self.staged, destination_snapshot=self.flat,
                    mo2_root=self.mo2, profile="Pilot", metadata_mod="Meta",
                    audio_mod="Audio", game_data=self.base)
        args.update(kwargs)
        return plan_library_publication(**args)

    def codes(self, result):
        return {row["code"] for row in result["blockers"]}

    def files(self):
        return {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                for path in self.root.rglob("*") if path.is_file()}

    def test_split_routes_are_concrete_manifest_last_and_read_only(self):
        before = self.files()
        with patch("subprocess.run", side_effect=AssertionError("No processes")), \
                patch("socket.create_connection", side_effect=AssertionError("No network")):
            result = self.plan()
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["snapshot_equivalence"]["matches"])
        self.assertEqual(len(result["snapshot_equivalence"]["files"]), 51)
        self.assertEqual([row["role"] for row in result["routes"]], ["audio", "manifest"])
        asset, manifest = result["routes"]
        self.assertEqual(Path(asset["physical_target"]), self.audio_mod / AUDIO_PATH / "hm_slot_02.wav")
        self.assertEqual(Path(manifest["physical_target"]), self.meta / MANIFEST_PATH)
        self.assertFalse(asset["before"]["exists"])
        self.assertEqual(asset["after_sha256"], hashlib.sha256(self.audio.read_bytes()).hexdigest())
        self.assertEqual(result["proposed_manifest"]["recordings"][0], self.old)
        self.assertEqual(result["proposed_manifest"]["custom"], {"preserved": ["unknown", None]})
        self.assertTrue(all(result[key] is False for key in
                            ("can_apply", "installed", "runtime_verified", "vfs_verified",
                             "writes_performed", "candidate_available")))
        self.assertEqual(before, self.files())
        self.assertEqual(result["review_token"], self.plan()["review_token"])

    def test_same_mod_and_unique_case_lookup_supported(self):
        result = self.plan(metadata_mod="meta", audio_mod="meta")
        self.assertEqual(result["blockers"], [])
        self.assertEqual(Path(result["routes"][0]["physical_target"]),
                         self.meta / AUDIO_PATH / "hm_slot_02.wav")

    def test_lyrics_route_uses_metadata_mod_and_remapped_slot(self):
        for path in self.staged.iterdir():
            path.unlink()
        self.add(self.staged, "sven", lyrics="A neutral fixture song.")
        result = self.plan()
        self.assertEqual(result["blockers"], [])
        lyrics = next(row for row in result["routes"] if row["role"] == "lyrics")
        self.assertEqual(Path(lyrics["physical_target"]),
                         self.meta / STORAGE_PATH / "hm_slot_02.lyrics.txt")
        self.assertEqual(lyrics["source"]["sha256"], lyrics["after_sha256"])

    def test_raw_manifest_formatting_mismatch_rejected(self):
        value = self.read_json(self.flat / "library.json")
        self.write(self.flat / "library.json", json.dumps(value, indent=4).encode())
        result = self.plan()
        self.assertIn("snapshot_mismatch", self.codes(result))
        self.assertIsNone(result["proposed_manifest"])
        self.assertEqual(result["routes"], [])

    def test_optional_absent_receipts_not_equal_synthetic_empty_receipts(self):
        self.json(self.flat / "receipts.json", {"version": 1, "performances": []})
        self.assertIn("snapshot_mismatch", self.codes(self.plan()))

    def test_history_and_orphans_match_exactly_and_reserve_slots(self):
        receipts = {"version": 1, "performances": [
            dict(id="fixture:receipt", slot=2, performer_id="mikael", composition_id="older",
                 save_id="save", world_id="world", at_hours=3, outcome="interrupted")]}
        self.json(self.flat / "receipts.json", receipts)
        self.json(self.flat / "trace.json", {"version": 1, "entries": []})
        self.write(self.flat / "hm_slot_03.wav", b"orphan")
        self.write(self.flat / "hm_slot_04.lyrics.txt", b"orphan lyrics")
        self.install_snapshot()
        result = self.plan()
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["proposed_manifest"]["recordings"][-1]["slot"], 5)
        self.assertEqual(len(result["preservation"]["orphans"]), 2)
        self.assertNotIn(RECEIPTS_PATH, [row["virtual_path"] for row in result["routes"]])
        self.assertNotIn(TRACE_PATH, [row["virtual_path"] for row in result["routes"]])

    def test_missing_orphan_in_flat_snapshot_rejected(self):
        self.write(self.audio_mod / AUDIO_PATH / "hm_slot_24.wav", b"orphan")
        self.assertIn("snapshot_mismatch", self.codes(self.plan()))

    def test_unmapped_flat_extra_rejected(self):
        self.write(self.flat / "notes.txt", b"unmapped evidence")
        self.assertIn("snapshot_extra_files", self.codes(self.plan()))

    def test_higher_manifest_winner_blocks_even_identical_bytes(self):
        self.write(self.mo2 / "overwrite" / MANIFEST_PATH,
                   (self.flat / "library.json").read_bytes())
        result = self.plan()
        self.assertTrue(result["snapshot_equivalence"]["matches"])
        self.assertIn("higher_priority_override", self.codes(result))
        route = result["routes"][-1]
        self.assertEqual(route["simulated_winner"]["layer"], "overwrite")

    def test_missing_or_disabled_destination_is_not_routed(self):
        self.assertIn("invalid_target_mod", self.codes(self.plan(audio_mod="Missing")))
        self.write(self.mo2 / "profiles/Pilot/modlist.txt", b"+Meta\n-Audio\n")
        self.assertIn("invalid_target_mod", self.codes(self.plan()))

    def test_roots_must_not_overlap_installation_or_each_other(self):
        for kwargs in ({"staged_library": self.flat},
                       {"destination_snapshot": self.meta},
                       {"game_data": self.mo2},
                       {"mo2_root": self.root}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, "overlap"):
                self.plan(**kwargs)

    def test_disabled_shared_profile_has_no_effect_and_no_blanket_gate(self):
        result = self.plan()
        other = next(row for row in result["shared_profiles"] if row["profile"] == "Other")
        self.assertFalse(any(row["effective_change"] for row in other["effects"]))
        self.assertTrue(other["affected_scope_complete"])
        self.assertEqual(result["blockers"], [])

    def test_effective_other_profile_changes_report_incomplete_validation(self):
        for modlist in (b"+Meta\n-Audio\n", b"-Meta\n+Audio\n", b"+Meta\n+Audio\n"):
            with self.subTest(modlist=modlist):
                self.write(self.mo2 / "profiles/Other/modlist.txt", modlist)
                result = self.plan()
                self.assertIn("affected_profile_validation_incomplete", self.codes(result))
                other = next(row for row in result["shared_profiles"] if row["profile"] == "Other")
                self.assertTrue(any(row["effective_change"] for row in other["effects"]))
                self.assertFalse(other["affected_scope_complete"])

    def test_fully_shadowed_other_profile_routes_reported_without_gate(self):
        shadow = self.mo2 / "mods/Shadow"
        self.write(shadow / MANIFEST_PATH, b"not our selected profile")
        self.write(shadow / AUDIO_PATH / "hm_slot_02.wav", b"foreign slot")
        self.write(self.mo2 / "profiles/Other/modlist.txt", b"+Shadow\n+Meta\n+Audio\n")
        result = self.plan()
        self.assertEqual(result["blockers"], [])
        other = next(row for row in result["shared_profiles"] if row["profile"] == "Other")
        self.assertTrue(all(row["higher_override"] for row in other["effects"]))
        self.assertFalse(any(row["effective_change"] for row in other["effects"]))

    def test_invalid_unrelated_profile_not_ignored(self):
        self.write(self.mo2 / "profiles/Other/modlist.txt", b"unexpected\n")
        self.assertIn("invalid_profile_scope", self.codes(self.plan()))
        self.write(self.mo2 / "profiles/Other/modlist.txt", b"+Missing\n")
        self.assertIn("invalid_profile_scope", self.codes(self.plan()))

    def test_foreign_modlist_markers_are_information_not_missing_mods(self):
        self.write(self.mo2 / "profiles/Other/modlist.txt",
                   b"-Meta\n-Audio\n*DLC: Dawnguard\n*Creation Club: Fish\n*Unmanaged: Example\n")
        result = self.plan()
        self.assertEqual(result["blockers"], [])
        self.assertEqual(len(next(row for row in result["shared_profiles"]
                                  if row["profile"] == "Other")["unmanaged_entries"]), 3)

    def test_existing_performer_contract_migration_remains_blocked(self):
        for path in self.staged.iterdir():
            path.unlink()
        self.add(self.staged, "mikael")
        self.assertIn("legacy_performer_contract_conflict", self.codes(self.plan()))

    def test_duplicate_only_does_not_route_format_only_manifest_rewrite(self):
        for path in self.flat.iterdir():
            path.unlink()
        for path in self.staged.iterdir():
            shutil.copyfile(path, self.flat / path.name)
        self.install_snapshot()
        result = self.plan()
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["no_changes"])
        self.assertEqual(result["routes"], [])

    def test_private_prerequisite_bytes_not_exposed_or_interpreted(self):
        secret = b"unique-private-configuration-sentinel"
        self.write(self.meta / "SKSE/Plugins/SkyrimNet/config/BardSinging.yaml", secret)
        self.write(self.mo2 / "plugins/hold_music_adapter/local.json", secret)
        result = self.plan()
        self.assertNotIn(secret.decode(), json.dumps(result))
        self.assertTrue(all(value is False for value in result["prerequisites"].values()))
        self.assertEqual(result["blockers"], [])

    def test_actual_baseline_and_controller_evidence_bound_to_token(self):
        before = self.plan()
        self.write(self.mo2 / "profiles/Pilot/hold-music-runtime/BardSinging.baseline.yaml",
                   b"private-baseline-sentinel")
        self.write(self.meta / "Scripts/HM_Controller.pex", b"synthetic-controller")
        after = self.plan()
        self.assertNotEqual(before["review_token"], after["review_token"])
        self.assertNotIn("private-baseline-sentinel", json.dumps(after))
        state = after["prerequisite_evidence"]["selected_profile_state"]
        self.assertTrue(state["hold-music-runtime/BardSinging.baseline.yaml"]["exists"])
        self.assertFalse(after["prerequisites"]["performer_ownership_verified"])

    def test_unsafe_mod_names_rejected_before_routes(self):
        for name in ("../outside", "Audio/../Meta", "C:\\outside", "CON", "Audio."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.plan(audio_mod=name)

    def test_hardlinked_snapshot_asset_rejected(self):
        path = self.flat / self.old["file"]
        path.unlink()
        os.link(self.audio, path)
        with self.assertRaisesRegex(ValueError, "Hard-linked|unaliased"):
            self.plan()

    def test_source_directory_symlink_rejected(self):
        link = self.root / "source-link"
        try:
            link.symlink_to(self.staged, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks unavailable on this host")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.plan(staged_library=link)

    def test_omitted_base_coverage_explicit(self):
        result = self.plan(game_data=None)
        self.assertTrue(any("Base game Data was omitted" in text for text in result["limitations"]))

    def test_installed_drift_after_inspection_rejected(self):
        def changed(*args, **kwargs):
            result = plan_library_merge(*args, **kwargs)
            self.write(self.meta / MANIFEST_PATH, b"changed during review")
            return result
        with patch("hold_music.library_publication.plan_library_merge", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.plan()

    def test_source_drift_before_final_merge_rejected(self):
        calls = 0
        def changed(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                value = self.read_json(self.staged / "library.json")
                value["new_extra"] = True
                self.json(self.staged / "library.json", value)
            return plan_library_merge(*args, **kwargs)
        with patch("hold_music.library_publication.plan_library_merge", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.plan()

    def test_profile_added_during_planning_rejected(self):
        from hold_music.library_publication import _simulate
        changed = False
        def mutate(*args):
            nonlocal changed
            result = _simulate(*args)
            if not changed:
                changed = True
                self.write(self.mo2 / "profiles/New/modlist.txt", b"+Meta\n+Audio\n")
            return result
        with patch("hold_music.library_publication._simulate", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.plan()

    def test_target_shadow_created_during_review_rejected(self):
        from hold_music.library_publication import _simulate
        changed = False
        def mutate(*args):
            nonlocal changed
            result = _simulate(*args)
            if not changed:
                changed = True
                self.write(self.mo2 / "overwrite" / AUDIO_PATH / "hm_slot_02.wav", b"new shadow")
            return result
        with patch("hold_music.library_publication._simulate", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.plan()


if __name__ == "__main__":
    unittest.main()
