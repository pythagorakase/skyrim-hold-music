"""Artifact-bound offline evidence for the candidate runtime selector.

This module reads explicit local inputs only. Evidence records a local test run;
it is not a signed attestation or a claim that Skyrim executed the candidate.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

REPORT_FILENAME = "runtime-selection-verification.json"
SCRIPT_NAMES = ("HM_Config", "HM_Controller", "HM_Library")
IDENTITY_FIELDS = (
    "performer_id", "region", "recipe_id", "recipe_revision", "model_id",
    "instrument_family", "instrument_name", "arrangement", "mode", "voice",
)
VERIFICATION_FILES = (
    "tests/pex_vm.py", "tests/test_runtime_selection.py",
    "tools/verify_runtime_selection.py", "tools/build_game_package.py",
    "tools/build_config.py",
)
HELPER_FILES = (
    "hold_music/runtime_contract.py", "hold_music/recording_identity.py",
    "hold_music/runtime_capability.py",
)


def descriptor():
    """Return the only capability profile recognized by this verifier."""
    return {
        "schema_version": 1,
        "capability": "hold-music-runtime-selection",
        "manifest_version": 1,
        "comparison": "sha256-projection-v1",
        "identity_fields": list(IDENTITY_FIELDS),
        "encoding": "ordered-values-json-compact-utf8-ensure_ascii_false",
        "key_format": "lowercase-sha256-hex",
        "contracts_per_performer": 1,
        "instrument_family": "plucked_string",
        "arrangements": ["solo_lute", "solo_lute_and_voice"],
        "verification_scope": "compiled-papyrus-fixtures-with-native-mocks",
        "runtime_verified": False,
    }


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _same(left, right):
    # bool and int must remain different in schemas, unlike Python ==.
    return _encoded(left) == _encoded(right)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate evidence JSON key")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)


def _plain(path):
    for entry in (path, *path.parents):
        if entry.is_symlink():
            raise ValueError("Capability inputs cannot use symlinks")
        try:
            attributes = getattr(entry.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            continue
        if attributes & 0x400:
            raise ValueError("Capability inputs cannot use junctions")
    return path


def _files(root):
    _plain(root)
    if not root.is_dir():
        raise ValueError("Missing capability input directory: " + str(root))
    files, seen = [], set()
    for path in sorted(root.rglob("*")):
        _plain(path)
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.casefold() in seen:
            raise ValueError("Case-ambiguous capability input inventory")
        seen.add(relative.casefold())
        files.append(path)
    return files


def required_test_ids(raw):
    """Read explicit TestCase methods without importing or executing test code."""
    try:
        tree = ast.parse(raw.decode("utf-8-sig"))
    except (SyntaxError, UnicodeError) as exc:
        raise ValueError("Cannot parse runtime selection tests") from exc
    ids = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [item for item in node.body
                   if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and item.name.startswith("test_")]
        if not methods:
            continue
        valid_base = len(node.bases) == 1 and (
            isinstance(node.bases[0], ast.Name) and node.bases[0].id == "TestCase"
            or isinstance(node.bases[0], ast.Attribute) and node.bases[0].attr == "TestCase"
            and isinstance(node.bases[0].value, ast.Name) and node.bases[0].value.id == "unittest"
        )
        if not valid_base or any(isinstance(item, ast.AsyncFunctionDef) for item in methods):
            raise ValueError("Runtime tests must declare direct synchronous TestCase methods")
        ids.extend(f"test_runtime_selection.{node.name}.{item.name}" for item in methods)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Runtime selection requires distinct named tests")
    return sorted(ids)


def _decompiler(plan):
    if not isinstance(plan, dict):
        raise ValueError("Missing build plan")
    inputs = plan.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("Missing build input provenance")
    value = inputs.get("decompiler")
    if (not isinstance(value, dict) or set(value) != {"path", "sha256"}
            or not isinstance(value["path"], str) or not value["path"].strip()
            or not isinstance(value["sha256"], str)
            or not re.fullmatch("[0-9a-f]{64}", value["sha256"])):
        raise ValueError("Missing recorded disassembler provenance")
    # Historical path is never used to select a file by validation.
    return deepcopy(value)


def capture_inputs(build_dir, source_root, plan, *, read_bytes=None):
    """Hash candidate inputs using explicit roots and fixed verifier paths.

    read_bytes(Path)->bytes allows a read-only caller to observe every read.
    No file path from a receipt is opened, including the old disassembler path.
    """
    build = _plain(Path(build_dir).absolute())
    source = _plain(Path(source_root).absolute())
    disassembler = _decompiler(plan)
    reader = read_bytes or Path.read_bytes
    raw_cache = {}

    def read(path):
        path = _plain(path)
        if not path.is_file():
            raise ValueError("Missing capability input file: " + str(path))
        raw = reader(path)
        if not isinstance(raw, bytes):
            raise ValueError("Capability reader must return bytes")
        raw_cache[path] = raw
        return raw

    package = build / "package"
    package_hashes = {path.relative_to(package).as_posix(): _sha(read(path))
                      for path in _files(package)}
    declared = _json(read(build / "package-hashes.json"))
    if not isinstance(declared, dict) or not _same(declared, package_hashes):
        raise ValueError("Candidate package inventory does not match its hashes")
    source_hashes = {path.relative_to(source).as_posix(): _sha(read(path))
                     for folder in ("src", "data", "imports")
                     for path in _files(source / folder)}
    if not _same(source_hashes, plan.get("source_files")):
        raise ValueError("Candidate source inventory changed from the build plan")
    artifacts = {"package/" + name: digest for name, digest in package_hashes.items()}
    artifacts["package-hashes.json"] = _sha(raw_cache[build / "package-hashes.json"])
    for name in SCRIPT_NAMES:
        relative = f"Scripts/Source/{name}.psc"
        source_key = "src/" + relative
        if (source_key not in source_hashes or relative not in package_hashes
                or package_hashes[relative] != source_hashes[source_key]
                or f"Scripts/{name}.pex" not in package_hashes):
            raise ValueError("Required candidate script/source provenance is missing")
        relative = f"disassembly/{name}.pas"
        artifacts[relative] = _sha(read(build / relative))
    verification = {
        "game_package/" + name: _sha(read(source / name))
        for name in VERIFICATION_FILES
    }
    verification.update({name: _sha(read(source.parent / name)) for name in HELPER_FILES})
    tests = required_test_ids(raw_cache[source / "tests/test_runtime_selection.py"])
    return {
        "artifact_hashes": artifacts,
        "source_hashes": source_hashes,
        "verification_sources": verification,
        "required_test_ids": tests,
        "disassembler": disassembler,
        "disassembly_command": ["Champollion", "<candidate.pex>", "-a", "<build/disassembly>", "--no-debug-line"],
    }


def _validate_result(value, expected):
    keys = {"tests_run", "started", "passed", "failures", "errors", "skipped",
            "expected_failures", "unexpected_successes"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Invalid runtime test result schema")
    for key in ("tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes"):
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError("Invalid runtime test result count")
    if (value["tests_run"] != len(expected)
            or any(value[key] for key in ("failures", "errors", "skipped",
                                         "expected_failures", "unexpected_successes"))
            or not _same(value["started"], expected) or not _same(value["passed"], expected)):
        raise ValueError("Every required runtime test must run and pass without skips")


def create_report(inputs, test_result):
    """Create evidence only for the complete successful required test set."""
    expected = inputs.get("required_test_ids") if isinstance(inputs, dict) else None
    if not isinstance(expected, list) or not expected or len(expected) != len(set(expected)):
        raise ValueError("Missing required runtime test identities")
    _validate_result(test_result, expected)
    return {
        "schema_version": 1, "status": "passed_offline",
        "installed": False, "runtime_verified": False,
        "descriptor": descriptor(), "inputs": deepcopy(inputs),
        "tests": deepcopy(test_result),
    }


def receipt_capability(report_bytes):
    report = _json(report_bytes)
    if not isinstance(report, dict) or not _same(report.get("descriptor"), descriptor()):
        raise ValueError("Unrecognized runtime capability descriptor")
    return {
        "schema_version": 1, "descriptor": descriptor(),
        "verification_file": REPORT_FILENAME,
        "verification_sha256": _sha(report_bytes),
    }


def validate_capability(receipt, build_dir, source_root, *, read_bytes=None):
    """Validate locally produced offline evidence, returning None for legacy.

    Recomputes all measured files from explicit current roots. Historical paths
    in the report/plan do not prevent relocating byte-identical artifacts.
    """
    if not isinstance(receipt, dict):
        raise ValueError("Invalid build receipt")
    if "runtime_selection_capability" not in receipt:
        return None
    value = receipt["runtime_selection_capability"]
    expected_keys = {"schema_version", "descriptor", "verification_file", "verification_sha256"}
    if (not isinstance(value, dict) or set(value) != expected_keys
            or type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or not _same(value.get("descriptor"), descriptor())
            or value.get("verification_file") != REPORT_FILENAME
            or not isinstance(value.get("verification_sha256"), str)
            or not re.fullmatch("[0-9a-f]{64}", value["verification_sha256"])):
        raise ValueError("Unrecognized runtime capability receipt")
    reader = read_bytes or Path.read_bytes
    report_raw = reader(_plain(Path(build_dir).absolute() / REPORT_FILENAME))
    if not isinstance(report_raw, bytes) or _sha(report_raw) != value["verification_sha256"]:
        raise ValueError("Runtime verification report hash differs from the receipt")
    report = _json(report_raw)
    inputs = capture_inputs(build_dir, source_root, receipt.get("plan"), read_bytes=read_bytes)
    expected_report = create_report(inputs, report.get("tests") if isinstance(report, dict) else None)
    if not _same(report, expected_report):
        raise ValueError("Runtime verification evidence is stale or inconsistent")
    package_hashes = {
        name.removeprefix("package/"): digest for name, digest in inputs["artifact_hashes"].items()
        if name.startswith("package/")
    }
    if not _same(receipt.get("package_hashes"), package_hashes):
        raise ValueError("Capability package hashes differ from the build receipt")
    return {
        "descriptor": descriptor(), "verification_file": REPORT_FILENAME,
        "verification_sha256": value["verification_sha256"],
        "tests_run": report["tests"]["tests_run"], "status": "verified_offline",
        "installed": False, "runtime_verified": False,
    }
