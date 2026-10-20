"""Knowledge exports use the same production recipe contract as preparation."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hold_music.recording_identity import recording_request
from hold_music.regional import freeze_recipe
from hold_music.registry import DEFAULT_PATH, load_registry
from hold_music.repertoire import Snapshot
from tools.snapshot_knowledge import main
from test_knowledge_bridge import make_database


class SnapshotContractTests(unittest.TestCase):
    def test_cli_exports_versioned_identity_and_respects_regional_modes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = make_database(root / 'SkyrimNet-synthetic.db')
            original = db.read_bytes()
            for region, expected_mode in [('whiterun', 'lyrical'),
                                          ('winterhold', 'wordless'),
                                          ('hjaalmarch', 'instrumental')]:
                with self.subTest(region=region):
                    performer = deepcopy(load_registry().find_by_name('Mikael'))
                    performer['region'] = region
                    output = root / f'{region}.json'
                    with patch('tools.snapshot_knowledge.load_registry',
                               return_value=SimpleNamespace(performers=[performer])), \
                            redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        self.assertEqual(main([
                            '--db', str(db), '--registry', str(DEFAULT_PATH),
                            '--performer', 'mikael', '--library', str(root / 'library'),
                            '--out', str(output), '--allow-name-match', '--now-hours', '105',
                        ]), 0)
                    snapshot = json.loads(output.read_text(encoding='utf-8'))['snapshot']
                    expected = recording_request(freeze_recipe(region, 'vocal', 'male'))
                    self.assertEqual(snapshot['request'], expected)
                    self.assertEqual(snapshot['request']['mode'], expected_mode)
                    Snapshot.from_dict(snapshot)
            self.assertEqual(db.read_bytes(), original)
            self.assertFalse((root / 'library').exists())


if __name__ == '__main__':
    unittest.main()
