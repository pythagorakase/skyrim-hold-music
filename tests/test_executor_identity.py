from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from hold_music.executor import execute, plan_work, recover_publication
from hold_music.job_store import JobStore
from hold_music.lyria_client import MODEL
from hold_music.recording_identity import VERSION_FIELDS
from hold_music.regional import PALETTE, freeze_recipe
import test_executor as fixtures


IDENTITY = (*VERSION_FIELDS, 'arrangement', 'voice', 'model_id')


class ProductionIdentityTests(unittest.TestCase):
    setUp = fixtures.ExecutorTests.setUp
    run_jobs = fixtures.ExecutorTests.run_jobs

    def palette_copy(self):
        path = Path(self.temp.name) / 'palette.json'
        path.write_bytes(PALETTE.read_bytes())
        return path

    def revise_palette(self, path, region='pale', *, instrument=None):
        palette = json.loads(path.read_text(encoding='utf-8'))
        profile = next(row for row in palette['existing'] if row['id'] == region)
        if instrument is not None:
            profile['workshop']['plucked'] = instrument
        else:
            profile['core'] += ' Distinct synthetic direction.'
            if profile.get('core_instrumental'):
                profile['core_instrumental'] += ' Distinct synthetic direction.'
        path.write_text(json.dumps(palette), encoding='utf-8')

    def test_production_jobs_and_publication_have_exact_named_instrument_identity(self):
        self.jobs = plan_work(self.registry, self.library, performer_ids=['lynly_star_sung'])
        self.assertEqual(self.jobs[0]['instrument_name'], 'cittern')
        self.assertEqual(self.jobs[0]['instrument_family'], 'plucked_string')
        self.assertEqual(self.jobs[0]['arrangement'], 'solo_lute')
        self.assertEqual(self.jobs[0]['voice'], 'none')
        self.assertEqual(self.jobs[0]['model_id'], MODEL)
        row = self.run_jobs(max_jobs=1)['recordings'][0]
        for key in IDENTITY:
            self.assertEqual(row[key], self.jobs[0][key])
        self.assertEqual(plan_work(self.registry, self.library, performer_ids=['lynly_star_sung']), [])

    def test_ready_counts_require_every_recording_identity_field(self):
        self.run_jobs(max_jobs=1)
        manifest_path = self.library.root / 'library.json'
        original = json.loads(manifest_path.read_text())
        changes = dict(recipe_revision='fixture-old-revision', instrument_family='reedless_woodwind',
                       instrument_name='recorder', arrangement='solo_flute',
                       model_id='fixture/old-model', recipe_id='pale/alternate', gender='male',
                       mode='wordless')
        for key, value in changes.items():
            manifest = deepcopy(original)
            manifest['recordings'][0][key] = value
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.subTest(field=key):
                self.assertEqual(self.library.validate(), [])
                jobs = plan_work(self.registry, self.library, performer_ids=['karita'])
                self.assertEqual(len(jobs), 1)
        manifest_path.write_text(json.dumps(original), encoding='utf-8')
        self.assertEqual(plan_work(self.registry, self.library, performer_ids=['karita']), [])

    def test_unversioned_recording_does_not_satisfy_current_production_plan(self):
        self.run_jobs(max_jobs=1)
        manifest_path = self.library.root / 'library.json'
        manifest = json.loads(manifest_path.read_text())
        for key in (*VERSION_FIELDS, 'arrangement', 'voice'):
            manifest['recordings'][0].pop(key)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(self.library.validate(), [])
        self.assertEqual(len(plan_work(self.registry, self.library, performer_ids=['karita'])), 1)

    def test_plan_reports_explicit_non_lute_performers_without_assigning_plucked_jobs(self):
        jobs = plan_work(self.registry, self.library)
        unsupported = [row for row in self.registry.performers if row['instrument'] != 'lute']
        self.assertTrue(unsupported)
        for row in unsupported:
            self.assertNotIn(row['id'], [job['performer_id'] for job in jobs])
            decision = next(decision for decision in jobs.decisions if decision['performer_id'] == row['id'])
            self.assertEqual(decision['action'], 'no_selection')
            self.assertIn('lute animation family only', decision['reasons'][0])
        # The legacy duck-typed registry interface can still omit instrument.
        karita = self.registry.find_by_name('Karita')
        karita.pop('instrument')
        self.assertEqual(len(plan_work(self.registry, self.library, performer_ids=['karita'])), 1)

    def test_stale_palette_plan_is_rejected_before_any_paid_call(self):
        path = self.palette_copy()
        self.jobs = plan_work(self.registry, self.library, performer_ids=['karita'], palette_path=path)
        self.assertIsInstance(self.jobs[0]['palette_path'], str)
        self.revise_palette(path)
        with self.assertRaisesRegex(ValueError, 'Stale or invalid'):
            self.run_jobs()
        self.client.generate.assert_not_called()
        self.assertFalse(self.library.root.exists())

    def test_partial_or_inconsistent_identity_is_rejected_before_any_paid_call(self):
        original = deepcopy(self.jobs)
        for key, value in [('recipe_revision', 'altered'), ('instrument_family', 'reedless_woodwind'),
                           ('instrument_name', 'recorder'), ('arrangement', 'solo_flute'),
                           ('voice', 'male'), ('model_id', 'fixture/other-model'),
                           ('prompt_prefix', 'altered direction'), ('instrument_name', None)]:
            self.jobs = deepcopy(original)
            self.jobs[0][key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.run_jobs()
        self.client.generate.assert_not_called()
        self.assertFalse(self.library.root.exists())

    def test_recipe_edit_during_previous_job_blocks_next_paid_dispatch(self):
        path = self.palette_copy()
        self.jobs = plan_work(self.registry, self.library, performer_ids=['karita'],
                              target_per_performer=2, palette_path=path)
        result = next(self.client.generate.side_effect)

        def generate(prompt):
            self.revise_palette(path)
            return result

        self.client.generate.side_effect = generate
        report = self.run_jobs()
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(len(report['recordings']), 1)
        self.assertEqual(self.client.generate.call_count, 1)
        self.assertEqual(report['recordings'][0]['recipe_revision'], self.jobs[0]['recipe_revision'])

    def test_recovery_uses_retained_identity_when_current_recipe_changes(self):
        path = self.palette_copy()
        self.jobs = plan_work(self.registry, self.library, performer_ids=['karita'], palette_path=path)
        expected = deepcopy(self.jobs[0])
        self.convert.side_effect = ValueError('fixture conversion failure')
        report = self.run_jobs()
        self.revise_palette(path, instrument='oud')
        self.convert.side_effect = fixtures.fake_conversion
        recovered = recover_publication(report['jobs'][0], library=self.library, apply=True)
        self.assertEqual(recovered['status'], 'complete')
        for key in IDENTITY:
            self.assertEqual(recovered['recordings'][0][key], expected[key])
        self.assertNotEqual(freeze_recipe('pale', 'instrumental', 'female', path)['recipe_revision'],
                            expected['recipe_revision'])
        self.assertEqual(self.client.generate.call_count, 1)

    def test_existing_publication_recovery_rejects_changed_identity(self):
        from test_job_store import ProcessCrash
        original_update = JobStore.update

        def crash(store, job_id, **kwargs):
            if kwargs.get('state') == 'completed':
                raise ProcessCrash()
            return original_update(store, job_id, **kwargs)

        with patch.object(JobStore, 'update', new=crash), self.assertRaises(ProcessCrash):
            self.run_jobs(max_jobs=1)
        with JobStore(self.library.root) as store:
            job_id = store.summaries()[0]['job_id']
        path = self.library.root / 'library.json'
        original = json.loads(path.read_text())
        for key, value in [('recipe_revision', 'other'), ('instrument_name', 'oud'),
                           ('instrument_family', 'reedless_woodwind'), ('arrangement', 'solo_flute')]:
            changed = deepcopy(original)
            changed['recordings'][0][key] = value
            path.write_text(json.dumps(changed), encoding='utf-8')
            with self.subTest(field=key):
                self.assertEqual(self.library.validate(), [])
                self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'failed')
        path.write_text(json.dumps(original), encoding='utf-8')
        self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'complete')

    def test_legacy_manual_job_and_recovery_remain_explicitly_unversioned(self):
        legacy = deepcopy(self.jobs[0])
        for key in (*IDENTITY, 'prompt_prefix', 'region_label', 'palette_path'):
            legacy.pop(key, None)
        self.jobs = [legacy]
        self.convert.side_effect = ValueError('fixture conversion failure')
        report = self.run_jobs(max_jobs=1)
        self.convert.side_effect = fixtures.fake_conversion
        recovered = recover_publication(report['jobs'][0], library=self.library, apply=True)
        self.assertEqual(recovered['status'], 'complete')
        for key in (*VERSION_FIELDS, 'arrangement', 'voice'):
            self.assertNotIn(key, recovered['recordings'][0])
        self.assertEqual(self.client.generate.call_count, 1)

    def test_invalid_explicit_legacy_arrangement_or_voice_cannot_dispatch(self):
        legacy = deepcopy(self.jobs[0])
        for key in (*IDENTITY, 'prompt_prefix', 'region_label', 'palette_path'):
            legacy.pop(key, None)
        for key, value in [('arrangement', ''), ('arrangement', None), ('arrangement', False),
                           ('voice', ''), ('voice', None), ('voice', 'male')]:
            self.jobs = [dict(legacy, **{key: value})]
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.run_jobs(max_jobs=1)
        self.client.generate.assert_not_called()
        self.assertFalse(self.library.root.exists())

    def test_recovery_rejects_retained_prompt_changed_under_unchanged_identity(self):
        self.convert.side_effect = ValueError('fixture conversion failure')
        report = self.run_jobs(max_jobs=1)
        job_id = report['jobs'][0]
        with JobStore(self.library.root) as store:
            context = store.job(job_id)['context']
            original_prompt = context['prompt']
            context['prompt'] += '\nUnversioned altered direction.'
            store.update(job_id, context=context)
        self.convert.side_effect = fixtures.fake_conversion
        self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'failed')
        self.assertFalse((self.library.root / 'library.json').exists())
        with JobStore(self.library.root) as store:
            context = store.job(job_id)['context']
            context['prompt'] = original_prompt
            store.update(job_id, context=context)
        self.assertEqual(recover_publication(job_id, library=self.library, apply=True)['status'], 'complete')
        self.assertEqual(self.client.generate.call_count, 1)


class VocalProductionIdentityTests(unittest.TestCase):
    setUp = fixtures.ExecutorTests.setUp
    run_jobs = fixtures.ExecutorTests.run_jobs
    lyrical_jobs = fixtures.LyricalExecutorTests.lyrical_jobs
    palette_copy = ProductionIdentityTests.palette_copy
    revise_palette = ProductionIdentityTests.revise_palette

    def test_topical_planning_matches_all_identity_fields_and_reuses_existing_words(self):
        self.lyrical_jobs()
        self.run_jobs(max_jobs=1, max_usd=.20)
        path = self.library.root / 'library.json'
        original = json.loads(path.read_text())
        changes = dict(recipe_revision='fixture-old-revision', instrument_family='reedless_woodwind',
                       instrument_name='recorder', arrangement='solo_flute_and_voice', voice='female',
                       model_id='fixture/old-model', recipe_id='whiterun/alternate')
        for key, value in changes.items():
            changed = deepcopy(original)
            changed['recordings'][0][key] = value
            path.write_text(json.dumps(changed), encoding='utf-8')
            with self.subTest(field=key):
                jobs = plan_work(self.registry, self.library, performer_ids=['mikael'], modes=('lyrical',),
                                 db_path=self.db, allow_name_match=True, now_hours=104)
                self.assertEqual(jobs.decisions[0]['action'], 'generate_recording')
                self.assertEqual(len(jobs), 1)
                self.assertIn('lyrics', jobs[0])
                self.assertNotIn('lyric_brief', jobs[0])
        self.assertEqual(self.client.chat_completion.call_count, 1)

    def test_palette_change_during_lyric_call_uses_original_frozen_direction_and_identity(self):
        path = self.palette_copy()
        self.lyrical_jobs(palette_path=path)
        expected = deepcopy(self.jobs[0])
        response = self.client.chat_completion.return_value

        def write(**kwargs):
            self.revise_palette(path, region='whiterun', instrument='oud')
            return response

        self.client.chat_completion.side_effect = write
        report = self.run_jobs(max_jobs=1, max_usd=.20)
        self.assertEqual(report['status'], 'complete')
        prompt = self.client.generate.call_args.args[0]
        self.assertTrue(prompt.startswith(expected['prompt_prefix'] + '\n\nLyrics:\n'))
        self.assertNotIn('playing oud', prompt)
        for key in IDENTITY:
            self.assertEqual(report['recordings'][0][key], expected[key])
        self.assertEqual(self.client.chat_completion.call_count, 1)
        self.assertEqual(self.client.generate.call_count, 1)

    def test_redacted_plan_includes_identity_without_private_brief(self):
        self.lyrical_jobs()
        self.jobs[0]['lyric_brief']['summary'] = 'PRIVATE_SENTINEL'
        with redirect_stdout(io.StringIO()) as output:
            report = self.run_jobs(dry_run=True)
        self.assertNotIn('PRIVATE_SENTINEL', output.getvalue())
        for key in IDENTITY:
            self.assertEqual(report['plan']['jobs'][0][key], self.jobs[0][key])
        self.client.chat_completion.assert_not_called()
        self.client.generate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
