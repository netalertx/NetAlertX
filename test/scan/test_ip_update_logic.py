"""
Unit tests for device IP update logic (devPrimaryIPv4/devPrimaryIPv6 handling).
"""

from unittest.mock import Mock, patch
import pytest
from server.scan import device_handling


@pytest.fixture
def mock_device_handling():
    """Mock device_handling dependencies."""
    with patch.multiple(
        device_handling,
        update_devPresentLastScan_based_on_nics=Mock(return_value=0),
        update_devPresentLastScan_based_on_force_status=Mock(return_value=0),
        query_MAC_vendor=Mock(return_value=-1),
        guess_icon=Mock(return_value="icon"),
        guess_type=Mock(return_value="type"),
        get_setting_value=Mock(side_effect=lambda key: {
            "NEWDEV_replace_preset_icon": 0,
            "NEWDEV_devIcon": "icon",
            "NEWDEV_devType": "type",
        }.get(key, "")),
    ):
        yield


def test_ipv6_update_preserves_ipv4(scan_db, mock_device_handling):
    """
    Test that when a device already has a primary IPv4 and receives an IPv6 scan:
    - devLastIP is updated to the latest IP (IPv6)
    - devPrimaryIPv6 is set to the new IPv6
    - devPrimaryIPv4 is preserved
    """
    cur = scan_db.cursor()

    # 1️⃣ Create device with IPv4
    cur.execute(
        "INSERT INTO Devices (devMac, devLastIP, devPrimaryIPv4, devName) VALUES (?, ?, ?, ?)",
        ("aa:bb:cc:dd:ee:ff", "192.168.1.10", "192.168.1.10", "Device")
    )

    # 2️⃣ Insert a scan reporting IPv6
    cur.execute(
        """
        INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection)
        VALUES (?, ?, ?, ?)
        """,
        ("aa:bb:cc:dd:ee:ff", "2001:db8::1", "TEST_PLUGIN", "2025-01-01 01:00:00")
    )
    scan_db.commit()

    db = Mock(sql_connection=scan_db, sql=cur)

    # 3️⃣ Mock plugin authoritative settings
    with patch("server.scan.device_handling.get_plugin_authoritative_settings", return_value={}):
        device_handling.update_devices_data_from_scan(db)
        device_handling.update_ipv4_ipv6(db)

    # 4️⃣ Verify the device fields
    row = cur.execute(
        "SELECT devLastIP, devPrimaryIPv4, devPrimaryIPv6 FROM Devices WHERE devMac = ?",
        ("aa:bb:cc:dd:ee:ff",),
    ).fetchone()

    assert row["devLastIP"] == "2001:db8::1"        # Latest IP is now IPv6
    assert row["devPrimaryIPv6"] == "2001:db8::1"   # IPv6 field updated
    assert row["devPrimaryIPv4"] == "192.168.1.10"  # IPv4 preserved


def test_primary_ipv4_is_set_and_ipv6_preserved(scan_db, mock_device_handling):
    """Setting IPv4 in CurrentScan should update devPrimaryIPv4 without changing devPrimaryIPv6."""
    cur = scan_db.cursor()

    # Create device with IPv6 primary
    cur.execute(
        """
        INSERT INTO Devices (
            devMac, devLastConnection, devPresentLastScan, devLastIP,
            devPrimaryIPv4, devPrimaryIPv6, devVendor, devType, devName, devIcon
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("11:22:33:44:55:66", "2025-01-01 00:00:00", 0, "2001:db8::2", "", "2001:db8::2", "TestVendor", "type", "Device", "icon")
    )

    # CurrentScan with IPv4
    cur.execute(
        "INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
        ("11:22:33:44:55:66", "10.0.0.5", "ARPSCAN", "2025-01-01 02:00:00")
    )
    scan_db.commit()

    db = Mock(sql_connection=scan_db, sql=cur)

    device_handling.update_devices_data_from_scan(db)
    device_handling.update_ipv4_ipv6(db)

    row = cur.execute(
        "SELECT devLastIP, devPrimaryIPv4, devPrimaryIPv6 FROM Devices WHERE devMac = ?",
        ("11:22:33:44:55:66",),
    ).fetchone()

    assert row["devLastIP"] == "10.0.0.5"
    assert row["devPrimaryIPv4"] == "10.0.0.5"
    assert row["devPrimaryIPv6"] == "2001:db8::2"
