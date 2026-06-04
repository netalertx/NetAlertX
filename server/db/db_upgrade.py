import conf
from zoneinfo import ZoneInfo
import datetime as dt
from logger import mylog  # noqa: E402 [flake8 lint suppression]
from messaging.in_app import write_notification  # noqa: E402 [flake8 lint suppression]


# Define the expected Devices table columns (hardcoded base schema) [v26.1/2.XX]
EXPECTED_DEVICES_COLUMNS = [
    "devMac",
    "devName",
    "devOwner",
    "devType",
    "devVendor",
    "devFavorite",
    "devGroup",
    "devComments",
    "devFirstConnection",
    "devLastConnection",
    "devLastIP",
    "devFQDN",
    "devPrimaryIPv4",
    "devPrimaryIPv6",
    "devVlan",
    "devForceStatus",
    "devStaticIP",
    "devScan",
    "devLogEvents",
    "devAlertEvents",
    "devAlertDown",
    "devCanSleep",
    "devSkipRepeated",
    "devLastNotification",
    "devPresentLastScan",
    "devIsNew",
    "devLocation",
    "devIsArchived",
    "devParentMAC",
    "devParentPort",
    "devParentRelType",
    "devReqNicsOnline",
    "devIcon",
    "devGUID",
    "devSite",
    "devSSID",
    "devSyncHubNode",
    "devSourcePlugin",
    "devMacSource",
    "devNameSource",
    "devFQDNSource",
    "devLastIPSource",
    "devVendorSource",
    "devSSIDSource",
    "devParentMACSource",
    "devParentPortSource",
    "devParentRelTypeSource",
    "devVlanSource",
    "devCustomProps",
]


def ensure_column(sql, table: str, column_name: str, column_type: str) -> bool:
    """
    Ensures a column exists in the specified table. If missing, attempts to add it.
    Returns True on success, False on failure.

    Parameters:
    - sql: database cursor or connection wrapper (must support execute() and fetchall()).
    - table: name of the table (e.g., "Devices").
    - column_name: name of the column to ensure.
    - column_type: SQL type of the column (e.g., "TEXT", "INTEGER", "BOOLEAN").
    """

    try:
        # Get actual columns from DB
        sql.execute(f'PRAGMA table_info("{table}")')
        actual_columns = [row[1] for row in sql.fetchall()]

        # Check if target column is already present
        if column_name in actual_columns:
            return True  # Already exists

        # Validate that this column is in the expected schema
        expected = EXPECTED_DEVICES_COLUMNS if table == "Devices" else []
        if not expected or column_name not in expected:
            msg = (
                f"[db_upgrade] ⚠ ERROR: Column '{column_name}' is not in expected schema - "
                f"aborting to prevent corruption. "
                "Check https://docs.netalertx.com/UPDATES"
            )
            mylog("none", [msg])
            write_notification(msg)
            return False

        # Add missing column
        mylog("verbose", [f"[db_upgrade] Adding '{column_name}' ({column_type}) to {table} table"],)
        sql.execute(f'ALTER TABLE "{table}" ADD "{column_name}" {column_type}')
        return True

    except Exception as e:
        mylog("none", [f"[db_upgrade] ERROR while adding '{column_name}': {e}"])
        return False


def ensure_mac_lowercase_triggers(sql):
    """
    Ensures the triggers for lowercasing MAC addresses exist on the Devices table.
    """
    try:
        # 1. Handle INSERT Trigger
        sql.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_lowercase_mac_insert'")
        if not sql.fetchone():
            mylog("verbose", ["[db_upgrade] Creating trigger 'trg_lowercase_mac_insert'"])
            sql.execute("""
                CREATE TRIGGER trg_lowercase_mac_insert
                AFTER INSERT ON Devices
                BEGIN
                    UPDATE Devices
                    SET devMac = LOWER(NEW.devMac),
                        devParentMAC = LOWER(NEW.devParentMAC)
                    WHERE rowid = NEW.rowid;
                END;
            """)

        # 2. Handle UPDATE Trigger
        sql.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_lowercase_mac_update'")
        if not sql.fetchone():
            mylog("verbose", ["[db_upgrade] Creating trigger 'trg_lowercase_mac_update'"])
            # Note: Using 'WHEN' to prevent unnecessary updates and recursion
            sql.execute("""
                CREATE TRIGGER trg_lowercase_mac_update
                AFTER UPDATE OF devMac, devParentMAC ON Devices
                WHEN (NEW.devMac GLOB '*[A-Z]*') OR (NEW.devParentMAC GLOB '*[A-Z]*')
                BEGIN
                    UPDATE Devices
                    SET devMac = LOWER(NEW.devMac),
                        devParentMAC = LOWER(NEW.devParentMAC)
                    WHERE rowid = NEW.rowid;
                END;
            """)

        return True

    except Exception as e:
        mylog("none", [f"[db_upgrade] ERROR while ensuring MAC triggers: {e}"])
        return False


def ensure_views(sql) -> bool:
    """
    Ensures required views exist.

    Parameters:
    - sql: database cursor or connection wrapper (must support execute() and fetchall()).
    """
    sql.execute(""" DROP VIEW IF EXISTS Events_Devices;""")
    sql.execute(""" CREATE VIEW Events_Devices AS
                            SELECT *
                            FROM Events
                            LEFT JOIN Devices ON eveMac = devMac;
                          """)

    sql.execute(""" DROP VIEW IF EXISTS LatestEventsPerMAC;""")
    sql.execute("""CREATE VIEW LatestEventsPerMAC AS
                                WITH RankedEvents AS (
                                    SELECT
                                        e.*,
                                        ROW_NUMBER() OVER (PARTITION BY e.eveMac ORDER BY e.eveDateTime DESC) AS row_num
                                    FROM Events AS e
                                )
                                SELECT
                                    e.*,
                                    d.*,
                                    c.*
                                FROM RankedEvents AS e
                                LEFT JOIN Devices AS d ON e.eveMac = d.devMac
                                INNER JOIN CurrentScan AS c ON e.eveMac = c.scanMac
                                WHERE e.row_num = 1;""")

    sql.execute(""" DROP VIEW IF EXISTS Sessions_Devices;""")
    sql.execute(
        """CREATE VIEW Sessions_Devices AS SELECT * FROM Sessions LEFT JOIN "Devices" ON sesMac = devMac;"""
    )

    # handling the Convert_Events_to_Sessions / Sessions screens
    sql.execute("""DROP VIEW IF EXISTS Convert_Events_to_Sessions;""")
    sql.execute("""CREATE VIEW Convert_Events_to_Sessions AS  SELECT EVE1.eveMac,
                                      EVE1.eveIp,
                                      EVE1.eveEventType AS eveEventTypeConnection,
                                      EVE1.eveDateTime AS eveDateTimeConnection,
                                      CASE WHEN EVE2.eveEventType IN ('Disconnected', 'Device Down') OR
                                                EVE2.eveEventType IS NULL THEN EVE2.eveEventType ELSE '<missing event>' END AS eveEventTypeDisconnection,
                                      CASE WHEN EVE2.eveEventType IN ('Disconnected', 'Device Down') THEN EVE2.eveDateTime ELSE NULL END AS eveDateTimeDisconnection,
                                      CASE WHEN EVE2.eveEventType IS NULL THEN 1 ELSE 0 END AS eveStillConnected,
                                      EVE1.eveAdditionalInfo
                                  FROM Events AS EVE1
                                      LEFT JOIN
                                      Events AS EVE2 ON EVE1.evePairEventRowid = EVE2.RowID
                                WHERE EVE1.eveEventType IN ('New Device', 'Connected','Down Reconnected')
                            UNION
                                SELECT eveMac,
                                      eveIp,
                                      '<missing event>' AS eveEventTypeConnection,
                                      NULL AS eveDateTimeConnection,
                                      eveEventType AS eveEventTypeDisconnection,
                                      eveDateTime AS eveDateTimeDisconnection,
                                      0 AS eveStillConnected,
                                      eveAdditionalInfo
                                  FROM Events AS EVE1
                                WHERE (eveEventType = 'Device Down' OR
                                        eveEventType = 'Disconnected') AND
                                      EVE1.evePairEventRowid IS NULL;
                          """)

    sql.execute(""" DROP VIEW IF EXISTS LatestDeviceScan;""")
    sql.execute(""" CREATE VIEW LatestDeviceScan AS
                        WITH RankedScans AS (
                            SELECT
                                c.*,
                                ROW_NUMBER() OVER (
                                    PARTITION BY c.scanMac, c.scanSourcePlugin
                                    ORDER BY c.scanLastConnection DESC
                                ) AS rn
                            FROM CurrentScan c
                        )
                        SELECT
                            d.*,           -- all Device fields
                            r.*            -- all CurrentScan fields
                        FROM Devices d
                        LEFT JOIN RankedScans r
                            ON d.devMac = r.scanMac
                        WHERE r.rn = 1;

                          """)

    FLAP_THRESHOLD = 3
    FLAP_WINDOW_HOURS = 1

    # Read sleep window from settings; fall back to 30 min if not yet configured.
    # Uses the same sql cursor (no separate connection) to avoid lock contention.
    # Note: changing NTFPRCS_sleep_time requires a restart to take effect,
    # same behaviour as FLAP_THRESHOLD / FLAP_WINDOW_HOURS.
    try:
        sql.execute("SELECT setValue FROM Settings WHERE setKey = 'NTFPRCS_sleep_time'")
        _sleep_row = sql.fetchone()
        SLEEP_MINUTES = int(_sleep_row[0]) if _sleep_row and _sleep_row[0] else 30
    except Exception:
        SLEEP_MINUTES = 30

    sql.execute(""" DROP VIEW IF EXISTS DevicesView;""")
    sql.execute(f""" CREATE VIEW DevicesView AS
                    -- CTE computes devIsSleeping and devFlapping so devStatus can
                    -- reference them without duplicating the sub-expressions.
                    WITH base AS (
                        SELECT
                        rowid,
                        LOWER(IFNULL(devMac, '')) AS devMac,
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
                        IFNULL(devAlertDown, 0) AS devAlertDown,
                        IFNULL(devCanSleep, 0) AS devCanSleep,
                        IFNULL(devSkipRepeated, '') AS devSkipRepeated,
                        IFNULL(devLastNotification, '') AS devLastNotification,
                        IFNULL(devPresentLastScan, 0) AS devPresentLastScan,
                        IFNULL(devIsNew, '') AS devIsNew,
                        IFNULL(devLocation, '') AS devLocation,
                        IFNULL(devIsArchived, '') AS devIsArchived,
                        LOWER(IFNULL(devParentMAC, '')) AS devParentMAC,
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
                        -- devIsSleeping: opted-in, absent, and still within the sleep window
                        CASE
                            WHEN devCanSleep = 1
                             AND devPresentLastScan = 0
                             AND devLastConnection >= datetime('now', '-{SLEEP_MINUTES} minutes')
                            THEN 1
                            ELSE 0
                        END AS devIsSleeping,
                        -- devFlapping: toggling online/offline frequently within the flap window
                        CASE
                            WHEN EXISTS (
                                SELECT 1
                                FROM Events e
                                WHERE LOWER(e.eveMac) = LOWER(Devices.devMac)
                                AND e.eveEventType IN ('Connected','Disconnected','Device Down','Down Reconnected')
                                AND e.eveDateTime >= datetime('now', '-{FLAP_WINDOW_HOURS} hours')
                                GROUP BY e.eveMac
                                HAVING COUNT(*) >= {FLAP_THRESHOLD}
                            )
                            THEN 1
                            ELSE 0
                        END AS devFlapping
                        FROM Devices
                    )
                    SELECT *,
                        -- devStatus references devIsSleeping from the CTE (no duplication)
                        CASE
                            WHEN devIsNew = 1          THEN 'New'
                            WHEN devPresentLastScan = 1 THEN 'On-line'
                            WHEN devIsSleeping = 1     THEN 'Sleeping'
                            WHEN devAlertDown != 0     THEN 'Down'
                            WHEN devIsArchived = 1     THEN 'Archived'
                            WHEN devPresentLastScan = 0 THEN 'Off-line'
                            ELSE 'Unknown status'
                        END AS devStatus
                    FROM base

                          """)

    return True


def ensure_Indexes(sql) -> bool:
    """
    Ensures required indexes exist with correct structure.

    Parameters:
    - sql: database cursor or connection wrapper (must support execute()).
    """

    # Remove after 12/12/2026 - prevens idx_events_unique from failing - dedupe
    clean_duplicate_events = """
                                DELETE FROM Events
                                    WHERE rowid NOT IN (
                                        SELECT MIN(rowid)
                                        FROM Events
                                        GROUP BY
                                            eveMac,
                                            eveIp,
                                            eveEventType,
                                            eveDateTime
                                    );
                            """

    sql.execute(clean_duplicate_events)

    indexes = [
        # Sessions
        (
            "idx_ses_mac_date",
            "CREATE INDEX idx_ses_mac_date ON Sessions(sesMac, sesDateTimeConnection, sesDateTimeDisconnection, sesStillConnected)",
        ),
        # Events
        (
            "idx_eve_mac_date_type",
            "CREATE INDEX idx_eve_mac_date_type ON Events(eveMac, eveDateTime, eveEventType)",
        ),
        (
            "idx_eve_alert_pending",
            "CREATE INDEX idx_eve_alert_pending ON Events(evePendingAlertEmail)",
        ),
        (
            "idx_eve_mac_datetime_desc",
            "CREATE INDEX idx_eve_mac_datetime_desc ON Events(eveMac, eveDateTime DESC)",
        ),
        (
            "idx_eve_pairevent",
            "CREATE INDEX idx_eve_pairevent ON Events(evePairEventRowid)",
        ),
        (
            "idx_eve_type_date",
            "CREATE INDEX idx_eve_type_date ON Events(eveEventType, eveDateTime)",
        ),
        (
            "idx_events_unique",
            "CREATE UNIQUE INDEX idx_events_unique ON Events (eveMac, eveIp, eveEventType, eveDateTime)",
        ),
        # Devices
        ("idx_dev_mac", "CREATE INDEX idx_dev_mac ON Devices(devMac)"),
        (
            "idx_dev_present",
            "CREATE INDEX idx_dev_present ON Devices(devPresentLastScan)",
        ),
        (
            "idx_dev_alertdown",
            "CREATE INDEX idx_dev_alertdown ON Devices(devAlertDown)",
        ),
        (
            "idx_dev_cansleep",
            "CREATE INDEX idx_dev_cansleep ON Devices(devCanSleep)",
        ),
        ("idx_dev_isnew", "CREATE INDEX idx_dev_isnew ON Devices(devIsNew)"),
        (
            "idx_dev_isarchived",
            "CREATE INDEX idx_dev_isarchived ON Devices(devIsArchived)",
        ),
        ("idx_dev_favorite", "CREATE INDEX idx_dev_favorite ON Devices(devFavorite)"),
        (
            "idx_dev_parentmac",
            "CREATE INDEX idx_dev_parentmac ON Devices(devParentMAC)",
        ),
        # Optional filter indexes
        ("idx_dev_site", "CREATE INDEX idx_dev_site ON Devices(devSite)"),
        ("idx_dev_group", "CREATE INDEX idx_dev_group ON Devices(devGroup)"),
        ("idx_dev_owner", "CREATE INDEX idx_dev_owner ON Devices(devOwner)"),
        ("idx_dev_type", "CREATE INDEX idx_dev_type ON Devices(devType)"),
        ("idx_dev_vendor", "CREATE INDEX idx_dev_vendor ON Devices(devVendor)"),
        ("idx_dev_location", "CREATE INDEX idx_dev_location ON Devices(devLocation)"),
        # Settings
        ("idx_set_key", "CREATE INDEX idx_set_key ON Settings(setKey)"),
        # Plugins_Objects
        (
            "idx_plugins_plugin_mac_ip",
            "CREATE INDEX idx_plugins_plugin_mac_ip ON Plugins_Objects(plugin, objectPrimaryId, objectSecondaryId)",
        ),  # Issue #1251: Optimize name resolution lookup
        # Plugins_History: covers both the db_cleanup window function
        # (PARTITION BY plugin ORDER BY dateTimeChanged DESC) and the
        # API query (SELECT * … ORDER BY dateTimeChanged DESC).
        # Without this, both ops do a full 48k-row table sort on every cycle.
        (
            "idx_plugins_history_plugin_dt",
            "CREATE INDEX idx_plugins_history_plugin_dt ON Plugins_History(plugin, dateTimeChanged DESC)",
        ),
    ]

    for name, create_sql in indexes:
        sql.execute(f"DROP INDEX IF EXISTS {name};")
        sql.execute(create_sql + ";")

    return True


def ensure_CurrentScan(sql) -> bool:
    """
    Ensures required CurrentScan table exist.

    Parameters:
    - sql: database cursor or connection wrapper (must support execute() and fetchall()).
    """
    # 🐛 CurrentScan DEBUG: comment out below when debugging to keep the CurrentScan table after restarts/scan finishes
    sql.execute("DROP TABLE IF EXISTS CurrentScan;")
    sql.execute(""" CREATE TABLE IF NOT EXISTS CurrentScan (
                                scanMac STRING(50) NOT NULL COLLATE NOCASE,
                                scanLastIP STRING(50) NOT NULL COLLATE NOCASE,
                                scanVendor STRING(250),
                                scanSourcePlugin STRING(10),
                                scanName STRING(250),
                                scanLastQuery STRING(250),
                                scanLastConnection STRING(250),
                                scanSyncHubNode STRING(50),
                                scanSite STRING(250),
                                scanSSID STRING(250),
                                scanVlan STRING(250),
                                scanParentMAC STRING(250),
                                scanParentPort STRING(250),
                                scanFQDN STRING(250),
                                scanType STRING(250)
                            );
                        """)

    return True


def ensure_Parameters(sql) -> bool:
    """
    Ensures required Parameters table exist.

    Parameters:
    - sql: database cursor or connection wrapper (must support execute() and fetchall()).
    """

    # Re-creating Parameters table
    mylog("verbose", ["[db_upgrade] Re-creating Parameters table"])
    sql.execute("DROP TABLE Parameters;")

    sql.execute("""
          CREATE TABLE "Parameters" (
            "parID" TEXT PRIMARY KEY,
            "parValue"	TEXT
          );
          """)

    return True


def ensure_Settings(sql) -> bool:
    """
    Ensures required Settings table exist.

    Parameters:
    - sql: database cursor or connection wrapper (must support execute() and fetchall()).
    """

    # Re-creating Settings table
    mylog("verbose", ["[db_upgrade] Re-creating Settings table"])

    sql.execute(""" DROP TABLE IF EXISTS Settings;""")
    sql.execute("""
            CREATE TABLE "Settings" (
            "setKey"	        TEXT,
            "setName"	        TEXT,
            "setDescription"	TEXT,
            "setType"         TEXT,
            "setOptions"      TEXT,
            "setGroup"	          TEXT,
            "setValue"	      TEXT,
            "setEvents"	        TEXT,
            "setOverriddenByEnv" INTEGER
            );
            """)

    return True


def ensure_plugins_tables(sql) -> bool:
    """
    Ensures required plugins tables exist.

    Parameters:
    - sql: database cursor or connection wrapper (must support execute() and fetchall()).
    """

    # Plugin state
    sql_Plugins_Objects = """ CREATE TABLE IF NOT EXISTS Plugins_Objects(
                                    "index"           INTEGER,
                                    plugin TEXT NOT NULL,
                                    objectPrimaryId TEXT NOT NULL,
                                    objectSecondaryId TEXT NOT NULL,
                                    dateTimeCreated TEXT NOT NULL,
                                    dateTimeChanged TEXT NOT NULL,
                                    watchedValue1 TEXT NOT NULL,
                                    watchedValue2 TEXT NOT NULL,
                                    watchedValue3 TEXT NOT NULL,
                                    watchedValue4 TEXT NOT NULL,
                                    "status" TEXT NOT NULL,
                                    extra TEXT NOT NULL,
                                    userData TEXT NOT NULL,
                                    foreignKey TEXT NOT NULL,
                                    syncHubNodeName TEXT,
                                    helpVal1 TEXT,
                                    helpVal2 TEXT,
                                    helpVal3 TEXT,
                                    helpVal4 TEXT,
                                    objectGuid TEXT,
                                    PRIMARY KEY("index" AUTOINCREMENT)
                        ); """
    sql.execute(sql_Plugins_Objects)

    # Plugin execution results
    sql_Plugins_Events = """ CREATE TABLE IF NOT EXISTS Plugins_Events(
                                    "index"           INTEGER,
                                    plugin TEXT NOT NULL,
                                    objectPrimaryId TEXT NOT NULL,
                                    objectSecondaryId TEXT NOT NULL,
                                    dateTimeCreated TEXT NOT NULL,
                                    dateTimeChanged TEXT NOT NULL,
                                    watchedValue1 TEXT NOT NULL,
                                    watchedValue2 TEXT NOT NULL,
                                    watchedValue3 TEXT NOT NULL,
                                    watchedValue4 TEXT NOT NULL,
                                    "status" TEXT NOT NULL,
                                    extra TEXT NOT NULL,
                                    userData TEXT NOT NULL,
                                    foreignKey TEXT NOT NULL,
                                    syncHubNodeName TEXT,
                                    helpVal1 TEXT,
                                    helpVal2 TEXT,
                                    helpVal3 TEXT,
                                    helpVal4 TEXT,
                                    objectGuid TEXT,
                                    PRIMARY KEY("index" AUTOINCREMENT)
                        ); """
    sql.execute(sql_Plugins_Events)

    # Plugin execution history
    sql_Plugins_History = """ CREATE TABLE IF NOT EXISTS Plugins_History(
                                    "index"           INTEGER,
                                    plugin TEXT NOT NULL,
                                    objectPrimaryId TEXT NOT NULL,
                                    objectSecondaryId TEXT NOT NULL,
                                    dateTimeCreated TEXT NOT NULL,
                                    dateTimeChanged TEXT NOT NULL,
                                    watchedValue1 TEXT NOT NULL,
                                    watchedValue2 TEXT NOT NULL,
                                    watchedValue3 TEXT NOT NULL,
                                    watchedValue4 TEXT NOT NULL,
                                    "status" TEXT NOT NULL,
                                    extra TEXT NOT NULL,
                                    userData TEXT NOT NULL,
                                    foreignKey TEXT NOT NULL,
                                    syncHubNodeName TEXT,
                                    helpVal1 TEXT,
                                    helpVal2 TEXT,
                                    helpVal3 TEXT,
                                    helpVal4 TEXT,
                                    objectGuid TEXT,
                                    PRIMARY KEY("index" AUTOINCREMENT)
                        ); """
    sql.execute(sql_Plugins_History)

    # Dynamically generated language strings
    sql.execute("DROP TABLE IF EXISTS Plugins_Language_Strings;")
    sql.execute(""" CREATE TABLE IF NOT EXISTS Plugins_Language_Strings(
                                "index"           INTEGER,
                                languageCode TEXT NOT NULL,
                                stringKey TEXT NOT NULL,
                                stringValue TEXT NOT NULL,
                                extra TEXT NOT NULL,
                                PRIMARY KEY("index" AUTOINCREMENT)
                        ); """)

    return True


# ===============================================================================
# CamelCase Column Migration
# ===============================================================================

# Mapping of (table_name, old_column_name) → new_column_name.
# Only entries where the name actually changes are listed.
# Columns like "Index" → "index" are cosmetic case changes handled
# implicitly by SQLite's case-insensitive matching.
_CAMELCASE_COLUMN_MAP = {
    "Events": {
        "eve_MAC": "eveMac",
        "eve_IP": "eveIp",
        "eve_DateTime": "eveDateTime",
        "eve_EventType": "eveEventType",
        "eve_AdditionalInfo": "eveAdditionalInfo",
        "eve_PendingAlertEmail": "evePendingAlertEmail",
        "eve_PairEventRowid": "evePairEventRowid",
        "eve_PairEventRowID": "evePairEventRowid",
    },
    "Sessions": {
        "ses_MAC": "sesMac",
        "ses_IP": "sesIp",
        "ses_EventTypeConnection": "sesEventTypeConnection",
        "ses_DateTimeConnection": "sesDateTimeConnection",
        "ses_EventTypeDisconnection": "sesEventTypeDisconnection",
        "ses_DateTimeDisconnection": "sesDateTimeDisconnection",
        "ses_StillConnected": "sesStillConnected",
        "ses_AdditionalInfo": "sesAdditionalInfo",
    },
    "Online_History": {
        "Index": "index",
        "Scan_Date": "scanDate",
        "Online_Devices": "onlineDevices",
        "Down_Devices": "downDevices",
        "All_Devices": "allDevices",
        "Archived_Devices": "archivedDevices",
        "Offline_Devices": "offlineDevices",
    },
    "Plugins_Objects": {
        "Index": "index",
        "Plugin": "plugin",
        "Object_PrimaryID": "objectPrimaryId",
        "Object_SecondaryID": "objectSecondaryId",
        "DateTimeCreated": "dateTimeCreated",
        "DateTimeChanged": "dateTimeChanged",
        "Watched_Value1": "watchedValue1",
        "Watched_Value2": "watchedValue2",
        "Watched_Value3": "watchedValue3",
        "Watched_Value4": "watchedValue4",
        "Status": "status",
        "Extra": "extra",
        "UserData": "userData",
        "ForeignKey": "foreignKey",
        "SyncHubNodeName": "syncHubNodeName",
        "HelpVal1": "helpVal1",
        "HelpVal2": "helpVal2",
        "HelpVal3": "helpVal3",
        "HelpVal4": "helpVal4",
        "ObjectGUID": "objectGuid",
    },
    "Plugins_Events": {
        "Index": "index",
        "Plugin": "plugin",
        "Object_PrimaryID": "objectPrimaryId",
        "Object_SecondaryID": "objectSecondaryId",
        "DateTimeCreated": "dateTimeCreated",
        "DateTimeChanged": "dateTimeChanged",
        "Watched_Value1": "watchedValue1",
        "Watched_Value2": "watchedValue2",
        "Watched_Value3": "watchedValue3",
        "Watched_Value4": "watchedValue4",
        "Status": "status",
        "Extra": "extra",
        "UserData": "userData",
        "ForeignKey": "foreignKey",
        "SyncHubNodeName": "syncHubNodeName",
        "HelpVal1": "helpVal1",
        "HelpVal2": "helpVal2",
        "HelpVal3": "helpVal3",
        "HelpVal4": "helpVal4",
        "ObjectGUID": "objectGuid",
    },
    "Plugins_History": {
        "Index": "index",
        "Plugin": "plugin",
        "Object_PrimaryID": "objectPrimaryId",
        "Object_SecondaryID": "objectSecondaryId",
        "DateTimeCreated": "dateTimeCreated",
        "DateTimeChanged": "dateTimeChanged",
        "Watched_Value1": "watchedValue1",
        "Watched_Value2": "watchedValue2",
        "Watched_Value3": "watchedValue3",
        "Watched_Value4": "watchedValue4",
        "Status": "status",
        "Extra": "extra",
        "UserData": "userData",
        "ForeignKey": "foreignKey",
        "SyncHubNodeName": "syncHubNodeName",
        "HelpVal1": "helpVal1",
        "HelpVal2": "helpVal2",
        "HelpVal3": "helpVal3",
        "HelpVal4": "helpVal4",
        "ObjectGUID": "objectGuid",
    },
    "Plugins_Language_Strings": {
        "Index": "index",
        "Language_Code": "languageCode",
        "String_Key": "stringKey",
        "String_Value": "stringValue",
        "Extra": "extra",
    },
    "AppEvents": {
        "Index": "index",
        "GUID": "guid",
        "AppEventProcessed": "appEventProcessed",
        "DateTimeCreated": "dateTimeCreated",
        "ObjectType": "objectType",
        "ObjectGUID": "objectGuid",
        "ObjectPlugin": "objectPlugin",
        "ObjectPrimaryID": "objectPrimaryId",
        "ObjectSecondaryID": "objectSecondaryId",
        "ObjectForeignKey": "objectForeignKey",
        "ObjectIndex": "objectIndex",
        "ObjectIsNew": "objectIsNew",
        "ObjectIsArchived": "objectIsArchived",
        "ObjectStatusColumn": "objectStatusColumn",
        "ObjectStatus": "objectStatus",
        "AppEventType": "appEventType",
        "Helper1": "helper1",
        "Helper2": "helper2",
        "Helper3": "helper3",
        "Extra": "extra",
    },
    "Notifications": {
        "Index": "index",
        "GUID": "guid",
        "DateTimeCreated": "dateTimeCreated",
        "DateTimePushed": "dateTimePushed",
        "Status": "status",
        "JSON": "json",
        "Text": "text",
        "HTML": "html",
        "PublishedVia": "publishedVia",
        "Extra": "extra",
    },
}


def migrate_to_camelcase(sql) -> bool:
    """
    Detects legacy (underscore/PascalCase) column names and renames them
    to camelCase using ALTER TABLE … RENAME COLUMN (SQLite ≥ 3.25.0).

    Idempotent: columns already matching the new name are silently skipped.
    """

    # Quick probe: if Events table has 'eveMac' we're already on the new schema
    sql.execute('PRAGMA table_info("Events")')
    events_cols = {row[1] for row in sql.fetchall()}
    if "eveMac" in events_cols:
        mylog("verbose", ["[db_upgrade] Schema already uses camelCase — skipping migration"])
        return True

    if "eve_MAC" not in events_cols:
        # Events table doesn't exist or has unexpected schema — skip silently
        mylog("verbose", ["[db_upgrade] Events table missing/unrecognised — skipping camelCase migration"])
        return True

    mylog("none", ["[db_upgrade] Starting camelCase column migration …"])

    # Drop views first — ALTER TABLE RENAME COLUMN will fail if a view
    # references the old column name and the view SQL cannot be rewritten.
    for view_name in ("Events_Devices", "LatestEventsPerMAC", "Sessions_Devices",
                      "Convert_Events_to_Sessions", "LatestDeviceScan", "DevicesView"):
        sql.execute(f"DROP VIEW IF EXISTS {view_name};")

    renamed_count = 0

    for table, column_map in _CAMELCASE_COLUMN_MAP.items():
        # Check table exists
        sql.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not sql.fetchone():
            mylog("verbose", [f"[db_upgrade] Table '{table}' does not exist — skipping"])
            continue

        # Get current column names (case-preserved)
        sql.execute(f'PRAGMA table_info("{table}")')
        current_cols = {row[1] for row in sql.fetchall()}

        for old_name, new_name in column_map.items():
            if old_name in current_cols and new_name not in current_cols:
                sql.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old_name}" TO "{new_name}"')
                renamed_count += 1
                mylog("verbose", [f"[db_upgrade]   {table}.{old_name} → {new_name}"])

    mylog("none", [f"[db_upgrade] ✓ camelCase migration complete — {renamed_count} columns renamed"])
    return True


# ===============================================================================
# UTC Timestamp Migration (added 2026-02-10)
# ===============================================================================

def is_timestamps_in_utc(sql) -> bool:
    """
    Check if existing timestamps in Devices table are already in UTC format.

    Strategy:
    1. Sample 10 non-NULL devFirstConnection timestamps from Devices
    2. For each timestamp, assume it's UTC and calculate what it would be in local time
    3. Check if timestamps have a consistent offset pattern (indicating local time storage)
    4. If offset is consistently > 0, they're likely local timestamps (need migration)
    5. If offset is ~0 or inconsistent, they're likely already UTC (skip migration)

    Returns:
        bool: True if timestamps appear to be in UTC already, False if they need migration
    """
    try:
        # Get timezone offset in seconds
        import conf
        import datetime as dt

        now = dt.datetime.now(dt.UTC).replace(microsecond=0)
        current_offset_seconds = 0

        try:
            if isinstance(conf.tz, dt.tzinfo):
                tz = conf.tz
            elif conf.tz:
                tz = ZoneInfo(conf.tz)
            else:
                tz = None
        except Exception:
            tz = None

        if tz:
            local_now = dt.datetime.now(tz).replace(microsecond=0)
            local_offset = local_now.utcoffset().total_seconds()
            utc_offset = now.utcoffset().total_seconds() if now.utcoffset() else 0
            current_offset_seconds = int(local_offset - utc_offset)

        # Sample timestamps from Devices table
        sql.execute("""
            SELECT devFirstConnection, devLastConnection, devLastNotification
            FROM Devices
            WHERE devFirstConnection IS NOT NULL
            LIMIT 10
        """)

        samples = []
        for row in sql.fetchall():
            for ts in row:
                if ts:
                    samples.append(ts)

        if not samples:
            mylog("verbose", "[db_upgrade] No timestamp samples found in Devices - assuming UTC")
            return True  # Empty DB, assume UTC

        # Parse samples and check if they have timezone info (which would indicate migration already done)
        has_tz_marker = any('+' in str(ts) or 'Z' in str(ts) for ts in samples)
        if has_tz_marker:
            mylog("verbose", "[db_upgrade] Timestamps have timezone markers - already migrated to UTC")
            return True

        mylog("debug", f"[db_upgrade] Sampled {len(samples)} timestamps. Current TZ offset: {current_offset_seconds}s")
        mylog("verbose", "[db_upgrade] Timestamps appear to be in system local time - migration needed")
        return False

    except Exception as e:
        mylog("warn", f"[db_upgrade] Error checking UTC status: {e} - assuming UTC")
        return True


def migrate_timestamps_to_utc(sql) -> bool:
    """
    Safely migrate timestamp columns from local time to UTC.

    Migration rules (fail-safe):
    - Default behaviour: RUN migration unless proven safe to skip
    - Version > 26.2.6 → timestamps already UTC → skip
    - Missing / unknown / unparsable version → migrate
    - Migration flag present → skip
    - Detection says already UTC → skip

    Returns:
        bool: True if migration completed or not needed, False on error
    """

    try:
        # -------------------------------------------------
        # Check migration flag (idempotency protection)
        # -------------------------------------------------
        try:
            sql.execute("SELECT setValue FROM Settings WHERE setKey='DB_TIMESTAMPS_UTC_MIGRATED'")
            result = sql.fetchone()
            if result and str(result[0]) == "1":
                mylog("verbose", "[db_upgrade] UTC timestamp migration already completed - skipping")
                return True
        except Exception:
            pass

        # -------------------------------------------------
        # Read previous version
        # -------------------------------------------------
        sql.execute("SELECT setValue FROM Settings WHERE setKey='VERSION'")
        result = sql.fetchone()
        prev_version = result[0] if result else ""

        mylog("verbose", f"[db_upgrade] Version '{prev_version}' detected.")

        # Default behaviour: migrate unless proven safe
        should_migrate = True

        # -------------------------------------------------
        # Version-based safety check
        # -------------------------------------------------
        if prev_version and str(prev_version).lower() != "unknown":
            try:
                version_parts = prev_version.lstrip('v').split('.')
                major = int(version_parts[0]) if len(version_parts) > 0 else 0
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0

                # UTC timestamps introduced AFTER v26.2.6
                if (major, minor, patch) > (26, 2, 6):
                    should_migrate = False
                    mylog(
                        "verbose",
                        f"[db_upgrade] Version {prev_version} confirmed UTC timestamps - skipping migration",
                    )

            except (ValueError, IndexError) as e:
                mylog(
                    "warn",
                    f"[db_upgrade] Could not parse version '{prev_version}': {e} - running migration as safety measure",
                )
        else:
            mylog(
                "warn",
                "[db_upgrade] VERSION missing/unknown - running migration as safety measure",
            )

        # -------------------------------------------------
        # Detection fallback
        # -------------------------------------------------
        if should_migrate:
            try:
                if is_timestamps_in_utc(sql):
                    mylog(
                        "verbose",
                        "[db_upgrade] Timestamps appear already UTC - skipping migration",
                    )
                    return True
            except Exception as e:
                mylog(
                    "warn",
                    f"[db_upgrade] UTC detection failed ({e}) - continuing with migration",
                )
        else:
            return True

        # Get timezone offset
        try:
            if isinstance(conf.tz, dt.tzinfo):
                tz = conf.tz
            elif conf.tz:
                tz = ZoneInfo(conf.tz)
            else:
                tz = None
        except Exception:
            tz = None

        if tz:
            now_local = dt.datetime.now(tz)
            offset_hours = (now_local.utcoffset().total_seconds()) / 3600
        else:
            offset_hours = 0

        mylog("verbose", f"[db_upgrade] Starting UTC timestamp migration (offset: {offset_hours} hours)")

        # List of tables and their datetime columns (camelCase names —
        # migrate_to_camelcase() runs before this function).
        timestamp_columns = {
            'Devices': ['devFirstConnection', 'devLastConnection', 'devLastNotification'],
            'Events': ['eveDateTime'],
            'Sessions': ['sesDateTimeConnection', 'sesDateTimeDisconnection'],
            'Notifications': ['dateTimeCreated', 'dateTimePushed'],
            'Online_History': ['scanDate'],
            'Plugins_Objects': ['dateTimeCreated', 'dateTimeChanged'],
            'Plugins_Events': ['dateTimeCreated', 'dateTimeChanged'],
            'Plugins_History': ['dateTimeCreated', 'dateTimeChanged'],
            'AppEvents': ['dateTimeCreated'],
        }

        for table, columns in timestamp_columns.items():
            try:
                # Check if table exists
                sql.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not sql.fetchone():
                    mylog("debug", f"[db_upgrade] Table '{table}' does not exist - skipping")
                    continue

                for column in columns:
                    try:
                        # Update non-NULL timestamps
                        if offset_hours > 0:
                            # Convert local to UTC (subtract offset)
                            sql.execute(f"""
                                UPDATE {table}
                                SET {column} = DATETIME({column}, '-{int(offset_hours)} hours', '-{int((offset_hours % 1) * 60)} minutes')
                                WHERE {column} IS NOT NULL
                            """)
                        elif offset_hours < 0:
                            # Convert local to UTC (add offset absolute value)
                            abs_hours = abs(int(offset_hours))
                            abs_mins = int((abs(offset_hours) % 1) * 60)
                            sql.execute(f"""
                                UPDATE {table}
                                SET {column} = DATETIME({column}, '+{abs_hours} hours', '+{abs_mins} minutes')
                                WHERE {column} IS NOT NULL
                            """)

                        row_count = sql.rowcount
                        if row_count > 0:
                            mylog("verbose", f"[db_upgrade] Migrated {row_count} timestamps in {table}.{column}")
                    except Exception as e:
                        mylog("warn", f"[db_upgrade] Error updating {table}.{column}: {e}")
                        continue

            except Exception as e:
                mylog("warn", f"[db_upgrade] Error processing table {table}: {e}")
                continue

        mylog("none", "[db_upgrade] ✓ UTC timestamp migration completed successfully")
        return True

    except Exception as e:
        mylog("none", f"[db_upgrade] ERROR during timestamp migration: {e}")
        return False
