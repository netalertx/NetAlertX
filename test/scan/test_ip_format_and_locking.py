import pytest
from unittest.mock import Mock, patch
from server.scan import device_handling


@pytest.fixture
def mock_ip_handlers():
    """Mock device_handling helper functions to isolate IP logic."""
    with patch.multiple(
        "server.scan.device_handling",
        update_devPresentLastScan_based_on_nics=Mock(return_value=0),
        update_devPresentLastScan_based_on_force_status=Mock(return_value=0),
        query_MAC_vendor=Mock(return_value=-1),
        guess_icon=Mock(return_value="icon"),
        guess_type=Mock(return_value="type"),
        get_setting_value=Mock(return_value=""),
        get_plugin_authoritative_settings=Mock(return_value={})
    ):
        yield

# --- Test Cases ---


def test_valid_ipv4_format_accepted(scan_db, mock_ip_handlers):
    """Valid IPv4 address should be accepted and set as primary IPv4."""
    cur = scan_db.cursor()
    cur.execute("INSERT INTO Devices (devMac, devName) VALUES (?, ?)", ("ff:ff:cc:dd:ee:01", "Device1"))
    cur.execute(
        "INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
        ("ff:ff:cc:dd:ee:01", "192.168.1.100", "ARPSCAN", "2025-01-01 01:00:00")
    )
    scan_db.commit()

    db = Mock(sql_connection=scan_db, sql=cur)
    device_handling.update_devices_data_from_scan(db)
    device_handling.update_ipv4_ipv6(db)

    row = cur.execute("SELECT devLastIP, devPrimaryIPv4 FROM Devices WHERE devMac = ?", ("ff:ff:cc:dd:ee:01",)).fetchone()
    assert row["devLastIP"] == "192.168.1.100"
    assert row["devPrimaryIPv4"] == "192.168.1.100"


def test_valid_ipv6_format_accepted(scan_db, mock_ip_handlers):
    """Valid IPv6 address should be accepted and set as primary IPv6."""
    cur = scan_db.cursor()
    cur.execute("INSERT INTO Devices (devMac) VALUES (?)", ("ff:ff:cc:dd:ee:02",))
    cur.execute(
        "INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
        ("ff:ff:cc:dd:ee:02", "fe80::1", "ARPSCAN", "2025-01-01 01:00:00")
    )
    scan_db.commit()

    db = Mock(sql_connection=scan_db, sql=cur)
    device_handling.update_devices_data_from_scan(db)
    device_handling.update_ipv4_ipv6(db)

    row = cur.execute("SELECT devPrimaryIPv6 FROM Devices WHERE devMac = ?", ("ff:ff:cc:dd:ee:02",)).fetchone()
    assert row["devPrimaryIPv6"] == "fe80::1"


def test_invalid_ip_values_rejected(scan_db, mock_ip_handlers):
    """Invalid IP values like (unknown), null, empty should be rejected."""
    cur = scan_db.cursor()
    cur.execute("INSERT INTO Devices (devMac, devPrimaryIPv4) VALUES (?, ?)", ("ff:ff:cc:dd:ee:03", "192.168.1.50"))

    invalid_ips = ["", "null", "(unknown)", "(Unknown)"]
    for invalid_ip in invalid_ips:
        cur.execute("DELETE FROM CurrentScan")
        cur.execute(
            "INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
            ("ff:ff:cc:dd:ee:03", invalid_ip, "ARPSCAN", "2025-01-01 01:00:00")
        )
        scan_db.commit()

        db = Mock(sql_connection=scan_db, sql=cur)
        device_handling.update_devices_data_from_scan(db)
        device_handling.update_ipv4_ipv6(db)

        row = cur.execute("SELECT devPrimaryIPv4 FROM Devices WHERE devMac = ?", ("ff:ff:cc:dd:ee:03",)).fetchone()
        assert row["devPrimaryIPv4"] == "192.168.1.50", f"Failed on {invalid_ip}"


def test_ipv4_then_ipv6_scan_updates_primary_ips(scan_db, mock_ip_handlers):
    """
    Test that multiple scans with different IP types correctly update:
    - devLastIP to the latest scan
    - devPrimaryIPv4 and devPrimaryIPv6 appropriately
    """
    cur = scan_db.cursor()

    # 1️⃣ Create device
    cur.execute("INSERT INTO Devices (devMac) VALUES (?)", ("ff:ff:cc:dd:ee:04",))
    scan_db.commit()

    db = Mock(sql_connection=scan_db, sql=cur)

    # 2️⃣ First scan: IPv4
    cur.execute(
        "INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
        ("ff:ff:cc:dd:ee:04", "192.168.1.100", "ARPSCAN", "2025-01-01 01:00:00")
    )
    scan_db.commit()

    with patch("server.scan.device_handling.get_plugin_authoritative_settings", return_value={}):
        device_handling.update_devices_data_from_scan(db)
        device_handling.update_ipv4_ipv6(db)

    # 3️⃣ Second scan: IPv6
    cur.execute("DELETE FROM CurrentScan")
    cur.execute(
        "INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
        ("ff:ff:cc:dd:ee:04", "fe80::1", "IPv6SCAN", "2025-01-01 02:00:00")
    )
    scan_db.commit()

    with patch("server.scan.device_handling.get_plugin_authoritative_settings", return_value={}):
        device_handling.update_devices_data_from_scan(db)
        device_handling.update_ipv4_ipv6(db)

    # 4️⃣ Verify results
    row = cur.execute(
        "SELECT devLastIP, devPrimaryIPv4, devPrimaryIPv6 FROM Devices WHERE devMac = ?",
        ("ff:ff:cc:dd:ee:04",)
    ).fetchone()

    assert row["devLastIP"] == "fe80::1"       # Latest scan IP (IPv6)
    assert row["devPrimaryIPv4"] == "192.168.1.100"  # IPv4 preserved
    assert row["devPrimaryIPv6"] == "fe80::1"        # IPv6 set


def test_ipv4_address_format_variations(scan_db, mock_ip_handlers):
    """Test various valid IPv4 formats."""
    cur = scan_db.cursor()
    ipv4_addresses = ["1.1.1.1", "127.0.0.1", "192.168.1.1", "255.255.255.255"]

    for idx, ipv4 in enumerate(ipv4_addresses):
        mac = f"AA:BB:CC:DD:11:{idx:02X}".lower()
        cur.execute("INSERT INTO Devices (devMac) VALUES (?)", (mac,))
        cur.execute("INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
                    (mac, ipv4, "SCAN", "2025-01-01 01:00:00"))

    scan_db.commit()
    db = Mock(sql_connection=scan_db, sql=cur)
    device_handling.update_devices_data_from_scan(db)
    device_handling.update_ipv4_ipv6(db)

    for ipv4 in ipv4_addresses:
        row = cur.execute("SELECT devPrimaryIPv4 FROM Devices WHERE devLastIP = ?", (ipv4,)).fetchone()
        assert row is not None


def test_ipv6_address_format_variations(scan_db, mock_ip_handlers):
    """Test various valid IPv6 formats."""
    cur = scan_db.cursor()
    ipv6_addresses = ["::1", "fe80::1", "2001:db8::1", "::ffff:192.0.2.1"]

    for idx, ipv6 in enumerate(ipv6_addresses):
        mac = f"BB:BB:CC:DD:22:{idx:02X}"
        cur.execute("INSERT INTO Devices (devMac) VALUES (?)", (mac,))
        cur.execute("INSERT INTO CurrentScan (scanMac, scanLastIP, scanSourcePlugin, scanLastConnection) VALUES (?, ?, ?, ?)",
                    (mac, ipv6, "SCAN", "2025-01-01 01:00:00"))

    scan_db.commit()
    db = Mock(sql_connection=scan_db, sql=cur)
    device_handling.update_devices_data_from_scan(db)
    device_handling.update_ipv4_ipv6(db)

    for ipv6 in ipv6_addresses:
        row = cur.execute("SELECT devPrimaryIPv6 FROM Devices WHERE devLastIP = ?", (ipv6,)).fetchone()
        assert row is not None

