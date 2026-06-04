#!/usr/bin/env python

import os
import sqlite3
import sys
from flask import jsonify

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from database import get_temp_db_connection  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, format_ip_long  # noqa: E402 [flake8 lint suppression]
from db.db_helper import get_date_from_period  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC, format_date_iso, format_event_date, format_date_diff, format_date   # noqa: E402 [flake8 lint suppression]


# --------------------------
# Sessions Endpoints Functions
# --------------------------
# -------------------------------------------------------------------------------------------
def create_session(
    mac,
    ip,
    start_time,
    end_time=None,
    event_type_conn="Connected",
    event_type_disc="Disconnected",
):
    """Insert a new session into Sessions table"""
    conn = get_temp_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO Sessions (sesMac, sesIp, sesDateTimeConnection, sesDateTimeDisconnection,
                              sesEventTypeConnection, sesEventTypeDisconnection)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (mac, ip, start_time, end_time, event_type_conn, event_type_disc),
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Session created for MAC {mac}"})


# -------------------------------------------------------------------------------------------
def delete_session(mac):
    """Delete all sessions for a given MAC"""
    conn = get_temp_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM Sessions WHERE sesMac = ?", (mac,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Deleted sessions for MAC {mac}"})


# -------------------------------------------------------------------------------------------
def get_sessions(mac=None, start_date=None, end_date=None):
    """Retrieve sessions optionally filtered by MAC and date range"""
    conn = get_temp_db_connection()
    cur = conn.cursor()

    sql = "SELECT * FROM Sessions WHERE 1=1"
    params = []

    if mac:
        sql += " AND sesMac = ?"
        params.append(mac)
    if start_date:
        sql += " AND sesDateTimeConnection >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND sesDateTimeDisconnection <= ?"
        params.append(end_date)

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    conn.close()

    # Convert rows to list of dicts
    table_data = [dict(r) for r in rows]

    return jsonify({"success": True, "sessions": table_data})


def get_sessions_calendar(start_date, end_date, mac):
    """
    Fetch sessions between a start and end date for calendar display.
    Returns FullCalendar-compatible JSON.
    """

    if not start_date or not end_date:
        return jsonify({"success": False, "error": "Missing start or end date"}), 400

    # Normalize MAC (empty string → NULL)
    mac = mac or None

    conn = get_temp_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
        SELECT
            SES1.sesMac,
            SES1.sesEventTypeConnection,
            SES1.sesDateTimeConnection,
            SES1.sesEventTypeDisconnection,
            SES1.sesDateTimeDisconnection,
            SES1.sesIp,
            SES1.sesAdditionalInfo,
            SES1.sesStillConnected,

            CASE
              WHEN SES1.sesEventTypeConnection = '<missing event>' THEN
                IFNULL(
                  (
                    SELECT MAX(SES2.sesDateTimeDisconnection)
                    FROM Sessions AS SES2
                    WHERE SES2.sesMac = SES1.sesMac
                      AND SES2.sesDateTimeDisconnection < SES1.sesDateTimeDisconnection
                      AND SES2.sesDateTimeDisconnection BETWEEN Date(?) AND Date(?)
                  ),
                  DATETIME(SES1.sesDateTimeDisconnection, '-1 hour')
                )
              ELSE SES1.sesDateTimeConnection
            END AS sesDateTimeConnectionCorrected,

            CASE
              WHEN SES1.sesEventTypeDisconnection = '<missing event>' THEN
                (
                  SELECT MIN(SES2.sesDateTimeConnection)
                  FROM Sessions AS SES2
                  WHERE SES2.sesMac = SES1.sesMac
                    AND SES2.sesDateTimeConnection > SES1.sesDateTimeConnection
                    AND SES2.sesDateTimeConnection BETWEEN Date(?) AND Date(?)
                )
              ELSE SES1.sesDateTimeDisconnection
            END AS sesDateTimeDisconnectionCorrected

        FROM Sessions AS SES1
        WHERE (
              (SES1.sesDateTimeConnection BETWEEN Date(?) AND Date(?))
           OR (SES1.sesDateTimeDisconnection BETWEEN Date(?) AND Date(?))
           OR SES1.sesStillConnected = 1
        )
        AND (? IS NULL OR SES1.sesMac = ?)
    """

    cur.execute(
        sql,
        (
            start_date, end_date,
            start_date, end_date,
            start_date, end_date,
            start_date, end_date,
            mac, mac,
        ),
    )

    rows = cur.fetchall()
    conn.close()

    now_iso = timeNowUTC()

    events = []
    for row in rows:
        row = dict(row)

        # Color logic (unchanged from PHP)
        if (
            row["sesEventTypeConnection"] == "<missing event>" or row["sesEventTypeDisconnection"] == "<missing event>"
        ):
            color = "#f39c12"
        elif row["sesStillConnected"] == 1:
            color = "#00a659"
        else:
            color = "#0073b7"

        # --- IMPORTANT FIX ---
        # FullCalendar v3 CANNOT handle end = null
        end_dt = row["sesDateTimeDisconnectionCorrected"]
        if not end_dt and row["sesStillConnected"] == 1:
            end_dt = now_iso

        tooltip = (
            f"Connection: {format_event_date(row['sesDateTimeConnection'], row['sesEventTypeConnection'])}\n"
            f"Disconnection: {format_event_date(row['sesDateTimeDisconnection'], row['sesEventTypeDisconnection'])}\n"
            f"IP: {row['sesIp']}"
        )

        events.append(
            {
                "resourceId": row["sesMac"],
                "title": "",
                "start": format_date_iso(row["sesDateTimeConnectionCorrected"]),
                "end": format_date_iso(end_dt),
                "color": color,
                "tooltip": tooltip,
                "className": "no-border",
            }
        )

    return jsonify({"success": True, "sessions": events})


def get_device_sessions(mac, period):
    """
    Fetch device sessions for a given MAC address and period.
    """
    period_date = get_date_from_period(period)

    conn = get_temp_db_connection()
    cur = conn.cursor()

    sql = f"""
        SELECT
            IFNULL(sesDateTimeConnection, sesDateTimeDisconnection) AS sesDateTimeOrder,
            sesEventTypeConnection,
            sesDateTimeConnection,
            sesEventTypeDisconnection,
            sesDateTimeDisconnection,
            sesStillConnected,
            sesIp,
            sesAdditionalInfo
        FROM Sessions
        WHERE sesMac = ?
          AND (
              sesDateTimeConnection >= {period_date}
              OR sesDateTimeDisconnection >= {period_date}
              OR sesStillConnected = 1
          )
    """

    cur.execute(sql, (mac,))
    rows = cur.fetchall()
    conn.close()
    tz_name = get_setting_value("TIMEZONE") or "UTC"

    table_data = {"data": []}

    for row in rows:
        # Connection DateTime
        if row["sesEventTypeConnection"] == "<missing event>":
            ini = row["sesEventTypeConnection"]
        else:
            ini = format_date(row["sesDateTimeConnection"])

        # Disconnection DateTime
        if row["sesStillConnected"]:
            end = "..."
        elif row["sesEventTypeDisconnection"] == "<missing event>":
            end = row["sesEventTypeDisconnection"]
        else:
            end = format_date(row["sesDateTimeDisconnection"])

        # Duration
        if row["sesEventTypeConnection"] in ("<missing event>", None) or row[
            "sesEventTypeDisconnection"
        ] in ("<missing event>", None):
            dur = "..."
        elif row["sesStillConnected"]:
            dur = format_date_diff(row["sesDateTimeConnection"], None, tz_name)["text"]
        else:
            dur = format_date_diff(row["sesDateTimeConnection"], row["sesDateTimeDisconnection"], tz_name)["text"]

        # Additional Info
        info = row["sesAdditionalInfo"]
        if row["sesEventTypeConnection"] == "New Device":
            info = f"{row['sesEventTypeConnection']}:   {info}"

        # Push row data
        table_data["data"].append(
            {
                "sesMac": mac,
                "sesDateTimeOrder": row["sesDateTimeOrder"],
                "sesConnection": ini,
                "sesDisconnection": end,
                "sesDuration": dur,
                "sesIp": row["sesIp"],
                "sesInfo": info,
            }
        )

    # Control no rows
    if not table_data["data"]:
        table_data["data"] = []

    sessions = table_data["data"]

    return jsonify({"success": True, "sessions": sessions})


def get_session_events(event_type, period_date, page=1, limit=100, search=None, sort_col=0, sort_dir="desc"):
    """
    Fetch events or sessions based on type and period.
    Supports server-side pagination (page/limit), free-text search, and sorting.
    Returns { data, total, recordsFiltered } so callers can drive DataTables serverSide mode.
    """
    _MAX_LIMIT = 1000
    limit = min(max(1, int(limit)), _MAX_LIMIT)
    page  = max(1, int(page))

    conn = get_temp_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tz_name = get_setting_value("TIMEZONE") or "UTC"

    # Base SQLs
    sql_events = f"""
        SELECT
            eveDateTime AS eveDateTimeOrder,
            devName,
            devOwner,
            eveDateTime,
            eveEventType,
            NULL,
            NULL,
            NULL,
            NULL,
            eveIp,
            NULL,
            eveAdditionalInfo,
            NULL,
            devMac,
            evePendingAlertEmail
        FROM Events_Devices
        WHERE eveDateTime >= {period_date}
    """

    sql_sessions = """
        SELECT
            IFNULL(sesDateTimeConnection, sesDateTimeDisconnection) AS sesDateTimeOrder,
            devName,
            devOwner,
            NULL,
            NULL,
            sesDateTimeConnection,
            sesDateTimeDisconnection,
            NULL,
            NULL,
            sesIp,
            NULL,
            sesAdditionalInfo,
            sesStillConnected,
            devMac,
            0 AS sesPendingAlertEmail
        FROM Sessions_Devices
    """

    # Build SQL based on type
    if event_type == "all":
        sql = sql_events
    elif event_type == "sessions":
        sql = (
            sql_sessions + f"""
            WHERE (
                sesDateTimeConnection >= {period_date}
                OR sesDateTimeDisconnection >= {period_date}
                OR sesStillConnected = 1
            )
        """
        )
    elif event_type == "missing":
        sql = (
            sql_sessions + f"""
            WHERE (
                (sesDateTimeConnection IS NULL AND sesDateTimeDisconnection >= {period_date})
                OR (sesDateTimeDisconnection IS NULL AND sesStillConnected = 0 AND sesDateTimeConnection >= {period_date})
            )
        """
        )
    elif event_type == "voided":
        sql = sql_events + ' AND eveEventType LIKE "VOIDED%"'
    elif event_type == "new":
        sql = sql_events + ' AND eveEventType = "New Device"'
    elif event_type == "down":
        sql = sql_events + ' AND eveEventType = "Device Down"'
    else:
        sql = sql_events + " AND 1=0"

    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()

    table_data = {"data": []}

    for row in rows:
        row = list(row)  # make mutable

        if event_type in ("sessions", "missing"):
            # Duration
            if row[5] and row[6]:
                delta = format_date_diff(row[5], row[6], tz_name)
                row[7] = delta["text"]
                row[8] = int(delta["total_minutes"] * 60)  # seconds
            elif row[12] == 1:
                delta = format_date_diff(row[5], None, tz_name)
                row[7] = delta["text"]
                row[8] = int(delta["total_minutes"] * 60)  # seconds
            else:
                row[7] = "..."
                row[8] = 0

            # Connection
            row[5] = format_date(row[5]) if row[5] else "<missing event>"

            # Disconnection
            if row[6]:
                row[6] = format_date(row[6])
            elif row[12] == 0:
                row[6] = "<missing event>"
            else:
                row[6] = "..."

        else:
            # Event Date
            row[3] = format_date(row[3])

        # IP Order
        row[10] = format_ip_long(row[9])

        table_data["data"].append(row)

    all_rows = table_data["data"]

    # --- Sorting ---
    num_cols = len(all_rows[0]) if all_rows else 0
    if 0 <= sort_col < num_cols:
        reverse = sort_dir.lower() == "desc"
        all_rows.sort(
            key=lambda r: (r[sort_col] is None, r[sort_col] if r[sort_col] is not None else ""),
            reverse=reverse,
        )

    total = len(all_rows)

    # --- Free-text search (applied after formatting so display values are searchable) ---
    if search:
        search_lower = search.strip().lower()

        def _row_matches(r):
            return any(search_lower in str(v).lower() for v in r if v is not None)
        all_rows = [r for r in all_rows if _row_matches(r)]
    records_filtered = len(all_rows)

    # --- Pagination ---
    offset = (page - 1) * limit
    paged_rows = all_rows[offset: offset + limit]

    return jsonify({"data": paged_rows, "total": total, "recordsFiltered": records_filtered})
