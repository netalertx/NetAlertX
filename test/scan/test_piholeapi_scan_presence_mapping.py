"""
PIHOLEAPI's config.json must route the plugin's helpVal4 to
CurrentScan.scanPresence (server/plugin.py:process_plugin_events()).

pihole_api_scan.py writes helpVal4 '0' for a device it imports only because
PIHOLEAPI_GET_OFFLINE is on. Without the mapping, scanPresence falls back to
its default 1 and that offline device is marked as present.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import (  # noqa: E402
    make_plugin_db,
    make_plugin_dict,
    make_plugin_event_row,
    CREATE_CURRENT_SCAN,
)

import plugin  # noqa: E402
from plugin import process_plugin_events  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parents[2] / "server" / "plugins" / "pihole_api_scan" / "config.json"


def _piholeapi_plugin() -> dict:
    """Return a plugin dict with PIHOLEAPI's real CurrentScan mapping from its config.json."""
    config = json.loads(CONFIG_PATH.read_text())
    plugin_dict = make_plugin_dict(config["unique_prefix"])
    plugin_dict["mapped_to_table"] = config["mapped_to_table"]
    plugin_dict["database_column_definitions"] = config["database_column_definitions"]
    return plugin_dict


def test_offline_row_does_not_assert_presence(monkeypatch):
    """A PIHOLEAPI row with helpVal4 '0' lands in CurrentScan with scanPresence 0.

    process_plugin_events() unconditionally calls updateState(...) when the
    target table is CurrentScan (server/plugin.py) - stub it out so this pure
    data-mapping test can't write real application state to disk."""
    monkeypatch.setattr(plugin, "updateState", lambda *args, **kwargs: None)
    db, conn = make_plugin_db()
    conn.execute(CREATE_CURRENT_SCAN)
    conn.commit()
    try:
        row = make_plugin_event_row("PIHOLEAPI", "0a:60:b8:ad:b6:9d", secondary_id="192.168.178.64", help_val4="0")
        process_plugin_events(db, _piholeapi_plugin(), [row])

        assert conn.execute("SELECT scanMac, scanPresence FROM CurrentScan").fetchall() == [("0a:60:b8:ad:b6:9d", 0)]
    finally:
        conn.close()
