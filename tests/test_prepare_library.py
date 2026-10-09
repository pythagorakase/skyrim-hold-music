from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hold_music.registry import DEFAULT_PATH
from tools.prepare_library import main


class PrepareLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.library = Path(self.temp.name) / 'library'
        self.args = ['--library', str(self.library), '--registry', str(DEFAULT_PATH),
                     '--performers', 'karita', '--modes', 'instrumental', '--target', '1']

    def test_default_dry_run_reads_no_key_and_makes_no_call_or_directory(self):
        with patch('tools.prepare_library.lyria_client.generate') as generate, \
                patch('tools.prepare_library.lyria_client.read_openrouter_key') as key, \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(self.args), 0)
        jobs = json.loads(output.getvalue())
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['performer_id'], 'karita')
        self.assertEqual(jobs[0]['region'], 'pale')
        generate.assert_not_called()
        key.assert_not_called()
        self.assertFalse(self.library.exists())

    def test_help(self):
        with redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as error:
            main(['--help'])
        self.assertEqual(error.exception.code, 0)
        for flag in ('--spend', '--max-usd', '--max-jobs', '--bardsinging', '--registry'):
            self.assertIn(flag, output.getvalue())

    def test_invalid_arguments(self):
        for extra in [['--target', '-1'], ['--max-jobs', '-1'], ['--max-usd', 'nan'],
                      ['--modes', 'vocal'], ['--performers', 'typo'], ['--modes', 'instrumental,']]:
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()), \
                    patch('tools.prepare_library.lyria_client.generate') as generate, \
                    self.assertRaises(SystemExit) as error:
                main(self.args + extra)
            self.assertNotEqual(error.exception.code, 0)
            generate.assert_not_called()

    def test_required_paths(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main([])

    def test_spend_passes_caps_ffmpeg_and_credentials_to_executor(self):
        report = dict(status='complete', recordings=[], cost_usd=.08)
        with patch('tools.prepare_library.execute', return_value=report) as execute, \
                redirect_stdout(io.StringIO()) as output:
            result = main(self.args + ['--spend', '--max-jobs', '2', '--max-usd', '0.16',
                                      '--ffmpeg', 'fixture ffmpeg', '--bardsinging', 'fixture.yaml'])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), report)
        args = execute.call_args.kwargs
        self.assertTrue(args['spend'])
        self.assertFalse(args['dry_run'])
        self.assertEqual(args['max_jobs'], 2)
        self.assertEqual(args['max_usd'], '0.16')
        self.assertEqual(args['ffmpeg'], 'fixture ffmpeg')
        with patch('tools.prepare_library.lyria_client.read_openrouter_key', return_value='fixture') as key, \
                patch('tools.prepare_library.lyria_client.generate') as generate:
            args['client'].generate('prompt')
        key.assert_called_once_with(Path('fixture.yaml'))
        generate.assert_called_once_with('prompt', key='fixture')

    def test_failed_run_has_nonzero_exit(self):
        for status in ('failed', 'budget_exceeded'):
            with patch('tools.prepare_library.execute', return_value={'status': status}), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(main(self.args + ['--spend']), 1)

    def test_zero_cap_does_not_read_key_even_with_spend(self):
        with patch('tools.prepare_library.lyria_client.generate') as generate, \
                patch('tools.prepare_library.lyria_client.read_openrouter_key') as key, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.args + ['--spend', '--max-jobs', '0']), 0)
        generate.assert_not_called()
        key.assert_not_called()


    def test_lyrical_requires_database(self):
        with redirect_stderr(io.StringIO()) as output, self.assertRaises(SystemExit):
            main(self.args + ['--modes', 'lyrical'])
        self.assertIn('lyrical mode requires --db', output.getvalue())

    def test_lyrical_cli_dry_run_private_by_default(self):
        from test_knowledge_bridge import make_database
        db = make_database(Path(self.temp.name) / 'SkyrimNet-fixture.db')
        with redirect_stdout(io.StringIO()) as output, \
                patch('tools.prepare_library.lyria_client.chat_completion') as chat, \
                patch('tools.prepare_library.lyria_client.read_openrouter_key') as key:
            self.assertEqual(main(self.args + ['--performers', 'mikael', '--modes', 'lyrical',
                '--db', str(db), '--allow-name-match', '--lyric-model', 'fixture-model']), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data['job_count'], 1)
        self.assertEqual(data['decisions'][0]['action'], 'compose_lyrics')
        self.assertNotIn('summary', output.getvalue())
        self.assertNotIn('event_data', output.getvalue())
        chat.assert_not_called()
        key.assert_not_called()

    def test_snapshot_cli_writes_only_named_private_output_and_reports_counts(self):
        from test_knowledge_bridge import make_database
        from tools.snapshot_knowledge import main as snapshot_main
        db = make_database(Path(self.temp.name) / 'SkyrimNet-fixture.db')
        dest = self.library / 'private-snapshot.json'
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(snapshot_main(['--db', str(db), '--registry', str(DEFAULT_PATH),
                '--performer', 'mikael', '--library', str(self.library), '--out', str(dest),
                '--allow-name-match', '--now-hours', '105']), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report['now_hours'], 105)
        self.assertTrue(report['uuid_resolved'])
        self.assertNotIn('fictional', output.getvalue())
        from hold_music.repertoire import Snapshot
        Snapshot.from_dict(json.loads(dest.read_text())['snapshot'])
        before = db.read_bytes()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            snapshot_main(['--db', str(db), '--registry', str(DEFAULT_PATH),
                '--performer', 'mikael', '--library', str(self.library), '--out', str(db)])
        self.assertEqual(before, db.read_bytes())


if __name__ == '__main__':
    unittest.main()
