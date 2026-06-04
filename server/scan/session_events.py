from scan.device_handling import (
    create_new_devices,
    print_scan_stats,
    save_scanned_devices,
    exclude_ignored_devices,
    update_devices_data_from_scan,
    update_sync_hub_node,
    update_vendors_from_mac,
    update_icons_and_types,
    update_devPresentLastScan_based_on_force_status,
    update_devPresentLastScan_based_on_nics,
    update_ipv4_ipv6,
    update_devLastConnection_from_CurrentScan,
    update_presence_from_CurrentScan
)
from helper import get_setting_value
from db.db_helper import print_table_schema
from utils.datetime_utils import timeNowUTC
from logger import mylog, Logger
from messaging.reporting import skip_repeated_notifications
from messaging.in_app import update_unread_notifications_count
from const import NULL_EQUIVALENTS_SQL

# Predicate used in every negative-event INSERT to skip forced-online devices.
# Centralised here so all three event paths stay in sync.
_SQL_NOT_FORCED_ONLINE = "LOWER(COALESCE(devForceStatus, '')) != 'online'"


# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

# ===============================================================================
# SCAN NETWORK
# ===============================================================================


def process_scan(db):
    # Apply exclusions
    mylog("verbose", "[Process Scan]  Exclude ignored devices")
    exclude_ignored_devices(db)

    # Load current scan data
    mylog("verbose", "[Process Scan]  Processing scan results")
    save_scanned_devices(db)

    db.commitDB()

    # Print stats
    mylog("none", "[Process Scan] Print Stats")
    print_scan_stats(db)
    mylog("none", "[Process Scan] Stats end")

    # Create Events
    mylog("verbose", "[Process Scan] Sessions Events (connect / disconnect)")
    insert_events(db)

    # Create New Devices
    # after create events -> avoid 'connection' event
    mylog("verbose", "[Process Scan] Creating new devices")
    create_new_devices(db)

    # Update devices info
    mylog("verbose", "[Process Scan] Updating Devices Info")
    update_devices_data_from_scan(db)

    # Backfill devSyncHubNode for devices where it is empty
    mylog("verbose", "[Process Scan] Updating Sync Hub Node")
    update_sync_hub_node(db)

    # Last Connection Time stamp from CurrentScan
    mylog("verbose", "[Process Scan] Updating devLastConnection from CurrentScan")
    update_devLastConnection_from_CurrentScan(db)

    # Presence from CurrentScan
    mylog("verbose", "[Process Scan] Updating Presence from CurrentScan")
    update_presence_from_CurrentScan(db)

    # Update devPresentLastScan based on NICs presence
    mylog("verbose", "[Process Scan] Updating NICs presence")
    update_devPresentLastScan_based_on_nics(db)

    # Force device status
    mylog("verbose", "[Process Scan] Updating forced presence")
    update_devPresentLastScan_based_on_force_status(db)

    # Update Vendors
    mylog("verbose", "[Process Scan] Updating Vendors")
    update_vendors_from_mac(db)

    # Update IPs
    mylog("verbose", "[Process Scan] Updating v4 and v6 IPs")
    update_ipv4_ipv6(db)

    # Update Icons and Type based on heuristics
    mylog("verbose", "[Process Scan] Guessing Icons")
    update_icons_and_types(db)

    # Pair session events (Connection / Disconnection)
    mylog("verbose", "[Process Scan] Pairing session events (connection / disconnection) ")
    pair_sessions_events(db)

    # Sessions snapshot
    mylog("verbose", "[Process Scan] Creating sessions snapshot")
    create_sessions_snapshot(db)

    # Sessions snapshot
    mylog("verbose", "[Process Scan] Inserting scan results into Online_History")
    insertOnlineHistory(db)

    # Skip repeated notifications
    mylog("verbose", "[Process Scan] Skipping repeated notifications")
    skip_repeated_notifications(db)

    # Clear current scan as processed
    # 🐛 CurrentScan DEBUG: comment out below when debugging to keep the CurrentScan table after restarts/scan finishes
    db.sql.execute("DELETE FROM CurrentScan")

    # re-broadcast unread notifiation count to update FE
    update_unread_notifications_count()

    # Commit changes
    db.commitDB()


# -------------------------------------------------------------------------------
def pair_sessions_events(db):
    sql = db.sql  # TO-DO
    # Pair Connection / New Device events

    mylog("debug", "[Pair Session] - 1 Connections / New Devices")
    sql.execute("""UPDATE Events
                    SET evePairEventRowid =
                       (SELECT ROWID
                        FROM Events AS EVE2
                        WHERE EVE2.eveEventType IN ('New Device', 'Connected', 'Down Reconnected',
                            'Device Down', 'Disconnected')
                           AND EVE2.eveMac = Events.eveMac
                           AND EVE2.eveDateTime > Events.eveDateTime
                        ORDER BY EVE2.eveDateTime ASC LIMIT 1)
                    WHERE eveEventType IN ('New Device', 'Connected', 'Down Reconnected')
                    AND evePairEventRowid IS NULL
                 """)

    # Pair Disconnection / Device Down
    mylog("debug", "[Pair Session] - 2 Disconnections")
    sql.execute("""UPDATE Events
                    SET evePairEventRowid =
                        (SELECT ROWID
                         FROM Events AS EVE2
                         WHERE EVE2.evePairEventRowid = Events.ROWID)
                    WHERE eveEventType IN ('Device Down', 'Disconnected')
                      AND evePairEventRowid IS NULL
                 """)

    mylog("debug", "[Pair Session] Pair session end")
    db.commitDB()


# -------------------------------------------------------------------------------
def create_sessions_snapshot(db):
    sql = db.sql  # TO-DO

    # Clean sessions snapshot
    mylog("debug", "[Sessions Snapshot] - 1 Clean")
    sql.execute("DELETE FROM SESSIONS")

    # Insert sessions
    mylog("debug", "[Sessions Snapshot] - 2 Insert")
    sql.execute("""INSERT INTO Sessions
                    SELECT * FROM Convert_Events_to_Sessions""")

    mylog("debug", "[Sessions Snapshot] Sessions end")
    db.commitDB()


# -------------------------------------------------------------------------------
def insert_events(db):
    sql = db.sql  # TO-DO
    startTime = timeNowUTC()

    # Check device down – non-sleeping devices (immediate on first absence)
    mylog("debug", "[Events] - 1a - Devices down (non-sleeping)")
    sql.execute(f"""INSERT OR IGNORE INTO Events  (eveMac, eveIp, eveDateTime,
                        eveEventType, eveAdditionalInfo,
                        evePendingAlertEmail)
                    SELECT devMac, devLastIP, '{startTime}', 'Device Down', '', 1
                    FROM DevicesView
                    WHERE devAlertDown != 0
                      AND devCanSleep = 0
                      AND devPresentLastScan = 1
                      AND {_SQL_NOT_FORCED_ONLINE}
                      AND NOT EXISTS (SELECT 1 FROM CurrentScan
                                      WHERE devMac = scanMac
                                         ) """)

    # Check device down – sleeping devices whose sleep window has expired
    mylog("debug", "[Events] - 1b - Devices down (sleep expired)")
    sql.execute(f"""INSERT OR IGNORE INTO Events  (eveMac, eveIp, eveDateTime,
                        eveEventType, eveAdditionalInfo,
                        evePendingAlertEmail)
                    SELECT devMac, devLastIP, '{startTime}', 'Device Down', '', 1
                    FROM DevicesView
                    WHERE devAlertDown != 0
                      AND devCanSleep = 1
                      AND devIsSleeping = 0
                      AND devPresentLastScan = 0
                      AND {_SQL_NOT_FORCED_ONLINE}
                      AND NOT EXISTS (SELECT 1 FROM CurrentScan
                                      WHERE devMac = scanMac)
                      AND NOT EXISTS (SELECT 1 FROM Events
                                      WHERE eveMac = devMac
                                        AND eveEventType = 'Device Down'
                                        AND eveDateTime >= devLastConnection
                                         ) """)

    # Check new Connections or Down Reconnections
    mylog("debug", "[Events] - 2 - New Connections")
    sql.execute(f"""    INSERT OR IGNORE INTO Events (eveMac, eveIp, eveDateTime,
                                            eveEventType, eveAdditionalInfo,
                                            evePendingAlertEmail)
                        SELECT DISTINCT c.scanMac, c.scanLastIP, '{startTime}',
                                        CASE
                                            WHEN last_event.eveEventType = 'Device Down' and  last_event.evePendingAlertEmail = 0 THEN 'Down Reconnected'
                                            ELSE 'Connected'
                                        END,
                                        '',
                                        1
                        FROM CurrentScan AS c
                        LEFT JOIN LatestEventsPerMAC AS last_event ON c.scanMac = last_event.eveMac
                        WHERE last_event.devPresentLastScan = 0 OR last_event.eveMac IS NULL
                        """)

    # Check disconnections
    mylog("debug", "[Events] - 3 - Disconnections")
    sql.execute(f"""INSERT OR IGNORE INTO Events (eveMac, eveIp, eveDateTime,
                        eveEventType, eveAdditionalInfo,
                        evePendingAlertEmail)
                    SELECT devMac, devLastIP, '{startTime}', 'Disconnected', '',
                        devAlertEvents
                    FROM Devices
                    WHERE devAlertDown = 0
                      AND devPresentLastScan = 1
                      AND {_SQL_NOT_FORCED_ONLINE}
                      AND NOT EXISTS (SELECT 1 FROM CurrentScan
                                      WHERE devMac = scanMac
                                         ) """)

    # Check IP Changed
    mylog("debug", "[Events] - 4 - IP Changes")
    sql.execute(f"""INSERT OR IGNORE INTO Events (eveMac, eveIp, eveDateTime,
                        eveEventType, eveAdditionalInfo,
                        evePendingAlertEmail)
                    SELECT scanMac, scanLastIP, '{startTime}', 'IP Changed',
                        'Previous IP: '|| devLastIP, devAlertEvents
                    FROM Devices, CurrentScan
                    WHERE devMac = scanMac
                      AND scanLastIP IS NOT NULL
                      AND scanLastIP NOT IN ({NULL_EQUIVALENTS_SQL})
                      AND scanLastIP <> COALESCE(devPrimaryIPv4, '')
                      AND scanLastIP <> COALESCE(devPrimaryIPv6, '')
                      AND scanLastIP <> COALESCE(devLastIP, '') """)
    mylog("debug", "[Events] - Events end")


# -------------------------------------------------------------------------------
def insertOnlineHistory(db):
    sql = db.sql  # TO-DO: Implement sql object

    scanTimestamp = timeNowUTC()

    # Query to fetch all relevant device counts in one go
    query = """
    SELECT
        COUNT(*) AS allDevices,
        COALESCE(SUM(CASE WHEN devIsArchived = 1 THEN 1 ELSE 0 END), 0) AS archivedDevices,
        COALESCE(SUM(CASE WHEN devPresentLastScan = 1 THEN 1 ELSE 0 END), 0) AS onlineDevices,
        COALESCE(SUM(CASE WHEN devPresentLastScan = 0 AND devAlertDown = 1 AND devIsSleeping = 0 THEN 1 ELSE 0 END), 0) AS downDevices
    FROM DevicesView
    """

    deviceCounts = db.read(query)[
        0
    ]  # Assuming db.read returns a list of rows, take the first (and only) row

    allDevices = deviceCounts["allDevices"]
    archivedDevices = deviceCounts["archivedDevices"]
    onlineDevices = deviceCounts["onlineDevices"]
    downDevices = deviceCounts["downDevices"]

    offlineDevices = allDevices - archivedDevices - onlineDevices

    # Prepare the insert query using parameterized inputs
    insert_query = """
        INSERT INTO Online_History (scanDate, onlineDevices, downDevices, allDevices, archivedDevices, offlineDevices)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    mylog("debug", f"[Presence graph] Sql query: {insert_query} with values: {scanTimestamp}, {onlineDevices}, {downDevices}, {allDevices}, {archivedDevices}, {offlineDevices}",)

    # Debug output
    print_table_schema(db, "Online_History")

    # Insert the gathered data into the history table
    sql.execute(
        insert_query,
        (
            scanTimestamp,
            onlineDevices,
            downDevices,
            allDevices,
            archivedDevices,
            offlineDevices,
        ),
    )

    db.commitDB()
