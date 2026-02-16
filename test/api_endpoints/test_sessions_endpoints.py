import sys
import random
import os
import pytest
from datetime import datetime, timedelta

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value   # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from api_server.api_server_start import app  # noqa: E402 [flake8 lint suppression]


@pytest.fixture(scope="session")
def api_token():
    return get_setting_value("API_TOKEN")


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_mac():
    # Generate a unique MAC for each test run
    return "aa:bb:cc:" + ":".join(f"{random.randint(0, 255):02X}" for _ in range(3)).lower()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_device(client, api_token, test_mac):
    payload = {
        "createNew": True,
        "devOwner": "Unit Test",
        "devType": "Router",
        "devVendor": "TestVendor",
    }
    resp = client.post(f"/device/{test_mac}", json=payload, headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True


# -----------------------------
def test_create_session(client, api_token, test_mac):
    payload = {
        "mac": test_mac,
        "ip": "192.168.1.100",
        "start_time": timeNowUTC(),
        "event_type_conn": "Connected",
        "event_type_disc": "Disconnected"
    }
    resp = client.post("/sessions/create", json=payload, headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True


# -----------------------------
def test_list_sessions(client, api_token, test_mac):
    # Ensure at least one session exists
    payload = {
        "mac": test_mac,
        "ip": "192.168.1.100",
        "start_time": timeNowUTC()
    }
    client.post("/sessions/create", json=payload, headers=auth_headers(api_token))

    # List sessions for MAC
    resp = client.get(f"/sessions/list?mac={test_mac}", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True
    sessions = resp.json.get("sessions")
    assert any(ses["ses_MAC"] == test_mac for ses in sessions)


def test_device_sessions_by_period(client, api_token, test_mac):
    # 1. Create a dummy session so we have data
    payload = {
        "mac": test_mac,
        "ip": "192.168.1.200",
        "start_time": timeNowUTC()
    }
    resp_create = client.post("/sessions/create", json=payload, headers=auth_headers(api_token))
    assert resp_create.status_code == 200
    assert resp_create.json.get("success") is True

    # 2. Query sessions for the device with a valid period
    resp = client.get(
        f"/sessions/{test_mac}?period=7 days",
        headers=auth_headers(api_token)
    )
    assert resp.status_code == 200

    data = resp.json
    assert data.get("success") is True
    assert "sessions" in data

    sessions = data["sessions"]

    print(sessions)
    print(test_mac)

    assert isinstance(sessions, list)
    assert any(s["ses_MAC"] == test_mac for s in sessions)


def test_device_session_events(client, api_token, test_mac):
    """
    Test fetching session/events from the /sessions/session-events endpoint.
    """

    # 1. Create a dummy session to ensure we have data
    payload = {
        "mac": test_mac,
        "ip": "192.168.1.250",
        "start_time": timeNowUTC()
    }
    resp_create = client.post(
        "/sessions/create",
        json=payload,
        headers=auth_headers(api_token)
    )
    assert resp_create.status_code == 200
    assert resp_create.json.get("success") is True

    # 2. Fetch session events with default type ('all') and period ('7 days')
    resp = client.get(
        "/sessions/session-events?type=all&period=7 days",
        headers=auth_headers(api_token)
    )
    assert resp.status_code == 200

    data = resp.json
    assert "data" in data  # table data key
    events = data["data"]

    # 3. Validate the response structure
    assert isinstance(events, list)

    # If there is at least one row, check fields for sessions
    if events:
        row = events[0]
        # Expecting row as list with at least expected columns
        assert isinstance(row, list)
        # IP and datetime fields should exist
        assert row[9]  # IP column
        assert row[3]  # Event datetime column

    # 4. Optionally, test filtering by session type
    resp_sessions = client.get(
        "/sessions/session-events?type=sessions&period=7 days",
        headers=auth_headers(api_token)
    )
    assert resp_sessions.status_code == 200
    sessions = resp_sessions.json["data"]
    assert isinstance(sessions, list)


# -----------------------------
def test_delete_session(client, api_token, test_mac):
    # First create session
    payload = {
        "mac": test_mac,
        "ip": "192.168.1.100",
        "start_time": timeNowUTC()
    }
    client.post("/sessions/create", json=payload, headers=auth_headers(api_token))

    # Delete session
    resp = client.delete("/sessions/delete", json={"mac": test_mac}, headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True

    # Confirm deletion
    resp = client.get(f"/sessions/list?mac={test_mac}", headers=auth_headers(api_token))
    sessions = resp.json.get("sessions")
    assert not any(ses["ses_MAC"] == test_mac for ses in sessions)


def test_get_sessions_calendar(client, api_token, test_mac):
    """
    Test the /sessions/calendar endpoint.
    Creates session and ensures the calendar output is correct.
    Cleans up test sessions after test.
    """
    # --- Setup: create two sessions for the test MAC ---
    now = timeNowUTC(as_string=False)
    start1 = (now - timedelta(days=2)).isoformat(timespec="seconds")
    end1   = (now - timedelta(days=1, hours=20)).isoformat(timespec="seconds")

    start2 = (now - timedelta(days=1)).isoformat(timespec="seconds")
    end2   = (now - timedelta(hours=20)).isoformat(timespec="seconds")

    # Create sessions using your endpoint
    client.post("/sessions/create", json={
        "mac": test_mac,
        "ip": "192.168.1.100",
        "start_time": start1,
        "end_time": end1,
        "event_type_conn": "connect",
        "event_type_disc": "disconnect"
    }, headers=auth_headers(api_token))

    client.post("/sessions/create", json={
        "mac": test_mac,
        "ip": "192.168.1.100",
        "start_time": start2,
        "end_time": end2,
        "event_type_conn": "connect",
        "event_type_disc": "disconnect"
    }, headers=auth_headers(api_token))

    # --- Call the /sessions/calendar API ---
    start_date = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    end_date   = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    resp = client.get(
        f"/sessions/calendar?start={start_date}&end={end_date}",
        headers=auth_headers(api_token)
    )

    assert resp.status_code == 200
    data = resp.json
    assert data.get("success") is True
    assert "sessions" in data
    sessions = data["sessions"]

    # --- Verify calendar sessions ---
    assert len(sessions) >= 2  # at least our two sessions

    # Check expected keys
    expected_keys = {"resourceId", "title", "start", "end", "color", "tooltip", "className"}
    for ses in sessions:
        assert set(ses.keys()) == expected_keys

    # Check that all sessions belong to the test MAC
    mac_sessions = [ses for ses in sessions if ses["resourceId"] == test_mac]
    assert len(mac_sessions) == 2  # or exact number if you know it

    # Check ISO date formatting for start/end
    for ses in mac_sessions:
        # start must always be present
        assert ses["start"] is not None, f"Session start is None: {ses}"
        datetime.fromisoformat(ses["start"])

        # end can be None only if tooltip mentions "<still connected>"
        if ses["end"] is not None:
            datetime.fromisoformat(ses["end"])
        else:
            assert "<still connected>" in ses["tooltip"], f"End is None but session not marked as still connected: {ses}"

    # --- Cleanup: delete all test sessions for this MAC ---
    client.delete(f"/sessions/delete?mac={test_mac}", headers=auth_headers(api_token))
