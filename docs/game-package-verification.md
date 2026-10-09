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

`.venv/bin/python -m unittest discover -s game_package/tests -v`:

```text
test_globals_and_seq (test_plugin.PluginTests.test_globals_and_seq) ... ok
test_hashes_and_compiled_sources_match (test_plugin.PluginTests.test_hashes_and_compiled_sources_match) ... ok
test_quest_alias_scripts_and_every_property (test_plugin.PluginTests.test_quest_alias_scripts_and_every_property) ... ok
test_sound_paths_markers_category_3d_and_no_loop (test_plugin.PluginTests.test_sound_paths_markers_category_3d_and_no_loop) ... ok

----------------------------------------------------------------------
Ran 20 tests in 0.047s

OK
```

`.venv/bin/python -m unittest discover -s tests -v`:

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

## T1b reconciliation — 2026-10-09

This section supersedes T1's provisional-contract and permanent-lock gates above.
The full T0 registry is now derived through `hold_music.registry.load_registry`;
all 21 identities, including HearthFires.esm performers, are preserved. The
integer-ID projection has schema version 2 and flat region/venue fields.
The build fails if the tracked projection differs from a fresh derivation.
Talsgar matches by base form but is skipped because his region is null.

The game and helper now share version 1 `performances` receipts: slot/index ID,
game hours, completed/interrupted outcome, and process-local start time, without
a wall-clock requirement. The helper accepts optional written_at provenance
and empty MCM world IDs; session locks use original array indices >= N.
Compiled ChooseSlot selects real helper-produced manifests (tiny wave-module
WAVs), including wordless as sung preference. The same test reads compiled
AppendReceipt output through the Python library and verifies the exact key set.
Both load-clock branches are exercised: smaller clears all locks; equal/larger
preserves locks. Loads and successful performance starts update LastRealTime.

All remote writes were directed under `C:\MGO\hm-scratch\t1b\`.
The staged validator, package initializer, repertoire module and authored
performers file were unchanged copies needed by the new build-time import.
The existing installation/toolchain was read only. Cached dependencies were
copied into scratch with NuGet sources disabled. SSH/SCP used only `halcyon`;
no internet/provider calls or dependency downloads/installations were made.
No MO2, SkyrimVR, shortcut, VFS probe or profile installation was launched.
Build artifacts were copied back to ignored `game_package/build/`.

### Build log tail

Caprica compiled all three sources; Mutagen's ESP round trip passed;
Champollion disassembled the resulting PEX. The complete short build log is:

```text
Compiled: HM_Config
Compiled: HM_Controller
Compiled: HM_Library
{
  "path": "C:\\MGO\\hm-scratch\\t1b\\game_package\\build\\package\\HoldMusic.esp",
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
Build ready: C:\MGO\hm-scratch\t1b\game_package\build\package; 12 hashed files. Nothing installed or launched.
```

### Unpiped unittest commands and tails

`.venv/bin/python -m unittest discover -s tests -v`:

```text
test_saved_takes_without_new_lyric_metadata_remain_readable (test_workshop_server.WorkshopHTTPTests.test_saved_takes_without_new_lyric_metadata_remain_readable) ... ok
test_status_is_read_only_and_does_not_expose_key (test_workshop_server.WorkshopHTTPTests.test_status_is_read_only_and_does_not_expose_key) ... ok
test_success_hides_previous_failure_from_status_after_reload (test_workshop_server.WorkshopHTTPTests.test_success_hides_previous_failure_from_status_after_reload) ... ok
test_sung_takes_without_saved_lyrics_work_without_reading_catalog (test_workshop_server.WorkshopHTTPTests.test_sung_takes_without_saved_lyrics_work_without_reading_catalog) ... ok

----------------------------------------------------------------------
Ran 207 tests in 18.427s

OK (skipped=1)
```

`.venv/bin/python -m unittest discover -s game_package/tests -v`:

```text
test_globals_and_seq (test_plugin.PluginTests.test_globals_and_seq) ... ok
test_hashes_and_compiled_sources_match (test_plugin.PluginTests.test_hashes_and_compiled_sources_match) ... ok
test_quest_alias_scripts_and_every_property (test_plugin.PluginTests.test_quest_alias_scripts_and_every_property) ... ok
test_sound_paths_markers_category_3d_and_no_loop (test_plugin.PluginTests.test_sound_paths_markers_category_3d_and_no_loop) ... ok

----------------------------------------------------------------------
Ran 24 tests in 0.071s

OK
```

The full repository suite's single skip is the existing Windows embedded-interpreter
regression. The rebuilt package suite has no skips. Separately, temporarily moving
`build/` out of the way and restoring it in a finally block produced:

```text
Ran 15 tests in 0.002s

OK (skipped=29)
```

Those are missing-artifact skips (including subtests and class setup), each with
the build command and README staging/copy-back pointer. They establish clean
fresh-checkout discovery, not compiled behavior. That log and the two final
run tails are retained as `build/t1b-*-tests*.log`.

### Adapted existing assertions and fixtures

1. `test_resolved_form_ids`: replace the two-entry `forms.json` performer lookup with full T0 derivation equality, exact authored plugin/integer-ID checks, performer count, allowed regions, and byte-for-byte drift check. Existing audited form assertions remain.
2. Recording-library receipt fixture: `id='1:0'`, `region` and `started_real_seconds` replace the arbitrary ID/required `written_at`; existing receipt-driven tests now run without wall time.
3. `test_receipt_outcomes_scope_and_unknown_keys`: valid outcomes are completed/interrupted only; the old failed/playable case is replaced by a new malformed-outcome assertion rejecting failed.
4. `test_session_locks_survive_other_scopes_and_failed_outcomes` becomes `...interrupted_outcomes`: interrupted foreign-save receipts lock at index 0, then boundary 1 unlocks the previous receipt. WAV-preservation and replacement assertions remain.
5. `test_receipt_reserves_a_slot_even_when_manifest_entry_is_absent`: index 0 replaces its wall-clock boundary; the orphan-slot reservation assertions remain.
6. `test_replacement_requires_boundary_and_removes_old_lyrics`: expect `session_receipt_index` in the missing-boundary error and supply index 0 for safe replacement; sidecar/planner assertions remain.
7. `test_atomic_manifest_failure_restores_assets_and_cleans_temps`: supply index 0 instead of a timestamp; exact rollback assertions remain.
8. Compiled `test_registry_null_fallback_and_malformed_form_rejection`: select Mikael by ID rather than row 0; all explicit-null/malformed/mismatched-form assertions remain.

### Files changed

- `game_package/tools/build_registry.py` — Validate T0 input and derive/check the integer-ID game registry.
- `game_package/tools/build_game_package.py` — Check registry first and confine builds to T1b scratch.
- `game_package/src/SKSE/Plugins/HoldMusic/registry.json` — Regenerate all 21 performers with flat region/venue and original plugin identities.
- `game_package/src/Scripts/Source/HM_Library.psc` — Read flat regions, prefer wordless as sung, and write/read the unified receipts contract.
- `game_package/src/Scripts/Source/HM_Controller.psc` — Skip regionless performers and reset locks when the process clock rolls back.
- `hold_music/library.py` — Accept clockless game receipts and lock slots by original receipt-array index.
- `game_package/tests/pex_vm.py` — Skip missing compiled artifacts, support multiplication, and model typed JsonUtil defaults.
- `game_package/tests/test_controller.py` — Locate the Mikael fixture by stable ID in the complete registry.
- `game_package/tests/test_plugin.py` — Skip absent build artifacts before binary parsing.
- `game_package/tests/test_library_contract.py` — Exercise helper/compiled-VM interoperability, regionless skip and both clock branches.
- `tests/test_game_package_sources.py` — Check full derivation, allowed regions, plugin identities and drift rejection.
- `tests/test_recording_library.py` — Adapt session/receipt assertions and extend validation/boundary coverage.
- `docs/library-format.md` — Document the single receipt contract and index boundary API.
- `game_package/README.md` — Document T1b staging, derived data, unified contract and process-cache rationale.
- `docs/performance-ownership-design.md` — Add one inline sentence to open question 2 about process-local cache locks.
- `docs/game-package-verification.md` — Record this dated T1b evidence and remaining gates.

### Still unverified

Real JsonUtil null/path/array serialization, file writes and concurrent helper
reads, MO2 VFS winners/write targets, native engine cache behavior, saved sound
handles, animation attachment/stop, coexistence with other bard systems, audible
positioning, long WAV memory behavior, menu/audio timing, VR interruption and
MCM callbacks still need integration/headset verification. The specified clock
comparison conservatively retains locks if a restarted process has already
passed the saved LastRealTime. It does not identify a process uniquely.
No in-game claims are made.

The initial no-network/SSH conflict was explicitly resolved by the user's
follow-up. No new stop-report items. No git commands or index/commit changes;
the tree remains dirty, including the regenerated tracked registry for review.
A filesystem hash inventory confirmed all source changes are on the allowlist.

Authored by Codex, running GPT-6.

## T1c — Installer and rollback verification — 2026-10-09

Implemented `game_package/tools/install_game_package.py` with `--uninstall`
and optional `--purge`; no separate uninstaller is needed. Nothing was installed
on Halcyon and no MO2/game/window was launched. All remote staging writes stayed
under `C:\MGO\hm-scratch\t1c\`. No git commands, dependency installations,
internet requests or provider calls were made; the worktree remains dirty.

### Implementation and proof

- Validates the profile, complete built-package inventory and SHA256 hashes, and
  the T0 library before writing. Normal install/uninstall uses the adapter's
  CSV `tasklist` guard. Dry runs bypass only that process guard and write nothing,
  including Python bytecode.
- Read `C:\MGO\ModernMarriage\tools\install_local.py` over SSH. Matched its
  newest-ESS selection and mandatory matching SKSE co-save. Backups also preserve
  both profile lists and the complete previous target mod, including empty
  directories, before replacement.
- Installs the package, WAVs, JsonUtil data, metadata and documentation. Copies
  existing library receipts verbatim or initializes them only when absent.
  Records every installed file's hash plus manifest hash, versions, paths and
  backups in both receipt destinations.
- Preserves BOM, encoding and existing newlines; enables the mod immediately
  after the leading comment and enables the ESP once. Uninstall disables the
  mod, removes its enabled ESP entry, optionally purges the mod, and restores
  nothing else.
- Eleven new tests use temporary MO2 trees, actual copied build artifacts,
  two fake save pairs, and WAV-generated libraries made through
  `Library.add_recording`. They cover write-free plans, every installed hash,
  newest-pair backup, existing-mod backup, receipts, repeat installs, BOM/CRLF
  and other supported encodings/newlines, invalid inputs, process refusal,
  restoration after a simulated install write failure, and rollback/purge.
  Missing build artifacts skip with the build and staging instructions.

Run from the worktree root with
`PYTHONDONTWRITEBYTECODE=1` to avoid creating files outside the allowlist:

```text
.venv/bin/python -m unittest discover -s game_package/tests -v
Ran 35 tests in 0.251s
OK

.venv/bin/python -m unittest discover -s tests -v
Ran 207 tests in 18.482s
OK (skipped=1)
```

The repository suite's skip is the existing Windows embedded-interpreter
regression. No existing tests or fixtures were changed.

### Files changed

- `game_package/tools/install_game_package.py` — New guarded installer, JSON dry-run plan, backup/receipt handling and `--uninstall`/`--purge`.
- `game_package/tests/test_install_game_package.py` — New offline installer and rollback tests.
- `game_package/README.md` — Install/rollback instructions, save warning and unresolved JsonUtil write location.
- `docs/game-package-verification.md` — This dated T1c proof and complete Halcyon JSON plan.
- `docs/performance-ownership-design.md` — One T1c installer/rollback status line under T1.

### Halcyon dry run

Staged the worktree's `game_package/` (including `build/`) and `hold_music/`
under T1c, plus the required verification document in T1c's `docs/`.
The existing `C:\MGO\hm-scratch\t0\library` validated with no problems;
no fallback library was needed. Ran the installer with `--dry-run` against
the real root and requested experimental profile. Exit code: 0.

A read-only wrapper compared SHA256/file inventories before and after the CLI:
the two profile lists, target mod, T1c scratch and T0 library were unchanged;
the backup-directory inventory was unchanged. The dry run created neither the
proposed backup directory nor either install receipt. Its 18 planned files
include the existing T0 slot 01 WAV. The plan selects the Save263 ESS/SKSE pair,
inserts the mod at line 2, and appends the enabled ESP at line 2000.

The complete, unredacted JSON stdout follows. This is a captured plan, not an
installation receipt. Its timestamp and backup path are proposed only.
The verification-document hash refers to the staged document before appending
this report (embedding the plan necessarily changes this document's own hash).

```json
{
  "operation": "install",
  "dry_run": true,
  "version": "0.1.0",
  "root": "C:\\MGO\\Skyrim MGO 4.0 RC4.1",
  "profile": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2",
  "mod": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances",
  "data_mod": "MGO Experimental - Profile Data",
  "profile_edits": [
    {
      "path": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\modlist.txt",
      "encoding": "utf-8",
      "bom_hex": "",
      "before_sha256": "6cd32c18c40aa7b49a39b54e8f758fd62eecb7d90b417fcd4f572f86e6a14429",
      "after_sha256": "ae70f36b0704ad614be17ecd327f85171e63e8c79391873c6e321c84f55a39c8",
      "edits": [
        {
          "action": "insert",
          "line": 2,
          "text": "+MGO Experimental - Hold Music Performances",
          "newline": "\r\n"
        }
      ]
    },
    {
      "path": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\plugins.txt",
      "encoding": "utf-8",
      "bom_hex": "",
      "before_sha256": "7a28dd1bbfb4be2e95a427ee520906b15d1f256131a836e2cb44f67a7b9ba1c9",
      "after_sha256": "3a8fcb17a945fe18ddf0b5c4e8fc37e5378cef3c9f82759676874cccd990bc7c",
      "edits": [
        {
          "action": "append",
          "line": 2000,
          "text": "*HoldMusic.esp",
          "newline": "\r\n"
        }
      ]
    }
  ],
  "purge": false,
  "files": [
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\HoldMusic.esp",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\HoldMusic.esp",
      "sha256": "dc6b243f11ad4c20b648c2b87564dba9c47d85d59d6fa99bfa785d78f4af2d13"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\SEQ\\HoldMusic.seq",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\SEQ\\HoldMusic.seq",
      "sha256": "004be5580012efcdec118fce2444cf2dab6a4709d71924066ed03b59a19969de"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\SKSE\\Plugins\\HoldMusic\\registry.json",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\SKSE\\Plugins\\HoldMusic\\registry.json",
      "sha256": "367e57de35f9ef815ea28c146cc94ce4a65e7786fd1103a219df1f36297899f0"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\Scripts\\HM_Config.pex",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Scripts\\HM_Config.pex",
      "sha256": "03c3c4236819740bf2e520a65637408b9427d1f871d506280a9ab06194bd687e"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\Scripts\\HM_Controller.pex",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Scripts\\HM_Controller.pex",
      "sha256": "42751884bd1fea6b34df55e97d75a20560ef6dfca89c8eb7945880f3fe903b54"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\Scripts\\HM_Library.pex",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Scripts\\HM_Library.pex",
      "sha256": "04211cbeacd49b1353c90b9ee632b3c39af8ef9c3f363af1452d24bc5cfc12e7"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\Scripts\\Source\\HM_Config.psc",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Scripts\\Source\\HM_Config.psc",
      "sha256": "cda751f1c648b44216bfcde41db84d0b89e3754a87ae4544f3f951fb2c1b0596"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\Scripts\\Source\\HM_Controller.psc",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Scripts\\Source\\HM_Controller.psc",
      "sha256": "11f02733ee562475924089c9e8263020a6df0508f264319bbbb864ae377d7bae"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\Scripts\\Source\\HM_Library.psc",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Scripts\\Source\\HM_Library.psc",
      "sha256": "a019b0f1dc75a451c383cbe65fc22936dc52b524d9d0da8baa68d44ad349ab28"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\Sound\\fx\\holdmusic\\README.txt",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Sound\\fx\\holdmusic\\README.txt",
      "sha256": "d4d4cd81e8d94c3998028de7ae9b3a85cc52befaa409994e125bad5f53afe656"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\mcm\\config\\HoldMusic\\config.json",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\mcm\\config\\HoldMusic\\config.json",
      "sha256": "b32f028277e56d69df20a0ab25073d7f6fb8118c2fada4b31e7e2ed23b7cc831"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package\\mcm\\config\\HoldMusic\\settings.ini",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\mcm\\config\\HoldMusic\\settings.ini",
      "sha256": "b89747fa8565a3b79b5191a65bba76bf5c94507e0043acad4db9f12b47ed325b"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t0\\library\\library.json",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\SKSE\\Plugins\\StorageUtilData\\HoldMusic\\library.json",
      "sha256": "17254c5a90f345dbd625ed7418972aba3ba2fdba476d3670ca9df9d427b3c4fb"
    },
    {
      "source": null,
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\SKSE\\Plugins\\StorageUtilData\\HoldMusic\\receipts.json",
      "sha256": "fc7882d107516b7d60864b2c9370ad64462d1b07ba7820c245249bb6edbdc864",
      "content": "{\"version\": 1, \"performances\": []}\n"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t0\\library\\hm_slot_01.wav",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\Sound\\fx\\holdmusic\\hm_slot_01.wav",
      "sha256": "6b56a19ccce4405b0546c18e9291ba046306a7ffa6c7589eef380b73799af6c7"
    },
    {
      "source": null,
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\meta.ini",
      "sha256": "a1149ad7da32d8e0d1acb1f3926195ba084433d4d03726729af6cfc0bec7f486",
      "content": "[General]\nmodid=0\nversion=0.1.0\ncategory=0\nnotes=Hold Music owned performances; runtime and VFS verification pending.\n"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\game_package\\README.md",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\README.md",
      "sha256": "964044332c933ec3f1237c5f44611919160b838be1b716a4f47104c09bcf28ef"
    },
    {
      "source": "C:\\MGO\\hm-scratch\\t1c\\docs\\game-package-verification.md",
      "destination": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances\\docs\\game-package-verification.md",
      "sha256": "49222c534a192c9870d790142367401cfae8c3038116dc8d4821d201cf93837d"
    }
  ],
  "backups": [
    {
      "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\modlist.txt",
      "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\modlist.txt",
      "sha256": "6cd32c18c40aa7b49a39b54e8f758fd62eecb7d90b417fcd4f572f86e6a14429"
    },
    {
      "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\plugins.txt",
      "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\plugins.txt",
      "sha256": "7a28dd1bbfb4be2e95a427ee520906b15d1f256131a836e2cb44f67a7b9ba1c9"
    },
    {
      "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\saves\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.ess",
      "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\pre-install-save\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.ess",
      "sha256": "2831d7c263bcb7106d323bcd94630cd4ab8f336fda02ee8d42b4c47579c79074"
    },
    {
      "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\saves\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.skse",
      "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\pre-install-save\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.skse",
      "sha256": "256de08440a3862e088fb57e0eb295daced2e801293386ca1a51032094a4dc09"
    }
  ],
  "library": "C:\\MGO\\hm-scratch\\t0\\library",
  "backup": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances",
  "existing_mod_backup": null,
  "replace_existing_mod": false,
  "receipt_destinations": [
    "C:\\MGO\\hm-scratch\\t1c\\local\\game-package-install.json",
    "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\game-package-install.json"
  ],
  "receipt": {
    "receipt_version": 1,
    "version": "0.1.0",
    "library_version": 1,
    "installed_at": "2026-10-09T06:41:42.108941-05:00",
    "root": "C:\\MGO\\Skyrim MGO 4.0 RC4.1",
    "profile": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2",
    "mod": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\mods\\MGO Experimental - Hold Music Performances",
    "data_mod": "MGO Experimental - Profile Data",
    "library": "C:\\MGO\\hm-scratch\\t0\\library",
    "package": "C:\\MGO\\hm-scratch\\t1c\\game_package\\build\\package",
    "backup": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances",
    "library_manifest_sha256": "17254c5a90f345dbd625ed7418972aba3ba2fdba476d3670ca9df9d427b3c4fb",
    "package_hashes_sha256": "dc2ba878c37b6b9896571ca12fcc27a90c00c3948aee919447b98f2395a9e751",
    "files": {
      "HoldMusic.esp": "dc6b243f11ad4c20b648c2b87564dba9c47d85d59d6fa99bfa785d78f4af2d13",
      "SEQ/HoldMusic.seq": "004be5580012efcdec118fce2444cf2dab6a4709d71924066ed03b59a19969de",
      "SKSE/Plugins/HoldMusic/registry.json": "367e57de35f9ef815ea28c146cc94ce4a65e7786fd1103a219df1f36297899f0",
      "Scripts/HM_Config.pex": "03c3c4236819740bf2e520a65637408b9427d1f871d506280a9ab06194bd687e",
      "Scripts/HM_Controller.pex": "42751884bd1fea6b34df55e97d75a20560ef6dfca89c8eb7945880f3fe903b54",
      "Scripts/HM_Library.pex": "04211cbeacd49b1353c90b9ee632b3c39af8ef9c3f363af1452d24bc5cfc12e7",
      "Scripts/Source/HM_Config.psc": "cda751f1c648b44216bfcde41db84d0b89e3754a87ae4544f3f951fb2c1b0596",
      "Scripts/Source/HM_Controller.psc": "11f02733ee562475924089c9e8263020a6df0508f264319bbbb864ae377d7bae",
      "Scripts/Source/HM_Library.psc": "a019b0f1dc75a451c383cbe65fc22936dc52b524d9d0da8baa68d44ad349ab28",
      "Sound/fx/holdmusic/README.txt": "d4d4cd81e8d94c3998028de7ae9b3a85cc52befaa409994e125bad5f53afe656",
      "mcm/config/HoldMusic/config.json": "b32f028277e56d69df20a0ab25073d7f6fb8118c2fada4b31e7e2ed23b7cc831",
      "mcm/config/HoldMusic/settings.ini": "b89747fa8565a3b79b5191a65bba76bf5c94507e0043acad4db9f12b47ed325b",
      "SKSE/Plugins/StorageUtilData/HoldMusic/library.json": "17254c5a90f345dbd625ed7418972aba3ba2fdba476d3670ca9df9d427b3c4fb",
      "SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json": "fc7882d107516b7d60864b2c9370ad64462d1b07ba7820c245249bb6edbdc864",
      "Sound/fx/holdmusic/hm_slot_01.wav": "6b56a19ccce4405b0546c18e9291ba046306a7ffa6c7589eef380b73799af6c7",
      "meta.ini": "a1149ad7da32d8e0d1acb1f3926195ba084433d4d03726729af6cfc0bec7f486",
      "README.md": "964044332c933ec3f1237c5f44611919160b838be1b716a4f47104c09bcf28ef",
      "docs/game-package-verification.md": "49222c534a192c9870d790142367401cfae8c3038116dc8d4821d201cf93837d"
    },
    "profile_edits": [
      {
        "path": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\modlist.txt",
        "encoding": "utf-8",
        "bom_hex": "",
        "before_sha256": "6cd32c18c40aa7b49a39b54e8f758fd62eecb7d90b417fcd4f572f86e6a14429",
        "after_sha256": "ae70f36b0704ad614be17ecd327f85171e63e8c79391873c6e321c84f55a39c8",
        "edits": [
          {
            "action": "insert",
            "line": 2,
            "text": "+MGO Experimental - Hold Music Performances",
            "newline": "\r\n"
          }
        ]
      },
      {
        "path": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\plugins.txt",
        "encoding": "utf-8",
        "bom_hex": "",
        "before_sha256": "7a28dd1bbfb4be2e95a427ee520906b15d1f256131a836e2cb44f67a7b9ba1c9",
        "after_sha256": "3a8fcb17a945fe18ddf0b5c4e8fc37e5378cef3c9f82759676874cccd990bc7c",
        "edits": [
          {
            "action": "append",
            "line": 2000,
            "text": "*HoldMusic.esp",
            "newline": "\r\n"
          }
        ]
      }
    ],
    "backups": [
      {
        "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\modlist.txt",
        "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\modlist.txt",
        "sha256": "6cd32c18c40aa7b49a39b54e8f758fd62eecb7d90b417fcd4f572f86e6a14429"
      },
      {
        "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\plugins.txt",
        "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\plugins.txt",
        "sha256": "7a28dd1bbfb4be2e95a427ee520906b15d1f256131a836e2cb44f67a7b9ba1c9"
      },
      {
        "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\saves\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.ess",
        "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\pre-install-save\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.ess",
        "sha256": "2831d7c263bcb7106d323bcd94630cd4ab8f336fda02ee8d42b4c47579c79074"
      },
      {
        "source": "C:\\MGO\\Skyrim MGO 4.0 RC4.1\\profiles\\MGO EXP - SkyrimNet b26 + SeverActions 4.2\\saves\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.skse",
        "destination": "C:\\MGO\\codex-backups\\20261009-064142-091938-hold-music-performances\\pre-install-save\\Save263_970036FA_0_5A6F687261_BYOHHouse3Pale_011609_20261009060628_24_1.skse",
        "sha256": "256de08440a3862e088fb57e0eb295daced2e801293386ca1a51032094a4dc09"
      }
    ]
  }
}
```

### Stop-report items and remaining gates

No stop-report items. The real installation was deliberately not attempted;
it remains gated on the adapter's in-game test and closed MO2/Skyrim.
JsonUtil's physical read/write target, including possible receipt writes under
`overwrite\SKSE\Plugins\StorageUtilData\HoldMusic\`, remains unknown.
The VFS/game-side probes must settle where the helper reads receipts. No
headset, audio, native JsonUtil or VFS acceptance is claimed.

Authored by Codex, running GPT-6.
