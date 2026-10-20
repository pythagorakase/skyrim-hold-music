#!/usr/bin/env python3
"""Prepare a reversible SkyrimNet bard handoff for a selected MO2 profile.

Dry-run by default. Reports never contain configuration values other than the
bard enabled flag. Apply/rollback require the Windows game and MO2 to be closed.
Overwrite and data-mod inputs are shared and may affect other MO2 profiles.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "game_adapter/hold_music_adapter"))
from engine import MANAGED, get_scalar, replace_raw_scalar, scalar_location
from game_package.tools.install_game_package import (
    directory_name, require_closed, sha, text_format,
)

CONFIG = "SKSE/Plugins/SkyrimNet/config/BardSinging.yaml"


def _child(root, path):
    """Reject escaped paths and links, including directory junctions."""
    path = Path(path).absolute()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Ownership files must remain inside the requested MO2 root")
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
            raise ValueError("Linked ownership paths require manual review")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Ownership path resolves outside the requested MO2 root")
    return path


def _read(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _hash(raw):
    return None if raw is None else sha(raw)


def _decode(raw):
    return text_format(raw)[2]


def _encode_like(raw, text):
    bom, encoding, _ = text_format(raw)
    return bom + text.encode(encoding)


def _disabled(raw):
    text = _decode(raw)
    value = get_scalar(text, ("bard_singing", "enabled"))
    if type(value) is not bool:
        raise ValueError("Bard Singing enabled must be an unambiguous boolean")
    if not value:
        return raw
    start, end, _ = scalar_location(text, ("bard_singing", "enabled"))
    # The parser already established a true boolean. Preserve comments,
    # whitespace, encoding, BOM and every unrelated byte.
    scalar = text[start:end]
    at = scalar.index("true")
    return _encode_like(raw, text[:start] + scalar[:at] + "false" + scalar[at + 4:] + text[end:])


@dataclass
class HandoffPlan:
    root: Path
    profile: str
    observed: dict[Path, bytes | None] = field(default_factory=dict, repr=False)
    changes: dict[Path, bytes | None] = field(default_factory=dict, repr=False)
    roles: dict[Path, list[str]] = field(default_factory=dict)

    def read(self, path, role=None):
        path = _child(self.root, path)
        raw = _read(path)
        self.observed[path] = raw
        if role:
            self.roles.setdefault(path, []).append(role)
        return raw

    def change(self, path, after):
        if self.observed[path] != after:
            self.changes[path] = after
        else:
            self.changes.pop(path, None)

    def summary(self):
        return {
            "version": 1, "operation": "disable_skyrimnet_bard",
            "status": "dry_run", "mo2_root": str(self.root), "profile": self.profile,
            "changes": [
                {"path": str(path), "roles": self.roles.get(path, []),
                 "action": "delete" if after is None else "replace",
                 "before_sha256": _hash(self.observed[path]), "after_sha256": _hash(after)}
                for path, after in self.changes.items()
            ],
            "checks": {
                "all_known_launch_inputs_disabled_after_apply": True,
                "pending_overlay_reconciled_after_apply": True,
            },
            "limitations": [
                "Prepared input reconciliation is not proof of MO2 injection or runtime controller ownership.",
                "Overwrite and data-mod files are shared MO2 inputs; changing them can affect other profiles.",
                "Apply and rollback require Skyrim and MO2 closed; external writers must also remain stopped.",
                "Rollback backups contain private configuration; keep the receipt directory private.",
                "No Hold Music MCM, mod list, registry, audio, save or SkyrimNet database is changed.",
            ],
        }


def plan_handoff(mo2_root, profile):
    root = Path(mo2_root).resolve(strict=True)
    profile = directory_name(profile)
    plan = HandoffPlan(root, profile)
    profile_dir = root / "profiles" / profile
    modlist = plan.read(profile_dir / "modlist.txt", "profile_modlist")
    if modlist is None:
        raise ValueError("The selected MO2 profile has no mod list")
    active = [directory_name(line[1:]) for line in _decode(modlist).splitlines() if line.startswith("+")]
    roots = [root / "overwrite"] + [root / "mods" / name for name in active]
    sources = []
    # Observe absent higher-priority paths too: an overwrite created after the
    # plan must invalidate it before any configuration is changed.
    for base in roots:
        path = base / CONFIG
        if plan.read(path, "loose_candidate") is not None:
            sources.append(path)
    if not sources:
        raise ValueError("No active loose Bard Singing configuration was found")
    winner = sources[0]
    plan.roles[winner].append("loose_file_winner")
    targets = {winner}
    adapter_path = root / "plugins/hold_music_adapter/local.json"
    adapter_raw = plan.read(adapter_path, "adapter_configuration")
    source = None
    if adapter_raw is not None:
        adapter = json.loads(_decode(adapter_raw))
        if not isinstance(adapter, dict):
            raise ValueError("Invalid adapter configuration")
        if adapter.get("profile") == profile:
            adapter_mod = directory_name(adapter["mod"])
            data_mod = directory_name(adapter["data_mod"])
            if adapter_mod.casefold() in {name.casefold() for name in active}:
                if data_mod.casefold() not in {name.casefold() for name in active}:
                    raise ValueError("The configured adapter data mod is inactive")
                source = root / "mods" / data_mod / CONFIG
                if plan.read(source, "adapter_launch_input") is None:
                    raise ValueError("The adapter launch input is missing")
                targets.add(source)
    runtime = profile_dir / "hold-music-runtime"
    baseline_path = runtime / "BardSinging.baseline.yaml"
    overlay_path = runtime / "BardSinging.yaml"
    conflict_path = runtime / "BardSinging.conflict.yaml"
    baseline = plan.read(baseline_path, "adapter_baseline")
    overlay = plan.read(overlay_path, "adapter_overlay")
    conflict = plan.read(conflict_path, "adapter_conflict")
    if conflict is not None:
        raise ValueError("An adapter conflict copy requires manual review before handoff")
    if baseline is not None:
        if source is None or overlay is None:
            raise ValueError("Cannot reconcile an orphaned adapter baseline")
        original = _decode(baseline)
        candidate = _decode(overlay)
        normalized = original
        # Restore routing, never persist the temporary localhost endpoint.
        for address in MANAGED:
            raw = scalar_location(original, address)[2]
            candidate = replace_raw_scalar(candidate, address, raw)
            normalized = replace_raw_scalar(normalized, address, raw)
        current = plan.observed[source]
        if candidate != normalized:
            if _decode(current) != original:
                raise ValueError("Source and overlay both changed; preserve and review both edits")
            plan.change(source, _encode_like(baseline, candidate))
        plan.change(baseline_path, None)
    # A closed-session overlay is disposable, with an exact rollback backup.
    # Removing it also avoids presenting an old provider route as current state.
    if overlay is not None:
        if source is None:
            raise ValueError("Cannot establish ownership of the leftover adapter overlay")
        plan.change(overlay_path, None)
    for path in sorted(targets):
        raw = plan.changes.get(path, plan.observed[path])
        plan.change(path, _disabled(raw))
    return plan


def _verify_observed(plan, completed=()):
    for path, before in plan.observed.items():
        _child(plan.root, path)
        expected = plan.changes[path] if path in completed else before
        if _read(path) != expected:
            raise ValueError("An ownership input changed since planning; rerun the dry run")


def _atomic_write(path, raw):
    """Replace one file; temporary files never contain config in stdout/logs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _save_receipt(path, receipt):
    _atomic_write(path, (json.dumps(receipt, indent=2) + "\n").encode("utf-8"))


def apply_handoff(plan, receipt_dir):
    require_closed()
    _verify_observed(plan)
    receipt_dir = Path(receipt_dir).absolute()
    # A new directory prevents replacing another operation's recovery data.
    receipt_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    receipt_path = receipt_dir / "receipt.json"
    receipt = plan.summary()
    receipt.update(
        status="prepared", created_at=datetime.now(timezone.utc).isoformat(), files=[],
        guards=[{"relative_path": path.relative_to(plan.root).as_posix(), "sha256": _hash(raw)}
                for path, raw in plan.observed.items() if path not in plan.changes],
    )
    for index, (path, after) in enumerate(plan.changes.items()):
        before = plan.observed[path]
        backup = f"{index:03d}.before"
        if before is not None:
            _atomic_write(receipt_dir / backup, before)
        receipt["files"].append({
            "relative_path": path.relative_to(plan.root).as_posix(),
            "backup": backup if before is not None else None,
            "before_sha256": _hash(before), "after_sha256": _hash(after),
            "state": "pending",
        })
    # Durable recovery data comes before the first mutation. A crash after a
    # replace but before its checkpoint is recovered by content hashes.
    _save_receipt(receipt_path, receipt)
    try:
        _verify_observed(plan)
        completed = set()
        for record, (path, after) in zip(receipt["files"], plan.changes.items()):
            _verify_observed(plan, completed)
            if after is None:
                path.unlink()
            else:
                _atomic_write(path, after)
            completed.add(path)
            record["state"] = "applied"
            _save_receipt(receipt_path, receipt)
        _verify_observed(plan, completed)
        receipt["status"] = "applied"
        _save_receipt(receipt_path, receipt)
    except BaseException:
        receipt["status"] = "incomplete"
        _save_receipt(receipt_path, receipt)
        raise
    return {"status": receipt["status"], "receipt": str(receipt_path), "files_changed": len(receipt["files"])}


def rollback_handoff(receipt_path):
    require_closed()
    receipt_path = Path(receipt_path).absolute()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("version") != 1 or receipt.get("operation") != "disable_skyrimnet_bard":
        raise ValueError("Unrecognized ownership receipt")
    root = Path(receipt["mo2_root"]).resolve(strict=True)
    def verify_dependencies():
        for guard in receipt["guards"]:
            path = _child(root, root / guard["relative_path"])
            if _hash(_read(path)) != guard["sha256"]:
                raise ValueError("Ownership context changed after handoff; review before rollback")
    verify_dependencies()
    work = []
    for record in receipt["files"]:
        path = _child(root, root / record["relative_path"])
        current = _read(path)
        before = None
        if record["backup"] is not None:
            backup = Path(record["backup"])
            if backup.name != str(backup) or not backup.name.endswith(".before"):
                raise ValueError("Invalid rollback backup path")
            backup_path = receipt_path.parent / backup
            if backup_path.is_symlink():
                raise ValueError("Linked rollback backup is not supported")
            before = backup_path.read_bytes()
        if _hash(before) != record["before_sha256"]:
            raise ValueError("Rollback backup hash mismatch; nothing restored")
        if _hash(current) not in (record["before_sha256"], record["after_sha256"]):
            raise ValueError("A reconciled file has changed; rollback will not overwrite it")
        work.append((path, current, before, record))
    # Validate every file and backup before restoring any. Recheck each one
    # immediately before replacement to catch changes during restoration.
    for path, current, before, record in reversed(work):
        verify_dependencies()
        if _read(path) != current:
            raise ValueError("A file changed during rollback; recovery data was retained")
        if current != before:
            if before is None:
                path.unlink()
            else:
                _atomic_write(path, before)
        record["state"] = "restored"
        _save_receipt(receipt_path, receipt)
    receipt["status"] = "rolled_back"
    _save_receipt(receipt_path, receipt)
    return {"status": "rolled_back", "receipt": str(receipt_path), "files_restored": len(work)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mo2-root", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt-dir", type=Path, help="New private backup directory, required with --apply")
    parser.add_argument("--rollback", type=Path, help="Restore an earlier receipt with current-file hash guards")
    args = parser.parse_args(argv)
    try:
        if args.rollback:
            if args.mo2_root or args.profile or args.apply or args.receipt_dir:
                parser.error("--rollback cannot be combined with planning/apply options")
            result = rollback_handoff(args.rollback)
        else:
            if not args.mo2_root or not args.profile:
                parser.error("--mo2-root and --profile are required")
            if args.apply != bool(args.receipt_dir):
                parser.error("--apply and --receipt-dir must be supplied together")
            plan = plan_handoff(args.mo2_root, args.profile)
            result = apply_handoff(plan, args.receipt_dir) if args.apply else plan.summary()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        # Do not print a YAML parser/JSON decoding exception that might contain
        # credential-bearing source text.
        parser.exit(2, f"Ownership operation stopped ({type(exc).__name__}). Inputs/recovery data retained; review privately.\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
