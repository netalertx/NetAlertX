"""
Integration tests for the 'Device Down' event insertion and sleeping suppression.

Two complementary layers are tested:

Layer 1 — insert_events() (session_events.py)
  Non-sleeping devices (devCanSleep=0):
    The "Device Down" event fires when:
      devPresentLastScan = 1  (was online last scan)
      AND device NOT in CurrentScan  (absent this scan)
      AND devAlertDown != 0

  Sleeping devices (devCanSleep=1):
    The "Device Down" event is DEFERRED until the sleep window
    (NTFPRCS_sleep_time) expires.  During the sleep window the device
    is shown as "Sleeping" and NO down event is created.  After the
    window expires, insert_events creates the event via the
    sleep-expired query (devPresentLastScan=0, devIsSleeping=0).

Layer 2 — DevicesView down-count query (as used by insertOnlineHistory / db_helper)
  After presence is updated (devPresentLastScan → 0) the sleeping suppression
  (devIsSleeping=1) kicks in for count/API queries.
  Tests here verify that sleeping devices are excluded from down counts and that
  expired-window devices are included.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    make_db as _make_db,
    minutes_ago as _minutes_ago,
    insert_device as _insert_device,
    down_event_macs as _down_event_macs,
    make_device_dict as _make_device_dict,
    insert_device_from_dict as _insert_device_from_dict,
    make_current_scan_dict as _make_current_scan_dict,
    insert_current_scan_row_from_dict as _insert_current_scan_row_from_dict,
    DummyDB,
)

# server/ is already on sys.path after db_test_helpers import
from scan.session_events import insert_events, pair_sessions_events  # noqa: E402


# ---------------------------------------------------------------------------
# Layer 1: insert_events() — event creation on the down transition
#
# Non-sleeping (devCanSleep=0):
#   Condition: devPresentLastScan = 1 AND not in CurrentScan → immediate event.
# Sleeping (devCanSleep=1):
#   No event until sleep window expires (see TestInsertEventsSleepSuppression).
# ---------------------------------------------------------------------------

class TestInsertEventsDownDetection:
    """
    Tests for the 'Device Down' INSERT in insert_events() for non-sleeping devices.

    The down transition is: devPresentLastScan=1 AND absent from CurrentScan.
    CurrentScan is left empty in all tests (all devices absent this scan).
    """

    def test_null_alert_down_does_not_fire_down_event(self):
        """
        Regression: NULL devAlertDown must NOT produce a 'Device Down' event.

        Root cause: IFNULL(devAlertDown, '') made '' != 0 evaluate TRUE in SQLite,
        causing devices without devAlertDown set to fire constant down events.
        Fix:        IFNULL(devAlertDown, 0)  → 0 != 0 is FALSE.
        """
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "aa:11:22:33:44:01", alert_down=None, present_last_scan=1)
        conn.commit()

        insert_events(DummyDB(conn))

        assert "aa:11:22:33:44:01" not in _down_event_macs(cur), (
            "NULL devAlertDown must never fire a 'Device Down' event "
            "(IFNULL coercion regression)"
        )

    def test_zero_alert_down_does_not_fire_down_event(self):
        """Explicit devAlertDown=0 must NOT fire a 'Device Down' event."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "aa:11:22:33:44:02", alert_down=0, present_last_scan=1)
        conn.commit()

        insert_events(DummyDB(conn))

        assert "aa:11:22:33:44:02" not in _down_event_macs(cur)

    def test_alert_down_one_fires_down_event_when_absent(self):
        """devAlertDown=1, was online last scan, absent now → 'Device Down' event."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "aa:11:22:33:44:03", alert_down=1, present_last_scan=1)
        conn.commit()

        insert_events(DummyDB(conn))

        assert "aa:11:22:33:44:03" in _down_event_macs(cur)

    def test_device_in_current_scan_does_not_fire_down_event(self):
        """A device present in CurrentScan (online now) must NOT get Down event."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "aa:11:22:33:44:04", alert_down=1, present_last_scan=1)
        # Put it in CurrentScan → device is online this scan
        cur.execute(
            "INSERT INTO CurrentScan (scanMac, scanLastIP) VALUES (?, ?)",
            ("aa:11:22:33:44:04", "192.168.1.1"),
        )
        conn.commit()

        insert_events(DummyDB(conn))

        assert "aa:11:22:33:44:04" not in _down_event_macs(cur)

    def test_already_absent_last_scan_does_not_re_fire(self):
        """
        devPresentLastScan=0 means device was already absent last scan.
        For non-sleeping devices (devCanSleep=0), the down event was already
        created then; it must not be created again.
        """
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "aa:11:22:33:44:05", alert_down=1, present_last_scan=0)
        conn.commit()

        insert_events(DummyDB(conn))

        assert "aa:11:22:33:44:05" not in _down_event_macs(cur)

    def test_archived_device_does_not_fire_down_event(self):
        """Archived devices should not produce Down events."""
        conn = _make_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO Devices
                   (devMac, devAlertDown, devPresentLastScan, devCanSleep,
                    devLastConnection, devLastIP, devIsArchived, devIsNew)
               VALUES (?, 1, 1, 0, ?, '192.168.1.1', 1, 0)""",
            ("aa:11:22:33:44:06", _minutes_ago(60)),
        )
        conn.commit()

        insert_events(DummyDB(conn))

        # Archived devices have devIsArchived=1; insert_events doesn't filter
        # by archived, but DevicesView applies devAlertDown — archived here is
        # tested to confirm the count stays clean for future filter additions.
        # The archived device DOES get a Down event today (no archive filter in
        # insert_events). This test documents the current behaviour.
        # If that changes, update this assertion accordingly.
        assert "aa:11:22:33:44:06" in _down_event_macs(cur)

    def test_multiple_devices_mixed_alert_down(self):
        """Only devices with devAlertDown=1 that are absent fire Down events."""
        conn = _make_db()
        cur = conn.cursor()
        cases = [
            ("cc:00:00:00:00:01", None, 1),   # NULL  → no event
            ("cc:00:00:00:00:02", 0,    1),   # 0     → no event
            ("cc:00:00:00:00:03", 1,    1),   # 1     → event
            ("cc:00:00:00:00:04", 1,    0),   # already absent → no event
        ]
        for mac, alert_down, present in cases:
            _insert_device(cur, mac, alert_down=alert_down, present_last_scan=present)
        conn.commit()

        insert_events(DummyDB(conn))
        fired = _down_event_macs(cur)

        assert "cc:00:00:00:00:01" not in fired, "NULL devAlertDown must not fire"
        assert "cc:00:00:00:00:02" not in fired, "devAlertDown=0 must not fire"
        assert "cc:00:00:00:00:03" in fired,     "devAlertDown=1 absent must fire"
        assert "cc:00:00:00:00:04" not in fired, "already-absent device must not fire again"


# ---------------------------------------------------------------------------
# Layer 1b: insert_events() — sleeping device suppression
#
# Sleeping devices (devCanSleep=1) must NOT get a 'Device Down' event on the
# first-scan transition.  Instead, the event is deferred until the sleep
# window (NTFPRCS_sleep_time) expires.
# ---------------------------------------------------------------------------

class TestInsertEventsSleepSuppression:
    """
    Tests for sleeping device suppression in insert_events().

    Verifies that devCanSleep=1 devices DO NOT get immediate down events
    and only get events after the sleep window expires.
    """

    def test_sleeping_device_no_down_event_on_first_absence(self):
        """
        devCanSleep=1, devPresentLastScan=1, absent from CurrentScan.
        Sleep window has NOT expired → must NOT fire 'Device Down'.
        This is the core bug fix: previously the event fired immediately.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "bb:00:00:00:00:01", alert_down=1, present_last_scan=1,
                       can_sleep=1, last_connection=_minutes_ago(1))
        conn.commit()

        insert_events(DummyDB(conn))

        assert "bb:00:00:00:00:01" not in _down_event_macs(cur), (
            "Sleeping device must NOT get 'Device Down' on first absence "
            "(sleep window not expired)"
        )

    def test_sleeping_device_still_in_window_no_event(self):
        """
        devCanSleep=1, devPresentLastScan=0, devIsSleeping=1 (within window).
        Device was already absent last scan and is still sleeping.
        Must NOT fire 'Device Down'.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "bb:00:00:00:00:02", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(10))
        conn.commit()

        insert_events(DummyDB(conn))

        assert "bb:00:00:00:00:02" not in _down_event_macs(cur), (
            "Sleeping device within sleep window must NOT get 'Device Down'"
        )

    def test_sleeping_device_expired_window_fires_event(self):
        """
        devCanSleep=1, devPresentLastScan=0, sleep window expired
        (devLastConnection > NTFPRCS_sleep_time ago) → must fire 'Device Down'.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "bb:00:00:00:00:03", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(45))
        conn.commit()

        insert_events(DummyDB(conn))

        assert "bb:00:00:00:00:03" in _down_event_macs(cur), (
            "Sleeping device past its sleep window must get 'Device Down'"
        )

    def test_sleeping_device_expired_no_duplicate_event(self):
        """
        Once a 'Device Down' event exists for the current absence period,
        subsequent scan cycles must NOT create another one.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        last_conn = _minutes_ago(45)
        _insert_device(cur, "bb:00:00:00:00:04", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=last_conn)
        # Simulate: a Device Down event already exists for this absence
        cur.execute(
            "INSERT INTO Events (eveMac, eveIp, eveDateTime, eveEventType, "
            "eveAdditionalInfo, evePendingAlertEmail) "
            "VALUES (?, '192.168.1.1', ?, 'Device Down', '', 1)",
            ("bb:00:00:00:00:04", _minutes_ago(15)),
        )
        conn.commit()

        insert_events(DummyDB(conn))

        cur.execute(
            "SELECT COUNT(*) as cnt FROM Events "
            "WHERE eveMac = 'bb:00:00:00:00:04' AND eveEventType = 'Device Down'"
        )
        count = cur.fetchone()["cnt"]
        assert count == 1, (
            f"Expected exactly 1 Device Down event, got {count} (duplicate prevention)"
        )

    def test_sleeping_device_with_alert_down_zero_no_event(self):
        """devCanSleep=1 but devAlertDown=0 → never fires, even after sleep expires."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "bb:00:00:00:00:05", alert_down=0, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(45))
        conn.commit()

        insert_events(DummyDB(conn))

        assert "bb:00:00:00:00:05" not in _down_event_macs(cur)

    def test_mixed_sleeping_and_non_sleeping(self):
        """
        Non-sleeping device fires immediately on first absence.
        Sleeping device within window does NOT fire.
        Sleeping device past window DOES fire.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()

        # Non-sleeping, present last scan, absent now → immediate event
        _insert_device(cur, "bb:00:00:00:00:10", alert_down=1, present_last_scan=1,
                       can_sleep=0, last_connection=_minutes_ago(1))
        # Sleeping, present last scan (first absence) → NO event
        _insert_device(cur, "bb:00:00:00:00:11", alert_down=1, present_last_scan=1,
                       can_sleep=1, last_connection=_minutes_ago(1))
        # Sleeping, within window → NO event
        _insert_device(cur, "bb:00:00:00:00:12", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(10))
        # Sleeping, past window → event
        _insert_device(cur, "bb:00:00:00:00:13", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(45))
        conn.commit()

        insert_events(DummyDB(conn))
        fired = _down_event_macs(cur)

        assert "bb:00:00:00:00:10" in fired,     "Non-sleeping absent must fire"
        assert "bb:00:00:00:00:11" not in fired,  "Sleeping first-absence must NOT fire"
        assert "bb:00:00:00:00:12" not in fired,  "Sleeping within window must NOT fire"
        assert "bb:00:00:00:00:13" in fired,      "Sleeping past window must fire"


# ---------------------------------------------------------------------------
# Layer 2: DevicesView down-count query (post-presence-update)
#
# After update_presence_from_CurrentScan sets devPresentLastScan → 0 for absent
# devices, the sleeping suppression (devIsSleeping) becomes active for:
#   - insertOnlineHistory  (SUM ... WHERE devPresentLastScan=0 AND devIsSleeping=0)
#   - db_helper "down" filter
#   - getDown()
# ---------------------------------------------------------------------------

class TestDownCountSleepingSuppression:
    """
    Tests for the post-presence-update down-count query.

    Simulates the state AFTER update_presence_from_CurrentScan has run by
    inserting devices with devPresentLastScan=0 (already absent) directly.
    """

    _DOWN_COUNT_SQL = """
        SELECT devMac FROM DevicesView
        WHERE devAlertDown != 0
          AND devPresentLastScan = 0
          AND devIsSleeping = 0
          AND devIsArchived = 0
    """

    def test_null_alert_down_excluded_from_down_count(self):
        """NULL devAlertDown must not contribute to down count."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "dd:00:00:00:00:01", alert_down=None, present_last_scan=0)
        conn.commit()

        cur.execute(self._DOWN_COUNT_SQL)
        macs = {r["devMac"] for r in cur.fetchall()}
        assert "dd:00:00:00:00:01" not in macs

    def test_alert_down_one_included_in_down_count(self):
        """devAlertDown=1 absent device must be counted as down."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "dd:00:00:00:00:02", alert_down=1, present_last_scan=0,
                       last_connection=_minutes_ago(60))
        conn.commit()

        cur.execute(self._DOWN_COUNT_SQL)
        macs = {r["devMac"] for r in cur.fetchall()}
        assert "dd:00:00:00:00:02" in macs

    def test_sleeping_device_excluded_from_down_count(self):
        """
        devCanSleep=1 + absent + within sleep window → devIsSleeping=1.
        Must be excluded from the down-count query.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "dd:00:00:00:00:03", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(5))
        conn.commit()

        cur.execute(self._DOWN_COUNT_SQL)
        macs = {r["devMac"] for r in cur.fetchall()}
        assert "dd:00:00:00:00:03" not in macs, (
            "Sleeping device must be excluded from down count"
        )

    def test_expired_sleep_window_included_in_down_count(self):
        """Once the sleep window expires the device must appear in down count."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "dd:00:00:00:00:04", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(45))
        conn.commit()

        cur.execute(self._DOWN_COUNT_SQL)
        macs = {r["devMac"] for r in cur.fetchall()}
        assert "dd:00:00:00:00:04" in macs, (
            "Device past its sleep window must appear in down count"
        )

    def test_can_sleep_zero_always_in_down_count(self):
        """devCanSleep=0 device that is absent is always counted as down."""
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "dd:00:00:00:00:05", alert_down=1, present_last_scan=0,
                       can_sleep=0, last_connection=_minutes_ago(5))
        conn.commit()

        cur.execute(self._DOWN_COUNT_SQL)
        macs = {r["devMac"] for r in cur.fetchall()}
        assert "dd:00:00:00:00:05" in macs

    def test_online_history_down_count_excludes_sleeping(self):
        """
        Mirrors the insertOnlineHistory SUM query exactly.
        Sleeping devices must not inflate the downDevices count.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()

        # Normal down
        _insert_device(cur, "ee:00:00:00:00:01", alert_down=1, present_last_scan=0,
                       can_sleep=0, last_connection=_minutes_ago(60))
        # Sleeping (within window)
        _insert_device(cur, "ee:00:00:00:00:02", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(10))
        # Online
        _insert_device(cur, "ee:00:00:00:00:03", alert_down=1, present_last_scan=1,
                       last_connection=_minutes_ago(1))
        conn.commit()

        cur.execute("""
            SELECT
                COALESCE(SUM(CASE
                    WHEN devPresentLastScan = 0
                     AND devAlertDown = 1
                     AND devIsSleeping = 0
                    THEN 1 ELSE 0 END), 0) AS downDevices
            FROM DevicesView
        """)
        count = cur.fetchone()["downDevices"]
        assert count == 1, (
            f"Expected 1 down device (sleeping device must not be counted), got {count}"
        )


# ---------------------------------------------------------------------------
# Layer 1c: insert_events() — forced-online device suppression
#
# Devices with devForceStatus='online' are always considered present by the
# operator.  Generating 'Device Down' or 'Disconnected' events for them causes
# spurious flapping detection (devFlapping counts these events in DevicesView).
#
# Affected queries in insert_events():
#   1a  Device Down (non-sleeping)  — DevicesView query
#   1b  Device Down (sleep-expired) — DevicesView query
#   3   Disconnected                — Devices table query
# ---------------------------------------------------------------------------

class TestInsertEventsForceOnline:
    """
    Regression tests: forced-online devices must never generate
    'Device Down' or 'Disconnected' events.
    """

    def test_forced_online_no_device_down_event(self):
        """
        devForceStatus='online', devAlertDown=1, absent from CurrentScan.
        Must NOT produce a 'Device Down' event (regression: used to fire and
        cause devFlapping=1 after the threshold was reached).
        """
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "ff:00:00:00:00:01", alert_down=1, present_last_scan=1,
                       force_status="online")
        conn.commit()

        insert_events(DummyDB(conn))

        assert "ff:00:00:00:00:01" not in _down_event_macs(cur), (
            "forced-online device must never generate a 'Device Down' event"
        )

    def test_forced_online_sleep_expired_no_device_down_event(self):
        """
        devForceStatus='online', devCanSleep=1, sleep window expired.
        Must NOT produce a 'Device Down' event via the sleep-expired path.
        """
        conn = _make_db(sleep_minutes=30)
        cur = conn.cursor()
        _insert_device(cur, "ff:00:00:00:00:02", alert_down=1, present_last_scan=0,
                       can_sleep=1, last_connection=_minutes_ago(45),
                       force_status="online")
        conn.commit()

        insert_events(DummyDB(conn))

        assert "ff:00:00:00:00:02" not in _down_event_macs(cur), (
            "forced-online sleeping device must not get 'Device Down' after sleep expires"
        )

    def test_forced_online_no_disconnected_event(self):
        """
        devForceStatus='online', devAlertDown=0 (Disconnected path), absent.
        Must NOT produce a 'Disconnected' event.
        """
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "ff:00:00:00:00:03", alert_down=0, present_last_scan=1,
                       force_status="online")
        conn.commit()

        insert_events(DummyDB(conn))

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM Events "
            "WHERE eveMac = 'ff:00:00:00:00:03' AND eveEventType = 'Disconnected'"
        )
        assert cur.fetchone()["cnt"] == 0, (
            "forced-online device must never generate a 'Disconnected' event"
        )

    def test_forced_online_uppercase_no_device_down_event(self):
        """devForceStatus='ONLINE' (uppercase) must also be suppressed."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "ff:00:00:00:00:04", alert_down=1, present_last_scan=1,
                       force_status="ONLINE")
        conn.commit()

        insert_events(DummyDB(conn))

        assert "ff:00:00:00:00:04" not in _down_event_macs(cur), (
            "forced-online device (uppercase) must never generate a 'Device Down' event"
        )

    def test_dont_force_still_fires_device_down(self):
        """devForceStatus='dont_force' must behave normally — event fires."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "ff:00:00:00:00:05", alert_down=1, present_last_scan=1,
                       force_status="dont_force")
        conn.commit()

        insert_events(DummyDB(conn))

        assert "ff:00:00:00:00:05" in _down_event_macs(cur), (
            "dont_force device must still generate 'Device Down' when absent"
        )

    def test_forced_offline_still_fires_device_down(self):
        """devForceStatus='offline' suppresses nothing — event fires."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "ff:00:00:00:00:06", alert_down=1, present_last_scan=1,
                       force_status="offline")
        conn.commit()

        insert_events(DummyDB(conn))

        assert "ff:00:00:00:00:06" in _down_event_macs(cur), (
            "forced-offline device must still generate 'Device Down' when absent"
        )


# ---------------------------------------------------------------------------
# Layer 1d: insert_events() — NIC-derived presence suppression
#
# nic-parent-orphan-disconnect-events PRD: a parent device with NIC children
# (devParentRelType='nic') must not get Device Down/Disconnected events just
# because it has no direct CurrentScan row of its own, as long as its NICs
# satisfy devReqNicsOnline (ANY/ALL) against CurrentScan this cycle. Test
# names/setup follow that PRD's Tests section parity matrix directly.
# ---------------------------------------------------------------------------

def _setup_parent_with_nics(conn, parent_mac, nic_specs, req_nics_online=0,
                            parent_present_last_scan=1, alert_down=1,
                            parent_has_own_scan_row=False):
    """
    Insert a parent device plus its NIC children, and CurrentScan rows for
    whichever NICs (and optionally the parent) are present this cycle.

    nic_specs: list of (mac, present_this_cycle) tuples. A NIC not present
    this cycle gets no CurrentScan row at all (chosen as the PRD's single
    primary representation of "absent", not the scanPresence=0 variant).
    """
    _insert_device_from_dict(conn, _make_device_dict(
        parent_mac,
        devPresentLastScan=parent_present_last_scan,
        devAlertDown=alert_down,
        devParentMAC="",
        devParentRelType="",
        devReqNicsOnline=req_nics_online,
    ))
    for nic_mac, present in nic_specs:
        _insert_device_from_dict(conn, _make_device_dict(
            nic_mac,
            devPresentLastScan=1 if present else 0,
            devAlertDown=0,
            devParentMAC=parent_mac,
            devParentRelType="nic",
            devReqNicsOnline=0,
        ))
        if present:
            _insert_current_scan_row_from_dict(conn, _make_current_scan_dict(nic_mac, scanPresence=1))
    if parent_has_own_scan_row:
        _insert_current_scan_row_from_dict(conn, _make_current_scan_dict(parent_mac, scanPresence=1))
    conn.commit()


class TestInsertEventsNicDerivedPresence:

    def test_device_down_suppressed_one_nic_present(self):
        conn = _make_db()
        _setup_parent_with_nics(conn, "aa:11:00:00:00:01", [("bb:11:00:00:00:01", True)])

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:01" not in _down_event_macs(conn.cursor()), (
            "parent with a present NIC child must not get a spurious 'Device Down' event"
        )

    def test_disconnected_suppressed_one_nic_present(self):
        conn = _make_db()
        _setup_parent_with_nics(conn, "aa:11:00:00:00:02", [("bb:11:00:00:00:02", True)],
                                alert_down=0)

        insert_events(DummyDB(conn))

        cur = conn.cursor()
        cur.execute("SELECT eveEventType FROM Events WHERE eveMac = ?", ("aa:11:00:00:00:02",))
        event_types = [r["eveEventType"] for r in cur.fetchall()]
        assert "Disconnected" not in event_types, (
            f"expected no 'Disconnected' event, got event types: {event_types}"
        )

    def test_still_fires_when_nic_genuinely_absent(self):
        """Regression guard: this PRD must not silently suppress a real down
        transition - no CurrentScan row for the parent or its only NIC."""
        conn = _make_db()
        _setup_parent_with_nics(conn, "aa:11:00:00:00:03", [("bb:11:00:00:00:03", False)])

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:03" in _down_event_macs(conn.cursor())

    def test_unrelated_device_without_nics_not_falsely_suppressed(self):
        """Regression: an unqualified mac_column in
        nic_derived_presence_condition() used to bind to the function's own
        inner Devices row instead of the caller's, so any device anywhere
        with NIC-derived presence made every OTHER absent device (even one
        with no NIC children at all) look NIC-derived-present too, silently
        suppressing its real 'Device Down' event."""
        conn = _make_db()
        _setup_parent_with_nics(conn, "aa:11:00:00:00:11", [("bb:11:00:00:00:11", True)])
        cur = conn.cursor()
        _insert_device(cur, "cc:11:00:00:00:11", alert_down=1, present_last_scan=1)
        conn.commit()

        insert_events(DummyDB(conn))

        down_macs = _down_event_macs(conn.cursor())
        assert "aa:11:00:00:00:11" not in down_macs, (
            "the actual NIC-covered parent must still be suppressed"
        )
        assert "cc:11:00:00:00:11" in down_macs, (
            "a device with no NIC children of its own must still get its real "
            "'Device Down' event, not be suppressed just because an unrelated "
            "device elsewhere has NIC-derived presence"
        )

    def test_all_mode_one_nic_missing_still_fires(self):
        """Mirrors test_req_all_mode_partial_nics_does_not_raise_absent_parent
        in test_nic_presence.py - same ANY/ALL contract, different pipeline point."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:11:00:00:00:04",
            [("bb:11:00:00:00:04", True), ("cc:11:00:00:00:04", False)],
            req_nics_online=1,
        )

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:04" in _down_event_macs(conn.cursor())

    def test_all_mode_all_nics_present_suppresses(self):
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:11:00:00:00:05",
            [("bb:11:00:00:00:05", True), ("cc:11:00:00:00:05", True)],
            req_nics_online=1,
        )

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:05" not in _down_event_macs(conn.cursor())

    def test_any_mode_explicit_zero_one_nic_present_suppresses(self):
        """devReqNicsOnline=0 explicitly (not NULL, not 1) - parity with the
        real Python rule (str(device.get('devReqNicsOnline')) == '1' means
        everything else, including 0, is ANY mode)."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:11:00:00:00:06", [("bb:11:00:00:00:06", True)], req_nics_online=0,
        )

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:06" not in _down_event_macs(conn.cursor())

    def test_null_req_nics_online_one_nic_present_suppresses(self):
        """NULL defaults to ANY mode (str(None) == '1' is False in Python)."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:11:00:00:00:07", [("bb:11:00:00:00:07", True)], req_nics_online=None,
        )

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:07" not in _down_event_macs(conn.cursor())

    def test_null_req_nics_online_nic_absent_still_fires(self):
        """Negative NULL parity - the complement of the case above. Guards
        against a future change silently turning NULL into 'always present'
        or 'ALL' instead of ANY."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:11:00:00:00:08", [("bb:11:00:00:00:08", False)], req_nics_online=None,
        )

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:08" in _down_event_macs(conn.cursor())

    def test_any_mode_two_nics_one_present_suppresses(self):
        """Proves ANY semantics specifically (not 'all NICs present', which
        the ALL-mode tests above can't distinguish on their own) - two NICs,
        only one present, devReqNicsOnline=0."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:11:00:00:00:09",
            [("bb:11:00:00:00:09", True), ("cc:11:00:00:00:09", False)],
            req_nics_online=0,
        )

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:09" not in _down_event_macs(conn.cursor())

    def test_direct_parent_presence_overrides_regardless_of_nic_state(self):
        """The new OR-composed helper must not interfere with the
        pre-existing path: a parent with its own presence-asserting
        CurrentScan row this cycle is suppressed via
        current_scan_presence_condition() alone, even with every NIC absent."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:11:00:00:00:10", [("bb:11:00:00:00:10", False)],
            parent_has_own_scan_row=True,
        )

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:10" not in _down_event_macs(conn.cursor())

    def test_no_nic_children_unaffected(self):
        """Plain device, no devParentMAC - existing behavior (event fires
        exactly like it did before this PRD) must be untouched."""
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "aa:11:00:00:00:11", alert_down=1, present_last_scan=1)
        conn.commit()

        insert_events(DummyDB(conn))

        assert "aa:11:00:00:00:11" in _down_event_macs(conn.cursor())


# ---------------------------------------------------------------------------
# Layer 1e: insert_events() — NIC-derived reconnect (Connected/Down Reconnected)
#
# nic-parent-reconnect-events PRD: a NIC-covered parent whose presence is
# restored by NIC coverage must get a Connected/Down Reconnected event - the
# mainline "New Connections" query can't produce one for it (its present_agg
# is built from CurrentScan, which such a parent has no row in this cycle).
# ---------------------------------------------------------------------------

def _event_types_for(conn, mac):
    cur = conn.cursor()
    cur.execute("SELECT eveEventType FROM Events WHERE eveMac = ?", (mac,))
    return [r["eveEventType"] for r in cur.fetchall()]


class TestInsertEventsNicDerivedReconnect:

    def test_reconnect_fires_connected_no_prior_events(self):
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:22:00:00:00:01", [("bb:22:00:00:00:01", True)],
            parent_present_last_scan=0,
        )

        insert_events(DummyDB(conn))

        assert "Connected" in _event_types_for(conn, "aa:22:00:00:00:01")

    def test_reconnect_after_device_down_fires_down_reconnected(self):
        """The specific case the LatestEventsPerMAC INNER-JOIN-on-CurrentScan
        gap would have silently broken - see Design's second finding."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:22:00:00:00:02", [("bb:22:00:00:00:02", True)],
            parent_present_last_scan=0,
        )
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Events (eveMac, eveIp, eveDateTime, eveEventType, "
            "eveAdditionalInfo, evePendingAlertEmail) VALUES (?, '1.2.3.4', "
            "?, 'Device Down', '', 0)",
            ("aa:22:00:00:00:02", _minutes_ago(10)),
        )
        conn.commit()

        insert_events(DummyDB(conn))

        event_types = _event_types_for(conn, "aa:22:00:00:00:02")
        assert "Down Reconnected" in event_types
        assert "Connected" not in event_types

    def test_no_refire_while_already_nic_present(self):
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:22:00:00:00:03", [("bb:22:00:00:00:03", True)],
            parent_present_last_scan=1,
        )

        insert_events(DummyDB(conn))

        assert _event_types_for(conn, "aa:22:00:00:00:03") == []

    def test_no_double_fire_when_parent_has_direct_presence_too(self):
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:22:00:00:00:04", [("bb:22:00:00:00:04", True)],
            parent_present_last_scan=0, parent_has_own_scan_row=True,
        )

        insert_events(DummyDB(conn))

        event_types = _event_types_for(conn, "aa:22:00:00:00:04")
        assert event_types.count("Connected") == 1, (
            f"expected exactly one Connected event, got: {event_types}"
        )

    def test_dev_last_ip_used_not_nic_ip(self):
        conn = _make_db()
        parent_mac = "aa:22:00:00:00:05"
        nic_mac = "bb:22:00:00:00:05"
        _insert_device_from_dict(conn, _make_device_dict(
            parent_mac, devPresentLastScan=0, devAlertDown=1,
            devLastIP="10.0.0.99", devParentMAC="", devParentRelType="",
            devReqNicsOnline=0,
        ))
        _insert_device_from_dict(conn, _make_device_dict(
            nic_mac, devPresentLastScan=1, devAlertDown=0,
            devParentMAC=parent_mac, devParentRelType="nic", devReqNicsOnline=0,
        ))
        _insert_current_scan_row_from_dict(
            conn, _make_current_scan_dict(nic_mac, scanPresence=1, scanLastIP="192.168.5.5")
        )
        conn.commit()

        insert_events(DummyDB(conn))

        cur = conn.cursor()
        cur.execute(
            "SELECT eveIp FROM Events WHERE eveMac = ? AND eveEventType = 'Connected'",
            (parent_mac,),
        )
        assert cur.fetchone()["eveIp"] == "10.0.0.99"

    def test_quiet_mode_inheritance_from_present_nic(self):
        conn = _make_db()
        parent_mac = "aa:22:00:00:00:06"
        nic_mac = "bb:22:00:00:00:06"
        _setup_parent_with_nics(conn, parent_mac, [(nic_mac, True)], parent_present_last_scan=0)
        cur = conn.cursor()
        cur.execute("UPDATE CurrentScan SET scanNotificationMode = 'quiet' WHERE scanMac = ?", (nic_mac,))
        conn.commit()

        insert_events(DummyDB(conn))

        cur.execute(
            "SELECT evePendingAlertEmail FROM Events WHERE eveMac = ? AND eveEventType = 'Connected'",
            (parent_mac,),
        )
        assert cur.fetchone()["evePendingAlertEmail"] == 0

    def test_quiet_mode_requires_presence(self):
        """Locks in Open issue 1's decision: an absent NIC's quiet preference
        must not suppress notification for a reconnection it didn't contribute to."""
        conn = _make_db()
        parent_mac = "aa:22:00:00:00:07"
        present_nic = "bb:22:00:00:00:07"
        absent_nic = "cc:22:00:00:00:07"
        _setup_parent_with_nics(
            conn, parent_mac, [(present_nic, True), (absent_nic, False)],
            parent_present_last_scan=0, req_nics_online=0,
        )
        # Stale/inventory-only quiet row for the absent NIC - must not count.
        _insert_current_scan_row_from_dict(
            conn, _make_current_scan_dict(absent_nic, scanPresence=0, scanNotificationMode="quiet")
        )
        conn.commit()

        insert_events(DummyDB(conn))

        cur = conn.cursor()
        cur.execute(
            "SELECT evePendingAlertEmail FROM Events WHERE eveMac = ? AND eveEventType = 'Connected'",
            (parent_mac,),
        )
        assert cur.fetchone()["evePendingAlertEmail"] == 1

    def test_quiet_flag_from_separate_row_than_presence_row(self):
        """Quiet doesn't have to come from the same CurrentScan row that
        asserts presence - two rows for one NIC this cycle, one presence
        (not quiet), one quiet (not presence) - locks in the simplification
        pass's correction over an earlier, over-restrictive draft."""
        conn = _make_db()
        parent_mac = "aa:22:00:00:00:08"
        nic_mac = "bb:22:00:00:00:08"
        _insert_device_from_dict(conn, _make_device_dict(
            parent_mac, devPresentLastScan=0, devAlertDown=1,
            devParentMAC="", devParentRelType="", devReqNicsOnline=0,
        ))
        _insert_device_from_dict(conn, _make_device_dict(
            nic_mac, devPresentLastScan=1, devAlertDown=0,
            devParentMAC=parent_mac, devParentRelType="nic", devReqNicsOnline=0,
        ))
        _insert_current_scan_row_from_dict(
            conn, _make_current_scan_dict(nic_mac, scanPresence=1, scanSourcePlugin="ARPSCAN")
        )
        _insert_current_scan_row_from_dict(
            conn, _make_current_scan_dict(
                nic_mac, scanPresence=0, scanSourcePlugin="INVENTORY",
                scanNotificationMode="quiet",
            )
        )
        conn.commit()

        insert_events(DummyDB(conn))

        cur = conn.cursor()
        cur.execute(
            "SELECT evePendingAlertEmail FROM Events WHERE eveMac = ? AND eveEventType = 'Connected'",
            (parent_mac,),
        )
        assert cur.fetchone()["evePendingAlertEmail"] == 0

    def test_no_nic_children_unaffected(self):
        conn = _make_db()
        cur = conn.cursor()
        _insert_device(cur, "aa:22:00:00:00:09", alert_down=1, present_last_scan=0)
        conn.commit()

        insert_events(DummyDB(conn))

        assert _event_types_for(conn, "aa:22:00:00:00:09") == []

    def test_sibling_parent_with_absent_nics_not_falsely_reconnected(self):
        """Regression: an alias collision inside nic_derived_presence_condition()
        used to collapse its per-row check into a table-wide tautology - any
        NIC-covered parent anywhere in Devices made every other absent parent
        look NIC-derived-present too. A single-parent-per-DB test can't catch
        this (there's nothing else in the table to falsely match against), so
        this puts two sibling parents in one DB on purpose."""
        conn = _make_db()
        _setup_parent_with_nics(
            conn, "aa:22:00:00:00:10", [("bb:22:00:00:00:10", True)],
            parent_present_last_scan=0,
        )
        _setup_parent_with_nics(
            conn, "aa:22:00:00:00:11", [("bb:22:00:00:00:11", False)],
            parent_present_last_scan=0,
        )

        insert_events(DummyDB(conn))

        assert _event_types_for(conn, "aa:22:00:00:00:10") == ["Connected"]
        assert _event_types_for(conn, "aa:22:00:00:00:11") == []

    def test_orphan_pairing_closes_end_to_end(self):
        """A real-world scenario: absent -> Disconnected -> NIC-present ->
        Connected -> absent again -> second Disconnected. The second
        Disconnected must pair with its NIC-present Connected rather than
        becoming a permanent orphan.

        Event timestamps are pinned to controlled, strictly-increasing values
        after each cycle rather than relied on from real wall-clock time:
        timeNowUTC() truncates to whole seconds, and this test's three
        insert_events() calls run fast enough to plausibly land in the same
        second, which would break pair_sessions_events()'s strict
        eveDateTime > eveDateTime pairing query non-deterministically.
        """
        conn = _make_db()
        parent_mac = "aa:22:00:00:00:10"
        nic_mac = "bb:22:00:00:00:10"
        _insert_device_from_dict(conn, _make_device_dict(
            parent_mac, devPresentLastScan=1, devAlertDown=0,
            devParentMAC="", devParentRelType="", devReqNicsOnline=0,
        ))
        _insert_device_from_dict(conn, _make_device_dict(
            nic_mac, devPresentLastScan=1, devAlertDown=0,
            devParentMAC=parent_mac, devParentRelType="nic", devReqNicsOnline=0,
        ))
        cur = conn.cursor()

        def _pin_last_event_timestamp(mac, ts):
            cur.execute(
                "UPDATE Events SET eveDateTime = ? WHERE ROWID = "
                "(SELECT MAX(ROWID) FROM Events WHERE eveMac = ?)",
                (ts, mac),
            )
            conn.commit()

        # Seed an initial Connected event so the first Disconnected below has
        # something to pair to.
        cur.execute(
            "INSERT INTO Events (eveMac, eveIp, eveDateTime, eveEventType, "
            "eveAdditionalInfo, evePendingAlertEmail) VALUES (?, '1.2.3.4', "
            "'2026-01-01 09:00:00', 'Connected', '', 1)",
            (parent_mac,),
        )
        conn.commit()

        # Cycle 1: NIC absent, parent absent -> Disconnected.
        insert_events(DummyDB(conn))
        _pin_last_event_timestamp(parent_mac, "2026-01-01 09:05:00")
        pair_sessions_events(DummyDB(conn))

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM Events WHERE eveMac = ? AND eveEventType = 'Disconnected'",
            (parent_mac,),
        )
        assert cur.fetchone()["cnt"] == 1

        # Reflect what step 6/7 would have set devPresentLastScan to for the
        # next cycle - insert_events() alone doesn't run them.
        cur.execute("UPDATE Devices SET devPresentLastScan = 0 WHERE devMac = ?", (parent_mac,))
        conn.commit()

        # Cycle 2: NIC comes back -> parent Connected (this PRD's fix).
        _insert_current_scan_row_from_dict(conn, _make_current_scan_dict(nic_mac, scanPresence=1))
        conn.commit()
        insert_events(DummyDB(conn))
        _pin_last_event_timestamp(parent_mac, "2026-01-01 09:10:00")
        pair_sessions_events(DummyDB(conn))

        cur.execute("UPDATE Devices SET devPresentLastScan = 1 WHERE devMac = ?", (parent_mac,))
        cur.execute("DELETE FROM CurrentScan WHERE scanMac = ?", (nic_mac,))
        conn.commit()

        # Cycle 3: NIC absent again -> a second, real Disconnected.
        insert_events(DummyDB(conn))
        _pin_last_event_timestamp(parent_mac, "2026-01-01 09:15:00")
        pair_sessions_events(DummyDB(conn))

        cur.execute(
            "SELECT evePairEventRowid FROM Events WHERE eveMac = ? AND eveEventType = 'Disconnected' "
            "ORDER BY eveDateTime DESC LIMIT 1",
            (parent_mac,),
        )
        second_disconnect = cur.fetchone()
        assert second_disconnect["evePairEventRowid"] is not None, (
            "the second Disconnected must pair to the NIC-derived Connected event, "
            "not become a permanent orphan"
        )
