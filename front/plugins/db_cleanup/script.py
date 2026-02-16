#!/usr/bin/env python

import os
import sys

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from const import logPath, fullDbPath  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
from database import get_temp_db_connection  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value("TIMEZONE"))

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

pluginName = "DBCLNP"

LOG_PATH = logPath + "/plugins"
LOG_FILE = os.path.join(LOG_PATH, f"script.{pluginName}.log")
RESULT_FILE = os.path.join(LOG_PATH, f"last_result.{pluginName}.log")


def main():

    PLUGINS_KEEP_HIST = int(get_setting_value("PLUGINS_KEEP_HIST"))
    HRS_TO_KEEP_NEWDEV = int(get_setting_value("HRS_TO_KEEP_NEWDEV"))
    HRS_TO_KEEP_OFFDEV = int(get_setting_value("HRS_TO_KEEP_OFFDEV"))
    DAYS_TO_KEEP_EVENTS = int(get_setting_value("DAYS_TO_KEEP_EVENTS"))
    CLEAR_NEW_FLAG = get_setting_value("CLEAR_NEW_FLAG")

    mylog("verbose", [f"[{pluginName}] In script"])

    # Execute cleanup/upkeep
    cleanup_database(
        fullDbPath,
        DAYS_TO_KEEP_EVENTS,
        HRS_TO_KEEP_NEWDEV,
        HRS_TO_KEEP_OFFDEV,
        PLUGINS_KEEP_HIST,
        CLEAR_NEW_FLAG,
    )

    mylog("verbose", [f"[{pluginName}] Cleanup complete"])

    return 0


# ===============================================================================
# Cleanup / upkeep database
# ===============================================================================
def cleanup_database(
    dbPath,
    DAYS_TO_KEEP_EVENTS,
    HRS_TO_KEEP_NEWDEV,
    HRS_TO_KEEP_OFFDEV,
    PLUGINS_KEEP_HIST,
    CLEAR_NEW_FLAG,
):
    """
    Cleaning out old records from the tables that don't need to keep all data.
    """

    mylog("verbose", [f"[{pluginName}] Upkeep Database: {dbPath}"])

    conn = get_temp_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("REINDEX;")
        mylog("verbose", [f"[{pluginName}] REINDEX completed"])
    except Exception as e:
        mylog("none", [f"[{pluginName}] REINDEX failed: {e}"])

    # -----------------------------------------------------
    # Cleanup Online History
    mylog("verbose", [f"[{pluginName}] Online_History: Delete all but keep latest 150 entries"])
    cursor.execute(
        """DELETE from Online_History where "Index" not in (
                            SELECT "Index" from Online_History
                            order by Scan_Date desc limit 150)"""
    )
    mylog("verbose", [f"[{pluginName}] Online_History deleted rows: {cursor.rowcount}"])

    # -----------------------------------------------------
    # Cleanup Events
    mylog("verbose", f"[{pluginName}] Events: Delete all older than {str(DAYS_TO_KEEP_EVENTS)} days (DAYS_TO_KEEP_EVENTS setting)")
    sql = f"""DELETE FROM Events WHERE eve_DateTime <= date('now', '-{str(DAYS_TO_KEEP_EVENTS)} day')"""
    mylog("verbose", [f"[{pluginName}] SQL : {sql}"])
    cursor.execute(sql)
    mylog("verbose", [f"[{pluginName}] Events deleted rows: {cursor.rowcount}"])

    # -----------------------------------------------------
    # Plugins_History
    mylog("verbose", f"[{pluginName}] Plugins_History: Trim to {str(PLUGINS_KEEP_HIST)} per Plugin")
    delete_query = f"""DELETE FROM Plugins_History
                            WHERE "Index" NOT IN (
                                SELECT "Index"
                                FROM (
                                    SELECT "Index",
                                        ROW_NUMBER() OVER(PARTITION BY "Plugin" ORDER BY DateTimeChanged DESC) AS row_num
                                    FROM Plugins_History
                                ) AS ranked_objects
                                WHERE row_num <= {str(PLUGINS_KEEP_HIST)}
                            );"""
    cursor.execute(delete_query)
    mylog("verbose", [f"[{pluginName}] Plugins_History deleted rows: {cursor.rowcount}"])

    # -----------------------------------------------------
    # Notifications
    histCount = get_setting_value("DBCLNP_NOTIFI_HIST")
    mylog("verbose", f"[{pluginName}] Notifications: Trim to {histCount}")
    delete_query = f"""DELETE FROM Notifications
                            WHERE "Index" NOT IN (
                               SELECT "Index"
                                        FROM (
                                            SELECT "Index",
                                                ROW_NUMBER() OVER(PARTITION BY "Notifications" ORDER BY DateTimeCreated DESC) AS row_num
                                            FROM Notifications
                                        ) AS ranked_objects
                                        WHERE row_num <= {histCount}
                            );"""
    cursor.execute(delete_query)
    mylog("verbose", [f"[{pluginName}] Notifications deleted rows: {cursor.rowcount}"])

    # -----------------------------------------------------
    # AppEvents
    histCount = get_setting_value("WORKFLOWS_AppEvents_hist")
    mylog("verbose", [f"[{pluginName}] Trim AppEvents to less than {histCount}"])
    delete_query = f"""DELETE FROM AppEvents
                            WHERE "Index" NOT IN (
                               SELECT "Index"
                                        FROM (
                                            SELECT "Index",
                                                ROW_NUMBER() OVER(PARTITION BY "AppEvents" ORDER BY DateTimeCreated DESC) AS row_num
                                            FROM AppEvents
                                        ) AS ranked_objects
                                        WHERE row_num <= {histCount}
                            );"""
    cursor.execute(delete_query)
    mylog("verbose", [f"[{pluginName}] AppEvents deleted rows: {cursor.rowcount}"])

    conn.commit()

    # -----------------------------------------------------
    # Cleanup New Devices
    if HRS_TO_KEEP_NEWDEV != 0:
        mylog("verbose", f"[{pluginName}] Devices: Delete New Devices older than {str(HRS_TO_KEEP_NEWDEV)} hours")
        query = f"""DELETE FROM Devices WHERE devIsNew = 1 AND devFirstConnection < date('now', '-{str(HRS_TO_KEEP_NEWDEV)} hour')"""
        mylog("verbose", [f"[{pluginName}] Query: {query}"])
        cursor.execute(query)
        mylog("verbose", [f"[{pluginName}] Devices (new) deleted rows: {cursor.rowcount}"])

    # -----------------------------------------------------
    # Cleanup Offline Devices
    if HRS_TO_KEEP_OFFDEV != 0:
        mylog("verbose", f"[{pluginName}] Devices: Delete Offline Devices older than {str(HRS_TO_KEEP_OFFDEV)} hours")
        query = f"""DELETE FROM Devices WHERE devPresentLastScan = 0 AND devLastConnection < date('now', '-{str(HRS_TO_KEEP_OFFDEV)} hour')"""
        mylog("verbose", [f"[{pluginName}] Query: {query}"])
        cursor.execute(query)
        mylog("verbose", [f"[{pluginName}] Devices (offline) deleted rows: {cursor.rowcount}"])

    # -----------------------------------------------------
    # Clear New Flag
    if CLEAR_NEW_FLAG != 0:
        mylog("verbose", f'[{pluginName}] Devices: Clear "New Device" flag older than {str(CLEAR_NEW_FLAG)} hours')
        query = f"""UPDATE Devices SET devIsNew = 0 WHERE devIsNew = 1 AND date(devFirstConnection, '+{str(CLEAR_NEW_FLAG)} hour') < date('now')"""
        mylog("verbose", [f"[{pluginName}] Query: {query}"])
        cursor.execute(query)
        mylog("verbose", [f"[{pluginName}] Devices updated rows (clear new): {cursor.rowcount}"])

    # -----------------------------------------------------
    # De-dupe Plugins_Objects
    mylog("verbose", [f"[{pluginName}] Plugins_Objects: Delete all duplicates"])
    cursor.execute(
        """
        DELETE FROM Plugins_Objects
        WHERE rowid > (
            SELECT MIN(rowid) FROM Plugins_Objects p2
            WHERE Plugins_Objects.Plugin = p2.Plugin
            AND Plugins_Objects.Object_PrimaryID = p2.Object_PrimaryID
            AND Plugins_Objects.Object_SecondaryID = p2.Object_SecondaryID
            AND Plugins_Objects.UserData = p2.UserData
        )
    """
    )
    mylog("verbose", [f"[{pluginName}] Plugins_Objects deleted rows: {cursor.rowcount}"])

    conn.commit()

    # WAL + Vacuum
    cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    cursor.execute("PRAGMA wal_checkpoint(FULL);")
    mylog("verbose", [f"[{pluginName}] WAL checkpoint executed to truncate file."])

    mylog("verbose", [f"[{pluginName}] Shrink Database"])
    cursor.execute("VACUUM;")

    conn.close()


if __name__ == "__main__":
    main()
