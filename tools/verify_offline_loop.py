#!/usr/bin/env python3
"""Exercise preparation, library staging and receipt feedback without a provider or game."""
from __future__ import annotations

import argparse
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hold_music.knowledge_bridge import snapshot as knowledge_snapshot
from hold_music.library import Library, _atomic_json, _receipt_errors, wav_info
from hold_music.registry import load_registry
from hold_music.repertoire import Snapshot, plan

CONTRACT_FIELDS = ("recipe_id", "recipe_revision", "model_id", "instrument_family",
                   "instrument_name", "arrangement", "mode", "voice")
SCOPE = {"save_id": "offline-loop-fixture", "world_id": "offline-loop-fixture"}
NOW = 100.0


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(path, value)


def contract_for(performer):
    """A versioned test identity; never an admitted regional recipe or real model."""
    return dict(recipe_id=f"fixture/{performer['region']}/cittern-v1",
                recipe_revision="offline-fixture-v1", model_id="synthetic-pcm-fixture",
                instrument_family="plucked_string", instrument_name="cittern",
                arrangement="solo_lute_and_voice", mode="lyrical", voice=performer["gender"])


def request_for(performer, contract):
    return dict(tradition=performer["region"], **{key: contract[key] for key in
                ("recipe_id", "model_id", "arrangement", "mode", "voice")})


def compatible_recording(row, contract):
    """Strict staging boundary: missing legacy metadata is unknown, not a match."""
    errors = []
    for field in CONTRACT_FIELDS:
        actual = row.get(field)
        if field == "mode" and actual == "vocal":
            actual = "lyrical"
        if not isinstance(contract.get(field), str) or not contract[field].strip():
            errors.append(f"required contract field is missing: {field}")
        elif actual != contract[field]:
            errors.append(f"recording contract differs: {field}")
    if contract.get("instrument_family") != "plucked_string":
        errors.append("this staging pilot only supports the plucked_string animation family")
    if contract.get("arrangement") not in {"solo_lute", "solo_lute_and_voice"}:
        errors.append("this staging pilot only supports one visible plucked-string performer")
    if not isinstance(row.get("provenance"), dict) or not row["provenance"].get("kind"):
        errors.append("recording provenance is missing")
    return errors


def stage_selection(library, decision, contract, destination):
    """Stage only one compatible existing recording into a NEW scratch directory.

    The Data payload is library assets only, not an installable full game package.
    No runtime receipt file is included in that payload.
    """
    problems = library.validate()
    if problems:
        raise ValueError("Cannot stage invalid library: " + "; ".join(problems))
    if decision.get("action") != "play_recording":
        raise ValueError("Staging requires a play_recording decision")
    row = next((r for r in library.recordings
                if decision.get("recording_id") == f"slot:{r['slot']:02d}"), None)
    if row is None or not row["playable"]:
        raise ValueError("Selected recording is absent or unplayable")
    if (row["performer_id"] != decision.get("performer_id") or
            row["composition_id"] != decision.get("composition_id")):
        raise ValueError("Selected recording identity differs from the decision")
    if "save_id" in row and (row["save_id"], row["world_id"]) != (
            decision.get("save_id"), decision.get("world_id")):
        raise ValueError("Selected recording belongs to another save/world")
    expected_request = dict(tradition=row["region"], **{key: contract.get(key) for key in
                            ("recipe_id", "model_id", "arrangement", "mode", "voice")})
    if decision.get("request") != expected_request:
        raise ValueError("Decision request differs from the publication contract")
    errors = compatible_recording(row, contract)
    if errors:
        raise ValueError("; ".join(errors))

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    source_files = [library.root / "library.json", library.root / row["file"]]
    sidecar = library.root / f"hm_slot_{row['slot']:02d}.lyrics.txt"
    lyrics = sidecar.read_text(encoding="utf-8") if row["mode"] == "vocal" else None
    if sidecar.exists():
        source_files.append(sidecar)
    before = {str(path.resolve()): sha(path) for path in source_files}
    staging_library = Library(destination / "library")
    kwargs = {key: deepcopy(value) for key, value in row.items() if key not in
              {"file", "duration_seconds", "lyrics_sha256", "playable", "session_locked"}}
    staged_row = staging_library.add_recording(library.root / row["file"], lyrics=lyrics, **kwargs)
    problems = staging_library.validate()
    if problems:
        raise ValueError("Staged library validation failed: " + "; ".join(problems))
    data = destination / "Data"
    mapping = {"library.json": "SKSE/Plugins/StorageUtilData/HoldMusic/library.json",
               row["file"]: "Sound/fx/holdmusic/" + row["file"]}
    if lyrics is not None:
        mapping[sidecar.name] = "SKSE/Plugins/StorageUtilData/HoldMusic/" + sidecar.name
    files = []
    for name, relative in mapping.items():
        source, target = staging_library.root / name, data / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append(dict(path=relative, sha256=sha(target), bytes=target.stat().st_size))
    after = {str(path.resolve()): sha(path) for path in source_files}
    if before != after:
        raise ValueError("Source files changed during staging; do not deploy this payload")
    if sha(staging_library.root / row["file"]) != before[str((library.root / row["file"]).resolve())]:
        raise ValueError("Staged audio hash differs from the source")
    receipt = dict(version=1, status="staged_only", installed=False,
                   package_scope="library_assets_only", runtime_receipts_in_payload=False,
                   performer_id=decision["performer_id"], save_id=decision["save_id"],
                   world_id=decision["world_id"], recording_id=decision["recording_id"],
                   composition_id=decision["composition_id"], request=decision["request"],
                   contract=deepcopy(contract), source=deepcopy(row["source"]),
                   provenance=deepcopy(row["provenance"]),
                   source_files_sha256=before, files=files,
                   wav=wav_info(staging_library.root / staged_row["file"]))
    write_json(destination / "staging-receipt.json", receipt)
    return receipt


def reconcile_receipt(library, receipt, decision):
    """Append a validated receipt to a scratch library, idempotently.

    Both completed and interrupted starts count toward repeat cooldowns, matching
    the existing planner. This helper is not a concurrent game receipt writer.
    """
    if library.validate():
        raise ValueError("Cannot reconcile an invalid scratch library")
    errors = _receipt_errors(receipt, library.slots)
    if errors:
        raise ValueError("Invalid receipt: " + "; ".join(errors))
    if receipt.get("outcome") not in {"completed", "interrupted"}:
        raise ValueError("Receipt must describe a completed or interrupted performance")
    for key in ("performer_id", "composition_id", "save_id", "world_id"):
        if receipt.get(key) != decision.get(key):
            raise ValueError(f"Receipt differs from selection: {key}")
    if type(receipt.get("slot")) is not int or decision.get("recording_id") != f"slot:{receipt['slot']:02d}":
        raise ValueError("Receipt slot differs from selection")
    selected = next((r for r in library.recordings if r["slot"] == receipt["slot"]), None)
    if selected is None or any(selected[key] != receipt[key] for key in ("performer_id", "composition_id")):
        raise ValueError("Receipt does not identify the current scratch recording")
    probe = dict(save_id=decision["save_id"], world_id=decision["world_id"],
                 performer_id=decision["performer_id"], now_hours=receipt.get("at_hours"),
                 request=decision["request"], recent_performances=[dict(
                     id=receipt.get("id"), performer_id=receipt["performer_id"],
                     composition_id=receipt["composition_id"], save_id=receipt["save_id"],
                     world_id=receipt["world_id"], at=receipt.get("at_hours"))])
    Snapshot.from_dict(probe)
    existing = next((r for r in library.performances if
                     (r["save_id"], r["world_id"], r["id"]) ==
                     (receipt["save_id"], receipt["world_id"], receipt["id"])), None)
    if existing is not None:
        if existing != receipt:
            raise ValueError("Conflicting replay of an existing receipt id")
        return "already_reconciled"
    write_json(library.receipts_source,
               dict(version=1, performances=[*library.performances, deepcopy(receipt)]))
    if library.validate():
        raise ValueError("Reconciled scratch library failed validation")
    return "reconciled"


def fixture_database(path, performer):
    """Construct only the read-only bridge's used schema, with labeled fake facts."""
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
            CREATE TABLE uuid_mappings(uuid INTEGER, mod_file TEXT, local_form_id INTEGER, actor_name TEXT);
            CREATE TABLE memories(id INTEGER, actor_uuid INTEGER, content TEXT, location TEXT,
                game_time REAL, related_event_ids TEXT, importance_score REAL, tags TEXT, memory_type TEXT);
            CREATE TABLE events(id INTEGER, originating_actor_UUID INTEGER, target_actor_UUID INTEGER,
                event_type TEXT, event_data TEXT, location TEXT, game_time REAL);
        """)
        db.execute("INSERT INTO uuid_mappings VALUES(101, ?, ?, ?)",
                   (performer["form"]["plugin"], int(performer["form"]["id"], 16), performer["name"]))
        db.execute("INSERT INTO memories VALUES(1,101,?,?,?,?,?,?,?)",
                   ("SYNTHETIC: a potter's missing cup was returned.", performer["venue"],
                    99 * 3600, "[21]", 1.0, '["witnessed","quest_completed"]', "EXPERIENCE"))
        db.execute("INSERT INTO memories VALUES(2,999,?,?,?,?,?,?,?)",
                   ("OTHER_ACTOR_ONLY_SYNTHETIC", performer["venue"], 99 * 3600,
                    "[22]", 1.0, '["witnessed"]', "EXPERIENCE"))


def run(output, performer_id="sven", registry_path=None):
    """Create a reproducible proof bundle. Refuse an existing output directory."""
    registry = load_registry(registry_path) if registry_path else load_registry()
    performer = next((row for row in registry.performers if row["id"] == performer_id), None)
    if (not performer or performer["owner"] != "hold_music" or
            performer["instrument"] != "lute" or not performer["form"] or not performer["region"]):
        raise ValueError("Fixture requires a registered Hold Music plucked-string pilot performer")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    contract = contract_for(performer)
    request = request_for(performer, contract)
    write_json(output / "inputs.json", dict(synthetic=True, performer=performer,
               contract=contract, scope=SCOPE, now_hours=NOW,
               registry_sha256=sha(registry_path or ROOT / "game_adapter/data/performers.json")))
    wav = output / "synthetic-silence.wav"
    with wave.open(str(wav), "wb") as stream:
        stream.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 44100)
    db_path = output / "SkyrimNet-offline-loop-fixture.db"
    fixture_database(db_path, performer)
    db_hash = sha(db_path)
    library = Library(output / "source-library")
    library.add_recording(wav, performer_id=performer["id"], region=performer["region"],
        mode="vocal", gender=performer["gender"], composition_id="fixture:market-day",
        recipe_id=contract["recipe_id"], model_id=contract["model_id"],
        source=dict(kind="import", path_or_request_id="synthetic-silence.wav", sha256=sha(wav)),
        lyrics="Synthetic fixture words; this file contains silence, not a singing performance.",
        created_at="2026-10-20T00:00:00Z", created_at_hours=0, **SCOPE,
        title="Synthetic market day", topic_id="fixture:market-day",
        source_observation_ids=[], recipe_revision=contract["recipe_revision"],
        instrument_family=contract["instrument_family"], instrument_name=contract["instrument_name"],
        arrangement=contract["arrangement"], voice=contract["voice"],
        provenance=dict(kind="synthetic_test_fixture", audio="one second of silence"))
    source_hashes = {p.name: sha(p) for p in library.root.iterdir() if p.is_file()}
    data, bridge = knowledge_snapshot(performer, db_path, library, NOW, request)
    if not bridge["uuid_resolved"]:
        raise ValueError("Unresolved performer identity; no successful empty retrieval")
    write_json(output / "knowledge-snapshot.json", data)
    cached = plan(dict(data, policy={"selection": "cache_first"}))
    topical = plan(data)
    pending = dict(**SCOPE, id="fixture:pending-job", performer_id=performer["id"],
                   action="compose_lyrics", request=request, created_at=NOW,
                   topic_id=topical["subject"]["topic_id"], work_key=topical["work_key"])
    deduplicated = plan(dict(data, pending_jobs=[pending]))
    generation_cooldown = plan(dict(data, generation_history=[dict(
        **SCOPE, id="fixture:prior-lyric-attempt", performer_id=performer["id"],
        action="compose_lyrics", at=NOW - .5)]))
    stage = stage_selection(library, cached, contract, output / "staged")
    mismatch = {}
    for field in CONTRACT_FIELDS:
        changed = deepcopy(contract)
        changed[field] += "-changed"
        mismatch[field] = compatible_recording(library.recordings[0], changed)
    histories = {}
    for outcome in ("completed", "interrupted"):
        branch = output / ("receipt-" + outcome)
        shutil.copytree(output / "staged/library", branch)
        branch_library = Library(branch)
        receipt = dict(**SCOPE, id=f"fixture:performance:{outcome}",
                       performer_id=performer["id"], composition_id=cached["composition_id"],
                       slot=1, at_hours=NOW, outcome=outcome)
        first = reconcile_receipt(branch_library, receipt, cached)
        second = reconcile_receipt(branch_library, receipt, cached)
        decisions = {}
        for label, at in (("immediate", NOW + .1), ("after_song_window", NOW + 4),
                          ("after_topic_window", NOW + 24)):
            after, _ = knowledge_snapshot(performer, db_path, branch_library, at, request)
            # Isolate replay policy from the separate new topical story.
            after.update(observations=[], policy={"selection": "cache_first"})
            decisions[label] = plan(after)
        histories[outcome] = dict(receipt=receipt, first_reconciliation=first,
                                  repeated_reconciliation=second, decisions=decisions)
    other_performer = deepcopy(performer)
    other_performer["form"]["id"] = "0x00FFFFFF"
    _, unresolved = knowledge_snapshot(other_performer, db_path, library, NOW, request)
    foreign_save = deepcopy(data)
    foreign_save.update(save_id="different-save", world_id="different-save")
    foreign_save["observations"] = []
    foreign_decision = plan(foreign_save)
    checks = dict(
        identity_resolved=bridge["uuid_resolved"],
        actor_private_rows_excluded=all("OTHER_ACTOR_ONLY" not in r["summary"] for r in data["observations"]),
        cached_selection=cached["action"] == "play_recording",
        topical_proposal=topical["action"] == "compose_lyrics",
        duplicate_work_suppressed=deduplicated["action"] == "wait",
        generation_cooldown_keeps_cached_fallback=(
            generation_cooldown["action"] == "play_recording" and
            any("generation cooldown" in reason for reason in generation_cooldown["reasons"])),
        contract_mismatches_rejected=all(mismatch.values()),
        unresolved_identity_reported=not unresolved["uuid_resolved"] and "actor_uuid" in unresolved["unresolved_fields"],
        foreign_save_excluded=foreign_decision["action"] == "no_selection",
        receipt_replay_idempotent=all(h["repeated_reconciliation"] == "already_reconciled" for h in histories.values()),
        completed_and_interrupted_cooldowns=all(
            h["decisions"]["immediate"]["action"] == "no_selection" and
            h["decisions"]["after_song_window"]["action"] == "no_selection" and
            h["decisions"]["after_topic_window"]["action"] == "play_recording"
            for h in histories.values()),
        source_library_unchanged=source_hashes == {p.name: sha(p) for p in library.root.iterdir() if p.is_file()},
        knowledge_database_unchanged=db_hash == sha(db_path))
    report = dict(version=1, status="passed" if all(checks.values()) else "failed",
        synthetic=True, provider_calls=0, generation_jobs_executed=0, installed=False,
        runtime_tested=False, audio_description="one second of silent PCM; no musical validation",
        checks=checks, performer_id=performer["id"], scope=SCOPE, bridge=bridge,
        decisions=dict(cached=cached, topical=topical, already_pending=deduplicated,
                       generation_cooldown=generation_cooldown,
                       foreign_save=foreign_decision), staging=stage,
        contract_mismatch_diagnostics=mismatch, receipt_reconciliation=histories,
        unresolved_identity=unresolved,
        source_code_sha256={str(path.relative_to(ROOT)).replace("\\", "/"): sha(path) for path in
                            [Path(__file__), ROOT / "hold_music/library.py",
                             ROOT / "hold_music/knowledge_bridge.py", ROOT / "hold_music/registry.py",
                             ROOT / "hold_music/repertoire.py"]},
        limitations=["Fixture UUID mapping does not verify the actor identity in a real save.",
                     "Library asset staging does not install an ESP, scripts, or controller ownership.",
                     "No Papyrus runtime, sound playback, paid provider, or musical confidence is tested."])
    write_json(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="NEW scratch report directory")
    parser.add_argument("--performer", default="sven", help="registered owned pilot (default: sven)")
    parser.add_argument("--registry", type=Path, help="optional registry source, read only")
    args = parser.parse_args(argv)
    try:
        result = run(args.output, args.performer, args.registry)
    except (OSError, ValueError, sqlite3.Error, wave.Error) as exc:
        parser.exit(1, f"Offline loop failed: {exc}\n")
    print(json.dumps(dict(status=result["status"], report=str((args.output / "report.json").resolve()),
                          checks=result["checks"], provider_calls=0, installed=False), indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
