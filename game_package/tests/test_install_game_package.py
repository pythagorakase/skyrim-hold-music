"""Offline installer proof using the real build and a temporary MO2 installation.

Authored by Codex, running GPT-6.
"""
import codecs
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('install_game_package', ROOT / 'game_package/tools/install_game_package.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
from hold_music.library import Library


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in root.rglob('*')}


class TextEdits(unittest.TestCase):
    def test_encodings_and_newlines(self):
        for encoding, bom in [('utf-8', codecs.BOM_UTF8), ('utf-8', b''),
                              ('utf-16-le', codecs.BOM_UTF16_LE),
                              ('utf-16-be', codecs.BOM_UTF16_BE), ('cp1252', b'')]:
            for newline in ('\r\n', '\n', '\r'):
                with self.subTest(encoding=encoding, newline=newline):
                    raw = bom + ('# café' + newline + '+Other' + newline).encode(encoding)
                    new, _, _, _ = installer.edit_list(raw, 'modlist', 'Example')
                    self.assertEqual(new, bom + ('# café' + newline + '+Example' + newline + '+Other' + newline).encode(encoding))
                    plugins = bom + ('# café' + newline + '*Skyrim.esm').encode(encoding)
                    new, _, _, _ = installer.edit_list(plugins, 'plugins', 'Example')
                    self.assertEqual(new, plugins + (newline + '*HoldMusic.esp' + newline).encode(encoding))

    def test_process_guard(self):
        with patch.object(installer.os, 'name', 'nt'), patch.object(installer.subprocess, 'check_output') as tasklist:
            for name in ('ModOrganizer.exe', 'SkyrimVR.exe', 'SkyrimSE.exe', 'Skyrim.exe'):
                tasklist.return_value = f'"{name}","123","Console","1","100 K"\n'
                with self.assertRaisesRegex(RuntimeError, 'Close Skyrim and MO2'):
                    installer.require_closed()
            tasklist.return_value = '"explorer.exe","123","Console","1","100 K"\n'
            installer.require_closed()
            tasklist.assert_called_with(['tasklist', '/FO', 'CSV', '/NH'], text=True)


class InstallGamePackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / 'game_package/build/package-hashes.json').is_file() or not all(
                (ROOT / 'game_package/build/package' / p).is_file() for p in installer.REQUIRED):
            raise unittest.SkipTest('Build on halcyon: py -3 -B game_package/tools/build_game_package.py; '
                                    'see game_package/README.md Build for T1b staging and copy-back instructions')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / 'repo'
        self.package = self.repo / 'game_package/build/package'
        shutil.copytree(ROOT / 'game_package/build/package', self.package)
        shutil.copy2(ROOT / 'game_package/build/package-hashes.json', self.package.parent)
        (self.repo / 'docs').mkdir()
        shutil.copy2(ROOT / 'docs/game-package-verification.md', self.repo / 'docs')
        shutil.copy2(ROOT / 'game_package/README.md', self.repo / 'game_package')
        self.mo2 = self.base / 'MO2'
        self.profile = self.mo2 / 'profiles/Test Profile'
        (self.profile / 'saves').mkdir(parents=True)
        (self.mo2 / 'mods').mkdir()
        self.mod = self.mo2 / 'mods' / installer.MOD_NAME
        self.modlist = self.profile / 'modlist.txt'
        self.plugins = self.profile / 'plugins.txt'
        self.modlist.write_bytes(codecs.BOM_UTF8 + b'# MO2\r\n+Other\r\n')
        self.plugins.write_bytes(codecs.BOM_UTF8 + b'# Plugins\r\n*Skyrim.esm\r\n')
        for index, name in enumerate(('old', 'new'), 1):
            for ext in ('.ess', '.skse'):
                path = self.profile / 'saves' / (name + ext)
                path.write_bytes((name + ext).encode())
                os.utime(path, (index * 100, index * 100))
        self.library = self.base / 'library'
        wav = self.base / 'source.wav'
        with wave.open(str(wav), 'wb') as stream:
            stream.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            stream.writeframes(b'\x00\x00' * 441)
        for slot in (1, 3):
            Library(self.library).add_recording(wav, performer_id='mikael', region='whiterun',
                mode='instrumental', gender='male', composition_id=f'test-{slot}',
                recipe_id='whiterun/instrumental', model_id='offline-fixture',
                source={'kind': 'import', 'path_or_request_id': str(wav)}, slot=slot)
        for patcher in (patch.object(installer, 'ROOT', self.repo),
                        patch.object(installer, 'BACKUP_ROOT', self.base / 'backups')):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.guard = patch.object(installer, 'require_closed')
        self.closed = self.guard.start()
        self.addCleanup(self.guard.stop)

    def run_install(self, **kwargs):
        return installer.run(self.mo2, 'Test Profile', library=self.library, **kwargs)

    def test_dry_run_writes_nothing_and_lists_all_operations(self):
        before = snapshot(self.base)
        plan = self.run_install(dry_run=True)
        self.assertEqual(before, snapshot(self.base))
        self.closed.assert_not_called()
        self.assertEqual(len(plan['receipt_destinations']), 2)
        self.assertEqual(len(plan['backups']), 4)
        self.assertEqual({Path(e['path']).name for e in plan['profile_edits']}, {'modlist.txt', 'plugins.txt'})
        self.assertTrue(all(e['edits'] for e in plan['profile_edits']))
        self.assertEqual({Path(e['destination']).relative_to(self.mod).as_posix() for e in plan['files']},
                         set(plan['receipt']['files']))
        json.dumps(plan)

    def test_install_files_backup_receipt_and_idempotence(self):
        before = {p.name: p.read_bytes() for p in (self.modlist, self.plugins)}
        plan = self.run_install()
        self.closed.assert_called_once()
        receipt = json.loads((self.repo / 'local/game-package-install.json').read_text())
        backup = Path(receipt['backup'])
        self.assertEqual(receipt, json.loads((backup / 'game-package-install.json').read_text()))
        required = installer.REQUIRED | {'meta.ini', 'README.md', 'docs/game-package-verification.md',
            installer.JSON_DATA + 'library.json', installer.JSON_DATA + 'receipts.json',
            'Sound/fx/holdmusic/hm_slot_01.wav', 'Sound/fx/holdmusic/hm_slot_03.wav'}
        self.assertTrue(required <= set(receipt['files']))
        self.assertEqual(set(receipt['files']), {p.relative_to(self.mod).as_posix() for p in self.mod.rglob('*') if p.is_file()})
        for entry in plan['files']:
            path = Path(entry['destination'])
            self.assertEqual(installer.sha(path.read_bytes()), entry['sha256'])
            self.assertEqual(entry['sha256'], receipt['files'][path.relative_to(self.mod).as_posix()])
            if entry['source']:
                self.assertEqual(path.read_bytes(), Path(entry['source']).read_bytes())
        for name, data in before.items():
            self.assertEqual((backup / name).read_bytes(), data)
        self.assertEqual({p.name for p in (backup / 'pre-install-save').iterdir()}, {'new.ess', 'new.skse'})
        self.assertEqual((backup / 'pre-install-save/new.ess').read_bytes(), b'new.ess')
        self.assertEqual(receipt['library_manifest_sha256'], installer.sha((self.library / 'library.json').read_bytes()))
        self.assertEqual(json.loads((self.mod / installer.JSON_DATA / 'receipts.json').read_text()),
                         {'version': 1, 'performances': []})
        self.assertEqual(self.modlist.read_bytes(), codecs.BOM_UTF8 +
            ('# MO2\r\n+' + installer.MOD_NAME + '\r\n+Other\r\n').encode())
        self.assertEqual(self.plugins.read_bytes(), before['plugins.txt'] + b'*HoldMusic.esp\r\n')
        stable = self.modlist.read_bytes(), self.plugins.read_bytes()
        (self.mod / 'old-extra.txt').write_text('preserve in backup')
        (self.mod / 'empty').mkdir()
        second = self.run_install()
        self.assertEqual(stable, (self.modlist.read_bytes(), self.plugins.read_bytes()))
        self.assertEqual((Path(second['backup']) / 'content-mod/old-extra.txt').read_text(), 'preserve in backup')
        self.assertTrue((Path(second['backup']) / 'content-mod/empty').is_dir())
        self.assertFalse((self.mod / 'old-extra.txt').exists())

    def test_copy_existing_receipts(self):
        contents = b'{"version": 1, "performances": [], "fixture": true}\r\n'
        (self.library / 'receipts.json').write_bytes(contents)
        self.run_install()
        self.assertEqual((self.mod / installer.JSON_DATA / 'receipts.json').read_bytes(), contents)

    def test_install_write_failure_restores_profile_and_existing_mod(self):
        self.mod.mkdir()
        (self.mod / 'previous.txt').write_bytes(b'previous installation')
        before = snapshot(self.mo2)
        write_bytes = Path.write_bytes

        def fail(path, data):
            if path == self.mod / 'Scripts/HM_Controller.pex':
                raise OSError('simulated write failure')
            return write_bytes(path, data)

        with patch.object(Path, 'write_bytes', fail):
            with self.assertRaisesRegex(OSError, 'simulated write failure'):
                self.run_install()
        self.assertEqual(snapshot(self.mo2), before)
        self.assertFalse((self.repo / 'local/game-package-install.json').exists())

    def test_invalid_library_and_hash_mismatch_write_nothing(self):
        manifest = self.library / 'library.json'
        valid = manifest.read_bytes()
        manifest.write_text('{broken')
        before = snapshot(self.base)
        with self.assertRaisesRegex(ValueError, 'Invalid library'):
            self.run_install()
        self.assertEqual(snapshot(self.base), before)
        manifest.write_bytes(valid)
        (self.package / 'HoldMusic.esp').write_bytes(b'corrupt')
        before = snapshot(self.base)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.run_install()
        self.assertEqual(snapshot(self.base), before)

    def test_missing_artifact_and_incomplete_newest_save_refuse(self):
        pex = self.package / 'Scripts/HM_Controller.pex'
        data = pex.read_bytes()
        pex.unlink()
        before = snapshot(self.base)
        with self.assertRaisesRegex(ValueError, 'inventory mismatch'):
            self.run_install()
        self.assertEqual(snapshot(self.base), before)
        pex.write_bytes(data)
        (self.profile / 'saves/new.skse').unlink()
        before = snapshot(self.base)
        with self.assertRaisesRegex(ValueError, 'complete ESS/SKSE'):
            self.run_install()
        self.assertEqual(snapshot(self.base), before)

    def test_closed_check_refuses_before_writes_and_profile_validation(self):
        self.closed.side_effect = RuntimeError('Close Skyrim and MO2')
        before = snapshot(self.base)
        with self.assertRaisesRegex(RuntimeError, 'Close Skyrim'):
            self.run_install()
        self.assertEqual(snapshot(self.base), before)
        with self.assertRaisesRegex(ValueError, 'profile does not exist'):
            installer.run(self.mo2, 'Missing', library=self.library, dry_run=True)
        for name in ('../outside', '..\\outside', 'mod\n+Other', 'CON'):
            with self.assertRaises(ValueError):
                self.run_install(mod_name=name, dry_run=True)

    def test_prior_entries_removed_and_plugin_enabled_once(self):
        self.modlist.write_bytes(codecs.BOM_UTF8 + ('# MO2\r\n-' + installer.MOD_NAME +
            '\r\n+Other\r\n+' + installer.MOD_NAME + '\r\n').encode())
        self.plugins.write_bytes(b'# Plugins\nHoldMusic.esp\n*Other.esp')
        self.run_install()
        self.assertEqual(self.modlist.read_bytes(), codecs.BOM_UTF8 +
            ('# MO2\r\n+' + installer.MOD_NAME + '\r\n+Other\r\n').encode())
        self.assertEqual(self.plugins.read_bytes(), b'# Plugins\n*Other.esp\n*HoldMusic.esp\n')

    def test_uninstall_keeps_then_purges_and_restores_nothing(self):
        self.run_install()
        saved = snapshot(self.profile / 'saves')
        backups = snapshot(self.base / 'backups')
        contents = snapshot(self.mod)
        before = snapshot(self.base)
        self.run_install(uninstall=True, purge=True, dry_run=True)
        self.assertEqual(snapshot(self.base), before)
        # Uninstall needs neither the build nor the library.
        shutil.rmtree(self.package)
        shutil.rmtree(self.library)
        self.run_install(uninstall=True)
        self.assertEqual(contents, snapshot(self.mod))
        self.assertEqual(self.modlist.read_bytes(), codecs.BOM_UTF8 +
            ('# MO2\r\n-' + installer.MOD_NAME + '\r\n+Other\r\n').encode())
        self.assertEqual(self.plugins.read_bytes(), codecs.BOM_UTF8 + b'# Plugins\r\n*Skyrim.esm\r\n')
        self.run_install(uninstall=True, purge=True)
        self.assertFalse(self.mod.exists())
        self.assertEqual(saved, snapshot(self.profile / 'saves'))
        self.assertEqual(backups, snapshot(self.base / 'backups'))


if __name__ == '__main__':
    unittest.main()
