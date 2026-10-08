# Hold Music

Musical traditions for Skyrim's bards, with a local dashboard for comparing ideas and keeping listening notes.

The current design contains **six Orsimer/Bosmer finalists, nineteen existing cultural and regional profiles, and forty candidate ideas**. Strong predominant moods are intentional: build a distinct, coherent palette first, then develop its exceptions.

## Open the listening dashboard

Clone or download this repository, then open **[dashboard/index.html](dashboard/index.html)** in a browser. It is a self-contained HTML file; opening it needs no Python, Node, server, account or API key. GitHub displays HTML source, so open the downloaded file locally.

Compare two traditions under the same performer arrangement, edit and copy audition prompts, attach local audio, and save listening notes and verdicts. The page does not generate music or modify game files.

Notes and edited prompts save in that browser when storage is available. Use **Save & move notes** to export/import a JSON backup across computers. **Show backup text** and **Restore pasted backup** provide a text alternative. Audio attachments last only for the current page session and are not included in backups. Keep your original audio files.

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

Dashboard comparison, filtering, saved notes, arrangement-specific prompt reductions, and JSON/text backup restoration were checked in a browser through a local HTTP preview. The six finalists remain design candidates: generated audio, specialist vocal technique, advanced animation support and ensemble synchronization are not validated by this dashboard.

