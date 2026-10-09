"""Single-writer, offline instrumental/wordless library preparation."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from hold_music.lyria_client import MODEL
from hold_music.regional import PALETTE, REGIONS, music_prompt, performance_mode
from tools.import_recording import ffmpeg_arguments

ESTIMATED_JOB_USD = Decimal('0.08')


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
              modes=('instrumental',), palette_path=PALETTE):
    """Fill each selected mode's deficit; wordless applies only to Winterhold."""
    _count(target_per_performer, 'target_per_performer')
    modes = tuple(dict.fromkeys(modes))
    if 'vocal' in modes:
        raise ValueError('vocal is deferred to the knowledge bridge; use instrumental or wordless')
    if not modes or any(mode not in ('instrumental', 'wordless') for mode in modes):
        raise ValueError('modes must contain instrumental and/or wordless')
    selected = None if performer_ids is None else set(performer_ids)
    known = {row['id'] for row in registry.performers}
    if selected is not None and selected - known:
        raise ValueError('Unknown performer IDs: ' + ', '.join(sorted(selected - known)))
    library.load()
    jobs = []
    for performer in registry.performers:
        pid, region, gender = (performer[key] for key in ('id', 'region', 'gender'))
        if region is None or (selected is not None and pid not in selected):
            continue
        for requested in modes:
            if requested == 'wordless' and region != 'winterhold':
                continue
            choice = 'instrumental' if requested == 'instrumental' else 'vocal'
            mode = performance_mode(region, choice)
            ready = sum(row['playable'] for row in library.recordings
                        if (row['performer_id'], row['region'], row['mode'], row['gender']) ==
                        (pid, region, mode, gender))
            if ready >= target_per_performer:
                continue
            prompt = music_prompt(region, choice, gender, palette_path=palette_path)
            for _ in range(target_per_performer - ready):
                jobs.append(dict(performer_id=pid, region=region, mode=mode, gender=gender,
                                 recipe_id=f'{region}/{mode}', prompt=prompt))
    return jobs


def convert_mp3(audio_bytes, destination, *, ffmpeg):
    source = destination.with_suffix('.mp3')
    source.write_bytes(audio_bytes)
    subprocess.run(ffmpeg_arguments(ffmpeg, source, destination), check=True,
                   capture_output=True, text=True)


def _validate_job(job):
    if job['region'] not in REGIONS or job['gender'] not in ('male', 'female'):
        raise ValueError('Invalid job region or gender')
    if job['mode'] not in ('instrumental', 'wordless'):
        raise ValueError('Only instrumental and wordless jobs are supported')
    if job['mode'] == 'wordless' and job['region'] != 'winterhold':
        raise ValueError('Wordless jobs require Winterhold')
    if not isinstance(job['performer_id'], str) or not job['performer_id'].strip():
        raise ValueError('Invalid job performer')
    prompt = job['prompt']
    if not isinstance(prompt, str) or not prompt.strip() or 'lyrics:' in prompt.casefold():
        raise ValueError('Jobs require a music prompt without a Lyrics: block')
    if job['mode'] == 'wordless' and (
            'Wordless singing with vocables only; no lyrics, sentences or spoken words.' not in prompt):
        raise ValueError('Wordless jobs require the vocables sentence')
    if job['recipe_id'] != f"{job['region']}/{job['mode']}":
        raise ValueError('Invalid job recipe')


def execute(jobs, *, client, library, ffmpeg, max_jobs, max_usd, dry_run=True,
            spend=False, receipt_scope=('offline', 'offline')):
    """Return a JSON-safe run report. Both spend=True and dry_run=False are needed.

    Reserve an estimated $0.08 before each call, then account for reported cost.
    A provider charge can exceed that estimate; stop before any subsequent call.
    Failure messages deliberately contain only the exception class, not its text.
    """
    _count(max_jobs, 'max_jobs')
    budget = _usd(max_usd)
    jobs = list(jobs)
    for job in jobs:
        _validate_job(job)
    if (len(receipt_scope) != 2 or
            any(not isinstance(value, str) or not value.strip() for value in receipt_scope)):
        raise ValueError('receipt_scope requires nonempty save_id and world_id')
    if dry_run or not spend:
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
        return {'status': 'dry_run', 'jobs': jobs, 'attempted': 0, 'cost_usd': 0,
                'recordings': []}
    report = dict(status='complete', attempted=0, cost_usd=0, recordings=[], generations=[])
    total = Decimal(0)
    for job in jobs:
        if report['attempted'] >= max_jobs:
            report['status'] = 'max_jobs'
            break
        if total + ESTIMATED_JOB_USD > budget:
            report['status'] = 'budget'
            break
        try:
            executable = shutil.which(str(ffmpeg or 'ffmpeg'))
            if executable is None:
                raise ValueError('ffmpeg was not found; supply --ffmpeg')
            if not library.free_slots():
                raise ValueError('No writable free library slots')
            library.root.mkdir(parents=True, exist_ok=True)
            # Stage before dispatch so a scratch-directory failure cannot cost money.
            with tempfile.TemporaryDirectory(prefix='.executor-', dir=library.root) as temp:
                report['attempted'] += 1
                result = client.generate(job['prompt'])
                if not isinstance(result.request_id, str) or not result.request_id.strip():
                    raise ValueError('Generation returned no request ID')
                usage = result.usage
                estimated = usage is None or 'cost' not in usage or usage['cost'] is None
                cost = ESTIMATED_JOB_USD if estimated else _usd(usage['cost'])
                total += cost
                report['cost_usd'] = float(total)
                report['generations'].append(dict(request_id=result.request_id, usage=usage,
                    cost_usd=float(cost), estimated=estimated, duration_seconds=result.duration_seconds))
                wav = Path(temp) / 'converted.wav'
                convert_mp3(result.audio_bytes, wav, ffmpeg=executable)
                region, mode = job['region'], job['mode']
                digest = hashlib.sha256(job['prompt'].encode('utf-8')).hexdigest()[:16]
                receipt = dict(id=result.request_id, performer_id=job['performer_id'],
                    save_id=receipt_scope[0], world_id=receipt_scope[1],
                    action='generate_recording', at_hours=0)
                row = library.add_recording(wav, performer_id=job['performer_id'], region=region,
                    mode=mode, gender=job['gender'],
                    composition_id=f'gen:{region}:{mode}:{digest}:{result.request_id}',
                    recipe_id=f'{region}/{mode}', model_id=MODEL,
                    source={'kind': 'generated', 'path_or_request_id': result.request_id,
                            'sha256': hashlib.sha256(result.audio_bytes).hexdigest()},
                    generation_receipts=[receipt])
                report['recordings'].append(row)
            if total > budget:
                report['status'] = 'budget_exceeded'
                break
        except Exception as exc:
            failure = {key: job[key] for key in ('performer_id', 'region', 'mode')}
            failure['error_type'] = type(exc).__name__
            library.root.mkdir(parents=True, exist_ok=True)
            with (library.root / 'executor.log').open('a', encoding='utf-8') as log:
                log.write(json.dumps(failure, ensure_ascii=False) + '\n')
            report.update(status='failed', failure=failure)
            # Unknown outcomes may have incurred a charge; never label it zero.
            if report['attempted'] > len(report['generations']):
                report['unreported_attempt_cost'] = True
            break
    return report
