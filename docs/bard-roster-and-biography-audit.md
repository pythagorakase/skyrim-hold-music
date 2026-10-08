# Bard roster and biography audit

**Audited:** 2026-10-08. **Sample environment:** MGO RC4.1, SkyrimNet beta26-rc4, SeverActions 4.2. **Purpose:** choose existing performers, identify biography gaps, and explore additional musicians for the regional music mod.

The installed SkyrimNet bard check accepts the **Bard class OR BardSingerFaction membership**. This gives a useful starting list, but it misses some actual musicians and includes some nonmusicians. The biographies already contain substantial musical variety; the largest gaps are unrecognized mod performers, missing biographies for town-expansion bards, and musical backgrounds for proposed community performers.

This is a read-only audit of the active profile and shipped/profile prompt files. It does not establish who is enabled, alive, hired, present, or assigned a faction in the current save. No NPC, faction, prompt, configuration, or existing spec was changed. Biography filenames preserve the provenance of these summaries. Complete biography files and installation-specific extraction artifacts are not distributed here; the summaries avoid quest plot details.

## What counts as a bard

| Record | Form in originating plugin | Meaning for this audit |
|---|---|---|
| `Bard` class | `Skyrim.esm:01325D` | Sufficient for the installed SkyrimNet helper. Class membership is broader than actual musical occupation. |
| `BardSingerFaction` | `Skyrim.esm:0CF8F9` | Also sufficient for that helper. |
| `JobBardFaction` | `Skyrim.esm:053514` | Occupational marker; insufficient on its own for that helper. |
| `BardSingerInstrumentalOnlyFaction` | `Skyrim.esm:0F6F87` | Separate instrumental marker; insufficient on its own for that helper. |
| `SolitudeBardsCollegeFaction` | `Skyrim.esm:0C13C7` | College membership; insufficient on its own. |
| `BardFaction3DNPC` | `3DNPC.esp:1F24C7` | Interesting NPCs has its own bard faction; insufficient on its own. |
| Other bard flags | No-autostart, no-request, house-bard and special encounter factions | Context and restrictions to preserve; none should automatically be treated as a new invitation to perform. Audience factions are not performer designations. |

“Static bard check” below means applying the recovered helper to the winning plugin records, including direct NPC-template inheritance. It is not a complete prediction of runtime behavior. Quests can change faction membership; Sven is an important case to test in game. Adding a faction would not by itself supply an appropriate schedule, repertoire, instrument role, or safe handoff from an existing performance scene.

**Bio labels:** B26 means the current beta26 base library supplies the file. Legacy means the active profile retains a biography identical to the older SkyrimNet `original_prompts` copy, although the beta26 base library lacks it. For the matched entries below, the profile copy matches the source and no per-character overlay was found. These are shipped SkyrimNet characterizations, not independently verified Elder Scrolls canon or proof of the current save history.

## Vanilla and Hearthfire performers

Twenty named NPCs have the ordinary bard markers below. Lynly is added because her biography establishes musical ability despite lacking those markers. Associations describe their normal venue or institutional role, not a live location check.

| NPC and biography | Association | Static bard check | Musical information in shipped bio / gap |
|---|---|---|---|
| Delacourt (`delacourt_667.prompt`) (B26) | Dead Man’s Drink, Falkreath | Yes | Lute and voice; Nordic ballads and upbeat entertainment. Profile emphasizes cheering a gloomy town. |
| Luaffyn (`luaffyn_CB2.prompt`) (B26) | Candlehearth Hall, Windhelm | Yes | Dunmer; trained in Nordic, Imperial and traditional Dunmeri styles. Voice, lute, flute and drum; adapts to her audience. |
| Talsgar the Wanderer (`talsgar_the_wanderer_generic.prompt`) (B26) | Traveling | Yes | Common-folk stories and traveling Nordic ballads; a repertoire that can move between regions. |
| Lurbuk (`lurbuk_A64.prompt`) (B26) | Moorside Inn, Morthal | Yes | Poor lute playing and discordant original songs, with enormous confidence. Preserve his limitations. Has the instrumental-only marker, but Bard class still passes this helper. |
| Mikael (`mikael_671.prompt`) (B26) | Bannered Mare, Whiterun | Yes | Nordic lute and vocal performance; bio describes travel in Cyrodiil and learning across Tamriel. |
| Karita (`karita_6C7.prompt`) (B26) | Windpeak Inn, Dawnstar | Yes | Lute and voice; Nordic songs and her mother’s musical legacy. The correct bio is `karita_6C7`, not the other Karita. |
| Sven (`sven_491.prompt`) (B26) | Sleeping Giant Inn, Riverwood | No | Lute-playing local bard. Winning base has Lumberjack class and JobBardFaction; runtime faction assignment needs checking. |
| Ogmund (`ogmund_8F4.prompt`) (B26) | Silver-Blood Inn, Markarth | Yes | Nordic warrior-poet and skald, emphasizing old heroic ballads. Markarth location should not automatically give him a Reachfolk repertoire. |
| Lisette (`lisette_8A2.prompt`) (B26) | Winking Skeever, Solitude | Yes | College-trained lute and vocal performer; refined technique with interest in local stories and artistic freedom. |
| Viarmo (`viarmo_8CB.prompt`) (B26) | Bards College, headmaster | Yes | Altmer custodian of Nordic history and bardic tradition. Good ceremonial role; eligibility should not make him a constant tavern singer. |
| Pantea Ateia (`pantea_ateia_8CC.prompt`) (B26) | Bards College, teacher | Yes | Master vocalist and expert flautist; formal performance and vocal technique are strong distinguishing traits. |
| Ataf (`ataf_14D.prompt`) (B26) | Bards College, student | Yes | Redguard student learning Nordic ballads; basic lute and developing vocals. Preserve the difference between a student and a master. |
| Jorn (`jorn_8CF.prompt`) (B26) | Bards College, student | Yes | Martial drumming and interest in Imperial military cadences. |
| Inge Six Fingers (`inge_six_fingers_8CD.prompt`) (B26) | Bards College, teacher | Yes | Master lute technique and exacting instruction. Bio describes a Nord; technical race is ElderRace. |
| Illdi (`illdi_8D1.prompt`) (B26) | Bards College, student | Yes | Shy student with strong flute skills; a useful instrumental specialist. |
| Giraud Gemane (`giraud_gemane_8CE.prompt`) (B26) | Bards College, historian | No | History, poetry, writing and teaching. JobBardFaction plus a speech trainer class; do not assume a regular musical performance role. |
| Aia Arria (`aia_arria_8D0.prompt`) (B26) | Bards College, student | Yes | Exceptional voice with lute and flute proficiency. |
| Llewellyn the Nightingale (`llewellyn_the_nightingale_DEB.prompt`) (B26) | Lakeview Manor, when hired | Yes | House bard; lute, flute and drum. Bio also suggests nocturnal material. |
| Sonir (`sonir_632.prompt`) (B26) | Windstad Manor, when hired | Yes | House bard with lute, flute and drum proficiency. |
| Oriella (`oriella_633.prompt`) (B26) | Heljarchen Hall, when hired | Yes | House bard with lute, flute and drum proficiency. |
| Lynly Star-Sung (`lynly_star-sung_E03.prompt`) (B26) | Vilemyr Inn, Ivarstead | No | Bio explicitly describes competent lute playing. Farmer class and no scanned bard faction: a useful candidate for explicit registration. |

## Added settlements and inns

These actors have bard-class or occupational/performance markers in the active plugins. Where no biography was found, personality, training, skill level and repertoire remain authoring work. Plugin records establish the marker, not a complete musical identity.

| NPC and biography | Association | Static bard check | Musical information in shipped bio / gap |
|---|---|---|---|
| Arvlvan Thenven — no matched bio | Retching Netch, Raven Rock | Yes | Dunmer bard already provides a Solstheim anchor. No matched named biography found. |
| Gundlof Windsinger — no matched bio | Wyrmstooth / Fort Valus | Yes | Two bard records, including a Cragwater variant. No matched named biography; do not count the variants as two independent people. |
| Hillerica — no matched bio | Stumbling Sabrecat / Fort Dunstad | Yes | Nord bard; no matched named biography. |
| Astanova Giraudin — no matched bio | Sprightful Spriggan Inn, Oakwood | Yes | Breton bard; no matched named biography. |
| Shasha — no matched bio | Nibenese Nights Inn | Yes | Redguard bard; no matched named biography. |
| Parvana Al-Rihad — no matched bio | Riften expansion | Yes | Redguard with singing and occupational bard factions; no matched named biography. |
| Hilda (`hilda_generic.prompt`) (Legacy) | Solitude docks / Forecastle Inn in bio | Yes | College-trained maritime performer: sea shanties and ballads, lute, flute and voice. Matched generic biography belongs to this setting; do not reuse it for unrelated NPCs named Hilda. |
| Ronja — no matched bio | Whiterun expansion | No | Occupational and instrumental-only bard factions, but no matching class/singer flag for SkyrimNet. No matched named biography. |
| Jorn Scarred-Skald — no matched bio | Windhelm expansion | No | Instrumental-only faction; no matched named biography. |
| Kolfinna — no matched bio | Windhelm expansion | Yes | Occupational and singer factions; no matched named biography. |
| Higil Hammer-Shield — no matched bio | Windhelm expansion | No | Occupational bard faction only; no matched named biography. |
| Skadi Frost-Vein — no matched bio | Winterhold expansion | No | Occupational and instrumental-only bard factions; no matched named biography. Existing `skadi_8FE` describes a different NPC. |

## Interesting NPCs and other musical biographies

Several established musicians use combat or citizen classes and scripted performance systems. A scan of SkyrimNet’s native gate alone would miss them. Existing authored songs and scenes need a deliberate integration policy before adding generated performances.

| NPC and biography | Association | Static bard check | Musical information in shipped bio / gap |
|---|---|---|---|
| Alassea (`alassea_A9F.prompt`) (Legacy) | Windhelm / traveling | No | Imperial and Nordic musical training; voice and instruments. Has the 3DNPC bard faction but a mage class, so the SkyrimNet helper misses her. |
| Ange the Song-Bearer (`ange_the_song-bearer_A56.prompt`) (Legacy) | Nightgate Inn association | Yes | Traveling folk repertoire, stories and multiple instruments. |
| Yggleif (`yggleif_798.prompt`) (Legacy) | Bards College association | Yes | Traveling tales, lute, flute and strong vocals. |
| Edwayne (`edwayne_1D5.prompt`) (Legacy) | Bards College | No | High Rock lute-ballad techniques, satire and sharp verbal wit. College faction alone does not pass the SkyrimNet helper. |
| Fironet (`fironet_825.prompt`) (Legacy) | Winking Skeever | No | Aspiring Redguard musician with her grandmother’s lute; intermediate player, naturally pleasant but untrained voice, Redguard folk songs. |
| Asteria (`asteria_45B.prompt`) (Legacy) | Old Hroldan Inn | No | Expert lute and vocal performance, original ballads and adaptations. Installed bard-performance package also confirms this is more than a bio keyword. |
| Skjarn (`skjarn_E09.prompt`) (Legacy) | Four Shields Tavern association | No | Lute and drum, strong baritone, boastful rewrites of traditional Nord songs. |
| Fjona (`fjona_951.prompt`) (Legacy) | Wandering hunter-bard | No | Lute and singing; Nordic ballads. A traveling repertoire rather than a fixed inn identity. |
| Garthe (`garthe_BD6.prompt`) (Legacy) | Candlehearth Hall | No | Redguard string techniques, broad vocal repertoire and historical storytelling. |
| Kalstar (`kalstar_BD8.prompt`) (Legacy) | Candlehearth Hall | No | Lute, drum and flute; Nordic historical ballads and war songs. |
| Bodan (`bodan_3DF.prompt`) (Legacy) | Quest-associated traveling bard | No | Redguard warrior-composer with lute and storytelling skills. Availability is quest-dependent. |
| Amalee (`amalee_88A.prompt`) (Legacy) | Traveling / Eldergleam association | No | Aspiring Nord bard with performance, composition and storytelling skills. |
| Yarbrough (`yarbrough_09E.prompt`) (Legacy) | Frostfruit Inn, Rorikstead | No | Bosmer with College lute training and tenor voice suited to Nordic ballads; much more confident when performing. |
| Reunald (`reunald_BE9.prompt`) (Legacy) | Braidwood Inn, Kynesgrove | No | Breton and Nordic ballads, lute and flute; collects miners’ songs and stories. |
| Daenlyn Oakhollow (`daenlyn_oakhollow_04D.prompt`) (Legacy) | Quest-dependent traveling bard | No | Bosmer expert in lute, vocals and improvisation, with substantial Nordic training. A separate quest variant needs its own identity handling. |
| Darcy (`darcy_56E.prompt`) (Legacy) | College / traveling in bio | No | Redguard poet and orator who favors spoken recitation. A performance registry should support this without automatically turning him into a singer. |
| Jon Battle-Born (`jon_battle-born_68A.prompt`) (B26) | Whiterun | No | Poet and aspiring bard; songwriting and Nordic oral traditions. Suitable for an occasional role, not established here as a resident inn musician. |
| Yngvar the Singer (`yngvar_the_singer_8E5.prompt`) (B26) | Markarth | No | Bio describes a former bard with poetic composition and formal bardic knowledge. Possible occasional return to performance. |

**Other flagged 3DNPC records:** Stygg, Cypress, Ferimus and Talena pass through Bard class but lack matched biographies. Four generic actors named “Bard” also have singer/job flags; the available `bard_522` file does not match their placed reference suffixes. A separate Sven quest record has no verified matching biography. These belong in an integration review, not an automatic expansion of the live ensemble.

### The Cornerclub already has a conditional performer

Interesting NPCs places **the Songstress**, a Breton performer, and **Efram**, her manager, at New Gnisis Cornerclub. Both placed references start disabled. The author’s documentation says they become available after a quest and alternate between the Cornerclub and Old Hroldan. This explains how the installed world can contain a performer whom the player has not encountered there; it does not establish their current save state. [Author documentation](https://3dnpc.com/wiki/interesting-npcs/locations/eastmarch/efram/).

The Songstress has Citizen class and no matching SkyrimNet bard flag; no named biography was found. Efram (`efram_04E.prompt`) (Legacy) describes a manager, introducer and negotiator, rather than the musician. Their existing scene and repertoire deserve preservation. A permanent Dunmer resident with a local repertoire would add something distinct.

## Proposed community performers

All nineteen people in the next three tables have matched B26 biographies. None passes the static SkyrimNet bard check, and none of the reviewed biographies establishes instrumental or singing skill. The suggested musical roles are new characterization proposals, not facts recovered from the bios. No nominations have been applied.

### Gray Quarter

| Candidate | Existing biography foundation | Possible addition |
|---|---|---|
| Malthyr Elenil (`malthyr_elenil_129.prompt`) (B26) | Cornerclub worker; knows Dunmer traditions and history; observes and mediates among patrons. | Best initial resident-musician candidate: evening songs between shifts, with a small learned family or community repertoire. |
| Ambarys Rendar (`ambarys_rendar_128.prompt`) (B26) | Innkeeper and protector of the Cornerclub’s cultural space. | Host, patron and occasional chorus participant; Malthyr could carry the main musical role. |
| Revyn Sadri (`revyn_sadri_123.prompt`) (B26) | Merchant, speaker and keeper of cultural objects and stories. | Visiting storyteller or occasional reciter, if we want a second kind of performance. |
| Suvaris Atheron (`suvaris_atheron_126.prompt`) (B26) | Shipping manager with a complicated place in Windhelm’s social hierarchy. | A possible individual hobby if desired; her bio does not establish a natural community-music role. |

Luaffyn is already a Dunmer musician elsewhere in Windhelm. Her audience-adapted repertoire offers a useful contrast with a Cornerclub resident playing primarily for other Dunmer; neither needs to represent all Dunmeri music.

### One musician per major caravan

| Caravan and route in shipped bios | Members with biographies | First candidate to discuss |
|---|---|---|
| Ri’saad: Whiterun–Markarth | Ri'saad (`ri_saad_340.prompt`) (B26), Atahbah (`atahbah_341.prompt`) (B26), Khayla (`khayla_33F.prompt`) (B26), Ma'randru-jo (`ma_randru-jo_225.prompt`) (B26) | Atahbah: a repertoire of remembered home songs would fit her attachment to Elsweyr. This would be a new musical background. |
| Ahkari: Dawnstar–Riften | Ahkari (`ahkari_34A.prompt`) (B26), Zaynabi (`zaynabi_348.prompt`) (B26), Kharjo (`kharjo_92D.prompt`) (B26), Dro'marash (`dro_marash_347.prompt`) (B26) | Dro’marash: speechcraft and persuasive delivery make him a promising song/story leader. Kharjo is an alternative for a more personal, homesick repertoire. |
| Ma’dran: Solitude–Windhelm | Ma'dran (`ma_dran_345.prompt`) (B26), Ma'jhad (`ma_jhad_344.prompt`) (B26), Ra'zhinda (`ra_zhinda_342.prompt`) (B26) | Ma’jhad: his formal, poetic, measured speech suggests a distinctive delivery. Instrumental skill would need to be authored separately. |

These choices cover all eleven existing caravan members without adding new NPCs. The three camps could differ by the musician’s history, preferred tempo and social occasion, while sharing some songs that plausibly travel along the caravan network. Do not infer singing ability from speechcraft alone.

### Assemblage and dockworkers

| Candidate | Existing biography foundation | Possible addition |
|---|---|---|
| Scouts-Many-Marshes (`scouts-many-marshes_140.prompt`) (B26) | Diplomatic, hopeful dockworker who advocates for his coworkers. | Strongest work-song leader: short calls timed to hauling or loading, with a repeated group response. |
| Shahvee (`shahvee_141.prompt`) (B26) | Optimism, resilience, skilled work and a deliberate philosophy of finding happiness. | Evening communal songs at the Assemblage; a contrasting setting and mood to daytime labor. |
| Neetrenaza (`neetrenaza_13F.prompt`) (B26) | Experienced worker with solidarity toward the other Argonians. | Response voice, occasional lead verse, or someone who knows the older words. |
| Stands-In-Shallows (`stands-in-shallows_142.prompt`) (B26) | Longing for Black Marsh and knowledge of its traditions. | Potential source of remembered verses and oral repertoire, if that is the characterization we choose. |

A work song can begin with one leader and a simple shared response; every participant need not become a professional bard. Represent “can lead,” “can join a chorus,” and “can clap” as separate capabilities. Controlled singing without an instrument and synchronization with labor animations remain research tasks.

## Clapping and animation evidence

The user observed synchronized audience clapping during the Olaf festival. The active records contain `MS05KingOlafsFestivalApplaud` (`Skyrim.esm:1027DE`) and `MS05KingOlafsFestivalScene` (`Skyrim.esm:06C0EB`), providing a concrete starting point for reproducing that result. General assets include `SpectatorClap` (`Skyrim.esm:066375`) and `BardAudienceStayInLocationAndApplaud` (`Skyrim.esm:108ED6`, overridden here by `SkyrimsGotTalent-Bards.esp`).

**Status:** clapping is observed in game, with matching installed assets located. The next experiment is whether we can start, repeat and stop it predictably for a chosen audience and arrangement. Stomping remains unverified. Voice-only performance also remains unverified; an empty equipment slot alone would not establish that the animation’s attached instrument disappears.

## Implications for the music design

1. **Keep an explicit performer registry.** Existing class/faction markers can seed it. Add individual capabilities and participation roles; do not change a combat/stat class merely to make a character musical. Preserve existing quest and performance scenes.
2. **Use each biography to build a small musical profile.** Useful fields are learned traditions, instruments, vocal role, skill level, repertoire, audience and occasion. Luaffyn’s cross-cultural training, Ogmund’s Nordic identity, and Lurbuk’s limitations show why a race/location lookup alone is insufficient.
3. **Map technical races to culture deliberately.** Project ja-Kha’jay gives several caravan members custom race records, including Ohmes, Dagi-raht, Cathay-raht and Pahmar-raht variants. An exact `KhajiitRace` check would miss them. Inge’s ElderRace is another example. Ancestry also does not automatically determine musical training.
4. **Fill the largest gaps first.** Arvlvan Thenven is an existing Dunmer bard in Raven Rock without a matched bio. Malthyr plus one caravan member per group plus Scouts/Shahvee would add community music where our reviewed bios currently provide no musicians. These are proposals to choose among, not approved character changes.
5. **Connect actual performer context before relying on these fields.** Solo Lute 0.1.0 currently transforms the music-generation request; the recovered implementation does not yet provide the NPC/biography/location connection assumed by the draft spec. An inventory and identity mapping are groundwork for that connection.
6. **Keep the expanded regional scope.** The current design includes Cyrodiil and Solstheim; the earlier nine-hold restriction is historical. Solstheim and the Gray Quarter can share traditions while developing different local repertoires. Instrument families, audience participation and individual training can produce variation within the limited animation set.

## Audit scope and evidence

The record scan resolved winning definitions from **2,004 enabled plugins**, with no missing enabled plugin files. The raw inventory contains 123 selected NPC base records: 85 selected by broad bard class/faction markers, 20 comparison/candidate records, and 18 additional biography or scene-context records. These counts are not a count of active musicians. They include duplicate quest variants, unused records, special encounters and templates.

Examples requiring exclusion or review: Adonato Leotelli is a writer, Arivanya and Cedran work with horses, and Louis Letrush is a horse trader despite their Bard class. The scan also captures Grete, Lord Niles Macnarian, Lorumend, a summoned Aspect of Peace, twenty Fertility Mode grown-child bard templates, three Animated Carriage templates, Sovngarde/other quest actors and special traveling-bard encounters. Their class/faction flags alone do not establish an ordinary performance role. Lorumend’s exact musical role remains to be checked.

Name matching also needs identity checks: Karita, Sven, Hilda, Skadi and Valla have collisions or variants. In particular, the musical `valla_2D4` biography does not match the reference for the audited 3DNPC Valla; the matched `valla_E5E` describes a Nord brawler. She is excluded from the musical shortlist. A three-digit reference suffix is a useful check, not a globally unique identifier; record origin and character content must agree too.

The scanner resolves direct NPC-template inheritance for factions, race and class. It does not simulate leveled template selection, quest aliases, script-added factions, runtime spawns or current save changes. Biographical venue claims are identified as such. This is a substantial installed-record baseline, not a claim to have identified every scripted musical scene in every mod.

- Supporting raw inventory, extraction scripts and disassembly evidence are retained with the original local audit. Binary evidence is specific to that beta26 installation, not a public API guarantee.
- [Current regional music spec](bard-regional-music-spec.md) incorporates the subsequent palette design; this audit preserves its installation-specific observations and proposals.
