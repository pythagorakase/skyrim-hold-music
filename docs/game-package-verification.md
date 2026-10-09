# Game package offline verification — 2026-10-09

T1 was authored in the supplied worktree and built on halcyon under
`C:\MGO\hm-scratch\t1\game_package`. No git commands were run; changes are
left dirty for review. No Mac dependencies were installed. No paid requests
were made. No protected source directory or existing test was edited.

**Nothing was installed or run in-game.** ModOrganizer, SkyrimVR and MO2
shortcuts were not launched. The active installation was read only. The VFS
probe was written but not executed. All directed writes on halcyon were under
`C:\MGO\hm-scratch\t1`. The build also redirects its temporary/.NET/NuGet
state there and uses copies of already-cached package dependencies.

## Compiled and built

- Caprica 0.3.0 compiled HM_Config.psc, HM_Controller.psc and HM_Library.psc;
  final compile logs contain zero warnings and zero errors.
- Installed flags, vanilla/SKSE/PapyrusUtil imports and decompiled installed
  MCM_Helper base were used; build/dependencies.json identifies resolved imports.
- .NET 9 / Mutagen.Bethesda.Skyrim 0.51.5 emitted a 6,259-byte ESL-flagged
  HoldMusic.esp: one quest, five globals, 24 SNDR descriptors and 24 SOUN markers.
- Mutagen's serialize/read round trip passed. Actual header master: Skyrim.esm.
  MCM Helper/SkyUI are runtime script dependencies; unused explicit header
  masters were removed by Mutagen. No static links require their plugin records.
- SEQ contains file-relative quest ID 01000800 (bytes 00 08 00 01).
- Champollion disassembled all three PEX products to build/disassembly/*.pas.
- build/package-hashes.json contains SHA256 hashes for all 12 package files.
  Source copies match current src/ byte for byte. No slot WAVs are included.

## Tests and proof tails

Compiled-instruction VM: inn/non-inn entry, no performer, correct idle/sound,
duration/completed receipt, dialogue and all coarse interruptions, eligibility,
cap, disabled state, load cleanup, preserved slot locks, performer cooldown,
selection history, registry null fallback, config settings and world ID.
Native calls are deterministic mocks; these are not game execution tests.

Independent ESP parser: header ESL/master/counts, complete quest/alias VMAD
bindings and sound array, every descriptor/marker/path/category/output model,
no looping, global defaults, SEQ bytes and all package/source hashes.

Halcyon build log (complete short final log):

```text
Compiled: HM_Config
Compiled: HM_Controller
Compiled: HM_Library
{
  "path": "C:\\MGO\\hm-scratch\\t1\\game_package\\build\\package\\HoldMusic.esp",
  "bytes": 6259,
  "esl": true,
  "quests": 1,
  "globals": 5,
  "descriptors": 24,
  "markers": 24,
  "questFileId": "01000800",
  "masters": [
    "Skyrim.esm"
  ],
  "validation": "Mutagen serialize/read round-trip passed"
}
Disassembled: HM_Config.pex
Disassembled: HM_Controller.pex
Disassembled: HM_Library.pex
Build ready: C:\MGO\hm-scratch\t1\game_package\build\package; 12 hashed files. Nothing installed or launched.
```

`/Users/pythagor/hold_music/.venv/bin/python -m unittest discover -s game_package/tests -v`:

```text
test_globals_and_seq (test_plugin.PluginTests.test_globals_and_seq) ... ok
test_hashes_and_compiled_sources_match (test_plugin.PluginTests.test_hashes_and_compiled_sources_match) ... ok
test_quest_alias_scripts_and_every_property (test_plugin.PluginTests.test_quest_alias_scripts_and_every_property) ... ok
test_sound_paths_markers_category_3d_and_no_loop (test_plugin.PluginTests.test_sound_paths_markers_category_3d_and_no_loop) ... ok

----------------------------------------------------------------------
Ran 20 tests in 0.047s

OK
```

`/Users/pythagor/hold_music/.venv/bin/python -m unittest discover -s tests -v`:

```text
test_saved_takes_without_new_lyric_metadata_remain_readable (test_workshop_server.WorkshopHTTPTests.test_saved_takes_without_new_lyric_metadata_remain_readable) ... ok
test_status_is_read_only_and_does_not_expose_key (test_workshop_server.WorkshopHTTPTests.test_status_is_read_only_and_does_not_expose_key) ... ok
test_success_hides_previous_failure_from_status_after_reload (test_workshop_server.WorkshopHTTPTests.test_success_hides_previous_failure_from_status_after_reload) ... ok
test_sung_takes_without_saved_lyrics_work_without_reading_catalog (test_workshop_server.WorkshopHTTPTests.test_sung_takes_without_saved_lyrics_work_without_reading_catalog) ... ok

----------------------------------------------------------------------
Ran 150 tests in 10.499s

OK (skipped=1)
```

The existing suite initially passed 147 tests with one skip; with three new
source-contract tests, the final suite passes 150 with that same skip. Full
logs are retained under ignored game_package/build/.

## Resolved forms

All below originate in Skyrim.esm. Record identity and editor IDs were read
from the supplied roster cache; sound records were additionally read directly
from Skyrim.esm using the supplied parser. The full inspected catalog,
including additional candidate/reference sound records, is in
[forms.json](../game_package/data/forms.json). No form identity was guessed.

| Editor ID | Local FormID | Record |
|---|---|---|
| IdleLuteStart | 00096F8D | IDLE |
| IdleStop | 000E4242 | IDLE |
| AnimObjectLute | 00093643 | ANIO |
| IdleFluteStart (reference only) | 00096F8C | IDLE |
| LocTypeInn | 0001CB87 | KYWD |
| JobBardFaction | 00053514 | FACT |
| BardSingerFaction | 000CF8F9 | FACT |
| CurrentFollowerFaction | 0005C84E | FACT |
| Mikael | 0001A670 | NPC_ |
| Sven | 0001347F | NPC_ |
| AudioCategoryPausedDuringMenuFade | 0009F254 | SNCT |
| SOMMono02000_verb | 000E324B | SOPM |
| MUSBardLute01 (reference only) | 0010E444 | SOUN |
| MUSBardLute01SD (reference only) | 0010E440 | SNDR |

The cache contains IdleLuteStart and IdleStop; no separate vanilla lute-loop
record was found. Whether the start's animation graph loops and attaches the
lute properly on each race remains a headset check. The forced alias uses the
work order's explicit engine player reference 00000014; that special reference
is not present in the supplied cached ACHR records and is not claimed as a
newly resolved editor ID.

## Outstanding integration and headset questions

1. T0's performers.json and library-format.md were absent. The allowed minimal
   registry and documented provisional receipt/manifest shape were used. T0
   must reconcile this schema and write the exact StorageUtilData paths.
2. Slot locks survive save/load, conservatively protecting against retained
   audio buffers. This can exhaust 24 slots for a save lineage. There is no
   cache-safe unlock protocol in T1; it needs integration review before long
   running use. Session counts still reset on load as required.
3. save_id is a persisted player/name/game-day fallback; it is not an ESS name
   or globally unique identity. MCM world ID can disambiguate worlds. Cooldowns
   restart conservatively on load because the real clock is process-relative.
4. The unrun probe can establish observed file-handle destinations/hashes in a
   correctly injected MO2 process. It cannot prove actual JsonUtil writes or
   native null/path/array serialization; those require an orchestrated receipt
   test. Native file errors are traced, not retried transactionally.
5. Lute attachment/stop on each race, coexistence with other bard systems,
   sound positioning/long-WAV memory, VR dialogue/travel/menu interruption and
   cleanup of saved sound handles have no in-game evidence.
6. Audio category pause versus real-clock deadlines and Papyrus event
   scheduling still require runtime testing. MCM layout/callbacks have compiled
   scripts and config checks, not rendered UI verification.

No confirmed requirement/toolchain conflict produced a stop-report. These
limits are explicitly unverified gates, not evidence of in-game acceptance.
See the [README](../game_package/README.md) for the full operational contract.

## Files changed (one line each)

- `.gitignore` — Ignore offline build output and .NET intermediates.
- `docs/game-package-verification.md` — Record dated offline evidence, boundaries and file inventory.
- `docs/performance-ownership-design.md` — Add the T1 README link.
- `game_package/README.md` — Document build, state lifecycle, provisional helper schema and unverified gates.
- `game_package/data/forms.json` — Record resolved editor IDs, form IDs, types and audit provenance.
- `game_package/data/slots.json` — Define all 24 descriptor/marker/path mappings.
- `game_package/src/SKSE/Plugins/HoldMusic/registry.json` — Provide resolved minimal Mikael/Sven registry.
- `game_package/src/Scripts/Source/HM_Config.psc` — Implement MCM settings, world ID and stop flag.
- `game_package/src/Scripts/Source/HM_Controller.psc` — Implement alias triggers, eligibility, playback, polling, cap and cleanup.
- `game_package/src/Scripts/Source/HM_Library.psc` — Implement registry matching, selection, slot locks and JsonUtil receipts.
- `game_package/src/Sound/fx/holdmusic/README.txt` — Explain helper-supplied slot WAVs.
- `game_package/src/mcm/config/HoldMusic/config.json` — Define MCM Helper controls.
- `game_package/src/mcm/config/HoldMusic/settings.ini` — Provide required ModSettings defaults.
- `game_package/tests/pex_vm.py` — Adapt Modern Marriage compiled-instruction interpreter and native mocks.
- `game_package/tests/test_controller.py` — Exercise compiled controller, bridge and config behavior.
- `game_package/tests/test_plugin.py` — Independently parse ESP/VMAD/SEQ and verify package hashes.
- `game_package/tools/PluginBuilder/NuGet.Config` — Disable remote NuGet package sources.
- `game_package/tools/PluginBuilder/PluginBuilder.csproj` — Pin .NET 9 and Mutagen Skyrim 0.51.5.
- `game_package/tools/PluginBuilder/Program.cs` — Build and round-trip-check the ESP and write SEQ.
- `game_package/tools/build_game_package.py` — Compile, resolve imports, build, disassemble and hash within scratch.
- `game_package/tools/probe_vfs.py` — Provide a later read-only MO2 file-handle/hash probe; not executed.
- `tests/test_game_package_sources.py` — Add portable source, config, form and shared-slot checks.

Ignored artifacts: game_package/build/ contains PEX, PAS, ESP, SEQ, compile/
disassembly/build/validation logs, dependency provenance, test logs and hashes.
The remote scratch copy is retained for review; no install/profile operation
was performed.

Authored by Codex, running GPT-6.
