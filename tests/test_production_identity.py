"""The real preparation-to-staging path, with fake provider/audio conversion."""
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch

from hold_music.executor import execute, plan_work
from hold_music.job_store import inspect_jobs
from hold_music.library import Library
from hold_music.lyria_client import Result
from hold_music.recording_identity import CONTRACT_FIELDS, recording_request
from hold_music.registry import load_registry
from hold_music.repertoire import plan
from tools.verify_offline_loop import stage_selection
from test_executor import fake_conversion
from mp3_fixture import mp3_frames


class ProductionIdentityTests(unittest.TestCase):
    def test_owned_pilots_keep_identity_from_preparation_to_staged_assets(self):
        for performer in ('sven', 'lynly_star_sung'):
            with self.subTest(performer=performer), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                library = Library(root / 'library')
                jobs = plan_work(load_registry(), library, performer_ids=[performer])
                self.assertEqual(len(jobs), 1)
                client = Mock()
                client.generate.return_value = Result(mp3_frames(), 5, {'cost': 0}, 'fake-request')
                with patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')), \
                        patch('subprocess.run', side_effect=AssertionError('process launch forbidden')), \
                        patch('hold_music.executor.shutil.which', return_value='/fixture/ffmpeg'), \
                        patch('hold_music.executor.convert_mp3', side_effect=fake_conversion):
                    result = execute(jobs, client=client, library=library, ffmpeg='fixture',
                                     max_jobs=1, max_usd=.1, dry_run=False, spend=True)
                self.assertEqual(result['status'], 'complete')
                client.generate.assert_called_once_with(jobs[0]['prompt'])
                self.assertEqual(inspect_jobs(library.root)[0]['state'], 'completed')
                request = recording_request(jobs[0])
                decision = plan(library.snapshot(performer, 'fixture-save', 'fixture-world', 100, request))
                self.assertEqual(decision['action'], 'play_recording')
                self.assertEqual(plan_work(load_registry(), library, performer_ids=[performer]), [])
                contract = {key: request[key] for key in CONTRACT_FIELDS}
                receipt = stage_selection(library, decision, contract, root / 'staged')
                self.assertEqual(receipt['contract'], contract)
                self.assertEqual(receipt['source']['path_or_request_id'], 'fake-request')
                staged = Library(root / 'staged/library').load()
                self.assertEqual(staged.problems, [])
                self.assertEqual(recording_request(staged.recordings[0]), request)
                self.assertFalse(receipt['installed'])
                self.assertFalse(receipt['runtime_receipts_in_payload'])


if __name__ == '__main__':
    unittest.main()
