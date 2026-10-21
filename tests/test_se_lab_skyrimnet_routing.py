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
        api_style="chat", use_sse=False, use_structured_outputs=False, reasoning=False,
        api_key_from="", provider_settings={})
    slot = dict(provider_id="local", enabled=True, routing_role="primary", provider_settings={})
    root = dict(endpoint=routing.tier.LOOPBACK, api_key="", model_name=routing.EXPECTED_MODEL,
        model_params=[slot], default_params={}, variants={}, rotation_mode="sequential",
        timeout=30, connect_timeout=5, max_retries=0, provider_settings={},
        **{key:False for key in routing.ROTATION_FLAGS})
    policy=dict(mode="legacy",profile="",quantization_floor="",ttft_early_abort=False,
        ttft_abort_multiplier=2.0,ttft_abort_ceiling_ms=0,ttft_abort_floor_ms=2500,
        local_slow_demote=False,ttft_race_first_token=False)
    return [{"data": {"openrouter": root, "active_preset_id": SECRET,"routing":policy}},
            {"data": {"providers": [provider]}}, {"fields": []}, {"fields": []}]


def encoded(values): return [json.dumps(v).encode() for v in values]


def variant(root):
    return {key:copy.deepcopy(value) for key,value in root.items() if key in routing.VARIANT_FIELDS}


def native_candidate():
    """Pinned serializer shape, built-in reinsertion accounted for; no live I/O."""
    values=payloads();root=values[0]["data"]["openrouter"]
    records=[]
    for identifier in ("openrouter","nanogpt","nvidia","chutes","openrouter_decisions","hold_music_lab"):
        record=copy.deepcopy(values[1]["data"]["providers"][0])
        record.update(id=identifier,api_style="decisions" if identifier=="openrouter_decisions" else "chat",
            builtin=identifier!="hold_music_lab",provider_sorting="default",upstream_order_mode="fleet")
        records.append(record)
    values[1]["data"]["providers"]=records
    root["default_params"]={"temperature":0.0,"max_tokens":64,"top_p":1.0,"top_k":0,
        "frequency_penalty":0.0,"presence_penalty":0.0,"stop_sequences":[]}
    root["model_params"][0].update(provider_id="hold_music_lab",rotation_weight=1.0,
        request_timeout=30,connect_timeout=5,max_retries=0,ttft_abort_multiplier=2.0,ttft_abort_floor_ms=2500,
        **root["default_params"],**{key:False for key in routing.FLAGS})
    root.update(provider_sorting="default",event_history_count_dialogue=0)
    root["variants"]["decisions"]=variant(root)
    root["variants"]["decisions"]["model_params"][0]["enabled"]=False
    values[0]["data"].update(active_preset_id="",pending_first_run_preset_id="",active_variants=["decisions"])
    values[2]["fields"]=[dict(path="openrouter.model_params",type="model_params")]
    values[3]["fields"]=[dict(path="providers",type="providers_list")]
    return values


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

    def test_six_provider_native_candidate_inventories_decisions_without_selecting_it(self):
        report=self.audit(native_candidate())
        self.assertTrue(report["configured_graph_fake_only"])
        self.assertTrue(report["configured_endpoint_inventory_complete"])
        self.assertTrue(report["configured_passthrough_empty"])
        self.assertEqual(report["issues"],[])
        expected={"providers":6,"rotations":2,"variants":1,"slots":2,"disabled_slots":1,
            "non_chat_providers":1,"decisions_slots":1,"non_chat_slots":0,"base_enabled_chat_slots":1,
            "passthrough_fields":10,"passthrough_objects":10,"schema_container_descriptors":2}
        for key,value in expected.items():self.assertEqual(report["counts"][key],value,key)
        for key in ("diagnostic_selection_performed","diagnostic_ready","actor_group_overrides_verified",
                    "native_fallback_verified","native_inheritance_verified","egress_verified"):
            self.assertFalse(report[key],key)
        self.assertEqual(report["interpretation_scope"],"returned_configured_graph_only")

    def bodies(self,data):
        root=data[0]["data"]["openrouter"]
        return [root,*root["variants"].values(),*data[1]["data"]["providers"],
            *root["model_params"],*[slot for v in root["variants"].values() for slot in v["model_params"]]]

    def test_explicit_null_roundtrip_is_empty_only_with_every_layer_audited(self):
        data=native_candidate()
        for obj in self.bodies(data):obj["provider_settings"]=None
        report=self.audit(data)
        self.assertTrue(report["configured_graph_fake_only"])
        self.assertTrue(report["configured_passthrough_empty"])
        self.assertEqual(report["counts"]["passthrough_nulls"],10)
        self.assertEqual(report["counts"]["passthrough_objects"],0)
        self.assertFalse(report["actor_group_overrides_verified"])

    def test_every_passthrough_layer_requires_observation_not_schema_default(self):
        for index in range(10):
            data=native_candidate();del self.bodies(data)[index]["provider_settings"]
            data[2]["fields"].append(dict(path="openrouter.provider_settings",type="string",defaultValue={}))
            with self.subTest(layer=index):
                report=self.audit(data)
                self.assertFalse(report["configured_graph_fake_only"])
                self.assertFalse(report["configured_passthrough_empty"])
                self.assertIn("missing_passthrough_state",report["issues"])
                self.assertEqual(report["counts"]["schema_defaults_used"],0)

    def test_nonempty_shadowed_or_disabled_layers_are_never_exempt(self):
        for index in range(10):
            data=native_candidate()
            for obj in self.bodies(data):obj["provider_settings"]=None
            self.bodies(data)[index]["provider_settings"]={SECRET:None}
            with self.subTest(layer=index):
                report=self.audit(data)
                self.assertFalse(report["configured_graph_fake_only"])
                self.assertFalse(report["configured_passthrough_empty"])
                self.assertIn("request_body_passthrough_unresolved",report["issues"])

    def test_empty_nonobject_passthrough_and_null_credential_are_not_normalized(self):
        for body in ([],"",False,0,{"nested":{}},{"nested":None}):
            for index in (0,1,2,8,9):
                data=native_candidate();self.bodies(data)[index]["provider_settings"]=body
                with self.subTest(layer=index,value=body):
                    self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        for index in (0,1,2):
            data=native_candidate();self.bodies(data)[index]["api_key"]=None
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_native_schema_containers_require_exact_path_and_document(self):
        for doc,path,kind in ((2,"elsewhere.model_params","model_params"),(2,"providers","providers_list"),
                              (3,"openrouter.model_params","model_params"),(3,"providers","string"),
                              (2,"openrouter.model_params","bool"),(3,"providers",SECRET)):
            data=native_candidate();data[doc]["fields"]=[dict(path=path,type=kind,defaultValue=SECRET)]
            with self.subTest(document=doc,path=path,kind=kind):
                self.assertIn("schema_ambiguous",self.audit(data)["issues"])

    def test_variant_destinations_credentials_and_disabled_routes_are_audited(self):
        for key,value in (("endpoint",SECRET),("api_key",SECRET),("endpoint",None),("api_key",None)):
            data=native_candidate();data[0]["data"]["openrouter"]["variants"]["decisions"][key]=value
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        for key in ("endpoint","api_key"):
            data=native_candidate();del data[0]["data"]["openrouter"]["variants"]["decisions"][key]
            data[2]["fields"].append(dict(path="openrouter.variants.decisions."+key,type="string",defaultValue=""))
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_non_chat_inventory_never_grants_invocation_and_unknown_style_stays_incomplete(self):
        for style in ("decisions","systemone"):
            data=native_candidate();data[1]["data"]["providers"][-1]["api_style"]=style
            report=self.audit(data)
            self.assertTrue(report["configured_endpoint_inventory_complete"])
            self.assertEqual(report["counts"]["non_chat_slots"],2)
            self.assertEqual(report["counts"]["base_enabled_chat_slots"],0)
            self.assertFalse(report["diagnostic_ready"])
            self.assertFalse(report["diagnostic_selection_performed"])
        data=native_candidate();data[1]["data"]["providers"][0]["api_style"]=SECRET
        self.assertFalse(self.audit(data)["configured_endpoint_inventory_complete"])

    def test_native_metadata_is_typed_and_active_variant_labels_do_not_filter(self):
        data=native_candidate();data[0]["data"]["active_variants"]=[]
        self.assertEqual(self.audit(data)["counts"]["variants"],1)
        for container,key,value in (("doc","active_variants",[[]]),("doc","active_variants",["same","same"]),
                ("doc","pending_first_run_preset_id",{}),("root","event_history_count_dialogue",True),
                ("root","provider_sorting",[]),("provider","upstream_order_mode",SECRET),
                ("slot","ttft_abort_floor_ms",None),("slot","ttft_abort_multiplier",False),
                ("slot","stop_sequences",SECRET),("root","use_caching",True)):
            data=native_candidate();doc=data[0]["data"];root=doc["openrouter"]
            obj={"doc":doc,"root":root,"provider":data[1]["data"]["providers"][0],"slot":root["model_params"][0]}[container]
            obj[key]=value
            with self.subTest(container=container,key=key):
                self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_routing_policy_and_key_loan_state_cannot_be_omitted_or_defaulted(self):
        for key in routing.ROUTING_FIELDS:
            data=native_candidate();del data[0]["data"]["routing"][key]
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        for key,value in (("mode","smart"),("profile",SECRET),("quantization_floor",SECRET),
                          ("ttft_race_first_token",True),("ttft_abort_floor_ms",False)):
            data=native_candidate();data[0]["data"]["routing"][key]=value
            self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        data=native_candidate();del data[1]["data"]["providers"][4]["api_key_from"]
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])

    def test_unknown_fields_in_native_layers_and_malformed_rows_preserve_privacy_and_coverage(self):
        for target in ("doc","routing","variant","defaults","provider","slot"):
            data=native_candidate();doc=data[0]["data"];root=doc["openrouter"]
            obj={"doc":doc,"routing":doc["routing"],"variant":root["variants"]["decisions"],
                 "defaults":root["default_params"],"provider":data[1]["data"]["providers"][4],"slot":root["model_params"][0]}[target]
            obj[SECRET]=SECRET
            report=self.audit(data)
            self.assertFalse(report["configured_graph_fake_only"])
            self.assertEqual(report["counts"]["unknown_fields"],1)
        data=native_candidate();data[1]["data"]["providers"][0]=[]
        self.assertFalse(self.audit(data)["all_returned_providers_audited"])
        data=native_candidate();data[0]["data"]["openrouter"]["variants"]["decisions"]=[SECRET]
        self.assertFalse(self.audit(data)["disabled_and_backup_slots_audited"])

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

    def test_nonempty_provider_and_slot_passthrough_never_certified(self):
        for target in ("provider","slot"):
            for body in ({"provider":{"order":[SECRET]}},SECRET,[]):
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
        root["variants"]["scene"]=variant(root)
        root["variants"]["scene"]["timeout"]=10
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

    def test_sparse_seed_is_not_mistaken_for_complete_effective_routing(self):
        data=payloads();data[0]["data"]={"openrouter":{"endpoint":routing.tier.LOOPBACK,"api_key":""}}
        report=self.audit(data)
        self.assertFalse(report["configured_graph_fake_only"])
        self.assertFalse(report["diagnostic_ready"])

    def test_huge_integer_and_private_schema_envelope_fail_without_exception_leak(self):
        data=payloads();data[0]["data"]["openrouter"]["timeout"]=10**500
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])
        data=payloads();data[3]={"error":SECRET,"data":SECRET}
        self.assertFalse(self.audit(data)["configured_graph_fake_only"])


class CollectorTests(unittest.TestCase):
    write_documents=fixture.SmokeTests.write_documents

    def setUp(self):
        fixture.SmokeTests.setUp(self)
        observed=routing.smoke._context(fixture.RUN,**self.kw)[0]
        basis={**routing.SOURCE_BASIS,"dll_sha256":observed["modules"]["skyrimnet.dll"]["sha256"]}
        self.basis_patch=patch.object(routing,"SOURCE_BASIS",basis)
        self.basis_patch.start();self.addCleanup(self.basis_patch.stop)
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

    def test_native_candidate_capture_never_authorizes_chat_or_actor_context(self):
        self.data=native_candidate()
        for obj in GraphTests.bodies(self,self.data):obj["provider_settings"]=None
        report=self.collect()
        self.assertEqual(self.calls,list(routing.ROUTES))
        self.assertTrue(report["configured_graph_fake_only_observed"])
        self.assertTrue(report["audit"]["configured_endpoint_inventory_complete"])
        for key in ("diagnostic_ready","diagnostic_selection_performed","actor_group_overrides_verified",
                    "native_fallback_verified","egress_verified","runtime_verified","credentials_verified"):
            self.assertFalse(report[key],key)
        self.assertEqual(report["audit"]["counts"]["non_chat_providers"],1)

    def test_interpretation_refuses_unpinned_native_before_capture_or_network(self):
        token=self.plan()["review_token"]
        before={p:p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(routing,"SOURCE_BASIS",{**routing.SOURCE_BASIS,"dll_sha256":"0"*64}), \
                patch.object(routing.socket,"socket",side_effect=AssertionError("no socket")):
            for operation in (self.plan,lambda:self.collect(token)):
                with self.assertRaisesRegex(ValueError,"pinned native build"):operation()
        self.assertFalse(self.calls)
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

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
