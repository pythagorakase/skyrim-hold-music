import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from game_package.tools.probe_vfs import BARD_CONFIG, observe_file


class VfsObservationTests(unittest.TestCase):
    def test_reports_opened_destination_hash_and_boolean_without_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / BARD_CONFIG
            target.parent.mkdir(parents=True)
            raw = b"\xef\xbb\xbfbard_singing:\r\n  enabled: false\r\n  api_key: synthetic-private-key\r\n"
            target.write_bytes(raw)
            seen = []
            def destination(stream):
                seen.append(stream.name)
                return str(target)
            report = observe_file(root, BARD_CONFIG, resolve_handle=destination)
            self.assertEqual(seen, [str(target)])
            self.assertEqual(report["opened_path"], str(target))
            self.assertEqual(report["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertIs(report["bard_enabled"], False)
            self.assertNotIn("synthetic-private-key", json.dumps(report))

    def test_malformed_config_retains_handle_hash_but_has_no_enabled_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / BARD_CONFIG
            target.parent.mkdir(parents=True)
            for text in ('bard_singing:\n  enabled: "false"\n  api_key: private-value\n',
                         "bard_singing:\n  enabled: false\n  enabled: true\n"):
                with self.subTest(text=text):
                    target.write_text(text)
                    row = observe_file(root, BARD_CONFIG, resolve_handle=lambda stream: str(target))
                    self.assertIsNone(row["bard_enabled"])
                    self.assertEqual(row["configuration_error"], "ValueError")
                    self.assertNotIn("private-value", json.dumps(row))

    def test_normal_package_hash_and_missing_file_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "HoldMusic.esp").write_bytes(b"offline fixture")
            row = observe_file(root, "HoldMusic.esp", resolve_handle=lambda stream: stream.name,
                               expected=hashlib.sha256(b"offline fixture").hexdigest())
            self.assertTrue(row["matches_package"])
            self.assertNotIn("bard_enabled", row)
            missing = observe_file(root, BARD_CONFIG, resolve_handle=lambda stream: stream.name)
            self.assertEqual(missing["error"], "FileNotFoundError")
            self.assertNotIn("bard_enabled", missing)


if __name__ == "__main__":
    unittest.main()
