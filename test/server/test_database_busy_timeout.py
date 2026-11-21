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
import tempfile
import shutil
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
