"""SQLite connection/cursor subclasses that retry transient lock contention.

A write statement can raise sqlite3.OperationalError (SQLITE_BUSY and a few
related extended codes) when a concurrent writer holds the lock longer than
PRAGMA busy_timeout's own internal wait. RetryingConnection/RetryingCursor
add a short, bounded retry on top of that for execute()/commit() only -
executemany() is deliberately left unwrapped, since under isolation_level=None
each parameter tuple auto-commits individually, so a partial failure can
leave earlier rows already committed; retrying the whole call would re-apply
them.
"""

import random
import sqlite3
import time

from logger import mylog

MAX_ATTEMPTS = 3  # 1 initial attempt + 2 retries
JITTER_RANGE_SECONDS = (0.05, 0.25)  # randomized delay between retries

_RETRYABLE_BUSY_CODES = {
    sqlite3.SQLITE_BUSY,
    sqlite3.SQLITE_BUSY_RECOVERY,
    sqlite3.SQLITE_BUSY_TIMEOUT,
}
# Deliberately excludes SQLITE_BUSY_SNAPSHOT: that condition means this
# connection's read snapshot is stale relative to WAL changes made elsewhere,
# and a write would conflict - retrying the same statement against the same
# stale snapshot fails identically every time; recovering needs a fresh
# transaction, not a mechanical retry. Also excludes SQLITE_LOCKED
# ("database table is locked") - a same-connection unclosed-cursor
# condition that waiting doesn't fix either.


def _is_transient_lock_error(exc):
    """True if exc is a retryable BUSY-family sqlite3.OperationalError."""
    code = getattr(exc, "sqlite_errorcode", None)
    if code is not None:
        return code in _RETRYABLE_BUSY_CODES
    msg = str(exc).lower()
    return "database is locked" in msg or "database is busy" in msg


def _retry_sqlite_call(fn, *args, **kwargs):
    """Call fn(*args, **kwargs), retrying on a transient lock error up to
    MAX_ATTEMPTS times with small jitter between attempts."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as e:
            if not _is_transient_lock_error(e):
                raise
            if attempt == MAX_ATTEMPTS - 1:
                mylog("none", [f"[DB retry] giving up after {MAX_ATTEMPTS} attempts: {e}"])
                raise
            mylog("debug", [f"[DB retry] transient lock, retrying (attempt {attempt + 1}/{MAX_ATTEMPTS}): {e}"])
            time.sleep(random.uniform(*JITTER_RANGE_SECONDS))


class RetryingCursor(sqlite3.Cursor):
    """A sqlite3.Cursor whose execute() retries transient lock errors.
    executemany() is intentionally not overridden - see module docstring."""

    def execute(self, *args, **kwargs):
        return _retry_sqlite_call(super().execute, *args, **kwargs)


class RetryingConnection(sqlite3.Connection):
    """A sqlite3.Connection whose execute()/commit() retry transient lock
    errors, and whose cursor() defaults to RetryingCursor. executemany() is
    intentionally not overridden - see module docstring."""

    def cursor(self, factory=None):
        return super().cursor(factory or RetryingCursor)

    def execute(self, *args, **kwargs):
        return _retry_sqlite_call(super().execute, *args, **kwargs)

    def commit(self):
        return _retry_sqlite_call(super().commit)
