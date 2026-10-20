from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hold_music.executor import recover_publication
from hold_music.job_store import JobStore, JobStoreBusy, inspect_jobs
from hold_music.lyria_client import StreamError
import test_executor as fixtures
from tools.prepare_library import main


class ProcessCrash(BaseException):
    """Bypass ordinary exception handlers to simulate process loss."""


class DurableExecutorTests(unittest.TestCase):
    setUp = fixtures.ExecutorTests.setUp
    run_jobs = fixtures.ExecutorTests.run_jobs

    def leave_hot_journal(self):
        database = self.library.root / '.executor' / 'jobs.sqlite3'
        code = """
import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute('PRAGMA cache_size=1')
db.execute('BEGIN IMMEDIATE')
db.execute('UPDATE jobs SET context=?', ('x' * 4000000,))
os._exit(17)
"""
        result = subprocess.run([sys.executable, '-c', code, str(database)], capture_output=True)
        self.assertEqual(result.returncode, 17)
        self.assertTrue(database.with_name(database.name + '-journal').exists())

    def test_apply_recovery_opens_writable_before_inspecting_a_hot_journal(self):
        self.convert.side_effect = ValueError('fixture')
        job_id = self.run_jobs()['jobs'][0]
        self.leave_hot_journal()
        with self.assertRaisesRegex(ValueError, 'repair-journal'):
            inspect_jobs(self.library.root)
        from test_executor import fake_conversion
        self.convert.side_effect = fake_conversion
        report = recover_publication(job_id, library=self.library, apply=True)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_explicit_journal_repair_discovers_jobs_without_generation_or_publication(self):
        self.convert.side_effect = ValueError('fixture')
        job_id = self.run_jobs()['jobs'][0]
        self.leave_hot_journal()
        with redirect_stdout(io.StringIO()) as output, \
                patch('tools.prepare_library.lyria_client.read_openrouter_key') as key:
            self.assertEqual(main(['--library', str(self.library.root), '--repair-journal']), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report['provider_calls'], 0)
        self.assertEqual(report['jobs'][0]['job_id'], job_id)
        self.assertFalse((self.library.root / 'library.json').exists())
        self.assertEqual(self.client.generate.call_count, 1)
        key.assert_not_called()

    def test_conversion_failure_retains_audio_cost_and_blocks_paid_rerun(self):
        self.convert.side_effect = ValueError('PRIVATE error')
        report = self.run_jobs()
        job_id = report['jobs'][0]
        summaries = inspect_jobs(self.library.root)
        self.assertEqual(summaries[0]['state'], 'failed')
        self.assertFalse(summaries[0]['unknown_outcome'])
        self.assertEqual(summaries[0]['calls'][0]['accounting']['cost_usd'], .08)
        with JobStore(self.library.root) as store:
            saved = store.job(job_id)
            self.assertTrue(saved['calls'][0]['audio'])
        self.client.generate.reset_mock()
        self.assertEqual(self.run_jobs()['status'], 'recovery_required')
        self.client.generate.assert_not_called()
        self.assertNotIn('PRIVATE', json.dumps(summaries))

    def test_conversion_retry_uses_saved_audio_without_provider(self):
        self.convert.side_effect = ValueError('fixture')
        job_id = self.run_jobs()['jobs'][0]
        from test_executor import fake_conversion
        self.convert.side_effect = fake_conversion
        self.client.generate.reset_mock()
        report = recover_publication(job_id, library=self.library, apply=True)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['provider_calls'], 0)
        self.assertEqual(len(self.library.load().recordings), 1)
        self.assertFalse(inspect_jobs(self.library.root)[0]['pending'])
        self.assertEqual(self.library.validate(), [])
        self.client.generate.assert_not_called()

    def test_crash_during_call_stays_unknown_and_is_never_retried(self):
        self.client.generate.side_effect = ProcessCrash()
        with self.assertRaises(ProcessCrash):
            self.run_jobs()
        # A status read is genuinely read-only and still calls an in-flight call unknown.
        summary = inspect_jobs(self.library.root)[0]
        self.assertEqual(summary['state'], 'in_flight')
        self.assertTrue(summary['unknown_outcome'])
        self.client.generate.reset_mock()
        report = self.run_jobs()
        self.assertEqual(report['status'], 'recovery_required')
        self.assertEqual(report['pending_jobs'][0]['state'], 'unknown')
        self.client.generate.assert_not_called()
        recovery = recover_publication(summary['job_id'], library=self.library, apply=True)
        self.assertEqual(recovery['status'], 'failed')
        self.assertTrue(recovery['job']['unknown_outcome'])

    def test_returned_response_survives_crash_before_accounting(self):
        with patch.object(JobStore, 'account', side_effect=ProcessCrash()):
            with self.assertRaises(ProcessCrash):
                self.run_jobs(max_jobs=1)
        summary = inspect_jobs(self.library.root)[0]
        self.assertEqual(summary['state'], 'response_received')
        self.assertTrue(summary['unaccounted_response'])
        recovery = recover_publication(summary['job_id'], library=self.library, apply=True)
        self.assertEqual(recovery['status'], 'complete')
        self.assertEqual(recovery['job']['calls'][0]['accounting']['cost_usd'], .08)
        self.assertEqual(self.client.generate.call_count, 1)

    def test_writer_lock_prevents_a_second_executor_from_calling_provider(self):
        with JobStore(self.library.root):
            with self.assertRaises(JobStoreBusy):
                self.run_jobs()
        self.client.generate.assert_not_called()

    def test_crash_after_accounting_before_conversion_is_recoverable(self):
        original = JobStore.update

        def crash(store, job_id, **kwargs):
            if kwargs.get('state') == 'audio_ready':
                raise ProcessCrash()
            return original(store, job_id, **kwargs)

        with patch.object(JobStore, 'update', new=crash):
            with self.assertRaises(ProcessCrash):
                self.run_jobs(max_jobs=1)
        summary = inspect_jobs(self.library.root)[0]
        self.assertFalse(summary['unaccounted_response'])
        report = recover_publication(summary['job_id'], library=self.library, apply=True)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_crash_after_manifest_commit_recovers_without_duplicate(self):
        original = JobStore.update

        def crash(store, job_id, **kwargs):
            if kwargs.get('state') == 'completed':
                raise ProcessCrash()
            return original(store, job_id, **kwargs)

        with patch.object(JobStore, 'update', new=crash):
            with self.assertRaises(ProcessCrash):
                self.run_jobs(max_jobs=1)
        manifest_before = (self.library.root / 'library.json').read_bytes()
        job_id = inspect_jobs(self.library.root)[0]['job_id']
        self.convert.reset_mock()
        recovery = recover_publication(job_id, library=self.library, apply=True)
        self.assertEqual(recovery['status'], 'complete')
        self.assertEqual((self.library.root / 'library.json').read_bytes(), manifest_before)
        self.convert.assert_not_called()
        self.assertEqual(self.client.generate.call_count, 1)

    def test_recovery_rejects_replaced_valid_wav_or_missing_persisted_wav_hash(self):
        original = JobStore.update

        def crash(store, job_id, **kwargs):
            if kwargs.get('state') == 'completed':
                raise ProcessCrash()
            return original(store, job_id, **kwargs)

        with patch.object(JobStore, 'update', new=crash):
            with self.assertRaises(ProcessCrash):
                self.run_jobs(max_jobs=1)
        job_id = inspect_jobs(self.library.root)[0]['job_id']
        wav = self.library.root / 'hm_slot_01.wav'
        original_wav = wav.read_bytes()
        # Change a PCM sample without changing format, length or duration.
        altered = bytearray(original_wav)
        altered[-2:] = b'\x01\x00'
        wav.write_bytes(altered)
        self.assertEqual(self.library.validate(), [])
        self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'failed')
        self.assertEqual(wav.read_bytes(), altered)
        wav.write_bytes(original_wav)
        with JobStore(self.library.root) as store:
            context = store.job(job_id)['context']
            expected_hash = context.pop('converted_wav_sha256')
            store.update(job_id, context=context)
        self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'failed')
        with JobStore(self.library.root) as store:
            context = store.job(job_id)['context']
            context['converted_wav_sha256'] = expected_hash
            store.update(job_id, context=context)
        self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'complete')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_paid_result_survives_manifest_publication_failure(self):
        with patch.object(self.library, 'add_recording', side_effect=OSError('PRIVATE')):
            report = self.run_jobs(max_jobs=1)
        self.assertEqual(report['status'], 'failed')
        recovery = recover_publication(report['jobs'][0], library=self.library, apply=True)
        self.assertEqual(recovery['status'], 'complete')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_response_persistence_failure_remains_unknown(self):
        with patch.object(JobStore, 'returned', side_effect=OSError('disk failure')):
            report = self.run_jobs(max_jobs=1)
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(report['unreported_attempt_cost'])
        self.assertTrue(inspect_jobs(self.library.root)[0]['unknown_outcome'])
        self.assertEqual(self.run_jobs()['status'], 'recovery_required')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_malformed_cost_keeps_audio_but_refuses_unaccounted_publication(self):
        from hold_music.lyria_client import Result
        from mp3_fixture import mp3_frames
        self.client.generate.side_effect = [Result(mp3_frames(), 5, {'cost': -1}, 'invalid-cost')]
        report = self.run_jobs(max_jobs=1)
        summary = inspect_jobs(self.library.root)[0]
        self.assertTrue(summary['unaccounted_response'])
        recovery = recover_publication(report['jobs'][0], library=self.library, apply=True)
        self.assertEqual(recovery['status'], 'failed')
        with JobStore(self.library.root) as store:
            self.assertTrue(store.job(report['jobs'][0])['calls'][0]['audio'])
        self.assertFalse((self.library.root / 'library.json').exists())
        self.assertEqual(self.client.generate.call_count, 1)

    def test_numeric_overflow_stays_unaccounted_and_status_is_valid_json(self):
        from hold_music.lyria_client import Result
        from mp3_fixture import mp3_frames
        self.client.generate.side_effect = [Result(mp3_frames(), 5, {'cost': '1e999'}, 'overflow-cost')]
        report = self.run_jobs(max_jobs=1)
        self.assertEqual(report['status'], 'failed')
        summary = inspect_jobs(self.library.root)[0]
        self.assertTrue(summary['unaccounted_response'])
        self.assertIsNone(summary['calls'][0]['accounting'])
        json.dumps(report, allow_nan=False)
        json.dumps(summary, allow_nan=False)
        self.assertEqual(self.run_jobs()['status'], 'recovery_required')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_recovery_dry_run_writes_nothing_and_needs_no_encoder(self):
        self.convert.side_effect = ValueError('fixture')
        job_id = self.run_jobs()['jobs'][0]
        path = self.library.root / '.executor' / 'jobs.sqlite3'
        before = path.read_bytes()
        self.which.reset_mock()
        report = recover_publication(job_id, library=self.library)
        self.assertEqual(report['status'], 'recovery_dry_run')
        self.assertEqual(path.read_bytes(), before)
        self.which.assert_not_called()

    def test_cli_inspection_and_recovery_need_neither_registry_nor_credentials(self):
        self.convert.side_effect = ValueError('fixture')
        job_id = self.run_jobs()['jobs'][0]
        self.which.reset_mock()
        for extra in (['--job-status'], ['--recover-job', job_id]):
            with redirect_stdout(io.StringIO()) as output, \
                    patch('tools.prepare_library.lyria_client.read_openrouter_key') as key:
                self.assertEqual(main(['--library', str(self.library.root)] + extra), 0)
            self.assertIn(job_id, output.getvalue())
            key.assert_not_called()
        self.which.assert_not_called()
        from test_executor import fake_conversion
        self.convert.side_effect = fake_conversion
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--library', str(self.library.root), '--recover-job', job_id,
                                   '--apply-recovery']), 0)
        self.assertEqual(json.loads(output.getvalue())['provider_calls'], 0)


class DurableLyricsTests(unittest.TestCase):
    setUp = fixtures.ExecutorTests.setUp
    run_jobs = fixtures.ExecutorTests.run_jobs
    lyrical_jobs = fixtures.LyricalExecutorTests.lyrical_jobs

    def test_lyric_budget_stop_retains_private_result_and_prevents_recomposition(self):
        self.lyrical_jobs()
        self.client.chat_completion.return_value['usage']['cost'] = .03
        report = self.run_jobs(max_usd=.10)
        summary = inspect_jobs(self.library.root)[0]
        self.assertEqual(summary['state'], 'lyrics_ready')
        self.assertEqual(summary['calls'][0]['accounting']['cost_usd'], .03)
        self.assertNotIn('[Verse]', json.dumps(summary))
        with JobStore(self.library.root) as store:
            self.assertTrue(store.job(report['jobs'][0])['context']['lyrics'])
        self.assertEqual(self.run_jobs(max_usd=.20)['status'], 'recovery_required')
        self.assertEqual(self.client.chat_completion.call_count, 1)
        self.client.generate.assert_not_called()

    def test_crash_after_lyric_call_keeps_payload_without_recomposing(self):
        self.lyrical_jobs()
        with patch.object(JobStore, 'account', side_effect=ProcessCrash()):
            with self.assertRaises(ProcessCrash):
                self.run_jobs(max_usd=.20)
        summary = inspect_jobs(self.library.root)[0]
        self.assertTrue(summary['unaccounted_response'])
        with JobStore(self.library.root) as store:
            self.assertTrue(store.job(summary['job_id'])['calls'][0]['response']['content'])
        self.assertEqual(self.run_jobs(max_usd=.20)['status'], 'recovery_required')
        self.assertEqual(self.client.chat_completion.call_count, 1)
        self.client.generate.assert_not_called()

    def test_bad_lyrics_are_known_response_failure_with_durable_accounting(self):
        self.lyrical_jobs()
        self.client.chat_completion.return_value['content'] = 'PRIVATE malformed lyrics'
        self.run_jobs(max_usd=.20)
        summary = inspect_jobs(self.library.root)[0]
        self.assertEqual(summary['state'], 'failed')
        self.assertFalse(summary['unknown_outcome'])
        self.assertEqual(summary['calls'][0]['accounting']['cost_usd'], .003)
        self.assertNotIn('PRIVATE', json.dumps(summary))
        self.assertEqual(self.run_jobs(max_usd=.20)['status'], 'recovery_required')
        self.assertEqual(self.client.chat_completion.call_count, 1)

    def test_music_unknown_retains_lyric_cost_separately(self):
        self.lyrical_jobs()
        self.client.generate.side_effect = StreamError('PRIVATE')
        self.run_jobs(max_usd=.20)
        summary = inspect_jobs(self.library.root)[0]
        self.assertTrue(summary['unknown_outcome'])
        self.assertEqual(summary['calls'][0]['accounting']['cost_usd'], .003)
        self.assertIsNone(summary['calls'][1]['accounting'])
        self.assertEqual(summary['calls'][1]['estimate_usd'], '0.08')

    def test_recovery_rejects_structurally_valid_changes_to_published_lyrics_or_metadata(self):
        self.lyrical_jobs()
        original_update = JobStore.update

        def crash(store, job_id, **kwargs):
            if kwargs.get('state') == 'completed':
                raise ProcessCrash()
            return original_update(store, job_id, **kwargs)

        with patch.object(JobStore, 'update', new=crash):
            with self.assertRaises(ProcessCrash):
                self.run_jobs(max_usd=.20)
        job_id = inspect_jobs(self.library.root)[0]['job_id']
        manifest_path = self.library.root / 'library.json'
        original_manifest = json.loads(manifest_path.read_text())
        lyrics_path = self.library.root / 'hm_slot_01.lyrics.txt'
        original_lyrics = lyrics_path.read_bytes()
        from copy import deepcopy
        changes = [
            ('lyrics_sha256', hashlib.sha256(b'Altered words').hexdigest()),
            ('title', 'Altered title'),
            ('topic_id', 'altered-topic'),
            ('created_at_hours', 101),
            ('source_observation_ids', ['altered-observation']),
        ]
        for key, value in changes:
            with self.subTest(field=key):
                manifest = deepcopy(original_manifest)
                manifest['recordings'][0][key] = value
                manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
                lyrics_path.write_bytes(b'Altered words' if key == 'lyrics_sha256' else original_lyrics)
                self.assertEqual(self.library.validate(), [])
                report = recover_publication(job_id, library=self.library, apply=True)
                self.assertEqual(report['status'], 'failed')
                self.assertNotEqual(report['job']['state'], 'completed')
                self.assertEqual(manifest_path.read_text(), json.dumps(manifest))
        manifest_path.write_text(json.dumps(original_manifest), encoding='utf-8')
        lyrics_path.write_bytes(original_lyrics)
        self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'complete')
        self.assertEqual(self.client.generate.call_count, 1)
        self.assertEqual(self.client.chat_completion.call_count, 1)


class JobStoreTests(unittest.TestCase):
    def test_abrupt_process_exit_preserves_dispatch_and_releases_writer_lock(self):
        code = """
import os, sys
from hold_music.job_store import JobStore
with JobStore(sys.argv[1]) as store:
    job_id = store.begin_job(dict(job=dict(performer_id='fixture', region='pale', mode='instrumental')))
    store.begin_call(job_id, 'generate_recording', 'fixture-model', '0.08')
    os._exit(17)
"""
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, '-c', code, temp],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True)
            self.assertEqual(result.returncode, 17)
            with JobStore(temp) as store:
                pending = store.summaries(pending_only=True)
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]['state'], 'unknown')
                self.assertEqual(pending[0]['calls'][0]['state'], 'unknown')
                self.assertEqual(pending[0]['calls'][0]['estimate_usd'], '0.08')

    def test_inspection_does_not_create_library(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'missing'
            self.assertEqual(inspect_jobs(root), [])
            self.assertFalse(root.exists())

    def test_writer_lock_and_release(self):
        with tempfile.TemporaryDirectory() as temp:
            with JobStore(temp):
                with self.assertRaises(JobStoreBusy):
                    with JobStore(temp):
                        pass
            with JobStore(temp) as store:
                self.assertEqual(store.summaries(), [])

    def test_prepared_job_crash_does_not_claim_a_provider_call(self):
        with tempfile.TemporaryDirectory() as temp:
            with JobStore(temp) as store:
                store.begin_job(dict(job=dict(performer_id='fixture', region='pale', mode='instrumental')))
            with JobStore(temp) as store:
                self.assertEqual(store.summaries(pending_only=True), [])
                summary = store.summaries()[0]
                self.assertEqual(summary['error_type'], 'InterruptedBeforeDispatch')
                self.assertEqual(summary['calls'], [])


if __name__ == '__main__':
    unittest.main()
