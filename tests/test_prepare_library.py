from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hold_music.registry import DEFAULT_PATH
from tools.prepare_library import main
from hold_music.library import Library
from hold_music.runtime_paths import DEFAULT_MOD_NAME, storage_dirs


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

    def test_receipt_options_for_both_tools(self):
        from tools.snapshot_knowledge import main as snapshot_main
        root = Path(self.temp.name)
        dirs = storage_dirs(root / 'MO2', DEFAULT_MOD_NAME, 'Profile Data')
        dirs[2].mkdir(parents=True)
        discovered = dirs[2] / 'receipts.json'
        discovered.write_text('{"version": 1, "performances": []}')
        for tool, entrypoint in [('prepare_library', main), ('snapshot_knowledge', snapshot_main)]:
            for index, (extra, expected) in enumerate([
                ([], None), (['--receipts', str(discovered)], discovered),
                (['--mo2-root', str(root / 'MO2'), '--data-mod', 'Profile Data'], discovered),
                (['--mo2-root', str(root / 'missing')], None),
                (['--mo2-root', str(root / 'MO2'), '--mod-name', 'Profile Data'], discovered),
            ]):
                args = (self.args if tool == 'prepare_library' else
                        ['--db', str(root / 'unused.db'), '--registry', str(DEFAULT_PATH),
                         '--performer', 'sven', '--library', str(self.library),
                         '--out', str(root / f'snapshot-{index}.json')])
                with self.subTest(tool=tool, extra=extra), \
                        patch(f'tools.{tool}.Library', wraps=Library) as constructor, \
                        patch('tools.prepare_library.plan_work', return_value=[]), \
                        patch('tools.prepare_library.execute', return_value={'status': 'complete'}), \
                        patch('tools.snapshot_knowledge.snapshot', return_value=({}, {})), \
                        redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as diagnostic:
                    self.assertEqual(entrypoint(args + extra), 0)
                    constructor.assert_called_once_with(self.library, receipts_path=expected)
                    self.assertEqual(len(diagnostic.getvalue().splitlines()), 1)
                    self.assertIn(str(expected) if expected else 'library default applies', diagnostic.getvalue())

    def test_receipt_argument_conflicts_for_both_tools(self):
        from tools.snapshot_knowledge import main as snapshot_main
        for tool, entrypoint, args in [
            ('prepare_library', main, self.args),
            ('snapshot_knowledge', snapshot_main, ['--db', 'unused.db', '--registry', str(DEFAULT_PATH),
             '--performer', 'sven', '--library', str(self.library), '--out', 'unused.json']),
        ]:
            for extra in (['--receipts', 'a.json', '--mo2-root', 'MO2'],
                          ['--receipts', 'a.json', '--data-mod', 'Data'],
                          ['--receipts', 'a.json', '--mod-name', 'Music'],
                          ['--data-mod', 'Data'], ['--mod-name', 'Music']):
                with self.subTest(tool=tool, extra=extra), \
                        patch(f'tools.{tool}.Library') as library, redirect_stderr(io.StringIO()), \
                        self.assertRaises(SystemExit) as error:
                    entrypoint(args + extra)
                self.assertEqual(error.exception.code, 2)
                library.assert_not_called()

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
        for status in ('failed', 'budget_exceeded', 'recovery_required'):
            with patch('tools.prepare_library.execute', return_value={'status': status}), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(main(self.args + ['--spend']), 1)

    def test_job_inspection_does_not_create_library_or_read_credentials(self):
        with patch('tools.prepare_library.lyria_client.read_openrouter_key') as key, \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--library', str(self.library), '--job-status']), 0)
        self.assertEqual(json.loads(output.getvalue()), {'status': 'job_status', 'jobs': []})
        self.assertFalse(self.library.exists())
        key.assert_not_called()

    def test_recovery_flags_cannot_authorize_spending(self):
        for extra in (['--job-status', '--spend'], ['--recover-job', 'fixture', '--spend'],
                      ['--repair-journal', '--spend'],
                      ['--apply-recovery'], ['--job-status', '--recover-job', 'fixture']):
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()), \
                    patch('tools.prepare_library.lyria_client.read_openrouter_key') as key, \
                    self.assertRaises(SystemExit):
                main(['--library', str(self.library)] + extra)
            key.assert_not_called()
        self.assertFalse(self.library.exists())

    def test_recovery_honors_explicit_and_discovered_receipt_sources(self):
        root = Path(self.temp.name)
        dirs = storage_dirs(root / 'MO2', DEFAULT_MOD_NAME, 'Profile Data')
        dirs[2].mkdir(parents=True)
        discovered = dirs[2] / 'receipts.json'
        discovered.write_text('{"version": 1, "performances": []}')
        for extra, expected in [
            ([], None),
            (['--receipts', str(discovered)], discovered),
            (['--mo2-root', str(root / 'MO2'), '--data-mod', 'Profile Data'], discovered),
        ]:
            with self.subTest(extra=extra), \
                    patch('tools.prepare_library.Library', wraps=Library) as constructor, \
                    patch('tools.prepare_library.recover_publication',
                          return_value={'status': 'recovery_dry_run'}) as recover, \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as diagnostic:
                self.assertEqual(main(['--library', str(self.library), '--recover-job', 'fixture'] + extra), 0)
            constructor.assert_called_once_with(self.library, receipts_path=expected)
            self.assertEqual(recover.call_args.kwargs['library'].receipts_source,
                             expected or self.library / 'receipts.json')
            self.assertEqual(len(diagnostic.getvalue().splitlines()), 1)

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
