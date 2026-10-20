"""Single-writer library preparation, including actor-scoped lyrical work."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from hold_music.lyria_client import MODEL
from hold_music.job_store import JobStore, inspect_jobs
from hold_music import knowledge_bridge, lyricist, repertoire
from hold_music.regional import (PALETTE, REGIONS, freeze_recipe, prompt_from_recipe,
                                 recipe_fingerprint, performance_mode)
from hold_music.recording_identity import VERSION_FIELDS, CONTRACT_FIELDS, identity_errors, recording_request
from tools.import_recording import ffmpeg_arguments

ESTIMATED_JOB_USD = Decimal('0.08')
ESTIMATED_LYRICS_USD = Decimal('0.01')


class WorkPlan(list):
    """Compatible job list with separate planner decisions and bridge reports."""
    def __init__(self):
        super().__init__()
        self.decisions = []
        self.bridge_reports = []


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')


def _usd(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('USD amount must be finite and nonnegative') from None
    if not amount.is_finite() or amount < 0:
        raise ValueError('USD amount must be finite and nonnegative')
    return amount


def plan_work(registry, library, *, performer_ids=None, target_per_performer=1,
              modes=('instrumental',), palette_path=PALETTE, db_path=None,
              now_hours=None, allow_name_match=False):
    """Fill each selected mode's deficit; wordless applies only to Winterhold."""
    _count(target_per_performer, 'target_per_performer')
    modes = tuple(dict.fromkeys(modes))
    if 'vocal' in modes:
        raise ValueError('Use lyrical with the knowledge bridge instead of vocal')
    if not modes or any(mode not in ('instrumental', 'wordless', 'lyrical') for mode in modes):
        raise ValueError('modes must contain instrumental, wordless and/or lyrical')
    if 'lyrical' in modes and db_path is None:
        raise ValueError('lyrical mode requires --db pointing to a SkyrimNet database')
    selected = None if performer_ids is None else set(performer_ids)
    known = {row['id'] for row in registry.performers}
    if selected is not None and selected - known:
        raise ValueError('Unknown performer IDs: ' + ', '.join(sorted(selected - known)))
    library.load()
    jobs = WorkPlan()
    for performer in registry.performers:
        pid, region, gender = (performer[key] for key in ('id', 'region', 'gender'))
        if selected is not None and pid not in selected:
            continue
        if performer.get('instrument', 'lute') != 'lute':
            jobs.decisions.append(dict(performer_id=pid, action='no_selection', topic_id=None,
                reasons=['The production executor supports the lute animation family only; '
                         f"registered instrument {performer.get('instrument')!r} is unsupported."]))
            continue
        if region is None:
            if 'lyrical' in modes:
                jobs.decisions.append(dict(performer_id=pid, action='no_selection',
                    topic_id=None, reasons=['Performer has no registered region.']))
            continue
        for requested in modes:
            if requested == 'lyrical':
                if performance_mode(region, 'vocal') != 'vocal':
                    jobs.decisions.append(dict(performer_id=pid, action='no_selection', topic_id=None,
                        reasons=['The regional recipe does not support lyrics; lyrical dispatch is unsupported.']))
                    continue
                recipe = freeze_recipe(region, 'vocal', gender, palette_path, model_id=MODEL)
                request = recording_request(recipe)
                snap, bridge_report = knowledge_bridge.snapshot(performer, db_path, library,
                    now_hours, request, allow_name_match=allow_name_match)
                jobs.bridge_reports.append(bridge_report)
                if not bridge_report['uuid_resolved'] or bridge_report['blocking_library_problems']:
                    jobs.decisions.append(dict(performer_id=pid, action='no_selection', topic_id=None,
                        reasons=['Unresolved actor identity or library validation problems.']))
                    continue
                decision = repertoire.plan(snap)
                jobs.decisions.append(decision)
                if target_per_performer == 0 or decision['action'] not in ('compose_lyrics', 'generate_recording'):
                    continue
                subject = decision.get('subject') or {}
                job = dict(recipe, performer_id=pid, performer=performer, topic_id=subject.get('topic_id'),
                    save_id=snap['save_id'], world_id=snap['world_id'], now_hours=snap['now_hours'],
                    palette_path=str(palette_path))
                if decision['action'] == 'compose_lyrics':
                    job['lyric_brief'] = decision['lyric_brief']
                else:
                    composition = next(c for c in snap['compositions'] if c['id'] == decision['composition_id'])
                    job.update(lyrics=composition['lyrics'], composition_id=composition['id'],
                               title=composition['title'], topic_id=composition.get('topic_id'),
                               source_observation_ids=composition.get('source_observation_ids', []))
                jobs.append(job)
                continue
            if requested == 'wordless' and region != 'winterhold':
                continue
            choice = 'instrumental' if requested == 'instrumental' else 'vocal'
            recipe = freeze_recipe(region, choice, gender, palette_path, model_id=MODEL)
            mode = recipe['mode']
            request = recording_request(recipe)
            ready = sum(row['playable'] for row in library.recordings
                        if (row['performer_id'], row['region'], row['mode'], row['gender']) ==
                        (pid, region, mode, gender) and recording_request(row) == request)
            if ready >= target_per_performer:
                continue
            prompt = prompt_from_recipe(recipe)
            for _ in range(target_per_performer - ready):
                jobs.append(dict(recipe, performer_id=pid, prompt=prompt, palette_path=str(palette_path)))
    return jobs


def convert_mp3(audio_bytes, destination, *, ffmpeg):
    source = destination.with_suffix('.mp3')
    source.write_bytes(audio_bytes)
    subprocess.run(ffmpeg_arguments(ffmpeg, source, destination), check=True,
                   capture_output=True, text=True)


def _validate_job(job):
    if job['region'] not in REGIONS or job['gender'] not in ('male', 'female'):
        raise ValueError('Invalid job region or gender')
    if job['mode'] not in ('instrumental', 'wordless', 'vocal'):
        raise ValueError('Unsupported recording mode')
    if job['mode'] == 'wordless' and job['region'] != 'winterhold':
        raise ValueError('Wordless jobs require Winterhold')
    if not isinstance(job['performer_id'], str) or not job['performer_id'].strip():
        raise ValueError('Invalid job performer')
    if job['recipe_id'] != f"{job['region']}/{job['mode']}":
        raise ValueError('Invalid job recipe')
    for key in ('arrangement', 'voice'):
        if key in job and (not isinstance(job[key], str) or not job[key].strip()):
            raise ValueError(f'Explicit {key} must be nonempty text')
    if job['mode'] == 'instrumental' and job.get('voice', 'none') != 'none':
        raise ValueError('Instrumental jobs must set voice to none')
    problems = identity_errors(job)
    if problems:
        raise ValueError('; '.join(problems))
    recipe = None
    if any(job.get(key) is not None for key in VERSION_FIELDS):
        recipe = freeze_recipe(job['region'], job['mode'], job['gender'],
                               job.get('palette_path', PALETTE), model_id=MODEL)
        if any(job.get(key) != recipe[key] for key in CONTRACT_FIELDS) or (
                job.get('prompt_prefix') != recipe['prompt_prefix']):
            raise ValueError('Stale or invalid production recording identity; create a new plan')
        if job['mode'] != 'vocal' and job.get('prompt') != prompt_from_recipe(recipe):
            raise ValueError('Production prompt does not match its frozen recipe')
    elif job.get('model_id', MODEL) != MODEL:
        raise ValueError('Unsupported generation model')
    if job['mode'] == 'vocal':
        if performance_mode(job['region'], 'vocal') != 'vocal':
            raise ValueError('Regional recipe does not support lyrics')
        if bool(job.get('lyric_brief')) == bool(job.get('lyrics')):
            raise ValueError('Vocal jobs require either a brief or existing lyrics')
        for key in ('save_id', 'world_id'):
            if not isinstance(job.get(key), str) or not job[key].strip():
                raise ValueError('Vocal jobs require a resolved timeline')
        _usd(job.get('now_hours'))
        # Freeze even explicitly unversioned vocal work before a lyric call,
        # while leaving the legacy job and published identity unversioned.
        return recipe or freeze_recipe(job['region'], 'vocal', job['gender'],
                                       job.get('palette_path', PALETTE), model_id=MODEL)
    prompt = job['prompt']
    if not isinstance(prompt, str) or not prompt.strip() or 'lyrics:' in prompt.casefold():
        raise ValueError('Jobs require a music prompt without a Lyrics: block')
    if job['mode'] == 'wordless' and (
            'Wordless singing with vocables only; no lyrics, sentences or spoken words.' not in prompt):
        raise ValueError('Wordless jobs require the vocables sentence')
    if job['recipe_id'] != f"{job['region']}/{job['mode']}":
        raise ValueError('Invalid job recipe')
    return recipe


def _public_plan(jobs, decisions, bridge_reports, show_briefs):
    if not decisions and not any(job['mode'] == 'vocal' for job in jobs):
        return jobs
    if show_briefs:
        return dict(jobs=jobs, decisions=decisions, bridge_reports=bridge_reports)
    public_jobs = [{key: job.get(key) for key in
        ('performer_id', 'region', 'mode', 'gender', 'recipe_id', 'topic_id',
         *VERSION_FIELDS, 'arrangement', 'voice', 'model_id')} for job in jobs]
    public_decisions = [dict(performer_id=decision['performer_id'], action=decision['action'],
        topic_id=(decision.get('subject') or {}).get('topic_id', decision.get('topic_id')),
        reasons=decision['reasons']) for decision in decisions]
    return dict(job_count=len(jobs), jobs=public_jobs, decisions=public_decisions,
                bridge_reports=bridge_reports)


def _accounting(request_id, usage, action, estimate, **extra):
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError('Generation returned no request ID')
    if usage is not None and not isinstance(usage, dict):
        raise ValueError('Invalid usage')
    estimated = usage is None or usage.get('cost') is None
    cost = estimate if estimated else _usd(usage['cost'])
    public_cost = float(cost)
    if not math.isfinite(public_cost):
        raise ValueError('Cost cannot be represented as finite report accounting')
    if 'duration_seconds' in extra:
        duration = extra['duration_seconds']
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError('Generation returned invalid audio duration')
    safe_usage = None if usage is None else {key: value for key, value in usage.items()
        if key in ('cost', 'prompt_tokens', 'completion_tokens', 'total_tokens')
        and type(value) in (int, float) and _usd(value).is_finite()}
    return dict(request_id=request_id, usage=safe_usage, action=action,
                cost_usd=public_cost, estimated=estimated, **extra)


def _publish_saved(store, job_id, library, executable):
    saved = store.job(job_id)
    if saved['state'] == 'closed':
        raise ValueError('Closed jobs cannot be published or reopened')
    context, calls = saved['context'], saved['calls']
    if any(c['state'] != 'returned' for c in calls):
        raise ValueError('Unknown provider outcome requires external reconciliation')
    music = [c for c in calls if c['action'] == 'generate_recording']
    if len(music) != 1 or not music[0]['audio']:
        raise ValueError('No retained music response is available for publication')
    # Recover a crash after response persistence but before accounting persistence.
    for call in calls:
        if call['accounting'] is None:
            response = call['response']
            extra = dict(model=call['model'])
            if call['action'] == 'generate_recording':
                extra['duration_seconds'] = response['duration_seconds']
            entry = _accounting(response.get('request_id'), response.get('usage'),
                                call['action'], _usd(call['estimate_usd']), **extra)
            store.account(call['id'], entry)
    response, audio = music[0]['response'], music[0]['audio']
    source = dict(kind='generated', path_or_request_id=response['request_id'],
                  sha256=hashlib.sha256(audio).hexdigest())
    job, scope = context['job'], context['scope']
    problems = identity_errors(job)
    if problems:
        raise ValueError('; '.join(problems))
    if any(job.get(key) is not None for key in VERSION_FIELDS) and (
            job['recipe_revision'] != recipe_fingerprint(job) or job['model_id'] != music[0]['model']
            or context.get('prompt') != prompt_from_recipe(job, context.get('lyrics'))):
        raise ValueError('Retained production recording identity is inconsistent')
    lyrics, title, prompt = (context.get(key) for key in ('lyrics', 'title', 'prompt'))
    region, mode = job['region'], job['mode']
    digest = hashlib.sha256((lyrics if lyrics is not None else prompt).encode('utf-8')).hexdigest()[:16]
    composition_id = (job.get('composition_id') or f"lyric:{job['topic_id']}:{digest}"
                      if mode == 'vocal' else f"gen:{region}:{mode}:{digest}:{response['request_id']}")
    receipts = context['receipts'] + [dict(scope, id=response['request_id'], action='generate_recording')]
    # Replay the retained identity verbatim. Recovery must never consult today's
    # palette or fill absent legacy metadata from current defaults.
    extra = {key: job[key] for key in (*VERSION_FIELDS, 'arrangement', 'voice') if key in job}
    if mode == 'vocal':
        extra.update(save_id=scope['save_id'], world_id=scope['world_id'],
            created_at_hours=scope['at_hours'], title=title, topic_id=job.get('topic_id'),
            source_observation_ids=job.get('lyric_brief', {}).get('source_observation_ids',
                job.get('source_observation_ids', [])))
    library.load()
    matches = [r for r in library.recordings if r.get('source') == source
               and r['performer_id'] == job['performer_id'] and r['composition_id'] == composition_id]
    if matches:
        expected = dict(extra, region=region, mode=mode, gender=job['gender'],
                        recipe_id=job['recipe_id'], model_id=music[0]['model'],
                        lyrics_sha256=hashlib.sha256(lyrics.encode('utf-8')).hexdigest()
                            if lyrics is not None else None)
        expected.update({key: job.get(key) for key in (*VERSION_FIELDS, 'arrangement', 'voice')})
        if (len(matches) != 1 or not matches[0]['playable'] or library.validate()
                or any(matches[0].get(key) != value for key, value in expected.items())
                or any(receipt not in library.generation_receipts for receipt in receipts)
                or hashlib.sha256((library.root / matches[0]['file']).read_bytes()).hexdigest()
                    != context.get('converted_wav_sha256')):
            raise ValueError('Previously published result requires library repair')
        # Covers a process dying after manifest commit but before journal commit.
        row = matches[0]
        store.update(job_id, state='completed', recording=row)
        return row
    store.update(job_id, state='publishing')
    with tempfile.TemporaryDirectory(prefix='.executor-', dir=library.root) as temp:
        wav = Path(temp) / 'converted.wav'
        convert_mp3(audio, wav, ffmpeg=executable)
        # Pin the exact converted asset before publishing can commit a manifest.
        # Source MP3 provenance alone cannot detect later replacement of the WAV.
        context = dict(context, converted_wav_sha256=hashlib.sha256(wav.read_bytes()).hexdigest())
        store.update(job_id, context=context)
        row = library.add_recording(wav, performer_id=job['performer_id'], region=region,
            mode=mode, gender=job['gender'], composition_id=composition_id, lyrics=lyrics,
            recipe_id=job['recipe_id'], model_id=music[0]['model'], source=source,
            generation_receipts=receipts, **extra)
    store.update(job_id, state='completed', recording=row)
    return row


def recover_publication(job_id, *, library, ffmpeg=None, apply=False):
    """Inspect or publish a retained result. This API has no provider client."""
    if not apply:
        summary = next((row for row in inspect_jobs(library.root) if row['job_id'] == job_id), None)
        if summary is None:
            raise ValueError('Unknown durable job ID')
        return dict(status='recovery_dry_run', job=summary, provider_calls=0)
    if not JobStore(library.root).path.is_file():
        raise ValueError('Unknown durable job ID')
    executable = shutil.which(str(ffmpeg or 'ffmpeg'))
    if executable is None:
        raise ValueError('ffmpeg was not found; supply --ffmpeg')
    with JobStore(library.root) as store:
        # The writable open above also recovers a hot SQLite rollback journal.
        # A read-only preflight here would prevent that crash recovery.
        store.job(job_id)
        try:
            row = _publish_saved(store, job_id, library, executable)
            return dict(status='complete', job_id=job_id, recordings=[row], provider_calls=0,
                        job=next(r for r in store.summaries() if r['job_id'] == job_id))
        except Exception as exc:
            store.fail(job_id, type(exc).__name__)
            return dict(status='failed', job_id=job_id, error_type=type(exc).__name__, provider_calls=0,
                        job=next(r for r in store.summaries() if r['job_id'] == job_id))


def execute(jobs, *, client, library, ffmpeg, max_jobs, max_usd, dry_run=True,
            spend=False, receipt_scope=('offline', 'offline'), lyric_model=lyricist.MODEL,
            show_briefs=False):
    """Bounded explicitly authorized generation with durable paid-call evidence.

    Unknown outcomes and unpublished paid responses block subsequent spending.
    Recovery can publish retained audio, but never retries a provider request.
    """
    _count(max_jobs, 'max_jobs')
    budget = _usd(max_usd)
    decisions = getattr(jobs, 'decisions', [])
    bridge_reports = getattr(jobs, 'bridge_reports', [])
    jobs = deepcopy(list(jobs))
    for job in jobs:
        _validate_job(job)
    if (len(receipt_scope) != 2 or
            any(not isinstance(value, str) or not value.strip() for value in receipt_scope)):
        raise ValueError('receipt_scope requires nonempty save_id and world_id')
    if dry_run or not spend:
        public = _public_plan(jobs, decisions, bridge_reports, show_briefs)
        print(json.dumps(public, ensure_ascii=False, indent=2))
        return {'status': 'dry_run', 'plan': public,
                'jobs': public if isinstance(public, list) else public['jobs'],
                'attempted': 0, 'cost_usd': 0, 'recordings': []}
    report = dict(status='complete', attempted=0, cost_usd=0, recordings=[], generations=[], jobs=[])
    if not jobs:
        return report
    if max_jobs == 0:
        report['status'] = 'max_jobs'
        return report
    total = Decimal(0)
    if budget < ESTIMATED_JOB_USD + (ESTIMATED_LYRICS_USD if jobs[0].get('lyric_brief') else 0):
        report['status'] = 'budget'
        return report
    with JobStore(library.root) as store:
        pending = store.summaries(pending_only=True)
        if pending:
            report.update(status='recovery_required', pending_jobs=pending)
            return report
        for job in jobs:
            if report['attempted'] >= max_jobs:
                report['status'] = 'max_jobs'
                break
            reserve = ESTIMATED_JOB_USD + (ESTIMATED_LYRICS_USD if job.get('lyric_brief') else 0)
            if total + reserve > budget:
                report['status'] = 'budget'
                break
            job_id = None
            try:
                # Validate again immediately before this job; a previous call
                # may have overlapped a recipe edit. The returned direction is
                # immutable input to this job's subsequent music request.
                recipe = _validate_job(job)
                executable = shutil.which(str(ffmpeg or 'ffmpeg'))
                if executable is None:
                    raise ValueError('ffmpeg was not found; supply --ffmpeg')
                if not library.free_slots():
                    raise ValueError('No writable free library slots')
                # Check scratch creation before any paid call.
                with tempfile.TemporaryDirectory(prefix='.executor-', dir=library.root):
                    pass
                scope = dict(performer_id=job['performer_id'],
                    save_id=job.get('save_id', receipt_scope[0]),
                    world_id=job.get('world_id', receipt_scope[1]), at_hours=job.get('now_hours', 0))
                context = dict(job=job, scope=scope, lyrics=job.get('lyrics'),
                               title=job.get('title'), receipts=[])
                if job['mode'] == 'vocal':
                    context['prompt_prefix'] = recipe['prompt_prefix']
                    context['region_label'] = recipe['region_label']
                job_id = store.begin_job(context)
                report['jobs'].append(job_id)
                report['attempted'] += 1

                def account(call_id, response, action, estimate, **extra):
                    nonlocal total
                    entry = _accounting(response.get('request_id'), response.get('usage'), action, estimate, **extra)
                    store.account(call_id, entry)
                    total += _usd(entry['cost_usd'])
                    report['cost_usd'] = float(total)
                    report['generations'].append(entry)

                class LyricClient:
                    def chat_completion(self, **kwargs):
                        call_id = store.begin_call(job_id, 'compose_lyrics', kwargs['model'], ESTIMATED_LYRICS_USD)
                        result = client.chat_completion(**kwargs)
                        # Persist the private response before parsing can fail.
                        store.returned(call_id, result)
                        account(call_id, result, 'compose_lyrics', ESTIMATED_LYRICS_USD, model=kwargs['model'])
                        return result

                if job.get('lyric_brief'):
                    composed = lyricist.write_lyrics(job['lyric_brief'], performer=job['performer'],
                        region_label=context['region_label'], gender=job['gender'],
                        client=LyricClient(), model=lyric_model)
                    context.update(lyrics=composed['lyrics'], title=composed['title'])
                    context['receipts'].append(dict(scope, id=composed['request_id'], action='compose_lyrics'))
                    store.update(job_id, state='lyrics_ready', context=context)
                    if total + ESTIMATED_JOB_USD > budget:
                        report['status'] = 'budget_exceeded' if total > budget else 'budget'
                        break
                context['prompt'] = (prompt_from_recipe(
                    dict(mode='vocal', prompt_prefix=context['prompt_prefix']), context['lyrics'])
                    if job['mode'] == 'vocal' else job['prompt'])
                store.update(job_id, context=context)
                call_id = store.begin_call(job_id, 'generate_recording', MODEL, ESTIMATED_JOB_USD)
                result = client.generate(context['prompt'])
                response = dict(request_id=result.request_id, usage=result.usage,
                                duration_seconds=result.duration_seconds)
                store.returned(call_id, response, audio=result.audio_bytes)
                account(call_id, response, 'generate_recording', ESTIMATED_JOB_USD,
                        duration_seconds=result.duration_seconds, model=MODEL)
                store.update(job_id, state='audio_ready')
                report['recordings'].append(_publish_saved(store, job_id, library, executable))
                if total > budget:
                    report['status'] = 'budget_exceeded'
                    break
            except Exception as exc:
                failure = {key: job[key] for key in ('performer_id', 'region', 'mode')}
                failure['error_type'] = type(exc).__name__
                with (library.root / 'executor.log').open('a', encoding='utf-8') as log:
                    log.write(json.dumps(failure, ensure_ascii=False) + '\n')
                if job_id is not None:
                    store.fail(job_id, type(exc).__name__)
                    saved = store.job(job_id)
                    if any(c['state'] == 'unknown' or c['accounting'] is None for c in saved['calls']):
                        report['unreported_attempt_cost'] = True
                report.update(status='failed', failure=failure)
                break
        report['durable_jobs'] = [s for s in store.summaries() if s['job_id'] in report['jobs']]
    return report
