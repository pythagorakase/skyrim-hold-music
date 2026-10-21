# Disabled SkyrimNet lab: bounded MCP discovery

This collector checks protocol initialization and the registered tool inventory
of an already launched, attributed SkyrimNet lab process. It sends **zero
`tools/call` requests**. It does not invoke game inspection tools, execute
console or Papyrus functions, change settings, install, launch, stop, authenticate,
or request provider generation. Opening a session does create server protocol
state; discovery is not a claim of zero server-side effects.

The implementation is `hold_music/se_lab_mcp_discovery.py`; its CLI is
`tools/se_lab_mcp_discovery.py`. It requires a successful exact-run capture from
the [disabled-config smoke collector](se-lab-skyrimnet-smoke.md), as well as a
currently live attributed tier. An older successful capture cannot authorize a
replacement process.

## Commands

Run from the repository root with the established Python interpreter:

```powershell
& '<Python>\python.exe' -B -X utf8 tools/se_lab_mcp_discovery.py plan --run-id '<attributed tier run ID>' --smoke-capture '<successful exact-run smoke capture.json>'
& '<Python>\python.exe' -B -X utf8 tools/se_lab_mcp_discovery.py collect --run-id '<same ID>' --smoke-capture '<same capture.json>' --review-token '<discovery plan token>'
```

`--run-id` and `--smoke-capture` are required for both operations.
`--review-token` is required only for `collect` and is rejected for `plan`.
Installation, launch and config-smoke tokens are not discovery tokens. The CLI
does not expose a host, port, method, tool name, raw payload, credentials, timeout
override or injectable probes.

`plan` reads retained evidence and current process/module/TCP identities without
opening an endpoint connection. It binds the review to the exact run, game PID,
full native creation ticks, executable path and launch lineage, pinned module
paths/hashes, listener ownership, successful config capture and discovery
implementation. Missing, stale or changed evidence blocks collection; finding a
similarly named process does not establish attribution.

`ready_for_bounded_discovery` means the plan passed. A collection is successful
only with `tools_discovered`; incomplete evidence must not be promoted to a
passing result. The CLI returns JSON and exits zero only for the operation's
expected success status. Exceptions produce a generic `incomplete` JSON result
without exception text, session data or response content.

## Fixed transport and request sequence

The only destination is numeric IPv4 loopback `127.0.0.1:18889`. The collector
uses direct connections without environment proxies, redirects, authentication,
cookies or authorization headers. It checks the attributed game and listener,
then verifies each accepted server-side TCP connection before sending HTTP.
Ownership or identity ambiguity is a refusal. Collection rechecks its bindings
and does not adopt a restarted game or another listener.

One bounded session contains these four requests:

1. `GET /sse`, accepting one validated relative endpoint announcement for
   `/message` with exactly one bounded opaque `session_id` value. Absolute URLs
   are rejected, including ones naming the fixed origin.
2. POST JSON-RPC request ID `1`, method `initialize`, protocol version
   `2024-11-05`, empty client capabilities, and the fixed client identification
   `Hold Music SE Lab discovery` / `1`.
3. POST `notifications/initialized` without an ID, after a matching successful
   initialization response negotiating exactly `2024-11-05`.
4. POST request ID `2`, method `tools/list`, with empty parameters; require its
   matching successful SSE response containing the bounded tools array.

HTTP acceptance alone does not establish method success. The collector closes
the SSE connection after the exchange. It does not follow pagination, retry,
perform fallback discovery, answer server requests, or send sampling,
elicitation, roots, prompts, resources or game tool calls. A pagination cursor
means the inventory is incomplete.

Initialization also requires nonempty string `serverInfo.name` and
`serverInfo.version`, bounded to 256 and 128 characters respectively, with no
control characters. Their raw values are not exported; only the initialization
response hash is retained.

Before each POST and after the final reply, the client refuses any bytes already
pending in its decoded SSE or HTTP framing buffers. This prevents early replies
or trailing work from being accepted as the expected exchange. The check is
deliberately conservative: even a buffered heartbeat can make discovery
incomplete. It does not poll for later traffic or establish that no future
server event could arrive.

The reviewed bounds are 60 seconds total, four requests, 2 MiB cumulative
received bytes, 16 KiB HTTP headers, 16 KiB per POST acknowledgement body,
64 KiB per SSE line, 512 KiB per event, 128 events, 512 tools and 128 characters
for the session ID. Supported bounded HTTP/SSE framing includes
ordinary chunked SSE. Malformed, ambiguous, oversized or unsupported traffic
produces incomplete evidence, not a larger request or an alternate endpoint.

## Evidence and limits

The result retains sanitized attribution, method sequence, negotiated protocol,
matched response IDs, counts, all syntactically bounded validated tool names,
schema hashes and completion/failure flags. Schema projections include the
root type, property/required counts and property type counts; property names
are omitted. It does not retain raw session identifiers, arbitrary tool
descriptions or defaults, prompt content, credentials, or raw payloads.
Tool names containing the actual session token are rejected, case-insensitively.
Returned descriptions are untrusted data and cannot expand the request scope.
Schema hashes identify the observed schemas; they are not a stored, reviewed
copy of every callable argument contract.

Sanitized captures are written to
`C:/MGO/HoldMusic-SE-Lab/.skyrimnet-tier-runtime/mcp-discovery/<capture-id>.json`.
The `client_tools_call_enabled` and `tools_call_requests_performed` flags stay
false; they describe this client's scope, not the server's available capabilities.

`tools_discovered` establishes only that the attributed process accepted the
selected protocol and returned a complete inventory through this transport. It
does not establish that any listed tool works or has no internal side effects.
Runtime playback, provider calls, egress, all native initialization and game
inspection tool execution remain unverified. Discovery does not replace the
separate config smoke result or the accepted Hold Music runtime baseline.

Later candidates include `get_plugins`, `get_player_info` and
`get_nearby_actors`, after a separately bounded schema review. They are not called
here. In particular, a `get` or `search` prefix is not an authorization rule:
`search_memories` embeds its query; memory writes and knowledge imports can also
generate embeddings. Console execution, quest-function execution, content
reloads, template rendering, action eligibility evaluation and all mutations
remain outside this discovery scope.

## Shipped evidence and offline validation

The local beta26-rc4 release ZIP has SHA256
`6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef`.
Its `SKSE/Plugins/SkyrimNet.dll` has SHA256
`2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
These are DLL file offsets, not runtime addresses:

| Evidence | Offset |
|---|---|
| Constructor writes `/sse` | `0xCE1DF0` through `0xCE1E0E` |
| Constructor writes `/message` | `0xCE1E16` through `0xCE1E43` |
| Endpoint/session/message framing | `0x3BAC1D8`, `0x3BAC2E8`, `0x3BAC2F8` |
| `initialize`, `notifications/initialized`, `tools/list` | `0x1B618D8`, `0x3BAC418`, `0x3BAC1B0` |
| Protocol literals `2025-06-18`, `2025-03-26`, `2024-11-05` | `0x3BABF40`, `0x3BABF50`, `0x3BABF60` |

These constants support the interface design; they do not prove a current
listener or successful registration. The local beta26-rc4 devkit's
`docs/modding/WORKFLOW_MOD_INTEGRATION.md` lists player and nearby-actor queries
at lines 443-444 but supplies no initialization or transport specification.
The older inspection client used `[::1]:8889` and permitted arbitrary tool
calls; neither its address nor its unrestricted dispatch is used here.

Implementation validation uses fake observations and transport only. It must
cover process/peer replacement, stale bindings, split/chunked SSE, endpoint
escapes, duplicate or out-of-order replies, unsupported versions, server
requests, pagination, timeout/EOF/size limits and private-string redaction, and
prove that `tools/call` cannot be emitted. Such tests do not establish live MCP
acceptance. This document is not a record of a live discovery run.
