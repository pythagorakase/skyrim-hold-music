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

The audit examines the legacy root endpoint/key, every returned provider, the
default rotation and every returned variant. Disabled slots, backups, unknown
variant names and unreferenced providers are included. Preset labels are ignored
as evidence. Model names must match the fixed lab fixture; every named endpoint
must match the fixed fake-provider URL and returned credentials must be empty.
Provider identities must resolve uniquely and slot counts must align exactly.
No provider or model identifiers, endpoints, keys or arbitrary schema values
are exported.

Required missing values stay incomplete unless an exact scoped schema field
establishes a correctly typed default for a supported scalar. UI display defaults
are not adopted. Legacy endpoint and credential fields always require explicit
observed values; schema defaults cannot establish either. Oversized provider
lists report skipped record counts and incomplete coverage, never a successful
audit of all returned providers. Skipped malformed/oversized slot or variant
collections also clear the slot-coverage flag. Provider/slot passthrough must be explicitly empty; unknown
fields, malformed types, key borrowing and nonempty passthrough stay unresolved.
Retry, timeout, enabled, role and rotation values are checked even for inactive
slots. The source comments disagree about variant timeout fallback in native
code: unequal inherited variant/base values are marked unresolved; the report
never claims native inheritance verification.

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
bounded policy and final identity/protected-state checks remained stable. Four
sequential GETs are not an atomic native configuration snapshot, and this does
not prove that a diagnostic is ready or would use no hidden route. The collector
always leaves `diagnostic_ready`, `native_fallback_verified`,
`native_inheritance_verified`, `credentials_verified`, `egress_verified` and
`runtime_verified` false. It does not inspect secret stores, account state,
environment credentials, native memory, external traffic or provider billing.

Tests use synthetic configs, sockets, processes and temporary evidence trees.
No live endpoint or provider calls are part of these tests.
