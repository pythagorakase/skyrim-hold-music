"""Install the local prototype with Skyrim and MO2 closed. No game config edits."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil


def install(root, profile, data_mod):
    project = Path(__file__).resolve().parents[1]
    root = Path(root).resolve()
    profile_dir = root / "profiles" / profile
    modlist = profile_dir / "modlist.txt"
    data = root / "mods" / data_mod / "SKSE/Plugins/SkyrimNet"
    source_config = data / "config/BardSinging.yaml"
    if not modlist.is_file() or not source_config.is_file():
        raise RuntimeError("The selected profile or isolated SkyrimNet config is missing")
    marker = "MGO Experimental - Solo Lute"
    plugin = root / "plugins/solo_lute"
    mod = root / "mods" / marker
    for target in (plugin, mod):
        if not target.resolve().is_relative_to(root):
            raise RuntimeError("Installation target is outside MO2")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = root.parent / "codex-backups" / (stamp + "-solo-lute-plugin")
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(modlist, backup / "modlist.txt")
    shutil.copy2(source_config, backup / "BardSinging.yaml")
    for target, label in ((plugin, "mo2-plugin"), (mod, "content-mod")):
        if target.exists():
            shutil.copytree(target, backup / label)
    shutil.copytree(project / "mo2_plugin/solo_lute", plugin, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "local.json"))
    shutil.copytree(project / "content", mod, dirs_exist_ok=True)
    local = {"profile": profile, "data_mod": data_mod, "mod": marker, "port": 18765}
    (plugin / "local.json").write_text(json.dumps(local, indent=2) + "\n", encoding="utf-8")
    (mod / "meta.ini").write_text('[General]\nmodid=0\nversion=0.1.0\ncategory=0\nnotes=Local Solo Lute prototype; requires the MO2 companion plugin.\n', encoding="utf-8")
    settings = data / "config/plugins/SoloLute/settings.yaml"
    if not settings.exists():
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text("instrumentalPercent: 50\n", encoding="utf-8")
    raw = modlist.read_bytes().decode("utf-8-sig")
    lines = [line for line in raw.splitlines() if line not in ("+" + marker, "-" + marker)]
    lines.insert(1 if lines and lines[0].startswith("#") else 0, "+" + marker)
    newline = "\r\n" if "\r\n" in raw else "\n"
    modlist.write_bytes((newline.join(lines) + newline).encode("utf-8"))
    record = {"version": "0.1.0", "root": str(root), "profile": profile, "mod": str(mod),
              "mo2_plugin": str(plugin), "backup": str(backup), "settings": str(settings),
              "source_config_sha256": hashlib.sha256(source_config.read_bytes()).hexdigest()}
    out = project / "local"
    out.mkdir(exist_ok=True)
    (out / "installation.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (backup / "installation.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(project / "README.md", mod / "Solo Lute - Readme.md")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("profile")
    parser.add_argument("--data-mod", default="MGO Experimental - Profile Data")
    args = parser.parse_args()
    install(args.root, args.profile, args.data_mod)
