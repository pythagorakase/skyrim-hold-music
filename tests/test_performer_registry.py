import copy
import json
from pathlib import Path
import tempfile
import unittest

from hold_music.registry import DEFAULT_PATH, Registry, load_registry

ROOT = Path(__file__).resolve().parents[1]


class PerformerRegistryTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DEFAULT_PATH.read_text())
        self.registry = load_registry()

    def test_full_audited_roster_and_base_forms(self):
        names = {'Delacourt', 'Luaffyn', 'Talsgar the Wanderer', 'Lurbuk', 'Mikael',
                 'Karita', 'Sven', 'Ogmund', 'Lisette', 'Viarmo', 'Pantea Ateia',
                 'Ataf', 'Jorn', 'Inge Six Fingers', 'Illdi', 'Giraud Gemane',
                 'Aia Arria', 'Llewellyn the Nightingale', 'Sonir', 'Oriella', 'Lynly Star-Sung'}
        self.assertEqual({r['name'] for r in self.registry.performers}, names)
        self.assertEqual(len(self.registry.performers), 21)
        self.assertTrue(all(r['form'] for r in self.registry.performers))
        # Base forms read from Halcyon's roster.json, NOT biography/reference suffixes.
        expected = {'Mikael': '0x0001A670', 'Sven': '0x0001347F', 'Karita': '0x0001361A',
                    'Lynly Star-Sung': '0x000136BC', 'Sonir': '0x00019630'}
        for name, form in expected.items():
            self.assertEqual(self.registry.find_by_name(name)['form']['id'], form)
        self.assertEqual(self.registry.find_by_name('Sonir')['form']['plugin'], 'HearthFires.esm')

    def test_case_insensitive_exact_lookups(self):
        mikael = self.registry.find_by_name('MIKAEL')
        self.assertEqual(self.registry.find_by_form('sKyRiM.EsM', '01a670'), mikael)
        self.assertEqual(self.registry.find_by_form('skyrim.esm', 0x1A670), mikael)
        self.assertIsNone(self.registry.find_by_form('other.esp', '01A670'))
        self.assertIsNone(self.registry.find_by_name('Mika'))
        self.assertIsNone(self.registry.find_by_name(' Mikael'))

    def test_authored_regions_and_location_cross_check(self):
        locations = json.loads((ROOT / 'game_adapter/data/locations.json').read_text())['locations']
        expected = {'Sven': 'whiterun', 'Karita': 'pale', 'Lynly Star-Sung': 'rift',
                    'Llewellyn the Nightingale': 'falkreath', 'Sonir': 'hjaalmarch', 'Oriella': 'pale'}
        for row in self.registry.performers:
            venue = row['venue']
            if venue and locations.get(venue.casefold()) is not None:
                self.assertEqual(row['region'], locations[venue.casefold()], row['name'])
            if venue and venue.casefold() in locations and locations[venue.casefold()] is None:
                self.assertIn('venue ambiguous in locations.json; region authored', row['notes'])
            if venue == 'Bards College':
                self.assertEqual(row['region'], 'haafingar')
        for name, region in expected.items():
            self.assertEqual(self.registry.find_by_name(name)['region'], region)
        traveler = self.registry.find_by_name('Talsgar the Wanderer')
        self.assertIsNone(traveler['venue'])
        self.assertIsNone(traveler['region'])

    def test_traditions_exist_in_palette(self):
        ids = {r['id'] for r in json.loads((ROOT / 'dashboard/palette-data.json').read_text())['existing']}
        for row in self.registry.performers:
            self.assertLessEqual(set(row['traditions']), ids)
        self.assertEqual(self.registry.find_by_name('Luaffyn')['traditions'], ['eastmarch', 'dunmer'])

    def test_bad_registry_fields_and_duplicates(self):
        for field, value in [('id', ''), ('name', None), ('gender', 'unknown'), ('instrument', 'piano'),
                             ('region', 'solstheim'), ('venue', 3), ('traditions', 'whiterun'),
                             ('notes', None), ('form', {}), ('form', {'plugin': 'Skyrim.esm', 'id': '671'}),
                             ('form', {'plugin': '../Skyrim.esm', 'id': '0x0001A670'}),
                             ('form', {'plugin': 'Skyrim.esm', 'id': '0x0101A670'})]:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.data)
                data['performers'][0][field] = value
                with self.assertRaises(ValueError):
                    Registry(data)
        for field in ('id', 'name', 'form'):
            data = copy.deepcopy(self.data)
            data['performers'][1][field] = data['performers'][0][field]
            with self.assertRaises(ValueError):
                Registry(data)

    def test_nullable_form_and_custom_path(self):
        self.data['performers'][0]['form'] = None
        self.data['performers'][0]['notes'] += ' Form unresolved in roster.json.'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'registry.json'
            path.write_text(json.dumps(self.data))
            self.assertIsNone(load_registry(path).find_by_name('Delacourt')['form'])


if __name__ == '__main__':
    unittest.main()
