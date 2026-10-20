# HM_Lab plugin builder

Builds an isolated normal `HM_Lab.esp` and `SEQ/HM_Lab.seq`. It does not compile
Papyrus, copy production files, launch Skyrim, or install anything.

```text
HM_LabPluginBuilder <package-directory> [<data-directory>]
```

Pass `game_package/data` explicitly when running a copied builder outside the
repository. When omitted, the builder searches ancestors of its executable and
working directory for `data/forms.json` or `game_package/data/forms.json`.

The plugin has only `HM_LabQuest`, local ID `0x800`, marked Start Game Enabled
and Run Once, with one `HM_LabHarness` script. Starting the quest initializes
that script; the harness decides which work requires an explicit test command.
There are no quest aliases, placed actors, world edits, or production overrides.

| Harness property | Papyrus type | Bound record |
| --- | --- | --- |
| Library | HM_Library | HoldMusic.esp:000800 |
| Config | HM_Config | HoldMusic.esp:000800 |
| HoldMusicQuest | Quest | HoldMusic.esp:000800 |
| HM_Enabled | GlobalVariable | HoldMusic.esp:000801 |
| HM_InstrumentalPercent | GlobalVariable | HoldMusic.esp:000802 |
| HM_SessionCap | GlobalVariable | HoldMusic.esp:000803 |
| HM_MinDelaySeconds | GlobalVariable | HoldMusic.esp:000804 |
| HM_MaxDelaySeconds | GlobalVariable | HoldMusic.esp:000805 |
| LocTypeInn | Keyword | Skyrim.esm record selected from forms.json |

The controller can be obtained from `HoldMusicQuest.GetAlias(0)`. The plugin
does not bind a Sven reference; the opt-in harness fixture resolves its
separately verified vanilla references. The installed `HM_LabHarness.pex` must
declare these properties with the listed names and types.

Use .NET 9 and cached Mutagen.Bethesda.Skyrim 0.51.5 dependencies. Copy this
project's authored inputs into a new build workspace before invoking `dotnet`;
keep `bin`, `obj`, package cache, CLI state, and output in that workspace.
`NuGet.Config` intentionally provides no network package sources. Restore with
`-p:NuGetAudit=false` and point `NUGET_PACKAGES` at a complete isolated copy of
the known dependency cache.

```powershell
dotnet restore <copied-project> --configfile <copied-NuGet.Config> -p:NuGetAudit=false
dotnet run --project <copied-project> --no-restore --configuration Release -- <lab-package> <game_package/data>
python game_package/lab/tests/test_lab_plugin.py --package <lab-package>
```

The builder reads its serialized plugin back with Mutagen and checks every
property, master, record count, quest identity and flag, and SEQ entry. The
Python test independently decodes ESP/VMAD/SEQ bytes. These are package checks;
they do not establish that Skyrim loaded or ran the harness.
