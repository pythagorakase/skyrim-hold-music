from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hold_music.runtime_paths import DEFAULT_MOD_NAME, storage_dirs
from tools.collect_evidence import collect, main


def snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None,
                                      p.stat().st_mtime_ns, p.stat().st_mode)
            for p in root.rglob('*')}


class CollectEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.mo2 = self.base / 'MO2'
        self.mo2.mkdir()
        self.out = self.base / 'evidence'
        self.documents = self.mo2 / 'profiles/Test/experimental-documents'

    def write(self, path, text, mtime=100):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        os.utime(path, (mtime, mtime))
        return path

    def test_bundle_all_candidates_counts_logs_redaction_and_read_only(self):
        dirs = storage_dirs(self.mo2, DEFAULT_MOD_NAME, 'Data')
        for i, directory in enumerate(dirs):
            self.write(directory / 'receipts.json', json.dumps({'version': 1, 'performances':
                [{'outcome': 'completed'}, {'outcome': 'interrupted'}]}), 100 + i)
            self.write(directory / 'trace.json', json.dumps({'version': 1, 'entries': [
                {'seq': 1, 'real_seconds': 1.0, 'game_hours': 42.0, 'event': 'candidate',
                 'detail': 'id=sven owner=hold_music eligible=true'},
                {'seq': 2, 'real_seconds': 2.0, 'game_hours': 42.0, 'event': 'performance_start',
                 'detail': 'slot=3'}]}), 100 + i)
        self.write(self.mo2 / 'logs/HoldMusic.log', ''.join(f'helper-{i:03d}\n' for i in range(100)) +
                   'apiKEY=synthetic-sensitive\n')
        self.write(self.mo2 / 'logs/HoldMusic-Service.log',
                   'service-ready\nToKeN=synthetic-sensitive\nSECRET=synthetic-sensitive\n'
                   'Bearer synthetic-sensitive\nPassword=synthetic-sensitive\n')
        self.write(self.documents / 'SKSE/SkyrimNet-z-old.log', 'BardSinging old-file\n', 10)
        self.write(self.documents / 'SKSE/SkyrimNet-a-new.log',
                   '[2026-10-11 01:00:00.001] initialized\n' +
                   ''.join(f'[01:00:01] BardSinging match-{i:03d}\n' for i in range(130)) +
                   '[01:00:02] Dialogue: synthetic private dialogue\n'
                   '[01:00:03] memory: synthetic private memory\n'
                   '[01:00:04] HoldMusic dialogue: synthetic private dialogue\n'
                   '[01:00:05] BardSinging memory: synthetic private memory\n'
                   '[01:00:06] HoldMusic token=synthetic-sensitive\n'
                   '[2026-10-11 02:00:00.999] shutdown\n', 20)
        self.write(self.documents / 'Logs/Script/old/Papyrus.0.log', 'HoldMusic old-papyrus\n', 10)
        self.write(self.documents / 'Logs/Script/Papyrus.0.log',
                   ''.join(f'HoldMusic papyrus-{i:03d}\n' for i in range(125)) +
                   'Other script\nHoldMusic password=synthetic-sensitive\n', 20)
        before = snapshot(self.mo2)
        report = collect(self.mo2, 'Test', data_mod='Data', out=self.out)
        self.assertEqual(snapshot(self.mo2), before)
        text = report.read_text()
        for section in ('Runtime JSON', 'Receipt outcomes', 'Trace events', 'HoldMusic.log',
                        'HoldMusic-Service.log', 'SkyrimNet', 'Papyrus', 'Missing inputs'):
            self.assertIn(section, text)
        self.assertEqual(len(list(self.out.glob('*.json'))), 6)
        self.assertEqual((self.out / 'receipts-01.json').read_bytes(), (dirs[2] / 'receipts.json').read_bytes())
        for phrase in ('| completed | 1 |', '| interrupted | 1 |', '| candidate | 1 |',
                       '| performance_start | 1 |', 'Entry count: 2', 'Mtime (Unix seconds): 102.0',
                       'Size (bytes):', 'First timestamp: 2026-10-11 01:00:00.001',
                       'Last timestamp: 2026-10-11 02:00:00.999', 'service-ready',
                       'helper-021', 'helper-099', 'match-010', 'match-129', 'papyrus-005', 'papyrus-124'):
            self.assertIn(phrase, text)
        for phrase in ('synthetic-sensitive', 'synthetic private', 'old-file', 'old-papyrus',
                       'helper-020', 'match-009', 'papyrus-004', 'Other script'):
            self.assertNotIn(phrase, text)
        self.assertEqual(text.count('BardSinging match-'), 120)
        self.assertEqual(text.count('HoldMusic papyrus-'), 120)

    def test_redaction_applies_to_json_copies_and_derived_tables(self):
        directory = storage_dirs(self.mo2, DEFAULT_MOD_NAME)[0]
        self.write(directory / 'trace.json', '{\n"version": 1,\n"entries": [\n'
                   '{"event": "candidate", "detail": "TOKEN=synthetic-sensitive"},\n'
                   '{"event": "performance_stop", "detail": "outcome=completed"}\n]}\n')
        self.write(directory / 'receipts.json',
                   '{"version": 1, "performances": [{"outcome": "secret-value"}]}\n')
        before = snapshot(self.mo2)
        report = collect(self.mo2, 'Test', out=self.out)
        self.assertEqual(snapshot(self.mo2), before)
        for path in self.out.iterdir():
            text = path.read_text()
            self.assertNotRegex(text.lower(), 'key|token|secret|bearer|password')
            self.assertNotIn('synthetic-sensitive', text)
        self.assertNotIn('| candidate |', report.read_text())
        self.assertIn('| performance_stop | 1 |', report.read_text())
        self.assertEqual(json.loads((self.out / 'trace-01.json').read_text())['entries'],
                         [{'event': 'performance_stop', 'detail': 'outcome=completed'}])
        self.assertEqual((self.out / 'receipts-01.json').read_bytes(), b'')

    def test_missing_and_malformed_inputs_are_reported(self):
        directory = storage_dirs(self.mo2, DEFAULT_MOD_NAME)[1]
        self.write(directory / 'trace.json', '{partial')
        before = snapshot(self.mo2)
        text = collect(self.mo2, 'Test', out=self.out).read_text()
        self.assertEqual(snapshot(self.mo2), before)
        self.assertIn('Entry count: unavailable', text)
        self.assertIn('Missing.', text)
        self.assertIn(str(directory / 'receipts.json'), text)
        self.assertEqual((self.out / 'trace-01.json').read_text(), '{partial')

    def test_no_source_or_existing_output_overwrite(self):
        before = snapshot(self.mo2)
        with self.assertRaisesRegex(ValueError, 'outside'):
            collect(self.mo2, 'Test', out=self.mo2 / 'evidence')
        self.assertEqual(snapshot(self.mo2), before)
        collect(self.mo2, 'Test', out=self.out)
        before = snapshot(self.out)
        with self.assertRaises(FileExistsError):
            collect(self.mo2, 'Test', out=self.out)
        self.assertEqual(snapshot(self.out), before)

    def test_cli_prints_path_and_default_utc_directory(self):
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(['--mo2-root', str(self.mo2), '--profile', 'Test',
                                   '--out', str(self.out)]), 0)
        self.assertEqual(stdout.getvalue().strip(), str(self.out / 'report.md'))
        with patch('tools.collect_evidence.ROOT', self.base):
            report = collect(self.mo2, 'Test')
        self.assertEqual(report.parent.parent, self.base / 'local/evidence')
        self.assertRegex(report.parent.name, r'^\d{8}-\d{6}$')


if __name__ == '__main__':
    unittest.main()
