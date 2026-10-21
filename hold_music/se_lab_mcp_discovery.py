"""Bounded discovery of the attributed lab MCP server; no tool execution.

The transport admits only the three fixed MCP discovery messages. Responses
are untrusted data, and only bounded names, structural summaries and hashes
are retained. No credentials, prompts, raw sessions or payloads are exported.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from urllib.parse import urlsplit
import uuid

from hold_music import se_lab_skyrimnet_smoke as smoke

tier = smoke.tier
VERSION = 1
HOST = "127.0.0.1"
PORT = 18889
PROTOCOL = "2024-11-05"
SSE_SOURCE_BASIS = {
    "contract": "beta26-rc4-sse-content-type-pair-v1",
    "dll_sha256": "2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a",
}
METHODS = ("initialize", "notifications/initialized", "tools/list")
TOTAL_SECONDS = 60.0
MAX_TOTAL = 2 * 1024 * 1024
MAX_HEADERS = 16 * 1024
MAX_LINE = 64 * 1024
MAX_EVENT = 512 * 1024
MAX_POST_BODY = 16 * 1024
MAX_EVENTS = 128
MAX_TOOLS = 512
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}\Z")
SESSION = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
HEADER = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
FAILURES = (OSError, ValueError, TypeError, KeyError, RuntimeError, RecursionError,
            subprocess.SubprocessError)
DIAGNOSTIC_STAGES = frozenset((
    "sse_connect", "sse_accepted_peer", "sse_get_send", "sse_headers",
    "sse_content_type", "sse_endpoint", "initialize_post", "initialize_result",
    "initialized_notification", "tools_list_post", "tools_list_result",
    "inventory_validation", "final_stream_validation", "discovery_transport",
    "post_discovery_identity", "final_context", "total_deadline"))
DIAGNOSTIC_REASONS = frozenset((
    "validation_or_probe_failure", "socket_timeout", "socket_error",
    "unexpected_eof", "framing_limit", "header_ascii", "header_status_line",
    "header_version", "header_status", "header_field", "header_duplicate",
    "header_encoding", "sse_content_type", "body_encoding", "body_length",
    "peer_ownership", "deadline_exceeded", "context_changed", "context_failed"))
DUPLICATE_HEADER_CLASSES = frozenset((
    "content-type", "content-length", "transfer-encoding", "content-encoding",
    "cache-control", "connection", "keep-alive", "date", "server", "pragma",
    "vary", "location", "www-authenticate", "proxy-authenticate", "authorization",
    "proxy-authorization", "cookie", "set-cookie", "access-control-allow-origin",
    "access-control-allow-methods", "access-control-allow-headers", "other"))


def _duplicate_diagnostic(value):
    if value is None:
        return None
    if (not isinstance(value, dict)
            or set(value) != {"header_class", "values_equal", "occurrences_seen", "fields_seen"}
            or type(value["header_class"]) is not str
            or value["header_class"] not in DUPLICATE_HEADER_CLASSES
            or type(value["values_equal"]) is not bool
            or type(value["occurrences_seen"]) is not int or not 2 <= value["occurrences_seen"] <= 3
            or (value["occurrences_seen"] == 3 and value["header_class"] != "content-type")
            or type(value["fields_seen"]) is not int
            or not value["occurrences_seen"] <= value["fields_seen"] <= MAX_HEADERS):
        raise ValueError("Invalid fixed duplicate-header diagnostic")
    return {key: value[key] for key in ("header_class", "values_equal", "occurrences_seen", "fields_seen")}


def _sse_compatibility(value):
    if value is None:
        return False
    if (type(value) is not dict or set(value) != set(SSE_SOURCE_BASIS)
            or any(type(item) is not str for item in value.values())
            or value != SSE_SOURCE_BASIS):
        raise ValueError("Unsupported SSE header compatibility contract")
    return True


class _WireFailure(ValueError):
    def __init__(self, reason, http_status=None, duplicate_header=None):
        if reason not in DIAGNOSTIC_REASONS:
            raise ValueError("Unknown fixed discovery reason")
        self.reason = reason
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.duplicate_header = _duplicate_diagnostic(duplicate_header)
        super().__init__("Bounded discovery wire check failed")


class _DiscoveryFailure(ValueError):
    def __init__(self, stage, reason="validation_or_probe_failure", http_status=None, duplicate_header=None):
        if stage not in DIAGNOSTIC_STAGES:
            raise ValueError("Unknown fixed discovery stage")
        if reason not in DIAGNOSTIC_REASONS:
            raise ValueError("Unknown fixed discovery reason")
        self.stage = stage
        self.reason = reason
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.duplicate_header = _duplicate_diagnostic(duplicate_header)
        super().__init__("Bounded discovery stage failed")


@contextmanager
def _stage(name):
    try:
        yield
    except _DiscoveryFailure:
        raise
    except _WireFailure as error:
        raise _DiscoveryFailure(name, error.reason, error.http_status, error.duplicate_header) from None
    except FAILURES:
        raise _DiscoveryFailure(name) from None


def _socket_io(operation, *args):
    try:
        return operation(*args)
    except TimeoutError:
        raise _WireFailure("socket_timeout") from None
    except OSError:
        raise _WireFailure("socket_error") from None


def _messages():
    return (
        {"jsonrpc": "2.0", "id": 1, "method": METHODS[0], "params": {
            "protocolVersion": PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "Hold Music SE Lab discovery", "version": "1"}}},
        {"jsonrpc": "2.0", "method": METHODS[1]},
        {"jsonrpc": "2.0", "id": 2, "method": METHODS[2], "params": {}},
    )


def _wire(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _capture(path, binding, snapshot):
    path = tier._no_alias(Path(os.path.abspath(path)))
    expected = tier._no_alias(tier._root() / tier.RUNTIME_CONTROL / "smoke")
    if (path.parent != expected or path.suffix != ".json"
            or not re.fullmatch(r"[a-f0-9]{32}", path.stem)):
        raise ValueError("Expected retained smoke capture")
    report, state = tier._document(snapshot, path)
    if (type(report.get("version")) is not int or report["version"] != 1
            or report.get("tier") != tier.TIER
            or report.get("operation") != "skyrimnet_smoke_capture"
            or report.get("run_id") != binding["run_id"]
            or report.get("capture_id") != path.stem
            or report.get("status") != "disabled_controls_observed"
            or report.get("binding") != binding
            or report.get("binding_sha256") != tier._digest(binding)
            or report.get("observation_failure") is not None
            or any(report.get(k) is not True for k in (
                "live_snapshot_complete", "identity_stable", "disabled_controls_observed",
                "native_module_paths_and_hashes_observed", "config_get_service_observed"))):
        raise ValueError("Smoke capture is not a successful exact-run observation")
    rows = report.get("observations")
    if not isinstance(rows, list) or len(rows) != len(smoke.CHECKS):
        raise ValueError("Smoke config observations are incomplete")
    for row, (name, expected_checks) in zip(rows, smoke.CHECKS.items()):
        if (not isinstance(row, dict) or row.get("name") != name
                or row.get("all_match") is not True or not isinstance(row.get("checks"), list)
                or len(row["checks"]) != len(expected_checks)):
            raise ValueError("Smoke config observations are incomplete")
        for check, (field, expected_value) in zip(row["checks"], expected_checks.items()):
            if (not isinstance(check, dict) or check.get("path") != field
                    or type(check.get("expected")) is not type(expected_value)
                    or check["expected"] != expected_value
                    or any(check.get(k) is not True for k in ("present", "type_matches", "matches"))):
                raise ValueError("Smoke config readback does not match")
    return {"path": str(path), "sha256": state["sha256"], "capture_id": path.stem}


def _context(run_id, smoke_capture, process_probe, module_probe, connection_probe):
    base, run, launched = smoke._context(run_id, process_probe, module_probe, connection_probe)
    if base["modules"]["skyrimnet.dll"]["sha256"] != SSE_SOURCE_BASIS["dll_sha256"]:
        raise ValueError("SSE native implementation is not the reviewed build")
    snapshot = tier._Snapshot()
    capture = _capture(smoke_capture, base, snapshot)
    files = (Path(__file__), tier.REPO / "tools/se_lab_mcp_discovery.py")
    implementation = {str(p.relative_to(tier.REPO)): snapshot.read(p)["sha256"] for p in files}
    snapshot.finish()
    return {"version": VERSION, "tier": tier.TIER, "run_id": run_id,
            "smoke_binding": base, "smoke_capture": capture, "implementation": implementation,
            "host": HOST, "port": PORT, "sse_path": "/sse", "message_path": "/message",
            "protocol": PROTOCOL, "methods": list(METHODS),
            "sse_header_compatibility": dict(SSE_SOURCE_BASIS)}, run, launched


def discovery_plan(run_id, smoke_capture, *, process_probe=None, module_probe=None,
                   connection_probe=None):
    binding, _, _ = _context(run_id, smoke_capture,
        process_probe or tier._runtime_process_snapshot, module_probe or smoke._modules,
        connection_probe or smoke._connections)
    return {"version": VERSION, "operation": "mcp_discovery_plan",
            "status": "ready_for_bounded_discovery", "binding": binding,
            "review_token": "mcp-discovery-v1:" + tier._digest(binding),
            "network_requests_performed": False, "writes_performed": False,
            "game_inspection_tools_called": False, "runtime_verified": False,
            "egress_verified": False, "paid_generation": False}


def _endpoint(value):
    # This shipped server announces a relative /message?session_id=... URL.
    # Do not decode escaped paths or adopt an announced authority.
    if not isinstance(value, str) or len(value) > 160 or any(ord(c) <= 32 for c in value):
        raise ValueError("Invalid MCP endpoint")
    parsed = urlsplit(value)
    if (parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != "/message"
            or not parsed.query.startswith("session_id=")):
        raise ValueError("Invalid MCP endpoint")
    identifier = parsed.query[len("session_id="):]
    if not SESSION.fullmatch(identifier) or value != "/message?session_id=" + identifier:
        raise ValueError("Invalid MCP session")
    return value


def _peer(rows, pid, local_port):
    try:
        smoke._listeners(rows, pid)
    except FAILURES:
        raise _WireFailure("peer_ownership") from None
    matches = [r for r in rows if r["local_address"] == HOST and r["local_port"] == PORT
               and r["remote_address"] == HOST and r["remote_port"] == local_port
               and r["state"] == "Established"]
    if len(matches) != 1 or matches[0]["pid"] != pid:
        raise _WireFailure("peer_ownership")


class _Budget:
    def __init__(self, deadline, verify_live):
        self.deadline, self.verify_live = deadline, verify_live
        self.received, self.events = 0, 0

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise _WireFailure("deadline_exceeded")
        return min(seconds, 10.0)

    def check(self):
        self.remaining()
        self.verify_live()
        self.remaining()


class _Reader:
    def __init__(self, stream, budget):
        self.stream, self.budget, self.buffer = stream, budget, b""
        self.sse_content_type_pair_normalized = False

    def receive(self):
        self.budget.check()
        _socket_io(self.stream.settimeout, self.budget.remaining())
        chunk = _socket_io(self.stream.recv, 4096)
        self.budget.received += len(chunk)
        if self.budget.received > MAX_TOTAL:
            raise _WireFailure("framing_limit")
        self.buffer += chunk
        return bool(chunk)

    def through(self, delimiter, maximum):
        while delimiter not in self.buffer:
            if len(self.buffer) > maximum:
                raise _WireFailure("framing_limit")
            if not self.receive():
                raise _WireFailure("unexpected_eof")
        index = self.buffer.index(delimiter)
        if index > maximum:
            raise _WireFailure("framing_limit")
        result, self.buffer = self.buffer[:index], self.buffer[index + len(delimiter):]
        return result

    def exact(self, size):
        while len(self.buffer) < size:
            if not self.receive():
                raise _WireFailure("unexpected_eof")
        result, self.buffer = self.buffer[:size], self.buffer[size:]
        return result

    def headers(self, accepted, *, sse_content_type_compatibility=None):
        # Only the SSE GET call site supplies this pinned-build exception.
        # POST acknowledgements and callers without explicit opt-in stay strict.
        compatible_sse = _sse_compatibility(sse_content_type_compatibility)
        raw = self.through(b"\r\n\r\n", MAX_HEADERS)
        try:
            lines = raw.decode("ascii").split("\r\n")
        except UnicodeError:
            raise _WireFailure("header_ascii") from None
        try:
            version, status, *_ = lines.pop(0).split(" ")
        except ValueError:
            raise _WireFailure("header_status_line") from None
        if version != "HTTP/1.1":
            raise _WireFailure("header_version")
        if not re.fullmatch(r"[0-9]{3}", status):
            raise _WireFailure("header_status_line")
        status_code = int(status)
        if status_code not in accepted:
            raise _WireFailure("header_status", status_code)
        result, counts = {}, {}
        for field_count, line in enumerate(lines, 1):
            try:
                key, value = line.split(":", 1)
            except ValueError:
                raise _WireFailure("header_field", status_code) from None
            if not HEADER.fullmatch(key) or any(ord(c) < 32 and c != "\t" for c in value):
                raise _WireFailure("header_field", status_code)
            key = key.lower()
            counts[key] = counts.get(key, 0) + 1
            if key in result:
                if (compatible_sse and status_code == 200 and key == "content-type"
                        and counts[key] == 2 and result[key] == value.strip() == "text/event-stream"):
                    self.sse_content_type_pair_normalized = True
                    continue
                raise _WireFailure("header_duplicate", status_code, {
                    "header_class": key if key in DUPLICATE_HEADER_CLASSES else "other",
                    "values_equal": result[key] == value.strip(),
                    "occurrences_seen": counts[key], "fields_seen": field_count})
            result[key] = value.strip()
        if (result.get("content-encoding", "identity") != "identity"
                or ("content-length" in result and "transfer-encoding" in result)):
            raise _WireFailure("header_encoding", status_code)
        return result


class _Body:
    def __init__(self, reader, headers, maximum):
        self.reader, self.maximum, self.count = reader, maximum, 0
        self.chunked = "transfer-encoding" in headers
        self.left, self.done = None, False
        if self.chunked:
            if headers["transfer-encoding"].lower() != "chunked":
                raise _WireFailure("body_encoding")
        elif "content-length" in headers:
            text = headers["content-length"]
            if not text.isascii() or not text.isdecimal() or len(text) > 10:
                raise _WireFailure("body_length")
            self.left = int(text)
            if self.left > maximum:
                raise _WireFailure("framing_limit")

    def piece(self):
        if self.done:
            return b""
        if self.chunked:
            line = self.reader.through(b"\r\n", 32)
            if not re.fullmatch(rb"[0-9a-fA-F]{1,8}", line):
                raise ValueError("Invalid bounded HTTP chunk")
            size = int(line, 16)
            if size == 0:
                if self.reader.exact(2) != b"\r\n":
                    raise ValueError("HTTP trailers are unsupported")
                self.done = True
                return b""
            if self.count + size > self.maximum:
                raise ValueError("HTTP body exceeds bound")
            part = self.reader.exact(size)
            if self.reader.exact(2) != b"\r\n":
                raise ValueError("Invalid HTTP chunk terminator")
        elif self.left is not None:
            if not self.left:
                self.done = True
                return b""
            if not self.reader.buffer and not self.reader.receive():
                raise ValueError("Incomplete HTTP content")
            size = min(self.left, len(self.reader.buffer), 4096)
            part = self.reader.exact(size)
            self.left -= size
        else:
            if not self.reader.buffer and not self.reader.receive():
                self.done = True
                return b""
            part, self.reader.buffer = self.reader.buffer, b""
        self.count += len(part)
        if self.count > self.maximum:
            raise ValueError("HTTP body exceeds bound")
        return part


class _Events:
    def __init__(self, body, budget):
        self.body, self.budget, self.buffer = body, budget, b""

    def line(self):
        while b"\n" not in self.buffer:
            if len(self.buffer) > MAX_LINE:
                raise ValueError("SSE line exceeds bound")
            piece = self.body.piece()
            if not piece:
                raise ValueError("SSE closed before discovery completed")
            self.buffer += piece
        line, self.buffer = self.buffer.split(b"\n", 1)
        if len(line) > MAX_LINE:
            raise ValueError("SSE line exceeds bound")
        try:
            return line.rstrip(b"\r").decode("utf-8")
        except UnicodeError:
            raise ValueError("Invalid SSE text") from None

    def next(self):
        kind, data, size = None, [], 0
        while True:
            self.budget.remaining()
            line = self.line()
            size += len(line.encode("utf-8")) + 1
            if size > MAX_EVENT:
                raise ValueError("SSE event exceeds bound")
            if not line:
                if kind is None and not data:
                    continue
                self.budget.events += 1
                if self.budget.events > MAX_EVENTS:
                    raise ValueError("SSE event count exceeds bound")
                return kind or "message", "\n".join(data)
            if line.startswith(":"):
                continue
            field, separator, value = line.partition(":")
            if not separator:
                value = ""
            if value.startswith(" "):
                value = value[1:]
            if field == "event":
                if kind is not None:
                    raise ValueError("Duplicate SSE event type")
                kind = value
            elif field == "data":
                data.append(value)
            elif field not in ("id", "retry"):
                raise ValueError("Unknown SSE field")

    def expected(self, expected_kind):
        while True:
            kind, data = self.next()
            if kind == "heartbeat":
                continue
            if kind != expected_kind:
                raise ValueError("Unexpected SSE event")
            return data


class _Session:
    def __init__(self, pid, deadline, verify_live, connection_probe, *, sse_content_type_compatibility=None):
        _sse_compatibility(sse_content_type_compatibility)
        self.sse_content_type_compatibility = dict(sse_content_type_compatibility) if sse_content_type_compatibility is not None else None
        self.sse_content_type_pair_normalized = False
        self.pid, self.connections = pid, connection_probe
        self.budget = _Budget(deadline, verify_live)
        self.sse = None
        self.endpoint = None
        self.post_index = 0
        self.requests_sent = 0

    def _connect(self, *, sse=False):
        stream = None
        try:
            with _stage("sse_connect") if sse else nullcontext():
                self.budget.check()
                stream = _socket_io(socket.socket, socket.AF_INET, socket.SOCK_STREAM)
                _socket_io(stream.settimeout, self.budget.remaining())
                _socket_io(stream.connect, (HOST, PORT))
                self.budget.check()
            with _stage("sse_accepted_peer") if sse else nullcontext():
                _peer(self.connections(), self.pid, _socket_io(stream.getsockname)[1])
                self.budget.check()
            return stream
        except BaseException:
            if stream is not None:
                stream.close()
            raise

    def _send(self, stream, method, path, body=b""):
        self.budget.check()
        if self.requests_sent >= 4:
            raise ValueError("MCP request limit reached")
        if method == "GET" and path == "/sse" and not body and self.requests_sent == 0:
            headers = "Accept: text/event-stream\r\nConnection: keep-alive\r\n"
        elif (method == "POST" and path == self.endpoint and self.endpoint is not None
                and self.post_index < len(METHODS)
                and body == _wire(_messages()[self.post_index])):
            headers = ("Accept: application/json\r\nConnection: close\r\n"
                       "Content-Type: application/json\r\nContent-Length: " + str(len(body)) + "\r\n")
        else:
            raise ValueError("Unapproved MCP request")
        raw = (method + " " + path + " HTTP/1.1\r\nHost: 127.0.0.1:18889\r\n"
               "Accept-Encoding: identity\r\n" + headers + "\r\n").encode("ascii") + body
        _socket_io(stream.settimeout, self.budget.remaining())
        self.requests_sent += 1
        _socket_io(stream.sendall, raw)

    def __enter__(self):
        try:
            self.sse = self._connect(sse=True)
            with _stage("sse_get_send"):
                self._send(self.sse, "GET", "/sse")
            with _stage("sse_headers"):
                reader = _Reader(self.sse, self.budget)
                headers = reader.headers({200}, sse_content_type_compatibility=self.sse_content_type_compatibility)
                self.sse_content_type_pair_normalized = reader.sse_content_type_pair_normalized
            with _stage("sse_content_type"):
                if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "text/event-stream":
                    raise _WireFailure("sse_content_type", 200)
            with _stage("sse_endpoint"):
                self.events = _Events(_Body(reader, headers, MAX_TOTAL), self.budget)
                self.endpoint = _endpoint(self.events.expected("endpoint"))
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.sse is not None:
            self.sse.close()
            self.sse = None

    def require_no_buffered_work(self):
        # Already-read bytes belong to the preceding protocol phase. Do not
        # adopt early replies or ignore trailing work as if it were a reply to
        # a later request. This conservative check performs no extra reads.
        if self.events.buffer or self.events.body.reader.buffer:
            raise ValueError("Unsolicited buffered SSE work")

    def post_next(self):
        if self.post_index >= len(METHODS):
            raise ValueError("No further MCP methods are authorized")
        self.require_no_buffered_work()
        message = _messages()[self.post_index]
        with self._connect() as stream:
            self._send(stream, "POST", self.endpoint, _wire(message))
            reader = _Reader(stream, self.budget)
            body = _Body(reader, reader.headers({200, 202, 204}), MAX_POST_BODY)
            while body.piece():
                pass  # Never retain or interpret arbitrary HTTP acknowledgement text.
            if reader.buffer:
                raise ValueError("Unexpected data after HTTP acknowledgement")
        self.post_index += 1
        self.budget.check()

    def result(self, request_id):
        raw = self.events.expected("message").encode("utf-8")
        reply = smoke._json(raw)
        if (not isinstance(reply, dict) or set(reply) != {"jsonrpc", "id", "result"}
                or reply.get("jsonrpc") != "2.0" or type(reply.get("id")) is not int
                or reply["id"] != request_id or not isinstance(reply["result"], dict)):
            raise ValueError("Unexpected JSON-RPC response")
        return reply["result"]


def _schema_summary(schema):
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("Expected object input schema")
    properties, required = schema.get("properties", {}), schema.get("required", [])
    if (not isinstance(properties, dict) or not isinstance(required, list)
            or any(not isinstance(key, str) for key in required)
            or len(set(required)) != len(required) or any(key not in properties for key in required)):
        raise ValueError("Malformed input schema summary")
    counts = {name: 0 for name in sorted(TYPES)}
    unspecified = 0
    for value in properties.values():
        if isinstance(value, bool):
            unspecified += 1
            continue
        if not isinstance(value, dict):
            raise ValueError("Malformed property schema")
        types = value.get("type", [])
        types = [types] if isinstance(types, str) else types
        if not isinstance(types, list) or any(not isinstance(t, str) or t not in TYPES for t in types):
            raise ValueError("Unknown schema type")
        if not types:
            unspecified += 1
        for kind in set(types):
            counts[kind] += 1
    return {"sha256": tier._digest(schema), "input_type": "object",
            "property_count": len(properties), "required_count": len(required),
            "property_type_counts": counts, "unspecified_type_count": unspecified}


def _inventory(result, forbidden_text=()):
    rows = result.get("tools")
    if not isinstance(rows, list) or len(rows) > MAX_TOOLS:
        raise ValueError("Invalid bounded tool inventory")
    summaries, seen = [], set()
    for tool in rows:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not NAME.fullmatch(tool["name"]):
            raise ValueError("Invalid tool name")
        if any(value.casefold() in tool["name"].casefold() for value in forbidden_text):
            raise ValueError("Tool name contains private session data")
        if tool["name"].casefold() in seen:
            raise ValueError("Duplicate tool name")
        seen.add(tool["name"].casefold())
        summaries.append({"name": tool["name"], "schema": _schema_summary(tool.get("inputSchema"))})
    return {"tools": sorted(summaries, key=lambda row: row["name"]), "tool_count": len(rows),
            "pagination_present": "nextCursor" in result and result["nextCursor"] is not None,
            "inventory_sha256": tier._digest(result)}


def _discover(pid, deadline, verify_live, connection_probe, *, sse_content_type_compatibility=None):
    with _Session(pid, deadline, verify_live, connection_probe,
                  sse_content_type_compatibility=sse_content_type_compatibility) as session:
        with _stage("initialize_post"):
            session.post_next()
        with _stage("initialize_result"):
            initialized = session.result(1)
            if (initialized.get("protocolVersion") != PROTOCOL
                    or not isinstance(initialized.get("capabilities"), dict)
                    or not isinstance(initialized["capabilities"].get("tools"), dict)
                    or not isinstance(initialized.get("serverInfo"), dict)):
                raise ValueError("Unsupported MCP initialization result")
            for key, limit in (("name", 256), ("version", 128)):
                value = initialized["serverInfo"].get(key)
                if (not isinstance(value, str) or not value.strip() or len(value) > limit
                        or any(ord(char) < 32 or ord(char) == 127 for char in value)):
                    raise ValueError("Invalid bounded MCP server implementation metadata")
        with _stage("initialized_notification"):
            session.post_next()
        with _stage("tools_list_post"):
            session.post_next()
        with _stage("tools_list_result"):
            listed = session.result(2)
        with _stage("inventory_validation"):
            inventory = _inventory(listed, (session.endpoint.split("=", 1)[1],))
        with _stage("final_stream_validation"):
            session.require_no_buffered_work()
            session.budget.check()
        return {"protocol": PROTOCOL, "methods": list(METHODS), "matched_response_ids": [1, 2],
                "requests_sent": session.requests_sent, "received_bytes": session.budget.received,
                "events_received": session.budget.events, "initialization_sha256": tier._digest(initialized),
                "sse_content_type_pair_normalized": session.sse_content_type_pair_normalized,
                **inventory}


def collect_discovery(run_id, smoke_capture, review_token, *, process_probe=None, module_probe=None,
                      connection_probe=None, transport=None):
    process_probe = process_probe or tier._runtime_process_snapshot
    module_probe, connection_probe = module_probe or smoke._modules, connection_probe or smoke._connections
    root = tier._root()
    with tier._writer_lock(tier._no_alias(root / ".se-lab-writer.lock")), tier._writer_lock(tier._no_alias(root / tier.CONTROL / "writer.lock")):
        binding, run, launched = _context(run_id, smoke_capture, process_probe, module_probe, connection_probe)
        if not tier._matches(review_token, "mcp-discovery-v1:" + tier._digest(binding)):
            raise ValueError("MCP discovery review is stale")
        deadline = time.monotonic() + TOTAL_SECONDS
        def live():
            if time.monotonic() >= deadline or smoke._live(run, launched, process_probe) != binding["smoke_binding"]["game"]:
                raise ValueError("MCP discovery identity or deadline changed")
        observation, failure, failure_stage = None, None, None
        failure_reason, http_status, duplicate_header = None, None, None
        try:
            if transport is None:
                observation = _discover(binding["smoke_binding"]["game"]["pid"], deadline, live, connection_probe,
                    sse_content_type_compatibility=binding["sse_header_compatibility"])
            else:
                observation = transport(binding["smoke_binding"]["game"]["pid"], deadline, live, connection_probe)
            with _stage("post_discovery_identity"):
                live()
        except _DiscoveryFailure as error:
            failure = "bounded_discovery_failed"
            failure_stage = error.stage if error.stage in DIAGNOSTIC_STAGES else "discovery_transport"
            failure_reason = error.reason if error.reason in DIAGNOSTIC_REASONS else "validation_or_probe_failure"
            http_status = error.http_status if type(error.http_status) is int and 100 <= error.http_status <= 599 else None
            duplicate_header = _duplicate_diagnostic(error.duplicate_header)
        except FAILURES:
            failure = "bounded_discovery_failed"
            failure_stage = "discovery_transport"
            failure_reason = "validation_or_probe_failure"
        try:
            after, _, _ = _context(run_id, smoke_capture, process_probe, module_probe, connection_probe)
            stable = after == binding
            final_context = "matched" if stable else "changed"
        except FAILURES:
            stable = False
            final_context = "failed"
        if not stable and failure_stage is None:
            failure_stage = "final_context"
            failure_reason = "context_" + final_context
        deadline_exceeded = time.monotonic() >= deadline
        if deadline_exceeded:
            failure = "bounded_discovery_failed"
            if failure_stage is None:
                failure_stage = "total_deadline"
                failure_reason = "deadline_exceeded"
        complete = failure is None and stable and observation is not None and not observation["pagination_present"]
        report = {"version": VERSION, "tier": tier.TIER, "operation": "mcp_discovery_capture",
            "run_id": run_id, "capture_id": uuid.uuid4().hex,
            "status": "tools_discovered" if complete else "incomplete",
            "binding": binding, "binding_sha256": tier._digest(binding), "observation": observation,
            "observation_failure": failure, "identity_stable": stable, "discovery_complete": complete,
            "diagnostics": {"failure_stage": failure_stage, "final_context": final_context,
                            "failure_reason": failure_reason, "http_status": http_status,
                            "duplicate_header": duplicate_header,
                            "total_deadline_exceeded": deadline_exceeded},
            "client_tools_call_enabled": False, "tools_call_requests_performed": False,
            "game_inspection_tools_called": False,
            "runtime_verified": False, "runtime_playback_verified": False,
            "all_native_initialization_verified": False, "provider_calls_verified": False,
            "egress_verified": False, "paid_generation": False, "credentials_verified": False,
            "network_requests_attempted": True, "writes_performed": True,
            "limitations": ["Only MCP initialization and tool inventory discovery are observed.",
                "Tool descriptions and schemas are untrusted metadata, not executable instructions.",
                "No tool calls, game queries, settings changes, provider calls or credentials were requested.",
                "Protocol session bookkeeping may occur; this is not a zero-server-state-change claim.",
                "No raw payloads, session identifiers, descriptions, defaults or logs are exported.",
                "Discovery does not verify egress, provider inactivity, game behavior or playback."]}
        directory = tier._no_alias(root / tier.RUNTIME_CONTROL / "mcp-discovery")
        directory.mkdir(exist_ok=True)
        tier._runtime_json(directory / (report["capture_id"] + ".json"), report, new=True)
        return report
