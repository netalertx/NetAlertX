"""
Unit tests for the DevicesView SQL view built by ensure_views().

Regression coverage:
- NULL devAlertDown must NOT be treated as != 0 (IFNULL bug: '' vs 0).
- devCanSleep / devIsSleeping suppression within the sleep window.
- Only devices with devAlertDown = 1 AND devPresentLastScan = 0 appear in
  the "Device Down" event query.

Each test uses an isolated in-memory SQLite database so it has no
dependency on the running application or config.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    make_db as _make_db,
    minutes_ago as _minutes_ago,
    insert_device as _insert_device,
)


# ---------------------------------------------------------------------------
# Tests: devAlertDown NULL coercion
# ---------------------------------------------------------------------------

class TestAlertDownNullCoercion:
    """
    Guard against the IFNULL(devAlertDown, '') bug.

    When devAlertDown IS NULL and the view uses IFNULL(..., ''), the text value
    '' satisfies `!= 0` in SQLite (text > integer), causing spurious down events.
    The fix is IFNULL(devAlertDown, 0) so NULL → 0, and 0 != 0 is FALSE.
    """

    def test_null_alert_down_not_in_down_event_query(self):
        """A device with NULL devAlertDown must NOT appear in the down-event query."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "AA:BB:CC:DD:EE:01", alert_down=None, present_last_scan=0)
        conn.commit()

        cur.execute("""
            SELECT devMac FROM DevicesView
            WHERE devAlertDown != 0
              AND devPresentLastScan = 0
        """)
        rows = cur.fetchall()
        macs = [r["devMac"] for r in rows]
        assert "AA:BB:CC:DD:EE:01" not in macs, (
            "Device with NULL devAlertDown must not fire a down event "
            "(IFNULL coercion regression)"
        )

    def test_zero_alert_down_not_in_down_event_query(self):
        """A device with explicit devAlertDown=0 must NOT appear."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "AA:BB:CC:DD:EE:02", alert_down=0, present_last_scan=0)
        conn.commit()

        cur.execute(
            "SELECT devMac FROM DevicesView WHERE devAlertDown != 0 AND devPresentLastScan = 0"
        )
        macs = [r["devMac"] for r in cur.fetchall()]
        assert "AA:BB:CC:DD:EE:02" not in macs

    def test_one_alert_down_in_down_event_query(self):
        """A device with devAlertDown=1 and absent MUST appear in the down-event query."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "AA:BB:CC:DD:EE:03", alert_down=1, present_last_scan=0)
        conn.commit()

        cur.execute(
            "SELECT devMac FROM DevicesView WHERE devAlertDown != 0 AND devPresentLastScan = 0"
        )
        macs = [r["devMac"] for r in cur.fetchall()]
        # DevicesView returns LOWER(devMac), so compare against lowercase
        assert "aa:bb:cc:dd:ee:03" in macs

    def test_online_device_not_in_down_event_query(self):
        """An online device (devPresentLastScan=1) should never fire a down event."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "AA:BB:CC:DD:EE:04", alert_down=1, present_last_scan=1)
        conn.commit()

        cur.execute(
            "SELECT devMac FROM DevicesView WHERE devAlertDown != 0 AND devPresentLastScan = 0"
        )
        macs = [r["devMac"] for r in cur.fetchall()]
        assert "AA:BB:CC:DD:EE:04" not in macs


# ---------------------------------------------------------------------------
# Tests: devIsSleeping suppression
# ---------------------------------------------------------------------------

class TestIsSleepingSuppression:
    """
    When devCanSleep=1 and the device has been absent for less than
    NTFPRCS_sleep_time minutes, devIsSleeping must be 1 and the device
    must NOT appear in the down-event query.
    """

    def test_sleeping_device_is_marked_sleeping(self):
        """devCanSleep=1, absent, last seen 5 min ago → devIsSleeping=1."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(
            cur, "BB:BB:BB:BB:BB:01",
            alert_down=1, present_last_scan=0,
            can_sleep=1, last_connection=_minutes_ago(5),
        )
        conn.commit()

        # DevicesView returns LOWER(devMac); query must use lowercase
        cur.execute("SELECT devIsSleeping FROM DevicesView WHERE devMac = 'bb:bb:bb:bb:bb:01'")
        row = cur.fetchone()
        assert row["devIsSleeping"] == 1

    def test_sleeping_device_not_in_down_event_query(self):
        """A sleeping device must be excluded from the down-event query."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(
            cur, "BB:BB:BB:BB:BB:02",
            alert_down=1, present_last_scan=0,
            can_sleep=1, last_connection=_minutes_ago(5),
        )
        conn.commit()

        cur.execute("""
            SELECT devMac FROM DevicesView
            WHERE devAlertDown != 0
              AND devIsSleeping = 0
              AND devPresentLastScan = 0
        """)
        macs = [r["devMac"] for r in cur.fetchall()]
        # DevicesView returns LOWER(devMac)
        assert "bb:bb:bb:bb:bb:02" not in macs

    def test_expired_sleep_window_fires_down(self):
        """After the sleep window expires, the device must appear as Down."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(
            cur, "BB:BB:BB:BB:BB:03",
            alert_down=1, present_last_scan=0,
            can_sleep=1, last_connection=_minutes_ago(45),  # > 30 min
        )
        conn.commit()

        # DevicesView returns LOWER(devMac); query must use lowercase
        cur.execute("SELECT devIsSleeping FROM DevicesView WHERE devMac = 'bb:bb:bb:bb:bb:03'")
        assert cur.fetchone()["devIsSleeping"] == 0

        cur.execute("""
            SELECT devMac FROM DevicesView
            WHERE devAlertDown != 0
              AND devIsSleeping = 0
              AND devPresentLastScan = 0
        """)
        macs = [r["devMac"] for r in cur.fetchall()]
        assert "bb:bb:bb:bb:bb:03" in macs

    def test_can_sleep_zero_device_is_not_sleeping(self):
        """devCanSleep=0 device recently offline → devIsSleeping must be 0."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(
            cur, "BB:BB:BB:BB:BB:04",
            alert_down=1, present_last_scan=0,
            can_sleep=0, last_connection=_minutes_ago(5),
        )
        conn.commit()

        # DevicesView returns LOWER(devMac); query must use lowercase
        cur.execute("SELECT devIsSleeping FROM DevicesView WHERE devMac = 'bb:bb:bb:bb:bb:04'")
        assert cur.fetchone()["devIsSleeping"] == 0

    def test_devstatus_sleeping(self):
        """DevicesView devStatus must be 'Sleeping' for a sleeping device."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(
            cur, "BB:BB:BB:BB:BB:05",
            alert_down=1, present_last_scan=0,
            can_sleep=1, last_connection=_minutes_ago(5),
        )
        conn.commit()

        # DevicesView returns LOWER(devMac); query must use lowercase
        cur.execute("SELECT devStatus FROM DevicesView WHERE devMac = 'bb:bb:bb:bb:bb:05'")
        assert cur.fetchone()["devStatus"] == "Sleeping"

    def test_devstatus_down_after_window_expires(self):
        """DevicesView devStatus must be 'Down' once the sleep window expires."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(
            cur, "BB:BB:BB:BB:BB:06",
            alert_down=1, present_last_scan=0,
            can_sleep=1, last_connection=_minutes_ago(45),
        )
        conn.commit()

        # DevicesView returns LOWER(devMac); query must use lowercase
        cur.execute("SELECT devStatus FROM DevicesView WHERE devMac = 'bb:bb:bb:bb:bb:06'")
        assert cur.fetchone()["devStatus"] == "Down"
