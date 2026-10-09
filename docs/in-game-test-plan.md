# In-game test plan: Hold Music 0.2.1 at the Bannered Mare

Written 9 October 2026 for the next short play session. Nothing here changes
the game; it describes what to do and what to look at afterwards.

## Before launching

- Launch from the already-open MO2 as usual, in the experimental profile. No
  MO2 restart is required: the 0.2.1 helper files are installed and the old
  helper was stopped, so the next launch starts the new helper automatically.
  (Restarting MO2 is harmless and additionally loads the 0.2.1 plugin code.)
- The **Hold Music** setting *Instrumental chance (%)* is 50. Leave it unless
  you specifically want to force the sung path (0) or the instrumental path
  (100) for this one test.
- Expect a few seconds' delay and a paid request (about $0.08) if a new
  composition is made.

## What to do

1. Go to the Bannered Mare in Whiterun while Mikael is there and awake
   (he performs in the evening; sitting down is not needed).
2. Stay in the inn for a few minutes, out of menus and dialogue. SkyrimNet's
   ambient scheduler starts bard songs on its own when you enter an inn with a
   recognized bard. If nothing starts after a few minutes, ask Mikael in
   dialogue to play a song (SkyrimNet's on-request path), then wait again.
3. Listen. Note whether the piece sounds like a solo cittern/lute with or
   without one voice, whether the voice sings the words it was given, and
   whether it feels like the Whiterun recipe (strophic ballad with a short
   refrain, triple-meter dance lilt in livelier pieces).
4. Save afterwards so the song record is kept.

## What could happen, and how to tell

- **A new composition through Hold Music.** `logs\HoldMusic-Service.log` in the
  MO2 folder gets a line like
  `request=... bard='Mikael' location='The Bannered Mare, Hold: Whiterun'
  region=whiterun via=suffix-table mode=vocal|instrumental ...`, followed by
  `response_forwarded bytes=...`. The song appears in SkyrimNet's Bard Singing
  dashboard page and in the `bard_songs` table with Mikael as composer.
- **A cached song is replayed instead.** SkyrimNet keeps a shared, gender-
  filtered pool of cached songs. One cached male song already exists from the
  Oct 8 adapter test (Talsgar the Wanderer, instrumental, plain Nord recipe).
  If Mikael plays that, no new service-log line appears. That still proves
  playback of adapter output in-game, but not the Whiterun recipe. New songs
  are generated every 8 game-hours; well over 8 game-hours have passed since
  that test, so a new composition is the likelier outcome.
- **Nothing plays.** SkyrimNet has an open upstream bug (GitHub issue #559)
  where the ambient bard trigger intermittently stays silent in the Sleeping
  Giant Inn and the Bannered Mare. If no music starts and
  `HoldMusic-Service.log` has no new request, the adapter was never asked; try
  the dialogue request, or another inn with a recognized bard (Karita at the
  Windpeak Inn in Dawnstar is nearest Heljarchen Hall).
- **A request fails.** The service log shows `Music request stopped: ...` or an
  `OpenRouter music HTTP status=...` line and no song plays. The most likely
  cause is the lyric model omitting the routing marker; a failed request is
  not retried and costs nothing.

## Why Riverwood was silent

Riverwood does have a bard, Sven at the Sleeping Giant Inn, but SkyrimNet's
bard check accepts the Bard class or `BardSingerFaction`, and Sven's winning
record has the Lumberjack class with only `JobBardFaction`. SkyrimNet never
treats him as a performer, so no music request reaches the adapter there.
Registering Sven is a design decision for the performance-ownership work, not
an adapter fix.

## Afterwards

Nothing needs to be collected by hand. The service log, SkyrimNet's
`bard_songs` row and audio file, and the save are enough to reconstruct what
happened; a short note on what it sounded like is the one thing only you can
provide.
