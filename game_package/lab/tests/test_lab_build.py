"""Read-only planning and isolation tests for the separate LAB package builder."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/build_lab.py"
SPEC = importlib.util.spec_from_file_location("hold_music_lab_build", MODULE_PATH)
lab = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lab
SPEC.loader.exec_module(lab)


class LabBuildPlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source/game_package"
        self.production = self.root / "candidate/build"
        self.installed = self.root / "mo2"
        self.installed.mkdir()
        self.tool_dir = self.root / "toolchain"
        for relative in (
            "lab/src/Scripts/Source/HM_LabHarness.psc", "lab/builder/Program.cs",
            "lab/builder/HM_LabPluginBuilder.csproj", "lab/builder/NuGet.Config",
            "lab/tests/test_lab_plugin.py", "src/Scripts/Source/HM_Controller.psc",
            "src/Scripts/Source/HM_Config.psc", "src/Scripts/Source/HM_Library.psc",
            "imports/BardSongsScript.psc", "data/forms.json",
        ):
            self.write(self.source / relative, "fixture: " + relative)
        for relative in (
            "package/HoldMusic.esp", "package/Scripts/HM_Controller.pex",
            "package/Scripts/HM_Config.pex", "package/Scripts/HM_Library.pex",
            "imports/Quest.psc",
        ):
            self.write(self.production / relative, "fixture: " + relative)
        self.write(self.production / "build-plan.json",
                   json.dumps({"stack": {"mo2_root": str(self.installed)}}))
        for name in ("Caprica.exe", "flags.flg", "Champollion.exe", "dotnet.exe"):
            self.write(self.tool_dir / name, "tool fixture: " + name)
        self.cache = self.root / "cache"
        self.package_relative = "mutagen.bethesda.skyrim/0.51.5"
        self.write(self.cache / self.package_relative / "lib/fixture.dll", "cached assembly fixture")
        self.assets = self.root / "assets/project.assets.json"
        self.assets_data = {
            "packageFolders": {str(self.cache): {}},
            "libraries": {"Mutagen.Bethesda.Skyrim/0.51.5": {
                "type": "package", "path": self.package_relative,
            }},
        }
        self.save_assets()
        self.config = lab.LabBuildConfig(
            workspace=self.root / "new-workspace",
            production_build=self.production,
            compiler=self.tool_dir / "Caprica.exe",
            flags=self.tool_dir / "flags.flg",
            decompiler=self.tool_dir / "Champollion.exe",
            dotnet=self.tool_dir / "dotnet.exe",
            dependency_assets=self.assets,
        )

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def save_assets(self):
        self.write(self.assets, json.dumps(self.assets_data))

    def test_plan_is_read_only_and_captures_actual_input_hashes(self):
        before = lab.tree_hashes(self.root)
        with mock.patch.object(lab.subprocess, "run", side_effect=AssertionError("No tools in plan")):
            plan = self.config.plan(self.source)
        self.assertFalse(self.config.workspace.exists())
        self.assertEqual(lab.tree_hashes(self.root), before)
        self.assertEqual(plan["compile_targets"], ["HM_LabHarness.psc"])
        self.assertTrue(plan["offline_only"])
        self.assertFalse(plan["runtime_verified"])
        self.assertFalse(plan["installs_game_files"])
        self.assertFalse(plan["launches_game"])
        self.assertFalse(plan["downloads_dependencies"])
        self.assertEqual(plan["protected_mo2_root"], str(self.installed))
        self.assertEqual(plan["inputs"]["harness"]["sha256"],
                         lab.sha256(self.source / "lab/src/Scripts/Source/HM_LabHarness.psc"))
        self.assertEqual(set(plan["import_directories"]),
                         {"candidate_imports", "production_sources", "package_imports"})
        self.assertIn("lib/fixture.dll", plan["offline_packages"][0]["files"])

    def test_empty_workspace_is_allowed_but_no_files_are_created(self):
        self.config.workspace.mkdir()
        self.config.plan(self.source)
        self.assertEqual(list(self.config.workspace.iterdir()), [])

    def test_nonempty_or_file_workspace_is_rejected(self):
        self.write(self.config.workspace / "keep.txt", "existing work")
        with self.assertRaisesRegex(ValueError, "absent or empty"):
            self.config.plan(self.source)
        with self.assertRaisesRegex(ValueError, "absent or empty"):
            replace(self.config, workspace=self.config.workspace / "keep.txt").plan(self.source)
        self.assertEqual((self.config.workspace / "keep.txt").read_text(), "existing work")

    def test_protected_inputs_installed_paths_and_cache_cannot_contain_workspace(self):
        targets = [
            self.production / "new", self.installed / "mods/new",
            self.source / "src/new", self.source / "imports/new",
            self.source / "data/new", self.source / "tools/new",
            self.source / "lab/src/new", self.source / "lab/builder/new",
            self.source / "lab/tools/new", self.source / "lab/tests/new",
            self.assets.parent / "new", self.cache / self.package_relative / "new",
            self.tool_dir / "new",
        ]
        for target in targets:
            with self.subTest(workspace=target):
                with self.assertRaisesRegex(ValueError, "overlaps"):
                    replace(self.config, workspace=target).plan(self.source)
                self.assertFalse(target.exists())

    def test_missing_harness_is_a_plan_failure(self):
        (self.source / "lab/src/Scripts/Source/HM_LabHarness.psc").unlink()
        with self.assertRaisesRegex(ValueError, "Missing harness"):
            self.config.plan(self.source)
        self.assertFalse(self.config.workspace.exists())

    def test_missing_candidate_pex_is_a_plan_failure(self):
        (self.production / "package/Scripts/HM_Controller.pex").unlink()
        with self.assertRaisesRegex(ValueError, "Missing production_controller"):
            self.config.plan(self.source)

    def test_plan_requires_recorded_installed_root(self):
        self.write(self.production / "build-plan.json", "{}")
        with self.assertRaisesRegex(ValueError, "absolute stack.mo2_root"):
            self.config.plan(self.source)

    def test_plan_requires_exact_mutagen_version_and_existing_cache(self):
        entry = self.assets_data["libraries"].pop("Mutagen.Bethesda.Skyrim/0.51.5")
        self.assets_data["libraries"]["Mutagen.Bethesda.Skyrim/0.51.4"] = entry
        self.save_assets()
        with self.assertRaisesRegex(ValueError, "0.51.5"):
            self.config.plan(self.source)
        self.assets_data["libraries"] = {"Mutagen.Bethesda.Skyrim/0.51.5": {
            "type": "package", "path": "missing/0.51.5",
        }}
        self.save_assets()
        with self.assertRaisesRegex(ValueError, "not cached"):
            self.config.plan(self.source)

    def test_unsafe_dependency_paths_are_rejected_before_any_write(self):
        for value in ("../escape", r"..\escape", r"C:\escape", "/escape", "", "."):
            with self.subTest(path=value):
                self.assets_data["libraries"]["Mutagen.Bethesda.Skyrim/0.51.5"]["path"] = value
                self.save_assets()
                with self.assertRaisesRegex(ValueError, "Unsafe package cache path"):
                    self.config.plan(self.source)
                self.assertFalse(self.config.workspace.exists())

    def test_input_changes_after_planning_are_detected(self):
        plan = self.config.plan(self.source)
        lab.verify_inputs_unchanged(plan)
        self.write(self.source / "src/Scripts/Source/HM_Controller.psc", "changed after plan")
        with self.assertRaisesRegex(ValueError, "Import directory changed"):
            lab.verify_inputs_unchanged(plan)

    def test_snapshot_rejects_a_changed_input(self):
        source = self.source / "lab/src/Scripts/Source/HM_LabHarness.psc"
        digest = lab.sha256(source)
        self.write(source, "changed after plan")
        destination = self.root / "snapshot/HM_LabHarness.psc"
        with self.assertRaisesRegex(ValueError, "Input changed after planning"):
            lab.copy_checked(source, destination, digest)
        self.assertFalse(destination.exists())

    def test_cli_defaults_to_plan_and_requires_explicit_tool_paths(self):
        arguments = []
        for name, value in vars(self.config).items():
            arguments.extend(["--" + name.replace("_", "-"), str(value)])
        config, do_build = lab.parse_args(arguments)
        self.assertEqual(config, self.config)
        self.assertFalse(do_build)
        self.assertTrue(lab.parse_args(arguments + ["--build"])[1])

    def test_complete_assembly_does_not_mask_source_decompilation_errors(self):
        assembly = self.root / "disassembly/HM_LabHarness.pas"
        self.write(assembly, ".objectTable\n.object HM_LabHarness Quest\n.endObject\n.endObjectTable\n")
        result = lab.inspect_disassembly(
            assembly, "1 files failed to decompile.\nERROR: Orphaned nodes in TryAutorun\n",
            self.root / "decompiled-source/HM_LabHarness.psc")
        self.assertTrue(result["assembly_complete"])
        self.assertFalse(result["source_decompilation_verified"])
        self.assertEqual(len(result["source_decompilation_diagnostics"]), 2)

    def test_truncated_assembly_is_rejected(self):
        assembly = self.root / "disassembly/HM_LabHarness.pas"
        self.write(assembly, ".objectTable\n.object HM_LabHarness Quest\n")
        with self.assertRaisesRegex(RuntimeError, "incomplete object table"):
            lab.inspect_disassembly(assembly, "", self.root / "HM_LabHarness.psc")

    def test_source_decompilation_requires_an_output_file_and_clean_diagnostics(self):
        assembly = self.root / "disassembly/HM_LabHarness.pas"
        source = self.root / "decompiled-source/HM_LabHarness.psc"
        self.write(assembly, ".objectTable\n.object HM_LabHarness Quest\n.endObject\n.endObjectTable\n")
        self.assertFalse(lab.inspect_disassembly(
            assembly, "0 files failed to decompile.\n", source)["source_decompilation_verified"])
        self.write(source, "Scriptname HM_LabHarness extends Quest\n")
        self.assertTrue(lab.inspect_disassembly(
            assembly, "0 files failed to decompile.\n", source)["source_decompilation_verified"])


if __name__ == "__main__":
    unittest.main()
