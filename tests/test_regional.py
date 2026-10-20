import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy
import shutil
import subprocess
import sys

from hold_music.regional import (REGIONS, PALETTE, load_profiles, music_prompt, resolve_location,
                                 resolve_location_detail, performance_mode, freeze_recipe,
                                 prompt_from_recipe, recipe_fingerprint)


class RegionalRecipes(unittest.TestCase):
    def test_provisional_nine_regions_and_nord_fallback_are_available(self):
        _, profiles = load_profiles()
        self.assertEqual(set(profiles), set(REGIONS) | {'nord'})
        for region in (*REGIONS, 'nord'):
            for choice in ('instrumental', 'vocal'):
                text = music_prompt(region, choice, 'female', 'Unique lyric draft.')
                profile = profiles[region]
                for field in ('core', 'lute'):
                    clause = (profile.get(field + '_instrumental') or profile[field]) if performance_mode(region, choice) == 'instrumental' else profile[field]
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
        self.assertIn('One adult male performer; singing while playing lute; plucked strings.', text)
        self.assertIn('Wordless singing with vocables only; no lyrics, sentences or spoken words.', text)
        self.assertNotIn('UNUSED_VERSES', text)
        self.assertNotIn('Lyrics:', text)

    def test_lyrical_mode_preserves_actual_voice_and_exact_lyrics(self):
        lyric = '[Verse]\nA long road—home.\n'
        for gender in ('male', 'female'):
            text = music_prompt('falkreath', 'vocal', gender, lyric)
            self.assertIn(f'One adult {gender} performer; singing while playing plucked kantele; plucked strings.', text)
            self.assertNotIn('plucked plucked', text)
            self.assertTrue(text.endswith(lyric))

    def test_hjaalmarch_stays_instrumental_for_every_requested_mode(self):
        for choice in ('instrumental', 'vocal', 'wordless'):
            with self.subTest(choice=choice):
                self.assertEqual(performance_mode('hjaalmarch', choice), 'instrumental')
                text = music_prompt('hjaalmarch', choice, 'male', 'UNUSED_VERSES')
                self.assertIn('Entirely instrumental; no singing, humming or spoken words', text)
                self.assertIn('solo plucked kanklės instrumental; plucked strings.', text)
                self.assertIn('Plucked kanklės: ', text)
                self.assertNotIn('UNUSED_VERSES', text)
                self.assertNotIn('Voice:', text)
                self.assertNotIn('Lyrics:', text)

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
                        mode = performance_mode(region, choice)
                        adaptation = {'vocal': 'solo adaptation', 'wordless': 'solo wordless adaptation',
                                      'instrumental': 'instrumental reduction'}[mode]
                        styles = [line for line in prompt.splitlines() if line.startswith('Style: ')]
                        self.assertEqual(styles, [f"Style: {profiles[region]['reference']} ({adaptation})."])
                        self.assertEqual(prompt.count('One adult '), 1)
                        self.assertEqual(prompt.count('No bowed strings.'), 1)
                        self.assertNotIn('plucked plucked', prompt)
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
        self.assertIn('No bowed strings.', prompt)


class FrozenRecipes(unittest.TestCase):
    def test_regional_module_remains_standalone_for_the_mo2_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            module = root / 'regional.py'
            palette = root / 'palette-data.json'
            shutil.copyfile(PALETTE.parent.parent / 'hold_music' / 'regional.py', module)
            shutil.copyfile(PALETTE, palette)
            code = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location('standalone_regional', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.music_prompt('falkreath', 'vocal', 'female', 'Fixture words.', palette_path=sys.argv[2]))
"""
            result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', code,
                                     str(module), str(palette)], cwd=root, capture_output=True, text=True,
                                    encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), music_prompt('falkreath', 'vocal', 'female', 'Fixture words.'))

    def test_freeze_uses_one_palette_read_and_preserves_exact_lyrics_independent_direction(self):
        with patch.object(Path, 'read_text', autospec=True, side_effect=Path.read_text) as read:
            recipe = freeze_recipe('falkreath', 'vocal', 'female')
        self.assertEqual(read.call_count, 1)
        self.assertEqual(recipe['instrument_name'], 'plucked kantele')
        self.assertEqual(recipe['instrument_family'], 'plucked_string')
        self.assertEqual(recipe['arrangement'], 'solo_lute_and_voice')
        self.assertEqual(recipe['voice'], 'female')
        for lyrics in ('First exact verse.', 'Another verse.\n'):
            self.assertEqual(prompt_from_recipe(recipe, lyrics),
                             music_prompt('falkreath', 'vocal', 'female', lyrics))
        self.assertNotIn('Lyrics:', recipe['prompt_prefix'])
        self.assertEqual(recipe['recipe_revision'], recipe_fingerprint(recipe))

    def test_fingerprint_changes_for_actual_direction_and_identity_not_unrelated_notes(self):
        original = json.loads(PALETTE.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'palette.json'
            path.write_text(json.dumps(original), encoding='utf-8')
            before = freeze_recipe('pale', 'instrumental', 'female', path)
            unrelated = deepcopy(original)
            unrelated['unrelated_note'] = 'No prompt change.'
            next(p for p in unrelated['existing'] if p['id'] == 'rift')['core'] += ' Unrelated recipe.'
            path.write_text(json.dumps(unrelated), encoding='utf-8')
            self.assertEqual(freeze_recipe('pale', 'instrumental', 'female', path), before)
            for field in ('instrument', 'direction', 'region_label'):
                changed = deepcopy(original)
                profile = next(p for p in changed['existing'] if p['id'] == 'pale')
                if field == 'instrument':
                    profile['workshop']['plucked'] = 'cittern'
                elif field == 'direction':
                    key = 'core_instrumental' if profile.get('core_instrumental') else 'core'
                    profile[key] += ' Distinct synthetic direction.'
                else:
                    changed['auditionRegions']['pale'] += ' synthetic venue'
                path.write_text(json.dumps(changed), encoding='utf-8')
                with self.subTest(field=field):
                    self.assertNotEqual(freeze_recipe('pale', 'instrumental', 'female', path)['recipe_revision'],
                                        before['recipe_revision'])
            path.write_text(json.dumps(original), encoding='utf-8')
            for options in (dict(gender='male'), dict(choice='vocal'), dict(model_id='fixture/other-model')):
                args = dict(region='pale', choice='instrumental', gender='female', palette_path=path)
                args.update(options)
                self.assertNotEqual(freeze_recipe(**args)['recipe_revision'], before['recipe_revision'])

    def test_instrumental_and_wordless_identities_describe_actual_voice(self):
        instrumental = freeze_recipe('hjaalmarch', 'vocal', 'male')
        self.assertEqual(instrumental['mode'], 'instrumental')
        self.assertEqual(instrumental['voice'], 'none')
        self.assertEqual(instrumental['arrangement'], 'solo_lute')
        self.assertEqual(instrumental['instrument_name'], 'plucked kanklės')
        wordless = freeze_recipe('winterhold', 'vocal', 'male')
        self.assertEqual(wordless['mode'], 'wordless')
        self.assertEqual(wordless['voice'], 'male')
        self.assertEqual(wordless['arrangement'], 'solo_lute_and_voice')


if __name__ == '__main__':
    unittest.main()
