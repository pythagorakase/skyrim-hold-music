# SkyrimNet beta 28 upgrade, 22 October 2026

**Installed and verified through MO2's VFS; first game load remains pending.**
The user authorized beta 28 before MGO RC5 because RC5 is delayed. This supersedes
the upgrade timing in the [15 October migration plan](stack-migration-rc5-beta27.md).
Its performer ownership, backup and runtime acceptance requirements still apply.
Musical listening validation remains independent of this upgrade.

## Installed target

- MGO root: `C:\MGO\Skyrim MGO 4.0 RC4.1`.
- Selected profile: `MGO EXP - SkyrimNet b26 + SeverActions 4.2`.
  Keep this exact name: the profile isolation and Hold Music mapper use it.
  The name is historical; its enabled SkyrimNet package is now beta 28.
- Enabled clean package: `mods/SkyrimNet - Experimental beta28`.
- Disabled, retained package: `mods/SkyrimNet - Experimental beta26-rc4`.
- Release: [vbeta28](https://github.com/MinLL/SkyrimNet-GamePlugin/releases/tag/vbeta28),
  published `2026-10-22T13:41:43Z`.
- Official archive: `skyrimnet-beta28.zip`, 263,199,213 bytes,
  SHA256 `f75aa984add2844c26e454ebb158180a8eb84979e4e4709e98a48a42a6a64ef7`,
  matching GitHub's asset digest.
- Installed DLL SHA256:
  `1eb7a62310361ef3456865875e41d7ebff165ca92de431b1b6858e616c10a5b7`.

All 2,352 archive files were extracted into a new mod folder and verified.
The old package was not overlaid: beta 28 replaces runtime libraries and hashed
dashboard assets, and removes old files including `ggml-opencl.dll` and
`SkyrimNet.pdb`. Existing SeverActions 4.2.0, OStimNet 2.4.1, IntelEngine 3.5.0,
PrismaUI VR Alpha 8 and other dependencies were retained. Package export names
alone do not establish add-on ABI compatibility.

The only intentional private configuration change was appending
`ui_host: prismaui` to Profile Data's `Dashboard.yaml`, preserving the existing
dashboard backend. The native bard master switch remains disabled. Existing
provider settings, custom content, biographies, audio and library state were
preserved. No regional recipe or audition was changed.

## Preservation and rollback

The private local audit root is
`C:\MGO\codex-investigations\20261022-skyrimnet-beta28`.
With Skyrim and MO2 closed, the preparation copied and verified these complete
trees against their sources:

- `backup/profile`: 930 files, 3,528,077,730 bytes, including saves/cosaves,
  isolated Documents/SKSE state, INIs and Hold Music runtime state.
- `backup/profile-data`: 5,375 files, 6,694,098,180 bytes, including SkyrimNet
  databases, any SQLite sidecars, private configuration, custom content and audio.
- `backup/mo2`: MO2 configuration and the profile isolation mapper.

The preparation also fingerprinted the old SkyrimNet package, shared Overwrite,
Hold Music mods, converted content, SeverActions, Steam manifests and VR executable.
Backups and raw local reports contain private state and are not committed.

Beta 28 adds SQL migrations `0028_embedding_producers`,
`0029_reembed_world_knowledge_with_titles`, `0030_bard_songs_imported` and
`0031_omnisight_manual_capture` relative to the installed beta 26 package. These
include embedding rebuilds and new song metadata. After a beta 28 game load,
switching only the DLL back is insufficient rollback. Close the game and MO2,
retain the post-upgrade state separately, then restore the pre-upgrade profile
and Profile Data together and select the retained beta 26 package. Do not merge
an old database into later gameplay state or discard new saves.

## File verification

The final read-only Python process was launched through the existing MO2 profile.
It observed `usvfs_x64.dll` loaded and checked **2,775 opened files** for both
expected bytes and physical destinations. All passed, covering the new package,
custom configuration/content, databases, Hold Music data and selected integration
binaries. Both obsolete package files were absent from the VFS.

The effective `BardSinging.yaml` is the Hold Music mapper's temporary file under
`profile/hold-music-runtime`, derived from Profile Data. The first probe expected
Profile Data directly and reported this one source/hash mismatch; it correctly
observed native bards disabled. The reviewed probe verifies the adapter's exact
three-field routing transformation, its loopback-only endpoint, the mapped `HM1`
prompt, the disabled bard switch and the retained PrismaUI backend. Its endpoint
token and private settings are not included in the report.

Audit receipts:

| Local file | SHA256 |
| --- | --- |
| `preparation-receipt.json` | `6cd8c65ab292e432bbaf53ebe78c7eee9aaf0590e5089b62e213b3a1cc33f394` |
| `activation-receipt.json` | `8ce9d8324fcf28a2b19f3ad6a1d6a8996ada7c39dd371f97267227517afee7e9` |
| `vfs-result-reviewed.json` | `c1f472f970e0ece4ea60967ad2c2bed7948f6d0fe242358b7d4f59d82e56ae63` |
| `final-preservation-review.json` | `b7b9051f95192f7a33c4ab2c2c10c6ea47a9d2b6dec4355d0546c76706f697b9` |

An independent final review verified both cold backups, the clean new package
and all protected content against their original hashes. Activation changes
were byte-exact. MO2 additionally refreshed the generated adapter `base_url`
and normalized `Lux - Vigilant Patch.esp` to `Lux - Vigilant patch.esp` in
`plugins.txt` and `loadorder.txt`; case-insensitive plugin identity, activation
and ordering were unchanged. Both Steam manifests retain their read-only locks
and original hashes.

Skyrim was not launched, so no beta 28 database migration, loaded-save behavior,
runtime plugin compatibility or playback result is claimed. No paid inference or
music generation was requested. The isolated SE lab remains pinned to its own
beta26-rc4 tier; its historical evidence has not been relabeled as beta 28.

## Bard changes and Hold Music implications

The [release notes](https://github.com/MinLL/SkyrimNet-GamePlugin/releases/tag/vbeta28)
describe fixes for NPC speech/history being cut off when a song starts and early
`/playsong` title requests arriving before chat initialization. The broader
conversation scheduler also changed, so dialogue interruption deserves a fresh
runtime check. The shipped `bard_song_lyrics.prompt` is byte-identical to beta 26
and beta 27; no automatic `HM1` prompt rewrite was needed.

Beta 27's composition switch remains separate from the master bard switch:
`bard_singing.generation.compose_enabled` can prevent new compositions while
allowing library playback. It does not establish Hold Music ownership. Preserve
`bard_singing.enabled: false` for the owned-controller checks.

The new [package ownership API](https://github.com/MinLL/SkyrimNet-GamePlugin/blob/vbeta28/Source/Scripts/SkyrimNetApi.psc)
is a useful future integration candidate. Owner-specific holds stop SkyrimNet's
managed package application and have persistence/cleanup events, but leave
ActorUtil overrides and listed packages alone. The documented contract does not
prove suppression of native bard audio or scheduling. Do not replace the bard
ownership gate with a package hold without a separate controlled test.

## Next runtime check

Use the same experimental profile and its copied saves. On first load, inspect
fresh logs for beta 28, completed database migrations and successful SkyrimNet,
SeverActions, OStimNet and IntelEngine initialization. Verify the dashboard uses
PrismaUI and native bards remain disabled. Then check ordinary speech and
interruption before the existing Sven owned-performance acceptance test.
Keep the original VR CTD and the separate SE lab results explicitly unresolved
until their relevant runtime checks pass.
