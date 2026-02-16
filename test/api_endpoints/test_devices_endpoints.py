# import pathlib
# import sqlite3
import base64
import random
# import string
# import uuid
import pytest

from helper import get_setting_value
from api_server.api_server_start import app
from db.db_helper import get_device_conditions


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


def create_dummy(client, api_token, test_mac):
    payload = {
        "createNew": True,
        "devName": "Test Device",
        "devOwner": "Unit Test",
        "devType": "Router",
        "devVendor": "TestVendor",
    }
    client.post(f"/device/{test_mac}", json=payload, headers=auth_headers(api_token))


def test_get_all_devices(client, api_token, test_mac):
    # Ensure there is at least one device
    create_dummy(client, api_token, test_mac)

    # Fetch all devices
    resp = client.get("/devices", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True
    devices = resp.json.get("devices")
    assert isinstance(devices, list)
    # Ensure our test device is in the list
    assert any(d["devMac"] == test_mac for d in devices)


def test_delete_devices_with_macs(client, api_token, test_mac):
    # First create device so it exists
    create_dummy(client, api_token, test_mac)

    client.post(f"/device/{test_mac}", json={"createNew": True}, headers=auth_headers(api_token))

    # Delete by MAC
    resp = client.delete("/devices", json={"macs": [test_mac]}, headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True


def test_delete_all_empty_macs(client, api_token):
    resp = client.delete("/devices/empty-macs", headers=auth_headers(api_token))
    assert resp.status_code == 200
    # Expect success flag in response
    assert resp.json.get("success") is True


def test_delete_unknown_devices(client, api_token):
    resp = client.delete("/devices/unknown", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True


def test_export_devices_csv(client, api_token, test_mac):
    # Create a device first
    create_dummy(client, api_token, test_mac)

    # Export devices as CSV
    resp = client.get("/devices/export/csv", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment; filename=devices.csv" in resp.headers.get("Content-disposition", "")

    # CSV should contain test_mac
    assert test_mac in resp.data.decode()


def test_export_devices_json(client, api_token, test_mac):
    # Create a device first
    create_dummy(client, api_token, test_mac)

    # Export devices as JSON
    resp = client.get("/devices/export/json", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()
    assert any(dev.get("devMac") == test_mac for dev in data["data"])


def test_export_devices_invalid_format(client, api_token):
    # Request with unsupported format
    resp = client.get("/devices/export/invalid", headers=auth_headers(api_token))
    assert resp.status_code == 400
    assert "Unsupported format" in resp.json.get("error")


def test_export_import_cycle_base64(client, api_token, test_mac):
    # 1. Create a dummy device
    create_dummy(client, api_token, test_mac)

    # 2. Export devices as CSV
    resp = client.get("/devices/export/csv", headers=auth_headers(api_token))
    assert resp.status_code == 200
    csv_data = resp.data.decode("utf-8")

    print(csv_data)

    # Ensure our dummy device is in the CSV
    assert test_mac in csv_data
    assert "Test Device" in csv_data

    # 3. Base64-encode the CSV for JSON payload
    csv_base64 = base64.b64encode(csv_data.encode("utf-8")).decode("utf-8")
    json_payload = {"content": csv_base64}

    # 4. POST to import endpoint with JSON content
    resp = client.post(
        "/devices/import",
        json=json_payload,
        headers={**auth_headers(api_token), "Content-Type": "application/json"}
    )
    assert resp.status_code == 200
    assert resp.json.get("success") is True

    # 5. Verify import results
    assert resp.json.get("inserted") >= 1
    assert resp.json.get("skipped_lines") == []


def test_devices_totals(client, api_token, test_mac):
    # 1. Create a dummy device
    create_dummy(client, api_token, test_mac)

    # 2. Call the totals endpoint
    resp = client.get("/devices/totals", headers=auth_headers(api_token))
    assert resp.status_code == 200

    # 3. Ensure the response is a JSON list
    data = resp.json
    assert isinstance(data, list)

    # 4. Dynamically get expected length
    conditions = get_device_conditions()
    expected_length = len(conditions)
    assert len(data) == expected_length

    # 5. Check that at least 1 device exists
    assert data[0] >= 1  # 'devices' count includes the dummy device


def test_devices_by_status(client, api_token, test_mac):
    # 1. Create a dummy device
    create_dummy(client, api_token, test_mac)

    # 2. Request devices by a valid status
    resp = client.get("/devices/by-status?status=my", headers=auth_headers(api_token))
    assert resp.status_code == 200
    data = resp.json
    assert isinstance(data, list)
    assert any(d["id"] == test_mac for d in data)

    # 3. Request devices with an invalid/unknown status
    resp_invalid = client.get("/devices/by-status?status=invalid_status", headers=auth_headers(api_token))
    # Strict validation now returns 422 for invalid status enum values
    assert resp_invalid.status_code == 422

    # 4. Check favorite formatting if devFavorite = 1
    # Update dummy device to favorite
    client.post(
        f"/device/{test_mac}",
        json={"devFavorite": 1},
        headers=auth_headers(api_token)
    )
    resp_fav = client.get("/devices/by-status?status=my", headers=auth_headers(api_token))
    fav_data = next((d for d in resp_fav.json if d["id"] == test_mac), None)
    assert fav_data is not None
    assert "&#9733" in fav_data["title"]


def test_delete_test_devices(client, api_token):

    # Delete by MAC
    resp = client.delete("/devices", json={"macs": ["aa:bb:cc:*"]}, headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True
