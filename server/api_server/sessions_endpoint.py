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
        INSERT INTO Sessions (ses_MAC, ses_IP, ses_DateTimeConnection, ses_DateTimeDisconnection,
                              ses_EventTypeConnection, ses_EventTypeDisconnection)
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

    cur.execute("DELETE FROM Sessions WHERE ses_MAC = ?", (mac,))
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
        sql += " AND ses_MAC = ?"
        params.append(mac)
    if start_date:
        sql += " AND ses_DateTimeConnection >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND ses_DateTimeDisconnection <= ?"
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
            SES1.ses_MAC,
            SES1.ses_EventTypeConnection,
            SES1.ses_DateTimeConnection,
            SES1.ses_EventTypeDisconnection,
            SES1.ses_DateTimeDisconnection,
            SES1.ses_IP,
            SES1.ses_AdditionalInfo,
            SES1.ses_StillConnected,

            CASE
              WHEN SES1.ses_EventTypeConnection = '<missing event>' THEN
                IFNULL(
                  (
                    SELECT MAX(SES2.ses_DateTimeDisconnection)
                    FROM Sessions AS SES2
                    WHERE SES2.ses_MAC = SES1.ses_MAC
                      AND SES2.ses_DateTimeDisconnection < SES1.ses_DateTimeDisconnection
                      AND SES2.ses_DateTimeDisconnection BETWEEN Date(?) AND Date(?)
                  ),
                  DATETIME(SES1.ses_DateTimeDisconnection, '-1 hour')
                )
              ELSE SES1.ses_DateTimeConnection
            END AS ses_DateTimeConnectionCorrected,

            CASE
              WHEN SES1.ses_EventTypeDisconnection = '<missing event>' THEN
                (
                  SELECT MIN(SES2.ses_DateTimeConnection)
                  FROM Sessions AS SES2
                  WHERE SES2.ses_MAC = SES1.ses_MAC
                    AND SES2.ses_DateTimeConnection > SES1.ses_DateTimeConnection
                    AND SES2.ses_DateTimeConnection BETWEEN Date(?) AND Date(?)
                )
              ELSE SES1.ses_DateTimeDisconnection
            END AS ses_DateTimeDisconnectionCorrected

        FROM Sessions AS SES1
        WHERE (
              (SES1.ses_DateTimeConnection BETWEEN Date(?) AND Date(?))
           OR (SES1.ses_DateTimeDisconnection BETWEEN Date(?) AND Date(?))
           OR SES1.ses_StillConnected = 1
        )
        AND (? IS NULL OR SES1.ses_MAC = ?)
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
            row["ses_EventTypeConnection"] == "<missing event>" or row["ses_EventTypeDisconnection"] == "<missing event>"
        ):
            color = "#f39c12"
        elif row["ses_StillConnected"] == 1:
            color = "#00a659"
        else:
            color = "#0073b7"

        # --- IMPORTANT FIX ---
        # FullCalendar v3 CANNOT handle end = null
        end_dt = row["ses_DateTimeDisconnectionCorrected"]
        if not end_dt and row["ses_StillConnected"] == 1:
            end_dt = now_iso

        tooltip = (
            f"Connection: {format_event_date(row['ses_DateTimeConnection'], row['ses_EventTypeConnection'])}\n"
            f"Disconnection: {format_event_date(row['ses_DateTimeDisconnection'], row['ses_EventTypeDisconnection'])}\n"
            f"IP: {row['ses_IP']}"
        )

        events.append(
            {
                "resourceId": row["ses_MAC"],
                "title": "",
                "start": format_date_iso(row["ses_DateTimeConnectionCorrected"]),
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
            IFNULL(ses_DateTimeConnection, ses_DateTimeDisconnection) AS ses_DateTimeOrder,
            ses_EventTypeConnection,
            ses_DateTimeConnection,
            ses_EventTypeDisconnection,
            ses_DateTimeDisconnection,
            ses_StillConnected,
            ses_IP,
            ses_AdditionalInfo
        FROM Sessions
        WHERE ses_MAC = ?
          AND (
              ses_DateTimeConnection >= {period_date}
              OR ses_DateTimeDisconnection >= {period_date}
              OR ses_StillConnected = 1
          )
    """

    cur.execute(sql, (mac,))
    rows = cur.fetchall()
    conn.close()
    tz_name = get_setting_value("TIMEZONE") or "UTC"

    table_data = {"data": []}

    for row in rows:
        # Connection DateTime
        if row["ses_EventTypeConnection"] == "<missing event>":
            ini = row["ses_EventTypeConnection"]
        else:
            ini = format_date(row["ses_DateTimeConnection"])

        # Disconnection DateTime
        if row["ses_StillConnected"]:
            end = "..."
        elif row["ses_EventTypeDisconnection"] == "<missing event>":
            end = row["ses_EventTypeDisconnection"]
        else:
            end = format_date(row["ses_DateTimeDisconnection"])

        # Duration
        if row["ses_EventTypeConnection"] in ("<missing event>", None) or row[
            "ses_EventTypeDisconnection"
        ] in ("<missing event>", None):
            dur = "..."
        elif row["ses_StillConnected"]:
            dur = format_date_diff(row["ses_DateTimeConnection"], None, tz_name)["text"]
        else:
            dur = format_date_diff(row["ses_DateTimeConnection"], row["ses_DateTimeDisconnection"], tz_name)["text"]

        # Additional Info
        info = row["ses_AdditionalInfo"]
        if row["ses_EventTypeConnection"] == "New Device":
            info = f"{row['ses_EventTypeConnection']}:   {info}"

        # Push row data
        table_data["data"].append(
            {
                "ses_MAC": mac,
                "ses_DateTimeOrder": row["ses_DateTimeOrder"],
                "ses_Connection": ini,
                "ses_Disconnection": end,
                "ses_Duration": dur,
                "ses_IP": row["ses_IP"],
                "ses_Info": info,
            }
        )

    # Control no rows
    if not table_data["data"]:
        table_data["data"] = []

    sessions = table_data["data"]

    return jsonify({"success": True, "sessions": sessions})


def get_session_events(event_type, period_date):
    """
    Fetch events or sessions based on type and period.
    """
    conn = get_temp_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tz_name = get_setting_value("TIMEZONE") or "UTC"

    # Base SQLs
    sql_events = f"""
        SELECT
            eve_DateTime AS eve_DateTimeOrder,
            devName,
            devOwner,
            eve_DateTime,
            eve_EventType,
            NULL,
            NULL,
            NULL,
            NULL,
            eve_IP,
            NULL,
            eve_AdditionalInfo,
            NULL,
            devMac,
            eve_PendingAlertEmail
        FROM Events_Devices
        WHERE eve_DateTime >= {period_date}
    """

    sql_sessions = """
        SELECT
            IFNULL(ses_DateTimeConnection, ses_DateTimeDisconnection) AS ses_DateTimeOrder,
            devName,
            devOwner,
            NULL,
            NULL,
            ses_DateTimeConnection,
            ses_DateTimeDisconnection,
            NULL,
            NULL,
            ses_IP,
            NULL,
            ses_AdditionalInfo,
            ses_StillConnected,
            devMac,
            0 AS ses_PendingAlertEmail
        FROM Sessions_Devices
    """

    # Build SQL based on type
    if event_type == "all":
        sql = sql_events
    elif event_type == "sessions":
        sql = (
            sql_sessions + f"""
            WHERE (
                ses_DateTimeConnection >= {period_date}
                OR ses_DateTimeDisconnection >= {period_date}
                OR ses_StillConnected = 1
            )
        """
        )
    elif event_type == "missing":
        sql = (
            sql_sessions + f"""
            WHERE (
                (ses_DateTimeConnection IS NULL AND ses_DateTimeDisconnection >= {period_date})
                OR (ses_DateTimeDisconnection IS NULL AND ses_StillConnected = 0 AND ses_DateTimeConnection >= {period_date})
            )
        """
        )
    elif event_type == "voided":
        sql = sql_events + ' AND eve_EventType LIKE "VOIDED%"'
    elif event_type == "new":
        sql = sql_events + ' AND eve_EventType = "New Device"'
    elif event_type == "down":
        sql = sql_events + ' AND eve_EventType = "Device Down"'
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

    return jsonify(table_data)
