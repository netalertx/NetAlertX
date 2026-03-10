"""Tests for GET /languages endpoint."""

import sys
import os
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
# AUTHENTICATION TESTS
# ========================================================================

def test_languages_unauthorized(client):
    """Missing token should be forbidden."""
    resp = client.get("/languages")
    assert resp.status_code == 403

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False


def test_languages_invalid_token(client):
    """Invalid bearer token should be forbidden."""
    resp = client.get("/languages", headers=auth_headers("INVALID-TOKEN"))
    assert resp.status_code == 403

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is False


def test_languages_valid_token(client, api_token):
    """Valid token should return 200 with success=True."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert data is not None
    assert data.get("success") is True


# ========================================================================
# RESPONSE STRUCTURE TESTS
# ========================================================================

def test_languages_response_structure(client, api_token):
    """Response must contain required fields with correct types."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert data.get("success") is True
    assert isinstance(data.get("default"), str)
    assert isinstance(data.get("count"), int)
    assert isinstance(data.get("languages"), list)


def test_languages_default_is_en_us(client, api_token):
    """Default language must always be en_us."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    data = resp.get_json()
    assert data["default"] == "en_us"


def test_languages_count_matches_list(client, api_token):
    """count must equal len(languages)."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    data = resp.get_json()
    assert data["count"] == len(data["languages"])


def test_languages_entry_shape(client, api_token):
    """Each language entry must have 'code' and 'display' string fields."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    data = resp.get_json()

    for entry in data["languages"]:
        assert "code" in entry, f"Missing 'code' in {entry}"
        assert "display" in entry, f"Missing 'display' in {entry}"
        assert isinstance(entry["code"], str)
        assert isinstance(entry["display"], str)
        # code must match pattern xx_xx
        assert len(entry["code"]) == 5 and entry["code"][2] == "_", \
            f"Unexpected code format: {entry['code']}"


def test_languages_includes_en_us(client, api_token):
    """en_us must always be in the language list."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    data = resp.get_json()
    codes = [l["code"] for l in data["languages"]]
    assert "en_us" in codes


def test_languages_display_contains_code(client, api_token):
    """Each display name must embed its code in parentheses, e.g. 'English (en_us)'."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    data = resp.get_json()

    for entry in data["languages"]:
        assert f"({entry['code']})" in entry["display"], \
            f"Display '{entry['display']}' does not contain '({entry['code']})'"


def test_languages_minimum_count(client, api_token):
    """Must have at least 20 languages (the original set)."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    data = resp.get_json()
    assert data["count"] >= 20, f"Expected >=20 languages, got {data['count']}"


def test_languages_no_duplicate_codes(client, api_token):
    """Language codes must be unique."""
    resp = client.get("/languages", headers=auth_headers(api_token))
    data = resp.get_json()
    codes = [l["code"] for l in data["languages"]]
    assert len(codes) == len(set(codes)), "Duplicate language codes found"
