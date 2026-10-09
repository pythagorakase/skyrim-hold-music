"""Offline contract and security checks. These tests never call Google."""

import base64
from http.client import HTTPConnection
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from tools import configure_key
from tools import workshop_server as server


AUDIO = b"ID3\x04\x00\x00fixture-audio-data"
SECRET = "fixture-key-never-returned-to-browser"


def music_payload(audio=AUDIO, mime="audio/mpeg"):
    return {"status": "completed", "steps": [
        {"type": "model_output", "content": [{"type": "text", "text": "Verse one"}]},
        {"type": "model_output", "content": [{"type": "audio", "mime_type": mime, "data": base64.b64encode(audio).decode("ascii")}]},
    ]}


class KeyTests(unittest.TestCase):
    def test_atomic_private_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            path = Path(temporary) / "hold-music" / "gemini-api-key"
            configure_key.save_key(SECRET, path)
            self.assertEqual(server.read_key(path), SECRET)
            # Windows chmod only changes the read-only flag, not POSIX modes.
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(len(list(path.parent.iterdir())), 1)
            configure_key.save_key("replacement-key", path)
            self.assertEqual(server.read_key(path), "replacement-key")
            with patch.dict(os.environ, {"GEMINI_API_KEY": "environment-key"}):
                self.assertEqual(server.read_key(path), "environment-key")

    def test_invalid_keys_and_missing_file(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            path = Path(temporary) / "private" / "key"
            self.assertIsNone(server.read_key(path))
            for key in ("", "hello world", "one\ntwo", "\x01control", "é", "x" * 513):
                with self.subTest(key_length=len(key)), self.assertRaises(ValueError):
                    configure_key.save_key(key, path)
            self.assertFalse(path.exists())

    def test_non_terminal_fails_without_reading_or_saving_key(self):
        with patch("sys.stdin.isatty", return_value=False), patch.object(configure_key.getpass, "getpass") as getpass, patch.object(configure_key, "save_key") as save, patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(configure_key.main(), 1)
            getpass.assert_not_called()
            save.assert_not_called()

    def test_echo_fallback_fails_without_saving(self):
        with patch("sys.stdin.isatty", return_value=True), patch.object(configure_key.getpass, "getpass", side_effect=configure_key.getpass.GetPassWarning("no hidden terminal")), patch.object(configure_key, "save_key") as save, patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(configure_key.main(), 1)
            save.assert_not_called()


class GoogleTests(unittest.TestCase):
    def http_failure(self, code, body):
        upstream = HTTPError(server.GOOGLE_ENDPOINT, code, SECRET, {}, io.BytesIO(body))
        opener = Mock()
        opener.open.side_effect = upstream
        with patch.object(server, "build_opener", return_value=opener), self.assertRaises(server.WorkshopError) as raised:
            server.call_google("prompt", SECRET)
        opener.open.assert_called_once()
        return raised.exception

    def test_request_endpoint_key_header_model_and_no_storage(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(music_payload()).encode())
        with patch.object(server, "build_opener", return_value=opener):
            result = server.call_google("The exact edited prompt", SECRET)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, server.GOOGLE_ENDPOINT)
        self.assertNotIn(SECRET, request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), SECRET)
        self.assertEqual(json.loads(request.data), {"model": "lyria-3.5", "input": "The exact edited prompt", "store": False})
        self.assertEqual(server.parse_music(result), (AUDIO, "audio/mpeg", "Verse one"))
        opener.open.assert_called_once()

    def test_upstream_failures_are_safe_and_never_retried(self):
        for failure in (HTTPError(server.GOOGLE_ENDPOINT, 403, SECRET, {}, io.BytesIO(SECRET.encode())), URLError(SECRET), TimeoutError(SECRET), ValueError(SECRET)):
            with self.subTest(failure=type(failure).__name__):
                opener = Mock()
                opener.open.side_effect = failure
                with patch.object(server, "build_opener", return_value=opener), self.assertRaises(server.WorkshopError) as raised:
                    server.call_google("prompt", SECRET)
                self.assertNotIn(SECRET, str(raised.exception))
                opener.open.assert_called_once()

    def test_redirect_is_never_followed(self):
        self.assertIsNone(server.NoRedirects().redirect_request(None, None, 302, "redirect", {}, "https://evil.invalid/"))

    def test_http_diagnostics_redact_active_key_and_credential_patterns(self):
        other_google_key = "AIza" + "b" * 35
        credentials = [SECRET, other_google_key, "query-secret-value", "header-secret-value", "auth-secret-value", "standalone-token", "environment-secret-value"]
        message = (f"échec 音楽 {SECRET}; {other_google_key}; "
                   "https://example.invalid/?key=query-secret-value&other=ok "
                   "x-goog-api-key: header-secret-value "
                   "Authorization: Bearer auth-secret-value "
                   "Bearer standalone-token GEMINI_API_KEY=environment-secret-value")
        failure = self.http_failure(403, json.dumps({"error": {
            "message": message, "status": "PERMISSION_DENIED", "code": "permission_denied",
            "details": [{"reason": "API_KEY_SERVICE_BLOCKED", "metadata": {"key": SECRET}}],
            "ignored": {"key": SECRET},
        }}).encode())
        output = str(failure) + json.dumps(failure.details)
        for credential in credentials:
            self.assertNotIn(credential, output)
        self.assertIn("Google HTTP 403", str(failure))
        self.assertIn("échec 音楽", str(failure))
        self.assertEqual(failure.details["status"], "PERMISSION_DENIED")
        self.assertEqual(failure.details["code"], "permission_denied")
        self.assertEqual(failure.details["reasons"], ["API_KEY_SERVICE_BLOCKED"])
        self.assertNotIn("metadata", output)
        self.assertEqual(str(failure).count("No automatic retry was made."), 1)

    def test_credentials_are_redacted_before_display_truncation(self):
        value = "x" * 688 + SECRET + " end"
        failure = self.http_failure(500, json.dumps({"error": {"message": value}}).encode())
        self.assertNotIn(SECRET[:10], str(failure))
        self.assertEqual(len(failure.details["message"]), 700)
        self.assertTrue(failure.details["message"].endswith("…"))

    def test_encoded_active_key_and_known_authorization_forms(self):
        key = "fixture+key/with=symbols"
        cases = [
            "fixture%2Bkey%2Fwith%3Dsymbols",
            '"x-goog-api-key": "other-secret"',
            '"Authorization": "Basic dXNlcjpwYXNz"',
            "https://example.invalid/?api_key=other-secret&access_token=another-secret",
            "sk-or-v1-" + "c" * 40,
            "ya29." + "d" * 40,
        ]
        for value in cases:
            with self.subTest(value=value):
                output = server.safe_provider_text(value, key)
                for secret in ("fixture%2Bkey%2Fwith%3Dsymbols", "other-secret", "dXNlcjpwYXNz", "another-secret", "c" * 40, "d" * 40):
                    self.assertNotIn(secret, output)
                self.assertIn("[redacted]", output)

    def test_non_json_and_unexpected_error_types_keep_http_status_only(self):
        bodies = [b"<html>" + SECRET.encode() + b"</html>", b"not json", b"\xff", b"[]", b"null"]
        for value in (None, [], "oops", 42, {"message": [SECRET], "status": {"key": SECRET}, "code": 403,
                                                   "details": [{"reason": {"key": SECRET}}, [], SECRET]}):
            bodies.append(json.dumps({"error": value}).encode())
        for body in bodies:
            with self.subTest(body=body):
                failure = self.http_failure(418, body)
                self.assertIn("Google HTTP 418", str(failure))
                self.assertEqual(failure.details, {"provider": "google", "http_status": 418})
                self.assertNotIn(SECRET, str(failure))

    def test_error_source_read_is_capped_and_malformed_deep_json_is_safe(self):
        stream = Mock()
        stream.read.return_value = b"{" * server.MAX_ERROR_BODY
        error = HTTPError(server.GOOGLE_ENDPOINT, 503, SECRET, {}, stream)
        failure = server.google_http_failure(error, SECRET)
        stream.read.assert_called_once_with(64 * 1024)
        stream.close.assert_called_once()
        self.assertEqual(failure.details["http_status"], 503)
        deeply_nested = ('{"error":' + "[" * 2000 + "0" + "]" * 2000 + "}").encode()
        failure = self.http_failure(500, deeply_nested)
        self.assertIn("Google HTTP 500", str(failure))

    def test_payment_5xx_and_api_compatibility_have_actionable_hints(self):
        for code, expected in ((402, "prepaid credit"), (500, "internal server"), (502, "gateway"), (503, "overloaded"), (504, "timed out")):
            failure = self.http_failure(code, b"{}")
            self.assertIn(expected, str(failure))
            self.assertIn(f"Google HTTP {code}", str(failure))
        failure = self.http_failure(400, b'{"error":{"message":"Unsupported model for this API revision","code":"invalid_request"}}')
        self.assertIn("endpoint and request settings support Lyria 3.5", str(failure))
        self.assertIn("invalid_request", str(failure))

    def test_unicode_controls_and_diagnostic_fields_are_bounded(self):
        failure = self.http_failure(400, json.dumps({"error": {
            "message": "Café\n音楽\u202e\x00unavailable", "status": "S" * 200, "code": "C" * 200,
            "details": [{"reason": str(index) + "r" * 200} for index in range(100)],
        }}).encode())
        self.assertIn("Café 音楽 unavailable", str(failure))
        self.assertNotIn("\u202e", str(failure))
        self.assertNotIn("\x00", str(failure))
        self.assertLessEqual(len(failure.details["status"]), 100)
        self.assertLessEqual(len(failure.details["code"]), 100)
        self.assertEqual(len(failure.details["reasons"]), 5)
        self.assertTrue(all(len(reason) <= 120 for reason in failure.details["reasons"]))

    def test_mp3_wav_and_last_audio_block(self):
        for mime in ("audio/mp3", "audio/mpeg", "audio/wav", "audio/x-wav"):
            self.assertEqual(server.parse_music(music_payload(mime=mime))[1], mime)
        payload = music_payload()
        payload["steps"][1]["content"].append({"type": "audio", "data": base64.b64encode(b"last").decode()})
        self.assertEqual(server.parse_music(payload)[0], b"last")

    def test_unfinished_blocked_malformed_responses(self):
        bad_payloads = [{"steps": []}, {"steps": "wrong"}, music_payload(mime="text/html"), music_payload(audio=b"")]
        broken_audio = music_payload()
        broken_audio["steps"][1]["content"][0]["data"] = "not base64!"
        bad_payloads.append(broken_audio)
        for status in ("queued", "in_progress", "failed", "cancelled", "incomplete", "requires_action"):
            payload = music_payload()
            payload["status"] = status
            bad_payloads.append(payload)
        for payload in bad_payloads:
            with self.subTest(payload_status=payload.get("status")), self.assertRaises(server.WorkshopError):
                server.parse_music(payload)


class WorkshopHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        dashboard = self.root / "dashboard"
        dashboard.mkdir()
        (dashboard / "index.html").write_text("<!doctype html><title>Workshop fixture</title>", encoding="utf-8")
        (dashboard / "palette-data.json").write_text(json.dumps({"finalists": [
            {"id": "solo", "name": "Canonical solo"},
            {"id": "ensemble", "name": "Canonical ensemble", "ensemble_roles": ["a", "b", "c"], "ensemble_clause": "Three singers"},
        ], "existing": []}), encoding="utf-8")
        (self.root / "secret.txt").write_text(SECRET, encoding="utf-8")
        self.generator = Mock(return_value=music_payload())
        self.key_reader = Mock(return_value=SECRET)
        self.workshop = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader)
        self.http = server.WorkshopServer(port=0, workshop=self.workshop)
        self.thread = threading.Thread(target=self.http.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=1)
        self.temporary.cleanup()

    def request(self, method, path, payload=None, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=3)
        request_headers = {"Origin": self.origin}
        if method == "POST":
            request_headers.update({"Content-Type": "application/json", "X-Workshop-Token": self.workshop.token})
        request_headers.update(headers or {})
        body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        content = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            content = json.loads(content) if content else None
        return status, response_headers, content

    def payload(self, **overrides):
        return {"profile_id": "solo", "profile_name": "untrusted supplied name", "arrangement": "lute_voice", "prompt": "A quiet song with one lute", **overrides}

    def completed_job(self, identifier):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status, _, content = self.request("GET", f"/api/jobs/{identifier}")
            self.assertEqual(status, 200)
            if content["job"]["status"] in ("completed", "failed"):
                return content["job"]
            time.sleep(0.005)
        self.fail("Fixture job did not finish")

    def test_status_is_read_only_and_does_not_expose_key(self):
        status, headers, content = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertTrue(content["configured"])
        self.assertEqual(content["model"], "lyria-3.5")
        self.assertIsNone(content["active_job"])
        self.assertEqual(content["csrf_token"], self.workshop.token)
        self.assertNotIn(SECRET, json.dumps(content))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.generator.assert_not_called()

    def test_completed_generation_saved_restored_and_playable(self):
        status, _, content = self.request("POST", "/api/generate", self.payload())
        self.assertEqual(status, 202)
        self.assertEqual(content["job"]["status"], "queued")
        job = self.completed_job(content["job"]["id"])
        self.assertEqual(job["status"], "completed")
        take = job["take"]
        self.assertEqual(take["profile_name"], "Canonical solo")
        self.assertEqual(take["prompt"], self.payload()["prompt"])
        self.assertEqual(take["lyrics"], "Verse one")
        self.generator.assert_called_once_with(self.payload()["prompt"], SECRET)
        self.assertEqual(self.request("GET", take["audio_url"])[2], AUDIO)
        download_status, headers, audio = self.request("GET", take["download_url"])
        self.assertEqual(download_status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(audio, AUDIO)
        takes = self.request("GET", "/api/takes")[2]["takes"]
        self.assertEqual(takes, [take])
        restored = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader)
        self.assertEqual(restored.list_takes(), takes)
        self.assertIsNone(self.workshop.status()["active_job"])
        for path in (self.root / "auditions").glob("*/*"):
            self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_audio_ranges_and_head(self):
        content = self.request("POST", "/api/generate", self.payload())[2]
        take = self.completed_job(content["job"]["id"])["take"]
        status, headers, content = self.request("GET", take["audio_url"], headers={"Range": "bytes=3-7"})
        self.assertEqual(status, 206)
        self.assertEqual(content, AUDIO[3:8])
        self.assertEqual(headers["Content-Range"], f"bytes 3-7/{len(AUDIO)}")
        self.assertEqual(self.request("GET", take["audio_url"], headers={"Range": "bytes=-4"})[2], AUDIO[-4:])
        for invalid in ("bytes=999-", "bytes=-0", "bytes=0-2,5-8", "bytes=8-3", "bytes=" + "9" * 5000 + "-"):
            self.assertEqual(self.request("GET", take["audio_url"], headers={"Range": invalid})[0], 416)
        status, headers, body = self.request("HEAD", take["audio_url"])
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(int(headers["Content-Length"]), len(AUDIO))

    def test_allowlisted_static_routes_only(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertEqual(self.request("GET", "/index.html")[0], 200)
        for path in ("/secret.txt", "/tools/configure_key.py", "/../secret.txt", "/%2e%2e/secret.txt", "/dashboard/palette-data.json", "/.config/hold-music/gemini-api-key"):
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_origin_host_csrf_and_fetch_metadata_protect_generation(self):
        rejected_headers = [
            {"Origin": "https://evil.invalid"}, {"Origin": "null"},
            {"Host": f"evil.invalid:{self.http.server_port}"},
            {"Host": f"localhost:{self.http.server_port}"},  # Origin is 127.0.0.1, so mismatch.
            {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"},
            {"X-Workshop-Token": "wrong"}, {"X-Workshop-Token": ""}, {"X-Workshop-Token": "é"},
        ]
        for headers in rejected_headers:
            with self.subTest(headers=headers):
                self.assertEqual(self.request("POST", "/api/generate", self.payload(), headers=headers)[0], 403)
        self.assertEqual(self.request("GET", "/api/status", headers={"Origin": "https://evil.invalid"})[0], 403)
        self.assertEqual(self.request("OPTIONS", "/api/generate")[0], 405)
        self.generator.assert_not_called()

    def test_missing_key_invalid_body_and_prompt_validation(self):
        self.key_reader.return_value = None
        self.assertFalse(self.request("GET", "/api/status")[2]["configured"])
        self.assertEqual(self.request("POST", "/api/generate", self.payload())[0], 503)
        self.key_reader.return_value = SECRET
        for payload in ([1], self.payload(profile_id="unknown"), self.payload(profile_id=[]), self.payload(arrangement=[]), self.payload(arrangement="trio"), self.payload(prompt="  "), self.payload(prompt="x" * 20001), self.payload(prompt="bad\x00prompt")):
            self.assertEqual(self.request("POST", "/api/generate", payload)[0], 400)
        self.assertEqual(self.request("POST", "/api/generate", raw=b"no JSON")[0], 400)
        self.assertEqual(self.request("POST", "/api/generate", self.payload(), headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/generate", self.payload(), headers={"Content-Length": str(server.MAX_BODY + 1)})[0], 413)
        self.generator.assert_not_called()

    def test_only_one_request_at_a_time(self):
        release = threading.Event()
        entered = threading.Event()
        def generate(prompt, key):
            entered.set()
            release.wait(3)
            return music_payload()
        self.generator.side_effect = generate
        first = self.request("POST", "/api/generate", self.payload())[2]["job"]
        try:
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.request("GET", "/api/status")[2]["active_job"]["id"], first["id"])
            self.assertEqual(self.request("POST", "/api/generate", self.payload())[0], 409)
        finally:
            release.set()
        self.assertEqual(self.completed_job(first["id"])["status"], "completed")
        self.generator.assert_called_once()

    def test_failed_job_hides_exception_and_clears_active(self):
        self.generator.side_effect = RuntimeError(SECRET)
        first = self.request("POST", "/api/generate", self.payload())[2]["job"]
        failed = self.completed_job(first["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertNotIn(SECRET, json.dumps(failed))
        self.assertIn("No automatic retry", failed["error"])
        self.assertIsNone(self.request("GET", "/api/status")[2]["active_job"])
        self.assertEqual(self.request("GET", "/api/takes")[2]["takes"], [])
        self.generator.assert_called_once()

    def test_provider_failure_saved_privately_and_restored_without_prompt_or_key(self):
        provider_error = HTTPError(server.GOOGLE_ENDPOINT, 402, SECRET, {}, io.BytesIO(json.dumps({"error": {
            "message": "Prepaid credits exhausted for " + SECRET, "code": "payment_required",
            "details": [{"reason": "BILLING_DISABLED"}],
        }}).encode()))
        self.generator.side_effect = server.google_http_failure(provider_error, SECRET)
        first = self.request("POST", "/api/generate", self.payload())[2]["job"]
        failed = self.completed_job(first["id"])
        self.assertEqual(failed["error_details"]["http_status"], 402)
        self.assertEqual(failed["error_details"]["code"], "payment_required")
        self.assertEqual(self.workshop.status()["latest_failed_job"], failed)
        diagnostic = self.root / "auditions" / first["id"] / "failure.json"
        saved = diagnostic.read_text()
        self.assertNotIn(SECRET, saved)
        self.assertNotIn(self.payload()["prompt"], saved)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(diagnostic.stat().st_mode), 0o600)
        restored = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader)
        self.assertEqual(restored.get_job(first["id"]), failed)
        self.assertEqual(restored.status()["latest_failed_job"], failed)
        self.assertIsNone(restored.status()["active_job"])
        self.generator.assert_called_once()

    def test_success_hides_previous_failure_from_status_after_reload(self):
        self.generator.side_effect = server.WorkshopError("Google HTTP 503: Unavailable. No automatic retry was made.")
        first = self.request("POST", "/api/generate", self.payload())[2]["job"]
        self.assertEqual(self.completed_job(first["id"])["status"], "failed")
        self.generator.side_effect = None
        second = self.request("POST", "/api/generate", self.payload())[2]["job"]
        self.assertEqual(self.completed_job(second["id"])["status"], "completed")
        self.assertIsNone(self.workshop.status()["latest_failed_job"])
        restored = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader)
        self.assertIsNone(restored.status()["latest_failed_job"])
        self.assertEqual(restored.get_job(first["id"])["status"], "failed")

    def test_failure_storage_problem_preserves_original_diagnostic(self):
        self.generator.side_effect = server.WorkshopError("Google HTTP 402: Payment required. No automatic retry was made.")
        with patch.object(server, "write_private", side_effect=OSError(SECRET)):
            first = self.request("POST", "/api/generate", self.payload())[2]["job"]
            failed = self.completed_job(first["id"])
        self.assertIn("HTTP 402", failed["error"])
        self.assertFalse(failed["diagnostic_saved"])
        self.assertNotIn(SECRET, json.dumps(failed))

    def test_key_can_be_added_after_server_starts(self):
        self.key_reader.return_value = None
        self.assertFalse(self.request("GET", "/api/status")[2]["configured"])
        self.key_reader.return_value = "new-fixture-key"
        first = self.request("POST", "/api/generate", self.payload())[2]["job"]
        self.assertEqual(self.completed_job(first["id"])["status"], "completed")
        self.generator.assert_called_once_with(self.payload()["prompt"], "new-fixture-key")


if __name__ == "__main__":
    unittest.main()
