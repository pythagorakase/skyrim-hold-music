# Hold Music

Musical traditions for Skyrim's bards, with a local workshop for generating songs, comparing ideas and keeping listening notes.

The current design contains **six Orsimer/Bosmer finalists, nineteen existing cultural and regional profiles, and forty candidate ideas**. Strong predominant moods are intentional: build a distinct, coherent palette first, then develop its exceptions.

## Run the music workshop

The workshop calls Google's Gemini API directly with **`lyria-3.5`**. Choose two musical traditions, select their shared performer arrangement and optionally a saved SkyrimNet lyric draft, edit the musical directions, then click **Generate song**. Each generation is a paid API request using your Google project's billing and quota. Requests run one at a time; the workshop never retries a generation automatically.

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

Generated takes remain in the git-ignored `auditions/` folder, with their full submitted prompt, musical directions, original supplied lyrics and source, profile, arrangement, model and any returned lyrics. The workshop restores this take library after a restart. Play and download takes beside their matching tradition and arrangement. Back up `auditions/` separately from listening notes. If a request fails or times out, check the displayed error before deciding whether to generate again; a timed-out provider request might still have incurred a charge.

Every complete request specifies the performer’s race and target region, including requests using saved custom musical directions. **Performer race** can be selected separately in A and B; **Target region** can use each recipe’s default or one shared location. Regional recipes default to their named hold, Cyrodiil vernacular defaults to Cyrodiil, and other cultural recipes default to Skyrim without a named settlement. Sung Orc auditions include provisional vocal casting. Newly generated lyrics follow the performer and setting; supplied lyrics retain their words. Musical directions stay editable. **Copy music prompt** copies the complete musical prompt without lyrics; **Copy lyrics** copies supplied lyrics separately. **Exact request preview** and **Copy complete request** retain the full Google API request; saved takes keep their original text.

The arrangement selector adapts each recipe to **plucked strings + voice**, **plucked strings instrumental**, **flute instrumental**, **alternating flute + voice**, **drum + voice**, or **voice alone** where a musical reduction is defined. The actual plucked instrument comes from the recipe: selected ballads/dances use cittern, Redguard uses oud, Spinner’s tales uses biwa, Khajiit uses sitar, and the revised Argonian study uses a kacapi plucked zither. Other recipes retain lute; no bowed strings are offered. **Available arrangements & omissions** explains the choices for each panel. Drum solos are available for Seven-Step, Leaping tales, Redguard cycles, Rift jigs and Khajiit tabla. The Khajiit percussion prompt uses Hindustani tabla solo, with a 16-beat teental cycle, sliding bayan bass, crisp dayan strokes, accelerating variations and a threefold tihai. One performer plays the tabla pair without vocals or melodic accompaniment. Close-Circle also offers its three-voice study.

Khajiit and Argonian recipes and performers are **instrumental only** while convincing beastfolk vocals remain unresolved. The Argonian reference now combines Sundanese kacapi suling with repeating cells from the earlier kotekan sketch. **Resonant Name-Songs · throat singing** makes the existing khöömei finalist explicit without changing its ID. **Show all saved arrangements** exposes earlier takes, including vocal beastfolk auditions. Old edited directions remain stored; **Reset to recipe** adopts the new instrument treatment. Historical `lute`/`lute_voice` storage keys now represent the plucked-string family. Unsupported combinations are rejected before any provider request, and instrumental directions cannot contain a `Lyrics:` block.

Every recipe’s complete music prompt leads with a named real-world musical reference and a short adaptation label. Default music prompts fit within 1,000 characters, excluding lyrics; a live counter flags longer custom edits without truncating them. **Reset to recipe** adopts compact defaults while saved edits remain intact. Inline `Lyrics:` blocks are excluded from music-only copying and counting and can be copied separately. Musical fingerprints, instruments and performer count remain explicit; drum-only versions use rhythmic features only. Newly selected references for fictional forms are provisional audition influences.

Provider failures show Google's HTTP status and a bounded diagnostic with credentials removed. Failed-job diagnostics are saved locally in `auditions/<job-id>/failure.json` and survive restarts; they do not contain the submitted prompt, key, or raw provider response. A billing/credit error is distinguished from quota limits and provider outages.

The server is intended for local use and binds to loopback only. It serves the dashboard and generated audio, not the repository or credential file. See Google's [music-generation guide](https://ai.google.dev/gemini-api/docs/music-generation) and [API key setup](https://ai.google.dev/gemini-api/docs/api-key) for provider configuration. Musical duration and arrangement instructions are prompts, not guarantees about the returned recording.

## Connect saved SkyrimNet lyrics

The shared **Shared lyrics** picker supplies identical original words to both audition panels. It reads the `bard_songs` table from explicitly configured SQLite databases in read-only mode. **Refresh lyrics** rereads those sources without invoking SkyrimNet's lyric generator or Google. Saved lyrics are optional. Choose **Let Lyria write lyrics** to generate without a saved draft, or include your own `Lyrics:` block in the musical directions. Instrumentals omit the selected draft. When using a saved draft, a changed or unavailable source blocks submission until refreshed; remove any `Lyrics:` block from musical directions to avoid competing lyric instructions. **Exact request preview** shows the combined request before generation; the selected words are appended without trimming or rewriting.

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

## Open the portable listening dashboard

Clone or download this repository, then open **[dashboard/index.html](dashboard/index.html)** in a browser. It is a self-contained HTML file; opening it needs no Python, Node, server, account or API key. GitHub displays HTML source, so open the downloaded file locally.

Compare two traditions under the same performer arrangement, edit and copy audition prompts, attach local audio, and save listening notes and verdicts. Music generation and saved takes require the local workshop server above. Neither mode modifies game files.

Notes and edited prompts save in that browser when storage is available. Use **Save & move notes** to export/import a JSON backup across computers. **Show backup text** and **Restore pasted backup** provide a text alternative. Audio attachments last only for the current page session and are not included in backups. Keep your original audio files.

Browser notes are scoped to the page's address. To move existing notes from the standalone file to the workshop, export them from the old page and import them at the local workshop URL.

## Design and research

- [Regional music spec](docs/bard-regional-music-spec.md): proposed repertoire, arrangement rules, implementation phases and unresolved questions.
- [Musical traditions exploration](docs/bard-musical-traditions-exploration.md): all forty ideas, shortlist and independent reviews.
- [Bard roster and biography audit](docs/bard-roster-and-biography-audit.md): one versioned installation's performer inventory, with static-record versus runtime limitations.

The dashboard build reads the documents in this repository. The existing Obsidian documents are separate copies; changes do not synchronize automatically in either direction. Copy updated source documents across when switching where you edit. The reviews are historical inputs, and the current spec takes precedence over their earlier candidate fragments.

## Rebuild on macOS or Windows

Use Python 3.10 or later. On macOS, from the repository folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/build_dashboard.py
open dashboard/index.html
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/build_dashboard.py
Start-Process .\dashboard\index.html
```

The build reads the Markdown sources, regenerates the palette data and embeds it in the HTML template. Run `python tools/build_dashboard.py --help` for options, including an explicit additional `--output` destination for an Obsidian copy. Node.js is optional: if present on PATH, the build also checks the embedded JavaScript's syntax. No paid generation request runs during a build.

## Existing game prototype

The new **[Hold Music 0.2.0 game adapter](docs/game-adapter.md)** applies the nine
approved Nord/region recipes to newly composed songs based on the bard's current
location. It preserves the separate-process repair from Solo Lute 0.1.1 and
retains SkyrimNet's own scheduling and playback. The native cache can still share
recordings between holds; this pilot does not enforce regional playback.

[prototype/solo_lute](prototype/solo_lute) preserves the eleven tracked files of Solo Lute 0.1.0 from source commit `1a47016c82f311ec52ca26b0380b9e0c7ca062c5`. It is the historical Windows/MO2 request adapter, with a 50% instrumental/vocal choice and an OpenRouter/Lyria route. Its installation/probe helpers retain MGO-specific assumptions. This frozen snapshot predates both the regional integration and the independent-process repair; use the current game adapter above.

Its October 7 offline and VFS checks are recorded in the [prototype verification](prototype/solo_lute/VERIFICATION.md). In-game playback and musical compliance still need testing. To rerun its standard-library tests from this repository:

```sh
python3 -m unittest discover -s prototype/solo_lute/tests -v
```

The snapshot excludes local settings, credentials, recorded request payloads, game assets and generated music. The prototype's temporary runtime configuration and backups may contain the existing provider key; keep those outside version control. No software license has been selected yet.

## Current status

The [offline library executor](docs/executor.md) prepares instrumental and Winterhold wordless recordings with explicit job and spending caps. It defaults to a JSON dry run; lyrical work awaits the knowledge bridge, and this tool neither installs nor plays anything in-game.

Dashboard comparison, filtering, saved notes, arrangement-specific prompt reductions, and JSON/text backup restoration were checked in a browser through a local HTTP preview. The six finalists remain design candidates: stylistic fidelity, specialist vocal technique, advanced animation support and ensemble synchronization are not validated by this dashboard.

The workshop's generation lifecycle, exact prompt retention, duplicate suppression, take playback/download, reload recovery and failure display were checked in a browser with synthetic audio. Offline server tests cover the Google request format, credential isolation, request validation, single-job behavior, response parsing, saved audio and redacted failure diagnostics. On October 8, 2026, a live Lyria 3.5 request for Resonant Name-Songs with lute and voice returned a 167-second song. Its audio, original prompt and returned lyrics were saved, and browser decoding/playback succeeded. That transport check does not establish musical compliance with the proposed style.

Run the offline workshop checks with:

```sh
.venv/bin/python -m unittest discover -s tests -v
node tests/test_workshop_prompts.js
```
