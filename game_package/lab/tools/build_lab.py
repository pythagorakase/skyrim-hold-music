"""Plan or build the separate Hold Music LAB package with offline dependencies."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
HARNESS = "HM_LabHarness"
BUILDER_FILES = ("Program.cs", "HM_LabPluginBuilder.csproj", "NuGet.Config")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def overlaps(first: Path, second: Path) -> bool:
    first, second = first.resolve(), second.resolve()
    return first.is_relative_to(second) or second.is_relative_to(first)


def ensure_fresh_workspace(workspace: Path) -> None:
    workspace = workspace.resolve()
    if workspace == Path(workspace.anchor):
        raise ValueError("Workspace must not be a filesystem root")
    if workspace.exists() and (not workspace.is_dir() or any(workspace.iterdir())):
        raise ValueError("Workspace must be absent or empty; use a fresh directory")


@dataclass(frozen=True)
class LabBuildConfig:
    workspace: Path
    production_build: Path
    compiler: Path
    flags: Path
    decompiler: Path
    dotnet: Path
    dependency_assets: Path

    def dependency_packages(self):
        assets = json.loads(self.dependency_assets.read_text(encoding="utf-8-sig"))
        caches = [Path(folder) for folder in assets["packageFolders"]]
        packages = []
        seen = set()
        libraries = assets["libraries"]
        if "Mutagen.Bethesda.Skyrim/0.51.5" not in libraries:
            raise ValueError("Dependency assets must include Mutagen.Bethesda.Skyrim/0.51.5")
        for name, detail in sorted(libraries.items()):
            if detail["type"] != "package":
                continue
            raw = detail["path"]
            relative, windows_relative = Path(raw), PureWindowsPath(raw)
            if (not raw or relative == Path(".") or relative.anchor or windows_relative.anchor
                    or ".." in relative.parts or ".." in windows_relative.parts):
                raise ValueError(f"Unsafe package cache path: {name}")
            normalized = windows_relative.as_posix().casefold()
            if normalized in seen:
                raise ValueError(f"Duplicate package cache path: {name}")
            seen.add(normalized)
            source = next((cache / relative for cache in caches if (cache / relative).is_dir()), None)
            if source is None:
                raise ValueError(f"Required offline package is not cached: {name}")
            packages.append((source.resolve(), relative))
        if not packages:
            raise ValueError("Dependency assets contain no cached packages")
        return packages

    def plan(self, source_root: Path = ROOT) -> dict:
        """Validate and hash inputs without running tools or creating directories."""
        source_root = source_root.resolve()
        workspace, production = self.workspace.resolve(), self.production_build.resolve()
        ensure_fresh_workspace(workspace)
        files = {
            "harness": source_root / f"lab/src/Scripts/Source/{HARNESS}.psc",
            "compiler": self.compiler.resolve(),
            "flags": self.flags.resolve(),
            "decompiler": self.decompiler.resolve(),
            "dotnet": self.dotnet.resolve(),
            "dependency_assets": self.dependency_assets.resolve(),
            "production_plan": production / "build-plan.json",
            "production_plugin": production / "package/HoldMusic.esp",
            "production_controller": production / "package/Scripts/HM_Controller.pex",
            "production_config": production / "package/Scripts/HM_Config.pex",
            "production_library": production / "package/Scripts/HM_Library.pex",
            "forms": source_root / "data/forms.json",
            "plugin_project": source_root / "lab/builder/HM_LabPluginBuilder.csproj",
            "plugin_source": source_root / "lab/builder/Program.cs",
            "nuget_config": source_root / "lab/builder/NuGet.Config",
            "plugin_test": source_root / "lab/tests/test_lab_plugin.py",
            "build_driver": Path(__file__).resolve(),
        }
        for label, path in files.items():
            if not path.is_file():
                raise ValueError(f"Missing {label}: {path}")
        input_dirs = {
            "candidate_imports": production / "imports",
            "production_sources": source_root / "src/Scripts/Source",
            "package_imports": source_root / "imports",
        }
        for label, path in input_dirs.items():
            if not path.is_dir():
                raise ValueError(f"Missing {label} directory: {path}")
        production_plan = json.loads(files["production_plan"].read_text(encoding="utf-8-sig"))
        mo2_value = production_plan.get("stack", {}).get("mo2_root")
        if not isinstance(mo2_value, str) or not mo2_value or not Path(mo2_value).is_absolute():
            raise ValueError("Production build-plan.json must record an absolute stack.mo2_root")
        mo2_root = Path(mo2_value).resolve()
        if not mo2_root.is_dir():
            raise ValueError(f"Recorded installed MO2 root is unavailable: {mo2_root}")
        protected = [
            production, mo2_root,
            source_root / "src", source_root / "imports", source_root / "data",
            source_root / "tools", source_root / "lab/src", source_root / "lab/builder",
            source_root / "lab/tools", source_root / "lab/tests",
            self.dependency_assets.parent,
            self.compiler.parent, self.decompiler.parent, self.dotnet.parent,
            *files.values(), *input_dirs.values(),
        ]
        for path in protected:
            if overlaps(workspace, path):
                raise ValueError(f"Workspace overlaps a protected input or installed path: {path}")
        packages = self.dependency_packages()
        for source, _ in packages:
            if overlaps(workspace, source):
                raise ValueError(f"Workspace overlaps a package cache: {source}")
        for name in ("HM_Controller.psc", "HM_Config.psc", "HM_Library.psc"):
            if not (input_dirs["production_sources"] / name).is_file():
                raise ValueError(f"Missing production script import: {name}")
        return {
            "schema_version": 1,
            "mode": "offline_lab_build_plan",
            "offline_only": True,
            "source_root": str(source_root),
            "workspace": str(workspace),
            "production_build": str(production),
            "protected_mo2_root": str(mo2_root),
            "package": str(workspace / "build/package"),
            "inputs": {name: {"path": str(path), "sha256": sha256(path)}
                       for name, path in files.items()},
            "import_directories": {
                name: {"path": str(path), "files": tree_hashes(path)}
                for name, path in input_dirs.items()
            },
            "offline_packages": [
                {"source": str(source), "path": relative.as_posix(), "files": tree_hashes(source)}
                for source, relative in packages
            ],
            "compile_targets": [f"{HARNESS}.psc"],
            "writes_confined_to": str(workspace),
            "installs_game_files": False,
            "launches_game": False,
            "downloads_dependencies": False,
            "runtime_verified": False,
        }


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def copy_checked(source: Path, destination: Path, expected: str) -> None:
    if sha256(source) != expected:
        raise ValueError(f"Input changed after planning: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256(destination) != expected:
        raise ValueError(f"Snapshot hash mismatch: {destination}")


def copy_tree_checked(source: Path, destination: Path, expected: dict) -> None:
    # Only planned files enter the snapshot; added or removed files abort the build.
    if tree_hashes(source) != expected:
        raise ValueError(f"Input directory changed after planning: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    for relative, digest in expected.items():
        copy_checked(source / relative, destination / relative, digest)


def verify_inputs_unchanged(plan: dict) -> None:
    for value in plan["inputs"].values():
        if sha256(Path(value["path"])) != value["sha256"]:
            raise ValueError(f"Input changed during lab build: {value['path']}")
    for value in plan["import_directories"].values():
        if tree_hashes(Path(value["path"])) != value["files"]:
            raise ValueError(f"Import directory changed during lab build: {value['path']}")
    for value in plan["offline_packages"]:
        if tree_hashes(Path(value["source"])) != value["files"]:
            raise ValueError(f"Dependency cache changed during lab build: {value['source']}")


def inspect_disassembly(assembly_file: Path, tool_output: str, source_file: Path) -> dict:
    if not assembly_file.is_file():
        raise RuntimeError("Decompiler did not produce HM_LabHarness.pas")
    assembly = assembly_file.read_text(encoding="utf-8-sig")
    if (not re.search(r"^\s*\.object HM_LabHarness Quest\s*$", assembly, re.M | re.I)
            or not assembly.rstrip().endswith(".endObjectTable")):
        raise RuntimeError("Generated HM_LabHarness.pas has an incomplete object table")
    # Champollion 1.3.2 emits assembly before reconstructing source and may return
    # exit code zero even when the latter fails. Keep those outcomes separate.
    diagnostics = [
        line for line in tool_output.splitlines()
        if line.startswith("ERROR:") or re.search(r"\b[1-9]\d* files? failed to decompile", line)
    ]
    return {
        "assembly_complete": True,
        "source_decompilation_verified": bool(
            not diagnostics and source_file.is_file() and source_file.stat().st_size),
        "source_decompilation_diagnostics": diagnostics,
    }


def build(config: LabBuildConfig, plan: dict) -> dict:
    if os.name != "nt":
        raise ValueError("Compilation requires the installed Windows toolchain; planning is portable")
    workspace = Path(plan["workspace"])
    ensure_fresh_workspace(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    build_dir = workspace / "build"
    build_dir.mkdir()
    write_json(build_dir / "build-plan.json", plan)
    package = build_dir / "package"
    scripts = package / "Scripts"
    scripts.mkdir(parents=True)
    environment = os.environ.copy()
    redirects = {
        "TEMP": "tmp", "TMP": "tmp", "DOTNET_CLI_HOME": "dotnet-home",
        "NUGET_PACKAGES": "nuget", "NUGET_HTTP_CACHE_PATH": "nuget-http",
        "NUGET_PLUGINS_CACHE_PATH": "nuget-plugins", "MSBUILDUSEREXTENSIONSPATH": "msbuild",
        "APPDATA": "appdata", "LOCALAPPDATA": "localappdata",
    }
    for name, relative in redirects.items():
        directory = workspace / relative
        directory.mkdir(exist_ok=True)
        environment[name] = str(directory)
    environment.update(
        DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
        DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE="1", DOTNET_NOLOGO="1",
        DOTNET_GENERATE_ASPNET_CERTIFICATE="false", PYTHONDONTWRITEBYTECODE="1",
    )
    for dependency in plan["offline_packages"]:
        copy_tree_checked(Path(dependency["source"]), workspace / "nuget" / dependency["path"],
                          dependency["files"])
    snapshots = workspace / "inputs"
    project = snapshots / "plugin-builder"
    for label, name in zip(("plugin_source", "plugin_project", "nuget_config"), BUILDER_FILES):
        value = plan["inputs"][label]
        copy_checked(Path(value["path"]), project / name, value["sha256"])
    for label, relative in (
        ("harness", f"lab-source/{HARNESS}.psc"),
        ("flags", "flags/TESV_Papyrus_Flags.flg"),
        ("forms", "data/forms.json"),
        ("plugin_test", "tests/test_lab_plugin.py"),
    ):
        value = plan["inputs"][label]
        copy_checked(Path(value["path"]), snapshots / relative, value["sha256"])
    import_paths = []
    for name, value in plan["import_directories"].items():
        destination = snapshots / name
        copy_tree_checked(Path(value["path"]), destination, value["files"])
        import_paths.append(destination)
    commands = []

    def run(arguments, log_name):
        command = [str(item) for item in arguments]
        result = subprocess.run(command, cwd=build_dir, env=environment,
                                capture_output=True, text=True, errors="replace")
        log_path = build_dir / log_name
        log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
        commands.append({"argv": command, "exit_code": result.returncode,
                         "log": log_name, "log_sha256": sha256(log_path)})
        if result.returncode:
            raise RuntimeError(f"Lab build command failed; see {log_path}")
        return result.stdout + result.stderr

    try:
        csproj = project / "HM_LabPluginBuilder.csproj"
        run([config.dotnet, "restore", csproj, "--configfile", project / "NuGet.Config",
             "-p:NuGetAudit=false"], "plugin-restore.log")
        run([config.dotnet, "run", "--project", csproj, "--no-restore",
             "--configuration", "Release", "--", package, snapshots / "data"],
            "plugin-validation.json")
        source = snapshots / "lab-source" / f"{HARNESS}.psc"
        run([config.compiler, source, "--game=skyrim", "--ignorecwd",
             "--allow-unknown-events=true",
             "--skyrim-allow-unknown-events-on-non-native-class=true",
             "-i", ";".join(str(path) for path in [source.parent, *import_paths]),
             "-f", snapshots / "flags/TESV_Papyrus_Flags.flg",
             "-o", scripts, "--dump-asm"], "compile-HM_LabHarness.log")
        pex = scripts / f"{HARNESS}.pex"
        if not pex.is_file() or {path.name for path in scripts.glob("*.pex")} != {pex.name}:
            raise RuntimeError("Compiler must produce exactly HM_LabHarness.pex")
        generated_asm = scripts / f"{HARNESS}.pas"
        if generated_asm.is_file():
            caprica_asm = build_dir / "caprica-asm"
            caprica_asm.mkdir()
            shutil.move(str(generated_asm), str(caprica_asm / generated_asm.name))
        copy_checked(source, scripts / "Source" / source.name, plan["inputs"]["harness"]["sha256"])
        disassembly = build_dir / "disassembly"
        disassembly.mkdir()
        decompiled_source = build_dir / "decompiled-source"
        decompiled_source.mkdir()
        disassembler_output = run(
            [config.decompiler, pex, "-a", disassembly, "-p", decompiled_source, "--no-debug-line"],
            "disassemble-HM_LabHarness.log")
        disassembly_status = inspect_disassembly(
            disassembly / f"{HARNESS}.pas", disassembler_output,
            decompiled_source / f"{HARNESS}.psc")
        run([sys.executable, "-B", snapshots / "tests/test_lab_plugin.py",
             "--package", package, "--forms", snapshots / "data/forms.json", "-v"],
            "plugin-tests.log")
        expected_package = {
            "HM_Lab.esp", "SEQ/HM_Lab.seq", f"Scripts/{HARNESS}.pex",
            f"Scripts/Source/{HARNESS}.psc",
        }
        package_hashes = tree_hashes(package)
        if set(package_hashes) != expected_package:
            raise RuntimeError(f"Unexpected lab package files: {sorted(package_hashes)}")
        verify_inputs_unchanged(plan)
        receipt = {
            "schema_version": 1,
            "mode": "offline_lab_build_receipt",
            "status": "passed",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "offline_only": True,
            "runtime_verified": False,
            "installs_game_files": False,
            "launches_game": False,
            "downloads_dependencies": False,
            "workspace": str(workspace),
            "production_build": plan["production_build"],
            "build_plan_sha256": sha256(build_dir / "build-plan.json"),
            "inputs": plan["inputs"],
            "import_directories": plan["import_directories"],
            "offline_packages": plan["offline_packages"],
            "outputs": {"package": package_hashes, "disassembly": tree_hashes(disassembly),
                        "decompiled_source": tree_hashes(decompiled_source)},
            "disassembly_status": disassembly_status,
            "commands": commands,
            "validation": "Offline compilation, PEX disassembly, and ESP/VMAD/SEQ validation passed",
        }
        write_json(build_dir / "build-receipt.json", receipt)
        return receipt
    except Exception as error:
        write_json(build_dir / "build-failure.json", {
            "status": "failed", "error": str(error), "commands": commands,
            "offline_only": True, "runtime_verified": False,
        })
        raise


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True,
                        help="Fresh directory for all generated files; never reuse a nonempty workspace")
    parser.add_argument("--production-build", type=Path, required=True,
                        help="Existing candidate build directory containing build-plan.json, package, imports")
    parser.add_argument("--compiler", type=Path, required=True, help="Installed Caprica executable")
    parser.add_argument("--flags", type=Path, required=True)
    parser.add_argument("--decompiler", type=Path, required=True, help="Installed Champollion executable")
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--dependency-assets", type=Path, required=True,
                        help="Existing project.assets.json for cached exact Mutagen 0.51.5 dependencies")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--build", action="store_true", help="Build into the isolated workspace")
    mode.add_argument("--dry-run", action="store_true", help="Explicit alias for the default read-only plan")
    values = vars(parser.parse_args(argv))
    do_build = values.pop("build")
    values.pop("dry_run")
    return LabBuildConfig(**{name: value.resolve() for name, value in values.items()}), do_build


def main(argv=None):
    config, do_build = parse_args(argv)
    plan = config.plan()
    if do_build:
        receipt = build(config, plan)
        print(json.dumps({
            "status": receipt["status"], "package": plan["package"],
            "receipt": str(config.workspace / "build/build-receipt.json"),
            "offline_only": True, "runtime_verified": False,
            "disassembly_status": receipt["disassembly_status"],
        }, indent=2))
    else:
        print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, KeyError) as error:
        print(f"LAB build error: {error}", file=sys.stderr)
        raise SystemExit(1)
