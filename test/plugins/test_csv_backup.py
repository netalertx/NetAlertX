"""
Tests for csv_backup/script.py (NetAlertX modules stubbed when run outside the container).

    pytest test/plugins/test_csv_backup.py -v
"""

import os
import sqlite3
import sys
import tempfile
import types
from unittest.mock import MagicMock, patch

_tmp_log = tempfile.mkdtemp()
_stubbed_module_names = []


def _stub(name: str, **attrs):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        _stubbed_module_names.append(name)


_stub("pytz", timezone=lambda tz: tz)
_stub("conf")
_stub("const", logPath=_tmp_log)
_stub("logger", mylog=lambda *a: None, Logger=MagicMock)
_stub("helper", get_setting_value=lambda k: "")
_stub("utils")
_stub("utils.datetime_utils", timeNowUTC=MagicMock())
_stub("database", get_temp_db_connection=MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server", "plugins", "csv_backup"))

import script  # noqa: E402

for _name in _stubbed_module_names:
    sys.modules.pop(_name, None)


def test_null_columns_are_written_empty(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE Devices (devMac TEXT, devName TEXT, devFQDN TEXT)")
    conn.execute("INSERT INTO Devices VALUES ('aa:bb:cc:00:11:01', 'router', NULL)")

    argv = ["script.py", "overwrite=TRUE", f"location={tmp_path}"]
    with patch.object(script, "get_temp_db_connection", return_value=conn), patch.object(sys, "argv", argv):
        script.main()

    rows = (tmp_path / "devices.csv").read_text().splitlines()
    assert rows[1] == '"aa:bb:cc:00:11:01","router",""'
