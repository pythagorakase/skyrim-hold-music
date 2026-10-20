"""The Python projection pins identities before case-insensitive Papyrus reads."""
from copy import deepcopy
import hashlib
import json
import unittest

from hold_music.runtime_contract import (
    RUNTIME_CONTRACT_FIELDS, manifest_runtime_selection_errors,
    project_runtime_contract, recording_contract_errors, runtime_contract_errors,
    recording_runtime_identity_errors, runtime_identity_key, runtime_selection_errors,
)


def fixture_decision():
    return dict(performer_id="sven", request=dict(
        tradition="whiterun", recipe_id="fixture/whiterun/cittern-v1",
        recipe_revision="offline-fixture-v1", model_id="synthetic-pcm-fixture",
        instrument_family="plucked_string", instrument_name="cittern",
        arrangement="solo_lute_and_voice", mode="lyrical", voice="male"))


class RuntimeContractTests(unittest.TestCase):
    def setUp(self):
        self.decision = fixture_decision()
        self.contract = project_runtime_contract(self.decision)

    def test_golden_projection_normalizes_only_lyrical_and_preserves_input(self):
        before = deepcopy(self.decision)
        self.assertEqual(self.contract, dict(
            performer_id="sven", region="whiterun",
            recipe_id="fixture/whiterun/cittern-v1", recipe_revision="offline-fixture-v1",
            model_id="synthetic-pcm-fixture", instrument_family="plucked_string",
            instrument_name="cittern", arrangement="solo_lute_and_voice",
            mode="vocal", voice="male",
            identity_key="7207d6f146bbdfbb709b3267e413a437ede5701a597436feff0e3f2931935c4f"))
        self.assertEqual(self.decision, before)
        self.assertEqual(runtime_contract_errors(self.contract), [])
        self.assertEqual(runtime_selection_errors(dict(version=1, contracts=[self.contract])), [])

    def test_digest_uses_exact_case_and_compact_unescaped_utf8_field_order(self):
        changed = dict(self.contract, instrument_name="qanbûs")
        expected_bytes = (
            '["sven","whiterun","fixture/whiterun/cittern-v1","offline-fixture-v1",'
            '"synthetic-pcm-fixture","plucked_string","qanbûs","solo_lute_and_voice",'
            '"vocal","male"]'
        ).encode("utf-8")
        self.assertEqual(runtime_identity_key(changed), hashlib.sha256(expected_bytes).hexdigest())
        self.assertNotEqual(runtime_identity_key(changed),
                            runtime_identity_key(dict(changed, instrument_name="Qanbûs")))
        self.assertNotEqual(runtime_identity_key(changed),
                            runtime_identity_key(dict(changed, instrument_name="qanbûs ")))

    def test_all_readable_fields_are_required_nonempty_text(self):
        for field in RUNTIME_CONTRACT_FIELDS:
            for value in (None, "", " \t", 1, True, [], {}):
                with self.subTest(field=field, value=value):
                    changed = dict(self.contract, **{field: value})
                    self.assertTrue(runtime_contract_errors(changed))
                    with self.assertRaises(ValueError):
                        runtime_identity_key(changed)
            missing = deepcopy(self.contract)
            missing.pop(field)
            self.assertTrue(runtime_contract_errors(missing))
        self.assertTrue(runtime_contract_errors(dict(self.contract, extra="unsupported")))

    def test_stale_or_missing_identity_keys_never_validate(self):
        for key in (None, "", "0" * 64, self.contract["identity_key"].upper(), [], 3):
            self.assertTrue(runtime_contract_errors(dict(self.contract, identity_key=key)))
        for field in RUNTIME_CONTRACT_FIELDS:
            changed = dict(self.contract, **{field: self.contract[field].upper()})
            self.assertTrue(runtime_contract_errors(changed), field)
        missing = deepcopy(self.contract)
        missing.pop("identity_key")
        self.assertTrue(runtime_contract_errors(missing))

    def test_supported_modes_require_coherent_animation_and_voice(self):
        for mode, arrangement, voice in (
            ("instrumental", "solo_lute", "none"),
            ("vocal", "solo_lute_and_voice", "male"),
            ("vocal", "solo_lute_and_voice", "female"),
            ("wordless", "solo_lute_and_voice", "male"),
            ("wordless", "solo_lute_and_voice", "female"),
        ):
            changed = dict(self.contract, mode=mode, arrangement=arrangement, voice=voice)
            changed["identity_key"] = runtime_identity_key(changed)
            self.assertEqual(runtime_contract_errors(changed), [])
        for changes in (
            dict(mode="instrumental"), dict(voice="none"), dict(voice="choir"),
            dict(arrangement="solo_lute"), dict(arrangement="duet"),
            dict(instrument_family="reedless_woodwind"), dict(mode="lyrical"),
        ):
            changed = dict(self.contract, **changes)
            changed["identity_key"] = runtime_identity_key(changed)
            self.assertTrue(runtime_contract_errors(changed), changes)

    def test_projection_requires_the_explicit_request_and_never_uses_recording_fallback(self):
        for field in self.decision["request"]:
            changed = deepcopy(self.decision)
            changed["recording"] = dict(self.contract)
            changed["request"].pop(field)
            with self.assertRaises(ValueError):
                project_runtime_contract(changed)
        for request in (None, [], "unknown", dict(self.decision["request"], unsupported="extra")):
            with self.assertRaises(ValueError):
                project_runtime_contract(dict(self.decision, request=request))
        unrelated = dict(self.decision, recording=dict(self.contract, instrument_name="lute"),
                         current_palette={"instrument_name": "guitar"})
        self.assertEqual(project_runtime_contract(unrelated), self.contract)

    def test_duplicate_performers_are_rejected_even_across_modes_regions_and_case(self):
        for changes in ({}, dict(region="rift"), dict(mode="wordless"),
                        dict(performer_id="SVEN"), dict(recipe_revision="next-revision")):
            other = dict(self.contract, **changes)
            other["identity_key"] = runtime_identity_key(other)
            errors = runtime_selection_errors(dict(version=1, contracts=[self.contract, other]))
            self.assertTrue(any("duplicate performer_id" in item for item in errors), errors)
        other = dict(self.contract, performer_id="lynly_star_sung", region="rift", voice="female")
        other["identity_key"] = runtime_identity_key(other)
        self.assertEqual(runtime_selection_errors(dict(version=1, contracts=[self.contract, other])), [])

    def test_every_entry_and_complete_root_are_validated(self):
        valid = dict(version=1, contracts=[self.contract])
        for value in (None, [], 1, {}, dict(valid, version=True), dict(valid, version=1.0),
                      dict(valid, version=2), dict(valid, contracts=[]),
                      dict(valid, contracts={}), dict(valid, extra=True)):
            self.assertTrue(runtime_selection_errors(value), value)
        errors = runtime_selection_errors(dict(version=1, contracts=[self.contract, None]))
        self.assertTrue(any("contracts[1]" in error for error in errors))
        self.assertEqual(valid, dict(version=1, contracts=[self.contract]))

    def test_optional_legacy_manifest_is_unchanged_but_cannot_claim_current_contract(self):
        legacy = dict(version=1, slots=24, recordings=[dict(performer_id="sven")])
        before = deepcopy(legacy)
        self.assertEqual(manifest_runtime_selection_errors(legacy), [])
        self.assertTrue(manifest_runtime_selection_errors(legacy, required=True))
        self.assertTrue(manifest_runtime_selection_errors(dict(legacy, runtime_selection=None)))
        self.assertEqual(legacy, before)
        current = dict(legacy, runtime_selection=dict(version=1, contracts=[self.contract]))
        self.assertEqual(manifest_runtime_selection_errors(current, required=True), [])

    def test_recording_matches_all_fields_and_its_own_independent_digest(self):
        row = dict(self.contract, file="hm_slot_01.wav", slot=1, gender="male")
        self.assertEqual(recording_contract_errors(row, self.contract), [])
        for field in RUNTIME_CONTRACT_FIELDS:
            with self.subTest(field=field):
                changed = dict(row, **{field: row[field] + "-changed"})
                changed["identity_key"] = runtime_identity_key(changed)
                self.assertTrue(recording_contract_errors(changed, self.contract))
        changed = dict(row, instrument_name="CITTERN")
        self.assertTrue(recording_contract_errors(changed, self.contract))
        # A matching readable source may lack or have an untrusted old key.
        # Staging may project it; publication must require its freshly stored key.
        for value in (None, "stale"):
            changed = dict(row, identity_key=value)
            self.assertEqual(recording_contract_errors(changed, self.contract, require_identity_key=False), [])
            self.assertTrue(recording_contract_errors(changed, self.contract))
        legacy = {key: value for key, value in row.items()
                  if key not in ("recipe_revision", "instrument_name", "instrument_family", "identity_key")}
        self.assertTrue(recording_contract_errors(legacy, self.contract, require_identity_key=False))

    def test_manifest_checks_all_projected_rows_but_allows_retained_other_revisions(self):
        previous = dict(self.contract, recipe_revision="older-revision")
        previous["identity_key"] = runtime_identity_key(previous)
        manifest = dict(version=1, recordings=[self.contract, previous],
                        runtime_selection=dict(version=1, contracts=[self.contract]))
        self.assertEqual(manifest_runtime_selection_errors(manifest, required=True), [])
        self.assertEqual(recording_runtime_identity_errors(previous), [])
        self.assertTrue(recording_contract_errors(previous, self.contract))
        for changed in (dict(previous, identity_key="stale"), dict(previous, recipe_revision=None),
                        dict(previous, performer_id="unconfigured")):
            candidate = dict(manifest, recordings=[self.contract, changed])
            self.assertTrue(manifest_runtime_selection_errors(candidate, required=True))
        unconfigured = dict(previous, performer_id="unconfigured")
        unconfigured["identity_key"] = runtime_identity_key(unconfigured)
        self.assertTrue(any("performer contract" in problem for problem in
                            manifest_runtime_selection_errors(dict(manifest, recordings=[unconfigured]))))
        # Source manifests without this extension remain accepted for projection.
        source = dict(version=1, recordings=[{key: value for key, value in previous.items()
                                             if key != "identity_key"}])
        self.assertEqual(manifest_runtime_selection_errors(source), [])
        self.assertTrue(manifest_runtime_selection_errors(source, required=True))

    def test_explicit_null_projection_markers_require_valid_identity_and_performer_contract(self):
        row = dict(performer_id="unconfigured", recipe_revision=None,
                   instrument_family=None, instrument_name=None)
        manifest = dict(version=1, recordings=[row],
                        runtime_selection=dict(version=1, contracts=[self.contract]))
        errors = manifest_runtime_selection_errors(manifest, required=True)
        self.assertTrue(any("identity_key" in error for error in errors), errors)
        self.assertTrue(any("requires a performer contract" in error for error in errors), errors)
        for field in ("recipe_revision", "instrument_family", "instrument_name", "identity_key"):
            with self.subTest(field=field):
                candidate = dict(manifest, recordings=[dict(performer_id="unconfigured", **{field: None})])
                self.assertTrue(manifest_runtime_selection_errors(candidate))


if __name__ == "__main__":
    unittest.main()
