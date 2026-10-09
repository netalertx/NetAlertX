"""
Registry and discovery for device "field views" - the Sources tab's Field View,
which pivots Plugins_Objects data by a semantic field (e.g. "ip") across every
plugin that reports it, instead of by plugin.

DEVICE_FIELD_VIEWS is small and hand-maintained on purpose: it records the
semantic-to-schema mapping (target_column), the product capability
(multi_valued), the display label (label_key), and the frontend rendering
type (value_type) that cannot be derived safely from the plugin configs.
Which plugin's column actually answers a field is NOT hand-maintained -
that's derived fresh from all_plugins by get_plugin_columns_for_field()
below, since that fact has exactly one real source already (each plugin's
own config.json).
"""

_PLUGINS_OBJECTS_COLUMN_ROLES = (
    "objectPrimaryId",
    "objectSecondaryId",
    "watchedValue1",
    "watchedValue2",
    "watchedValue3",
    "watchedValue4",
)

DEVICE_FIELD_VIEWS = {
    "ip": {
        # Reuses the existing "IP" label already defined for deviceDetails.php's
        # own Sessions table - en_us.json already had 4 other "IP" keys before this
        # one; search before adding a near-duplicate for the same plain text.
        "label_key": "DevDetail_SessionTable_IP",
        "target_column": "scanLastIP",
        "multi_valued": True,
        # Renders via plugin_column_render.js's device_ip case - a clickable
        # "find other devices with this IP" link.
        "value_type": "device_ip",
    },
    "name": {
        "label_key": "Device_TableHead_Name",
        "target_column": "scanName",
        "multi_valued": True,
        "value_type": "none",
    },
    "vendor": {
        "label_key": "Device_TableHead_Vendor",
        "target_column": "scanVendor",
        "multi_valued": True,
        "value_type": "none",
    },
    "type": {
        "label_key": "Device_TableHead_Type",
        "target_column": "scanType",
        "multi_valued": True,
        "value_type": "none",
    },
}


def get_plugin_columns_for_field(all_plugins, field_key):
    """Return [(plugin_prefix, column_role)] for every CurrentScan-mapped plugin whose
    database_column_definitions maps DEVICE_FIELD_VIEWS[field_key]'s target_column to one of
    Plugins_Objects' identity/watched columns (objectPrimaryId/objectSecondaryId/watchedValue1-4
    - not 'extra' or any other column), AND whose own objectPrimaryId maps to scanMac
    specifically (deliberately not scanParentMAC too - see the PRD's correction trail).
    column_role is whichever of those columns the match landed on."""
    target_column = DEVICE_FIELD_VIEWS[field_key]["target_column"]
    results = []

    for plugin in all_plugins:
        if plugin.get("mapped_to_table") != "CurrentScan":
            continue

        columns = plugin.get("database_column_definitions", [])

        primary_id_col = next(
            (c for c in columns if c.get("column") == "objectPrimaryId"), None
        )
        if not primary_id_col or primary_id_col.get("mapped_to_column") != "scanMac":
            continue

        field_col = None
        for c in columns:
            if c.get("column") in _PLUGINS_OBJECTS_COLUMN_ROLES and c.get("mapped_to_column") == target_column:
                field_col = c
                break
        if not field_col:
            continue

        results.append((plugin.get("unique_prefix"), field_col["column"]))

    return results


_field_views_cache = {"all_plugins_ref": None, "result": None}


def get_all_device_field_views(all_plugins):
    """Return {field_key: [(plugin_prefix, column_role), ...]} for every DEVICE_FIELD_VIEWS
    field, cached by all_plugins' object identity. all_plugins is loaded once at startup/config
    reload and reused as the same object across every later call (e.g. update_api() runs on
    every scan cycle and plugin completion) - caching by identity avoids re-scanning every
    plugin's config on each of those calls, recomputing only when a genuinely new all_plugins
    object (an actual reload) is passed in. The cache retains a reference to the list itself
    (compared with `is`), not just its id() - an id() alone can be reused by an unrelated
    object once the original all_plugins list is garbage collected, which would wrongly
    serve a stale cached result for what is actually a new reload."""
    if _field_views_cache["all_plugins_ref"] is not all_plugins:
        _field_views_cache["result"] = {
            field_key: get_plugin_columns_for_field(all_plugins, field_key)
            for field_key in DEVICE_FIELD_VIEWS
        }
        _field_views_cache["all_plugins_ref"] = all_plugins
    return _field_views_cache["result"]


def build_field_views_payload(all_plugins):
    """Return get_all_device_field_views()'s result in the JSON-serializable shape embedded
    into plugins.json's field_views block: {field_key: {"label_key": ..., "value_type": ...,
    "columns": [{"plugin": ..., "column": ...}, ...]}}. label_key/value_type travel alongside
    their columns so the frontend reads DEVICE_FIELD_VIEWS' own declared label and rendering
    type instead of re-deriving them per field_key itself."""
    all_columns = get_all_device_field_views(all_plugins)
    return {
        field_key: {
            "label_key": DEVICE_FIELD_VIEWS[field_key]["label_key"],
            "value_type": DEVICE_FIELD_VIEWS[field_key]["value_type"],
            "columns": [{"plugin": prefix, "column": column} for prefix, column in columns],
        }
        for field_key, columns in all_columns.items()
    }
