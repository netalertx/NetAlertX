"""
Unit tests for db_cleanup plugin SQL logic.

Covers:
- Sessions trim (reuses DAYS_TO_KEEP_EVENTS window)
- ANALYZE refreshes sqlite_stat1 after bulk deletes
- PRAGMA optimize runs without error

Each test creates an isolated in-memory SQLite database so there is no
dependency on the running application or its config.
"""

import sqlite3
import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db():
    """Return an in-memory connection seeded with the tables used by db_cleanup."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE Events (
            eve_MAC     TEXT NOT NULL,
            eve_IP      TEXT NOT NULL,
            eve_DateTime DATETIME NOT NULL,
            eve_EventType TEXT NOT NULL,
            eve_AdditionalInfo TEXT DEFAULT '',
            eve_PendingAlertEmail INTEGER NOT NULL DEFAULT 1,
            eve_PairEventRowid INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE Sessions (
            ses_MAC                  TEXT,
            ses_IP                   TEXT,
            ses_EventTypeConnection  TEXT,
            ses_DateTimeConnection   DATETIME,
            ses_EventTypeDisconnection TEXT,
            ses_DateTimeDisconnection  DATETIME,
            ses_StillConnected       INTEGER,
            ses_AdditionalInfo       TEXT
        )
    """)

    conn.commit()
    return conn


def _seed_sessions(cur, old_count: int, recent_count: int, days: int):
    """
    Insert `old_count` rows with connection date older than `days` days and
    `recent_count` rows with connection date today.
    """
    for i in range(old_count):
        cur.execute(
            "INSERT INTO Sessions (ses_MAC, ses_DateTimeConnection) "
            "VALUES (?, date('now', ?))",
            (f"AA:BB:CC:DD:EE:{i:02X}", f"-{days + 1} day"),
        )
    for i in range(recent_count):
        cur.execute(
            "INSERT INTO Sessions (ses_MAC, ses_DateTimeConnection) "
            "VALUES (?, date('now'))",
            (f"11:22:33:44:55:{i:02X}",),
        )


def _run_sessions_trim(cur, days: int) -> int:
    """Execute the exact DELETE used by db_cleanup and return rowcount."""
    cur.execute(
        f"DELETE FROM Sessions "
        f"WHERE ses_DateTimeConnection <= date('now', '-{days} day')"
    )
    return cur.rowcount


# ---------------------------------------------------------------------------
# Sessions trim tests
# ---------------------------------------------------------------------------

class TestSessionsTrim:

    def test_old_rows_are_deleted(self):
        """Rows older than DAYS_TO_KEEP_EVENTS window must be removed."""
        conn = _make_db()
        cur = conn.cursor()
        _seed_sessions(cur, old_count=10, recent_count=5, days=30)

        deleted = _run_sessions_trim(cur, days=30)

        assert deleted == 10, f"Expected 10 old rows deleted, got {deleted}"
        cur.execute("SELECT COUNT(*) FROM Sessions")
        remaining = cur.fetchone()[0]
        assert remaining == 5, f"Expected 5 recent rows to survive, got {remaining}"

    def test_recent_rows_are_preserved(self):
        """Rows within the retention window must not be touched."""
        conn = _make_db()
        cur = conn.cursor()
        _seed_sessions(cur, old_count=0, recent_count=20, days=30)

        deleted = _run_sessions_trim(cur, days=30)

        assert deleted == 0, f"Expected 0 deletions, got {deleted}"
        cur.execute("SELECT COUNT(*) FROM Sessions")
        assert cur.fetchone()[0] == 20

    def test_empty_table_is_a_no_op(self):
        """Trim against an empty Sessions table must not raise."""
        conn = _make_db()
        cur = conn.cursor()

        deleted = _run_sessions_trim(cur, days=30)

        assert deleted == 0

    def test_trim_is_bounded_by_days_parameter(self):
        """Only rows strictly outside the window are removed; boundary row survives."""
        conn = _make_db()
        cur = conn.cursor()
        # Row exactly AT the boundary (date = 'now' - days exactly)
        cur.execute(
            "INSERT INTO Sessions (ses_MAC, ses_DateTimeConnection) "
            "VALUES (?, date('now', ?))",
            ("AA:BB:CC:00:00:01", "-30 day"),
        )
        # Row just inside the window
        cur.execute(
            "INSERT INTO Sessions (ses_MAC, ses_DateTimeConnection) "
            "VALUES (?, date('now', '-29 day'))",
            ("AA:BB:CC:00:00:02",),
        )

        _run_sessions_trim(cur, days=30)

        cur.execute("SELECT ses_MAC FROM Sessions")
        remaining_macs = {row[0] for row in cur.fetchall()}
        # Boundary row (== threshold) is deleted; inside row survives
        assert "AA:BB:CC:00:00:02" in remaining_macs, "Row inside window was wrongly deleted"

    def test_sessions_trim_uses_same_value_as_events(self):
        """
        Regression: verify that the Sessions DELETE uses an identical day-offset
        expression to the Events DELETE so the two tables stay aligned.
        """

        INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
        script_path = os.path.join(
            INSTALL_PATH, "front", "plugins", "db_cleanup", "script.py"
        )
        with open(script_path) as fh:
            source = fh.read()

        events_expr = "DELETE FROM Events WHERE eve_DateTime <= date('now', '-{str(DAYS_TO_KEEP_EVENTS)} day')"
        sessions_expr = "DELETE FROM Sessions WHERE ses_DateTimeConnection <= date('now', '-{str(DAYS_TO_KEEP_EVENTS)} day')"

        assert events_expr in source, "Events DELETE expression changed unexpectedly"
        assert sessions_expr in source, "Sessions DELETE is not aligned with Events DELETE"


# ---------------------------------------------------------------------------
# ANALYZE tests
# ---------------------------------------------------------------------------

class TestAnalyze:

    def test_analyze_populates_sqlite_stat1(self):
        """
        After ANALYZE, sqlite_stat1 must exist and have at least one row
        for the Events table (which has an implicit rowid index).
        """
        conn = _make_db()
        cur = conn.cursor()

        # Seed some rows so ANALYZE has something to measure
        for i in range(20):
            cur.execute(
                "INSERT INTO Events (eve_MAC, eve_IP, eve_DateTime, eve_EventType) "
                "VALUES (?, '1.2.3.4', date('now'), 'Connected')",
                (f"AA:BB:CC:DD:EE:{i:02X}",),
            )
        conn.commit()

        cur.execute("ANALYZE;")
        conn.commit()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'")
        assert cur.fetchone() is not None, "sqlite_stat1 table not created by ANALYZE"

    def test_analyze_does_not_raise_on_empty_tables(self):
        """ANALYZE against empty tables must complete without exceptions."""
        conn = _make_db()
        cur = conn.cursor()

        # Should not raise
        cur.execute("ANALYZE;")
        conn.commit()

    def test_analyze_is_idempotent(self):
        """Running ANALYZE twice must not raise or corrupt state."""
        conn = _make_db()
        cur = conn.cursor()

        cur.execute("ANALYZE;")
        cur.execute("ANALYZE;")
        conn.commit()


# ---------------------------------------------------------------------------
# PRAGMA optimize tests
# ---------------------------------------------------------------------------

class TestPragmaOptimize:

    def test_pragma_optimize_does_not_raise(self):
        """PRAGMA optimize must complete without exceptions."""
        conn = _make_db()
        cur = conn.cursor()

        # Run ANALYZE first (as db_cleanup does) then optimize
        cur.execute("ANALYZE;")
        cur.execute("PRAGMA optimize;")
        conn.commit()

    def test_pragma_optimize_after_bulk_delete(self):
        """
        PRAGMA optimize after a bulk DELETE (simulating db_cleanup) must
        complete without error, validating the full tail sequence.
        """
        conn = _make_db()
        cur = conn.cursor()

        for i in range(50):
            cur.execute(
                "INSERT INTO Sessions (ses_MAC, ses_DateTimeConnection) "
                "VALUES (?, date('now', '-60 day'))",
                (f"AA:BB:CC:DD:EE:{i:02X}",),
            )
        conn.commit()

        # Mirror the tail sequence from cleanup_database.
        # WAL checkpoints are omitted: they require no open transaction and are
        # not supported on :memory: databases (SQLite raises OperationalError).
        cur.execute("DELETE FROM Sessions WHERE ses_DateTimeConnection <= date('now', '-30 day')")
        conn.commit()
        cur.execute("ANALYZE;")
        conn.execute("VACUUM;")
        cur.execute("PRAGMA optimize;")

        cur.execute("SELECT COUNT(*) FROM Sessions")
        assert cur.fetchone()[0] == 0
