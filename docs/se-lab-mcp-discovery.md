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

### Pinned SSE Content-Type compatibility

The observed beta26-rc4 DLL inserts `Content-Type: text/event-stream` twice in
its MCP SSE response. The collector admits that one specific pair only when
the current observed SkyrimNet module has SHA256
`2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
Planning and collection bind that hash and contract
`beta26-rc4-sse-content-type-pair-v1`; a different observed DLL blocks admission.
The transport also requires an explicit `sse_content_type_compatibility` value
from that validated binding. Its default remains strict.

The exception applies only to the HTTP 200 response to the fixed SSE GET:
exactly two case-insensitive Content-Type field names, each with the literal
value `text/event-stream` after surrounding whitespace is stripped. Conflicting
values, parameters, combined values, another MIME type and a third copy are
rejected. The parser continues checking the entire header block and normal
framing limits. All other duplicate headers and all duplicate POST-response
headers remain rejected, including Content-Length, Transfer-Encoding, auth and
cookie fields. Successful observations record the boolean
`sse_content_type_pair_normalized`; single ordinary Content-Type remains valid
and leaves that flag false. This does not add a request or retry.

This is a reviewed interoperability exception, not general list-field joining.
[RFC 9110 section 5.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-5.3)
does not generally make singleton Content-Type duplicates list-valued.
[RFC 9112 section 6.3](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3)
separately governs framing ambiguity; those checks are unchanged.

The clean artifact's MCP handler `18146b740` inserts Content-Type through
`180aa8630` at `18146b9b0`, then its streaming setup `18146e530` inserts the
same value at `18146e606`. The common insertion routine increments the header
count and links a new node. These are static preferred-base addresses, not
loaded-process addresses. Retained capture `b66c1648a99048fdb6cd3181154e89bb`
confirmed the first rejected header was Content-Type with equal values; earlier
failed captures and their source snapshots remain unchanged. This observation
does not establish successful discovery beyond that former rejection point.

The reviewed bounds are 60 seconds total, four requests, 2 MiB cumulative
received bytes, 16 KiB HTTP headers, 16 KiB per POST acknowledgement body,
64 KiB per SSE line, 512 KiB per event, 128 events, 512 tools and 128 characters
for the session ID. Supported bounded HTTP/SSE framing includes
ordinary chunked SSE. Malformed, ambiguous, oversized or unsupported traffic
produces incomplete evidence, not a larger request or an alternate endpoint.
The total deadline includes the final process, module and retained-context
recheck. If that recheck finishes at or after the deadline, collection is
incomplete even when the returned inventory and identity checks otherwise pass.
Bounded native probes can finish after the deadline; their eventual return does
not turn an overrun into a successful discovery.

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

New captures include a fixed `diagnostics` projection. `failure_stage` identifies
the first failing phase, without retaining exception text or server content:
`sse_connect`, `sse_accepted_peer`, `sse_get_send`, `sse_headers`,
`sse_content_type`, `sse_endpoint`, `initialize_post`, `initialize_result`,
`initialized_notification`, `tools_list_post`, `tools_list_result`,
`inventory_validation`, `final_stream_validation`, `discovery_transport`,
`post_discovery_identity`, `final_context`, or `total_deadline`. It is null when
none of those checks failed. A stage names the operation being attempted, not
proof that its request reached the server. For example, a POST-stage failure can
occur during its pre-send ownership check or its HTTP acknowledgement.

`failure_reason` is also a fixed enum, never exception text. Handshake reasons
distinguish `socket_timeout`, `socket_error`, `unexpected_eof`, `framing_limit`,
`header_ascii`, `header_status_line`, `header_version`, `header_status`,
`header_field`, `header_duplicate`, `header_encoding`, `sse_content_type`,
`body_encoding`, `body_length`, and `peer_ownership`. Other fixed reasons are
`validation_or_probe_failure`, `deadline_exceeded`, `context_changed`, and
`context_failed`. A timeout of the socket read can occur before the overall
60-second deadline; these are separate observations.

`http_status` is null unless the failure can be associated with a parsed,
strictly three-digit HTTP code in the range 100-599. It never contains a status
reason phrase, arbitrary header name/value, URL, response body, or session identifier.
Status reporting does not make any additional code acceptable. Older captures
may contain only the coarse `sse_handshake` stage; they are not retroactively
classified or rewritten.

For a duplicate rejection, `duplicate_header` contains only an allowlisted
lowercase standard-header classification (unknown names become `other`), a
`values_equal` boolean, `occurrences_seen`, and `fields_seen`. Equality compares
the two values after the parser's existing surrounding-whitespace stripping;
it does not export either value. `occurrences_seen` is 2 at the first duplicate
rejection, or 3 when rejecting a third Content-Type after the permitted SSE
pair. Every other header classification remains limited to 2, and `fields_seen`
must be at least `occurrences_seen`. Counts describe only fields examined through that rejection, not the
complete header block. The pinned SSE pair above is the sole duplicate exception.

`final_context` is only `matched`, `changed`, or `failed`, and
`total_deadline_exceeded` is a boolean. These independent checks remain visible
when an earlier wire stage failed. Pagination can still make discovery
incomplete with no exception stage. These diagnostic labels do not change the
request sequence or retry policy. Older captures are left intact;
missing diagnostic fields cannot establish where an earlier attempt stopped.

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
