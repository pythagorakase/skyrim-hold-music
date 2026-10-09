from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from hold_music.executor import execute, plan_work, convert_mp3
from hold_music.library import Library
from hold_music.lyria_client import MODEL, Result, StreamError
from hold_music.registry import load_registry, Registry
from mp3_fixture import mp3_frames


def fake_conversion(audio, destination, *, ffmpeg):
    with wave.open(str(destination), 'wb') as stream:
        stream.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
        stream.writeframes(bytes(8820))


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.library = Library(Path(self.temp.name) / 'library')
        self.registry = load_registry()
        self.jobs = plan_work(self.registry, self.library, performer_ids=['karita'], target_per_performer=3)
        self.client = Mock()
        self.client.generate.side_effect = [Result(mp3_frames(), 200 * 1152 / 44100,
                                                  {'cost': .08}, f'gen-{i}') for i in range(4)]
        which = patch('hold_music.executor.shutil.which', return_value='/fixture/ffmpeg')
        self.which = which.start()
        self.addCleanup(which.stop)
        convert = patch('hold_music.executor.convert_mp3', side_effect=fake_conversion)
        self.convert = convert.start()
        self.addCleanup(convert.stop)

    def run_jobs(self, **kwargs):
        args = dict(client=self.client, library=self.library, ffmpeg='ffmpeg',
                    max_jobs=3, max_usd=.30, dry_run=False, spend=True)
        args.update(kwargs)
        return execute(self.jobs, **args)

    def test_plan_counts_and_null_region(self):
        jobs = plan_work(self.registry, self.library, target_per_performer=2)
        expected = [p for p in self.registry.performers if p['region'] is not None]
        self.assertEqual(len(jobs), 2 * len(expected))
        self.assertNotIn('talsgar', {job['performer_id'] for job in jobs})
        self.assertEqual(len(self.jobs), 3)
        self.assertEqual(self.jobs[0]['region'], 'pale')
        self.assertEqual(self.jobs[0]['gender'], 'female')
        self.assertEqual(plan_work(self.registry, self.library, target_per_performer=0), [])

    def test_winterhold_wordless_and_other_holds_skipped(self):
        row = deepcopy(self.registry.performers[0])
        row.update(id='winter-fixture', region='winterhold')
        registry = Registry(dict(version=1, scope='test', performers=[row]))
        jobs = plan_work(registry, self.library, modes=('instrumental', 'wordless', 'wordless'))
        self.assertEqual([job['mode'] for job in jobs], ['instrumental', 'wordless'])
        self.assertIn('Wordless singing with vocables only; no lyrics, sentences or spoken words.',
                      jobs[1]['prompt'])
        self.assertTrue(all('Lyrics:' not in job['prompt'] for job in jobs))
        self.assertEqual(plan_work(self.registry, self.library, performer_ids=['karita'],
                                   modes=('wordless',)), [])
        with self.assertRaisesRegex(ValueError, 'knowledge bridge'):
            plan_work(registry, self.library, modes=('vocal',))

    def test_planning_invalid_inputs(self):
        for kwargs in [dict(performer_ids=['typo']), dict(target_per_performer=-1),
                       dict(target_per_performer=True), dict(modes=('lyrical',)), dict(modes=())]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                plan_work(self.registry, self.library, **kwargs)

    def test_success_publishes_manifest_and_receipt(self):
        report = self.run_jobs(max_jobs=1, receipt_scope=('save-test', 'world-test'))
        self.assertEqual(report['attempted'], 1)
        self.assertEqual(report['cost_usd'], .08)
        row = report['recordings'][0]
        self.assertEqual(row['slot'], 1)
        self.assertEqual(row['duration_seconds'], .1)
        self.assertEqual(row['recipe_id'], 'pale/instrumental')
        self.assertEqual(row['model_id'], MODEL)
        self.assertIsNone(row['lyrics_sha256'])
        self.assertEqual(row['source'], dict(kind='generated', path_or_request_id='gen-0',
            sha256=hashlib.sha256(mp3_frames()).hexdigest()))
        digest = hashlib.sha256(self.jobs[0]['prompt'].encode()).hexdigest()[:16]
        self.assertEqual(row['composition_id'], f'gen:pale:instrumental:{digest}:gen-0')
        manifest = json.loads((self.library.root / 'library.json').read_text())
        self.assertEqual(manifest['generation_receipts'], [dict(id='gen-0', performer_id='karita',
            save_id='save-test', world_id='world-test', action='generate_recording', at_hours=0)])
        self.assertEqual(self.library.validate(), [])
        self.assertEqual(sorted(p.name for p in self.library.root.iterdir()),
                         ['hm_slot_01.wav', 'library.json'])

    def test_existing_playable_recordings_count_and_missing_asset_does_not(self):
        self.run_jobs(max_jobs=1)
        self.assertEqual(plan_work(self.registry, self.library, performer_ids=['karita']), [])
        jobs = plan_work(self.registry, self.library, performer_ids=['karita'], target_per_performer=3)
        self.assertEqual(len(jobs), 2)
        (self.library.root / 'hm_slot_01.wav').unlink()
        self.assertEqual(len(plan_work(self.registry, self.library, performer_ids=['karita'])), 1)

    def test_dry_run_and_spend_both_required(self):
        for flags in [dict(dry_run=True, spend=True), dict(dry_run=False, spend=False), {}]:
            with redirect_stdout(io.StringIO()) as output:
                result = execute(self.jobs, client=self.client, library=self.library,
                                 ffmpeg=None, max_jobs=1, max_usd=.10, **flags)
            self.assertEqual(result['status'], 'dry_run')
            self.assertEqual(json.loads(output.getvalue()), self.jobs)
        self.client.generate.assert_not_called()
        self.which.assert_not_called()
        self.assertFalse(self.library.root.exists())

    def test_job_and_budget_caps(self):
        self.assertEqual(self.run_jobs(max_jobs=0)['status'], 'max_jobs')
        self.assertEqual(self.run_jobs(max_usd=.079)['status'], 'budget')
        self.client.generate.assert_not_called()
        report = self.run_jobs(max_usd=.16)
        self.assertEqual(report['attempted'], 2)
        self.assertEqual(report['cost_usd'], .16)
        self.assertEqual(report['status'], 'budget')

    def test_reported_cost_controls_next_reservation(self):
        self.client.generate.side_effect = [Result(mp3_frames(), 5, {'cost': .03}, 'cheap')]
        report = self.run_jobs(max_usd=.10)
        self.assertEqual(report['attempted'], 1)
        self.assertEqual(report['cost_usd'], .03)
        self.assertEqual(report['status'], 'budget')

    def test_absent_usage_uses_estimate(self):
        self.client.generate.side_effect = [Result(mp3_frames(), 5, None, 'no-usage')]
        report = self.run_jobs(max_usd=.10)
        self.assertEqual(report['cost_usd'], .08)
        self.assertTrue(report['generations'][0]['estimated'])
        self.assertEqual(self.client.generate.call_count, 1)

    def test_actual_overrun_stops_and_reports_paid_result(self):
        self.client.generate.side_effect = [Result(mp3_frames(), 5, {'cost': .12}, 'expensive')]
        report = self.run_jobs(max_usd=.10)
        self.assertEqual(report['status'], 'budget_exceeded')
        self.assertEqual(report['cost_usd'], .12)
        self.assertEqual(len(report['recordings']), 1)
        self.assertEqual(self.client.generate.call_count, 1)

    def test_generation_failure_logs_only_identity_and_type(self):
        self.client.generate.side_effect = StreamError('private prompt and key')
        report = self.run_jobs()
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(report['unreported_attempt_cost'])
        self.assertEqual(self.client.generate.call_count, 1)
        self.assertFalse((self.library.root / 'library.json').exists())
        log = (self.library.root / 'executor.log').read_text()
        self.assertEqual(json.loads(log), dict(performer_id='karita', region='pale',
                                             mode='instrumental', error_type='StreamError'))
        self.assertNotIn('private', log)
        self.convert.assert_not_called()

    def test_conversion_failure_preserves_manifest_and_accounts_cost(self):
        self.run_jobs(max_jobs=1)
        before = (self.library.root / 'library.json').read_bytes()
        self.convert.side_effect = RuntimeError('private details')
        report = self.run_jobs()
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['cost_usd'], .08)
        self.assertEqual((self.library.root / 'library.json').read_bytes(), before)
        self.assertFalse((self.library.root / 'hm_slot_02.wav').exists())
        self.assertFalse(any(p.name.startswith('.executor-') for p in self.library.root.iterdir()))

    def test_preflight_blocks_paid_request(self):
        self.which.return_value = None
        self.assertEqual(self.run_jobs()['status'], 'failed')
        self.client.generate.assert_not_called()
        self.which.return_value = '/fixture/ffmpeg'
        with patch.object(self.library, 'free_slots', return_value=[]):
            self.assertEqual(self.run_jobs()['status'], 'failed')
        self.client.generate.assert_not_called()

    def test_invalid_budget_and_jobs_never_call(self):
        for kwargs in [dict(max_usd='nan'), dict(max_usd='inf'), dict(max_usd=-1),
                       dict(max_jobs=-1), dict(receipt_scope=('', 'world'))]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_jobs(**kwargs)
        self.jobs[0]['prompt'] += '\nLyrics:\nforbidden'
        with self.assertRaises(ValueError):
            self.run_jobs()
        self.client.generate.assert_not_called()

    def test_conversion_uses_importer_arguments(self):
        from tools.import_recording import ffmpeg_arguments
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'out.wav'
            with patch('hold_music.executor.subprocess.run') as run:
                convert_mp3(b'fixture MP3', destination, ffmpeg='ffmpeg')
            source = destination.with_suffix('.mp3')
            self.assertEqual(source.read_bytes(), b'fixture MP3')
            run.assert_called_once_with(ffmpeg_arguments('ffmpeg', source, destination),
                                        check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
