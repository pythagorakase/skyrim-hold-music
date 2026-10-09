# Hold Music game package (T1)

Offline-built Skyrim VR package: an ESL-flagged `HoldMusic.esp`, three compiled
Papyrus scripts, 24 positional sound slots, and an MCM Helper menu. **Nothing
was installed or run in-game.** No WAV is bundled, and the VFS probe was not run.
See [dated verification](../docs/game-package-verification.md) for evidence.

## Build

Author on macOS; build only on halcyon under `C:\MGO\hm-scratch\t1b`:

First create `C:\MGO\hm-scratch\t1b`, `hold_music` and `game_adapter\data`
subdirectories there using the work order's encoded PowerShell SSH recipe.
The builder imports T0's validator, so stage these read-only source copies as
siblings of `game_package` (all remote writes remain inside T1b):

```sh
scp -o BatchMode=yes hold_music/__init__.py hold_music/registry.py hold_music/repertoire.py 'halcyon:C:/MGO/hm-scratch/t1b/hold_music/'
scp -o BatchMode=yes game_adapter/data/performers.json 'halcyon:C:/MGO/hm-scratch/t1b/game_adapter/data/'
scp -r -o BatchMode=yes game_package 'halcyon:C:/MGO/hm-scratch/t1b/'
ssh -o BatchMode=yes halcyon 'cd /d C:\MGO\hm-scratch\t1b && py -3 -B game_package\tools\build_game_package.py'
scp -r -o BatchMode=yes 'halcyon:C:/MGO/hm-scratch/t1b/game_package/build' game_package/
.venv/bin/python -m unittest discover -s game_package/tests -v
.venv/bin/python -m unittest discover -s tests -v
```

The script enforces its Windows scratch root, uses installed Caprica 0.3.0,
Champollion, .NET 9 and cached Mutagen.Bethesda.Skyrim 0.51.5 dependencies. It
redirects temporary files, .NET state and NuGet caches into the scratch root;
NuGet sources are disabled. There are no dependency installations on macOS.
Build output, imports, dependency provenance, logs, disassembly and hashes go
under ignored `build/`. The builder's `bin/` and `obj/` are also ignored.

Import resolution follows Modern Marriage's `tools/build.py`: reversed active
MO2 mod order, installed loose sources first, then decompile the winning PEX for
missing types. It seeds vanilla/SKSE, JsonUtil, StorageUtil, MiscUtil and MCM
Helper APIs. MCM Helper VR actually supplies only SKI_ConfigMenu source under
`Source/Scripts`; its MCM_ConfigBase PEX is decompiled for the import. External
imports are compile inputs only, not copied into the distributable package.
The active profile is `MGO EXP - SkyrimNet b26 + SeverActions 4.2`.

`build/package/` is the eventual Data layout. The builder emits the ESP, player
alias bindings and SEQ, validates a Mutagen serialize/read round trip, then the
build script disassembles all three PEX files and hashes every package file.
This is an offline build tool, not an installer or rollback tool.

## Install and rollback

Use the separate installer only after the adapter's in-game test and with both
MO2 and Skyrim closed. It requires the retrieved `build/package` and
`build/package-hashes.json`, this checkout's `hold_music` package and
`docs/game-package-verification.md`, and a valid T0 library with `library.json`.
No build, dependency installation, provider request or game launch is performed.

```bat
py -3 game_package\tools\install_game_package.py "C:\MGO\Skyrim MGO 4.0 RC4.1" "MGO EXP - SkyrimNet b26 + SeverActions 4.2" --library "C:\MGO\hm-scratch\t0\library" --dry-run
```

`--dry-run` validates and prints the complete JSON plan without writing anything,
including bytecode, backups or receipts; it is permitted while MO2 is open.
Remove that flag only when authorized to install after the gate above. The
default `--mod-name` is `MGO Experimental - Hold Music Performances`.
`--data-mod` defaults to `MGO Experimental - Profile Data` and is recorded as
profile context only; all package and library files go into the performance
mod. It does not edit the data mod or SkyrimNet settings.

Before changing the profile, the installer verifies every build-package hash,
requires `Library(root).validate()` to return no problems, and backs up
`modlist.txt`, `plugins.txt`, the entire existing target mod, and the newest
ESS with its matching SKSE co-save under
`C:\MGO\codex-backups\<timestamp>-hold-music-performances\`.
Like Modern Marriage, it refuses if no save exists or the newest ESS lacks its
SKSE pair; it does not silently choose an older complete pair. Saves are never
modified. Existing mod content is replaced after backup, removing stale files.

The mod receives the plugin, SEQ, compiled scripts and sources, MCM files,
registry, every manifest WAV, and copies of `library.json` and `receipts.json`.
Only a missing library-root receipts file is initialized with
`{"version": 1, "performances": []}`. It also includes version 0.1.0 metadata,
this README, and `docs/game-package-verification.md`. The installer inserts the
enabled mod directly after the first comment line (otherwise first), removes
prior entries for that mod, and appends/enables `*HoldMusic.esp` once. It preserves
the profile files' BOM, encoding and existing line endings. The installed file
hashes, manifest hash, versions, paths and backup location are recorded in
`local/game-package-install.json` at the checkout root and in the backup folder.

Rollback uses the same tool's `--uninstall` mode; no library or build is needed:

```bat
py -3 game_package\tools\install_game_package.py "C:\MGO\Skyrim MGO 4.0 RC4.1" "MGO EXP - SkyrimNet b26 + SeverActions 4.2" --uninstall
```

It disables the mod with `-<mod-name>`, removes its enabled plugin entry, and
keeps the mod folder. Add `--purge` to delete that folder, or `--dry-run` to
inspect either rollback plan. Pass the original `--mod-name` if customized.
Rollback restores nothing else: no saves, other mods, settings or backup
contents. Saves made with the plugin enabled will log a missing-plugin warning
on load, as with any removed mod.

**JsonUtil's write target under MO2 is not yet known** (design open question 4).
The receipts file may end up in
`overwrite\SKSE\Plugins\StorageUtilData\HoldMusic\` rather than the mod folder.
The VFS probe and game-side write probe must decide where the helper reads it;
the installer does not establish that location or claim runtime verification.

## Records and sound

`data/slots.json` is the shared 1..24 slot definition. Each `HM_SlotNN` SNDR has
one `Sound\fx\holdmusic\hm_slot_NN.wav`; `HM_Sound_NN` is its SOUN marker.
The player alias's `Sound[] SlotSounds` VMAD array binds the markers in order.
The installed `Sound.psc` exposes `Play(ObjectReference)` and
`GetDescriptor()`; Mutagen's SoundMarker has the SDSC descriptor reference.
Vanilla `MUSBardLute01` uses this same SOUN-to-SNDR structure. The independent
binary test verifies all 24 bindings and paths.

Output model `SOMMono02000_verb` (`Skyrim.esm:000E324B`) supplies mono 3D
positioning (its SOPM NAM1 positioning flag is set). Category
`AudioCategoryPausedDuringMenuFade` (`0009F254`) matches the vanilla bard lute
category: SFX routing, menu pause, and dialogue fade. SNDR looping is explicitly
None. These records do not replace the game's soundtrack or suppress other
bard systems. They contain no custom idles or animation objects.

The quest is `HM_Quest`, local ID `00000800`, start-game enabled and run once.
Its forced player alias (`00000014`) has HM_Controller and
SKI_PlayerLoadGameAlias; HM_Config and HM_Library bind to the quest. Globals
are enabled=1, instrumental percent=50, session cap=3, min delay=15 and max
delay=60. Mutagen removes unreferenced header masters, so the verified ESP's
only master is Skyrim.esm. The optional world-ID input uses implicit string storage, as specified by the
[MCM Helper setting documentation](https://github.com/Exit-9B/MCM-Helper/wiki/Setting-Types,-Storage,-and-Persistence).
MCM Helper and SkyUI are runtime **script**
dependencies, with no static record links requiring extra header masters.
Skyrim VR also needs its installed ESL-support and PapyrusUtil/SKSE stack.

## Registry and helper contract

`game_adapter/data/performers.json` is the only authored performer registry.
Run `python -B game_package/tools/build_registry.py` after registry changes and
review the generated `src/SKSE/Plugins/HoldMusic/registry.json`. The package
builder first checks it against a fresh derivation and fails on drift without
rewriting it. Schema version 2 retains all performers and authored plugin names,
converts hex form IDs to integers for JsonUtil, and uses flat `region`/`venue`.
Actor names are used only for explicit JSON `"form": null`; missing, malformed
or nonmatching forms never fall back. Talsgar matches by identity but is skipped
because his registry region is null. The nine hold IDs come from T0.

The helper must supply a manifest at the exact JsonUtil base-relative filename
`HoldMusic/library.json`, meaning:

```text
Data/SKSE/Plugins/StorageUtilData/HoldMusic/library.json
Data/SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json
```

Registry reads use `../HoldMusic/registry.json`, resolving to the shipped
`Data/SKSE/Plugins/HoldMusic/registry.json`. Under MO2, these virtual Data paths
must resolve to the intended profile data mod or overwrite. Their physical
read/write locations have **not** been established. The helper must not place
library.json beside the registry and assume JsonUtil will find it.

The manifest is T0's [library format](../docs/library-format.md):
`{"version":1,"slots":24,"recordings":[...]}`. Each recording has top-level
`slot`, `performer_id`, `region`, `mode`, `duration_seconds`, and `composition_id`
plus the helper's asset/provenance metadata. A compiled-VM test selects a real
`Library.add_recording` manifest built with a tiny standard-library WAV.

Duration must describe the actual WAV; slot numbers are integers 1..24. The
helper supplies mono PCM WAVs at the fixed sound paths. It may include lyrics
hashes and generation receipts as additional metadata. Selection uses matching
performer and registry-venue region, excludes locked slots, prefers compositions
with no receipt, then the least recent receipt (append order). The requested
vocal/instrumental mode breaks equally recent ties; `wordless` is a sung mode
and receives the same preference as `vocal`. Interrupted attempts also
count as performed. The game never generates music or calls a provider.

The game owns appending `receipts.json`; the helper reads it. Initial contents
are `{"version":1,"performances":[]}`. Each append contains exactly:

```json
{"id":"1:0","slot":1,"performer_id":"mikael","region":"whiterun",
 "composition_id":"unique-composition-id","save_id":"20:PlayerName:42.0",
 "world_id":"","at_hours":1008.0,"outcome":"completed",
 "started_real_seconds":123.0}
```

`id` combines slot and zero-based append index. `at_hours` is game days from
Utility.GetCurrentGameTime multiplied by 24; Papyrus has no wall clock.
Outcomes are completed or interrupted. The helper accepts optional `written_at`
provenance but locks receipts by index: `Library(root, session_receipt_index=N)`
reserves every receipt slot at index >= N. Capture N as the receipt count when
the game process starts, not when loading another save.

`save_id` combines the player reference FormID, actor-base name and game day of
first receipt, then persists on HM_Library. It approximates a save lineage,
not an ESS filename or globally unique character. An optional MCM world ID
may be empty; branched saves can share the fallback.
JsonUtil.Save is called explicitly after each receipt; a failed save traces an
error. Real JsonUtil serialization, concurrent helper reads and file failures
still need integration validation.

## Lifecycle and persistence

Entering an inn schedules a single randomized check. MiscUtil scans loaded
NPCs within 2000 units. Eligibility requires 3D loaded, alive, outside combat
and player dialogue, outside CurrentFollowerFaction, GetSitState=0 and
GetSleepState=0. This conservatively rejects all sitting/furniture transitions
and sleep transitions; it does not inspect the full AI package graph or prove
that another mod does not own an actor's animation.

Successful lute idle starts precede positional sound playback. The controller
stores performer, venue, slot, instance, real start/end times and count; polls
at most two seconds apart; and uses the remaining duration for the last update.
This implements the duration deadline without registering competing finish and
poll updates. Completion stops audio and idle, appends a receipt, then schedules
another check within the cap. Dialogue, combat, death, furniture/sleep, loss of
3D, changed cell/location, disable and MCM stop interrupt. Leaving cancels the
pending check. No ongoing polling occurs after an unsuccessful idle check.
MCM stop while idle inhibits the pending check until a fresh inn entry.

The session cap counts starts (including later interruptions), resets on
OnPlayerLoadGame, and permits only one active performer. Performer cooldowns
are 1800 real seconds from start. Controller/library state is ordinary saved
Papyrus variables/properties. On loading mid-performance, cleanup stops the
stored instance and idle and appends interrupted; it does not resume the song
or immediately schedule another. Existing cooldowns conservatively restart at
1800 seconds because process real-clock timestamps are not portable across
relaunches. Repeated loading can therefore extend a cooldown.

Used-slot locks survive save loads within the process because cached WAV
buffers can survive an ESS load. On OnPlayerLoadGame, a real clock smaller than
stored LastRealTime clears all locks: an engine-cached WAV buffer can only
survive within one process. LastRealTime updates on every load and performance
start. If a relaunched process clock has already overtaken the stored value,
this comparison conservatively retains locks; it is not a unique process ID.
The helper's session receipt boundary must likewise represent a process start.

Tests skip with a build command when PEX/disassembly or ESP/SEQ artifacts are
absent, so a fresh checkout is green; missing artifacts are not verification.

## Verification boundaries and later VFS probe

The PEX VM is adapted from Modern Marriage's test interpreter. It executes
Champollion disassembly of the compiled PEX and fails unknown opcodes/native
calls; game APIs and JsonUtil are deterministic mocks. Binary ESP parsing is
independent of Mutagen, including complete VMAD object-array contents, record
counts/flags, file paths, globals, SEQ and source/package hashes. These tests
do not emulate Skyrim's scheduler, native JSON implementation, animation graph,
VR controls, sound cache or MO2 injection.

**Do not run the probe as part of this work order.** Later, the orchestrator can
configure a console Python executable in MO2 and launch it with:

```text
C:\MGO\hm-scratch\t1b\game_package\tools\probe_vfs.py --data-root <SkyrimVR-Data> --manifest C:\MGO\hm-scratch\t1b\game_package\build\package-hashes.json
```

The probe does not launch anything, install anything or write files. It reads
package files, slot WAVs and both JsonUtil files through its inherited VFS,
emits SHA256 hashes and Windows file-handle destinations, and returns nonzero
for missing files/hash mismatches. The orchestrator must confirm the process
was actually launched through the intended MO2 profile and compare destinations
to the intended winning mod/overwrite. Identical hashes alone do not identify
a winner. This read-only probe cannot prove JsonUtil's eventual write target;
that remains a separate orchestrated game-side receipt test.

Still unverified: race-specific lute attachment/idle stop, coexistence with
vanilla/SkyrimNet bard activity, audible positioning, long-WAV memory behavior,
menu timing versus paused audio, interruptions in VR, MCM rendering/callbacks,
load-game native sound handles, receipt persistence, VFS winners and headset
playback. No claim of installation readiness or headset acceptance is made.

Authored by Codex, running GPT-6.
