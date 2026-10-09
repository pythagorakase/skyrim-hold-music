# Regional Bard Music Variation

**Status:** Draft, palette development and phased implementation
**Scope:** Musical traditions, performer context and prompt construction for generated bard performances

**Audition workspace:** [Hold Music listening dashboard](../dashboard/index.html) · [Full idea bank and independent reviews](bard-musical-traditions-exploration.md). Open the HTML file in a browser to compare profiles, edit prompts, attach local audio and keep listening notes. It is a portable snapshot of this spec; browser experiments do not change these source documents. Export notes to move them between computers. Audio attachments last only for the current page session.

## Summary

Bard music should vary by learned tradition, performer and place. Build a diverse, coherent and audibly distinct palette first. Each tradition may have a strong predominant mood; exceptions such as cheerful Dunmer songs can remain minority conditions developed later. Race supplies a fallback cultural association, while established biography and musical training can select a different repertoire.

The regional scope includes Skyrim, Cyrodiil and Solstheim. Raven Rock and the Gray Quarter can share a Dunmeri foundation; Skaal traditions remain a separate cultural possibility. Cyrodiil needs its own local vernacular as well as court music.

## Implementation baseline

- Solo Lute 0.1.0 changes the music-generation request. The NPC identity, biography, race and location connection assumed by the original draft is still to be built.
- Performer and regional fragments below describe the proposed assembly contract. They are not evidence that these fields reach the current adapter.
- The current SkyrimNet performance path uses the lute animation. First implementation therefore remains one lute performer, with or without voice; flute, drum, voice-only and ensemble control need separate integration work.
- A visible lute can represent a family of plucked-string sounds. Other instruments likewise use plausible animation families rather than a single literal timbre, subject to listening and visual tests.
- Audience clapping has been observed during the Olaf festival and the corresponding applause assets were located. Repeatable start, timing and stop control still need a prototype; stomping remains unverified.
- The [bard roster and biography audit](bard-roster-and-biography-audit.md) supplies the installed-profile baseline and candidate musicians. Static record eligibility is distinct from current save state.

## Proposed architecture: Hold Music owns performances

**Status: proposed direction, not implemented or enabled.** A complete performance controller is a plausible successor to the current request adapter. Hold Music would own repertoire selection, scheduling, its song library, conditional lyric composition, music generation and performance lifecycle. SkyrimNet would remain the source of character context and, where the supported integration permits, on-demand text generation. Its ordinary dialogue, biographies and memories remain useful independently of its bard manager.

- Choose the performer, repertoire and actual arrangement, then check for an eligible cached recording before requesting new content. An instrumental or wordless-vocal piece needs no lyric-writing call. A repeat performance can reuse its recording; a new arrangement can reuse a suitable existing lyric. Generate new words for a requested/upcoming lyrical performance that needs a new composition or topic.
- Build the lyric brief from knowledge available to that bard. The shipped lyric template uses identity, location, voice, memories, witnessed events, recent dialogue and previous song titles. A generic call to the template does not populate these values automatically.
- Keep compositions and recordings distinct: title/lyrics/context provenance belong to a composition; performer, repertoire, instrument, vocal mode, arrangement and recipe/model version belong to its recording. Hold Music should own its metadata rather than extending SkyrimNet's live song table ad hoc.
- Generate asynchronously ahead of playback where possible. A waiting or failed provider request must not leave an actor trapped in a performance pose. Prefer an eligible existing recording when one is available.
- Coordinate audio, animation objects, start/stop, dialogue/combat interruptions, cell changes and cleanup. Preserve authored vanilla/mod quest scenes through explicit ownership rules. Existing animation assets may be reusable without starting complete scenes that also control their own audio.

Static feasibility evidence: the installed beta26 DLL exports general memory/event/dialogue query and custom-prompt functions. The Papyrus custom-prompt callback documents a 750-character response cap; the native route is a candidate for full lyrics, with response-length and worker-thread handoff behavior still to verify. Exact equivalence to the built-in bard manager's witnessed-event and conversation selection is also unresolved.

The bard enable switch is not an established lyrics-only mode: installed disabled-feature messages cover song-topic requests and compose/play-song commands. Prove the independent context/lyric route and one cached replacement performance with correct cleanup, then validate turning off SkyrimNet's bard feature. Its effects on existing playback, vanilla suppression and reload requirements remain unverified. No runtime configuration has been changed for this proposal.

## Repertoire logic: first offline implementation

The first decision engine is implemented in `hold_music/repertoire.py`, with synthetic quest-success and scandal examples. It plans from an explicit snapshot of a bard's knowledge, known compositions and compatible recordings. The live SkyrimNet knowledge bridge, persistent library, generation executor and playback controller are still pending. See [repertoire logic and runnable examples](repertoire-logic.md) for the contract and tuning defaults.

- A successful quest, a scandalous affair circulating as gossip, and ordinary local news are all valid subjects. No heroic framing is required. Select from what the bard knows; hearing gossip does not mean learning a pre-existing song about it.
- Keep direct knowledge and hearsay distinct. Wit, teasing and exaggerated imagery are appropriate artistic choices; repetition does not turn an allegation into a confirmed event. Preserve occurrence and knowledge-acquisition times instead of treating retrieval time as freshness.
- Choose between a familiar recording, another recording of a known composition, or new lyrics for a suitable fresh subject. Instrumental and wordless choices skip lyric generation. Topic/song cooldowns, pending-job deduplication and generation-start limits keep every performance from creating more content.
- The default planner policy is `cache_first`. The example snapshots use `topical_when_salient`, which can prepare a new song about recent news while retaining a familiar playable fallback. These are offline decisions, not paid generation requests or changes to SkyrimNet's settings.
- Save/continuity scope, explicitly learned repertoire and exact recording identity prevent another bard's private knowledge or incompatible recording from becoming an automatic performance. The future live bridge must preserve those boundaries.

## Goals

- Two bards of different cultures in the same inn sound different.
- Nord bards in different holds sound different.
- No fragment implies an instrument or performer that is not visible.

## Non-goals

- Changing which instrument a bard plays, until Phase 2.
- Full lyric generation, live knowledge ingestion and performance ownership in this offline planning milestone.

## Design principles

1. **Performer first.** The visible animation fixes an instrument family and the roster fixes the number of performers. Variation can use related timbres, mode, meter, articulation, ornament and vocal technique without introducing an unseen player.
2. **Learned tradition sets the idiom.** Race is a fallback when individual training is unknown. Region provides a compatible local influence. Established character identities, such as Ogmund’s Nordic skald tradition, remain meaningful away from their place of origin.
3. **Features over labels.** Tradition names alone tend to collapse into generic fantasy tavern music. Every fragment carries concrete musical features; the tradition name is an optional prefix.
4. **Distinct palette before nuance.** Give each core a recognizable rhythmic, melodic and textural identity with a predominant mood. Do not flatten the palette by giving every culture an equal share of every mood.
5. **Draft selection is not audio validation.** Orsimer and Bosmer finalists will become provisional defaults and alternatives for listening tests; generation fidelity and animation feasibility remain separate checks.

## Phasing

| Phase | Adds | Depends on |
|---|---|---|
| 1 | Regional idioms on solo lute, with or without voice | Performer context connection and a selected palette |
| 2 | Flute and drum | Overriding SkyrimNet's lute-only animation |
| 3 | Visible accompanists recruited from the audience | Phase 1 for voice roles, Phase 2 for instrumental roles |
| 4 | Ambient music at caravan camps and the Windhelm docks | Phase 1; richer with Phases 2 and 3 |

### Phase 1: lute only

SkyrimNet forces the lute animation, so every performance is solo lute or lute with voice.

- Planned Phase 1 fields: `core`, arrangement reductions, `dialect`, compatible `tint`, `voice`, `lute`, `phase_modes` and explicit audition selection.
- Later-phase fields: flute/drum arrangements and additional performer roles; reductions already matter for Phase 1 lute-only comparisons.
- Orsimer and Bosmer now have auditionable musical profiles. Their selected production cores remain unset until listening comparisons; an audition explicitly names its candidate.
- Khajiit and Argonian profiles become usable when an existing or nominated NPC is explicitly registered as capable of the requested role; ancestry alone does not assign new skills.
- Done when the acceptance criteria pass with `instrument` fixed to lute.

### Phase 2: instruments

- Enable the flute and drum arrangement lines after their animation/controller paths are validated.
- Instrument material preferences can be assigned to particular Bosmer characters. There is no blanket racial lute ban; the visible prop and established biography remain authoritative.
- Decide who picks the instrument: fixed per NPC or selected per performance from the chosen repertoire and the performer’s capabilities.
- Done when the acceptance criteria pass across all three instruments.

### Phase 3: accompanists

Audience members are recruited into visible accompanying roles.

- Principle 1 widens from "solo only" to "every sound has a visible source". The performer block lists exactly who is playing and what.
- New input `accompanists`: a list of visible performers, each with a role (voice, drum, flute, clapping).
- The selected learned tradition chooses the idiom. Accompanists supply only the roles present in the arrangement; they do not automatically receive professional bard skills.
- Plural-performer language becomes legal, but only when it matches the accompanist list exactly.
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

### Phase 4: ambient scenes outside the walls

Occasional music from nominated community performers at the Khajiit caravan camps and Windhelm docks/Assemblage. These are the first target scenes, not an absolute claim that every Khajiit or Argonian must remain outside cities. A New Gnisis Cornerclub resident is another proposed community musician; existing quest-dependent performances there need coordination.

| Scene | Profile | When | Notes |
|---|---|---|---|
| Caravan camp | `khajiit` | Night, while the caravan is camped | Mode follows `moon_phase` |
| Windhelm docks | `argonian` | Day, during work | Work rhythm |
| Argonian Assemblage | `argonian` | Occasional evenings | Community response or a small social performance |

- These community scenes default to their own repertoire. A location tint applies only when chosen for that audience and compatible with the core.
- Needs a trigger (location, time of day, a free NPC to perform) and a frequency cap so it stays occasional.
- A visible performer is still required. In Phase 1 that means a lute.
- NPC nominations, scenes and triggers remain proposed; the inventory records the candidates.

## Inputs

These are proposed context fields; they are not yet connected to the Solo Lute adapter.

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

## Resolution rules

1. **Select a learned repertoire.** An explicit audition or known performer tradition takes priority. Otherwise use a mapped cultural fallback. For cultures with `selected_core: null`, require an explicit audition candidate; do not silently ship the shortlist as random variants or fall back to a missing culture layer. Production selection remains pending.
2. **Resolve the occasion and region.** Use current region/community and available repertoire. Breton court/folk and Imperial court/vernacular are distinct choices. College training makes learned forms available; it does not replace the location or erase personal tradition. The new Cyrodiil vernacular is independently selectable.
3. **Apply regional dialects deliberately.** A Nord regional performance may use the matching dialect as its core. A biography-selected or named tradition retains its core away from home. Thus Ogmund does not automatically become a Reachfolk musician, and a Bosmer trained in Nordic ballads retains that option.
4. **Apply only compatible tints.** Tints may adjust density, ornament or local phrasing. Drop a tint that erases the chosen meter, articulation, predominant mood or defining technique. No Hjaalmarch neighboring-tone requirement is added to a stable Orsimer overtone fundamental.
5. **Khajiit.** Keep the existing hold-tint exemption and append the selected moon condition when available. A condition changes the course within the family; it does not replace the musical identity.
6. **Check the actual arrangement.** Append only the chosen instrument-family line and, if singing, an eligible voice line. A flute player alternates vocal/instrumental phrases. Specialist technique and ensemble descriptions require affirmative capability and the matching visible roster. An ordinary novice does not acquire overtone mastery from race.
7. **Use the right reduction.** For drum-only performances without singing omit pitched material and use the rhythmic line. A drum-and-voice arrangement can retain the pitched vocal structure. Where a lone flute, voice, or drum-and-voice arrangement cannot support a drone, chord blocks or simultaneous counterpoint, replace the ordinary core with `core_monophonic`; adding an instrument line does not cancel an incompatible core. For other instrumental performances use the explicitly described instrumental arrangement. Instrument-only clauses describe melodic phrases, not an absent singer; remove any voice-dependent answer/accompaniment wording. During comparisons, audition the candidate's honest reduction; do not conceal weakness by switching styles. In eventual production, an unavailable reduction may select an explicitly designated instrumental repertoire, with the actual repertoire recorded in the cache identity.
8. **Fallback and caching.** Unknown culture and unknown region preserve existing behavior. Record performer/repertoire, actual instrument family, vocal or instrumental mode, technique, roster and relevant location/moon conditions in future cache identity so a track cannot imply a different arrangement. This connection is planned. Preserve Solo Lute's existing 50/50 composition policy unless separately changed.

## Prompt assembly

Order:

1. Named `reference` with a brief solo, single-line, three-voice or rhythmic adaptation label
2. Tamriel/Elder Scrolls setting, explicit target region, adult performer race and actual arrangement
3. One intimate acoustic-room instruction and compact vocal casting when singing
4. Arrangement-compatible `core` or `dialect`, voice technique and selected instrument treatment
5. One instruction tying generated lyrics to the performer and setting; supplied lyrics instead remain a separate, verbatim block

The workshop adds performer and region context to every complete request, including saved custom musical directions. Race defaults to the profile's provisional audition cast and can be overridden separately for A and B. Target region defaults to the named hold for regional profiles, Cyrodiil for its vernacular profile, and otherwise Skyrim with no specific settlement assigned. A shared region override lets both auditions use the same place.

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

The Orc finalists' `audition_casting` fields and the Khajiit voice direction specify provisional vocal characters for listening tests. They are casting choices, not definitions of a tradition or rules for every member of a race. They do not select a gender or confer technique proficiency. A race override selects the matching vocal character instead of carrying the repertoire's Orc cast into another performer. In eventual NPC integration, the actual performer's `voice_character` replaces these audition defaults. Instrumental prompts still name race and place but omit vocal casting and technique; a three-singer arrangement retains its exact roles.

Performer and region controls, a context summary and the exact-request preview expose the complete audition context. Existing custom musical directions are preserved; **Reset to recipe** explicitly adopts revised musical defaults. Context instructs newly generated lyrics to keep the performer identity and venue consistent without announcing the race or inventing a birthplace. With no named settlement selected, lyrics avoid naming the current venue. Supplied SkyrimNet lyrics remain unchanged: their characters and locations are song subjects, not authority to recast or relocate the audition. Saved takes retain the exact prompt originally sent to Google.

Google's [Lyria prompt guide](https://ai.google.dev/gemini-api/docs/lyria-prompt-guide#vocal-delivery-and-singer-profiles) recommends explicit vocal range and timbre. Setting names provide context; the casting and technique clauses describe the sound to audition. Their effectiveness still requires listening.

Example, Nord with lute and voice in Windhelm, tradition names on:

```
[setting] [performer block] [voice character] In the style of Icelandic rímur: austere chanted
heroic verse, narrow melodic range, close to unaccompanied. Voice: declaimed more
than crooned, syllabic, storyteller's chest voice. Lute: bare fifths and single
notes shadowing the voice. [acoustic production constraint]
```

Example, Redguard with lute, not singing, in Dawnstar, tradition names on:

```
[performer block] In the style of Arab-Andalusian and Spanish Renaissance song:
Phrygian color, clearly articulated melodic phrases in a recurring rhythmic cycle,
ornamental runs returning to firm cadence notes, leaving more space between phrases.
Lute: an oud-like single melodic line, distinct plucked attacks and brief runs.
[acoustic production constraint]
```

## Culture profiles

These are selective compositional references, not complete descriptions of the real traditions or claims of canonical Tamrielic music. Predominant moods are intentional. `orc` remains the internal key for Orsimer.

| ID             | Reference tradition                                    | Why                                                                 |
| -------------- | ------------------------------------------------------ | ------------------------------------------------------------------- |
| `nord`         | Scandinavian medieval ballad                           | Strophic, modal, drone-heavy storytelling                           |
| `imperial`     | Italian frottola, early Baroque monody (Caccini)       | Expressive solo melody with strong harmonic arrivals |
| `imperial_vernacular` | Italian frottola and Renaissance villanella, adapted as an original vernacular | Firm pulse, short refrain and clear cadences for Cyrodiil |
| `breton_court` | French air de cour                                     | High Rock's feudal courts                                           |
| `breton_folk`  | Breton gwerz                                           | Narrative lament for the folk register                              |
| `redguard`     | Arab-Andalusian song, Spanish vihuela (Milán, Narváez) | The lute played like the oud it descends from                       |
| `dunmer`       | Armenian and Persian modal lament                      | Exile music for the Gray Quarter                                    |
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
    lute_instrumental: "upper-string melody with ornamental runs over arpeggiated bass, clear cadences"
    reference: "Italian frottola and early Baroque monody"
    core: "clear major or minor tonality, flexible expressive tempo, strong cadences"
    voice: "lyrical solo line with ornamental runs and cadential trills"
    lute: "arpeggiated chordal accompaniment under the melody, continuo style"
    flute: "singing, vocal-style melody with cadential trills"
    drum: "light, even dance pulse"

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
    lute_instrumental: "long sorrowful melody with slow ornaments over the same instrument’s low drone strings"
    core_monophonic: "slow free-rhythm lament, long sorrowful single-line phrases and augmented-second color"
    reference: "Armenian and Persian modal lament"
    core: "slow lament, minor mode with augmented-second color, free rhythm, long sorrowful phrases over a sustained low drone"
    voice: "mournful, restrained, long-breathed, slow melisma"
    lute: "sparse plucked notes over a low drone string"
    flute: "low, breathy tone with slow pitch bends"
    drum: "slow, sparse pulse"

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

## Orsimer and Bosmer finalists

The exploration produced **18 Orsimer candidates and 22 Bosmer candidates**, with an independent palette review adding eight alternatives and challenges. The [complete idea bank](bard-musical-traditions-exploration.md) retains the options and rejection reasons. The names below are working names for invented traditions. They are audition finalists, not six equally frequent production modes.

| Culture | Finalist | Audible identity | Predominant mood | Role in the shortlist |
|---|---|---|---|---|
| Orsimer | **Resonant Name-Songs · throat singing** | One sustained vocal fundamental with a moving upper overtone melody, long vowels, sparse plucked punctuation | Grave, concentrated, enduring | Favorite vocal identity; individual technique required; instrumental reduction is weaker |
| Orsimer | **Seven-Step Oath-Songs** | Deliberate 2+2+3 grouping, compact four-note material, clipped words, damped instrumental answers and decisive rests | Resolute, exacting, communal | Most portable candidate across the existing lute/voice and instrumental grammar |
| Orsimer | **Close-Circle Songs** | Plain lead phrases with compact chord blocks that change and stop together | Solemn solidarity, intimate warmth | Ensemble finalist; current solo version explicitly gives chord work to the lute |
| Bosmer | **Leaping tales** | Quick five-pulse 3+2 grouping, wide angular leaps, dry attacks, shortened answers and sudden gaps | Mischievous, alert, slightly uncanny | Preferred broadly usable Bosmer candidate |
| Bosmer | **Hunting-call airs** | Brief sharply defined calls, separated registers, complete pauses and clean endings | Watchful, restrained, faintly predatory | Strong flute and quiet-instrumental candidate |
| Bosmer | **Spinner's tales** | Conversational singing, a recurring three-note tag, elastic phrase lengths and character changes by one voice | Intimate, absorbing, uncanny | Narrative finalist; weaker as a drum-only or purely instrumental identity |

**The family distinction:** Orsimer holds a sound or brings attacks and endings together; Bosmer moves, breaks off and changes register. Orsimer ensemble chord blocks differ from Altmer independently moving counterpoint. Bosmer complete phrase exchanges differ from Argonian continuous interlocking cells.

The initial Bosmer proposal shared the Orsimer candidate's seven-pulse grouping. The selected Bosmer audition brief uses **five pulses grouped 3+2** instead. Its fast, angular, broken delivery also separates it from Falkreath's slow descending five-beat lament. Meter is a listening target, not a verified model capability.

### Candidate fragments

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

For `orc_close_circle`, append `ensemble_clause` only when the three specified singers are visibly participating. The solo lute supplies the chordal reduction; a lone flute or drum uses only its declared reduced line and omits the chordal `core`. For `orc_resonant_names`, require `solo_overtones` only for the sung technique, and label the instrumental version as a reduction. For `bosmer_spinners_tales`, an instrumental render uses the tag/phrase structure without pretending that characters are speaking. The same physical roster constraints apply to every profile.

### What to audition first

The first live Resonant Name-Songs take (2026-10-08) received listener feedback that its voice was too light and delicate to fit the intended Orc performer. Its submitted prompt omitted Skyrim, Orc identity and explicit vocal weight, and the technique clause omitted the earlier draft's low fundamental. The revised recipe adds setting, separate audition casting and a stronger low-fundamental instruction. This is a prompt correction awaiting another listening comparison, not a claim that the model will now obey it. Retain the original take as the comparison baseline.

1. Compare Resonant Name-Songs and Seven-Step with the same one-singer/one-lute arrangement and recording perspective. Then compare each one's honest lute-only version. Their portability matters under the existing roughly 50/50 instrumental composition policy.
2. Compare Leaping tales, Hunting-call airs and Spinner's tales on the same performer. Leaping tales is the first default candidate; the other two must earn space by audible distinction.
3. Compare Close-Circle's solo lute reduction now; its three-singer form waits for a matching visible ensemble. The three-person adaptation is not labeled authentic Sardinian tenore, which is a four-part tradition.
4. Listen without labels. Score the actual meter, phrase shape, articulation, timbre, source count and identity against the nearest existing neighbor. Overall production polish does not substitute for distinctness.
5. Preserve failed renders as failed auditions: an ordinary low chant is not successful overtone singing; a choir is not one singer; flattened meter has not met the rhythmic target. A simpler core can still win if it remains distinctive.

Real technique references: [UNESCO on solo khoomei](https://ich.unesco.org/en/RL/mongolian-art-of-singing-khoomei-00210?RL=00210), [UNESCO on four-part Sardinian tenore](https://ich.unesco.org/en/RL/canto-a-tenore-sardinian-pastoral-songs-00165), and [Tbilisi State Conservatory's account of polyphonic principles](https://polyphony.ge/en/georgia/georgian-traditional-music/forms/). They support the acoustic distinctions, not the invented Orsimer names or social meanings.

The explicit-name audition revision adds provisional anchors to the original fictional forms: Bulgarian rachenitsa for Seven-Step, Balkan aksak dance music for Leaping tales, Swedish kulning for Hunting-call airs, and Japanese biwa narrative song for Spinner's tales. These choices borrow selected features and preserve the existing recipes; they are not retrospective claims that the forms were modeled completely on those traditions. [University of Arizona's meter guide](https://opentextbooks.library.arizona.edu/folkdance/chapter/chapter-28/) documents the 2+2+3 rachenitsa grouping; Leaping tales retains its separately specified 3+2. [Sweden's Institute for Language and Folklore](https://www.isof.se/folkminnen/amnesomraden/folklig-sang-musik-och-dans/lar-dig-mer-om-folklig-sang-och-musik/fabodarnas-toner) describes kulning and short herding melodies. [Smithsonian's biwa program notes](https://asia-archive.si.edu/podcast/voice-of-the-biwa-junko-tahara-ensemble/) describe narrative song with plucked-lute accompaniment. The Pale's original coastal air uses a provisional Scottish/Hebridean slow-air anchor; the [Scottish Music Centre's Highland-air collection](https://www.scottishmusiccentre.com/shop-all/p/musica-scotica-vol-vii-original-highland-airs-collected-at-raasay-in-1812-by-elizabeth-jane-ross) provides a named song-air and instrumental repertoire for comparison.

### Bosmer materials and learning

Keep personal instrument material/observance choices separate from musical idiom. The installed bios give Yarbrough and Daenlyn lute skills and Nordic training; the new Bosmer candidates do not automatically replace their learned repertoire. Imported materials and differing interpretations of the Pact also have textual support: [official Y'ffre Q&A, preserved transcript](https://elderscrolls.fandom.com/wiki/Loremaster%27s_Archive%3A_Y%27ffre%27s_Beckoning) and [The Green Pact and the Dominion, game-book transcript](https://teso.mmorpg-life.com/the-green-pact-and-the-dominion-lorebook/). These are not a blanket ruling on every character's instrument. Bone, hide or imported materials are optional individual details when the prop and characterization support them.

## Hold profiles

`dialect` supplies the selected regional Nord repertoire. `tint` is a compatible local influence on another selected tradition, never an unconditional overwrite. These are compositional adaptations of the references, not claims that an entire real tradition has these exact properties.

| ID | Capital | Reference tradition | Why |
|---|---|---|---|
| `haafingar` | Solitude | Danish court of Christian IV, where Dowland was lutenist | A northern court importing southern polish |
| `eastmarch` | Windhelm | Icelandic rímur and tvísöngur | Oldest city, most traditionalist |
| `whiterun` | Whiterun | Swedish and Danish ballads, polska | The baseline |
| `reach` | Markarth | Gaelic sean-nós, puirt à beul, pibroch | Reachman influence |
| `falkreath` | Falkreath | Karelian lament and runo-song | A graveyard town's music |
| `rift` | Riften | Playford dance tunes, broadside ballads | Tavern town |
| `winterhold` | Winterhold | Sámi joik | Far north, sparse |
| `pale` | Dawnstar | Original northern coastal air, auditioned with Scottish and Hebridean slow-air influences | Long exposed calls over a slow rocking pulse, distinct from Winterhold’s circular vocables |
| `hjaalmarch` | Morthal | Lithuanian sutartinės | Haunted marsh, hold run by a seer. Mirrors Windhelm: the grating second against the hollow fifth |

```yaml
holds:
  haafingar:
    lute_instrumental: "refined upper melody over spacious chord answers, a clear triple dance pulse"
    core_monophonic: "polished triple dance motion, refined single-line phrases and clear cadence returns"
    reference: "the Danish court of Christian IV and Dowland's lute airs"
    dialect: "polished courtly style, recognizable triple dance pulse, refined airs and spacious instrumental answers"
    tint: "polished, courtly phrasing"

  eastmarch:
    drum: "isolated low strokes at the ends of declaimed phrases; leave speech-paced gaps"
    core_instrumental: "austere heroic melody, narrow range, irregular declamatory phrase lengths and complete pauses"
    lute_instrumental: "austere narrow melody punctuated by bare fifths and clean pauses"
    reference: "Icelandic rímur and tvísöngur"
    reference_focus: "austere narrative declamation and open-fifth color; a single melodic line replaces the second singer in a solo reduction"
    dialect: "austere speech-shaped heroic phrases, narrow melodic range and exposed single melody"
    tint: "sparser and more austere"
    lute: "bare fifths between phrases and single notes following the lead melody"

  whiterun:
    drum: "broad three-pulse groups with a weighted first beat and a lighter turning third"
    lute_instrumental: "plain modal refrain above open tonic and fifth strings, a broad triple dance lilt"
    core_monophonic: "strophic Dorian or Mixolydian melody, short refrain, plain ornaments and broad triple sway"
    reference: "Swedish and Danish ballads and polska dance tunes"
    dialect: "strophic ballad with a short refrain, Dorian or Mixolydian mode, steady drone on the tonic and fifth, triple-meter dance lilt in livelier pieces"
    tint: null

  reach:
    lute_instrumental: "one unfolding air with connected picked graces and increasingly ornamented variations"
    reference: "Gaelic sean-nós song and pibroch"
    dialect: "free-rhythm air with connected grace-note ornament and a slowly unfolding melody"
    dance_dialect: "quick flowing mouth-music dance, connected ornamental runs and a recurring lively pulse"
    tint: "extra grace-note ornament"
    flute: "a plain theme followed by increasingly ornamented variations"

  falkreath:
    drum: "slow five-beat groups, a falling sequence of softer attacks and a gap after each cell"
    lute_instrumental: "short descending five-beat melody cells, sparse open strings and restrained repeats"
    reference: "Karelian laments and runo-song"
    dialect: "slow lament, narrow range within a fifth, perceptible five-beat repetition and short descending cells"
    tint: "slower and more mournful"

  rift:
    drum: "bouncing six-pulse jig groups, alternating deep first and crisp fourth strokes"
    lute_instrumental: "catchy Mixolydian jig melody between bright chord strokes, bouncing compound pulse"
    reference: "Playford English country dance tunes and broadside ballads"
    dialect: "fast and bawdy, bouncing jig rhythm, major or Mixolydian mode, catchy strophic tune"
    tint: "faster and rowdier"

  winterhold:
    drum: "sparse returning stroke figure with open pauses; avoid a closing flourish"
    lute_instrumental: "a sparse circular figure with returning small variations, open pauses and no grand cadence"
    reference: "Sámi joik"
    dialect: "sparse circular melody with recurring short figures and little sense of a beginning or final cadence"
    voice: "plain wordless vocables, recurring intimate phrases"
    tint: "sparser, with more silence between phrases"

  pale:
    drum: "widely spaced low strokes in a slow rocking compound pulse"
    lute_instrumental: "long complete melody calls above widely separated low plucks, slow rocking compound pulse"
    reference: "Scottish and Hebridean slow airs"
    reference_focus: "long complete phrases, a slow rocking compound pulse and open gaps rather than circular joik or an unmetered lament"
    dialect: "long exposed melodic calls, slow rocking compound pulse, broad register and silence between complete phrases"
    tint: "more space between complete phrases"
    lute: "widely separated low notes mark a slow rocking pulse"
    flute: "long clear calls with distinct endings and open gaps"

  hjaalmarch:
    lute_instrumental: "one melody shadowed a whole step away on the same instrument, lingering adjacent-tone friction"
    core_monophonic: "one hushed slowly reiterated melody with neighboring-note turns and lingering unstable endings"
    # A compatible tint may affect Lurbuk; neither this region nor his race grants new mastery.
    reference: "Lithuanian sutartinės"
    reference_focus: "repeated motifs, neighboring-tone friction and interlocking or canonic phrasing; a single-line reduction uses neighbor-note turns rather than hidden parts"
    dialect: "hushed slowly reiterated phrases, sustained neighboring-tone friction and lingering unstable endings"
    tint: "hushed, unresolved, with clashing seconds"
    lute: "melody shadowed a whole step away so the two lines grate"
    flute: "circles the same few notes, leaning on clashing neighbor tones"
```

## Workshop instrument adaptations

The shared selector chooses an arrangement family; each recipe names its actual instrument. Cittern supplies a bright plucked attack for selected dance/ballad reductions, oud for Redguard, sitar for Khajiit, biwa for Spinner’s tales, and kacapi plucked zither for the new Argonian audition. Other recipes retain lute. All strings are plucked; no bowed-string arrangement is offered. These are provisional timbral choices for fictional repertoire, not claims of historical authenticity or new game props. The [Met’s cittern](https://www.metmuseum.org/art/collection/search/504210) and [sitar](https://www.metmuseum.org/art/collection/search/500759) document those plucked families. [Smithsonian’s Sundanese collection](https://folkways.si.edu/java-sundanese-folk-music/world/music/album/smithsonian) provides the instrumental zither/flute reference for Argonian; the earlier gamelan sketch is retained as repeating-cell inspiration rather than requesting its ensemble.

Khajiit and Argonian recipes are instrumental only. Choosing either race for another recipe also excludes sung arrangements. This is a workshop audition policy motivated by the current model’s voice limitations, not a statement that those peoples cannot sing. Existing vocal takes and edited directions remain stored. Supplied lyrics stay selected but are omitted from instrumental requests.

Solo percussion is offered for Seven-Step, Leaping tales, Redguard cycles, Rift jigs and Khajiit tabla solos, where the rhythm has a specific signature. The Khajiit percussion variant names Hindustani tabla solo rather than requesting a reduction of a raga melody: one player uses the dayan/bayan pair, teental, bass slides, quick finger variations and a concluding tihai. No melodic accompanist or spoken drum syllables are requested. [Darbar’s tabla guide](https://darbar.org/tabla/) describes the paired drums and solo repertoire; its [teental recital](https://player.darbar.org/videos/dch339-tabla-solo-by-satyajit-talwalkar) documents the 16-beat cycle, and its [concert guide](https://player.darbar.org/packages/indian-music-appreciation-course/videos/concert-performance-sukhdeep-dhanjal-and-harmeet-virdee) explains the threefold tihai resolution. Solo voice is retained for vocal-led forms; chordal court/counterpoint and neighboring-tone recipes omit it. Close-Circle keeps plucked-string reductions and its explicit three-voice study. Flute reductions are single lines; voice with flute alternates. Unsupported choices show a reason before a request can be sent.

`lute` and `lute_voice` remain the stored arrangement keys so older notes and takes remain readable; their workshop labels now mean the plucked-string family.

```yaml
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
    plucked: "lute"
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
    note: "The flute versions are melodic reductions of the court air; plucked strings retain its harmonic answers."
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
    plucked: "lute"
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
    plucked: "lute"
    allowed: [lute_voice, lute, flute, flute_voice]
    note: "Plucked strings can retain simultaneous neighboring tones; flute uses an explicitly weaker sequential reduction."
```

## Regions beyond the nine holds

| Region or community | First palette decision | Distinctive role |
|---|---|---|
| Cyrodiil | `imperial_vernacular` for an appropriate local/learned popular repertoire; `imperial` remains the court/expressive solo option | Firm pulse, short refrain and clear harmonic arrivals; further Colovian/Nibenese subdivision can follow |
| Gray Quarter and Raven Rock | Shared `dunmer` core | Predominant mournful modal repertoire; local song choices and arrangement density may diverge later |
| Skaal community | Separate northern tradition slot; no default assigned yet | Do not apply Raven Rock's Dunmeri mapping to all Solstheim residents or duplicate every northern mode |
| Other added regions | Explicit available repertoire, then known character culture, otherwise unknown-region fallback | Preserve individual learning and avoid false location guesses |

Overtone singing is concentrated in the Orsimer specialist finalist for the first audition palette. A later named Skaal or other performer could learn it, but adding it to every northern region now would weaken the new distinction.

## Palette boundaries and alternatives

The objective is distinctness of sound, not equal emotional coverage. Dunmer remains predominantly mournful. These boundaries are now reflected in the fragments above; alternatives are held for later auditions rather than silently merged into the core.

| Neighbors | Boundary to preserve | Alternative held in reserve |
|---|---|---|
| Redguard / Khajiit | Articulated repeated cycles and firm returns / sustained slides and gradually unfolding development | A separately researched Redguard narrative-ostinato branch, including possible griot influences |
| Dunmer / Breton folk / Falkreath | Long melisma and modal tension / syllabic text-led stanzas / short descending five-beat cells | Rare convivial Dunmer condition later |
| Imperial / Breton court / Haafingar | Rhetorical solo melody and harmonic arrivals / restrained intimacy / clear triple dance motion | Distinct local vernaculars, not a universal College override |
| Argonian / Hjaalmarch | Crisp continuous recurring cells / slow sustained adjacent-tone friction | More varied communal Argonian responses after the core is audible |
| Winterhold / Pale | Sparse circular vocables / long complete calls over slow rocking time | A separately developed Skaal mode later |
| Orsimer / Bosmer | Held resonance or synchronized firm attacks / quick changing phrases, leaps and gaps | Further social occasions only after the main audition distinguishes them |
| Altmer / Orsimer ensemble | Independent moving/imitating lines / compact chord blocks that move and stop together | Additional ensemble forms require their own visible roster |

## Fragment-writing rules

- Describe features (mode, meter, ornament, delivery), not just a tradition name.
- Name only sound sources represented by the visible animation family. A lute-family line may request related plucked-string timbres such as oud, vihuela, cittern or sarod; these are alternatives for that player, never additional instruments. Apply the same discipline to flute and drum families. Timbral plausibility must be auditioned.
- In solo prompts, omit any implication of another performer. Describe voice/instrument exchange by the one musician explicitly. In ensemble prompts, every additional voice, instrument or clap must match a visible role and a source count.
- Name the musical source even when adapting an ensemble tradition. Label the reduction and retain the concrete compositional description; the source name never authorizes absent voices or instruments.
- Keep each fragment to one clause list. Proposed budget: at most 400 characters for the selected reference/core-or-dialect/tint layer, with separately bounded voice and instrument clauses. Enforce the limit after assembly without cutting off a defining feature; exact voice/instrument limits remain an implementation decision.

## Config

| Setting | Default | Effect |
|---|---|---|
| `regional_variation_enabled` | false | Master toggle. Off means output identical to current behavior |
| `include_tradition_names` | true | Adds the `In the style of {reference}:` prefix |
| `hold_tint_enabled` | true | Lets non-Nords pick up hold tints |
| `college_repertoire_enabled` | true | Allows established learned repertoire; never forces Haafingar or court music |
| `audition_tradition` | unset | Explicit candidate selection during comparisons; never an automatic six-way mixture |

## Acceptance criteria

- An explicitly selected Nord regional performance can produce distinct Solitude, Windhelm and Falkreath prompts without erasing a biography-selected tradition.
- A Nord and Redguard with different selected traditions in the same inn produce audibly distinct intended structures, not merely different labels.
- Orsimer and Bosmer each have an explicit selected audition candidate while their production core is unset. Bosmer receives a musical layer with a lute; no race-wide material ban removes it.
- The near-neighbor pairs in the boundary table are distinguishable in blind listening, including when their predominant moods match.
- Across region, tradition, instrument, singing and roster combinations, every audible source has a matching visible role. One flutist never supplies simultaneous independent sung and blown parts.
- Specialist overtone singing requires an assigned technique; ancestry, low voice or a College flag is insufficient. Lurbuk's existing limitations remain meaningful.
- Drum-only and reduced flute arrangements contain no impossible pitched/chordal instructions. Instrumental fallback identifies its actual selected repertoire.
- Unknown culture with unknown region preserves the existing behavior; the master switch off remains byte-identical to the current implementation.
- The assembled regional layer respects its character limit; voice/instrument clauses preserve the defining features and source constraints.
- Authored motifs, meters and overtone effects remain proposed until heard in generated output. This document does not claim in-game or audio validation.

## Open questions

1. **Orsimer winner.** Does Resonant Name-Songs produce true one-singer overtones and remain worthwhile beside its instrumental reduction, or should the portable Seven-Step candidate supply the initial core?
2. **Bosmer winner.** Does Leaping tales retain its quick 3+2 spring, articulation and gaps reliably? Do Hunting-call airs and Spinner's tales deserve immediate additional repertoire or later expansion?
3. **Performer connection.** Which actor/context data reaches the request and cache? Implement stable identity, known repertoire, capabilities and actual arrangement before automatic selection.
4. **Animation and synchronization.** Validate voice-only, flute/drum choices, clapping control and ensemble handoffs. Stomping has no confirmed asset/control path yet.
5. **Moon phase.** The phase-mode map remains a starting guess using Masser. Decide whether Secunda should matter and confirm phase data is available.
6. **Pitch and meter fidelity.** Test overtone melody, 7-pulse/5-pulse patterns, modal tuning and clean silences. Do not assume model fidelity from prompt wording.
7. **Regional development.** Develop Skaal and further Cyrodiil local forms after the first distinct palette. Keep Raven Rock and the Gray Quarter connected through the Dunmeri core.
8. **Rare conditions.** Add cheerful Dunmer and other minority moods after the core palette succeeds. Predominant moods do not need equal balancing now.
