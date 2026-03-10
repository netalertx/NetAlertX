# ---------------------------------------------------------------------------------#
#  NetAlertX                                                                       #
#  Open Source Network Guard / WIFI & LAN intrusion detector                      #
#                                                                                 #
#  reporting.py - NetAlertX Back module. Template to email reporting in HTML format #
# ---------------------------------------------------------------------------------#
#    Puche      2021        pi.alert.application@gmail.com   GNU GPLv3            #
#    jokob-sk   2022        jokob.sk@gmail.com               GNU GPLv3            #
#    leiweibau  2022        https://github.com/leiweibau     GNU GPLv3            #
#    cvc90      2023        https://github.com/cvc90         GNU GPLv3            #
# ---------------------------------------------------------------------------------#

import os
import json
import sys
from zoneinfo import ZoneInfo

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server"])

from helper import (  # noqa: E402 [flake8 lint suppression]
    get_setting_value,
)
from logger import mylog  # noqa: E402 [flake8 lint suppression]
from db.sql_safe_builder import create_safe_condition_builder  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import format_date_iso  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]

# ===============================================================================
# Timezone conversion
# ===============================================================================

DATETIME_FIELDS = {
    "new_devices": ["Datetime"],
    "down_devices": ["eve_DateTime"],
    "down_reconnected": ["eve_DateTime"],
    "events": ["Datetime"],
    "plugins": ["DateTimeChanged"],
}


def get_datetime_fields_from_columns(column_names):
    return [
        col for col in column_names
        if "date" in col.lower() or "time" in col.lower()
    ]


def apply_timezone_to_json(json_obj, section=None):
    data = json_obj.json["data"]
    columns = json_obj.columnNames

    fields = DATETIME_FIELDS.get(section) or get_datetime_fields_from_columns(columns)

    return apply_timezone(data, fields)


def apply_timezone(data, fields):
    """
    Convert UTC datetime fields in a list of dicts to the configured timezone.

    Args:
        data (list[dict]): Rows returned from DB
        fields (list[str]): Field names to convert

    Returns:
        list[dict]: Modified data with timezone-aware ISO strings
    """
    if not data or not fields:
        return data

    # Determine local timezone
    tz = conf.tz
    if isinstance(tz, str):
        tz = ZoneInfo(tz)

    for row in data:
        if not isinstance(row, dict):
            continue

        for field in fields:
            value = row.get(field)
            if not value:
                continue

            try:
                # Convert DB UTC string → local timezone ISO
                # format_date_iso already assumes UTC if naive
                row[field] = format_date_iso(value)
            except Exception:
                # Never crash, leave original value if conversion fails
                continue

    return data


# ===============================================================================
# REPORTING
# ===============================================================================
def get_notifications(db):
    """
    Fetch notifications for all configured sections.

    Args:
        db: Database object with `.sql` for executing queries.

    Returns:
        dict: JSON-ready dict with data and metadata for each section.
    """
    sql = db.sql

    mylog("verbose", "[Notification] Check if something to report")

    # Disable events where reporting is disabled
    sql.execute("""
        UPDATE Events SET eve_PendingAlertEmail = 0
        WHERE eve_PendingAlertEmail = 1
          AND eve_EventType NOT IN ('Device Down', 'Down Reconnected', 'New Device')
          AND eve_MAC IN (SELECT devMac FROM Devices WHERE devAlertEvents = 0)
    """)
    sql.execute("""
        UPDATE Events SET eve_PendingAlertEmail = 0
        WHERE eve_PendingAlertEmail = 1
          AND eve_EventType IN ('Device Down', 'Down Reconnected')
          AND eve_MAC IN (SELECT devMac FROM Devices WHERE devAlertDown = 0)
    """)

    alert_down_minutes = int(get_setting_value("NTFPRCS_alert_down_time") or 0)

    sections = get_setting_value("NTFPRCS_INCLUDED_SECTIONS") or []
    mylog("verbose", ["[Notification] Included sections: ", sections])

    # -------------------------
    # Helper: condition mapping
    # -------------------------
    def get_section_condition(section):
        """
        Resolve condition setting key with backward compatibility.
        """
        # New format
        key = f"NTFPRCS_{section}_condition"
        value = get_setting_value(key)

        if value:
            return value

        # Legacy keys
        legacy_map = {
            "new_devices": "NTFPRCS_new_dev_condition",
            "events": "NTFPRCS_event_condition",
        }

        legacy_key = legacy_map.get(section)
        if legacy_key:
            return get_setting_value(legacy_key)

        return ""

    # -------------------------
    # SQL templates
    # -------------------------
    sql_templates = {
        "new_devices": """
            SELECT
                eve_MAC as MAC,
                eve_DateTime as Datetime,
                devLastIP as IP,
                eve_EventType as "Event Type",
                devName as "Device name",
                devComments as Comments
            FROM Events_Devices
            WHERE eve_PendingAlertEmail = 1
              AND eve_EventType = 'New Device' {condition}
            ORDER BY eve_DateTime
        """,
        "down_devices": f"""
            SELECT
                devName,
                eve_MAC,
                devVendor,
                eve_IP,
                eve_DateTime,
                eve_EventType
            FROM Events_Devices AS down_events
            WHERE eve_PendingAlertEmail = 1
              AND down_events.eve_EventType = 'Device Down'
              AND eve_DateTime < datetime('now', '-{alert_down_minutes} minutes')
              AND NOT EXISTS (
                  SELECT 1
                  FROM Events AS connected_events
                  WHERE connected_events.eve_MAC = down_events.eve_MAC
                    AND connected_events.eve_EventType = 'Connected'
                    AND connected_events.eve_DateTime > down_events.eve_DateTime
              )
            ORDER BY down_events.eve_DateTime
        """,
        "down_reconnected": """
            SELECT
                devName,
                eve_MAC,
                devVendor,
                eve_IP,
                eve_DateTime,
                eve_EventType
            FROM Events_Devices AS reconnected_devices
            WHERE reconnected_devices.eve_EventType = 'Down Reconnected'
              AND reconnected_devices.eve_PendingAlertEmail = 1
            ORDER BY reconnected_devices.eve_DateTime
        """,
        "events": """
            SELECT
                eve_MAC as MAC,
                eve_DateTime as Datetime,
                devLastIP as IP,
                eve_EventType as "Event Type",
                devName as "Device name",
                devComments as Comments
            FROM Events_Devices
            WHERE eve_PendingAlertEmail = 1
              AND eve_EventType IN ('Connected', 'Down Reconnected', 'Disconnected','IP Changed') {condition}
            ORDER BY eve_DateTime
        """,
        "plugins": """
            SELECT
                Plugin,
                Object_PrimaryId,
                Object_SecondaryId,
                DateTimeChanged,
                Watched_Value1,
                Watched_Value2,
                Watched_Value3,
                Watched_Value4,
                Status
            FROM Plugins_Events
        """
    }

    # Titles for metadata
    section_titles = {
        "new_devices": "🆕 New devices",
        "down_devices": "🔴 Down devices",
        "down_reconnected": "🔁 Reconnected down devices",
        "events": "⚡ Events",
        "plugins": "🔌 Plugins"
    }

    # Sections that support dynamic conditions
    sections_with_conditions = {"new_devices", "events"}

    # Initialize final structure
    final_json = {}
    for section in ["new_devices", "down_devices", "down_reconnected", "events", "plugins"]:
        final_json[section] = []
        final_json[f"{section}_meta"] = {
            "title": section_titles.get(section, section),
            "columnNames": []
        }

    condition_builder = create_safe_condition_builder()

    # -------------------------
    # Main loop
    # -------------------------
    condition_builder = create_safe_condition_builder()

    SECTION_CONDITION_MAP = {
        "new_devices": "NTFPRCS_new_dev_condition",
        "events": "NTFPRCS_event_condition",
    }

    sections_with_conditions = set(SECTION_CONDITION_MAP.keys())

    for section in sections:
        template = sql_templates.get(section)

        if not template:
            mylog("verbose", ["[Notification] Unknown section: ", section])
            continue

        safe_condition = ""
        parameters = {}

        try:
            if section in sections_with_conditions:
                condition_key = SECTION_CONDITION_MAP.get(section)
                condition_setting = get_setting_value(condition_key)

                if condition_setting:
                    safe_condition, parameters = condition_builder.get_safe_condition_legacy(
                        condition_setting
                    )

            sqlQuery = template.format(condition=safe_condition)

        except Exception as e:
            mylog("verbose", [f"[Notification] Error building condition for {section}: ", e])
            sqlQuery = template.format(condition="")
            parameters = {}

        mylog("debug", [f"[Notification] {section} SQL query: ", sqlQuery])
        mylog("debug", [f"[Notification] {section} parameters: ", parameters])

        try:
            json_obj = db.get_table_as_json(sqlQuery, parameters)
        except Exception as e:
            mylog("minimal", [f"[Notification] DB error in section {section}: ", e])
            continue

        final_json[section] = json_obj.json.get("data", [])
        final_json[f"{section}_meta"] = {
            "title": section_titles.get(section, section),
            "columnNames": getattr(json_obj, "columnNames", [])
        }

    mylog("debug", [f"[Notification] final_json: {json.dumps(final_json)}"])

    return final_json


# -------------------------------------------------------------------------------
def skip_repeated_notifications(db):
    """
    Skips sending alerts for devices recently notified.

    Clears `eve_PendingAlertEmail` for events linked to devices whose last
    notification time is within their `devSkipRepeated` interval.

    Args:
        db: Database object with `.sql.execute()` and `.commitDB()`.
    """

    # Skip repeated notifications
    # due strfime : Overflow --> use  "strftime / 60"
    mylog("verbose", "[Skip Repeated Notifications] Skip Repeated")

    db.sql.execute("""UPDATE Events SET eve_PendingAlertEmail = 0
                    WHERE eve_PendingAlertEmail = 1 AND eve_MAC IN
                        (
                        SELECT devMac FROM Devices
                        WHERE devLastNotification IS NOT NULL
                          AND devLastNotification <>""
                          AND (strftime("%s", devLastNotification)/60 +
                                devSkipRepeated * 60) >
                              (strftime('%s','now','localtime')/60 )
                        )
                 """)

    db.commitDB()
