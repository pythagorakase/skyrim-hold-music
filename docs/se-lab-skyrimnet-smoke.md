# Disabled SkyrimNet lab: bounded live smoke observation

This separate collector observes an **already launched and attributed**
`MO2-SkyrimNet` process. It cannot install, launch, stop, enable, authenticate,
change settings, send MCP commands, or request provider generation. The existing
installer/launcher implementation and its receipts remain unchanged.

The implementation is `hold_music/se_lab_skyrimnet_smoke.py`; the CLI is
`tools/se_lab_skyrimnet_smoke.py`. It uses the existing tier process observer,
including its full native Windows creation ticks. It never mixes those identities
with a second timestamp representation.

## Commands and scope

```powershell
& '<Python 3.12>\python.exe' -B -X utf8 tools/se_lab_skyrimnet_smoke.py plan --run-id '<attributed tier run ID>'
& '<Python 3.12>\python.exe' -B -X utf8 tools/se_lab_skyrimnet_smoke.py collect --run-id '<same ID>' --review-token '<plan token>'
```

`plan` reads local evidence, live process/module identities and TCP tables. It
does not connect to a port or write files. It requires:

- The fixed lab root, exact separate tier launch command, retained run/launch
  identity and unchanged frozen launch implementation.
- The same currently live `SkyrimSE.exe` PID, full creation ticks, path and
  recorded MO2 → SKSE loader → game lineage. An unattributed or stopped launch
  cannot be upgraded by finding a process with the same executable name.
- Unchanged protected baseline MO2 and shared Game observations.
- All seven approved native module names, each observed at its **exact pinned
  physical mod path**, with current bytes matching the original launch inventory.
  A virtual `Game/Data/...` path is not silently mapped to a guessed physical
  winner. Missing, duplicate, unknown or unresolved correspondence blocks the
  plan. Only the seven expected names are enumerated; this is not an inventory
  proving that no other native module loaded.
- Exactly one IPv4 listener at each of `127.0.0.1:18880` and
  `127.0.0.1:18889`, both owned by that same game PID. Wildcard/foreign listeners
  fail. The MCP port is inspected only; no connection or protocol message is sent.

The review token binds the run and launch document hashes, game identity,
module paths/hashes, listeners, fixed route list and the new smoke module/tool
hashes. Installation or launch tokens do not authorize collection.

`collect` repeats that review under the existing lab/tier writer locks. It makes
one sequential GET per fixed category, with no retries. The only routes are
`/config?api=get&name=` followed by one of:

`game`, `STT`, `BardSinging`, `VastAI`, `Events`, `PlayerDialogue`, `Memory`,
`DynamicBio`, `UniversalTranslator`, `OmniSight`, `Agents`, `WebServer`, `mcp`.

There are no Auth, Providers, OpenRouter, file, log, dashboard, general status,
reload/update, action, chat, MCP or undocumented harness requests. A request
contains no authentication, cookie, privileged-token or proxy headers. Raw
sockets use only numeric IPv4 `127.0.0.1:18880`; environment proxy settings and
redirect destinations are never consulted.

After connecting but **before sending HTTP**, the collector requires an accepted
server-side `Established` TCP row with the exact client ephemeral port and the
attributed game PID. Merely observing a listener before connecting is insufficient.
It checks the live process again and rechecks ownership after the response. A
server-side connection table that cannot be observed is a refusal, not permission
to skip the check.

HTTP is bounded to a 60-second batch, at most four seconds per exchange, 16 KiB
of headers and 512 KiB of response body. It accepts HTTP/1.1 200, JSON content,
one decimal Content-Length and identity encoding. Redirects, authentication
errors, chunked/compressed responses, duplicate headers, malformed/duplicate-key
JSON and nonfinite numbers fail closed. Unsupported response framing may require
a separately reviewed extension; no automatic fallback is attempted.

## What the evidence means

Each GET response must contain an object at `.data`. The collector reads only
fixed nested paths and requires exact types and values; it does not use dashboard
defaults when a field is missing. The observed contract covers:

- Disabled master AI, Game Master, narration, Decisions, content auto-update,
  bard generation and fallback, VastAI, NPC/player reactions, memory background
  processing, dynamic biographies, translation, OmniSight and agents.
- TTS `noop` and STT `none`.
- The intended enabled loopback web/MCP hosts and exact ports.

Unexpected values are **not exported**. Reports contain fixed path names,
expected values, presence/type/match flags and response byte counts. The raw
response, arbitrary extra fields, errors, provider credentials, auth state,
environment and log text never enter the report. Errors have fixed generic
messages. A final process/module/protected-state recheck is required for a
complete observation.

New sanitized captures are written exclusively to
`C:/MGO/HoldMusic-SE-Lab/.skyrimnet-tier-runtime/smoke/<capture-id>.json`.
They do not rewrite the launch result, installation journal, native configs or
baseline captures. Incomplete captures are retained as incomplete evidence.

`disabled_controls_observed` means those backend values matched during this
bounded observation. It does not prove every native consumer honors them, that
all initialization succeeded, or that no requests occurred before observation.
Loaded path/hash correspondence is not an attestation of relocated process
memory or of every dependency/subsystem. Credentials, complete provider routing,
VFS write destinations, zero egress and gameplay remain unverified. The report
keeps `runtime_verified`, `egress_verified`, `credentials_verified`,
`effective_provider_routing_verified` and `all_native_initialization_verified`
false. No inference of billing authority is made from a GET response.

## Source evidence and tests

The clean official [beta26-rc4 release](https://github.com/MinLL/SkyrimNet-GamePlugin/releases/tag/vbeta26-rc4)
archive has SHA256
`6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef`.
Its shipped dashboard source maps establish the route and envelope:

- `assets/web/main.c0c96ccd.js.map` →
  `src/components/QuickToggles/quickTogglesApi.js`: fixed config GETs, `.data`,
  strict Boolean checks in the UI.
- The same map → `src/pages/ConfigPage.jsx`: config GET and separate schema GET;
  schema is a direct object, config data is the `.data` member.
- `assets/web-new/main.c12d8cff.js.map` → `shared/hooks/useConfig.js`:
  `/config?api=get&name=<ID>` and `.data`.
- Its `shared/pages/settings/PluginSection.jsx`: nested dot paths and schema
  types; `WebServerSection.jsx` and `MCPSection.jsx` establish the case-sensitive
  IDs `WebServer` and `mcp`.

The native backend implementation is not shipped as source. Native DLL strings
such as `MCPServerManager: MCP server started successfully on {}:{}` identify
possible log messages, not observed successful initialization. The frozen launch
checkpoint did not capture prelaunch shared Documents log content, so this smoke
collector deliberately does not infer fresh native initialization from a touched
`skse64.log` or `SkyrimNet.log`.

The independent source extraction and design provenance are retained in the
ignored `local/se-lab-skyrimnet-smoke-design-20261021/` directory. Tests use only
temporary trees, fake process/module/TCP observations and fake sockets/transports.
They cover stale/reused process identities, listener/connection ownership,
unresolved module paths, token drift, typed disabled controls, privacy sentinels,
malformed/bounded HTTP, and interrupted observations. They do not call a real
endpoint or establish runtime acceptance.
