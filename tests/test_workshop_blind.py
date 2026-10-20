"""Offline blind-session contracts. Every provider response is synthetic."""

import base64
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import io
import json
from pathlib import Path
import random
import secrets
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from tools import workshop_blind as blind
from tools import workshop_server as server
from tools import seed_blind_clips


def music(audio=b"ID3 synthetic clip", lyrics="Provider lyrics must stay hidden"):
    return {"status": "completed", "steps": [{"type": "model_output", "content": [
        {"type": "text", "text": lyrics},
        {"type": "audio", "mime_type": "audio/mpeg", "data": base64.b64encode(audio).decode()},
    ]}]}


def profile(identifier, *, stage="baseline", arrangement="lute_voice", vocal_mode="lyrics"):
    return {"id": identifier, "name": "Style " + identifier, "reference": "Reference " + identifier,
            "core": "Contrasting phrases " + identifier, "core_instrumental": "Melody " + identifier,
            "core_instrumental_monophonic": "One line " + identifier,
            "voice": "Clear solo singing", "lute": "Plucked phrase answers", "lute_instrumental": "Plucked melody",
            "flute": "A single melody", "flute_instrumental": "Successive neighboring notes",
            "workshop": {"allowed": ["lute_voice", "lute", "flute"], "plucked": "kantele", "flute": "recorder",
                         "family_rules": {"plucked": "No bowed strings.", "flute": "No reed-driven sound."}},
            "audition": {"stage": stage, "arrangement": arrangement, "vocal_mode": vocal_mode, "revision": "fixture-v1"}}


class BlindHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "dashboard").mkdir()
        (self.root / "dashboard/index.html").write_text("<!doctype html><title>Fixture</title>")
        self.palette = {"baseline": {"revision": "fixture-v1", "profiles": ["alpha", "beta", "gamma"], "comparisons": ["challenger"]},
                        "existing": [profile("alpha"), profile("beta", vocal_mode="wordless"), profile("gamma", arrangement="lute", vocal_mode="instrumental")],
                        "comparisons": [profile("challenger", stage="comparison")], "finalists": [profile("deferred", stage="deferred")]}
        self.save_palette()
        self.generator = Mock(side_effect=lambda *a, **kw: music(b"ID3 " + secrets.token_bytes(12)))
        self.workshop = self.new_workshop()
        self.http = server.WorkshopServer(port=0, workshop=self.workshop)
        self.thread = threading.Thread(target=self.http.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(1)
        self.temporary.cleanup()

    def save_palette(self):
        (self.root / "dashboard/palette-data.json").write_text(json.dumps(self.palette))

    def new_workshop(self):
        return server.Workshop(self.root, generator=self.generator, key_reader=lambda: "synthetic-secret")

    def request(self, method, path, payload=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=3)
        request_headers = {"Origin": f"http://127.0.0.1:{self.http.server_port}"}
        if method == "POST":
            request_headers.update({"Content-Type": "application/json", "X-Workshop-Token": self.workshop.token})
        request_headers.update(headers or {})
        connection.request(method, path, body=json.dumps(payload).encode() if payload is not None else None, headers=request_headers)
        response = connection.getresponse()
        content = response.read()
        result = json.loads(content) if content and response.getheader("Content-Type", "").startswith("application/json") else content
        status = response.status
        connection.close()
        return status, result

    def create(self, **changes):
        status, result = self.request("POST", "/api/blind/sessions", {"mode": "canonical", "size": 2, **changes})
        self.assertEqual(status, 200, result)
        return result["session"]

    def start(self, session, request_id=None):
        payload = {"request_id": request_id or secrets.token_hex(16), "generate": True}
        status, result = self.request("POST", "/api/blind/sessions/" + session["id"] + "/next", payload)
        self.assertEqual(status, 200, result)
        return result["session"]

    def wait(self, session):
        for _ in range(200):
            result = self.workshop.blind.get(session["id"])
            if result["current_trial"]["status"] in ("ready", "failed"):
                return result
            time.sleep(.005)
        self.fail("Synthetic clip did not finish")

    def answer(self, session, guess="unsure"):
        status, result = self.request("POST", "/api/blind/trials/" + session["current_trial"]["id"] + "/guess", {"guess": guess})
        self.assertEqual(status, 200, result)
        return result["session"]

    def test_no_cost_plans_active_modes_and_balance_persist_across_sessions(self):
        for _ in range(4):
            self.create(size=5)
        counts = Counter(target for s in self.workshop.blind.sessions.values() for target in s["plan"])
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
        self.assertEqual(set(counts), {"alpha", "beta", "gamma"})
        restored = self.new_workshop()
        restored.blind.create({"mode": "canonical", "size": 4})
        counts = Counter(target for s in restored.blind.sessions.values() for target in s["plan"])
        self.assertEqual(len(set(counts.values())), 1)
        catalog = self.request("GET", "/api/blind")[1]
        self.assertEqual(len(catalog["sessions"]), 4)
        self.assertEqual(set(catalog["modes"][0]["choice_ids"]), {"alpha", "beta", "gamma", "challenger"})
        self.assertEqual(len(self.create(include_challenger=True)["choices"]), 4)
        self.generator.assert_not_called()

    def test_hidden_metadata_never_enters_regular_routes_and_reveals_after_guess(self):
        session = self.wait(self.start(self.create(size=1)))
        trial = session["current_trial"]
        self.assertEqual(set(trial), {"id", "status", "audio_url", "listened", "choices", "presentation_contract"})
        self.assertEqual(self.request("GET", "/api/takes")[1], {"takes": []})
        self.assertEqual(self.request("GET", "/api/trash")[1], {"takes": []})
        job = self.request("GET", "/api/jobs/" + trial["id"])[1]["job"]
        self.assertEqual(set(job), {"id", "status", "kind"})
        self.assertNotIn("Reference", json.dumps(self.request("GET", "/api/status")[1]))
        status, audio = self.request("GET", trial["audio_url"], headers={"Range": "bytes=0-2"})
        self.assertEqual((status, audio), (206, b"ID3"))
        answered = self.answer(session)
        reveal = answered["current_trial"]["reveal"]
        self.assertIn("Reference", reveal["prompt"])
        self.assertEqual(reveal["model"], blind.MODEL)
        self.assertEqual(reveal["lyrics"], "Provider lyrics must stay hidden")
        self.assertTrue(answered["finished"])
        self.assertEqual(self.workshop.blind.catalog()["active_session"], answered)
        self.assertEqual(self.new_workshop().blind.get(session["id"]), answered)
        self.assertEqual(self.generator.call_args.kwargs, {"model": blind.MODEL})

    def test_durable_request_receipt_and_global_generation_lock(self):
        entered, release = threading.Event(), threading.Event()
        def generate(*args, **kwargs):
            entered.set()
            release.wait(3)
            return music()
        self.generator.side_effect = generate
        session, receipt = self.create(), secrets.token_hex(16)
        try:
            started = self.start(session, receipt)
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.start(session, receipt)["current_trial"]["id"], started["current_trial"]["id"])
            self.assertEqual(self.request("POST", "/api/blind/sessions/" + self.create()["id"] + "/next", {"request_id": secrets.token_hex(16), "generate": True})[0], 409)
            self.assertEqual(self.request("POST", "/api/generate", {"profile_id": "alpha", "arrangement": "lute_voice", "prompt": "test"})[0], 409)
            self.assertNotIn("profile_id", self.workshop.status()["active_job"])
            persisted = json.loads((self.root / "auditions/.blind/sessions" / (session["id"] + ".json")).read_text())
            self.assertIn(receipt, persisted["requests"])
        finally:
            release.set()
        done = self.wait(started)
        self.start(session, receipt)
        answered = self.answer(done)
        self.start(answered, receipt)
        self.generator.assert_called_once()

    def test_first_guess_is_immutable_unsure_counts_and_reaction_is_separate(self):
        session = self.wait(self.start(self.create(size=1)))
        answered = self.answer(session)
        trial = answered["current_trial"]
        self.assertEqual(self.answer(answered), answered)
        self.assertEqual(self.request("POST", "/api/blind/trials/" + trial["id"] + "/guess", {"guess": "alpha"})[0], 409)
        stats = self.workshop.blind.stats()["groups"][0]
        self.assertEqual((stats["attempts"], stats["correct"], stats["accuracy"], stats["chance"]), (1, 0, 0.0, 1/3))
        self.assertEqual(stats["confusions"][0]["guess"], "unsure")
        reacted = self.request("POST", "/api/blind/trials/" + trial["id"] + "/reaction", {"reaction": "keep"})[1]["session"]
        self.assertEqual(reacted["current_trial"]["reaction"], "keep")
        self.assertEqual(self.workshop.blind.stats()["groups"][0], stats)
        self.assertEqual(self.new_workshop().blind.get(session["id"]), reacted)

    def test_failures_hide_answer_and_explicit_retry_keeps_reserved_target(self):
        self.generator.side_effect = server.WorkshopError("Reference alpha synthetic-secret", 502, details={"http_status": 429, "message": "secret target"})
        session = self.wait(self.start(self.create(size=1)))
        failed = session["current_trial"]
        self.assertEqual(failed["status"], "failed")
        self.assertIn("429", failed["error"])
        self.assertNotIn("Reference", failed["error"])
        self.assertNotIn("synthetic-secret", failed["error"])
        self.assertEqual(self.workshop.blind.stats(), {"groups": []})
        old_target = self.workshop.blind.sessions[session["id"]]["trials"][0]["target"]
        self.generator.side_effect = None
        self.generator.return_value = music()
        session = self.wait(self.start(session))
        self.assertEqual(self.workshop.blind.sessions[session["id"]]["trials"][-1]["target"], old_target)
        self.assertEqual(self.answer(session)["completed"], 1)
        self.assertEqual(self.generator.call_count, 2)

    def test_restart_does_not_retry_unknown_paid_work(self):
        session = self.create(size=1)
        private = self.workshop.blind.sessions[session["id"]]
        tid, rid = secrets.token_hex(16), secrets.token_hex(16)
        private["trials"] = [{"id": tid, "status": "generating", "target": private["plan"][0], "request_id": rid}]
        private["requests"][rid] = tid
        self.workshop.blind._save(private)
        restored = self.new_workshop()
        result = restored.blind.get(session["id"])
        self.assertEqual(result["current_trial"]["status"], "failed")
        self.assertIn("unknown", result["current_trial"]["error"])
        self.assertEqual(restored.blind.next(session["id"], {"request_id": rid, "generate": True}), result)
        self.generator.assert_not_called()

    def test_duplicate_audio_across_cohorts_and_abandoned_audio_is_practice(self):
        self.generator.side_effect = None
        self.generator.return_value = music()
        first = self.wait(self.start(self.create(size=1)))
        self.request("HEAD", first["current_trial"]["audio_url"])
        self.assertEqual(self.workshop.blind.exposures, {})
        self.request("GET", first["current_trial"]["audio_url"])
        # First audio was heard but deliberately not answered.
        second = self.wait(self.start(self.create(size=1, mode="flute")))
        answered = self.answer(second)
        self.assertTrue(answered["current_trial"]["practice"])
        self.assertFalse(answered["current_trial"]["scored"])
        self.assertEqual(self.workshop.blind.stats(), {"groups": []})
        restored = self.new_workshop()
        first_answer = restored.blind.guess(first["current_trial"]["id"], {"guess": "unsure"})
        self.assertFalse(first_answer["current_trial"]["scored"], "A duplicate already revealed this recording's answer")
        self.assertEqual(restored.blind.stats(), {"groups": []})

    def test_answered_original_scores_once_and_replays_stay_practice(self):
        self.generator.side_effect = None
        self.generator.return_value = music()
        first = self.wait(self.start(self.create(size=1)))
        for _ in range(2):
            self.request("GET", first["current_trial"]["audio_url"])
        first = self.answer(first)
        self.assertTrue(first["current_trial"]["scored"])
        self.request("GET", first["current_trial"]["audio_url"])
        second = self.answer(self.wait(self.start(self.create(size=1))))
        self.assertTrue(second["current_trial"]["practice"])
        self.assertEqual(self.workshop.blind.stats()["groups"][0]["attempts"], 1)

    def test_unreadable_exposure_history_is_preserved_and_blocks_new_scoring(self):
        session = self.wait(self.start(self.create(size=1)))
        ledger = self.root / "auditions/.blind/exposures.json"
        ledger.write_text("{broken saved history")
        restored = self.new_workshop()
        with self.assertRaises(server.WorkshopError) as raised:
            restored.blind.guess(session["current_trial"]["id"], {"guess": "unsure"})
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(ledger.read_text(), "{broken saved history")
        self.assertEqual(restored.blind.get(session["id"])["current_trial"]["status"], "ready")
        new_session = restored.blind.create({"size": 1})
        calls = self.generator.call_count
        with self.assertRaises(server.WorkshopError) as raised:
            restored.blind.next(new_session["id"], {"request_id": secrets.token_hex(16)})
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(self.generator.call_count, calls)

    def test_frozen_recipes_survive_palette_change_without_pooling(self):
        first = self.create(size=1)
        old_private = deepcopy(self.workshop.blind.sessions[first["id"]])
        for p in self.palette["existing"]:
            p["core"] = "A revised musical phrase"
        self.save_palette()
        second = self.create(size=1)
        self.assertNotEqual(old_private["group_id"], self.workshop.blind.sessions[second["id"]]["group_id"])
        answered = self.answer(self.wait(self.start(first)))
        target = answered["current_trial"]["reveal"]["profile_id"]
        self.assertEqual(answered["current_trial"]["reveal"]["prompt"], old_private["recipes"][target]["prompt"])
        self.answer(self.wait(self.start(second)))
        self.assertEqual(len(self.workshop.blind.stats()["groups"]), 2)

    def test_instrument_and_lyric_rules_and_supported_family_filters(self):
        for mode in blind.MODES:
            session = self.create(mode=mode)
            recipes = self.workshop.blind.sessions[session["id"]]["recipes"]
            for identifier, recipe in recipes.items():
                prompt = recipe["prompt"]
                self.assertIn("No reed-driven sound." if mode == "flute" else "No bowed strings.", prompt)
                if mode != "canonical" or identifier == "gamma":
                    self.assertEqual(recipe["supplied_lyrics"], "")
                    self.assertIn("Instrumental only", prompt)
                elif identifier == "beta":
                    self.assertEqual(recipe["supplied_lyrics"], "")
                    self.assertIn("Wordless vocables", prompt)
                else:
                    self.assertEqual(recipe["supplied_lyrics"], blind.NEUTRAL_LYRICS)
        self.palette["existing"][0]["workshop"]["allowed"].remove("flute")
        self.save_palette()
        self.assertEqual(self.request("POST", "/api/blind/sessions", {"mode": "flute"})[0], 409)
        self.assertEqual({c["id"] for c in self.create(mode="flute", include_challenger=True)["choices"]}, {"beta", "gamma", "challenger"})
        self.generator.assert_not_called()

    def test_bad_requests_and_csrf_cannot_generate(self):
        session = self.create()
        for value in ({"size": True}, {"size": 31}, {"mode": []}, {"include_challenger": "yes"}):
            self.assertEqual(self.request("POST", "/api/blind/sessions", value)[0], 400)
        self.assertEqual(self.request("POST", "/api/blind/sessions/" + session["id"] + "/next", {"request_id": "bad"})[0], 400)
        self.assertEqual(self.request("POST", "/api/blind/sessions/" + session["id"] + "/next", {"request_id": secrets.token_hex(16)}, headers={"X-Workshop-Token": "wrong"})[0], 403)
        self.assertEqual(self.request("POST", "/api/blind/sessions", {}, headers={"Origin": "https://elsewhere.invalid"})[0], 403)
        self.generator.assert_not_called()

    def consume(self, session, request_id=None):
        status, result = self.request("POST", "/api/blind/sessions/" + session["id"] + "/next", {"request_id": request_id or secrets.token_hex(16)})
        self.assertEqual(status, 200, result)
        return result["session"]

    def test_seed_dry_run_bounded_resume_and_no_fake_sessions_or_scores(self):
        plan = self.workshop.blind.seed(clips_per_style=3, max_clips=4)
        self.assertEqual((plan["needed"], plan["planned"]), (9, 4))
        self.assertFalse((self.root / "auditions").exists())
        self.generator.assert_not_called()
        report = self.workshop.blind.seed(clips_per_style=3, max_clips=4, execute=True)
        self.assertEqual((report["attempted"], report["completed"], report["failed"], report["ready_after"], report["remaining"]), (4, 4, 0, 4, 5))
        counts = Counter(r["target"] for r in self.workshop.blind.pool.values())
        self.assertEqual(set(counts.values()), {1, 2})
        self.assertEqual(self.workshop.blind.sessions, {})
        self.assertEqual(self.workshop.blind.stats(), {"groups": []})
        self.assertEqual(self.workshop.blind.catalog()["pool"]["by_mode"]["canonical"], {"ready": 4, "total": 4})
        self.assertIsNone(self.workshop.blind.catalog()["active_session"])
        restored = self.new_workshop()
        resumed = restored.blind.seed(clips_per_style=3, max_clips=9, execute=True)
        self.assertEqual((resumed["attempted"], resumed["ready_after"], resumed["remaining"]), (5, 9, 0))
        self.assertEqual(self.generator.call_count, 9)
        self.assertEqual(restored.blind.seed(clips_per_style=3, execute=True)["planned"], 0)
        self.assertEqual(self.generator.call_count, 9)
        self.assertTrue(Path(resumed["report_path"]).is_file())

    def test_default_next_consumes_pool_without_key_or_provider_and_deduplicates(self):
        self.workshop.blind.seed(clips_per_style=1, max_clips=3, execute=True)
        session = self.create(size=5)
        self.assertEqual(session["ready_count"], 3)
        self.workshop.key_reader = Mock(return_value=None)
        request_id = secrets.token_hex(16)
        session = self.consume(session, request_id)
        self.assertEqual(session["current_trial"]["status"], "ready")
        self.assertEqual(session["ready_count"], 2)
        self.assertEqual(self.consume(session, request_id), session)
        self.assertEqual(self.request("POST", "/api/blind/sessions/" + session["id"] + "/next", {"request_id": request_id, "generate": True})[0], 409)
        self.assertEqual(set(session["current_trial"]), {"id", "status", "audio_url", "listened", "choices", "presentation_contract"})
        self.assertEqual(self.request("GET", session["current_trial"]["audio_url"])[0], 200)
        session = self.answer(session)
        for _ in range(2):
            session = self.answer(self.consume(session))
        status, result = self.request("POST", "/api/blind/sessions/" + session["id"] + "/next", {"request_id": secrets.token_hex(16)})
        self.assertEqual(status, 409)
        self.assertIn("No fresh saved clips", result["error"])
        self.assertEqual(self.generator.call_count, 3)
        self.workshop.key_reader.assert_not_called()
        restored = self.new_workshop()
        self.assertEqual(restored.blind.get(session["id"]), session)
        self.assertEqual(restored.blind.catalog()["pool"]["ready"], 0)
        self.assertEqual(restored.blind.stats()["groups"][0]["attempts"], 3)

    def test_pool_matches_exact_frozen_cohort_and_unavailable_plan_uses_stock(self):
        self.workshop.blind.seed(clips_per_style=1, max_clips=1, execute=True)
        session = self.create(size=5)
        source = next(iter(self.workshop.blind.pool.values()))
        stored = self.workshop.blind.sessions[session["id"]]
        stored["plan"][0] = next(c["id"] for c in session["choices"] if c["id"] != source["target"])
        self.workshop.blind._save(stored)
        for p in self.palette["existing"]:
            p["core"] = "New source revision"
        self.save_palette()
        newer = self.create()
        self.assertEqual(newer["ready_count"], 0)
        self.assertEqual(self.request("POST", "/api/blind/sessions/" + newer["id"] + "/next", {"request_id": secrets.token_hex(16)})[0], 409)
        old = self.consume(session)
        private = self.workshop.blind.sessions[old["id"]]["trials"][-1]
        self.assertEqual(private["target"], source["target"])
        self.assertEqual(self.generator.call_count, 1)

    def test_claim_survives_crash_between_session_and_pool_receipts(self):
        self.workshop.blind.seed(clips_per_style=1, max_clips=1, execute=True)
        session = self.create()
        rid = secrets.token_hex(16)
        with patch.object(self.workshop.blind, "_save_pool", side_effect=OSError("synthetic storage failure")):
            self.assertEqual(self.request("POST", "/api/blind/sessions/" + session["id"] + "/next", {"request_id": rid})[0], 408)
        restored = self.new_workshop()
        recovered = restored.blind.next(session["id"], {"request_id": rid})
        self.assertEqual(recovered["current_trial"]["status"], "ready")
        self.assertEqual(recovered["ready_count"], 0)
        source = next(iter(restored.blind.pool.values()))
        self.assertEqual(source["claimed_by"], recovered["current_trial"]["id"])
        another = restored.blind.create({"size": 1})
        with self.assertRaises(server.WorkshopError):
            restored.blind.next(another["id"], {"request_id": secrets.token_hex(16)})
        self.assertEqual(self.generator.call_count, 1)

    def test_seed_stops_at_first_failure_and_never_retries_failed_or_interrupted(self):
        self.generator.side_effect = [music(b"first unique audio"), server.WorkshopError("secret prompt and synthetic-secret", details={"http_status": 429})]
        report = self.workshop.blind.seed(clips_per_style=3, max_clips=9, execute=True)
        self.assertEqual((report["attempted"], report["completed"], report["failed"]), (2, 1, 1))
        self.assertTrue(report["stopped"])
        self.assertIn("429", report["error"])
        self.assertNotIn("secret", report["error"])
        restored = self.new_workshop()
        blocked = restored.blind.seed(clips_per_style=3, max_clips=9, execute=True)
        self.assertTrue(blocked["stopped"])
        self.assertEqual(blocked["attempted"], 0)
        self.assertEqual(self.generator.call_count, 2)
        failed = next(r for r in restored.blind.pool.values() if r["status"] == "failed")
        failed["status"] = "generating"
        restored.blind._save_pool(failed)
        interrupted = self.new_workshop()
        self.assertEqual(interrupted.blind.pool[failed["id"]]["status"], "interrupted")
        self.assertTrue(interrupted.blind.seed(execute=True)["stopped"])
        self.assertEqual(self.generator.call_count, 2)

    def test_duplicate_seed_audio_is_preserved_but_never_fills_fresh_quota(self):
        self.generator.side_effect = None
        self.generator.return_value = music()
        report = self.workshop.blind.seed(clips_per_style=3, max_clips=9, execute=True)
        self.assertEqual((report["attempted"], report["completed"], report["duplicates"], report["failed"], report["ready_after"]), (2, 1, 1, 0, 1))
        self.assertTrue(report["stopped"])
        self.assertEqual(report["remaining"], 8)
        self.assertEqual(self.generator.call_count, 2)
        self.assertTrue(self.new_workshop().blind.seed(execute=True)["stopped"])
        self.assertEqual(self.generator.call_count, 2)

    def test_successful_seed_receipt_survives_report_storage_failure(self):
        writer = self.workshop.blind.write
        calls = 0
        def fail_report(path, data):
            nonlocal calls
            if "seed-reports" in path.parts:
                calls += 1
                if calls == 2:
                    raise OSError("synthetic report write failure")
            return writer(path, data)
        with patch.object(self.workshop.blind, "write", side_effect=fail_report):
            report = self.workshop.blind.seed(clips_per_style=1, max_clips=3, execute=True)
        self.assertEqual((report["attempted"], report["completed"], report["failed"]), (1, 1, 0))
        self.assertTrue(report["stopped"])
        self.assertTrue(report["report_error"])
        self.assertEqual(self.new_workshop().blind.seed_plan(clips_per_style=1)["needed"], 2)

    def test_seed_cli_requires_execute_and_process_lock(self):
        with patch.object(seed_blind_clips, "Workshop", return_value=self.workshop), patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(seed_blind_clips.main(["--root", str(self.root), "--clips-per-style", "1", "--max-clips", "3"]), 0)
            self.generator.assert_not_called()
            with blind.storage_lock(self.root):
                self.assertEqual(seed_blind_clips.main(["--root", str(self.root), "--execute"]), 1)
            self.generator.assert_not_called()
            self.assertEqual(seed_blind_clips.main(["--root", str(self.root), "--clips-per-style", "1", "--max-clips", "3", "--execute"]), 0)
        self.assertEqual(self.generator.call_count, 3)

    def test_interrupted_seeding_has_truthful_durable_report_and_no_retry(self):
        self.generator.side_effect = KeyboardInterrupt()
        report = self.workshop.blind.seed(clips_per_style=1, max_clips=3, execute=True)
        self.assertEqual((report["attempted"], report["completed"]), (1, 0))
        self.assertTrue(report["stopped"])
        self.assertTrue(report["interrupted"])
        self.assertEqual(next(iter(self.workshop.blind.pool.values()))["status"], "interrupted")
        self.assertTrue(json.loads(Path(report["report_path"]).read_text())["stopped"])
        self.assertTrue(self.new_workshop().blind.seed(execute=True)["stopped"])
        self.generator.assert_called_once()

    def test_open_ended_default_accepts_more_than_thirty_answers_and_restores(self):
        status, result = self.request("POST", "/api/blind/sessions", {})
        self.assertEqual(status, 200)
        session = result["session"]
        self.assertIsNone(session["size"])
        for _ in range(32):
            session = self.answer(self.wait(self.start(session)))
        self.assertEqual(session["completed"], 32)
        self.assertFalse(session["finished"])
        self.assertEqual(self.new_workshop().blind.get(session["id"]), session)
        self.assertEqual(self.workshop.blind.stats()["groups"][0]["attempts"], 32)
        summary = self.workshop.blind.catalog()["sessions"][0]
        self.assertEqual((summary["size"], summary["format"], summary["include_challenger"]), (None, "clip", False))

    def test_clip_digest_preserves_existing_pool_and_full_isolated(self):
        # Only read canonical palette source; all state and media stay temporary.
        self.palette = json.loads((server.ROOT / "dashboard/palette-data.json").read_text())
        self.save_palette()
        clip_plan = self.workshop.blind.seed_plan()
        self.assertEqual(clip_plan["group_id"], "c1de0884d13ecf5b7ed89ea7419dab4b67c39425638eb0b2d627175d2dc67067")
        self.workshop.blind.seed(clips_per_style=1, max_clips=1, execute=True)
        clip = self.create(size=None)
        full = self.create(size=None, format="full")
        self.assertEqual((clip["ready_count"], full["ready_count"]), (1, 0))
        self.assertTrue(all("description" in choice for choice in full["choices"]))
        self.assertTrue(all(set(choice) == {"id", "name"} for choice in self.workshop.blind.sessions[clip["id"]]["choices"]))
        self.assertNotEqual(self.workshop.blind.sessions[clip["id"]]["group_id"], self.workshop.blind.sessions[full["id"]]["group_id"])
        full = self.wait(self.start(full))
        self.assertEqual(self.generator.call_args.kwargs["model"], "lyria-3.5")
        self.assertNotIn("thirty-second", self.generator.call_args.args[0])
        self.assertIn("complete acoustic song", self.generator.call_args.args[0])
        self.assertEqual(self.workshop.blind.get(clip["id"])["ready_count"], 1)
        self.answer(full)
        self.answer(self.consume(clip))
        self.assertEqual({g["model"] for g in self.workshop.blind.stats()["groups"]}, {blind.MODEL, "lyria-3.5"})
        pool = self.workshop.blind.catalog()["pool"]
        self.assertEqual(pool["by_format"]["clip"]["total"], 1)
        self.assertEqual(pool["by_format"]["full"]["total"], 0)

    def test_legacy_finite_session_without_format_still_loads(self):
        session = self.create(size=1)
        private = self.workshop.blind.sessions[session["id"]]
        del private["format"]
        self.workshop.blind._save(private)
        restored = self.new_workshop().blind.get(session["id"])
        self.assertEqual(restored["format"], "clip")
        self.assertEqual(restored["size"], 1)

    def replay_request(self, session, *, replay="all", hours=24, fallback=False, request_id=None):
        return self.request("POST", "/api/blind/sessions/" + session["id"] + "/next",
                            {"request_id": request_id or secrets.token_hex(16), "replay": replay,
                             "replay_after_hours": hours, "generate_if_needed": fallback})

    def test_replay_wall_clock_history_resets_and_latest_correctness(self):
        clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch.object(blind, "now", side_effect=lambda: clock.isoformat()):
            session = self.wait(self.start(self.create(size=None)))
            original_id = session["current_trial"]["id"]
            self.assertEqual(self.request("POST", f"/api/blind/trials/{original_id}/played", {"completed": True})[0], 200)
            session = self.answer(session)
            target = session["current_trial"]["reveal"]["profile_id"]
            clock += timedelta(hours=23)
            self.assertEqual(self.replay_request(session, replay="incorrect")[0], 409)
            # History play resets the interval even though no audio GET occurs.
            self.request("POST", f"/api/blind/trials/{original_id}/played", {})
            clock += timedelta(hours=2)
            self.assertEqual(self.replay_request(session, replay="incorrect")[0], 409)
            clock += timedelta(hours=22)
            status, result = self.replay_request(session, replay="incorrect")
            self.assertEqual(status, 200, result)
            replayed = result["session"]
            self.assertNotEqual(replayed["current_trial"]["id"], original_id)
            self.assertTrue(replayed["current_trial"]["practice"])
            self.assertNotIn("reveal", replayed["current_trial"])
            replay_id = replayed["current_trial"]["id"]
            self.request("POST", f"/api/blind/trials/{replay_id}/played", {"completed": True})
            corrected = self.answer(replayed, target)
            self.assertTrue(corrected["current_trial"]["correct"])
            self.assertFalse(corrected["current_trial"]["scored"])
            clock += timedelta(hours=24)
            self.assertEqual(self.replay_request(corrected, replay="incorrect")[0], 409)
            status, result = self.replay_request(corrected, replay="all")
            self.assertEqual(status, 200)
            wrong_again = self.answer(result["session"], "unsure")
            clock += timedelta(hours=24)
            self.assertEqual(self.replay_request(wrong_again, replay="incorrect")[0], 200)
            self.assertEqual(self.generator.call_count, 1)
            self.assertEqual(self.workshop.blind.stats()["groups"][0]["attempts"], 1)

    def test_played_completion_is_durable_and_read_only_status_does_not_reset_interval(self):
        clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch.object(blind, "now", side_effect=lambda: clock.isoformat()):
            session = self.wait(self.start(self.create(size=None)))
            tid = session["current_trial"]["id"]
            self.assertFalse(session["current_trial"]["listened"])
            self.request("POST", f"/api/blind/trials/{tid}/played", {"completed": True})
            session = self.answer(session)
            self.assertTrue(self.new_workshop().blind.get(session["id"])["current_trial"]["listened"])
            timestamp = next(iter(self.workshop.blind.exposures.values()))["last_played_at"]
            clock += timedelta(hours=25)
            self.request("GET", "/api/blind")
            self.request("GET", "/api/blind/stats")
            self.assertEqual(next(iter(self.workshop.blind.exposures.values()))["last_played_at"], timestamp)
            self.assertEqual(self.replay_request(session, replay="none")[0], 409)
            self.assertEqual(self.replay_request(session, replay="all")[0], 200)
            self.generator.assert_called_once()

    def test_replayed_pool_record_does_not_reclaim_source_after_restart(self):
        self.workshop.blind.seed(clips_per_style=1, max_clips=3, execute=True)
        session = self.answer(self.consume(self.create(size=None)))
        original = self.workshop.blind.sessions[session["id"]]["trials"][0]
        source_id = original["source_id"]
        status, result = self.replay_request(session, hours=0)
        self.assertEqual(status, 200)
        replayed = self.answer(result["session"])
        restored = self.new_workshop()
        self.assertFalse(restored.blind.pool_error)
        self.assertEqual(restored.blind.pool[source_id]["claimed_by"], original["id"])
        self.assertEqual(restored.blind.get(session["id"])["ready_count"], 2)
        ready = restored.blind.next(session["id"], {"request_id": secrets.token_hex(16), "generate_if_needed": True})
        self.assertEqual(ready["current_trial"]["status"], "ready")
        self.assertFalse(ready["current_trial"].get("practice", False))
        self.assertEqual(self.generator.call_count, 3)

    def test_explicit_fallback_only_one_call_and_replay_options_idempotent(self):
        entered, release = threading.Event(), threading.Event()
        def generate(*args, **kwargs):
            entered.set()
            release.wait(3)
            return music()
        self.generator.side_effect = generate
        session = self.create(size=None, format="full")
        rid = secrets.token_hex(16)
        try:
            status, started = self.replay_request(session, fallback=True, request_id=rid)
            self.assertEqual(status, 200)
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.replay_request(session, fallback=True, request_id=rid)[0], 200)
            self.assertEqual(self.replay_request(session, replay="incorrect", fallback=True, request_id=rid)[0], 409)
            # Switching session or format cannot purchase a second active request.
            self.assertEqual(self.replay_request(self.create(size=None), fallback=True)[0], 409)
        finally:
            release.set()
        result = self.wait(started["session"])
        self.assertEqual(result["current_trial"]["status"], "ready")
        self.generator.assert_called_once()
        self.assertEqual(self.generator.call_args.kwargs["model"], "lyria-3.5")

    def test_replay_intervals_and_corrupt_pool_never_trigger_paid_fallback(self):
        session = self.create(size=None)
        for interval in (-1, True, float("inf"), float("nan"), "24"):
            self.assertEqual(self.replay_request(session, hours=interval, fallback=True)[0], 400)
        self.workshop.blind.pool_error = True
        self.assertEqual(self.replay_request(session, fallback=True)[0], 409)
        self.generator.assert_not_called()

    def test_practice_remains_unscored_without_exposure_ledger_and_latest_saved_guess_wins(self):
        session = self.answer(self.wait(self.start(self.create(size=None))))
        status, result = self.replay_request(session, hours=0)
        self.assertEqual(status, 200)
        replayed = result["session"]
        private = self.workshop.blind.sessions[session["id"]]["trials"][-1]
        target, audio_hash = private["target"], private["audio_sha256"]
        self.workshop.blind.exposures = {}
        corrected = self.answer(replayed, target)
        self.assertFalse(corrected["current_trial"]["scored"])
        # Simulate stale ledger audit data after a separated write; session wins.
        self.workshop.blind.exposures[audio_hash]["latest_correct"] = False
        self.assertEqual(self.replay_request(corrected, replay="incorrect", hours=0)[0], 409)
        self.assertEqual(self.workshop.blind.stats()["groups"][0]["attempts"], 1)

    def test_large_open_ended_history_restores_beyond_generic_json_limit(self):
        self.generator.side_effect = lambda *a, **kw: music(b"ID3 " + secrets.token_bytes(12), lyrics="Synthetic returned lyric text. " * 6000)
        session = self.create(size=None, format="full")
        for _ in range(12):
            session = self.answer(self.wait(self.start(session)))
        path = self.root / "auditions/.blind/sessions" / (session["id"] + ".json")
        self.assertGreater(path.stat().st_size, 2_000_000)
        self.assertEqual(self.new_workshop().blind.get(session["id"]), session)
        before = path.read_bytes()
        with patch.object(blind, "SESSION_LIMIT", len(before)):
            with self.assertRaises(server.WorkshopError):
                self.workshop.blind.next(session["id"], {"request_id": secrets.token_hex(16), "generate_if_needed": True})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.generator.call_count, 12)

    def test_three_choices_include_target_and_two_distinct_randomized_distractors(self):
        session = self.create(include_challenger=True)
        private = self.workshop.blind.sessions[session["id"]]
        positions, distractor_sets = set(), set()
        with patch.object(blind.secrets, "SystemRandom", return_value=random.Random(312)):
            for _ in range(60):
                trial = {"target": "alpha"}
                self.workshop.blind._offer_choices(private, trial)
                offered = trial["choice_ids"]
                self.assertEqual(len(set(offered)), 3)
                self.assertIn("alpha", offered)
                self.assertTrue(set(offered) <= {c["id"] for c in session["choices"]})
                self.assertEqual(trial["presentation_contract"], blind.PRESENTATION)
                positions.add(offered.index("alpha"))
                distractor_sets.add(frozenset(set(offered) - {"alpha"}))
        self.assertEqual(positions, {0, 1, 2})
        self.assertEqual(len(distractor_sets), 3)
        self.generator.assert_not_called()

    def test_offered_choices_are_frozen_and_unoffered_guess_is_rejected(self):
        session = self.create(size=None, include_challenger=True)
        request_id = secrets.token_hex(16)
        session = self.wait(self.start(session, request_id))
        trial = session["current_trial"]
        offered = {c["id"] for c in trial["choices"]}
        self.assertEqual(len(offered), 3)
        self.assertTrue(all(set(c) == {"id", "name", "description"} for c in trial["choices"]))
        private = self.workshop.blind.sessions[session["id"]]
        self.assertIn(private["trials"][0]["target"], offered)
        self.assertEqual(len(session["choices"]), 4)
        unoffered = next(c["id"] for c in session["choices"] if c["id"] not in offered)
        status, result = self.request("POST", f"/api/blind/trials/{trial['id']}/guess", {"guess": unoffered})
        self.assertEqual(status, 400)
        self.assertIn("offered", result["error"])
        self.assertEqual(self.workshop.blind.stats(), {"groups": []})
        self.assertEqual(self.workshop.blind.exposures, {})
        self.assertEqual(self.start(session, request_id), session)
        for _ in range(2):
            restored = self.new_workshop()
            self.assertEqual(restored.blind.get(session["id"]), session)
            self.assertEqual(restored.blind.catalog()["active_session"], session)
        answered = self.answer(session, private["trials"][0]["target"])
        self.assertTrue(answered["current_trial"]["correct"])
        self.assertEqual(answered["current_trial"]["choices"], trial["choices"])
        replayed = self.replay_request(answered, hours=0)[1]["session"]
        self.assertEqual(len(replayed["current_trial"]["choices"]), 3)
        self.assertTrue(replayed["current_trial"]["practice"])
        self.assertNotIn("reveal", replayed["current_trial"])
        self.answer(replayed)
        self.assertEqual(self.workshop.blind.stats()["groups"][0]["attempts"], 1)
        self.generator.assert_called_once()

    def test_legacy_ready_migrates_once_preserving_audio_answers_and_chance_groups(self):
        ids = ["style_" + str(i) for i in range(11)]
        self.palette["baseline"]["profiles"] = ids
        self.palette["existing"] = [profile(identifier) for identifier in ids]
        self.save_palette()
        self.workshop.blind.seed(clips_per_style=1, max_clips=4, execute=True)
        session = self.create(size=None)
        for _ in range(3):
            session = self.answer(self.consume(session))
        session = self.consume(session)
        private = self.workshop.blind.sessions[session["id"]]
        group_id = private["group_id"]
        for trial in private["trials"]:
            del trial["choice_ids"]
            del trial["presentation_contract"]
        historical = deepcopy(private["trials"][:3])
        pending = deepcopy(private["trials"][-1])
        pool_before = deepcopy(self.workshop.blind.pool)
        self.workshop.blind._save(private)
        restored = self.new_workshop()
        old_stats = restored.blind.stats()["groups"][0]
        self.assertEqual((old_stats["id"], old_stats["choice_count"], old_stats["chance"], old_stats["attempts"]), (group_id, 11, 1/11, 3))
        migrated = restored.blind.catalog()["active_session"]
        current = migrated["current_trial"]
        self.assertEqual(migrated["pool_group_id"], group_id)
        self.assertEqual(current["presentation_contract"], blind.PRESENTATION)
        self.assertEqual(current["id"], pending["id"])
        self.assertEqual(current["audio_url"], session["current_trial"]["audio_url"])
        self.assertEqual(len(current["choices"]), 3)
        self.assertTrue(all(len(t["choices"]) == 11 for t in migrated["trials"][:3]))
        saved = json.loads((self.root / "auditions/.blind/sessions" / (session["id"] + ".json")).read_text())
        self.assertEqual(saved["trials"][:3], historical)
        self.assertEqual(saved["trials"][-1], {**pending, "choice_ids": [c["id"] for c in current["choices"]], "presentation_contract": blind.PRESENTATION})
        self.assertEqual(saved["group_id"], group_id)
        self.assertEqual(restored.blind.pool, pool_before)
        self.assertEqual(restored.blind.get(session["id"]), migrated)
        restored = self.new_workshop()
        self.assertEqual(restored.blind.catalog()["active_session"], migrated)
        restored.blind.guess(current["id"], {"guess": "unsure"})
        groups = {g["presentation_contract"]: g for g in restored.blind.stats()["groups"]}
        self.assertEqual(groups[blind.LEGACY_PRESENTATION], old_stats)
        self.assertEqual((groups[blind.PRESENTATION]["attempts"], groups[blind.PRESENTATION]["choice_count"], groups[blind.PRESENTATION]["chance"]), (1, 3, 1/3))
        self.assertEqual(groups[blind.PRESENTATION]["pool_group_id"], group_id)
        self.assertNotEqual(groups[blind.PRESENTATION]["id"], group_id)
        self.assertEqual(self.generator.call_count, 4)

    def test_presentation_contract_separates_equal_size_legacy_scores(self):
        session = self.answer(self.wait(self.start(self.create(size=None))))
        private = self.workshop.blind.sessions[session["id"]]
        del private["trials"][0]["choice_ids"]
        del private["trials"][0]["presentation_contract"]
        self.workshop.blind._save(private)
        self.answer(self.wait(self.start(session)))
        groups = self.workshop.blind.stats()["groups"]
        self.assertEqual(len(groups), 2)
        self.assertEqual({g["presentation_contract"] for g in groups}, {blind.PRESENTATION, blind.LEGACY_PRESENTATION})
        self.assertTrue(all(g["chance"] == 1/3 and g["attempts"] == 1 for g in groups))

    def test_failed_migration_never_serves_unpersisted_choices(self):
        session = self.wait(self.start(self.create(size=None, include_challenger=True)))
        private = self.workshop.blind.sessions[session["id"]]
        del private["trials"][0]["choice_ids"]
        del private["trials"][0]["presentation_contract"]
        self.workshop.blind._save(private)
        path = self.root / "auditions/.blind/sessions" / (session["id"] + ".json")
        before = path.read_bytes()
        with patch.object(self.workshop.blind, "write", side_effect=OSError("fixture disk failure")):
            with self.assertRaises(OSError):
                self.workshop.blind.get(session["id"])
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn("choice_ids", self.workshop.blind.sessions[session["id"]]["trials"][0])
        migrated = self.workshop.blind.get(session["id"])
        self.assertEqual(self.new_workshop().blind.get(session["id"]), migrated)
        self.generator.assert_called_once()


class ClipProviderTests(unittest.TestCase):
    def test_exact_clip_model_and_no_storage_without_changing_default(self):
        for model in (server.MODEL, blind.MODEL):
            opener = Mock()
            opener.open.return_value = io.BytesIO(json.dumps(music()).encode())
            with patch.object(server, "build_opener", return_value=opener):
                server.call_google("synthetic prompt", "fixture-key", model=model)
            request = opener.open.call_args.args[0]
            self.assertEqual(json.loads(request.data), {"model": model, "input": "synthetic prompt", "store": False})
            opener.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
