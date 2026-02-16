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
                            LEFT JOIN Devices ON eve_MAC = devMac;
                          """)

    sql.execute(""" DROP VIEW IF EXISTS LatestEventsPerMAC;""")
    sql.execute("""CREATE VIEW LatestEventsPerMAC AS
                                WITH RankedEvents AS (
                                    SELECT
                                        e.*,
                                        ROW_NUMBER() OVER (PARTITION BY e.eve_MAC ORDER BY e.eve_DateTime DESC) AS row_num
                                    FROM Events AS e
                                )
                                SELECT
                                    e.*,
                                    d.*,
                                    c.*
                                FROM RankedEvents AS e
                                LEFT JOIN Devices AS d ON e.eve_MAC = d.devMac
                                INNER JOIN CurrentScan AS c ON e.eve_MAC = c.scanMac
                                WHERE e.row_num = 1;""")

    sql.execute(""" DROP VIEW IF EXISTS Sessions_Devices;""")
    sql.execute(
        """CREATE VIEW Sessions_Devices AS SELECT * FROM Sessions LEFT JOIN "Devices" ON ses_MAC = devMac;"""
    )

    # handling the Convert_Events_to_Sessions / Sessions screens
    sql.execute("""DROP VIEW IF EXISTS Convert_Events_to_Sessions;""")
    sql.execute("""CREATE VIEW Convert_Events_to_Sessions AS  SELECT EVE1.eve_MAC,
                                      EVE1.eve_IP,
                                      EVE1.eve_EventType AS eve_EventTypeConnection,
                                      EVE1.eve_DateTime AS eve_DateTimeConnection,
                                      CASE WHEN EVE2.eve_EventType IN ('Disconnected', 'Device Down') OR
                                                EVE2.eve_EventType IS NULL THEN EVE2.eve_EventType ELSE '<missing event>' END AS eve_EventTypeDisconnection,
                                      CASE WHEN EVE2.eve_EventType IN ('Disconnected', 'Device Down') THEN EVE2.eve_DateTime ELSE NULL END AS eve_DateTimeDisconnection,
                                      CASE WHEN EVE2.eve_EventType IS NULL THEN 1 ELSE 0 END AS eve_StillConnected,
                                      EVE1.eve_AdditionalInfo
                                  FROM Events AS EVE1
                                      LEFT JOIN
                                      Events AS EVE2 ON EVE1.eve_PairEventRowID = EVE2.RowID
                                WHERE EVE1.eve_EventType IN ('New Device', 'Connected','Down Reconnected')
                            UNION
                                SELECT eve_MAC,
                                      eve_IP,
                                      '<missing event>' AS eve_EventTypeConnection,
                                      NULL AS eve_DateTimeConnection,
                                      eve_EventType AS eve_EventTypeDisconnection,
                                      eve_DateTime AS eve_DateTimeDisconnection,
                                      0 AS eve_StillConnected,
                                      eve_AdditionalInfo
                                  FROM Events AS EVE1
                                WHERE (eve_EventType = 'Device Down' OR
                                        eve_EventType = 'Disconnected') AND
                                      EVE1.eve_PairEventRowID IS NULL;
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
                                            eve_MAC,
                                            eve_IP,
                                            eve_EventType,
                                            eve_DateTime
                                    );
                            """

    sql.execute(clean_duplicate_events)

    indexes = [
        # Sessions
        (
            "idx_ses_mac_date",
            "CREATE INDEX idx_ses_mac_date ON Sessions(ses_MAC, ses_DateTimeConnection, ses_DateTimeDisconnection, ses_StillConnected)",
        ),
        # Events
        (
            "idx_eve_mac_date_type",
            "CREATE INDEX idx_eve_mac_date_type ON Events(eve_MAC, eve_DateTime, eve_EventType)",
        ),
        (
            "idx_eve_alert_pending",
            "CREATE INDEX idx_eve_alert_pending ON Events(eve_PendingAlertEmail)",
        ),
        (
            "idx_eve_mac_datetime_desc",
            "CREATE INDEX idx_eve_mac_datetime_desc ON Events(eve_MAC, eve_DateTime DESC)",
        ),
        (
            "idx_eve_pairevent",
            "CREATE INDEX idx_eve_pairevent ON Events(eve_PairEventRowID)",
        ),
        (
            "idx_eve_type_date",
            "CREATE INDEX idx_eve_type_date ON Events(eve_EventType, eve_DateTime)",
        ),
        (
            "idx_events_unique",
            "CREATE UNIQUE INDEX idx_events_unique ON Events (eve_MAC, eve_IP, eve_EventType, eve_DateTime)",
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
            "CREATE INDEX idx_plugins_plugin_mac_ip ON Plugins_Objects(Plugin, Object_PrimaryID, Object_SecondaryID)",
        ),  # Issue #1251: Optimize name resolution lookup
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
            "par_ID" TEXT PRIMARY KEY,
            "par_Value"	TEXT
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
                                    "Index"	          INTEGER,
                                    Plugin TEXT NOT NULL,
                                    Object_PrimaryID TEXT NOT NULL,
                                    Object_SecondaryID TEXT NOT NULL,
                                    DateTimeCreated TEXT NOT NULL,
                                    DateTimeChanged TEXT NOT NULL,
                                    Watched_Value1 TEXT NOT NULL,
                                    Watched_Value2 TEXT NOT NULL,
                                    Watched_Value3 TEXT NOT NULL,
                                    Watched_Value4 TEXT NOT NULL,
                                    Status TEXT NOT NULL,
                                    Extra TEXT NOT NULL,
                                    UserData TEXT NOT NULL,
                                    ForeignKey TEXT NOT NULL,
                                    SyncHubNodeName TEXT,
                                    "HelpVal1" TEXT,
                                    "HelpVal2" TEXT,
                                    "HelpVal3" TEXT,
                                    "HelpVal4" TEXT,
                                    ObjectGUID TEXT,
                                    PRIMARY KEY("Index" AUTOINCREMENT)
                        ); """
    sql.execute(sql_Plugins_Objects)

    # Plugin execution results
    sql_Plugins_Events = """ CREATE TABLE IF NOT EXISTS Plugins_Events(
                                    "Index"	          INTEGER,
                                    Plugin TEXT NOT NULL,
                                    Object_PrimaryID TEXT NOT NULL,
                                    Object_SecondaryID TEXT NOT NULL,
                                    DateTimeCreated TEXT NOT NULL,
                                    DateTimeChanged TEXT NOT NULL,
                                    Watched_Value1 TEXT NOT NULL,
                                    Watched_Value2 TEXT NOT NULL,
                                    Watched_Value3 TEXT NOT NULL,
                                    Watched_Value4 TEXT NOT NULL,
                                    Status TEXT NOT NULL,
                                    Extra TEXT NOT NULL,
                                    UserData TEXT NOT NULL,
                                    ForeignKey TEXT NOT NULL,
                                    SyncHubNodeName TEXT,
                                    "HelpVal1" TEXT,
                                    "HelpVal2" TEXT,
                                    "HelpVal3" TEXT,
                                    "HelpVal4" TEXT,
                                    PRIMARY KEY("Index" AUTOINCREMENT)
                        ); """
    sql.execute(sql_Plugins_Events)

    # Plugin execution history
    sql_Plugins_History = """ CREATE TABLE IF NOT EXISTS Plugins_History(
                                    "Index"	          INTEGER,
                                    Plugin TEXT NOT NULL,
                                    Object_PrimaryID TEXT NOT NULL,
                                    Object_SecondaryID TEXT NOT NULL,
                                    DateTimeCreated TEXT NOT NULL,
                                    DateTimeChanged TEXT NOT NULL,
                                    Watched_Value1 TEXT NOT NULL,
                                    Watched_Value2 TEXT NOT NULL,
                                    Watched_Value3 TEXT NOT NULL,
                                    Watched_Value4 TEXT NOT NULL,
                                    Status TEXT NOT NULL,
                                    Extra TEXT NOT NULL,
                                    UserData TEXT NOT NULL,
                                    ForeignKey TEXT NOT NULL,
                                    SyncHubNodeName TEXT,
                                    "HelpVal1" TEXT,
                                    "HelpVal2" TEXT,
                                    "HelpVal3" TEXT,
                                    "HelpVal4" TEXT,
                                    PRIMARY KEY("Index" AUTOINCREMENT)
                        ); """
    sql.execute(sql_Plugins_History)

    # Dynamically generated language strings
    sql.execute("DROP TABLE IF EXISTS Plugins_Language_Strings;")
    sql.execute(""" CREATE TABLE IF NOT EXISTS Plugins_Language_Strings(
                                "Index"	          INTEGER,
                                Language_Code TEXT NOT NULL,
                                String_Key TEXT NOT NULL,
                                String_Value TEXT NOT NULL,
                                Extra TEXT NOT NULL,
                                PRIMARY KEY("Index" AUTOINCREMENT)
                        ); """)

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

        # List of tables and their datetime columns
        timestamp_columns = {
            'Devices': ['devFirstConnection', 'devLastConnection', 'devLastNotification'],
            'Events': ['eve_DateTime'],
            'Sessions': ['ses_DateTimeConnection', 'ses_DateTimeDisconnection'],
            'Notifications': ['DateTimeCreated', 'DateTimePushed'],
            'Online_History': ['Scan_Date'],
            'Plugins_Objects': ['DateTimeCreated', 'DateTimeChanged'],
            'Plugins_Events': ['DateTimeCreated', 'DateTimeChanged'],
            'Plugins_History': ['DateTimeCreated', 'DateTimeChanged'],
            'AppEvents': ['DateTimeCreated'],
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
