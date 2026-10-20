"""Candidate promotion plans inspect fixture trees without changing their contents."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hold_music.promotion import DEFAULT_DATA_MOD, DEFAULT_MOD, REQUIRED_FILES, SETTINGS, STORAGE, plan_promotion
from hold_music.recording_identity import CONTRACT_FIELDS
from hold_music.runtime_contract import project_runtime_contract, runtime_identity_key


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, (dict, list)) else value, encoding="utf-8")


def snapshot(root):
    return {str(path.relative_to(root)): (
        path.is_dir(), path.stat().st_mtime_ns,
        None if path.is_dir() else sha(path)) for path in root.rglob("*")}


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "checkout/game_package"
        self.build = self.root / "candidate/build"
        self.package = self.build / "package"
        self.mo2 = self.root / "mo2"
        self.profile = self.mo2 / "profiles/pilot"
        self.target = self.mo2 / "mods" / DEFAULT_MOD
        self.target.mkdir(parents=True)
        write(self.profile / "modlist.txt", "+" + DEFAULT_MOD + "\n")
        write(self.profile / "plugins.txt", "*HoldMusic.esp\n")
        write(self.profile / "saves/a.ess", "existing save")
        write(self.profile / "saves/a.skse", "existing co-save")
        write(self.profile / "saves/b.ess", "unpaired save must also survive")
        self.hashes, source_hashes = {}, {}
        for relative in sorted(REQUIRED_FILES):
            write(self.package / relative, "candidate fixture: " + relative)
            self.hashes[relative] = sha(self.package / relative)
            if relative.endswith(".psc"):
                write(self.source / "src" / relative, "candidate fixture: " + relative)
                source_hashes["src/" + relative] = sha(self.source / "src" / relative)
        inputs = {"modlist": {"path": str(self.profile / "modlist.txt"),
                              "sha256": sha(self.profile / "modlist.txt")}}
        for label, filename in (("plugin_project", "PluginBuilder.csproj"),
                                ("plugin_source", "Program.cs"), ("nuget_config", "NuGet.Config")):
            path = self.source / "tools/PluginBuilder" / filename
            write(path, "source " + filename)
            inputs[label] = {"path": str(path), "sha256": sha(path)}
        self.receipt = {
            "schema_version": 1, "status": "built_offline", "installed": False, "runtime_verified": False,
            "package_hashes": self.hashes,
            "plan": {"mode": "offline_build_plan", "source_files": source_hashes, "inputs": inputs,
                     "stack": {"mo2_root": str(self.mo2), "profile": "pilot"}},
            "dependencies": {},
        }
        self.save_receipt()
        write(self.target / "Scripts/HM_Controller.pex", "older compiled controller")
        write(self.target / SETTINGS, "user-customized settings")
        write(self.target / (STORAGE + "/library.json"), {"version": 1, "slots": 24, "recordings": []})
        write(self.target / (STORAGE + "/receipts.json"), {"version": 1, "performances": [{"private": "history"}]})
        write(self.target / (STORAGE + "/trace.json"), {"version": 1, "entries": [{"private": "trace"}]})
        write(self.target / "Sound/fx/holdmusic/hm_slot_03.wav", "existing audio")
        write(self.target / (STORAGE + "/hm_slot_03.lyrics.txt"), "existing lyrics")
        write(self.target / "unrelated.txt", "keep me")
        write(self.mo2 / "overwrite" / (STORAGE + "/trace.json"), "shadow trace")
        write(self.mo2 / "mods" / DEFAULT_DATA_MOD / (STORAGE + "/receipts.json"), "shadow receipt")

    def save_receipt(self):
        write(self.build / "package-hashes.json", self.hashes)
        write(self.build / "build-receipt.json", self.receipt)

    def plan(self, **changes):
        args = dict(build_dir=self.build, source_root=self.source, mo2_root=self.mo2, profile="pilot")
        args.update(changes)
        return plan_promotion(**args)

    def assert_read_only_failure(self, **changes):
        before = snapshot(self.root)
        with self.assertRaises((ValueError, OSError)):
            self.plan(**changes)
        self.assertEqual(snapshot(self.root), before)

    def add_payload(self, relative, value):
        write(self.package / relative, value)
        self.hashes[relative] = sha(self.package / relative)
        self.save_receipt()

    def recording(self, **extra):
        return dict(slot=1, file="hm_slot_01.wav", performer_id="sven", region="whiterun",
                    mode="instrumental", gender="male", duration_seconds=1, composition_id="existing",
                    recipe_id="whiterun/instrumental", model_id="old-model", lyrics_sha256=None,
                    created_at="2026-10-20T00:00:00Z", playable=True,
                    source={"kind": "import", "path_or_request_id": "fixture.wav"}, **extra)

    def projected_library(self):
        row = self.recording(recipe_revision="fixture-revision", instrument_family="plucked_string",
                             instrument_name="cittern", arrangement="solo_lute", voice="none")
        contract = project_runtime_contract(dict(
            action="play_recording", performer_id=row["performer_id"],
            request=dict(tradition=row["region"], **{key: row[key] for key in CONTRACT_FIELDS})))
        row["identity_key"] = runtime_identity_key(row)
        return {"version": 1, "slots": 24, "recordings": [row],
                "runtime_selection": {"version": 1, "contracts": [contract]}}

    def test_candidate_capability_does_not_claim_installed_runtime_support(self):
        write(self.target / (STORAGE + "/library.json"), self.projected_library())
        before = snapshot(self.root)
        with patch("hold_music.promotion.validate_capability",
                   return_value={"fixture": "verified offline candidate"}):
            report = self.plan()
        self.assertEqual(report["blockers"], [])
        self.assertTrue(report["candidate_runtime_selection_verified"])
        self.assertFalse(report["runtime_identity_supported"])
        self.assertFalse(report["runtime_verified"])
        self.assertFalse(report["installed"])
        self.assertEqual(snapshot(self.root), before)

    def test_candidate_capability_does_not_clear_manifest_or_merge_blockers(self):
        data = self.projected_library()
        data["recordings"][0]["instrument_name"] = "Cittern"
        write(self.target / (STORAGE + "/library.json"), data)
        inspection = self.root / "inspection"
        write(inspection / "library.json", self.projected_library())
        before = snapshot(self.root)
        with patch("hold_music.promotion.validate_capability", return_value={"fixture": True}):
            report = self.plan(library=inspection)
        codes = {row["code"] for row in report["blockers"]}
        self.assertIn("invalid_runtime_selection", codes)
        self.assertIn("library_promotion_not_supported", codes)
        self.assertNotIn("versioned_library_unsupported", codes)
        self.assertEqual(snapshot(self.root), before)

    def test_malformed_capability_cannot_be_treated_as_legacy(self):
        before = snapshot(self.root)
        with patch("hold_music.promotion.validate_capability",
                   side_effect=ValueError("Stale capability evidence")):
            with self.assertRaisesRegex(ValueError, "Stale capability"):
                self.plan()
        self.assertEqual(snapshot(self.root), before)

    def test_explicit_contract_requires_capability_even_without_projected_rows(self):
        for recordings in ([self.recording()], []):
            with self.subTest(recordings=recordings):
                data = self.projected_library()
                data["recordings"] = recordings
                write(self.target / (STORAGE + "/library.json"), data)
                before = snapshot(self.root)
                report = self.plan()
                codes = {row["code"] for row in report["blockers"]}
                self.assertIn("versioned_library_unsupported", codes)
                self.assertNotIn("invalid_runtime_selection", codes)
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(snapshot(self.root), before)

    def test_deterministic_plan_preserves_all_runtime_state_and_paths(self):
        before = snapshot(self.root)
        first, second = self.plan(), self.plan()
        self.assertEqual(first, second)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(first["status"], "review_only")
        self.assertFalse(first["installed"])
        self.assertFalse(first["runtime_verified"])
        self.assertFalse(first["writes_performed"])
        self.assertFalse(first["runtime_identity_supported"])
        actions = {row["relative_path"]: row["action"] for row in first["files"]}
        self.assertEqual(actions["Scripts/HM_Controller.pex"], "replace_static")
        self.assertEqual(actions["HoldMusic.esp"], "add_static")
        self.assertEqual(actions[SETTINGS], "preserve_user_settings")
        preserved = {row["path"] for row in first["preserved"]}
        for path in (self.target / "unrelated.txt", self.target / "Sound/fx/holdmusic/hm_slot_03.wav",
                     self.target / (STORAGE + "/receipts.json"), self.target / (STORAGE + "/trace.json"),
                     self.target / (STORAGE + "/hm_slot_03.lyrics.txt"), self.target / SETTINGS,
                     self.profile / "modlist.txt", self.profile / "plugins.txt",
                     self.profile / "saves/a.ess", self.profile / "saves/a.skse",
                     self.profile / "saves/b.ess"):
            self.assertIn(str(path), preserved)
        self.assertIsNone(first["source_commit"])

    def test_unchanged_static_files_are_identified(self):
        write(self.target / "HoldMusic.esp", (self.package / "HoldMusic.esp").read_text())
        row = next(row for row in self.plan()["files"] if row["relative_path"] == "HoldMusic.esp")
        self.assertEqual(row["action"], "unchanged")

    def test_target_change_invalidates_prior_snapshot(self):
        first = self.plan()
        write(self.target / (STORAGE + "/trace.json"), "new runtime history")
        second = self.plan()
        self.assertNotEqual(first["snapshot_sha256"], second["snapshot_sha256"])

    def test_wrong_target_stack_or_changed_modlist_are_blockers(self):
        self.receipt["plan"]["stack"]["profile"] = "another profile"
        self.save_receipt()
        write(self.profile / "modlist.txt", "changed but preserved")
        before = snapshot(self.root)
        codes = {row["code"] for row in self.plan()["blockers"]}
        self.assertIn("build_stack_mismatch", codes)
        self.assertIn("build_modlist_changed", codes)
        self.assertEqual(snapshot(self.root), before)

    def test_tampered_package_and_receipt_or_extra_payload_are_rejected(self):
        for change in ("hash", "receipt", "extra", "missing"):
            with self.subTest(change=change):
                original = (self.package / "HoldMusic.esp").read_bytes()
                saved = deepcopy(self.receipt)
                if change == "hash":
                    write(self.package / "HoldMusic.esp", "tampered")
                elif change == "receipt":
                    self.receipt["status"] = "staged_only"
                    self.save_receipt()
                elif change == "extra":
                    write(self.package / "unexpected.txt", "not inventoried")
                else:
                    (self.build / "build-receipt.json").unlink()
                self.assert_read_only_failure()
                (self.package / "HoldMusic.esp").write_bytes(original)
                (self.package / "unexpected.txt").unlink(missing_ok=True)
                self.receipt = saved
                self.save_receipt()

    def test_stale_source_and_plugin_builder_inputs_are_rejected(self):
        for relative in ("src/Scripts/Source/HM_Library.psc", "tools/PluginBuilder/Program.cs"):
            path = self.source / relative
            old = path.read_bytes()
            with self.subTest(relative=relative):
                write(path, "changed after build")
                self.assert_read_only_failure()
                path.write_bytes(old)

    def test_added_builder_consumed_sources_invalidate_receipt(self):
        for relative in ("src/Scripts/Source/HM_NewController.psc",
                         "data/new-forms.json", "imports/NewDependency.psc"):
            with self.subTest(relative=relative):
                path = self.source / relative
                write(path, "added after candidate build")
                before = snapshot(self.root)
                with self.assertRaisesRegex(ValueError, "Actual source inventory"):
                    self.plan()
                self.assertEqual(snapshot(self.root), before)
                path.unlink()

    def test_removed_builder_consumed_source_invalidates_receipt(self):
        path = self.source / "src/Scripts/Source/HM_Controller.psc"
        path.unlink()
        before = snapshot(self.root)
        with self.assertRaisesRegex(ValueError, "Actual source inventory"):
            self.plan()
        self.assertEqual(snapshot(self.root), before)

    def test_missing_source_provenance_is_rejected(self):
        self.receipt["plan"]["source_files"] = {"src/other.psc": "0" * 64}
        self.save_receipt()
        self.assert_read_only_failure()

    def test_malformed_build_inputs_fail_without_reading_receipt_selected_paths(self):
        original = deepcopy(self.receipt["plan"]["inputs"])
        for invalid in (None, [], {"plugin_project": None}):
            with self.subTest(inputs=invalid):
                self.receipt["plan"]["inputs"] = invalid
                self.save_receipt()
                self.assert_read_only_failure()
        self.receipt["plan"]["inputs"] = original
        self.receipt["plan"]["inputs"]["plugin_source"]["path"] = str(self.root / "do-not-open")
        self.save_receipt()
        self.assertEqual(self.plan()["status"], "review_only")
        self.assertFalse((self.root / "do-not-open").exists())

    def test_traversing_and_absolute_inventory_paths_are_rejected(self):
        original = deepcopy(self.hashes)
        for bad in ("../escape", "..\\escape", "C:escape", "C:/escape", "/escape",
                    "Scripts/file:stream", "Scripts/CON", "Scripts/trailing."):
            with self.subTest(path=bad):
                self.hashes = {**original, bad: "0" * 64}
                self.receipt["package_hashes"] = self.hashes
                self.save_receipt()
                self.assert_read_only_failure()
        self.hashes = original
        self.receipt["package_hashes"] = self.hashes
        self.save_receipt()

    def test_case_duplicate_inventory_and_duplicate_json_keys_are_rejected(self):
        self.hashes["holdmusic.esp"] = self.hashes["HoldMusic.esp"]
        self.save_receipt()
        self.assert_read_only_failure()
        (self.build / "package-hashes.json").write_text('{"x":"a","x":"b"}')
        self.assert_read_only_failure()

    def test_profile_traversal_and_source_or_build_overlap_are_rejected(self):
        for value in ("..", "../pilot", "..\\pilot", "C:pilot", "pilot "):
            with self.subTest(profile=value):
                self.assert_read_only_failure(profile=value)
        self.assert_read_only_failure(build_dir=self.mo2)
        self.assert_read_only_failure(source_root=self.mo2 / "mods")

    def test_symlink_input_is_rejected_before_reading_its_contents(self):
        alias = self.root / "source-alias"
        try:
            alias.symlink_to(self.source, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable for this test account")
        self.assert_read_only_failure(source_root=alias)

    def test_nested_candidate_symlink_is_rejected(self):
        alias = self.package / "foreign"
        try:
            alias.symlink_to(self.source, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable for this test account")
        self.assert_read_only_failure()

    def test_versioned_metadata_blocks_without_relabeling_existing_recordings(self):
        versioned = self.recording(recipe_revision="r1", instrument_family="plucked_string",
                                   instrument_name="cittern", arrangement="solo_lute", voice="none")
        write(self.target / (STORAGE + "/library.json"),
              {"version": 1, "slots": 24, "recordings": [self.recording(), versioned]})
        before = snapshot(self.root)
        codes = {row["code"] for row in self.plan()["blockers"]}
        self.assertIn("versioned_library_unsupported", codes)
        self.assertEqual(snapshot(self.root), before)

    def test_partial_identity_and_malformed_library_are_explicit_blockers(self):
        path = self.target / (STORAGE + "/library.json")
        write(path, {"version": 1, "slots": 24, "recordings": [self.recording(recipe_revision="r1")]})
        codes = {row["code"] for row in self.plan()["blockers"]}
        self.assertIn("malformed_library_metadata", codes)
        self.assertIn("versioned_library_unsupported", codes)
        path.write_text("{invalid")
        self.assertIn("malformed_library_metadata", {row["code"] for row in self.plan()["blockers"]})

    def test_legacy_unknown_identity_is_preserved_and_not_a_versioned_capability(self):
        write(self.target / (STORAGE + "/library.json"),
              {"version": 1, "slots": 24, "recordings": [self.recording()]})
        before = snapshot(self.root)
        result = self.plan()
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["runtime_identity_supported"])
        self.assertEqual(snapshot(self.root), before)

    def test_runtime_payload_and_unknown_candidate_files_cannot_be_promoted(self):
        self.add_payload(STORAGE + "/trace.json", {"version": 1, "entries": []})
        self.add_payload("Sound/fx/holdmusic/hm_slot_01.wav", "candidate audio")
        self.add_payload("Scripts/unreviewed.pex", "new script")
        result = self.plan()
        codes = {row["code"] for row in result["blockers"]}
        self.assertIn("runtime_payload_not_supported", codes)
        self.assertIn("unsupported_candidate_file", codes)
        for row in result["files"]:
            if row["relative_path"].endswith(("trace.json", ".wav")):
                self.assertEqual(row["action"], "preserve_runtime")

    def test_candidate_versioned_library_has_an_explicit_runtime_blocker(self):
        self.add_payload(STORAGE + "/library.json", {
            "version": 1, "slots": 24, "recordings": [self.recording(
                recipe_revision="r1", instrument_family="plucked_string",
                instrument_name="cittern", arrangement="solo_lute", voice="none")]})
        codes = {row["code"] for row in self.plan()["blockers"]}
        self.assertIn("runtime_payload_not_supported", codes)
        self.assertIn("versioned_library_unsupported", codes)

    def test_inspection_library_is_never_merged(self):
        library = self.root / "prepared"
        write(library / "library.json", {"version": 1, "slots": 24, "recordings": []})
        before = snapshot(self.root)
        result = self.plan(library=library)
        self.assertIn("library_promotion_not_supported", {row["code"] for row in result["blockers"]})
        self.assertEqual(snapshot(self.root), before)
        self.assert_read_only_failure(library=self.target)

    def test_possible_overrides_are_reported_without_claiming_a_vfs_winner(self):
        path = self.mo2 / "overwrite/Scripts/HM_Controller.pex"
        write(path, "other winner may shadow the package")
        before = snapshot(self.root)
        result = self.plan()
        self.assertIn("possible_static_override", {row["code"] for row in result["blockers"]})
        self.assertFalse(result["vfs_winners_verified"])
        self.assertEqual(snapshot(self.root), before)

    def test_cli_has_no_apply_option_and_writes_no_bytecode_or_report(self):
        script = Path(__file__).resolve().parents[1] / "tools/plan_game_promotion.py"
        args = [sys.executable, "-B", str(script), "--build-dir", str(self.build),
                "--source-root", str(self.source), "--mo2-root", str(self.mo2), "--profile", "pilot"]
        before = snapshot(self.root)
        run = subprocess.run(args, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["operation"], "plan_game_promotion")
        self.assertEqual(snapshot(self.root), before)
        self.assertNotEqual(subprocess.run([*args, "--apply"], capture_output=True).returncode, 0)
        self.assertEqual(snapshot(self.root), before)


if __name__ == "__main__":
    unittest.main()
