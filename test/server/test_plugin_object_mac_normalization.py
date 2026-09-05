"""
Tests for centralized MAC-case normalization in plugin_object_class.

Regression coverage for https://github.com/netalertx/NetAlertX/issues/1775:
plugin authors are responsible for calling normalize_mac() themselves before
writing a MAC as primaryId, and it's easy for one parsing branch in one
plugin to forget (see server/plugins/snmp_discovery) - producing a device
reported under two different MAC cases and spurious connect/disconnect
events, since plugin_object_class.idsHash (used to detect new/missing
objects across scan cycles) is a case-sensitive hash of primaryId.

plugin_object_class now normalizes primaryId itself as a generic safety
net, via utils.plugin_utils.primary_id_is_mac(), whenever the owning
plugin's config.json marks objectPrimaryId as a MAC (true for every
device-scanning plugin - arp_scan, snmp_discovery, sync, etc. - and false
for publishers/exporters/other non-scanning plugins, whose primaryId is not
a MAC and must not be silently rewritten).

Run from inside the NetAlertX container - server/plugin.py isn't importable
standalone outside it (real conf/database/api imports).

    pytest "test/server/test_plugin_object_mac_normalization.py" -v
"""

import os
import sys

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import make_plugin_event_row  # noqa: E402

from plugin import plugin_object_class  # noqa: E402
from utils.plugin_utils import primary_id_is_mac  # noqa: E402

PREFIX = "TESTPLG"


def _scanner_plugin(prefix=PREFIX):
    """Shaped like a real device-scanning plugin's config.json
    (e.g. snmp_discovery, arp_scan): objectPrimaryId marked as a MAC."""
    return {
        "unique_prefix": prefix,
        "settings": [
            {"function": "WATCH", "value": ["watchedValue1", "watchedValue2"]},
        ],
        "mapped_to_table": "CurrentScan",
        "database_column_definitions": [
            {"column": "objectPrimaryId", "mapped_to_column": "scanMac", "type": "device_mac"},
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP", "type": "device_ip"},
        ],
    }


def _non_scanner_plugin(prefix=PREFIX):
    """Shaped like a non-scanning plugin (publisher/exporter): no
    CurrentScan mapping, primaryId is not a MAC."""
    return {
        "unique_prefix": prefix,
        "settings": [],
    }


class TestScannerPluginNormalizesMacCase:
    def test_uppercase_primary_id_is_normalized(self):
        row = make_plugin_event_row(PREFIX, "AA:BB:CC:DD:EE:FF")
        obj = plugin_object_class(_scanner_plugin(), row)
        assert obj.primaryId == "aa:bb:cc:dd:ee:ff"

    def test_hyphenated_primary_id_is_normalized_to_colon_form(self):
        row = make_plugin_event_row(PREFIX, "AA-BB-CC-DD-EE-FF")
        obj = plugin_object_class(_scanner_plugin(), row)
        assert obj.primaryId == "aa:bb:cc:dd:ee:ff"

    def test_idshash_agrees_across_case_variants(self):
        """The actual bug: two readings of the same device that differ only
        in MAC case must produce the same idsHash, or the scan-cycle diff
        engine treats them as different objects (spurious connect/disconnect)."""
        upper = plugin_object_class(_scanner_plugin(), make_plugin_event_row(PREFIX, "AA:BB:CC:DD:EE:FF"))
        lower = plugin_object_class(_scanner_plugin(), make_plugin_event_row(PREFIX, "aa:bb:cc:dd:ee:ff"))
        assert upper.idsHash == lower.idsHash


class TestNonScannerPluginLeavesPrimaryIdAlone:
    def test_primary_id_untouched(self):
        """A publisher/exporter's primaryId isn't a MAC - must not be run
        through normalize_mac(), which would silently mangle it."""
        row = make_plugin_event_row(PREFIX, "Some-Mixed-Case-ID")
        obj = plugin_object_class(_non_scanner_plugin(), row)
        assert obj.primaryId == "Some-Mixed-Case-ID"


def test_helper_detects_scanner_vs_non_scanner_plugins():
    assert primary_id_is_mac(_scanner_plugin()) is True
    assert primary_id_is_mac(_non_scanner_plugin()) is False
