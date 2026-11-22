#!/usr/bin/env python
#
# -------------------------------------------------------------------------------
#  NetAlertX  v2.70  /  2021-02-01
#  Open Source Network Guard / WIFI & LAN intrusion detector
#
#  Back module. Network scanner
# -------------------------------------------------------------------------------
#  Puche 2021 / 2022+ jokob             support@netalertx.com                GNU GPLv3
# -------------------------------------------------------------------------------


# ===============================================================================
# IMPORTS
# ===============================================================================
# from __future__ import print_function

import sys
import os
import sqlite3
import time
import datetime
import math
import traceback
from pathlib import Path

# Register NetAlertX modules
import conf
from const import fullConfPath, sql_new_devices, logPath
from logger import mylog
from helper import filePermissions, get_setting_value
from utils.datetime_utils import timeNowUTC, is_datetime_future, normalizeTimeStamp
from app_state import updateState
from api import update_api, check_activity, update_GUI_port
from scan.session_events import process_scan
from scan.resource_history import get_process_cpu_times_and_io, insert_resource_history
from initialise import importConfigs, renameSettings
from database import DB
from db.retry import is_transient_lock_error
from messaging.reporting import get_notifications
from models.notification_instance import NotificationInstance
from models.user_events_queue_instance import UserEventsQueueInstance
from scan.device_handling import update_devices_names
from workflows.manager import WorkflowManager

STARTUP_RETRY_ATTEMPTS = 3  # 1 initial attempt + 2 retries, matching db/retry.py's own MAX_ATTEMPTS
STARTUP_RETRY_DELAY_SECONDS = 5

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
    """Initialize the database/app state once, then run the recurring backend
    loop (plugin scans, workflow processing, API/device-list refresh) until
    the process exits."""
    mylog("none", ["[MAIN] Setting up ..."])  # has to be level 'none' as user config not loaded yet

    mylog("none", [f"[conf.tz] Setting up ...{conf.tz}"])

    # check file permissions and fix if required
    filePermissions()

    # Header + init app state
    updateState("Initializing", None, None, None, 0)

    # Open + init DB once and keep open
    # Opening/closing the DB frequently actually causes more issues
    db = DB()  # instance of class DB

    # Both calls retried as a whole (not just the individual statements
    # RetryingConnection already retries) because this runs once, before
    # the main loop's own catch-and-continue exists to help: open()'s pragma
    # statements and initDB()'s BEGIN IMMEDIATE both need write-lock-level
    # access, and under sustained contention right after a restart (while
    # whatever caused the original contention is still ongoing), either one
    # can exhaust those per-statement retries too - with nothing here to
    # catch it, the process would exit uncaught on every single restart
    # attempt. open() is a no-op (just logs and returns) once already open,
    # so re-running it on a retry after initDB() alone failed is harmless.
    for _init_attempt in range(STARTUP_RETRY_ATTEMPTS):
        try:
            db.open()
            db.initDB()
            break
        except sqlite3.OperationalError as e:
            if not is_transient_lock_error(e) or _init_attempt == STARTUP_RETRY_ATTEMPTS - 1:
                raise
            mylog("none", [f"[MAIN] Transient DB lock during startup, retrying ({_init_attempt + 1}/{STARTUP_RETRY_ATTEMPTS}): {e}"])
            time.sleep(STARTUP_RETRY_DELAY_SECONDS)

    sql = db.sql  # To-Do replace with the db class

    # Initialize the WorkflowManager
    workflow_manager = WorkflowManager(db)

    #Run this once to update the defined GUI port for the activity check
    update_GUI_port()

    # ===============================================================================
    # This is the main loop of NetAlertX
    # ===============================================================================

    mylog("debug", "[MAIN] Starting loop")

    all_plugins = None
    pm = None

    # Tracks the last "remaining minutes" value broadcast while paused, so we only
    # call updateState() when the displayed countdown minute actually changes.
    last_paused_minute_broadcast = None

    # -- SETTINGS BACKWARD COMPATIBILITY START --
    # rename settings that have changed names due to code cleanup or migration to plugins
    renameSettings(Path(fullConfPath))
    # -- SETTINGS BACKWARD COMPATIBILITY END --

    while True:
        try:
            # Catch transient SQLite lock contention anywhere in this
            # loop body (not just the schedule-tick block above, which
            # re-raises after recording tick_failed) and skip to the next
            # iteration instead of letting it crash the whole process.
            # An uncaught exception here kills the main thread, which (since
            # the API server thread is a daemon) kills the whole process -
            # correct for a rare crash, since the container's supervisor
            # restarts it in seconds. But under sustained write contention,
            # a transient lock that survives db.retry's own bounded retries
            # can recur on literally the next iteration after a restart,
            # turning a rare crash into a crash-loop that never stabilizes.
            # A genuinely different exception (a real bug) still propagates
            # and crashes the process exactly as before.
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

            # Pause gate: skip the automatic scheduled-scan block below while paused.
            # Manually-triggered scans (handled by check_and_run_user_event() above) are unaffected.
            pause_until_dt = normalizeTimeStamp(updateState().pause_until)

            if pause_until_dt and is_datetime_future(pause_until_dt):
                remaining_minutes = math.ceil((pause_until_dt - timeNowUTC(as_string=False)).total_seconds() / 60)

                if remaining_minutes != last_paused_minute_broadcast:
                    updateState(f"Process: Paused for {remaining_minutes} min")
                    last_paused_minute_broadcast = remaining_minutes

            else:
                if last_paused_minute_broadcast is not None:
                    # Pause expired naturally (not via /scan/resume) - clear it and resume normal state
                    updateState("Process: Idle", pause_until="")
                    last_paused_minute_broadcast = None

                # proceed if 1 minute passed
                if conf.last_scan_run + datetime.timedelta(minutes=1) < conf.loop_start_time:
                    # last time any scan or maintenance/upkeep was run
                    conf.last_scan_run = loop_start_time

                    # Resource-usage sampling: brackets the whole schedule-tick block
                    # below (run_plugin_scripts("schedule") through process_scan()),
                    # not just the scan pipeline itself - plugin subprocess execution
                    # happens in this window and is the class of cost this history
                    # exists to catch. Gated on MAINT_PERF_DAYS so a disabled install
                    # pays no sampling cost at all (see scan/resource_history.py).
                    # Defensive: an empty/corrupted setting value must disable this
                    # optional feature, not raise and kill the whole main loop -
                    # this sits outside the try/finally below, so an uncaught
                    # ValueError/TypeError here would have no safety net at all.
                    try:
                        resource_history_enabled = int(get_setting_value("MAINT_PERF_DAYS", 30)) != 0
                    except (TypeError, ValueError):
                        resource_history_enabled = False
                    resource_pre = get_process_cpu_times_and_io() if resource_history_enabled else None
                    tick_start_monotonic = time.monotonic()
                    tick_failed = False

                    try:
                        # Header (also broadcasts last_scan_run to frontend via SSE / app_state.json)
                        updateState("Process: Start",
                                    last_scan_run=loop_start_time.replace(microsecond=0).isoformat(),
                                    next_scan_time="")

                        # Timestamp
                        startTime = loop_start_time
                        startTime = startTime.replace(microsecond=0)

                        # Check if any plugins need to run on schedule
                        pm.run_plugin_scripts("schedule")

                        # Compute the next scheduled run time AFTER schedule check (which updates last_next_schedule)
                        # Only device_scanner plugins have meaningful next_scan times for user display
                        scanner_prefixes = {p["unique_prefix"] for p in all_plugins if p.get("plugin_type") == "device_scanner"}
                        scanner_next = [s.last_next_schedule for s in conf.mySchedules if s.service in scanner_prefixes]

                        # Get the earliest next scan time across all device scanners and broadcast.
                        # updateState validates the value is in the future before storing/broadcasting.
                        if scanner_next:
                            next_scan_dt = min(scanner_next)
                            updateState(next_scan_time=next_scan_dt.replace(microsecond=0).isoformat())

                        # determine run/scan type based on passed time
                        # --------------------------------------------

                        # Runs plugin scripts which are set to run every time after a scans finished
                        pm.run_plugin_scripts("always_after_scan")

                        # process all the scanned data into new devices
                        processScan = updateState("Check scan").processScan
                        mylog("debug", [f"[MAIN] processScan: {processScan}"])

                        if processScan is True:
                            mylog("debug", "[MAIN] start processing scan results")
                            process_scan(db, all_plugins)
                            updateState("Scan processed", None, None, None, None, False)
                    except Exception:
                        tick_failed = True
                        raise
                    finally:
                        if resource_history_enabled:
                            duration_ms = int((time.monotonic() - tick_start_monotonic) * 1000)
                            resource_post = get_process_cpu_times_and_io()
                            insert_resource_history(db, resource_pre, resource_post, duration_ms, tick_failed)

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

                # Writes each chunk's processed flags in one statement instead of
                # one commit per event (see WorkflowManager.process_event_batch).
                workflow_manager.process_event_batch(new_events)

                if workflow_manager.update_api:
                    update_api(db, all_plugins, True)

                updateState("Workflows: End")

            # check if devices list needs updating
            userUpdatedDevices = UserEventsQueueInstance().has_update_devices()

            mylog("debug", [f"[Plugins] Should I update API (userUpdatedDevices): {userUpdatedDevices}"],)

            if userUpdatedDevices:
                update_api(db, all_plugins, True, ["devices"], userUpdatedDevices)

            # ------------------------------------------------------------------
            # Loop with dynamic sleep if enabled (energy saving)
            # ------------------------------------------------------------------
            if conf.DEEP_SLEEP:
                is_active = check_activity()

                if is_active:
                    mylog("debug", ["[DEEP_SLEEP] Active Cycle"])
                    time.sleep(5)
                else:
                    mylog("debug", ["[DEEP_SLEEP] Passive Cycle"])
                    for _ in range(3):
                        if check_activity():
                            break
                        time.sleep(20)
            else:
                time.sleep(5)
        except sqlite3.OperationalError as e:
            if not is_transient_lock_error(e):
                raise
            mylog("none", [f"[MAIN] Transient DB lock, skipping this iteration: {e}"])
            time.sleep(5)
            continue


def _main_entrypoint():
    """Run main() once; on any uncaught Exception, log its traceback to a
    synchronous file before re-raising it unchanged. Unlike mylog(), which
    buffers through an async queue flushed every 10 lines or 1s idle, a
    synchronous open/write/close can't lose the traceback to a fast crash
    right after - the same reason a prior sys.excepthook-based attempt
    (removed - it silently failed to take effect in the real target
    environment for a reason never identified) was abandoned in favor of
    this plain try/except in normal control flow instead of a global hook.
    """
    try:
        return main()
    except Exception:
        with open(os.path.join(logPath, "main_crash.log"), "a") as f:
            f.write(f"{timeNowUTC()} [MAIN CRASH]\n{traceback.format_exc()}\n")
        raise


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == "__main__":
    mylog("debug", ["[__main__] Welcome to NetAlertX"])
    sys.exit(_main_entrypoint())
