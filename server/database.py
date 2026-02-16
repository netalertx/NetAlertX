"""all things database to support NetAlertX"""

import sqlite3

# Register NetAlertX modules
from const import fullDbPath, sql_devices_stats, sql_devices_all

from logger import mylog
from db.db_helper import get_table_json, json_obj
from workflows.app_events import AppEvent_obj
from db.db_upgrade import (
    ensure_column,
    ensure_views,
    ensure_CurrentScan,
    ensure_plugins_tables,
    ensure_Parameters,
    ensure_Settings,
    ensure_Indexes,
    ensure_mac_lowercase_triggers,
    migrate_timestamps_to_utc,
)


class DB:
    """
    DB Class to provide the basic database interactions.
    Open / Commit / Close / read / write
    """

    def __init__(self):
        """
        Initializes the class instance by setting up placeholders for the
        SQL engine and SQL connection.

        Attributes:
            sql: Placeholder for the SQL engine or session object.
            sql_connection: Placeholder for the SQL database connection.
        """
        self.sql = None
        self.sql_connection = None

    def open(self):
        """
        Opens a connection to the SQLite database if it is not already open.
        This method initializes the database connection and cursor, and sets
        several SQLite PRAGMA options to optimize performance and reliability:
        - Enables Write-Ahead Logging (WAL) mode.
        - Sets synchronous mode to NORMAL for a balance between
          performance and safety.
        - Stores temporary tables and indices in memory.
        If the database is already open, the method logs a debug message
        and returns.
        If an error occurs during connection, it logs the error
        with minimal verbosity.
        Raises:
            sqlite3.Error: If there is an error opening the database.
        """
        # Check if DB is open
        if self.sql_connection is not None:
            mylog("debug", ["[Database] - open: DB already open"])
            return

        mylog("verbose", "[Database] Opening DB")
        # Open DB and Cursor
        try:
            self.sql_connection = sqlite3.connect(fullDbPath, isolation_level=None)

            # The WAL journaling mode uses a write-ahead log instead of a
            # rollback journal to implement transactions.
            self.sql_connection.execute("pragma journal_mode=WAL;")
            # When synchronous is NORMAL (1), the SQLite database engine will
            # still sync at the most critical moments,
            # but less often than in FULL mode.
            self.sql_connection.execute("PRAGMA synchronous=NORMAL;")
            # When temp_store is MEMORY (2) temporary tables and indices
            # are kept as if they were in pure in-memory databases.
            self.sql_connection.execute("PRAGMA temp_store=MEMORY;")

            self.sql_connection.text_factory = str
            self.sql_connection.row_factory = sqlite3.Row
            self.sql = self.sql_connection.cursor()
        except sqlite3.Error as e:
            mylog("minimal", ["[Database] - Open DB Error: ", e])

    def commitDB(self):
        """
        Commits the current transaction to the database.
        Returns:
            bool: True if the commit was successful, False if the database connection is not open.
        """
        if self.sql_connection is None:
            mylog("debug", "commitDB: database is not open")
            return False

        # Commit changes to DB
        self.sql_connection.commit()
        return True

    def rollbackDB(self):
        """
        Rolls back the current transaction in the database if a SQL connection exists.

        This method checks if a SQL connection is active and, if so, undoes all changes made in the current transaction, reverting the database to its previous state.
        """
        if self.sql_connection:
            self.sql_connection.rollback()

    def get_sql_array(self, query):
        """
        Executes the given SQL query and returns the result as a list of lists.
        Args:
            query (str): The SQL query to execute.
        Returns:
            list[list]: A list of rows, where each row is represented as a list of column values.
                        Returns None if the database connection is not open.
        """
        if self.sql_connection is None:
            mylog("debug", "getQueryArray: database is not open")
            return

        self.sql.execute(query)
        rows = self.sql.fetchall()
        # self.commitDB()

        # Convert result into list of lists
        # Efficiently convert each row to a list

        return [list(row) for row in rows]

    def initDB(self):
        """
        Initializes and upgrades the database schema for the application.
        This method performs the following actions within a transaction:
            - Ensures required columns exist in the 'Devices' table, adding them if missing.
            - Sets up or updates the 'Settings', 'Parameters', 'Plugins', and 'CurrentScan' tables.
            - Ensures necessary database views and indexes are present.
            - Commits the transaction if all operations succeed.
            - Rolls back the transaction and logs an error if any operation fails.
            - Initializes the AppEvent database table after schema setup.
        Raises:
            RuntimeError: If ensuring any required column fails.
            Exception: For any other errors encountered during initialization.
        """

        try:
            # Start transactional upgrade
            self.sql_connection.execute("BEGIN IMMEDIATE;")

            # Add Devices fields if missing
            if not ensure_column(self.sql, "Devices", "devFQDN", "TEXT"):
                raise RuntimeError("ensure_column(devFQDN) failed")
            if not ensure_column(self.sql, "Devices", "devPrimaryIPv4", "TEXT"):
                raise RuntimeError("ensure_column(devPrimaryIPv4) failed")
            if not ensure_column(self.sql, "Devices", "devPrimaryIPv6", "TEXT"):
                raise RuntimeError("ensure_column(devPrimaryIPv6) failed")
            if not ensure_column(self.sql, "Devices", "devVlan", "TEXT"):
                raise RuntimeError("ensure_column(devVlan) failed")
            if not ensure_column(self.sql, "Devices", "devForceStatus", "TEXT"):
                raise RuntimeError("ensure_column(devForceStatus) failed")
            if not ensure_column(self.sql, "Devices", "devParentRelType", "TEXT"):
                raise RuntimeError("ensure_column(devParentRelType) failed")
            if not ensure_column(self.sql, "Devices", "devReqNicsOnline", "INTEGER"):
                raise RuntimeError("ensure_column(devReqNicsOnline) failed")
            if not ensure_column(self.sql, "Devices", "devMacSource", "TEXT"):
                raise RuntimeError("ensure_column(devMacSource) failed")
            if not ensure_column(self.sql, "Devices", "devNameSource", "TEXT"):
                raise RuntimeError("ensure_column(devNameSource) failed")
            if not ensure_column(self.sql, "Devices", "devFQDNSource", "TEXT"):
                raise RuntimeError("ensure_column(devFQDNSource) failed")
            if not ensure_column(self.sql, "Devices", "devLastIPSource", "TEXT"):
                raise RuntimeError("ensure_column(devLastIPSource) failed")
            if not ensure_column(self.sql, "Devices", "devVendorSource", "TEXT"):
                raise RuntimeError("ensure_column(devVendorSource) failed")
            if not ensure_column(self.sql, "Devices", "devSSIDSource", "TEXT"):
                raise RuntimeError("ensure_column(devSSIDSource) failed")
            if not ensure_column(self.sql, "Devices", "devParentMACSource", "TEXT"):
                raise RuntimeError("ensure_column(devParentMACSource) failed")
            if not ensure_column(self.sql, "Devices", "devParentPortSource", "TEXT"):
                raise RuntimeError("ensure_column(devParentPortSource) failed")
            if not ensure_column(self.sql, "Devices", "devParentRelTypeSource", "TEXT"):
                raise RuntimeError("ensure_column(devParentRelTypeSource) failed")
            if not ensure_column(self.sql, "Devices", "devVlanSource", "TEXT"):
                raise RuntimeError("ensure_column(devVlanSource) failed")

            # Settings table setup
            ensure_Settings(self.sql)

            # Parameters tables setup
            ensure_Parameters(self.sql)

            # One-time UTC timestamp migration (must run after Parameters table exists)
            migrate_timestamps_to_utc(self.sql)

            # Plugins tables setup
            ensure_plugins_tables(self.sql)

            # CurrentScan table setup
            ensure_CurrentScan(self.sql)

            # Views
            ensure_views(self.sql)

            # Indexes
            ensure_Indexes(self.sql)

            # Normalization triggers
            ensure_mac_lowercase_triggers(self.sql)

            # commit changes
            self.commitDB()
        except Exception as e:
            mylog("minimal", ["[Database] - initDB ERROR:", e])
            self.rollbackDB()  # rollback any changes on error
            raise  # re-raise the exception

        # Init the AppEvent database table
        AppEvent_obj(self)

    def get_table_as_json(self, sqlQuery, parameters=None):
        """
        Wrapper to use the central get_table_as_json helper.

        Args:
            sqlQuery (str): The SQL query to execute.
            parameters (dict, optional): Named parameters for the SQL query.
        """
        try:
            result = get_table_json(self.sql, sqlQuery, parameters)
        except Exception as e:
            mylog("minimal", ["[Database] - get_table_as_json ERROR:", e])
            return json_obj({}, [])  # return empty object on failure

        # mylog('debug',[ '[Database] - get_table_as_json - returning ', len(rows), " rows with columns: ", columnNames])
        # mylog('debug',[ '[Database] - get_table_as_json - returning json ', json.dumps(result) ])

        return result

    # -------------------------------------------------------------------------------
    # referece from here: https://codereview.stackexchange.com/questions/241043/interface-class-for-sqlite-databases
    # -------------------------------------------------------------------------------
    def read(self, query, *args):
        """check the query and arguments are aligned and are read only"""
        # mylog('debug',[ '[Database] - Read All: SELECT Query: ', query, " params: ", args])
        try:
            assert query.count("?") == len(args)
            assert query.upper().strip().startswith("SELECT")
            self.sql.execute(query, args)
            rows = self.sql.fetchall()
            return rows
        except AssertionError:
            mylog("minimal", ["[Database] - ERROR: inconsistent query and/or arguments.", query, " params: ", args,],)
        except sqlite3.Error as e:
            mylog("minimal", ["[Database] - SQL ERROR: ", e])
        return None

    def read_one(self, query, *args):
        """
        call read() with the same arguments but only returns the first row.
        should only be used when there is a single row result expected
        """
        mylog("debug", ["[Database] - Read One: ", query, " params: ", args])
        rows = self.read(query, *args)
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            mylog("verbose", ["[Database] - Warning!: query returns multiple rows, only first row is passed on!", query, " params: ", args,],)
            return rows[0]
        # empty result set
        return None


def get_device_stats(db):
    """
    Retrieve device statistics from the database.

    Args:
        db: A database connection or handler object that provides a `read_one` method.

    Returns:
        The result of the `read_one` method executed with the `sql_devices_stats` query,
        typically containing statistics such as the number of devices online, down, all,
        archived, new, or unknown.

    Raises:
        Any exceptions raised by the underlying database handler.
    """
    # columns = ["online","down","all","archived","new","unknown"]
    return db.read_one(sql_devices_stats)


def get_all_devices(db):
    """
    Retrieve all devices from the database.

    Args:
        db: A database connection or handler object that provides a `read` method.

    Returns:
        The result of executing the `sql_devices_all` query using the database handler.
    """
    return db.read(sql_devices_all)


def get_array_from_sql_rows(rows):
    """
    Converts a sequence of SQL query result rows into a list of lists.
    Each row can be an instance of sqlite3.Row, a tuple, a list, or a single value.
    - If the row is a sqlite3.Row, it is converted to a list.
    - If the row is a tuple or list, it is converted to a list.
    - If the row is a single value, it is wrapped in a list.
    Args:
        rows (Iterable): An iterable of rows returned from an SQL query.
    Returns:
        list: A list of lists, where each inner list represents a row of data.
    """
    # Convert result into list of lists
    return [
        list(row) if isinstance(row, (sqlite3.Row, tuple, list)) else [row]
        for row in rows
    ]


def get_temp_db_connection():
    """
    Returns a new SQLite connection with Row factory.
    Should be used per-thread/request to avoid cross-thread issues.
    """
    conn = sqlite3.connect(fullDbPath, timeout=5, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")  # 5s wait before giving up
    conn.row_factory = sqlite3.Row
    return conn
