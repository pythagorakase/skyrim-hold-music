"""Offline contract and security checks. These tests never call Google."""

import base64
import errno
from copy import deepcopy
import hashlib
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
from tools import workshop_library as library


AUDIO = b"ID3\x04\x00\x00fixture-audio-data"
SECRET = "fixture-key-never-returned-to-browser"
ORIGINAL_LYRICS = "  First line, café\r\nSecond line\r\n\r\n  "
LYRIC_DIGEST = hashlib.sha256(ORIGINAL_LYRICS.encode("utf-8")).hexdigest()


def music_payload(audio=AUDIO, mime="audio/mpeg"):
    return {"status": "completed", "steps": [
        {"type": "model_output", "content": [{"type": "text", "text": "Verse one"}]},
        {"type": "model_output", "content": [{"type": "audio", "mime_type": mime, "data": base64.b64encode(audio).decode("ascii")}]},
    ]}


class StartupTests(unittest.TestCase):
    def test_occupied_port_reports_existing_address(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(server, "ROOT", Path(temporary)), \
                patch("sys.argv", ["workshop_server.py", "--port", "8765"]), \
                patch.object(server, "WorkshopServer", side_effect=OSError(errno.EADDRINUSE, "Address in use")), \
                patch("sys.stderr", new_callable=io.StringIO) as error:
            with self.assertRaises(SystemExit) as raised:
                server.main()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Port 8765 is already in use", error.getvalue())
        self.assertIn("http://127.0.0.1:8765/", error.getvalue())
        self.assertIn("instead of starting a second instance", error.getvalue())


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
        self.assertIn("endpoint supports the requested music model and settings", str(failure))
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
        self.catalog = {"songs": [{"id": "skyrim-song-1", "title": "Original song", "lyrics": ORIGINAL_LYRICS,
                                   "bard_name": "Fixture bard", "created_at": "2026-10-08T13:00:00Z", "sha256": LYRIC_DIGEST}],
                        "source": {"label": "Fixture SkyrimNet songs", "updated_at": "2026-10-08T15:00:00Z"}}
        self.catalog_reader = Mock(side_effect=lambda: deepcopy(self.catalog))
        self.workshop = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader, catalog_reader=self.catalog_reader)
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
        request_headers = {key: value for key, value in request_headers.items() if value is not None}
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
        payload = {"profile_id": "solo", "profile_name": "untrusted supplied name", "arrangement": "lute_voice", "prompt": "A quiet song with one lute", **overrides}
        if isinstance(payload["arrangement"], str) and payload["arrangement"] in server.SUNG_ARRANGEMENTS:
            payload.setdefault("lyrics_song_id", "skyrim-song-1")
            payload.setdefault("lyrics_sha256", LYRIC_DIGEST)
        return payload

    def expected_prompt(self, payload=None):
        payload = self.payload() if payload is None else payload
        if payload["arrangement"] in server.SUNG_ARRANGEMENTS:
            return payload["prompt"] + server.LYRICS_SEPARATOR + ORIGINAL_LYRICS
        return payload["prompt"]

    def seed_listening_study(self):
        """An offline two-take trial, plus AI controls and a missing recording."""
        identifiers = ["a" * 32, "b" * 32]
        for identifier in identifiers:
            folder = self.root / "auditions" / identifier
            folder.mkdir(parents=True)
            (folder / "audio.mp3").write_bytes(AUDIO)
            (folder / "take.json").write_text(json.dumps({
                "id": identifier, "profile_id": "solo", "profile_name": "Canonical solo",
                "arrangement": "lute_voice", "prompt": "Frozen fixture directions",
                "created_at": "2026-10-13T12:00:00Z", "lyrics": "", "model": "lyria-3.5", "mime_type": "audio/mpeg",
            }))
        directory = self.root / "local" / "listening-tests" / "2026-10-13-fixture"
        directory.mkdir(parents=True)
        (directory / "palette-snapshot.json").write_text(json.dumps(self.workshop.palette))
        (directory / "manifest.json").write_text(json.dumps({
            "corpus": {"solo_1": {"take_id": identifiers[0], "profile_id": "solo"},
                       "solo_2": {"take_id": identifiers[1], "profile_id": "solo"}},
            "trials": [{"id": "s01", "kind": "repeatability", "audio_ids": ["solo_1", "solo_2"]},
                       {"id": "x01", "kind": "reversed", "audio_ids": ["solo_2", "solo_1"]},
                       {"id": "x02", "kind": "duplicate", "audio_ids": ["solo_1", "solo_1"]}],
            "excluded_conditions": [{"id": "s02", "kind": "repeatability", "audio_ids": ["solo_1", "solo_3"]}],
        }))
        return identifiers

    def test_live_inventory_discovers_batch_and_marks_version_honestly(self):
        self.assertEqual(self.request("GET", "/api/takes")[2]["takes"], [])
        self.seed_listening_study()
        takes = self.request("GET", "/api/takes")[2]["takes"]
        self.assertEqual(len(takes), 2)
        self.assertEqual({t["prompt_status"]["state"] for t in takes}, {"current"})
        # A rebuild with the same named revision still invalidates old recipes.
        palette = deepcopy(self.workshop.palette)
        palette["finalists"][0]["voice"] = "A new vocal approach"
        (self.root / "dashboard" / "palette-data.json").write_text(json.dumps(palette))
        takes = self.request("GET", "/api/takes")[2]["takes"]
        self.assertEqual({t["prompt_status"]["state"] for t in takes}, {"obsolete"})
        self.generator.assert_not_called()

    def seed_neighbor_study(self):
        ids = self.seed_listening_study() + ["c" * 32, "d" * 32]
        for identifier in ids[2:]:
            folder = self.root / "auditions" / identifier
            folder.mkdir()
            take = json.loads((self.root / "auditions" / ids[0] / "take.json").read_text())
            take.update(id=identifier, profile_id="ensemble", profile_name="Canonical ensemble")
            (folder / "take.json").write_text(json.dumps(take))
            (folder / "audio.mp3").write_bytes(AUDIO)
        path = self.root / "local/listening-tests/2026-10-13-fixture/manifest.json"
        manifest = json.loads(path.read_text())
        manifest["excluded_conditions"] = []
        manifest["trials"].extend([
            {"id": "s02", "kind": "repeatability", "audio_ids": ["ensemble_1", "ensemble_2"]},
            {"id": "n01", "kind": "neighbor", "audio_ids": ["solo_1", "ensemble_1"]},
        ])
        for identifier, profile, replicate in zip(ids, ["solo", "solo", "ensemble", "ensemble"], [1, 2, 1, 2]):
            manifest["corpus"][f"{profile}_{replicate}"] = {"take_id": identifier, "profile_id": profile,
                "replicate": replicate, "lyric_id": "workroom" if replicate == 1 else "cart", "vocal_mode": "lyrics"}
        path.write_text(json.dumps(manifest))
        return ids, path

    def test_neighbor_expands_to_four_exact_batch_takes_without_rewriting_pair_review(self):
        ids, _ = self.seed_neighbor_study()
        pair_version = library.digest({"ids": [ids[0], ids[2]],
            "prompts": ["Frozen fixture directions"] * 2,
            "recipes": [library.recipe_fingerprint(self.workshop.profiles[p], self.workshop.palette) for p in ["solo", "ensemble"]]})
        identifier = "2026-10-13-fixture:n01"
        prior = {"version": pair_version, "take_ids": [ids[0], ids[2]], "outcome": "distinct",
                 "preference": "a", "notes": "Initial pair only; might be a fluke.", "saved_at": "2026-10-13T15:00:00Z", "history": []}
        review_path = self.root / "auditions/listening-reviews.json"
        review_path.write_text(json.dumps({identifier: prior}))
        original_bytes = review_path.read_bytes()
        comparison = next(c for c in self.workshop.listening()["comparisons"] if c["kind"] == "neighbor")
        self.assertEqual(comparison["evidence_take_ids"], ids)
        self.assertEqual([len(g["samples"]) for g in comparison["groups"]], [2, 2])
        self.assertEqual([s["lyric_id"] for s in comparison["groups"][0]["samples"]], ["workroom", "cart"])
        self.assertIsNone(comparison["review"])
        self.assertEqual(comparison["previous_review_scope"], "pair")
        self.assertEqual(comparison["previous_review"], prior)
        self.assertEqual(comparison["state"], "pending")
        self.assertEqual(review_path.read_bytes(), original_bytes)
        payload = {"id": identifier, "version": pair_version, "outcome": "distinct", "preference": "both"}
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 409)
        payload["version"] = comparison["version"]
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 400)
        payload["consistency"] = {"a": "consistent", "b": "inconsistent"}
        review = self.request("POST", "/api/listening/review", payload)[2]["review"]
        self.assertEqual(review["take_ids"], ids)
        self.assertEqual(review["scope"], "all_style_takes")
        self.assertEqual(review["history"], [{k: v for k, v in prior.items() if k != "history"}])
        restored = server.Workshop(self.root, key_reader=lambda: None)
        current = next(c for c in restored.listening()["comparisons"] if c["kind"] == "neighbor")
        self.assertEqual(current["state"], "reviewed")
        self.assertEqual(current["review"]["consistency"], payload["consistency"])
        payload["consistency"]["a"] = "uncertain"
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 200)
        self.assertEqual(next(c for c in self.workshop.listening()["comparisons"] if c["kind"] == "neighbor")["state"], "revisit")
        self.generator.assert_not_called()

    def test_missing_second_take_blocks_expanded_review_and_restore_recovers_it(self):
        ids, _ = self.seed_neighbor_study()
        comparison = next(c for c in self.workshop.listening()["comparisons"] if c["kind"] == "neighbor")
        payload = {"id": comparison["id"], "version": comparison["version"], "outcome": "distinct", "preference": "both",
                   "consistency": {"a": "consistent", "b": "consistent"}}
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 200)
        self.assertEqual(self.request("POST", f"/api/takes/{ids[1]}/trash", {})[0], 200)
        missing = next(c for c in self.workshop.listening()["comparisons"] if c["kind"] == "neighbor")
        self.assertEqual(missing["state"], "waiting")
        self.assertEqual(missing["missing"], ["solo_2"])
        self.assertEqual(len(missing["evidence_take_ids"]), 4)
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 409)
        self.assertEqual(self.request("POST", f"/api/takes/{ids[1]}/restore", {})[0], 200)
        restored = next(c for c in self.workshop.listening()["comparisons"] if c["kind"] == "neighbor")
        self.assertEqual(restored["state"], "reviewed")
        # A modification to the extra recording invalidates the whole comparison.
        path = self.root / "auditions" / ids[1] / "take.json"
        take = json.loads(path.read_text()); take["prompt"] = "Changed second take directions"; path.write_text(json.dumps(take))
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 409)
        self.generator.assert_not_called()

    def test_failed_sample_keeps_its_slot_and_unrelated_library_takes_are_excluded(self):
        ids, path = self.seed_neighbor_study()
        manifest = json.loads(path.read_text()); del manifest["corpus"]["solo_2"]; path.write_text(json.dumps(manifest))
        # solo_2 still exists in the library; the batch manifest declares no successful sample.
        comparison = next(c for c in self.workshop.listening()["comparisons"] if c["kind"] == "neighbor")
        self.assertEqual(comparison["evidence_take_ids"], [ids[0], None, ids[2], ids[3]])
        self.assertEqual(comparison["missing"], ["solo_2"])
        self.assertEqual(comparison["state"], "waiting")
        self.generator.assert_not_called()

    def test_review_is_durable_and_bound_to_exact_pair_and_recipe(self):
        ids = self.seed_listening_study()
        queue = self.request("GET", "/api/listening")[2]
        self.assertEqual(len(queue["comparisons"]), 2)  # no reversed or duplicate chores
        comparison = queue["comparisons"][0]
        self.assertEqual(comparison["take_ids"], ids)
        self.assertEqual(queue["comparisons"][1]["state"], "waiting")
        payload = {"id": comparison["id"], "version": comparison["version"], "outcome": "consistent", "preference": "a", "notes": "Fixture listening only"}
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 200)
        restored = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader)
        reviewed = restored.listening()["comparisons"][0]
        self.assertEqual(reviewed["state"], "reviewed")
        self.assertEqual(reviewed["review"]["notes"], payload["notes"])
        # Missing recordings cannot inherit a saved result, and restoring retains it.
        self.assertEqual(self.request("POST", f"/api/takes/{ids[0]}/trash", {})[0], 200)
        self.assertEqual(self.request("GET", "/api/listening")[2]["comparisons"][0]["state"], "waiting")
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 409)
        self.assertEqual(self.request("POST", f"/api/takes/{ids[0]}/restore", {})[0], 200)
        self.assertEqual(self.request("GET", "/api/listening")[2]["comparisons"][0]["state"], "reviewed")
        self.workshop.profiles["solo"]["voice"] = "Changed recipe"
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 409)
        changed = self.request("GET", "/api/listening")[2]["comparisons"][0]
        self.assertEqual(changed["state"], "obsolete")
        self.assertEqual(changed["previous_review"]["notes"], payload["notes"])
        self.generator.assert_not_called()

    def test_trash_restore_preserves_all_original_bytes_and_is_restart_safe(self):
        ids = self.seed_listening_study()
        folder = self.root / "auditions" / ids[0]
        originals = {p.name: p.read_bytes() for p in folder.iterdir()}
        self.request("GET", "/api/takes")
        self.assertEqual(self.request("POST", f"/api/takes/{ids[0]}/trash", {})[0], 200)
        self.assertFalse(folder.exists())
        self.assertEqual(self.request("GET", f"/api/takes/{ids[0]}/audio")[0], 404)
        self.assertEqual(len(self.request("GET", "/api/takes")[2]["takes"]), 1)
        restored = server.Workshop(self.root, key_reader=lambda: None)
        self.assertEqual(restored.trash_takes()[0]["id"], ids[0])
        restored.move_take(ids[0], restore=True)
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, originals)
        self.assertEqual(len(self.request("GET", "/api/takes")[2]["takes"]), 2)
        self.generator.assert_not_called()

    def test_mutations_require_same_origin_token_and_reject_path_traversal(self):
        ids = self.seed_listening_study()
        for path in (f"/api/takes/{ids[0]}/trash", f"/api/takes/{ids[0]}/restore", "/api/listening/review"):
            self.assertEqual(self.request("POST", path, {}, headers={"X-Workshop-Token": None})[0], 403)
            self.assertEqual(self.request("POST", path, {}, headers={"Origin": "https://evil.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/takes/../trash", {})[0], 404)
        self.assertTrue((self.root / "auditions" / ids[0]).exists())
        self.assertEqual((self.root / "secret.txt").read_text(), SECRET)
        self.generator.assert_not_called()

    def test_mutations_reject_real_symlink_inside_take_directory(self):
        ids = self.seed_listening_study()
        folder = self.root / "auditions" / ids[0]
        try:
            (folder / "linked-secret").symlink_to(self.root / "secret.txt")
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows account lacks the privilege to create symlinks")
            raise
        self.assertEqual(self.request("POST", f"/api/takes/{ids[0]}/trash", {})[0], 409)
        self.assertTrue(folder.exists())
        self.assertEqual((self.root / "secret.txt").read_text(), SECRET)
        self.generator.assert_not_called()

    def test_unknown_versions_are_not_invented_and_generation_records_fingerprint(self):
        ids = self.seed_listening_study()
        snapshot = self.root / "local/listening-tests/2026-10-13-fixture/palette-snapshot.json"
        snapshot.unlink()
        self.assertEqual(self.request("GET", "/api/takes")[2]["takes"][0]["prompt_status"]["state"], "unknown")
        result = self.request("POST", "/api/generate", self.payload(direction_draft="quiet song"))[2]
        take = self.completed_job(result["job"]["id"])["take"]
        self.assertEqual(len(take["recipe_fingerprint"]), 64)
        self.assertEqual(take["direction_draft"], "quiet song")
        self.assertEqual(take["prompt_status"]["state"], "current")
        self.assertEqual(self.request("POST", "/api/generate", self.payload(direction_draft="not part of the prompt"))[0], 400)

    def test_invalid_reviews_do_not_destroy_existing_notes(self):
        self.seed_listening_study()
        comparison = self.workshop.listening()["comparisons"][0]
        payload = {"id": comparison["id"], "version": comparison["version"], "outcome": "consistent", "preference": "both", "notes": "First opinion"}
        self.request("POST", "/api/listening/review", payload)
        payload["notes"] = "Revised opinion"
        saved = self.request("POST", "/api/listening/review", payload)[2]["review"]
        self.assertEqual(saved["history"][0]["notes"], "First opinion")
        payload["outcome"] = "distinct"  # wrong kind of result for a repeatability test
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 400)
        path = self.root / "auditions/listening-reviews.json"
        path.write_text("incomplete fixture")
        payload["outcome"] = "consistent"
        self.assertEqual(self.request("POST", "/api/listening/review", payload)[0], 409)
        self.assertEqual(path.read_text(), "incomplete fixture")

    def test_omitted_recipe_arrangements_reject_even_with_another_race_or_custom_prompt(self):
        profile = self.workshop.profiles["solo"]
        profile["workshop"] = {"allowed": ["lute", "flute"],
                               "omitted": {key: "This recipe is instrumental only." for key in server.ARRANGEMENTS - {"lute", "flute"}}}
        for arrangement in server.ARRANGEMENTS - {"lute", "flute"}:
            status, _, content = self.request("POST", "/api/generate", self.payload(arrangement=arrangement, performer_race="nord", prompt="A custom direction"))
            self.assertEqual(status, 400)
            self.assertIn("instrumental only", content["error"])
        self.generator.assert_not_called()
        self.catalog_reader.assert_not_called()
        self.key_reader.assert_not_called()
        self.assertEqual(self.workshop.jobs, {})

    def test_beastfolk_casting_disallows_all_sung_arrangements_on_other_repertoire(self):
        for race in ("khajiit", "argonian"):
            for arrangement in server.SUNG_ARRANGEMENTS:
                status, _, content = self.request("POST", "/api/generate", self.payload(arrangement=arrangement, performer_race=race))
                self.assertEqual(status, 400)
                self.assertIn("instrumental only", content["error"])
        for race in ("unknown", "", [], None):
            status, _, content = self.request("POST", "/api/generate", self.payload(performer_race=race))
            self.assertEqual(status, 400)
            self.assertIn("known performer race", content["error"])
        self.generator.assert_not_called()
        self.key_reader.assert_not_called()

    def test_instrumental_direction_cannot_include_inline_lyrics(self):
        status, _, content = self.request("POST", "/api/generate", self.payload(arrangement="lute", performer_race="khajiit", prompt="A sitar tune.\nLyrics:\nSing these words"))
        self.assertEqual(status, 400)
        self.assertIn("Lyrics: block", content["error"])
        self.generator.assert_not_called()

    def test_baseline_gate_rejects_deferred_profiles_and_arrangements_before_provider_access(self):
        palette = json.loads((server.ROOT / "dashboard" / "palette-data.json").read_text(encoding="utf-8"))
        profiles = palette["finalists"] + palette["existing"] + palette["comparisons"]
        self.workshop.profiles.update({p["id"]: p for p in profiles})
        for profile in profiles:
            for arrangement in server.ARRANGEMENTS:
                if profile["audition"].get("arrangement") == arrangement:
                    continue
                with self.subTest(profile=profile["id"], arrangement=arrangement):
                    status, _, response = self.request("POST", "/api/generate", self.payload(
                        profile_id=profile["id"], arrangement=arrangement, prompt="Custom direction"))
                    self.assertEqual(status, 400)
                    self.assertIn("listening", response["error"])
        self.generator.assert_not_called()
        self.key_reader.assert_not_called()
        self.catalog_reader.assert_not_called()

    def test_wordless_baseline_rejects_saved_and_inline_lyrics(self):
        palette = json.loads((server.ROOT / "dashboard" / "palette-data.json").read_text(encoding="utf-8"))
        self.workshop.profiles["winterhold"] = next(p for p in palette["existing"] if p["id"] == "winterhold")
        for extra in ({"lyrics_song_id": "skyrim-song-1", "lyrics_sha256": LYRIC_DIGEST}, {"prompt": "A joik.\nLyrics:\nNot vocables"}):
            payload = {"profile_id": "winterhold", "arrangement": "lute_voice", "prompt": "A joik.", **extra}
            status, _, response = self.request("POST", "/api/generate", payload)
            self.assertEqual(status, 400)
            self.assertIn("wordless", response["error"])
        self.generator.assert_not_called()
        self.key_reader.assert_not_called()
        self.catalog_reader.assert_not_called()

    def test_admitted_reach_comparison_saves_baseline_provenance(self):
        palette = json.loads((server.ROOT / "dashboard" / "palette-data.json").read_text(encoding="utf-8"))
        profile = palette["comparisons"][0]
        self.workshop.profiles[profile["id"]] = profile
        payload = self.payload(profile_id=profile["id"], prompt="An English sean-nós air on one lute.")
        status, _, response = self.request("POST", "/api/generate", payload)
        self.assertEqual(status, 202)
        take = self.completed_job(response["job"]["id"])["take"]
        self.assertEqual(take["recipe_revision"], palette["baseline"]["revision"])
        self.assertEqual(take["audition_stage"], "comparison")
        self.assertEqual(take["vocal_mode"], "lyrics")
        self.assertEqual(take["prompt"], self.expected_prompt(payload))
        reloaded = server.Workshop(self.root, key_reader=lambda: None)
        self.assertEqual(reloaded.list_takes()[0]["recipe_revision"], palette["baseline"]["revision"])

    def test_wordless_preview_is_submitted_verbatim_and_provenance_survives(self):
        palette = json.loads((server.ROOT / "dashboard" / "palette-data.json").read_text(encoding="utf-8"))
        self.workshop.profiles["winterhold"] = next(p for p in palette["existing"] if p["id"] == "winterhold")
        prompt = "One singer and lute.\nWordless vocables only; no lyrics, sentences or spoken words."
        payload = self.payload(profile_id="winterhold", prompt=prompt)
        payload.pop("lyrics_song_id")
        payload.pop("lyrics_sha256")
        status, _, response = self.request("POST", "/api/generate", payload)
        self.assertEqual(status, 202)
        take = self.completed_job(response["job"]["id"])["take"]
        self.assertEqual(take["prompt"], prompt)
        self.assertEqual(take["vocal_mode"], "wordless")
        self.assertNotIn("supplied_lyrics", take)
        self.catalog_reader.assert_not_called()
        self.generator.assert_called_once_with(prompt, SECRET)

    def test_instrumental_take_keeps_actual_instrument_and_race_across_reload(self):
        self.workshop.profiles["solo"]["workshop"] = {"allowed": ["lute"], "plucked": "cittern", "flute": "flute", "drum": "hand drum", "omitted": {}}
        payload = self.payload(arrangement="lute", performer_race="khajiit")
        status, _, response = self.request("POST", "/api/generate", payload)
        self.assertEqual(status, 202)
        job = self.completed_job(response["job"]["id"])
        self.assertEqual(job["status"], "completed")
        take = job["take"]
        self.assertEqual(take["instrument_name"], "cittern")
        self.assertEqual(take["performer_race"], "khajiit")
        self.generator.assert_called_once_with(payload["prompt"], SECRET)
        self.catalog_reader.assert_not_called()
        restored = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader)
        self.assertEqual(restored.list_takes()[0]["instrument_name"], "cittern")
        self.assertEqual(restored.list_takes()[0]["performer_race"], "khajiit")

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
        self.catalog["songs"][0]["collection"] = "Archived SkyrimNet songs"
        status, _, content = self.request("POST", "/api/generate", self.payload())
        self.assertEqual(status, 202)
        self.assertEqual(content["job"]["status"], "queued")
        job = self.completed_job(content["job"]["id"])
        self.assertEqual(job["status"], "completed")
        take = job["take"]
        self.assertEqual(take["profile_name"], "Canonical solo")
        self.assertEqual(take["prompt"], self.expected_prompt())
        self.assertEqual(take["direction_prompt"], self.payload()["prompt"])
        self.assertEqual(take["supplied_lyrics"], ORIGINAL_LYRICS)
        self.assertEqual(take["lyric_source"], {"id": "skyrim-song-1", "title": "Original song", "bard_name": "Fixture bard",
                                               "created_at": "2026-10-08T13:00:00Z", "sha256": LYRIC_DIGEST,
                                               "source_label": "Archived SkyrimNet songs", "collection": "Archived SkyrimNet songs"})
        self.assertEqual(take["lyrics"], "Verse one")
        self.generator.assert_called_once_with(self.expected_prompt(), SECRET)
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

    def test_external_link_can_open_dashboard_but_not_api_or_embedded_content(self):
        navigation = {"Origin": None, "Sec-Fetch-Site": "cross-site",
                      "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
        for site in ("cross-site", "same-site"):
            for path in ("/", "/index.html"):
                status, headers, body = self.request("GET", path, headers={**navigation, "Sec-Fetch-Site": site})
                self.assertEqual(status, 200)
                self.assertIn(b"Workshop fixture", body)
                self.assertEqual(headers["X-Frame-Options"], "DENY")
        for path in ("/api/status", "/api/takes", "/api/lyrics"):
            self.assertEqual(self.request("GET", path, headers=navigation)[0], 403)
        for overrides in ({"Sec-Fetch-Mode": "cors"}, {"Sec-Fetch-Dest": "iframe"},
                          {"Origin": "https://evil.invalid"}, {"Host": "evil.invalid"}):
            self.assertEqual(self.request("GET", "/", headers={**navigation, **overrides})[0], 403)
        self.assertEqual(self.request("POST", "/api/generate", self.payload(), headers=navigation)[0], 403)
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
        self.generator.assert_called_once_with(self.expected_prompt(), "new-fixture-key")

    def test_lyrics_route_reads_current_catalog_without_provider_call(self):
        status, _, catalog = self.request("GET", "/api/lyrics")
        self.assertEqual(status, 200)
        self.assertEqual(catalog, self.catalog)
        self.assertEqual(catalog["songs"][0]["lyrics"].encode("utf-8"), ORIGINAL_LYRICS.encode("utf-8"))
        self.catalog["source"]["updated_at"] = "2026-10-08T16:00:00Z"
        self.assertEqual(self.request("GET", "/api/lyrics")[2], self.catalog)
        self.assertEqual(self.request("GET", "/api/lyrics", headers={"Origin": "https://evil.invalid"})[0], 403)
        self.assertEqual(self.catalog_reader.call_count, 2)
        self.generator.assert_not_called()

    def test_original_lyrics_are_forwarded_verbatim_in_all_sung_arrangements(self):
        for arrangement in sorted(server.SUNG_ARRANGEMENTS):
            payload = self.payload(arrangement=arrangement, profile_id="ensemble" if arrangement == "trio" else "solo",
                                   prompt="  Detailed musical directions\r\nwith a trailing line.\n")
            status, _, result = self.request("POST", "/api/generate", payload)
            self.assertEqual(status, 202)
            take = self.completed_job(result["job"]["id"])["take"]
            expected = self.expected_prompt(payload)
            self.assertEqual(self.generator.call_args.args[0].encode("utf-8"), expected.encode("utf-8"))
            self.assertEqual(take["supplied_lyrics"].encode("utf-8"), ORIGINAL_LYRICS.encode("utf-8"))
            self.assertEqual(take["direction_prompt"], payload["prompt"])
            self.assertEqual(take["prompt"], expected)
        self.assertEqual(self.generator.call_count, len(server.SUNG_ARRANGEMENTS))

    def test_missing_unknown_and_stale_lyric_selection_prevent_provider_calls(self):
        for field in ("lyrics_song_id", "lyrics_sha256"):
            missing = self.payload()
            missing.pop(field)
            self.assertEqual(self.request("POST", "/api/generate", missing)[0], 400)
        for payload, status in ((self.payload(lyrics_song_id="missing-song"), 409),
                                (self.payload(lyrics_sha256="stale-digest"), 409),
                                (self.payload(lyrics_song_id=[]), 400),
                                (self.payload(lyrics_sha256=[]), 400),
                                (self.payload(supplied_lyrics="replacement"), 400)):
            self.assertEqual(self.request("POST", "/api/generate", payload)[0], status)
        self.assertEqual(self.workshop.jobs, {})
        self.generator.assert_not_called()

    def test_sung_takes_without_saved_lyrics_work_without_reading_catalog(self):
        self.catalog_reader.side_effect = AssertionError("Optional lyrics must not read the catalog")
        for arrangement in sorted(server.SUNG_ARRANGEMENTS):
            directions = "A quiet song\n\nLyrics:\nMy own words\r\n\r\n" if arrangement == "voice" else "A quiet song"
            payload = self.payload(arrangement=arrangement, profile_id="ensemble" if arrangement == "trio" else "solo", prompt=directions)
            payload.pop("lyrics_song_id")
            payload.pop("lyrics_sha256")
            status, _, result = self.request("POST", "/api/generate", payload)
            self.assertEqual(status, 202)
            take = self.completed_job(result["job"]["id"])["take"]
            self.assertEqual(self.generator.call_args.args[0], directions)
            self.assertEqual(take["prompt"], directions)
            self.assertNotIn("supplied_lyrics", take)
            self.assertNotIn("lyric_source", take)
        self.catalog_reader.assert_not_called()

    def test_catalog_changes_are_checked_again_at_submit(self):
        self.assertEqual(self.request("GET", "/api/lyrics")[2]["songs"][0]["sha256"], LYRIC_DIGEST)
        self.catalog["songs"][0]["lyrics"] = "Changed words"
        self.catalog["songs"][0]["sha256"] = hashlib.sha256(b"Changed words").hexdigest()
        status, _, result = self.request("POST", "/api/generate", self.payload())
        self.assertEqual(status, 409)
        self.assertIn("changed", result["error"])
        self.generator.assert_not_called()

    def test_empty_unavailable_and_malformed_catalogs_fail_closed(self):
        for catalog in ({"songs": [], "source": {}}, {"songs": [], "source": {}, "error": "source unavailable"},
                        {"songs": "invalid", "source": {}}, {"songs": [{"id": "skyrim-song-1", "sha256": LYRIC_DIGEST}], "source": {}}):
            self.catalog = catalog
            self.assertEqual(self.request("POST", "/api/generate", self.payload())[0], 503)
        self.catalog_reader.side_effect = OSError(SECRET)
        status, _, catalog = self.request("GET", "/api/lyrics")
        self.assertEqual(status, 200)
        self.assertEqual(catalog["songs"], [])
        self.assertNotIn(SECRET, json.dumps(catalog))
        self.assertEqual(self.request("POST", "/api/generate", self.payload())[0], 503)
        self.generator.assert_not_called()

    def test_inline_lyrics_blocks_and_oversize_combined_prompt_refused(self):
        for prompt in ("Directions\nLyrics:\nconflicting lyrics", "Lyrics: words", "Style\r\n \tlyRICS \t: same words"):
            status, _, content = self.request("POST", "/api/generate", self.payload(prompt=prompt))
            self.assertEqual(status, 400)
            self.assertIn("Remove the Lyrics:", content["error"])
        directions = "x" * (server.MAX_PROMPT - len(server.LYRICS_SEPARATOR) - len(ORIGINAL_LYRICS) + 1)
        status, _, content = self.request("POST", "/api/generate", self.payload(prompt=directions))
        self.assertEqual(status, 400)
        self.assertIn("together", content["error"])
        self.generator.assert_not_called()

    def test_instrumentals_omit_lyric_source_and_do_not_need_catalog(self):
        self.catalog_reader.side_effect = AssertionError("Instrumental must not read lyrics")
        for arrangement in ("lute", "flute", "drum"):
            payload = self.payload(arrangement=arrangement)
            status, _, result = self.request("POST", "/api/generate", payload)
            self.assertEqual(status, 202)
            take = self.completed_job(result["job"]["id"])["take"]
            self.assertEqual(self.generator.call_args.args[0], payload["prompt"])
            self.assertEqual(take["direction_prompt"], payload["prompt"])
            self.assertNotIn("lyric_source", take)
            self.assertNotIn("supplied_lyrics", take)
        self.catalog_reader.assert_not_called()

    def test_instrumentals_reject_stale_or_supplied_lyric_fields(self):
        for field, value in (("lyrics_song_id", "skyrim-song-1"), ("lyrics_sha256", LYRIC_DIGEST), ("supplied_lyrics", "words")):
            self.assertEqual(self.request("POST", "/api/generate", self.payload(arrangement="lute", **{field: value}))[0], 400)
        self.generator.assert_not_called()

    def test_saved_takes_without_new_lyric_metadata_remain_readable(self):
        identifier = "a" * 32
        directory = self.root / "auditions" / identifier
        directory.mkdir(parents=True)
        old = {"id": identifier, "profile_id": "solo", "profile_name": "Old take", "arrangement": "lute_voice",
               "prompt": "An old generated song", "model": "lyria-3.5", "created_at": "2026-10-08T00:00:00Z",
               "lyrics": "Previously generated lyrics", "mime_type": "audio/mpeg"}
        (directory / "audio.mp3").write_bytes(AUDIO)
        (directory / "take.json").write_text(json.dumps(old), encoding="utf-8")
        restored = server.Workshop(self.root, generator=self.generator, key_reader=self.key_reader, catalog_reader=self.catalog_reader)
        take = restored.list_takes()[0]
        self.assertEqual(take["prompt"], old["prompt"])
        self.assertNotIn("lyric_source", take)
        self.assertNotIn("supplied_lyrics", take)
        self.generator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
