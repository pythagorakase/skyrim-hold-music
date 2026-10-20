"""Run identity selection against the explicit candidate's disassembled PEX."""
from copy import deepcopy
import hashlib
import json
import unittest

from pex_vm import VM


FIELDS = ("performer_id", "region", "recipe_id", "recipe_revision", "model_id",
          "instrument_family", "instrument_name", "arrangement", "mode", "voice")
VERSION_FIELDS = ("recipe_revision", "instrument_family", "instrument_name")
MISSING = object()


def identity_key(row):
    encoded = json.dumps([row[key] for key in FIELDS],
                         ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contract(**changes):
    row = dict(performer_id="mikael", region="whiterun",
               recipe_id="whiterun/instrumental", recipe_revision="revision-1",
               model_id="fixture-model", instrument_family="plucked_string",
               instrument_name="cittern", arrangement="solo_lute",
               mode="instrumental", voice="none")
    row.update(changes)
    row["identity_key"] = identity_key(row)
    return row


class RuntimeSelectionTests(unittest.TestCase):
    def strict(self, **changes):
        vm = VM()
        expected = contract(**changes)
        manifest = vm.files["HoldMusic/library.json"]
        manifest["runtime_selection"] = {"version": 1, "contracts": [deepcopy(expected)]}
        manifest["recordings"][0].update(expected, playable=True)
        return vm, manifest, expected

    def choose(self, vm, performer="mikael", region="whiterun", prefer="instrumental"):
        return vm.run("hm_library", "ChooseSlot", performer, region, prefer)

    def start(self, vm):
        vm.enter()
        vm.advance(15)
        self.assertIn(("play", 1, "Mikael"), vm.effects)

    def test_matching_projected_identity_starts_current_animation(self):
        vm, _, _ = self.strict(instrument_name="vihuela")
        self.start(vm)
        self.assertIn(("idle", "Mikael", "IdleLuteStart"), vm.effects)
        self.assertLess(vm.effects.index(("idle", "Mikael", "IdleLuteStart")),
                        vm.effects.index(("play", 1, "Mikael")))

    def test_each_readable_identity_axis_must_match(self):
        alternatives = dict(performer_id="other", region="rift", recipe_id="other/recipe",
                            recipe_revision="revision-2", model_id="other-model",
                            instrument_family="reedless_woodwind", instrument_name="vihuela",
                            arrangement="solo_flute", mode="wordless", voice="female")
        for field, value in alternatives.items():
            with self.subTest(field=field):
                vm, manifest, _ = self.strict()
                row = manifest["recordings"][0]
                row[field] = value
                # Keep the original key too: readable disagreement is rejected.
                self.assertEqual(self.choose(vm), 0)

    def test_case_only_change_is_rejected_by_independently_projected_key(self):
        self.assertTrue(VM.equal("cittern", "Cittern"))
        for field in FIELDS:
            with self.subTest(field=field):
                vm, manifest, _ = self.strict()
                row = manifest["recordings"][0]
                row[field] = row[field].upper()
                row["identity_key"] = identity_key(row)
                self.assertEqual(self.choose(vm), 0)

    def test_supplied_key_does_not_claim_raw_string_case_coherence(self):
        # BSFixedString has already lost case fidelity. Python validates this
        # raw-field/key disagreement before staging; Papyrus cannot rehash it.
        vm, manifest, _ = self.strict()
        manifest["recordings"][0]["instrument_name"] = "CITTERN"
        self.assertEqual(self.choose(vm), 1)

    def test_every_required_field_rejects_missing_null_blank_and_wrong_types(self):
        for target in ("recording", "contract"):
            for field in FIELDS:
                for value in (MISSING, None, "", " \t\r\n", 7, True, [], {}):
                    with self.subTest(target=target, field=field, value=value):
                        vm, manifest, _ = self.strict()
                        row = (manifest["recordings"][0] if target == "recording"
                               else manifest["runtime_selection"]["contracts"][0])
                        if value is MISSING:
                            del row[field]
                        else:
                            row[field] = value
                        self.assertEqual(self.choose(vm), 0)

    def test_missing_invalid_and_mismatched_keys_are_rejected(self):
        for target in ("recording", "contract"):
            for value in (MISSING, None, "", "a" * 63, "a" * 65, "g" * 64, [], 1):
                with self.subTest(target=target, value=value):
                    vm, manifest, _ = self.strict()
                    row = (manifest["recordings"][0] if target == "recording"
                           else manifest["runtime_selection"]["contracts"][0])
                    if value is MISSING:
                        del row["identity_key"]
                    else:
                        row["identity_key"] = value
                    self.assertEqual(self.choose(vm), 0)
        vm, manifest, _ = self.strict()
        manifest["recordings"][0]["identity_key"] = "0" * 64
        self.assertEqual(self.choose(vm), 0)

    def test_root_schema_and_contract_container_fail_closed_for_legacy(self):
        invalid = [None, False, 1, "bad", [], {}, {"version": 1, "contracts": []},
                   {"version": 1}, {"contracts": []},
                   *({"version": version, "contracts": []}
                     for version in (0, 2, 1.5, None, True, "1", {}, [])),
                   *({"version": 1, "contracts": value}
                     for value in (None, False, 1, "bad", {}))]
        for selection in invalid:
            with self.subTest(selection=selection):
                vm = VM()
                vm.files["HoldMusic/library.json"]["runtime_selection"] = selection
                self.assertEqual(self.choose(vm), 0)
                vm.enter()
                vm.advance(15)
                self.assertFalse(any(row[0] in ("idle", "play", "stop_vanilla")
                                     for row in vm.effects))

    def test_malformed_contract_entry_blocks_all_selection(self):
        for value in (None, False, 1, "", [], {}, {"performer_id": "other"}):
            with self.subTest(value=value):
                vm, manifest, _ = self.strict()
                manifest["runtime_selection"]["contracts"].append(value)
                self.assertEqual(self.choose(vm), 0)
                self.assertEqual(self.choose(vm, performer="sven"), 0)

    def test_malformed_recording_collection_or_entries_cannot_be_selected(self):
        for value in (None, False, 1, "", {}, [None], [False], [1], [""], [[]], [{}]):
            with self.subTest(value=value):
                vm, manifest, _ = self.strict()
                manifest["recordings"] = value
                self.assertEqual(self.choose(vm), 0)

    def test_duplicate_performer_contracts_fail_closed_including_case_aliases(self):
        for changed in ({}, {"mode": "wordless", "arrangement": "solo_lute_and_voice",
                             "voice": "male"}, {"performer_id": "MIKAEL"},
                        {"region": "rift"}):
            with self.subTest(changed=changed):
                vm, manifest, _ = self.strict()
                manifest["runtime_selection"]["contracts"].append(contract(**changed))
                self.assertEqual(self.choose(vm), 0)
                self.assertEqual(self.choose(vm, performer="sven"), 0)

    def test_unknown_root_or_contract_members_fail_closed(self):
        for target in ("root", "contract"):
            with self.subTest(target=target):
                vm, manifest, _ = self.strict()
                selection = manifest["runtime_selection"]
                row = selection if target == "root" else selection["contracts"][0]
                row["unexpected"] = "unsupported schema"
                self.assertEqual(self.choose(vm), 0)

    def test_contract_for_wrong_region_is_not_a_legacy_escape(self):
        vm, manifest, _ = self.strict()
        manifest["runtime_selection"]["contracts"][0] = contract(region="rift")
        self.assertEqual(self.choose(vm), 0)

    def test_any_version_field_presence_requires_contract_even_null_or_partial(self):
        for field in (*VERSION_FIELDS, "identity_key"):
            for value in (None, "", "value", False, [], {}):
                with self.subTest(field=field, value=value):
                    vm = VM()
                    manifest = vm.files["HoldMusic/library.json"]
                    bad = dict(manifest["recordings"][0], slot=3, region="rift")
                    bad[field] = value
                    manifest["recordings"].append(bad)
                    self.assertEqual(self.choose(vm), 0)
                    # The unrelated legacy performer is still usable.
                    self.assertEqual(self.choose(vm, performer="sven"), 2)

    def test_versioned_rows_without_matching_contract_never_fall_back(self):
        for selection in (MISSING, {"version": 1, "contracts": []},
                          {"version": 1, "contracts": [contract(performer_id="other")]}):
            with self.subTest(selection=selection):
                vm, manifest, _ = self.strict()
                legacy = {"slot": 3, "performer_id": "mikael", "region": "whiterun",
                          "mode": "instrumental", "duration_seconds": 6, "composition_id": "legacy"}
                manifest["recordings"].append(legacy)
                if selection is MISSING:
                    del manifest["runtime_selection"]
                else:
                    manifest["runtime_selection"] = selection
                self.assertEqual(self.choose(vm), 0)

    def test_explicit_contract_never_adopts_legacy_or_incompatible_rows(self):
        vm, manifest, _ = self.strict()
        legacy = VM().files["HoldMusic/library.json"]["recordings"][0]
        manifest["recordings"] = [legacy]
        self.assertEqual(self.choose(vm), 0)
        vm, manifest, _ = self.strict()
        manifest["recordings"][0]["recipe_revision"] = "outdated"
        manifest["recordings"].append(dict(legacy, slot=3))
        self.assertEqual(self.choose(vm), 0)

    def test_supported_mode_voice_and_arrangement_combinations(self):
        for mode, arrangement, voice in (
                ("instrumental", "solo_lute", "none"),
                ("vocal", "solo_lute_and_voice", "male"),
                ("vocal", "solo_lute_and_voice", "female"),
                ("wordless", "solo_lute_and_voice", "male"),
                ("wordless", "solo_lute_and_voice", "female")):
            with self.subTest(mode=mode, voice=voice):
                vm, _, _ = self.strict(mode=mode, arrangement=arrangement, voice=voice)
                self.assertEqual(self.choose(vm), 1)

    def test_unsupported_family_mode_voice_and_arrangement_are_rejected(self):
        for changes in (
                {"instrument_family": "reedless_woodwind"}, {"instrument_family": "percussion"},
                {"arrangement": "solo_flute"}, {"arrangement": "solo_lute_and_voice"},
                {"voice": "male"}, {"mode": "lyrical"}, {"mode": "other"},
                {"mode": "vocal", "arrangement": "solo_lute_and_voice", "voice": "none"},
                {"mode": "wordless", "arrangement": "solo_lute_and_voice", "voice": "choir"}):
            with self.subTest(changes=changes):
                vm, _, _ = self.strict(**changes)
                self.assertEqual(self.choose(vm), 0)

    def test_strict_playable_must_be_boolean_true(self):
        for value in (MISSING, None, False, 0, 1, "true", [], {}):
            with self.subTest(value=value):
                vm, manifest, _ = self.strict()
                if value is MISSING:
                    del manifest["recordings"][0]["playable"]
                else:
                    manifest["recordings"][0]["playable"] = value
                self.assertEqual(self.choose(vm), 0)

    def test_legacy_behavior_and_other_performer_survive_valid_contracts(self):
        vm = VM()
        self.assertEqual(self.choose(vm), 1)
        vm.files["HoldMusic/library.json"]["runtime_selection"] = {
            "version": 1, "contracts": [contract(performer_id="other")]}
        self.assertEqual(self.choose(vm), 1)
        vm, _, _ = self.strict()
        self.assertEqual(self.choose(vm, performer="sven"), 2)
        vm.candidates = ["Sven"]
        vm.enter()
        vm.advance(15)
        vm.advance(6)
        self.assertNotIn("runtime_identity", vm.receipts[0])

    def test_strict_oldest_unperformed_and_session_locks_are_preserved(self):
        vm, manifest, _ = self.strict()
        row = manifest["recordings"][0]
        manifest["recordings"].extend([dict(row, slot=3, composition_id="c3"),
                                       dict(row, slot=4, composition_id="c4")])
        vm.receipts.extend([{"composition_id": "c1"}, {"composition_id": "c3"}])
        self.assertEqual(self.choose(vm), 4)
        vm.run("hm_library", "LockSlot", 4)
        self.assertEqual(self.choose(vm), 1)
        vm.run("hm_library", "LockSlot", 1)
        self.assertEqual(self.choose(vm), 3)
        vm.run("hm_library", "LockSlot", 3)
        self.assertEqual(self.choose(vm), 0)

    def test_receipt_captures_selected_identity_before_metadata_changes(self):
        vm, manifest, expected = self.strict()
        self.start(vm)
        manifest["recordings"][0].update(contract(instrument_name="vihuela"))
        manifest["runtime_selection"]["contracts"][0] = contract(instrument_name="vihuela")
        vm.advance(6)
        receipt = vm.receipts[0]
        self.assertEqual(receipt["runtime_identity"], dict(version=1, **expected))
        self.assertEqual(receipt["outcome"], "completed")
        self.assertEqual(receipt["composition_id"], "c1")

    def test_load_cleanup_keeps_selected_identity_and_locks(self):
        vm, manifest, expected = self.strict()
        self.start(vm)
        del manifest["runtime_selection"]
        vm.run("hm_controller", "OnPlayerLoadGame")
        self.assertEqual(vm.receipts[0]["runtime_identity"], dict(version=1, **expected))
        self.assertEqual(vm.receipts[0]["outcome"], "interrupted")
        self.assertTrue(vm.state["hm_library"]["locked"][0])
        vm.run("hm_controller", "OnPlayerLoadGame")
        self.assertEqual(len(vm.receipts), 1)

    def test_strict_to_legacy_selection_clears_receipt_identity(self):
        vm, _, _ = self.strict()
        self.start(vm)
        vm.advance(6)
        vm.candidates = ["Sven"]
        vm.enter()
        vm.advance(15)
        vm.advance(6)
        self.assertEqual(len(vm.receipts), 2)
        self.assertIn("runtime_identity", vm.receipts[0])
        self.assertNotIn("runtime_identity", vm.receipts[1])

    def test_missing_receipt_and_trace_arrays_are_initialized_at_zero(self):
        vm, _, expected = self.strict()
        vm.files["HoldMusic/receipts.json"] = {}
        vm.files["HoldMusic/trace.json"] = {}
        self.start(vm)
        vm.advance(6)
        self.assertEqual(len(vm.receipts), 1)
        self.assertEqual(vm.receipts[0]["runtime_identity"], dict(version=1, **expected))
        entries = vm.files["HoldMusic/trace.json"]["entries"]
        self.assertIsInstance(entries, list)
        self.assertEqual(entries[0]["seq"], 1)
        self.assertEqual(entries[0]["event"], "location_enter")


if __name__ == "__main__":
    unittest.main()
