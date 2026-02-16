import pytest
from helper import get_setting_value
from api_server.api_server_start import app
from models.device_instance import DeviceInstance


@pytest.fixture(scope="session")
def api_token():
    return get_setting_value("API_TOKEN")


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_mac_norm():
    # Now normalized to lowercase
    return "aa:bb:cc:dd:ee:ff"


@pytest.fixture
def test_parent_mac_input():
    # Input with mixed/upper case to test the trigger/normalization
    return "AA:BB:CC:DD:EE:00"


@pytest.fixture
def test_parent_mac_norm():
    # Expected result in DB (lowercase)
    return "aa:bb:cc:dd:ee:00"


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_update_normalization(client, api_token, test_mac_norm, test_parent_mac_input, test_parent_mac_norm):
    # 1. Create a device
    create_payload = {
        "createNew": True,
        "devName": "Normalization Test Device",
        "devOwner": "Unit Test",
    }
    # Pass the lowercase mac
    resp = client.post(f"/device/{test_mac_norm}", json=create_payload, headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True

    # 2. Update the device sending UPPERCASE parent MAC
    # To verify the triggers/logic flip it to lowercase
    update_payload = {
        "devParentMAC": test_parent_mac_input,
        "devName": "Updated Device"
    }

    resp = client.post(f"/device/{test_mac_norm}", json=update_payload, headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True

    # 3. Verify in DB that devParentMAC is LOWERCASE
    device_handler = DeviceInstance()
    # Query using lowercase mac
    device = device_handler.getDeviceData(test_mac_norm)

    assert device is not None
    assert device["devName"] == "Updated Device"

    # CRITICAL CHECKS:
    # It must be lowercase now
    assert device["devParentMAC"] == test_parent_mac_norm
    # It should NOT be the uppercase input we sent
    assert device["devParentMAC"] != test_parent_mac_input

    # Cleanup
    device_handler.deleteDeviceByMAC(test_mac_norm)