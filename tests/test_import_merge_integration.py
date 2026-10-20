"""Existing-audio import through selection, staging and additive merge review."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.library import Library
from hold_music.library_merge import plan_library_merge
from hold_music.recording_identity import CONTRACT_FIELDS, recording_request
from hold_music.repertoire import plan
from tools.import_recording import review_import_recording
from tools.verify_offline_loop import stage_selection


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns,
             hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*") if p.is_file()}


class ImportMergeIntegrationTests(unittest.TestCase):
    def test_reviewed_import_keeps_identity_through_selection_and_slot_remapping(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "existing.mp3"
            source.write_bytes(b"synthetic conversion input; no provider")
            converter = root / "fake-ffmpeg"
            converter.write_bytes(b"fixture executable; never launched")
            metadata = {
                "version": 1,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "lyrics_sha256": None, "performer_id": "sven",
                "region": "whiterun", "mode": "instrumental", "gender": "male",
                "recipe_id": "fixture/cittern", "recipe_revision": "fixture-revision",
                "model_id": "synthetic-fixture", "instrument_family": "plucked_string",
                "instrument_name": "cittern", "arrangement": "solo_lute", "voice": "none",
            }
            sidecar = root / "metadata.json"
            sidecar.write_text(json.dumps(metadata), encoding="utf-8")
            arguments = dict(library=root / "imported", performer="sven", region="whiterun",
                             mode="instrumental", gender="male", source=source,
                             metadata=sidecar, ffmpeg=converter)

            def convert(command, **kwargs):
                with wave.open(str(command[-1]), "wb") as wav:
                    wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                    wav.writeframes(b"\0\0" * 4410)

            with patch("socket.create_connection", side_effect=AssertionError("Network forbidden")), \
                    patch("tools.import_recording.shutil.which", return_value=str(converter)), \
                    patch("tools.import_recording.subprocess.run", side_effect=convert) as run:
                before = snapshot(root)
                review = review_import_recording(**arguments)
                self.assertTrue(review["can_apply"], review)
                self.assertEqual(snapshot(root), before)
                run.assert_not_called()
                imported = review_import_recording(**arguments, apply=True,
                                                   review_token=review["review_token"])
                self.assertEqual(imported["status"], "imported", imported)
                run.assert_called_once()
            library = Library(root / "imported").load()
            row = imported["recording"]
            request = recording_request(row)
            for key in CONTRACT_FIELDS:
                self.assertEqual(request[key], metadata[key])
            decision = plan(library.snapshot("sven", "fixture-save", "fixture-world", 100, request))
            self.assertEqual(decision["action"], "play_recording", decision)
            contract = {key: request[key] for key in CONTRACT_FIELDS}
            staging = stage_selection(library, decision, contract, root / "staged")
            self.assertEqual(staging["source"]["sha256"], metadata["source_sha256"])
            self.assertFalse(staging["installed"])

            # Preserve a different performer's legacy recording and all reserved assets.
            destination = Library(root / "destination")
            destination.add_recording(library.root / row["file"], performer_id="legacy-other",
                region="whiterun", mode="instrumental", gender="male",
                composition_id="legacy-content", recipe_id="whiterun/instrumental",
                model_id="unknown", source={"kind": "import", "path_or_request_id": "fixture"})
            original_manifest = deepcopy(destination.load().manifest)
            (destination.root / "hm_slot_03.wav").write_bytes(b"orphan audio must survive")
            (destination.root / "hm_slot_04.lyrics.txt").write_text("orphan words", encoding="utf-8")
            receipts = root / "current-receipts.json"
            receipts.write_text(json.dumps({"version": 1, "performances": [{
                "id": "interrupted:0", "slot": 2, "performer_id": "legacy-other",
                "composition_id": "older-content", "save_id": "fixture-save",
                "world_id": "fixture-world", "at_hours": 10, "outcome": "interrupted",
            }]}), encoding="utf-8")
            before = snapshot(root)
            merge = plan_library_merge(root / "staged/library", destination.root,
                                       receipts_path=receipts)
            self.assertEqual(merge["blockers"], [], merge)
            additions = [a for a in merge["actions"] if a["kind"] == "add_recording"]
            self.assertEqual([(a["source_slot"], a["destination_slot"]) for a in additions], [(1, 5)])
            proposed = merge["proposed_manifest"]
            self.assertEqual(proposed["recordings"][0], original_manifest["recordings"][0])
            addition = next(r for r in proposed["recordings"] if r["slot"] == 5)
            self.assertEqual(addition["file"], "hm_slot_05.wav")
            for key in CONTRACT_FIELDS:
                self.assertEqual(addition[key], row[key])
            self.assertEqual(addition["source"], row["source"])
            self.assertFalse(merge["writes_performed"])
            self.assertFalse(merge["runtime_verified"])
            self.assertEqual(snapshot(root), before)
            self.assertEqual(source.read_bytes(), b"synthetic conversion input; no provider")


if __name__ == "__main__":
    unittest.main()
