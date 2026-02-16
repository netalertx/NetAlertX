import sys
import os
import pytest
import random
from datetime import timedelta

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
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


def create_event(client, api_token, mac, event="UnitTest Event", days_old=None):
    payload = {"ip": "0.0.0.0", "event_type": event}

    # Calculate the event_time if days_old is given
    if days_old is not None:
        event_time = timeNowUTC(as_string=False) - timedelta(days=days_old)
        # ISO 8601 string
        payload["event_time"] = event_time.isoformat()

    return client.post(f"/events/create/{mac}", json=payload, headers=auth_headers(api_token))


def list_events(client, api_token, mac=None):
    url = "/events" if mac is None else f"/events?mac={mac}"
    return client.get(url, headers=auth_headers(api_token))


def test_create_event(client, api_token, test_mac):
    # create event
    resp = create_event(client, api_token, test_mac)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("success") is True

    # confirm event exists
    resp = list_events(client, api_token, test_mac)
    assert resp.status_code == 200
    events = resp.get_json().get("events", [])
    assert any(ev.get("eve_MAC") == test_mac for ev in events)


def test_delete_events_for_mac(client, api_token, test_mac):
    # create event
    resp = create_event(client, api_token, test_mac)
    assert resp.status_code == 200

    # confirm exists
    resp = list_events(client, api_token, test_mac)
    assert resp.status_code == 200
    events = resp.json.get("events", [])
    assert any(ev["eve_MAC"] == test_mac for ev in events)

    # delete
    resp = client.delete(f"/events/{test_mac}", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True

    # confirm deleted
    resp = list_events(client, api_token, test_mac)
    assert resp.status_code == 200
    assert len(resp.json.get("events", [])) == 0


def test_get_events_totals(client, api_token):
    # 1. Request totals with default period
    resp = client.get(
        "/sessions/totals",
        headers=auth_headers(api_token)
    )
    assert resp.status_code == 200

    data = resp.json
    assert isinstance(data, list)
    # Expecting 6 counts: all_events, sessions, missing, voided, new, down
    assert len(data) == 6
    for count in data:
        assert isinstance(count, int)  # each should be a number

    # 2. Request totals with custom period
    resp_month = client.get(
        "/sessions/totals?period=1 month",
        headers=auth_headers(api_token)
    )
    assert resp_month.status_code == 200
    data_month = resp_month.json
    assert isinstance(data_month, list)
    assert len(data_month) == 6


def test_delete_all_events(client, api_token, test_mac):
    # create two events
    create_event(client, api_token, test_mac)
    create_event(client, api_token, "ff:ff:ff:ff:ff:ff")

    resp = list_events(client, api_token)
    # At least the two we created should be present
    assert len(resp.json.get("events", [])) >= 2

    # delete all
    resp = client.delete("/events", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True

    # confirm no events
    resp = list_events(client, api_token)
    assert len(resp.json.get("events", [])) == 0


def test_delete_events_dynamic_days(client, api_token, test_mac):
    # Determine initial count so test doesn't rely on preexisting events
    before = list_events(client, api_token, test_mac)
    initial_events = before.json.get("events", [])
    initial_count = len(initial_events)

    # Count pre-existing events younger than 30 days for test_mac
    # These will remain after delete operation
    from datetime import datetime
    thirty_days_ago = timeNowUTC(as_string=False) - timedelta(days=30)
    initial_younger_count = 0
    for ev in initial_events:
        if ev.get("eve_MAC") == test_mac and ev.get("eve_DateTime"):
            try:
                # Parse event datetime (handle ISO format)
                ev_time_str = ev["eve_DateTime"]
                # Try parsing with timezone info
                try:
                    ev_time = datetime.fromisoformat(ev_time_str.replace("Z", "+00:00"))
                except ValueError:
                    # Fallback for formats without timezone
                    ev_time = datetime.fromisoformat(ev_time_str)
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=thirty_days_ago.tzinfo)
                if ev_time > thirty_days_ago:
                    initial_younger_count += 1
            except (ValueError, TypeError):
                pass  # Skip events with unparseable dates

    # create old + new events
    create_event(client, api_token, test_mac, days_old=40)  # should be deleted
    create_event(client, api_token, test_mac, days_old=5)   # should remain

    resp = list_events(client, api_token, test_mac)
    assert len(resp.json.get("events", [])) == initial_count + 2

    # delete events older than 30 days
    resp = client.delete("/events/30", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True
    assert "Deleted events older than 30 days" in resp.json.get("message", "")

    # confirm only recent events remain (pre-existing younger + newly created 5-day-old)
    resp = list_events(client, api_token, test_mac)
    events = resp.get_json().get("events", [])
    mac_events = [ev for ev in events if ev.get("eve_MAC") == test_mac]
    expected_remaining = initial_younger_count + 1  # 1 for the 5-day-old event we created
    assert len(mac_events) == expected_remaining
