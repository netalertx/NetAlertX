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
sql_devices_all = """
                    SELECT
                        rowid,
                        IFNULL(devMac, '') AS devMac,
                        IFNULL(devName, '') AS devName,
                        IFNULL(devOwner, '') AS devOwner,
                        IFNULL(devType, '') AS devType,
                        IFNULL(devVendor, '') AS devVendor,
                        IFNULL(devFavorite, '') AS devFavorite,
                        IFNULL(devGroup, '') AS devGroup,
                        IFNULL(devComments, '') AS devComments,
                        IFNULL(devFirstConnection, '') AS devFirstConnection,
                        IFNULL(devLastConnection, '') AS devLastConnection,
                        IFNULL(devLastIP, '') AS devLastIP,
                        IFNULL(devPrimaryIPv4, '') AS devPrimaryIPv4,
                        IFNULL(devPrimaryIPv6, '') AS devPrimaryIPv6,
                        IFNULL(devVlan, '') AS devVlan,
                        IFNULL(devForceStatus, '') AS devForceStatus,
                        IFNULL(devStaticIP, '') AS devStaticIP,
                        IFNULL(devScan, '') AS devScan,
                        IFNULL(devLogEvents, '') AS devLogEvents,
                        IFNULL(devAlertEvents, '') AS devAlertEvents,
                        IFNULL(devAlertDown, '') AS devAlertDown,
                        IFNULL(devSkipRepeated, '') AS devSkipRepeated,
                        IFNULL(devLastNotification, '') AS devLastNotification,
                        IFNULL(devPresentLastScan, 0) AS devPresentLastScan,
                        IFNULL(devIsNew, '') AS devIsNew,
                        IFNULL(devLocation, '') AS devLocation,
                        IFNULL(devIsArchived, '') AS devIsArchived,
                        IFNULL(devParentMAC, '') AS devParentMAC,
                        IFNULL(devParentPort, '') AS devParentPort,
                        IFNULL(devIcon, '') AS devIcon,
                        IFNULL(devGUID, '') AS devGUID,
                        IFNULL(devSite, '') AS devSite,
                        IFNULL(devSSID, '') AS devSSID,
                        IFNULL(devSyncHubNode, '') AS devSyncHubNode,
                        IFNULL(devSourcePlugin, '') AS devSourcePlugin,
                        IFNULL(devCustomProps, '') AS devCustomProps,
                        IFNULL(devFQDN, '') AS devFQDN,
                        IFNULL(devParentRelType, '') AS devParentRelType,
                        IFNULL(devReqNicsOnline, '') AS devReqNicsOnline,
                        IFNULL(devMacSource, '') AS devMacSource,
                        IFNULL(devNameSource, '') AS devNameSource,
                        IFNULL(devFQDNSource, '') AS devFQDNSource,
                        IFNULL(devLastIPSource, '') AS devLastIPSource,
                        IFNULL(devVendorSource, '') AS devVendorSource,
                        IFNULL(devSSIDSource, '') AS devSSIDSource,
                        IFNULL(devParentMACSource, '') AS devParentMACSource,
                        IFNULL(devParentPortSource, '') AS devParentPortSource,
                        IFNULL(devParentRelTypeSource, '') AS devParentRelTypeSource,
                        IFNULL(devVlanSource, '') AS devVlanSource,
                        CASE
                            WHEN devIsNew = 1 THEN 'New'
                            WHEN devPresentLastScan = 1 THEN 'On-line'
                            WHEN devPresentLastScan = 0 AND devAlertDown != 0 THEN 'Down'
                            WHEN devIsArchived = 1 THEN 'Archived'
                            WHEN devPresentLastScan = 0 THEN 'Off-line'
                            ELSE 'Unknown status'
                        END AS devStatus
                    FROM Devices
                    """

sql_appevents = """select * from AppEvents order by DateTimeCreated desc"""
# The below query calculates counts of devices in various categories:
#  (connected/online, offline, down, new, archived),
#  as well as a combined count for devices that match any status listed in the UI_MY_DEVICES setting
sql_devices_tiles = """
                        WITH Statuses AS (
                            SELECT setValue
                            FROM Settings
                            WHERE setKey = 'UI_MY_DEVICES'
                        ),
                        MyDevicesFilter AS (
                            SELECT
                                -- Build a dynamic filter for devices matching any status in UI_MY_DEVICES
                                devPresentLastScan, devAlertDown, devIsNew, devIsArchived
                            FROM Devices
                            WHERE
                                (instr((SELECT setValue FROM Statuses), 'online') > 0 AND devPresentLastScan = 1) OR
                                (instr((SELECT setValue FROM Statuses), 'offline') > 0 AND devPresentLastScan = 0 AND devIsArchived = 0) OR
                                (instr((SELECT setValue FROM Statuses), 'down') > 0 AND devPresentLastScan = 0 AND devAlertDown = 1) OR
                                (instr((SELECT setValue FROM Statuses), 'new') > 0 AND devIsNew = 1) OR
                                (instr((SELECT setValue FROM Statuses), 'archived') > 0 AND devIsArchived = 1)
                        )
                        SELECT
                            -- Counts for each individual status
                            (SELECT COUNT(*) FROM Devices WHERE devPresentLastScan = 1) AS connected,
                            (SELECT COUNT(*) FROM Devices WHERE devPresentLastScan = 0) AS offline,
                            (SELECT COUNT(*) FROM Devices WHERE devPresentLastScan = 0 AND devAlertDown = 1) AS down,
                            (SELECT COUNT(*) FROM Devices WHERE devIsNew = 1) AS new,
                            (SELECT COUNT(*) FROM Devices WHERE devIsArchived = 1) AS archived,
                            (SELECT COUNT(*) FROM Devices WHERE devFavorite = 1) AS favorites,
                            (SELECT COUNT(*) FROM Devices) AS "all",
                            (SELECT COUNT(*) FROM Devices) AS "all_devices",
                            -- My Devices count
                            (SELECT COUNT(*) FROM MyDevicesFilter) AS my_devices
                        FROM Statuses;
                    """
sql_devices_filters = """
                    SELECT DISTINCT 'devSite' AS columnName, devSite AS columnValue
                        FROM Devices WHERE devSite NOT IN ('', 'null') AND devSite IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devSourcePlugin' AS columnName, devSourcePlugin AS columnValue
                        FROM Devices WHERE devSourcePlugin NOT IN ('', 'null') AND devSourcePlugin IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devOwner' AS columnName, devOwner AS columnValue
                        FROM Devices WHERE devOwner NOT IN ('', 'null') AND devOwner IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devType' AS columnName, devType AS columnValue
                        FROM Devices WHERE devType NOT IN ('', 'null') AND devType IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devGroup' AS columnName, devGroup AS columnValue
                        FROM Devices WHERE devGroup NOT IN ('', 'null') AND devGroup IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devLocation' AS columnName, devLocation AS columnValue
                        FROM Devices WHERE devLocation NOT IN ('', 'null') AND devLocation IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devVendor' AS columnName, devVendor AS columnValue
                        FROM Devices WHERE devVendor NOT IN ('', 'null') AND devVendor IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devSyncHubNode' AS columnName, devSyncHubNode AS columnValue
                        FROM Devices WHERE devSyncHubNode NOT IN ('', 'null') AND devSyncHubNode IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devVlan' AS columnName, devVlan AS columnValue
                        FROM Devices WHERE devVlan NOT IN ('', 'null') AND devVlan IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devParentRelType' AS columnName, devParentRelType AS columnValue
                        FROM Devices WHERE devParentRelType NOT IN ('', 'null') AND devParentRelType IS NOT NULL
                    UNION
                    SELECT DISTINCT 'devSSID' AS columnName, devSSID AS columnValue
                        FROM Devices WHERE devSSID NOT IN ('', 'null') AND devSSID IS NOT NULL
                    ORDER BY columnName;
                    """

sql_devices_stats = f"""
                    SELECT
                        Online_Devices as online,
                        Down_Devices as down,
                        All_Devices as 'all',
                        Archived_Devices as archived,
                        (SELECT COUNT(*) FROM Devices a WHERE devIsNew = 1) as new,
                        (SELECT COUNT(*) FROM Devices a WHERE devName IN ({NULL_EQUIVALENTS_SQL}) OR devName IS NULL) as unknown
                    FROM Online_History
                    ORDER BY Scan_Date DESC
                    LIMIT 1
                    """
sql_events_pending_alert = "SELECT  * FROM Events where eve_PendingAlertEmail is not 0"
sql_settings = "SELECT  * FROM Settings"
sql_plugins_objects = "SELECT  * FROM Plugins_Objects"
sql_language_strings = "SELECT  * FROM Plugins_Language_Strings"
sql_notifications_all = "SELECT  * FROM Notifications"
sql_online_history = "SELECT  * FROM Online_History"
sql_plugins_events = "SELECT  * FROM Plugins_Events"
sql_plugins_history = "SELECT  * FROM Plugins_History ORDER BY DateTimeChanged DESC"
sql_new_devices = """SELECT * FROM (
                        SELECT eve_IP as devLastIP,
                               eve_MAC as devMac,
                               MAX(eve_DateTime) as lastEvent
                        FROM Events_Devices
                        WHERE eve_PendingAlertEmail = 1
                        AND eve_EventType = 'New Device'
                        GROUP BY eve_MAC
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
