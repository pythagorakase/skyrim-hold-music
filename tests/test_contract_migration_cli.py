import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.review_contract_migration import main


class ContractMigrationCliTests(unittest.TestCase):
    arguments = ["--mo2-root", "fixture", "--profile", "pilot", "--proposal", "proposal.json"]

    def test_review_passes_explicit_inputs_and_prints_blockers(self):
        report = {"blockers": [{"code": "missing_audio"}], "writes_performed": False}
        output = io.StringIO()
        with patch("tools.review_contract_migration.review_contract_migration",
                   return_value=report) as review, contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments + [
                "--game-data", "game/Data", "--vfs-report", "capture.json",
                "--session-receipt-index", "2",
            ]), 2)
        review.assert_called_once_with(
            mo2_root=Path("fixture"), profile="pilot", proposal_path=Path("proposal.json"),
            game_data=Path("game/Data"), vfs_report=Path("capture.json"), session_receipt_index=2,
        )
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_readonly_success_does_not_invent_optional_inputs(self):
        with patch("tools.review_contract_migration.review_contract_migration",
                   return_value={"blockers": []}) as review, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.arguments), 0)
        for key in ("game_data", "vfs_report", "session_receipt_index"):
            self.assertIsNone(review.call_args.kwargs[key])

    def test_explicit_proposal_required_and_no_apply_or_launcher(self):
        for arguments in (self.arguments[:4], self.arguments + ["--apply"],
                          self.arguments + ["--launch-mo2"]):
            with self.subTest(arguments=arguments), \
                    patch("tools.review_contract_migration.review_contract_migration") as review, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(arguments)
            self.assertEqual(error.exception.code, 2)
            review.assert_not_called()

    def test_invalid_input_is_concise(self):
        output = io.StringIO()
        with patch("tools.review_contract_migration.review_contract_migration",
                   side_effect=ValueError("Unsafe fixture proposal")), \
                contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as error:
            main(self.arguments)
        self.assertEqual(error.exception.code, 1)
        self.assertIn("Unsafe fixture proposal", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
