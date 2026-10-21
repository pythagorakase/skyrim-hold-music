"""Native receipt casing is adapted only in derived, exactly scoped history."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

from hold_music.library import Library
from hold_music.recording_identity import recording_request
from hold_music.repertoire import plan
from hold_music.runtime_contract import runtime_identity_key


class RuntimeReceiptAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'library'
        self.wav = Path(temporary.name) / 'synthetic.wav'
        with wave.open(str(self.wav), 'wb') as stream:
            stream.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            stream.writeframes(b'\0\0' * 441)
        self.library = Library(self.root, session_receipt_index=0)
        self.identity = dict(performer_id='sven', region='whiterun', mode='instrumental',
                             recipe_id='lab/synthetic-pluck', recipe_revision='lab-v1',
                             model_id='deterministic-pcm-fixture', instrument_family='plucked_string',
                             instrument_name='synthetic plucked-string test signal',
                             arrangement='solo_lute', voice='none')
        self.row = self.add()
        self.receipt = dict(id='1:1', slot=1, performer_id='Sven', region='Whiterun',
                            composition_id='lab:synthetic-pluck-v1',
                            save_id='20:Prisoner:0.340628', world_id='hold-music-se-lab',
                            at_hours=8.1759529113769531, started_real_seconds=30.730001449584961,
                            outcome='interrupted', runtime_identity=dict(
                                self.identity, version=1, identity_key=self.row['identity_key']))
        # Actual spellings emitted by the SE lab: the projected
        # key survives, but strings can inherit other BSFixedString casing.
        self.receipt['runtime_identity'].update(performer_id='Sven', region='Whiterun',
                                                mode='Instrumental', voice='None')
        self.write_receipts(self.receipt)

    def add(self, composition_id='lab:synthetic-pluck-v1', **changes):
        identity = dict(self.identity)
        identity.update({key: value for key, value in changes.items() if key in identity})
        extra = {key: value for key, value in changes.items() if key not in identity}
        return self.library.add_recording(self.wav, **identity, gender='male',
            composition_id=composition_id, identity_key=runtime_identity_key(identity),
            source={'kind': 'import', 'path_or_request_id': 'synthetic.wav'}, **extra)

    def write_receipts(self, *rows):
        (self.root / 'receipts.json').write_text(json.dumps({'version': 1, 'performances': rows}), encoding='utf-8')

    def snapshot(self, **changes):
        args = dict(performer_id='sven', save_id=self.receipt['save_id'],
                    world_id=self.receipt['world_id'], now_hours=self.receipt['at_hours'] + .1,
                    request=recording_request(self.row))
        args.update(changes)
        return self.library.snapshot(**args)

    def hashes(self):
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.iterdir() if path.is_file()}

    def test_actual_engine_case_preserves_raw_identity_and_honors_repeat_window(self):
        before = self.hashes()
        self.assertEqual(self.library.validate(), [])
        snapshot = self.snapshot()
        self.assertEqual(snapshot['recent_performances'][0]['performer_id'], 'sven')
        self.assertEqual(snapshot['request'], recording_request(self.row))
        self.assertNotEqual(plan(snapshot)['action'], 'play_recording')
        self.assertEqual(plan(self.snapshot(now_hours=self.receipt['at_hours'] + 4.1))['action'], 'play_recording')
        self.assertEqual(self.library.performances, [self.receipt])
        self.assertEqual(self.library.performances[0]['runtime_identity']['identity_key'], self.row['identity_key'])
        self.assertNotEqual(runtime_identity_key(self.receipt['runtime_identity']), self.row['identity_key'])
        self.assertIn(1, self.library._locked_slots)
        self.assertEqual(self.hashes(), before)

    def test_composition_alias_selects_unplayed_alternative(self):
        alternate = self.add(composition_id='another-composition')
        receipt = deepcopy(self.receipt)
        receipt['composition_id'] = receipt['composition_id'].upper()
        self.write_receipts(receipt)
        snapshot = self.snapshot()
        self.assertEqual(snapshot['recent_performances'][0]['composition_id'], self.row['composition_id'])
        decision = plan(snapshot)
        self.assertEqual(decision['action'], 'play_recording')
        self.assertEqual(decision['recording_id'], f"slot:{alternate['slot']:02d}")
        self.assertEqual(self.library.performances[0], receipt)

    def test_legacy_receipts_share_case_adapter_without_inventing_identity(self):
        receipt = deepcopy(self.receipt)
        del receipt['runtime_identity']
        self.write_receipts(receipt)
        self.assertNotEqual(plan(self.snapshot())['action'], 'play_recording')
        self.assertNotIn('runtime_identity', self.library.performances[0])

    def test_save_and_world_scope_remain_exact_even_for_case_aliases(self):
        for field in ('save_id', 'world_id'):
            with self.subTest(field=field):
                snapshot = self.snapshot(**{field: self.receipt[field].upper()})
                history = snapshot['recent_performances'][0]
                self.assertEqual(history[field], self.receipt[field])
                self.assertEqual(history['performer_id'], 'Sven')
                self.assertEqual(plan(snapshot)['action'], 'play_recording')

    def test_other_performer_and_future_history_are_not_relabelled(self):
        for changes in ({'performer_id': 'Other'}, {'at_hours': self.receipt['at_hours'] + 10}):
            with self.subTest(changes=changes):
                receipt = dict(self.receipt, **changes)
                self.write_receipts(receipt)
                snapshot = self.snapshot()
                self.assertEqual(snapshot['recent_performances'][0]['performer_id'], receipt['performer_id'])
                self.assertEqual(plan(snapshot)['action'], 'play_recording')

    def test_ambiguous_performer_spellings_stop_snapshot_even_on_exact_match(self):
        self.add(performer_id='Sven')
        for performer in ('Sven', 'sven', 'SVEN'):
            with self.subTest(performer=performer):
                self.write_receipts(dict(self.receipt, performer_id=performer))
                before = self.hashes()
                with self.assertRaisesRegex(ValueError, 'Ambiguous runtime receipt performer'):
                    self.snapshot()
                self.assertEqual(self.hashes(), before)

    def test_ambiguous_composition_spellings_stop_snapshot_even_on_exact_match(self):
        self.add(composition_id=self.row['composition_id'].upper())
        for composition in (self.row['composition_id'], self.row['composition_id'].upper()):
            with self.subTest(composition=composition):
                self.write_receipts(dict(self.receipt, composition_id=composition))
                with self.assertRaisesRegex(ValueError, 'Ambiguous runtime receipt composition'):
                    self.snapshot()

    def test_alias_from_other_source_scope_does_not_make_current_history_ambiguous(self):
        self.add(performer_id='Sven', save_id='other-save', world_id='other-world', created_at_hours=0)
        self.add(composition_id=self.row['composition_id'].upper(), save_id='other-save', world_id='other-world', created_at_hours=0)
        self.assertNotEqual(plan(self.snapshot())['action'], 'play_recording')

    def test_ambiguity_in_history_from_another_world_does_not_affect_current_plan(self):
        self.add(performer_id='Sven')
        self.write_receipts(dict(self.receipt, world_id='another-world'))
        self.assertEqual(plan(self.snapshot())['action'], 'play_recording')

    def test_unknown_composition_is_preserved_without_fabricating_source_identity(self):
        receipt = dict(self.receipt, composition_id='Unknown OLD Song')
        self.write_receipts(receipt)
        snapshot = self.snapshot()
        self.assertEqual(snapshot['recent_performances'][0]['performer_id'], 'sven')
        self.assertEqual(snapshot['recent_performances'][0]['composition_id'], receipt['composition_id'])
        self.assertEqual(plan(snapshot)['action'], 'play_recording')

    def test_unicode_casefold_expansions_do_not_alias_performer_or_composition(self):
        row = self.add(performer_id='stra\u00dfe', composition_id='stra\u00dfe-song')
        receipt = dict(self.receipt, performer_id='STRASSE', composition_id='STRASSE-SONG')
        self.write_receipts(receipt)
        snapshot = self.snapshot(performer_id='stra\u00dfe', request=recording_request(row))
        self.assertEqual(snapshot['recent_performances'][0]['performer_id'], 'STRASSE')
        self.assertEqual(plan(snapshot)['action'], 'play_recording')
        self.add(composition_id='stra\u00dfe-song')
        self.write_receipts(dict(receipt, performer_id='Sven'))
        snapshot = self.snapshot()
        self.assertEqual(snapshot['recent_performances'][0]['performer_id'], 'sven')
        self.assertEqual(snapshot['recent_performances'][0]['composition_id'], 'STRASSE-SONG')

    def test_generation_history_and_strict_recording_identity_are_not_normalized(self):
        document = json.loads((self.root / 'library.json').read_text())
        generation = dict(id='generation', performer_id='Sven', save_id=self.receipt['save_id'],
                          world_id=self.receipt['world_id'], at_hours=8,
                          action='generate_recording')
        document['generation_receipts'] = [generation]
        (self.root / 'library.json').write_text(json.dumps(document), encoding='utf-8')
        snapshot = self.snapshot()
        self.assertEqual(snapshot['generation_history'][0]['performer_id'], 'Sven')
        changed = dict(snapshot['request'], instrument_name=snapshot['request']['instrument_name'].upper())
        self.assertNotEqual(plan(self.snapshot(now_hours=20, request=changed))['action'], 'play_recording')
        self.assertEqual(self.library.manifest['recordings'][0]['identity_key'], self.row['identity_key'])


if __name__ == '__main__':
    unittest.main()
