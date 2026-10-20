"""Read-only upsert review for a candidate performer's runtime contract.

The candidate source's identity rules are audited; no installed selector, live
lock, cooldown, registry region or actual ChooseSlot result is established.
"""
from __future__ import annotations

from copy import deepcopy
import math
import os
from pathlib import Path

from hold_music.installed_library import (
    RECEIPTS_PATH, _Snapshot, _digest, inspect_installed_library,
)
from hold_music.library import MODES, SLOTS, _recording_errors
from hold_music.library_merge import _json
from hold_music.promotion import _no_alias
from hold_music.recording_identity import VERSION_FIELDS
from hold_music.runtime_contract import (
    RUNTIME_CONTRACT_FIELDS, manifest_runtime_selection_errors,
    recording_contract_errors, recording_runtime_identity_errors, runtime_selection_errors,
)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _marked(row):
    return isinstance(row, dict) and any(key in row for key in (*VERSION_FIELDS, 'identity_key'))


def _selection(manifest):
    if not isinstance(manifest, dict):
        return False, {}, ['No valid current manifest']
    if 'runtime_selection' not in manifest:
        return False, {}, []
    value = manifest['runtime_selection']
    errors = runtime_selection_errors(value)
    if errors:
        return True, {}, errors
    return True, {row['performer_id'].casefold(): row for row in value['contracts']}, []


def _core_reasons(row):
    """Candidate metadata prerequisites, deliberately separate from identity."""
    if not isinstance(row, dict):
        return ['recording must be an object']
    reasons = []
    if type(row.get('slot')) is not int or not 1 <= row['slot'] <= SLOTS:
        reasons.append('slot must be an integer from 1 to 24')
    for key in ('performer_id', 'region', 'composition_id'):
        if not _text(row.get(key)):
            reasons.append(key + ' must be nonempty text')
    duration = row.get('duration_seconds')
    try:
        valid_duration = type(duration) in (int, float) and math.isfinite(duration) and duration > 0
    except OverflowError:
        valid_duration = False
    if not valid_duration:
        reasons.append('duration_seconds must be positive and finite')
    if row.get('mode') not in MODES:
        reasons.append('mode must be vocal, wordless or instrumental')
    return reasons


def _route(contract, marked, global_errors, projection_available=True):
    if not projection_available:
        return 'unavailable_projection'
    if global_errors:
        return 'blocked_global_selection'
    if contract is not None:
        return 'strict'
    return 'strict_missing_contract' if marked else 'legacy'


def _impact(row, *, contract, marked, global_errors, projection_available=True):
    route = _route(contract, marked, global_errors, projection_available)
    reasons = []
    if not isinstance(row, dict):
        reasons.append(dict(code='malformed_recording', detail='Recording is not an object'))
    elif route == 'unavailable_projection':
        reasons.append(dict(code='projection_unavailable', detail='Invalid or ambiguous inputs prevent an upsert projection'))
    elif route == 'blocked_global_selection':
        reasons.append(dict(code='invalid_global_selection', detail='The candidate rejects a malformed global runtime_selection block'))
    elif route == 'strict_missing_contract':
        reasons.append(dict(code='missing_performer_contract',
                            detail='At least one recording for this performer contains a version marker, even if null; legacy fallback is suppressed'))
    elif route == 'strict':
        for key in (*RUNTIME_CONTRACT_FIELDS, 'identity_key'):
            actual = row.get(key)
            if not _text(actual):
                reasons.append(dict(code='unknown_identity_field', field=key, actual=actual, expected=contract[key]))
            elif actual != contract[key]:
                reasons.append(dict(code='identity_field_mismatch', field=key, actual=actual, expected=contract[key]))
        for problem in recording_runtime_identity_errors(row):
            reasons.append(dict(code='invalid_recording_identity', detail=problem))
        # Keep compatibility tied to the shared exact validator, including its
        # independently calculated digest, rather than just a friendly diff.
        if recording_contract_errors(row, contract) and not reasons:
            reasons.append(dict(code='identity_contract_mismatch', detail='Recording does not match the explicit contract'))
    identity_eligible = not reasons
    metadata_reasons = _core_reasons(row)
    required_playable = route == 'strict'
    if required_playable and (not isinstance(row, dict) or row.get('playable') is not True):
        metadata_reasons.append('strict selection requires stored playable to be true')
    return dict(route=route, identity_eligible=identity_eligible, reasons=reasons,
                stored_playable_required=required_playable,
                metadata_eligible=identity_eligible and not metadata_reasons,
                metadata_reasons=metadata_reasons)


def review_contract_migration(mo2_root, profile, proposal_path, *, game_data=None,
                              vfs_report=None, session_receipt_index=None):
    """Inspect fresh files and project an explicit upsert entirely in memory.

    There is no apply operation. Unmentioned contracts and all manifest rows,
    history and unknown fields survive unchanged. Malformed existing selection
    cannot be repaired by silently replacing it; projection is then unavailable.
    """
    proposal_file = _no_alias(Path(os.path.abspath(proposal_path)))
    proposal_snapshot = _Snapshot()
    proposal_observation, raw = proposal_snapshot.read(proposal_file, content=True)
    if raw is None:
        raise ValueError('Proposal file is missing')
    proposal, proposal_errors = None, []
    try:
        proposal = _json(raw)
    except (ValueError, UnicodeError):
        proposal_errors.append('Proposal must be strict UTF-8 JSON without duplicate keys or nonfinite numbers')
    if not proposal_errors:
        proposal_errors.extend(runtime_selection_errors(proposal))
    inspection = inspect_installed_library(mo2_root, profile, game_data=game_data,
                                          vfs_report=vfs_report, session_receipt_index=session_receipt_index)
    inspection_blockers = deepcopy(inspection['blockers'])
    blockers = [dict(item, origin='inspection') for item in inspection_blockers]

    def block(code, detail, **extra):
        item = dict(code=code, detail=detail, **extra)
        if item not in blockers:
            blockers.append(item)

    for problem in proposal_errors:
        block('invalid_proposal', problem)
    manifest = inspection['manifest']
    _, current_contracts, global_errors = _selection(manifest)
    for problem in global_errors:
        block('invalid_existing_selection', problem)
    rows = manifest.get('recordings', []) if isinstance(manifest, dict) else []
    if not isinstance(rows, list):
        rows = []
    submitted = proposal['contracts'] if not proposal_errors else []
    submitted_contracts = {row['performer_id'].casefold(): row for row in submitted}

    # The runtime compares performer strings without case fidelity. Refuse any
    # upsert that would silently relabel an existing spelling or merge aliases.
    spellings = {}
    for row in [*rows, *current_contracts.values(), *submitted]:
        if isinstance(row, dict) and _text(row.get('performer_id')):
            spellings.setdefault(row['performer_id'].casefold(), set()).add(row['performer_id'])
    aliases = {key: sorted(values) for key, values in spellings.items() if len(values) > 1}
    for values in aliases.values():
        block('performer_case_alias', 'Performer identifiers differ only in case', identifiers=values)

    projection_possible = isinstance(manifest, dict) and not proposal_errors and not global_errors and not aliases
    projected = deepcopy(manifest) if projection_possible else None
    proposed_selection, after_contracts = None, {}
    projected_errors = []
    if projected is not None:
        proposed_selection = deepcopy(manifest.get('runtime_selection', {'version': 1, 'contracts': []}))
        replacements = set()
        for index, contract in enumerate(proposed_selection['contracts']):
            key = contract['performer_id'].casefold()
            if key in submitted_contracts:
                proposed_selection['contracts'][index] = deepcopy(submitted_contracts[key])
                replacements.add(key)
        proposed_selection['contracts'].extend(deepcopy(row) for row in submitted
                                               if row['performer_id'].casefold() not in replacements)
        projected['runtime_selection'] = proposed_selection
        _, after_contracts, after_global_errors = _selection(projected)
        projected_errors.extend(manifest_runtime_selection_errors(projected, required=True))
        if type(projected.get('version')) is not int or projected['version'] != 1 or type(projected.get('slots')) is not int or projected['slots'] != SLOTS:
            projected_errors.append('Projected manifest requires version 1 and 24 slots')
        projected_rows = projected.get('recordings')
        if not isinstance(projected_rows, list):
            projected_errors.append('Projected recordings must be a list')
        else:
            for index, row in enumerate(projected_rows):
                projected_errors.extend(f'recordings[{index}]: {error}' for error in _recording_errors(row, SLOTS))
        for problem in projected_errors:
            block('invalid_projected_manifest', problem)
    else:
        after_global_errors = global_errors

    marked = set()
    for row in rows:
        if _marked(row) and _text(row.get('performer_id')):
            marked.add(row['performer_id'].casefold())
    reservations = {item['slot']: deepcopy(item['reasons']) for item in inspection['reservations']}
    row_impacts = []
    for index, row in enumerate(rows):
        performer = row.get('performer_id') if isinstance(row, dict) else None
        key = performer.casefold() if _text(performer) else None
        summary = next((item for item in inspection['recordings'] if item['metadata'] == row), None)
        asset_valid = summary['asset_valid'] if summary is not None else None
        before = _impact(row, contract=current_contracts.get(key), marked=key in marked,
                         global_errors=global_errors)
        after = _impact(row, contract=after_contracts.get(key), marked=key in marked,
                        global_errors=after_global_errors, projection_available=projection_possible)
        slot = row.get('slot') if isinstance(row, dict) else None
        row_impacts.append(dict(index=index, slot=slot, performer_id=performer,
                                before=before, after=after, asset_valid=asset_valid,
                                stored_playable=row.get('playable') if isinstance(row, dict) else None,
                                reservation_reasons=reservations.get(slot, []) if type(slot) is int else [],
                                live_session_locks_verified=False))

    performers = []
    for key, names in sorted(spellings.items()):
        name = next((row['performer_id'] for row in rows if isinstance(row, dict)
                     and _text(row.get('performer_id')) and row['performer_id'].casefold() == key), sorted(names)[0])
        relevant = [item for item in row_impacts if _text(item['performer_id']) and item['performer_id'].casefold() == key]
        old, new = current_contracts.get(key), after_contracts.get(key)
        if key not in submitted_contracts:
            change = 'retained'
        elif old is None:
            change = 'add'
        else:
            change = 'unchanged' if old == submitted_contracts[key] else 'replace'
        counts = {stage: sum(item[stage]['identity_eligible'] for item in relevant) for stage in ('before', 'after')}
        available = {stage: sum(item[stage]['metadata_eligible'] and item['asset_valid'] is True
                                for item in relevant) for stage in ('before', 'after')}
        performers.append(dict(
            performer_id=name, change=change, before_contract=deepcopy(old), after_contract=deepcopy(new),
            before_route=_route(old, key in marked, global_errors),
            after_route=_route(new, key in marked, after_global_errors, projection_possible),
            row_indexes=[item['index'] for item in relevant], identity_eligible_counts=counts,
            available_asset_candidates=available,
        ))
        if projection_possible and key in submitted_contracts:
            if not counts['after']:
                block('no_identity_eligible_recordings', 'Proposed performer contract has no identity-compatible recordings',
                      performer_id=name)
            if not available['after']:
                block('no_available_asset_candidates',
                      'Proposed performer contract has no matching candidate with valid assets and required stored playable metadata',
                      performer_id=name)

    # Re-observe the inspector's own trusted path inventory at the end. No
    # user-supplied report paths are accepted and no stale report is imported.
    guard = _Snapshot()
    guard.files = {row['path']: deepcopy(row) for row in inspection['snapshot']['files']}
    guard.directories = {row['path']: deepcopy(row) for row in inspection['snapshot']['directories']}
    guard.finish()
    proposal_snapshot.finish()
    result = dict(
        version=1, status='blocked' if blockers else 'reviewed', scope='candidate_selection_identity_audit',
        operation='upsert_contracts_only', semantics_version=1, mo2_root=inspection['mo2_root'], profile=profile,
        inspection_token=inspection['review_token'],
        proposal=dict(proposal_observation, runtime_selection=deepcopy(proposal) if not proposal_errors else None),
        current_runtime_selection=deepcopy(manifest.get('runtime_selection')) if isinstance(manifest, dict) else None,
        proposed_runtime_selection=proposed_selection, projected_manifest=projected,
        projection_possible=projection_possible, performers=performers, rows=row_impacts,
        inspection_blockers=inspection_blockers, projected_manifest_errors=projected_errors, blockers=blockers,
        history=deepcopy(inspection['history']), receipts_source=deepcopy(inspection['files'][RECEIPTS_PATH]['winner']),
        inspection_warnings=deepcopy(inspection['warnings']),
        writes_performed=False, installed=False, vfs_verified=False, runtime_verified=False,
        warnings=[dict(code='metadata_only_review', detail='This review changes nothing and predicts no actual selected slot')],
        limitations=[
            'The audit describes the candidate HM_Library identity rules, not the installed or running selector.',
            'Explicit proposal contracts are upserts only; no recording metadata, history, unknown fields or unmentioned contracts are rewritten.',
            'Any version marker, including explicit null, suppresses legacy fallback for that performer without a contract.',
            'Identity eligibility is separate from valid assets, stored playable, receipt reservations and unknown live session locks.',
            'The candidate legacy path ignores stored playable; the strict path requires it to be true.',
            'Preferred mode ranks candidates and is not a legacy identity filter.',
            'Registry region, actor ownership, installed selector capability, process state, cooldowns and actual ChooseSlot results are not verified.',
            'Strict Python checks bind exact readable identity fields to their digest; Papyrus cannot independently rehash arbitrary JSON edits.',
            'No apply operation or removal/legacy-fallback migration is provided.',
        ])
    result['review_token'] = _digest(result)
    return result
