import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from game_package.tools.probe_vfs import (
    AUDIO_STORAGE, BARD_CONFIG, LIBRARY_STORAGE, library_targets, load_manifest,
    observe_file, observe_targets, probe_failed, probe_targets,
)


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
            self.assertIs(missing["exists"], False)
            self.assertIs(missing["required"], True)
            self.assertNotIn("bard_enabled", missing)


class VfsLibraryTargetsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.package_bytes = b"synthetic package"
        self.manifest = {"HoldMusic.esp": hashlib.sha256(self.package_bytes).hexdigest()}

    def put(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def minimum_files(self):
        self.put("HoldMusic.esp", self.package_bytes)
        self.put(BARD_CONFIG, b"bard_singing:\n  enabled: false\n  api_key: never-echo-me\n")
        self.put(f"{LIBRARY_STORAGE}/library.json", b'{"version":1,"slots":24,"recordings":[]}')

    def observe(self):
        return observe_targets(self.root, self.manifest, resolve_handle=lambda stream: stream.name)

    def test_all_library_files_include_lyrics_and_trace_with_required_status(self):
        targets = library_targets()
        self.assertEqual(len(targets), 51)
        self.assertIs(targets[f"{LIBRARY_STORAGE}/library.json"], True)
        self.assertIs(targets[f"{LIBRARY_STORAGE}/receipts.json"], False)
        self.assertIs(targets[f"{LIBRARY_STORAGE}/trace.json"], False)
        for slot in range(1, 25):
            self.assertIs(targets[f"{AUDIO_STORAGE}/hm_slot_{slot:02d}.wav"], False)
            self.assertIs(targets[f"{LIBRARY_STORAGE}/hm_slot_{slot:02d}.lyrics.txt"], False)
        self.assertNotIn(f"{AUDIO_STORAGE}/hm_slot_01.lyrics.txt", targets)

    def test_healthy_partial_library_reports_optional_absence_without_failing(self):
        self.minimum_files()
        self.put(f"{AUDIO_STORAGE}/hm_slot_01.wav", b"synthetic audio")
        words = b"private synthetic lyrics never returned"
        lyrics = self.put(f"{LIBRARY_STORAGE}/hm_slot_01.lyrics.txt", words)
        before = {str(path): (path.stat().st_mtime_ns, path.read_bytes())
                  for path in self.root.rglob("*") if path.is_file()}
        rows = self.observe()
        self.assertFalse(probe_failed(rows))
        self.assertEqual(len(rows), 53)
        found = {row["virtual_path"]: row for row in rows}
        self.assertEqual(found[f"{LIBRARY_STORAGE}/hm_slot_01.lyrics.txt"]["opened_path"], str(lyrics))
        self.assertEqual(found[f"{LIBRARY_STORAGE}/hm_slot_01.lyrics.txt"]["sha256"],
                         hashlib.sha256(words).hexdigest())
        self.assertIs(found[f"{AUDIO_STORAGE}/hm_slot_24.wav"]["exists"], False)
        self.assertEqual(found[f"{AUDIO_STORAGE}/hm_slot_24.wav"]["error"], "FileNotFoundError")
        self.assertNotIn("opened_path", found[f"{AUDIO_STORAGE}/hm_slot_24.wav"])
        encoded = json.dumps(rows)
        self.assertNotIn(words.decode(), encoded)
        self.assertNotIn("never-echo-me", encoded)
        self.assertEqual({str(path): (path.stat().st_mtime_ns, path.read_bytes())
                          for path in self.root.rglob("*") if path.is_file()}, before)

    def test_missing_required_input_or_wrong_package_hash_still_fails(self):
        self.minimum_files()
        library = self.root / LIBRARY_STORAGE / "library.json"
        library.unlink()
        rows = self.observe()
        self.assertTrue(probe_failed(rows))
        missing = next(row for row in rows if row["virtual_path"].endswith("/library.json"))
        self.assertIs(missing["required"], True)
        self.assertIs(missing["exists"], False)
        self.put(f"{LIBRARY_STORAGE}/library.json", b"{}")
        self.put("HoldMusic.esp", b"changed")
        self.assertTrue(probe_failed(self.observe()))

    def test_package_entry_cannot_downgrade_to_optional(self):
        name = f"{AUDIO_STORAGE}/hm_slot_24.wav"
        self.manifest[name] = "0" * 64
        self.assertIs(probe_targets(self.manifest)[name], True)
        self.minimum_files()
        self.assertTrue(probe_failed(self.observe()))

    def test_optional_read_failure_is_not_reported_as_absence(self):
        name = f"{LIBRARY_STORAGE}/trace.json"
        with patch.object(Path, "open", side_effect=PermissionError("private detail")):
            row = observe_file(self.root, name, resolve_handle=lambda stream: stream.name,
                               required=False)
        self.assertEqual(row["error"], "PermissionError")
        self.assertNotIn("exists", row)
        self.assertNotIn("private detail", json.dumps(row))
        self.assertTrue(probe_failed([row]))

    def test_missing_handle_destination_after_successful_open_is_not_absence(self):
        name = f"{LIBRARY_STORAGE}/trace.json"
        self.put(name, b"{}")
        def failed_resolver(stream):
            raise FileNotFoundError("fixture handle resolution failed")
        row = observe_file(self.root, name, resolve_handle=failed_resolver, required=False)
        self.assertIs(row["exists"], True)
        self.assertEqual(row["error"], "FileNotFoundError")
        self.assertTrue(probe_failed([row]))

    def test_unsafe_manifest_virtual_paths_are_rejected_before_any_reads(self):
        unsafe = ("/absolute", "../escape", "Data/../escape", "C:/secrets", "C:relative",
                  r"..\escape", r"\\server\share\file", "Data//file", "Data/./file",
                  "Data/file:stream", "Data/NUL", "Data/COM1.txt", "Data/trailing.",
                  "Data/trailing ", "Data/control\x00", "")
        for name in unsafe:
            with self.subTest(name=name), patch.object(Path, "open") as opened:
                with self.assertRaises(ValueError):
                    observe_targets(self.root, {**self.manifest, name: "0" * 64},
                                    resolve_handle=lambda stream: stream.name)
                opened.assert_not_called()
                with self.assertRaises(ValueError):
                    observe_file(self.root, name, resolve_handle=lambda stream: stream.name)
                opened.assert_not_called()

    def test_duplicate_keys_types_and_hashes_are_rejected(self):
        digest = "0" * 64
        duplicate = ('{"HoldMusic.esp":"' + digest + '","HoldMusic.esp":"' + digest + '"}').encode()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_manifest(duplicate)
        for manifest in ([], {}, {"file": True}, {"file": None}, {"file": {}},
                         {"file": "0" * 63}, {"file": "A" * 64},
                         {"file": digest, "FILE": digest}):
            with self.subTest(manifest=manifest), patch.object(Path, "open") as opened:
                with self.assertRaises(ValueError):
                    observe_targets(self.root, manifest, resolve_handle=lambda stream: stream.name)
                opened.assert_not_called()
        self.assertEqual(load_manifest(b"\xef\xbb\xbf" + json.dumps(self.manifest).encode()),
                         self.manifest)

    def test_manifest_cannot_alias_a_canonical_library_or_config_target(self):
        for name in (BARD_CONFIG.lower(), f"{LIBRARY_STORAGE}/library.JSON"):
            with self.subTest(name=name), patch.object(Path, "open") as opened:
                with self.assertRaisesRegex(ValueError, "aliases"):
                    observe_targets(self.root, {name: "0" * 64},
                                    resolve_handle=lambda stream: stream.name)
                opened.assert_not_called()

    def test_no_default_injection_or_runtime_claim_is_added(self):
        self.minimum_files()
        rows = self.observe()
        for row in rows:
            self.assertNotIn("injected", row)
            self.assertNotIn("runtime_verified", row)
            self.assertNotIn("write_target", row)
        old_error_row = {"virtual_path": "legacy", "error": "FileNotFoundError"}
        self.assertTrue(probe_failed([old_error_row]))


if __name__ == "__main__":
    unittest.main()
