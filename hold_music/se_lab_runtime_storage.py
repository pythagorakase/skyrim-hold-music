"""Runtime-only, metadata-only accounting for three PrismaUI session files.

This is not an installer, a writer attribution mechanism, or a general cache
exception. A fresh launch must bind the returned contract while Game/default is
absent. Existing installation/preflight snapshots remain strict and unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from hold_music.promotion import _component, _no_alias, _relative


VERSION = 1
POLICY_ID = "prismaui-1.5.1-default-session-three-files-v1"
MANIFEST = "lab-manifest.json"
FILES = ("default/cookie.jar.db", "default/cookie.jar.db-shm", "default/cookie.jar.db-wal")
_STAMP = {"path", "size", "mtime_ns", "ctime_ns", "device", "inode"}
_DIRECTORY = {"path", "exists", "device", "inode", "mtime_ns", "inventory_sha256"}
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _policy():
    return dict(version=VERSION, policy_id=POLICY_ID, game_directory="default",
                files=list(FILES), fresh_directory_absent=True, contents_read=False,
                attribution_verified=False)


class _ObservationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _root(value):
    path = Path(value)
    if not path.is_absolute() or str(path) != os.path.abspath(path):
        raise ValueError("An absolute canonical lab root is required")
    info = _info(path)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("The lab root must be an ordinary directory")
    return path


def _info(path):
    _no_alias(path)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise _ObservationError("aliased_path")
    return info


def _integer_fields(row, names):
    return all(type(row.get(name)) is int and row[name] >= 0 for name in names)


def _baseline(root, value):
    """Validate retained data lexically; never open a path supplied by a report."""
    if (not isinstance(value, dict)
            or set(value) != {"Game", "MO2", "manifest", "directories", "root_identity"}
            or not isinstance(value["root_identity"], dict)
            or set(value["root_identity"]) != {"device", "inode"}
            or not _integer_fields(value["root_identity"], ("device", "inode"))):
        raise ValueError("Invalid protected baseline")
    directories = value["directories"]
    if not isinstance(directories, dict):
        raise ValueError("Invalid protected baseline directories")
    paths = set()
    for section in ("Game", "MO2"):
        rows = value[section]
        if not isinstance(rows, dict):
            raise ValueError("Invalid protected baseline files")
        folded = set()
        for relative, row in rows.items():
            _relative(relative)
            if relative.casefold() in folded:
                raise ValueError("Ambiguous protected baseline")
            folded.add(relative.casefold())
            path = str(root / section / relative)
            if (not isinstance(row, dict) or set(row) != _STAMP or row["path"] != path
                    or not _integer_fields(row, _STAMP - {"path"})):
                raise ValueError("Invalid protected baseline file metadata")
            paths.add(path)
    folded_directories = set()
    for path, row in directories.items():
        if not isinstance(path, str):
            raise ValueError("Invalid protected baseline directory path")
        try:
            relative = Path(path).relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("Invalid protected baseline directory path") from exc
        _relative(relative)
        if (relative.split("/")[0] not in ("Game", "MO2")
                or str(root / relative) != path or path in paths
                or path.casefold() in folded_directories
                or not isinstance(row, dict) or set(row) != _DIRECTORY
                or row["path"] != path or row["exists"] is not True
                or not _integer_fields(row, ("device", "inode", "mtime_ns"))
                or not isinstance(row["inventory_sha256"], str)
                or not _HEX.fullmatch(row["inventory_sha256"])):
            raise ValueError("Invalid protected baseline directory metadata")
        folded_directories.add(path.casefold())
    for section in ("Game", "MO2"):
        if str(root / section) not in directories:
            raise ValueError("Protected baseline roots must exist")
    children_by_parent = {}
    for path in paths | set(directories):
        parent = Path(path).parent
        if parent != root and str(parent) not in directories:
            raise ValueError("Protected baseline directory inventory is incomplete")
        children_by_parent.setdefault(str(parent), []).append(Path(path).name)
    for path, row in directories.items():
        children = sorted(children_by_parent.get(path, ()))
        if len({p.casefold() for p in children}) != len(children) or _digest(children) != row["inventory_sha256"]:
            raise ValueError("Protected baseline directory inventory is inconsistent")
    manifest = value["manifest"]
    if (not isinstance(manifest, dict) or set(manifest) != _STAMP | {"exists", "sha256"}
            or manifest["path"] != str(root / MANIFEST) or manifest["exists"] is not True
            or not _integer_fields(manifest, _STAMP - {"path"})
            or not isinstance(manifest["sha256"], str) or not _HEX.fullmatch(manifest["sha256"])):
        raise ValueError("Invalid protected baseline manifest")
    # No adoption of existing opaque session data, including an empty old folder.
    if (any(p.split("/")[0].casefold() == "default" for p in value["Game"])
            or any(Path(p).relative_to(root).parts[:2] == ("Game", "default")
                   for p in directories)
            or any(Path(p).parent == root / "Game" and Path(p).name.casefold() == "default"
                   for p in directories)):
        raise ValueError("Fresh runtime storage requires Game/default to be absent")
    return deepcopy(value)


def _stamp(path, info):
    return dict(path=str(path), size=info.st_size, mtime_ns=info.st_mtime_ns,
                ctime_ns=info.st_ctime_ns, device=info.st_dev, inode=info.st_ino)


def _manifest(path, expected):
    """Check the retained manifest object before any content read, not afterward."""
    wanted = {key: expected[key] for key in _STAMP}

    def check(info, *, handle=False):
        actual = _stamp(path, info)
        # On Windows lstat and fstat can report different ctime values for the
        # same file after an in-place write. Keep the full path guards; the
        # opened handle must match device, inode, size and mtime before reading.
        keys = _STAMP - ({"ctime_ns"} if handle and os.name == "nt" else set())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or any(actual[key] != wanted[key] for key in keys)):
            raise _ObservationError("manifest_identity_or_metadata_changed")

    check(_info(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        # A path can be replaced after lstat but before open. No read is allowed
        # until the actual handle matches the retained original manifest.
        check(os.fstat(stream.fileno()), handle=True)
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
        check(os.fstat(stream.fileno()), handle=True)
        check(_info(path))
    return {**wanted, "exists": True, "sha256": digest.hexdigest()}


def _scan(root, manifest_baseline):
    """One metadata walk; volatile SQLite files are never opened or hashed."""
    root = _root(root)
    directories = {}
    storage = {name: dict(path="Game/" + name, exists=False) for name in FILES}
    storage_directory = dict(path="Game/default", exists=False)

    def walk(path, relative, section):
        nonlocal storage_directory
        before = _info(path)
        if not stat.S_ISDIR(before.st_mode):
            raise _ObservationError("invalid_directory")
        names = sorted(entry.name for entry in path.iterdir())
        after = _info(path)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise _ObservationError("directory_identity_changed")
        if len({name.casefold() for name in names}) != len(names):
            raise _ObservationError("ambiguous_names")
        mutable_directory = section == "Game" and relative in ("", "default/")
        if not mutable_directory and before.st_mtime_ns != after.st_mtime_ns:
            raise _ObservationError("immutable_directory_changed")
        row = dict(path=str(path), exists=True, device=before.st_dev, inode=before.st_ino,
                   mtime_ns=before.st_mtime_ns, inventory_sha256=_digest(names))
        directories[str(path)] = row
        if section == "Game" and relative == "default/":
            storage_directory = {**row, "path": "Game/default"}
        files = {}
        for name in names:
            _component(name)
            rel = relative + name
            cache_directory = section == "Game" and relative == "" and name.casefold() == "default"
            cache_file = section == "Game" and relative == "default/"
            if cache_directory and name != "default":
                raise _ObservationError("noncanonical_storage_name")
            if cache_file and rel not in FILES:
                raise _ObservationError("unexpected_storage_entry")
            child = path / name
            try:
                info = _info(child)
            except FileNotFoundError:
                if cache_file:
                    storage[rel]["missing_after_listing"] = True
                    continue
                raise _ObservationError("immutable_entry_disappeared")
            if stat.S_ISDIR(info.st_mode):
                if cache_file:
                    raise _ObservationError("storage_entry_is_directory")
                files.update(walk(child, rel + "/", section))
            else:
                if cache_directory:
                    raise _ObservationError("storage_root_is_not_directory")
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise _ObservationError("nonregular_or_aliased_file")
                files[rel] = _stamp(child, info)
                if cache_file:
                    storage[rel] = {**files[rel], "path": "Game/" + rel, "exists": True}
        return files

    result = {name: walk(root / name, "", name) for name in ("Game", "MO2")}
    result["manifest"] = _manifest(root / MANIFEST, manifest_baseline)
    result["directories"] = directories
    info = _info(root)
    result["root_identity"] = dict(device=info.st_dev, inode=info.st_ino)
    return result, dict(directory=storage_directory, files=list(storage.values()), contents_read=False)


def _projection(root, observed, baseline):
    result = deepcopy(observed)
    result["Game"] = {name: row for name, row in result["Game"].items() if name not in FILES}
    storage_directory = result["directories"].pop(str(root / "Game/default"), None)
    game = result["directories"][str(root / "Game")]
    # Creating the one permitted directory changes Game's mtime/listing. Its
    # identity and every other child are still checked; all other directories
    # retain their original complete metadata guards.
    if storage_directory is not None:
        game["mtime_ns"] = baseline["directories"][str(root / "Game")]["mtime_ns"]
    children = {Path(name).parts[0] for name in result["Game"]}
    children.update(Path(path).name for path in result["directories"] if Path(path).parent == root / "Game")
    game["inventory_sha256"] = _digest(sorted(children))
    return result


def _contract(root, baseline):
    policy = _policy()
    return dict(version=VERSION, root=str(root), policy=policy,
                policy_sha256=_digest(policy), protected_baseline_sha256=_digest(baseline),
                immutable_projection_sha256=_digest(_projection(root, baseline, baseline)))


def prepare_runtime_storage(root, protected_baseline):
    """Bind before a fresh launch; reject existing storage or baseline drift.

    The caller must retain this exact object in the immutable launch intent.
    This function does not authorize installation, launch, or later cache cleanup.
    """
    root = _root(root)
    baseline = _baseline(root, protected_baseline)
    first, _ = _scan(root, baseline["manifest"])
    second, _ = _scan(root, baseline["manifest"])
    if first != baseline or second != baseline:
        raise ValueError("Fresh protected baseline changed or runtime storage already exists")
    return _contract(root, baseline)


def observe_runtime_storage(root, protected_baseline, contract):
    """Return stable binding separately from volatile, private metadata.

    Missing/altered contracts raise rather than implicitly granting exceptions
    to older runs. Operational/structural failures return a blocked observation.
    Only the baseline manifest is read; game assets and database files use stat.
    """
    # Lexical checks happen before touching a potentially changed root.
    root = Path(root)
    if not root.is_absolute() or str(root) != os.path.abspath(root):
        raise ValueError("An absolute canonical lab root is required")
    baseline = _baseline(root, protected_baseline)
    binding = _contract(root, baseline)
    if not isinstance(contract, dict) or _digest(contract) != _digest(binding):
        raise ValueError("An explicit exact pre-launch runtime-storage contract is required")
    result = dict(version=VERSION, policy_id=POLICY_ID, binding=binding,
                  protected_paths_unchanged=False, original_assets_unchanged=False,
                  storage_within_contract=False, observation=None, blockers=[],
                  writes_performed=False, database_contents_read=False, asset_contents_read=False,
                  writer_attribution_verified=False, runtime_verified=False, egress_verified=False)
    try:
        first, first_storage = _scan(root, baseline["manifest"])
        second, second_storage = _scan(root, baseline["manifest"])
        projection = _projection(root, second, baseline)
        stable = _projection(root, first, baseline) == projection
        matches = stable and _digest(projection) == binding["immutable_projection_sha256"]
        result.update(protected_paths_unchanged=first == baseline and second == baseline,
                      original_assets_unchanged=matches, storage_within_contract=True,
                      observation=dict(first=first_storage, last=second_storage,
                                       metadata_changed_during_observation=first_storage != second_storage,
                                       private_runtime_storage=True, contents_read=False))
        if not matches:
            result["blockers"].append("original_assets_changed" if stable else "original_assets_unstable")
    except _ObservationError as exc:
        result["blockers"].append(exc.code)
    except (OSError, ValueError):
        # No exception text, paths from errors, credentials, or native log data.
        result["blockers"].append("runtime_storage_observation_failed")
    result["status"] = "within_contract" if not result["blockers"] else "blocked"
    return result
