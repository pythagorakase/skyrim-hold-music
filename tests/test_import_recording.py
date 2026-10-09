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
from tools.import_recording import ffmpeg_arguments, import_recording, main


class ImportRecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'existing recording.mp3'
        self.source.write_bytes(b'mock mp3 source bytes')
        self.lyrics = self.root / 'lyrics.txt'
        self.lyrics.write_text('The lantern warms the winding road.\nWe share the light and lift the load.\n')
        self.args = dict(library=self.root / 'library', performer='mikael', region='whiterun',
                         mode='vocal', gender='male', source=self.source, lyrics=self.lyrics)

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
        with patch('tools.import_recording.shutil.which', return_value='/mock/ffmpeg'), \
             patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg) as run:
            row = import_recording(**self.args)
            second = import_recording(**self.args)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(row['slot'], 1)
        self.assertEqual(second['slot'], 2)
        self.assertEqual(row['composition_id'], second['composition_id'])
        self.assertEqual(row['source'], {'kind': 'import', 'path_or_request_id': str(self.source.resolve()),
                                         'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()})
        self.assertEqual(row['recipe_id'], 'whiterun/vocal')
        self.assertEqual(row['model_id'], 'google/lyria-3-pro-preview')
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
        with patch('tools.import_recording.shutil.which', return_value='/mock/ffmpeg'), \
             patch('tools.import_recording.subprocess.run', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'conversion failed: bad input'):
                import_recording(**self.args)
        self.assertEqual(list(self.args['library'].iterdir()), [])

    def test_instrumental_lyrics_rejected_before_conversion(self):
        with patch('tools.import_recording.shutil.which', return_value='/mock/ffmpeg'), \
             patch('tools.import_recording.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, '--lyrics requires vocal'):
                import_recording(**dict(self.args, mode='instrumental'))
            run.assert_not_called()

    def test_cli_prints_json(self):
        arguments = ['--library', str(self.args['library']), '--performer', 'mikael',
                     '--region', 'whiterun', '--mode', 'vocal', '--gender', 'male',
                     '--source', str(self.source), '--lyrics', str(self.lyrics), '--ffmpeg', '/mock/ffmpeg']
        output = io.StringIO()
        with patch('tools.import_recording.shutil.which', return_value='/mock/ffmpeg'), \
             patch('tools.import_recording.subprocess.run', side_effect=self.fake_ffmpeg), \
             contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments), 0)
        self.assertEqual(json.loads(output.getvalue())['file'], 'hm_slot_01.wav')


if __name__ == '__main__':
    unittest.main()
