from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.contract_migration import review_contract_migration
from hold_music.installed_library import AUDIO_PATH, MANIFEST_PATH, RECEIPTS_PATH, inspect_installed_library
from hold_music.runtime_contract import RUNTIME_CONTRACT_FIELDS, runtime_identity_key


class ContractMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.mo2 = self.base / 'MO2'
        self.high = self.mo2 / 'mods/High'
        self.low = self.mo2 / 'mods/Low'
        self.high.mkdir(parents=True)
        self.low.mkdir(parents=True)
        self.write(self.mo2 / 'profiles/Pilot/modlist.txt', b'+High\n+Low\n')
        self.r1 = self.row(1, revision='r1')
        self.r2 = self.row(2, revision='r2')
        self.legacy = self.row(3, versioned=False)
        self.other = self.row(4, performer='mikael', versioned=False)
        self.manifest = dict(version=1, slots=24, recordings=[self.r1, self.r2, self.legacy, self.other],
                             runtime_selection=dict(version=1, contracts=[self.contract(self.r1)]),
                             custom={'retain': ['unknown', {'value': True}]},
                             generation_receipts=[dict(id='paid-fixture', performer_id='sven', save_id='save',
                                world_id='world', at_hours=1, action='generate_recording')])
        self.publish_fixture()
        self.proposal_path = self.base / 'proposal.json'
        self.proposal(self.contract(self.r2))

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def json(self, path, value):
        self.write(path, json.dumps(value).encode('utf-8'))

    def row(self, slot, performer='sven', revision='r1', versioned=True, mode='instrumental'):
        value = dict(slot=slot, file=f'hm_slot_{slot:02d}.wav', performer_id=performer, region='whiterun',
                     mode=mode, gender='male', composition_id=f'fixture:{slot}', duration_seconds=.01,
                     lyrics_sha256=None, recipe_id='fixture/recipe', model_id='fixture/model',
                     created_at='2026-10-20T00:00:00Z', source=dict(kind='import', path_or_request_id='fixture'),
                     playable=True)
        if versioned:
            value.update(recipe_revision=revision, instrument_family='plucked_string', instrument_name='cittern',
                         arrangement='solo_lute' if mode == 'instrumental' else 'solo_lute_and_voice',
                         voice='none' if mode == 'instrumental' else 'male')
            value['identity_key'] = runtime_identity_key(value)
        return value

    def contract(self, row):
        return {key: row[key] for key in (*RUNTIME_CONTRACT_FIELDS, 'identity_key')}

    def proposal(self, *contracts):
        self.json(self.proposal_path, dict(version=1, contracts=list(contracts)))

    def publish_fixture(self):
        self.json(self.low / MANIFEST_PATH, self.manifest)
        self.json(self.low / RECEIPTS_PATH, dict(version=1, performances=[]))
        for row in self.manifest['recordings']:
            if not isinstance(row, dict) or type(row.get('slot')) is not int:
                continue
            path = (self.high if row['slot'] % 2 == 0 else self.low) / AUDIO_PATH / row['file']
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                continue
            with wave.open(str(path), 'wb') as stream:
                stream.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
                stream.writeframes(b'\x00\x00' * 441)

    def review(self, **kwargs):
        return review_contract_migration(self.mo2, 'Pilot', self.proposal_path, **kwargs)

    def codes(self, report):
        return {item['code'] for item in report['blockers']}

    def test_revision_upsert_impacts_preserve_every_original_row_and_extra(self):
        before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.base.rglob('*') if path.is_file()}
        report = self.review()
        self.assertEqual(report['status'], 'reviewed')
        self.assertEqual(report['scope'], 'candidate_selection_identity_audit')
        self.assertTrue(report['projection_possible'])
        self.assertEqual([item['before']['identity_eligible'] for item in report['rows']], [True, False, False, True])
        self.assertEqual([item['after']['identity_eligible'] for item in report['rows']], [False, True, False, True])
        self.assertEqual(report['projected_manifest']['recordings'], self.manifest['recordings'])
        self.assertEqual(report['projected_manifest']['custom'], self.manifest['custom'])
        self.assertEqual(report['projected_manifest']['generation_receipts'], self.manifest['generation_receipts'])
        self.assertEqual(report['projected_manifest']['runtime_selection']['contracts'], [self.contract(self.r2)])
        self.assertEqual(report['inspection_token'], inspect_installed_library(self.mo2, 'Pilot')['review_token'])
        self.assertTrue(all(report[key] is False for key in ('writes_performed', 'installed', 'vfs_verified', 'runtime_verified')))
        self.assertEqual(before, {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                                 for path in self.base.rglob('*') if path.is_file()})
        self.assertEqual(report['review_token'], self.review()['review_token'])

    def test_changes_name_concrete_unknown_and_mismatch_fields(self):
        report = self.review()
        self.assertIn('recipe_revision', [reason.get('field') for reason in report['rows'][0]['after']['reasons']])
        legacy = report['rows'][2]['after']
        unknown = {reason.get('field') for reason in legacy['reasons'] if reason['code'] == 'unknown_identity_field'}
        self.assertTrue({'recipe_revision', 'instrument_family', 'instrument_name', 'arrangement', 'voice', 'identity_key'} <= unknown)
        self.assertFalse(legacy['identity_eligible'])

    def test_unmentioned_contract_retained_and_new_contract_appended(self):
        extra = self.row(5, performer='lynly', revision='r1')
        self.manifest['recordings'].append(extra)
        self.manifest['runtime_selection']['contracts'].append(self.contract(extra))
        self.publish_fixture()
        report = self.review()
        contracts = report['proposed_runtime_selection']['contracts']
        self.assertEqual(contracts, [self.contract(self.r2), self.contract(extra)])
        lynly = next(item for item in report['performers'] if item['performer_id'] == 'lynly')
        self.assertEqual(lynly['change'], 'retained')
        self.assertEqual(lynly['before_contract'], lynly['after_contract'])

    def test_no_palette_or_recording_inference_for_new_performer(self):
        new = self.row(9, performer='new-performer', revision='never-generated')
        self.proposal(self.contract(new))
        report = self.review()
        self.assertIn('no_identity_eligible_recordings', self.codes(report))
        self.assertIn('no_available_asset_candidates', self.codes(report))
        self.assertEqual(report['proposed_runtime_selection']['contracts'],
                         [self.contract(self.r1), self.contract(new)])
        new_impact = next(item for item in report['performers'] if item['performer_id'] == 'new-performer')
        self.assertEqual(new_impact['identity_eligible_counts'], {'before': 0, 'after': 0})
        self.assertEqual(report['projected_manifest']['recordings'], self.manifest['recordings'])

    def test_disabled_matching_strict_row_is_identity_eligible_but_not_available(self):
        self.r2['playable'] = False
        self.publish_fixture()
        report = self.review()
        impact = report['rows'][1]
        self.assertTrue(impact['after']['identity_eligible'])
        self.assertTrue(impact['asset_valid'])
        self.assertFalse(impact['after']['metadata_eligible'])
        self.assertTrue(impact['after']['stored_playable_required'])
        self.assertIn('no_available_asset_candidates', self.codes(report))
        self.assertNotIn('no_identity_eligible_recordings', self.codes(report))

    def test_missing_assets_do_not_change_identity_and_inherit_blockers(self):
        (self.high / AUDIO_PATH / self.r2['file']).unlink()
        report = self.review()
        self.assertTrue(report['rows'][1]['after']['identity_eligible'])
        self.assertFalse(report['rows'][1]['asset_valid'])
        self.assertIn('missing_audio', self.codes(report))
        self.assertIn('no_available_asset_candidates', self.codes(report))
        self.assertTrue(any(item.get('origin') == 'inspection' for item in report['blockers']))

    def test_legacy_ignores_playable_and_preferred_mode_is_not_a_filter(self):
        self.other['playable'] = False
        self.other['mode'] = 'vocal'
        self.publish_fixture()
        report = self.review()
        row = report['rows'][3]
        self.assertEqual(row['before']['route'], 'legacy')
        self.assertTrue(row['before']['identity_eligible'])
        self.assertTrue(row['before']['metadata_eligible'])
        self.assertTrue(row['asset_valid'])
        self.assertFalse(row['before']['stored_playable_required'])
        performer = next(item for item in report['performers'] if item['performer_id'] == 'mikael')
        self.assertEqual(performer['available_asset_candidates'], {'before': 1, 'after': 1})
        self.assertIn('Preferred mode ranks candidates', ' '.join(report['limitations']))

    def test_receipt_reservations_are_separate_from_identity_and_asset_counts(self):
        self.json(self.mo2 / 'overwrite' / RECEIPTS_PATH, dict(version=1, performances=[
            dict(id='heard', performer_id='sven', composition_id=self.r2['composition_id'],
                 save_id='save', world_id='world', at_hours=3, slot=2, outcome='completed')]))
        report = self.review()
        self.assertIn('receipt_at_or_after_boundary', report['rows'][1]['reservation_reasons'])
        self.assertFalse(report['rows'][1]['live_session_locks_verified'])
        sven = next(item for item in report['performers'] if item['performer_id'] == 'sven')
        self.assertEqual(sven['available_asset_candidates']['after'], 1)
        self.assertEqual(report['status'], 'reviewed')

    def test_null_marker_suppresses_legacy_for_all_rows_of_performer(self):
        self.manifest.pop('runtime_selection')
        self.manifest['recordings'] = [self.legacy, dict(self.legacy, slot=6, file='hm_slot_06.wav', recipe_revision=None), self.other]
        self.publish_fixture()
        report = self.review()
        self.assertEqual([item['before']['route'] for item in report['rows']],
                         ['strict_missing_contract', 'strict_missing_contract', 'legacy'])
        self.assertFalse(report['rows'][0]['before']['identity_eligible'])
        self.assertIn('invalid_projected_manifest', self.codes(report))
        self.assertIn('recipe_revision', report['projected_manifest']['recordings'][1])
        self.assertIsNone(report['projected_manifest']['recordings'][1]['recipe_revision'])

    def test_nullable_trio_remains_preserved_and_blocks_projected_manifest(self):
        self.manifest.pop('runtime_selection')
        self.legacy.update(recipe_revision=None, instrument_family=None, instrument_name=None)
        self.manifest['recordings'] = [self.legacy]
        self.publish_fixture()
        report = self.review()
        self.assertEqual(report['projected_manifest']['recordings'], [self.legacy])
        self.assertIn('invalid_projected_manifest', self.codes(report))
        self.assertFalse(report['rows'][0]['before']['identity_eligible'])

    def test_missing_contract_for_versioned_performer_does_not_fallback(self):
        self.manifest.pop('runtime_selection')
        self.publish_fixture()
        report = self.review()
        self.assertEqual(report['rows'][0]['before']['route'], 'strict_missing_contract')
        self.assertFalse(report['rows'][2]['before']['identity_eligible'])
        self.assertTrue(report['rows'][1]['after']['identity_eligible'])
        self.assertTrue(report['rows'][3]['before']['identity_eligible'])

    def test_malformed_global_selection_blocks_every_performer_and_projection(self):
        for selection in (None, {}, {'version': True, 'contracts': []}, {'version': 1, 'contracts': [self.contract(self.r1), self.contract(self.r1)]}):
            with self.subTest(selection=selection):
                self.manifest['runtime_selection'] = selection
                self.publish_fixture()
                report = self.review()
                self.assertFalse(report['projection_possible'])
                self.assertIsNone(report['projected_manifest'])
                self.assertTrue(all(item['before']['route'] == 'blocked_global_selection' for item in report['rows']))
                self.assertTrue(all(not item['before']['identity_eligible'] for item in report['rows']))

    def test_proposal_cannot_remove_contracts_or_request_legacy_fallback(self):
        for proposal in (dict(version=1, contracts=[]), dict(version=1, contracts=[], remove=['sven']),
                         dict(version=1, contracts=[{'performer_id': 'sven', 'legacy': True}])):
            with self.subTest(proposal=proposal):
                self.json(self.proposal_path, proposal)
                report = self.review()
                self.assertIn('invalid_proposal', self.codes(report))
                self.assertFalse(report['projection_possible'])
                self.assertIsNone(report['projected_manifest'])

    def test_duplicate_json_keys_and_nonfinite_numbers_rejected(self):
        raw = self.proposal_path.read_bytes()
        for invalid in (raw[:-1] + b',"version":1}', raw.replace(b'"version": 1', b'"version": 1e999'), b'[]'):
            with self.subTest(invalid=invalid):
                self.proposal_path.write_bytes(invalid)
                report = self.review()
                self.assertIn('invalid_proposal', self.codes(report))
                self.assertIsNone(report['projected_manifest'])

    def test_invalid_proposal_contents_are_not_echoed(self):
        private = 'private-wrong-file-sentinel'
        self.json(self.proposal_path, dict(version=1, contracts=[self.contract(self.r2)], secret=private))
        report = self.review()
        self.assertIsNone(report['proposal']['runtime_selection'])
        self.assertIn('invalid_proposal', self.codes(report))
        self.assertNotIn(private, json.dumps(report))
        self.assertEqual(report['proposal']['sha256'], hashlib.sha256(self.proposal_path.read_bytes()).hexdigest())

    def test_changed_identity_fields_report_concrete_mismatches(self):
        for field, value in (('recipe_revision', 'r99'), ('instrument_name', 'vihuela'),
                             ('region', 'rift'), ('model_id', 'another-model'), ('recipe_id', 'another-recipe')):
            with self.subTest(field=field):
                contract = self.contract(self.r2)
                contract[field] = value
                contract['identity_key'] = runtime_identity_key(contract)
                self.proposal(contract)
                report = self.review()
                reasons = report['rows'][1]['after']['reasons']
                self.assertTrue(any(item['code'] == 'identity_field_mismatch' and item.get('field') == field
                                    and item['expected'] == value for item in reasons))
                self.assertIn('no_identity_eligible_recordings', self.codes(report))
        vocal = self.contract(self.row(8, mode='vocal'))
        self.proposal(vocal)
        report = self.review()
        self.assertIn('mode', {item.get('field') for item in report['rows'][1]['after']['reasons']})

    def test_performer_case_alias_blocks_instead_of_relabeling(self):
        contract = self.contract(self.r2)
        contract['performer_id'] = 'Sven'
        contract['identity_key'] = runtime_identity_key(contract)
        self.proposal(contract)
        report = self.review()
        self.assertIn('performer_case_alias', self.codes(report))
        self.assertFalse(report['projection_possible'])
        self.assertIsNone(report['projected_manifest'])

    def test_raw_malformed_rows_remain_enumerated_by_index(self):
        self.manifest['recordings'].extend([None, 7, dict(self.legacy, slot='wrong')])
        self.publish_fixture()
        report = self.review()
        self.assertEqual([item['index'] for item in report['rows']], list(range(7)))
        self.assertFalse(report['rows'][4]['before']['identity_eligible'])
        self.assertIsNone(report['rows'][4]['asset_valid'])
        self.assertEqual(report['projected_manifest']['recordings'], self.manifest['recordings'])
        self.assertTrue(report['projected_manifest_errors'])

    def test_corrupt_projected_digest_never_satisfies_contract(self):
        self.r2['identity_key'] = '0' * 64
        self.publish_fixture()
        report = self.review()
        self.assertFalse(report['rows'][1]['after']['identity_eligible'])
        self.assertIn('invalid_projected_manifest', self.codes(report))
        self.assertTrue(any(item['code'] == 'invalid_recording_identity' for item in report['rows'][1]['after']['reasons']))

    def test_unchanged_proposal_does_not_append_duplicate_contract(self):
        self.proposal(self.contract(self.r1))
        report = self.review()
        self.assertEqual(report['projected_manifest']['runtime_selection'], self.manifest['runtime_selection'])
        sven = next(item for item in report['performers'] if item['performer_id'] == 'sven')
        self.assertEqual(sven['change'], 'unchanged')
        self.assertEqual(sven['identity_eligible_counts'], {'before': 1, 'after': 1})

    def test_proposal_drift_after_inspection_is_rejected(self):
        def inspect_then_edit(*args, **kwargs):
            report = inspect_installed_library(*args, **kwargs)
            self.proposal(self.contract(self.r1))
            return report

        with patch('hold_music.contract_migration.inspect_installed_library', side_effect=inspect_then_edit), \
                self.assertRaisesRegex(ValueError, 'changed during inspection'):
            self.review()

    def test_installed_input_drift_after_inspection_is_rejected(self):
        def inspect_then_edit(*args, **kwargs):
            report = inspect_installed_library(*args, **kwargs)
            self.write(self.mo2 / 'overwrite' / MANIFEST_PATH, b'new higher winner')
            return report

        with patch('hold_music.contract_migration.inspect_installed_library', side_effect=inspect_then_edit), \
                self.assertRaisesRegex(ValueError, 'changed during inspection'):
            self.review()

    def test_receipt_change_changes_review_token_and_is_preserved(self):
        first = self.review()
        self.json(self.low / RECEIPTS_PATH, dict(version=1, performances=[
            dict(id='heard', performer_id='sven', composition_id='fixture:1', save_id='save', world_id='world',
                 at_hours=3, slot=1, outcome='completed')]))
        second = self.review()
        self.assertNotEqual(first['review_token'], second['review_token'])
        self.assertNotEqual(first['inspection_token'], second['inspection_token'])
        self.assertEqual(second['history']['performance_count'], 1)

    def test_hardlinked_and_symlinked_proposals_rejected(self):
        alias = self.base / 'proposal-alias.json'
        try:
            os.link(self.proposal_path, alias)
        except OSError:
            self.skipTest('Hard links unavailable')
        with self.assertRaises(ValueError):
            self.review()
        alias.unlink()
        try:
            alias.symlink_to(self.proposal_path)
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):
            review_contract_migration(self.mo2, 'Pilot', alias)


if __name__ == '__main__':
    unittest.main()
