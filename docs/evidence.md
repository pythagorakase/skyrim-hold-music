# Runtime evidence

Hold Music's game trace records controller decisions and performance outcomes
without dialogue or game free text. It complements the performance history in
[`receipts.json`](library-format.md), which the helper reads without writing.
Collecting evidence makes no provider calls and changes no game or MO2 inputs.

The collector's newest-file heuristic helps find recent logs; it does not prove
which receipt or library file wins in MO2. Use the separate
[installed-library inspection](installed-library-inspection.md) for a selected
profile's loose-file priority and split asset validation. Captured handle evidence
can corroborate particular paths and hashes without proving current injection
or future write destinations.

## Frozen trace schema

`trace.json` has this shape:

```json
{"version": 1, "entries": [
  {"seq": 1, "real_seconds": 115.0, "game_hours": 1008.0,
   "event": "candidate", "detail": "id=sven owner=hold_music eligible=true"}
]}
```

Each entry has `seq` (integer), `real_seconds` (float), `game_hours` (float),
`event` (string), and `detail` (string). The game keeps at most 300 entries,
then rolls by clearing the array and continuing with event `trace_rolled`.
The event names are:

`location_enter`, `location_leave`, `check_start`, `candidate`, `no_performer`,
`slot_chosen`, `vanilla_stopped`, `vanilla_unavailable`, `vanilla_restarted`,
`idle_failed`, `performance_start`, `performance_stop`, `receipt_failed`,
`session_cap`, `disabled`, and `trace_rolled`.

`detail` carries only IDs, booleans, numbers and outcome words, for example
`id=sven owner=hold_music eligible=true` or `outcome=completed slot=3`.
Never put dialogue or free text from the game in this field.

## MO2 storage

PapyrusUtil's JsonUtil writes both files under the virtual game directory
`Data/SKSE/Plugins/StorageUtilData/HoldMusic/`. MO2 routes writes to an existing
file into the mod folder that supplies it; a newly created file goes into
`<MO2 root>/overwrite/`. The installer ships both `receipts.json` and an empty
`trace.json` (`{"version": 1, "entries": []}` followed by a newline), so their
writes stay in the installed mod folder. Installing replaces that mod after
backing it up, so the installed trace starts empty; purge removes its folder.

The locator searches `SKSE/Plugins/StorageUtilData/HoldMusic` under, in order:

1. `<MO2 root>/mods/<mod-name>/`
2. `<MO2 root>/overwrite/`
3. `<MO2 root>/mods/<data-mod>/`, if supplied

`resolve_receipts` and `resolve_trace` select the newest existing file by mtime,
with candidate order breaking ties. Discovery reports filesystem state, not
proof of which file currently wins the VFS. The collector retains every
existing candidate, newest first, so conflicting locations remain visible.

## Collect a report

Run locally on the Windows machine with the MO2 tree:

```powershell
py -3 tools\collect_evidence.py --mo2-root "C:\MGO\Skyrim MGO 4.0 RC4.1" --profile "MGO EXP - SkyrimNet b26 + SeverActions 4.2" --data-mod "MGO Experimental - Profile Data"
```

`--mod-name` defaults to `MGO Experimental - Hold Music Performances`.
`--out <dir>` selects a new directory outside MO2; the default is
`local/evidence/<UTC YYYYMMDD-HHMMSS>/` under the repository (`local/` is ignored).
Existing output directories are refused to preserve previous evidence. The
same stdlib-only tool runs on macOS with `python3` against a local fixture tree.
The command prints the path to `report.md`.

The Markdown report includes each receipts/trace source path, mtime, byte size,
entry count, receipt outcome counts and trace event counts. Copies use numbered
names such as `receipts-01.json` and `trace-01.json` (newest first per file kind).
It also includes:

- The last 80 lines of `<MO2 root>/logs/HoldMusic.log` and `HoldMusic-Service.log`.
- The last 120 allowed matches from the newest `SkyrimNet*.log` under
  `profiles/<profile>/experimental-documents/SKSE/`, its filename, and the first
  and last timestamps found in retained-safe source lines (not only the excerpt).
- The last 120 lines containing `HoldMusic` from the newest `Papyrus.0.log`
  under `profiles/<profile>/experimental-documents/Logs/Script/`.
- Missing input paths, explicitly marked missing. Malformed JSON is copied
  after redaction and listed with an unavailable entry count.

SkyrimNet's only allowed matching patterns are `BardSinging`, `Hold Music`,
`HoldMusic`, `Generation check`, `Playing '`, `Playback started`, and
`Starting song generation`. Lines marked as dialogue or memory are excluded
even if they match. No dialogue or memory text belongs in the report.

## Read-only performance preflight

`tools/preflight_performance.py` checks the prepared pilot after Skyrim exits.
It does not change settings, inspect save contents, request music, or launch
MO2/the game. It prints a human-readable checklist, or JSON with `--json`:

```powershell
py -3 -B tools\preflight_performance.py --mo2-root "C:\MGO\Skyrim MGO 4.0 RC4.1" --profile "MGO EXP - SkyrimNet b26 + SeverActions 4.2" --performer sven --json
```

The exit code is 0 for `prepared_for_headset_test`, 2 for a blocked check or
invalid input. The JSON names each failed check and the selected files, without
dumping credentials, configuration bodies, lyrics, memories or trace details.

Checks cover enabled mod/plugin entries, required package files, both bard
switches, MCM overrides and session cap, the selected performer's owner/base
form/region, matching slot metadata and complete PCM WAV data, and valid evidence
files. The saved `playable` flag is not trusted. Empty trace/receipt arrays mean
no recorded evidence and do not fail the preflight.

Loose files are resolved from overwrite first, then enabled mods in MO2's
stored priority order. If the installed adapter is configured for this profile,
its separate launch input is checked too. An outstanding adapter baseline blocks
the check until reconciliation. Archives, arbitrary plugin mappings, live globals,
actor state and session locks are not resolved: the result is an offline
preparation check, not VFS or runtime acceptance. Process state is a caller
precondition, not inferred from stale files.

On October 14 this check validated the installed Sven and Lynly WAVs but found
an older enabled `BardSinging.yaml` under overwrite, conflicting with the
disabled profile-data source and last adapter overlay. The pilot remains
`blocked` until the conflict is resolved or the effective VFS mapping is
verified. The live dashboard shutdown in that session is separately confirmed
by SkyrimNet's log; it is not invalidated by the offline conflict.

## Redaction

Before writing any report or copy, drop every entire line containing `key`,
`token`, `secret`, `bearer`, or `password`, case-insensitively, including substring
matches. This applies to JSON copies, log excerpts, and report metadata. Parsed
JSON rows containing those terms are also excluded from outcome/event tables;
entry counts describe the original array. Unredacted JSON is copied byte for
byte. Line removal can leave redacted copies incomplete or empty; these are
evidence excerpts, not files to restore into the game. Source files are never
modified. Synthetic fixtures exercise this rule without personal log content.
