import os
import sqlite3
import tempfile
import pytest
from unittest.mock import Mock, patch

# Add server paths
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server', 'db'))

from db.sql_safe_builder import create_safe_condition_builder  # noqa: E402 [flake8 lint suppression]
from messaging.reporting import get_notifications  # noqa: E402 [flake8 lint suppression]

# -----------------------------
# Fixtures
# -----------------------------


@pytest.fixture
def test_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        path = tmp.name
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def builder():
    return create_safe_condition_builder()


@pytest.fixture
def test_db(test_db_path):
    conn = sqlite3.connect(test_db_path)
    cur = conn.cursor()

    # Minimal schema for integration testing
    cur.execute('''
        CREATE TABLE IF NOT EXISTS Events_Devices (
            eveMac TEXT,
            eveDateTime TEXT,
            devLastIP TEXT,
            eveIp TEXT,
            eveEventType TEXT,
            devName TEXT,
            devVendor TEXT,
            devComments TEXT,
            evePendingAlertEmail INTEGER
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS Devices (
            devMac TEXT PRIMARY KEY,
            devName TEXT,
            devComments TEXT,
            devAlertEvents INTEGER DEFAULT 1,
            devAlertDown INTEGER DEFAULT 1
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS Events (
            eveMac TEXT,
            eveDateTime TEXT,
            eveEventType TEXT,
            evePendingAlertEmail INTEGER
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS Plugins_Events (
            plugin TEXT,
            objectPrimaryId TEXT,
            objectSecondaryId TEXT,
            dateTimeChanged TEXT,
            watchedValue1 TEXT,
            watchedValue2 TEXT,
            watchedValue3 TEXT,
            watchedValue4 TEXT,
            "status" TEXT
        )
    ''')

    # Insert test data
    test_data = [
        ('aa:bb:cc:dd:ee:ff', '2024-01-01 12:00:00', '192.168.1.100', '192.168.1.100', 'New Device', 'Test Device', 'Apple', 'Test Comment', 1),
        ('11:22:33:44:55:66', '2024-01-01 12:01:00', '192.168.1.101', '192.168.1.101', 'Connected', 'Test Device 2', 'Dell', 'Another Comment', 1),
        ('77:88:99:aa:bb:cc', '2024-01-01 12:02:00', '192.168.1.102', '192.168.1.102', 'Disconnected', 'Test Device 3', 'Cisco', 'Third Comment', 1),
    ]
    cur.executemany('''
        INSERT INTO Events_Devices (eveMac, eveDateTime, devLastIP, eveIp, eveEventType, devName, devVendor, devComments, evePendingAlertEmail)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', test_data)

    conn.commit()
    conn.close()
    return test_db_path

# -----------------------------
# Tests
# -----------------------------


def test_fresh_install_compatibility(builder):
    condition, params = builder.get_safe_condition_legacy("")
    assert condition == ""
    assert params == {}

    condition, params = builder.get_safe_condition_legacy("AND devName = 'TestDevice'")
    assert "devName = :" in condition
    assert 'TestDevice' in params.values()


def test_existing_db_compatibility():
    mock_db = Mock()
    mock_result = Mock()
    mock_result.columnNames = ['devName', 'eveMac', 'devVendor', 'eveIp', 'eveDateTime', 'eveEventType', 'devComments']
    mock_result.json = {'data': []}
    mock_db.get_table_as_json.return_value = mock_result

    with patch('messaging.reporting.get_setting_value') as s:
        s.side_effect = lambda k: {
            'NTFPRCS_INCLUDED_SECTIONS': ['new_devices', 'events'],
            'NTFPRCS_new_dev_condition': "AND devName = 'TestDevice'",
            'NTFPRCS_event_condition': "AND devComments LIKE '%test%'",
            'NTFPRCS_alert_down_time': '60'
        }.get(k, '')

        with patch('messaging.reporting.get_timezone_offset', return_value='+00:00'):
            result = get_notifications(mock_db)

    assert 'new_devices' in result
    assert 'events' in result
    assert 'new_devices_meta' in result
    assert 'events_meta' in result
    assert mock_db.get_table_as_json.called


def test_notification_system_integration(builder):
    email_condition = "AND devName = 'EmailTestDevice'"
    condition, params = builder.get_safe_condition_legacy(email_condition)
    assert "devName = :" in condition
    assert 'EmailTestDevice' in params.values()

    apprise_condition = "AND eveEventType = 'Connected'"
    condition, params = builder.get_safe_condition_legacy(apprise_condition)
    assert "eveEventType = :" in condition
    assert 'Connected' in params.values()

    webhook_condition = "AND devComments LIKE '%webhook%'"
    condition, params = builder.get_safe_condition_legacy(webhook_condition)
    assert "devComments LIKE :" in condition
    assert '%webhook%' in params.values()

    mqtt_condition = "AND eveMac = 'aa:bb:cc:dd:ee:ff'"
    condition, params = builder.get_safe_condition_legacy(mqtt_condition)
    assert "eveMac = :" in condition
    assert 'aa:bb:cc:dd:ee:ff' in params.values()


def test_settings_persistence(builder):
    test_settings = [
        "AND devName = 'Persistent Device'",
        "AND devComments = {s-quote}Legacy Quote{s-quote}",
        "AND eveEventType IN ('Connected', 'Disconnected')",
        "AND devLastIP = '192.168.1.1'",
        ""
    ]
    for setting in test_settings:
        condition, params = builder.get_safe_condition_legacy(setting)
        assert isinstance(condition, str)
        assert isinstance(params, dict)


def test_device_operations(builder):
    device_conditions = [
        "AND devName = 'Updated Device'",
        "AND devMac = 'aa:bb:cc:dd:ee:ff'",
        "AND devComments = 'Device updated successfully'",
        "AND devLastIP = '192.168.1.200'"
    ]
    for cond in device_conditions:
        safe_condition, params = builder.get_safe_condition_legacy(cond)
        assert len(params) > 0 or safe_condition == ""
        assert "'" not in safe_condition


def test_plugin_functionality(builder):
    plugin_conditions = [
        "AND plugin = 'TestPlugin'",
        "AND objectPrimaryId = 'primary123'",
        "AND status = 'Active'"
    ]
    for cond in plugin_conditions:
        safe_condition, params = builder.get_safe_condition_legacy(cond)
        if safe_condition:
            assert ":" in safe_condition
            assert len(params) > 0


def test_sql_injection_prevention(builder):
    malicious_inputs = [
        "'; DROP TABLE Events_Devices; --",
        "' OR '1'='1",
        "1' UNION SELECT * FROM Devices --",
        "'; INSERT OR IGNORE INTO Events VALUES ('hacked'); --",
        "' AND (SELECT COUNT(*) FROM sqlite_master) > 0 --"
    ]
    for payload in malicious_inputs:
        condition, params = builder.get_safe_condition_legacy(payload)
        assert condition == ""
        assert params == {}


def test_error_handling(builder):
    invalid_condition = "INVALID SQL SYNTAX HERE"
    condition, params = builder.get_safe_condition_legacy(invalid_condition)
    assert condition == ""
    assert params == {}

    edge_cases = [None, "", "   ", "\n\t", "AND column_not_in_whitelist = 'value'"]
    for case in edge_cases:
        if case is not None:
            condition, params = builder.get_safe_condition_legacy(case)
            assert isinstance(condition, str)
            assert isinstance(params, dict)


def test_backward_compatibility(builder):
    legacy_conditions = [
        "AND devName = {s-quote}Legacy Device{s-quote}",
        "AND devComments = {s-quote}Old Style Quote{s-quote}",
        "AND devName = 'Normal Quote'"
    ]
    for cond in legacy_conditions:
        condition, params = builder.get_safe_condition_legacy(cond)
        if condition:
            assert "{s-quote}" not in condition
            assert ":" in condition
            assert len(params) > 0


def test_performance_impact(builder):
    import time
    test_condition = "AND devName = 'Performance Test Device'"
    start = time.time()
    for _ in range(1000):
        condition, params = builder.get_safe_condition_legacy(test_condition)
    end = time.time()
    avg_ms = (end - start) / 1000 * 1000
    assert avg_ms < 1.0
