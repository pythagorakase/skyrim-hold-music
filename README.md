# Hold Music

Musical traditions for Skyrim's bards, with a local workshop for generating songs, comparing ideas and keeping listening notes.

The current design contains **six Orsimer/Bosmer finalists, nineteen existing cultural and regional profiles, and forty candidate ideas**. Strong predominant moods are intentional: build a distinct, coherent palette first, then develop its exceptions.

## Run the music workshop

The workshop calls Google's Gemini API directly with **`lyria-3.5`**. Choose two musical traditions, select their shared performer arrangement, edit an audition prompt and click **Generate song**. Each generation is a paid API request using your Google project's billing and quota. Requests run one at a time; the workshop never retries a generation automatically.

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

Generated takes remain in the git-ignored `auditions/` folder, with their original prompt, profile, arrangement, model and any returned lyrics. The workshop restores this take library after a restart. Play and download takes beside their matching tradition and arrangement. Back up `auditions/` separately from listening notes. If a request fails or times out, check the displayed error before deciding whether to generate again; a timed-out provider request might still have incurred a charge.

Fresh audition recipes include the Skyrim setting. Sung Orc finalist recipes also specify provisional vocal casting: a mature, full-bodied voice with chest resonance and audible grain. The full prompt remains editable. Existing custom edits are preserved; use **Reset to recipe** to adopt revised defaults. Saved takes retain their original prompts for comparison.

Provider failures show Google's HTTP status and a bounded diagnostic with credentials removed. Failed-job diagnostics are saved locally in `auditions/<job-id>/failure.json` and survive restarts; they do not contain the submitted prompt, key, or raw provider response. A billing/credit error is distinguished from quota limits and provider outages.

The server is intended for local use and binds to loopback only. It serves the dashboard and generated audio, not the repository or credential file. See Google's [music-generation guide](https://ai.google.dev/gemini-api/docs/music-generation) and [API key setup](https://ai.google.dev/gemini-api/docs/api-key) for provider configuration. Musical duration and arrangement instructions are prompts, not guarantees about the returned recording.

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

[prototype/solo_lute](prototype/solo_lute) preserves the eleven tracked files of Solo Lute 0.1.0 from source commit `1a47016c82f311ec52ca26b0380b9e0c7ca062c5`. It is the existing Windows/MO2 request adapter, with a 50% instrumental/vocal choice and an OpenRouter/Lyria route. Its installation/probe helpers retain MGO-specific assumptions. It is not a Mac game mod, and the regional dashboard profiles are not connected to its live request path yet.

Its October 7 offline and VFS checks are recorded in the [prototype verification](prototype/solo_lute/VERIFICATION.md). In-game playback and musical compliance still need testing. To rerun its standard-library tests from this repository:

```sh
python3 -m unittest discover -s prototype/solo_lute/tests -v
```

The snapshot excludes local settings, credentials, recorded request payloads, game assets and generated music. The prototype's temporary runtime configuration and backups may contain the existing provider key; keep those outside version control. No software license has been selected yet.

## Current status

Dashboard comparison, filtering, saved notes, arrangement-specific prompt reductions, and JSON/text backup restoration were checked in a browser through a local HTTP preview. The six finalists remain design candidates: stylistic fidelity, specialist vocal technique, advanced animation support and ensemble synchronization are not validated by this dashboard.

The workshop's generation lifecycle, exact prompt retention, duplicate suppression, take playback/download, reload recovery and failure display were checked in a browser with synthetic audio. Offline server tests cover the Google request format, credential isolation, request validation, single-job behavior, response parsing, saved audio and redacted failure diagnostics. On October 8, 2026, a live Lyria 3.5 request for Resonant Name-Songs with lute and voice returned a 167-second song. Its audio, original prompt and returned lyrics were saved, and browser decoding/playback succeeded. That transport check does not establish musical compliance with the proposed style.

Run the offline workshop checks with:

```sh
python3 -m unittest discover -s tests -v
```
