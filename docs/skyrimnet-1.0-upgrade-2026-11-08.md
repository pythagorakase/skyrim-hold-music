# SkyrimNet 1.0 development baseline, 8 November 2026

**Installed and verified through MO2's VFS. First game load remains pending.**
The user authorized using SkyrimNet 1.0 for ongoing development and accepted
the [vanilla standards policy](bard-regional-music-spec.md#existing-vanilla-songs-agreed-policy-8-november-2026).

The official release is titled [SkyrimNet 1.0.0](https://github.com/MinLL/SkyrimNet-GamePlugin/releases/tag/v1.0.0-rc1),
with exact tag `v1.0.0-rc1`, published `2026-11-08T05:37:24Z`. The live release API
reported `prerelease: false`. Use the exact tag in evidence rather than assuming
an unsuffixed build.

## Installed target

- MGO root: `C:\MGO\Skyrim MGO 4.0 RC4.1`.
- Profile: `MGO EXP - SkyrimNet b26 + SeverActions 4.2`; retain the historical
  name because the isolation and Hold Music mappers match it exactly.
- Enabled: `SkyrimNet - Experimental 1.0.0-rc1`.
- Retained disabled: `SkyrimNet - Experimental beta29.1-rc2`, with older beta
  packages still retained at their previous disabled positions.
- Archive: 271,852,726 bytes, 2,419 files, SHA256
  `cdf798ddef0895aa5306e23ccc1a21a0446ec46f77825432eef5aea28c4d67cb`.
- Installed `SkyrimNet.dll` SHA256
  `e94ffc3ed071d427b5582fb5906192c731c549fab2c38662313ff70fa291c0bc`.

The clean package replaces the prior package at the same priority. No
intentional config edit was required. The existing PrismaUI VR setup,
SeverActions, IntelEngine, OStimNet and Hold Music layers were preserved.
The [tagged requirements](https://github.com/MinLL/SkyrimNet-GamePlugin/blob/v1.0.0-rc1/README.md#requirements)
are unchanged from the prior target. The native DLL keeps all 118 export names,
Public API 14 and package API 1. The additional static import, Windows
`DWrite.dll`, is present. These checks reduce static compatibility uncertainty;
loaded-save and add-on initialization still need a fresh game run.

## Preservation and verification

With game and MO2 closed, the private audit at
`C:\MGO\codex-investigations\20261108-skyrimnet-1.0` verified complete cold
copies of the selected profile (940 files, 3,600,288,842 bytes) and Profile Data
(5,383 files, 6,693,270,603 bytes), plus MO2 configuration/mapper inputs. These
include the current saves/cosaves and databases, private settings, and retained
audio. The older 2 November rollback snapshot predates the November 3 session.

MO2 launched a read-only payload which verified **2,868** file hashes and
physical sources, including the release, custom layers, and all four installed
[ownership diagnostic](ownership-diagnostic-2026-11-03.md) files. It observed
82 obsolete prior UI assets plus two older retired binary paths absent, native
Bard Singing disabled, PrismaUI selected, and the exact three-field Hold Music
loopback overlay and mapped `HM1` prompt. No game or paid provider request was
launched. Steam manifests remain locked and unchanged.

| Local receipt | SHA256 |
| --- | --- |
| `preparation-receipt.json` | `3f7933ae009ca02d33d4a43b4c564281e637b342e9c5f46a717f73210c7c8cda` |
| `activation-receipt.json` | `fa443095198c1797a81fc3df1824c8ce43be80585b0901ecb25a9b892493f079` |
| `vfs-result-reviewed.json` | `63fdd58376d34acf68598accf2e7e921a402584da40826dba8eb72c930646fc0` |
| `final-preservation-review.json` | `b932aa2949705d88b6ffee6694a92b6f3cdc8c87ef59ef604f4b3d71a4c21cbb` |

Independent verification matched both cold backups, all 5,383 Profile Data
files, the retained old package, the clean new package and the protected
roots/files to their recorded hashes. The selected profile changed only its
exact modlist swap and generated `hold-music-runtime/BardSinging.yaml` overlay.
No game or MO2 process remained after the probe.

The ESP, base content manifest, bard lyric prompt, public API source and all
32 SQL files are byte-identical to beta29.1-rc2. No new migration is bundled.
This does not promise that a later game session leaves saves or databases
unchanged. For rollback before a game load, close game/MO2 and restore the
retained profile modlist. After a game load, preserve newer state separately
and restore the matching cold profile and Profile Data together if needed.
Do not discard new saves or merge mismatched databases.

## Development on 1.0

The release replaces the older bard request with separate `PLAYBARDSONG`,
`COMPOSEBARDSONG` and `STOPBARDSONG` actions. The master bard switch and separate
composition control remain present; playing a known native song can still
re-download uncached audio. No matching custom action overrides required
migration in the active Profile Data. The evidence collector now retains the
new action IDs and the legacy `REQUESTBARDSONG` ID without relaxing its private
dialogue filter. Five collector tests and a fixture with both action formats
passed. An action log entry alone is not playback proof.

Keep native SkyrimNet bards disabled for the Hold Music ownership check. The
next live test is a normal NPC exchange to verify startup and one fresh Sven
candidate check to collect `diag_v=1`. The 3 November VR result remains evidence
for beta29.1-rc2 only. The separate SE lab remains pinned to beta26-rc4 and needs
a separately reviewed 1.0 tier before any native compatibility claims there.

The [vanilla standards integration note](vanilla-standards-integration.md)
maps the first original-song test to its existing vanilla request path. Preserve
that authored path and its conditions, then design an explicit handoff around
observed scene start/stop behavior. Hold Music remains authoritative for its
prepared recordings and regional selection; native song action changes do not
implement a vanilla-scene handoff or establish exclusive playback ownership.
