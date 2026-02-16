"""
Tests for the Extended MCP API Endpoints.

This module tests the new "Textbook Implementation" endpoints added to the MCP server.
It covers Devices CRUD, Events, Sessions, Messaging, NetTools, Logs, DB Query, and Sync.
"""

from unittest.mock import patch, MagicMock

import pytest

from api_server.api_server_start import app
from helper import get_setting_value


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="session")
def api_token():
    return get_setting_value("API_TOKEN")


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# DEVICES EXTENDED TESTS
# =============================================================================

@patch('models.device_instance.DeviceInstance.setDeviceData')
def test_update_device(mock_set_device, client, api_token):
    """Test POST /device/{mac} for updating device."""
    mock_set_device.return_value = {"success": True}
    payload = {"devName": "Updated Device", "createNew": False}

    response = client.post('/device/00:11:22:33:44:55',
                           json=payload,
                           headers=auth_headers(api_token))

    assert response.status_code == 200
    assert response.json["success"] is True
    mock_set_device.assert_called_with("00:11:22:33:44:55", payload)


@patch('models.device_instance.DeviceInstance.deleteDeviceByMAC')
def test_delete_device(mock_delete, client, api_token):
    """Test DELETE /device/{mac}/delete."""
    mock_delete.return_value = {"success": True}

    response = client.delete('/device/00:11:22:33:44:55/delete',
                             headers=auth_headers(api_token))

    assert response.status_code == 200
    assert response.json["success"] is True
    mock_delete.assert_called_with("00:11:22:33:44:55")


@patch('models.device_instance.DeviceInstance.resetDeviceProps')
def test_reset_device_props(mock_reset, client, api_token):
    """Test POST /device/{mac}/reset-props."""
    mock_reset.return_value = {"success": True}

    response = client.post('/device/00:11:22:33:44:55/reset-props',
                           headers=auth_headers(api_token))

    assert response.status_code == 200
    assert response.json["success"] is True
    mock_reset.assert_called_with("00:11:22:33:44:55")


@patch('models.device_instance.DeviceInstance.copyDevice')
def test_copy_device(mock_copy, client, api_token):
    """Test POST /device/copy."""
    mock_copy.return_value = {"success": True}
    payload = {"macFrom": "00:11:22:33:44:55", "macTo": "aa:bb:cc:dd:ee:ff"}

    response = client.post('/device/copy',
                           json=payload,
                           headers=auth_headers(api_token))

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    mock_copy.assert_called_with("00:11:22:33:44:55", "aa:bb:cc:dd:ee:ff")


@patch('models.device_instance.DeviceInstance.deleteDevices')
def test_delete_devices_bulk(mock_delete, client, api_token):
    """Test DELETE /devices."""
    mock_delete.return_value = {"success": True}
    payload = {"macs": ["00:11:22:33:44:55", "aa:bb:cc:dd:ee:ff"]}

    response = client.delete('/devices',
                             json=payload,
                             headers=auth_headers(api_token))

    assert response.status_code == 200
    mock_delete.assert_called_with(["00:11:22:33:44:55", "aa:bb:cc:dd:ee:ff"])


@patch('models.device_instance.DeviceInstance.deleteAllWithEmptyMacs')
def test_delete_empty_macs(mock_delete, client, api_token):
    """Test DELETE /devices/empty-macs."""
    mock_delete.return_value = {"success": True}
    response = client.delete('/devices/empty-macs', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('models.device_instance.DeviceInstance.deleteUnknownDevices')
def test_delete_unknown_devices(mock_delete, client, api_token):
    """Test DELETE /devices/unknown."""
    mock_delete.return_value = {"success": True}
    response = client.delete('/devices/unknown', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('models.device_instance.DeviceInstance.getFavorite')
def test_get_favorite_devices(mock_get, client, api_token):
    """Test GET /devices/favorite."""
    mock_get.return_value = [{"devMac": "00:11:22:33:44:55", "devFavorite": 1}]
    response = client.get('/devices/favorite', headers=auth_headers(api_token))
    assert response.status_code == 200
    # API returns list of favorite devices (legacy: wrapped in a list -> [[{...}]])
    assert isinstance(response.json, list)
    assert len(response.json) == 1
    # Check inner list
    inner = response.json[0]
    assert isinstance(inner, list)
    assert len(inner) == 1
    assert inner[0]["devMac"] == "00:11:22:33:44:55"


# =============================================================================
# EVENTS EXTENDED TESTS
# =============================================================================

@patch('models.event_instance.EventInstance.createEvent')
def test_create_event(mock_create, client, api_token):
    """Test POST /events/create/{mac}."""
    mock_create.return_value = {"success": True}
    payload = {"event_type": "Test Event", "ip": "1.2.3.4"}

    response = client.post('/events/create/00:11:22:33:44:55',
                           json=payload,
                           headers=auth_headers(api_token))

    assert response.status_code == 200
    mock_create.assert_called_with("00:11:22:33:44:55", "1.2.3.4", "Test Event", "", 1, None)


@patch('models.device_instance.DeviceInstance.deleteDeviceEvents')
def test_delete_events_by_mac(mock_delete, client, api_token):
    """Test DELETE /events/{mac}."""
    mock_delete.return_value = {"success": True}
    response = client.delete('/events/00:11:22:33:44:55', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_delete.assert_called_with("00:11:22:33:44:55")


@patch('models.event_instance.EventInstance.deleteAllEvents')
def test_delete_all_events(mock_delete, client, api_token):
    """Test DELETE /events."""
    mock_delete.return_value = {"success": True}
    response = client.delete('/events', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('models.event_instance.EventInstance.getEvents')
def test_get_all_events(mock_get, client, api_token):
    """Test GET /events."""
    mock_get.return_value = [{"eveMAC": "00:11:22:33:44:55"}]
    response = client.get('/events?mac=00:11:22:33:44:55', headers=auth_headers(api_token))
    assert response.status_code == 200
    assert response.json["success"] is True
    mock_get.assert_called_with("00:11:22:33:44:55")


@patch('models.event_instance.EventInstance.deleteEventsOlderThan')
def test_delete_old_events(mock_delete, client, api_token):
    """Test DELETE /events/{days}."""
    mock_delete.return_value = {"success": True}
    response = client.delete('/events/30', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_delete.assert_called_with(30)


@patch('models.event_instance.EventInstance.getEventsTotals')
def test_get_event_totals(mock_get, client, api_token):
    """Test Events GET /sessions/totals returns event totals via EventInstance.getEventsTotals."""
    mock_get.return_value = [10, 5, 0, 0, 0, 0]
    response = client.get('/sessions/totals?period=7 days', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_get.assert_called_with("7 days")


# =============================================================================
# SESSIONS EXTENDED TESTS
# =============================================================================

@patch('api_server.api_server_start.create_session')
def test_create_session(mock_create, client, api_token):
    """Test POST /sessions/create."""
    mock_create.return_value = ({"success": True}, 200)
    payload = {
        "mac": "00:11:22:33:44:55",
        "ip": "1.2.3.4",
        "start_time": "2023-01-01 10:00:00"
    }

    response = client.post('/sessions/create',
                           json=payload,
                           headers=auth_headers(api_token))

    assert response.status_code == 200
    mock_create.assert_called_once()


@patch('api_server.api_server_start.delete_session')
def test_delete_session(mock_delete, client, api_token):
    """Test DELETE /sessions/delete."""
    mock_delete.return_value = ({"success": True}, 200)
    payload = {"mac": "00:11:22:33:44:55"}

    response = client.delete('/sessions/delete',
                             json=payload,
                             headers=auth_headers(api_token))

    assert response.status_code == 200
    mock_delete.assert_called_with("00:11:22:33:44:55")


@patch('api_server.api_server_start.get_sessions')
def test_list_sessions(mock_get, client, api_token):
    """Test GET /sessions/list."""
    mock_get.return_value = ({"success": True, "sessions": []}, 200)
    response = client.get('/sessions/list?mac=00:11:22:33:44:55', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_get.assert_called_with("00:11:22:33:44:55", None, None)


@patch('api_server.api_server_start.get_sessions_calendar')
def test_sessions_calendar(mock_get, client, api_token):
    """Test GET /sessions/calendar."""
    mock_get.return_value = ({"success": True}, 200)
    response = client.get('/sessions/calendar?start=2023-01-01&end=2023-01-31', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.get_device_sessions')
def test_device_sessions(mock_get, client, api_token):
    """Test GET /sessions/{mac}."""
    mock_get.return_value = ({"success": True}, 200)
    response = client.get('/sessions/00:11:22:33:44:55?period=7 days', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_get.assert_called_with("00:11:22:33:44:55", "7 days")


@patch('api_server.api_server_start.get_session_events')
def test_session_events(mock_get, client, api_token):
    """Test GET /sessions/session-events."""
    mock_get.return_value = ({"success": True}, 200)
    response = client.get('/sessions/session-events', headers=auth_headers(api_token))
    assert response.status_code == 200


# =============================================================================
# MESSAGING EXTENDED TESTS
# =============================================================================

@patch('api_server.api_server_start.write_notification')
def test_write_notification(mock_write, client, api_token):
    """Test POST /messaging/in-app/write."""
    # Set return value to match real function behavior (returns None)
    mock_write.return_value = None
    payload = {"content": "Test Alert", "level": "warning"}
    response = client.post('/messaging/in-app/write',
                           json=payload,
                           headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_write.assert_called_with("Test Alert", "warning")


@patch('api_server.api_server_start.get_unread_notifications')
def test_get_unread_notifications(mock_get, client, api_token):
    """Test GET /messaging/in-app/unread."""
    mock_get.return_value = ([], 200)
    response = client.get('/messaging/in-app/unread', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.mark_all_notifications_read')
def test_mark_all_read(mock_mark, client, api_token):
    """Test POST /messaging/in-app/read/all."""
    mock_mark.return_value = {"success": True}
    response = client.post('/messaging/in-app/read/all', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.delete_notifications')
def test_delete_all_notifications(mock_delete, client, api_token):
    """Test DELETE /messaging/in-app/delete."""
    mock_delete.return_value = ({"success": True}, 200)
    response = client.delete('/messaging/in-app/delete', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.delete_notification')
def test_delete_single_notification(mock_delete, client, api_token):
    """Test DELETE /messaging/in-app/delete/{guid}."""
    mock_delete.return_value = {"success": True}
    response = client.delete('/messaging/in-app/delete/abc-123', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_delete.assert_called_with("abc-123")


@patch('api_server.api_server_start.mark_notification_as_read')
def test_read_single_notification(mock_read, client, api_token):
    """Test POST /messaging/in-app/read/{guid}."""
    mock_read.return_value = {"success": True}
    response = client.post('/messaging/in-app/read/abc-123', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_read.assert_called_with("abc-123")


# =============================================================================
# NET TOOLS EXTENDED TESTS
# =============================================================================

@patch('api_server.api_server_start.speedtest')
def test_speedtest(mock_run, client, api_token):
    """Test GET /nettools/speedtest."""
    mock_run.return_value = ({"success": True}, 200)
    response = client.get('/nettools/speedtest', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.nslookup')
def test_nslookup(mock_run, client, api_token):
    """Test POST /nettools/nslookup."""
    mock_run.return_value = ({"success": True}, 200)
    payload = {"devLastIP": "8.8.8.8"}
    response = client.post('/nettools/nslookup',
                           json=payload,
                           headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_run.assert_called_with("8.8.8.8")


@patch('api_server.api_server_start.nmap_scan')
def test_nmap(mock_run, client, api_token):
    """Test POST /nettools/nmap."""
    mock_run.return_value = ({"success": True}, 200)
    payload = {"scan": "192.168.1.1", "mode": "fast"}
    response = client.post('/nettools/nmap',
                           json=payload,
                           headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_run.assert_called_with("192.168.1.1", "fast")


@patch('api_server.api_server_start.internet_info')
def test_internet_info(mock_run, client, api_token):
    """Test GET /nettools/internetinfo."""
    mock_run.return_value = ({"success": True}, 200)
    response = client.get('/nettools/internetinfo', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.network_interfaces')
def test_interfaces(mock_run, client, api_token):
    """Test GET /nettools/interfaces."""
    mock_run.return_value = ({"success": True}, 200)
    response = client.get('/nettools/interfaces', headers=auth_headers(api_token))
    assert response.status_code == 200


# =============================================================================
# LOGS & HISTORY & METRICS
# =============================================================================

@patch('api_server.api_server_start.delete_online_history')
def test_delete_history(mock_delete, client, api_token):
    """Test DELETE /history."""
    mock_delete.return_value = ({"success": True}, 200)
    response = client.delete('/history', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.clean_log')
def test_clean_log(mock_clean, client, api_token):
    """Test DELETE /logs."""
    mock_clean.return_value = ({"success": True}, 200)
    response = client.delete('/logs?file=app.log', headers=auth_headers(api_token))
    assert response.status_code == 200
    mock_clean.assert_called_with("app.log")


@patch('api_server.api_server_start.UserEventsQueueInstance')
def test_add_to_queue(mock_queue_class, client, api_token):
    """Test POST /logs/add-to-execution-queue."""
    mock_queue = MagicMock()
    mock_queue.add_event.return_value = (True, "Added")
    mock_queue_class.return_value = mock_queue

    payload = {"action": "test_action"}
    response = client.post('/logs/add-to-execution-queue',
                           json=payload,
                           headers=auth_headers(api_token))
    assert response.status_code == 200
    assert response.json["success"] is True


@patch('api_server.api_server_start.get_metric_stats')
def test_metrics(mock_get, client, api_token):
    """Test GET /metrics."""
    mock_get.return_value = "metrics_data 1"
    response = client.get('/metrics', headers=auth_headers(api_token))
    assert response.status_code == 200
    assert b"metrics_data 1" in response.data


# =============================================================================
# SYNC
# =============================================================================

@patch('api_server.api_server_start.handle_sync_get')
def test_sync_get(mock_handle, client, api_token):
    """Test GET /sync."""
    mock_handle.return_value = ({"success": True}, 200)
    response = client.get('/sync', headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.handle_sync_post')
def test_sync_post(mock_handle, client, api_token):
    """Test POST /sync."""
    mock_handle.return_value = ({"success": True}, 200)
    payload = {"data": {}, "node_name": "node1", "plugin": "test"}
    response = client.post('/sync',
                           json=payload,
                           headers=auth_headers(api_token))
    assert response.status_code == 200


# =============================================================================
# DB QUERY
# =============================================================================

@patch('api_server.api_server_start.read_query')
def test_db_read(mock_read, client, api_token):
    """Test POST /dbquery/read."""
    mock_read.return_value = ({"success": True}, 200)
    payload = {"rawSql": "base64encoded", "confirm_dangerous_query": True}
    response = client.post('/dbquery/read', json=payload, headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.write_query')
def test_db_write(mock_write, client, api_token):
    """Test POST /dbquery/write."""
    mock_write.return_value = ({"success": True}, 200)
    payload = {"rawSql": "base64encoded", "confirm_dangerous_query": True}
    response = client.post('/dbquery/write', json=payload, headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.update_query')
def test_db_update(mock_update, client, api_token):
    """Test POST /dbquery/update."""
    mock_update.return_value = ({"success": True}, 200)
    payload = {
        "columnName": "id",
        "id": [1],
        "dbtable": "Settings",
        "columns": ["col"],
        "values": ["val"]
    }
    response = client.post('/dbquery/update', json=payload, headers=auth_headers(api_token))
    assert response.status_code == 200


@patch('api_server.api_server_start.delete_query')
def test_db_delete(mock_delete, client, api_token):
    """Test POST /dbquery/delete."""
    mock_delete.return_value = ({"success": True}, 200)
    payload = {
        "columnName": "id",
        "id": [1],
        "dbtable": "Settings"
    }
    response = client.post('/dbquery/delete', json=payload, headers=auth_headers(api_token))
    assert response.status_code == 200
