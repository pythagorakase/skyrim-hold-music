import unittest
from tools.build_game_locations import registry


class LocationRegistry(unittest.TestCase):
    def test_parent_chains_homonyms_cycles_and_unknowns(self):
        rows = [
            {'id': 'hold1', 'editor_id': 'FalkreathHoldLocation'},
            {'id': 'hold2', 'editor_id': 'EastmarchHoldLocation'},
            {'id': 'town', 'name': 'Falkreath', 'parent': 'hold1'},
            {'id': 'inn', 'name': "Dead Man's Drink", 'parent': 'town'},
            {'id': 'cell', 'name': 'Cell label', 'parent': 'inn'},
            {'id': 'ambig1', 'name': 'Shared name', 'parent': 'hold1'},
            {'id': 'ambig2', 'name': 'Shared name', 'parent': 'hold2'},
            {'id': 'unknown1', 'name': 'Generic Cave', 'parent': 'hold1'},
            {'id': 'unknown2', 'name': 'Generic Cave'},
            {'id': 'cycle1', 'name': 'Cycle One', 'parent': 'cycle2'},
            {'id': 'cycle2', 'name': 'Cycle Two', 'parent': 'cycle1'},
        ]
        result = registry(rows)
        self.assertEqual(result['locations']["dead man's drink"], 'falkreath')
        self.assertEqual(result['locations']['cell label'], 'falkreath')
        self.assertIsNone(result['locations']['shared name'])
        self.assertIsNone(result['locations']['generic cave'])
        self.assertNotIn('cycle one', result['locations'])


class ObservedLocations(unittest.TestCase):
    def test_live_location_descriptions_and_resolution_rules(self):
        import json
        from pathlib import Path
        from hold_music.regional import resolve_location_detail
        data = json.loads((Path(__file__).resolve().parents[1] / 'game_adapter/data/locations.json').read_text())
        cases = [
            ('The Bannered Mare, Hold: Whiterun', 'whiterun', 'suffix-table'),
            ('Sleeping Giant Inn, Hold: Riverwood', 'whiterun', 'suffix-registry'),
            ('Door to Heljarchen Hall, Hold: Heljarchen Hall', 'pale', 'suffix-registry'),
            ('Windpeak Inn, Hold: Dawnstar', 'pale', 'suffix-table'),
            ('Bards College, Solitude, Outdoors, Hold: Haafingar', 'haafingar', 'suffix-table'),
            ('Hold: The Pale', 'pale', 'suffix-table'),
            ('Hold: Falkreath', 'falkreath', 'suffix-table'),
            ('The Bannered Mare, Hold: Unknown', 'whiterun', 'segment-registry'),
            ('Whiterun, Hold: Whiterun Hold', 'whiterun', 'suffix-table'),
            ('Skyrim Wilderness, Outdoors', 'nord', 'default'),
            ('Sprightful Spriggan Inn, Hold: Oakwood', 'falkreath', 'suffix-registry'),
            ('Lakeview Manor, Hold: Lakeview Manor', 'falkreath', 'suffix-registry'),
            ('Nightgate Inn, Hold: Nightgate Inn', 'pale', 'suffix-registry'),
            ('Vilemyr Inn, Hold: Ivarstead', 'rift', 'suffix-registry'),
            ('The Frozen Hearth, Hold: Winterhold College', 'winterhold', 'suffix-registry'),
        ]
        for location, region, rule in cases:
            with self.subTest(location=location):
                self.assertEqual(resolve_location_detail(location, data), (region, rule))

    def test_exact_matching_normalization_and_precedence(self):
        from hold_music.regional import resolve_location_detail
        data = {'locations': {'the bannered mare': 'whiterun', 'solitude': 'rift',
                              'parent town': 'pale', 'unknown': 'rift', 'outdoors': 'rift',
                              'ambiguous inn': None, 'invalid inn': 'not-a-region'}}
        cases = [
            ('Road past The Bannered Mare', 'nord', 'default'),
            ('Hold: Near Parent Town', 'nord', 'default'),
            ('Hold: Near Whiterun', 'nord', 'default'),
            ('Ambiguous Inn', 'nord', 'default'),
            ('Invalid Inn', 'nord', 'default'),
            ('Outdoors, Unknown, Skyrim, Tamriel, Indoors, Interior, Exterior', 'nord', 'default'),
            ('The Bannered Mare, Solitude', 'whiterun', 'segment-registry'),
            ('Solitude, The Bannered Mare', 'haafingar', 'segment-table'),
            ('The Bannered Mare, Hold: Solitude', 'haafingar', 'suffix-table'),
            ('Solitude, Hold: Parent Town', 'pale', 'suffix-registry'),
            ('The Bannered Mare, Hold: None', 'whiterun', 'segment-registry'),
            ('The Bannered Mare, Hold:', 'whiterun', 'segment-registry'),
            ('The Bannered Mare, Hold: Unmapped', 'whiterun', 'segment-registry'),
            ('  [ "THE   BANNERED MARE" , [Outdoors], "Hold: Unknown" ].!?  ', 'whiterun', 'segment-registry'),
            ('Hold: Winterhold Hold', 'winterhold', 'suffix-table'),
            ('Hold: Eastmarch Hold', 'eastmarch', 'suffix-table'),
            ('Hold: Falkreath Hold', 'falkreath', 'suffix-table'),
            ('Hold: The Reach', 'reach', 'suffix-table'),
            ('Reach', 'reach', 'segment-table'),
            ('', 'nord', 'default'),
            (None, 'nord', 'default'),
        ]
        for location, region, rule in cases:
            with self.subTest(location=location):
                self.assertEqual(resolve_location_detail(location, data), (region, rule))
