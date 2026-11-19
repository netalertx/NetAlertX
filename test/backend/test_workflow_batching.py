"""
Tests for Fix 4 of the main-loop crash-resilience work: batching
AppEvents writes per event batch instead of one commit per event.

Covers:
  - mark_processed_batch() (server/workflows/app_events.py)
  - WorkflowManager.process_event_batch() and the mark_done parameter on
    process_event() (server/workflows/manager.py)
  - The replay-blast-radius tradeoff this introduces (bounded by
    BATCH_WRITE_CHUNK_SIZE) and why it's safe given the current, real
    action implementations (idempotent replay)

Uses a real file-based SQLite DB (not :memory:) for the Devices table,
since UpdateFieldAction/DeleteObjectAction route through DeviceInstance(),
which opens its own connection via database.get_temp_db_connection() against
database.fullDbPath - a separate connection from the one these tests hold
directly, exactly like the real main loop vs. model-layer split.
"""

import os
import sys
import sqlite3
import tempfile
import shutil
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db_test_helpers import CREATE_DEVICES, make_device_dict, insert_device_from_dict  # noqa: E402

CREATE_APP_EVENTS = """
CREATE TABLE IF NOT EXISTS "AppEvents" (
    "index" INTEGER PRIMARY KEY AUTOINCREMENT,
    "guid" TEXT UNIQUE,
    "appEventProcessed" BOOLEAN DEFAULT 0,
    "objectType" TEXT,
    "objectGuid" TEXT,
    "appEventType" TEXT
)
"""


class _DummyDB:
    """Minimal DB wrapper matching the interface WorkflowManager expects."""

    def __init__(self, conn):
        self.sql = conn.cursor()
        self._conn = conn

    def commitDB(self):
        self._conn.commit()


class WorkflowBatchingTestCase(unittest.TestCase):
    """Base class: a real file-based Devices + AppEvents DB, and a
    WorkflowManager with no workflows loaded by default (tests add their
    own via self.mgr.workflows)."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._tmpdir, "test_app.db")
        self._patcher = patch("database.fullDbPath", self._db_path)
        self._patcher.start()

        self.conn = sqlite3.connect(self._db_path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(CREATE_DEVICES)
        self.conn.execute(CREATE_APP_EVENTS)

        self.db = _DummyDB(self.conn)

        from workflows.manager import WorkflowManager
        with patch.object(WorkflowManager, "load_workflows", return_value=[]):
            self.mgr = WorkflowManager(self.db)

    def tearDown(self):
        self._patcher.stop()
        self.conn.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _insert_app_event(self, guid, obj_guid, obj_type="Devices", event_type="update"):
        cur = self.conn.execute(
            'INSERT INTO "AppEvents" (guid, objectGuid, objectType, appEventType, appEventProcessed) '
            "VALUES (?, ?, ?, ?, 0)",
            (guid, obj_guid, obj_type, event_type),
        )
        return cur.lastrowid

    def _get_event_row(self, index):
        return self.conn.execute('SELECT * FROM "AppEvents" WHERE "index" = ?', (index,)).fetchone()

    def _is_processed(self, index):
        row = self._get_event_row(index)
        return bool(row["appEventProcessed"]) if row else None

    def _insert_test_device(self, mac="aa:bb:cc:dd:ee:01", **overrides):
        device = make_device_dict(mac, **overrides)
        insert_device_from_dict(self.conn, device)
        self.conn.commit()
        return device["devGUID"]

    @staticmethod
    def _always_true_workflow(name, mac, actions):
        """A minimal, always-enabled workflow whose single condition
        trivially matches the given device's own devMac - avoids needing a
        real business condition for tests that just need "this runs"."""
        return {
            "name": name,
            "enabled": "Yes",
            "trigger": {"object_type": "Devices", "event_type": "update"},
            "conditions": [{"logic": "AND", "conditions": [
                {"field": "devMac", "operator": "equals", "value": mac}
            ]}],
            "actions": actions,
        }


class TestMarkProcessedBatch(WorkflowBatchingTestCase):
    def test_mark_processed_batch_marks_all_given_indices(self):
        from workflows.app_events import mark_processed_batch

        idx1 = self._insert_app_event("g1", "dev-1")
        idx2 = self._insert_app_event("g2", "dev-2")
        idx3 = self._insert_app_event("g3", "dev-3")

        mark_processed_batch(self.db, [idx1, idx2, idx3])

        self.assertTrue(self._is_processed(idx1))
        self.assertTrue(self._is_processed(idx2))
        self.assertTrue(self._is_processed(idx3))

    def test_mark_processed_batch_empty_list_is_noop(self):
        # sqlite3.Connection.execute is a read-only C-extension slot and
        # cannot be monkeypatched (confirmed in Fix 1's design) - spy on
        # db.commitDB() instead, a plain Python method on _DummyDB, to
        # confirm an empty list short-circuits before even attempting a write.
        from workflows.app_events import mark_processed_batch

        with patch.object(self.db, "commitDB") as spy:
            mark_processed_batch(self.db, [])
        spy.assert_not_called()


class TestProcessEventBatch(WorkflowBatchingTestCase):
    def test_process_event_batch_empty_list_is_noop(self):
        with patch("workflows.manager.mark_processed_batch") as spy:
            self.mgr.process_event_batch([])
        spy.assert_not_called()

    def test_process_event_batch_calls_workflows_then_marks_all_processed_once(self):
        mac = "aa:bb:cc:dd:ee:02"
        guid = self._insert_test_device(mac=mac, devIsNew=0)
        wf = self._always_true_workflow(
            "wf1", mac, [{"type": "update_field", "field": "devIsNew", "value": "1"}]
        )
        self.mgr.workflows = [wf]

        idx1 = self._insert_app_event("g1", guid)
        idx2 = self._insert_app_event("g2", guid)

        with patch("workflows.manager.mark_processed_batch", wraps=__import__(
            "workflows.app_events", fromlist=["mark_processed_batch"]
        ).mark_processed_batch) as spy:
            self.mgr.process_event_batch([
                self._get_event_row(idx1), self._get_event_row(idx2),
            ])
            self.assertEqual(spy.call_count, 1)  # one write for the whole batch, not two

        self.assertTrue(self._is_processed(idx1))
        self.assertTrue(self._is_processed(idx2))

        row = self.conn.execute("SELECT devIsNew FROM Devices WHERE devGUID = ?", (guid,)).fetchone()
        self.assertEqual(row["devIsNew"], 1)

    def test_cascade_skipped_event_still_included_in_batch_mark(self):
        guid = self._insert_test_device()
        self.mgr.workflows = []
        self.mgr._mutated_guids.add(guid)

        idx = self._insert_app_event("g1", guid)
        self.mgr.process_event_batch([self._get_event_row(idx)])

        self.assertTrue(self._is_processed(idx))

    def test_event_with_no_matching_workflow_still_marked_processed(self):
        guid = self._insert_test_device()
        self.mgr.workflows = []  # no workflows at all -> nothing triggers

        idx = self._insert_app_event("g1", guid)
        self.mgr.process_event_batch([self._get_event_row(idx)])

        self.assertTrue(self._is_processed(idx))

    def test_action_exception_mid_batch_leaves_whole_chunk_unmarked(self):
        """Documents the accepted tradeoff: process_event_batch() adds no new
        per-action exception handling (that would risk silently masking a
        real bug forever) - an action exception propagates and the whole
        chunk is left unmarked for replay, exactly as an action bug already
        crashes the main loop today, unbatched."""
        mac = "aa:bb:cc:dd:ee:03"
        guid = self._insert_test_device(mac=mac)
        wf = self._always_true_workflow(
            "wf-raises", mac, [{"type": "update_field", "field": "devIsNew", "value": "1"}]
        )
        self.mgr.workflows = [wf]

        idx1 = self._insert_app_event("g1", guid)
        idx2 = self._insert_app_event("g2", guid)

        with patch(
            "workflows.actions.UpdateFieldAction.execute",
            side_effect=ValueError("simulated action bug"),
        ):
            with self.assertRaises(ValueError):
                self.mgr.process_event_batch([
                    self._get_event_row(idx1), self._get_event_row(idx2),
                ])

        self.assertFalse(self._is_processed(idx1))
        self.assertFalse(self._is_processed(idx2))

    def test_batch_write_chunking_bounds_crash_blast_radius(self):
        from workflows import manager as manager_mod

        guid = self._insert_test_device()
        self.mgr.workflows = []

        chunk_size = manager_mod.BATCH_WRITE_CHUNK_SIZE
        total = chunk_size + 50
        indices = [self._insert_app_event(f"g{i}", guid) for i in range(total)]

        call_count = {"n": 0}
        real_mark_batch = manager_mod.mark_processed_batch

        def failing_on_second_chunk(db, event_indices):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("simulated crash during the second chunk's write")
            real_mark_batch(db, event_indices)

        events = [self._get_event_row(i) for i in indices]
        with patch("workflows.manager.mark_processed_batch", side_effect=failing_on_second_chunk):
            with self.assertRaises(RuntimeError):
                self.mgr.process_event_batch(events)

        # First chunk already committed before the second chunk's write failed.
        for i in indices[:chunk_size]:
            self.assertTrue(self._is_processed(i))
        # Second (final, smaller) chunk never got marked.
        for i in indices[chunk_size:]:
            self.assertFalse(self._is_processed(i))


class TestProcessEventMarkDoneParameter(WorkflowBatchingTestCase):
    """Protects the mark_done backward-compatibility contract: any direct
    caller of process_event() (e.g. test/backend/test_workflows.py:421)
    must keep its original per-event-commit behavior by default."""

    def test_process_event_default_mark_done_preserves_direct_caller_behavior(self):
        guid = self._insert_test_device()
        self.mgr.workflows = []
        idx = self._insert_app_event("g1", guid)

        self.mgr.process_event(self._get_event_row(idx))  # no mark_done argument

        self.assertTrue(self._is_processed(idx))

    def test_process_event_mark_done_false_does_not_mark(self):
        guid = self._insert_test_device()
        self.mgr.workflows = []
        idx = self._insert_app_event("g1", guid)

        self.mgr.process_event(self._get_event_row(idx), mark_done=False)

        self.assertFalse(self._is_processed(idx))


class TestActionReplayIdempotency(WorkflowBatchingTestCase):
    """The concrete idempotency proof behind Fix 4's safety claim."""

    def test_replaying_update_field_action_is_idempotent(self):
        from workflows.actions import UpdateFieldAction
        from workflows.triggers import Trigger

        mac = "aa:bb:cc:dd:ee:04"
        guid = self._insert_test_device(mac=mac, devIsNew=0)
        event = {"objectType": "Devices", "appEventType": "update", "objectGuid": guid}

        for _ in range(2):  # simulate a crash-and-replay: apply it twice
            trigger = Trigger({"object_type": "Devices", "event_type": "update"}, event, self.db)
            UpdateFieldAction(self.db, "devIsNew", "1", trigger).execute()

            row = self.conn.execute(
                "SELECT devIsNew FROM Devices WHERE devGUID = ?", (guid,)
            ).fetchone()
            self.assertEqual(row["devIsNew"], 1)

    def test_replaying_delete_object_action_is_idempotent(self):
        from workflows.actions import DeleteObjectAction
        from workflows.triggers import Trigger

        guid = self._insert_test_device()
        event = {"objectType": "Devices", "appEventType": "update", "objectGuid": guid}

        trigger = Trigger({"object_type": "Devices", "event_type": "update"}, event, self.db)
        DeleteObjectAction(self.db, trigger).execute()  # first application: device deleted

        row = self.conn.execute("SELECT * FROM Devices WHERE devGUID = ?", (guid,)).fetchone()
        self.assertIsNone(row)

        # Replay: a fresh Trigger lookup finds nothing, so the action's own
        # existence guard must no-op rather than reach DeviceInstance.delete()
        # a second time (which would raise ValueError on a missing GUID).
        trigger2 = Trigger({"object_type": "Devices", "event_type": "update"}, event, self.db)
        self.assertIsNone(trigger2.object)
        DeleteObjectAction(self.db, trigger2).execute()  # must not raise

        row = self.conn.execute("SELECT * FROM Devices WHERE devGUID = ?", (guid,)).fetchone()
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
