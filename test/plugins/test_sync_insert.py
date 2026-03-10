"""
Tests for the SYNC plugin's schema-aware device insert logic.

The core invariant: only columns that actually exist in the Devices table
are included in the INSERT statement. Computed/virtual fields (devStatus,
devIsSleeping, devFlapping) and unknown future columns must be silently
dropped — never cause an OperationalError.
"""

import sys
import os

import pytest

# Ensure shared helpers and server code are importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))

from db_test_helpers import make_db, make_device_dict, sync_insert_devices  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    """Fresh in-memory DB with the Devices table and all views."""
    return make_db()


class TestSyncInsertSchemaAware:

    def test_clean_device_inserts_successfully(self, conn):
        """Happy path: a well-formed device dict inserts without error."""
        device = make_device_dict()
        inserted = sync_insert_devices(conn, [device])
        assert inserted == 1

        cur = conn.cursor()
        cur.execute("SELECT devMac FROM Devices WHERE devMac = ?", (device["devMac"],))
        row = cur.fetchone()
        assert row is not None

    def test_computed_devStatus_is_silently_dropped(self, conn):
        """devStatus is a computed view column — must NOT raise OperationalError."""
        device = make_device_dict()
        device["devStatus"] = "Online"  # computed in DevicesView, not in Devices table

        # Pre-fix this would raise: sqlite3.OperationalError: table Devices has no column named devStatus
        inserted = sync_insert_devices(conn, [device])
        assert inserted == 1

    def test_computed_devIsSleeping_is_silently_dropped(self, conn):
        """devIsSleeping is a CTE/view column — must NOT raise OperationalError."""
        device = make_device_dict()
        device["devIsSleeping"] = 0  # the exact field that triggered the original bug report

        inserted = sync_insert_devices(conn, [device])
        assert inserted == 1

    def test_computed_devFlapping_is_silently_dropped(self, conn):
        """devFlapping is also computed in the view."""
        device = make_device_dict()
        device["devFlapping"] = 0

        inserted = sync_insert_devices(conn, [device])
        assert inserted == 1

    def test_rowid_is_silently_dropped(self, conn):
        """rowid must never appear in an INSERT column list."""
        device = make_device_dict()
        device["rowid"] = 42

        inserted = sync_insert_devices(conn, [device])
        assert inserted == 1

    def test_all_computed_fields_at_once(self, conn):
        """All known computed/virtual columns together — none should abort the insert."""
        device = make_device_dict()
        device["rowid"] = 99
        device["devStatus"] = "Online"
        device["devIsSleeping"] = 0
        device["devFlapping"] = 0
        device["totally_unknown_future_column"] = "ignored"

        inserted = sync_insert_devices(conn, [device])
        assert inserted == 1

    def test_batch_insert_multiple_devices(self, conn):
        """Multiple devices with computed fields all insert correctly."""
        devices = []
        for i in range(3):
            d = make_device_dict(mac=f"aa:bb:cc:dd:ee:{i:02x}")
            d["devGUID"] = f"guid-{i}"
            d["devStatus"] = "Online"          # computed
            d["devIsSleeping"] = 0             # computed
        devices.append(d)

        inserted = sync_insert_devices(conn, devices)
        assert inserted == len(devices)

    def test_values_aligned_with_columns_after_filtering(self, conn):
        """Values must be extracted in the same order as insert_cols (alignment bug guard)."""
        device = make_device_dict()
        device["devStatus"] = "SHOULD_BE_DROPPED"
        device["devIsSleeping"] = 999

        sync_insert_devices(conn, [device])

        cur = conn.cursor()
        cur.execute("SELECT devName, devVendor, devLastIP FROM Devices WHERE devMac = ?", (device["devMac"],))
        row = cur.fetchone()
        assert row["devName"] == "Test Device"
        assert row["devVendor"] == "Acme"
        assert row["devLastIP"] == "192.168.1.10"

    def test_unknown_column_does_not_prevent_insert(self, conn):
        """A column that was added on the node but doesn't exist on the hub is dropped."""
        device = make_device_dict()
        device["devNewFeatureOnlyOnNode"] = "some_value"

        # Must not raise — hub schema wins
        inserted = sync_insert_devices(conn, [device])
        assert inserted == 1

    def test_empty_device_list_returns_zero(self, conn):
        """Edge case: empty list should not raise and should return 0."""
        inserted = sync_insert_devices(conn, [])
        assert inserted == 0
