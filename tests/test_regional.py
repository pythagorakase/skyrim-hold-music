import json
from pathlib import Path
import tempfile
import unittest

from hold_music.regional import REGIONS, load_profiles, music_prompt, resolve_location, resolve_location_detail, performance_mode


class RegionalRecipes(unittest.TestCase):
    def test_approved_nine_regions_and_nord_fallback_are_available(self):
        _, profiles = load_profiles()
        self.assertEqual(set(profiles), set(REGIONS) | {'nord'})
        for region in (*REGIONS, 'nord'):
            for choice in ('instrumental', 'vocal'):
                text = music_prompt(region, choice, 'female', 'Unique lyric draft.')
                profile = profiles[region]
                for field in ('core', 'lute'):
                    clause = (profile.get(field + '_instrumental') or profile[field]) if choice == 'instrumental' else profile[field]
                    self.assertIn(clause, text)

    def test_instrumentals_never_receive_lyric_draft_or_voice_technique(self):
        _, profiles = load_profiles()
        for region in (*REGIONS, 'nord'):
            text = music_prompt(region, 'instrumental', 'female', 'PRIVATE_UNUSED_DRAFT')
            self.assertNotIn('PRIVATE_UNUSED_DRAFT', text)
            self.assertNotIn('Voice:', text)
            self.assertNotIn('female singer', text)
            instrument = profiles[region].get('workshop', {}).get('plucked') or 'lute'
            self.assertIn(f'One adult female performer; solo {instrument} instrumental; plucked strings.', text)
            self.assertIn(f"Style: {profiles[region]['reference']} (instrumental reduction).", text)
            self.assertNotIn('Lyrics:', text)

    def test_winterhold_sung_half_is_wordless(self):
        text = music_prompt('winterhold', 'vocal', 'male', 'UNUSED_VERSES')
        self.assertIn('Wordless singing', text)
        self.assertIn('One adult male performer; singing with plucked lute.', text)
        self.assertIn('Wordless singing with vocables only; no lyrics, sentences or spoken words.', text)
        self.assertNotIn('UNUSED_VERSES', text)
        self.assertNotIn('Lyrics:', text)

    def test_lyrical_mode_preserves_actual_voice_and_exact_lyrics(self):
        lyric = '[Verse]\nA long road—home.\n'
        for gender in ('male', 'female'):
            text = music_prompt('falkreath', 'vocal', gender, lyric)
            self.assertIn(f'One adult {gender} performer; singing with plucked lute.', text)
            self.assertTrue(text.endswith(lyric))

    def test_location_resolution_does_not_guess_from_substrings(self):
        registry = {'locations': {"dead man's drink": 'falkreath', 'ambiguous inn': None}}
        self.assertEqual(resolve_location("  Dead Man's  Drink ", registry), 'falkreath')
        self.assertEqual(resolve_location('The road from Falkreath to Whiterun', registry), 'nord')
        self.assertEqual(resolve_location('Ambiguous Inn', registry), 'nord')


class CompactPrompts(unittest.TestCase):
    def test_full_golden_prompts(self):
        fixtures = json.loads((Path(__file__).parent / 'fixtures/regional_prompts.json').read_text(encoding='utf-8'))
        lyrics = 'The lantern warms the winding road.\nWe share the light and lift the load.'
        for name, expected in fixtures.items():
            region, mode = name.split('_')
            with self.subTest(name=name):
                self.assertEqual(music_prompt(region, mode, 'male', lyrics), expected)
        self.assertEqual(music_prompt('winterhold', 'vocal', 'male', lyrics), fixtures['winterhold_wordless'])

    def test_all_regions_and_three_modes_are_compact_with_one_named_style(self):
        _, profiles = load_profiles()
        for region in (*REGIONS, 'nord'):
            for choice in ('vocal', 'instrumental', 'wordless'):
                for gender in ('male', 'female'):
                    with self.subTest(region=region, choice=choice, gender=gender):
                        prompt = music_prompt(region, choice, gender, 'PRIVATE_LYRIC')
                        direction = prompt.split('\n\nLyrics:\n', 1)[0]
                        self.assertLess(len(direction), 1000)
                        mode = 'wordless' if choice == 'wordless' else performance_mode(region, choice)
                        adaptation = {'vocal': 'solo adaptation', 'wordless': 'solo wordless adaptation',
                                      'instrumental': 'instrumental reduction'}[mode]
                        styles = [line for line in prompt.splitlines() if line.startswith('Style: ')]
                        self.assertEqual(styles, [f"Style: {profiles[region]['reference']} ({adaptation})."])
                        self.assertEqual(prompt.count('One adult '), 1)
                        self.assertEqual('Voice: ' in prompt, mode != 'instrumental')
                        self.assertEqual('Lyrics:' in prompt, mode == 'vocal')
                        self.assertEqual('PRIVATE_LYRIC' in prompt, mode == 'vocal')
                        self.assertEqual('Sing the supplied lyrics' in prompt, mode == 'vocal')
                        if region == 'nord':
                            self.assertIn('Tamriel (Elder Scrolls): Skyrim, unnamed venue.', prompt)

    def test_missing_instrumental_fields_and_instrument_name_fall_back(self):
        source = Path(__file__).resolve().parents[1] / 'dashboard/palette-data.json'
        palette = json.loads(source.read_text(encoding='utf-8'))
        profile = next(p for p in palette['existing'] if p['id'] == 'eastmarch')
        for field in ('core_instrumental', 'lute_instrumental', 'workshop'):
            profile.pop(field, None)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'palette.json'
            path.write_text(json.dumps(palette), encoding='utf-8')
            prompt = music_prompt('eastmarch', 'instrumental', 'female', palette_path=path)
        self.assertIn(profile['core'] + '.', prompt)
        self.assertIn('Lute: ' + profile['lute'] + '.', prompt)
        self.assertIn('One adult female performer; solo lute instrumental; plucked strings.', prompt)


if __name__ == '__main__':
    unittest.main()
