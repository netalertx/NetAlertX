import sys
# import pathlib
# import sqlite3
import random
# import string
# import uuid
import os
import pytest

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
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
    resp = client.post(
        f"/device/{test_mac}", json=payload, headers=auth_headers(api_token)
    )
    assert resp.status_code == 200
    assert resp.json.get("success") is True


def test_get_device(client, api_token, test_mac):
    # First create it
    client.post(
        f"/device/{test_mac}", json={"createNew": True}, headers=auth_headers(api_token)
    )
    # Then retrieve it
    resp = client.get(f"/device/{test_mac}", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("devMac") == test_mac


def test_reset_device_props(client, api_token, test_mac):
    client.post(
        f"/device/{test_mac}", json={"createNew": True}, headers=auth_headers(api_token)
    )
    resp = client.post(
        f"/device/{test_mac}/reset-props", json={}, headers=auth_headers(api_token)
    )
    assert resp.status_code == 200
    assert resp.json.get("success") is True


def test_delete_device_events(client, api_token, test_mac):
    client.post(
        f"/device/{test_mac}", json={"createNew": True}, headers=auth_headers(api_token)
    )
    resp = client.delete(
        f"/device/{test_mac}/events/delete", headers=auth_headers(api_token)
    )
    assert resp.status_code == 200
    assert resp.json.get("success") is True


def test_delete_device(client, api_token, test_mac):
    client.post(
        f"/device/{test_mac}", json={"createNew": True}, headers=auth_headers(api_token)
    )
    resp = client.delete(f"/device/{test_mac}/delete", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True


def test_copy_device(client, api_token, test_mac):
    # Step 1: Create the source device
    payload = {"createNew": True}
    resp = client.post(
        f"/device/{test_mac}", json=payload, headers=auth_headers(api_token)
    )
    assert resp.status_code == 200

    # Step 2: Generate a target MAC
    target_mac = "aa:bb:cc:" + ":".join(
        f"{random.randint(0, 255):02X}" for _ in range(3)
    )

    # Step 3: Copy device
    copy_payload = {"macFrom": test_mac, "macTo": target_mac}
    resp = client.post(
        "/device/copy", json=copy_payload, headers=auth_headers(api_token)
    )
    assert resp.status_code == 200

    # Step 4: Verify new device exists
    resp = client.get(f"/device/{target_mac}", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("devMac") == target_mac

    # Cleanup: delete both devices
    client.delete(f"/device/{test_mac}/delete", headers=auth_headers(api_token))
    client.delete(f"/device/{target_mac}/delete", headers=auth_headers(api_token))


def test_update_device_column(client, api_token, test_mac):
    # First, create the device
    client.post(
        f"/device/{test_mac}",
        json={"createNew": True},
        headers=auth_headers(api_token),
    )

    # Update its parent MAC
    resp = client.post(
        f"/device/{test_mac}/update-column",
        json={"columnName": "devParentMAC", "columnValue": "internet"},
        headers=auth_headers(api_token),
    )

    assert resp.status_code == 200
    assert resp.json.get("success") is True

    # Try updating a non-existent device
    resp_missing = client.post(
        "/device/11:22:33:44:55:66/update-column",
        json={"columnName": "devParentMAC", "columnValue": "internet"},
        headers=auth_headers(api_token),
    )

    assert resp_missing.status_code == 404
    assert resp_missing.json.get("success") is False
