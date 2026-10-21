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

## Explicit disposable-world baseline

A fresh `QASmoke` world can still run Sven's Riverwood intro scene. In the actual
lab `Skyrim.esm`, his highest-priority intro patrol applies until intro stage 10
or MQ102 stage 50; the intro scene also gives him a travel package. Merely
teleporting him into the inn does not remove those packages. This was a plausible
cause of the observed moving/absent fixture; it is not a diagnosis of every
earlier eligibility or idle failure.

For an explicitly disposable autorun world, the operator may add this **boolean**
to the enabled control file:

```json
{"version":1,"enabled":true,"world_id":"hold-music-se-lab","allow_disposable_world_setup":true}
```

This option requires the existing valid world, fresh request, and `auto_run:true`
guards. Manual commands never use it. The harness resolves only the inspected
`DialogueRiverwoodIntroScene` quest `000954D9`, scene `000954DA`, GameHour
global `00000038`, and the read-only MQ102 stage. It temporarily sets GameHour
to 18:00 before any Story Manager entry. The intro is event-scoped: a real engine
run rejected an attempt to start it through `SetStage` while it was stopped.

When the intro has not completed and is not running, the harness first requires
the existing MQ102 stage to be below 50, then teleports the player from outside
Riverwood to persistent marker `00096595 RiverwoodSoldierSceneMarker`. The
marker's spatial cell is `00009731 Riverwood04`, location `00013163`; its storage
parent is Tamriel's persistent cell. The inspected Story Manager `CLOC` chain
(`0001320E` → `0009002B` → `0009002D` → `00096593`) requires that new location,
MQ102 below 50, intro stage 10 not done, and hours 08:00–20:00. Active overrides
preserve these conditions. The harness never calls `Quest.Start`, injects a
story event, or changes MQ102.

It waits for observed loaded-player arrival **and** actual intro quest startup;
arrival alone cannot establish Story Manager acceptance. Only a running quest
receives the authored stage 20 cleanup, whose actual SE fragment calls stage 10
then stops the quest. If the quest naturally completes between observations,
stage 10 done with quest/scene stopped is recorded separately and no restart is
attempted. It verifies stage 10 is done and both quest and scene have stopped.

It then asks Sven to evaluate his normal package, records the package FormID,
and proceeds with the existing inn teleport and unchanged eligibility checks.
Sven's inspected `SvenPlayInn10x16` package
`0001CB1B` covers 10:00–02:00. The recorded package is an observation, not a
condition the harness forces or a promise that the engine will keep it active.

Setup has a 90-second real-time budget for exterior loading and quest startup,
with at most eighty 0.25-second story waits and twenty 0.1-second cleanup waits.
Once verified, a separate 90-second focused preparation or 120-second ambient
deadline starts afresh. Focused playback receives its own fixed deadline from
the fresh production start timestamp, plus the selected duration and 20 seconds
for evidence. Cancellation, a revoked guard, or a changed request
across a latent move or wait prevents setup from continuing or overwriting the
terminal result. `world_setup` records baseline/readback fields, both deadlines,
exterior arrival, observed quest startup versus natural completion, and whether
the stage 20 request was issued and accepted.

GameHour is restored on completion, failure, timeout, or cleanup, with a
three-game-minute readback tolerance for natural clock advancement. A failed
restoration prevents a pass. **Quest stage history is not undone**; evidence
explicitly keeps `quest_history_restored:false` and
`normal_quest_playthrough_verified:false`. Discard the test world afterward.
The source/record inspection artifacts are retained locally under
`local/se-lab-sven-schedule-inspection-20261021/inspection-summary.json`.
Story Manager and exterior-anchor evidence is retained separately under
`local/se-lab-sven-story-inspection-20261021/inspection-summary.json`.

## Optional controlled standing fixture

The live exterior-entry run `20261021T051101Z-1960d1585a9f` verified Story
Manager startup, accepted stage 20 cleanup, stopped quest/scene, and Sven's
normal inn package. It then failed correctly because Sven's sit state was 3.
That package's actual Sandbox inputs allow sitting. This does not establish
which operation consumed the time before the failed eligibility check.

An additional **boolean** `allow_controlled_actor_ai:true` in the control file
opts a disposable autorun into a controlled standing fixture. It requires the
separate `allow_disposable_world_setup:true` baseline above. Manual commands do
not acquire it. The candidate harness requires the controller's cooperative
admission handshake described below, including for ambient setup and cleanup.
With the flag false, ambient entry remains a separate uncontrolled integration
scenario. Controlled ambient scheduling still needs engine confirmation. The lab quest has
priority 90 and one initially empty Optional
reference alias, `0: FixtureActor`, with no default actor, extra actor flags,
factions, or alias scripts. Its sole package is the unoverridden vanilla
`0010FB3F DefaultBardStayAtCurrentLocation`: a Travel template with Near Self,
radius zero, and no forced idle or script. Its conditions exclude followers
and the player. There is no production actor/package override.

Before any player/Sven fixture transition, the controlled autorun also takes a
Sven-only lease on vanilla faction `000163FA BardSingerNoAutostart`. The actual
`BardSongStarter` quest `000BE159`, reached by inn location-change node
`000D1EEB`, checks this faction in its stage-zero fragment before enqueueing a
continuous `PlaySongRequest`. The separate Karita/DA16 exception makes this a
Sven fixture rule, not a general performer policy. The record bindings, actual
PEX tests and decompiled fragment are retained in
`local/se-lab-bard-preemption-20261021/`.

The lease records `IsInFaction` and `GetFactionRank`. Existing membership is
never rewritten. For absent membership, a saved intent precedes one native
`SetFactionRank(faction, 0)`; `AddToFaction` is not used because it is itself a
scripted check-and-set. Readbacks and continuation guards must succeed before
movement. Observable dialogue, a current scene, a running starter quest, or the
known competing bard package `000FB904` prevents acquisition. An unknown current
package is reported as zero, not interpreted as proof of inactivity; the later
loaded/standing package check remains mandatory.

After controller cleanup and owned alias release, the lease removes only an
observed rank zero that this run introduced. A changed rank or changed
preexisting membership is preserved and prevents a pass. The whole acquisition
and release sequences fence new runs, including native getter and mutation
continuations. Cancellation during a mutation can leave a failed pending result
while its late return is compensated; that terminal result is not upgraded.
This is observed-value ownership, not an atomic compare-and-swap: an outside
write of the same rank is indistinguishable, and a process crash cannot restore
state. Dispose of this world instead of saving it as a playthrough.

Native run17 returned `IsInFaction:false` with rank `-2` both before acquisition
and after removal; the imported `Actor.psc` comment mentions only `-1`.
Restoration therefore requires nonmembership **and a negative rank**, while
retaining the raw baseline and final values. This establishes effective absence,
not exact restoration of an internal absent-entry representation. Existing
members still require the exact saved rank; no rank-normalization write is made.

This faction inhibits the starter only. A previously queued or directly invoked
`PlaySongRequest` bypasses it, can wait for dialogue, and may still preempt the
fixture. No wait is treated as proof that such a queue drained, no vanilla queue
is reset, and no repeated start attempt is used to obtain a lucky pass. Evidence
records `vanilla_autostart` baseline/acquisition/release/conflict fields and
always keeps `pending_work_drained_verified:false`.

The harness first moves Sven to the verified stage marker, then saves ownership
intent and acquires the empty alias before moving the player into the inn. This
ordering gives Near Self the stage position. It refuses an already occupied
alias or an actor already using the hold package. A focused run waits within
the 90-second preparation deadline for the exact alias actor, expected
package, loaded actor, and standing/sleep states of zero. The original controller
eligibility checks still apply, and there is only one performance-start attempt.
Uncontrolled ambient mode retains genuine player entry and the production scheduler.

Completion, failure, timeout, cancellation, and revoked opt-in release only the
exact actor this run acquired. A foreign replacement is preserved and reported
as a failure. Release requires an empty alias and an observed package other than
the hold package after `EvaluatePackage`, with at most ten 0.1-second readback
waits. The observed package is reported; the harness does not claim to restore
the exact former package or posture. An acquisition still inside its native call
cannot certify release. Cancellation during that window leaves a failed terminal
result and cleans up any late assignment when the call returns. It never changes
that result into a pass.

Run/request guards are checked after fixture moves, focused scanning, matching,
diagnostics and selection, and around the single production start. These checks
apply to ordinary autorun and manual focused commands as well as controlled AI.
A suspended preparation or finish blocks a new run. Nested cancellation during
release takes precedence over an older completion result.

Production start is not atomic: cancellation inside a native idle/audio call
can return before that start stack does. The result then records
`focused_start_cleanup_pending:true`; an unresolved controlled faction lease
makes its status `failed`, with lease intent still recorded. Suspension asks the
controller to cancel its owned start; the harness retains fixture leases until
the returned ticket reports drain, then leaves the terminal result unchanged.
That pending result does not certify cleanup or a successful run, even after
the later compensation; inspect production traces/receipts for what followed.

Evidence includes `controlled_actor_ai`, the `fixture_ai` acquisition/standing/
release readbacks, and `normal_actor_ai_behavior_verified:false`. A controlled
focused pass would establish controller mechanics with an explicitly held actor.
**Normal tavern AI integration remains outstanding**:
the production controller does not acquire this package. Native `PlayIdle`
compatibility with the lab hold has been observed in a failed overall run; a
passing controlled scenario and normal actor AI compatibility remain separate.

Focused runs record in-memory timing boundaries for native scanning, registry
matching, diagnostics, and selection, publishing them in existing result saves.
The full before/after interval must not be attributed to scanning alone. The
controlled build14 run measured a 0.50-second scan phase and 18.03-second matching
phase (including their continuation guards);
total post-world-setup preparation exceeded the former 40-second limit.
Preparation now has a fixed 90-second budget checked after native phases and
before start. Playback uses the production trace timestamp plus the selected
duration (at most 30 seconds) and 20 seconds for trace/receipt acceptance. Late
observation or subsequent polling never extends that deadline. Ambient retains
its 120-second limit. Evidence also reports collection duration and the previous
completed result-save duration; those measurements add no extra result writes.

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

Autorun waits within its 90-second focused preparation deadline for the player and Sven to
be loaded in the same cell after the teleport. It still uses the unchanged
production eligibility checks. A failed scan records `fixture_diagnostics`:
ownership, registry identity, loaded/same-cell flags, combat/dialogue/follower
state, sitting/sleeping state, distance, and scan count. Its diagnostic flags
are integers so a JSON boolean serialization failure does not erase them.

`focused-complete` awaits the fixture's natural duration. `focused-interrupt`
sets the normal `HM_Config.StopRequested` flag once the observed production start
timestamp is at least two seconds old. Autorun performs a bounded wait of at
most two seconds immediately after confirming that start, then issues the
request before the first full post-start result save. Manual scenarios retain
the poll check before evidence collection. The eight-second synthetic fixture remains
unchanged. Automatic requests stop at the trace-based duration boundary, and
`interrupt_window_missed` records an expired window. The matching receipt must
also prove the request preceded its earlier production-start timestamp plus
duration. A completed receipt still fails; it is never relabelled.

The result distinguishes `performance_start_trace_real_seconds` from the later
`performance_start_observed_real_seconds`. Loading/setup time does not count
toward the interruption interval. The scenario awaits the production
poller, a fresh matching `performance_interrupt_guard` with
`reason=stop_requested` at or after the recorded request time, the stop trace,
and an interrupted receipt. A stop timestamp preceding the request fails.
Completion or an unrelated stop
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

Before baselines or fixture/global mutations, the harness obtains its own
positive `SuspendAdmission()` ticket and waits at most 15 seconds for
`IsAdmissionDrained(ticket)`. A foreign, failed or unsafe hold is never borrowed.
Existing stop receipts become visible before the fresh baseline is taken.
Initial global capture/mutation and admission transitions remain owned across
native returns, so cancellation cannot publish restoration and then allow an
older setup stack to mutate settings or a replacement run.

Focused setup resumes its ticket before the labeled direct controller call.
Controlled ambient setup holds admission while positioning the standing fixture,
then makes a real exterior transition, observes loaded arrival outside the inn,
resumes its own drained ticket, and teleports back into the inn. Only that final
post-resume engine location change supplies the ambient scheduling test; the
harness never invokes `OnLocationChange` for it. Resume itself schedules nothing.
The entire movement step, including player lookup, authorization, optional
resume and `MoveTo` return, keeps an in-flight ownership fence. Cancellation
before submission can reconcile after that step returns. Cancellation after a
teleport is submitted retains admission and fixture leases with
`fixture_movement_unresolved:true`: native return does not acknowledge dispatch
of every delayed location event. Even explicit cleanup cannot infer that missing
acknowledgment; discard this disposable world. No post-cancellation resume is
attempted merely because the native move returned.

On completion/failure/cancellation, the harness acquires or retains a ticket and
waits for actual Hold Music owned-work drain before restoring globals/hour or
releasing the actor alias and starter-faction lease. It resumes admission last.
Cleanup has a fixed 15-second bound; unresolved drain, ownership or readback
retains the ticket/leases and blocks replacement runs. An explicit `Cleanup`
may attempt later reconciliation without upgrading a previously published
failed result. Pending evidence retains the causal failure separately from the
cleanup state. This is not a claim that vanilla scenes or all engine work drained.

The test temporarily sets enabled/chance/session-cap/delay globals and restores
their saved values after this drain on completion, failure, timeout, or cleanup.
Restoration is checked with `GetValue`; a mismatch prevents a pass. A process
crash cannot execute cleanup, which is why the lab uses disposable saves.
Actor fixture positions intentionally remain changed in that disposable world.
Do not use it as a playthrough save.

Papyrus can interleave production and harness stacks. If a receipt becomes
visible between the trace read and receipt read, the harness polls again for
the corresponding stop trace and cleared stop flag, within the same deadline.
Wrong projected identity, regressing trace history, malformed/shrinking receipt
history, or a changed request/control guard fails the run.
Visible stop/receipt evidence alone does not establish that the production stack
returned. Cleanup waits for the owned suspension acknowledgment; the production
stop guard prevents nested stop requests from producing duplicate receipts.
`admission` reports the ticket, in-flight operations, drain observation, resume
and pending state, with scope `hold_music_owned_work` and
`all_engine_work_drained:false`.

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
The protected-literal fix subsequently produced real boolean fields with zero
serialization errors in the isolated SE engine. Later runs reached production
playback and persisted receipts, including a complete projected identity after
the production array-initialization fix. An unsolicited interruption and later
moving/unavailable Sven fixtures still prevented a passing completion scenario.
The initial evening/intro-cleanup baseline failed on the event-scoped quest
startup restriction (`20261021T050155Z-933a384bdad1`). The revised natural exterior
entry subsequently verified the intended Story Manager startup and cleanup,
then failed the seated actor check.

Controlled build14 run `20261021T054636Z-1fd285da6f0a` subsequently verified alias
acquisition, the expected standing package, unchanged actor eligibility, and
alias release. Production started and emitted a completed receipt with the full
projected identity. The overall run failed: preparation exceeded the old focused
deadline before playback began, and concurrent stopping exposed a second
interrupted receipt with slot zero. That historical receipt and the failed run
are preserved. New attempts take fresh trace/receipt baselines rather than
deleting or repairing history. The revised phase deadlines and production stop
guard were installed in build16. Run `20261021T061035Z-a82c7eba3b8e` then failed
before selection when vanilla package `000FB904` replaced the verified hold
package; no new recording receipt was emitted. This motivated the narrow
starter-faction lease above.
Normal actor AI integration, audibility and visual animation remain unverified.

Run17 `20261021T063910Z-1ac9c1294471` verified the faction lease, standing alias,
real playback, and one completed receipt with the full identity. Alias release,
globals and GameHour also read back correctly. Its overall status stayed failed
because cleanup expected absent rank `-1`, whereas the engine returned `-2`.
That failed result is preserved. Frozen18 completion run
`20261021T065140Z-c9a5261dfebc` then passed: exactly one new start, completed stop
and full-identity receipt (baseline/index 5), with alias, globals and hour
restored. The faction went from absent/rank -2 to owned rank 0 and back to
absent/rank -2 with no conflict. This verifies the controlled focused baseline,
not normal actor AI, audibility or the later admission candidate.

Frozen18 interruption run `20261021T065757Z-4b60d0a80eab` reached a normal
completed receipt, but issued no interruption request. Its first full post-start
save consumed approximately 5.37 seconds; the next poll missed the short fixture
window. Alias, faction, globals and hour restored correctly. The candidate early
request ordering above addresses that measured bottleneck without lengthening
the signal or accepting a completed receipt as interruption. The new admission
integration and revised interruption ordering remain offline candidate evidence
until the matched package is tested in the engine.

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
