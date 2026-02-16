import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from api_server.api_server_start import app
from helper import get_setting_value


@pytest.fixture(scope="session")
def api_token():
    return get_setting_value("API_TOKEN")


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- Device Search Tests ---


@patch("models.device_instance.get_temp_db_connection")
def test_get_device_info_ip_partial(mock_db_conn, client, api_token):
    """Test device search with partial IP search."""
    # Mock database connection - DeviceInstance._fetchall calls conn.execute().fetchall()
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [{"devName": "Test Device", "devMac": "aa:bb:cc:dd:ee:ff", "devLastIP": "192.168.1.50"}]
    mock_conn.execute.return_value = mock_execute_result
    mock_db_conn.return_value = mock_conn

    payload = {"query": ".50"}
    response = client.post("/devices/search", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["devices"]) == 1
    assert data["devices"][0]["devLastIP"] == "192.168.1.50"


# --- Trigger Scan Tests ---


@patch("api_server.api_server_start.UserEventsQueueInstance")
def test_trigger_scan_ARPSCAN(mock_queue_class, client, api_token):
    """Test trigger_scan with ARPSCAN type."""
    mock_queue = MagicMock()
    mock_queue_class.return_value = mock_queue

    payload = {"type": "ARPSCAN"}
    response = client.post("/nettools/trigger-scan", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    mock_queue.add_event.assert_called_once()
    call_args = mock_queue.add_event.call_args[0]
    assert "run|ARPSCAN" in call_args[0]


@patch("api_server.api_server_start.UserEventsQueueInstance")
def test_trigger_scan_invalid_type(mock_queue_class, client, api_token):
    """Test trigger_scan with invalid scan type."""
    mock_queue = MagicMock()
    mock_queue_class.return_value = mock_queue

    payload = {"type": "invalid_type", "target": "192.168.1.0/24"}
    response = client.post("/nettools/trigger-scan", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


# --- get_open_ports Tests ---


@patch("models.plugin_object_instance.get_temp_db_connection")
@patch("models.device_instance.get_temp_db_connection")
def test_get_open_ports_ip(mock_device_db_conn, mock_plugin_db_conn, client, api_token):
    """Test get_open_ports with an IP address."""
    # Mock database connections for both device lookup and plugin objects
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()

    # Mock for PluginObjectInstance.getByField (returns port data)
    mock_execute_result.fetchall.return_value = [{"Object_SecondaryID": "22", "Watched_Value2": "ssh"}, {"Object_SecondaryID": "80", "Watched_Value2": "http"}]
    # Mock for DeviceInstance.getByIP (returns device with MAC)
    mock_execute_result.fetchone.return_value = {"devMac": "aa:bb:cc:dd:ee:ff"}

    mock_conn.execute.return_value = mock_execute_result
    mock_plugin_db_conn.return_value = mock_conn
    mock_device_db_conn.return_value = mock_conn

    payload = {"target": "192.168.1.1"}
    response = client.post("/device/open_ports", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["open_ports"]) == 2
    assert data["open_ports"][0]["port"] == 22
    assert data["open_ports"][1]["service"] == "http"


@patch("models.plugin_object_instance.get_temp_db_connection")
def test_get_open_ports_mac_resolve(mock_plugin_db_conn, client, api_token):
    """Test get_open_ports with a MAC address that resolves to an IP."""
    # Mock database connection for MAC-based open ports query
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [{"Object_SecondaryID": "80", "Watched_Value2": "http"}]
    mock_conn.execute.return_value = mock_execute_result
    mock_plugin_db_conn.return_value = mock_conn

    payload = {"target": "aa:bb:cc:dd:ee:ff"}
    response = client.post("/device/open_ports", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "target" in data
    assert len(data["open_ports"]) == 1
    assert data["open_ports"][0]["port"] == 80


# --- get_network_topology Tests ---
@patch("models.device_instance.get_temp_db_connection")
def test_get_network_topology(mock_db_conn, client, api_token):
    """Test get_network_topology."""
    # Mock database connection for topology query
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [
        {"devName": "Router", "devMac": "AA:AA:AA:AA:AA:AA", "devParentMAC": None, "devParentPort": None, "devVendor": "VendorA"},
        {"devName": "Device1", "devMac": "BB:BB:BB:BB:BB:BB", "devParentMAC": "AA:AA:AA:AA:AA:AA", "devParentPort": "eth1", "devVendor": "VendorB"},
    ]
    mock_conn.execute.return_value = mock_execute_result
    mock_db_conn.return_value = mock_conn

    response = client.get("/devices/network/topology", headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["nodes"]) == 2
    links = data.get("links", [])
    assert len(links) == 1
    assert links[0]["source"] == "AA:AA:AA:AA:AA:AA"
    assert links[0]["target"] == "BB:BB:BB:BB:BB:BB"


# --- get_recent_alerts Tests ---
@patch("models.event_instance.get_temp_db_connection")
def test_get_recent_alerts(mock_db_conn, client, api_token):
    """Test get_recent_alerts."""
    # Mock database connection for events query
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mock_execute_result.fetchall.return_value = [{"eve_DateTime": now, "eve_EventType": "New Device", "eve_MAC": "aa:bb:cc:dd:ee:ff"}]
    mock_conn.execute.return_value = mock_execute_result
    mock_db_conn.return_value = mock_conn

    response = client.get("/events/recent", headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["hours"] == 24
    assert "count" in data
    assert "events" in data


# --- Device Alias Tests ---


@patch("models.device_instance.DeviceInstance.updateDeviceColumn")
def test_set_device_alias(mock_update_col, client, api_token):
    """Test set_device_alias."""
    mock_update_col.return_value = {"success": True, "message": "Device alias updated"}

    payload = {"alias": "New Device Name"}
    response = client.post("/device/aa:bb:cc:dd:ee:ff/set-alias", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    mock_update_col.assert_called_once_with("aa:bb:cc:dd:ee:ff", "devName", "New Device Name")


@patch("models.device_instance.DeviceInstance.updateDeviceColumn")
def test_set_device_alias_not_found(mock_update_col, client, api_token):
    """Test set_device_alias when device is not found."""
    mock_update_col.return_value = {"success": False, "error": "Device not found"}

    payload = {"alias": "New Device Name"}
    response = client.post("/device/ff:ff:ff:ff:ff:ff/set-alias", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is False
    assert "Device not found" in data["error"]


# --- Wake-on-LAN Tests ---


@patch("api_server.api_server_start.wakeonlan")
def test_wol_wake_device(mock_wakeonlan, client, api_token):
    """Test wol_wake_device."""
    mock_wakeonlan.return_value = {"success": True, "message": "WOL packet sent to aa:bb:cc:dd:ee:ff"}

    payload = {"devMac": "aa:bb:cc:dd:ee:ff"}
    response = client.post("/nettools/wakeonlan", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "aa:bb:cc:dd:ee:ff" in data["message"]


def test_wol_wake_device_invalid_mac(client, api_token):
    """Test wol_wake_device with invalid MAC."""
    payload = {"devMac": "invalid-mac"}
    response = client.post("/nettools/wakeonlan", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 422
    data = response.get_json()
    assert data["success"] is False


# --- OpenAPI Spec Tests ---

# --- Latest Device Tests ---


@patch("models.device_instance.get_temp_db_connection")
def test_get_latest_device(mock_db_conn, client, api_token):
    """Test get_latest_device endpoint."""
    # Mock database connection for latest device query
    # API uses getLatest() which calls _fetchone
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()
    mock_execute_result.fetchone.return_value = {
        "devName": "Latest Device",
        "devMac": "aa:bb:cc:dd:ee:ff",
        "devLastIP": "192.168.1.100",
        "devFirstConnection": "2025-12-07 10:30:00",
    }
    mock_conn.execute.return_value = mock_execute_result
    mock_db_conn.return_value = mock_conn

    response = client.get("/devices/latest", headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1, "Expected at least one device in response"
    assert data[0]["devName"] == "Latest Device"
    assert data[0]["devMac"] == "aa:bb:cc:dd:ee:ff"


def test_openapi_spec(client, api_token):
    """Test openapi_spec endpoint contains MCP tool paths."""
    response = client.get("/openapi.json", headers=auth_headers(api_token))
    assert response.status_code == 200
    spec = response.get_json()

    # Check for MCP tool endpoints in the spec with correct paths
    assert "/nettools/trigger-scan" in spec["paths"]
    assert "/device/open_ports" in spec["paths"]
    assert "/devices/network/topology" in spec["paths"]
    assert "/events/recent" in spec["paths"]
    assert "/device/{mac}/set-alias" in spec["paths"]
    assert "/nettools/wakeonlan" in spec["paths"]
    # Check for newly added MCP endpoints
    assert "/devices/export" in spec["paths"]
    assert "/devices/import" in spec["paths"]
    assert "/devices/totals" in spec["paths"]
    assert "/nettools/traceroute" in spec["paths"]


# --- MCP Device Export Tests ---


@patch("models.device_instance.get_temp_db_connection")
def test_mcp_devices_export_csv(mock_db_conn, client, api_token):
    """Test MCP devices export in CSV format."""
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [{"devMac": "aa:bb:cc:dd:ee:ff", "devName": "Test Device", "devLastIP": "192.168.1.1"}]
    mock_conn.execute.return_value = mock_execute_result
    mock_db_conn.return_value = mock_conn

    response = client.get("/devices/export", headers=auth_headers(api_token))

    assert response.status_code == 200
    # CSV response should have content-type header
    assert "text/csv" in response.content_type
    assert "attachment; filename=devices.csv" in response.headers.get("Content-Disposition", "")


@patch("models.device_instance.DeviceInstance.exportDevices")
def test_mcp_devices_export_json(mock_export, client, api_token):
    """Test MCP devices export in JSON format."""
    mock_export.return_value = {
        "format": "json",
        "data": [{"devMac": "aa:bb:cc:dd:ee:ff", "devName": "Test Device", "devLastIP": "192.168.1.1"}],
        "columns": ["devMac", "devName", "devLastIP"],
    }

    response = client.get("/devices/export?format=json", headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert "data" in data
    assert "columns" in data
    assert len(data["data"]) == 1


# --- MCP Device Import Tests ---


@patch("models.device_instance.get_temp_db_connection")
def test_mcp_devices_import_json(mock_db_conn, client, api_token):
    """Test MCP devices import from JSON content."""
    mock_conn = MagicMock()
    mock_execute_result = MagicMock()
    mock_conn.execute.return_value = mock_execute_result
    mock_db_conn.return_value = mock_conn

    # Mock successful import
    with patch("models.device_instance.DeviceInstance.importCSV") as mock_import:
        mock_import.return_value = {"success": True, "message": "Imported 2 devices"}

        payload = {"content": "bW9ja2VkIGNvbnRlbnQ="}  # base64 encoded content
        response = client.post("/devices/import", json=payload, headers=auth_headers(api_token))

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "Imported 2 devices" in data["message"]


# --- MCP Device Totals Tests ---


@patch("database.get_temp_db_connection")
def test_mcp_devices_totals(mock_db_conn, client, api_token):
    """Test MCP devices totals endpoint."""
    mock_conn = MagicMock()
    mock_sql = MagicMock()
    mock_execute_result = MagicMock()
    # Mock the getTotals method to return sample data
    mock_execute_result.fetchone.return_value = [10, 8, 2, 0, 1, 3]  # devices, connected, favorites, new, down, archived
    mock_sql.execute.return_value = mock_execute_result
    mock_conn.cursor.return_value = mock_sql
    mock_db_conn.return_value = mock_conn

    response = client.get("/devices/totals", headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    # Should return device counts as array
    assert isinstance(data, list)
    assert len(data) >= 4  # At least online, offline, etc.


# --- MCP Traceroute Tests ---


@patch("api_server.api_server_start.traceroute")
def test_mcp_traceroute(mock_traceroute, client, api_token):
    """Test MCP traceroute endpoint."""
    mock_traceroute.return_value = ({"success": True, "output": "traceroute output"}, 200)

    payload = {"devLastIP": "8.8.8.8"}
    response = client.post("/nettools/traceroute", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "output" in data
    mock_traceroute.assert_called_once_with("8.8.8.8")


@patch("api_server.api_server_start.traceroute")
def test_mcp_traceroute_missing_ip(mock_traceroute, client, api_token):
    """Test MCP traceroute with missing IP."""
    mock_traceroute.return_value = ({"success": False, "error": "Invalid IP: None"}, 400)

    payload = {}  # Missing devLastIP
    response = client.post("/nettools/traceroute", json=payload, headers=auth_headers(api_token))

    assert response.status_code == 422
    data = response.get_json()
    assert data["success"] is False
    assert "error" in data
    mock_traceroute.assert_not_called()
    # mock_traceroute.assert_called_once_with(None)
