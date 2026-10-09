"""Preserved pre-regional musical treatment for exempt performers."""
import re
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

