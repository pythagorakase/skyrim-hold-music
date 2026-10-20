"""Read-only review of a candidate game package against an existing installation.

This is not an installer. Runtime state and library assets are never merged,
and package hashes alone cannot attest to engine behavior or VFS winners.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re

from hold_music.library import _recording_errors
from hold_music.recording_identity import VERSION_FIELDS

DEFAULT_MOD = "MGO Experimental - Hold Music Performances"
DEFAULT_DATA_MOD = "MGO Experimental - Profile Data"
STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusic"
BARD_CONFIG = "SKSE/Plugins/SkyrimNet/config/BardSinging.yaml"
SETTINGS = "mcm/config/HoldMusic/settings.ini"
STATIC_FILES = frozenset({
    "HoldMusic.esp", "SEQ/HoldMusic.seq", "SKSE/Plugins/HoldMusic/registry.json",
    "mcm/config/HoldMusic/config.json", "Sound/fx/holdmusic/README.txt",
    *(f"Scripts/{name}.pex" for name in ("HM_Config", "HM_Controller", "HM_Library")),
    *(f"Scripts/Source/{name}.psc" for name in ("HM_Config", "HM_Controller", "HM_Library")),
})
REQUIRED_FILES = STATIC_FILES - {"Sound/fx/holdmusic/README.txt"} | {SETTINGS}


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(raw):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)


def _component(value):
    if (not isinstance(value, str) or not value or value in (".", "..")
            or value[-1] in " ." or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
            or value.split(".")[0].upper() in {
                "CON", "PRN", "AUX", "NUL",
                *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError("Unsafe path component")
    return value


def _relative(value):
    if not isinstance(value, str) or PureWindowsPath(value).anchor:
        raise ValueError("Unsafe relative path")
    for part in value.split("/"):
        _component(part)
    return value


def _no_alias(path):
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Symlink or junction is not a promotion input: " + str(entry))
    return path


def _root(value):
    path = _no_alias(Path(os.path.abspath(value)))
    if not path.is_dir():
        raise ValueError("Missing input directory: " + str(path))
    return path


def _child(root, relative):
    return _no_alias(root / _relative(relative))


def _files(root):
    if not root.exists():
        return []
    _no_alias(root)
    if not root.is_dir():
        raise ValueError("Expected directory: " + str(root))
    result, seen = [], set()
    for folder, directories, filenames in os.walk(root, followlinks=False):
        for name in (*directories, *filenames):
            _no_alias(Path(folder) / name)
        for name in sorted(filenames):
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix().casefold()
            if relative in seen:
                raise ValueError("Duplicate case-insensitive filesystem path")
            seen.add(relative)
            result.append(path)
        directories.sort()
    return sorted(result)


def _hash_inventory(value, label):
    if not isinstance(value, dict) or not value:
        raise ValueError(label + " must be a nonempty hash inventory")
    seen = set()
    for relative, digest in value.items():
        _relative(relative)
        if relative.casefold() in seen:
            raise ValueError("Duplicate case-insensitive path in " + label)
        seen.add(relative.casefold())
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("Invalid SHA256 in " + label)
    return value


class _Observation:
    def __init__(self):
        self.rows = {}

    def read(self, path, *, content=False):
        path = _no_alias(path)
        name = str(path)
        if not path.exists():
            row, raw = {"path": name, "exists": False}, None
        else:
            before = path.stat()
            if not path.is_file():
                raise ValueError("Expected regular file: " + name)
            hasher = hashlib.sha256()
            parts = [] if content else None
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    hasher.update(chunk)
                    if parts is not None:
                        parts.append(chunk)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("Input changed while reading: " + name)
            row = {"path": name, "exists": True, "size": after.st_size,
                   "mtime_ns": after.st_mtime_ns, "sha256": hasher.hexdigest()}
            raw = b"".join(parts) if parts is not None else None
        if name in self.rows and self.rows[name] != row:
            raise ValueError("Input changed during planning: " + name)
        self.rows[name] = row
        return (row, raw) if content else row

    def finish(self):
        for name, row in self.rows.items():
            path = _no_alias(Path(name))
            if path.exists() != row["exists"]:
                raise ValueError("Input presence changed during planning: " + name)
            if row["exists"]:
                info = path.stat()
                if (info.st_size, info.st_mtime_ns) != (row["size"], row["mtime_ns"]):
                    raise ValueError("Input changed during planning: " + name)
        return [self.rows[key] for key in sorted(self.rows)]


def plan_promotion(build_dir, source_root, mo2_root, profile, *,
                   mod_name=DEFAULT_MOD, data_mod=DEFAULT_DATA_MOD, library=None):
    """Return a deterministic review plan without creating files or subprocesses."""
    build, source, mo2 = map(_root, (build_dir, source_root, mo2_root))
    _component(profile)
    _component(mod_name)
    if data_mod is not None:
        _component(data_mod)
    for left, right in ((build, mo2), (source, mo2)):
        if left.is_relative_to(right) or right.is_relative_to(left):
            raise ValueError("Candidate/source overlaps the installed MO2 root")
    target = _root(_child(mo2, "mods/" + mod_name))
    profile_dir = _root(_child(mo2, "profiles/" + profile))
    package = _root(_child(build, "package"))
    observed = _Observation()
    receipt_file, receipt_raw = observed.read(_child(build, "build-receipt.json"), content=True)
    hashes_file, hashes_raw = observed.read(_child(build, "package-hashes.json"), content=True)
    if receipt_raw is None or hashes_raw is None:
        raise ValueError("A complete build receipt and package hash inventory are required")
    receipt, hashes = _json(receipt_raw), _hash_inventory(_json(hashes_raw), "package hashes")
    if (not isinstance(receipt, dict) or type(receipt.get("schema_version")) is not int
            or receipt["schema_version"] != 1 or receipt.get("status") != "built_offline"
            or receipt.get("installed") is not False or receipt.get("runtime_verified") is not False):
        raise ValueError("Expected a built_offline game-package receipt, not a staging receipt")
    if receipt.get("package_hashes") != hashes or not REQUIRED_FILES <= set(hashes):
        raise ValueError("Build receipt/package inventory mismatch")
    actual = {path.relative_to(package).as_posix() for path in _files(package)}
    if actual != set(hashes):
        raise ValueError("Actual package inventory differs from the build receipt")
    provenance = receipt.get("plan")
    if not isinstance(provenance, dict) or provenance.get("mode") != "offline_build_plan":
        raise ValueError("Missing offline build plan provenance")
    source_hashes = _hash_inventory(provenance.get("source_files"), "source hashes")
    if not {f"src/{name}" for name in STATIC_FILES if name.startswith("Scripts/Source/")} <= set(source_hashes):
        raise ValueError("Build receipt lacks controller source provenance")
    def current_source_paths():
        return {path.relative_to(source).as_posix()
                for folder in ("src", "data", "imports")
                for path in _files(_child(source, folder))}

    if current_source_paths() != set(source_hashes):
        raise ValueError("Actual source inventory differs from the build receipt")
    for relative, digest in sorted(source_hashes.items()):
        current = observed.read(_child(source, relative))
        if current.get("sha256") != digest:
            raise ValueError("Recorded source differs from the explicit source root: " + relative)
        if relative.startswith("src/") and relative[4:] in hashes and hashes[relative[4:]] != digest:
            raise ValueError("Packaged source differs from its build input: " + relative)
    # Only local source inputs are re-read; receipt paths never select files.
    inputs = provenance.get("inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError("Build inputs must be an object")
    for label, relative in (
        ("plugin_project", "tools/PluginBuilder/PluginBuilder.csproj"),
        ("plugin_source", "tools/PluginBuilder/Program.cs"),
        ("nuget_config", "tools/PluginBuilder/NuGet.Config"),
    ):
        declared = inputs.get(label, {})
        if not isinstance(declared, dict):
            raise ValueError("Invalid build input: " + label)
        current = observed.read(_child(source, relative))
        if current.get("sha256") is None or current["sha256"] != declared.get("sha256"):
            raise ValueError("Recorded build input differs from the source root: " + label)

    blockers, files, preserved = [], [], []

    def block(code, detail):
        item = {"code": code, "detail": detail}
        if item not in blockers:
            blockers.append(item)

    built_stack = provenance.get("stack")
    if (not isinstance(built_stack, dict) or built_stack.get("profile") != profile
            or not isinstance(built_stack.get("mo2_root"), str)
            or os.path.normcase(os.path.abspath(built_stack["mo2_root"])) != os.path.normcase(str(mo2))):
        block("build_stack_mismatch", "Candidate was not recorded against the selected MO2 root and profile")

    def library_metadata(path, origin):
        state, raw = observed.read(path, content=True)
        if raw is None:
            return
        try:
            data = _json(raw)
            if (not isinstance(data, dict) or type(data.get("version")) is not int
                    or data["version"] != 1 or data.get("slots") != 24
                    or not isinstance(data.get("recordings"), list)):
                raise ValueError("invalid library shape")
            seen_slots = set()
            for index, row in enumerate(data["recordings"]):
                if _recording_errors(row, 24):
                    block("malformed_library_metadata", f"{origin}: recording {index}")
                if isinstance(row, dict) and type(row.get("slot")) is int:
                    if row["slot"] in seen_slots:
                        block("malformed_library_metadata", f"{origin}: duplicate slot")
                    seen_slots.add(row["slot"])
                if isinstance(row, dict) and any(row.get(key) is not None for key in VERSION_FIELDS):
                    block("versioned_library_unsupported",
                          f"{origin}: recording {index}; no verified runtime identity capability")
        except (ValueError, TypeError, KeyError):
            block("malformed_library_metadata", origin)

    for relative, digest in sorted(hashes.items()):
        src, dest = _child(package, relative), _child(target, relative)
        proposed, existing = observed.read(src), observed.read(dest)
        if proposed.get("sha256") != digest:
            raise ValueError("Package hash mismatch: " + relative)
        if relative in STATIC_FILES:
            action = "unchanged" if existing.get("sha256") == digest else (
                "replace_static" if existing["exists"] else "add_static")
        elif relative == SETTINGS:
            action = "preserve_user_settings"
            if not existing["exists"]:
                block("missing_user_settings", relative)
        elif relative.casefold().startswith((STORAGE.casefold() + "/", "sound/fx/holdmusic/")):
            action = "preserve_runtime"
            block("runtime_payload_not_supported", relative + "; requires a separate library merge plan")
        else:
            action = "unsupported_candidate_file"
            block("unsupported_candidate_file", relative)
        files.append({"relative_path": relative, "source": proposed, "destination": existing, "action": action})
        if relative.casefold() == (STORAGE + "/library.json").casefold():
            library_metadata(src, "candidate library")

    for path in _files(target):
        row = observed.read(path)
        relative = path.relative_to(target).as_posix()
        if relative not in STATIC_FILES:
            preserved.append({"kind": "installed_runtime_or_other", **row})
    library_metadata(_child(target, STORAGE + "/library.json"), "installed library")
    for relative in ("modlist.txt", "plugins.txt"):
        row = observed.read(_child(profile_dir, relative))
        if not row["exists"]:
            raise ValueError("Missing profile list: " + relative)
        recorded_modlist = inputs.get("modlist", {})
        if relative == "modlist.txt" and (
                not isinstance(recorded_modlist, dict) or row["sha256"] != recorded_modlist.get("sha256")):
            block("build_modlist_changed", "Selected profile modlist differs from the recorded build input")
        preserved.append({"kind": "profile_list", **row})
    for path in _files(_child(profile_dir, "saves")):
        preserved.append({"kind": "save", **observed.read(path)})
    for name, root in (("overwrite", _child(mo2, "overwrite")),
                       *((("data_mod", _child(mo2, "mods/" + data_mod)),) if data_mod else ())):
        for relative in (STORAGE, "SKSE/Plugins/HoldMusic", "Sound/fx/holdmusic"):
            for path in _files(_child(root, relative)):
                preserved.append({"kind": name, **observed.read(path)})
        preserved.append({"kind": name, **observed.read(_child(root, BARD_CONFIG))})
        library_metadata(_child(root, STORAGE + "/library.json"), name + " library")
        for relative in sorted(STATIC_FILES):
            shadow = observed.read(_child(root, relative))
            if shadow["exists"]:
                block("possible_static_override", str(_child(root, relative)))
    if library is not None:
        proposed_library = _root(library)
        for other in (target, build):
            if proposed_library.is_relative_to(other) or other.is_relative_to(proposed_library):
                raise ValueError("Inspection library overlaps candidate or target")
        if not _child(proposed_library, "library.json").is_file():
            raise ValueError("Inspection library requires library.json")
        library_metadata(_child(proposed_library, "library.json"), "inspection library")
        # Metadata review does not stage, overwrite or merge any recording.
        block("library_promotion_not_supported", "Inspection only; existing audio and manifests are preserved")

    if current_source_paths() != set(source_hashes):
        raise ValueError("Source inventory changed during planning")
    snapshot = observed.finish()
    snapshot_hash = _digest(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode())
    return {
        "schema_version": 1, "operation": "plan_game_promotion",
        "status": "blocked" if blockers else "review_only",
        "installed": False, "runtime_verified": False, "writes_performed": False,
        "build_dir": str(build), "source_root": str(source),
        "target": {"mo2_root": str(mo2), "profile": profile, "mod": str(target)},
        "build_receipt_sha256": receipt_file["sha256"],
        "package_hashes_sha256": hashes_file["sha256"],
        "source_commit": None, "source_commit_status": "not_recorded_by_build_receipt",
        "recorded_build_stack": provenance.get("stack"),
        "build_provenance": {"inputs": inputs, "dependencies": receipt.get("dependencies", {}),
                             "source_files": source_hashes},
        "files": files, "preserved": sorted(preserved, key=lambda row: (row["path"], row["kind"])),
        "blockers": sorted(blockers, key=lambda row: (row["code"], row["detail"])),
        "runtime_identity_supported": False, "vfs_winners_verified": False,
        "snapshot_sha256": snapshot_hash, "observed_files": snapshot,
        "limits": [
            "Static differences are proposals only; this command has no apply operation.",
            "Runtime JSON, audio, lyrics, user settings, saves and profile lists are preserved.",
            "Build provenance is evidence, not attestation of runtime identity enforcement.",
            "Library metadata inspection does not validate or promote its audio assets.",
            "VFS winners, running processes, saved-script compatibility and playback remain unverified.",
            "Replan after any source or target change; observations are not an atomic filesystem snapshot.",
        ],
    }
