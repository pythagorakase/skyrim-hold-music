"""Read-only physical routing for a strictly additive flat-library proposal.

The explicit destination snapshot is evidence supplied by the caller. This
module never creates a flattened library, changes a mod, or supplies an apply
operation. Loose-file priority is a model, not an injected VFS attestation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from hold_music.installed_library import (
    AUDIO_PATH, MANIFEST_PATH, RECEIPTS_PATH, STORAGE_PATH, TRACE_PATH,
    _Snapshot, _digest, _profile_text, inspect_installed_library,
)
from hold_music.library import SLOTS
from hold_music.library_merge import plan_library_merge
from hold_music.promotion import _component, _no_alias, _root


def _content(row):
    if not row or not row.get("exists"):
        return {"exists": False}
    return {"exists": True, "sha256": row["sha256"], "size": row["size"]}


def _mapped_files():
    result = {MANIFEST_PATH: "library.json", RECEIPTS_PATH: "receipts.json",
              TRACE_PATH: "trace.json"}
    for slot in range(1, SLOTS + 1):
        stem = f"hm_slot_{slot:02d}"
        result[AUDIO_PATH + "/" + stem + ".wav"] = stem + ".wav"
        result[STORAGE_PATH + "/" + stem + ".lyrics.txt"] = stem + ".lyrics.txt"
    return result


def _profiles(mo2, base, observed, block):
    """Read every profile list, retaining disabled targets and foreign markers."""
    folder, _ = observed.resolve(mo2, "profiles")
    state, names = observed.directory(folder)
    if not state["exists"]:
        block("missing_profiles", "MO2 profiles directory is missing")
    result, seen_profiles = [], set()
    for name in names:
        path = _no_alias(folder / _component(name))
        if not path.is_dir():
            continue
        if name.casefold() in seen_profiles:
            block("profile_case_alias", "Profile directories differ only in case")
        seen_profiles.add(name.casefold())
        observed.directory(path)
        list_path, _ = observed.resolve(path, "modlist.txt")
        list_state, raw = observed.read(list_path, content=True)
        plugins, _ = observed.resolve(path, "plugins.txt")
        plugins_state = observed.read(plugins)
        active, disabled, unmanaged, seen, errors = [], [], [], set(), []
        if raw is None:
            errors.append("modlist.txt is missing")
        else:
            for number, line in enumerate(_profile_text(raw).splitlines(), 1):
                if not line.strip() or line.startswith("#"):
                    continue
                foreign = re.fullmatch(r"\*(DLC|Creation Club|Unmanaged): (.+)", line)
                if foreign:
                    kind, foreign_name = foreign.groups()
                    _component(foreign_name)
                    key = line[1:].casefold()
                    unmanaged.append({"kind": kind, "name": foreign_name})
                elif line[0] in "+-":
                    mod = _component(line[1:])
                    key = mod.casefold()
                    (active if line[0] == "+" else disabled).append(mod)
                else:
                    errors.append(f"modlist line {number} has no enabled/disabled prefix")
                    continue
                if key in seen:
                    errors.append("duplicate case-insensitive modlist entry")
                seen.add(key)
        layers = []
        overwrite, _ = observed.resolve(mo2, "overwrite")
        overwrite_state, _ = observed.directory(overwrite)
        layers.append(dict(priority=0, kind="overwrite", name="overwrite",
                           path=str(overwrite), exists=overwrite_state["exists"]))
        for mod in active:
            mod_path, _ = observed.resolve(mo2, "mods/" + mod)
            mod_state, _ = observed.directory(mod_path)
            if not mod_state["exists"]:
                errors.append("active mod directory missing: " + mod)
            layers.append(dict(priority=len(layers), kind="mod", name=mod,
                               path=str(mod_path), exists=mod_state["exists"]))
        if base is not None:
            layers.append(dict(priority=len(layers), kind="game_data", name="game_data",
                               path=str(base), exists=True))
        for error in errors:
            block("invalid_profile_scope", error, profile=name)
        result.append(dict(profile=name, path=str(path), modlist=list_state,
                           plugins=plugins_state, layers=layers, disabled=disabled,
                           unmanaged_entries=unmanaged, errors=errors))
    return result


def _candidates(layers, virtual, observed):
    rows = []
    for layer in layers:
        path, _ = observed.resolve(Path(layer["path"]), virtual)
        rows.append(dict(observed.read(path), priority=layer["priority"],
                         layer=layer["name"], layer_kind=layer["kind"]))
    return rows


def _simulate(layers, route, observed):
    candidates = _candidates(layers, route["virtual_path"], observed)
    winner = next((row for row in candidates if row["exists"]), None)
    target = next((layer for layer in layers if layer["kind"] == "mod"
                   and layer["name"].casefold() == route["target_mod"].casefold()), None)
    after = deepcopy(candidates)
    if target is not None:
        index = target["priority"]
        after[index] = dict(path=route["physical_target"], exists=True,
                            size=route["after_size"], sha256=route["after_sha256"],
                            priority=index, layer=target["name"], layer_kind="mod",
                            projected=True)
    simulated = next((row for row in after if row["exists"]), None)
    higher = bool(target is not None and winner is not None
                  and winner["priority"] < target["priority"])
    # A change of winner provenance is reported even when the bytes agree.
    effective = (_content(winner) != _content(simulated)
                 or (winner or {}).get("path") != (simulated or {}).get("path"))
    effect = ("disabled" if target is None else "shadowed" if higher
              else "unchanged" if not effective else "added" if winner is None else "replaced")
    return dict(virtual_path=route["virtual_path"], target_mod=route["target_mod"],
                target_enabled=target is not None, higher_override=higher,
                current_winner=winner, simulated_winner=simulated,
                effective_change=effective, effect=effect, candidates=candidates)


def plan_library_publication(staged_library, destination_snapshot, mo2_root, profile, *,
                             metadata_mod, audio_mod, game_data=None, vfs_report=None,
                             session_receipt_index=None):
    """Review explicit managed-mod routes, with no executable token consumer.

    Source and flat destination must be outside the installation and explicit
    base Data. The flat destination must exactly reproduce all mapped effective
    bytes, including absent history files and orphan slot assets. Existing merge
    restrictions prohibit implicit performer-contract changes.
    """
    staged, flat, mo2 = map(_root, (staged_library, destination_snapshot, mo2_root))
    base = _root(game_data) if game_data is not None else None
    _component(profile)
    _component(metadata_mod)
    _component(audio_mod)
    roots = [staged, flat, mo2] + ([base] if base is not None else [])
    for index, left in enumerate(roots):
        for right in roots[index + 1:]:
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError("Source, snapshot, MO2 and game Data roots must not overlap")

    inspection = inspect_installed_library(
        mo2, profile, game_data=base, vfs_report=vfs_report,
        session_receipt_index=session_receipt_index)
    merge = plan_library_merge(staged, flat, session_receipt_index=session_receipt_index)
    blockers = []

    def block(code, detail, **extra):
        item = dict(code=code, detail=detail, **extra)
        if item not in blockers:
            blockers.append(item)

    for origin, report in (("inspection", inspection), ("merge", merge)):
        for item in report["blockers"]:
            block(item["code"], item["detail"], origin=origin)
    observed = _Snapshot()
    mapped = _mapped_files()
    equivalence = []
    for virtual, name in mapped.items():
        actual, _ = observed.resolve(flat, name)
        snapshot_state = observed.read(actual)
        installed = inspection["files"][virtual]["winner"]
        matches = _content(snapshot_state) == _content(installed)
        equivalence.append(dict(virtual_path=virtual, flat_file=snapshot_state,
                                installed_winner=deepcopy(installed), matches=matches))
        if not matches:
            block("snapshot_mismatch", "Flat snapshot differs from the current loose winner",
                  virtual_path=virtual)
    expected = set(mapped.values())
    inventory = merge["snapshot"]["inventories"][str(flat)]
    extras = [name for name in inventory if name not in expected]
    if extras:
        block("snapshot_extra_files", "Flat destination has files without a mapped installed equivalent",
              files=extras)
    equivalent = all(item["matches"] for item in equivalence) and not extras

    profiles = _profiles(mo2, base, observed, block)
    selected = [item for item in profiles if item["profile"].casefold() == profile.casefold()]
    if len(selected) != 1:
        block("selected_profile_scope", "Selected profile does not resolve uniquely")
    selected = selected[0] if len(selected) == 1 else None
    targets = {}
    for role, requested in (("metadata", metadata_mod), ("audio", audio_mod)):
        matches = [layer for layer in inspection["layers"] if layer["kind"] == "mod"
                   and layer["name"].casefold() == requested.casefold() and layer["exists"]]
        if len(matches) != 1:
            block("invalid_target_mod", "Explicit target must be an existing active managed mod",
                  role=role, mod=requested)
        else:
            targets[role] = matches[0]

    routes = []
    additions = [action for action in merge["actions"] if action["kind"] == "add_recording"]
    proposed = deepcopy(merge["proposed_manifest"]) if equivalent else None

    def route(virtual, role, source, sha, size):
        target = targets["audio" if role == "audio" else "metadata"]
        path, _ = observed.resolve(Path(target["path"]), virtual)
        before = observed.read(path)
        item = dict(virtual_path=virtual, role=role, target_mod=target["name"],
                    physical_target=str(path), before=before, source=source,
                    after_sha256=sha, after_size=size,
                    action="replace" if before["exists"] else "add")
        effect = _simulate(inspection["layers"], item, observed)
        item.update(current_winner=effect["current_winner"],
                    simulated_winner=effect["simulated_winner"],
                    higher_override=effect["higher_override"])
        if effect["higher_override"]:
            block("higher_priority_override", "Explicit target would remain hidden by a higher loose winner",
                  virtual_path=virtual, target_mod=target["name"])
        routes.append(item)

    if proposed is not None and additions and len(targets) == 2:
        for action in additions:
            for asset in action["assets"]:
                source_state = observed.read(Path(asset["source"]))
                if source_state.get("sha256") != asset["sha256"]:
                    raise ValueError("Staged source changed during route planning")
                virtual = (AUDIO_PATH if asset["kind"] == "audio" else STORAGE_PATH)
                virtual += "/" + Path(asset["destination"]).name
                route(virtual, asset["kind"], dict(kind="staged_file", **source_state),
                      asset["sha256"], source_state["size"])
        encoded = (json.dumps(proposed, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        sha = hashlib.sha256(encoded).hexdigest()
        route(MANIFEST_PATH, "manifest",
              dict(kind="merged_manifest", merge_token=merge["review_token"], sha256=sha, size=len(encoded)),
              sha, len(encoded))

    shared = []
    for other in profiles:
        effects = [_simulate(other["layers"], item, observed) for item in routes]
        is_selected = selected is not None and other["profile"] == selected["profile"]
        changed = [item for item in effects if item["effective_change"]]
        complete = is_selected or not changed
        if not complete:
            block("affected_profile_validation_incomplete",
                  "Effective changes require validation of this other profile's complete projected library",
                  profile=other["profile"], virtual_paths=[item["virtual_path"] for item in changed])
        shared.append(dict(profile=other["profile"], selected=is_selected,
                           modlist=other["modlist"], plugins=other["plugins"],
                           unmanaged_entries=other["unmanaged_entries"], effects=effects,
                           projected_library_validated=bool(is_selected and not blockers),
                           affected_scope_complete=complete and not other["errors"]))

    # Relevant capability and ownership inputs are observed as hashes only.
    # Presence is never interpreted as proof of compatibility, control or writes.
    evidence_paths = (
        "Scripts/HM_Library.pex", "Scripts/HM_Controller.pex", "Scripts/HM_Config.pex",
        "Scripts/Source/HM_Library.psc",
        "SKSE/Plugins/HoldMusic/registry.json",
        "SKSE/Plugins/SkyrimNet/config/BardSinging.yaml",
        "mcm/config/HoldMusic/settings.ini", "mcm/settings/HoldMusic.ini",
    )
    evidence = {}
    for virtual in evidence_paths:
        candidates = _candidates(inspection["layers"], virtual, observed)
        evidence[virtual] = dict(candidates=candidates,
                                winner=next((row for row in candidates if row["exists"]), None))
    adapter, _ = observed.resolve(mo2, "plugins/hold_music_adapter/local.json")
    adapter_state = observed.read(adapter)
    if selected is not None:
        profile_state = {}
        for relative in ("hold-music-runtime/BardSinging.yaml",
                         "hold-music-runtime/BardSinging.baseline.yaml"):
            path, _ = observed.resolve(Path(selected["path"]), relative)
            profile_state[relative] = observed.read(path)
    else:
        profile_state = {}

    guard = _Snapshot()
    guard.files = {row["path"]: deepcopy(row) for row in inspection["snapshot"]["files"]}
    guard.directories = {row["path"]: deepcopy(row) for row in inspection["snapshot"]["directories"]}
    guard.finish()
    routing_snapshot = observed.finish()
    if plan_library_merge(staged, flat, session_receipt_index=session_receipt_index)["review_token"] != merge["review_token"]:
        raise ValueError("Flat inputs changed during publication planning")
    # Recheck installed/profile observations after the final flat-library read.
    guard.finish()
    observed.finish()

    result = dict(
        schema_version=1, operation="plan_library_publication",
        status="blocked" if blockers else "review_only", mo2_root=str(mo2), profile=profile,
        staged_library=str(staged), destination_snapshot=str(flat),
        metadata_mod=metadata_mod, audio_mod=audio_mod,
        game_data=str(base) if base is not None else None,
        inspection_token=inspection["review_token"], merge_token=merge["review_token"],
        snapshot_equivalence=dict(matches=equivalent, files=equivalence, extra_files=extras),
        routes=routes, shared_profiles=shared, proposed_manifest=proposed,
        no_changes=not merge["actions"] and not blockers, blockers=blockers,
        inspection_blockers=deepcopy(inspection["blockers"]), merge_blockers=deepcopy(merge["blockers"]),
        preservation=dict(
            merge=deepcopy(merge["preservation"]), reservations=deepcopy(inspection["reservations"]),
            reserved_slots=deepcopy(merge["reserved_slots"]), history=deepcopy(inspection["history"]),
            receipts_source=deepcopy(inspection["files"][RECEIPTS_PATH]["winner"]),
            trace_source=deepcopy(inspection["files"][TRACE_PATH]["winner"]),
            orphans=deepcopy(inspection["orphans"]),
            existing_files_modified=False, source_history_imported=False),
        snapshot=routing_snapshot,
        prerequisite_evidence=dict(loose_inputs=evidence, adapter_state=adapter_state,
                                   selected_profile_state=profile_state),
        prerequisites=dict(runtime_capability_verified=False, performer_ownership_verified=False,
                           process_quiescence_verified=False, write_destinations_verified=False,
                           live_session_locks_verified=False),
        can_apply=False, installed=False, vfs_verified=False, runtime_verified=False,
        writes_performed=False, candidate_available=False,
        limitations=[
            "Read-only proposal: no writer, apply token consumer, flattening, process scan or installation is provided.",
            "Loose priority simulation does not verify archive winners, actual VFS injection, current save, live locks or future write paths.",
            "The explicit destination snapshot must match raw mapped bytes and absences, including history and orphan slot assets.",
            "Only existing active managed mods may be targets; overwrite and base game Data are never destinations.",
            "Existing performer contracts are retained under the additive merge rules; migration review does not authorize replacement here.",
            "Other profiles with effective changes require a separate complete projected-library validation; disabled or hidden routes are reported without an approval claim.",
            "Registry, ownership and capability inputs are bound as hashes only and remain unverified prerequisites.",
            "A matching VFS capture is historical read evidence only; no destination is inferred to be writable.",
        ] + (["Base game Data was omitted; base and unmanaged loose winners were not inspected."] if base is None else []),
    )
    result["review_token"] = _digest(result)
    return result
