# Performer registry and recording library (T0)

This is an offline format and Python API, using only Python 3.10+ standard-library
modules. It does not install a game package, generate music, or establish in-game
playback. The future installed library root is the profile's
`hold-music-runtime/library`; callers currently pass an explicit root.

## Authored performers

`game_adapter/data/performers.json` has `version: 1`, a descriptive `scope`, and
`performers`. Each entry contains `id`, `name`, `form`, `venue`, `region`, `gender`,
`instrument`, `traditions`, `owner`, `source`, and `notes`. IDs are stable machine names;
display names are not game identities. `form` is either null (unresolved, explained
in notes) or `{ "plugin": "Skyrim.esm", "id": "0x0001A670" }`: a plugin-local
**base NPC form**, without a load-order prefix. Biography filename suffixes and
placed-reference IDs must not be substituted for base IDs.

The 21 entries cover the audit's vanilla/Hearthfire table, including Sven, Lynly,
College staff/students, and traveling Talsgar. Base forms were resolved from the
read-only Halcyon artifact
`C:\MGO\codex-investigations\20261008-bard-roster\roster.json`. All are resolved.
Gender facts absent from the audit text are marked `Gender source: vanilla`.
One primary instrument is authored per performer; College registration does not
claim a routine inn performance role. Giraud's voice role means recitation.

Regions are authored from venue towns. Non-null exact venue entries in
`game_adapter/data/locations.json` must agree; ambiguous/null names are allowed.
Sven's Sleeping Giant Inn is Whiterun and Karita's Windpeak Inn is the Pale, with
ambiguity notes on both. House venues use Falkreath, Hjaalmarch and the Pale.
Talsgar has null venue/region and the traveling `nord` tradition. Luaffyn uses
`eastmarch` and `dunmer`. All tradition IDs exist in the palette's `existing` list;
a region label does not assert that Ogmund performs Reachfolk music.

`load_registry(path=DEFAULT_PATH)` returns a `Registry` with `.performers`,
`.find_by_name(name)` (case-insensitive exact), and `.find_by_form(plugin, id)`
(case-insensitive plugin and hexadecimal string or integer ID). Missing matches
return None. Invalid registry structure, enums, IDs or forms raise ValueError;
I/O and malformed JSON errors are explicit to the caller.

The game registry is a generated projection: `python -B
game_package/tools/build_registry.py` validates this source through `load_registry`
and writes schema version 2 with integer form IDs and flat `region`/`venue`.
Plugin identities (including HearthFires.esm) are preserved. The package build
checks the tracked file against a fresh derivation and fails on drift.

## Ownership

Every performer requires an authored `owner` string, exactly `hold_music` or
`skyrimnet`; ownership is not derived from SkyrimNet's predicate. Sven and Lynly
Star-Sung belong to `hold_music`; all other registered performers belong to
`skyrimnet`. The game controller performs only for `hold_music` performers;
`skyrimnet` performers stay with SkyrimNet's bard system until the T3 hand-off.
The generated game registry carries the authored field unchanged.

## Library files

`library.json` contains `version: 1`, `slots: 24`, and `recordings`. A recording is:

```json
{
  "slot": 1,
  "file": "hm_slot_01.wav",
  "performer_id": "mikael",
  "region": "whiterun",
  "mode": "vocal",
  "gender": "male",
  "duration_seconds": 95.4,
  "composition_id": "example-composition",
  "lyrics_sha256": null,
  "recipe_id": "whiterun/vocal",
  "model_id": "google/lyria-3-pro-preview",
  "created_at": "2026-10-09T12:00:00Z",
  "source": {"kind": "import", "path_or_request_id": "source.mp3"},
  "playable": true
}
```

Modes are `vocal`, `wordless`, and `instrumental`; genders are `male` and `female`.
Regions are the nine hold IDs. Composition IDs identify immutable content:
conflicting regions or non-null lyrics hashes under one ID are rejected. A vocal
and instrumental rendition can share a composition; its vocal words are retained
in the planner's composition while each recording keeps its own mode. The importer
adds `source.sha256`, the SHA256 of the original MP3 bytes. `source.kind` may also
be `generated`, with the provider request ID in `path_or_request_id`.
Unknown extra keys are preserved in the manifest when adding recordings.

Production preparation now writes `recipe_revision`, `instrument_family`,
`instrument_name`, `arrangement` and `voice` alongside the recipe/model IDs.
The revision identifies the frozen production prompt direction and identity,
excluding the particular lyrics. `instrument_name` is the actual requested
sound source, such as `cittern`; `solo_lute` and `solo_lute_and_voice` name
the visible plucked-string animation arrangement. They do not require a
literal lute timbre. The current executor emits `plucked_string`; the library
accepts other nonempty family identifiers for future explicitly supported
arrangements without asserting their game compatibility.

The revision/family/name extension is all-or-nothing: all three may be absent
or null for legacy data, or all three must be nonempty strings with explicit
arrangement and voice. Partial metadata blocks publication. Legacy rows remain
readable, are not rewritten, and cannot satisfy a versioned production request.
Matching an old six-field request is only legacy compatibility, not proof of
recipe revision or instrument identity. No old recording is automatically
upgraded using today's palette.

These checks apply to Python planning, preparation and strict offline staging.
The installed Papyrus pilot still selects by performer/region/mode; it does not
yet enforce this full contract. A structurally valid library is not automatically
a compatible deployment for that controller.

Slot files are exactly `hm_slot_01.wav` through `hm_slot_24.wav`: mono, 16-bit PCM,
44100 Hz. `wav_info()` uses `wave` to inspect the format, calculate frame duration,
and reject truncated audio. Duration must match the manifest within one sample.
On each read, `playable` is recomputed from the actual asset rather than trusted
from disk. A missing, malformed, truncated or incompatible WAV is not playable.

Vocal words are UTF-8 bytes in `hm_slot_NN.lyrics.txt`; `lyrics_sha256` hashes those
exact bytes. Instrumental and wordless recordings have no words and use null.
An import may omit lyrics, but the planner cannot use a vocal composition until
its nonempty sidecar and matching hash are supplied. Such entries are omitted
from snapshots with an explanatory `.problems` entry, never fabricated lyrics.
A sidecar mismatch is also reported and excluded from the planner snapshot.

## Receipt contract and slot reuse

The game owns `receipts.json`; the library never rewrites it. Its shape is:

```json
{
  "version": 1,
  "performances": [{
    "id": "1:0",
    "slot": 1,
    "performer_id": "mikael",
    "region": "whiterun",
    "composition_id": "example-composition",
    "save_id": "save-identity",
    "world_id": "continuity-identity",
    "at_hours": 123.5,
    "outcome": "completed",
    "started_real_seconds": 115.0
  }]
}
```

The exact game path is `Data/SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json`.
Papyrus appends to `performances` and explicitly calls JsonUtil.Save; it emits
only the fields above. `id` is `<slot>:<zero-based array index>`. `at_hours` is
required, finite, nonnegative game time (`Utility.GetCurrentGameTime() * 24.0`).
`started_real_seconds` is the process-local start clock. Papyrus has no wall
clock and does not write `written_at`; the helper accepts that field optionally
as ISO UTC provenance but never uses it for locks. `region` and
`started_real_seconds` are tolerated metadata. Outcomes are exactly `completed`
and `interrupted`. The optional MCM world ID may be an empty string.

Unknown extra keys are tolerated by the helper. Missing receipts mean no history.
Malformed JSON, including trailing partial-write garbage, rejects the entire
document, reports problems, and blocks publication/reuse without crashing the
reader. Invalid individual rows are reported and excluded and also block writes.
Callers must inspect `.problems` before acting on snapshots with incomplete history.
Real JsonUtil serialization and concurrent reads remain runtime verification gates.

Construct `Library(root, session_receipt_index=N)` or pass that index to `load()`.
The helper records the full receipt-array length N when a game process session
starts. Every receipt at original array index >= N reserves its slot, regardless
of outcome, timestamp, save or world (engine caching spans save loads). The index
is a nonnegative integer; it is not an index into filtered valid rows. Loaded
recordings carry derived `session_locked` flags; slots remain reserved even when
no manifest entry names them. Do not advance N on a save load within one process.

`free_slots()` returns ascending unoccupied/unreserved slots, excluding orphan
WAVs and sidecars. It never automatically evicts a recording. `add_recording()`
uses the next free slot unless `slot=` explicitly requests replacement. Any
replacement requires a session boundary; locked slots cannot be rewritten.
A new session boundary permits replacement of old-session slots. Only the caller
can establish a real game-session boundary; it must not move it merely to bypass
a lock.

Publication stages files under the library root, replaces the WAV/sidecar, then
writes `library.json` through a flushed/fsynced temporary file and `os.replace`.
Ordinary publication exceptions restore the previous assets and leave the old
manifest intact. This is a **single-writer API**, not a multi-process transaction:
the future executor must serialize helper writes and coordinate replacements
with the game receipt writer. A process/power failure between asset and manifest
publication can leave an orphan or mismatch, which validation reports or slot
allocation preserves; multi-file crash recovery is not claimed.

## Python API and planner mapping

- `Library(root, session_receipt_index=None, receipts_path=None)` optionally reads
  performance receipts from a separate path; `.receipts_source` is the `Path`
  used, defaulting to `<root>/receipts.json`. Relative overrides are relative to
  the working directory. Missing overrides mean empty history, not fallback to
  the root file. The library never writes either receipts file. MO2 discovery
  and runtime evidence collection are described in [evidence](evidence.md).
- `Library(root).load()` refreshes state and returns the instance. `validate()`
  refreshes and returns a list of problems; file-content problems do not raise.
- `recordings_for(performer_id=None, region=None, mode=None, gender=None)` refreshes
  and filters by exact values. Returned rows include computed asset/session flags.
- `add_recording(wav_path, *, performer_id, region, mode, gender, composition_id,
  recipe_id, model_id, source, lyrics=None, slot=None, created_at=None,
  generation_receipts=(), require_unoccupied=False, **extra)` validates, copies
  and publishes an entry. Import uses `require_unoccupied=True` to forbid the
  replacement API and recheck availability before publication. This guard does
  not make arbitrary concurrent writers safe; the serial-writer requirement
  still applies.
- `snapshot(performer_id, save_id, world_id, now_hours, request)` returns a dict
  accepted by `hold_music.repertoire.Snapshot.from_dict` and `plan`.

Snapshots contain this performer's recordings and one composition per distinct
eligible composition ID, with `known_by: [performer_id]`, the sidecar words, and
no inferred observations. Planner recording IDs are `slot:01`, etc. Library
`vocal` becomes planner `lyrical`; region becomes tradition. Arrangement and
voice are copied when explicit. Missing arrangement becomes `unknown`; missing
voice becomes `none` for instrumental mode and `unknown` otherwise. Gender alone
does not establish a recording's voice identity. Recipe/model IDs and the
revision/family/name extension are copied exactly (null when legacy), never
taken from the caller's request. The request argument uses the planner's Request
shape.

Offline prepared material is baseline knowledge at game hour zero in the requested
save/world. UTC `created_at` is provenance, never converted into an in-game time.
Optional recording `save_id` and `world_id` together restrict runtime material to
that timeline; `created_at_hours` supplies its in-game creation/knowledge time.
Future executors must supply these for material acquired during play. Foreign
scopes and future recordings are excluded before assembling known compositions.

Completed and interrupted performances map to `recent_performances` with their
original performer/save/world/composition IDs and `at_hours` as `at`. Receipts retain
their composition ID across slot reuse. The planner enforces scope and time.

Optional top-level `library.json.generation_receipts` contains confirmed generation
starts, including failed attempts: `id`, `performer_id`, `save_id`, `world_id`,
`action` (`compose_lyrics` or `generate_recording`), and `at_hours`. These map to
`generation_history`, dropping unknown extra keys and renaming `at_hours` to `at`.
This collection persists independently of slot replacement. Imports create no
generation receipt. UTC import timestamps and performance receipts never count
as paid generation starts. T0 does not implement a generation executor.

## Candidate runtime selection projection

New scratch staging can add `runtime_selection: {"version": 1, "contracts": [...]}`
and an `identity_key` on each projected recording. Each performer has one explicit
contract containing performer/region and the eight recording-contract fields.
The key is SHA-256 of their ordered UTF-8 JSON value array; exact ordering,
supported arrangements and native comparison limits are specified in the
[candidate runtime contract](candidate-runtime-identity.md).

Python verifies both readable metadata and keys. The compiled candidate uses
the validated projection to reject other revisions, instruments and arrangements
without falling back to legacy rows. It captures selected identity for the
performance receipt. Fully legacy performers retain their existing selection
behavior. `Library.validate()` alone does not certify this optional projection;
staging and promotion apply the additional runtime-contract validation.

This is candidate metadata, not an installed-library migration. Current recipes
never fill historical gaps, and staging writes only a new payload.

## Import an existing MP3

```sh
python tools/import_recording.py --library /path/to/library \
  --performer mikael --region whiterun --mode vocal --gender male \
  --source /path/to/existing.mp3 --lyrics /path/to/lyrics.txt \
  --ffmpeg /path/to/ffmpeg
```

This command now prints a read-only review. Repeat the same arguments with
`--apply --review-token <returned-token>` to convert and publish into the
explicitly selected offline library. Review does not run ffmpeg or create the
library. A changed source, sidecar, metadata, converter or destination state
requires another review.

Without a metadata sidecar, new imports retain the unversioned `region/mode`
classification and use `model_id: "unknown"`. The former hardcoded
`google/lyria-3-pro-preview` label was not provider evidence. Existing rows retain
their historical bytes and are not silently relabeled or upgraded.

Use `--metadata /path/to/recording-metadata.json` only when the recording's
original identity is known. Its exact fields are:

- `version`: integer `1`.
- `source_sha256`: SHA-256 of the original source bytes.
- `lyrics_sha256`: SHA-256 of the supplied raw lyrics file, or null when omitted.
- `performer_id`, `region`, `mode`, `gender`: must match the command arguments.
- `recipe_id`, `recipe_revision`, `model_id`, `instrument_family`,
  `instrument_name`, `arrangement`, `voice`: explicit nonempty identity fields.

The metadata is an operator assertion bound to specific files. It does not
verify a provider or musical style. Never copy today's palette revision onto
historical audio merely to satisfy a strict request. Duplicate keys, partial
identity and contradictory arguments are rejected. Other named instrument
families can remain offline library metadata; their runtime compatibility
requires separate staging validation. Import rejects destinations already
carrying `runtime_selection`; it neither creates nor extends playback contracts.
Use a source library followed by explicit staging and merge review.

Application uses frozen source bytes and runs ffmpeg with
`-ac 1 -ar 44100 -sample_fmt s16 -c:a pcm_s16le`, validates the output, records
original source path/hash and a content-derived composition ID, then rechecks
reviewed inputs before publication. Missing ffmpeg produces a message naming
`--ffmpeg`. Temporary conversion files stay under the chosen library root.
Optional `--receipts` and `--session-receipt-index` describe current slot
reservations; they do not establish a real process-session boundary.
No paid requests are made.

This uses the existing offline single-writer publication API. It is not an
installed-game updater or a multi-file crash-recovery transaction. The separate
[library merge review](library-merge-review.md) plans slot remapping and contract
conflicts without writing either library.

Unit tests create tiny WAVs with `wave` and substitute the subprocess call; they
never execute ffmpeg. The separate Halcyon proof uses only the existing Mikael
MP3 and the two lyric lines from `tests/fixtures/skyrimnet_music_request.json`,
with all remote writes confined to `C:\MGO\hm-scratch\t0\`. This establishes
offline conversion and validation only, not in-game verification.
