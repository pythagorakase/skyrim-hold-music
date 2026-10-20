# Library publication: next implementation boundary

Design checkpoint, 20 October 2026. This document describes the next fixture-only
work after the [contract migration review](contract-migration-review.md).
There is no library publication writer or live apply command.

The existing static transaction protects runtime libraries; keep that boundary.
The full installer seeds receipt/trace state and does not copy lyric sidecars.
It is not an additive publication helper.

## Bind explicit routes and effects

A publication plan must name each virtual path, physical target, role, prior
presence/hash and source hash. Audio belongs under `Sound/fx/holdmusic`; lyrics
and `library.json` belong under `SKSE/Plugins/StorageUtilData/HoldMusic`.
Require explicit target roots. Captured opened paths prove historical reads,
not permission or routing for writes.

Use the installed projection to simulate the proposed winner for every file.
Report higher overrides, changed priorities and unknown archive/custom routing
before mutation. Bind the staged identity, explicit migration decisions,
installed snapshot, profile lists, relevant controller/registry/ownership
evidence and route table into one review.

MO2 mods and overwrite are shared across profiles. Inventory every profile that
can see a target root and explain its affected manifest/slot paths. A selected
profile label does not isolate these writes. Do not implicitly enable mods,
change priorities, relocate overwrite files or select a different destination.

## Commit point and recovery

The first transaction should support only additive recordings in absent,
unreserved slots plus explicitly reviewed contract changes. Preserve old
recordings, unknown provenance, receipts, trace, generation accounting and
orphan reservations. Closing Skyrim does not authorize rewriting its history.

Require fresh process checks, stopped helper writers, and a lock shared by
writers to the same physical library. Recompute and recheck the reviewed inputs
under that lock. Unknown process state is not proof of quiescence; the tool's
lock cannot exclude arbitrary external editors.

Persist intent and exact recovery information before writing. Publish and
verify new WAVs and lyrics first. Atomically replace `library.json` **last**:
that replacement is the commit point. Recovery must distinguish the before and
after manifest hashes, including a crash between replacement and its journal
checkpoint. A crash before commit leaves reserved assets until journal-driven
recovery resolves them.

Rollback must unpublish or restore the manifest before touching added assets.
Remove only transaction-added bytes that still match recorded hashes and are
not referenced by current state. A later manifest edit or third-state asset
must block automatic restoration. Later receipts, traces and generation
accounting must survive. If gameplay has already used a newly introduced slot,
the first implementation should retain its assets or block rollback explicitly,
rather than erase that history's audio. Recovery must work after staging/source
files have disappeared.

## First bounded fixture milestone

Start with one instrumental recording in a free slot, explicit effective target
paths, matching supported controller evidence and retained histories. Show
manifest-last commit and conservative recovery/rollback without widening the
static-file allowlist or exposing a live apply command.

Exercise stale inputs, a new higher override, changed receipts/profile state,
another writer or process starting, capacity/reservations, every asset/manifest
crash boundary, source disappearance, later gameplay history, modified manifest
rollback, shared-profile impact and preservation of lyric sidecars. Keep
simulated routing and process observations visibly separate from real MO2
injection and successful gameplay.
