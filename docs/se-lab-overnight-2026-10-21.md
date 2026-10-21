# SE lab overnight checkpoint, 20–21 October 2026

The user released Steam for overnight work on the evening of 20 October.
Continue until 08:00 America/Chicago on 21 October, then summarize and pause the
`hold-music-offline-overnight-development` heartbeat. The old Echo watcher stays
paused. The former Steam-use deferral is lifted for the isolated lab only.

## Current checkpoint (02:44 CDT)

- Native-fix checkpoint `f54a52a` is synchronized on Halcyon, GitHub and clean
  Echo. The earlier local commit is retained on
  `checkpoint/se-lab-native-fixes-20261021-0120`.
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
