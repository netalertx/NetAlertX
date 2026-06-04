"""Tests for the /sync POST and GET endpoints.

Covers:
  - Authentication enforcement (403 on missing/invalid token)
  - Content-type enforcement on POST (regression for data= vs json= bug)
  - Happy-path POST returns 200
  - GET auth enforcement
"""

import os
import sys
import pytest

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value  # noqa: E402
from api_server.api_server_start import app  # noqa: E402


@pytest.fixture(scope="session")
def api_token():
    """Load API token from system settings."""
    return get_setting_value("API_TOKEN")


@pytest.fixture
def client():
    """Flask test client."""
    with app.test_client() as client:
        yield client


def auth_headers(token):
    """Helper to construct Authorization header."""
    return {"Authorization": f"Bearer {token}"}


# ========================================================================
# POST /sync - authentication
# ========================================================================

def test_sync_post_no_token_is_forbidden(client):
    resp = client.post("/sync")
    assert resp.status_code == 403


def test_sync_post_invalid_token_is_forbidden(client):
    resp = client.post("/sync", headers=auth_headers("INVALID-TOKEN"))
    assert resp.status_code == 403


# ========================================================================
# POST /sync - content-type enforcement
# Regression: node used to send data= (form-encoded); validation rejects it.
# ========================================================================

def test_sync_post_form_encoded_returns_415(client, api_token):
    """Form-encoded body must be rejected with 415 Unsupported Media Type.

    Regression test: before the fix sync.py used ``requests.post(data=…)``
    which sends application/x-www-form-urlencoded. The validate_request
    middleware requires application/json — this test ensures that contract
    is enforced so the node can never silently regress to form encoding.
    """
    resp = client.post(
        "/sync",
        headers=auth_headers(api_token),
        data={"data": "payload", "plugin": "ARPSCAN", "node_name": "Node1"},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 415


def test_sync_post_json_body_is_accepted(client, api_token, tmp_path, monkeypatch):
    """JSON body must pass validation and return 200."""
    plugins_dir = tmp_path / "log" / "plugins"
    plugins_dir.mkdir(parents=True)

    monkeypatch.setenv("NETALERTX_PLUGINS_LOG", str(plugins_dir))
    resp = client.post(
        "/sync",
        headers=auth_headers(api_token),
        json={"data": "test_payload", "plugin": "TESTPLUGIN", "node_name": "TestNode"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "message" in data


def test_sync_post_json_body_writes_encoded_file(client, api_token, tmp_path, monkeypatch):
    """A successful POST must persist an encoded file in the plugins log dir."""
    plugins_dir = tmp_path / "log" / "plugins"
    plugins_dir.mkdir(parents=True)

    monkeypatch.setenv("NETALERTX_PLUGINS_LOG", str(plugins_dir))
    client.post(
        "/sync",
        headers=auth_headers(api_token),
        json={"data": "encrypted_blob", "plugin": "ARPSCAN", "node_name": "Node1"},
    )

    written = list(plugins_dir.glob("last_result.ARPSCAN.encoded.Node1.*.log"))
    assert len(written) == 1
    assert written[0].read_text() == "encrypted_blob"


# ========================================================================
# GET /sync - authentication
# ========================================================================

def test_sync_get_no_token_is_forbidden(client):
    resp = client.get("/sync")
    assert resp.status_code == 403


def test_sync_get_invalid_token_is_forbidden(client):
    resp = client.get("/sync", headers=auth_headers("INVALID-TOKEN"))
    assert resp.status_code == 403
