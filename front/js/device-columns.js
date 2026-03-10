// =============================================================================
//  device-columns.js — Single source of truth for device field definitions.
//
//  To add a new device column, update ONLY these places:
//    1. DEVICE_COLUMN_FIELDS  — add the field name in the correct position
//    2. COLUMN_NAME_MAP       — add Device_TableHead_X → fieldName mapping
//    3. NUMERIC_DEFAULTS      — add fieldName if its default value is 0 not ""
//    4. GRAPHQL_EXTRA_FIELDS  — add fieldName ONLY if it is NOT a display column
//                               (i.e. fetched for logic but not shown in table)
//    5. front/plugins/ui_settings/config.json  options[]
//    6. front/php/templates/language/en_us.json  Device_TableHead_X
//       then run merge_translations.py for other languages
//    7. Backend: DB view + GraphQL type
// =============================================================================

// Ordered list of all device table column field names.
// Position here determines the positional index used throughout devices.php.
const DEVICE_COLUMN_FIELDS = [
  "devName",               // 0  Device_TableHead_Name
  "devOwner",              // 1  Device_TableHead_Owner
  "devType",               // 2  Device_TableHead_Type
  "devIcon",               // 3  Device_TableHead_Icon
  "devFavorite",           // 4  Device_TableHead_Favorite
  "devGroup",              // 5  Device_TableHead_Group
  "devFirstConnection",    // 6  Device_TableHead_FirstSession
  "devLastConnection",     // 7  Device_TableHead_LastSession
  "devLastIP",             // 8  Device_TableHead_LastIP
  "devIsRandomMac",        // 9  Device_TableHead_MAC (random MAC flag column)
  "devStatus",             // 10 Device_TableHead_Status
  "devMac",                // 11 Device_TableHead_MAC_full
  "devIpLong",             // 12 Device_TableHead_LastIPOrder
  "rowid",                 // 13 Device_TableHead_Rowid
  "devParentMAC",          // 14 Device_TableHead_Parent_MAC
  "devParentChildrenCount",// 15 Device_TableHead_Connected_Devices
  "devLocation",           // 16 Device_TableHead_Location
  "devVendor",             // 17 Device_TableHead_Vendor
  "devParentPort",         // 18 Device_TableHead_Port
  "devGUID",               // 19 Device_TableHead_GUID
  "devSyncHubNode",        // 20 Device_TableHead_SyncHubNodeName
  "devSite",               // 21 Device_TableHead_NetworkSite
  "devSSID",               // 22 Device_TableHead_SSID
  "devSourcePlugin",       // 23 Device_TableHead_SourcePlugin
  "devPresentLastScan",    // 24 Device_TableHead_PresentLastScan
  "devAlertDown",          // 25 Device_TableHead_AlertDown
  "devCustomProps",        // 26 Device_TableHead_CustomProps
  "devFQDN",               // 27 Device_TableHead_FQDN
  "devParentRelType",      // 28 Device_TableHead_ParentRelType
  "devReqNicsOnline",      // 29 Device_TableHead_ReqNicsOnline
  "devVlan",               // 30 Device_TableHead_Vlan
  "devPrimaryIPv4",        // 31 Device_TableHead_IPv4
  "devPrimaryIPv6",        // 32 Device_TableHead_IPv6
  "devFlapping",           // 33 Device_TableHead_Flapping
];

// Named index constants — eliminates all mapIndx(N) magic numbers.
// Access as COL.devFlapping, COL.devMac, etc.
const COL = Object.fromEntries(DEVICE_COLUMN_FIELDS.map((name, i) => [name, i]));

// Fields whose GraphQL response value should default to 0 instead of "".
const NUMERIC_DEFAULTS = new Set([
  "devParentChildrenCount",
  "devReqNicsOnline",
  "devFlapping",
]);

// Fields fetched from GraphQL for internal logic only — not display columns.
// These are merged with DEVICE_COLUMN_FIELDS to build the GraphQL query.
const GRAPHQL_EXTRA_FIELDS = [
  "devComments",
  "devStaticIP",
  "devScan",
  "devLogEvents",
  "devAlertEvents",
  "devSkipRepeated",
  "devLastNotification",
  "devIsNew",
  "devIsArchived",
  "devIsSleeping",
];

// Row positions for extra (non-display) fields.
// In dataSrc, extra fields are appended AFTER the display columns in each row,
// so their position = DEVICE_COLUMN_FIELDS.length + their index in GRAPHQL_EXTRA_FIELDS.
// Use COL_EXTRA.fieldName to access them in createdCell rowData.
const COL_EXTRA = Object.fromEntries(
  GRAPHQL_EXTRA_FIELDS.map((name, i) => [name, DEVICE_COLUMN_FIELDS.length + i])
);

// Maps Device_TableHead_* language keys to their GraphQL/DB field names.
// Used by getColumnNameFromLangString() in ui_components.js and by
// column filter logic in devices.php.
//
// NOTE: Device_TableHead_MAC maps to devMac (display), while position 9 in
// DEVICE_COLUMN_FIELDS uses devIsRandomMac (the random-MAC flag column).
// These are intentionally different; do not collapse them.
const COLUMN_NAME_MAP = {
  "Device_TableHead_Name":              "devName",
  "Device_TableHead_Owner":             "devOwner",
  "Device_TableHead_Type":              "devType",
  "Device_TableHead_Icon":              "devIcon",
  "Device_TableHead_Favorite":          "devFavorite",
  "Device_TableHead_Group":             "devGroup",
  "Device_TableHead_FirstSession":      "devFirstConnection",
  "Device_TableHead_LastSession":       "devLastConnection",
  "Device_TableHead_LastIP":            "devLastIP",
  "Device_TableHead_MAC":               "devMac",
  "Device_TableHead_Status":            "devStatus",
  "Device_TableHead_MAC_full":          "devMac",
  "Device_TableHead_LastIPOrder":       "devIpLong",
  "Device_TableHead_Rowid":             "rowid",
  "Device_TableHead_Parent_MAC":        "devParentMAC",
  "Device_TableHead_Connected_Devices": "devParentChildrenCount",
  "Device_TableHead_Location":          "devLocation",
  "Device_TableHead_Vendor":            "devVendor",
  "Device_TableHead_Port":              "devParentPort",
  "Device_TableHead_GUID":              "devGUID",
  "Device_TableHead_SyncHubNodeName":   "devSyncHubNode",
  "Device_TableHead_NetworkSite":       "devSite",
  "Device_TableHead_SSID":              "devSSID",
  "Device_TableHead_SourcePlugin":      "devSourcePlugin",
  "Device_TableHead_PresentLastScan":   "devPresentLastScan",
  "Device_TableHead_AlertDown":         "devAlertDown",
  "Device_TableHead_CustomProps":       "devCustomProps",
  "Device_TableHead_FQDN":              "devFQDN",
  "Device_TableHead_ParentRelType":     "devParentRelType",
  "Device_TableHead_ReqNicsOnline":     "devReqNicsOnline",
  "Device_TableHead_Vlan":              "devVlan",
  "Device_TableHead_IPv4":              "devPrimaryIPv4",
  "Device_TableHead_IPv6":              "devPrimaryIPv6",
  "Device_TableHead_Flapping":          "devFlapping",
};

console.log("init device-columns.js");
