"""
Tests for nbtscan_scan/nbtscan.py output parsing in execute_name_lookup().

    pytest test/plugins/test_nbtscan_parsing.py -v
"""

import os
import sys
import tempfile
import types
from unittest.mock import MagicMock, patch

_tmp_log = tempfile.mkdtemp()

_stubbed_module_names = []


def _stub(name: str, **attrs):
    """Register a placeholder module in sys.modules if the real one is absent."""
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        _stubbed_module_names.append(name)


_stub("pytz", timezone=lambda tz: tz)
_stub("conf", tz=None)
_stub("const", logPath=_tmp_log)
_stub("plugin_helper", Plugin_Objects=MagicMock)
_stub("logger", mylog=lambda *a: None, Logger=MagicMock)
_stub("helper", get_setting_value=lambda k, default="": "")
_stub("models")
_stub("models.device_instance", DeviceInstance=MagicMock)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server", "plugins", "nbtscan_scan"))

import nbtscan  # noqa: E402

for _name in _stubbed_module_names:
    sys.modules.pop(_name, None)

IP = "192.168.129.11"

HEADER = "Doing NBT name scan for addresses from 192.168.129.11\n\n"
TABLE_HEADER = (
    "IP address       NetBIOS Name     Server    User             MAC address      \n"
    "------------------------------------------------------------------------------\n"
)


def _lookup(output, ip=IP):
    """Run execute_name_lookup with nbtscan's output mocked."""
    with patch.object(nbtscan.subprocess, "check_output", return_value=output):
        return nbtscan.execute_name_lookup(ip, 10)


def test_valid_result_row_returns_name():
    output = HEADER + TABLE_HEADER + f"{IP}    MYPC             <server>  <unknown>        aa:bb:cc:dd:ee:ff\n"
    assert _lookup(output) == ("MYPC", "")


def test_sendto_failed_line_is_not_a_name():
    output = HEADER + f"{IP}\tSendto failed\n"
    assert _lookup(output) == ("", "")


def test_sendto_failed_line_with_spaces_is_not_a_name():
    output = HEADER + f"{IP}    Sendto failed\n"
    assert _lookup(output) == ("", "")


def test_no_result_row_returns_empty():
    output = HEADER + TABLE_HEADER
    assert _lookup(output) == ("", "")


def test_ip_must_be_first_field_not_substring():
    output = HEADER + TABLE_HEADER + "192.168.129.110   OTHERPC          <server>  <unknown>        aa:bb:cc:dd:ee:ff\n"
    assert _lookup(output) == ("", "")


def test_unknown_placeholder_name_rejected():
    output = HEADER + TABLE_HEADER + f"{IP}    <unknown>        <server>  <unknown>        aa:bb:cc:dd:ee:ff\n"
    assert _lookup(output) == ("", "")


def test_overlong_name_rejected():
    output = HEADER + TABLE_HEADER + f"{IP}    {'A' * 20}  <server>  <unknown>        aa:bb:cc:dd:ee:ff\n"
    assert _lookup(output) == ("", "")
