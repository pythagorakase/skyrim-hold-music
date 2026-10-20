"""Private retained-job review uses synthetic provider evidence only."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import test_executor as fixtures
from test_job_store import ProcessCrash
from hold_music.executor import recover_publication
from hold_music.job_review import continue_job, reconcile_job
from hold_music.job_store import JobStore, JobStoreBusy, inspect_jobs, readonly_store
from hold_music.library import Library
from hold_music.lyria_client import StreamError
from hold_music.regional import prompt_from_recipe


class ReviewFixture(unittest.TestCase):
    setUp = fixtures.ExecutorTests.setUp
    run_jobs = fixtures.ExecutorTests.run_jobs
    lyrical_jobs = fixtures.LyricalExecutorTests.lyrical_jobs

    def retained_lyrics(self, *, unparsed=False):
        self.lyrical_jobs()
        if unparsed:
            with patch.object(JobStore, 'account', side_effect=ProcessCrash()):
                with self.assertRaises(ProcessCrash):
                    self.run_jobs(max_usd=.20)
            return inspect_jobs(self.library.root)[0]['job_id']
        self.client.chat_completion.return_value['usage']['cost'] = .03
        report = self.run_jobs(max_usd=.10)
        self.assertEqual(report['status'], 'budget')
        return report['jobs'][0]

    def unknown_job(self, *, lyrical=False, crash=False):
        if lyrical:
            self.lyrical_jobs()
        self.client.generate.side_effect = ProcessCrash() if crash else StreamError('PRIVATE provider error')
        if crash:
            with self.assertRaises(ProcessCrash):
                self.run_jobs(max_jobs=1)
            return inspect_jobs(self.library.root)[0]['job_id']
        return self.run_jobs(max_jobs=1)['jobs'][0]

    def saved(self, job_id):
        with readonly_store(self.library.root) as store:
            return store.job(job_id)

    def tree(self):
        return {str(path.relative_to(self.library.root)): path.read_bytes()
                for path in self.library.root.rglob('*') if path.is_file()}

    def apply_continuation(self, job_id, token, **kwargs):
        options = dict(library=self.library, client=self.client, review_token=token,
                       dry_run=False, spend=True)
        options.update(kwargs)
        return continue_job(job_id, **options)

    def edit_context(self, job_id, edit):
        with JobStore(self.library.root, recover_interrupted=False) as store:
            context = store.job(job_id)['context']
            edit(context)
            store.update(job_id, context=context)

    def resolve(self, job_id, *, resolution=None):
        resolution = resolution or dict(outcome='confirmed_not_charged', cost_usd='0',
                                        evidence='PRIVATE billing reference')
        preview = reconcile_job(job_id, library=self.library, resolution=resolution)
        self.assertTrue(preview['can_reconcile'], preview)
        result = reconcile_job(job_id, library=self.library, resolution=resolution,
                               review_token=preview['review_token'], apply=True)
        return result, preview['review_token'], resolution


class ContinuationTests(ReviewFixture):
    def test_preview_is_read_only_redacted_and_does_not_need_encoder_or_client(self):
        job_id = self.retained_lyrics()
        before = self.tree()
        self.which.reset_mock()
        preview = continue_job(job_id, library=self.library)
        self.assertTrue(preview['can_continue'], preview)
        self.assertEqual(preview['status'], 'continuation_dry_run')
        self.assertEqual(preview['prior_cost_usd'], .03)
        self.assertEqual(preview['new_reservation_usd'], .08)
        self.assertEqual(preview['provider_calls'], 0)
        self.assertNotIn('[Verse]', json.dumps(preview))
        self.assertNotIn('private', preview)
        shown = continue_job(job_id, library=self.library, show_briefs=True)
        self.assertEqual(preview['review_token'], shown['review_token'])
        self.assertIn('[Verse]', shown['private']['lyrics'])
        self.assertEqual(before, self.tree())
        self.which.assert_not_called()
        self.client.generate.assert_not_called()

    def test_continuation_reuses_exact_words_direction_scope_and_receipts(self):
        job_id = self.retained_lyrics()
        saved = self.saved(job_id)
        preview = continue_job(job_id, library=self.library, max_usd='.08')
        with patch('hold_music.regional.freeze_recipe', side_effect=AssertionError('Do not read current palette')):
            report = self.apply_continuation(job_id, preview['review_token'], max_usd='.08')
        self.assertEqual(report['status'], 'complete', report)
        self.assertEqual(report['provider_calls'], 1)
        self.assertEqual(report['cost_usd'], .08)
        self.assertEqual(report['prior_cost_usd'], .03)
        self.client.chat_completion.assert_called_once()
        self.client.generate.assert_called_once_with(
            prompt_from_recipe(saved['context']['job'], saved['context']['lyrics']))
        row = report['recordings'][0]
        self.assertEqual(row['recipe_revision'], saved['context']['job']['recipe_revision'])
        self.assertEqual(row['created_at_hours'], saved['context']['scope']['at_hours'])
        self.assertEqual(row['save_id'], saved['context']['scope']['save_id'])
        manifest = json.loads((self.library.root / 'library.json').read_text())
        self.assertEqual([r['id'] for r in manifest['generation_receipts']], ['lyrics-1', 'gen-0'])
        self.assertEqual((self.library.root / 'hm_slot_01.lyrics.txt').read_text(), saved['context']['lyrics'])
        self.assertEqual(self.library.validate(), [])
        repeated = self.apply_continuation(job_id, preview['review_token'], max_usd='.08')
        self.assertEqual(repeated['status'], 'already_applied')
        self.assertEqual(repeated['provider_calls'], 0)
        self.assertEqual(self.client.generate.call_count, 1)
        self.assertEqual(self.apply_continuation(job_id, preview['review_token'], max_usd='.09')['status'], 'blocked')

    def test_raw_returned_lyrics_can_be_parsed_locally_and_accounted_without_recomposition(self):
        job_id = self.retained_lyrics(unparsed=True)
        saved = self.saved(job_id)
        self.assertIsNone(saved['calls'][0]['accounting'])
        self.assertIsNone(saved['context']['lyrics'])
        before = self.tree()
        preview = continue_job(job_id, library=self.library)
        self.assertTrue(preview['can_continue'])
        self.assertEqual(preview['prior_cost_usd'], .003)
        self.assertEqual(before, self.tree())
        report = self.apply_continuation(job_id, preview['review_token'])
        self.assertEqual(report['status'], 'complete', report)
        after = self.saved(job_id)
        self.assertEqual(after['calls'][0]['response'], saved['calls'][0]['response'])
        self.assertEqual(after['calls'][0]['accounting']['cost_usd'], .003)
        self.client.chat_completion.assert_called_once()
        self.client.generate.assert_called_once()

    def test_missing_authorization_and_default_flags_never_dispatch(self):
        job_id = self.retained_lyrics()
        preview = continue_job(job_id, library=self.library)
        before = self.tree()
        for flags in ({}, {'spend': True}, {'dry_run': False}):
            report = continue_job(job_id, library=self.library, client=self.client,
                                  review_token=preview['review_token'], **flags)
            self.assertEqual(report['status'], 'continuation_dry_run')
        self.assertEqual(before, self.tree())
        for token in (None, '', 'incorrect', 'non-ASCII-☃'):
            report = self.apply_continuation(job_id, token)
            self.assertEqual(report['status'], 'blocked')
        self.client.generate.assert_not_called()
        self.assertEqual(len(self.saved(job_id)['calls']), 1)

    def test_token_binds_operation_budget_encoder_and_selected_receipts(self):
        job_id = self.retained_lyrics()
        token = continue_job(job_id, library=self.library)['review_token']
        alternate = Library(self.library.root, receipts_path=Path(self.temp.name) / 'other-receipts.jsonl')
        indexed = Library(self.library.root, session_receipt_index=1)
        for options in (dict(max_usd='.11'), dict(max_jobs=2), dict(ffmpeg='different'),
                        dict(library=alternate), dict(library=indexed)):
            with self.subTest(options=options):
                result = self.apply_continuation(job_id, token, **options)
                self.assertEqual(result['status'], 'blocked')
        self.client.generate.assert_not_called()

    def test_token_binds_retained_state_even_valid_nonsemantic_changes(self):
        job_id = self.retained_lyrics()
        token = continue_job(job_id, library=self.library)['review_token']
        self.edit_context(job_id, lambda context: context.update(operator_note='PRIVATE'))
        self.assertEqual(self.apply_continuation(job_id, token)['status'], 'blocked')
        self.assertTrue(continue_job(job_id, library=self.library)['can_continue'])
        self.client.generate.assert_not_called()

    def test_conflicting_saved_evidence_and_legacy_jobs_are_not_eligible(self):
        job_id = self.retained_lyrics()
        original = deepcopy(self.saved(job_id)['context'])
        edits = [
            lambda c: c.update(title='PRIVATE different title'),
            lambda c: c.update(lyrics='PRIVATE different lyrics'),
            lambda c: c.update(prompt='PRIVATE other prompt'),
            lambda c: c.update(prompt_prefix='PRIVATE other direction'),
            lambda c: c['scope'].update(save_id='another-save'),
            lambda c: c['receipts'][0].update(id='different-request'),
            lambda c: c['job'].pop('recipe_revision'),
            lambda c: c['job'].update(model_id='different-model'),
            lambda c: c['job'].pop('topic_id'),
            lambda c: c['job'].update(topic_id=''),
            lambda c: c['job'].update(topic_id='different-topic'),
            lambda c: c['job'].update(composition_id=42),
            lambda c: c['job'].update(composition_id=''),
            lambda c: c['job'].update(composition_id=None),
            lambda c: c['job']['lyric_brief'].update(source_observation_ids='PRIVATE invalid IDs'),
            lambda c: c['job']['lyric_brief'].update(source_observation_ids=[None]),
        ]
        for edit in edits:
            with self.subTest(edit=edit):
                with JobStore(self.library.root, recover_interrupted=False) as store:
                    context = deepcopy(original)
                    edit(context)
                    store.update(job_id, context=context)
                preview = continue_job(job_id, library=self.library)
                self.assertFalse(preview['can_continue'])
                self.assertIsNone(preview['review_token'])
                self.assertNotIn('PRIVATE', json.dumps(preview))
                self.assertEqual(self.apply_continuation(job_id, 'incorrect')['status'], 'blocked')
        self.client.generate.assert_not_called()

    def test_existing_composition_conflict_blocks_before_dispatch(self):
        job_id = self.retained_lyrics()
        self.edit_context(job_id, lambda c: c['job'].update(composition_id='existing-work'))
        # Publish a valid unrelated recording whose composition identity is
        # deliberately reused by the retained job. No provider is involved.
        wav = Path(self.temp.name) / 'existing.wav'
        fixtures.fake_conversion(b'', wav, ffmpeg='fixture')
        self.library.add_recording(wav, performer_id='another-performer', region='pale',
            mode='instrumental', gender='female', composition_id='existing-work',
            recipe_id='pale/instrumental', model_id='fixture-model',
            source=dict(kind='import', path_or_request_id='fixture'))
        token = continue_job(job_id, library=self.library)['review_token']
        result = self.apply_continuation(job_id, token)
        self.assertEqual(result['status'], 'blocked')
        self.client.generate.assert_not_called()
        self.assertEqual(len(self.saved(job_id)['calls']), 1)

    def test_existing_lyric_receipt_collision_blocks_before_dispatch(self):
        job_id = self.retained_lyrics()
        receipt = dict(self.saved(job_id)['context']['receipts'][0], performer_id='another-performer')
        manifest = dict(version=1, slots=24, recordings=[], generation_receipts=[receipt])
        (self.library.root / 'library.json').write_text(json.dumps(manifest))
        self.assertEqual(self.library.validate(), [])
        token = continue_job(job_id, library=self.library)['review_token']
        result = self.apply_continuation(job_id, token)
        self.assertEqual(result['status'], 'blocked')
        self.client.generate.assert_not_called()
        self.assertEqual(len(self.saved(job_id)['calls']), 1)

    def test_existing_same_region_composition_with_other_lyrics_blocks(self):
        job_id = self.retained_lyrics()
        self.edit_context(job_id, lambda c: c['job'].update(composition_id='existing-work'))
        wav = Path(self.temp.name) / 'existing.wav'
        fixtures.fake_conversion(b'', wav, ffmpeg='fixture')
        self.library.add_recording(wav, performer_id='another-performer', region='whiterun',
            mode='vocal', gender='female', composition_id='existing-work', lyrics='Other words',
            recipe_id='whiterun/vocal', model_id='fixture-model',
            source=dict(kind='import', path_or_request_id='fixture'))
        self.assertEqual(self.library.validate(), [])
        token = continue_job(job_id, library=self.library)['review_token']
        self.assertEqual(self.apply_continuation(job_id, token)['status'], 'blocked')
        self.client.generate.assert_not_called()

    def test_conflicting_accounting_and_malformed_lyric_response_block(self):
        job_id = self.retained_lyrics()
        with JobStore(self.library.root, recover_interrupted=False) as store:
            call = store.job(job_id)['calls'][0]
            original = call['accounting']
            altered = dict(original, cost_usd=0)
            store.account(call['id'], altered)
        self.assertFalse(continue_job(job_id, library=self.library)['can_continue'])
        with JobStore(self.library.root, recover_interrupted=False) as store:
            store.account(call['id'], original)
            response = dict(call['response'], content='PRIVATE malformed words')
            store.returned(call['id'], response)
        preview = continue_job(job_id, library=self.library)
        self.assertFalse(preview['can_continue'])
        self.assertNotIn('PRIVATE', json.dumps(preview))
        self.client.generate.assert_not_called()

    def test_consistent_but_invalid_clock_types_block_before_dispatch(self):
        job_id = self.retained_lyrics()
        for clock in ('102.0', True, None, -1, float('inf')):
            def change(context):
                context['job']['now_hours'] = clock
                context['scope']['at_hours'] = clock
                context['receipts'][0]['at_hours'] = clock
            self.edit_context(job_id, change)
            preview = continue_job(job_id, library=self.library)
            self.assertFalse(preview['can_continue'])
            self.assertEqual(self.apply_continuation(job_id, 'incorrect')['status'], 'blocked')
        self.client.generate.assert_not_called()

    def test_boolean_receipt_clock_cannot_match_numeric_one_by_python_equality(self):
        job_id = self.retained_lyrics()
        for scope_clock, receipt_clock in ((1, True), (True, 1)):
            def change(context):
                context['job']['now_hours'] = 1
                context['scope']['at_hours'] = scope_clock
                context['receipts'][0]['at_hours'] = receipt_clock
            self.edit_context(job_id, change)
            self.assertFalse(continue_job(job_id, library=self.library)['can_continue'])
        self.client.generate.assert_not_called()

    def test_another_pending_job_blocks_until_resolved(self):
        job_id = self.retained_lyrics()
        token = continue_job(job_id, library=self.library)['review_token']
        with JobStore(self.library.root, recover_interrupted=False) as store:
            other = store.begin_job(dict(job=dict(performer_id='fixture', region='pale', mode='instrumental')))
            store.begin_call(other, 'generate_recording', 'fixture-model', '.08')
        preview = continue_job(job_id, library=self.library)
        self.assertFalse(preview['can_continue'])
        self.assertEqual(preview['other_pending_jobs'], [other])
        self.assertEqual(self.apply_continuation(job_id, token)['status'], 'blocked')
        self.client.generate.assert_not_called()

    def test_limits_and_preflight_prevent_dispatch(self):
        job_id = self.retained_lyrics()
        for options in (dict(max_usd='.079'), dict(max_jobs=0)):
            self.assertFalse(continue_job(job_id, library=self.library, **options)['can_continue'])
        for value in ('NaN', 'Infinity', '-1', '1e999', '1e-9999'):
            with self.assertRaises(ValueError):
                continue_job(job_id, library=self.library, max_usd=value)
        token = continue_job(job_id, library=self.library)['review_token']
        with patch('hold_music.job_review.shutil.which', return_value=None):
            self.assertEqual(self.apply_continuation(job_id, token)['status'], 'blocked')
        with patch.object(self.library, 'free_slots', return_value=[]):
            self.assertEqual(self.apply_continuation(job_id, token)['status'], 'blocked')
        self.client.generate.assert_not_called()
        self.assertEqual(len(self.saved(job_id)['calls']), 1)

    def test_apply_freshly_validates_selected_external_receipts(self):
        job_id = self.retained_lyrics()
        receipts = Path(self.temp.name) / 'receipts.jsonl'
        receipts.write_text('')
        external = Library(self.library.root, receipts_path=receipts)
        token = continue_job(job_id, library=external)['review_token']
        receipts.write_text('PRIVATE malformed json')
        result = self.apply_continuation(job_id, token, library=external)
        self.assertEqual(result['status'], 'blocked')
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.client.generate.assert_not_called()

    def test_writer_lock_blocks_authorized_apply(self):
        job_id = self.retained_lyrics()
        token = continue_job(job_id, library=self.library)['review_token']
        with JobStore(self.library.root, recover_interrupted=False):
            with self.assertRaises(JobStoreBusy):
                self.apply_continuation(job_id, token)
        self.client.generate.assert_not_called()

    def test_atomic_authorization_crash_is_consumed_and_never_redispatched(self):
        job_id = self.retained_lyrics(unparsed=True)
        token = continue_job(job_id, library=self.library)['review_token']
        original = JobStore.authorize_continuation

        def crash_after_commit(store, *args, **kwargs):
            original(store, *args, **kwargs)
            raise ProcessCrash()

        with patch.object(JobStore, 'authorize_continuation', new=crash_after_commit):
            with self.assertRaises(ProcessCrash):
                self.apply_continuation(job_id, token)
        saved = self.saved(job_id)
        self.assertEqual(saved['state'], 'in_flight')
        self.assertEqual(len(saved['reviews']), 1)
        self.assertEqual(saved['calls'][1]['state'], 'in_flight')
        self.assertIsNotNone(saved['calls'][0]['accounting'])
        self.assertEqual(self.apply_continuation(job_id, token)['status'], 'already_applied')
        self.assertFalse(continue_job(job_id, library=self.library)['can_continue'])
        self.client.generate.assert_not_called()

    def test_transaction_failure_does_not_consume_authorization_or_partial_accounting(self):
        job_id = self.retained_lyrics(unparsed=True)
        token = continue_job(job_id, library=self.library)['review_token']
        original = self.saved(job_id)
        with JobStore(self.library.root, recover_interrupted=False) as store:
            store.db.execute("""CREATE TRIGGER fail_music BEFORE INSERT ON calls
                WHEN NEW.action='generate_recording' BEGIN SELECT RAISE(ABORT, 'fixture'); END""")
            store.db.commit()
        result = self.apply_continuation(job_id, token)
        self.assertEqual(result['status'], 'failed')
        saved = self.saved(job_id)
        self.assertEqual(saved['calls'], original['calls'])
        self.assertEqual(saved['context'], original['context'])
        self.assertEqual(saved['reviews'], [])
        self.client.generate.assert_not_called()

    def test_crash_during_provider_leaves_uncertain_call_and_no_retry(self):
        job_id = self.retained_lyrics()
        token = continue_job(job_id, library=self.library)['review_token']
        self.client.generate.side_effect = ProcessCrash()
        with self.assertRaises(ProcessCrash):
            self.apply_continuation(job_id, token)
        self.assertEqual(self.apply_continuation(job_id, token)['status'], 'already_applied')
        self.assertFalse(continue_job(job_id, library=self.library)['can_continue'])
        self.assertTrue(inspect_jobs(self.library.root)[0]['unknown_outcome'])
        self.assertEqual(self.client.generate.call_count, 1)
        self.client.chat_completion.assert_called_once()

    def test_response_crash_and_conversion_failure_recover_saved_audio_without_provider(self):
        job_id = self.retained_lyrics()
        token = continue_job(job_id, library=self.library)['review_token']
        with patch.object(JobStore, 'account', side_effect=ProcessCrash()):
            with self.assertRaises(ProcessCrash):
                self.apply_continuation(job_id, token)
        self.assertTrue(inspect_jobs(self.library.root)[0]['unaccounted_response'])
        self.assertFalse(continue_job(job_id, library=self.library)['can_continue'])
        self.convert.side_effect = ValueError('PRIVATE conversion failure')
        failed = recover_publication(job_id, library=self.library, apply=True)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['job']['calls'][1]['accounting']['cost_usd'], .08)
        self.convert.side_effect = fixtures.fake_conversion
        recovered = recover_publication(job_id, library=self.library, apply=True)
        self.assertEqual(recovered['status'], 'complete')
        self.assertEqual(recovered['provider_calls'], 0)
        self.assertEqual(self.client.generate.call_count, 1)
        self.client.chat_completion.assert_called_once()

    def test_readonly_preview_does_not_migrate_old_schema(self):
        job_id = self.retained_lyrics()
        path = self.library.root / '.executor' / 'jobs.sqlite3'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('DROP TABLE job_reviews')
        before = self.tree()
        self.assertTrue(continue_job(job_id, library=self.library)['can_continue'])
        self.assertEqual(before, self.tree())
        with closing(sqlite3.connect(path)) as db, db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='job_reviews'").fetchone())


class ReconciliationTests(ReviewFixture):
    def test_readonly_preview_redacts_evidence_and_scopes_cost_to_uncertain_call(self):
        job_id = self.unknown_job(lyrical=True)
        resolution = dict(outcome='charged_no_artifact', cost_usd='.08', evidence='PRIVATE billing reference')
        before = self.tree()
        preview = reconcile_job(job_id, library=self.library, resolution=resolution)
        self.assertTrue(preview['can_reconcile'], preview)
        self.assertEqual(preview['status'], 'reconciliation_dry_run')
        self.assertEqual(preview['prior_cost_usd'], .003)
        self.assertEqual(preview['resolution']['cost_usd'], '0.08')
        self.assertEqual(preview['resolution']['applies_to'], 'single_uncertain_call')
        self.assertEqual(preview['uncertain_call']['action'], 'generate_recording')
        self.assertNotIn('PRIVATE', json.dumps(preview))
        self.assertEqual(before, self.tree())

    def test_apply_preserves_raw_evidence_and_closes_pending_with_operator_provenance(self):
        job_id = self.unknown_job(lyrical=True)
        original = self.saved(job_id)
        result, token, resolution = self.resolve(job_id)
        self.assertEqual(result['status'], 'closed')
        saved = self.saved(job_id)
        for key in ('context', 'calls', 'recording', 'error_type', 'created_at'):
            self.assertEqual(saved[key], original[key])
        self.assertEqual(saved['state'], 'closed')
        self.assertEqual(saved['reviews'][0]['data']['resolution']['evidence'], resolution['evidence'])
        self.assertEqual(saved['reviews'][0]['data']['prior_accounting'][0]['cost_usd'], .003)
        summary = inspect_jobs(self.library.root)[0]
        self.assertFalse(summary['pending'])
        self.assertTrue(summary['unknown_outcome'])
        self.assertFalse(summary['resolution']['provider_verified'])
        self.assertEqual(summary['resolution']['provenance'], 'operator_report')
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('PRIVATE', json.dumps(summary))
        repeat = reconcile_job(job_id, library=self.library, resolution=resolution, review_token=token, apply=True)
        self.assertEqual(repeat['status'], 'already_applied')
        self.assertEqual(len(self.saved(job_id)['reviews']), 1)
        changed = dict(resolution, evidence='PRIVATE different reference')
        self.assertEqual(reconcile_job(job_id, library=self.library, resolution=changed,
                                      review_token=token, apply=True)['status'], 'blocked')
        self.assertEqual(self.client.generate.call_count, 1)

    def test_closed_inflight_raw_state_survives_normal_store_and_all_mutators(self):
        job_id = self.unknown_job(crash=True)
        self.resolve(job_id)
        original = self.saved(job_id)
        call_id = original['calls'][0]['id']
        with JobStore(self.library.root) as store:
            self.assertEqual(store.job(job_id)['calls'][0]['state'], 'in_flight')
            operations = [
                lambda: store.update(job_id, state='prepared'),
                lambda: store.begin_call(job_id, 'generate_recording', 'fixture', '.08'),
                lambda: store.returned(call_id, {'request_id': 'replacement'}),
                lambda: store.account(call_id, {'cost_usd': 0}),
            ]
            for operation in operations:
                with self.assertRaisesRegex(ValueError, 'Closed'):
                    operation()
            store.fail(job_id, 'Changed')
        self.assertEqual(self.saved(job_id), original)
        recovery = recover_publication(job_id, library=self.library, apply=True)
        self.assertEqual(recovery['status'], 'failed')
        self.assertEqual(self.saved(job_id), original)
        self.assertEqual(recovery['job']['state'], 'closed')

    def test_review_records_are_append_only_and_writer_lock_is_shared(self):
        job_id = self.unknown_job()
        resolution = dict(outcome='confirmed_not_charged', cost_usd='0', evidence='PRIVATE ref')
        token = reconcile_job(job_id, library=self.library, resolution=resolution)['review_token']
        with JobStore(self.library.root, recover_interrupted=False):
            with self.assertRaises(JobStoreBusy):
                reconcile_job(job_id, library=self.library, resolution=resolution, review_token=token, apply=True)
        reconcile_job(job_id, library=self.library, resolution=resolution, review_token=token, apply=True)
        with JobStore(self.library.root) as store:
            for sql in ("UPDATE job_reviews SET data='{}'", 'DELETE FROM job_reviews'):
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'append-only'):
                    with store.db:
                        store.db.execute(sql)
        self.assertEqual(len(self.saved(job_id)['reviews']), 1)

    def test_resolution_validation_finite_cost_and_private_errors(self):
        job_id = self.unknown_job()
        valid = dict(outcome='confirmed_not_charged', cost_usd='0', evidence='PRIVATE ref')
        for changes in ({'outcome': 'unsupported'}, {'cost_usd': '.08'}, {'cost_usd': 'NaN'},
                        {'cost_usd': '1e999'}, {'cost_usd': '1e-9999'}, {'cost_usd': '-1'},
                        {'evidence': ''}, {'evidence': []}, {'outcome': 'charged_no_artifact'}):
            with self.subTest(changes=changes):
                try:
                    reconcile_job(job_id, library=self.library, resolution=dict(valid, **changes))
                except ValueError as exc:
                    self.assertNotIn('PRIVATE', str(exc))
                else:
                    self.fail('Invalid resolution was accepted')
        self.assertEqual(self.saved(job_id)['reviews'], [])

    def test_token_binds_resolution_and_job_state(self):
        job_id = self.unknown_job()
        resolution = dict(outcome='confirmed_not_charged', cost_usd='0', evidence='PRIVATE ref')
        token = reconcile_job(job_id, library=self.library, resolution=resolution)['review_token']
        for changed in (dict(resolution, evidence='PRIVATE changed'),
                        dict(resolution, outcome='charged_no_artifact', cost_usd='.08')):
            self.assertEqual(reconcile_job(job_id, library=self.library, resolution=changed,
                review_token=token, apply=True)['status'], 'blocked')
        self.edit_context(job_id, lambda c: c.update(operator_note='PRIVATE changed'))
        self.assertEqual(reconcile_job(job_id, library=self.library, resolution=resolution,
            review_token=token, apply=True)['status'], 'blocked')
        self.assertEqual(self.saved(job_id)['reviews'], [])

    def test_extra_unknown_or_retained_evidence_or_invalid_prior_accounting_block(self):
        job_id = self.unknown_job(lyrical=True)
        resolution = dict(outcome='confirmed_not_charged', cost_usd='0', evidence='PRIVATE ref')
        original = self.saved(job_id)
        path = self.library.root / '.executor' / 'jobs.sqlite3'
        unknown_id = original['calls'][1]['id']
        known_id = original['calls'][0]['id']
        cases = [
            ("UPDATE calls SET audio=? WHERE id=?", (b'paid-result', unknown_id)),
            ("UPDATE calls SET response=? WHERE id=?", ('{}', unknown_id)),
            ("UPDATE calls SET state=? WHERE id=?", ('unknown', known_id)),
            ("UPDATE calls SET accounting=? WHERE id=?", ('{"cost_usd":0}', known_id)),
        ]
        for sql, values in cases:
            with self.subTest(sql=sql):
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute(sql, values)
                self.assertFalse(reconcile_job(job_id, library=self.library, resolution=resolution)['can_reconcile'])
                with closing(sqlite3.connect(path)) as db, db:
                    for call in original['calls']:
                        db.execute('UPDATE calls SET state=?, audio=?, response=?, accounting=? WHERE id=?',
                            (call['state'], call['audio'], json.dumps(call['response']) if call['response'] is not None else None,
                             json.dumps(call['accounting']) if call['accounting'] is not None else None, call['id']))

    def test_derived_prior_accounting_is_attested_without_rewriting_raw_calls(self):
        job_id = self.unknown_job(lyrical=True)
        path = self.library.root / '.executor' / 'jobs.sqlite3'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("UPDATE calls SET accounting=NULL WHERE action='compose_lyrics'")
        original = self.saved(job_id)
        result, _, _ = self.resolve(job_id)
        self.assertEqual(result['prior_cost_usd'], .003)
        after = self.saved(job_id)
        self.assertEqual(after['calls'], original['calls'])
        self.assertEqual(after['reviews'][0]['data']['prior_accounting'][0]['cost_usd'], .003)

    def test_completed_or_lyrics_only_jobs_cannot_be_reconciled(self):
        job_id = self.retained_lyrics()
        resolution = dict(outcome='confirmed_not_charged', cost_usd='0', evidence='PRIVATE ref')
        self.assertFalse(reconcile_job(job_id, library=self.library, resolution=resolution)['can_reconcile'])
        token = continue_job(job_id, library=self.library)['review_token']
        self.assertEqual(self.apply_continuation(job_id, token)['status'], 'complete')
        self.assertFalse(reconcile_job(job_id, library=self.library, resolution=resolution)['can_reconcile'])


if __name__ == '__main__':
    unittest.main()
