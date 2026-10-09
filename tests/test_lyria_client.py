import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from hold_music import lyria_client as client
from mp3_fixture import mp3_frames, id3v2_tag, ID3V1


def event(value):
    return b'data: ' + json.dumps(value).encode() + b'\n\n'


def audio_stream(audio=None, *, usage=True):
    encoded = base64.b64encode(mp3_frames() if audio is None else audio).decode()
    chunks = [b': heartbeat\n\n']
    # Split within base64 quads and across choices, not independently encoded pieces.
    for start in range(0, len(encoded), 913):
        fragment = encoded[start:start + 913]
        chunks.append(event({'id': 'gen-offline', 'choices': [
            {'delta': {'audio': {'data': fragment[:7]}}},
            {'delta': {'audio': {'data': fragment[7:]}}}]}))
    if usage:
        chunks.append(event({'usage': {'cost': 0.073, 'completion_tokens': 12}}))
    chunks.append(b'data: [DONE]\n\n')
    return b''.join(chunks)


@contextmanager
def server(body, status=200):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, self.headers, json.loads(self.rfile.read(
                int(self.headers['Content-Length'])))))
            self.send_response(status)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('X-Request-ID', 'header-id')
            if status in (301, 302, 307, 308):
                self.send_header('Location', '/redirected')
            self.end_headers()
            try:
                for start in range(0, len(body), 127):
                    self.wfile.write(body[start:start + 127])
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}/music', requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


class LyriaClientTests(unittest.TestCase):
    def test_stream_request_audio_usage_and_id(self):
        audio = id3v2_tag() + mp3_frames() + ID3V1
        with server(audio_stream(audio)) as (url, requests):
            result = client.generate('Offline prompt', key='fixture-key', upstream=url)
        self.assertEqual(len(requests), 1)
        _, headers, body = requests[0]
        self.assertEqual(headers['Authorization'], 'Bearer fixture-key')
        self.assertEqual(headers['X-Title'], 'Hold Music - SkyrimNet')
        self.assertEqual(headers['Accept'], 'text/event-stream')
        self.assertEqual(body, {'model': client.MODEL, 'messages': [
            {'role': 'user', 'content': 'Offline prompt'}], 'stream': True})
        self.assertEqual(result.audio_bytes, audio)
        self.assertAlmostEqual(result.duration_seconds, 200 * 1152 / 44100)
        self.assertEqual(result.usage['cost'], .073)
        self.assertEqual(result.request_id, 'gen-offline')

    def test_absent_usage_and_header_id(self):
        body = audio_stream(usage=False).replace(b'"id": "gen-offline", ', b'')
        with server(body) as (url, _):
            result = client.generate('test', key='fixture', upstream=url)
        self.assertIsNone(result.usage)
        self.assertEqual(result.request_id, 'header-id')

    def test_http_status_and_redirects_never_retry(self):
        for status in (302, 307, 401, 429, 500):
            with self.subTest(status=status), server(b'private upstream text', status) as (url, requests):
                with self.assertRaises(client.HTTPStatusError) as error:
                    client.generate('test', key='fixture-secret', upstream=url)
                self.assertEqual(error.exception.status, status)
                self.assertNotIn('private', str(error.exception))
                self.assertEqual(len(requests), 1)

    def test_sse_failures(self):
        cases = [
            (b'data: oops\n\n', client.StreamError),
            (event([]), client.StreamError),
            (event({'error': {'message': 'private'}}), client.StreamError),
            (event({'choices': {}}), client.StreamError),
            (audio_stream().replace(b'data: [DONE]\n\n', b''), client.StreamError),
            (b'data: [DONE]\n\n', client.MissingAudioError),
            (event({'choices': [{'delta': {'audio': {'data': '@@'}}}]}) +
             b'data: [DONE]\n\n', client.InvalidBase64Error),
            (audio_stream(b'not an mp3'), client.ZeroDurationError),
        ]
        for body, expected in cases:
            with self.subTest(expected=expected), server(body) as (url, requests):
                with self.assertRaises(expected):
                    client.generate('test', key='fixture', upstream=url)
                self.assertEqual(len(requests), 1)

    def test_response_cap_includes_non_audio_bytes(self):
        with server(b':' + b'x' * 1000) as (url, requests), \
                patch.object(client, 'MAX_RESPONSE_BYTES', 100):
            with self.assertRaises(client.ResponseTooLargeError):
                client.generate('test', key='fixture', upstream=url)
            self.assertEqual(len(requests), 1)

    def test_timeout_is_forwarded_and_transport_failure_is_sanitized(self):
        with patch.object(client.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = TimeoutError('fixture-secret')
            with self.assertRaisesRegex(client.StreamError, '^Upstream transport failed$'):
                client.generate('test', key='fixture-secret')
            self.assertEqual(build.return_value.open.call_args.kwargs['timeout'], 300)
            self.assertEqual(build.return_value.open.call_count, 1)

    def test_mp3_versions_and_damage_match_adapter(self):
        for version, rate, samples in ((1, 44100, 1152), (2, 22050, 576), (2.5, 11025, 576)):
            self.assertAlmostEqual(client.mp3_duration(mp3_frames(version, count=3, padding=True)),
                                   3 * samples / rate)
        self.assertEqual(client.mp3_duration(b'bad'), 0)
        self.assertAlmostEqual(client.mp3_duration(mp3_frames(count=2)[:-1]), 1152 / 44100)

    def test_narrow_key_reader_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            path = Path(temp) / 'BardSinging.yaml'
            for raw, expected in [('fixture-key # comment', 'fixture-key'),
                                  ('"fixture-key" # comment', 'fixture-key'),
                                  ("'fixture''key'", "fixture'key")]:
                path.write_text('bard_singing:\n  openrouter:\n    api_key: ' + raw + '\n')
                self.assertEqual(client.read_openrouter_key(path), expected)
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'environment-fixture'}):
                self.assertEqual(client.read_openrouter_key('missing'), 'environment-fixture')
            for text in ['bard_singing:\n  openrouter:\n    api_key: true\n',
                         'bard_singing:\n  openrouter:\n    api_key: a\n    api_key: b\n',
                         'bard_singing:\n  openrouter:\n    api_key: |\n      secret\n']:
                path.write_text(text)
                with self.assertRaises(ValueError):
                    client.read_openrouter_key(path)
            with self.assertRaises(ValueError):
                client.read_openrouter_key()
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'bad\nkey'}):
            with self.assertRaises(ValueError):
                client.read_openrouter_key()


if __name__ == '__main__':
    unittest.main()
