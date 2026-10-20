"""Import publication must never opt into Library's explicit replacement API."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.library import Library
import hold_music.library as library_module


class ImportSlotGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wav = self.root / "source.wav"
        with wave.open(str(self.wav), "wb") as wav:
            wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0" * 441)
        self.library = Library(self.root / "library", session_receipt_index=0)
        self.args = dict(performer_id="fixture", region="whiterun", mode="instrumental",
                         gender="male", composition_id="fixture", recipe_id="fixture",
                         model_id="unknown", source={"kind": "import", "path_or_request_id": "fixture"})

    def test_explicit_session_boundary_does_not_enable_import_replacement(self):
        self.library.add_recording(self.wav, slot=1, **self.args)
        original = {p.name: p.read_bytes() for p in self.library.root.iterdir() if p.is_file()}
        with self.assertRaisesRegex(ValueError, "replacement is forbidden"):
            self.library.add_recording(self.wav, slot=1, require_unoccupied=True, **self.args)
        self.assertEqual({p.name: p.read_bytes() for p in self.library.root.iterdir() if p.is_file()}, original)

    def test_asset_created_while_staging_is_preserved_and_blocks_publication(self):
        copyfile = library_module.shutil.copyfile

        def concurrent_asset(source, destination):
            result = copyfile(source, destination)
            (self.library.root / "hm_slot_01.wav").write_bytes(b"concurrent asset")
            return result

        with patch("hold_music.library.shutil.copyfile", side_effect=concurrent_asset):
            with self.assertRaisesRegex(ValueError, "Library changed"):
                self.library.add_recording(self.wav, slot=1, require_unoccupied=True, **self.args)
        self.assertEqual((self.library.root / "hm_slot_01.wav").read_bytes(), b"concurrent asset")
        self.assertFalse((self.library.root / "library.json").exists())

    def test_guard_flag_is_not_silently_truthy(self):
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            self.library.add_recording(self.wav, require_unoccupied="yes", **self.args)
        self.assertFalse(self.library.root.exists())

    def test_free_slot_publishes_without_changing_legacy_manifest_fields(self):
        row = self.library.add_recording(self.wav, slot=1, require_unoccupied=True, **self.args)
        self.assertEqual(row["slot"], 1)
        self.assertNotIn("require_unoccupied", row)
        self.assertEqual(self.library.validate(), [])


if __name__ == "__main__":
    unittest.main()
