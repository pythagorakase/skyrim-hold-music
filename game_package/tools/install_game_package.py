"""Install or disable Hold Music in one closed MO2 profile; dry runs never write.

Authored by Codex, running GPT-6.
"""
import sys

# Set this before any other import: plain CLI dry runs create no bytecode.
sys.dont_write_bytecode = True

import argparse
import codecs
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hold_music.library import Library

VERSION = '0.1.0'
BACKUP_ROOT = Path(r'C:\MGO\codex-backups')
MOD_NAME = 'MGO Experimental - Hold Music Performances'
DATA_MOD = 'MGO Experimental - Profile Data'
JSON_DATA = 'SKSE/Plugins/StorageUtilData/HoldMusic/'
REQUIRED = {
    'HoldMusic.esp', 'SEQ/HoldMusic.seq',
    'mcm/config/HoldMusic/config.json', 'mcm/config/HoldMusic/settings.ini',
    'SKSE/Plugins/HoldMusic/registry.json',
    *('Scripts/' + name + '.pex' for name in ('HM_Config', 'HM_Controller', 'HM_Library')),
    *('Scripts/Source/' + name + '.psc' for name in ('HM_Config', 'HM_Controller', 'HM_Library')),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require_closed():
    if os.name != 'nt':
        raise RuntimeError('This installer targets the Windows MO2 game setup')
    output = subprocess.check_output(['tasklist', '/FO', 'CSV', '/NH'], text=True)
    names = {row[0].lower() for row in csv.reader(io.StringIO(output)) if row}
    if names & {'modorganizer.exe', 'skyrimvr.exe', 'skyrimse.exe', 'skyrim.exe'}:
        raise RuntimeError('Close Skyrim and MO2 before installing or uninstalling')


def directory_name(name):
    if (not name or name in ('.', '..') or name[-1:] in (' ', '.')
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
        raise ValueError('Expected a single Windows profile or mod directory name')
    return name


def child(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path must remain within ' + str(root))
    return path


def text_format(raw):
    for bom, encoding in ((codecs.BOM_UTF8, 'utf-8'),
                          (codecs.BOM_UTF16_LE, 'utf-16-le'),
                          (codecs.BOM_UTF16_BE, 'utf-16-be')):
        if raw.startswith(bom):
            return bom, encoding, raw[len(bom):].decode(encoding)
    try:
        return b'', 'utf-8', raw.decode('utf-8')
    except UnicodeDecodeError:
        # MO2 may use the Windows Western code page; byte round-trip is exact.
        return b'', 'cp1252', raw.decode('cp1252')


def edit_list(raw, kind, mod_name, uninstall=False):
    """Keep unrelated lines, BOM, encoding, and individual line endings intact."""
    bom, encoding, text = text_format(raw)
    match = re.search(r'\r\n|\n|\r', text)
    newline = match[0] if match else '\r\n'
    lines = text.splitlines(keepends=True)
    edits = []

    def body(line):
        return line.rstrip('\r\n')

    if kind == 'modlist':
        matches = [i for i, line in enumerate(lines)
                   if body(line)[:1] in ('+', '-') and body(line)[1:].casefold() == mod_name.casefold()]
        position = matches[0] if uninstall and matches else (1 if lines and lines[0].startswith('#') else 0)
        for i in reversed(matches):
            edits.append({'action': 'remove', 'line': i + 1, 'text': body(lines[i])})
            del lines[i]
        position = min(position, len(lines))
        value = ('-' if uninstall else '+') + mod_name
        if position and not lines[position - 1].endswith(('\r', '\n')):
            lines[position - 1] += newline
            edits.append({'action': 'terminate_line', 'line': position, 'newline': newline})
        lines.insert(position, value + newline)
        edits.append({'action': 'insert', 'line': position + 1, 'text': value, 'newline': newline})
    else:
        matches = [i for i, line in enumerate(lines)
                   if body(line).lstrip('*').casefold() == 'holdmusic.esp']
        if not uninstall and any(body(lines[i]).startswith('*') for i in matches):
            # Keep the first enabled entry and remove any duplicate entries.
            keep = next(i for i in matches if body(lines[i]).startswith('*'))
        else:
            keep = None
        for i in reversed(matches):
            if i != keep and (not uninstall or body(lines[i]).startswith('*')):
                edits.append({'action': 'remove', 'line': i + 1, 'text': body(lines[i])})
                del lines[i]
        if not uninstall and keep is None:
            if lines and not lines[-1].endswith(('\r', '\n')):
                lines[-1] += newline
                edits.append({'action': 'terminate_line', 'line': len(lines), 'newline': newline})
            lines.append('*HoldMusic.esp' + newline)
            edits.append({'action': 'append', 'line': len(lines), 'text': '*HoldMusic.esp', 'newline': newline})
    return bom + ''.join(lines).encode(encoding), edits, encoding, bom.hex()


def run(root, profile, *, library=None, data_mod=DATA_MOD, mod_name=MOD_NAME,
        dry_run=False, uninstall=False, purge=False):
    if purge and not uninstall:
        raise ValueError('--purge requires --uninstall')
    if not dry_run:
        require_closed()
    root = Path(root).resolve()
    for name in (profile, mod_name, data_mod):
        directory_name(name)
    profile_dir = child(root, Path('profiles') / profile)
    if not profile_dir.is_dir():
        raise ValueError('MO2 profile does not exist: ' + str(profile_dir))
    mods = child(root, 'mods')
    mod = child(mods, mod_name)
    # Never traverse an aliased mod directory when replacing or purging it.
    if mod != mods / mod_name:
        raise ValueError('Target mod must not be a symlink or junction')
    edits, updated, original = [], {}, {}
    for name, kind in (('modlist.txt', 'modlist'), ('plugins.txt', 'plugins')):
        path = child(profile_dir, name)
        original[path] = path.read_bytes()
        new, changes, encoding, bom = edit_list(original[path], kind, mod_name, uninstall)
        updated[path] = new
        edits.append({'path': str(path), 'encoding': encoding, 'bom_hex': bom,
                      'before_sha256': sha(original[path]), 'after_sha256': sha(new), 'edits': changes})
    plan = {'operation': 'uninstall' if uninstall else 'install', 'dry_run': dry_run,
            'version': VERSION, 'root': str(root), 'profile': str(profile_dir),
            'mod': str(mod), 'data_mod': data_mod, 'profile_edits': edits,
            'purge': bool(purge), 'files': [], 'backups': []}
    if uninstall:
        plan['remove_tree'] = str(mod) if purge and mod.exists() else None
        if not dry_run:
            for path, new in updated.items():
                path.write_bytes(new)
            if purge and mod.exists():
                shutil.rmtree(mod)
        return plan

    package = ROOT / 'game_package/build/package'
    hashes = json.loads((package.parent / 'package-hashes.json').read_text(encoding='utf-8-sig'))
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()}
    if not isinstance(hashes, dict) or not REQUIRED <= set(hashes) or actual != set(hashes):
        raise ValueError('Package inventory mismatch; build and retrieve game_package/build first')
    payloads = {}

    def add(source, relative, content=None):
        dest = child(mod, relative)
        data = content if content is not None else Path(source).read_bytes()
        entry = {'source': str(source) if source is not None else None,
                 'destination': str(dest), 'sha256': sha(data)}
        if source is None:
            entry['content'] = data.decode('utf-8')
        plan['files'].append(entry)
        payloads[dest] = data

    for relative, digest in sorted(hashes.items()):
        source = child(package.resolve(), relative)
        data = source.read_bytes()
        if sha(data) != digest:
            raise ValueError('Package hash mismatch: ' + relative)
        add(source, relative, data)
    if library is None:
        raise ValueError('--library is required for installation')
    library = Path(library).resolve()
    if not library.is_dir() or not (library / 'library.json').is_file():
        raise ValueError('Invalid library: library.json is required')
    lib = Library(library)
    problems = lib.validate()
    if problems:
        raise ValueError('Invalid library: ' + '; '.join(problems))
    add(library / 'library.json', JSON_DATA + 'library.json')
    receipts = library / 'receipts.json'
    if receipts.exists():
        add(receipts, JSON_DATA + 'receipts.json')
    else:
        add(None, JSON_DATA + 'receipts.json', b'{"version": 1, "performances": []}\n')
    for row in lib.recordings:
        add(library / row['file'], 'Sound/fx/holdmusic/' + row['file'])
    add(None, 'meta.ini', ('[General]\nmodid=0\nversion=' + VERSION +
        '\ncategory=0\nnotes=Hold Music owned performances; runtime and VFS verification pending.\n').encode())
    add(ROOT / 'game_package/README.md', 'README.md')
    add(ROOT / 'docs/game-package-verification.md', 'docs/game-package-verification.md')

    # Match Modern Marriage: newest ESS, then require its matching co-save.
    saves = list((profile_dir / 'saves').glob('*.ess'))
    if not saves:
        raise ValueError('Expected a complete ESS/SKSE save pair; no ESS saves found')
    save = max(saves, key=lambda p: (p.stat().st_mtime_ns, p.name))
    if not save.with_suffix('.skse').is_file():
        raise ValueError('Expected a complete ESS/SKSE save pair: ' + save.name)
    backup = BACKUP_ROOT / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-hold-music-performances')

    def backup_file(source, relative):
        plan['backups'].append({'source': str(source), 'destination': str(backup / relative),
                                'sha256': sha(source.read_bytes())})

    for path in original:
        backup_file(path, path.name)
    if mod.exists():
        if not mod.is_dir():
            raise ValueError('Target mod is not a directory')
        for path in sorted(mod.rglob('*')):
            if path.is_symlink() or not path.resolve().is_relative_to(mod):
                raise ValueError('Existing mod contains a symlink or junction: ' + str(path))
            if path.is_file():
                backup_file(path, Path('content-mod') / path.relative_to(mod))
    for path in (save, save.with_suffix('.skse')):
        backup_file(path, Path('pre-install-save') / path.name)
    plan.update(library=str(library), backup=str(backup),
                existing_mod_backup=str(backup / 'content-mod') if mod.exists() else None,
                replace_existing_mod=mod.exists())
    receipt = {'receipt_version': 1, 'version': VERSION, 'library_version': lib.manifest['version'],
               'installed_at': datetime.now().astimezone().isoformat(),
               'root': str(root), 'profile': str(profile_dir), 'mod': str(mod),
               'data_mod': data_mod, 'library': str(library), 'package': str(package),
               'backup': str(backup), 'library_manifest_sha256': sha((library / 'library.json').read_bytes()),
               'package_hashes_sha256': sha((package.parent / 'package-hashes.json').read_bytes()),
               'files': {str(p.relative_to(mod).as_posix()): sha(data) for p, data in payloads.items()},
               'profile_edits': edits, 'backups': plan['backups']}
    receipt_paths = (ROOT / 'local/game-package-install.json', backup / 'game-package-install.json')
    plan['receipt_destinations'] = list(map(str, receipt_paths))
    plan['receipt'] = receipt
    if dry_run:
        return plan

    # All validation precedes any writes. Preserve the old mod in full, including
    # empty directories, before replacing it so stale slot audio cannot survive.
    backup.mkdir(parents=True, exist_ok=False)
    for entry in plan['backups']:
        dest = Path(entry['destination'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry['source'], dest)
        if sha(dest.read_bytes()) != entry['sha256']:
            raise RuntimeError('Backup verification failed: ' + str(dest))
    existed = mod.exists()
    if existed:
        shutil.copytree(mod, backup / 'content-mod', dirs_exist_ok=True)
    try:
        if existed:
            shutil.rmtree(mod)
        for dest, data in payloads.items():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            if sha(dest.read_bytes()) != sha(data):
                raise RuntimeError('Installed hash mismatch: ' + str(dest))
        for path, new in updated.items():
            path.write_bytes(new)
        for path in receipt_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    except Exception:
        # An ordinary install failure restores only the installation targets.
        # Explicit --uninstall intentionally never restores backups or saves.
        for path, old in original.items():
            path.write_bytes(old)
        if mod.exists():
            shutil.rmtree(mod)
        if existed:
            shutil.copytree(backup / 'content-mod', mod)
        raise
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('profile')
    parser.add_argument('--library')
    parser.add_argument('--data-mod', default=DATA_MOD)
    parser.add_argument('--mod-name', default=MOD_NAME)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--purge', action='store_true')
    args = parser.parse_args()
    try:
        result = run(**vars(args))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
