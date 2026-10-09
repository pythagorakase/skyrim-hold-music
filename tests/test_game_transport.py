import base64
import http.client
import http.server
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game_adapter" / "hold_music_adapter"))
import engine
import service
from mp3_fixture import mp3_frames


CONFIG = '''bard_singing:
  enabled: true
  provider: openrouter
  backup_provider: none
  openrouter:
    api_key: "fake-key-for-local-tests"
    model: google/lyria-3-pro-preview
  acestep_local:
    base_url: http://localhost:8002/v1/chat/completions
    model: acemusic/acestep-v1.5-turbo
  generation:
    default_style: "Original lute song"
    interval_hours: 8
    max_cached_songs: 50
  playback:
    volume: 0.7
'''


def sample(lyric="[Verse]\nThe road bends toward the sea.", gender="Female"):
    return {"model": engine.MODEL, "stream": True, "messages": [{
        "role": "user", "content": gender + " vocal. Old style, choir, orchestra HM1[Delacourt||Dead Man's Drink]\n\nLyrics:\n" + lyric,
    }]}


class TransformTests(unittest.TestCase):
    def test_instrumental_removes_all_input_voice_lyrics_and_extra_fields(self):
        request = sample("UNIQUE_DRAFT_THAT_MUST_NEVER_REACH_LYRIA")
        request["audio_config"] = {"vocal_language": "en"}
        request["lyrics"] = "EXTRA_LYRICS_MUST_NOT_LEAK"
        result = engine.transform(request, "instrumental")
        text = json.dumps(result)
        for unwanted in ("UNIQUE_DRAFT", "EXTRA_LYRICS", "Female vocal", "Lyrics:", "audio_config", "Old style"):
            self.assertNotIn(unwanted, text)
        self.assertEqual(set(result), {"model", "messages", "stream"})
        self.assertIn("One adult female performer; solo lute instrumental; plucked strings.", text)
        self.assertIn("Style: Karelian laments and runo-song (instrumental reduction).", text)
        self.assertNotIn("Voice:", text)

    def test_vocal_keeps_gender_and_lyrics_verbatim(self):
        lyric = "[Verse]\nZohra’s road — and a lute.\n[Chorus]\nSing!\n"
        for gender in ("Male", "Female"):
            text = engine.transform(sample(lyric, gender), "vocal")["messages"][0]["content"]
            self.assertIn("One adult " + gender.lower() + " performer; singing with plucked lute.", text)
            self.assertTrue(text.endswith("Lyrics:\n" + lyric))
            self.assertNotIn("Old style", text)

    def test_rejects_unrecognized_vocal_format(self):
        request = sample()
        request["messages"][0]["content"] = "Different native protocol"
        with self.assertRaises(ValueError):
            engine.transform(request, "vocal")

    def test_does_not_route_unrelated_models(self):
        request = sample()
        request["model"] = "unrelated/dialogue-model"
        with self.assertRaises(ValueError):
            engine.transform(request, "instrumental")

    def test_unknown_shapes_are_rejected(self):
        for request in (None, [], {}, {"model": engine.MODEL, "messages": [None]},
                        {"model": engine.MODEL, "messages": [{"role": "system", "content": "no"}]}):
            with self.assertRaises(ValueError):
                engine.transform(request, "instrumental")


class ModeTests(unittest.TestCase):
    def test_force_each_mode_and_reject_invalid_percent(self):
        picker = engine.ModeSelector(bytes(range(32)))
        self.assertEqual(picker.choose(sample(), 0), "vocal")
        self.assertEqual(picker.choose(sample(), 100), "instrumental")
        for value in (-1, 101, True, "50", 0.5):
            with self.assertRaises(ValueError):
                picker.choose(sample(), value)

    def test_retry_and_restart_keep_choice(self):
        with tempfile.TemporaryDirectory() as d:
            seed = Path(d) / "seed.txt"
            first = engine.ModeSelector.from_file(seed)
            second = engine.ModeSelector.from_file(seed)
            self.assertEqual(first.choose(sample(), 50), second.choose(sample(), 50))
            reordered = {k: sample()[k] for k in reversed(sample())}
            self.assertEqual(first.choose(sample(), 50), second.choose(reordered, 50))

    def test_distinct_compositions_are_approximately_half_instrumental(self):
        picker = engine.ModeSelector(bytes(range(32)))
        count = sum(picker.choose(sample(f"[Verse]\nNew composition {i}."), 50) == "instrumental" for i in range(2000))
        self.assertTrue(900 <= count <= 1100, count)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source.yaml"
        self.source.write_bytes(CONFIG.replace("\n", "\r\n").encode())
        self.bridge = engine.ConfigOverlay(self.source, Path(self.tmp.name) / "runtime")

    def test_only_three_fields_are_overlaid_and_source_is_untouched(self):
        before = self.source.read_bytes()
        overlay = self.bridge.prepare("http://127.0.0.1:18765/test/v1/chat/completions")
        self.assertEqual(before, self.source.read_bytes())
        data = engine.read_text(overlay)
        self.assertEqual(engine.get_scalar(data, engine.MANAGED[0]), "acestep_local")
        self.assertEqual(engine.get_scalar(data, engine.MANAGED[2]), engine.MODEL)
        self.assertIn("\r\n", data)
        self.bridge.reconcile()
        self.assertEqual(before, self.source.read_bytes())

    def test_dashboard_edits_survive_but_local_route_does_not(self):
        overlay = self.bridge.prepare("http://127.0.0.1:18765/test/v1/chat/completions")
        changed = engine.read_text(overlay).replace("volume: 0.7", "volume: 0.4")
        engine.atomic_text(overlay, changed)
        self.bridge.reconcile()
        result = engine.read_text(self.source)
        self.assertIn("volume: 0.4", result)
        self.assertEqual(engine.get_scalar(result, engine.MANAGED[0]), "openrouter")
        self.assertEqual(engine.get_scalar(result, engine.MANAGED[1]), "http://localhost:8002/v1/chat/completions")

    def test_conflicting_edits_are_preserved_without_overwrite(self):
        overlay = self.bridge.prepare("http://127.0.0.1:18765/test/v1/chat/completions")
        engine.atomic_text(overlay, engine.read_text(overlay).replace("volume: 0.7", "volume: 0.4"))
        self.source.write_text(CONFIG.replace("interval_hours: 8", "interval_hours: 12"))
        before = self.source.read_bytes()
        with self.assertLogs(engine.LOG, level="WARNING") as logs:
            self.assertIsNone(self.bridge.reconcile())
        self.assertIn("preserved a conflict copy", logs.output[0])
        self.assertEqual(before, self.source.read_bytes())
        conflict = self.bridge.runtime / "BardSinging.conflict.yaml"
        self.assertTrue(conflict.exists())
        self.assertIn("volume: 0.4", engine.read_text(conflict))
        self.assertEqual(engine.get_scalar(engine.read_text(conflict), engine.MANAGED[0]), "openrouter")
        self.assertFalse(self.bridge.baseline.exists())
        self.assertTrue(self.bridge.prepare("http://127.0.0.1:18765/test/v1/chat/completions").exists())

    def test_prepare_recovers_a_pending_conflict_after_restart(self):
        endpoint = "http://127.0.0.1:18765/test/v1/chat/completions"
        overlay = self.bridge.prepare(endpoint)
        engine.atomic_text(overlay, engine.read_text(overlay).replace("volume: 0.7", "volume: 0.4"))
        self.source.write_text(CONFIG.replace("interval_hours: 8", "interval_hours: 12"))
        bridge = engine.ConfigOverlay(self.source, self.bridge.runtime)
        with self.assertLogs(engine.LOG, level="WARNING"):
            prepared = bridge.prepare(endpoint)
        self.assertTrue(prepared.exists())
        self.assertIn("interval_hours: 12", engine.read_text(prepared))
        self.assertIn("volume: 0.7", engine.read_text(prepared))
        self.assertIn("volume: 0.4", engine.read_text(bridge.runtime / "BardSinging.conflict.yaml"))
        self.assertEqual(engine.get_scalar(engine.read_text(prepared), engine.MANAGED[0]), "acestep_local")
        bridge.reconcile()
        self.assertFalse(bridge.baseline.exists())

    def test_bom_round_trip_in_every_derived_file_and_after_restart(self):
        bom = b"\xef\xbb\xbf"
        original = bom + CONFIG.replace("\n", "\r\n").encode()
        self.source.write_bytes(original)
        endpoint = "http://127.0.0.1:18765/test/v1/chat/completions"
        overlay = self.bridge.prepare(endpoint)
        for path in (self.source, self.bridge.baseline, overlay):
            self.assertTrue(path.read_bytes().startswith(bom))
            self.assertFalse(engine.read_text(path).startswith("\ufeff"))
            self.assertIn(b"\r\n", path.read_bytes())
        self.bridge.reconcile()
        self.assertEqual(self.source.read_bytes(), original)
        self.bridge.prepare(endpoint)
        # A dashboard writer may omit the BOM; the baseline remembers the source.
        engine.atomic_text(overlay, engine.read_text(overlay).replace("volume: 0.7", "volume: 0.4"))
        recovered = engine.ConfigOverlay(self.source, self.bridge.runtime)
        recovered.reconcile()
        self.assertEqual(self.source.read_bytes(), original.replace(b"volume: 0.7", b"volume: 0.4"))
        recovered.prepare(endpoint)
        engine.atomic_text(overlay, engine.read_text(overlay).replace("volume: 0.4", "volume: 0.2"))
        self.source.write_bytes(self.source.read_bytes().replace(b"interval_hours: 8", b"interval_hours: 12"))
        with self.assertLogs(engine.LOG, level="WARNING"):
            engine.ConfigOverlay(self.source, self.bridge.runtime).reconcile()
        conflict = self.bridge.runtime / "BardSinging.conflict.yaml"
        self.assertTrue(conflict.read_bytes().startswith(bom))
        self.assertIn(b"volume: 0.2", conflict.read_bytes())
        self.assertIn(b"\r\n", conflict.read_bytes())
        self.assertFalse(self.bridge.baseline.exists())
        recovered.prepare(endpoint)
        for path in (self.source, recovered.baseline, overlay, conflict):
            self.assertEqual(path.read_bytes().count(bom), 1)

    def test_unknown_provider_falls_back_before_overlay_creation(self):
        self.source.write_text(CONFIG.replace("provider: openrouter", "provider: minimax"))
        with self.assertRaises(ValueError):
            self.bridge.prepare("http://127.0.0.1/test")
        self.assertFalse(self.bridge.overlay.exists())

    def test_yaml_scalar_handling(self):
        self.assertEqual(engine.parse_scalar('"a#b" # comment'), "a#b")
        self.assertEqual(engine.parse_scalar("'it''s a key'"), "it's a key")
        self.assertEqual(engine.parse_scalar("abc # comment"), "abc")
        with self.assertRaises(ValueError):
            engine.parse_scalar("| multiline")
        with self.assertRaises(ValueError):
            engine.get_scalar("same: 1\nsame: 2\n", ("same",))


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.config = root / "BardSinging.yaml"
        self.config.write_text(CONFIG)
        self.settings = root / "settings.yaml"
        self.settings.write_text("instrumentalPercent: 100\n")
        self.received = []
        self.status = 200
        fixture = self
        # Hand-assembled Layer III frames; split one base64 string off quartet boundaries.
        self.audio = mp3_frames()
        audio = base64.b64encode(self.audio).decode()
        fragments = (audio[:31], audio[31:1003], audio[1003:])
        events = [{"id": "fixture-1", "choices": [{"index": 0, "delta": {"audio": {"data": part}},
                                                      "finish_reason": None}]} for part in fragments]
        events.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        self.stream = b"".join(("data: " + json.dumps(event) + "\n\n").encode() for event in events)
        self.stream += b"data: [DONE]\n\n"
        self.stall = 0

        class Upstream(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fixture.received.append((body, dict(self.headers)))
                self.send_response(fixture.status)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                if fixture.status == 200:
                    time.sleep(fixture.stall)
                    for i in range(0, len(fixture.stream), 997):
                        self.wfile.write(fixture.stream[i:i+997])
                        self.wfile.flush()
                else:
                    self.wfile.write(b'{"error":"test quota"}')

        self.upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.upstream.server_close)
        self.addCleanup(self.upstream.shutdown)
        self.adapter = engine.Adapter(self.config, self.settings, root / "state", port=0,
                                      upstream=f"http://127.0.0.1:{self.upstream.server_port}/v1/chat/completions")
        self.url = self.adapter.start()
        self.addCleanup(self.adapter.stop)

    def post(self, payload=None, headers=None, url=None):
        request = urllib.request.Request(url or self.url, data=json.dumps(payload or sample()).encode(),
                                         headers={"Content-Type": "application/json", **(headers or {})})
        return urllib.request.urlopen(request, timeout=3)

    def assert_duration_stream(self, relayed):
        init = engine.content_event({"role": "assistant", "content": ""})
        self.assertTrue(relayed.startswith(init))
        # Exact suffix checks every original audio/finish line, spacing and event order.
        self.assertTrue(relayed.endswith(self.stream))
        prefix = relayed[:-len(self.stream)]
        self.assertIn(b"**Duration:** 5s", prefix)
        self.assertNotIn(b'"audio"', prefix)
        self.assertTrue(relayed.endswith(b"data: [DONE]\n\n"))
        events = [json.loads(line[6:]) for line in relayed.splitlines()
                  if line.startswith(b"data: ") and line != b"data: [DONE]"]
        self.assertEqual(events[0], {"choices": [{"index": 0,
                         "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})
        fragments = [choice["delta"]["audio"]["data"] for event in events
                     for choice in event.get("choices", []) if "audio" in choice.get("delta", {})]
        self.assertEqual(base64.b64decode("".join(fragments), validate=True), self.audio)

    def test_duration_metadata_precedes_verbatim_audio_and_updates_health(self):
        with self.assertLogs(engine.LOG, level="INFO") as logs:
            with self.post() as response:
                self.assertEqual(response.headers["Connection"], "close")
                self.assert_duration_stream(response.read())
        self.assertEqual(service.health(self.url)["counts"]["duration_reported"], 1)
        self.assertEqual(self.adapter.counts["errors"], 0)
        self.assertIn(f"duration_seconds=5 audio_bytes={len(self.audio)} reported=true", "\n".join(logs.output))

    def test_heartbeat_arrives_during_three_second_upstream_stall(self):
        self.stall = 3
        started = time.monotonic()
        with self.post() as response:
            init = response.readline() + response.readline()
            self.assertLess(time.monotonic() - started, 1.5)
            heartbeat = response.readline() + response.readline()
            self.assertEqual(json.loads(heartbeat.splitlines()[0][6:])["choices"][0]["delta"], {"content": "."})
            self.assertLess(time.monotonic() - started, 2.9)
            self.assertGreaterEqual(time.monotonic() - started, 1.8)
            self.assert_duration_stream(init + heartbeat + response.read())

    def assert_fallback(self, reason):
        with self.assertLogs(engine.LOG, level="INFO") as logs:
            with self.post() as response:
                relayed = response.read()
        self.assertEqual(relayed, engine.content_event({"role": "assistant", "content": ""}) + self.stream)
        self.assertNotIn(b"**Duration:**", relayed)
        self.assertEqual(self.adapter.counts["duration_reported"], 0)
        self.assertEqual(self.adapter.counts["errors"], 0)
        self.assertEqual(self.adapter.counts["upstream_http_200"], 1)
        self.assertIn(reason, "\n".join(logs.output))
        self.assertIn("reported=false", "\n".join(logs.output))
        self.assertNotIn("PRIVATE_UPSTREAM_TEXT", "\n".join(logs.output))

    def test_upstream_error_event_uses_verbatim_fallback(self):
        self.stream = b'data: {"error":{"message":"PRIVATE_UPSTREAM_TEXT"}}\n\n' + self.stream
        self.assert_fallback("upstream error event")

    def test_invalid_base64_uses_verbatim_fallback(self):
        self.stream = b'data: {"choices":[{"delta":{"audio":{"data":"PRIVATE_UPSTREAM_TEXT!"}}}]}\n\ndata: [DONE]\n\n'
        self.assert_fallback("invalid audio base64")

    def test_missing_done_uses_verbatim_fallback(self):
        self.stream = self.stream.removesuffix(b"data: [DONE]\n\n")
        self.assert_fallback("missing [DONE]")

    def test_no_audio_uses_verbatim_fallback(self):
        self.stream = b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        self.assert_fallback("no audio")

    def test_zero_duration_skips_metadata(self):
        self.stream = b'data: {"choices":[{"delta":{"audio":{"data":"bm90IG1wMw=="}}}]}\n\ndata: [DONE]\n\n'
        self.assert_fallback("unrecognized MP3 duration")

    def test_instrumental_through_http_and_sse_audio_is_byte_identical(self):
        self.settings.write_text("instrumentalPercent: 100\nreportDuration: false\n")
        with self.post() as response:
            self.assertEqual(response.read(), self.stream)
        self.assertEqual(self.adapter.counts["duration_reported"], 0)
        body, headers = self.received[0]
        self.assertNotIn("Lyrics:", body["messages"][0]["content"])
        self.assertEqual(headers["Authorization"], "Bearer fake-key-for-local-tests")
        self.assertEqual(self.adapter.counts["instrumental"], 1)

    def test_vocal_branch_through_http(self):
        self.settings.write_text("instrumentalPercent: 0\n")
        with self.post() as response:
            self.assert_duration_stream(response.read())
        self.assertTrue(self.received[0][0]["messages"][0]["content"].endswith("Lyrics:\n[Verse]\nThe road bends toward the sea."))

    def test_upstream_error_is_not_retried_or_changed_to_a_vocal(self):
        self.status = 429
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post()
        self.assertEqual(caught.exception.code, 429)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.adapter.counts["vocal"], 0)

    def real_request(self):
        return json.loads((Path(__file__).parent / "fixtures/skyrimnet_music_request.json").read_text(encoding="utf-8"))

    def test_recorded_request_shape_through_http_in_both_modes(self):
        incoming = self.real_request()
        lyrics = incoming["messages"][0]["content"].split("\n\nLyrics:\n", 1)[1]
        for percent, mode in ((0, "vocal"), (100, "instrumental")):
            with self.subTest(mode=mode):
                self.settings.write_text(f"instrumentalPercent: {percent}\n")
                with self.assertLogs(engine.LOG, level="INFO") as logs:
                    with mock.patch.object(engine, "context", wraps=engine.context) as context:
                        with self.post(incoming) as response:
                            self.assert_duration_stream(response.read())
                        self.assertEqual(context.call_count, 1)
                body, _ = self.received[-1]
                prompt = body["messages"][0]["content"]
                self.assertTrue(prompt.startswith("Style: "))
                self.assertEqual(prompt.splitlines()[1], "Tamriel (Elder Scrolls): Whiterun Hold, Skyrim.")
                self.assertNotIn("HM1[", prompt)
                self.assertEqual(lyrics in prompt, mode == "vocal")
                self.assertEqual("Lyrics:" in prompt, mode == "vocal")
                self.assertEqual(set(body), {"model", "messages", "stream"})
                self.assertEqual(body["model"], engine.MODEL)
                self.assertTrue(body["stream"])
                self.assertEqual(self.adapter.counts[mode], 1)
                log = "\n".join(logs.output)
                self.assertIn(f"bard='Mikael' location='The Bannered Mare, Hold: Whiterun' region=whiterun via=suffix-table mode={mode}", log)
                self.assertNotIn(lyrics, log)

    def test_wordless_counter_and_log_through_http(self):
        incoming = self.real_request()
        incoming["messages"][0]["content"] = incoming["messages"][0]["content"].replace(
            "The Bannered Mare, Hold: Whiterun", "The Frozen Hearth, Hold: Winterhold College")
        self.settings.write_text("instrumentalPercent: 0\n")
        with self.assertLogs(engine.LOG, level="INFO") as logs:
            with self.post(incoming) as response:
                self.assert_duration_stream(response.read())
        prompt = self.received[0][0]["messages"][0]["content"]
        self.assertIn("Wordless singing with vocables only; no lyrics, sentences or spoken words.", prompt)
        self.assertNotIn("Lyrics:", prompt)
        self.assertNotIn("The lantern warms", prompt)
        self.assertNotIn("HM1[", prompt)
        self.assertEqual(self.adapter.counts["wordless"], 1)
        self.assertEqual(self.adapter.counts["vocal"], 0)
        self.assertIn("region=winterhold via=suffix-registry mode=wordless lyrics_forwarded=False", "\n".join(logs.output))

    def test_excluded_counter_and_log_through_http_in_both_modes(self):
        incoming = self.real_request()
        incoming["messages"][0]["content"] = incoming["messages"][0]["content"].replace(
            "Mikael||The Bannered Mare, Hold: Whiterun", "Lurbuk||Moorside Inn, Hold: Hjaalmarch")
        for index, (percent, mode) in enumerate(((0, "vocal"), (100, "instrumental")), 1):
            self.settings.write_text(f"instrumentalPercent: {percent}\n")
            with self.assertLogs(engine.LOG, level="INFO") as logs:
                with self.post(incoming) as response:
                    self.assert_duration_stream(response.read())
            self.assertEqual(self.received[-1][0], engine.transform(incoming, mode))
            self.assertNotIn("HM1[", self.received[-1][0]["messages"][0]["content"])
            self.assertEqual(self.adapter.counts["excluded"], index)
            self.assertEqual(self.adapter.counts[mode], 0)
            self.assertIn(f"region=hjaalmarch via=suffix-table mode=excluded lyrics_forwarded={mode == 'vocal'}", "\n".join(logs.output))

    def test_marker_missing_returns_502_without_upstream_and_counts_error(self):
        incoming = self.real_request()
        incoming["messages"][0]["content"] = incoming["messages"][0]["content"].replace(
            "HM1[Mikael||The Bannered Mare, Hold: Whiterun]", "")
        with self.assertLogs(engine.LOG, level="WARNING") as logs:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.post(incoming)
        self.assertEqual(caught.exception.code, 502)
        caught.exception.close()
        self.assertEqual(self.received, [])
        self.assertEqual(self.adapter.counts["errors"], 1)
        self.assertIn("Hold Music requires one request-scoped bard/location marker", "\n".join(logs.output))

    def test_http_exception_before_headers_counts_error_and_logs_only_type(self):
        with mock.patch.object(self.adapter.opener, "open", side_effect=http.client.BadStatusLine("PRIVATE_UPSTREAM_TEXT")):
            with self.assertLogs(engine.LOG, level="WARNING") as logs:
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.post(self.real_request())
        self.assertEqual(caught.exception.code, 502)
        caught.exception.close()
        self.assertEqual(self.adapter.counts["errors"], 1)
        self.assertEqual(self.received, [])
        self.assertEqual(logs.output, ["WARNING:hold_music_adapter:Music request stopped: BadStatusLine"])

    def test_incomplete_stream_counts_error_without_retry_or_private_log_text(self):
        self.settings.write_text("instrumentalPercent: 100\nreportDuration: false\n")
        upstream = mock.MagicMock()
        upstream.__enter__.return_value = upstream
        upstream.status = 200
        upstream.headers = {"Content-Type": "text/event-stream"}
        upstream.read1.side_effect = [b"partial stream", http.client.IncompleteRead(b"PRIVATE_AUDIO", 42)]
        with mock.patch.object(self.adapter.opener, "open", return_value=upstream) as opened:
            with self.assertLogs(engine.LOG, level="WARNING") as logs:
                with self.post(self.real_request()) as response:
                    self.assertEqual(response.read(), b"partial stream")
        opened.assert_called_once()
        self.assertEqual(self.adapter.counts["errors"], 1)
        self.assertEqual(self.adapter.counts["upstream_http_200"], 0)
        self.assertEqual(logs.output, ["WARNING:hold_music_adapter:Music request stopped: IncompleteRead"])

    def test_health_reports_compatible_protocol_and_current_build(self):
        info = service.health(self.url)
        self.assertEqual(info["version"], "0.2.0")
        self.assertEqual(info["build"], "0.2.2")

    def test_buffered_timeout_flushes_and_retains_error_accounting_and_slots(self):
        upstream = mock.MagicMock()
        upstream.__enter__.return_value = upstream
        upstream.status = 200
        upstream.headers = {"Content-Type": "text/event-stream"}
        prefix = self.stream.removesuffix(b"data: [DONE]\n\n")
        upstream.read1.side_effect = [prefix, engine.socket.timeout("PRIVATE_UPSTREAM_TEXT")]
        with mock.patch.object(self.adapter.opener, "open", return_value=upstream) as opened:
            with self.assertLogs(engine.LOG, level="WARNING") as logs:
                with self.post() as response:
                    self.assertEqual(response.read(), engine.content_event({"role": "assistant", "content": ""}) + prefix)
        opened.assert_called_once()
        self.assertEqual(self.adapter.counts["errors"], 1)
        self.assertEqual(self.adapter.counts["upstream_http_200"], 0)
        self.assertEqual(self.adapter.counts["duration_reported"], 0)
        self.assertNotIn("PRIVATE_UPSTREAM_TEXT", "\n".join(logs.output))
        self.assertIn("Music stream disconnected or timed out; no adapter retry", "\n".join(logs.output))
        self.assertTrue(self.adapter.slot.acquire(blocking=False))
        self.assertTrue(self.adapter.slot.acquire(blocking=False))
        try:
            self.assertFalse(self.adapter.slot.acquire(blocking=False))
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.post()
            self.assertEqual(caught.exception.code, 429)
            caught.exception.close()
        finally:
            self.adapter.slot.release()
            self.adapter.slot.release()

    def test_browser_origins_and_wrong_routes_cannot_generate_music(self):
        for kwargs in ({"headers": {"Origin": "https://example.com"}},
                       {"url": f"http://127.0.0.1:{self.adapter.port}/v1/chat/completions"}):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.post(**kwargs)
            self.assertEqual(caught.exception.code, 403)
        self.assertEqual(self.received, [])


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'BardSinging.yaml'
        self.config.write_text(CONFIG)
        self.settings = self.root / 'settings.yaml'
        self.settings.write_text('instrumentalPercent: 50\n')

    def test_hidden_helper_is_independent_reused_and_stopped(self):
        adapter = service.ProcessAdapter(sys.executable, self.config, self.settings,
                                         self.root / 'runtime', self.root / 'service.log')
        self.addCleanup(adapter.stop)
        endpoint = adapter.start()
        info = service.health(endpoint)
        self.assertNotEqual(info['pid'], os.getpid())
        self.assertEqual(adapter.start(), endpoint)
        self.assertEqual(service.health(endpoint)['pid'], info['pid'])
        self.assertEqual(info['build'], '0.2.2')
        self.assertIn('build=0.2.2', (self.root / 'service.log').read_text())
        status = adapter.status_file
        adapter.stop()
        self.assertFalse(status.exists())
        with self.assertRaises(OSError):
            service.health(endpoint)

    @unittest.skipUnless(os.name == 'nt', 'Windows embedded-interpreter regression')
    def test_responds_while_host_holds_gil_and_stops_when_host_exits(self):
        # PyDLL deliberately retains the host interpreter GIL during Sleep.
        # An HTTP thread in that interpreter would be unable to answer.
        owner = self.root / 'owner.py'
        ready = self.root / 'ready.json'
        owner.write_text('''import ctypes, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from service import ProcessAdapter
root = Path(sys.argv[2])
adapter = ProcessAdapter(sys.executable, root/'BardSinging.yaml', root/'settings.yaml',
                         root/'runtime', root/'service.log')
url = adapter.start()
(root/'ready.json').write_text(json.dumps({'url':url, 'status':str(adapter.status_file)}))
ctypes.PyDLL('kernel32').Sleep(2500)
# Exit without stop(): the helper must notice the owner is gone.
''', encoding='utf-8')
        child = subprocess.Popen([sys.executable, '-I', str(owner), str(Path(service.__file__).parent),
                                  str(self.root)], creationflags=subprocess.CREATE_NO_WINDOW,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def cleanup():
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=4)
        self.addCleanup(cleanup)
        deadline = time.monotonic() + 8
        while not ready.exists() and time.monotonic() < deadline:
            self.assertIsNone(child.poll())
            time.sleep(0.05)
        data = json.loads(ready.read_text())
        time.sleep(0.1)
        for _ in range(3):
            self.assertIsNone(child.poll())
            self.assertEqual(service.health(data['url'])['service'], 'hold-music')
            time.sleep(0.1)
        child.wait(timeout=5)
        status = Path(data['status'])
        deadline = time.monotonic() + 5
        while status.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(status.exists(), 'Orphan helper did not clean up')
        with self.assertRaises(OSError):
            service.health(data['url'])


if __name__ == "__main__":
    unittest.main()
