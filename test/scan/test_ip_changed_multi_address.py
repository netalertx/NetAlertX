"""
Tests for insert_events()'s IP Changed query (server/scan/session_events.py)
with a device that has more than one simultaneously-present, already-known
address in one address family.

Today's query reduces every scanPresence=1 CurrentScan row for a MAC to a
single MIN(scanLastIP) candidate, then tests that one value against
devPrimaryIPv4/devPrimaryIPv6/devLastIP. A MAC with two simultaneously-valid,
already-known addresses can have MIN() select the one not currently sitting
in the single-valued devPrimaryIPv6 slot, failing all three comparisons
despite not being new.

The fix makes the "known" test additive (three-slot check OR an address
already seen, and not missing-in-last-scan, by an eligible plugin for this
MAC's "ip" field) and evaluates every distinct present address individually
instead of via one MIN()-reduced stand-in value.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    make_db,
    insert_device,
    make_current_scan_dict,
    insert_current_scan_row_from_dict,
    seed_plugin_object,
    CREATE_PLUGINS_OBJECTS,
    DummyDB,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
from scan.session_events import insert_events  # noqa: E402

MAC = "aa:bb:cc:dd:ee:01"


def _ip_eligible_plugin(prefix="FREEBOX", column="objectSecondaryId"):
    """A plugin config participating in the 'ip' field view - objectPrimaryId
    maps to scanMac and the given column role maps to scanLastIP, matching
    get_plugin_columns_for_field()'s two requirements."""
    return {
        "unique_prefix": prefix,
        "mapped_to_table": "CurrentScan",
        "database_column_definitions": [
            {"column": "objectPrimaryId", "mapped_to_column": "scanMac"},
            {"column": column, "mapped_to_column": "scanLastIP"},
        ],
    }


def _gap_plugin(prefix="dockerdisc"):
    """A plugin config that structurally cannot participate in the 'ip' field
    view - objectPrimaryId maps to scanParentMAC, not scanMac - mirroring
    dockerdisc's real shape."""
    return {
        "unique_prefix": prefix,
        "mapped_to_table": "CurrentScan",
        "database_column_definitions": [
            {"column": "objectPrimaryId", "mapped_to_column": "scanParentMAC"},
        ],
    }


def _make_db_with_plugins_objects():
    """make_db() plus the Plugins_Objects table - needed here but not by the
    other scan tests, so built locally rather than folding into make_db()."""
    conn = make_db()
    conn.executescript(CREATE_PLUGINS_OBJECTS)
    conn.commit()
    return conn


class TestMultiAddressFalsePositiveFixed:
    """Reproduces netalertx/NetAlertX#1831's captured log, then confirms the fix."""

    def test_known_second_address_does_not_fire(self):
        conn = _make_db_with_plugins_objects()
        cur = conn.cursor()
        insert_device(cur, MAC, alert_down=1, present_last_scan=1, last_ip="IPv6-4")
        cur.execute("UPDATE Devices SET devPrimaryIPv6 = 'IPv6-4' WHERE devMac = ?", (MAC,))
        conn.commit()

        # Two simultaneously-present rows for the same MAC - IPv6-4 (the
        # known devPrimaryIPv6) and IPv6-2 (also known, via Plugins_Objects,
        # but not sitting in any of the three slots).
        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="IPv6-4"))
        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="IPv6-2"))

        seed_plugin_object(
            cur, "FREEBOX", MAC, secondary_id="IPv6-2", status="watched-not-changed",
        )
        conn.commit()

        db = DummyDB(conn)
        insert_events(db, all_plugins=[_ip_eligible_plugin()])

        rows = conn.execute(
            "SELECT * FROM Events WHERE eveMac = ? AND eveEventType = 'IP Changed'", (MAC,)
        ).fetchall()
        assert rows == [], "IPv6-2 is known via Plugins_Objects - must not fire IP Changed"


class TestGenuineCrossFamilyChangeNotSuppressed:
    """The additive/per-address design must not trade the false positive above
    for a false negative: a genuinely new address in one family must still
    fire even when another family's already-known address is present too."""

    def test_new_ipv4_fires_alongside_known_ipv6(self):
        conn = _make_db_with_plugins_objects()
        cur = conn.cursor()
        insert_device(cur, MAC, alert_down=1, present_last_scan=1, last_ip="192.168.1.10")
        cur.execute("UPDATE Devices SET devPrimaryIPv4 = '192.168.1.10', "
                    "devPrimaryIPv6 = 'IPv6-known' WHERE devMac = ?", (MAC,))
        conn.commit()

        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="IPv6-known"))
        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="10.0.0.99"))
        conn.commit()

        db = DummyDB(conn)
        insert_events(db, all_plugins=[_ip_eligible_plugin()])

        rows = conn.execute(
            "SELECT eveIp, eveAdditionalInfo FROM Events WHERE eveMac = ? AND eveEventType = 'IP Changed'",
            (MAC,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["eveIp"] == "10.0.0.99"
        assert "10.0.0.99" in rows[0]["eveAdditionalInfo"]
        assert "IPv6-known" not in rows[0]["eveAdditionalInfo"]


class TestGapPluginDeviceUnaffected:
    """A device whose only contributing plugin can't participate in the 'ip'
    field view (dockerdisc's real shape) must see exactly today's three-slot
    behavior - the additive set is empty and must be a true no-op."""

    def test_real_change_still_fires(self):
        conn = _make_db_with_plugins_objects()
        cur = conn.cursor()
        insert_device(cur, MAC, alert_down=1, present_last_scan=1, last_ip="192.168.1.10")
        cur.execute("UPDATE Devices SET devPrimaryIPv4 = '192.168.1.10' WHERE devMac = ?", (MAC,))
        conn.commit()
        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="192.168.1.77"))
        conn.commit()

        db = DummyDB(conn)
        insert_events(db, all_plugins=[_gap_plugin()])

        rows = conn.execute(
            "SELECT eveIp FROM Events WHERE eveMac = ? AND eveEventType = 'IP Changed'", (MAC,)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["eveIp"] == "192.168.1.77"

    def test_non_change_still_suppressed(self):
        conn = _make_db_with_plugins_objects()
        cur = conn.cursor()
        insert_device(cur, MAC, alert_down=1, present_last_scan=1, last_ip="192.168.1.10")
        cur.execute("UPDATE Devices SET devPrimaryIPv4 = '192.168.1.10' WHERE devMac = ?", (MAC,))
        conn.commit()
        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="192.168.1.10"))
        conn.commit()

        db = DummyDB(conn)
        insert_events(db, all_plugins=[_gap_plugin()])

        rows = conn.execute(
            "SELECT * FROM Events WHERE eveMac = ? AND eveEventType = 'IP Changed'", (MAC,)
        ).fetchall()
        assert rows == []

    def test_no_all_plugins_argument_is_equivalent(self):
        """Omitting all_plugins entirely (the pre-fix call shape) must behave
        identically - callers that haven't been updated yet see no change."""
        conn = _make_db_with_plugins_objects()
        cur = conn.cursor()
        insert_device(cur, MAC, alert_down=1, present_last_scan=1, last_ip="192.168.1.10")
        cur.execute("UPDATE Devices SET devPrimaryIPv4 = '192.168.1.10' WHERE devMac = ?", (MAC,))
        conn.commit()
        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="192.168.1.77"))
        conn.commit()

        db = DummyDB(conn)
        insert_events(db)

        rows = conn.execute(
            "SELECT eveIp FROM Events WHERE eveMac = ? AND eveEventType = 'IP Changed'", (MAC,)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["eveIp"] == "192.168.1.77"


class TestEventAggregation:
    """Multiple genuinely-new addresses in one cycle must still produce
    exactly one Events row, listing every new address in eveAdditionalInfo -
    today's one-row-per-MAC-per-cycle shape, not multiplied volume."""

    def test_two_new_addresses_one_cycle_one_row(self):
        conn = _make_db_with_plugins_objects()
        cur = conn.cursor()
        insert_device(cur, MAC, alert_down=1, present_last_scan=1, last_ip="192.168.1.10")
        cur.execute("UPDATE Devices SET devPrimaryIPv4 = '192.168.1.10', "
                    "devPrimaryIPv6 = '' WHERE devMac = ?", (MAC,))
        conn.commit()

        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="10.0.0.50"))
        insert_current_scan_row_from_dict(conn, make_current_scan_dict(MAC, scanLastIP="IPv6-new"))
        conn.commit()

        db = DummyDB(conn)
        insert_events(db, all_plugins=[_ip_eligible_plugin()])

        rows = conn.execute(
            "SELECT eveAdditionalInfo FROM Events WHERE eveMac = ? AND eveEventType = 'IP Changed'",
            (MAC,),
        ).fetchall()
        assert len(rows) == 1
        info = rows[0]["eveAdditionalInfo"]
        assert "10.0.0.50" in info
        assert "IPv6-new" in info
