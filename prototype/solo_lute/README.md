# Solo Lute 0.1.0 - working title

A local SkyrimNet beta26 experiment: one bard, one lute, sometimes a voice.
New compositions have a 50% chance of being instrumental. Both modes use a
Renaissance/Baroque musical brief, with expressive lute writing and natural
acoustic sound. Vocal pieces keep the bard's generated words and vocal gender.
Instrumental requests contain neither those words nor the engine's vocal prefix.

## How it works

The prototype has a SkyrimNet content/settings package and an MO2 companion.
The companion runs a tiny loopback HTTP adapter in MO2's existing Python runtime.
Nothing is injected into Skyrim and no extra executable has to be started.
SkyrimNet's supported local music URL sends requests to the adapter; the adapter
rewrites the music prompt and forwards to **the existing OpenRouter account and
google/lyria-3-pro-preview model**. The dashboard will therefore temporarily show
**AceStep (Local)** as the transport. No AceStep model is downloaded or run.

The music endpoint is a temporary VFS mapping of BardSinging.yaml. The source
configuration retains its OpenRouter provider. Unchecking the **MGO Experimental
- Solo Lute** mod and restarting the game removes the mapping. Ordinary dialogue,
STT, TTS, follower behavior, and Skyrim's playback/animation code are untouched.
There is no ESP, native DLL, Papyrus script, database edit, or save migration.

Requests retry with the same instrumental/vocal choice. The adapter adds no
automatic retries of paid generations. It passes audio responses through unchanged.
If adapter setup fails before launching, MO2 exposes the original config. If an
upstream generation fails, the error is returned without silently making a vocal
replacement. Existing backup-provider settings are not altered.

## Use and settings

Installed locally for **MGO EXP - SkyrimNet b26 + SeverActions 4.2** only. Keep MO2
open while playing, as usual. No hotkey or power is needed.

The content package supplies **SoloLute** settings to SkyrimNet's dashboard
(not its MCM). **Instrumental chance (%)** defaults to 50. Set 0 for all vocals,
100 for all instrumentals. Values are read for each new request. Its persistent
settings file is `config/plugins/SoloLute/settings.yaml` in the isolated profile
data mod. Do not change the music provider while using the adapter; disable the
MO2 content mod between game sessions to restore the normal route instead.

Changing the percentage affects newly generated music only. The existing cache
and normal selection rules determine what is replayed; strict alternation is
intentionally out of scope. Identical generation requests retain their choice.

SkyrimNet still creates and stores a lyric draft before asking for music. For an
instrumental piece the draft is discarded at the outbound request boundary, so
it may still be shown in the song catalog despite never being sent to Lyria.
This prototype does not revise the stored metadata or suppress that small LLM
call. Nor does it fix vanilla scripted dialogue being interrupted by bard music.
It changes generation instructions; musical compliance still needs listening.

## Privacy, routing, and recovery

The adapter reads the already configured OpenRouter music key at request time.
It never logs credentials, lyric text, or audio. Logs in MO2's `logs/SoloLute.log`
show the selected mode and whether lyrics were forwarded. The local listener is
loopback-only, uses an unpredictable request path, rejects browser-originated
requests, and only accepts the verified music model.

Temporary config copies under the selected profile's `solo-lute-runtime` contain
the existing API key, just like the source config. They are local runtime data,
not part of this repository or a distribution archive. Do not publish them.
After game exit, any dashboard changes to other Bard Singing fields are copied
back with the original routing restored. Concurrent conflicting edits are kept
as `BardSinging.conflict.yaml`, never written over the changed source.

To disable: exit Skyrim, uncheck the Solo Lute mod, then launch normally. The MO2
companion can remain installed; inactive profiles receive no mappings. For full
removal, close MO2 too, then remove its `plugins/solo_lute` companion folder and
the content mod. No save cleaning is required. The earlier archived song library
is separate and remains recoverable from its existing backup.

## Development

Standard-library Python, tested with `python -m unittest discover -s tests -v`.
`tools/install_local.py MO2_ROOT PROFILE` installs while MO2 and Skyrim are closed,
backing up the existing modlist and config. It writes no localhost route into
the original config. `tools/vfs_probe.py` runs through MO2 without launching Skyrim
or calling a paid API; it checks which configuration the virtual filesystem sees.

## Future ideas (not implemented)

- Recruit nearby patrons into a performance using existing drum or audience
  clapping/stomping animations. Expand instrumentation only after performers
  have actually joined; release their AI packages cleanly when music ends.
- Regional musical palettes based on bard race or hold, with the style choices
  to be decided later.
- A proper pre-generation hook in SkyrimNet could skip unused lyric drafts and
  record instrumental metadata directly, eventually replacing the local adapter.
