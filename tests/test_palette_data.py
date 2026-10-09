"""Validate editorial arrangement policies without running providers or the game."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tools import build_palette_data as builder


class ArrangementPolicyTests(unittest.TestCase):
    def test_every_active_profile_has_supported_instruments_and_explained_omissions(self):
        data, _ = builder.build_dataset()
        profiles = data['finalists'] + data['existing']
        for profile in profiles:
            with self.subTest(profile=profile['id']):
                policy = profile['workshop']
                self.assertEqual(set(policy['allowed']) | set(policy['omitted']), builder.ARRANGEMENTS)
                self.assertFalse(set(policy['allowed']) & set(policy['omitted']))
                self.assertIn(policy['plucked'], ('lute', 'cittern', 'oud', 'sitar', 'biwa', 'plucked zither (kacapi)'))
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
            lambda d: d['cultures']['khajiit'].update(drum_reference=''),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                doc = deepcopy(original)
                mutation(doc)
                with patch.object(builder, 'documents', return_value=doc), self.assertRaises(builder.BuildError):
                    builder.build_dataset()
