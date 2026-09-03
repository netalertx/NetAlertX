"""Tests for the SNMP discovery plugin (server/plugins/snmp_discovery/script.py).

Regression test for https://github.com/netalertx/NetAlertX/issues/1775:
the primary "mib-2.3.1.1.2.15..." parsing branch built the MAC directly
from snmpwalk's raw (uppercase) hex dump without going through
normalize_mac(), unlike the plugin's other two parsing branches - so the
same device could be reported under two different MAC cases depending on
which SNMP output format matched that scan cycle, producing spurious
connect/disconnect events for what is really one device.

Run from inside the NetAlertX container, or locally - NetAlertX-specific
modules are stubbed out automatically before the script is imported.

    pytest "test/plugins/test_snmp_discovery.py" -v
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_snmp_discovery_module():
    missing_module = object()
    previous_modules = {}

    def stub(name, **attributes):
        previous_modules[name] = sys.modules.get(name, missing_module)
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module

    stub(
        "plugin_helper",
        Plugin_Objects=MagicMock,
        handleEmpty=lambda v: v if v not in (None, "") else "(unknown)",
        normalize_mac=lambda mac: mac.strip().lower().replace("-", ":"),
    )
    stub("logger", mylog=MagicMock(), Logger=MagicMock())
    stub("helper", get_setting_value=MagicMock(return_value=60))
    stub("const", logPath="/tmp")
    stub("conf", tz=None)
    stub("pytz", timezone=MagicMock(return_value="UTC"))

    module_path = Path(__file__).resolve().parents[2] / "server" / "plugins" / "snmp_discovery" / "script.py"
    spec = importlib.util.spec_from_file_location("snmp_discovery", module_path)
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


snmp_discovery = _load_snmp_discovery_module()

ROUTER_CMD = "snmpwalk -v2c -c public -Oqn 192.168.1.14 .1.3.6.1.2.1.3.1.1.2"


def _run_main_with_output(output):
    """Run main() with subprocess.check_output faked to return `output`,
    and Plugin_Objects faked so add_object() calls can be inspected."""
    plugin_objects = MagicMock()

    with patch.object(snmp_discovery, "Plugin_Objects", return_value=plugin_objects), \
         patch("subprocess.check_output", return_value=output), \
         patch.object(sys, "argv", ["script.py", f"routers={ROUTER_CMD}"]):
        snmp_discovery.main()

    return plugin_objects


def test_numeric_oid_branch_normalizes_mac_case():
    """The branch that historically skipped normalize_mac() (GH #1775)."""
    output = 'mib-2.3.1.1.2.15.1.192.168.1.14 "2C F4 32 18 61 43 "\n'

    plugin_objects = _run_main_with_output(output)

    assert plugin_objects.add_object.call_count == 1
    call_kwargs = plugin_objects.add_object.call_args_list[0].kwargs
    assert call_kwargs["primaryId"] == "2c:f4:32:18:61:43"
    assert call_kwargs["foreignKey"] == "2c:f4:32:18:61:43"


def test_numeric_oid_branch_tolerates_repeated_whitespace_between_bytes():
    """Some snmpwalk output has runs of repeated spaces or embedded tabs
    between hex bytes rather than a single space. Splitting on a literal
    single space (the pre-fix behaviour) turns each extra space into an
    empty token, which normalize_mac() then zero-pads into a fabricated
    "00" octet, and leaves a tab glued to its neighboring byte instead of
    splitting it out - silently corrupting the MAC rather than just its
    case."""
    output = 'mib-2.3.1.1.2.15.1.192.168.1.14 "2C  F4\t32 18 61 43 "\n'

    plugin_objects = _run_main_with_output(output)

    assert plugin_objects.add_object.call_count == 1
    call_kwargs = plugin_objects.add_object.call_args_list[0].kwargs
    assert call_kwargs["primaryId"] == "2c:f4:32:18:61:43"
    assert call_kwargs["foreignKey"] == "2c:f4:32:18:61:43"


def test_all_three_output_formats_agree_on_mac_case():
    """The same physical MAC, reported through each of the plugin's three
    supported snmpwalk output formats, must normalize to the same devMac -
    otherwise NetAlertX's plugin-object diffing (idsHash in server/plugin.py)
    treats them as different devices and fires spurious connect/disconnect
    events for what is really one device."""
    outputs = [
        'mib-2.3.1.1.2.15.1.192.168.1.14 "2C F4 32 18 61 43 "\n',
        "IP-MIB::ipNetToMediaPhysAddress.17.192.168.1.14 = STRING: 2C:F4:32:18:61:43\n",
        "ipNetToMediaPhysAddress[3][192.168.1.14] 2C:F4:32:18:61:43\n",
    ]

    macs_seen = set()
    for output in outputs:
        plugin_objects = _run_main_with_output(output)
        assert plugin_objects.add_object.call_count == 1
        macs_seen.add(plugin_objects.add_object.call_args_list[0].kwargs["primaryId"])

    assert macs_seen == {"2c:f4:32:18:61:43"}
