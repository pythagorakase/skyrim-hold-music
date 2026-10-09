import unittest

from hold_music.regional import REGIONS, load_profiles, music_prompt, resolve_location


class RegionalRecipes(unittest.TestCase):
    def test_approved_nine_regions_and_nord_fallback_are_available(self):
        _, profiles = load_profiles()
        self.assertEqual(set(profiles), set(REGIONS) | {'nord'})
        for region in (*REGIONS, 'nord'):
            for choice in ('instrumental', 'vocal'):
                text = music_prompt(region, choice, 'female', 'Unique lyric draft.')
                self.assertIn(profiles[region]['core'], text)
                self.assertIn(profiles[region]['lute'], text)

    def test_instrumentals_never_receive_lyric_draft_or_voice_technique(self):
        _, profiles = load_profiles()
        for region in (*REGIONS, 'nord'):
            text = music_prompt(region, 'instrumental', 'female', 'PRIVATE_UNUSED_DRAFT')
            self.assertNotIn('PRIVATE_UNUSED_DRAFT', text)
            self.assertNotIn('Voice:', text)
            self.assertNotIn('female singer', text)
            self.assertIn('entirely instrumental', text)

    def test_winterhold_sung_half_is_wordless(self):
        text = music_prompt('winterhold', 'vocal', 'male', 'UNUSED_VERSES')
        self.assertIn('Wordless singing', text)
        self.assertIn('male singer', text)
        self.assertNotIn('UNUSED_VERSES', text)
        self.assertNotIn('Lyrics:', text)

    def test_lyrical_mode_preserves_actual_voice_and_exact_lyrics(self):
        lyric = '[Verse]\nA long road—home.\n'
        for gender in ('male', 'female'):
            text = music_prompt('falkreath', 'vocal', gender, lyric)
            self.assertIn(f'One {gender} singer', text)
            self.assertTrue(text.endswith(lyric))

    def test_location_resolution_does_not_guess_from_substrings(self):
        registry = {'locations': {"dead man's drink": 'falkreath', 'ambiguous inn': None}}
        self.assertEqual(resolve_location("  Dead Man's  Drink ", registry), 'falkreath')
        self.assertEqual(resolve_location('The road from Falkreath to Whiterun', registry), 'nord')
        self.assertEqual(resolve_location('Ambiguous Inn', registry), 'nord')


if __name__ == '__main__':
    unittest.main()
