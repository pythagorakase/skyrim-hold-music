# Reviewing performer selection changes

`tools/review_contract_migration.py` compares the candidate selector's current
identity rules with explicit proposed rules, using a fresh
[installed-library inspection](installed-library-inspection.md). It neither
publishes a manifest nor changes recordings, receipts or assets.

```sh
python -B tools/review_contract_migration.py \
  --mo2-root /path/to/MO2 \
  --profile "Selected profile" \
  --game-data /path/to/SkyrimVR/Data \
  --proposal /path/to/proposed-contracts.json
```

The proposal is a canonical `runtime_selection` object:
`{"version": 1, "contracts": [...]}`. Each contract supplies all ten exact identity
fields and their matching `identity_key`, as defined in
[candidate runtime identity](candidate-runtime-identity.md). Use the explicit,
frozen planner request to produce a proposal; recordings and today's musical
palette are not sources for filling unknown historical values.

The proposal contains **upserts only**. An existing performer's contract is
replaced explicitly; a new performer's contract is added. Every unmentioned
contract stays in its original order. There is no removal or legacy-fallback
operation. Case-only performer changes are ambiguous and are rejected.

## What the review compares

Each retained recording remains visible in the audit, including invalid rows.
The report explains identity compatibility before and after the proposal and
keeps these separate:

- Unknown or mismatched recipe revision, model, named instrument, family,
  arrangement, region, mode or voice.
- Validated audio and lyric assets.
- The stored playback flag and whether the strict selector requires it.
- Occupied, receipt-reserved and orphaned slots.
- Live locks, controller ownership, ranking and actual playback, which this
  operation cannot establish.

The baseline is the **candidate selector with the currently observed manifest**,
not a claim about the installed controller's behavior. With an explicit contract,
only a complete matching projected identity can qualify. A version field's
presence, even explicit `null` or a partial identity, suppresses legacy fallback
for that performer. Without a contract, only a fully legacy performer retains
the legacy selection path. The candidate's legacy path does not enforce the
strict playback-flag check; the audit reports that distinction.

The requested mode is a ranking preference in `ChooseSlot`, not a general
hard filter. A strict contract still fixes its own mode. The review does not
predict which slot wins ranking, whether a save knows a composition, or whether
a process has cleared its in-memory sound locks.

## Preservation and blockers

The in-memory projected manifest changes only `runtime_selection`. All
recordings, historical fields, unknown extensions and generation history remain
unchanged. It is a review artifact, not an installable package.

Existing inspection problems remain blockers. A proposal cannot silently
repair a malformed existing contract block; when it cannot be safely preserved,
no projected manifest is produced. Strict validation also examines the complete
prospective manifest. Nullable legacy fields that become incompatible with a
strict projection are reported rather than removed or filled.

A changed performer without matching valid asset candidates is explicitly
blocked. A compatible recording is still not evidence of current playback
availability: reservations and unknown live locks remain separate. Existing
missing assets cannot be cleared by borrowing a source-library copy.

The review binds proposal bytes and fresh installed observations. Changed
inputs invalidate it. There is no apply option or consumer that treats the token
as authorization. Installation, VFS, runtime and write flags remain false.

The [publication design](library-publication-design.md) describes the next
engineering boundary; listening validation remains independent.
