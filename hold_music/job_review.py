"""Reviewed continuation and operator reconciliation of private retained jobs.

Tokens identify the exact reviewed state and operation; they are not credentials.
Nothing in this module retries a historical music request.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
import math
from pathlib import Path
import shutil
import tempfile

from hold_music.executor import (_accounting, _count, _publish_saved, _usd,
                                 ESTIMATED_JOB_USD)
from hold_music.job_store import JobStore, readonly_store
from hold_music.lyria_client import MODEL
from hold_music.lyricist import parse_lyrics
from hold_music.recording_identity import VERSION_FIELDS, CONTRACT_FIELDS, identity_errors
from hold_music.regional import REGIONS, performance_mode, prompt_from_recipe, recipe_fingerprint


def _digest(value):
    """Hash private persisted values without putting their contents in a report."""
    if isinstance(value, bytes):
        return dict(bytes_sha256=hashlib.sha256(value).hexdigest(), length=len(value))
    if isinstance(value, dict):
        return {key: _digest(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_digest(item) for item in value]
    return value


def _hash(value):
    raw = json.dumps(_digest(value), sort_keys=True, ensure_ascii=False,
                     separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _money(value):
    amount = _usd(value)
    number = float(amount)
    if not math.isfinite(number) or amount > 0 and number == 0:
        raise ValueError('USD amount must have a finite report representation')
    return amount


def _amount_text(value):
    return str(_money(value).normalize())


def _clock(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Retained clock must be a finite nonnegative number')


def _token(saved, library, operation):
    fingerprint = _hash(saved)
    token = 'review-v1:' + _hash(dict(job_fingerprint=fingerprint,
        library=str(Path(library.root).resolve()), operation=operation))
    return fingerprint, token


def _matches(actual, expected):
    return (isinstance(actual, str) and isinstance(expected, str) and actual.isascii()
            and expected.isascii() and hmac.compare_digest(actual, expected))


def _call_accounting(call):
    if call['state'] != 'returned' or not isinstance(call['response'], dict):
        raise ValueError('Returned provider evidence is required')
    if call['action'] not in ('compose_lyrics', 'generate_recording'):
        raise ValueError('Unsupported retained provider action')
    if not isinstance(call['model'], str) or not call['model'].strip():
        raise ValueError('Retained provider model is missing')
    response = call['response']
    extra = dict(model=call['model'])
    if call['action'] == 'generate_recording':
        extra['duration_seconds'] = response.get('duration_seconds')
    expected = _accounting(response.get('request_id'), response.get('usage'), call['action'],
                           _money(call['estimate_usd']), **extra)
    if call['accounting'] is not None and call['accounting'] != expected:
        raise ValueError('Retained accounting conflicts with the provider response')
    return expected


def _prior_report(entries):
    total = sum((_money(row['cost_usd']) for row in entries), _money(0))
    return dict(prior_cost_usd=float(_money(total)), prior_accounting=entries,
                prior_cost_includes_estimates=any(row['estimated'] for row in entries))


def _continuation_context(saved):
    """Validate and locally reconstruct one interrupted, versioned lyric result."""
    if saved['state'] not in ('lyrics_ready', 'response_received', 'failed'):
        raise ValueError('Job is not a retained lyric result awaiting music')
    if saved['recording'] is not None or saved['reviews']:
        raise ValueError('Job has already been published or reviewed for dispatch')
    calls = saved['calls']
    if len(calls) != 1 or calls[0]['action'] != 'compose_lyrics' or calls[0]['audio'] is not None:
        raise ValueError('Continuation requires exactly one lyric call and no historical music call')
    call = calls[0]
    accounting = _call_accounting(call)
    context = deepcopy(saved['context'])
    job = context['job']
    if identity_errors(job) or not all(isinstance(job.get(key), str) and job[key].strip()
                                      for key in VERSION_FIELDS):
        raise ValueError('Continuation requires a complete versioned recording identity')
    if (job.get('region') not in REGIONS or job.get('mode') != 'vocal'
            or performance_mode(job['region'], 'vocal') != 'vocal'
            or job.get('gender') not in ('male', 'female')
            or job.get('voice') != job['gender'] or job.get('arrangement') != 'solo_lute_and_voice'
            or job.get('instrument_family') != 'plucked_string' or job.get('model_id') != MODEL
            or job.get('recipe_id') != f"{job['region']}/vocal"
            or job.get('recipe_revision') != recipe_fingerprint(job)):
        raise ValueError('Retained production identity is incompatible or inconsistent')
    if (not isinstance(job.get('lyric_brief'), dict) or not job['lyric_brief'] or job.get('lyrics')
            or not isinstance(job.get('performer_id'), str) or not job['performer_id'].strip()):
        raise ValueError('Retained job must originate from one actor-scoped lyric composition')
    if not isinstance(job.get('topic_id'), str) or not job['topic_id'].strip():
        raise ValueError('Retained lyric composition requires a topic identity')
    if 'composition_id' in job and (
            not isinstance(job['composition_id'], str) or not job['composition_id'].strip()):
        raise ValueError('Explicit retained composition identity must be nonempty text')
    brief = job['lyric_brief']
    for key, expected in (('topic_id', job['topic_id']), ('performer_id', job['performer_id']),
                          ('tradition', job['region'])):
        if key in brief and brief[key] != expected:
            raise ValueError('Retained lyric brief conflicts with its composition scope')
    sources = brief.get('source_observation_ids', job.get('source_observation_ids', []))
    if not isinstance(sources, list) or any(not isinstance(value, str) or not value.strip() for value in sources):
        raise ValueError('Retained source observation identities must be a list of nonempty text')
    for key in ('save_id', 'world_id'):
        if not isinstance(job.get(key), str) or not job[key].strip():
            raise ValueError('Retained job requires its original save and world scope')
    _clock(job.get('now_hours'))
    if not isinstance(context.get('scope'), dict):
        raise ValueError('Retained scope is missing')
    _clock(context['scope'].get('at_hours'))
    scope = dict(performer_id=job['performer_id'], save_id=job['save_id'],
                 world_id=job['world_id'], at_hours=job['now_hours'])
    if context.get('scope') != scope or context.get('prompt_prefix') != job['prompt_prefix']:
        raise ValueError('Retained scope or prompt prefix conflicts with the original job')
    if context.get('region_label') != job.get('region_label'):
        raise ValueError('Retained regional context conflicts with the original job')
    title, lyrics = parse_lyrics(call['response'].get('content'))
    for key, value in (('title', title), ('lyrics', lyrics)):
        if context.get(key) is not None and context[key] != value:
            raise ValueError('Saved title or lyrics conflict with the retained lyric response')
    receipt = dict(scope, id=call['response']['request_id'], action='compose_lyrics')
    if context.get('receipts') not in ([], [receipt]):
        raise ValueError('Saved lyric receipt conflicts with retained provider evidence')
    for saved_receipt in context['receipts']:
        _clock(saved_receipt.get('at_hours'))
    prompt = prompt_from_recipe(job, lyrics)
    if context.get('prompt') is not None and context['prompt'] != prompt:
        raise ValueError('Saved music prompt conflicts with its frozen direction and lyrics')
    context.update(title=title, lyrics=lyrics, prompt=prompt, receipts=[receipt])
    return context, call, accounting


def _publication_preflight(context, library):
    """Check already-known publication conflicts before authorizing new music.

    free_slots() must have refreshed and validated the selected library first.
    Future provider IDs, audio and usage can only be validated after they return.
    """
    job = context['job']
    lyrics_hash = hashlib.sha256(context['lyrics'].encode('utf-8')).hexdigest()
    composition_id = job.get('composition_id') or f"lyric:{job['topic_id']}:{lyrics_hash[:16]}"
    for row in library.recordings:
        if row['composition_id'] == composition_id and (
                row['region'] != job['region']
                or row['lyrics_sha256'] is not None and row['lyrics_sha256'] != lyrics_hash):
            raise ValueError('Retained composition conflicts with existing immutable content')
    prior_ids = {(row['save_id'], row['world_id'], row['id']) for row in library.generation_receipts}
    if any((row['save_id'], row['world_id'], row['id']) in prior_ids for row in context['receipts']):
        raise ValueError('Retained lyric receipt is already present in the library')


def _continuation_operation(library, max_jobs, max_usd, ffmpeg):
    _count(max_jobs, 'max_jobs')
    budget = _money(max_usd)
    return dict(kind='continuation', max_jobs=max_jobs, max_usd=_amount_text(budget),
                ffmpeg=None if ffmpeg is None else str(ffmpeg),
                receipts_source=str(Path(library.receipts_source).resolve()),
                session_receipt_index=library.session_receipt_index)


def _continuation_preview(store, saved, library, *, max_jobs, max_usd, ffmpeg, show_briefs):
    operation = _continuation_operation(library, max_jobs, max_usd, ffmpeg)
    budget = _money(max_usd)
    fingerprint, token = _token(saved, library, operation)
    report = dict(status='continuation_dry_run', job_id=saved['id'], state=saved['state'],
        can_continue=False, blockers=[], review_token=None, state_fingerprint=fingerprint,
        provider_calls=0, new_reservation_usd=float(ESTIMATED_JOB_USD),
        reservation_is_estimate=True, max_jobs=max_jobs, max_usd=float(budget))
    context = call = accounting = None
    try:
        context, call, accounting = _continuation_context(saved)
        job = context['job']
        report.update(_prior_report([accounting]))
        report['identity'] = {key: job.get(key) for key in
                              ('performer_id', 'region', 'gender', *CONTRACT_FIELDS)}
        report['scope'] = context['scope']
        report['lyrics_sha256'] = hashlib.sha256(context['lyrics'].encode('utf-8')).hexdigest()
        report['prompt_sha256'] = hashlib.sha256(context['prompt'].encode('utf-8')).hexdigest()
        if show_briefs:
            report['private'] = dict(title=context['title'], lyrics=context['lyrics'],
                                     prompt=context['prompt'], lyric_brief=job['lyric_brief'])
    except (ValueError, KeyError, TypeError, OverflowError):
        report['blockers'].append('Retained lyrics, scope, identity or accounting are missing, conflicting or unsupported.')
    other_pending = [row['job_id'] for row in store.summaries(pending_only=True)
                     if row['job_id'] != saved['id']]
    if other_pending:
        report['blockers'].append('Other unresolved jobs must be reviewed first.')
        report['other_pending_jobs'] = other_pending
    if max_jobs < 1:
        report['blockers'].append('The job limit must authorize one recording.')
    if budget < ESTIMATED_JOB_USD:
        report['blockers'].append('The new-call budget is below the music reservation.')
    report['can_continue'] = not report['blockers']
    if report['can_continue']:
        report['review_token'] = token
    return report, context, call, accounting, operation


def _already_applied(saved, review_token, kind, resolution=None, operation=None):
    for review in saved['reviews']:
        if review['kind'] == kind and _matches(review_token, review['review_token']):
            if resolution is not None and review['data'].get('resolution') != resolution:
                return None
            if operation is not None and review['data'].get('operation') != operation:
                return None
            return dict(status='already_applied', job_id=saved['id'], state=saved['state'],
                        review_token=review_token, provider_calls=0)
    return None


def continue_job(job_id, *, library, client=None, ffmpeg=None, max_jobs=1, max_usd='0.10',
                 review_token=None, dry_run=True, spend=False, show_briefs=False):
    """Review, then dispatch at most one first music call for retained lyrics."""
    if dry_run or not spend:
        with readonly_store(library.root) as store:
            return _continuation_preview(store, store.job(job_id), library, max_jobs=max_jobs,
                max_usd=max_usd, ffmpeg=ffmpeg, show_briefs=show_briefs)[0]
    if not JobStore(library.root).path.is_file():
        raise ValueError('No durable job journal exists')
    with JobStore(library.root, recover_interrupted=False) as store:
        saved = store.job(job_id)
        operation = _continuation_operation(library, max_jobs, max_usd, ffmpeg)
        repeated = _already_applied(saved, review_token, 'continuation', operation=operation)
        if repeated:
            return repeated
        report, context, lyric_call, lyric_accounting, operation = _continuation_preview(
            store, saved, library, max_jobs=max_jobs, max_usd=max_usd, ffmpeg=ffmpeg, show_briefs=False)
        report['status'] = 'blocked'
        if not report['can_continue']:
            return report
        if not _matches(review_token, report['review_token']):
            report['blockers'].append('A matching current review token is required.')
            report['can_continue'] = False
            return report
        if client is None:
            report['blockers'].append('An explicit generation client is required for the authorized call.')
            report['can_continue'] = False
            return report
        try:
            executable = shutil.which(str(ffmpeg or 'ffmpeg'))
            if executable is None:
                raise ValueError('Missing encoder')
            if not library.free_slots():
                raise ValueError('No free library slots')
            _publication_preflight(context, library)
            with tempfile.TemporaryDirectory(prefix='.executor-', dir=library.root):
                pass
        except (ValueError, OSError):
            report['blockers'].append(
                'Encoder, library validation, composition or receipt conflicts, writable scratch space or free slots failed preflight.')
            report['can_continue'] = False
            return report
        report.update(status='complete', attempted=1, provider_calls=0, cost_usd=0,
                      recordings=[], generations=[])
        try:
            call_id = store.authorize_continuation(job_id, review_token=review_token,
                fingerprint=report['state_fingerprint'], context=context,
                lyric_call_id=lyric_call['id'], lyric_accounting=lyric_accounting,
                model=context['job']['model_id'], estimate=ESTIMATED_JOB_USD,
                authorization=dict(operation=operation, prior_call_id=lyric_call['id'],
                                   new_reservation_usd=str(ESTIMATED_JOB_USD)))
            report['provider_calls'] = 1
            result = client.generate(context['prompt'])
            response = dict(request_id=result.request_id, usage=result.usage,
                            duration_seconds=result.duration_seconds)
            store.returned(call_id, response, audio=result.audio_bytes)
            accounting = _accounting(result.request_id, result.usage, 'generate_recording',
                ESTIMATED_JOB_USD, duration_seconds=result.duration_seconds, model=context['job']['model_id'])
            store.account(call_id, accounting)
            report['generations'].append(accounting)
            report['cost_usd'] = accounting['cost_usd']
            store.update(job_id, state='audio_ready')
            report['recordings'].append(_publish_saved(store, job_id, library, executable))
            if _money(report['cost_usd']) > _money(max_usd):
                report['status'] = 'budget_exceeded'
        except Exception as exc:
            store.fail(job_id, type(exc).__name__)
            report.update(status='failed', error_type=type(exc).__name__)
            calls = store.job(job_id)['calls']
            if any(call['state'] in ('in_flight', 'unknown') or call['accounting'] is None for call in calls):
                report['unreported_attempt_cost'] = True
        report['job'] = next(row for row in store.summaries() if row['job_id'] == job_id)
        return report


def _resolution(value):
    if not isinstance(value, dict) or set(value) != {'outcome', 'cost_usd', 'evidence'}:
        raise ValueError('Resolution requires outcome, cost_usd and private evidence')
    if value['outcome'] not in ('confirmed_not_charged', 'charged_no_artifact'):
        raise ValueError('Unsupported operator resolution outcome')
    amount = _money(value['cost_usd'])
    if (value['outcome'] == 'confirmed_not_charged' and amount != 0
            or value['outcome'] == 'charged_no_artifact' and amount <= 0):
        raise ValueError('Resolution cost conflicts with the declared outcome')
    if not isinstance(value['evidence'], str) or not value['evidence'].strip():
        raise ValueError('A private operator attestation or reference is required')
    return dict(outcome=value['outcome'], cost_usd=_amount_text(amount), evidence=value['evidence'])


def _reconciliation_preview(saved, library, resolution):
    fingerprint, token = _token(saved, library, dict(kind='reconciliation', resolution=resolution))
    report = dict(status='reconciliation_dry_run', job_id=saved['id'], state=saved['state'],
        can_reconcile=False, blockers=[], review_token=None, state_fingerprint=fingerprint, provider_calls=0,
        resolution=dict(outcome=resolution['outcome'], cost_usd=resolution['cost_usd'],
                        provenance='operator_report', provider_verified=False,
                        applies_to='single_uncertain_call'))
    target = None
    try:
        if saved['state'] in ('completed', 'closed') or saved['recording'] is not None or not saved['calls']:
            raise ValueError('Terminal or unattempted job')
        unknown = [call for call in saved['calls'] if call['state'] in ('unknown', 'in_flight')]
        if len(unknown) != 1:
            raise ValueError('Exactly one uncertain call is required')
        target = unknown[0]
        if (target['response'] is not None or target['audio'] is not None or target['accounting'] is not None
                or target['action'] not in ('compose_lyrics', 'generate_recording')
                or not isinstance(target['model'], str) or not target['model'].strip()):
            raise ValueError('Uncertain call contains conflicting retained evidence')
        others = [_call_accounting(call) for call in saved['calls'] if call['id'] != target['id']]
        report.update(_prior_report(others))
        report['uncertain_call'] = dict(id=target['id'], action=target['action'], model=target['model'],
                                        raw_state=target['state'])
    except (ValueError, KeyError, TypeError, OverflowError):
        report['blockers'].append('Only one uncertain call without retained result can be reconciled; other call accounting must be valid.')
    report['can_reconcile'] = not report['blockers']
    if report['can_reconcile']:
        report['review_token'] = token
    return report, target


def reconcile_job(job_id, *, library, resolution, review_token=None, apply=False):
    """Append an operator attestation and close, preserving all raw call evidence."""
    resolution = _resolution(resolution)
    if not apply:
        with readonly_store(library.root) as store:
            return _reconciliation_preview(store.job(job_id), library, resolution)[0]
    if not JobStore(library.root).path.is_file():
        raise ValueError('No durable job journal exists')
    with JobStore(library.root, recover_interrupted=False) as store:
        saved = store.job(job_id)
        repeated = _already_applied(saved, review_token, 'reconciliation', resolution)
        if repeated:
            repeated['resolution'] = dict(outcome=resolution['outcome'], cost_usd=resolution['cost_usd'],
                                          provenance='operator_report', provider_verified=False,
                                          applies_to='single_uncertain_call')
            return repeated
        report, target = _reconciliation_preview(saved, library, resolution)
        report['status'] = 'blocked'
        if not report['can_reconcile']:
            return report
        if not _matches(review_token, report['review_token']):
            report['blockers'].append('A matching current review token is required.')
            report['can_reconcile'] = False
            return report
        store.close_with_attestation(job_id, review_token=review_token,
            fingerprint=report['state_fingerprint'], attestation=dict(
                resolution=resolution, provenance='operator_report', provider_verified=False,
                uncertain_call_id=target['id'], raw_call_state=target['state'],
                prior_accounting=report['prior_accounting']))
        report['status'] = 'closed'
        report['job'] = next(row for row in store.summaries() if row['job_id'] == job_id)
        return report
