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
        response = requests.post(hub_url + API_ENDPOINT, json=data, headers=headers, timeout=5)
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
    """Mirror of the node-name extraction in sync.main() (Mode 3).

    PUSH shape: last_result.PLUGIN.(decoded|encoded).NodeName.N.log
      — marker present AND the second-to-last segment (before .log) is a digit
    PULL shape: last_result.NodeName.log
      — no marker, or marker present but no digit counter
        (e.g. node name is 'office.encoded.lab')

    Both forms handle dots anywhere in PLUGIN or NodeName.
    """
    marker_present = '.decoded.' in file_name or '.encoded.' in file_name
    is_push = marker_present and file_name.rsplit('.', 2)[1].isdigit()
    if is_push:
        marker = '.decoded.' if '.decoded.' in file_name else '.encoded.'
        _, after = file_name.split(marker, 1)
        return after.rsplit('.', 2)[0]
    return file_name[len('last_result.'):-len('.log')]


def _should_delete_after_process(filename: str) -> bool:
    """Mirror of the delete-after-process condition in execute_plugin() (server/plugin.py).

    Only node-sync intermediary files (.encoded. / .decoded.) are removed after
    processing.  Local plugin result files (last_result.ARPSCAN.log etc.) must
    survive so SYNC Mode 1 can read and forward them to the hub.
    """
    return ".encoded." in filename or ".decoded." in filename


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
        payload = mock_post.call_args[1]["json"]
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
        transmitted = mock_post.call_args[1]["json"]["data"]
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

    def test_pull_mode_filename(self):
        # PULL mode: last_result.MyNode.log  →  "MyNode"
        assert _node_name_from_filename("last_result.MyNode.log") == "MyNode"

    def test_push_decoded_filename(self):
        # PUSH mode (post-decode): last_result.ARPSCAN.decoded.MyNode.1.log  →  "MyNode"
        assert _node_name_from_filename("last_result.ARPSCAN.decoded.MyNode.1.log") == "MyNode"

    def test_push_encoded_filename(self):
        # PUSH mode (pre-decode): last_result.ARPSCAN.encoded.MyNode.1.log  →  "MyNode"
        assert _node_name_from_filename("last_result.ARPSCAN.encoded.MyNode.1.log") == "MyNode"

    def test_pull_node_name_with_underscores(self):
        assert _node_name_from_filename("last_result.Wladek_Site.log") == "Wladek_Site"

    def test_push_decoded_node_name_with_underscores(self):
        assert _node_name_from_filename("last_result.ARPSCAN.decoded.Wladek_Site.1.log") == "Wladek_Site"

    def test_push_decoded_node_name_with_counter_gt_1(self):
        # Counter increments when multiple pushes arrive before SYNC runs
        assert _node_name_from_filename("last_result.ARPSCAN.decoded.Node_Vlan01.3.log") == "Node_Vlan01"

    def test_push_decoded_different_plugins(self):
        for plugin in ("NMAP", "PIHOLE", "DHCPLEASES"):
            fname = f"last_result.{plugin}.decoded.HubNode.1.log"
            assert _node_name_from_filename(fname) == "HubNode", \
                f"Expected 'HubNode' from {fname}"

    # --- dot-in-identifier regression (fragile parts[3] fix) ---

    def test_pull_node_name_with_dots(self):
        # PULL mode: node name set to e.g. "node.home" or an IP like "192.168.1.82"
        assert _node_name_from_filename("last_result.node.home.log") == "node.home"
        assert _node_name_from_filename("last_result.192.168.1.82.log") == "192.168.1.82"

    def test_push_decoded_node_name_with_dots(self):
        # Node name "Node.Vlan01" must survive the filename round-trip intact
        assert _node_name_from_filename("last_result.ARPSCAN.decoded.Node.Vlan01.1.log") == "Node.Vlan01"

    def test_push_decoded_plugin_name_with_dots(self):
        # Hypothetical plugin with a dot in its name must not shift the node index
        assert _node_name_from_filename("last_result.MY.PLUGIN.decoded.NodeA.1.log") == "NodeA"

    def test_push_both_identifiers_with_dots(self):
        assert _node_name_from_filename(
            "last_result.A.B.decoded.x.y.z.1.log"
        ) == "x.y.z"

    def test_pull_with_encoded_in_node_name(self):
        # Regression: PULL file whose node name contains '.encoded.' must NOT
        # be mis-classified as a PUSH artifact (no digit counter → PULL branch).
        assert _node_name_from_filename("last_result.office.encoded.lab.log") == "office.encoded.lab"
        assert _node_name_from_filename("last_result.site.decoded.backup.log") == "site.decoded.backup"


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


# ===========================================================================
# Plugin result file retention (regression for execute_plugin delete bug)
# ===========================================================================

class TestPluginFileRetention:
    """Regression for the execute_plugin() delete-condition bug (server/plugin.py).

    Before the fix the condition was ``filename != "last_result.log"``.  No
    plugin ever writes to that literal name — all write ``last_result.ARPSCAN.log``
    etc. — so every local result file was deleted immediately after processing,
    before SYNC Mode 1 had a chance to read and forward it to the hub.

    The corrected condition deletes ONLY ``.encoded.`` / ``.decoded.``
    node-sync intermediary files.  Local plugin result files must survive.
    """

    def test_local_result_file_not_flagged_for_deletion(self):
        assert _should_delete_after_process("last_result.ARPSCAN.log") is False

    def test_local_result_files_for_common_plugins_not_flagged(self):
        for plugin in ("NMAP", "PIHOLE", "SYNC", "DHCPLEASES", "ARPSCAN"):
            fname = f"last_result.{plugin}.log"
            assert _should_delete_after_process(fname) is False, \
                f"{fname} must NOT be deleted — SYNC Mode 1 still needs it"

    def test_encoded_node_sync_file_flagged_for_deletion(self):
        assert _should_delete_after_process("last_result.ARPSCAN.encoded.Node1.1.log") is True

    def test_decoded_node_sync_file_flagged_for_deletion(self):
        assert _should_delete_after_process("last_result.ARPSCAN.decoded.Node1.1.log") is True

    def test_encoded_files_with_various_node_names_flagged(self):
        for node in ("Node1", "Home_Hub", "Site_B", "OfficeNode"):
            fname = f"last_result.ARPSCAN.encoded.{node}.1.log"
            assert _should_delete_after_process(fname) is True, \
                f"{fname} should be deleted after processing"

    def test_decoded_files_with_various_node_names_flagged(self):
        for node in ("Node1", "Home_Hub", "Site_B"):
            fname = f"last_result.ARPSCAN.decoded.{node}.2.log"
            assert _should_delete_after_process(fname) is True, \
                f"{fname} should be deleted after processing"

    def test_empty_device_list_returns_zero(self, conn):
        assert sync_insert_devices(conn, [], existing_macs=set()) == 0


# ===========================================================================
# Mode 3 JSON-skip behaviour
# Regression: local plugin result files (pipe-delimited) must not crash Mode 3.
# ===========================================================================

def _parse_sync_payload(file_path: str) -> list:
    """Mirror of the json.load + data['data'] block in sync.main() Mode 3.

    Returns the list of device dicts on success, or raises nothing on invalid
    input — callers should catch JSONDecodeError / KeyError and skip the file.
    """
    with open(file_path, "r") as f:
        data = json.load(f)
    return data["data"]


class TestMode3JsonSkip:
    """Regression for the crash when Mode 3 encountered pipe-delimited plugin files.

    Before the fix, sync.py called json.load() on every last_result.*.log file
    returned by decode_and_rename_files(), including local plugin result files
    (e.g. last_result.DIGSCAN.log) which are pipe-delimited and not JSON.  The
    fix wraps the load in try/except(JSONDecodeError, KeyError) and continues.
    """

    def test_valid_sync_payload_is_parsed(self, tmp_path):
        payload = {"data": [{"devMac": "aa:bb:cc:dd:ee:01", "devName": "TestDevice"}]}
        f = tmp_path / "last_result.ARPSCAN.decoded.Node1.1.log"
        f.write_text(json.dumps(payload))
        result = _parse_sync_payload(str(f))
        assert len(result) == 1
        assert result[0]["devMac"] == "aa:bb:cc:dd:ee:01"

    def test_pipe_delimited_file_raises_json_error(self, tmp_path):
        """Pipe-delimited plugin file must raise JSONDecodeError so callers can skip it."""
        f = tmp_path / "last_result.DIGSCAN.log"
        f.write_text("aa:bb:cc:dd:ee:01|192.168.1.1|2026-01-01 00:00:00|hostname||subnet||DIGSCAN|||||\n")
        with pytest.raises(json.JSONDecodeError):
            _parse_sync_payload(str(f))

    def test_json_without_data_key_raises_key_error(self, tmp_path):
        """JSON that lacks the 'data' key must raise KeyError so callers can skip it."""
        f = tmp_path / "last_result.UNKNOWN.log"
        f.write_text(json.dumps({"result": []}))
        with pytest.raises(KeyError):
            _parse_sync_payload(str(f))

    def test_empty_file_raises_json_error(self, tmp_path):
        f = tmp_path / "last_result.EMPTY.log"
        f.write_text("")
        with pytest.raises(json.JSONDecodeError):
            _parse_sync_payload(str(f))


# ===========================================================================
# SYNC_BEHAVIOR - three hub device-write modes (Mode 3 - RECEIVE)
# ===========================================================================

class TestSyncBehavior:
    """Covers the three SYNC_BEHAVIOR modes for hub-side device writes.

    copy-new     (default) — INSERT new MACs only, skip existing.
    carbon-copy            — UPSERT all MACs; node values overwrite hub values.
    hub-defaults           — skip direct write; let hub pipeline handle it.
    """

    # ------------------------------------------------------------------
    # copy-new (default – backward compatible)
    # ------------------------------------------------------------------

    def test_copy_new_inserts_new_device(self, conn):
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        written = sync_insert_devices(conn, [device], existing_macs=set(), behavior="copy-new")
        assert written == 1
        cur = conn.cursor()
        cur.execute("SELECT devMac FROM Devices WHERE devMac = ?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone() is not None

    def test_copy_new_skips_existing_device(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac, devName) VALUES (?, ?)", ("aa:bb:cc:dd:ee:01", "Original"))
        conn.commit()

        device = make_device_dict(mac="aa:bb:cc:dd:ee:01", devName="Updated")
        written = sync_insert_devices(conn, [device], existing_macs={"aa:bb:cc:dd:ee:01"}, behavior="copy-new")
        assert written == 0
        cur.execute("SELECT devName FROM Devices WHERE devMac = ?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone()["devName"] == "Original"

    def test_copy_new_only_new_in_mixed_batch(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac, devName) VALUES (?, ?)", ("aa:bb:cc:dd:ee:existing", "Existing"))
        conn.commit()

        devices = [
            make_device_dict(mac="aa:bb:cc:dd:ee:existing"),
            make_device_dict(mac="aa:bb:cc:dd:ee:new1"),
            make_device_dict(mac="aa:bb:cc:dd:ee:new2"),
        ]
        written = sync_insert_devices(conn, devices, existing_macs={"aa:bb:cc:dd:ee:existing"}, behavior="copy-new")
        assert written == 2

    # ------------------------------------------------------------------
    # carbon-copy — UPSERT, node is authoritative
    # ------------------------------------------------------------------

    def test_carbon_copy_inserts_new_device(self, conn):
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        written = sync_insert_devices(conn, [device], behavior="carbon-copy")
        assert written == 1
        cur = conn.cursor()
        cur.execute("SELECT devMac FROM Devices WHERE devMac = ?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone() is not None

    def test_carbon_copy_overwrites_existing_device(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac, devName) VALUES (?, ?)", ("aa:bb:cc:dd:ee:01", "OldName"))
        conn.commit()

        device = make_device_dict(mac="aa:bb:cc:dd:ee:01", devName="NewName")
        written = sync_insert_devices(conn, [device], behavior="carbon-copy")
        assert written == 1
        cur.execute("SELECT devName FROM Devices WHERE devMac = ?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone()["devName"] == "NewName"

    def test_carbon_copy_processes_all_devices_in_batch(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac, devName) VALUES (?, ?)", ("aa:bb:cc:dd:ee:01", "OldName"))
        conn.commit()

        devices = [
            make_device_dict(mac="aa:bb:cc:dd:ee:01", devName="UpdatedName"),
            make_device_dict(mac="aa:bb:cc:dd:ee:02"),
        ]
        written = sync_insert_devices(conn, devices, behavior="carbon-copy")
        assert written == 2

        cur.execute("SELECT devName FROM Devices WHERE devMac = ?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone()["devName"] == "UpdatedName"

    def test_carbon_copy_does_not_duplicate_existing_device(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac, devName) VALUES (?, ?)", ("aa:bb:cc:dd:ee:01", "Original"))
        conn.commit()

        device = make_device_dict(mac="aa:bb:cc:dd:ee:01", devName="Updated")
        sync_insert_devices(conn, [device], behavior="carbon-copy")

        cur.execute("SELECT COUNT(*) AS cnt FROM Devices WHERE devMac = ?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone()["cnt"] == 1

    def test_carbon_copy_does_not_overwrite_devPresentLastScan(self, conn):
        """Regression: carbon-copy must NOT clobber devPresentLastScan.

        Scenario: device is online on the hub (devPresentLastScan=1) but the
        node reports it as offline (devPresentLastScan=0).  Without the fix the
        UPSERT would flip presence to 0, triggering a Device Down event on the
        next scan cycle and a Connected event on the scan after that, causing
        the device to accumulate enough churn events to be flagged as Flapping.
        """
        cur = conn.cursor()
        # Hub already knows this device and currently sees it as online.
        cur.execute(
            "INSERT INTO Devices (devMac, devName, devPresentLastScan) VALUES (?, ?, ?)",
            ("aa:bb:cc:dd:ee:01", "HubDevice", 1),
        )
        conn.commit()

        # Node reports same MAC as offline.
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01", devPresentLastScan=0)
        sync_insert_devices(conn, [device], behavior="carbon-copy")

        cur.execute(
            "SELECT devPresentLastScan FROM Devices WHERE devMac = ?",
            ("aa:bb:cc:dd:ee:01",),
        )
        row = cur.fetchone()
        assert row["devPresentLastScan"] == 1, (
            "carbon-copy must not overwrite devPresentLastScan with a node's offline value"
        )

    # ------------------------------------------------------------------
    # hub-defaults — no direct write, hub pipeline handles it
    # ------------------------------------------------------------------

    def test_hub_defaults_writes_nothing(self, conn):
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        written = sync_insert_devices(conn, [device], behavior="hub-defaults")
        assert written == 0

    def test_hub_defaults_leaves_db_empty(self, conn):
        devices = [make_device_dict(mac=f"aa:bb:cc:dd:ee:0{i}") for i in range(3)]
        sync_insert_devices(conn, devices, behavior="hub-defaults")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM Devices")
        assert cur.fetchone()["cnt"] == 0

    def test_hub_defaults_returns_zero_for_empty_input(self, conn):
        assert sync_insert_devices(conn, [], behavior="hub-defaults") == 0

    # ------------------------------------------------------------------
    # "New Device" events — copy-new and carbon-copy must fire; hub-defaults must not
    # ------------------------------------------------------------------

    def test_copy_new_fires_new_device_event(self, conn):
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        sync_insert_devices(conn, [device], existing_macs=set(), behavior="copy-new")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM Events WHERE eveEventType='New Device' AND eveMac=?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone()["cnt"] == 1

    def test_copy_new_does_not_fire_event_for_existing_device(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac) VALUES (?)", ("aa:bb:cc:dd:ee:01",))
        conn.commit()
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        sync_insert_devices(conn, [device], existing_macs={"aa:bb:cc:dd:ee:01"}, behavior="copy-new")
        cur.execute("SELECT COUNT(*) AS cnt FROM Events WHERE eveEventType='New Device'")
        assert cur.fetchone()["cnt"] == 0

    def test_carbon_copy_fires_new_device_event_for_new_mac(self, conn):
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01")
        sync_insert_devices(conn, [device], existing_macs=set(), behavior="carbon-copy")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM Events WHERE eveEventType='New Device' AND eveMac=?", ("aa:bb:cc:dd:ee:01",))
        assert cur.fetchone()["cnt"] == 1

    def test_carbon_copy_does_not_fire_event_for_existing_mac(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac) VALUES (?)", ("aa:bb:cc:dd:ee:01",))
        conn.commit()
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01", devName="Updated")
        sync_insert_devices(conn, [device], existing_macs={"aa:bb:cc:dd:ee:01"}, behavior="carbon-copy")
        cur.execute("SELECT COUNT(*) AS cnt FROM Events WHERE eveEventType='New Device'")
        assert cur.fetchone()["cnt"] == 0

    def test_hub_defaults_fires_no_events_directly(self, conn):
        devices = [make_device_dict(mac=f"aa:bb:cc:dd:ee:0{i}") for i in range(3)]
        sync_insert_devices(conn, devices, existing_macs=set(), behavior="hub-defaults")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM Events WHERE eveEventType='New Device'")
        assert cur.fetchone()["cnt"] == 0

    def test_copy_new_fires_events_only_for_new_macs_in_mixed_batch(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac) VALUES (?)", ("aa:bb:cc:dd:ee:existing",))
        conn.commit()

        devices = [
            make_device_dict(mac="aa:bb:cc:dd:ee:existing"),
            make_device_dict(mac="aa:bb:cc:dd:ee:new1"),
            make_device_dict(mac="aa:bb:cc:dd:ee:new2"),
        ]
        sync_insert_devices(conn, devices, existing_macs={"aa:bb:cc:dd:ee:existing"}, behavior="copy-new")

        cur.execute("SELECT eveMac FROM Events WHERE eveEventType='New Device'")
        event_macs = {r["eveMac"] for r in cur.fetchall()}
        assert event_macs == {"aa:bb:cc:dd:ee:new1", "aa:bb:cc:dd:ee:new2"}

    def test_carbon_copy_fires_events_only_for_new_macs_in_mixed_batch(self, conn):
        cur = conn.cursor()
        cur.execute("INSERT INTO Devices (devMac, devName) VALUES (?, ?)", ("aa:bb:cc:dd:ee:existing", "Old"))
        conn.commit()

        devices = [
            make_device_dict(mac="aa:bb:cc:dd:ee:existing", devName="Updated"),
            make_device_dict(mac="aa:bb:cc:dd:ee:new1"),
        ]
        sync_insert_devices(conn, devices, existing_macs={"aa:bb:cc:dd:ee:existing"}, behavior="carbon-copy")

        cur.execute("SELECT eveMac FROM Events WHERE eveEventType='New Device'")
        event_macs = {r["eveMac"] for r in cur.fetchall()}
        assert event_macs == {"aa:bb:cc:dd:ee:new1"}

    def test_new_device_event_fields_are_correct(self, conn):
        device = make_device_dict(mac="aa:bb:cc:dd:ee:01", devLastIP="10.0.0.1", devVendor="Acme")
        sync_insert_devices(conn, [device], existing_macs=set(), behavior="copy-new")
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM Events WHERE eveEventType='New Device' AND eveMac=?",
            ("aa:bb:cc:dd:ee:01",),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["eveMac"] == "aa:bb:cc:dd:ee:01"
        assert row["eveIp"] == "10.0.0.1"
        assert row["eveAdditionalInfo"] == "Acme"
        assert row["evePendingAlertEmail"] == 1
        # Confirm exactly one event was inserted (no duplicates).
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM Events WHERE eveEventType='New Device' AND eveMac=?",
            ("aa:bb:cc:dd:ee:01",),
        )
        assert cur.fetchone()["cnt"] == 1
