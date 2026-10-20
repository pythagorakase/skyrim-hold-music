# Reviewed static promotion and rollback

Design and fixture-test checkpoint, 20 October 2026. This work prepares a
transaction path; it does not authorize an installation. Actual installation
requires a separate, explicit approval of the concrete review. Regional
listening remains independent of this engineering work.

The existing [read-only planner](game-promotion.md) supplies verified candidate
provenance, before/after hashes and protected-file observations. A successful
review is not an apply operation, and a review token is a state fingerprint,
not a credential or evidence of user approval.

## Interface and reviewed state

`tools/promote_game_package.py` defaults to read-only review with explicit
`--build-dir`, `--source-root`, `--mo2-root` and `--profile`. Application requires
both `--apply` and the returned `--review-token`. `--rollback` also previews by
default and requires its own fresh token plus `--apply` to mutate files.
`--status` only inspects existing recovery state. Preview/status must neither
create the journal directory nor acquire a writer lock that creates files.

The core operations are `promote_static`, `rollback_static` and
`promotion_status`. Canonical serialization binds an apply token to its
operation, explicit installation target/profile, exact ordered actions,
candidate/build receipt and capability hashes, and the full reviewed snapshot.
A rollback token binds the existing journal/backups, target/context guards and
fresh destination/protected-file observations; it does not depend on the
original candidate. An apply token cannot authorize rollback or a different
target. Any changed input invalidates that review; never silently refresh a
token and apply the new result.

## Allowed changes and preconditions

Only additions/replacements in `hold_music.promotion.STATIC_FILES` may reach the
existing mod directory. Unchanged files require no rewrite. Unknown package
files and blocked plans stop the operation. Never replace the whole mod tree.

Runtime JSON, library manifests, audio, lyrics, receipts, traces, MCM
`settings.ini`, SkyrimNet configuration, unrelated files, profile lists and saves
are protected. There is no library merge, seed/reset, profile enablement, save
restore, ownership handoff or provider call in this transaction. The registry
and MCM schema are static files; their exact proposed contents remain part of
the review.

Before mutation, establish that Skyrim and MO2 are closed, acquire the
target-specific kernel lock, and recompute the planner result against the same
explicit roots. Require the reviewed token and a blocker-free plan. Recheck
path containment, aliases, source inventory, capability evidence, destination
hashes and protected state before writing. A failed process enumeration is not
proof of quiescence. Other file writers must remain stopped; the lock coordinates
this tool's writers, not arbitrary editors or the game.

Repeat the process/path/hash guards at mutation boundaries. They reduce races
but do not make several files an atomic filesystem transaction.
The review's `can_apply` describes file/state eligibility; execution still needs
fresh Windows process verification. There is no CLI flag to bypass that check.

## Recovery record and interruptions

Keep the fixed journal and kernel lock under
`<mo2>/.hold-music-promotion/<canonical-target-hash>`. Validate this location and
its ancestors against links and path escapes. Bind journal contents to that
target; paths inside a receipt cannot redirect writes. Keep prior transaction
history and reject a concurrent writer or unresolved earlier transaction.

Before the first target mutation, retain every replacement's original bytes,
record its hash, size and timestamp, and record prior absence for additions.
Freeze reviewed candidate bytes for the current operation and record their
hashes. Flush original-byte backups and the prepared journal to durable storage.
Replace individual files through temporary files in the control directory on
the same filesystem, flushing before atomic replacement; checkpoint each completed action.
Verify final static hashes and unchanged protected-file bytes/metadata before
recording success. Do not infer success merely because a replacement returned.

An interruption can occur after replacement but before its checkpoint. Recovery
therefore compares the actual destination with the recorded before/after hashes,
rather than trusting an action's status alone. Retain recovery data on exceptions,
failed writes and unknown states. Status reports partial work; it never resumes
an interrupted apply automatically. Fixture crash injection exercises process
interruption, not every possible power-loss/filesystem failure.

## Conservative rollback

Rollback needs the validated journal, backups, target and installation-context
guards. It must still work if the original checkout or candidate has moved or
changed. It does not regenerate old files from current source or rerun a build.

Preview all backups and current destinations before restoring any file, then
require the rollback-specific reviewed token. A destination already equal to its
recorded before state needs no change. Restore a replacement only while it
matches this transaction's after hash; remove an added file only while it still
matches the added bytes. Any third state, missing required backup, corrupt backup
or changed installation context is a conflict: preserve it and request a new review,
without forcing restoration over later user work.

Restore eligible actions in reverse order, rechecking each destination and
checkpointing progress. Repeated rollback must recognize already restored
files. If a crash occurred before a backup was saved and the destination still
has its original bytes, no restoration is needed for that entry. Empty parent
directories created for added static files may remain; rollback never recursively
removes directories. Starting a later reviewed transaction archives the prior
terminal journal and retains its backups. The command targets
the current transaction; it does not offer arbitrary historical rollback.
Normal post-gameplay changes to runtime receipts, traces, audio, settings and
saves are allowed:
preserve their current bytes and bind those fresh observations to the rollback
token for race checks. Their old apply-time hashes must not gate ordinary
rollback or cause old copies to be restored. Changed modlist/plugin lists or
profile/target ownership context can block rollback without undoing those
changes.

## Evidence and fixture coverage

Completion means only that reviewed static bytes were promoted or restored.
Keep `runtime_verified: false`; compiled-script fixtures and hashes do not prove
MO2 VFS winners, saved-script compatibility, controller ownership, playback or
the absence of a CTD. Those require separate observations after an authorized
deployment.

Use temporary fixtures only for this checkpoint. Cover no-write previews/status,
wrong/stale/cross-operation tokens, process/lock refusal, source and protected
state drift, corrupt backups, path aliases/escapes, interruption before and after
each replacement/checkpoint, rollback after candidate removal, later target
edits, repeated rollback and preservation of every excluded file.

Implementation references:

- `game_package/tools/install_game_package.py:require_closed` informed the
  stricter `promotion_transaction.default_process_probe` Windows process guard;
  the full installer is not a promotion helper.
- `tools/reconcile_bard_ownership.py` demonstrates flushed atomic writes,
  recovery data before mutation, and hash-guarded rollback.
- `hold_music/job_store.py:_writer_lock` supplies the kernel-lock pattern;
  promotion must use its own target journal rather than the paid-job store.
