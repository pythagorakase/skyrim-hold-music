"""Exercise the public offline planner command with synthetic story snapshots."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "tools" / "plan_repertoire.py"
EXAMPLES = ROOT / "examples" / "repertoire"


class RepertoireCommandTests(unittest.TestCase):
    def run_command(self, path, cwd):
        return subprocess.run(
            [sys.executable, str(COMMAND), str(path)], cwd=cwd,
            capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def test_examples_propose_lyrics_without_changing_snapshot(self):
        with tempfile.TemporaryDirectory() as working:
            for name in ("scandal", "quest-success"):
                with self.subTest(name=name):
                    path = EXAMPLES / f"{name}.json"
                    before = hashlib.sha256(path.read_bytes()).hexdigest()
                    result = self.run_command(path, working)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    decision = json.loads(result.stdout)
                    self.assertEqual(decision["action"], "compose_lyrics")
                    self.assertIsNotNone(decision["lyric_brief"])
                    self.assertIsNotNone(decision["fallback"])
                    self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cache_first_reuses_a_recording_without_lyrics(self):
        with tempfile.TemporaryDirectory() as working:
            data = json.loads((EXAMPLES / "scandal.json").read_text(encoding="utf-8"))
            data["policy"]["selection"] = "cache_first"
            path = Path(working) / "snapshot.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_command(path, working)
            self.assertEqual(result.returncode, 0, result.stderr)
            decision = json.loads(result.stdout)
            self.assertEqual(decision["action"], "play_recording")
            self.assertEqual(decision["recording_id"], "demo:recording:market-day")
            self.assertIsNone(decision["lyric_brief"])

    def test_invalid_snapshot_reports_an_error_without_a_plan(self):
        with tempfile.TemporaryDirectory() as working:
            path = Path(working) / "invalid.json"
            for contents in ("{broken", "{}", "[]"):
                with self.subTest(contents=contents):
                    path.write_text(contents, encoding="utf-8")
                    result = self.run_command(path, working)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("Cannot plan repertoire:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
