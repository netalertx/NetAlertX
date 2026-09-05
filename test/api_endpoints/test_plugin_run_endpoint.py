"""Tests for /plugin/<prefix>/run endpoint."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

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


def test_run_plugin_unauthorized(client):
    """Missing token should be forbidden."""
    resp = client.post("/plugin/ARPSCAN/run")
    assert resp.status_code == 403
    assert resp.get_json().get("success") is False


@patch("api_server.api_server_start.UserEventsQueueInstance")
def test_run_plugin_success(mock_queue_class, client, api_token):
    """A known, loaded plugin prefix queues a run event."""
    mock_queue = MagicMock()
    mock_queue_class.return_value = mock_queue

    loaded_plugins = get_setting_value("LOADED_PLUGINS")
    prefix = loaded_plugins[0]

    resp = client.post(f"/plugin/{prefix}/run", headers=auth_headers(api_token))

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    mock_queue.add_event.assert_called_once()
    call_args = mock_queue.add_event.call_args[0]
    assert f"run|{prefix}" in call_args[0]


@patch("api_server.api_server_start.UserEventsQueueInstance")
def test_run_plugin_invalid_prefix(mock_queue_class, client, api_token):
    """An unknown plugin prefix is rejected before touching the queue."""
    mock_queue = MagicMock()
    mock_queue_class.return_value = mock_queue

    resp = client.post("/plugin/NOT_A_REAL_PLUGIN/run", headers=auth_headers(api_token))

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    mock_queue.add_event.assert_not_called()
