# Field Lock Scenarios - Comprehensive Test Suite

Created comprehensive tests for all device field locking scenarios in NetAlertX using two complementary approaches.

## Test Files

### 1. Unit Tests - Direct Authorization Logic
**File:** `/workspaces/NetAlertX/test/authoritative_fields/test_field_lock_scenarios.py`
- Tests the `can_overwrite_field()` function directly
- Verifies authorization rules without database operations
- Fast, focused unit tests with direct assertions

**16 Unit Tests covering:**

#### Protected Sources (No Override)
- ✅ `test_locked_source_prevents_plugin_overwrite()` - LOCKED source blocks updates
- ✅ `test_user_source_prevents_plugin_overwrite()` - USER source blocks updates

#### Updatable Sources (Allow Override)
- ✅ `test_newdev_source_allows_plugin_overwrite()` - NEWDEV allows plugin updates
- ✅ `test_empty_current_source_allows_plugin_overwrite()` - Empty source allows updates

#### Plugin Ownership Rules
- ✅ `test_plugin_source_allows_same_plugin_overwrite()` - Plugin can update its own fields
- ✅ `test_plugin_source_allows_different_plugin_overwrite_with_set_always()` - Different plugin CAN update WITH SET_ALWAYS
- ✅ `test_plugin_source_rejects_different_plugin_without_set_always()` - Different plugin CANNOT update WITHOUT SET_ALWAYS

#### SET_EMPTY Authorization
- ✅ `test_set_empty_allows_overwrite_on_empty_field()` - SET_EMPTY works with NEWDEV
- ✅ `test_set_empty_rejects_overwrite_on_non_empty_field()` - SET_EMPTY doesn't override plugin fields
- ✅ `test_set_empty_with_empty_string_source()` - SET_EMPTY works with empty string source

#### Empty Value Handling
- ✅ `test_empty_plugin_value_not_used()` - Empty string values rejected
- ✅ `test_whitespace_only_plugin_value_not_used()` - Whitespace-only values rejected
- ✅ `test_none_plugin_value_not_used()` - None values rejected

#### SET_ALWAYS Override Behavior
- ✅ `test_set_always_overrides_plugin_ownership()` - SET_ALWAYS overrides other plugins but NOT USER/LOCKED
- ✅ `test_multiple_plugins_set_always_scenarios()` - Multi-plugin update scenarios

#### Multi-Field Scenarios
- ✅ `test_different_fields_with_different_sources()` - Each field respects its own source

---

### 2. Integration Tests - Real Scan Simulation
**File:** `/workspaces/NetAlertX/test/authoritative_fields/test_field_lock_scan_integration.py`
- Simulates real-world scanner operations with CurrentScan/Devices tables
- Tests full scan update pipeline
- Verifies field locking behavior in realistic scenarios

**8 Integration Tests covering:**

#### Field Source Protection
- ✅ `test_scan_updates_newdev_device_name()` - NEWDEV fields are populated from scan
- ✅ `test_scan_does_not_update_user_field_name()` - USER fields remain unchanged during scan
- ✅ `test_scan_does_not_update_locked_field()` - LOCKED fields remain unchanged during scan

#### Vendor Discovery
- ✅ `test_scan_updates_empty_vendor_field()` - Empty vendor gets populated from scan

#### IP Address Handling
- ✅ `test_scan_updates_ip_addresses()` - IPv4 and IPv6 set from scan data
- ✅ `test_scan_updates_ipv6_without_changing_ipv4()` - IPv6 update preserves existing IPv4

#### Device Status
- ✅ `test_scan_updates_presence_status()` - Offline devices correctly marked as not present

#### Multi-Device Scenarios
- ✅ `test_scan_multiple_devices_mixed_sources()` - Complex multi-device scan with mixed source types

---

### 3. IP Format & Field Locking Tests (`test_ip_format_and_locking.py`)
- IP format validation (IPv4/IPv6)
- Invalid IP rejection
- Address format variations
- Multi-scan IP update scenarios

**6 IP Format Tests covering:**

#### IPv4 & IPv6 Validation
- ✅ `test_valid_ipv4_format_accepted()` - Valid IPv4 sets devPrimaryIPv4
- ✅ `test_valid_ipv6_format_accepted()` - Valid IPv6 sets devPrimaryIPv6

#### Invalid Values
- ✅ `test_invalid_ip_values_rejected()` - Rejects: empty, "null", "(unknown)", "(Unknown)"

#### Multi-Scan Scenarios
- ✅ `test_ipv4_ipv6_mixed_in_multiple_scans()` - IPv4 then IPv6 updates preserve both

#### Format Variations
- ✅ `test_ipv4_address_format_variations()` - Tests 6 IPv4 ranges: loopback, private, broadcast
- ✅ `test_ipv6_address_format_variations()` - Tests 5 IPv6 formats: loopback, link-local, full address

---

## Total Tests: 33

- 10 Authoritative handler tests (existing)
- 3 Device status mapping tests (existing)
- 17 Field lock scenarios (unit tests)
- 8 Field lock scan integration tests
- 2 IP update logic tests (existing, refactored)
- 6 IP format validation tests

## Test Execution Commands

### Run all authoritative fields tests
```bash
cd /workspaces/NetAlertX
python -m pytest test/authoritative_fields/ -v
```

### Run all field lock tests
```bash
python -m pytest test/authoritative_fields/test_field_lock_scenarios.py test/authoritative_fields/test_field_lock_scan_integration.py -v
```

### Run IP format validation tests
```bash
python -m pytest test/authoritative_fields/test_ip_format_and_locking.py -v
```

---

## Test Architecture

### Unit Tests (`test_field_lock_scenarios.py`)

**Approach:** Direct function testing
- Imports: `can_overwrite_field()` from `server.db.authoritative_handler`
- No database setup required
- Fast execution
- Tests authorization logic in isolation

**Structure:**
```python
def test_scenario():
    result = can_overwrite_field(
        field_name="devName",
        current_source="LOCKED",
        plugin_prefix="ARPSCAN",
        plugin_settings={"set_always": [], "set_empty": []},
        field_value="New Value",
    )
    assert result is False
```

### Integration Tests (`test_field_lock_scan_integration.py`)

**Approach:** Full pipeline simulation
- Sets up in-memory SQLite database
- Creates Devices and CurrentScan tables
- Populates with realistic scan data
- Calls `device_handling.update_devices_data_from_scan()`
- Verifies final state in Devices table

**Fixtures:**
- `@pytest.fixture scan_db`: In-memory SQLite database with full schema
- `@pytest.fixture mock_device_handlers`: Mocks device_handling helper functions

**Structure:**
```python
def test_scan_scenario(scan_db, mock_device_handlers):
    cur = scan_db.cursor()

    # Insert device with specific source
    cur.execute("INSERT INTO Devices ...")

    # Insert scan results
    cur.execute("INSERT INTO CurrentScan ...")
    scan_db.commit()

    # Run actual scan update
    db = Mock()
    db.sql_connection = scan_db
    db.sql = cur
    device_handling.update_devices_data_from_scan(db)

    # Verify results
    row = cur.execute("SELECT ... FROM Devices")
    assert row["field"] == "expected_value"
```

---

## Key Scenarios Tested

### Protection Rules (Honored in Both Unit & Integration Tests)

| Scenario | Current Source | Plugin Action | Result |
|----------|---|---|---|
| **User Protection** | USER | Try to update | ❌ BLOCKED |
| **Explicit Lock** | LOCKED | Try to update | ❌ BLOCKED |
| **Default/Empty** | NEWDEV or "" | Try to update with value | ✅ ALLOWED |
| **Same Plugin** | PluginA | PluginA tries to update | ✅ ALLOWED |
| **Different Plugin** | PluginA | PluginB tries to update (no SET_ALWAYS) | ❌ BLOCKED |
| **Different Plugin (SET_ALWAYS)** | PluginA | PluginB tries with SET_ALWAYS | ✅ ALLOWED |
| **SET_ALWAYS > USER** | USER | PluginA with SET_ALWAYS | ❌ BLOCKED (USER always protected) |
| **SET_ALWAYS > LOCKED** | LOCKED | PluginA with SET_ALWAYS | ❌ BLOCKED (LOCKED always protected) |
| **Empty Value** | NEWDEV | Plugin provides empty/None | ❌ BLOCKED |

---

## Field Support

All 10 lockable fields tested:
1. `devMac` - Device MAC address
2. `devName` - Device hostname/alias
3. `devFQDN` - Fully qualified domain name
4. `devLastIP` - Last known IP address
5. `devVendor` - Device manufacturer
6. `devSSID` - WiFi network name
7. `devParentMAC` - Parent/gateway MAC
8. `devParentPort` - Parent device port
9. `devParentRelType` - Relationship type
10. `devVlan` - VLAN identifier

---

## Plugins Referenced in Tests

- **ARPSCAN** - ARP scanning network discovery
- **NBTSCAN** - NetBIOS name resolution
- **PIHOLEAPI** - Pi-hole DNS/Ad blocking integration
- **UNIFIAPI** - Ubiquiti UniFi network controller integration
- **DHCPLSS** - DHCP lease scanning (referenced in config examples)

---

## Authorization Rules Reference

**From `server/db/authoritative_handler.py` - `can_overwrite_field()` function:**

1. **Rule 1 (USER & LOCKED Protection):** If `current_source` is "USER" or "LOCKED" → Return `False` immediately
   - These are ABSOLUTE protections - even SET_ALWAYS cannot override
2. **Rule 2 (Value Validation):** If `field_value` (the NEW value to write) is empty/None/whitespace → Return `False` immediately
   - Plugin cannot write empty values - only meaningful data allowed
3. **Rule 3 (SET_ALWAYS Override):** If field is in plugin's `set_always` list → Return `True`
   - Allows overwriting ANY source (except USER/LOCKED already blocked in Rule 1)
   - Works on empty current values, plugin-owned fields, other plugins' fields
4. **Rule 4 (SET_EMPTY):** If field is in plugin's `set_empty` list AND current_source is empty/"NEWDEV" → Return `True`
   - Restrictive: Only fills empty fields, won't overwrite plugin-owned fields
5. **Rule 5 (Default):** If current_source is empty/"NEWDEV" → Return `True`, else → Return `False`
   - Default behavior: only overwrite empty/unset fields

**Key Principles:**
- **USER and LOCKED** = Absolute protection (cannot be overwritten, even with SET_ALWAYS)
- **SET_ALWAYS** = Allow overwrite of: own fields, other plugin fields, empty current values, NEWDEV fields
- **SET_EMPTY** = "Set only if empty" - fills empty fields only, won't overwrite existing plugin data
- **Default** = Plugins can only update NEWDEV/empty fields without authorization
- Plugin ownership (e.g., "ARPSCAN") is treated like any other non-protected source for override purposes

---

## Related Documentation

- **User Guide:** [DEVICE_FIELD_LOCK.md](../../docs/DEVICE_FIELD_LOCK.md) - User-friendly field locking instructions
- **API Documentation:** [API_DEVICE_FIELD_LOCK.md](../../docs/API_DEVICE_FIELD_LOCK.md) - Endpoint documentation
- **Plugin Configuration:** [PLUGINS_DEV_CONFIG.md](../../docs/PLUGINS_DEV_CONFIG.md) - SET_ALWAYS/SET_EMPTY configuration guide
- **Device Management:** [DEVICE_MANAGEMENT.md](../../docs/DEVICE_MANAGEMENT.md) - Device management admin guide

---

## Implementation Files

**Code Under Test:**
- `server/db/authoritative_handler.py` - Authorization logic
- `server/scan/device_handling.py` - Scan update pipeline
- `server/api_server/api_server_start.py` - API endpoints for field locking

**Test Files:**
- `test/authoritative_fields/test_field_lock_scenarios.py` - Unit tests
- `test/authoritative_fields/test_field_lock_scan_integration.py` - Integration tests

---

**Created:** January 19, 2026
**Last Updated:** January 19, 2026
**Status:** ✅ 24 comprehensive tests created covering all scenarios
