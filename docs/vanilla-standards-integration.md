# Traditional standards: the first native handoff

The accepted repertoire policy keeps original authored performances alongside
local songs and topical originals. Start with **Ragnar the Red** as a native
performance, with no generated audio or lyric request. Later regional recordings
can retain its recognizable identity and words. Cross-region versions need a
parent song identity or a reviewed contract change; the current library rejects
one composition ID with conflicting regions. This audit does not implement a
planner route or runtime handoff.

## Ragnar's existing route on this VR profile

| Step | Verified record or script |
| --- | --- |
| Request menu | `BardSongsGeneralRequestBranchTopic` (`Skyrim.esm:00055843`), winning Relationship Dialogue Overhaul record, links to the title request. |
| Title request | `BardSongsDrinkingSong02RequestBranchTopic` (`000D0802`), with response `INFO 000D081D`. |
| Dispatch | `TIF__000D081D.Fragment_0` invokes `BardSongsScript.PlaySongRequest(speaker, "Any", False, 1, True)` on the owning `BardSongs` quest (`00074A55`). This is a queued, one-shot request through the vanilla script, not a direct scene start. |
| Scene | Song index `1` chooses `BardSongsDrinkingSong02Scene` (`000D0843`) or `BardSongsDrinkingSong02WithIntroScene` (`000D0845`). The **02** in the editor ID is not the dispatch index. |
| Singing | Each scene leads to six dialogue actions sharing verse responses `000D083C`–`000D0841`; the intro scene has an additional dialogue action. The scene scripts manage the lute idle, audience quest, inn music and end cleanup. |

The title response requires `BardSingerFaction` and excludes Talsgar and the
`FemaleEvenToned` and `MaleNord` voice types. The general inn request branch
also requires an inn and filters `BardNoRequestFaction` and current followers;
the winning RDO records add a relationship-rank condition with an option to
disable rival-service blocking. These are existing dialogue conditions to
retain, not a new Hold Music eligibility list. The winning Sven actor record
(`Synthesis.esp`) retains `MaleYoungEager`. A stock English VR voice archive
index contains all six verse FUZ members for that voice and the intro member.
That confirms assets exist; it does not identify the live archive/loose-file
winner or prove a particular save currently offers the request.

`PlaySongRequest` stores one set of request fields and schedules an update.
`PlaySong` waits for dialogue to close, sets up bard aliases and location
ownership, and respects its follower and loaded-actor checks. The script can
replace Sven's requested song with a lute instrumental while `MQ106` is
strictly between stages 20 and 50, or while `MQ203` is running. Preserve those
branches. The scene end fragments release the idle and tavern silence and
attempt the normal follow-on; the saved non-continuous request and stop state
matter to that call. A bare `Scene.Start()` would skip the request setup.

## Handoff boundary

- Keep vanilla dialogue requests available as the first route. Admit a future
  Hold Music request only through a reviewed single-performance handoff with
  equivalent winning dialogue and quest gates. Never force an unavailable title
  or dispatch concurrent requests into the shared vanilla request fields.
- Before native dispatch, stop and clean up any *owned* audio and animation,
  then hold off new Hold Music admission and its vanilla-stop polling through
  the queued request and live scene. Resume after actual completion or confirmed
  cleanup; check both scene variants. A queued request is not proof of a start.
- Protect quest scenes and Skyrim's Got Talent duets as separate owners.
  `StopAllSongs()` is broad: it stops both Ragnar variants and other vanilla
  scenes. Do not use it to take an authored scene away from its owner. BA Bard
  Songs' inspected instrumental overrides are separate from these vocal records.
- Keep SkyrimNet's native bard manager disabled for this pilot. Its playback
  state is independent of the vanilla `BardSongs` scenes.

## First test on SkyrimNet 1.0 RC1

1. After the upgrade's startup verification, use a copied test save in a guarded
   session. Verify native Bard Singing is off and keep provider dispatch disabled
   for the test. Initially suspend Hold Music admission, so the first observation
   isolates the original scene. Use ordinary game dialogue, not SkyrimNet chat.
2. With Sven in the Sleeping Giant Inn and eligible in that save, request Ragnar
   through the standard menu. If unavailable, record the dialogue and quest
   conditions; do not force the scene. Observe optional intro, voiced verses,
   lute idle, no competing audio and normal cleanup. On a separate eligible
   trial, check interruption and cleanup. No new music or lyrics are required.
3. After the [ownership diagnostic](ownership-diagnostic-2026-11-03.md) and a
   demonstrated owned performance, test the mixed handoff independently. Capture
   admission suspended, owned instance stopped, one native variant started,
   native cleanup, and later admission resumed. Include a protected scene or
   duet refusal case. The native-only observation cannot pass this mixed test.

**Evidence boundary:** Offline inspection of installed Skyrim VR records, English
string tables, prior `Skyrim - Misc.bsa` PEX extraction and current profile
plugin order. The 8 November scan resolved all 2,005 enabled plugins without
parse errors. USSEP wins the `BardSongs` quest and the first shared verse record;
RDO wins the general request path. No active override was found for the Ragnar
title response or either scene. Report and voice-index evidence are in
`local/vanilla-standards-20261108.json` and
`local/vanilla-standards-voice-index-20261108.json`; no audio was extracted. No
game was launched and no runtime result is claimed here.
