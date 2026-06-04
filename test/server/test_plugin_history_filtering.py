"""
Tests for the Plugins_History selective recording introduced to prevent
unbounded table growth.

Verifies that process_plugin_events() only writes history rows for objects
whose state actually changed in the current cycle:
  - new objects
  - watched-changed objects
  - missing-in-last-scan (first transition only)

Objects that are watched-not-changed or already missing should NOT generate
history entries.
"""

import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

# Test helpers (shared DDL, fake DB, factories)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    make_plugin_db,
    make_plugin_dict,
    make_plugin_event_row,
    seed_plugin_object,
    plugin_history_rows,
    plugin_objects_rows,
)

from plugin import process_plugin_events  # noqa: E402

PREFIX = "TESTPLG"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plugin_db():
    """Yield a (PluginFakeDB, connection) backed by an in-memory SQLite database."""
    db, conn = make_plugin_db()
    yield db, conn
    conn.close()


def _no_report_on(key):
    """Monkeypatch target: return empty REPORT_ON so no events are generated."""
    return [] if key.endswith("_REPORT_ON") else ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHistoryOnlyRecordsChanges:
    """Core assertion: unchanged objects must NOT appear in Plugins_History."""

    def test_new_object_recorded_in_history(self, plugin_db, monkeypatch):
        """A brand-new object should produce exactly one history row."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        plugin = make_plugin_dict(PREFIX)
        events = [make_plugin_event_row(PREFIX, "device_A")]

        process_plugin_events(db, plugin, events)

        rows = plugin_history_rows(conn, PREFIX)
        assert len(rows) == 1
        assert rows[0][2] == "device_A"  # objectPrimaryId

    def test_unchanged_object_not_recorded(self, plugin_db, monkeypatch):
        """An object with watched-not-changed should NOT appear in history."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "device_A", watched1="val1",
                           status="watched-not-changed")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        events = [make_plugin_event_row(PREFIX, "device_A", watched1="val1")]

        process_plugin_events(db, plugin, events)

        rows = plugin_history_rows(conn, PREFIX)
        assert len(rows) == 0, (
            "watched-not-changed objects should not generate history rows"
        )

    def test_watched_changed_recorded(self, plugin_db, monkeypatch):
        """An object whose watched column changed should appear in history."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "device_A", watched1="old_value",
                           status="watched-not-changed")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        events = [make_plugin_event_row(PREFIX, "device_A", watched1="new_value")]

        process_plugin_events(db, plugin, events)

        rows = plugin_history_rows(conn, PREFIX)
        assert len(rows) == 1
        assert rows[0][2] == "device_A"

    def test_missing_first_time_recorded(self, plugin_db, monkeypatch):
        """An object going missing for the first time should appear in history."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "device_A", status="watched-not-changed")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        events = []  # No events reported — device_A is now missing

        process_plugin_events(db, plugin, events)

        rows = plugin_history_rows(conn, PREFIX)
        assert len(rows) == 1
        assert rows[0][2] == "device_A"

    def test_already_missing_not_re_recorded(self, plugin_db, monkeypatch):
        """An object already marked missing-in-last-scan should NOT produce
        another history row on subsequent runs."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "device_A",
                           status="missing-in-last-scan")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        events = []  # still missing

        process_plugin_events(db, plugin, events)

        rows = plugin_history_rows(conn, PREFIX)
        assert len(rows) == 0, (
            "already-missing objects should not generate additional history rows"
        )

    def test_mixed_scenario(self, plugin_db, monkeypatch):
        """Simulate a realistic mixed run: new + unchanged + changed + missing."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "unchanged", watched1="same",
                           status="watched-not-changed")
        seed_plugin_object(cur, PREFIX, "will_change", watched1="old",
                           status="watched-not-changed")
        seed_plugin_object(cur, PREFIX, "will_vanish",
                           status="watched-not-changed")
        seed_plugin_object(cur, PREFIX, "already_gone",
                           status="missing-in-last-scan")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        events = [
            make_plugin_event_row(PREFIX, "brand_new"),                       # new
            make_plugin_event_row(PREFIX, "unchanged", watched1="same"),      # no change
            make_plugin_event_row(PREFIX, "will_change", watched1="new"),     # changed
            # will_vanish not reported  → first-time missing
            # already_gone not reported → still missing (no history)
        ]

        process_plugin_events(db, plugin, events)

        rows = plugin_history_rows(conn, PREFIX)
        recorded_ids = {r[2] for r in rows}  # objectPrimaryId

        assert "brand_new" in recorded_ids, "new object should be in history"
        assert "will_change" in recorded_ids, "changed object should be in history"
        assert "will_vanish" in recorded_ids, "first-time missing should be in history"
        assert "unchanged" not in recorded_ids, "unchanged should NOT be in history"
        assert "already_gone" not in recorded_ids, "already-missing should NOT be in history"
        assert len(rows) == 3

    def test_objects_table_still_updated_for_unchanged(self, plugin_db, monkeypatch):
        """Even though history is skipped, Plugins_Objects must still be updated
        for unchanged objects (no regression)."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "device_A", watched1="val1",
                           status="watched-not-changed")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        events = [make_plugin_event_row(PREFIX, "device_A", watched1="val1")]

        process_plugin_events(db, plugin, events)

        objs = plugin_objects_rows(conn, PREFIX)
        assert len(objs) == 1, "Plugins_Objects should still have the object"

    def test_recovery_from_missing_recorded(self, plugin_db, monkeypatch):
        """An object that was missing-in-last-scan and reappears (even with
        unchanged watched values) should produce a history row."""
        db, conn = plugin_db
        monkeypatch.setattr("plugin.get_setting_value", _no_report_on)

        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "device_A", watched1="val1",
                           status="missing-in-last-scan")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        # device_A reappears with the same watched value
        events = [make_plugin_event_row(PREFIX, "device_A", watched1="val1")]

        process_plugin_events(db, plugin, events)

        rows = plugin_history_rows(conn, PREFIX)
        assert len(rows) == 1, (
            "recovery from missing-in-last-scan should generate a history row"
        )
        assert rows[0][2] == "device_A"
