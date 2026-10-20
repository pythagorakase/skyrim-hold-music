# Hold Music owns performances: design

**Status (19 October 2026 reconciliation):** the owned controller is installed.
Its October 14 session established quest startup and SkyrimNet's live bard
shutdown; that inspection also found conflicting saved configuration copies.
The October 15 Sven visit reached candidate discovery and exposed the native
scan crash documented below. The targeted fix is installed, but successful
owned playback, animation and interruption remain unverified. Refresh the
read-only preflight before the next runtime test rather than treating the
October 14 configuration report as the current state.
See [the runtime test](in-game-test-plan.md#second-test-sven-at-the-sleeping-giant-inn-hold-music-owned-path).

**Migration direction:** MGO 4.0 RC5 and SkyrimNet beta 27 remain the planned
coordinated target. The [migration plan](stack-migration-rc5-beta27.md) defines
the native-import comparison and verification sequence. Portable deployment,
actor identity, library preparation and handoff work can proceed before that
upgrade or the completion of regional listening tests.

**Decision owner:** recorded here by Claude under the delegated takeover; the
user's standing direction is that Hold Music should eventually take over the
bard functions entirely from SkyrimNet.

**Runtime update (15 October 2026, evening):** the first owned-controller test
reached candidate discovery and crashed in PapyrusUtil VR's native dead filter.
SkyrimNet's bard feature was disabled in that session. A targeted controller
workaround is now installed; successful owned playback remains unverified.
See the [native RCA, fix and retest](sven-crash-2026-10-15.md).

## Offline handoff and VFS evidence (20 October 2026)

`tools/reconcile_bard_ownership.py` now prepares the controller handoff without
requiring regional listening results. Its default dry run reads the selected
profile, highest-priority loose Bard Singing configuration, adapter launch
input and any pending overlay. It plans disabling SkyrimNet's bard flag in
the effective loose input and the active adapter input. It leaves Hold Music's
MCM state, mod lists, audio, registry, saves and databases unchanged.
The selected profile identifies which inputs to inspect; it does not isolate
those inputs. Overwrite and mod-directory configurations are shared MO2 files,
so changing them can affect other profiles that read the same file. Review
the proposed paths before deliberately applying a handoff.

For a pending adapter session, it restores the original three provider routing
fields before preserving dashboard edits, then disables bard singing. Changes
to both source and overlay, a conflict copy, or an orphaned baseline block the
handoff for review. A completed session's leftover overlay is removed with an
exact backup; the adapter can build a fresh overlay on its next launch.

```powershell
python tools/reconcile_bard_ownership.py `
  --mo2-root "C:\MGO\Skyrim MGO 4.0 RC4.1" `
  --profile "MGO EXP - SkyrimNet b26 + SeverActions 4.2"
```

The real-install dry run on 20 October planned two changes: disable the old
overwrite `enabled: true` and remove the stale runtime overlay. Its configured
profile-data input was already disabled. **These changes have not been applied.**
No game or MO2 process was launched for this work.

Apply is a separate operation: append `--apply --receipt-dir <new-private-dir>`
only when making the handoff deliberately. The tool checks that Skyrim and MO2
are closed on Windows, snapshots exact original bytes before any mutation,
and records per-file hashes and recovery progress. It refuses changed inputs,
including a newly created higher-priority config or changed profile/adapter
settings. Backups can include provider credentials; keep the receipt directory
private and out of Git. Reports contain paths, hashes and operation metadata,
not configuration contents.

Restore with `python tools/reconcile_bard_ownership.py --rollback <receipt.json>`.
Rollback checks every backup and target hash and the unchanged profile context
before restoring anything. It can recover an interrupted apply, including the
gap between a file replacement and its receipt checkpoint. It refuses to
overwrite later edits. Files are replaced atomically one at a time; the entire
handoff is not a filesystem-wide transaction. MO2, Skyrim and other writers must
remain stopped throughout either operation.

The read-only `game_package/tools/probe_vfs.py` now includes
`SKSE/Plugins/SkyrimNet/config/BardSinging.yaml` in its observed files. Run it
**through the intended MO2 profile**, with its existing `--data-root` and
`--manifest` arguments plus `--profile "<profile name>"`, and save its JSON.
The config row contains the file-handle destination, SHA-256 and parsed
`bard_enabled` boolean from that same open handle. Malformed or ambiguous flags
are explicit failures, with no credential values emitted.

Pass the resulting JSON to `tools/preflight_performance.py --vfs-report <json>`
alongside its ordinary profile arguments. Preflight checks the observation's
profile, destination and current hash; an old report whose bytes changed fails.
A disabled observed overlay **does not clear a conflicting enabled fallback**.
The profile label is supplied by the operator, and the probe cannot itself
prove MO2 injection or a running controller's state. Review the actual opened
destination and startup evidence before the next headset test. The new VFS
probe has fixture coverage but has not yet been run through MO2.

## Why take over

Evidence gathered on 9 October:

- SkyrimNet's bard code is closed (the C++ repository is private). Its bard
  eligibility check is undocumented. Static inspection suggested the Bard
  class or `BardSingerFaction` would exclude Sven and Lynly. That did not
  predict Sven's runtime behavior: SkyrimNet played him successfully on
  October 13. Lynly's runtime eligibility remains unverified.
- Its ambient trigger is an internal scheduler that fires on entering an inn,
  and GitHub issue #559 (open since Beta24) reports it intermittently staying
  silent in exactly the Sleeping Giant Inn and the Bannered Mare.
- Its song cache is one per-save pool filtered only by singer gender (issue
  #652 also reports the cap not being honored), so a Whiterun composition can
  be replayed in Riften and Lurbuk can perform another bard's recording. The
  0.2.x adapter regionalizes composition but cannot regionalize playback.
- Playback uses a native hook on the audio manager rather than the vanilla
  `BardSongsScript` scenes, so neither vanilla schedule mods nor Hold Music can
  coordinate with it.
- The request adapter depends on a lyric-model-copied routing marker because
  SkyrimNet exposes no actor identity on the music request.

Taking over means Hold Music decides who performs, when, what, and plays the
audio itself; SkyrimNet remains the source of character context (memories,
events, dialogue) and nothing else in the bard chain.

## Boundaries

In scope for the first owned release:

- One performer, one lute-family prop, solo lute with or without one voice
  (Phase 1 of the regional spec). Flute, drum, accompanists and ambient
  outdoor scenes stay later phases.
- Inn performances only, triggered by the player entering an inn that has a
  registered performer present and awake.
- Compositions prepared ahead of time, off the game thread, by the existing
  helper process, using the regional recipes and the repertoire planner.
- Performer registry authored by Hold Music (vanilla bards plus explicitly
  registered musicians such as Sven and Lynly), not SkyrimNet's predicate.

Out of scope: on-request singing through SkyrimNet dialogue actions, player
composition, Suno re-download, changing any SkyrimNet database row, and any
new native DLL.

## Architecture

Three parts, two of which already exist in some form.

### 1. Library and executor (helper process, Python, exists partly)

The independent helper that already proxies music requests becomes a small
service with a durable library under the profile's `hold-music-runtime`:

- `registry.json`: performers (stable form identity, display name, home venue,
  known traditions, vocal gender, instrument) authored from the roster audit.
- `library/`: recordings as mono PCM WAV files in numbered slots
  (`hm_slot_01.wav` ... `hm_slot_NN.wav`) plus `library.json` describing each
  slot: performer, region, mode, duration seconds, composition id, lyrics
  hash, generation receipt. ffmpeg (present on Halcyon) converts Lyria's MP3.
- `receipts.json`: performance receipts written by the game side (slot, time,
  outcome) which the planner reads back as `recent_performances` and
  `generation_history`.
- A scheduler loop: for every registered performer keep K ready recordings
  for their home region (initially K = 2, one vocal and one instrumental),
  generating ahead of time with the repertoire planner's cooldowns and job
  caps so a single play session never triggers more than a bounded spend.
  Lyrics come from an OpenRouter LLM call built from the bard's SkyrimNet
  memories, read read-only from the SkyrimNet database (the knowledge bridge
  research documents the tables), through the planner's lyric brief.
  Music comes from the existing OpenRouter Lyria transport and regional
  prompts.

The planner (`hold_music/repertoire.py`) is already the decision engine; this
part supplies the snapshot it was designed for and executes its actions.

### 2. Game package (new: ESL-flagged ESP, Papyrus, sound descriptors)

Built with the same offline toolchain the Modern Marriage mod used on Halcyon:
Caprica for Papyrus, a Mutagen-based plugin builder for the ESP, Champollion
disassembly plus the PEX mock VM for tests, and an MO2 VFS probe.

- One quest (start-game enabled) with a player reference alias whose script
  handles `OnLocationChange`. On entering a location with `LocTypeInn`, it
  scans loaded actors against the registry (form identity), picks a performer
  who is awake, not in dialogue, not following the player and not in combat,
  waits a short randomized delay, and starts a performance.
- A performance is: play the vanilla lute idle on the performer (the idle
  attaches the lute animation object, the same way the vanilla
  `MS05BardLutePlay` script plays the flute idle), play the slot's sound at
  the performer, wait the recorded duration, then play the stop idle. Dialogue
  with the player, combat, the performer leaving the cell or the player
  leaving the location stops the sound and the idle. This is the one-performer
  contract from the regional spec.
- Audio goes through N sound descriptors, one per library slot, each pointing
  at a fixed file name under `Sound\fx\holdmusic\`. The helper fills slot
  files ahead of time; a slot is used at most once per game session so an
  engine-cached buffer can never play stale audio. Mono WAV keeps 3D
  positioning and avoids the xWMA encoder, which is not installed.
- The bridge to the helper is PapyrusUtil's `JsonUtil`: the script reads
  `library.json` to choose a slot (matching performer and current region,
  preferring unperformed compositions) and appends receipts. No polling loop
  runs while nothing is happening.
- An MCM (MCM Helper is installed) exposes the master switch, the instrumental
  chance, the per-session performance cap and a "stop performance" control.

### 3. SkyrimNet hand-off

The 0.2.x adapter remains installed during the pilot, but SkyrimNet bard
singing must be off whenever the owned controller is tested. The planned
config overlay change adds one managed scalar, `bard_singing.enabled`, so switching
to Hold Music ownership is a profile-local toggle that disables SkyrimNet's
scheduler without touching the source config, and switching back is the same
toggle. Lyric generation moves to Hold Music's own prompt at that point; the
`HM1` marker template override is retired with the adapter route.

## Phasing and gates

| Step | Deliverable | Offline proof | Needs the headset |
|---|---|---|---|
| T0 | Registry from the roster audit; library format; helper writes slot WAVs from existing recordings (the Oct 8 Talsgar and Oct 9 Mikael samples) | Unit tests, ffmpeg conversion, manifest validation | No |
| T1 | Game package: ESP, Papyrus controller, descriptors for 24 slots, MCM, install/rollback tool, VFS probe | Caprica compile, PEX VM tests for trigger/selection/interruption, Mutagen round trip, VFS winner check | One session: hear a known slot play on Mikael, confirm the idle, dialogue interruption and stop |
| T2 | Executor: ahead-of-time composition with planner cooldowns and spend caps, lyrics from SkyrimNet memories read-only | Planner tests with recorded snapshots, dry-run mode with no provider calls, one paid end-to-end generation | One session: hear a fresh composition made for the current bard and hold |
| T3 | Hand-off: overlay toggle for `bard_singing.enabled`, retire the marker template, documentation | Config tests | One session with SkyrimNet bards off |

T0 format and API: [Performer registry and recording library](library-format.md).
T1 package implementation and offline boundaries: [game package README](../game_package/README.md).
T1c install/rollback: `game_package/tools/install_game_package.py` supports write-free JSON dry runs and `--uninstall`; JsonUtil's physical write target remains open pending the probe.
T2a implements [offline instrumental and Winterhold wordless preparation](executor.md).
T2b adds the [read-only actor knowledge bridge](knowledge-bridge.md), planner-driven lyrical jobs, and separately accounted lyric/music calls.

T0 and T1 are independent; T2 depends on T0. Offline T3 implementation and
configuration tests can proceed before a headset visit. Permanent takeover
still depends on runtime acceptance and adequate coverage for the other bards.

### Work that can proceed without the Sven visit

- The read-only [performance preflight](evidence.md#read-only-performance-preflight)
  is implemented and exercised against the installed profile. It catches the
  conflicting overwrite/adapter inputs and verifies the matching audio assets.
- Implement and test a reversible ownership switch, including overlay failure,
  restart, dashboard edits, conflict recovery, and return to SkyrimNet. Its
  offline contract must account for both the SkyrimNet switch and Hold Music's
  MCM setting; the registry's `owner` field alone is insufficient.
- Prepare roster and library coverage plans, strengthen actor identity mapping,
  and exercise the planner/executor with synthetic snapshots and dry runs.
  New paid generation remains a separately bounded action.
- Continue prompt consistency and listening-workshop work using versioned
  provisional recipes. Listening confidence is recorded separately and does
  not gate engineering. Admit new repertoire through an explicit source revision;
  no all-regions listening pass is required to develop it. Keep sound-source,
  performer-capability and supported-arrangement checks.
- Follow the [development roadmap](development-roadmap.md) for the next bounded
  integration milestone using existing recordings without paid generation.

The headset gate covers sound and positioning, animation/scene coexistence,
dialogue and departure interruption, and game-written receipts. Offline tests
do not establish those outcomes or approve a full roster rollout.

## Original staged takeover (11 October 2026; isolation assumption superseded)

The first owned release was intended to run beside SkyrimNet and take only
the performers SkyrimNet's eligibility check rejected.
Each registered performer carries an authored `owner` field (`hold_music` or
`skyrimnet`); the game controller performs only for `hold_music` performers,
and the adapter keeps regionalizing SkyrimNet's compositions for the rest.
Sven (Sleeping Giant Inn) and Lynly Star-Sung (Vilemyr Inn) were assigned
`hold_music` on the assumption that SkyrimNet would not act on them. Sven's
October 13 cached playback disproved that assumption. The authored owner
field restricts only our controller; it does not tell SkyrimNet to abstain.
The vanilla scene lock also does not stop SkyrimNet's native audio playback.
A mutually exclusive handoff is therefore required before the Sven test;
Lynly cannot be presumed isolated without runtime evidence either. Full
ownership (T3) remains unverified.

Two consequences shape T1d and T1e:

- **Vanilla scene lock.** The controller does not depend on SkyrimNet to
  silence the vanilla `BardSongs` scenes any more. It calls the vanilla
  quest script's `StopAllSongs()` before its own lute idle and, while a
  performance runs, re-stops any vanilla scene that restarts (bard AI
  packages call `PlaySong(..., ChangeSettings=True)`, which bypasses the
  vanilla stop flag). This is what caused the drum overlap heard on 9 October.
- **Evidence without Papyrus logging.** The profile has Papyrus logging off,
  so the controller writes a bounded `trace.json` through JsonUtil (schema in
  [evidence.md](evidence.md)) and `tools/collect_evidence.py` assembles trace,
  receipts and the relevant log lines into one report after a session. Both
  JSON files are shipped by the installer so MO2's virtual file system keeps
  the game's writes inside the mod folder; the collector also checks
  `overwrite`.

| Step | Deliverable | Offline proof | Needs the headset |
|---|---|---|---|
| T1d | `owner` field in the registry; runtime storage locator; evidence collector; installer ships `trace.json` | Unit tests, derived registry check | No |
| T1e | Owner gate, vanilla scene lock and trace log in the controller; plugin wiring for the vanilla quest and scenes; Halcyon compile | PEX VM tests, Caprica compile, Mutagen round trip | One session: Sven performs at the Sleeping Giant Inn with no vanilla overlap; trace and receipts collected |
| T2c | Consolidated seed library on Halcyon with instrumental recordings for Sven and Lynly (plus sung pieces when the planner selects a topic) | Library validation, bounded spend | No |

Status on 11 October 2026: T1d and T1e are merged (commits bed7648 and cbc6140);
the Halcyon build of the merged tree passed Caprica, the Mutagen round trip and
48 package tests. T2c produced `C:\MGO\hm-scratch\library` on Halcyon with
four validated slots (Mikael vocal and Karita instrumental imported, Sven and
Lynly instrumentals generated for $0.16 together). The planner declined sung
pieces for both: Sven resolves in SkyrimNet's database by name but has no
memories yet, and Lynly has never been met, so there is nothing to write about.
The installer dry run against the real profile planned 22 files and two
profile edits with nothing written. The install itself waits for MO2 to be
closed; see [in-game-test-plan.md](in-game-test-plan.md).

## Decisions recorded

- **Papyrus plus sound descriptors, no DLL.** A native plugin would allow
  playing arbitrary files directly but adds a C++ toolchain and crash surface
  to a VR install; the slot pool is enough for a bounded library and matches
  the toolchain already proven on this machine.
- **Idle animation, not vanilla scenes.** The vanilla `BardSongsScript` scenes
  carry their own songs and quest state (Sven's main-quest branches, Talsgar's
  non-continuous mode). Playing the idle directly keeps Hold Music's audio and
  timing authoritative and avoids silencing work.
- **Registry over predicate.** Who performs is authored data, so Sven and
  Lynly can perform and a Bards College historian need not.
- **Explicit handoff before replacement.** Sven disproved the assumption that
  the owned pilot could safely use bards SkyrimNet ignores. Test with SkyrimNet
  bard singing off and Hold Music on, then return to the opposite state for
  ordinary play. A permanent switch requires broader repertoire coverage.
- **Ahead-of-time generation.** A performance must never wait on a paid
  request; if no recording fits, the bard does not perform and the helper
  queues work for next time.
- **Mono WAV.** Larger than xWMA but encoder-free and correct for a 3D source.

## Open questions to settle during T1

1. Exact form identities of the lute start/stop idles and whether the idle
   alone attaches the lute animation object for every performer race.
2. Whether a sound descriptor can play a 2-3 minute WAV without the engine's
   memory budget complaining; if not, cap recordings at 150 seconds in the
   prompt and trim in ffmpeg. T1b clears slot locks on load when the real clock is below LastRealTime (updated on loads/starts): an engine-cached WAV buffer can only survive within one process.
3. The right interruption set in VR (menus, fast travel, cell transitions).
4. Whether JsonUtil reads from the profile's data mod path under MO2's VFS or
   needs the file inside a mod folder; the install tool will place it where the
   VFS probe proves it is read.
