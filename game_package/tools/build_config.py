"""Explicit, read-only validation for a portable offline package build."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PureWindowsPath
import shutil


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class BuildConfig:
    workspace: Path
    mo2_root: Path
    profile: str
    compiler: Path
    flags: Path
    decompiler: Path
    vanilla_imports: Path
    vanilla_pex: Path
    dependency_assets: Path
    dotnet: Path

    @property
    def profile_dir(self):
        return self.mo2_root / "profiles" / self.profile

    @property
    def build_dir(self):
        return self.workspace / "build"

    def dependency_packages(self):
        assets = json.loads(self.dependency_assets.read_text(encoding="utf-8-sig"))
        caches = [Path(folder) for folder in assets["packageFolders"]]
        result = []
        for name, detail in sorted(assets["libraries"].items()):
            if detail["type"] != "package":
                continue
            relative = Path(detail["path"])
            windows_relative = PureWindowsPath(detail["path"])
            if relative.anchor or windows_relative.anchor or ".." in relative.parts or ".." in windows_relative.parts:
                raise ValueError(f"Unsafe package cache path: {name}")
            source = next((cache / relative for cache in caches
                           if (cache / relative).is_dir()), None)
            if source is None:
                raise ValueError(f"Required offline package is not cached: {name}")
            result.append((source, relative))
        if not result:
            raise ValueError("Dependency assets contain no cached packages")
        return result

    def plan(self, source_root: Path):
        """Validate all inputs without creating even the workspace directory."""
        if (not self.profile or "/" in self.profile or "\\" in self.profile
                or Path(self.profile).name != self.profile or self.profile in (".", "..")):
            raise ValueError("Profile must be one directory name below MO2 profiles")
        source_root = source_root.resolve()
        workspace = self.workspace.resolve()
        if workspace == Path(workspace.anchor):
            raise ValueError("Workspace must not be a filesystem root")
        if workspace.exists() and (not workspace.is_dir() or any(workspace.iterdir())):
            raise ValueError("Build workspace must be absent or empty; use a fresh directory")
        protected = [self.mo2_root, self.vanilla_imports, self.vanilla_pex,
                     self.dependency_assets.parent,
                     source_root / "src", source_root / "imports",
                     source_root / "data", source_root / "tools"]
        for path in protected:
            resolved = path.resolve()
            if workspace.is_relative_to(resolved) or resolved.is_relative_to(workspace):
                raise ValueError(f"Workspace overlaps a protected input: {path}")
        files = {
            "modlist": self.profile_dir / "modlist.txt",
            "compiler": self.compiler, "flags": self.flags,
            "decompiler": self.decompiler, "dotnet": self.dotnet,
            "dependency_assets": self.dependency_assets,
            "plugin_project": source_root / "tools/PluginBuilder/PluginBuilder.csproj",
            "plugin_source": source_root / "tools/PluginBuilder/Program.cs",
            "nuget_config": source_root / "tools/PluginBuilder/NuGet.Config",
        }
        for label, path in files.items():
            if not path.is_file():
                raise ValueError(f"Missing {label}: {path}")
        for path in (self.mo2_root / "mods", self.vanilla_imports, self.vanilla_pex,
                     source_root / "src", source_root / "imports", source_root / "data"):
            if not path.is_dir():
                raise ValueError(f"Missing input directory: {path}")
        packages = self.dependency_packages()
        for source, _ in packages:
            if workspace.is_relative_to(source.resolve()) or source.resolve().is_relative_to(workspace):
                raise ValueError(f"Workspace overlaps a package cache: {source}")
        source_files = {
            p.relative_to(source_root).as_posix(): sha256(p)
            for folder in ("src", "data", "imports")
            for p in sorted((source_root / folder).rglob("*")) if p.is_file()
        }
        return {
            "schema_version": 1,
            "mode": "offline_build_plan",
            "source_root": str(source_root),
            "workspace": str(workspace),
            "package": str(workspace / "build/package"),
            "stack": {"mo2_root": str(self.mo2_root), "profile": self.profile},
            "inputs": {key: {"path": str(path), "sha256": sha256(path)}
                       for key, path in files.items()},
            "source_files": source_files,
            "offline_packages": [{"source": str(source), "path": relative.as_posix()}
                                 for source, relative in packages],
            "writes_confined_to": str(workspace),
            "installs_game_files": False,
            "downloads_dependencies": False,
            "runtime_verified": False,
        }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate an offline game-package build; no writes unless --build is supplied.")
    parser.add_argument("--workspace", type=Path, required=True, help="Fresh, empty build directory")
    parser.add_argument("--mo2-root", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--compiler", type=Path, required=True, help="Installed Caprica executable")
    parser.add_argument("--flags", type=Path, required=True, help="TESV Papyrus flags file")
    parser.add_argument("--decompiler", type=Path, required=True, help="Installed Champollion executable")
    parser.add_argument("--vanilla-imports", type=Path, required=True)
    parser.add_argument("--vanilla-pex", type=Path, required=True)
    parser.add_argument("--dependency-assets", type=Path, required=True,
                        help="Existing project.assets.json identifying cached exact dependencies")
    parser.add_argument("--dotnet", type=Path, default=Path(shutil.which("dotnet") or "dotnet"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--build", action="store_true", help="Compile into the fresh workspace on Windows")
    mode.add_argument("--dry-run", action="store_true", help="Explicit alias for the default validation")
    args = parser.parse_args(argv)
    values = vars(args).copy()
    build = values.pop("build")
    values.pop("dry_run")
    for key, value in values.items():
        if isinstance(value, Path):
            values[key] = value.resolve()
    return BuildConfig(**values), build
