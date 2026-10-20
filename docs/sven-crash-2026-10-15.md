# Sven crash: native dead-filter mismatch and Hold Music fix

## Finding

The October 15 crash at 18:18:14 CDT was triggered by Hold Music's performer
scan, before it selected or played a recording. The installed PapyrusUtil VR
3.6.0.0b `ScanCellNPCs` dead-filter branch uses the non-VR virtual-function
index for `IsDead`. In Skyrim VR that slot belongs to `SetParentCell`, which
expects a cell pointer rather than a boolean. This explains the native crash
and supports a precise compatibility workaround in Hold Music.

This finding is specific to the installed DLL identified below. It is not a
claim that every PapyrusUtil version or function has this defect.

## Evidence

- Sven's 18:17:27.024 voice event references INFO `000960D7`, whose Skyrim.esm
  editor ID is `BardSongsFlute04`. The heard flute was a vanilla performance.
- SkyrimNet logged `BardSinging: Feature disabled in config` in this session.
  Competing SkyrimNet playback does not explain this crash.
- Hold Music's trace ends with `check_start`, 53.07 seconds after inn entry.
  Its next instruction was `ScanCellNPCs(Game.GetPlayer(), 2000.0, None, True)`.
  No candidate, selected slot, vanilla-stop or performance-start event exists.
- CrashLogger names `ScanCellNPCs`, shows its four-argument native signature,
  and reports the chain through PapyrusUtil, Luma's cell-change hook and the
  game. The fault reads `0xFFFFFF15` from an invalid `0xFFFFFF01` pointer.

Installed PapyrusUtil machine code at RVA `0x644E3` calls `[vtable+0x4C8]`,
slot `0x99`, after setting `DL=1`. It expects a boolean result. The
[published PapyrusUtil source](https://github.com/eeveelo/PapyrusUtil/blob/feac8e91dbd29c064e895c13f5e7a291a133590f/MiscUtil.cpp#L331-L348)
identifies that operation as its optional death check. The
[VR-aware function mapping](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/cd61f6620d564946e3262a96033406c0372c8d93/src/RE/T/TESObjectREFR.cpp#L1035-L1042)
places `SetParentCell` at VR slot `0x99` and `IsDead` at `0x9A`.

The installed SkyrimVR executable independently corroborates this: its
PlayerCharacter slot `0x99` targets RVA `0x6C11A0`, and this crash is at
`0x6C1222`, exactly `0x82` bytes into that function. Slot `0x9A` points to
`0x5EB800`, also used by Actor and Character.

Installed Luma Utility 1.7 hooks the correct VR cell-change slot and forwards
the bad argument unchanged. Its [matching-era source](https://github.com/Minizbot2012/LumaUtil/blob/3fcdb9c0acbb21559f0c92de97eaf7ad9d82e6b9/src/Hooks.cpp#L138-L154)
agrees with the disassembly. Removing Luma would not correct PapyrusUtil's
wrong dispatch. Neither Sven's audio nor the nearby NPC/cell patches are
implicated by this evidence.

## Fix and validation

The controller now calls `ScanCellNPCs(..., None, False)`. The complete native
scan was inspected: on this no-keyword route, `False` bypasses the defective
virtual call; distance filtering uses direct coordinate arithmetic.

Dead actors can now appear in the candidate array, but the existing
`Eligible()` check rejects them through the separate native Papyrus
`Actor.IsDead()` method before any scene, idle or sound change. The radius,
registry matching, ownership rules and name-only entries remain intact.
There are no ESP, quest-property or saved-state-schema changes.

Caprica compiled the controller successfully. Champollion produced complete
disassembly; its optional high-level decompilation reported an orphan-node
warning in the unchanged `Remember` function. Comparing executable
instructions shows exactly one semantic change: the scan argument switches
from `True` to `False`.

All **52 package tests pass**, including four new compiled-script regressions
for dead unregistered actors, dead owned actors preceding a living performer,
all-dead rooms, and null/unloaded candidates with name-only matching. The old
compiled controller fails the new unsafe-branch guard. These tests model
native APIs and do not replace in-game validation.

Only `Scripts/HM_Controller.pex` and `Scripts/Source/HM_Controller.psc` were
updated in the installed performance mod. The other 20 mod files, profile
lists, SkyrimNet bard setting and two recent ESS/SKSE pairs were hash-checked
unchanged. Runtime trace, receipts and the library were preserved. The original
installation receipt remains historical; a separate patch receipt records
this update.

The MO2-launched read probe confirmed USVFS injection and the expected physical
file destinations and hashes for all 19 game-data files, including the patched
controller, four recordings and preserved runtime JSON. No MCM settings override
was present. After reopening, MO2 changed only the spelling of one unrelated
plugin from `Lux - Vigilant patch.esp` to `Lux - Vigilant Patch.esp`; case-insensitive
plugin order and enablement are identical. All saves, bard settings and mod files
still matched their post-patch hashes. The correct experimental MO2 instance is
open and Skyrim is closed.

## Retest and rollback

Keep SkyrimNet's bard feature disabled for this owned-controller test. Load
the pre-crash save, then leave and re-enter the Sleeping Giant Inn with Sven
present. Loading a save inside the inn does not itself schedule a new song.
Wait 15-60 seconds; expect a lute performance using slot 3, about 159 seconds.
The trace should advance through candidate, slot selection, vanilla-stop and
performance-start, then a completion or interruption receipt. Audibility,
animation and native stability remain pending this test.

The two previous controller files and the saved evidence are backed up at
`C:\MGO\codex-backups\20261015-183707-hold-music-scan-fix`. With Skyrim closed,
restoring its `mod\Scripts` controller PEX and source reverts this patch;
that also restores the known crash-triggering branch. Saves are not modified
or restored by the patch.

## Local evidence

Raw reports, reproducible binary inspection, full hashes and instruction bytes:
`C:\MGO\codex-investigations\20261015-sven-holdmusic-ctd`.
Patch receipt: `local/game-package-scan-fix-20261015.json`.
MO2 read probe: `local/game-package-vfs-20261015.json`.

The installed PapyrusUtil SHA256 is
`fb5a856474f0e4fb6edb459dca8b6bbb1dc9098f17bc1c03ba107cbbbedd3ae8`.
The patched controller PEX SHA256 is
`d1e72c890a4662569a3635e5ead81aa60c9abce70c842c065984a85b33b019c8`.

The game's packed on-disk code prevents independent disassembly of its native
Papyrus `IsDead` wrapper here. The exact bad scan branch is established by the
installed DLL, executable vtable data, crash instruction and trace; successful
live playback with the workaround is still to be observed.
