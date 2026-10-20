"""Explicit flat evidence and split routes remain a plan, never an installation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.library import Library
from hold_music.library_publication import plan_library_publication
from hold_music.runtime_contract import project_runtime_contract

STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusic"
AUDIO = "Sound/fx/holdmusic"


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns,
            hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*") if p.is_file()}


class LibraryPublicationIntegrationTests(unittest.TestCase):
    def test_free_slot_routes_and_manifest_last_preserve_installed_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            mo2, base = root / "mo2", root / "game/Data"
            meta, audio_mod = mo2 / "mods/Meta", mo2 / "mods/Audio"
            for path in (meta, audio_mod, base, mo2 / "profiles/pilot", mo2 / "profiles/unaffected"):
                path.mkdir(parents=True)
            for profile, modlist in (("pilot", "+Meta\n+Audio\n"),
                                     ("unaffected", "-Meta\n-Audio\n")):
                (mo2 / "profiles" / profile / "modlist.txt").write_text(modlist, encoding="utf-8")
                (mo2 / "profiles" / profile / "plugins.txt").write_text("*HoldMusic.esp\n", encoding="utf-8")
            audio = root / "silent-fixture.wav"
            with wave.open(str(audio), "wb") as wav:
                wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0\0" * 4410)
            destination = Library(root / "destination-snapshot")
            old = destination.add_recording(
                audio, performer_id="sven", region="whiterun", mode="instrumental",
                gender="male", composition_id="retained-legacy", recipe_id="old-label",
                model_id="unknown", source={"kind": "import", "path_or_request_id": "old-fixture"},
            )
            original_manifest = deepcopy(destination.load().manifest)
            receipt = {"version": 1, "performances": [{
                "id": "fixture:0", "slot": 2, "performer_id": "sven", "composition_id": "older-fixture",
                "save_id": "fixture-save", "world_id": "fixture-world", "at_hours": 10,
                "outcome": "interrupted",
            }]}
            (destination.root / "receipts.json").write_text(json.dumps(receipt), encoding="utf-8")
            (destination.root / "hm_slot_04.wav").write_bytes(b"reserved orphan")

            def copy(source, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

            copy(destination.root / "library.json", meta / STORAGE / "library.json")
            copy(destination.root / old["file"], audio_mod / AUDIO / old["file"])
            copy(destination.root / "receipts.json", mo2 / "overwrite" / STORAGE / "receipts.json")
            copy(destination.root / "hm_slot_04.wav", audio_mod / AUDIO / "hm_slot_04.wav")
            contract = project_runtime_contract({
                "performer_id": "mikael", "request": {
                    "tradition": "whiterun", "recipe_id": "fixture/cittern",
                    "recipe_revision": "fixture-r1", "model_id": "synthetic-fixture",
                    "instrument_family": "plucked_string", "instrument_name": "cittern",
                    "arrangement": "solo_lute", "mode": "instrumental", "voice": "none",
                },
            })
            staged = Library(root / "staged-library")
            staged.add_recording(audio, gender="male", composition_id="new-fixture",
                source={"kind": "import", "path_or_request_id": "new-synthetic-fixture"}, **contract)
            staged_manifest = deepcopy(staged.load().manifest)
            staged_manifest["runtime_selection"] = {"version": 1, "contracts": [contract]}
            (staged.root / "library.json").write_text(json.dumps(staged_manifest), encoding="utf-8")
            before = snapshot(root)
            with patch("socket.create_connection", side_effect=AssertionError("Network forbidden")):
                report = plan_library_publication(
                    staged.root, destination.root, mo2, "pilot",
                    metadata_mod="Meta", audio_mod="Audio", game_data=base,
                )
            self.assertEqual(report["blockers"], [], report["blockers"])
            self.assertTrue(report["snapshot_equivalence"]["matches"])
            self.assertEqual(report["proposed_manifest"]["recordings"][0], original_manifest["recordings"][0])
            self.assertEqual([row["slot"] for row in report["proposed_manifest"]["recordings"]], [1, 3])
            added = report["proposed_manifest"]["recordings"][1]
            for field in ("identity_key", "recipe_id", "recipe_revision", "instrument_name",
                          "instrument_family", "arrangement"):
                self.assertEqual(added[field], contract[field])
            other = next(item for item in report["shared_profiles"]
                         if item["profile"] == "unaffected")
            self.assertTrue(other["affected_scope_complete"])
            self.assertTrue(all(not effect["effective_change"] for effect in other["effects"]))
            routes = {row["virtual_path"]: row for row in report["routes"]}
            self.assertEqual(set(routes), {AUDIO + "/hm_slot_03.wav", STORAGE + "/library.json"})
            self.assertEqual(Path(routes[AUDIO + "/hm_slot_03.wav"]["physical_target"]),
                             audio_mod / AUDIO / "hm_slot_03.wav")
            self.assertEqual(Path(routes[STORAGE + "/library.json"]["physical_target"]),
                             meta / STORAGE / "library.json")
            self.assertEqual(report["routes"][-1]["virtual_path"], STORAGE + "/library.json")
            encoded = (json.dumps(report["proposed_manifest"], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.assertEqual(routes[STORAGE + "/library.json"]["after_sha256"],
                             hashlib.sha256(encoded).hexdigest())
            for flag in ("can_apply", "installed", "vfs_verified", "runtime_verified", "writes_performed"):
                self.assertIs(report[flag], False)
            self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
