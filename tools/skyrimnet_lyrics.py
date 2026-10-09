"""Read an explicitly configured SkyrimNet song database without changing it.

The connection is local to the workshop or uses an existing SSH configuration.
Only song metadata and lyrics are selected; no game settings or credentials are
read. The private machine-specific configuration belongs in local/, not Git.
"""

import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess


MAX_SONGS = 1000
MAX_LYRICS = 20_000
MAX_CATALOG_BYTES = 24 * 1024 * 1024
MAX_REMOTE_COMMAND = 8000
CONFIG_NAME = "skyrimnet-lyrics-source.json"


def read_rows(database):
    """Use SQLite's read-only URI mode, including any committed WAL content."""
    path = Path(database).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.row_factory = sqlite3.Row
        columns = {row[1] for row in connection.execute("PRAGMA table_info(bard_songs)")}
        if not {"id", "title", "lyrics", "created_at"}.issubset(columns):
            raise ValueError("Not a SkyrimNet song database")
        composer = "composer_name" if "composer_name" in columns else "'' AS composer_name"
        query = ("SELECT id, title, lyrics, created_at, " + composer +
                 " FROM bard_songs WHERE lyrics IS NOT NULL AND trim(lyrics) != '' "
                 "ORDER BY created_at DESC, id DESC LIMIT ?")
        return [dict(row) for row in connection.execute(query, (MAX_SONGS + 1,))]


def remote_command(config):
    """Encode the fixed reader and path as data, never as shell fragments."""
    import inspect

    code = ("import json, sqlite3\nfrom pathlib import Path\nfrom contextlib import closing\n"
            f"MAX_SONGS = {MAX_SONGS}\n" + inspect.getsource(read_rows) +
            "\nsources = " + ascii(config["databases"]) +
            "\nprint(json.dumps([read_rows(source['path']) for source in sources], ensure_ascii=True))\n")
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    python = config["python"].replace("'", "''")
    powershell = ("$ErrorActionPreference='Stop'; "
                  "$code=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded + "')); "
                  "$code | & '" + python + "' -; exit $LASTEXITCODE")
    ps_encoded = base64.b64encode(powershell.encode("utf-16-le")).decode("ascii")
    remote = "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + ps_encoded
    if len(remote) > MAX_REMOTE_COMMAND:
        # Windows cmd.exe rejects command lines above 8,191 characters; fail
        # before contacting the host instead of producing a confusing remote error.
        raise ValueError("Remote command too long; configure fewer or shorter database paths")
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "ConnectionAttempts=1",
            config["ssh_host"], remote]


def normalize_rows(rows, identity):
    if not isinstance(rows, list) or len(rows) > MAX_SONGS:
        raise ValueError("Song catalog is too large or invalid")
    namespace = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    songs, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] < 1:
            raise ValueError("Invalid song record")
        lyrics = row.get("lyrics")
        if not isinstance(lyrics, str) or not lyrics.strip() or len(lyrics) > MAX_LYRICS:
            raise ValueError("Invalid or oversized song lyrics")
        if any(ord(char) < 32 and char not in "\r\n\t" for char in lyrics):
            raise ValueError("Invalid song characters")
        identifier = namespace + ":" + str(row["id"])
        if identifier in seen:
            raise ValueError("Duplicate song ID")
        seen.add(identifier)
        songs.append({"id": identifier, "title": str(row.get("title") or "Untitled song")[:500],
                      "lyrics": lyrics, "bard_name": str(row.get("composer_name") or "Unknown bard")[:200],
                      "created_at": str(row.get("created_at") or "")[:100],
                      "sha256": hashlib.sha256(lyrics.encode("utf-8")).hexdigest()})
    return songs


def load_catalog(root):
    source = {"label": "SkyrimNet saved lyrics", "updated_at": None}
    result = {"songs": [], "source": source}
    path = Path(root) / "local" / CONFIG_NAME
    if not path.is_file():
        return {**result, "error": "The SkyrimNet lyrics source is not configured. See the workshop README."}
    try:
        if path.stat().st_size > 16_000:
            raise ValueError("Oversized configuration")
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("Invalid source configuration")
        if "label" in config:
            if not isinstance(config["label"], str) or not config["label"].strip():
                raise ValueError("Invalid source label")
            source["label"] = config["label"][:300]
        databases = config.get("databases", [{"path": config.get("database"), "label": source["label"]}])
        if not isinstance(databases, list) or not 1 <= len(databases) <= 8:
            raise ValueError("Invalid database list")
        for entry in databases:
            if (not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"]
                    or not isinstance(entry.get("label"), str) or not entry["label"].strip()):
                raise ValueError("Invalid database source")
        config["databases"] = databases
        host = config.get("ssh_host", "")
        if host:
            if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,199}", host):
                raise ValueError("Invalid SSH host")
            if not isinstance(config.get("python"), str) or not config["python"] or any(ord(c) < 32 for c in config["python"]):
                raise ValueError("Invalid Python path")
            # The remote operation is read-only. Suppress stderr, which can
            # contain machine paths; return a fixed useful error instead.
            process = subprocess.run(remote_command(config), capture_output=True, timeout=14, check=False)
            if process.returncode or len(process.stdout) > MAX_CATALOG_BYTES:
                raise ValueError("Could not read remote catalog")
            groups = json.loads(process.stdout.decode("utf-8-sig"))
        else:
            groups = [read_rows(entry["path"]) for entry in databases]
        if not isinstance(groups, list) or len(groups) != len(databases):
            raise ValueError("Incomplete catalog response")
        collections = []
        songs = []
        for entry, rows in zip(databases, groups):
            group = normalize_rows(rows, host + "\n" + entry["path"])
            for song in group:
                song["collection"] = entry["label"][:300]
            songs.extend(group)
            collections.append({"label": entry["label"][:300], "count": len(group)})
        if len(songs) > MAX_SONGS:
            raise ValueError("Combined catalog is too large")
        result["songs"] = songs
        source["collections"] = collections
        source["updated_at"] = datetime.now(timezone.utc).isoformat()
        return result
    except (OSError, ValueError, TypeError, sqlite3.Error, subprocess.SubprocessError, RecursionError):
        return {**result, "error": "Could not read the configured SkyrimNet song library. Check the source path and SSH connection, then refresh lyrics."}
