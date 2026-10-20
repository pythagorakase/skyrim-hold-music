"""Independent contract-review regressions; all data is synthetic and temporary."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music import contract_migration
from hold_music.runtime_contract import project_runtime_contract

STORAGE = "SKSE/Plugins/StorageUtilData/HoldMusic"
AUDIO = "Sound/fx/holdmusic"
OMIT = object()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def snapshot(root):
    return {
        path.relative_to(root).as_posix():
        (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
        for path in root.rglob("*") if path.is_file()
    }


def identity(performer="sven", revision="r1", region="whiterun"):
    request = dict(
        tradition=region, recipe_id="fixture/cittern", recipe_revision=revision,
        model_id="synthetic-fixture", instrument_family="plucked_string",
        instrument_name="cittern", arrangement="solo_lute", mode="instrumental", voice="none")
    return project_runtime_contract(dict(performer_id=performer, request=request))


def recording(slot, contract=None, **extra):
    result = dict(
        slot=slot, file=f"hm_slot_{slot:02d}.wav", performer_id="sven",
        region="whiterun", mode="instrumental", gender="male", duration_seconds=0.1,
        composition_id=f"fixture-{slot}", lyrics_sha256=None,
        recipe_id="historical-label", model_id="unknown",
        created_at="2026-10-20T00:00:00Z", playable=True,
        source={"kind": "import", "path_or_request_id": f"synthetic-{slot}"},
    )
    if contract is not None:
        result.update(deepcopy(contract))
    result.update(extra)
    return result


class ContractMigrationSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.mo2 = self.root / "mo2"
        self.mod = self.mo2 / "mods/Library"
        profile = self.mo2 / "profiles/pilot"
        profile.mkdir(parents=True)
        self.mod.mkdir(parents=True)
        (profile / "modlist.txt").write_text("+Library\n", encoding="utf-8")
        self.manifest_path = self.mod / STORAGE / "library.json"
        self.proposal = self.root / "proposal.json"
        self.old, self.new = identity(), identity(revision="r2")
        self.persist([recording(1, self.old), recording(2, self.new)],
                     {"version": 1, "contracts": [self.old]})
        write_json(self.proposal, {"version": 1, "contracts": [self.new]})

    def persist(self, rows, selection=OMIT):
        self.manifest = dict(version=1, slots=24, recordings=deepcopy(rows),
                             custom_extension={"keep": ["exact", None, 3]})
        if selection is not OMIT:
            self.manifest["runtime_selection"] = deepcopy(selection)
        write_json(self.manifest_path, self.manifest)
        for row in rows:
            if not isinstance(row, dict) or type(row.get("slot")) is not int:
                continue
            path = self.mod / AUDIO / f"hm_slot_{row['slot']:02d}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(path), "wb") as output:
                output.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                output.writeframes(b"\0\0" * 4410)

    def review(self, proposal=None):
        return contract_migration.review_contract_migration(
            self.mo2, "pilot", self.proposal if proposal is None else proposal)

    def assert_readonly(self, report):
        for field in ("installed", "vfs_verified", "runtime_verified", "writes_performed"):
            self.assertIs(report[field], False)

    def codes(self, report):
        return {row["code"] for row in report["blockers"]}

    def test_legacy_contract_addition_does_not_invent_identity_fields(self):
        self.persist([recording(1)])
        before = snapshot(self.root)
        report = self.review()
        self.assert_readonly(report)
        row = report["rows"][0]
        self.assertTrue(row["before"]["identity_eligible"])
        self.assertFalse(row["after"]["identity_eligible"])
        self.assertEqual(report["projected_manifest"]["recordings"], self.manifest["recordings"])
        for key in ("recipe_revision", "instrument_family", "instrument_name", "identity_key"):
            self.assertNotIn(key, report["projected_manifest"]["recordings"][0])
        self.assertIn("no_identity_eligible_recordings", self.codes(report))
        self.assertEqual(snapshot(self.root), before)

    def test_null_marker_on_another_region_row_suppresses_performer_legacy_route(self):
        for field in ("recipe_revision", "instrument_family", "instrument_name", "identity_key"):
            with self.subTest(field=field):
                rows = [recording(1), recording(2, region="rift", **{field: None})]
                self.persist(rows)
                report = self.review()
                self.assertEqual(report["projected_manifest"]["recordings"], rows)
                self.assertIn("invalid_projected_manifest", self.codes(report))
                self.assertEqual(len(report["rows"]), 2)
                for item in report["rows"]:
                    self.assertEqual(item["before"]["route"], "strict_missing_contract")
                    self.assertFalse(item["before"]["identity_eligible"])
                    self.assertFalse(item["after"]["identity_eligible"])

    def test_partial_and_malformed_rows_stay_visible_by_original_index(self):
        rows = [recording(1, recipe_revision="known-but-incomplete"), None,
                {"slot": 3, "performer_id": "sven", "unknown": ["keep", None]}, "not-an-object"]
        self.persist(rows)
        report = self.review()
        self.assertEqual(report["projected_manifest"]["recordings"], rows)
        self.assertEqual([item["index"] for item in report["rows"]], list(range(len(rows))))
        self.assertTrue(report["inspection_blockers"])
        self.assertTrue(report["projected_manifest_errors"])
        self.assertEqual(report["performers"][0]["row_indexes"], [0, 2])
        self.assertFalse(report["rows"][1]["after"]["identity_eligible"])
        self.assertFalse(report["rows"][3]["after"]["identity_eligible"])

    def test_malformed_existing_contract_cannot_be_repaired_by_upsert(self):
        for selection in (
            {"version": 1, "contracts": [dict(self.old, unknown="preserve")]},
            {"version": 1, "contracts": [self.old, self.old]},
            {"version": 1, "contracts": [self.old], "unsupported": "preserve"},
        ):
            with self.subTest(selection=selection):
                self.persist([recording(1, self.old), recording(2, self.new)], selection)
                before = snapshot(self.root)
                report = self.review()
                self.assertEqual(report["current_runtime_selection"], selection)
                self.assertIn("invalid_existing_selection", self.codes(report))
                self.assertFalse(report["projection_possible"])
                self.assertIsNone(report["projected_manifest"])
                for row in report["rows"]:
                    self.assertFalse(row["before"]["identity_eligible"])
                    self.assertFalse(row["after"]["identity_eligible"])
                self.assertEqual(snapshot(self.root), before)

    def test_case_only_performer_upsert_does_not_relabel_existing_recordings(self):
        alias = identity("SVEN", revision="r2")
        write_json(self.proposal, {"version": 1, "contracts": [alias]})
        before = snapshot(self.root)
        report = self.review()
        self.assertIn("performer_case_alias", self.codes(report))
        self.assertFalse(report["projection_possible"])
        self.assertIsNone(report["projected_manifest"])
        self.assertEqual(snapshot(self.root), before)

    def test_changed_region_reports_every_old_and_new_region_recording(self):
        new_region = identity(revision="r2", region="rift")
        rows = [recording(1, self.old), recording(2, new_region)]
        self.persist(rows, {"version": 1, "contracts": [self.old]})
        write_json(self.proposal, {"version": 1, "contracts": [new_region]})
        report = self.review()
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["performers"][0]["row_indexes"], [0, 1])
        self.assertTrue(report["rows"][0]["before"]["identity_eligible"])
        self.assertFalse(report["rows"][0]["after"]["identity_eligible"])
        self.assertFalse(report["rows"][1]["before"]["identity_eligible"])
        self.assertTrue(report["rows"][1]["after"]["identity_eligible"])
        self.assertEqual(report["projected_manifest"]["recordings"], rows)

    def test_identity_compatibility_does_not_hide_disabled_assets_or_receipt_reservations(self):
        rows = [recording(1, self.old), recording(2, self.new, playable=False)]
        self.persist(rows, {"version": 1, "contracts": [self.old]})
        write_json(self.mod / STORAGE / "receipts.json", {
            "version": 1, "performances": [{
                "id": "fixture:0", "slot": 2, "performer_id": "sven",
                "composition_id": "fixture-2", "save_id": "fixture-save",
                "world_id": "fixture-world", "at_hours": 10, "outcome": "interrupted",
            }],
        })
        report = self.review()
        row = report["rows"][1]
        self.assertTrue(row["after"]["identity_eligible"])
        self.assertFalse(row["after"]["metadata_eligible"])
        self.assertTrue(row["asset_valid"])
        self.assertIn("receipt_at_or_after_boundary", row["reservation_reasons"])
        self.assertFalse(row["live_session_locks_verified"])
        self.assertIn("no_available_asset_candidates", self.codes(report))

    def test_proposal_cannot_request_recording_edits_or_follow_embedded_file_paths(self):
        private = self.root / "not-an-authorized-proposal-input.txt"
        private.write_text("synthetic-private-payload", encoding="utf-8")
        proposal = {"version": 1, "contracts": [self.new],
                    "recordings": [{"file": str(private)}]}
        write_json(self.proposal, proposal)
        original_open = Path.open

        def guarded_open(path, *args, **kwargs):
            if path == private:
                raise AssertionError("Proposal must not authorize a payload read")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", guarded_open):
            report = self.review()
        self.assertIn("invalid_proposal", self.codes(report))
        self.assertIsNone(report["projected_manifest"])
        self.assertNotIn("synthetic-private-payload", json.dumps(report))

    def test_duplicate_proposal_keys_cannot_choose_alternate_upserts(self):
        self.proposal.write_text(
            '{"version":1,"contracts":[],"contracts":' + json.dumps([self.new]) + '}',
            encoding="utf-8")
        report = self.review()
        self.assertIn("invalid_proposal", self.codes(report))
        self.assertFalse(report["projection_possible"])

    def test_proposal_drift_after_inspection_invalidates_the_review(self):
        original = contract_migration.inspect_installed_library

        def changed_proposal(*args, **kwargs):
            result = original(*args, **kwargs)
            stamp = self.proposal.stat()
            raw = self.proposal.read_bytes()
            self.assertIn(b'"r2"', raw)
            self.proposal.write_bytes(raw.replace(b'"r2"', b'"r3"'))
            os.utime(self.proposal, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            return result

        with patch.object(contract_migration, "inspect_installed_library",
                          side_effect=changed_proposal):
            with self.assertRaisesRegex(ValueError, "changed during inspection"):
                self.review()

    def test_installed_input_drift_after_inspection_invalidates_the_review(self):
        original = contract_migration.inspect_installed_library

        def changed_manifest(*args, **kwargs):
            result = original(*args, **kwargs)
            stamp = self.manifest_path.stat()
            raw = self.manifest_path.read_bytes()
            self.manifest_path.write_bytes(raw.replace(b"synthetic-1", b"synthetic-9"))
            os.utime(self.manifest_path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            return result

        with patch.object(contract_migration, "inspect_installed_library",
                          side_effect=changed_manifest):
            with self.assertRaisesRegex(ValueError, "changed during inspection"):
                self.review()

    def test_hardlinked_proposal_is_not_accepted_as_an_unaliased_input(self):
        linked = self.root / "linked-proposal.json"
        try:
            os.link(self.proposal, linked)
        except OSError:
            self.skipTest("Filesystem does not support fixture hardlinks")
        with self.assertRaisesRegex(ValueError, "unaliased"):
            self.review(linked)


if __name__ == "__main__":
    unittest.main()
