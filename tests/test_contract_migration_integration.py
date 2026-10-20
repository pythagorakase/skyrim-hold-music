"""Contract changes are reviewable without relabeling or publishing recordings."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.contract_migration import review_contract_migration
from hold_music.library import Library
from hold_music.recording_identity import CONTRACT_FIELDS
from hold_music.runtime_contract import project_runtime_contract, runtime_identity_key

STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusic"
AUDIO = "Sound/fx/holdmusic"


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns,
            hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*") if p.is_file()}


class ContractMigrationIntegrationTests(unittest.TestCase):
    def test_revision_upsert_preserves_old_takes_other_performers_and_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            mo2 = root / "mo2"
            high, low, base = mo2 / "mods/High", mo2 / "mods/Low", root / "game/Data"
            for directory in (high, low, base, mo2 / "profiles/pilot"):
                directory.mkdir(parents=True)
            (mo2 / "profiles/pilot/modlist.txt").write_text("+High\n+Low\n", encoding="utf-8")
            audio = root / "synthetic.wav"
            with wave.open(str(audio), "wb") as wav:
                wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0\0" * 4410)

            def contract(performer, revision):
                request = dict(
                    tradition="whiterun", recipe_id="fixture/cittern", recipe_revision=revision,
                    model_id="synthetic-fixture", instrument_family="plucked_string",
                    instrument_name="cittern", arrangement="solo_lute", mode="instrumental", voice="none",
                )
                return project_runtime_contract(dict(performer_id=performer, request=request))

            old_sven, new_sven, mikael = contract("sven", "r1"), contract("sven", "r2"), contract("mikael", "r1")
            library = Library(root / "source-library")
            for index, (performer, identity) in enumerate((
                ("sven", old_sven), ("sven", new_sven), ("sven", None),
                ("mikael", mikael), ("faendal", None),
            ), start=1):
                fields = {key: identity[key] for key in CONTRACT_FIELDS} if identity else dict(
                    mode="instrumental", recipe_id="historical-label", model_id="unknown",
                )
                if identity:
                    fields["identity_key"] = runtime_identity_key(identity)
                library.add_recording(audio, performer_id=performer, region="whiterun", gender="male",
                    composition_id=f"fixture-{index}",
                    source={"kind": "import", "path_or_request_id": f"synthetic-{index}"}, **fields)

            original = deepcopy(library.load().manifest)
            original["runtime_selection"] = {"version": 1, "contracts": [old_sven, mikael]}
            original["fixture_extension"] = {"preserve": "unrecognized metadata"}
            manifest = low / STORAGE / "library.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps(original), encoding="utf-8")
            for row in original["recordings"]:
                target = high / AUDIO / row["file"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(library.root / row["file"], target)
            (high / AUDIO / "hm_slot_06.wav").write_bytes(b"retained orphan")
            receipts = {"version": 1, "performances": [{
                "id": "fixture:0", "slot": 2, "performer_id": "sven", "composition_id": "fixture-2",
                "save_id": "fixture-save", "world_id": "fixture-world", "at_hours": 10,
                "outcome": "interrupted",
            }]}
            (low / STORAGE / "receipts.json").write_text(json.dumps(receipts), encoding="utf-8")
            proposal = root / "proposal.json"
            proposal.write_text(json.dumps({"version": 1, "contracts": [new_sven]}), encoding="utf-8")
            before = snapshot(root)

            with patch("socket.create_connection", side_effect=AssertionError("Network forbidden")):
                report = review_contract_migration(mo2, "pilot", proposal, game_data=base)
            self.assertEqual(report["blockers"], [], report["blockers"])
            projected = report["projected_manifest"]
            self.assertEqual(projected["recordings"], original["recordings"])
            self.assertEqual(projected["fixture_extension"], original["fixture_extension"])
            self.assertEqual(projected["runtime_selection"]["contracts"], [new_sven, mikael])
            rows = {row["slot"]: row for row in report["rows"]}
            self.assertTrue(rows[1]["before"]["identity_eligible"])
            self.assertFalse(rows[1]["after"]["identity_eligible"])
            self.assertFalse(rows[2]["before"]["identity_eligible"])
            self.assertTrue(rows[2]["after"]["identity_eligible"])
            self.assertFalse(rows[3]["after"]["identity_eligible"])
            self.assertNotIn("recipe_revision", projected["recordings"][2])
            for slot in (4, 5):
                self.assertEqual(rows[slot]["before"], rows[slot]["after"])
                self.assertTrue(rows[slot]["after"]["identity_eligible"])
            self.assertIn("receipt_at_or_after_boundary", rows[2]["reservation_reasons"])
            for flag in ("installed", "vfs_verified", "runtime_verified", "writes_performed"):
                self.assertIs(report[flag], False)
            self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
