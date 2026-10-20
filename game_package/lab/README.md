# Hold Music SE laboratory harness

This package is for a separate Skyrim SE laboratory and disposable test saves.
It contains a normal `HM_Lab.esp`, its start-enabled quest `HM_LabQuest`, and
`HM_LabHarness.pex`. Its masters are `Skyrim.esm` and `HoldMusic.esp`. It references
the production quest/controller; it neither overrides their records nor changes
their source.

The first tier does not call SkyrimNet or any paid provider. It exercises the
actual Hold Music controller, PapyrusUtil/JsonUtil, vanilla bard scene shutdown,
idle acceptance, Sound form playback calls, and receipt persistence.

## Explicit activation and evidence

All three paths are relative to `Data/SKSE/Plugins/StorageUtilData`:

- `HoldMusicSELab/control.json`
- `HoldMusicSELab/request.json`
- `HoldMusicSELab/result.json`

The control file must be version 1, explicitly enabled, and match
`HM_Config.WorldId`. The accepted lab world is deliberately fixed:

```json
{"version":1,"enabled":true,"world_id":"hold-music-se-lab"}
```

Every scenario needs a **new** runner-generated run ID. The runner must archive
each result and compare both its ID and timestamp with the request. A result from
a previous run, even one that passed, is not current evidence.

```json
{
  "version": 1,
  "run_id": "a-fresh-uuid-for-this-scenario",
  "started_at_utc": "2026-10-20T12:00:00Z",
  "auto_run": true,
  "scenario": "ambient-entry"
}
```

Supported autorun scenarios are `ambient-entry`, `focused-complete`, and
`focused-interrupt`. The quest's `OnInit` checks only an explicitly true
`auto_run` flag; it polls the enabled control/world/property bindings for at most
30 seconds. It never starts a scenario just because the plugin is installed.
Use a fresh process and new disposable save for each single-slot fixture test.
There is no player-load-game autorun hook.

Before launch, seed valid empty production arrays in the isolated lab only:

```json
{"version":1,"entries":[]}
```

```json
{"version":1,"performances":[]}
```

These are `HoldMusic/trace.json` and `HoldMusic/receipts.json`, respectively.
The harness requires them to exist, takes fresh baselines, and never clears or
replaces either history. It also never resets the production slot locks,
performer cooldowns, remembered session count, or runtime identity contracts.
The fixture library must contain a compatible playable projected recording
with a nonempty identity key; legacy unknown identity cannot pass this lab.
Focused fixture duration must be positive and no longer than 30 seconds.

## Actual entry versus focused calls

Start autorun outside an inn, for example in `QASmoke`. The following persistent
references were verified in the lab's `Skyrim.esm`:

| Purpose | Local FormID | Parent cell |
| --- | --- | --- |
| Sven actor reference, base `0001347F` | `00013491` | Persistent actor |
| Sven stage XMarkerHeading | `001027DA` | `RiverwoodSleepingGiantInn`, `000133C6` |
| Player audience marker | `0010FCB7` | `RiverwoodSleepingGiantInn`, `000133C6` |

The harness resolves only these fixed base-master references. It validates the
actor's registry identity and the markers' shared inn location, moves Sven to
the stage marker, and moves the player to the audience marker. This is a real
engine location transition caused by a **scripted teleport**. It does not
establish that walking through a door works.

`ambient-entry` arms first, then teleports. It requires the fresh production
trace chain `location_enter` → `check_start` → eligible Hold Music-owned Sven →
`slot_chosen` → `performance_start` → `performance_stop`, followed by a new
matching receipt and projected identity key. It never calls the controller's
entry handler or start function directly.

The focused scenarios explicitly call the controller's entry handler to
initialize its private venue, cancel the scheduled ambient check, scan for Sven,
choose an unlocked recording, and call `StartPerformance`. Their evidence
therefore sets `ambient_scheduling_bypassed` and
`controller_entry_setup_injected` to true. They do not claim ambient selection
or a naturally delivered entry event.

Autorun waits within its 40-second focused deadline for the player and Sven to
be loaded in the same cell after the teleport. It still uses the unchanged
production eligibility checks. A failed scan records `fixture_diagnostics`:
ownership, registry identity, loaded/same-cell flags, combat/dialogue/follower
state, sitting/sleeping state, distance, and scan count. Its diagnostic flags
are integers so a JSON boolean serialization failure does not erase them.

`focused-complete` awaits the fixture's natural duration. `focused-interrupt`
sets the normal `HM_Config.StopRequested` flag two seconds after first observing
the production start, recorded as `performance_start_observed_real_seconds`.
Loading/setup time does not count toward this interval. It awaits the production
poller, stop trace, and interrupted receipt. Completion or an unrelated stop
before the harness requests interruption fails this scenario. A direct stop
call is used only to bound cleanup, never as a substitute for successful
interruption evidence.

Manual console commands remain available, with `auto_run` absent or false:

```text
cqf HM_LabQuest ArmAmbient
cqf HM_LabQuest FocusedStart
cqf HM_LabQuest FocusedInterrupt
cqf HM_LabQuest Interrupt
cqf HM_LabQuest Cleanup
cqf HM_LabQuest Status
```

Arm ambient outside an inn and then enter. Start focused scenarios inside the
inn with Sven present and eligible. `Interrupt`, `Cleanup`, and `Status` refer to
the existing active run; the other commands consume a fresh request ID.

## Results and cleanup limits

`result.json` includes the request ID/timestamp, scenario, `running` / `passed` /
`failed` / `cancelled` status, reason, baseline/current trace sequences,
baseline/matched receipt indices, selected slot/key, and individual assertions.
It distinguishes an injected focused setup from a scripted fixture teleport.
Missing, malformed or stale results cannot establish current evidence.
The collector archives fresh results independently of their outcome: a
still-running, failed or cancelled result is not a successful scenario, even
when evidence collection succeeds.

Boolean evidence uses whitespace-protected JSON literals and checks the native
parser result, stored JSON type, and value readback. Any mismatch reports
`boolean_serialization_errors`, changes the result to `failed`, and prevents
continued execution. A failed evidence save also ends the scenario; final
Papyrus logging cannot claim a pass if the final result could not be saved.

The test temporarily sets enabled/chance/session-cap/delay globals and restores
their saved values on completion, failure, timeout, or explicit cleanup.
Restoration is checked with `GetValue`; a mismatch prevents a pass. A process
crash cannot execute cleanup, which is why the lab uses disposable saves.
Actor fixture positions intentionally remain changed in that disposable world.
Do not use it as a playthrough save.

Papyrus can interleave production and harness stacks. If a receipt becomes
visible between the trace read and receipt read, the harness polls again for
the corresponding stop trace and cleared stop flag, within the same deadline.
Wrong projected identity, regressing trace history, malformed/shrinking receipt
history, or a changed request/control guard fails the run.
Once the production stop trace or its matching receipt is visible, finishing
the lab never calls `StopPerformance` again: the production stack may still be
clearing its private performer, and a second stop could create a duplicate
receipt. It unregisters scheduling instead. A production completion stack that
resumes afterward can still schedule its ordinary next check; the result does
not claim timer quiescence.

`performance_start` establishes that `PlayIdle` returned true and `Sound.Play`
returned a nonnegative handle. A stop trace and matching receipt establish the
production cleanup path; they cannot prove audible sound or a visually correct
animation. Accordingly every result keeps `audio_audibility_verified:false` and
`animation_visual_verified:false`. The harness also cannot certify a Skyrim VR
native plugin, headset behavior, the MGO stack, or an existing playthrough.

## First engine run and pending confirmation

The first isolated SE run (`20261020T160503Z-aa30e1b59ea5`, harness build `-05`)
reached the inn transition without a CTD, then failed the Sven
loaded/eligible/owned check before playback. It also persisted null boolean
fields; PapyrusUtil logged JSON parse errors. The available evidence does not
identify which eligibility condition failed.

Papyrus uses a case-insensitive string cache that preserves an existing spelling,
as documented in [SKSE StringUtil](https://github.com/ianpatt/skse64/blob/master/scripts/modified/StringUtil.psc).
An already-interned `True`/`False` is therefore a plausible source of invalid JSON
from bare lowercase literals. [PapyrusUtil's parser](https://github.com/eeveelo/PapyrusUtil/blob/master/External.cpp)
replaces the destination even when parsing fails, consistent with the nulls.
The protected-literal fix, fail-closed serialization checks, and new fixture
diagnostics have compiled-fixture regression coverage; their engine confirmation
remains pending. No successful playback or cleanup is claimed from that first run.

## Offline build and tests

`tools/build_lab.py` takes explicit production candidate and toolchain paths.
Without `--build` it prints a read-only plan. With `--build` it requires a fresh
workspace, copies hashed inputs and exact cached dependencies there, compiles
only the new harness, and writes the separate plugin/package. There is no
install or launch option.

```powershell
python -B game_package/lab/tools/build_lab.py `
  --workspace C:/path/to/fresh-lab-build `
  --production-build C:/path/to/verified-production-build `
  --compiler C:/path/to/Caprica.exe `
  --flags C:/path/to/TESV_Papyrus_Flags.flg `
  --decompiler C:/path/to/Champollion.exe `
  --dotnet C:/path/to/dotnet.exe `
  --dependency-assets C:/path/to/cached/project.assets.json `
  --build
```

The build receipt records source/input/output hashes and explicitly retains
`offline_only:true`, `runtime_verified:false`. Champollion PEX assembly can be
complete even when its optional reconstructed PSC output reports an error;
the receipt keeps those diagnostics separate.

```powershell
$env:HOLD_MUSIC_TEST_BUILD='C:/path/to/verified-production-build'
$env:HM_LAB_BUILD='C:/path/to/fresh-lab-build/build'
$env:HM_LAB_PACKAGE="$env:HM_LAB_BUILD/package"
python -B -m unittest discover -s game_package/lab/tests -v
```

The tests execute the compiled PEX assembly using the existing instruction
interpreter with mocked native APIs, and independently inspect the ESP/VMAD/SEQ.
They are useful regression checks, not evidence that Skyrim has run.
