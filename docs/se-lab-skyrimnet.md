# Disabled SkyrimNet SE lab preparation

`tools/se_lab_skyrimnet.py` reviews a concrete preparation recipe, checks a
first-boot installation, explicitly installs a separate disabled tier, and offers
a separately reviewed one-shot launch plus local metadata collection. It never
arms a scenario, contacts HTTP/MCP, or generates audio. The existing
baseline `tools/se_lab.py` is unchanged and continues to exclude SkyrimNet.

```powershell
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py plan
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py preflight
```

`--show-files` includes every proposed payload hash/source and observed snapshot.
`plan`, `preflight`, `install-plan`, `install-status` and recovery previews are
read-only. Installation, recovery and launch have separate explicit commands and
tokens. There is no root override. Tests substitute temporary roots
in process only.

## Separate instance and source contract

- Lab root: `C:\MGO\HoldMusic-SE-Lab`.
- Existing baseline instance: `MO2`, unchanged.
- Proposed second instance: `MO2-SkyrimNet`, with separate portable marker,
  mods, overwrite, profiles, settings and saves.
- Profile: `Hold Music SE Lab - SkyrimNet Disabled`.
- Shared game: the existing physical `Game` directory, SE 1.6.1170.0 and its
  baseline-pinned SKSE loader/runtime DLL. No Game payload is proposed.
- Config mod: `Hold Music SkyrimNet Disabled Config`, highest priority.
- Fixed loopback ports: web 18880, MCP 18889, future fake provider 18881.

A second profile in the existing instance would share overwrite. This design
uses an independent instance instead. Reusing shared Game is conditional on
preserving its files: the report binds every file's inventory metadata and the
baseline's native hashes. This is a drift guard, not an OS read-only mount or a
complete hash proof for every vanilla archive. SkyrimNet content and all native
plugin DLLs under physical `Game/Data/SKSE/Plugins` block the recipe. Future
installation must not copy anything into Game.

The recipe validates the baseline manifest and its declared source bytes, then
adds these pinned archives:

| Source | Mapping |
|---|---|
| Clean SkyrimNet beta26-rc4 ZIP | Complete Data-relative package |
| PrismaUI 1.5.1 ZIP | Strip `PrismaUI_1.5.1/` wrapper |
| Media Keys Fix 1.0.1 7z | Complete Data-relative package |
| Papyrus Extender 6.4.3 7z | FOMOD `Required/` plus `AE/` (1.6.1170+) |
| po3 Tweaks 1.15.1 7z | FOMOD `Required/` plus `AE/` (1.6.629+) |

Archive paths and release SHA256 pins are constants in
`hold_music/se_lab_skyrimnet.py`. ZIP members are read in memory; 7z members are
decoded through `tar -tvf`/`tar -xOf`, without filesystem extraction. The validated
regular-file listing and lengths divide a single decoded stream, bounded to
1 GiB. Every mapped member has
a source entry and proposed SHA256. Unsafe, duplicate-case or overlapping
member paths are rejected.

The seven approved immediate SKSE plugin DLL names are PapyrusUtil, MCMHelper,
po3_PapyrusExtender, po3_Tweaks, PrismaUI, MediaKeysFix and SkyrimNet. Bundled
private libraries remain part of the pinned archive payload. This inventory
does not establish successful native loading.

## Concrete disabled configuration

The recipe includes exact seed contents and hashes. JSON-format `.yaml` files
are valid YAML. The controls were read from the actual beta26-rc4 shipped
dashboard and native field strings:

- `SkyrimNet.yaml`: global AI, GameMaster, narration and all three decision
  selectors off; TTS `noop`; automatic base-content updates off.
- `STT.yaml`: backend `none`; no external key.
- `BardSinging.yaml`: disabled; backup provider `none`; cloud keys empty.
- `VastAI.yaml`: disabled, key empty.
- NPC/player reactions, background memory processing, DynamicBio,
  UniversalTranslator, OmniSight and Agents disabled.
- Web/MCP listeners explicitly use `127.0.0.1` and the tier ports.
- Providers and the legacy/default chat route point to the unused loopback fake
  endpoint, with an empty key. No fake server is started.
- `po3_Tweaks.ini` explicitly enables `[Fixes] Load EditorIDs`, as read by
  [the tagged v1.15.1 source](https://github.com/powerof3/po3-Tweaks/blob/v1.15.1/src/Settings.cpp#L67).
- The existing Papyrus lab control is disabled so native inspection does not
  automatically run a performance scenario.

These seeds are an initial contract, not an assertion that the native plugin
has accepted them. Read back generated schema/effective values in a separate
runtime step before enabling anything. The shipped UI uses these read routes:
`/config?api=categories`, `config-filenames`, `schemas`,
`schema&name=<id>`, and `get&name=<id>`. This tool calls none of them.

Beta26 can add provider records and preset/model variants on first load.
Its paid Jev decision model can inherit an OpenRouter key even when dialogue
uses another provider. Do not copy production keys, Auth.yaml, databases, songs
or account state into the lab. See the
[beta26 release notes](https://github.com/MinLL/SkyrimNet-GamePlugin/releases/tag/vbeta26-rc4).

## What preflight proves

`prepared_files_verified` requires the separate instance's exact payload,
ordered mod/plugin/loadorder lists, local saves/settings, fixed game/profile
and directory configuration, and disabled config winners. Extra mod/overwrite
files, auth files, databases, old saves, altered hashes, aliases and redirects
block it. Profiles contain their own Skyrim.ini and SkyrimPrefs.ini; optional
SkyrimCustom.ini is observed. The first-boot contract intentionally rejects
generated/changed configs and runtime data after a launch; a later runtime
collector must interpret those changes rather than weakening this check.

Preflight briefly binds all three IPv4 loopback ports simultaneously and then
closes the sockets, detecting current collisions. It does not listen, connect,
send HTTP, reserve them for a future launch, or identify an existing server.
Any future HTTP/MCP collector must bind the listening PID, executable path and
start time to the exact launched lab game. A port number alone proves nothing.

`clean_launch_environment()` is an allowlist helper for the explicit
launcher: OS paths survive, arbitrary credential/proxy variables do not, and
Steam app/game IDs are pinned to 489830. The exact inherited `USERNAME` is
required and passed under that canonical name: MO2 2.5.2's
[logging initializer](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/loglist.cpp#L371)
uses it without checking for a missing value. Missing, empty, NUL-containing or
case-ambiguous values fail before launch; no fallback identity is invented.
The helper does not mutate the caller's
environment. Reports disclose names of retained variables, never their values.
The launcher passes this environment explicitly to the separate MO2 executable.

The original inspection reports keep `can_apply` false. Installation/recovery
reviews can report `can_apply=true`, meaning only that their explicit file action
can be requested. Only a successful `launch-plan` reports `can_launch=true`.
Every operation keeps `native_verified`, `runtime_verified` and `egress_verified`
false. Tokens bind their distinct tier
and operation and cannot authorize the baseline runner.

## Explicit installation and interrupted preparation

```powershell
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py install-plan
# Use that exact install-plan review_token; an inspection token is rejected.
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py install --review-token '<token>'
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py install-status
```

Install accepts only an **absent** fixed `MO2-SkyrimNet` directory. An existing
empty directory is also rejected. It copies neither baseline application state
nor AppData, settings, account data, saves or credentials. Baseline manifest
entries naming auth/database/save state are rejected before staging, even if
their hashes match. Required baseline mod files remain hash-pinned copies.

Application support comes from the complete clean
[official MO2 2.5.2 distribution](https://github.com/ModOrganizer2/modorganizer/releases/tag/v2.5.2),
`C:\MGO\download\Mod.Organizer-2.5.2.7z`, SHA256
`e6376efd87fd5ddd95aee959405e8f067afa526ea6c2c0c5aa03c5108bf4a815`.
The local archive matched an independently hashed stream of that official asset.
Its `ModOrganizer.exe` must also match the baseline manifest. Fresh generated
portable-instance/profile files select only the lab Game, local settings/saves,
the ordered approved mods/plugins, and the exact disabled config seeds. No old
MO2 INI or private application directory is copied.

The install review binds source/archive bytes, every proposed file hash, exact
fresh config text, baseline/Game inventories, fixed paths and implementation
source hashes. Apply recomputes that review before writes and under a fixed
kernel writer lock. A strict Windows process check must establish that Skyrim,
SKSE loaders and MO2 are closed; unavailable or malformed process evidence
fails closed. The probe never terminates any process. Tests alone inject fake
process proofs.

The dedicated `.skyrimnet-tier-install` directory stores `writer.lock`, a durable
`journal.json` and a new `stage` directory. The journal precedes staging writes.
Files are exclusively created and flushed; aliases, changed staging ancestors,
unexpected files, private-state inputs and stale source hashes fail the action.
The complete staged inventory is checked, all inputs and process closure are
rechecked, and a journaled `publishing` intent precedes a same-filesystem
**no-replace** directory rename. Final checks precede `installed_disabled`.
Neither shared Game nor baseline MO2 is a destination. The lock coordinates this
tool's writers, not arbitrary editors. Metadata inventories and rechecks are
drift guards, not filesystem locks or a promise of atomicity against external
writers. Flush/rename behavior is tested for process death; sudden power-loss
durability is not claimed on Windows.

There is no automatic retry, cleanup, overwrite, resume or launch. A failed
attempt retains journal/staged/published evidence. Use status, then one of:

```powershell
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py recover --recovery-action retain_partial
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py recover --recovery-action retain_partial --apply --review-token '<recovery-token>'
# Or, only after a verified publish whose final journal checkpoint was interrupted:
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py recover --recovery-action acknowledge_published
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py recover --recovery-action acknowledge_published --apply --review-token '<recovery-token>'
```

`retain_partial` moves unpublished staging to `retained` without deleting any
bytes; it can also close a journal-only interruption. `acknowledge_published`
requires the exact complete frozen file/directory inventory, including absence
of extras, and performs no copying. It does not reload current sources, so source
archive removal or independent baseline edits do not strand published evidence.
Status reports protected changes since installation; recovery binds fresh
protected observations and verifies that it preserves them. Both actions require
fresh matching tokens and process closure. An interrupted recovery is reviewed
again. Foreign targets, malformed journals, aliases and unrecognized control
residue block automated actions and remain untouched for manual inspection.

This is a single retained transaction, not an upgrade manager. A completed or
retained attempt blocks new installation; the tool does not recycle its control
directory or uninstall a used instance. Successful file installation is still
not native/VFS/runtime/config-acceptance verification.

## Next runtime milestone

The current launch/collection checkpoint is tested with synthetic installations
and fake process observations. Those tests are not a real SkyrimNet first-boot
result. Do not use the failed requested-interruption baseline as acceptance.

## Explicit first boot and bounded local collection

`launch-plan` requires an exact completed installation and the unchanged strict
first-boot preflight. It also requires three explicit accepted baseline capture
references: `focused_complete`, `focused_interrupt`, and `ambient_entry`. Put
only references in a JSON file:

```json
{
  "focused_complete": {
    "capture": {"run_id": "<baseline run ID>", "capture_id": "<32 hex characters>"},
    "before": {"run_id": "<prior run ID>", "capture_id": "<prior capture ID>"}
  },
  "focused_interrupt": {
    "capture": {"run_id": "<baseline run ID>", "capture_id": "<32 hex characters>"},
    "before": {"run_id": "<prior run ID>", "capture_id": "<prior capture ID>"}
  },
  "ambient_entry": {
    "capture": {"run_id": "<baseline run ID>", "capture_id": "<32 hex characters>"},
    "before": {"run_id": "<prior run ID>", "capture_id": "<prior capture ID>"}
  }
}
```

The `before` reference is required when the run began with existing receipts;
omit it for an empty history. The prior capture's receipt and trace bytes must
match the original run's baseline hashes. All references resolve only beneath
the fixed lab `runs` directory. Paths in historical JSON cannot select files
for the tool to open.

Acceptance checks the fresh nonce, request timestamp, scenario, passed terminal
result, exactly one new receipt, unchanged prior receipt history, matching
start/stop trace, restored globals/hour and resolved controlled alias/faction
ownership. When admission evidence exists, its ticket must be released, drain
and resume observed, and all pending/fault fields clear. Ambient acceptance
requires the production inn-entry and scan assertions without injected entry
setup. Requested interruption requires a timely stop request and the causal
`stop_requested` trace guard; completion or an unrelated interruption fails.
Ambient duration must match the pinned source recording and the production
start trace; its unused focused-duration cache is not an ambient measurement.
Focused scenarios require their cached fixture duration to match the source.
The complete receipt identity must match the selected synthetic source fixture
and its projected digest. ASCII case differences in captured Papyrus display
strings are accepted without recomputing or normalizing the source digest.
Every baseline mod file copied into the second tier must match that accepted
run's original preflight hash. Controlled AI evidence does not establish natural
tavern behavior or general vanilla-scene quiescence.

```powershell
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py launch-plan --baseline-evidence '<references.json>'
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py launch --baseline-evidence '<references.json>' --review-token '<launch-plan token>' --timeout-seconds 30
& '<bundled Python 3.12 path>\python.exe' -B -X utf8 tools/se_lab_skyrimnet.py collect --run-id '<returned first-boot run ID>'
```

Launch rechecks the exact recipe, acceptance files, implementation, protected
Game/baseline inventories, process closure and clean environment under writer
locks. It stores durable intent in `.skyrimnet-tier-runtime` before `Popen`.
Generated MO2 INI paths use forward slashes. First-boot preflight requires the
exact generated UTF-8 bytes for both `ModOrganizer.ini` and the selected profile's
`settings.ini`. This fresh-instance contract rejects custom formatting, BOMs,
other encodings, aliases and even otherwise valid alternative Qt representations.
Additional parsed checks provide diagnostics; they cannot admit a noncanonical
file. It does not rewrite either file. Python's INI parser alone is insufficient:
Qt can silently discard unescaped Windows backslashes and their
following letters while returning `NoError`. A temporary-fixture regression
against the pinned MO2 Qt 6.7.1 parser can be enabled with
`HOLD_MUSIC_TEST_QT_ROOT` pointing to that MO2 distribution; it does not launch MO2
or change its settings. A configuration defect does not establish the exact
cause of an application crash without further evidence.
The fresh instance explicitly sets `game_edition=Steam`: MO2 2.5.2's
[instance setup](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/instancemanager.cpp#L162)
requires a selected edition when a game has multiple variants, and the
[Skyrim SE plugin](https://github.com/ModOrganizer2/modorganizer-game_skyrimSE/blob/82ac42f83f717b4884c8c551cb67b545e15177bc/src/gameskyrimse.cpp#L257)
lists Steam, GOG and Epic Games. This prevents the known edition-selection prompt
before command dispatch. The plugin source is a pinned public revision, not a
claim that its complete source was matched to the shipped DLL.
The seed leaves `first_start`, `version` and custom executables absent: the
[direct CLI run path](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/main.cpp#L121)
returns before the main window's tutorial and version-migration handling.
Only fixed `MO2-SkyrimNet/ModOrganizer.exe`, the disabled profile and fixed lab
SKSE loader are dispatched. The observation timeout is finite, 1–60 seconds;
it never kills a process or repeats a launch. Any retained attempt, including an
unknown spawn outcome, prevents automatic retry or reset.

Process evidence uses executable path, PID, parent PID and exact Windows creation
ticks. A bounded native observer is ready before dispatch and polls at a requested
20 ms interval, retaining short-lived parent identities. It uses process-only
Toolhelp snapshots, limited-query process handles, `QueryFullProcessImageNameW`
and `GetProcessTimes`. Run and result metadata name this backend
`native-filetime-v1` and report sample count and maximum observed sampling gap.
Launch and collection use the same full-precision ticks: FILETIME plus
504911232000000000, expressed as 100 ns intervals since year 1. Do not compare
these identities to rounded CIM creation timestamps.

Attribution requires the observed separate MO2 → SKSE loader → game ancestry.
Polling cannot guarantee observation of every transient process. A missing or
inaccessible identity, changed PID, worker failure or missing parent leaves the
launch **unattributed**. The tool does not relax that condition to a matching
executable path. Shared Documents logs remain outside this proof.

For a read-only identity recheck before any separately authorized cleanup,
import `hold_music.se_lab_skyrimnet` from this checkout and call
`_runtime_process_snapshot()`. Match the retained row's PID, parent PID, full
path and `created_ticks` exactly. The call reads process metadata only; it does
not stop anything. A missing row or mismatched identity provides no authority
to stop a replacement process. Neither this launcher nor collector provides a
kill command.

The collector is separate from strict first-boot preflight: generated config,
Auth or database files need not match pristine seeds after boot. It hashes local
files and reports only change counts/digests, private-file count, protected-path
drift and current process attribution. It exports no raw logs, configuration,
Auth/database contents, environment values, command-line inventory or arbitrary
generated filenames. A changing file tree or reused PID prevents a coherent
capture. Captures are new files under `.skyrimnet-tier-runtime/captures`; they
never replace runtime state or original baseline evidence. Local metadata is
not proof that a plugin initialized or accepted a configuration.

No HTTP/MCP client is implemented in this checkpoint. `native_verified`,
`effective_config_verified`, `vfs_verified`, `runtime_verified` and
`egress_verified` remain false even when launch ancestry is attributed. Native
loading, effective disabled settings, write destinations and listener ownership
still need a separate bounded smoke test before any enabled AI pathway.

The disabled configuration and absent credentials supply no provider billing
authority; they are not independent proof of zero network egress. Windows
Firewall rules scoped only to the full lab SkyrimSE.exe path are an optional
stronger control when elevation is available. Do not modify Steam, SkyrimVR,
other application rules or global firewall defaults. No firewall changes are
implemented here.

After baseline success, the explicit installer can prepare the exact recipe
and MO2 application support files. Then a dedicated runtime collector
can verify native loading, actual config acceptance/write destinations and
fresh, attributed MCP observations. SKSE Documents logs may be shared across
SE instances: runs must be serialized and existing evidence preserved. Only
after that should an enabled AI pathway use a deterministic loopback fake
provider. The private `/harness` API is not used: its referenced documentation
is absent from the public tag and release devkit.
