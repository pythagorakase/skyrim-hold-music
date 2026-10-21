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
    def run_wire(self, initial=None, ack=ACK, connections=None, live=None, gated=True, fragment=19):
        raw=initial if initial is not None else sse()
        sockets=gated_sockets(raw,ack,fragment) if gated else [FakeSocket(raw,53123,fragment)]+[FakeSocket(ack,p,fragment) for p in range(53124,53127)]
        self.sockets = sockets
        with patch.object(mcp.socket, "socket", side_effect=sockets):
            return mcp._discover(12, time.monotonic() + 60, live or (lambda: None),
                                 connections or tcp)

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
        inputs = dict(implementation={"frozen": "hash"}, protected={"baseline": "unchanged"}, instance={"files": files})
        run = dict(version=1,tier=mcp.tier.TIER,run_id=RUN,operation="skyrimnet_disabled_first_boot",inputs=inputs,
                   inputs_sha256=mcp.tier._digest(inputs),launch_command=mcp.tier._runtime_command(self.root),started_ns=self.started)
        launch = dict(tier=mcp.tier.TIER,run_id=RUN,process_started=True,launcher_pid=10,
                      processes=copy.deepcopy(self.processes),game=copy.deepcopy(self.processes[-1]),launch_attributed=True)
        for name,value in (("run.json",run),("launch-result.json",launch)):
            (self.runtime / name).write_text(json.dumps(value))
        for name,value in (("_root",self.root),("_implementation",inputs["implementation"]),("_protected",inputs["protected"])):
            mock=patch.object(mcp.tier,name,return_value=value);mock.start();self.addCleanup(mock.stop)
        self.kw = dict(process_probe=lambda:copy.deepcopy(self.processes), module_probe=lambda pid:copy.deepcopy(self.modules), connection_probe=tcp)
        base,_,_ = mcp.smoke._context(RUN,**self.kw)
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

    def test_private_errors_never_escape_capture(self):
        def failure(*args):raise ValueError(SECRET)
        result=self.collect(transport=failure)
        self.assertEqual(result["observation_failure"],"bounded_discovery_failed")
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
