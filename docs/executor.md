# Ahead-of-time recordings (T2a)

`tools/prepare_library.py` prepares instrumental recordings and Winterhold-only
wordless recordings in an explicit offline library. It uses the authored
performer registry, shared regional prompts, OpenRouter
`google/lyria-3-pro-preview`, and ffmpeg. Nothing here installs a game package,
changes SkyrimNet, or plays audio in-game. T2b adds actor-scoped lyrical
compositions through the [knowledge bridge](knowledge-bridge.md); use `lyrical`
on the CLI (`vocal` is the library mode name). Instrumental and wordless jobs
request no lyrics.

The plan contains one job per missing playable recording of each requested mode,
up to `--target` per performer. Counts match performer, region, mode and gender.
Performers with null regions are skipped. `wordless` applies only to Winterhold;
other holds are skipped for that mode. The Winterhold prompt uses the shared
vocal-choice mapping and explicitly requires vocables without words. Duplicate
mode selections are collapsed; unknown performer IDs and modes are errors.

From the repository root, inspect a plan without credentials, ffmpeg or calls:

```sh
python tools/prepare_library.py --library /path/to/library \
  --registry game_adapter/data/performers.json \
  --performers karita --modes instrumental --target 1
```

To execute a bounded paid run, add explicit spending permission:

```sh
python tools/prepare_library.py --library /path/to/library \
  --registry game_adapter/data/performers.json \
  --performers karita --modes instrumental --target 1 \
  --spend --max-jobs 1 --max-usd 0.10 \
  --ffmpeg /path/to/ffmpeg --bardsinging /path/to/BardSinging.yaml
```

On Windows use `py -3` instead of `python`. The credential reader uses
`OPENROUTER_API_KEY` when set; otherwise it reads only
`bard_singing.openrouter.api_key` using the adapter's narrow YAML scalar reader.
It never rewrites the file or prints the key. Omit `--performers` to select every
registered performer; use `--modes instrumental,wordless` to include Winterhold's
wordless jobs. A registry without a Winterhold performer has no wordless work.

## Budget and failure rules

Defaults are one job and USD 0.10 per invocation. Both the Python API's
`dry_run=False` and `spend=True` are required to call the client; the CLI sets
these only with `--spend`. Dry runs print the entire proposed job list as JSON,
including prompts, without applying execution caps or writing the library.

Before each request, the executor requires room for an estimated USD 0.08 in
the remaining budget. Afterward it uses the returned `usage.cost`, or USD 0.08
when usage/cost is absent or null. Decimal arithmetic avoids rounding past an
exact budget boundary. Reported zero is a real zero; malformed, negative or
nonfinite costs stop the run. `max_jobs` caps attempts. No request is retried.
The estimate is not a provider-enforced price ceiling: a returned charge can
exceed it. In that case the successful recording is retained, the report says
`budget_exceeded`, the CLI exits nonzero, and no further job is dispatched.
These caps are per invocation, not a durable account-wide spending limit.

The client sends a single streaming POST with the adapter's authorization and
`X-Title` headers. Redirects are forbidden, the socket timeout is 300 seconds,
and the entire SSE response is capped at 64,000,000 bytes. Audio fragments are
concatenated before strict base64 decoding; a complete `[DONE]` and positive
MP3 frame duration are required. Typed errors contain no response body or key.
The provider SSE `id` is preferred, then `X-Request-ID`; if neither is supplied,
a unique `local:` ID identifies the attempt without claiming a provider ID.

ffmpeg and a writable free slot are checked before dispatch. MP3/WAV scratch
files stay inside a temporary directory under the explicit library root and
are cleaned on success or failure. ffmpeg produces mono 16-bit PCM at 44.1 kHz
using the importer's exact arguments. The library validates the WAV and derives
its duration before publishing it to the next free numbered slot. No recording
is automatically evicted. Run only one executor against a library at a time;
this is the library's single-writer API, not a concurrent scheduler.

Each published entry records a prompt-hash/request-ID composition identity,
`region/mode` recipe, model, and generated MP3 SHA256 provenance. Successful
generation receipts are written atomically with the manifest, using game hour
zero and the API's `receipt_scope` (default `offline`, `offline`). The recordings
remain baseline offline material; this scope is for receipts, not a claimed
live save identity. See [the library contract](library-format.md).

The spend report includes manifest entries, MP3 duration, raw usage, accounted
cost, and whether the cost was estimated. On the first generation, conversion
or publication failure, no recording for that failed job is published; prior
successful recordings remain. One JSON line is appended to
`<library>/executor.log` containing only performer ID, region, mode and error
type, and the CLI exits nonzero. Prompts, exception messages and credentials
are excluded. A successful run need not create a log. An unreported attempt's
charge remains unknown and is explicitly flagged in the report, never asserted
to be free. Inspect an uncertain provider outcome before any manually requested
new run; the tool itself never retries.

## Offline verification

```sh
python -m unittest discover -s tests -v
python tools/prepare_library.py --help
```

Transport tests use a loopback `http.server` and hand-assembled MP3 frames.
Executor tests substitute conversion with a valid `wave`-written WAV; CLI tests
mock provider entry points. Tests never call a provider or require an encoder.
These checks establish transport, accounting and library publication, not
musical quality or game playback.


## Lyrical preparation (T2b)

```sh
python tools/prepare_library.py --library /private/library \
  --registry game_adapter/data/performers.json --performers mikael \
  --modes lyrical --db /private/SkyrimNet-save.db --allow-name-match
```

`--db` is mandatory for lyrical mode. The read-only bridge requires a resolved
actor and registered region. Name matching is opt-in and restricted to the
performer's plugin; placed-reference registration remains a follow-up.
`--now-hours` overrides the default last known in-game time. `--lyric-model`
defaults to `openai/gpt-5.6-terra`. No key is read by a dry run.

For each selected performer, the planner receives `topical_when_salient`,
`solo_lute_and_voice`, lyrical mode, the vocal gender, `region/vocal`, and the
Lyria model ID. `compose_lyrics` emits one job with its brief and topic;
`generate_recording` reuses a known composition's exact words without a lyric
call. Other actions emit no job and retain the planner's reason. Lyrical jobs
follow planner cooldowns and topic selection, rather than multiplying a single
brief up to `--target`; target zero suppresses dispatch. Null-region performers
are skipped. Winterhold's approved recipe remains wordless, so lyrical dispatch
is skipped there. Mixed comma-separated modes retain the existing deficit plans.

Dry-run JSON includes decisions, counts and topic IDs. Briefs contain private
memories and are omitted unless `--show-briefs` is explicitly supplied; this
flag also reveals existing lyrics. Never paste those private contents into
shared logs, tests or reports. An unresolved identity is reported, not treated
as an empty successful retrieval.

Add `--spend --max-jobs 1 --max-usd 0.20`, `--ffmpeg`, and `--bardsinging` to
execute. A composed vocal job has **two costs**: one non-streaming lyric-model
call, then one existing streaming music call. The executor reserves USD 0.01
for lyrics plus USD 0.08 for music before the job. It counts reported lyric
`usage.cost` immediately, even if lyric parsing later rejects the response,
and requires another USD 0.08 of remaining capacity before dispatching music.
Absent/null costs use their respective estimates; zero is retained. As before,
these are estimates, not provider-enforced ceilings. `max_jobs` counts attempted
recording jobs (a new lyrical job may make two calls). Neither call is retried.
The key reader and body-free typed transport errors are shared with Lyria;
text responses are capped at 1 MB and requests use a 1024-token output bound.

The lyric prompt asks for a title, two or three short verses and a chorus,
under 200 words, with `[Verse]`/`[Chorus]` tags, actor-known facts and preserved
hearsay. Parsing requires `Title:` and `Lyrics:`, nonempty content, at most
1,200 lyric characters, and no adapter markers or style line. Prompt constraints
about literary content are not claimed as a semantic verifier.

Successful publication writes the exact UTF-8 lyrics sidecar/hash, song title,
source observation IDs, topic ID, save/world scope and in-game creation time.
New composition IDs are `lyric:<topic_id>:<first-16-SHA256-of-lyrics>`; a new
recording of an existing composition retains its composition ID. Both successful
`compose_lyrics` and `generate_recording` receipts publish atomically with a new
composition's recording. Reused lyrics create only the music receipt. Bridge
snapshots restore topic metadata so a published song is selected again rather
than recomposed for the same topic.

Spend reports contain the title/manifest and separate model/request IDs,
numeric usage and costs; they exclude lyrics and briefs. Failures contain only
identity and exception type. An unreported call has an explicit unknown-cost
flag. The existing publication contract persists generation receipts only with
a successfully published recording: budget stops or failed conversion after a
paid call leave accounting in the returned report, not a durable planner receipt.
This remains a single-invocation executor, not a crash-safe paid-job queue;
inspect uncertain outcomes before any separately authorized future run.
