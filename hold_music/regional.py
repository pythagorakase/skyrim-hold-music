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
    """Prefer SkyrimNet's explicit hold suffix, then an exact audited name."""
    if not isinstance(location, str):
        return 'nord'
    name = ' '.join(location.casefold().split())
    # Observed native inputs include "Windpeak Inn, Hold: Dawnstar" and
    # "Bards College, Solitude, Outdoors, Hold: Haafingar". Do not substring-guess.
    hold = re.search(r'(?:^|, )hold: ([^,]+)$', name)
    if hold:
        return HOLD_NAMES.get(hold[1], 'nord')
    region = registry.get('locations', {}).get(name)
    return region if region in REGIONS else 'nord'


def performance_mode(region, choice):
    if choice not in ('instrumental', 'vocal'):
        raise ValueError('Unknown composition choice')
    # Winterhold's approved sung recipe uses vocables, not written verses.
    if region == 'winterhold' and choice == 'vocal':
        return 'wordless'
    return choice


def music_prompt(region, choice, gender, lyrics='', palette_path=PALETTE):
    setting, profiles = load_profiles(palette_path)
    if region not in profiles:
        raise ValueError('Unknown regional recipe')
    if gender.casefold() not in ('male', 'female'):
        raise ValueError('Unsupported SkyrimNet vocal gender')
    profile = profiles[region]
    mode = performance_mode(region, choice)
    if mode == 'instrumental':
        performer = 'One musician playing a single lute, entirely instrumental. No singing, humming, spoken words or vocalizations.'
    else:
        performer = f'One {gender.casefold()} singer accompanying themselves on a single lute. Only one voice and one lute.'
        if mode == 'wordless':
            performer += ' Wordless singing with vocables only; no lyrics, sentences or spoken words.'
    reference = profile.get('reference')
    idiom = (f'In the style of {reference}: ' if reference else '') + profile['core'].rstrip('.') + '.'
    sections = [setting, performer, idiom]
    if mode != 'instrumental':
        sections.append('Voice: ' + profile['voice'].rstrip('.') + '.')
    sections.append('Lute: ' + profile['lute'].rstrip('.') + '.')
    sections.append('Intimate pre-modern acoustic performance by the listed performer only. '
                    'No other instruments, percussion, backing voices, choir, overdubs, '
                    'orchestral backing or modern studio production.')
    if mode == 'vocal':
        if not isinstance(lyrics, str) or not lyrics.strip():
            raise ValueError('A lyrical performance needs lyrics')
        sections.append('Lyrics:\n' + lyrics)
    return '\n\n'.join(sections)
