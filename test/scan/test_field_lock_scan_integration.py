"""
Integration tests for device field locking during actual scan updates.

Simulates real-world scenarios by:
1. Setting up Devices table with various source values
2. Populating CurrentScan with new discovery data
3. Running actual device_handling scan updates
4. Verifying field updates respect authorization rules

Tests all combinations of field sources (LOCKED, USER, NEWDEV, plugin name)
with realistic scan data.
"""

import sqlite3
from unittest.mock import Mock, patch

import pytest

from server.scan import device_handling


@pytest.fixture
def mock_device_handlers():
    """Mock device_handling helper functions."""
    with patch.multiple(
        device_handling,
        update_devPresentLastScan_based_on_nics=Mock(return_value=0),
        update_devPresentLastScan_based_on_force_status=Mock(return_value=0),
        query_MAC_vendor=Mock(return_value=-1),
        guess_icon=Mock(return_value="icon"),
        guess_type=Mock(return_value="type"),
        get_setting_value=Mock(
            side_effect=lambda key: {
                "NEWDEV_replace_preset_icon": 0,
                "NEWDEV_devIcon": "icon",
                "NEWDEV_devType": "type",
            }.get(key, "")
        ),
    ):
        yield


@pytest.fixture
def scan_db_for_new_devices():
    """Create an in-memory SQLite database for create_new_devices tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE Devices (
            devMac TEXT PRIMARY KEY,
            devName TEXT,
            devVendor TEXT,
            devLastIP TEXT,
            devPrimaryIPv4 TEXT,
            devPrimaryIPv6 TEXT,
            devFirstConnection TEXT,
            devLastConnection TEXT,
            devSyncHubNode TEXT,
            devGUID TEXT,
            devParentMAC TEXT,
            devParentPort TEXT,
            devSite TEXT,
            devSSID TEXT,
            devType TEXT,
            devSourcePlugin TEXT,
            devMacSource TEXT,
            devNameSource TEXT,
            devFQDNSource TEXT,
            devLastIPSource TEXT,
            devVendorSource TEXT,
            devSSIDSource TEXT,
            devParentMACSource TEXT,
            devParentPortSource TEXT,
            devParentRelTypeSource TEXT,
            devVlanSource TEXT,
            devAlertEvents INTEGER,
            devAlertDown INTEGER,
            devPresentLastScan INTEGER,
            devIsArchived INTEGER,
            devIsNew INTEGER,
            devSkipRepeated INTEGER,
            devScan INTEGER,
            devOwner TEXT,
            devFavorite INTEGER,
            devGroup TEXT,
            devComments TEXT,
            devLogEvents INTEGER,
            devLocation TEXT,
            devCustomProps TEXT,
            devParentRelType TEXT,
            devReqNicsOnline INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE CurrentScan (
            scanMac TEXT,
            scanName TEXT,
            scanVendor TEXT,
            scanSourcePlugin TEXT,
            scanLastIP TEXT,
            scanSyncHubNode TEXT,
            scanParentMAC TEXT,
            scanParentPort TEXT,
            scanSite TEXT,
            scanSSID TEXT,
            scanType TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE Events (
            eve_MAC TEXT,
            eve_IP TEXT,
            eve_DateTime TEXT,
            eve_EventType TEXT,
            eve_AdditionalInfo TEXT,
            eve_PendingAlertEmail INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE Sessions (
            ses_MAC TEXT,
            ses_IP TEXT,
            ses_EventTypeConnection TEXT,
            ses_DateTimeConnection TEXT,
            ses_EventTypeDisconnection TEXT,
            ses_DateTimeDisconnection TEXT,
            ses_StillConnected INTEGER,
            ses_AdditionalInfo TEXT
        )
        """
    )

    conn.commit()
    yield conn
    conn.close()


def test_create_new_devices_sets_sources(scan_db_for_new_devices):
    """New device insert initializes source fields from scan method."""
    cur = scan_db_for_new_devices.cursor()
    cur.execute(
        """
        INSERT INTO CurrentScan (
            scanMac, scanName, scanVendor, scanSourcePlugin, scanLastIP,
            scanSyncHubNode, scanParentMAC, scanParentPort,
            scanSite, scanSSID, scanType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:10",
            "DeviceOne",
            "AcmeVendor",
            "ARPSCAN",
            "192.168.1.10",
            "",
            "11:22:33:44:55:66",
            "1",
            "",
            "MyWifi",
            "",
        ),
    )
    scan_db_for_new_devices.commit()

    settings = {
        "NEWDEV_devType": "default-type",
        "NEWDEV_devParentMAC": "ff:ff:ff:ff:ff:ff",
        "NEWDEV_devOwner": "owner",
        "NEWDEV_devGroup": "group",
        "NEWDEV_devComments": "",
        "NEWDEV_devLocation": "",
        "NEWDEV_devCustomProps": "",
        "NEWDEV_devParentRelType": "uplink",
        "SYNC_node_name": "SYNCNODE",
    }

    def get_setting_value_side_effect(key):
        return settings.get(key, "")

    db = Mock()
    db.sql_connection = scan_db_for_new_devices
    db.sql = cur
    db.commitDB = scan_db_for_new_devices.commit

    with patch.multiple(
        device_handling,
        get_setting_value=Mock(side_effect=get_setting_value_side_effect),
        safe_int=Mock(return_value=0),
    ):
        device_handling.create_new_devices(db)

    row = cur.execute(
        """
        SELECT
            devMacSource,
            devNameSource,
            devVendorSource,
            devLastIPSource,
            devSSIDSource,
            devParentMACSource,
            devParentPortSource,
            devParentRelTypeSource,
            devFQDNSource,
            devVlanSource
        FROM Devices WHERE devMac = ?
        """,
        ("aa:bb:cc:dd:ee:10",),
    ).fetchone()

    assert row["devMacSource"] == "ARPSCAN"
    assert row["devNameSource"] == "ARPSCAN"
    assert row["devVendorSource"] == "ARPSCAN"
    assert row["devLastIPSource"] == "ARPSCAN"
    assert row["devSSIDSource"] == "ARPSCAN"
    assert row["devParentMACSource"] == "ARPSCAN"
    assert row["devParentPortSource"] == "ARPSCAN"
    assert row["devParentRelTypeSource"] == "NEWDEV"
    assert row["devFQDNSource"] == "NEWDEV"
    assert row["devVlanSource"] == "NEWDEV"


def test_scan_updates_newdev_device_name(scan_db, mock_device_handlers):
    """Scanner discovers name for device with NEWDEV source."""
    cur = scan_db.cursor()

    # Device with empty name (NEWDEV)
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
            devType, devIcon, devParentPort, devParentMAC, devSite, devSSID
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:01",
            "2025-01-01 00:00:00",
            0,
            "192.168.1.1",
            "",  # No name yet
            "NEWDEV",  # Default/unset
            "TestVendor",
            "NEWDEV",
            "ARPSCAN",
            "type",
            "icon",
            "",
            "",
            "",
            "",
        ),
    )

    # Scanner discovers name
    cur.execute(
        """
        INSERT INTO CurrentScan (
            scanMac, scanLastIP, scanVendor, scanSourcePlugin, scanName,
            scanLastQuery, scanLastConnection, scanSyncHubNode,
            scanSite, scanSSID, scanParentMAC, scanParentPort, scanType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:01",
            "192.168.1.1",
            "TestVendor",
            "NBTSCAN",
            "DiscoveredDevice",
            "",
            "2025-01-01 01:00:00",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
    )
    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)

    row = cur.execute(
        "SELECT devName FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:01",),
    ).fetchone()

    # Name SHOULD be updated from NEWDEV
    assert row["devName"] == "DiscoveredDevice", "Name should be updated from empty"


def test_scan_does_not_update_user_field_name(scan_db, mock_device_handlers):
    """Scanner cannot override devName when source is USER."""
    cur = scan_db.cursor()

    # Device with USER-edited name
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
            devType, devIcon, devParentPort, devParentMAC, devSite, devSSID
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:02",
            "2025-01-01 00:00:00",
            0,
            "192.168.1.2",
            "My Custom Device",
            "USER",  # User-owned
            "TestVendor",
            "NEWDEV",
            "ARPSCAN",
            "type",
            "icon",
            "",
            "",
            "",
            "",
        ),
    )

    # Scanner tries to update name
    cur.execute(
        """
        INSERT INTO CurrentScan (
            scanMac, scanLastIP, scanVendor, scanSourcePlugin, scanName,
            scanLastQuery, scanLastConnection, scanSyncHubNode,
            scanSite, scanSSID, scanParentMAC, scanParentPort, scanType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:02",
            "192.168.1.2",
            "TestVendor",
            "NBTSCAN",
            "ScannedDevice",
            "",
            "2025-01-01 01:00:00",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
    )
    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)

    row = cur.execute(
        "SELECT devName FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:02",),
    ).fetchone()

    # Name should NOT be updated because it's USER-owned
    assert row["devName"] == "My Custom Device", "USER name should not be changed by scan"


def test_scan_does_not_update_locked_field(scan_db, mock_device_handlers):
    """Scanner cannot override LOCKED devName."""
    cur = scan_db.cursor()

    # Device with LOCKED name
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
            devType, devIcon, devParentPort, devParentMAC, devSite, devSSID
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:03",
            "2025-01-01 00:00:00",
            0,
            "192.168.1.3",
            "Important Device",
            "LOCKED",  # Locked
            "TestVendor",
            "NEWDEV",
            "ARPSCAN",
            "type",
            "icon",
            "",
            "",
            "",
            "",
        ),
    )

    # Scanner tries to update name
    cur.execute(
        """
        INSERT INTO CurrentScan (
            scanMac, scanLastIP, scanVendor, scanSourcePlugin, scanName,
            scanLastQuery, scanLastConnection, scanSyncHubNode,
            scanSite, scanSSID, scanParentMAC, scanParentPort, scanType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:03",
            "192.168.1.3",
            "TestVendor",
            "NBTSCAN",
            "Unknown",
            "",
            "2025-01-01 01:00:00",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
    )
    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)

    row = cur.execute(
        "SELECT devName FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:03",),
    ).fetchone()

    # Name should NOT be updated because it's LOCKED
    assert row["devName"] == "Important Device", "LOCKED name should not be changed"


def test_scan_updates_empty_vendor_field(scan_db, mock_device_handlers):
    """Scan updates vendor when it's empty/NULL."""
    cur = scan_db.cursor()

    # Device with empty vendor
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
            devType, devIcon, devParentPort, devParentMAC, devSite, devSSID
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:04",
            "2025-01-01 00:00:00",
            0,
            "192.168.1.4",
            "Device",
            "NEWDEV",
            "",  # Empty vendor
            "NEWDEV",
            "ARPSCAN",
            "type",
            "icon",
            "",
            "",
            "",
            "",
        ),
    )

    # Scan discovers vendor
    cur.execute(
        """
        INSERT INTO CurrentScan (
            scanMac, scanLastIP, scanVendor, scanSourcePlugin, scanName,
            scanLastQuery, scanLastConnection, scanSyncHubNode,
            scanSite, scanSSID, scanParentMAC, scanParentPort, scanType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:04",
            "192.168.1.4",
            "Apple Inc.",
            "ARPSCAN",
            "",
            "",
            "2025-01-01 01:00:00",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
    )
    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)

    row = cur.execute(
        "SELECT devVendor FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:04",),
    ).fetchone()

    # Vendor SHOULD be updated
    assert row["devVendor"] == "Apple Inc.", "Empty vendor should be populated from scan"


def test_scan_updates_ip_addresses(scan_db, mock_device_handlers):
    """Scan updates IPv4 and IPv6 addresses correctly."""
    cur = scan_db.cursor()

    # Device with empty IPs
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
            devType, devIcon, devParentPort, devParentMAC, devSite, devSSID,
            devPrimaryIPv4, devPrimaryIPv6
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:05",
            "2025-01-01 00:00:00",
            0,
            "",
            "Device",
            "NEWDEV",
            "Vendor",
            "NEWDEV",
            "NEWDEV",
            "type",
            "icon",
            "",
            "",
            "",
            "",
            "",  # No IPv4
            "",  # No IPv6
        ),
    )

    # Scan discovers IPv4
    cur.execute(
        """
        INSERT INTO CurrentScan (
            scanMac, scanLastIP, scanVendor, scanSourcePlugin, scanName,
            scanLastQuery, scanLastConnection, scanSyncHubNode,
            scanSite, scanSSID, scanParentMAC, scanParentPort, scanType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:05",
            "192.168.1.100",
            "Vendor",
            "ARPSCAN",
            "",
            "",
            "2025-01-01 01:00:00",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
    )
    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)
    device_handling.update_ipv4_ipv6(db)

    row = cur.execute(
        "SELECT devLastIP, devPrimaryIPv4, devPrimaryIPv6 FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:05",),
    ).fetchone()

    # IPv4 should be set
    assert row["devLastIP"] == "192.168.1.100", "Last IP should be updated"
    assert row["devPrimaryIPv4"] == "192.168.1.100", "Primary IPv4 should be set"
    assert row["devPrimaryIPv6"] == "", "IPv6 should remain empty"


def test_scan_updates_ipv6_without_changing_ipv4(scan_db, mock_device_handlers):
    """Scan updates IPv6 without overwriting IPv4."""
    cur = scan_db.cursor()

    # Device with IPv4 already set
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
            devType, devIcon, devParentPort, devParentMAC, devSite, devSSID,
            devPrimaryIPv4, devPrimaryIPv6
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:06",
            "2025-01-01 00:00:00",
            0,
            "192.168.1.101",
            "Device",
            "NEWDEV",
            "Vendor",
            "NEWDEV",
            "NEWDEV",
            "type",
            "icon",
            "",
            "",
            "",
            "",
            "192.168.1.101",  # IPv4 already set
            "",  # No IPv6
        ),
    )

    # Scan discovers IPv6
    cur.execute(
        """
        INSERT INTO CurrentScan (
            scanMac, scanLastIP, scanVendor, scanSourcePlugin, scanName,
            scanLastQuery, scanLastConnection, scanSyncHubNode,
            scanSite, scanSSID, scanParentMAC, scanParentPort, scanType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:06",
            "fe80::1",
            "Vendor",
            "ARPSCAN",
            "",
            "",
            "2025-01-01 01:00:00",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
    )
    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)
    device_handling.update_ipv4_ipv6(db)

    row = cur.execute(
        "SELECT devPrimaryIPv4, devPrimaryIPv6 FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:06",),
    ).fetchone()

    # IPv4 should remain, IPv6 should be set
    assert row["devPrimaryIPv4"] == "192.168.1.101", "IPv4 should not change"
    assert row["devPrimaryIPv6"] == "fe80::1", "IPv6 should be set"


def test_scan_updates_presence_status(scan_db, mock_device_handlers):
    """Scan correctly updates devPresentLastScan status."""
    cur = scan_db.cursor()

    # Device not in current scan (offline)
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
            devType, devIcon, devParentPort, devParentMAC, devSite, devSSID
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "aa:bb:cc:dd:ee:07",
            "2025-01-01 00:00:00",
            1,  # Was online
            "192.168.1.102",
            "Device",
            "NEWDEV",
            "Vendor",
            "NEWDEV",
            "ARPSCAN",
            "type",
            "icon",
            "",
            "",
            "",
            "",
        ),
    )

    # Note: No CurrentScan entry for this MAC - device is offline
    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)
    device_handling.update_presence_from_CurrentScan(db)

    row = cur.execute(
        "SELECT devPresentLastScan FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:07",),
    ).fetchone()

    # Device should be marked as offline
    assert row["devPresentLastScan"] == 0, "Offline device should have devPresentLastScan = 0"


def test_scan_multiple_devices_mixed_sources(scan_db, mock_device_handlers):
    """Scan with multiple devices having different source combinations."""
    cur = scan_db.cursor()

    devices_data = [
        # (MAC, Name, NameSource, Vendor, VendorSource)
        ("aa:bb:cc:dd:ee:11", "Device1", "NEWDEV", "", "NEWDEV"),  # Both updatable
        ("aa:bb:cc:dd:ee:12", "My Device", "USER", "OldVendor", "NEWDEV"),  # Name protected
        ("aa:bb:cc:dd:ee:13", "Locked Device", "LOCKED", "", "NEWDEV"),  # Name locked
        ("aa:bb:cc:dd:ee:14", "Device4", "ARPSCAN", "", "NEWDEV"),  # Name from plugin
    ]

    for mac, name, name_src, vendor, vendor_src in devices_data:
        cur.execute(
            """
            INSERT INTO Devices (
                devMac, devLastConnection, devPresentLastScan, devLastIP,
                devName, devNameSource, devVendor, devVendorSource, devLastIPSource,
                devType, devIcon, devParentPort, devParentMAC, devSite, devSSID
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mac,
                "2025-01-01 00:00:00",
                0,
                "192.168.1.1",
                name,
                name_src,
                vendor,
                vendor_src,
                "ARPSCAN",
                "type",
                "icon",
                "",
                "",
                "",
                "",
            ),
        )

    # Scan discovers all devices with new data
    scan_entries = [
        ("aa:bb:cc:dd:ee:11", "192.168.1.1", "Apple Inc.", "ScanPlugin", "ScannedDevice1"),
        ("aa:bb:cc:dd:ee:12", "192.168.1.2", "Samsung", "ScanPlugin", "ScannedDevice2"),
        ("aa:bb:cc:dd:ee:13", "192.168.1.3", "Sony", "ScanPlugin", "ScannedDevice3"),
        ("aa:bb:cc:dd:ee:14", "192.168.1.4", "LG", "ScanPlugin", "ScannedDevice4"),
    ]

    for mac, ip, vendor, scan_method, name in scan_entries:
        cur.execute(
            """
            INSERT INTO CurrentScan (
                scanMac, scanLastIP, scanVendor, scanSourcePlugin, scanName,
                scanLastQuery, scanLastConnection, scanSyncHubNode,
                scanSite, scanSSID, scanParentMAC, scanParentPort, scanType
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (mac, ip, vendor, scan_method, name, "", "2025-01-01 01:00:00", "", "", "", "", "", ""),
        )

    scan_db.commit()

    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur

    # Run scan update
    device_handling.update_devices_data_from_scan(db)

    # Check results
    results = {
        "aa:bb:cc:dd:ee:11": {"name": "Device1", "vendor": "Apple Inc."},  # Name already set, won't update
        "aa:bb:cc:dd:ee:12": {"name": "My Device", "vendor": "Samsung"},  # Name protected (USER)
        "aa:bb:cc:dd:ee:13": {"name": "Locked Device", "vendor": "Sony"},  # Name locked
        "aa:bb:cc:dd:ee:14": {"name": "Device4", "vendor": "LG"},  # Name already from plugin, won't update
    }

    for mac, expected in results.items():
        row = cur.execute(
            "SELECT devName, devVendor FROM Devices WHERE devMac = ?",
            (mac,),
        ).fetchone()
        assert row["devName"] == expected["name"], f"Device {mac} name mismatch: got {row['devName']}, expected {expected['name']}"
