import base64
import http.client
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game_adapter/hold_music_adapter"))
import engine
from mp3_fixture import mp3_frames


class DurationRelayTests(unittest.TestCase):
    def test_settings_defaults_and_explicit_boolean(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.yaml"
            self.assertEqual(engine.load_settings(path), (50, True))
            for setting, expected in (("", True), ("reportDuration: true\n", True),
                                      ("reportDuration: false\n", False)):
                path.write_text("instrumentalPercent: 25\n" + setting)
                self.assertEqual(engine.load_settings(path), (25, expected))
            for setting in ('"false"', '0', 'null'):
                path.write_text("instrumentalPercent: 25\nreportDuration: " + setting)
                with self.assertRaises(ValueError):
                    engine.load_settings(path)

    def test_all_choices_contribute_fragments_in_order(self):
        audio = mp3_frames()
        encoded = base64.b64encode(audio).decode()
        event = {"choices": [{"delta": {"audio": {"data": fragment}}}
                             for fragment in (encoded[:3], encoded[3:]) ]}
        duration, size, reason = engine.buffered_duration([
            b"data: " + json.dumps(event).encode() + b"\r\n", b"\r\n", b"data: [DONE]\r\n", b"\r\n"])
        self.assertAlmostEqual(duration, 200 * 1152 / 44100)
        self.assertEqual(size, len(audio))
        self.assertIsNone(reason)

    def test_read_failures_flush_verbatim_buffer_and_propagate_original_error(self):
        for error in (socket.timeout("PRIVATE_BODY"), http.client.IncompleteRead(b"PRIVATE_BODY", 12)):
            with self.subTest(error=type(error).__name__):
                response = mock.Mock()
                prefix = b": upstream comment\r\ndata: unfinished"
                response.read1.side_effect = [prefix[:5], prefix[5:], error]
                output = io.BytesIO()
                count = mock.Mock()
                with self.assertLogs(engine.LOG, level="WARNING") as logs:
                    with self.assertRaises(type(error)) as caught:
                        engine.relay_duration(response, output, "test-request", count)
                self.assertIs(caught.exception, error)
                self.assertEqual(output.getvalue(), engine.content_event({"role": "assistant", "content": ""}) + prefix)
                count.assert_not_called()
                self.assertNotIn("PRIVATE_BODY", "\n".join(logs.output))
                self.assertFalse(any(t.name == "HoldMusicHeartbeat" for t in threading.enumerate()))

    def test_response_cap_rejects_before_forwarding_excess_bytes(self):
        response = mock.Mock()
        response.read1.side_effect = [b"x" * 32_000_000, b"y" * 32_000_001]
        output = io.BytesIO()
        count = mock.Mock()
        with self.assertLogs(engine.LOG, level="WARNING"):
            with self.assertRaisesRegex(ValueError, "Unexpectedly large music response"):
                engine.relay_duration(response, output, "test-request", count)
        self.assertEqual(output.getvalue(), engine.content_event({"role": "assistant", "content": ""}) + b"x" * 32_000_000)
        count.assert_not_called()

    def test_malformed_event_is_preserved_without_logging_body(self):
        for payload in (b'{"PRIVATE_BODY":', b'[]', b'{"choices":42}'):
            response = mock.Mock()
            stream = b"data: " + payload + b"\n\ndata: [DONE]\n\n"
            response.read1.side_effect = [stream, b""]
            output = io.BytesIO()
            with self.assertLogs(engine.LOG, level="WARNING") as logs:
                engine.relay_duration(response, output, "test-request", mock.Mock())
            self.assertEqual(output.getvalue(), engine.content_event({"role": "assistant", "content": ""}) + stream)
            self.assertNotIn("PRIVATE_BODY", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
