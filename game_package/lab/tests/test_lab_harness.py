"""Execute the compiled LAB PEX with mocked natives, never claim engine proof.

HOLD_MUSIC_TEST_BUILD points at the immutable production candidate build.
HM_LAB_BUILD points at the independently compiled lab build.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "game_package" / "tests"))
from pex_vm import VM, functions
from hold_music.runtime_contract import runtime_identity_key

LAB_BUILD = Path(os.environ.get("HM_LAB_BUILD", ROOT / "local" / "unbuilt-lab")).resolve()
CONTROL = "HoldMusicSELab/control.json"
REQUEST = "HoldMusicSELab/request.json"
RESULT = "HoldMusicSELab/result.json"
WORLD = "hold-music-se-lab"


class LabVM(VM):
    """The existing instruction interpreter, with lab-specific native mocks."""

    def __init__(self):
        self.timers = {}
        self.callers = []
        super().__init__()
        text = (LAB_BUILD / "disassembly" / "HM_LabHarness.pas").read_text()
        owner = "hm_labharness"
        self.scripts[owner] = functions(text)
        self.state[owner] = {}
        for name, _, value in re.findall(
            r"\.variable (\S+) (\S+).*?\.initialValue ([^\r\n]+)", text, re.S
        ):
            value = value.strip()
            if value.lower() in ("none", "true", "false"):
                parsed = {"none": None, "true": True, "false": False}[value.lower()]
            elif value.startswith('"'):
                parsed = json.loads(value)
            else:
                parsed = float(value) if "." in value else int(value)
            self.state[owner][name.lower()] = parsed
        for name in ("Library", "Config"):
            self.prop(owner, name, ("self", "hm_" + name.lower()))
        self.prop(owner, "HoldMusicQuest", ("quest", "HoldMusic"))
        self.prop(owner, "LocTypeInn", "LocTypeInn")
        for name in self.settings:
            self.prop(owner, name, ("global", name))
        self.prop("hm_config", "WorldId", WORLD)
        self.files.update({
            CONTROL: {"version": 1, "enabled": True, "world_id": WORLD},
            REQUEST: {"version": 1, "run_id": "run-001", "started_at_utc": "2026-10-20T12:00:00Z"},
            "HoldMusic/trace.json": {"version": 1, "entries": []},
        })
        contract = dict(
            performer_id="sven", region="whiterun", recipe_id="lab-tone",
            recipe_revision="fixture-v1", model_id="synthetic-fixture",
            instrument_family="plucked_string", instrument_name="lute",
            arrangement="solo_lute", mode="instrumental", voice="none",
        )
        contract["identity_key"] = runtime_identity_key(contract)
        self.files["HoldMusic/library.json"] = {
            "version": 1,
            "runtime_selection": {"version": 1, "contracts": [contract]},
            "recordings": [dict(
                contract, slot=1, composition_id="lab-tone-v1",
                playable=True, duration_seconds=8.0,
            )],
        }
        self.actors["P"]["location"] = "outside"
        self.candidates = ["Sven"]
        self.initial_settings = self.settings.copy()

    def run(self, owner, method, *params):
        self.callers.append((owner.lower(), method.lower()))
        try:
            return super().run(owner, method, *params)
        finally:
            self.callers.pop()

    def method(self, obj, name, args):
        if isinstance(obj, tuple) and obj[0] == "self":
            if name == "registerforsingleupdate":
                self.timers[obj[1]] = self.now + args[0]
                return None
            if name == "unregisterforupdate":
                self.timers.pop(obj[1], None)
                return None
            if name == "onlocationchange" and self.callers[-1][0] == "hm_labharness":
                self.effects.append(("injected_entry_setup",))
        if obj == ("quest", "HoldMusic") and name == "getalias":
            assert args == [0]
            return ("self", "hm_controller")
        if obj in (("marker", "stage"), ("marker", "audience")):
            if name == "getcurrentlocation":
                return "inn"
        if obj in ("P", "Sven") and name == "moveto":
            assert args[0] in (("marker", "stage"), ("marker", "audience"))
            old = self.actors[obj]["location"]
            self.actors[obj]["location"] = "inn"
            self.actors[obj]["cell"] = "inn-cell"
            self.effects.append(("move_fixture", obj, args[0]))
            if obj == "P":
                self.effects.append(("engine_location_change", old, "inn"))
                self.run("hm_controller", "OnLocationChange", old, "inn")
            return None
        return super().method(obj, name, args)

    def static(self, owner, name, args):
        if owner == "game" and name == "getformfromfile" and args[1] == "Skyrim.esm":
            placed = {0x13491: "Sven", 0x1027DA: ("marker", "stage"), 0x10FCB7: ("marker", "audience")}
            if args[0] in placed:
                return placed[args[0]]
        if owner == "stringutil" and name == "substring":
            return args[0][args[1]:] if args[2] == 0 else args[0][args[1]:args[1] + args[2]]
        if owner == "jsonutil" and name == "clearall":
            assert args[0] == RESULT, "Harness must never clear production JSON."
            self.files[args[0]] = {}
            return None
        return super().static(owner, name, args)

    def tick(self, seconds):
        end = self.now + seconds
        for _ in range(2000):
            pending = [(at, owner) for owner, at in self.timers.items() if at <= end + 1e-8]
            if not pending:
                self.now = end
                return
            at, owner = min(pending)
            self.now = at
            self.timers.pop(owner)
            self.run(owner, "OnUpdate")
        raise AssertionError("Timer loop limit")

    def lab(self, method):
        return self.run("hm_labharness", method)

    @property
    def result(self):
        return self.files.get(RESULT)

    def autorun(self, scenario):
        self.files[REQUEST].update(auto_run=True, scenario=scenario)
        self.lab("OnInit")
        self.tick(20.0)


class LabHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = [
            LAB_BUILD / "package" / "Scripts" / "HM_LabHarness.pex",
            LAB_BUILD / "disassembly" / "HM_LabHarness.pas",
        ]
        if not all(path.is_file() for path in required):
            if os.environ.get("HM_LAB_BUILD"):
                raise AssertionError("Explicit HM_LAB_BUILD is missing compiled harness artifacts.")
            raise unittest.SkipTest("Set HM_LAB_BUILD and HOLD_MUSIC_TEST_BUILD to compiled builds.")

    def test_no_request_autorun_flag_has_no_effects(self):
        vm = LabVM()
        before = copy.deepcopy(vm.files)
        vm.lab("OnInit")
        vm.tick(10)
        self.assertEqual(vm.files, before)
        self.assertFalse(vm.timers)

    def test_guard_requires_exact_lab_world_and_enabled_control(self):
        for mutation in ("wrong_world", "disabled", "malformed_version"):
            with self.subTest(mutation=mutation):
                vm = LabVM()
                if mutation == "wrong_world":
                    vm.prop("hm_config", "WorldId", "real-playthrough")
                elif mutation == "disabled":
                    vm.files[CONTROL]["enabled"] = False
                else:
                    vm.files[CONTROL]["version"] = True
                vm.lab("ArmAmbient")
                self.assertIsNone(vm.result)
                self.assertEqual(vm.settings, vm.initial_settings)
                self.assertFalse(vm.timers)

    def test_reused_request_id_does_not_replace_existing_result(self):
        vm = LabVM()
        original = {"run_id": "run-001", "status": "passed", "old": True}
        vm.files[RESULT] = copy.deepcopy(original)
        vm.lab("ArmAmbient")
        self.assertEqual(vm.result, original)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_missing_receipt_array_does_not_begin(self):
        vm = LabVM()
        vm.files["HoldMusic/receipts.json"] = {}
        vm.lab("ArmAmbient")
        self.assertIsNone(vm.result)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_ambient_real_entry_chain_completes_and_preserves_history_locks(self):
        vm = LabVM()
        old_receipt = {"performer_id": "other", "composition_id": "historic"}
        vm.receipts.append(old_receipt.copy())
        vm.lab("ArmAmbient")
        vm.enter()
        vm.tick(12)
        result = vm.result
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["receipt_baseline"], 1)
        self.assertEqual(result["receipt_index"], 1)
        for key in ("real_inn_entry", "production_scan", "eligible_owned_sven", "slot_selection",
                    "performance_start", "performance_stop", "receipt", "receipt_identity_key",
                    "cleanup_trace_and_receipt", "evidence_valid"):
            self.assertTrue(result["assertions"][key], key)
        self.assertEqual(vm.receipts[0], old_receipt)
        self.assertTrue(vm.state["hm_library"]["locked"][0])
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertTrue(result["globals_restored"])
        self.assertFalse(result["ambient_scheduling_bypassed"])
        self.assertNotIn(("injected_entry_setup",), vm.effects)
        self.assertFalse(vm.timers)

    def test_ambient_without_entry_times_out_without_false_pass(self):
        vm = LabVM()
        vm.lab("ArmAmbient")
        vm.tick(121)
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(vm.result["assertions"]["real_inn_entry"])
        self.assertFalse(vm.receipts)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_focused_complete_labels_bypass_and_restores_globals(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")
        self.assertTrue(vm.result["ambient_scheduling_bypassed"])
        self.assertTrue(vm.result["controller_entry_setup_injected"])
        self.assertFalse(vm.result["assertions"]["real_inn_entry"])
        self.assertFalse(vm.result["assertions"]["production_scan"])
        self.assertIn(("injected_entry_setup",), vm.effects)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_focused_interrupt_uses_stop_request_and_interrupted_receipt(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedInterrupt")
        vm.tick(8)
        self.assertEqual(vm.result["status"], "passed")
        self.assertEqual(vm.result["expected_outcome"], "interrupted")
        self.assertTrue(vm.result["assertions"]["stop_request_issued"])
        self.assertEqual(vm.receipts[-1]["outcome"], "interrupted")
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.state["hm_config"]["::stoprequested_var"])

    def test_opt_in_autorun_ambient_teleports_and_uses_real_event(self):
        vm = LabVM()
        vm.autorun("ambient-entry")
        self.assertEqual(vm.result["status"], "passed")
        self.assertTrue(vm.result["scripted_fixture_teleport"])
        self.assertTrue(vm.result["fixture_moved"])
        self.assertTrue(vm.result["assertions"]["real_inn_entry"])
        self.assertIn(("move_fixture", "Sven", ("marker", "stage")), vm.effects)
        self.assertIn(("move_fixture", "P", ("marker", "audience")), vm.effects)
        self.assertNotIn(("injected_entry_setup",), vm.effects)

    def test_opt_in_autorun_focused_interrupt(self):
        vm = LabVM()
        vm.autorun("focused-interrupt")
        self.assertEqual(vm.result["status"], "passed")
        self.assertTrue(vm.result["assertions"]["stop_request_issued"])
        self.assertTrue(vm.result["controller_entry_setup_injected"])

    def test_opt_in_autorun_unknown_scenario_never_moves_actor(self):
        vm = LabVM()
        vm.autorun("unknown")
        self.assertIsNone(vm.result)
        self.assertFalse(any(effect[0] == "move_fixture" for effect in vm.effects))

    def test_evidence_never_claims_audibility_or_visual_verification(self):
        vm = LabVM()
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "passed")
        self.assertFalse(vm.result["audio_audibility_verified"])
        self.assertFalse(vm.result["animation_visual_verified"])
        self.assertEqual(vm.result["run_id"], vm.files[REQUEST]["run_id"])
        self.assertEqual(vm.result["started_at_utc"], vm.files[REQUEST]["started_at_utc"])

    def test_cleanup_cancels_and_restores_without_passing(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.lab("Cleanup")
        self.assertEqual(vm.result["status"], "cancelled")
        self.assertEqual(vm.receipts[-1]["outcome"], "interrupted")
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.timers)
        before = copy.deepcopy(vm.result)
        vm.lab("Cleanup")
        self.assertEqual(vm.result, before)

    def test_changed_active_request_stops_and_restores(self):
        vm = LabVM()
        vm.lab("ArmAmbient")
        vm.files[REQUEST]["run_id"] = "run-002"
        vm.tick(1)
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.result["run_id"], "run-001")
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_changed_guard_stops_and_restores(self):
        vm = LabVM()
        vm.lab("ArmAmbient")
        vm.files[CONTROL]["enabled"] = False
        vm.tick(1)
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_failed_initial_result_save_never_enables_test(self):
        vm = LabVM()
        vm.save_failures.add(RESULT)
        vm.lab("ArmAmbient")
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.timers)
        self.assertFalse(vm.state["hm_labharness"]["active"])

    def test_trace_regression_fails_and_restores(self):
        vm = LabVM()
        vm.lab("ArmAmbient")
        vm.enter()
        vm.tick(2)
        vm.files["HoldMusic/trace.json"]["entries"] = []
        vm.tick(1)
        self.assertEqual(vm.result["status"], "failed")
        self.assertIn("regressed", vm.result["reason"])
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_malformed_runtime_receipts_fail_and_restore(self):
        vm = LabVM()
        vm.lab("ArmAmbient")
        vm.files["HoldMusic/receipts.json"]["performances"] = {}
        vm.tick(1)
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_wrong_receipt_identity_cannot_pass(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        # Drive the production stop while the harness is not polling.
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        vm.receipts[-1]["runtime_identity"]["identity_key"] = "0" * 64
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(vm.result["assertions"]["receipt_identity_key"])
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_second_run_preserves_session_slot_lock(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")
        vm.files[REQUEST]["run_id"] = "run-002"
        vm.lab("FocusedStart")
        self.assertEqual(vm.result["status"], "failed")
        self.assertIn("unlocked", vm.result["reason"])
        self.assertEqual(len(vm.receipts), 1)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_unversioned_recording_cannot_satisfy_strict_lab_scenario(self):
        vm = LabVM()
        row = vm.files["HoldMusic/library.json"]["recordings"][0]
        for name in ("recipe_revision", "instrument_family", "instrument_name", "identity_key"):
            row.pop(name)
        vm.files["HoldMusic/library.json"].pop("runtime_selection")
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        self.assertEqual(vm.result["status"], "failed")
        self.assertIn("projected", vm.result["reason"])
        self.assertFalse(vm.receipts)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_receipt_before_trace_snapshot_converges_on_later_poll(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        entries = vm.files["HoldMusic/trace.json"]["entries"]
        stop = entries.pop()
        self.assertEqual(stop["event"], "performance_stop")
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "running")
        self.assertTrue(vm.result["assertions"]["receipt"])
        self.assertFalse(vm.result["assertions"]["performance_stop"])
        entries.append(stop)
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "passed")

    def test_receipt_before_cleared_stop_flag_converges_on_later_poll(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        vm.prop("hm_config", "StopRequested", True)
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "running")
        self.assertFalse(vm.result["assertions"]["cleanup_trace_and_receipt"])
        vm.prop("hm_config", "StopRequested", False)
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "passed")

    def test_failed_global_readback_cannot_report_pass(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        normal_method = vm.method

        def reject_cap_restore(obj, name, args):
            if obj == ("global", "HM_SessionCap") and name == "setvalue" and args == [3.0]:
                return None
            return normal_method(obj, name, args)

        vm.method = reject_cap_restore
        vm.tick(12)
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(vm.result["globals_restored"])
        self.assertIn("read back", vm.result["reason"])
        vm.method = normal_method
        vm.lab("Cleanup")
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_receipt_save_stack_interleaving_does_not_stop_twice(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        normal_static = vm.static
        switched = False

        def switch_after_receipt_save(owner, name, args):
            nonlocal switched
            value = normal_static(owner, name, args)
            if not switched and owner == "jsonutil" and name == "save" and args[0] == "HoldMusic/receipts.json":
                switched = True
                vm.lab("OnUpdate")
            return value

        vm.static = switch_after_receipt_save
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        self.assertTrue(switched)
        self.assertEqual(vm.result["status"], "passed")
        self.assertEqual([row["outcome"] for row in vm.receipts], ["completed"])
        self.assertTrue(vm.result["assertions"]["production_stop_seen"])
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertIsNone(vm.state["hm_controller"]["performer"])

    def test_wrong_identity_during_receipt_save_does_not_stop_twice(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        normal_static = vm.static
        switched = False

        def switch_after_corrupt_receipt(owner, name, args):
            nonlocal switched
            value = normal_static(owner, name, args)
            if not switched and owner == "jsonutil" and name == "save" and args[0] == "HoldMusic/receipts.json":
                switched = True
                vm.receipts[-1]["runtime_identity"]["identity_key"] = "0" * 64
                vm.lab("OnUpdate")
            return value

        vm.static = switch_after_corrupt_receipt
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual([row["outcome"] for row in vm.receipts], ["completed"])
        self.assertEqual(vm.settings, vm.initial_settings)


if __name__ == "__main__":
    unittest.main()
