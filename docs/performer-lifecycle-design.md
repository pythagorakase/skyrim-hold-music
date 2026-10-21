# Performer lifecycle design

21 October 2026. **The full performer lease remains proposed, not runtime accepted.**
The next prototype should give Hold Music a dedicated performer alias and a
bounded package lease, then remove that overlay when the performance ends.
The lab's controlled alias is test isolation, not the production solution.

## Established evidence

In SE lab run `20261021T051101Z-1960d1585a9f`, Sven was loaded, scanned, in the
same cell, about 211 units away, and registered to Hold Music. Combat, death,
dialogue, follower and sleep checks were clear. His `sit_state` was **3** and
eligibility was **0**; selection, playback and receipt assertions were false.
The fixture observed his ordinary inn package `0001CB1B` after the intro quest
stopped. This establishes rejection **before playback because he was seated**.
It does not explain earlier short performances without interruption snapshots.

The observed production [controller](../game_package/src/Scripts/Source/HM_Controller.psc)
rejects sitting/sleeping actors. `StartPerformance` calls vanilla
`StopAllSongs`, starts an idle and positional audio, and locks a sound slot.
It acquires no actor alias or package. `StopPerformance` stops sound/idle and
writes a receipt, with no AI ownership to release. `CheckVanillaScenes` can
repeatedly stop vanilla scenes and replay the idle. Before the narrow stop fix
below, its `Busy` flag guarded `OnUpdate`, not every public start/stop path.

The [library](../game_package/src/Scripts/Source/HM_Library.psc) also stores the
latest selection in mutable `ActiveComposition`, `ActiveDuration`,
`ActiveIdentity` and `ActiveIdentityKey` fields. Duration and receipt writing
read those fields later. Another selection during acquisition or playback
could therefore change the duration or label the receipt with another track.
An actor lease must preserve the recording selection as well as actor ownership.

Fresh extraction from the isolated SE game's `Skyrim - Misc.bsa`, decompilation
of its three relevant scripts, and selected Skyrim.esm records establish:

- `BardSongsScript.PlaySong` sets `Playing=1`, fills bard aliases and starts an
  authored scene after its dialogue/follower/load checks. The checked-in
  `imports/BardSongsScript.psc` is only a compilation stub.
- `BardSongs` quest `00074A55` attaches `BardSongsBardSpotStay` (`00107513`) and
  `BardSongsBardSpotStay6x19` (`0010F576`) to its Bard alias. Both require
  `Playing==1` and a `BardPlaySpot` linked reference. Sven has that link.
- `BardSongsInstrumentalLute02` (`001069C2`) has package actions as well as idle
  fragments. Its end fragment can call `PlaySong` again: stopping a scene can
  interact with continuation logic.
- `StopAllSongs` sets `StopSong=True`, stops its listed primary scenes and sets
  `Playing=0`; it neither clears aliases nor calls `EvaluatePackage`. Its list
  does not include the separate Bard2 drum/wedding scenes. It is not a complete
  actor-scoped arbitration API.

Stopping vanilla songs thus removes a condition supporting vanilla's stay
packages, while Hold Music supplies no replacement package. This is a concrete
ownership gap and a plausible source of competition with normal AI. It is not
proof that a particular earlier interruption had that cause.

Local evidence is retained under
`local/se-lab-performer-lifecycle-20261021/`: extraction receipt, decompiled
scripts, record dump and override check. The archived run's evidence is
`C:\MGO\HoldMusic-SE-Lab\runs\20261021T051101Z-1960d1585a9f\captures\ed9ae0d4ba6d4bc2bd16d5d7eeb564b5\logs\harness.bin`.
These artifacts are intentionally untracked. No matching record override was
found in the inspected Update.esm/four enabled lab plugins, or loose replacement
for those scripts; this was not a full archive-winner or loaded-save audit.

The later controlled run `20261021T061035Z-a82c7eba3b8e` initially acquired the
lab stay package, then observed vanilla `BardSongsBardSpotTravel` (`000FB904`)
before selection. It failed and released the fixture without starting playback.
That package observation does not identify the exact scene responsible.

Further inspection identifies a narrow lab isolation hook: `BardSongStarter`
quest `000BE159`, stage 0, runs
`QF_BardSongsDrinkingSong01_000BE159.Fragment_1`. Its Change Location story node
`000D1EEB` tests `LocTypeInn` and selects a bard in the event location. The
fragment checks `BardSingerNoAutostart` faction `000163FA`; otherwise it queues
`PlaySongRequest` with continuous playback and `ChangeSettings=True`.
Sven's ordinary inn package has no attached script fragment. Do not attribute
the request to that package simply because it was active.

A temporary Sven-only faction membership, verified before any fixture location
transition and restored last, can suppress this particular fresh request path.
It is not a production AI lease or a general NPC solution: the fragment has a
Karita/DA16 exception, and already queued or direct `PlaySong` calls do not
recheck the faction. `PlaySong` may wait for dialogue, while `ChangeSettings=True`
bypasses its `StopSong` early return. A quiet interval cannot establish that
all queued vanilla work has drained. Foreign scenes or lost package ownership
must still fail the controlled run rather than provoke a stop/reassert loop.
Preserve preexisting faction rank and report conflicting cleanup instead of
overwriting it; same-value writes from another script are not distinguishable.

An executable inspection of the actual extracted Starter and BardSongs PEX
passes four cases: absent membership queues a request; membership blocks the
starter; an already queued request can still start after membership and
`StopAllSongs`; direct `PlaySong` also bypasses the faction. These run in the
repository's opcode VM with native calls/timers mocked, not in Skyrim. Source
hashes and call traces are retained under
`local/se-lab-bard-preemption-20261021/starter-pex-proof.json`.

## Narrow stop serialization: implemented in source

Run `20261021T054636Z-1fd285da6f0a` recorded a completed slot-1 receipt followed
by an interrupted slot-0 receipt for the same performer/start. Overlapping
normal completion and harness cleanup exposed shared fields changing during
`StopPerformance` calls.

The source fix claims stop ownership before yielding, freezes scalar receipt
arguments, detaches active fields and holds admission until cleanup finishes.
Reentrant stops are no-ops; an explicit idle stop still cancels scheduling.
Direct starts and update-driven selection defer during startup/cleanup. A stop
during startup queues cancellation, and the starting stack drains and
compensates late idle/audio returns before reopening admission. Compiled-script
regressions reproduce failures in the old PEX and pass with this fix.

Controlled native run `20261021T065140Z-c9a5261dfebc` now passes normal completion
with one full-identity receipt and fixture cleanup. The deliberate concurrency
interleavings remain compiled-script evidence, not a native stress test. The
fix does not implement the AI alias/package lease, an immutable library
composition/identity snapshot across all callers, or durable save/load
reconciliation. Those remain proposed below.

## Cooperative admission handoff: reviewed, controlled native baseline passed

The installed lab candidate offers `SuspendAdmission()`, returning a positive
ownership ticket or zero; `IsAdmissionDrained(ticket)`; and
`ResumeAdmission(ticket)`, which accepts only the matching drained hold and
does not schedule work. It counts admitted location, scheduling, selection,
scene and native-start stacks as well as active playback/cleanup. Stop requests
invalidate earlier continuations, and late idle/audio effects are compensated
before drain acknowledgment. Suspension during initialization or unresolved
load intersections fails closed rather than clearing counters or slot locks.

Independent review passes 89 compiled controller/identity cases, three concrete
initialization/load reproductions and 150 native boundary checks. The old PEX
fails 17 relevant cancellation subcases. This is a cooperative controller
contract, not authenticated ownership, arbitrary external library protection,
a vanilla queue-drain API or save rollback protection. Fresh-process lab scope
is required until independent save/load upgrade behavior is established.

The lab integration must acquire and drain before fixture setup, then suspend
and drain again before restoring globals or releasing actor/faction ownership.
Timeout or a late unresolved native return retains ownership and reports pending
failure. Controlled ambient tests must resume before a real inn re-entry; they
must not inject a location event to manufacture automatic scheduling evidence.

The matched admission01/harness20 pair passed three fresh SE runs: requested
interruption `20261021T073100Z-7f43558f4725`, completion
`20261021T073656Z-724c1caa62e4`, and actual ambient entry
`20261021T073954Z-86c74b138816`. All ended with the ticket released, no pending
controller/fixture work, and restored alias/faction/globals/hour. Ambient entry
used the production scan and selection. These establish the ordinary controlled
paths; deliberate cancellation interleavings still have compiled/mock evidence,
not native stress-test coverage. Cancelled submitted fixture movement retains
unresolved ownership because MoveTo return cannot certify all future engine
events have drained. None of these fixtures implements the production AI lease.

## Proposed dedicated lease

Use a new optional Hold Music performer alias with an authored holding package
conditioned on our own lease state. Do not edit actor base packages, borrow
vanilla aliases/`Playing`, teleport performers, or broadly disable AI or set
shared restrained/movement flags. A complete owned scene remains an alternative
for later ensembles, with greater fragment and conflict-handling complexity.

The current [plugin builder](../game_package/tools/PluginBuilder/Program.cs)
creates the start-enabled, run-once `HM_Quest` at priority **0**, with player
alias **0**. Preserve existing form/alias identities. Choose and test package
priority explicitly; do not copy the lab's priority 90 into production. The
first prototype may require a new world. Adding aliases to a quest already
persisted in a save needs independent upgrade evidence, not an automatic quest
stop/restart workaround.

Retain the standing eligibility check initially. The lease should keep an
already eligible actor available during playback. Getting a seated bard up is
a separate, bounded invitation/movement design; removing the guard or retrying
until a lucky sample passes would not establish safe acquisition.

1. **Admit and freeze.** Admit one operation before validation can yield. Every
   caller, including direct calls and events, must use the same admission
   protocol. Reserve an authored, Hold Music-owned actor and freeze slot,
   composition, duration, complete recording identity, performer, region and
   receipt scope into the lease. Enforce exclusive selection across all callers
   until that snapshot is complete; later playback/receipts use the snapshot,
   never the library's mutable last selection. Recheck loaded/alive/awake,
   combat/dialogue/follower, venue/cell and current scene.
2. **Acquire.** Record an operation generation and `acquiring` state, fill only
   our empty alias, request `EvaluatePackage`, then wait a bounded interval for
   the expected alias/package and standing state. Check ownership and safety
   after every yielding boundary. Timeout or foreign scene/package preemption
   aborts acquisition; do not fight it by continually replaying the idle.
3. **Play.** Start idle/audio only after acquisition. Distinguish idle refusal,
   sound refusal and actual start. Keep conservative sound-slot reservations
   independent of actor cleanup; releasing AI does not make a cached slot safe
   to overwrite.
4. **Release and drain.** Invalidate the generation, stop polling and stop only
   our sound instance. Keep exclusive acquire/start/release ownership until
   outstanding native calls return and any late owned effects are compensated.
   A stale-generation check cannot undo a late `ForceRefTo`, `PlayIdle` or
   `Sound.Play`. Keep returned values local until ownership is rechecked.
   Do not admit a replacement lease while those calls can still affect it.
   Clear only our alias still containing our actor; stop an idle only when it
   remains ours and will not disturb a newer foreign scene. Preserve a foreign
   alias replacement and report failed reconciliation. Cleanup must be
   idempotent, including recursive/repeated stop requests.
5. **Observe restoration.** After removing our overlay, request reevaluation
   and record alias/package/scene results. Let the engine choose the schedule
   appropriate **now**; do not force the previously observed package back after
   time, quest or combat state has changed. Bound observation and distinguish
   an unloaded/unobservable actor from confirmed restoration.

`ForceRefIfEmpty` in the reviewed ReferenceAlias source is a
`GetReference`-then-`ForceRefTo` helper, not an atomic compare-and-swap primitive.
Neither it nor a generation counter proves mutual exclusion across Papyrus
stacks. The implementation must demonstrate admission and in-flight ownership
under controlled interleavings before relying on them.

Every terminal route uses the same release: completion, disable/stop request,
dialogue, combat/death, cell/venue departure, unload, alias loss and failed
acquisition/idle/audio. Save/load aborts and reconciles a persisted lease before
new admission. Never resume or stop a serialized sound handle on the assumption
that its number still identifies our sound in a new process; real-time comparison
alone does not establish process identity. Clear our alias even without loaded
3D; defer unsafe animation and package observations. Alias events may supplement
polling with the same fences. Emit at most one receipt for a started lease;
acquisition failure has a separate diagnostic, and cleanup must survive receipt
failure. Specify session-count/cooldown accounting for each failure phase, while
preserving conservative slot locking after an audio attempt.

## Ownership boundaries and bounded validation

The first prototype should defer whenever `GetCurrentScene()` is nonempty and
remove global `StopAllSongs`/idle-reassertion as arbitration. An empty scene does
not prove an actor is unowned: acquisition must observe its package and yield
when another wins. Intentional vanilla takeover needs a separate actor-scoped
adapter accounting for continuation callbacks. SkyrimNet's
bard playback must be verifiably disabled for owned-controller tests: registry
ownership and disabling paid composition do not prove cached playback is off.
Verify the effective configuration and runtime state separately. Other
SkyrimNet dialogue/AI can still preempt the actor; yield or use observed,
supported hooks. Do not toggle global providers per song or re-enable another
scheduler when a lease ends.

Acceptance tests must cover eight groups:

1. Standing sandbox actor acquires once; seated/unloaded/foreign-scene actors
   cause no mutation. Competing public callers cannot both pass admission.
2. Initially occupied, replaced and lost aliases preserve foreign references;
   timeout/preemption ends without an idle replay loop.
3. Cancellation around alias assignment, reevaluation, idle and sound calls
   compensates late returns without affecting a replacement lease.
4. A second selection during acquisition cannot change frozen duration,
   composition or receipt identity.
5. Dialogue/combat/scene/cell/unload interruptions in every phase; nested stop
   and receipt-save interleavings produce at most one receipt and safe cleanup.
6. Release across a changed schedule restores current engine choice, without
   demanding the old package.
7. Save/load in every phase, including stale sound-ID collision: no replay,
   foreign sound stop or silent alias leak.
8. Compiled-script and plugin round-trip checks prove alias flags, package
   conditions/priority and preserved IDs. Follow with real SE transitions
   **without the lab-only alias**, then natural inn entry and separate VR tests.

Capture generation, alias, package, scene and recording identity at each
transition. A controlled fixture pass cannot replace ordinary AI or saved-world
upgrade validation. The first bounded runtime claim is lifecycle management for
a naturally standing eligible performer, not automatic acquisition of seated
bards.

This work does not change musical recipes, require new paid generation or gate
progress on listening judgments. It does not establish broad performer support,
SkyrimNet integration readiness or production installation readiness. The
[October 15 VR scan CTD RCA](sven-crash-2026-10-15.md) remains separate: its
installed PapyrusUtil dead-filter dispatch failed before selection/playback.
This lifecycle proposal neither revises that evidence nor attributes that crash
to sitting, audio or competing bard control.
