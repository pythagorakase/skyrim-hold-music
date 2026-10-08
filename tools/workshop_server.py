#!/usr/bin/env python3
"""Loopback-only Lyria workshop, using the Python standard library.

No generation happens until a user submits /api/generate with this session's
CSRF token. Keys stay in the server process; generated takes stay on disk.
"""

import argparse
import base64
import binascii
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import tempfile
import threading
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = Path.home() / ".config" / "hold-music" / "gemini-api-key"
MODEL = "lyria-3.5"
GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MAX_BODY = 128_000
MAX_RESPONSE = 128 * 1024 * 1024
MAX_ERROR_BODY = 64 * 1024
MAX_PROMPT = 20_000
ARRANGEMENTS = frozenset(("lute_voice", "lute", "flute", "flute_voice", "drum", "drum_voice", "voice", "trio"))
AUDIO_FORMATS = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav"}
ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


class WorkshopError(Exception):
    """An explicitly safe message suitable for returning to the browser."""

    def __init__(self, message: str, status: int = 400, *, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.details = details


def safe_provider_text(value, key: str | None = None, *, limit: int = 700) -> str:
    """Redact credentials before bounding selected diagnostic strings.

    Never pass whole response bodies here. Only explicitly selected string
    fields from Google's JSON error envelope may become browser diagnostics.
    """
    if not isinstance(value, str):
        return ""
    if key:
        for secret in {key, quote(key, safe=""), quote_plus(key, safe="")}:
            value = value.replace(secret, "[redacted]")
    # Recognizable credentials, including keys other than the active key.
    value = re.sub(r"AIza[A-Za-z0-9_-]{20,}", "[redacted]", value)
    value = re.sub(r"\b(?:sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}|ya29\.[A-Za-z0-9._-]+)", "[redacted]", value)
    value = re.sub(r"(?i)([?&](?:key|api[_-]?key|x-goog-api-key|access_token|token)=)[^\s&#\"'<>]*", r"\1[redacted]", value)
    value = re.sub(r"(?i)(\b(?:x-goog-api-key|x-api-key|api[_-]?key|gemini_api_key)\b[\"']?\s*[:=]\s*[\"']?)[^\s,;\"'<>]+", r"\1[redacted]", value)
    value = re.sub(r"(?i)(\bauthorization\b[\"']?\s*[:=]\s*[\"']?)(?:bearer\s+|basic\s+)?[^\s,;\"'<>]+", r"\1[redacted]", value)
    value = re.sub(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+", "[redacted]", value)
    # Drop display controls (including bidi overrides) without damaging Unicode.
    value = "".join(" " if unicodedata.category(char).startswith("C") else char for char in value)
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit - 1] + "…"


def google_http_failure(error: HTTPError, key: str) -> WorkshopError:
    """Keep HTTP status and safe error fields; discard raw bodies and headers."""
    details = {"provider": "google", "http_status": error.code}
    try:
        payload = json.loads(error.read(MAX_ERROR_BODY))
        envelope = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(envelope, dict):
            for field, limit in (("message", 700), ("status", 100), ("code", 100)):
                value = safe_provider_text(envelope.get(field), key, limit=limit)
                if value:
                    details[field] = value
            entries = envelope.get("details")
            if isinstance(entries, list):
                reasons = [safe_provider_text(entry.get("reason"), key, limit=120)
                           for entry in entries[:20] if isinstance(entry, dict)]
                reasons = list(dict.fromkeys(reason for reason in reasons if reason))[:5]
                if reasons:
                    details["reasons"] = reasons
    except (OSError, ValueError, UnicodeError, RecursionError):
        pass
    finally:
        error.close()
    messages = {
        400: "Google rejected this request. Check the request settings and prompt.",
        401: "Google did not accept the API key. Update your local key before trying again.",
        402: "Google requires payment or available credits. Check the project's billing and prepaid credit balance before trying again.",
        403: "Google denied access. Check the key's project, billing, API restrictions, and Lyria access.",
        404: "Lyria 3.5 is unavailable for this API project or endpoint. Check model access and endpoint compatibility.",
        422: "Google rejected the request format. Check that the endpoint and request settings support Lyria 3.5.",
        429: "Google's quota or rate limit was reached. Check the project's limits before trying again.",
        500: "Google reported an internal server error. Check Google's service status before manually trying again.",
        502: "Google reported a gateway error. Check Google's service status before manually trying again.",
        503: "Google's generation service is unavailable or overloaded. Check Google's service status before manually trying again.",
        504: "Google's generation service timed out. Check your project usage before manually trying again.",
    }
    message = f"Google HTTP {error.code}: " + messages.get(error.code, "Google could not complete generation. Check the provider diagnostic before trying again.")
    selected = " ".join([details.get("message", ""), details.get("status", ""), details.get("code", ""), *details.get("reasons", [])])
    if error.code in (400, 405, 409) and re.search(r"(?i)\b(?:revision|version|model|unsupported)\b", selected):
        message += " Check that the endpoint and request settings support Lyria 3.5."
    if details.get("message"):
        message += " Provider: " + details["message"]
    labels = [details["status"]] if details.get("status") else []
    if details.get("code") and details["code"] not in labels:
        labels.append(details["code"])
    labels.extend(details.get("reasons", []))
    if labels:
        message += " (" + "; ".join(labels) + ")"
    message += " No automatic retry was made."
    return WorkshopError(message, 502, details=details)


def read_key(path: Path = KEY_PATH) -> str | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        try:
            with Path(path).open(encoding="ascii") as stream:
                key = stream.read(514).strip()
        except (OSError, UnicodeError):
            return None
    if not key or len(key) > 512 or any(not 33 <= ord(c) <= 126 for c in key):
        return None
    return key


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward Google's credential to a redirect destination.
        return None


def call_google(prompt: str, key: str) -> dict:
    request = Request(
        GOOGLE_ENDPOINT,
        data=json.dumps({"model": MODEL, "input": prompt, "store": False}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with build_opener(NoRedirects()).open(request, timeout=600) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise WorkshopError("Google's response exceeded the workshop's download limit.", 502)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Unexpected response")
        return payload
    except HTTPError as error:
        raise google_http_failure(error, key) from None
    except (TimeoutError, socket.timeout):
        raise WorkshopError("The Google request timed out. It may still have incurred a charge; no automatic retry was made.", 504) from None
    except (URLError, OSError):
        raise WorkshopError("The connection to Google failed. The request may still have incurred a charge; no automatic retry was made.", 502) from None
    except (ValueError, UnicodeError):
        raise WorkshopError("Google returned an unreadable response. No automatic retry was made.", 502) from None


def parse_music(payload: dict) -> tuple[bytes, str, str]:
    """Read model_output steps; Google's examples use the last audio block."""
    if "status" in payload and payload["status"] != "completed":
        raise WorkshopError("Google did not return a completed song. No automatic retry was made.", 502)
    audio = None
    mime = "audio/mpeg"
    lyrics = []
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        raise WorkshopError("Google returned an unexpected song format.", 502)
    for step in steps:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        content = step.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                lyrics.append(block["text"])
            elif block.get("type") == "audio":
                mime = block.get("mime_type", "audio/mpeg")
                if mime not in AUDIO_FORMATS or not isinstance(block.get("data"), str):
                    raise WorkshopError("Google returned an unsupported audio format.", 502)
                try:
                    audio = base64.b64decode(block["data"], validate=True)
                except (ValueError, binascii.Error):
                    raise WorkshopError("Google returned invalid audio data.", 502) from None
    if not audio:
        raise WorkshopError("Google returned no audio. The prompt may have been blocked; review it before trying again.", 502)
    if len(audio) > MAX_RESPONSE:
        raise WorkshopError("The generated audio exceeded the workshop's download limit.", 502)
    return audio, mime, "\n\n".join(lyrics)[:200_000]


def write_private(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".saving-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Workshop:
    def __init__(self, root: Path = ROOT, *, generator=call_google, key_reader=read_key):
        self.root = Path(root)
        self.data_dir = self.root / "auditions"
        self.generator = generator
        self.key_reader = key_reader
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.jobs = {}
        self.takes = {}
        self.active_id = None
        palette = json.loads((self.root / "dashboard" / "palette-data.json").read_text(encoding="utf-8"))
        self.profiles = {item["id"]: item for group in ("finalists", "existing") for item in palette[group]}
        self._load_takes()
        self._load_failures()

    def _load_failures(self):
        for path in self.data_dir.glob("*/failure.json"):
            try:
                if path.is_symlink() or path.parent.is_symlink() or not ID_PATTERN.fullmatch(path.parent.name):
                    continue
                if path.stat().st_size > 16_000:
                    continue
                job = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(job, dict) or job.get("id") != path.parent.name or job.get("status") != "failed":
                    continue
                if not all(isinstance(job.get(field), str) for field in ("profile_id", "arrangement", "error", "failed_at", "model")):
                    continue
                restored = {field: job[field] for field in ("id", "status", "profile_id", "arrangement", "failed_at", "model")}
                restored["error"] = safe_provider_text(job["error"], limit=2400)
                details = job.get("error_details")
                if isinstance(details, dict) and details.get("provider") == "google" and type(details.get("http_status")) is int and 100 <= details["http_status"] <= 599:
                    clean = {"provider": "google", "http_status": details["http_status"]}
                    for field, limit in (("message", 700), ("status", 100), ("code", 100)):
                        value = safe_provider_text(details.get(field), limit=limit)
                        if value:
                            clean[field] = value
                    if isinstance(details.get("reasons"), list):
                        reasons = [safe_provider_text(reason, limit=120) for reason in details["reasons"][:5]]
                        if any(reasons):
                            clean["reasons"] = [reason for reason in reasons if reason]
                    restored["error_details"] = clean
                self.jobs[job["id"]] = restored
            except (OSError, ValueError, KeyError, TypeError, RecursionError):
                continue

    def _fail_job(self, identifier, message, details=None):
        with self.lock:
            self.jobs[identifier].update(status="failed", error=message, model=MODEL,
                                         failed_at=datetime.now(timezone.utc).isoformat())
            if details:
                self.jobs[identifier]["error_details"] = deepcopy(details)
            failure = deepcopy(self.jobs[identifier])
            try:
                directory = self.data_dir / identifier
                directory.mkdir(parents=True, mode=0o700, exist_ok=True)
                write_private(directory / "failure.json", json.dumps(failure, ensure_ascii=False, indent=2).encode("utf-8"))
            except OSError:
                # Preserve the original provider failure even if storage is full.
                self.jobs[identifier]["diagnostic_saved"] = False

    def _load_takes(self):
        for path in self.data_dir.glob("*/take.json"):
            try:
                if path.is_symlink() or path.parent.is_symlink() or not ID_PATTERN.fullmatch(path.parent.name):
                    continue
                if path.stat().st_size > 512_000:
                    continue
                take = json.loads(path.read_text(encoding="utf-8"))
                if take["id"] != path.parent.name or take["mime_type"] not in AUDIO_FORMATS:
                    continue
                if not all(isinstance(take.get(key), str) for key in ("profile_id", "profile_name", "arrangement", "prompt", "created_at", "lyrics", "model")):
                    continue
                audio = path.parent / ("audio" + AUDIO_FORMATS[take["mime_type"]])
                if not audio.is_file() or audio.is_symlink():
                    continue
                self.takes[take["id"]] = self._public_take(take)
            except (OSError, ValueError, KeyError, TypeError):
                continue

    @staticmethod
    def _public_take(take):
        result = {key: take[key] for key in ("id", "profile_id", "profile_name", "arrangement", "prompt", "model", "created_at", "lyrics", "mime_type")}
        result["audio_url"] = f"/api/takes/{take['id']}/audio"
        result["download_url"] = f"/api/takes/{take['id']}/download"
        return result

    def status(self):
        with self.lock:
            failures = [job for job in self.jobs.values() if job["status"] == "failed"]
            latest_failure = max(failures, key=lambda job: job.get("failed_at", ""), default=None)
            if latest_failure and any(take["created_at"] >= latest_failure["failed_at"] for take in self.takes.values()):
                latest_failure = None
            return {"configured": bool(self.key_reader()), "model": MODEL,
                    "active_job": deepcopy(self.jobs.get(self.active_id)),
                    "latest_failed_job": deepcopy(latest_failure), "csrf_token": self.token}

    def list_takes(self):
        with self.lock:
            return deepcopy(sorted(self.takes.values(), key=lambda t: t["created_at"], reverse=True))

    def get_job(self, identifier):
        with self.lock:
            if identifier not in self.jobs:
                raise WorkshopError("Generation job not found.", 404)
            return deepcopy(self.jobs[identifier])

    def submit(self, payload):
        if not isinstance(payload, dict):
            raise WorkshopError("The request must be a JSON object.")
        profile_id = payload.get("profile_id")
        arrangement = payload.get("arrangement")
        prompt = payload.get("prompt")
        if not isinstance(profile_id, str) or profile_id not in self.profiles:
            raise WorkshopError("Choose an existing palette profile.")
        if not isinstance(arrangement, str) or arrangement not in ARRANGEMENTS:
            raise WorkshopError("Choose a supported performer arrangement.")
        profile = self.profiles[profile_id]
        if arrangement == "trio" and not (isinstance(profile.get("ensemble_roles"), list) and len(profile["ensemble_roles"]) == 3 and profile.get("ensemble_clause")):
            raise WorkshopError("This profile has no defined three-voice arrangement.")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT:
            raise WorkshopError(f"Enter a prompt of 1 to {MAX_PROMPT:,} characters.")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in prompt):
            raise WorkshopError("The prompt contains unsupported control characters.")
        with self.lock:
            if self.active_id:
                raise WorkshopError("A song is already generating. Wait for it to finish before starting another.", 409)
            if not self.key_reader():
                raise WorkshopError("Add your Google key with python3 tools/configure_key.py, then try again.", 503)
            identifier = secrets.token_hex(16)
            job = {"id": identifier, "status": "queued", "profile_id": profile_id, "arrangement": arrangement}
            self.jobs[identifier] = job
            self.active_id = identifier
            snapshot = deepcopy(job)
            threading.Thread(target=self._generate, args=(identifier, profile["name"], prompt), daemon=True).start()
            return snapshot

    def _generate(self, identifier, profile_name, prompt):
        try:
            with self.lock:
                self.jobs[identifier]["status"] = "generating"
                job = deepcopy(self.jobs[identifier])
            key = self.key_reader()
            if not key:
                raise WorkshopError("The Google key is no longer configured. Add it locally before trying again.")
            audio, mime, lyrics = parse_music(self.generator(prompt, key))
            take = {"id": identifier, "profile_id": job["profile_id"], "profile_name": profile_name,
                    "arrangement": job["arrangement"], "prompt": prompt, "model": MODEL,
                    "created_at": datetime.now(timezone.utc).isoformat(), "lyrics": lyrics, "mime_type": mime}
            directory = self.data_dir / identifier
            directory.mkdir(parents=True, mode=0o700)
            write_private(directory / ("audio" + AUDIO_FORMATS[mime]), audio)
            write_private(directory / "take.json", json.dumps(take, ensure_ascii=False, indent=2).encode("utf-8"))
            take = self._public_take(take)
            with self.lock:
                self.takes[identifier] = take
                self.jobs[identifier].update(status="completed", take=take)
        except WorkshopError as error:
            self._fail_job(identifier, str(error), error.details)
        except OSError:
            self._fail_job(identifier, "The song could not be saved locally. Check available storage and folder permissions. No automatic retry was made.")
        except Exception:
            self._fail_job(identifier, "Generation failed unexpectedly. The request may still have incurred a charge. No automatic retry was made.")
        finally:
            with self.lock:
                self.active_id = None

    def audio_file(self, identifier):
        with self.lock:
            take = self.takes.get(identifier)
            if not take or not ID_PATTERN.fullmatch(identifier):
                raise WorkshopError("Saved take not found.", 404)
            mime = take["mime_type"]
        path = self.data_dir / identifier / ("audio" + AUDIO_FORMATS[mime])
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            raise WorkshopError("Saved audio not found.", 404)
        return path, mime


class WorkshopServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=8765, workshop=None):
        self.workshop = workshop if workshop is not None else Workshop()
        super().__init__(("127.0.0.1", port), WorkshopHandler)


class WorkshopHandler(BaseHTTPRequestHandler):
    server_version = "HoldMusicWorkshop/1"

    def log_message(self, format, *args):
        # Do not log URLs, prompts, headers, upstream bodies, or credentials.
        pass

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()

    def send_json(self, status, value, *, head=False):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def check_origin(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host_headers = self.headers.get_all("Host", [])
        if len(host_headers) != 1 or host_headers[0] not in hosts:
            raise WorkshopError("Use this workshop's local browser address.", 403)
        origins = self.headers.get_all("Origin", [])
        if origins and (len(origins) != 1 or origins[0] != "http://" + host_headers[0]):
            raise WorkshopError("Cross-origin requests are not allowed.", 403)
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            raise WorkshopError("Cross-origin requests are not allowed.", 403)

    def do_OPTIONS(self):
        self.send_json(405, {"error": "Cross-origin requests are not allowed."})

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        try:
            self.check_origin()
            workshop = self.server.workshop
            if self.path in ("/", "/index.html"):
                content = (workshop.root / "dashboard" / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                if not head:
                    self.wfile.write(content)
            elif self.path == "/api/status":
                self.send_json(200, workshop.status(), head=head)
            elif self.path == "/api/takes":
                self.send_json(200, {"takes": workshop.list_takes()}, head=head)
            elif re.fullmatch(r"/api/jobs/[a-f0-9]{32}", self.path):
                self.send_json(200, {"job": workshop.get_job(self.path.rsplit("/", 1)[1])}, head=head)
            elif re.fullmatch(r"/api/takes/[a-f0-9]{32}/(?:audio|download)", self.path):
                self.serve_audio(head=head)
            else:
                raise WorkshopError("Not found.", 404)
        except WorkshopError as error:
            self.send_json(error.status, {"error": str(error)}, head=head)
        except OSError:
            self.send_json(500, {"error": "A local workshop file could not be read."}, head=head)

    def serve_audio(self, *, head=False):
        identifier = self.path.split("/")[3]
        path, mime = self.server.workshop.audio_file(identifier)
        with path.open("rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            start, end = 0, size - 1
            status = 200
            range_header = self.headers.get("Range")
            if range_header:
                match = re.fullmatch(r"bytes=(\d{0,20})-(\d{0,20})", range_header)
                if not match or not any(match.groups()):
                    self.send_range_error(size)
                    return
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                else:
                    suffix = int(right)
                    start = max(0, size - suffix)
                if start > end or start >= size:
                    self.send_range_error(size)
                    return
                status = 206
            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if self.path.endswith("/download"):
                self.send_header("Content-Disposition", f'attachment; filename="hold-music-{identifier}{AUDIO_FORMATS[mime]}"')
            self.end_headers()
            if not head:
                stream.seek(start)
                remaining = length
                while remaining:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

    def send_range_error(self, size):
        self.send_response(416)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        try:
            self.check_origin()
            if self.path != "/api/generate":
                raise WorkshopError("Not found.", 404)
            token = self.headers.get("X-Workshop-Token", "")
            if not token.isascii() or not secrets.compare_digest(token, self.server.workshop.token):
                raise WorkshopError("Refresh the workshop page before generating.", 403)
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise WorkshopError("Send the generation request as JSON.", 415)
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or len(lengths[0]) > 12 or not lengths[0].isdigit():
                raise WorkshopError("A valid request length is required.", 411)
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise WorkshopError("The request is too large or empty.", 413)
            self.connection.settimeout(10)
            body = self.rfile.read(length)
            if len(body) != length:
                raise WorkshopError("The request was incomplete.")
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeError):
                raise WorkshopError("The request contains invalid JSON.") from None
            job = self.server.workshop.submit(payload)
            self.send_json(202, {"job": job})
        except WorkshopError as error:
            self.send_json(error.status, {"error": str(error)})
        except (TimeoutError, OSError):
            self.send_json(408, {"error": "The local request did not finish. Refresh the page to check generation status."})


def main():
    parser = argparse.ArgumentParser(description="Run the local Lyria 3.5 workshop. No generation occurs on startup.")
    parser.add_argument("--port", type=int, default=8765, help="Local port (default: 8765)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        server = WorkshopServer(args.port)
    except (OSError, ValueError):
        parser.exit(1, "Could not start the workshop. Check the port and dashboard build.\n")
    print(f"Hold Music workshop: http://127.0.0.1:{server.server_port}", flush=True)
    print("Google Lyria 3.5. One generation at a time; no automatic retries. Press Ctrl+C to stop.", flush=True)
    if not server.workshop.status()["configured"]:
        print("Add your key in another terminal with: python3 tools/configure_key.py", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
