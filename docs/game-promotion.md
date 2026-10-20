# Read-Only Game Package Promotion Plan

`tools/plan_game_promotion.py` compares an explicitly selected offline build with
an existing Hold Music installation. It prints a review plan and has **no apply
option**. It does not launch a process or the game, generate audio, install files,
create backups, rewrite profile lists, or merge a recording library.

The separate [reviewed static transaction tool](game-promotion-transactions.md)
can apply allowlisted static changes and restore their retained backups. It
requires an operation-specific review token and fresh guards; this planner
remains read-only. The overnight checkpoint exercises mutations only against
synthetic installations.

```powershell
python -B tools/plan_game_promotion.py `
  --build-dir "C:\MGO\HoldMusic\local\portable-build-verified-20261020\build" `
  --source-root "C:\MGO\HoldMusic\game_package" `
  --mo2-root "C:\MGO\Skyrim MGO 4.0 RC4.1" `
  --profile "MGO EXP - SkyrimNet b26 + SeverActions 4.2"
```

Use the actual selected profile and paths. `--mod-name` and `--data-mod` can
identify other explicitly selected installation directories. The latter is
inspection context, not a claim about priority. `--library <path>` optionally
inspects a prepared library's metadata and always reports that library promotion
is unsupported. The tool does not stage that audio. `-B` prevents Python bytecode
writes; the CLI also sets that restriction before importing project modules.

Exit code 0 means a readable `review_only` plan, **not deployment approval**.
Exit code 2 means a valid report contains blockers. Exit code 1 means an input
could not be validated. Invalid CLI arguments also exit nonzero.

## What Is Verified

The explicit build directory must contain `build-receipt.json`,
`package-hashes.json` and the complete package inventory. The receipt must be
from an offline game-package build; a library-only staging receipt is rejected.
Every package hash is checked. The complete `src/data/imports` source inventory,
source hashes and local plugin-builder inputs are checked against the explicit
source root; added or removed source files invalidate the candidate. Paths embedded in the receipt
never select input files. A changed target build profile or modlist is reported.

The report links the build-receipt hash, package-inventory hash, source
provenance, proposed source/destination hashes and an observed-file snapshot
hash. Existing build receipts do not record a Git commit; the plan reports that
as unknown rather than assigning the current checkout's HEAD to an older build.
Compiler and dependency records remain historical build provenance; planning
does not rerun tools or independently reproduce the build.

Static scripts, source, plugin, sequence, registry and MCM schema files are
compared against an explicit allowlist. Identical files are unchanged; other
allowed files become proposed static additions or replacements. Unexpected
candidate files are blockers. The planner rejects unsafe relative paths,
case-ambiguous inventories, symlinks and junctions, and overlapping candidate
and installation roots.

## What Is Preserved

The plan leaves the installed mod tree in place and inventories runtime JSON,
receipts, trace, existing audio and lyrics, user MCM settings, unrelated files,
profile lists and all files in the selected profile's saves directory. Known
overwrite/data-mod Hold Music files and the Bard Singing configuration are
observed without exposing configuration contents. A possible static override
is reported; actual MO2 VFS winners remain unverified.

Candidate runtime JSON and audio are not merged. The old installer's complete
mod replacement and empty trace initialization are not promotion operations.
Save files and profile lists are not edited, and missing user settings are
reported instead of silently replaced with defaults.

## Candidate Identity and Installed Runtime Evidence

The installed Papyrus pilot selects by performer, region and mode. The new
[candidate library selector](candidate-runtime-identity.md) also checks the
projected recipe revision, named instrument, family, arrangement, voice and
model. A new build earns `candidate_runtime_selection_verified: true` only when
its required compiled-script fixtures pass without skips and its verification
report matches the current package, disassembly, source, fixtures and helpers.
Changing any measured input invalidates that evidence. An older receipt without
this capability remains usable for legacy review, but versioned libraries or
explicit runtime contracts produce `versioned_library_unsupported`, even when
the current recordings are legacy-only or empty.

Candidate capability removes only that compatibility blocker. A projected
library must independently pass strict contract and identity-key validation;
partial, null or stale metadata blocks review. Library merging remains
unsupported and produces its own blocker. Legacy identity stays unknown and is
never filled from current recipes. The hash projection's Papyrus string and
numeric limitations are documented in the candidate contract.

The plan always records `installed: false`, `runtime_verified: false` and
`runtime_identity_supported: false`, including for a verified candidate. Its
compiled fixtures use mocked native APIs, not the Skyrim engine. It does not establish process state,
saved-script compatibility, controller ownership, sound/animation behavior or
VFS write destinations. Replan after source or target changes; filesystem
observations are not an atomic snapshot. Any later apply/rollback implementation
must recheck reviewed hashes and preserve these same runtime boundaries. The
separate transaction path follows those boundaries without adding library
merging or profile enablement.

The separate [library merge review](library-merge-review.md) can compare two
explicit flattened libraries and propose additive slot/contract changes. It is
read-only and does not remove this planner's `library_promotion_not_supported`
blocker. Effective MO2 paths, runtime capability and an interrupted-write
recovery design remain requirements for an eventual library deployment.

## Offline Tests

```sh
python -B -m unittest discover -s tests -p test_game_promotion.py -v
```

Tests use temporary fixture trees and compare file bytes and modification times
before and after planning. They cover deterministic reports, preservation,
stale/tampered inputs, path safety, candidate capability and identity blockers, and the CLI's
absence of an apply operation. They neither modify the installed game nor make
provider calls.
