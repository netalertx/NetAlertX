"""Tests for /plugins/stats endpoint."""

import sys
import os
import pytest

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value  # noqa: E402
from api_server.api_server_start import app  # noqa: E402


@pytest.fixture(scope="session")
def api_token():
    return get_setting_value("API_TOKEN")


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_plugin_stats_unauthorized(client):
    """Missing token should be forbidden."""
    resp = client.get("/plugins/stats")
    assert resp.status_code == 403
    assert resp.get_json().get("success") is False


def test_plugin_stats_success(client, api_token):
    """Valid token returns success with data array."""
    resp = client.get("/plugins/stats", headers=auth_headers(api_token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert data.get("success") is True
    assert isinstance(data.get("data"), list)


def test_plugin_stats_entry_structure(client, api_token):
    """Each entry has tableName, plugin, cnt fields."""
    resp = client.get("/plugins/stats", headers=auth_headers(api_token))
    data = resp.get_json()

    for entry in data["data"]:
        assert "tableName" in entry
        assert "plugin" in entry
        assert "cnt" in entry
        assert entry["tableName"] in ("objects", "events", "history")
        assert isinstance(entry["cnt"], int)
        assert entry["cnt"] >= 0


def test_plugin_stats_with_foreignkey(client, api_token):
    """foreignKey param filters results and returns valid structure."""
    resp = client.get(
        "/plugins/stats?foreignKey=00:00:00:00:00:00",
        headers=auth_headers(api_token),
    )
    assert resp.status_code == 200

    data = resp.get_json()
    assert data.get("success") is True
    assert isinstance(data.get("data"), list)
    # With a non-existent MAC, data should be empty
    assert len(data["data"]) == 0
