"""
Tests for server/scan/resource_history.py - tick-scoped resource sampling
and the Resource_History insert, plus the __main__.py schedule-tick
try/except/finally wiring that calls it.
"""

import os
import sys
import sqlite3
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import psutil
import pytest

from server.scan import resource_history as rh

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import make_db  # noqa: E402


# ---------------------------------------------------------------------------
# get_process_cpu_times_and_io()
# ---------------------------------------------------------------------------

def test_cpu_times_includes_children(monkeypatch):
    """children_user/children_system must be summed in, not just user/system."""
    fake_times = SimpleNamespace(user=1.0, system=2.0, children_user=3.0, children_system=4.0)
    fake_io = SimpleNamespace(read_bytes=100, write_bytes=200)
    fake_process = MagicMock()
    fake_process.cpu_times.return_value = fake_times
    fake_process.io_counters.return_value = fake_io
    monkeypatch.setattr(rh.psutil, "Process", lambda: fake_process)

    cpu_time_s, read_bytes, write_bytes = rh.get_process_cpu_times_and_io()

    assert cpu_time_s == pytest.approx(10.0)  # 1+2+3+4
    assert read_bytes == 100
    assert write_bytes == 200


def test_cpu_times_falls_back_to_zeros_on_psutil_error(monkeypatch):
    """psutil.Error/AttributeError from cpu_times()/io_counters() must not raise."""
    import psutil as real_psutil

    def raising_process():
        raise real_psutil.AccessDenied()

    monkeypatch.setattr(rh.psutil, "Process", raising_process)

    result = rh.get_process_cpu_times_and_io()

    assert result == (0.0, 0, 0)


def test_cpu_times_falls_back_on_attribute_error(monkeypatch):
    """A mocked cpu_times() missing children_* fields must fall back to zeros."""
    fake_process = MagicMock()
    fake_process.cpu_times.return_value = SimpleNamespace(user=1.0, system=1.0)  # no children_*
    monkeypatch.setattr(rh.psutil, "Process", lambda: fake_process)

    result = rh.get_process_cpu_times_and_io()

    assert result == (0.0, 0, 0)


# ---------------------------------------------------------------------------
# insert_resource_history()
# ---------------------------------------------------------------------------

class _FakeDB:
    """Minimal DB wrapper exposing .sql like the real DB class."""

    def __init__(self, conn):
        self.sql = conn.cursor()
        self._conn = conn

    def open(self):
        pass

    def initDB(self):
        pass

    def commitDB(self):
        self._conn.commit()


def _make_resource_history_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE Resource_History (
            "index"           INTEGER PRIMARY KEY AUTOINCREMENT,
            resDateTime       TEXT NOT NULL,
            resCpuPercent     REAL,
            resRssMb          REAL,
            resIoReadBytes    INTEGER,
            resIoWriteBytes   INTEGER,
            resScanDurationMs INTEGER,
            resTickFailed     INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return _FakeDB(conn)


def test_insert_computes_deltas_exactly():
    """resCpuPercent/resIoReadBytes/resIoWriteBytes must match hand-computed deltas."""
    db = _make_resource_history_db()
    pre = (10.0, 1000, 2000)
    post = (13.0, 1500, 2600)  # cpu delta = 3.0s, io read delta = 500, io write delta = 600

    rh.insert_resource_history(db, pre, post, duration_ms=6000)  # 6s wall time

    row = db.sql.execute(
        "SELECT resCpuPercent, resIoReadBytes, resIoWriteBytes, resScanDurationMs, resTickFailed "
        "FROM Resource_History"
    ).fetchone()

    assert row[0] == pytest.approx((3.0 / 6.0) * 100)  # 50%
    assert row[1] == 500
    assert row[2] == 600
    assert row[3] == 6000
    assert row[4] == 0


def test_insert_zero_duration_guard():
    """duration_ms <= 0 must yield resCpuPercent == 0.0, not a ZeroDivisionError."""
    db = _make_resource_history_db()

    rh.insert_resource_history(db, (0.0, 0, 0), (5.0, 10, 10), duration_ms=0)

    row = db.sql.execute("SELECT resCpuPercent FROM Resource_History").fetchone()
    assert row[0] == 0.0


def test_insert_records_tick_failed_flag():
    """tick_failed=True must be stored as resTickFailed=1."""
    db = _make_resource_history_db()

    rh.insert_resource_history(db, (0.0, 0, 0), (0.0, 0, 0), duration_ms=1000, tick_failed=True)

    row = db.sql.execute("SELECT resTickFailed FROM Resource_History").fetchone()
    assert row[0] == 1


def test_insert_failure_is_caught_and_logged():
    """A raising db.sql.execute() must not propagate - the real tick's commit must survive."""
    class RaisingDB:
        class _Sql:
            def execute(self, *a, **kw):
                raise sqlite3.OperationalError("locked")
        sql = _Sql()

    # Must not raise.
    rh.insert_resource_history(RaisingDB(), (0.0, 0, 0), (0.0, 0, 0), duration_ms=1000)


def test_rss_sampling_failure_does_not_skip_the_row(monkeypatch):
    """
    Regression: a failing psutil RSS read must zero resRssMb, not get caught
    by the INSERT's own except block and skip the whole row (CPU/IO were
    already computed successfully by that point).
    """
    db = _make_resource_history_db()

    def raising_process():
        raise psutil.AccessDenied()

    monkeypatch.setattr(rh.psutil, "Process", raising_process)

    rh.insert_resource_history(db, (0.0, 0, 0), (1.0, 100, 200), duration_ms=1000)

    row = db.sql.execute(
        "SELECT resRssMb, resIoReadBytes, resIoWriteBytes FROM Resource_History"
    ).fetchone()
    assert row is not None, "Row must still be inserted despite the RSS sampling failure"
    assert row[0] == 0.0
    assert row[1] == 100  # IO values, computed before the RSS read, are unaffected
    assert row[2] == 200


# ---------------------------------------------------------------------------
# __main__.py schedule-tick wiring: try/except/finally + MAINT_PERF_DAYS gate
# ---------------------------------------------------------------------------

class _StopTestLoop(Exception):
    """Sentinel raised from the mocked time.sleep() to end the `while True:` loop."""


class _FakeState:
    def __init__(self):
        self.pause_until = None
        self.processScan = True
        self.graphQLServerStarted = 1


class _FakePM:
    def __init__(self, raise_on_schedule=False):
        self.raise_on_schedule = raise_on_schedule
        self.calls = []

    def check_and_run_user_event(self):
        pass

    def run_plugin_scripts(self, phase):
        self.calls.append(phase)
        if phase == "schedule" and self.raise_on_schedule:
            raise RuntimeError("boom-in-schedule")


class _FakeNotificationInstance:
    """Stands in for NotificationInstance(db) - create() and the three
    processed/clear methods are all called on this same object in __main__.py."""

    def create(self, final_json, x):
        return SimpleNamespace(HasNotifications=False)

    def setAllProcessed(self):
        pass

    def clearPendingEmailFlag(self):
        pass

    def clearPluginEvents(self):
        pass


class _FakeWorkflowManager:
    def __init__(self, db):
        pass

    def get_new_app_events(self):
        return []


def _ensure_stub_module(name, **attrs):
    """Inject a minimal fake module for an optional third-party dependency
    that isn't relevant to what's under test here (e.g. json2table, used only
    for HTML-formatted notification bodies) but is unconditionally imported
    by server/__main__.py's own import chain."""
    import importlib
    try:
        importlib.import_module(name)
    except ImportError:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod


@pytest.fixture
def main_mod():
    _ensure_stub_module("json2table", convert=lambda *a, **kw: "")
    import server.__main__ as m
    return m


def _common_patches(monkeypatch, main_mod, db, fake_pm):
    monkeypatch.setattr(main_mod, "filePermissions", lambda: None)
    monkeypatch.setattr(main_mod, "update_GUI_port", lambda: None)
    monkeypatch.setattr(main_mod, "renameSettings", lambda path: None)
    monkeypatch.setattr(main_mod, "importConfigs", lambda pm, db, all_plugins: (fake_pm, [], False))
    monkeypatch.setattr(main_mod, "update_api", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "updateState", lambda *a, **kw: _FakeState())
    monkeypatch.setattr(main_mod, "DB", lambda: db)
    monkeypatch.setattr(main_mod, "process_scan", lambda db, all_plugins=None: None)
    monkeypatch.setattr(main_mod, "get_setting_value", lambda key, default=None: 30 if key == "MAINT_PERF_DAYS" else default)
    monkeypatch.setattr(main_mod.conf, "last_scan_run", main_mod.timeNowUTC(as_string=False) - main_mod.datetime.timedelta(minutes=5))
    monkeypatch.setattr(main_mod.conf, "DEEP_SLEEP", False, raising=False)
    monkeypatch.setattr(main_mod.time, "sleep", lambda *a, **kw: (_ for _ in ()).throw(_StopTestLoop()))


def test_tick_failure_records_row_and_reraises(monkeypatch, main_mod):
    """A raising run_plugin_scripts('schedule') must still insert resTickFailed=1
    and re-raise the original exception unchanged."""
    conn = make_db()
    rh_upgrade_conn = conn.cursor()
    from server.db.db_upgrade import ensure_Resource_History
    ensure_Resource_History(rh_upgrade_conn)
    conn.commit()
    db = _FakeDB(conn)

    fake_pm = _FakePM(raise_on_schedule=True)
    _common_patches(monkeypatch, main_mod, db, fake_pm)

    with pytest.raises(RuntimeError, match="boom-in-schedule"):
        main_mod.main()

    row = conn.execute(
        "SELECT resTickFailed FROM Resource_History"
    ).fetchone()
    assert row is not None, "Resource_History row must be written even when the tick raises"
    assert row[0] == 1


def test_normal_tick_records_row_with_tick_failed_zero(monkeypatch, main_mod):
    """A normal, non-raising tick must insert a row with resTickFailed=0."""
    conn = make_db()
    rh_upgrade_conn = conn.cursor()
    from server.db.db_upgrade import ensure_Resource_History
    ensure_Resource_History(rh_upgrade_conn)
    conn.commit()
    db = _FakeDB(conn)

    fake_pm = _FakePM(raise_on_schedule=False)
    _common_patches(monkeypatch, main_mod, db, fake_pm)
    monkeypatch.setattr(main_mod, "get_notifications", lambda db: {})
    monkeypatch.setattr(main_mod, "NotificationInstance", lambda db: _FakeNotificationInstance())
    monkeypatch.setattr(main_mod, "update_devices_names", lambda pm: None)
    monkeypatch.setattr(main_mod, "WorkflowManager", _FakeWorkflowManager)
    monkeypatch.setattr(main_mod, "UserEventsQueueInstance", lambda: SimpleNamespace(
        has_update_devices=lambda: False
    ))

    with pytest.raises(_StopTestLoop):
        main_mod.main()

    row = conn.execute(
        "SELECT resTickFailed FROM Resource_History"
    ).fetchone()
    assert row is not None, "Resource_History row must be written on a normal tick"
    assert row[0] == 0
    assert "schedule" in fake_pm.calls


def test_maint_perf_days_zero_disables_collection(monkeypatch, main_mod):
    """MAINT_PERF_DAYS == 0 must produce zero new Resource_History rows."""
    conn = make_db()
    rh_upgrade_conn = conn.cursor()
    from server.db.db_upgrade import ensure_Resource_History
    ensure_Resource_History(rh_upgrade_conn)
    conn.commit()
    db = _FakeDB(conn)

    fake_pm = _FakePM(raise_on_schedule=False)
    _common_patches(monkeypatch, main_mod, db, fake_pm)
    # Override the default 30-day fixture value with 0 (disabled).
    monkeypatch.setattr(main_mod, "get_setting_value", lambda key, default=None: 0 if key == "MAINT_PERF_DAYS" else default)
    monkeypatch.setattr(main_mod, "get_notifications", lambda db: {})
    monkeypatch.setattr(main_mod, "NotificationInstance", lambda db: _FakeNotificationInstance())
    monkeypatch.setattr(main_mod, "update_devices_names", lambda pm: None)
    monkeypatch.setattr(main_mod, "WorkflowManager", _FakeWorkflowManager)
    monkeypatch.setattr(main_mod, "UserEventsQueueInstance", lambda: SimpleNamespace(
        has_update_devices=lambda: False
    ))

    with pytest.raises(_StopTestLoop):
        main_mod.main()

    row = conn.execute("SELECT COUNT(*) FROM Resource_History").fetchone()
    assert row[0] == 0, "MAINT_PERF_DAYS=0 must produce zero Resource_History rows"


def test_maint_perf_days_non_numeric_disables_instead_of_crashing(monkeypatch, main_mod):
    """
    Regression: an empty/corrupted MAINT_PERF_DAYS setting value must disable
    the optional feature, not raise ValueError/TypeError and kill the whole
    main loop - this int() call sits outside the tick's own try/except/finally,
    so it has no other safety net.
    """
    conn = make_db()
    rh_upgrade_conn = conn.cursor()
    from server.db.db_upgrade import ensure_Resource_History
    ensure_Resource_History(rh_upgrade_conn)
    conn.commit()
    db = _FakeDB(conn)

    fake_pm = _FakePM(raise_on_schedule=False)
    _common_patches(monkeypatch, main_mod, db, fake_pm)
    # Simulate a corrupted/empty setting value instead of a real integer.
    monkeypatch.setattr(main_mod, "get_setting_value", lambda key, default=None: "" if key == "MAINT_PERF_DAYS" else default)
    monkeypatch.setattr(main_mod, "get_notifications", lambda db: {})
    monkeypatch.setattr(main_mod, "NotificationInstance", lambda db: _FakeNotificationInstance())
    monkeypatch.setattr(main_mod, "update_devices_names", lambda pm: None)
    monkeypatch.setattr(main_mod, "WorkflowManager", _FakeWorkflowManager)
    monkeypatch.setattr(main_mod, "UserEventsQueueInstance", lambda: SimpleNamespace(
        has_update_devices=lambda: False
    ))

    # Must reach the sentinel (i.e. complete the tick normally), not raise ValueError.
    with pytest.raises(_StopTestLoop):
        main_mod.main()

    row = conn.execute("SELECT COUNT(*) FROM Resource_History").fetchone()
    assert row[0] == 0, "A non-numeric MAINT_PERF_DAYS must disable collection, not crash"


def test_after_sample_precedes_insert_and_final_commit(monkeypatch, main_mod):
    """Self-measurement boundary: the 'after' sample and insert_resource_history()
    must both run before the tick's own later db.commitDB() calls, so the
    feature's own write never inflates what it reports."""
    conn = make_db()
    rh_upgrade_conn = conn.cursor()
    from server.db.db_upgrade import ensure_Resource_History
    ensure_Resource_History(rh_upgrade_conn)
    conn.commit()
    db = _FakeDB(conn)

    call_order = []
    real_commit = db.commitDB
    real_get_times = rh.get_process_cpu_times_and_io
    real_insert = rh.insert_resource_history

    def spy_commit():
        call_order.append("commitDB")
        return real_commit()

    def spy_get_times():
        call_order.append("sample")
        return real_get_times()

    def spy_insert(*args, **kwargs):
        call_order.append("insert")
        return real_insert(*args, **kwargs)

    db.commitDB = spy_commit

    fake_pm = _FakePM(raise_on_schedule=False)
    _common_patches(monkeypatch, main_mod, db, fake_pm)
    monkeypatch.setattr(main_mod, "get_process_cpu_times_and_io", spy_get_times)
    monkeypatch.setattr(main_mod, "insert_resource_history", spy_insert)
    monkeypatch.setattr(main_mod, "get_notifications", lambda db: {})
    monkeypatch.setattr(main_mod, "NotificationInstance", lambda db: _FakeNotificationInstance())
    monkeypatch.setattr(main_mod, "update_devices_names", lambda pm: None)
    monkeypatch.setattr(main_mod, "WorkflowManager", _FakeWorkflowManager)
    monkeypatch.setattr(main_mod, "UserEventsQueueInstance", lambda: SimpleNamespace(
        has_update_devices=lambda: False
    ))

    with pytest.raises(_StopTestLoop):
        main_mod.main()

    insert_index = call_order.index("insert")
    # Both samples (pre and post) happen before the insert...
    assert call_order[:insert_index].count("sample") == 2
    # ...and every commitDB() recorded happens after the insert, not before it.
    commits_before_insert = call_order[:insert_index].count("commitDB")
    assert commits_before_insert == 0, (
        f"insert_resource_history() must run before the tick's own commitDB() calls, "
        f"call order was: {call_order}"
    )


# ---------------------------------------------------------------------------
# Non-interference regression test (Design §1's correction): the /health
# live gauge (cpu_percent-based) must not affect the tick-scoped sampler's
# own computation, since they use independent Process() objects.
# ---------------------------------------------------------------------------

def test_health_gauge_does_not_affect_tick_scoped_sampling(monkeypatch):
    from server.api_server import health_endpoint

    pre = rh.get_process_cpu_times_and_io()

    # Simulate /health being polled mid-tick, between the two tick-scoped samples.
    health_endpoint.get_process_cpu_percent()

    post = rh.get_process_cpu_times_and_io()

    db = _make_resource_history_db()
    rh.insert_resource_history(db, pre, post, duration_ms=1000)

    row = db.sql.execute("SELECT resCpuPercent FROM Resource_History").fetchone()
    # Purely a non-crash / non-interference check - the /health call must not
    # raise or corrupt the tick-scoped computation's independent state.
    assert row[0] is not None
