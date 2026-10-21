# Regional Bard Music Variation

**Status:** Working spec; workshop implemented, palette auditions and phased game integration ongoing
**Scope:** Musical traditions, performer context and prompt construction for generated bard performances
**Reconciled:** 2026-10-19

**Working document:** This file is the canonical spec in the project Obsidian vault. The project-root [SPEC.md](../SPEC.md) convenience symlink points to it. The former Home-vault copy now links here; edit this file directly in either Obsidian or a code editor. [Migration record](vault-migration-2026-10-13.md).

**Build:** `python3 tools/rebuild_palette.py` from the project root generates the dashboard JSON/HTML and synchronizes the local game-package palette from these sources. The default editorial snapshot date comes from the ISO `Reconciled` field above. Generated artifacts are outputs; browser-edited directions are audition drafts, and saved takes preserve their historical prompts. Adopt a draft by updating the source recipe and rebuilding.

**Audition workspace:** [Hold Music listening dashboard](../dashboard/index.html) · [Full idea bank and independent reviews](bard-musical-traditions-exploration.md). Open the HTML file to compare profiles, edit prompts, attach local audio and keep listening notes. For generation and saved takes, run `python3 tools/workshop_server.py` from the project root and open `http://127.0.0.1:8765/`. The workshop calls Google's Lyria 3.5 directly and never retries a generation automatically. Browser experiments do not change these source documents. Export notes to move them between computers. Attached audio lasts only for the page session; generated takes and their exact submitted prompts are saved separately on disk.

## Summary

Bard music should vary by learned tradition, performer and place. Build a diverse, coherent and audibly distinct palette first. Each tradition may have a strong predominant mood; exceptions such as cheerful Dunmer songs can remain minority conditions developed later. Race supplies a fallback cultural association, while established biography and musical training can select a different repertoire.

The initial scope is the nine holds, Cyrodiil and a Dunmeri/Raven Rock core for Solstheim. Gray Quarter can share that foundation; Skaal and a separate Cyrodiil vernacular are deferred.

The named reference styles and their musical fingerprints are provisional targets. Reference-recording listening can change the chosen influence, phrase shape, meter or predominant mood; the first written palette is not a commitment to preserve a poor fit.

**Development decision, 2026-10-19:** the user's listening validation does not gate project progress. Engineering proceeds against explicitly versioned provisional recipes, with listening confidence recorded separately. Continue performer/context integration, library and job durability, controller work and migration preparation using existing recordings or synthetic fixtures without requiring new paid audio. Preserve the current eleven-style baseline, Reach comparison, deferred catalog and vocal constraints. New workshop admission remains an intentional source change, not an automatic unlock or a claim that a style has passed. See the [development roadmap](development-roadmap.md).

## Provisional Eleven-Style Baseline

**Adopted for auditions: 2026-10-13. Listening validation: pending for all eleven styles.** This replaces the broad workshop palette as the active starting set. Target selection is not evidence of Lyria fidelity or production approval. Reach sean-nós is the sole admitted challenger, not a twelfth regional base.

| Region | Predominant reference | Audible identity |
|---|---|---|
| Eastmarch | Icelandic rímur | Narrow syllabic narrative declamation; sparse plucked punctuation |
| Whiterun | Scandinavian medieval narrative ballad | Substantial modal verses; short returning refrain |
| The Reach | Reel-based puirt-à-beul | Dense articulated syllables driving a duple reel |
| Falkreath | Karelian runo-song | Short descending cells, narrow range, recurring five-beat cycle |
| The Rift | Playford-style English country-dance jig | Bouncing 6/8, compact repeated strains, bright chordal punctuation |
| Haafingar | Renaissance galliard | Triple dance motion, shaped cadences, developed lute passagework |
| Hjaalmarch | Instrumental sutartinės on one plucked kanklės | Interlocking repeated figures; exposed neighboring-note clashes |
| Winterhold | Sámi joik, wordless adaptation | Circular short figures, small changes, vocables |
| The Pale | Hebridean iorram-inspired rowing song | Broad sung lines over a measured rowing pulse |
| Solstheim | Persian āvāz-inspired lament | Long modal melismas, flexible timing; initial Dunmeri/Raven Rock core |
| Cyrodiil | Italian early Baroque monody | Expressive solo singing over moving harmony and strong harmonic arrivals |

These are narrow fictional adaptations, not universal definitions of the traditions. Five-beat Falkreath, reel-based Reach and the Pale's slow 6/8 are authored constraints. Hjaalmarch is the least secure candidate: generic eerie arpeggios fail. [UNESCO documents instrumental plucked-zither sutartinės](https://www.unesco.org/archives/multimedia/document-1666), and the [Lithuanian National Culture Centre identifies kanklės as a plucked instrument with a sutartinės repertoire](https://www.lnkc.lt/eknygos/eka/instrum/chordoph.html); the workshop tests one such player.

Use one canonical arrangement per style: **one singer accompanying themself on the recipe's named plucked instrument**, with **wordless vocables for Winterhold** and **instrumental kanklės for Hjaalmarch**. Reach sean-nós uses the same voice-and-lute arrangement as puirt-à-beul. The 16 October instrument-family policy permits suitable named plucked strings, including zithers; the 19 October reconciliation retains all eleven style targets and vocal modes while adopting the limited instrument mappings below. Blind recognition may compare admitted styles within a shared supported instrumental family. Broader side-by-side arrangements, ensembles, alternate moods, stylistic tints, court/folk branches, other cultures and Skaal differentiation remain deferred. Casting and venue controls may hold comparison conditions constant; they add no musical style layer.

### Listening Evidence and Intentional Recipe Revisions

1. Freeze the recipe, canonical arrangement, exact prompt, model/provider route and comparison conditions. Every audible source must match the visible solo performer.
2. Hear several independent, unselected takes per style. Record defining features, missing features, enjoyment and failures separately. One attractive take proves possibility only.
3. Blind-test nearest neighbors, then shuffle the eleven bases together and record confusions. Priorities: Reach/Rift, Falkreath/Eastmarch, Haafingar/Cyrodiil and Pale/Whiterun/Winterhold. Compare sean-nós against Reach puirt-à-beul, Eastmarch, Pale and Solstheim.
4. Repeat with fresh English lyrics where applicable. Shared text is a diagnostic; also test suitable syllable density for each form. Winterhold stays wordless and Hjaalmarch instrumental. Interleave fresh A/B/A requests to check switching and repeatability; preserve every attempt and exact prompt.
5. Assess **each** base separately when listening: defining structure, separation from neighbors, repeatability across texts/takes, enjoyable listening and correct sound sources. An aggregate score cannot establish an untested region's fidelity. Revise or replace weak recipes as evidence arrives; pending or unsuccessful listening does not stop engineering.
6. Keep the active workshop bounded through deliberate source revisions. A revision may admit one provisional experiment or replace a recipe with its rationale, technical constraints and available evidence recorded here; all eleven listening passes are not a prerequisite. Browser verdicts do not unlock anything. Sean-nós remains a separate challenger until an explicit decision replaces the Reach base.

**Evidence ledger:** no baseline has passed yet; no numeric success threshold has been adopted. Record take IDs, prompts, model/route, lyric IDs or wordless/instrumental mode, blind guesses/confusions, enjoyment, failures and decisions in workshop notes; retain the audio with saved takes. Software checks, reference recordings and successful generation are not listening evidence.

The source policy below controls both the UI and workshop server. Deferred profiles retain notes, earlier edited directions and historical takes, but cannot submit new generations. Earlier browser edits are preserved separately and do not override the new baseline defaults. Increment `workshop_baseline.revision` whenever an adopted recipe changes so saved drafts from the prior revision remain historical.

```yaml
workshop_baseline:
  revision: "baseline-11-v2"
  status: "listening_pending"
  gate: "The eleven bases, Reach comparison and supported blind instrument-family comparisons remain admitted. Listening validation does not gate engineering. Further workshop admission requires a deliberate source revision with rationale and any available evidence; all eleven listening passes are not required."
  profiles:
    eastmarch: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "Falkreath; Reach sean-nós", boundary: "Speech-shaped narrow declamation must differ from repeated five-beat cells and flowing ornamented airs."}
    whiterun: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "The Pale; Cyrodiil", boundary: "Substantial modal verses and a short refrain, without jig bounce or moving continuo harmony."}
    reach: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "The Rift; Reach sean-nós", boundary: "Dense syllables drive a duple reel; the Rift has compound jig bounce and less packed delivery."}
    falkreath: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "Eastmarch; Solstheim", boundary: "The recurring five-beat descending cell must be audible. Sadness alone does not distinguish it."}
    rift: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "The Reach; Haafingar", boundary: "Compact strains in bouncing 6/8, distinct from a duple vocal reel or triple galliard."}
    haafingar: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "Cyrodiil; Whiterun", boundary: "Maintain the triple galliard dance and shaped lute passagework, not flexible monody or plain ballad."}
    hjaalmarch: {arrangement: lute, vocal_mode: instrumental, neighbor: "Winterhold; Falkreath", boundary: "One plucked kanklės retains interacting repeated figures and exposed seconds. Generic eerie arpeggios fail."}
    winterhold: {arrangement: lute_voice, vocal_mode: wordless, neighbor: "The Pale; Eastmarch", boundary: "Short circular figures and changing vocables, without English verses or a closing pop chorus."}
    pale: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "Whiterun; Winterhold; Reach sean-nós", boundary: "Broad sung lines over a measured rowing pulse, distinct from small circles or a free air."}
    dunmer: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "Reach sean-nós; Falkreath", boundary: "Long modal melismas and flexible timing, distinct from short metrical cells or Gaelic ornaments."}
    imperial: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "Haafingar; Whiterun", boundary: "Expressive melody over moving bass and changing harmony, without regular dance or modal drone ballad."}
  comparisons:
    reach_sean_nos: {arrangement: lute_voice, vocal_mode: lyrics, neighbor: "Reach puirt-à-beul; Eastmarch; The Pale; Solstheim", boundary: "Connected ornaments and breath-led free phrasing must remain recognizable in English. Prefer it if it passes and is more enjoyable."}
comparison_profiles:
  reach_sean_nos:
    culture: "Nord"
    name: "The Reach · sean-nós comparison"
    audition_race: nord
    audition_region: reach
    reference: "Irish sean-nós singing"
    core: "free-rhythm air, slowly unfolding melody, connected grace-note ornaments and breath-led pauses"
    voice: "flowing ornamented solo line with clear English words and flexible text-shaped timing"
    lute: "sparse plucked notes following the vocal phrase, leaving room for its ornaments"
    lute_instrumental: "one unfolding air with connected picked graces and increasingly ornamented variations"
```

## Deferred Cultural Palette

These directions are retained as future research, **unavailable for new workshop generations** under the current bounded baseline. An intentional source revision may admit a specific candidate without waiting for every regional style to pass. Their instrumental-first vocal-credibility constraints still apply if they are admitted later; engineering can already support their metadata and capabilities.

The initial cultural rollout should use **instrumental-only Orsimer, Khajiit and Argonian performances**, deferring their vocal styles until generated voices are credible. This is a delivery decision based on listening results, not a claim that these peoples cannot sing. Orsimer vocal finalists remain deferred research; Khajiit and Argonian recipes and performer casts currently exclude singing in the workshop. No production Orsimer or Bosmer core has been selected.

| Repertoire | Current direction | Deferred work |
|---|---|---|
| Orsimer | Compare Seven-Step's deliberate 2+2+3 instrumental phrasing and Close-Circle's plucked chord blocks; keep Resonant Name-Songs as an explicitly reduced resonance study | Production vocals, including khöömei/throat singing; require credible vocal weight and an audible moving overtone melody before promoting that finalist |
| Khajiit | Hindustani instrumental raga on sitar or solo bansuri; **Hindustani tabla solo** on one player's dayan/bayan pair is also a full option | Beastfolk vocals; flute/drum game integration and caravan scenes remain later phases |
| Argonian | Sundanese kacapi suling influence adapted to solo kacapi or suling, with recurring kotekan-inspired cells | Beastfolk vocals; no drum-only reduction yet because the current identity depends on pitched cells; dock/Assemblage scenes remain later phases |
| Bosmer | Leaping tales, Hunting-call airs and Spinner's tales remain distinct auditions with appropriate instrumental and vocal reductions | Production core selection, additional visible performers and any unsupported arrangement |

The workshop retains arrangement-specific prompt definitions, real-world style references for every recipe, explicit performer race and target region, and optional saved SkyrimNet lyrics. Default complete music prompts fit Suno's **1,000-character budget excluding lyrics**. Copying exports the whole assembled music prompt, with lyrics available separately; the complete Google request remains available too. Plucked strings can be cittern, oud, sitar, biwa, kacapi or lute as appropriate. Bowed strings are excluded. Unsupported combinations have a stated musical reason rather than a generic reduction that loses the style.

The retained research catalog is wider than the active workshop baseline and game release. Instrumental-only cultural repertoire still needs a selected recording, a registered capable performer and the appropriate game animation/controller path; it is not automatically enabled by an audition or by this document.

## Reference Listening and Palette Revisions

The companion [reference listening guide](skyrim-hold-music-listening-notes.md) now lives beside this spec in the project vault. It contains the playlists, listening cues, comparisons and possible revisions migrated from `Home/Skyrim/hold_music/`. The user is ear-testing these influences against the recordings. The guide's written criteria and catalog matches are not themselves scores from listening to generated takes. This guide owns the listening research; this spec owns the current prompt fragments. Both are edited directly in the same repository, rather than maintained as separate Home-vault copies.

Keep the **current recipe**, a **proposed listening variant** and an **adopted revision** distinct. Record the reason for a change, representative recordings and the audible features to test. Compare the candidate with the existing recipe and its nearest regional neighbor using the same performer, arrangement, region and lyrics where appropriate. A better fit can justify changing the musical target itself, not only making the generator obey the old wording. After adopting a revision, update the named reference, arrangement reductions and neighboring comparison criteria together, then rebuild the dashboard; the game palette is a separate integration step. Preserve earlier takes and their exact prompts as historical comparisons.

The rímur-only Eastmarch and iorram-inspired Pale candidates were adopted into the **provisional audition baseline on 2026-10-13**. This is target selection, not a listening pass. The guide's older mixed targets are superseded by the eleven-style table. Reach sean-nós has a separate comparison ID, prompt and take history.

## Implementation Baseline

- The current [Hold Music 0.2.2 request adapter](game-adapter.md) applies Nord recipes for all nine holds to new compositions using a model-copied bard/location marker. Lurbuk retains the legacy treatment. This pilot does not implement race-aware repertoire selection, and SkyrimNet still controls scheduling, its shared cache and playback. A Nord performance is documented in the [9 October in-game verification](game-adapter-verification.md#first-in-game-performance-through-hold-music--9-october-2026-1114-central); that is not validation of the wider palette.
- The workshop supplies explicit race, region and arrangement context to Lyria 3.5. These controls are audition inputs, not proof that the game adapter receives the same fields. The game adapter and offline executor currently use a separate OpenRouter/Lyria route. Rebuilding synchronizes the repository's local package only; it does not deploy this baseline to a running game. The shared regional helper keeps Hjaalmarch instrumental and Winterhold's vocal requests wordless.
- The current SkyrimNet performance path uses the lute animation. Phase 1 therefore remains one plucked-string performer, with voice only for an eligible repertoire; flute, drum, voice-only and ensemble control need separate integration work. New Orsimer and beastfolk repertoire follows the instrumental-first release gate above, not the pilot's generic vocal probability.
- A visible lute can represent a family of plucked-string sounds. Other instruments likewise use plausible animation families rather than a single literal timbre, subject to listening and visual tests.
- Audience clapping has been observed during the Olaf festival and the corresponding applause assets were located. Repeatable start, timing and stop control still need a prototype; stomping remains unverified.
- The [bard roster and biography audit](bard-roster-and-biography-audit.md) supplies the installed-profile baseline and candidate musicians. Static record eligibility is distinct from current save state.
- The owned game controller is installed on HALCYON. Its 15 October test crashed in PapyrusUtil VR's native dead filter during candidate discovery; a targeted workaround passed 52 package tests and the recorded VFS checks and was installed. Successful owned playback and cleanup after the fix remain unverified. SkyrimNet's bard feature was disabled for that session. See the [RCA and retest](sven-crash-2026-10-15.md).
- The planned next stack target is MGO RC5 with SkyrimNet beta 27 or its verified successor, upgraded together. The [migration plan](stack-migration-rc5-beta27.md) retains the existing stack as a reference and compares native imports against Hold Music's ownership requirements. Neither the upgrade nor palette listening blocks portable engineering.

## Target Architecture: Hold Music Owns Performances

**Status: offline components implemented; independent controller installed, successful owned playback still unverified after the 15 October fix.** Hold Music is intended to own repertoire selection, scheduling, its song library, conditional lyric composition, music generation and performance lifecycle. SkyrimNet remains a source of character context. The [ownership design](performance-ownership-design.md), [library contract](library-format.md), [executor](executor.md) and [game-package verification](game-package-verification.md) describe the implemented pieces and remaining integration gates. Installation and offline tests do not establish synchronized playback.

**20 October production identity checkpoint:** Python preparation and selection
carry a frozen recipe revision, model, actual named instrument, instrument family,
arrangement and voice through each request, durable job and saved recording.
Matching the region alone is insufficient. Existing unversioned recordings stay
readable and unchanged; their missing identity remains unknown. A lute animation
may request the recipe's named plucked instrument, without changing the current
musical prompts. The installed Papyrus pilot still requires separate integration
of this full selection contract. This engineering checkpoint neither admits
additional styles nor requires listening validation.

- Choose the performer, repertoire and actual arrangement, then check for an eligible cached recording before requesting new content. An instrumental or wordless-vocal piece needs no lyric-writing call. A repeat performance can reuse its recording; a new arrangement can reuse a suitable existing lyric. Generate new words for a requested/upcoming lyrical performance that needs a new composition or topic.
- Build the lyric brief from knowledge available to that bard. The shipped lyric template uses identity, location, voice, memories, witnessed events, recent dialogue and previous song titles. A generic call to the template does not populate these values automatically.
- Keep compositions and recordings distinct: title/lyrics/context provenance belong to a composition; performer, repertoire, instrument, vocal mode, arrangement and recipe/model version belong to its recording. Hold Music should own its metadata rather than extending SkyrimNet's live song table ad hoc.
- Generate asynchronously ahead of playback where possible. A waiting or failed provider request must not leave an actor trapped in a performance pose. Prefer an eligible existing recording when one is available.
- Coordinate audio, animation objects, start/stop, dialogue/combat interruptions, cell changes and cleanup. Preserve authored vanilla/mod quest scenes through explicit ownership rules. Existing animation assets may be reusable without starting complete scenes that also control their own audio.

The earlier native-route investigation found general memory/event/dialogue query and custom-prompt exports, with a documented 750-character Papyrus callback cap. The implemented [offline knowledge bridge](knowledge-bridge.md) instead reads actor-scoped memories and qualifying events from SQLite in read-only mode; its lyrical executor uses a separate text-model call. It does not reproduce the built-in bard manager's dialogue selection, runtime knowledge conditions or gossip propagation. Live context acquisition and playback handoffs still need validation.

The bard enable switch is not a lyrics-only mode: installed disabled-feature messages cover song-topic requests and compose/play-song commands. The independent offline knowledge/lyric route is implemented; it does not depend on enabling SkyrimNet's bard manager. SkyrimNet's bard feature was disabled for the 15 October owned-controller test. Keep mutually exclusive ownership for the retest and verify cached playback, vanilla suppression, interruption and reload cleanup. Earlier static assumptions that SkyrimNet would ignore Sven were disproved by his cached playback on 13 October.

## Repertoire Logic and Offline Preparation

The decision engine in `hold_music/repertoire.py` plans from an explicit snapshot of a bard's knowledge, known compositions and compatible recordings. The authored performer registry, durable recording library, read-only offline knowledge bridge and bounded generation executor are also implemented. The executor supports instrumental, Winterhold wordless and actor-scoped lyrical preparation; its current recipes are the Nord regional pilot, not the full cultural workshop palette. Live scheduling and independent game playback remain integration work. See [repertoire logic and runnable examples](repertoire-logic.md), [library format](library-format.md), [knowledge bridge](knowledge-bridge.md) and [executor](executor.md).

**Offline engineering checkpoint, 2026-10-20:** the executor now retains dispatch state, paid responses and accounting in a private journal, with explicit provider-free recovery of saved audio. Reviewed continuation can authorize the first music request from retained lyrics using the frozen recipe, original knowledge scope and a token tied to the reviewed state and budget. Separate operator reconciliation can close one uncertain call without resending it or erasing its evidence. Malformed returned results remain retained and blocking. These operations require explicit action; offline tests use fake providers.

The [offline integration proof](offline-integration.md) links synthetic actor knowledge, cached selection, topical proposals, versioned staging and receipt feedback without generating music. The ownership tools provide a read-only VFS observation and reversible configuration plan; the portable package builder produces isolated candidate artifacts. Python production selection carries the full recording identity. Scratch staging now projects that frozen request and each recording's identity key for the [candidate Papyrus selector](candidate-runtime-identity.md), which fails closed for mismatched versioned material and captures selected identity in performance receipts. The builder requires compiled fixtures and binds their results to package/source/disassembly hashes. The [promotion planner](game-promotion.md) validates this candidate evidence and projected metadata, compares static files and inventories protected runtime state without applying changes. A separate [reviewed static transaction path](game-promotion-transactions.md) adds durable backups, guarded per-file apply and rollback that preserves later gameplay history; this checkpoint tests it only against synthetic installations. Candidate verification does not establish installed runtime support; library merging remains blocked. These changes neither revise musical recipes nor establish successful in-game playback.

Existing recordings can receive explicit, source-hash-bound import metadata after review. Unknown provider, recipe revision or instrument provenance remains unknown; an old importer label or today's palette cannot fill those gaps. A separate [library merge review](library-merge-review.md) proposes additive slot remapping, reserves receipt-locked and orphaned assets, and flags contract changes that would make existing performers' recordings ineligible. It writes neither library and does not authorize deployment. Listening confidence remains independent of these technical checks.

The [installed-library inspection](installed-library-inspection.md) resolves each manifest, receipt, lyric sidecar and WAV through the selected profile's ordered loose-file layers. Timestamp-based log discovery is not evidence of a winning runtime input. The snapshot preserves conflicting lower copies and reports missing or invalid effective assets without borrowing source-library data. Captured file handles may corroborate specific current bytes, while actual MO2 injection, archive behavior, write routing and playback remain separate evidence requirements.

The [contract-migration review](contract-migration-review.md) evaluates explicit performer-contract upserts against that fresh installed view. It shows which retained recordings gain or lose candidate identity eligibility without relabeling unknown provenance, rewriting recordings or dropping unmentioned contracts. Asset validation, stored playback flags, reservations and runtime selection remain separate. Missing compatible material or malformed current/prospective metadata blocks the review. A later [library publication transaction](library-publication-design.md) still needs explicit destinations, shared-profile effects, durable manifest-last commit and guarded recovery.

The [publication route planner](library-publication-plan.md) verifies an explicit flat destination snapshot against the fresh effective installed files before reusing the additive merge plan. It binds proposed audio/lyrics/manifest paths, exposes shared-profile effects and checks that each selected-profile target would win. It does not flatten files, loosen migration blockers, infer write destinations from file handles or provide an apply command.

**20 October SE testing decision:** the user authorized an isolated Skyrim SE
1.6.1170 lab for repeatable real-engine testing. Its physical game copy and
portable MO2 profile are separate from Steam's managed installation and VR/MGO;
both existing Steam manifest locks remain unchanged. The first SKSE-only
bootstrap reached QASmoke. A separate, explicitly armed lab quest tests scripted
inn entry, discovery, strict recording identity and completion/interruption
receipts with an eight-second synthetic PCM fixture. Offline test success is not
an in-game performance result, and SE success cannot certify VR-native
compatibility, audibility or visual animation quality. SkyrimNet/MCP is a
subsequent integration tier; no paid calls or musical recipe changes are
required. See the [lab setup, evidence and remaining checks](se-testing-lab.md).

The pinned PapyrusUtil 4.6, SkyUI 5.2SE and Address Library 11 archives are now
installed and hash-verified in that lab. Preflight passed 442 checks. The first
Hold Music engine run reached the inn but failed Sven's eligibility check
before playback; preserve that failure as evidence, not a successful
performance. The user subsequently released Steam for overnight lab testing.
The revised harness confirmed result serialization and reached playback. A real
engine error in the candidate's identity-array reset was fixed with a typed
allocation; a subsequent engine receipt now contains the full recording identity.
Controlled completion passes with a full-identity receipt and restored
fixture state. Harness20 passed requested interruption after moving its stop
request ahead of expensive result persistence. The same matched pair also passed
fresh completion and actual ambient inn entry through production scan/selection.
Each run appends one full-identity receipt and restores fixture state. These
controlled fixtures do not establish natural NPC AI, visual/audible quality or
VR compatibility.
Preserve all earlier failures and this timing failure; do not treat partial
assertions as a passing scenario. See the
[overnight checkpoint](se-lab-overnight-2026-10-21.md).

A [separate SkyrimNet lab preparation tool](se-lab-skyrimnet.md) now describes
the pinned dependency payload and verifies an isolated instance's disabled,
credential-free seed files. Native acceptance is checked separately. A reviewed
install command can now
publish that exact payload into a new independent MO2 directory, with retained
interruption evidence and explicit recovery. A separately reviewed one-shot
launcher requires three accepted baseline captures and records exact process
ancestry; its local collector records bounded metadata without HTTP/MCP or
provider calls. This prepares the next coexistence milestone while retaining
the smaller controller baseline and its outstanding runtime checks.

The first installed SkyrimNet tier stopped in MO2 before a game process was
observed. A confirmed Qt INI path-escaping defect is corrected in source;
actual Qt 6.7.1 regressions verify the generated game paths and local-save
settings. Exact generated bytes now gate both fresh INIs. The failed instance,
evidence and original source have been retained intact, with verified inventories
and unchanged protected paths. A fresh corrected installation and preflight
passed but reproduced the same early MO2 crash before Skyrim. Both attempts are
preserved. Matching official symbols identify an omitted `USERNAME` launch
variable causing MO2's startup logger to dereference null. The inherited-value
correction and explicit Steam-edition seed pass the full 84-case suite (one
expected Windows skip) and independent review. The next launch passed that
native crash and stopped before Skyrim at a bundled plugin's missing
`ProgramW6432` requirement. Its exact source and complete instance are retained.
The next seed also supplies the profile's required empty `SkyrimCustom.ini`
and the pinned shipped Skyrim INI defaults; these avoid a source-confirmed MO2
repair dialog and preserve the known baseline's vendor startup settings.
The fourth isolated launch reached Skyrim, with all seven expected native plugins
reported loaded in the fresh SKSE log. That run's effective SkyrimNet configuration
was unverified: its loader rejected the omitted mandatory dialogue-distance field,
preventing later config registration. Native automatic model downloads and
telemetry were observed, despite no requests from our inspection tooling. The
corrected seed supplies the required field and disables both telemetry switches.
The fifth run is positively attributed and passes all 29 typed readback checks
across 13 categories, with seven pinned native module paths/hashes and owned
loopback listeners. Original assets remain unchanged; the explicitly permitted
PrismaUI cache is observed separately. Failed evidence remains retained, and no
musical recipes or listening decisions change.

The separate [native/config smoke collector](se-lab-skyrimnet-smoke.md) adds
bounded, read-only GET checks after exact process, module and listener
attribution. Its 29 synthetic tests and first real settings readback pass.
It does not enable AI, generate content or export raw settings.
The [MCP discovery client](se-lab-mcp-discovery.md) separately passes synthetic
tests and independent review. It requires that successful same-run smoke result
and permits only initialization and tool inventory, with no tool execution.
The [routing inspector](se-lab-skyrimnet-routing.md) adds four fixed read-only
configuration/schema GETs and 27 synthetic tests. Its first live audit remains
incomplete because native defaults add provider/variant/slot routes. MCP discovery
now passes with 56 tools after a pinned transport fix, and one [guarded plugin
query](se-lab-mcp-plugins.md) confirms all five expected profile plugins. This
remains main-menu evidence. Generation stays disabled while routing is diagnosed.
Explicit missing credentials, ambiguous inheritance and
skipped provider/slot branches remain incomplete, without enabling diagnostics.
The [native routing investigation](se-lab-native-routing-findings.md) records
the source-pinned reinsertion rules and an unapplied loopback-only candidate.
MCP transport diagnostics identify duplicate identical Content-Type headers
from this build's SSE handler; the narrowly scoped compatibility change passes
live discovery and the combined 68-case fake suite. The [startup model audit](se-lab-native-model-initialization.md)
separately explains why disabled AI does not suppress every model check.
These findings do not change musical recipes or require listening validation.

The next isolated world-readiness tier uses a fixed QASmoke startup, disables
production playback and harness autorun, and seeds three catalog-matching public
models from retained files without old verification sidecars. Its explicit native
provider defaults need fresh effective readback. The revised routing audit passes
40 synthetic cases while keeping diagnostics, actor/group overrides, native
fallback and egress unverified. A [fixed player snapshot](se-lab-mcp-player.md)
passes 24 independently reviewed cases and permits one literal query after
same-run smoke/discovery. It may persist lab identity bookkeeping; its response
contains no cell identifier. A real world-startup result is still pending.

Runtime receipts can inherit Papyrus string casing (`Sven` versus authored
`sven`). The history adapter resolves only unambiguous source spellings within
the exact save/world scope, so repeat suppression sees the actual performance.
Raw receipts and their captured identity keys remain intact; ambiguous history
blocks planning rather than erasing cooldown evidence. Readable runtime fields
are not rehashed as canonical source identity.

The SE engine fixture also separates controlled playback from ordinary NPC AI.
The current controller starts/stops the idle and audio but does not acquire a
performer AI package; a seated Sven is correctly ineligible. A temporary lab
alias/package may hold a disposable test actor at the stage to isolate playback,
interruption and receipts. Any such result must explicitly report injected AI
control and keep normal actor behavior unverified. Natural tavern performance
under the actor's ordinary packages remains a separate integration check.
The controlled fixture now passes completion and cleanup with one identity-bearing
receipt. It temporarily suppresses the verified fresh vanilla starter through
Sven-only faction membership, restoring exact preexisting membership or effective
absence; it does not claim that already queued vanilla work is drained. The
duplicate-stop fix has native normal-completion evidence and compiled concurrency
regressions. A further reviewed controller admission protocol must acknowledge
its own outstanding native work before fixture release, preserve unresolved
ownership, and resume before real ambient entry. Native validation of that
protocol and deliberate interruption remain pending. The
[production performer lifecycle proposal](performer-lifecycle-design.md)
defines a distinct future AI lease, frozen recording identity, cancellation and
save/load contract; it is not implemented by the lab fixture.

An affected shared profile can reuse the selected library's content validation only after its own fresh inspection and complete before/after equivalence across all 51 mapped paths, including histories, absences and orphan assets. Different physical winners retain their provenance; different library contents remain blocked. This bounded proof does not validate controller ownership, archives, current saves or runtime behavior.

- A successful quest, a scandalous affair circulating as gossip, and ordinary local news are all valid subjects. No heroic framing is required. Select from what the bard knows; hearing gossip does not mean learning a pre-existing song about it.
- Keep direct knowledge and hearsay distinct. Wit, teasing and exaggerated imagery are appropriate artistic choices; repetition does not turn an allegation into a confirmed event. Preserve occurrence and knowledge-acquisition times instead of treating retrieval time as freshness.
- Choose between a familiar recording, another recording of a known composition, or new lyrics for a suitable fresh subject. Instrumental and wordless choices skip lyric generation. Topic/song cooldowns, pending-job deduplication and generation-start limits keep every performance from creating more content.
- The default planner policy is `cache_first`. The example snapshots use `topical_when_salient`, which can prepare a new song about recent news while retaining a familiar playable fallback. These are offline decisions, not paid generation requests or changes to SkyrimNet's settings.
- Save/continuity scope, explicitly learned repertoire and exact recording identity prevent another bard's private knowledge or incompatible recording from becoming an automatic performance. The future live bridge must preserve those boundaries.

## Goals

- Two bards of different cultures in the same inn sound different.
- Nord bards in different holds sound different.
- No fragment implies an instrument or performer that is not visible.

## Non-Goals

- Changing a bard's visible game instrument or animation family through palette edits alone. Later instrument support needs Phase 2's animation/controller work and runtime checks; that work does not wait for regional listening results.
- Enabling live knowledge ingestion or independent performance ownership through palette edits. Offline lyric preparation is a separate implemented tool; the audition workshop can optionally reuse saved SkyrimNet words without invoking its lyric generator.

## Design Principles

1. **Performer first.** The visible animation fixes an instrument family and the roster fixes the number of performers. Variation can use related timbres, mode, meter, articulation, ornament and vocal technique without introducing an unseen player.
2. **Learned tradition sets the idiom.** Race is a fallback when individual training is unknown. Region provides a compatible local influence. Established character identities, such as Ogmund’s Nordic skald tradition, remain meaningful away from their place of origin.
3. **Named influences plus features.** Every complete recipe names its real-world style reference and gives concrete musical features. A label alone tends to collapse into generic fantasy tavern music; omitting the name also loses useful direction. Describe the actual solo or ensemble adaptation.
4. **Distinct palette before nuance.** Give each core a recognizable rhythmic, melodic and textural identity with a predominant mood. Do not flatten the palette by giving every culture an equal share of every mood.
5. **Draft selection is not audio validation.** Orsimer and Bosmer finalists are explicit listening candidates, not production defaults. Generation fidelity and animation feasibility remain separate checks; deferred vocals do not block development of a credible instrumental repertoire.
6. **Reference listening can revise the target.** Use recordings to reassess the named influence and the features borrowed from it. Update the prompt and its comparisons when the musical direction changes; do not treat earlier reviews or playlist labels as fixed requirements. Performer identity, setting, visible sound sources and supported arrangements remain constraints.

## Phasing

Engineering through these integration phases can proceed with versioned provisional recipes and existing or synthetic test audio. Listening confidence develops independently; no phase requires all eleven styles to pass. Wider recipe definitions do not automatically grant workshop or production availability. Preserve each phase's actual performer, animation, ownership and lifecycle requirements.

| Phase | Adds | Depends on |
|---|---|---|
| 1 | Regional idioms on solo plucked strings; eligible repertoires may add one voice | Performer context connection, explicit provisional recipes and cultural vocal constraints |
| 2 | Flute and drum | Overriding SkyrimNet's lute-only animation |
| 3 | Visible accompanists recruited from the audience | Phase 1 for voice roles, Phase 2 for instrumental roles |
| 4 | Ambient music at caravan camps and the Windhelm docks | Phase 1; richer with Phases 2 and 3 |

### Phase 1: Plucked Strings Using the Lute Animation

SkyrimNet forces the lute animation, so every performance uses one lute-family player. The recipe may name a compatible plucked timbre such as cittern rather than lute. Orsimer, Khajiit and Argonian cultural rollout starts instrumental only; supported vocal repertoires may add that same performer's voice. This target policy is separate from the existing Nord pilot's 50% instrumental choice.

- Planned Phase 1 fields: `core`, arrangement reductions, `dialect`, compatible `tint`, `voice`, `lute`, `phase_modes` and explicit audition selection.
- Later-phase fields: flute/drum arrangements and additional performer roles; reductions already matter for Phase 1 lute-only comparisons.
- Orsimer and Bosmer have defined candidate profiles. Their selected production cores remain unset; engineering fixtures explicitly name a candidate without selecting a production winner or admitting it to the workshop. A future source revision can select a provisional core with its rationale and confidence recorded. Orsimer vocals, including Resonant Name-Songs' specialist technique, stay outside the initial release while vocal credibility is unresolved.
- Khajiit and Argonian instrumental profiles become usable when an existing or nominated NPC is explicitly registered as capable of the requested role; ancestry alone does not assign new skills. Their proposed ambient scenes still belong to Phase 4.
- Done when the acceptance criteria pass with the visible instrument family fixed to plucked strings.

### Phase 2: Instruments

- Enable the flute and drum arrangement lines after their animation/controller paths are validated.
- Khajiit solo bansuri and tabla, and Argonian solo suling, are retained research recipes requiring intentional admission and this phase's game support. Supporting their instrument families does not depend on regional listening passes. Tabla means one player using a two-drum pair; it does not add a second performer. Argonian drum solo remains omitted until a distinctive rhythmic repertoire is designed.
- Instrument material preferences can be assigned to particular Bosmer characters. There is no blanket racial lute ban; the visible prop and established biography remain authoritative.
- Decide who picks the instrument: fixed per NPC or selected per performance from the chosen repertoire and the performer’s capabilities.
- Done when the acceptance criteria pass across all three instruments.

### Phase 3: Accompanists

Audience members are recruited into visible accompanying roles.

- Principle 1 widens from "solo only" to "every sound has a visible source". The performer block lists exactly who is playing and what.
- New input `accompanists`: a list of visible performers, each with a role (voice, drum, flute, clapping).
- The selected learned tradition chooses the idiom. Accompanists supply only the roles present in the arrangement; they do not automatically receive professional bard skills.
- Plural-performer language becomes legal, but only when it matches the accompanist list exactly.
- Ensemble support does not clear a deferred vocal style's fidelity gate. Initial beastfolk community arrangements remain instrumental, and Orsimer vocal ensembles still require credible voices before production use.
- This unlocks the multi-voice forms that Phases 1 and 2 imitate on one instrument:

```yaml
ensemble:               # appended only when accompanists are present
  cultures:
    nord: "listeners join on the refrain"
    orc_seven_step: "the leader's line is answered together by the listed singers on one short phrase"
    orc_close_circle: "one lead voice and two listed response voices change chord tones and release together"
    bosmer: "the listed second performer answers a complete short phrase after a gap"
    argonian: "each performer repeats a different short cell so the parts interlock"
  holds:
    eastmarch: "a second voice shadows the melody in parallel fifths"
    hjaalmarch: "two voices a whole step apart chase each other in tight canon"
    rift: "the room joins on the refrain, loud and ragged"
```

- Named multipart and instrumental-ensemble traditions remain explicit musical influences in reduced prompts. Actual sound sources must still match the visible roster: a solo or three-voice adaptation of canto a tenore is a reduction, not the authentic four-part form.
- A singer's fundamental and audible upper overtones can belong to one voice. This does not authorize adding recorded backing voices. One flute player alternates playing and singing; simultaneous sustained flute and voice require separate performers.
- Done when the performers described in every prompt match the visible performers one for one.

### Phase 4: Ambient Scenes Outside the Walls

Occasional music from nominated community performers at the Khajiit caravan camps and Windhelm docks/Assemblage. These are the first target scenes, not an absolute claim that every Khajiit or Argonian must remain outside cities. A New Gnisis Cornerclub resident is another proposed community musician; existing quest-dependent performances there need coordination.

| Scene | Profile | When | Notes |
|---|---|---|---|
| Caravan camp | `khajiit` | Night, while the caravan is camped | Mode follows `moon_phase` |
| Windhelm docks | `argonian` | Day, during work | Pitched repeating-cell instrumental repertoire; no implied work chorus |
| Argonian Assemblage | `argonian` | Occasional evenings | Instrumental social performance; ensemble responses deferred |

- These community scenes default to their own repertoire. A location tint applies only when chosen for that audience and compatible with the core.
- Needs a trigger (location, time of day, a free NPC to perform) and a frequency cap so it stays occasional.
- A visible performer is still required. The Phase 1 instrument family is plucked strings; flute and tabla scenes depend on Phase 2. Community participation must not reintroduce deferred beastfolk vocals.
- NPC nominations, scenes and triggers remain proposed; the inventory records the candidates.

## Inputs

These are the full target context fields. The workshop supplies audition race, region and arrangement; the current game pilot receives bard/location text, and the offline library supplies authored identity and region. Neither path yet establishes this complete live, race-aware contract.

| Input | Values | Required | Notes |
|---|---|---|---|
| `performer_id` | Stable actor identity, including originating plugin/form | Yes | Names and three-digit prompt suffixes alone can collide |
| `race` | Normalized cultural fallback | No | Include custom Khajiit races and ElderRace mappings where appropriate |
| `known_traditions` | Authored or biographically established repertoire | No | Takes priority over ancestry; College training expands choices |
| `tradition` | Explicitly selected core or audition candidate | During auditions | Orsimer/Bosmer finalists are not an equal random mix |
| `vocal_techniques` | Technique, evidence status and proficiency | For specialist forms | Solo overtones require an affirmative individual capability; unknown is not mastery |
| `voice_character` | The actual singer's age, vocal register, weight, texture and delivery; gender when specified | For sung performances | Describes the performer separately from the learned repertoire; an Orc tradition does not turn a non-Orc performer into an Orc |
| `region` | Skyrim hold, Cyrodiil, Raven Rock, Skaal community, other/unknown | No | Interiors inherit their parent region; community identity can be more specific |
| `hold` | Skyrim hold or unknown | No | Legacy location field; retained as a regional lookup input |
| `instrument` | lute, flute, drum, voice-only | Yes | Animation family; voice-only remains gated on animation validation |
| `sings` | Boolean | Yes | A flute player who sings must alternate phrases or have another visible player |
| `college_trained` | Boolean | No | Not equivalent to current College-faction membership and not a forced Haafingar override |
| `register` | court, tavern, camp, work, ceremonial | No | Selects an appropriate available repertoire, not an automatic new skill |
| `song_form` | For example Reach air or dance | Where needed | Avoid merging contradictory tempos in one core |
| `moon_phase` | new, waxing, full, waning | No | Khajiit condition; initially Masser, if its phase is available |
| `accompanists` | Exact visible performers and roles | For ensembles | Includes response voices, instrument players and clappers |

## Resolution Rules

The current workshop selects exactly one admitted recipe and its canonical arrangement, without tints, alternate moods or cultural branches. The following broader rules describe deferred architecture.

1. **Select a learned repertoire.** An explicit audition or known performer tradition takes priority. Otherwise use a mapped cultural fallback. For cultures with `selected_core: null`, explicitly name the candidate in an admitted audition or engineering fixture; do not silently ship the shortlist as random variants or fall back to a missing culture layer. Production selection remains pending and does not prevent selector implementation or offline tests.
2. **Resolve the occasion and region.** Use current region/community and available repertoire. Breton court/folk and Imperial court/vernacular are distinct choices. College training makes learned forms available; it does not replace the location or erase personal tradition. The new Cyrodiil vernacular is independently selectable.
3. **Apply regional dialects deliberately.** A Nord regional performance may use the matching dialect as its core. A biography-selected or named tradition retains its core away from home. Thus Ogmund does not automatically become a Reachfolk musician, and a Bosmer trained in Nordic ballads retains that option.
4. **Apply only compatible tints.** Tints may adjust density, ornament or local phrasing. Drop a tint that erases the chosen meter, articulation, predominant mood or defining technique. No Hjaalmarch neighboring-tone requirement is added to a stable Orsimer overtone fundamental.
5. **Khajiit.** Keep the existing hold-tint exemption and append the selected moon condition when available. A condition changes the course within the family; it does not replace the musical identity.
6. **Check the actual arrangement and vocal gate.** Initial Orsimer, Khajiit and Argonian cultural releases are instrumental only; do not attach lyrics or vocal clauses. Experimental Orsimer vocal auditions remain outside the active baseline. The workshop excludes singing for either a Khajiit/Argonian recipe or performer cast, even when the other selection is a different culture. For eligible sung arrangements append only the chosen instrument-family line and voice line. A flute player alternates vocal/instrumental phrases. Specialist technique and ensemble descriptions require affirmative capability and the matching visible roster. An ordinary novice does not acquire overtone mastery from race.
7. **Use the right reduction.** For drum-only performances without singing omit pitched material and use the rhythmic line. A drum-and-voice arrangement can retain the pitched vocal structure. Where a lone flute, voice, or drum-and-voice arrangement cannot support a drone, chord blocks or simultaneous counterpoint, replace the ordinary core with `core_monophonic`; adding an instrument line does not cancel an incompatible core. For other instrumental performances use the explicitly described instrumental arrangement. Instrument-only clauses describe melodic phrases, not an absent singer; remove any voice-dependent answer/accompaniment wording. During comparisons, audition the candidate's honest reduction; do not conceal weakness by switching styles. In eventual production, an unavailable reduction may select an explicitly designated instrumental repertoire, with the actual repertoire recorded in the cache identity.
8. **Fallback and caching.** Unknown culture and unknown region preserve existing behavior. Record performer/repertoire, actual instrument family, vocal or instrumental mode, technique, roster and relevant location/moon conditions in the complete cache identity so a track cannot imply a different arrangement. The offline library has explicit recording identity; the SkyrimNet pilot's shared native cache does not enforce this cultural contract. Its existing 50/50 composition policy remains the pilot baseline. A future cultural selector applies vocal eligibility first, so that probability never overrides the instrumental-only release gate.

## Prompt Assembly

Order:

1. Named `reference` with a brief solo, single-line, three-voice or rhythmic adaptation label
2. Tamriel/Elder Scrolls setting, explicit target region, adult performer race and actual arrangement
3. One intimate acoustic-room instruction and compact vocal casting when singing
4. Arrangement-compatible `core` or `dialect`, voice technique and selected instrument treatment
5. One instruction tying generated lyrics to the performer and setting; supplied lyrics instead remain a separate, verbatim block

The workshop adds performer and region context to every complete request, including saved custom musical directions. Race defaults to the profile's provisional audition cast and can be overridden separately for A and B. Target region defaults to the named hold for regional profiles, Cyrodiil for monody and Raven Rock for the Solstheim lament. Deferred cultural profiles retain their historical defaults. A shared region override lets both auditions use the same place.

Every workshop recipe names a real-world musical reference, including original fictional candidates and requests with saved custom directions. The compact complete prompt leads with that name and labels the selected adaptation. The arrangement-compatible musical clauses supply the concrete features; `reference_focus` remains editorial rationale rather than another repeated prompt paragraph. Instrumental and rhythmic reductions retain the name and their actual sound sources. These are audition influences, not claims that the invented Tamrielic forms are authentic versions of the source traditions.

Default complete music prompts fit within a 1,000-character budget, excluding lyrics. The workshop shows a live character count and separate **Copy music prompt** and **Copy lyrics** controls for interfaces such as Suno. Saved custom directions remain intact; an over-budget edit is flagged, never truncated. **Reset to recipe** adopts the compact defaults. The exact Google request remains available separately and includes supplied lyrics with the verbatim instruction. Inline `Lyrics:` blocks are also separated for music-only copying and counting while the full API request retains the user's original words.

```yaml
audition_context: "An in-world acoustic performance in Tamriel, in the Elder Scrolls setting. The music is made by the listed performers in the room, with natural close room acoustics rather than a cinematic backing score."
audition_races:
  nord: "Nord"
  imperial: "Imperial"
  breton: "Breton"
  redguard: "Redguard"
  dunmer: "Dunmer (Dark Elf)"
  altmer: "Altmer (High Elf)"
  bosmer: "Bosmer (Wood Elf)"
  orc: "Orc (Orsimer)"
  khajiit: "Khajiit"
  argonian: "Argonian"
audition_regions:
  skyrim: "Skyrim; no specific hold or settlement assigned"
  haafingar: "Haafingar, around Solitude, Skyrim"
  eastmarch: "Eastmarch, around Windhelm, Skyrim"
  whiterun: "Whiterun Hold, Skyrim"
  reach: "the Reach, around Markarth, Skyrim"
  falkreath: "Falkreath Hold, Skyrim"
  rift: "the Rift, around Riften, Skyrim"
  winterhold: "Winterhold, Skyrim"
  pale: "the Pale, around Dawnstar, Skyrim"
  hjaalmarch: "Hjaalmarch, around Morthal, Skyrim"
  cyrodiil: "Cyrodiil; no specific city assigned"
  raven_rock: "Raven Rock, Solstheim"
  skaal: "the Skaal community, Solstheim"
audition_voices:
  orc: "dark, full-bodied, grainy low-to-mid voice with weighty chest resonance and firm, unforced delivery"
  khajiit: "warm, husky, throaty voice with subtle rumbling grain, clear consonants and supple phrasing"
```

The Orc finalists' `audition_casting` fields describe provisional voices for experimental listening tests, with production vocals deferred. The retained Khajiit voice direction is reserved for future work and is not used by current instrumental-only prompts. These are casting choices, not definitions of a tradition or rules for every member of a race. They do not select a gender or confer technique proficiency. An eligible race override selects the matching vocal character instead of carrying the repertoire's Orc cast into another performer. In eventual NPC integration, the actual performer's `voice_character` replaces audition defaults. Instrumental prompts still name race and place but omit vocal casting and technique; a three-singer experimental arrangement retains its exact roles.

Performer and region controls, a context summary and the exact-request preview expose the complete audition context. Existing custom musical directions are preserved in their historical prompt set. Only current-baseline edits override defaults; **Reset to recipe** clears the current edit without deleting the historical set. Context instructs newly generated lyrics to keep the performer identity and venue consistent without announcing the race or inventing a birthplace. With no named settlement selected, lyrics avoid naming the current venue. Supplied SkyrimNet lyrics remain unchanged: their characters and locations are song subjects, not authority to recast or relocate the audition. Saved takes retain the exact prompt originally sent to Google.

Saved lyrics are optional: the shared picker reads existing `bard_songs` drafts from configured SQLite sources in read-only mode and supplies identical words to both panels. Refreshing it invokes neither SkyrimNet's lyric generator nor Google. **Let Lyria write lyrics** leaves a supported sung request without a saved draft; a custom `Lyrics:` block is another explicit source. Instrumental Hjaalmarch and wordless Winterhold omit the selected draft and reject inline lyric blocks. Selecting an archived lyric does not install that composition into the game.

Google's [Lyria prompt guide](https://ai.google.dev/gemini-api/docs/lyria-prompt-guide#vocal-delivery-and-singer-profiles) recommends explicit vocal range and timbre. Setting names provide context; the casting and technique clauses describe the sound to audition. Their effectiveness still requires listening.

Example, Nord with lute and voice in Windhelm:

```
Style: Icelandic rímur (solo adaptation).
Tamriel (Elder Scrolls): Eastmarch, around Windhelm, Skyrim.
One adult Nord performer singing with plucked lute.
Intimate live acoustic room; only this performer and lute.
Austere chanted verse, narrow melodic range and long pauses.
Voice: syllabic chest-register declamation.
Lute: bare fifths and single notes shadowing the voice.
Lyrics fit the performer and region; keep race implicit.
```

Example, Redguard with solo oud in Dawnstar, instrumental:

```
Style: Arab-Andalusian song and Spanish Renaissance vihuela (solo oud reduction).
Tamriel (Elder Scrolls): the Pale, around Dawnstar, Skyrim.
One adult Redguard performer; solo oud instrumental, plucked strings.
Intimate live acoustic room; only this performer and oud.
Phrygian color, recurring rhythmic cycle, ornamental runs returning to firm cadences.
Oud: distinct plucked attacks, brief melodic runs and spacious phrase endings.
```

## Culture Profiles

Only `imperial` (Cyrodiil) and `dunmer` (Solstheim) are currently admitted from this section. Other definitions remain deferred research.

These are selective compositional references, not complete descriptions of the real traditions or claims of canonical Tamrielic music. Predominant moods are intentional. `orc` remains the internal key for Orsimer.

| ID             | Reference tradition                                    | Why                                                                 |
| -------------- | ------------------------------------------------------ | ------------------------------------------------------------------- |
| `nord`         | Scandinavian medieval ballad                           | Strophic, modal, drone-heavy storytelling                           |
| `imperial`     | Italian early Baroque monody       | Expressive solo melody with strong harmonic arrivals |
| `imperial_vernacular` | Italian frottola and Renaissance villanella, adapted as an original vernacular | Firm pulse, short refrain and clear cadences for Cyrodiil |
| `breton_court` | French air de cour                                     | High Rock's feudal courts                                           |
| `breton_folk`  | Breton gwerz                                           | Narrative lament for the folk register                              |
| `redguard`     | Arab-Andalusian song, Spanish vihuela (Milán, Narváez) | The lute played like the oud it descends from                       |
| `dunmer`       | Persian āvāz-inspired lament                      | Exile music for the Gray Quarter                                    |
| `altmer`       | Ricercar, fantasia                                     | Learned counterpoint, the most "Baroque" of the set                 |
| `orc`          | Three original finalists; khöömei provides one vocal-technique reference | Resonance, deliberate grouping and collective precision; see shortlist |
| `bosmer`       | Three original finalists                               | Agile discontinuous phrases, clear attacks, register contrast and purposeful gaps |
| `khajiit`      | Hindustani instrumental raga and tabla solo, with Rajasthani desert color | Sitar or bamboo flute for unfolding melody; tabla for intricate rhythmic development |
| `argonian`     | Sundanese kacapi suling, retaining kotekan-inspired cells | Instrumental plucked-zither or bamboo-flute audition; a fictional solo adaptation |

```yaml
cultures:
  nord:
    lute_instrumental: "plain modal melody with open-string tonic and fifth drones, a short returning refrain"
    core_monophonic: "strophic modal melody with a short refrain, plain Dorian or Mixolydian phrases and few ornaments"
    reference: "Scandinavian medieval ballads"
    core: "strophic ballad with a short refrain, Dorian or Mixolydian mode, steady drone on the tonic and fifth, plain melody with few ornaments"
    voice: "declaimed more than crooned, syllabic, storyteller's chest voice"
    lute: "simple plucked melody over open-string drones"
    flute: "plain modal melody, few ornaments"
    drum: "steady walking pulse"

  imperial:
    audition_region: cyrodiil
    reference: "Italian early Baroque monody"
    core: "expressive solo melody, flexible speech-shaped timing over moving bass and changing harmony, pronounced harmonic arrivals"
    voice: "intimate rhetorical singing with brief ornamental runs and clear English words"
    lute: "changing chordal support and moving bass, with arpeggiated answers at cadences"
    lute_instrumental: "expressive upper melody over moving bass and changing chords, flexible timing and strong harmonic arrivals"
    flute: "expressive vocal-style melody with cadential ornaments"
    drum: "restrained pulse following the expressive phrases"

  imperial_vernacular:
    lute_instrumental: "short refrain melody between crisp chord strokes, regular pulse and strong cadence returns"
    audition_region: cyrodiil
    reference: "Italian frottola and Renaissance villanella"
    reference_focus: "short strophic refrains, a firm pulse and clear cadences; a vernacular adaptation rather than courtly monody"
    core: "firm regular pulse, short memorable refrain, clear major or minor harmony, decisive cadence returns"
    voice: "direct syllabic delivery with brief ornamental pickups"
    lute: "crisp chordal rhythm with a short melodic answer"
    flute: "clear tuneful phrases returning to strong cadence notes"
    drum: "even dance pulse with clear phrase-ending accents"

  breton_court:
    lute_instrumental: "delicate melody above soft broken chords, small graces and breathing pauses"
    reference: "French air de cour"
    core: "minor or Dorian mode, gentle unhurried pace, speech-like phrasing, delicate grace notes"
    voice: "light, intimate, restrained"
    lute: "soft broken-chord accompaniment"
    flute: "soft, sweet tone with small graces"
    drum: "quiet, restrained pulse"

  breton_folk:
    core_instrumental: "slow strophic instrumental air, long restrained phrases, flexible rhythm and little ornament"
    lute_instrumental: "one restrained repeating melody, sparse plucks and flexible unhurried phrasing"
    reference: "Breton gwerz"
    core: "slow text-led lament, long stanzas on a repeating restrained melody, flexible syllabic rhythm, little melodic ornament"
    voice: "clear plain syllables, unhurried narrative delivery, almost unaccompanied"
    lute: "sparse single notes following each melodic phrase"
    flute: "soft, sweet tone with small graces"
    drum: "quiet, restrained pulse"

  redguard:
    lute_instrumental: "clearly picked Phrygian melody, articulated runs and decisive returns to the cycle"
    reference: "Arab-Andalusian and Spanish Renaissance song"
    core: "Phrygian color, articulated ornamental phrases in a clear recurring rhythmic cycle, runs returning to firm cadence notes"
    voice: "ornamented but clearly articulated phrases, brief melismas ending decisively"
    lute: "oud-like melodic plucking, distinct attacks and brief runs returning to the cycle, few chords"
    flute: "articulated ornamented phrases with clear cadence returns"
    drum: "cyclic hand-drum pattern mixing deep and sharp strokes"

  dunmer:
    audition_region: raven_rock
    reference: "Persian āvāz-inspired lament"
    core: "slow modal lament, long ornamented phrases with flexible unmetered timing and gradual melodic development"
    core_monophonic: "slow modal lament, long ornamented single-line phrases with flexible timing"
    voice: "mournful long-breathed solo line, connected melismas and clear English words"
    lute: "sparse plucked support and short echoes of the vocal melody, little chordal movement"
    lute_instrumental: "long sorrowful modal melody with connected picked ornaments and flexible timing"
    flute: "long breathy modal phrases with slow ornaments"
    drum: "slow sparse punctuation"

  altmer:
    lute_instrumental: "two or three independently moving plucked lines, precise imitation and balanced cadences"
    core_monophonic: "precise sequential imitation within one melodic line, measured phrasing and formal ornaments"
    reference: "ricercars and fantasias"
    core: "learned counterpoint, strict measured tempo, imitative lines, precise formal ornaments, balanced phrases"
    voice: "pure straight tone, exact intonation, little vibrato"
    lute: "two or three independent lines implied on the one lute"
    flute: "one clean line imitates its own earlier phrase in sequence, with precise trills"
    drum: "exact and understated"

  orc:
    selected_core: null   # choose after the audition; no equal-weight random mixture
    audition_candidates: [orc_resonant_names, orc_seven_step, orc_close_circle]
    vocal_favorite: orc_resonant_names
    portable_candidate: orc_seven_step

  bosmer:
    selected_core: null
    audition_candidates: [bosmer_leaping_tales, bosmer_hunting_calls, bosmer_spinners_tales]
    favorite: bosmer_leaping_tales
    material_policy: "individual observance and visible prop; no blanket lute prohibition"

  khajiit:
    lute_instrumental: "long sliding meend phrases over the same instrument’s open drone strings; free alap grows into a measured pulse"
    core_monophonic: "one sliding melodic line around a stable tone, unmetered opening slowly finding pulse and gathering speed"
    reference: "Hindustani instrumental raga, with Rajasthani desert-music color"
    drum_reference: "Hindustani tabla solo"
    core: "sustained drone, unmetered opening that slowly finds a pulse and accelerates, notes joined by slides instead of clean steps"
    lute: "plucked melody with long meend bends, ringing open drone strings on the same instrument"
    flute: "breathy bamboo tone, continuous pitch slides, long phrases returning to a resting note"
    drum: "deep sliding bayan bass against crisp dayan finger strokes; 16-beat teental (4+4+4+4), playful syncopation and increasingly rapid variations; finish with a threefold tihai landing on the first beat"
    ignores_hold_tint: true
    phase_modes:          # suggested starting map, tune by ear
      new: "darkest mode with a flattened second, low register, the pulse arrives late and stays slow"
      waxing: "brighter mode with a raised fourth, rising phrases, gathering tempo"
      full: "bright major or Mixolydian mode, fast, fully metered and dance-like"
      waning: "minor mode, descending phrases, slowing tempo"

  argonian:
    lute_instrumental: "alternating low anchors and rippling upper five-note cells, crisp woody attacks and ringing decay"
    reference: "Sundanese kacapi suling, with Balinese kotekan-inspired repeating cells"
    reference_focus: "a fictional solo adaptation: plucked zither or bamboo flute, with cyclic cells borrowed from the earlier kotekan sketch"
    core: "five-note modal cells, rippling even pulse and alternating registers, poised level intensity, recurring low anchor and a clean abrupt ending"
    lute: "crisp woody plucks, alternating low anchor and bright upper cells on one zither, brief ringing decay"
    flute: "soft bamboo tone with small tongued attacks; one line alternates registers and curls around five recurring notes"
    drum: "interlocking two-handed pattern, steady and unchanging"
```

## Orsimer and Bosmer Finalists

**Deferred under the current bounded workshop baseline.** Historical finalists retain IDs, recipes, notes and takes; new generations are blocked until intentional admission. Their deferred status does not block supporting engineering.

The exploration produced **18 Orsimer candidates and 22 Bosmer candidates**, with an independent palette review adding eight alternatives and challenges. The [complete idea bank](bard-musical-traditions-exploration.md) retains the options and rejection reasons. The names below are working names for invented traditions. They are audition finalists, not six equally frequent production modes.

| Culture | Finalist | Audible identity | Predominant mood | Role in the shortlist |
|---|---|---|---|---|
| Orsimer | **Resonant Name-Songs · throat singing** | One sustained vocal fundamental with a moving upper overtone melody, long vowels, sparse plucked punctuation | Grave, concentrated, enduring | Experimental vocal identity; production vocals deferred; instrumental contour reduction is weaker |
| Orsimer | **Seven-Step Oath-Songs** | Deliberate 2+2+3 grouping, compact four-note material, clipped words, damped instrumental answers and decisive rests | Resolute, exacting, communal | Portable instrumental release candidate; vocal version remains experimental |
| Orsimer | **Close-Circle Songs** | Plain lead phrases with compact chord blocks that change and stop together | Solemn solidarity, intimate warmth | Plucked chord-block release candidate; three-voice form is a deferred ensemble study |
| Bosmer | **Leaping tales** | Quick five-pulse 3+2 grouping, wide angular leaps, dry attacks, shortened answers and sudden gaps | Mischievous, alert, slightly uncanny | Preferred broadly usable Bosmer candidate |
| Bosmer | **Hunting-call airs** | Brief sharply defined calls, separated registers, complete pauses and clean endings | Watchful, restrained, faintly predatory | Strong flute and quiet-instrumental candidate |
| Bosmer | **Spinner's tales** | Conversational singing, a recurring three-note tag, elastic phrase lengths and character changes by one voice | Intimate, absorbing, uncanny | Narrative finalist; weaker as a drum-only or purely instrumental identity |

**The family distinction:** Orsimer holds a sound or brings attacks and endings together; Bosmer moves, breaks off and changes register. Orsimer ensemble chord blocks differ from Altmer independently moving counterpoint. Bosmer complete phrase exchanges differ from Argonian continuous interlocking cells.

The initial Bosmer proposal shared the Orsimer candidate's seven-pulse grouping. The selected Bosmer audition brief uses **five pulses grouped 3+2** instead. Its fast, angular, broken delivery also separates it from Falkreath's slow descending five-beat lament. Meter is a listening target, not a verified model capability.

### Candidate Fragments

These fragments use the same core/voice/instrument contract as the existing profiles. Every finalist now has a named audition influence, with a `reference_focus` that preserves its fictional fingerprint and identifies the reduction. A named audition resolves through `traditions`; no candidate is implicitly activated for every NPC of that ancestry.

```yaml
traditions:
  orc_resonant_names:
    lute_instrumental: "isolated low plucks answered by ringing upper notes; a resonant contour reduction of the vocal form"
    reference: "Mongolian khöömei overtone singing"
    reference_focus: "a steady low foundation with moving upper harmonics; instrumental reductions translate contour and resonance without adding a throat singer"
    audition_casting: "dark, full-bodied, grainy low-to-mid voice with weighty chest resonance and firm, unforced delivery"
    core: "slow breath-length phrases, stable tonal center, sparse resonance and decisive pauses; grave and concentrated"
    voice: "one singer sustains a weighty low fundamental with a moving whistle-like upper-overtone melody; rounded vowels alternate with plain sung phrases"
    lute: "isolated low plucks and spare ringing upper notes, audible decay between phrases"
    flute: "one slow narrow melodic line, separated ordinary and upper-register tones"
    drum: "widely spaced contrasting low and dry strokes"
    required_vocal_technique: solo_overtones
    instrumental_status: reduced_arrangement

  orc_seven_step:
    lute_instrumental: "low damped strokes and a rising-fourth melody mark deliberate 2+2+3 groups, decisive rests"
    reference: "Bulgarian rachenitsa"
    reference_focus: "borrow the 2+2+3 additive rhythm, with deliberate resolute phrasing rather than a fast wedding-dance tempo"
    audition_casting: "dark, full-bodied, grainy low-to-mid voice with weighty chest resonance and firm, unforced delivery"
    core: "seven pulses grouped 2+2+3, compact four-note phrases and rising fourths, dry attacks and decisive rests; resolute"
    voice: "clipped syllabic statements, deliberate consonants and firm phrase endings"
    lute: "damped low strums and short single-note answers marking each uneven group"
    flute: "short clearly tongued phrases with emphatic rests"
    drum: "deliberate two-two-three groups, deep first attack and a clean gap after each full line"

  orc_close_circle:
    lute_instrumental: "simple upper melody against compact low chord blocks, every part releasing together"
    core_monophonic: "one plain narrow melody in slow measured phrases, decisive releases and clean pauses; solemn warmth"
    reference: "Sardinian canto a tenore"
    reference_focus: "compact chord responses and coordinated releases; the listed solo or three-voice reduction is not an authentic four-part tenore ensemble"
    reference_focus_monophonic: "the plain lead melody, short measured phrases and coordinated clean cutoffs, reduced to one line without chord responses"
    audition_casting: "dark, full-bodied, grainy low-to-mid voice with weighty chest resonance and firm, unforced delivery"
    core: "slow measured phrases, a few compact chord shapes changing together, open fifths and collective cutoffs; solemn warmth"
    voice: "one plain text-bearing lead line, short statements ending in clean silence"
    lute: "low chord blocks under a simple upper line, with simultaneous releases"
    flute: "one plain lead melody; a reduction without simultaneous chordal parts"
    drum: "a sparse low stroke at phrase boundaries; reduced rhythmic outline"
    ensemble_roles: [lead_voice, bass_response, middle_response]
    ensemble_clause: "three visible singers: one lead, two compact chord responses, all releases synchronized"

  bosmer_leaping_tales:
    lute_instrumental: "angular wide-leaping melody in quick 3+2 groups, dry plucks and sudden gaps"
    reference: "Balkan aksak dance music"
    reference_focus: "use the selected five-pulse 3+2 grouping, quick wide leaps and sudden rests rather than inheriting another dance meter"
    core: "quick five-pulse groups of 3+2, short angular motives with wide leaps, dry attacks and sudden rests; alert and mischievous"
    voice: "agile clear syllables, light register jumps, pauses with a punchline's timing"
    lute: "dry clipped single notes and occasional open intervals, brief answers at phrase endings"
    flute: "focused tongued tone, agile leaps and short turns cut off by silence"
    drum: "light three-two groups, a clipped final answer and deliberate missing strokes"

  bosmer_hunting_calls:
    lute_instrumental: "isolated two- or three-note calls in high and middle registers with complete gaps"
    reference: "Swedish kulning and Scandinavian herding-call music"
    reference_focus: "brief clear calls, register contrasts and complete gaps, rendered intimately rather than as distant shouting"
    core: "brief two- or three-note calls at separated registers, complete gaps and clean endings; watchful and spare"
    voice: "one singer alternates a clear compact high call with a quieter lower answer"
    lute: "isolated picked calls in high and middle registers, each phrase ending before the next"
    flute: "clear focused calls, fourth and fifth leaps, sharply defined entrances"
    drum: "pairs of contrasting strokes with complete pauses; a rhythmic reduction of the calls"

  bosmer_spinners_tales:
    core_instrumental: "a recurring three-note tag amid irregular phrase lengths, sudden register turns and clear endings; intimate and uncanny"
    lute_instrumental: "a recurring three-note tag, irregular phrase lengths and sudden register turns, sparse plucked punctuation"
    reference: "Japanese biwa narrative song, especially biwa hōshi storytelling"
    reference_focus: "speech-shaped narration, sparse plucked punctuation and the returning three-note tag; retain the chosen lyric language and listed instrument"
    core: "a recurring three-note tag amid changing speech-paced phrase lengths, sudden register turns and clear endings; intimate and uncanny"
    voice: "one conversational singer changes character through register, pacing and articulation"
    lute: "a recognizable short tag and sparse punctuation, fuller playing only in interludes"
    flute: "one recurring figure alternates plain low and ornamented high versions in sequence"
    drum: "short muted strokes in changing phrase lengths, a recurring three-stroke tag and deliberate pauses"
```

For `orc_close_circle`, append `ensemble_clause` only when the three specified singers are participating in the experimental study. Solo plucked strings supply the chordal reduction. Its retained monophonic sketches do not authorize flute or drum choices: the current workshop omits those because they lose the defining chord responses. For `orc_resonant_names`, require `solo_overtones` only for the experimental sung technique, and label the instrumental version as a contour reduction rather than throat singing. For `bosmer_spinners_tales`, an instrumental render uses the tag/phrase structure without pretending that characters are speaking. The same physical roster constraints apply to every profile; game ensembles additionally need validated visible roles.

### What to Audition First

The first live Resonant Name-Songs take (2026-10-08) received listener feedback that its voice was too light and delicate to fit the intended Orc performer. Its submitted prompt omitted Skyrim, Orc identity and explicit vocal weight, and the technique clause omitted the earlier draft's low fundamental. The revised recipe adds setting, separate audition casting and a stronger low-fundamental instruction. Subsequent discussion still identified vocal credibility and convincing throat singing as unresolved model-fidelity problems. These prompt changes do not establish success. Retain the original take as the comparison baseline and defer production vocals while developing instrumental options.

1. Compare the Orsimer instrumental candidates first: Seven-Step's deliberate grouping, Close-Circle's chord blocks and Resonant Name-Songs' honest contour reduction. Use the same performer, region and recording perspective. No winner is selected by this document update. Keep one-singer Resonant/Seven-Step tests as experiments; successful transport or a low chant does not satisfy the vocal release gate.
2. Compare Leaping tales, Hunting-call airs and Spinner's tales on the same performer. Leaping tales is the first default candidate; the other two must earn space by audible distinction.
3. Compare Khajiit sitar, bansuri and unaccompanied tabla as separate arrangements; compare Argonian kacapi and suling for recognizable recurring pitched cells. Do not ask a tabla solo to reproduce a raga melody or add an unseen melodic accompanist. Close-Circle's three-singer study stays experimental and game deployment waits for a matching visible ensemble; the three-person adaptation is not labeled authentic four-part Sardinian tenore.
4. Listen without labels. Score the actual meter, phrase shape, articulation, timbre, source count and identity against the nearest existing neighbor. Overall production polish does not substitute for distinctness.
5. Preserve failed renders as failed auditions: an ordinary low chant is not successful overtone singing; a choir is not one singer; flattened meter has not met the rhythmic target. A simpler core can still win if it remains distinctive.

Real technique references: [UNESCO on solo khoomei](https://ich.unesco.org/en/RL/mongolian-art-of-singing-khoomei-00210?RL=00210), [UNESCO on four-part Sardinian tenore](https://ich.unesco.org/en/RL/canto-a-tenore-sardinian-pastoral-songs-00165), and [Tbilisi State Conservatory's account of polyphonic principles](https://polyphony.ge/en/georgia/georgian-traditional-music/forms/). They support the acoustic distinctions, not the invented Orsimer names or social meanings.

The explicit-name audition revision adds provisional anchors to the original fictional forms: Bulgarian rachenitsa for Seven-Step, Balkan aksak dance music for Leaping tales, Swedish kulning for Hunting-call airs, and Japanese biwa narrative song for Spinner's tales. These choices borrow selected features and preserve the existing recipes; they are not retrospective claims that the forms were modeled completely on those traditions. [University of Arizona's meter guide](https://opentextbooks.library.arizona.edu/folkdance/chapter/chapter-28/) documents the 2+2+3 rachenitsa grouping; Leaping tales retains its separately specified 3+2. [Sweden's Institute for Language and Folklore](https://www.isof.se/folkminnen/amnesomraden/folklig-sang-musik-och-dans/lar-dig-mer-om-folklig-sang-och-musik/fabodarnas-toner) describes kulning and short herding melodies. [Smithsonian's biwa program notes](https://asia-archive.si.edu/podcast/voice-of-the-biwa-junko-tahara-ensemble/) describe narrative song with plucked-lute accompaniment. The Pale's original coastal air uses a provisional Scottish/Hebridean slow-air anchor; the [Scottish Music Centre's Highland-air collection](https://www.scottishmusiccentre.com/shop-all/p/musica-scotica-vol-vii-original-highland-airs-collected-at-raasay-in-1812-by-elizabeth-jane-ross) provides a named song-air and instrumental repertoire for comparison.

### Bosmer Materials and Learning

Keep personal instrument material/observance choices separate from musical idiom. The installed bios give Yarbrough and Daenlyn lute skills and Nordic training; the new Bosmer candidates do not automatically replace their learned repertoire. Imported materials and differing interpretations of the Pact also have textual support: [official Y'ffre Q&A, preserved transcript](https://elderscrolls.fandom.com/wiki/Loremaster%27s_Archive%3A_Y%27ffre%27s_Beckoning) and [The Green Pact and the Dominion, game-book transcript](https://teso.mmorpg-life.com/the-green-pact-and-the-dominion-lorebook/). These are not a blanket ruling on every character's instrument. Bone, hide or imported materials are optional individual details when the prop and characterization support them.

## Hold Profiles

`dialect` supplies the selected regional Nord repertoire. `tint` is a compatible local influence on another selected tradition, never an unconditional overwrite. These are compositional adaptations of the references, not claims that an entire real tradition has these exact properties.

The table and YAML describe the provisional baseline recipes. Sean-nós is separate in `comparison_profiles`; former mixed targets and wider reductions are deferred.

| ID | Capital | Reference tradition | Why |
|---|---|---|---|
| `haafingar` | Solitude | Renaissance galliard | A northern court importing southern polish |
| `eastmarch` | Windhelm | Icelandic rímur | Oldest city, most traditionalist |
| `whiterun` | Whiterun | Scandinavian medieval narrative ballad | The baseline |
| `reach` | Markarth | Reel-based puirt-à-beul | Reachman influence |
| `falkreath` | Falkreath | Karelian runo-song | A graveyard town's music |
| `rift` | Riften | Playford-style English country-dance jig | Tavern town |
| `winterhold` | Winterhold | Sámi joik | Far north, sparse |
| `pale` | Dawnstar | Hebridean iorram-inspired rowing song | Broad sung lines over a measured rowing pulse |
| `hjaalmarch` | Morthal | Lithuanian sutartinės | Interlocking instrumental figures and exposed seconds |

```yaml
holds:
  haafingar:
    reference: "Renaissance galliard"
    dialect: "clear triple galliard dance, balanced phrases, shaped cadences and developed lute passagework"
    voice: "measured syllabic singing that preserves the triple dance pulse"
    lute: "refined passagework and spacious chord answers within the triple dance"
    lute_instrumental: "refined galliard melody and developed passagework over spacious chords in clear triple time"
    tint: null

  eastmarch:
    reference: "Icelandic rímur"
    dialect: "austere syllabic narrative declamation, narrow range and speech-shaped phrases with clear pauses"
    voice: "articulated English narrative verse, speech-shaped and restrained with few ornaments"
    lute: "isolated plucked notes and bare fifths punctuate vocal phrases"
    lute_instrumental: "austere narrow melody, irregular declamatory phrases, bare fifths and clean pauses"
    tint: null

  whiterun:
    reference: "Scandinavian medieval narrative ballad"
    dialect: "substantial strophic narrative verses and a short returning refrain, plain Dorian or Mixolydian melody"
    voice: "plain syllabic storytelling, sustained complete verses and a short refrain"
    lute: "restrained modal support on tonic and fifth, simple plucked answers"
    lute_instrumental: "plain modal verse melody and a short returning refrain over sparse tonic and fifth strings"
    tint: null

  reach:
    reference: "Scottish puirt-à-beul, reel-based mouth music"
    dialect: "duple reel pulse, compact repeating dance strains and dense articulated syllables driving the rhythm"
    voice: "quick clearly articulated English syllables, tightly fitted to the duple reel, voice driving the dance"
    lute: "light plucked support following the vocal rhythm, brief picked ornaments"
    lute_instrumental: "compact reel strains in clear duple time, tightly packed articulated notes and light ornaments"
    tint: null

  falkreath:
    reference: "Karelian runo-song"
    dialect: "mournful repeated narrative cells, narrow range within a fifth, short descending melody in a perceptible five-beat cycle"
    voice: "plain syllabic English lines returning to the same five-beat melodic cell"
    lute: "sparse open strings reinforce each recurring five-beat cell"
    lute_instrumental: "short descending five-beat melody cells, narrow range, sparse open strings and restrained repeats"
    tint: null

  rift:
    reference: "Playford-style English country-dance jig"
    dialect: "bouncing 6/8 jig, major or Mixolydian melody, compact repeated strains and bright phrase-ending accents"
    voice: "direct syllabic English singing, spacious enough to hear the compound jig bounce"
    lute: "bright chordal punctuation between compact repeating jig strains"
    lute_instrumental: "catchy repeated jig strains between bright chord strokes in bouncing 6/8"
    tint: null

  winterhold:
    reference: "Sámi joik, wordless adaptation"
    dialect: "short circular melodic figures return with small variations, open-ended phrasing without a closing chorus"
    voice: "wordless vocables only, intimate recurring figures with small changes; no lyrics, sentences or spoken words"
    lute: "sparse plucked punctuation around the recurring vocal figure"
    lute_instrumental: "short circular plucked figures with small variations and no grand final cadence"
    tint: null

  pale:
    reference: "Hebridean iorram-inspired rowing song"
    dialect: "broad complete strophic lines over a measured slow 6/8 rowing pulse, natural breaths between phrases"
    voice: "long clear English sung lines carried by the recurring rowing pulse"
    lute: "widely spaced low plucks mark the measured rowing pulse without filling every breath"
    lute_instrumental: "broad strophic melody over widely spaced low plucks marking a slow 6/8 rowing pulse"
    tint: null

  hjaalmarch:
    reference: "Lithuanian instrumental sutartinės"
    dialect: "short interlocking repeated figures with exposed neighboring-note clashes and unresolved returns on one plucked instrument"
    core_monophonic: "short repeated figures alternate neighboring notes with unresolved returns; a weaker single-line reduction without simultaneous seconds"
    core_instrumental_monophonic: "short repeated figures alternate neighboring notes with unresolved returns; a weaker single-line reduction without simultaneous seconds"
    voice: ""
    flute: "one reedless flute repeats short cells and successive neighboring notes, leaving brief gaps; no simultaneous parts"
    lute: "alternating short figures overlap on ringing strings, producing audible seconds on one plucked kanklės"
    lute_instrumental: "short interlocking figures and simultaneous adjacent-tone clashes on one plucked kanklės, repeated with unresolved returns"
    tint: null
    core_instrumental: "short interlocking repeated figures, ringing adjacent-tone clashes and unresolved returns on one plucked instrument"
```

## Blind Recognition Auditions

**Accepted direction (16 October 2026), reconciled with the eleven-style baseline on 19 October 2026.** This mode tests the provisional palette; a completed software session does not establish a listening pass.

**Current interaction policy (19 October 2026):** the dashboard uses an open-ended **Play → playback ends → judge → Play** loop. A radio choice selects **Clip** (roughly thirty-second Lyria Clip recordings) or **Full** (complete Lyria 3.5 songs). The listener decides when to stop; remove fixed session-size controls. Enable style judging only after playback ends. Give every style choice a concise musical description through a hover/focus tooltip, without target-specific emphasis. Hide the intended target, prompt, metadata and other answer cues until the listener chooses a style or "I'm Not Sure," then reveal the intended style and one short audible-signature cue. Written reviews remain optional. Use Title Case consistently for UI and document headings.

The original seed configuration is three independent clips for each of the eleven canonical styles, or **33 clips**. Preserve those cached recordings, exact prompts and exposure history. Seeding establishes available listening material, not musical approval. **Play** first selects eligible matching audio according to the replay policy. If no eligible saved recording remains, that explicit action may start at most one new paid generation, cache it and play the result. Disclose the paid fallback before the action. Settings changes, reloads, playback completion and judging must never start a generation. Failure or interruption must not trigger an automatic retry. Separate batch preparation remains explicitly bounded by its disclosed request limit.

**Three-Choice Judging (19 October 2026):** each question offers the intended style and exactly two distinct distractors sampled from the eligible style pool, plus **I'm Not Sure**. Shuffle the three style options without giving the target a fixed position. Save the offered options and their order with the trial; reloads and service restarts must not reroll them. Accept only an offered style or unsure. Preserve completed historical questions and their original options. Move an existing unanswered question to the three-choice format without replacing its audio. Use a one-in-three chance baseline for these questions and keep their scores separate from earlier full-palette results. This presentation change must preserve the existing recording pool and prompt cohort.

Replay has three choices. **None** consumes the unseen compatible queue, then allows the one-generation fallback on **Play**. **All Cached** first selects a cached recording after the configurable interval in hours since its last exposure. **Incorrect Only** first selects previously missed recordings after that same interval, using the latest saved judgment, including practice corrections; unsure counts as a miss. Every audio play, including history playback, resets that recording's interval. When no replay is due, both replay modes fall back to unseen compatible stock, then the one-generation fallback. Replayed audio is always practice; returning to the queue or a new session does not create another first encounter. Balance fresh style exposure across the frozen choice set without changing historical first answers.

Track first-encounter recognition separately from practice and replays. Report overall and per-style accuracy, attempt counts, the chance baseline for the actual choice set, and which pairs are confused. "I'm Not Sure" remains in the recognition denominator but is not an additional target style for the chance baseline. Freeze the format/model/provider route, prompt version, exact prompt, arrangement, actual instrument, neutral lyrics and active choice set for each pool cohort and preserve them with each result. A judging session must use its matching cohort; changed recipes or test conditions cannot silently borrow another pool's recordings or scores. Clip and Full remain distinct through their model and prompt identity; adding the format selector must not rewrite the existing Clip cohort. Keep/rework reactions capture musical suitability separately from recognition. Preserve saved takes and earlier results when the prompt revision changes.

The default target and distractor pool is the eleven bases; each question displays only three of them. Reach sean-nós is an optional comparison with its own identity and history. Deferred cultures are excluded. Neutral supplied lyrics or instrumental auditions must avoid naming the target culture or region in the recording. Winterhold remains wordless in its canonical arrangement and Hjaalmarch remains instrumental. Instrument identity is a legitimate part of a style; also offer comparisons within a shared supported instrument family to check that traditions survive the same animation grammar. The shared family chooses one actual recipe instrument per performer; it does not require every tradition to use the same literal lute.

Blind shared-family studies use only the admitted profiles whose `workshop_arrangements.allowed` contains the selected instrumental arrangement (`lute`, `flute` or `drum`). Each target pool must contain at least three supported styles to supply the intended style and two distractors; a single-style drum study cannot measure recognition. Record the resulting choice set and its chance baseline rather than substituting an unsupported arrangement or silently retaining excluded styles. These explicitly bounded studies do not unlock deferred profiles, broader side-by-side arrangements or new game animations. Honest monophonic reductions retain their limitation in the reveal. Keep canonical and shared-family scores separate.

Use independent fresh generations, whether prepared in a bounded batch or requested once through **Play**, to distinguish recognition of a tradition from memorization of individual recordings. Replaying an answered take is practice; moving a recording between sessions or cohorts does not create a new first encounter. Keep the side-by-side workshop for investigating confused pairs. Short-clip results do not establish full-length Lyria 3.5 behavior; use Full and the intended longer arrangements to confirm finalists. Preserve browser custom directions without silently reusing them as the current blind recipe; show any conflict with a newly selected instrument before a normal workshop request.

## Workshop Instrument Adaptations

**Instrument policy confirmed (16 October 2026):** the lute prop permits any plucked string instrument, including plucked zithers; it does not require a European lute. The flute prop permits any reedless woodwind, including recorder, fife, bansuri and suling. Choose one specific instrument appropriate to the recipe and foreground its name in the outgoing prompt. Do not ask for a literal lute alongside an oud, biwa or another selected substitute. Explicitly exclude bowed-string sound from plucked arrangements and reed-driven sound from flute-family arrangements; a reference tradition does not authorize those additional sound sources.

**Active instrument audit (19 October 2026):** the previous build forced every admitted profile to literal lute, overriding the authored cittern mappings. The reconciled eleven bases use cittern for Whiterun and the Rift, plucked kantele for Falkreath, plucked kanklės for Hjaalmarch, Persian setar for Solstheim, and lute for the six remaining bases. The Reach sean-nós challenger shares the Reach base's lute. These are provisional audition choices and remain unvalidated by generated listening. The [Met identifies setār as a plucked lute used with singing](https://www.metmuseum.org/art/collection/search/747200); [Uniarts' research connects the kantele with Finnish-Karelian runosong](https://www.uniarts.fi/en/projects/kantele-of-the-runosong-culture-and-the-dialogue-of-creativity/) and [identifies its plucked strings](https://www.uniarts.fi/en/events/isme-veila/). The Lithuanian source above supports Hjaalmarch's plucked kanklės. Their use here is an authored adaptation, not a claim of historical authenticity or a new game prop.

`workshop_baseline` retains each style's canonical arrangement and vocal mode. Wider definitions below supply supported reductions for the explicitly admitted blind shared-family comparisons; they do not enable deferred cultures or broader side-by-side generations. Saved custom directions keep their original wording and can conflict with updated names; preserve them as historical drafts, flag the mismatch and offer an explicit reset to the current recipe.

The shared selector chooses an arrangement family; each recipe names its actual instrument. Cittern supplies a bright plucked attack for selected dance/ballad reductions, oud for Redguard, sitar for Khajiit, biwa for Spinner’s tales, and kacapi plucked zither for the new Argonian audition. Other recipes retain lute. All strings are plucked; no bowed-string arrangement is offered. These are provisional timbral choices for fictional repertoire, not claims of historical authenticity or new game props. The [Met’s cittern](https://www.metmuseum.org/art/collection/search/504210) and [sitar](https://www.metmuseum.org/art/collection/search/500759) document those plucked families. [Smithsonian’s Sundanese collection](https://folkways.si.edu/java-sundanese-folk-music/world/music/album/smithsonian) provides the instrumental zither/flute reference for Argonian; the earlier gamelan sketch is retained as repeating-cell inspiration rather than requesting its ensemble.

Khajiit and Argonian recipes are instrumental only. Choosing either race for another recipe also excludes sung arrangements. This is a workshop audition policy motivated by the current model’s voice limitations, not a statement that those peoples cannot sing. Existing vocal takes and edited directions remain stored. Supplied lyrics stay selected but are omitted from instrumental requests.

Orsimer sung and throat-singing finalists are deferred research, while the eventual initial cultural game-release target remains instrumental only. Baseline admission must precede any new audition; an enabled audition is not production approval. Promote an Orsimer vocal style only after convincing voice and technique comparisons; defer beastfolk vocals until the same credibility problem is solved. Phase 1 can audition the plucked-string reductions; flute, drum and voice-only deployment require their later integration gates.

The deferred solo-percussion definitions cover Seven-Step, Leaping tales, Redguard cycles, Rift jigs and Khajiit tabla solos, where the rhythm has a specific signature. The Khajiit percussion variant names Hindustani tabla solo rather than requesting a reduction of a raga melody: one player uses the dayan/bayan pair, teental, bass slides, quick finger variations and a concluding tihai. No melodic accompanist or spoken drum syllables are requested. [Darbar’s tabla guide](https://darbar.org/tabla/) describes the paired drums and solo repertoire; its [teental recital](https://player.darbar.org/videos/dch339-tabla-solo-by-satyajit-talwalkar) documents the 16-beat cycle, and its [concert guide](https://player.darbar.org/packages/indian-music-appreciation-course/videos/concert-performance-sukhdeep-dhanjal-and-harmeet-virdee) explains the threefold tihai resolution. Solo voice is retained for vocal-led forms; chordal court/counterpoint and neighboring-tone recipes omit it. Close-Circle keeps plucked-string reductions and its explicit three-voice study. Flute reductions are single lines; voice with flute alternates. Unsupported choices show a reason before a request can be sent.

`lute` and `lute_voice` remain the stored arrangement keys so older notes and takes remain readable; their workshop labels now mean the plucked-string family.

```yaml
workshop_instrument_rules:
  plucked: "No bowed strings."
  flute: "No reed-driven sound."
workshop_omissions:
  lute_voice: "No sung plucked-string arrangement is defined for this instrumental recipe."
  lute: "No plucked-string reduction preserves this recipe yet."
  flute: "A flute alone loses the defining simultaneous chord responses."
  flute_voice: "Alternating flute and voice would lose the defining continuous vocal or plucked-string treatment."
  drum: "A drum solo loses the defining melody, resonance or harmony; this recipe has no distinctive percussion-only reduction."
  drum_voice: "Percussion would displace the defining free phrasing, chordal support or sustained tonal friction."
  voice: "A lone voice would lose the defining chordal or instrumental structure."
  trio: "Only Close-Circle currently defines a three-voice ensemble."
workshop_arrangements:
  reach_sean_nos:
    plucked: "lute"
    allowed: [lute_voice]
    note: "Sole admitted Reach challenger; compare against puirt-à-beul under the same arrangement."
  orc_resonant_names:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, drum_voice, voice]
    note: "Throat-singing finalist: khöömei, with a weighty low fundamental and moving upper overtones. Instrumentals are contour reductions."
  orc_seven_step:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice, drum, drum_voice, voice]
  orc_close_circle:
    plucked: "lute"
    allowed: [lute_voice, lute, trio]
    note: "The plucked instrument supplies the chord responses; the ensemble study uses exactly three voices."
  bosmer_leaping_tales:
    plucked: "cittern"
    allowed: [lute_voice, lute, flute, flute_voice, drum, drum_voice, voice]
  bosmer_hunting_calls:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice, voice]
  bosmer_spinners_tales:
    plucked: "biwa"
    allowed: [lute_voice, lute, flute, drum_voice, voice]
  nord:
    plucked: "cittern"
    allowed: [lute_voice, lute, flute, flute_voice, drum_voice, voice]
  imperial:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice, voice]
  imperial_vernacular:
    plucked: "cittern"
    allowed: [lute_voice, lute, flute, flute_voice, drum_voice, voice]
  breton_court:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice]
    note: "Voice and flute are single-line reductions of a form usually supported by plucked chords."
  breton_folk:
    plucked: "cittern"
    allowed: [lute_voice, lute, flute, flute_voice, voice]
  redguard:
    plucked: "oud"
    allowed: [lute_voice, lute, flute, flute_voice, drum, drum_voice, voice]
  dunmer:
    plucked: "Persian setar"
    allowed: [lute_voice, lute, flute, flute_voice, voice]
  altmer:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice]
    note: "Flute and alternating voice/flute use sequential imitation; independent counterpoint remains on plucked strings."
  khajiit:
    plucked: "sitar"
    allowed: [lute, flute, drum]
    flute: "bamboo flute (bansuri)"
    drum: "tabla (dayan + bayan pair)"
    omitted:
      lute_voice: "Khajiit repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      flute_voice: "Khajiit repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      drum_voice: "Khajiit repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      voice: "Khajiit repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      trio: "Khajiit repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
    note: "Choose sitar, unaccompanied bamboo flute, or a virtuoso tabla solo on the dayan/bayan pair. Each uses one performer; singing stays omitted."
  argonian:
    plucked: "plucked zither (kacapi)"
    allowed: [lute, flute]
    flute: "bamboo flute (suling)"
    omitted:
      lute_voice: "Argonian repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      flute_voice: "Argonian repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      drum_voice: "Argonian repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      voice: "Argonian repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
      trio: "Argonian repertoire is instrumental only while convincing beastfolk vocals remain unresolved."
    note: "New instrumental study: kacapi-like woody plucks or one bamboo flute. Keep recurring five-note cells; no gamelan ensemble."
  haafingar:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice]
    note: "The baseline keeps one voice and lute in a triple galliard. Other arrangements remain deferred."
  eastmarch:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice, drum_voice, voice]
  whiterun:
    plucked: "cittern"
    allowed: [lute_voice, lute, flute, flute_voice, drum_voice, voice]
  reach:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice, voice]
  falkreath:
    plucked: "plucked kantele"
    allowed: [lute_voice, lute, flute, flute_voice, drum_voice, voice]
  rift:
    plucked: "cittern"
    allowed: [lute_voice, lute, flute, flute_voice, drum, drum_voice, voice]
  winterhold:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice, drum_voice, voice]
  pale:
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice, drum_voice, voice]
  hjaalmarch:
    plucked: "plucked kanklės"
    allowed: [lute_voice, lute, flute, flute_voice]
    note: "Canonical instrumental kanklės preserves interacting figures and neighboring-note clashes; the blind flute reduction uses successive neighboring notes and cannot reproduce simultaneous seconds."
```

## Regions Beyond the Nine Holds

| Region or community | First palette decision | Distinctive role |
|---|---|---|
| Cyrodiil | `imperial`, Italian early Baroque monody | Moving harmony and expressive solo singing; vernacular and subregions deferred |
| Gray Quarter and Raven Rock | Shared `dunmer` core | Predominant mournful modal repertoire; local song choices and arrangement density may diverge later |
| Skaal community | Separate northern tradition slot; no default assigned yet | Do not apply Raven Rock's Dunmeri mapping to all Solstheim residents or duplicate every northern mode |
| Other added regions | Explicit available repertoire, then known character culture, otherwise unknown-region fallback | Preserve individual learning and avoid false location guesses |

Overtone singing is reserved for a deferred Orsimer specialist finalist. A later named Skaal or other performer could learn it, but adding it to every northern region now would weaken the new distinction.

## Palette Boundaries and Alternatives

The objective is distinctness of sound, not equal emotional coverage. Dunmer currently remains predominantly mournful. These working boundaries are reflected in the fragments above; alternatives are auditioned separately rather than silently merged into the core. Revise the comparison criteria when reference listening changes a profile's target, while retaining a clearly distinguishable palette.

| Neighbors | Boundary to preserve | Alternative held in reserve |
|---|---|---|
| Reach / Rift | Dense duple vocal reel / spacious syllabic 6/8 jig | Sean-nós is the sole admitted challenger, not an automatic alternate |
| Falkreath / Eastmarch | Descending five-beat cells / speech-shaped narrative declamation | Free lament and tvísöngur deferred |
| Haafingar / Cyrodiil | Triple galliard / expressive monody over moving harmony | Court airs, frottola and villanella deferred |
| Pale / Whiterun / Winterhold | Broad rowing-pulse lines / modal verses with short refrain / circular vocables | Composite coastal airs and polska deferred |
| Hjaalmarch / Winterhold | Instrumental interlocking figures and seconds / circular vocal melody | Sung sutartinės deferred; replace the base if its instrumental test fails |
| Reach sean-nós / Eastmarch / Pale / Solstheim | Ornamented free air / declamation / measured rowing / Persian modal melisma | Choose the preferred Reach base using listening evidence |


## Fragment-Writing Rules

- Describe features (mode, meter, ornament, delivery), not just a tradition name.
- Name only sound sources represented by the visible animation family. A lute-family line may request any plucked string instrument, such as oud, vihuela, cittern, sarod, biwa, sitar or a plucked zither; these are alternatives for that player, never additional instruments. A flute-family line may request any reedless woodwind. Name the selected instrument directly, exclude bowed-string and reed-driven substitutes respectively, and apply the same source-count discipline to drum families. Timbral plausibility must be auditioned.
- In solo prompts, omit any implication of another performer. Describe voice/instrument exchange by the one musician explicitly. In ensemble prompts, every additional voice, instrument or clap must match a visible role and a source count.
- Name the musical source even when adapting an ensemble tradition. Label the reduction and retain the concrete compositional description; the source name never authorizes absent voices or instruments.
- Keep each fragment to one concise clause list. The workshop's implemented contract is at most 1,000 characters for the complete default music prompt, excluding lyrics; shorten repetitive source prohibitions and editorial rationale before removing the defining musical features. Flag longer custom directions without truncating them. A 400-character musical-layer budget is an editorial guide, not a replacement for checking the complete assembled prompt.

## Config

These are target controller settings, not the current workshop or game-pilot configuration. The earlier optional-name proposal is superseded: current workshop recipes always name their real-world style reference.

| Setting | Default | Effect |
|---|---|---|
| `regional_variation_enabled` | false | Master toggle. Off means output identical to current behavior |
| `hold_tint_enabled` | true | Lets non-Nords pick up hold tints |
| `college_repertoire_enabled` | true | Allows established learned repertoire; never forces Haafingar or court music |
| `audition_tradition` | unset | Explicit candidate selection during comparisons; never an automatic six-way mixture |

## Acceptance Criteria

The current workshop must admit exactly eleven bases plus Reach sean-nós, reject deferred profiles and unsupported arrangements before provider access, exclude lyrics from Winterhold and Hjaalmarch, preserve historical records, and label every base as awaiting listening tests. Normal side-by-side generations retain the canonical arrangements; blind studies may additionally use the supported shared instrumental families described above. Blind recognition follows the open-ended Clip/Full Play-and-judge loop, enables choices after playback ends, consumes eligible cached audio first and permits only one disclosed paid fallback per explicit Play. It hides answer cues until guessing, balances fresh exposure, records the exact choice set, includes unsure answers in accuracy, and separates practice and frozen recipe cohorts. Replay eligibility respects the configured hours and selected policy. Seeding and replenishment retain explicit bounded paid authorization and no automatic retries. The broader eventual integration criteria below remain deferred.

- An explicitly selected Nord regional performance can produce distinct Solitude, Windhelm and Falkreath prompts without erasing a biography-selected tradition.
- A Nord and Redguard with different selected traditions in the same inn produce audibly distinct intended structures, not merely different labels.
- Orsimer and Bosmer each have an explicit selected audition candidate while their production core is unset. Bosmer receives a musical layer with a lute; no race-wide material ban removes it.
- The initial Orsimer, Khajiit and Argonian cultural release uses instrumental recordings only. Deferred vocal experiments do not enter the production pool merely because they generated successfully; the current Nord pilot's legacy behavior is a separate boundary.
- Khajiit includes an unaccompanied tabla-pair solo with a distinct rhythmic brief. Argonian uses its revised pitched-cell instrumental identity and does not receive a generic drum solo that erases it.
- The near-neighbor pairs in the boundary table are distinguishable in blind listening, including when their predominant moods match.
- Across region, tradition, instrument, singing and roster combinations, every audible source has a matching visible role. One flutist never supplies simultaneous independent sung and blown parts.
- Specialist overtone singing requires an assigned technique; ancestry, low voice or a College flag is insufficient. Lurbuk's existing limitations remain meaningful.
- Drum-only and reduced flute arrangements contain no impossible pitched/chordal instructions. Instrumental fallback identifies its actual selected repertoire.
- Unknown culture with unknown region preserves the existing behavior; the master switch off remains byte-identical to the current implementation.
- Every workshop music prompt names the reference, actual performer race, target region and chosen sound sources, including when custom musical directions are used. Complete defaults stay within 1,000 characters excluding lyrics; copied music contains the whole assembled direction, and optional lyrics are copied separately and preserved verbatim.
- Authored motifs, meters and overtone effects remain proposed until heard in generated output. The documented Nord pilot playback does not validate these cultural recipes, deferred vocal techniques or later-phase animations.

## Open Questions

The immediate engineering priorities are deterministic controller handoff, the repeatable preparation/playback loop, durable jobs and deployment, and explicit performer/recipe identity in the [development roadmap](development-roadmap.md). Listening can answer the questions below as time permits. Additional workshop cultures, arrangements, modes and minority moods remain deferred until intentionally admitted, without requiring all eleven bases to pass first.

1. **Orsimer winner and deferred vocals.** Which instrumental finalist is most distinctive and portable for the initial release? Keep the production core unset until comparison. Later, can Resonant Name-Songs produce a credible Orc voice with true one-singer overtones, rather than ordinary low singing?
2. **Bosmer winner.** Does Leaping tales retain its quick 3+2 spring, articulation and gaps reliably? Do Hunting-call airs and Spinner's tales deserve immediate additional repertoire or later expansion?
3. **Performer connection.** Extend beyond the pilot's bard/location marker and the offline authored registry to a live contract with stable identity, known repertoire, capabilities and actual arrangement before automatic cultural selection. Enforce instrumental-only eligibility before any vocal probability or cached-track choice.
4. **Animation and synchronization.** Validate voice-only, flute/drum choices, clapping control and ensemble handoffs. Stomping has no confirmed asset/control path yet.
5. **Moon phase.** The phase-mode map remains a starting guess using Masser. Decide whether Secunda should matter and confirm phase data is available.
6. **Pitch and meter fidelity.** Test overtone melody, 7-pulse/5-pulse patterns, modal tuning and clean silences. Do not assume model fidelity from prompt wording.
7. **Regional development.** Develop Skaal and further Cyrodiil local forms after the first distinct palette. Keep Raven Rock and the Gray Quarter connected through the Dunmeri core.
8. **Rare conditions.** Add cheerful Dunmer and other minority moods after the core palette succeeds. Predominant moods do not need equal balancing now.
9. **Beastfolk voices.** Revisit singing only when a generated Khajiit or Argonian voice is convincing for the intended performer. Keep sitar/bansuri/tabla and kacapi/suling development useful independently of that gate; another prompt wording alone is not evidence that it has been passed.
10. **Baseline fidelity and Reach choice.** Can Lyria preserve and switch among all eleven selected styles across fresh takes and English texts? Does the sole sean-nós challenger remain distinct from Eastmarch, Pale and Solstheim, and prove enjoyable enough to replace puirt-à-beul? Rímur-only Eastmarch and iorram-inspired Pale are already provisional targets; their repeatability and separation still need listening evidence.
