"""Bounded read-only HTTP observation of the already attributed disabled SE tier.

No launch, credentials, provider/MCP request, configuration update or raw payload
export. Native module correspondence is deliberately strict: a virtual pathname
that cannot be matched to a pinned physical module remains unverified.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid

from hold_music import se_lab_skyrimnet as tier

VERSION = 1
HOST = "127.0.0.1"
PORT = 18880
MAX_BODY = 512 * 1024
MAX_HEADERS = 16 * 1024
TOTAL_SECONDS = 60.0
# Exactly these scalar values may reach an output. Never inherit UI defaults.
CHECKS = {
    "game": {"general.globalAIEnabled": False, "gamemaster.agentEnabled": False,
        "narration.enabled": False, "tts.engine": "noop", "content.autoUpdateBase": False,
        "dialogue.decisions.useForMood": False, "dialogue.decisions.useForSpeakerSelection": False,
        "dialogue.decisions.useForPlayerTarget": False},
    "STT": {"backend": "none"},
    "BardSinging": {"bard_singing.enabled": False, "bard_singing.backup_provider": "none"},
    "VastAI": {"general.enabled": False},
    "Events": {"global.npcReactionsEnabled": False},
    "PlayerDialogue": {"enabled": False},
    "Memory": {"performance.enable_background_processing": False},
    "DynamicBio": {"enabled": False}, "UniversalTranslator": {"enabled": False},
    "OmniSight": {"omnisight.enabled": False}, "Agents": {"agents.enable": False},
    "WebServer": {"enabled": True, "host": HOST, "port": PORT},
    "mcp": {"mcp.enabled": True, "mcp.host": HOST, "mcp.port": 18889},
}
ROUTES = tuple("/config?api=get&name=" + name for name in CHECKS)


def _json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Invalid bounded JSON response") from None


def _powershell(command):
    if os.name != "nt":
        raise ValueError("Live smoke observation requires Windows")
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=8, check=True)
        if len(result.stdout) > 1024 * 1024:
            raise ValueError("Observation exceeded its bound")
        rows = _json(result.stdout.lstrip(b"\xef\xbb\xbf"))
        if not isinstance(rows, list):
            raise ValueError("Malformed observation")
        return rows
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ValueError("Windows identity observation unavailable") from None


def _modules(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("Invalid observed PID")
    names = ",".join("'" + name + "'" for name in sorted(tier.NATIVE_DLLS))
    return _powershell("$ErrorActionPreference='Stop'; $names=@(" + names + "); "
        "$rows=@((Get-Process -Id " + str(pid) + ").Modules | Where-Object "
        "{ $names -contains $_.ModuleName } | ForEach-Object "
        "{ [pscustomobject]@{name=$_.ModuleName;path=$_.FileName} }); "
        "ConvertTo-Json -Compress -InputObject $rows")


def _connections():
    return _powershell("$ErrorActionPreference='Stop'; $rows=@(Get-NetTCPConnection | "
        "Where-Object { $_.LocalPort -in @(18880,18889) } | ForEach-Object { "
        "[pscustomobject]@{local_address=$_.LocalAddress;local_port=[int]$_.LocalPort;"
        "remote_address=$_.RemoteAddress;remote_port=[int]$_.RemotePort;"
        "state=$_.State.ToString();pid=[int]$_.OwningProcess} }); "
        "ConvertTo-Json -Compress -InputObject $rows")


def _listeners(rows, pid):
    keys = {"local_address", "local_port", "remote_address", "remote_port", "state", "pid"}
    if (not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != keys
            or any(type(row[k]) is not int for k in ("local_port", "remote_port", "pid"))
            or any(not isinstance(row[k], str) for k in ("local_address", "remote_address", "state"))
            or not 0 <= row["local_port"] <= 65535 or not 0 <= row["remote_port"] <= 65535
            or row["pid"] < 0 for row in rows)):
        raise ValueError("Malformed listener observation")
    selected = []
    for port in (PORT, 18889):
        matching = [row for row in rows if isinstance(row, dict)
                    and row.get("local_port") == port and row.get("state") == "Listen"]
        if (len(matching) != 1 or matching[0].get("local_address") != HOST
                or type(matching[0].get("pid")) is not int or matching[0]["pid"] != pid):
            raise ValueError("Expected exact owned loopback listeners")
        selected.append(dict(address=HOST, port=port, pid=pid))
    return selected


def _live(run, launched, process_probe):
    _, game = tier._process_history(process_probe(), launched["processes"], tier._root(),
                                   run["started_ns"], launched["launcher_pid"])
    if game is None or game != launched.get("game") or launched.get("launch_attributed") is not True:
        raise ValueError("Exact attributed game process is not live")
    return game


def _context(run_id, process_probe, module_probe, connection_probe):
    if not isinstance(run_id, str) or not tier.baseline.RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid first-boot run ID")
    root = tier._root()
    runtime = tier._fixed(root, tier.RUNTIME_CONTROL)
    snapshot = tier._Snapshot()
    run, run_state = tier._document(snapshot, runtime / "run.json")
    launched, launched_state = tier._document(snapshot, runtime / "launch-result.json")
    if (run.get("version") != 1 or run.get("tier") != tier.TIER or run.get("run_id") != run_id
            or run.get("operation") != "skyrimnet_disabled_first_boot"
            or run.get("launch_command") != tier._runtime_command(root)
            or not isinstance(run.get("inputs"), dict) or tier._digest(run["inputs"]) != run.get("inputs_sha256")
            or launched.get("tier") != tier.TIER or launched.get("run_id") != run_id
            or launched.get("process_started") is not True or type(launched.get("launcher_pid")) is not int
            or not isinstance(launched.get("processes"), list)):
        raise ValueError("Invalid retained attributed launch")
    if tier._implementation(snapshot) != run["inputs"].get("implementation"):
        raise ValueError("Frozen launch implementation changed")
    protected = tier._protected(root)
    if protected != run["inputs"].get("protected"):
        raise ValueError("Protected baseline or Game changed")
    game = _live(run, launched, process_probe)
    files = run["inputs"].get("instance", {}).get("files")
    if not isinstance(files, dict):
        raise ValueError("Missing pinned module inventory")
    expected = {}
    for relative, row in files.items():
        relative = tier._relative(relative)
        parts = Path(relative).parts
        name = parts[-1].casefold()
        if name in tier.NATIVE_DLLS:
            if (len(parts) != 5 or parts[0] != "mods" or parts[2:4] != ("SKSE", "Plugins")
                    or name in expected or not isinstance(row, dict)
                    or not isinstance(row.get("sha256"), str)):
                raise ValueError("Ambiguous pinned native module")
            path = tier._no_alias(root / tier.INSTANCE / relative)
            current = snapshot.read(path)
            if not current.get("exists") or current.get("sha256") != row["sha256"]:
                raise ValueError("Pinned native module changed")
            expected[name] = dict(path=str(path), sha256=row["sha256"])
    if set(expected) != tier.NATIVE_DLLS:
        raise ValueError("Incomplete pinned native module set")
    modules = module_probe(game["pid"])
    if not isinstance(modules, list) or len(modules) != len(expected):
        raise ValueError("Expected native modules are not all observed")
    seen = set()
    for row in modules:
        if not isinstance(row, dict) or set(row) != {"name", "path"} or not isinstance(row["name"], str):
            raise ValueError("Malformed native module observation")
        name = row["name"].casefold()
        if (name not in expected or name in seen or not isinstance(row["path"], str)
                or os.path.normcase(row["path"]) != os.path.normcase(expected[name]["path"])):
            raise ValueError("Native module physical path is unverified")
        seen.add(name)
    listeners = _listeners(connection_probe(), game["pid"])
    if _live(run, launched, process_probe) != game:
        raise ValueError("Game process changed during observation")
    snapshot.finish()
    implementation = {str(path.relative_to(tier.REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__), tier.REPO / "tools/se_lab_skyrimnet_smoke.py")}
    binding = dict(version=VERSION, tier=tier.TIER, run_id=run_id, game=game,
        run_sha256=run_state["sha256"], launch_sha256=launched_state["sha256"],
        modules=expected, listeners=listeners, routes=list(ROUTES), implementation=implementation)
    return binding, run, launched


def smoke_plan(run_id, *, process_probe=None, module_probe=None, connection_probe=None):
    binding, _, _ = _context(run_id, process_probe or tier._runtime_process_snapshot,
                             module_probe or _modules, connection_probe or _connections)
    return dict(version=VERSION, operation="skyrimnet_smoke_plan", status="ready_for_bounded_get",
        binding=binding, review_token="skyrimnet-smoke-v1:" + tier._digest(binding),
        network_requests_performed=False, writes_performed=False, runtime_verified=False,
        egress_verified=False, paid_generation=False)


def _verify_connection(rows, pid, local_port):
    _listeners(rows, pid)
    matching = [row for row in rows if row.get("local_address") == HOST and row.get("local_port") == PORT
                and row.get("remote_address") == HOST and row.get("remote_port") == local_port
                and row.get("state") == "Established"]
    if len(matching) != 1 or type(matching[0].get("pid")) is not int or matching[0]["pid"] != pid:
        raise ValueError("Connected HTTP peer is not the attributed game")


def _http_get(route, pid, deadline, verify_live, connection_probe):
    if route not in ROUTES:
        raise ValueError("HTTP route is not allowlisted")
    end = min(deadline, time.monotonic() + 4.0)
    def remaining():
        value = end - time.monotonic()
        if value <= 0:
            raise ValueError("Bounded HTTP observation timed out")
        return value
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stream:
        stream.settimeout(remaining())
        stream.connect((HOST, PORT))
        verify_live()
        # Pin the accepted server-side connection, not just its listening port.
        _verify_connection(connection_probe(), pid, stream.getsockname()[1])
        stream.settimeout(remaining())
        stream.sendall(("GET " + route + " HTTP/1.1\r\nHost: 127.0.0.1:18880\r\n"
            "Accept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n").encode("ascii"))
        raw = b""
        while b"\r\n\r\n" not in raw:
            stream.settimeout(remaining())
            chunk = stream.recv(4096)
            if not chunk:
                raise ValueError("Incomplete HTTP headers")
            raw += chunk
            if len(raw.split(b"\r\n\r\n", 1)[0]) > MAX_HEADERS:
                raise ValueError("HTTP headers exceeded bound")
        header, body = raw.split(b"\r\n\r\n", 1)
        try:
            lines = header.decode("ascii").split("\r\n")
            if lines[0].split(" ", 2)[:2] != ["HTTP/1.1", "200"]:
                raise ValueError("HTTP status is not 200")
            headers = {}
            for line in lines[1:]:
                key, value = line.split(":", 1)
                key = key.casefold()
                if key in headers:
                    raise ValueError("Duplicate HTTP header")
                headers[key] = value.strip()
            size = headers.get("content-length", "")
            if (not size.isascii() or not size.isdecimal() or int(size) > MAX_BODY
                    or "transfer-encoding" in headers or headers.get("content-encoding", "identity") != "identity"
                    or headers.get("content-type", "").split(";", 1)[0].strip() != "application/json"):
                raise ValueError("Unsupported bounded JSON response framing")
            size = int(size)
        except (ValueError, UnicodeError):
            raise ValueError("Invalid bounded HTTP response") from None
        while len(body) < size:
            stream.settimeout(remaining())
            chunk = stream.recv(min(4096, size - len(body)))
            if not chunk:
                raise ValueError("Incomplete HTTP body")
            body += chunk
        if len(body) != size:
            raise ValueError("Unexpected HTTP body length")
        verify_live()
        _listeners(connection_probe(), pid)
        return body


def _project(name, raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BODY:
        raise ValueError("Config response exceeded bound")
    value = _json(raw)
    if not isinstance(value, dict) or "error" in value or not isinstance(value.get("data"), dict):
        raise ValueError("Config response envelope is invalid")
    checks = []
    for path, expected in CHECKS[name].items():
        actual = value["data"]
        for key in path.split("."):
            actual = actual.get(key) if isinstance(actual, dict) else None
        valid_type = type(actual) is type(expected)
        # Never export an unexpected value: it could be private text.
        checks.append(dict(path=path, expected=expected, present=actual is not None,
            type_matches=valid_type, matches=valid_type and actual == expected))
    return dict(name=name, checks=checks, all_match=all(row["matches"] for row in checks),
                response_bytes=len(raw))


def collect_smoke(run_id, review_token, *, process_probe=None, module_probe=None,
                  connection_probe=None, transport=None):
    process_probe = process_probe or tier._runtime_process_snapshot
    module_probe, connection_probe = module_probe or _modules, connection_probe or _connections
    transport = transport or _http_get
    root = tier._root()
    with tier._writer_lock(tier._no_alias(root / ".se-lab-writer.lock")), tier._writer_lock(tier._no_alias(root / tier.CONTROL / "writer.lock")):
        binding, run, launched = _context(run_id, process_probe, module_probe, connection_probe)
        token = "skyrimnet-smoke-v1:" + tier._digest(binding)
        if not tier._matches(review_token, token):
            raise ValueError("Smoke review is stale or belongs to another operation")
        deadline = time.monotonic() + TOTAL_SECONDS
        observations = []
        def live():
            if time.monotonic() >= deadline or _live(run, launched, process_probe) != binding["game"]:
                raise ValueError("Live observation identity or deadline changed")
        failure = None
        for name, route in zip(CHECKS, ROUTES):
            try:
                live()
                raw = transport(route, binding["game"]["pid"], deadline, live, connection_probe)
                observations.append(_project(name, raw))
                live()
            except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
                failure = "bounded_observation_failed"
                break
        try:
            after, _, _ = _context(run_id, process_probe, module_probe, connection_probe)
            stable = after == binding
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
            stable = False
        complete = failure is None and stable and len(observations) == len(CHECKS)
        passed = complete and all(row["all_match"] for row in observations)
        report = dict(version=VERSION, tier=tier.TIER, operation="skyrimnet_smoke_capture", run_id=run_id,
            capture_id=uuid.uuid4().hex, status="disabled_controls_observed" if passed else "incomplete_or_mismatched",
            binding=binding, binding_sha256=tier._digest(binding), observations=observations,
            observation_failure=failure, live_snapshot_complete=complete, identity_stable=stable,
            native_module_paths_and_hashes_observed=stable, config_get_service_observed=bool(observations),
            disabled_controls_observed=passed, all_native_initialization_verified=False,
            credentials_verified=False, effective_provider_routing_verified=False, vfs_verified=False,
            runtime_verified=False, egress_verified=False, paid_generation=False,
            network_requests_attempted=True, network_requests_performed=True if observations else None,
            writes_performed=True,
            limitations=["Only fixed config GETs and seven loaded module path/hash correspondences are observed.",
                "No authentication, provider, MCP, settings writes, raw payloads or logs were requested/exported.",
                "Loaded module paths do not prove every native subsystem initialized or no other native module loaded.",
                "Disabled readbacks are not evidence of zero egress, billing-credential absence or playback readiness."])
        directory = tier._no_alias(root / tier.RUNTIME_CONTROL / "smoke")
        directory.mkdir(exist_ok=True)
        tier._runtime_json(directory / (report["capture_id"] + ".json"), report, new=True)
        return report
