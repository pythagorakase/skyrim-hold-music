"""CLI authorization, privacy and routing for explicitly reviewed retained jobs."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.prepare_library import main
from hold_music.job_store import inspect_jobs
from hold_music.lyria_client import StreamError
import test_executor as fixtures


class JobReviewCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        self.args = ['--library', str(self.library)]
        self.resolution = self.root / 'private-resolution.json'
        self.resolution.write_text(json.dumps(dict(outcome='confirmed_not_charged',
            cost_usd='0', evidence='PRIVATE operator evidence reference')), encoding='utf-8')

    def run_cli(self, extra):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            code = main(self.args + extra)
        return code, out.getvalue(), err.getvalue()

    def test_continuation_preview_needs_no_registry_credentials_or_spending(self):
        result = dict(status='continuation_dry_run', can_continue=True, review_token='fixture-token')
        with patch('tools.prepare_library.continue_job', return_value=result) as continued, \
                patch('tools.prepare_library.lyria_client.read_openrouter_key') as key, \
                patch('tools.prepare_library.load_registry') as registry:
            code, out, _ = self.run_cli(['--continue-job', 'job-one'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), result)
        kwargs = continued.call_args.kwargs
        self.assertEqual(continued.call_args.args, ('job-one',))
        self.assertTrue(kwargs['dry_run'])
        self.assertFalse(kwargs['spend'])
        self.assertIsNone(kwargs['review_token'])
        key.assert_not_called()
        registry.assert_not_called()
        self.assertFalse(self.library.exists())

    def test_continuation_apply_carries_review_budget_and_external_receipts(self):
        external = self.root / 'receipts.json'
        result = dict(status='complete')
        with patch('tools.prepare_library.continue_job', return_value=result) as continued:
            code, _, _ = self.run_cli(['--continue-job', 'job-one', '--spend',
                '--review-token', 'reviewed-token', '--max-usd', '0.12', '--max-jobs', '1',
                '--receipts', str(external), '--ffmpeg', 'fixture-encoder'])
        self.assertEqual(code, 0)
        kwargs = continued.call_args.kwargs
        self.assertFalse(kwargs['dry_run'])
        self.assertTrue(kwargs['spend'])
        self.assertEqual(kwargs['review_token'], 'reviewed-token')
        self.assertEqual(kwargs['max_usd'], '0.12')
        self.assertEqual(kwargs['max_jobs'], 1)
        self.assertEqual(kwargs['ffmpeg'], 'fixture-encoder')
        self.assertEqual(kwargs['library'].receipts_source, external)

    def test_reconciliation_preview_and_apply_never_construct_a_provider(self):
        for apply in (False, True):
            result = dict(status='reconciled' if apply else 'reconciliation_dry_run',
                          can_reconcile=True)
            extra = ['--reconcile-job', 'job-one', '--resolution-json', str(self.resolution)]
            if apply:
                extra += ['--apply-reconciliation', '--review-token', 'reviewed-token']
            with self.subTest(apply=apply), \
                    patch('tools.prepare_library.reconcile_job', return_value=result) as reconciled, \
                    patch('tools.prepare_library._Client') as provider:
                code, out, err = self.run_cli(extra)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out), result)
            self.assertNotIn('PRIVATE', out + err)
            self.assertEqual(reconciled.call_args.kwargs['apply'], apply)
            self.assertEqual(reconciled.call_args.kwargs['resolution']['cost_usd'], '0')
            provider.assert_not_called()
        self.assertFalse(self.library.exists())

    def test_contradictory_or_unreviewed_flags_fail_before_any_operation(self):
        for extra in [
            ['--continue-job', 'job', '--spend'],
            ['--reconcile-job', 'job'],
            ['--apply-reconciliation'],
            ['--reconcile-job', 'job', '--resolution-json', str(self.resolution), '--apply-reconciliation'],
            ['--reconcile-job', 'job', '--resolution-json', str(self.resolution), '--spend'],
            ['--continue-job', 'job', '--reconcile-job', 'job'],
            ['--continue-job', 'job', '--apply-recovery'],
            ['--continue-job', 'job', '--resolution-json', str(self.resolution)],
            ['--review-token', 'token'],
            ['--job-status', '--review-token', 'token'],
        ]:
            with self.subTest(extra=extra), \
                    patch('tools.prepare_library.continue_job') as continued, \
                    patch('tools.prepare_library.reconcile_job') as reconciled, \
                    patch('tools.prepare_library.lyria_client.read_openrouter_key') as key, \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(self.args + extra)
            continued.assert_not_called()
            reconciled.assert_not_called()
            key.assert_not_called()

    def test_malformed_private_resolution_does_not_leak_content(self):
        self.resolution.write_text('PRIVATE evidence must not leak {', encoding='utf-8')
        with patch('tools.prepare_library.reconcile_job') as reconciled, \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err, \
                self.assertRaises(SystemExit):
            main(self.args + ['--reconcile-job', 'job', '--resolution-json', str(self.resolution)])
        self.assertNotIn('PRIVATE', out.getvalue() + err.getvalue())
        self.assertIn('Cannot read private resolution JSON', err.getvalue())
        reconciled.assert_not_called()

    def test_blocked_operations_return_failure_status(self):
        cases = [
            ('continue_job', ['--continue-job', 'job'], dict(status='continuation_dry_run', can_continue=False)),
            ('reconcile_job', ['--reconcile-job', 'job', '--resolution-json', str(self.resolution)],
             dict(status='reconciliation_dry_run', can_reconcile=False)),
        ]
        for api, extra, report in cases:
            with self.subTest(api=api), patch(f'tools.prepare_library.{api}', return_value=report):
                code, out, _ = self.run_cli(extra)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out), report)


class RetainedJobCommandIntegrationTests(unittest.TestCase):
    setUp = fixtures.ExecutorTests.setUp
    run_jobs = fixtures.ExecutorTests.run_jobs
    lyrical_jobs = fixtures.LyricalExecutorTests.lyrical_jobs

    def command(self, extra):
        with patch('tools.prepare_library._Client', return_value=self.client), \
                patch('tools.prepare_library.lyria_client.read_openrouter_key') as key, \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            code = main(['--library', str(self.library.root)] + extra)
        key.assert_not_called()
        return code, json.loads(out.getvalue()), out.getvalue()

    def test_cli_continues_saved_lyrics_once_without_recomposition(self):
        self.lyrical_jobs()
        self.client.chat_completion.return_value['usage']['cost'] = .03
        job_id = self.run_jobs(max_usd=.10)['jobs'][0]
        journal = self.library.root / '.executor/jobs.sqlite3'
        before = journal.read_bytes()
        options = ['--continue-job', job_id, '--max-jobs', '1', '--max-usd', '0.10']
        code, preview, public = self.command(options)
        self.assertEqual(code, 0)
        self.assertTrue(preview['can_continue'])
        self.assertEqual(journal.read_bytes(), before)
        self.assertNotIn('[Verse]', public)
        self.client.generate.assert_not_called()
        apply = options + ['--review-token', preview['review_token'], '--spend']
        code, report, _ = self.command(apply)
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(self.client.chat_completion.call_count, 1)
        self.assertEqual(self.client.generate.call_count, 1)
        self.assertEqual(len(self.library.load().recordings), 1)
        code, repeated, _ = self.command(apply)
        self.assertEqual(code, 0)
        self.assertEqual(repeated['status'], 'already_applied')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_cli_operator_reconciliation_is_provider_free_and_retains_uncertainty(self):
        self.client.generate.side_effect = StreamError('PRIVATE uncertain provider response')
        job_id = self.run_jobs(max_jobs=1)['jobs'][0]
        resolution = Path(self.temp.name) / 'private-resolution.json'
        resolution.write_text(json.dumps(dict(outcome='confirmed_not_charged', cost_usd='0',
            evidence='PRIVATE checked provider reference')), encoding='utf-8')
        options = ['--reconcile-job', job_id, '--resolution-json', str(resolution)]
        journal = self.library.root / '.executor/jobs.sqlite3'
        before = journal.read_bytes()
        code, preview, public = self.command(options)
        self.assertEqual(code, 0)
        self.assertTrue(preview['can_reconcile'])
        self.assertEqual(journal.read_bytes(), before)
        self.assertNotIn('PRIVATE', public)
        code, report, public = self.command(options + ['--apply-reconciliation',
            '--review-token', preview['review_token']])
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'closed')
        self.assertNotIn('PRIVATE', public)
        self.assertEqual(self.client.generate.call_count, 1)
        self.client.chat_completion.assert_not_called()
        summary = inspect_jobs(self.library.root)[0]
        self.assertEqual(summary['state'], 'closed')
        self.assertFalse(summary['pending'])
        self.assertEqual(summary['calls'][0]['state'], 'unknown')
        self.assertFalse((self.library.root / 'library.json').exists())


if __name__ == '__main__':
    unittest.main()
