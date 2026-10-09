"""Read-only, actor-scoped SkyrimNet snapshots. Contents are private, not logs.

This adapter targets the schema inspected on Halcyon; see docs/knowledge-bridge.md.
It never reads dialogue or unscoped world knowledge, or writes to SkyrimNet.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path
import re
import sqlite3

from hold_music.repertoire import Snapshot

TIME_NOTES = {
    'memories.game_time': 'Game seconds / 3600 = learned_at; happened_at equals learned_at only for direct evidence.',
    'events.game_time': 'Game seconds / 3600 = happened_at and learned_at for an originating/target actor.',
    'memories.creation_time': 'Observed epoch seconds despite Julian-date SQL default; never used as game time.',
    'memories.updated_at': 'Epoch-seconds field; all inspected actor rows null; never used as game time.',
    'events.local_time': 'Observed epoch seconds despite Julian-date SQL default; never used as game time.',
    'events.playtime': 'No established conversion to game hours; not used.',
    'now_hours': 'Last known in-game time: maximum across actor memories and all events; not a live clock.',
}


@contextmanager
def read_database(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('PRAGMA query_only=ON')
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')  # One consistent read snapshot across identity, clocks and rows.
        yield db
    finally:
        db.close()


def _resolve(performer, db, allow_name_match):
    form = performer.get('form')
    if not form:
        return None, 'unresolved'
    form_id = int(form['id'], 16) if isinstance(form['id'], str) else form['id']
    matches = {row[0] for row in db.execute(
        'SELECT uuid FROM uuid_mappings WHERE mod_file = ? COLLATE NOCASE AND local_form_id = ?',
        (form['plugin'], form_id))}
    matches.discard(0)
    if len(matches) == 1:
        return matches.pop(), 'plugin_base_form'
    if matches:  # An ambiguous form identity must not be overridden with a name.
        return None, 'ambiguous_base_form'
    if allow_name_match:
        matches = {row[0] for row in db.execute(
            'SELECT uuid FROM uuid_mappings WHERE mod_file = ? COLLATE NOCASE '
            'AND actor_name = ? COLLATE NOCASE', (form['plugin'], performer['name']))}
        matches.discard(0)
        if len(matches) == 1:
            return matches.pop(), 'plugin_actor_name'
        if matches:
            return None, 'ambiguous_actor_name'
    return None, 'unresolved'


def resolve_uuid(performer, db, *, allow_name_match=False):
    """Resolve a registry base identity, optionally an exact plugin-scoped name.

    db is a connection from read_database(), not a path or a copied database.
    """
    return _resolve(performer, db, allow_name_match)[0]


def _hours(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value / 3600


def _list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return [part.strip() for part in str(value).split(',') if part.strip()]
    return parsed if isinstance(parsed, list) else [parsed]


def _labels(memory_type, tags):
    return {re.sub(r'[\s-]+', '_', str(value).strip().casefold())
            for value in [memory_type or '', *_list(tags)] if isinstance(value, str) and value.strip()}


def classify(memory_type, tags):
    """Explicit metadata only; never infer an outcome from private prose."""
    labels = _labels(memory_type, tags)
    rumor = bool(labels & {'rumor', 'rumour', 'hearsay', 'gossip'})
    direct = bool(labels & {'witnessed', 'witness', 'direct', 'observation', 'witnessed_event', 'witnessed_completed_quest'}) and not rumor
    if direct and labels & {'quest_success', 'quest_completed', 'completed_quest', 'witnessed_completed_quest'}:
        kind = 'quest_success'
    elif labels & {'scandal', 'affair', 'theft', 'murder', 'theft_accusation', 'murder_accusation'}:
        kind = 'scandal'
    elif rumor:
        kind = 'gossip'
    elif (memory_type or '').strip().casefold() in {
            'experience', 'event', 'news', 'everyday_news', 'fact', 'knowledge',
            'witnessed', 'witness', 'direct', 'observation', 'witnessed_event',
            'quest_success', 'quest_completed', 'completed_quest'}:
        kind = 'everyday_news'
    else:
        kind = 'other'
    return kind, 'direct' if direct else 'rumor'


def _interest(value):
    return min(1.0, max(0.0, value)) if type(value) in (int, float) and math.isfinite(value) else 0.5


def _local(location, performer):
    if not isinstance(location, str) or not location.strip() or location.strip().casefold() in {'unknown', 'none'}:
        return 0.5
    names = {value.strip().casefold() for value in (performer.get('venue'), performer.get('region')) if value}
    return 1.0 if location.strip().casefold() in names else 0.2


def snapshot(performer, db_path, library, now_hours, request, *, max_observations=40,
             since_hours=None, allow_name_match=False):
    """Return (planner_snapshot, content-free bridge_report).

    None now_hours means the last known game time. since_hours is an absolute
    lower game-hour bound, excluding rows with unknown game time when supplied.
    """
    if type(max_observations) is not int or max_observations < 0:
        raise ValueError('max_observations must be a nonnegative integer')
    for name, value in (('now_hours', now_hours), ('since_hours', since_hours)):
        if value is not None and _hours(value) is None:
            raise ValueError(f'{name} must be finite nonnegative hours')
    save_id = Path(db_path).stem.removeprefix('SkyrimNet-')
    scope = dict(save_id=save_id, world_id=save_id)
    report = dict(performer_id=performer['id'], **scope, uuid_resolved=False,
                  resolution='unresolved', memories=0, events=0, observations=0,
                  time_domains=dict(TIME_NOTES), unresolved_fields=['playthrough_id', 'events.playtime'])
    observations = []
    with read_database(db_path) as db:
        actor, resolution = _resolve(performer, db, allow_name_match)
        report.update(uuid_resolved=actor is not None, resolution=resolution)
        if now_hours is None:
            clocks = [row[0] for row in db.execute(
                'SELECT max(game_time) FROM memories WHERE actor_uuid = ? '
                'UNION ALL SELECT max(game_time) FROM events', (actor,))]
            now_hours = max((_hours(value) for value in clocks if _hours(value) is not None), default=0.0)
        else:
            report['time_domains']['now_hours'] = 'Caller-supplied in-game hours; not inferred from wall clock.'
        report['now_hours'] = now_hours
        if actor is None:
            report['unresolved_fields'].append('actor_uuid')
        else:
            sources = (
                ('memories', 'actor_uuid = ?', (actor,)),
                ('events', '(originating_actor_UUID = ? OR target_actor_UUID = ?)', (actor, actor)),
            )
            for table, where, args in sources:
                report[table] = db.execute(f'SELECT count(*) FROM {table} WHERE {where}', args).fetchone()[0]
                if since_hours is not None:
                    where += ' AND game_time >= ?'
                    args += (since_hours * 3600,)
                # Select only these actor's rows. No dialogue or global memory query.
                rows = db.execute(f'SELECT * FROM {table} WHERE {where} '
                                  'ORDER BY game_time DESC, id DESC LIMIT ?', (*args, max_observations))
                for row in rows:
                    memory = table == 'memories'
                    identity = f"{'mem' if memory else 'evt'}:{row['id']}"
                    summary = row['content'] if memory else row['event_data']
                    if not isinstance(summary, str) or not summary.strip():
                        continue
                    when = _hours(row['game_time'])
                    if memory:
                        kind, evidence = classify(row['memory_type'], row['tags'])
                        related = [value for value in _list(row['related_event_ids'])
                                   if type(value) is int and value > 0 or
                                   isinstance(value, str) and value.isdecimal() and int(value) > 0]
                        event_id = f'evt:{related[0]}' if related else identity
                    else:
                        kind, _ = classify(row['event_type'], '["witnessed"]')
                        evidence, event_id = 'direct', identity
                    observations.append(dict(scope, id=identity, performer_id=performer['id'],
                        event_id=event_id, topic_id=event_id, kind=kind, summary=summary.strip()[:500],
                        happened_at=when if evidence == 'direct' else None, learned_at=when,
                        source_id=f"skyrimnet:{'memory' if memory else 'event'}:{row['id']}",
                        evidence=evidence, interest=_interest(row['importance_score']) if memory else 0.5,
                        local_relevance=_local(row['location'], performer)))
    observations.sort(key=lambda row: (row['learned_at'] is not None,
                                      row['learned_at'] or 0, row['id']), reverse=True)
    observations = observations[:max_observations]
    report.update(observations=len(observations),
                  memory_observations=sum(row['id'].startswith('mem:') for row in observations),
                  event_observations=sum(row['id'].startswith('evt:') for row in observations),
                  unknown_happened_at=sum(row['happened_at'] is None for row in observations),
                  unknown_learned_at=sum(row['learned_at'] is None for row in observations))
    if report['unknown_happened_at']:
        report['unresolved_fields'].append('observations.happened_at')
    if report['unknown_learned_at']:
        report['unresolved_fields'].append('observations.learned_at')
    result = library.snapshot(performer['id'], save_id, save_id, now_hours, request)
    # The library retains extra manifest metadata but its core snapshot omits it.
    included_slots = {int(row['id'].removeprefix('slot:')) for row in result['recordings']}
    metadata = {row['composition_id']: row for row in library.recordings
                if row['slot'] in included_slots}
    for composition in result['compositions']:
        row = metadata[composition['id']]
        for key in ('topic_id', 'source_observation_ids', 'title'):
            if key in row:
                composition[key] = row[key]
    result.update(observations=observations, policy={'selection': 'topical_when_salient'})
    Snapshot.from_dict(result)
    report['library_problems'] = len(library.problems)
    report['blocking_library_problems'] = len(library._write_errors)
    return result, report
