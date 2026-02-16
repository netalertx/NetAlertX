import sys
import random
import os
import pytest

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
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


def test_graphql_debug_get(client):
    """GET /graphql should return the debug string"""
    resp = client.get("/graphql")
    assert resp.status_code == 200
    assert resp.data.decode() == "NetAlertX GraphQL server running."


def test_graphql_post_unauthorized(client):
    """POST /graphql without token should return 403"""
    query = {"query": "{ devices { devName devMac } }"}
    resp = client.post("/graphql", json=query)
    assert resp.status_code == 403
    # Check either error field or message field for the unauthorized text
    error_text = resp.json.get("error", "") or resp.json.get("message", "")
    assert "Unauthorized" in error_text or "Forbidden" in error_text


def test_graphql_post_devices(client, api_token):
    """POST /graphql with a valid token should return device data"""
    query = {
        "query": """
        {
            devices {
                devices {
                    devGUID
                    devGroup
                    devIsRandomMac
                    devParentChildrenCount
                }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200

    body = resp.get_json()

    # GraphQL spec: response always under "data"
    assert "data" in body
    data = body["data"]

    assert "devices" in data
    assert isinstance(data["devices"]["devices"], list)
    assert isinstance(data["devices"]["count"], int)


def test_graphql_post_settings(client, api_token):
    """POST /graphql should return settings data"""
    query = {
        "query": """
        {
            settings {
                settings { setKey setValue setGroup }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    data = resp.json.get("data", {})
    assert "settings" in data
    assert isinstance(data["settings"]["settings"], list)
