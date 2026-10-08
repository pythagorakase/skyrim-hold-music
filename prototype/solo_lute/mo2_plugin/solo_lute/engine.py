"""Solo Lute's out-of-process music adapter. Python standard library only.

The game uses its supported local music URL. This adapter constructs a fresh
Lyria request, then passes the response through without decoding the audio.
No process injection, Papyrus, database writes, or external Python service.
"""
from __future__ import annotations

import hashlib
import hmac
import http.server
import json
import logging
import re
import secrets
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "0.1.0"
UPSTREAM = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/lyria-3-pro-preview"
BASE_STYLE = (
    "An intimate acoustic performance by one musician on a single gut-strung lute, "
    "drawing on Renaissance and Baroque lute repertoire. Clear plucked articulation, "
    "interweaving melody and bass, expressive ornamentation, flowing passages and "
    "natural pauses. Everything should sound playable by one performer, with natural "
    "room resonance. No additional instruments, percussion, overdubs, backing ensemble, "
    "or modern production."
)
VOCAL_STYLE = (
    "One natural, unforced singing voice, self-accompanied on lute. An expressive "
    "lute song with instrumental introductions and passages between verses. "
    "Only one voice and one lute; no backing singers, choir, or vocal doubling."
)
INSTRUMENTAL_STYLE = (
    "Entirely instrumental solo lute. Develop the melody through variations, "
    "ornamented repetitions, and interweaving musical lines. "
    "No singing, humming, vocalizations, or spoken words."
)
LOG = logging.getLogger("solo_lute")
MANAGED = (
    ("bard_singing", "provider"),
    ("bard_singing", "acestep_local", "base_url"),
    ("bard_singing", "acestep_local", "model"),
)


def read_text(path):
    # Preserve line endings and BOM; SkyrimNet sometimes rewrites its YAML.
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
    """
    def __init__(self, source, runtime):
        self.source = Path(source)
        self.runtime = Path(runtime)
        self.overlay = self.runtime / "BardSinging.yaml"
        self.baseline = self.runtime / "BardSinging.baseline.yaml"

    def prepare(self, endpoint):
        self.reconcile()
        original = read_text(self.source)
        if get_scalar(original, MANAGED[0]) != "openrouter":
            raise ValueError("Solo Lute currently requires the OpenRouter music provider")
        if get_scalar(original, ("bard_singing", "openrouter", "model")) != MODEL:
            raise ValueError("Solo Lute currently requires the verified Lyria 3 Pro model")
        # Check all paths before writing either file.
        for path in MANAGED:
            scalar_location(original, path)
        changed = original
        for path, value in zip(MANAGED, ("acestep_local", endpoint, MODEL)):
            changed = replace_raw_scalar(changed, path, json.dumps(value))
        atomic_text(self.baseline, original)
        atomic_text(self.overlay, changed)
        return self.overlay

    def reconcile(self):
        if not self.baseline.exists() or not self.overlay.exists():
            return
        original = read_text(self.baseline)
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
                atomic_text(self.runtime / "BardSinging.conflict.yaml", candidate)
                raise ValueError("Bard settings changed in two places; preserved a conflict copy")
            atomic_text(self.source, candidate)
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


def transform(request, mode):
    if not isinstance(request, dict) or request.get("model") != MODEL:
        raise ValueError("Unexpected music model")
    messages = request.get("messages")
    if not isinstance(messages, list) or len(messages) != 1:
        raise ValueError("Expected one bard music message")
    message = messages[0]
    if not isinstance(message, dict) or message.get("role") != "user" or not isinstance(message.get("content"), str):
        raise ValueError("Unexpected bard music message format")
    content = message["content"]
    # Rebuild from an allowlist, never forward the original style/voice text or
    # provider-specific fields into an instrumental request.
    if mode == "instrumental":
        prompt = BASE_STYLE + "\n\n" + INSTRUMENTAL_STYLE
    elif mode == "vocal":
        voice = re.match(r"\s*(male|female)\s+vocal\.\s*", content, re.I)
        parts = re.split(r"\r?\n\s*Lyrics:\s*\r?\n", content, maxsplit=1, flags=re.I)
        if not voice or len(parts) != 2 or not parts[1].strip():
            raise ValueError("Unrecognized SkyrimNet vocal/lyrics format")
        prompt = voice[1].capitalize() + " vocal. " + BASE_STYLE + "\n\n" + VOCAL_STYLE
        prompt += "\n\nLyrics:\n" + parts[1]
    else:
        raise ValueError("Unknown performance mode")
    return {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": True}


def load_settings(path):
    if not Path(path).exists():
        return 50
    text = read_text(path)
    return get_scalar(text, ("instrumentalPercent",))


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
        self.route = "/solo-lute/" + self.token + "/v1/chat/completions"
        self.server = None
        self.thread = None
        self.slot = threading.BoundedSemaphore(2)
        self.counts = {"vocal": 0, "instrumental": 0, "upstream_http_200": 0, "errors": 0}
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
                    body = json.dumps({"service": "solo-lute", "version": VERSION, "counts": adapter.counts}).encode()
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
                    percent = load_settings(adapter.settings_file)
                    mode = adapter.selector.choose(incoming, percent)
                    outgoing = transform(incoming, mode)
                    credential = get_scalar(read_text(adapter.credential_file), ("bard_singing", "openrouter", "api_key"))
                    if not isinstance(credential, str) or not credential or "\n" in credential or "\r" in credential:
                        raise ValueError("Missing OpenRouter music key")
                    request_id = hashlib.sha256(raw).hexdigest()[:12]
                    body = json.dumps(outgoing, ensure_ascii=False).encode("utf-8")
                    req = urllib.request.Request(adapter.upstream, data=body, headers={
                        "Authorization": "Bearer " + credential,
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                        "X-Title": "Solo Lute - SkyrimNet",
                    }, method="POST")
                    adapter.count(mode)
                    LOG.info("request=%s mode=%s lyrics_forwarded=%s percent=%s", request_id, mode, mode == "vocal", percent)
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
                        while True:
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
                except (ValueError, TypeError, OSError, urllib.error.URLError) as exc:
                    adapter.count("errors")
                    LOG.warning("Music request stopped: %s", type(exc).__name__)
                    if not sent_headers:
                        self.json_error(502, "Solo Lute could not complete this music request; see its local log")
                finally:
                    adapter.slot.release()

        class Server(http.server.ThreadingHTTPServer):
            daemon_threads = True
            # Windows SO_REUSEADDR can allow overlapping listeners. Refuse collisions.
            allow_reuse_address = False

        self.server = Server(("127.0.0.1", self.port), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, name="SoloLuteMusic", daemon=True)
        self.thread.start()
        LOG.info("Local music adapter ready on loopback port %s", self.port)
        return f"http://127.0.0.1:{self.port}" + self.route

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self.server = None
