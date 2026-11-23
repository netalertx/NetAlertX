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
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))

import logger as logger_mod  # noqa: E402


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
