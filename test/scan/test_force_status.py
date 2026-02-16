"""Tests for forced device status updates."""

import sqlite3

from server.scan import device_handling


class DummyDB:
    """Minimal DB wrapper compatible with device_handling helpers."""

    def __init__(self, conn):
        self.sql = conn.cursor()
        self._conn = conn

    def commitDB(self):
        self._conn.commit()


def test_force_status_updates_present_flag():
    """Forced status should override devPresentLastScan for online/offline values."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE Devices (
            devMac TEXT PRIMARY KEY,
            devPresentLastScan INTEGER,
            devForceStatus TEXT
        )
        """
    )

    cur.executemany(
        """
        INSERT INTO Devices (devMac, devPresentLastScan, devForceStatus)
        VALUES (?, ?, ?)
        """,
        [
            ("AA:AA:AA:AA:AA:01", 0, "online"),
            ("AA:AA:AA:AA:AA:02", 1, "offline"),
            ("AA:AA:AA:AA:AA:03", 1, "dont_force"),
            ("AA:AA:AA:AA:AA:04", 0, None),
            ("AA:AA:AA:AA:AA:05", 0, "ONLINE"),
        ],
    )
    conn.commit()

    db = DummyDB(conn)
    updated = device_handling.update_devPresentLastScan_based_on_force_status(db)

    rows = {
        row["devMac"]: row["devPresentLastScan"]
        for row in cur.execute("SELECT devMac, devPresentLastScan FROM Devices")
    }

    assert updated == 3
    assert rows["AA:AA:AA:AA:AA:01"] == 1
    assert rows["AA:AA:AA:AA:AA:02"] == 0
    assert rows["AA:AA:AA:AA:AA:03"] == 1
    assert rows["AA:AA:AA:AA:AA:04"] == 0
    assert rows["AA:AA:AA:AA:AA:05"] == 1

    conn.close()
