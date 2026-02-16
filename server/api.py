#!/usr/bin/env python
import json
import time
import threading
import datetime

# Register NetAlertX modules
import conf
from const import (
    apiPath,
    sql_appevents,
    sql_devices_all,
    sql_events_pending_alert,
    sql_settings,
    sql_plugins_events,
    sql_plugins_history,
    sql_plugins_objects,
    sql_language_strings,
    sql_notifications_all,
    sql_online_history,
    sql_devices_tiles,
    sql_devices_filters,
)
from logger import mylog
from helper import write_file, get_setting_value
from utils.datetime_utils import timeNowUTC
from app_state import updateState
from models.user_events_queue_instance import UserEventsQueueInstance

# Import the start_server function
from api_server.api_server_start import start_server

apiEndpoints = []

# Lock for thread safety
api_lock = threading.Lock()
periodic_write_lock = threading.Lock()
stop_event = threading.Event()  # Event to signal thread termination


# ===============================================================================
# API
# ===============================================================================
def update_api(
    db, all_plugins, forceUpdate, updateOnlyDataSources=[], is_ad_hoc_user_event=False
):
    mylog("debug", ["[API] Update API starting"])

    # Start periodic write if not running
    start_periodic_write(interval=1)

    # Update app_state.json and retrieve app_state to check if GraphQL server is running
    app_state = updateState()

    # Save plugins
    write_file(apiPath + "plugins.json", json.dumps({"data": all_plugins}))

    # Prepare database tables we want to expose
    dataSourcesSQLs = [
        ["appevents", sql_appevents],
        ["devices", sql_devices_all],
        ["events_pending_alert", sql_events_pending_alert],
        ["settings", sql_settings],
        ["plugins_events", sql_plugins_events],
        ["plugins_history", sql_plugins_history],
        ["plugins_objects", sql_plugins_objects],
        ["plugins_language_strings", sql_language_strings],
        ["notifications", sql_notifications_all],
        ["online_history", sql_online_history],
        ["devices_tiles", sql_devices_tiles],
        ["devices_filters", sql_devices_filters],
        ["custom_endpoint", conf.API_CUSTOM_SQL],
    ]

    # Save selected database tables
    for dsSQL in dataSourcesSQLs:
        if not updateOnlyDataSources or dsSQL[0] in updateOnlyDataSources:
            api_endpoint_class(
                db,
                forceUpdate,
                dsSQL[1],
                apiPath + "table_" + dsSQL[0] + ".json",
                is_ad_hoc_user_event,
            )

    # Start the GraphQL server
    graphql_port_value = get_setting_value("GRAPHQL_PORT")
    api_token_value = get_setting_value("API_TOKEN")

    # Start GraphQL server if not yet running
    if app_state.graphQLServerStarted == 0:
        if graphql_port_value is not None and len(api_token_value) > 1:
            try:
                graphql_port_value = int(
                    graphql_port_value
                )  # Ensure port is an integer
                start_server(graphql_port_value, app_state)  # Start the server
            except ValueError:
                mylog("none", [f"[API] Invalid GRAPHQL_PORT value, must be an integer: {graphql_port_value}"],)
        else:
            mylog("none", ["[API] GRAPHQL_PORT or API_TOKEN is not set, will try later."])


# -------------------------------------------------------------------------------
class api_endpoint_class:
    def __init__(self, db, forceUpdate, query, path, is_ad_hoc_user_event=False):

        current_time = timeNowUTC(as_string=False)

        self.db = db
        self.query = query
        self.jsonData = db.get_table_as_json(self.query).json
        self.path = path
        self.fileName = path.split("/")[-1]
        self.hash = hash(json.dumps(self.jsonData))
        self.debounce_interval = 3  # Time in seconds to wait before writing
        self.changeDetectedWhen = None
        # self.last_update_time = current_time - datetime.timedelta(minutes=1)  # Last time data was updated
        self.is_ad_hoc_user_event = is_ad_hoc_user_event
        self.needsUpdate = False

        # Check if the endpoint needs to be updated
        found = False
        index = 0

        # Search previous endpoint states to check if API needs updating
        for endpoint in apiEndpoints:
            # Match SQL and API endpoint path
            if endpoint.query == self.query and endpoint.path == self.path:
                found = True
                mylog("trace", [f"[API] api_endpoint_class: Hashes  (file|old|new): ({self.fileName}|{endpoint.hash}|{self.hash})"],)
                if endpoint.hash != self.hash:
                    self.needsUpdate = True
                    # Only update changeDetectedWhen if it hasn't been set recently
                    if not self.changeDetectedWhen or current_time > (
                        self.changeDetectedWhen + datetime.timedelta(seconds=self.debounce_interval)
                    ):
                        self.changeDetectedWhen = (
                            current_time  # Set timestamp for change detection
                        )
                    if index < len(apiEndpoints):
                        apiEndpoints[index] = self
                    # check end of bounds and replace
                    if index < len(apiEndpoints):
                        apiEndpoints[index] = self

            index = index + 1

        # needs also an update if new endpoint
        if not found:
            self.needsUpdate = True
            # Only update changeDetectedWhen if it hasn't been set recently
            if not self.changeDetectedWhen or current_time > (
                self.changeDetectedWhen + datetime.timedelta(seconds=self.debounce_interval)
            ):
                self.changeDetectedWhen = (
                    current_time  # Initialize timestamp for new endpoint
                )
            apiEndpoints.append(self)

        # Needs to be called for initial updates
        self.try_write(forceUpdate)

    # ----------------------------------------
    def try_write(self, forceUpdate):
        current_time = timeNowUTC(as_string=False)

        # Debugging info to understand the issue
        # mylog('debug', [f'[API] api_endpoint_class: {self.fileName} is_ad_hoc_user_event
        # {self.is_ad_hoc_user_event} last_update_time={self.last_update_time},
        # debounce time={self.last_update_time + datetime.timedelta(seconds=self.debounce_interval)}.'])

        # Only attempt to write if the debounce time has passed
        if forceUpdate is True or (
            self.needsUpdate and (
                self.changeDetectedWhen is None or current_time > (
                    self.changeDetectedWhen + datetime.timedelta(seconds=self.debounce_interval)
                )
            )
        ):
            mylog("debug", [f"[API] api_endpoint_class: Writing {self.fileName} after debounce."],)

            write_file(self.path, json.dumps(self.jsonData))

            self.needsUpdate = False
            self.last_update_time = timeNowUTC(as_string=False)  # Reset last_update_time after writing

            # Update user event execution log
            # mylog('verbose', [f'[API] api_endpoint_class: is_ad_hoc_user_event {self.is_ad_hoc_user_event}'])
            if self.is_ad_hoc_user_event:
                execution_log = UserEventsQueueInstance()
                execution_log.finalize_event("update_api")
                self.is_ad_hoc_user_event = False

        # else:
        #     # Debugging if write is skipped
        #     mylog('trace', [f'[API] api_endpoint_class: Skipping write for {self.fileName}, debounce time not passed.'])


# ===============================================================================
# Periodic Write Functions
# ===============================================================================
periodic_write_running = False
periodic_write_thread = None


def periodic_write(interval=1):
    """Periodically checks all endpoints for pending writes."""

    while not stop_event.is_set():
        with api_lock:
            for endpoint in apiEndpoints:
                endpoint.try_write(False)  # Attempt to write each endpoint if necessary
        time.sleep(interval)


def start_periodic_write(interval=1):
    """Start periodic_write if it's not already running."""
    global periodic_write_running, periodic_write_thread

    with periodic_write_lock:
        if not periodic_write_running:
            mylog("trace", ["[API] Starting periodic_write thread."])
            periodic_write_running = True
            periodic_write_thread = threading.Thread(
                target=periodic_write, args=(interval,), daemon=True
            )
            periodic_write_thread.start()
        else:
            mylog("trace", ["[API] periodic_write is already running."])


def stop_periodic_write():
    """Stop the periodic_write thread."""
    global periodic_write_running

    with periodic_write_lock:
        if periodic_write_running:
            stop_event.set()
            periodic_write_thread.join()
            periodic_write_running = False
            mylog("trace", ["[API] periodic_write thread stopped."])
