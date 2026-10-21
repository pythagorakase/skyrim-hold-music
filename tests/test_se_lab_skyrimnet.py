"""Only synthetic archives and temporary installations; no real lab mutations."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import configparser
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from hold_music import se_lab_skyrimnet as tier
from hold_music.runtime_contract import runtime_identity_key
from tools import se_lab_skyrimnet as cli


class SkyrimNetTierTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "lab"
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        # The target is Windows, including when fake-tree tests run elsewhere.
        patch.dict(os.environ, {"USERNAME": "fixture-user"}).start()
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
        if not extra and game is None:
            seed = tier._instance_seeds(self.root, dict(active_mods=[], enabled_plugins=[]))["ModOrganizer.ini"]
            self.write(tier.INSTANCE + "/ModOrganizer.ini", seed.encode("utf-8"))
            return
        self.write(tier.INSTANCE + "/ModOrganizer.ini", (
            "[General]\ngameName=Skyrim Special Edition\ngame_edition=Steam\nselected_profile=@ByteArray(" + tier.PROFILE
            + ")\ngamePath=@ByteArray(" + (game or self.root / "Game").as_posix() + ")\n" + extra).encode())

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

    def test_preflight_requires_explicit_steam_edition_in_canonical_seed(self):
        self.prepare_fixture()
        relative = tier.INSTANCE + "/ModOrganizer.ini"
        canonical = (self.root / relative).read_bytes()
        self.assertEqual(canonical.count(b"game_edition=Steam\n"), 1)
        for replacement in (b"", b"game_edition=\n", b"game_edition=GOG\n",
                            b"game_edition=Epic Games\n"):
            with self.subTest(replacement=replacement):
                raw = canonical.replace(b"game_edition=Steam\n", replacement)
                self.write(relative, raw)
                report = tier.preflight()
                self.assertEqual(report["status"], "blocked")
                self.assertIn("mo2_ini_seed", self.codes(report))
                self.assertEqual((self.root / relative).read_bytes(), raw)

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
        self.ini(extra="[Settings]\noverwrite_directory=" + (self.root / "MO2/overwrite").as_posix() + "\n")
        self.assertIn("directory_redirect", self.codes(tier.preflight()))
        self.ini(game=self.root.parent / "Steam/Skyrim")
        self.assertIn("mo2_identity", self.codes(tier.preflight()))

    def test_preflight_rejects_single_backslash_qt_paths(self):
        self.prepare_fixture()
        self.ini()
        path = self.root / tier.INSTANCE / "ModOrganizer.ini"
        raw = path.read_text()
        path.write_text(raw.replace((self.root / "Game").as_posix(), str(self.root / "Game").replace("/", "\\")))
        self.assertIn("mo2_ini", self.codes(tier.preflight()))
        self.ini(extra="[Settings]\nmod_directory=" + str(self.root / tier.INSTANCE / "mods").replace("/", "\\") + "\n")
        self.assertIn("mo2_ini", self.codes(tier.preflight()))

    def test_preflight_rejects_even_correct_noncanonical_qt_escaped_backslashes(self):
        self.prepare_fixture()
        if os.name != "nt":
            self.skipTest("Windows path semantics; decoder coverage runs independently on every host")
        path = self.root / tier.INSTANCE / "ModOrganizer.ini"
        raw = path.read_text()
        path.write_text(raw.replace((self.root / "Game").as_posix(), str(self.root / "Game").replace("\\", "\\\\")))
        self.assertIn("mo2_ini_seed", self.codes(tier.preflight()))

    def test_preflight_rejects_explicit_empty_directory_overrides(self):
        self.prepare_fixture()
        for key in ("base_directory", "mod_directory", "profiles_directory", "overwrite_directory", "cache_directory"):
            with self.subTest(key=key):
                self.ini(extra="[Settings]\n" + key + "=\n")
                self.assertIn("directory_redirect", self.codes(tier.preflight()))

    def test_preflight_rejects_qt_section_and_encoded_key_aliases(self):
        self.prepare_fixture()
        for extra in ("[general]\ngamePath=@ByteArray(C:/Steam/Skyrim)\n",
                      "%67amePath=@ByteArray(C:/Steam/Skyrim)\n",
                      "game%50ath=@ByteArray(C:/Steam/Skyrim)\n",
                      "Settings\\mod_directory=C:/Steam/mods\n",
                      "Settings/mod_directory=C:/Steam/mods\n",
                      "[Settings]\nmod%5Fdirectory=C:/Steam/mods\n",
                      "[Settings]\nmod_directory=%BASE_DIR%/mods\n[settings]\nmod_directory=C:/Steam/mods\n",
                      "[DEFAULT]\nmod_directory=C:/Steam/mods\n",
                      "[Unknown]\nkey=value\n"):
            with self.subTest(extra=extra):
                self.ini(extra=extra)
                self.assertIn("mo2_ini_seed", self.codes(tier.preflight()))

    def test_preflight_rejects_noncanonical_mo2_encoding_delimiters_and_formatting(self):
        self.prepare_fixture()
        path = tier.INSTANCE + "/ModOrganizer.ini"
        canonical = (self.root / path).read_bytes()
        for raw in (canonical.decode("utf-8").encode("utf-16"), b"\xef\xbb\xbf" + canonical,
                    canonical.replace(b"\n", b"\r\n"), canonical + b"\n# custom comment\n",
                    canonical.replace(b"gamePath=", b"gamePath:"),
                    canonical.replace(b"gamePath=", b"gamePath =")):
            with self.subTest(raw_sha256=hashlib.sha256(raw).hexdigest()):
                self.write(path, raw)
                before = self.files()
                report = tier.preflight()
                self.assertIn("mo2_ini_seed", self.codes(report))
                self.assertFalse(report["can_launch"])
                self.assertEqual(self.files(), before)

    def test_preflight_rejects_noncanonical_profile_settings_aliases_and_encodings(self):
        self.prepare_fixture()
        path = tier.INSTANCE + "/profiles/" + tier.PROFILE + "/settings.ini"
        canonical = (self.root / path).read_bytes()
        for raw in (canonical + b"[general]\nLocalSaves=false\nLocalSettings=false\n",
                    canonical + b"%4cocalSaves=false\nLocal%53ettings=false\n",
                    canonical.replace(b"LocalSaves=", b"LocalSaves:"),
                    b"[DEFAULT]\nLocalSaves=true\nLocalSettings=true\n[General]\n",
                    canonical + b"[Unknown]\nkey=value\n", canonical + b"# custom comment\n",
                    canonical.decode("utf-8").encode("utf-16"), b"\xef\xbb\xbf" + canonical,
                    canonical.replace(b"\n", b"\r\n")):
            with self.subTest(raw_sha256=hashlib.sha256(raw).hexdigest()):
                self.write(path, raw)
                before = self.files()
                report = tier.preflight()
                self.assertIn("local_profile_seed", self.codes(report))
                self.assertFalse(report["can_launch"])
                self.assertEqual(self.files(), before)

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
                  "uSeRnAmE": "exact fixture user",
                  "OPENROUTER_API_KEY": "secret-a", "AWS_SECRET_ACCESS_KEY": "secret-b",
                  "HTTP_PROXY": "private-proxy", "UNKNOWN_SECRET": "secret-c", "SteamAppId": "611670"}
        clean = tier.clean_launch_environment(source)
        self.assertEqual(clean, {"SystemRoot": r"C:\Windows", "PATH": "fixture-path", "APPDATA": "fixture-appdata",
                                 "USERNAME": "exact fixture user",
                                 "SteamAppId": "489830", "SteamGameId": "489830"})
        self.assertEqual(source["SteamAppId"], "611670")
        self.assertNotIn("USERNAME", source)

    def test_clean_environment_rejects_missing_empty_and_ambiguous_username(self):
        for source in ({}, {"USERNAME": ""}, {"USERNAME": None}, {"USERNAME": "PRIVATE\0VALUE"},
                       {"USERNAME": "PRIVATE_A", "username": "PRIVATE_B"},
                       {"USERNAME": "PRIVATE_A", "UserName": "PRIVATE_A"}):
            with self.subTest(names=sorted(source)), self.assertRaisesRegex(ValueError, "USERNAME") as error:
                tier.clean_launch_environment(source)
            self.assertNotIn("PRIVATE", str(error.exception))

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

    def baseline_capture(self, scenario, recipe, *, before=None):
        number = {"focused_complete": 1, "focused_interrupt": 2, "ambient_entry": 3}[scenario]
        reference = dict(run_id=f"20261021T01000{number}Z-" + str(number) * 12,
                         capture_id=str(number) * 32)
        capture = self.root / "runs" / reference["run_id"] / "captures" / reference["capture_id"]
        run_dir = capture.parent.parent
        old_rows, old_trace = [], []
        before_states = {}
        if before:
            _, _, docs, before_states = tier._capture_documents(self.root, before, tier._Snapshot())
            old_rows, old_trace = docs["receipts"]["performances"], docs["trace"]["entries"]
        old_seq = max((row.get("seq", 0) for row in old_trace), default=0)
        outcome = "interrupted" if scenario == "focused_interrupt" else "completed"
        assertion_names = ("evidence_valid", "slot_selection", "performance_start", "performance_stop",
                           "receipt", "receipt_identity_key", "cleanup_trace_and_receipt")
        result = dict(version=1, run_id=reference["run_id"], started_at_utc="2026-10-21T01:00:00+00:00",
            scenario=scenario, status="passed", expected_outcome=outcome, runtime_engine_observed=True,
            world_id="hold-music-se-lab",
            assertions={name: True for name in assertion_names}, globals_restored=True,
            focused_start_in_flight=False, focused_start_cleanup_pending=False, boolean_serialization_errors=0,
            fixture_ai=dict(requested=True, released=True, acquisition_intent=False, acquisition_in_flight=False),
            vanilla_autostart=dict(requested=True, released=True, intent=False, mutation_in_flight=False, conflict=False),
            world_setup=dict(game_hour_restored=True), receipt_baseline=len(old_rows), receipt_index=len(old_rows),
            selected_slot=1, selected_identity_key=self.fixture_contract["identity_key"], started_real_seconds=10, observed_real_seconds=40,
            trace_baseline=old_seq, controlled_actor_ai=True, timing=dict(fixture_duration_seconds=8))
        if scenario == "ambient_entry":
            result["timing"]["fixture_duration_seconds"] = 0  # The native ambient path never fills the focused cache.
            result["assertions"].update(production_scan=True, eligible_owned_sven=True, real_inn_entry=True)
            result.update(ambient_scheduling_bypassed=False, controller_entry_setup_injected=False)
        rows = old_rows + [dict(slot=1, outcome=outcome, performer_id="Sven", region="Whiterun",
            composition_id="lab:synthetic", save_id="disposable-" + str(number), world_id="hold-music-se-lab",
            started_real_seconds=20, at_hours=18, runtime_identity=dict(self.fixture_contract, version=1,
                                                         performer_id="Sven", mode="Instrumental", voice="None"))]
        new_trace = [dict(seq=old_seq + 1, event="performance_start", detail="id=sven slot=1 duration=8.000000",
                          real_seconds=21)]
        if scenario == "focused_interrupt":
            result["assertions"].update(requested_interruption_guard=True, stop_request_issued=True)
            result["interruption_request_real_seconds"] = 22
            new_trace.append(dict(seq=old_seq + 2, event="performance_interrupt_guard",
                detail="id=Sven slot=1 reason=stop_requested enabled=1", real_seconds=23))
        new_trace.append(dict(seq=old_seq + len(new_trace) + 1, event="performance_stop",
                             detail="outcome=" + outcome + " id=Sven slot=1", real_seconds=25))
        docs = dict(harness=result, receipts=dict(performances=rows), trace=dict(entries=old_trace + new_trace))
        logs = []
        for name, virtual in tier.BASELINE_LOGS.items():
            raw = json.dumps(docs[name]).encode()
            self.write(str((capture / "logs" / (name + ".bin")).relative_to(self.root)), raw)
            logs.append(dict(id=name, source="MO2/overwrite/" + virtual, archived_file="logs/" + name + ".bin",
                after=dict(sha256=hashlib.sha256(raw).hexdigest(), mtime_ns=2), fresh=True,
                content_changed=True, written_after_start=True))
        evidence = dict(version=1, run_id=reference["run_id"], capture_id=reference["capture_id"],
                        fresh_required_evidence=True, logs=logs)
        run = dict(version=1, run_id=reference["run_id"], request_published=True,
            scenario=scenario.replace("_", "-"), started_ns=1, started_at_utc=result["started_at_utc"],
            review_token="baseline-proof", logs=[dict(id=k, before=v) for k, v in before_states.items()])
        original = [dict(path=row["source"]["path"], sha256=row["sha256"]) for row in recipe["files"]
                    if "path" in row["source"]]
        prior = dict(operation="se_lab_preflight", status="ready_for_explicit_launch", profile=tier.baseline.PROFILE,
                     review_token=run["review_token"], snapshot=dict(files=original))
        for path, document in ((capture / "evidence.json", evidence), (run_dir / "run.json", run),
                               (run_dir / "preflight.json", prior)):
            self.write(str(path.relative_to(self.root)), json.dumps(document).encode())
        return reference

    def runtime_fixture(self):
        self.fixture_contract = dict(performer_id="sven", region="whiterun", mode="instrumental", voice="none",
            recipe_id="lab/synthetic", recipe_revision="lab-v1", model_id="deterministic-pcm-fixture",
            instrument_family="plucked_string", instrument_name="synthetic plucked-string test signal", arrangement="solo_lute")
        self.fixture_contract["identity_key"] = runtime_identity_key(self.fixture_contract)
        recording = dict(self.fixture_contract, slot=1, duration_seconds=8, composition_id="lab:synthetic",
                         provenance=dict(kind="synthetic_test_fixture"))
        manifest = dict(recordings=[recording], runtime_selection=dict(version=1, contracts=[self.fixture_contract]))
        source = "MO2/mods/Hold Music Lab Data/SKSE/Plugins/StorageUtilData/HoldMusic/library.json"
        self.write(source, json.dumps(manifest).encode())
        self.manifest["files"].append(dict(path=source, sha256=self.sha(source)))
        self.save_manifest()
        self.install_fixture()
        recipe = tier.preflight()
        complete = self.baseline_capture("focused_complete", recipe)
        interrupt = self.baseline_capture("focused_interrupt", recipe, before=complete)
        ambient = self.baseline_capture("ambient_entry", recipe, before=interrupt)
        return dict(focused_complete=dict(capture=complete), focused_interrupt=dict(capture=interrupt, before=complete),
                    ambient_entry=dict(capture=ambient, before=interrupt))

    def change_capture(self, reference, name, change):
        _, directory = tier._capture_reference(self.root, reference)
        path = directory / "logs" / (name + ".bin")
        document = json.loads(path.read_bytes())
        change(document)
        raw = json.dumps(document).encode()
        path.write_bytes(raw)
        evidence_path = directory / "evidence.json"
        evidence = json.loads(evidence_path.read_bytes())
        next(row for row in evidence["logs"] if row["id"] == name)["after"]["sha256"] = hashlib.sha256(raw).hexdigest()
        evidence_path.write_text(json.dumps(evidence))

    def process_rows(self):
        run = json.loads((self.root / tier.RUNTIME_CONTROL / "run.json").read_bytes())
        ticks = run["started_ns"] // 100 + 621355968000000000 + 1
        return [dict(pid=100, parent_pid=77, path=str(self.root / tier.INSTANCE / "ModOrganizer.exe"), created_ticks=ticks),
                dict(pid=101, parent_pid=100, path=str(self.root / "Game/skse64_loader.exe"), created_ticks=ticks + 1),
                dict(pid=102, parent_pid=101, path=str(self.root / "Game/SkyrimSE.exe"), created_ticks=ticks + 2)]

    def fake_observer(self, spawn, *, rows=None):
        get_rows = rows or self.process_rows
        class Observer:
            def __init__(self, **options): pass
            def start(self): return []
            def capture(self):
                current = get_rows() if spawn.called else []
                return dict(history=current, current=current, samples=1, max_sample_gap_seconds=0)
            def stop(self): return True
        return Observer

    def fake_launch(self, references, *, popen=None):
        plan = tier.launch_plan(references)
        with patch.object(tier.baseline, "_require_windows"), \
                patch.object(tier.subprocess, "Popen", side_effect=popen or (lambda *a, **k: SimpleNamespace(pid=100))) as spawn, \
                patch.object(tier, "_ProcessObserver", self.fake_observer(spawn)):
            return tier.launch(references, plan["review_token"], process_probe=self.closed)

    def test_launch_review_binds_all_baselines_without_writes_or_processes(self):
        references = self.runtime_fixture()
        before = self.files()
        with patch.object(tier.subprocess, "Popen", side_effect=AssertionError("review spawned")):
            report = tier.launch_plan(references)
        self.assertTrue(report["can_launch"])
        self.assertFalse(report["runtime_verified"])
        self.assertEqual(before, self.files())
        self.assertEqual(report["review_token"], tier.launch_plan(references)["review_token"])

    def test_failed_interrupt_cannot_authorize_first_boot(self):
        references = self.runtime_fixture()
        self.change_capture(references["focused_interrupt"]["capture"], "harness", lambda row: row.update(status="failed"))
        with self.assertRaisesRegex(ValueError, "accepted scenario"):
            tier.launch_plan(references)
        self.assertFalse((self.root / tier.RUNTIME_CONTROL).exists())

    def test_baseline_nonempty_history_requires_exact_preserved_before_capture(self):
        references = self.runtime_fixture()
        incomplete = json.loads(json.dumps(references))
        incomplete["focused_interrupt"].pop("before")
        with self.assertRaisesRegex(ValueError, "before capture"):
            tier.launch_plan(incomplete)
        self.change_capture(references["focused_interrupt"]["capture"], "receipts",
            lambda row: row["performances"][0].update(outcome="lost-original"))
        with self.assertRaisesRegex(ValueError, "history changed"):
            tier.launch_plan(references)

    def test_baseline_wrong_identity_cleanup_and_late_interrupt_fail_closed(self):
        references = self.runtime_fixture()
        selected = references["focused_interrupt"]["capture"]
        _, directory = tier._capture_reference(self.root, selected)
        original = {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
        cases = (("harness", lambda r: r.update(selected_identity_key="b" * 64)),
                 ("harness", lambda r: r["fixture_ai"].update(acquisition_in_flight=True)),
                 ("harness", lambda r: r.update(interruption_request_real_seconds=28)),
                 ("harness", lambda r: r.update(world_setup=None)),
                 ("receipts", lambda r: r["performances"][-1].update(runtime_identity=None)),
                 ("receipts", lambda r: r["performances"][-1].update(runtime_identity=dict(identity_key=self.fixture_contract["identity_key"]))),
                 ("receipts", lambda r: r["performances"][-1]["runtime_identity"].update(instrument_name="different")),
                 ("trace", lambda r: r["entries"][-1].update(detail="outcome=interrupted id=Sven slot=10")))
        for name, change in cases:
            with self.subTest(name=name, change=change):
                for path, raw in original.items(): path.write_bytes(raw)
                self.change_capture(selected, name, change)
                with self.assertRaises(ValueError): tier.launch_plan(references)

    def test_admission_protocol_requires_fully_restored_ticket_and_no_pending_work(self):
        references = self.runtime_fixture()
        selected = references["ambient_entry"]["capture"]
        admission = dict(ticket=0, baselines_ready=True, resumed=True, drained_observed=True,
            acquire_in_flight=False, resume_in_flight=False, fault=False, cleanup_pending=False,
            initial_drain_pending=False, begin_in_flight=False, baseline_work_in_flight=False,
            transition_in_flight=False, pending_finish_reason="")
        self.change_capture(selected, "harness", lambda row: row.update(admission=admission))
        tier.launch_plan(references)
        self.change_capture(selected, "harness", lambda row: row.update(admission=dict(admission,
            fixture_transition_in_flight=False, fixture_movement_unresolved=False)))
        tier.launch_plan(references)
        for key, value in (("ticket", 1), ("resumed", False), ("drained_observed", False),
                           ("cleanup_pending", True), ("fault", True), ("resume_in_flight", True)):
            with self.subTest(key=key):
                self.change_capture(selected, "harness", lambda row: row.update(admission=dict(admission, **{key: value})))
                with self.assertRaisesRegex(ValueError, "admission"): tier.launch_plan(references)
        for key in ("fixture_transition_in_flight", "fixture_movement_unresolved"):
            for value in (True, 0, None, "false"):
                with self.subTest(key=key, value=value):
                    self.change_capture(selected, "harness", lambda row: row.update(admission=dict(admission, **{key: value})))
                    with self.assertRaisesRegex(ValueError, "admission"): tier.launch_plan(references)

    def test_ambient_baseline_is_required_and_cannot_bypass_production_entry(self):
        references = self.runtime_fixture()
        missing = dict(references); missing.pop("ambient_entry")
        with self.assertRaisesRegex(ValueError, "ambient-entry"): tier.launch_plan(missing)
        self.change_capture(references["ambient_entry"]["capture"], "harness",
                            lambda row: row.update(ambient_scheduling_bypassed=True))
        with self.assertRaisesRegex(ValueError, "production entry"): tier.launch_plan(references)

    def test_ambient_duration_uses_exact_production_start_and_pinned_source(self):
        references = self.runtime_fixture()
        self.assertTrue(tier.launch_plan(references)["can_launch"])
        reference = references["ambient_entry"]["capture"]
        for detail in ("id=sven slot=1 ", "id=sven slot=1 duration=", "id=sven slot=1 duration=NaN",
                       "id=sven slot=1 duration=9.000000", "id=sven slot=1 duration=-8", "id=sven slot=1 duration=8 extra"):
            with self.subTest(detail=detail):
                def change(document):
                    next(row for row in reversed(document["entries"]) if row["event"] == "performance_start")["detail"] = detail
                self.change_capture(reference, "trace", change)
                with self.assertRaisesRegex(ValueError, "Ambient production duration"):
                    tier.launch_plan(references)

    def test_focused_duration_cache_and_actual_request_window_remain_required(self):
        references = self.runtime_fixture()
        reference = references["focused_interrupt"]["capture"]
        for duration in (None, 0, 9, "8", float("nan")):
            with self.subTest(duration=duration):
                self.change_capture(reference, "harness", lambda row: row.update(timing=dict(fixture_duration_seconds=duration)))
                with self.assertRaisesRegex(ValueError, "Baseline duration|not valid JSON"):
                    tier.launch_plan(references)
        self.change_capture(reference, "harness", lambda row: row.update(timing=dict(fixture_duration_seconds=8),
                                                                        interruption_request_real_seconds=28))
        with self.assertRaisesRegex(ValueError, "timely request"): tier.launch_plan(references)

    def test_capture_path_and_body_cannot_select_external_reads(self):
        references = self.runtime_fixture()
        references["focused_complete"]["capture"]["run_id"] = "../private"
        with self.assertRaisesRegex(ValueError, "reference"):
            tier.launch_plan(references)

    def test_launch_rejects_stale_or_cross_operation_token_before_spawn(self):
        references = self.runtime_fixture()
        plan = tier.launch_plan(references)
        self.change_capture(references["focused_complete"]["capture"], "harness", lambda r: r.update(review_note="changed"))
        with patch.object(tier.baseline, "_require_windows"), patch.object(tier.subprocess, "Popen") as spawn:
            for token in ("skyrimnet-install-v1:other", plan["review_token"]):
                with self.assertRaises(ValueError): tier.launch(references, token, process_probe=self.closed)
            spawn.assert_not_called()
        self.assertFalse((self.root / tier.RUNTIME_CONTROL).exists())

    def test_launch_clean_environment_exact_command_and_original_trees_preserved(self):
        references = self.runtime_fixture()
        original = tier._protected(self.root)
        calls = []
        def spawn(command, **options):
            calls.append((command, options))
            return SimpleNamespace(pid=100)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "NEVER_COPY", "HTTP_PROXY": "NEVER_COPY",
                                    "USERNAME": "PRIVATE_USERNAME_SENTINEL"}):
            result = self.fake_launch(references, popen=spawn)
        self.assertEqual(result["status"], "launched_attributed")
        self.assertEqual(calls[0][0], tier._runtime_command(self.root))
        self.assertEqual(calls[0][1]["cwd"], str(self.root / tier.INSTANCE))
        self.assertFalse(calls[0][1]["shell"])
        self.assertNotIn("NEVER_COPY", json.dumps(calls[0][1]["env"]))
        self.assertEqual(calls[0][1]["env"]["USERNAME"], "PRIVATE_USERNAME_SENTINEL")
        self.assertNotIn("PRIVATE_USERNAME_SENTINEL", json.dumps(result))
        for name in ("run.json", "launch-result.json"):
            self.assertNotIn("PRIVATE_USERNAME_SENTINEL", (self.root / tier.RUNTIME_CONTROL / name).read_text())
        self.assertEqual(original, tier._protected(self.root))
        self.assertFalse(result["native_verified"])
        with self.assertRaisesRegex(ValueError, "attempt already"):
            tier.launch_plan(references)

    def test_launch_rejects_missing_empty_or_changed_username_before_attempt(self):
        references = self.runtime_fixture()
        plan = tier.launch_plan(references)
        source = dict(os.environ)
        source.pop("USERNAME", None)
        for username in (None, "", "PRIVATE_CHANGED_USERNAME"):
            environment = dict(source)
            if username is not None: environment["USERNAME"] = username
            with self.subTest(username_present=username is not None), patch.dict(os.environ, environment, clear=True), \
                    patch.object(tier.baseline, "_require_windows"), patch.object(tier.subprocess, "Popen") as spawn:
                with self.assertRaises(ValueError) as error:
                    tier.launch(references, plan["review_token"], process_probe=self.closed)
                spawn.assert_not_called()
                self.assertNotIn("PRIVATE_CHANGED_USERNAME", str(error.exception))
                self.assertFalse((self.root / tier.RUNTIME_CONTROL).exists())

    def test_process_lineage_refuses_missing_loader_foreign_parent_old_and_reused_pid(self):
        references = self.runtime_fixture()
        self.fake_launch(references)
        run = json.loads((self.root / tier.RUNTIME_CONTROL / "run.json").read_bytes())
        original = self.process_rows()
        for mutation in (lambda rows: rows[1].update(parent_pid=900),
                         lambda rows: rows[2].update(parent_pid=100)):
            rows = json.loads(json.dumps(original)); mutation(rows)
            self.assertIsNone(tier._process_history(rows, [], self.root, run["started_ns"], 100)[1])
        for mutation in (lambda rows: rows[0].update(path=str(self.root / "MO2/ModOrganizer.exe")),
                         lambda rows: rows[0].update(created_ticks=1),
                         lambda rows: rows.append(dict(rows[0]))):
            rows = json.loads(json.dumps(original)); mutation(rows)
            with self.assertRaises(ValueError): tier._process_history(rows, [], self.root, run["started_ns"], 100)
        replaced = json.loads(json.dumps(original)); replaced[2]["created_ticks"] += 1
        with self.assertRaisesRegex(ValueError, "reused"):
            tier._process_history(replaced, original, self.root, run["started_ns"], 100)
        with self.assertRaises(ValueError): tier._process_history([], [{}], self.root, run["started_ns"], 100)

    def test_uncertain_spawn_is_retained_and_never_retried(self):
        references = self.runtime_fixture()
        def uncertain(*args, **kwargs): raise OSError("PRIVATE_SPAWN_SENTINEL")
        result = self.fake_launch(references, popen=uncertain)
        self.assertEqual(result["status"], "launch_failed_or_unknown")
        self.assertNotIn("PRIVATE_SPAWN_SENTINEL", json.dumps(result))
        with self.assertRaises(ValueError): tier.launch_plan(references)

    def test_change_after_intent_preserves_attempt_without_spawning(self):
        references = self.runtime_fixture()
        token = tier.launch_plan(references)["review_token"]
        original = tier._runtime_json
        def intent(path, value, **options):
            result = original(path, value, **options)
            if path.name == "launch-result.json":
                self.write("Game/late-change", b"foreign")
            return result
        with patch.object(tier.baseline, "_require_windows"), patch.object(tier, "_runtime_json", side_effect=intent), \
                patch.object(tier.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                tier.launch(references, token, process_probe=self.closed)
            spawn.assert_not_called()
        self.assertTrue((self.root / tier.RUNTIME_CONTROL / "run.json").is_file())
        self.assertEqual((self.root / "Game/late-change").read_bytes(), b"foreign")

    def test_missing_short_lived_loader_times_out_without_claim_or_retry(self):
        references = self.runtime_fixture()
        token = tier.launch_plan(references)["review_token"]
        def rows(): return [row for row in self.process_rows() if row["pid"] != 101]
        with patch.object(tier.baseline, "_require_windows"), \
                patch.object(tier.subprocess, "Popen", return_value=SimpleNamespace(pid=100)) as spawn, \
                patch.object(tier, "_ProcessObserver", self.fake_observer(spawn, rows=rows)), \
                patch.object(tier.time, "monotonic", side_effect=[0, 2]):
            result = tier.launch(references, token, timeout_seconds=1, process_probe=self.closed)
        self.assertEqual(result["status"], "launched_unattributed")
        self.assertFalse(result["launch_attributed"])
        self.assertFalse(result["processes_terminated"])
        self.assertEqual(spawn.call_count, 1)

    def test_prearmed_foreign_history_refuses_dispatch_even_after_process_exits(self):
        references = self.runtime_fixture()
        token = tier.launch_plan(references)["review_token"]
        test = self
        class Observer:
            def __init__(self, **options): pass
            def start(self): return []
            def capture(self): return dict(history=test.process_rows()[:1], current=[], samples=2, max_sample_gap_seconds=0)
            def stop(self): return True
        with patch.object(tier.baseline, "_require_windows"), patch.object(tier, "_ProcessObserver", Observer), \
                patch.object(tier.subprocess, "Popen") as spawn:
            result = tier.launch(references, token, process_probe=self.closed)
        spawn.assert_not_called()
        self.assertFalse(result["launch_attributed"])
        self.assertFalse(result["process_started"])

    def test_worker_failure_at_join_cannot_leave_positive_launch_claim(self):
        references = self.runtime_fixture()
        token = tier.launch_plan(references)["review_token"]
        with patch.object(tier.baseline, "_require_windows"), \
                patch.object(tier.subprocess, "Popen", return_value=SimpleNamespace(pid=100)) as spawn:
            base = self.fake_observer(spawn)
            class Observer(base):
                failed = False
                def capture(self):
                    if self.failed: raise ValueError("incomplete")
                    return super().capture()
                def stop(self): self.failed = True; return True
            with patch.object(tier, "_ProcessObserver", Observer):
                result = tier.launch(references, token, process_probe=self.closed)
        self.assertEqual(result["status"], "launch_observation_incomplete")
        self.assertEqual(result["process_observer"], "native-filetime-v1")
        self.assertTrue(result["process_started"])
        self.assertFalse(result["launch_attributed"])
        self.assertIsNone(result["game"])
        self.assertFalse(result["processes_terminated"])

    def assert_final_frame_invalidates_launch(self, mutation):
        references = self.runtime_fixture()
        token = tier.launch_plan(references)["review_token"]
        with patch.object(tier.baseline, "_require_windows"), \
                patch.object(tier.subprocess, "Popen", return_value=SimpleNamespace(pid=100)) as spawn:
            base = self.fake_observer(spawn)
            class Observer(base):
                joined = False
                def capture(self):
                    observed = super().capture()
                    if self.joined: mutation(observed)
                    return observed
                def stop(self): self.joined = True; return True
            with patch.object(tier, "_ProcessObserver", Observer):
                result = tier.launch(references, token, process_probe=self.closed)
        self.assertEqual(result["status"], "launch_observation_incomplete")
        self.assertTrue(result["process_started"])
        self.assertFalse(result["launch_attributed"])
        self.assertIsNone(result["game"])
        self.assertFalse(result["processes_terminated"])

    def test_game_exit_in_final_joined_frame_invalidates_launch(self):
        self.assert_final_frame_invalidates_launch(lambda frame: frame.update(
            current=[row for row in frame["current"] if row["pid"] != 102]))

    def test_foreign_process_in_final_joined_frame_invalidates_launch(self):
        def foreign(frame):
            row = dict(frame["current"][-1], pid=777, parent_pid=666,
                       path=str(self.root / "other/SkyrimSE.exe"))
            frame["current"] = frame["current"] + [row]
            frame["history"] = frame["history"] + [row]
        self.assert_final_frame_invalidates_launch(foreign)

    def test_runtime_writer_lock_and_foreign_result_change_are_preserved(self):
        references = self.runtime_fixture()
        token = tier.launch_plan(references)["review_token"]
        with patch.object(tier.baseline, "_require_windows"), tier._writer_lock(self.root / ".se-lab-writer.lock"), \
                patch.object(tier.subprocess, "Popen") as spawn:
            with self.assertRaises(ValueError): tier.launch(references, token, process_probe=self.closed)
            spawn.assert_not_called()
        foreign = b'{"foreign":"preserve"}'
        def replace_result(*args, **kwargs):
            (self.root / tier.RUNTIME_CONTROL / "launch-result.json").write_bytes(foreign)
            return SimpleNamespace(pid=100)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.fake_launch(references, popen=replace_result)
        self.assertEqual((self.root / tier.RUNTIME_CONTROL / "launch-result.json").read_bytes(), foreign)

    def test_process_guard_and_invalid_timeout_refuse_before_attempt(self):
        references = self.runtime_fixture()
        token = tier.launch_plan(references)["review_token"]
        with patch.object(tier.baseline, "_require_windows"), patch.object(tier.subprocess, "Popen") as spawn:
            for timeout in (0, 61, float("nan"), float("inf"), True):
                with self.assertRaises(ValueError): tier.launch(references, token, timeout_seconds=timeout, process_probe=self.closed)
            with self.assertRaises(ValueError): tier.launch(references, token, process_probe=lambda: dict(verified=False))
            spawn.assert_not_called()
        self.assertFalse((self.root / tier.RUNTIME_CONTROL).exists())

    def test_collector_handles_firstboot_changes_without_exporting_private_content(self):
        references = self.runtime_fixture()
        result = self.fake_launch(references)
        self.write(tier.INSTANCE + "/overwrite/" + tier.CONFIG + "Auth.yaml", b"COLLECTOR_SECRET_SENTINEL")
        self.write(tier.INSTANCE + "/overwrite/private.db", b"DATABASE_SECRET_SENTINEL")
        with patch.object(tier, "_runtime_process_snapshot", side_effect=self.process_rows), \
                patch.object(tier, "preflight", side_effect=AssertionError("firstboot contract reused")), \
                patch.object(tier.subprocess, "run", side_effect=AssertionError("unexpected child/network")):
            report = tier.collect(result["run_id"])
        self.assertEqual(report["status"], "local_evidence_collected")
        self.assertEqual(report["private_runtime_file_count"], 2)
        self.assertEqual(report["changed_file_count"], 2)
        self.assertFalse(report["native_verified"])
        self.assertFalse(report["effective_config_verified"])
        self.assertFalse(report["network_requests_performed"])
        self.assertNotIn("SECRET_SENTINEL", json.dumps(report))
        self.assertTrue(report["protected_paths_unchanged"])

    def test_collector_rejects_process_reuse_and_reports_protected_drift(self):
        references = self.runtime_fixture()
        result = self.fake_launch(references)
        rows = self.process_rows(); rows[-1]["created_ticks"] += 1
        with patch.object(tier, "_runtime_process_snapshot", return_value=rows), self.assertRaises(ValueError):
            tier.collect(result["run_id"])
        self.write("Game/new-foreign-file", b"changed")
        with patch.object(tier, "_runtime_process_snapshot", side_effect=self.process_rows):
            report = tier.collect(result["run_id"])
        self.assertEqual(report["status"], "protected_state_changed")

    def test_collector_rejects_changed_inventory_before_capture(self):
        references = self.runtime_fixture()
        result = self.fake_launch(references)
        observations = 0
        def changed():
            nonlocal observations
            observations += 1
            if observations == 2:
                self.write(tier.INSTANCE + "/overwrite/new-runtime-file", b"changed during capture")
            return self.process_rows()
        with patch.object(tier, "_runtime_process_snapshot", side_effect=changed), self.assertRaisesRegex(ValueError, "changed"):
            tier.collect(result["run_id"])
        self.assertFalse((self.root / tier.RUNTIME_CONTROL / "captures").exists())

    def test_runtime_cli_requires_separate_arguments_and_sanitizes_errors(self):
        for args in (["launch"], ["launch-plan"], ["collect"], ["collect", "--run-id", "x", "--show-files"],
                     ["plan", "--timeout-seconds", "4"], ["launch-plan", "--baseline-evidence", "x", "--apply"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): cli.main(args)
        error = io.StringIO()
        with patch.object(tier, "collect", side_effect=ValueError("PRIVATE_ERROR_SENTINEL")), redirect_stderr(error):
            self.assertEqual(cli.main(["collect", "--run-id", "20261021T010001Z-" + "1" * 12]), 1)
        self.assertNotIn("PRIVATE_ERROR_SENTINEL", error.getvalue())


class QtIniEncodingTests(unittest.TestCase):
    def test_safe_literal_subset_matches_windows_path_and_byte_array_forms(self):
        for encoded in ("C:/MGO/HoldMusic-SE-Lab/Game", "@ByteArray(C:/MGO/HoldMusic-SE-Lab/Game)",
                        r"C:\\MGO\\HoldMusic-SE-Lab\\Game", r"@ByteArray(C:\\MGO\\HoldMusic-SE-Lab\\Game)"):
            with self.subTest(encoded=encoded):
                self.assertEqual(tier._qt_ini_string(encoded).replace("\\", "/"), "C:/MGO/HoldMusic-SE-Lab/Game")
        self.assertEqual(tier._qt_ini_string("@ByteArray(" + tier.PROFILE + ")"), tier.PROFILE)

    def test_ambiguous_qt_syntax_is_rejected_instead_of_differently_decoded(self):
        for encoded in (r"C:\MGO\HoldMusic-SE-Lab\Game", r"@ByteArray(C:\MGO\HoldMusic-SE-Lab\Game)",
                        "C:/Game\\", r"C:\\MGO\Game", r"C:/Game\n", r"C:/Game\x20", '"C:/Game"',
                        "C:/Game,other", "C:/Game;comment", "@Variant(private)", "@ByteArray(unclosed", "bad\npath"):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError): tier._qt_ini_string(encoded)

    def test_generator_uses_forward_slashes_for_every_qt_path(self):
        root = Path(tempfile.gettempdir()).resolve() / "path fixture"
        seed = tier._instance_seeds(root, dict(active_mods=[], enabled_plugins=[]))["ModOrganizer.ini"]
        parsed = configparser.ConfigParser(interpolation=None); parsed.read_string(seed)
        self.assertEqual(tier._qt_ini_string(parsed.get("General", "gamePath")), (root / "Game").as_posix())
        self.assertEqual(parsed.get("General", "game_edition"), "Steam")
        self.assertEqual(set(parsed["General"]), {"gamename", "game_edition", "selected_profile", "gamepath"})
        self.assertNotIn("\\", seed)
        for key, value in parsed.items("Settings"):
            self.assertTrue(Path(tier._qt_ini_string(value)).is_relative_to(root / tier.INSTANCE), key)

    @unittest.skipUnless(os.name == "nt" and os.environ.get("HOLD_MUSIC_TEST_QT_ROOT"),
                         "Set HOLD_MUSIC_TEST_QT_ROOT to the pinned MO2 Qt6.7.1 distribution for native parser proof")
    def test_real_qt_reads_generated_paths_and_exposes_old_single_backslash_bug(self):
        root = Path(tempfile.gettempdir()).resolve() / "qt path fixture"
        corrected = tier._instance_seeds(root, dict(active_mods=[], enabled_plugins=[]))["ModOrganizer.ini"]
        old = corrected.replace(root.as_posix(), str(root)).replace("/", "\\")
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            alias = corrected + "\n[general]\ngamePath=@ByteArray(C:/Steam/Skyrim)\n"
            for name, text in (("old.ini", old), ("corrected.ini", corrected), ("alias.ini", alias)):
                path = Path(temporary) / name; path.write_text(text, encoding="utf-8"); paths.append(path)
            original = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
            script = r'''
import hashlib,json,os,sys
from pathlib import Path
root=Path(sys.argv[1]); handles=[os.add_dll_directory(str(root/'dlls')),os.add_dll_directory(str(root))]
sys.path.insert(0,str(root/'plugins/plugin_python/libs'))
from PyQt6.QtCore import QSettings,QByteArray,qVersion
rows=[]
for name in sys.argv[2:]:
 settings=QSettings(name,QSettings.Format.IniFormat)
 keys=['gamePath','game_edition','Settings/base_directory','Settings/mod_directory','Settings/profiles_directory',
       'Settings/overwrite_directory','Settings/download_directory','Settings/cache_directory']
 values={}
 for key in keys:
  value=settings.value(key);values[key]=bytes(value).decode('utf-8') if isinstance(value,QByteArray) else value
 rows.append(dict(values=values,status=settings.status().name));del settings
print(json.dumps(dict(version=qVersion(),rows=rows)))
'''
            result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", script,
                os.environ["HOLD_MUSIC_TEST_QT_ROOT"], *map(str, paths)], check=True, capture_output=True,
                text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            report = json.loads(result.stdout)
            self.assertEqual(report["version"], "6.7.1")
            self.assertEqual([row["status"] for row in report["rows"]], ["NoError", "NoError", "NoError"])
            self.assertNotEqual(report["rows"][0]["values"]["gamePath"], str(root / "Game"))
            parsed = configparser.ConfigParser(interpolation=None);parsed.read_string(corrected)
            self.assertEqual(report["rows"][1]["values"], {"gamePath": (root / "Game").as_posix(), "game_edition": "Steam",
                **{"Settings/" + key: value for key, value in parsed.items("Settings")}})
            self.assertEqual(report["rows"][2]["values"]["gamePath"], "C:/Steam/Skyrim")
            self.assertEqual(original, {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})

    @unittest.skipUnless(os.name == "nt" and os.environ.get("HOLD_MUSIC_TEST_QT_ROOT"),
                         "Set HOLD_MUSIC_TEST_QT_ROOT to the pinned MO2 Qt6.7.1 distribution for native parser proof")
    def test_real_qt_profile_aliases_and_encodings_require_canonical_bytes(self):
        root = Path(tempfile.gettempdir()).resolve()
        canonical = tier._instance_seeds(root, dict(active_mods=[], enabled_plugins=[]))[
            "profiles/" + tier.PROFILE + "/settings.ini"]
        cases = [canonical.encode("utf-8"),
                 (canonical + "[general]\nLocalSaves=false\nLocalSettings=false\n").encode("utf-8"),
                 (canonical + "%4cocalSaves=false\nLocal%53ettings=false\n").encode("utf-8"),
                 canonical.replace("=", ":").encode("utf-8"), canonical.encode("utf-16")]
        with tempfile.TemporaryDirectory() as temporary:
            paths = [Path(temporary) / (str(index) + ".ini") for index in range(len(cases))]
            for path, raw in zip(paths, cases): path.write_bytes(raw)
            script = r'''
import json,os,sys
from pathlib import Path
root=Path(sys.argv[1]); handles=[os.add_dll_directory(str(root/'dlls')),os.add_dll_directory(str(root))]
sys.path.insert(0,str(root/'plugins/plugin_python/libs'))
from PyQt6.QtCore import QSettings,qVersion
rows=[]
for name in sys.argv[2:]:
 settings=QSettings(name,QSettings.Format.IniFormat)
 rows.append(dict(local_saves=settings.value('LocalSaves',type=bool),
                  local_settings=settings.value('LocalSettings',type=bool),
                  present=[settings.contains(key) for key in ['LocalSaves','LocalSettings']],
                  status=settings.status().name));del settings
print(json.dumps(dict(version=qVersion(),rows=rows)))
'''
            result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", script,
                os.environ["HOLD_MUSIC_TEST_QT_ROOT"], *map(str, paths)], check=True, capture_output=True,
                text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            report = json.loads(result.stdout)
            self.assertEqual(report["version"], "6.7.1")
            self.assertEqual(report["rows"][0], dict(local_saves=True, local_settings=True,
                present=[True, True], status="NoError"))
            for row in report["rows"][1:3]:
                self.assertEqual(row, dict(local_saves=False, local_settings=False,
                    present=[True, True], status="NoError"))
            for row in report["rows"][3:]:
                self.assertEqual(row["present"], [False, False])
                self.assertEqual(row["status"], "FormatError")
            self.assertEqual([path.read_bytes() for path in paths], cases)


class NativeProcessObserverTests(unittest.TestCase):
    def wait_for(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(0.005)
        self.fail("Bounded observer condition was not observed")

    def rows(self, root):
        tick = tier.UNIX_TO_DOTNET_TICKS + 1
        return [dict(pid=100, parent_pid=77, path=str(root / tier.INSTANCE / "ModOrganizer.exe"), created_ticks=tick),
                dict(pid=101, parent_pid=100, path=str(root / "Game/skse64_loader.exe"), created_ticks=tick + 1),
                dict(pid=102, parent_pid=101, path=str(root / "Game/SkyrimSE.exe"), created_ticks=tick + 2)]

    def test_prearmed_sampler_retains_transient_loader_and_exact_ticks(self):
        root = Path(tempfile.gettempdir()).resolve() / "synthetic-observer"
        rows, frame = self.rows(root), []
        observer = tier._ProcessObserver(timeout_seconds=3, snapshot=lambda: list(frame), interval=0.001)
        self.addCleanup(observer.stop)
        self.assertEqual(observer.start(), [])
        frame[:] = rows[:2]
        self.wait_for(lambda: len(observer.capture()["history"]) == 2)
        frame[:] = [rows[0], rows[2]]
        self.wait_for(lambda: len(observer.capture()["history"]) == 3)
        observed = observer.capture()
        history, game = tier._process_history(observed["current"], observed["history"], root, 100, 100)
        self.assertEqual(history, rows)
        self.assertEqual(game, rows[2])
        self.assertGreaterEqual(observed["samples"], 3)
        self.assertTrue(observer.stop())
        self.assertFalse(observer.thread.is_alive())

    def test_initial_nonempty_frame_is_reported_before_dispatch(self):
        rows = self.rows(Path(tempfile.gettempdir()).resolve())
        observer = tier._ProcessObserver(timeout_seconds=2, snapshot=lambda: rows, interval=0.001)
        self.addCleanup(observer.stop)
        self.assertEqual(observer.start(), rows)

    def test_native_failure_and_malformed_first_frame_fail_closed_without_exception_body(self):
        def broken(): raise OSError("PRIVATE_NATIVE_SENTINEL")
        for snapshot in (broken, lambda: {}, lambda: [{}]):
            with self.subTest(snapshot=snapshot):
                observer = tier._ProcessObserver(timeout_seconds=2, snapshot=snapshot)
                try:
                    with self.assertRaisesRegex(ValueError, "incomplete") as error: observer.start()
                    self.assertNotIn("PRIVATE_NATIVE_SENTINEL", str(error.exception))
                finally: self.assertTrue(observer.stop())

    def test_reused_duplicate_and_overflowing_late_identities_fail_closed(self):
        root = Path(tempfile.gettempdir()).resolve()
        rows = self.rows(root)
        for later, maximum in (([dict(rows[0], created_ticks=rows[0]["created_ticks"] + 1)], 128),
                               ([rows[0], rows[0]], 128), (rows[:2], 1)):
            with self.subTest(later=later, maximum=maximum):
                frame = rows[:1]
                observer = tier._ProcessObserver(timeout_seconds=2, snapshot=lambda: list(frame), interval=0.001,
                                                 max_identities=maximum)
                try:
                    observer.start()
                    frame[:] = later
                    self.wait_for(lambda: observer.failed)
                    with self.assertRaisesRegex(ValueError, "incomplete"): observer.capture()
                finally: self.assertTrue(observer.stop())

    def test_observer_deadline_expires_without_unbounded_polling(self):
        observer = tier._ProcessObserver(timeout_seconds=0.05, snapshot=lambda: [], interval=0.001)
        try:
            observer.start()
            self.wait_for(lambda: observer.expired)
            with self.assertRaisesRegex(ValueError, "incomplete"): observer.capture()
        finally: self.assertTrue(observer.stop())

    @unittest.skipUnless(os.name == "nt", "Native Windows process identity check")
    def test_harmless_native_python_child_is_retained_after_exit_with_exact_filetime(self):
        # No game, Steam, private config, network, file output or provider is involved.
        with patch.object(tier, "PROCESS_NAMES", {Path(sys.executable).name.lower()}):
            observer = tier._ProcessObserver(timeout_seconds=4, interval=0.01)
            try:
                observer.start()
                child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(0.4)"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    self.wait_for(lambda: any(row["pid"] == child.pid for row in observer.capture()["history"]))
                    row = next(row for row in observer.capture()["history"] if row["pid"] == child.pid)
                    native = tier._NativeProcesses()
                    started, entries = native.entries()
                    self.assertEqual(row, native.identity(entries[child.pid], started))
                    self.assertEqual(row["parent_pid"], os.getpid())
                    self.assertEqual(os.path.normcase(row["path"]), os.path.normcase(sys.executable))
                finally: child.wait(timeout=3)
                self.wait_for(lambda: all(item["pid"] != child.pid for item in observer.capture()["current"]))
                self.assertIn(row, observer.capture()["history"])
            finally: self.assertTrue(observer.stop())


if __name__ == "__main__":
    unittest.main()
