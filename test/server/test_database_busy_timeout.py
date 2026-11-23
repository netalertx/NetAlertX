"""
Regression guard for the main-loop SQLite connection's busy_timeout
(server/database.py's DB.open()) - see
.gemini/internal-docs/PRDs/execution-queue-fe-locking-fix.md, fix D.

Without PRAGMA busy_timeout, a collision with a concurrent writer (e.g. a
PHP request) fails immediately with "database is locked" instead of
retrying internally for a bounded window.
"""

import os
import sys
import sqlite3
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))

from database import DB  # noqa: E402
from db.retry import RetryingCursor  # noqa: E402


class TestDatabaseBusyTimeout(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._tmpdir, "test_app.db")

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_open_sets_busy_timeout_5000ms(self):
        db = DB()
        with patch("database.fullDbPath", self._db_path):
            db.open()
        try:
            value = db.sql_connection.execute("PRAGMA busy_timeout;").fetchone()[0]
            self.assertEqual(value, 5000)
        finally:
            db.sql_connection.close()

    def test_open_uses_retrying_cursor(self):
        """Regression guard: DB.open()'s connection factory must keep
        producing a RetryingCursor so lock-contention retries (server/db/retry.py)
        aren't silently dropped by a future refactor."""
        db = DB()
        with patch("database.fullDbPath", self._db_path):
            db.open()
        try:
            self.assertIsInstance(db.sql, RetryingCursor)
        finally:
            db.sql_connection.close()

    def test_open_resets_state_and_reraises_on_lock_error(self):
        """open() must not swallow a connect-time sqlite3.Error - it has to
        reset sql_connection/sql back to None and re-raise, so a caller's
        retry loop (server/__main__.py's startup retry) actually sees the
        failure instead of silently continuing with a half-built DB object
        whose next statement (initDB()'s BEGIN IMMEDIATE) would crash with
        an unrelated AttributeError on a None sql_connection."""
        db = DB()
        with patch("database.fullDbPath", self._db_path), \
                patch("database.sqlite3.connect", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(sqlite3.OperationalError):
                db.open()
        self.assertIsNone(db.sql_connection)
        self.assertIsNone(db.sql)

    def test_open_closes_connection_on_post_connect_failure(self):
        """A PRAGMA failing after connect() succeeded must close the
        already-allocated connection before the references are cleared,
        not leak it, and the original error must still propagate."""
        fake_connection = MagicMock()
        fake_connection.execute.side_effect = sqlite3.OperationalError("database is locked")
        db = DB()
        with patch("database.fullDbPath", self._db_path), \
                patch("database.sqlite3.connect", return_value=fake_connection):
            with self.assertRaises(sqlite3.OperationalError):
                db.open()
        fake_connection.close.assert_called_once()
        self.assertIsNone(db.sql_connection)
        self.assertIsNone(db.sql)

    def test_open_preserves_original_error_when_close_fails(self):
        """If cleanup close() itself raises, the original open() error is
        still the one that propagates."""
        fake_connection = MagicMock()
        fake_connection.execute.side_effect = sqlite3.OperationalError("database is locked")
        fake_connection.close.side_effect = sqlite3.ProgrammingError("close failed")
        db = DB()
        with patch("database.fullDbPath", self._db_path), \
                patch("database.sqlite3.connect", return_value=fake_connection):
            with self.assertRaises(sqlite3.OperationalError) as ctx:
                db.open()
        self.assertIn("database is locked", str(ctx.exception))
        self.assertIsNone(db.sql_connection)
        self.assertIsNone(db.sql)


if __name__ == "__main__":
    unittest.main()
