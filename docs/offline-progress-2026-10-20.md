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
  The source checkpoint is ready for synchronization; the synchronization
  receipt records final GitHub, Halcyon and Echo commit/tree identities.

## Next bounded work

1. Extend the read-only promotion plan toward a reviewed apply/rollback design
   that rechecks hashes and preserves runtime JSON, receipts, saves and audio.
   Test against synthetic installations only. The existing complete-mod installer
   is not an incremental promotion path, and the new candidate remains unapplied.
2. Add explicit reviewed import metadata where needed. The old importer model
   label is only a placeholder; it must not be used to infer a current recipe
   revision or sound source for historical audio.
3. Keep real actor identity and controller playback evidence separate. Actual
   MO2-injected ownership observation and the Sven runtime retest still need
   the relevant local/game session; they do not stop offline engineering.

Overnight follow-ups should inspect current changes and this checkpoint before
starting another unit of work. Continue in reversible, tested increments and
pause the overnight follow-up by 08:00 America/Chicago on 20 October.
