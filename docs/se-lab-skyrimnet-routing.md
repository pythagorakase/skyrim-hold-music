# Disabled SkyrimNet lab: returned routing graph audit

This separate collector reads four backend configuration/schema responses from
the already attributed, currently live disabled SkyrimNet lab. It does not
enable AI, launch anything, call MCP, test a model, start a fake provider,
authenticate, or modify configuration. The original installer, smoke collector
and discovery modules are unchanged.

```powershell
& '<Python 3.12>\python.exe' -B -X utf8 tools/se_lab_skyrimnet_routing.py plan --run-id '<tier run ID>' --smoke-capture '<successful exact-run smoke capture>'
& '<Python 3.12>\python.exe' -B -X utf8 tools/se_lab_skyrimnet_routing.py collect --run-id '<same ID>' --smoke-capture '<same capture>' --review-token '<routing plan token>'
```

`plan` does not connect to a port or write evidence. It requires a successful
disabled-controls smoke capture bound to the same current launch, seven pinned
native module paths/hashes, protected baseline/Game state and owned loopback
listeners. The token also binds the routing module/tool and reused smoke-capture
validation implementation. A prior launch, installation, smoke or discovery
token cannot authorize this collection.

`collect` repeats those checks under the existing lab/tier writer locks, then
makes these four GETs in order, once each, with no retries:

1. `/config?api=get&name=OpenRouter`
2. `/config?api=get&name=Providers`
3. `/config?api=schema&name=OpenRouter`
4. `/config?api=schema&name=Providers`

The separate transport admits only this list; it does not widen the smoke
collector's allowlist. It connects directly to numeric IPv4 `127.0.0.1:18880`,
verifies the accepted server-side connection belongs to the exact live game
PID before sending HTTP, and rechecks identity/listeners afterward. No proxies,
redirects, cookies, authorization or settings writes are supported. Each exchange
has a four-second bound including process/TCP observations, with 16 KiB headers,
512 KiB body and a 60-second batch bound. HTTP/1.1 200, one Content-Length,
identity encoding and JSON content are required. Chunking, compression,
duplicate headers/JSON keys, nonfinite numbers and unsupported framing fail
closed. Slow Windows TCP queries can cause an incomplete observation.

## Source-backed interpretation

The reviewed beta26-rc4 ZIP is
`local/se-lab-downloads/skyrimnet-beta26-rc4.zip`, SHA256
`6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef`.
Its `web-new/main.c12d8cff.js.map` contains the primary shipped dashboard sources:

- `shared/hooks/useConfig.js`: configuration GET envelope `.data`.
- `PluginSection.jsx`: schema GET is a direct object with `fields`, each having
  a dot `path`, `type` and optional `defaultValue`.
- `shared/pages/AILLMs.jsx`: root/variant model lists, indexed parameters,
  defaults, timeout/retry fallback and the excluded diagnostic POST fan-out.
- `RotationEditor.jsx`: comma-split names and index-aligned `model_params`;
  disabled/backup fields and provider-specific body passthrough.
- `apiStyle.js` and `AIProviders.jsx`: provider format, key borrowing and
  request-body passthrough. The source-backed built-in key loan is narrowly
  restricted; the collector does not invent generic recursive borrowing.

Source excerpts and their original byte hashes are retained in ignored
`local/se-lab-skyrimnet-routing-design-20261021/`. These dashboard contracts
provide field interpretation, not proof of every native fallback branch.

The added native interpretation is restricted to `SkyrimNet.dll` SHA256
`2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
The plan and collection check that hash against the already verified live module
binding before reading any endpoint. A different build requires another review.
The clean DLL's provider and text-model serializers establish the extra fields:
`ProvidersConfig::SaveToNode` at `0x1802670a0`,
`TextModelConfig::SaveToNode` at `0x180268a50`, and the slot serializer at
`0x1808955f0`. Addresses are static preferred-image VAs, not live process addresses.

Recognized fields include provider `upstream_order_mode`, variant endpoint/key
and retry controls, base caching/history/sorting flags, stop sequences, slot
TTFT controls, and document routing/preset metadata. The narrow policy requires
legacy routing, empty route profile/quantization selectors, and disabled
experimental routing switches. Known fields still require their scoped types;
unknown fields remain incomplete. `active_variants` is bounded list metadata,
never permission to skip other configured variants.

Native custom schema descriptors are accepted only for `providers_list` at
`Providers`' `providers` path and `model_params` at `OpenRouter`'s
`openrouter.model_params` path. They describe UI containers, not scalar defaults
or general JSON Schema. The same descriptor at another path/document, or a
conflicting descriptor at these paths, remains ambiguous. This does not permit
arbitrary custom descriptor types.

The audit examines the legacy root endpoint/key, every returned provider, the
default rotation and every returned variant. Disabled slots, backups, unknown
variant names and unreferenced providers are included. Preset labels are ignored
as evidence. Model names must match the fixed lab fixture; every named endpoint
must match the fixed fake-provider URL and returned credentials must be empty.
Provider identities must resolve uniquely and slot counts must align exactly.
No provider or model identifiers, endpoints, keys or arbitrary schema values
are exported.

The native catalog can contain the six proposed loopback rows, including the
preserved built-in decisions provider and a disabled decisions slot. The known
`chat`, `decisions` and `systemone` styles are inventoried without claiming that
this collector implements any of their protocols. Non-chat providers/slots,
decisions slots and enabled base chat slots are counted separately. An enabled
chat slot count is metadata, not a selection or permission to send a request.
No route is selected, and `diagnostic_ready` always remains false. A future chat
diagnostic needs its own reviewed selector, exact model/provider binding and
protocol checks; this collector cannot authorize it.

Required missing values stay incomplete unless an exact scoped schema field
establishes a correctly typed default for a supported scalar. UI display defaults
are not adopted. Base and variant endpoint/credential fields, key-loan state and
every passthrough field require explicit observed values; schema defaults cannot
establish them. Oversized provider
lists report skipped record counts and incomplete coverage, never a successful
audit of all returned providers. Skipped malformed/oversized slot or variant
collections also clear the slot-coverage flag. Unknown fields, malformed types,
key borrowing and nonempty passthrough stay unresolved.
Retry, timeout, enabled, role and rotation values are checked even for inactive
slots. The source comments disagree about variant timeout fallback in native
code: unequal inherited variant/base values are marked unresolved; the report
never claims native inheritance verification.

### Explicit null and empty passthrough

At the exact `provider_settings` paths in the base, every variant, every provider
and every slot, the policy accepts an explicit JSON null or an object with zero
keys. Every layer must pass. A missing field, empty array/string, scalar, object
containing a null-valued key, or nonempty object remains incomplete. An empty
high-priority setting never exempts an unsafe lower layer from inspection.

This is a pinned serialization interpretation: the native recursive JSON-to-YAML
converter can round-trip `{}` as null. Resolver `0x180216840` selects one settings
value; `CreateRequestPayload` at `0x18037ef20–0x18037f00d` copies only object
entries into the request. A resolved null or empty object adds no passthrough
keys there. A null slot can inherit provider/variant/base settings; a resolved
provider's null can stop lower fallback, and a parsed variant optional can also
hold null. Therefore `configured_passthrough_empty` does **not** mean inheritance
is disabled. All recognized layers must be explicitly empty/null, even if a
current route would shadow some of them.

`BaseConfig::GetOverrideValue` at `0x180f88030` also consults actor, faction-group
and explicit-group overrides. Those are not covered by these four GETs.
`actor_group_overrides_verified` stays false. A future fake-chat diagnostic would
need to bind an empty override context or separately audit the applicable
override data. Static evidence and hashes for 18 relevant functions are retained
in `local/provider-settings-static-20261021/evidence.json`; the corresponding
review describes load-versus-fallback distinctions. No native request was
executed to establish these findings.

This is intentionally a narrow accepted subset, not a general settings
interpreter. Sparse seed files alone do not establish a complete effective graph.
For example, missing enabled/role/default-parameter or passthrough state may keep
the audit incomplete even though the returned visible endpoint is loopback.
Unsupported live schema shapes require a separate reviewed extension; there is
no fallback GET or automatic config repair.

## Evidence and limits

Only fixed issue codes, booleans, counts, response byte counts and SHA256 hashes
leave the private in-memory audit. Raw configuration/schema values, exception
bodies, unknown keys, model/provider IDs and schema defaults are not retained.
New sanitized captures use an exclusive filename under
`.skyrimnet-tier-runtime/routing/<capture-id>.json`; previous evidence and all
native configuration files remain intact.

`configured_graph_fake_only_observed` means that the returned graph met this
bounded configured-inventory policy and final identity/protected-state checks
remained stable. The compatible audit key `configured_graph_fake_only` retains
that limited meaning. `configured_endpoint_inventory_complete` reports that all
required configured graph/type/policy checks passed;
`configured_passthrough_empty` describes only the fully visited settings fields.
The interpretation scope is always `returned_configured_graph_only`. Four
sequential GETs are not an atomic native configuration snapshot, and this does
not prove that a diagnostic is ready or would use no hidden route. The collector
always leaves `diagnostic_ready`, `diagnostic_selection_performed`,
`actor_group_overrides_verified`, `native_fallback_verified`,
`native_inheritance_verified`, `credentials_verified`, `egress_verified` and
`runtime_verified` false. It does not inspect secret stores, account state,
environment credentials, native memory, external traffic or provider billing.

Tests use synthetic configs, sockets, processes and temporary evidence trees.
No live endpoint or provider calls are part of these tests.
