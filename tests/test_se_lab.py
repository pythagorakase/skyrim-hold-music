"""SE lab tooling exercises temporary files and fake launchers only."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import se_lab


class SELabTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "isolated-lab"
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(se_lab, "LAB_ROOT", self.root).start()
        patch.object(se_lab, "_file_version", return_value="1.6.1170.0").start()
        patch.object(se_lab, "_require_windows", return_value=None).start()
        self.closed = patch.object(se_lab, "default_process_probe",
                                   return_value=dict(verified=True, quiescent=True, processes=[])).start()
        self.write("Game/SkyrimSE.exe", b"synthetic-runtime")
        self.write("Game/skse64_loader.exe", b"synthetic-loader")
        self.write("MO2/ModOrganizer.exe", b"synthetic-MO2")
        self.write("MO2/portable.txt", b"")
        self.ini()
        self.write("MO2/profiles/" + se_lab.PROFILE + "/modlist.txt", b"+Harness\n")
        self.write("MO2/profiles/" + se_lab.PROFILE + "/plugins.txt", b"*HoldMusicSELab.esp\n")
        self.write("MO2/profiles/" + se_lab.PROFILE + "/settings.ini",
                   b"[General]\nLocalSaves=true\nLocalSettings=true\n")
        self.write("MO2/profiles/" + se_lab.PROFILE + "/Skyrim.ini", b"[General]\nsLanguage=ENGLISH\n")
        self.write("MO2/profiles/" + se_lab.PROFILE + "/SkyrimPrefs.ini", b"[Display]\nbFull Screen=0\n")
        self.write("MO2/mods/Harness/HoldMusicSELab.esp", b"synthetic-plugin")
        self.json("MO2/mods/Harness/" + se_lab.CONTROL,
                  dict(version=1, enabled=True, world_id="hold-music-se-lab"))
        self.result_path = "MO2/overwrite/" + se_lab.STORAGE + "/result.json"
        self.manifest = dict(
            version=1, paid_generation=False,
            runtime=dict(path="Game/SkyrimSE.exe", version="1.6.1170.0", sha256=self.sha("Game/SkyrimSE.exe")),
            loader=dict(path="Game/skse64_loader.exe", sha256=self.sha("Game/skse64_loader.exe")),
            mo2=dict(path="MO2/ModOrganizer.exe", profile=se_lab.PROFILE, sha256=self.sha("MO2/ModOrganizer.exe")),
            required_mods=["Harness"], required_plugins=["HoldMusicSELab.esp"],
            files=[dict(path="MO2/mods/Harness/HoldMusicSELab.esp",
                        sha256=self.sha("MO2/mods/Harness/HoldMusicSELab.esp"))],
            logs=[dict(id="harness", path=self.result_path, required=True, run_id_field="run_id")])
        self.save_manifest()

    def write(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def json(self, relative, value):
        self.write(relative, json.dumps(value).encode())

    def read_json(self, relative):
        return json.loads((self.root / relative).read_text())

    def sha(self, relative):
        return hashlib.sha256((self.root / relative).read_bytes()).hexdigest()

    def save_manifest(self):
        self.json(se_lab.MANIFEST, self.manifest)

    def ini(self, *, game=None, extra=""):
        self.write("MO2/ModOrganizer.ini", (
            "[General]\ngameName=Skyrim Special Edition\nselected_profile=@ByteArray("
            + se_lab.PROFILE + ")\ngamePath=@ByteArray(" + str(game or self.root / "Game")
            + ")\n" + extra).encode())

    def files(self):
        return {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                for path in self.root.rglob("*") if path.is_file()}

    def token(self):
        report = se_lab.preflight()
        self.assertEqual(report["status"], "ready_for_explicit_launch", report["checks"])
        return report["review_token"]

    def failed(self, report):
        return {row["code"] for row in report["checks"] if not row["passed"]}

    def arm(self):
        return se_lab.arm(self.token())

    def result(self, run_id, **extra):
        request = self.read_json(se_lab.REQUEST) if (self.root / se_lab.REQUEST).exists() else {}
        value = dict(version=1, run_id=run_id, started_at_utc=request.get("started_at_utc", "old"))
        if request.get("scenario") is not None:
            value["scenario"] = se_lab.SCENARIO_RESULTS[request["scenario"]]
        value.update(extra)
        self.json(self.result_path, value)

    def test_preflight_readonly_hashes_runtime_profile_and_plugin_winner(self):
        before = self.files()
        with patch.object(se_lab.subprocess, "Popen", side_effect=AssertionError("No launch")):
            report = se_lab.preflight()
        self.assertEqual(report["status"], "ready_for_explicit_launch")
        self.assertEqual(report["runtime_version"], "1.6.1170.0")
        self.assertFalse(report["writes_performed"])
        self.assertFalse(report["runtime_verified"])
        self.assertEqual(report["review_token"], se_lab.preflight()["review_token"])
        self.assertEqual(before, self.files())
        self.closed.assert_not_called()

    def test_hash_and_actual_version_are_independent_checks(self):
        self.write("Game/SkyrimSE.exe", b"changed executable")
        self.assertIn("file_hash", self.failed(se_lab.preflight()))
        with patch.object(se_lab, "_file_version", return_value="1.6.640.0"):
            self.assertIn("runtime_version", self.failed(se_lab.preflight()))

    def test_production_game_path_and_foreign_directory_override_blocked(self):
        self.ini(game=self.root.parent / "production")
        self.assertIn("mo2_game_path", self.failed(se_lab.preflight()))
        self.ini(extra="[Settings]\nmod_directory=" + str(self.root.parent / "production-mods") + "\n")
        self.assertIn("mo2_directory", self.failed(se_lab.preflight()))

    def test_alternate_lab_directory_cannot_bypass_audited_mods(self):
        self.ini(extra="[Settings]\nmod_directory=" + str(self.root / "MO2/alternateMods") + "\n")
        self.assertIn("mo2_directory", self.failed(se_lab.preflight()))
        self.ini(extra="[Settings]\nmod_directory=" + str(self.root / "MO2/mods") + "\n")
        self.assertEqual(se_lab.preflight()["status"], "ready_for_explicit_launch")

    def test_global_saves_or_settings_and_missing_local_ini_blocked(self):
        relative = "MO2/profiles/" + se_lab.PROFILE
        self.write(relative + "/settings.ini", b"[General]\nLocalSaves=false\nLocalSettings=true\n")
        self.assertIn("profile_local_state", self.failed(se_lab.preflight()))
        self.write(relative + "/settings.ini", b"[General]\nLocalSaves=true\nLocalSettings=false\n")
        self.assertIn("profile_local_state", self.failed(se_lab.preflight()))
        self.write(relative + "/settings.ini", b"[General]\nLocalSaves=true\nLocalSettings=true\n")
        (self.root / relative / "SkyrimPrefs.ini").unlink()
        self.assertIn("profile_ini", self.failed(se_lab.preflight()))

    def test_optional_custom_ini_changes_invalidate_review(self):
        relative = "MO2/profiles/" + se_lab.PROFILE + "/SkyrimCustom.ini"
        token = self.token()
        self.write(relative, b"[General]\nsLocalSavePath=AlternateSaves\\\n")
        with self.assertRaisesRegex(ValueError, "token"):
            se_lab.arm(token)
        token = self.token()
        self.write(relative, b"[General]\nsLocalSavePath=ChangedAgain\\\n")
        with self.assertRaisesRegex(ValueError, "token"):
            se_lab.arm(token)

    def test_missing_portable_or_wrong_profile_blocked(self):
        (self.root / "MO2/portable.txt").unlink()
        self.assertIn("portable_instance", self.failed(se_lab.preflight()))
        value = (self.root / "MO2/ModOrganizer.ini").read_text().replace(se_lab.PROFILE, "Production")
        self.write("MO2/ModOrganizer.ini", value.encode())
        self.assertIn("mo2_profile", self.failed(se_lab.preflight()))

    def test_disabled_plugin_or_shadowed_plugin_blocked(self):
        self.write("MO2/profiles/" + se_lab.PROFILE + "/plugins.txt", b"HoldMusicSELab.esp\n")
        self.assertIn("required_plugins", self.failed(se_lab.preflight()))
        self.write("MO2/profiles/" + se_lab.PROFILE + "/plugins.txt", b"*HoldMusicSELab.esp\n")
        self.write("MO2/overwrite/HoldMusicSELab.esp", b"unknown override")
        self.assertIn("plugin_winner_hash", self.failed(se_lab.preflight()))

    def test_declared_script_shadow_rejected(self):
        relative = "MO2/mods/Harness/Scripts/HM_Library.pex"
        self.write(relative, b"fixture script")
        self.manifest["files"].append(dict(path=relative, sha256=self.sha(relative)))
        self.save_manifest()
        self.write("MO2/overwrite/Scripts/HM_Library.pex", b"another script")
        self.assertIn("declared_virtual_winner", self.failed(se_lab.preflight()))

    def test_no_skyrimnet_or_disabled_harness_control(self):
        self.write("MO2/mods/Harness/SKSE/Plugins/SkyrimNet.dll", b"forbidden first-tier plugin")
        self.assertIn("skyrimnet_disabled", self.failed(se_lab.preflight()))
        self.json("MO2/mods/Harness/" + se_lab.CONTROL,
                  dict(version=1, enabled=False, world_id="hold-music-se-lab"))
        self.assertIn("lab_control", self.failed(se_lab.preflight()))

    def test_invalid_manifest_escape_duplicate_and_paid_flag_rejected(self):
        self.manifest["logs"][0]["path"] = "../outside.json"
        self.save_manifest()
        with self.assertRaises(ValueError):
            se_lab.preflight()
        self.manifest["logs"][0]["path"] = self.result_path
        self.manifest["paid_generation"] = True
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "paid"):
            se_lab.preflight()
        self.write(se_lab.MANIFEST, b'{"version":1,"version":1}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            se_lab.preflight()

    def test_arm_preserves_previous_request_and_launches_nothing(self):
        with patch.object(se_lab.subprocess, "Popen", side_effect=AssertionError("No launch")):
            first = self.arm()
            first_request = (self.root / se_lab.REQUEST).read_bytes()
            second = self.arm()
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual((Path(second["directory"]) / "previous-request.json").read_bytes(), first_request)
        self.assertEqual(self.read_json(se_lab.REQUEST)["run_id"], second["run_id"])
        self.assertNotIn("auto_run", self.read_json(se_lab.REQUEST))
        self.assertNotIn("scenario", self.read_json(se_lab.REQUEST))
        self.assertFalse(second["process_started"])
        self.closed.assert_not_called()

    def test_explicit_scenario_is_saved_and_emitted_without_launch(self):
        with patch.object(se_lab.subprocess, "Popen", side_effect=AssertionError("No launch")):
            result = se_lab.arm(self.token(), scenario="focused-interrupt")
        request = self.read_json(se_lab.REQUEST)
        self.assertIs(request["auto_run"], True)
        self.assertEqual(request["scenario"], "focused-interrupt")
        self.assertEqual(result["scenario"], "focused-interrupt")
        saved = self.read_json("runs/" + result["run_id"] + "/run.json")
        self.assertEqual(saved["scenario"], "focused-interrupt")
        self.result(result["run_id"])
        evidence = se_lab.collect(result["run_id"])
        self.assertTrue(evidence["fresh_required_evidence"])
        self.assertTrue(evidence["logs"][0]["scenario_matches"])
        self.assertTrue(evidence["logs"][0]["request_timestamp_matches"])

    def test_invalid_scenario_cannot_write_or_dispatch(self):
        before = self.files()
        token = self.token()
        with patch.object(se_lab.subprocess, "Popen") as spawn:
            for value in ("unknown", "", True, ["focused-complete"]):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(ValueError, "Scenario"):
                        se_lab.arm(token, scenario=value)
                    with self.assertRaisesRegex(ValueError, "Scenario"):
                        se_lab.launch(token, scenario=value)
            spawn.assert_not_called()
        self.assertEqual(before, self.files())

    def test_stale_and_nonascii_review_tokens_refuse_request(self):
        token = self.token()
        self.write("MO2/profiles/" + se_lab.PROFILE + "/loadorder.txt", b"HoldMusicSELab.esp\n")
        for value in (token, "not-a-token", "é"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "token"):
                se_lab.arm(value)
        self.assertFalse((self.root / se_lab.REQUEST).exists())

    def fake_popen(self, *, timeout=False, create_result=False):
        outer = self
        class Process:
            pid = 4242
            def __init__(self, command, **kwargs):
                outer.assertEqual(command[0], str(outer.root / "MO2/ModOrganizer.exe"))
                outer.assertEqual(command[1:5], ["-i", "", "-p", se_lab.PROFILE])
                outer.assertEqual(command[-1], str(outer.root / "Game/skse64_loader.exe"))
                outer.assertFalse(kwargs["shell"])
                outer.assertEqual(kwargs["cwd"], str(outer.root / "MO2"))
                kwargs["stdout"].write(b"fake isolated launcher\n")
                if create_result:
                    outer.result(outer.read_json(se_lab.REQUEST)["run_id"], passed=True)
            def wait(self, timeout):
                if timeout_flag:
                    raise subprocess.TimeoutExpired("fixture", timeout)
                return 0
            def kill(self):
                raise AssertionError("Must never kill")
            def terminate(self):
                raise AssertionError("Must never terminate")
        timeout_flag = timeout
        return Process

    def test_launch_uses_only_isolated_mo2_and_captures_output(self):
        with patch.object(se_lab.subprocess, "Popen", self.fake_popen(create_result=True)):
            result = se_lab.launch(self.token(), timeout_seconds=1, scenario="ambient-entry")
        self.assertEqual(result["status"], "launcher_exited")
        self.assertTrue(result["process_started"])
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["processes_terminated"])
        self.assertEqual((Path(result["directory"]) / "launcher-output.log").read_bytes(),
                         b"fake isolated launcher\n")
        self.assertTrue(se_lab.collect(result["run_id"])["fresh_required_evidence"])
        self.assertEqual(self.read_json(se_lab.REQUEST)["scenario"], "ambient-entry")

    def test_timeout_leaves_owned_and_unrelated_processes_alone(self):
        with patch.object(se_lab.subprocess, "Popen", self.fake_popen(timeout=True)):
            result = se_lab.launch(self.token(), timeout_seconds=1)
        self.assertEqual(result["status"], "launcher_wait_timeout")
        self.assertIsNone(result["launcher_returncode"])
        self.assertFalse(result["processes_terminated"])

    def test_existing_or_unknown_process_state_blocks_launch(self):
        for response in (dict(verified=True, quiescent=False, processes=["skyrimvr.exe"]),
                         dict(verified=False, quiescent=True, processes=[]),
                         dict(verified=1, quiescent=True, processes=[])):
            with self.subTest(response=response), \
                    patch.object(se_lab, "default_process_probe", return_value=response), \
                    patch.object(se_lab.subprocess, "Popen") as spawn:
                with self.assertRaisesRegex(ValueError, "Close all"):
                    se_lab.launch(self.token())
                spawn.assert_not_called()

    def test_failed_launch_does_not_support_current_run_collection(self):
        with patch.object(se_lab.subprocess, "Popen", side_effect=OSError("fixture failure")):
            result = se_lab.launch(self.token())
        self.assertEqual(result["status"], "launch_failed")
        with self.assertRaisesRegex(ValueError, "confirmed launcher"):
            se_lab.collect(result["run_id"])

    def test_matching_fresh_result_archived_exactly_but_not_called_runtime_pass(self):
        run = self.arm()
        self.result(run["run_id"], scenario="smoke", passed=True)
        raw = (self.root / self.result_path).read_bytes()
        report = se_lab.collect(run["run_id"])
        self.assertEqual(report["status"], "evidence_collected")
        self.assertTrue(report["logs"][0]["run_id_matches"])
        self.assertFalse(report["runtime_verified"])
        self.assertEqual((Path(report["directory"]) / "logs/harness.bin").read_bytes(), raw)
        second = se_lab.collect(run["run_id"])
        self.assertNotEqual(report["capture_id"], second["capture_id"])
        self.assertEqual((Path(report["directory"]) / "logs/harness.bin").read_bytes(), raw)

    def test_old_touched_result_does_not_count_as_new(self):
        self.result("older-run", passed=True)
        run = self.arm()
        os.utime(self.root / self.result_path, None)
        report = se_lab.collect(run["run_id"])
        self.assertEqual(report["status"], "incomplete_evidence")
        self.assertFalse(report["logs"][0]["content_changed"])
        self.assertFalse(report["logs"][0]["run_id_matches"])

    def test_changed_nonce_mismatch_or_old_mtime_refused(self):
        run = self.arm()
        self.result("different-run")
        self.assertFalse(se_lab.collect(run["run_id"])["fresh_required_evidence"])
        self.result(run["run_id"])
        started = self.read_json("runs/" + run["run_id"] + "/run.json")["started_ns"]
        os.utime(self.root / self.result_path, ns=(started - 1, started - 1))
        report = se_lab.collect(run["run_id"])
        self.assertTrue(report["logs"][0]["run_id_matches"])
        self.assertFalse(report["logs"][0]["written_after_start"])
        self.assertFalse(report["fresh_required_evidence"])

    def test_matching_nonce_with_wrong_scenario_or_timestamp_is_not_fresh(self):
        run = se_lab.arm(self.token(), scenario="focused-complete")
        self.result(run["run_id"], scenario="focused_interrupt")
        report = se_lab.collect(run["run_id"])
        self.assertTrue(report["logs"][0]["run_id_matches"])
        self.assertFalse(report["logs"][0]["scenario_matches"])
        self.assertFalse(report["fresh_required_evidence"])
        self.result(run["run_id"], started_at_utc="old timestamp")
        report = se_lab.collect(run["run_id"])
        self.assertTrue(report["logs"][0]["scenario_matches"])
        self.assertFalse(report["logs"][0]["request_timestamp_matches"])
        self.assertFalse(report["fresh_required_evidence"])

    def test_actual_harness_result_scenario_names_match_explicit_requests(self):
        # HM_LabHarness.TryAutorun maps hyphenated requests to these exact
        # BeginRun/SaveResult names; do not derive this fixture from our mapping.
        pairs = (("ambient-entry", "ambient_entry"),
                 ("focused-complete", "focused_complete"),
                 ("focused-interrupt", "focused_interrupt"))
        for requested, emitted in pairs:
            with self.subTest(scenario=requested):
                run = se_lab.arm(self.token(), scenario=requested)
                request = self.read_json(se_lab.REQUEST)
                result = dict(
                    version=1, run_id=run["run_id"], started_at_utc=request["started_at_utc"],
                    world_id="hold-music-se-lab", scenario=emitted, status="passed", reason="",
                    expected_performer_id="sven",
                    expected_outcome="interrupted" if requested == "focused-interrupt" else "completed",
                    started_real_seconds=10.0, observed_real_seconds=14.0,
                    trace_baseline=0, trace_cursor=4, receipt_baseline=0, receipt_index=0,
                    selected_slot=1, selected_identity_key="a" * 64,
                    runtime_engine_observed=True, audio_audibility_verified=False,
                    animation_visual_verified=False,
                    ambient_scheduling_bypassed=requested != "ambient-entry",
                    controller_entry_setup_injected=requested != "ambient-entry",
                    scripted_fixture_teleport=True, fixture_moved=True, globals_restored=True,
                    assertions=dict(performance_start=True, performance_stop=True, evidence_valid=True))
                self.json(self.result_path, result)
                report = se_lab.collect(run["run_id"])
                self.assertTrue(report["fresh_required_evidence"])
                self.assertEqual(report["expected_result_scenario"], emitted)
                self.assertEqual(report["scenario"], requested)
                self.assertTrue(report["logs"][0]["scenario_matches"])
                self.assertFalse(report["runtime_verified"])
                self.assertEqual(json.loads((Path(report["directory"]) / "logs/harness.bin").read_bytes()),
                                 result)
                # A request-shaped result must not be mistaken for the known
                # harness protocol merely because it echoes the run nonce.
                result["scenario"] = requested
                self.json(self.result_path, result)
                self.assertFalse(se_lab.collect(run["run_id"])["fresh_required_evidence"])
    def test_missing_or_malformed_result_is_incomplete(self):
        run = self.arm()
        report = se_lab.collect(run["run_id"])
        self.assertFalse(report["fresh_required_evidence"])
        self.assertIsNone(report["logs"][0]["archived_file"])
        self.write(self.result_path, b'{"run_id": "x", "run_id":"y"}')
        self.assertFalse(se_lab.collect(run["run_id"])["fresh_required_evidence"])

    def test_input_changes_before_request_publication_refused(self):
        original = se_lab._recheck_inputs
        def changed(report):
            self.write("MO2/mods/Harness/HoldMusicSELab.esp", b"modified after first preflight")
            return original(report)
        with patch.object(se_lab, "_recheck_inputs", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.arm()
        self.assertFalse((self.root / se_lab.REQUEST).exists())

    def test_evidence_changed_during_collection_never_gets_completed_descriptor(self):
        run = self.arm()
        self.result(run["run_id"])
        original, mutated = se_lab._Snapshot.read, False
        def change(snapshot, path, **kwargs):
            nonlocal mutated
            result = original(snapshot, path, **kwargs)
            if path == self.root / self.result_path and not mutated:
                mutated = True
                self.result(run["run_id"], changed=True)
            return result
        with patch.object(se_lab._Snapshot, "read", change):
            with self.assertRaisesRegex(ValueError, "changed"):
                se_lab.collect(run["run_id"])
        self.assertEqual(list((self.root / "runs" / run["run_id"]).rglob("evidence.json")), [])

    def test_invalid_run_id_and_saved_outside_path_refused(self):
        with self.assertRaises(ValueError):
            se_lab.collect("../outside")
        run = self.arm()
        relative = "runs/" + run["run_id"] + "/run.json"
        data = self.read_json(relative)
        data["logs"][0]["path"] = "../outside.json"
        self.json(relative, data)
        with self.assertRaises(ValueError):
            se_lab.collect(run["run_id"])

    def test_hardlinked_log_rejected(self):
        self.write("outside-fixture.log", b"do not follow aliases")
        path = self.root / self.result_path
        path.parent.mkdir(parents=True, exist_ok=True)
        os.link(self.root / "outside-fixture.log", path)
        with self.assertRaisesRegex(ValueError, "unaliased"):
            self.arm()

    def test_cli_has_no_root_override_or_implicit_launch(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(se_lab.main(["preflight"]), 0)
        self.assertFalse(json.loads(stdout.getvalue())["writes_performed"])
        with redirect_stderr(stderr), self.assertRaises(SystemExit):
            se_lab.main(["preflight", "--lab-root", str(self.root.parent)])

    def test_cli_explicit_scenario_routes_to_arm(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(se_lab.main(["arm", "--review-token", self.token(),
                                         "--scenario", "focused-complete"]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["scenario"], "focused-complete")
        self.assertIs(self.read_json(se_lab.REQUEST)["auto_run"], True)


if __name__ == "__main__":
    unittest.main()
