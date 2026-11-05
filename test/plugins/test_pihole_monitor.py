"""Tests for the pihole_monitor (PIHOLEMON) plugin.

pihole_monitor.py is loaded with its NetAlertX-internal dependencies
(plugin_helper, logger, helper, const, conf, pytz, utils.*) stubbed out,
the same approach test_mikrotik_scan.py uses - it keeps these tests
runnable without the full devcontainer environment and without any live
Pi-hole. `requests` itself is left real; individual HTTP calls are mocked
per test.

Layout:
  - PiholeSource.auth() / fetch_top_blocked_clients(): unit tests against
    a mocked `requests`, covering the auth success/failure paths and the
    None-sentinel-on-failure contract (vs. a genuine empty {}).
  - netalertx_device_owners(): unit tests for the batched (one request for
    every device, not one per device) owner lookup.
  - build_ip_to_mac(): pure-function unit tests for the multi-IP-per-MAC
    fix (a device must not lose its other IPs to the by-MAC merge).
  - compute_delta(): pure-function unit tests turning Pi-hole's raw,
    cumulative-since-FTL-started count into a real per-run increment -
    None (not 0) on a first-ever run or a counter reset, a genuine 0
    distinct from that None otherwise.
  - aggregate_source_deltas(): pure-function unit tests for combining
    per-source deltas correctly - a counter reset on one source must not
    net out against real traffic on another (they're diffed
    independently, then summed - never combined as raw totals first).
  - main(): integration tests with PiholeSource's network-touching
    methods stubbed at the object level, covering source aggregation,
    the stats_complete gate (a failed fetch must not corrupt a device's
    history with a false zero), the history_days age-based clamp/trim
    (not a run count - see trim_history()), the zero-baseline anomaly fix
    (a device with an all-zero history must still be flagged, not silently
    exempted), the bootstrap/counter-reset runs that establish or
    re-anchor last_raw without recording a bogus delta, the dual-source
    reset-masking regression, tolerance of a pre-per-source state file
    (last_raw as a plain number, from before this round), and
    per-instance Verify SSL.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests


def _is_mac(value):
    """Same shape as plugin_helper.is_mac, without pytz as a dependency."""
    import re
    s = str(value).lower().strip()
    return bool(re.match(r"^[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\1[0-9a-f]{2}){4}$", s))


def _load_pihole_monitor_module():
    missing_module = object()
    previous_modules = {}

    def stub(name, **attributes):
        previous_modules[name] = sys.modules.get(name, missing_module)
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module

    stub("plugin_helper", Plugin_Objects=MagicMock, is_mac=_is_mac)
    stub("logger", mylog=MagicMock(), Logger=MagicMock())
    stub("helper", get_setting_value=MagicMock(return_value="UTC"))
    stub("const", logPath="/tmp", dbFolderPath="/tmp/db")
    stub("conf", tz=None)
    stub("pytz", timezone=MagicMock(return_value="UTC"))
    stub("utils")
    stub("utils.datetime_utils", timeNowUTC=MagicMock())
    stub("utils.crypto_utils", string_to_fake_mac=lambda s: "fa:ce:00:00:00:01")

    module_path = Path(__file__).resolve().parents[2] / "server" / "plugins" / "pihole_monitor" / "pihole_monitor.py"
    spec = importlib.util.spec_from_file_location("pihole_monitor", module_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is missing_module:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module

    return module


pihole_monitor = _load_pihole_monitor_module()


def _resp(json_data):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data)
    return resp


# ---------------------------------------------------------------------------
# PiholeSource.auth()
# ---------------------------------------------------------------------------


def test_auth_success_stores_sid_and_csrf():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    with patch("requests.post", return_value=_resp({"session": {"valid": True, "sid": "abc", "csrf": "xyz"}})):
        assert source.auth() is True
    assert source.sid == "abc"
    assert source.csrf == "xyz"


def test_auth_invalid_session_returns_false():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "wrongpw", True, 5)
    with patch("requests.post", return_value=_resp({"session": {"valid": False}})):
        assert source.auth() is False
    assert source.sid is None


def test_auth_connection_error_returns_false_without_raising():
    import requests as real_requests
    source = pihole_monitor.PiholeSource("primary", "http://unreachable/", "pw", True, 5)
    with patch("requests.post", side_effect=real_requests.exceptions.ConnectionError("no route")):
        assert source.auth() is False
    assert source.sid is None


def test_auth_unconfigured_source_short_circuits():
    source = pihole_monitor.PiholeSource("secondary", "", "", True, 5)
    with patch("requests.post") as mock_post:
        assert source.auth() is False
    mock_post.assert_not_called()


def test_auth_timeout_returns_false():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    with patch("requests.post", side_effect=requests.exceptions.Timeout("slow")):
        assert source.auth() is False
    assert source.sid is None


def test_auth_unexpected_error_returns_false():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    with patch("requests.post", side_effect=ValueError("boom")):
        assert source.auth() is False


def test_auth_unparseable_json_returns_false():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(side_effect=ValueError("not json"))
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    with patch("requests.post", return_value=resp):
        assert source.auth() is False


def test_auth_disables_insecure_warning_when_verify_ssl_off():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", False, 5)
    session_resp = _resp({"session": {"valid": True, "sid": "s", "csrf": "c"}})
    with patch("requests.post", return_value=session_resp), \
         patch("requests.packages.urllib3.disable_warnings") as mock_disable:
        assert source.auth() is True
    mock_disable.assert_called_once()


# ---------------------------------------------------------------------------
# PiholeSource.deauth()
# ---------------------------------------------------------------------------


def test_deauth_clears_session_on_success():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    source.sid = "sid"
    source.csrf = "csrf"
    with patch("requests.delete", return_value=_resp({})) as mock_delete:
        source.deauth()
    mock_delete.assert_called_once()
    assert source.sid is None
    assert source.csrf is None


def test_deauth_swallows_request_errors():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    source.sid = "sid"
    with patch("requests.delete", side_effect=requests.exceptions.ConnectionError("gone")):
        source.deauth()  # must not raise
    assert source.sid is None


def test_deauth_noop_without_an_active_session():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    with patch("requests.delete") as mock_delete:
        source.deauth()
    mock_delete.assert_not_called()


# ---------------------------------------------------------------------------
# PiholeSource.fetch_devices()
# ---------------------------------------------------------------------------


def test_fetch_devices_success_returns_device_list():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    source.sid = "sid"
    source.csrf = "csrf"  # also exercises _headers() including X-FTL-CSRF
    payload = {"devices": [{"hwaddr": "aa:bb:cc:dd:ee:01"}]}
    with patch("requests.get", return_value=_resp(payload)) as mock_get:
        result = source.fetch_devices(max_clients=500)
    assert result == [{"hwaddr": "aa:bb:cc:dd:ee:01"}]
    assert mock_get.call_args.kwargs["params"] == {"max_devices": "500", "max_addresses": "2"}


def test_fetch_devices_failure_returns_empty_list():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    source.sid = "sid"
    with patch("requests.get", side_effect=requests.exceptions.Timeout("slow")):
        assert source.fetch_devices(max_clients=500) == []


def test_fetch_devices_without_session_returns_empty_list():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    with patch("requests.get") as mock_get:
        assert source.fetch_devices(max_clients=500) == []
    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# netalertx_device_owners() - one batched request, not one per device
# ---------------------------------------------------------------------------


def test_netalertx_device_owners_returns_empty_dict_without_url():
    assert pihole_monitor.netalertx_device_owners(None, "token", 5) == {}


def test_netalertx_device_owners_returns_mac_keyed_dict_on_success():
    payload = {"data": {"devices": {"devices": [
        {"devMac": "aa:bb:cc:dd:ee:01", "devOwner": "Mauricio"},
        {"devMac": "aa:bb:cc:dd:ee:02", "devOwner": ""},
    ]}}}
    with patch("requests.post", return_value=_resp(payload)) as mock_post:
        owners = pihole_monitor.netalertx_device_owners("http://nax/graphql", "tok", 5)
    assert owners == {"aa:bb:cc:dd:ee:01": "Mauricio", "aa:bb:cc:dd:ee:02": ""}
    assert mock_post.call_args.kwargs["headers"] == {"Authorization": "Bearer tok"}
    # No per-device filter - the whole device list comes back in one request.
    assert "variables" not in mock_post.call_args.kwargs["json"]


def test_netalertx_device_owners_returns_empty_dict_when_none_known():
    payload = {"data": {"devices": {"devices": []}}}
    with patch("requests.post", return_value=_resp(payload)):
        owners = pihole_monitor.netalertx_device_owners("http://nax/graphql", "", 5)
    assert owners == {}


def test_netalertx_device_owners_returns_empty_dict_on_request_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
        owners = pihole_monitor.netalertx_device_owners("http://nax/graphql", "tok", 5)
    assert owners == {}


def test_netalertx_device_owners_fetches_once_regardless_of_device_count():
    """Regression guard for the N-round-trips bug: on a network with many
    devices, this must still be exactly one HTTP call, not one per device."""
    payload = {"data": {"devices": {"devices": [
        {"devMac": f"aa:bb:cc:dd:ee:{i:02x}", "devOwner": f"user{i}"} for i in range(50)
    ]}}}
    with patch("requests.post", return_value=_resp(payload)) as mock_post:
        owners = pihole_monitor.netalertx_device_owners("http://nax/graphql", "tok", 5)
    assert mock_post.call_count == 1
    assert len(owners) == 50


# ---------------------------------------------------------------------------
# gather_device_entries() - skip branches and the fake-MAC fallback
# ---------------------------------------------------------------------------


def test_gather_device_entries_skips_invalid_hwaddr_empty_ips_and_placeholder_ip():
    devices = [
        {"hwaddr": "00:00:00:00:00:00", "ips": [{"ip": "10.0.0.1"}]},  # excluded hwaddr
        {"hwaddr": "", "ips": [{"ip": "10.0.0.2"}]},                    # missing hwaddr
        {"hwaddr": "aa:bb:cc:dd:ee:01", "ips": []},                     # no ips at all
        {"hwaddr": "aa:bb:cc:dd:ee:02", "ips": [{"ip": "0.0.0.0"}]},    # only a placeholder ip
        {"hwaddr": "ip-::", "ips": [{"ip": "10.0.0.4"}]},               # placeholder hwaddr, the ::-specific case
        {"hwaddr": "ip-10.0.0.5", "ips": [{"ip": "10.0.0.5"}]},         # placeholder hwaddr, the general case
        {"hwaddr": "aa:bb:cc:dd:ee:03", "ips": [{"ip": "10.0.0.3", "lastSeen": 1000}]},  # the one real entry
    ]
    source = MagicMock()
    source.fetch_devices.return_value = devices
    entries = pihole_monitor.gather_device_entries(source, consider_online=300, fake_mac=False, max_clients=500)
    assert [e["mac"] for e in entries] == ["aa:bb:cc:dd:ee:03"]


def test_gather_device_entries_fake_mac_fallback_for_invalid_hwaddr():
    devices = [{"hwaddr": "not-a-real-mac", "ips": [{"ip": "10.0.0.9", "lastSeen": 1000}]}]
    source = MagicMock()
    source.fetch_devices.return_value = devices
    entries = pihole_monitor.gather_device_entries(source, consider_online=300, fake_mac=True, max_clients=500)
    assert entries[0]["mac"] == "fa:ce:00:00:00:01"  # from the stubbed string_to_fake_mac


# ---------------------------------------------------------------------------
# PiholeSource.fetch_top_blocked_clients() - None sentinel vs. genuine {}
# ---------------------------------------------------------------------------


def test_fetch_top_blocked_clients_success_returns_dict():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    source.sid = "sid"
    payload = {"clients": [{"ip": "10.0.0.5", "count": 12}, {"ip": "10.0.0.6", "count": 0}]}
    with patch("requests.get", return_value=_resp(payload)) as mock_get:
        result = source.fetch_top_blocked_clients(count=123)
    assert result == {"10.0.0.5": 12, "10.0.0.6": 0}
    assert mock_get.call_args.kwargs["params"] == {"blocked": "true", "count": 123}


def test_fetch_top_blocked_clients_genuine_empty_is_not_none():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    source.sid = "sid"
    with patch("requests.get", return_value=_resp({"clients": []})):
        result = source.fetch_top_blocked_clients(count=500)
    assert result == {}


def test_fetch_top_blocked_clients_failure_returns_none_not_empty_dict():
    import requests as real_requests
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    source.sid = "sid"
    with patch("requests.get", side_effect=real_requests.exceptions.Timeout("slow")):
        result = source.fetch_top_blocked_clients(count=500)
    assert result is None


def test_fetch_top_blocked_clients_without_session_returns_none():
    source = pihole_monitor.PiholeSource("primary", "http://ph1/", "pw", True, 5)
    assert source.fetch_top_blocked_clients(count=500) is None


# ---------------------------------------------------------------------------
# build_ip_to_mac() - a multi-IP device must not lose its other IPs
# ---------------------------------------------------------------------------


def _entry(mac, ip, last_seen):
    return {"mac": mac, "ip": ip, "name": "", "macVendor": "", "lastSeen": last_seen, "is_online": True}


def test_build_ip_to_mac_keeps_every_ip_of_a_multi_ip_device():
    entries = [
        _entry("aa:bb:cc:dd:ee:01", "10.0.0.5", 100),
        _entry("aa:bb:cc:dd:ee:01", "10.0.0.6", 90),  # same device, second IP, older lastSeen
    ]
    ip_to_mac = pihole_monitor.build_ip_to_mac(entries)
    assert ip_to_mac == {"10.0.0.5": "aa:bb:cc:dd:ee:01", "10.0.0.6": "aa:bb:cc:dd:ee:01"}


def test_build_ip_to_mac_freshest_mac_wins_on_ip_reassignment():
    entries = [
        _entry("aa:bb:cc:dd:ee:01", "10.0.0.5", 100),  # older MAC on this IP
        _entry("aa:bb:cc:dd:ee:02", "10.0.0.5", 200),  # DHCP reassigned, newer
    ]
    ip_to_mac = pihole_monitor.build_ip_to_mac(entries)
    assert ip_to_mac == {"10.0.0.5": "aa:bb:cc:dd:ee:02"}


def test_build_ip_to_mac_differs_from_naive_merged_result():
    """Regression guard for the original bug: deriving the IP map from
    merge_device_entries()'s output (one entry per MAC) drops a device's
    other IPs. build_ip_to_mac() must not do that."""
    entries = [
        _entry("aa:bb:cc:dd:ee:01", "10.0.0.5", 100),
        _entry("aa:bb:cc:dd:ee:01", "10.0.0.6", 90),
    ]
    merged = pihole_monitor.merge_device_entries(entries)
    naive_ip_to_mac = {e["ip"]: mac for mac, e in merged.items()}
    assert naive_ip_to_mac == {"10.0.0.5": "aa:bb:cc:dd:ee:01"}  # the bug: 10.0.0.6 missing

    fixed_ip_to_mac = pihole_monitor.build_ip_to_mac(entries)
    assert "10.0.0.6" in fixed_ip_to_mac


# ---------------------------------------------------------------------------
# main() - orchestration, with PiholeSource's network methods stubbed
# ---------------------------------------------------------------------------


def _device_payload(mac, ip, name="dev", vendor="Acme", last_seen=1000):
    return {"hwaddr": mac, "macVendor": vendor, "ips": [{"ip": ip, "name": name, "lastSeen": last_seen}]}


class _Settings(dict):
    """get_setting_value side_effect backed by a dict, with the plugin's
    own defaults for anything a test doesn't override."""

    _DEFAULTS = {
        "PIHOLEMON_PRIMARY_VERIFY_SSL": True,
        "PIHOLEMON_SECONDARY_VERIFY_SSL": True,
        "PIHOLEMON_RUN_TIMEOUT": 5,
        "PIHOLEMON_GET_OFFLINE": False,
        "PIHOLEMON_FAKE_MAC": False,
        "PIHOLEMON_API_MAXCLIENTS": 500,
        "PIHOLEMON_CONSIDER_ONLINE": 300,
        # False in tests by default (config.json's real default is True) so
        # a plain main() test doesn't make a live-looking requests.post call
        # nobody asked for - tests that exercise owner lookup opt in and
        # mock requests.post themselves.
        "PIHOLEMON_GET_OWNER": False,
        "GRAPHQL_PORT": 20212,
        "API_TOKEN": None,
        "PIHOLEMON_MULTIPLIER": 4,
        "PIHOLEMON_MIN_BLOCKED": 1,
        "PIHOLEMON_HISTORY_DAYS": 7,
        "PIHOLEMON_PRIMARY_URL": "http://ph1/",
        "PIHOLEMON_PRIMARY_PASSWORD": "pw1",
        "PIHOLEMON_SECONDARY_URL": "",
        "PIHOLEMON_SECONDARY_PASSWORD": "",
    }

    def __call__(self, key):
        if key in self:
            return self[key]
        return self._DEFAULTS[key]


@pytest.fixture
def settings():
    return _Settings()


@pytest.fixture
def isolated_state(tmp_path, settings):
    """Points STATE_FILE/RESULT_FILE at a scratch dir and wires up
    get_setting_value, for every main()-level test."""
    with patch.object(pihole_monitor, "STATE_FILE", str(tmp_path / "state.json")), \
         patch.object(pihole_monitor, "RESULT_FILE", str(tmp_path / "last_result.log")), \
         patch.object(pihole_monitor, "get_setting_value", side_effect=settings), \
         patch.object(pihole_monitor.PiholeSource, "auth", return_value=True), \
         patch.object(pihole_monitor.PiholeSource, "deauth", return_value=None):
        yield tmp_path


def test_main_aggregates_blocked_counts_from_both_sources(isolated_state, settings):
    settings["PIHOLEMON_SECONDARY_URL"] = "http://ph2/"
    settings["PIHOLEMON_SECONDARY_PASSWORD"] = "pw2"

    devices_by_label = {
        "primary": [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")],
        "secondary": [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")],
    }
    blocked_by_label = {"primary": {"10.0.0.5": 30}, "secondary": {"10.0.0.5": 15}}

    def _fetch_devices(self, max_clients):
        return devices_by_label[self.label]

    def _fetch_top_blocked(self, count):
        return blocked_by_label[self.label]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", _fetch_devices), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", _fetch_top_blocked), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        # last_raw=0 for both sources so each source's raw count comes
        # straight through as its own delta (30 and 15) - this test is
        # about summing per-source deltas, not about compute_delta() or
        # aggregate_source_deltas()' reset handling (covered separately).
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {"last_raw": {"primary": 0, "secondary": 0}, "history": []}})
        assert pihole_monitor.main() == 0

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    # Not imported twice (one device-import row) and its blocked counts
    # from both instances are summed, not compared/overwritten.
    assert call.kwargs["primaryId"] == "aa:bb:cc:dd:ee:01"
    assert call.kwargs["watched3"] == "45"


def test_main_stats_complete_false_when_a_source_fetch_fails(isolated_state, settings):
    """A failed top_clients fetch must not write a false zero into a
    device's history, and must not evaluate an anomaly this run."""
    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value=None), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        # Seed a history (and a last_raw reference point) so a baseline
        # exists and would trip the multiplier if (incorrectly) evaluated
        # against a written-in zero. Timestamp 1 matches the stubbed
        # timeNowUTC's default "now" (see module stub), so nothing is
        # trimmed by the day-window here - not what this test is about.
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {"last_raw": {"primary": 1000}, "history": [[1, 40], [1, 42], [1, 38]]}})
        assert pihole_monitor.main() == 0

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    assert call.kwargs["watched4"] == "normal"  # not "anomaly" - stats were incomplete

    state_after = pihole_monitor.load_state()
    # Untouched, including last_raw - no false delta or reference-point
    # update from a run whose data was incomplete.
    assert state_after["aa:bb:cc:dd:ee:01"] == {"last_raw": {"primary": 1000}, "history": [[1, 40], [1, 42], [1, 38]]}


def test_main_records_anomaly_when_stats_are_complete(isolated_state, settings):
    settings["PIHOLEMON_MULTIPLIER"] = 2
    settings["PIHOLEMON_MIN_BLOCKED"] = 5
    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.5": 50}), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        # last_raw=0 so this run's raw count (50) is also its delta -
        # baseline avg 10, 50 >> 2x.
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {"last_raw": {"primary": 0}, "history": [[1, 10], [1, 10], [1, 10]]}})
        assert pihole_monitor.main() == 0

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    assert call.kwargs["watched4"] == "anomaly"

    state_after = pihole_monitor.load_state()
    assert state_after["aa:bb:cc:dd:ee:01"] == {"last_raw": {"primary": 50}, "history": [[1, 10], [1, 10], [1, 10], [1, 50]]}


_DAY = 86400
_FIXED_NOW = 2_000_000  # arbitrary fixed epoch, for deterministic age-based trimming


def _fixed_now_mock():
    now = MagicMock()
    now.timestamp.return_value = _FIXED_NOW
    return now


@pytest.mark.parametrize(
    ("configured_days", "expected_history"),
    [
        # Seed has samples aged 10, 3, and 1 days; a new one lands at age 0.
        (-5, [[_FIXED_NOW - 1 * _DAY, 10], [_FIXED_NOW, 40]]),                                              # negative - clamps to 1 day, only the freshest old sample survives
        (0, [[_FIXED_NOW - 3 * _DAY, 20], [_FIXED_NOW - 1 * _DAY, 10], [_FIXED_NOW, 40]]),                  # falsy - falls back to 7 via `or`, drops only the 10-day-old sample
        (1, [[_FIXED_NOW - 1 * _DAY, 10], [_FIXED_NOW, 40]]),                                               # explicit 1 - same cutoff as the clamped negative case
        (7, [[_FIXED_NOW - 3 * _DAY, 20], [_FIXED_NOW - 1 * _DAY, 10], [_FIXED_NOW, 40]]),                  # the documented default - same as the 0/fallback case
        (15, [[_FIXED_NOW - 10 * _DAY, 30], [_FIXED_NOW - 3 * _DAY, 20], [_FIXED_NOW - 1 * _DAY, 10], [_FIXED_NOW, 40]]),  # wide enough - nothing trimmed
    ],
)
def test_main_history_days_clamps_and_trims_by_age(isolated_state, settings, configured_days, expected_history):
    """Distinct, ordered seed values at distinct known ages (not len() alone)
    so a wrong cutoff - e.g. a 1-day clamp that actually kept the 3-day-old
    sample too, which a bare len() check would miss - shows up as a
    mismatch. Also guards against day/second unit mixups (a classic
    `history_days` vs `history_days * 86400` bug) since the exact surviving
    ages are asserted, not just a count."""
    settings["PIHOLEMON_HISTORY_DAYS"] = configured_days
    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]
    # last_raw=0 so this run's raw count (40) is also its delta - this test
    # is about the day-based trim/clamp, not about compute_delta() itself.
    seed = {"aa:bb:cc:dd:ee:01": {"last_raw": {"primary": 0}, "history": [
        [_FIXED_NOW - 10 * _DAY, 30],
        [_FIXED_NOW - 3 * _DAY, 20],
        [_FIXED_NOW - 1 * _DAY, 10],
    ]}}

    with patch.object(pihole_monitor, "timeNowUTC", return_value=_fixed_now_mock()), \
         patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.5": 40}), \
         patch.object(pihole_monitor, "Plugin_Objects"):
        pihole_monitor.save_state(seed)
        assert pihole_monitor.main() == 0

    history = pihole_monitor.load_state()["aa:bb:cc:dd:ee:01"]["history"]
    assert history == expected_history


def test_main_history_days_baseline_uses_only_samples_inside_the_window():
    """The day-window must also gate the baseline itself, not just what
    gets persisted - an old, out-of-window sample must not silently drag
    the average up or down."""
    stale = [_FIXED_NOW - 30 * _DAY, 1000]  # far outside any sane window
    fresh = [_FIXED_NOW - 1 * _DAY, 10]
    history = pihole_monitor.trim_history([stale, fresh], _FIXED_NOW, history_days=7)
    assert history == [fresh]  # the stale, high-value sample must be gone


# ---------------------------------------------------------------------------
# compute_delta() - Pi-hole's raw cumulative-since-FTL-started count turned
# into a real per-run increment (see its docstring for why this matters).
# ---------------------------------------------------------------------------


def test_compute_delta_none_when_never_seen_before():
    assert pihole_monitor.compute_delta(None, 500) is None


def test_compute_delta_none_when_counter_went_backwards():
    """Pi-hole/FTL restarted (or the device dropped out of top_clients) -
    current_raw < last_raw must not produce a negative delta."""
    assert pihole_monitor.compute_delta(1000, 5) is None


def test_compute_delta_returns_the_real_increment():
    assert pihole_monitor.compute_delta(100, 150) == 50


def test_compute_delta_zero_is_a_real_value_not_none():
    """No new blocked queries since last run is a genuine 0, distinct from
    None ('we can't tell this run') - a caller conflating them would either
    silently drop a legitimate quiet period or treat it as untrustworthy."""
    delta = pihole_monitor.compute_delta(100, 100)
    assert delta == 0
    assert delta is not None


# ---------------------------------------------------------------------------
# aggregate_source_deltas() - per-source deltas summed independently, so one
# source's counter reset can't net out against real traffic on another.
# ---------------------------------------------------------------------------


def test_aggregate_source_deltas_sums_valid_deltas_from_every_source():
    delta, updated = pihole_monitor.aggregate_source_deltas(
        {"primary": 100, "secondary": 200},
        {"primary": 150, "secondary": 250},
    )
    assert delta == 100  # 50 + 50
    assert updated == {"primary": 150, "secondary": 250}


def test_aggregate_source_deltas_reset_source_does_not_mask_the_others_spike():
    """Regression guard for the exact bug CodeRabbit flagged: combining raw
    totals across sources before diffing would let a reset on one source
    net against real growth on another (primary +2000, secondary resetting
    1000->5 would combine into a raw delta of only 1005). Diffing each
    source first and summing only the valid deltas must instead surface
    the primary's full 2000, with the secondary contributing nothing this
    run (not a corrective -995)."""
    delta, updated = pihole_monitor.aggregate_source_deltas(
        {"primary": 1000, "secondary": 1000},
        {"primary": 3000, "secondary": 5},  # secondary: FTL restarted, counter reset
    )
    assert delta == 2000  # primary's real delta only, not 3000-1000+5-1000=1005
    assert updated == {"primary": 3000, "secondary": 5}  # both re-anchored regardless


def test_aggregate_source_deltas_none_when_every_source_is_invalid():
    delta, updated = pihole_monitor.aggregate_source_deltas(
        {},  # nothing seen before - every source is bootstrapping
        {"primary": 100, "secondary": 200},
    )
    assert delta is None
    assert updated == {"primary": 100, "secondary": 200}


def test_aggregate_source_deltas_source_absent_this_run_keeps_its_old_last_raw():
    """A source that authenticated last run but not this one (or whose
    fetch failed) shouldn't have its reference point touched - only
    sources actually present in raw_by_source are updated."""
    delta, updated = pihole_monitor.aggregate_source_deltas(
        {"primary": 100, "secondary": 200},
        {"primary": 150},  # secondary absent this run
    )
    assert delta == 50  # primary only
    assert updated == {"primary": 150, "secondary": 200}  # secondary untouched


def test_main_dual_source_reset_does_not_mask_the_others_spike(isolated_state, settings):
    """Integration-level version of the same regression: a real spike on
    the primary instance must not be diluted by a simultaneous counter
    reset on the secondary, when both instances report the same device."""
    settings["PIHOLEMON_SECONDARY_URL"] = "http://ph2/"
    settings["PIHOLEMON_SECONDARY_PASSWORD"] = "pw2"
    settings["PIHOLEMON_MULTIPLIER"] = 2
    settings["PIHOLEMON_MIN_BLOCKED"] = 100

    devices_by_label = {
        "primary": [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")],
        "secondary": [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")],
    }
    # primary: real spike (1000 -> 3000). secondary: FTL restarted (1000 -> 5).
    blocked_by_label = {"primary": {"10.0.0.5": 3000}, "secondary": {"10.0.0.5": 5}}

    def _fetch_devices(self, max_clients):
        return devices_by_label[self.label]

    def _fetch_top_blocked(self, count):
        return blocked_by_label[self.label]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", _fetch_devices), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", _fetch_top_blocked), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {
            "last_raw": {"primary": 1000, "secondary": 1000},
            "history": [[1, 50], [1, 50]],  # baseline avg 50
        }})
        assert pihole_monitor.main() == 0

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    # The real signal (2000), not the raw-combined-first result (1005).
    assert call.kwargs["watched3"] == "2000"
    assert call.kwargs["watched4"] == "anomaly"

    state_after = pihole_monitor.load_state()["aa:bb:cc:dd:ee:01"]
    assert state_after["last_raw"] == {"primary": 3000, "secondary": 5}
    assert state_after["history"][-1] == [1, 2000]


def test_main_tolerates_pre_per_source_state_instead_of_crashing(isolated_state, settings):
    """Before this round, last_raw was a single number, not a per-source
    dict. A state file saved by that older version must not crash this
    version - it's treated the same as no prior reference point (every
    source bootstraps fresh this run) rather than raising."""
    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.5": 500}), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        # Legacy shape: last_raw is a plain int, not {"primary": ...}.
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {"last_raw": 1234, "history": [[1, 10], [1, 10]]}})
        assert pihole_monitor.main() == 0  # must not raise

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    assert call.kwargs["watched4"] == "normal"  # bootstrapping again, not an anomaly

    state_after = pihole_monitor.load_state()["aa:bb:cc:dd:ee:01"]
    assert state_after["last_raw"] == {"primary": 500}  # re-anchored in the new shape
    assert state_after["history"] == [[1, 10], [1, 10]]  # old baseline history untouched


def test_main_bootstrap_run_sets_last_raw_without_recording_a_delta(isolated_state, settings):
    """The first time a device is ever seen, there's no prior raw count to
    diff against - this run must establish the reference point (last_raw)
    for the next run, without fabricating a delta or evaluating an anomaly
    off one."""
    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.5": 5000}), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        assert pihole_monitor.main() == 0  # no prior save_state() call - genuinely first-ever run

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    assert call.kwargs["watched4"] == "normal"  # never an anomaly on a bootstrap run
    assert "unknown" in call.kwargs["extra"]

    state_after = pihole_monitor.load_state()
    assert state_after["aa:bb:cc:dd:ee:01"] == {"last_raw": {"primary": 5000}, "history": []}


def test_main_counter_reset_updates_last_raw_without_touching_history(isolated_state, settings):
    """A Pi-hole/FTL restart resets the raw counter, so this run's raw value
    can come back lower than what was last seen. That must reset the
    reference point for future deltas, but not corrupt the existing
    baseline history with a bogus negative or wrap-around delta."""
    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.5": 5}), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {"last_raw": {"primary": 1000}, "history": [[1, 10], [1, 10]]}})
        assert pihole_monitor.main() == 0

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    assert call.kwargs["watched4"] == "normal"

    state_after = pihole_monitor.load_state()
    # last_raw re-anchored to the post-restart value; the pre-restart
    # baseline history is preserved exactly, not wiped or corrupted.
    assert state_after["aa:bb:cc:dd:ee:01"] == {"last_raw": {"primary": 5}, "history": [[1, 10], [1, 10]]}


def test_main_returns_1_when_no_source_is_configured(isolated_state, settings):
    settings["PIHOLEMON_PRIMARY_URL"] = ""
    settings["PIHOLEMON_PRIMARY_PASSWORD"] = ""
    assert pihole_monitor.main() == 1


def test_main_marks_stats_incomplete_when_a_source_fails_to_authenticate(tmp_path, settings):
    """Also exercises the CONSIDER_ONLINE fallback (a non-int setting falls
    back to 300) alongside the per-source auth-failure branch, which needs
    per-label auth behavior rather than the isolated_state fixture's
    blanket auth=True."""
    settings["PIHOLEMON_SECONDARY_URL"] = "http://ph2/"
    settings["PIHOLEMON_SECONDARY_PASSWORD"] = "badpw"
    settings["PIHOLEMON_CONSIDER_ONLINE"] = "not-a-number"

    def _auth(self):
        return self.label == "primary"  # secondary fails to authenticate

    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]

    with patch.object(pihole_monitor, "STATE_FILE", str(tmp_path / "state.json")), \
         patch.object(pihole_monitor, "RESULT_FILE", str(tmp_path / "last_result.log")), \
         patch.object(pihole_monitor, "get_setting_value", side_effect=settings), \
         patch.object(pihole_monitor.PiholeSource, "auth", _auth), \
         patch.object(pihole_monitor.PiholeSource, "deauth", return_value=None), \
         patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.5": 999}), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {"last_raw": {"primary": 5}, "history": [[1, 1], [1, 1], [1, 1]]}})
        assert pihole_monitor.main() == 0

        instance = mock_plugin_objects.return_value
        (call,) = instance.add_object.call_args_list
        assert call.kwargs["watched4"] == "normal"  # secondary's auth failure marks stats incomplete
        # Untouched, including last_raw - state.
        assert pihole_monitor.load_state()["aa:bb:cc:dd:ee:01"] == {"last_raw": {"primary": 5}, "history": [[1, 1], [1, 1], [1, 1]]}


def test_main_links_offline_device_resolves_owner_skips_invalid_mac_and_tracks_unknown_ip(isolated_state, settings):
    """One run covering four branches at once: an offline device still
    gets its blocked traffic linked to its real MAC (not a bare IP), an
    online device gets its devOwner resolved via GraphQL, a device with an
    invalid hardware address is skipped entirely, and blocked traffic on
    an IP no device was ever seen on (FAKE_MAC off) is not written out,
    since primaryId maps to CurrentScan.scanMac and would create a bogus
    device whose "MAC" is the IP."""
    settings["PIHOLEMON_GET_OWNER"] = True
    settings["API_TOKEN"] = "tok"

    now = MagicMock()
    now.timestamp.return_value = 2_000_000

    devices = [
        {"hwaddr": "aa:bb:cc:dd:ee:01", "macVendor": "Acme",
         "ips": [{"ip": "10.0.0.1", "name": "online-dev", "lastSeen": 2_000_000 - 10}]},        # online
        {"hwaddr": "aa:bb:cc:dd:ee:02", "macVendor": "Acme",
         "ips": [{"ip": "10.0.0.2", "name": "offline-dev", "lastSeen": 2_000_000 - 10_000}]},   # offline
        {"hwaddr": "not-a-real-mac", "macVendor": "Acme",
         "ips": [{"ip": "10.0.0.3", "name": "bad-mac-dev", "lastSeen": 2_000_000 - 10}]},        # invalid MAC
    ]
    blocked = {"10.0.0.1": 5, "10.0.0.2": 5, "10.0.0.99": 5}  # .99: never any device's IP
    owner_resp = _resp({"data": {"devices": {"devices": [
        {"devMac": "aa:bb:cc:dd:ee:01", "devOwner": "Mauricio"}
    ]}}})

    with patch.object(pihole_monitor, "timeNowUTC", return_value=now), \
         patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=devices), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value=blocked), \
         patch("requests.post", return_value=owner_resp), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        assert pihole_monitor.main() == 0

    instance = mock_plugin_objects.return_value
    calls_by_primary_id = {c.kwargs["primaryId"]: c for c in instance.add_object.call_args_list}

    assert "owner: Mauricio" in calls_by_primary_id["aa:bb:cc:dd:ee:01"].kwargs["extra"]
    assert calls_by_primary_id["aa:bb:cc:dd:ee:02"].kwargs["foreignKey"] == "aa:bb:cc:dd:ee:02"
    assert "not-a-real-mac" not in calls_by_primary_id
    assert "10.0.0.99" not in calls_by_primary_id


def test_main_unknown_ip_uses_fake_mac_when_enabled(isolated_state, settings):
    """With FAKE_MAC on, blocked traffic on an IP Pi-hole never tied to a
    MAC is written out under the fake MAC derived from that IP (same as
    device import), never under the bare IP."""
    settings["PIHOLEMON_FAKE_MAC"] = True

    now = MagicMock()
    now.timestamp.return_value = 2_000_000

    with patch.object(pihole_monitor, "timeNowUTC", return_value=now), \
         patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=[]), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.99": 5}), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        assert pihole_monitor.main() == 0

    calls_by_primary_id = {c.kwargs["primaryId"]: c for c in mock_plugin_objects.return_value.add_object.call_args_list}

    assert "10.0.0.99" not in calls_by_primary_id
    assert calls_by_primary_id["fa:ce:00:00:00:01"].kwargs["foreignKey"] == "fa:ce:00:00:00:01"  # stubbed string_to_fake_mac


def test_main_flags_anomaly_against_an_all_zero_baseline(isolated_state, settings):
    """Regression guard: baseline == 0.0 is falsy in Python, so a naive
    `bool(... and baseline and ...)` check would silently exempt a device
    with a real, all-zero history - exactly the device most worth flagging
    the first time it blocks anything at all."""
    settings["PIHOLEMON_MULTIPLIER"] = 4
    settings["PIHOLEMON_MIN_BLOCKED"] = 1
    device = [_device_payload("aa:bb:cc:dd:ee:01", "10.0.0.5")]

    with patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=device), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={"10.0.0.5": 5}), \
         patch.object(pihole_monitor, "Plugin_Objects") as mock_plugin_objects:
        # last_raw=0 so this run's raw count (5) is also its delta.
        pihole_monitor.save_state({"aa:bb:cc:dd:ee:01": {"last_raw": {"primary": 0}, "history": [[1, 0], [1, 0], [1, 0]]}})  # genuinely never blocked before
        assert pihole_monitor.main() == 0

    instance = mock_plugin_objects.return_value
    (call,) = instance.add_object.call_args_list
    assert call.kwargs["watched4"] == "anomaly"
    assert "avg=0.0" in call.kwargs["extra"]
    assert "ratio=" not in call.kwargs["extra"]  # dividing by a zero baseline is skipped, not attempted


def test_main_applies_independent_verify_ssl_per_instance(isolated_state, settings):
    """PIHOLEMON_PRIMARY_VERIFY_SSL and PIHOLEMON_SECONDARY_VERIFY_SSL must
    reach each instance independently - a self-signed secondary shouldn't
    force verification off (or on) for the primary too."""
    settings["PIHOLEMON_SECONDARY_URL"] = "http://ph2/"
    settings["PIHOLEMON_SECONDARY_PASSWORD"] = "pw2"
    settings["PIHOLEMON_PRIMARY_VERIFY_SSL"] = True
    settings["PIHOLEMON_SECONDARY_VERIFY_SSL"] = False

    seen_verify_ssl = {}

    def _auth(self):
        seen_verify_ssl[self.label] = self.verify_ssl
        return True

    with patch.object(pihole_monitor.PiholeSource, "auth", _auth), \
         patch.object(pihole_monitor.PiholeSource, "fetch_devices", return_value=[]), \
         patch.object(pihole_monitor.PiholeSource, "fetch_top_blocked_clients", return_value={}), \
         patch.object(pihole_monitor, "Plugin_Objects"):
        assert pihole_monitor.main() == 0

    assert seen_verify_ssl == {"primary": True, "secondary": False}
