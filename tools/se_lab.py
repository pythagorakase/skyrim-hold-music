"""Preflight, explicitly launch/arm, and collect the isolated Skyrim SE lab."""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import configparser
import ctypes
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.installed_library import _Snapshot, _profile_text
from hold_music.job_store import _writer_lock
from hold_music.library_merge import _json
from hold_music.promotion import _component, _no_alias, _relative
from hold_music.promotion_transaction import default_process_probe

LAB_ROOT = Path(r"C:\MGO\HoldMusic-SE-Lab")
PROFILE = "Hold Music SE Lab"
RUNTIME_VERSION = "1.6.1170.0"
MANIFEST = "lab-manifest.json"
STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusicSELab"
REQUEST = "MO2/overwrite/" + STORAGE + "/request.json"
CONTROL = STORAGE + "/control.json"
RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
SCENARIO_RESULTS = {
    "ambient-entry": "ambient_entry",
    "focused-complete": "focused_complete",
    "focused-interrupt": "focused_interrupt",
}
SCENARIOS = tuple(SCENARIO_RESULTS)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _root():
    # There is deliberately no root argument, environment override or CLI bypass.
    root = _no_alias(LAB_ROOT)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("The fixed isolated SE lab directory is missing")
    return root


def _path(relative):
    return _no_alias(_root() / _relative(relative))


def _write_new(path, raw):
    _no_alias(path.parent).mkdir(parents=True, exist_ok=True)
    _no_alias(path)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    _write_new(temporary, raw)
    try:
        _no_alias(path)
        if path.exists() and (not path.is_file() or path.stat().st_nlink > 1):
            raise ValueError("Output must be an unaliased regular file")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _file_version(path):
    """Read the executable's fixed Windows version resource, without launching."""
    if os.name != "nt":
        return None
    from ctypes import wintypes
    class FixedInfo(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in (
            "signature", "structure", "file_ms", "file_ls", "product_ms",
            "product_ls", "flags_mask", "flags", "os", "type", "subtype",
            "date_ms", "date_ls")]
    dll = ctypes.WinDLL("version", use_last_error=True)
    dll.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    dll.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    dll.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    dll.GetFileVersionInfoW.restype = wintypes.BOOL
    dll.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                  ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    dll.VerQueryValueW.restype = wintypes.BOOL
    ignored = wintypes.DWORD()
    size = dll.GetFileVersionInfoSizeW(str(path), ctypes.byref(ignored))
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not dll.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not dll.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return None
    if length.value < ctypes.sizeof(FixedInfo):
        return None
    info = ctypes.cast(pointer, ctypes.POINTER(FixedInfo)).contents
    if info.signature != 0xFEEF04BD:
        return None
    return ".".join(str(value) for value in
                    (info.file_ms >> 16, info.file_ms & 65535,
                     info.file_ls >> 16, info.file_ls & 65535))


def _unwrap(value):
    if value.startswith("@ByteArray(") and value.endswith(")"):
        value = value[11:-1]
    return value.replace("\\\\", "\\")


def _manifest(snapshot):
    state, raw = snapshot.read(_path(MANIFEST), content=True)
    value = _json(raw) if raw is not None else None
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("lab-manifest.json requires version 1")
    if value.get("paid_generation") is not False:
        raise ValueError("The baseline lab must explicitly disable paid generation")
    for key, expected in (("runtime", "Game/SkyrimSE.exe"),
                          ("loader", "Game/skse64_loader.exe"),
                          ("mo2", "MO2/ModOrganizer.exe")):
        row = value.get(key)
        if (not isinstance(row, dict) or row.get("path") != expected
                or not isinstance(row.get("sha256"), str) or not SHA.fullmatch(row["sha256"])):
            raise ValueError("Invalid fixed executable declaration: " + key)
    if value["runtime"].get("version") != RUNTIME_VERSION or value["mo2"].get("profile") != PROFILE:
        raise ValueError("The manifest must select SE 1.6.1170.0 and the fixed lab profile")
    for key in ("required_mods", "required_plugins"):
        rows = value.get(key)
        if (not isinstance(rows, list) or not rows or any(not isinstance(item, str) for item in rows)
                or len({item.casefold() for item in rows}) != len(rows)):
            raise ValueError(key + " requires unique names")
        for item in rows:
            _component(item)
    files = value.get("files")
    if not isinstance(files, list):
        raise ValueError("Manifest files must be a list of expected physical hashes")
    seen = set()
    for row in files:
        if (not isinstance(row, dict) or not isinstance(row.get("sha256"), str)
                or not SHA.fullmatch(row["sha256"])):
            raise ValueError("Invalid manifest file hash")
        relative = _relative(row.get("path"))
        if relative.casefold() in seen or relative.split("/")[0] not in ("Game", "MO2", "Documents"):
            raise ValueError("Invalid or duplicate manifest file path")
        seen.add(relative.casefold())
    logs = value.get("logs")
    if not isinstance(logs, list) or not logs:
        raise ValueError("Manifest logs must list the lab-local evidence sources")
    ids, paths = set(), set()
    for row in logs:
        if not isinstance(row, dict) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", row.get("id", "")):
            raise ValueError("Invalid evidence log id")
        relative = _relative(row.get("path"))
        if (relative.split("/")[0] not in ("Game", "MO2", "Documents")
                or row["id"] in ids or relative.casefold() in paths
                or type(row.get("required", False)) is not bool):
            raise ValueError("Invalid or duplicate evidence log path")
        if "run_id_field" in row and not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", row["run_id_field"]):
            raise ValueError("Invalid JSON run-id field")
        ids.add(row["id"])
        paths.add(relative.casefold())
    if not any(row.get("required") and row.get("run_id_field") for row in logs):
        raise ValueError("At least one required JSON result must echo the run_id")
    return value, state


def preflight():
    """Inspect only the fixed lab; a successful report is not a runtime result."""
    root, observed = _root(), _Snapshot()
    manifest, manifest_state = _manifest(observed)
    checks = []
    def check(code, passed, detail, **extra):
        checks.append(dict(code=code, passed=passed is True, detail=detail, **extra))

    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    expected.update({manifest[key]["path"]: manifest[key]["sha256"] for key in ("runtime", "loader", "mo2")})
    for relative, digest in expected.items():
        state = observed.read(_path(relative))
        check("file_hash", state.get("sha256") == digest, "Required physical input hash", path=relative)
    version = _file_version(_path("Game/SkyrimSE.exe"))
    check("runtime_version", version == RUNTIME_VERSION, "Windows executable version must be 1.6.1170.0",
          actual=version)
    observed.read(_path("Game/SkyrimSE.exe"))
    portable = observed.read(_path("MO2/portable.txt"))
    check("portable_instance", portable["exists"], "An isolated portable MO2 instance is required")
    _, raw_ini = observed.read(_path("MO2/ModOrganizer.ini"), content=True)
    config = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        config.read_string(_profile_text(raw_ini or b""))
        game = _unwrap(config.get("General", "gamePath"))
        selected = _unwrap(config.get("General", "selected_profile"))
        game_matches = os.path.normcase(os.path.normpath(game)) == os.path.normcase(str(root / "Game"))
        check("mo2_game_path", game_matches, "MO2 must point to the isolated Game directory")
        check("mo2_profile", selected == PROFILE, "MO2 selected profile must match the lab")
        check("mo2_game_name", config.get("General", "gameName") == "Skyrim Special Edition",
              "MO2 game must be Skyrim Special Edition")
        # These overrides can redirect reads/writes out of a portable instance.
        directory_keys = {"base_directory": "", "download_directory": "downloads",
                          "downloads_directory": "downloads", "mod_directory": "mods",
                          "mods_directory": "mods", "profiles_directory": "profiles",
                          "overwrite_directory": "overwrite", "cache_directory": "webcache"}
        for section in config.sections():
            for key, value in config.items(section):
                if key not in directory_keys or not value.strip():
                    continue
                value = _unwrap(value).replace("%BASE_DIR%", str(root / "MO2"))
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = root / "MO2" / candidate
                normalized = Path(os.path.abspath(candidate))
                expected_path = root / "MO2" / directory_keys[key]
                matches = os.path.normcase(str(normalized)) == os.path.normcase(str(expected_path))
                check("mo2_directory", matches,
                      "Explicit MO2 directories must match the exact audited lab directories", key=key)
                if matches:
                    _no_alias(normalized)
    except (configparser.Error, UnicodeError, ValueError):
        check("mo2_ini", False, "Cannot establish isolated MO2 configuration")

    profile_relative = "MO2/profiles/" + PROFILE
    _, settings_raw = observed.read(_path(profile_relative + "/settings.ini"), content=True)
    try:
        settings = configparser.ConfigParser(interpolation=None, strict=True)
        settings.read_string(_profile_text(settings_raw or b""))
        local = (settings.getboolean("General", "LocalSaves") is True
                 and settings.getboolean("General", "LocalSettings") is True)
        check("profile_local_state", local, "Profile-local saves and INI settings must both be enabled")
    except (configparser.Error, UnicodeError, ValueError):
        check("profile_local_state", False, "Cannot establish profile-local saves and INI settings")
    for name in ("Skyrim.ini", "SkyrimPrefs.ini"):
        state = observed.read(_path(profile_relative + "/" + name))
        check("profile_ini", state["exists"], "The selected profile must contain its local game INI", file=name)
    observed.read(_path(profile_relative + "/SkyrimCustom.ini"))
    _, mod_raw = observed.read(_path(profile_relative + "/modlist.txt"), content=True)
    _, plugin_raw = observed.read(_path(profile_relative + "/plugins.txt"), content=True)
    observed.read(_path(profile_relative + "/loadorder.txt"))
    active, enabled, seen = [], [], set()
    for line in _profile_text(mod_raw or b"").splitlines():
        if not line.strip() or line.startswith("#") or re.fullmatch(r"\*(DLC|Creation Club|Unmanaged): .+", line):
            continue
        if line[0] not in "+-":
            check("modlist", False, "Malformed modlist entry")
            continue
        name = _component(line[1:])
        check("modlist_unique", name.casefold() not in seen, "Mod entries must be unique")
        seen.add(name.casefold())
        if line[0] == "+":
            active.append(name)
    for line in _profile_text(plugin_raw or b"").splitlines():
        if line.startswith("*"):
            enabled.append(_component(line[1:]))
    check("plugins_unique", len(enabled) == len({name.casefold() for name in enabled}),
          "Enabled plugin entries must be unique")
    check("required_mods", {name.casefold() for name in manifest["required_mods"]} <=
          {name.casefold() for name in active}, "Required lab mods must be enabled")
    check("required_plugins", {name.casefold() for name in manifest["required_plugins"]} <=
          {name.casefold() for name in enabled}, "Required lab plugins must be enabled")
    layers = [_path("MO2/overwrite")]
    for name in active:
        directory = _path("MO2/mods/" + name)
        state, _ = observed.directory(directory)
        check("active_mod_exists", state["exists"], "An enabled mod directory must exist", mod=name)
        layers.append(directory)
    layers.append(_path("Game/Data"))

    def winner(relative):
        found = None
        for layer in layers:
            path, exists = observed.resolve(layer, relative)
            state = observed.read(path) if exists else {"path": str(path), "exists": False}
            if found is None and state["exists"]:
                found = state
        return found

    for name in manifest["required_plugins"]:
        current = winner(name)
        relative = str(Path(current["path"]).relative_to(root).as_posix()) if current else None
        check("plugin_winner_hash", bool(current and expected.get(relative) == current.get("sha256")),
              "Required plugin's actual loose winner must have a declared matching hash", plugin=name)
    active_keys = {name.casefold() for name in active}
    for relative, digest in expected.items():
        parts = relative.split("/")
        virtual = None
        if len(parts) > 3 and parts[:2] == ["MO2", "mods"] and parts[2].casefold() in active_keys:
            virtual = "/".join(parts[3:])
        elif len(parts) > 2 and parts[:2] == ["Game", "Data"]:
            virtual = "/".join(parts[2:])
        if virtual:
            current = winner(virtual)
            check("declared_virtual_winner", bool(current and current.get("sha256") == digest),
                  "A declared active Data input must remain the actual loose winner", virtual_path=virtual)
    check("skyrimnet_disabled", winner("SKSE/Plugins/SkyrimNet.dll") is None,
          "The first-tier offline lab must not load SkyrimNet")
    control = winner(CONTROL)
    try:
        control_path = Path(control["path"]) if control else None
        _, control_raw = observed.read(control_path, content=True) if control_path else (None, None)
        value = _json(control_raw) if control_raw else None
        valid = (isinstance(value, dict) and type(value.get("version")) is int and value["version"] == 1
                 and value.get("enabled") is True and value.get("world_id") == "hold-music-se-lab")
        check("lab_control", valid, "The isolated harness control must be explicitly enabled")
    except (OSError, ValueError, UnicodeError):
        check("lab_control", False, "Cannot establish the isolated harness control")
    snapshot = observed.finish()
    report = dict(version=1, operation="se_lab_preflight", lab_root=str(root), profile=PROFILE,
                  runtime_version=version, manifest=manifest_state, checks=checks,
                  status="ready_for_explicit_launch" if all(row["passed"] for row in checks) else "blocked",
                  launch_command=[str(_path("MO2/ModOrganizer.exe")), "-i", "", "-p", PROFILE,
                                  "--logs", "run", "--cwd", str(_path("Game")),
                                  str(_path("Game/skse64_loader.exe"))],
                  logs=manifest["logs"], snapshot=snapshot, writes_performed=False,
                  runtime_verified=False, paid_generation=False,
                  limitations=["This verifies prepared loose files, not MO2 injection or successful gameplay.",
                               "Launch and arm are explicit actions; preflight never launches or writes.",
                               "The baseline profile excludes SkyrimNet and all provider generation."])
    report["review_token"] = _digest(report)
    return report


def _review(token):
    report = preflight()
    if report["status"] == "blocked":
        raise ValueError("Lab preflight is blocked; inspect the failed checks")
    if not isinstance(token, str) or not token.isascii() or not hmac.compare_digest(token, report["review_token"]):
        raise ValueError("A matching fresh preflight review token is required")
    return report


def _closed():
    value = default_process_probe()
    if not (isinstance(value, dict) and value.get("verified") is True
            and value.get("quiescent") is True and value.get("processes") == []):
        raise ValueError("Close all Skyrim and MO2 processes before a lab launch; none will be terminated")


def _recheck_inputs(report):
    current = preflight()
    # Creating a run/request changes expected output-directory inventories.
    # Revalidate winners and all input bytes instead of accepting an old token.
    if (current["status"] == "blocked" or current["checks"] != report["checks"]
            or current["snapshot"]["files"] != report["snapshot"]["files"]):
        raise ValueError("Lab inputs changed while preparing the run")


def _scenario(value):
    if value is not None and (not isinstance(value, str) or value not in SCENARIOS):
        raise ValueError("Scenario must be ambient-entry, focused-complete or focused-interrupt")
    return value


def _prepare_run(report, mode, scenario=None):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    directory = _path("runs/" + run_id)
    _no_alias(directory.parent).mkdir(parents=True, exist_ok=True)
    directory.mkdir()
    observed = _Snapshot()
    logs = [dict(row, before=observed.read(_path(row["path"]))) for row in report["logs"]]
    observed.finish()
    started_ns = time.time_ns()
    started = datetime.fromtimestamp(started_ns / 1e9, timezone.utc).isoformat()
    run = dict(version=1, run_id=run_id, mode=mode, started_at_utc=started,
               started_ns=started_ns, review_token=report["review_token"],
               launch_command=report["launch_command"], logs=logs,
               scenario=scenario,
               runtime_verified=False, paid_generation=False)
    request = dict(version=1, run_id=run_id, started_at_utc=started)
    if scenario is not None:
        request.update(auto_run=True, scenario=scenario)
    _atomic_json(directory / "preflight.json", report)
    _atomic_json(directory / "run.json", run)
    previous = _path(REQUEST)
    if previous.exists():
        _, raw = _Snapshot().read(previous, content=True)
        _write_new(directory / "previous-request.json", raw)
    _recheck_inputs(report)
    _atomic_json(previous, request)
    run["request_published"] = True
    _atomic_json(directory / "run.json", run)
    return run, directory


def arm(review_token, *, scenario=None):
    """Create a fresh nonce/baseline for a scenario in an already-open lab."""
    _scenario(scenario)
    with _writer_lock(_path(".se-lab-writer.lock")):
        report = _review(review_token)
        run, directory = _prepare_run(report, "arm", scenario)
    return dict(status="armed", run_id=run["run_id"], directory=str(directory),
                request=str(_path(REQUEST)), scenario=scenario,
                process_started=False, runtime_verified=False)


def _require_windows():
    if os.name != "nt":
        raise ValueError("Real SE lab launch requires Windows")


def launch(review_token, *, timeout_seconds=30, scenario=None):
    """Launch only through this portable MO2; timeout never kills any process."""
    _scenario(scenario)
    _require_windows()
    if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 60:
        raise ValueError("Launch timeout must be between 1 and 60 seconds")
    with _writer_lock(_path(".se-lab-writer.lock")):
        report = _review(review_token)
        _closed()
        run, directory = _prepare_run(report, "launch", scenario)
        result = dict(status="launch_pending", run_id=run["run_id"], directory=str(directory),
                      scenario=scenario,
                      process_started=False, runtime_verified=False, processes_terminated=False)
        _atomic_json(directory / "launch-result.json", result)
        # Explicit launch is the only subprocess execution in this module.
        try:
            _closed()
            with (directory / "launcher-output.log").open("xb") as output:
                process = subprocess.Popen(report["launch_command"], cwd=str(_path("MO2")),
                                           stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                           shell=False)
                result.update(status="launched", process_started=True, launcher_pid=process.pid)
                _atomic_json(directory / "launch-result.json", result)
                try:
                    result.update(status="launcher_exited", launcher_returncode=process.wait(timeout=timeout_seconds))
                except subprocess.TimeoutExpired:
                    result.update(status="launcher_wait_timeout", launcher_returncode=None)
        except OSError as exc:
            result.update(status="launch_failed", error_type=type(exc).__name__)
        _atomic_json(directory / "launch-result.json", result)
        return result


def collect(run_id):
    """Archive observed changed logs; only echoed nonces correlate JSON results."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid lab run id")
    directory = _path("runs/" + run_id)
    observed = _Snapshot()
    _, raw = observed.read(directory / "run.json", content=True)
    run = _json(raw) if raw else None
    if (not isinstance(run, dict) or type(run.get("version")) is not int
            or run["version"] != 1 or run.get("run_id") != run_id
            or run.get("mode") not in ("arm", "launch") or type(run.get("started_ns")) is not int
            or run["started_ns"] <= 0 or run.get("request_published") is not True
            or not isinstance(run.get("started_at_utc"), str) or not run["started_at_utc"]
            or not isinstance(run.get("logs"), list)):
        raise ValueError("Invalid saved run baseline")
    _scenario(run.get("scenario"))
    if run["mode"] == "launch":
        _, result_raw = observed.read(directory / "launch-result.json", content=True)
        result = _json(result_raw) if result_raw else None
        if not isinstance(result, dict) or result.get("process_started") is not True:
            raise ValueError("This run has no confirmed launcher process start")
    capture_id = uuid.uuid4().hex
    capture = directory / "captures" / capture_id
    records, payloads, seen = [], {}, set()
    for spec in run["logs"]:
        if (not isinstance(spec, dict) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", spec.get("id", ""))
                or spec["id"] in seen or type(spec.get("required", False)) is not bool
                or not isinstance(spec.get("before"), dict)):
            raise ValueError("Invalid saved evidence source")
        seen.add(spec["id"])
        path = _path(spec["path"])
        if spec["path"].split("/")[0] not in ("MO2", "Game", "Documents"):
            raise ValueError("Saved evidence source is outside lab output namespaces")
        state, raw = observed.read(path, content=True)
        before = spec["before"]
        changed = bool(state["exists"] and state.get("sha256") != before.get("sha256"))
        recent = bool(state["exists"] and state["mtime_ns"] >= run["started_ns"])
        nonce_matches = None
        timestamp_matches = None
        scenario_matches = None
        if spec.get("run_id_field"):
            try:
                document = _json(raw) if raw else None
                nonce_matches = isinstance(document, dict) and document.get(spec["run_id_field"]) == run_id
                timestamp_matches = (isinstance(document, dict)
                                     and document.get("started_at_utc") == run["started_at_utc"])
                if run.get("scenario") is not None:
                    scenario_matches = (isinstance(document, dict)
                                        and document.get("scenario") == SCENARIO_RESULTS[run["scenario"]])
            except (ValueError, UnicodeError):
                nonce_matches = False
                timestamp_matches = False
                if run.get("scenario") is not None:
                    scenario_matches = False
        fresh = (changed and recent and nonce_matches is not False
                 and timestamp_matches is not False and scenario_matches is not False)
        row = dict(id=spec["id"], source=spec["path"], required=spec.get("required", False),
                   before=before, after=state, content_changed=changed, written_after_start=recent,
                   run_id_matches=nonce_matches, request_timestamp_matches=timestamp_matches,
                   scenario_matches=scenario_matches, fresh=fresh, archived_file=None)
        if raw is not None:
            relative = "logs/" + spec["id"] + ".bin"
            payloads[relative] = raw
            row["archived_file"] = relative
        records.append(row)
    observed.finish()
    required = [row for row in records if row["required"]]
    complete = bool(required and all(row["fresh"] for row in required)
                    and any(row["required"] and row["run_id_matches"] is True for row in records))
    report = dict(version=1, status="evidence_collected" if complete else "incomplete_evidence",
                  run_id=run_id, scenario=run.get("scenario"),
                  expected_result_scenario=SCENARIO_RESULTS.get(run.get("scenario")),
                  capture_id=capture_id, directory=str(capture), logs=records,
                  fresh_required_evidence=complete, runtime_verified=False, paid_generation=False,
                  limitations=["Fresh evidence is not a passing scenario or proof of VFS write ownership.",
                               "Unchanged/touched old files and mismatched run IDs never count as fresh.",
                               "Launcher exit/timeout is not a game outcome; no process is terminated."])
    _no_alias(capture.parent).mkdir(parents=True, exist_ok=True)
    capture.mkdir()
    for relative, raw in payloads.items():
        target = _no_alias(capture / relative)
        _write_new(target, raw)
        if hashlib.sha256(target.read_bytes()).hexdigest() != hashlib.sha256(raw).hexdigest():
            raise ValueError("Evidence archive verification failed")
    observed.finish()
    _atomic_json(capture / "evidence.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    for name in ("launch", "arm"):
        command = commands.add_parser(name)
        command.add_argument("--review-token", required=True)
        command.add_argument("--scenario", choices=SCENARIOS)
        if name == "launch":
            command.add_argument("--timeout-seconds", type=float, default=30)
    command = commands.add_parser("collect")
    command.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight()
        elif args.command == "launch":
            result = launch(args.review_token, timeout_seconds=args.timeout_seconds, scenario=args.scenario)
        elif args.command == "arm":
            result = arm(args.review_token, scenario=args.scenario)
        else:
            result = collect(args.run_id)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        parser.exit(1, "Cannot operate SE lab: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if result["status"] in ("blocked", "launch_failed", "incomplete_evidence") else 0


if __name__ == "__main__":
    raise SystemExit(main())
