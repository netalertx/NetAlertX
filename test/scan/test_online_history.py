"""
Unit tests for insertOnlineHistory() (server/scan/session_events.py).

Covers GitHub issue #1876: Device Cards and the Presence page's historical
chart disagreed on "offline" device counts, and the chart occasionally showed
negative offline values.

Root cause: offlineDevices was derived as allDevices - archivedDevices -
onlineDevices, where onlineDevices (devPresentLastScan=1) was not filtered by
devIsArchived. Archiving a device does not stop it from being scanned, so an
archived-but-still-present device was counted in both archivedDevices and
onlineDevices and subtracted from allDevices twice, undercounting (and
potentially going negative) instead of matching the Cards tile's definition
(devIsArchived=0 AND devPresentLastScan=0).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    make_db,
    make_device_dict,
    insert_device_from_dict,
    DummyDB,
)

from scan.session_events import insertOnlineHistory  # noqa: E402


def _seed(conn, devices):
    for d in devices:
        insert_device_from_dict(conn, d)
    conn.commit()


def _fetch_latest_history_row(conn):
    row = conn.execute(
        "SELECT * FROM Online_History ORDER BY \"index\" DESC LIMIT 1"
    ).fetchone()
    return dict(row)


class TestInsertOnlineHistoryOfflineCount:
    def test_offline_count_matches_cards_definition(self):
        """
        offlineDevices must equal COUNT(devIsArchived=0 AND devPresentLastScan=0),
        the same definition used by the Device Cards tile (db_helper.get_device_conditions).
        """
        conn = make_db()
        _seed(conn, [
            make_device_dict("aa:bb:cc:dd:ee:01", devPresentLastScan=1, devIsArchived=0),
            make_device_dict("aa:bb:cc:dd:ee:02", devPresentLastScan=0, devIsArchived=0),
            make_device_dict("aa:bb:cc:dd:ee:03", devPresentLastScan=0, devIsArchived=0),
            make_device_dict("aa:bb:cc:dd:ee:04", devPresentLastScan=0, devIsArchived=1),
        ])

        db = DummyDB(conn)
        insertOnlineHistory(db)
        db.commitDB()

        history = _fetch_latest_history_row(conn)
        assert history["offlineDevices"] == 2, (
            f"Expected 2 offline (non-archived, not present), got {history['offlineDevices']}"
        )

    def test_archived_but_still_present_device_does_not_corrupt_offline_count(self):
        """
        An archived device that is still answering scans (devIsArchived=1 AND
        devPresentLastScan=1) must not be double-subtracted from offlineDevices.
        Before the fix this produced a negative offlineDevices value.
        """
        conn = make_db()
        _seed(conn, [
            # Archived but still present on the network - a normal state, since
            # archiving a device does not stop it from being scanned.
            make_device_dict("aa:bb:cc:dd:ee:01", devPresentLastScan=1, devIsArchived=1),
            # One genuinely offline, non-archived device.
            make_device_dict("aa:bb:cc:dd:ee:02", devPresentLastScan=0, devIsArchived=0),
        ])

        db = DummyDB(conn)
        insertOnlineHistory(db)
        db.commitDB()

        history = _fetch_latest_history_row(conn)
        assert history["offlineDevices"] == 1, (
            f"Expected 1 offline device, got {history['offlineDevices']} (must never be negative)"
        )
        assert history["offlineDevices"] >= 0
