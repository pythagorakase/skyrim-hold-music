"""Compiled-PEX evidence: diagnostic reads must not change ownership admission."""
import copy
import unittest

from pex_vm import VM


class OwnershipDiagnosticTests(unittest.TestCase):
    def fields(self, vm, performer='sven', raw_owner='hold_music'):
        detail = vm.run('hm_library', 'OwnershipDiagnostic', performer, raw_owner)
        return dict(part.split('=', 1) for part in detail.split())

    def test_expected_property_and_matched_owner_are_reported_without_writes(self):
        vm = VM()
        files, effects, state = copy.deepcopy(vm.files), list(vm.effects), copy.deepcopy(vm.state)
        self.assertEqual(self.fields(vm), {
            'diag_v': '1', 'diag_registry': 'expected',
            'diag_registry_bytes': str(len('../HoldMusic/registry.json')),
            'diag_row': '1', 'diag_rows': '3',
            'diag_owner_type': 'string', 'diag_owner_class': 'hold_music'})
        self.assertEqual(vm.files, files)
        self.assertEqual(vm.effects, effects)
        self.assertEqual(vm.state, state)

    def test_exact_admission_read_is_classified_instead_of_reading_it_again(self):
        vm = VM()
        # A second read may differ; preserve evidence about the first comparison.
        row = vm.files['../HoldMusic/registry.json']['performers'][1]
        row['owner'] = 'hold_music'
        self.assertEqual(self.fields(vm, raw_owner='')['diag_owner_class'], 'empty')
        self.assertEqual(self.fields(vm, raw_owner='skyrimnet')['diag_owner_class'], 'skyrimnet')
        self.assertEqual(self.fields(vm, raw_owner='HOLD_MUSIC')['diag_owner_class'], 'hold_music')

    def test_unknown_owner_content_is_never_in_the_diagnostic(self):
        vm = VM()
        raw = 'private arbitrary value with spaces / and symbols'
        detail = vm.run('hm_library', 'OwnershipDiagnostic', 'sven', raw)
        self.assertNotIn(raw, detail)
        self.assertEqual(dict(part.split('=', 1) for part in detail.split())['diag_owner_class'], 'unknown')

    def test_owner_presence_and_json_types_are_distinguished(self):
        vm = VM()
        row = vm.files['../HoldMusic/registry.json']['performers'][1]
        cases = [(None, 'null_or_unresolved'), ('', 'string'), (False, 'bool'),
                 (0, 'number'), ([], 'array'), ({}, 'object')]
        for value, expected in cases:
            with self.subTest(value=value):
                row['owner'] = value
                fields = self.fields(vm, raw_owner='')
                self.assertEqual(fields['diag_owner_type'], expected)
                self.assertEqual(fields['diag_owner_class'], 'empty')
        del row['owner']
        self.assertEqual(self.fields(vm, raw_owner='')['diag_owner_type'], 'missing')

    def test_no_matching_row_is_distinct_from_missing_owner_member(self):
        vm = VM()
        fields = self.fields(vm, performer='absent', raw_owner='')
        self.assertEqual(fields['diag_row'], '-1')
        self.assertEqual(fields['diag_owner_type'], 'no_row')

    def test_case_insensitive_member_match_does_not_claim_a_resolved_json_null(self):
        vm = VM()
        row = vm.files['../HoldMusic/registry.json']['performers'][1]
        row['Owner'] = row.pop('owner')
        # Papyrus member-name comparison is case insensitive; native JSON paths
        # remain exact in this model. This is a diagnostic possibility, not a
        # claim about the cause of the observed session's failed lookup.
        raw = vm.run('hm_library', 'Owner', 'sven')
        self.assertEqual(raw, '')
        fields = self.fields(vm, raw_owner=raw)
        self.assertEqual(fields['diag_owner_type'], 'null_or_unresolved')
        self.assertEqual(fields['diag_owner_class'], 'empty')

    def test_saved_property_override_is_reported_without_disclosing_its_value(self):
        vm = VM()
        private_path = '../private-folder/registry-with-personal-name.json'
        vm.files[private_path] = copy.deepcopy(vm.files['../HoldMusic/registry.json'])
        vm.prop('hm_library', 'RegistryFile', private_path)
        fields = self.fields(vm)
        self.assertEqual(fields['diag_registry'], 'other')
        self.assertEqual(fields['diag_registry_bytes'], str(len(private_path)))
        self.assertEqual(fields['diag_row'], '1')
        self.assertNotIn(private_path, ' '.join(fields.values()))

    def test_diagnostic_row_search_is_bounded(self):
        vm = VM()
        vm.files['../HoldMusic/registry.json']['performers'] = [
            {'id': 'other', 'owner': 'skyrimnet'} for _ in range(512)
        ] + [{'id': 'sven', 'owner': 'hold_music'}]
        fields = self.fields(vm)
        self.assertEqual(fields['diag_rows'], '513')
        self.assertEqual(fields['diag_row'], '-1')
        self.assertEqual(fields['diag_owner_type'], 'no_row')

    def test_registered_candidates_emit_diagnostics_and_unknown_owner_stays_denied(self):
        for owner, expected in [('', 'empty'), ('unknown', 'unknown'), ('skyrimnet', 'skyrimnet')]:
            with self.subTest(owner=owner):
                vm = VM()
                # The shipped legacy VR package seeds this file. Newer source
                # can also initialize it, but absence is not this test's subject.
                vm.files['HoldMusic/trace.json'] = {'version': 1, 'entries': []}
                row = vm.files['../HoldMusic/registry.json']['performers'][1]
                row['owner'] = owner
                vm.candidates = ['Sven']
                vm.enter()
                vm.advance(15)
                self.assertFalse(any(effect[0] in ('play', 'idle', 'stop_vanilla') for effect in vm.effects))
                candidates = [r for r in vm.files['HoldMusic/trace.json']['entries']
                              if r['event'] == 'candidate']
                self.assertEqual(len(candidates), 1)
                self.assertIn('diag_owner_class=' + expected, candidates[0]['detail'])
                self.assertIn('diag_owner_type=string', candidates[0]['detail'])
                self.assertEqual(set(candidates[0]), {'seq', 'real_seconds', 'game_hours', 'event', 'detail'})
                self.assertFalse(vm.receipts)


if __name__ == '__main__':
    unittest.main()
