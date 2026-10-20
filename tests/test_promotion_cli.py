"""The command-line boundary never turns a preview or status read into a write."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import promote_game_package as cli
from promotion_fixtures import create_promotion_fixture

ROOT = Path(__file__).resolve().parents[1]


class PromotionCliTests(unittest.TestCase):
    def invoke(self, arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(arguments)
        return code, json.loads(output.getvalue())

    def args(self):
        return ["--mo2-root", "fixture-mo2", "--build-dir", "fixture-build",
                "--source-root", "fixture-source", "--profile", "fixture-profile"]

    def test_default_review_never_enables_apply(self):
        with patch.object(cli, "promote_static", return_value={"status": "promotion_dry_run"}) as run:
            code, result = self.invoke(self.args())
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "promotion_dry_run")
        self.assertIs(run.call_args.kwargs["apply"], False)
        self.assertIsNone(run.call_args.kwargs["review_token"])
        self.assertEqual(run.call_args.kwargs["mo2_root"], Path("fixture-mo2"))
        self.assertNotIn("process_probe", run.call_args.kwargs)

    def test_apply_requires_a_separately_supplied_token(self):
        with patch.object(cli, "promote_static", return_value={"status": "static_applied"}) as run:
            code, _ = self.invoke(self.args() + ["--apply", "--review-token", "reviewed-token"])
        self.assertEqual(code, 0)
        self.assertIs(run.call_args.kwargs["apply"], True)
        self.assertEqual(run.call_args.kwargs["review_token"], "reviewed-token")

    def test_rollback_is_reviewed_before_restoring(self):
        for execution in ([], ["--apply", "--review-token", "rollback-token"]):
            with self.subTest(execution=execution), patch.object(
                    cli, "rollback_static", return_value={"status": "rollback_dry_run"}) as run:
                self.invoke(["--mo2-root", "fixture-mo2", "--rollback", *execution])
            self.assertEqual(run.call_args.kwargs["apply"], bool(execution))
            self.assertNotIn("process_probe", run.call_args.kwargs)

    def test_status_cannot_dispatch_mutation(self):
        with patch.object(cli, "promotion_status", return_value={"status": "no_transaction"}) as status, \
                patch.object(cli, "promote_static") as promote, patch.object(cli, "rollback_static") as rollback:
            self.invoke(["--mo2-root", "fixture-mo2", "--status"])
        status.assert_called_once()
        promote.assert_not_called()
        rollback.assert_not_called()

    def test_invalid_or_unreviewed_execution_is_rejected_before_core(self):
        invalid = [
            self.args() + ["--apply"],
            self.args() + ["--apply", "--review-token", ""],
            self.args() + ["--review-token", "token"],
            self.args() + ["--rollback"],
            self.args() + ["--status"],
            ["--mo2-root", "fixture-mo2", "--status", "--apply", "--review-token", "token"],
            ["--mo2-root", "fixture-mo2", "--status", "--review-token", "token"],
            ["--mo2-root", "fixture-mo2", "--rollback", "--apply"],
            ["--mo2-root", "fixture-mo2"],
            self.args() + ["--process-probe", "fake"],
            self.args() + ["--library", "fixture-library"],
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), \
                    patch.object(cli, "promote_static") as promote, \
                    patch.object(cli, "rollback_static") as rollback, \
                    patch.object(cli, "promotion_status") as status:
                with self.assertRaises(SystemExit) as raised:
                    cli.main(arguments)
                self.assertEqual(raised.exception.code, 2)
            promote.assert_not_called()
            rollback.assert_not_called()
            status.assert_not_called()

    def test_blocked_or_interrupted_result_is_not_reported_as_success(self):
        for result in ({"status": "blocked"}, {"status": "interrupted"},
                       {"status": "promotion_dry_run", "blockers": [{"code": "fixture"}]}):
            with self.subTest(result=result), patch.object(cli, "promote_static", return_value=result):
                code, returned = self.invoke(self.args())
                self.assertEqual(code, 2)
                self.assertEqual(returned, result)

    def test_core_refusal_is_an_error_not_a_successful_report(self):
        with patch.object(cli, "promote_static", side_effect=ValueError("Changed input")), \
                redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                cli.main(self.args())
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(output.getvalue(), "")

    def test_real_cli_preview_status_and_rejected_token_preserve_fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = create_promotion_fixture(Path(temporary).resolve())
            arguments = fixture["arguments"]
            common = [sys.executable, "-B", str(ROOT / "tools/promote_game_package.py"),
                      "--mo2-root", str(arguments["mo2_root"])]
            promotion = [*common, "--build-dir", str(arguments["build_dir"]),
                         "--source-root", str(arguments["source_root"]),
                         "--profile", arguments["profile"]]

            def state():
                return {p.relative_to(fixture["root"]).as_posix():
                        (p.read_bytes(), p.stat().st_mtime_ns)
                        for p in fixture["root"].rglob("*") if p.is_file()}

            original = state()
            review = subprocess.run(promotion, capture_output=True, text=True, check=True)
            parsed = json.loads(review.stdout)
            self.assertEqual(parsed["status"], "promotion_dry_run")
            self.assertTrue(parsed["can_apply"])
            self.assertIsInstance(parsed["review_token"], str)
            status = subprocess.run([*common, "--status"], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(status.stdout)["status"], "no_transaction")
            refused = subprocess.run([*promotion, "--apply", "--review-token", "stale-token"],
                                     capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(json.loads(refused.stdout)["status"], "blocked")
            self.assertEqual(state(), original)
            self.assertFalse((arguments["mo2_root"] / ".hold-music-promotion").exists())
