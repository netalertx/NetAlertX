"""
Tests for execute_plugin()'s handling of a script plugin that runs
successfully but legitimately finds zero entries this cycle.

Before this fix, execute_plugin() treated "zero output rows" as a single
case, whether caused by a crashed/timed-out subprocess or by a script that
ran to completion and legitimately found nothing. That meant
process_plugin_events() was skipped whenever a script plugin's result
normalized to zero rows, so previously-tracked objects never transitioned to
"missing-in-last-scan" when everything that plugin was tracking disappeared
at once (e.g. the omada_sdn_openapi plugin's include_offline filter making
every device at a site offline at the same time).

_plugin_produced_no_output() isolates the gating decision so it's directly
testable without mocking subprocess/file I/O.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    make_plugin_db,
    make_plugin_dict,
    seed_plugin_object,
    plugin_objects_rows,
)

from plugin import process_plugin_events, _plugin_produced_no_output  # noqa: E402

PREFIX = "TESTPLG"


@pytest.fixture
def plugin_db():
    db, conn = make_plugin_db()
    yield db, conn
    conn.close()


class TestPluginProducedNoOutput:
    """Pure truth-table coverage for the extracted gating helper."""

    def test_crashed_script_subprocess_is_treated_as_no_output(self):
        assert _plugin_produced_no_output("script", [], subprocess_ok=False) is True

    def test_successful_script_run_with_zero_entries_is_not_no_output(self):
        """A script that completed without crashing but found nothing must
        still be allowed to reach process_plugin_events()."""
        assert _plugin_produced_no_output("script", [], subprocess_ok=True) is False

    def test_script_with_entries_is_never_no_output(self):
        assert _plugin_produced_no_output("script", [("row",)], subprocess_ok=False) is False

    def test_non_script_plugin_behavior_is_unchanged(self):
        """app-db-query/sqlite-db-query have no subprocess step and already
        return early on failure - zero rows must still mean "skip", exactly
        like before this fix."""
        assert _plugin_produced_no_output("app-db-query", [], subprocess_ok=True) is True
        assert _plugin_produced_no_output("sqlite-db-query", [], subprocess_ok=True) is True


class TestProcessPluginEventsWithEmptyList:
    """Validates the assumption the gating fix relies on: calling
    process_plugin_events() with an empty events list is what actually
    produces the "missing-in-last-scan" transition for existing objects."""

    def test_empty_events_marks_existing_object_missing(self, plugin_db):
        db, conn = plugin_db
        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "aa:bb:cc:dd:ee:01", status="watched-not-changed")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        process_plugin_events(db, plugin, [])

        rows = plugin_objects_rows(conn, PREFIX)
        assert len(rows) == 1
        assert rows[0][10] == "missing-in-last-scan"  # "status" column

    def test_already_missing_object_is_not_remarked_changed(self, plugin_db):
        db, conn = plugin_db
        cur = conn.cursor()
        seed_plugin_object(cur, PREFIX, "aa:bb:cc:dd:ee:02", status="missing-in-last-scan")
        conn.commit()

        plugin = make_plugin_dict(PREFIX)
        process_plugin_events(db, plugin, [])

        row = plugin_objects_rows(conn, PREFIX)[0]
        assert row[10] == "missing-in-last-scan"  # "status" column
