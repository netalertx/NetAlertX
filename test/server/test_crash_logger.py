"""
Tests for server/logger.py's install_crash_logger(): a sys.excepthook/
threading.excepthook pair that writes an uncaught exception's traceback to
a dedicated crash log before the process exits.

Why this exists: log_writer() (same module) buffers mylog() output and only
flushes every 10 entries or after 1s of queue idle - a process that crashes
again within that window loses its final log lines, including any context
about what actually crashed. This writes synchronously (open, write, close
- never a held-open file descriptor) so it survives regardless of timing,
and deliberately doesn't hold the file open between crashes so it can't
conflict with the existing log-clearing/rotation endpoint the way a
continuously-redirected stdout/stderr stream would.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logger as logger_mod  # noqa: E402


def _read_crash_log(tmp_path):
    crash_log = tmp_path / "crash.log"
    if not crash_log.exists():
        return ""
    return crash_log.read_text()


def test_install_crash_logger_writes_main_thread_exception(tmp_path, monkeypatch):
    """A main-thread-style uncaught exception, passed to the installed
    sys.excepthook, must be written to crash.log before being handed to
    the original excepthook (preserving existing crash-then-exit behavior)."""
    monkeypatch.setattr(logger_mod, "logPath", str(tmp_path))
    original_hook = sys.excepthook
    try:
        logger_mod.install_crash_logger()
        try:
            raise ValueError("boom-main-thread")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()

        called_original = {}
        monkeypatch.setattr(
            sys, "__excepthook__",
            lambda t, v, tb: called_original.update(type=t, value=v),
        )
        sys.excepthook(exc_type, exc_value, exc_tb)

        content = _read_crash_log(tmp_path)
        assert "boom-main-thread" in content
        assert "ValueError" in content
        assert called_original.get("type") is ValueError
    finally:
        sys.excepthook = original_hook


def test_install_crash_logger_writes_background_thread_exception(tmp_path, monkeypatch):
    """A real exception raised in a background thread must also reach
    crash.log, via threading.excepthook."""
    monkeypatch.setattr(logger_mod, "logPath", str(tmp_path))
    original_hook = threading.excepthook
    try:
        logger_mod.install_crash_logger()

        def _raise():
            raise RuntimeError("boom-background-thread")

        t = threading.Thread(target=_raise)
        t.start()
        t.join(timeout=5)

        deadline = time.monotonic() + 2
        content = ""
        while time.monotonic() < deadline:
            content = _read_crash_log(tmp_path)
            if "boom-background-thread" in content:
                break
            time.sleep(0.05)

        assert "boom-background-thread" in content
        assert "RuntimeError" in content
    finally:
        threading.excepthook = original_hook


def test_crash_log_write_failure_does_not_raise(tmp_path, monkeypatch):
    """If crash.log itself can't be opened (e.g. a bad logPath), the hook
    must not raise - it would otherwise mask the original exception."""
    monkeypatch.setattr(logger_mod, "logPath", "/nonexistent/path/that/does/not/exist")
    original_hook = sys.excepthook
    try:
        logger_mod.install_crash_logger()
        try:
            raise ValueError("boom-unwritable")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()

        called_original = {}
        monkeypatch.setattr(
            sys, "__excepthook__",
            lambda t, v, tb: called_original.update(type=t, value=v),
        )
        sys.excepthook(exc_type, exc_value, exc_tb)  # must not raise

        assert called_original.get("type") is ValueError
    finally:
        sys.excepthook = original_hook
