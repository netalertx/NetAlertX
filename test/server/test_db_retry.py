"""
Unit and integration tests for server/db/retry.py's SQLite busy-retry wrapper.

Covers the retry/backoff design for transient "database is locked"
conditions: which sqlite_errorcode values are retried, which are
deliberately excluded (SQLITE_LOCKED, SQLITE_BUSY_SNAPSHOT), why
executemany() is left unwrapped, and the real regression this design
targets (mark_processed() recovering from a transient lock instead of
crashing the caller).
"""

import os
import sys
import sqlite3
import tempfile
import shutil
import threading
import time
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.retry import (  # noqa: E402
    RetryingConnection,
    RetryingCursor,
    MAX_ATTEMPTS,
    JITTER_RANGE_SECONDS,
    _retry_sqlite_call,
)
from workflows.app_events import mark_processed  # noqa: E402


def _busy_error(code=sqlite3.SQLITE_BUSY, message="database is locked"):
    """Build a real OperationalError with a specific sqlite_errorcode set."""
    exc = sqlite3.OperationalError(message)
    exc.sqlite_errorcode = code
    return exc


class DummyDB:
    """Minimal DB wrapper matching session_events.insert_events()'s interface."""

    def __init__(self, conn):
        self.sql = conn.cursor()
        self._conn = conn

    def commitDB(self):
        self._conn.commit()


class TestRetrySqliteCallLoopMechanics(unittest.TestCase):
    """Loop-mechanics tests via direct dependency injection - sqlite3.Cursor/
    Connection are immutable C-extension types and cannot be monkeypatched,
    so _retry_sqlite_call() is exercised directly with an injected callable."""

    def test_retries_on_locked_then_succeeds(self):
        fake_fn = MagicMock(side_effect=[_busy_error(), _busy_error(), "ok"])
        result = _retry_sqlite_call(fake_fn)
        self.assertEqual(result, "ok")
        self.assertEqual(fake_fn.call_count, 3)

    def test_raises_after_max_attempts(self):
        fake_fn = MagicMock(side_effect=[_busy_error()] * (MAX_ATTEMPTS + 2))
        with self.assertRaises(sqlite3.OperationalError):
            _retry_sqlite_call(fake_fn)
        self.assertEqual(fake_fn.call_count, MAX_ATTEMPTS)

    def test_does_not_retry_on_unrelated_operational_error(self):
        fake_fn = MagicMock(
            side_effect=_busy_error(code=sqlite3.SQLITE_ERROR, message="no such table: Foo")
        )
        with self.assertRaises(sqlite3.OperationalError):
            _retry_sqlite_call(fake_fn)
        self.assertEqual(fake_fn.call_count, 1)

    def test_does_not_retry_on_table_locked(self):
        fake_fn = MagicMock(
            side_effect=_busy_error(code=sqlite3.SQLITE_LOCKED, message="database table is locked")
        )
        with self.assertRaises(sqlite3.OperationalError):
            _retry_sqlite_call(fake_fn)
        self.assertEqual(fake_fn.call_count, 1)

    def test_does_not_retry_on_busy_snapshot(self):
        fake_fn = MagicMock(side_effect=_busy_error(code=sqlite3.SQLITE_BUSY_SNAPSHOT))
        with self.assertRaises(sqlite3.OperationalError):
            _retry_sqlite_call(fake_fn)
        self.assertEqual(fake_fn.call_count, 1)

    def test_retries_on_busy_recovery_and_busy_timeout(self):
        for code in (sqlite3.SQLITE_BUSY_RECOVERY, sqlite3.SQLITE_BUSY_TIMEOUT):
            fake_fn = MagicMock(side_effect=[_busy_error(code=code), "ok"])
            result = _retry_sqlite_call(fake_fn)
            self.assertEqual(result, "ok")
            self.assertEqual(fake_fn.call_count, 2)


class TestExecutemanyNotWrapped(unittest.TestCase):
    def test_executemany_is_not_wrapped(self):
        self.assertIs(RetryingCursor.executemany, sqlite3.Cursor.executemany)
        self.assertIs(RetryingConnection.executemany, sqlite3.Connection.executemany)


class TestRetryIntegration(unittest.TestCase):
    """Real two-connection, file-based tests - exercise the actual sqlite3
    C-level behavior this design depends on, not mocks."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._tmpdir, "test_app.db")

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _open_retrying_connection(self, busy_timeout_ms=200):
        conn = sqlite3.connect(self._db_path, isolation_level=None, factory=RetryingConnection)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms};")
        return conn

    def _open_locker_connection(self, busy_timeout_ms=200):
        conn = sqlite3.connect(
            self._db_path, isolation_level=None, check_same_thread=False
        )
        conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms};")
        return conn

    def test_cursor_reusable_after_failed_execute(self):
        """A RetryingCursor that exhausts its retries and raises must still
        be usable afterward - the failure must not leave it in a broken
        state. Holds the lock longer than MAX_ATTEMPTS * busy_timeout so the
        cursor's own retries are genuinely exhausted and it raises for real,
        then releases the lock and reuses the same cursor object."""
        busy_timeout_ms = 50
        c1 = self._open_retrying_connection(busy_timeout_ms=busy_timeout_ms)
        c1.execute("CREATE TABLE t (x INTEGER)")
        cur = c1.cursor()

        c2 = self._open_locker_connection(busy_timeout_ms=busy_timeout_ms)
        c2.execute("BEGIN IMMEDIATE")
        c2.execute("INSERT INTO t VALUES (1)")

        # Must exceed the true worst-case retry window, not just the
        # busy_timeout waits: MAX_ATTEMPTS busy_timeout waits PLUS
        # (MAX_ATTEMPTS - 1) jitter sleeps at their maximum - a real, fixed
        # devcontainer test failure (AssertionError: OperationalError not
        # raised) came from omitting the jitter sleeps here, so the retry
        # loop sometimes outlasted the lock and quietly succeeded instead.
        busy_timeout_component = MAX_ATTEMPTS * (busy_timeout_ms / 1000.0)
        jitter_component = (MAX_ATTEMPTS - 1) * JITTER_RANGE_SECONDS[1]
        safety_margin = 0.3
        hold_seconds = busy_timeout_component + jitter_component + safety_margin

        def release_lock_late():
            time.sleep(hold_seconds)
            c2.commit()

        t = threading.Thread(target=release_lock_late)
        t.start()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                cur.execute("INSERT INTO t VALUES (2)")
        finally:
            t.join()

        # The same cursor object, reused after a genuine, exhausted-retry failure.
        cur.execute("INSERT INTO t VALUES (3)")
        rows = {r[0] for r in cur.execute("SELECT x FROM t").fetchall()}
        self.assertEqual(rows, {1, 3})
        c1.close()
        c2.close()

    def test_executemany_partial_commit_under_busy_is_a_real_risk(self):
        """Confirms why executemany() is deliberately left unwrapped: under
        isolation_level=None, a partial executemany() failure leaves earlier
        rows already durably committed - retrying the whole call would
        re-insert them."""
        c1 = sqlite3.connect(self._db_path, isolation_level=None)
        c1.execute("PRAGMA journal_mode=WAL;")
        c1.execute("CREATE TABLE t (x INTEGER)")
        c1.execute("PRAGMA busy_timeout=100;")

        c2 = self._open_locker_connection(busy_timeout_ms=100)

        def locker():
            time.sleep(0.05)
            c2.execute("BEGIN IMMEDIATE")
            c2.execute("INSERT INTO t VALUES (999)")
            time.sleep(0.4)
            c2.commit()

        t = threading.Thread(target=locker)
        t.start()
        try:
            def slow_params():
                for v in range(1, 11):
                    time.sleep(0.03)
                    yield (v,)
            with self.assertRaises(sqlite3.OperationalError):
                c1.executemany("INSERT INTO t VALUES (?)", slow_params())
        finally:
            t.join()

        rows = {r[0] for r in c1.execute("SELECT x FROM t").fetchall()}
        self.assertIn(1, rows)  # the first row, attempted before contention, is already committed
        self.assertNotIn(10, rows)  # later rows never got attempted
        c1.close()
        c2.close()

    def test_mark_processed_recovers_from_lock(self):
        """The regression test anchored directly to issue #1875: a transient
        lock during mark_processed() must be retried and recovered, not
        crash the caller."""
        conn = self._open_retrying_connection(busy_timeout_ms=100)
        conn.execute(
            'CREATE TABLE AppEvents ("index" INTEGER PRIMARY KEY, appEventProcessed INTEGER DEFAULT 0)'
        )
        conn.execute('INSERT INTO AppEvents ("index", appEventProcessed) VALUES (1, 0)')
        db = DummyDB(conn)

        locker = self._open_locker_connection(busy_timeout_ms=100)

        def hold_lock_briefly():
            locker.execute("BEGIN IMMEDIATE")
            locker.execute('INSERT INTO AppEvents ("index", appEventProcessed) VALUES (2, 0)')
            time.sleep(0.15)  # shorter than MAX_ATTEMPTS x busy_timeout
            locker.commit()

        t = threading.Thread(target=hold_lock_briefly)
        t.start()
        time.sleep(0.02)  # let the locker grab the lock first
        try:
            mark_processed(db, 1)  # must not raise
        finally:
            t.join()

        row = conn.execute('SELECT appEventProcessed FROM AppEvents WHERE "index" = 1').fetchone()
        self.assertEqual(row[0], 1)
        conn.close()
        locker.close()


if __name__ == "__main__":
    unittest.main()
