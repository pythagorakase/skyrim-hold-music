# Performer registry and recording library (T0)

This is an offline format and Python API, using only Python 3.10+ standard-library
modules. It does not install a game package, generate music, or establish in-game
playback. The future installed library root is the profile's
`hold-music-runtime/library`; callers currently pass an explicit root.

## Authored performers

`game_adapter/data/performers.json` has `version: 1`, a descriptive `scope`, and
`performers`. Each entry contains `id`, `name`, `form`, `venue`, `region`, `gender`,
`instrument`, `traditions`, `source`, and `notes`. IDs are stable machine names;
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

- `Library(root).load()` refreshes state and returns the instance. `validate()`
  refreshes and returns a list of problems; file-content problems do not raise.
- `recordings_for(performer_id=None, region=None, mode=None, gender=None)` refreshes
  and filters by exact values. Returned rows include computed asset/session flags.
- `add_recording(wav_path, *, performer_id, region, mode, gender, composition_id,
  recipe_id, model_id, source, lyrics=None, slot=None, created_at=None,
  generation_receipts=(), **extra)` validates, copies and publishes an entry.
- `snapshot(performer_id, save_id, world_id, now_hours, request)` returns a dict
  accepted by `hold_music.repertoire.Snapshot.from_dict` and `plan`.

Snapshots contain this performer's recordings and one composition per distinct
eligible composition ID, with `known_by: [performer_id]`, the sidecar words, and
no inferred observations. Planner recording IDs are `slot:01`, etc. Library
`vocal` becomes planner `lyrical`; region becomes tradition; gender becomes voice
(or `none` for instrumentals). Arrangement defaults to `solo_lute_and_voice`, or
`solo_lute` for instrumentals. Optional manifest `arrangement` and `voice` override
those defaults. Recipe/model IDs are copied exactly; they are not taken from the
caller's request. The request argument itself uses the planner's Request shape.

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

## Import an existing MP3

```sh
python tools/import_recording.py --library /path/to/library \
  --performer mikael --region whiterun --mode vocal --gender male \
  --source /path/to/existing.mp3 --lyrics /path/to/lyrics.txt \
  --ffmpeg /path/to/ffmpeg
```

The importer runs ffmpeg with `-ac 1 -ar 44100 -sample_fmt s16 -c:a pcm_s16le`,
validates the output, records original source path/hash and a content-derived
composition ID, and prints the entry. It uses the T0 recipe naming convention
`region/mode` and model label `google/lyria-3-pro-preview`; this label describes
the imported fixture contract, not verification of an arbitrary MP3's provider.
Missing ffmpeg produces a message naming `--ffmpeg`. Temporary conversion files
stay under the chosen library root. No paid requests are made.

Unit tests create tiny WAVs with `wave` and substitute the subprocess call; they
never execute ffmpeg. The separate Halcyon proof uses only the existing Mikael
MP3 and the two lyric lines from `tests/fixtures/skyrimnet_music_request.json`,
with all remote writes confined to `C:\MGO\hm-scratch\t0\`. This establishes
offline conversion and validation only, not in-game verification.
