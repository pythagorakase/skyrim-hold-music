"""Read-only library merge plans use synthetic flat libraries, never game files."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.library import Library
from hold_music.library_merge import plan_library_merge
from hold_music.recording_identity import CONTRACT_FIELDS
from hold_music.runtime_contract import RUNTIME_CONTRACT_FIELDS, runtime_identity_key


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def files(root):
    return {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in root.rglob("*") if path.is_file()}


class LibraryMergeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "staged"
        self.target = self.root / "destination"
        for path in (self.source, self.target):
            path.mkdir()
            write_json(path / "library.json", {"version": 1, "slots": 24, "recordings": []})
        self.audio = self.root / "synthetic.wav"
        with wave.open(str(self.audio), "wb") as stream:
            stream.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            stream.writeframes(b"\x00\x00" * 4410)
        self.add(self.source)

    def add(self, root, *, slot=None, performer="sven", composition="fixture-song",
            revision="fixture-v1", strict=True, lyrics=None):
        mode = "vocal" if lyrics is not None else "instrumental"
        identity = dict(performer_id=performer, region="whiterun", mode=mode,
                        recipe_id="whiterun/cittern", recipe_revision=revision,
                        model_id="synthetic-fixture", instrument_family="plucked_string",
                        instrument_name="cittern",
                        arrangement="solo_lute_and_voice" if lyrics is not None else "solo_lute",
                        voice="male" if lyrics is not None else "none")
        identity["identity_key"] = runtime_identity_key(identity)
        extra = {key: identity[key] for key in
                 ("recipe_revision", "instrument_family", "instrument_name",
                  "arrangement", "voice", "identity_key")} if strict else {}
        row = Library(root).add_recording(
            self.audio, slot=slot, performer_id=performer, region="whiterun", mode=mode,
            gender="male", composition_id=composition, recipe_id=identity["recipe_id"],
            model_id=identity["model_id"] if strict else "unknown",
            source={"kind": "import", "path_or_request_id": "synthetic-audio"},
            created_at="2026-10-20T00:00:00Z", lyrics=lyrics, **extra)
        if strict:
            manifest = read_json(root / "library.json")
            contracts = manifest.setdefault("runtime_selection", {"version": 1, "contracts": []})["contracts"]
            if not any(item["performer_id"] == performer for item in contracts):
                contracts.append(identity)
            write_json(root / "library.json", manifest)
        return row

    def plan(self, **kwargs):
        return plan_library_merge(self.source, self.target, **kwargs)

    def mutate(self, root, change):
        path = root / "library.json"
        value = read_json(path)
        change(value)
        write_json(path, value)

    def blocked(self, report, code=None):
        self.assertEqual(report["status"], "blocked", report)
        self.assertTrue(report["blockers"])
        self.assertEqual(report["actions"], [])
        self.assertIsNone(report["proposed_manifest"])
        self.assertFalse(report["writes_performed"])
        if code:
            self.assertIn(code, {row["code"] for row in report["blockers"]}, report)

    def receipts(self, slots, path=None):
        path = path or self.target / "receipts.json"
        write_json(path, {"version": 1, "performances": [
            {"id": f"receipt-{i}", "performer_id": "older-performer", "composition_id": "older-song",
             "slot": slot, "at_hours": i, "outcome": "interrupted",
             "save_id": "fixture-save", "world_id": "fixture-world"}
            for i, slot in enumerate(slots)]})
        return path

    def test_remaps_around_raw_locks_reservations_and_orphan_assets_without_writes(self):
        self.add(self.target, performer="other", composition="other-song", strict=False)
        self.mutate(self.target, lambda m: m.update(reserved_slots=[5], locked_slots=[6],
                                                  custom={"preserve": "exact"}))
        self.mutate(self.target, lambda m: m["recordings"][0].update(session_locked=True, playable=False))
        self.receipts([2])
        (self.target / "hm_slot_03.wav").write_bytes(b"orphan")
        (self.target / "hm_slot_04.lyrics.txt").write_text("orphan", encoding="utf-8")
        original = read_json(self.target / "library.json")
        before = files(self.root)
        with patch("socket.create_connection", side_effect=AssertionError("No network")), \
                patch("subprocess.run", side_effect=AssertionError("No processes")):
            result = self.plan()
        self.assertEqual(result["blockers"], [])
        added = next(a for a in result["actions"] if a["kind"] == "add_recording")
        self.assertEqual((added["source_slot"], added["destination_slot"]), (1, 7))
        self.assertEqual(result["proposed_manifest"]["recordings"][0], original["recordings"][0])
        self.assertEqual(result["proposed_manifest"]["custom"], original["custom"])
        self.assertEqual(set(result["reserved_slots"]), {"1", "2", "3", "4", "5", "6"})
        self.assertEqual(files(self.root), before)

    def test_snapshot_and_token_are_deterministic_and_bind_external_receipts(self):
        external = self.receipts([2], self.root / "current.json")
        first = self.plan(receipts_path=external)
        second = self.plan(receipts_path=external)
        self.assertEqual(first, second)
        self.receipts([2, 3], external)
        third = self.plan(receipts_path=external)
        self.assertNotEqual(first["review_token"], third["review_token"])
        self.assertNotEqual(first["snapshot_sha256"], third["snapshot_sha256"])
        self.assertTrue(any(row["path"] == str(external) for row in third["snapshot"]["files"]))

    def test_token_binds_unrelated_assets_and_missing_slot_paths(self):
        first = self.plan()
        (self.target / "operator-notes.txt").write_text("keep", encoding="utf-8")
        second = self.plan()
        self.assertNotEqual(first["review_token"], second["review_token"])
        self.assertTrue(any(row["path"].endswith("hm_slot_24.wav") and not row["exists"]
                            for row in second["snapshot"]["files"]))

    def test_default_boundary_reserves_all_receipts_explicit_boundary_releases_old_only(self):
        self.receipts([1, 2])
        default = self.plan()
        explicit = self.plan(session_receipt_index=1)
        self.assertEqual(default["actions"][0]["destination_slot"], 3)
        self.assertEqual(explicit["actions"][0]["destination_slot"], 1)
        self.assertEqual(explicit["reserved_slots"], {"2": ["receipt_at_or_after_boundary"]})
        self.assertNotEqual(default["review_token"], explicit["review_token"])

    def test_bad_boundaries_and_missing_explicit_receipts_are_rejected(self):
        for value in (-1, True, 1.5, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan(session_receipt_index=value)
        self.blocked(self.plan(session_receipt_index=1), "invalid_session_boundary")
        self.blocked(self.plan(receipts_path=self.root / "absent.json"), "missing_input")

    def test_malformed_receipt_row_and_duplicate_scoped_ids_block(self):
        path = self.receipts([1])
        original = read_json(path)
        for change in (lambda d: d["performances"].append(deepcopy(d["performances"][0])),
                       lambda d: d["performances"][0].update(slot=True),
                       lambda d: d.update(version=True),
                       lambda d: d.update(performances=None)):
            value = deepcopy(original)
            change(value)
            write_json(path, value)
            self.blocked(self.plan(), "invalid_history")

    def test_legacy_performer_cannot_receive_first_contract_implicitly(self):
        self.add(self.target, strict=False)
        self.blocked(self.plan(), "legacy_performer_contract_conflict")

    def test_existing_contract_cannot_be_switched(self):
        self.add(self.target, composition="another-song", revision="older-version")
        self.blocked(self.plan(), "runtime_contract_conflict")

    def test_same_contract_accepts_an_additional_composition(self):
        self.add(self.target, composition="another-song")
        original = read_json(self.target / "library.json")
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        self.assertEqual([a["kind"] for a in report["actions"]], ["add_recording"])
        self.assertEqual(report["proposed_manifest"]["runtime_selection"], original["runtime_selection"])

    def test_exact_duplicate_is_a_noop_but_distinct_take_under_same_request_is_added(self):
        self.add(self.target)
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["actions"], [])
        self.assertEqual(len(report["duplicates"]), 1)
        self.assertEqual(report["proposed_manifest"], read_json(self.target / "library.json"))
        audio = self.source / "hm_slot_01.wav"
        raw = bytearray(audio.read_bytes())
        raw[-1] = 1
        audio.write_bytes(raw)
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["duplicates"], [])
        self.assertEqual([a["kind"] for a in report["actions"]], ["add_recording"])
        self.assertEqual(report["actions"][0]["destination_slot"], 2)

    def test_two_staged_renditions_keep_distinct_audio_and_provenance(self):
        self.add(self.source, slot=2)
        audio = self.source / "hm_slot_02.wav"
        raw = bytearray(audio.read_bytes())
        raw[-1] = 1
        audio.write_bytes(raw)
        self.mutate(self.source, lambda m: m["recordings"][1]["source"].update(
            path_or_request_id="second-take-provenance"))
        original = read_json(self.source / "library.json")
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        recordings = [a for a in report["actions"] if a["kind"] == "add_recording"]
        self.assertEqual([a["destination_slot"] for a in recordings], [1, 2])
        self.assertNotEqual(recordings[0]["assets"][0]["sha256"], recordings[1]["assets"][0]["sha256"])
        self.assertEqual(report["proposed_manifest"]["recordings"], original["recordings"])

    def test_duplicate_source_identity_blocks_even_when_both_match_destination(self):
        self.add(self.target)
        self.add(self.source, slot=2)
        self.blocked(self.plan(), "duplicate_recording")

    def test_existing_duplicate_takes_are_preserved_and_match_lowest_slot(self):
        self.add(self.target, slot=7)
        self.add(self.target, slot=2)
        self.mutate(self.target, lambda m: m["recordings"].reverse())
        original = read_json(self.target / "library.json")
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["actions"], [])
        self.assertEqual(report["duplicates"][0]["destination_slot"], 2)
        self.assertEqual(report["proposed_manifest"], original)
        self.add(self.source, slot=2, performer="new-performer", composition="new-song")
        report = self.plan()
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["proposed_manifest"]["recordings"][:2], original["recordings"])

    def test_exact_identity_fields_must_match_staged_contract(self):
        path = self.source / "library.json"
        original = read_json(path)
        for field in RUNTIME_CONTRACT_FIELDS:
            with self.subTest(field=field):
                value = deepcopy(original)
                value["recordings"][0][field] += "-different"
                # A recomputed digest does not authorize changing the contract.
                value["recordings"][0]["identity_key"] = runtime_identity_key(value["recordings"][0])
                write_json(path, value)
                self.blocked(self.plan())
        write_json(path, original)

    def test_partial_and_missing_projection_never_downgrade_to_legacy(self):
        path = self.source / "library.json"
        original = read_json(path)
        for field in (*CONTRACT_FIELDS, "identity_key"):
            with self.subTest(field=field):
                value = deepcopy(original)
                value["recordings"][0].pop(field)
                write_json(path, value)
                self.blocked(self.plan())
        value = deepcopy(original)
        value.pop("runtime_selection")
        write_json(path, value)
        self.blocked(self.plan(), "invalid_runtime_selection")

    def test_invalid_root_duplicate_performer_and_unused_contract_block(self):
        path = self.source / "library.json"
        original = read_json(path)
        for selection in (None, {"version": True, "contracts": []},
                          {"version": 1, "contracts": []},
                          dict(original["runtime_selection"], extra="unknown")):
            value = deepcopy(original)
            value["runtime_selection"] = selection
            write_json(path, value)
            self.blocked(self.plan(), "invalid_runtime_selection")
        for performer, expected in (("SVEN", "invalid_runtime_selection"),
                                     ("unrepresented", "unused_staged_contract")):
            value = deepcopy(original)
            other = deepcopy(value["runtime_selection"]["contracts"][0])
            other["performer_id"] = performer
            other["identity_key"] = runtime_identity_key(other)
            value["runtime_selection"]["contracts"].append(other)
            write_json(path, value)
            self.blocked(self.plan(), expected)

    def test_versioned_destination_without_contract_blocks_without_inference(self):
        self.add(self.target, performer="other", composition="other")
        self.mutate(self.target, lambda m: m.pop("runtime_selection"))
        self.blocked(self.plan(), "invalid_runtime_selection")

    def test_nullable_legacy_identity_is_preserved_but_cannot_be_implicitly_activated(self):
        self.add(self.target, performer="other", composition="other", strict=False)
        self.mutate(self.target, lambda m: m["recordings"][0].update(
            recipe_revision=None, instrument_family=None, instrument_name=None))
        before = files(self.target)
        report = self.plan()
        self.blocked(report, "prospective_runtime_incompatibility")
        self.assertNotIn("invalid_runtime_selection", {item["code"] for item in report["blockers"]})
        self.assertEqual(files(self.target), before)

    def test_identity_key_null_cannot_be_treated_as_legacy_unknown(self):
        self.add(self.target, performer="other", composition="other", strict=False)
        self.mutate(self.target, lambda m: m["recordings"][0].update(identity_key=None))
        self.blocked(self.plan(), "invalid_runtime_selection")

    def test_unplayable_or_locked_staged_row_cannot_be_imported(self):
        path = self.source / "library.json"
        original = read_json(path)
        for changes, code in (({"playable": False}, "unplayable_staged_recording"),
                              ({"session_locked": True}, "locked_staged_recording"),
                              ({"session_locked": "false"}, "invalid_recording")):
            value = deepcopy(original)
            value["recordings"][0].update(changes)
            write_json(path, value)
            self.blocked(self.plan(), code)

    def test_audio_validation_rejects_malformed_missing_and_wrong_duration(self):
        audio = self.source / "hm_slot_01.wav"
        original = audio.read_bytes()
        for raw in (b"broken", original[:-2]):
            audio.write_bytes(raw)
            self.blocked(self.plan(), "invalid_audio")
        audio.unlink()
        self.blocked(self.plan(), "missing_audio")
        audio.write_bytes(original)
        self.mutate(self.source, lambda m: m["recordings"][0].update(duration_seconds=50))
        self.blocked(self.plan(), "invalid_audio")

    def test_lyrics_validation_and_exact_sidecar_remapping(self):
        other = self.root / "sung"
        other.mkdir()
        write_json(other / "library.json", {"version": 1, "slots": 24, "recordings": []})
        self.add(other, lyrics="A quiet road.\n")
        report = plan_library_merge(other, self.target)
        self.assertEqual(report["blockers"], [])
        assets = report["actions"][0]["assets"]
        self.assertEqual([asset["kind"] for asset in assets], ["audio", "lyrics"])
        sidecar = other / "hm_slot_01.lyrics.txt"
        sidecar.write_text("Changed words", encoding="utf-8")
        self.blocked(plan_library_merge(other, self.target), "invalid_lyrics")
        sidecar.unlink()
        self.blocked(plan_library_merge(other, self.target), "missing_lyrics")

    def test_full_destination_never_replaces_an_orphan(self):
        for slot in range(1, 25):
            (self.target / f"hm_slot_{slot:02d}.wav").write_bytes(b"preserve")
        before = files(self.target)
        self.blocked(self.plan(), "insufficient_slots")
        self.assertEqual(files(self.target), before)

    def test_overlapping_and_hard_linked_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            plan_library_merge(self.source, self.source)
        nested = self.source / "nested"
        nested.mkdir()
        with self.assertRaises(ValueError):
            plan_library_merge(self.source, nested)
        link = self.target / "alias.wav"
        try:
            os.link(self.source / "hm_slot_01.wav", link)
        except OSError:
            self.skipTest("Host does not support fixture hard links")
        with self.assertRaisesRegex(ValueError, "Hard-linked"):
            self.plan()

    def test_symlinked_input_is_rejected_when_platform_permits(self):
        alias = self.root / "alias"
        try:
            alias.symlink_to(self.source, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not permit fixture symlinks")
        with self.assertRaisesRegex(ValueError, "Symlink|junction"):
            plan_library_merge(alias, self.target)

    def test_concurrent_inventory_change_does_not_return_a_stale_review(self):
        from hold_music import library_merge
        original = library_merge.wav_info
        def mutate_after_read(path):
            info = original(path)
            (self.target / "late-file.txt").write_text("changed", encoding="utf-8")
            return info
        with patch.object(library_merge, "wav_info", side_effect=mutate_after_read):
            with self.assertRaisesRegex(ValueError, "inventory changed"):
                self.plan()

    def test_same_size_content_change_with_restored_timestamp_is_detected(self):
        from hold_music import library_merge
        original = library_merge.wav_info
        def mutate_after_read(path):
            info = original(path)
            stat = path.stat()
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 1
            path.write_bytes(raw)
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            return info
        with patch.object(library_merge, "wav_info", side_effect=mutate_after_read):
            with self.assertRaisesRegex(ValueError, "changed during planning"):
                self.plan()


if __name__ == "__main__":
    unittest.main()
