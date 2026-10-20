# Library publication: next implementation boundary

Design checkpoint, 20 October 2026. The
[read-only route planner](library-publication-plan.md) now makes explicit
destinations and shared-profile effects reviewable. This document describes
the remaining fixture-only transaction work.
There is no library publication writer or live apply command.

The existing static transaction protects runtime libraries; keep that boundary.
The full installer seeds receipt/trace state and does not copy lyric sidecars.
It is not an additive publication helper.

## Bind explicit routes and effects

The publication plan names each virtual path, physical target, role, prior
presence/hash and source hash. Audio belongs under `Sound/fx/holdmusic`; lyrics
and `library.json` belong under `SKSE/Plugins/StorageUtilData/HoldMusic`.
It requires explicit target roots. Captured opened paths prove historical reads,
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
unreserved slots and contracts for genuinely new performers. Keep the route
planner's existing-performer migration blockers; a separate migration review
does not authorize combining those operations. Preserve old
recordings, unknown provenance, receipts, trace, generation accounting and
orphan reservations. Closing Skyrim does not authorize rewriting its history.

Require fresh process checks, stopped helper writers, and a lock shared by
writers to the same physical library. Recompute and recheck the reviewed inputs
under that lock. Unknown process state is not proof of quiescence; the tool's
lock cannot exclude arbitrary external editors.

Persist intent and exact recovery information before writing. Retain exact
original manifest bytes, canonical proposed manifest bytes and every new asset
in transaction storage; verify their hashes and durability before touching any
destination. Recovery must not require the original staged source. Publish and
verify new WAVs and lyrics first. Atomically replace `library.json` **last**:
that replacement is the commit point. Recovery must distinguish the before and
after manifest hashes, including a crash between replacement and its journal
checkpoint. A crash before commit leaves reserved assets until journal-driven
recovery resolves them.

Rollback must unpublish or restore the manifest before touching added assets.
Remove only transaction-added bytes that still match recorded hashes and are
not referenced by current state. A later manifest edit or third-state asset
must block automatic restoration. Later receipts, traces and generation
accounting must survive. For the first implementation, committed rollback should
always retain added assets as reserved orphans. Report
`rolled_back_with_retained_assets` distinctly. Removal may be considered only for
a proven uncommitted transaction with unchanged, unreferenced assets and
sufficient current history evidence. Missing or malformed history is not proof
that a slot was never played.

## Fixture transaction contract

Recompute the route plan from its explicit input paths; never execute actions
from a caller-edited report. Keep every current blocker, including incomplete
other-profile validation. A clean route review has all execution prerequisites
false and cannot serve as an apply authorization.

The fixture transaction needs a separate operation-bound review token, covering
the route token, current prerequisites, canonical roots and current journal.
Capability for the winning controller bytes, performer/configuration ownership,
physical destinations, stopped helper writers and process quiescence require
separate evidence. Fixture evidence must be explicitly labeled synthetic.

Use a lock shared across profiles and target combinations for the same canonical
MO2 root. Under it, reject unresolved prior transactions and recheck the plan and
prerequisites. Permit only unique allowlisted routes for absent new WAV/lyrics
and one manifest. Bind all route before-states, protected histories and original
absence; keep private configuration contents out of the journal.

After retaining verified payloads/backups and durable intent, publish assets in
deterministic order with same-filesystem atomic replacement, expected-before
checks, verification and checkpoints. Recheck processes, profile/override state,
prerequisites and protected history at each boundary. Persist manifest commit
intent before the final manifest replacement, then verify exact bytes and the
complete current effective library before recording a committed state.

Status remains read-only. Explicit recovery has its own fresh review token and
classifies actual before/after/third-state hashes independently of journal phase.
Never automatically resume a partially applied transaction. Preserve current
receipts and trace during rollback; bind their latest bytes into that review
instead of trying to restore apply-time history.

## Crash and interference matrix

| Observed boundary | Required result |
| --- | --- |
| Before payloads and intent are durable | No destination writes; preview/status creates nothing. |
| Durable intent, no asset written | Existing library unchanged; source deletion cannot prevent recovery. |
| Asset replaced, checkpoint lost | Recognize its after hash; retain/reserve the orphan until explicit recovery. |
| Assets ready, manifest still before | Uncommitted; process restart, disk/permission failure or drift blocks commit without retry. |
| Manifest replaced, commit checkpoint lost | After manifest plus expected assets means committed content; never delete referenced assets. |
| A path has a third-state hash | Block mutation and retain all evidence and third-party bytes. |
| New override/profile, priority change, alias, writer contention or unknown process state | Block; do not repair or relocate files to make the plan work. |
| Committed rollback with unchanged after manifest | Restore/unpublish manifest first; retain added assets as reserved orphans. |
| Later manifest rows or generation accounting | Block whole-manifest rollback rather than overwrite those edits. |
| Later receipts/trace, including interrupted playback in any save/world | Preserve latest bytes and retain introduced assets. |
| Crash during rollback | Infer actual manifest state; recognize completed restoration idempotently and never clean referenced assets. |
| Missing/corrupt retained payload or backup | Block operations needing those bytes; do not reconstruct from mutable source. |

Inject real subprocess exits after each replacement and journal checkpoint.
Reuse the static transaction's atomic-write, locking and process-check patterns,
but keep its static allowlist and restoration policy separate from this
history-preserving library transaction.

## Smaller first step: source-independent preparation

Before implementing a destination writer, add a fixture-only
`prepare_library_publication_bundle(...)` using the same explicit publication
inputs plus a required fresh `output_dir`. Preparation recomputes a blocker-free,
nonempty route plan and exclusively creates an output directory outside every
source and installation root. Existing, overlapping or aliased outputs are
rejected before writing.

Freeze the routed assets and exact proposed manifest, preserving two distinct
before states: the **physical target** (possibly absent) and the **effective
winner** (possibly a different lower mod). Retain both exact byte sets when
present and both absence states. Restoring an originally absent target means
removing the new override under appropriate guards, not copying the lower
winner into that target. Changed lower winners must invalidate recovery review.

Copy and verify retained payloads, then recompute the original plan. Only after
all hashes and reviewed inputs still match may preparation publish its final
descriptor. Missing/invalid final descriptors identify incomplete output.
The descriptor binds routes, original plan token, both before states and a
strict relative payload inventory. Return an external bundle token.

A separate read-only `inspect_publication_bundle(bundle_dir,
expected_bundle_token=...)` must verify the complete inventory, strict JSON,
relative paths, absence of aliases/hardlinks and every hash without following
original absolute paths. It must work after source deletion. Recalculating a
tampered bundle's internal hashes cannot satisfy the externally retained token;
do not describe ordinary files as OS-immutable.

This artifact is preparation, not durable transaction intent, a writer lock or
recovery authority. Keep `can_apply` and every ownership, capability, process,
write-readiness and runtime flag false. Test no-op/existing-output preservation,
interrupted preparation, input drift, distinct before states, source deletion,
payload/descriptor tampering and unsafe output paths before adding any writer.

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
