# SE lab overnight checkpoint, 20–21 October 2026

The user released Steam for overnight work on the evening of 20 October.
Continue until 08:00 America/Chicago on 21 October, then summarize and pause the
`hold-music-offline-overnight-development` heartbeat. The old Echo watcher stays
paused. The former Steam-use deferral is lifted for the isolated lab only.

## Morning handoff (07:53 CDT)

Source checkpoint `9e977802123d7dc5ecb4c54ef0a9c5af84e65162` is synchronized
on Halcyon, GitHub and a clean Echo checkout. The current source has 301 passing
Windows cases with two platform skips across the 303-case suite; the three Qt
checks initially missing their optional bundle path passed separately. Echo's
full eight-suite run passed 297 cases with six expected platform skips
(303 total, 57.162 seconds), clean before and after. Its log is
`local/se-lab-echo-qasmoke-v3-9e97780-20261021.log`, SHA256
`0c1fb8a510c72c82eba8db9d087fde8b88aceaef423aa6f9248633ff42d61893`.

Final process inspection finds no relevant game/MO2 processes. The sixth tier
and its opaque cache are retained; active tier paths and `Game/default` are
absent. Both original Steam manifests remain read-only with their starting
hashes. No paid inference or audio-generation request was made by the tools.
Native startup transfer activity is explicitly documented below.

The controlled baseline's three engine scenarios pass. SkyrimNet v2 adds
effective disabled-control, plugin and player observations, with the visible
notice and incomplete routing capture preserved. The source-only v3 recipe and
routing correction are ready for a new isolated installation/readback; v3 has
not been installed or launched. The next live cycle should be completed and
retained as a whole, then advance to a bounded fake-provider check and controlled
coexistence. Natural NPC behavior, audible quality and SkyrimVR acceptance are
separate remaining checks. Pause the overnight follow-up after this checkpoint
is synchronized; leave the older Echo watcher disabled.

## Sixth run: player observed, controls disabled (07:20 CDT)

The QASmoke preparation was published as `0b9831b` and synchronized to clean
Halcyon/GitHub/Echo before installation. Echo's seven-suite verification passed
287 tests with six expected platform skips (293 total, 56.262 seconds). Its log
is `local/se-lab-echo-qasmoke-v2-0b9831b-20261021.log`, SHA256
`8938bab862944619314a016671fa93ad98b2c3c7ba2c14f0523365e4f36d58aa`.
Windows passed 108 tier cases plus one expected skip, 183 combined observer cases
plus one expected skip, and all 22 owned-process cleanup cases. These are test
results; the actual observations below are separate evidence.

Installation transaction `1acfa126b9c24448899c6444227b2263` staged 5,577 files;
preflight verified all seven native DLL winners, eighteen configuration winners
and the three exact public model inputs. Run `20261021T120618Z-1473fc07a7ba`
then launched with `native-filetime-v2` attribution. The saved history binds
game PID50156, loader PID21668 and MO2 PID43528 to exact paths and creation
ticks. Twenty-one raw source files and their receipt were preserved before
launch at `local/se-lab-qasmoke-v2-source-20261021`; this is distinct from a
Git archive whose line endings may be normalized.

| Observation | Capture | Result |
|---|---|---|
| Disabled controls | `bc518e689d8d478c92d44edee64b199c` | All 29 typed checks across 13 categories pass; seven DLLs and loopback listeners attributed |
| Routing | `826a769b8d384345979184cc471de585` | Four GETs complete, but graph remains incomplete |
| MCP discovery | `8ee59ff26eee434bb514768436fc0aba` | Successful tool inventory and matched final context |
| Loaded plugins | `871ccd9890c1408e84871f08a122550f` | All five expected plugins present among ten loaded plugins |
| Player snapshot | `b822bd766b304fae80282199a18a5b92` | Canonical player exists; UUID, level and coordinates pass typed checks |

The player query made one literal tool call after its prerequisites; raw name,
UUID and coordinates were not exported. It may persist lab identity bookkeeping.
No returned field identifies the cell. A stone interior, chests and compass were
visually observed, consistent with the fixed QASmoke startup. A SkyrimNet notice
about optional UIExtensions and original DragonbornVoiceOver requirements
remained visible after an Okay click and Return. No Ignore action or optional
dependency installation occurred. Do not claim confirmed notice dismissal,
unpaused gameplay, a programmatically identified cell, natural AI or playback.

The routing audit now sees all six providers, both rotations, both slots and
all ten explicit-null passthrough layers, with no skipped providers or unknown
fields. It reports four remaining issue categories: missing explicit/schema
value, unsupported routing policy, invalid retry/timeout and invalid typed value.
No provider diagnostic, inference or paid generation request was sent by these
collectors. Actor/group overrides, fallback and egress remain unverified. Keep
the original incomplete capture immutable while investigating serializer defaults.

Metadata capture `28a9515fdb364e4cbe636edc3a5f1044` and same-handle cleanup passed.
All relevant processes are closed, original assets are unchanged and runtime
storage was within the explicitly reviewed contract. Literal protected-path
equality is **false** because PrismaUI added its three permitted cookie database
files. Do not replace that result with an all-paths-unchanged claim.

Shared logs are archived under
`checkpoints/skyrimnet-qasmoke-v2-shared-logs-after-20261021`. The fresh
SkyrimNet log has 4,379 lines, 609,720 bytes and SHA256
`fe9b492cb5338d2900b70de49f0a615898b44fac3c37fa5779f4ac53dec52951`.
Fixed-pattern analysis finds no error/critical or configuration-load failure
markers and thirteen warning lines. It also finds a model-download start and
two download/verification completion markers; disabled AI is not proof of
zero startup traffic. The archived Papyrus.0.log matches its old hash and is
**not** fresh sixth-run world evidence. Retention and the final handoff follow
below; no second launch of this one-shot instance is authorized by its old token.

## Sixth-run retention and next bounded task (07:33 CDT)

Whole-tier retention completed at
`checkpoints/skyrimnet-qasmoke-world-observed-20261021`: 5,842 MO2 files,
two installation-journal files and nine runtime evidence files. Three exclusive
directory moves preserved their inventoried bytes and identities. The active
SkyrimNet tier paths are now absent; the baseline MO2/Game installation remains.
The source archive for `0b9831b` and the separate raw 21-file snapshot retain
their distinct lineage. Retention receipt SHA256:
`79ce07f90473ce8083820a525a7bc4ce034441ea44a57851f477cd6aca2cc521`.

The separate opaque-cache operation also completed. It moved only the three
permitted cookie database files into the checkpoint's `private-runtime-cache`,
without parsing their contents. Preexisting protected files remained unchanged
and `Game/default` is absent afterward. Cache receipt SHA256:
`da24a50856cb0562c2fd539d673d9d18e242c90e2e0315baaea38847187d7f4c`.
Neither operation changes the original literal protected-path result or upgrades
the incomplete routing capture. Root's retention/cache fixture suite passed
42/42 in 45.434 seconds, with independent 42-case runs also passing.

Exact public-seed reconstructions now match both sixth routing response hashes:
OpenRouter 2,155 bytes / `87f15080268d5bee81dd64f0dd73ea8de5fe33b053f0441b39781fd73e401179`;
Providers 1,813 bytes / `b26625cf5364f9dc6842d03530fab55be8c841c947eeb16077f6fadad0f34adf`.
They explain every reported issue: six omitted empty lender strings, four
omitted native routing defaults and two null default stop-sequence vectors.
The actual slot controls were explicit and valid. The reviewed correction
normalizes only those pinned serializer cases and reports fixed counts; malformed
explicit values and other required omissions still fail. The applied correction
passed 49/49 routing tests in Root's run (3.705 seconds), plus independent
mutation review. This source checkpoint does not rewrite the retained observation.

The seeded embedding/VAD models each logged local SHA verification. The extra
startup transfer concerned the finetuned Whisper small model. A source-backed
retained-file check found it at
`MO2-SkyrimNet/overwrite/SKSE/Plugins/SkyrimNet/models/ggml-skyrim-small.bin`,
487,601,967 bytes, SHA256
`a8ea2ae79712cf4f5fa51a68ffb0bdc8d108b82099566d834a0b445181317160`.
This matches the clean catalog and retention inventory. The catalog basename
includes `whisper`; the native destination omits it. Its old sidecar remains
preserved and is not a substitute for checking the model bytes.

The future recipe is now `skyrimnet-beta26-rc4-qasmoke-disabled-v3`, with the
same disabled provider/playback seeds and an exact four-file model catalog.
Its new local cache is
`local/se-lab-startup-model-cache-v3-20261021/startup-models.zip`, 581,087,797
bytes, SHA256 `19347f2a64830fdd3e7917e2ce2c3b9ef0a63dd012ad9d69a59b869a546c7d17`.
It contains only the three original public models plus the verified native
Whisper destination, with no sidecars. Membership, CRC, every decompressed
hash and unchanged retained sources were independently checked. No download
was needed. Provenance receipt SHA256:
`184bec5131db12447184eac224fa9e0238b3e1677dad802fa13a482ce5bc2c03`.

The actual read-only v3 installation plan has 5,578 files and no blockers,
recorded at `local/se-lab-qasmoke-v3-install-plan-20261021.json`. It performed
no installation. Four focused recipe tests pass, including rejection of an old
three-model cache, the wrong Whisper bytes/name, sidecars, corruption and a
shadowing winner. The frozen tier/routing suite then passed 155 cases with four
skips (159 total, 652.001 seconds). Three skips were native Qt/bundled-source
checks whose optional bundle-path environment variable was absent; all three
passed in a separate 0.166-second run against the verified retained distribution.
The remaining skip is Windows symlink creation. The other five observer suites
passed 143 cases with one expected platform skip (144 total, 41.908 seconds).
Together this covers 301 passing cases and two platform skips across the
303-case suite. No implementation changed between these runs.

Full-suite log: `local/se-lab-qasmoke-v3-full-root-tests-20261021.log`, SHA256
`19408855f9b225f05bd351ce7051abeaace70facc53e0cf0bce454c53d0f83aa`.
Observer log: `local/se-lab-qasmoke-v3-observer-root-tests-20261021.log`, SHA256
`d946552decfa666a95279b4d6b7e44994e02639c56826082c2a402ce0f35fc8d`.
The supplemental Qt log is `local/se-lab-qasmoke-v3-qt-root-tests-20261021.log`.
V3 has not been installed or launched; future runtime readback must be a fresh
observation. The actual installation-plan artifact remains an unapplied review.

The next live session should consume a reviewed four-model seed in a **new**
disabled instance, exercise the corrected routing audit with fresh attribution,
and deliberately resolve/observe the optional-dependency notice before claiming
unpaused gameplay. Keep generation disabled. After that, add one explicitly
bounded fake-provider dispatch check with its override context accounted for,
then test controlled Hold Music coexistence and ordinary NPC packages separately.
SE success still cannot clear the VR-specific native scan CTD or establish
musical/audible quality. Listening validation remains independent of this work.

## QASmoke preparation checkpoint (historical)

The working MCP checkpoint is synchronized at `0f5bdc6` on Halcyon, GitHub and
clean Echo. Echo's six-suite run passed 242 tests with six expected platform
skips (248 total, 46.553 seconds). Its log is
`local/se-lab-echo-mcp-checkpoint-0f5bdc6-20261021.log`, SHA256
`d774b2a0535c90b9ea17db543e98d01126ff74174ae5781c4ffc6d0cc8a8516a`.
This supersedes the earlier portable tar-fixture failure without rewriting it.

The next separate tier, `skyrimnet-beta26-rc4-qasmoke-disabled-v2`, binds a literal
QASmoke startup intent into preparation, installation and launch review. It uses
the unchanged vendor Skyrim.ini plus a fixed SkyrimCustom.ini; a highest-priority
MCM seed disables production Hold Music playback, and the harness stays disabled
with no armed request/result. The lower copied baseline files remain unchanged.
Its three public startup models are exact catalog matches recovered from the
previous retained run; no old verification sidecars are installed.

The explicit provider seed includes all five native built-ins plus the lab row,
with loopback endpoints, empty keys/key loans and a disabled decisions slot.
This prevents the known missing-ID/default insertion case, but it needs fresh
effective readback. The revised four-GET audit inventories every configured
layer, including disabled slots, and only admits explicit null/empty passthrough
after full coverage. Actor/group overrides and native fallback remain unverified;
no provider diagnostic or inference request is authorized by that audit.

A separate fixed `get_player_info` collector is ready for review. Its pinned
native handler may create and persist lab UUID/identity-alias bookkeeping. It
requests no game-state mutation or provider action. The redacted reply can
confirm the canonical player object and typed fields, but cannot establish a cell
or fresh world: the native tool returns no cell identifier. Visual scene
observation is a separate evidence source. Relevant tests and independent review
have now passed before the next installation and launch.

Root's combined smoke/routing/MCP/storage suite passed 183 tests with one expected
platform skip (184 total, 48.996 seconds). The unchanged owned-process cleanup
helper passed all 22 tests under the new tier in 6.629 seconds. Independent
review separately cleared all 40 routing and 24 player cases without live probes
or sockets. The new installation plan has 5,577 files and no blockers; it remains
unapplied. The full tier suite then passed 108 tests with one expected Windows
symlink skip (109 total, 646.941 seconds), including real Qt parser checks and
harmless native observer children. Both original Steam manifests remain
read-only and retain their original hashes. All functional sources stayed frozen
through these tests; the next step is publication, absent-only installation and
one fresh world-readiness launch.

## Retained main-menu checkpoint (06:35 CDT)

Fifth run `20261021T105157Z-a7f1bce383bc` is positively attributed with
`native-filetime-v2`. Its fresh installation transaction is
`f5e9389e26d24022bcb8aa36ad6b8eed`; first-boot preflight passed. The observer
retained MO2 PID45328, loader PID50044 and game PID10008 with their full creation
ticks and exact paths. Same-handle cleanup is now complete: game10008 exited
with the recorded forced code18509, MO2 exited naturally with code0, and a fresh
snapshot confirms all relevant processes closed. Whole-tier and opaque-cache
retention are complete; the next installation will need fresh preparation.

The fresh smoke capture `2e6d86c91f02414392cf9b618b03d637` passes all 29 typed
checks across 13 configuration categories. All seven pinned native modules
match physical paths and hashes; both loopback listeners belong to the same
game. Global AI, both GameMaster switches, bard generation, narration, telemetry
and the other requested services read back disabled. The main-menu window was
visually observed. No optional Anniversary download was accepted. This is
effective-control evidence, not a world-load, playback, or zero-egress result.
Smoke report SHA256:
`c528b7eebd2146ca6b32743228d56b8e8ecf4d9a63f5d75fba61b110c20dcb5e`.

Four routing GETs completed in capture `9d1631c5728d4f50b2b33119b4c51e14`.
Its audit remains `incomplete_or_mismatched`: six returned providers, one
variant and two slots include non-test endpoints/defaults and unresolved
inheritance/fields. No provider request was made; do not enable generation
from this evidence. MCP discovery capture `b914abeb74f74b0b81c5940074a722a7`
is also incomplete, with stable identity and a bounded discovery failure.
Two separately reviewed observations preserve that failure and narrow it:
`cd3d1e880d8f421a90f25369cd87ddc5` reports SSE handshake failure;
`aff92aaf04904e1aa67c86c2513128ce` reports `sse_headers/header_duplicate`,
HTTP200, matched final context and no deadline overrun. No `tools/call` has
been sent. Diagnostics change no wire acceptance or request sequence; the latest
36-case discovery suite passes independently. Exact source for the last capture
is saved under `local/se-lab-mcp-handshake-source-20261021` with a receipt;
module SHA256 `4ddc9c32d549db9aec1114dff582dd2ba616b1e4f4c321c83fbdf98a66752a39`.
Fresh capture `b66c1648a99048fdb6cd3181154e89bb` identifies the duplicate as
`content-type`, with equal trimmed values, two occurrences and two fields
examined. It still rejects the response and sends no POST. This connects the
observed failure to the clean DLL's MCP SSE handler, which inserts the same
`text/event-stream` value twice into the same response headers. The separate
AgentsPage streaming handler is not the evidence for this finding. Diagnostic
source `5ddc0fe6eaad32521d30480896d89254c230a16d51abd27583117182dcadf74b`
is retained under `local/se-lab-mcp-duplicate-source-20261021`. A narrowly pinned
SSE-only compatibility change is being tested; no header acceptance has yet
changed in an actual observation. Root's combined discovery/plugin fake suite
passed 54/54 in 15.459 seconds using unittest discovery; direct module-style
invocation failed the new test's sibling-fixture import and is not a passing run.
At that diagnostic checkpoint, the separate `get_plugins` collector was still
under adversarial prerequisite review and had made no actual tool call.

The subsequently reviewed compatibility source
`217872aaa2a5004a1387adf2825e937ceeb302aacae4c4ad383ba252f251dab0`
passes a fresh live discovery: capture `d006c9c5f98e43e39e45b086c1fb9c2c`
returned 56 tools using four requests and three SSE events, with matched final
context and the pinned two-Content-Type exception actually used. Report SHA256:
`b3b5de55bd6e5b451c9825cfb0872b124765def74204900810d19369b925efa5`.
All previous failures above remain separate failed captures.

One explicitly reviewed `get_plugins` call then passed in capture
`1881b35770274cc2abc89cb1c7ba9f1b`: ten loaded filenames, all five expected
profile plugins present, five total requests, four SSE events, and stable
identity/context. No other game-inspection tool was called. Its exact source
is retained in `local/se-lab-mcp-plugins-source-20261021`; the four files and
both linked prerequisite captures passed independent review. Root's final
combined suite passed 68/68 in 19.426 seconds with zero skips. Log SHA256:
`615c6b1b98f0910269f9e138e93799eee28b8d1ea4462288df9430acc4603ebb`.
This is a main-menu loaded-plugin observation, not world or playback acceptance.
MO2 changed its profile header again during exit; that later state correctly
fails the live profile gate and is retained rather than retroactively adopted.

Earlier diagnostic revisions have recorded hashes/test results, but were not
independently snapshotted before later edits. Their reports remain immutable.

Static inspection explains the routing mismatch: the native reload adds missing
built-in provider IDs, and text-model loading recreates the `decisions` variant
when omitted. A custom-only catalog and `variants:{}` therefore do not remove
native routes. A separate explicit seed candidate is being prepared; no live
configuration has been changed. The Anniversary download prompt remains visible
after Escape/console-key attempts; no further UI input or download was accepted.
The earlier baseline entered QASmoke using its explicit `sStartingCell`, which
this first-boot profile deliberately does not set.

Local metadata capture `32ba9d3dcfe74fbdab49d8f0a52da14d` reports original
assets unchanged and runtime storage within its explicit contract. Literal
protected-path equality is false because the permitted session cache appeared.
The next task is a separate disposable QASmoke world-readiness checkpoint,
keeping generation, production Hold Music playback and harness autorun disabled.
The native provider-default audit remains incomplete.

Closed-run shared logs are archived under
`checkpoints/skyrimnet-observer-v2-shared-logs-after-20261021`. SkyrimNet.log is
214,169 bytes/1,620 lines, SHA256
`713e2a099f6e499ceed01a71913fbd798b3f933b5ae717e0181aac0c5d934934`.
The fixed-pattern summary records zero error/critical/config-registration
failures, four warning lines, one model-download-start marker, two download
success/verification markers and no telemetry/provider-request markers. Absent
markers are not proof of absent traffic. The [native model audit](se-lab-native-model-initialization.md)
explains unconditional embedding/VAD verification and exact-hash local reuse;
it does not establish a general no-egress control. The archived Papyrus log's
old timestamp means it must not be treated as fresh fifth-run world evidence.

All eleven raw launch-bound source files, including the original line endings,
are separately preserved under `local/se-lab-fifth-launch-source-20261021`.
Its receipt SHA256 is
`bc251c8859e4d15f1367e327a908b29048eefb395cf01ab43953a72f1a33683b`.
Both new retention helpers passed 36/36 independent temporary-fixture tests.
Actual whole-tier retention now reports `retained_verified`, preserving all
5,840 instance files, two installation files and twelve runtime evidence files
under `checkpoints/skyrimnet-disabled-controls-observed-20261021`. Its separate
opaque three-file cache operation reports `cache_retained_verified`, with
Game/default absent and all preexisting protected files unchanged. Original-run
literal protected equality remains false; it is not reset by moving the cache.
Whole-tier result SHA256:
`11d5574fb9de4c977bb4d9631a4de1aca6da7d8cbea54beb3bdb9b22f4fd65a4`.
The next source work may now begin. A three-file public model seed was staged
from exact catalog-matching retained overwrite files, without old verification
sidecars, network requests or installation; see the model audit for its hash.

### Source and prior retention checkpoint (05:42 CDT)

- Checkpoint `4969963` is synchronized on Halcyon, GitHub and clean Echo.
  Identical-tree local commit `5dff260` is preserved on
  `checkpoint/se-lab-observer-v2-20261021-0543`. Echo's full 209-case suite
  completed in 44.654 seconds: 202 passed, six expected Windows-only skips,
  and one fixture error. The fixture's synthetic `PATH` hid the host `tar`
  executable. Full log: `local/se-lab-echo-observer-v2-4969963-20261021.log`,
  SHA256 `5c5284235e70ca37d9f24e4bcad5d31aabfdccfd3b81ab6defea04b08a67f2a0`.
  A test-only correction restores the host lookup path solely around the two
  archive-reader calls. The affected case then passed 1/1 with no skips on
  Windows (0.100 seconds) and Echo (0.017 seconds). Echo executed the patched
  test in memory; its `4969963` checkout remained clean before and after.
  Patched test SHA256:
  `e733760bbad5d7f1ce5d739dccec9044e1acb8cfbbb2b1f3575ee9357743465a`.
  Targeted Echo log: `local/se-lab-echo-tar-fixture-4969963-20261021.log`,
  SHA256 `5f282f22ed10aff7c8d06a3648b1882602ca7935e3fb2da803b4731824f0b2ed`.
  The full suite was not repeated after that correction. Frozen implementation
  hashes below are unchanged; these tests made no service changes or game/MO2
  launches. The fresh installation and runtime observations are recorded above.

- Fourth-run cleanup is complete: exact owned game handle terminated with exit
  18509, MO2 exited naturally with code 0, and an independent snapshot confirms
  all relevant lab processes closed. No late identity upgraded launch authority.
  Whole-tier retention completed `retained_verified` at 05:37 CDT: 5,806
  instance files, two install files and four runtime files, plus the original
  source archive, are intact under
  `checkpoints/skyrimnet-observer-failed-attempt-20261021`. Protected state stayed
  unchanged relative to the retention review; original-run equality remains
  explicitly false. The separate three-file opaque cache archive also completed
  `cache_retained_verified`, preserving all preexisting protected files and
  leaving Game/default absent. The cache bytes remain inside the fourth-run
  checkpoint; their contents were not parsed or exported. Both helpers passed
  24/24 independent fixture tests. Result hashes:
  `bf440cd0e0cca08d50fdea9cb7abe22ebe13fd7de913add75fcf10c0b2d9b55c`
  and `1705397a037b8d8f56723a13f27270ec58a4ba36f0626cda03ea7beea8fe9614`.
- The archived SkyrimNet log explains a separate startup failure:
  `GameConfig.h:2555` rejects missing
  `dialogue.distanceToDetectBackgroundDialogue`, then MainWorker fails game
  configuration registration. The log contains 65,197 `Configuration game not
  found` messages. Read-only disassembly of the pinned clean DLL confirms the
  loader begins with an unconditional floating-point conversion of that field;
  the shipped dashboard supplies default 1000. The frozen correction supplies
  that value. Independent inspection found no further required-field blocker
  in the examined OpenRouter/model-slot, Providers, STT, Bard, VastAI and Memory
  parsers; this bounded static review does not prove complete native acceptance.
- The same native log records embedding-model downloads and a telemetry response.
  Earlier statements below about no HTTP requests mean requests made by our
  observation tooling only. They do **not** establish native zero egress. The
  next seed explicitly disables telemetry, metrics, both GameMaster switches
  and local Kokoro narration as well as AI. Acceptance requires fresh runtime
  readback. No paid model/audio generation was requested.
- The observer/storage/config candidate is frozen at tier hash
  `6d4bb6dc13e1e920fc1dd07fd54c22eb1f905119dd27c4d0afd2b8be95d77f73`,
  smoke hash `47bd7b72d6615a4092e19eee72f300fddd157bebc839158c41751e910d9cb073`,
  and storage helper hash
  `9a33e0bb6e87884ec7c4333499e6d75790d66b0beb93b0d2809875fd24613d71`.
  The final tier suite passed 100 plus one expected Windows symlink skip in
  597.403 seconds; observation/storage passed 107 plus one expected skip in
  12.327 seconds. All 209 cases completed (207 passed, two expected skips),
  including actual Qt, bundled EA and native Python-child checks. Tier log
  SHA256 `19c8d79c83842503b992f28664c45622d79bab4ac2b9933b7e869294825fc5c7`;
  observation/storage log
  `5f590b12542e889fc08fd05290d91885b0978082af0e0e70d69093c5dc8d71f5`.
  Earlier partial suite logs are retained
  as superseded by the additional source-confirmed disable controls.
- Positive-attribution cleanup v2 passed 22/22 independent fixture tests. It
  keeps the original process handles, permits only the launch-bound storage
  contract, and records natural MO2 exit separately. It has not been applied.

### Previous fourth-run checkpoint (05:13 CDT)

- Checkpoint `0737580` is synchronized on Halcyon, GitHub and clean Echo;
  identical-tree local `9695daa` remains on
  `checkpoint/se-lab-profile-ready-20261021-0501`. Echo's Python3.13.5 passed
  90 portable tests plus one explicit Windows-native skip, including the 80
  observation regressions; no service was restarted.
- Fourth run `20261021T100330Z-49533a3d026a` started Skyrim. The fresh shared
  SKSE log reports all seven expected native plugins loaded, including
  SkyrimNet. However, the launcher reported `launch_observation_incomplete`
  after 48 samples, retaining the exact MO2 and SKSE parent identities but not
  the game. A later read-only game identity links to that retained loader.
  This supports exact owned-process cleanup only; it does not upgrade the
  failed launch or authorize the guarded endpoint checks.
- Capture `a5c1895b609d46cca7461d9e2b6d3ff1` reports
  `protected_state_changed`, 239 instance changes and no attributed game.
  The only new protected Game files are `default/cookie.jar.db` and its
  `-shm`/`-wal` sidecars. All existing Game file rows, the baseline MO2 and
  manifest remain unchanged. These private database contents have not been
  read or exported. The ten frozen sources and original launch evidence are
  preserved under `checkpoints/skyrimnet-observer-failure-20261021/`.
- Native observation currently reopens each PID every frame and permanently
  fails on one missing identity. A mocked API reproduction proves that a
  previously verified loader exiting between enumeration and reopen causes
  this failure. The live report lacks the diagnostic category needed to prove
  the exact branch. The correction will retain query/synchronize handles for
  verified identities and add sanitized failure categories; unknown identities
  and reused PIDs still fail closed.
- Pinned PrismaUI1.5.1 source uses Ultralight's persistent default session and
  supplies no cache-root setting. The public API/archive exposes no cache
  configuration. This explains the observed storage location at source level,
  without claiming a process-write trace. The next runtime contract will account
  for precisely those three files while preserving strict original asset checks
  and reporting the cache change separately. Cleanup and design review are in
  progress. Our tooling made no HTTP/MCP/provider request.
- Windows UI tooling lists the game window but fails to attach to its returned
  identity twice (`window ... was not found`). No UI input was sent, and UI
  automation stopped after the documented retry. This is separate from native
  process liveness and is not evidence of a CTD.

### Tested profile-ready installation (05:00 CDT)

- The final tier suite passed 86 cases: 85 passed and one expected Windows
  symlink-permission skip, in 481.318 seconds. Both actual Qt checks and the
  pinned bundled-EA regression ran. Log SHA256:
  `6921d8e040ba3008a13e4394b62b075834d13c2017b75c96b9b2bfe165b5c3b2`.
  The frozen implementation remains `f085e72a...93ac40b`.
- Installation `05164efc80de4f3a839c0a299acb41b2` completed
  `installed_disabled`; `protected_changed_since_install=false`.
  Post-install preflight returned `prepared_files_verified`, 3,939 selected
  payload files and no blockers. The exact vendor/default/empty custom INI
  hashes were independently checked in the installed profile. Receipt SHA256:
  `f836d3535fbe9c2e0308544c6b8bd7e84b7f4957c727db1e00ea3cf0757e42a3`.
- Prelaunch shared log evidence is retained under
  `checkpoints/skyrimnet-profile-ready-shared-logs-before-20261021/`; the
  earlier logs are unchanged and SkyrimNet.log is still absent. The launch
  review is in progress. No live HTTP/MCP/provider request has occurred.

### Reviewed startup correction (04:54 CDT)

- The final environment/profile correction is frozen at module SHA256
  `f085e72a2f71d980a2a88ce5e4148f8c4d7c12620bd7e67faed2a4b3193ac40b`.
  Independent final profile/edition/Qt/EA checks passed 5/5 with no skips;
  generated `Skyrim.ini` bytes equal the clean vendor file, `SkyrimCustom.ini`
  is empty, and blocked-read tests prove seed generation imports no profile.
  No autorun or baseline-only Launcher field is added.
- The three observation suites pass against that source: 80 tests in 4.978s,
  log SHA256
  `da60bbc94ad9589ebf44fa3002ed02e69da3f722acf9b6f311a34af4fe47ed46`.
  The final 86-case tier suite is running; its completion is required before
  launch. The new installation plan has no blockers and covers 5,573 files;
  explicit installation is in progress. No live endpoint call has occurred.

### Retained third attempt (04:51 CDT)

- Third-attempt retention completed `retained_verified`, with protected paths
  unchanged: 5,595 instance files, two install files and four runtime files now
  remain under `checkpoints/skyrimnet-programw6432-failed-attempt-20261021/`.
  The original `cb79d30` source archive is SHA256
  `7db79d2950416ec64b4a726a0b5571d7e75a21cf763a62824d08c5328e919559`;
  all ten raw source snapshots match the run, with archive differences limited
  to CRLF/LF normalization. The retention helper passed 12 fixture tests twice,
  including exact confirmed-cleanup identity requirements.
- The three-variable environment repair passed five focused tests independently,
  including the bundled EA-source reproduction. A broader source audit found
  that MO2's direct CLI setup also checks for `SkyrimCustom.ini` when local INIs
  are enabled. An absent file triggers configuration copying and a warning;
  an empty file satisfies the check. The new seed will provide an empty file
  and reject missing/changed initial bytes before launching.
- The corrected profile will use the exact clean shipped `Skyrim_Default.ini`
  content (1,859 bytes, SHA256
  `61c151bc60d5d737dad3d65a99a48d9bb8b50812b6b9f1f993323f0337813fa8`)
  as its `Skyrim.ini`. This preserves the vendor DLC/archive entries also used
  by the successful baseline. It adds no baseline-only autorun/debug settings
  or shared-profile imports. The prior minimal seed's engine fallback behavior
  is unverified. Minimal windowed preferences remain unchanged.
- Full tests for the environment-only intermediate change were intentionally
  stopped when the profile findings arrived; their partial log is retained,
  not reported as a test failure or completed suite. The final combined change
  will receive fresh focused and full checks before installation.

### Third startup diagnosis (04:43 CDT)

- Third launch `20261021T093337Z-4ff5fdf6348c` gets past the original native
  crash and initializes MO2 logging/plugins. It stops on the bundled
  `basic_games` plugin's `KeyError: 'ProgramW6432'`, before a game process
  starts. Read-only accessibility inspection identified the exact error; no
  dialog input was sent. The recorded MO2 PID 35276 was closed through the
  reviewed same-handle identity/termination helper, with exit confirmed.
- Capture `e471f994f689462883f1ad234c73df85` is
  `incomplete_process_evidence`, with protected paths unchanged, 24 changed
  files and zero private runtime files. The ten exact implementation files,
  run/launch evidence and dialog projection are retained under
  `checkpoints/skyrimnet-startup-dialog-20261021/`. Before/after shared log
  hashes and timestamps are identical; no SkyrimNet log exists.
- Two independent audits cover all 270 bundled Python files and official
  MO2/uibase v2.5.2 core sources. The only additional missing startup variable
  found is `ProgramW6432`, directly indexed by unconditional EA discovery
  during the bundled plugin import. A fully mocked source reproduction
  confirms that failure without reading actual launcher settings.
  `USERNAME` and `PATH` are the other direct requirements; `COMSPEC` has a
  native fallback. The next correction adds only `ProgramW6432` and validates
  these three values before launch. Credentials, proxy settings and Python
  overrides stay excluded. This bounded audit does not cover every native DLL.
- No HTTP, MCP, provider or paid generation request has occurred. Full retention
  of this third instance and the corrected-environment tests are in progress.

### Corrected startup installation (04:29 CDT)

- Startup fix checkpoint `c738aa2` is synchronized on Halcyon, GitHub and clean
  Echo; identical-tree local `cb79d30` is retained on
  `checkpoint/se-lab-startup-20261021-0426`. Four focused environment/edition
  tests also pass on Echo's Python3.13.
- New installation `f5e6692b7c224e9eb94fe159329d35b9` completed
  `installed_disabled`, with protected paths unchanged. Post-install preflight
  returned `prepared_files_verified`: 3,939 selected files, no blockers, expected
  ports available. The installed canonical INI explicitly selects Steam and
  retains Qt-safe paths. Shared logs are archived under
  `checkpoints/skyrimnet-startup-shared-logs-before-20261021/`; their contents
  still match the previous baseline and SkyrimNet.log remains absent.
- First boot under the corrected environment is next. Its review binds the
  three accepted baseline captures. No live HTTP/MCP/provider call has occurred.

### Accepted correction checkpoint (04:24 CDT)

- Second retention completed `retained_verified`: all three directories, 5,573
  instance files, raw journals and original `327cc4f` source archive are intact
  under `checkpoints/skyrimnet-username-failed-attempt-20261021/`; protected
  baseline/Game state is unchanged. The first qsettings checkpoint is untouched.
- The final USERNAME/Steam-edition source is frozen at SHA256
  `1960a510ea0a92b5a7ceeb1ed24c6b7ae9130a138c24a0582f2df6d69e2f80cd`.
  Independent focused checks pass 7/7, including actual Qt6.7.1; the 80 smoke,
  routing and MCP regressions pass against it. The synchronized prior checkpoint
  also passes those 80 observation tests on Echo's Python3.13. The full tier suite
  passed 84 cases: 83 passed and one expected Windows symlink-permission skip,
  with both actual Qt6.7.1 cases run. Log SHA256:
  `bd2d260b99eaaa35e6b5d3ccb619dc90a7724ed8ed9952f739eade1388b1bb9c`.
  The new install plan has no blockers and its reviewed apply is in progress.
  Native launch and all HTTP/MCP observation remain pending.

### Diagnosed startup checkpoint (04:12 CDT)

- Inspection checkpoint `69ba125` is synchronized on Halcyon, GitHub and clean
  Echo. Its identical-tree local commit `327cc4f` is retained on
  `checkpoint/se-lab-inspection-20261021-0413`. The final 80 observation tests
  passed again after whitespace cleanup; no live observations have run.
- Matching official MO2 2.5.2 symbols localize both early crashes to
  `initLogging`, `src/loglist.cpp:371`, the unchecked
  `std::string("\\") + getenv("USERNAME")` expression. Executable, PDB and
  dump GUID/age match; the dump records a null read with both instruction address
  operands zero. The retained launch environment omitted `USERNAME`, while the
  working baseline inherits it. This identifies the early startup failure;
  progress beyond it still needs a corrected launch.
- All 1,626 regular application archive files match the working baseline.
  No dependency replacement is justified. A narrow source correction now
  preserves exactly one nonempty inherited `USERNAME` without exporting its
  value, and rejects missing/ambiguous values before dispatch. Its tests/review
  are in progress; the installed failed attempt is untouched.
- Independent source review also confirms the fresh INI needs
  `game_edition=Steam`: instance setup otherwise presents a variant-selection
  dialog before CLI dispatch. Only that field is added; the direct CLI path
  bypasses the main-window tutorial/version handling, so those flags and custom
  executables remain absent. Final test coverage includes actual Qt parsing.
- The second retention helper is prepared, not applied, under
  `local/se-lab-skyrimnet-env-retention-20261021/`. Its 11 fixture tests pass
  independently. It changes only five fixed literals from the first reviewed
  helper and targets `skyrimnet-username-failed-attempt-20261021`. The original
  `327cc4f` archive is retained as Git content; all ten exact raw source files
  already match the failed run's hashes in the separate source snapshot. Git
  archive line endings differ only by CRLF-to-LF normalization.
- Symbol evidence is `local/mo2-symbols-20261021/symbol-projection.json`, SHA256
  `b91087073945676786538ed182500b8b85e800973e9e360af2a74a4e4f304311`.
  The official source is [MO2 loglist.cpp at v2.5.2](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/loglist.cpp#L371).

### Second failed startup checkpoint (04:08 CDT)

- Corrected run `20261021T090334Z-6b4447114828` also failed before Skyrim
  started. Its separate MO2 PID 14048 crashed at the same `0xEF486` offset and
  identical seven-frame module stack. The Qt path defect was real, but fixing it
  did not resolve this native startup failure. No live lab processes remain.
- Capture `a49b5783fe8c49438910a5636c553c42` reports
  `incomplete_process_evidence`, protected paths unchanged, one changed file
  (the MO2 crash dump), and zero private runtime files. Shared SE log bytes and
  timestamps are identical before/after; no SkyrimNet log appeared. No HTTP,
  MCP, provider or paid generation call has occurred.
- The second crash, events, exact INI, module stack and ten frozen implementation
  files are archived in
  `checkpoints/skyrimnet-corrected-boot-failure-20261021/`. Both failed
  attempts remain distinct. The next investigation compares startup configuration
  and application payload with the working baseline and maps the crash using
  matching official MO2 symbols. Do not mutate this retained attempt to retry.

### Corrected installation checkpoint (04:02 CDT)

- The Qt-safe seed/preflight correction is frozen: 81 tests ran, 80 passed and
  one expected Windows permissions case skipped. Both actual bundled Qt 6.7.1
  regressions passed. Independent review passed 13 focused methods and blocked
  all 17 adversarial INI representations; the smoke/MCP regression passed all
  49 cases against the final corrected source. First boot requires the exact
  generated UTF-8 bytes for both INIs; ordinary semantic parsing is insufficient.
- The failed instance and both control directories were retained intact under
  `checkpoints/skyrimnet-qsettings-failed-attempt-20261021/`. The reviewed move
  completed `retained_verified`, including 5,573 instance files, original source
  archive `c31046d`, per-step inventories and unchanged protected paths. No files
  were deleted or overwritten. Fresh corrected transaction
  `da5291644a274e938d460eafb72bbcd1` completed `installed_disabled` with unchanged
  protected paths. Its preflight returned `prepared_files_verified` and its
  launch plan accepted all three baseline captures. The explicit launch is now
  in progress, using a 60-second native process observation window.
- The original failed run remains historical evidence below. The path defect is
  confirmed; whether the corrected seed resolves the native startup failure is
  still awaiting a new attributed launch.
- Current corrected receipts (SHA256): install
  `57ac09bc7f63bea0badba52f20af7ce7965c0352cb7a03cf6dbf1bdd4b60be41`,
  preflight `65c1149e50eafde98105be72906979d1ae86c86b4d5347fbc7d152b68e6c9abb`,
  launch plan `01160514d2ba4d1fc586736479cfdd39f184a9e87268ba89d5469a4aea582969`.
  Shared logs were archived again under
  `checkpoints/skyrimnet-corrected-shared-logs-before-20261021/`; they still
  matched the earlier baseline hashes, and no shared SkyrimNet log existed.
- Final independently reviewed observation tooling passes 80/80 synthetic
  tests: smoke 24, routing 27 and MCP discovery 29. Smoke now handles the actual
  PrismaUI archive's lowercase `SKSE/plugins` component while retaining exact
  full physical-path/hash matching; final exchange/batch deadline checks refuse
  overruns. Routing requires explicitly observed legacy credentials and reports
  skipped provider/variant/slot coverage as incomplete. No live requests yet.

### Prior first-boot checkpoint (03:27 CDT)

- `c31046d` is synchronized on Halcyon, GitHub and clean Echo. The prior
  `450e6b5` checkpoint remains in history; local equivalent commits are retained
  on checkpoint branches. The new installer/launcher suite completed with
  69 passes and one expected Windows skip. Smoke checks pass 20 synthetic tests;
  the separately reviewed MCP discovery client passes 29, with no live calls yet.
- Separate `MO2-SkyrimNet` installation transaction
  `1e71f9713bf44146a5dba215388366be` completed `installed_disabled`, and its
  post-install preflight passed. The installer published 5,572 files, including
  the fresh MO2 application support. The stricter runtime recipe checks 3,939
  selected payload files. Baseline MO2/shared Game are preserved.
- First-boot run `20261021T082018Z-7ec91cdb271c` failed before a game process
  was observed. WER identifies the separate MO2 process (39800) crashing with
  `0xc0000005` at `ModOrganizer.exe+0xEF486`. Native process snapshots are now
  empty. The retained result is `launch_observation_incomplete`, not acceptance.
  Local capture `22338b26947a47ed8c0593f633d3c325` reports protected paths
  unchanged, one changed tier file (the crash dump) and no private runtime files.
- The actual bundled Qt 6.7.1 parser confirms a seed/preflight defect: single
  backslashes in generated paths are parsed as INI escapes. For example,
  `gamePath` becomes `C:GOoldMusic-SE-Labame`, despite `QSettings.NoError`.
  The working baseline uses Qt-safe paths. A narrow writer/validation fix and
  native decoder regression are in progress. This is a definite configuration
  bug; the precise native crash mechanism remains unconfirmed.
- Preserve this failed instance, both control directories and their receipts.
  Root is preparing an explicit, reviewed retention into a new checkpoint before
  a fresh corrected installation. Do not reset or reuse the original attempt.
  Crash files, Windows events, stack projection and all ten exact original
  implementation sources are archived under
  `checkpoints/skyrimnet-first-boot-failure-20261021/`.
- The following previous checkpoint details remain historical evidence; later
  continuation entries supersede their pending-work and live-process statements.

### Prior baseline checkpoint (02:44 CDT)

- Three-scenario checkpoint `450e6b5` is synchronized on Halcyon, GitHub and
  clean Echo. The identical-tree local commit is retained on
  `checkpoint/se-lab-three-scenarios-20261021-0246`; the earlier native-fix
  checkpoint and its local branch are also retained.
- Installed: production `se-lab-production-admission-20261021-01`, harness `-20`.
  They passed 110 production / 146 lab tests. General suite: 918 passes and 11
  expected skips. Tests use fake providers; no paid generation occurred.
- Controlled completion run `20261021T065140Z-c9a5261dfebc` **passed** with a
  fresh full-identity receipt and alias/faction/globals/hour cleanup. Its exact
  owned processes were stopped after capture. Requested interruption run
  `20261021T065757Z-4b60d0a80eab` failed because its clip completed before the
  stop request; its cleanup succeeded and exact owned processes were stopped.
  The new matched pair passed interruption `20261021T073100Z-7f43558f4725`,
  completion `20261021T073656Z-724c1caa62e4` and ambient entry
  `20261021T073954Z-86c74b138816`. All captures/shared logs are archived and
  their exact owned processes stopped. No lab game or MO2 remains active.
- The Sven-only `BardSingerNoAutostart` fixture blocks the verified fresh starter
  path, not already queued work. Native absence rank -2 is now handled without
  changing preexisting membership. Natural tavern AI remains unverified.
- Production admission suspension/drain/resume passed independent review:
  89 compiled cases, three reset/init reproductions and 150 boundary checks.
  The authoritative build passed 110 production tests with zero skips and
  28 identity capability cases. Harness20 passed independent review and is now
  installed with it. Source owners are frozen; root owns staging/game runs.
  Inspect agent state before continuing or changing their files.
- The three controlled native baseline scenarios pass. The separate disabled
  SkyrimNet installer remains unexecuted; its process observer is being revised
  to capture the short-lived loader with native identity timestamps. Wait for
  its source/tests to freeze before the first install.
- Harness19 is a retained, **rejected** candidate: it passed its 145-case suite
  and 34 independent setup/cleanup cases, but additional ambient movement probes
  found stale movement/playback after cancellation. Harness20 fixed that defect
  and passed the same additional probes; do not install19.
- The disabled SkyrimNet launcher/metadata collector passed its focused tests
  before the process-observer revision. It requires explicit accepted completion, interruption and
  ambient captures. It makes no HTTP/MCP/provider calls and does not claim native
  loading or effective configuration acceptance. Root's broader Python suite
  completed: 929 cases, 918 passes and 11 expected skips; log
  `local/se-lab-general-admission-20261021.log`. The two later movement-field
  checks also passed their targeted acceptance regression.
- `durable_execution` owns a separate new, read-only SkyrimNet native/config
  smoke module/tool/tests/docs. It uses fake transports until root performs an
  explicitly reviewed actual read. No endpoint has been contacted.
- Both original Steam manifest read-only flags and recorded hashes were checked
  again after publication and remain unchanged. Production VR/MGO is untouched.

## Starting state

- Source baseline: `2f23089`, clean Windows checkout and previously synchronized
  GitHub/Echo. Inspect current status before every change; preserve other work.
- Lab: `C:\MGO\HoldMusic-SE-Lab`, Skyrim SE 1.6.1170, SKSE 2.2.6, portable MO2.
- Installed harness: `local/se-lab-harness-20261020-07/build/package`.
- PEX SHA256: `4ae50157e6f18ea4ca21501b4a1290393ec789e22e53ca8c07833fbfeb26a71b`.
- Its 56 offline tests passed. Preflight passed all 442 checks at overnight start.
- Both original Steam manifest locks remain read-only with their recorded hashes.
- Shared SE logs were backed up to `checkpoints/overnight-20261021-start/`.
- The prior daytime run reached the inn but failed Sven eligibility before
  playback. No baseline playback pass or VR compatibility claim exists yet.

## Active work

Root owns engine launches, process cleanup and installed lab changes. The
`holdmusic_progress_review` agent reviews evidence/source; `durable_execution`
researches the next SkyrimNet tier without installs or paid calls.

First rerun `focused-complete` with the guarded runner and fresh request. Inspect
boolean serialization and detailed Sven diagnostics on failure. Prove requested
interruption and actual scripted ambient entry in separate fresh processes.
Preserve every failed run and all trace/receipt history. Use synthetic audio;
do not infer audibility or animation appearance from native call return values.

Only advance SkyrimNet inside a separate isolated lab tier after baseline
evidence is sound. Verify actual supported settings and use no external paid
provider access or copied production credentials. Do not alter VR/MGO, original
Steam installations, their locks, musical recipes, auditions or playthrough saves.

## Continuation notes

### 23:30 CDT: first revised engine run

Run `20261021T042942Z-71888dbfa3cd` used harness `-07`. The collector retained
fresh required evidence and the result failed correctly. The harness boolean
fix is confirmed in-engine: real booleans and zero serialization errors.
Sven was loaded, in the same cell, found by the scan, owned by Hold Music and
eligible. Production accepted the idle and sound call, recorded start/stop and
one completed receipt, restored globals, and remained running without a crash.

The receipt lacks its required `runtime_identity`, so this is not an acceptance
pass. Papyrus logs identify `None` to `String[]` casting, mismatched temporary
types and failed identity-array allocation in `HM_Library.ChooseSlot`.
`holdmusic_progress_review` is fixing the array reset with regression tests and
fresh builds; `holdmusic_sync_review` independently reviews that change.
The exact two owned processes were stopped after validating PID/path/start time;
logs and evidence are retained under that run directory. No game is left running
at this checkpoint. Root must inspect agent status and new build receipts before
staging or rerunning.

Use bundled Python 3.12 with `PYTHONUTF8=1`; the default Python 3.10 is unsuitable.
Echo SSH alias is `echo`; its Homebrew Git is `/opt/homebrew/bin/git` because the
Apple Git currently stops at an Xcode license prompt. Inspect and fast-forward
only clean checkouts. Windows Git CLI push can hang on credential-manager login;
the connected GitHub tools can publish an exact verified tree with a head lease.

Do not repeat completed work from earlier offline checkpoints. Record run IDs,
outcomes, source/build revisions, tests, remaining uncertainty and the next
bounded task below before yielding the thread.

### 23:35–23:38 CDT: identity fix confirmed; playback guards under investigation

Staged fresh production `local/se-lab-production-arrayfix-20261021-01/build`
and compatible harness `local/se-lab-harness-20261021-08/build`. Production passed
80 tests including 28 identity cases; harness passed 56 tests; all zero skips.
Independent review verified the compiled instructions and source/artifact-bound
receipts. The old build fails the new regression at the logged cast. Lab backup
and replacement receipt: `checkpoints/arrayfix-20261021-01/`; preflight 442/442.

- `20261021T043545Z-296b66f70a50`: strict slot selected; native idle returned
  false, production logged `idle_failed`, and the harness failed. Collector
  reported incomplete evidence because no new receipt was produced.
- `20261021T043703Z-0dbef97ebacd`: playback started and stopped as interrupted
  after about 3.6 seconds. The new receipt contains the expected identity key
  and all ten identity fields. Completion scenario still failed, correctly.
  Collector retained fresh required evidence. No HM array/cast errors recurred.

Both exact owned process pairs were stopped after PID/path/creation-time checks.
Each run retains collected evidence plus shared Papyrus/SKSE/PapyrusUtil logs.
No prior receipts/traces were reset. Identity correction is now observed in the
engine; overall completion acceptance is not established.

`holdmusic_progress_review` is adding event-only idle-refusal/interruption
diagnostics without retries, delays, eligibility overrides or outcome changes.
Root must stage its fresh tested builds and inspect guard reasons next.
`durable_execution` prepares a separate disabled/no-auth SkyrimNet tier; a second
profile alone is insufficient because MO2 overwrite is shared, so that tier
needs its own portable MO2 instance and writable roots. It remains unlaunched.

### 23:43 CDT: diagnostic candidate and fixture stability

Staged `local/se-lab-production-diagnostics-20261021-01/build` and compatible
`local/se-lab-harness-20261021-09/build` after 86 production and 56 harness tests
passed with zero skips; independent compiled review passed 37 controller/trace
tests. Backup: `checkpoints/diagnostics-20261021-01/`; preflight 442/442.
Controller PEX: `7d2c4cc3ca299063fc13964bd28d6a5dfd5200f62cb3cc21d63cd8cd971669b1`.
Harness PEX: `0a6d37863cd696607212f7f81e6ec7b62f8071dcc4486ea84f2ea42e385a7c86`.

Focused run `20261021T044327Z-a20912cd9e00` failed readiness before selection.
Its snapshot found loaded/eligible Sven in the same cell, but distance was
FLT_MAX and the following eligibility check failed. This is changing actor
state, not proof of a particular cause. The verified stage/player markers are
about 303 units apart; previous observed distances of 464/518 do not describe
Sven remaining at that marker. His normal package schedule is being inspected
before choosing a stable fixture time; no production eligibility override or
retry was added. This failed run and shared logs are retained; its processes
were stopped using exact identity checks.

Ambient run `20261021T044451Z-07e245403f30` observed real inn entry and the
normal production scan, then an ineligible Sven and no performer. It failed at
its bounded deadline (128.86 engine real seconds); collection correctly reported
incomplete evidence with no new receipt. Shared logs and failed result are
archived. The owned MO2 52100 and SkyrimSE 11180 were stopped after checking their
exact paths and creation times. No lab game remains running at this checkpoint.

Read-only inspection of Skyrim.esm found Sven's normal inn package runs from
10:00 for 16 hours, with sleep 02:00–09:00 and breakfast 09:00–10:00. An all-day
higher-priority Riverwood introduction patrol remains eligible while both its
intro stage 10 and MQ102 stage 50 are incomplete. A new QASmoke world can retain
that patrol regardless of the hour. This explains a fixture conflict worth
testing; it does not retroactively identify every failed guard. The extraction
agent is checking the intro stage fragment before proposing a minimal disposable
world setup. MQ102 and actual playthrough saves remain untouched.

Separate SkyrimNet preparation/preflight source is complete in
`hold_music/se_lab_skyrimnet.py`, `tools/se_lab_skyrimnet.py` and its tests/docs.
It has no apply, launch or HTTP/MCP operation. The first actual read-only recipe
validated the cached archives and baseline without blockers. The final report
`local/se-lab-skyrimnet-plan-final-20261021.json` describes 3,939 files and 17 seeds
with no blockers. It is a snapshot of the diagnostic baseline, not installation
or native-load evidence; regenerate after any baseline artifact change. Root
independently ran all `test_se_lab*.py`: 53 total cases, 51 passed and two expected
Windows symlink skips. No second instance is installed.

An additional real-receipt boundary issue is being fixed by
`holdmusic_sync_review`: Papyrus emitted performer `Sven`, while authored source
uses `sven`; the planner ignored recent playback because the derived history
kept that casing. The adapter must preserve raw receipts and their identity key,
map only unambiguous source IDs, retain exact save/world boundaries, and block
ambiguous same-scope history. Never rehash Papyrus-cased readable identity fields
as if they were canonical source metadata.

### 00:02 CDT: native Story Manager restriction captured

The receipt adapter fix is complete: derived performance history resolves only
unambiguous ASCII case aliases in the exact save/world scope; raw receipts and
their captured identity keys remain unchanged. Ambiguous aliases fail closed.
Root ran 87 focused receipt/library/planner tests with zero skips, including the
actual engine receipt. The complete Python suite passed 890 cases (879 passes,
11 expected skips) in 232 seconds; log `local/se-lab-general-final-20261021.log`.

Fresh production `local/se-lab-production-fixture-20261021-01/build` passed
86 tests against the final adapter source. Harness `-10` passed 68 tests, with
50 compiled harness cases also independently reviewed. Staging backup:
`checkpoints/fixture-20261021-01/`; preflight 442/442. Only the isolated lab
control file now explicitly permits disposable-world setup.

Run `20261021T050155Z-933a384bdad1` failed that setup before inn movement or
playback. Native Papyrus refused `SetStage(20)` because the introduction quest
is event scoped and had not started through Story Manager. Stage remained zero;
the clock was not changed. The collector correctly reported incomplete evidence
without a new trace/receipt. Failed result and shared logs were retained. Exact
owned SkyrimSE 18436 and MO2 41220 were stopped after path/start-time checks.

Actual records now identify the natural trigger: Change Location (CLOC) into
RiverwoodLocation, MQ102 stage below 50, intro stage 10 not done, and hour 08–20.
Exterior marker `00096595` belongs spatially to Riverwood04 despite its persistent
cell storage. The next bounded fixture will enter there, await actual quest
startup before its authored cleanup, then run the original scenario. It must
restore the prior hour on cancellation/failure, preserve request fencing, and
never mutate MQ102 or relax production eligibility. This remains a runtime
hypothesis. No complete/interrupt/ambient baseline acceptance claim exists yet.

### 00:11 CDT: real location-entry fixture staged

Harness `local/se-lab-harness-20261021-11/build` passed all 78 lab tests
(60 compiled harness, 15 builder, three ESP), zero skips; independent review
also passed all 60 compiled harness cases. The new restriction regression fails
against the prior `-10` artifact, matching the native failure. Production
`se-lab-production-fixture-20261021-01` is unchanged. PEX SHA256:
`09a7f004a31720881d4017ba7276c31573b316e9bc7161b6b288f28333f24c49`.

The source-inspected Story Manager event/anchor conditions and all active
overrides are captured in
`local/se-lab-sven-story-inspection-20261021/inspection-summary.json`.
The harness sets the authorized temporary hour before exterior entry, observes
loaded Riverwood arrival plus quest startup, or separately records natural
completion. It requests stage 20 only for an observed running quest. Cancellation
after latent movement/waits is fenced; the setup budget is 90 real seconds.

Staging backup: `checkpoints/story-entry-20261021-01/`; preflight 442/442.
Focused-complete run `20261021T051101Z-1960d1585a9f` verified actual Riverwood
arrival, observed the quest running, accepted its authored stage 20, read back
stage 10 complete and quest/scene stopped, and observed normal inn package
`0001CB1B`. This resolves the Story Manager setup blocker in the engine.

The scenario then failed for an explicit, different reason: Sven was loaded,
in the same cell, owned and about 211 units from the player, but seated
(`sit_state:3`). Production correctly rejected him. No selection, playback or
new receipt occurred. The original hour and other globals were restored. The
collector reported incomplete evidence, correctly. All failed evidence and
shared logs are retained. Root stopped exact SkyrimSE 24348 and MO2 47212 after
PID/path/creation-time checks; no lab process remains running at this checkpoint.

Next bounded work is a reviewed, explicitly recorded disposable standing-actor
fixture. Do not relax production eligibility, retry until a lucky pass, or call
injected AI control natural actor behavior. Compare a lab alias/package with
documented native movement controls, including idle compatibility and restoration,
before implementing. Source remains frozen at `-11` pending that review.

### 00:28 CDT: controlled standing fixture review

Actual records identify `DefaultBardStayAtCurrentLocation` (`0010FB3F`): an
authored Travel/NearSelf package with radius zero and no own idle. The lab
builder now declares one optional, initially empty reference alias on the lab
quest at priority 90. The proposed harness fills it only after moving verified
Sven to the stage, under a separate `allow_controlled_actor_ai` boolean opt-in.
It observes package/standing state, preserves production eligibility, and clears
only its own acquired actor on every terminal path. Release requires an empty
alias and a different observed package. No actor base package list is edited.

Controlled results explicitly leave normal actor AI behavior unverified. The
production controller itself does not acquire an AI package, so ordinary tavern
behavior remains a separate integration check even if controlled tests pass.
In-memory phase timings separate scan, matching, diagnostics and selection;
the original 40/120-second scenario budgets remain unchanged.

Root's compiled `-12` harness check passed 73 cases after correcting one stale
diagnostic-text assertion. Subsequent independent review reproduced a missing
post-inn-teleport cancellation fence: cleanup released the alias, but the resumed
stack could overwrite the cancelled result with `running`. This candidate was
not staged or launched. The owner is adding the regression/fence and will build
a fresh candidate. `-11` remains installed and no lab game is running.

The separate disabled SkyrimNet installer is now source-complete and reviewed.
It uses the complete pinned official MO2 2.5.2 archive, exclusively publishes an
absent `MO2-SkyrimNet` directory, and never writes baseline MO2 or shared Game.
Journal-only partial attempts, interruption after publication, foreign targets,
source changes and recovery interruptions have fake-tree regressions. Recovery
preserves partial evidence; it does not automatically resume or overwrite.
No launcher/provider/HTTP operation was added. The focused lab suite passed
73 cases (71 passes, two expected Windows symlink skips), with independent
review of the new installer and recovery cases. Read-only actual planning found
5,572 proposed files with no blockers; the real tier is still absent. Root's
full general integration rerun passed 910 cases (899 passes, 11 expected skips)
in 280 seconds; log `local/se-lab-general-final2-20261021.log`. Providers were
fakes. The installer module, CLI and tests are frozen; no real install occurred.

Actual SE `BardSongsScript` and records expose a production lifecycle difference:
vanilla fills its bard aliases, sets `Playing=1`, and starts a scene. Its standing
packages require that variable and a BardPlaySpot link. `StopAllSongs` stops
scenes and sets `Playing=0`, without clearing aliases or evaluating packages.
Hold Music's stop-vanilla-plus-idle path therefore does not retain those
conditional standing packages. This supports a separate performer-lifecycle
design task, not a retrospective cause assignment for earlier interruptions or
the separately diagnosed VR native-scan crash. The ignored source inspection is
under `local/se-lab-performer-lifecycle-20261021/`.

### 00:42 CDT: cancellation review and provenance refresh

Harness `-13` fixed the independent review's three cancellation races: resumed
teleport, resumed scan/selection, and cancellation during nested release. Its
99 lab tests passed with zero skips, including 80 compiled harness cases also
run independently. All 22 receipt input/artifact hashes matched. The preserved
`-12` artifact fails the new cancellation regressions. Neither was installed.

The staging guard then rejected the older production fixture's full-test receipt
because it measured an earlier version of the now-final SkyrimNet installer
module. This happened before any lab writes. The source and compiled production
scripts are unchanged, but the broader test provenance must be refreshed rather
than bypassed. A fresh production/harness pair is being built with all measured
inputs frozen; `-11` remains installed until that pair passes verification.
The actual installer module and CLI remain unexecuted against the lab.

Fresh sync inspection found GitHub and clean Echo still at the same baseline
`2f230895455905817f7c0396d2f60ade5e146c27`; overnight changes are not yet published.
Both original Steam manifest read-only flags and recorded hashes still match.

### 00:46–00:49 CDT: controlled fixture works; timing and stop race exposed

The fresh production `se-lab-production-standing-20261021-01` passed 86 tests;
matching harness `-14` passed all 99 lab tests. Independent receipt inspection
verified 186 production and 118 lab inputs. Production PEX differences from the
prior build were only compilation timestamps; source and non-PEX payload were
unchanged. Staging passed all guards, backed up to
`checkpoints/standing-20261021-01/`, and enabled the separate controlled-AI opt-in.

Run `20261021T054636Z-1fd285da6f0a` verified Story Manager setup and acquired the
lab alias's stay package `0010FB3F`. Sven was standing, eligible, loaded and in
the same cell. It selected the strict slot, started playback and wrote a full
identity-bearing **completed** receipt. The terminal harness outcome was still
**failed**, because its 40-second scenario deadline began before preparation.
Actual engine times: setup finished 28.743; deadline 68.743; scan 47.900–48.398;
matching finished 66.430; diagnostics finished 70.342; selection 71.260–73.243;
start trace 76.383. The scan phase took 0.498 seconds; matching consumed 18.032.
Both measurements include their continuation checks, not just the native call.
The next harness separates bounded preparation from the playback deadline.

Timeout cleanup overlapped production completion and exposed a separate real
controller race: after the valid completed slot-1 receipt (`1:2`), a concurrent
stop wrote an interrupted slot-0 receipt (`0:3`) using partly cleared fields.
Both raw receipts are retained. `StopPerformance` needs idempotent admission
and stable receipt parameters across native yields; a narrow fix and compiled
interleaving regressions are in progress. Do not treat this run as acceptance.

The harness released its alias, observed a different package, and restored
globals/hour. Capture `69c3d29c49e44e6fb6b39fe2191bc3b1` contains fresh required
evidence; shared logs are archived in the run. Root stopped exact SkyrimSE
45920 and MO2 46684 after matching paths and full creation timestamps.
No audibility or visual animation claim is made. Production natural-AI design
is now recorded separately in [performer-lifecycle-design.md](performer-lifecycle-design.md).

### 00:59 CDT: narrow stop fix verified offline

The old compiled controller fails nine added race tests in 24 subcases. The
replacement serializes first-stop ownership before yielding, captures stable
receipt arguments, defers new starts/selection during cleanup, and compensates
native startup calls that return after cancellation. Idle stop still cancels
scheduling. All 46 controller tests and 28 identity tests passed; independent
reproductions of four native-boundary failures now produce one slot-1 receipt
and one sound stop. This does not implement the full actor AI lease or protect
library selection against arbitrary external direct calls.

Authoritative `se-lab-production-stopfix-20261021-01` passed all 95 production
tests without skips. The first matching timing harness (`-15`) exposed a
regression in its earlier interruption request: a delayed poll could request a
stop after completion and then accept unrelated evidence. It was not staged.
The replacement keeps separate fixed preparation/playback budgets, binds request
timing to the performance window, and requires the matching production
`stop_requested` guard. The existing eight-second synthetic fixture is unchanged.
The currently installed pair remains standing production01 / harness14.

### 01:10–01:13 CDT: final harness rejects vanilla package preemption

The replacement harness `-16` passed all 111 lab tests (92 focused cases also
passed independently), with no skips. Production stopfix01 passed 95 tests.
The linked handoff verifies all 186 production and 118 lab measured inputs and
all 22 harness receipt hashes. That pair was staged, with prior files retained
under `checkpoints/stopfix-20261021-01/`.

Run `20261021T061035Z-a82c7eba3b8e` failed **before selection** at real time
51.460, before its fixed preparation deadline of 120.013. Story Manager setup
finished at 30.013 and the lab initially acquired standing package `0010FB3F`.
Sven subsequently switched to vanilla `000FB904` (`BardSongsBardSpotTravel`).
The harness correctly rejected that loss of control; no fresh playback start,
stop or receipt occurred. Four historical receipts remain, including the
previous duplicate-stop evidence. This run does not test the new production
stop fix at runtime, and the package alone does not identify the competing scene.

The terminal result reports the owned alias released and globals/hour restored.
Capture `34363982abe24aa29fa8dc13c2d703b1` is `incomplete_evidence` because there
is no fresh receipt; the failed result and shared logs are retained. Root stopped
only the recorded SkyrimSE 47980 and MO2 3412 processes after matching executable
paths and full UTC creation ticks. No lab process remains from this run.

Next bounded task: inspect the actual SE vanilla bard scheduling/scene handoff
and design deterministic, explicitly recorded fixture isolation. Do not retry
until lucky, disable all actor AI, or relax production eligibility. Then obtain
fresh completion and correctly attributed requested-interruption evidence with
the stop fix. Natural ambient behavior and the disabled SkyrimNet tier remain
later checkpoints. Both original Steam manifest locks/hashes are preserved.

### 01:39–01:41 CDT: completion observed; native faction sentinel corrected

Harness `-17` passed all 129 lab tests (110 focused cases independently), with
zero skips. Independent native-call interleavings passed 14/14 after the release
admission fence; the earlier draft passed only 2/14. Actual extracted vanilla
PEX tests also verified four starter/queued/direct request cases, with engine
calls mocked. The fixture is explicitly focused-only: controlled ambient entry
is rejected before world/faction/actor mutation, because automatic selection's
production admission/drain protocol remains a separate implementation task.

It was staged with unchanged production stopfix01, backing up to
`checkpoints/autostart-20261021-01/`. Run
`20261021T063910Z-1ac9c1294471` acquired the NoAutostart faction before transitions,
held package `0010FB3F`, selected strict slot 1, started at 94.365 and completed
at 103.953. It appended exactly one full-identity receipt (`1:4`, index 4) after
baseline 4, with no fresh duplicate or slot-zero receipt. This is normal
completion evidence for stopfix01, not a deliberate native concurrency proof.

The terminal scenario still **failed** at 113.372: native SE reported absent
faction rank **-2** both before addition and after removal. The imported PSC
comment and harness had assumed -1. Alias release, globals and hour restoration
succeeded, but the overly narrow rank check reported a conflict and retained
cleanup intent. Preserve that failed result. A three-comparison harness fix uses
`!IsInFaction && rank < 0` for effective absence, retains raw ranks, and keeps
exact rank checks for preexisting members. New tests cover both negative
sentinels, no-write cleanup, and contradictory readbacks; the old artifact fails
the real -2 cases.

Capture `5297b671606344eb80ed030b1bc77ab9` contains fresh required evidence;
shared logs are archived. Root stopped only SkyrimSE 44864 after checking its
exact path and UTC creation ticks. MO2 had already exited. Two computer-use
observations failed with `foreground window did not report a process id`; no
further UI action was attempted and no visual/audibility claim is made.

The next harness is built from retained detached worktree
`local/se-lab-harness18-source-20261021` at `f54a52a`, with the three frozen
harness overlays. Production admission work is proceeding concurrently in the
main checkout. Harness-only staging must retain the exact installed stopfix01
package, verify its pinned historical test-to-build-to-package hash chain and
installed manifest equality, and make no production writes. It must not claim
the actively edited main controller is the source of that old binary.

### 01:51–01:57 CDT: first complete controlled native pass

Harness `-18` was staged alone against the exact retained stopfix01 package,
with backup `checkpoints/autostart-rank-20261021-01/`. All 132 lab tests passed
without skips and all frozen input/artifact hashes matched. The historical
production receipt chain was verified; no production files were rewritten.

Fresh run `20261021T065140Z-c9a5261dfebc` **passed**. It held the standing fixture,
selected strict slot 1, started at real 104.755, completed, and appended one
full-identity receipt at index 5 after baseline 5. The alias was released,
NoAutostart returned to absent/raw rank -2 with no conflict or retained intent,
and globals/hour were restored. The result records its controlled fixture and
injected focused setup explicitly. It proves neither normal NPC AI behavior nor
visual/audible quality, queued vanilla drainage, or VR compatibility.

Capture `a847264a195f482896f1fcda17427d38` retains fresh matching evidence and
shared logs. Root stopped only SkyrimSE 25484 and MO2 17296 after exact path and
UTC creation-tick checks. The next fresh process run is requested interruption
`20261021T065757Z-4b60d0a80eab`; its owned identities are saved in that run folder.

The production admission draft adds cooperative suspension tickets, drain
acknowledgment and explicit resume without automatic scheduling. Independent
review passed all 89 controller/identity cases, 150 before/after native-call
boundaries and three initialization/load reproductions. The old artifact fails
17 cancellation subcases. Load/init intersections fail closed; acknowledgment
covers this controller's work only. Source and evidence are retained under
`local/se-lab-admission-20261021/`; a fresh authoritative build and harness
integration are in progress, with native validation still pending.

### 01:58–02:03 CDT: requested interruption exposes harness timing

Run `20261021T065757Z-4b60d0a80eab` failed correctly: start trace 88.130,
completed stop 97.719, no stop request, terminal failure at 99.446. It appended
one completed full-identity receipt (`1:6`) after baseline 6. It did not exercise
requested interruption. Full result persistence took about 5.37 seconds and
evidence collection up to 0.826 seconds; the post-start persistence/poll ordering
needs a regression with slow native operations. Do not lengthen the fixture or
relax causality assertions to convert this into a pass.

Alias/faction/globals/hour cleanup succeeded. Capture
`24a01167c7ac415e9b2bd7180fe49d4a` and shared logs retain the failure. Root stopped
only SkyrimSE 40020 and MO2 8688 after path/full UTC creation-tick verification.
The Papyrus log also contains an event-scoped-quest startup error from the
vanilla intro scene's end fragment; it is retained, not attributed to Hold Music
playback. Both original Steam manifests remain read-only with unchanged hashes.

Production `se-lab-production-admission-20261021-01` now has an authoritative
build: 110/110 production tests, 28/28 identity capability tests, no skips, all
111 inputs unchanged. Controller instruction blocks match the independently
reviewed draft. Its handoff is `build/handoff-summary.json`; no installation has
occurred. Harness integration and independent boundary review are next, followed
by a fresh matched-pair native run. A separate agent is implementing the guarded
disabled-SkyrimNet launcher/collector with fake processes/HTTP only.

### 02:15–02:25 CDT: independent continuation review before installation

The first admission-integrated harness draft allowed cancelled setup to write
globals after cleanup, and an old Finish stack could unregister a replacement
run's timer. An identical compiled boundary probe passed only 5/34 cases on
that draft and 34/34 after fixes. The early-interruption change also reproduces
the observed native timing defect against harness18: a simulated slow first
post-start save sees no prior request. The replacement places the request before
that persistence, while retaining actual-start/window/guard/receipt checks.

Authoritative harness19 passed all 145 lab cases (126 harness +19 plugin), but
additional independent ambient movement probes found a blocker: cancellation
at the player lookup or movement native boundary could release the fixture,
then an old continuation could move and trigger production playback. Six of
eight probes showed late movement and three showed late playback. The candidate
is retained and was never installed. Evidence is under
`local/se-lab-harness-independent-admission-20261021/`.

Harness20 must hold movement ownership across player lookup, authorization,
resume and MoveTo return. Cancellation before submission can reconcile after
return; cancellation after submission retains an owned suspension/leases and
reports unresolved movement. Returning from MoveTo cannot prove every later
engine location event was delivered. Do not invent a full engine queue-drain
acknowledgment or automatically resume a cancelled uncertain movement.

Parallel SkyrimNet tooling changed one Python input measured by the original
production test receipt. The original proof is preserved; a supplemental full
110-case rerun passed with unchanged inputs and the same pinned package/build.
Receipt `production-revalidation-tests-receipt.json` is in the admission01 build
folder, SHA256 `3f3f1f86a827c1a36afc889600d19ca45d0913d40d3bf4d7f3bed99b18f38d72`.
The launcher source was frozen before that rerun. Staging must verify both proof
links and the fresh input hashes rather than ignoring the recorded drift.

The validator subsequently added exact-false checks for the new movement
pending/unresolved fields. Its affected test passed all eight negative subcases.
A second preserved supplemental production run again passed 110 cases with
unchanged inputs: `production-revalidation02-tests-receipt.json`, SHA256
`724b434c45700eacfdc513c16c67094a4aeb1c3f45172747e8574f1db734eb80`.
Final20 staging must use this newer receipt. The disabled-tier suite otherwise
passed 57 of 58 cases with one expected Windows symlink skip; no real tier
installation or launch has occurred.

### 02:31 CDT: reviewed admission pair staged; interruption rerun active

Harness20 passed 146/146 cases with zero skips and all measured inputs unchanged.
Independent review of the exact final artifact passed 34 setup/cleanup boundary
cases, eight movement boundaries, four delayed-event checks and a healthy
ambient control. All 55 compiled functions match the cleared proof04 build.
Submitted movement cancellation retains suspension and leases with explicit
unresolved/pending evidence; no late event starts playback in those mocked
checks. These remain compiled-instruction tests, not native concurrency proof.

The source was built from retained snapshot `local/se-lab-harness20-source-20261021`.
Final PEX SHA256 is
`32ff016c8f7c40d824981fc48a289a61668e5925c31af59fba3fca5b9b54d3b9`;
handoff `build/production-lab-handoff.json` SHA256 is
`13708637783eae8e5953124d8d0953fc7bf6e1373dcd72a1ac3153048c076810`.
It binds the original production proof, supplemental revalidation02, source
snapshots, independent evidence and all artifacts.

Root staged production admission01 and harness20 only, backing up the previous
pair/manifest/control under `checkpoints/admission-20261021-01/`. Six files
changed. Fresh preflight passed, then requested-interruption run
`20261021T073100Z-7f43558f4725` launched. No acceptance result exists yet for this
pair. Stop only the saved PID/path/full-creation-tick identities after collecting
its result and archiving shared logs.

### 02:44 CDT: all three matched-pair native baseline scenarios pass

Production admission01 and harness20 passed three fresh game processes:

| Scenario | Run | Capture | New receipt |
|---|---|---|---|
| Requested interruption | `20261021T073100Z-7f43558f4725` | `514b808b0c6042f2a40e4e766a686023` | `1:7`, interrupted |
| Focused completion | `20261021T073656Z-724c1caa62e4` | `47391ff1520742bcb96e49ae320da68a` | `1:8`, completed |
| Ambient entry | `20261021T073954Z-86c74b138816` | `1b2cd6977930447aa145b3078b729fd3` | `1:9`, completed |

Each adds exactly one start/stop and full-identity receipt, preserving earlier
history. Interruption request120.516 followed actual receipt start117.351 by
3.165 seconds, before the eight-second endpoint; guard123.832 recorded
`stop_requested` and stop124.330 recorded `interrupted`. Ambient entry observed
fixture exit and real re-entry after resume, then production check/candidate/
slot selection. Its result has `controller_entry_setup_injected=false` and
`ambient_scheduling_bypassed=false`; all ambient assertions passed.

All three report ticket0, resumed/drained/baselines-ready true, no pending or
in-flight controller/fixture flags, alias/faction release and globals/hour
restoration. Exact owned process identities and cleanup records remain in each
run directory; root stopped only those verified identities after capture and
shared-log archival. No game/MO2 process remains active.

Independent focused-capture review verified all archived hashes and matching
trace/receipt history. SKSE/PapyrusUtilDev contain no error/warning matches;
Papyrus retains vanilla/DLC/BYOH warnings and the vanilla intro scene fragment's
event-scoped quest error at line85. No Hold Music exception, identity-array cast
or JSON parse failure appeared. Do not describe these as error-free playthroughs
or general actor-AI/visual/audible/VR acceptance.

The original Steam SE/VR manifest locks and hashes still match the starting
record. No paid calls, recipe changes or production game changes occurred.

Next bounded task: finalize the native process observer before the absent-only
disabled SkyrimNet installation. Fresh PowerShell/CIM probes take ~0.30–0.35s,
so the current sleep plus subprocess loop can miss a short-lived loader. Native
Toolhelp/process-handle snapshots measured ~7ms and preserve exact FILETIME
creation ticks; CIM rounds some of those values. Launch and collection must use
the same backend and retain full ancestry, not relax comparison to path/PID.
The source owner is adjusting this before first boot; no current native baseline
artifact needs to change. A separate smoke collector is being developed with
fake transports to read narrow effective disabled settings only after exact
process/module/listener attribution. No SkyrimNet instance has been installed
or launched yet.

### 03:06 CDT: disabled-tier launch and smoke tools frozen; installation pending

All three native references pass the full acceptance validator, bound to the
same 200 copied baseline mod files and preserved prior trace/receipt hashes.
Reference file `local/se-lab-skyrimnet-baseline-evidence-20261021.json` has SHA256
`6bb86f980f8e6dd6f32bfcf122e21e92ba3e9ed7ab74d83eaec1243e6fbcc242`.
Ambient duration is validated from its production start trace against the
pinned eight-second source; the harness's focused-only cached duration is not
used for that scenario. Focused duration and requested-interruption window
checks remain strict; no raw capture was rewritten.

The new pre-armed native observer records exact FILETIME creation ticks and
retains short-lived loader ancestry. It uses read-only process handles. A
reviewed final-sample race is fixed: after worker join, the final observed
history/current set is revalidated and can invalidate prior attribution; it
cannot upgrade a previously unattributed launch. Initial full suite passed
67 of 68 with one expected platform skip; four affected launch tests and two
independent final-sample regressions pass. The final 70-case suite is still
running against frozen module SHA256
`e412d6f026a1f236aeefc11b2c516a6ed144b759f212b500fb94368273b1fa79`.
Wait for its final result before installation. Do not compare native creation
ticks to rounded CIM timestamps when checking owned processes for cleanup.

The separate smoke collector passed 20/20 synthetic tests, independently reviewed
and rerun by root. It observes pinned loaded modules, exact process/listener/
accepted-connection ownership and 13 fixed read-only config categories, retaining
only typed comparison results. No live endpoints have been contacted. A new
MCP discovery-only client is being implemented separately; no tool calls or
provider calls are authorized by that discovery client.

The frozen-source installation review has 5,572 files, no blockers and an absent
separate target. It remains unapplied. Root saved prelaunch shared-log existence,
bytes/hashes and timestamps under
`checkpoints/skyrimnet-first-boot-shared-logs-before-20261021/`; SkyrimNet.log did
not exist. This operator snapshot is separate from the bounded smoke collector.
The last synchronized source checkpoint is `450e6b5`; the three-run independent
native audit is retained at `local/se-lab-native-baseline-review-20261021.json`.
