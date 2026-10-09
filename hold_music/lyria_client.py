"""Bounded, single-attempt OpenRouter Lyria transport (standard library only)."""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
import uuid

UPSTREAM = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/lyria-3-pro-preview"
MAX_RESPONSE_BYTES = 64_000_000


@dataclass(frozen=True)
class Result:
    audio_bytes: bytes
    duration_seconds: float
    usage: dict | None
    request_id: str


class LyriaError(Exception):
    """Body-free failure; messages never include credentials or provider text."""


class HTTPStatusError(LyriaError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Upstream HTTP status {status}")


class StreamError(LyriaError):
    pass


class MissingAudioError(LyriaError):
    pass


class InvalidBase64Error(LyriaError):
    pass


class ZeroDurationError(LyriaError):
    pass


class ResponseTooLargeError(StreamError):
    pass


# Minimal scalar reader copied from the adapter; this is not a general YAML parser.
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


def read_openrouter_key(bardsinging_yaml_path=None):
    key = os.environ.get("OPENROUTER_API_KEY")
    if key is None:
        if bardsinging_yaml_path is None:
            raise ValueError("Supply --bardsinging or OPENROUTER_API_KEY")
        try:
            key = get_scalar(Path(bardsinging_yaml_path).read_text(encoding="utf-8-sig"),
                             ("bard_singing", "openrouter", "api_key"))
        except (ValueError, OSError):
            raise ValueError("Cannot read OpenRouter key scalar") from None
    if not isinstance(key, str) or not key.strip() or "\n" in key or "\r" in key:
        raise ValueError("Missing or invalid OpenRouter key")
    return key


# Keep frame parsing identical to the adapter, including damaged-tail behavior.
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


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Upstream redirects are disabled", headers, fp)


def _parse_sse(body, request_id):
    fragments = []
    usage = None
    done = False
    for line in body.splitlines(keepends=True):
        if not line.startswith(b"data:"):
            continue
        payload = line[5:].strip()
        if payload == b"[DONE]":
            done = True
            continue
        try:
            event = json.loads(payload)
        except (ValueError, UnicodeError):
            raise StreamError("Invalid SSE JSON") from None
        if not isinstance(event, dict):
            raise StreamError("Invalid SSE event")
        if isinstance(event.get("error"), dict):
            raise StreamError("Upstream error event")
        if isinstance(event.get("id"), str) and event["id"].strip():
            request_id = event["id"]
        if isinstance(event.get("usage"), dict):
            usage = event["usage"]
        choices = event.get("choices", [])
        if not isinstance(choices, list):
            raise StreamError("Invalid SSE choices")
        for choice in choices:
            delta = choice.get("delta") if isinstance(choice, dict) else None
            audio = delta.get("audio") if isinstance(delta, dict) else None
            fragment = audio.get("data") if isinstance(audio, dict) else None
            if isinstance(fragment, str):
                fragments.append(fragment)
    if not done:
        raise StreamError("Missing [DONE]")
    if not fragments or not any(fragments):
        raise MissingAudioError("No audio")
    try:
        audio = base64.b64decode("".join(fragments), validate=True)
    except (ValueError, binascii.Error):
        raise InvalidBase64Error("Invalid audio base64") from None
    duration = mp3_duration(audio)
    if not duration:
        raise ZeroDurationError("Unrecognized MP3 duration")
    return Result(audio, duration, usage, request_id)


def generate(prompt, *, key, upstream=UPSTREAM, timeout=300):
    """One POST, no redirects or retries; cap the entire SSE response at 64 MB."""
    if not isinstance(key, str) or not key.strip() or "\n" in key or "\r" in key:
        raise ValueError("Missing or invalid OpenRouter key")
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "stream": True}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(upstream, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Accept": "text/event-stream", "X-Title": "Hold Music - SkyrimNet",
    }, method="POST")
    opener = urllib.request.build_opener(NoRedirects())
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise HTTPStatusError(response.status)
            request_id = response.headers.get("X-Request-ID") or "local:" + uuid.uuid4().hex
            chunks, total = [], 0
            while True:
                chunk = response.read1(min(65536, MAX_RESPONSE_BYTES - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise ResponseTooLargeError("Unexpectedly large music response")
                chunks.append(chunk)
        return _parse_sse(b"".join(chunks), request_id)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise HTTPStatusError(status) from None
    except (OSError, http.client.HTTPException):
        raise StreamError("Upstream transport failed") from None
