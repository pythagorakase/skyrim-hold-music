import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.library import Library, wav_info
from hold_music.repertoire import Snapshot, plan

WORDS = 'The lantern warms the winding road.\nWe share the light and lift the load.\n'
REQUEST = dict(tradition='whiterun', arrangement='solo_lute_and_voice', mode='lyrical',
               voice='male', recipe_id='whiterun/vocal', model_id='test-model')


def make_wav(path, channels=1, width=2, rate=44100, frames=4410):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((channels, width, rate, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\0' * frames * channels * width)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'library'
        self.wav = Path(self.temp.name) / 'source.wav'
        make_wav(self.wav)
        self.library = Library(self.root)

    def add(self, **changes):
        args = dict(performer_id='mikael', region='whiterun', mode='vocal', gender='male',
                    composition_id='song', recipe_id='whiterun/vocal', model_id='test-model',
                    source={'kind': 'import', 'path_or_request_id': 'fixture.mp3'}, lyrics=WORDS)
        args.update(changes)
        return self.library.add_recording(self.wav, **args)

    def manifest(self):
        return json.loads((self.root / 'library.json').read_text())

    def write_manifest(self, data):
        (self.root / 'library.json').write_text(json.dumps(data))

    def receipts(self, **changes):
        row = dict(id='performance', slot=1, performer_id='mikael', composition_id='song',
                   save_id='save', world_id='world', at_hours=98, outcome='completed',
                   written_at='2026-10-09T12:00:00Z')
        row.update(changes)
        (self.root / 'receipts.json').write_text(json.dumps({'version': 1, 'performances': [row], 'extra': 7}))
        return row

    def snapshot(self, performer='mikael', **changes):
        args = dict(performer_id=performer, save_id='save', world_id='world', now_hours=100, request=REQUEST)
        args.update(changes)
        return self.library.snapshot(**args)

    def test_missing_library_and_receipts_are_empty_without_writes(self):
        self.assertEqual(self.library.validate(), [])
        self.assertEqual(self.library.free_slots(), list(range(1, 25)))
        self.assertFalse(self.root.exists())
        self.assertEqual(plan(self.snapshot())['action'], 'no_selection')

    def test_publication_filters_and_header(self):
        row = self.add()
        self.assertEqual(row['slot'], 1)
        self.assertTrue(row['playable'])
        self.assertAlmostEqual(row['duration_seconds'], .1)
        self.assertEqual(row['lyrics_sha256'], hashlib.sha256(WORDS.encode()).hexdigest())
        self.assertEqual((self.root / 'hm_slot_01.lyrics.txt').read_text(), WORDS)
        self.assertEqual(self.library.validate(), [])
        self.assertEqual(len(self.library.recordings_for('mikael', 'whiterun', 'vocal', 'male')), 1)
        for criteria in ({'performer_id': 'sven'}, {'region': 'rift'}, {'mode': 'wordless'}, {'gender': 'female'}):
            self.assertEqual(self.library.recordings_for(**criteria), [])
        self.assertEqual(wav_info(self.root / row['file'])['frames'], 4410)

    def test_planner_plays_own_rested_recording_not_another_performers(self):
        self.add()
        own = self.snapshot()
        Snapshot.from_dict(own)
        self.assertEqual(own['compositions'][0]['known_by'], ['mikael'])
        self.assertEqual(own['compositions'][0]['lyrics'], WORDS)
        self.assertEqual(plan(own)['action'], 'play_recording')
        self.assertEqual(plan(self.snapshot('sven'))['action'], 'no_selection')
        self.receipts(at_hours=90)
        self.assertEqual(plan(self.snapshot())['action'], 'play_recording')
        self.receipts(at_hours=99)
        self.assertEqual(plan(self.snapshot())['action'], 'no_selection')

    def test_receipt_outcomes_scope_and_unknown_keys(self):
        self.add()
        for outcome, action in [('completed', 'no_selection'), ('interrupted', 'no_selection'), ('failed', 'play_recording')]:
            self.receipts(outcome=outcome, extra={'future': True})
            self.assertEqual(self.library.validate(), [])
            self.assertEqual(plan(self.snapshot())['action'], action)
        for scope in ({'save_id': 'other'}, {'world_id': 'other'}, {'performer_id': 'sven'}, {'at_hours': 101}):
            self.receipts(**scope)
            self.assertEqual(plan(self.snapshot())['action'], 'play_recording')

    def test_partial_receipts_rejected_and_reported_without_helper_crash(self):
        self.add()
        self.receipts()
        with (self.root / 'receipts.json').open('a') as stream:
            stream.write('{partial')
        self.assertTrue(any('receipts.json' in p for p in self.library.validate()))
        self.assertEqual(self.library.performances, [])
        self.assertEqual(self.library.free_slots(), [])
        with self.assertRaisesRegex(ValueError, 'invalid library'):
            self.add(composition_id='new')

    def test_session_locks_survive_other_scopes_and_failed_outcomes(self):
        self.add()
        self.receipts(outcome='failed', save_id='different')
        self.library = Library(self.root, session_started_at='2026-10-09T11:00:00Z')
        self.assertTrue(self.library.load().recordings[0]['session_locked'])
        original = (self.root / 'hm_slot_01.wav').read_bytes()
        with self.assertRaisesRegex(ValueError, 'session locked'):
            self.add(slot=1)
        self.assertEqual((self.root / 'hm_slot_01.wav').read_bytes(), original)
        self.library.load(session_started_at='2026-10-09T12:00:00Z')
        self.assertFalse(self.library.recordings[0]['session_locked'])
        self.add(slot=1, composition_id='replacement')
        self.assertEqual(self.manifest()['recordings'][0]['composition_id'], 'replacement')

    def test_receipt_reserves_a_slot_even_when_manifest_entry_is_absent(self):
        self.add()
        self.receipts(slot=2)
        cache = Library(self.root, '2026-10-09T11:00:00Z')
        self.assertNotIn(2, cache.free_slots())
        self.assertEqual(cache.free_slots()[0], 3)

    def test_replacement_requires_boundary_and_removes_old_lyrics(self):
        self.add()
        with self.assertRaisesRegex(ValueError, 'session_started_at'):
            self.add(slot=1)
        self.library = Library(self.root, '2026-10-09T12:00:00Z')
        self.add(slot=1, mode='instrumental', lyrics=None, composition_id='instrumental', recipe_id='whiterun/instrumental')
        self.assertFalse((self.root / 'hm_slot_01.lyrics.txt').exists())
        snapshot = self.snapshot()
        request = snapshot['recordings'][0]['request']
        self.assertEqual(request['voice'], 'none')
        self.assertEqual(request['arrangement'], 'solo_lute')
        self.assertIsNone(snapshot['compositions'][0]['lyrics'])
        snapshot['request'] = request
        self.assertEqual(plan(snapshot)['action'], 'play_recording')

    def test_wordless_and_optional_request_fields(self):
        self.add(mode='wordless', lyrics=None, arrangement='solo_voice', voice='mikael-v1')
        snapshot = self.snapshot()
        request = snapshot['recordings'][0]['request']
        self.assertEqual(request['mode'], 'wordless')
        self.assertEqual(request['arrangement'], 'solo_voice')
        self.assertEqual(request['voice'], 'mikael-v1')
        snapshot['request'] = request
        self.assertEqual(plan(snapshot)['action'], 'play_recording')

    def test_vocal_without_lyrics_can_be_imported_but_cannot_supply_planner_composition(self):
        self.add(lyrics=None)
        self.assertEqual(self.library.validate(), [])
        snapshot = self.snapshot()
        self.assertEqual(snapshot['compositions'], [])
        self.assertTrue(any('snapshot omitted slot' in p for p in self.library.problems))
        self.assertEqual(plan(snapshot)['action'], 'no_selection')

    def test_lyrics_hash_mismatch_is_reported_and_excluded_from_snapshot(self):
        self.add()
        (self.root / 'hm_slot_01.lyrics.txt').write_text('Different words')
        self.assertTrue(any('hash differs' in p for p in self.library.validate()))
        self.assertEqual(plan(self.snapshot())['action'], 'no_selection')

    def test_missing_wrong_duration_and_truncated_audio_are_not_playable(self):
        self.add()
        path = self.root / 'hm_slot_01.wav'
        original = path.read_bytes()
        for data in (b'not WAV', original[:-10]):
            path.write_bytes(data)
            self.assertTrue(self.library.validate())
            self.assertFalse(self.library.recordings[0]['playable'])
        path.unlink()
        self.assertTrue(self.library.validate())
        self.assertFalse(self.library.recordings[0]['playable'])
        path.write_bytes(original)
        manifest = self.manifest()
        manifest['recordings'][0]['duration_seconds'] = 20
        self.write_manifest(manifest)
        self.assertTrue(any('duration differs' in p for p in self.library.validate()))
        self.assertFalse(self.library.recordings[0]['playable'])

    def test_wrong_audio_formats_rejected_before_publication(self):
        for params in ({'channels': 2}, {'width': 1}, {'rate': 48000}):
            make_wav(self.wav, **params)
            with self.assertRaisesRegex(ValueError, 'mono 16-bit PCM'):
                self.add()
            self.assertFalse(self.root.exists())

    def test_manifest_playable_flag_is_recomputed(self):
        self.add()
        manifest = self.manifest()
        manifest['recordings'][0]['playable'] = False
        self.write_manifest(manifest)
        self.assertTrue(self.library.load().recordings[0]['playable'])

    def test_compositions_are_deduplicated_and_immutable(self):
        self.add()
        self.add()
        self.assertEqual(len(self.snapshot()['compositions']), 1)
        self.assertEqual(len(self.snapshot()['recordings']), 2)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.add(lyrics='changed words')

    def test_instrumental_rendition_preserves_a_lyrical_composition(self):
        self.add(mode='instrumental', lyrics=None, recipe_id='whiterun/instrumental')
        self.add()
        snapshot = self.snapshot()
        self.assertEqual(len(snapshot['compositions']), 1)
        self.assertEqual(snapshot['compositions'][0]['mode'], 'lyrical')
        self.assertEqual(snapshot['compositions'][0]['lyrics'], WORDS)
        snapshot['request'] = snapshot['recordings'][0]['request']
        self.assertEqual(plan(snapshot)['action'], 'play_recording')
        self.assertEqual(plan(snapshot)['recording_id'], 'slot:01')

    def test_generation_history_preserves_exact_scope_and_time_without_import_receipts(self):
        receipt = dict(id='job-1', performer_id='mikael', save_id='save', world_id='world',
                       action='generate_recording', at_hours=99.5, provider='future-extra')
        self.add(generation_receipts=[receipt])
        history = self.snapshot()['generation_history']
        self.assertEqual(history, [dict(id='job-1', performer_id='mikael', save_id='save',
                                       world_id='world', action='generate_recording', at=99.5)])
        Snapshot.from_dict(self.snapshot())
        (self.root / 'hm_slot_01.wav').unlink()
        self.assertEqual(plan(self.snapshot())['action'], 'wait')
        with self.assertRaisesRegex(ValueError, 'generation receipts'):
            self.add(composition_id='new', generation_receipts=[receipt])

    def test_optional_runtime_timeline_never_leaks_to_other_saves_or_the_past(self):
        self.add(save_id='save', world_id='world', created_at_hours=101)
        self.assertEqual(plan(self.snapshot())['action'], 'no_selection')
        self.assertEqual(plan(self.snapshot(now_hours=102))['action'], 'play_recording')
        self.assertEqual(plan(self.snapshot(save_id='other', now_hours=102))['action'], 'no_selection')
        self.assertEqual(plan(self.snapshot(world_id='other', now_hours=102))['action'], 'no_selection')

    def test_malformed_json_shapes_and_fields_report_without_raising(self):
        self.add()
        valid = self.manifest()
        for value in (None, [], {}, {'version': 2, 'slots': '24', 'recordings': {}},
                      {'version': 1, 'slots': 24, 'recordings': [None, [], 'bad']}):
            self.write_manifest(value)
            self.assertTrue(self.library.validate())
        for field, value in [('slot', True), ('slot', 25), ('file', '../outside.wav'), ('mode', []),
                             ('gender', None), ('region', {}), ('duration_seconds', float('nan')),
                             ('created_at', 'yesterday'), ('source', []), ('lyrics_sha256', 'bad'),
                             ('performer_id', ''), ('composition_id', None), ('recipe_id', False),
                             ('model_id', ''), ('playable', 1), ('created_at_hours', -1)]:
            with self.subTest(field=field):
                data = copy.deepcopy(valid)
                data['recordings'][0][field] = value
                self.write_manifest(data)
                self.assertTrue(self.library.validate())
        self.write_manifest(valid)
        for row in (None, [], {}, {'id': 'x', 'slot': 'bad'}):
            (self.root / 'receipts.json').write_text(json.dumps({'version': 1, 'performances': [row]}))
            self.assertTrue(self.library.validate())

    def test_duplicates_and_unsafe_slot_names_report(self):
        self.add()
        data = self.manifest()
        data['recordings'].append(copy.deepcopy(data['recordings'][0]))
        self.write_manifest(data)
        self.assertTrue(any('duplicate slot' in p for p in self.library.validate()))
        self.assertEqual(self.library.free_slots(), [])

    def test_atomic_manifest_failure_restores_assets_and_cleans_temps(self):
        self.add()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.library = Library(self.root, '2026-10-09T12:00:00Z')
        with patch('hold_music.library._atomic_json', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.add(slot=1, composition_id='new', lyrics='new lyrics')
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)
        with patch('hold_music.library.os.replace', side_effect=OSError('replace failure')):
            from hold_music.library import _atomic_json
            with self.assertRaises(OSError):
                _atomic_json(self.root / 'library.json', {'new': True})
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_full_library_and_orphans_are_not_automatically_overwritten(self):
        self.root.mkdir()
        make_wav(self.root / 'hm_slot_01.wav')
        self.assertEqual(self.add()['slot'], 2)
        for slot in range(3, 25):
            self.add(slot=slot)
        self.assertEqual(self.library.free_slots(), [])
        with self.assertRaisesRegex(ValueError, 'No free'):
            self.add()


if __name__ == '__main__':
    unittest.main()
