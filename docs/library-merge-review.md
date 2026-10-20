# Read-only library merge review

The merge planner reviews existing recordings in two explicit, flattened library
directories. It does not copy audio, replace a manifest, deploy a game package or
activate a runtime contract. Regional listening remains a separate refinement
process; this review checks identity, assets, slot availability and preservation.

```sh
python -B tools/plan_library_merge.py \
  --staged-library /scratch/staged/library \
  --destination-library /scratch/destination \
  --receipts /scratch/current-receipts.json
```

The Python entry point is
`plan_library_merge(staged_library, destination_library, *, receipts_path=None,
session_receipt_index=None)`. Both roots must already contain `library.json`;
WAV and lyrics files must be beside their manifest. An installed MO2 library
splits those files across directories and may have winning overrides. This
command does not discover or flatten that effective installation.
The separate [installed-library inspector](installed-library-inspection.md)
can review those split loose-file paths without copying them or changing this
planner's flat-library input contract.
The [publication route planner](library-publication-plan.md) can bind an explicit
flat destination snapshot to fresh installed-file hashes, then propose physical
routes and shared-profile effects. It does not create the snapshot or write
either library.

## Identity and contract decisions

Incoming recordings need the complete projected runtime identity and a matching
staged performer contract. Their readable fields, independent digest, WAV and
lyrics must validate. Unknown historical metadata is not completed using today's
palette or an importer's old model placeholder.

Existing destination rows and their metadata remain intact. Adding a contract
for a performer with legacy destination recordings would change selection:
those recordings could become ineligible. That requires a separate explicit
migration decision and blocks this additive plan. A different contract for an
already configured performer also blocks review. A matching existing contract
can be retained; a new performer's contract is only a proposed action.
The separate [contract-migration review](contract-migration-review.md) can audit
explicit performer-contract upserts against the installed projection, including
the retained rows that lose compatibility. It does not bypass this planner's
blockers or apply either proposal.

Composition identity, recording compatibility and individual takes are distinct.
Conflicting immutable composition content cannot be merged under one ID.
Different audio takes can share a composition and compatibility contract.
Matching audio/lyrics bytes with the same compatibility and save/world scope
identify an already-present take, which consumes no new slot. Existing duplicate
destination rows remain untouched.

Legacy rows with explicitly null revision/family/name remain unknown. The planner
does not remove those fields. If adding a runtime-selection block would make
such retained rows fail the current projection validator, the proposed merge
is blocked for an explicit migration decision. A clean report must validate the
combined manifest, not just its two inputs separately.

## Slots and history

Proposed additions use free slots deterministically. Occupied slots, orphan WAVs,
orphan sidecars and receipt-reserved slots are unavailable. The plan never evicts
or replaces one to make room.

Without an explicit session boundary, all destination receipt slots are reserved,
including interrupted performances. `--session-receipt-index N` may use only an
already established process-session boundary within the raw receipt-array length.
A save load is not a new process session. A missing explicitly selected receipts
file or malformed history blocks review.

The destination's receipt history and generation accounting are preserved.
Source history is not imported as new destination events. Extra destination
files remain protected. A proposed manifest is review material, not an instruction
to overwrite the installed manifest.

## Review identity and limits

The report contains blockers, proposed actions, preservation observations and a
snapshot-based review token. Changed inputs require a fresh review. This token
is a fingerprint for comparison; there is no `--apply` or `--review-token`
execution option.

The separate [static package transaction](game-promotion-transactions.md) still
cannot merge a library. A future library writer needs effective MO2 path
resolution, verified controller capability, process coordination, fresh guards,
durable asset/manifest recovery and a concrete reviewed rollback policy.
`writes_performed` and `runtime_verified` remain false in this review.
