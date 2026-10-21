import copy
import hashlib
import io
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from hold_music import se_lab_mcp_player as player
from tools import se_lab_mcp_player as cli
import test_se_lab_mcp_discovery as fixture

d = player.discovery
SECRET, SESSION, RUN = fixture.SECRET, fixture.SESSION, fixture.RUN
UUID = 18446744073709551610
COORDINATE = -12345.67891


def inventory(schema=None, name="get_player_info"):
    return {"tools": [{"name": name, "description": SECRET,
                       "inputSchema": schema if schema is not None else {"type": "object"}}]}


def body():
    return {"uuid": UUID, "name": SECRET, "formID": "0x00000014", "level": 1,
            "position": {"x": COORDINATE, "y": 0, "z": 42.125}}


def answer(value=None, text=None):
    return {"isError": False, "content": [{"type": "text", "text": text if text is not None
        else json.dumps(body() if value is None else value, indent=2)}]}


def tcp():
    return fixture.tcp() + [dict(local_address="127.0.0.1", local_port=18889,
        remote_address="127.0.0.1", remote_port=53127, state="Established", pid=12)]


def sockets(*, listed=None, result=None, initialized=None, endpoint=None, chunked=True, raw_reply=None, tail=b""):
    def frame(raw):
        if not chunked:
            return raw
        return b"".join(f"{len(raw[i:i+7]):X}\r\n".encode() + raw[i:i+7] + b"\r\n"
                        for i in range(0, len(raw), 7))
    header = b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
    if chunked:
        header += b"Transfer-Encoding: chunked\r\n"
    stream = fixture.FakeSocket(header + b"\r\n" + frame(fixture.event("endpoint",
        endpoint or "/message?session_id=" + SESSION)), 53123, 4096)
    rows = [stream] + [fixture.FakeSocket(fixture.ACK, port, 4096) for port in range(53124, 53128)]
    rows[1].on_send = lambda _: setattr(stream, "raw", stream.raw + frame(fixture.reply(1,
        initialized if initialized is not None else fixture.init_result())))
    rows[3].on_send = lambda _: setattr(stream, "raw", stream.raw + frame(fixture.reply(2,
        listed if listed is not None else inventory())))
    rows[4].on_send = lambda _: setattr(stream, "raw", stream.raw + frame(
        (b"event: message\n" + b"".join(b"data: " + line.encode() + b"\n" for line in raw_reply.split("\n")) + b"\n" if raw_reply is not None else
         fixture.reply(3, result if result is not None else answer())) + tail))
    return rows


class ProjectionTests(unittest.TestCase):
    def test_exact_native_schema_not_semantic_variants(self):
        self.assertEqual(player._empty_arguments_schema({"type": "object"})["sha256"], player.SCHEMA_SHA256)
        for value in ({}, True, {"type": ["object"]}, {"type": "object", "properties": {}},
                      {"type": "object", "additionalProperties": False},
                      {"type": "object", "description": SECRET}, {"type": "object", "allOf": []}):
            with self.subTest(value=value), self.assertRaises(ValueError): player._empty_arguments_schema(value)

    def test_typed_projection_preserves_no_raw_identity_or_coordinates(self):
        result = player._projection(answer())
        self.assertTrue(result["player_exists"])
        self.assertTrue(result["canonical_player_form"])
        self.assertEqual(result["name_sha256"], hashlib.sha256(SECRET.encode()).hexdigest())
        self.assertEqual(result["name_characters"], len(SECRET))
        self.assertEqual(result["position_finite"], {"x": True, "y": True, "z": True})
        for private in (SECRET, str(UUID), str(COORDINATE), "42.125"):
            self.assertNotIn(private, json.dumps(result))

    def test_unsigned_integer_limits_and_bool_float_rejection(self):
        for key, maximum in (("uuid", 2**64-1), ("level", 65535)):
            for valid in (0, maximum):
                value = body(); value[key] = valid
                self.assertTrue(player._projection(answer(value))[key + ("_uint64_valid" if key == "uuid" else "_uint16_valid")])
            for bad in (-1, maximum+1, True, False, 1.0, "1", None):
                value = body(); value[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError): player._projection(answer(value))

    def test_finite_coordinates_and_huge_integer_fail_sanitized(self):
        for valid in (0, -1, 1.5, 1e30):
            value = body(); value["position"]["x"] = valid
            self.assertTrue(player._projection(answer(value))["position_finite"]["x"])
        for bad in (True, None, "0", float("nan"), float("inf"), -float("inf"), 10**400):
            value = body(); value["position"]["x"] = bad
            with self.subTest(bad=str(bad)[:30]), self.assertRaises(ValueError): player._projection(answer(value))
        raw = json.dumps(body()).replace(str(COORDINATE), "1e309")
        with self.assertRaises(ValueError): player._projection(answer(text=raw))

    def test_wrong_form_is_not_a_player_and_never_exports_returned_form(self):
        value = body(); value["formID"] = "0x00013491"
        result = player._projection(answer(value))
        self.assertFalse(result["canonical_player_form"]); self.assertIsNone(result["player_exists"])
        self.assertNotIn("00013491", json.dumps(result))
        for bad in ("0X00000014", "0x14", 20, "0x0000001a"):
            value["formID"] = bad
            with self.assertRaises(ValueError): player._projection(answer(value))

    def test_native_error_text_is_not_success_even_when_iserror_false(self):
        for text, reason in (("Error: Game is not ready yet", "game_not_ready"),
                             ("Error: Player not available", "player_not_available")):
            with self.assertRaises(player._Failure) as caught: player._projection(answer(text=text))
            self.assertEqual(caught.exception.reason, reason)

    def test_malformed_duplicate_missing_extra_fields_and_name_bounds_refuse(self):
        variants = []
        for key in body():
            value = body(); del value[key]; variants.append(value)
        variants.extend(({**body(), "cell": "QASmoke"}, {**body(), "position": {"x": 1, "y": 2}},
                         {**body(), "position": {"x": 1, "y": 2, "z": 3, "w": 4}}))
        for name in ("", None, "bad\nname", "x"*(player.MAX_NAME_BYTES+1), "\ud800"):
            variants.append({**body(), "name": name})
        for value in variants:
            with self.subTest(value=str(value)[:80]), self.assertRaises(ValueError): player._projection(answer(value))
        for text in ('{"uuid":1,"uuid":2}', 'NaN', '[]', 'private '+SECRET):
            with self.assertRaises(ValueError): player._projection(answer(text=text))
        for value in ({**answer(), "isError": 0}, {**answer(), "isError": True},
                      {**answer(), "extra": SECRET}, {"isError": False, "content": []},
                      {"isError": False, "content": answer()["content"]*2}):
            with self.assertRaises(ValueError): player._projection(value)
        with patch.object(player, "MAX_TEXT", 2), self.assertRaises(ValueError): player._projection(answer())


class WireTests(unittest.TestCase):
    def wire(self, rows=None, connections=tcp):
        self.rows, self.activity = rows or sockets(), {}
        with patch.object(d.socket, "socket", side_effect=self.rows):
            return player._inspect(12, time.monotonic()+60, lambda: None, connections,
                d._schema_summary({"type": "object"}), self.activity)

    def test_exact_five_requests_one_player_call_no_credentials_or_proxy(self):
        with patch.dict("os.environ", {"HTTP_PROXY": SECRET, "ALL_PROXY": SECRET}): result = self.wire()
        self.assertTrue(result["player_exists"]); self.assertEqual(self.activity["requests_attempted"], 5)
        sent = [json.loads(s.sent[0].split(b"\r\n\r\n", 1)[1]) for s in self.rows[1:]]
        self.assertEqual(sent, list(player._messages()))
        self.assertEqual(sent[-1]["params"], {"name": "get_player_info", "arguments": {}})
        self.assertTrue(all(row.closed for row in self.rows))
        for row in self.rows:
            self.assertEqual(row.connected, [("127.0.0.1", 18889)])
            self.assertNotIn(b"Authorization", row.sent[0]); self.assertNotIn(b"Cookie", row.sent[0])
        self.assertNotIn(SESSION, json.dumps(result))

    def test_hash_covers_exact_response_json_not_canonical_reserialization(self):
        raw = json.dumps({"result": answer(), "id": 3, "jsonrpc": "2.0"}, indent=3)
        self.wire(sockets(raw_reply=raw))
        self.assertEqual(self.activity["raw_rpc_data_sha256"], hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(self.activity["raw_rpc_data_bytes"], len(raw.encode()))
        self.assertNotEqual(self.activity["raw_rpc_data_sha256"], player.tier._digest(json.loads(raw)))

    def test_wrong_tool_schema_case_alias_pagination_or_missing_blocks_before_call(self):
        variants = [inventory(name="get_plugins"), inventory(name="GET_PLAYER_INFO"), {"tools": []},
                    inventory({"type": "object", "properties": {}}), {**inventory(), "nextCursor": SECRET},
                    {"tools": inventory()["tools"]*2},
                    {"tools": inventory()["tools"] + inventory(name="GET_PLAYER_INFO")["tools"]}]
        for listed in variants:
            with self.subTest(listed=listed), self.assertRaises(player._Failure): self.wire(sockets(listed=listed))
            self.assertFalse(self.activity["tool_call_attempted"]); self.assertFalse(self.rows[4].sent)

    def test_foreign_peer_and_partial_send_no_retry(self):
        foreign = tcp(); foreign[-1]["pid"] = 999
        with self.assertRaises(player._Failure): self.wire(connections=lambda: foreign)
        self.assertFalse(self.activity["tool_call_attempted"])
        rows = sockets(); rows[4].sendall = lambda _: (_ for _ in ()).throw(OSError(SECRET))
        with self.assertRaises(player._Failure): self.wire(rows)
        self.assertTrue(self.activity["tool_call_attempted"]); self.assertEqual(self.activity["requests_attempted"], 5)
        self.assertIsNone(self.activity["raw_rpc_data_sha256"]); self.assertTrue(all(row.closed for row in rows))

    def test_wrong_id_duplicate_json_trailing_work_and_missing_reply_fail(self):
        for raw in ('{"jsonrpc":"2.0","id":3,"id":3,"result":{}}',
                    json.dumps({"jsonrpc":"2.0","id":4,"result":answer()}),
                    json.dumps({"jsonrpc":"2.0","id":3,"error":{"message":SECRET}})):
            with self.assertRaises(player._Failure): self.wire(sockets(raw_reply=raw))
            self.assertEqual(self.activity["raw_rpc_data_sha256"], hashlib.sha256(raw.encode()).hexdigest())
        with self.assertRaises(player._Failure): self.wire(sockets(chunked=False, tail=fixture.reply(3, answer())))
        rows = sockets(); rows[4].on_send = lambda _: None
        with self.assertRaises(player._Failure): self.wire(rows)
        self.assertTrue(self.activity["tool_call_attempted"])

    def test_arbitrary_calls_and_arguments_or_sixth_request_refused(self):
        rows = sockets()
        with patch.object(d.socket, "socket", side_effect=rows), player._Session(12,time.monotonic()+60,lambda:None,tcp) as session:
            session.post_next(); session.result(1); session.post_next(); session.post_next(); session.result(2)
            for params in ({"name":"get_plugins","arguments":{}}, {"name":"get_player_info","arguments":{"x":1}}):
                with self.assertRaises(ValueError): session._send(rows[4],"POST",session.endpoint,
                    d._wire({"jsonrpc":"2.0","id":3,"method":"tools/call","params":params}))
            with self.assertRaises(ValueError): session._send(rows[4],"POST",session.endpoint,d._wire(player._messages()[3]))
            session.schema_authorized=True; session.post_next(); session.result(3)
            with self.assertRaises(ValueError): session.post_next()
        self.assertEqual(session.requests_sent,5)


class ContextTests(unittest.TestCase):
    def save(self): self.path.write_text(json.dumps(self.capture))
    def setUp(self):
        fixture.ContextTests.setUp(self)
        self.kw["connection_probe"] = tcp
        base, _, _ = player.smoke._context(RUN, **self.kw)
        patcher = patch.dict(player.SOURCE_BASIS, {"dll_sha256": base["modules"]["skyrimnet.dll"]["sha256"]})
        patcher.start(); self.addCleanup(patcher.stop)
        binding, _, _ = d._context(RUN, self.path, **self.kw)
        self.discovery = {"version":1,"tier":player.tier.TIER,"operation":"mcp_discovery_capture",
            "run_id":RUN,"capture_id":"b"*32,"status":"tools_discovered","binding":binding,
            "binding_sha256":player.tier._digest(binding),"discovery_complete":True,"identity_stable":True,
            "observation_failure":None,"tools_call_requests_performed":False,"client_tools_call_enabled":False,
            "game_inspection_tools_called":False,"diagnostics":{"failure_stage":None,"failure_reason":None,
                "http_status":None,"final_context":"matched","total_deadline_exceeded":False,"duplicate_header":None},
            "observation":{"protocol":d.PROTOCOL,"methods":list(d.METHODS),"matched_response_ids":[1,2],
                "requests_sent":4,"received_bytes":500,"events_received":3,"initialization_sha256":"a"*64,
                **d._inventory(inventory())}}
        self.discovery_path = self.runtime / "mcp-discovery" / ("b"*32+".json")
        self.discovery_path.parent.mkdir(); self.save_discovery()
    def save_discovery(self): self.discovery_path.write_text(json.dumps(self.discovery))
    def plan(self): return player.player_plan(RUN,self.path,self.discovery_path,**self.kw)
    def collect(self, rows=None, token=None):
        self.rows = rows or sockets(); token = token or self.plan()["review_token"]
        with patch.object(d.socket,"socket",side_effect=self.rows):
            return player.collect_player(RUN,self.path,self.discovery_path,token,**self.kw)

    def test_readonly_plan_and_capture_preserve_inputs_and_redact_values(self):
        before = {str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(d.socket,"socket",side_effect=AssertionError("No socket")): plan=self.plan()
        self.assertEqual(plan["status"],"ready_for_one_player_snapshot")
        self.assertFalse(plan["writes_performed"]); self.assertFalse(plan["network_requests_performed"])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        result=self.collect(token=plan["review_token"])
        self.assertEqual(result["status"],"player_snapshot_observed")
        self.assertTrue(result["player_exists"]);self.assertEqual(result["tool_call_outcome"],"reply_validated")
        self.assertTrue(result["identity_bookkeeping_may_write"])
        for flag in ("exact_player_cell_verified","qasmoke_programmatically_verified","fresh_world_verified",
                     "runtime_verified","runtime_playback_verified","normal_actor_ai_behavior_verified",
                     "egress_verified","paid_generation","game_state_mutation_requested"):
            self.assertIs(result[flag],False)
        for private in (SECRET,SESSION,str(UUID),str(COORDINATE)):self.assertNotIn(private,json.dumps(result))
        path=self.runtime/"mcp-player"/(result["capture_id"]+".json")
        self.assertEqual(json.loads(path.read_text()),result)
        for path,raw in before.items():self.assertEqual(Path(path).read_bytes(),raw)

    def test_real_discovery_producer_and_compatibility_feed_one_player_call(self):
        rows=fixture.gated_sockets(fixture.sse(inventory=inventory()))
        with patch.object(d.socket,"socket",side_effect=rows):
            capture=d.collect_discovery(RUN,self.path,d.discovery_plan(RUN,self.path,**self.kw)["review_token"],**self.kw)
        self.discovery_path=self.runtime/"mcp-discovery"/(capture["capture_id"]+".json")
        rows=sockets();rows[0].raw=rows[0].raw.replace(b"Content-Type: text/event-stream\r\n",
            b"Content-Type: text/event-stream\r\n"*2,1)
        result=self.collect(rows)
        self.assertEqual(result["status"],"player_snapshot_observed")
        self.assertTrue(result["activity"]["sse_content_type_pair_normalized"])

    def test_invalid_wrong_run_wrong_tool_and_tampered_schema_captures_refuse(self):
        original=copy.deepcopy(self.discovery)
        changes=(lambda r:r.update(status="incomplete"),lambda r:r.update(run_id="wrong"),
            lambda r:r.update(identity_stable=1),lambda r:r.update(client_tools_call_enabled=True),
            lambda r:r["binding"].update(version=True),
            lambda r:r["diagnostics"].update(total_deadline_exceeded=0),
            lambda r:r["observation"].update(matched_response_ids=[True,2]),
            lambda r:r["observation"]["tools"][0].update(name="get_plugins"),
            lambda r:r["observation"]["tools"][0]["schema"].update(sha256="0"*64),
            lambda r:r["observation"]["tools"][0]["schema"].update(property_count=False))
        with patch.object(d.socket,"socket",side_effect=AssertionError("No socket")):
            for change in changes:
                self.discovery=copy.deepcopy(original);change(self.discovery);self.save_discovery()
                with self.assertRaises(ValueError):self.plan()

    def test_stale_capture_or_implementation_or_token_and_native_hash_refuse_before_send(self):
        token=self.plan()["review_token"]
        self.discovery["extra"]=SECRET;self.save_discovery()
        with self.assertRaises(ValueError):self.collect(token=token)
        self.assertFalse(any(row.sent for row in self.rows))
        with patch.dict(player.SOURCE_BASIS,{"dll_sha256":"0"*64}),self.assertRaises(ValueError):self.plan()
        with self.assertRaises(ValueError):self.collect(token="mcp-plugins-v1:"+"0"*64)
        token=self.plan()["review_token"]
        original=player._context
        def changed(*args,**kwargs):
            binding,run,launched=original(*args,**kwargs)
            binding["implementation"]["changed"]=True
            return binding,run,launched
        with patch.object(player,"_context",side_effect=changed),self.assertRaises(ValueError):self.collect(token=token)

    def test_partial_send_and_missing_reply_are_unknown_incomplete_retained_once(self):
        for mode in ("partial","ack_timeout","reply_missing"):
            rows=sockets()
            if mode=="partial": rows[4].sendall=lambda _:(_ for _ in ()).throw(OSError(SECRET))
            elif mode=="ack_timeout": rows[4].recv=lambda _:(_ for _ in ()).throw(TimeoutError(SECRET))
            else: rows[4].on_send=lambda _:None
            result=self.collect(rows)
            self.assertEqual(result["status"],"incomplete");self.assertEqual(result["tool_call_outcome"],"unknown")
            self.assertIsNone(result["player_exists"]);self.assertTrue(result["tools_call_requests_attempted"])
            self.assertEqual(result["activity"]["requests_attempted"],5)
            self.assertTrue(all(row.closed for row in rows));self.assertNotIn(SECRET,json.dumps(result))
        self.assertEqual(len(list((self.runtime/"mcp-player").glob("*.json"))),3)

    def test_valid_error_text_and_wrong_player_never_claim_existence(self):
        for text in ("Error: Game is not ready yet","Error: Player not available"):
            result=self.collect(sockets(result=answer(text=text)))
            self.assertEqual(result["status"],"incomplete");self.assertIsNone(result["player_exists"])
            self.assertEqual(result["tool_call_outcome"],"unknown")
            self.assertIsNotNone(result["activity"]["raw_rpc_data_sha256"])
        value=body();value["formID"]="0x00013491"
        result=self.collect(sockets(result=answer(value)))
        self.assertEqual(result["status"],"incomplete");self.assertIsNone(result["player_exists"])
        self.assertEqual(result["tool_call_outcome"],"reply_validated")

    def test_foreign_tool_schema_prevents_attempt_and_post_ack_is_strict(self):
        result=self.collect(sockets(listed=inventory(name="get_plugins")))
        self.assertEqual(result["tool_call_outcome"],"not_attempted")
        self.assertFalse(self.rows[4].sent)
        rows=sockets();rows[4].raw=(b"HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\n"
            b"Content-Type: text/event-stream\r\nContent-Type: text/event-stream\r\n\r\n")
        result=self.collect(rows)
        self.assertEqual(result["status"],"incomplete");self.assertEqual(result["diagnostics"]["failure_reason"],"header_duplicate")

    def test_final_identity_drift_cannot_claim_player_snapshot(self):
        rows=sockets();release=rows[4].on_send
        def change(raw):
            release(raw);self.processes[-1]["created_ticks"]+=1
        rows[4].on_send=change;result=self.collect(rows)
        self.assertEqual(result["status"],"incomplete");self.assertFalse(result["identity_stable"])
        self.assertIsNone(result["player_exists"])

    def test_final_context_or_last_socket_deadline_cannot_pass(self):
        clock=[100.0];calls=[];original=player._context;token=self.plan()["review_token"]
        def context(*args,**kwargs):
            value=original(*args,**kwargs);calls.append(True)
            if len(calls)==2:clock[0]+=player.TOTAL_SECONDS
            return value
        with patch.object(player,"_context",side_effect=context),patch.object(player.time,"monotonic",side_effect=lambda:clock[0]):
            result=self.collect(token=token)
        self.assertEqual(result["status"],"incomplete");self.assertTrue(result["diagnostics"]["total_deadline_exceeded"])
        rows=sockets();release=rows[4].on_send;clock[0]=100
        def late(raw):release(raw);clock[0]+=61
        rows[4].on_send=late
        with patch.object(player.time,"monotonic",side_effect=lambda:clock[0]):result=self.collect(rows)
        self.assertEqual(result["status"],"incomplete");self.assertTrue(result["tools_call_requests_attempted"])


class CLITests(unittest.TestCase):
    def test_cli_requires_review_and_sanitizes_error(self):
        with self.assertRaises(SystemExit),patch("sys.stderr",new_callable=io.StringIO):
            cli.main(["collect","--run-id",RUN,"--smoke-capture","a","--discovery-capture","b"])
        with patch.object(player,"player_plan",side_effect=ValueError(SECRET)),patch("sys.stdout",new_callable=io.StringIO) as output:
            self.assertEqual(cli.main(["plan","--run-id",RUN,"--smoke-capture","a","--discovery-capture","b"]),1)
        self.assertNotIn(SECRET,output.getvalue())
    def test_plan_success_exit_code(self):
        with patch.object(player,"player_plan",return_value={"status":"ready_for_one_player_snapshot"}),patch("sys.stdout",new_callable=io.StringIO):
            self.assertEqual(cli.main(["plan","--run-id",RUN,"--smoke-capture","a","--discovery-capture","b"]),0)


if __name__ == "__main__": unittest.main()
