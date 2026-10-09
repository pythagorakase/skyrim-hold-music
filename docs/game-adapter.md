# Hold Music 0.2.0: regional composition pilot

Installed in the experimental profile on October 8, 2026. See the
[verification record](game-adapter-verification.md) for tested boundaries and the
remaining in-game playback check.

New compositions use the approved Nord/region recipe for the bard's current
location, regardless of race. This applies to performers SkyrimNet already
recognizes as bards; it does not add factions or recruit new performers.

One performer plays one lute. The default is a 50% instrumental chance per new
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

The request adapter reads exactly one marker in the native style prefix,
uses SkyrimNet's explicit `Hold: ...` suffix when present (including capital
names such as `Dawnstar` for the Pale), and otherwise checks exact names from
winning LCTN/CELL records. It replaces the music
prompt with the selected regional recipe. The marker never reaches the music
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
exits; conflicting edits are preserved in a recovery file. The helper exits with
MO2. There is no extra automatic retry of paid generations.

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
logs record composer, location, region and mode without lyrics or credentials.

To revert, close Skyrim and MO2, disable Hold Music and re-enable Solo Lute in the
experimental profile, then relaunch. Leave only one music adapter content mod
enabled at a time. No database rollback is involved. Newly cached recordings
remain under SkyrimNet's normal management.

The **Hold Music** dashboard plugin settings control instrumental chance. It is
not a new in-game MCM. Settings changes apply to subsequent requests.

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
