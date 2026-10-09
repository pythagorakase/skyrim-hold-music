# Actor knowledge and lyrical compositions (T2b)

The bridge reads SkyrimNet through SQLite `?mode=ro` URIs, immediately enables
`PRAGMA query_only=ON`, and holds one read transaction per snapshot. It never
copies or changes the source database. It reads one actor's memories and events
that actor originated or targeted; membership in `actor_UUIDs` alone is not
recipient evidence. It does not read dialogue, embeddings, diary contents,
existing song lyrics, or global/conditional knowledge (`actor_uuid = 0`). It
cannot evaluate SkyrimNet's runtime knowledge conditions or reconstruct gossip
propagation. This is an offline adapter, not a live clock or gameplay controller.

## Inspected schema and identities

Read-only inspection on Halcyon, 9 October 2026, used
`SkyrimNet-1790647717106-452561.db`. Relevant column names and declared types:

| Table | Columns |
|---|---|
| `uuid_mappings` | `id INTEGER`, `uuid BIGINT`, `form_id INTEGER`, `actor_name TEXT`, `bio_template_name TEXT`, `created_at REAL`, `updated_at REAL`, `mod_file TEXT`, `local_form_id INTEGER` |
| `memories` | `id INTEGER`, `actor_uuid BIGINT`, `content TEXT`, `location TEXT`, `game_time REAL`, `creation_time REAL`, `related_event_ids TEXT`, `related_actors TEXT`, `emotion TEXT`, `importance_score REAL`, `tags TEXT`, `memory_type TEXT`, `embedding_checksum TEXT`, `condition_expr TEXT`, `always_inject INTEGER`, `is_active INTEGER`, `display_name TEXT`, `pack_id INTEGER`, `knowledge_key TEXT`, `source_key TEXT`, `source_hash TEXT`, `updated_at REAL` |
| `events` | `id INTEGER`, `event_type TEXT`, `event_data TEXT`, `location TEXT`, `game_time REAL`, `game_time_str TEXT`, `local_time REAL`, `actor_UUIDs TEXT`, `originating_actor_UUID BIGINT`, `target_actor_UUID BIGINT`, `memory_generated_for_actors TEXT`, `playtime INTEGER` |
| `bard_songs` (identity inspection only) | `id INTEGER`, `save_id TEXT`, `title TEXT`, `lyrics TEXT`, `style_tags TEXT`, `gender TEXT`, `audio_filename TEXT`, `suno_song_id TEXT`, `duration_seconds REAL`, `game_time_created REAL`, `play_count INTEGER`, `is_cached INTEGER`, `created_at TIMESTAMP`, `composer_uuid INTEGER`, `composer_name TEXT` |

IDs are integer primary keys. Memory actor/content, mapping UUID/form ID and
event type/data are NOT NULL. Memory importance defaults to 0.5, memory type to
`EXPERIENCE`, related-event/tag fields are text-encoded lists. The synthetic
fixture records the inspected columns, types, nullability and defaults without
copying any personal data. Runtime reading does not consult `bard_songs`.

`resolve_uuid(performer, db, *, allow_name_match=False)` first matches
`mod_file` case-insensitively and `local_form_id` against the registry's plugin
and hexadecimal base form. It does not strip a runtime load-order prefix and
pretend the result is a plugin identity. A unique UUID is required. An ambiguous
base match is unresolved, without name fallback.

The inspected mapping stores placed references: Mikael is `0x0001A671`, whereas
the authored base is `0x0001A670` (zero base matches). Only when explicitly
passed `allow_name_match=True`, the bridge tries exact case-insensitive
`actor_name`, restricted to the same case-insensitive `mod_file`. Multiple
UUIDs are unresolved; UUID zero is never a personal actor. Of 2,548 mappings,
274 lacked plugin/local-form metadata and cannot safely use this fallback.
Adding placed-reference identities to the registry is a follow-up, not T2b.

The filename provides `save_id`: remove `.db` and the `SkyrimNet-` prefix,
yielding `1790647717106-452561` here. Inspected `bard_songs.save_id` values were
empty. Inspection of all table/column names found no stored playthrough ID;
`world_id` therefore equals `save_id`. The public runtime playthrough-ID API
is not queried. No cross-save continuity or rollback identity is invented.

## Time domains

The following conversion is explicitly adopted by the T2b follow-up: a memory's
`game_time` is when the bard formed it. It is not reconstructed from wall time.

| Column | Observed domain and conversion to the shared game-hour timeline |
|---|---|
| `memories.game_time` | Game seconds. `learned_at = game_time / 3600`; direct evidence also gets `happened_at = learned_at`; rumor occurrence remains null. For example, 1,199,593.734741 seconds becomes 333.220481873 hours. |
| `events.game_time` | Game seconds. Origin/target involvement supplies direct event evidence: both times equal `game_time / 3600`. 3,187,182.897949 seconds becomes 885.328582764 hours, whose time of day agrees with the stored 21:19 clock. |
| `memories.creation_time` | SQL default is `julianday('now')`, but all 743 inspected personal-memory rows were epoch-valued, not Julian-valued. No in-game conversion; ignored. |
| `memories.updated_at` | Documented epoch seconds; all 743 personal-memory values were null. No in-game conversion; ignored even if populated. |
| `events.local_time` | SQL default is `julianday('now')`, but all 10,554 inspected events were epoch-valued, not Julian-valued. No in-game conversion; ignored. |
| `events.playtime` | Integer process/play clock with no established game-hour conversion; ignored. |

Julian dates could convert to Unix seconds with `(JD - 2440587.5) * 86400`, but
neither Unix nor Julian wall time establishes game hours across pauses, loads,
and changing timescale. No interpolation, retrieval-time replacement, or
wall-clock offset is used. Null, negative, nonnumeric or nonfinite game times
remain null. A late wall-clock edit cannot refresh the game's knowledge age.

Unless overridden by `--now-hours`, the snapshot uses the maximum valid game
hour across this actor's memories and **all events**, described as **last known
in-game time**, never the live clock. Other actors' memories do not advance it.
No available timestamp yields 0 as a conservative empty-history origin.
The caller can supply a game-hour override without changing source rows.

## Observation mapping

Every observation carries the filename-derived save/world scope and the selected
registry performer ID. Memory IDs are `mem:<id>` and source IDs are
`skyrimnet:memory:<id>`; events use `evt:<id>` and `skyrimnet:event:<id>`.
The first valid positive related-event ID, if supplied, becomes both `event_id`
and `topic_id` with the `evt:` prefix. Otherwise the memory's own stable ID is
used for both fields, without asserting an external event exists. Event topics
are their own event IDs. Related IDs group retellings; they never grant access
to an unrelated actor's event content.

Summaries are stripped memory `content` or event `event_data`, capped at 500
characters. Related actors and emotion are not inferred into new facts.
Importance was already fractional (observed range 0.12–0.98), so
`interest = min(1, max(0, importance_score))`; missing/invalid importance is 0.5.
Events have no importance column and use 0.5. Location equality after stripping
whitespace and case-folding against venue or region gives 1.0; absent/empty/
`unknown`/`none` gives 0.5; other locations give 0.2. Substring matching is not
used.

Type/tag labels are case-folded, with spaces and hyphens normalized to underscores.
The following table is evaluated in order; no prose-based classification occurs:

| Metadata | Planner kind |
|---|---|
| Direct evidence plus explicit `quest_success`, `quest_completed`, `completed_quest`, or `witnessed_completed_quest` | `quest_success` |
| `scandal`, `affair`, `theft`, `murder`, `theft_accusation`, or `murder_accusation` | `scandal` |
| `rumor`, `rumour`, `hearsay`, or `gossip` | `gossip` |
| Recognized ordinary type: `experience`, `event`, `news`, `everyday_news`, `fact`, `knowledge`, or a witness/quest label above without qualifying direct quest evidence | `everyday_news` |
| Unknown or empty type with no explicit classification tag above | `other` |

Direct memory evidence requires `witnessed`, `witness`, `direct`, `observation`,
`witnessed_event`, or `witnessed_completed_quest` in type/tags. Rumor/hearsay/gossip
labels override a witness label. `EXPERIENCE` alone does not establish witnessing.
A quest-success label without direct evidence never establishes a completed
quest as fact. An originated/targeted event is directly experienced as an event;
this does not verify every claim contained in its payload.

## API, CLI and privacy

`snapshot(performer, db_path, library, now_hours, request, *,
max_observations=40, since_hours=None, allow_name_match=False)` returns
`(planner_snapshot, bridge_report)`. `None` selects last known time. The bridge
merges the library snapshot, preserves topical metadata from library entries,
and validates the result with `Snapshot.from_dict`. The report contains counts,
resolution method, clock notes and unresolved fields, never summaries.

The latest observations by game time are capped at 40 across both sources;
unknown times sort last. SQL retrieves at most the cap from each actor-scoped
source before merging. `since_hours` is an absolute lower bound on game hours;
when provided it excludes unknown-time rows. Report source counts precede this
filter/cap, while output counts describe the returned observations. Malformed
library history blocks planning; missing audio may instead require a new
recording of a known composition.

```sh
python tools/snapshot_knowledge.py --db /private/SkyrimNet-save.db \
  --registry game_adapter/data/performers.json --performer mikael \
  --library /private/library --out /private/library/mikael-snapshot.json \
  --allow-name-match
```

The named output is a JSON object containing `snapshot` and `bridge_report`.
The output is created exclusively, never overwriting an existing file; stdout
contains only the report. Use the library root or an explicitly chosen private
path. Never commit, paste, log, or put real memory/dialogue text in tests, docs,
or reports. Exported snapshots and generated lyric sidecars are private files.
Dry runs reveal briefs only with the explicit `--show-briefs` option; do not use
that flag for shared logs. Tests use invented fixture content and fake clients.
No provider calls are made by tests; existing loopback HTTP fixtures are allowed.
