"""The nine provisional Nord/region recipes shared with the local game package.

Recipe data comes from the same generated palette as the listening workshop.
This module does not choose an actor, change game state, or make provider calls.
"""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

REGIONS = ('haafingar', 'eastmarch', 'whiterun', 'reach', 'falkreath',
           'rift', 'winterhold', 'pale', 'hjaalmarch')
PALETTE = Path(__file__).resolve().parents[1] / 'dashboard' / 'palette-data.json'
# This module is also copied into the standalone MO2 adapter. Production
# execution passes its transport's model explicitly; prompt-only callers use
# this default without importing the Hold Music package.
DEFAULT_MODEL = 'google/lyria-3-pro-preview'
HOLD_NAMES = {**{region: region for region in REGIONS},
              'whiterun hold': 'whiterun', 'falkreath hold': 'falkreath',
              'winterhold hold': 'winterhold',
              'the pale': 'pale', 'dawnstar': 'pale',
              'the reach': 'reach', 'markarth': 'reach',
              'the rift': 'rift', 'riften': 'rift',
              'solitude': 'haafingar', 'windhelm': 'eastmarch', 'morthal': 'hjaalmarch'}


def load_profiles(path=PALETTE):
    palette = json.loads(Path(path).read_text(encoding='utf-8'))
    return palette['auditionContext'], _profiles(palette)


def _profiles(palette):
    profiles = {p['id']: p for p in palette['existing'] if p['id'] in (*REGIONS, 'nord')}
    if set(profiles) != set(REGIONS) | {'nord'}:
        raise ValueError('The regional game palette must contain Nord and all nine holds')
    return profiles


def resolve_location(location, registry):
    """Return the region, preserving the original caller interface."""
    return resolve_location_detail(location, registry)[0]


def resolve_location_detail(location, registry):
    """Resolve exact suffix/segment names and report the first matching rule."""
    if not isinstance(location, str):
        return 'nord', 'default'

    def normalize(value):
        return ' '.join(value.casefold().split()).strip(' \"\'[](){}.,;:!?')

    segments = [normalize(part) for part in normalize(location).split(',')]
    locations = registry.get('locations', {})
    hold_value = None
    # An empty suffix may have lost its trailing colon during normalization.
    suffix = re.fullmatch(r'hold:(?:\s*(.*))?', segments[-1])
    if suffix or segments[-1] == 'hold':
        segments.pop()
        hold_value = normalize(suffix[1] or '') if suffix else ''
    if hold_value not in (None, '', 'unknown', 'none'):
        region = HOLD_NAMES.get(hold_value) or HOLD_NAMES.get(hold_value.removesuffix(' hold'))
        if region:
            return region, 'suffix-table'
        region = locations.get(hold_value)
        if region in REGIONS:
            return region, 'suffix-registry'
    generic = {'outdoors', 'indoors', 'interior', 'exterior', 'unknown', 'skyrim', 'tamriel'}
    for segment in segments:
        if not segment or segment in generic:
            continue
        region = HOLD_NAMES.get(segment)
        if region:
            return region, 'segment-table'
        region = locations.get(segment)
        if region in REGIONS:
            return region, 'segment-registry'
    return 'nord', 'default'


def performance_mode(region, choice):
    if choice not in ('instrumental', 'vocal', 'wordless'):
        raise ValueError('Unknown composition choice')
    # Preserve the baseline exceptions even when the caller requests vocals.
    if region == 'hjaalmarch':
        return 'instrumental'
    if region == 'winterhold' and choice == 'vocal':
        return 'wordless'
    return choice


def freeze_recipe(region, choice, gender, palette_path=PALETTE, *, model_id=DEFAULT_MODEL):
    """Freeze one exact direction and its sound-source identity from one read.

    The revision hashes the actual lyrics-independent prompt plus identity.
    It does not change when unrelated notes, recipes, or lyric content change.
    Arrangement names refer to the existing visible animation family.
    """
    palette = json.loads(Path(palette_path).read_text(encoding='utf-8'))
    profiles = _profiles(palette)
    if region not in profiles:
        raise ValueError('Unknown regional recipe')
    if gender.casefold() not in ('male', 'female'):
        raise ValueError('Unsupported SkyrimNet vocal gender')
    profile = profiles[region]
    mode = performance_mode(region, choice)
    region_label = 'Skyrim, unnamed venue' if region == 'nord' else palette['auditionRegions'][region]
    instrument = profile.get('workshop', {}).get('plucked') or 'lute'
    if not isinstance(instrument, str) or not instrument.strip():
        raise ValueError('Regional recipe requires a named plucked instrument')
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError('Regional recipe requires a model ID')
    if mode == 'instrumental':
        adaptation = 'instrumental reduction'
        role = f'solo {instrument} instrumental; plucked strings'
        # Cheap insurance for a paid in-game request: the compact workshop
        # wording implies an instrumental, but say so outright.
        role += '. Entirely instrumental; no singing, humming or spoken words'
    else:
        adaptation = 'solo wordless adaptation' if mode == 'wordless' else 'solo adaptation'
        role = f'singing while playing {instrument}; plucked strings'
    family_rule = profile.get('workshop', {}).get('family_rules', {}).get('plucked') or 'No bowed strings.'
    core = (profile.get('core_instrumental') or profile['core']) if mode == 'instrumental' else profile['core']
    lute = (profile.get('lute_instrumental') or profile['lute']) if mode == 'instrumental' else profile['lute']
    sections = [f"Style: {profile['reference']} ({adaptation}).",
                f'Tamriel (Elder Scrolls): {region_label}.',
                f'One adult {gender.casefold()} performer; {role}.',
                'Intimate live acoustic room; only these sound sources. '
                'No other instruments, percussion, backing voices, choir, overdubs, '
                'orchestral backing or modern studio production.',
                family_rule,
                core.rstrip('.') + '.']
    if mode != 'instrumental':
        voice = 'Voice: ' + profile['voice'].rstrip('.') + '.'
        if mode == 'wordless':
            voice += ' Wordless singing with vocables only; no lyrics, sentences or spoken words.'
        sections.append(voice)
    sections.append(instrument.capitalize() + ': ' + lute.rstrip('.') + '.')
    if mode == 'vocal':
        sections.append('Sing the supplied lyrics as written, preserving their words and order.')
    prefix = '\n'.join(sections)
    identity = dict(region=region, mode=mode, gender=gender.casefold(),
        recipe_id=f'{region}/{mode}', model_id=model_id,
        arrangement='solo_lute' if mode == 'instrumental' else 'solo_lute_and_voice',
        voice='none' if mode == 'instrumental' else gender.casefold(),
        instrument_family='plucked_string', instrument_name=instrument)
    frozen = dict(identity, prompt_prefix=prefix, region_label=region_label)
    return dict(frozen, recipe_revision=recipe_fingerprint(frozen))


def recipe_fingerprint(recipe):
    """Hash a retained production direction without consulting today's palette."""
    identity = {key: recipe[key] for key in
        ('region', 'mode', 'gender', 'recipe_id', 'model_id', 'arrangement', 'voice',
         'instrument_family', 'instrument_name')}
    fingerprint = json.dumps(dict(version=1, identity=identity, prompt_prefix=recipe['prompt_prefix']),
                             sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return 'sha256:' + hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()


def prompt_from_recipe(recipe, lyrics=''):
    """Append exact lyrics to an already frozen direction without rereading it."""
    if recipe['mode'] != 'vocal':
        return recipe['prompt_prefix']
    if not isinstance(lyrics, str) or not lyrics.strip():
        raise ValueError('A lyrical performance needs lyrics')
    return recipe['prompt_prefix'] + '\n\nLyrics:\n' + lyrics


def music_prompt(region, choice, gender, lyrics='', palette_path=PALETTE):
    return prompt_from_recipe(freeze_recipe(region, choice, gender, palette_path), lyrics)
