# Disabled-tier routing candidate — 2026-10-21

This is an offline proposal, not an installed configuration or permission to call a provider. The fifth run remains unchanged. `candidate-seeds.json` contains candidate **live configuration** documents for `Providers.yaml` and `OpenRouter.yaml`; it is not an exported preset.

Candidate SHA256: `72ed3310e76b9a65f15af54a51a2a97e8b2a0026c00ea70385a72dbdde80506f`.

## What the fifth readback establishes

The four fixed routing GETs completed, but the sanitized audit was incomplete: six providers, two rotations, one variant, two slots, one key-borrowing reference and 21 unknown fields. It reported external/default routing and unresolved inheritance. That does not prove that any provider was called. The global AI controls remain disabled.

Evidence: `local/se-lab-observer-v2-routing-result-20261021.json`, SHA256 `6fd2859e0dc92d7517a2df4b0beee34e09a8d2f504204b5cc3e5b3aeb2ccea95`, run `20261021T105157Z-a7f1bce383bc`.

Only counts and issue categories were retained. The exact 21 unknown fields cannot be reconstructed from that report. The static findings below identify actual serializer omissions in the collector, not a retrospective field-by-field attribution of the live response.

## Pinned evidence

All native addresses below are virtual addresses in the clean, statically inspected DLL, image base `0x180000000`. The DLL was not loaded or executed for this investigation.

| Artifact | SHA256 |
| --- | --- |
| `local/se-lab-downloads/skyrimnet-beta26-rc4.zip` | `6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef` |
| ZIP member `SKSE/Plugins/SkyrimNet.dll` | `2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a` |
| ZIP member `SKSE/Plugins/SkyrimNet/assets/web-new/main.c12d8cff.js.map` | `2dab71be5240d800e265e24410cdb947612a2d8fd7fbedba37a3abc2929545a9` |

Embedded UI paths below are relative to `webpack://skyrimnet-dashboard-browser/../shared/` in that source map.

## Two native reconciliation rules explain the added routes

1. **Missing built-in provider IDs are restored.** `MainWorker::reloadConfigs`, `0x1802768c0–0x18027b475`, checks the loaded nonempty catalog at `0x1802772b8`. The branch beginning `0x18027784a` enumerates built-ins (`0x18027788a`), checks existing IDs (`0x1802778b6`) and appends missing records (`0x1802778e1`). Existing matching records are retained. The branch logs “Providers: added the built-in records this catalog predates” and saves Providers. Thus a custom-only seed is expanded to five built-ins plus the custom record. The Providers loader itself replaces its vector from the supplied sequence; the later reconciliation is the relevant addition.
2. **The decisions variant is restored and its default provider repaired.** `TextModelConfig::LoadFromNode`, `0x180252910–0x180256479`, parses the supplied variants, then inserts missing reseeded defaults at `0x180255180–0x180255377`. It looks up `decisions` and calls `DefaultDecisionProviders` at `0x1802553f0`. That helper (`0x180894320–0x180894930`) ensures at least one slot and substitutes `openrouter_decisions` when the slot provider is missing, empty or exactly `openrouter`. A different explicit nonempty ID survives. An empty variants object therefore does not remove this native route.

The UI independently agrees: `pages/AIProviders.jsx:35–36` lists the same five canonical built-in IDs; `utils/presetApply.js:12–15,67–85` preserves the runtime-reseeded decisions block. Neither the provider page's sorting nor its save routine invents the extra providers.

## Candidate decisions

The candidate supplies all five built-in IDs plus `hold_music_lab`, so native reconciliation can retain explicit values rather than append external defaults.

| Provider ID | Preserved API style | Candidate role |
| --- | --- | --- |
| `openrouter` | `chat` | Catalog entry, explicit loopback and empty credentials |
| `nanogpt` | `chat` | Same |
| `nvidia` | `chat` | Same |
| `chutes` | `chat` | Same |
| `openrouter_decisions` | `decisions` | Catalog entry only; no decision invocation proposed |
| `hold_music_lab` | `chat` | Explicit base slot and disabled decisions-slot binding |

The built-in constructor is `0x18020b730–0x18020c15b`; the decisions enum and built-in key lender are assigned at `0x18020c0cf` and `0x18020c0df`. `components/aiproviders/apiStyle.js:1–29` defines the styles and the endpoint-specific built-in key loan.

Every catalog endpoint, the legacy endpoint, and the decisions variant endpoint is `http://127.0.0.1:18881/v1/chat/completions`. All credential and lender strings are empty. Every applicable SSE, reasoning, structured-output, caching and passthrough setting is explicitly disabled or empty. Retries are zero; timeouts are explicit. The built-in `upstream_order_mode` value `fleet` is retained from the native provider constructor (`0x180200e30–0x180200f7d`).

The base has one `hold-music-lab-disabled` model and one custom chat slot. The decisions variant has its own explicit model and custom provider binding, but its slot is **disabled**. This intentionally avoids native default-provider substitution without pretending that a chat provider implements the decisions protocol. The disabled decisions slot is not a valid future decision test; it must remain excluded from any chat diagnostic selection.

`general.globalAIEnabled`, both Game Master enable controls and all three decision-use controls must remain false. The base slot's enabled value is only a configured route for a possible later, separately authorized one-shot fake-chat diagnostic. This proposal starts no listener, enables no AI and authorizes no request. Empty preset IDs and legacy routing mode avoid intentionally selecting an unrelated preset or fleet policy, but their eventual native readback still needs validation.

The source map confirms that live models are comma-separated `model_name` strings with index-aligned `model_params`, not slot objects containing a `name` field (`components/aimodels/RotationEditor.jsx:22–27,143–150`). Exported preset `variants.default` is a different representation (`utils/presetSerialize.js:15–24`).

## Bounded collector adaptation

Keep the existing four-GET, exact-run ownership, redaction, size and deadline guards. Do not resolve a graph problem by filtering out built-in providers, inactive variants or disabled slots.

1. Recognize the pinned custom schema descriptors `providers_list` at the providers-list path and `model_params` at `openrouter.model_params`. They are UI container descriptors, not scalar defaults or JSON Schema. The model-params schema constructor is `0x1802308b0–0x1802322d9`, with field/type literals at `0x180232076` and `0x18023208a`. `pages/settings/PluginSection.jsx:18–21,53–65,81–108` shows the matching dotted-path UI schema handling. Unknown descriptor/path pairs remain incomplete.
2. Extend exact typed field recognition from the serializers below. Do not merely permit arbitrary unknown keys. In particular, recognize each variant's endpoint and API key as additional routing/credential inputs that must independently satisfy loopback/blank constraints.
3. Separate **all-configured-route inventory** from **one supported future chat diagnostic selection**. Every provider and slot must remain counted, including the preserved decisions-style record. Inventory can establish that its configured endpoint is loopback and its credential/loan is empty without claiming its protocol is supported. A diagnostic selector must require an enabled base chat slot with the exact custom provider/model and must never select decisions or invoke its API.
4. Preserve incomplete results for unresolved inheritance, nonempty passthrough, missing credentials, unexpected variants, skipped/overflowed entries or unsupported selected protocols. A known non-chat catalog row alone should not erase an otherwise complete endpoint inventory; its unsupported invocation status must remain explicit.
5. If needed, add a sanitized shape diagnosis using only a fixed allowlist of known field names, JSON types and counts. Unknown names should contribute counts/hashes, not raw strings. That would make the remaining live schema gaps diagnosable without retaining provider values, endpoints, keys or response bodies.

### Exact serializer coverage

`ProvidersConfig::SaveToNode`, `0x1802670a0–0x180267c7d`, emits:

`id`, `name`, `endpoint`, `api_key`, `api_key_from`, `api_style`, `use_sse`, `use_structured_outputs`, `reasoning`, `provider_settings`, `provider_sorting`, **`upstream_order_mode`**, `builtin`.

`TextModelConfig::SaveToNode`, `0x180268a50–0x18026a975`, emits these base keys:

`model_name`, `endpoint`, `api_key`, `timeout`, `connect_timeout`, `use_caching`, `support_dynamic_event_caching`, `event_history_count_dialogue`, `use_structured_outputs`, `reasoning`, `use_sse`, `provider_sorting`, `provider_settings`, `max_retries`, `rotation_mode`, `default_params`, `model_params`, `variants`.

Known default-parameter keys are `temperature`, `max_tokens`, `top_p`, `top_k`, `frequency_penalty`, `presence_penalty`, `stop_sequences`. Known optional variant fields include its own model, endpoint, key, timeout/connect timeout/retries, caching flags, SSE/reasoning/structured flags, provider settings, default params, model params and rotation mode.

Document-level fields outside `openrouter` include `active_preset_id`, `pending_first_run_preset_id` and `routing`. Routing contains `mode`, `profile`, `quantization_floor`, `ttft_early_abort`, `ttft_abort_multiplier`, `ttft_abort_ceiling_ms`, `ttft_abort_floor_ms`, `local_slow_demote`, `ttft_race_first_token`.

The OpenRouter GET adds **`active_variants`** at `0x180af3b62` within `ConfigPageGet`, `0x180af33a0–0x180af3dbb`. It is bounded list metadata, not another rotation. `pages/AILLMs.variants.jsx:47–56` confirms this. It must not be used to omit configured orphan variants from the safety inventory.

### Empty passthrough objects require care

The candidate explicitly seeds `provider_settings: {}`. The native recursive JSON-to-YAML helper (`0x1802103f0–0x180210914`) initializes an undefined/default YAML node. For an empty JSON object, its object loop at `0x1802106bb–0x1802107e9` performs no indexed assignment to create a map, so it can return a null node. `provider_settings` can consequently round-trip as explicit JSON null. Its UI schema type may be `string` for an editor, while native load/save supports structured JSON values (`0x180210920–0x180211ce0`).

Do not treat every null or missing value as safe. Any adaptation should distinguish missing from explicit null and apply only to the source-pinned `provider_settings` fields after every applicable fallback layer is proven empty/disabled. Native request-body merge/null handling still needs a bounded verification before upgrading this part of the audit to complete. The same caution applies to nullable optional slot controls; this candidate supplies concrete values to avoid relying on those defaults.

### Subsequent static resolution review

The [request-body and inheritance audit](se-lab-native-passthrough-findings.md)
now traces the pinned chat builder. A final resolved null adds no body keys;
null at a slot can still inherit. A conservative audit may accept only explicit
null or `{}` at every present, fully covered configured layer. Missing fields
remain incomplete. Actor/faction/group overrides are a separate native input
that the four GETs do not cover. No collector relaxation or provider invocation
has been implemented from this finding.

## Next review boundary

After the parent closes and retains the fifth run, implement the seed and collector changes as a separate reviewed checkpoint with fixtures for native reinsertion, disabled decisions preservation, exact style retention, variant fallback keys, custom schema descriptors, null-vs-missing passthrough, unknown fields, overflow and redaction. A fresh disabled native boot/readback must then confirm that all six catalog endpoints and both slot bindings retain the candidate values. Only a separate subsequent decision can authorize a fake listener or one-shot chat diagnostic.

No native provider request, decisions request, AI enablement, active seed change, installed write or game operation occurred in this investigation. No claim is made about egress prevention, model behavior or normal tavern AI readiness.
