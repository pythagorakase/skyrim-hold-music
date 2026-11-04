# Ownership diagnostic, 3 November 2026

**Installed and VFS-verified for the next VR run; runtime observation remains
pending.** The [Sven session](sven-session-2026-11-03.md) found a candidate but
failed its ownership comparison. The old trace normalized every failed
comparison to `skyrimnet`, including missing and unknown values. Save311
inspection found the expected saved file properties and correct library binding.

## Diagnostic contract

The existing `candidate` detail gains `diag_v=1` fields for the exact admission
value's classification before normalization, registry property classification
and length, row/count and owner-member presence/type. Unknown raw values and
arbitrary paths are not logged. `null_or_unresolved` does not assert that failed
native type checks prove JSON null. See the [field contract](evidence.md#versioned-ownership-diagnostic).

Admission remains `owner == "hold_music"`; unknown ownership remains denied.
The helper does not reload, repair, save or mutate the registry. No quest, ESP,
persistent variable or property changed. Instrumentation can affect native
string interning and timing: a disappearing failure under this build would be
an observation, not proof of a causal fix.

## Frozen VR artifact

This is a surgical patch of the installed 15 October VR controller/library,
built at `local/ownership-diagnostic-20261103/vr-diagnostic/build/package`.
Only the four approved PEX/PSC files were installed. That workspace also has
supporting compile/disassembly inputs; do not copy it wholesale into the mod.
The broader current-source SE controller remains a separate offline artifact.
The default `game_package/build` twelve-file manifest stayed unchanged.

Executable comparison found only the legacy controller's `OnUpdate` changed;
the library adds `OwnershipDiagnostic` while every existing function's
instructions remain unchanged. Persistent variable/property schemas match.

| Installed file | SHA256 |
| --- | --- |
| `Scripts/HM_Controller.pex` | `932b5486afafc1e9a319cd692265d653a4f089234872086b051ec59ac4e9c0dd` |
| `Scripts/HM_Library.pex` | `1983e3c13e580d296b1bff188172c71f11b58562d5a8b0bf095fa2f02ccf28d3` |
| `Scripts/Source/HM_Controller.psc` | `e5f3afe03177976b0619efc681e2e562b25f8f06047e59331448b442f713ef1c` |
| `Scripts/Source/HM_Library.psc` | `53efbc4dc3c265730cd7931e8eab1e203cb7902765d842f3756fb2d2f2484c7e` |

The final preparation receipt is
`local/ownership-diagnostic-20261103/reviewed-receipt-v2.json`, SHA256
`aba11f3416c464128bffe74c5d352ef2b43160990b472b7da69345551134b259`.
Installation used the earlier reviewed receipt with the same candidate hashes;
the second review adds another test without changing the artifact.

## Checks and preservation

Compiled PEX tests passed: 61 current-controller cases, nine current diagnostic
cases, nine VR diagnostic cases, 28 original-baseline cases and the same 28
legacy cases under the VR diagnostic. These use mocked natives and do not prove
engine playback. They cover denied unknown owners, preservation of the admission
read, bounded row search, redaction and case-insensitive member lookup with an
unresolved case-sensitive JSON path. Independent source review found no blocker.

With Skyrim and MO2 closed, the patch changed four files. The other 18 mod
files and eight protected paths (Save311/cosave, profile lists, bard configuration
and both Steam manifests) remained unchanged. Audio, registry, library, trace
and receipts were preserved. Private rollback files and deployment receipts are
under `local/checks/sven-diagnostic-deployment-20261103/`.

A read-only MO2-launched probe verified USVFS loaded and all eight expected
physical destinations/hashes: four changed files, registry, library, trace and
receipts. The effective native Bard Singing switch remained disabled. The probe
and helper exited; Skyrim was not launched and no provider request was made.

## Next observation and rollback

Use the same experimental profile, Hold Music enabled and native Bard Singing
disabled. Enter the Sleeping Giant Inn with Sven present; if loading inside,
leave and re-enter. One candidate check is enough to collect the new fields.
Inspect them before changing ownership or retrying playback.

For rollback, close Skyrim and MO2, confirm the four installed hashes above,
then restore the matching four files from the retained `backup` tree. These
prior scripts already contain the no-native-dead-filter workaround. Do not
restore game saves or change the registry to remove this diagnostic.
