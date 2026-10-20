"""Pure validation of explicit runtime selection contracts.

The planner request is authoritative. A recording and the current palette must
never supply missing request metadata. Legacy recordings remain readable, but
unknown identity fields cannot satisfy one of these contracts.
"""
from __future__ import annotations

import hashlib
import json

from hold_music.recording_identity import CONTRACT_FIELDS, VERSION_FIELDS

RUNTIME_CONTRACT_FIELDS = ("performer_id", "region", *CONTRACT_FIELDS)
RUNTIME_SELECTION_VERSION = 1
_REQUEST_FIELDS = {"tradition", *CONTRACT_FIELDS}


def runtime_identity_key(value):
    """Hash the exact ten readable fields; never normalize case or fill defaults.

    JsonUtil/Papyrus strings cannot reliably distinguish case. The separately
    validated digest projects that distinction into the runtime comparison.
    """
    if not isinstance(value, dict):
        raise ValueError("Runtime identity must be an object")
    fields = []
    for key in RUNTIME_CONTRACT_FIELDS:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Runtime identity requires nonempty {key}")
        fields.append(item)
    raw = json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def runtime_contract_errors(contract):
    """Validate one canonical stored contract, without changing its contents."""
    if not isinstance(contract, dict):
        return ["runtime contract must be an object"]
    errors = []
    if set(contract) != {*RUNTIME_CONTRACT_FIELDS, "identity_key"}:
        errors.append("runtime contract must contain exactly the supported identity fields")
    for key in RUNTIME_CONTRACT_FIELDS:
        value = contract.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"runtime contract requires nonempty {key}")
    if contract.get("instrument_family") != "plucked_string":
        errors.append("runtime contract requires the plucked_string animation family")
    mode, arrangement, voice = (contract.get(key) for key in ("mode", "arrangement", "voice"))
    if mode == "instrumental":
        if arrangement != "solo_lute" or voice != "none":
            errors.append("instrumental runtime contracts require solo_lute and voice none")
    elif mode in ("vocal", "wordless"):
        if arrangement != "solo_lute_and_voice" or voice not in ("male", "female"):
            errors.append("sung runtime contracts require solo_lute_and_voice and one male or female voice")
    else:
        errors.append("runtime contract mode must be instrumental, vocal or wordless")
    try:
        expected_key = runtime_identity_key(contract)
    except ValueError:
        expected_key = None
    if expected_key is None or contract.get("identity_key") != expected_key:
        errors.append("runtime contract identity_key must match the exact readable fields")
    return errors


def runtime_selection_errors(selection):
    """Validate the complete versioned block, including unselected entries.

    A performer can have only one active identity. Case-insensitive duplicate
    actor IDs are ambiguous to the runtime, even across different regions/modes.
    """
    if not isinstance(selection, dict):
        return ["runtime_selection must be an object"]
    errors = []
    if set(selection) != {"version", "contracts"}:
        errors.append("runtime_selection must contain exactly version and contracts")
    if type(selection.get("version")) is not int or selection["version"] != RUNTIME_SELECTION_VERSION:
        errors.append("runtime_selection version must be 1")
    contracts = selection.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        errors.append("runtime_selection contracts must be a nonempty list")
        return errors
    seen = set()
    for index, contract in enumerate(contracts):
        problems = runtime_contract_errors(contract)
        errors.extend(f"runtime_selection contracts[{index}]: {problem}" for problem in problems)
        if not problems:
            key = contract["performer_id"].casefold()
            if key in seen:
                errors.append(f"runtime_selection contracts[{index}]: duplicate performer_id")
            seen.add(key)
    return errors


def manifest_runtime_selection_errors(manifest, *, required=False):
    """Validate the optional manifest extension; absence never invents defaults.

    Use required=True at publication/promotion boundaries that promise runtime
    selection. Every projected/versioned row then needs a coherent independent
    digest and a configured performer. Older revisions may coexist; matching
    each recording to its current contract remains a separate check. Fully
    legacy rows are not upgraded and cannot satisfy a strict runtime contract.
    """
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    if "runtime_selection" not in manifest:
        return ["manifest requires runtime_selection"] if required else []
    selection = manifest["runtime_selection"]
    errors = runtime_selection_errors(selection)
    performers = set()
    if isinstance(selection, dict) and isinstance(selection.get("contracts"), list):
        performers = {contract["performer_id"].casefold() for contract in selection["contracts"]
                      if not runtime_contract_errors(contract)}
    rows = manifest.get("recordings")
    if not isinstance(rows, list):
        return errors + ["runtime manifest recordings must be a list"]
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"runtime manifest recordings[{index}] must be an object")
            continue
        projected = any(key in row for key in (*VERSION_FIELDS, "identity_key"))
        if projected:
            problems = recording_runtime_identity_errors(row)
            errors.extend(f"runtime manifest recordings[{index}]: {problem}" for problem in problems)
            performer = row.get("performer_id")
            if not isinstance(performer, str) or performer.casefold() not in performers:
                errors.append(f"runtime manifest recordings[{index}] requires a performer contract")
    return errors


def project_runtime_contract(decision):
    """Project a decision's performer and exact request, never a recording row."""
    if not isinstance(decision, dict) or not isinstance(decision.get("request"), dict):
        raise ValueError("Runtime projection requires a decision with an explicit request")
    request = decision["request"]
    if set(request) != _REQUEST_FIELDS:
        raise ValueError("Decision request must contain exactly the supported identity fields")
    contract = dict(performer_id=decision.get("performer_id"), region=request["tradition"],
                    **{key: request[key] for key in CONTRACT_FIELDS})
    if contract["mode"] == "lyrical":
        contract["mode"] = "vocal"
    contract["identity_key"] = runtime_identity_key(contract)
    errors = runtime_contract_errors(contract)
    if errors:
        raise ValueError("; ".join(errors))
    return contract


def recording_contract_errors(recording, contract, *, require_identity_key=True):
    """Require all configured identity fields to match a stored recording exactly."""
    errors = runtime_contract_errors(contract)
    if errors:
        return errors
    if not isinstance(recording, dict):
        return ["recording must be an object"]
    errors = [f"recording contract differs: {key}" for key in RUNTIME_CONTRACT_FIELDS
              if recording.get(key) != contract[key]]
    try:
        key = runtime_identity_key(recording)
    except ValueError:
        key = None
    if key != contract["identity_key"]:
        errors.append("recording projected identity differs from the runtime contract")
    if require_identity_key and (key is None or recording.get("identity_key") != key):
        errors.append("recording identity_key must match the exact readable fields")
    return errors


def recording_runtime_identity_errors(recording):
    """Validate a projected row's own fields/digest, independently of a request."""
    if not isinstance(recording, dict):
        return ["recording must be an object"]
    identity = {key: recording.get(key) for key in (*RUNTIME_CONTRACT_FIELDS, "identity_key")}
    return runtime_contract_errors(identity)
