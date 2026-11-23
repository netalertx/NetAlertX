"""
Regression coverage: print_scan_stats() (device_handling.py)
undercounted "down_alerts"/"new_down_alerts" whenever a device's stored MAC and its
CurrentScan MAC differed only by case.

DevicesView exposes devMac as LOWER(IFNULL(devMac, '')) - a function-derived VIEW
column, not a bare table column. print_scan_stats()'s down-alert subqueries compared
it against CurrentScan.scanMac as `devMac = scanMac` (DevicesView column on the LEFT),
which - unlike a bare COLLATE NOCASE column comparison - loses NOCASE collation and
becomes a case-sensitive byte comparison. Reversing the operand order to
`scanMac = devMac` restores NOCASE collation (SQLite gives precedence to the left
operand's column collation; scanMac is a real COLLATE-free CurrentScan column but the
comparison still resolves via devMac's declared NOCASE affinity once devMac is on the
right, verified empirically against a real SQLite instance built from the actual
DevicesView definition - see server/scan/device_handling.py print_scan_stats()).

This function is diagnostic/verbose-log-only (mylog("verbose"/"trace", ...), no other
consumer) - it does not drive real "Device Down" notifications, which go through
session_events.insert_events() -> presence.current_scan_presence_condition() instead
and were already safe (scanMac on the left there). This test covers the diagnostic
counter only.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    DummyDB,
    make_device_dict,
    insert_device_from_dict,
    make_current_scan_dict,
    insert_current_scan_row_from_dict,
)

import scan.device_handling as device_handling  # noqa: E402
from scan.device_handling import print_scan_stats  # noqa: E402


def _run_stats(conn, monkeypatch):
    """Call print_scan_stats() and return the logged down_alerts/new_down_alerts
    counts, parsed straight out of its own mylog("verbose", ...) calls - this
    exercises the real function/query rather than a re-derived copy of it."""
    logged = {}

    def fake_mylog(level, parts):
        """Stand in for logger.mylog: parse the down_alerts/new_down_alerts
        counts straight out of print_scan_stats()'s own log lines."""
        text = "".join(parts) if isinstance(parts, list) else str(parts)
        if "Down Alerts" in text and "New Down Alerts" not in text:
            logged["down_alerts"] = int(text.rsplit(":", 1)[1].strip())
        elif "New Down Alerts" in text:
            logged["new_down_alerts"] = int(text.rsplit(":", 1)[1].strip())

    monkeypatch.setattr(device_handling, "mylog", fake_mylog)

    db = DummyDB(conn)
    print_scan_stats(db)
    return logged


class TestScanStatsMacCase:
    def test_matching_mac_different_case_is_not_a_false_down_alert(self, scan_db, monkeypatch):
        """Device stored lowercase, present this cycle under an uppercase MAC
        (e.g. a plugin like FREEBOX reporting uppercase) must not be counted
        as down."""
        device = make_device_dict(
            mac="54:ef:44:9a:b6:7f",
            devAlertDown=1,
            devCanSleep=0,
            devPresentLastScan=1,
        )
        insert_device_from_dict(scan_db, device)

        current_scan = make_current_scan_dict(mac="54:EF:44:9A:B6:7F")
        insert_current_scan_row_from_dict(scan_db, current_scan)

        stats = _run_stats(scan_db, monkeypatch)

        assert stats["down_alerts"] == 0
        assert stats["new_down_alerts"] == 0

    def test_truly_absent_device_is_still_counted_as_down(self, scan_db, monkeypatch):
        """Sanity check: a device genuinely missing from CurrentScan this
        cycle must still be counted - the fix must not mask real down alerts.

        An unrelated CurrentScan row is seeded too: print_scan_stats() GROUPs
        BY scanSourcePlugin, so an empty CurrentScan produces zero result rows
        and print_scan_stats() falls back to its hardcoded all-zero stub - that
        would make this assertion pass for the wrong reason."""
        device = make_device_dict(
            mac="54:ef:44:9a:b6:7f",
            devAlertDown=1,
            devCanSleep=0,
            devPresentLastScan=1,
        )
        insert_device_from_dict(scan_db, device)

        other_scan = make_current_scan_dict(mac="11:22:33:44:55:66")
        insert_current_scan_row_from_dict(scan_db, other_scan)

        stats = _run_stats(scan_db, monkeypatch)

        assert stats["down_alerts"] == 1
        assert stats["new_down_alerts"] == 1
