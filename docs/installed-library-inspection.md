# Inspecting a split installed library

`tools/inspect_installed_library.py` reads the loose Hold Music files associated
with an explicit MO2 profile. It does not launch MO2 or Skyrim, flatten/copy the
library, merge recordings or write runtime state.

```sh
python -B tools/inspect_installed_library.py \
  --mo2-root /path/to/MO2 \
  --profile "Selected profile" \
  --game-data /path/to/SkyrimVR/Data
```

The Python API is
`inspect_installed_library(mo2_root, profile, *, game_data=None,
vfs_report=None, session_receipt_index=None)`.

## What the projection resolves

Loose layers are inspected in priority order: overwrite, enabled mods in the
profile's stored modlist order, then the explicitly supplied base-game Data
directory. A file's modification time does not determine its winner. Disabled
mods cannot supply effective content.

MO2's `*DLC:`, `*Creation Club:` and `*Unmanaged:` entries are retained as
informational foreign content, not interpreted as folders under `mods/`.
MO2 writes the `*` marker for foreign entries in
[Profile::doWriteModlist](https://github.com/ModOrganizer2/modorganizer/blob/master/src/profile.cpp#L226-L254)
and defines those names in
[ModInfoForeign](https://github.com/ModOrganizer2/modorganizer/blob/master/src/modinfoforeign.cpp#L31-L63).
Loose files in an explicitly supplied base Data layer are inspected; archive
contents and other unmanaged mappings remain outside the projection.

Each virtual file is resolved independently:

- `SKSE/Plugins/StorageUtilData/HoldMusic/library.json`
- `SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json`
- `SKSE/Plugins/StorageUtilData/HoldMusic/trace.json`
- `SKSE/Plugins/StorageUtilData/HoldMusic/hm_slot_NN.lyrics.txt`
- `Sound/fx/holdmusic/hm_slot_NN.wav`

The manifest, a recording's WAV and its lyrics may legitimately come from
different layers. All 24 slots are inspected. Source-library scratch files are
never substituted for missing installed sidecars.

The report retains candidate paths, hashes, priority and differing lower copies,
plus missing higher-priority paths. A malformed higher-priority manifest, receipt
or referenced asset blocks validation; a valid lower copy is not a fallback.
Case-insensitive component lookup preserves actual spelling while rejecting
ambiguous case collisions and unsafe aliases.

The effective manifest, history and referenced WAV/lyrics are validated without
rewriting old metadata. Occupied, receipt-reserved and orphaned slots are reported.
Each recording distinguishes valid assets from its stored playback enablement:
valid files do not turn a disabled recording back on.
Without an explicit established process-session boundary, all observed receipt
slots remain reserved. A boundary does not prove that Skyrim has exited or that
its in-memory sound cache is clear.

## Captured file-handle evidence

`--vfs-report /path/to/existing-capture.json` can compare a previous version-2
file-handle capture with current known candidates. Profile, timestamp, virtual
paths, opened destinations and file hashes are checked. Report-supplied paths do
not authorize arbitrary file reads. Missing or stale observations remain visible;
matching old observations do not override today's loose-file priority.

The separate `game_package/tools/probe_vfs.py` now includes lyrics and trace
targets as well as all WAV slots. File rows retain the existing version-2 fields
and add `required` and observed `exists`. Missing optional slot assets, receipts
or trace files are represented as absent; missing required inputs and unreadable
files still fail the probe. Failure to resolve an opened handle is an error,
not evidence that an optional file was absent.

The probe still needs a separately authorized MO2-launched process for actual
injection evidence. Fixture captures and ordinary filesystem reads are not
injected observations. Neither tool proves future write destinations.

## Boundaries before deployment

This is a loose-file projection. It does not establish archive contents, external
or unmanaged mappings, plugin-created overlays, running-save state, controller
ownership, process quiescence or successful playback. An omitted base Data layer
is an explicit coverage limitation. `installed`, `vfs_verified`,
`runtime_verified` and `writes_performed` remain false.

The deterministic snapshot/review token identifies inspected inputs, not
permission to mutate them. No apply option consumes it. The
[flat-library merge planner](library-merge-review.md) and
[static package transaction](game-promotion-transactions.md) retain their
separate limits. The [contract-migration review](contract-migration-review.md)
uses this projection for explicit upserts and retained-recording impact reports.
A future library deployment must bind the effective inputs,
explicit contract changes, destination routing and durable rollback in its own
review.
