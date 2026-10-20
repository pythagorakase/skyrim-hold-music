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

## Parallel Engineering

### Durable Jobs and Accounting

The [executor](executor.md#lyrical-preparation-t2b) is a bounded invocation,
not a crash-safe queue. Persist job state and cost accounting before adding
automatic replenishment. Preserve paid-call evidence even if later conversion
or publication fails, distinguish failed from unknown provider outcomes, and
recover without automatically resubmitting uncertain requests. Test crashes
between each transition with fake clients. Explicit generation authorization,
spending limits and no automatic retries remain requirements.

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

Parameterize the package builder's RC4.1/profile/toolchain assumptions, preserve
dry-run and rollback behavior, and record the exact target stack. Continue
portable work while following the [RC5 / SkyrimNet migration plan](stack-migration-rc5-beta27.md).
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
