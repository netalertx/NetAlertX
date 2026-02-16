"""
Authoritative field update handler for NetAlertX.

This module enforces source-tracking policies when plugins or users update device fields.
It prevents overwrites when fields are marked as USER or LOCKED, and tracks the source
of each field value.

Author: NetAlertX Core
License: GNU GPLv3
"""

import sys
import os

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server"])

from logger import mylog  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from db.db_helper import row_to_json  # noqa: E402 [flake8 lint suppression]
from plugin_helper import normalize_mac  # noqa: E402 [flake8 lint suppression]
from const import NULL_EQUIVALENTS  # noqa: E402 [flake8 lint suppression]


# Map of field to its source tracking field
FIELD_SOURCE_MAP = {
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

# Fields that support source tracking
TRACKED_FIELDS = set(FIELD_SOURCE_MAP.keys())


def get_plugin_authoritative_settings(plugin_prefix):
    """
    Get SET_ALWAYS and SET_EMPTY settings for a plugin.

    Args:
        plugin_prefix: The unique prefix of the plugin (e.g., "UNIFIAPI").

    Returns:
        dict: {
            "set_always": [list of fields],
            "set_empty": [list of fields]
        }
    """
    try:
        set_always_key = f"{plugin_prefix}_SET_ALWAYS"
        set_empty_key = f"{plugin_prefix}_SET_EMPTY"

        set_always = get_setting_value(set_always_key) or []
        set_empty = get_setting_value(set_empty_key) or []

        # Normalize to list of strings if they aren't already
        if isinstance(set_always, str):
            set_always = [set_always]
        if isinstance(set_empty, str):
            set_empty = [set_empty]

        return {
            "set_always": list(set_always) if set_always else [],
            "set_empty": list(set_empty) if set_empty else [],
        }
    except Exception as e:
        mylog("debug", [f"[authoritative_handler] Failed to get settings for {plugin_prefix}: {e}"])
        return {"set_always": [], "set_empty": []}


def can_overwrite_field(field_name, current_value, current_source, plugin_prefix, plugin_settings, field_value, allow_override_if_changed=False):
    """
    Determine if a plugin can overwrite a field.

    Rules:
    - USER/LOCKED cannot overwrite.
    - SET_ALWAYS can overwrite everything if new value not empty.
    - SET_EMPTY can overwrite if current value empty.
    - Otherwise, overwrite only empty fields.

    Args:
        field_name: The field being updated (e.g., "devName").
        current_value: Current value in Devices.
        current_source: Current source in Devices (USER, LOCKED, etc.).
        plugin_prefix: Plugin prefix.
        plugin_settings: Dict with set_always and set_empty lists.
        field_value: The new value from scan.

    Returns:
        bool: True if overwrite allowed.
    """

    empty_values = ("0.0.0.0", *NULL_EQUIVALENTS, None)

    # Rule 1: USER/LOCKED protected
    if current_source in ("USER", "LOCKED"):
        return False

    # Rule 2: Must provide a non-empty value, otherwise reject
    if (not field_value) or (field_value in empty_values) or ((isinstance(field_value, str) and not field_value.strip())):
        return False

    # Rule 3: Allow overwrite if value same to update Source fields
    if current_value == field_value:
        return True

    # Rule 4: SET_ALWAYS
    set_always = plugin_settings.get("set_always", [])
    if field_name in set_always:
        return True

    # Rule 5: SET_EMPTY
    set_empty = plugin_settings.get("set_empty", [])
    if field_name in set_empty:
        if current_value in empty_values:
            return True
        return False

    # Rule 6: Default - overwrite if current value empty
    if current_value in empty_values:
        return True

    # Rule 7: Optional override flag to allow overwrite if value changed (devLastIP)
    if allow_override_if_changed and field_value != current_value:
        return True

    return False


def get_overwrite_sql_clause(field_name, source_column, plugin_settings):
    """
    Build a SQL condition for authoritative overwrite checks.

    Returns a SQL snippet that permits overwrite for the given field
    based on SET_ALWAYS/SET_EMPTY and USER/LOCKED protection.

    Args:
        field_name: The field being updated (e.g., "devName").
        source_column: The *Source column name (e.g., "devNameSource").
        plugin_settings: dict with "set_always" and "set_empty" lists.

    Returns:
        str: SQL condition snippet (no leading WHERE).
    """
    set_always = plugin_settings.get("set_always", [])
    set_empty = plugin_settings.get("set_empty", [])

    mylog("debug", [f"[get_overwrite_sql_clause] DEBUG: field_name:{field_name}, source_column:{source_column}, set_always:{set_always}, set_empty:{set_empty}"])

    if field_name in set_always:
        return f"COALESCE({source_column}, '') NOT IN ('USER', 'LOCKED')"

    if field_name in set_empty or field_name not in set_always:
        return f"COALESCE({source_column}, '') IN ('', 'NEWDEV')"

    return f"COALESCE({source_column}, '') IN ('', 'NEWDEV')"


def get_source_for_field_update_with_value(
    field_name, plugin_prefix, field_value, is_user_override=False
):
    """
    Determine the source value for a field update based on the new value.

    If the new value is empty or an "unknown" placeholder, return NEWDEV.
    Otherwise, fall back to standard source selection rules.

    Args:
        field_name: The field being updated.
        plugin_prefix: The unique prefix of the plugin writing (e.g., "UNIFIAPI").
        field_value: The new value being written.
        is_user_override: If True, return "USER".

    Returns:
        str: The source value to set for the *Source field.
    """
    if is_user_override:
        return "USER"

    if field_value is None:
        return "NEWDEV"

    if isinstance(field_value, str):
        stripped = field_value.strip()
        if stripped.lower() in NULL_EQUIVALENTS:
            return "NEWDEV"

    return plugin_prefix


def enforce_source_on_user_update(devMac, updates_dict, conn):
    """
    When a user updates device fields, enforce source tracking.

    For each field with a corresponding *Source field:
    - If the field value is being changed, set the *Source to "USER".
    - If user explicitly locks a field, set the *Source to "LOCKED".

    Args:
        devMac: The MAC address of the device being updated.
        updates_dict: Dict of field -> value being updated.
        conn: Database connection object.
    """

    # Check if field has a corresponding source and should be updated
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(Devices)")
        device_columns = {row["name"] for row in cur.fetchall()}
    except Exception:
        device_columns = set()

    updates_to_apply = {}
    for field_name in updates_dict.keys():
        if field_name in FIELD_SOURCE_MAP:
            source_field = FIELD_SOURCE_MAP[field_name]
            if not device_columns or source_field in device_columns:
                updates_to_apply[source_field] = "USER"

    if not updates_to_apply:
        return

    # Build SET clause
    set_clause = ", ".join([f"{k}=?" for k in updates_to_apply.keys()])
    values = list(updates_to_apply.values())
    values.append(devMac)

    sql = f"UPDATE Devices SET {set_clause} WHERE devMac = ?"

    try:
        cur.execute(sql, values)
        mylog(
            "debug",
            [f"[enforce_source_on_user_update] Updated sources for {devMac}: {updates_to_apply}"],
        )
    except Exception as e:
        mylog("none", [f"[enforce_source_on_user_update] ERROR: {e}"])
        raise


def get_locked_field_overrides(devMac, updates_dict, conn):
    """
    For user updates, restore values for any fields whose *Source is LOCKED.

    Args:
        devMac: The MAC address of the device being updated.
        updates_dict: Dict of field -> value being updated.
        conn: Database connection object.

    Returns:
        tuple(set, dict): (locked_fields, overrides)
            locked_fields: set of field names that are locked
            overrides: dict of field -> existing value to preserve
    """
    tracked_fields = [field for field in updates_dict.keys() if field in FIELD_SOURCE_MAP]
    if not tracked_fields:
        return set(), {}

    select_columns = tracked_fields + [FIELD_SOURCE_MAP[field] for field in tracked_fields]
    select_clause = ", ".join(select_columns)

    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT {select_clause} FROM Devices WHERE devMac=?",
            (devMac,),
        )
        row = cur.fetchone()
    except Exception:
        row = None

    if not row:
        return set(), {}

    row_data = row_to_json(list(row.keys()), row)
    locked_fields = set()
    overrides = {}

    for field in tracked_fields:
        source_field = FIELD_SOURCE_MAP[field]
        if row_data.get(source_field) == "LOCKED":
            locked_fields.add(field)
            overrides[field] = row_data.get(field) or ""

    return locked_fields, overrides


def lock_field(devMac, field_name, conn):
    """
    Lock a field so it won't be overwritten by plugins.

    Returns:
        dict: {"success": bool, "error": str|None}
    """
    if field_name not in FIELD_SOURCE_MAP:
        msg = f"Field {field_name} does not support locking"
        mylog("debug", [f"[lock_field] {msg}"])
        return {"success": False, "error": msg}

    source_field = FIELD_SOURCE_MAP[field_name]
    cur = conn.cursor()

    try:
        cur.execute("PRAGMA table_info(Devices)")
        device_columns = {row["name"] for row in cur.fetchall()}
    except Exception as e:
        device_columns = set()
        mylog("none", [f"[lock_field] Failed to get table info: {e}"])

    if device_columns and source_field not in device_columns:
        msg = f"Source column {source_field} missing for {field_name}"
        mylog("debug", [f"[lock_field] {msg}"])
        return {"success": False, "error": msg}

    sql = f"UPDATE Devices SET {source_field}='LOCKED' WHERE devMac = ?"

    try:
        cur.execute(sql, (devMac,))
        conn.commit()
        mylog("debug", [f"[lock_field] Locked {field_name} for {devMac}"])
        return {"success": True, "error": None}
    except Exception as e:
        mylog("none", [f"[lock_field] ERROR: {e}"])
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def unlock_field(devMac, field_name, conn):
    """
    Unlock a field so plugins can overwrite it again.

    Returns:
        dict: {"success": bool, "error": str|None}
    """
    if field_name not in FIELD_SOURCE_MAP:
        msg = f"Field {field_name} does not support unlocking"
        mylog("debug", [f"[unlock_field] {msg}"])
        return {"success": False, "error": msg}

    source_field = FIELD_SOURCE_MAP[field_name]
    cur = conn.cursor()

    try:
        cur.execute("PRAGMA table_info(Devices)")
        device_columns = {row["name"] for row in cur.fetchall()}
    except Exception as e:
        device_columns = set()
        mylog("none", [f"[unlock_field] Failed to get table info: {e}"])

    if device_columns and source_field not in device_columns:
        msg = f"Source column {source_field} missing for {field_name}"
        mylog("debug", [f"[unlock_field] {msg}"])
        return {"success": False, "error": msg}

    sql = f"UPDATE Devices SET {source_field}='' WHERE devMac = ?"

    try:
        cur.execute(sql, (devMac,))
        conn.commit()
        mylog("debug", [f"[unlock_field] Unlocked {field_name} for {devMac}"])
        return {"success": True, "error": None}
    except Exception as e:
        mylog("none", [f"[unlock_field] ERROR: {e}"])
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def unlock_fields(conn, mac=None, fields=None, clear_all=False):
    """
    Unlock or clear source fields for one device, multiple devices, or all devices.

    Args:
        conn: Database connection object.
        mac: Device MAC address (string) or list of MACs. If None, operate on all devices.
        fields: Optional list of fields to unlock. If None, use all tracked fields.
        clear_all: If True, clear all values in source fields; otherwise, only clear LOCKED/USER.

    Returns:
        dict: {
            "success": bool,
            "error": str|None,
            "devicesAffected": int,
            "fieldsAffected": list
        }
    """
    target_fields = fields if fields else list(FIELD_SOURCE_MAP.keys())
    if not target_fields:
        return {"success": False, "error": "No fields to process", "devicesAffected": 0, "fieldsAffected": []}

    try:
        cur = conn.cursor()
        fields_set_clauses = []

        for field in target_fields:
            source_field = FIELD_SOURCE_MAP[field]
            if clear_all:
                fields_set_clauses.append(f"{source_field}=''")
            else:
                fields_set_clauses.append(
                    f"{source_field}=CASE WHEN {source_field} IN ('LOCKED','USER') THEN '' ELSE {source_field} END"
                )

        set_clause = ", ".join(fields_set_clauses)

        if mac:
            # mac can be a single string or a list
            macs = mac if isinstance(mac, list) else [mac]
            normalized_macs = [normalize_mac(m) for m in macs]

            placeholders = ",".join("?" for _ in normalized_macs)
            sql = f"UPDATE Devices SET {set_clause} WHERE devMac IN ({placeholders})"
            cur.execute(sql, normalized_macs)
        else:
            # All devices
            sql = f"UPDATE Devices SET {set_clause}"
            cur.execute(sql)

        conn.commit()
        return {
            "success": True,
            "error": None,
            "devicesAffected": cur.rowcount,
            "fieldsAffected": target_fields,
        }

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "success": False,
            "error": str(e),
            "devicesAffected": 0,
            "fieldsAffected": [],
        }
    finally:
        conn.close()
