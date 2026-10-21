import copy
import io
import json
import time
import unittest
from unittest.mock import patch

from hold_music import se_lab_skyrimnet_routing as routing
from tools import se_lab_skyrimnet_routing as cli
import test_se_lab_skyrimnet_smoke as fixture

SECRET = "PRIVATE-KEY-MODEL-ENDPOINT-SENTINEL"


def payloads():
    provider = dict(id="local", name=SECRET, endpoint=routing.tier.LOOPBACK, api_key="",
        api_style="chat", use_sse=False, provider_settings={})
    slot = dict(provider_id="local", enabled=True, routing_role="primary", provider_settings={})
    root = dict(endpoint=routing.tier.LOOPBACK, api_key="", model_name=routing.EXPECTED_MODEL,
        model_params=[slot], default_params={}, variants={}, rotation_mode="sequential",
        timeout=30, connect_timeout=5, max_retries=0)
    return [{"data": {"openrouter": root, "active_preset_id": SECRET}},
            {"data": {"providers": [provider]}}, {"fields": []}, {"fields": []}]


def encoded(values): return [json.dumps(v).encode() for v in values]


class GraphTests(unittest.TestCase):
    def audit(self, values):
        report = routing._audit_graph(encoded(values))
        self.assertNotIn(SECRET, json.dumps(report))
        self.assertNotIn(routing.tier.LOOPBACK, json.dumps(report))
        self.assertNotIn(routing.EXPECTED_MODEL, json.dumps(report))
        return report

    def test_explicit_complete_graph_has_only_fixed_projection(self):
        report = self.audit(payloads())
        self.assertTrue(report["configured_graph_fake_only"])
        self.assertEqual(report["counts"]["slots"], 1)
        self.assertFalse(report["preset_label_used_as_evidence"])
        self.assertFalse(report["native_fallback_verified"])

    def test_root_route_audited_even_when_provider_is_fake(self):
        for key in ("endpoint", "api_key"):
            data=payloads(); data[0]["data"]["openrouter"][key]=SECRET
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_legacy_endpoint_and_key_require_observed_values_despite_schema_defaults(self):
        for key,default in (("endpoint",routing.tier.LOOPBACK),("api_key","")):
            data=payloads();del data[0]["data"]["openrouter"][key]
            data[2]["fields"]=[dict(path="openrouter."+key,type="string",defaultValue=default)]
            with self.subTest(key=key):
                report=self.audit(data)
                self.assertFalse(report["configured_graph_fake_only"])
                self.assertEqual(report["counts"]["schema_defaults_used"],0)
                self.assertIn("missing_explicit_or_schema_value",report["issues"])

    def test_oversized_provider_list_reports_skipped_coverage_honestly(self):
        data=payloads();data[1]["data"]["providers"]*=257
        report=self.audit(data)
        self.assertFalse(report["configured_graph_fake_only"])
        self.assertFalse(report["all_returned_providers_audited"])
        self.assertEqual(report["counts"]["providers_returned"],257)
        self.assertEqual(report["counts"]["providers_skipped"],257)
        self.assertEqual(report["counts"]["providers"],0)

    def test_skipped_variant_or_slot_collections_report_incomplete_coverage(self):
        for field,value in (("model_params",[{}]*257),("model_params",SECRET),
                            ("variants",{str(i):{} for i in range(257)}),("variants",[])):
            data=payloads();data[0]["data"]["openrouter"][field]=value
            with self.subTest(field=field,value_type=type(value).__name__):
                report=self.audit(data)
                self.assertFalse(report["configured_graph_fake_only"])
                self.assertFalse(report["disabled_and_backup_slots_audited"])

    def test_disabled_backup_and_unreferenced_providers_are_not_exempt(self):
        data=payloads(); root=data[0]["data"]["openrouter"]
        root["model_params"][0].update(enabled=False,routing_role="backup")
        data[1]["data"]["providers"][0]["endpoint"]=SECRET
        report=self.audit(data)
        self.assertFalse(report["configured_graph_fake_only"])
        self.assertEqual(report["counts"]["disabled_slots"],1)
        self.assertEqual(report["counts"]["backup_slots"],1)
        data=payloads(); extra=copy.deepcopy(data[1]["data"]["providers"][0])
        extra.update(id=SECRET,api_key=SECRET);data[1]["data"]["providers"].append(extra)
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_every_variant_checked_without_preset_label_trust(self):
        data=payloads(); root=data[0]["data"]["openrouter"]
        root["variants"][SECRET]=dict(model_name=SECRET,model_params=[copy.deepcopy(root["model_params"][0])],default_params={})
        report=self.audit(data)
        self.assertEqual(report["counts"]["rotations"],2)
        self.assertFalse(report["configured_graph_fake_only"])

    def test_model_slots_must_align_and_names_are_not_params_keys(self):
        for change in ("extra_name","extra_params","empty_name","numeric_name","name_in_params"):
            data=payloads();root=data[0]["data"]["openrouter"]
            if change=="extra_name":root["model_name"]+=","+routing.EXPECTED_MODEL
            if change=="extra_params":root["model_params"].append({})
            if change=="empty_name":root["model_name"]+=","
            if change=="numeric_name":root["model_name"]=123
            if change=="name_in_params":root["model_params"][0]["name"]=SECRET
            with self.subTest(change=change):self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_duplicate_missing_and_borrowed_provider_references(self):
        for change in ("duplicate","missing","loan","loan_missing","loan_secret"):
            data=payloads(); records=data[1]["data"]["providers"]
            if change=="duplicate":records.append(copy.deepcopy(records[0]))
            elif change=="missing":data[0]["data"]["openrouter"]["model_params"][0]["provider_id"]=SECRET
            else:
                records[0]["api_key_from"]="local" if change!="loan_missing" else SECRET
                if change=="loan_secret":records[0]["api_key"]=SECRET
            with self.subTest(change=change):self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_provider_and_slot_passthrough_never_certified(self):
        for target in ("provider","slot"):
            for body in ({"provider":{"order":[SECRET]}},SECRET,None):
                data=payloads(); record=(data[1]["data"]["providers"][0] if target=="provider" else data[0]["data"]["openrouter"]["model_params"][0])
                record["provider_settings"]=body
                with self.subTest(target=target,body=type(body).__name__):self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_unknown_keys_types_and_dynamic_schema_defaults_are_not_exported(self):
        for where in ("root","slot","provider","schema"):
            data=payloads()
            if where=="root":data[0]["data"]["openrouter"][SECRET]=SECRET
            if where=="slot":data[0]["data"]["openrouter"]["model_params"][0]["enabled"]=SECRET
            if where=="provider":data[1]["data"]["providers"][0][SECRET]=SECRET
            if where=="schema":data[2]={"fields":[{"path":"openrouter.timeout","type":SECRET,"defaultValue":SECRET}]}
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_missing_controls_only_use_exact_typed_schema_defaults(self):
        data=payloads(); del data[0]["data"]["openrouter"]["timeout"]
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        data[2]["fields"]=[dict(path="openrouter.timeout",type="int",defaultValue=30)]
        self.assertTrue(self.audit(data)["configured_graph_fake_only"])
        data[2]["fields"][0]["path"]="elsewhere.timeout"
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        data[2]["fields"][0].update(path="openrouter.timeout",defaultValue=SECRET)
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_schema_duplicate_path_and_type_disagreement_refuse(self):
        for fields in ([dict(path="openrouter.timeout",type="string")],
                       [dict(path="openrouter.timeout",type="int")]*2):
            data=payloads();data[2]["fields"]=fields
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_variant_timeout_inheritance_remains_explicitly_unresolved(self):
        data=payloads();root=data[0]["data"]["openrouter"]
        root["variants"]["scene"]=dict(model_name=routing.EXPECTED_MODEL,model_params=copy.deepcopy(root["model_params"]),default_params={},timeout=10)
        self.assertIn("native_timeout_inheritance_unresolved",self.audit(data)["issues"])
        root["variants"]["scene"]["model_params"][0]["request_timeout"]=12
        self.assertTrue(self.audit(data)["configured_graph_fake_only"])
        root["variants"]["scene"]["timeout"]=SECRET
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_invalid_retry_rotation_and_nonfinite_numbers(self):
        for key,value in (("timeout",False),("timeout",0),("max_retries",-1),("max_retries","0"),("rotation_mode",SECRET)):
            data=payloads();data[0]["data"]["openrouter"][key]=value
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        raw=encoded(payloads());raw[0]=b'{"data":{"openrouter":{"timeout":NaN}}}'
        with self.assertRaises(ValueError):routing._audit_graph(raw)

    def test_seed_is_not_mistaken_for_complete_effective_routing(self):
        data=payloads();data[0]["data"]=json.loads(routing.tier.configuration_seeds()[routing.tier.CONFIG+"OpenRouter.yaml"])
        data[1]["data"]=json.loads(routing.tier.configuration_seeds()[routing.tier.CONFIG+"Providers.yaml"])
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_huge_integer_and_private_schema_envelope_fail_without_exception_leak(self):
        data=payloads();data[0]["data"]["openrouter"]["timeout"]=10**500
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        data=payloads();data[3]={"error":SECRET,"data":SECRET}
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])


class CollectorTests(unittest.TestCase):
    write_documents=fixture.SmokeTests.write_documents

    def setUp(self):
        fixture.SmokeTests.setUp(self)
        plan=routing.smoke.smoke_plan(fixture.RUN,**self.kw)
        report=routing.smoke.collect_smoke(fixture.RUN,plan["review_token"],transport=lambda route,*args:json.dumps(fixture.response(route.split("name=")[1])).encode(),**self.kw)
        self.capture=self.runtime/"smoke"/(report["capture_id"]+".json")
        self.data=payloads();self.calls=[]

    def plan(self):return routing.routing_plan(fixture.RUN,self.capture,**self.kw)
    def transport(self,route,*args):
        self.calls.append(route);return encoded(self.data)[routing.ROUTES.index(route)]
    def collect(self,token=None,transport=None):
        return routing.collect_routing(fixture.RUN,self.capture,token or self.plan()["review_token"],transport=transport or self.transport,**self.kw)

    def test_plan_no_network_or_writes(self):
        before={p:p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(routing.socket,"socket",side_effect=AssertionError("no sockets")):self.plan()
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_four_gets_and_sanitized_retained_capture(self):
        report=self.collect()
        self.assertEqual(self.calls,list(routing.ROUTES))
        self.assertEqual(report["status"],"configured_graph_fake_only_observed")
        for key in ("diagnostic_ready","native_fallback_verified","egress_verified","provider_requests_performed"):self.assertFalse(report[key])
        saved=self.runtime/"routing"/(report["capture_id"]+".json")
        self.assertNotIn(SECRET,saved.read_text())
        self.assertEqual(len(report["audit"]["responses"]),4)

    def test_stale_cross_operation_unicode_and_changed_smoke_send_nothing(self):
        for token in ("é","mcp-discovery-v1:x","wrong"):
            with self.assertRaises(ValueError):self.collect(token)
        token=self.plan()["review_token"]
        doc=json.loads(self.capture.read_text());doc["disabled_controls_observed"]=False
        self.capture.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):self.collect(token)
        self.assertFalse(self.calls)

    def test_exit_or_module_drift_invalidates_even_positive_graph(self):
        def transport(route,*args):
            raw=self.transport(route,*args)
            if len(self.calls)==4:Path(self.modules[0]["path"]).write_bytes(b"changed")
            return raw
        from pathlib import Path
        report=self.collect(transport=transport)
        self.assertFalse(report["configured_graph_fake_only_observed"])
        self.assertFalse(report["identity_stable"])

    def test_private_transport_errors_not_exported_or_retried(self):
        def bad(*args):raise ValueError(SECRET)
        report=self.collect(transport=bad)
        self.assertNotIn(SECRET,json.dumps(report));self.assertEqual(report["request_attempt_count"],1)
        self.assertIsNone(report["audit"])

    def test_final_context_cannot_overrun_batch_deadline(self):
        token=self.plan()["review_token"]
        clock=[0.0];calls=[0];original=routing._context
        def slow_final(*args,**kwargs):
            result=original(*args,**kwargs);calls[0]+=1
            if calls[0]==2:clock[0]+=61.0
            return result
        with patch.object(routing.time,"monotonic",side_effect=lambda:clock[0]),patch.object(routing,"_context",side_effect=slow_final):
            report=self.collect(token)
        self.assertTrue(report["identity_stable"])
        self.assertFalse(report["live_snapshot_complete"])
        self.assertFalse(report["configured_graph_fake_only_observed"])
        self.assertEqual(report["observation_failure"],"bounded_observation_failed")

    def test_cli_errors_are_private_and_review_token_required(self):
        out=io.StringIO()
        with patch.object(cli,"routing_plan",side_effect=ValueError(SECRET)),patch("sys.stdout",out):
            self.assertEqual(cli.main(["plan","--run-id",fixture.RUN,"--smoke-capture",str(self.capture)]),1)
        self.assertNotIn(SECRET,out.getvalue())


class WireTests(unittest.TestCase):
    def wire(self,raw,peer=12,route=None):
        sock=fixture.FakeSocket(raw)
        rows=fixture.tcp()+[dict(local_address="127.0.0.1",local_port=18880,remote_address="127.0.0.1",remote_port=53123,state="Established",pid=peer)]
        with patch.object(routing.socket,"socket",return_value=sock):
            result=routing._http_get(route or routing.ROUTES[0],12,time.monotonic()+30,lambda:None,lambda:rows)
        return result,sock
    def raw(self,body=b'{}',extra=b'',status=b'200 OK'):
        return b'HTTP/1.1 '+status+b'\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\n'+extra+b'\r\n'+body
    def test_exact_four_route_allowlist_no_proxy_auth_or_post(self):
        original=routing.smoke.ROUTES
        for route in routing.ROUTES:
            with patch.dict("os.environ",{"HTTP_PROXY":SECRET}):_,sock=self.wire(self.raw(),route=route)
            self.assertEqual(sock.connected,[("127.0.0.1",18880)])
            self.assertTrue(sock.sent[0].startswith(("GET "+route+" HTTP/1.1").encode()))
            self.assertNotIn(b'Authorization',sock.sent[0]);self.assertNotIn(b'Cookie',sock.sent[0])
        for route in (routing.smoke.ROUTES[0],"/test?api=llm","/auth","http://evil.invalid"):
            with self.assertRaises(ValueError):self.wire(self.raw(),route=route)
        self.assertEqual(routing.smoke.ROUTES,original)
    def test_accepted_connection_foreign_refuses_and_bad_framing_fails(self):
        with self.assertRaises(ValueError):self.wire(self.raw(),peer=99)
        for raw in (self.raw(status=b'302 Found'),self.raw(extra=b'Content-Encoding: gzip\r\n'),self.raw(extra=b'Transfer-Encoding: chunked\r\n'),self.raw()+b'extra',self.raw(extra=b'Content-Length: 0\r\n')):
            with self.assertRaises(ValueError):self.wire(raw)

    def test_final_live_or_listener_probe_cannot_overrun_exchange_deadline(self):
        for slow_probe in ("live","listeners"):
            clock=[0.0];calls={"live":0,"listeners":0}
            sock=fixture.FakeSocket(self.raw())
            rows=fixture.tcp()+[dict(local_address="127.0.0.1",local_port=18880,remote_address="127.0.0.1",remote_port=53123,state="Established",pid=12)]
            def probe(name):
                calls[name]+=1
                if name==slow_probe and calls[name]==2:clock[0]+=10.0
            def live():probe("live")
            def connections():probe("listeners");return rows
            with self.subTest(slow_probe=slow_probe),patch.object(routing.time,"monotonic",side_effect=lambda:clock[0]),patch.object(routing.socket,"socket",return_value=sock),self.assertRaisesRegex(ValueError,"timed out"):
                routing._http_get(routing.ROUTES[0],12,60.0,live,connections)
            self.assertEqual(len(sock.sent),1)


if __name__=="__main__":unittest.main()
