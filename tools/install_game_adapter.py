"""Install Hold Music in one MO2 profile, with Skyrim and MO2 closed.

Backs up every existing target. Retires Solo Lute only in this profile and
preserves source provider routing, song caches, memories, and game plugins.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'game_adapter/hold_music_adapter'))
from engine import ConfigOverlay, MODEL, get_scalar, read_text
from build_game_adapter import build


def require_closed():
    if os.name != 'nt':
        raise RuntimeError('This installer targets the Windows MO2 game setup')
    output = subprocess.check_output(['tasklist', '/FO', 'CSV', '/NH'], text=True)
    names = {row[0].lower() for row in csv.reader(io.StringIO(output)) if row}
    if names & {'modorganizer.exe', 'skyrimvr.exe', 'skyrimse.exe', 'skyrim.exe'}:
        raise RuntimeError('Close Skyrim and MO2 before installing')


def child(root, relative):
    path = (root/relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Installation path must remain within MO2')
    return path


def install(root, profile, data_mod, game_data):
    require_closed()
    root = Path(root).resolve()
    for name in (profile, data_mod):
        if not name or Path(name).name != name or name in ('.', '..'):
            raise ValueError('Expected a single profile or mod directory name')
    profile_dir = child(root, Path('profiles')/profile)
    modlist = profile_dir/'modlist.txt'
    data = child(root, Path('mods')/data_mod)/'SKSE/Plugins/SkyrimNet'
    config = data/'config/BardSinging.yaml'
    raw = modlist.read_bytes().decode('utf-8-sig')
    if '+'+data_mod not in raw.splitlines():
        raise RuntimeError('The isolated profile data mod must be enabled')
    if get_scalar(read_text(config), ('bard_singing', 'provider')) != 'openrouter':
        raise RuntimeError('Hold Music expects the existing OpenRouter provider')
    if get_scalar(read_text(config), ('bard_singing', 'openrouter', 'model')) != MODEL:
        raise RuntimeError('Unexpected music model; no changes made')
    if not Path(game_data).is_dir():
        raise ValueError('Game Data directory is missing')
    marker = 'MGO Experimental - Hold Music'
    plugin = child(root, 'plugins/hold_music_adapter')
    mod = child(root, Path('mods')/marker)
    settings = data/'config/plugins/HoldMusic/settings.yaml'
    prior = data/'config/plugins/SoloLute/settings.yaml'
    percent = get_scalar(read_text(settings if settings.exists() else prior), ('instrumentalPercent',)) if settings.exists() or prior.exists() else 50
    if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
        raise ValueError('Invalid instrumental chance in existing settings')
    backup = root.parent/'codex-backups'/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-hold-music')
    backup.mkdir(parents=True, exist_ok=False)
    for source, name in ((modlist, 'modlist.txt'), (config, 'BardSinging.yaml'), (settings, 'settings.yaml')):
        if source.exists():
            shutil.copy2(source, backup/name)
    for source, name in ((plugin, 'mo2-plugin'), (mod, 'content-mod')):
        if source.exists():
            shutil.copytree(source, backup/name)
    for runtime_name in ('solo-lute-runtime', 'hold-music-runtime'):
        runtime = profile_dir/runtime_name
        if runtime.exists():
            shutil.copytree(runtime, backup/runtime_name)
        # Recover dashboard edits only after preserving their inputs.
        ConfigOverlay(config, runtime).reconcile()
    build()
    shutil.copytree(ROOT/'game_adapter/hold_music_adapter', plugin, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'local.json'))
    shutil.copytree(ROOT/'game_adapter/content', mod, dirs_exist_ok=True)
    (mod/'SKSE/Plugins/SkyrimNet/external/local.hold-music/prompts').mkdir(exist_ok=True)
    python = Path(sys.executable).resolve()
    if python.with_name('pythonw.exe').is_file():
        python = python.with_name('pythonw.exe')
    local = {'profile': profile, 'data_mod': data_mod, 'mod': marker, 'port': 0, 'python': str(python)}
    (plugin/'local.json').write_text(json.dumps(local, indent=2)+'\n', encoding='utf-8')
    (mod/'meta.ini').write_text('[General]\nmodid=0\nversion=0.2.0\ncategory=0\nnotes=Hold Music regional composition pilot; requires its MO2 companion.\n', encoding='utf-8')
    shutil.copy2(ROOT/'docs/game-adapter.md', mod/'Hold Music - Readme.md')
    shutil.copy2(ROOT/'docs/game-adapter-verification.md', mod/'game-adapter-verification.md')
    if not settings.exists():
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(f'instrumentalPercent: {percent}\n', encoding='utf-8')
    old_seed = profile_dir/'solo-lute-runtime/mode-seed.txt'
    new_seed = profile_dir/'hold-music-runtime/mode-seed.txt'
    if old_seed.is_file() and not new_seed.exists():
        new_seed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_seed, new_seed)
    lines = [('-MGO Experimental - Solo Lute' if line == '+MGO Experimental - Solo Lute' else line)
             for line in raw.splitlines() if line not in ('+'+marker, '-'+marker)]
    lines.insert(1 if lines and lines[0].startswith('#') else 0, '+'+marker)
    newline = '\r\n' if '\r\n' in raw else '\n'
    modlist.write_bytes((newline.join(lines)+newline).encode('utf-8'))
    record = {'version': '0.2.0', 'root': str(root), 'profile': profile, 'data_mod': data_mod,
              'game_data': str(Path(game_data).resolve()), 'mod': str(mod), 'mo2_plugin': str(plugin),
              'backup': str(backup), 'settings': str(settings),
              'source_config_sha256': hashlib.sha256(config.read_bytes()).hexdigest()}
    (ROOT/'local').mkdir(exist_ok=True)
    for path in (ROOT/'local/installation.json', backup/'installation.json'):
        path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('profile')
    parser.add_argument('--data-mod', default='MGO Experimental - Profile Data')
    parser.add_argument('--game-data', required=True)
    args = parser.parse_args()
    install(args.root, args.profile, args.data_mod, args.game_data)
