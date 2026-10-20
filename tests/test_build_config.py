"""Portable build planning rejects unsafe targets before making any writes."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "game_package/tools/build_config.py"
SPEC = importlib.util.spec_from_file_location("holdmusic_build_config", MODULE)
build_config = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_config
SPEC.loader.exec_module(build_config)


class BuildConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "checkout/game_package"
        for folder in ("src", "imports", "data", "tools/PluginBuilder"):
            (self.source / folder).mkdir(parents=True)
        for relative in ("src/controller.psc", "data/slots.json",
                         "imports/native.psc", "tools/PluginBuilder/Program.cs",
                         "tools/PluginBuilder/PluginBuilder.csproj",
                         "tools/PluginBuilder/NuGet.Config"):
            (self.source / relative).write_text("fixture", encoding="utf-8")
        self.mo2 = self.root / "mo2"
        (self.mo2 / "profiles/test profile").mkdir(parents=True)
        (self.mo2 / "profiles/test profile/modlist.txt").write_text("+fixture\n")
        (self.mo2 / "mods").mkdir()
        inputs = self.root / "inputs"
        inputs.mkdir()
        for name in ("caprica.exe", "flags.flg", "champollion.exe", "dotnet.exe"):
            (inputs / name).write_text(name)
        for name in ("vanilla-imports", "vanilla-pex", "cache/pkg/1.0"):
            (inputs / name).mkdir(parents=True)
        self.assets = inputs / "project.assets.json"
        self.assets.write_text(json.dumps({
            "packageFolders": {str(inputs / "cache"): {}},
            "libraries": {"Pkg/1.0": {"type": "package", "path": "pkg/1.0"}}
        }))
        self.config = build_config.BuildConfig(
            workspace=self.root / "checkout/local/fresh-build",
            mo2_root=self.mo2, profile="test profile",
            compiler=inputs / "caprica.exe", flags=inputs / "flags.flg",
            decompiler=inputs / "champollion.exe",
            vanilla_imports=inputs / "vanilla-imports",
            vanilla_pex=inputs / "vanilla-pex",
            dependency_assets=self.assets, dotnet=inputs / "dotnet.exe",
        )

    def test_plan_hashes_inputs_and_never_creates_workspace(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        plan = self.config.plan(self.source)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.assertFalse(self.config.workspace.exists())
        self.assertEqual(plan["stack"]["profile"], "test profile")
        self.assertEqual(plan["source_files"]["src/controller.psc"],
                         build_config.sha256(self.source / "src/controller.psc"))
        self.assertFalse(plan["installs_game_files"])
        self.assertFalse(plan["downloads_dependencies"])
        self.assertFalse(plan["runtime_verified"])

    def test_rejects_nonempty_workspace_preserving_contents(self):
        self.config.workspace.mkdir(parents=True)
        saved = self.config.workspace / "receipt.json"
        saved.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "absent or empty"):
            self.config.plan(self.source)
        self.assertEqual(saved.read_text(), "preserve")

    def test_rejects_installed_and_source_targets(self):
        for workspace in (self.mo2 / "new", self.source / "src/new",
                          self.source / "tools/new", self.config.vanilla_pex / "new"):
            with self.subTest(workspace=workspace):
                with self.assertRaisesRegex(ValueError, "protected input"):
                    replace(self.config, workspace=workspace).plan(self.source)
                self.assertFalse(workspace.exists())

    def test_missing_offline_dependency_is_an_error(self):
        (self.root / "inputs/cache/pkg/1.0").rmdir()
        with self.assertRaisesRegex(ValueError, "not cached"):
            self.config.plan(self.source)
        self.assertFalse(self.config.workspace.exists())

    def test_searches_all_declared_caches(self):
        data = json.loads(self.assets.read_text())
        data["packageFolders"] = {str(self.root / "absent"): {},
                                  **data["packageFolders"]}
        self.assets.write_text(json.dumps(data))
        self.assertEqual(len(self.config.plan(self.source)["offline_packages"]), 1)

    def test_rejects_rooted_drive_relative_and_traversing_package_paths(self):
        data = json.loads(self.assets.read_text())
        for path in ("/pkg/1.0", "\\pkg\\1.0", "D:pkg", "D:\\pkg",
                     "../pkg", "..\\pkg"):
            with self.subTest(path=path):
                data["libraries"]["Pkg/1.0"]["path"] = path
                self.assets.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "Unsafe package cache path"):
                    self.config.plan(self.source)
                self.assertFalse(self.config.workspace.exists())

    def test_rejects_profile_traversal_on_any_host(self):
        for profile in ("..", "../wrong", "..\\wrong", "", "one/two"):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError, "Profile"):
                    replace(self.config, profile=profile).plan(self.source)

    def test_missing_tool_is_reported_before_any_write(self):
        with self.assertRaisesRegex(ValueError, "Missing compiler"):
            replace(self.config, compiler=self.root / "missing.exe").plan(self.source)
        self.assertFalse(self.config.workspace.exists())

    def test_argument_parser_defaults_to_read_only(self):
        config, build = build_config.parse_args([
            "--workspace", str(self.config.workspace),
            "--mo2-root", str(self.mo2), "--profile", "test profile",
            "--compiler", str(self.config.compiler),
            "--flags", str(self.config.flags),
            "--decompiler", str(self.config.decompiler),
            "--vanilla-imports", str(self.config.vanilla_imports),
            "--vanilla-pex", str(self.config.vanilla_pex),
            "--dependency-assets", str(self.assets),
            "--dotnet", str(self.config.dotnet),
        ])
        self.assertFalse(build)
        self.assertEqual(config.workspace, self.config.workspace.resolve())
        self.assertFalse(config.workspace.exists())


if __name__ == "__main__":
    unittest.main()
