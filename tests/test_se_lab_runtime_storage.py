"""Synthetic metadata fixtures only; no game processes or database reads."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hold_music import se_lab_runtime_storage as storage
from hold_music import se_lab_skyrimnet as tier


class RuntimeStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "lab"
        self.root.mkdir()
        self.write("Game/SkyrimSE.exe", b"fixture executable")
        self.write("Game/Data/Skyrim.esm", b"fixture master")
        self.write("MO2/ModOrganizer.exe", b"fixture application")
        (self.root / "MO2/empty").mkdir()
        self.write(storage.MANIFEST, b'{"fixture":true}')
        self.baseline = tier._protected(self.root)
        self.contract = storage.prepare_runtime_storage(self.root, self.baseline)

    def write(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def observe(self):
        return storage.observe_runtime_storage(self.root, self.baseline, self.contract)

    def assert_allowed(self, result, *, unchanged=False):
        self.assertEqual(result["status"], "within_contract", result)
        self.assertTrue(result["original_assets_unchanged"])
        self.assertTrue(result["storage_within_contract"])
        self.assertEqual(result["protected_paths_unchanged"], unchanged)
        self.assertEqual(result["binding"], self.contract)
        self.assertFalse(result["writes_performed"])
        self.assertFalse(result["database_contents_read"])
        self.assertFalse(result["asset_contents_read"])
        self.assertFalse(result["writer_attribution_verified"])
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["egress_verified"])

    def assert_blocked(self, result):
        self.assertEqual(result["status"], "blocked", result)
        self.assertTrue(result["blockers"])
        self.assertFalse(result["protected_paths_unchanged"])
        self.assertFalse(result["original_assets_unchanged"])

    def test_fresh_contract_matches_existing_strict_snapshot_without_writes(self):
        before = tier._protected(self.root)
        self.assert_allowed(self.observe(), unchanged=True)
        self.assertEqual(before, tier._protected(self.root))
        self.assertEqual(self.contract, storage.prepare_runtime_storage(self.root, self.baseline))
        self.assertEqual(self.contract["policy"]["files"], list(storage.FILES))
        self.assertTrue(self.contract["policy"]["fresh_directory_absent"])

    def test_three_generated_files_are_separate_from_protected_assets(self):
        for name in storage.FILES:
            self.write("Game/" + name, b"opaque private fixture")
        result = self.observe()
        self.assert_allowed(result)
        self.assertEqual(3, sum(row["exists"] for row in result["observation"]["last"]["files"]))
        self.assertNotIn("opaque private fixture", json.dumps(result))
        self.assertNotEqual(self.baseline, tier._protected(self.root))

    def test_volatile_growth_replacement_and_deletion_do_not_change_binding(self):
        path = self.write("Game/" + storage.FILES[0], b"initial")
        first = self.observe()
        path.write_bytes(b"more opaque data")
        self.write("Game/" + storage.FILES[1], b"shared")
        self.write("Game/" + storage.FILES[2], b"wal")
        second = self.observe()
        path.unlink()
        self.write("Game/" + storage.FILES[0], b"replaced")
        (self.root / "Game" / storage.FILES[1]).unlink()
        third = self.observe()
        for result in (first, second, third):
            self.assert_allowed(result)
        self.assertNotEqual(first["observation"], second["observation"])
        self.assertNotEqual(second["observation"], third["observation"])
        self.assertEqual(first["binding"], third["binding"])
        self.assertEqual(storage._digest(first["binding"]), storage._digest(third["binding"]))

    def test_mutation_between_metadata_walks_is_accounted_without_stale_token(self):
        self.write("Game/" + storage.FILES[0], b"first")
        scan = storage._scan
        count = 0
        def changing(root, manifest):
            nonlocal count
            result = scan(root, manifest)
            count += 1
            if count == 1:
                self.write("Game/" + storage.FILES[0], b"larger and different")
                self.write("Game/" + storage.FILES[2], b"new WAL")
            return result
        with patch.object(storage, "_scan", side_effect=changing):
            result = self.observe()
        self.assert_allowed(result)
        self.assertTrue(result["observation"]["metadata_changed_during_observation"])

    def test_missing_file_after_listing_is_optional_only_for_exact_cache_name(self):
        path = self.write("Game/" + storage.FILES[2], b"wal")
        lstat = Path.lstat
        removed = False
        def disappearing(value, *args, **kwargs):
            nonlocal removed
            if value == path and not removed:
                removed = True
                path.unlink()
            return lstat(value, *args, **kwargs)
        with patch.object(Path, "lstat", disappearing):
            result = self.observe()
        self.assert_allowed(result)
        self.assertTrue(result["observation"]["first"]["files"][2]["missing_after_listing"])

    def test_db_and_game_asset_contents_are_never_opened(self):
        for name in storage.FILES:
            self.write("Game/" + name, b"SECRET_FIXTURE_BODY")
        original = Path.open
        opened = []
        def guarded(path, *args, **kwargs):
            opened.append(path)
            if path != self.root / storage.MANIFEST:
                raise AssertionError("Only the baseline manifest may be opened")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            result = self.observe()
        self.assert_allowed(result)
        self.assertTrue(opened)
        self.assertNotIn("SECRET_FIXTURE_BODY", json.dumps(result))

    def test_database_renamed_over_manifest_is_rejected_without_opening_it(self):
        source = self.write("Game/" + storage.FILES[0], b"PRIVATE_DATABASE_FIXTURE")
        manifest = self.root / storage.MANIFEST
        manifest.unlink()
        source.rename(manifest)
        with patch.object(Path, "open", side_effect=AssertionError("Replaced manifest must not be opened")):
            report = self.observe()
        self.assert_blocked(report)
        self.assertEqual(report["blockers"], ["manifest_identity_or_metadata_changed"])
        self.assertFalse(report["database_contents_read"])

    def test_manifest_replacement_between_stat_and_open_is_not_read(self):
        source = self.write("Game/" + storage.FILES[0], b"x" * self.baseline["manifest"]["size"])
        os.utime(source, ns=(self.baseline["manifest"]["mtime_ns"],) * 2)
        manifest = self.root / storage.MANIFEST
        original = Path.open
        reads = []

        class ReadGuard:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def fileno(self):
                return self.stream.fileno()
            def read(self, count):
                reads.append(count)
                raise AssertionError("No replaced-file content read is permitted")

        def replace(path, *args, **kwargs):
            self.assertEqual(path, manifest)
            manifest.rename(self.root / "retained-original-manifest")
            source.rename(manifest)
            return ReadGuard(original(path, *args, **kwargs))

        with patch.object(Path, "open", replace):
            report = self.observe()
        self.assert_blocked(report)
        self.assertEqual(report["blockers"], ["manifest_identity_or_metadata_changed"])
        self.assertEqual(reads, [])

    def test_existing_or_empty_storage_cannot_be_adopted_by_fresh_policy(self):
        (self.root / "Game/default").mkdir()
        for contents in (False, True):
            with self.subTest(contents=contents):
                if contents:
                    self.write("Game/" + storage.FILES[0], b"prior private state")
                with self.assertRaises(ValueError):
                    storage.prepare_runtime_storage(self.root, self.baseline)
                refreshed = tier._protected(self.root)
                with self.assertRaises(ValueError):
                    storage.prepare_runtime_storage(self.root, refreshed)

    def test_no_contract_or_modified_contract_cannot_upgrade_old_run(self):
        candidates = [None, {}, {**self.contract, "version": True},
                      {**self.contract, "policy_sha256": "0" * 64}]
        changed = deepcopy(self.contract)
        changed["policy"]["files"].append("default/other.db")
        candidates.append(changed)
        for contract in candidates:
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                storage.observe_runtime_storage(self.root, self.baseline, contract)

    def test_unknown_file_and_subdirectory_under_storage_block(self):
        for name, directory in (("unexpected.db", False), ("cookie.jar.db-journal", False),
                                ("sub", True), ("cookie.jar.db", True)):
            with self.subTest(name=name, directory=directory):
                path = self.root / "Game/default" / name
                path.parent.mkdir(exist_ok=True)
                if directory:
                    path.mkdir()
                else:
                    path.write_bytes(b"unexpected")
                self.assert_blocked(self.observe())
                if directory:
                    path.rmdir()
                else:
                    path.unlink()

    def test_case_aliased_storage_names_and_file_root_block(self):
        path = self.write("Game/Default/cookie.jar.db", b"opaque")
        self.assert_blocked(self.observe())
        path.unlink()
        path.parent.rmdir()
        path = self.write("Game/default/Cookie.jar.db", b"opaque")
        self.assert_blocked(self.observe())
        path.unlink()
        path.parent.rmdir()
        self.write("Game/default", b"not a directory")
        self.assert_blocked(self.observe())

    def test_unrelated_new_files_and_empty_directories_still_block(self):
        for relative in ("Game/unexpected.bin", "Game/Data/cookie.jar.db", "MO2/default/cookie.jar.db"):
            with self.subTest(relative=relative):
                path = self.write(relative, b"new")
                self.assert_blocked(self.observe())
                path.unlink()
        (self.root / "Game/unexpected-directory").mkdir()
        self.assert_blocked(self.observe())

    def test_original_file_modified_removed_or_replaced_blocks(self):
        path = self.root / "Game/Data/Skyrim.esm"
        for operation in ("modify", "remove", "replace"):
            with self.subTest(operation=operation):
                path.write_bytes(b"fixture master")
                self.baseline = tier._protected(self.root)
                self.contract = storage.prepare_runtime_storage(self.root, self.baseline)
                if operation == "modify":
                    path.write_bytes(b"modified master")
                elif operation == "remove":
                    path.unlink()
                else:
                    path.unlink()
                    path.write_bytes(b"fixture master")
                self.assert_blocked(self.observe())

    def test_manifest_content_baseline_mo2_and_directory_metadata_are_protected(self):
        mutations = (
            lambda: self.write(storage.MANIFEST, b'{"fixture":false}'),
            lambda: self.write("MO2/ModOrganizer.exe", b"modified application"),
            lambda: os.utime(self.root / "Game/Data", ns=(1_700_000_000_000_000_000,) * 2),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.baseline = tier._protected(self.root)
                self.contract = storage.prepare_runtime_storage(self.root, self.baseline)
                mutate()
                self.assert_blocked(self.observe())

    def test_storage_hardlinks_block_without_opening_target(self):
        source = self.write("opaque-original", b"private")
        destination = self.root / "Game/default/cookie.jar.db"
        destination.parent.mkdir()
        try:
            os.link(source, destination)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Fixture filesystem does not support hardlinks: " + type(exc).__name__)
        self.assert_blocked(self.observe())

    def test_symlink_storage_and_original_roots_block(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        target = self.root / "Game/default"
        try:
            target.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Symlink creation unavailable: " + type(exc).__name__)
        self.assert_blocked(self.observe())
        target.unlink()
        game = self.root / "Game"
        retained = self.root / "retained-game"
        game.rename(retained)
        game.symlink_to(retained, target_is_directory=True)
        self.assert_blocked(self.observe())

    def test_direct_reparse_readbacks_fail_even_after_an_earlier_alias_check(self):
        self.write("Game/" + storage.FILES[0], b"opaque")
        original = Path.lstat
        for path in (self.root, self.root / "Game", self.root / "Game/default",
                     self.root / "Game" / storage.FILES[0]):
            with self.subTest(path=path):
                def aliased(value, *args, **kwargs):
                    info = original(value, *args, **kwargs)
                    if value == path:
                        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                    return info
                with patch.object(storage, "_no_alias", side_effect=lambda value: value), \
                        patch.object(Path, "lstat", aliased):
                    result = self.observe()
                self.assert_blocked(result)
                self.assertEqual(result["blockers"], ["aliased_path"])
    def test_lab_and_game_root_identity_changes_are_not_hidden_by_storage(self):
        first_scan, _ = storage._scan(self.root, self.baseline["manifest"])
        for where in ("lab", "game"):
            with self.subTest(where=where):
                altered = deepcopy(first_scan)
                row = (altered["root_identity"] if where == "lab"
                       else altered["directories"][str(self.root / "Game")])
                row["inode"] += 1
                with patch.object(storage, "_scan", return_value=(altered, {"contents_read": False})):
                    self.assert_blocked(self.observe())

    def test_game_root_mtime_alone_is_not_excused_when_storage_is_absent(self):
        os.utime(self.root / "Game", ns=(1_700_000_000_000_000_000,) * 2)
        self.assert_blocked(self.observe())

    def test_immutable_change_between_walks_is_not_an_allowed_volatile_change(self):
        scan = storage._scan
        calls = 0
        def changing(root, manifest):
            nonlocal calls
            result = scan(root, manifest)
            calls += 1
            if calls == 1:
                self.write("Game/SkyrimSE.exe", b"changed after first observation")
            return result
        with patch.object(storage, "_scan", side_effect=changing):
            report = self.observe()
        self.assert_blocked(report)
        self.assertIn("original_assets_unstable", report["blockers"])

    def test_errors_are_fixed_categories_without_private_exception_text(self):
        with patch.object(storage, "_scan", side_effect=PermissionError("PRIVATE_SECRET_PATH_TOKEN")):
            report = self.observe()
        self.assert_blocked(report)
        self.assertEqual(report["blockers"], ["runtime_storage_observation_failed"])
        self.assertNotIn("PRIVATE_SECRET", json.dumps(report))

    def test_contract_rejects_forged_baseline_paths_types_and_directory_inventory(self):
        variants = []
        item = deepcopy(self.baseline)
        item["manifest"]["path"] = str(self.root.parent / "private.db")
        variants.append(item)
        item = deepcopy(self.baseline)
        item["Game"]["SkyrimSE.exe"]["size"] = True
        variants.append(item)
        item = deepcopy(self.baseline)
        item["directories"][str(self.root / "Game")]["inventory_sha256"] = "0" * 64
        variants.append(item)
        item = deepcopy(self.baseline)
        item["Game"]["../other"] = item["Game"].pop("SkyrimSE.exe")
        variants.append(item)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                storage.observe_runtime_storage(self.root, variant, self.contract)


if __name__ == "__main__":
    unittest.main()
