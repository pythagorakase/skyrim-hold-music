"""Independent import/merge boundary regressions using local synthetic assets."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from hold_music.library import Library
from hold_music.runtime_contract import project_runtime_contract, runtime_identity_key
from tools import import_recording as importer


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
        output.writeframes(b"\x00\x00" * 4410)


def files(root):
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*")) if path.is_file()
    } if root.exists() else {}


def recording_fixture(root, *, performer="sven", region="whiterun",
                      composition="fixture-composition", strict=True, contract=True,
                      slot=1, revision="reviewed-v1"):
    """Write one synthetic source row and optionally its explicit projection."""
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "library.json", dict(version=1, slots=24, recordings=[]))
    original = root.parent / (root.name + "-input.wav")
    wav(original)
    request = dict(
        tradition=region, recipe_id=f"{region}/fixture", recipe_revision=revision,
        model_id="fixture-model", instrument_family="plucked_string",
        instrument_name="cittern", arrangement="solo_lute", mode="instrumental", voice="none")
    projection = project_runtime_contract(dict(performer_id=performer, request=request))
    extra = {
        key: request[key] for key in
        ("recipe_revision", "instrument_family", "instrument_name", "arrangement", "voice")
    } if strict else {}
    if strict and contract:
        extra["identity_key"] = projection["identity_key"]
    row = Library(root, session_receipt_index=0).add_recording(
        original, performer_id=performer, region=region, mode="instrumental",
        gender="male", composition_id=composition, recipe_id=request["recipe_id"],
        model_id=request["model_id"] if strict else "unknown",
        source=dict(kind="import", path_or_request_id="synthetic-fixture"),
        slot=slot, **extra)
    if strict and contract:
        manifest = json.loads((root / "library.json").read_text(encoding="utf-8"))
        manifest["runtime_selection"] = dict(version=1, contracts=[projection])
        write_json(root / "library.json", manifest)
    return row


class ImportSourceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "recording.mp3"
        self.source.write_bytes(b"synthetic original source")
        self.lyrics = self.root / "words.txt"
        self.lyrics.write_bytes(b"\xef\xbb\xbfA lamp beside the road.\r\n")
        self.ffmpeg = self.root / "fake-ffmpeg.exe"
        self.ffmpeg.write_bytes(b"synthetic executable identity")
        self.ffmpeg.chmod(0o755)
        self.library = self.root / "library"
        write_json(self.library / "library.json", dict(version=1, slots=24, recordings=[]))
        self.metadata = self.root / "recording.identity.json"
        self.identity = dict(
            version=1, source_sha256=sha(self.source), lyrics_sha256=sha(self.lyrics),
            performer_id="sven", region="whiterun", mode="vocal", gender="male",
            recipe_id="whiterun/operator-song", recipe_revision="source-review-v1",
            model_id="operator-supplied-model", instrument_family="plucked_string",
            instrument_name="cittern", arrangement="solo_lute_and_voice", voice="male")
        write_json(self.metadata, self.identity)
        self.arguments = dict(
            library=self.library, performer="sven", region="whiterun", mode="vocal",
            gender="male", source=self.source, lyrics=self.lyrics, ffmpeg=self.ffmpeg,
            metadata=self.metadata)

    def review(self, **extra):
        return importer.review_import_recording(**dict(self.arguments, **extra))

    def assert_blocked(self, operation):
        try:
            report = operation()
        except (ValueError, OSError):
            return
        self.assertEqual(report["status"], "blocked", report)
        self.assertIs(report["can_apply"], False)

    def fake_conversion(self, arguments, **options):
        wav(Path(arguments[-1]))

    def test_explicit_metadata_does_not_activate_a_runtime_selection_contract(self):
        review = self.review()
        self.assertIs(review["can_apply"], True, review)
        with patch.object(importer.subprocess, "run", side_effect=self.fake_conversion):
            result = self.review(apply=True, review_token=review["review_token"])
        self.assertEqual(result["status"], "imported", result)
        manifest = json.loads((self.library / "library.json").read_text(encoding="utf-8"))
        self.assertNotIn("runtime_selection", manifest)
        row = manifest["recordings"][0]
        for key in ("recipe_id", "recipe_revision", "model_id",
                    "instrument_family", "instrument_name", "arrangement", "voice"):
            self.assertEqual(row[key], self.identity[key])

    def test_source_lyrics_and_sidecar_changes_during_conversion_block_publication(self):
        for name in ("source", "lyrics", "metadata"):
            with self.subTest(changed=name):
                path = getattr(self, name)
                original = path.read_bytes()
                review = self.review()
                self.assertIs(review["can_apply"], True, review)
                before = files(self.library)

                def changed_during_conversion(arguments, **options):
                    self.fake_conversion(arguments, **options)
                    path.write_bytes(original + b" ")

                try:
                    with patch.object(importer.subprocess, "run", side_effect=changed_during_conversion):
                        self.assert_blocked(lambda: self.review(
                            apply=True, review_token=review["review_token"]))
                    after = files(self.library)
                    # An attempted apply may retain its harmless kernel-lock file.
                    before.pop(".import.lock", None)
                    after.pop(".import.lock", None)
                    self.assertEqual(after, before)
                    self.assertEqual(path.read_bytes(), original + b" ")
                finally:
                    path.write_bytes(original)

    def test_duplicate_identity_keys_are_rejected_before_conversion(self):
        raw = json.dumps(self.identity)
        self.metadata.write_text(
            raw[:-1] + ', "model_id": "conflicting-model"}', encoding="utf-8")
        before = files(self.library)
        with patch.object(importer.subprocess, "run") as convert:
            self.assert_blocked(lambda: self.review())
            convert.assert_not_called()
        self.assertEqual(files(self.library), before)

    def test_source_or_converter_drift_invalidates_review_before_conversion(self):
        for path in (self.source, self.ffmpeg):
            with self.subTest(changed=path.name):
                original = path.read_bytes()
                review = self.review()
                path.write_bytes(original + b" changed")
                before = files(self.library)
                with patch.object(importer.subprocess, "run") as convert:
                    self.assert_blocked(lambda: self.review(
                        apply=True, review_token=review["review_token"]))
                    convert.assert_not_called()
                self.assertEqual(files(self.library), before)
                path.write_bytes(original)

    def test_import_into_projected_runtime_library_requires_separate_merge_review(self):
        recording_fixture(self.library, performer="lynly")
        before = files(self.library)
        with patch.object(importer.subprocess, "run") as convert:
            self.assert_blocked(lambda: self.review())
            convert.assert_not_called()
        self.assertEqual(files(self.library), before)

    def test_slot_filled_after_final_preflight_is_not_replaced_by_import(self):
        review = self.review()
        real_add = Library.add_recording
        competing_rows = []

        def concurrent_publication(cache, wav_path, **keywords):
            competing_rows.append(real_add(
                Library(self.library), wav_path, slot=keywords["slot"],
                performer_id="other-bard", region="rift", mode="instrumental",
                gender="female", composition_id="concurrent-publication",
                recipe_id="rift/legacy", model_id="unknown",
                source=dict(kind="import", path_or_request_id="concurrent-fixture")))
            return real_add(cache, wav_path, **keywords)

        with patch.object(importer.subprocess, "run", side_effect=self.fake_conversion), \
                patch.object(Library, "add_recording", new=concurrent_publication):
            self.assert_blocked(lambda: self.review(
                apply=True, review_token=review["review_token"]))
        self.assertEqual(len(competing_rows), 1)
        manifest = json.loads((self.library / "library.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [row["composition_id"] for row in manifest["recordings"]],
            ["concurrent-publication"])
        self.assertEqual(manifest["recordings"][0]["performer_id"], "other-bard")


class LibraryMergeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "staged-library"
        self.destination = self.root / "destination-library"
        recording_fixture(self.source, performer="new-bard", composition="incoming")
        recording_fixture(
            self.destination, performer="existing-bard", composition="retained", strict=False)

    def review(self, **extra):
        from hold_music.library_merge import plan_library_merge
        return plan_library_merge(self.source, self.destination, **extra)

    def edit_manifest(self, root, edit):
        path = root / "library.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        edit(manifest)
        write_json(path, manifest)

    def assert_refused_read_only(self, **extra):
        before = files(self.root)
        try:
            report = self.review(**extra)
        except (ValueError, OSError):
            report = None
        if report is not None:
            self.assertTrue(report["blockers"], report)
            self.assertFalse(report["writes_performed"])
        self.assertEqual(files(self.root), before)

    def test_preserves_disabled_destination_row_and_excludes_source_generation_history(self):
        retained_history = [dict(
            id="destination-generation", performer_id="existing-bard", save_id="saved-world",
            world_id="world", at_hours=1, action="compose_lyrics")]
        foreign_history = [dict(
            id="source-generation", performer_id="new-bard", save_id="source-save",
            world_id="source-world", at_hours=10, action="generate_recording")]

        def destination_edit(manifest):
            manifest["recordings"][0]["playable"] = False
            manifest["recordings"][0]["operator_note"] = "intentionally disabled"
            manifest["generation_receipts"] = retained_history

        self.edit_manifest(self.destination, destination_edit)
        self.edit_manifest(self.source, lambda manifest: manifest.update(
            generation_receipts=foreign_history))
        original = json.loads((self.destination / "library.json").read_text(encoding="utf-8"))
        before = files(self.root)
        report = self.review()
        self.assertEqual(report["blockers"], [], report)
        proposed = report["proposed_manifest"]
        self.assertEqual(proposed["recordings"][0], original["recordings"][0])
        self.assertEqual(proposed["generation_receipts"], retained_history)
        self.assertNotIn("source-generation", json.dumps(proposed))
        self.assertEqual(files(self.root), before)

    def test_contract_activation_cannot_silently_disable_retained_legacy_performer(self):
        recording_fixture(
            self.destination, performer="new-bard", composition="legacy-song", strict=False)
        self.assert_refused_read_only()

    def test_different_active_contract_cannot_be_silently_replaced(self):
        recording_fixture(
            self.destination, performer="new-bard", composition="older-song",
            revision="different-reviewed-revision")
        self.assert_refused_read_only()

    def test_same_composition_identifier_cannot_acquire_conflicting_region(self):
        recording_fixture(
            self.source, performer="new-bard", composition="retained", region="rift")
        self.assert_refused_read_only()

    def test_session_boundary_beyond_receipt_history_cannot_unlock_slots(self):
        receipts = self.root / "current-receipts.json"
        write_json(receipts, dict(version=1, performances=[dict(
            id="interrupted-performance", performer_id="existing-bard", save_id="save",
            world_id="world", composition_id="historical", at_hours=2,
            slot=2, outcome="interrupted")]))
        self.assert_refused_read_only(receipts_path=receipts, session_receipt_index=2)

    def test_duplicate_manifest_keys_cannot_select_an_alternate_contract(self):
        path = self.source / "library.json"
        raw = path.read_text(encoding="utf-8")
        path.write_text(raw[:-1] + ', "runtime_selection": null}', encoding="utf-8")
        self.assert_refused_read_only()


if __name__ == "__main__":
    unittest.main()
