# Hold Music

Musical traditions for Skyrim's bards, with a local workshop for generating songs, comparing ideas and keeping listening notes.

The active workshop contains **eleven provisional regional styles**: the nine Skyrim holds, Solstheim and Cyrodiil. **Reach sean-nós** remains a separate comparison against its puirt-à-beul base. Every style awaits listening validation. **Listening validation does not gate engineering progress:** the current recipes are versioned provisional inputs while listening confidence develops separately. Further variations and cultural candidates remain outside the active workshop until deliberately admitted in a source revision; admission does not require all eleven styles to pass first.

The [knowledge bridge](docs/knowledge-bridge.md) supports private actor-scoped snapshots and [bounded lyrical library preparation](docs/executor.md).

The [development roadmap](docs/development-roadmap.md) separates continuing engineering from optional listening work. The owned controller's [15 October crash workaround](docs/sven-crash-2026-10-15.md) is installed on HALCYON; successful playback and interruption after that fix still need a short in-game check. The [RC5 / SkyrimNet migration plan](docs/stack-migration-rc5-beta27.md) describes the next stack target and does not block portable development.

See [runtime evidence](docs/evidence.md) for MO2 receipts and trace storage and the redacted evidence collector.

## Run the Music Workshop

The workshop opens on **Blind Auditions**, an open-ended listen-and-judge loop. Choose **Clip** or **Full**, then press **Play**. Listen until playback ends, choose the intended style or **I'm Not Sure**, and press **Play** again when ready for another recording. After playback ends, choose from **three styles: the intended style and two distractors**, or **I'm Not Sure**. The three choices are shuffled and saved for that question, so reloading cannot change them. Each choice has a concise musical description available by pointer hover or keyboard focus. The intended style, exact prompt, instrument and listening cue stay hidden until your answer is saved. There is no fixed session length.

**Clip** uses the existing pool of roughly thirty-second **`lyria-3-clip-preview`** recordings. **Full** uses complete **`lyria-3.5`** songs. The selected format, recipe and test conditions determine which saved recordings are compatible; scores from the two formats stay separate. The main **Play** action first reuses eligible saved audio. If none is available, that explicit action may make **one paid generation request**, save the result and play it. The interface discloses this fallback. Changing settings, refreshing the page, reaching the end of playback or saving an answer never starts a generation, and failed requests are never automatically retried.

Choose the replay policy and, for replay modes, the minimum interval in hours since a recording was last heard:

| Replay Policy | What Play Selects |
|---|---|
| None | An unseen compatible recording; if the fresh queue is empty, one new generation |
| All Cached | A compatible cached recording whose replay interval has elapsed, then unseen stock, then one new generation if needed |
| Incorrect Only | A previously missed compatible recording whose replay interval has elapsed, then unseen stock, then one new generation if needed |

Every new generation is a paid request. Replayed recordings remain practice and cannot add another first-encounter score. **Incorrect Only** follows the latest saved judgment, including practice corrections; an unsure answer counts as a miss. Each audio play, including a history replay, restarts that recording's interval. A few independent recordings per style provide a useful starting queue; the initial seed batch is configured for **three clips per baseline style, 33 clips total**. Existing clips, their exact prompts and their judging history are retained as the interface changes. Batch preparation and replenishment remain available separately with an explicit request limit; saved receipts establish what completed.

Preview the initial seed batch without making provider requests:

```sh
python3 tools/seed_blind_clips.py --mode canonical --clips-per-style 3 --max-clips 33
```

The preview reports the exact model, frozen test conditions and style counts. Stop the workshop server before executing the authorized paid batch, then restart it to judge the saved pool:

```sh
python3 tools/seed_blind_clips.py --mode canonical --clips-per-style 3 --max-clips 33 --execute
```

The seeder writes a request receipt before contacting the provider and stops on the first provider, authentication or storage failure. Rerunning the command resumes only remaining unattempted deficits when the cohort has no blocked failure; it does not retry failed or interrupted slots. Inspect any failure before authorizing a recovery request.

Targets and distractors come from the eleven baseline styles; Reach sean-nós is an optional challenger. Each question shows only the target and two distinct distractors. Fresh targets are balanced across sessions sharing the same frozen test conditions. Choose each style's usual arrangement, instrumental plucked strings, or supported instrumental reedless woodwinds; each test condition uses its own compatible recordings. Shared-family reductions are listening experiments and do not expand the full-length workshop's canonical arrangements. Sung auditions use neutral supplied lyrics; Winterhold stays wordless and Hjaalmarch instrumental. Blind auditions use canonical recipe defaults, preserving browser-edited directions in **Make a Take**.

Results show overall and per-style first-answer accuracy, attempts, the actual choice set's chance baseline and confusion pairs. “I'm Not Sure” counts in the denominator. Scores are separated by format/model, prompt set, arrangement mode, neutral lyrics and the number of offered choices. Three-choice questions have a one-in-three chance baseline; earlier questions with the full palette retain their original baseline and separate results. Cached replays and **Session History & Practice** preserve the original first answer; repeated audio cannot become a new first encounter. Optional **Keep / Rework** reactions record enjoyment separately. Short-clip recognition does not establish full-length Lyria 3.5 behavior or approve a style for the game.

Pools, sessions, exact prompts, responses and audio save privately under `auditions/.blind/`, separate from the existing take library. Pool records live in `.blind/pool/` and their audio in `.blind/audio/`. Refreshing or restarting restores saved work. An interrupted seed request is never automatically resubmitted; inspect its status before explicitly requesting more paid clips. Include hidden files when backing up `auditions/`. A completed seed batch supplies listening material; it does not establish stylistic fidelity or production quality.

**Compare Takes** retains the existing listening queue. Each style comparison loads both takes of each style in one click, grouped as **A1/A2** and **B1/B2**. Shared lyric sets are labeled so you can compare the same words across styles. **Save & next comparison** records each style's consistency, their separation, enjoyment and notes. Same-style repeatability tests load their two takes. The latest saved trial supplies the exact recordings; missing samples are never replaced with unrelated library takes.

Earlier decisions about a single pair remain visible with their notes, and the comparison reopens for a decision across both takes per style. Reversed and identical-audio controls used to test the AI judges are omitted from human listening tasks. Missing recordings and obsolete prompts appear under **Waiting for Takes**, where the available recordings can still be heard. Automated judgments identify the original pair they cover; they are optional supporting evidence and never approve a style.

Use **Take Library** to find all saved recordings, filter by style or prompt status, and inspect their exact prompts. **Delete take** moves the whole recording and its provenance to recoverable **Trash**; use **Undo** or filter to Trash and restore it. Deleting a take makes its existing comparisons incomplete without replacing either recording or discarding your decision. Trash is retained until you manage it outside the workshop; there is no permanent-delete button.

**Current prompt** means the saved recipe fingerprint (or the trial's frozen palette snapshot) matches today's recipe. Recipe changes, including changes within the same named revision, mark recordings **Obsolete prompt**. A different musical direction saved in this browser marks earlier takes **Obsolete edited prompt**. Older takes without reliable version evidence are **Prompt version unknown**, not assumed current or obsolete. Deferred styles have their own label. Every new workshop take records its recipe fingerprint and editable musical direction separately from performer context and lyrics.

For generation, open **Make a Take**, choose musical traditions, select the shared performer arrangement and optionally a saved SkyrimNet lyric draft, edit the musical directions, then click **Generate song**. The workshop calls Google's Gemini API directly with **`lyria-3.5`**. Each generation is a paid API request using your Google project's billing and quota. Requests run one at a time; the workshop never retries a generation automatically.

From the repository folder, save your Gemini API key using the hidden local prompt:

```sh
python3 tools/configure_key.py
```

On Windows, use `py -3` instead of `python3`. The prompt does not echo your key or put it in your shell history. It writes `~/.config/hold-music/gemini-api-key`, outside the repository, with owner-only file permissions on macOS/Linux. The key stays on the server; it is not stored in the dashboard, browser storage, notes exports or generated take metadata. You can also supply `GEMINI_API_KEY` in the server's environment; it takes precedence over the file. Keep the actual value out of chat and source control.

Start the local server and open its URL:

```sh
python3 tools/workshop_server.py
```

Open **[http://127.0.0.1:8765](http://127.0.0.1:8765)**. The server uses Python 3.10+ with no additional packages. Keep its terminal running. After adding or replacing the key, use **Refresh connection** in the workshop. A configured key means the server found a credential; Google verifies its access when you generate a song.

If startup reports that port 8765 is already in use, an existing workshop may already be running: open its URL rather than starting another instance. To restart a server running in your terminal, press **Ctrl+C** there, then run the same command again. `--port 8766` selects another port when you intentionally need one; use the URL printed by that instance.

Generated takes remain in the git-ignored `auditions/` folder, with their full submitted prompt, musical directions, original supplied lyrics and source, profile, arrangement, model and any returned lyrics. Refreshing saved work discovers recordings made by a separate batch process. Comparison decisions and their history save privately in `auditions/listening-reviews.json`; deleted takes are in `auditions/.trash/`. Back up the entire folder and the trial folders under `local/listening-tests/`. The browser notes export contains palette notes and edited directions, not comparison decisions or audio. If a request fails or times out, check the displayed error before deciding whether to generate again; a timed-out provider request might still have incurred a charge.

The **Baseline** collection contains the eleven regional targets. **Compare** contains only Reach sean-nós. **Deferred** preserves the earlier cultural profiles, finalists and idea bank for reading notes and hearing saved takes; new generations from those profiles are blocked in both the UI and server.

Each style has one canonical full-length arrangement: one singer playing a **plucked string instrument**, with **wordless vocables for Winterhold** and **instrumental plucked strings for Hjaalmarch**. The lute animation is a family: current provisional recipes include lute, cittern, kantele, kanklės and Persian setar, explicitly excluding bowed strings. Flute-family experiments use reedless woodwinds and exclude reed-driven sounds. The shared arrangement selector indicates which panel is available. Other instrumental/sung substitutions, ensembles, alternate moods and stylistic mixtures remain outside the active baseline and its bounded blind-family experiments. Casting and venue controls remain available to hold comparison conditions constant. Cyrodiil defaults to its monody repertoire; Solstheim defaults to the Dunmeri/Raven Rock Persian lament.

The workshop shows listening criteria and each profile's nearest neighbors and audible boundary. When listening, keep several unselected takes, blind-test the neighbors and all eleven together, repeat with new English lyrics where appropriate, and interleave fresh A/B/A requests. Record structure, enjoyment, confusions and failures separately. Engineering uses the current provisional recipes without waiting for these results. A deliberate source revision can admit a bounded experiment or replace a recipe, recording its rationale and any available listening evidence; a browser verdict never unlocks it. Sean-nós remains a separate challenger until an explicit decision replaces the Reach base.

Earlier edited directions and takes remain intact. New edits use a separate baseline revision, so an old mixed-style prompt cannot silently override the simplified default. **Earlier edited directions** shows the historical text. **Reset to recipe** resets only the current revision's edit. Notes exports include both prompt sets. **Show all saved arrangements** includes historical recordings, even when their arrangement is now deferred. New saved takes identify their recipe revision and audition stage; historical audio and prompts are not rewritten.

Every complete music prompt includes one named real-world reference, performer race, target region, actual sound sources and concrete musical features. Default music prompts fit within **1,000 characters excluding lyrics**; custom edits are flagged when longer and never truncated. **Copy music prompt**, **Copy lyrics**, and **Exact request preview** preserve their separate purposes. Supplied lyrics are used verbatim only by lyrical styles; Winterhold and Hjaalmarch omit them and reject inline `Lyrics:` blocks. Lyria is directed to write English words when an admitted lyrical style has no supplied text.

Provider failures show Google's HTTP status and a bounded diagnostic with credentials removed. Failed-job diagnostics are saved locally in `auditions/<job-id>/failure.json` and survive restarts; they do not contain the submitted prompt, key, or raw provider response. A billing/credit error is distinguished from quota limits and provider outages.

The server is intended for local use and binds to loopback only. It serves the dashboard and generated audio, not the repository or credential file. See Google's [music-generation guide](https://ai.google.dev/gemini-api/docs/music-generation) and [API key setup](https://ai.google.dev/gemini-api/docs/api-key) for provider configuration. Musical duration and arrangement instructions are prompts, not guarantees about the returned recording.

## Connect Saved SkyrimNet Lyrics

The shared **Shared lyrics** picker supplies identical original words to both lyrical audition panels. It reads the `bard_songs` table from explicitly configured SQLite databases in read-only mode. **Refresh lyrics** rereads those sources without invoking SkyrimNet's lyric generator or Google. Saved lyrics are optional. Choose **Let Lyria write English lyrics** to generate without a saved draft, or include your own `Lyrics:` block in the musical directions. Instrumental and wordless styles omit the selected draft. When using a saved draft, a changed or unavailable source blocks submission until refreshed; remove any `Lyrics:` block from musical directions to avoid competing lyric instructions. **Exact request preview** shows the combined request before generation; the selected words are appended without trimming or rewriting.

Machine-specific paths live in the git-ignored `local/skyrimnet-lyrics-source.json`. For a local installation, omit `ssh_host` and `python`. For a Windows installation reached through an existing SSH alias, use:

```json
{
  "ssh_host": "your-existing-ssh-alias",
  "python": "C:\\Path\\To\\python.exe",
  "label": "SkyrimNet saved lyrics",
  "databases": [
    {"path": "C:\\Path\\To\\SkyrimNet-save.db", "label": "Current profile"},
    {"path": "C:\\Path\\To\\Archived-save.db", "label": "Archived drafts"}
  ]
}
```

The Windows reader uses PowerShell and Python's standard-library SQLite support over SSH. It never changes the game databases, restores archived songs into the game, or downloads their audio. The source machine must be reachable when refreshing or starting a take that uses a saved draft. Source paths are explicit: update this private configuration when changing saves or profiles.

This workstation is connected to the experimental-profile database and the library archived before Solo Lute. At setup on October 8, 2026, the current database had no indexed songs and the archive contained nine drafts by Lurbuk, Karita, Lisette, Illdi and Viarmo. Archived drafts are labeled in the picker; their author is not an instruction about who sings the audition. No new song was generated to validate this connection.

## Open the Portable Listening Dashboard

Clone or download this repository, then open **[dashboard/index.html](dashboard/index.html)** in a browser. It is a self-contained HTML file; opening it needs no Python, Node, server, account or API key. GitHub displays HTML source, so open the downloaded file locally.

Compare two traditions under the same performer arrangement, edit and copy audition prompts, attach local audio, and save listening notes and verdicts. Music generation and saved takes require the local workshop server above. Neither mode modifies game files.

Notes and edited prompts save in that browser when storage is available. Use **Save & move notes** to export/import a JSON backup across computers. **Show backup text** and **Restore pasted backup** provide a text alternative. Audio attachments last only for the current page session and are not included in backups. Keep your original audio files.

Browser notes are scoped to the page's address. To move existing notes from the standalone file to the workshop, export them from the old page and import them at the local workshop URL.

## Design and Research

- [Regional music spec](docs/bard-regional-music-spec.md): the canonical target styles, prompt fragments, arrangement rules, implementation phases and unresolved questions. [SPEC.md](SPEC.md) is a local convenience link to this same file.
- [Reference listening notes](docs/skyrim-hold-music-listening-notes.md): playlists, listening cues and candidate regional revisions, with historical playlists and annotations for the adopted provisional baseline.
- [Musical traditions exploration](docs/bard-musical-traditions-exploration.md): all forty ideas, shortlist and independent reviews.
- [Bard roster and biography audit](docs/bard-roster-and-biography-audit.md): one versioned installation's performer inventory, with static-record versus runtime limitations.

Open this repository folder as an Obsidian vault and edit these same files in Obsidian or a code editor. The former `Home/Skyrim/hold_music` notes now link to the project vault; their originals were archived during the [13 October migration](docs/vault-migration-2026-10-13.md). There is one working copy of each document. Obsidian's local settings under `.obsidian/` are excluded from Git. Opening or connecting the vault on another machine remains a separate setup step.

The spec's YAML recipe blocks define the active palette. The listening notes and reviews supply evidence and candidates; they do not automatically change those recipes. Rebuild the generated dashboard and game-package palette after adopting a source change. Browser-edited directions remain audition drafts; only edits for the current baseline revision override its defaults. A rebuild preserves earlier prompt sets for reference. To adopt a draft, transfer its musical changes into the appropriate source recipe, increment `workshop_baseline.revision`, update the spec's ISO `Reconciled` date, then rebuild. Saved takes retain their original submitted prompts.

## Rebuild on macOS or Windows

Use Python 3.10 or later. On macOS, from the repository folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/rebuild_palette.py
open dashboard/index.html
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/rebuild_palette.py
Start-Process .\dashboard\index.html
```

This command reads the Markdown sources, regenerates the palette JSON and dashboard HTML, then synchronizes the local game-package recipes and location registry. Its editorial date comes from the spec's ISO `Reconciled` field unless `--date` is supplied. It does not install or deploy anything to another machine. Run `python tools/rebuild_palette.py --help` for options; an optional `--output` creates an additional generated HTML export, not another editable source. Node.js is optional: if present on PATH, the build also checks the embedded JavaScript's syntax. No paid generation request runs during a build. The individual `build_dashboard.py` and `build_game_adapter.py` tools remain available for separate build steps.

## Existing Game Prototype

The new **[Hold Music 0.2.0 game adapter](docs/game-adapter.md)** applies the nine
provisional Nord/region recipes to newly composed songs based on the bard's current
location. It preserves the separate-process repair from Solo Lute 0.1.1 and
retains SkyrimNet's own scheduling and playback. The native cache can still share
recordings between holds; this pilot does not enforce regional playback.

[prototype/solo_lute](prototype/solo_lute) preserves the eleven tracked files of Solo Lute 0.1.0 from source commit `1a47016c82f311ec52ca26b0380b9e0c7ca062c5`. It is the historical Windows/MO2 request adapter, with a 50% instrumental/vocal choice and an OpenRouter/Lyria route. Its installation/probe helpers retain MGO-specific assumptions. This frozen snapshot predates both the regional integration and the independent-process repair; use the current game adapter above.

Its October 7 offline and VFS checks are recorded in the [prototype verification](prototype/solo_lute/VERIFICATION.md). In-game playback and musical compliance still need testing. To rerun its standard-library tests from this repository:

```sh
python3 -m unittest discover -s prototype/solo_lute/tests -v
```

The snapshot excludes local settings, credentials, recorded request payloads, game assets and generated music. The prototype's temporary runtime configuration and backups may contain the existing provider key; keep those outside version control. No software license has been selected yet.

## Current Status

The [offline library executor](docs/executor.md) prepares instrumental, Winterhold wordless, and lyrical recordings with explicit job and spending caps. Lyrical planning uses the read-only [knowledge bridge](docs/knowledge-bridge.md). It defaults to a JSON dry run and does not install or play anything in-game.

The 20 October offline work adds durable paid-result recovery, an inspectable
[preparation and receipt proof](docs/offline-integration.md), reversible
[ownership reconciliation](docs/performance-ownership-design.md), and a
[portable package build](game_package/README.md#build). These paths can be
developed and tested with fixtures while listening remains optional.

The owned game package is installed on HALCYON. On October 15 its candidate scan crashed in PapyrusUtil VR's native dead filter while vanilla flute audio was playing. A targeted controller workaround was installed and passed 52 package tests and the recorded VFS checks; successful owned playback and interruption remain unverified. SkyrimNet's bard feature was disabled for that session and must remain inactive for the isolated owned-controller retest. The [RCA and retest](docs/sven-crash-2026-10-15.md) and [in-game test plan](docs/in-game-test-plan.md) supersede earlier assumptions that Sven is excluded from SkyrimNet playback. The [read-only preflight](docs/evidence.md#read-only-performance-preflight) helps check pilot inputs and conflicting configuration copies before the next session.

Dashboard comparison, filtering, saved notes, arrangement-specific prompt reductions, and JSON/text backup restoration were checked in a browser through a local HTTP preview. The six earlier Orsimer/Bosmer finalists are deferred research candidates: stylistic fidelity, specialist vocal technique, advanced animation support and ensemble synchronization are not validated by this dashboard.

The workshop's generation lifecycle, exact prompt retention, duplicate suppression, take playback/download, reload recovery and failure display were checked in a browser with synthetic audio. Offline server tests cover the Google request format, credential isolation, request validation, single-job behavior, response parsing, saved audio and redacted failure diagnostics. On October 8, 2026, a live Lyria 3.5 request for Resonant Name-Songs with lute and voice returned a 167-second song. Its audio, original prompt and returned lyrics were saved, and browser decoding/playback succeeded. That transport check does not establish musical compliance with the proposed style.

After updating, restart an already running workshop server to load the new generation policy, then refresh the page. Builds do not restart or deploy a running service.

Run the offline workshop checks with:

```sh
.venv/bin/python -m unittest discover -s tests -v
node tests/test_workshop_prompts.js
```
