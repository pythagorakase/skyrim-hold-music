"""A split loose-file library and synthetic handle capture remain inspection only."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

from game_package.tools.probe_vfs import library_targets, observe_file
from hold_music.installed_library import inspect_installed_library
from hold_music.library import Library

STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusic"
AUDIO = "Sound/fx/holdmusic"


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns,
             hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*") if p.is_file()}


class InstalledLibraryIntegrationTests(unittest.TestCase):
    def test_split_sources_priority_and_complete_synthetic_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            mo2 = root / "mo2"
            base = root / "game/Data"
            high, low, disabled = (mo2 / "mods" / name for name in ("High", "Low", "Disabled"))
            for directory in (high, low, disabled, mo2 / "overwrite", mo2 / "profiles/pilot", base):
                directory.mkdir(parents=True)
            (mo2 / "profiles/pilot/modlist.txt").write_text("+High\n+Low\n-Disabled\n", encoding="utf-8")
            (mo2 / "profiles/pilot/plugins.txt").write_text("*HoldMusic.esp\n", encoding="utf-8")
            source = root / "source.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0\0" * 4410)
            scratch = Library(root / "scratch")
            row = scratch.add_recording(source, performer_id="sven", region="whiterun",
                mode="vocal", gender="male", composition_id="fixture-song",
                recipe_id="legacy-fixture", model_id="unknown", lyrics="Synthetic fixture words.",
                source={"kind": "import", "path_or_request_id": "synthetic-fixture"})

            def copy(source_path, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, destination)

            copy(scratch.root / "library.json", low / STORAGE / "library.json")
            copy(scratch.root / row["file"], high / AUDIO / row["file"])
            copy(scratch.root / "hm_slot_01.lyrics.txt", base / STORAGE / "hm_slot_01.lyrics.txt")
            # The lower duplicate's newer mtime cannot outrank High's WAV.
            copy(source, low / AUDIO / row["file"])
            with wave.open(str(low / AUDIO / row["file"]), "wb") as wav:
                wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                wav.writeframes(b"\1\0" * 4410)
            os.utime(low / AUDIO / row["file"], (2000000000, 2000000000))
            orphan = high / AUDIO / "hm_slot_03.wav"
            orphan.write_bytes(b"orphan bytes are preserved, not silently reused")
            receipt = {"version": 1, "performances": [{
                "id": "fixture:0", "slot": 2, "performer_id": "sven",
                "composition_id": "previous-fixture", "save_id": "fixture-save",
                "world_id": "fixture-world", "at_hours": 10, "outcome": "interrupted",
            }]}
            receipt_path = mo2 / "overwrite" / STORAGE / "receipts.json"
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            lower_receipts = low / STORAGE / "receipts.json"
            lower_receipts.write_text('{"version":1,"performances":[]}', encoding="utf-8")
            os.utime(lower_receipts, (2000000000, 2000000000))
            (disabled / STORAGE).mkdir(parents=True)
            (disabled / STORAGE / "library.json").write_text("invalid inactive manifest", encoding="utf-8")

            before = snapshot(root)
            report = inspect_installed_library(mo2, "pilot", game_data=base)
            self.assertEqual(report["blockers"], [], report["blockers"])
            self.assertEqual(Path(report["files"][STORAGE + "/library.json"]["winner"]["path"]),
                             low / STORAGE / "library.json")
            self.assertEqual(Path(report["files"][AUDIO + "/hm_slot_01.wav"]["winner"]["path"]),
                             high / AUDIO / "hm_slot_01.wav")
            self.assertEqual(Path(report["files"][STORAGE + "/hm_slot_01.lyrics.txt"]["winner"]["path"]),
                             base / STORAGE / "hm_slot_01.lyrics.txt")
            self.assertEqual(Path(report["files"][STORAGE + "/receipts.json"]["winner"]["path"]), receipt_path)
            self.assertEqual(report["history"]["performance_count"], 1)
            self.assertTrue({1, 2, 3} <= {r["slot"] for r in report["reservations"]})
            self.assertEqual(snapshot(root), before)

            # Build a fixture-only virtual Data view; the actual process is never launched through MO2.
            virtual = root / "synthetic-virtual-data"
            virtual.mkdir()
            for name, item in report["files"].items():
                if item["winner"] is not None:
                    copy(Path(item["winner"]["path"]), virtual / name)
            observations = []
            for name, required in library_targets().items():
                winner = report["files"][name]["winner"]
                observations.append(observe_file(virtual, name, required=required,
                    resolve_handle=lambda stream, winner=winner: winner["path"]))
            capture = root / "synthetic-capture.json"
            capture.write_text(json.dumps({
                "version": 2, "profile": "pilot",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data_root": str(base), "files": observations,
            }), encoding="utf-8")
            before = snapshot(root)
            corroborated = inspect_installed_library(mo2, "pilot", game_data=base, vfs_report=capture)
            self.assertEqual(corroborated["blockers"], [], corroborated["blockers"])
            for key in ("installed", "vfs_verified", "runtime_verified", "writes_performed"):
                self.assertIs(corroborated[key], False)
            self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
