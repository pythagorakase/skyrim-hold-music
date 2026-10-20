"""Read-only additive review between two explicit, flat recording libraries.

There is deliberately no writer or apply token consumer here. A proposed manifest
is an in-memory review artifact, not an installation or a runtime contract change.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import wave

from hold_music.library import SLOTS, _receipt_errors, _recording_errors, wav_info
from hold_music.promotion import _Observation, _child, _files, _no_alias, _root
from hold_music.recording_identity import VERSION_FIELDS
from hold_music.runtime_contract import (
    manifest_runtime_selection_errors, recording_contract_errors,
    recording_runtime_identity_errors,
)


def _digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("nonfinite JSON number: " + value)

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            invalid(value)
        return number

    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=invalid, parse_float=finite)


def _projected(row):
    return any(key in row for key in (*VERSION_FIELDS, "identity_key"))


def _recording_key(row, assets):
    """A take includes its bytes, compatibility, composition and explicit scope.

    Multiple renditions may share every request field. The projected identity is
    a compatibility contract, never a unique recording/take identifier.
    """
    return (row["performer_id"], row["composition_id"], row["identity_key"],
            row.get("save_id"), row.get("world_id"),
            *(assets[kind].get("sha256") for kind in ("audio", "lyrics")))


def plan_library_merge(staged_library, destination_library, *, receipts_path=None,
                       session_receipt_index=None):
    """Plan additive imports without changing either input or launching anything.

    Both roots must contain library.json and use the flat library WAV/sidecar
    layout. An omitted session boundary reserves every observed receipt slot.
    Missing default receipts.json is observed as an empty offline history; an
    explicitly supplied missing receipt file is an error. Neither proves that a
    running game has no additional locks. A later installer needs its own review,
    ownership, quiescence and transaction controls.
    """
    staged, destination = map(_root, (staged_library, destination_library))
    if staged.is_relative_to(destination) or destination.is_relative_to(staged):
        raise ValueError("Staged and destination library roots must not overlap")
    if session_receipt_index is not None and (
            type(session_receipt_index) is not int or session_receipt_index < 0):
        raise ValueError("session_receipt_index must be a nonnegative integer")
    boundary = 0 if session_receipt_index is None else session_receipt_index
    receipts = (_no_alias(Path(os.path.abspath(receipts_path))) if receipts_path is not None
                else _child(destination, "receipts.json"))
    if receipts.is_relative_to(staged) or receipts == destination / "library.json":
        raise ValueError("Current receipts must not alias staged assets or the destination manifest")

    observed = _Observation()
    blockers, actions, duplicates = [], [], []

    def block(code, detail):
        item = {"code": code, "detail": detail}
        if item not in blockers:
            blockers.append(item)

    def inventory(root):
        result = []
        for path in _files(root):
            relative = path.relative_to(root).as_posix()
            _child(root, relative)  # Also reject Windows-ambiguous path components on Unix.
            if path.stat().st_nlink > 1:
                raise ValueError("Hard-linked library input is ambiguous: " + str(path))
            result.append(relative)
            observed.read(path)
        return result

    inventories = {str(root): inventory(root) for root in (staged, destination)}
    if receipts.exists() and receipts.stat().st_nlink > 1:
        raise ValueError("Hard-linked current receipts are ambiguous")

    def document(path, label, *, required):
        _, raw = observed.read(path, content=True)
        if raw is None:
            if required:
                block("missing_input", label + " is missing")
            return None
        try:
            return _json(raw)
        except (ValueError, UnicodeError) as exc:
            block("invalid_json", f"{label}: {exc}")
            return None

    def history(rows, label, *, generation=False):
        if not isinstance(rows, list):
            block("invalid_history", label + " must be a list")
            return []
        seen = set()
        for index, row in enumerate(rows):
            problems = _receipt_errors(row, SLOTS, generation)
            if not problems:
                key = (row["save_id"], row["world_id"], row["id"])
                if key in seen:
                    problems.append("duplicate scoped receipt id")
                seen.add(key)
            for problem in problems:
                block("invalid_history", f"{label}[{index}]: {problem}")
        return rows

    def receipt_document(path, label, *, required=False):
        value = document(path, label, required=required)
        if value is None:
            return []
        if (not isinstance(value, dict) or type(value.get("version")) is not int
                or value["version"] != 1):
            block("invalid_history", label + " requires an object with version 1")
            return []
        return history(value.get("performances"), label + " performances")

    def manifest(root, label, *, source):
        value = document(_child(root, "library.json"), label + " library.json", required=True)
        if not isinstance(value, dict):
            if value is not None:
                block("invalid_manifest", label + " library.json must be an object")
            return None, [], {}, {}
        if (type(value.get("version")) is not int or value["version"] != 1
                or type(value.get("slots")) is not int or value["slots"] != SLOTS):
            block("invalid_manifest", label + " requires version 1 and 24 slots")
        rows = value.get("recordings")
        if not isinstance(rows, list):
            block("invalid_manifest", label + " recordings must be a list")
            rows = []
        if source and not rows:
            block("empty_staged_library", "Staged library must contain a recording")
        # The flat helper's legacy format permits an all-unknown nullable trio.
        # Do not label that old destination invalid or fill in its identity. Once
        # a runtime_selection block exists its stricter presence rules still apply.
        strict = source or any(isinstance(row, dict) and (
            "identity_key" in row or any(row.get(key) is not None for key in VERSION_FIELDS))
            for row in rows)
        for problem in manifest_runtime_selection_errors(value, required=strict):
            block("invalid_runtime_selection", label + ": " + problem)
        history(value.get("generation_receipts", []), label + " generation_receipts",
                generation=True)
        selection = value.get("runtime_selection")
        contracts = {}
        if isinstance(selection, dict) and isinstance(selection.get("contracts"), list):
            for contract in selection["contracts"]:
                if isinstance(contract, dict) and isinstance(contract.get("performer_id"), str):
                    contracts[contract["performer_id"].casefold()] = contract
        valid, assets, slots = [], {}, set()
        for index, row in enumerate(rows):
            prefix = f"{label} recordings[{index}]"
            problems = _recording_errors(row, SLOTS)
            if isinstance(row, dict) and "session_locked" in row and type(row["session_locked"]) is not bool:
                problems.append("session_locked must be boolean")
            if problems:
                for problem in problems:
                    block("invalid_recording", prefix + ": " + problem)
                continue
            slot = row["slot"]
            if slot in slots:
                block("duplicate_slot", prefix + ": duplicate slot")
            slots.add(slot)
            if source:
                if not row["playable"]:
                    block("unplayable_staged_recording", prefix + ": playable must be true")
                if row.get("session_locked"):
                    block("locked_staged_recording", prefix + ": staged recording is locked")
                for problem in recording_runtime_identity_errors(row):
                    block("invalid_recording_identity", prefix + ": " + problem)
                contract = contracts.get(row["performer_id"].casefold())
                if contract is not None:
                    for problem in recording_contract_errors(row, contract):
                        block("staged_contract_mismatch", prefix + ": " + problem)
            audio = _child(root, row["file"])
            audio_observation = observed.read(audio)
            if not audio_observation["exists"]:
                block("missing_audio", prefix + ": WAV is missing")
            else:
                try:
                    info = wav_info(audio)
                    if not math.isclose(info["duration_seconds"], row["duration_seconds"],
                                        rel_tol=0, abs_tol=1 / 44100):
                        raise ValueError("WAV duration differs from metadata")
                except (OSError, ValueError, EOFError, wave.Error) as exc:
                    block("invalid_audio", prefix + ": " + str(exc))
                # The header validator reads separately; verify its bytes stayed fixed.
                observed.read(audio)
            lyrics = _child(root, f"hm_slot_{slot:02d}.lyrics.txt")
            lyrics_observation, raw = observed.read(lyrics, content=True)
            if raw is not None:
                try:
                    text = raw.decode("utf-8")
                    if (row["mode"] != "vocal" or not text.strip()
                            or lyrics_observation["sha256"] != row["lyrics_sha256"]):
                        raise ValueError("lyrics mode, content or digest differs from metadata")
                except (ValueError, UnicodeError) as exc:
                    block("invalid_lyrics", prefix + ": " + str(exc))
            elif row["lyrics_sha256"] is not None:
                block("missing_lyrics", prefix + ": lyrics sidecar is missing")
            assets[slot] = {"audio": audio_observation, "lyrics": lyrics_observation}
            valid.append(row)
        return value, valid, contracts, assets

    source_manifest, source_rows, source_contracts, source_assets = manifest(
        staged, "staged", source=True)
    target_manifest, target_rows, target_contracts, target_assets = manifest(
        destination, "destination", source=False)
    # Source history is validated but never copied. When the chosen current
    # history is external, preserve and validate any local history independently.
    receipt_document(_child(staged, "receipts.json"), "staged receipts.json")
    default_receipts = _child(destination, "receipts.json")
    if receipts != default_receipts:
        receipt_document(default_receipts, "destination receipts.json")
    performances = receipt_document(receipts, "current receipts", required=receipts_path is not None)
    if boundary > len(performances):
        block("invalid_session_boundary", "session_receipt_index exceeds raw receipt count")

    # Case-insensitive runtime IDs must not silently identify different content.
    compositions, performer_names, identities = {}, {}, {}
    identities_by_library = {"destination": set(), "staged": set()}
    for label, rows, assets in (("destination", target_rows, target_assets),
                                ("staged", source_rows, source_assets)):
        for row in sorted(rows, key=lambda row: row["slot"]):
            performer = row["performer_id"]
            previous = performer_names.setdefault(performer.casefold(), performer)
            if performer != previous:
                block("performer_alias", f"Performer IDs differ only in case: {previous}, {performer}")
            cid = row["composition_id"]
            others = compositions.setdefault(cid.casefold(), [])
            for other in others:
                if (cid != other["composition_id"] or row["region"] != other["region"]
                        or (row["lyrics_sha256"] is not None
                            and other["lyrics_sha256"] is not None
                            and row["lyrics_sha256"] != other["lyrics_sha256"])):
                    block("composition_conflict", f"Composition {cid} has conflicting immutable content")
            others.append(row)
            if not _projected(row) or recording_runtime_identity_errors(row):
                continue
            key = _recording_key(row, assets[row["slot"]])
            if label == "staged" and key in identities_by_library[label]:
                block("duplicate_recording", f"{label} contains duplicate recording identity for {cid}")
            identities_by_library[label].add(key)
            prior = identities.get(key)
            if prior is None:
                identities[key] = (label, row)
            elif prior[0] == label:
                continue
            else:
                duplicates.append({"source_slot": row["slot"], "destination_slot": prior[1]["slot"],
                                   "performer_id": performer, "composition_id": cid,
                                   "identity_key": row["identity_key"]})

    target_performers = {row["performer_id"].casefold() for row in target_rows}
    source_performers = {row["performer_id"].casefold() for row in source_rows}
    new_contracts = []
    for performer, contract in sorted(source_contracts.items()):
        current = target_contracts.get(performer)
        if performer not in source_performers:
            block("unused_staged_contract", "Staged contract has no recording: " + performer)
        elif current is not None and current != contract:
            block("runtime_contract_conflict", "Existing performer contract cannot change: " + performer)
        elif current is None and performer in target_performers:
            block("legacy_performer_contract_conflict",
                  "A new contract would suppress retained legacy playback: " + performer)
        elif current is None:
            new_contracts.append(contract)

    reserved = {}

    def reserve(slot, reason):
        reserved.setdefault(slot, set()).add(reason)

    for row in target_rows:
        reserve(row["slot"], "occupied_recording")
        if row.get("session_locked"):
            reserve(row["slot"], "manifest_session_lock")
    for index, row in enumerate(performances):
        if index >= boundary and isinstance(row, dict) and type(row.get("slot")) is int:
            if 1 <= row["slot"] <= SLOTS:
                reserve(row["slot"], "receipt_at_or_after_boundary")
    # Preserve explicit reservations when present; never interpret them as free.
    if isinstance(target_manifest, dict):
        for field in ("reserved_slots", "locked_slots"):
            if field in target_manifest:
                values = target_manifest[field]
                if (not isinstance(values, list)
                        or any(type(slot) is not int or not 1 <= slot <= SLOTS for slot in values)
                        or len(set(values)) != len(values)):
                    block("invalid_slot_reservations", field + " must contain unique slot numbers")
                else:
                    for slot in values:
                        reserve(slot, field)
    for slot in range(1, SLOTS + 1):
        for kind, suffix in (("audio", ".wav"), ("lyrics", ".lyrics.txt")):
            path = _child(destination, f"hm_slot_{slot:02d}{suffix}")
            state = observed.read(path)
            # Cross-platform case aliases must not look like an available slot.
            aliases = [name for name in inventories[str(destination)]
                       if name.casefold() == path.name.casefold()]
            if state["exists"] or aliases:
                reserve(slot, "existing_" + kind)
            if aliases and aliases != [path.name]:
                block("asset_path_alias", "Slot asset has noncanonical case: " + aliases[0])

    proposed = deepcopy(target_manifest) if isinstance(target_manifest, dict) else None
    duplicate_slots = {item["source_slot"] for item in duplicates}
    imports = [row for row in sorted(source_rows, key=lambda row: row["slot"])
               if row["slot"] not in duplicate_slots]
    free = [slot for slot in range(1, SLOTS + 1) if slot not in reserved]
    if len(imports) > len(free):
        block("insufficient_slots", f"Need {len(imports)} free slots; found {len(free)}")
    if not blockers:
        for row, slot in zip(imports, free):
            addition = deepcopy(row)
            addition.update(slot=slot, file=f"hm_slot_{slot:02d}.wav")
            proposed["recordings"].append(addition)
            assets = []
            for kind, suffix in (("audio", ".wav"), ("lyrics", ".lyrics.txt")):
                state = source_assets[row["slot"]][kind]
                if state["exists"]:
                    assets.append({"kind": kind, "source": state["path"],
                                   "destination": str(destination / f"hm_slot_{slot:02d}{suffix}"),
                                   "sha256": state["sha256"]})
            actions.append({"kind": "add_recording", "source_slot": row["slot"],
                            "destination_slot": slot, "performer_id": row["performer_id"],
                            "composition_id": row["composition_id"],
                            "identity_key": row["identity_key"], "assets": assets})
        for contract in new_contracts:
            selection = proposed.setdefault("runtime_selection", {"version": 1, "contracts": []})
            selection["contracts"].append(deepcopy(contract))
            actions.append({"kind": "add_runtime_contract", "performer_id": contract["performer_id"],
                            "identity_key": contract["identity_key"]})
        for problem in manifest_runtime_selection_errors(proposed, required=True):
            block("prospective_runtime_incompatibility", "Proposed manifest: " + problem)
        if blockers:
            actions = []
            proposed = None
    else:
        proposed = None

    # Observe complete inventories twice, including unrelated assets/history, so
    # additions or removals cannot hide behind an unchanged manifest.
    for root in (staged, destination):
        if inventory(root) != inventories[str(root)]:
            raise ValueError("Library inventory changed during planning: " + str(root))
    for name in list(observed.rows):
        observed.read(Path(name))
    snapshot = {"files": observed.finish(), "inventories": inventories,
                "staged_library": str(staged), "destination_library": str(destination),
                "receipts_path": str(receipts), "session_receipt_index": session_receipt_index,
                "effective_session_receipt_index": boundary}
    snapshot_sha = _digest(snapshot)
    preservation = {
        "destination_recordings": len(target_rows),
        "destination_performances": len(performances),
        "destination_generation_receipts": len(target_manifest.get("generation_receipts", []))
        if isinstance(target_manifest, dict)
        and isinstance(target_manifest.get("generation_receipts", []), list) else None,
        "source_history_imported": False,
        "destination_files": [str(destination / name) for name in inventories[str(destination)]],
        "current_receipts": str(receipts),
        "existing_rows_and_metadata": "preserved verbatim in the proposed manifest",
        "existing_contracts": "preserved; no legacy upgrade or contract replacement",
    }
    report = {"schema_version": 1, "operation": "plan_library_merge",
              "status": "blocked" if blockers else "review_only",
              "installed": False, "writes_performed": False, "runtime_verified": False,
              "can_apply": False, "blockers": blockers, "actions": actions,
              "duplicates": duplicates, "proposed_manifest": proposed,
              "reserved_slots": {str(slot): sorted(reasons) for slot, reasons in sorted(reserved.items())},
              "preservation": preservation, "snapshot": snapshot, "snapshot_sha256": snapshot_sha,
              "compatibility_limits": [
                  "Review only: no executable apply or runtime contract activation.",
                  "Flat library roots only; installed split audio/storage layouts require a separate transaction.",
                  "No game quiescence, ownership, VFS winner or runtime capability is established.",
                  "Absent default receipts describe offline history, not the absence of live game locks.",
                  "No source performance or generation history is imported; no palette metadata is inferred.",
                  "Nullable legacy identity is preserved; introducing contracts blocks if it makes that raw state incompatible.",
              ]}
    report["review_token"] = _digest(report)
    return report
