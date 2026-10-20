# Candidate runtime identity integration

Design checkpoint, 20 October 2026. This is the next bounded offline task,
not an installed capability or a tested gameplay result. The installed
Papyrus pilot still selects by performer, region and mode.

## Expected contract

Project an explicit per-performer selection contract into a **new staged**
library from the validated, frozen `decision.request`. The existing offline
staging proof already records that request in its receipt. Keep the expected
contract separate from recording rows so selection can compare the candidate
with an independently supplied request.

Carry recipe ID and revision, model, named instrument, instrument family,
arrangement, mode and voice. Preserve the explicit planner `lyrical` to library
`vocal` normalization. Do not derive missing fields from current recipes or
historical audio. Reject wrong performer/region and duplicate or conflicting
contracts during staging. Source libraries and installed manifests stay intact.

## Candidate selection

Keep `HM_Library.ChooseSlot`'s public signature and current ranking/lock behavior.
Add identity checks before a recording becomes eligible:

- A performer with an explicit contract or any versioned/partial recording
  identity uses strict selection. Require a complete contract and exact
  agreement with the candidate's identity. Missing, malformed or conflicting
  contracts return no slot. Legacy recordings cannot become a fallback for
  this performer.
- A performer with only legacy recordings and no explicit contract retains
  existing behavior. Unknown legacy fields remain unknown.
- The current controller always starts `IdleLuteStart`. Strict candidates
  must therefore stay within `plucked_string` and the supported solo plucked
  instrumental or voice arrangements. A named cittern or other suitable
  plucked instrument can use that animation family; flute/drum require a
  separate controller extension.

This approach does not require new saved Auto properties, an ESP binding change,
or a change to the 15 October actor-scan workaround. Keep contemporary recipe
revisions out of the actor registry derivation; ownership and actor identity
remain its responsibility.

## Build and promotion evidence

After implementing and compiling the candidate, add a versioned selection
capability descriptor to its build receipt, bound to the relevant source and
PEX hashes. Tests must target that exact isolated build. Teach promotion planning
to recognize only the verified descriptor/hash contract, not an arbitrary
capability boolean supplied in a receipt.

The current planner's versioned-library blocker remains in force until that
work exists. A future promotion path still needs an explicit library merge,
reviewed target hashes, backups and rollback. Compilation does not establish
runtime behavior or saved-game compatibility, and no installation is authorized
by this design note.

## Offline acceptance and unresolved engine evidence

Extend the compiled Papyrus VM fixtures to cover each identity mismatch,
missing/null/partial fields, legacy-only behavior, mixed strict/legacy rejection,
malformed/duplicate contracts, unsupported animation arrangements, mode
normalization, and existing locks, cooldowns and receipt ordering. Add staging
and promotion tests for wrong identity and capability/hash disagreement.

Inspect string comparison semantics in the actual Papyrus environment before
claiming byte-exact engine identity. The current Python test VM uses Python
string equality; passing that simulation alone is insufficient. Prefer a
contract representation whose comparison behavior is explicit and tested.

Capture the selected identity at performance start if receipts will include it.
Do not reread mutable library metadata at performance end and retrospectively
assign that newer identity to an earlier performance.

Relevant entry points: `tools/verify_offline_loop.py`,
`game_package/src/Scripts/Source/HM_Library.psc`,
`game_package/src/Scripts/Source/HM_Controller.psc`,
`game_package/tools/build_game_package.py`, `game_package/tools/build_registry.py`,
`game_package/tests/test_controller.py`, `game_package/tests/pex_vm.py`,
and `hold_music/promotion.py`.
