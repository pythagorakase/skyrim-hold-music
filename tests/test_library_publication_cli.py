import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.plan_library_publication import main


class LibraryPublicationCliTests(unittest.TestCase):
    arguments = [
        "--staged-library", "staged", "--destination-snapshot", "snapshot",
        "--mo2-root", "fixture-mo2", "--profile", "pilot",
        "--metadata-mod", "Meta", "--audio-mod", "Audio",
    ]

    def test_explicit_roots_and_routes_are_forwarded_and_blockers_printed(self):
        report = {"blockers": [{"code": "snapshot_mismatch"}], "can_apply": False}
        output = io.StringIO()
        with patch("tools.plan_library_publication.plan_library_publication",
                   return_value=report) as plan, contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments + ["--game-data", "game/Data",
                "--vfs-report", "capture.json", "--session-receipt-index", "2"]), 2)
        plan.assert_called_once_with(
            staged_library=Path("staged"), destination_snapshot=Path("snapshot"),
            mo2_root=Path("fixture-mo2"), profile="pilot", metadata_mod="Meta", audio_mod="Audio",
            game_data=Path("game/Data"), vfs_report=Path("capture.json"), session_receipt_index=2,
        )
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_no_apply_launcher_or_implicit_destination(self):
        for arguments in (self.arguments[:-2], self.arguments + ["--apply"],
                          self.arguments + ["--launch-mo2"]):
            with self.subTest(arguments=arguments), \
                    patch("tools.plan_library_publication.plan_library_publication") as plan, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(arguments)
            self.assertEqual(error.exception.code, 2)
            plan.assert_not_called()

    def test_readonly_success_and_concise_failure(self):
        with patch("tools.plan_library_publication.plan_library_publication",
                   return_value={"blockers": [], "can_apply": False}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.arguments), 0)
        output = io.StringIO()
        with patch("tools.plan_library_publication.plan_library_publication",
                   side_effect=ValueError("Unsafe fixture route")), \
                contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as error:
            main(self.arguments)
        self.assertEqual(error.exception.code, 1)
        self.assertIn("Unsafe fixture route", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
