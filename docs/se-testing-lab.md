# Isolated Skyrim SE testing lab

`tools/se_lab.py` operates only inside `C:\MGO\HoldMusic-SE-Lab`.
There is no command-line root override. Its fixed runtime is Skyrim Special
Edition **1.6.1170.0**, with the portable MO2 profile **Hold Music SE Lab**.
It never edits the production Skyrim VR/MGO installation.

The first tier tests the engine, SKSE, JsonUtil and the dedicated lab harness.
It refuses a loose `SkyrimNet.dll` winner and requires `paid_generation: false`.
SkyrimNet/MCP integration belongs in a separately configured later tier.

## Installed state, updated 21 October 2026

The independent physical copy exists at the fixed path above. It was copied
from the installed **1.6.1170** game; no Steam update was accepted. It is not a
hard link or junction to the Steam installation. Copying adds isolation from
Steam-managed file replacement; matching the runtime and dependencies remains
necessary.

Both original Steam app manifests remain read-only with unchanged hashes.
SE (`489830`) has an update pending, and Steam logs an access-denied manifest
write. VR (`611670`) has no pending target build. That explains why only SE
currently displays the update failure; it does not mean the VR lock is absent.
The audit and original manifest copies are under the lab's `checkpoints/`.

The **Bootstrap - SKSE only** profile reached QASmoke through the copied
SKSE 2.2.6 loader. Its screenshot and SKSE initialization logs are retained at
`checkpoints/skse-bootstrap-qasmoke.png` and `checkpoints/skse-bootstrap/`.
This establishes that the isolated game and loader can run. It does not
establish Hold Music, JsonUtil, SkyrimNet, audible playback or VR compatibility.
The lab game and MO2 processes were then stopped; no playthrough save was used.
The original SE/VR installations and the other character-testing lab were not
modified. Shared SE Documents logs were backed up before the bootstrap.

Installed in the main profile:

- SKSE Scripts 2.2.6 and matching root loader/runtime DLL.
- MCM Helper SE 1.6.2, with only its Skyrim SE installation branch.
- Hold Music Candidate from `se-lab-production-admission-20261021-01`.
- Separate harness from `se-lab-harness-20261021-20`.
- Hold Music Lab Data: eight seconds of deterministic plucked-tone PCM,
  strict synthetic recording identity, one session slot, and a lab-only world.
- PapyrusUtil AE SE 4.6, Nexus file 462773, for Steam 1.6.1170/SKSE 2.2.6.
- SkyUI 5.2SE, Nexus file 35407.
- Address Library AE version 11, Nexus file 470707, including
  `SKSE/Plugins/versionlib-1-6-1170-0.bin`.

The three original Nexus archives were downloaded on Echo and transferred over
SSH. All byte sizes and SHA256 values matched Echo's receipt. The additive
installation and pre-edit profile/manifest backups are under
`checkpoints/nexus-dependencies-20261020/`; the manifest records actual hashes
for all 38 added files. All **442 preflight checks passed**.

The first runner launch exposed an MO2 command-line error: `-i ""` queries the
instance and exits successfully without launching. The runner now relies on the
verified portable marker and omits that query option. A subsequent engine run
loaded PapyrusUtil and MCM Helper successfully, initialized Hold Music and
SkyUI, and teleported into the Sleeping Giant Inn. Its focused scenario failed
the Sven eligibility check before playback. The failed result and shared
Papyrus/SKSE log copies are retained under
`runs/20261020T160503Z-aa30e1b59ea5/`; do not count this as a playback pass.

That first run also exposed null boolean fields in the harness result and
matching native JSON parser errors. Revision `-07` uses protected JSON literals
and checks parser return, value type and readback; a serialization/save failure
cannot log or record a pass. It adds Sven's load/cell/scan/eligibility diagnostics
and a bounded wait for the loaded fixture without overriding the production
eligibility rules. Requested interruption must have its own stop request and
an interrupted receipt; its two-second delay starts at the first observed
production start trace, excluding fixture loading.

The revised harness is installed with its previous package and manifest backed
up at `checkpoints/harness-revision-20261020-07/`. All **56 offline lab tests
passed with zero skips**, including compiled-PEX regressions. The runner and
fixture suite passed **33 of 34 cases**, with one expected Windows directory
symlink capability skip. Post-install preflight again passed all **442 checks**.
That revision left the production candidate unchanged. The user released Steam
for overnight testing on 20 October, and run `20261021T042942Z-71888dbfa3cd`
confirmed valid boolean results, loaded/eligible Sven, playback start, completion
and cleanup. It still failed acceptance because the receipt lacked identity.
Native logs exposed a `None` to `String[]` cast that invalidated reused compiled
array temporaries. The replacement candidate uses a typed ten-element reset and
an explicit identity-key gate. Its 80 production tests (including 28 identity
tests) and compatible harness's 56 tests passed with zero skips; the old candidate
fails the new regression at the same cast observed in the engine.

The replacement packages and manifest were staged with backups under
`checkpoints/arrayfix-20261021-01/`. Run `20261021T043545Z-296b66f70a50`
selected the recording but recorded `idle_failed`; its receipt evidence was
unchanged. Run `20261021T043703Z-0dbef97ebacd` started playback and produced a
full identity-bearing receipt, but its unsolicited interrupted outcome failed
the requested completion scenario. Neither is a full acceptance pass. Investigate
the immediate idle/interrupt guard state, then prove completion, requested
interruption and ambient entry in fresh worlds. The
[overnight checkpoint](se-lab-overnight-2026-10-21.md) records the current work.

The current diagnostic candidate preserves the original eligibility and poll
guard order. It adds event-only `idle_failed_state` and
`performance_interrupt_guard` records, including the first failing guard and
subsequent actor/scene state. The snapshot can change after the triggering check;
it is diagnostic evidence, not a new eligibility rule. Existing start/stop
records and harness requirements remain unchanged. Its 86 production tests and
56 lab tests passed; independent compiled review passed 37 controller/trace
tests. The preceding package and manifest are retained under
`checkpoints/diagnostics-20261021-01/`.

Fresh disposable-world setup exposed a separate fixture issue: Sven's intro
quest is event scoped. Run `20261021T050155Z-933a384bdad1` failed when the engine
refused to start it directly with its cleanup stage. No inn movement or playback
occurred. A source-inspected replacement now primes the real Change Location
event by entering Riverwood, observes quest startup, and only then invokes the
authored cleanup. Run `20261021T051101Z-1960d1585a9f` verified that setup in the
engine, including the intended inn package. It then correctly failed because
Sven had sat down (`sit_state:3`) before selection. The clock and globals were
restored. The separately opted-in standing fixture is now installed with backups
under `checkpoints/standing-20261021-01/`. It temporarily fills a lab-owned alias
with the verified vanilla stay package and observes acquisition/release; it does
not relax production eligibility or claim normal tavern behavior. The refreshed
candidate/harness subsequently exposed a preparation-deadline failure and a
concurrent-stop duplicate receipt. The current pair fixes stop serialization
and separates bounded preparation from playback evidence, requiring a matching
`stop_requested` guard for requested interruptions. It passed 95 production
tests and 111 lab tests without skips; prior packages are backed up under
`checkpoints/stopfix-20261021-01/`. Its first engine run failed before selection
when vanilla package `000FB904` preempted the lab stay package. No new receipt
was written; alias release and globals/hour restoration succeeded. The stop
fix remains unexercised by that run. Runtime acceptance and the next bounded
handoff investigation are tracked in the overnight checkpoint.
MQ102 and normal playthrough saves are untouched.

The focused fixture now acquires temporary Sven-only `BardSingerNoAutostart`
membership before transitions, suppressing the verified fresh Story Manager
starter path. It does not drain already queued or direct vanilla requests.
Harness18 handles the native absent-faction rank -2 and preserves raw readbacks
and exact preexisting ranks. All 132 lab tests passed with zero skips. The
retained production package was not rewritten during harness-only staging.

Run `20261021T065140Z-c9a5261dfebc` **passed controlled completion**, appending
one full-identity receipt and restoring the owned alias, faction, globals and
hour. Fresh requested-interruption run `20261021T065757Z-4b60d0a80eab` failed
correctly: the eight-second clip completed before a stop request was issued.
It appended one completed receipt and restored the fixture; it is not an
interruption pass. Its evidence points to slow post-start result persistence
delaying polling. Both runs and shared logs were archived and their exact owned
processes stopped. No natural NPC AI, visual/audible or VR result is inferred.

A new cooperative controller suspension/drain/resume protocol has passed
independent compiled review and 110 production tests. It is installed with
harness20, which passed 146 lab tests and independent continuation checks.
The matched pair now passes fresh native completion, requested interruption and
ambient entry (runs `20261021T073656Z-724c1caa62e4`,
`20261021T073100Z-7f43558f4725` and `20261021T073954Z-86c74b138816`). Each
appends exactly one full-identity receipt and restores fixture state. Ambient
entry uses the real location event and production scan/selection, with no
injected entry or scheduling bypass. The harness holds fixture ownership until
the controller acknowledges return/compensation of its own admitted work, and resumes before
actual controlled ambient inn entry. Unresolved cleanup must remain visible and
must not permit a replacement run. Cancellation after a submitted movement keeps
an unresolved suspension: native return does not establish that all later
location events have been delivered. Native cancellation races, normal tavern
AI, audibility, visual animation and VR compatibility remain separate checks.
Archived Papyrus logs retain vanilla/DLC initialization warnings and the intro
scene fragment's event-scoped quest error; these are not error-free playthroughs.
The overnight checkpoint records exact captures and progress.

Installation receipts and the blocked preflight are under
`checkpoints/candidate-staging-20261020/`. Existing trace and receipt history
must remain intact. The fixture creator seeds these arrays only for a new lab.
The original compiled harness passed 44 offline tests; the runner passed 31 tests.
These use mocked native calls and fake launches, separate from the bootstrap.
The build receipts retain the provenance of their existing compiler imports;
they do not claim an independently rebuilt SE-native dependency stack.
The complete general suite passed under bundled Python 3.12.14 in UTF-8 mode:
**859 cases, 849 passed and 10 expected platform/capability skips**. The log is
`local/se-lab-general-tests-python312-20261020.log`. An initial default-Python
3.10 run is retained separately; it failed on existing newer APIs, ISO timestamp
parsing, missing PyYAML and Windows default text encoding. No compatibility
fixes for that older environment are included in this lab change.

SkyrimNet and its additional dependencies have been acquired/staged where
available, but are not enabled in the baseline. Its integration is the next
tier after the controller scenarios pass. There were no paid provider calls.

## Layout and installation record

The installation owner prepares these paths; this tool does not install them:

```text
C:\MGO\HoldMusic-SE-Lab\
  lab-manifest.json
  Game\SkyrimSE.exe
  Game\skse64_loader.exe
  Game\Data\
  MO2\ModOrganizer.exe
  MO2\portable.txt
  MO2\ModOrganizer.ini
  MO2\mods\
  MO2\overwrite\
  MO2\profiles\Hold Music SE Lab\
    modlist.txt
    plugins.txt
    settings.ini
    Skyrim.ini
    SkyrimPrefs.ini
  runs\<run-id>\
```

`lab-manifest.json` is strict JSON with this shape. SHA placeholders must be
replaced with independently recorded lowercase SHA256 values:

```json
{
  "version": 1,
  "paid_generation": false,
  "runtime": {
    "path": "Game/SkyrimSE.exe",
    "version": "1.6.1170.0",
    "sha256": "<runtime SHA256>"
  },
  "loader": {
    "path": "Game/skse64_loader.exe",
    "sha256": "<loader SHA256>"
  },
  "mo2": {
    "path": "MO2/ModOrganizer.exe",
    "profile": "Hold Music SE Lab",
    "sha256": "<MO2 SHA256>"
  },
  "required_mods": [
    "SKSE Scripts 2.2.6",
    "MCM Helper SE 1.6.2",
    "Address Library AE",
    "PapyrusUtil SE 4.6",
    "SkyUI SE 5.2",
    "Hold Music Candidate",
    "Hold Music SE Lab Harness",
    "Hold Music Lab Data"
  ],
  "required_plugins": ["HM_Lab.esp"],
  "files": [
    {
      "path": "MO2/mods/Hold Music SE Lab Harness/HM_Lab.esp",
      "sha256": "<plugin SHA256>"
    }
  ],
  "logs": [
    {
      "id": "harness",
      "path": "MO2/overwrite/SKSE/Plugins/StorageUtilData/HoldMusicSELab/result.json",
      "required": true,
      "run_id_field": "run_id"
    }
  ]
}
```

The example uses the first-tier installation's mod folder names. List every
actual required plugin and relevant dependency/script hash as well; the single
`HM_Lab.esp` file entry illustrates the shape rather than a complete inventory.
Every required plugin must have a declared matching hash at its actual loose
winner. Declared active mod/Data files are also checked against their winners,
so an unexpected overwrite script cannot silently replace a hashed lower copy.
Do not put mutable request/result logs in `files`.

Preflight reads the executable's Windows version resource independently of its
declared hash. It checks portable mode, the configured game path and profile,
profile lists, required hashes, plugin winners and the harness control.
Explicit MO2 directory overrides must match the audited directories:
`MO2`, `MO2/mods`, `MO2/profiles`, `MO2/overwrite`, `MO2/downloads` and
`MO2/webcache`. `settings.ini` must enable both `LocalSaves` and `LocalSettings`;
the selected profile must contain its local `Skyrim.ini` and `SkyrimPrefs.ini`.

The effective harness control is:

```json
{"version": 1, "enabled": true, "world_id": "hold-music-se-lab"}
```

Its virtual path is
`SKSE/Plugins/StorageUtilData/HoldMusicSELab/control.json`.

## Explicit actions

Use the verified Python 3.12 environment with the repository requirements and
UTF-8 mode. Do not rely on this PC's default `python`, which currently selects
3.10 without PyYAML. Existing full-project tooling uses newer standard-library
APIs and ISO timestamp parsing; the full suite also reads UTF-8 palette files.
For this installation:

```powershell
$LabPython = 'C:\Users\neilg\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONUTF8 = '1'
```

Run a read-only preflight and retain its `review_token`:

```powershell
& $LabPython -B tools/se_lab.py preflight
```

Launch with that fresh token:

```powershell
& $LabPython -B tools/se_lab.py launch --review-token "<token>" --scenario ambient-entry --timeout-seconds 30
```

Launch checks that no Skyrim or MO2 process is already running, records the
baseline, rechecks the inputs, writes a new harness request, and launches only
the isolated MO2. It uses `-p` for the fixed profile and the explicit SKSE loader
path with the lab Game working directory.
Portable selection comes from the verified `portable.txt` sentinel. Do not add
`-i ""`: MO2 2.5.2 treats an empty instance option as a query and exits with code
zero without launching the game. These options are implemented by the
[MO2 2.5.2 command-line source](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/commandline.cpp).

An explicit `--scenario` selects `ambient-entry`, `focused-complete`, or
`focused-interrupt`, and publishes `auto_run: true`. Omit it for manual mode.
Use a fresh game process and disposable world for each single-slot fixture
scenario. The start-enabled quest consumes autorun only on initialization.
Ambient entry uses a scripted teleport into the inn and observes the actual
engine location event; it does not certify walking through the door.

The timeout is a **wait limit**, not a game termination deadline. A timeout
leaves every process running. A launcher exit code is recorded without treating
it as a passing engine or gameplay test. No `taskkill`, process-name termination
or child-tree cleanup is performed.

For the next scenario in an already-open lab, obtain a fresh preflight token
and arm a new request without launching another process:

```powershell
& $LabPython -B tools/se_lab.py arm --review-token "<token>"
```

`arm` does not send game input or run a console command. It only records a new
baseline and writes the request. Use the harness's documented scenario entry
point separately. Interrupt/Cleanup actions for the current scenario keep its
existing request; arm again only when beginning another scenario.

Launch and arm write:

```text
MO2/overwrite/SKSE/Plugins/StorageUtilData/HoldMusicSELab/request.json
```

The request contains `version`, a unique `run_id`, and `started_at_utc`.
The harness must echo the exact `run_id` and `started_at_utc` into its result.
Explicit scenarios add `auto_run` and `scenario`. The preceding request
is preserved in the new run directory. Inputs and request publication use a
local writer lock; this does not exclude unrelated editors or establish game
process ownership.

## Evidence collection

After running the scenario, collect its declared lab-local evidence:

```powershell
& $LabPython -B tools/se_lab.py collect --run-id "<run-id>"
```

Each capture receives a new directory:

```text
runs\<run-id>\
  preflight.json
  run.json
  previous-request.json       # when a prior request existed
  launch-result.json          # launch mode only
  launcher-output.log         # launch mode only
  captures\<capture-id>\
    evidence.json
    logs\<log-id>.bin
```

Evidence is fresh only when its content hash differs from the recorded baseline,
its write time is at or after the run start, and any declared JSON `run_id_field`
matches the run. At least one required JSON result must echo the nonce and
request timestamp. Explicit scenarios must match the known harness result
names: `ambient-entry` maps to `ambient_entry`, `focused-complete` to
`focused_complete`, and `focused-interrupt` to `focused_interrupt`.
Touching an unchanged old log, copying a result with the wrong nonce, a missing
required result, invalid JSON or a file that changes during collection cannot
produce complete fresh evidence.

The exact observed bytes are archived, including stale files for diagnosis.
Full text logs may include older lines; use the recorded baseline and timestamps
when attributing their contents. Captures never replace existing captures.
`fresh_required_evidence: true` means the expected current-run evidence was
collected. It does **not** mean the scenario passed: inspect the harness result's
checks and errors. The tool keeps `runtime_verified: false`.

Global SKSE/Papyrus logs outside this lab are not silently read or archived.
The installation operator must separately preserve any shared Documents files
and explicitly stage relevant evidence into a declared lab-local path with its
source provenance. Missing output at the declared physical path remains missing
evidence; a presumed MO2 write destination is not treated as verified.

## Fixture checks

```powershell
& $LabPython -B -m unittest discover -s tests -p test_se_lab.py -v
& $LabPython -B -m unittest discover -s tests -p test_se_lab_fixture.py -v
```

These tests patch the fixed root to a temporary fixture and use fake executable
version readers and launchers. They do not launch Skyrim, MO2, SKSE or a provider.
They cover identity/hash failures, profile isolation, overriding winners,
foreign paths, stale review tokens, existing processes, timeout preservation,
per-run nonces, stale/malformed logs, archive bytes and input drift.
