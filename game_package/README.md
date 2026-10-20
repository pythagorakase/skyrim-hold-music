# Hold Music game package (T1)

Offline-built Skyrim VR package: an ESL-flagged `HoldMusic.esp`, three compiled
Papyrus scripts, 24 positional sound slots, and an MCM Helper menu. The pilot
was installed on Halcyon on October 13; the targeted actor-scan workaround was
installed and VFS-verified on October 15. Successful owned playback after that
fix still requires the [runtime test](../docs/in-game-test-plan.md). See the
[crash RCA and repair](../docs/sven-crash-2026-10-15.md) and the historical
[package verification](../docs/game-package-verification.md) for their distinct
evidence. No WAV is bundled in Git; generated builds and recordings remain
separate machine-local artifacts.

## Build

Author on either host; compile with the installed Windows Caprica, Champollion,
.NET 9 and cached Mutagen.Bethesda.Skyrim 0.51.5 dependencies. The builder now
takes explicit stack and toolchain paths. It defaults to a **read-only plan**;
`--build` compiles into a fresh, empty workspace and never installs anything.
The historical RC4.1 paths below are one concrete example, not built-in defaults:

```powershell
$buildArgs = @(
  '--workspace', 'C:\MGO\HoldMusic\local\package-build-example',
  '--mo2-root', 'C:\MGO\Skyrim MGO 4.0 RC4.1',
  '--profile', 'MGO EXP - SkyrimNet b26 + SeverActions 4.2',
  '--compiler', 'C:\MGO\character-work\tools\caprica-0.3.0\Caprica.exe',
  '--flags', 'C:\MGO\character-work\flatrim-test\script-source\TESV_Papyrus_Flags.flg',
  '--decompiler', 'C:\MGO\codex-investigations\20261002-companions-hostility\decompiler\Champollion.exe',
  '--vanilla-imports', 'C:\MGO\codex-investigations\20261006-ostimnet-spouse-guard\compile-imports',
  '--vanilla-pex', 'C:\MGO\codex-investigations\20261006-ostimnet-spouse-guard\vanilla-pex',
  '--dependency-assets', 'C:\MGO\ModernMarriage\tools\PluginBuilder\obj\project.assets.json'
)
python -B game_package/tools/build_game_package.py @buildArgs --dry-run
python -B game_package/tools/build_game_package.py @buildArgs --build
$env:HOLD_MUSIC_TEST_BUILD = 'C:\MGO\HoldMusic\local\package-build-example\build'
python -B -m unittest discover -s game_package/tests -v
Remove-Item Env:\HOLD_MUSIC_TEST_BUILD
```

`--dotnet` can override the executable found on PATH. The workspace must not
overlap installed game files, compiler imports, package caches or authored
package inputs. A nonempty workspace is refused, so a new build cannot mix
stale outputs into the package. No source checkout staging is needed.

Temporary files, .NET state, offline package caches and a copy of the C#
builder all stay in the workspace. NuGet sources and vulnerability-audit
network queries are disabled; missing cached dependencies fail the build.
`build/` contains the package, imports, logs, disassembly, input plan, package
hashes and a build receipt identifying the stack, source and toolchain hashes.
The receipt does not establish installation or runtime compatibility.
The checkout's existing `game_package/build` is left intact. Tests can target
the new build with `HOLD_MUSIC_TEST_BUILD`; an incomplete explicit target fails
rather than silently skipping. Without that variable, historical test behavior
and the `game_package/build` default are preserved.

Import resolution follows Modern Marriage's `tools/build.py`: reversed active
MO2 mod order, installed loose sources first, then decompile the winning PEX for
missing types. It seeds vanilla/SKSE, JsonUtil, StorageUtil, MiscUtil and MCM
Helper APIs. MCM Helper VR actually supplies only SKI_ConfigMenu source under
`Source/Scripts`; its MCM_ConfigBase PEX is decompiled for the import. External
imports are compile inputs only, not copied into the distributable package.
The profile is supplied explicitly; these import choices do not prove MO2's
runtime VFS winners.

`<workspace>/build/package/` is the eventual Data layout. The builder emits the ESP, player
alias bindings and SEQ, validates a Mutagen serialize/read round trip, then the
build script disassembles all three PEX files and hashes every package file.
This is an offline build tool, not an installer or rollback tool. The current
installer still reads the reviewed `game_package/build` location; a successful
candidate build is not automatically promoted there or installed.

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
None. These records do not replace the game's soundtrack. The controller
stops vanilla bard scenes as described below; SkyrimNet playback is separate.
They contain no custom idles or animation objects.

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
The sibling registry derivation must also supply `owner` on every performer.
Only `owner="hold_music"` is allowed to perform; absent, unknown, or
`"skyrimnet"` owners are skipped. Tests supply explicit owner-bearing fixtures;
T1e does not regenerate or edit the shipped registry.
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

## Vanilla scene lock and trace (T1e)

The alias binds `BardSongsQuest` to Skyrim.esm:00074A55 and `VanillaScenes`
to the 16 single-bard scenes in the frozen order recorded in the dated proof.
Before starting the lute idle it casts the quest to `BardSongsScript` and calls
`StopAllSongs()`. Every performance poll checks all 16 scenes; a playing scene
causes another stop and lute-start idle, without changing our sound instance.
A failed cast emits `vanilla_unavailable` and permits our performance to proceed.
Poll timing stays at most two seconds. This does not stop SkyrimNet audio.

`imports/BardSongsScript.psc` is a hand-written compile-time type stub only.
Caprica imports it to compile the cast and call; the builder compiles only
`src/Scripts/Source/*.psc`, copies only `src/` into the package, and rejects any
BardSongsScript file in the resulting package before hashing. Never ship the stub.

`HM_Library.Trace` saves `HoldMusic/trace.json` after every entry using
`JsonUtil.Save(TraceFile, False)`. Its virtual path is
`Data/SKSE/Plugins/StorageUtilData/HoldMusic/trace.json`; the physical MO2 write
target still requires game-side verification. It does not require Papyrus logging.
The shape is `{"version":1,"entries":[{"seq":1,"real_seconds":100.0,
"game_hours":1008.0,"event":"disabled","detail":""}]}`. Sequence numbers are
kept in the script and reconciled with the final on-disk entry after save loads.
At 300 entries, `JsonUtil.ClearPath(TraceFile, ".entries")` clears the path,
`SetRawPathValue(..., "[]")` initializes the empty array, and `trace_rolled`
with `dropped=300` is saved before the triggering entry. Save failure falls
back to one `Debug.Trace` warning per library session reset; that warning is
not evidence when Papyrus logging is disabled.

Events are frozen: `location_enter`, `location_leave`, `check_start`,
`candidate`, `no_performer`, `slot_chosen`, `vanilla_stopped`,
`vanilla_unavailable`, `vanilla_restarted`, `idle_failed`, `performance_start`,
`performance_stop`, `receipt_failed`, `session_cap`, `disabled`, `trace_rolled`.
There is no load event. `location_enter` and `location_leave` fire only for
locations with `LocTypeInn`, so ordinary travel cannot fill the ring. Details contain only field names, ids, numeric values,
booleans and outcome/mode words; actor names and dialogue are not logged.
Each matched candidate gets one line, even when ineligible or unowned; unknown
owners are reported as `owner=skyrimnet`, and absent regions as `region=none`.
`scanned` counts actors visited and `matched` counts registry matches when a
check ends without a performance. `slot_chosen` reports the requested mode,
which can differ from the selected recording's fallback mode.

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
C:\MGO\HoldMusic\game_package\tools\probe_vfs.py --data-root <SkyrimVR-Data> --manifest C:\MGO\HoldMusic\game_package\build\package-hashes.json --profile "MGO EXP - SkyrimNet b26 + SeverActions 4.2"
```

Run the probe from the current checkout: it imports the strict configuration
scalar reader from `game_adapter/hold_music_adapter/engine.py` and its sibling
modules. It uses only Python's standard library and needs no provider access.
Use the manifest for the exact package being checked.

The probe does not launch anything, install anything or write files. It reads
package files, slot WAVs, both JsonUtil files and SkyrimNet's `BardSinging.yaml`
through its inherited VFS, emits SHA256 hashes and Windows file-handle
destinations, and returns nonzero for missing files/hash mismatches or malformed
bard settings. The config row includes only the parsed `bard_enabled` flag,
never provider credentials. The orchestrator must confirm the process
was actually launched through the intended MO2 profile and compare destinations
to the intended winning mod/overwrite. Identical hashes alone do not identify
a winner. This read-only probe cannot prove JsonUtil's eventual write target;
that remains a separate orchestrated game-side receipt test.
Pass the captured report to `tools/preflight_performance.py --vfs-report` for
profile/destination/hash checks. See the [reversible ownership handoff](../docs/performance-ownership-design.md#offline-handoff-and-vfs-evidence-20-october-2026)
for safe preparation and rollback of conflicting launch inputs.

Still unverified: race-specific lute attachment/idle stop, coexistence with
vanilla/SkyrimNet bard activity, audible positioning, long-WAV memory behavior,
menu timing versus paused audio, interruptions in VR, MCM rendering/callbacks,
load-game native sound handles, receipt persistence, VFS winners and headset
playback. No claim of installation readiness or headset acceptance is made.

Authored by Codex, running GPT-6.
