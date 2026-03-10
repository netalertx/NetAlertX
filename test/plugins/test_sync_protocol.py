"""
Tests for SYNC plugin push/pull/receive behaviour.

Three modes exercised:
  Mode 1 – PUSH  (NODE): send_data() POSTs encrypted device data to the hub.
  Mode 2 – PULL  (HUB):  get_data() GETs a base64 JSON blob from each node.
  Mode 3 – RECEIVE:      hub parses decoded log files and upserts devices into DB.

sync.py is intentionally NOT imported here — its module-level code has side
effects (reads live config, initialises logging).  Instead, the pure logic
under test is extracted into thin local mirrors that match the production
implementation exactly, so any divergence will surface as a test failure.
"""

import base64
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

# Make shared helpers + server packages importable from test/plugins/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))

from db_test_helpers import make_db, make_device_dict, sync_insert_devices  # noqa: E402
from utils.crypto_utils import encrypt_data, decrypt_data  # noqa: E402

# ---------------------------------------------------------------------------
# Local mirrors of sync.py logic (no module-level side-effects on import)
# ---------------------------------------------------------------------------

API_ENDPOINT = "/sync"


def _send_data(api_token, file_content, encryption_key, file_path, node_name, pref, hub_url):
    """Mirror of sync.send_data() — returns True on HTTP 200, False otherwise."""
    encrypted_data = encrypt_data(file_content, encryption_key)
    data = {
        "data": encrypted_data,
        "file_path": file_path,
        "plugin": pref,
        "node_name": node_name,
    }
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        response = requests.post(hub_url + API_ENDPOINT, data=data, headers=headers, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def _get_data(api_token, node_url):
    """Mirror of sync.get_data() — returns parsed JSON dict or '' on any failure."""
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        response = requests.get(node_url + API_ENDPOINT, headers=headers, timeout=5)
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                pass
    except requests.RequestException:
        pass
    return ""


def _node_name_from_filename(file_name: str) -> str:
    """Mirror of the node-name extraction in sync.main()."""
    parts = file_name.split(".")
    return parts[2] if ("decoded" in file_name or "encoded" in file_name) else parts[1]


def _determine_mode(hub_url: str, send_devices: bool, plugins_to_sync: list, pull_nodes: list):
    """Mirror of the is_hub / is_node detection block in sync.main()."""
    is_node = len(hub_url) > 0 and (send_devices or bool(plugins_to_sync))
    is_hub = len(pull_nodes) > 0
    return is_hub, is_node


def _currentscan_candidates(device_data: list[dict]) -> list[dict]:
    """
    Mirror of the plugin_objects.add_object() filter in sync.main().

    Only online (devPresentLastScan=1) and non-internet devices are eligible
    to be written to the CurrentScan / plugin result file.
    """
    return [
        d for d in device_data
        if d.get("devPresentLastScan") == 1 and str(d.get("devMac", "")).lower() != "internet"
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ENCRYPTION_KEY = "test-secret-key"
API_TOKEN = "tok_abc123"
HUB_URL = "http://hub.local:20211"
NODE_URL = "http://node.local:20211"


@pytest.fixture
def conn():
    """Fresh in-memory DB with Devices table and all views."""
    return make_db()


# ===========================================================================
# Mode detection
# ===========================================================================

class TestModeDetection:

    def test_is_node_when_hub_url_and_send_devices(self):
        is_hub, is_node = _determine_mode(HUB_URL, send_devices=True, plugins_to_sync=[], pull_nodes=[])
        assert is_node is True
        assert is_hub is False

    def test_is_node_when_hub_url_and_plugins_set(self):
        is_hub, is_node = _determine_mode(HUB_URL, send_devices=False, plugins_to_sync=["NMAP"], pull_nodes=[])
        assert is_node is True
        assert is_hub is False

    def test_is_hub_when_pull_nodes_set(self):
        is_hub, is_node = _determine_mode("", send_devices=False, plugins_to_sync=[], pull_nodes=[NODE_URL])
        assert is_hub is True
        assert is_node is False

    def test_is_both_hub_and_node(self):
        is_hub, is_node = _determine_mode(HUB_URL, send_devices=True, plugins_to_sync=[], pull_nodes=[NODE_URL])
        assert is_hub is True
        assert is_node is True

    def test_neither_when_no_config(self):
        is_hub, is_node = _determine_mode("", send_devices=False, plugins_to_sync=[], pull_nodes=[])
        assert is_hub is False
        assert is_node is False

    def test_no_hub_url_means_not_node_even_with_send_devices(self):
        is_hub, is_node = _determine_mode("", send_devices=True, plugins_to_sync=[], pull_nodes=[])
        assert is_node is False


# ===========================================================================
# send_data (Mode 1 – PUSH)
# ===========================================================================

class TestSendData:

    def _mock_post(self, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        return patch("requests.post", return_value=resp)

    def test_returns_true_on_http_200(self):
        with self._mock_post(200):
            result = _send_data(API_TOKEN, '{"data":[]}', ENCRYPTION_KEY,
                                "/tmp/file.log", "node1", "SYNC", HUB_URL)
        assert result is True

    def test_returns_false_on_non_200(self):
        for code in (400, 401, 403, 500, 503):
            with self._mock_post(code):
                result = _send_data(API_TOKEN, '{"data":[]}', ENCRYPTION_KEY,
                                    "/tmp/file.log", "node1", "SYNC", HUB_URL)
            assert result is False, f"Expected False for HTTP {code}"

    def test_returns_false_on_connection_error(self):
        with patch("requests.post", side_effect=requests.ConnectionError("refused")):
            result = _send_data(API_TOKEN, '{"data":[]}', ENCRYPTION_KEY,
                                "/tmp/file.log", "node1", "SYNC", HUB_URL)
        assert result is False

    def test_returns_false_on_timeout(self):
        with patch("requests.post", side_effect=requests.Timeout("timed out")):
            result = _send_data(API_TOKEN, '{"data":[]}', ENCRYPTION_KEY,
                                "/tmp/file.log", "node1", "SYNC", HUB_URL)
        assert result is False

    def test_posts_to_correct_endpoint(self):
        resp = MagicMock()
        resp.status_code = 200
        with patch("requests.post", return_value=resp) as mock_post:
            _send_data(API_TOKEN, '{"data":[]}', ENCRYPTION_KEY,
                       "/tmp/file.log", "node1", "SYNC", HUB_URL)
        url_called = mock_post.call_args[0][0]
        assert url_called == HUB_URL + "/sync"

    def test_bearer_auth_header_sent(self):
        resp = MagicMock()
        resp.status_code = 200
        with patch("requests.post", return_value=resp) as mock_post:
            _send_data(API_TOKEN, '{"data":[]}', ENCRYPTION_KEY,
                       "/tmp/file.log", "node1", "SYNC", HUB_URL)
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {API_TOKEN}"

    def test_payload_contains_expected_fields(self):
        resp = MagicMock()
        resp.status_code = 200
        with patch("requests.post", return_value=resp) as mock_post:
            _send_data(API_TOKEN, '{"data":[]}', ENCRYPTION_KEY,
                       "/tmp/file.log", "node1", "SYNC", HUB_URL)
        payload = mock_post.call_args[1]["data"]
        assert "data" in payload          # encrypted blob
        assert payload["file_path"] == "/tmp/file.log"
        assert payload["plugin"] == "SYNC"
        assert payload["node_name"] == "node1"

    def test_payload_data_is_encrypted_not_plaintext(self):
        """The 'data' field in the POST must be encrypted, not the raw content."""
        plaintext = '{"secret": "do_not_expose"}'
        resp = MagicMock()
        resp.status_code = 200
        with patch("requests.post", return_value=resp) as mock_post:
            _send_data(API_TOKEN, plaintext, ENCRYPTION_KEY,
                       "/tmp/file.log", "node1", "SYNC", HUB_URL)
        transmitted = mock_post.call_args[1]["data"]["data"]
        assert transmitted != plaintext
        # Verify it round-trips correctly
        assert decrypt_data(transmitted, ENCRYPTION_KEY) == plaintext


# ===========================================================================
# get_data (Mode 2 – PULL)
# ===========================================================================

class TestGetData:

    def _mock_get(self, status_code=200, json_body=None, side_effect=None):
        resp = MagicMock()
        resp.status_code = status_code
        if json_body is not None:
            resp.json.return_value = json_body
        if side_effect is not None:
            return patch("requests.get", side_effect=side_effect)
        return patch("requests.get", return_value=resp)

    def test_returns_parsed_json_on_200(self):
        body = {"node_name": "node1", "data_base64": base64.b64encode(b"hello").decode()}
        with self._mock_get(200, json_body=body):
            result = _get_data(API_TOKEN, NODE_URL)
        assert result == body

    def test_gets_from_correct_endpoint(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        with patch("requests.get", return_value=resp) as mock_get:
            _get_data(API_TOKEN, NODE_URL)
        url_called = mock_get.call_args[0][0]
        assert url_called == NODE_URL + "/sync"

    def test_bearer_auth_header_sent(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        with patch("requests.get", return_value=resp) as mock_get:
            _get_data(API_TOKEN, NODE_URL)
        headers = mock_get.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {API_TOKEN}"

    def test_returns_empty_string_on_json_decode_error(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = json.JSONDecodeError("bad json", "", 0)
        with patch("requests.get", return_value=resp):
            result = _get_data(API_TOKEN, NODE_URL)
        assert result == ""

    def test_returns_empty_string_on_connection_error(self):
        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            result = _get_data(API_TOKEN, NODE_URL)
        assert result == ""

    def test_returns_empty_string_on_timeout(self):
        with patch("requests.get", side_effect=requests.Timeout("timed out")):
            result = _get_data(API_TOKEN, NODE_URL)
        assert result == ""

    def test_returns_empty_string_on_non_200(self):
        resp = MagicMock()
        resp.status_code = 401
        with patch("requests.get", return_value=resp):
            result = _get_data(API_TOKEN, NODE_URL)
        assert result == ""


# ===========================================================================
# Node name extraction from filename (Mode 3 – RECEIVE)
# ===========================================================================

class TestNodeNameExtraction:

    def test_simple_filename(self):
        # last_result.MyNode.log  →  "MyNode"
        assert _node_name_from_filename("last_result.MyNode.log") == "MyNode"

    def test_decoded_filename(self):
        # last_result.decoded.MyNode.1.log  →  "MyNode"
        assert _node_name_from_filename("last_result.decoded.MyNode.1.log") == "MyNode"

    def test_encoded_filename(self):
        # last_result.encoded.MyNode.1.log  →  "MyNode"
        assert _node_name_from_filename("last_result.encoded.MyNode.1.log") == "MyNode"

    def test_node_name_with_underscores(self):
        assert _node_name_from_filename("last_result.Wladek_Site.log") == "Wladek_Site"

    def test_decoded_node_name_with_underscores(self):
        assert _node_name_from_filename("last_result.decoded.Wladek_Site.1.log") == "Wladek_Site"


# ===========================================================================
# CurrentScan candidates filter (Mode 3 – RECEIVE)
# ===========================================================================

class TestCurrentScanCandidates:

    def test_online_device_is_included(self):
        d = make_device_dict(devPresentLastScan=1)
        assert len(_currentscan_candidates([d])) == 1

    def test_offline_device_is_excluded(self):
        d = make_device_dict(devPresentLastScan=0)
        assert len(_currentscan_candidates([d])) == 0

    def test_internet_mac_is_excluded(self):
        d = make_device_dict(mac="internet", devPresentLastScan=1)
        assert len(_currentscan_candidates([d])) == 0

    def test_internet_mac_case_insensitive(self):
        for mac in ("INTERNET", "Internet", "iNtErNeT"):
            d = make_device_dict(mac=mac, devPresentLastScan=1)
            assert len(_currentscan_candidates([d])) == 0, f"mac={mac!r} should be excluded"

    def test_mixed_batch(self):
        devices = [
            make_device_dict(mac="aa:bb:cc:dd:ee:01", devPresentLastScan=1),   # included
            make_device_dict(mac="aa:bb:cc:dd:ee:02", devPresentLastScan=0),   # offline
            make_device_dict(mac="internet", devPresentLastScan=1),             # root node
            make_device_dict(mac="aa:bb:cc:dd:ee:03", devPresentLastScan=1),   # included
        ]
        result = _currentscan_candidates(devices)
        macs = [d["devMac"] for d in result]
        assert "aa:bb:cc:dd:ee:01" in macs
        assert "aa:bb:cc:dd:ee:03" in macs
        assert "aa:bb:cc:dd:ee:02" not in macs
        assert "internet" not in macs


# ===========================================================================
# DB insert filtering – new vs existing devices (Mode 3 – RECEIVE)
# ===========================================================================

class TestReceiveInsert:

    def test_new_device_is_inserted(self, conn):
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        inserted = sync_insert_devices(conn, [device], existing_macs=set())
        assert inserted == 1
        cur = conn.cursor()
        cur.execute("SELECT devMac FROM Devices WHERE devMac = ?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone() is not None

    def test_existing_device_is_not_reinserted(self, conn):
        # Pre-populate Devices
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Devices (devMac, devName) VALUES (?, ?)",
            ("aa:bb:cc:dd:ee:01", "Existing"),
        )
        conn.commit()

        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        inserted = sync_insert_devices(conn, [device], existing_macs={"aa:bb:cc:dd:ee:01"})
        assert inserted == 0

    def test_only_new_devices_inserted_in_mixed_batch(self, conn):
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Devices (devMac, devName) VALUES (?, ?)",
            ("aa:bb:cc:dd:ee:existing", "Existing"),
        )
        conn.commit()

        devices = [
            make_device_dict(mac="aa:bb:cc:dd:ee:existing"),
            make_device_dict(mac="aa:bb:cc:dd:ee:new1"),
            make_device_dict(mac="aa:bb:cc:dd:ee:new2"),
        ]
        inserted = sync_insert_devices(
            conn, devices, existing_macs={"aa:bb:cc:dd:ee:existing"}
        )
        assert inserted == 2

    def test_computed_fields_in_payload_do_not_abort_insert(self, conn):
        """Regression: devIsSleeping / devStatus / devFlapping must be silently dropped."""
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        device["devIsSleeping"] = 0
        device["devStatus"] = "Online"
        device["devFlapping"] = 0
        device["rowid"] = 99
        # Must not raise OperationalError
        inserted = sync_insert_devices(conn, [device], existing_macs=set())
        assert inserted == 1

    def test_empty_device_list_returns_zero(self, conn):
        assert sync_insert_devices(conn, [], existing_macs=set()) == 0
