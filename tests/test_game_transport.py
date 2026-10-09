import base64
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
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game_adapter" / "hold_music_adapter"))
import engine
import service


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
        self.assertIn("entirely instrumental", text)

    def test_vocal_keeps_gender_and_lyrics_verbatim(self):
        lyric = "[Verse]\nZohra’s road — and a lute.\n[Chorus]\nSing!\n"
        for gender in ("Male", "Female"):
            text = engine.transform(sample(lyric, gender), "vocal")["messages"][0]["content"]
            self.assertIn("One " + gender.lower() + " singer", text)
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
        with self.assertRaises(ValueError):
            self.bridge.reconcile()
        self.assertEqual(before, self.source.read_bytes())
        self.assertTrue((self.bridge.runtime / "BardSinging.conflict.yaml").exists())

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
        # A tiny fake audio payload. No music is generated and no paid API is called.
        audio = base64.b64encode(b"offline-audio-fixture").decode()
        self.stream = ("data: " + json.dumps({"id": "fixture-1", "choices": [{"delta": {"audio": {"data": audio}}}]}) + "\n\ndata: [DONE]\n\n").encode()

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
                    for i in range(0, len(fixture.stream), 7):
                        self.wfile.write(fixture.stream[i:i+7])
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

    def test_instrumental_through_http_and_sse_audio_is_byte_identical(self):
        with self.post() as response:
            self.assertEqual(response.read(), self.stream)
        body, headers = self.received[0]
        self.assertNotIn("Lyrics:", body["messages"][0]["content"])
        self.assertEqual(headers["Authorization"], "Bearer fake-key-for-local-tests")
        self.assertEqual(self.adapter.counts["instrumental"], 1)

    def test_vocal_branch_through_http(self):
        self.settings.write_text("instrumentalPercent: 0\n")
        with self.post() as response:
            self.assertEqual(response.read(), self.stream)
        self.assertTrue(self.received[0][0]["messages"][0]["content"].endswith("Lyrics:\n[Verse]\nThe road bends toward the sea."))

    def test_upstream_error_is_not_retried_or_changed_to_a_vocal(self):
        self.status = 429
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post()
        self.assertEqual(caught.exception.code, 429)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.adapter.counts["vocal"], 0)

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
