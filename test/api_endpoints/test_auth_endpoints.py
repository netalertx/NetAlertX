# tests/test_auth.py

import sys
import os
import hashlib
import pytest
from unittest.mock import patch

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value  # noqa: E402
from api_server.api_server_start import app  # noqa: E402


@pytest.fixture(scope="session")
def api_token():
    """Load API token from system settings (same as other tests)."""
    return get_setting_value("API_TOKEN")


@pytest.fixture
def client():
    """Flask test client."""
    with app.test_client() as client:
        yield client


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# -------------------------
# AUTH ENDPOINT TESTS
# -------------------------

def test_auth_ok(client, api_token):
    """Valid token should allow access."""
    resp = client.get("/auth", headers=auth_headers(api_token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is True
    assert "successful" in data.get("message", "").lower()


def test_auth_missing_token(client):
    """Missing token should be forbidden."""
    resp = client.get("/auth")
    assert resp.status_code == 403

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False
    assert "not authorized" in data.get("message", "").lower()


def test_auth_invalid_token(client):
    """Invalid bearer token should be forbidden."""
    resp = client.get("/auth", headers=auth_headers("INVALID-TOKEN"))
    assert resp.status_code == 403

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False
    assert "not authorized" in data.get("message", "").lower()


# -------------------------
# LOGIN ENDPOINT TESTS
# -------------------------

_DEFAULT_PW = "123456"
_DEFAULT_PW_HASH = hashlib.sha256(_DEFAULT_PW.encode()).hexdigest()


def test_login_valid_local_credentials(client):
    """POST /api/auth/login with correct local password returns 200."""
    with patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.get_setting_value", return_value=False):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": _DEFAULT_PW},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("success") is True
    assert data.get("provider") == "local"
    assert data.get("username") == "admin"


def test_login_wrong_local_password(client):
    """POST /api/auth/login with incorrect password returns 401."""
    with patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.get_setting_value", return_value=False):
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "totally_wrong"},
        )
    assert resp.status_code == 401
    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False


def test_login_missing_password_field(client):
    """POST /api/auth/login without password returns 422 validation error."""
    resp = client.post("/api/auth/login", json={"username": "admin"})
    assert resp.status_code == 422


def test_login_missing_username_field(client):
    """POST /api/auth/login without username returns 422 validation error."""
    resp = client.post("/api/auth/login", json={"password": "secret"})
    assert resp.status_code == 422


def test_login_empty_body(client):
    """POST /api/auth/login with empty JSON object returns 422."""
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 422


def test_login_no_json_content_type(client):
    """POST /api/auth/login with wrong content-type returns 415."""
    resp = client.post(
        "/api/auth/login",
        data="username=admin&password=123456",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 415


def test_login_endpoint_requires_post(client):
    """GET /api/auth/login should return 405 because the route is POST-only."""
    resp = client.get("/api/auth/login")
    assert resp.status_code == 405

