from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

from tools.preflight_performance import inspect, main
from hold_music.runtime_paths import DEFAULT_MOD_NAME


class PerformancePreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'MO2'
        self.profile = self.root / 'profiles/Test'
        self.mod = self.root / 'mods' / DEFAULT_MOD_NAME
        self.data = self.root / 'mods/Data'
        self.storage = self.mod / 'SKSE/Plugins/StorageUtilData/HoldMusic'
        self.write(self.profile / 'modlist.txt', '+' + DEFAULT_MOD_NAME + '\n+Data\n-Inactive\n')
        self.write(self.profile / 'plugins.txt', '*HoldMusic.esp\n')
        self.config = self.data / 'SKSE/Plugins/SkyrimNet/config/BardSinging.yaml'
        self.write(self.config, 'bard_singing:\n  enabled: false\n  api_key: synthetic-private-key\n')
        self.defaults = self.mod / 'mcm/config/HoldMusic/settings.ini'
        self.write(self.defaults, '[General]\nbEnabled=1\niSessionCap=3\niInstrumentalPercent=50\n')
        for relative in ['HoldMusic.esp', 'SEQ/HoldMusic.seq', 'mcm/config/HoldMusic/config.json',
                         'Scripts/HM_Config.pex', 'Scripts/HM_Controller.pex', 'Scripts/HM_Library.pex']:
            self.write(self.mod / relative, 'fixture-only')
        self.registry = {'schema_version': 2, 'performers': [
            {'id': 'sven', 'owner': 'hold_music', 'region': 'whiterun',
             'form': {'plugin': 'Skyrim.esm', 'id': 123}},
            {'id': 'mikael', 'owner': 'skyrimnet', 'region': 'whiterun'},
        ]}
        self.registry_path = self.mod / 'SKSE/Plugins/HoldMusic/registry.json'
        self.write_json(self.registry_path, self.registry)
        self.audio = self.mod / 'Sound/fx/holdmusic/hm_slot_03.wav'
        self.audio.parent.mkdir(parents=True)
        with wave.open(str(self.audio), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(44100)
            stream.writeframes(b'\0\0' * 441)
        self.manifest = {'version': 1, 'slots': 24, 'recordings': [
            {'slot': 3, 'file': 'hm_slot_03.wav', 'performer_id': 'sven',
             'region': 'whiterun', 'mode': 'instrumental', 'duration_seconds': .01,
             'composition_id': 'fixture', 'playable': False},
        ]}
        self.write_json(self.storage / 'library.json', self.manifest)
        self.write_json(self.storage / 'receipts.json', {'version': 1, 'performances': []})
        self.write_json(self.storage / 'trace.json', {'version': 1, 'entries': []})

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def write_json(self, path, value):
        self.write(path, json.dumps(value))

    def run_check(self):
        return inspect(self.root, 'Test', data_mod='Data')

    def failures(self):
        return {row['code'] for row in self.run_check()['checks'] if not row['passed']}

    def test_prepared_is_read_only_and_does_not_claim_runtime_success(self):
        def state():
            return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}
        before = state()
        report = self.run_check()
        self.assertEqual(before, state())
        self.assertEqual(report['status'], 'prepared_for_headset_test')
        self.assertEqual(report['coverage'], {'registered': 2, 'hold_music_owned': 1})
        self.assertEqual(report['runtime_evidence']['trace.json'][0]['entries'], 0)
        self.assertTrue(report['recordings'][0]['playable'])  # Read the WAV, not the saved flag.
        self.assertNotIn('synthetic-private-key', json.dumps(report))
        self.assertIn('not globals already stored', ' '.join(report['limitations']))

    def test_both_controllers_or_unparseable_bard_setting_block_the_pilot(self):
        for text in ('bard_singing:\n  enabled: true\n',
                     'bard_singing:\n  enabled: "false"\n',
                     'bard_singing:\n  enabled: false\n  enabled: true\n'):
            with self.subTest(text=text):
                self.write(self.config, text)
                self.assertIn('skyrimnet_music_disabled', self.failures())

    def test_overwrite_wins_and_inactive_mod_is_ignored(self):
        rel = 'SKSE/Plugins/SkyrimNet/config/BardSinging.yaml'
        self.write(self.root / 'mods/Inactive' / rel, 'bard_singing:\n  enabled: true\n')
        self.assertEqual(self.run_check()['status'], 'prepared_for_headset_test')
        self.write(self.root / 'overwrite' / rel, 'bard_singing:\n  enabled: true\n')
        self.assertIn('skyrimnet_music_disabled', self.failures())

    def test_mod_priority_and_partial_mcm_override(self):
        self.write(self.profile / 'modlist.txt', '+Higher\n+' + DEFAULT_MOD_NAME + '\n+Data\n')
        self.write(self.root / 'mods/Higher/mcm/settings/HoldMusic.ini', '[General]\nbEnabled=0\n')
        self.assertIn('hold_music_enabled', self.failures())
        self.assertNotIn('performance_settings', self.failures())
        self.write(self.root / 'overwrite/mcm/settings/HoldMusic.ini', '[General]\nbEnabled=1\niSessionCap=0\n')
        self.assertNotIn('hold_music_enabled', self.failures())
        self.assertIn('performance_settings', self.failures())

    def test_pending_overlay_is_not_assumed_to_be_live(self):
        self.write(self.profile / 'hold-music-runtime/BardSinging.baseline.yaml', 'private fixture')
        self.assertIn('overlay_reconciled', self.failures())

    def test_adapter_input_cannot_silently_override_a_disabled_loose_file(self):
        self.write_json(self.root / 'plugins/hold_music_adapter/local.json',
                        {'profile': 'Test', 'mod': DEFAULT_MOD_NAME, 'data_mod': 'Data'})
        self.write(self.config, 'bard_singing:\n  enabled: true\n')
        self.write(self.root / 'overwrite/SKSE/Plugins/SkyrimNet/config/BardSinging.yaml',
                   'bard_singing:\n  enabled: false\n')
        self.assertNotIn('skyrimnet_music_disabled', self.failures())
        self.assertIn('adapter_music_disabled', self.failures())
        self.assertIn('bard_settings_agree', self.failures())
        report = self.run_check()
        self.assertEqual([row['enabled'] for row in report['bard_setting_sources']], [False, True])

    def vfs_report(self, source=None, **changes):
        source = source or self.config
        report = {'version': 2, 'profile': 'Test', 'observed_at': '2026-10-20T05:00:00+00:00',
                  'files': [{'virtual_path': 'SKSE/Plugins/SkyrimNet/config/BardSinging.yaml',
                             'opened_path': str(source), 'bard_enabled': False,
                             'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}
        report.update(changes)
        path = self.root / 'vfs-report.json'
        self.write_json(path, report)
        return path

    def vfs_check(self, path):
        return inspect(self.root, 'Test', data_mod='Data', vfs_report=path)

    def test_vfs_observation_verifies_current_hash_and_profile_without_claiming_injection(self):
        path = self.vfs_report()
        report = self.vfs_check(path)
        self.assertEqual(report['status'], 'prepared_for_headset_test')
        self.assertTrue(report['vfs_evidence']['current_file_matches'])
        self.assertIs(report['vfs_evidence']['bard_enabled'], False)
        self.assertNotIn('synthetic-private-key', json.dumps(report))
        self.assertIn('does not prove injection', ' '.join(report['limitations']))
        self.write(self.config, 'bard_singing:\n  enabled: true\n')
        report = self.vfs_check(path)
        self.assertFalse(report['vfs_evidence']['current_file_matches'])
        self.assertFalse(next(row for row in report['checks']
                              if row['code'] == 'vfs_observed_bard_disabled')['passed'])
        for changes in ({'profile': 'Other'}, {'version': 1}, {'observed_at': '2026-10-20'}):
            path = self.vfs_report(**changes)
            report = self.vfs_check(path)
            self.assertFalse(next(row for row in report['checks']
                                  if row['code'] == 'vfs_observed_bard_disabled')['passed'])

    def test_vfs_disabled_overlay_does_not_clear_fallback_conflict(self):
        self.write(self.config, 'bard_singing:\n  enabled: true\n')
        overlay = self.profile / 'hold-music-runtime/BardSinging.yaml'
        self.write(overlay, 'bard_singing:\n  enabled: false\n')
        report = self.vfs_check(self.vfs_report(source=overlay))
        checks = {row['code']: row['passed'] for row in report['checks']}
        self.assertTrue(checks['vfs_observed_bard_disabled'])
        self.assertFalse(checks['skyrimnet_music_disabled'])
        self.assertEqual(report['status'], 'blocked')

    def test_vfs_rejects_unrelated_destination_or_duplicate_observation(self):
        unrelated = self.root / 'profiles/Other/hold-music-runtime/BardSinging.yaml'
        self.write(unrelated, 'bard_singing:\n  enabled: false\n')
        report = self.vfs_check(self.vfs_report(source=unrelated))
        self.assertFalse(next(row for row in report['checks']
                              if row['code'] == 'vfs_observed_bard_disabled')['passed'])
        path = self.vfs_report()
        value = json.loads(path.read_text())
        value['files'].append(value['files'][0])
        self.write_json(path, value)
        report = self.vfs_check(path)
        self.assertFalse(next(row for row in report['checks']
                              if row['code'] == 'vfs_observed_bard_disabled')['passed'])

    def test_vfs_accepts_windows_extended_handle_path(self):
        path = self.vfs_report()
        value = json.loads(path.read_text())
        value['files'][0]['opened_path'] = '\\\\?\\' + str(self.config)
        self.write_json(path, value)
        report = self.vfs_check(path)
        self.assertTrue(next(row for row in report['checks']
                             if row['code'] == 'vfs_observed_bard_disabled')['passed'])

    def test_disabled_plugin_or_missing_startup_file_blocks(self):
        self.write(self.profile / 'plugins.txt', 'HoldMusic.esp\n')
        self.assertIn('package_enabled', self.failures())
        (self.mod / 'SEQ/HoldMusic.seq').unlink()
        self.assertIn('package_files', self.failures())

    def test_wrong_owner_or_region_does_not_claim_a_playable_pilot(self):
        self.registry['performers'][0]['owner'] = 'skyrimnet'
        self.write_json(self.registry_path, self.registry)
        self.assertIn('performer_owned', self.failures())
        self.registry['performers'][0]['owner'] = 'hold_music'
        self.registry['performers'][0]['region'] = 'rift'
        self.write_json(self.registry_path, self.registry)
        self.assertIn('matching_recording', self.failures())

    def test_missing_truncated_and_wrong_duration_audio_block(self):
        valid = self.audio.read_bytes()
        self.audio.unlink()
        self.assertIn('slot_03', self.failures())
        self.audio.write_bytes(valid[:-2])
        self.assertIn('slot_03', self.failures())
        self.audio.write_bytes(valid)
        self.manifest['recordings'][0]['duration_seconds'] = 1
        self.write_json(self.storage / 'library.json', self.manifest)
        self.assertIn('slot_03', self.failures())

    def test_duplicate_slots_and_path_escape_are_rejected(self):
        self.manifest['recordings'].append(dict(self.manifest['recordings'][0]))
        self.write_json(self.storage / 'library.json', self.manifest)
        self.assertIn('matching_recording', self.failures())
        self.manifest['recordings'].pop()
        self.manifest['recordings'][0]['file'] = '../../../private.wav'
        self.write_json(self.storage / 'library.json', self.manifest)
        self.assertIn('slot_03', self.failures())

    def test_corrupt_runtime_json_is_distinct_from_no_performance(self):
        self.write(self.storage / 'trace.json', '{partial')
        self.assertIn('trace.json', self.failures())
        self.assertNotIn('receipts.json', self.failures())

    def test_cli_status_and_invalid_profile(self):
        args = ['--mo2-root', str(self.root), '--profile', 'Test', '--data-mod', 'Data', '--json']
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(out.getvalue())['status'], 'prepared_for_headset_test')
        self.audio.unlink()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 2)
        with self.assertRaises(ValueError):
            inspect(self.root, '../Test')


if __name__ == '__main__':
    unittest.main()
