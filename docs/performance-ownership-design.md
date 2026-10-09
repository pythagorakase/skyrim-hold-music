# Hold Music owns performances: design

**Status:** design, 9 October 2026. Nothing below is installed or enabled.
**Decision owner:** recorded here by Claude under the delegated takeover; the
user's standing direction is that Hold Music should eventually take over the
bard functions entirely from SkyrimNet.

## Why take over

Evidence gathered on 9 October:

- SkyrimNet's bard code is closed (the C++ repository is private). Its bard
  eligibility check is undocumented; on this install it accepts the Bard class
  or `BardSingerFaction`, which excludes real performers such as Sven in
  Riverwood (Lumberjack class, `JobBardFaction` only) and Lynly in Ivarstead.
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

While the owned path is being validated, the 0.2.x adapter stays installed and
SkyrimNet's bard singing stays on. The config overlay already managed by the
MO2 plugin gains one more managed scalar, `bard_singing.enabled`, so switching
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

T0 and T1 are independent of each other and can be built in parallel; T2
depends on T0; T3 depends on T1 and T2 passing their headset gates.

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
- **Ahead-of-time generation.** A performance must never wait on a paid
  request; if no recording fits, the bard does not perform and the helper
  queues work for next time.
- **Mono WAV.** Larger than xWMA but encoder-free and correct for a 3D source.

## Open questions to settle during T1

1. Exact form identities of the lute start/stop idles and whether the idle
   alone attaches the lute animation object for every performer race.
2. Whether a sound descriptor can play a 2-3 minute WAV without the engine's
   memory budget complaining; if not, cap recordings at 150 seconds in the
   prompt and trim in ffmpeg.
3. The right interruption set in VR (menus, fast travel, cell transitions).
4. Whether JsonUtil reads from the profile's data mod path under MO2's VFS or
   needs the file inside a mod folder; the install tool will place it where the
   VFS probe proves it is read.
