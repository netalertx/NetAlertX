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

Tests exercise _write_crash_log() and install_crash_logger()'s hook
assignment directly, rather than relying on sys.__excepthook__/
threading.__excepthook__ actually firing end-to-end - that chain depends on
CPython/pytest-plugin internals that differ across environments (confirmed:
identical hook logic passed in one sandbox and failed in a real devcontainer
run, because the real environment's sys.excepthook/threading.excepthook
were not the plain defaults this test assumed).
"""

import contextlib
import io
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logger as logger_mod  # noqa: E402


def _read_crash_log(tmp_path):
    crash_log = tmp_path / "crash.log"
    if not crash_log.exists():
        return ""
    return crash_log.read_text()


def test_write_crash_log_writes_exception_text(tmp_path, monkeypatch):
    """_write_crash_log() must append the exception type/message and a
    traceback to crash.log, opened fresh and closed immediately."""
    monkeypatch.setattr(logger_mod, "logPath", str(tmp_path))

    try:
        raise ValueError("boom-main-thread")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    logger_mod._write_crash_log("main thread", exc_type, exc_value, exc_tb)

    content = _read_crash_log(tmp_path)
    assert "boom-main-thread" in content
    assert "ValueError" in content
    assert "main thread" in content


def test_write_crash_log_appends_across_multiple_crashes(tmp_path, monkeypatch):
    """A second crash must not overwrite the first - both must be present."""
    monkeypatch.setattr(logger_mod, "logPath", str(tmp_path))

    for msg in ("first-crash", "second-crash"):
        try:
            raise ValueError(msg)
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
        logger_mod._write_crash_log("main thread", exc_type, exc_value, exc_tb)

    content = _read_crash_log(tmp_path)
    assert "first-crash" in content
    assert "second-crash" in content


def test_write_crash_log_failure_does_not_raise(monkeypatch):
    """If crash.log itself can't be opened (e.g. a bad logPath), the write
    helper must not raise - it would otherwise mask the original exception
    for whatever excepthook called it."""
    monkeypatch.setattr(logger_mod, "logPath", "/nonexistent/path/that/does/not/exist")

    try:
        raise ValueError("boom-unwritable")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    logger_mod._write_crash_log("main thread", exc_type, exc_value, exc_tb)  # must not raise


def test_install_crash_logger_sets_both_hooks(monkeypatch):
    """install_crash_logger() must replace both sys.excepthook and
    threading.excepthook with its own callables - whatever they were set
    to before (the plain default, or something else already installed in
    this process/environment)."""
    sentinel_sys_hook = object()
    sentinel_threading_hook = object()
    monkeypatch.setattr(sys, "excepthook", sentinel_sys_hook)
    monkeypatch.setattr(threading, "excepthook", sentinel_threading_hook)

    logger_mod.install_crash_logger()

    assert sys.excepthook is not sentinel_sys_hook
    assert threading.excepthook is not sentinel_threading_hook
    assert callable(sys.excepthook)
    assert callable(threading.excepthook)


def test_installed_sys_hook_writes_crash_log(tmp_path, monkeypatch):
    """The actual hook function install_crash_logger() installs onto
    sys.excepthook, called directly with real exception info, must write
    to crash.log. Whatever it chains to afterward (the real
    sys.__excepthook__ prints a traceback to stderr) is swallowed via
    redirect_stderr rather than asserted on - see module docstring for
    why that chain isn't asserted on directly."""
    monkeypatch.setattr(logger_mod, "logPath", str(tmp_path))
    logger_mod.install_crash_logger()
    installed_hook = sys.excepthook

    try:
        raise ValueError("boom-installed-hook")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    with contextlib.redirect_stderr(io.StringIO()):
        installed_hook(exc_type, exc_value, exc_tb)

    content = _read_crash_log(tmp_path)
    assert "boom-installed-hook" in content
