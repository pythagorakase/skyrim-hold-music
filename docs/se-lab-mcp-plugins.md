# One guarded MCP plugin query

`tools/se_lab_mcp_plugins.py` adds a separate, explicitly reviewed `get_plugins`
inspection after successful disabled-config smoke and complete MCP discovery.
It does not change the launch, smoke, routing, or discovery transports. The
implementation has fixture and fake-socket coverage; live tool-call acceptance
is still pending.

```powershell
python -B tools/se_lab_mcp_plugins.py plan --run-id RUN --smoke-capture SMOKE_JSON --discovery-capture DISCOVERY_JSON
python -B tools/se_lab_mcp_plugins.py collect --run-id RUN --smoke-capture SMOKE_JSON --discovery-capture DISCOVERY_JSON --review-token TOKEN
```

Both captures must be retained in their fixed isolated-lab directories, refer
to the exact live attributed game, and match the current implementation and
disabled-control evidence. The plan performs no network requests. It binds the
capture hashes, native module identities, the current module/CLI, the recorded
`get_plugins` schema hash, and the original and currently observed profile
`plugins.txt` hashes. A failed
or incomplete discovery capture cannot authorize a call.

MO2 was observed prepending exactly these two LF-terminated lines (106 bytes)
to the canonical 71-byte, five-plugin seed:

```text
# This file is used by Skyrim to keep track of your downloaded content.
# Please do not modify this file.
```

The launch pin must still equal the canonical seed hash. Current bytes must be
exactly that seed or exactly this header followed by that seed; arbitrary
comments, BOMs, CRLF conversion, reordering, and changed rows are rejected. The
plan binds the original hash, observed hash, and recognized form separately,
and reports `byte_identical_to_launch:false` for the header form. A form change
invalidates an earlier plan or final-context check. No installed file is edited.

Collection opens one direct IPv4 connection to `127.0.0.1:18889` for `/sse`, then
sends only initialize, initialized notification, tools/list, and one
`tools/call` with `{"name":"get_plugins","arguments":{}}`. Each accepted TCP
peer must belong to the attributed game. The existing strict JSON-RPC/SSE/HTTP
framing and size/deadline checks apply. Proxy environment settings, redirects,
credentials, arbitrary methods, arbitrary arguments, pagination, and automatic
retries are not used. Fresh tools/list must contain exactly one case-unambiguous
`get_plugins`, with a schema matching the retained hash. Only a small understood
object-schema subset accepting `{}` is admitted; unreviewed constraint keywords
are rejected even if the required-property count is zero.

The transport forwards only the native-hash-bound SSE compatibility descriptor
from the validated discovery binding. The reviewed duplicate Content-Type pair
is permitted only for the SSE GET response; POST acknowledgements remain
strict. The capture reports whether this specific normalization occurred.

The tool call is marked attempted before sending, including partial-send cases.
An absent or invalid response remains an unknown outcome. There is no second
call within that collection. Every completed collection attempt retains a new
capture under `.skyrimnet-tier-runtime/mcp-plugins/`; it does not overwrite smoke,
discovery, or prior plugin captures. Exact process/context identity is checked
again before reporting success. A final-context check that exceeds the total
60-second budget cannot produce a successful result.

## Pinned native contract

The clean beta26-rc4 archive contains `SKSE/Plugins/SkyrimNet.dll` with SHA256
`2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
Static disassembly establishes:

- Registration at preferred VA `0x180D0DB5B` sets the tool name/description and
  immediately builds an object input schema with no parameters or required
  keys. The handler does not inspect request arguments.
- Lambda `0x180D13340` invokes `0x180CF62E0`, which checks readiness, calls
  `GetAllLoadedPlugins` at `0x1804337D0`, serializes filename strings as a JSON
  array, and returns a text-content block through `0x180CE6260`.
- The tools/call dispatcher at `0x181463CF0` places that block array under
  `content` and initializes `isError` to false. The supported result is exactly
  `{"isError":false,"content":[{"type":"text","text":"[...filenames...]"}]}`.
- Readiness failure uses the same text envelope with
  `Error: Game is not ready yet`. It does not set the outer error flag. The
  collector therefore requires parsed filename-array content; `isError:false`
  alone is insufficient. That exact readiness message produces only the fixed
  `game_not_ready` diagnostic, an incomplete result, and no retry.

The shipped devkit workflow also shows a no-argument `get_plugins` call and
describes loaded `.esp/.esm/.esl` filenames. The [public workflow](https://github.com/MinLL/SkyrimNet-GamePlugin/blob/main/docs/modding/WORKFLOW_ACTIONS.md)
is useful corroboration, but its main branch is not the pinned release. The
devkit does not ship this native handler's source. Static extraction scripts,
function dumps, hashes, and the detailed audit are retained locally in
`local/mcp-get-plugins-static-20261021/` and
`local/se-lab-mcp-get-plugins-static-audit-20261021.md`.

## What the capture establishes

Only the already pinned profile filenames appear in output, each with a
presence boolean. Other returned filenames remain private in memory; the report
contains counts and hashes, not their raw list or response text. Mixed results,
duplicate case aliases, filename paths, oversized lists/text, unsupported result
envelopes, or game-readiness messages fail validation. A well-formed response
missing any expected profile plugin is retained as incomplete.

The native enumeration reads loaded-file state but may initialize an internal
plugin cache and write diagnostic logs. Thus this is a non-mutating game-state
query, not a zero-server-side-effect claim, and cached results are possible.
Filename presence does not establish VFS winners, native initialization, actor
behavior, audible playback, provider inactivity, or zero network egress. Those
readiness flags remain false; no actor, quest, console, configuration, provider,
or paid-generation action is exposed by this collector.
