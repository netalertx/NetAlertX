"""
Tests for Freebox plugin (freebox.py).

freebox.py is imported directly. Its module-level side effects
(get_setting_value, Logger, Plugin_Objects) are patched out before the
first import so no live config reads, log files, or result files are
created during tests.
"""

import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SERVER = os.path.join(_ROOT, "server")
_PLUGINS = os.path.join(_ROOT, "server", "plugins")
_PLUGIN_DIR = os.path.join(_ROOT, "server", "plugins", "freebox")

for _p in [_ROOT, _SERVER, _PLUGINS, _PLUGIN_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Import freebox with module-level side effects patched
# ---------------------------------------------------------------------------
# freebox.py calls get_setting_value(), Logger(), and Plugin_Objects() at
# module level. Patching these before the first import prevents live config
# reads, log-file creation, and result-file creation during tests.

with patch("helper.get_setting_value", return_value="UTC"), \
     patch("logger.Logger"), \
     patch("plugin_helper.Plugin_Objects"):
    import freebox  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _l3(addr="192.168.1.10", reachable=True, active=None, last_time_reachable=1700000000):
    entry = {"addr": addr, "reachable": reachable, "last_time_reachable": last_time_reachable}
    if active is not None:
        entry["active"] = active
    return entry


def _host(mac="aa:bb:cc:dd:ee:01", active=True, l3connectivities=None,
          name="testdevice", vendor="TestVendor", host_type="workstation"):
    host = {
        "l2ident": {"id": mac},
        "primary_name": name,
        "vendor_name": vendor,
        "host_type": host_type,
    }
    if active is not None:
        host["active"] = active
    if l3connectivities is not None:
        host["l3connectivities"] = l3connectivities
    return host


# ===========================================================================
# select_l3_entries_for_presence - pure decision function
# ===========================================================================

class TestSelectL3EntriesForPresence:

    def test_prefers_reachable_entries_when_available(self):
        l3_entries = [_l3("10.0.0.1", reachable=True), _l3("10.0.0.2", reachable=False)]
        host = _host(l3connectivities=l3_entries)
        result = freebox.select_l3_entries_for_presence(host)
        assert [e["addr"] for e in result] == ["10.0.0.1"]

    def test_returns_all_reachable_entries_unchanged(self):
        """Today's existing multi-IP-per-device behavior (e.g. IPv4 + IPv6
        both reachable) must be preserved exactly - one row per reachable
        address, not collapsed to a single fallback."""
        l3_entries = [_l3("10.0.0.1", reachable=True), _l3("fe80::1", reachable=True)]
        host = _host(l3connectivities=l3_entries)
        result = freebox.select_l3_entries_for_presence(host)
        assert {e["addr"] for e in result} == {"10.0.0.1", "fe80::1"}

    def test_falls_back_to_unreachable_entry_when_host_active(self):
        """The exact bug from issue #1828: host.active=True but every L3
        address reports reachable=False must still report presence, using
        the best-available (even if currently unreachable) address."""
        host = _host(active=True, l3connectivities=[_l3("10.0.0.1", reachable=False)])
        result = freebox.select_l3_entries_for_presence(host)
        assert [e["addr"] for e in result] == ["10.0.0.1"]

    def test_returns_empty_when_host_not_active(self):
        """A genuinely absent host (active=False) must still be skipped -
        this fallback must not mask a real disconnection."""
        host = _host(active=False, l3connectivities=[_l3("10.0.0.1", reachable=False)])
        result = freebox.select_l3_entries_for_presence(host)
        assert result == []

    def test_missing_active_key_defaults_to_present(self):
        """Fail open if the API unexpectedly omits 'active', rather than
        silently reintroducing the false-disconnect bug this exists to fix."""
        host = _host(active=None, l3connectivities=[_l3("10.0.0.1", reachable=False)])
        result = freebox.select_l3_entries_for_presence(host)
        assert [e["addr"] for e in result] == ["10.0.0.1"]

    def test_prefers_active_entry_among_unreachable_when_available(self):
        """Each l3connectivities entry has its own 'active' flag, independent
        of 'reachable' (per the Freebox API's LanHostL3Connectivity schema) -
        when nothing is reachable, an entry Freebox still marks active is a
        better guess than an arbitrary stale one. The active entry is placed
        second on purpose, so a naive "just take the first one" fallback
        would fail this test."""
        l3_entries = [_l3("10.0.0.1", reachable=False, active=False),
                      _l3("10.0.0.2", reachable=False, active=True)]
        host = _host(active=True, l3connectivities=l3_entries)
        result = freebox.select_l3_entries_for_presence(host)
        assert [e["addr"] for e in result] == ["10.0.0.2"]

    def test_falls_back_to_first_entry_when_none_are_active_either(self):
        l3_entries = [_l3("10.0.0.1", reachable=False), _l3("10.0.0.2", reachable=False)]
        host = _host(active=True, l3connectivities=l3_entries)
        result = freebox.select_l3_entries_for_presence(host)
        assert [e["addr"] for e in result] == ["10.0.0.1"]

    def test_empty_entry_when_active_but_no_l3_entries_at_all(self):
        """No fabricated '0.0.0.0' address or epoch-zero timestamp when there's
        genuinely no L3 data - an empty dict lets main() leave secondaryId/
        watched4 blank instead of writing misleading placeholder values."""
        host = _host(active=True, l3connectivities=[])
        result = freebox.select_l3_entries_for_presence(host)
        assert result == [{}]

    def test_empty_entry_when_l3connectivities_missing_entirely(self):
        host = _host(active=True)  # l3connectivities key omitted entirely
        assert "l3connectivities" not in host
        result = freebox.select_l3_entries_for_presence(host)
        assert result == [{}]

    def test_empty_entry_when_l3connectivities_not_a_list(self):
        host = _host(active=True)
        host["l3connectivities"] = "not-a-list"
        result = freebox.select_l3_entries_for_presence(host)
        assert result == [{}]


# ===========================================================================
# main() - end-to-end row emission
# ===========================================================================

class TestMainHostLoop:

    _SETTINGS = {
        "FREEBOX_address": "mafreebox.freebox.fr",
        "FREEBOX_api_version": 6,
        "FREEBOX_api_port": 443,
    }

    def _patch_settings(self):
        return patch.object(freebox, "get_setting_value", side_effect=lambda k: self._SETTINGS[k])

    def test_reporter_scenario_active_but_unreachable_still_emits(self):
        """Regression for issue #1828: a host with active=True but every L3
        address reachable=False must still get a row emitted, not be
        silently dropped (which the scan pipeline would otherwise read as
        'device gone' and fire a false Disconnected/Flapping event)."""
        hosts = [_host(mac="aa:bb:cc:dd:ee:01", active=True,
                       l3connectivities=[_l3("10.0.0.1", reachable=False)])]
        mock_po = MagicMock()

        with self._patch_settings(), \
             patch.object(freebox, "get_device_data", AsyncMock(return_value=(None, hosts))), \
             patch.object(freebox, "plugin_objects", mock_po):
            result = freebox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 1
        call = mock_po.add_object.call_args_list[0]
        assert call.kwargs["primaryId"] == "aa:bb:cc:dd:ee:01"
        assert call.kwargs["secondaryId"] == "10.0.0.1"

    def test_inactive_host_still_not_emitted(self):
        """Regression guard: a genuinely absent host must not start being
        reported as present as a side effect of fixing #1828."""
        hosts = [_host(mac="aa:bb:cc:dd:ee:02", active=False,
                       l3connectivities=[_l3("10.0.0.2", reachable=False)])]
        mock_po = MagicMock()

        with self._patch_settings(), \
             patch.object(freebox, "get_device_data", AsyncMock(return_value=(None, hosts))), \
             patch.object(freebox, "plugin_objects", mock_po):
            result = freebox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 0

    def test_active_host_no_l3_entries_emits_blank_ip_and_timestamp(self):
        """A host with active=True but no l3connectivities at all still gets
        a presence row (primaryId/MAC alone is enough to assert presence),
        but must not fabricate a '0.0.0.0' address or an epoch-zero
        'last seen' timestamp - both would be misleading for data we don't
        actually have."""
        hosts = [_host(mac="aa:bb:cc:dd:ee:05", active=True, l3connectivities=[])]
        mock_po = MagicMock()

        with self._patch_settings(), \
             patch.object(freebox, "get_device_data", AsyncMock(return_value=(None, hosts))), \
             patch.object(freebox, "plugin_objects", mock_po):
            result = freebox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 1
        call = mock_po.add_object.call_args_list[0]
        assert call.kwargs["secondaryId"] == ""
        assert call.kwargs["watched4"] == ""

    def test_reachable_host_unchanged(self):
        """Regression guard: the common/working case (at least one reachable
        L3 address) must be unaffected by this fix."""
        hosts = [_host(mac="aa:bb:cc:dd:ee:03", active=True,
                       l3connectivities=[_l3("10.0.0.3", reachable=True)])]
        mock_po = MagicMock()

        with self._patch_settings(), \
             patch.object(freebox, "get_device_data", AsyncMock(return_value=(None, hosts))), \
             patch.object(freebox, "plugin_objects", mock_po):
            result = freebox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 1
        assert mock_po.add_object.call_args_list[0].kwargs["secondaryId"] == "10.0.0.3"

    def test_unknown_mac_still_skipped(self):
        host = _host(active=True, l3connectivities=[_l3("10.0.0.4", reachable=False)])
        host["l2ident"] = {}
        mock_po = MagicMock()

        with self._patch_settings(), \
             patch.object(freebox, "get_device_data", AsyncMock(return_value=(None, [host]))), \
             patch.object(freebox, "plugin_objects", mock_po):
            result = freebox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 0
