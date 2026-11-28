"""
Tests for csv_backup/script.py.

    pytest test/plugins/test_csv_backup.py -v
"""

import csv
import importlib.util
import os
import sys
import tempfile
import types
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db_test_helpers import insert_device, make_db  # noqa: E402

_tmp_log = tempfile.mkdtemp()


def _module(name: str, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# Stand-ins for the plugin's imports, only while it loads. It is loaded under
# its own name because other plugin tests import their own "script" module.
_plugin_modules = {
    "pytz": _module("pytz", timezone=lambda tz: tz),
    "conf": _module("conf"),
    "const": _module("const", logPath=_tmp_log),
    "logger": _module("logger", mylog=lambda *a: None, Logger=MagicMock),
    "helper": _module("helper", get_setting_value=lambda k: ""),
    "utils": _module("utils"),
    "utils.datetime_utils": _module("utils.datetime_utils", timeNowUTC=MagicMock()),
    "database": _module("database", get_temp_db_connection=MagicMock()),
}
_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "server", "plugins", "csv_backup", "script.py")
_spec = importlib.util.spec_from_file_location("csv_backup_script", _SCRIPT_PATH)
script = importlib.util.module_from_spec(_spec)
with patch.dict(sys.modules, _plugin_modules):
    _spec.loader.exec_module(script)


def _backup_rows(tmp_path, conn):
    argv = ["script.py", "overwrite=TRUE", f"location={tmp_path}"]
    with patch.object(script, "get_temp_db_connection", return_value=conn), patch.object(sys, "argv", argv):
        script.main()
    with open(tmp_path / "devices.csv", newline="") as f:
        reader = csv.reader(f)
        header = [col.strip('"') for col in next(reader)]
        return [dict(zip(header, (v.strip('"') for v in row))) for row in reader]


def test_null_columns_are_written_empty(tmp_path):
    conn = make_db()
    insert_device(conn.cursor(), "aa:bb:cc:00:11:01", alert_down=None)

    row = _backup_rows(tmp_path, conn)[0]
    assert row["devAlertDown"] == ""
    assert row["devFQDN"] == ""


def test_falsy_values_are_kept(tmp_path):
    conn = make_db()
    insert_device(conn.cursor(), "aa:bb:cc:00:11:02", alert_down=0)

    row = _backup_rows(tmp_path, conn)[0]
    assert row["devAlertDown"] == "0"
    assert row["devFavorite"] == "0"
    assert row["devIsArchived"] == "0"
