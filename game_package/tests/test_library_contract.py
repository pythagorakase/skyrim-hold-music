"""Execute the compiled bridge against actual helper manifests and receipts."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hold_music.library import Library
from pex_vm import VM, require_pex


class LibraryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_pex()

    def test_helper_manifest_selected_and_game_receipts_read_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wav = root / 'source.wav'
            with wave.open(str(wav), 'wb') as stream:
                stream.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
                stream.writeframes(b'\0\0' * 441)
            library = Library(root / 'library', session_receipt_index=0)
            for mode in ('instrumental', 'wordless', 'vocal'):
                library.add_recording(wav, performer_id='mikael', region='whiterun',
                    mode=mode, gender='male', composition_id=mode, recipe_id='fixture',
                    model_id='fixture', source={'kind': 'import', 'path_or_request_id': str(wav)})
            v = VM()
            v.files['HoldMusic/library.json'] = json.loads((library.root / 'library.json').read_text())
            self.assertEqual(v.run('hm_library', 'ChooseSlot', 'mikael', 'whiterun', 'instrumental'), 1)
            self.assertEqual(v.run('hm_library', 'ChooseSlot', 'mikael', 'whiterun', 'vocal'), 2)
            self.assertAlmostEqual(v.run('hm_library', 'Duration'), .01)
            v.run('hm_library', 'AppendReceipt', 2, 'mikael', 'whiterun', 115.0, 'completed', '')
            self.assertEqual(v.run('hm_library', 'ChooseSlot', 'mikael', 'whiterun', 'vocal'), 3)
            v.run('hm_library', 'AppendReceipt', 3, 'mikael', 'whiterun', 116.0, 'interrupted', 'world')
            document = v.files['HoldMusic/receipts.json']
            self.assertEqual(set(document), {'version', 'performances'})
            self.assertEqual(document['version'], 1)
            for index, row in enumerate(document['performances']):
                self.assertEqual(set(row), {'id', 'slot', 'performer_id', 'region', 'composition_id',
                                          'save_id', 'world_id', 'at_hours', 'outcome', 'started_real_seconds'})
                self.assertEqual(row['id'], f'{index + 2}:{index}')
                self.assertEqual(row['at_hours'], 42.0 * 24.0)
                self.assertEqual(row['started_real_seconds'], 115.0 + index)
            (library.root / 'receipts.json').write_text(json.dumps(document))
            self.assertEqual(library.validate(), [])
            self.assertEqual([r['session_locked'] for r in library.recordings], [False, True, True])
            self.assertEqual(library.performances, document['performances'])

    def test_regionless_registered_performer_is_skipped(self):
        v = VM()
        row = next(r for r in v.files['../HoldMusic/registry.json']['performers'] if r['region'] is None)
        name = row['name']
        v.actors[name] = dict(v.actors['Mikael'], base=row['form']['id'])
        v.candidates = [name]
        v.files['HoldMusic/library.json']['recordings'][0].update(performer_id=row['id'], region='')
        self.assertEqual(v.run('hm_library', 'FindPerformer', name), row['id'])
        self.assertEqual(v.run('hm_library', 'Region', row['id']), '')
        v.enter(); v.advance(15)
        self.assertFalse(any(effect[0] == 'play' for effect in v.effects))
        self.assertEqual(v.state['hm_controller']['sessioncount'], 0)

    def test_process_clock_restart_clears_all_locks(self):
        v = VM(); v.enter(); v.advance(15)
        self.assertEqual(v.state['hm_controller']['lastrealtime'], 115.0)
        v.run('hm_library', 'LockSlot', 24)
        v.now = 5.0
        v.run('hm_controller', 'OnPlayerLoadGame')
        self.assertFalse(any(v.state['hm_library']['locked']))
        self.assertEqual(v.state['hm_controller']['lastrealtime'], 5.0)
        self.assertEqual(v.receipts[0]['outcome'], 'interrupted')
        self.assertEqual(v.run('hm_library', 'ChooseSlot', 'mikael', 'whiterun', 'instrumental'), 1)

    def test_same_process_load_keeps_locks_and_updates_clock(self):
        for now in (115.0, 200.0):
            with self.subTest(now=now):
                v = VM(); v.enter(); v.advance(15)
                v.run('hm_library', 'LockSlot', 24)
                v.now = now
                v.run('hm_controller', 'OnPlayerLoadGame')
                self.assertTrue(v.state['hm_library']['locked'][0])
                self.assertTrue(v.state['hm_library']['locked'][23])
                self.assertEqual(v.state['hm_controller']['lastrealtime'], now)
                self.assertEqual(v.run('hm_library', 'ChooseSlot', 'mikael', 'whiterun', 'instrumental'), 0)
