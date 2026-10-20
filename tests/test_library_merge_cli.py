import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.plan_library_merge import main


class LibraryMergeCliTests(unittest.TestCase):
    arguments = ["--staged-library", "staged", "--destination-library", "target"]

    def test_read_only_options_and_result(self):
        report = {"blockers": [], "writes_performed": False, "runtime_verified": False,
                  "review_token": "review-only", "actions": []}
        output = io.StringIO()
        with patch("tools.plan_library_merge.plan_library_merge", return_value=report) as plan, \
                contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments + ["--receipts", "history.json",
                                                    "--session-receipt-index", "3"]), 0)
        plan.assert_called_once_with(staged_library=Path("staged"),
                                     destination_library=Path("target"),
                                     receipts_path=Path("history.json"), session_receipt_index=3)
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_missing_boundary_is_not_fabricated(self):
        with patch("tools.plan_library_merge.plan_library_merge",
                   return_value={"blockers": []}) as plan, \
                contextlib.redirect_stdout(io.StringIO()):
            main(self.arguments)
        self.assertIsNone(plan.call_args.kwargs["session_receipt_index"])
        self.assertIsNone(plan.call_args.kwargs["receipts_path"])

    def test_blocked_review_returns_nonzero_json(self):
        report = {"blockers": [{"code": "conflict", "detail": "Existing identity differs"}],
                  "writes_performed": False}
        output = io.StringIO()
        with patch("tools.plan_library_merge.plan_library_merge", return_value=report), \
                contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments), 2)
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_apply_and_token_options_are_not_supported(self):
        for extra in (["--apply"], ["--review-token", "anything"]):
            with self.subTest(extra=extra), \
                    patch("tools.plan_library_merge.plan_library_merge") as plan, \
                    contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as exit_info:
                main(self.arguments + extra)
            self.assertEqual(exit_info.exception.code, 2)
            plan.assert_not_called()

    def test_unreadable_input_error_is_concise(self):
        output = io.StringIO()
        with patch("tools.plan_library_merge.plan_library_merge",
                   side_effect=ValueError("Malformed fixture")), \
                contextlib.redirect_stderr(output), \
                self.assertRaises(SystemExit) as exit_info:
            main(self.arguments)
        self.assertEqual(exit_info.exception.code, 1)
        self.assertIn("Malformed fixture", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
