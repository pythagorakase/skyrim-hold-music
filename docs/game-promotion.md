# Read-Only Game Package Promotion Plan

`tools/plan_game_promotion.py` compares an explicitly selected offline build with
an existing Hold Music installation. It prints a review plan and has **no apply
option**. It does not launch a process or the game, generate audio, install files,
create backups, rewrite profile lists, or merge a recording library.

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

## Runtime Identity Remains a Separate Requirement

The current Papyrus pilot selects by performer, region and mode. It does not
enforce the production contract's recipe revision, named instrument, instrument
family, arrangement, voice and model. Versioned recordings in an observed or
proposed library therefore produce an explicit compatibility blocker, even if
their schema and offline planner checks pass. Partial identity metadata is
reported as malformed. Legacy identity stays unknown and is never filled from
the current recipes.

No package currently gains runtime identity capability merely by supplying
metadata in a receipt. A later compiled, tested controller needs an explicit
capability contract bound to its build and hashes before versioned library
promotion can be supported.

The plan always records `installed: false`, `runtime_verified: false` and
`runtime_identity_supported: false`. It does not establish process state,
saved-script compatibility, controller ownership, sound/animation behavior or
VFS write destinations. Replan after source or target changes; filesystem
observations are not an atomic snapshot. Any later apply/rollback implementation
must recheck reviewed hashes and preserve these same runtime boundaries.

## Offline Tests

```sh
python -B -m unittest discover -s tests -p test_game_promotion.py -v
```

Tests use temporary fixture trees and compare file bytes and modification times
before and after planning. They cover deterministic reports, preservation,
stale/tampered inputs, path safety, runtime identity blockers and the CLI's
absence of an apply operation. They neither modify the installed game nor make
provider calls.
