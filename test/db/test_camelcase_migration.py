"""
Unit tests for migrate_to_camelcase() in db_upgrade.

Covers:
- Already-migrated schema (eveMac present) → skip, return True
- Unrecognised schema (neither eveMac nor eve_MAC) → skip, return True
- Legacy Events columns renamed to camelCase equivalents
- Legacy Sessions columns renamed to camelCase equivalents
- Legacy Online_History columns renamed to camelCase equivalents
- Legacy Plugins_Objects columns renamed to camelCase equivalents
- Legacy Plugins_Language_Strings columns renamed to camelCase equivalents
- Missing tables are silently skipped without error
- Existing row data is preserved through the column rename
- Views referencing old column names are dropped before ALTER TABLE runs
- Migration is idempotent (second call detects eveMac and returns early)
"""

import sys
import os
import sqlite3

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from db.db_upgrade import migrate_to_camelcase  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cursor():
    """Return an in-memory SQLite cursor and its parent connection."""
    conn = sqlite3.connect(":memory:")
    return conn.cursor(), conn


def _col_names(cursor, table):
    """Return the set of column names for a given table."""
    cursor.execute(f'PRAGMA table_info("{table}")')
    return {row[1] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Legacy DDL fixtures (pre-migration schema with old column names)
# ---------------------------------------------------------------------------

_LEGACY_EVENTS_DDL = """
    CREATE TABLE Events (
        eve_MAC TEXT NOT NULL,
        eve_IP TEXT NOT NULL,
        eve_DateTime DATETIME NOT NULL,
        eve_EventType TEXT NOT NULL,
        eve_AdditionalInfo TEXT DEFAULT '',
        eve_PendingAlertEmail INTEGER NOT NULL DEFAULT 1,
        eve_PairEventRowid INTEGER
    )
"""

_LEGACY_SESSIONS_DDL = """
    CREATE TABLE Sessions (
        ses_MAC TEXT,
        ses_IP TEXT,
        ses_EventTypeConnection TEXT,
        ses_DateTimeConnection DATETIME,
        ses_EventTypeDisconnection TEXT,
        ses_DateTimeDisconnection DATETIME,
        ses_StillConnected INTEGER,
        ses_AdditionalInfo TEXT
    )
"""

_LEGACY_ONLINE_HISTORY_DDL = """
    CREATE TABLE Online_History (
        "Index" INTEGER PRIMARY KEY AUTOINCREMENT,
        "Scan_Date" TEXT,
        "Online_Devices" INTEGER,
        "Down_Devices" INTEGER,
        "All_Devices" INTEGER,
        "Archived_Devices" INTEGER,
        "Offline_Devices" INTEGER
    )
"""

_LEGACY_PLUGINS_OBJECTS_DDL = """
    CREATE TABLE Plugins_Objects (
        "Index" INTEGER PRIMARY KEY AUTOINCREMENT,
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
        HelpVal1 TEXT,
        HelpVal2 TEXT,
        HelpVal3 TEXT,
        HelpVal4 TEXT,
        ObjectGUID TEXT
    )
"""

_LEGACY_PLUGINS_LANG_DDL = """
    CREATE TABLE Plugins_Language_Strings (
        "Index" INTEGER PRIMARY KEY AUTOINCREMENT,
        Language_Code TEXT NOT NULL,
        String_Key TEXT NOT NULL,
        String_Value TEXT NOT NULL,
        Extra TEXT NOT NULL
    )
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMigrateToCamelCase:

    def test_returns_true_if_already_camelcase(self):
        """DB already on camelCase schema → skip silently, return True."""
        cur, conn = _make_cursor()
        cur.execute("""
            CREATE TABLE Events (
                eveMac TEXT NOT NULL, eveIp TEXT NOT NULL,
                eveDateTime DATETIME NOT NULL, eveEventType TEXT NOT NULL,
                eveAdditionalInfo TEXT, evePendingAlertEmail INTEGER,
                evePairEventRowid INTEGER
            )
        """)
        conn.commit()

        result = migrate_to_camelcase(cur)

        assert result is True
        assert "eveMac" in _col_names(cur, "Events")

    def test_returns_true_if_unknown_schema(self):
        """Events exists but has neither eve_MAC nor eveMac → skip, return True."""
        cur, conn = _make_cursor()
        cur.execute("CREATE TABLE Events (someOtherCol TEXT)")
        conn.commit()

        result = migrate_to_camelcase(cur)

        assert result is True

    def test_events_legacy_columns_renamed(self):
        """All legacy eve_* columns are renamed to their camelCase equivalents."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        conn.commit()

        result = migrate_to_camelcase(cur)

        assert result is True
        cols = _col_names(cur, "Events")
        expected_new = {
            "eveMac", "eveIp", "eveDateTime", "eveEventType",
            "eveAdditionalInfo", "evePendingAlertEmail", "evePairEventRowid",
        }
        old_names = {
            "eve_MAC", "eve_IP", "eve_DateTime", "eve_EventType",
            "eve_AdditionalInfo", "eve_PendingAlertEmail", "eve_PairEventRowid",
        }
        assert expected_new.issubset(cols), f"Missing new columns: {expected_new - cols}"
        assert not old_names & cols, f"Old columns still present: {old_names & cols}"

    def test_sessions_legacy_columns_renamed(self):
        """All legacy ses_* columns are renamed to their camelCase equivalents."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        cur.execute(_LEGACY_SESSIONS_DDL)
        conn.commit()

        result = migrate_to_camelcase(cur)

        assert result is True
        cols = _col_names(cur, "Sessions")
        assert {
            "sesMac", "sesIp", "sesEventTypeConnection", "sesDateTimeConnection",
            "sesEventTypeDisconnection", "sesDateTimeDisconnection",
            "sesStillConnected", "sesAdditionalInfo",
        }.issubset(cols)
        assert not {"ses_MAC", "ses_IP", "ses_DateTimeConnection"} & cols

    def test_online_history_legacy_columns_renamed(self):
        """Quoted legacy Online_History column names are renamed to camelCase."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        cur.execute(_LEGACY_ONLINE_HISTORY_DDL)
        conn.commit()

        migrate_to_camelcase(cur)

        cols = _col_names(cur, "Online_History")
        assert {
            "scanDate", "onlineDevices", "downDevices",
            "allDevices", "archivedDevices", "offlineDevices",
        }.issubset(cols)
        assert not {"Scan_Date", "Online_Devices", "Down_Devices"} & cols

    def test_plugins_objects_legacy_columns_renamed(self):
        """All renamed Plugins_Objects columns receive their camelCase names."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        cur.execute(_LEGACY_PLUGINS_OBJECTS_DDL)
        conn.commit()

        migrate_to_camelcase(cur)

        cols = _col_names(cur, "Plugins_Objects")
        assert {
            "plugin", "objectPrimaryId", "objectSecondaryId",
            "dateTimeCreated", "dateTimeChanged",
            "watchedValue1", "watchedValue2", "watchedValue3", "watchedValue4",
            "status", "extra", "userData", "foreignKey", "syncHubNodeName",
            "helpVal1", "helpVal2", "helpVal3", "helpVal4", "objectGuid",
        }.issubset(cols)
        assert not {
            "Object_PrimaryID", "Watched_Value1", "ObjectGUID",
            "ForeignKey", "UserData", "Plugin",
        } & cols

    def test_plugins_language_strings_renamed(self):
        """Plugins_Language_Strings legacy column names are renamed to camelCase."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        cur.execute(_LEGACY_PLUGINS_LANG_DDL)
        conn.commit()

        migrate_to_camelcase(cur)

        cols = _col_names(cur, "Plugins_Language_Strings")
        assert {"languageCode", "stringKey", "stringValue", "extra"}.issubset(cols)
        assert not {"Language_Code", "String_Key", "String_Value"} & cols

    def test_missing_table_silently_skipped(self):
        """Tables in the migration map that don't exist are skipped without error."""
        cur, conn = _make_cursor()
        # Only Events (legacy) exists — all other mapped tables are absent
        cur.execute(_LEGACY_EVENTS_DDL)
        conn.commit()

        result = migrate_to_camelcase(cur)

        assert result is True
        assert "eveMac" in _col_names(cur, "Events")

    def test_data_preserved_after_rename(self):
        """Existing rows remain accessible under the new camelCase column names."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        cur.execute(
            "INSERT INTO Events (eve_MAC, eve_IP, eve_DateTime, eve_EventType) "
            "VALUES ('aa:bb:cc:dd:ee:ff', '192.168.1.1', '2025-01-01 12:00:00', 'Connected')"
        )
        conn.commit()

        migrate_to_camelcase(cur)

        cur.execute(
            "SELECT eveMac, eveIp, eveEventType FROM Events WHERE eveMac = 'aa:bb:cc:dd:ee:ff'"
        )
        row = cur.fetchone()
        assert row is not None, "Row missing after camelCase migration"
        assert row[0] == "aa:bb:cc:dd:ee:ff"
        assert row[1] == "192.168.1.1"
        assert row[2] == "Connected"

    def test_views_dropped_before_migration(self):
        """Views referencing old column names do not block ALTER TABLE RENAME COLUMN."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        # A view that references old column names would normally block the rename
        cur.execute("CREATE VIEW Events_Devices AS SELECT eve_MAC, eve_IP FROM Events")
        conn.commit()

        result = migrate_to_camelcase(cur)

        assert result is True
        assert "eveMac" in _col_names(cur, "Events")
        # View is dropped (ensure_views() is responsible for recreation separately)
        cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='Events_Devices'")
        assert cur.fetchone() is None

    def test_idempotent_second_run(self):
        """Running migration twice is safe — second call detects eveMac and exits early."""
        cur, conn = _make_cursor()
        cur.execute(_LEGACY_EVENTS_DDL)
        conn.commit()

        first = migrate_to_camelcase(cur)
        second = migrate_to_camelcase(cur)

        assert first is True
        assert second is True
        cols = _col_names(cur, "Events")
        assert "eveMac" in cols
        assert "eve_MAC" not in cols
