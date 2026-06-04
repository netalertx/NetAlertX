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
sql_devices_filters = f"""
                    SELECT DISTINCT 'devSite' AS columnName, devSite AS columnValue, devSite AS columnLabel
                        FROM Devices WHERE devSite NOT IN ({NULL_EQUIVALENTS_SQL}) AND devSite IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devSourcePlugin' AS columnName, devSourcePlugin AS columnValue, devSourcePlugin AS columnLabel
                        FROM Devices WHERE devSourcePlugin NOT IN ({NULL_EQUIVALENTS_SQL}) AND devSourcePlugin IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devOwner' AS columnName, devOwner AS columnValue, devOwner AS columnLabel
                        FROM Devices WHERE devOwner NOT IN ({NULL_EQUIVALENTS_SQL}) AND devOwner IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devType' AS columnName, devType AS columnValue, devType AS columnLabel
                        FROM Devices WHERE devType NOT IN ({NULL_EQUIVALENTS_SQL}) AND devType IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devGroup' AS columnName, devGroup AS columnValue, devGroup AS columnLabel
                        FROM Devices WHERE devGroup NOT IN ({NULL_EQUIVALENTS_SQL}) AND devGroup IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devLocation' AS columnName, devLocation AS columnValue, devLocation AS columnLabel
                        FROM Devices WHERE devLocation NOT IN ({NULL_EQUIVALENTS_SQL}) AND devLocation IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devVendor' AS columnName, devVendor AS columnValue, devVendor AS columnLabel
                        FROM Devices WHERE devVendor NOT IN ({NULL_EQUIVALENTS_SQL}) AND devVendor IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devSyncHubNode' AS columnName, devSyncHubNode AS columnValue, devSyncHubNode AS columnLabel
                        FROM Devices WHERE devSyncHubNode NOT IN ({NULL_EQUIVALENTS_SQL}) AND devSyncHubNode IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devVlan' AS columnName, devVlan AS columnValue, devVlan AS columnLabel
                        FROM Devices WHERE devVlan NOT IN ({NULL_EQUIVALENTS_SQL}) AND devVlan IS NOT NULL
                    UNION
                    SELECT 'devParentMAC' AS columnName, d.devParentMAC AS columnValue,
                           COALESCE(p.devName, d.devParentMAC) AS columnLabel
                        FROM Devices d
                        LEFT JOIN Devices p ON LOWER(p.devMac) = LOWER(d.devParentMAC)
                        WHERE d.devParentMAC NOT IN ({NULL_EQUIVALENTS_SQL}) AND d.devParentMAC IS NOT NULL
                        GROUP BY d.devParentMAC COLLATE NOCASE
                    UNION
                    SELECT DISTINCT 'devParentRelType' AS columnName, devParentRelType AS columnValue, devParentRelType AS columnLabel
                        FROM Devices WHERE devParentRelType NOT IN ({NULL_EQUIVALENTS_SQL}) AND devParentRelType IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devSSID' AS columnName, devSSID AS columnValue, devSSID AS columnLabel
                        FROM Devices WHERE devSSID NOT IN ({NULL_EQUIVALENTS_SQL}) AND devSSID IS NOT NULL
                    ORDER BY columnName;
                    """

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
