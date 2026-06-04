"""
Shared in-memory database factories and helpers for NetAlertX unit tests.

Import from any test subdirectory with:

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from db_test_helpers import make_db, insert_device, minutes_ago, DummyDB, down_event_macs, make_device_dict, sync_insert_devices
    from db_test_helpers import make_plugin_db, make_plugin_dict, make_plugin_event_row, seed_plugin_object, plugin_history_rows, plugin_objects_rows, PluginFakeDB
"""

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta

# Make the 'server' package importable when this module is loaded directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from db.db_upgrade import ensure_views  # noqa: E402


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

CREATE_DEVICES = """
    CREATE TABLE IF NOT EXISTS Devices (
        devMac                 TEXT PRIMARY KEY,
        devName                TEXT,
        devOwner               TEXT,
        devType                TEXT,
        devVendor              TEXT,
        devFavorite            INTEGER DEFAULT 0,
        devGroup               TEXT,
        devComments            TEXT,
        devFirstConnection     TEXT,
        devLastConnection      TEXT,
        devLastIP              TEXT,
        devPrimaryIPv4         TEXT,
        devPrimaryIPv6         TEXT,
        devVlan                TEXT,
        devForceStatus         TEXT,
        devStaticIP            TEXT,
        devScan                INTEGER DEFAULT 1,
        devLogEvents           INTEGER DEFAULT 1,
        devAlertEvents         INTEGER DEFAULT 1,
        devAlertDown           INTEGER,             -- intentionally nullable
        devCanSleep            INTEGER DEFAULT 0,
        devSkipRepeated        INTEGER DEFAULT 0,
        devLastNotification    TEXT,
        devPresentLastScan     INTEGER DEFAULT 0,
        devIsNew               INTEGER DEFAULT 0,
        devLocation            TEXT,
        devIsArchived          INTEGER DEFAULT 0,
        devParentMAC           TEXT,
        devParentPort          TEXT,
        devIcon                TEXT,
        devGUID                TEXT,
        devSite                TEXT,
        devSSID                TEXT,
        devSyncHubNode         TEXT,
        devSourcePlugin        TEXT,
        devCustomProps         TEXT,
        devFQDN                TEXT,
        devParentRelType       TEXT,
        devReqNicsOnline       INTEGER DEFAULT 0,
        devMacSource           TEXT,
        devNameSource          TEXT,
        devFQDNSource          TEXT,
        devLastIPSource        TEXT,
        devVendorSource        TEXT,
        devSSIDSource          TEXT,
        devParentMACSource     TEXT,
        devParentPortSource    TEXT,
        devParentRelTypeSource TEXT,
        devVlanSource          TEXT
    )
"""

# Includes evePairEventRowid — required by insert_events().
CREATE_EVENTS = """
    CREATE TABLE IF NOT EXISTS Events (
        eveMac               TEXT,
        eveIp                TEXT,
        eveDateTime          TEXT,
        eveEventType         TEXT,
        eveAdditionalInfo    TEXT,
        evePendingAlertEmail INTEGER,
        evePairEventRowid    INTEGER
    )
"""

CREATE_CURRENT_SCAN = """
    CREATE TABLE IF NOT EXISTS CurrentScan (
        scanMac            TEXT,
        scanLastIP         TEXT,
        scanVendor         TEXT,
        scanSourcePlugin   TEXT,
        scanName           TEXT,
        scanLastQuery      TEXT,
        scanLastConnection TEXT,
        scanSyncHubNode    TEXT,
        scanSite           TEXT,
        scanSSID           TEXT,
        scanParentMAC      TEXT,
        scanParentPort     TEXT,
        scanType           TEXT
    )
"""

CREATE_SETTINGS = """
    CREATE TABLE IF NOT EXISTS Settings (
        setKey   TEXT PRIMARY KEY,
        setValue TEXT
    )
"""


# ---------------------------------------------------------------------------
# DB factory
# ---------------------------------------------------------------------------

def make_db(sleep_minutes: int = 30) -> sqlite3.Connection:
    """
    Return a fully seeded in-memory SQLite connection with DevicesView built.

    Builds all required tables (Devices, Events, CurrentScan, Settings) and
    calls ensure_views() so DevicesView is immediately queryable.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(CREATE_DEVICES)
    cur.execute(CREATE_EVENTS)
    cur.execute(CREATE_CURRENT_SCAN)
    cur.execute(CREATE_SETTINGS)
    cur.execute(
        "INSERT OR REPLACE INTO Settings (setKey, setValue) VALUES (?, ?)",
        ("NTFPRCS_sleep_time", str(sleep_minutes)),
    )
    conn.commit()
    ensure_views(cur)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def minutes_ago(n: int) -> str:
    """Return a UTC timestamp string for *n* minutes ago."""
    dt = datetime.now(timezone.utc) - timedelta(minutes=n)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def now_utc() -> str:
    """Return the current UTC timestamp as a string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Device row factory
# ---------------------------------------------------------------------------

def insert_device(
    cur,
    mac: str,
    *,
    alert_down,
    present_last_scan: int = 0,
    can_sleep: int = 0,
    last_connection: str | None = None,
    last_ip: str = "192.168.1.1",
    force_status: str | None = None,
) -> None:
    """
    Insert a minimal Devices row.

    Parameters
    ----------
    alert_down:
        Value for devAlertDown. Pass ``None`` to store SQL NULL (tests the
        IFNULL coercion regression), ``0`` for disabled, ``1`` for enabled.
    present_last_scan:
        ``1`` = device was seen last scan (about to go down transition).
        ``0`` = device was already absent last scan.
    can_sleep:
        ``1`` enables the sleeping window for this device.
    last_connection:
        ISO-8601 UTC string; defaults to 60 minutes ago when omitted.
    last_ip:
        Value stored in devLastIP.
    force_status:
        Value for devForceStatus (``'online'``, ``'offline'``, or ``None``/
        ``'dont_force'``).
    """
    cur.execute(
        """
        INSERT INTO Devices
            (devMac, devAlertDown, devPresentLastScan, devCanSleep,
             devLastConnection, devLastIP, devIsArchived, devIsNew, devForceStatus)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)
        """,
        (mac, alert_down, present_last_scan, can_sleep,
         last_connection or minutes_ago(60), last_ip, force_status),
    )


def make_device_dict(mac: str = "aa:bb:cc:dd:ee:ff", **overrides) -> dict:
    """
    Return a fully-populated Devices row dict with safe defaults.

    Mirrors every column in CREATE_DEVICES so callers can be inserted
    directly via sync_insert_devices() or similar helpers.  Pass keyword
    arguments to override any individual field.

    Computed/view-only columns (devStatus, devIsSleeping, devFlapping,
    rowid, …) are intentionally absent — tests that need to verify they are
    dropped should add them after calling this function.
    """
    base = {
        "devMac":                 mac,
        "devName":                "Test Device",
        "devOwner":               "",
        "devType":                "",
        "devVendor":              "Acme",
        "devFavorite":            0,
        "devGroup":               "",
        "devComments":            "",
        "devFirstConnection":     "2024-01-01 00:00:00",
        "devLastConnection":      "2024-01-02 00:00:00",
        "devLastIP":              "192.168.1.10",
        "devPrimaryIPv4":         "192.168.1.10",
        "devPrimaryIPv6":         "",
        "devVlan":                "",
        "devForceStatus":         "",
        "devStaticIP":            "",
        "devScan":                1,
        "devLogEvents":           1,
        "devAlertEvents":         1,
        "devAlertDown":           1,
        "devCanSleep":            0,
        "devSkipRepeated":        0,
        "devLastNotification":    "",
        "devPresentLastScan":     1,
        "devIsNew":               0,
        "devLocation":            "",
        "devIsArchived":          0,
        "devParentMAC":           "",
        "devParentPort":          "",
        "devIcon":                "",
        "devGUID":                "test-guid-1",
        "devSite":                "",
        "devSSID":                "",
        "devSyncHubNode":         "node1",
        "devSourcePlugin":        "",
        "devCustomProps":         "",
        "devFQDN":                "",
        "devParentRelType":       "",
        "devReqNicsOnline":       0,
        "devMacSource":           "",
        "devNameSource":          "",
        "devFQDNSource":          "",
        "devLastIPSource":        "",
        "devVendorSource":        "",
        "devSSIDSource":          "",
        "devParentMACSource":     "",
        "devParentPortSource":    "",
        "devParentRelTypeSource": "",
        "devVlanSource":          "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Sync insert helper (shared by test/plugins/test_sync_insert.py and
# test/plugins/test_sync_protocol.py — mirrors sync.py's insert block)
# ---------------------------------------------------------------------------

def sync_insert_devices(
    conn: sqlite3.Connection,
    device_data: list,
    existing_macs: set | None = None,
    behavior: str = "copy-new",
) -> int:
    """
    Schema-aware device write mirroring sync.py's Mode-3 SYNC_BEHAVIOR block.

    Parameters
    ----------
    conn:
        In-memory (or real) SQLite connection with Devices and Events tables.
    device_data:
        List of device dicts as received from table_devices.json or a node log.
    existing_macs:
        Set of MAC addresses already present in Devices.  Used to compute
        genuinely new MACs for the Events INSERT and (for ``copy-new``) to
        filter write candidates.  Pass ``None`` to treat every device as new.
    behavior:
        One of ``"copy-new"`` (default), ``"carbon-copy"``, or
        ``"hub-defaults"``.

        ``copy-new``    — INSERT OR IGNORE for new MACs only (current default).
        ``carbon-copy`` — UPSERT (INSERT … ON CONFLICT DO UPDATE) for all MACs.
        ``hub-defaults``— skip write entirely; hub pipeline handles new devices
                          and their Events rows.

    Returns the number of device rows written (0 for ``hub-defaults``).
    Side-effect: inserts an Events row with eveEventType='New Device' for each
    genuinely new MAC when behavior is ``copy-new`` or ``carbon-copy``.
    """
    if not device_data or behavior == "hub-defaults":
        return 0

    cursor = conn.cursor()

    # Genuinely new MACs — drives the Events INSERT for both non-hub-defaults modes.
    new_devices = (
        [d for d in device_data if d["devMac"] not in existing_macs]
        if existing_macs is not None
        else list(device_data)
    )

    # Fire "New Device" events before the Devices INSERT pre-seeds the table.
    if new_devices:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor.executemany(
            """INSERT OR IGNORE INTO Events
               (eveMac, eveIp, eveDateTime, eveEventType, eveAdditionalInfo, evePendingAlertEmail)
               VALUES (?, ?, ?, 'New Device', ?, 1)""",
            [(d["devMac"], d.get("devLastIP", ""), now, d.get("devVendor", ""))
             for d in new_devices],
        )

    if behavior == "copy-new":
        candidates = new_devices
    else:  # carbon-copy — process all devices
        candidates = list(device_data)

    if not candidates:
        conn.commit()
        return 0

    cursor.execute("PRAGMA table_info(Devices)")
    db_columns = {row[1] for row in cursor.fetchall()}

    insert_cols  = [k for k in candidates[0].keys() if k in db_columns]
    columns      = ", ".join(insert_cols)
    placeholders = ", ".join("?" for _ in insert_cols)

    if behavior == "carbon-copy":
        _CARBON_COPY_SKIP = {"devMac", "devPresentLastScan"}
        update_cols   = [col for col in insert_cols if col not in _CARBON_COPY_SKIP]
        update_clause = ", ".join(f"{col}=excluded.{col}" for col in update_cols)
        sql = (
            f"INSERT INTO Devices ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(devMac) DO UPDATE SET {update_clause}"
        )
    else:
        sql = f"INSERT OR IGNORE INTO Devices ({columns}) VALUES ({placeholders})"

    values = [tuple(d.get(col) for col in insert_cols) for d in candidates]
    cursor.executemany(sql, values)
    conn.commit()
    return len(values)


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def down_event_macs(cur) -> set:
    """Return the set of MACs that have a 'Device Down' event row (lowercased)."""
    cur.execute("SELECT eveMac FROM Events WHERE eveEventType = 'Device Down'")
    return {r["eveMac"].lower() for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# DummyDB — minimal wrapper used by scan.session_events helpers
# ---------------------------------------------------------------------------

class DummyDB:
    """
    Minimal DB wrapper that satisfies the interface expected by
    ``session_events.insert_events()`` and related helpers.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.sql = conn.cursor()
        self._conn = conn

    def commitDB(self) -> None:
        self._conn.commit()


# ---------------------------------------------------------------------------
# Plugin tables DDL & helpers  (used by test/server/test_plugin_history_filtering.py)
# ---------------------------------------------------------------------------

CREATE_PLUGINS_OBJECTS = """
CREATE TABLE IF NOT EXISTS Plugins_Objects(
    "index"           INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin            TEXT NOT NULL,
    objectPrimaryId   TEXT NOT NULL,
    objectSecondaryId TEXT NOT NULL,
    dateTimeCreated   TEXT NOT NULL,
    dateTimeChanged   TEXT NOT NULL,
    watchedValue1     TEXT NOT NULL,
    watchedValue2     TEXT NOT NULL,
    watchedValue3     TEXT NOT NULL,
    watchedValue4     TEXT NOT NULL,
    "status"          TEXT NOT NULL,
    extra             TEXT NOT NULL,
    userData          TEXT NOT NULL,
    foreignKey        TEXT NOT NULL,
    syncHubNodeName   TEXT,
    helpVal1          TEXT,
    helpVal2          TEXT,
    helpVal3          TEXT,
    helpVal4          TEXT,
    objectGuid        TEXT
);
"""

CREATE_PLUGINS_EVENTS = """
CREATE TABLE IF NOT EXISTS Plugins_Events(
    "index"           INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin            TEXT NOT NULL,
    objectPrimaryId   TEXT NOT NULL,
    objectSecondaryId TEXT NOT NULL,
    dateTimeCreated   TEXT NOT NULL,
    dateTimeChanged   TEXT NOT NULL,
    watchedValue1     TEXT NOT NULL,
    watchedValue2     TEXT NOT NULL,
    watchedValue3     TEXT NOT NULL,
    watchedValue4     TEXT NOT NULL,
    "status"          TEXT NOT NULL,
    extra             TEXT NOT NULL,
    userData          TEXT NOT NULL,
    foreignKey        TEXT NOT NULL,
    syncHubNodeName   TEXT,
    helpVal1          TEXT,
    helpVal2          TEXT,
    helpVal3          TEXT,
    helpVal4          TEXT,
    objectGuid        TEXT
);
"""

CREATE_PLUGINS_HISTORY = """
CREATE TABLE IF NOT EXISTS Plugins_History(
    "index"           INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin            TEXT NOT NULL,
    objectPrimaryId   TEXT NOT NULL,
    objectSecondaryId TEXT NOT NULL,
    dateTimeCreated   TEXT NOT NULL,
    dateTimeChanged   TEXT NOT NULL,
    watchedValue1     TEXT NOT NULL,
    watchedValue2     TEXT NOT NULL,
    watchedValue3     TEXT NOT NULL,
    watchedValue4     TEXT NOT NULL,
    "status"          TEXT NOT NULL,
    extra             TEXT NOT NULL,
    userData          TEXT NOT NULL,
    foreignKey        TEXT NOT NULL,
    syncHubNodeName   TEXT,
    helpVal1          TEXT,
    helpVal2          TEXT,
    helpVal3          TEXT,
    helpVal4          TEXT,
    objectGuid        TEXT
);
"""


class PluginFakeSQL:
    """Wraps a sqlite3.Cursor to provide the interface plugin.py expects."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        if params:
            return self._cursor.execute(sql, params)
        return self._cursor.execute(sql)

    def executemany(self, sql, params_list):
        return self._cursor.executemany(sql, params_list)


class PluginFakeDB:
    """Minimal DB facade expected by process_plugin_events."""
    def __init__(self, conn):
        self.sql_connection = conn
        self.sql = PluginFakeSQL(conn.cursor())

    def get_sql_array(self, query):
        cur = self.sql_connection.cursor()
        cur.execute(query)
        return cur.fetchall()

    def commitDB(self):
        self.sql_connection.commit()


def make_plugin_db() -> tuple:
    """
    Return a (PluginFakeDB, connection) backed by an in-memory SQLite
    database with all three plugin tables created.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        CREATE_PLUGINS_OBJECTS + CREATE_PLUGINS_EVENTS + CREATE_PLUGINS_HISTORY
    )
    conn.commit()
    db = PluginFakeDB(conn)
    return db, conn


def make_plugin_dict(prefix: str, watched_columns=None) -> dict:
    """Return a minimal plugin dict compatible with process_plugin_events."""
    return {
        "unique_prefix": prefix,
        "settings": [
            {
                "function": "WATCH",
                "value": watched_columns or ["watchedValue1"],
            },
        ],
    }


def make_plugin_event_row(prefix: str, primary_id: str, secondary_id="sec",
                          watched1="val1", watched2="", watched3="",
                          watched4="", changed="2026-01-01 00:00:00",
                          extra="", user_data="", foreign_key="",
                          status="not-processed"):
    """Build a tuple mimicking a raw plugin output row (19 columns + index)."""
    return (
        0,              # index (placeholder, not used for events)
        prefix,         # plugin
        primary_id,
        secondary_id,
        changed,        # dateTimeCreated
        changed,        # dateTimeChanged
        watched1,
        watched2,
        watched3,
        watched4,
        status,
        extra,
        user_data,
        foreign_key,
        None,           # syncHubNodeName
        None,           # helpVal1
        None,           # helpVal2
        None,           # helpVal3
        None,           # helpVal4
    )


def seed_plugin_object(cur, prefix: str, primary_id: str,
                       secondary_id="sec", watched1="val1",
                       status="watched-not-changed",
                       changed="2026-01-01 00:00:00"):
    """Insert a row into Plugins_Objects to simulate a pre-existing object."""
    cur.execute(
        """INSERT INTO Plugins_Objects
           (plugin, objectPrimaryId, objectSecondaryId, dateTimeCreated,
            dateTimeChanged, watchedValue1, watchedValue2, watchedValue3,
            watchedValue4, status, extra, userData, foreignKey)
           VALUES (?, ?, ?, ?, ?, ?, '', '', '', ?, '', '', '')""",
        (prefix, primary_id, secondary_id, changed, changed, watched1, status),
    )


def plugin_history_rows(conn, prefix: str):
    """Return all Plugins_History rows for a given plugin prefix."""
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM Plugins_History WHERE plugin = ?", (prefix,)
    )
    return cur.fetchall()


def plugin_objects_rows(conn, prefix: str):
    """Return all Plugins_Objects rows for a given plugin prefix."""
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM Plugins_Objects WHERE plugin = ?", (prefix,)
    )
    return cur.fetchall()
