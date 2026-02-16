"""
Unit tests for authoritative field update handler.
"""

from server.db.authoritative_handler import (
    can_overwrite_field,
    get_source_for_field_update_with_value,
    FIELD_SOURCE_MAP,
)


class TestCanOverwriteField:
    """Test the can_overwrite_field authorization logic."""

    def test_user_source_prevents_overwrite(self):
        """USER source should prevent any overwrite."""
        assert not can_overwrite_field(
            "devName", "OldName", "USER", "UNIFIAPI", {"set_always": [], "set_empty": []}, "NewName"
        )

    def test_locked_source_prevents_overwrite(self):
        """LOCKED source should prevent any overwrite."""
        assert not can_overwrite_field(
            "devName", "OldName", "LOCKED", "ARPSCAN", {"set_always": [], "set_empty": []}, "NewName"
        )

    def test_empty_value_prevents_overwrite(self):
        """Empty/None values should prevent overwrite."""
        assert not can_overwrite_field(
            "devName", "OldName", "", "UNIFIAPI", {"set_always": ["devName"], "set_empty": []}, ""
        )
        assert not can_overwrite_field(
            "devName", "OldName", "", "UNIFIAPI", {"set_always": ["devName"], "set_empty": []}, None
        )

    def test_set_always_allows_overwrite(self):
        """SET_ALWAYS should allow overwrite regardless of current source."""
        assert can_overwrite_field(
            "devName", "OldName", "ARPSCAN", "UNIFIAPI", {"set_always": ["devName"], "set_empty": []}, "NewName"
        )
        assert can_overwrite_field(
            "devName", "", "NEWDEV", "UNIFIAPI", {"set_always": ["devName"], "set_empty": []}, "NewName"
        )

    def test_set_empty_allows_overwrite_only_when_empty(self):
        """SET_EMPTY should allow overwrite only if field is empty or NEWDEV."""
        assert can_overwrite_field(
            "devName", "", "", "UNIFIAPI", {"set_always": [], "set_empty": ["devName"]}, "NewName"
        )
        assert can_overwrite_field(
            "devName", "", "NEWDEV", "UNIFIAPI", {"set_always": [], "set_empty": ["devName"]}, "NewName"
        )
        assert not can_overwrite_field(
            "devName", "OldName", "ARPSCAN", "UNIFIAPI", {"set_always": [], "set_empty": ["devName"]}, "NewName"
        )

    def test_default_behavior_overwrites_empty_fields(self):
        """Without SET_ALWAYS/SET_EMPTY, should overwrite only empty fields."""
        assert can_overwrite_field(
            "devName", "", "", "UNIFIAPI", {"set_always": [], "set_empty": []}, "NewName"
        )
        assert can_overwrite_field(
            "devName", "", "NEWDEV", "UNIFIAPI", {"set_always": [], "set_empty": []}, "NewName"
        )
        assert not can_overwrite_field(
            "devName", "OldName", "ARPSCAN", "UNIFIAPI", {"set_always": [], "set_empty": []}, "NewName"
        )

    def test_whitespace_value_treated_as_empty(self):
        """Whitespace-only values should be treated as empty."""
        assert not can_overwrite_field(
            "devName", "OldName", "", "UNIFIAPI", {"set_always": ["devName"], "set_empty": []}, "   "
        )


class TestGetSourceForFieldUpdateWithValue:
    """Test source value determination with value-based normalization."""

    def test_user_override_sets_user_source(self):
        assert (
            get_source_for_field_update_with_value(
                "devName", "UNIFIAPI", "Device", is_user_override=True
            )
            == "USER"
        )

    def test_plugin_update_sets_plugin_prefix(self):
        assert (
            get_source_for_field_update_with_value(
                "devName", "UNIFIAPI", "Device", is_user_override=False
            )
            == "UNIFIAPI"
        )
        assert (
            get_source_for_field_update_with_value(
                "devLastIP", "ARPSCAN", "192.168.1.1", is_user_override=False
            )
            == "ARPSCAN"
        )

    def test_empty_or_unknown_values_return_newdev(self):
        assert (
            get_source_for_field_update_with_value(
                "devName", "ARPSCAN", "", is_user_override=False
            )
            == "NEWDEV"
        )
        assert (
            get_source_for_field_update_with_value(
                "devName", "ARPSCAN", "(unknown)", is_user_override=False
            )
            == "NEWDEV"
        )

    def test_non_empty_value_sets_plugin_prefix(self):
        assert (
            get_source_for_field_update_with_value(
                "devVendor", "ARPSCAN", "Acme", is_user_override=False
            )
            == "ARPSCAN"
        )


class TestFieldSourceMapping:
    """Test field source mapping is correct."""

    def test_all_tracked_fields_have_source_counterpart(self):
        """All tracked fields should have a corresponding *Source field."""
        expected_fields = {
            "devMac": "devMacSource",
            "devName": "devNameSource",
            "devFQDN": "devFQDNSource",
            "devLastIP": "devLastIPSource",
            "devVendor": "devVendorSource",
            "devSSID": "devSSIDSource",
            "devParentMAC": "devParentMACSource",
            "devParentPort": "devParentPortSource",
            "devParentRelType": "devParentRelTypeSource",
            "devVlan": "devVlanSource",
        }

        for field, source in expected_fields.items():
            assert field in FIELD_SOURCE_MAP
            assert FIELD_SOURCE_MAP[field] == source
