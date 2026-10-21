# Pinned provider_settings null and inheritance review — 2026-10-21

This is static analysis of the clean beta26-rc4 DLL. No process was attached, no DLL code was executed, no game/configuration was changed, and no endpoint/provider request was made. The previous routing collector and all launch-bound source files remain unchanged.

## Decision

**Explicit null is not a universal inheritance barrier.** For the selected OpenRouter chat request path, the final resolved JSON null contributes no request-body keys, but a null **slot** setting is skipped and can inherit a provider or lower-layer setting. Conversely, a resolved provider record returns its `provider_settings` even if null; an engaged variant-level optional can also return null without falling through to the base. Missing fields are not interchangeable with explicit null in an audit.

A limited acceptance rule is justified for the candidate's **observed configured graph only**: accept explicit null or an exactly empty JSON object at every applicable root, variant, provider and slot `provider_settings` path, after every provider reference resolves uniquely and every collection/field is fully audited. Preserve missing as incomplete. Do not label this `inheritance_disabled`; use a scoped claim such as `configured_passthrough_empty`. This does not establish arbitrary actor/group overrides, every native API style, unseen fallback behavior, or zero egress.

The candidate's custom chat provider is especially useful: its explicit empty/null setting is returned before variant/base fallback when the slot has no non-null override and the provider resolves. This is not an excuse to omit dormant lower layers from inventory.

## Pinned inputs and method

- Archive: `local/se-lab-downloads/skyrimnet-beta26-rc4.zip`, SHA256 `6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef`.
- Member: `SKSE/Plugins/SkyrimNet.dll`, SHA256 `2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
- Preferred image base: `0x180000000`; all addresses below are static preferred-image VAs, not observed live addresses.
- `local/inspect_provider_settings_20261021.py` locates exact public string literals and direct call references, then uses PE unwind-function bounds and Capstone disassembly. `local/dump_provider_functions_20261021.py` restricts final dumps to specified functions. These helpers read the ZIP member and write only ignored local evidence.
- The function names quoted below are corroborated by embedded logging literals. Other function descriptions are inferred from data flow, member offsets, branching and copy operations; they are not recovered source declarations or native execution tests.
- SHA-indexed disassemblies used for this review are in `evidence.json`. Broad intermediate xref dumps are working material, not a claim that every native consumer has been audited.

## Request-body consumer

`SkyrimNet::LLM::OpenRouterInterface::CreateRequestPayload` is identified by its embedded log name at `0x18037eef5` in function `0x18037e250`.

At `0x18037ef13–0x18037ef20` it calls `0x180216840` with the current variant and override key, retaining the resolved JSON at `[rbp-8]`. `0x18037ef26–0x18037ef34` skips the merge unless the JSON type byte is nonzero and exactly 1 (object). Thus null (type 0), arrays, scalars and strings are not merged by this block. A nonobject should still remain invalid/incomplete in an audit; ignoring it at this block is not general safety evidence.

For an object, `0x18037ef3a–0x18037ef6f` obtains begin/end iterators. Empty objects have no entries. `0x18037ef75–0x18037f00d` loops over entries, copies each value and key, indexes the already-created request object at `0x18037efcb`, and assigns that value at `0x18037efd7`. Helper `0x180209b20` swaps the complete JSON value into the indexed destination, then destroys the displaced value. This is top-level key assignment: a nonempty passthrough can overwrite an existing request field; this is not a recursive merge-patch null-deletion operation. A null *value inside a nonempty object* is consequently different from an entire null settings object and must not be accepted as empty.

## Resolution order and exact branches

The resolver is `0x180216840–0x180217294`. It chooses one JSON settings value; the body consumer does not independently merge provider, slot, variant and base objects together.

| Order | Layer | Evidence and null behavior |
| --- | --- | --- |
| 1 | Override-context raw slot | `0x1802168b3–0x1802168bb` calls `0x180214810`. That helper only uses the base `openrouter.model_params` override path when the variant is empty and a nonempty override key exists (`0x180214845–0x180214883`, `0x18021492a–0x180214968`), then indexes the selected slot. In the resolver, a defined `provider_settings` must have YAML type other than Null (`0x18021694f–0x18021695c`). A non-null value converts through `0x180210920` and returns (`0x180216a1c–0x180216a69`). Missing/null skips this layer. |
| 2 | Parsed selected slot | If `0x180212150` does not establish an override model-list replacement, `0x1802139f0` returns the indexed slot. It selects variant model params when an explicit variant model list is engaged, otherwise the base list (`0x180213a64–0x180213b37`). The resolver checks both the outer optional slot and the inner settings optional (`0x180216ad9`, `0x180216ae7`) and returns the latter's JSON (`0x180216af1–0x180216b01`). The slot parser excludes explicit YAML Null from this optional, so an ordinary loaded null slot falls through. |
| 3 | Resolved provider catalog row | `0x180216bcd–0x180216bde` passes member offset `0xa8` to `0x1801ec7f0`. The helper resolves the slot provider with `0x180213c90` and copies its settings member when the provider exists (`0x1801ec829–0x1801ec844`). The resolver tests only this outer optional's presence at `0x180216be4`; it does not test the returned JSON for null before returning it. A resolved provider's null/empty object therefore suppresses lower variant/base fallback. An unresolved provider does not. |
| 4 | Variant override-context node | For a nonempty variant and override key, the resolver constructs `openrouter.variants.<variant>.provider_settings` (`0x180216d34–0x180216de6`) and calls `BaseConfig::GetOverrideValue` at `0x180216e56`. Defined non-null YAML is converted and returned (`0x180216f22–0x180216f8d`); missing/null continues. |
| 5 | Parsed variant-level optional | It finds the variant at `0x180217012–0x180217048`, tests presence of the settings optional at offset `0xf0`, and returns the JSON at `+0xe0` (`0x180217035–0x18021705e`). It does not retest that JSON for null. Explicit variant null can be an engaged optional; missing is different. |
| 6 | Base override-context node | With a nonempty override key, it looks up `openrouter.provider_settings` (`0x1802170b0–0x1802170ee`). Defined non-null YAML converts and returns (`0x180217150–0x1802171b0`); missing/null continues. |
| 7 | Parsed base | Final fallback copies `[TextModelConfig+0x118]` at `0x18021720d–0x180217217`, including JSON null. No lower passthrough layer appears in this resolver. |

Provider resolution itself is observable: `0x180213c90` first checks a raw slot provider ID, otherwise its parsed slot's provider ID; `0x18025ab20` obtains the `Providers` config and asks its catalog lookup at `0x18025ac26–0x18025ac2c`. Missing or unresolved IDs cannot be silently treated as empty passthrough. Duplicate IDs must remain an audit error rather than depending on native lookup order.

### Load and round-trip distinctions

- JSON-to-YAML helper `0x1802103f0` starts with a default YAML node. Its empty-object iteration creates no map entry. The earlier proposal's explicit `{}` can therefore round-trip as null. An object that contains a key with null value is nonempty and does not qualify as empty.
- YAML-to-JSON helper `0x180210920` explicitly maps YAML type 1 (Null) to JSON type 0 at `0x180210965–0x18021097e`.
- Slot model-params parser `0x180894930` checks node presence, then rejects YAML Null before engaging its optional (`0x180894efd–0x180894f70`; conversion/engagement only at `0x18089501f–0x1808950e5`). This confirms null and missing both leave the freshly parsed slot settings optional disengaged, so both may inherit.
- Provider loader `0x180250810` checks that the key is defined, converts it at `0x180251345`, then assigns the JSON member at `0x180251352–0x18025137d`. Unlike the slot parser, it does not reject YAML Null. The provider serializer maps member `+0xa8` back through the recursive converter at `0x1802676b0–0x1802676be`.
- Base loader `0x180252910` converts defined base settings at `0x180253bc8` and calls `0x18026ef80`; that helper assigns the JSON member at `+0x118` without a null exclusion.
- The same loader converts defined variant settings at `0x180254e78` and engages an optional using `0x1801df790` at `0x180254e89`. The optional setter marks `+0x10` present even for JSON null (`0x1801df7fb–0x1801df80f`). This supports the parsed-variant null behavior above.
- A missing base/variant key skips its loader assignment. This review does not assume missing values erase previous in-memory state during reload. Even where a fresh constructor supplies an empty object, that does not justify synthesizing an absent live GET field from a schema default.

## Additional override boundary

`0x180f88030` is explicitly identified as `FatelessEngine::Config::BaseConfig::GetOverrideValue` by embedded logging literals. It consults actor-specific, faction-group and explicit-group data; those paths appear at `0x180f88251`, `0x180f887d2`, and `0x180f88f9e` respectively. The function returns no override when passed an empty override key (`0x180f88092–0x180f88096`).

The four existing routing/config/schema GETs do not inventory every actor/group override. Therefore an eventual one-shot fake-chat selection must separately bind a known empty override context, or obtain a separate reviewed complete audit of the applicable override data. The all-configured-graph report must keep this limitation explicit even if all visible settings are null/empty. It cannot claim arbitrary character requests are fake-only.

This review establishes the observed chat builder's passthrough handling. It does not validate the decisions API's request builder or every native endpoint/protocol merely because a catalog row is loopback.

## Proposed bounded audit normalization

1. Pin this exact native DLL and validate the returned configuration graph, all field types, all providers, both default and every configured variant, every slot (including disabled/backups), alignment, limits and unique references. Reject incomplete/skipped collections.
2. Require the `provider_settings` key to be **present** at base, every variant, every provider and every slot in the returned graph. Accept only `null` or a dictionary with zero keys at these exact known paths. Preserve which representation was observed as fixed counts, never raw values. Do not accept empty arrays, strings, booleans, numbers, nested null-key objects, arbitrary same-named fields, or missing values/schema defaults.
3. Do not use an empty higher layer to exempt a nonempty lower layer. For this limited candidate, rejecting every nonempty applicable layer is easier to verify and avoids fragile route-specific shadow reasoning. Mark the scoped result as configured passthrough empty, not disabled inheritance and not a native fallback proof.
4. Require explicit credentials/endpoints and unique selected provider references independently. Null handling must not relax credential, provider-ID, routing-role, mode, retry or timeout checks.
5. Keep `native_fallback_verified=false`, `egress_verified=false`, and actor/group override coverage false. A future fake-chat diagnostic must restrict the selected protocol to chat and bind empty override context; it still needs its own explicit execution approval and listener ownership checks.

## Regression cases for a future implementation

- Entire graph has explicit `{}`; same graph round-trips every exact settings path as null: both establish only scoped configured-passthrough emptiness.
- Every individual base/provider/slot/variant path removed: remains incomplete; schema `defaultValue: null` or `{}` cannot repair it.
- Null slot plus provider `{secret_sentinel: ...}`: fails. Null slot/provider with nonempty variant/base also fails the conservative all-layer audit even if current provider shadows it.
- Null value inside a nonempty object, an empty list, whitespace string, boolean and number at each path: fail without leaking their contents.
- Missing/duplicate provider ID; extra/hidden variant; disabled backup carrying passthrough; overflowed provider or slot collection: fail completeness.
- Actor/group override context nonempty or unverified: cannot upgrade to native-request/diagnostic readiness from the four-GET result.
- Non-chat catalog row may remain inventoried, but can never be selected by the constrained chat diagnostic.

No test of real provider request construction was run. The checks here are static branch/data-flow evidence, not native execution, installation acceptance or a zero-network guarantee.
