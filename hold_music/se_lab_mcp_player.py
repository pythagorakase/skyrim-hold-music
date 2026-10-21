"""One explicitly reviewed get_player_info query; no generic MCP dispatch surface.

The pinned handler can initialize/persist UUID and identity-alias bookkeeping.
It reports no cell identifier and exposes no game-state mutation/provider action.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
import math
from pathlib import Path
import re
import time
import uuid

from hold_music import se_lab_mcp_discovery as discovery

smoke, tier = discovery.smoke, discovery.tier
VERSION = 1
TOOL = "get_player_info"
METHODS = (*discovery.METHODS, "tools/call")
TOTAL_SECONDS = 60.0
MAX_TEXT = 16 * 1024
MAX_NAME_BYTES = 1024
SCHEMA = {"type": "object"}
SCHEMA_SHA256 = "a2c799262a3ce3c19ef5cdd983bf3d12b43ab3c426227091b909dcb7054738c0"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FORM_ID = re.compile(r"0x[0-9A-F]{8}\Z")
SOURCE_BASIS = {
    "dll_sha256": "2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a",
    "contract": "beta26-rc4-get-player-info-snapshot-v1",
    "handler_rva": "0xcf56d0", "dispatch_rva": "0x1463cf0",
    "native_source_available": False, "static_disassembly_reviewed": True,
    "identity_bookkeeping_may_write": True,
}
STAGES = discovery.DIAGNOSTIC_STAGES | frozenset((
    "discovery_capture", "fresh_schema", "player_post", "player_result",
    "player_validation", "post_query_identity", "player_transport"))
REASONS = discovery.DIAGNOSTIC_REASONS | {"game_not_ready", "player_not_available"}


class _Failure(ValueError):
    def __init__(self, stage, reason="validation_or_probe_failure", http_status=None):
        self.stage = stage if stage in STAGES else "player_transport"
        self.reason = reason if reason in REASONS else "validation_or_probe_failure"
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        super().__init__("Bounded player inspection failed")


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
    # The pinned native handler and retained discovery both establish exactly
    # this schema. Do not admit semantically similar or constraint-bearing forms.
    if type(schema) is not dict or schema != SCHEMA or tier._digest(schema) != SCHEMA_SHA256:
        raise ValueError("The pinned empty-argument schema changed")
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
                **discovery._schema_summary(SCHEMA), "sha256": SCHEMA_SHA256})):
        raise ValueError("The zero-parameter tool was not discovered")
    return {"path": str(path), "sha256": state["sha256"], "capture_id": path.stem}, target


def _context(run_id, smoke_capture, discovery_capture, process_probe, module_probe, connection_probe):
    base, run, launched = discovery._context(run_id, smoke_capture, process_probe, module_probe, connection_probe)
    snapshot = tier._Snapshot()
    capture, schema = _capture(discovery_capture, base, snapshot)
    if base["smoke_binding"]["modules"]["skyrimnet.dll"]["sha256"] != SOURCE_BASIS["dll_sha256"]:
        raise ValueError("The native implementation is not the statically reviewed build")
    files = (Path(__file__), tier.REPO / "tools/se_lab_mcp_player.py")
    implementation = {str(p.relative_to(tier.REPO)): snapshot.read(p)["sha256"] for p in files}
    snapshot.finish()
    return dict(version=VERSION, tier=tier.TIER, run_id=run_id,
        discovery_binding=base, discovery_capture=capture, tool=TOOL, arguments={},
        schema=schema, methods=list(METHODS), source_basis=SOURCE_BASIS,
        implementation=implementation), run, launched


def player_plan(run_id, smoke_capture, discovery_capture, *, process_probe=None, module_probe=None, connection_probe=None):
    binding, _, _ = _context(run_id, smoke_capture, discovery_capture,
        process_probe or tier._runtime_process_snapshot, module_probe or smoke._modules,
        connection_probe or smoke._connections)
    return dict(version=VERSION, operation="mcp_player_plan", status="ready_for_one_player_snapshot",
        binding=binding, review_token="mcp-player-v1:" + tier._digest(binding),
        network_requests_performed=False, writes_performed=False, tools_call_requests_performed=False,
        identity_bookkeeping_may_write=True, game_state_mutation_requested=False,
        exact_player_cell_verified=False, qasmoke_programmatically_verified=False,
        fresh_world_verified=False, egress_verified=False,
        runtime_verified=False, runtime_playback_verified=False, paid_generation=False)


class _Session(discovery._Session):
    """Separate fixed sequence; the discovery transport remains unchanged."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema_authorized = False
        self.tool_call_attempted = False
        self.raw_rpc_data_sha256 = None
        self.raw_rpc_data_bytes = None

    def _send(self, stream, method, path, body=b""):
        self.budget.check()
        if self.requests_sent >= 5:
            raise ValueError("Player inspection request limit reached")
        if method == "GET" and path == "/sse" and not body and self.requests_sent == 0:
            headers = "Accept: text/event-stream\r\nConnection: keep-alive\r\n"
        elif (method == "POST" and path == self.endpoint and self.endpoint is not None
                and self.post_index < len(METHODS)
                and body == discovery._wire(_messages()[self.post_index])
                and (self.post_index != 3 or self.schema_authorized)):
            headers = ("Accept: application/json\r\nConnection: close\r\n"
                "Content-Type: application/json\r\nContent-Length: " + str(len(body)) + "\r\n")
        else:
            raise ValueError("Unapproved player inspection request")
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

    def result(self, request_id):
        if request_id != 3:
            return super().result(request_id)
        # Hash the exact UTF-8 JSON-RPC SSE data payload before parsing. This
        # excludes HTTP chunk/SSE framing and is never a reserialized object.
        raw = self.events.expected("message").encode("utf-8")
        self.raw_rpc_data_sha256 = hashlib.sha256(raw).hexdigest()
        self.raw_rpc_data_bytes = len(raw)
        reply = smoke._json(raw)
        if (type(reply) is not dict or set(reply) != {"jsonrpc", "id", "result"}
                or reply.get("jsonrpc") != "2.0" or type(reply.get("id")) is not int
                or reply["id"] != 3 or type(reply["result"]) is not dict):
            raise ValueError("Unexpected player JSON-RPC response")
        return reply["result"]


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _projection(result):
    if (type(result) is not dict or set(result) != {"isError", "content"}
            or result["isError"] is not False or type(result["content"]) is not list
            or len(result["content"]) != 1):
        raise ValueError("Unsupported player-result envelope")
    block = result["content"][0]
    if (type(block) is not dict or set(block) != {"type", "text"}
            or block["type"] != "text" or type(block["text"]) is not str):
        raise ValueError("Unsupported player-result content")
    failures = {"Error: Game is not ready yet": "game_not_ready",
                "Error: Player not available": "player_not_available"}
    if block["text"] in failures:
        raise _Failure("player_validation", failures[block["text"]])
    raw = block["text"].encode("utf-8")
    if len(raw) > MAX_TEXT:
        raise ValueError("Player-result text exceeds bound")
    data = smoke._json(raw)
    if (type(data) is not dict or set(data) != {"uuid", "name", "formID", "level", "position"}
            or type(data["uuid"]) is not int or not 0 <= data["uuid"] <= 2**64 - 1
            or type(data["level"]) is not int or not 0 <= data["level"] <= 65535
            or type(data["name"]) is not str or not data["name"]
            or any(ord(c) < 32 or ord(c) == 127 for c in data["name"])
            or type(data["formID"]) is not str or not FORM_ID.fullmatch(data["formID"])
            or type(data["position"]) is not dict or set(data["position"]) != {"x", "y", "z"}
            or not all(_finite_number(value) for value in data["position"].values())):
        raise ValueError("Malformed player snapshot")
    name_bytes = data["name"].encode("utf-8")
    if len(name_bytes) > MAX_NAME_BYTES:
        raise ValueError("Player name exceeds bound")
    canonical = data["formID"] == "0x00000014"
    return {"player_exists": True if canonical else None, "canonical_player_form": canonical,
        "uuid_uint64_valid": True, "level_uint16_valid": True,
        "position_finite": {axis: True for axis in ("x", "y", "z")},
        "name_sha256": hashlib.sha256(name_bytes).hexdigest(),
        "name_characters": len(data["name"]), "name_utf8_bytes": len(name_bytes),
        "text_sha256": hashlib.sha256(raw).hexdigest(), "text_bytes": len(raw)}


def _inspect(pid, deadline, live, connection_probe, schema, activity, *, sse_header_compatibility=None):
    # Only a compatibility descriptor from the validated exact-run discovery
    # binding may enable the pinned server's narrowly reviewed SSE header form.
    options = {} if sse_header_compatibility is None else {"sse_content_type_compatibility": sse_header_compatibility}
    session = _Session(pid, deadline, live, connection_probe, **options)
    try:
        with _stage("player_transport"), session:
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
            with _stage("player_post"):
                session.post_next()
            with _stage("player_result"):
                result = session.result(3)
            with _stage("player_validation"):
                projected = _projection(result)
            with _stage("final_stream_validation"):
                session.require_no_buffered_work()
                session.budget.check()
            return {"protocol": discovery.PROTOCOL, "methods": list(METHODS),
                "matched_response_ids": [1, 2, 3], "schema_sha256": schema["sha256"],
                "initialization_sha256": tier._digest(initialized), **projected}
    finally:
        activity.update(requests_attempted=session.requests_sent,
            tool_call_attempted=session.tool_call_attempted,
            raw_rpc_data_sha256=session.raw_rpc_data_sha256,
            raw_rpc_data_bytes=session.raw_rpc_data_bytes,
            received_bytes=session.budget.received, events_received=session.budget.events,
            sse_content_type_pair_normalized=session.sse_content_type_pair_normalized)


def collect_player(run_id, smoke_capture, discovery_capture, review_token, *,
                    process_probe=None, module_probe=None, connection_probe=None):
    process_probe = process_probe or tier._runtime_process_snapshot
    module_probe, connection_probe = module_probe or smoke._modules, connection_probe or smoke._connections
    root = tier._root()
    with tier._writer_lock(tier._no_alias(root / ".se-lab-writer.lock")), tier._writer_lock(tier._no_alias(root / tier.CONTROL / "writer.lock")):
        binding, run, launched = _context(run_id, smoke_capture, discovery_capture,
            process_probe, module_probe, connection_probe)
        if not tier._matches(review_token, "mcp-player-v1:" + tier._digest(binding)):
            raise ValueError("Player inspection review is stale")
        deadline = time.monotonic() + TOTAL_SECONDS
        def live():
            if (time.monotonic() >= deadline or smoke._live(run, launched, process_probe)
                    != binding["discovery_binding"]["smoke_binding"]["game"]):
                raise ValueError("Player inspection identity or deadline changed")
        activity = {"requests_attempted": 0, "tool_call_attempted": False, "received_bytes": 0,
            "events_received": 0, "sse_content_type_pair_normalized": False,
            "raw_rpc_data_sha256": None, "raw_rpc_data_bytes": None}
        observation, failure = None, None
        try:
            observation = _inspect(binding["discovery_binding"]["smoke_binding"]["game"]["pid"],
                deadline, live, connection_probe, binding["schema"], activity,
                sse_header_compatibility=binding["discovery_binding"].get("sse_header_compatibility"))
            with _stage("post_query_identity"):
                live()
        except _Failure as error:
            failure = error
        except discovery.FAILURES:
            failure = _Failure("player_transport")
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
        complete = bool(failure is None and stable and observation is not None and observation["player_exists"])
        outcome = ("not_attempted" if not activity["tool_call_attempted"] else
                   "reply_validated" if observation is not None else "unknown")
        report = dict(version=VERSION, tier=tier.TIER, operation="mcp_player_capture",
            run_id=run_id, capture_id=uuid.uuid4().hex,
            status="player_snapshot_observed" if complete else "incomplete",
            binding=binding, binding_sha256=tier._digest(binding), observation=observation,
            observation_failure=None if failure is None else "bounded_player_inspection_failed",
            diagnostics={"failure_stage": None if failure is None else failure.stage,
                "failure_reason": None if failure is None else failure.reason,
                "http_status": None if failure is None else failure.http_status,
                "final_context": final_context, "total_deadline_exceeded": exceeded},
            activity=activity, identity_stable=stable, player_snapshot_observed=complete,
            player_exists=True if complete else None, tool_call_outcome=outcome,
            tools_call_requests_attempted=activity["tool_call_attempted"],
            game_inspection_reply_validated=observation is not None,
            network_requests_attempted=activity["requests_attempted"] > 0, writes_performed=True,
            runtime_verified=False, runtime_playback_verified=False,
            native_initialization_verified=False, egress_verified=False, paid_generation=False,
            identity_bookkeeping_may_write=True, game_state_mutation_requested=False,
            exact_player_cell_verified=False, qasmoke_programmatically_verified=False,
            fresh_world_verified=False, normal_actor_ai_behavior_verified=False,
            limitations=["Only the pinned get_player_info handler is requested, once, with empty arguments.",
                "The native wrapper may create/cache entities and persist UUID or identity-alias bookkeeping.",
                "This is not a zero-write server query; no game-state mutation or provider action is requested.",
                "The reply contains no cell identifier; coordinates cannot establish QASmoke or a fresh world.",
                "Raw player name, UUID, coordinates, response text and session identifiers are not exported.",
                "The raw response hash covers UTF-8 JSON-RPC SSE data, excluding transport framing.",
                "An attempted call with no validated reply has an unknown outcome and is not retried."])
        directory = tier._no_alias(root / tier.RUNTIME_CONTROL / "mcp-player")
        directory.mkdir(exist_ok=True)
        tier._runtime_json(directory / (report["capture_id"] + ".json"), report, new=True)
        return report
