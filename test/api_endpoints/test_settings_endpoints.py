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


def test_get_setting_unauthorized(client):
    resp = client.get("/settings/API_TOKEN")  # no auth header
    assert resp.status_code == 403
    assert resp.json.get("error") == "Forbidden"


def test_get_setting_valid_key(client, api_token):
    # We know API_TOKEN exists in settings
    resp = client.get("/settings/API_TOKEN", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True
    # The value should equal the token itself
    assert resp.json.get("value") == api_token


def test_get_setting_invalid_key(client, api_token):
    resp = client.get("/settings/DOES_NOT_EXIST", headers=auth_headers(api_token))
    assert resp.status_code == 200
    assert resp.json.get("success") is True
    # Depending on implementation, might be None or ""
    assert resp.json.get("value") in (None, "")
