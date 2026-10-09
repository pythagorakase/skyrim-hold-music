"""Read-only catalog checks; no game installation or provider is contacted."""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import skyrimnet_lyrics as catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "local").mkdir()
        self.db = self.root / "songs.db"
        self.lyrics = "[Verse]\r\nA bard’s road — sung softly.\r\n\r\n"
        # Close connections explicitly: Windows cannot delete an open database file.
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("CREATE TABLE bard_songs (id INTEGER, title TEXT, lyrics TEXT, composer_name TEXT, created_at TEXT)")
            db.execute("INSERT INTO bard_songs VALUES (1, ?, ?, 'Lurbuk', '2026-10-05')", ("The road", self.lyrics))
            db.execute("INSERT INTO bard_songs VALUES (2, 'Empty', '', '', '')")
            db.commit()
        self.configure(database=str(self.db), label="Test library")

    def configure(self, **values):
        (self.root / "local" / catalog.CONFIG_NAME).write_text(json.dumps(values))

    def test_reads_existing_lyrics_exactly_without_database_changes(self):
        before = self.db.read_bytes()
        result = catalog.load_catalog(self.root)
        self.assertNotIn("error", result)
        self.assertEqual(len(result["songs"]), 1)
        song = result["songs"][0]
        self.assertEqual(song["lyrics"], self.lyrics)
        self.assertEqual(song["bard_name"], "Lurbuk")
        self.assertEqual(song["sha256"], hashlib.sha256(self.lyrics.encode()).hexdigest())
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(result["source"]["label"], "Test library")

    def test_missing_database_is_not_created(self):
        missing = self.root / "missing.db"
        self.configure(database=str(missing))
        self.assertIn("error", catalog.load_catalog(self.root))
        self.assertFalse(missing.exists())

    def test_committed_wal_rows_are_visible(self):
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("INSERT INTO bard_songs VALUES (3, 'New song', 'New words', 'Karita', '2026-10-08')")
            writer.commit()
            self.assertEqual(len(catalog.load_catalog(self.root)["songs"]), 2)

    def test_remote_failure_has_no_raw_stderr_and_no_fallback(self):
        self.configure(database="C:\\songs.db", ssh_host="halcyon", python="C:\\Python\\python.exe")
        with patch.object(catalog.subprocess, "run", side_effect=subprocess.TimeoutExpired("ssh", 14, stderr=b"private-detail")) as run:
            result = catalog.load_catalog(self.root)
        self.assertEqual(result["songs"], [])
        self.assertIn("error", result)
        self.assertNotIn("private-detail", json.dumps(result))
        self.assertEqual(run.call_count, 1)

    def test_ssh_option_injection_is_rejected_before_execution(self):
        self.configure(database="C:\\songs.db", ssh_host="-oProxyCommand=bad", python="python")
        with patch.object(catalog.subprocess, "run") as run:
            self.assertIn("error", catalog.load_catalog(self.root))
        run.assert_not_called()

    def test_oversized_remote_command_fails_before_contacting_the_host(self):
        databases = [{"path": "C:\\" + ("very-long-folder-name\\" * 12) + f"SkyrimNet-{index}.db", "label": f"Library {index}"}
                     for index in range(8)]
        self.configure(databases=databases, ssh_host="halcyon", python="C:\\Python\\python.exe")
        with patch.object(catalog.subprocess, "run") as run:
            result = catalog.load_catalog(self.root)
        self.assertIn("error", result)
        run.assert_not_called()
        short = {"databases": databases[:2], "ssh_host": "halcyon", "python": "C:\\Python\\python.exe"}
        self.assertLessEqual(len(catalog.remote_command(short)[-1]), catalog.MAX_REMOTE_COMMAND)

    def test_ids_are_namespaced_and_duplicate_rows_rejected(self):
        rows = [{"id": 1, "title": "A", "lyrics": self.lyrics}]
        self.assertNotEqual(catalog.normalize_rows(rows, "first")[0]["id"], catalog.normalize_rows(rows, "second")[0]["id"])
        with self.assertRaises(ValueError):
            catalog.normalize_rows(rows * 2, "first")

    def test_legacy_database_without_composer_name(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("ALTER TABLE bard_songs DROP COLUMN composer_name")
            db.commit()
        self.assertEqual(catalog.load_catalog(self.root)["songs"][0]["bard_name"], "Unknown bard")

    def test_current_and_archived_sources_are_identified_separately(self):
        archive = self.root / "archive.db"
        archive.write_bytes(self.db.read_bytes())
        self.configure(databases=[{"path": str(self.db), "label": "Current profile"},
                                  {"path": str(archive), "label": "Archived drafts"}])
        result = catalog.load_catalog(self.root)
        self.assertEqual([s["collection"] for s in result["songs"]], ["Current profile", "Archived drafts"])
        self.assertEqual(len({s["id"] for s in result["songs"]}), 2)
        self.assertEqual(result["source"]["collections"][1]["count"], 1)


if __name__ == "__main__":
    unittest.main()
