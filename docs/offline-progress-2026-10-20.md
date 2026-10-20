# Offline overnight development — 20 October 2026

The user authorized continued offline progress without waiting for regional-style
listening. The first checkpoint builds on the synchronized `6195383` baseline.
Musical recipes, active styles and listening results are unchanged.

## Implemented in the first checkpoint

- **Durable bounded generation:** a private SQLite journal records dispatch
  before a call and retains returned audio/lyrics plus accounting before local
  processing. Unknown outcomes and unpublished paid results block new spending.
  Explicit status, SQLite repair and saved-audio publication recovery need no
  provider. Crash tests cover abrupt process exit, hot rollback journals,
  interrupted accounting/publication and changed publication identity.
- **Ownership evidence and reversible handoff:** the VFS probe includes the
  actual opened Bard Singing configuration, hash and enabled value. Preflight
  can compare a captured observation with current inputs. A separate command
  defaults to a dry-run plan, preserves overlay edits and records exact backups
  for guarded rollback. Shared overwrite/data-mod effects are documented.
- **Offline integration proof:** a synthetic actor-knowledge database and silent
  PCM recording exercise the real registry, bridge, planner and library. The
  linked report covers cached selection, topical work, duplicate suppression,
  generation cooldown fallback, strict staging identity and completed/interrupted
  performance receipts. Both owned pilot performers have regression coverage.
- **Portable package build:** explicit stack/toolchain inputs replace the
  hardcoded scratch/install/profile paths. A read-only plan precedes an explicit
  build into a new workspace. Source, compiler and dependency provenance accompany
  the artifacts. Tests can select a candidate build without replacing the
  checkout's established build.

## Local evidence

- `local/portable-build-verified-20261020/build/build-receipt.json`: successful
  Caprica compilation, offline .NET/Mutagen round trip, disassembly and hashes.
  All 52 compiled package/controller/installer tests passed against this candidate.
- `local/offline-loop-overnight-sven-20261020/report.json`: all 13 integration
  checks passed; zero provider calls and no installation.
- `local/ownership-dry-run-20261020.json`: all 1,825 observed paths/inputs retained
  their prior bytes and timestamps. The plan proposes two changes but applies
  neither: disabling the older overwrite flag and removing the closed-session
  adapter overlay. The adapter's profile-data source is already disabled.
- `local/overnight-20261020-tests-final.log`: Windows general regression results.
  Independent review prompted additional recovery edge-case tests.

The installed controller PEX and source retain their verified 15 October
hashes. No Skyrim/MO2 launch, active configuration change, audio purchase or
style admission was part of this checkpoint. Candidate builds and proof audio
remain in ignored local workspaces.

## Second checkpoint: production recording identity

- Production requests now carry recipe revision, actual named instrument,
  instrument family, arrangement, voice and model through cache counts,
  repertoire selection, pending recording identity, durable jobs, publication
  and library snapshots. Legacy metadata stays explicitly unknown, readable and
  unmodified; partial new metadata is rejected.
- The revision fingerprints the exact production prompt direction and identity
  from one palette read. New dispatch rejects stale plans. Vocal direction is
  frozen before lyric generation and retained through recovery, so a palette
  edit cannot relabel an already dispatched request. Known lyrics and topic
  deduplication remain independent of the recording's sound source.
- Explicit non-lute registry instruments are reported as unsupported by the
  current preparation executor. The active recipes and prompt output are
  unchanged; a named plucked sound source can still use the lute animation.
- Knowledge-export requests now use the same versioned recipe and regional
  mode policy. The staging helper accepts validated source provenance from
  ordinary prepared recordings, without requiring a synthetic annotation.
- Added a complete production-plan → fake provider → journal/publication →
  library/planner → strict staging check for Sven and Lynly, plus metadata,
  stale-plan, recovery and standalone-adapter regression coverage.

This is an offline production contract. The installed Papyrus pilot still
selects by performer/region/mode and needs separate integration before those
runtime choices enforce every field. No installed files or configuration were
changed. Historical auditions and style admission are unaffected.

Second-checkpoint validation:

- **461 general tests on Windows and 461 on macOS:** 460 passed and one expected
  platform-specific skip on each host. The new standalone adapter test runs
  Python in isolated mode outside the repository.
- **1,274 workshop prompt contracts** passed on both hosts. Existing golden
  regional prompts passed, and regenerated dashboard HTML retained SHA256
  `baf0aaf094f70f3cf79c8ea6115cbfba724d47c9c00d7e30a70df86268679133`.
- All **13 offline-loop checks** passed using the expanded production request.
  The additional production preparation/staging regression covers both owned
  pilot performers using fake provider responses and silent PCM conversion.
- Windows log: `local/identity-checkpoint-20261020-tests-final.log`.
  Proof: `local/offline-loop-identity-sven-20261020/report.json`.
  Echo tests used an isolated source export under
  `/tmp/holdmusic-identity-20261020.O1phcg`; synchronization does not copy its test
  libraries or journal fixtures into the real checkout.
- Installed controller PEX/source hashes still match the 15 October workaround.
  No compiled game-controller code changed in this checkpoint; the first
  checkpoint's separately tested portable build remains a candidate only.

## Third checkpoint: reviewed retained jobs and promotion planning

- Added a read-only review of retained, versioned lyric jobs. Continuation uses
  the original scope, parsed saved lyrics, frozen instrument/recipe identity and
  prompt. A token binds retained state, budget, cap, ffmpeg option, receipt source
  and session boundary. Apply consumes that authorization and reserves the first
  music call atomically; repeating it cannot resubmit. Historical lyric cost is
  separate from the additional music budget.
- Added reviewed operator reconciliation for a single uncertain call with no
  response or audio. A private billing/request attestation can close the attempt
  without contacting a provider. Append-only review records preserve original
  calls, context and accounting; reports distinguish operator evidence from
  provider verification and redact evidence text. This does not discard malformed
  returned results or create automatic retries.
- Added a read-only game-package promotion planner. It verifies package and
  source provenance, compares allowed static files and inventories protected
  runtime JSON, receipts, audio, settings, profile lists and saves. It has no
  apply operation. Versioned libraries are blocked while the Papyrus pilot lacks
  the corresponding selection contract.
- Two real read-only plans observed identical hashes/timestamps across 696 paths,
  including 634 preservation entries. They proposed three PEX replacements;
  eight other static files were unchanged, and user settings were preserved.
  No changes were applied. Existing legacy recordings did not trigger the
  versioned-library blocker; that is not runtime compatibility evidence.
- Focused CLI tests use fake responses to exercise lyric continuation,
  idempotence, operator closure, redaction and explicit authorization flags.
  Known composition/receipt collisions and malformed topic, source and clock
  fields now block before paid dispatch. Independent review reran those
  reproductions and found no remaining blockers.

Third-checkpoint validation:

- **523 general tests on Windows:** 520 passed, three expected skips
  (two symlink-privilege cases and the existing platform-specific case).
- **523 general tests on macOS:** 522 passed, one expected platform-specific
  skip. Both symlink rejection cases ran successfully there.
- **1,274 workshop prompt contracts** passed on both hosts. The dashboard
  remains at SHA256
  `baf0aaf094f70f3cf79c8ea6115cbfba724d47c9c00d7e30a70df86268679133`.
- Windows log: `local/reviewed-jobs-checkpoint-20261020-tests-final.log`.
  Echo tested source commit `ca8a96448008c54dbccf7529ff4adda7a32f7a89` in
  `/tmp/holdmusic-reviewed-jobs-20261020.YpUSKB/source`. Only this verification
  documentation changed afterwards. Logs and synchronization receipt belong in
  `local/reviewed-jobs-publish-20261020/`.
- Actual read-only promotion report:
  `local/game-promotion-review-20261020.json`; observed snapshot SHA256
  `8f58bc814082ac686a6837e05fff20450edce7cc84a7230f3e4527ff533fa3b5`.
- Installed controller PEX/source hashes still match the 15 October workaround.
  No controller code, installed files, active configuration, recipes or
  audition data were changed. Paid provider calls: zero. The candidate build
  and three proposed PEX replacements remain unapplied.

## Fourth checkpoint: candidate runtime recording identity

- Added explicit runtime contracts projected from frozen planner requests into
  new staged payloads. Each recording receives an independently derived SHA-256
  identity key. Strict metadata validation rejects missing/null fields, duplicate
  performers, unsupported arrangements and stale readable-field/key pairs.
  Source libraries and historical audio remain unchanged.
- Added candidate Papyrus selection for that projection, retaining current
  ranking, cooldowns and locks. A versioned performer cannot fall back to legacy
  rows. Unaffected legacy performers keep their existing behavior. Receipts
  capture selected identity before subsequent manifest changes. The controller
  still uses the supported plucked-string animation family.
- Added 24 independent compiled-script regressions and an artifact-bound
  verification report. The builder requires every named fixture to pass without
  skips, then binds results to package, source, disassembly, fixtures and helpers.
  Promotion revalidates the evidence; a receipt flag alone cannot claim support.
- Documented native limitations: Papyrus string interning cannot reliably
  preserve raw text casing, so the runtime uses the validated SHA-256 projection.
  Python verifies exact readable metadata. Native numeric predicates cannot
  distinguish schema version `1` from `1.0`; the projection writes integer `1`.
  Corrected the VM's missing-array `PathCount` result to `-1` and fixed candidate
  receipt/trace initialization to start at zero.
- Read-only promotion now separates candidate verification from installed
  runtime support. Two real plans observed the same 708-path snapshot and 634
  preservation entries. A valid synthetic projected library clears the identity
  blocker but retains the unsupported-library-merge blocker. Nothing was applied.

Fourth-checkpoint validation:

- **557 general tests on Windows:** 554 passed, three expected platform skips.
- **557 general tests on macOS:** 556 passed, one expected platform skip.
  The final suite includes the independent review's regression: a legacy-only or
  empty library with an explicit runtime contract still requires candidate
  capability. The planner cannot silently let an old selector ignore it.
- **76 compiled game-package tests on each host:** all passed against
  `local/runtime-identity-build-20261020-02/build`; its required 24-test subset
  also passed inside the builder before the capability receipt was written.
- **1,274 workshop prompt contracts on each host** passed; dashboard SHA256 remains
  `baf0aaf094f70f3cf79c8ea6115cbfba724d47c9c00d7e30a70df86268679133`.
- All **14 offline-loop checks** passed in
  `local/offline-loop-runtime-identity-20261020/`, including independent contract
  projection and unchanged source library/database.
- Echo validated the exact copied candidate and its report in
  `/tmp/holdmusic-runtime-identity-20261020.d0S6Jf/`, with the source exported from
  `120f031` plus the reviewed two-file promotion fix. Build verification SHA256:
  `f9e5a94742927917a9ee0cfc267024740e58418fea0291285504cf9fa146d0de`.
  The 14-check synthetic proof also passed there. Cross-host test logs and the
  final synchronization receipt are retained in
  `local/runtime-identity-publish-20261020/`.
- Logs: `local/runtime-identity-checkpoint-20261020-tests-final.log`,
  `local/runtime-identity-game-tests-20261020.log` and
  `local/runtime-identity-build-20261020-02.log`. The first fresh compile exposed
  Caprica's unsupported carriage-return escape; the successful candidate uses
  `StringUtil.AsChar(13)`. The failed workspace is retained separately.
- Promotion reports: `local/runtime-identity-promotion-review-20261020.json` and
  `local/runtime-identity-promotion-staged-20261020.json`. Unchanged observed
  snapshot: `595c3f8abd73b3e1f756736ed8e13eb4fd20e672b4b23aa51fc2eda5badb9488`.
- Installed controller PEX/source hashes still match the 15 October workaround.
  Candidate artifacts remain local and unapplied. Paid provider calls: zero.
  No installed files, active configuration, recipes or auditions were changed.
  Source checkpoint `30f2418` was synchronized to GitHub, Halcyon and Echo.
  The synchronization receipt records the exact commit/tree identities.

## Fifth checkpoint: reviewed static promotion and rollback

- Added a separate static transaction command. Review/status create no files;
  apply and rollback each need an operation-specific token. Promotion rechecks
  candidate, source, target and protected-file observations against the review.
  Rollback rechecks its retained journal/backups and current target/context.
  Existing read-only promotion planning remains unchanged.
- Mutations are limited to allowlisted static files plus a fixed per-target
  control directory. A kernel writer lock prevents competing transactions.
  Exact original-byte backups and durable per-file intent precede replacement.
  Interrupted work remains observable and blocks another apply; recovery never
  automatically resumes an interrupted update.
- Rollback uses retained backups and current target observations, even when the
  candidate/source checkout has moved or disappeared. It preserves new receipts,
  traces, settings, audio and saves. Third-party static edits, corrupt required
  backups or changed profile context block restoration before other files move.
  Prior terminal journals and backups remain available after a later transaction.
- Independent review caught journal parent-path traversal, a missing guard for
  newly created script overrides, final-write changes and rollback accepting
  an immediate external edit as successful restoration. Regressions now exercise
  those cases. Journal error reporting also preserves concurrent journal edits.
- Process enumeration is required for execution and fails closed on unknown or
  malformed results. Tests inject fake process observations; the CLI has no
  bypass option. Real subprocess deaths after replacement during both apply and
  rollback left durable journals, released kernel locks and recovered through
  a fresh reviewed rollback.
- A synthetic round trip promoted ten fixture static files and restored every
  original target byte. Proof:
  `local/promotion-fixture-proof-20261020/proof.json`.
- Actual installation **inspection only** proposed four replacements: three PEX
  files and `HM_Library.psc`. It observed the same 708-path snapshot as the fourth
  checkpoint, including 634 preservation entries, and created no transaction
  directory. Reports: `local/static-promotion-review-20261020.json` and
  `local/static-promotion-status-20261020.json`. Nothing was applied to the game.

Fifth-checkpoint validation:

- **596 general tests on Windows:** 593 passed, three expected platform skips.
- **596 general tests on macOS:** 595 passed, one expected platform skip.
  These include 39 new transaction, independent safety and CLI cases, including
  abrupt process termination during both apply and rollback.
- **1,274 workshop prompt contracts on each host** passed. Existing musical
  recipes, arrangements and the dashboard are unchanged.
- Echo tested source commit `fec2d09` in the isolated workspace
  `/tmp/holdmusic-static-promotion-20261020.idGXfw/source`; subsequent changes
  only clarify documentation and record results. The existing Echo checkout
  and its auditions were not used as test fixtures.
- Logs: `local/static-promotion-checkpoint-20261020-tests-final.log` and
  `local/static-promotion-publish-20261020/{general-tests,prompt-tests}.log`.
  The latter folder also retains the source synchronization receipt.
- The compiled candidate and capability receipt are unchanged from the fourth
  checkpoint; its 76 compiled package tests were not repeated for this
  Python-only transaction change. The fresh read-only plan verified the
  candidate evidence and observed the unchanged installation snapshot.

The [transaction documentation](game-promotion-transactions.md) records the
recovery boundaries. Empty parent directories may remain after rollback; there
is no recursive directory deletion or arbitrary historical rollback command.
Library merging, profile enablement and actual runtime compatibility remain
separate requirements. This checkpoint changes no musical recipe or audition.
Source checkpoint `4a020e9` is synchronized across GitHub, Halcyon and Echo;
`local/static-promotion-publish-20261020/verification.json` records the identities
and unchanged audition inventory.

## Sixth checkpoint: reviewed imports and additive library planning

- Existing-audio import now defaults to read-only CLI review. Explicit apply
  binds the source, raw lyrics, complete optional metadata, converter and current
  library/receipt state. Source bytes are frozen for conversion and inputs are
  checked again before publication. Fixtures use a fake converter and no provider.
- New imports without asserted provenance use an unknown model rather than the
  former Lyria placeholder. Historical rows are unchanged. Explicit metadata
  includes recipe revision, named instrument, family, arrangement and voice,
  with file hashes and performer/region/mode/gender cross-checks. It records
  operator assertions; no current palette values or provider evidence are inferred.
- Import remains an offline source-library operation. Destinations carrying
  `runtime_selection` are rejected; staging must explicitly derive the playback
  contract from a planner request. Import publication uses the existing serial
  writer and does not claim the static transaction's crash-recovery guarantees.
- A separate read-only merge planner compares two explicit flattened libraries,
  validates projected incoming identity/assets and proposes deterministic free
  slot remapping. Existing rows, history, receipt reservations and orphan assets
  are preserved. Incoming generation/performance history is not copied.
- Conflicting contracts and implicit activation over an existing legacy performer
  block additive planning. New-performer contract additions remain proposed
  actions only. Snapshot tokens identify the review; there is no merge apply
  command, and static package promotion still rejects library merging.
- Independent review distinguished compatibility from individual audio takes:
  different renditions may share a recipe and composition, while exact matching
  content can be recognized as already present. Existing duplicate destination
  rows remain untouched. The complete proposed manifest is validated after
  combination; nullable legacy fields are preserved and any resulting projection
  incompatibility blocks the proposal instead of rewriting historical metadata.
- Import publication explicitly requires an unoccupied slot, including a fresh
  check after conversion/staging. A competing publication injected after final
  import preflight was preserved and caused the import to stop. Other library
  writers must still be stopped; this is not an arbitrary-writer transaction.

Sixth-checkpoint validation:

- **672 general tests on Windows:** 667 passed, five expected platform/capability
  skips, including unavailable Windows fixture symlinks.
- **672 general tests on macOS:** 671 passed, one expected platform skip.
  The source-bound converter-symlink and library-alias cases ran there.
  This checkpoint adds 76 cases across import, slot protection, merge planning,
  CLI, independent safety and end-to-end integration.
- **1,274 workshop prompt contracts on each host** passed. Dashboard SHA256
  remains `baf0aaf094f70f3cf79c8ea6115cbfba724d47c9c00d7e30a70df86268679133`.
- The retained synthetic proof at
  `local/import-merge-fixture-proof-20261020/proof.json` passed all six checks.
  It links reviewed import, exact repertoire selection, staged source provenance
  and a proposed slot-1-to-slot-5 remap after preserving occupied, interrupted
  and orphaned slots. The real merge CLI also printed the fixture review without
  writing either library.
- Echo tested source commit `3a147c4` in
  `/tmp/holdmusic-import-merge-20261020.nlhy2o/source`; subsequent edits only
  record validation. Logs and synchronization evidence are retained in
  `local/import-merge-publish-20261020/`. Windows full-suite log:
  `local/import-merge-checkpoint-20261020-tests-final.log`.
- The compiled candidate and measured capability inputs are unchanged; compiled
  package tests were not repeated for this Python-only checkpoint. Installed
  controller PEX/source hashes retain the prior workaround, and no real promotion
  control directory was created. No installed files, active configuration,
  musical recipes, auditions or paid provider state were changed.

Source checkpoint `515b3f9` is synchronized across GitHub, Halcyon and Echo;
`local/import-merge-publish-20261020/verification.json` records the final identities
and unchanged audition inventory.

## Seventh checkpoint: inspecting the effective installed library

- Added a read-only profile inspector that resolves manifest, receipt history,
  trace, all 24 WAVs and all 24 lyric sidecars independently through overwrite,
  enabled mods and an optional explicit base Data directory. It keeps source
  paths and hashes rather than flattening assets into a misleading source library.
- File modification time does not affect priority. Differing shadowed copies are
  reported; a malformed effective file cannot fall back to a valid lower copy.
  Unknown historical identity remains unchanged. Occupied, receipt-reserved and
  orphaned slots remain reserved without assuming live game locks have cleared.
- Optional captured handles are compared only with known current candidates.
  Report-supplied paths never authorize arbitrary reads. Old captures cannot
  override current loose-file priority or establish write routing, MO2 injection,
  controller ownership or runtime playback.
- Extended the existing version-2 VFS capture with all lyric sidecars and trace,
  plus explicit required/presence fields. Optional absence is allowed; unreadable
  files, required missing inputs and failure to resolve an opened handle still
  fail. Package-manifest paths and hashes are validated before target reads.
- Actual selected-profile inspection found four recordings and no conflicting
  loose copies. Slot 1 declares a lyric hash but has no effective loose lyric
  sidecar. All four rows retain historical metadata without the new full recipe
  identity. This is a migration input gap, not evidence of the earlier CTD's
  cause; no installed asset or metadata was changed.

Seventh-checkpoint validation:

- **728 general tests on Windows:** 721 passed, seven expected platform/capability
  skips. **728 on macOS:** 726 passed, two expected platform/filesystem skips.
  The 56 new cases cover the inspector, CLI, independent adversarial review,
  split-layer integration and expanded probe. Case-distinct directory fixtures
  skip when the host volume cannot represent them; Windows symlink fixtures
  also skip when unavailable.
- **1,274 workshop prompt contracts on each host** passed. The dashboard and
  musical recipes are unchanged.
- All seven checks in `local/installed-library-fixture-proof-20261020/proof.json`
  passed. The retained fixture independently resolves metadata, audio and lyrics,
  ignores newer lower-priority copies, reserves occupied/receipt/orphan slots,
  matches a synthetic handle capture and preserves all input bytes and mtimes.
  The matching capture deliberately leaves installation/VFS/runtime flags false.
- Actual selected-profile inspection observed 1,821 loose layers, eight relevant
  files and 6,275 directory states, retaining the three standard DLC entries as
  informational foreign content. Report:
  `local/installed-library-publish-20261020/installed-library-review-final.json`.
  It contains one blocker: the missing slot-1 lyric sidecar. No fallback copy,
  source-library substitution or inferred historical identity was used.
- Echo tested source commit `0253ed0` in the isolated workspace
  `/tmp/holdmusic-installed-library-20261020.resmmR/source`; subsequent changes
  only record validation. Logs and the final synchronization receipt are kept in
  `local/installed-library-publish-20261020/`. Windows suite log:
  `local/installed-library-checkpoint-20261020-tests-final.log`.
- The compiled candidate and measured capability inputs are unchanged; compiled
  package tests were not repeated for this Python/probe-only checkpoint.
  Installed controller PEX/source hashes retain the prior workaround and no
  promotion control directory was created. No MO2/game process was launched,
  no installed files or active configuration were changed, and no paid audio
  or audition was generated or discarded.

Source checkpoint `043afe8` is synchronized across GitHub, Halcyon and Echo;
`local/installed-library-publish-20261020/verification.json` records matching
source trees, unchanged inspected inputs and the preserved audition inventory.

## Eighth checkpoint: explicit performer-contract migration review

- Added a read-only migration review based on a fresh installed-library
  projection and an explicit proposal. Proposals upsert complete performer
  contracts only; unmentioned contracts remain in order and all recordings,
  historical metadata, generation history and unknown manifest fields survive.
- Each retained row has before/after candidate identity compatibility and
  concrete exclusion reasons. Valid assets, stored playback flags, receipt/slot
  reservations, unknown live locks and actual selection remain separate.
  The candidate's legacy path and strict path are identified explicitly.
- Malformed current contract blocks cannot be silently repaired by a proposal.
  Partial or explicitly nullable identity remains untouched and can block the
  complete prospective manifest. Case-only performer changes are ambiguous.
  Changed performers without matching valid asset candidates are blocked.
- This is a candidate identity audit, not a claim that the installed controller
  enforces those rules or a prediction of ranking, save knowledge or playback.
  There is no apply option, recording import, identity backfill or provider call.
- The [publication design](library-publication-design.md) records the next
  boundary: explicit split destinations, shared-profile impact, fresh ownership
  and process evidence, assets first, manifest last, and recovery that preserves
  later gameplay history. The existing static transaction and full installer
  retain their separate limits.

Eighth-checkpoint validation:

- **769 general tests on Windows:** 761 passed, eight expected platform/capability
  skips. **769 on macOS:** 767 passed, two expected platform/filesystem skips.
  This adds 41 migration, independent safety, CLI and integration cases.
- **1,274 workshop prompt contracts on each host** passed.
- All eight retained proof checks passed at
  `local/contract-migration-fixture-proof-20261020/proof.json`. The fixture
  changes only Sven's proposed contract: his revision-1 recording loses identity
  compatibility, revision 2 gains it, legacy metadata stays unknown, and both
  unmentioned strict and legacy performers remain unchanged.
- Four fixture selections also matched the unchanged compiled candidate:
  Sven before/after selected slots 1/2, and the unmentioned strict/legacy
  performers kept slots 4/5. This used the Windows disassembly VM with mocked
  natives and a freshly revalidated artifact capability receipt, not Skyrim.
  Verification hash remains
  `f9e5a94742927917a9ee0cfc267024740e58418fea0291285504cf9fa146d0de`.
- Echo tested source commit `d1bd8db` in
  `/tmp/holdmusic-contract-migration-20261020.en7cXF/source`; later edits only
  record validation. Logs and synchronization evidence are retained in
  `local/contract-migration-publish-20261020/`. Windows suite log:
  `local/contract-migration-checkpoint-20261020-tests-final.log`.
- A fresh read-only installed inspection matched the seventh checkpoint's
  snapshot token and single missing-lyrics blocker. No real performer proposal
  was invented or applied. Installed controller, configuration, recordings,
  recipes and auditions remain unchanged; paid provider calls remain zero.

## Next bounded work

1. Build the first fixture-only split-library publication plan/transaction for
   one new instrumental recording in a genuinely free slot. Bind explicit
   destinations, staged identity, migration decisions, profile impact and
   current receipts without widening the static-file allowlist.
2. Prove manifest-last commit and conservative recovery across real subprocess
   crash boundaries. Preserve later receipts/trace/history and newly played
   assets, block third-party manifest changes, and recover without source files.
   No live apply command until the routing/ownership review is concrete.
3. Keep the candidate unapplied and real actor/controller evidence separate. Actual
   MO2-injected ownership observation and the Sven runtime retest still need
   the relevant local/game session; they do not stop offline engineering.

Overnight follow-ups should inspect current changes and this checkpoint before
starting another unit of work. Continue in reversible, tested increments and
pause the overnight follow-up by 08:00 America/Chicago on 20 October.
