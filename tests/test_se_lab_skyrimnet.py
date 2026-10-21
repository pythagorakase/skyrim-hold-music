"""Only synthetic archives and temporary installations; no real lab mutations."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from hold_music import se_lab_skyrimnet as tier
from tools import se_lab_skyrimnet as cli


class SkyrimNetTierTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "lab"
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(tier, "LAB_ROOT", self.root).start()
        patch.object(tier.baseline, "_file_version", return_value="1.6.1170.0").start()
        patch.object(tier, "_ports_available", return_value=True).start()
        self.write("Game/SkyrimSE.exe", b"synthetic1170")
        self.write("Game/skse64_loader.exe", b"synthetic-loader")
        self.write("Game/skse64_1_6_1170.dll", b"synthetic-skse")
        self.write("Game/Data/Skyrim.esm", b"synthetic-vanilla")
        self.write("MO2/ModOrganizer.exe", b"synthetic-mo2")
        self.write("MO2/mods/PapyrusUtil SE 4.6/SKSE/Plugins/PapyrusUtil.dll", b"synthetic-pu")
        self.write("MO2/mods/MCM Helper SE 1.6.2/SKSE/Plugins/MCMHelper.dll", b"synthetic-mcm")
        for mod in tier.BASE_MODS:
            self.write("MO2/mods/" + mod + "/source.txt", mod.encode())
        for mod, plugin in zip(tier.BASE_MODS, tier.BASE_PLUGINS):
            self.write("MO2/mods/" + mod + "/" + plugin, plugin.encode())
        self.manifest = dict(version=1, paid_generation=False,
            runtime=dict(path="Game/SkyrimSE.exe", sha256=self.sha("Game/SkyrimSE.exe"), version="1.6.1170.0"),
            loader=dict(path="Game/skse64_loader.exe", sha256=self.sha("Game/skse64_loader.exe")),
            mo2=dict(path="MO2/ModOrganizer.exe", sha256=self.sha("MO2/ModOrganizer.exe")),
            files=[dict(path="Game/skse64_1_6_1170.dll", sha256=self.sha("Game/skse64_1_6_1170.dll"))],
            required_mods=list(tier.BASE_MODS), required_plugins=list(tier.BASE_PLUGINS))
        for path in (self.root / "MO2/mods").rglob("*"):
            if path.is_file():
                relative = path.relative_to(self.root).as_posix()
                self.manifest["files"].append(dict(path=relative, sha256=self.sha(relative)))
        self.save_manifest()
        self.archives = []
        for number, (mod, dll) in enumerate((
                ("SkyrimNet beta26-rc4 Clean", "SkyrimNet.dll"), ("PrismaUI 1.5.1", "PrismaUI.dll"),
                ("Media Keys Fix 1.0.1", "MediaKeysFix.dll"), ("Papyrus Extender SE 6.4.3", "po3_PapyrusExtender.dll"),
                ("powerofthree Tweaks SE 1.15.1", "po3_Tweaks.dll"))):
            path = self.root / (str(number) + ".zip")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("selected/SKSE/Plugins/" + dll, ("synthetic-" + dll).encode())
                if number == 0:
                    archive.writestr("selected/SkyrimNet.esp", b"synthetic-SN")
                archive.writestr("ignored/foreign.dll", b"not-selected")
            self.archives.append(dict(mod=mod, path=path, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                      kind="zip", prefixes=("selected/",)))
        patch.object(tier, "ARCHIVES", tuple(self.archives)).start()
        application = self.root / "clean-mo2.zip"
        with zipfile.ZipFile(application, "w") as archive:
            archive.writestr("ModOrganizer.exe", b"synthetic-mo2")
            archive.writestr("dlls/Qt6Core.dll", b"synthetic-qt")
            archive.writestr("plugins/game_skyrimse.dll", b"synthetic-game-support")
        self.application = dict(path=application, sha256=hashlib.sha256(application.read_bytes()).hexdigest(),
                                kind="zip", prefixes=("",))
        patch.object(tier, "MO2_ARCHIVE", self.application).start()

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def sha(self, relative):
        return hashlib.sha256((self.root / relative).read_bytes()).hexdigest()

    def save_manifest(self):
        self.write(tier.baseline.MANIFEST, json.dumps(self.manifest).encode())

    def files(self):
        return {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                for path in self.root.rglob("*") if path.is_file()}

    def prepare_fixture(self):
        report = tier.preparation_plan()
        seeds = dict((row["virtual_path"], row["text"]) for row in report["configuration_seeds"])
        for row in report["files"]:
            source = row["source"]
            if "path" in source:
                raw = Path(source["path"]).read_bytes()
            elif "archive" in source:
                with zipfile.ZipFile(source["archive"]) as archive:
                    raw = archive.read(source["member"])
            else:
                virtual = row["path"].split("/mods/" + tier.CONFIG_MOD + "/", 1)[1]
                raw = seeds[virtual].encode()
            self.write(row["path"], raw)
        prefix = tier.INSTANCE + "/profiles/" + tier.PROFILE + "/"
        self.write(tier.INSTANCE + "/portable.txt", b"")
        self.ini()
        self.write(prefix + "settings.ini", b"[General]\nLocalSaves=true\nLocalSettings=true\n")
        self.write(prefix + "Skyrim.ini", b"[General]\nsLanguage=ENGLISH\n")
        self.write(prefix + "SkyrimPrefs.ini", b"[Display]\nbFull Screen=0\n")
        self.write(prefix + "modlist.txt", "".join("+" + name + "\n" for name in report["active_mods"]).encode())
        self.write(prefix + "plugins.txt", "".join("*" + name + "\n" for name in report["enabled_plugins"]).encode())
        self.write(prefix + "loadorder.txt", "".join(name + "\n" for name in report["enabled_plugins"]).encode())

    def ini(self, extra="", game=None):
        self.write(tier.INSTANCE + "/ModOrganizer.ini", (
            "[General]\ngameName=Skyrim Special Edition\nselected_profile=@ByteArray(" + tier.PROFILE
            + ")\ngamePath=@ByteArray(" + str(game or self.root / "Game") + ")\n" + extra).encode())

    @staticmethod
    def codes(report):
        return {row["code"] for row in report["blockers"]}

    def test_plan_is_readonly_exact_disabled_recipe_and_tier_scoped(self):
        before = self.files()
        with patch.object(tier.subprocess, "run", side_effect=AssertionError("No child process for ZIP fixtures")):
            report = tier.preparation_plan()
        self.assertEqual(report["status"], "preparation_plan")
        self.assertEqual(before, self.files())
        self.assertEqual(report["review_token"], tier.preparation_plan()["review_token"])
        self.assertFalse(report["can_launch"])
        self.assertFalse(report["can_apply"])
        self.assertFalse(report["egress_verified"])
        self.assertFalse(report["runtime_verified"])
        self.assertFalse(report["writes_performed"])
        self.assertEqual(report["tier"], "skyrimnet-beta26-rc4-disabled-v1")
        self.assertFalse(any("ignored" in row["path"] for row in report["files"]))
        seeds = {row["virtual_path"]: json.loads(row["text"]) for row in report["configuration_seeds"]
                 if row["virtual_path"].endswith((".yaml", ".json"))}
        self.assertIs(seeds[tier.CONFIG + "SkyrimNet.yaml"]["general"]["globalAIEnabled"], False)
        self.assertEqual(seeds[tier.CONFIG + "SkyrimNet.yaml"]["tts"]["engine"], "noop")
        self.assertEqual(seeds[tier.CONFIG + "STT.yaml"]["backend"], "none")
        self.assertFalse(seeds[tier.baseline.CONTROL]["enabled"])
        self.assertNotIn(tier.CONFIG + "Auth.yaml", seeds)
        self.assertEqual(tier.configuration_seeds()["SKSE/Plugins/po3_Tweaks.ini"],
                         "[Fixes]\nLoad EditorIDs = true\n")

    def test_preflight_verifies_only_prepared_files_not_runtime(self):
        self.prepare_fixture()
        before = self.files()
        report = tier.preflight()
        self.assertEqual(report["status"], "prepared_files_verified", report["blockers"])
        self.assertEqual(before, self.files())
        self.assertFalse(report["native_verified"])
        self.assertFalse(report["can_launch"])
        self.assertTrue(report["ports_available"])
        self.assertEqual(len(report["config_winners"]), len(report["configuration_seeds"]))
        self.assertEqual(len(report["native_winners"]), 7)

    def test_preflight_missing_instance_blocks_without_creating_it(self):
        before = self.files()
        report = tier.preflight()
        self.assertEqual(report["status"], "blocked")
        self.assertIn("file_hash", self.codes(report))
        self.assertEqual(before, self.files())

    def test_pinned_archive_drift_rejected_before_payload_trust(self):
        self.archives[0]["path"].write_bytes(b"replaced")
        with self.assertRaisesRegex(ValueError, "Pinned archive"):
            tier.preparation_plan()

    def test_archive_path_escape_and_duplicate_case_rejected(self):
        for members in (("../escape",), ("selected/Same", "selected/same")):
            with self.subTest(members=members):
                path = self.archives[0]["path"]
                with zipfile.ZipFile(path, "w") as archive:
                    for name in members:
                        archive.writestr(name, b"fixture")
                self.archives[0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaises(ValueError):
                    tier.preparation_plan()

    def test_baseline_native_source_and_version_must_match(self):
        self.write("Game/skse64_1_6_1170.dll", b"new-native")
        with self.assertRaisesRegex(ValueError, "Baseline source"):
            tier.preparation_plan()
        self.write("Game/skse64_1_6_1170.dll", b"synthetic-skse")
        with patch.object(tier.baseline, "_file_version", return_value="1.6.640.0"):
            with self.assertRaisesRegex(ValueError, "1.6.1170"):
                tier.preparation_plan()

    def test_shared_game_cannot_supply_skyrimnet_or_native_plugins(self):
        self.write("Game/Data/SKSE/Plugins/SkyrimNet/config/Auth.yaml", b"private sentinel")
        self.write("Game/Data/SKSE/Plugins/unknown.dll", b"native")
        report = tier.preparation_plan()
        self.assertIn("physical_game_skyrimnet", self.codes(report))
        self.assertIn("physical_game_plugin", self.codes(report))
        self.assertNotIn("private sentinel", json.dumps(report))

    def test_duplicate_approved_native_name_cannot_create_a_second_winner(self):
        relative = "MO2/mods/Hold Music Candidate/SKSE/Plugins/PapyrusUtil.dll"
        self.write(relative, b"another-papyrus")
        self.manifest["files"].append(dict(path=relative, sha256=self.sha(relative)))
        self.save_manifest()
        report = tier.preparation_plan()
        self.assertIn("native_recipe", self.codes(report))

    def test_separate_instance_does_not_accept_baseline_redirect(self):
        self.prepare_fixture()
        self.ini(extra="[Settings]\noverwrite_directory=" + str(self.root / "MO2/overwrite") + "\n")
        self.assertIn("directory_redirect", self.codes(tier.preflight()))
        self.ini(game=self.root.parent / "Steam/Skyrim")
        self.assertIn("mo2_identity", self.codes(tier.preflight()))

    def test_unknown_mod_plugin_and_private_state_block(self):
        self.prepare_fixture()
        prefix = tier.INSTANCE + "/profiles/" + tier.PROFILE + "/"
        path = self.root / (prefix + "modlist.txt")
        path.write_text(path.read_text() + "+Unreviewed\n")
        self.write(tier.INSTANCE + "/mods/Unreviewed/SKSE/Plugins/Other.dll", b"other")
        self.write(tier.INSTANCE + "/private/Auth.yaml", b"api_key: DO_NOT_LEAK")
        report = tier.preflight()
        self.assertTrue({"unapproved_payload", "profile_list", "private_runtime_state"} <= self.codes(report))
        self.assertNotIn("DO_NOT_LEAK", json.dumps(report))

    def test_modified_or_shadowed_config_cannot_pass(self):
        self.prepare_fixture()
        relative = tier.INSTANCE + "/mods/" + tier.CONFIG_MOD + "/" + tier.CONFIG + "SkyrimNet.yaml"
        self.write(relative, b'{"general":{"globalAIEnabled":true}}')
        self.write(tier.INSTANCE + "/overwrite/" + tier.CONFIG + "Providers.yaml", b"providers: []")
        report = tier.preflight()
        self.assertTrue({"file_hash", "unapproved_payload", "config_winner"} <= self.codes(report))

    def test_global_profile_state_disabled_list_and_port_collision_block(self):
        self.prepare_fixture()
        prefix = tier.INSTANCE + "/profiles/" + tier.PROFILE + "/"
        self.write(prefix + "settings.ini", b"[General]\nLocalSaves=false\nLocalSettings=true\n")
        self.write(prefix + "plugins.txt", b"SkyrimNet.esp\n")
        with patch.object(tier, "_ports_available", return_value=False):
            report = tier.preflight()
        self.assertTrue({"local_profile", "profile_list", "ports_busy"} <= self.codes(report))

    def test_loadorder_and_existing_save_do_not_qualify_as_fresh_tier(self):
        self.prepare_fixture()
        prefix = tier.INSTANCE + "/profiles/" + tier.PROFILE + "/"
        first = tier.preflight()["review_token"]
        self.write(prefix + "loadorder.txt", b"SkyrimNet.esp\n")
        self.write(prefix + "saves/old.ess", b"old-world")
        report = tier.preflight()
        self.assertNotEqual(first, report["review_token"])
        self.assertTrue({"profile_list", "private_runtime_state"} <= self.codes(report))

    def test_source_manifest_duplicate_and_unapproved_path_block(self):
        self.manifest["files"].append(self.manifest["files"][0])
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            tier.preparation_plan()
        self.manifest["files"].pop()
        self.manifest["files"].append(dict(path="../outside", sha256="a" * 64))
        self.save_manifest()
        with self.assertRaises(ValueError):
            tier.preparation_plan()

    def test_hash_and_shared_game_inventory_changes_bind_review_token(self):
        first = tier.preparation_plan()["review_token"]
        self.write("Game/Data/Skyrim.esm", b"different-vanilla")
        self.assertNotEqual(first, tier.preparation_plan()["review_token"])

    def test_late_shared_game_mutation_is_not_accepted(self):
        original = tier._Snapshot.finish
        def changed(snapshot):
            result = original(snapshot)
            self.write("Game/Data/Skyrim.esm", b"late-change")
            return result
        with patch.object(tier._Snapshot, "finish", changed):
            with self.assertRaisesRegex(ValueError, "Shared Game changed"):
                tier.preparation_plan()

    def test_clean_environment_has_no_inherited_keys_tokens_or_proxies(self):
        source = {"SystemRoot": r"C:\Windows", "PATH": "fixture-path", "APPDATA": "fixture-appdata",
                  "OPENROUTER_API_KEY": "secret-a", "AWS_SECRET_ACCESS_KEY": "secret-b",
                  "HTTP_PROXY": "private-proxy", "UNKNOWN_SECRET": "secret-c", "SteamAppId": "611670"}
        clean = tier.clean_launch_environment(source)
        self.assertEqual(clean, {"SystemRoot": r"C:\Windows", "PATH": "fixture-path", "APPDATA": "fixture-appdata",
                                 "SteamAppId": "489830", "SteamGameId": "489830"})
        self.assertEqual(source["SteamAppId"], "611670")

    def test_alias_rejected_without_following_target(self):
        destination = self.root / "Game/Data/aliased"
        try:
            destination.symlink_to(self.root.parent, target_is_directory=True)
        except OSError:
            self.skipTest("Platform does not permit test symlink")
        with self.assertRaises(ValueError):
            tier.preparation_plan()

    def test_cli_has_no_write_or_launch_route_and_no_secret_environment_output(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "CLI_SECRET_SENTINEL"}), redirect_stdout(output):
            self.assertEqual(cli.main(["plan"]), 0)
        value = json.loads(output.getvalue())
        self.assertNotIn("files", value)
        self.assertGreater(value["file_count"], 10)
        self.assertNotIn("CLI_SECRET_SENTINEL", output.getvalue())
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["launch"])

    @staticmethod
    def closed():
        return dict(verified=True, quiescent=True, processes=[])

    def install_fixture(self):
        plan = tier.installation_plan()
        return tier.install(plan["review_token"], process_probe=self.closed)

    def test_install_review_is_readonly_complete_and_separate_from_inspection_token(self):
        before = self.files()
        plan = tier.installation_plan()
        self.assertEqual(plan["status"], "installation_plan")
        self.assertTrue(plan["can_apply"])
        self.assertEqual(before, self.files())
        self.assertIn("dlls/Qt6Core.dll", plan["inputs"]["files"])
        self.assertIn("plugins/game_skyrimse.dll", plan["inputs"]["files"])
        self.assertIn("tools/se_lab_skyrimnet.py", plan["inputs"]["implementation"])
        self.assertEqual(plan["inputs"]["application_archive"]["sha256"], self.application["sha256"])
        for token in (tier.preparation_plan()["review_token"], "☃", "wrong"):
            with self.assertRaisesRegex(ValueError, "review"):
                tier.install(token, process_probe=self.closed)
        self.assertEqual(before, self.files())

    def test_install_rejects_private_baseline_sources_before_copy(self):
        for name in ("Auth.yaml", "state.db", "saves/old.ess"):
            with self.subTest(name=name):
                relative = "MO2/mods/Hold Music Lab Data/" + name
                self.write(relative, b"PRIVATE_SENTINEL")
                self.manifest["files"].append(dict(path=relative, sha256=self.sha(relative)))
                self.save_manifest()
                with self.assertRaisesRegex(ValueError, "private runtime state"):
                    tier.installation_plan()
                self.manifest["files"].pop()
        self.assertFalse((self.root / tier.INSTANCE).exists())

    def test_changed_application_or_instance_state_in_distribution_blocks(self):
        self.application["path"].write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Pinned archive"):
            tier.installation_plan()
        with zipfile.ZipFile(self.application["path"], "w") as archive:
            archive.writestr("ModOrganizer.exe", b"synthetic-mo2")
            archive.writestr("ModOrganizer.ini", b"private-account-state")
        self.application["sha256"] = hashlib.sha256(self.application["path"].read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "instance state"):
            tier.installation_plan()

    def test_tar_single_stream_has_exact_member_boundaries_and_rejects_links(self):
        archive_path = self.root / "plain.tar"
        with tarfile.open(archive_path, "w") as archive:
            for name, raw in (("folder/first.txt", b"first"), ("second.txt", b"second")):
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
        spec = dict(path=archive_path, sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                    kind="tar", prefixes=("",))
        decoded = {name: bytes(raw) for name, raw, _ in tier._archive_payloads(spec, tier._Snapshot())}
        self.assertEqual(decoded, {"folder/first.txt": b"first", "second.txt": b"second"})
        with tarfile.open(archive_path, "w") as archive:
            info = tarfile.TarInfo("escape")
            info.type = tarfile.SYMTYPE
            info.linkname = "../outside"
            archive.addfile(info)
        spec["sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "member listing"):
            list(tier._archive_payloads(spec, tier._Snapshot()))

    def test_application_component_alias_is_rejected_in_review(self):
        with zipfile.ZipFile(self.application["path"], "a") as archive:
            archive.writestr("DLLS/other.dll", b"ambiguous component")
        self.application["sha256"] = hashlib.sha256(self.application["path"].read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "component case alias"):
            tier.installation_plan()

    def test_install_requires_absent_target_and_strict_process_proof_before_writes(self):
        plan = tier.installation_plan()
        before = self.files()
        for proof in ({"verified": 1, "quiescent": True, "processes": []},
                      {"verified": True, "quiescent": False, "processes": ["skyrimse.exe"]}):
            with self.assertRaisesRegex(ValueError, "closure"):
                tier.install(plan["review_token"], process_probe=lambda: proof)
        self.assertEqual(before, self.files())
        (self.root / tier.INSTANCE).mkdir()
        self.assertIn("target_exists", self.codes(tier.installation_plan()))
        with self.assertRaises(ValueError):
            tier.install(plan["review_token"], process_probe=self.closed)

    def test_stale_review_binds_baseline_and_implementation_before_writes(self):
        plan = tier.installation_plan()
        original = tier._implementation
        def changed(snapshot):
            value = original(snapshot)
            value["tools/se_lab_skyrimnet.py"] = "f" * 64
            return value
        with patch.object(tier, "_implementation", changed):
            with self.assertRaises(ValueError):
                tier.install(plan["review_token"], process_probe=self.closed)
        self.write("MO2/untouched.txt", b"unrelated baseline state")
        with self.assertRaises(ValueError):
            tier.install(plan["review_token"], process_probe=self.closed)
        self.assertFalse((self.root / tier.CONTROL).exists())

    def test_install_exact_payload_preserves_original_and_cannot_repeat(self):
        protected = tier._protected(self.root)
        report = self.install_fixture()
        self.assertEqual(report["status"], "installed_disabled", report)
        self.assertFalse(report["blockers"])
        self.assertTrue(report["writes_performed"])
        self.assertFalse(report["can_launch"])
        self.assertFalse(report["native_verified"])
        self.assertEqual(protected, tier._protected(self.root))
        self.assertEqual(tier.preflight()["status"], "prepared_files_verified")
        self.assertEqual((self.root / tier.INSTANCE / "dlls/Qt6Core.dll").read_bytes(), b"synthetic-qt")
        self.assertIn("retained_transaction", self.codes(tier.installation_plan()))
        before = self.files()
        with self.assertRaises(ValueError):
            tier.install(tier.installation_plan()["review_token"], process_probe=self.closed)
        self.assertEqual(before, self.files())

    def test_failure_before_stage_creation_has_explicit_retention_recovery(self):
        plan = tier.installation_plan()
        original = tier._journal_write
        def crash(control, journal, prior):
            result = original(control, journal, prior)
            if journal["state"] == "staging":
                raise OSError("fixture interruption before mkdir")
            return result
        with patch.object(tier, "_journal_write", crash), self.assertRaises(OSError):
            tier.install(plan["review_token"], process_probe=self.closed)
        self.assertEqual(tier.installation_status()["recovery_actions"], ["retain_partial"])
        recovery = tier.recover_installation("retain_partial")
        def during_recovery(control, journal, prior):
            result = original(control, journal, prior)
            if journal["state"] == "retaining":
                raise OSError("fixture interruption of journal-only recovery")
            return result
        with patch.object(tier, "_journal_write", during_recovery), self.assertRaises(OSError):
            tier.recover_installation("retain_partial", apply=True,
                review_token=recovery["review_token"], process_probe=self.closed)
        self.assertEqual(tier.installation_status()["recovery_actions"], ["retain_partial"])
        recovery = tier.recover_installation("retain_partial")
        result = tier.recover_installation("retain_partial", apply=True,
            review_token=recovery["review_token"], process_probe=self.closed)
        self.assertEqual(result["status"], "retained_partial")
        self.assertFalse((self.root / tier.INSTANCE).exists())

    def test_partial_failure_preserved_and_reviewed_retention_never_resumes(self):
        plan = tier.installation_plan()
        original = tier._new_file
        def interrupted(*args):
            original(*args)
            raise OSError("fixture disk failure")
        with patch.object(tier, "_new_file", interrupted), self.assertRaises(OSError):
            tier.install(plan["review_token"], process_probe=self.closed)
        stage = self.root / tier.CONTROL / "stage"
        before = tier._inventory(stage)
        review = tier.recover_installation("retain_partial")
        self.assertEqual(before, tier._inventory(stage))
        with self.assertRaises(ValueError):
            tier.recover_installation("retain_partial", apply=True, review_token="wrong", process_probe=self.closed)
        result = tier.recover_installation("retain_partial", apply=True,
            review_token=review["review_token"], process_probe=self.closed)
        self.assertEqual(result["status"], "retained_partial")
        retained = tier._inventory(self.root / tier.CONTROL / "retained")
        self.assertEqual({key: row["sha256"] for key, row in before["files"].items()},
                         {key: row["sha256"] for key, row in retained["files"].items()})
        self.assertFalse((self.root / tier.INSTANCE).exists())

    def interrupted_publication(self):
        original = tier._journal_write
        def crash(control, journal, prior):
            if journal["state"] == "installed_disabled":
                raise OSError("fixture final checkpoint interruption")
            return original(control, journal, prior)
        with patch.object(tier, "_journal_write", crash), self.assertRaises(OSError):
            self.install_fixture()

    def test_published_recovery_needs_exact_target_but_not_current_source_archives(self):
        self.interrupted_publication()
        self.application["path"].unlink()
        self.archives[0]["path"].unlink()
        self.write("MO2/new-baseline-file.txt", b"baseline independently changed")
        report = tier.installation_status()
        self.assertEqual(report["recovery_actions"], ["acknowledge_published"])
        self.assertTrue(report["protected_changed_since_install"])
        review = tier.recover_installation("acknowledge_published")
        result = tier.recover_installation("acknowledge_published", apply=True,
            review_token=review["review_token"], process_probe=self.closed)
        self.assertEqual(result["status"], "installed_disabled")

    def test_published_recovery_rejects_extra_files_stale_review_and_changed_bytes(self):
        self.interrupted_publication()
        review = tier.recover_installation("acknowledge_published")
        self.write(tier.INSTANCE + "/unreviewed.ini", b"external")
        self.assertIn("target_drift", self.codes(tier.installation_status()))
        with self.assertRaises(ValueError):
            tier.recover_installation("acknowledge_published", apply=True,
                review_token=review["review_token"], process_probe=self.closed)
        (self.root / tier.INSTANCE / "unreviewed.ini").unlink()
        self.write(tier.INSTANCE + "/dlls/Qt6Core.dll", b"external edit")
        self.assertIn("target_drift", self.codes(tier.installation_status()))

    def test_recovery_review_binds_current_implementation_without_reloading_sources(self):
        self.interrupted_publication()
        review = tier.recover_installation("acknowledge_published")
        original = tier._implementation
        def changed(snapshot):
            result = original(snapshot)
            result["tools/se_lab_skyrimnet.py"] = "e" * 64
            return result
        with patch.object(tier, "_implementation", changed):
            with self.assertRaisesRegex(ValueError, "stale"):
                tier.recover_installation("acknowledge_published", apply=True,
                    review_token=review["review_token"], process_probe=self.closed)
        self.assertEqual(tier.installation_status()["status"], "publishing")

    def test_external_empty_target_cannot_be_replaced_at_publish(self):
        original = tier._exclusive_rename
        def race(source, target):
            target.mkdir()
            return original(source, target)
        with patch.object(tier, "_exclusive_rename", race), self.assertRaises(OSError):
            self.install_fixture()
        self.assertEqual(list((self.root / tier.INSTANCE).iterdir()), [])
        self.assertTrue((self.root / tier.CONTROL / "stage").is_dir())
        self.assertIn("conflicting_target", self.codes(tier.installation_status()))

    def test_source_drift_after_staging_prevents_publish(self):
        original = tier._stage_payload
        def changed(*args):
            original(*args)
            self.application["path"].write_bytes(b"late source replacement")
        with patch.object(tier, "_stage_payload", changed), self.assertRaises(ValueError):
            self.install_fixture()
        self.assertFalse((self.root / tier.INSTANCE).exists())
        self.assertEqual(tier.installation_status()["recovery_actions"], ["retain_partial"])

    def test_kernel_writer_lock_blocks_second_installer(self):
        control = self.root / tier.CONTROL
        control.mkdir()
        plan = tier.installation_plan()
        with tier._writer_lock(control / "writer.lock"):
            with self.assertRaises(ValueError):
                tier.install(plan["review_token"], process_probe=self.closed)
        self.assertFalse((control / "journal.json").exists())

    def test_process_start_during_staging_stops_publication(self):
        calls = []
        def probe():
            calls.append(True)
            return self.closed() if len(calls) < 3 else dict(verified=True, quiescent=False, processes=["modorganizer.exe"])
        plan = tier.installation_plan()
        with self.assertRaisesRegex(ValueError, "closure"):
            tier.install(plan["review_token"], process_probe=probe)
        self.assertFalse((self.root / tier.INSTANCE).exists())
        self.assertEqual(tier.installation_status()["recovery_actions"], ["retain_partial"])

    def test_foreign_and_malformed_journals_cannot_drive_recovery(self):
        self.interrupted_publication()
        path = self.root / tier.CONTROL / "journal.json"
        original = json.loads(path.read_text())
        for key, value in (("tier", "baseline"), ("state", []), ("directories", [".", "../escape"])):
            with self.subTest(key=key):
                changed = {**original, key: value}
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    tier.recover_installation("acknowledge_published")

    def test_real_process_death_after_publish_releases_lock_for_reviewed_recovery(self):
        arguments = dict(root=str(self.root), application={**self.application, "path": str(self.application["path"])},
            archives=[{**row, "path": str(row["path"])} for row in self.archives])
        script = '''
import json, os, sys
from pathlib import Path
from hold_music import se_lab_skyrimnet as tier
args=json.loads(sys.argv[1]); tier.LAB_ROOT=Path(args['root'])
tier.MO2_ARCHIVE=args['application']; tier.MO2_ARCHIVE['path']=Path(tier.MO2_ARCHIVE['path'])
tier.ARCHIVES=args['archives']
for row in tier.ARCHIVES: row['path']=Path(row['path'])
tier.baseline._file_version=lambda path:'1.6.1170.0'
original=tier._exclusive_rename
def crash(source,destination):
 original(source,destination)
 os._exit(42)
tier._exclusive_rename=crash
tier.install(tier.installation_plan()['review_token'],process_probe=lambda:dict(verified=True,quiescent=True,processes=[]))
'''
        child = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", script, json.dumps(arguments)],
                               cwd=tier.REPO, capture_output=True, timeout=60)
        self.assertEqual(child.returncode, 42, child.stderr.decode(errors="replace"))
        status = tier.installation_status()
        self.assertEqual(status["status"], "publishing")
        self.assertEqual(status["recovery_actions"], ["acknowledge_published"])
        review = tier.recover_installation("acknowledge_published")
        self.assertEqual(tier.recover_installation("acknowledge_published", apply=True,
            review_token=review["review_token"], process_probe=self.closed)["status"], "installed_disabled")

    def test_cli_install_and_recovery_require_operation_specific_explicit_tokens(self):
        for args in (["install"], ["plan", "--review-token", "x"], ["recover"],
                     ["recover", "--recovery-action", "retain_partial", "--apply"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cli.main(args)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["install-plan"]), 0)
        report = json.loads(output.getvalue())
        self.assertNotIn("inputs", report)
        self.assertGreater(report["file_count"], 20)
        self.assertFalse((self.root / tier.CONTROL).exists())


if __name__ == "__main__":
    unittest.main()
