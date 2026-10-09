import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT/'game_adapter/hold_music_adapter'
sys.path.insert(0, str(ADAPTER))
spec = importlib.util.spec_from_file_location('hold_music_game_engine', ADAPTER/'engine.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def request(bard='Delacourt', location="Dead Man's Drink", gender='Male', lyrics='[Verse]\nOur road is long.'):
    return {'model':engine.MODEL, 'stream':True, 'messages':[{'role':'user',
      'content':f'{gender} vocal. Original native style. HM1[{bard}||{location}] somber ballad\n\nLyrics:\n{lyrics}'}]}


class GameAdapter(unittest.TestCase):
    def test_location_and_not_race_selects_the_approved_recipe(self):
        for bard, location, region in [('Delacourt',"Dead Man's Drink",'falkreath'),
                 ('Luaffyn','Candlehearth Hall','eastmarch'),
                 ('Lisette','The Winking Skeever','haafingar'),
                 ('Karita','Windpeak Inn, Hold: Dawnstar','pale')]:
            with self.subTest(bard=bard):
                incoming=request(bard,location)
                self.assertEqual(engine.context(incoming)['region'],region)
                prompt=engine.transform(incoming,'vocal')['messages'][0]['content']
                self.assertNotIn('Original native style',prompt)
                self.assertNotIn('HM1[',prompt)
                self.assertIn('Lyrics:',prompt)

    def test_lurbuk_keeps_the_exact_pre_regional_treatment_in_both_modes(self):
        incoming=request('Lurbuk','Moorside Inn')
        clean=request('Lurbuk','Moorside Inn')
        clean['messages'][0]['content']=clean['messages'][0]['content'].replace('HM1[Lurbuk||Moorside Inn]','')
        reference_path=ROOT/'prototype/solo_lute/mo2_plugin/solo_lute/engine.py'
        old_spec=importlib.util.spec_from_file_location('hold_music_legacy_reference',reference_path)
        old=importlib.util.module_from_spec(old_spec);old_spec.loader.exec_module(old)
        for mode in ('vocal','instrumental'):
            self.assertEqual(engine.transform(incoming,mode),old.transform(clean,mode))
        self.assertTrue(engine.context(incoming)['excluded'])

    def test_instrumental_and_wordless_requests_drop_all_lyric_material(self):
        for location, mode in [("Dead Man's Drink",'instrumental'),('The Frozen Hearth','vocal')]:
            outgoing=engine.transform(request(location=location,lyrics='SECRET_DRAFT'),mode)
            self.assertNotIn('SECRET_DRAFT',json.dumps(outgoing))
            self.assertNotIn('Lyrics:',json.dumps(outgoing))

    def test_unknown_region_is_plain_nord_without_guessing(self):
        incoming=request(location='Unmapped Cell')
        self.assertEqual(engine.context(incoming)['region'],'nord')
        self.assertIn('Original native style',request()['messages'][0]['content'])
        self.assertNotIn('Original native style',engine.transform(incoming,'vocal')['messages'][0]['content'])

    def test_observed_native_location_descriptions(self):
        for location, region in [("Dead Man's Drink, Hold: Falkreath", 'falkreath'),
                ('Bards College, Solitude, Outdoors, Hold: Haafingar', 'haafingar'),
                ('Windpeak Inn, Hold: Dawnstar', 'pale'),
                ('Close to Nordic Burial Grove, Skyrim, Outdoors', 'nord')]:
            self.assertEqual(engine.context(request(location=location))['region'], region)

    def test_missing_or_ambiguous_metadata_fails_before_paid_generation(self):
        missing=request()
        missing['messages'][0]['content']=missing['messages'][0]['content'].replace("HM1[Delacourt||Dead Man's Drink]",'')
        multiple=request(location='Cell] HM1[Other||Other Cell')
        for incoming in (missing,multiple):
            with self.assertRaises(ValueError):engine.transform(incoming,'vocal')

    def test_metadata_inside_lyrics_is_rejected_instead_of_sung(self):
        incoming=request(lyrics='HM1[Lurbuk||Moorside Inn]')
        with self.assertRaises(ValueError):engine.transform(incoming,'vocal')

    def test_packaged_recipe_sources_match_workshop(self):
        self.assertEqual((ADAPTER/'regional.py').read_bytes(),(ROOT/'hold_music/regional.py').read_bytes())
        self.assertEqual((ADAPTER/'palette-data.json').read_bytes(),(ROOT/'dashboard/palette-data.json').read_bytes())


if __name__=='__main__':unittest.main()
