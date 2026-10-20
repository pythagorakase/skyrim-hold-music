# Candidate runtime identity integration

Candidate implementation checkpoint, 20 October 2026. Python staging and the
candidate Papyrus library now implement the contract below. This is not an
installed capability or a tested gameplay result. The installed Papyrus pilot
still selects by performer, region and mode. Build/test results are recorded in
the [overnight checkpoint](offline-progress-2026-10-20.md).

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

The manifest extension is `runtime_selection: {version: 1, contracts: [...]}`.
One active contract is allowed per performer, rejecting case aliases. Each
contract and projected recording carries `identity_key`: SHA256 of the compact
UTF-8 JSON array of these ten values in order: performer ID, region, recipe ID,
recipe revision, model ID, instrument family, instrument name, arrangement,
stored mode and voice. JSON preserves Unicode and uses `,`/`:` separators with
no extra whitespace. Python computes the expected contract from the decision
and the recording key from its own fields, then requires agreement.

`hold_music/runtime_contract.py` validates readable fields against the key.
`tools/verify_offline_loop.py` adds the extension only to its new staged copy and
receipt. It does not rewrite the source library or infer identity for old audio.
The [contract-migration review](contract-migration-review.md) separately audits
explicit changes against existing split-layer library files, retaining all
historical rows and unmentioned contracts without publishing its projection.

## Candidate selection

Keep `HM_Library.ChooseSlot`'s public signature and current ranking/lock behavior.
Add identity checks before a recording becomes eligible:

- A performer with an explicit contract or any versioned/partial recording
  identity uses strict selection. Require a complete contract and exact
  agreement with the candidate's projected identity. Missing, malformed or conflicting
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

The builder runs the dedicated compiled selector fixtures in a fresh subprocess
against its isolated candidate. A versioned capability descriptor binds the
source, PEX, disassembly, fixture, test VM and verification tooling hashes to the
named test results. It also records the disassembler provenance. Hashes are
checked again after tests; failed or skipped required tests prevent a successful
capability receipt. This is local build evidence, not authenticated attestation.

The promotion planner requires that exact evidence and validates the projected
library metadata. It reports candidate verification separately from installed
runtime support. Missing or stale evidence cannot clear the versioned-library
blocker. A future promotion path still needs an explicit library merge,
reviewed target hashes, backups and rollback. Compilation does not establish
runtime behavior or saved-game compatibility, and no installation is authorized
by this design note.

## Offline acceptance and unresolved engine evidence

Extend the compiled Papyrus VM fixtures to cover each identity mismatch,
missing/null/partial fields, legacy-only behavior, mixed strict/legacy rejection,
malformed/duplicate contracts, unsupported animation arrangements, mode
normalization, and existing locks, cooldowns and receipt ordering. Add staging
and promotion tests for wrong identity and capability/hash disagreement.

The installed SKSEVR `StringUtil.psc` warns that case-insensitive string
interning can lose the original casing, including character access. The
[official StringUtil source](https://github.com/ianpatt/skse64/blob/master/scripts/modified/StringUtil.psc)
and [native implementation](https://github.com/ianpatt/skse64/blob/master/skse64/PapyrusStringUtil.cpp)
corroborate that limitation. A character-by-character Papyrus comparison would
not fix it.

The candidate therefore compares the authoritative projected SHA256 key and
checks the readable fields as far as those APIs permit. It cannot independently
rehash raw JSON text or detect an arbitrary case-only text edit made without
updating its key. Staging/promotion enforce raw-field/key consistency and bind
the reviewed files; arbitrary post-review mutation is outside this guarantee.
The test VM now models case-insensitive comparisons, and a fixture explicitly
demonstrates this boundary. Neither simulated natives nor offline compilation
establish engine behavior.

Python requires integer schema version `1`. JsonUtil's available Papyrus type
predicates can reject strings, booleans and fractional values, but cannot
distinguish JSON `1` from `1.0`; the trusted projection always writes the integer.
The candidate also initializes missing receipt/trace arrays at index zero:
native `PathCount` returns `-1` for a missing or non-container path, as shown in
the [PapyrusUtil implementation](https://github.com/eeveelo/PapyrusUtil/blob/master/External.cpp).
The VM and compiled regression now reflect that behavior.

The selected identity is captured when the slot is chosen and appended as
`runtime_identity` on its receipt. Later library edits cannot retrospectively
relabel that performance. Legacy receipts keep their existing shape.

Relevant entry points: `tools/verify_offline_loop.py`,
`game_package/src/Scripts/Source/HM_Library.psc`,
`game_package/src/Scripts/Source/HM_Controller.psc`,
`game_package/tools/build_game_package.py`, `game_package/tools/build_registry.py`,
`game_package/tests/test_controller.py`, `game_package/tests/pex_vm.py`,
and `hold_music/promotion.py`.
