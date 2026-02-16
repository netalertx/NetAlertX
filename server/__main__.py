#!/usr/bin/env python
#
# -------------------------------------------------------------------------------
#  NetAlertX  v2.70  /  2021-02-01
#  Open Source Network Guard / WIFI & LAN intrusion detector
#
#  Back module. Network scanner
# -------------------------------------------------------------------------------
#  Puche 2021 / 2022+ jokob             jokob@duck.com                GNU GPLv3
# -------------------------------------------------------------------------------


# ===============================================================================
# IMPORTS
# ===============================================================================
# from __future__ import print_function

import sys
import time
import datetime
from pathlib import Path

# Register NetAlertX modules
import conf
from const import fullConfPath, sql_new_devices
from logger import mylog
from helper import filePermissions
from utils.datetime_utils import timeNowUTC
from app_state import updateState
from api import update_api
from scan.session_events import process_scan
from initialise import importConfigs, renameSettings
from database import DB
from messaging.reporting import get_notifications
from models.notification_instance import NotificationInstance
from models.user_events_queue_instance import UserEventsQueueInstance
from scan.device_handling import update_devices_names
from workflows.manager import WorkflowManager

# ===============================================================================
# ===============================================================================
#                              MAIN
# ===============================================================================
# ===============================================================================
"""
main structure of NetAlertX

    Initialise All
    Rename old settings
    start Loop forever
        initialise loop
            (re)import config
            (re)import plugin config
        run plugins (once)
        run frontend events
        update API
        run plugins (scheduled)
        processing scan results
        run plugins (after Scan)
        reporting - could be replaced by run flows TODO
    end loop
"""


def main():
    mylog("none", ["[MAIN] Setting up ..."])  # has to be level 'none' as user config not loaded yet

    mylog("none", [f"[conf.tz] Setting up ...{conf.tz}"])

    # check file permissions and fix if required
    filePermissions()

    # Header + init app state
    updateState("Initializing", None, None, None, 0)

    # Open DB once and keep open
    # Opening/closing the DB frequently actually causes more issues
    db = DB()  # instance of class DB
    db.open()
    sql = db.sql  # To-Do replace with the db class

    # Init DB
    db.initDB()

    # Initialize the WorkflowManager
    workflow_manager = WorkflowManager(db)

    # ===============================================================================
    # This is the main loop of NetAlertX
    # ===============================================================================

    mylog("debug", "[MAIN] Starting loop")

    all_plugins = None
    pm = None

    # -- SETTINGS BACKWARD COMPATIBILITY START --
    # rename settings that have changed names due to code cleanup or migration to plugins
    renameSettings(Path(fullConfPath))
    # -- SETTINGS BACKWARD COMPATIBILITY END --

    while True:
        # re-load user configuration and plugins
        pm, all_plugins, imported = importConfigs(pm, db, all_plugins)

        # update time started
        conf.loop_start_time = timeNowUTC(as_string=False)

        loop_start_time = conf.loop_start_time  # TODO fix

        # Handle plugins executed ONCE
        if conf.plugins_once_run is False:
            pm.run_plugin_scripts("once")
            conf.plugins_once_run = True

        # check if user is waiting for api_update
        pm.check_and_run_user_event()

        # Update API endpoints
        update_api(db, all_plugins, False)

        # proceed if 1 minute passed
        if conf.last_scan_run + datetime.timedelta(minutes=1) < conf.loop_start_time:
            # last time any scan or maintenance/upkeep was run
            conf.last_scan_run = loop_start_time

            # Header
            updateState("Process: Start")

            # Timestamp
            startTime = loop_start_time
            startTime = startTime.replace(microsecond=0)

            # Check if any plugins need to run on schedule
            pm.run_plugin_scripts("schedule")

            # determine run/scan type based on passed time
            # --------------------------------------------

            # Runs plugin scripts which are set to run every time after a scans finished
            pm.run_plugin_scripts("always_after_scan")

            # process all the scanned data into new devices
            processScan = updateState("Check scan").processScan
            mylog("debug", [f"[MAIN] processScan: {processScan}"])

            if processScan is True:
                mylog("debug", "[MAIN] start processing scan results")
                process_scan(db)
                updateState("Scan processed", None, None, None, None, False)

            # Name resolution
            # --------------------------------------------

            # Check if new devices found (created by process_scan)
            sql.execute(sql_new_devices)
            newDevices = sql.fetchall()
            db.commitDB()

            # If new devices were found, run all plugins registered to be run when new devices are found
            # Run these before name resolution so plugins like NSLOOKUP that are configured
            # for `on_new_device` can populate names used in the notifications below.
            if len(newDevices) > 0:
                pm.run_plugin_scripts("on_new_device")

            # run plugins before notification processing (e.g. Plugins to discover device names)
            pm.run_plugin_scripts("before_name_updates")

            # Resolve devices names (will pick up results from on_new_device plugins above)
            mylog("debug", "[Main] Resolve devices names")
            update_devices_names(pm)

            # Notification handling
            # ----------------------------------------

            # send all configured notifications
            final_json = get_notifications(db)

            # Write the notifications into the DB
            notification = NotificationInstance(db)
            notificationObj = notification.create(final_json, "")

            # ------------------------------------------------------------------------------
            # Run all enabled publisher gateways (notification delivery)
            # ------------------------------------------------------------------------------
            # Design notes:
            # - The eve_PendingAlertEmail flag is only cleared *after* a notification is sent.
            # - If no notification is sent (HasNotifications == False), the flag stays set,
            #   meaning the event may still trigger alerts later depending on user settings
            #   (e.g. down-event reporting, delay timers, plugin conditions).
            # - A pending flag means “still under evaluation,” not “missed.”
            #   It will clear automatically once its event is included in a sent alert.
            # ------------------------------------------------------------------------------
            if notificationObj.HasNotifications:
                pm.run_plugin_scripts("on_notification")
                notification.setAllProcessed()

                # Only clear pending email flags and plugins_events once notifications are sent.
                notification.clearPendingEmailFlag()

            else:
                # If there are no notifications to process,
                # we still need to clear all plugin events to prevent database growth if
                # no notification gateways are configured
                notification.clearPluginEvents()
                mylog("verbose", ["[Notification] No changes to report"])

            # Commit SQL
            db.commitDB()

            mylog("verbose", ["[MAIN] Process: Idle"])
        else:
            # do something
            # mylog('verbose', ['[MAIN] Waiting to start next loop'])
            updateState("Process: Idle")

        # WORKFLOWS handling
        # ----------------------------------------
        # Fetch new unprocessed events
        new_events = workflow_manager.get_new_app_events()

        mylog("debug", [f"[MAIN] Processing WORKFLOW new_events from get_new_app_events: {len(new_events)}"],)

        # Process each new event and check triggers
        if len(new_events) > 0:
            updateState("Workflows: Start")
            update_api_flag = False
            for event in new_events:
                mylog("debug", [f"[MAIN] Processing WORKFLOW app event with GUID {event['GUID']}"],)

                # proceed to process events
                workflow_manager.process_event(event)

                if workflow_manager.update_api:
                    # Update API endpoints if needed
                    update_api_flag = True

            if update_api_flag:
                update_api(db, all_plugins, True)

            updateState("Workflows: End")

        # check if devices list needs updating
        userUpdatedDevices = UserEventsQueueInstance().has_update_devices()

        mylog("debug", [f"[Plugins] Should I update API (userUpdatedDevices): {userUpdatedDevices}"],)

        if userUpdatedDevices:
            update_api(db, all_plugins, True, ["devices"], userUpdatedDevices)

        # loop
        time.sleep(5)  # wait for N seconds


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == "__main__":
    mylog("debug", ["[__main__] Welcome to NetAlertX"])
    sys.exit(main())
