"""
Unit tests for device field locking scenarios.

Tests all combinations of field sources (LOCKED, USER, NEWDEV, plugin name)
and verifies that plugin updates are correctly allowed/rejected based on
field source and SET_ALWAYS/SET_EMPTY configuration.
"""

from server.db.authoritative_handler import can_overwrite_field


def test_locked_source_prevents_plugin_overwrite():
    result = can_overwrite_field(
        field_name="devName",
        current_value="ExistingName",
        current_source="LOCKED",
        plugin_prefix="ARPSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="New Name",
    )
    assert result is False


def test_user_source_prevents_plugin_overwrite():
    result = can_overwrite_field(
        field_name="devName",
        current_value="UserName",
        current_source="USER",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="Plugin Discovered Name",
    )
    assert result is False


def test_newdev_source_allows_plugin_overwrite():
    result = can_overwrite_field(
        field_name="devName",
        current_value="",
        current_source="NEWDEV",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="DiscoveredName",
    )
    assert result is True


def test_empty_current_source_allows_plugin_overwrite():
    result = can_overwrite_field(
        field_name="devName",
        current_value="",
        current_source="",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="DiscoveredName",
    )
    assert result is True


def test_plugin_source_allows_same_plugin_overwrite_with_set_always():
    result = can_overwrite_field(
        field_name="devName",
        current_value="OldName",
        current_source="NBTSCAN",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": ["devName"], "set_empty": []},
        field_value="NewName",
    )
    assert result is True


def test_plugin_source_cannot_overwrite_without_authorization():
    result = can_overwrite_field(
        field_name="devName",
        current_value="OldName",
        current_source="NBTSCAN",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="NewName",
    )
    assert result is False


def test_plugin_source_allows_different_plugin_overwrite_with_set_always():
    result = can_overwrite_field(
        field_name="devVendor",
        current_value="OldVendor",
        current_source="ARPSCAN",
        plugin_prefix="PIHOLEAPI",
        plugin_settings={"set_always": ["devVendor"], "set_empty": []},
        field_value="NewVendor",
    )
    assert result is True


def test_plugin_source_rejects_different_plugin_without_set_always():
    result = can_overwrite_field(
        field_name="devVendor",
        current_value="OldVendor",
        current_source="ARPSCAN",
        plugin_prefix="PIHOLEAPI",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="NewVendor",
    )
    assert result is False


def test_set_empty_allows_overwrite_on_empty_field():
    result = can_overwrite_field(
        field_name="devName",
        current_value="",
        current_source="ARPSCAN",
        plugin_prefix="PIHOLEAPI",
        plugin_settings={"set_always": [], "set_empty": ["devName"]},
        field_value="DiscoveredName",
    )
    assert result is True


def test_set_empty_rejects_overwrite_on_non_empty_field():
    result = can_overwrite_field(
        field_name="devName",
        current_value="ExistingName",
        current_source="ARPSCAN",
        plugin_prefix="PIHOLEAPI",
        plugin_settings={"set_always": [], "set_empty": ["devName"]},
        field_value="NewName",
    )
    assert result is False


def test_empty_plugin_value_not_used():
    # Allows overwrite as new value same as old
    result = can_overwrite_field(
        field_name="devName",
        current_value="same value",
        current_source="AVAHISCAN",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="same value",
    )
    assert result is True


def test_whitespace_only_plugin_value_not_used():
    result = can_overwrite_field(
        field_name="devName",
        current_value="",
        current_source="NEWDEV",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="   ",
    )
    assert result is False


def test_none_plugin_value_not_used():
    result = can_overwrite_field(
        field_name="devName",
        current_value="",
        current_source="NEWDEV",
        plugin_prefix="NBTSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value=None,
    )
    assert result is False


def test_set_always_overrides_plugin_ownership():
    result = can_overwrite_field(
        field_name="devVendor",
        current_value="OldVendor",
        current_source="ARPSCAN",
        plugin_prefix="UNIFIAPI",
        plugin_settings={"set_always": ["devVendor"], "set_empty": []},
        field_value="NewVendor",
    )
    assert result is True

    result = can_overwrite_field(
        field_name="devVendor",
        current_value="UserVendor",
        current_source="USER",
        plugin_prefix="UNIFIAPI",
        plugin_settings={"set_always": ["devVendor"], "set_empty": []},
        field_value="NewVendor",
    )
    assert result is False

    result = can_overwrite_field(
        field_name="devVendor",
        current_value="LockedVendor",
        current_source="LOCKED",
        plugin_prefix="UNIFIAPI",
        plugin_settings={"set_always": ["devVendor"], "set_empty": []},
        field_value="NewVendor",
    )
    assert result is False


def test_multiple_plugins_set_always_scenarios():
    plugins_scenarios = [
        ("ARPSCAN", "ARPSCAN", False),
        ("ARPSCAN", "ARPSCAN", True),
        ("ARPSCAN", "NBTSCAN", False),
        ("ARPSCAN", "PIHOLEAPI", True),
        ("ARPSCAN", "UNIFIAPI", True),
    ]

    for current_source, plugin_prefix, has_set_always in plugins_scenarios:
        result = can_overwrite_field(
            field_name="devName",
            current_value="ExistingName",
            current_source=current_source,
            plugin_prefix=plugin_prefix,
            plugin_settings={"set_always": ["devName"] if has_set_always else [], "set_empty": []},
            field_value="NewName",
        )

        if has_set_always:
            assert result is True
        else:
            assert result is False


def test_different_fields_with_different_sources():
    fields_sources = [
        ("devName", "USER", "UserValue"),
        ("devVendor", "ARPSCAN", "VendorX"),
        ("devLastIP", "NEWDEV", ""),
        ("devFQDN", "LOCKED", "locked.example.com"),
    ]

    results = {}
    for field_name, current_source, current_value in fields_sources:
        results[field_name] = can_overwrite_field(
            field_name=field_name,
            current_value=current_value,
            current_source=current_source,
            plugin_prefix="NBTSCAN",
            plugin_settings={"set_always": [], "set_empty": []},
            field_value="NewValue",
        )

    assert results["devName"] is False
    assert results["devVendor"] is False
    assert results["devLastIP"] is True
    assert results["devFQDN"] is False


def test_set_empty_with_empty_string_source():
    result = can_overwrite_field(
        field_name="devName",
        current_value="",
        current_source="",
        plugin_prefix="PIHOLEAPI",
        plugin_settings={"set_always": [], "set_empty": ["devName"]},
        field_value="DiscoveredName",
    )
    assert result is True
