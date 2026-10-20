"""Validate editorial arrangement policies without running providers or the game."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tools import build_palette_data as builder


class ArrangementPolicyTests(unittest.TestCase):
    def test_every_active_profile_has_supported_instruments_and_explained_omissions(self):
        data, _ = builder.build_dataset()
        profiles = data['finalists'] + data['existing'] + data['comparisons']
        for profile in profiles:
            with self.subTest(profile=profile['id']):
                policy = profile['workshop']
                self.assertEqual(set(policy['allowed']) | set(policy['omitted']), builder.ARRANGEMENTS)
                self.assertFalse(set(policy['allowed']) & set(policy['omitted']))
                self.assertIn(policy['plucked'], ('lute', 'cittern', 'oud', 'sitar', 'biwa',
                                                  'plucked zither (kacapi)', 'plucked kantele',
                                                  'plucked kanklės', 'Persian setar'))
                self.assertEqual(policy['family_rules']['plucked'], 'No bowed strings.')
                self.assertEqual(policy['family_rules']['flute'], 'No reed-driven sound.')
                self.assertTrue(profile['lute_instrumental'])
                for reason in policy['omitted'].values():
                    self.assertTrue(reason.strip())

    def test_invalid_policy_edits_fail_the_build(self):
        original = builder.documents(builder.DEFAULT_SPEC.read_text(encoding='utf-8'))
        mutations = [
            lambda d: d['workshop_arrangements'].pop('nord'),
            lambda d: d['workshop_arrangements']['nord'].update(allowed=['unknown']),
            lambda d: d['workshop_arrangements']['nord'].update(allowed=[{}]),
            lambda d: d['workshop_arrangements']['nord'].update(allowed=['lute', 'lute']),
            lambda d: d['workshop_arrangements']['khajiit'].update(allowed=['lute_voice']),
            lambda d: d['workshop_arrangements']['nord'].update(allowed=['trio']),
            lambda d: d['workshop_arrangements']['nord'].update(plucked=''),
            lambda d: d['workshop_omissions'].update(drum=''),
            lambda d: d['workshop_instrument_rules'].pop('flute'),
            lambda d: d['workshop_instrument_rules'].update(plucked=''),
            lambda d: d['cultures']['khajiit'].update(drum_reference=''),
            lambda d: d['workshop_baseline']['profiles'].pop('eastmarch'),
            lambda d: d['workshop_baseline']['profiles'].update(eastmarch={}),
            lambda d: d['workshop_baseline']['profiles']['hjaalmarch'].update(arrangement='lute_voice'),
            lambda d: d['workshop_baseline']['profiles']['winterhold'].update(vocal_mode='lyrics'),
            lambda d: d['workshop_baseline'].update(status='passed'),
            lambda d: d['workshop_baseline']['comparisons'].update(extra={}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                doc = deepcopy(original)
                mutation(doc)
                with patch.object(builder, 'documents', return_value=doc), self.assertRaises(builder.BuildError):
                    builder.build_dataset()

    def test_baseline_admits_only_eleven_bases_and_one_reach_challenger(self):
        data, _ = builder.build_dataset()
        profiles = {p['id']: p for p in data['finalists'] + data['existing'] + data['comparisons']}
        bases = set(data['baseline']['profiles'])
        self.assertEqual(bases, {'eastmarch', 'whiterun', 'reach', 'falkreath', 'rift',
                                'haafingar', 'hjaalmarch', 'winterhold', 'pale', 'dunmer', 'imperial'})
        self.assertEqual(data['baseline']['comparisons'], ['reach_sean_nos'])
        self.assertEqual(data['baseline']['status'], 'listening_pending')
        for ident, p in profiles.items():
            if ident in bases or ident == 'reach_sean_nos':
                self.assertIn(p['audition']['stage'], ('baseline', 'comparison'))
            else:
                self.assertEqual(p['audition']['stage'], 'deferred')
        self.assertEqual(profiles['imperial']['audition_region'], 'cyrodiil')
        self.assertEqual(profiles['dunmer']['audition_region'], 'raven_rock')
        self.assertEqual(profiles['reach_sean_nos']['audition_region'], 'reach')

    def test_baseline_preserves_named_instruments_without_changing_arrangement_families(self):
        data, _ = builder.build_dataset()
        profiles = {p['id']: p for p in data['existing'] + data['comparisons']}
        expected = {'whiterun': 'cittern', 'rift': 'cittern', 'falkreath': 'plucked kantele',
                    'hjaalmarch': 'plucked kanklės', 'dunmer': 'Persian setar'}
        for ident, instrument in expected.items():
            with self.subTest(profile=ident):
                profile = profiles[ident]
                self.assertEqual(profile['workshop']['plucked'], instrument)
                self.assertEqual(profile['audition']['arrangement'],
                                 'lute' if ident == 'hjaalmarch' else 'lute_voice')
        self.assertEqual(profiles['reach']['workshop']['plucked'],
                         profiles['reach_sean_nos']['workshop']['plucked'])
