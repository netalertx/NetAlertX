from scan.device_handling import (
    create_new_devices,
    print_scan_stats,
    save_own_device,
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
from scan.presence import current_scan_presence_condition, nic_derived_presence_condition
from db.db_helper import print_table_schema
from db.plugin_field_views import get_plugin_columns_for_field
from utils.datetime_utils import timeNowUTC
from logger import mylog, Logger
from messaging.reporting import skip_repeated_notifications
from messaging.in_app import update_unread_notifications_count
from const import NULL_EQUIVALENTS_SQL

# Predicate used in every negative-event INSERT to skip forced-online devices.
# Centralised here so all three event paths stay in sync.
_SQL_NOT_FORCED_ONLINE = "LOWER(COALESCE(devForceStatus, '')) != 'online'"


def _connect_event_type_case(event_type_expr, pending_expr):
    """SQL CASE fragment shared by every insert_events() query that decides
    Connected vs. Down Reconnected: 'Down Reconnected' iff the referenced
    prior event was an unacknowledged Device Down, else 'Connected'.

    event_type_expr/pending_expr are trusted, hardcoded SQL expressions (a
    column reference or a scalar subquery) evaluating to the prior event's
    eveEventType/evePendingAlertEmail - same trust-boundary contract as
    current_scan_presence_condition()'s mac_column, not parameterized SQL.
    Centralised here (like _SQL_NOT_FORCED_ONLINE above) so every connect-
    side query classifies a reconnect the same way.
    """
    return f"""CASE
                    WHEN {event_type_expr} = 'Device Down' AND {pending_expr} = 0 THEN 'Down Reconnected'
                    ELSE 'Connected'
                END"""


def _known_plugin_ip_addresses_sql(all_plugins):
    """Build a SQL derived-table body (scanMac, knownAddr) unioning every
    (plugin, column_role) pair get_plugin_columns_for_field() names for the
    'ip' field - the Plugins_Objects-derived half of insert_events()'s IP
    Changed query's additive "known" test. An address already reported (and
    not missing-in-last-scan) by any
    eligible plugin for a MAC counts as known, on top of the existing
    devPrimaryIPv4/devPrimaryIPv6/devLastIP three-slot check - never instead
    of it, so a device whose only contributing plugins can't participate
    (dockerdisc, wificanary) gets an always-empty set here and the overall
    check reduces to exactly today's three-slot behavior.

    Returns None when all_plugins has no eligible plugin, so the caller can
    omit the NOT EXISTS clause entirely rather than build a degenerate query.

    A plugin's unique_prefix is a trusted config.json value (read at
    installation/reload time, not request time) and column is always one of
    plugin_field_views._PLUGINS_OBJECTS_COLUMN_ROLES' fixed literals - both
    interpolated here the same way startTime already is elsewhere in this
    file, not user input requiring parameterization.
    """
    pairs = get_plugin_columns_for_field(all_plugins or [], "ip")
    if not pairs:
        return None
    return " UNION ALL ".join(
        f"""SELECT objectPrimaryId AS scanMac, {column} AS knownAddr
            FROM Plugins_Objects
            WHERE plugin = '{plugin}'
              AND status != 'missing-in-last-scan'
              AND {column} IS NOT NULL"""
        for plugin, column in pairs
    )


# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

# ===============================================================================
# SCAN NETWORK
# ===============================================================================


def process_scan(db, all_plugins=None):

    # Save own device data into CurrentScan TODO:move potentially into a separate plugin
    mylog("verbose", "[Process Scan]  Processing scan results")
    save_own_device(db)

    # Apply exclusions
    mylog("verbose", "[Process Scan]  Exclude ignored devices")
    exclude_ignored_devices(db)

    db.commitDB()

    # Print stats
    mylog("none", "[Process Scan] Print Stats")
    print_scan_stats(db)
    mylog("none", "[Process Scan] Stats end")

    # Create Events
    mylog("verbose", "[Process Scan] Sessions Events (connect / disconnect)")
    insert_events(db, all_plugins)

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
def insert_events(db, all_plugins=None):
    """Insert this cycle's Device Down/New Connections/Disconnected/IP Changed
    Events rows. all_plugins (every plugin's parsed config.json) is optional
    and defaults to None/empty - the IP Changed query's Plugins_Objects-
    derived "known address" half is then skipped entirely, matching today's
    three-slot-only behavior exactly."""
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
                      AND NOT ({current_scan_presence_condition("devMac")}
                               OR {nic_derived_presence_condition("DevicesView.devMac")}) """)

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
                      AND NOT ({current_scan_presence_condition("devMac")}
                               OR {nic_derived_presence_condition("DevicesView.devMac")})
                      AND NOT EXISTS (SELECT 1 FROM Events
                                      WHERE eveMac = devMac
                                        AND eveEventType = 'Device Down'
                                        AND eveDateTime >= devLastConnection
                                         ) """)

    # Check new Connections or Down Reconnections
    mylog("debug", "[Events] - 2 - New Connections")
    # Two separate per-MAC aggregates, deliberately not one:
    # - present_agg: scanPresence = 1 rows only. Gates whether this MAC
    #   counts as "just connected" (abstain, not override - a sibling
    #   non-presence row never blocks it), and MIN() picks one deterministic
    #   scanLastIP so two plugins reporting different IPs for one MAC don't
    #   each insert their own Connected event.
    # - quiet_agg: unrestricted by scanPresence on purpose - a plugin's quiet
    #   preference counts even from a row that isn't the one asserting
    #   presence (most-restrictive-wins is a separate axis from presence).
    # This runs before create_new_devices(), so a legitimately new device
    # (scanCreatesDevice=1 this cycle) has no Devices row yet either - the
    # final WHERE clause treats "will be created this cycle" the same as
    # "already exists" rather than requiring a Devices row, or a
    # scanCreatesDevice=0-only MAC would suppress the mainline case too.
    sql.execute(f"""    INSERT OR IGNORE INTO Events (eveMac, eveIp, eveDateTime,
                                            eveEventType, eveAdditionalInfo,
                                            evePendingAlertEmail)
                        SELECT present_agg.scanMac, present_agg.scanLastIP, '{startTime}',
                                        {_connect_event_type_case("last_event.eveEventType", "last_event.evePendingAlertEmail")},
                                        '',
                                        CASE WHEN quiet_agg.scanQuiet = 1 THEN 0 ELSE 1 END
                        FROM (
                            SELECT scanMac, MIN(scanLastIP) AS scanLastIP
                            FROM CurrentScan
                            WHERE scanPresence = 1
                            GROUP BY scanMac
                        ) present_agg
                        JOIN (
                            SELECT scanMac,
                                   MAX(CASE WHEN scanNotificationMode = 'quiet' THEN 1 ELSE 0 END) AS scanQuiet,
                                   MAX(scanCreatesDevice) AS scanCreates
                            FROM CurrentScan
                            GROUP BY scanMac
                        ) quiet_agg ON quiet_agg.scanMac = present_agg.scanMac
                        LEFT JOIN LatestEventsPerMAC AS last_event ON present_agg.scanMac = last_event.eveMac
                        WHERE (last_event.devPresentLastScan = 0 OR last_event.eveMac IS NULL)
                          AND (
                                quiet_agg.scanCreates = 1
                                OR EXISTS (SELECT 1 FROM Devices WHERE devMac = present_agg.scanMac)
                              )
                        """)

    # NIC-derived New Connections/Down Reconnected: fires for a parent with
    # no CurrentScan row of its own but whose NIC children satisfy
    # nic_derived_presence_condition(). Reads Events directly instead of
    # LatestEventsPerMAC, which INNER JOINs CurrentScan and would silently
    # return no row for every MAC this query targets.
    mylog("debug", "[Events] - 2b - NIC-derived New Connections")
    # ROWID DESC breaks eveDateTime ties (timeNowUTC() truncates to whole
    # seconds) so both subqueries resolve to the same row.
    _last_event_type = """(SELECT eveEventType FROM Events
                            WHERE eveMac = nic_parent.devMac
                            ORDER BY eveDateTime DESC, ROWID DESC LIMIT 1)"""
    _last_event_pending = """(SELECT evePendingAlertEmail FROM Events
                               WHERE eveMac = nic_parent.devMac
                               ORDER BY eveDateTime DESC, ROWID DESC LIMIT 1)"""
    sql.execute(f"""INSERT OR IGNORE INTO Events (eveMac, eveIp, eveDateTime,
                        eveEventType, eveAdditionalInfo, evePendingAlertEmail)
                    SELECT nic_parent.devMac, nic_parent.devLastIP, '{startTime}',
                        {_connect_event_type_case(_last_event_type, _last_event_pending)},
                        '',
                        CASE WHEN EXISTS (
                            SELECT 1 FROM Devices AS nic
                            WHERE nic.devParentMAC = nic_parent.devMac
                              AND nic.devParentRelType = 'nic'
                              AND {current_scan_presence_condition("nic.devMac")}
                              AND EXISTS (SELECT 1 FROM CurrentScan AS quiet_scan
                                          WHERE quiet_scan.scanMac = nic.devMac
                                            AND quiet_scan.scanNotificationMode = 'quiet')
                        ) THEN 0 ELSE 1 END
                    FROM Devices AS nic_parent
                    WHERE IFNULL(nic_parent.devParentRelType, '') != 'nic'
                      AND nic_parent.devPresentLastScan = 0
                      AND NOT {current_scan_presence_condition("nic_parent.devMac")}
                      AND {nic_derived_presence_condition("nic_parent.devMac")}
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
                      AND NOT ({current_scan_presence_condition("devMac")}
                               OR {nic_derived_presence_condition("Devices.devMac")}) """)

    # Check IP Changed
    mylog("debug", "[Events] - 4 - IP Changes")
    # Unlike Device Down/Disconnected (which fire on row *absence*), IP
    # Changed fires from a present row, so quiet is consulted additively here:
    # suppress if EITHER the live aggregate says quiet OR devAlertEvents is
    # off. Same quiet_agg split as the New Connections query above.
    #
    # Per-address evaluation, not a single MIN()-reduced candidate: a device
    # with two simultaneously present, already-known addresses in one family
    # must not have only the
    # MIN()'d one tested against the three-slot check - that's exactly how a
    # known address can still fail every comparison and fire a false event.
    # Every distinct present address is instead judged on its own membership
    # in known(), additive over today's three-slot check with the
    # Plugins_Objects-derived set below (empty, hence a no-op, for a device
    # whose only contributing plugins can't participate - dockerdisc,
    # wificanary). Addresses that fail known() are aggregated into exactly
    # one Events row per MAC per cycle (today's shape), listing every one of
    # them in eveAdditionalInfo rather than multiplying event/notification
    # volume with one row per address.
    known_plugin_ips_sql = _known_plugin_ip_addresses_sql(all_plugins)
    known_plugin_ips_clause = (
        f"""AND NOT EXISTS (
                SELECT 1 FROM ({known_plugin_ips_sql}) known_plugin_ips
                WHERE known_plugin_ips.scanMac = present_addrs.scanMac
                  AND known_plugin_ips.knownAddr = present_addrs.scanLastIP
            )"""
        if known_plugin_ips_sql else ""
    )
    sql.execute(f"""INSERT OR IGNORE INTO Events (eveMac, eveIp, eveDateTime,
                        eveEventType, eveAdditionalInfo,
                        evePendingAlertEmail)
                    WITH present_addrs AS (
                        SELECT DISTINCT scanMac, scanLastIP
                        FROM CurrentScan
                        WHERE scanPresence = 1
                          AND scanLastIP IS NOT NULL
                          AND scanLastIP NOT IN ({NULL_EQUIVALENTS_SQL})
                    ),
                    quiet_agg AS (
                        SELECT scanMac,
                               MAX(CASE WHEN scanNotificationMode = 'quiet' THEN 1 ELSE 0 END) AS scanQuiet
                        FROM CurrentScan
                        GROUP BY scanMac
                    ),
                    new_addrs AS (
                        SELECT present_addrs.scanMac, present_addrs.scanLastIP
                        FROM present_addrs
                        JOIN Devices ON Devices.devMac = present_addrs.scanMac
                        WHERE present_addrs.scanLastIP <> COALESCE(Devices.devPrimaryIPv4, '')
                          AND present_addrs.scanLastIP <> COALESCE(Devices.devPrimaryIPv6, '')
                          AND present_addrs.scanLastIP <> COALESCE(Devices.devLastIP, '')
                          {known_plugin_ips_clause}
                    ),
                    new_addrs_agg AS (
                        SELECT scanMac,
                               MIN(scanLastIP) AS firstNewIP,
                               GROUP_CONCAT(scanLastIP, ', ') AS allNewIPs
                        FROM new_addrs
                        GROUP BY scanMac
                    )
                    SELECT new_addrs_agg.scanMac, new_addrs_agg.firstNewIP, '{startTime}', 'IP Changed',
                        'Previous IP: ' || Devices.devLastIP || ' | New IP(s): ' || new_addrs_agg.allNewIPs,
                        CASE WHEN quiet_agg.scanQuiet = 1 THEN 0 ELSE Devices.devAlertEvents END
                    FROM new_addrs_agg
                    JOIN Devices ON Devices.devMac = new_addrs_agg.scanMac
                    JOIN quiet_agg ON quiet_agg.scanMac = new_addrs_agg.scanMac
                    """)
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
