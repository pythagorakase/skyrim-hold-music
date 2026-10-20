"""Local, private executor journal. A provider request is never replayed here."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid


class JobStoreBusy(ValueError):
    """Another executor holds this library's writer lock."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _writer_lock(path):
    # Kernel locks disappear when a process dies; a stale file is harmless.
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise JobStoreBusy('Another executor is using this library') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class JobStore:
    """Single writer, SQLite FULL-synchronous journal including paid payloads.

    Private jobs, lyrics and provider results belong only in this local store.
    ``summaries`` excludes those fields. No recovery method calls a provider.
    """

    def __init__(self, library_root, *, recover_interrupted=True):
        self.root = Path(library_root) / '.executor'
        self.path = self.root / 'jobs.sqlite3'
        self.db = None
        self._lock = None
        self.recover_interrupted = recover_interrupted

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = _writer_lock(self.root / 'writer.lock')
        self._lock.__enter__()
        try:
            self.db = sqlite3.connect(self.path)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL,
                    context TEXT NOT NULL, error_type TEXT, recording TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS calls (
                    id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                    action TEXT NOT NULL, model TEXT NOT NULL,
                    state TEXT NOT NULL, estimate_usd TEXT NOT NULL,
                    response TEXT, audio BLOB, accounting TEXT, error_type TEXT
                );
                CREATE TABLE IF NOT EXISTS job_reviews (
                    id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                    kind TEXT NOT NULL, review_token TEXT NOT NULL UNIQUE,
                    fingerprint TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS job_reviews_no_update
                    BEFORE UPDATE ON job_reviews BEGIN
                    SELECT RAISE(ABORT, 'Job reviews are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS job_reviews_no_delete
                    BEFORE DELETE ON job_reviews BEGIN
                    SELECT RAISE(ABORT, 'Job reviews are append-only'); END;
            ''')
            # A process may have died after sending a request. Never resubmit it.
            if self.recover_interrupted:
                with self.db:
                    self.db.execute("""UPDATE calls SET state='unknown' WHERE state='in_flight'
                        AND job_id IN (SELECT id FROM jobs WHERE state!='closed')""")
                    self.db.execute("""UPDATE jobs SET state='unknown', error_type='Interrupted',
                        updated_at=? WHERE state='in_flight'""", (_now(),))
                    self.db.execute("""UPDATE jobs SET state='failed', error_type='InterruptedBeforeDispatch',
                        updated_at=? WHERE state='prepared'""", (_now(),))
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self._lock is not None:
            self._lock.__exit__(*args)
            self._lock = None

    def begin_job(self, context):
        job_id = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO jobs VALUES (?, ?, ?, NULL, NULL, ?, ?)',
                            (job_id, 'prepared', _json(context), _now(), _now()))
        return job_id

    def update(self, job_id, *, state=None, context=None, recording=None, error_type=None):
        row = self.job(job_id)
        if row['state'] == 'closed':
            raise ValueError('Closed jobs cannot be changed or reopened')
        with self.db:
            self.db.execute('''UPDATE jobs SET state=?, context=?, recording=?,
                error_type=?, updated_at=? WHERE id=?''',
                (state or row['state'], _json(context if context is not None else row['context']),
                 _json(recording) if recording is not None else
                 (_json(row['recording']) if row['recording'] is not None else None),
                 error_type, _now(), job_id))

    def begin_call(self, job_id, action, model, estimate):
        if self.job(job_id)['state'] == 'closed':
            raise ValueError('Closed jobs cannot dispatch')
        call_id = uuid.uuid4().hex
        with self.db:
            self.db.execute('''INSERT INTO calls
                (id, job_id, action, model, state, estimate_usd) VALUES (?, ?, ?, ?, ?, ?)''',
                (call_id, job_id, action, model, 'in_flight', str(estimate)))
            self.db.execute("UPDATE jobs SET state='in_flight', updated_at=? WHERE id=?",
                            (_now(), job_id))
        return call_id

    def returned(self, call_id, response, *, audio=None):
        """Commit the response before parsing, conversion, or publication."""
        self._assert_call_open(call_id)
        with self.db:
            self.db.execute("UPDATE calls SET state='returned', response=?, audio=? WHERE id=?",
                            (_json(response), audio, call_id))
            self.db.execute("""UPDATE jobs SET state='response_received', updated_at=?
                WHERE id=(SELECT job_id FROM calls WHERE id=?)""", (_now(), call_id))

    def account(self, call_id, accounting):
        self._assert_call_open(call_id)
        with self.db:
            self.db.execute('UPDATE calls SET accounting=? WHERE id=?',
                            (_json(accounting), call_id))

    def _assert_call_open(self, call_id):
        row = self.db.execute('''SELECT jobs.state FROM jobs JOIN calls
            ON calls.job_id=jobs.id WHERE calls.id=?''', (call_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown durable call ID')
        if row['state'] == 'closed':
            raise ValueError('Closed job evidence cannot be changed')

    def fail(self, job_id, error_type):
        if self.job(job_id)['state'] == 'closed':
            return
        with self.db:
            self.db.execute("""UPDATE calls SET state='unknown', error_type=?
                WHERE job_id=? AND state='in_flight'""", (error_type, job_id))
            unknown = self.db.execute("SELECT 1 FROM calls WHERE job_id=? AND state='unknown'",
                                      (job_id,)).fetchone()
            self.db.execute('UPDATE jobs SET state=?, error_type=?, updated_at=? WHERE id=?',
                            ('unknown' if unknown else 'failed', error_type, _now(), job_id))

    def job(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown durable job ID')
        row = dict(row)
        row['context'] = json.loads(row['context'])
        row['recording'] = json.loads(row['recording']) if row['recording'] else None
        row['calls'] = []
        for call in self.db.execute('SELECT * FROM calls WHERE job_id=? ORDER BY rowid', (job_id,)):
            call = dict(call)
            for key in ('response', 'accounting'):
                call[key] = json.loads(call[key]) if call[key] else None
            row['calls'].append(call)
        row['reviews'] = self.reviews(job_id)
        return row

    def reviews(self, job_id):
        # Read-only previews must work on journals created before this table.
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_reviews'").fetchone():
            return []
        result = []
        for row in self.db.execute('SELECT * FROM job_reviews WHERE job_id=? ORDER BY rowid', (job_id,)):
            row = dict(row)
            row['data'] = json.loads(row['data'])
            result.append(row)
        return result

    def authorize_continuation(self, job_id, *, review_token, fingerprint, context,
                               lyric_call_id, lyric_accounting, model, estimate, authorization):
        """Consume a reviewed authorization and commit dispatch in one transaction."""
        if self.job(job_id)['state'] in ('closed', 'completed'):
            raise ValueError('Terminal jobs cannot dispatch')
        call_id = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO job_reviews VALUES (?, ?, ?, ?, ?, ?, ?)',
                (uuid.uuid4().hex, job_id, 'continuation', review_token, fingerprint,
                 _json(authorization), _now()))
            self.db.execute('UPDATE calls SET accounting=? WHERE id=? AND job_id=? AND accounting IS NULL',
                            (_json(lyric_accounting), lyric_call_id, job_id))
            self.db.execute('''INSERT INTO calls
                (id, job_id, action, model, state, estimate_usd) VALUES (?, ?, ?, ?, ?, ?)''',
                (call_id, job_id, 'generate_recording', model, 'in_flight', str(estimate)))
            self.db.execute("UPDATE jobs SET context=?, state='in_flight', error_type=NULL, updated_at=? WHERE id=?",
                            (_json(context), _now(), job_id))
        return call_id

    def close_with_attestation(self, job_id, *, review_token, fingerprint, attestation):
        """Close a reviewed unknown outcome without rewriting its raw evidence."""
        if self.job(job_id)['state'] in ('closed', 'completed'):
            raise ValueError('Terminal jobs cannot be reconciled')
        with self.db:
            self.db.execute('INSERT INTO job_reviews VALUES (?, ?, ?, ?, ?, ?, ?)',
                (uuid.uuid4().hex, job_id, 'reconciliation', review_token, fingerprint,
                 _json(attestation), _now()))
            self.db.execute("UPDATE jobs SET state='closed', updated_at=? WHERE id=?", (_now(), job_id))

    def summaries(self, *, pending_only=False):
        result = []
        for row in self.db.execute('SELECT id, state, context, error_type FROM jobs ORDER BY rowid'):
            # Status must not load potentially large audio blobs or private responses.
            calls = []
            for call in self.db.execute('''SELECT id, action, model, state, estimate_usd,
                    accounting, error_type FROM calls WHERE job_id=? ORDER BY rowid''', (row['id'],)):
                call = dict(call)
                call['accounting'] = json.loads(call['accounting']) if call['accounting'] else None
                calls.append(call)
            pending = row['state'] not in ('completed', 'closed') and bool(calls)
            if pending_only and not pending:
                continue
            job = json.loads(row['context'])['job']
            summary = dict(job_id=row['id'], state=row['state'], pending=pending,
                performer_id=job['performer_id'], region=job['region'], mode=job['mode'],
                error_type=row['error_type'], calls=calls,
                unknown_outcome=any(c['state'] in ('in_flight', 'unknown') for c in calls),
                unaccounted_response=any(c['state'] == 'returned' and c['accounting'] is None
                                         for c in calls))
            resolved = [r for r in self.reviews(row['id']) if r['kind'] == 'reconciliation']
            if resolved:
                entry = resolved[-1]
                resolution = entry['data']['resolution']
                summary['resolution'] = dict(outcome=resolution['outcome'], cost_usd=resolution['cost_usd'],
                    provenance='operator_report', provider_verified=False, review_id=entry['id'],
                    applies_to='single_uncertain_call')
            result.append(summary)
        return result


def inspect_jobs(library_root):
    """Read summaries without creating files, recovering state, or taking a lock."""
    store = JobStore(library_root)
    if not store.path.exists():
        return []
    with readonly_store(library_root) as store:
        return store.summaries()


@contextmanager
def readonly_store(library_root):
    """Read existing journal state without creating files or recovering writes."""
    store = JobStore(library_root)
    if not store.path.is_file():
        raise ValueError('No durable job journal exists')
    store.db = sqlite3.connect(store.path.resolve().as_uri() + '?mode=ro', uri=True)
    store.db.row_factory = sqlite3.Row
    try:
        store.db.execute('PRAGMA query_only=ON')
        store.db.execute('BEGIN')
        yield store
    except sqlite3.OperationalError as exc:
        if getattr(exc, 'sqlite_errorcode', 0) & 0xff == sqlite3.SQLITE_READONLY:
            raise ValueError('Journal recovery is required; use --repair-journal before read-only inspection') from None
        raise
    finally:
        store.db.close()


def repair_journal(library_root):
    """Explicit local crash repair; no provider request and no publication."""
    if not JobStore(library_root).path.is_file():
        raise ValueError('No durable job journal exists')
    with JobStore(library_root) as store:
        return dict(status='journal_repaired', jobs=store.summaries(), provider_calls=0)
