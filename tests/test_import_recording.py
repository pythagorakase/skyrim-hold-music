import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.library import Library
from hold_music.job_store import _writer_lock
from tools.import_recording import ffmpeg_arguments, import_recording, main, review_import_recording


class ImportRecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'existing recording.mp3'
        self.source.write_bytes(b'mock mp3 source bytes')
        self.lyrics = self.root / 'lyrics.txt'
        self.lyrics.write_text('The lantern warms the winding road.\nWe share the light and lift the load.\n')
        self.executable = self.root / 'fake-ffmpeg.exe'
        self.executable.write_bytes(b'fixture executable; subprocess is mocked')
        self.args = dict(library=self.root / 'library', performer='mikael', region='whiterun',
                         mode='vocal', gender='male', source=self.source, lyrics=self.lyrics,
                         ffmpeg=self.executable)
        self.which = patch('tools.import_recording.shutil.which', return_value=str(self.executable))
        self.which.start()
        self.addCleanup(self.which.stop)

    def fake_ffmpeg(self, args, **kwargs):
        self.assertEqual(kwargs, dict(check=True, capture_output=True, text=True))
        with wave.open(args[-1], 'wb') as stream:
            stream.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            stream.writeframes(b'\x00\x00' * 4410)

    def test_argument_construction_preserves_paths_and_explicit_pcm(self):
        command = ffmpeg_arguments('C:/Program Files/ffmpeg.exe', 'source file.mp3', 'out.wav')
        self.assertEqual(command, ['C:/Program Files/ffmpeg.exe', '-nostdin', '-hide_banner',
            '-loglevel', 'error', '-y', '-i', 'source file.mp3', '-vn', '-ac', '1', '-ar',
            '44100', '-sample_fmt', 's16', '-c:a', 'pcm_s16le', 'out.wav'])

    def test_import_manifest_and_provenance_without_executing_ffmpeg(self):
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg) as run:
            row = import_recording(**self.args)
            second = import_recording(**self.args)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(row['slot'], 1)
        self.assertEqual(second['slot'], 2)
        self.assertEqual(row['composition_id'], second['composition_id'])
        self.assertEqual(row['source'], {'kind': 'import', 'path_or_request_id': str(self.source.resolve()),
                                         'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()})
        self.assertEqual(row['recipe_id'], 'whiterun/vocal')
        self.assertEqual(row['model_id'], 'unknown')
        self.assertNotIn('recipe_revision', row)
        self.assertNotIn('instrument_family', row)
        self.assertNotIn('instrument_name', row)
        self.assertEqual(row['duration_seconds'], .1)
        self.assertTrue(row['playable'])
        self.assertEqual(Library(self.args['library']).validate(), [])
        manifest = json.loads((self.args['library'] / 'library.json').read_text())
        self.assertNotIn('generation_receipts', manifest)
        self.assertFalse(any(p.name.startswith('.import-') for p in self.args['library'].iterdir()))

    def test_missing_ffmpeg_names_the_flag_and_writes_nothing(self):
        with patch('tools.import_recording.shutil.which', return_value=None), \
             patch('tools.import_recording.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, '--ffmpeg'):
                import_recording(**self.args)
            run.assert_not_called()
        self.assertFalse(self.args['library'].exists())

    def test_failed_conversion_does_not_publish(self):
        error = subprocess.CalledProcessError(1, ['ffmpeg'], stderr='bad input')
        with patch('tools.import_recording.subprocess.run', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'conversion failed: bad input'):
                import_recording(**self.args)
        self.assertEqual([p.name for p in self.args['library'].iterdir()], ['.import.lock'])

    def test_instrumental_lyrics_rejected_before_conversion(self):
        with patch('tools.import_recording.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, '--lyrics requires vocal'):
                import_recording(**dict(self.args, mode='instrumental'))
            run.assert_not_called()

    def cli_arguments(self):
        return ['--library', str(self.args['library']), '--performer', 'mikael',
                '--region', 'whiterun', '--mode', 'vocal', '--gender', 'male',
                '--source', str(self.source), '--lyrics', str(self.lyrics),
                '--ffmpeg', str(self.executable)]

    def metadata(self, **updates):
        data = dict(version=1, performer_id='mikael', region='whiterun', mode='vocal',
                    gender='male', source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),
                    lyrics_sha256=hashlib.sha256(self.lyrics.read_bytes()).hexdigest(),
                    recipe_id='fixture/whiterun-vocal', recipe_revision='fixture-r1',
                    model_id='fixture/music-v1', instrument_family='plucked_string',
                    instrument_name='cittern', arrangement='solo_lute_and_voice', voice='male')
        data.update(updates)
        path = self.root / 'recording.metadata.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def no_publication(self):
        self.assertFalse((self.args['library'] / 'library.json').exists())
        self.assertFalse(list(self.args['library'].glob('hm_slot_*')))

    def test_cli_default_is_read_only_and_apply_requires_review(self):
        arguments = self.cli_arguments()
        output = io.StringIO()
        with patch('tools.import_recording.subprocess.run') as run, contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments), 0)
            run.assert_not_called()
        preview = json.loads(output.getvalue())
        self.assertEqual(preview['status'], 'import_dry_run')
        self.assertFalse(self.args['library'].exists())
        output = io.StringIO()
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg), \
                contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments + ['--apply', '--review-token', preview['review_token']]), 0)
        self.assertEqual(json.loads(output.getvalue())['recording']['file'], 'hm_slot_01.wav')

    def test_cli_rejects_apply_without_token_and_token_without_apply(self):
        for extra in (['--apply'], ['--review-token', 'test']):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()), \
                    patch('tools.import_recording.subprocess.run') as run, self.assertRaises(SystemExit) as result:
                main(self.cli_arguments() + extra)
            self.assertEqual(result.exception.code, 2)
            run.assert_not_called()
        self.assertFalse(self.args['library'].exists())

    def test_preview_does_not_write_and_hides_lyrics_content(self):
        before = {str(p.relative_to(self.root)): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        with patch('tools.import_recording.subprocess.run') as run:
            first = review_import_recording(**self.args)
            second = review_import_recording(**self.args)
        self.assertEqual(first['review_token'], second['review_token'])
        self.assertFalse(first['writes_performed'])
        self.assertFalse(first['runtime_verified'])
        self.assertNotIn('The lantern', json.dumps(first))
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes()
                                 for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse(self.args['library'].exists())
        run.assert_not_called()

    def test_explicit_identity_preserved_without_palette_inference(self):
        metadata = self.metadata()
        before = metadata.read_bytes()
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg):
            review = review_import_recording(**self.args, metadata=metadata)
            result = review_import_recording(**self.args, metadata=metadata, apply=True,
                                             review_token=review['review_token'])
        row = result['recording']
        self.assertEqual(row['recipe_id'], 'fixture/whiterun-vocal')
        self.assertEqual(row['recipe_revision'], 'fixture-r1')
        self.assertEqual(row['instrument_name'], 'cittern')
        self.assertEqual(row['model_id'], 'fixture/music-v1')
        self.assertEqual(row['voice'], 'male')
        self.assertEqual(row['source']['metadata_sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(row['source']['metadata_provenance'], 'operator_asserted')
        self.assertNotIn('identity_key', row)
        self.assertNotIn('runtime_selection', Library(self.args['library']).load().manifest)
        self.assertEqual(metadata.read_bytes(), before)
        self.assertEqual(Library(self.args['library']).validate(), [])

    def test_other_explicit_families_remain_offline_metadata(self):
        metadata = self.metadata(instrument_family='reedless_woodwind', instrument_name='venu',
                                 arrangement='solo_flute_and_voice')
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg):
            row = import_recording(**self.args, metadata=metadata)
        self.assertEqual(row['instrument_family'], 'reedless_woodwind')
        self.assertFalse(review_import_recording(**self.args, metadata=metadata)['runtime_verified'])

    def test_metadata_bad_fields_rejected_before_conversion_or_writes(self):
        cases = [
            {'source_sha256': '0' * 64}, {'lyrics_sha256': None}, {'performer_id': 'sven'},
            {'region': 'rift'}, {'mode': 'wordless'}, {'gender': 'female'},
            {'recipe_id': ''}, {'recipe_revision': None}, {'model_id': 42},
            {'instrument_family': ''}, {'instrument_name': []}, {'arrangement': True},
            {'voice': 'none'}, {'version': True}, {'version': 1.0}, {'extra': 'ignored?'},
        ]
        for updates in cases:
            with self.subTest(updates=updates), patch('tools.import_recording.subprocess.run') as run:
                metadata = self.metadata(**updates)
                with self.assertRaises(ValueError):
                    import_recording(**self.args, metadata=metadata)
                run.assert_not_called()
                self.assertFalse(self.args['library'].exists())

    def test_partial_duplicate_and_nonfinite_metadata_rejected(self):
        path = self.metadata()
        original = path.read_text()
        variants = [
            json.dumps({k: v for k, v in json.loads(original).items() if k != 'instrument_name'}),
            original[:-1] + ', "model_id": "second"}',
            original.replace('"version": 1', '"version": NaN'),
            '[]',
        ]
        for raw in variants:
            with self.subTest(raw=raw), patch('tools.import_recording.subprocess.run') as run:
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    review_import_recording(**self.args, metadata=path)
                run.assert_not_called()
        self.assertFalse(self.args['library'].exists())

    def test_instrumental_metadata_and_no_lyrics_hash(self):
        metadata = self.metadata(mode='instrumental', voice='none', arrangement='solo_lute',
                                 lyrics_sha256=None)
        args = dict(self.args, mode='instrumental', lyrics=None, metadata=metadata)
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg):
            row = import_recording(**args)
        self.assertIsNone(row['lyrics_sha256'])
        metadata = self.metadata(mode='instrumental', voice='male', arrangement='solo_lute',
                                 lyrics_sha256=None)
        with patch('tools.import_recording.subprocess.run') as run, self.assertRaisesRegex(ValueError, 'voice'):
            import_recording(**dict(args, metadata=metadata))
        run.assert_not_called()

    def test_invalid_or_missing_token_has_no_writes(self):
        for token in (None, '', 'stale', 'é' * 64, 12):
            with self.subTest(token=token), patch('tools.import_recording.subprocess.run') as run:
                result = review_import_recording(**self.args, apply=True, review_token=token)
                self.assertEqual(result['status'], 'blocked')
                self.assertFalse(self.args['library'].exists())
                run.assert_not_called()

    def test_source_and_lyrics_changes_stale_review_before_conversion(self):
        for path in (self.source, self.lyrics):
            with self.subTest(path=path), patch('tools.import_recording.subprocess.run') as run:
                preview = review_import_recording(**self.args)
                path.write_bytes(path.read_bytes() + b'\nchanged')
                result = review_import_recording(**self.args, apply=True, review_token=preview['review_token'])
                self.assertEqual(result['status'], 'blocked')
                run.assert_not_called()
                self.assertFalse(self.args['library'].exists())

    def test_metadata_identity_change_stales_review_before_conversion(self):
        path = self.metadata()
        preview = review_import_recording(**self.args, metadata=path)
        self.metadata(instrument_name='vihuela')
        with patch('tools.import_recording.subprocess.run') as run:
            result = review_import_recording(**self.args, metadata=path, apply=True,
                                             review_token=preview['review_token'])
        self.assertEqual(result['status'], 'blocked')
        run.assert_not_called()
        self.assertFalse(self.args['library'].exists())

    def test_ffmpeg_change_stales_review(self):
        preview = review_import_recording(**self.args)
        self.executable.write_bytes(b'changed executable')
        with patch('tools.import_recording.subprocess.run') as run:
            result = review_import_recording(**self.args, apply=True, review_token=preview['review_token'])
        self.assertEqual(result['status'], 'blocked')
        run.assert_not_called()

    def test_ffmpeg_symlink_allowed_and_target_change_stales_review(self):
        link = self.root / 'ffmpeg-link'
        try:
            link.symlink_to(self.executable)
        except OSError:
            self.skipTest('Symlink creation is unavailable')
        with patch('tools.import_recording.shutil.which', return_value=str(link)):
            preview = review_import_recording(**dict(self.args, ffmpeg=link))
            self.assertEqual(preview['plan']['ffmpeg']['path'], str(self.executable))
            self.assertEqual(preview['plan']['ffmpeg_lookup'], str(link))
            replacement = self.root / 'other-ffmpeg'
            replacement.write_bytes(self.executable.read_bytes())
            link.unlink()
            link.symlink_to(replacement)
            with patch('tools.import_recording.subprocess.run') as run:
                result = review_import_recording(**dict(self.args, ffmpeg=link), apply=True,
                                                 review_token=preview['review_token'])
            self.assertEqual(result['status'], 'blocked')
            run.assert_not_called()

    def test_new_occupancy_stales_review(self):
        preview = review_import_recording(**self.args)
        self.args['library'].mkdir()
        (self.args['library'] / 'hm_slot_01.wav').write_bytes(b'owned orphan')
        with patch('tools.import_recording.subprocess.run') as run:
            result = review_import_recording(**self.args, apply=True, review_token=preview['review_token'])
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual((self.args['library'] / 'hm_slot_01.wav').read_bytes(), b'owned orphan')
        run.assert_not_called()

    def receipts(self):
        path = self.root / 'external-receipts.json'
        path.write_text(json.dumps({'version': 1, 'performances': [
            dict(id='heard', performer_id='mikael', composition_id='old', save_id='save',
                 world_id='world', at_hours=12, slot=1, outcome='completed')
        ]}))
        return path

    def test_receipt_source_boundary_and_current_locks_bound_to_review(self):
        receipts = self.receipts()
        args = dict(self.args, receipts_path=receipts)
        preview = review_import_recording(**args)
        self.assertEqual(preview['plan']['slot'], 2)
        self.assertEqual(preview['plan']['locked_slots'], [1])
        self.assertEqual(preview['plan']['session_receipt_index'], 0)
        other = self.root / 'other-receipts.json'
        other.write_bytes(receipts.read_bytes())
        for changes in ({'receipts_path': other}, {'session_receipt_index': 1}):
            with self.subTest(changes=changes), patch('tools.import_recording.subprocess.run') as run:
                result = review_import_recording(**dict(args, **changes), apply=True,
                                                 review_token=preview['review_token'])
                self.assertEqual(result['status'], 'blocked')
                run.assert_not_called()
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg):
            result = review_import_recording(**args, apply=True, review_token=preview['review_token'])
        self.assertEqual(result['recording']['slot'], 2)
        self.assertFalse((self.args['library'] / 'receipts.json').exists())

    def test_returned_receipt_change_stales_review(self):
        path = self.receipts()
        preview = review_import_recording(**self.args, receipts_path=path)
        data = json.loads(path.read_text())
        data['performances'][0]['slot'] = 2
        path.write_text(json.dumps(data))
        with patch('tools.import_recording.subprocess.run') as run:
            result = review_import_recording(**self.args, receipts_path=path, apply=True,
                                             review_token=preview['review_token'])
        self.assertEqual(result['status'], 'blocked')
        run.assert_not_called()

    def test_receipt_boundary_cannot_exceed_actual_history(self):
        path = self.receipts()
        for index in (2, True, -1, '0'):
            with self.subTest(index=index), patch('tools.import_recording.subprocess.run') as run, \
                    self.assertRaises(ValueError):
                review_import_recording(**self.args, receipts_path=path, session_receipt_index=index)
            run.assert_not_called()
        self.assertFalse(self.args['library'].exists())

    def test_source_frozen_and_original_rechecked_after_conversion(self):
        original = self.source.read_bytes()

        def convert(command, **kwargs):
            frozen = Path(command[command.index('-i') + 1])
            self.assertNotEqual(frozen, self.source)
            self.assertEqual(frozen.read_bytes(), original)
            self.source.write_bytes(b'changed while converting')
            self.fake_ffmpeg(command, **kwargs)

        preview = review_import_recording(**self.args)
        with patch('tools.import_recording.subprocess.run', side_effect=convert), \
                self.assertRaisesRegex(ValueError, 'changed during conversion'):
            review_import_recording(**self.args, apply=True, review_token=preview['review_token'])
        self.no_publication()

    def test_lyrics_metadata_and_receipts_rechecked_after_conversion(self):
        for target in ('lyrics', 'metadata', 'receipts'):
            with self.subTest(target=target):
                metadata = self.metadata()
                receipts = self.receipts()
                path = {'lyrics': self.lyrics, 'metadata': metadata, 'receipts': receipts}[target]
                args = dict(self.args, metadata=metadata, receipts_path=receipts)
                preview = review_import_recording(**args)

                def convert(command, **kwargs):
                    path.write_bytes(path.read_bytes() + b' ')
                    self.fake_ffmpeg(command, **kwargs)

                with patch('tools.import_recording.subprocess.run', side_effect=convert), \
                        self.assertRaises(ValueError):
                    review_import_recording(**args, apply=True, review_token=preview['review_token'])
                self.no_publication()

    def test_frozen_source_tampering_blocks_publication(self):
        def convert(command, **kwargs):
            Path(command[command.index('-i') + 1]).write_bytes(b'tampered')
            self.fake_ffmpeg(command, **kwargs)

        with patch('tools.import_recording.subprocess.run', side_effect=convert), \
                self.assertRaisesRegex(ValueError, 'Frozen conversion input changed'):
            import_recording(**self.args)
        self.no_publication()

    def test_library_change_during_conversion_is_not_overwritten(self):
        def convert(command, **kwargs):
            (self.args['library'] / 'hm_slot_01.wav').write_bytes(b'external writer')
            self.fake_ffmpeg(command, **kwargs)

        with patch('tools.import_recording.subprocess.run', side_effect=convert), \
                self.assertRaisesRegex(ValueError, 'changed during conversion'):
            import_recording(**self.args)
        self.assertEqual((self.args['library'] / 'hm_slot_01.wav').read_bytes(), b'external writer')
        self.assertFalse((self.args['library'] / 'library.json').exists())

    def test_active_import_writer_blocks_conversion(self):
        preview = review_import_recording(**self.args)
        self.args['library'].mkdir()
        with _writer_lock(self.args['library'] / '.import.lock'), \
                patch('tools.import_recording.subprocess.run') as run, self.assertRaises(ValueError):
            review_import_recording(**self.args, apply=True, review_token=preview['review_token'])
        run.assert_not_called()
        self.no_publication()

    def test_cli_lock_error_is_concise(self):
        review = review_import_recording(**self.args)
        with patch('tools.import_recording._writer_lock', side_effect=RuntimeError('fixture writer busy')), \
                contextlib.redirect_stderr(io.StringIO()) as output, self.assertRaises(SystemExit) as result:
            main(self.cli_arguments() + ['--apply', '--review-token', review['review_token']])
        self.assertEqual(result.exception.code, 1)
        self.assertIn('Cannot import recording: fixture writer busy', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())

    def test_existing_recordings_preserved_without_relabeling(self):
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg):
            import_recording(**self.args)
        manifest_path = self.args['library'] / 'library.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['recordings'][0]['model_id'] = 'legacy-explicit-claim'
        manifest_path.write_text(json.dumps(manifest))
        old = manifest['recordings'][0]
        old_wav = (self.args['library'] / 'hm_slot_01.wav').read_bytes()
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg):
            import_recording(**self.args, metadata=self.metadata())
        updated = json.loads(manifest_path.read_text())
        self.assertEqual(updated['recordings'][0], old)
        self.assertEqual((self.args['library'] / 'hm_slot_01.wav').read_bytes(), old_wav)

    def test_repeated_apply_token_does_not_import_again(self):
        preview = review_import_recording(**self.args)
        with patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg) as run:
            first = review_import_recording(**self.args, apply=True, review_token=preview['review_token'])
            second = review_import_recording(**self.args, apply=True, review_token=preview['review_token'])
        self.assertEqual(first['status'], 'imported')
        self.assertEqual(second['status'], 'blocked')
        self.assertEqual(run.call_count, 1)

    def test_duplicate_library_keys_rejected_without_writes(self):
        self.args['library'].mkdir()
        path = self.args['library'] / 'library.json'
        raw = b'{"version":1,"slots":24,"recordings":[],"recordings":[]}'
        path.write_bytes(raw)
        with patch('tools.import_recording.subprocess.run') as run, self.assertRaisesRegex(ValueError, 'duplicate'):
            review_import_recording(**self.args)
        run.assert_not_called()
        self.assertEqual(path.read_bytes(), raw)
        self.assertFalse((self.args['library'] / '.import.lock').exists())

    def test_projected_runtime_library_requires_separate_staging(self):
        self.args['library'].mkdir()
        (self.args['library'] / 'library.json').write_text(json.dumps(
            dict(version=1, slots=24, recordings=[], runtime_selection={})))
        with patch('tools.import_recording.subprocess.run') as run, \
                self.assertRaisesRegex(ValueError, 'separate reviewed staging'):
            review_import_recording(**self.args, metadata=self.metadata())
        run.assert_not_called()

    def test_cli_stale_token_has_nonzero_blocked_json(self):
        arguments = ['--library', str(self.args['library']), '--performer', 'mikael',
                     '--region', 'whiterun', '--mode', 'vocal', '--gender', 'male',
                     '--source', str(self.source), '--lyrics', str(self.lyrics), '--ffmpeg', '/mock/ffmpeg']
        output = io.StringIO()
        with patch('tools.import_recording.subprocess.run') as run, \
             contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments + ['--apply', '--review-token', 'stale']), 2)
        self.assertEqual(json.loads(output.getvalue())['status'], 'blocked')
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
