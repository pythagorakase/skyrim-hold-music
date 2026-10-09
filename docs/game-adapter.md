# Hold Music 0.2.2: regional composition pilot

The 0.2.0 pilot was installed in the experimental profile on October 8, 2026.
The 0.2.2 changes have offline verification only. See the
[verification record](game-adapter-verification.md) for tested boundaries and the
remaining in-game playback check.

New compositions use the approved Nord/region recipe for the bard's current
location, regardless of race. This applies to performers SkyrimNet already
recognizes as bards; it does not add factions or recruit new performers.

One adult performer plays one lute-family instrument, using the palette’s
plucked instrument name (for example, lute or cittern). The default is a 50% instrumental chance per new
request, with stable choices on retries. Instrumentals omit both the lyric draft
and all vocal instructions. Winterhold's sung selections use wordless vocables
and omit lyrics too. Other sung selections retain SkyrimNet's lyric text.
Musical instructions are prompts, not guarantees of the generated audio.

Lurbuk's own compositions keep the pre-regional Solo Lute treatment in both
modes. There is no new Orc recipe in this version. Unknown or ambiguous location
names use the plain Nord recipe.

## Playback boundary

This version regionalizes **composition**, not the playback library. SkyrimNet
still owns scheduling, native cache selection, animation and audio playback. It
can reuse gender-matched recordings across bards and holds, including Lurbuk.
There is no claim of strict regional playback or Lurbuk playback isolation.
Existing recordings and native cache settings are not modified by this installer.

## How it works

SkyrimNet beta 26 supplies `bard_name` and `current_location` to its existing lyric
template, alongside the bard's memories, events and dialogue. A minimal template
override asks the lyric model to copy an `HM1[bard||location]` marker into its Style
line. This is a model-mediated context bridge, not a native actor-ID API.

The request adapter reads exactly one marker in the native style prefix.
Location resolution casefolds text, collapses whitespace and strips surrounding
quotes/brackets and trailing punctuation from the whole string and each
comma-separated segment. A final `Hold: ...` segment supplies a parent-location
name, which is not necessarily a hold; empty, `unknown` and `none` values are
ignored. The first exact match wins, in this order:

1. The explicit hold/capital table for the suffix, also trying it without a
   trailing ` hold` (`Whiterun Hold` resolves to Whiterun).
2. The audited location registry for the suffix (`Riverwood` resolves to
   Whiterun, `Heljarchen Hall` to the Pale).
3. Each remaining segment from venue to last: first the hold/capital table,
   then the registry. Generic `outdoors`, `indoors`, `interior`, `exterior`,
   `unknown`, `skyrim` and `tamriel` tokens are skipped. An unknown suffix still
   permits venue resolution (`The Bannered Mare, Hold: Unknown` is Whiterun).
4. The plain Nord fallback.

Only registry values naming one of the nine regions are accepted. There is no
substring matching. Service logs identify the winning rule as `suffix-table`,
`suffix-registry`, `segment-table`, `segment-registry` or `default`.
The adapter replaces the music prompt with the selected regional recipe. The marker never reaches the music
provider. Missing, duplicated or misplaced markers stop that music request before
a paid generation. The existing lyric generation still runs for instrumentals;
its draft is simply not sent to Lyria.

The MO2 companion temporarily maps the supported local music URL to a hidden,
independent Python helper, which forwards the music request to the configured
OpenRouter key and `google/lyria-3-pro-preview`. The independent process preserves
the Solo Lute 0.1.1 repair for MO2's embedded-Python listener stalling during play.
No DLL injection, Papyrus, ESP, game executable changes, or database writes.
The workshop remains separate and uses Google's direct `lyria-3.5` route.

Both the route and the metadata template are exposed through MO2 only after the
helper starts successfully. If startup fails, the original provider and lyric
template remain visible. Source provider routing stays unchanged. Dashboard
changes to other Bard Singing settings are reconciled after the launched program
exits. If source edits conflict with dashboard edits, the dashboard candidate
(with original routing restored) is saved as `BardSinging.conflict.yaml` and a
WARNING is logged. The source stays intact, the baseline is removed and
reconciliation returns normally. The next `prepare()` builds a fresh overlay
from the source, keeping the music route available; the conflict copy remains
for manual recovery. Source BOMs and line endings are preserved in the overlay,
baseline, source write-back and conflict copy. The helper exits with
MO2. There is no extra automatic retry of paid generations.

## Compact game prompts

Prompts use the workshop's compact line format with no assumed performer race:

```text
Style: <reference> (<adaptation>).
Tamriel (Elder Scrolls): <regional audition label>.
One adult <gender> performer; <role>.
Intimate live acoustic room; only these sound sources. No other instruments, percussion, backing voices, choir, overdubs, orchestral backing or modern studio production.
<core>.
Voice: <voice>.
<Instrument>: <lute clause>.
```

The reference is always named, including multipart traditions, with `solo
adaptation`, `solo wordless adaptation` or `instrumental reduction` to identify
the reduction. Sung roles are `singing with plucked <instrument>`; instrumental
roles are `solo <instrument> instrumental; plucked strings`. Instrument names
come from `workshop.plucked`, falling back to lute. The Nord fallback's setting
is `Skyrim, unnamed venue`.

Instrumentals use `core_instrumental` and `lute_instrumental` where supplied,
falling back to `core` and `lute`, and omit the Voice line and lyric material.
Wordless prompts append `Wordless singing with vocables only; no lyrics,
sentences or spoken words.` to the Voice line and also omit lyrics. Vocal
prompts append `Sing the supplied lyrics as written, preserving their words and
order.`, a blank line, and `Lyrics:` followed by the unchanged lyric text.
Default directions remain below 1,000 characters excluding the lyrics block.
Lurbuk retains the separate legacy prompt unchanged.

## Duration reporting

SkyrimNet reads the recording duration from response text. Lyria's audio-only
stream did not supply it, so installations without FFmpeg cached recordings
with a duration of zero. Helper build 0.2.2 buffers the audio and walks its MP3
frames in Python, then reports the duration rounded to whole seconds.

`reportDuration` defaults to `true`, including when the key is missing. Set
`reportDuration: false` in the same `config/plugins/HoldMusic/settings.yaml`
file as `instrumentalPercent` to restore byte-for-byte upstream pass-through.
The setting is read for each request; the content dashboard schema is unchanged.

After upstream HTTP 200, the helper immediately sends headers and an assistant
init event. While buffering, it sends a `.` content heartbeat every two seconds.
It then sends `\n\n## Metadata\n**Duration:** <N>s\n` as a content event,
followed by the original upstream audio and finish events in their original
order, ending with the original `[DONE]`. Audio base64 fragments are joined
before decoding; the forwarded audio bytes are unchanged. Connections close
when the relay finishes.

Upstream error events, missing audio or `[DONE]`, invalid base64, and unreadable
MP3 duration fall back to the buffered upstream bytes without duration metadata.
Read failures also flush the buffer before using the existing error handling.
The init/heartbeat events already sent remain in the response. Warnings contain
only the fallback reason, never response bodies. Logs record rounded duration,
decoded audio size and whether metadata was reported; `/health` adds a
`duration_reported` counter. The 64 MB response cap, two-request limit and
upstream timeout remain in place. No in-game verification of 0.2.2 was performed.

## Local installation

Requires the beta 26 experimental profile, its isolated profile-data mod, and
standalone Python 3.10+. Close Skyrim and MO2 first. From this repository:

```powershell
py -3 tools/install_game_adapter.py 'C:\MGO\Skyrim MGO 4.0 RC4.1' 'MGO EXP - SkyrimNet b26 + SeverActions 4.2' --game-data 'C:\Steam\steamapps\common\SkyrimVR\Data'
```

The installer backs up the mod list and existing targets, enables
`MGO Experimental - Hold Music`, and disables `MGO Experimental - Solo Lute` in
that profile. It retains the prior instrumental percentage. Local paths and
provider-bearing runtime files stay out of version control and release archives.
`HoldMusic.log` and `HoldMusic-Service.log` are in MO2's `logs` folder; service
logs record composer, location, region, resolution rule and mode without lyrics
or credentials.

To revert, close Skyrim and MO2, disable Hold Music and re-enable Solo Lute in the
experimental profile, then relaunch. Leave only one music adapter content mod
enabled at a time. No database rollback is involved. Newly cached recordings
remain under SkyrimNet's normal management.

The **Hold Music** dashboard plugin settings control instrumental chance. It is
not a new in-game MCM. Settings changes apply to subsequent requests.

## Helper hot-swap and version compatibility

`engine.VERSION` remains `0.2.0`: the MO2-resident plugin compares helper health
against the protocol version it imported when MO2 started. `engine.BUILD` is
`0.2.2`, exposed as `build` in `/health` and in the independent helper's ready
log line. Content and installer versions are 0.2.2. The unchanged MO2-resident
plugin and its startup message remain at 0.2.1.

With Skyrim closed and no music request in flight, copy the rebuilt package
files over `plugins\hold_music_adapter`. In the profile's
`hold-music-runtime` folder, touch the helper's `helper-*.stop` file, using the
same identifier as its `helper-*.json` status file. The helper shuts down; the
next configured-profile launch starts the updated helper. Do not create a
literal wildcard filename. MO2 can remain open for helper-only changes because
the protocol version is unchanged. Changes to the MO2 plugin `__init__.py`
require an MO2 restart. Restart MO2 to load the complete 0.2.1 package, including
its in-process configuration reconciliation changes.

## Build and validation

```sh
python tools/build_game_adapter.py --validation-root local/validation-content
python -m unittest discover -s tests -v
```

The build copies the canonical workshop palette and `hold_music/regional.py`
into the self-contained MO2 package. The historical `prototype/solo_lute` tree
is preserved unchanged.

`game_adapter/data/locations.json` is a versioned English lookup for this MGO
profile, derived from winning LCTN parent chains and CELL XLCN references. It is
not a universal registry for arbitrary load orders or localized game names.
Ambiguous names conservatively fall back to Nord. Rebuild it after relevant
location-mod changes using a trusted audited snapshot:

```powershell
py -3 tools/build_game_locations.py --audit-module 'C:\MGO\codex-investigations\20261008-bard-roster\records.py' --output game_adapter/data/locations.json
py -3 tools/build_game_adapter.py
```

The builder also accepts portable `--records-json` rows containing `id`, `type`,
`name`, `editor_id` and `parent`. The parent is an LCTN PNAM or CELL XLCN reference.
Cycles and unknown roots do not guess a hold.

Offline tests cover recipes, location ambiguity, context validation, Lurbuk
parity, lyric omission, route restoration, streaming, duplicate-request modes,
and helper lifetime. Native content validation and MO2 VFS checks must be
recorded separately from actual in-headset bard playback.
