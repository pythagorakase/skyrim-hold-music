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
        self.settings["GameHour"] = 8.0
        self.intro_stage = 0
        self.intro_done = set()
        self.intro_running = False
        self.intro_playing = False
        self.intro_cleanup_succeeds = True
        self.main_quest_stage = 0
        self.story_trigger_enabled = True
        self.fixture_alias = None
        self.hold_package_enabled = True
        self.fixture_package = 0xEA072
        self.initial_settings = self.settings.copy()

    def run(self, owner, method, *params):
        self.callers.append((owner.lower(), method.lower()))
        try:
            return super().run(owner, method, *params)
        finally:
            self.callers.pop()

    def method(self, obj, name, args):
        if isinstance(obj, tuple) and obj[0] == "self":
            if obj[1] == "hm_labharness" and name == "getalias":
                assert args == [0]
                return ("alias", "fixture")
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
        if obj == ("alias", "fixture"):
            if name == "getreference":
                return self.fixture_alias
            if name == "forcerefto":
                self.fixture_alias = args[0]
                self.effects.append(("hold_force", args[0]))
                return None
            if name == "clear":
                self.effects.append(("hold_clear", self.fixture_alias))
                self.fixture_alias = None
                return None
        if obj == ("quest", "intro"):
            if name == "getstage":
                return self.intro_stage
            if name == "getstagedone":
                return args[0] in self.intro_done
            if name == "isrunning":
                return self.intro_running
            if name == "setstage":
                assert args == [20], "Only inspected intro cleanup is permitted."
                if not self.intro_running:
                    self.effects.append(("intro_stage_refused_outside_story_manager", 20))
                    return False
                self.effects.append(("intro_stage", 20))
                if self.intro_cleanup_succeeds:
                    self.intro_done.update((10, 20))
                    self.intro_stage = 20
                    self.intro_running = False
                    self.intro_playing = False
                return self.intro_cleanup_succeeds
        if obj == ("quest", "MQ102"):
            assert name == "getstage", "The lab may only read MQ102."
            return self.main_quest_stage
        if obj == ("scene", "intro") and name == "isplaying":
            return self.intro_playing
        if obj == "Sven" and name == "evaluatepackage":
            self.effects.append(("evaluate_fixture_package",))
            if self.fixture_alias == "Sven" and self.hold_package_enabled:
                self.fixture_package = 0x10FB3F
            elif not self.intro_running and not self.intro_playing and self.settings["GameHour"] == 18.0:
                self.fixture_package = 0x1CB1B
            elif not self.intro_running and not self.intro_playing:
                self.fixture_package = 0x36C1B
            return None
        if obj == "Sven" and name == "getcurrentpackage":
            return ("package", self.fixture_package)
        if isinstance(obj, tuple) and obj[0] == "package" and name == "getformid":
            return obj[1]
        if obj == ("global", "GameHour") and name == "setvalue":
            self.effects.append(("set_game_hour", args[0]))
        if obj in (("marker", "stage"), ("marker", "audience")):
            if name == "getcurrentlocation":
                return "inn"
        if obj == "riverwood":
            if name == "getformid":
                return 0x13163
            if name == "haskeyword":
                return False
        if obj == "P" and name == "moveto" and args[0] == ("marker", "exterior"):
            old = self.actors["P"]["location"]
            self.actors["P"].update(location="riverwood", cell="riverwood-cell")
            self.effects.append(("move_story_fixture", "P", args[0]))
            self.effects.append(("engine_location_change", old, "riverwood"))
            self.run("hm_controller", "OnLocationChange", old, "riverwood")
            if (self.story_trigger_enabled and self.main_quest_stage < 50 and 10 not in self.intro_done
                    and 8.0 <= self.settings["GameHour"] <= 20.0):
                self.intro_running = self.intro_playing = True
                self.effects.append(("story_manager_intro_start",))
            return None
        if obj == "Sven" and name == "getformid":
            return 0x13491
        if obj == "Sven" and name == "getdistance":
            assert args == ["P"]
            return 300.0
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
            placed = {
                0x13491: "Sven", 0x1027DA: ("marker", "stage"), 0x10FCB7: ("marker", "audience"),
                0x954D9: ("quest", "intro"), 0x954DA: ("scene", "intro"), 0x38: ("global", "GameHour"),
                0x4E50D: ("quest", "MQ102"), 0x96595: ("marker", "exterior"), 0x13163: "riverwood",
                0x10FB3F: ("package", 0x10FB3F),
            }
            if args[0] in placed:
                return placed[args[0]]
        if owner == "utility" and name == "wait":
            self.effects.append(("setup_wait", args[0]))
            self.now += args[0]
            return None
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
                self.now = max(self.now, end)
                return
            at, owner = min(pending)
            self.now = max(self.now, at)
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
        self.assertTrue(vm.result["assertions"]["requested_interruption_guard"])
        self.assertEqual(vm.receipts[-1]["outcome"], "interrupted")
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.state["hm_config"]["::stoprequested_var"])

    def test_delayed_interrupt_poll_cannot_relabel_completed_receipt(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedInterrupt")
        # The production stack runs while the lab's first poll is delayed.
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.result["expected_outcome"], "interrupted")
        self.assertEqual([row["outcome"] for row in vm.receipts], ["completed"])
        self.assertFalse(vm.result["assertions"]["stop_request_issued"])
        self.assertTrue(vm.result["interrupt_window_missed"])
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.state["hm_config"]["::stoprequested_var"])

    def test_unrelated_early_interruption_cannot_pass_requested_interrupt(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedInterrupt")
        vm.actors["Sven"]["combat"] = True
        vm.now += 0.5
        vm.run("hm_controller", "OnUpdate")
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual([row["outcome"] for row in vm.receipts], ["interrupted"])
        self.assertFalse(vm.result["assertions"]["stop_request_issued"])
        self.assertIn("before the lab issued", vm.result["reason"])
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_manual_interrupt_after_observed_completion_does_not_relabel_it(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        vm.lab("CollectEvidence")
        vm.lab("Interrupt")
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "passed")
        self.assertEqual(vm.result["expected_outcome"], "completed")
        self.assertFalse(vm.result["assertions"]["stop_request_issued"])
        self.assertEqual([row["outcome"] for row in vm.receipts], ["completed"])
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

    def test_disposable_setup_requires_explicit_boolean_and_autorun(self):
        for flag in (None, False, "true", 1):
            with self.subTest(flag=flag):
                vm = LabVM()
                if flag is not None:
                    vm.files[CONTROL]["allow_disposable_world_setup"] = flag
                vm.autorun("focused-complete")
                self.assertEqual(vm.result["status"], "passed")
                self.assertFalse(vm.result["disposable_world_setup"])
                self.assertFalse(any(e[0] in ("intro_stage", "set_game_hour", "evaluate_fixture_package") for e in vm.effects))
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        self.assertFalse(vm.lab("PrepareDisposableWorld"))
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")
        self.assertFalse(any(e[0] in ("intro_stage", "set_game_hour") for e in vm.effects))

    def test_disposable_setup_uses_authored_cleanup_then_inn_hour_and_restores_hour(self):
        for scenario in ("ambient-entry", "focused-complete", "focused-interrupt"):
            with self.subTest(scenario=scenario):
                vm = LabVM()
                vm.files[CONTROL]["allow_disposable_world_setup"] = True
                vm.autorun(scenario)
                self.assertEqual(vm.result["status"], "passed")
                setup = vm.result["world_setup"]
                self.assertTrue(setup["baseline_observed"])
                self.assertTrue(setup["ready"])
                self.assertEqual(setup["game_hour_before"], 8.0)
                self.assertEqual(setup["game_hour_configured"], 18.0)
                self.assertEqual(setup["game_hour_current"], 8.0)
                self.assertTrue(setup["game_hour_restored"])
                self.assertTrue(setup["intro_stage10_after"])
                self.assertFalse(setup["intro_running_after"])
                self.assertFalse(setup["intro_scene_playing_after"])
                self.assertEqual(setup["package_after_evaluate"], 0x1CB1B)
                self.assertFalse(setup["quest_history_restored"])
                self.assertFalse(setup["normal_quest_playthrough_verified"])
                self.assertIn(10, vm.intro_done)
                self.assertEqual(vm.settings, vm.initial_settings)
                events = [e[0] for e in vm.effects]
                self.assertLess(events.index("set_game_hour"), events.index("move_story_fixture"))
                self.assertLess(events.index("move_story_fixture"), events.index("story_manager_intro_start"))
                self.assertLess(events.index("story_manager_intro_start"), events.index("intro_stage"))
                self.assertLess(events.index("set_game_hour"), events.index("evaluate_fixture_package"))
                self.assertLess(events.index("evaluate_fixture_package"), events.index("move_fixture"))

    def test_disposable_setup_already_clean_quest_does_not_repeat_its_stage(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.intro_done.add(10)
        vm.intro_stage = 10
        vm.intro_running = vm.intro_playing = False
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "passed")
        self.assertFalse(any(e[0] == "intro_stage" for e in vm.effects))

    def test_disposable_setup_cleanup_failure_is_bounded_before_inn_or_playback(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.intro_cleanup_succeeds = False
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(len([e for e in vm.effects if e[0] == "setup_wait"]), 20)
        self.assertFalse(any(e[0] in ("move_fixture", "play") for e in vm.effects))
        self.assertEqual([e for e in vm.effects if e[0] == "set_game_hour"], [("set_game_hour", 18.0), ("set_game_hour", 8.0)])
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_disposable_setup_cancellation_during_each_latent_wait_cannot_resume(self):
        for intro_success in (False, True):
            with self.subTest(intro_success=intro_success):
                vm = LabVM()
                vm.files[CONTROL]["allow_disposable_world_setup"] = True
                vm.intro_cleanup_succeeds = intro_success
                normal_static = vm.static
                cancelled = False
                cancellation_result = None

                def cancel_during_wait(owner, name, args):
                    nonlocal cancelled, cancellation_result
                    value = normal_static(owner, name, args)
                    if not cancelled and owner == "utility" and name == "wait":
                        cancelled = True
                        vm.lab("Cleanup")
                        cancellation_result = copy.deepcopy(vm.result)
                    return value

                vm.static = cancel_during_wait
                vm.autorun("focused-complete")
                self.assertTrue(cancelled)
                self.assertEqual(vm.result["status"], "cancelled")
                self.assertEqual(vm.result, cancellation_result)
                self.assertFalse(any(e[0] in ("move_fixture", "play") for e in vm.effects))
                self.assertEqual(vm.settings, vm.initial_settings)
                self.assertFalse(vm.timers)

    def test_disposable_setup_changed_request_or_opt_in_after_wait_fails_closed(self):
        for change in ("request", "allow", "enabled", "auto_run"):
            with self.subTest(change=change):
                vm = LabVM()
                vm.files[CONTROL]["allow_disposable_world_setup"] = True
                normal_static = vm.static

                def revoke_during_wait(owner, name, args):
                    value = normal_static(owner, name, args)
                    if owner == "utility" and name == "wait":
                        if change == "request":
                            vm.files[REQUEST]["run_id"] = "other-run"
                        elif change == "auto_run":
                            vm.files[REQUEST]["auto_run"] = False
                        else:
                            vm.files[CONTROL]["allow_disposable_world_setup" if change == "allow" else "enabled"] = False
                    return value

                vm.static = revoke_during_wait
                vm.autorun("focused-complete")
                self.assertEqual(vm.result["status"], "failed")
                self.assertFalse(any(e[0] == "move_fixture" for e in vm.effects))
                self.assertEqual(vm.settings, vm.initial_settings)

    def test_disposable_setup_deadline_is_separate_and_bounded(self):
        for extra_delay in (15.0, 91.0):
            with self.subTest(extra_delay=extra_delay):
                vm = LabVM()
                vm.files[CONTROL]["allow_disposable_world_setup"] = True
                normal_static = vm.static

                def slow_setup(owner, name, args):
                    value = normal_static(owner, name, args)
                    if owner == "utility" and name == "wait":
                        vm.now += extra_delay
                    return value

                vm.static = slow_setup
                vm.autorun("focused-complete")
                vm.tick(30)
                self.assertEqual(vm.settings, vm.initial_settings)
                if extra_delay < 90:
                    self.assertEqual(vm.result["status"], "passed")
                    setup = vm.result["world_setup"]
                    self.assertEqual(vm.result["focused_preparation_deadline_real_seconds"], setup["setup_finished_real_seconds"] + 90)
                    self.assertEqual(setup["scenario_deadline_real_seconds"], vm.result["performance_start_trace_real_seconds"] + 8 + 20)
                    self.assertGreater(setup["setup_finished_real_seconds"], vm.result["started_real_seconds"] + 15)
                else:
                    self.assertEqual(vm.result["status"], "failed")
                    self.assertFalse(any(e[0] == "move_fixture" for e in vm.effects))

    def test_disposable_setup_hour_write_or_restore_failure_cannot_pass(self):
        for rejected_hour in (18.0, 8.0):
            with self.subTest(rejected_hour=rejected_hour):
                vm = LabVM()
                vm.files[CONTROL]["allow_disposable_world_setup"] = True
                normal_method = vm.method

                def reject_hour(obj, name, args):
                    if obj == ("global", "GameHour") and name == "setvalue" and args == [rejected_hour]:
                        return None
                    return normal_method(obj, name, args)

                vm.method = reject_hour
                vm.autorun("focused-complete")
                self.assertEqual(vm.result["status"], "failed")
                if rejected_hour == 18.0:
                    self.assertFalse(any(e[0] in ("evaluate_fixture_package", "move_fixture") for e in vm.effects))
                    self.assertEqual(vm.settings, vm.initial_settings)
                else:
                    self.assertFalse(vm.result["globals_restored"])
                    self.assertFalse(vm.result["world_setup"]["game_hour_restored"])
                    vm.method = normal_method
                    vm.lab("Cleanup")
                    self.assertEqual(vm.settings, vm.initial_settings)

    def test_disposable_setup_does_not_override_actor_eligibility(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.actors["Sven"]["sit"] = 3
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertTrue(vm.result["world_setup"]["ready"])
        self.assertEqual(vm.result["fixture_diagnostics"]["sit_state"], 3)
        self.assertFalse(vm.receipts)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_disposable_setup_failed_baseline_save_precedes_quest_and_time_mutation(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        normal_static = vm.static
        rejected = False

        def reject_baseline_save(owner, name, args):
            nonlocal rejected
            value = normal_static(owner, name, args)
            if (not rejected and owner == "jsonutil" and name == "save" and args[0] == RESULT
                    and vm.state["hm_labharness"]["worldbaselineobserved"]):
                rejected = True
                return False
            return value

        vm.static = reject_baseline_save
        vm.autorun("focused-complete")
        self.assertTrue(rejected)
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(any(e[0] in ("intro_stage", "set_game_hour", "move_fixture") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_disposable_setup_missing_form_does_not_reuse_previous_baseline(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.state["hm_labharness"]["oldgamehour"] = 22.0
        normal_static = vm.static

        def missing_intro(owner, name, args):
            if owner == "game" and name == "getformfromfile" and args == [0x954D9, "Skyrim.esm"]:
                return None
            return normal_static(owner, name, args)

        vm.static = missing_intro
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(vm.result["world_setup"]["baseline_observed"])
        self.assertEqual(vm.result["world_setup"]["game_hour_before"], 0.0)
        self.assertFalse(any(e[0] in ("intro_stage", "set_game_hour", "move_fixture") for e in vm.effects))

    def test_game_hour_readback_allows_only_documented_clock_tolerance(self):
        vm = LabVM()
        for difference, expected in ((0.049, True), (-0.049, True), (0.06, False), (-0.06, False)):
            with self.subTest(difference=difference):
                self.assertEqual(vm.run("hm_labharness", "HourNear", 8.0 + difference, 8.0), expected)

    def test_fresh_stopped_event_quest_requires_exterior_story_start_before_stage(self):
        vm = LabVM()
        self.assertFalse(vm.intro_running)
        self.assertFalse(vm.method(("quest", "intro"), "setstage", [20]))
        self.assertNotIn(10, vm.intro_done)
        vm.effects.clear()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "passed")
        setup = vm.result["world_setup"]
        self.assertFalse(setup["intro_running_before"])
        self.assertTrue(setup["story_entry_attempted"])
        self.assertTrue(setup["story_entry_observed"])
        self.assertTrue(setup["intro_running_observed"])
        self.assertFalse(setup["intro_natural_completion_observed"])
        self.assertTrue(setup["intro_cleanup_requested"])
        self.assertTrue(setup["intro_cleanup_accepted"])
        self.assertEqual(setup["exterior_location_after"], 0x13163)
        self.assertFalse(any(e[0] == "intro_stage_refused_outside_story_manager" for e in vm.effects))
        self.assertEqual(vm.main_quest_stage, 0)

    def test_exterior_arrival_without_quest_start_is_not_acceptance(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.story_trigger_enabled = False
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        setup = vm.result["world_setup"]
        self.assertTrue(setup["story_entry_observed"])
        self.assertFalse(setup["intro_running_observed"])
        self.assertEqual(setup["story_wait_attempts"], 80)
        self.assertFalse(any(e[0] in ("intro_stage", "intro_stage_refused_outside_story_manager", "move_fixture", "play") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_running_intro_can_cleanup_without_new_exterior_entry(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.intro_running = vm.intro_playing = True
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "passed")
        self.assertTrue(vm.result["world_setup"]["intro_running_observed"])
        self.assertFalse(vm.result["world_setup"]["story_entry_attempted"])
        self.assertFalse(any(e[0] == "move_story_fixture" for e in vm.effects))

    def test_natural_intro_completion_during_entry_is_not_restarted(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        normal_method = vm.method

        def complete_during_entry(obj, name, args):
            result = normal_method(obj, name, args)
            if obj == "P" and name == "moveto" and args[0] == ("marker", "exterior"):
                vm.intro_done.add(10)
                vm.intro_stage = 10
                vm.intro_running = vm.intro_playing = False
            return result

        vm.method = complete_during_entry
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "passed")
        self.assertTrue(vm.result["world_setup"]["story_entry_observed"])
        self.assertFalse(vm.result["world_setup"]["intro_running_observed"])
        self.assertFalse(vm.result["world_setup"]["intro_cleanup_requested"])
        self.assertTrue(vm.result["world_setup"]["intro_natural_completion_observed"])
        self.assertFalse(any(e[0].startswith("intro_stage") for e in vm.effects))

    def test_cleanup_inside_exterior_moveto_cannot_resume_or_overwrite_cancelled_result(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        normal_method = vm.method
        cancellation_result = None

        def cancel_during_entry(obj, name, args):
            nonlocal cancellation_result
            result = normal_method(obj, name, args)
            if obj == "P" and name == "moveto" and args[0] == ("marker", "exterior"):
                vm.lab("Cleanup")
                cancellation_result = copy.deepcopy(vm.result)
            return result

        vm.method = cancel_during_entry
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "cancelled")
        self.assertEqual(vm.result, cancellation_result)
        self.assertFalse(any(e[0] in ("intro_stage", "move_fixture", "play") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.timers)

    def test_cleanup_during_story_start_wait_cannot_request_a_later_stage(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.story_trigger_enabled = False
        normal_static = vm.static
        cancellation_result = None

        def cancel_during_story_wait(owner, name, args):
            nonlocal cancellation_result
            result = normal_static(owner, name, args)
            if owner == "utility" and name == "wait":
                vm.lab("Cleanup")
                cancellation_result = copy.deepcopy(vm.result)
                vm.intro_running = vm.intro_playing = True
            return result

        vm.static = cancel_during_story_wait
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "cancelled")
        self.assertEqual(vm.result, cancellation_result)
        self.assertFalse(any(e[0] in ("intro_stage", "move_fixture", "play") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.timers)

    def test_advanced_main_quest_refuses_priming_without_modifying_it(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.main_quest_stage = 50
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.result["world_setup"]["mq102_stage_before_read_only"], 50)
        self.assertEqual(vm.main_quest_stage, 50)
        self.assertFalse(any(e[0] in ("intro_stage", "move_story_fixture", "move_fixture") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_missing_exterior_anchor_refuses_priming_before_any_move(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        normal_static = vm.static

        def missing_anchor(owner, name, args):
            if owner == "game" and name == "getformfromfile" and args == [0x96595, "Skyrim.esm"]:
                return None
            return normal_static(owner, name, args)

        vm.static = missing_anchor
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(any(e[0] in ("intro_stage", "move_story_fixture", "move_fixture") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_quest_started_without_observed_riverwood_location_cannot_prime(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        normal_method = vm.method

        def wrong_arrival(obj, name, args):
            result = normal_method(obj, name, args)
            if obj == "P" and name == "moveto" and args[0] == ("marker", "exterior"):
                vm.actors["P"]["location"] = "outside"
            return result

        vm.method = wrong_arrival
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(vm.result["world_setup"]["story_entry_observed"])
        self.assertFalse(any(e[0] in ("intro_stage", "move_fixture", "play") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_revoked_opt_in_during_story_wait_blocks_cleanup_and_inn_entry(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_disposable_world_setup"] = True
        vm.story_trigger_enabled = False
        normal_static = vm.static

        def revoke_during_story_wait(owner, name, args):
            result = normal_static(owner, name, args)
            if owner == "utility" and name == "wait":
                vm.files[CONTROL]["allow_disposable_world_setup"] = False
                vm.intro_running = vm.intro_playing = True
            return result

        vm.static = revoke_during_story_wait
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(any(e[0] in ("intro_stage", "move_fixture", "play") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def controlled_vm(self):
        vm = LabVM()
        vm.files[CONTROL].update(allow_disposable_world_setup=True, allow_controlled_actor_ai=True)
        return vm

    def test_controlled_alias_is_opt_in_and_manual_commands_never_acquire(self):
        for flag in (None, False, "true", 1):
            with self.subTest(flag=flag):
                vm = LabVM()
                vm.files[CONTROL]["allow_disposable_world_setup"] = True
                if flag is not None:
                    vm.files[CONTROL]["allow_controlled_actor_ai"] = flag
                vm.autorun("focused-complete")
                self.assertEqual(vm.result["status"], "passed")
                self.assertFalse(any(e[0] == "hold_force" for e in vm.effects))
                self.assertFalse(vm.result["controlled_actor_ai"])
        vm = self.controlled_vm()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")
        self.assertFalse(any(e[0] == "hold_force" for e in vm.effects))

    def test_controlled_alias_success_acquires_after_stage_move_and_releases(self):
        for scenario in ("ambient-entry", "focused-complete", "focused-interrupt"):
            with self.subTest(scenario=scenario):
                vm = self.controlled_vm()
                vm.autorun(scenario)
                self.assertEqual(vm.result["status"], "passed")
                ai = vm.result["fixture_ai"]
                self.assertTrue(vm.result["controlled_actor_ai"])
                self.assertFalse(vm.result["normal_actor_ai_behavior_verified"])
                self.assertTrue(ai["acquired"])
                self.assertTrue(ai["standing_observed"])
                self.assertTrue(ai["released"])
                self.assertFalse(ai["acquisition_intent"])
                self.assertEqual(ai["package_before"], 0x1CB1B)
                self.assertEqual(ai["package_during"], 0x10FB3F)
                self.assertEqual(ai["package_after_release"], 0x36C1B)
                self.assertIsNone(vm.fixture_alias)
                self.assertEqual(vm.settings, vm.initial_settings)
                self.assertEqual(len([e for e in vm.effects if e[0] == "hold_force"]), 1)
                self.assertEqual(len([e for e in vm.effects if e[0] == "hold_clear"]), 1)
                stage = vm.effects.index(("move_fixture", "Sven", ("marker", "stage")))
                acquire = vm.effects.index(("hold_force", "Sven"))
                entry = vm.effects.index(("move_fixture", "P", ("marker", "audience")))
                self.assertLess(stage, acquire)
                self.assertLess(acquire, entry)

    def test_preexisting_alias_blocks_new_run_without_clearing_it(self):
        vm = self.controlled_vm()
        vm.fixture_alias = "OtherActor"
        before = copy.deepcopy(vm.files)
        vm.autorun("focused-complete")
        self.assertIsNone(vm.result)
        self.assertEqual(vm.fixture_alias, "OtherActor")
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(any(e[0] in ("hold_force", "hold_clear", "move_fixture", "move_story_fixture") for e in vm.effects))
        for key in (CONTROL, "HoldMusic/library.json", "HoldMusic/receipts.json"):
            self.assertEqual(vm.files[key], before[key])

    def test_failed_or_mismatched_alias_acquisition_never_starts_performance(self):
        for replacement in (None, "OtherActor"):
            with self.subTest(replacement=replacement):
                vm = self.controlled_vm()
                normal_method = vm.method

                def wrong_acquisition(obj, name, args):
                    result = normal_method(obj, name, args)
                    if obj == ("alias", "fixture") and name == "forcerefto":
                        vm.fixture_alias = replacement
                    return result

                vm.method = wrong_acquisition
                vm.autorun("focused-complete")
                self.assertEqual(vm.result["status"], "failed")
                self.assertEqual(vm.fixture_alias, replacement)
                self.assertFalse(any(e[0] == "play" for e in vm.effects))
                self.assertFalse(any(e[0] == "hold_clear" for e in vm.effects))
                self.assertEqual(vm.settings, vm.initial_settings)

    def test_acquisition_intent_save_failure_prevents_alias_write(self):
        vm = self.controlled_vm()
        normal_static = vm.static
        rejected = False

        def reject_intent_save(owner, name, args):
            nonlocal rejected
            result = normal_static(owner, name, args)
            if (not rejected and owner == "jsonutil" and name == "save" and args[0] == RESULT
                    and vm.state["hm_labharness"]["fixtureholdintent"]):
                rejected = True
                return False
            return result

        vm.static = reject_intent_save
        vm.autorun("focused-complete")
        self.assertTrue(rejected)
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(any(e[0] == "hold_force" for e in vm.effects))
        self.assertIsNone(vm.fixture_alias)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_cancellation_inside_alias_assignment_cannot_leave_a_late_claim(self):
        for before_assignment in (False, True):
            with self.subTest(before_assignment=before_assignment):
                vm = self.controlled_vm()
                normal_method = vm.method
                terminal = None

                def cancel_during_assignment(obj, name, args):
                    nonlocal terminal
                    targeted = obj == ("alias", "fixture") and name == "forcerefto"
                    if targeted and before_assignment:
                        vm.lab("Cleanup")
                        terminal = copy.deepcopy(vm.result)
                    result = normal_method(obj, name, args)
                    if targeted and not before_assignment:
                        vm.lab("Cleanup")
                        terminal = copy.deepcopy(vm.result)
                    return result

                vm.method = cancel_during_assignment
                vm.autorun("focused-complete")
                # While the native acquisition is in flight, release cannot
                # yet be certified. Keep a failed terminal result; compensate
                # any late assignment after return without publishing a pass.
                self.assertEqual(vm.result["status"], "failed")
                self.assertEqual(vm.result, terminal)
                self.assertIsNone(vm.fixture_alias)
                self.assertFalse(vm.state["hm_labharness"]["fixtureholdintent"])
                self.assertFalse(any(e == ("move_fixture", "P", ("marker", "audience")) for e in vm.effects))
                self.assertFalse(vm.receipts)
                self.assertEqual(vm.settings, vm.initial_settings)
                self.assertFalse(vm.timers)

    def test_standing_readiness_is_bounded_without_retrying_performance(self):
        for obstruction in ("package", "sitting"):
            with self.subTest(obstruction=obstruction):
                vm = self.controlled_vm()
                if obstruction == "package":
                    vm.hold_package_enabled = False
                else:
                    vm.actors["Sven"]["sit"] = 3
                vm.autorun("focused-complete")
                vm.tick(95)
                self.assertEqual(vm.result["status"], "failed")
                self.assertFalse(vm.result["fixture_ai"]["standing_observed"])
                self.assertTrue(vm.result["fixture_ai"]["released"])
                self.assertFalse(any(e[0] in ("play", "idle") for e in vm.effects))
                self.assertIsNone(vm.fixture_alias)
                self.assertEqual(vm.settings, vm.initial_settings)

    def test_cancellation_during_standing_wait_releases_owned_alias(self):
        vm = self.controlled_vm()
        vm.actors["Sven"]["sit"] = 3
        vm.files[REQUEST].update(auto_run=True, scenario="focused-complete")
        vm.lab("OnInit")
        vm.tick(5)
        self.assertEqual(vm.fixture_alias, "Sven")
        vm.lab("Cleanup")
        self.assertEqual(vm.result["status"], "cancelled")
        self.assertTrue(vm.result["fixture_ai"]["released"])
        self.assertIsNone(vm.fixture_alias)
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.timers)

    def test_release_preserves_foreign_alias_and_cannot_report_pass(self):
        vm = self.controlled_vm()
        vm.files[REQUEST].update(auto_run=True, scenario="focused-complete")
        vm.lab("OnInit")
        vm.tick(5)
        self.assertTrue(vm.result["assertions"]["performance_start"])
        vm.fixture_alias = "OtherActor"
        vm.tick(12)
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(vm.result["fixture_ai"]["released"])
        self.assertEqual(vm.fixture_alias, "OtherActor")
        self.assertFalse(any(e[0] == "hold_clear" for e in vm.effects))

    def test_failed_alias_clear_or_package_release_cannot_report_pass(self):
        for failure in ("clear", "package"):
            with self.subTest(failure=failure):
                vm = self.controlled_vm()
                normal_method = vm.method

                def fail_release(obj, name, args):
                    if failure == "clear" and obj == ("alias", "fixture") and name == "clear":
                        return None
                    if failure == "package" and obj == "Sven" and name == "evaluatepackage" and vm.fixture_package == 0x10FB3F and vm.fixture_alias is None:
                        return None
                    return normal_method(obj, name, args)

                vm.method = fail_release
                vm.autorun("focused-complete")
                self.assertEqual(vm.result["status"], "failed")
                self.assertFalse(vm.result["fixture_ai"]["released"])
                vm.method = normal_method
                vm.lab("Cleanup")
                self.assertIsNone(vm.fixture_alias)
                self.assertNotEqual(vm.fixture_package, 0x10FB3F)

    def test_revoked_controlled_ai_permission_releases_before_inn_entry(self):
        vm = self.controlled_vm()
        normal_method = vm.method

        def revoke_during_assignment(obj, name, args):
            result = normal_method(obj, name, args)
            if obj == ("alias", "fixture") and name == "forcerefto":
                vm.files[CONTROL]["allow_controlled_actor_ai"] = False
            return result

        vm.method = revoke_during_assignment
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertIsNone(vm.fixture_alias)
        self.assertFalse(any(e == ("move_fixture", "P", ("marker", "audience")) for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_controlled_ai_without_disposable_setup_is_refused(self):
        vm = LabVM()
        vm.files[CONTROL]["allow_controlled_actor_ai"] = True
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(any(e[0] in ("hold_force", "move_fixture") for e in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_focused_timing_brackets_separate_scan_from_later_work(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        normal_static = vm.static

        def scan_cost(owner, name, args):
            result = normal_static(owner, name, args)
            if owner == "miscutil" and name == "scancellnpcs":
                vm.now += 3.0
            return result

        vm.static = scan_cost
        vm.lab("FocusedStart")
        timing = vm.result["timing"]
        self.assertEqual(timing["focused_scan_finished"] - timing["focused_scan_started"], 3.0)
        ordered = [timing[key] for key in ("focused_scan_started", "focused_scan_finished", "focused_matching_finished", "focused_diagnostics_finished", "focused_selection_started", "focused_selection_finished")]
        self.assertEqual(ordered, sorted(ordered))

    def test_slow_focused_preparation_has_separate_fixed_playback_budget(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        normal_static = vm.static

        def slow_scan(owner, name, args):
            value = normal_static(owner, name, args)
            if owner == "miscutil" and name == "scancellnpcs":
                vm.now += 48.0
            return value

        vm.static = slow_scan
        vm.lab("FocusedStart")
        self.assertEqual(vm.result["status"], "running")
        self.assertGreater(vm.result["performance_start_trace_real_seconds"], vm.result["started_real_seconds"] + 40)
        self.assertEqual(vm.result["focused_preparation_deadline_real_seconds"], vm.result["started_real_seconds"] + 90)
        self.assertEqual(vm.result["focused_playback_deadline_real_seconds"], vm.result["performance_start_trace_real_seconds"] + 28)
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")
        self.assertEqual([row["outcome"] for row in vm.receipts], ["completed"])

    def test_preparation_expiry_or_cancellation_after_native_return_never_starts(self):
        for point in ("scancellnpcs", "chooseslot"):
            for cancel in (False, True):
                with self.subTest(point=point, cancel=cancel):
                    vm = self.controlled_vm()
                    normal_static, normal_run = vm.static, vm.run
                    terminal = None

                    def delay():
                        nonlocal terminal
                        vm.now += 91
                        if cancel:
                            vm.lab("Cleanup")
                            terminal = copy.deepcopy(vm.result)

                    def slow_native(owner, name, args):
                        value = normal_static(owner, name, args)
                        if point == "scancellnpcs" and owner == "miscutil" and name == point:
                            delay()
                        return value

                    def slow_selection(owner, name, *args):
                        value = normal_run(owner, name, *args)
                        if point == "chooseslot" and name.lower() == point and ("hm_labharness", "runfocusedprepared") in vm.callers:
                            delay()
                        return value

                    vm.static, vm.run = slow_native, slow_selection
                    vm.autorun("focused-complete")
                    self.assertEqual(vm.result["status"], "cancelled" if cancel else "failed")
                    if cancel:
                        self.assertEqual(vm.result, terminal)
                    else:
                        self.assertIn("90-second", vm.result["reason"])
                    self.assertFalse(any(e[0] in ("play", "idle") for e in vm.effects))
                    self.assertFalse(vm.receipts)
                    self.assertIsNone(vm.fixture_alias)
                    self.assertFalse(vm.timers)

    def test_playback_deadline_uses_production_timestamp_not_late_observation(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        normal_run = vm.run

        def delayed_return(owner, name, *args):
            value = normal_run(owner, name, *args)
            if owner.lower() == "hm_controller" and name.lower() == "startperformance":
                vm.now += 6
            return value

        vm.run = delayed_return
        vm.lab("FocusedStart")
        self.assertEqual(vm.result["performance_start_observed_real_seconds"] - vm.result["performance_start_trace_real_seconds"], 6)
        self.assertEqual(vm.result["focused_playback_deadline_real_seconds"], vm.result["performance_start_trace_real_seconds"] + 28)
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")

    def test_playback_deadline_never_extends_on_repeated_polls(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        deadline = vm.result["focused_playback_deadline_real_seconds"]
        vm.timers.clear()  # Simulate a missing production completion poll.
        for offset in (5, 10, 20, 27):
            vm.now = vm.result["performance_start_trace_real_seconds"] + offset
            vm.lab("OnUpdate")
            self.assertEqual(vm.result["focused_playback_deadline_real_seconds"], deadline)
            self.assertEqual(vm.result["status"], "running")
        vm.now = deadline
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.result["focused_playback_deadline_real_seconds"], deadline)
        self.assertFalse(vm.timers)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_missing_or_invalid_production_start_timestamp_cannot_pass(self):
        for stamp in (None, "not-a-number", -1.0, 999999.0):
            with self.subTest(stamp=stamp):
                vm = LabVM()
                vm.actors["P"]["location"] = "inn"
                normal_run = vm.run

                def corrupt_timestamp(owner, name, *args):
                    value = normal_run(owner, name, *args)
                    if owner.lower() == "hm_controller" and name.lower() == "startperformance":
                        entry = next(row for row in reversed(vm.files["HoldMusic/trace.json"]["entries"]) if row["event"] == "performance_start")
                        if stamp is None:
                            entry.pop("real_seconds", None)
                        else:
                            entry["real_seconds"] = stamp
                    return value

                vm.run = corrupt_timestamp
                vm.lab("FocusedStart")
                self.assertEqual(vm.result["status"], "failed")
                self.assertFalse(vm.result["assertions"]["performance_start"])
                self.assertFalse(vm.timers)

    def test_interrupt_request_precedes_expensive_evidence_collection(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedInterrupt")
        normal_run = vm.run
        observed_early_request = False

        def slow_collection(owner, name, *args):
            nonlocal observed_early_request
            if owner.lower() == "hm_labharness" and name.lower() == "collectevidencerows":
                if not observed_early_request:
                    self.assertTrue(vm.state["hm_config"]["::stoprequested_var"])
                    observed_early_request = True
                    vm.now += 3
            return normal_run(owner, name, *args)

        vm.run = slow_collection
        vm.now += 2.1
        vm.lab("OnUpdate")
        self.assertTrue(observed_early_request)
        self.assertEqual(vm.result["timing"]["evidence_collection_max_seconds"], 3)
        vm.tick(5)
        self.assertEqual(vm.result["status"], "passed")
        self.assertEqual([row["outcome"] for row in vm.receipts], ["interrupted"])

    def test_earlier_unrelated_stop_cannot_pass_a_late_precollection_request(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedInterrupt")
        vm.now += 1
        vm.actors["Sven"]["combat"] = True
        vm.run("hm_controller", "OnUpdate")
        vm.actors["Sven"]["combat"] = False
        vm.now += 1.1
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertTrue(vm.result["assertions"]["stop_request_issued"])
        self.assertFalse(vm.result["assertions"]["requested_interruption_guard"])
        self.assertIn("before the lab issued", vm.result["reason"])
        self.assertEqual([row["outcome"] for row in vm.receipts], ["interrupted"])
        self.assertFalse(vm.timers)

    def test_interrupted_receipt_requires_matching_fresh_stop_request_guard(self):
        for mismatch in ("missing", "reason", "timestamp", "actor", "slot"):
            with self.subTest(mismatch=mismatch):
                vm = LabVM()
                vm.actors["P"]["location"] = "inn"
                vm.lab("FocusedInterrupt")
                vm.tick(2.1)
                self.assertTrue(vm.result["assertions"]["stop_request_issued"])
                normal_run = vm.run
                altered = False

                def alter_guard(owner, name, *args):
                    nonlocal altered
                    value = normal_run(owner, name, *args)
                    if not altered and owner.lower() == "hm_controller" and name.lower() == "onupdate":
                        rows = vm.files["HoldMusic/trace.json"]["entries"]
                        guard = next((row for row in rows if row["event"] == "performance_interrupt_guard"), None)
                        if guard is not None:
                            altered = True
                            if mismatch == "missing":
                                guard["event"] = "different_event"
                            elif mismatch == "reason":
                                guard["detail"] = guard["detail"].replace("reason=stop_requested", "reason=actor_combat")
                            elif mismatch == "timestamp":
                                guard["real_seconds"] = vm.result["interruption_request_real_seconds"] - 0.5
                            elif mismatch == "actor":
                                guard["detail"] = guard["detail"].replace("id=sven", "id=other")
                            else:
                                guard["detail"] = guard["detail"].replace("slot=1", "slot=2")
                    return value

                vm.run = alter_guard
                vm.tick(35)
                self.assertTrue(altered)
                self.assertEqual(vm.result["status"], "failed")
                self.assertFalse(vm.result["assertions"]["requested_interruption_guard"])
                self.assertEqual([row["outcome"] for row in vm.receipts], ["interrupted"])
                self.assertFalse(vm.timers)

    def test_request_inside_trace_window_but_after_receipt_duration_cannot_pass(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        normal_run = vm.run

        def lagging_start_trace(owner, name, *args):
            value = normal_run(owner, name, *args)
            if owner.lower() == "hm_controller" and name.lower() == "startperformance":
                row = next(row for row in reversed(vm.files["HoldMusic/trace.json"]["entries"]) if row["event"] == "performance_start")
                row["real_seconds"] += 0.3
                vm.now += 0.3
            return value

        vm.run = lagging_start_trace
        vm.lab("FocusedInterrupt")
        vm.now = vm.result["performance_start_trace_real_seconds"] + 7.8
        vm.lab("OnUpdate")
        self.assertTrue(vm.result["assertions"]["stop_request_issued"])
        vm.run("hm_controller", "OnUpdate")
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertTrue(vm.result["assertions"]["requested_interruption_guard"])
        self.assertTrue(vm.result["interrupt_window_missed"])
        self.assertIn("actual production duration", vm.result["reason"])
        self.assertEqual([row["outcome"] for row in vm.receipts], ["interrupted"])

    def test_late_request_inside_unrelated_native_stop_cannot_claim_its_receipt(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedInterrupt")
        normal_static = vm.static
        terminal = None

        def interrupt_during_unrelated_stop(owner, name, args):
            nonlocal terminal
            value = normal_static(owner, name, args)
            if terminal is None and owner == "sound" and name == "stopinstance":
                vm.lab("OnUpdate")
                terminal = copy.deepcopy(vm.result)
            return value

        vm.static = interrupt_during_unrelated_stop
        vm.actors["Sven"]["combat"] = True
        vm.now += 3
        vm.run("hm_controller", "OnUpdate")
        vm.lab("OnUpdate")
        self.assertIsNotNone(terminal)
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.result, terminal)
        self.assertTrue(vm.result["assertions"]["stop_request_issued"])
        self.assertFalse(vm.result["assertions"]["requested_interruption_guard"])
        self.assertIn("guard does not match", vm.result["reason"])
        self.assertEqual([row["outcome"] for row in vm.receipts], ["interrupted"])
        self.assertFalse(vm.timers)

    def test_ambient_deadline_remains_fixed_120_seconds_after_world_setup(self):
        vm = self.controlled_vm()
        vm.autorun("ambient-entry")
        self.assertEqual(vm.result["status"], "passed")
        setup = vm.result["world_setup"]
        self.assertEqual(setup["scenario_deadline_real_seconds"], setup["setup_finished_real_seconds"] + 120)
        self.assertEqual(vm.result["focused_preparation_deadline_real_seconds"], 0)
        self.assertEqual(vm.result["focused_playback_deadline_real_seconds"], 0)

    def test_result_timing_reports_previous_save_without_extra_write(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        normal_static = vm.static

        def slow_save(owner, name, args):
            value = normal_static(owner, name, args)
            if owner == "jsonutil" and name == "save" and args[0] == RESULT:
                vm.now += 3
            return value

        vm.static = slow_save
        vm.lab("FocusedStart")
        self.assertEqual(vm.result["timing"]["previous_result_save_seconds"], 3)
        self.assertEqual(vm.result["timing"]["previous_result_save_max_seconds"], 3)
        self.assertEqual(sum(e == ("save", RESULT) for e in vm.effects), 2)
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")

    def test_cancel_during_each_final_fixture_move_preserves_terminal_and_no_scheduling(self):
        for controlled in (False, True):
            for moved_actor in ("Sven", "P"):
                with self.subTest(controlled=controlled, moved_actor=moved_actor):
                    vm = self.controlled_vm() if controlled else LabVM()
                    normal_method = vm.method
                    terminal = None

                    def cancel_move(obj, name, args):
                        nonlocal terminal
                        value = normal_method(obj, name, args)
                        if obj == moved_actor and name == "moveto" and args[0] in (("marker", "stage"), ("marker", "audience")):
                            vm.lab("Cleanup")
                            terminal = copy.deepcopy(vm.result)
                        return value

                    vm.method = cancel_move
                    vm.autorun("focused-complete")
                    self.assertIsNotNone(terminal)
                    self.assertEqual(vm.result["status"], "cancelled")
                    self.assertEqual(vm.result, terminal)
                    self.assertIsNone(vm.fixture_alias)
                    self.assertFalse(any(e[0] in ("play", "idle") for e in vm.effects))
                    self.assertFalse(vm.receipts)
                    self.assertFalse(vm.timers)
                    self.assertEqual(vm.settings, vm.initial_settings)

    def test_changed_request_or_permission_during_fixture_move_fails_without_start(self):
        for moved_actor in ("Sven", "P"):
            for change in ("request", "enabled", "auto_run", "controlled_ai"):
                with self.subTest(moved_actor=moved_actor, change=change):
                    vm = self.controlled_vm()
                    normal_method = vm.method

                    def revoke_during_move(obj, name, args):
                        value = normal_method(obj, name, args)
                        if obj == moved_actor and name == "moveto" and args[0] in (("marker", "stage"), ("marker", "audience")):
                            if change == "request":
                                vm.files[REQUEST]["run_id"] = "replacement-request"
                            elif change == "auto_run":
                                vm.files[REQUEST]["auto_run"] = False
                            elif change == "enabled":
                                vm.files[CONTROL]["enabled"] = False
                            else:
                                vm.files[CONTROL]["allow_controlled_actor_ai"] = False
                        return value

                    vm.method = revoke_during_move
                    vm.autorun("focused-complete")
                    self.assertEqual(vm.result["status"], "failed")
                    self.assertEqual(vm.result["run_id"], "run-001")
                    self.assertIsNone(vm.fixture_alias)
                    self.assertFalse(any(e[0] in ("play", "idle") for e in vm.effects))
                    self.assertFalse(vm.timers)
                    self.assertEqual(vm.settings, vm.initial_settings)

    def test_cancel_after_focused_scan_never_starts_or_overwrites_terminal(self):
        for controlled in (False, True):
            with self.subTest(controlled=controlled):
                vm = self.controlled_vm() if controlled else LabVM()
                normal_static = vm.static
                terminal = None

                def cancel_scan(owner, name, args):
                    nonlocal terminal
                    value = normal_static(owner, name, args)
                    if owner == "miscutil" and name == "scancellnpcs":
                        vm.lab("Cleanup")
                        terminal = copy.deepcopy(vm.result)
                    return value

                vm.static = cancel_scan
                if controlled:
                    vm.autorun("focused-complete")
                else:
                    vm.actors["P"]["location"] = "inn"
                    vm.lab("FocusedStart")
                self.assertIsNotNone(terminal)
                self.assertEqual(vm.result["status"], "cancelled")
                self.assertEqual(vm.result, terminal)
                self.assertIsNone(vm.fixture_alias)
                self.assertFalse(any(e[0] in ("play", "idle") for e in vm.effects))
                self.assertFalse(vm.receipts)
                self.assertFalse(vm.timers)
                self.assertEqual(vm.settings, vm.initial_settings)

    def test_cancel_during_focused_matching_diagnostics_selection_and_identity_never_starts(self):
        for point in ("findperformer", "recordfixturediagnostics", "chooseslot", "recordingidentity"):
            with self.subTest(point=point):
                vm = self.controlled_vm()
                normal_run = vm.run
                terminal = None

                def cancel_phase(owner, name, *args):
                    nonlocal terminal
                    value = normal_run(owner, name, *args)
                    if terminal is None and name.lower() == point and ("hm_labharness", "startfocusedprepared") in vm.callers:
                        vm.lab("Cleanup")
                        terminal = copy.deepcopy(vm.result)
                    return value

                vm.run = cancel_phase
                vm.autorun("focused-complete")
                self.assertIsNotNone(terminal)
                self.assertEqual(vm.result["status"], "cancelled")
                self.assertEqual(vm.result, terminal)
                self.assertIsNone(vm.fixture_alias)
                self.assertFalse(any(e[0] in ("play", "idle") for e in vm.effects))
                self.assertFalse(vm.receipts)
                self.assertFalse(vm.timers)

    def test_revoked_request_after_selection_fails_before_native_start(self):
        vm = self.controlled_vm()
        normal_run = vm.run

        def replace_request(owner, name, *args):
            value = normal_run(owner, name, *args)
            if name.lower() == "chooseslot" and ("hm_labharness", "startfocusedprepared") in vm.callers:
                vm.files[REQUEST]["run_id"] = "replacement-request"
            return value

        vm.run = replace_request
        vm.autorun("focused-complete")
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.result["run_id"], "run-001")
        self.assertFalse(any(e[0] in ("play", "idle") for e in vm.effects))
        self.assertIsNone(vm.fixture_alias)
        self.assertFalse(vm.timers)

    def test_cancel_inside_native_start_defers_stop_until_return_and_preserves_pending_terminal(self):
        for point in ("idle", "sound"):
            for after in (False, True):
                with self.subTest(point=point, after=after):
                    vm = self.controlled_vm()
                    normal_method = vm.method
                    terminal = None
                    switched = False

                    def cancel_start(obj, name, args):
                        nonlocal terminal, switched
                        targeted = ((point == "idle" and obj == "Sven" and name == "playidle") or
                                    (point == "sound" and obj == ("sound", 1) and name == "play"))
                        if targeted and not switched:
                            switched = True
                            if after:
                                value = normal_method(obj, name, args)
                            vm.lab("Cleanup")
                            terminal = copy.deepcopy(vm.result)
                            # The suspended production stack still owns the
                            # start attempt; a fresh run cannot claim it.
                            self.assertFalse(vm.run("hm_labharness", "BeginRun", "focused_complete"))
                            if not after:
                                value = normal_method(obj, name, args)
                            return value
                        return normal_method(obj, name, args)

                    vm.method = cancel_start
                    vm.autorun("focused-complete")
                    self.assertTrue(switched)
                    self.assertEqual(vm.result["status"], "cancelled")
                    self.assertEqual(vm.result, terminal)
                    self.assertTrue(vm.result["focused_start_cleanup_pending"])
                    self.assertFalse(vm.state["hm_labharness"]["focusedstartinflight"])
                    self.assertIsNone(vm.state["hm_controller"]["performer"])
                    self.assertEqual([row["outcome"] for row in vm.receipts], ["interrupted"])
                    self.assertIsNone(vm.fixture_alias)
                    self.assertFalse(vm.timers)
                    self.assertEqual(vm.settings, vm.initial_settings)

    def test_nested_cleanup_during_finish_release_cannot_be_overwritten_by_pass(self):
        vm = self.controlled_vm()
        normal_method, normal_static = vm.method, vm.static
        delayed = False
        terminal = None

        def delay_first_release(obj, name, args):
            nonlocal delayed
            if not delayed and obj == "Sven" and name == "evaluatepackage" and vm.fixture_alias is None and vm.fixture_package == 0x10FB3F:
                delayed = True
                return None
            return normal_method(obj, name, args)

        def cancel_release_wait(owner, name, args):
            nonlocal terminal
            value = normal_static(owner, name, args)
            if terminal is None and delayed and owner == "utility" and name == "wait":
                vm.lab("Cleanup")
                terminal = copy.deepcopy(vm.result)
                self.assertFalse(vm.run("hm_labharness", "BeginRun", "focused_complete"))
            return value

        vm.method, vm.static = delay_first_release, cancel_release_wait
        vm.autorun("focused-complete")
        self.assertTrue(delayed)
        self.assertIsNotNone(terminal)
        self.assertEqual(vm.result["status"], "cancelled")
        self.assertEqual(vm.result, terminal)
        self.assertEqual([row["outcome"] for row in vm.receipts], ["completed"])
        self.assertEqual(vm.state["hm_labharness"]["finishdepth"], 0)
        self.assertFalse(any(e[0] == "trace" and "LAB: passed" in e[1] for e in vm.effects))
        self.assertIsNone(vm.fixture_alias)
        self.assertFalse(vm.timers)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_delayed_fixture_arrival_still_gets_two_seconds_before_interruption(self):
        vm = LabVM()
        vm.actors["Sven"]["loaded"] = False
        vm.files[REQUEST].update(auto_run=True, scenario="focused-interrupt")
        vm.lab("OnInit")
        vm.tick(6)
        self.assertEqual(vm.result["status"], "running")
        self.assertFalse(vm.result["assertions"]["performance_start"])
        vm.actors["Sven"]["loaded"] = True
        vm.tick(1)
        started = vm.result["performance_start_observed_real_seconds"]
        self.assertGreater(started, vm.result["started_real_seconds"] + 2)
        self.assertTrue(vm.result["assertions"]["performance_start"])
        self.assertFalse(vm.result["assertions"]["stop_request_issued"])
        vm.tick(0.75)
        self.assertLess(vm.now, started + 2)
        self.assertFalse(vm.result["assertions"]["stop_request_issued"])
        vm.tick(4)
        self.assertEqual(vm.result["status"], "passed")
        self.assertTrue(vm.result["assertions"]["stop_request_issued"])
        self.assertEqual(vm.receipts[-1]["outcome"], "interrupted")

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

    def test_protected_boolean_literals_survive_bare_token_case_collision(self):
        vm = LabVM()
        normal_static = vm.static

        def emulate_intern_collision(owner, name, args):
            if owner == "jsonutil" and name == "setrawpathvalue" and args[2] in ("true", "false"):
                # Model the observed native failure: BSFixedString's existing
                # bare spelling is True/False, invalid case-sensitive JSON.
                vm.json_set(args[0], args[1], None)
                return False
            return normal_static(owner, name, args)

        vm.static = emulate_intern_collision
        self.assertFalse(vm.static("jsonutil", "setrawpathvalue", [RESULT, ".repro", "true"]))
        vm.lab("ArmAmbient")
        vm.enter()
        vm.tick(12)
        self.assertEqual(vm.result["status"], "passed")
        self.assertEqual(vm.result["boolean_serialization_errors"], 0)
        self.assertTrue(vm.result["runtime_engine_observed"])
        self.assertFalse(vm.result["audio_audibility_verified"])
        self.assertTrue(all(type(value) is bool for value in vm.result["assertions"].values()))

    def test_failed_boolean_parse_cannot_enable_or_report_a_running_test(self):
        vm = LabVM()
        normal_static = vm.static

        def reject_boolean_parse(owner, name, args):
            if owner == "jsonutil" and name == "setrawpathvalue" and args[2].strip() in ("true", "false"):
                vm.json_set(args[0], args[1], None)
                return False
            return normal_static(owner, name, args)

        vm.static = reject_boolean_parse
        vm.lab("ArmAmbient")
        self.assertEqual(vm.result["status"], "failed")
        self.assertGreater(vm.result["boolean_serialization_errors"], 0)
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.state["hm_labharness"]["active"])
        self.assertFalse(vm.timers)

    def test_boolean_readback_mismatch_fails_even_if_native_parser_reports_success(self):
        vm = LabVM()
        normal_static = vm.static

        def corrupt_boolean(owner, name, args):
            result = normal_static(owner, name, args)
            if owner == "jsonutil" and name == "setrawpathvalue" and args[2].strip() in ("true", "false"):
                vm.json_set(args[0], args[1], not json.loads(args[2]))
            return result

        vm.static = corrupt_boolean
        vm.lab("ArmAmbient")
        self.assertEqual(vm.result["status"], "failed")
        self.assertGreater(vm.result["boolean_serialization_errors"], 0)
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_final_serialization_failure_never_logs_a_pass(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedStart")
        vm.now += 8
        vm.run("hm_controller", "OnUpdate")
        normal_static = vm.static

        def reject_final_boolean(owner, name, args):
            if owner == "jsonutil" and name == "setrawpathvalue" and args[2].strip() in ("true", "false"):
                vm.json_set(args[0], args[1], None)
                return False
            return normal_static(owner, name, args)

        vm.static = reject_final_boolean
        vm.lab("OnUpdate")
        self.assertEqual(vm.result["status"], "failed")
        self.assertFalse(any(effect[0] == "trace" and "LAB: passed" in effect[1] for effect in vm.effects))
        self.assertTrue(any(effect[0] == "trace" and "Final result could not" in effect[1] for effect in vm.effects))
        self.assertEqual(vm.settings, vm.initial_settings)

    def test_autorun_waits_for_loaded_fixture_without_bypassing_eligibility(self):
        vm = LabVM()
        vm.actors["Sven"]["loaded"] = False
        vm.files[REQUEST].update(auto_run=True, scenario="focused-complete")
        vm.lab("OnInit")
        vm.tick(4)
        self.assertEqual(vm.result["status"], "running")
        self.assertEqual(vm.result["fixture_diagnostics"]["phase"], "waiting_for_loaded_fixture")
        self.assertEqual(vm.result["fixture_diagnostics"]["loaded_flag"], 0)
        self.assertFalse(any(effect[0] == "play" for effect in vm.effects))
        vm.actors["Sven"]["loaded"] = True
        vm.actors["Sven"]["sit"] = 3
        vm.tick(1)
        self.assertEqual(vm.result["status"], "failed")
        self.assertEqual(vm.result["fixture_diagnostics"]["sit_state"], 3)
        self.assertEqual(vm.result["fixture_diagnostics"]["loaded_flag"], 1)
        self.assertEqual(vm.result["fixture_diagnostics"]["eligible_flag"], 0)
        self.assertEqual(vm.result["fixture_diagnostics"]["scanned_sven_flag"], 1)
        self.assertFalse(vm.receipts)

    def test_fixture_readiness_wait_is_bounded_and_records_integer_diagnostics(self):
        vm = LabVM()
        vm.actors["Sven"]["loaded"] = False
        vm.files[REQUEST].update(auto_run=True, scenario="focused-complete")
        vm.lab("OnInit")
        vm.tick(95)
        self.assertEqual(vm.result["status"], "failed")
        self.assertIn("90-second", vm.result["reason"])
        diagnostic = vm.result["fixture_diagnostics"]
        for key in ("scan_count", "loaded_flag", "sit_state", "sleep_state", "same_cell_flag"):
            self.assertIs(type(diagnostic[key]), int, key)
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.receipts)

    def test_transient_failure_saving_interruption_request_cannot_later_pass(self):
        vm = LabVM()
        vm.actors["P"]["location"] = "inn"
        vm.lab("FocusedInterrupt")
        normal_static = vm.static
        rejected = False

        def reject_interruption_save(owner, name, args):
            nonlocal rejected
            value = normal_static(owner, name, args)
            if (not rejected and owner == "jsonutil" and name == "save" and args[0] == RESULT
                    and vm.state["hm_labharness"]["interruptrequested"]):
                rejected = True
                return False
            return value

        vm.static = reject_interruption_save
        vm.tick(10)
        self.assertTrue(rejected)
        self.assertEqual(vm.result["status"], "failed")
        self.assertIn("interruption request", vm.result["reason"])
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.state["hm_labharness"]["active"])

    def test_transient_failure_saving_loaded_fixture_wait_cannot_continue(self):
        vm = LabVM()
        vm.actors["Sven"]["loaded"] = False
        vm.files[REQUEST].update(auto_run=True, scenario="focused-complete")
        vm.lab("OnInit")
        vm.tick(2)
        self.assertEqual(vm.result["status"], "running")
        normal_static = vm.static
        rejected = False

        def reject_wait_save(owner, name, args):
            nonlocal rejected
            value = normal_static(owner, name, args)
            if not rejected and owner == "jsonutil" and name == "save" and args[0] == RESULT:
                rejected = True
                return False
            return value

        vm.static = reject_wait_save
        vm.tick(1)
        self.assertEqual(vm.result["status"], "failed")
        self.assertIn("waiting for the loaded fixture", vm.result["reason"])
        self.assertEqual(vm.settings, vm.initial_settings)
        self.assertFalse(vm.timers)


if __name__ == "__main__":
    unittest.main()
