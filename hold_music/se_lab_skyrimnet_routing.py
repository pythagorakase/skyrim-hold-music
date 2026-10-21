"""Private in-memory audit of four attributed SkyrimNet config/schema GETs.

This observes the returned configured graph only. It neither exercises a route
nor establishes native fallback behavior, credential absence or zero egress.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import socket
import time
import uuid

from hold_music import se_lab_skyrimnet_smoke as smoke
from hold_music import se_lab_mcp_discovery as discovery

tier = smoke.tier
VERSION = 1
HOST, PORT = "127.0.0.1", 18880
MAX_BODY, MAX_HEADERS = smoke.MAX_BODY, smoke.MAX_HEADERS
TOTAL_SECONDS = 60.0
ROUTES = ("/config?api=get&name=OpenRouter", "/config?api=get&name=Providers",
          "/config?api=schema&name=OpenRouter", "/config?api=schema&name=Providers")
FAILURES = discovery.FAILURES
EXPECTED_MODEL = "hold-music-lab-disabled"
SOURCE_BASIS = {
    "archive_sha256": "6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef",
    "dashboard_contract": "beta26-rc4-web-new-main.c12d8cff",
    "config_envelope": "data",
    "schema_envelope": "direct_fields",
    "slot_binding": "comma_split_index",
    "native_inheritance_verified": False,
}


def _context(run_id, smoke_capture, process_probe, module_probe, connection_probe):
    base, run, launched = smoke._context(run_id, process_probe, module_probe, connection_probe)
    snapshot = tier._Snapshot()
    capture = discovery._capture(smoke_capture, base, snapshot)
    files = (Path(__file__), tier.REPO / "tools/se_lab_skyrimnet_routing.py", Path(discovery.__file__))
    implementation = {str(p.relative_to(tier.REPO)): snapshot.read(p)["sha256"] for p in files}
    snapshot.finish()
    return dict(version=VERSION, tier=tier.TIER, run_id=run_id, smoke_binding=base,
        smoke_capture=capture, implementation=implementation, routes=list(ROUTES),
        source_basis=SOURCE_BASIS), run, launched


def routing_plan(run_id, smoke_capture, *, process_probe=None, module_probe=None, connection_probe=None):
    binding, _, _ = _context(run_id, smoke_capture, process_probe or tier._runtime_process_snapshot,
        module_probe or smoke._modules, connection_probe or smoke._connections)
    return dict(version=VERSION, operation="skyrimnet_routing_plan", status="ready_for_bounded_get",
        binding=binding, review_token="skyrimnet-routing-v1:" + tier._digest(binding),
        network_requests_performed=False, writes_performed=False, diagnostic_ready=False,
        runtime_verified=False, native_fallback_verified=False, egress_verified=False, paid_generation=False)


def _text(value):
    return isinstance(value, str) and len(value) <= 4096 and not any(ord(c) < 32 for c in value)


def _typed(value, kind):
    if kind == "bool": return type(value) is bool
    if kind == "int": return type(value) is int and abs(value) <= 2**53
    if kind == "float": return type(value) in (int, float) and abs(value) <= 2**53 and math.isfinite(value)
    if kind in ("string", "select"): return _text(value)
    return False


class _Audit:
    """All dynamic values stay here. Only fixed issue codes and counts escape."""
    def __init__(self):
        self.issues = set()
        self.counts = {key: 0 for key in ("providers", "providers_returned", "providers_skipped", "rotations", "variants", "slots", "disabled_slots",
            "backup_slots", "borrowed_key_references", "unknown_fields", "schema_fields",
            "schema_defaults_used", "schema_type_checks", "inherited_controls", "passthrough_objects")}

    def bad(self, code): self.issues.add(code)

    def shape(self, value, allowed):
        if not isinstance(value, dict):
            self.bad("malformed_graph"); return {}
        unknown = set(value) - set(allowed)
        if unknown:
            self.counts["unknown_fields"] += len(unknown); self.bad("unsupported_fields")
        return value

    def schema(self, value):
        if (not isinstance(value, dict) or "error" in value or not isinstance(value.get("fields"), list)
                or len(value["fields"]) > 4096):
            self.bad("schema_unavailable"); return {}
        fields = {}
        for field in value["fields"]:
            if (not isinstance(field, dict) or not _text(field.get("path")) or not field["path"]
                    or any(not p for p in field["path"].split(".")) or field["path"] in fields
                    or field.get("type") not in ("bool", "int", "float", "string", "select", "hotkey")):
                self.bad("schema_ambiguous"); continue
            fields[field["path"]] = field
            self.counts["schema_fields"] += 1
        return fields

    def scalar(self, obj, key, kind, schema, path, *, default=False):
        field = schema.get(path)
        if field is not None:
            self.counts["schema_type_checks"] += 1
            accepted = {"string", "select"} if kind == "string" else ({"int", "float"} if kind == "float" else {kind})
            if field["type"] not in accepted:
                self.bad("schema_type_mismatch")
        if key in obj:
            value = obj[key]
        elif default and field is not None and "defaultValue" in field:
            value = field["defaultValue"]
            self.counts["schema_defaults_used"] += 1
        else:
            self.bad("missing_explicit_or_schema_value"); return None
        if not _typed(value, kind):
            self.bad("invalid_typed_value"); return None
        return value

    def body(self, obj, key):
        if key not in obj:
            self.bad("missing_passthrough_state")
        elif not isinstance(obj[key], dict) or obj[key]:
            self.bad("request_body_passthrough_unresolved")
        else:
            self.counts["passthrough_objects"] += 1


PARAMS = {"temperature": "float", "top_p": "float", "top_k": "int", "min_p": "float",
    "max_tokens": "int", "frequency_penalty": "float", "presence_penalty": "float",
    "repetition_penalty": "float", "seed": "int"}
CONTROLS = {"request_timeout": "float", "connect_timeout": "float", "max_retries": "int"}
PROVIDER_FIELDS = {"id", "name", "endpoint", "api_key", "api_key_from", "api_style", "use_sse",
    "use_structured_outputs", "reasoning", "provider_settings", "provider_sorting", "builtin"}
SLOT_FIELDS = set(PARAMS) | set(CONTROLS) | {"provider_id", "provider_settings", "use_sse", "enabled",
    "routing_role", "rotation_weight", "use_structured_outputs", "reasoning"}
ROOT_FIELDS = {"endpoint", "api_key", "model_name", "model_params", "default_params", "variants",
    "rotation_mode", "timeout", "connect_timeout", "max_retries"}
VARIANT_FIELDS = {"model_name", "model_params", "default_params", "rotation_mode", "timeout", "connect_timeout"}


def _audit_graph(payloads):
    """Pure bounded projection; arguments and raw schemas are never returned."""
    audit = _Audit()
    if not isinstance(payloads, list) or len(payloads) != 4:
        raise ValueError("Expected four bounded responses")
    values, hashes = [], []
    for raw in payloads:
        if not isinstance(raw, bytes) or len(raw) > MAX_BODY:
            raise ValueError("Response exceeded bound")
        values.append(smoke._json(raw))
        hashes.append(dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
    for i in (0, 1):
        if not isinstance(values[i], dict) or "error" in values[i] or not isinstance(values[i].get("data"), dict):
            raise ValueError("Invalid config envelope")
        values[i] = values[i]["data"]
    schemas = [audit.schema(values[2]), audit.schema(values[3])]
    root_doc = audit.shape(values[0], {"openrouter", "active_preset_id"})
    if "active_preset_id" in root_doc and not _text(root_doc["active_preset_id"]): audit.bad("invalid_typed_value")
    root = audit.shape(root_doc.get("openrouter"), ROOT_FIELDS)
    provider_doc = audit.shape(values[1], {"providers"})
    records = provider_doc.get("providers")
    provider_coverage = isinstance(records, list) and 1 <= len(records) <= 256
    if isinstance(records, list):
        audit.counts["providers_returned"] = len(records)
    if not isinstance(records, list) or not 1 <= len(records) <= 256:
        audit.counts["providers_skipped"] = audit.counts["providers_returned"]
        audit.bad("malformed_providers"); records = []
    providers = {}
    for index, value in enumerate(records):
        record = audit.shape(value, PROVIDER_FIELDS)
        audit.counts["providers"] += 1
        prefix = "providers." + str(index) + "."
        identifier = audit.scalar(record, "id", "string", schemas[1], prefix + "id")
        if not identifier or identifier in providers:
            audit.bad("duplicate_or_missing_provider_identity")
        else: providers[identifier] = record
        if audit.scalar(record, "endpoint", "string", schemas[1], prefix+"endpoint") != tier.LOOPBACK:
            audit.bad("non_fake_endpoint")
        if audit.scalar(record, "api_key", "string", schemas[1], prefix+"api_key") != "":
            audit.bad("nonempty_or_unknown_credential")
        if audit.scalar(record, "api_style", "string", schemas[1], prefix+"api_style") != "chat":
            audit.bad("unsupported_request_style")
        if audit.scalar(record, "use_sse", "bool", schemas[1], prefix+"use_sse") is not False:
            audit.bad("streaming_not_disabled")
        for key in ("name", "provider_sorting"):
            if key in record and not _text(record[key]): audit.bad("invalid_typed_value")
        for key in ("builtin", "use_structured_outputs", "reasoning"):
            if key in record and type(record[key]) is not bool: audit.bad("invalid_typed_value")
        audit.body(record, "provider_settings")
    for record in records:
        if not isinstance(record, dict) or "api_key_from" not in record: continue
        borrowed = record["api_key_from"]
        if not _text(borrowed): audit.bad("invalid_typed_value")
        elif borrowed:
            audit.counts["borrowed_key_references"] += 1
            # Only the shipped openrouter_decisions loan is source-backed; its
            # remote endpoint cannot meet this fake-only policy. Never invent
            # generic recursive borrowing semantics for custom records.
            audit.bad("key_borrowing_unresolved")
            if borrowed not in providers: audit.bad("missing_borrowed_provider")
            elif providers[borrowed].get("api_key") != "": audit.bad("nonempty_or_unknown_credential")
    # Credentials and destinations require an explicit effective readback. A
    # schema default is not evidence that the running legacy route adopted it.
    if audit.scalar(root, "endpoint", "string", schemas[0], "openrouter.endpoint") != tier.LOOPBACK:
        audit.bad("non_fake_legacy_endpoint")
    if audit.scalar(root, "api_key", "string", schemas[0], "openrouter.api_key") != "":
        audit.bad("nonempty_or_unknown_legacy_credential")
    base_controls = {}
    for key, kind in CONTROLS.items():
        source = "timeout" if key == "request_timeout" else key
        base_controls[key] = audit.scalar(root, source, kind, schemas[0], "openrouter."+source, default=True)
    def valid_control(key, value):
        if value is None or value < 0 or (key != "max_retries" and value == 0):
            audit.bad("invalid_retry_or_timeout")
    for key, value in base_controls.items(): valid_control(key, value)
    variants = root.get("variants")
    slot_coverage = True
    if not isinstance(variants, dict) or len(variants) > 256:
        slot_coverage = False
        audit.bad("malformed_variants"); variants = {}
    rotations = [(None, root, "openrouter")]
    for key, value in variants.items():
        audit.counts["variants"] += 1
        if not _text(key) or not key or "." in key: audit.bad("ambiguous_variant_identity")
        rotations.append((key, audit.shape(value, VARIANT_FIELDS), "openrouter.variants."+key))
    for variant, rotation, path in rotations:
        audit.counts["rotations"] += 1
        if variant is not None:
            for key in ("timeout", "connect_timeout"):
                if key in rotation:
                    control = audit.scalar(rotation, key, "float", schemas[0], path+"."+key)
                    valid_control(key, control)
        names = audit.scalar(rotation, "model_name", "string", schemas[0], path+".model_name")
        names = [name.strip() for name in names.split(",")] if names is not None else []
        params = rotation.get("model_params")
        if not isinstance(params, list) or len(params) > 256:
            slot_coverage = False
            audit.bad("malformed_slots"); params = []
        if not names or len(names) != len(params) or any(not name for name in names): audit.bad("slot_count_mismatch")
        if any(name != EXPECTED_MODEL for name in names): audit.bad("model_not_lab_fixture")
        defaults = audit.shape(rotation.get("default_params"), PARAMS)
        for key, value in defaults.items():
            if key in PARAMS and not _typed(value, PARAMS[key]): audit.bad("invalid_typed_value")
        mode = rotation.get("rotation_mode")
        if mode is None and variant is not None:
            mode = root.get("rotation_mode"); audit.counts["inherited_controls"] += 1
        if mode is None:
            mode = audit.scalar(root, "rotation_mode", "string", schemas[0], "openrouter.rotation_mode", default=True)
        if mode not in ("sequential", "random"): audit.bad("unresolved_rotation_mode")
        for index, value in enumerate(params):
            slot = audit.shape(value, SLOT_FIELDS); audit.counts["slots"] += 1
            prefix = path + ".model_params."+str(index)+"."
            identifier = audit.scalar(slot, "provider_id", "string", schemas[0], prefix+"provider_id")
            if identifier not in providers: audit.bad("missing_slot_provider")
            if variant == "decisions": audit.bad("unsupported_request_style")
            enabled = audit.scalar(slot, "enabled", "bool", schemas[0], prefix+"enabled", default=True)
            if enabled is False: audit.counts["disabled_slots"] += 1
            role = audit.scalar(slot, "routing_role", "string", schemas[0], prefix+"routing_role", default=True)
            if role == "backup": audit.counts["backup_slots"] += 1
            elif role != "primary": audit.bad("unresolved_slot_role")
            audit.body(slot, "provider_settings")
            for key in ("use_sse", "use_structured_outputs", "reasoning"):
                if key in slot and type(slot[key]) is not bool: audit.bad("invalid_typed_value")
            if slot.get("use_sse") is True: audit.bad("streaming_not_disabled")
            for key, kind in PARAMS.items():
                if key in slot and not _typed(slot[key], kind): audit.bad("invalid_typed_value")
            if "rotation_weight" in slot and (not _typed(slot["rotation_weight"], "float") or slot["rotation_weight"] <= 0):
                audit.bad("invalid_typed_value")
            if mode == "random" and "rotation_weight" not in slot: audit.bad("missing_explicit_or_schema_value")
            for key, kind in CONTROLS.items():
                if key in slot:
                    control = audit.scalar(slot, key, kind, schemas[0], prefix+key)
                else:
                    audit.counts["inherited_controls"] += 1
                    source = "timeout" if key == "request_timeout" else key
                    if variant is not None and key != "max_retries" and source in rotation:
                        control = audit.scalar(rotation, source, kind, schemas[0], path+"."+source)
                        # Dashboard comments disagree about native fallback at
                        # this tier. Different values cannot certify resolution.
                        if control != base_controls[key]: audit.bad("native_timeout_inheritance_unresolved")
                    else: control = base_controls[key]
                valid_control(key, control)
    return dict(configured_graph_fake_only=not audit.issues, counts=audit.counts,
        issues=sorted(audit.issues), responses=hashes, preset_label_used_as_evidence=False,
        disabled_and_backup_slots_audited=slot_coverage, all_returned_providers_audited=provider_coverage,
        native_fallback_verified=False, native_inheritance_verified=False)


def collect_routing(run_id, smoke_capture, review_token, *, process_probe=None, module_probe=None,
                    connection_probe=None, transport=None):
    process_probe = process_probe or tier._runtime_process_snapshot
    module_probe, connection_probe = module_probe or smoke._modules, connection_probe or smoke._connections
    transport = transport or _http_get
    root = tier._root()
    with tier._writer_lock(tier._no_alias(root / ".se-lab-writer.lock")), tier._writer_lock(tier._no_alias(root / tier.CONTROL / "writer.lock")):
        binding, run, launched = _context(run_id, smoke_capture, process_probe, module_probe, connection_probe)
        if not tier._matches(review_token, "skyrimnet-routing-v1:"+tier._digest(binding)):
            raise ValueError("Routing review is stale or belongs to another operation")
        deadline = time.monotonic() + TOTAL_SECONDS
        def live():
            if time.monotonic() >= deadline or smoke._live(run, launched, process_probe) != binding["smoke_binding"]["game"]:
                raise ValueError("Live identity or observation deadline changed")
        raw_responses, audit, failure = [], None, None
        attempted = 0
        try:
            for route in ROUTES:
                live(); attempted += 1
                raw_responses.append(transport(route, binding["smoke_binding"]["game"]["pid"], deadline, live, connection_probe))
                live()
            audit = _audit_graph(raw_responses)
        except FAILURES:
            failure = "bounded_observation_failed"
        finally:
            raw_responses.clear()
        try:
            after, _, _ = _context(run_id, smoke_capture, process_probe, module_probe, connection_probe)
            stable = after == binding
        except FAILURES:
            stable = False
        if time.monotonic() >= deadline:
            failure = "bounded_observation_failed"
        complete = failure is None and stable and audit is not None
        passed = complete and audit["configured_graph_fake_only"]
        report = dict(version=VERSION, tier=tier.TIER, operation="skyrimnet_routing_capture", run_id=run_id,
            capture_id=uuid.uuid4().hex, status="configured_graph_fake_only_observed" if passed else "incomplete_or_mismatched",
            binding=binding, binding_sha256=tier._digest(binding), audit=audit, observation_failure=failure,
            identity_stable=stable, live_snapshot_complete=complete, configured_graph_fake_only_observed=passed,
            request_attempt_count=attempted, diagnostic_ready=False, native_fallback_verified=False,
            native_inheritance_verified=False, egress_verified=False, runtime_verified=False,
            credentials_verified=False, paid_generation=False, provider_requests_performed=False,
            network_requests_attempted=bool(attempted), writes_performed=True,
            limitations=["Only four fixed config/schema GETs; no diagnostic or provider request was sent.",
                "Returned configuration is not proof of native fallback behavior, zero egress or billing-credential absence.",
                "Unknown fields, key borrowing, nonempty request-body passthrough and unresolved defaults remain incomplete.",
                "No raw configuration, schema defaults, response errors, model names or provider identifiers are retained."])
        directory = tier._no_alias(root / tier.RUNTIME_CONTROL / "routing")
        directory.mkdir(exist_ok=True)
        tier._runtime_json(directory / (report["capture_id"]+".json"), report, new=True)
        return report


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
        smoke._verify_connection(connection_probe(), pid, stream.getsockname()[1])
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
        smoke._listeners(connection_probe(), pid)
        remaining()
        return body
