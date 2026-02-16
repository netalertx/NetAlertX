import os
import base64
import re
import sqlite3
import csv
from io import StringIO
from front.plugins.plugin_helper import is_mac, normalize_mac
from logger import mylog
from models.plugin_object_instance import PluginObjectInstance
from database import get_temp_db_connection
from db.db_helper import get_table_json, get_device_conditions, get_device_condition_by_status, row_to_json, get_date_from_period
from db.authoritative_handler import (
    enforce_source_on_user_update,
    get_locked_field_overrides,
    lock_field,
    unlock_field,
    FIELD_SOURCE_MAP,
    unlock_fields
)
from helper import is_random_mac, get_setting_value
from utils.datetime_utils import timeNowUTC


class DeviceInstance:

    # --- helpers --------------------------------------------------------------
    def _fetchall(self, query, params=()):
        conn = get_temp_db_connection()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _fetchone(self, query, params=()):
        conn = get_temp_db_connection()
        row = conn.execute(query, params).fetchone()
        conn.close()
        return dict(row) if row else None

    def _execute(self, query, params=()):
        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        conn.close()

    # --- public API -----------------------------------------------------------
    def getAll(self):
        return self._fetchall("SELECT * FROM Devices")

    def getUnknown(self):
        return self._fetchall("""
            SELECT * FROM Devices
            WHERE devName IN ("(unknown)", "(name not found)", "")
        """)

    def getValueWithMac(self, column_name, devMac):
        row = self._fetchone(f"""
            SELECT {column_name} FROM Devices WHERE devMac = ?
        """, (devMac,))
        return row.get(column_name) if row else None

    def getDown(self):
        return self._fetchall("""
            SELECT * FROM Devices
            WHERE devAlertDown = 1 AND devPresentLastScan = 0
        """)

    def getOffline(self):
        return self._fetchall("""
            SELECT * FROM Devices
            WHERE devPresentLastScan = 0
        """)

    def getByGUID(self, devGUID):
        return self._fetchone("""
            SELECT * FROM Devices WHERE devGUID = ?
        """, (devGUID,))

    def exists(self, devGUID):
        row = self._fetchone("""
            SELECT COUNT(*) as count FROM Devices WHERE devGUID = ?
        """, (devGUID,))
        return row['count'] > 0 if row else False

    def getByIP(self, ip):
        return self._fetchone("""
            SELECT * FROM Devices WHERE devLastIP = ?
        """, (ip,))

    def search(self, query):
        like = f"%{query}%"
        return self._fetchall("""
            SELECT * FROM Devices
            WHERE devMac LIKE ? OR devName LIKE ? OR devLastIP LIKE ?
        """, (like, like, like))

    def getLatest(self):
        return self._fetchone("""
            SELECT * FROM Devices
            ORDER BY devFirstConnection DESC LIMIT 1
        """)

    def getFavorite(self):
        return self._fetchall("""
            SELECT * FROM Devices
            WHERE devFavorite = 1
        """)

    def getNetworkTopology(self):
        rows = self._fetchall("""
            SELECT devName, devMac, devParentMAC, devParentPort, devVendor FROM Devices
        """)
        nodes = [{"id": r["devMac"], "name": r["devName"], "vendor": r["devVendor"]} for r in rows]
        links = [{"source": r["devParentMAC"], "target": r["devMac"], "port": r["devParentPort"]}
                 for r in rows if r["devParentMAC"]]
        return {"nodes": nodes, "links": links}

    def updateField(self, devGUID, field, value):
        if not self.exists(devGUID):
            msg = f"[Device] updateField: GUID {devGUID} not found"
            mylog("none", msg)
            raise ValueError(msg)
        self._execute(f"UPDATE Devices SET {field}=? WHERE devGUID=?", (value, devGUID))

    def delete(self, devGUID):
        if not self.exists(devGUID):
            msg = f"[Device] delete: GUID {devGUID} not found"
            mylog("none", msg)
            raise ValueError(msg)
        self._execute("DELETE FROM Devices WHERE devGUID=?", (devGUID,))

    def resolvePrimaryID(self, target):
        if is_mac(target):
            return target.lower()
        dev = self.getByIP(target)
        return dev['devMac'].lower() if dev else None

    def getOpenPorts(self, target):
        primary = self.resolvePrimaryID(target)
        if not primary:
            return []

        objs = PluginObjectInstance().getByField(
            plugPrefix='NMAP',
            matchedColumn='Object_PrimaryID',
            matchedKey=primary,
            returnFields=['Object_SecondaryID', 'Watched_Value2']
        )

        ports = []
        for o in objs:

            port = int(o.get('Object_SecondaryID') or 0)

            ports.append({"port": port, "service": o.get('Watched_Value2', '')})

        return ports

    # --- devices_endpoint.py methods (HTTP response layer) -------------------

    def getAll_AsResponse(self):
        """Return all devices as raw data (not jsonified)."""
        return self.getAll()

    def deleteDevices(self, macs):
        """
        Delete devices from the Devices table.
        - If `macs` is None → delete ALL devices.
        - If `macs` is a list → delete only matching MACs (supports wildcard '*').
        """
        conn = get_temp_db_connection()
        cur = conn.cursor()

        if macs is None:
            # No MACs provided → delete all
            cur.execute("DELETE FROM Devices")
            conn.commit()
            conn.close()
            return {"success": True, "deleted": "all"}

        deleted_count = 0

        for mac in macs:
            if "*" in mac:
                # Wildcard matching
                sql_pattern = mac.replace("*", "%")
                cur.execute("DELETE FROM Devices WHERE devMac LIKE ?", (sql_pattern,))
            else:
                # Exact match
                cur.execute("DELETE FROM Devices WHERE devMac = ?", (mac,))
            deleted_count += cur.rowcount

        conn.commit()
        conn.close()

        return {"success": True, "deleted_count": deleted_count}

    def deleteAllWithEmptyMacs(self):
        """Delete devices with empty MAC addresses."""
        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM Devices WHERE devMac IS NULL OR devMac = ''")
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        return {"success": True, "deleted": deleted}

    def deleteUnknownDevices(self):
        """Delete devices marked as unknown."""
        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute(
            """DELETE FROM Devices WHERE devName='(unknown)' OR devName='(name not found)'"""
        )
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        return {"success": True, "deleted": deleted}

    def exportDevices(self, export_format):
        """
        Export devices from the Devices table in the desired format.
        """
        conn = get_temp_db_connection()
        cur = conn.cursor()

        # Fetch all devices
        devices_json = get_table_json(cur, "SELECT * FROM Devices")
        conn.close()

        # Ensure columns exist
        columns = devices_json.columnNames or (
            list(devices_json["data"][0].keys()) if devices_json["data"] else []
        )

        if export_format == "json":
            return {
                "format": "json",
                "data": [row for row in devices_json["data"]],
                "columns": list(columns)
            }
        elif export_format == "csv":
            si = StringIO()
            writer = csv.DictWriter(si, fieldnames=columns, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in devices_json.json["data"]:
                writer.writerow(row)
            return {
                "format": "csv",
                "content": si.getvalue(),
            }
        else:
            return {"error": f"Unsupported format '{export_format}'"}

    def importCSV(self, file_storage=None, json_content=None):
        """
        Import devices from CSV.
        - json_content: base64-encoded CSV string
        - file_storage: uploaded file object
        - fallback: read from config/devices.csv
        """
        data = ""
        skipped = []

        # 1. Try JSON `content` (base64-encoded CSV)
        if json_content:
            try:
                data = base64.b64decode(json_content, validate=True).decode("utf-8")
            except Exception as e:
                return {"success": False, "error": f"Base64 decode failed: {e}"}

        # 2. Otherwise, try uploaded file
        elif file_storage:
            try:
                data = file_storage.read().decode("utf-8")
            except Exception as e:
                return {"success": False, "error": f"File read failed: {e}"}

        # 3. Fallback: try local file (same as PHP `$file = '../../../config/devices.csv';`)
        else:
            config_root = os.environ.get("NETALERTX_CONFIG", "/data/config")
            local_file = os.path.join(config_root, "devices.csv")
            try:
                with open(local_file, "r", encoding="utf-8") as f:
                    data = f.read()
            except FileNotFoundError:
                return {"success": False, "error": "CSV file missing"}

        if not data:
            return {"success": False, "error": "No CSV data found"}

        # --- Clean up newlines inside quoted fields ---
        data = re.sub(r'"([^"]*)"', lambda m: m.group(0).replace("\n", " "), data)

        # --- Parse CSV ---
        lines = data.splitlines()
        reader = csv.reader(lines)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration:
            return {"success": False, "error": "CSV missing header"}

        # --- Wipe Devices table ---
        conn = get_temp_db_connection()
        sql = conn.cursor()
        sql.execute("DELETE FROM Devices")

        # --- Prepare insert ---
        placeholders = ",".join(["?"] * len(header))
        insert_sql = f"INSERT INTO Devices ({', '.join(header)}) VALUES ({placeholders})"

        row_count = 0
        for idx, row in enumerate(reader, start=1):
            if len(row) != len(header):
                skipped.append(idx)
                continue
            try:
                sql.execute(insert_sql, [col.strip() for col in row])
                row_count += 1
            except sqlite3.Error as e:
                mylog("error", [f"[ImportCSV] SQL ERROR row {idx}: {e}"])
                skipped.append(idx)

        conn.commit()
        conn.close()

        return {"success": True, "inserted": row_count, "skipped_lines": skipped}

    def getTotals(self):
        """Get device totals by status."""
        conn = get_temp_db_connection()
        sql = conn.cursor()

        conditions = get_device_conditions()

        # Build sub-selects dynamically for all dictionary entries
        sub_queries = []
        for key, condition in conditions.items():
            # Make sure the alias is SQL-safe (no spaces or special chars)
            alias = key.replace(" ", "_").lower()
            sub_queries.append(f'(SELECT COUNT(*) FROM Devices {condition}) AS "{alias}"')

        # Join all sub-selects with commas
        query = "SELECT\n    " + ",\n    ".join(sub_queries)
        sql.execute(query)
        row = sql.fetchone()
        conn.close()

        return list(row) if row else []

    def getNamedTotals(self):
        """Get device totals by status."""
        conn = get_temp_db_connection()
        sql = conn.cursor()

        conditions = get_device_conditions()

        # Build sub-selects dynamically for all dictionary entries
        sub_queries = []
        for key, condition in conditions.items():
            # Make sure the alias is SQL-safe (no spaces or special chars)
            alias = key.replace(" ", "_").lower()
            sub_queries.append(f'(SELECT COUNT(*) FROM Devices {condition}) AS "{alias}"')

        # Join all sub-selects with commas
        query = "SELECT\n    " + ",\n    ".join(sub_queries)

        mylog('none', [f'[getNamedTotals] query {query}'])
        json_obj = get_table_json(sql, query, parameters=None)

        return json_obj

    def getByStatus(self, status=None):
        """
        Return devices filtered by status. Returns all if no status provided.
        Possible statuses: my, connected, favorites, new, down, archived
        """
        conn = get_temp_db_connection()
        sql = conn.cursor()

        # Build condition for SQL
        condition = get_device_condition_by_status(status) if status else ""

        query = f"SELECT * FROM Devices {condition}"
        sql.execute(query)

        table_data = []
        for row in sql.fetchall():
            r = dict(row)  # Convert sqlite3.Row to dict for .get()
            dev_name = r.get("devName", "")
            if r.get("devFavorite") == 1:
                dev_name = f'<span class="text-yellow">&#9733</span>&nbsp;{dev_name}'

            # Start with all fields from the device record
            device_record = r.copy()
            # Override with formatted fields
            device_record["id"] = r.get("devMac", "")
            device_record["title"] = dev_name
            device_record["favorite"] = r.get("devFavorite", 0)

            table_data.append(device_record)

        conn.close()
        return table_data

    # --- device_endpoint.py methods -------------------------------------------

    def getDeviceData(self, mac, period=""):
        """Fetch device info with children, event stats, and presence calculation."""
        now = timeNowUTC()

        # Special case for new device
        if mac.lower() == "new":
            device_data = {
                "devMac": "",
                "devName": "",
                "devOwner": "",
                "devType": "",
                "devVendor": "",
                "devFavorite": 0,
                "devGroup": "",
                "devComments": "",
                "devFirstConnection": now,
                "devLastConnection": now,
                "devLastIP": "",
                "devStaticIP": 0,
                "devScan": 0,
                "devLogEvents": 0,
                "devAlertEvents": 0,
                "devAlertDown": 0,
                "devParentRelType": "default",
                "devReqNicsOnline": 0,
                "devSkipRepeated": 0,
                "devLastNotification": "",
                "devPresentLastScan": 0,
                "devIsNew": 1,
                "devLocation": "",
                "devIsArchived": 0,
                "devParentMAC": "",
                "devParentPort": "",
                "devIcon": "",
                "devGUID": "",
                "devSite": "",
                "devSSID": "",
                "devSyncHubNode": str(get_setting_value("SYNC_node_name")),
                "devSourcePlugin": "",
                "devCustomProps": "",
                "devStatus": "Unknown",
                "devIsRandomMAC": False,
                "devSessions": 0,
                "devEvents": 0,
                "devDownAlerts": 0,
                "devPresenceHours": 0,
                "devFQDN": "",
                "devForceStatus" : "dont_force",
                "devVlan": ""
            }
            return device_data

        # Compute period date for sessions/events
        period_date_sql = get_date_from_period(period)

        # Fetch device info + computed fields
        sql = f"""
        SELECT
            d.*,
            CASE
                WHEN d.devAlertDown != 0 AND d.devPresentLastScan = 0 THEN 'Down'
                WHEN d.devPresentLastScan = 1 THEN 'On-line'
                ELSE 'Off-line'
            END AS devStatus,

            (SELECT COUNT(*) FROM Sessions
             WHERE ses_MAC = d.devMac AND (
                ses_DateTimeConnection >= {period_date_sql} OR
                ses_DateTimeDisconnection >= {period_date_sql} OR
                ses_StillConnected = 1
             )) AS devSessions,

            (SELECT COUNT(*) FROM Events
             WHERE eve_MAC = d.devMac AND eve_DateTime >= {period_date_sql}
               AND eve_EventType NOT IN ('Connected','Disconnected')) AS devEvents,

            (SELECT COUNT(*) FROM Events
             WHERE eve_MAC = d.devMac AND eve_DateTime >= {period_date_sql}
               AND eve_EventType = 'Device Down') AS devDownAlerts,

            (SELECT CAST(MAX(0, SUM(
                julianday(IFNULL(ses_DateTimeDisconnection,'{now}')) -
                julianday(CASE WHEN ses_DateTimeConnection < {period_date_sql}
                               THEN {period_date_sql} ELSE ses_DateTimeConnection END)
            ) * 24) AS INT)
             FROM Sessions
             WHERE ses_MAC = d.devMac
               AND ses_DateTimeConnection IS NOT NULL
               AND (ses_DateTimeDisconnection IS NOT NULL OR ses_StillConnected = 1)
               AND (ses_DateTimeConnection >= {period_date_sql}
                    OR ses_DateTimeDisconnection >= {period_date_sql} OR ses_StillConnected = 1)
            ) AS devPresenceHours

        FROM Devices d
        WHERE d.devMac = ? OR CAST(d.rowid AS TEXT) = ?
        """

        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute(sql, (mac, mac))
        row = cur.fetchone()

        if not row:
            conn.close()
            return None

        device_data = row_to_json(list(row.keys()), row)
        device_data["devFirstConnection"] = device_data["devFirstConnection"]
        device_data["devLastConnection"] = device_data["devLastConnection"]
        device_data["devIsRandomMAC"] = is_random_mac(device_data["devMac"])

        # Fetch children
        cur.execute(
            "SELECT * FROM Devices WHERE LOWER(devParentMAC) = LOWER(?) ORDER BY devPresentLastScan DESC",
            (device_data["devMac"],),
        )
        children_rows = cur.fetchall()
        children = [row_to_json(list(r.keys()), r) for r in children_rows]
        children_nics = [c for c in children if c.get("devParentRelType") == "nic"]

        device_data["devChildrenDynamic"] = children
        device_data["devChildrenNicsDynamic"] = children_nics

        conn.close()
        return device_data

    def setDeviceData(self, mac, data):
        """Update or create a device."""
        normalized_mac = normalize_mac(mac)
        normalized_parent_mac = normalize_mac(data.get("devParentMAC") or "")

        if normalized_mac == normalized_parent_mac:
            return {
                "success": False,
                "error": "Can't set current node as the node parent."
            }

        fields_updated_by_set_device_data = {
            "devName",
            "devOwner",
            "devType",
            "devVendor",
            "devIcon",
            "devFavorite",
            "devGroup",
            "devLocation",
            "devComments",
            "devParentMAC",
            "devParentPort",
            "devSSID",
            "devSite",
            "devStaticIP",
            "devScan",
            "devAlertEvents",
            "devAlertDown",
            "devParentRelType",
            "devReqNicsOnline",
            "devSkipRepeated",
            "devIsNew",
            "devIsArchived",
            "devCustomProps",
            "devForceStatus",
            "devVlan"
        }

        # Only mark USER for tracked fields that this method actually updates.
        tracked_update_fields = set(FIELD_SOURCE_MAP.keys()) & fields_updated_by_set_device_data
        tracked_update_fields.discard("devMac")

        locked_fields = set()
        pre_update_tracked_values = {}
        if not data.get("createNew", False):
            conn_preview = get_temp_db_connection()
            try:
                locked_fields, overrides = get_locked_field_overrides(
                    normalized_mac,
                    data,
                    conn_preview,
                )
                if overrides:
                    data.update(overrides)

                # Capture pre-update values for tracked fields so we can mark USER only
                # when the user actually changes the value.
                tracked_fields_in_payload = [
                    k for k in data.keys() if k in tracked_update_fields
                ]
                if tracked_fields_in_payload:
                    select_clause = ", ".join(tracked_fields_in_payload)
                    cur_preview = conn_preview.cursor()
                    cur_preview.execute(
                        f"SELECT {select_clause} FROM Devices WHERE devMac=?",
                        (normalized_mac,),
                    )
                    row = cur_preview.fetchone()
                    if row:
                        pre_update_tracked_values = row_to_json(list(row.keys()), row)
            finally:
                conn_preview.close()

        conn = None
        try:
            if data.get("createNew", False):
                sql = """
                INSERT INTO Devices (
                    devMac, devName, devOwner, devType, devVendor, devIcon,
                    devFavorite, devGroup, devLocation, devComments,
                    devParentMAC, devParentPort, devSSID, devSite,
                    devStaticIP, devScan, devAlertEvents, devAlertDown,
                    devParentRelType, devReqNicsOnline, devSkipRepeated,
                    devIsNew, devIsArchived, devLastConnection,
                    devFirstConnection, devLastIP, devGUID, devCustomProps,
                    devSourcePlugin, devForceStatus, devVlan
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                values = (
                    normalized_mac,
                    data.get("devName") or "",
                    data.get("devOwner") or "",
                    data.get("devType") or "",
                    data.get("devVendor") or "",
                    data.get("devIcon") or "",
                    data.get("devFavorite") or 0,
                    data.get("devGroup") or "",
                    data.get("devLocation") or "",
                    data.get("devComments") or "",
                    normalized_parent_mac,
                    data.get("devParentPort") or "",
                    data.get("devSSID") or "",
                    data.get("devSite") or "",
                    data.get("devStaticIP") or 0,
                    data.get("devScan") or 0,
                    data.get("devAlertEvents") or 0,
                    data.get("devAlertDown") or 0,
                    data.get("devParentRelType") or "default",
                    data.get("devReqNicsOnline") or 0,
                    data.get("devSkipRepeated") or 0,
                    data.get("devIsNew") or 0,
                    data.get("devIsArchived") or 0,
                    data.get("devLastConnection") or timeNowUTC(),
                    data.get("devFirstConnection") or timeNowUTC(),
                    data.get("devLastIP") or "",
                    data.get("devGUID") or "",
                    data.get("devCustomProps") or "",
                    data.get("devSourcePlugin") or "DUMMY",
                    data.get("devForceStatus") or "dont_force",
                    data.get("devVlan") or "",
                )

            else:
                sql = """
                UPDATE Devices SET
                    devName=?, devOwner=?, devType=?, devVendor=?, devIcon=?,
                    devFavorite=?, devGroup=?, devLocation=?, devComments=?,
                    devParentMAC=?, devParentPort=?, devSSID=?, devSite=?,
                    devStaticIP=?, devScan=?, devAlertEvents=?, devAlertDown=?,
                    devParentRelType=?, devReqNicsOnline=?, devSkipRepeated=?,
                    devIsNew=?, devIsArchived=?, devCustomProps=?, devForceStatus=?, devVlan=?
                WHERE devMac=?
                """
                values = (
                    data.get("devName") or "",
                    data.get("devOwner") or "",
                    data.get("devType") or "",
                    data.get("devVendor") or "",
                    data.get("devIcon") or "",
                    data.get("devFavorite") or 0,
                    data.get("devGroup") or "",
                    data.get("devLocation") or "",
                    data.get("devComments") or "",
                    normalized_parent_mac,
                    data.get("devParentPort") or "",
                    data.get("devSSID") or "",
                    data.get("devSite") or "",
                    data.get("devStaticIP") or 0,
                    data.get("devScan") or 0,
                    data.get("devAlertEvents") or 0,
                    data.get("devAlertDown") or 0,
                    data.get("devParentRelType") or "default",
                    data.get("devReqNicsOnline") or 0,
                    data.get("devSkipRepeated") or 0,
                    data.get("devIsNew") or 0,
                    data.get("devIsArchived") or 0,
                    data.get("devCustomProps") or "",
                    data.get("devForceStatus") or "dont_force",
                    data.get("devVlan") or "",
                    normalized_mac,
                )

            conn = get_temp_db_connection()
            cur = conn.cursor()
            cur.execute(sql, values)

            if data.get("createNew", False):
                # Initialize source-tracking fields on device creation.
                # We always mark devMacSource as NEWDEV, and mark other tracked fields
                # as NEWDEV only if the create payload provides a non-empty value.
                initial_sources = {FIELD_SOURCE_MAP["devMac"]: "NEWDEV"}
                for field_name, source_field in FIELD_SOURCE_MAP.items():
                    if field_name == "devMac":
                        continue
                    field_value = data.get(field_name)
                    if field_value is None:
                        continue
                    if isinstance(field_value, str) and not field_value.strip():
                        continue
                    initial_sources[source_field] = "NEWDEV"

                if initial_sources:
                    # Apply source updates in a single statement for the newly inserted row.
                    set_clause = ", ".join([f"{col}=?" for col in initial_sources.keys()])
                    source_values = list(initial_sources.values())
                    source_values.append(normalized_mac)
                    source_sql = f"UPDATE Devices SET {set_clause} WHERE devMac = ?"
                    cur.execute(source_sql, source_values)

            # Enforce source tracking on user updates
            # User-updated fields should have their *Source set to "USER"
            def _normalize_tracked_value(value):
                if value is None:
                    return ""
                if isinstance(value, str):
                    return value.strip()
                return str(value)

            user_updated_fields = {}
            if not data.get("createNew", False):
                for field_name in tracked_update_fields:
                    if field_name in locked_fields:
                        continue
                    if field_name not in data:
                        continue

                    if field_name == "devParentMAC":
                        new_value = normalized_parent_mac
                    else:
                        new_value = data.get(field_name)

                    old_value = pre_update_tracked_values.get(field_name)
                    if _normalize_tracked_value(old_value) != _normalize_tracked_value(new_value):
                        user_updated_fields[field_name] = new_value

            if user_updated_fields and not data.get("createNew", False):
                try:
                    enforce_source_on_user_update(normalized_mac, user_updated_fields, conn)
                except Exception as e:
                    mylog("none", [f"[DeviceInstance] Failed to enforce source tracking: {e}"])
                    conn.rollback()
                    conn.close()
                    return {"success": False, "error": f"Source tracking failed: {e}"}

            # Commit all changes atomically after all operations succeed
            conn.commit()
            conn.close()

            mylog("debug", f"[DeviceInstance] setDeviceData SQL: {sql.strip()}")
            mylog("debug", f"[DeviceInstance] setDeviceData VALUES:{values}")

            return {"success": True}
        except Exception as e:
            if conn:
                conn.rollback()

            # Optional: your existing logger
            mylog("none", f"[DeviceInstance] setDeviceData({mac}) failed: {e}")

            return {
                "success": False,
                "error": str(e)
            }

        finally:
            if conn:
                conn.close()

    def deleteDeviceByMAC(self, mac):
        """Delete a device by MAC."""
        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM Devices WHERE devMac=?", (mac,))
        conn.commit()
        conn.close()
        return {"success": True}

    def deleteDeviceEvents(self, mac):
        """Delete all events for a device."""
        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM Events WHERE eve_MAC=?", (mac,))
        conn.commit()
        conn.close()
        return {"success": True}

    def resetDeviceProps(self, mac):
        """Reset device custom properties to default."""
        default_props = get_setting_value("NEWDEV_devCustomProps")
        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE Devices SET devCustomProps=? WHERE devMac=?",
            (default_props, mac),
        )
        conn.commit()
        conn.close()
        return {"success": True}

    def updateDeviceColumn(self, mac, column_name, column_value):
        """Update a specific column for a given device."""
        conn = get_temp_db_connection()
        cur = conn.cursor()

        # Build safe SQL with column name
        sql = f"UPDATE Devices SET {column_name}=? WHERE devMac=?"
        cur.execute(sql, (column_value, mac))
        conn.commit()

        if cur.rowcount > 0:
            result = {"success": True}
        else:
            result = {"success": False, "error": "Device not found"}

        conn.close()
        return result

    def lockDeviceField(self, mac, field_name):
        """Lock a device field so it won't be overwritten by plugins."""
        if field_name not in FIELD_SOURCE_MAP:
            return {"success": False, "error": f"Field {field_name} does not support locking"}

        mac_normalized = normalize_mac(mac)
        conn = get_temp_db_connection()
        try:
            result = lock_field(mac_normalized, field_name, conn)
            # Include field name in response
            result["fieldName"] = field_name
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "fieldName": field_name}
        finally:
            conn.close()

    def unlockDeviceField(self, mac, field_name):
        """Unlock a device field so plugins can overwrite it again."""
        if field_name not in FIELD_SOURCE_MAP:
            return {"success": False, "error": f"Field {field_name} does not support unlocking"}

        mac_normalized = normalize_mac(mac)
        conn = get_temp_db_connection()
        try:
            result = unlock_field(mac_normalized, field_name, conn)
            # Include field name in response
            result["fieldName"] = field_name
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "fieldName": field_name}
        finally:
            conn.close()

    def unlockFields(self, mac=None, fields=None, clear_all=False):
        """
        Wrapper to unlock one field, multiple fields, or all fields of a device or all devices.

        Args:
            mac: Optional MAC address of a single device (string) or multiple devices (list of strings).
                If None, the operation applies to all devices.
            fields: Optional list of field names to unlock. If None, all tracked fields are unlocked.
            clear_all: If True, clear all values in the corresponding source fields.
                    If False, only clear fields whose source is 'LOCKED' or 'USER'.

        Returns:
            dict: {
                "success": bool,
                "error": str|None,
                "devicesAffected": int,
                "fieldsAffected": list
            }
        """
        # If no fields specified, unlock all tracked fields
        if fields is None:
            fields_to_unlock = list(FIELD_SOURCE_MAP.keys())
        else:
            # Validate fields
            invalid_fields = [f for f in fields if f not in FIELD_SOURCE_MAP]
            if invalid_fields:
                return {
                    "success": False,
                    "error": f"Invalid fields: {', '.join(invalid_fields)}",
                    "devicesAffected": 0,
                    "fieldsAffected": []
                }
            fields_to_unlock = fields

        conn = get_temp_db_connection()
        result = unlock_fields(conn, mac=mac, fields=fields_to_unlock, clear_all=clear_all)
        conn.close()

        return result

    def copyDevice(self, mac_from, mac_to):
        """Copy a device entry from one MAC to another."""
        conn = get_temp_db_connection()
        cur = conn.cursor()

        try:
            # Drop temporary table if exists
            cur.execute("DROP TABLE IF EXISTS temp_devices")

            # Create temporary table with source device
            cur.execute(
                "CREATE TABLE temp_devices AS SELECT * FROM Devices WHERE devMac = ?",
                (mac_from,),
            )

            # Update temporary table to target MAC
            cur.execute("UPDATE temp_devices SET devMac = ?", (mac_to,))

            # Delete previous entry with target MAC
            cur.execute("DELETE FROM Devices WHERE devMac = ?", (mac_to,))

            # Insert new entry from temporary table
            cur.execute(
                "INSERT INTO Devices SELECT * FROM temp_devices WHERE devMac = ?", (mac_to,)
            )

            # Drop temporary table
            cur.execute("DROP TABLE temp_devices")

            conn.commit()
            return {
                "success": True,
                "message": f"Device copied from {mac_from} to {mac_to}",
            }

        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}

        finally:
            conn.close()
