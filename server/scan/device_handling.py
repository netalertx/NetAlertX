import subprocess
import os
import re
import ipaddress
from helper import get_setting_value, check_IP_format
from utils.datetime_utils import timeNowUTC, normalizeTimeStamp
from logger import mylog, Logger
from const import vendorsPath, vendorsPathNewest, sql_generateGuid, NULL_EQUIVALENTS
from models.device_instance import DeviceInstance
from scan.name_resolution import NameResolver
from scan.device_heuristics import guess_icon, guess_type
from db.db_helper import sanitize_SQL_input, list_to_where, safe_int
from db.authoritative_handler import (
    get_overwrite_sql_clause,
    can_overwrite_field,
    get_plugin_authoritative_settings,
    get_source_for_field_update_with_value,
    FIELD_SOURCE_MAP
)
from helper import format_ip_long

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

_device_columns_cache = None


def get_device_columns(sql, force_reload=False):
    """
    Return a set of column names in the Devices table.

    Cached after first call unless force_reload=True.
    """
    global _device_columns_cache
    if _device_columns_cache is None or force_reload:
        try:
            _device_columns_cache = {row["name"] for row in sql.execute("PRAGMA table_info(Devices)").fetchall()}
        except Exception:
            _device_columns_cache = set()
    return _device_columns_cache


def has_column(sql, column_name):
    """
    Check if a column exists in Devices table.

    Uses cached columns.
    """
    device_columns = get_device_columns(sql)
    return column_name in device_columns


# -------------------------------------------------------------------------------
# Removing devices from the CurrentScan DB table which the user chose to ignore by MAC or IP
def exclude_ignored_devices(db):
    sql = db.sql  # Database interface for executing queries

    mac_condition = list_to_where(
        "OR", "scanMac", "LIKE", get_setting_value("NEWDEV_ignored_MACs")
    )
    ip_condition = list_to_where(
        "OR", "scanLastIP", "LIKE", get_setting_value("NEWDEV_ignored_IPs")
    )

    # Only delete if either the MAC or IP matches an ignored condition
    conditions = []
    if mac_condition:
        conditions.append(mac_condition)
    if ip_condition:
        conditions.append(ip_condition)

    # Join conditions and prepare the query
    conditions_str = " OR ".join(conditions)
    if conditions_str:
        query = f"""DELETE FROM CurrentScan WHERE
                        1=1
                        AND (
                            {conditions_str}
                        )
                """
    else:
        query = "DELETE FROM CurrentScan WHERE 1=1 AND 1=0"  # No valid conditions, prevent deletion

    mylog("debug", f"[New Devices] Excluding Ignored Devices Query: {query}")

    sql.execute(query)


# -------------------------------------------------------------------------------
FIELD_SPECS = {

    # ⚠ "priority" is unused currently ⚠

    # ==========================================================
    # DEVICE NAME
    # ==========================================================
    "devName": {
        "scan_col": "scanName",
        "source_col": "devNameSource",
        "empty_values": NULL_EQUIVALENTS,
        "default_value": "(unknown)",
        "priority": ["NSLOOKUP", "AVAHISCAN", "NBTSCAN", "DIGSCAN", "ARPSCAN", "DHCPLSS", "NEWDEV", "N/A"],
    },

    # ==========================================================
    # IP ADDRESS (last seen)
    # ==========================================================
    "devLastIP": {
        "scan_col": "scanLastIP",
        "source_col": "devLastIPSource",
        "empty_values": NULL_EQUIVALENTS,
        "priority": ["ARPSCAN", "NEWDEV", "N/A"],
        "default_value": "0.0.0.0",
        "allow_override_if_changed": True,
    },

    # ==========================================================
    # VENDOR
    # ==========================================================
    "devVendor": {
        "scan_col": "scanVendor",
        "source_col": "devVendorSource",
        "empty_values": NULL_EQUIVALENTS,
        "priority": ["VNDRPDT", "ARPSCAN", "NEWDEV", "N/A"],
    },


    # ==========================================================
    # SYNC HUB NODE NAME
    # ==========================================================
    "devSyncHubNode": {
        "scan_col": "scanSyncHubNode",
        "source_col": None,
        "empty_values": NULL_EQUIVALENTS,
        "priority": None,
    },

    # ==========================================================
    # Network Site
    # ==========================================================
    "devSite": {
        "scan_col": "scanSite",
        "source_col": None,
        "empty_values": NULL_EQUIVALENTS,
        "priority": None,
    },

    # ==========================================================
    # VLAN
    # ==========================================================
    "devVlan": {
        "scan_col": "scanVlan",
        "source_col": "devVlanSource",
        "empty_values": NULL_EQUIVALENTS,
        "priority": None,
    },

    # ==========================================================
    # devType
    # ==========================================================
    "devType": {
        "scan_col": "scanType",
        "source_col": None,
        "empty_values": NULL_EQUIVALENTS,
        "priority": None,
    },

    # ==========================================================
    # TOPOLOGY (PARENT NODE)
    # ==========================================================
    "devParentMAC": {
        "scan_col": "scanParentMAC",
        "source_col": "devParentMACSource",
        "empty_values": NULL_EQUIVALENTS,
        "priority": ["SNMPDSC", "UNIFIAPI", "UNFIMP", "NEWDEV", "N/A"],
    },

    "devParentPort": {
        "scan_col": "scanParentPort",
        "source_col": None,
        "empty_values": NULL_EQUIVALENTS,
        "priority": ["SNMPDSC", "UNIFIAPI", "UNFIMP", "NEWDEV", "N/A"],
    },

    # ==========================================================
    # WIFI SSID
    # ==========================================================
    "devSSID": {
        "scan_col": "scanSSID",
        "source_col": None,
        "empty_values": NULL_EQUIVALENTS,
        "priority": ["SNMPDSC", "UNIFIAPI", "UNFIMP", "NEWDEV", "N/A"],
    },
}


def update_presence_from_CurrentScan(db):
    """
    Update devPresentLastScan based on whether the device has entries in CurrentScan.
    """
    sql = db.sql
    mylog("debug", "[Update Devices] - Updating devPresentLastScan")

    # Mark present if exists in CurrentScan
    sql.execute("""
        UPDATE Devices
        SET devPresentLastScan = 1
        WHERE EXISTS (
            SELECT 1 FROM CurrentScan
            WHERE devMac = scanMac
        )
    """)

    # Mark not present if not in CurrentScan
    sql.execute("""
        UPDATE Devices
        SET devPresentLastScan = 0
        WHERE NOT EXISTS (
            SELECT 1 FROM CurrentScan
            WHERE devMac = scanMac
        )
    """)


def update_devLastConnection_from_CurrentScan(db):
    """
    Update devLastConnection to current time for all devices seen in CurrentScan.
    """
    sql = db.sql
    startTime = timeNowUTC()
    mylog("debug", f"[Update Devices] - Updating devLastConnection to {startTime}")

    sql.execute(f"""
        UPDATE Devices
        SET devLastConnection = '{startTime}'
        WHERE EXISTS (
            SELECT 1 FROM CurrentScan
            WHERE devMac = scanMac
        )
    """)


def update_devices_data_from_scan(db):
    sql = db.sql

    # ----------------------------------------------------------------
    # 1️⃣ Get plugin scan methods
    # ----------------------------------------------------------------
    plugin_rows = sql.execute("SELECT DISTINCT scanSourcePlugin FROM CurrentScan").fetchall()
    plugin_prefixes = [row[0] for row in plugin_rows if row[0]] or [None]

    plugin_settings_cache = {}

    def get_plugin_settings_cached(plugin_prefix):
        if plugin_prefix not in plugin_settings_cache:
            plugin_settings_cache[plugin_prefix] = get_plugin_authoritative_settings(plugin_prefix)
        return plugin_settings_cache[plugin_prefix]

    # ----------------------------------------------------------------
    # 2️⃣ Loop over plugins & update fields
    # ----------------------------------------------------------------
    for plugin_prefix in plugin_prefixes:
        filter_by_scan_method = bool(plugin_prefix)
        source_prefix = plugin_prefix if filter_by_scan_method else "NEWDEV"
        plugin_settings = get_plugin_settings_cached(source_prefix)

        # Get all devices joined with latest scan
        sql_tmp = f"""
            SELECT *
            FROM LatestDeviceScan
            {"WHERE scanSourcePlugin = ?" if filter_by_scan_method else ""}
        """
        rows = sql.execute(sql_tmp, (source_prefix,) if filter_by_scan_method else ()).fetchall()
        col_names = [desc[0] for desc in sql.description]

        for row in rows:
            row_dict = dict(zip(col_names, row))

            for field, spec in FIELD_SPECS.items():

                scan_col = spec.get("scan_col")
                if scan_col not in row_dict:
                    continue

                current_value = row_dict.get(field)
                current_source = row_dict.get(f"{field}Source") or ""
                new_value = row_dict.get(scan_col)

                if can_overwrite_field(
                    field_name=field,
                    current_value=current_value,
                    current_source=current_source,
                    plugin_prefix=source_prefix,
                    plugin_settings=plugin_settings,
                    field_value=new_value,
                    allow_override_if_changed=spec.get("allow_override_if_changed", False)
                ):
                    # Build UPDATE dynamically
                    update_cols = [f"{field} = ?"]
                    sql_val = [new_value]

                    #  if a source field available, update too
                    source_field = FIELD_SOURCE_MAP.get(field)
                    if source_field:
                        update_cols.append(f"{source_field} = ?")
                        sql_val.append(source_prefix)

                    sql_val.append(row_dict["devMac"])

                    sql_tmp = f"""
                        UPDATE Devices
                        SET {', '.join(update_cols)}
                        WHERE devMac = ?
                    """

                    mylog("debug", f"[Update Devices] - ({source_prefix}) current_value: {current_value} new_value: {new_value} -> {field}")
                    mylog("debug", f"[Update Devices] - ({source_prefix}) {spec['scan_col']} -> {field}")
                    mylog("debug", f"[Update Devices] sql_tmp: {sql_tmp}, sql_val: {sql_val}")
                    sql.execute(sql_tmp, sql_val)

    db.commitDB()


def update_ipv4_ipv6(db):
    """
    Fill devPrimaryIPv4 and devPrimaryIPv6 based on devLastIP.
    Skips empty devLastIP and preserves existing values for the other version.
    """
    sql = db.sql
    mylog("debug", "[Update Devices] Updating devPrimaryIPv4 / devPrimaryIPv6 from devLastIP")

    devices = sql.execute("SELECT devMac, devLastIP FROM Devices").fetchall()
    records_to_update = []

    for device in devices:
        last_ip = device["devLastIP"]
        # Keeping your specific skip logic
        if not last_ip or last_ip.lower() in ("", "null", "(unknown)", "(Unknown)"):
            continue

        ipv4, ipv6 = None, None
        try:
            ip_obj = ipaddress.ip_address(last_ip)
            if ip_obj.version == 4:
                ipv4 = last_ip
            else:
                ipv6 = last_ip
        except ValueError:
            continue

        records_to_update.append((ipv4, ipv6, device["devMac"]))

    if records_to_update:
        # We use COALESCE(?, Column) so that if the first arg is NULL,
        # it keeps the current value of the column.

        # mylog("none", f"[Update Devices] Updated records_to_update: {records_to_update}")

        sql.executemany(
            """
            UPDATE Devices
            SET devPrimaryIPv4 = COALESCE(NULLIF(?, ''), devPrimaryIPv4),
                devPrimaryIPv6 = COALESCE(NULLIF(?, ''), devPrimaryIPv6)
            WHERE devMac = ?
            """,
            records_to_update,
        )

    mylog("debug", f"[Update Devices] Updated {len(records_to_update)} IPv4/IPv6 entries")


def update_icons_and_types(db):
    sql = db.sql
    # Guess ICONS
    recordsToUpdate = []

    default_icon = get_setting_value("NEWDEV_devIcon")

    if get_setting_value("NEWDEV_replace_preset_icon"):
        query = f"""SELECT * FROM Devices
                    WHERE devIcon in ('', 'null', '{default_icon}')
                        OR devIcon IS NULL"""
    else:
        query = """SELECT * FROM Devices
                    WHERE devIcon in ('', 'null')
                        OR devIcon IS NULL"""

    for device in sql.execute(query):
        # Conditional logic for devIcon guessing
        devIcon = guess_icon(
            device["devVendor"],
            device["devMac"],
            device["devLastIP"],
            device["devName"],
            default_icon,
        )

        recordsToUpdate.append([devIcon, device["devMac"]])

    mylog("debug", f"[Update Devices] recordsToUpdate: {recordsToUpdate}")

    if len(recordsToUpdate) > 0:
        sql.executemany(
            "UPDATE Devices SET devIcon = ? WHERE devMac = ? ", recordsToUpdate
        )

    # Guess Type
    recordsToUpdate = []
    query = """SELECT * FROM Devices
                    WHERE devType in ('', 'null')
                OR devType IS NULL"""
    default_type = get_setting_value("NEWDEV_devType")

    for device in sql.execute(query):
        # Conditional logic for devIcon guessing
        devType = guess_type(
            device["devVendor"],
            device["devMac"],
            device["devLastIP"],
            device["devName"],
            default_type,
        )

        recordsToUpdate.append([devType, device["devMac"]])

    if len(recordsToUpdate) > 0:
        sql.executemany(
            "UPDATE Devices SET devType = ? WHERE devMac = ? ", recordsToUpdate
        )


def update_vendors_from_mac(db):
    """
    Enrich Devices.devVendor using MAC vendor lookup (VNDRPDT),
    without modifying CurrentScan. Respects plugin authoritative rules.
    """
    sql = db.sql
    recordsToUpdate = []

    # Get plugin authoritative settings for vendor
    vendor_settings = get_plugin_authoritative_settings("VNDRPDT")
    vendor_clause = (
        get_overwrite_sql_clause("devVendor", "devVendorSource", vendor_settings)
        if has_column(sql, "devVendorSource")
        else "1=1"
    )

    # Build mapping: devMac -> vendor (skip unknown or invalid)
    vendor_map = {}
    for row in sql.execute("SELECT DISTINCT scanMac FROM CurrentScan"):
        mac = row["scanMac"]
        vendor = query_MAC_vendor(mac)
        if vendor not in (-1, -2):
            vendor_map[mac] = vendor

    mylog("debug", f"[Vendor Mapping] Found {len(vendor_map)} valid MACs to enrich")

    # Select Devices eligible for vendor update
    if "devVendor" in vendor_settings.get("set_always", []):
        # Always overwrite eligible devices
        query = f"SELECT devMac FROM Devices WHERE {vendor_clause}"
    else:
        # Only update empty or unknown vendors
        empty_vals = FIELD_SPECS.get("devVendor", {}).get("empty_values", [])
        empty_condition = " OR ".join(f"devVendor = '{v}'" for v in empty_vals)
        query = f"SELECT devMac FROM Devices WHERE ({empty_condition} OR devVendor IS NULL) AND {vendor_clause}"

    for device in sql.execute(query):
        mac = device["devMac"]
        if mac in vendor_map:
            recordsToUpdate.append([vendor_map[mac], "VNDRPDT", mac])

    # Apply updates
    if recordsToUpdate:
        if has_column(sql, "devVendorSource"):
            sql.executemany(
                "UPDATE Devices SET devVendor = ?, devVendorSource = ? WHERE devMac = ? AND " + vendor_clause,
                recordsToUpdate,
            )
        else:
            sql.executemany(
                "UPDATE Devices SET devVendor = ? WHERE devMac = ?",
                [(r[0], r[2]) for r in recordsToUpdate],
            )

    mylog("debug", f"[Update Devices] Updated {len(recordsToUpdate)} vendors using MAC mapping")


# -------------------------------------------------------------------------------
def save_scanned_devices(db):
    sql = db.sql  # TO-DO

    # Add Local MAC of default local interface
    local_mac_cmd = [
        "/sbin/ifconfig `ip -o route get 1 | sed 's/^.*dev \\([^ ]*\\).*$/\\1/;q'` | grep ether | awk '{print $2}'"
    ]
    local_mac = (
        subprocess.Popen(
            local_mac_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        .communicate()[0]
        .decode()
        .strip()
    )

    local_ip_cmd = ["ip -o route get 1 | sed 's/^.*src \\([^ ]*\\).*$/\\1/;q'"]
    local_ip = (
        subprocess.Popen(
            local_ip_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        .communicate()[0]
        .decode()
        .strip()
    )

    mylog("debug", ["[Save Devices] Saving this IP into the CurrentScan table:", local_ip])

    if check_IP_format(local_ip) == "":
        local_ip = "0.0.0.0"

    # Proceed if variable contains valid MAC
    if check_mac_or_internet(local_mac):
        sql.execute(
            f"""INSERT OR IGNORE INTO CurrentScan (scanMac, scanLastIP, scanVendor, scanSourcePlugin) VALUES ( '{local_mac}', '{local_ip}', Null, 'local_MAC') """
        )


# -------------------------------------------------------------------------------
def print_scan_stats(db):
    sql = db.sql  # TO-DO

    query = """
    SELECT
        (SELECT COUNT(*) FROM CurrentScan) AS devices_detected,
        (SELECT COUNT(*) FROM CurrentScan WHERE NOT EXISTS (SELECT 1 FROM Devices WHERE devMac = scanMac)) AS new_devices,
        (SELECT COUNT(*) FROM Devices WHERE devAlertDown != 0 AND NOT EXISTS (SELECT 1 FROM CurrentScan WHERE devMac = scanMac)) AS down_alerts,
        (SELECT COUNT(*) FROM Devices WHERE devAlertDown != 0 AND devPresentLastScan = 1 AND NOT EXISTS (SELECT 1 FROM CurrentScan WHERE devMac = scanMac)) AS new_down_alerts,
        (SELECT COUNT(*) FROM Devices WHERE devPresentLastScan = 0) AS new_connections,
        (SELECT COUNT(*) FROM Devices WHERE devPresentLastScan = 1 AND NOT EXISTS (SELECT 1 FROM CurrentScan WHERE devMac = scanMac)) AS disconnections,
                (SELECT COUNT(*) FROM Devices, CurrentScan
                        WHERE devMac = scanMac
                            AND scanLastIP IS NOT NULL
                            AND scanLastIP NOT IN ('', 'null', '(unknown)', '(Unknown)')
                            AND scanLastIP <> COALESCE(devPrimaryIPv4, '')
                            AND scanLastIP <> COALESCE(devPrimaryIPv6, '')
                            AND scanLastIP <> COALESCE(devLastIP, '')
                ) AS ip_changes,
        scanSourcePlugin,
        COUNT(*) AS scan_method_count
    FROM CurrentScan
    GROUP BY scanSourcePlugin
    """

    sql.execute(query)
    stats = sql.fetchall()

    mylog("verbose", f"[Scan Stats] Devices Detected.......: {stats[0]['devices_detected']}",)
    mylog("verbose", f"[Scan Stats] New Devices............: {stats[0]['new_devices']}")
    mylog("verbose", f"[Scan Stats] Down Alerts............: {stats[0]['down_alerts']}")
    mylog("verbose", f"[Scan Stats] New Down Alerts........: {stats[0]['new_down_alerts']}",)
    mylog("verbose", f"[Scan Stats] New Connections........: {stats[0]['new_connections']}",)
    mylog("verbose", f"[Scan Stats] Disconnections.........: {stats[0]['disconnections']}")
    mylog("verbose", f"[Scan Stats] IP Changes.............: {stats[0]['ip_changes']}")

    # if str(stats[0]["new_devices"]) != '0':
    mylog("trace", "   ================ DEVICES table content  ================")
    sql.execute("select * from Devices")
    rows = sql.fetchall()
    for row in rows:
        row_dict = dict(row)
        mylog("trace", f"    {row_dict}")

    mylog("trace", "   ================ CurrentScan table content  ================")
    sql.execute("select * from CurrentScan")
    rows = sql.fetchall()
    for row in rows:
        row_dict = dict(row)
        mylog("trace", f"    {row_dict}")

    mylog("trace", "   ================ Events table content where eve_PendingAlertEmail = 1  ================",)
    sql.execute("select * from Events where eve_PendingAlertEmail = 1")
    rows = sql.fetchall()
    for row in rows:
        row_dict = dict(row)
        mylog("trace", f"    {row_dict}")

    mylog("trace", "   ================ Events table COUNT  ================")
    sql.execute("select count(*) from Events")
    rows = sql.fetchall()
    for row in rows:
        row_dict = dict(row)
        mylog("trace", f"    {row_dict}")

    mylog("verbose", "[Scan Stats] Scan Method Statistics:")
    for row in stats:
        if row["scanSourcePlugin"] is not None:
            mylog("verbose", f"    {row['scanSourcePlugin']}: {row['scan_method_count']}")


# -------------------------------------------------------------------------------
def create_new_devices(db):
    sql = db.sql  # TO-DO
    startTime = timeNowUTC()

    # Insert events for new devices from CurrentScan (not yet in Devices)

    mylog("debug", '[New Devices] Insert "New Device" Events')
    query_new_device_events = f"""
    INSERT OR IGNORE INTO Events  (
        eve_MAC, eve_IP, eve_DateTime,
        eve_EventType, eve_AdditionalInfo,
        eve_PendingAlertEmail
    )
    SELECT DISTINCT scanMac, scanLastIP, '{startTime}', 'New Device', scanVendor, 1
    FROM CurrentScan
    WHERE NOT EXISTS (
        SELECT 1 FROM Devices
        WHERE devMac = scanMac
    )
    """

    # mylog('debug',f'[New Devices] Log Events Query: {query_new_device_events}')

    sql.execute(query_new_device_events)

    mylog("debug", "[New Devices] Insert Connection into session table")

    sql.execute(f"""INSERT INTO Sessions (
                        ses_MAC, ses_IP, ses_EventTypeConnection, ses_DateTimeConnection,
                        ses_EventTypeDisconnection, ses_DateTimeDisconnection,
                        ses_StillConnected, ses_AdditionalInfo
                    )
                    SELECT scanMac, scanLastIP, 'Connected', '{startTime}', NULL, NULL, 1, scanVendor
                    FROM CurrentScan
                    WHERE EXISTS (
                        SELECT 1 FROM Devices
                        WHERE devMac = scanMac
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM Sessions
                        WHERE ses_MAC = scanMac AND ses_StillConnected = 1
                    )
                    """)

    # Create new devices from CurrentScan
    mylog("debug", "[New Devices] 2 Create devices")

    # default New Device values preparation
    newDevColumns = """devAlertEvents,
                        devAlertDown,
                        devPresentLastScan,
                        devIsArchived,
                        devIsNew,
                        devSkipRepeated,
                        devScan,
                        devOwner,
                        devFavorite,
                        devGroup,
                        devComments,
                        devLogEvents,
                        devLocation,
                        devCustomProps,
                        devParentRelType,
                        devReqNicsOnline
                        """

    newDevDefaults = f"""{safe_int("NEWDEV_devAlertEvents")},
                        {safe_int("NEWDEV_devAlertDown")},
                        {safe_int("NEWDEV_devPresentLastScan")},
                        {safe_int("NEWDEV_devIsArchived")},
                        {safe_int("NEWDEV_devIsNew")},
                        {safe_int("NEWDEV_devSkipRepeated")},
                        {safe_int("NEWDEV_devScan")},
                        '{sanitize_SQL_input(get_setting_value("NEWDEV_devOwner"))}',
                        {safe_int("NEWDEV_devFavorite")},
                        '{sanitize_SQL_input(get_setting_value("NEWDEV_devGroup"))}',
                        '{sanitize_SQL_input(get_setting_value("NEWDEV_devComments"))}',
                        {safe_int("NEWDEV_devLogEvents")},
                        '{sanitize_SQL_input(get_setting_value("NEWDEV_devLocation"))}',
                        '{sanitize_SQL_input(get_setting_value("NEWDEV_devCustomProps"))}',
                        '{sanitize_SQL_input(get_setting_value("NEWDEV_devParentRelType"))}',
                        {safe_int("NEWDEV_devReqNicsOnline")}
                        """

    # Fetch data from CurrentScan skipping ignored devices by IP and MAC
    query = """SELECT scanMac, scanName, scanVendor, scanSourcePlugin, scanLastIP, scanSyncHubNode, scanParentMAC, scanParentPort, scanSite, scanSSID, scanType
                FROM CurrentScan """

    mylog("debug", f"[New Devices] Collecting New Devices Query: {query}")
    current_scan_data = sql.execute(query).fetchall()

    for row in current_scan_data:
        (
            scanMac,
            scanName,
            scanVendor,
            scanSourcePlugin,
            scanLastIP,
            scanSyncHubNode,
            scanParentMAC,
            scanParentPort,
            scanSite,
            scanSSID,
            scanType,
        ) = row

        # Preserve raw values to determine source attribution
        raw_name = str(scanName).strip() if scanName else ""
        raw_vendor = str(scanVendor).strip() if scanVendor else ""
        raw_ip = str(scanLastIP).strip() if scanLastIP else ""
        if raw_ip.lower() in NULL_EQUIVALENTS:
            raw_ip = ""
        raw_ssid = str(scanSSID).strip() if scanSSID else ""
        if raw_ssid.lower() in NULL_EQUIVALENTS:
            raw_ssid = ""
        raw_parent_mac = str(scanParentMAC).strip() if scanParentMAC else ""
        if raw_parent_mac.lower() in NULL_EQUIVALENTS:
            raw_parent_mac = ""
        raw_parent_port = str(scanParentPort).strip() if scanParentPort else ""
        if raw_parent_port.lower() in NULL_EQUIVALENTS:
            raw_parent_port = ""

        # Handle NoneType
        scanName = raw_name if raw_name else "(unknown)"
        scanType = (
            str(scanType).strip() if scanType else get_setting_value("NEWDEV_devType")
        )
        scanParentMAC = raw_parent_mac
        scanParentMAC = (
            scanParentMAC
            if scanParentMAC and scanMac.lower() != "internet"
            else (
                get_setting_value("NEWDEV_devParentMAC")
                if scanMac.lower() != "internet"
                else "null"
            )
        )
        scanSyncHubNode = (
            scanSyncHubNode
            if scanSyncHubNode and scanSyncHubNode != "null"
            else (get_setting_value("SYNC_node_name"))
        )

        # Derive primary IP family values
        scanLastIP = raw_ip
        scanSSID = raw_ssid
        scanParentPort = raw_parent_port
        cur_IP_normalized = check_IP_format(scanLastIP) if ":" not in scanLastIP else scanLastIP

        # Validate IPv6 addresses using format_ip_long for consistency (do not store integer result)
        if cur_IP_normalized and ":" in cur_IP_normalized:
            validated_ipv6 = format_ip_long(cur_IP_normalized)
            if validated_ipv6 is None or validated_ipv6 < 0:
                cur_IP_normalized = ""

        primary_ipv4 = cur_IP_normalized if cur_IP_normalized and ":" not in cur_IP_normalized else ""
        primary_ipv6 = cur_IP_normalized if cur_IP_normalized and ":" in cur_IP_normalized else ""

        plugin_prefix = str(scanSourcePlugin).strip() if scanSourcePlugin else "NEWDEV"

        dev_mac_source = get_source_for_field_update_with_value(
            "devMac", plugin_prefix, scanMac, is_user_override=False
        )
        dev_name_source = get_source_for_field_update_with_value(
            "devName", plugin_prefix, raw_name, is_user_override=False
        )
        dev_vendor_source = get_source_for_field_update_with_value(
            "devVendor", plugin_prefix, raw_vendor, is_user_override=False
        )
        dev_last_ip_source = get_source_for_field_update_with_value(
            "devLastIP", plugin_prefix, cur_IP_normalized, is_user_override=False
        )
        dev_ssid_source = get_source_for_field_update_with_value(
            "devSSID", plugin_prefix, raw_ssid, is_user_override=False
        )
        dev_parent_mac_source = get_source_for_field_update_with_value(
            "devParentMAC", plugin_prefix, raw_parent_mac, is_user_override=False
        )
        dev_parent_port_source = get_source_for_field_update_with_value(
            "devParentPort", plugin_prefix, raw_parent_port, is_user_override=False
        )
        dev_parent_rel_type_source = "NEWDEV"
        dev_fqdn_source = "NEWDEV"
        dev_vlan_source = "NEWDEV"

        # Preparing the individual insert statement
        sqlQuery = f"""INSERT OR IGNORE INTO Devices
                        (
                            devMac,
                            devName,
                            devVendor,
                            devLastIP,
                            devPrimaryIPv4,
                            devPrimaryIPv6,
                            devFirstConnection,
                            devLastConnection,
                            devSyncHubNode,
                            devGUID,
                            devParentMAC,
                            devParentPort,
                            devSite,
                            devSSID,
                            devType,
                            devSourcePlugin,
                            devMacSource,
                            devNameSource,
                            devFQDNSource,
                            devLastIPSource,
                            devVendorSource,
                            devSSIDSource,
                            devParentMACSource,
                            devParentPortSource,
                            devParentRelTypeSource,
                            devVlanSource,
                            {newDevColumns}
                        )
                        VALUES
                        (
                            '{sanitize_SQL_input(scanMac)}',
                            '{sanitize_SQL_input(scanName)}',
                            '{sanitize_SQL_input(scanVendor)}',
                            '{sanitize_SQL_input(cur_IP_normalized)}',
                            '{sanitize_SQL_input(primary_ipv4)}',
                            '{sanitize_SQL_input(primary_ipv6)}',
                            ?,
                            ?,
                            '{sanitize_SQL_input(scanSyncHubNode)}',
                            {sql_generateGuid},
                            '{sanitize_SQL_input(scanParentMAC)}',
                            '{sanitize_SQL_input(scanParentPort)}',
                            '{sanitize_SQL_input(scanSite)}',
                            '{sanitize_SQL_input(scanSSID)}',
                            '{sanitize_SQL_input(scanType)}',
                            '{sanitize_SQL_input(scanSourcePlugin)}',
                            '{sanitize_SQL_input(dev_mac_source)}',
                            '{sanitize_SQL_input(dev_name_source)}',
                            '{sanitize_SQL_input(dev_fqdn_source)}',
                            '{sanitize_SQL_input(dev_last_ip_source)}',
                            '{sanitize_SQL_input(dev_vendor_source)}',
                            '{sanitize_SQL_input(dev_ssid_source)}',
                            '{sanitize_SQL_input(dev_parent_mac_source)}',
                            '{sanitize_SQL_input(dev_parent_port_source)}',
                            '{sanitize_SQL_input(dev_parent_rel_type_source)}',
                            '{sanitize_SQL_input(dev_vlan_source)}',
                            {newDevDefaults}
                        )"""

        mylog("trace", f"[New Devices] Create device SQL: {sqlQuery}")

        sql.execute(sqlQuery, (startTime, startTime))

    mylog("debug", "[New Devices] New Devices end")
    db.commitDB()


# -------------------------------------------------------------------------------
# Check if plugins data changed
def check_plugin_data_changed(pm, plugins_to_check):
    """
    Checks whether any of the specified plugins have updated data since their
    last recorded check time.

    This function compares each plugin's `lastDataChange` timestamp from
    `pm.plugin_states` with its corresponding `lastDataCheck` timestamp from
    `pm.plugin_checks`. If a plugin's data has changed more recently than it
    was last checked, it is flagged as changed.

    Args:
        pm (object): Plugin manager or state object containing:
            - plugin_states (dict): Per-plugin metadata with "lastDataChange".
            - plugin_checks (dict): Per-plugin last check timestamps.
        plugins_to_check (list[str]): List of plugin names to validate.

    Returns:
        bool: True if any plugin data has changed since last check,
              otherwise False.

    Logging:
        - Logs unexpected or invalid timestamps at level 'none'.
        - Logs when no changes are detected at level 'debug'.
        - Logs each changed plugin at level 'debug'.
    """

    plugins_changed = []

    for plugin_name in plugins_to_check:

        last_data_change = pm.plugin_states.get(plugin_name, {}).get("lastDataChange")
        last_data_check = pm.plugin_checks.get(plugin_name, "")

        if not last_data_change:
            continue

        # Normalize and validate last_changed timestamp
        last_changed_ts = normalizeTimeStamp(last_data_change)

        if last_changed_ts is None:
            mylog('none', f'[check_plugin_data_changed] Unexpected last_data_change timestamp for {plugin_name} (input|output): ({last_data_change}|{last_changed_ts})')

        # Normalize and validate last_data_check timestamp
        last_data_check_ts = normalizeTimeStamp(last_data_check)

        if last_data_check_ts is None:
            mylog('none', f'[check_plugin_data_changed] Unexpected last_data_check timestamp for {plugin_name} (input|output): ({last_data_check}|{last_data_check_ts})')

        # Track which plugins have newer state than last_checked
        if last_data_check_ts is None or last_changed_ts is None or last_changed_ts > last_data_check_ts:
            mylog('debug', f'[check_plugin_data_changed] {plugin_name} changed (last_changed_ts|last_data_check_ts): ({last_changed_ts}|{last_data_check_ts})')
            plugins_changed.append(plugin_name)

    # Skip if no plugin state changed since last check
    if len(plugins_changed) == 0:
        mylog('debug', f'[check_plugin_data_changed] No relevant plugin changes since last check for {plugins_to_check}')
        return False

    # Continue if changes detected
    for p in plugins_changed:
        mylog('debug', f'[check_plugin_data_changed] {p} changed (last_change|last_check): ({pm.plugin_states.get(p, {}).get("lastDataChange")}|{pm.plugin_checks.get(p)})')

    return True


# -------------------------------------------------------------------------------
def update_devices_names(pm):

    # --- Short-circuit if no name-resolution plugin has changed ---
    if check_plugin_data_changed(pm, ["DIGSCAN", "NSLOOKUP", "NBTSCAN", "AVAHISCAN"]) is False:
        mylog('debug', '[Update Device Name] No relevant plugin changes since last check.')
        return

    mylog('debug', '[Update Device Name] Check if unknown devices present to resolve names for or if REFRESH_FQDN enabled.')

    sql = pm.db.sql
    resolver = NameResolver(pm.db)
    device_handler = DeviceInstance()

    nameNotFound = "(name not found)"

    # Define resolution strategies in priority order
    strategies = [
        (resolver.resolve_dig, "DIGSCAN"),
        (resolver.resolve_mdns, "AVAHISCAN"),
        (resolver.resolve_nslookup, "NSLOOKUP"),
        (resolver.resolve_nbtlookup, "NBTSCAN"),
    ]

    def resolve_devices(devices, resolve_both_name_and_fqdn=True):
        """
        Attempts to resolve device names and/or FQDNs using available strategies.

        Parameters:
            devices (list): List of devices to resolve.
            resolve_both_name_and_fqdn (bool): If True, resolves both name and FQDN.
                                               If False, resolves only FQDN.

        Returns:
            recordsToUpdate (list): List of
                [newName, nameSource, newFQDN, fqdnSource, devMac] or [newFQDN, fqdnSource, devMac].
            recordsNotFound (list): List of [nameNotFound, devMac] for DB update.
            foundStats (dict): Number of successes per strategy.
            notFound (int): Number of devices not resolved.
        """
        recordsToUpdate = []
        recordsNotFound = []
        foundStats = {label: 0 for _, label in strategies}
        notFound = 0

        for device in devices:
            resolved_successfully = False

            # Attempt each resolution strategy in order
            for resolve_fn, label in strategies:
                resolved = resolve_fn(device["devMac"], device["devLastIP"])

                # Extract values
                current_raw = resolved.raw if resolved.raw else ""
                current_cleaned = resolved.cleaned if resolved.cleaned else ""

                # Validation: Ensure we actually got a real FQDN/Name
                if (current_raw not in [nameNotFound, "", "localhost."] and " communications error to " not in current_raw):

                    foundStats[label] += 1
                    resolved_successfully = True

                    if resolve_both_name_and_fqdn:
                        # Logic: If cleaned name is missing, fallback to raw,
                        # but if both are missing, this strategy failed.
                        final_name = current_cleaned if current_cleaned else current_raw
                        recordsToUpdate.append([final_name, label, current_raw, label, device["devMac"]])
                    else:
                        recordsToUpdate.append([current_raw, label, device["devMac"]])

                    break  # Stop trying other strategies for this device

            # If after all strategies we found nothing
            if not resolved_successfully:
                notFound += 1
                if resolve_both_name_and_fqdn:
                    if device["devName"] != nameNotFound:
                        recordsNotFound.append([nameNotFound, device["devMac"]])

        return recordsToUpdate, recordsNotFound, foundStats, notFound

    # --- Step 1: Update device names for unknown devices ---
    unknownDevices = device_handler.getUnknown()
    if unknownDevices:
        mylog("verbose", f"[Update Device Name] Trying to resolve devices without name. Unknown devices count: {len(unknownDevices)}",)

        # Try resolving both name and FQDN
        recordsToUpdate, recordsNotFound, fs, notFound = resolve_devices(
            unknownDevices
        )

        # Log summary
        res_string = f"{fs['DIGSCAN']}/{fs['AVAHISCAN']}/{fs['NSLOOKUP']}/{fs['NBTSCAN']}"
        mylog("verbose", f"[Update Device Name] Names Found (DIGSCAN/AVAHISCAN/NSLOOKUP/NBTSCAN): {len(recordsToUpdate)} ({res_string})",)
        mylog("verbose", f"[Update Device Name] Names Not Found         : {notFound}")

        # Apply updates to database
        sql.executemany(
            """UPDATE Devices
                SET devName = CASE
                    WHEN COALESCE(devNameSource, '') IN ('USER', 'LOCKED') THEN devName
                    ELSE ?
                END
                WHERE devMac = ?
                  AND COALESCE(devNameSource, '') IN ('', 'NEWDEV')""",
            recordsNotFound,
        )

        records_by_plugin = {}
        for entry in recordsToUpdate:
            records_by_plugin.setdefault(entry[1], []).append(entry)

        for plugin_label, plugin_records in records_by_plugin.items():
            plugin_settings = get_plugin_authoritative_settings(plugin_label)
            name_clause = get_overwrite_sql_clause(
                "devName", "devNameSource", plugin_settings
            )
            fqdn_clause = get_overwrite_sql_clause(
                "devFQDN", "devFQDNSource", plugin_settings
            )

            sql.executemany(
                f"""UPDATE Devices
                    SET devName = CASE
                        WHEN {name_clause} THEN ?
                        ELSE devName
                    END,
                        devNameSource = CASE
                        WHEN {name_clause} THEN ?
                        ELSE devNameSource
                    END,
                        devFQDN = CASE
                        WHEN {fqdn_clause} THEN ?
                        ELSE devFQDN
                    END,
                        devFQDNSource = CASE
                        WHEN {fqdn_clause} THEN ?
                        ELSE devFQDNSource
                    END
                    WHERE devMac = ?""",
                plugin_records,
            )

    # --- Step 2: Optionally refresh FQDN for all devices ---
    if get_setting_value("REFRESH_FQDN"):
        allDevices = device_handler.getAll()
        if allDevices:
            mylog("verbose", f"[Update FQDN] Trying to resolve FQDN. Devices count: {len(allDevices)}",)

            # Try resolving only FQDN
            recordsToUpdate, _, fs, notFound = resolve_devices(
                allDevices, resolve_both_name_and_fqdn=False
            )

            # Log summary
            res_string = f"{fs['DIGSCAN']}/{fs['AVAHISCAN']}/{fs['NSLOOKUP']}/{fs['NBTSCAN']}"
            mylog("verbose", f"[Update FQDN] Names Found (DIGSCAN/AVAHISCAN/NSLOOKUP/NBTSCAN): {len(recordsToUpdate)}({res_string})",)
            mylog("verbose", f"[Update FQDN] Names Not Found         : {notFound}")

            records_by_plugin = {}
            for entry in recordsToUpdate:
                records_by_plugin.setdefault(entry[1], []).append(entry)

            for plugin_label, plugin_records in records_by_plugin.items():
                plugin_settings = get_plugin_authoritative_settings(plugin_label)
                fqdn_clause = get_overwrite_sql_clause(
                    "devFQDN", "devFQDNSource", plugin_settings
                )

                # Apply FQDN-only updates
                sql.executemany(
                    f"""UPDATE Devices
                        SET devFQDN = CASE
                            WHEN {fqdn_clause} THEN ?
                            ELSE devFQDN
                        END,
                            devFQDNSource = CASE
                            WHEN {fqdn_clause} THEN ?
                            ELSE devFQDNSource
                        END
                        WHERE devMac = ?""",
                    plugin_records,
                )

    # Commit all database changes
    pm.db.commitDB()

    # --- Step 3: Log last checked time ---
    # After resolving names, update last checked
    pm.plugin_checks = {"DIGSCAN": timeNowUTC(), "AVAHISCAN": timeNowUTC(), "NSLOOKUP": timeNowUTC(), "NBTSCAN": timeNowUTC()}


# -------------------------------------------------------------------------------
# Updates devPresentLastScan for parent devices based on the presence of their NICs
def update_devPresentLastScan_based_on_nics(db):
    """
    Updates devPresentLastScan in the Devices table for parent devices
    based on the presence of their NICs and the devReqNicsOnline setting.

    Args:
        db: A database object with `.execute()` and `.fetchall()` methods.
    """

    sql = db.sql

    # Step 1: Load all devices from the DB
    devices = sql.execute("SELECT * FROM Devices").fetchall()

    # Convert rows to dicts (assumes sql.row_factory = sqlite3.Row or similar)
    devices = [dict(row) for row in devices]

    # Build MAC -> NICs map
    mac_to_nics = {}
    for device in devices:
        if device.get("devParentRelType") == "nic":
            parent_mac = device.get("devParentMAC")
            if parent_mac:
                mac_to_nics.setdefault(parent_mac, []).append(device)

    # Step 2: For each non-NIC device, determine new devPresentLastScan
    updates = []
    for device in devices:
        if device.get("devParentRelType") == "nic":
            continue  # skip NICs

        mac = device.get("devMac")
        if not mac:
            continue

        req_all = str(device.get("devReqNicsOnline")) == "1"
        nics = mac_to_nics.get(mac, [])

        original = device.get("devPresentLastScan", 0)
        new_present = original

        if nics:
            nic_statuses = [nic.get("devPresentLastScan") == 1 for nic in nics]
            if req_all:
                new_present = int(all(nic_statuses))
            else:
                new_present = int(any(nic_statuses))

        # Only add update if changed
        if original != new_present:
            updates.append((new_present, mac))

    # Step 3: Execute batch update
    for present, mac in updates:
        sql.execute(
            "UPDATE Devices SET devPresentLastScan = ? WHERE devMac = ?", (present, mac)
        )

    db.commitDB()
    return len(updates)


# -------------------------------------------------------------------------------
# Force devPresentLastScan based on devForceStatus
def update_devPresentLastScan_based_on_force_status(db):
    """
    Forces devPresentLastScan in the Devices table based on devForceStatus.

    devForceStatus values:
      - "online"  -> devPresentLastScan = 1
      - "offline" -> devPresentLastScan = 0
      - "dont_force" or empty -> no change

    Args:
        db: A database object with `.execute()` and `.fetchone()` methods.

    Returns:
        int: Number of devices updated.
    """

    sql = db.sql

    online_count_row = sql.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM Devices
        WHERE LOWER(COALESCE(devForceStatus, '')) = 'online'
          AND devPresentLastScan != 1
        """
    ).fetchone()
    online_updates = online_count_row["cnt"] if online_count_row else 0

    offline_count_row = sql.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM Devices
        WHERE LOWER(COALESCE(devForceStatus, '')) = 'offline'
          AND devPresentLastScan != 0
        """
    ).fetchone()
    offline_updates = offline_count_row["cnt"] if offline_count_row else 0

    if online_updates > 0:
        sql.execute(
            """
            UPDATE Devices
            SET devPresentLastScan = 1
            WHERE LOWER(COALESCE(devForceStatus, '')) = 'online'
            """
        )

    if offline_updates > 0:
        sql.execute(
            """
            UPDATE Devices
            SET devPresentLastScan = 0
            WHERE LOWER(COALESCE(devForceStatus, '')) = 'offline'
            """
        )

    total_updates = online_updates + offline_updates
    if total_updates > 0:
        mylog("debug", f"[Update Devices] Forced devPresentLastScan for {total_updates} devices")

    db.commitDB()
    return total_updates


# -------------------------------------------------------------------------------
# Check if the variable contains a valid MAC address or "internet"
def check_mac_or_internet(input_str):
    # Regular expression pattern for matching a MAC address
    mac_pattern = r"([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})"

    if input_str.lower() == "internet":
        return True
    elif re.match(mac_pattern, input_str):
        return True
    else:
        return False


# -------------------------------------------------------------------------------
# Lookup unknown vendors on devices
def query_MAC_vendor(pMAC):
    pMACstr = str(pMAC)

    filePath = vendorsPath

    if os.path.isfile(vendorsPathNewest):
        filePath = vendorsPathNewest

    # Check MAC parameter
    mac = pMACstr.replace(":", "").lower()
    if len(pMACstr) != 17 or len(mac) != 12:
        return -2  # return -2 if ignored MAC

    # Search vendor in HW Vendors DB
    mac_start_string6 = mac[0:6]

    try:
        with open(filePath, "r") as f:
            for line in f:
                line_lower = (
                    line.lower()
                )  # Convert line to lowercase for case-insensitive matching
                if line_lower.startswith(mac_start_string6):
                    parts = line.split("\t", 1)
                    if len(parts) > 1:
                        vendor = parts[1].strip()
                        mylog("debug", [f"[Vendor Check] Found '{vendor}' for '{pMAC}' in {vendorsPath}"], )
                        return vendor
                    else:
                        mylog("debug", [f'[Vendor Check] ⚠ ERROR: Match found, but line could not be processed: "{line_lower}"'],)
                        return -1

        return -1  # MAC address not found in the database
    except FileNotFoundError:
        mylog("none", [f"[Vendor Check] ⚠ ERROR: Vendors file {vendorsPath} not found."])
        return -1
