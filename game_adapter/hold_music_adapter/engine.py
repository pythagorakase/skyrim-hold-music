"""Hold Music's out-of-process music adapter. Python standard library only.

The game uses its supported local music URL. This adapter constructs a fresh
Lyria request, then reports the recording duration before relaying its audio.
No process injection, Papyrus, or database writes. A standalone Python helper
keeps the network listener independent of MO2's embedded interpreter.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import http.client
import http.server
import json
import logging
import os
import re
import secrets
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

if __package__:
    from .regional import REGIONS, music_prompt, performance_mode, resolve_location_detail
    from .legacy import transform as legacy_transform
else:
    from regional import REGIONS, music_prompt, performance_mode, resolve_location_detail
    from legacy import transform as legacy_transform

# Protocol compatibility: MO2 keeps the VERSION imported at startup while the
# independent helper can be hot-swapped. BUILD identifies the updated helper.
VERSION = "0.2.0"
BUILD = "0.2.2"
UPSTREAM = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/lyria-3-pro-preview"
PALETTE_PATH = Path(__file__).parent / 'palette-data.json'
LOCATIONS_PATH = Path(__file__).parent / 'locations.json'
CONTEXT_TAG = re.compile(r'HM1\[([^\[\]\r\n|]{1,160})\|\|([^\[\]\r\n|]{1,240})\]')
LOG = logging.getLogger("hold_music_adapter")
MANAGED = (
    ("bard_singing", "provider"),
    ("bard_singing", "acestep_local", "base_url"),
    ("bard_singing", "acestep_local", "model"),
)


def read_text(path):
    # Preserve line endings, but strip a leading BOM for parsing. ConfigOverlay
    # tracks that BOM separately and restores it on derived file writes.
    return Path(path).read_bytes().decode("utf-8-sig")


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def scalar_location(text, path):
    """Locate one scalar by its indentation path, without reserializing YAML.

    This deliberately accepts only the block mappings used by SkyrimNet's
    generated config. Unexpected YAML fails before routing is changed.
    """
    stack = []
    hits = []
    offset = 0
    for line in text.splitlines(keepends=True):
        m = re.match(r"^( *)([A-Za-z_][\w -]*):([^\r\n]*)(?:\r?\n)?$", line)
        if m:
            indent = len(m[1])
            while stack and stack[-1][0] >= indent:
                stack.pop()
            address = tuple(key for _, key in stack) + (m[2],)
            raw = m[3].strip()
            if address == tuple(path):
                hits.append((offset + m.start(3), offset + m.end(3), raw))
            if not raw or raw.startswith("#"):
                stack.append((indent, m[2]))
        offset += len(line)
    if len(hits) != 1:
        raise ValueError("Missing or ambiguous config field: " + ".".join(path))
    return hits[0]


def parse_scalar(raw):
    if raw.startswith('"'):
        value, end = json.JSONDecoder().raw_decode(raw)
        if raw[end:].strip() and not raw[end:].lstrip().startswith("#"):
            raise ValueError("Unsupported quoted YAML scalar")
        return value
    if raw.startswith("'"):
        m = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", raw)
        if not m:
            raise ValueError("Unsupported quoted YAML scalar")
        return m[1].replace("''", "'")
    value = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    if value in ("true", "false"):
        return value == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if not value or value[0] in "&*!|>{[" or value in ("null", "~"):
        raise ValueError("Unsupported YAML scalar")
    return value


def get_scalar(text, path):
    return parse_scalar(scalar_location(text, path)[2])


def replace_raw_scalar(text, path, raw):
    start, end, _ = scalar_location(text, path)
    return text[:start] + " " + raw + text[end:]


class ConfigOverlay:
    """One VFS-only config override; preserve dashboard edits on game exit.

    The source is never replaced with a localhost route. Baseline/overlay files
    stay under the profile, outside the source repository and distributable.
    Conflicts preserve dashboard edits in a recovery copy and clear the baseline
    without raising, so the next prepare can keep the music route active.
    """
    def __init__(self, source, runtime):
        self.source = Path(source)
        self.runtime = Path(runtime)
        self.overlay = self.runtime / "BardSinging.yaml"
        self.baseline = self.runtime / "BardSinging.baseline.yaml"
        self.source_bom = False

    def _write(self, path, text):
        atomic_text(path, ("\ufeff" if self.source_bom else "") + text)

    def prepare(self, endpoint):
        self.reconcile()
        source_bytes = self.source.read_bytes()
        self.source_bom = source_bytes.startswith(b"\xef\xbb\xbf")
        original = source_bytes.decode("utf-8-sig")
        if get_scalar(original, MANAGED[0]) != "openrouter":
            raise ValueError("Hold Music currently requires the OpenRouter music provider")
        if get_scalar(original, ("bard_singing", "openrouter", "model")) != MODEL:
            raise ValueError("Hold Music currently requires the verified Lyria 3 Pro model")
        # Check all paths before writing either file.
        for path in MANAGED:
            scalar_location(original, path)
        changed = original
        for path, value in zip(MANAGED, ("acestep_local", endpoint, MODEL)):
            changed = replace_raw_scalar(changed, path, json.dumps(value))
        self._write(self.baseline, original)
        self._write(self.overlay, changed)
        return self.overlay

    def reconcile(self):
        """Restore routing; preserve conflicting edits without blocking a launch."""
        if not self.baseline.exists() or not self.overlay.exists():
            return
        baseline_bytes = self.baseline.read_bytes()
        self.source_bom = baseline_bytes.startswith(b"\xef\xbb\xbf")
        original = baseline_bytes.decode("utf-8-sig")
        candidate = read_text(self.overlay)
        for path in MANAGED:
            raw = scalar_location(original, path)[2]
            candidate = replace_raw_scalar(candidate, path, raw)
        # Compare semantic scalar whitespace, as prepare normalizes one space.
        normalized = original
        for path in MANAGED:
            normalized = replace_raw_scalar(normalized, path, scalar_location(original, path)[2])
        if candidate != normalized:
            if read_text(self.source) != original:
                self._write(self.runtime / "BardSinging.conflict.yaml", candidate)
                LOG.warning("Bard settings changed in two places; preserved a conflict copy")
                self.baseline.unlink()
                return
            self._write(self.source, candidate)
            LOG.info("Preserved Bard Singing dashboard edits; restored the three original routing fields")
        self.baseline.unlink()


class ModeSelector:
    """A random per-install seed makes each distinct request a stable coin flip.

    Retries retain their mode, including after restarting MO2. No lyrics, keys,
    or per-request history are persisted in this selection state.
    """
    def __init__(self, seed):
        if len(seed) != 32:
            raise ValueError("Invalid mode-selection seed")
        self.seed = seed

    @classmethod
    def from_file(cls, path):
        path = Path(path)
        if not path.exists():
            atomic_text(path, secrets.token_hex(32))
        return cls(bytes.fromhex(read_text(path).strip()))

    def choose(self, request, percent):
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
            raise ValueError("Instrumental percentage must be an integer from 0 to 100")
        canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest = hmac.digest(self.seed, canonical.encode("utf-8"), "sha256")
        coin = int.from_bytes(digest[:8], "big")
        return "instrumental" if coin * 100 < percent * (1 << 64) else "vocal"


def context(request):
    """Read the request's own context marker; never guess from a nearby actor."""
    if not isinstance(request, dict) or request.get('model') != MODEL:
        raise ValueError('Unexpected music model')
    messages = request.get('messages')
    if not isinstance(messages, list) or len(messages) != 1:
        raise ValueError('Expected one bard music message')
    message = messages[0]
    if not isinstance(message, dict) or message.get('role') != 'user' or not isinstance(message.get('content'), str):
        raise ValueError('Unexpected bard music message format')
    text = message['content']
    voice = re.match(r'\s*(male|female)\s+vocal\.\s*', text, re.I)
    parts = re.split(r'\r?\n\s*Lyrics:\s*\r?\n', text, maxsplit=1, flags=re.I)
    if not voice or len(parts) != 2 or not parts[1].strip():
        raise ValueError('Unrecognized SkyrimNet vocal/lyrics format')
    tags = list(CONTEXT_TAG.finditer(parts[0]))
    if len(tags) != 1:
        raise ValueError('Hold Music requires one request-scoped bard/location marker')
    tag = tags[0]
    bard, location = tag[1].strip(), tag[2].strip()
    if not bard or not location or 'HM1[' in parts[1]:
        raise ValueError('Empty routing context or routing metadata in lyrics')
    registry = json.loads(LOCATIONS_PATH.read_text(encoding='utf-8'))
    region, rule = resolve_location_detail(location, registry)
    return {'bard': bard, 'location': location, 'region': region, 'rule': rule,
            'excluded': bard.casefold() == 'lurbuk', 'gender': voice[1].lower(),
            'lyrics': parts[1], 'original_content': text,
            'tag_start': tag.start(), 'tag_end': tag.end()}


def transform(request, mode, details=None):
    if details is None:
        details = context(request)
    if mode not in ('instrumental', 'vocal'):
        raise ValueError('Unknown performance mode')
    if details['excluded']:
        text = details['original_content']
        # Retain the exact pre-regional treatment, including its 50/50 policy.
        clean = text[:details['tag_start']] + text[details['tag_end']:]
        return legacy_transform({'model': MODEL, 'stream': True,
                                 'messages': [{'role': 'user', 'content': clean}]}, mode)
    else:
        prompt = music_prompt(details['region'], mode, details['gender'],
                              details['lyrics'], palette_path=PALETTE_PATH)
    return {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'stream': True}


def load_settings(path):
    if not Path(path).exists():
        return 50, True
    text = read_text(path)
    percent = get_scalar(text, ("instrumentalPercent",))
    report = True
    if re.search(r'^ *reportDuration:', text, re.M):
        report = get_scalar(text, ("reportDuration",))
        if not isinstance(report, bool):
            raise ValueError("reportDuration must be a boolean")
    return percent, report


def mp3_duration(data: bytes) -> float:
    """Sum complete MPEG-1/2/2.5 Layer III frames; never guess past damage."""
    offset = 0
    duration = 0.0
    if data.startswith(b"ID3"):
        if len(data) < 10 or any(value & 0x80 for value in data[6:10]):
            return 0.0
        size = 0
        for value in data[6:10]:
            size = (size << 7) | value
        offset = 10 + size
        if data[3] == 4 and data[5] & 0x10:  # ID3v2.4 footer
            offset += 10
    while offset + 4 <= len(data):
        if data[offset:offset + 3] == b"TAG":
            break
        header = int.from_bytes(data[offset:offset + 4], "big")
        version = (header >> 19) & 3
        layer = (header >> 17) & 3
        bitrate_index = (header >> 12) & 15
        rate_index = (header >> 10) & 3
        if (header >> 21 != 0x7FF or version == 1 or layer != 1
                or bitrate_index == 15 or rate_index == 3
                or header & 3 == 2):
            break
        if bitrate_index == 0:  # Free-format needs a different frame scanner.
            return 0.0
        rates = (44100, 48000, 32000)
        sample_rate = rates[rate_index] // {3: 1, 2: 2, 0: 4}[version]
        bitrates = ((0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
                    if version == 3 else
                    (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160))
        samples = 1152 if version == 3 else 576
        length = (144 if version == 3 else 72) * bitrates[bitrate_index] * 1000 // sample_rate
        length += (header >> 9) & 1
        if offset + length > len(data):
            break
        duration += samples / sample_rate
        offset += length
    return duration


def content_event(delta):
    return ("data: " + json.dumps({"choices": [{"index": 0, "delta": delta,
                                               "finish_reason": None}]},
                                  separators=(",", ":")) + "\n\n").encode()


def buffered_duration(lines):
    """Return duration, decoded size and a body-free fallback reason."""
    fragments = []
    done = False
    for line in lines:
        if not line.startswith(b"data:"):
            continue
        payload = line[5:].strip()
        if payload == b"[DONE]":
            done = True
            continue
        try:
            event = json.loads(payload)
        except (ValueError, UnicodeError):
            return 0.0, 0, "invalid SSE JSON"
        if not isinstance(event, dict):
            return 0.0, 0, "invalid SSE event"
        if isinstance(event.get("error"), dict):
            return 0.0, 0, "upstream error event"
        choices = event.get("choices", [])
        if not isinstance(choices, list):
            return 0.0, 0, "invalid SSE choices"
        for choice in choices:
            delta = choice.get("delta") if isinstance(choice, dict) else None
            audio = delta.get("audio") if isinstance(delta, dict) else None
            fragment = audio.get("data") if isinstance(audio, dict) else None
            if isinstance(fragment, str):
                fragments.append(fragment)
    if not done:
        return 0.0, 0, "missing [DONE]"
    if not fragments or not any(fragments):
        return 0.0, 0, "no audio"
    try:
        audio = base64.b64decode("".join(fragments), validate=True)
    except (ValueError, binascii.Error):
        return 0.0, 0, "invalid audio base64"
    duration = mp3_duration(audio)
    return duration, len(audio), None if duration else "unrecognized MP3 duration"


def relay_duration(response, output, request_id, count):
    """Buffer upstream while a small writer thread keeps SkyrimNet alive."""
    output.write(content_event({"role": "assistant", "content": ""}))
    output.flush()
    stopped = threading.Event()
    heartbeat_errors = []

    def heartbeat():
        while not stopped.wait(2):
            try:
                output.write(content_event({"content": "."}))
                output.flush()
            except OSError as exc:
                heartbeat_errors.append(exc)
                return

    thread = threading.Thread(target=heartbeat, name="HoldMusicHeartbeat", daemon=True)
    thread.start()
    chunks = []
    total = 0
    failure = None
    try:
        while True:
            chunk = response.read1(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > 64_000_000:
                raise ValueError("Unexpectedly large music response")
            chunks.append(chunk)
            if heartbeat_errors:
                raise heartbeat_errors[0]
    except (ValueError, TypeError, OSError, http.client.HTTPException) as exc:
        failure = exc
    finally:
        stopped.set()
        thread.join()
    # Stop the sole concurrent writer before emitting metadata or upstream bytes.
    lines = b"".join(chunks).splitlines(keepends=True)
    if failure is None and heartbeat_errors:
        failure = heartbeat_errors[0]
    if failure is None:
        duration, audio_bytes, reason = buffered_duration(lines)
    else:
        duration, audio_bytes, reason = 0.0, 0, type(failure).__name__
    reported = reason is None and duration > 0.0
    seconds = round(duration)
    if reason:
        LOG.warning("request=%s duration fallback: %s", request_id, reason)
    if reported:
        output.write(content_event({"content": f"\n\n## Metadata\n**Duration:** {seconds}s\n"}))
        output.flush()
        count("duration_reported")
    LOG.info("request=%s duration_seconds=%s audio_bytes=%s reported=%s",
             request_id, seconds, audio_bytes, str(reported).lower())
    for line in lines:
        output.write(line)
    output.flush()
    if failure is not None:
        raise failure
    return total


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Upstream redirects are disabled", headers, fp)


class Adapter:
    def __init__(self, credential_file, settings_file, runtime, port=18765, upstream=UPSTREAM):
        self.credential_file = Path(credential_file)
        self.settings_file = Path(settings_file)
        self.selector = ModeSelector.from_file(Path(runtime) / "mode-seed.txt")
        self.port = port
        self.upstream = upstream  # Tests use a local fixture; the installed plugin never overrides this.
        self.token = secrets.token_urlsafe(24)
        self.route = "/hold-music/" + self.token + "/v1/chat/completions"
        self.server = None
        self.thread = None
        self.slot = threading.BoundedSemaphore(2)
        self.counts = {"vocal": 0, "instrumental": 0, "wordless": 0, "excluded": 0, "upstream_http_200": 0, "errors": 0, "duration_reported": 0}
        self.lock = threading.Lock()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def count(self, name):
        with self.lock:
            self.counts[name] += 1

    def start(self):
        adapter = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_):
                pass  # Never log the local capability URL, body, key, or audio.

            def setup(self):
                super().setup()
                self.connection.settimeout(330)

            def json_error(self, status, message):
                body = json.dumps({"error": {"message": message}}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def allowed(self):
                return (self.headers.get("Host") == f"127.0.0.1:{adapter.port}"
                        and not self.headers.get("Origin")
                        and not self.headers.get("Sec-Fetch-Site"))

            def do_GET(self):
                if self.path != "/health" or not self.allowed():
                    self.json_error(404, "Not found")
                    return
                with adapter.lock:
                    body = json.dumps({"service": "hold-music", "version": VERSION, "build": BUILD, "pid": os.getpid(), "counts": adapter.counts}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.path != adapter.route or not self.allowed():
                    self.json_error(403, "Local music route required")
                    return
                if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
                    self.json_error(415, "A length-delimited JSON request is required")
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2_000_000:
                        raise ValueError()
                except ValueError:
                    self.json_error(413, "Invalid request size")
                    return
                if not adapter.slot.acquire(blocking=False):
                    self.json_error(429, "Two music requests are already active")
                    return
                sent_headers = False
                try:
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError("Incomplete request")
                    incoming = json.loads(raw)
                    percent, report_duration = load_settings(adapter.settings_file)
                    mode = adapter.selector.choose(incoming, percent)
                    details = context(incoming)
                    outgoing = transform(incoming, mode, details)
                    actual_mode = 'excluded' if details['excluded'] else performance_mode(details['region'], mode)
                    credential = get_scalar(read_text(adapter.credential_file), ("bard_singing", "openrouter", "api_key"))
                    if not isinstance(credential, str) or not credential or "\n" in credential or "\r" in credential:
                        raise ValueError("Missing OpenRouter music key")
                    request_id = hashlib.sha256(raw).hexdigest()[:12]
                    body = json.dumps(outgoing, ensure_ascii=False).encode("utf-8")
                    req = urllib.request.Request(adapter.upstream, data=body, headers={
                        "Authorization": "Bearer " + credential,
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                        "X-Title": "Hold Music - SkyrimNet",
                    }, method="POST")
                    adapter.count(actual_mode)
                    LOG.info("request=%s bard=%r location=%r region=%s via=%s mode=%s lyrics_forwarded=%s percent=%s",
                             request_id, details['bard'], details['location'], details['region'], details['rule'], actual_mode,
                             actual_mode == 'vocal' or (actual_mode == 'excluded' and mode == 'vocal'), percent)
                    # No extra retry layer: an uncertain paid generation must not be duplicated here.
                    with adapter.opener.open(req, timeout=300) as response:
                        if response.status != 200:
                            raise urllib.error.HTTPError(req.full_url, response.status, "Unexpected upstream status", response.headers, None)
                        self.send_response(200)
                        self.send_header("Content-Type", response.headers.get("Content-Type", "text/event-stream"))
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "close")
                        self.end_headers()
                        sent_headers = True
                        total = 0
                        if report_duration:
                            total = relay_duration(response, self.wfile, request_id, adapter.count)
                        while not report_duration:
                            chunk = response.read1(65536)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > 64_000_000:
                                raise ValueError("Unexpectedly large music response")
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        adapter.count("upstream_http_200")
                        LOG.info("request=%s response_forwarded bytes=%s", request_id, total)
                except (BrokenPipeError, ConnectionResetError, socket.timeout):
                    adapter.count("errors")
                    LOG.warning("Music stream disconnected or timed out; no adapter retry")
                except urllib.error.HTTPError as exc:
                    adapter.count("errors")
                    LOG.warning("OpenRouter music HTTP status=%s; no adapter retry", exc.code)
                    if not sent_headers:
                        self.json_error(exc.code if 400 <= exc.code < 600 else 502, f"OpenRouter music returned HTTP {exc.code}")
                except (ValueError, TypeError, OSError, urllib.error.URLError, http.client.HTTPException) as exc:
                    adapter.count("errors")
                    # Validation errors are authored locally; never include the input body.
                    reason = str(exc) if isinstance(exc, ValueError) and type(exc) is ValueError else type(exc).__name__
                    LOG.warning("Music request stopped: %s", reason)
                    if not sent_headers:
                        self.json_error(502, "Hold Music could not complete this music request; see its local log")
                finally:
                    adapter.slot.release()

        class Server(http.server.ThreadingHTTPServer):
            daemon_threads = True
            # Windows SO_REUSEADDR can allow overlapping listeners. Refuse collisions.
            allow_reuse_address = False

        self.server = Server(("127.0.0.1", self.port), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, name="HoldMusicMusic", daemon=True)
        self.thread.start()
        LOG.info("Local music adapter ready on loopback port %s", self.port)
        return f"http://127.0.0.1:{self.port}" + self.route

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self.server = None
