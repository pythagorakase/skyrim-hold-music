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

Both `prepare_library.py` and `snapshot_knowledge.py` accept `--receipts <path>`
to read separate game performance history, or the mutually exclusive
`--mo2-root <path> --mod-name <name> [--data-mod <name>]` to discover the newest
receipts in the mod, overwrite, or optional data mod. `--mod-name` defaults to
`MGO Experimental - Hold Music Performances`; mod options require `--mo2-root`.
Each command prints one receipts-source line to stderr, preserving JSON stdout;
when discovery finds none, it names the library default that applies. Neither
tool writes receipts; see [runtime evidence](evidence.md) for storage details.

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
The private journal retains historical accounted costs and per-call estimates;
it does not treat an unknown call's estimate as a confirmed charge. Unresolved
paid work blocks a subsequent invocation before it can spend.

The client sends a single streaming POST with the adapter's authorization and
`X-Title` headers. Redirects are forbidden, the socket timeout is 300 seconds,
and the entire SSE response is capped at 64,000,000 bytes. Audio fragments are
concatenated before strict base64 decoding; a complete `[DONE]` and positive
MP3 frame duration are required. Typed errors contain no response body or key.
The provider SSE `id` is preferred, then `X-Request-ID`; if neither is supplied,
a unique `local:` ID identifies the attempt without claiming a provider ID.

ffmpeg, a free slot and scratch-directory creation are checked before dispatch.
Returned source audio is retained in the private job journal. Conversion
MP3/WAV scratch files stay inside a temporary directory under the explicit
library root and are cleaned on ordinary success or failure. ffmpeg produces
mono 16-bit PCM at 44.1 kHz
using the importer's exact arguments. The library validates the WAV and derives
its duration before publishing it to the next free numbered slot. No recording
is automatically evicted. The executor takes an OS writer lock for the entire
run; another executor using that library is rejected before dispatch. The
lock releases when the process exits, including a crash. Other library writers
must still be paused: this is the library's single-writer API, not a concurrent
scheduler.

Each published entry records a prompt-hash/request-ID composition identity,
`region/mode` recipe, model, and generated MP3 SHA256 provenance. Successful
generation receipts are written atomically with the manifest, using game hour
zero and the API's `receipt_scope` (default `offline`, `offline`). The recordings
remain baseline offline material; this scope is for receipts, not a claimed
live save identity. See [the library contract](library-format.md).

The spend report includes manifest entries, MP3 duration, numeric usage, accounted
cost, and whether the cost was estimated. On the first generation, conversion
or publication failure, no recording for that failed job is published; prior
successful recordings remain. One JSON line is appended to
`<library>/executor.log` containing only performer ID, region, mode and error
type, and the CLI exits nonzero. Prompts, exception messages and credentials
are excluded. A successful run need not create a log. An unreported attempt's
charge remains unknown and is explicitly flagged in the report, never asserted
to be free. Inspect an uncertain provider outcome before any manually requested
new run; the tool itself never retries. A new spend invocation returns
`recovery_required` while the journal contains an unknown call or unpublished
paid response. No provider request is made in that case.

## Durable job journal and recovery

Each authorized execution writes `<library>/.executor/jobs.sqlite3`, using
SQLite transactions with `synchronous=FULL`. The directory is private local
state: it contains actor briefs, exact prompts and lyrics, provider responses,
and original generated audio, as well as accounting. It is ignored by the
repository and must not be pasted into shared logs. No credentials are stored
by the executor. Keep this directory with the library when backing up or moving
it; deleting it loses recovery evidence and the guard against uncertain retries.

The executor commits a local call ID, action, model and estimated reservation
**before** calling the provider. It commits the returned payload before lyric
parsing, conversion or publication, then commits validated accounting. A process
interruption during a request is an unknown outcome, including the narrow gap
between provider completion and response persistence. Opening the journal for
execution/recovery marks interrupted in-flight requests `unknown` and never
resubmits them. A provider exception is conservatively unknown; a conversion
or parsing error after a persisted response is a known local failure. A disk
failure that prevents response persistence can only retain the earlier
in-flight evidence, not guarantee retention of the returned bytes.

Inspect public summaries without a registry, credentials, ffmpeg, state writes,
or provider calls:

```sh
python tools/prepare_library.py --library /private/library --job-status
```

This read-only command does not rewrite an interrupted state; it reports an
in-flight request as an unknown outcome. Normal planning dry runs also remain
free of library/journal writes. Python itself can create ordinary import caches.
If a hard crash leaves a hot SQLite rollback journal, read-only inspection
cannot perform SQLite's required repair. Explicitly repair local journal state
and list the recovered job IDs without generating or publishing anything:

```sh
python tools/prepare_library.py --library /private/library --repair-journal
```

This takes the same writer lock and leaves uncertain requests blocked.
Applying a known job's recovery also performs this SQLite repair before
inspecting its retained result.

For a failed conversion/publication or interrupted local publication, inspect
and then explicitly apply recovery from the retained audio:

```sh
python tools/prepare_library.py --library /private/library --recover-job JOB_ID
python tools/prepare_library.py --library /private/library --recover-job JOB_ID \
  --apply-recovery --ffmpeg /path/to/ffmpeg
```

Recovery has no provider client and cannot generate. Its default is read-only.
The same `--receipts` or `--mo2-root` discovery options apply during recovery,
so slot safety uses the selected external performance history.
Applying it validates stored accounting, converts the retained audio and
publishes the original composition and generation receipts. If the manifest
committed before the process died, recovery finds that recording by performer,
composition and exact source provenance, validates it, and completes the
journal without adding a duplicate recording or receipt. Failure preserves the
paid response for another local repair attempt. A successful recovery reports
the original per-call costs separately from its zero new provider calls.
The converted WAV hash is committed to the journal before publication. Recovery
requires the existing WAV to match that hash; a missing hash or a replaced WAV
fails closed even when its format, duration and manifest metadata remain valid.
An existing vocal recording must also retain the original lyrics hash, title,
topic, source observations and creation/save scope; a structurally valid edited
recording is not silently accepted as the saved job's result.

Unknown requests require external provider reconciliation. Lyrics-only results
(including a budget stop between lyrics and music), malformed provider metadata
and rejected lyrics remain retained and block new spending. This version has
no automatic resume, cancellation/reconciliation UI or provider resubmission for
those states. Do not delete the journal to bypass them. The next queue step is
an explicit reviewed reconciliation/continuation contract, not a retry timer.

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
flag. Planner generation receipts still publish atomically with a successful
recording. The separate durable journal preserves paid evidence and accounting
even when lyrics parsing, the second-call budget gate, conversion or publication
prevents that recording from being published. A lyrics-only result is private,
recoverable evidence; it is not presented as a completed planner composition.
This is a bounded executor with durable recovery, not an automatic replenishment
scheduler. See the recovery limitations above before authorizing a later run.
