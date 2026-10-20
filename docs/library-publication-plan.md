# Planning explicit library publication routes

`tools/plan_library_publication.py` prepares a read-only route plan. It connects
the [flat additive merge review](library-merge-review.md) with a fresh
[installed-library projection](installed-library-inspection.md), without
creating a flattened copy, importing audio or writing any game file.

```sh
python -B tools/plan_library_publication.py \
  --staged-library /scratch/staged/library \
  --destination-snapshot /scratch/explicit-installed-snapshot \
  --mo2-root /path/to/MO2 \
  --profile "Selected profile" \
  --metadata-mod "Existing metadata mod" \
  --audio-mod "Existing audio mod" \
  --game-data /path/to/SkyrimVR/Data
```

The two source roots must be explicit, non-overlapping flat directories outside
the installation and base Data roots. The destination snapshot must match the
freshly observed effective manifest, receipt/trace files, all WAVs and all lyric
sidecars, including absent files and orphaned slots. Matching a manifest alone
is insufficient. Raw file hashes and presence are compared; an absent receipt
file is not interchangeable with an empty history file.

The tool does not make that snapshot or borrow missing installed assets from
another library. Staged inputs still undergo the existing strict metadata and
asset validation. Additive merge rules reserve occupied, receipt-reserved and
orphaned slots; existing metadata and history are preserved. The migration
review does not bypass the merge planner's contract-change blockers.

## Explicit physical targets

Metadata and audio destinations are named existing managed mods, both enabled
in the selected profile. They may be the same mod. Overwrite and base Data are
not publication destinations, and the tool never enables a mod or moves an
override to make a route work.

Each route names its virtual path, role, physical destination, before-state,
source evidence and proposed hash. New audio goes under `Sound/fx/holdmusic`;
lyrics and the manifest go under `SKSE/Plugins/StorageUtilData/HoldMusic`.
The combined manifest is serialized deterministically for its concrete hash
and listed after the asset routes. Nothing is written.

The simulated selected-profile winner must be the exact proposed physical
target. A higher-priority file blocks that route even when its current bytes
match, because writing the proposed target would not change what the profile
reads. Captured opened paths do not authorize destinations.

## Shared profiles and incomplete evidence

Every profile list and the profile-directory inventory are observed. An unreadable
or malformed list cannot be skipped while claiming complete impact coverage.
Each affected virtual path is considered independently: a profile may see the
audio mod but not the metadata mod, or a higher override may hide only one file.
The report exposes disabled, shadowed and effective changes.

A profile with effective changes can qualify through a bounded proof of
complete content equivalence. It first receives its own fresh installed-library
inspection, including slot-directory inventories that catch noncanonical and
out-of-range assets beyond the 51 mapped paths. That inspection must be valid.
Every mapped before-state and every simulated after-state must then match the
validated selected profile by raw presence, size and hash. This includes
unchanged recordings, orphan assets, receipts, trace and absent files.

Different physical winners may qualify when all their bytes and presence agree;
the report preserves their separate provenance and rechecks each inspection
snapshot before returning. It reports
`validation_basis: complete_before_after_equivalence` and
`validation_scope: mapped_loose_library_content`. This proves content
compatibility under the observed loose-file model; controller ownership,
archives, current saves, live locks and runtime behavior remain unverified.

Different before-state libraries or diverging after-states still produce
`affected_profile_validation_incomplete`; a general projection for those cases
is not implemented. Disabled or fully shadowed routes can remain reviewable.
Unknown or malformed profile scope also blocks review.
Shared visibility is not isolation, and a disabled target today does not prove
it will stay disabled. Standard DLC/Creation Club/unmanaged markers remain
informational; archive contents and custom mappings are not verified.

The final state fingerprint rechecks staged files, the flat snapshot, installed
inputs, profile lists and relevant directory inventories. A new profile,
changed priority, new override or changed source invalidates the review.

`can_apply`, `installed`, `vfs_verified`, `runtime_verified` and
`writes_performed` remain false. This operation has no apply option, process
quiescence proof, executable recovery journal or runtime capability attestation.
Ownership, controller capability, actual routing and a concrete transaction
still need their own evidence before deployment.

The [publication transaction design](library-publication-design.md) describes
the remaining manifest-last commit and recovery work. Listening remains a
separate refinement activity.
