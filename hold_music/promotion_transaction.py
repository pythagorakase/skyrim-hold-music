"""Reviewed, journaled static-file promotion; never a whole-mod installer.

No operation resumes an interrupted apply. Rollback uses retained prior bytes
and fresh target observations, without requiring the old source/build to exist.
The kernel lock coordinates this tool's writers; it cannot lock out editors or
the game, so file guards and a process probe are checked before every mutation.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from hold_music.job_store import _writer_lock, JobStoreBusy
from hold_music.promotion import (
    DEFAULT_MOD, DEFAULT_DATA_MOD, STATIC_FILES, STORAGE, BARD_CONFIG,
    _child, _component, _files, _json, _no_alias, _root, plan_promotion,
)

PROCESSES = frozenset({
    "modorganizer.exe", "skyrimvr.exe", "skyrimse.exe", "skyrim.exe",
    "sksevr_loader.exe", "skse64_loader.exe", "skse_loader.exe",
    "skyrimlauncher.exe", "skyrimvrlauncher.exe", "skyrimselauncher.exe",
})
TERMINAL = {"static_applied", "rolled_back"}


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _token(intent, value):
    return "promotion-v1:" + _hash(_canonical(dict(intent=intent, review=value)))


def _matches(left, right):
    return (isinstance(left, str) and left.isascii() and isinstance(right, str)
            and hmac.compare_digest(left, right))


def _block(code, detail):
    return dict(code=code, detail=detail)


def _locations(mo2_root, mod_name):
    mo2 = _root(mo2_root)
    _component(mod_name)
    target = _root(_child(mo2, "mods/" + mod_name))
    key = _hash(str(target).casefold().encode("utf-8"))
    control = _no_alias(mo2 / ".hold-music-promotion" / key)
    return dict(mo2=mo2, target=target, control=control, journal=control / "journal.json")


def _identity(path):
    info = _no_alias(path).stat()
    return dict(device=info.st_dev, inode=info.st_ino)


def _observe(path):
    path = _no_alias(path)
    if not path.exists():
        return dict(path=str(path), exists=False)
    if not path.is_file():
        raise ValueError("Expected a regular promotion file")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError("Promotion input changed while reading")
    return dict(path=str(path), exists=True, sha256=_hash(raw), size=after.st_size,
                mtime_ns=after.st_mtime_ns)


def _content(row):
    return {key: row[key] for key in ("exists", "sha256", "size") if key in row}


def _static_snapshot(target):
    return {relative: _observe(_child(target, relative)) for relative in sorted(STATIC_FILES)}


def default_process_probe():
    """Verify process enumeration on Windows; unknown platforms fail closed."""
    if os.name != "nt":
        return dict(verified=False, quiescent=False, processes=[], reason="Windows process verification required")
    try:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                                text=True, check=True, timeout=15)
        rows = list(csv.reader(io.StringIO(result.stdout), strict=True))
        if not rows or any(len(row) != 5 or not row[0].strip() or not row[1].isdigit() for row in rows):
            raise ValueError("Invalid process inventory")
        running = sorted({row[0].casefold() for row in rows} & PROCESSES)
        return dict(verified=True, quiescent=not running, processes=running)
    except (OSError, ValueError, subprocess.SubprocessError, csv.Error):
        return dict(verified=False, quiescent=False, processes=[], reason="Process enumeration unavailable")


def _closed(probe):
    try:
        result = (probe or default_process_probe)()
    except Exception:
        return False
    return (isinstance(result, dict) and result.get("verified") is True
            and result.get("quiescent") is True and result.get("processes") == [])


def _sync_directory(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _atomic_write(path, raw, *, scratch=None, expected=None):
    """Durably stage bytes, then replace atomically on the same filesystem."""
    path = _no_alias(path)
    _no_alias(path.parent).mkdir(parents=True, exist_ok=True)
    scratch = _no_alias(scratch or path.parent)
    scratch.mkdir(parents=True, exist_ok=True)
    if scratch.stat().st_dev != path.parent.stat().st_dev:
        raise ValueError("Promotion replacement must stay on one filesystem")
    fd, temporary = tempfile.mkstemp(prefix=".promotion-", dir=scratch)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _no_alias(path)
        if expected is not None and _content(_observe(path)) != expected:
            raise ValueError("Destination changed immediately before replacement")
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _save(loc, journal):
    raw = _canonical(journal)
    _atomic_write(loc["journal"], raw, expected=loc["journal_expected"])
    loc["journal_expected"] = dict(exists=True, sha256=_hash(raw), size=len(raw))


def _protected_path(loc, value):
    if (not isinstance(value, str) or any(part in (".", "..") for part in re.split(r"[/\\]", value))
            or not Path(value).is_absolute()):
        raise ValueError("Unsafe protected path in promotion journal")
    path = Path(os.path.abspath(value))
    if not path.is_relative_to(loc["mo2"]):
        raise ValueError("Protected path escapes the installation")
    return _no_alias(path)


def _load(loc):
    state = _observe(loc["journal"])
    loc["journal_expected"] = _content(state)
    if not state["exists"]:
        if loc["control"].exists():
            unexpected = [p for p in _files(loc["control"]) if p.name != "writer.lock"]
            if unexpected:
                raise ValueError("Orphaned promotion data requires manual inspection")
        return None, state
    raw = loc["journal"].read_bytes()
    if _hash(raw) != state["sha256"] or _observe(loc["journal"]) != state:
        raise ValueError("Promotion journal changed while reading")
    journal = _json(raw)
    if (not isinstance(journal, dict) or journal.get("version") != 1
            or type(journal.get("version")) is not int
            or journal.get("target") != str(loc["target"])
            or not re.fullmatch("[0-9a-f]{32}", str(journal.get("transaction_id", "")))
            or journal.get("state") not in {"preparing", "applying", "static_applied",
                                           "rolling_back", "rolled_back", "interrupted"}
            or not isinstance(journal.get("entries"), list)
            or not journal["entries"] or not isinstance(journal.get("static_before"), dict)
            or set(journal["static_before"]) != STATIC_FILES):
        raise ValueError("Invalid promotion journal")
    context = journal.get("context")
    if (not isinstance(context, dict) or set(context) != {"profile", "data_mod", "roots", "profile_lists"}
            or not isinstance(context["roots"], dict) or set(context["roots"]) != {"mo2", "target", "profile"}
            or not isinstance(context["profile_lists"], dict)
            or set(context["profile_lists"]) != {"modlist.txt", "plugins.txt"}
            or not isinstance(journal.get("protected_before"), list)):
        raise ValueError("Invalid promotion journal context")
    _component(context["profile"])
    if context["data_mod"] is not None:
        _component(context["data_mod"])
    for value in context["roots"].values():
        if (not isinstance(value, dict) or set(value) != {"device", "inode"}
                or any(type(number) is not int or number < 0 for number in value.values())):
            raise ValueError("Invalid directory identity in promotion journal")
    def valid_content(value):
        return (isinstance(value, dict) and type(value.get("exists")) is bool
                and (not value["exists"] or (
                    isinstance(value.get("sha256"), str)
                    and re.fullmatch("[0-9a-f]{64}", value["sha256"])
                    and type(value.get("size")) is int and value["size"] >= 0)))
    for relative, value in journal["static_before"].items():
        if not valid_content(value) or value.get("path") != str(_child(loc["target"], relative)):
            raise ValueError("Invalid original static-file observation")
    for value in context["profile_lists"].values():
        if not valid_content(value) or not value["exists"]:
            raise ValueError("Invalid profile-list guard")
    for row in journal["protected_before"]:
        if not valid_content(row):
            raise ValueError("Invalid protected-file observation")
        _protected_path(loc, row.get("path"))
    seen = set()
    for entry in journal["entries"]:
        if not isinstance(entry, dict) or entry.get("relative_path") not in STATIC_FILES:
            raise ValueError("Journal contains a nonstatic destination")
        relative = entry["relative_path"]
        if relative in seen:
            raise ValueError("Journal repeats a static destination")
        seen.add(relative)
        before, after = entry.get("before"), entry.get("after")
        if (not valid_content(before) or not valid_content(after) or after.get("exists") is not True
                or before != _content(journal["static_before"][relative])
                or type(entry.get("backup_saved")) is not bool
                or entry.get("phase") not in {"pending", "backed_up", "replace_intent", "applied",
                                             "restore_intent", "rolled_back"}):
            raise ValueError("Invalid journal file evidence")
        for value in (before, after):
            if value["exists"] and (not re.fullmatch("[0-9a-f]{64}", str(value.get("sha256", "")))
                                    or type(value.get("size")) is not int or value["size"] < 0):
                raise ValueError("Invalid journal file digest")
    return journal, state


@contextmanager
def _lock(loc):
    _no_alias(loc["control"]).mkdir(parents=True, exist_ok=True)
    try:
        with _writer_lock(_no_alias(loc["control"] / "writer.lock")):
            yield
    except JobStoreBusy:
        raise ValueError("Another promotion writer is using this target") from None


def _backup(loc, journal, entry):
    return _child(loc["control"], "backups/" + journal["transaction_id"] + "/" + entry["relative_path"])


def _protected(loc, context, original):
    """Observe CURRENT mutable state, plus missing paths from the prior review."""
    profile = _root(_child(loc["mo2"], "profiles/" + _component(context["profile"])))
    paths = {_protected_path(loc, row["path"]) for row in original}
    paths.update(path for path in _files(loc["target"])
                 if path.relative_to(loc["target"]).as_posix() not in STATIC_FILES)
    paths.update(_files(_child(profile, "saves")))
    paths.update(_child(profile, name) for name in ("modlist.txt", "plugins.txt"))
    roots = [_child(loc["mo2"], "overwrite")]
    if context["data_mod"] is not None:
        roots.append(_child(loc["mo2"], "mods/" + _component(context["data_mod"])))
    for root in roots:
        for relative in (STORAGE, "SKSE/Plugins/HoldMusic", "Sound/fx/holdmusic"):
            paths.update(_files(_child(root, relative)))
        paths.add(_child(root, BARD_CONFIG))
        paths.update(_child(root, relative) for relative in STATIC_FILES)
    # Journal content cannot select paths outside this installation.
    return [_observe(_protected_path(loc, str(path))) for path in sorted(paths)]


def _context(plan, loc, data_mod):
    profile = _root(_child(loc["mo2"], "profiles/" + plan["target"]["profile"]))
    return dict(profile=plan["target"]["profile"], data_mod=data_mod,
                roots={name: _identity(path) for name, path in
                       (("mo2", loc["mo2"]), ("target", loc["target"]), ("profile", profile))},
                profile_lists={name: _content(_observe(_child(profile, name)))
                               for name in ("modlist.txt", "plugins.txt")})


def _structural_errors(loc, context):
    profile = _root(_child(loc["mo2"], "profiles/" + _component(context["profile"])))
    errors = []
    for name, path in (("mo2", loc["mo2"]), ("target", loc["target"]), ("profile", profile)):
        if _identity(path) != context["roots"][name]:
            errors.append(_block("structural_context_changed", name + " directory identity changed"))
    for name, expected in context["profile_lists"].items():
        if name not in {"modlist.txt", "plugins.txt"} or _content(_observe(_child(profile, name))) != expected:
            errors.append(_block("profile_list_changed", "Selected profile lists changed"))
    return errors


def _promotion_review(arguments):
    plan = plan_promotion(**arguments)
    loc = _locations(arguments["mo2_root"], arguments["mod_name"])
    journal, state = _load(loc)
    static = _static_snapshot(loc["target"])
    context = _context(plan, loc, arguments["data_mod"])
    changes = [row for row in plan["files"] if row["action"] in ("add_static", "replace_static")]
    blockers = list(plan["blockers"])
    if not changes:
        blockers.append(_block("no_static_changes", "No static additions or replacements are proposed"))
    if journal is not None and journal["state"] not in TERMINAL:
        blockers.append(_block("recovery_required", "An interrupted transaction must be reviewed for rollback"))
    bound = dict(arguments={key: str(value) if isinstance(value, Path) else value
                            for key, value in arguments.items()},
                 plan=plan, static=static, context=context, journal=state)
    report = dict(status="promotion_dry_run", can_apply=not blockers, blockers=blockers,
                  review_token=None if blockers else _token("apply_static", bound),
                  writes_performed=False, installed=False, runtime_verified=False,
                  plan=plan, journal_path=str(loc["journal"]), static_changes=len(changes))
    return report, loc, plan, static, context, changes, journal


def promote_static(build_dir, source_root, mo2_root, profile, *, mod_name=DEFAULT_MOD,
                   data_mod=DEFAULT_DATA_MOD, review_token=None, apply=False, process_probe=None):
    arguments = dict(build_dir=_root(build_dir), source_root=_root(source_root),
                     mo2_root=_root(mo2_root), profile=profile, mod_name=mod_name, data_mod=data_mod)
    reviewed = _promotion_review(arguments)
    report, loc = reviewed[:2]
    if not apply:
        return report
    report["status"] = "blocked"
    if not report["can_apply"] or not _matches(review_token, report["review_token"]):
        report["can_apply"] = False
        report["blockers"].append(_block("review_required", "A matching current review token is required"))
        return report
    if not _closed(process_probe):
        report.update(can_apply=False, blockers=[_block("processes_unverified", "Verify Skyrim and MO2 are closed")])
        return report
    with _lock(loc):
        fresh = _promotion_review(arguments)
        report, loc, plan, static, context, changes, previous = fresh
        report["status"] = "blocked"
        if not report["can_apply"] or not _matches(review_token, report["review_token"]):
            report.update(can_apply=False)
            report["blockers"].append(_block("review_changed", "The reviewed inputs changed before the writer lock"))
            return report
        if not _closed(process_probe):
            report.update(can_apply=False, blockers=[_block("processes_unverified", "Verify Skyrim and MO2 are closed")])
            return report
        # Freeze verified static bytes before creating durable dispatch intent.
        payloads, prior, entries = {}, {}, []
        for row in changes:
            relative = row["relative_path"]
            if relative not in STATIC_FILES:
                raise ValueError("Only allowlisted static files can be promoted")
            payloads[relative] = _no_alias(Path(row["source"]["path"])).read_bytes()
            if _hash(payloads[relative]) != row["source"]["sha256"]:
                raise ValueError("Candidate changed before preparation")
            before = _content(static[relative])
            if before["exists"]:
                prior[relative] = _child(loc["target"], relative).read_bytes()
                if _hash(prior[relative]) != before["sha256"]:
                    raise ValueError("Destination changed before preparation")
            entries.append(dict(relative_path=relative, before=before,
                                after=_content(row["source"]), phase="pending", backup_saved=False))
        if previous is not None:
            archive = _child(loc["control"], "history/" + previous["transaction_id"] + ".json")
            if archive.exists() and archive.read_bytes() != _canonical(previous):
                raise ValueError("Existing transaction archive differs")
            if not archive.exists():
                _atomic_write(archive, _canonical(previous))
        journal = dict(version=1, transaction_id=uuid.uuid4().hex, target=str(loc["target"]),
                       state="preparing", review_token=review_token, plan_sha256=_hash(_canonical(plan)),
                       context=context, static_before=static,
                       protected_before=_protected(loc, context, plan["preserved"]),
                       entries=entries)
        plan_observations = {row["path"]: row for row in plan["observed_files"]}
        if any(plan_observations.get(row["path"]) != row for row in journal["protected_before"]):
            raise ValueError("Protected observations changed since the reviewed plan")
        _save(loc, journal)
        try:
            for entry in entries:
                if entry["before"]["exists"]:
                    _atomic_write(_backup(loc, journal, entry), prior[entry["relative_path"]],
                                  expected=dict(exists=False))
                    entry["backup_saved"] = True
                entry["phase"] = "backed_up"
                _save(loc, journal)
            # Replan all current inputs immediately before the first destination write.
            if _hash(_canonical(plan_promotion(**arguments))) != journal["plan_sha256"]:
                raise ValueError("Reviewed inputs changed before the first static write")
            protected = _protected(loc, context, journal["protected_before"])
            original_protected = {row["path"]: {key: value for key, value in row.items() if key != "kind"}
                                  for row in journal["protected_before"]}
            if {row["path"]: row for row in protected} != original_protected:
                raise ValueError("Protected files changed before promotion")
            journal["state"] = "applying"
            _save(loc, journal)
            expected_static = deepcopy(static)
            def guard():
                if not _closed(process_probe) or _structural_errors(loc, context):
                    raise ValueError("Process or structural context changed")
                if _protected(loc, context, journal["protected_before"]) != protected:
                    raise ValueError("Protected files changed during promotion")
                if _static_snapshot(loc["target"]) != expected_static:
                    raise ValueError("Static destination changed during promotion")
                for candidate in entries:
                    if candidate["before"]["exists"] and (
                            _content(_observe(_backup(loc, journal, candidate))) != candidate["before"]):
                        raise ValueError("Backup changed during promotion")
                if _no_alias(loc["journal"]).read_bytes() != _canonical(journal):
                    raise ValueError("Journal changed during promotion")
            for entry in entries:
                guard()
                entry["phase"] = "replace_intent"
                _save(loc, journal)
                _atomic_write(_child(loc["target"], entry["relative_path"]),
                              payloads[entry["relative_path"]], scratch=loc["control"],
                              expected=entry["before"])
                expected_static[entry["relative_path"]] = _observe(_child(loc["target"], entry["relative_path"]))
                if _content(expected_static[entry["relative_path"]]) != entry["after"]:
                    raise ValueError("Written static file differs from the candidate")
                entry["phase"] = "applied"
                _save(loc, journal)
            guard()
            journal["state"] = "static_applied"
            _save(loc, journal)
            return dict(status="static_applied", writes_performed=True, installed=False,
                        runtime_verified=False, transaction_id=journal["transaction_id"],
                        journal_path=str(loc["journal"]), static_files_changed=len(entries))
        except Exception as exc:
            journal.update(state="interrupted", error_type=type(exc).__name__)
            recorded = True
            try:
                _save(loc, journal)
            except (OSError, ValueError):
                recorded = False
            return dict(status="interrupted", writes_performed=True, installed=False,
                        runtime_verified=False, error_type=type(exc).__name__,
                        journal_update_recorded=recorded,
                        transaction_id=journal["transaction_id"], journal_path=str(loc["journal"]))


def _rollback_review(loc):
    journal, state = _load(loc)
    if journal is None:
        return dict(status="rollback_dry_run", can_rollback=False, review_token=None,
                    blockers=[_block("no_transaction", "No promotion transaction exists")],
                    writes_performed=False), None, None
    blockers = _structural_errors(loc, journal["context"])
    if journal["state"] == "rolled_back":
        blockers.append(_block("already_rolled_back", "This transaction is already rolled back"))
    files, backups = {}, {}
    entries = {entry["relative_path"]: entry for entry in journal["entries"]}
    for relative, original in journal["static_before"].items():
        current = _observe(_child(loc["target"], relative))
        files[relative] = current
        entry = entries.get(relative)
        allowed = [entry["before"], entry["after"]] if entry else [_content(original)]
        if _content(current) not in allowed:
            blockers.append(_block("static_file_changed", relative))
        if entry and entry["before"]["exists"]:
            backup = _observe(_backup(loc, journal, entry))
            backups[relative] = backup
            # Before preparation completed, an absent backup is safe only if
            # this destination still has the reviewed original bytes.
            if (backup["exists"] and _content(backup) != entry["before"]
                    or not backup["exists"] and (
                        entry["backup_saved"] or _content(current) != entry["before"])):
                blockers.append(_block("backup_changed_or_missing", relative))
    protected = _protected(loc, journal["context"], journal["protected_before"])
    old = {row["path"]: _content(row) for row in journal["protected_before"]}
    changed = [row["path"] for row in protected if old.get(row["path"]) != _content(row)]
    observation = dict(journal=state, files=files, backups=backups, protected=protected,
                       context=journal["context"])
    report = dict(status="rollback_dry_run", can_rollback=not blockers, blockers=blockers,
                  review_token=None if blockers else _token("rollback_static", observation),
                  writes_performed=False, transaction_id=journal["transaction_id"],
                  journal_path=str(loc["journal"]), state=journal["state"],
                  protected_changes_since_promotion=changed, files=files, backups=backups)
    return report, journal, observation


def rollback_static(mo2_root, *, mod_name=DEFAULT_MOD, review_token=None, apply=False, process_probe=None):
    loc = _locations(mo2_root, mod_name)
    report, journal, observation = _rollback_review(loc)
    if not apply:
        return report
    report["status"] = "blocked"
    if not report["can_rollback"] or not _matches(review_token, report["review_token"]):
        report["can_rollback"] = False
        report["blockers"].append(_block("review_required", "A matching current rollback review token is required"))
        return report
    if not _closed(process_probe):
        report.update(can_rollback=False, blockers=[_block("processes_unverified", "Verify Skyrim and MO2 are closed")])
        return report
    with _lock(loc):
        report, journal, observation = _rollback_review(loc)
        if not report["can_rollback"] or not _matches(review_token, report["review_token"]):
            report.update(status="blocked", can_rollback=False)
            report["blockers"].append(_block("review_changed", "Rollback inputs changed before the writer lock"))
            return report
        if not _closed(process_probe):
            report.update(status="blocked", can_rollback=False,
                          blockers=[_block("processes_unverified", "Verify Skyrim and MO2 are closed")])
            return report
        for entry in journal["entries"]:
            if entry["before"]["exists"] and observation["backups"][entry["relative_path"]]["exists"]:
                entry["backup_saved"] = True
        journal["state"] = "rolling_back"
        _save(loc, journal)
        try:
            expected_files = deepcopy(observation["files"])
            def guard():
                if not _closed(process_probe):
                    raise ValueError("Process quiescence could not be verified")
                if _structural_errors(loc, journal["context"]):
                    raise ValueError("Structural rollback context changed")
                if _static_snapshot(loc["target"]) != expected_files:
                    raise ValueError("Static files changed during rollback")
                if _protected(loc, journal["context"], journal["protected_before"]) != observation["protected"]:
                    raise ValueError("Protected files changed during rollback")
                for relative, expected in observation["backups"].items():
                    original_entry = next(row for row in journal["entries"] if row["relative_path"] == relative)
                    if _observe(_backup(loc, journal, original_entry)) != expected:
                        raise ValueError("Backups changed during rollback")
                if _no_alias(loc["journal"]).read_bytes() != _canonical(journal):
                    raise ValueError("Journal changed during rollback")
            for entry in reversed(journal["entries"]):
                guard()
                relative = entry["relative_path"]
                target = _child(loc["target"], relative)
                if _content(expected_files[relative]) == entry["before"]:
                    entry["phase"] = "rolled_back"
                    _save(loc, journal)
                    continue
                entry["phase"] = "restore_intent"
                _save(loc, journal)
                if entry["before"]["exists"]:
                    raw = _backup(loc, journal, entry).read_bytes()
                    if _hash(raw) != entry["before"]["sha256"]:
                        raise ValueError("Backup changed before restore")
                    _atomic_write(target, raw, scratch=loc["control"],
                                  expected=_content(expected_files[relative]))
                else:
                    if _content(_observe(target)) != _content(expected_files[relative]):
                        raise ValueError("Destination changed immediately before removal")
                    _no_alias(target).unlink()
                    _sync_directory(target.parent)
                expected_files[relative] = _observe(target)
                if _content(expected_files[relative]) != entry["before"]:
                    raise ValueError("Restored static file differs from the retained original")
                entry["phase"] = "rolled_back"
                _save(loc, journal)
            guard()
            journal["state"] = "rolled_back"
            _save(loc, journal)
            return dict(status="rolled_back", writes_performed=True, installed=False,
                        runtime_verified=False, transaction_id=journal["transaction_id"],
                        journal_path=str(loc["journal"]))
        except Exception as exc:
            journal.update(state="interrupted", error_type=type(exc).__name__)
            recorded = True
            try:
                _save(loc, journal)
            except (OSError, ValueError):
                recorded = False
            return dict(status="interrupted", writes_performed=True, installed=False,
                        runtime_verified=False, error_type=type(exc).__name__,
                        journal_update_recorded=recorded,
                        transaction_id=journal["transaction_id"], journal_path=str(loc["journal"]))


def promotion_status(mo2_root, *, mod_name=DEFAULT_MOD):
    loc = _locations(mo2_root, mod_name)
    report, journal, _ = _rollback_review(loc)
    if journal is None:
        return dict(status="no_transaction", writes_performed=False, state=None,
                    transaction_id=None, recovery_required=False, journal_path=str(loc["journal"]))
    report.update(status="promotion_status", recovery_required=journal["state"] not in TERMINAL)
    return report
