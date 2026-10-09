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
