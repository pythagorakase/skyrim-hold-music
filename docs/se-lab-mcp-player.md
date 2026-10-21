# One guarded player snapshot

`tools/se_lab_mcp_player.py` adds a separate fixed `get_player_info` query after
successful same-run disabled-config smoke and complete MCP discovery. It reuses
the existing strict discovery transport without changing launch, smoke, routing,
discovery, or plugin inspection. This checkpoint has synthetic fixture coverage;
actual player-query acceptance is pending.

```powershell
python -B tools/se_lab_mcp_player.py plan --run-id RUN --smoke-capture SMOKE_JSON --discovery-capture DISCOVERY_JSON
python -B tools/se_lab_mcp_player.py collect --run-id RUN --smoke-capture SMOKE_JSON --discovery-capture DISCOVERY_JSON --review-token TOKEN
```

The plan makes no network request or filesystem write. It binds both retained
captures, the exact live game identity, current module paths/hashes, collector
and CLI bytes, and the native implementation and schema described below. It
refuses wrong-run, incomplete, contradictory, changed, or foreign captures.
The existing user authorization for isolated lab testing covers the possible
lab-only identity bookkeeping described here; this is not a zero-write server
query or a request to enable AI.

Collection performs at most five HTTP requests in one bounded session: SSE GET,
initialize, initialized notification, tools/list, and one tools/call with exactly
`{"name":"get_player_info","arguments":{}}`. Fresh discovery must contain the
exact case-sensitive tool name and exact native empty schema. A `get_plugins`
entry cannot substitute even though it has the same schema hash.

Only direct `127.0.0.1:18889` connections and the validated announced `/message`
endpoint are used. The transport retains socket/process ownership checks,
fixed protocol `2024-11-05`, strict HTTP/SSE/JSON framing, 60-second total limit,
2 MiB cumulative receive limit, 512 KiB event limit and 128-event limit. It
advertises no sampling or client tools. Proxies, redirects, credentials, arbitrary
tool names/arguments, pagination and automatic retries are unavailable. The
native-hash-bound SSE header compatibility is forwarded only from the validated
discovery binding; POST acknowledgements remain strict.

The call is marked attempted before `sendall`. A partial send, failed
acknowledgement or missing/invalid reply produces `tool_call_outcome:"unknown"`,
an incomplete result, and no retry. A fully validated reply remains explicitly
distinguished from a successful final identity check. Context drift or an
overrun during the last check prevents `player_snapshot_observed`.

Completed collection attempts retain a new report under
`.skyrimnet-tier-runtime/mcp-player/`; smoke, discovery, input files and earlier
reports are preserved. An unsuccessful preflight makes no tool request. Reports
use only fixed diagnostic codes, never raw exception/server error strings.

## Pinned native contract

The clean beta26-rc4 DLL SHA-256 is
`2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
Static registration at preferred VA `0x180d0ea6b`, callable `0x180d128f0`, and
handler `0x180cf56d0` establish the schema `{"type":"object"}` with canonical
SHA-256 `a2c799262a3ce3c19ef5cdd983bf3d12b43ab3c426227091b909dcb7054738c0`.
The handler ignores arguments; this client nevertheless permits only `{}` and
rejects extra schema keywords rather than inferring their meaning.

The handler checks SkyrimNet's internal ready predicate and obtains its player
wrapper. It then serializes exactly these fields as JSON inside one text block:

| Field | Accepted type |
| --- | --- |
| `uuid` | Python integer in `0..2**64-1`; bool and float rejected |
| `name` | Nonempty UTF-8 string, at most 1,024 bytes, no control characters |
| `formID` | Canonical `0x` plus eight uppercase hexadecimal digits; player acceptance requires `0x00000014` |
| `level` | Python integer in `0..65535`; bool and float rejected |
| `position` | Exactly `x`, `y`, `z`, each a finite JSON number; bool, infinity and oversized integers rejected |

The envelope must be exactly `isError:false` and one `type:"text"` content block.
The native readiness failures are plain text `Error: Game is not ready yet` and
`Error: Player not available`, even when the outer error flag is false. They
therefore produce incomplete observations with fixed diagnostic codes. HTTP
success or `isError:false` alone never proves player availability.

The reply has **no cell identifier, location, health or fresh-world nonce**.
Coordinates cannot establish QASmoke. The readiness predicate and subsequent
reads are sequential; they do not prove an atomic engine snapshot.

## Internal side effects and honest output

`GetPlayer` calls `EntityMap::MakeAndAddToMap` (`0x18044601d → 0x180193660`),
which may allocate/cache an Entity and call `UUIDResolver::AddMapping(false)`.
The false flag is not a no-write option: incomplete/missing mappings can reach
`UUIDResolver::SaveToDatabase` at `0x180191250 → 0x1802c2f80`, and conditional
rename bookkeeping can reach `IdentityAliasStore::RecordRename` at
`0x1801912cd → 0x18073fd00`. The inspected handler does not request actor movement,
quest/Papyrus/console actions, provider inference, embeddings, audio or generation.
That bounded finding does not establish absence of other work elsewhere in the
process. Reports disclose `identity_bookkeeping_may_write:true`.

The output retains typed validity checks, canonical-player-form equality,
name hash/length, and hashes/sizes of received text. It exports no raw name,
UUID, coordinates, response body, arbitrary descriptions or session identifier.
`activity.raw_rpc_data_sha256` hashes the actual UTF-8 JSON-RPC SSE data payload
before JSON parsing, including its whitespace and member order. It excludes
HTTP chunk/SSE framing; it is not a hash of a reconstructed object. The separate
`text_sha256` hashes the received inner text. Both may bind private content
without exporting it. A raw payload hash alone is not validation.

`player_exists` is true only on a completed canonical-player observation; it is
null when that fact remains unestablished. Cell, QASmoke, fresh world, actor AI,
playback and egress verification remain false. A separate visual observation
can provide its own world-readiness evidence. The collector cannot load a save,
start a world, move the player, enable AI, or make a paid generation call.

Detailed offline disassemblies and the static contract are retained in
`local/se-lab-player-info-audit-20261021/`. The fixture suite is
`python -B -m unittest discover -s tests -p test_se_lab_mcp_player.py -v`.

## Optional dependency notice during the sixth run

In run `20261021T120618Z-1473fc07a7ba`, a visible interior was covered by a
SkyrimNet notice about missing optional UIExtensions support for the wheel menu
and original Dragonborn Voice Over v1.1.1 support for silent voice playback and
the Universal Translator. The notice remained visible after one Okay click and
Return. Subsequent guarded `get_plugins` and `get_player_info` calls passed;
the player observation confirmed the canonical player form. This establishes
successful native readback despite the notice, not successful notice dismissal.

Static inspection used the clean beta26-rc4 DLL with SHA-256
`2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
The addresses below are preferred virtual addresses, not live process addresses.

- `get_player_info` calls the readiness predicate at `0x180cf5715`, and
  `get_plugins` calls the same predicate at `0x180cf632f`. The predicate at
  `0x18098fb90` accepts lifecycle states 4, 5, 7 and 8. It does not directly
  inspect optional dependencies or menu visibility.
- The optional notice constructs Okay as button index 0 and Ignore as index 1
  (`0x1801d636b–0x1801d63d5`). Its callback at `0x1801d4a20` returns immediately
  for every index except 1. Okay therefore performs no configuration mutation
  in this callback.
- Ignore stores the current warning signature in the game configuration's
  `diagnostics.ignored_optional_signature` field, then calls
  `ConfigManager::SaveConfig("game")` at `0x1801d4ae2`. It attempts persistent
  suppression through a game-config save; the callback ignores the save return
  value, so selecting Ignore alone would not prove successful persistence.

The notice is queued through `QueueMessageSequence` at `0x180451c80`.
This inspection does not establish whether the engine was paused, whether the
click or Return reached the intended button, or whether another notice was
queued. Neither the visual observation nor the player reply establishes the
exact cell as QASmoke. No additional dependency installation or Ignore selection
was needed for these successful readbacks. Any future Ignore selection should
be recorded as an intentional configuration-save action, not treated as ordinary
nonpersistent dismissal.
