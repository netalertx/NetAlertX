"""
Tests for the Devices filterable-columns registry (server/db/device_filter_columns.py)
and its two generated consumers: const.sql_devices_filters and ui_settings/config.json's
columns_filters.options[] - see device-filter-column-registry.md.

Four things are tested:
1. build_devices_filters_sql() produces correct query results for both the generic
   column shape and the devParentMAC special-case shape, and covers every registry
   column.
2. Every registry label_key exists as a real key in en_us.json.
3. ui_settings/config.json's columns_filters.options[] exactly matches the registry's
   label_keys, in registry order (the drift guard - fails if someone edits the
   registry and forgets to run the sync script).
4. sync_device_filter_columns_config.py is idempotent and a no-op against the
   current (already-synced) config.json.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from const import NULL_EQUIVALENTS_SQL  # noqa: E402
from db.device_filter_columns import DEVICE_FILTER_COLUMNS, build_devices_filters_sql  # noqa: E402
from db.sync_device_filter_columns_config import sync_columns_filters_options  # noqa: E402
from db_test_helpers import make_db, insert_device_from_dict, make_device_dict  # noqa: E402

_EN_US_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "front", "php", "templates", "language", "en_us.json"
)
_UI_SETTINGS_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "server", "plugins", "ui_settings", "config.json"
)


class TestGeneratorCorrectness:
    def test_generic_block_returns_right_rows(self):
        """A column with no label_join resolves columnValue/columnLabel to its own value."""
        conn = make_db()
        insert_device_from_dict(conn, make_device_dict("aa:bb:cc:dd:ee:01", devOwner="Alice"))
        insert_device_from_dict(conn, make_device_dict("aa:bb:cc:dd:ee:02", devOwner=""))

        sql = build_devices_filters_sql(NULL_EQUIVALENTS_SQL)
        rows = conn.execute(sql).fetchall()
        owner_rows = [r for r in rows if r["columnName"] == "devOwner"]

        assert len(owner_rows) == 1
        assert owner_rows[0]["columnValue"] == "Alice"
        assert owner_rows[0]["columnLabel"] == "Alice"

    def test_parent_mac_block_resolves_parent_name_as_label(self):
        """devParentMAC's columnLabel is the parent device's devName, not its MAC."""
        conn = make_db()
        insert_device_from_dict(conn, make_device_dict("aa:bb:cc:dd:ee:01", devName="Router", devParentMAC=""))
        insert_device_from_dict(conn, make_device_dict(
            "aa:bb:cc:dd:ee:02", devName="Laptop", devParentMAC="aa:bb:cc:dd:ee:01",
        ))

        sql = build_devices_filters_sql(NULL_EQUIVALENTS_SQL)
        rows = conn.execute(sql).fetchall()
        parent_mac_rows = [r for r in rows if r["columnName"] == "devParentMAC"]

        assert len(parent_mac_rows) == 1
        assert parent_mac_rows[0]["columnValue"] == "aa:bb:cc:dd:ee:01"
        assert parent_mac_rows[0]["columnLabel"] == "Router"

    def test_parent_mac_block_falls_back_to_mac_when_parent_unknown(self):
        """If the parent MAC doesn't match any Devices row, columnLabel falls back to the raw MAC."""
        conn = make_db()
        insert_device_from_dict(conn, make_device_dict(
            "aa:bb:cc:dd:ee:02", devParentMAC="aa:bb:cc:dd:ee:99",
        ))

        sql = build_devices_filters_sql(NULL_EQUIVALENTS_SQL)
        rows = conn.execute(sql).fetchall()
        parent_mac_rows = [r for r in rows if r["columnName"] == "devParentMAC"]

        assert len(parent_mac_rows) == 1
        assert parent_mac_rows[0]["columnLabel"] == "aa:bb:cc:dd:ee:99"

    def test_every_registry_column_appears_in_generated_sql(self):
        """Every DEVICE_FILTER_COLUMNS entry has a block in the generated SQL - catches a
        registry entry silently dropped by the generator loop."""
        sql = build_devices_filters_sql(NULL_EQUIVALENTS_SQL)
        for column_name in DEVICE_FILTER_COLUMNS:
            assert f"'{column_name}' AS columnName" in sql, f"{column_name} missing from generated SQL"


class TestRegistryToLanguageFileConsistency:
    def test_every_label_key_exists_in_en_us_json(self):
        with open(_EN_US_JSON_PATH, encoding="utf-8") as f:
            en_us = json.load(f)

        for column_name, spec in DEVICE_FILTER_COLUMNS.items():
            assert spec["label_key"] in en_us, (
                f"{column_name}'s label_key {spec['label_key']!r} is missing from en_us.json"
            )


class TestRegistryToConfigDriftGuard:
    def test_config_options_match_registry_in_order(self):
        with open(_UI_SETTINGS_CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)

        columns_filters = next(
            s for s in config["settings"] if s.get("function") == "columns_filters"
        )
        expected = [spec["label_key"] for spec in DEVICE_FILTER_COLUMNS.values()]
        assert columns_filters["options"] == expected, (
            "ui_settings/config.json's columns_filters.options[] is out of sync with "
            "DEVICE_FILTER_COLUMNS - run server/db/sync_device_filter_columns_config.py"
        )


class TestSyncScriptIdempotency:
    def test_no_diff_against_current_already_synced_config(self, tmp_path):
        """Running the sync script against the real, already-correct config.json
        produces no change - proves the sync script's output format matches the
        hand-maintained array's existing format exactly, not just its content."""
        tmp_config = tmp_path / "config.json"
        tmp_config.write_text(
            open(_UI_SETTINGS_CONFIG_PATH, encoding="utf-8").read(), encoding="utf-8"
        )

        changed = sync_columns_filters_options(str(tmp_config))

        assert changed is False
        assert tmp_config.read_text(encoding="utf-8") == open(
            _UI_SETTINGS_CONFIG_PATH, encoding="utf-8"
        ).read()

    def test_running_twice_is_stable(self, tmp_path):
        """A second run after a real change produces no further diff."""
        tmp_config = tmp_path / "config.json"
        with open(_UI_SETTINGS_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        columns_filters = next(
            s for s in data["settings"] if s.get("function") == "columns_filters"
        )
        columns_filters["options"] = list(reversed(columns_filters["options"]))
        tmp_config.write_text(json.dumps(data, indent=2), encoding="utf-8")

        first_run_changed = sync_columns_filters_options(str(tmp_config))
        content_after_first_run = tmp_config.read_text(encoding="utf-8")

        second_run_changed = sync_columns_filters_options(str(tmp_config))
        content_after_second_run = tmp_config.read_text(encoding="utf-8")

        assert first_run_changed is True
        assert second_run_changed is False
        assert content_after_first_run == content_after_second_run
