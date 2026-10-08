"""
Tests for the Sources tab's Field View backend (server/db/plugin_field_views.py).

Four things are tested:
1. get_plugin_columns_for_field() correctness against a fabricated plugin list -
   every column role, both exclusion reasons, and that matching is on
   mapped_to_column, not the advisory type tag.
2. The MAC-identity invariant holds for every real, participating plugin.
3. The IP-discovery structural check holds against the real plugin inventory,
   and dockerfdisc/wificanary are excluded for their documented reasons.
4. get_all_device_field_views()'s identity-based cache.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))

from db.plugin_field_views import (  # noqa: E402
    DEVICE_FIELD_VIEWS,
    build_field_views_payload,
    get_all_device_field_views,
    get_plugin_columns_for_field,
)
from utils.plugin_utils import get_plugins_configs  # noqa: E402


def _plugin(prefix, primary_mapped_to="scanMac", extra_columns=None):
    """Build a fake CurrentScan-mapped plugin dict for get_plugin_columns_for_field() tests."""
    columns = [{"column": "objectPrimaryId", "mapped_to_column": primary_mapped_to}]
    if extra_columns:
        columns.extend(extra_columns)
    return {
        "unique_prefix": prefix,
        "mapped_to_table": "CurrentScan",
        "database_column_definitions": columns,
    }


class TestGetPluginColumnsForFieldCorrectness:
    def test_matches_objectSecondaryId(self):
        plugins = [_plugin("A", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP", "type": "device_ip"},
        ])]
        assert get_plugin_columns_for_field(plugins, "ip") == [("A", "objectSecondaryId")]

    def test_matches_watchedValue_role_regardless_of_type_tag(self):
        """Matching is on mapped_to_column, not the advisory type tag - a mislabeled
        column (type: 'label' on an actual scanLastIP mapping) must still be included."""
        plugins = [_plugin("B", extra_columns=[
            {"column": "watchedValue2", "mapped_to_column": "scanLastIP", "type": "label"},
        ])]
        assert get_plugin_columns_for_field(plugins, "ip") == [("B", "watchedValue2")]

    def test_excludes_extra_mapped_column(self):
        """scanLastIP mapped to 'extra' (not an identity/watched column) must be excluded -
        there's no column role get_plugin_columns_for_field() can point at."""
        plugins = [_plugin("C", extra_columns=[
            {"column": "extra", "mapped_to_column": "scanLastIP"},
        ])]
        assert get_plugin_columns_for_field(plugins, "ip") == []

    def test_excludes_non_scanMac_objectPrimaryId(self):
        """A plugin whose objectPrimaryId maps to scanParentMAC (not scanMac) is excluded,
        even if it maps scanLastIP correctly - the MAC-identity invariant is checked first."""
        plugins = [_plugin("D", primary_mapped_to="scanParentMAC", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ])]
        assert get_plugin_columns_for_field(plugins, "ip") == []

    def test_excludes_non_CurrentScan_mapped_plugin(self):
        plugin = _plugin("E", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ])
        plugin["mapped_to_table"] = "Plugins_Objects"
        assert get_plugin_columns_for_field([plugin], "ip") == []

    def test_multiple_plugins_mixed(self):
        plugins = [
            _plugin("A", extra_columns=[{"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"}]),
            _plugin("B", primary_mapped_to="scanParentMAC", extra_columns=[
                {"column": "extra", "mapped_to_column": "scanLastIP"},
            ]),
            _plugin("F", extra_columns=[{"column": "watchedValue1", "mapped_to_column": "scanLastIP"}]),
        ]
        assert get_plugin_columns_for_field(plugins, "ip") == [
            ("A", "objectSecondaryId"),
            ("F", "watchedValue1"),
        ]


class TestRealPluginInventory:
    """Checked against the real plugin inventory (get_plugins_configs(True)), not a
    fabricated list - these are the two tests that would catch a real plugin's config.json
    silently breaking the invariant get_plugin_columns_for_field() enforces."""

    def test_mac_identity_invariant_holds_for_participants(self):
        all_plugins = get_plugins_configs(True)
        participants = get_plugin_columns_for_field(all_plugins, "ip")
        by_prefix = {p.get("unique_prefix"): p for p in all_plugins}

        for prefix, _column in participants:
            plugin = by_prefix[prefix]
            primary_id_col = next(
                c for c in plugin["database_column_definitions"]
                if c.get("column") == "objectPrimaryId"
            )
            assert primary_id_col.get("mapped_to_column") == "scanMac", (
                f"{prefix} participates in the 'ip' field view but its objectPrimaryId "
                f"does not map to scanMac - this should have been excluded"
            )

    def test_ip_discovery_structural_check(self):
        all_plugins = get_plugins_configs(True)
        participants = get_plugin_columns_for_field(all_plugins, "ip")
        participant_prefixes = {prefix for prefix, _ in participants}

        assert "dockerdisc" not in participant_prefixes, (
            "dockerdisc maps its IP to 'extra' and objectPrimaryId to scanParentMAC - "
            "excluded for both reasons, should never appear here"
        )
        assert "wificanary" not in participant_prefixes, (
            "wificanary has no MAC-based objectPrimaryId at all - should never appear here"
        )

        valid_roles = {"objectPrimaryId", "objectSecondaryId", "watchedValue1", "watchedValue2", "watchedValue3", "watchedValue4"}
        for prefix, column in participants:
            assert column in valid_roles, f"{prefix} returned an invalid column role: {column}"

        # Incidental today - not frozen. A future plugin addition legitimately changes this.
        assert len(participants) == 23


class TestGetAllDeviceFieldViewsCache:
    def test_same_object_returns_cached_result(self):
        plugins = [_plugin("A", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ])]
        first = get_all_device_field_views(plugins)
        second = get_all_device_field_views(plugins)
        assert first is second

    def test_different_object_recomputes(self):
        plugins_v1 = [_plugin("A", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ])]
        plugins_v2 = [_plugin("A", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ]), _plugin("G", extra_columns=[
            {"column": "watchedValue3", "mapped_to_column": "scanLastIP"},
        ])]

        result_v1 = get_all_device_field_views(plugins_v1)
        result_v2 = get_all_device_field_views(plugins_v2)

        assert result_v1 is not result_v2
        assert result_v1["ip"] == [("A", "objectSecondaryId")]
        assert result_v2["ip"] == [("A", "objectSecondaryId"), ("G", "watchedValue3")]

    def test_covers_every_registered_field(self):
        plugins = [_plugin("A", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ])]
        result = get_all_device_field_views(plugins)
        assert set(result.keys()) == set(DEVICE_FIELD_VIEWS.keys())


class TestBuildFieldViewsPayload:
    """The exact shape embedded into plugins.json's field_views block - the frontend
    contract, not just producer/helper equality. Each field_key maps to an object
    carrying its own label_key/value_type alongside its columns, so the frontend
    reads DEVICE_FIELD_VIEWS' declared label/rendering type instead of re-deriving
    them per field_key."""

    def test_matches_get_all_device_field_views_content(self):
        plugins = [
            _plugin("A", extra_columns=[{"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"}]),
            _plugin("F", extra_columns=[{"column": "watchedValue2", "mapped_to_column": "scanLastIP"}]),
        ]
        payload = build_field_views_payload(plugins)
        expected = get_all_device_field_views(plugins)

        assert payload["ip"]["columns"] == [
            {"plugin": prefix, "column": column} for prefix, column in expected["ip"]
        ]

    def test_entry_shape_has_label_key_value_type_and_columns(self):
        plugins = [_plugin("A", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ])]
        payload = build_field_views_payload(plugins)

        assert set(payload["ip"].keys()) == {"label_key", "value_type", "columns"}
        assert payload["ip"]["label_key"] == DEVICE_FIELD_VIEWS["ip"]["label_key"]
        assert payload["ip"]["value_type"] == DEVICE_FIELD_VIEWS["ip"]["value_type"]
        assert len(payload["ip"]["columns"]) == 1
        column_entry = payload["ip"]["columns"][0]
        assert set(column_entry.keys()) == {"plugin", "column"}
        assert column_entry == {"plugin": "A", "column": "objectSecondaryId"}

    def test_covers_every_registered_field_with_its_own_label_key(self):
        plugins = [_plugin("A", extra_columns=[
            {"column": "objectSecondaryId", "mapped_to_column": "scanLastIP"},
        ])]
        payload = build_field_views_payload(plugins)

        assert set(payload.keys()) == set(DEVICE_FIELD_VIEWS.keys())
        for field_key, field_def in DEVICE_FIELD_VIEWS.items():
            assert payload[field_key]["label_key"] == field_def["label_key"]
            assert payload[field_key]["value_type"] == field_def["value_type"]
