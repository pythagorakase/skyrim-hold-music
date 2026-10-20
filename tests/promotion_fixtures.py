"""Temporary fake installation inputs; never selects the real game directory."""
import hashlib
import json
from pathlib import Path

from hold_music.promotion import DEFAULT_MOD, DEFAULT_DATA_MOD, REQUIRED_FILES, SETTINGS, STORAGE


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, (dict, list)) else value, encoding="utf-8")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closed_processes():
    return dict(verified=True, quiescent=True, processes=[])


def create_promotion_fixture(root):
    """Return arguments, target, package, profile_dir, source_root, build_dir, root."""
    root = Path(root).resolve()
    source, build, mo2 = root / "checkout/game_package", root / "candidate/build", root / "mo2"
    package, profile = build / "package", mo2 / "profiles/pilot"
    target = mo2 / "mods" / DEFAULT_MOD
    target.mkdir(parents=True)
    _write(profile / "modlist.txt", "+" + DEFAULT_MOD + "\n")
    _write(profile / "plugins.txt", "*HoldMusic.esp\n")
    _write(profile / "saves/test.ess", "existing fixture save")
    hashes, sources = {}, {}
    for relative in sorted(REQUIRED_FILES):
        _write(package / relative, "candidate fixture: " + relative)
        hashes[relative] = _sha(package / relative)
        if relative.endswith(".psc"):
            _write(source / "src" / relative, "candidate fixture: " + relative)
            sources["src/" + relative] = _sha(source / "src" / relative)
    inputs = {"modlist": {"path": str(profile / "modlist.txt"), "sha256": _sha(profile / "modlist.txt")}}
    for label, name in (("plugin_project", "PluginBuilder.csproj"), ("plugin_source", "Program.cs"),
                        ("nuget_config", "NuGet.Config")):
        path = source / "tools/PluginBuilder" / name
        _write(path, "source fixture " + name)
        inputs[label] = dict(path=str(path), sha256=_sha(path))
    _write(build / "package-hashes.json", hashes)
    _write(build / "build-receipt.json", dict(
        schema_version=1, status="built_offline", installed=False, runtime_verified=False,
        package_hashes=hashes, dependencies={}, plan=dict(
            mode="offline_build_plan", source_files=sources, inputs=inputs,
            stack=dict(mo2_root=str(mo2), profile="pilot"))))
    _write(target / "Scripts/HM_Controller.pex", "prior controller bytes")
    _write(target / SETTINGS, "custom user settings")
    _write(target / (STORAGE + "/library.json"), dict(version=1, slots=24, recordings=[]))
    _write(target / (STORAGE + "/receipts.json"), {"private": "fixture history"})
    _write(target / (STORAGE + "/trace.json"), {"private": "fixture trace"})
    _write(target / "Sound/fx/holdmusic/hm_slot_03.wav", "existing fixture audio")
    _write(target / (STORAGE + "/hm_slot_03.lyrics.txt"), "existing fixture lyrics")
    _write(target / "unrelated.txt", "keep this file")
    _write(mo2 / "overwrite" / (STORAGE + "/trace.json"), "shadow fixture trace")
    _write(mo2 / "mods" / DEFAULT_DATA_MOD / (STORAGE + "/receipts.json"), "shadow fixture receipts")
    return dict(root=root, target=target, package=package, profile_dir=profile,
                source_root=source, build_dir=build,
                arguments=dict(build_dir=build, source_root=source, mo2_root=mo2,
                               profile="pilot", mod_name=DEFAULT_MOD, data_mod=DEFAULT_DATA_MOD))
