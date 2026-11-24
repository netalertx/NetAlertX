# tests/test_auth.py

import sys
import os
import hashlib
import pytest
from unittest.mock import patch

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value  # noqa: E402
from api_server.api_server_start import (  # noqa: E402
    app,
    _failed_logins,
    _failed_logins_lock,
    _is_rate_limited,
    _record_failed_login,
    _clear_failed_logins,
    _MAX_FAILED_ATTEMPTS,
    _LOCKOUT_WINDOW_SECONDS,
)


@pytest.fixture(autouse=True)
def reset_login_rate_limiter():
    """Ensure rate-limiter state does not leak between tests."""
    with _failed_logins_lock:
        _failed_logins.clear()
    yield
    with _failed_logins_lock:
        _failed_logins.clear()


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


def test_login_valid_local_credentials(client, api_token):
    """POST /api/auth/login with correct local password returns 200."""
    with patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.get_setting_value", return_value=False):
        resp = client.post(
            "/api/auth/login",
            headers=auth_headers(api_token),
            json={"username": "admin", "password": _DEFAULT_PW},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("success") is True
    assert data.get("provider") == "local"
    assert data.get("username") == "admin"


def test_login_wrong_local_password(client, api_token):
    """POST /api/auth/login with incorrect password returns 401."""
    with patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.get_setting_value", return_value=False):
        resp = client.post(
            "/api/auth/login",
            headers=auth_headers(api_token),
            json={"username": "admin", "password": "totally_wrong"},
        )
    assert resp.status_code == 401
    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False


def test_login_missing_password_field(client, api_token):
    """POST /api/auth/login without password returns 422 validation error."""
    resp = client.post("/api/auth/login", headers=auth_headers(api_token), json={"username": "admin"})
    assert resp.status_code == 422


def test_login_missing_username_field(client, api_token):
    """POST /api/auth/login without username defaults to admin."""
    with patch("auth.manager.LdapProvider._read_config", return_value={"enabled": False}), \
         patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.get_setting_value", return_value=False):
        resp = client.post("/api/auth/login", headers=auth_headers(api_token), json={"password": _DEFAULT_PW})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("username") == "admin"


def test_login_empty_body(client, api_token):
    """POST /api/auth/login with empty JSON object returns 422."""
    resp = client.post("/api/auth/login", headers=auth_headers(api_token), json={})
    assert resp.status_code == 422


def test_login_no_json_content_type(client, api_token):
    """POST /api/auth/login with wrong content-type returns 415."""
    resp = client.post(
        "/api/auth/login",
        headers=auth_headers(api_token),
        data="username=admin&password=123456",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 415


def test_login_endpoint_requires_post(client):
    """GET /api/auth/login should return 405 because the route is POST-only."""
    resp = client.get("/api/auth/login")
    assert resp.status_code == 405


# -------------------------
# RATE LIMITING TESTS
# -------------------------

def test_rate_limiter_unit_threshold_and_clear():
    """_record_failed_login triggers _is_rate_limited at threshold and _clear_failed_logins resets it."""
    ip = "198.51.100.10"
    assert _is_rate_limited(ip) is False
    for _ in range(_MAX_FAILED_ATTEMPTS - 1):
        _record_failed_login(ip)
        assert _is_rate_limited(ip) is False

    _record_failed_login(ip)
    assert _is_rate_limited(ip) is True

    _clear_failed_logins(ip)
    assert _is_rate_limited(ip) is False


def test_rate_limiter_lockout_window_expiry():
    """Failed attempts older than _LOCKOUT_WINDOW_SECONDS expire and lift the lockout."""
    ip = "198.51.100.11"
    base_time = 1000.0
    with patch("api_server.api_server_start.time.monotonic", return_value=base_time):
        for _ in range(_MAX_FAILED_ATTEMPTS):
            _record_failed_login(ip)
        assert _is_rate_limited(ip) is True

    # Just before window expiry: still locked out
    with patch("api_server.api_server_start.time.monotonic", return_value=base_time + _LOCKOUT_WINDOW_SECONDS - 1):
        assert _is_rate_limited(ip) is True

    # At/after window expiry: lockout cleared
    with patch("api_server.api_server_start.time.monotonic", return_value=base_time + _LOCKOUT_WINDOW_SECONDS + 1):
        assert _is_rate_limited(ip) is False


def test_login_endpoint_returns_429_after_max_failed_attempts(client, api_token):
    """POST /api/auth/login returns 429 after _MAX_FAILED_ATTEMPTS failed logins and recovers after window expiry."""
    base_time = 2000.0
    headers = {**auth_headers(api_token), "X-Forwarded-For": "198.51.100.20"}

    with patch("api_server.api_server_start.time.monotonic", return_value=base_time), \
         patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.LdapProvider._read_config", return_value={"enabled": False}), \
         patch("auth.manager.get_setting_value", return_value=False):
        for _ in range(_MAX_FAILED_ATTEMPTS):
            resp = client.post(
                "/api/auth/login",
                headers=headers,
                json={"username": "admin", "password": "wrong_password"},
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )
            assert resp.status_code == 401

        # Next attempt must be rejected with 429 even with valid credentials
        resp_429 = client.post(
            "/api/auth/login",
            headers=headers,
            json={"username": "admin", "password": _DEFAULT_PW},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert resp_429.status_code == 429
        data = resp_429.get_json()
        assert data is not None
        assert data.get("success") is False
        assert "too many" in data.get("error", "").lower()

    # After lockout window expires, valid login succeeds
    with patch("api_server.api_server_start.time.monotonic", return_value=base_time + _LOCKOUT_WINDOW_SECONDS + 1), \
         patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.LdapProvider._read_config", return_value={"enabled": False}), \
         patch("auth.manager.get_setting_value", return_value=False):
        resp_ok = client.post(
            "/api/auth/login",
            headers=headers,
            json={"username": "admin", "password": _DEFAULT_PW},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert resp_ok.status_code == 200


def test_login_rate_limiter_ignores_spoofed_xff_from_untrusted_peer(client, api_token):
    """X-Forwarded-For is ignored when REMOTE_ADDR is not the trusted local PHP relay (127.0.0.1 / ::1)."""
    with patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.LdapProvider._read_config", return_value={"enabled": False}), \
         patch("auth.manager.get_setting_value", return_value=False):
        for idx in range(_MAX_FAILED_ATTEMPTS):
            resp = client.post(
                "/api/auth/login",
                headers={**auth_headers(api_token), "X-Forwarded-For": f"10.0.0.{idx + 1}"},
                json={"username": "admin", "password": "wrong_password"},
                environ_base={"REMOTE_ADDR": "203.0.113.50"},
            )
            assert resp.status_code == 401

        # Spoofing yet another X-Forwarded-For from the same untrusted peer must still be rate-limited
        resp_429 = client.post(
            "/api/auth/login",
            headers={**auth_headers(api_token), "X-Forwarded-For": "10.0.0.99"},
            json={"username": "admin", "password": _DEFAULT_PW},
            environ_base={"REMOTE_ADDR": "203.0.113.50"},
        )
        assert resp_429.status_code == 429


def test_login_rate_limiter_honors_xff_from_trusted_local_relay(client, api_token):
    """X-Forwarded-For is honored when REMOTE_ADDR is 127.0.0.1 so distinct clients have separate buckets."""
    with patch("auth.local_provider.get_setting_value", return_value=_DEFAULT_PW_HASH), \
         patch("auth.manager.LdapProvider._read_config", return_value={"enabled": False}), \
         patch("auth.manager.get_setting_value", return_value=False):
        for _ in range(_MAX_FAILED_ATTEMPTS):
            resp = client.post(
                "/api/auth/login",
                headers={**auth_headers(api_token), "X-Forwarded-For": "198.51.100.30"},
                json={"username": "admin", "password": "wrong_password"},
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )
            assert resp.status_code == 401

        # Different client IP relayed via 127.0.0.1 must NOT be rate-limited
        resp_other = client.post(
            "/api/auth/login",
            headers={**auth_headers(api_token), "X-Forwarded-For": "198.51.100.31"},
            json={"username": "admin", "password": _DEFAULT_PW},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert resp_other.status_code == 200

