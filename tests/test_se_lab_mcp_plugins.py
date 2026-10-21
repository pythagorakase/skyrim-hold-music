import copy
import hashlib
import io
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from hold_music import se_lab_mcp_plugins as plugins
from tools import se_lab_mcp_plugins as cli
import test_se_lab_mcp_discovery as fixture

d = plugins.discovery
SECRET, SESSION, RUN = fixture.SECRET, fixture.SESSION, fixture.RUN
EXPECTED = [*plugins.tier.BASE_PLUGINS, "SkyrimNet.esp"]


def inventory(schema=None):
    return {"tools": [{"name": "get_plugins", "description": SECRET,
                       "inputSchema": schema if schema is not None else {"type": "object"}}]}


def answer(names=None):
    return {"isError": False, "content": [{"type": "text", "text": json.dumps(
        names if names is not None else ["Skyrim.esm", *EXPECTED, SECRET + ".esp"], indent=2)}]}


def tcp():
    return fixture.tcp() + [dict(local_address="127.0.0.1", local_port=18889,
        remote_address="127.0.0.1", remote_port=53127, state="Established", pid=12)]


def sockets(*, listed=None, result=None, initialized=None, endpoint=None, chunked=True, tail=b""):
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
    rows[4].on_send = lambda _: setattr(stream, "raw", stream.raw + frame(fixture.reply(3,
        result if result is not None else answer()) + tail))
    return rows


class SchemaAndProjectionTests(unittest.TestCase):
    def test_understood_empty_object_schemas_only(self):
        for value in ({"type": "object"}, {"type": "object", "properties": {}, "required": [],
                "additionalProperties": False, "description": SECRET}):
            self.assertEqual(plugins._empty_arguments_schema(value)["required_count"], 0)
        for value in ({}, True, {"type": ["object"]}, {"type": "object", "properties": []},
                {"type": "object", "required": {}}, {"type": "object", "minProperties": 1},
                {"type": "object", "enum": [{"x": 1}]}, {"type": "object", "allOf": []},
                {"type": "object", "$ref": SECRET}, {"type": "object", "const": {}},
                {"type": "object", "additionalProperties": {}},
                {"type": "object", "properties": {"optional": {"type": "string"}}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plugins._empty_arguments_schema(value)

    def test_projection_contains_only_pinned_names_counts_and_hashes(self):
        result = plugins._projection(answer(), EXPECTED)
        self.assertTrue(result["all_expected_present"])
        self.assertEqual(result["other_plugin_count"], 2)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn("Skyrim.esm", json.dumps(result))
        missing = plugins._projection(answer(["Skyrim.esm"]), EXPECTED)
        self.assertFalse(missing["all_expected_present"])
        self.assertEqual(missing["plugin_count"], 1)
        underscore = plugins._projection(answer(["_ResourcePack.esl", *EXPECTED]), EXPECTED)
        self.assertTrue(underscore["all_expected_present"])
        self.assertEqual(underscore["other_plugin_count"], 1)
        self.assertNotIn("_ResourcePack", json.dumps(underscore))

    def test_readiness_error_false_iserror_and_unsupported_envelopes_refused(self):
        bad = [answer([]), answer()]
        bad[0]["content"][0]["text"] = "Error: Game is not ready yet"
        bad[1]["isError"] = True
        for result in bad + [{"content": []}, {"isError": False, "structuredContent": []},
            {**answer(), "extra": SECRET}, {"isError": 0, "content": answer()["content"]},
            {"isError": False, "content": answer()["content"] * 2},
            {"isError": False, "content": [{"type": "image", "text": SECRET}]},
            {"isError": False, "content": [{"type": "text", "text": "{}"}]},
            {"isError": False, "content": [{"type": "text", "text": "NaN"}]}]:
            with self.subTest(result=result), self.assertRaises(ValueError):
                plugins._projection(result, EXPECTED)

    def test_filename_boundaries_and_aliases_refused_without_export(self):
        for names in (["A.esp", "a.ESP"], ["../private.esp"], ["C:\\private.esp"],
            ["bad\n.esp"], [None], [{"name": "Skyrim.esm"}], ["x.txt"], [SESSION + ".esp"],
            ["a" * 260 + ".esp"], ["x.esp"] * (plugins.MAX_PLUGINS + 1)):
            with self.subTest(names=names[:2]), self.assertRaises(ValueError):
                plugins._projection(answer(names), EXPECTED, (SESSION,))
        with patch.object(plugins, "MAX_TEXT", 3), self.assertRaises(ValueError):
            plugins._projection(answer(), EXPECTED)


class WireTests(unittest.TestCase):
    def wire(self, rows=None, schema=None, connections=tcp):
        self.rows = rows or sockets()
        self.activity = {}
        with patch.object(d.socket, "socket", side_effect=self.rows):
            return plugins._inspect(12, time.monotonic() + 60, lambda: None, connections,
                schema or d._schema_summary({"type": "object"}), EXPECTED, self.activity)

    def test_fixed_five_requests_one_empty_argument_call_no_credentials(self):
        with patch.dict("os.environ", {"HTTP_PROXY": SECRET, "ALL_PROXY": SECRET}):
            result = self.wire()
        self.assertTrue(result["all_expected_present"])
        self.assertEqual(self.activity["requests_attempted"], 5)
        self.assertTrue(self.activity["tool_call_attempted"])
        sent = [json.loads(row.sent[0].split(b"\r\n\r\n", 1)[1]) for row in self.rows[1:]]
        self.assertEqual(sent, list(plugins._messages()))
        self.assertEqual(sent[-1], {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "get_plugins", "arguments": {}}})
        self.assertTrue(all(row.closed for row in self.rows))
        for row in self.rows:
            self.assertEqual(row.connected, [("127.0.0.1", 18889)])
            self.assertNotIn(b"Authorization", row.sent[0]); self.assertNotIn(b"Cookie", row.sent[0])
        self.assertNotIn(SECRET, json.dumps(result)); self.assertNotIn(SESSION, json.dumps(result))

    def test_schema_drift_unknown_constraints_pagination_missing_duplicate_block_before_call(self):
        bad = [inventory({"type": "object", "description": SECRET}),
               inventory({"type": "object", "minProperties": 1}), {"tools": []},
               {**inventory(), "nextCursor": SECRET}, {"tools": inventory()["tools"] * 2}]
        bad.append({"tools": [{"name": "GET_PLUGINS", "inputSchema": {"type": "object"}}]})
        for listed in bad:
            with self.subTest(listed=listed), self.assertRaises(plugins._Failure):
                self.wire(sockets(listed=listed))
            self.assertFalse(self.activity["tool_call_attempted"])
            self.assertFalse(self.rows[4].sent)
        hidden = {"type": "object", "not": {}}
        with self.assertRaises(plugins._Failure):
            self.wire(sockets(listed=inventory(hidden)), schema=d._schema_summary(hidden))
        self.assertFalse(self.rows[4].sent)

    def test_foreign_tool_post_peer_and_partial_send_never_retry(self):
        rows = tcp(); rows[-1]["pid"] = 99
        with self.assertRaises(plugins._Failure): self.wire(connections=lambda: rows)
        self.assertFalse(self.activity["tool_call_attempted"])
        self.assertFalse(self.rows[4].sent)
        raw = sockets(); raw[4].sendall = lambda _: (_ for _ in ()).throw(OSError(SECRET))
        with self.assertRaises(plugins._Failure): self.wire(raw)
        self.assertTrue(self.activity["tool_call_attempted"])
        self.assertEqual(self.activity["requests_attempted"], 5)
        self.assertTrue(all(row.closed for row in raw))

    def test_wrong_reply_server_request_and_trailing_work_are_not_success(self):
        for tail in (fixture.reply(3, answer()), fixture.event("message", json.dumps(
            {"jsonrpc": "2.0", "id": 4, "method": "sampling/createMessage", "params": {}}))):
            with self.assertRaises(plugins._Failure): self.wire(sockets(tail=tail, chunked=False))
        raw = sockets()
        raw[4].on_send = lambda _: setattr(raw[0], "raw", fixture.reply(2, answer()))
        # Nonchunked fixture avoids hiding the wrong ID behind malformed chunking.
        raw = sockets(chunked=False)
        raw[4].on_send = lambda _: setattr(raw[0], "raw", fixture.reply(2, answer()))
        with self.assertRaises(plugins._Failure): self.wire(raw)
        self.assertTrue(self.activity["tool_call_attempted"])

    def test_transport_does_not_allow_call_before_schema_or_sixth_request(self):
        raw = sockets()
        with patch.object(d.socket, "socket", side_effect=raw), plugins._Session(
                12, time.monotonic() + 60, lambda: None, tcp) as session:
            session.post_next(); session.result(1)
            session.post_next(); session.post_next(); session.result(2)
            with self.assertRaises(ValueError): session.post_next()
            self.assertFalse(raw[4].sent)
            session.schema_authorized = True
            # Failed unauthorized dispatch consumed a connection, not a request.
            with patch.object(d.socket, "socket", return_value=raw[4]):
                session.post_next(); session.result(3)
            with self.assertRaises(ValueError): session.post_next()
            with self.assertRaises(ValueError): session._send(raw[4], "GET", "/sse")
        self.assertEqual(session.requests_sent, 5)


class ContextTests(unittest.TestCase):
    def save(self): self.path.write_text(json.dumps(self.capture))

    def setUp(self):
        fixture.ContextTests.setUp(self)
        self.kw["connection_probe"] = tcp
        relative = "profiles/" + plugins.tier.PROFILE + "/plugins.txt"
        self.profile = self.root / plugins.tier.INSTANCE / relative
        self.profile.parent.mkdir(parents=True)
        self.profile.write_bytes("".join("*" + name + "\n" for name in EXPECTED).encode())
        run_path = self.runtime / "run.json"
        run = json.loads(run_path.read_text())
        run["inputs"]["instance"]["files"][relative] = {"sha256": hashlib.sha256(self.profile.read_bytes()).hexdigest()}
        run["inputs_sha256"] = plugins.tier._digest(run["inputs"])
        run_path.write_text(json.dumps(run))
        base, _, _ = plugins.smoke._context(RUN, **self.kw)
        self.capture["binding"] = base; self.capture["binding_sha256"] = plugins.tier._digest(base); self.save()
        patcher = patch.dict(plugins.SOURCE_BASIS, {"dll_sha256": base["modules"]["skyrimnet.dll"]["sha256"]})
        patcher.start(); self.addCleanup(patcher.stop)
        binding, _, _ = d._context(RUN, self.path, **self.kw)
        self.discovery = {"version": 1, "tier": plugins.tier.TIER, "operation": "mcp_discovery_capture",
            "run_id": RUN, "capture_id": "b" * 32, "status": "tools_discovered", "binding": binding,
            "binding_sha256": plugins.tier._digest(binding), "discovery_complete": True,
            "identity_stable": True, "observation_failure": None, "tools_call_requests_performed": False,
            "client_tools_call_enabled": False, "game_inspection_tools_called": False,
            "diagnostics": {"failure_stage": None, "failure_reason": None, "http_status": None,
                "final_context": "matched", "total_deadline_exceeded": False, "duplicate_header": None},
            "observation": {"protocol": d.PROTOCOL, "methods": list(d.METHODS), "matched_response_ids": [1, 2],
                "requests_sent": 4, "received_bytes": 500, "events_received": 3,
                "initialization_sha256": "a" * 64, **d._inventory(inventory())}}
        self.discovery_path = self.runtime / "mcp-discovery" / ("b" * 32 + ".json")
        self.discovery_path.parent.mkdir(); self.save_discovery()

    def save_discovery(self): self.discovery_path.write_text(json.dumps(self.discovery))
    def plan(self): return plugins.plugins_plan(RUN, self.path, self.discovery_path, **self.kw)
    def collect(self, rows=None, token=None):
        self.rows = rows or sockets()
        token = token or self.plan()["review_token"]
        with patch.object(d.socket, "socket", side_effect=self.rows):
            return plugins.collect_plugins(RUN, self.path, self.discovery_path, token, **self.kw)

    def test_readonly_plan_and_successful_retained_capture_no_raw_data(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(d.socket, "socket", side_effect=AssertionError("No socket")):
            plan = self.plan()
        self.assertFalse(plan["network_requests_performed"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        result = self.collect(token=plan["review_token"])
        self.assertEqual(result["status"], "expected_plugins_observed")
        self.assertTrue(result["tools_call_requests_attempted"])
        self.assertTrue(result["game_inspection_reply_validated"])
        for flag in ("runtime_verified", "runtime_playback_verified", "native_initialization_verified", "egress_verified", "paid_generation"):
            self.assertIs(result[flag], False)
        self.assertNotIn(SECRET, json.dumps(result)); self.assertNotIn(SESSION, json.dumps(result))
        output = self.runtime / "mcp-plugins" / (result["capture_id"] + ".json")
        self.assertEqual(json.loads(output.read_text()), result)
        for name, content in before.items(): self.assertEqual(Path(name).read_bytes(), content)

    def test_real_discovery_producer_capture_and_pinned_sse_pair_feed_one_query(self):
        # Exercise the real retained-report contract, rather than only a hand
        # assembled fixture that could drift from the upstream producer.
        discovery_sockets = fixture.gated_sockets(fixture.sse(inventory=inventory()))
        with patch.object(d.socket, "socket", side_effect=discovery_sockets):
            capture = d.collect_discovery(RUN, self.path, d.discovery_plan(RUN, self.path, **self.kw)["review_token"], **self.kw)
        self.assertEqual(capture["status"], "tools_discovered")
        self.discovery_path = self.runtime / "mcp-discovery" / (capture["capture_id"] + ".json")
        raw = sockets()
        raw[0].raw = raw[0].raw.replace(b"Content-Type: text/event-stream\r\n",
            b"Content-Type: text/event-stream\r\nContent-Type: text/event-stream\r\n", 1)
        result = self.collect(raw)
        self.assertEqual(result["status"], "expected_plugins_observed")
        self.assertTrue(result["activity"]["sse_content_type_pair_normalized"])
        self.assertEqual(result["activity"]["requests_attempted"], 5)

    def test_sse_compatibility_is_not_applied_to_post_acknowledgements(self):
        raw = sockets()
        raw[4].raw = (b"HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\n"
            b"Content-Type: text/event-stream\r\nContent-Type: text/event-stream\r\n\r\n")
        result = self.collect(raw)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["diagnostics"]["failure_reason"], "header_duplicate")
        self.assertTrue(result["tools_call_requests_attempted"])
        self.assertEqual(result["activity"]["requests_attempted"], 5)
        self.assertFalse(result["activity"]["sse_content_type_pair_normalized"])

    def test_incomplete_wrong_run_or_changed_capture_refuses_before_network(self):
        original = copy.deepcopy(self.discovery)
        for key, value in (("status", "incomplete"), ("run_id", "wrong"), ("identity_stable", 1),
                ("discovery_complete", False), ("observation_failure", SECRET), ("tools_call_requests_performed", True)):
            self.discovery = copy.deepcopy(original); self.discovery[key] = value; self.save_discovery()
            with self.subTest(key=key), self.assertRaises(ValueError): self.plan()
        self.discovery = original; self.save_discovery(); token = self.plan()["review_token"]
        self.discovery["extra"] = SECRET; self.save_discovery()
        with self.assertRaises(ValueError): self.collect(token=token)
        self.assertFalse(any(row.sent for row in self.rows))

    def test_profile_changed_unpinned_implementation_or_cross_operation_token_refuses(self):
        token = self.plan()["review_token"]
        self.profile.write_bytes(self.profile.read_bytes() + b"*Foreign.esp\n")
        with self.assertRaises(ValueError): self.collect(token=token)
        self.assertFalse(any(row.sent for row in self.rows))
        self.profile.write_bytes("".join("*" + name + "\n" for name in EXPECTED).encode())
        with patch.dict(plugins.SOURCE_BASIS, {"dll_sha256": "0" * 64}), self.assertRaises(ValueError): self.plan()
        with self.assertRaises(ValueError): self.collect(token="mcp-discovery-v1:" + "0" * 64)

    def test_malformed_or_contradictory_retained_evidence_refuses_before_network(self):
        original = copy.deepcopy(self.discovery)
        changes = (
            lambda r: r["diagnostics"].update(failure_stage="sse_headers", failure_reason="header_duplicate"),
            lambda r: r["diagnostics"].update(total_deadline_exceeded=True),
            lambda r: r["diagnostics"].update(total_deadline_exceeded=0),
            lambda r: r["observation"].update(matched_response_ids=[True, 2]),
            lambda r: r["observation"]["tools"][0]["schema"].update(property_count=False),
            lambda r: r["binding"].update(version=True),
            lambda r: r["observation"].update(initialization_sha256=SECRET),
            lambda r: r["observation"].update(received_bytes=0),
            lambda r: r["observation"].update(events_received=2),
            lambda r: r.update(client_tools_call_enabled=True),
        )
        with patch.object(d.socket, "socket", side_effect=AssertionError("No socket")):
            for index, change in enumerate(changes):
                self.discovery = copy.deepcopy(original); change(self.discovery); self.save_discovery()
                with self.subTest(case=index), self.assertRaises(ValueError): self.plan()

    def test_arbitrary_profile_comments_bom_crlf_and_reordering_are_not_silently_adopted(self):
        original = self.profile.read_bytes()
        for raw in (b"# generated comment\n" + original, b"\xef\xbb\xbf" + original,
                    original.replace(b"\n", b"\r\n"), b"\n".join(original.splitlines()[::-1]) + b"\n"):
            self.profile.write_bytes(raw)
            with self.subTest(raw=raw[:20]), patch.object(d.socket, "socket", side_effect=AssertionError("No socket")), self.assertRaises(ValueError):
                self.plan()

    def test_exact_native_mo2_header_binds_observed_and_original_bytes_separately(self):
        original = self.profile.read_bytes()
        old_token = self.plan()["review_token"]
        self.assertEqual(len(plugins.MO2_PLUGIN_HEADER), 106)
        self.profile.write_bytes(plugins.MO2_PLUGIN_HEADER + original)
        plan = self.plan()
        profile = plan["binding"]["profile"]
        self.assertEqual(profile["pinned_sha256"], "af9ad064b5f82cd3a36cfc01c4a3c4ce262b2cd4ed323f1f111631d678e7c111")
        self.assertEqual(profile["sha256"], "bcbf16a82bfd40cd0a226de7f904fa0fa10310e8946566e920950155f6fedccd")
        self.assertEqual(profile["observed_form"], "mo2_downloaded_content_header")
        self.assertIs(profile["byte_identical_to_launch"], False)
        with self.assertRaises(ValueError): self.collect(token=old_token)
        self.assertFalse(any(row.sent for row in self.rows))
        self.assertEqual(self.collect(token=plan["review_token"])["status"], "expected_plugins_observed")

    def test_header_compatibility_never_adopts_a_forged_launch_pin(self):
        run = json.loads((self.runtime / "run.json").read_text())
        relative = "profiles/" + plugins.tier.PROFILE + "/plugins.txt"
        self.profile.write_bytes(plugins.MO2_PLUGIN_HEADER + self.profile.read_bytes())
        for pin in ("0" * 64, hashlib.sha256(self.profile.read_bytes()).hexdigest(), None):
            run["inputs"]["instance"]["files"][relative]["sha256"] = pin
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                plugins._profile(plugins.tier._Snapshot(), run)

    def test_header_transition_during_call_fails_final_context(self):
        raw = sockets(); release = raw[4].on_send
        def change(request):
            release(request)
            self.profile.write_bytes(plugins.MO2_PLUGIN_HEADER + self.profile.read_bytes())
        raw[4].on_send = change
        result = self.collect(raw)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["diagnostics"]["final_context"], "changed")
        self.assertTrue(result["game_inspection_reply_validated"])

    def test_missing_expected_plugins_and_readiness_error_remain_incomplete(self):
        missing = self.collect(sockets(result=answer(["Skyrim.esm"])))
        self.assertEqual(missing["status"], "incomplete")
        self.assertTrue(missing["game_inspection_reply_validated"])
        error = answer(); error["content"][0]["text"] = "Error: Game is not ready yet"
        result = self.collect(sockets(result=error))
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["diagnostics"]["failure_stage"], "plugins_validation")
        self.assertEqual(result["diagnostics"]["failure_reason"], "game_not_ready")
        self.assertIsNone(result["observation"])
        self.assertTrue(result["tools_call_requests_attempted"])

    def test_final_identity_and_profile_drift_downgrade_after_valid_reply(self):
        for kind in ("process", "profile"):
            raw = sockets(); release = raw[4].on_send
            def change(request):
                release(request)
                if kind == "process": self.processes[-1]["created_ticks"] += 1
                else: self.profile.write_bytes(self.profile.read_bytes() + b"# drift\n")
            raw[4].on_send = change
            with self.subTest(kind=kind):
                result = self.collect(raw)
                self.assertEqual(result["status"], "incomplete")
                self.assertFalse(result["identity_stable"])
            if kind == "process": self.processes[-1]["created_ticks"] -= 1

    def test_final_context_over_deadline_cannot_pass(self):
        clock = [100.0]; calls = []; original = plugins._context
        token = self.plan()["review_token"]
        def context(*args, **kwargs):
            value = original(*args, **kwargs); calls.append(True)
            if len(calls) == 2: clock[0] += plugins.TOTAL_SECONDS
            return value
        with patch.object(plugins, "_context", side_effect=context), patch.object(plugins.time, "monotonic", side_effect=lambda: clock[0]):
            result = self.collect(token=token)
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["diagnostics"]["total_deadline_exceeded"])


class CLITests(unittest.TestCase):
    def test_cli_requires_explicit_capture_and_review_and_redacts_exception(self):
        with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO):
            cli.main(["collect", "--run-id", RUN, "--smoke-capture", "a", "--discovery-capture", "b"])
        with patch.object(plugins, "plugins_plan", side_effect=ValueError(SECRET)), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(cli.main(["plan", "--run-id", RUN, "--smoke-capture", "a", "--discovery-capture", "b"]), 1)
        self.assertNotIn(SECRET, output.getvalue())


if __name__ == "__main__":
    unittest.main()
