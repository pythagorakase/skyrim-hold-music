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

## Next bounded work

1. Add explicit reviewed continuation for retained lyrics and reconciliation
   of unknown provider outcomes. Keep paid dispatch separate, explicitly
   authorized and bounded; test with fake providers only. Do not delete journal
   records to bypass a pending result. Preserve the frozen production identity
   and prompt while continuing an already reviewed job.
2. Extend portable deployment/promotion plans without changing installed game
   files. Preserve runtime JSON, receipts, saves and existing audio. Inspect how
   a candidate Papyrus controller should enforce the versioned selection fields;
   accepting arbitrary library metadata is not runtime compatibility.
3. Add explicit reviewed import metadata where needed. The old importer model
   label is only a placeholder; it must not be used to infer a current recipe
   revision or sound source for historical audio.
4. Keep real actor identity and controller playback evidence separate. Actual
   MO2-injected ownership observation and the Sven runtime retest still need
   the relevant local/game session; they do not stop offline engineering.

Overnight follow-ups should inspect current changes and this checkpoint before
starting another unit of work. Continue in reversible, tested increments and
pause the overnight follow-up by 08:00 America/Chicago on 20 October.
