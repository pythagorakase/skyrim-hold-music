# Development Roadmap

**Decision date: 2026-10-19.** The user's validation of regional styles does not
gate engineering progress. Current recipes are provisional, versioned inputs.
Listening confidence, technical readiness and runtime evidence are separate
records; none is inferred from another.

## Current Baseline

The workshop already provides the eleven regional targets, the separate Reach
sean-nós challenger, and open-ended three-choice Clip/Full blind auditions.
Practice, first encounters, prompt/model cohorts, saved takes and provenance
are preserved. The deferred catalog and existing vocal constraints remain in
place. This decision changes no recipe, active profile, prompt revision or
listening score and does not admit new paid generation automatically.

The performer registry, recording library, repertoire planner, read-only
actor-knowledge bridge and bounded lyrical/instrumental executor are implemented.
The game pilot remains narrower than the workshop: its regional selection and
plucked-string arrangement need further integration. The owned controller is
installed on HALCYON with the [15 October scan workaround](sven-crash-2026-10-15.md).
Successful owned playback and interruption after that fix are still unverified.

## Next Integration Milestone

Build one repeatable **prepare, publish, perform, reconcile** loop for the
existing pilot performers using existing recordings. Complete all offline
parts without requiring listening judgments or buying new audio:

1. Establish a deterministic, reversible controller handoff. The 19 October
   read-only preflight found an older overwrite `BardSinging.yaml` with
   `enabled: true` and a profile-data copy with `enabled: false`; the last
   adapter overlay recorded `false`. This is a fallback-input conflict, not
   proof of SkyrimNet playback being enabled in a running game. Extend the
   MO2 VFS probe to report the actual winning Bard Singing file and enabled
   value, then implement tested overlay reconciliation and rollback. The
   earlier package VFS check did not include this configuration file. Make
   no runtime configuration change merely to synchronize source code.
2. Resolve the selected performer and save-scoped knowledge through the
   read-only bridge. Report unresolved identity explicitly.
3. Plan from known compositions, compatible recordings and performance history.
   Demonstrate both cached selection and a proposed topical job with synthetic
   fixtures; a dry run makes no provider calls.
4. Carry the recipe revision, model, actual instrument family, arrangement,
   voice mode and source provenance through recording selection and publication.
   Reject incompatible reuse instead of silently substituting another style.
5. Stage a package from existing audio, validate its metadata and WAV files,
   and produce a deployment receipt with source versions and file hashes.
   Keep real deployment separate from planning and preserve installed runtime
   JSON, saves, private configuration and recordings.
6. Feed a captured or synthetic performance receipt back into planning. Show
   that replay history, interruptions and cooldowns affect the next decision
   without manufacturing knowledge or duplicate composition work.

The milestone's offline acceptance is an inspectable report linking performer,
save scope, selected recording or proposed job, versioned recipe, staged files
and reconciled receipt. A mock provider or existing WAV is sufficient; there is
no requirement for an approved regional palette.

**20 October offline checkpoint:** the [integration proof](offline-integration.md)
now exercises that sequence with explicitly synthetic knowledge and silent PCM
fixtures for the existing pilot performers. It produces a linked staging receipt
and demonstrates duplicate suppression, generation cooldown fallback and
completed/interrupted performance history. The second checkpoint carries exact
recipe revision, named instrument, family, arrangement and voice through
production planning, job journaling, publication, cache counts and selection.
Legacy metadata remains unknown and is never inferred from current recipes.
The installed Papyrus pilot still needs the corresponding
[candidate selection integration](candidate-runtime-identity.md);
offline compatibility is not evidence that runtime selection enforces it.

The VFS probe now observes the winning Bard Singing configuration path, hash and
enabled flag. A separate dry-run-first handoff tool can prepare guarded changes
and rollback data. Neither has been used to change the installed profile in this
offline checkpoint; actual MO2 injection and runtime ownership remain unverified.

## Parallel Engineering

### Durable Jobs and Accounting

The [executor](executor.md) now journals dispatch, returned payloads and accounting
in a private SQLite store. An uncertain request or unpublished paid result blocks
new spending; explicit recovery can publish retained audio without a provider.
Crash-boundary tests use fake clients. This is durable bounded execution, not an
automatic replenishment scheduler. Explicit generation authorization, per-run
spending limits and no automatic retries remain requirements. Reviewed
continuation now authorizes one first music call from valid retained lyrics,
using the original frozen identity and prompt. A matching review token is
required; consuming it and reserving dispatch are atomic. Separate reviewed
reconciliation can append an operator attestation and close a response-less
uncertain call while preserving raw evidence. No provider is queried during
reconciliation. Malformed returned results still need a dedicated resolution
path; they are retained and continue to block spending.

### Performer, Repertoire and Arrangement Identity

Separate learned tradition from venue region and from the visible instrument
family. The registry already carries traditions and an instrument, while the
current executor predominantly selects by hold and uses a fixed plucked-string
arrangement. Extend that contract deliberately, with backwards-compatible
recording metadata and explicit provisional recipe selection.

Add verified placed-reference identities for the actor knowledge bridge, which
currently needs opt-in name matching for some actors. Test ambiguity and
save-boundary cases. An unresolved identity must not become an empty successful
retrieval. Deferred styles can appear as named synthetic test fixtures without
becoming active workshop choices or assigned NPC skills.

### Portable Build and Deployment

The [package builder](../game_package/README.md#build) now accepts explicit
MO2/profile/toolchain paths and defaults to a read-only plan. It compiles into a
fresh workspace with offline dependencies and records input/source hashes and
the target stack. Candidate artifacts can be tested without replacing the
checkout's reviewed build. The [promotion planner](game-promotion.md) now verifies
the candidate and its source provenance, compares allowed static files and
inventories protected runtime data, audio, settings and saves. It has no apply
operation. The candidate Papyrus selector enforces a validated identity
projection; the builder now requires its compiled fixtures to pass and binds
that evidence to the actual artifacts and sources. Promotion validates that
evidence separately from the projected library. Missing candidate evidence or
malformed identity still blocks review; library merging remains unsupported.
The installed controller and runtime verification remain separate. A separate
[static transaction path](game-promotion-transactions.md) implements reviewed
per-file apply/rollback with durable backups, target locking and fresh input
checks. Rollback preserves later gameplay data and works without the original
candidate checkout. Its mutations are tested against synthetic installations;
this does not authorize a real deployment or library merge.
The [existing-audio importer](library-format.md#import-an-existing-mp3) now
reviews source-bound identity before conversion; unknown provenance remains
unknown. The separate [library merge review](library-merge-review.md) proposes
additions and slot remapping while preserving history and blocking implicit
contract changes for existing performers. It has no apply operation. Next
resolve the effective installed library paths and design explicit contract
migration and durable library publication without inferring historical identity.
Continue portable
work while following the [RC5 / SkyrimNet migration plan](stack-migration-rc5-beta27.md).
Evaluate native song import as an alternative delivery route when its actual
metadata and ownership behavior can be inspected. Do not assume imported audio
alone enforces performer or regional eligibility.

### Instrument and Performance Lifecycle

Use the plucked-string pilot to establish reliable start, stop, interruption,
cell exit and load cleanup. Flute, drum and later audience controls can be
researched and prototyped independently with fixture audio. In-game availability
still requires a supported animation/controller path and the correct visible
performer count. Pending musical confidence does not prevent this work.

## The Next Short Gameplay Check

When the user next plays, follow the [current retest](sven-crash-2026-10-15.md)
and [in-game plan](in-game-test-plan.md) against the actual selected profile.
First resolve the conflicting configuration inputs and verify effective
controller ownership through the extended VFS probe and startup evidence.
With SkyrimNet's bard controller inactive, enter the Sleeping Giant Inn while
Sven is present; leave and re-enter if loading inside. Check that candidate
discovery advances beyond `check_start`, existing slot audio and the lute idle
start together, and talking to Sven or leaving stops them cleanly. Collect
trace and receipts afterwards.

This is a bounded runtime correctness check, not a request to judge all eleven
styles. It remains necessary before claiming the owned path works in-game;
offline development continues while it is pending.

## Listening as Parallel Refinement

Use blind guessing or side-by-side listening whenever convenient. Record
confusions, enjoyment and fidelity per recipe/model cohort without inventing
passes or pooling changed prompts. Results prioritize the next musical
revision; they do not pause engineering.

Keep the active workshop bounded. A new admission or recipe replacement needs
an intentional source revision with rationale, technical constraints and any
available evidence, not eleven completed listening passes. Retain pending
confidence where evidence is absent, preserve older recordings and prompt
histories, and increment the recipe revision when musical inputs change.
Orsimer, Khajiit and Argonian vocal constraints and all unsupported arrangement
restrictions remain in force.
