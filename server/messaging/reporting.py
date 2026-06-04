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
from messaging.notification_sections import (  # noqa: E402 [flake8 lint suppression]
    SECTION_ORDER,
    SECTION_TITLES,
    DATETIME_FIELDS,
    SQL_TEMPLATES,
    SECTIONS_WITH_CONDITIONS,
    SECTION_CONDITION_MAP,
)
import conf  # noqa: E402 [flake8 lint suppression]


# ===============================================================================
# Timezone conversion
# ===============================================================================
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
        UPDATE Events SET evePendingAlertEmail = 0
        WHERE evePendingAlertEmail = 1
          AND eveEventType NOT IN ('Device Down', 'Down Reconnected', 'New Device')
          AND eveMac IN (SELECT devMac FROM Devices WHERE devAlertEvents = 0)
    """)
    sql.execute("""
        UPDATE Events SET evePendingAlertEmail = 0
        WHERE evePendingAlertEmail = 1
          AND eveEventType IN ('Device Down', 'Down Reconnected')
          AND eveMac IN (SELECT devMac FROM Devices WHERE devAlertDown = 0)
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

    # SQL templates with placeholders for runtime values
    # {condition} and {alert_down_minutes} are formatted at query time

    # Initialize final structure
    final_json = {}
    for section in SECTION_ORDER:
        final_json[section] = []
        final_json[f"{section}_meta"] = {
            "title": SECTION_TITLES.get(section, section),
            "columnNames": []
        }

    condition_builder = create_safe_condition_builder()

    # -------------------------
    # Main loop
    # -------------------------
    for section in sections:
        template = SQL_TEMPLATES.get(section)

        if not template:
            mylog("verbose", ["[Notification] Unknown section: ", section])
            continue

        safe_condition = ""
        parameters = {}

        try:
            if section in SECTIONS_WITH_CONDITIONS:
                condition_key = SECTION_CONDITION_MAP.get(section)
                condition_setting = get_setting_value(condition_key)

                if condition_setting:
                    safe_condition, parameters = condition_builder.get_safe_condition_legacy(
                        condition_setting
                    )

            # Format template with runtime placeholders
            format_vars = {"condition": safe_condition}
            if section == "down_devices":
                format_vars["alert_down_minutes"] = alert_down_minutes
            if section == "events":
                # 'Down Reconnected' has its own dedicated section; exclude it
                # from events when that section is also active to prevent the
                # same device appearing twice with different IP sources.
                if "down_reconnected" in sections:
                    format_vars["event_types"] = "'Connected', 'Disconnected','IP Changed'"
                else:
                    format_vars["event_types"] = "'Connected', 'Down Reconnected', 'Disconnected','IP Changed'"
            sqlQuery = template.format(**format_vars)

        except Exception as e:
            mylog("verbose", [f"[Notification] Error building condition for {section}: ", e])
            fallback_vars = {"condition": ""}
            if section == "down_devices":
                fallback_vars["alert_down_minutes"] = alert_down_minutes
            if section == "events":
                if "down_reconnected" in sections:
                    fallback_vars["event_types"] = "'Connected', 'Disconnected','IP Changed'"
                else:
                    fallback_vars["event_types"] = "'Connected', 'Down Reconnected', 'Disconnected','IP Changed'"
            sqlQuery = template.format(**fallback_vars)
            parameters = {}

        mylog("debug", [f"[Notification] {section} SQL query: ", sqlQuery])
        mylog("debug", [f"[Notification] {section} parameters: ", parameters])

        try:
            json_obj = db.get_table_as_json(sqlQuery, parameters)
            data = apply_timezone_to_json(json_obj, section)
        except Exception as e:
            mylog("none", [f"[Notification] apply_timezone failed for section {section}: ", e])

            # fallback: preserve raw DB payload instead of dropping section
            try:
                data = json_obj.json.get("data", [])
            except Exception:
                data = []

            final_json[section] = data
            final_json[f"{section}_meta"] = {
                "title": SECTION_TITLES.get(section, section),
                "columnNames": getattr(json_obj, "columnNames", [])
            }
            continue

        final_json[section] = data
        final_json[f"{section}_meta"] = {
            "title": SECTION_TITLES.get(section, section),
            "columnNames": getattr(json_obj, "columnNames", [])
        }

    mylog("debug", [f"[Notification] final_json: {json.dumps(final_json)}"])

    return final_json


# -------------------------------------------------------------------------------
def skip_repeated_notifications(db):
    """
    Skips sending alerts for devices recently notified.

    Clears `evePendingAlertEmail` for events linked to devices whose last
    notification time is within their `devSkipRepeated` interval.

    Args:
        db: Database object with `.sql.execute()` and `.commitDB()`.
    """

    # Skip repeated notifications
    # due strfime : Overflow --> use  "strftime / 60"
    mylog("verbose", "[Skip Repeated Notifications] Skip Repeated")

    db.sql.execute("""UPDATE Events SET evePendingAlertEmail = 0
                    WHERE evePendingAlertEmail = 1 AND eveMac IN
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
