import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from hold_music import se_lab_mcp_discovery as mcp
from tools import se_lab_mcp_discovery as cli

RUN = "20261021T100000Z-123456789abc"
SECRET = "NEVER-EXPORT-SECRET-SENTINEL"
SESSION = "session-private-abcdef123456"


def diagnostic(stage=None, reason=None, status=None, context="matched", exceeded=False, duplicate=None):
    return {"failure_stage":stage,"failure_reason":reason,"http_status":status,
            "final_context":context,"total_deadline_exceeded":exceeded,"duplicate_header":duplicate}


def tcp():
    rows = [dict(local_address="127.0.0.1", local_port=port,
        remote_address="0.0.0.0", remote_port=0, state="Listen", pid=12)
        for port in (18880, 18889)]
    rows += [dict(local_address="127.0.0.1", local_port=18889,
        remote_address="127.0.0.1", remote_port=port, state="Established", pid=12)
        for port in range(53123, 53127)]
    return rows


def init_result():
    return {"protocolVersion": mcp.PROTOCOL, "capabilities": {"tools": {}},
            "serverInfo": {"name": SECRET, "version": SECRET}}


def tools_result():
    return {"tools": [{"name": "get_nearby_actors", "description": SECRET,
        "inputSchema": {"type": "object", "properties": {
            "radius": {"type": "number", "description": SECRET, "default": SECRET}},
            "required": [], "description": SECRET}}]}


def event(kind, data):
    return ("event: " + kind + "\ndata: " + data + "\n\n").encode()


def reply(request_id, result):
    return event("message", json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}))


def sse(endpoint=None, initialized=None, inventory=None, extra=b"", chunked=True):
    body = event("endpoint", endpoint or "/message?session_id=" + SESSION)
    body += extra + reply(1, initialized if initialized is not None else init_result())
    body += reply(2, inventory if inventory is not None else tools_result())
    if chunked:
        # Deliberately split UTF-8/SSE delimiters and JSON across HTTP chunks.
        framed = b"".join(f"{len(body[i:i+7]):X}\r\n".encode() + body[i:i+7] + b"\r\n"
                           for i in range(0, len(body), 7)) + b"0\r\n\r\n"
        return b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n" + framed
    return b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n" + body


ACK = b"HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\n\r\n"


class FakeSocket:
    def __init__(self, raw, port, fragment=19):
        self.raw, self.port, self.fragment = raw, port, fragment
        self.sent, self.connected, self.closed = [], [], False
        self.on_send = None

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
    def close(self): self.closed = True
    def settimeout(self, value):
        if value <= 0: raise AssertionError("Expected finite timeout")
    def connect(self, address): self.connected.append(address)
    def getsockname(self): return ("127.0.0.1", self.port)
    def sendall(self, value):
        self.sent.append(value)
        if self.on_send: self.on_send(value)
    def recv(self, size):
        amount = min(size, self.fragment)
        result, self.raw = self.raw[:amount], self.raw[amount:]
        return result


def gated_sockets(initial, ack=ACK, fragment=19):
    """Release each reply only after its corresponding request is sent."""
    sockets=[FakeSocket(initial,53123,fragment)]+[FakeSocket(ack,p,fragment) for p in range(53124,53127)]
    try:
        head,body=initial.split(b"\r\n\r\n",1)
        chunked=b"Transfer-Encoding: chunked" in head
        if chunked:
            parts=[]
            while body:
                line,body=body.split(b"\r\n",1);size=int(line,16)
                if not size:break
                if len(body)<size+2 or body[size:size+2]!=b"\r\n":raise ValueError("bad test chunk")
                parts.append(body[:size]);body=body[size+2:]
            body=b"".join(parts)
        endpoint,rest=body.split(b"\n\n",1);endpoint+=b"\n\n"
        second=rest.find(b"event: message",rest.find(b"event: message")+1)
        first,second_reply=(rest,b"") if second<0 else (rest[:second],rest[second:])
        def frame(raw):
            if not chunked:return raw
            return b"".join(f"{len(raw[i:i+7]):X}\r\n".encode()+raw[i:i+7]+b"\r\n" for i in range(0,len(raw),7))
        sockets[0].raw=head+b"\r\n\r\n"+frame(endpoint)
        def release(raw):sockets[0].raw+=frame(raw)
        sockets[1].on_send=lambda _:release(first)
        sockets[3].on_send=lambda _:release(second_reply)
    except (ValueError,IndexError):
        pass  # Malformed negative fixtures remain malformed.
    return sockets


class WireTests(unittest.TestCase):
    def run_wire(self, initial=None, ack=ACK, connections=None, live=None, gated=True, fragment=19, compatibility=None):
        raw=initial if initial is not None else sse()
        sockets=gated_sockets(raw,ack,fragment) if gated else [FakeSocket(raw,53123,fragment)]+[FakeSocket(ack,p,fragment) for p in range(53124,53127)]
        self.sockets = sockets
        with patch.object(mcp.socket, "socket", side_effect=sockets):
            return mcp._discover(12, time.monotonic() + 60, live or (lambda: None),
                                 connections or tcp, sse_content_type_compatibility=compatibility)

    def test_chunked_split_sse_only_emits_fixed_discovery_messages(self):
        with patch.dict("os.environ", {"HTTP_PROXY": "http://evil.invalid", "ALL_PROXY": SECRET}):
            result = self.run_wire(sse(extra=event("heartbeat", "private heartbeat")))
        self.assertEqual(result["methods"], list(mcp.METHODS))
        self.assertEqual(result["requests_sent"], 4)
        self.assertEqual(result["matched_response_ids"], [1, 2])
        self.assertEqual(result["tools"][0]["schema"]["property_type_counts"]["number"], 1)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(SESSION, json.dumps(result))
        self.assertTrue(all(s.closed for s in self.sockets))
        for sock in self.sockets:
            self.assertEqual(sock.connected, [("127.0.0.1", 18889)])
            self.assertNotIn(b"Authorization", sock.sent[0])
            self.assertNotIn(b"Cookie", sock.sent[0])
        self.assertTrue(self.sockets[0].sent[0].startswith(b"GET /sse HTTP/1.1"))
        sent = [json.loads(s.sent[0].split(b"\r\n\r\n")[1]) for s in self.sockets[1:]]
        self.assertEqual(sent, list(mcp._messages()))
        self.assertNotIn("tools/call", json.dumps(sent))

    def test_pinned_sse_pair_requires_explicit_optin_and_normalizes_only_two_literals(self):
        for names in (b"Content-Type: text/event-stream\r\nContent-Type: text/event-stream\r\n",
                      b"cOnTeNt-TyPe:\ttext/event-stream \t\r\nCONTENT-TYPE: text/event-stream\r\n"):
            raw=sse().replace(b"Content-Type: text/event-stream\r\n",names,1)
            with self.subTest(names=names):
                with self.assertRaises(mcp._DiscoveryFailure) as caught:self.run_wire(raw)
                self.assertEqual(caught.exception.reason,"header_duplicate")
                self.assertFalse(any(s.sent for s in self.sockets[1:]))
                result=self.run_wire(raw,compatibility=dict(mcp.SSE_SOURCE_BASIS))
                self.assertTrue(result["sse_content_type_pair_normalized"])
                self.assertEqual(result["requests_sent"],4)
                self.assertEqual([json.loads(s.sent[0].split(b"\r\n\r\n")[1]) for s in self.sockets[1:]],list(mcp._messages()))
        self.assertFalse(self.run_wire(compatibility=dict(mcp.SSE_SOURCE_BASIS))["sse_content_type_pair_normalized"])

    def test_sse_pair_exception_does_not_admit_conflicts_third_or_combined_types(self):
        invalid=(
            b"Content-Type: text/event-stream\r\nContent-Type: application/json\r\n",
            b"Content-Type: text/event-stream; charset=utf-8\r\nContent-Type: text/event-stream; charset=utf-8\r\n",
            b"Content-Type: application/json\r\nContent-Type: application/json\r\n",
            b"Content-Type: TEXT/EVENT-STREAM\r\nContent-Type: TEXT/EVENT-STREAM\r\n",
            b"Content-Type: text/event-stream\r\n"*3,
            b"Content-Type: text/event-stream, text/event-stream\r\n",
        )
        for headers in invalid:
            raw=sse().replace(b"Content-Type: text/event-stream\r\n",headers,1)
            with self.subTest(headers=headers),self.assertRaises(mcp._DiscoveryFailure) as caught:
                self.run_wire(raw,compatibility=dict(mcp.SSE_SOURCE_BASIS))
            self.assertFalse(any(s.sent for s in self.sockets[1:]))
            if headers.count(b"Content-Type:")==3:
                self.assertEqual(caught.exception.duplicate_header["occurrences_seen"],3)

    def test_sse_pair_continues_validating_entire_header_and_framing(self):
        pair=b"Content-Type: text/event-stream\r\n"*2
        bad=(b"Content-Length: 0\r\nContent-Length: 0\r\n",
             b"Transfer-Encoding: chunked\r\n",
             b"Content-Length: 0\r\n",  # Conflicts with the existing Transfer-Encoding.
             b"Authorization: x\r\nAuthorization: x\r\n",
             b"Set-Cookie: x\r\nSet-Cookie: x\r\n",
             b"Cache-Control: no-cache\r\nCache-Control: no-cache\r\n",
             b"Connection: keep-alive\r\nConnection: keep-alive\r\n",
             b"X-Unknown: x\r\nX-Unknown: x\r\n",
             b"Malformed header\r\n",b"Content-Encoding: gzip\r\n")
        for extra in bad:
            raw=sse().replace(b"Content-Type: text/event-stream\r\n",pair+extra,1)
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                self.run_wire(raw,compatibility=dict(mcp.SSE_SOURCE_BASIS))
            self.assertFalse(any(s.sent for s in self.sockets[1:]))
        raw=sse().replace(b"Content-Type: text/event-stream\r\n",pair,1)
        with self.assertRaises(ValueError):
            self.run_wire(raw.replace(b"\r\n\r\n7\r\n",b"\r\n\r\ninvalid\r\n",1),compatibility=dict(mcp.SSE_SOURCE_BASIS))
        for bound,value in (("MAX_EVENT",60),("MAX_LINE",20),("MAX_TOTAL",50),("MAX_HEADERS",40)):
            with self.subTest(bound=bound),patch.object(mcp,bound,value),self.assertRaises(ValueError):
                self.run_wire(raw,compatibility=dict(mcp.SSE_SOURCE_BASIS))

    def test_sse_compatibility_never_reaches_post_header_parser(self):
        raw=sse().replace(b"Content-Type: text/event-stream\r\n",b"Content-Type: text/event-stream\r\n"*2,1)
        ack=b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Type: text/event-stream\r\nContent-Length: 0\r\n\r\n"
        with self.assertRaises(mcp._DiscoveryFailure) as caught:
            self.run_wire(raw,ack=ack,compatibility=dict(mcp.SSE_SOURCE_BASIS))
        self.assertEqual(caught.exception.stage,"initialize_post")
        self.assertEqual(caught.exception.reason,"header_duplicate")
        self.assertEqual(sum(len(s.sent) for s in self.sockets),2)
        self.assertFalse(any(s.sent for s in self.sockets[2:]))

    def test_invalid_sse_contract_refuses_before_socket_creation(self):
        invalid=(True,{}, {**mcp.SSE_SOURCE_BASIS,"dll_sha256":"0"*64},
                 {**mcp.SSE_SOURCE_BASIS,"contract":"unreviewed"},
                 {**mcp.SSE_SOURCE_BASIS,"extra":SECRET})
        for value in invalid:
            with self.subTest(value=value),patch.object(mcp.socket,"socket",side_effect=AssertionError("No socket")),self.assertRaises(ValueError):
                mcp._discover(12,time.monotonic()+60,lambda:None,tcp,sse_content_type_compatibility=value)

    def test_close_delimited_and_fixed_length_sse_are_bounded_and_supported(self):
        self.assertEqual(self.run_wire(sse(chunked=False))["tool_count"], 1)
        raw = sse(chunked=False)
        head, body = raw.split(b"\r\n\r\n", 1)
        raw = head + b"\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        self.assertEqual(self.run_wire(raw)["tool_count"], 1)

    def test_endpoint_origin_path_and_session_escapes_rejected_before_post(self):
        bad = ["http://evil.invalid/message?session_id=x", "//127.0.0.1:18889/message?session_id=x",
            "http://127.0.0.1:18889/message?session_id=x", "/mcp?session_id=x", "/message/../message?session_id=x",
            "/%6dessage?session_id=x", "/message?session_id=", "/message?session_id=x&next=y",
            "/message?session_id=x#fragment", "/message?session_id=x%0d%0aHost:evil",
            "/message?session_id=x\rHost:evil", "/message?session_id=" + "x" * 129]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError): self.run_wire(sse(endpoint=value))
            self.assertFalse(any(sock.sent for sock in self.sockets[1:]))
            self.assertTrue(self.sockets[0].closed)

    def test_foreign_peer_or_missing_listener_refuses_before_sse_send(self):
        for change in ("peer", "listener", "wildcard"):
            rows = tcp()
            if change == "peer": rows[2]["pid"] = 99
            elif change == "listener": rows.pop(1)
            else: rows[1]["local_address"] = "0.0.0.0"
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_wire(connections=lambda: rows)
            self.assertFalse(self.sockets[0].sent)
            self.assertTrue(self.sockets[0].closed)

    def test_foreign_post_peer_refuses_before_json_body(self):
        rows = tcp(); rows[3]["pid"] = 99
        with self.assertRaises(ValueError): self.run_wire(connections=lambda: rows)
        self.assertTrue(self.sockets[0].sent)
        self.assertFalse(self.sockets[1].sent)

    def test_identity_change_before_send_refuses(self):
        def changed(): raise ValueError(SECRET)
        with self.assertRaises(ValueError): self.run_wire(live=changed)
        self.assertFalse(any(s.sent for s in self.sockets))

    def test_redirect_auth_compression_duplicate_headers_and_bad_chunks(self):
        for raw in [b"HTTP/1.1 302 Found\r\nLocation: http://evil.invalid\r\n\r\n",
            b"HTTP/1.1 401 Unauthorized\r\n\r\n",
            sse().replace(b"Transfer-Encoding: chunked", b"Content-Encoding: gzip\r\nTransfer-Encoding: chunked"),
            sse().replace(b"Transfer-Encoding: chunked", b"Content-Length: 1\r\nTransfer-Encoding: chunked"),
            sse().replace(b"Transfer-Encoding: chunked", b"Transfer-Encoding: chunked\r\nTransfer-Encoding: chunked"),
            sse().replace(b"\r\n\r\n7\r\n", b"\r\n\r\ninvalid\r\n", 1),
            b"HTTP/1.1 200 OK\r\nX: " + b"a" * (mcp.MAX_HEADERS + 1)]:
            with self.subTest(raw=raw[:50]), self.assertRaises(ValueError): self.run_wire(raw)
            self.assertFalse(any(s.sent for s in self.sockets[1:]))

    def test_post_redirect_and_oversized_ack_refuse(self):
        for ack in [b"HTTP/1.1 302 Found\r\nContent-Length: 0\r\n\r\n",
                    b"HTTP/1.1 200 OK\r\nContent-Length: 999999\r\n\r\n"]:
            with self.assertRaises(ValueError): self.run_wire(ack=ack)
            self.assertFalse(self.sockets[2].sent)

    def test_protocol_mismatch_error_and_server_request_fail_closed(self):
        bad = init_result(); bad["protocolVersion"] = "2025-06-18"
        with self.assertRaises(ValueError): self.run_wire(sse(initialized=bad))
        self.assertFalse(self.sockets[2].sent)
        for payload in [{"jsonrpc": "2.0", "id": 1, "error": {"message": SECRET}},
                        {"jsonrpc": "2.0", "id": 99, "method": "sampling/createMessage", "params": {"x": SECRET}},
                        {"jsonrpc": "2.0", "id": True, "result": init_result()}]:
            raw = sse(chunked=False)
            start = raw.index(b"event: message")
            raw = raw[:start] + event("message", json.dumps(payload))
            with self.assertRaises(ValueError): self.run_wire(raw)
            self.assertFalse(self.sockets[2].sent)

    def test_server_implementation_name_and_version_must_be_bounded_nonempty_strings(self):
        for field,limit in (("name",256),("version",128)):
            for value in (None,False,1,{},[],""," \t","bad\nvalue", "bad\x7fvalue","x"*(limit+1)):
                initialized=init_result()
                if value is None:initialized["serverInfo"].pop(field)
                else:initialized["serverInfo"][field]=value
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    self.run_wire(sse(initialized=initialized))
                self.assertFalse(self.sockets[2].sent)
                self.assertTrue(all(sock.closed for sock in self.sockets if sock.connected))
        initialized=init_result();initialized["serverInfo"]={"name":"n"*256,"version":"v"*128}
        result=self.run_wire(sse(initialized=initialized))
        self.assertNotIn("n"*256,json.dumps(result));self.assertNotIn("v"*128,json.dumps(result))

    def test_duplicate_json_keys_and_out_of_order_replies_refuse(self):
        prefix = sse(chunked=False).split(b"event: message", 1)[0]
        for raw in [event("message", '{"jsonrpc":"2.0","id":1,"id":1,"result":{}}'),
                    reply(2, tools_result()), reply(1, init_result()) + reply(1, init_result())]:
            with self.assertRaises(ValueError): self.run_wire(prefix + raw)

    def test_missing_response_and_heartbeat_flood_are_incomplete(self):
        prefix = sse(chunked=False).split(b"event: message", 1)[0]
        for tail in [b"", event("heartbeat", "") * (mcp.MAX_EVENTS + 1)]:
            with self.assertRaises(ValueError): self.run_wire(prefix + tail)

    def test_event_line_total_and_deadline_bounds(self):
        for name, value in [("MAX_LINE", 20), ("MAX_EVENT", 60), ("MAX_TOTAL", 50)]:
            with patch.object(mcp, name, value), self.assertRaises(ValueError): self.run_wire()
        with patch.object(mcp.time, "monotonic", return_value=100), self.assertRaises(ValueError):
            mcp._discover(12, 99, lambda: None, tcp)

    def test_inventory_pagination_is_reported_without_followup(self):
        inventory = tools_result(); inventory["nextCursor"] = SECRET
        result = self.run_wire(sse(inventory=inventory))
        self.assertTrue(result["pagination_present"])
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(sum(bool(s.sent) for s in self.sockets), 4)

    def test_session_token_in_tool_name_is_never_exported(self):
        for name in (SESSION,"prefix_"+SESSION,SESSION.upper()):
            inventory=tools_result();inventory["tools"][0]["name"]=name
            with self.subTest(name=name),self.assertRaises(ValueError):self.run_wire(sse(inventory=inventory))

    def test_already_read_early_or_duplicate_final_replies_refuse(self):
        with self.assertRaises(ValueError):self.run_wire(gated=False,fragment=4096)
        self.assertFalse(self.sockets[1].sent)
        raw=sse(chunked=False)+reply(2,tools_result())
        with self.assertRaises(ValueError):self.run_wire(raw,fragment=4096)

    def test_bad_tool_names_duplicate_names_and_schema_shapes_refuse(self):
        variants = []
        for name in ("tool name", "tool\nname", "x" * 129):
            value = tools_result(); value["tools"][0]["name"] = name; variants.append(value)
        value = tools_result(); value["tools"] *= 2; variants.append(value)
        for schema in ({"type": "string"}, {"type": "object", "required": ["missing"]},
                       {"type": "object", "properties": {"x": {"type": SECRET}}}):
            value = tools_result(); value["tools"][0]["inputSchema"] = schema; variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError): self.run_wire(sse(inventory=value))

    def test_session_has_no_arbitrary_method_parameter_and_refuses_fifth_request(self):
        sockets = gated_sockets(sse())
        with patch.object(mcp.socket, "socket", side_effect=sockets):
            with mcp._Session(12, time.monotonic() + 60, lambda: None, tcp) as session:
                with self.assertRaises(ValueError):
                    session._send(sockets[0], "POST", session.endpoint,
                        mcp._wire({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}))
                session.post_next();session.result(1)
                session.post_next();session.post_next();session.result(2)
                with self.assertRaises(ValueError): session.post_next()
                with self.assertRaises(ValueError): session._send(sockets[0], "POST", "/auth")


class ContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.runtime = self.root / mcp.tier.RUNTIME_CONTROL; self.runtime.mkdir()
        (self.root / mcp.tier.CONTROL).mkdir()
        self.started = 1700000000000000000
        ticks = self.started // 100 + 621355968000000000
        paths = [self.root / mcp.tier.INSTANCE / "ModOrganizer.exe", self.root / "Game/skse64_loader.exe", self.root / "Game/SkyrimSE.exe"]
        self.processes = [dict(pid=10+i, parent_pid=9+i, path=str(p), created_ticks=ticks+i+1) for i,p in enumerate(paths)]
        self.modules, files = [], {}
        for name in sorted(mcp.tier.NATIVE_DLLS):
            relative = "mods/Approved " + name + "/SKSE/Plugins/" + name
            path = self.root / mcp.tier.INSTANCE / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            files[relative] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.modules.append(dict(name=name, path=str(path)))
        for relative in ("Game/SkyrimSE.exe", "Game/skse64_loader.exe", "MO2/ModOrganizer.exe", "lab-manifest.json"):
            path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic protected asset")
        protected = mcp.tier._protected(self.root)
        contract = mcp.tier.prepare_runtime_storage(self.root, protected)
        inputs = dict(implementation={"frozen": "hash"}, protected=protected,
                      runtime_storage=contract, instance={"files": files})
        run = dict(version=1,tier=mcp.tier.TIER,run_id=RUN,operation="skyrimnet_disabled_first_boot",inputs=inputs,
                   inputs_sha256=mcp.tier._digest(inputs),launch_command=mcp.tier._runtime_command(self.root),started_ns=self.started)
        launch = dict(tier=mcp.tier.TIER,run_id=RUN,process_started=True,launcher_pid=10,
                      processes=copy.deepcopy(self.processes),game=copy.deepcopy(self.processes[-1]),launch_attributed=True)
        for name,value in (("run.json",run),("launch-result.json",launch)):
            (self.runtime / name).write_text(json.dumps(value))
        for name,value in (("_root",self.root),("_implementation",inputs["implementation"])):
            mock=patch.object(mcp.tier,name,return_value=value);mock.start();self.addCleanup(mock.stop)
        self.kw = dict(process_probe=lambda:copy.deepcopy(self.processes), module_probe=lambda pid:copy.deepcopy(self.modules), connection_probe=tcp)
        base,_,_ = mcp.smoke._context(RUN,**self.kw)
        patcher=patch.dict(mcp.SSE_SOURCE_BASIS,{"dll_sha256":base["modules"]["skyrimnet.dll"]["sha256"]})
        patcher.start();self.addCleanup(patcher.stop)
        observations = []
        for name, checks in mcp.smoke.CHECKS.items():
            observations.append({"name": name, "all_match": True, "response_bytes": 100,
                "checks": [{"path": key, "expected": value, "present": True, "type_matches": True,"matches":True}
                           for key,value in checks.items()]})
        self.capture = {"version":1,"tier":mcp.tier.TIER,"operation":"skyrimnet_smoke_capture","run_id":RUN,
            "capture_id":"a"*32,"status":"disabled_controls_observed","binding":base,"binding_sha256":mcp.tier._digest(base),
            "observations":observations,"observation_failure":None,"live_snapshot_complete":True,"identity_stable":True,
            "disabled_controls_observed":True,"native_module_paths_and_hashes_observed":True,"config_get_service_observed":True}
        self.path=self.runtime / "smoke" / ("a"*32+".json");self.path.parent.mkdir()
        self.save()
        self.calls=[]

    def save(self):self.path.write_text(json.dumps(self.capture))
    def plan(self):return mcp.discovery_plan(RUN,self.path,**self.kw)
    def transport(self,pid,deadline,live,connections):
        live();self.calls.append(pid)
        return {"protocol":mcp.PROTOCOL,"methods":list(mcp.METHODS),"matched_response_ids":[1,2],
                "requests_sent":4,"received_bytes":500,"events_received":3,"initialization_sha256":"a"*64,
                **mcp._inventory(tools_result())}
    def collect(self,token=None,transport=None):
        return mcp.collect_discovery(RUN,self.path,token or self.plan()["review_token"],transport=transport or self.transport,**self.kw)

    def test_plan_is_readonly_and_never_opens_a_socket(self):
        before={str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(mcp.socket,"socket",side_effect=AssertionError("No socket")):
            result=self.plan()
        self.assertEqual(result["status"],"ready_for_bounded_discovery")
        self.assertFalse(result["network_requests_performed"])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_successful_capture_is_sanitized_and_claims_only_discovery(self):
        result=self.collect()
        self.assertEqual(result["status"],"tools_discovered")
        self.assertEqual(result["diagnostics"],diagnostic())
        for key in ("game_inspection_tools_called","runtime_verified","egress_verified","credentials_verified","client_tools_call_enabled","tools_call_requests_performed"):
            self.assertIs(result[key],False)
        paths=list((self.runtime/"mcp-discovery").glob("*.json"));self.assertEqual(len(paths),1)
        self.assertNotIn(SECRET,paths[0].read_text());self.assertNotIn(SESSION,paths[0].read_text())

    def test_full_fake_socket_capture_preserves_smoke_and_exports_no_raw_response(self):
        token=self.plan()["review_token"]
        before=self.path.read_bytes()
        sockets=gated_sockets(sse())
        with patch.object(mcp.socket,"socket",side_effect=sockets):
            result=mcp.collect_discovery(RUN,self.path,token,**self.kw)
        self.assertEqual(result["status"],"tools_discovered")
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(result["observation"]["requests_sent"],4)
        self.assertNotIn(SECRET,json.dumps(result));self.assertNotIn(SESSION,json.dumps(result))
        self.assertTrue(all(s.closed for s in sockets))

    def test_real_collector_passes_only_validated_observed_build_compatibility(self):
        token=self.plan()["review_token"]
        raw=sse().replace(b"Content-Type: text/event-stream\r\n",b"Content-Type: text/event-stream\r\n"*2,1)
        sockets=gated_sockets(raw)
        with patch.object(mcp.socket,"socket",side_effect=sockets):
            result=mcp.collect_discovery(RUN,self.path,token,**self.kw)
        self.assertEqual(result["status"],"tools_discovered")
        self.assertTrue(result["observation"]["sse_content_type_pair_normalized"])
        self.assertEqual(result["binding"]["sse_header_compatibility"],mcp.SSE_SOURCE_BASIS)
        self.assertEqual(result["binding"]["smoke_binding"]["modules"]["skyrimnet.dll"]["sha256"],mcp.SSE_SOURCE_BASIS["dll_sha256"])

    def test_wrong_observed_dll_refuses_plan_and_collection_before_network(self):
        token=self.plan()["review_token"]
        before={str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.dict(mcp.SSE_SOURCE_BASIS,{"dll_sha256":"0"*64}),patch.object(mcp.socket,"socket",side_effect=AssertionError("No socket")):
            with self.assertRaises(ValueError):self.plan()
            with self.assertRaises(ValueError):self.collect(token)
        self.assertFalse(self.calls)
        # Collection can create only the writer lock files before admission.
        after={str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file() and p.name not in (".se-lab-writer.lock","writer.lock")}
        self.assertEqual(before,after)

    def test_smoke_missing_failed_wrong_run_or_tampered_readback_refuses(self):
        original=copy.deepcopy(self.capture)
        for change in ("failed","run","binding","boolean","observations","expected_type"):
            self.capture=copy.deepcopy(original)
            if change=="failed":self.capture["status"]="incomplete_or_mismatched"
            elif change=="run":self.capture["run_id"]="20261021T100001Z-123456789abc"
            elif change=="binding":self.capture["binding"]["game"]["created_ticks"]+=1
            elif change=="boolean":self.capture["identity_stable"]=1
            elif change=="observations":self.capture["observations"].pop()
            else:self.capture["observations"][0]["checks"][0]["expected"]=0
            self.save()
            with self.subTest(change=change),self.assertRaises(ValueError):self.plan()
        self.path.unlink()
        with self.assertRaises((ValueError,OSError)):self.plan()
        self.assertFalse(self.calls)

    def test_capture_must_be_retained_in_fixed_runtime_directory(self):
        outside=self.root/"outside.json";outside.write_text(json.dumps(self.capture))
        with self.assertRaises(ValueError):mcp.discovery_plan(RUN,outside,**self.kw)

    def test_review_token_and_smoke_hash_drift_send_nothing(self):
        token=self.plan()["review_token"]
        self.capture["response_extra"]="changed";self.save()
        for value in (token,"skyrimnet-smoke-v1:wrong","é"):
            with self.subTest(value=value),self.assertRaises(ValueError):self.collect(value)
        self.assertFalse(self.calls)

    def test_process_reuse_and_module_drift_refuse_before_network(self):
        token=self.plan()["review_token"]
        self.processes[-1]["created_ticks"]+=1
        with self.assertRaises(ValueError):self.collect(token)
        self.processes[-1]["created_ticks"]-=1
        Path(self.modules[0]["path"]).write_bytes(b"changed")
        with self.assertRaises(ValueError):self.collect(token)
        self.assertFalse(self.calls)

    def test_process_exit_during_discovery_keeps_incomplete_report(self):
        def vanish(*args):
            result=self.transport(*args);self.processes.pop();return result
        result=self.collect(transport=vanish)
        self.assertEqual(result["status"],"incomplete");self.assertFalse(result["identity_stable"])
        self.assertEqual(result["diagnostics"]["failure_stage"],"post_discovery_identity")
        self.assertEqual(result["diagnostics"]["final_context"],"failed")

    def test_fixed_wire_failure_stages_preserve_request_limits_and_old_capture(self):
        old=self.runtime/"mcp-discovery"/("b"*32+".json")
        old.parent.mkdir();old.write_bytes(b'{"immutable_prior_capture":true}\n')
        old_bytes=old.read_bytes();old_mtime=old.stat().st_mtime_ns
        bad_init=init_result();bad_init["protocolVersion"]=SECRET
        bad_inventory=tools_result();bad_inventory["tools"][0]["name"]=SECRET+"/invalid"
        bad_ack=b"HTTP/1.1 500 Private\r\nContent-Length: 0\r\n\r\n"
        cases=(
            ("sse_content_type",sse().replace(b"text/event-stream",b"application/json"),None,1),
            ("sse_endpoint",sse(endpoint="/"+SECRET+"?session_id="+SESSION),None,1),
            ("initialize_post",sse(),1,2),
            ("initialize_result",sse(initialized=bad_init),None,2),
            ("initialized_notification",sse(),2,3),
            ("tools_list_post",sse(),3,4),
            ("tools_list_result",sse(chunked=False).replace(b'"id": 2',b'"id": 3'),None,4),
            ("inventory_validation",sse(inventory=bad_inventory),None,4),
            ("final_stream_validation",sse(chunked=False)+reply(2,tools_result()),None,4),
        )
        for stage,raw,ack_index,sent_count in cases:
            sockets=gated_sockets(raw,fragment=4096)
            if ack_index is not None:sockets[ack_index].raw=bad_ack
            with self.subTest(stage=stage),patch.object(mcp.socket,"socket",side_effect=sockets):
                result=mcp.collect_discovery(RUN,self.path,self.plan()["review_token"],**self.kw)
                self.assertEqual(result["status"],"incomplete")
                self.assertIsNone(result["observation"])
                self.assertEqual(result["observation_failure"],"bounded_discovery_failed")
                reason,status="validation_or_probe_failure",None
                if stage=="sse_content_type":reason,status="sse_content_type",200
                if ack_index is not None:reason,status="header_status",500
                self.assertEqual(result["diagnostics"],diagnostic(stage,reason,status))
                self.assertTrue(result["identity_stable"])
                self.assertEqual(sum(len(s.sent) for s in sockets),sent_count)
                self.assertTrue(all(s.closed for s in sockets if s.connected))
                self.assertNotIn(SECRET,json.dumps(result));self.assertNotIn(SESSION,json.dumps(result))
                self.assertNotIn(b'"tools/call"',b"".join(part for s in sockets for part in s.sent))
                self.assertEqual(old.read_bytes(),old_bytes)
                self.assertEqual(old.stat().st_mtime_ns,old_mtime)
                retained=self.runtime/"mcp-discovery"/(result["capture_id"]+".json")
                self.assertEqual(json.loads(retained.read_text()),result)

    def test_final_context_failure_or_mismatch_has_fixed_stage(self):
        token=self.plan()["review_token"];original=mcp._context
        for mode in ("changed","failed"):
            calls=[]
            def final_check(*args,**kwargs):
                value=original(*args,**kwargs);calls.append(True)
                if len(calls)==2:
                    if mode=="failed":raise ValueError(SECRET)
                    value[0]["private_changed_marker"]=SECRET
                return value
            with self.subTest(mode=mode),patch.object(mcp,"_context",side_effect=final_check):
                result=self.collect(token)
                self.assertEqual(result["status"],"incomplete")
                self.assertEqual(result["diagnostics"],diagnostic("final_context","context_"+mode,context=mode))
                self.assertNotIn(SECRET,json.dumps(result))

    def test_header_diagnostics_are_fixed_redacted_and_do_not_send_posts(self):
        cases=(
            (b"HTTP/1.0 200 "+SECRET.encode()+b"\r\n\r\n","sse_headers","header_version",None),
            (b"HTTP/1.1 401 "+SECRET.encode()+b"\r\nLocation: http://"+SECRET.encode()+b"\r\n\r\n","sse_headers","header_status",401),
            (b"HTTP/1.1 404 "+SECRET.encode()+b"\r\n\r\n","sse_headers","header_status",404),
            (b"HTTP/1.1 999 "+SECRET.encode()+b"\r\n\r\n","sse_headers","header_status",None),
            (b"HTTP/1.1 000 "+SECRET.encode()+b"\r\n\r\n","sse_headers","header_status",None),
            (b"HTTP/1.1 "+SECRET.encode()+b"\r\n\r\n","sse_headers","header_status_line",None),
            (SECRET.encode()+b"\r\n\r\n","sse_headers","header_status_line",None),
            (b"HTTP/1.1 200 OK\r\nX: \xff"+SECRET.encode()+b"\r\n\r\n","sse_headers","header_ascii",None),
            (b"HTTP/1.1 200 OK\r\n"+SECRET.encode()+b"\r\n\r\n","sse_headers","header_field",200),
            (b"HTTP/1.1 200 OK\r\nInvalid key: "+SECRET.encode()+b"\r\n\r\n","sse_headers","header_field",200),
            (b"HTTP/1.1 200 OK\r\nX: \x01"+SECRET.encode()+b"\r\n\r\n","sse_headers","header_field",200),
            (b"HTTP/1.1 200 OK\r\nX: "+SECRET.encode()+b"\r\nx: "+SESSION.encode()+b"\r\n\r\n","sse_headers","header_duplicate",200),
            (b"HTTP/1.1 200 OK\r\nContent-Encoding: "+SECRET.encode()+b"\r\n\r\n","sse_headers","header_encoding",200),
            (b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nTransfer-Encoding: chunked\r\n\r\n","sse_headers","header_encoding",200),
            (b"","sse_headers","unexpected_eof",None),
            (b"HTTP/1.1 200 OK\r\nX: "+SECRET.encode(),"sse_headers","unexpected_eof",None),
            (b"HTTP/1.1 200 OK\r\nX: "+b"a"*(mcp.MAX_HEADERS+1)+SECRET.encode(),"sse_headers","framing_limit",None),
            (b"HTTP/1.1 200 OK\r\nX: "+b"a"*(mcp.MAX_HEADERS+1)+b"\r\n\r\n","sse_headers","framing_limit",None),
            (b"HTTP/1.1 200 OK\r\n\r\n","sse_content_type","sse_content_type",200),
            (b"HTTP/1.1 200 OK\r\nContent-Type: "+SECRET.encode()+b"\r\n\r\n","sse_content_type","sse_content_type",200),
            (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: "+SECRET.encode()+b"\r\n\r\n","sse_endpoint","body_encoding",None),
            (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: "+SECRET.encode()+b"\r\n\r\n","sse_endpoint","body_length",None),
        )
        old=self.runtime/"mcp-discovery"/("c"*32+".json")
        old.parent.mkdir();old.write_bytes(b'{"prior_handshake_failure":true}\n')
        old_bytes=old.read_bytes();old_mtime=old.stat().st_mtime_ns
        for raw,stage,reason,status in cases:
            sockets=gated_sockets(raw)
            with self.subTest(stage=stage,reason=reason,status=status),patch.object(mcp.socket,"socket",side_effect=sockets):
                result=mcp.collect_discovery(RUN,self.path,self.plan()["review_token"],**self.kw)
                duplicate={"header_class":"other","values_equal":False,"occurrences_seen":2,"fields_seen":2} if reason=="header_duplicate" else None
                self.assertEqual(result["diagnostics"],diagnostic(stage,reason,status,duplicate=duplicate))
                self.assertEqual(result["status"],"incomplete")
                self.assertIsNone(result["observation"])
                self.assertEqual(len(sockets[0].sent),1)
                self.assertFalse(any(s.sent for s in sockets[1:]))
                self.assertTrue(sockets[0].closed)
                self.assertNotIn(SECRET,json.dumps(result));self.assertNotIn(SESSION,json.dumps(result))
                self.assertEqual(old.read_bytes(),old_bytes);self.assertEqual(old.stat().st_mtime_ns,old_mtime)

    def test_socket_failures_are_attributed_to_exact_handshake_boundary(self):
        for method,stage,sent_count in (("connect","sse_connect",0),
                                       ("getsockname","sse_accepted_peer",0),
                                       ("sendall","sse_get_send",0),
                                       ("recv","sse_headers",1)):
            for exception,reason in ((TimeoutError,"socket_timeout"),(OSError,"socket_error")):
                sockets=gated_sockets(sse())
                with self.subTest(method=method,reason=reason),patch.object(sockets[0],method,side_effect=exception(SECRET)),patch.object(mcp.socket,"socket",side_effect=sockets):
                    result=mcp.collect_discovery(RUN,self.path,self.plan()["review_token"],**self.kw)
                    self.assertEqual(result["diagnostics"],diagnostic(stage,reason))
                    self.assertEqual(result["status"],"incomplete")
                    self.assertEqual(len(sockets[0].sent),sent_count)
                    self.assertFalse(any(s.sent for s in sockets[1:]))
                    self.assertTrue(sockets[0].closed)
                    self.assertNotIn(SECRET,json.dumps(result))
        with patch.object(mcp.socket,"socket",side_effect=OSError(SECRET)):
            result=mcp.collect_discovery(RUN,self.path,self.plan()["review_token"],**self.kw)
        self.assertEqual(result["diagnostics"],diagnostic("sse_connect","socket_error"))
        self.assertNotIn(SECRET,json.dumps(result))

    def test_duplicate_header_projection_is_allowlisted_and_still_refuses_before_post(self):
        names=("Content-Type","Content-Length","Transfer-Encoding","Cache-Control",
               "Connection","Authorization","Set-Cookie",SECRET)
        old=self.runtime/"mcp-discovery"/("d"*32+".json")
        old.parent.mkdir();old.write_bytes(b'{"prior_duplicate_failure":true}\n')
        before=(old.read_bytes(),old.stat().st_mtime_ns)
        for name in names:
            for equal in (True,False):
                value="text/event-stream" if name=="Content-Type" else SECRET
                second=value if equal else SESSION
                raw=("HTTP/1.1 200 OK\r\nX-First: ignored\r\n"+name+": "+value+
                     "\r\n"+name.swapcase()+":\t"+second+" \t\r\n\r\n").encode()
                sockets=gated_sockets(raw)
                expected={"header_class":name.lower() if name.lower() in mcp.DUPLICATE_HEADER_CLASSES else "other",
                          "values_equal":equal,"occurrences_seen":2,"fields_seen":3}
                with self.subTest(name=name,equal=equal),patch.object(mcp.socket,"socket",side_effect=sockets):
                    result=mcp.collect_discovery(RUN,self.path,self.plan()["review_token"],transport=lambda *args:mcp._discover(*args),**self.kw)
                    self.assertEqual(result["diagnostics"],diagnostic("sse_headers","header_duplicate",200,duplicate=expected))
                    self.assertEqual(result["status"],"incomplete")
                    self.assertFalse(any(s.sent for s in sockets[1:]))
                    self.assertTrue(sockets[0].closed)
                    self.assertNotIn(SECRET,json.dumps(result));self.assertNotIn(SESSION,json.dumps(result))
                    self.assertEqual((old.read_bytes(),old.stat().st_mtime_ns),before)

    def test_duplicate_diagnostic_refuses_arbitrary_fields_and_invalid_types(self):
        good={"header_class":"content-type","values_equal":True,"occurrences_seen":2,"fields_seen":3}
        third={**good,"occurrences_seen":3}
        self.assertEqual(mcp._WireFailure("header_duplicate",200,third).duplicate_header,third)
        bad=[{**good,"header_class":SECRET},{**good,"header_class":[]},{**good,"values_equal":1},
             {**good,"occurrences_seen":True},{**good,"occurrences_seen":4},
             {**third,"fields_seen":2},
             {**good,"fields_seen":True},{**good,"fields_seen":mcp.MAX_HEADERS+1},
             {**good,"raw_value":SECRET}]
        bad.extend({**third,"header_class":name} for name in mcp.DUPLICATE_HEADER_CLASSES
                   if name != "content-type")
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError) as caught:
                mcp._WireFailure("header_duplicate",200,value)
            self.assertNotIn(SECRET,str(caught.exception))

    def test_accepted_peer_rejection_is_distinct_from_connection_and_header_failure(self):
        sockets=gated_sockets(sse())
        def replaced_peer():
            rows=tcp()
            if sockets[0].connected and not sockets[0].closed:rows[2]["pid"]=99
            return rows
        kw={**self.kw,"connection_probe":replaced_peer}
        token=mcp.discovery_plan(RUN,self.path,**kw)["review_token"]
        with patch.object(mcp.socket,"socket",side_effect=sockets):
            result=mcp.collect_discovery(RUN,self.path,token,**kw)
        self.assertEqual(result["diagnostics"],diagnostic("sse_accepted_peer","peer_ownership"))
        self.assertFalse(any(s.sent for s in sockets));self.assertTrue(sockets[0].closed)

    def test_diagnostic_constructors_never_accept_arbitrary_reason_or_status(self):
        for call in (lambda:mcp._WireFailure(SECRET),lambda:mcp._DiscoveryFailure(SECRET),
                     lambda:mcp._DiscoveryFailure("sse_headers",SECRET)):
            with self.assertRaises(ValueError) as caught:call()
            self.assertNotIn(SECRET,str(caught.exception))
        for status in (True,SECRET,999,0,200.0):
            self.assertIsNone(mcp._WireFailure("header_status",status).http_status)
            self.assertIsNone(mcp._DiscoveryFailure("sse_headers","header_status",status).http_status)

    def test_final_context_recheck_cannot_overrun_total_deadline(self):
        token=self.plan()["review_token"]
        original_context=mcp._context
        for elapsed in (mcp.TOTAL_SECONDS - 0.001, mcp.TOTAL_SECONDS, mcp.TOTAL_SECONDS + 10):
            clock=[100.0];checks=[];self.calls.clear()
            def final_slow_context(*args, **kwargs):
                result=original_context(*args, **kwargs)
                checks.append(True)
                if len(checks)==2:
                    clock[0]+=elapsed
                return result
            with self.subTest(elapsed=elapsed), patch.object(mcp,"_context",side_effect=final_slow_context), patch.object(mcp.time,"monotonic",side_effect=lambda:clock[0]):
                result=self.collect(token)
                within_bound=elapsed < mcp.TOTAL_SECONDS
                self.assertEqual(len(checks),2)
                self.assertEqual(self.calls,[12])
                self.assertTrue(result["identity_stable"])
                self.assertEqual(result["observation"]["requests_sent"],4)
                self.assertEqual(result["status"],"tools_discovered" if within_bound else "incomplete")
                self.assertIs(result["discovery_complete"],within_bound)
                self.assertEqual(result["observation_failure"],None if within_bound else "bounded_discovery_failed")
                self.assertEqual(result["diagnostics"],diagnostic() if within_bound else diagnostic("total_deadline","deadline_exceeded",exceeded=True))
                self.assertFalse(result["tools_call_requests_performed"])
                retained=self.runtime/"mcp-discovery"/(result["capture_id"]+".json")
                self.assertEqual(json.loads(retained.read_text()),result)

    def test_private_errors_never_escape_capture(self):
        def failure(*args):raise ValueError(SECRET)
        result=self.collect(transport=failure)
        self.assertEqual(result["observation_failure"],"bounded_discovery_failed")
        self.assertEqual(result["diagnostics"]["failure_stage"],"discovery_transport")
        self.assertNotIn(SECRET,json.dumps(result))

    def test_pagination_retained_as_incomplete_without_retry(self):
        def paged(*args):
            result=self.transport(*args);result["pagination_present"]=True;return result
        result=self.collect(transport=paged)
        self.assertEqual(result["status"],"incomplete");self.assertEqual(len(self.calls),1)

    def test_cli_plan_collect_dispatch_and_exception_redaction(self):
        for op,status,extra in [("plan","ready_for_bounded_discovery",[]),("collect","tools_discovered",["--review-token","token"])]:
            with patch.object(mcp,"discovery_plan",return_value={"status":status}) as plan, patch.object(mcp,"collect_discovery",return_value={"status":status}) as collect, patch("sys.stdout",io.StringIO()):
                self.assertEqual(cli.main([op,"--run-id",RUN,"--smoke-capture",str(self.path),*extra]),0)
                self.assertEqual(plan.call_count,int(op=="plan"));self.assertEqual(collect.call_count,int(op=="collect"))
        output=io.StringIO()
        with patch.object(mcp,"discovery_plan",side_effect=ValueError(SECRET)),patch("sys.stdout",output):
            self.assertEqual(cli.main(["plan","--run-id",RUN,"--smoke-capture",str(self.path)]),1)
        self.assertNotIn(SECRET,output.getvalue())


if __name__ == "__main__":unittest.main()
