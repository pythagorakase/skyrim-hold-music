"""The nine approved Nord/region recipes for the first game integration.

Recipe data comes from the same generated palette as the listening workshop.
This module does not choose an actor, change game state, or make provider calls.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REGIONS = ('haafingar', 'eastmarch', 'whiterun', 'reach', 'falkreath',
           'rift', 'winterhold', 'pale', 'hjaalmarch')
PALETTE = Path(__file__).resolve().parents[1] / 'dashboard' / 'palette-data.json'
HOLD_NAMES = {**{region: region for region in REGIONS},
              'whiterun hold': 'whiterun', 'falkreath hold': 'falkreath',
              'winterhold hold': 'winterhold',
              'the pale': 'pale', 'dawnstar': 'pale',
              'the reach': 'reach', 'markarth': 'reach',
              'the rift': 'rift', 'riften': 'rift',
              'solitude': 'haafingar', 'windhelm': 'eastmarch', 'morthal': 'hjaalmarch'}


def load_profiles(path=PALETTE):
    palette = json.loads(Path(path).read_text(encoding='utf-8'))
    profiles = {p['id']: p for p in palette['existing'] if p['id'] in (*REGIONS, 'nord')}
    if set(profiles) != set(REGIONS) | {'nord'}:
        raise ValueError('The regional game palette must contain Nord and all nine holds')
    return palette['auditionContext'], profiles


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
    if choice not in ('instrumental', 'vocal'):
        raise ValueError('Unknown composition choice')
    # Winterhold's approved sung recipe uses vocables, not written verses.
    if region == 'winterhold' and choice == 'vocal':
        return 'wordless'
    return choice


def music_prompt(region, choice, gender, lyrics='', palette_path=PALETTE):
    _, profiles = load_profiles(palette_path)
    if region not in profiles:
        raise ValueError('Unknown regional recipe')
    if gender.casefold() not in ('male', 'female'):
        raise ValueError('Unsupported SkyrimNet vocal gender')
    profile = profiles[region]
    mode = 'wordless' if choice == 'wordless' else performance_mode(region, choice)
    palette = json.loads(Path(palette_path).read_text(encoding='utf-8'))
    region_label = 'Skyrim, unnamed venue' if region == 'nord' else palette['auditionRegions'][region]
    instrument = profile.get('workshop', {}).get('plucked') or 'lute'
    if mode == 'instrumental':
        adaptation = 'instrumental reduction'
        role = f'solo {instrument} instrumental; plucked strings'
        # Cheap insurance for a paid in-game request: the compact workshop
        # wording implies an instrumental, but say so outright.
        role += '. Entirely instrumental; no singing, humming or spoken words'
    else:
        adaptation = 'solo wordless adaptation' if mode == 'wordless' else 'solo adaptation'
        role = f'singing with plucked {instrument}'
    core = (profile.get('core_instrumental') or profile['core']) if mode == 'instrumental' else profile['core']
    lute = (profile.get('lute_instrumental') or profile['lute']) if mode == 'instrumental' else profile['lute']
    sections = [f"Style: {profile['reference']} ({adaptation}).",
                f'Tamriel (Elder Scrolls): {region_label}.',
                f'One adult {gender.casefold()} performer; {role}.',
                'Intimate live acoustic room; only these sound sources. '
                'No other instruments, percussion, backing voices, choir, overdubs, '
                'orchestral backing or modern studio production.',
                core.rstrip('.') + '.']
    if mode != 'instrumental':
        voice = 'Voice: ' + profile['voice'].rstrip('.') + '.'
        if mode == 'wordless':
            voice += ' Wordless singing with vocables only; no lyrics, sentences or spoken words.'
        sections.append(voice)
    sections.append(instrument.capitalize() + ': ' + lute.rstrip('.') + '.')
    if mode == 'vocal':
        if not isinstance(lyrics, str) or not lyrics.strip():
            raise ValueError('A lyrical performance needs lyrics')
        sections.append('Sing the supplied lyrics as written, preserving their words and order.')
        sections.append('\nLyrics:\n' + lyrics)
    return '\n'.join(sections)
