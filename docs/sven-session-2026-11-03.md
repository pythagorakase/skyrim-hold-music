# Sven headset check, 3 November 2026

**Result: the candidate scan progressed beyond the previous crash site;
Hold Music playback and cleanup remain unverified.** The user heard successive
drum and lute instrumentals and confirmed that ordinary dialogue stopped both
audio and the performance animation. The controller trace shows that Hold Music
did not start those performances.

## Actual session and startup

The selected profile remains `MGO EXP - SkyrimNet b26 + SeverActions 4.2`.
An independent 2 November installation, retained in
`C:\MGO\codex-backups\20261102-skyrimnet-beta29.1-fc4c66b2`, enabled
`SkyrimNet - Experimental beta29.1-rc2` and disabled beta 28. The current session
reports build `0.29.1`; its installed DLL SHA256 matches that installation's
receipt: `5cc4a57b2bd8dc094d2d0774c71815b89c1962e8eae5e1ef7fd5749bd60413b8`.
Attribute these results to that version, rather than the earlier beta 28 upgrade.

The current isolated logs confirm native Bard Singing disabled at 21:17:49.411
local time, successful database migrations 27 through 31 at 21:18:19.889–.931,
and PrismaUI selected. SkyrimNet, SeverActionsNative, IntelEngine and OStimNet
loaded/initialized. No native bard generation or playback-start entry appeared
in the inspected interval through approximately 21:25:45. OStimNet reported the
optional OStimNavigator absent; no structured SkyrimNet error/critical entries
appeared in that interval.

## Human observations and controller evidence

The player described a vanilla-sounding drum piece, then an original-sounding
drum instrumental, followed by an original-sounding lute instrumental. Opening
ordinary dialogue with Sven stopped both the sound and instrument animation.
This verifies the observed interaction with that performance; its audio source
is not established by resemblance or novelty.

The enabled BA Bard Songs 1.3 mod/plugin supplies 87 loose XWM variants
(21 drum, 30 flute, 36 lute) and overrides 13 vanilla bard sound descriptors.
It provides a plausible source for novel-sounding vanilla performances. Static
inventory does not identify the exact heard segment or its live VFS winner.

The current trace advanced through fresh inn entry, `check_start`, a registered
Sven candidate, and `no_performer` (`scanned=15 matched=1`). Sven was eligible,
had a supported Whiterun region and passed the cooldown check, but failed the
Hold Music ownership gate. There is no `slot_chosen`, `performance_start`,
`performance_stop` or performance receipt. The installed controller PEX remains
the 15 October no-native-dead-filter workaround, SHA256
`d1e72c890a4662569a3635e5ead81aa60c9abce70c842c065984a85b33b019c8`.
This run supports progress beyond the old scan crash, without proving general
stability or owned performance lifecycle success.

## Ownership diagnostic needed

The installed registry gives Sven `owner: "hold_music"`. Its source and compiled
lookup logic read the expected owner path. However, the installed controller
rewrites every failed ownership comparison to the trace label `skyrimnet`,
including missing, empty and unknown values. The logged label therefore does
not prove that the registry returned that owner. Do not hardcode ownership or
rewrite the registry based on this trace.

The next bounded diagnostic should capture the runtime `RegistryFile` property,
matched row index, owner presence/type and a safe owner classification
(`hold_music`, `skyrimnet`, empty/missing, unknown) before normalization. Verify
the actual registry path through the VFS. Saved Auto-property values and native
JSON state remain possibilities, not established causes. Retain the fail-closed
ownership gate. Prepare and test the diagnostic outside the running installation
before requesting another headset attempt.

## Retained evidence

`local/evidence/20261103-sven-live-001/` contains the redacted collector report,
trace/receipt copies and `session-summary.json` with the user's observations.
It is a live read-only capture, not an atomic snapshot of a closed save. The
source log is the selected profile's `experimental-documents/SKSE/SkyrimNet.log`.
No running-game configuration or installed scripts were changed during review.

## Closed-session follow-up

After normal game exit, a second bundle at
`local/evidence/20261103-sven-closed-001/` retained the final eight-entry trace,
empty receipt history, filtered logs and a private hash-verified snapshot of
the three latest manual ESS/SKSE pairs and relevant logs (13 files,
63,814,335 bytes). The added trace entry is inn exit; no owned performance
start or stop appeared. Raw dialogue and prompt captures remain local.

The bundled ReSaver 6.0.467 parser structurally inspected a copy of Save311.
Its one `HM_Library` instance has the expected saved `RegistryFile`,
`LibraryFile`, `ReceiptsFile` and `TraceFile` values, and the saved
`HM_Controller.Library` reference points to that instance. Both serialized
instances match their script variable descriptors. Original save/cosave hashes
were verified unchanged. This rules against stale saved paths or a wrong saved
library reference in Save311, without proving the earlier native JSON cache or
physical file opened during the failed candidate call.

The saved-property report is
`local/checks/sven-saved-properties-20261103/inspection-report.json`, SHA256
`3afd240adfb1e1a462d149b82d0d1ca943f51d3bd7251d9f96a22285770272d6`.
The next diagnostic retains the ownership gate and captures the already-read
owner's classification, registry-property classification/length, matched row
and JSON owner-member type. Arbitrary paths/owner values are not logged.

The [diagnostic deployment](ownership-diagnostic-2026-11-03.md) is now installed
and VFS-verified for a future run. It changes only four files from this run's
legacy baseline; the ownership gate is unchanged and runtime evidence remains
pending. Do not mistake the diagnostic for an ownership or playback fix.
