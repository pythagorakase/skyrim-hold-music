# Repertoire decision logic

This is the first executable, offline part of the proposed Hold Music controller. It reads a supplied JSON snapshot and returns a decision. It does not read SkyrimNet, write a save, reserve a job, call an LLM or music provider, or start playback. The live knowledge bridge, durable library and performance controller remain to be implemented.

## Try it

From the repository root, with Python 3.10 or newer:

```sh
python3 tools/plan_repertoire.py examples/repertoire/scandal.json
python3 tools/plan_repertoire.py examples/repertoire/quest-success.json
python3 -m unittest discover -s tests -p 'test_repertoire*.py' -v
```

On Windows use `py -3` in place of `python3`. The command also works from another directory when given absolute paths. It writes its decision as JSON to standard output and leaves the snapshot untouched.

Both examples are invented fixtures. Their cached recording is metadata for a pretend playable asset; no audio or private game data ships with these examples. The scandal example concerns alleged secret meetings between two married merchants. The quest example concerns recovering a mill worker's stolen pay, with no heroic destiny required. Both explicitly select `topical_when_salient` and provide a familiar song as the playback fallback while new words would be prepared.

## What the planner knows

Three separate records matter:

1. **Observation:** something this bard witnessed or heard, with occurrence time, acquisition time and source. A rumor is a valid musical subject; it retains its uncertainty.
2. **Composition:** a song's title, words, tradition and topic, plus which performers explicitly know it. Knowing a rumor does not mean knowing a song about it. A bard can learn an existing song without receiving its composer's private memories.
3. **Recording:** a rendition of a composition for a particular performer, tradition, arrangement, vocal mode, voice, recipe and generation model. Another singer's recording is not automatically suitable.

Scope includes both `save_id` and `world_id`, plus the performer where appropriate. A future adapter must supply stable identities; display names alone are insufficient. `world_id` is Hold Music's explicit continuity namespace, not a claimed SkyrimNet API field. The planner's times are in-game hours on one timeline. Raw SkyrimNet timestamp fields must be normalized deliberately; a load of an earlier save must not import future observations, learned songs or generation history.

The adapter is responsible for establishing that an observation is available to this bard. The planner checks the supplied actor and save scope, but cannot prove that a caller labeled an omniscient event correctly. SkyrimNet's actor-filtered memories and world knowledge are the candidate sources; the [knowledge bridge research](skyrimnet-knowledge-bridge.md) records their limits.

## Selection and new work

The default policy is `cache_first`: reuse an eligible, sufficiently rested recording before proposing generation. `topical_when_salient` can put a recent, interesting, uncovered subject ahead of that familiar recording, while returning the familiar recording as a fallback. This is the proposed mode for occasional songs about the player's recent activities. Neither policy automatically spends money.

Topics can be successful quests, scandals, gossip, everyday news or other known events. Classification is explicit input, not a keyword test that guesses quest completion from a sentence. No category gets an automatic heroic preference. Salience is the mean of supplied `interest` and `local_relevance`; repeated copies of gossip do not increase it. `topic_id` identifies the same claim or occurrence, not a broad category such as all Windhelm gossip. Freshness anchors span the topic's observations even when retellings have different receipt/event IDs. A distinct factual development needs its own normalized topic identity; the planner does not infer that identity from prose.

The planner can return these actions:

| Action | Meaning |
|---|---|
| `play_recording` | A compatible, known recording can be reused now. |
| `compose_lyrics` | A new lyrical composition has a suitable known subject and passes limits; `lyric_brief` supplies the bounded story context. |
| `generate_recording` | A known composition needs a compatible rendition, or an instrumental/wordless piece needs audio; no lyric-writing call is requested. |
| `wait` | Relevant work is already pending; do not queue it again. |
| `no_selection` | No eligible performance or new-work proposal is available under the supplied constraints. |

Decisions explain their reasons and may carry a `fallback`, so a future asynchronous executor can let an existing song play while new material is prepared. `work_key` identifies equivalent proposed work. Returning a plan does not claim a request was queued, a recording succeeded or a bard learned anything. In topical mode, the same subject can advance from new lyrics to a rendition of the completed composition and then to playback; a familiar fallback must not prevent the new song from finishing that sequence.

Instrumental and wordless modes never request lyrics. Re-recording a known lyrical composition reuses its words. The caller chooses the actual arrangement and mode before planning; this module does not replace Solo Lute's existing 50/50 policy, choose the cultural profile, or validate animation capability. `arrangement` and `recipe_id` must distinguish the actual roster, instrument roles, techniques and relevant regional/moon conditions when the future resolver supplies them. Matching arbitrary labels is not proof that the physical performance is possible.

## Gossip and artistic license

The lyric brief keeps source identifiers and the supplied uncertainty. A scandal can be teasing, bawdy, mocking or gleefully exaggerated in attitude, imagery and refrain. Hearsay remains hearsay; repeated rumor is not independent confirmation. The brief does not require every line to say "allegedly," and it does not transform a modest quest success into an epic victory.

Occurrence time and the time a bard learned about an event are distinct. Looking up old gossip now does not make it recent. Unknown timestamps are accepted as unknown and cannot qualify a story as a fresh topical candidate. Repeated observations must retain the original claim identity and occurrence time. Knowledge acquisition time must also survive polling and reloads.

This version does not adjudicate contradictory accounts, infer that two differently keyed rumors are the same event, or model geographic rumor spread. Those are bridge/editorial responsibilities. It also does not teach a song to another NPC merely because the composition exists in the library. Song learning needs an explicit receipt or authored rule in the future persistence layer.

## Initial policy values

These are deterministic tuning defaults, not claims about Skyrim's time conventions or final gameplay balance. They can be overridden in the snapshot's `policy` object.

| Field | Default | Purpose |
|---|---:|---|
| `selection` | `cache_first` | Prefer familiar playable material; use `topical_when_salient` for occasional fresh subjects. |
| `topic_max_age_hours` | 72 | Old events are not freshly topical because they were mentioned again. |
| `knowledge_max_age_hours` | 48 | Limit fresh-topic selection to recently acquired knowledge. |
| `salience_threshold` | 0.75 | Minimum mean of interest and local relevance for topical priority. |
| `composition_cooldown_hours` | 24 | Space lyric-writing starts for this bard. |
| `recording_cooldown_hours` | 1 | Space music-generation starts for this bard. |
| `song_repeat_hours` | 4 | Rest a recently performed composition, including alternate recordings. |
| `topic_repeat_hours` | 24 | Avoid another performance about the same topic too soon. |
| `budget_window_hours` | 24 | Rolling window for job-count limits. |
| `max_lyric_jobs` | 2 | Maximum lyric job starts within the window. |
| `max_recording_jobs` | 2 | Maximum recording job starts within the window. |
| `max_pending_jobs` | 1 | Limit concurrent work for this bard. |

`generation_history` represents confirmed starts, including failed requests that may have cost money. A future executor must reserve a job atomically before dispatch and persist the same job ID in pending/history records to avoid double counting. Plans alone must never consume the budget. These job-count limits are not a dollar budget, and a live service will also need a global concurrency/spending limit across performers, explicit retry rules and cancellation handling.

## Snapshot contract

The complete fixtures under `examples/repertoire/` are the simplest starting point. `hold_music.repertoire.Snapshot.from_dict()` validates the input; `plan(snapshot_or_dict)` returns a JSON-serializable decision.

Top-level fields are `save_id`, `world_id`, `performer_id`, `now_hours`, `request`, and optional arrays `observations`, `compositions`, `recordings`, `recent_performances`, `pending_jobs`, `generation_history`, plus optional `policy`. Every array item has its own `save_id` and `world_id`.

- `request`: `tradition`, `arrangement`, `mode` (`lyrical`, `wordless`, `instrumental`), `voice`, `recipe_id`, `model_id`. Instrumental requests use `voice: "none"`.
- Observation: `id`, `performer_id`, `event_id`, `topic_id`, `kind`, `summary`, `happened_at`, `learned_at`, `source_id`, `evidence` (`direct` or `rumor`), `interest`, `local_relevance`.
- Composition: `id`, `title`, `tradition`, `mode`, `lyrics`, `topic_id`, `source_observation_ids`, `known_by`, `composer_id`, `created_at`.
- Recording: `id`, `composition_id`, `performer_id`, `request`, `playable`, `created_at`.
- Performance receipt: `id`, `performer_id`, `composition_id`, `recording_id`, `topic_id`, `at`.
- Pending job: `id`, `performer_id`, `action`, `request`, `topic_id`, `composition_id`, `created_at`, `status` (`queued` or `running`).
- Generation-start receipt: `id`, `performer_id`, `action`, `at`.

The initial library is a supplied snapshot, not an implemented database. `known_by` is a current-timeline assertion: the future library must omit knowledge acquired after a loaded save, even if the song itself is older. Composition IDs must identify immutable content: changed words require a new composition/revision identity, and changed arrangement instructions require a new recipe identity. A recording's `playable` flag must eventually come from asset verification. No file path or game object is opened by this planner.

## Next integration steps

1. Normalize a small actor-scoped SkyrimNet knowledge sample, keeping source IDs, uncertainty and time domains intact. Entries whose ages are unknown can support background context but cannot be fabricated into recent events.
2. Add durable composition, recording, learning and performance receipts with save/load handling. Keep ordinary gossip propagation under SkyrimNet's ownership.
3. Atomically queue an approved planner action, validate returned lyrics/audio, and publish successful results to the library. Keep failed/unknown provider outcomes distinct from successful recordings.
4. Feed a ready recording to a performance controller and prove start, interruption and cleanup before disabling SkyrimNet's bard feature.

## Verification

On 8 October 2026, all 44 repertoire tests passed on Windows with Python 3.10 and on Echo with Python 3.13. They cover the topical lyrics-to-recording-to-playback sequence, alternate renditions, actor/save isolation, unknown and future dates, repeated rumors, pending work, cooldowns and job-count limits. The CLI examples run from outside the repository and leave their snapshots unchanged. An isolated dashboard rebuild on Echo reproduced the existing HTML and palette data byte for byte and passed the JavaScript syntax check. These are offline checks; no game playback, live knowledge ingestion, lyric generation or paid music request was exercised.
