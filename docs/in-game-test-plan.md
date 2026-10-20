# In-game test plan: Hold Music at the Bannered Mare

**Migration update (15 October 2026):** the procedures below describe RC4.1
tests and recorded outcomes. For MGO RC5 with SkyrimNet beta 27, use the
[migration validation sequence](stack-migration-rc5-beta27.md#validation-on-the-new-stack).
Recheck the selected profile, save and controller handoff before repeating a
test; disabling SkyrimNet composition alone does not disable its playback.

**Result (9 October 2026, 11:14):** passed. Mikael composed and performed
"The Shadowed Rose" through adapter 0.2.2 with the Whiterun recipe, correct
duration and lyric pacing; see the verification record. The plan below is kept
for repeating the test.

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

Sven was not in the Sleeping Giant Inn when you entered it at 00:17 on
October 8 (in-game 7:53 AM); only Orgnar, Delphine, Embry and Gorr were nearby.
The Bannered Mare itself was never entered that day. Static record inspection
also suggested that SkyrimNet would exclude Sven, but that inference was
disproved by his successful SkyrimNet playback on October 13. His runtime
eligibility cannot be inferred from those static records alone.

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

# Second test: Sven at the Sleeping Giant Inn (Hold Music owned path)

Prepared 11 October 2026. This is the first headset test of the owned
performance path (T1 gate in the design doc).

**Installation update (13 October 2026):** the prepared package is now installed
and enabled in the experimental profile on HALCYON. All 22 installed files,
the two profile-list edits, and backups of those lists and the Save296 ESS/SKSE
pair were verified. The original save is unchanged. Sven has the prepared
158.7-second instrumental in slot 3; the first in-game test remains pending.

**Runtime correction (14 October 2026):** the first Sven visit on October 13
used the already installed adapter/SkyrimNet path. At 18:09:45 CDT, SkyrimNet
selected the cached Talsgar instrumental **Ballad of the Open Road**, played
it on Sven, and logged playback finishing at 18:12:40. No new composition was
requested for that performance. The player described it as a rather nice
instrumental solo. This is evidence of successful cached playback, not of
the new controller or its Whiterun slot.

The owned controller was installed later, at 18:39 CDT. Its trace and receipts
were still empty when checked on October 14. **The original test procedure
required an explicit handoff to prevent SkyrimNet and Hold Music from
controlling Sven together; the procedure below is now revised.** The assumption
that SkyrimNet never acts on Sven is false in this save. Game settings were
unchanged during that initial evidence review. The retained source is
`SkyrimNet.2026-10-13_22-48-09.log`; a filtered local evidence copy is kept under
`local/checks/sven-first-visit-2026-10-14/playback-evidence.json`.

**Post-session evidence (14 October 2026):** the player did not revisit Sven.
The session nevertheless establishes two useful facts: `HM_Quest` started at
18:57:27 CDT, and SkyrimNet logged `BardSinging: Shutting down` at 19:01:50
when its dashboard switch was turned off. The adapter preserved that edit in
the profile data mod on game exit at 19:30:14. Trace and receipt arrays remain
empty; without an inn visit, this does not establish a controller failure.
The filtered report is in `local/checks/post-session-2026-10-14/evidence-report.md`.

The new preflight also found a conflicting **older overwrite copy** of
`BardSinging.yaml`, last modified October 5 CDT, with singing still enabled.
The adapter's configured source and last overlay both have singing disabled.
The live shutdown above is confirmed, but loose-file priority alone cannot
prove what a subsequent adapter mapping will expose. Resolve the conflict or
verify the VFS winner before declaring the next pilot ready. No game files or
settings were changed during this post-session inspection.

**Crash and fix update (15 October 2026):** Sven's next visit crashed in the
owned controller's candidate scan while a vanilla flute piece was playing.
The installed PapyrusUtil VR dead filter dispatches the wrong virtual function.
The [RCA and fix](sven-crash-2026-10-15.md) document the binary evidence and the
installed two-file workaround. SkyrimNet's bard feature was already disabled
in that run and was left disabled. All 52 package tests passed at installation;
successful owned playback still needs runtime confirmation. The next headset
test checks that the trace advances beyond `check_start` into playback. If
loading inside the inn, leave and re-enter to schedule the check.

**Development policy (19 October 2026):** this is a runtime lifecycle check,
not approval of a regional musical style. Offline engineering continues with
provisional recipes and existing audio; see the [development roadmap](development-roadmap.md).

## Before the next session

Installation is already complete; do not reinstall solely to run this test.
An agent can use the updated checkout on HALCYON to inspect the prepared files:

```powershell
py -3 -B tools\preflight_performance.py --mo2-root "C:\MGO\Skyrim MGO 4.0 RC4.1" --profile "MGO EXP - SkyrimNet b26 + SeverActions 4.2" --performer sven --json
```

This makes no provider calls and changes no inputs. It checks the enabled
package, loose-file precedence, configured adapter input, MCM defaults and
overrides, ownership, matching audio format/duration, and evidence-file validity.
`prepared_for_headset_test` means those file checks passed, not that playback
works. `blocked` names the checks needing attention. In particular, an old
overlay is not assumed to be live, and zero trace entries is not a failed test.
See [the preflight contract](evidence.md#read-only-performance-preflight).

The required pilot state is **SkyrimNet Bard Singing off, Hold Music on**.
If needed, the agent can use SkyrimNet's live web dashboard to change its
Quick Toggles → Bard Singing switch, as done on October 14; the player need
not find that menu in VR. Keep dialogue and other gameplay features enabled.
Offline profile changes or reinstallation require both Skyrim and MO2 closed.

## What to do

1. Launch as usual and load a pre-crash save. In MCM -> Hold Music, confirm
   Enable Hold Music is on; if the menu is missing, skip this test and report it.
   Keep SkyrimNet Bard Singing disabled; dialogue remains available. Only Sven
   and Lynly are owned by Hold Music. If loading inside the inn, leave and
   re-enter so the controller schedules a fresh check.
2. Travel to Riverwood and enter the Sleeping Giant Inn while Sven is inside
   (he is there most of the day and evening). The controller waits a random 15
   to 60 seconds after you enter, then checks the room.
3. Expect: the vanilla lute song stops if it was playing, Sven raises his lute,
   and a solo lute piece in the Whiterun recipe plays from his position for
   158.7 seconds (slot 3). Open his ordinary dialogue menu during the piece:
   both sound and lute animation should stop. Leaving the inn or combat should
   also stop it, but a short session only needs the one dialogue-interruption
   check. If a vanilla song tries to restart mid-performance it should stop
   again within two seconds. These are expectations awaiting runtime proof.
4. If nothing happens within two minutes: step outside and back in once. Then
   note the game time and move on; the trace will say why.
5. Do not expect an immediate repeat after a successful start: performer
   cooldowns and used-slot locks apply even if the piece was interrupted.
   Lynly at the Vilemyr Inn in Ivarstead is an optional separate venue, not a
   required detour (slot 4, Rift recipe, 182.5 seconds).
6. For ordinary play afterwards, turn Hold Music off before re-enabling
   SkyrimNet Bard Singing. If the session ends before doing this, report it so
   the next launch state can be checked; do not assume the dashboard change
   expires when Skyrim exits.

## Afterwards

Nothing to collect by hand. When the game is closed, an agent runs
`tools/collect_evidence.py` on Halcyon; it gathers `trace.json`, `receipts.json`,
the Hold Music logs and the bard-related SkyrimNet log lines into one redacted
report. The trace records every inn entry, every registry match with its owner
and eligibility, the chosen slot, the vanilla stop, the start, and the stop
outcome, so a silent inn is diagnosable without Papyrus logging.

## What it does not test

Sung material: both prepared seed recordings are instrumental. Lyrical
preparation requires a fresh actor-knowledge snapshot and a suitable planner
decision; a conversation alone does not guarantee that a song will be selected.
