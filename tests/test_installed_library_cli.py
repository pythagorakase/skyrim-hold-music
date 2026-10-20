import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.inspect_installed_library import main


class InstalledLibraryCliTests(unittest.TestCase):
    arguments = ["--mo2-root", "fixture-mo2", "--profile", "fixture-profile"]

    def test_explicit_layers_and_evidence_are_forwarded(self):
        report = {"blockers": [], "writes_performed": False, "runtime_verified": False}
        output = io.StringIO()
        with patch("tools.inspect_installed_library.inspect_installed_library",
                   return_value=report) as inspect, contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments + [
                "--game-data", "game/Data", "--vfs-report", "capture.json",
                "--session-receipt-index", "2",
            ]), 0)
        inspect.assert_called_once_with(mo2_root=Path("fixture-mo2"), profile="fixture-profile",
            game_data=Path("game/Data"), vfs_report=Path("capture.json"), session_receipt_index=2)
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_no_layers_or_session_boundary_are_invented(self):
        with patch("tools.inspect_installed_library.inspect_installed_library",
                   return_value={"blockers": []}) as inspect, contextlib.redirect_stdout(io.StringIO()):
            main(self.arguments)
        self.assertIsNone(inspect.call_args.kwargs["game_data"])
        self.assertIsNone(inspect.call_args.kwargs["vfs_report"])
        self.assertIsNone(inspect.call_args.kwargs["session_receipt_index"])

    def test_blocked_inspection_returns_json_and_nonzero(self):
        report = {"blockers": [{"code": "missing_manifest", "detail": "fixture missing"}],
                  "writes_performed": False}
        output = io.StringIO()
        with patch("tools.inspect_installed_library.inspect_installed_library",
                   return_value=report), contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments), 2)
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_no_apply_or_automatic_capture_option(self):
        for option in ("--apply", "--launch-mo2"):
            with self.subTest(option=option), \
                    patch("tools.inspect_installed_library.inspect_installed_library") as inspect, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(self.arguments + [option])
            self.assertEqual(error.exception.code, 2)
            inspect.assert_not_called()

    def test_invalid_path_error_is_concise(self):
        output = io.StringIO()
        with patch("tools.inspect_installed_library.inspect_installed_library",
                   side_effect=ValueError("Unsafe fixture path")), \
                contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as error:
            main(self.arguments)
        self.assertEqual(error.exception.code, 1)
        self.assertIn("Unsafe fixture path", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
