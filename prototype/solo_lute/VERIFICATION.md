# Prototype verification - 7 October 2026

Target: SkyrimNet beta26-rc4, MO2 2.5.2, the isolated MGO experimental profile.

## Passed

- 17 standard-library tests cover both music branches, preserved lyric text,
  unexpected request formats, retry-stable random selection, forced 0/100 modes,
  approximate 50/50 distribution, config overlays, dashboard edit recovery,
  conflicting edits, streamed audio pass-through, provider errors, and rejected
  browser-originated requests.
- The transformations accept an actual recorded SkyrimNet Lyria request. The
  vocal output retains its exact lyrics; the instrumental output includes neither
  the lyrics nor the vocal prefix. This replay did not contact the provider.
- SkyrimNet's beta26 content-validate tool reports no errors or warnings for the
  content/settings package.
- The real MO2 embedded Python runtime loads the companion and starts the adapter.
- A Python probe launched through MO2 sees the local provider route, the Lyria
  model ID, and the external content package. Its loopback health request succeeds.
- With the content mod unchecked, that same probe sees the original OpenRouter
  configuration and no Solo Lute content layer. The content mod was re-enabled
  after the rollback test.
- The original BardSinging.yaml remains byte-for-byte unchanged after both probes.
- The adapter's narrow scalar reader agrees with PyYAML on the existing music
  credential, without printing or copying it into project files.

Detailed local reports are in the ignored `local/` directory. Temporary config
copies containing the existing credential remain under the MO2 profile, outside
the repository and distributable archive.

## Still requires an in-game test

The game was not started and no paid music was generated. The selected local
transport uses SkyrimNet's existing OtherMusicInterface; its first actual Lyria
response through this transport and the audible performance still need checking.
The original adapter is untouched. Offline fixtures confirm stream handling,
but cannot guarantee that Lyria will obey instrumentation and vocal instructions.

SkyrimNet continues to create/store lyric drafts before the adapter's coin flip.
The adapter only removes them from instrumental music requests; it does not edit
the catalog or existing cached audio.

## Design references

- [SkyrimNet content roots](https://github.com/MinLL/SkyrimNet-GamePlugin/blob/main/docs/modding/CONTENT_ROOTS.md)
- [MO2 Python plugin API](https://www.modorganizer.org/python-plugins-doc/index.html)
- [Lyria prompting guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-lyria-3-pro/)
- Installed beta26-rc4 PublicAPI.h: no outbound music-request modifier is exposed.
- Installed Bard Singing settings expose a local music URL and model field.
- Recorded OtherMusicInterface payloads include the gender prefix and Lyrics block.
