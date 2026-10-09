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


## 0.2.1 offline verification — 9 October 2026

This change performed no in-game or paid check. The earlier 0.2.0 evidence
above is historical and does not verify 0.2.1 in Skyrim or MO2.

The offline tests cover:

- All fifteen recorded location descriptions and their winning resolution rules
  against the real registry; exact suffix/segment precedence, normalization,
  generic tokens, absent/unknown suffixes, invalid/ambiguous registry values,
  long hold names and no substring guessing.
- Full golden text for Whiterun vocal, Whiterun instrumental, Winterhold
  wordless and Pale instrumental; all ten regions in vocal, instrumental and
  explicit wordless modes for both genders, each below 1,000 direction
  characters with exactly one named Style/adaptation line. Instrumental clause
  selection, missing-field/lute fallback, voice/lyric omission and verbatim
  vocal lyrics are checked.
- The recorded SkyrimNet request shape for Mikael through the real loopback
  Adapter and fake upstream in both modes: Whiterun label, Style prefix, lyric
  inclusion/omission, marker removal, resolution logs and one context parse.
- HTTP wordless and excluded counters/logs, both Lurbuk choices, missing-marker
  502 without an upstream call, HTTPException/IncompleteRead error accounting
  and type-only diagnostics without retry, byte-identical fixture SSE forwarding,
  upstream errors and local route/origin restrictions. The upstream is an
  offline fixture; no music is generated.
- Conflict preservation, warning, baseline removal and successful next prepare,
  including a pending conflict recovered after restart; BOM preservation in
  overlay, baseline, source write-back and conflict files, with CRLF preserved.
- Health protocol version 0.2.0 plus build 0.2.1, helper ready-log build,
  independent helper reuse/shutdown, stable mode choices, unchanged Lurbuk legacy
  parity and byte equality of packaged canonical recipes/palette.
- The existing repository unittest suite and Node workshop prompt checks. The
  Windows-only embedded-interpreter regression is skipped on this macOS host.

Commands run unpiped:

```text
/Users/pythagor/hold_music/.venv/bin/python tools/build_game_adapter.py
/Users/pythagor/hold_music/.venv/bin/python -m unittest discover -s tests -v
node tests/test_workshop_prompts.js
```

Results: package synchronization succeeded; `Ran 146 tests in 10.020s`,
`OK (skipped=1)`. The Node check reported `Prompt contracts passed: 14820 valid
combinations; maximum 768/1000 characters
(bosmer_spinners_tales/drum_voice/orc/haafingar).` The game-specific maximum was
710 characters (Whiterun wordless, female). The Python run also emitted
non-failing SQLite connection ResourceWarnings in the existing suite.

### 0.2.1 live transport check and deployment — 9 October 2026

One paid synthetic request was sent through a fresh independent 0.2.1 helper on
HALCYON, isolated from the running game, using the committed Mikael fixture
(`The Bannered Mare, Hold: Whiterun`) in vocal mode: HTTP 200, completed SSE,
2,296,331 bytes of MP3 (about 95 seconds at 192 kbps), OpenRouter cost $0.0792,
service log `region=whiterun via=suffix-table mode=vocal lyrics_forwarded=True`,
helper build 0.2.1 reported alongside protocol version 0.2.0. The sample is kept
in the ignored `local/music-service-check-0.2.1/` folder and was not listened
to or judged for musical compliance.

The full suite also passed on Windows with Python 3.12 (147 tests) after the
workshop tests were made encoding- and file-lock-safe.

The 0.2.1 package files were then copied over the installed MO2 plugin and
content mod with MO2 open and Skyrim closed, and the 0.2.0 helper was stopped
through its stop file, so the next configured-profile launch starts the 0.2.1
helper. The MO2-resident plugin code (version string and in-process reconcile
recovery) takes effect only after MO2 restarts. Backup:
`C:\MGO\codex-backups\20261009-055334-hold-music-0.2.1-hotswap`. No in-game
composition or playback has been observed yet for either 0.2.0 or 0.2.1.
