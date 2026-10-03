"""CONSTANTS for NetAlertX"""

import os

from config_paths import (
    API_PATH_STR,
    API_PATH_WITH_TRAILING_SEP,
    APP_PATH_STR,
    CONFIG_PATH_STR,
    CONFIG_PATH_WITH_TRAILING_SEP,
    DATA_PATH_STR,
    DB_PATH_STR,
    DB_PATH_WITH_TRAILING_SEP,
    LOG_PATH_STR,
    LOG_PATH_WITH_TRAILING_SEP,
    PLUGINS_PATH_WITH_TRAILING_SEP,
    REPORT_TEMPLATES_PATH_WITH_TRAILING_SEP,
)
from db.device_filter_columns import build_devices_filters_sql

# ===============================================================================
# PATHS
# ===============================================================================

applicationPath = APP_PATH_STR
dataPath = DATA_PATH_STR
configPath = CONFIG_PATH_STR
dbFolderPath = DB_PATH_STR
apiRoot = API_PATH_STR
logRoot = LOG_PATH_STR

dbFileName = "app.db"
confFileName = "app.conf"
defaultWebPort = 20211

confPath = CONFIG_PATH_WITH_TRAILING_SEP + confFileName
dbPath = DB_PATH_WITH_TRAILING_SEP + dbFileName
pluginsPath = PLUGINS_PATH_WITH_TRAILING_SEP.rstrip(os.sep)
logPath = LOG_PATH_WITH_TRAILING_SEP.rstrip(os.sep)
apiPath = API_PATH_WITH_TRAILING_SEP
reportTemplatesPath = REPORT_TEMPLATES_PATH_WITH_TRAILING_SEP
fullConfFolder = configPath
fullConfPath = confPath
fullDbPath = dbPath
vendorsPath = os.getenv("VENDORSPATH", "/usr/share/arp-scan/ieee-oui.txt")
vendorsPathNewest = os.getenv(
    "VENDORSPATH_NEWEST", "/usr/share/arp-scan/ieee-oui_all_filtered.txt"
)

NATIVE_SPEEDTEST_PATH = os.getenv("NATIVE_SPEEDTEST_PATH", "/usr/bin/speedtest")

default_tz = "Europe/Berlin"

# ===============================================================================
# Magic strings
# ===============================================================================

NULL_EQUIVALENTS = ["", "null", "(unknown)", "(Unknown)", "(name not found)"]

# Convert list to SQL string: wrap each value in single quotes and escape single quotes if needed
NULL_EQUIVALENTS_SQL = ",".join("'" + v.replace("'", "''") + "'" for v in NULL_EQUIVALENTS)

# ===============================================================================
# SQL queries
# ===============================================================================
sql_devices_all =   """
                        SELECT
                            *
                        FROM DevicesView
                    """

sql_appevents = """select * from AppEvents order by dateTimeCreated desc"""
sql_devices_filters = build_devices_filters_sql(NULL_EQUIVALENTS_SQL)

sql_devices_stats = f"""
                    SELECT
                        onlineDevices as online,
                        downDevices as down,
                        allDevices as 'all',
                        archivedDevices as archived,
                        (SELECT COUNT(*) FROM Devices a WHERE devIsNew = 1) as new,
                        (SELECT COUNT(*) FROM Devices a WHERE devName IN ({NULL_EQUIVALENTS_SQL}) OR devName IS NULL) as unknown
                    FROM Online_History
                    ORDER BY scanDate DESC
                    LIMIT 1
                    """
sql_events_pending_alert = "SELECT  * FROM Events where evePendingAlertEmail is not 0"
sql_events_all = "SELECT rowid, * FROM Events ORDER BY eveDateTime DESC"
sql_settings = "SELECT  * FROM Settings"
sql_plugins_objects = "SELECT  * FROM Plugins_Objects"
sql_plugins_stats = """SELECT 'objects' AS tableName, plugin, COUNT(*) AS cnt FROM Plugins_Objects GROUP BY plugin
                       UNION ALL
                       SELECT 'events',  plugin, COUNT(*) FROM Plugins_Events  GROUP BY plugin
                       UNION ALL
                       SELECT 'history', plugin, COUNT(*) FROM Plugins_History  GROUP BY plugin"""
sql_language_strings = "SELECT  * FROM Plugins_Language_Strings"
sql_notifications_all = "SELECT  * FROM Notifications"
sql_online_history = "SELECT  * FROM Online_History"

# Resource_History read-side views (System Info -> Performance tab).
# hour/day return raw per-tick rows (cheap indexed range scan); week/month
# roll up at query time into hourly buckets (SUM for additive IO bytes,
# AVG for CPU%/RSS/duration) - no pre-aggregated rollup table, see
# resource-usage-history PRD Design §4. Deltas are already stored per-row
# by insert_resource_history(), so no LAG()/window function is needed here.
sql_resource_history_hour = """
                    SELECT resDateTime, resCpuPercent, resRssMb, resIoReadBytes,
                           resIoWriteBytes, resScanDurationMs, resTickFailed
                    FROM Resource_History
                    WHERE resDateTime >= datetime('now', '-1 hour')
                    ORDER BY resDateTime
                    """
sql_resource_history_day = """
                    SELECT resDateTime, resCpuPercent, resRssMb, resIoReadBytes,
                           resIoWriteBytes, resScanDurationMs, resTickFailed
                    FROM Resource_History
                    WHERE resDateTime >= datetime('now', '-1 day')
                    ORDER BY resDateTime
                    """


sql_resource_history_bucketed_template = """
                    SELECT
                        strftime('%Y-%m-%d %H:00:00', resDateTime) AS bucket,
                        AVG(resCpuPercent) AS resCpuPercent,
                        AVG(resRssMb) AS resRssMb,
                        SUM(resIoReadBytes) AS resIoReadBytes,
                        SUM(resIoWriteBytes) AS resIoWriteBytes,
                        AVG(resScanDurationMs) AS resScanDurationMs,
                        MAX(resTickFailed) AS resTickFailed
                    FROM Resource_History
                    WHERE resDateTime >= datetime('now', '-{days} day')
                    GROUP BY bucket
                    ORDER BY bucket
                    """
sql_resource_history_week = sql_resource_history_bucketed_template.format(days=7)
sql_resource_history_month = sql_resource_history_bucketed_template.format(days=30)
sql_plugins_events = "SELECT  * FROM Plugins_Events"
sql_plugins_history = "SELECT  * FROM Plugins_History ORDER BY dateTimeChanged DESC"
sql_new_devices = """SELECT * FROM (
                        SELECT eveIp as devLastIP,
                               eveMac as devMac,
                               MAX(eveDateTime) as lastEvent
                        FROM Events_Devices
                        WHERE evePendingAlertEmail = 1
                        AND eveEventType = 'New Device'
                        GROUP BY eveMac
                        ORDER BY lastEvent
                     ) t1
                     LEFT JOIN
                     ( SELECT devName, devMac as devMac_t2 FROM Devices ) t2
                     ON t1.devMac = t2.devMac_t2"""


sql_generateGuid = """
                lower(
                    hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-' || '4' ||
                    substr(hex( randomblob(2)), 2) || '-' ||
                    substr('AB89', 1 + (abs(random()) % 4) , 1)  ||
                    substr(hex(randomblob(2)), 2) || '-' ||
                    hex(randomblob(6))
                )
            """
