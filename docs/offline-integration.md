# Offline preparation and receipt loop

`tools/verify_offline_loop.py` exercises the existing performer registry,
read-only knowledge bridge, repertoire planner and recording library together.
It needs no game, MO2, network, credentials, provider calls, listening judgments
or generated music.

```sh
python tools/verify_offline_loop.py --output local/offline-loop-sven
python tools/verify_offline_loop.py --output local/offline-loop-lynly --performer lynly_star_sung
```

Choose a **new** output directory on each run. An existing directory is rejected
before its contents can be changed. The optional `--registry` selects a read-only
registry source. By default the real authored registry supplies the performer,
venue, regional identity, owner and animation family. Only registered Hold Music
plucked-string pilot performers are accepted.

## What the proof bundle contains

- `inputs.json`: performer identity, save/world scope, the synthetic recipe and
  model contract, and the registry hash.
- `SkyrimNet-offline-loop-fixture.db`: a minimal synthetic database with one
  actor-known quest success and another actor's private row. The bridge reads it
  with its normal read-only transaction; its hash must remain unchanged.
- `synthetic-silence.wav` and `source-library/`: one second of silent mono,
  16-bit, 44100 Hz PCM, synthetic lyrics and complete source metadata. This is a
  technical fixture, not a music sample or an admitted regional recipe.
- `knowledge-snapshot.json`: the scoped planner input, containing only synthetic
  information. The fixture's UUID is intentionally matched to the registry's base
  form; this does not verify a placed actor identity in a real save.
- `staged/library/`: a newly published copy validated with the real library API.
- `staged/Data/`: the selected WAV, lyrics and manifest in the game's library
  asset layout. It contains no runtime `receipts.json`, ESP or scripts.
- `staged/staging-receipt.json`: source and destination hashes, source provenance,
  recipe revision, model, named instrument, instrument family, arrangement,
  vocal mode and voice, performer/save scope, and checked WAV format.
- `receipt-completed/` and `receipt-interrupted/`: isolated copies used to feed
  each synthetic outcome back into the library and planner.
- `report.json`: the linked decisions, staging receipt, reconciliation results,
  explicit unresolved-identity example, checks and implementation source hashes.

The command exits nonzero if a check fails and prints a compact JSON summary.
Partial scratch output can remain after an error for inspection; it is never a
successful deployment receipt.

## Decisions demonstrated

The same snapshot first selects its cached recording under `cache_first`, then
proposes lyrics about the fresh actor-known quest under `topical_when_salient`.
The latter retains the cached fallback. Adding the proposed job to pending work
produces `wait`, without executing a job or creating a composition.
An independent synthetic prior lyric-attempt receipt activates the composition
cooldown; the planner then uses the cached recording instead of buying another
generation. Performance receipts and generation-attempt accounting stay separate.

Staging demands exact recipe ID, recipe revision, model, instrument family,
named instrument, arrangement, mode and voice. A missing legacy metadata field
is unverified and fails this strict boundary. Changes to any field are rejected;
the tool does not silently relabel an old recording to satisfy a new request.
The current pilot only accepts one visible plucked-string performer.
Production recordings can use their validated `source` import/provider metadata
as provenance; the proof's extra synthetic annotation is not required for real
recordings. This does not certify that their audible content matches the prompt.

The same fields now travel through the production planner request, pending-work
identity, executor journal/publication and library snapshot. This proof uses
that production request shape before checking the stricter plucked-string
staging boundary; it no longer supplies missing identity only at publication.
Staging now writes a `runtime_selection` contract from that frozen request and
independently derives each staged recording's `identity_key`. Both are recorded
in the staging receipt. The source library remains byte-for-byte unchanged;
historical rows are not relabeled. The [candidate Papyrus selector](candidate-runtime-identity.md)
checks this projection, while the installed controller remains unchanged.

Both completed and interrupted performance receipts count as a heard start for
the current planner's repeat policy. Re-ingesting the identical receipt is a
no-op; changing an existing scoped receipt ID is rejected. Immediately after a
performance, the song cannot repeat. At four hours the song window has elapsed,
but the fixture composition's topic remains blocked until 24 hours. At the topic
boundary the existing recording is eligible again. These history probes omit
the separate fresh-topic observation so the replay behavior is unambiguous.
No knowledge or composition is created by a performance receipt.

## Boundary of the evidence

`status: passed` proves this synthetic integration path, including preservation
of its source library and database. It does **not** mean installed, runtime
tested, musically approved or paid-provider tested. The staged Data folder is
only a library asset payload and must not be treated as a complete mod package.
Its synthetic audio is not intended for installation.

The receipt helper writes only the command's scratch branches. It is a serial
test helper, not a concurrent runtime receipt collector; the game still owns
the live receipt file. Actual controller ownership, Papyrus execution, audible
playback, interruption and cell/load cleanup require the separate runtime check.
Source versions, deployment and runtime evidence remain distinct.

Run the regression checks with:

```sh
python -m unittest discover -s tests -p test_offline_loop.py -v
```
