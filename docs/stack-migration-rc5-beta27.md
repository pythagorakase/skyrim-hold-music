# Hold Music migration to MGO RC5 and SkyrimNet beta 27

**Planning baseline: 15 October 2026.** Upgrade SkyrimNet together with MGO
4.0 RC5 when RC5 is available, as requested. RC5's imminent arrival is the
user's expectation; its final contents, destination and save compatibility
still need checking against the released package. This preparation changes
project documentation only. **19 October update:** regional listening validation
does not gate engineering or migration preparation. Use versioned provisional
recipes and existing recordings; keep runtime compatibility and ownership checks
separate from musical confidence. See the [development roadmap](development-roadmap.md).

Beta 27 makes a native library of prepared recordings worth comparing with
Hold Music's playback integration when the target stack is available. This
comparison does not block portable controller, library or planner work. Hold Music still needs to control
which performer, tradition, region and arrangement may use a recording. The
standing direction toward performance ownership remains in place; native
import is a candidate delivery route, subject to those requirements.

## Verified baseline

On October 15, `ModOrganizer.ini` selects
`MGO EXP - SkyrimNet b26 + SeverActions 4.2` under
`C:\MGO\Skyrim MGO 4.0 RC4.1`. Its lists enable
`SkyrimNet - Experimental beta26-rc4`, SeverActions 4.2.0, both Hold Music mods
and `HoldMusic.esp`; Solo Lute is disabled. This is configuration evidence,
not a check of a running save.

The repository records successful adapter playback on Mikael and cached
SkyrimNet playback on Sven. The owned controller was installed afterwards.
Its 15 October test crashed during candidate discovery in PapyrusUtil VR's
native dead filter while vanilla flute audio was playing. A targeted workaround
was installed with 52 passing package tests and recorded VFS checks; successful
owned playback after the fix remains unverified. SkyrimNet's bard feature was
disabled for that session. See the [RCA and retest](sven-crash-2026-10-15.md).
Sven's earlier SkyrimNet playback disproved assumed per-performer isolation:
retain the [handoff requirement](in-game-test-plan.md#second-test-sven-at-the-sleeping-giant-inn-hold-music-owned-path)
and recheck the actual profile before the next runtime test.

## What beta 27 changes

[SkyrimNet beta 27](https://github.com/MinLL/SkyrimNet-GamePlugin/releases/tag/vbeta27)
was published on October 14, 2026, at tag `vbeta27`, commit
`c53cb30e108503a27b71f8e98b146a1124b790ea`. Its bard changes are:

- Import MP3, WAV, OGG or FLAC with male, female or instrumental classification.
  Instrumentals are available to any bard and can be requested by style.
- Import/export audio with a same-stem YAML metadata file. Browser imports
  select the pair together.
- Keep a song exclusive to player performance.
- Disable **Compose New Songs With AI** while retaining library playback;
  unmatched requests are declined. The default is enabled.
- Keep imported recordings per save without automatic eviction.
- Fix lookup of non-English song titles and cancellation of streamed music
  requests.

The separate composition switch is useful for a prepared-library trial, but
it does **not** establish exclusive controller ownership. Leaving SkyrimNet
playback enabled can still conflict with Hold Music's controller.

The shipped [beta 27 lyric template](https://github.com/MinLL/SkyrimNet-GamePlugin/blob/vbeta27/plugins/skyrimnet/base/prompts/bard_song_lyrics.prompt)
is byte-identical to the
[beta 26 release template](https://github.com/MinLL/SkyrimNet-GamePlugin/blob/vbeta26-rc4/plugins/skyrimnet/base/prompts/bard_song_lyrics.prompt).
That reduces immediate template-rebase work; it does not validate our `HM1`
override, provider route or runtime context on beta 27.

## Integration choices

| Route | What it offers | What must be established |
|---|---|---|
| Hold Music preparation, SkyrimNet import and playback | A supported way to play existing recordings without the request proxy | Performer and region restrictions, supported automation, correct selection and lifecycle |
| Hold Music preparation and owned controller | Authored performer ownership, exact recording selection and our trace/receipts | Exclusive handoff, reliable sound/animation cleanup and the outstanding gameplay test |
| Existing 0.2.2 request adapter | Continuity for the current composition route | Beta 27 config, prompt, streaming, cancellation and cache behavior |

Style tags and vocal classification are insufficient evidence of strict
performer or regional eligibility. Keep the registry, compositions, recording
metadata, lyric provenance, planner and spending limits authoritative in Hold
Music. A SkyrimNet export should be a projection of that library, not its only
copy. No per-bard scheduler exclusion or playback API has been established by
this release review.

Capture the actual exported YAML before writing an exporter; do not invent
field names or assume it can represent Hold Music's complete metadata. A
wordless vocal is still a voice recording and must not become an unrestricted
instrumental merely because it has no lyrics. Per-save storage also requires
an explicit re-import or verified migration when the target save changes.

## Preparation before RC5

- Continue portable palette, library and planner work. Defer new assumptions
  about SkyrimNet's scheduler and import internals until the target stack can
  be exercised.
- Preserve the RC4.1 installation as the reference. Before the upgrade, close
  the game and capture the selected profile, mod/plugin lists, ESS/SKSE pair,
  SkyrimNet database and song audio, private settings and credentials, Hold
  Music library/lyrics/receipts/trace, workshop auditions and install backups.
  A Git checkout alone does not contain these private assets.
- Treat the [package builder](../game_package/tools/build_game_package.py) as
  RC4.1-specific: it currently pins the old install, profile and scratch root.
  Parameterize or deliberately retarget it before an RC5 build. Resolve the
  actual RC5 profile and dependencies rather than substituting a guessed path.
- Repoint private workshop/knowledge database configuration only after the
  target save is identified. Read its schema and actor mappings again through
  the existing read-only adapters; do not carry UUID/name assumptions across
  saves or insert rows into SkyrimNet's song table.
- Compare beta 27's effective Bard Singing configuration with the adapter's
  three managed routing scalars. Preserve the new composition setting through
  overlay preparation and reconciliation. Recheck the winning prompt and
  content bundle through MO2's VFS.

## Validation on the new stack

1. **Establish the RC5 baseline.** Check RC5's release instructions and save
   policy, the bundled SkyrimNet version, then the actual selected profile,
   winning DLL/content files and startup log. Resolve dependency and override
   conflicts before adding Hold Music behavior. Record the exact release tag
   if a beta 27 follow-up has replaced the reviewed build.
2. **Run an isolated native import trial.** Keep the owned controller inactive
   through its supported switch in the test profile. Enable SkyrimNet bard
   playback and disable its new-composition switch. Import an existing
   instrumental and a compatible vocal recording; no new music generation is
   needed. Exercise ambient playback, requests by title/style, a request with
   no matching song, and player-only exclusion. Check logs for unexpected
   composition requests.
3. **Test the library contract.** Export and re-import a pair, compare audio
   hashes and metadata, check duplicate handling and persistence after restart
   and save reload. Test performer/region mismatches explicitly. Record which
   constraints are enforced and which are merely descriptive tags.
4. **Test performance lifecycle.** Verify spatial audio, prop/animation,
   vanilla-song suppression, dialogue interruption, menus, combat, cell exit
   and load cleanup. Use Sven, Mikael and Lynly where present; establish each
   actor's runtime eligibility rather than inferring it from static records.
5. **Validate the selected integration.** If native playback cannot enforce
   Hold Music's selection rules, retain the owned path and prove SkyrimNet's
   bard controller is inactive before testing it. If retaining the request
   adapter, verify `HM1`, duration, streaming and cancellation with offline
   fixtures before a bounded live composition check. Stopping a request must
   not cause our helper to retry an uncertain paid generation.
6. **Recheck context and capture evidence.** Exercise the saved-lyrics reader
   and actor knowledge bridge against the target schema. Beta 27 also changes
   memory retrieval; preserve actor scope and provenance rather than claiming
   our direct database reader mirrors native retrieval. Collect the VFS
   results, logs, trace/receipts and listening observations under the exact
   stack and save identity.

Migration is complete when the chosen route meets performer/region rules,
one controller owns each tested performance, interruption and persistence
checks pass, and the old stack remains recoverable. Imported audio playing
once is an intermediate result, not completion of the ownership design.
