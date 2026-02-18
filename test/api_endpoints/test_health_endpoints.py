"""Tests for health check endpoint."""

import sys
import os
import pytest
from unittest.mock import patch

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
# AUTHENTICATION TESTS
# ========================================================================

def test_health_unauthorized(client):
    """Missing token should be forbidden."""
    resp = client.get("/health")
    assert resp.status_code == 403

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False


def test_health_invalid_token(client):
    """Invalid bearer token should be forbidden."""
    resp = client.get("/health", headers=auth_headers("INVALID-TOKEN"))
    assert resp.status_code == 403

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False


def test_health_valid_token(client, api_token):
    """Valid token should allow access."""
    resp = client.get("/health", headers=auth_headers(api_token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is True


# ========================================================================
# RESPONSE STRUCTURE TESTS
# ========================================================================

def test_health_response_structure(client, api_token):
    """Response should contain all required health metrics."""
    resp = client.get("/health", headers=auth_headers(api_token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert data.get("success") is True

    # Check all required fields are present
    assert "db_size_mb" in data
    assert "mem_usage_pct" in data
    assert "load_1m" in data
    assert "storage_pct" in data
    assert "cpu_temp" in data
    assert "storage_gb" in data
    assert "mem_mb" in data


def test_health_db_size_type(client, api_token):
    """db_size_mb should be a float."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    assert isinstance(data["db_size_mb"], (int, float))
    assert data["db_size_mb"] >= 0


def test_health_mem_usage_type(client, api_token):
    """mem_usage_pct should be an integer in range [0, 100]."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    mem = data["mem_usage_pct"]
    assert isinstance(mem, int)
    assert 0 <= mem <= 100 or mem == -1  # -1 on error


def test_health_load_avg_type(client, api_token):
    """load_1m should be a float."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    load = data["load_1m"]
    assert isinstance(load, (int, float))
    assert load >= -1  # -1 on error


def test_health_storage_pct_type(client, api_token):
    """storage_pct should be an integer in range [0, 100]."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    storage = data["storage_pct"]
    assert isinstance(storage, int)
    assert 0 <= storage <= 100 or storage == -1  # -1 on error


def test_health_cpu_temp_optional(client, api_token):
    """cpu_temp should be optional (int or null)."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    cpu_temp = data["cpu_temp"]
    assert cpu_temp is None or isinstance(cpu_temp, int)
    if isinstance(cpu_temp, int):
        assert cpu_temp > -100  # Reasonable temperature bounds


# ========================================================================
# METRIC CALCULATION TESTS
# ========================================================================

def test_health_db_size_realistic(client, api_token):
    """Database size should be reasonable (>0 MB in active system)."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    # In a real system with data, DB should be > 1 MB
    # Allow 0 for minimal installations without data
    assert data["db_size_mb"] >= 0
    # Sanity check: file shouldn't exceed 5GB
    assert data["db_size_mb"] < 5000


def test_health_mem_usage_reasonable(client, api_token):
    """Memory usage should be reasonable for normal operation."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    # Sanity check: should be between 0% and 100%
    if data["mem_usage_pct"] != -1:
        assert 0 <= data["mem_usage_pct"] <= 100


def test_health_storage_pct_reasonable(client, api_token):
    """Storage percentage should be reasonable."""
    resp = client.get("/health", headers=auth_headers(api_token))
    data = resp.get_json()

    # Sanity check: should be between 0% and 100%
    if data["storage_pct"] != -1:
        assert 0 <= data["storage_pct"] <= 100


# ========================================================================
# ERROR HANDLING TESTS
# ========================================================================

@patch('api_server.api_server_start.get_health_status')
def test_health_exception_handling(mock_health, client, api_token):
    """Health endpoint should handle exceptions gracefully."""
    mock_health.side_effect = Exception("Test error")

    resp = client.get("/health", headers=auth_headers(api_token))
    assert resp.status_code == 500

    data = resp.get_json()
    assert data.get("success") is False
    assert "error" in data


# ========================================================================
# METRIC INDEPENDENCE TESTS
# ========================================================================

def test_health_multiple_calls_consistency(client, api_token):
    """Multiple calls should return consistent structure."""
    for _ in range(3):
        resp = client.get("/health", headers=auth_headers(api_token))
        assert resp.status_code == 200

        data = resp.get_json()
        assert data.get("success") is True
        assert "db_size_mb" in data
        assert "mem_usage_pct" in data
        assert "load_1m" in data
        assert "storage_pct" in data
        assert "cpu_temp" in data
        assert "storage_gb" in data
        assert "mem_mb" in data


# ========================================================================
# HTTP METHOD TESTS
# ========================================================================

def test_health_post_not_allowed(client, api_token):
    """POST to /health should not be allowed."""
    resp = client.post("/health", headers=auth_headers(api_token))
    # Either 405 Method Not Allowed or 404 Not Found is acceptable
    assert resp.status_code in (404, 405)


def test_health_delete_not_allowed(client, api_token):
    """DELETE to /health should not be allowed."""
    resp = client.delete("/health", headers=auth_headers(api_token))
    # Either 405 Method Not Allowed or 404 Not Found is acceptable
    assert resp.status_code in (404, 405)


# ========================================================================
# QUERY TOKEN AUTHENTICATION TEST
# ========================================================================

def test_health_query_token_auth(client, api_token):
    """Query token should also work for authentication."""
    resp = client.get(f"/health?token={api_token}")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data.get("success") is True
