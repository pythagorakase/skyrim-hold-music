# In-game test plan: Hold Music at the Bannered Mare

Written 9 October 2026 for the next short play session. Nothing here changes
the game; it describes what to do and what to look at afterwards. It assumes
the adapter currently installed on HALCYON (0.2.1, or 0.2.2 if the duration
change lands first; both behave the same for this test).

## Before launching

1. **Restart MO2** (close it, open it again on the experimental profile). It is
   free, it loads the current plugin code, and it clears a stale runtime
   overlay that still points at the old helper's port.
2. Launch Skyrim VR from MO2 as usual. Before loading a save, confirm in the
   MO2 `logs` folder that `HoldMusic.log` ends with "Prepared temporary Bard
   Singing route ..." and that `HoldMusic-Service.log` ends with
   "Independent music helper ready ... build=0.2.x". If `HoldMusic.log`
   says "Adapter setup failed", stop: SkyrimNet would then use its own
   provider and style, and a song would look like a Hold Music result without
   being one.
3. **Load the latest save** (Save263, Heljarchen Hall, 01:06 on Oct 9).
   SkyrimNet composes a new song only when the game clock is more than eight
   in-game hours past the last composition (game time 823 h). That save is
   about 49 hours past it; an older save may not be, and would make Mikael
   replay the cached Talsgar instrumental instead of composing.
4. The Hold Music *Instrumental chance (%)* has been set to 0 for this first
   test so the result is a sung Whiterun piece and the fuller code path is
   exercised. Set it back to 50 afterwards in the SkyrimNet dashboard
   (Plugins, Hold Music) or in
   `mods\MGO Experimental - Profile Data\SKSE\Plugins\SkyrimNet\config\plugins\HoldMusic\settings.yaml`.
5. Expect a paid request of about $0.08 for the music plus a small lyric
   model call, and 80 to 120 seconds of generation time.

## What to do

1. Fast travel straight to Whiterun and go directly to the Bannered Mare.
   Do not stop at other inns or linger where another recognized bard could
   be: SkyrimNet starts the composition for the first eligible bard it finds
   after a cell load, and that would use up the open interval on someone
   other than Mikael.
2. Mikael must be inside when the inn loads. He is there most of the day and
   evening. SkyrimNet runs its bard check about two seconds after the cell
   load, so if he is not inside, leave and come back later rather than
   waiting.
3. Wait through the generation. When it completes, SkyrimNet may or may not
   start the performance on its own. If nothing plays within a minute of the
   completion, step outside and back in: dispatch happens on cell load.
4. Listen. Note whether it is one voice with one plucked instrument, whether
   the words are sung as written, and whether it feels like the Whiterun
   recipe (strophic ballad with a short refrain, triple-meter lilt).
5. Save afterwards.

Optional free pre-check of playback alone: in SkyrimNet's chat, type
`/playsong Ballad of the Open Road` (the cached Talsgar instrumental) and see
whether music plays and the SkyrimNet log shows "Playback started". This
exercises playback without any new generation.

## What the logs will say

- **A new composition through Hold Music.** `logs\HoldMusic-Service.log` gets
  `request=... bard='Mikael' location='The Bannered Mare, Hold: Whiterun'
  region=whiterun via=suffix-table mode=vocal ...` then
  `response_forwarded bytes=...`. SkyrimNet's main log,
  `profiles\MGO EXP - SkyrimNet b26 + SeverActions 4.2\experimental-documents\SKSE\SkyrimNet.log`,
  shows `Generation check ... shouldGenerate=true`, `Starting song generation
  for 'Mikael'`, then `Playing '<title>' on bard 'Mikael' (<seconds>s)` and
  `Playback started`. The song appears in the Bard Singing dashboard page and
  in `bard_songs` with Mikael as composer.
- **A cached song is replayed instead.** No new service-log line; the
  SkyrimNet log shows `shouldGenerate=false` and `BardSinging/Filter`
  selecting "Ballad of the Open Road". That proves playback of adapter output
  but not the Whiterun recipe; it means the interval was not open (older
  save) or another bard already consumed it.
- **Nothing plays.** If the SkyrimNet log has no `Generation check` at all,
  no eligible bard was in the cell when it loaded. If it has the check and a
  generation but no `Playing` line, playback did not start; try re-entering.
  SkyrimNet also has an open upstream bug (GitHub issue #559) where the
  ambient trigger intermittently stays silent in this very inn. The second
  ambient option is Karita at the Windpeak Inn in Dawnstar, nearest
  Heljarchen Hall. Asking a bard to sing in dialogue is a third path, but it
  has its own open upstream bug (#668) and is not relied on here.
- **A request fails.** The service log shows `Music request stopped: ...` or
  `OpenRouter music HTTP status=...` and no song plays. The likeliest cause is
  the lyric model omitting the routing marker. A failed request costs only the
  lyric model call; no music charge is made and nothing is retried.

## How SkyrimNet decides (from its own log and binary, 9 October)

The bard manager runs about two seconds after every cell load. If an eligible
bard (Bard class, or a member of `BardSingerFaction`) is in the loaded cell it
logs a `Generation check` line with the last composition's game time, the
current game time and the 8-hour interval, then either starts a new generation
or picks a gender-matched cached song. If no eligible bard is in the cell it
logs nothing. These rules were observed from one real run and the binary's
strings; treat the exact formula as inferred.

## Why Riverwood was silent

Two reasons. Sven's winning record has the Lumberjack class and is listed in
`BardSingerFaction` at rank -1 (not a member), so SkyrimNet's check never
treats him as a performer. And he was not in the Sleeping Giant Inn when you
entered it at 00:17 (in-game 7:53 AM); only Orgnar, Delphine, Embry and Gorr
were nearby. The Bannered Mare itself was never entered on Oct 8 (Whiterun
interiors visited were Warmaiden's and Belethor's). Registering Sven is a
design decision for the performance-ownership work, not an adapter fix.

## Listening before the test

The 0.2.1 live check produced the exact Whiterun sung recipe this test will
request: `local/checks/Hold Music 0.2.1 - Whiterun vocal (Mikael fixture).mp3`
on the Mac, and `C:\MGO\HoldMusic\local\music-service-check-0.2.1\` on
HALCYON. Listening to it first costs nothing and tells you whether the recipe
itself produces one voice and one plucked instrument before the in-game chain
is added on top.

## Afterwards

Nothing needs to be collected by hand. The two logs, SkyrimNet's `bard_songs`
row and audio file, and the save are enough to reconstruct what happened; a
short note on what it sounded like is the one thing only you can provide.
