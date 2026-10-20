import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from tools import create_se_lab_fixture as fixture
from hold_music.runtime_contract import manifest_runtime_selection_errors


class LabFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "lab"
        for path in ("checkpoints", "build", "MO2/mods", "MO2/overwrite"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "checkpoints/bootstrap.json").write_text("{}")
        self.patch = patch.object(fixture, "LAB", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def run_fixture(self):
        with contextlib.redirect_stdout(io.StringIO()):
            fixture.main()

    def test_fixture_has_strict_identity_real_pcm_and_empty_runtime_arrays(self):
        self.run_fixture()
        mod = self.root / "MO2/mods/Hold Music Lab Data"
        manifest = json.loads((mod / "SKSE/Plugins/StorageUtilData/HoldMusic/library.json").read_text())
        self.assertEqual([], manifest_runtime_selection_errors(manifest, required=True))
        with wave.open(str(mod / "Sound/fx/holdmusic/hm_slot_01.wav")) as wav:
            self.assertEqual((1, 2, 44100), (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()))
            self.assertEqual(8, wav.getnframes() / wav.getframerate())
            self.assertNotEqual({0}, set(wav.readframes(wav.getnframes())))
        runtime = self.root / "MO2/overwrite/SKSE/Plugins/StorageUtilData/HoldMusic"
        self.assertEqual({"version": 1, "entries": []}, json.loads((runtime / "trace.json").read_text()))
        self.assertEqual({"version": 1, "performances": []}, json.loads((runtime / "receipts.json").read_text()))
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaises(SystemExit):
            self.run_fixture()
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_existing_runtime_history_blocks_before_audio_creation(self):
        receipt = self.root / "MO2/overwrite/SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"performances":[{"id":"keep-me"}]}')
        with self.assertRaises(SystemExit):
            self.run_fixture()
        self.assertFalse((self.root / "build/synthetic-audio-v1").exists())
        self.assertIn("keep-me", receipt.read_text())

    def test_overwrite_alias_blocks_before_any_fixture_writes(self):
        target = Path(self.temp.name) / "outside"
        target.mkdir()
        overwrite = self.root / "MO2/overwrite"
        overwrite.rmdir()
        try:
            overwrite.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks unavailable on this host")
        with self.assertRaises(ValueError):
            self.run_fixture()
        self.assertEqual([], list(target.iterdir()))
        self.assertFalse((self.root / "build/synthetic-audio-v1").exists())


if __name__ == "__main__":
    unittest.main()
