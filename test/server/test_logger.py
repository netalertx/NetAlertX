"""
Tests for server/logger.py's file_print() - stdout can legitimately have its
reader go away mid-run (a closed docker-logs pipe, a supervisor restart),
and print() raising BrokenPipeError must not be allowed to crash the whole
process over a non-essential stdout echo (the real log-persistence path is
the file write via log_writer()'s queue, not this mirror).
"""

import os
import sys
import builtins
import logging
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))

import logger as logger_mod  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_logger_global_state():
    """logger.py's currentLevel and the stdlib root logger's handlers/level
    are process-wide globals that Logger()/setup_logging() mutate - restore
    them after each test so these tests can't leak state into any other
    test file collected in the same pytest session."""
    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    saved_level = root_logger.level
    saved_current_level = logger_mod.currentLevel
    try:
        yield
    finally:
        root_logger.handlers = saved_handlers
        root_logger.setLevel(saved_level)
        logger_mod.currentLevel = saved_current_level


def test_invalid_log_level_does_not_downgrade_existing_valid_level():
    """An invalid/empty LOG_LEVEL (what get_setting_value returns before
    settings have loaded - e.g. a plugin subprocess reading a table_settings
    .json that isn't written yet) must not silently latch currentLevel to
    'none' and silence every mylog() call for the rest of the process - it
    should keep whatever valid level was already active."""
    logger_mod.currentLevel = "debug"

    logger_mod.Logger("")

    assert logger_mod.currentLevel == "debug"


def test_valid_log_level_still_updates_current_level():
    """Regression guard: the fix for the above must not stop a genuinely
    valid new LOG_LEVEL from taking effect."""
    logger_mod.currentLevel = "verbose"

    logger_mod.Logger("debug")

    assert logger_mod.currentLevel == "debug"


def test_none_level_blocks_root_logger_for_third_party_loggers(monkeypatch):
    """LOG_LEVEL='none' (including the invalid-input fallback when there is
    no prior valid level) must actually block third-party library logging
    (urllib3, werkzeug) from reaching app.log, not let it through. NOTSET on
    the *root* logger means 'no threshold configured' (allow everything,
    since there's no parent to defer to) rather than 'disabled' - setting
    the root level to NOTSET for 'none' fails open instead of closed."""
    fake_queue = MagicMock()
    monkeypatch.setattr(logger_mod, "log_queue", fake_queue)

    logger_mod.Logger("none")

    third_party_logger = logging.getLogger("urllib3")
    third_party_logger.warning("Starting new HTTPS connection")

    fake_queue.put.assert_not_called()


def test_file_print_survives_broken_pipe_on_stdout(monkeypatch):
    """A BrokenPipeError from print() must not propagate - logging.log()
    (and therefore the file-backed log queue) must still have run."""
    def raising_print(*args, **kwargs):
        raise BrokenPipeError(32, "Broken pipe")
    monkeypatch.setattr(builtins, "print", raising_print)

    fake_log = MagicMock()
    fake_start_writer = MagicMock()
    monkeypatch.setattr(logger_mod.logging, "log", fake_log)
    monkeypatch.setattr(logger_mod, "start_log_writer_thread", fake_start_writer)

    logger_mod.file_print("some message")

    fake_log.assert_called_once()
    fake_start_writer.assert_called_once()


def test_file_print_normal_path_unaffected(monkeypatch):
    """Regression guard: normal (non-broken-pipe) stdout output must still
    happen - this isn't a blanket print() suppression."""
    printed = []
    monkeypatch.setattr(builtins, "print", lambda *a, **kw: printed.append(a))
    monkeypatch.setattr(logger_mod, "start_log_writer_thread", lambda: None)

    logger_mod.file_print("some message")

    assert len(printed) == 1
    assert "some message" in printed[0][0]


def test_file_print_other_oserror_still_propagates(monkeypatch):
    """Only a broken pipe is swallowed - a different OSError (a real,
    unexpected failure) must still surface rather than being silently lost."""
    def raising_print(*args, **kwargs):
        raise OSError(5, "Input/output error")
    monkeypatch.setattr(builtins, "print", raising_print)
    monkeypatch.setattr(logger_mod, "start_log_writer_thread", lambda: None)

    try:
        logger_mod.file_print("some message")
        assert False, "expected OSError to propagate"
    except OSError as e:
        assert e.errno == 5
