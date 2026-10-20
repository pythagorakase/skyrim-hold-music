import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.installed_library import (
    AUDIO_PATH, MANIFEST_PATH, RECEIPTS_PATH, STORAGE_PATH, TRACE_PATH,
    inspect_installed_library,
)
from hold_music.runtime_contract import runtime_identity_key


class InstalledLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'MO2'
        self.profile = self.root / 'profiles/Pilot'
        self.high = self.root / 'mods/High'
        self.low = self.root / 'mods/Low'
        self.high.mkdir(parents=True)
        self.low.mkdir(parents=True)
        self.write(self.profile / 'modlist.txt', b'# generated profile\n+High\n+Low\n-Disabled\n')
        self.words = b'A private fixture song.\n'
        self.row = dict(slot=1, file='hm_slot_01.wav', performer_id='sven', region='whiterun',
                        mode='vocal', gender='male', composition_id='fixture-composition',
                        recipe_id='legacy/filing-label', model_id='unknown', duration_seconds=.01,
                        lyrics_sha256=hashlib.sha256(self.words).hexdigest(), playable=True,
                        source=dict(kind='import', path_or_request_id='fixture', sha256='0' * 64),
                        created_at='2026-10-20T00:00:00Z')
        self.manifest = dict(version=1, slots=24, recordings=[self.row])
        self.json(self.low / MANIFEST_PATH, self.manifest)
        self.json(self.low / RECEIPTS_PATH, dict(version=1, performances=[]))
        self.write(self.high / STORAGE_PATH / 'hm_slot_01.lyrics.txt', self.words)
        self.wav(self.low / AUDIO_PATH / 'hm_slot_01.wav')

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def json(self, path, value):
        self.write(path, json.dumps(value).encode('utf-8'))

    def wav(self, path, frames=441, sample=0):
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), 'wb') as stream:
            stream.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            stream.writeframes(sample.to_bytes(2, 'little', signed=True) * frames)

    def inspect(self, **kwargs):
        return inspect_installed_library(self.root, 'Pilot', **kwargs)

    def codes(self, report):
        return {item['code'] for item in report['blockers']}

    def receipt(self, slot=2, identifier='heard'):
        return dict(id=identifier, performer_id='sven', composition_id='fixture-composition',
                    save_id='save', world_id='world', at_hours=12, slot=slot, outcome='completed')

    def capture(self, rows=None, **updates):
        if rows is None:
            rows = []
            for virtual, path in (
                (MANIFEST_PATH, self.low / MANIFEST_PATH),
                (RECEIPTS_PATH, self.low / RECEIPTS_PATH),
                (AUDIO_PATH + '/hm_slot_01.wav', self.low / AUDIO_PATH / 'hm_slot_01.wav'),
                (STORAGE_PATH + '/hm_slot_01.lyrics.txt', self.high / STORAGE_PATH / 'hm_slot_01.lyrics.txt'),
            ):
                rows.append(dict(virtual_path=virtual, opened_path=str(path),
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(), exists=True, required=False))
        value = dict(version=2, profile='Pilot', observed_at='2026-10-20T00:00:00Z', files=rows)
        value.update(updates)
        path = self.base / 'capture.json'
        self.json(path, value)
        return path

    def test_split_winners_read_only_and_legacy_identity_unchanged(self):
        before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.root.rglob('*') if path.is_file()}
        report = self.inspect()
        self.assertEqual(report['status'], 'inspected')
        self.assertEqual(report['manifest'], self.manifest)
        self.assertTrue(report['recordings'][0]['playable'])
        self.assertEqual(report['recordings'][0]['audio']['path'], str(self.low / AUDIO_PATH / 'hm_slot_01.wav'))
        self.assertEqual(report['recordings'][0]['lyrics']['path'], str(self.high / STORAGE_PATH / 'hm_slot_01.lyrics.txt'))
        self.assertNotIn('recipe_revision', report['recordings'][0]['metadata'])
        self.assertNotIn('private fixture song', json.dumps(report))
        self.assertTrue(all(report[key] is False for key in ('installed', 'vfs_verified', 'runtime_verified', 'writes_performed')))
        self.assertEqual(before, {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                                 for path in self.root.rglob('*') if path.is_file()})
        self.assertFalse((self.root / 'overwrite').exists())
        self.assertEqual(report['review_token'], self.inspect()['review_token'])

    def test_priority_wins_over_newer_mtime_and_all_candidates_retained(self):
        high_audio = self.high / AUDIO_PATH / 'hm_slot_01.wav'
        self.wav(high_audio, sample=1)
        os.utime(high_audio, (1, 1))
        overwrite = self.root / 'overwrite' / RECEIPTS_PATH
        self.json(overwrite, dict(version=1, performances=[self.receipt()]))
        os.utime(overwrite, (1, 1))
        self.write(self.high / AUDIO_PATH / 'hm_slot_03.wav', b'orphan-preserved')
        report = self.inspect()
        self.assertEqual(report['recordings'][0]['audio']['path'], str(high_audio))
        self.assertEqual(report['history']['performance_count'], 1)
        reserved = {item['slot']: item['reasons'] for item in report['reservations']}
        self.assertIn('receipt_at_or_after_boundary', reserved[2])
        self.assertIn('existing_audio', reserved[3])
        self.assertEqual(report['orphans'][0]['slot'], 3)
        self.assertTrue(report['files'][AUDIO_PATH + '/hm_slot_01.wav']['shadowed_conflict'])
        candidates = report['files'][MANIFEST_PATH]['candidates']
        self.assertEqual([item['exists'] for item in candidates], [False, False, True])
        self.assertEqual([item['layer'] for item in candidates], ['overwrite', 'High', 'Low'])

    def test_missing_or_malformed_high_winner_never_falls_back(self):
        self.write(self.root / 'overwrite' / MANIFEST_PATH, b'{"invalid":true}')
        report = self.inspect()
        self.assertIn('invalid_manifest', self.codes(report))
        self.assertEqual(report['manifest'], {'invalid': True})
        self.assertEqual(report['recordings'], [])
        self.write(self.root / 'overwrite' / MANIFEST_PATH, b'not-json')
        report = self.inspect()
        self.assertIn('invalid_json', self.codes(report))
        self.assertIsNone(report['manifest'])

    def test_optional_base_data_is_last_layer(self):
        game = self.base / 'Game/Data'
        self.json(game / MANIFEST_PATH, self.manifest)
        self.wav(game / AUDIO_PATH / 'hm_slot_01.wav', sample=2)
        (self.low / MANIFEST_PATH).unlink()
        report = self.inspect(game_data=game)
        self.assertEqual(report['layers'][-1]['kind'], 'game_data')
        self.assertEqual(report['files'][MANIFEST_PATH]['winner']['path'], str(game / MANIFEST_PATH))
        self.assertEqual(report['recordings'][0]['audio']['path'], str(self.low / AUDIO_PATH / 'hm_slot_01.wav'))
        with self.assertRaises(ValueError):
            self.inspect(game_data=self.low)

    def test_duplicate_profile_entries_and_missing_active_directory(self):
        self.write(self.profile / 'modlist.txt', b'+High\n+Low\n+low\n+Missing\n')
        report = self.inspect()
        self.assertIn('duplicate_mod_entry', self.codes(report))
        self.assertIn('missing_active_directory', self.codes(report))
        self.assertTrue(report['recordings'][0]['playable'])

    def test_active_separator_is_a_directory_name_not_comment(self):
        name = '#End Of List_separator'
        (self.root / 'mods' / name).mkdir()
        self.write(self.profile / 'modlist.txt', ('+' + name + '\n+High\n+Low\n').encode())
        report = self.inspect()
        self.assertEqual(report['status'], 'inspected')
        self.assertEqual(report['layers'][1]['name'], name)

    def test_standard_unmanaged_markers_are_informational_not_mod_directories(self):
        self.write(self.profile / 'modlist.txt',
                   b'+High\n+Low\n*DLC: Dawnguard\n*Creation Club: fixture\n*Unmanaged: loose-item\n')
        report = self.inspect()
        self.assertEqual(report['status'], 'inspected')
        self.assertEqual(len(report['layers']), 3)
        self.assertEqual([row['kind'] for row in report['unmanaged_entries']],
                         ['DLC', 'Creation Club', 'Unmanaged'])
        self.assertIn('base_data_omitted', {row['code'] for row in report['warnings']})
        self.assertIn('coverage is omitted', ' '.join(report['limitations']))
        self.write(self.profile / 'modlist.txt', b'+High\n+Low\n*Unknown: fixture\n')
        self.assertIn('invalid_modlist', self.codes(self.inspect()))

    def test_valid_assets_do_not_override_disabled_playable_metadata(self):
        self.row['playable'] = False
        self.json(self.low / MANIFEST_PATH, self.manifest)
        recording = self.inspect()['recordings'][0]
        self.assertTrue(recording['asset_valid'])
        self.assertFalse(recording['playable'])
        self.assertFalse(recording['metadata']['playable'])

    def test_component_lookup_accepts_unique_case_aliases(self):
        self.write(self.profile / 'modlist.txt', b'+hIGH\n+lOW\n')
        original = self.low / 'Sound'
        temporary = self.low / 'rename-for-case'
        original.rename(temporary)
        temporary.rename(self.low / 'sound')
        report = self.inspect()
        self.assertEqual(report['status'], 'inspected')
        self.assertEqual(report['recordings'][0]['audio']['path'], str(self.low / 'sound/fx/holdmusic/hm_slot_01.wav'))

    def test_ambiguous_case_directories_rejected_on_case_sensitive_filesystems(self):
        other = self.low / 'sound'
        if other.exists():
            self.skipTest('Filesystem does not allow distinct case aliases')
        other.mkdir()
        with self.assertRaisesRegex(ValueError, 'Ambiguous case-insensitive'):
            self.inspect()

    def test_source_aliases_and_unsafe_profile_rejected(self):
        for name in ('../Pilot', 'Pilot.', 'CON', 'Pilot/child'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect_installed_library(self.root, name)
        link = self.low / AUDIO_PATH / 'hm_slot_02.wav'
        try:
            link.symlink_to(self.low / AUDIO_PATH / 'hm_slot_01.wav')
        except OSError:
            self.skipTest('Symlink creation unavailable')
        with self.assertRaises(ValueError):
            self.inspect()

    def test_hardlinked_audio_rejected(self):
        original = self.low / AUDIO_PATH / 'hm_slot_01.wav'
        link = self.base / 'audio-alias.wav'
        try:
            os.link(original, link)
        except OSError:
            self.skipTest('Hard links unavailable')
        with self.assertRaisesRegex(ValueError, 'unaliased'):
            self.inspect()

    def test_receipt_boundary_reserved_slots_and_orphans(self):
        self.json(self.root / 'overwrite' / RECEIPTS_PATH,
                  dict(version=1, performances=[self.receipt(2), self.receipt(3, 'later')]))
        self.manifest.update(locked_slots=[4], reserved_slots=[5])
        self.row['session_locked'] = True
        self.json(self.low / MANIFEST_PATH, self.manifest)
        report = self.inspect(session_receipt_index=1)
        reserved = {item['slot']: item['reasons'] for item in report['reservations']}
        self.assertNotIn(2, reserved)
        self.assertIn('receipt_at_or_after_boundary', reserved[3])
        self.assertIn('manifest_session_lock', reserved[1])
        self.assertIn('locked_slots', reserved[4])
        self.assertIn('reserved_slots', reserved[5])
        self.assertIn('invalid_session_boundary', self.codes(self.inspect(session_receipt_index=3)))
        for invalid in (True, -1, '1'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.inspect(session_receipt_index=invalid)

    def test_missing_receipts_is_explicitly_distinguished_from_empty(self):
        (self.low / RECEIPTS_PATH).unlink()
        report = self.inspect()
        self.assertEqual(report['status'], 'inspected')
        self.assertFalse(report['history']['receipts_present'])
        self.assertEqual(report['history']['performance_count'], 0)

    def test_strict_json_and_history_duplicates_block(self):
        self.write(self.low / MANIFEST_PATH, b'{"version":1,"slots":24,"recordings":[],"recordings":[]}')
        self.assertIn('invalid_json', self.codes(self.inspect()))
        self.json(self.low / MANIFEST_PATH, self.manifest)
        self.json(self.low / RECEIPTS_PATH, dict(version=1, performances=[self.receipt(), self.receipt()]))
        self.assertIn('invalid_history', self.codes(self.inspect()))
        self.write(self.low / RECEIPTS_PATH, b'{"version":1,"performances":[],"extra":1e999}')
        self.assertIn('invalid_json', self.codes(self.inspect()))

    def test_slot_conflicts_and_invalid_metadata_are_not_treated_free(self):
        self.manifest['recordings'].append(dict(self.row))
        self.row['model_id'] = ''
        self.json(self.low / MANIFEST_PATH, self.manifest)
        report = self.inspect()
        self.assertIn('invalid_recording', self.codes(report))
        self.assertIn('duplicate_slot', self.codes(report))
        self.assertNotIn(1, report['unreserved_slots'])

    def test_effective_audio_and_lyrics_validated(self):
        self.wav(self.high / AUDIO_PATH / 'hm_slot_01.wav', frames=100)
        self.write(self.high / STORAGE_PATH / 'hm_slot_01.lyrics.txt', b'different words')
        report = self.inspect()
        self.assertIn('invalid_audio', self.codes(report))
        self.assertIn('invalid_lyrics', self.codes(report))
        self.assertFalse(report['recordings'][0]['playable'])

    def test_malformed_shadowed_json_is_reported_without_displacing_winner(self):
        self.json(self.high / MANIFEST_PATH, self.manifest)
        self.write(self.low / MANIFEST_PATH, b'bad shadow')
        report = self.inspect()
        self.assertEqual(report['status'], 'inspected')
        self.assertEqual(report['manifest'], self.manifest)
        self.assertIn('shadowed_invalid_json', {row['code'] for row in report['warnings']})
        self.assertTrue(report['files'][MANIFEST_PATH]['shadowed_conflict'])

    def test_projected_contract_validated_and_unknown_nullable_legacy_retained(self):
        self.row.update(recipe_revision=None, instrument_family=None, instrument_name=None)
        self.json(self.low / MANIFEST_PATH, self.manifest)
        self.assertEqual(self.inspect()['status'], 'inspected')
        self.row.update(recipe_revision='r1', instrument_family='plucked_string', instrument_name='cittern',
                        arrangement='solo_lute_and_voice', voice='male')
        identity = {key: self.row[key] for key in ('performer_id', 'region', 'recipe_id', 'recipe_revision',
                    'model_id', 'instrument_family', 'instrument_name', 'arrangement', 'mode', 'voice')}
        identity['identity_key'] = runtime_identity_key(identity)
        self.row['identity_key'] = identity['identity_key']
        self.manifest['runtime_selection'] = dict(version=1, contracts=[identity])
        self.json(self.low / MANIFEST_PATH, self.manifest)
        self.assertEqual(self.inspect()['status'], 'inspected')
        self.row['instrument_name'] = 'changed'
        self.json(self.low / MANIFEST_PATH, self.manifest)
        self.assertIn('invalid_runtime_selection', self.codes(self.inspect()))

    def test_snapshot_rejects_new_higher_shadow_during_validation(self):
        from hold_music.library import wav_info as actual

        def change(path):
            self.json(self.root / 'overwrite' / MANIFEST_PATH, self.manifest)
            return actual(path)

        with patch('hold_music.installed_library.wav_info', side_effect=change), \
                self.assertRaisesRegex(ValueError, 'changed during inspection'):
            self.inspect()

    def test_snapshot_rejects_audio_change_even_when_mtime_restored(self):
        from hold_music.library import wav_info as actual

        def change(path):
            result = actual(path)
            target = Path(path)
            info = target.stat()
            data = target.read_bytes()
            target.write_bytes(data[:-2] + b'\x01\x00')
            os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))
            return result

        with patch('hold_music.installed_library.wav_info', side_effect=change), \
                self.assertRaisesRegex(ValueError, 'changed during inspection'):
            self.inspect()

    def test_vfs_capture_matches_selected_current_paths_without_runtime_claim(self):
        report = self.inspect(vfs_report=self.capture())
        self.assertEqual(report['status'], 'inspected')
        self.assertTrue(report['vfs_evidence']['capture_complete'])
        self.assertEqual(len(report['vfs_evidence']['matched']), 4)
        self.assertFalse(report['vfs_verified'])
        self.assertFalse(report['runtime_verified'])
        self.assertFalse(report['installed'])

    def test_legacy_v2_present_capture_without_exists_is_accepted(self):
        path = self.capture()
        data = json.loads(path.read_text())
        for row in data['files']:
            del row['exists']
        self.json(path, data)
        self.assertTrue(self.inspect(vfs_report=path)['vfs_evidence']['capture_complete'])

    def test_vfs_capture_does_not_read_untrusted_opened_path(self):
        path = self.capture()
        data = json.loads(path.read_text())
        outside = self.base / 'outside-private.txt'
        self.write(outside, b'private secret')
        data['files'][0].update(opened_path=str(outside), sha256=hashlib.sha256(b'private secret').hexdigest())
        self.json(path, data)
        real_open = Path.open

        def guarded_open(target, *args, **kwargs):
            if target == outside:
                raise AssertionError('Untrusted capture path was opened')
            return real_open(target, *args, **kwargs)

        with patch.object(Path, 'open', guarded_open):
            report = self.inspect(vfs_report=path)
        self.assertIn('vfs_evidence_path', self.codes(report))
        self.assertFalse(report['vfs_evidence']['capture_complete'])
        self.assertNotIn('private secret', json.dumps(report))

    def test_vfs_capture_lower_priority_hash_and_missing_selected_evidence(self):
        path = self.capture()
        self.wav(self.high / AUDIO_PATH / 'hm_slot_01.wav', sample=4)
        report = self.inspect(vfs_report=path)
        self.assertIn('vfs_evidence_priority', self.codes(report))
        self.assertIn('incomplete_vfs_evidence', self.codes(report))
        self.write(self.high / STORAGE_PATH / 'hm_slot_01.lyrics.txt', b'changed')
        report = self.inspect(vfs_report=path)
        self.assertIn('vfs_evidence_hash', self.codes(report))

    def test_vfs_schema_timestamp_profile_and_virtual_path_guards(self):
        for changes in ({'profile': 'Other'}, {'version': True}, {'observed_at': '2026-10-20'},
                        {'observed_at': '2999-01-01T00:00:00Z'}, {'files': []}):
            with self.subTest(changes=changes):
                report = self.inspect(vfs_report=self.capture(**changes))
                self.assertFalse(report['vfs_evidence']['capture_complete'])
                self.assertTrue(report['blockers'])
        for virtual in ('../outside', '/outside', 'Sound/fx/holdmusic/../private', 'C:/outside'):
            with self.subTest(virtual=virtual):
                report = self.inspect(vfs_report=self.capture(rows=[dict(virtual_path=virtual)]))
                self.assertIn('invalid_vfs_evidence', self.codes(report))
        path = self.capture()
        data = json.loads(path.read_text())
        data['files'].append(dict(data['files'][0]))
        self.json(path, data)
        self.assertIn('invalid_vfs_evidence', self.codes(self.inspect(vfs_report=path)))

    def test_optional_absence_and_out_of_scope_probe_rows_do_not_open_paths(self):
        path = self.capture()
        data = json.loads(path.read_text())
        data['files'].extend([
            dict(virtual_path=TRACE_PATH, exists=False, required=False, error='FileNotFoundError'),
            dict(virtual_path='Scripts/HM_Library.pex', opened_path='C:/untrusted/script', sha256='0' * 64),
        ])
        self.json(path, data)
        report = self.inspect(vfs_report=path)
        self.assertTrue(report['vfs_evidence']['capture_complete'])
        self.assertEqual(report['vfs_evidence']['ignored_paths'], ['Scripts/HM_Library.pex'])

    def test_legacy_v2_optional_missing_reads_do_not_prove_absence_or_block_selected_reads(self):
        path = self.capture()
        data = json.loads(path.read_text())
        data['files'].append(dict(virtual_path=TRACE_PATH, error='FileNotFoundError'))
        self.json(path, data)
        report = self.inspect(vfs_report=path)
        self.assertTrue(report['vfs_evidence']['capture_complete'])
        self.assertNotIn(TRACE_PATH, [row['virtual_path'] for row in report['vfs_evidence']['matched']])

    def test_unexpected_slot_assets_are_visible_and_blocked(self):
        self.write(self.high / AUDIO_PATH / 'hm_slot_25.wav', b'preserve')
        report = self.inspect()
        self.assertIn('unexpected_slot_asset', self.codes(report))
        self.assertIn(AUDIO_PATH + '/hm_slot_25.wav', report['files'])


if __name__ == '__main__':
    unittest.main()
