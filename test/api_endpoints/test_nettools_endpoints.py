import random
import pytest

from helper import get_setting_value   # noqa: E402 [flake8 lint suppression]
from api_server.api_server_start import app   # noqa: E402 [flake8 lint suppression]


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


def test_wakeonlan_device(client, api_token, test_mac):
    # 1. Ensure at least one device exists
    create_dummy(client, api_token, test_mac)

    # 2. Fetch all devices
    resp = client.get("/devices", headers=auth_headers(api_token))
    assert resp.status_code == 200
    devices = resp.json.get("devices", [])
    assert len(devices) > 0

    # 3. Pick the first device (or the test device)
    device_mac = devices[0]["devMac"]

    # 4. Call the wakeonlan endpoint
    resp = client.post(
        "/nettools/wakeonlan",
        json={"devMac": device_mac},
        headers=auth_headers(api_token)
    )

    # 5. Conditional assertions based on MAC
    if device_mac.lower() == 'internet' or device_mac == test_mac:
        # For the dummy "internet" or test MAC, expect a 400 response
        assert resp.status_code in [400, 200]
    else:
        # For any other MAC, expect a 200 response
        assert resp.status_code == 200
        data = resp.json
        assert data.get("success") is True
        assert "WOL packet sent" in data.get("message", "")


def test_speedtest_endpoint(client, api_token):
    # 1. Call the speedtest endpoint
    resp = client.get("/nettools/speedtest", headers=auth_headers(api_token))

    # 2. Assertions
    if resp.status_code == 403:
        # Unauthorized access
        data = resp.json
        assert "error" in data
        assert data["error"] == "Forbidden"
    else:
        # Expect success
        assert resp.status_code == 200
        data = resp.json
        assert data.get("success") is True
        assert "output" in data
        assert isinstance(data["output"], list)
        # Optionally check that output lines are strings
        assert all(isinstance(line, str) for line in data["output"])


def test_traceroute_device(client, api_token, test_mac):
    # 1. Ensure at least one device exists
    create_dummy(client, api_token, test_mac)

    # 2. Fetch all devices
    resp = client.get("/devices", headers=auth_headers(api_token))
    assert resp.status_code == 200
    devices = resp.json.get("devices", [])
    assert len(devices) > 0

    # 3. Pick the first device
    device_ip = devices[0].get("devLastIP")
    if not device_ip:
        device_ip = "192.168.1.1"

    # 4. Call the traceroute endpoint
    resp = client.post(
        "/nettools/traceroute",
        json={"devLastIP": device_ip},
        headers=auth_headers(api_token)
    )

    # 5. Assertions

    # Expect 200 and valid traceroute output
    assert resp.status_code == 200
    data = resp.json
    assert data.get("success") is True
    assert "output" in data
    assert isinstance(data["output"], list)
    assert all(isinstance(line, str) for line in data["output"])


@pytest.mark.parametrize("ip,expected_status", [
    ("8.8.8.8", 200),
    ("256.256.256.256", 422),  # Invalid IP -> 422
    ("", 422),                  # Missing IP -> 422
])
def test_nslookup_endpoint(client, api_token, ip, expected_status):
    payload = {"devLastIP": ip} if ip else {}
    resp = client.post("/nettools/nslookup", json=payload, headers=auth_headers(api_token))

    assert resp.status_code == expected_status
    data = resp.json

    if expected_status == 200:
        assert data.get("success") is True
        assert isinstance(data["output"], list)
        assert all(isinstance(line, str) for line in data["output"])
    else:
        assert data.get("success") is False
        assert "error" in data


@pytest.mark.feature_complete
@pytest.mark.parametrize("ip,mode,expected_status", [
    ("127.0.0.1", "fast", 200),
    ("127.0.0.1", "normal", 200),
    ("127.0.0.1", "detail", 200),
    ("127.0.0.1", "skipdiscovery", 200),
    ("127.0.0.1", "invalidmode", 422),
    ("999.999.999.999", "fast", 422),
])
def test_nmap_endpoint(client, api_token, ip, mode, expected_status):
    payload = {"scan": ip, "mode": mode}
    resp = client.post("/nettools/nmap", json=payload, headers=auth_headers(api_token))

    assert resp.status_code == expected_status
    data = resp.json

    if expected_status == 200:
        assert data.get("success") is True
        assert data.get("mode") == mode
        assert data.get("ip") == ip
        assert isinstance(data["output"], list)
        assert all(isinstance(line, str) for line in data["output"])
    else:
        assert data.get("success") is False
        assert "error" in data


def test_nslookup_unauthorized(client):
    # No auth headers
    resp = client.post("/nettools/nslookup", json={"devLastIP": "8.8.8.8"})
    assert resp.status_code == 403
    data = resp.json
    assert data.get("success") is False
    assert data.get("error") == "Forbidden"


def test_nmap_unauthorized(client):
    # No auth headers
    resp = client.post("/nettools/nmap", json={"scan": "127.0.0.1", "mode": "fast"})
    assert resp.status_code == 403
    data = resp.json
    assert data.get("success") is False
    assert data.get("error") == "Forbidden"


def test_internet_info_endpoint(client, api_token):
    resp = client.get("/nettools/internetinfo", headers=auth_headers(api_token))
    data = resp.json

    if resp.status_code == 200:
        assert data.get("success") is True
        assert isinstance(data.get("output"), dict)
        assert len(data["output"]) > 0              # ensure output is not empty
    else:
        # Handle errors, e.g., curl failure
        assert data.get("success") is False
        assert "error" in data
        assert "details" in data


def test_interfaces_endpoint(client, api_token):
    # Call the /nettools/interfaces endpoint
    resp = client.get("/nettools/interfaces", headers=auth_headers(api_token))
    data = resp.json

    # Assertions
    if resp.status_code == 200:
        assert data.get("success") is True
        assert "interfaces" in data
        interfaces = data["interfaces"]
        assert isinstance(interfaces, dict)
        for if_name, iface in interfaces.items():
            assert "name" in iface
            assert "short" in iface
            assert "type" in iface
            assert "state" in iface
            assert "mtu" in iface
            assert "mac" in iface
            assert "ipv4" in iface and isinstance(iface["ipv4"], list)
            assert "ipv6" in iface and isinstance(iface["ipv6"], list)
            assert "rx_bytes" in iface
            assert "tx_bytes" in iface
    else:
        # Handle failure
        assert data.get("success") is False
        assert "error" in data
        assert "details" in data
