# SkyrimNet knowledge bridge

Status: research and proposed bridge contract, 8 October 2026. The current Hold Music repertoire planner is offline. This document specifies the evidence a future runtime bridge should provide; it does not claim that the bridge, gossip propagation or live repertoire selection has been implemented.

## What the bridge should preserve

A bard can draw on a recently completed quest or a scandalous rumor when that bard has a supported way to know about it. A successful quest does not prescribe a triumphant song. The event supplies subject matter; the performer's perspective, selected tradition and occasion supply interpretation and musical mood. Likewise, a rumor remains something heard or believed rather than becoming an omniscient statement of fact.

The user has observed gossip spreading in the installed game. Treat that as a behavior report to support and preserve. The exposed files establish actor-scoped memories, shared conditional knowledge and event callbacks. They do not establish the complete mechanism, delivery timing or recipient history behind that observed propagation. That is an integration detail to identify, not grounds to deny the observation.

## Inspected installation

- Selected profile: `MGO EXP - SkyrimNet b26 + SeverActions 4.2`, confirmed from `ModOrganizer.ini:3` in the RC4.1 installation.
- Active package inspected: `mods/SkyrimNet - Experimental beta26-rc4/`.
- C++ headers available in `mods/SkyrimNet/CppAPI/`, a separate installed package. Header declarations were checked against selected export names in the beta26 DLL, not assumed to match merely because both packages exist.
- DLL SHA-256: `2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
- Confirmed exports include `PublicGetWorldKnowledgeForActor`, `PublicGetWorldKnowledge`, `PublicQueryMemoriesForActor` and `PublicRegisterEventCallback`. Previous checks also confirmed the memory/event/dialogue getters and custom-prompt export.
- No personal memories, conversation logs, current lyrics or credential files were inspected. No game, provider or model call was made. Export inspection reads the DLL file without loading it.

Source shorthand below uses paths relative to the RC4.1 installation:

| Prefix | Installed-relative path |
|---|---|
| `B26` | `mods/SkyrimNet - Experimental beta26-rc4/` |
| `PROMPTS` | `B26/SKSE/Plugins/SkyrimNet/library/skyrimnet.base/prompts/` |
| `SQL` | `B26/SKSE/Plugins/SkyrimNet/sql/migrations/` |
| `SDK` | `mods/SkyrimNet/CppAPI/` |

Line references describe this snapshot and may move in later versions. Shipped templates describe intended behavior; they are not evidence that any particular fact reached a particular NPC in a running save.

## Memories and shared knowledge are distinct sources

**Actor memories** belong to a particular actor. The memory schema stores `actor_uuid`, content, location, `game_time`, related event IDs, related actors, emotion, importance, tags and memory type. The memory-builder template summarizes supplied events from an NPC's first-person perspective. This establishes a useful contextual source, but an LLM-written recollection is not automatically a verbatim event record or proof of objective truth. Sources: `SQL/0003_vector_memory_system.sql:7–20`; `PROMPTS/memory/memory_builder.prompt:2`, `:11–23`, `:35–39`.

`PublicQueryMemoriesForActor` provides filtering before truncation. The companion query structure supports tags, types, emotions, locations, importance, active state and time bounds. For a recent-material scan, prefer a time-ordered query with explicit bounds over semantic relevance alone. The header warns that semantic ordering can miss memories whose embeddings are not ready or which fall beyond its candidate cap; SQL orders see eligible rows before the requested result limit. Sources: `SDK/PublicAPI.h:193–210`; `SDK/PublicAPIMemoryQuery.h:33–45`, `:68–94`.

**World knowledge** is stored with `actor_uuid = 0` and selected for an NPC through a condition expression. It can be scoped to a person, faction, group or quest state. It need not have been copied into that actor's personal memory store. Sources: `SQL/0013_world_knowledge.sql:3–20`; `SDK/PublicAPI.h:608–622`; `B26/Source/Scripts/SkyrimNetApi.psc:869–892`.

Use `PublicGetWorldKnowledgeForActor(formId, maxResults, searchQuery)` for the bard's applicable knowledge. Do not substitute `PublicGetWorldKnowledge`, which lists global entries without establishing that this bard passes their conditions. The actor-specific getter mirrors the dialogue decorator and resolves form ID to UUID internally. Sources: `SDK/PublicAPI.h:653–687`.

The two actor-specific retrieval modes matter:

- Empty search query: deterministic `always_inject` entries only.
- Nonempty query: applicable always-inject entries plus semantic search results.

Rumors are explicitly described as an ordinary use of semantic knowledge in the shipped authoring template. An empty query alone would therefore omit material we want the repertoire planner to consider. Use a bounded set of concrete topic queries when appropriate, while retaining a separate recent-memory scan. A failed semantic retrieval is not proof that an NPC knows nothing about the topic. Sources: `SDK/PublicAPI.h:668–684`; `PROMPTS/agent_knowledge_builder.prompt:20–24`.

The character-bio module labels retrieved knowledge as things the character knows or has heard about. That module is included for particular render modes. The bard lyric template instead lists memories, events and dialogue as supplied variables; it does not directly call `get_world_knowledge`. A replacement lyric pipeline should explicitly add appropriately scoped shared knowledge rather than assume the built-in lyric context already includes it. Sources: `PROMPTS/submodules/character_bio/0130_world_knowledge.prompt:1–11`; `PROMPTS/bard_song_lyrics.prompt:19–32`.

## Recipient scoping, deduplication and timing

**A global event is not a receipt.** Event records have originating/target actors and an actor list. The callback exposes event ID and origin/target identities, but its documented payload has no complete witness or listener list. The callback is useful for marking material dirty or scheduling a refresh; it is not sufficient to grant every nearby bard knowledge. `memory_generated_for_actors` records memory-generation processing, not an independently documented rumor transmission chain. Sources: `SQL/0001_initial_schema.sql:6–16`; `SQL/0004_memory_generation_tracking.sql:4–8`; `SDK/PublicAPI.h:512–532`.

**Quest outcome and awareness require separate checks.** The shipped knowledge-authoring reference distinguishes persistent quest-stage conditions from active-only conditions. It describes `get_quest_stage(id, false)` for outcomes that remain true after completion, and `get_quest_stage(id, true)` or `is_quest_active` for in-progress knowledge. Those are runtime condition choices, not a date when the bard heard the news. Actual quest identifiers, successful terminal stages and outcome meanings still require verification for each quest. Sources: `PROMPTS/agent_knowledge_builder.prompt:44–48`, `:73–79`.

**SkyrimNet already has knowledge deduplication.** When eligible entries share a `knowledge_key`, the highest-importance passing entry wins. That supports, for example, a specific account replacing a general account. Preserve the upstream resolution rather than merging incompatible versions back together. Importance here is retrieval/override priority; it is not a probability that a rumor is true. Sources: `SQL/0018_knowledge_key.sql:1–4`; `PROMPTS/agent_knowledge_builder.prompt:25–34`.

**Content provenance is not social provenance.** `source_path`, `source_key` and `source_hash` identify managed knowledge-pack files and synchronization state. They do not identify the person who told an NPC a rumor, whether the NPC witnessed the event, or how widely it has spread. Sources: `SQL/0022_knowledge_provenance.sql:1–5`, `:9–13`.

**Time fields use different domains.** The memory-query header explicitly defines its bounds as game-seconds. Memory `creation_time` and event `local_time` default to Julian dates; memory `updated_at` is documented as seconds since epoch. An edited old memory is not necessarily a new event. The event getter's sample `gameTime` does not, by itself, establish every conversion needed by our bridge. Sources: `SDK/PublicAPIMemoryQuery.h:85–88`; `SQL/0003_vector_memory_system.sql:12–14`; `SQL/0001_initial_schema.sql:11–13`; `SQL/0026_memory_updated_at.sql:3–5`.

## Current public-shape gaps

| Available surface | What is established | What Hold Music must not invent |
|---|---|---|
| Actor-filtered world knowledge | Applicable content, always-inject flag, importance and display name in the documented return shape | Stable entry ID, `knowledge_key`, content-pack provenance, event date, date learned, teller and propagation hops are not guaranteed by that shape. |
| Actor memory query | Actor-scoped retrieval, IDs in the general documented memory result, filtering and time ordering | Every database column is not guaranteed to be serialized. Verify actual returned names/types before depending on related-event links or source fields. |
| Event callback | Event ID, type, data and origin/target UUIDs/form IDs | Full audience, receipt state and timing are not documented in the sample payload. |
| Quest-gated knowledge | A condition can make an outcome applicable after the relevant stage | A completion date or proof that every NPC has heard it. |
| Content-pack provenance | Stable file identity and content revision | In-world witness, teller or reliability information. |

Sources: `SDK/PublicAPI.h:175–189`, `:203–210`, `:514–524`, `:683–687`, and the migrations above. These are documented-shape gaps; an actual implementation may return additional fields. Verify serialization or request a supported API extension before relying on them. Avoid reconstructing identity by joining unrelated global records solely on content text.

The actor-specific knowledge getter returns `[]` for an unknown form, errors and empty results. Use readiness/export checks and explicit bridge status; an empty array alone cannot distinguish “no relevant knowledge” from every failure case. Source: `SDK/PublicAPI.h:677–684`, with readiness at `:275–283`.

## Proposed bridge contract

The runtime bridge should deliver an immutable, already actor-scoped topic snapshot to the offline planner. The planner should not query SkyrimNet's global store or decide who must know a fact merely from their location.

| Field group | Proposed content and rule |
|---|---|
| Snapshot identity | Schema version, playthrough ID, bridge capture ID, bard UUID/stable actor identity, capture time with an explicit clock domain, and source availability/completeness notes. SkyrimNet exposes a playthrough ID that persists across saves; it is not a save-branch identifier. |
| Source identity | Source kind (`actor_memory`, `scoped_world_knowledge`, or verified received event), source ID when exposed, upstream knowledge key when exposed, content revision and related source IDs when supported. Unknown fields remain null. |
| Recipient evidence | The exact bard for whom the memory was retrieved or the knowledge condition passed. Retain the query/context that produced a scoped result. A global event callback by itself is insufficient. |
| Topic content | A short faithful account, involved entities, topic/category and any supplied outcome. Preserve distinctions among what occurred, what someone claims, what the bard believes, and what remains uncertain. |
| Social provenance | Witnessed/heard/read/scoped-shared/unknown, with an identified teller or receipt event only when supported. Do not infer a named source or transmission history from a knowledge-pack filename. |
| Time provenance | Separate occurrence time, bard-acquisition time and bridge-observation time; include clock domain and precision for each. A newly observed timeless entry is newly observed, not automatically a recent event. |
| Musical separation | Evidence emotion or the bard's reaction may be retained as context. Neither importance nor quest success chooses heroic mood. Tradition, stance and occasion remain separate planning inputs. |
| Deduplication | Prefer playthrough + stable source/topic identity + meaningful revision. Where only content is available, an actor-scoped content fingerprint is an explicitly weaker snapshot identity, not a fabricated upstream event ID. |

Playthrough-ID evidence: `B26/Source/Scripts/SkyrimNetApi.psc:364–367`. Native callbacks run on SkyrimNet's thread pool, so copy the payload and marshal game-object work to the appropriate thread. Do not access game objects directly from an event callback. Source: `SDK/PublicAPI.h:514–532`.

A practical flow is:

1. A known new event or a periodic bounded refresh marks the bard's topic snapshot due for refresh. This does not start music generation.
2. Retrieve the bard's recent memories and applicable shared knowledge; normalize only the evidence the APIs actually provide.
3. Resolve revisions and duplicates, preserve uncertainty, and assess recency using known clocks. Leave timeless news eligible as general repertoire material without calling it “just happened.”
4. Let the planner compare available subjects with existing repertoire and the selected tradition. A quest's costs, a disputed account, scandal, sympathy, satire or ordinary local curiosity can shape the stance; successful completion alone does not choose praise.
5. Reuse a compatible cached piece or propose a genuinely needed composition. Keep lyric generation separate from topic refresh and from instrumental generation.

Listening to or singing a generated song should not automatically create a new corroborating fact and trigger another song. Track Hold Music origin/correlation information in its own state; if a later write-back integration is chosen, use supported provenance/tags and exclude those feedback records from topic discovery. The typed memory API already supports excluding tags before truncation. Source: `SDK/PublicAPIMemoryQuery.h:19–25`, `:71–73`. No write-back is part of this offline contract.

## Offline work now and runtime questions later

The offline planner tests actor-scoped eligibility, null time handling, stale updates, duplicate retellings, cache reuse and outcome-to-mood separation with synthetic inputs. These include knowledge known to one bard and unavailable to another, without assuming why it spread. Adjudicating contradictory accounts remains a bridge/editorial question; selecting a supplied direct observation does not independently prove its truth.

The future bridge needs to establish:

- Which installed subsystem produces the observed gossip circulation, and which supported API exposes actual receipts or applicable shared knowledge at the right time.
- The exact serialized fields returned by actor-scoped knowledge and memory APIs, including IDs, clocks, keys and revisions. Additional supported provenance fields would substantially improve deduplication.
- How quest-success events and outcome-specific knowledge become eligible, including paths where a nominally completed quest has several possible outcomes.
- Whether a newly reported event has entered memory/semantic indices yet; callback arrival, memory creation and embedding readiness are separate stages.
- How to invalidate snapshots after load, rollback, actor identity changes or changed knowledge conditions. A playthrough ID alone cannot distinguish a restored earlier save.
- Whether current prompt/template calls remain available when SkyrimNet's built-in bard feature is disabled, and how callback/scene ownership behaves during a performance.

These questions concern runtime integration. None requires the offline planner to invent a gossip network, overwrite SkyrimNet's knowledge store or expose a character to facts outside their established scope.
