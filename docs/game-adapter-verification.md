# Hold Music 0.2.0 verification — 8 October 2026

Target: SkyrimNet beta26-rc4, MO2 2.5.2, profile
`MGO EXP - SkyrimNet b26 + SeverActions 4.2` on HALCYON.

## Passed

- 105 offline tests across the existing workshop/repertoire and new regional
  adapter. Coverage includes every regional recipe, instrumental/wordless lyric
  omission, Lurbuk's exact legacy treatment, missing or misplaced metadata,
  known hold suffixes, ambiguous names, request streaming, config reconciliation,
  provider failures without retries, and independent helper lifetime.
- Two existing workshop permission assertions were made POSIX-only. Windows
  `chmod` does not implement POSIX 0600/0700; all platforms retain the tests for
  key isolation, atomic saves and redacted diagnostics. No workshop behavior changed.
- SkyrimNet's native content validator accepted the assembled settings and
  lyric prompt: zero errors, warnings, unresolved references or shadows.
- Four live synthetic lyric calls used both models in the current default
  rotation: `openai/gpt-5.6-terra` and `google/gemma-4-31b-it`. Each preserved the
  exact bard/location marker for Delacourt and Lurbuk. Adapter transformations
  selected Falkreath and the Lurbuk exemption respectively, without forwarding
  the routing marker to the music provider. Synthetic context only; no personal
  memories were submitted for these checks.
- A new independent Hold Music helper generated a real Falkreath instrumental
  via OpenRouter/Lyria: HTTP 200, completed SSE, 3,898,160 bytes of MP3, zero
  service errors, 23.58 seconds including helper shutdown. OpenRouter reported
  $0.0792. The helper log confirms Falkreath/instrumental and no lyrics forwarded.
  This isolated check did not alter the running game or its cache.
- Actual MO2 launch/VFS probe: new content root enumerated, context template
  enumerated and byte-identical to its source, temporary route visible, healthy
  independent helper, retired Solo Lute content absent. SkyrimNet's native
  validator was also launched inside that VFS and successfully rendered both
  content files. Helper shutdown was observed after MO2 exited.
- Disabling Hold Music in the profile restored the source OpenRouter route and
  removed the context template/content root from the VFS. Hold Music was then
  re-enabled. Solo Lute remains installed but disabled in this profile.
- Source `BardSinging.yaml` remained byte-identical throughout, SHA-256:
  `9ad37e1bcb27c70f795676e854c7de054b476c7f273b18d63b95d631af5a33d4`.
  The installation made no ESP, Papyrus, game executable or database changes.

The English location registry contains 4,213 exact names, with 35 ambiguous
names using Nord fallback. It is secondary to SkyrimNet's explicit hold suffix;
native logs supplied examples including `Hold: Falkreath`, `Hold: Haafingar` and
`Hold: Dawnstar`. Unknown outdoor descriptions do not guess a hold.

## Remaining gameplay check

The complete SkyrimNet chain still needs a fresh in-game composition: template
selection, native Style parsing, music request, cache insertion and audible
playback. Offline rendering and synthetic model/transport checks do not prove
that chain, nor the musical compliance of the recording. No claim of hearing
or judging the sample is made.

SkyrimNet's existing playback cache can share songs across holds and with Lurbuk.
This release regionalizes new compositions; it does not isolate playback pools.
The current marker is copied by the lyric model and may occasionally be omitted;
malformed requests fail before a paid music generation and leave a diagnostic.

Evidence is retained in ignored `local/`: `test-results.txt`,
`validation-final.json`, `lyric-bridge-check/result.json`,
`music-service-check/result.json`, `vfs-probe.json`, `vfs-native-validation.json`
and `vfs-disabled.json`. Installation backup:
`C:\MGO\codex-backups\20261008-213059-hold-music`.
