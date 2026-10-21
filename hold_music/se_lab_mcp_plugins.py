"""One explicitly reviewed get_plugins query; no generic MCP dispatch surface.

The pinned native handler enumerates/caches loaded filenames and may log. This
is a game-state inspection, not a claim that the server performs no writes.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import time
import uuid

from hold_music import se_lab_mcp_discovery as discovery

smoke, tier = discovery.smoke, discovery.tier
VERSION = 1
TOOL = "get_plugins"
METHODS = (*discovery.METHODS, "tools/call")
TOTAL_SECONDS = 60.0
MAX_PLUGINS = 4096
MAX_TEXT = 256 * 1024
FILENAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9 _().+'-]{0,249}\.(?:esm|esp|esl)\Z", re.I)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MO2_PLUGIN_HEADER = (b"# This file is used by Skyrim to keep track of your downloaded content.\n"
                     b"# Please do not modify this file.\n")
SOURCE_BASIS = {
    "dll_sha256": "2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a",
    "contract": "beta26-rc4-get-plugins-text-array-v1",
    "handler_rva": "0xcf62e0", "dispatch_rva": "0x1463cf0",
    "native_source_available": False, "static_disassembly_reviewed": True,
}
STAGES = discovery.DIAGNOSTIC_STAGES | frozenset((
    "discovery_capture", "fresh_schema", "plugins_post", "plugins_result",
    "plugins_validation", "post_query_identity", "plugins_transport"))
REASONS = discovery.DIAGNOSTIC_REASONS | {"game_not_ready"}


class _Failure(ValueError):
    def __init__(self, stage, reason="validation_or_probe_failure", http_status=None):
        self.stage = stage if stage in STAGES else "plugins_transport"
        self.reason = reason if reason in REASONS else "validation_or_probe_failure"
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        super().__init__("Bounded plugin inspection failed")


@contextmanager
def _stage(name):
    try:
        yield
    except _Failure:
        raise
    except (discovery._DiscoveryFailure, discovery._WireFailure) as error:
        raise _Failure(getattr(error, "stage", name), error.reason, error.http_status) from None
    except discovery.FAILURES:
        raise _Failure(name) from None


def _messages():
    return (*discovery._messages(), {"jsonrpc": "2.0", "id": 3,
        "method": "tools/call", "params": {"name": TOOL, "arguments": {}}})


def _empty_arguments_schema(schema):
    """Admit only a small, understood object-schema subset that accepts {}.

    Do not infer safety from an empty required list while ignoring allOf,
    dependentSchemas, const, enum, references, or other validation keywords.
    """
    allowed = {"type", "properties", "required", "additionalProperties", "title", "description"}
    if (not isinstance(schema, dict) or not set(schema) <= allowed
            or schema.get("type") != "object"
            or schema.get("properties", {}) != {} or type(schema.get("properties", {})) is not dict
            or schema.get("required", []) != [] or type(schema.get("required", [])) is not list
            or type(schema.get("additionalProperties", True)) is not bool
            or any(key in schema and (not isinstance(schema[key], str) or len(schema[key]) > 4096)
                   for key in ("title", "description"))):
        raise ValueError("The reviewed empty-argument schema is unsupported")
    return discovery._schema_summary(schema)


def _capture(path, binding, snapshot):
    path = tier._no_alias(Path(os.path.abspath(path)))
    directory = tier._no_alias(tier._root() / tier.RUNTIME_CONTROL / "mcp-discovery")
    if (path.parent != directory or path.suffix != ".json"
            or not re.fullmatch(r"[a-f0-9]{32}", path.stem)):
        raise ValueError("Expected a retained discovery capture")
    report, state = tier._document(snapshot, path)
    if (type(report.get("version")) is not int or report["version"] != 1
            or report.get("tier") != tier.TIER or report.get("operation") != "mcp_discovery_capture"
            or report.get("run_id") != binding["run_id"] or report.get("capture_id") != path.stem
            or report.get("status") != "tools_discovered"
            or tier._digest(report.get("binding")) != tier._digest(binding)
            or report.get("binding_sha256") != tier._digest(binding)
            or report.get("discovery_complete") is not True or report.get("identity_stable") is not True
            or report.get("observation_failure") is not None
            or any(report.get(key) is not False for key in (
                "tools_call_requests_performed", "client_tools_call_enabled", "game_inspection_tools_called"))
            or report.get("diagnostics") != {"failure_stage": None, "failure_reason": None,
                "http_status": None, "final_context": "matched", "total_deadline_exceeded": False,
                "duplicate_header": None}
            or report["diagnostics"]["total_deadline_exceeded"] is not False):
        raise ValueError("Discovery is not a successful exact-run observation")
    observation = report.get("observation")
    if (not isinstance(observation, dict) or observation.get("protocol") != discovery.PROTOCOL
            or observation.get("methods") != list(discovery.METHODS)
            or observation.get("matched_response_ids") != [1, 2]
            or any(type(value) is not int for value in observation["matched_response_ids"])
            or type(observation.get("requests_sent")) is not int or observation["requests_sent"] != 4
            or any(not isinstance(observation.get(key), str) or not SHA256.fullmatch(observation[key])
                   for key in ("initialization_sha256", "inventory_sha256"))
            or type(observation.get("received_bytes")) is not int
            or not 1 <= observation["received_bytes"] <= discovery.MAX_TOTAL
            or type(observation.get("events_received")) is not int
            or not 3 <= observation["events_received"] <= discovery.MAX_EVENTS
            or observation.get("pagination_present") is not False
            or not isinstance(observation.get("tools"), list)
            or type(observation.get("tool_count")) is not int
            or not 1 <= observation["tool_count"] == len(observation["tools"]) <= discovery.MAX_TOOLS):
        raise ValueError("Discovery inventory is incomplete")
    seen, target = set(), None
    for row in observation["tools"]:
        if (not isinstance(row, dict) or set(row) != {"name", "schema"}
                or not isinstance(row["name"], str) or not discovery.NAME.fullmatch(row["name"])
                or row["name"].casefold() in seen or not isinstance(row["schema"], dict)):
            raise ValueError("Discovery inventory is ambiguous")
        seen.add(row["name"].casefold())
        if row["name"] == TOOL:
            target = row["schema"]
    if (target is None or not isinstance(target.get("sha256"), str)
            or not SHA256.fullmatch(target["sha256"])
            or tier._digest(target) != tier._digest({
                **discovery._schema_summary({"type": "object"}), "sha256": target["sha256"]})):
        raise ValueError("The zero-parameter tool was not discovered")
    return {"path": str(path), "sha256": state["sha256"], "capture_id": path.stem}, target


def _profile(snapshot, run):
    relative = "profiles/" + tier.PROFILE + "/plugins.txt"
    path = tier._no_alias(tier._root() / tier.INSTANCE / relative)
    state, raw = snapshot.read(path, content=True)
    pinned = run["inputs"]["instance"]["files"].get(relative)
    expected = [*tier.BASE_PLUGINS, "SkyrimNet.esp"]
    canonical = "".join("*" + name + "\n" for name in expected).encode("utf-8")
    canonical_sha256 = hashlib.sha256(canonical).hexdigest()
    if (not isinstance(pinned, dict) or not state.get("exists")
            or pinned.get("sha256") != canonical_sha256
            or raw not in (canonical, MO2_PLUGIN_HEADER + canonical)):
        raise ValueError("The pinned plugin profile changed or is unsupported")
    return {"path": str(path), "sha256": state["sha256"], "pinned_sha256": canonical_sha256,
        "observed_form": "canonical_seed" if raw == canonical else "mo2_downloaded_content_header",
        "byte_identical_to_launch": raw == canonical, "expected_plugins": expected}


def _context(run_id, smoke_capture, discovery_capture, process_probe, module_probe, connection_probe):
    base, run, launched = discovery._context(run_id, smoke_capture, process_probe, module_probe, connection_probe)
    snapshot = tier._Snapshot()
    capture, schema = _capture(discovery_capture, base, snapshot)
    profile = _profile(snapshot, run)
    if base["smoke_binding"]["modules"]["skyrimnet.dll"]["sha256"] != SOURCE_BASIS["dll_sha256"]:
        raise ValueError("The native implementation is not the statically reviewed build")
    files = (Path(__file__), tier.REPO / "tools/se_lab_mcp_plugins.py")
    implementation = {str(p.relative_to(tier.REPO)): snapshot.read(p)["sha256"] for p in files}
    snapshot.finish()
    return dict(version=VERSION, tier=tier.TIER, run_id=run_id,
        discovery_binding=base, discovery_capture=capture, tool=TOOL, arguments={},
        schema=schema, profile=profile, methods=list(METHODS), source_basis=SOURCE_BASIS,
        implementation=implementation), run, launched


def plugins_plan(run_id, smoke_capture, discovery_capture, *, process_probe=None, module_probe=None, connection_probe=None):
    binding, _, _ = _context(run_id, smoke_capture, discovery_capture,
        process_probe or tier._runtime_process_snapshot, module_probe or smoke._modules,
        connection_probe or smoke._connections)
    return dict(version=VERSION, operation="mcp_plugins_plan", status="ready_for_one_plugin_query",
        binding=binding, review_token="mcp-plugins-v1:" + tier._digest(binding),
        network_requests_performed=False, writes_performed=False, tools_call_requests_performed=False,
        runtime_verified=False, runtime_playback_verified=False, paid_generation=False)


class _Session(discovery._Session):
    """Separate fixed sequence; the discovery transport remains unchanged."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema_authorized = False
        self.tool_call_attempted = False

    def _send(self, stream, method, path, body=b""):
        self.budget.check()
        if self.requests_sent >= 5:
            raise ValueError("Plugin inspection request limit reached")
        if method == "GET" and path == "/sse" and not body and self.requests_sent == 0:
            headers = "Accept: text/event-stream\r\nConnection: keep-alive\r\n"
        elif (method == "POST" and path == self.endpoint and self.endpoint is not None
                and self.post_index < len(METHODS)
                and body == discovery._wire(_messages()[self.post_index])
                and (self.post_index != 3 or self.schema_authorized)):
            headers = ("Accept: application/json\r\nConnection: close\r\n"
                "Content-Type: application/json\r\nContent-Length: " + str(len(body)) + "\r\n")
        else:
            raise ValueError("Unapproved plugin inspection request")
        raw = (method + " " + path + " HTTP/1.1\r\nHost: 127.0.0.1:18889\r\n"
               "Accept-Encoding: identity\r\n" + headers + "\r\n").encode("ascii") + body
        discovery._socket_io(stream.settimeout, self.budget.remaining())
        self.requests_sent += 1
        if method == "POST" and self.post_index == 3:
            self.tool_call_attempted = True  # Includes partial-send/unknown outcomes.
        discovery._socket_io(stream.sendall, raw)

    def post_next(self):
        if self.post_index >= len(METHODS):
            raise ValueError("No further MCP calls are authorized")
        self.require_no_buffered_work()
        with self._connect() as stream:
            self._send(stream, "POST", self.endpoint, discovery._wire(_messages()[self.post_index]))
            reader = discovery._Reader(stream, self.budget)
            body = discovery._Body(reader, reader.headers({200, 202, 204}), discovery.MAX_POST_BODY)
            while body.piece():
                pass
            if reader.buffer:
                raise ValueError("Unexpected HTTP acknowledgement data")
        self.post_index += 1
        self.budget.check()


def _projection(result, expected, forbidden_text=()):
    if (not isinstance(result, dict) or set(result) != {"isError", "content"}
            or result["isError"] is not False or not isinstance(result["content"], list)
            or len(result["content"]) != 1):
        raise ValueError("Unsupported plugin-result envelope")
    block = result["content"][0]
    if (not isinstance(block, dict) or set(block) != {"type", "text"}
            or block["type"] != "text" or not isinstance(block["text"], str)):
        raise ValueError("Unsupported plugin-result content")
    if block["text"] == "Error: Game is not ready yet":
        raise _Failure("plugins_validation", "game_not_ready")
    raw = block["text"].encode("utf-8")
    if len(raw) > MAX_TEXT:
        raise ValueError("Plugin-result text exceeds bound")
    names = smoke._json(raw)
    if (not isinstance(names, list) or len(names) > MAX_PLUGINS
            or any(not isinstance(name, str) or not FILENAME.fullmatch(name)
                   or any(value.casefold() in name.casefold() for value in forbidden_text) for name in names)
            or len({name.casefold() for name in names}) != len(names)):
        raise ValueError("Plugin-result filenames are malformed or ambiguous")
    present = {name.casefold() for name in names}
    expected_folded = {name.casefold() for name in expected}
    return {"plugin_count": len(names), "plugin_names_sha256": tier._digest(names),
        "result_sha256": tier._digest(result), "text_bytes": len(raw),
        "expected_plugins": [{"name": name, "present": name.casefold() in present} for name in expected],
        "all_expected_present": expected_folded <= present,
        "other_plugin_count": len(present - expected_folded)}


def _inspect(pid, deadline, live, connection_probe, schema, expected, activity, *, sse_header_compatibility=None):
    # Only a compatibility descriptor from the validated exact-run discovery
    # binding may enable the pinned server's narrowly reviewed SSE header form.
    options = {} if sse_header_compatibility is None else {"sse_content_type_compatibility": sse_header_compatibility}
    session = _Session(pid, deadline, live, connection_probe, **options)
    try:
        with _stage("plugins_transport"), session:
            with _stage("initialize_post"):
                session.post_next()
            with _stage("initialize_result"):
                initialized = session.result(1)
                if (initialized.get("protocolVersion") != discovery.PROTOCOL
                        or not isinstance(initialized.get("capabilities"), dict)
                        or not isinstance(initialized["capabilities"].get("tools"), dict)
                        or not isinstance(initialized.get("serverInfo"), dict)):
                    raise ValueError("Unsupported MCP initialization")
                for key, limit in (("name", 256), ("version", 128)):
                    value = initialized["serverInfo"].get(key)
                    if (not isinstance(value, str) or not value.strip() or len(value) > limit
                            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                        raise ValueError("Invalid MCP server metadata")
            with _stage("initialized_notification"):
                session.post_next()
            with _stage("tools_list_post"):
                session.post_next()
            with _stage("tools_list_result"):
                listed = session.result(2)
            with _stage("fresh_schema"):
                secret = session.endpoint.split("=", 1)[1]
                inventory = discovery._inventory(listed, (secret,))
                if inventory["pagination_present"]:
                    raise ValueError("Incomplete fresh tool inventory")
                rows = [row for row in listed["tools"] if row["name"] == TOOL]
                if len(rows) != 1 or tier._digest(_empty_arguments_schema(rows[0]["inputSchema"])) != tier._digest(schema):
                    raise ValueError("The reviewed tool schema changed")
                session.schema_authorized = True
            with _stage("plugins_post"):
                session.post_next()
            with _stage("plugins_result"):
                result = session.result(3)
            with _stage("plugins_validation"):
                projected = _projection(result, expected, (secret,))
            with _stage("final_stream_validation"):
                session.require_no_buffered_work()
                session.budget.check()
            return {"protocol": discovery.PROTOCOL, "methods": list(METHODS),
                "matched_response_ids": [1, 2, 3], "schema_sha256": schema["sha256"],
                "initialization_sha256": tier._digest(initialized), **projected}
    finally:
        activity.update(requests_attempted=session.requests_sent,
            tool_call_attempted=session.tool_call_attempted,
            received_bytes=session.budget.received, events_received=session.budget.events,
            sse_content_type_pair_normalized=session.sse_content_type_pair_normalized)


def collect_plugins(run_id, smoke_capture, discovery_capture, review_token, *,
                    process_probe=None, module_probe=None, connection_probe=None):
    process_probe = process_probe or tier._runtime_process_snapshot
    module_probe, connection_probe = module_probe or smoke._modules, connection_probe or smoke._connections
    root = tier._root()
    with tier._writer_lock(tier._no_alias(root / ".se-lab-writer.lock")), tier._writer_lock(tier._no_alias(root / tier.CONTROL / "writer.lock")):
        binding, run, launched = _context(run_id, smoke_capture, discovery_capture,
            process_probe, module_probe, connection_probe)
        if not tier._matches(review_token, "mcp-plugins-v1:" + tier._digest(binding)):
            raise ValueError("Plugin inspection review is stale")
        deadline = time.monotonic() + TOTAL_SECONDS
        def live():
            if (time.monotonic() >= deadline or smoke._live(run, launched, process_probe)
                    != binding["discovery_binding"]["smoke_binding"]["game"]):
                raise ValueError("Plugin inspection identity or deadline changed")
        activity = {"requests_attempted": 0, "tool_call_attempted": False, "received_bytes": 0,
            "events_received": 0, "sse_content_type_pair_normalized": False}
        observation, failure = None, None
        try:
            observation = _inspect(binding["discovery_binding"]["smoke_binding"]["game"]["pid"],
                deadline, live, connection_probe, binding["schema"], binding["profile"]["expected_plugins"], activity,
                sse_header_compatibility=binding["discovery_binding"].get("sse_header_compatibility"))
            with _stage("post_query_identity"):
                live()
        except _Failure as error:
            failure = error
        except discovery.FAILURES:
            failure = _Failure("plugins_transport")
        try:
            after, _, _ = _context(run_id, smoke_capture, discovery_capture,
                process_probe, module_probe, connection_probe)
            stable = after == binding
            final_context = "matched" if stable else "changed"
        except discovery.FAILURES:
            stable, final_context = False, "failed"
        if not stable and failure is None:
            failure = _Failure("final_context", "context_" + final_context)
        exceeded = time.monotonic() >= deadline
        if exceeded and failure is None:
            failure = _Failure("total_deadline", "deadline_exceeded")
        complete = failure is None and stable and observation is not None and observation["all_expected_present"]
        report = dict(version=VERSION, tier=tier.TIER, operation="mcp_plugins_capture",
            run_id=run_id, capture_id=uuid.uuid4().hex,
            status="expected_plugins_observed" if complete else "incomplete",
            binding=binding, binding_sha256=tier._digest(binding), observation=observation,
            observation_failure=None if failure is None else "bounded_plugin_inspection_failed",
            diagnostics={"failure_stage": None if failure is None else failure.stage,
                "failure_reason": None if failure is None else failure.reason,
                "http_status": None if failure is None else failure.http_status,
                "final_context": final_context, "total_deadline_exceeded": exceeded},
            activity=activity, identity_stable=stable, expected_plugins_observed=complete,
            tools_call_requests_attempted=activity["tool_call_attempted"],
            game_inspection_reply_validated=observation is not None,
            network_requests_attempted=activity["requests_attempted"] > 0, writes_performed=True,
            runtime_verified=False, runtime_playback_verified=False,
            native_initialization_verified=False, egress_verified=False, paid_generation=False,
            limitations=["Only the pinned get_plugins handler is requested, once, with empty arguments.",
                "Loaded filename presence is not VFS ownership, playback, AI behavior or provider inactivity.",
                "The native handler may initialize an internal plugin cache and write diagnostic logs.",
                "No raw response, arbitrary plugin names, session identifiers or descriptions are exported.",
                "An attempted call with no validated reply has an unknown outcome and is not retried."])
        directory = tier._no_alias(root / tier.RUNTIME_CONTROL / "mcp-plugins")
        directory.mkdir(exist_ok=True)
        tier._runtime_json(directory / (report["capture_id"] + ".json"), report, new=True)
        return report
