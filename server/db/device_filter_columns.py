"""
Single source of truth for which Devices-table columns are filterable in the
UI, used by both the generated sql_devices_filters query (server/const.py)
and the ui_settings plugin's columns_filters.options[] (synced via
sync_device_filter_columns_config.py). Follows the same dict-registry +
generator pattern as schema_columns.py.

Registry order is preserved into columns_filters.options[] by the sync
script, so it matches the order that setting's options have always been
hand-maintained in - reordering this dict changes the options list order
the Settings page's filter picker presents.

devFlapping is intentionally absent: it's computed in DevicesView's CTE,
not a plain Devices column, so the generic "FROM Devices" block shape this
registry drives cannot reach it without a structural change to the
generator. See device-filter-column-registry.md for the full design.
"""

DEVICE_FILTER_COLUMNS = {
    "devOwner": {"label_key": "Device_TableHead_Owner"},
    "devType": {"label_key": "Device_TableHead_Type"},
    "devGroup": {"label_key": "Device_TableHead_Group"},
    "devLocation": {"label_key": "Device_TableHead_Location"},
    "devVendor": {"label_key": "Device_TableHead_Vendor"},
    "devSyncHubNode": {"label_key": "Device_TableHead_SyncHubNodeName"},
    "devSite": {"label_key": "Device_TableHead_NetworkSite"},
    "devSSID": {"label_key": "Device_TableHead_SSID"},
    "devSourcePlugin": {"label_key": "Device_TableHead_SourcePlugin"},
    "devParentRelType": {"label_key": "Device_TableHead_ParentRelType"},
    "devParentMAC": {"label_key": "Device_TableHead_Parent_MAC", "label_join": "parent_name"},
    "devVlan": {"label_key": "Device_TableHead_Vlan"},
}


def _generic_filter_block(column_name, null_equivalents_sql):
    """Return the UNION SELECT block for an ordinary Devices column with no special label join."""
    return f"""SELECT DISTINCT '{column_name}' AS columnName, {column_name} AS columnValue, {column_name} AS columnLabel
                        FROM Devices WHERE {column_name} NOT IN ({null_equivalents_sql}) AND {column_name} IS NOT NULL"""


def _parent_mac_filter_block(null_equivalents_sql):
    """Return the UNION SELECT block for devParentMAC, resolving the parent device's name as the label."""
    return f"""SELECT 'devParentMAC' AS columnName, d.devParentMAC AS columnValue,
                           COALESCE(p.devName, d.devParentMAC) AS columnLabel
                        FROM Devices d
                        LEFT JOIN Devices p ON LOWER(p.devMac) = LOWER(d.devParentMAC)
                        WHERE d.devParentMAC NOT IN ({null_equivalents_sql}) AND d.devParentMAC IS NOT NULL
                        GROUP BY d.devParentMAC COLLATE NOCASE"""


def build_devices_filters_sql(null_equivalents_sql):
    """Generate the sql_devices_filters UNION query from DEVICE_FILTER_COLUMNS, one block per registry entry.

    null_equivalents_sql is const.NULL_EQUIVALENTS_SQL, passed in rather than imported to avoid a circular
    import (const.py is this module's caller and defines NULL_EQUIVALENTS_SQL before calling in).
    """
    blocks = []
    for column_name, spec in DEVICE_FILTER_COLUMNS.items():
        if spec.get("label_join") == "parent_name":
            blocks.append(_parent_mac_filter_block(null_equivalents_sql))
        else:
            blocks.append(_generic_filter_block(column_name, null_equivalents_sql))

    return "\n                    UNION\n                    ".join(blocks) + "\n                    ORDER BY columnName;\n                    "
