#!/usr/bin/env python3
"""Save a Gemini key locally, without putting it in shell history or chat."""

import getpass
import os
from pathlib import Path
import sys
import tempfile
import warnings


KEY_PATH = Path.home() / ".config" / "hold-music" / "gemini-api-key"


def valid_key(value: str) -> bool:
    return bool(value) and len(value) <= 512 and all(33 <= ord(c) <= 126 for c in value)


def save_key(key: str, destination: Path = KEY_PATH) -> None:
    """Atomically replace the private key file; never include the key in errors."""
    if not valid_key(key):
        raise ValueError("Enter a nonempty API key without spaces or line breaks.")
    destination = Path(destination)
    if destination.parent.is_symlink():
        raise ValueError("The key directory must not be a symbolic link.")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".key-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            os.chmod(temporary, 0o600)
            stream.write(key + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    if not sys.stdin.isatty():
        print("Run this helper in your own terminal so the key can be entered privately.", file=sys.stderr)
        return 1
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("Google Gemini API key (hidden): ")
        save_key(key)
    except (KeyboardInterrupt, EOFError):
        print("\nKey setup cancelled.", file=sys.stderr)
        return 1
    except (OSError, ValueError, getpass.GetPassWarning):
        print("Could not save the key privately. Check the input and local file permissions.", file=sys.stderr)
        return 1
    print(f"Key saved privately to {KEY_PATH}. The workshop will pick it up automatically.")
    if os.environ.get("GEMINI_API_KEY"):
        print("An existing GEMINI_API_KEY environment variable takes priority over this file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
