import os
import sqlite3
import json
import subprocess
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed


# Register NetAlertX modules
import conf
from const import pluginsPath, logPath, applicationPath, reportTemplatesPath
from logger import mylog, Logger
from helper import get_file_content, get_setting, get_setting_value
from utils.datetime_utils import timeNowUTC
from app_state import updateState
from api import update_api
from utils.plugin_utils import (
    logEventStatusCounts,
    get_plugin_setting_obj,
    print_plugin_info,
    list_to_csv,
    combine_plugin_objects,
    resolve_wildcards_arr,
    handle_empty,
    decode_and_rename_files
)
from models.notification_instance import NotificationInstance
from messaging.in_app import write_notification
from models.user_events_queue_instance import UserEventsQueueInstance
from utils.crypto_utils import generate_deterministic_guid


# -------------------------------------------------------------------------------
class plugin_manager:
    def __init__(self, db, all_plugins):
        self.db = db
        self.all_plugins = all_plugins
        self.plugin_states = {}
        self.plugin_checks = {}

        # object cache of settings and schedules for faster lookups
        self._cache = {}
        self._build_cache()

        # Make sure log level is initialized correctly
        Logger(get_setting_value("LOG_LEVEL"))

    def _build_cache(self):
        """Build a cache of settings and schedules for faster lookups."""
        self._cache["settings"] = {
            p["unique_prefix"]: {
                "RUN": get_plugin_setting_obj(p, "RUN"),
                "CMD": get_plugin_setting_obj(p, "CMD"),
            }
            for p in self.all_plugins
        }
        self._cache["schedules"] = {s.service: s for s in conf.mySchedules}

    def clear_cache(self):
        """Force rebuild of the cache (e.g. after config reload)."""
        self._cache = {}
        self._build_cache()

    # -------------------------------------------------------------------------------
    def run_plugin_scripts(self, runType):
        # Header
        updateState("Run: Plugins")

        mylog("debug", f"[Plugins] Check if any plugins need to be executed on run type: {runType}")

        for plugin in self.all_plugins:
            shouldRun = False
            prefix = plugin["unique_prefix"]

            # 🔹 Lookup RUN setting from cache instead of calling get_plugin_setting_obj each time
            run_setting = self._cache["settings"].get(prefix, {}).get("RUN")

            if run_setting is not None and run_setting["value"] == runType:
                if runType != "schedule":
                    shouldRun = True
                elif runType == "schedule":
                    # run if overdue scheduled time
                    # 🔹 Lookup schedule from cache instead of scanning conf.mySchedules
                    schd = self._cache["schedules"].get(prefix)
                    if schd:
                        # Check if schedule overdue
                        shouldRun = schd.runScheduleCheck()

            if shouldRun:
                # Header
                updateState(f"Plugin: {prefix}")

                print_plugin_info(plugin, ["display_name"])

                # 🔹 CMD also retrieved from cache
                cmd_setting = self._cache["settings"].get(prefix, {}).get("CMD")

                print_str = cmd_setting["value"] if cmd_setting else None

                mylog("debug", f"[Plugins] CMD: {print_str}")

                execute_plugin(self.db, self.all_plugins, plugin)

                # Update plugin states in app_state
                current_plugin_state = self.get_plugin_states(prefix)  # get latest plugin state

                # mylog('debug', f'current_plugin_state: {current_plugin_state}')

                updateState(pluginsStates={prefix: current_plugin_state.get(prefix, {})})

                # update last run time
                if runType == "schedule":
                    schd = self._cache["schedules"].get(prefix)
                    if schd:
                        # note the last time the scheduled plugin run was executed
                        schd.last_run = timeNowUTC(as_string=False)

    # ===============================================================================
    # Handling of  user initialized front-end events
    # ===============================================================================
    def check_and_run_user_event(self):
        """
        Process user events from the execution queue log file and notify the user about executed events.
        """
        execution_log = UserEventsQueueInstance()

        # Track whether to show notification for executed events
        executed_events = []

        # Read the log file to get the lines
        lines = execution_log.read_log()
        if not lines:
            mylog("debug", ["[check_and_run_user_event] User Execution Queue is empty"])
            return  # Exit early if the log file is empty
        else:
            mylog("debug", "[check_and_run_user_event] Process User Execution Queue:" + ", ".join(map(str, lines)))

        for line in lines:
            # Extract event name and parameters from the log line
            columns = line.strip().split("|")[2:4]

            event, param = "", ""
            if len(columns) == 2:
                event, param = columns

            # Process each event type
            if event == "test":
                self.handle_test(param)
                executed_events.append(f"test with param {param}")
                execution_log.finalize_event("test")
            elif event == "run":
                self.handle_run(param)
                executed_events.append(f"run with param {param}")
                execution_log.finalize_event("run")
            elif event == "update_api":
                # async handling
                update_api(self.db, self.all_plugins, False, param.split(","), True)

            else:
                mylog("minimal", f"[check_and_run_user_event] WARNING: Unhandled event in execution queue: {event} | {param}")
                execution_log.finalize_event(
                    event
                )  # Finalize unknown events to remove them

        # Notify user about executed events (if applicable)
        if len(executed_events) > 0 and executed_events:
            executed_events_message = ', '.join(executed_events)
            mylog('minimal', ['[check_and_run_user_event] INFO: Executed events: ', executed_events_message])
            write_notification(f"[Ad-hoc events] Events executed: {executed_events_message}", "interrupt", timeNowUTC())

        return

    # -------------------------------------------------------------------------------
    def handle_run(self, runType):

        mylog('minimal', ['[', timeNowUTC(), '] START Run: ', runType])

        # run the plugin
        for plugin in self.all_plugins:
            if plugin["unique_prefix"] == runType:
                pluginName = plugin["unique_prefix"]

                execute_plugin(self.db, self.all_plugins, plugin)

                # Update plugin states in app_state
                current_plugin_state = self.get_plugin_states(
                    pluginName
                )  # get latest plugin state
                updateState(
                    pluginsStates={pluginName: current_plugin_state.get(pluginName, {})}
                )

        mylog('minimal', ['[', timeNowUTC(), '] END Run: ', runType])

        return

    # -------------------------------------------------------------------------------
    def handle_test(self, runType):
        mylog('minimal', ['[', timeNowUTC(), '] [Test] START Test: ', runType])

        # Prepare test samples
        sample_json = json.loads(
            get_file_content(reportTemplatesPath + "webhook_json_sample.json")
        )[0]["body"]["attachments"][0]["text"]

        # Create fake notification
        notification = NotificationInstance(self.db)
        notificationObj = notification.create(sample_json, "")

        # Run test
        self.handle_run(runType)

        # Save notification
        notificationObj.upsert()

        mylog("minimal", ["[Test] END Test: ", runType])

        return

    # -------------------------------------------------------------------------------
    def get_plugin_states(self, plugin_name=None):
        """
        Returns plugin state summary suitable for updateState(..., pluginsStates=...).
        If plugin_name is provided, only calculates stats for that plugin.
        Structure per plugin:
        {
            "lastDataChange": str,
            "totalObjects": int,
            "newObjects": int,
            "changedObjects": int,
            "stateUpdated": str
        }
        """
        sql = self.db.sql
        plugin_states = {}
        now_str = timeNowUTC()

        if plugin_name:  # Only compute for single plugin
            sql.execute(
                """
                SELECT MAX(DateTimeChanged) AS last_changed,
                    COUNT(*) AS total_objects,
                    SUM(CASE WHEN DateTimeCreated = DateTimeChanged THEN 1 ELSE 0 END) AS new_objects
                FROM Plugins_Objects
                WHERE Plugin = ?
            """,
                (plugin_name,),
            )
            row = sql.fetchone()
            last_changed, total_objects, new_objects = row if row else ("", 0, 0)
            new_objects = new_objects or 0  # ensure it's int
            changed_objects = total_objects - new_objects

            plugin_states[plugin_name] = {
                "lastDataChange": last_changed or "",
                "totalObjects": total_objects or 0,
                "newObjects": new_objects or 0,
                "changedObjects": changed_objects or 0,
                "stateUpdated": now_str
            }

            # Save in memory
            self.plugin_states[plugin_name] = plugin_states[plugin_name]

        else:  # Compute for all plugins (full refresh)
            sql.execute("""
                SELECT Plugin,
                    MAX(DateTimeChanged) AS last_changed,
                    COUNT(*) AS total_objects,
                    SUM(CASE WHEN DateTimeCreated = DateTimeChanged THEN 1 ELSE 0 END) AS new_objects
                FROM Plugins_Objects
                GROUP BY Plugin
            """)
            for plugin, last_changed, total_objects, new_objects in sql.fetchall():
                new_objects = new_objects or 0  # ensure it's int
                changed_objects = total_objects - new_objects
                plugin_states[plugin] = {
                    "lastDataChange": last_changed or "",
                    "totalObjects": total_objects or 0,
                    "newObjects": new_objects or 0,
                    "changedObjects": changed_objects or 0,
                    "stateUpdated": now_str
                }

            # Save in memory
            self.plugin_states = plugin_states

        return plugin_states


# -------------------------------------------------------------------------------
class plugin_param:
    def __init__(self, param, plugin, db):
        mylog("debug", f"[Plugins] Resolving param: {param}")

        paramValuesCount = 1

        #  Get setting value
        if param["type"] == "setting":
            inputValue = get_setting(param["value"])

            if inputValue is not None:
                setVal = inputValue["setValue"]  # setting value
                setTyp = inputValue["setType"]  # setting type

                setTypJSN = json.loads(setTyp.replace('"', '"').replace("'", '"'))

                mylog("debug", f"[Plugins] setTyp: {setTyp}")
                mylog("debug", f"[Plugins] setTypJSN: {setTypJSN}")

                dataType = setTypJSN["dataType"]

                mylog("debug", f"[Plugins] dType: {dataType}")

                if dataType == "array":
                    # store number of returned values
                    paramValuesCount = len(setVal)

                if dataType in ["string", "integer", "boolean"]:
                    resolved = setVal

                elif dataType == "array":
                    #  make them safely passable to a python or linux script
                    resolved = list_to_csv(setVal)

                else:
                    mylog("none", "[Plugins] ⚠ ERROR: Parameter probably not converted.")
                    return json.dumps(setVal)

        #  Get SQL result
        if param["type"] == "sql":
            inputValue = db.get_sql_array(param["value"])

            # store number of returned values
            paramValuesCount = len(inputValue)

            #  make them safely passable to a python or linux script
            resolved = list_to_csv(inputValue)

        mylog("debug", f"[Plugins] Resolved value: {resolved}")

        #  Handle timeout multiplier if script executes multiple time
        multiplyTimeout = False
        if "timeoutMultiplier" in param and param["timeoutMultiplier"]:
            multiplyTimeout = True

        #  Handle base64 encoding
        encodeToBase64 = False
        if "base64" in param and param["base64"]:
            encodeToBase64 = True

        mylog("debug", f"[Plugins] Convert to Base64: {encodeToBase64}")
        if encodeToBase64:
            resolved = base64.b64encode(resolved.encode("ascii")).decode("ascii")
            mylog("debug", f"[Plugins] base64 value: {resolved}")

        self.resolved = resolved
        self.inputValue = inputValue
        self.base64 = encodeToBase64
        self.name = param["name"]
        self.type = param["type"]
        self.value = param["value"]
        self.paramValuesCount = paramValuesCount
        self.multiplyTimeout = multiplyTimeout


# Function to run a plugin command
def run_plugin(command, set_RUN_TIMEOUT, plugin):
    try:
        return subprocess.check_output(
            command,
            universal_newlines=True,
            stderr=subprocess.STDOUT,
            timeout=set_RUN_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        mylog("none", [e.output])
        mylog("none", "[Plugins] ⚠ ERROR - enable LOG_LEVEL=debug and check logs")
        return None
    except subprocess.TimeoutExpired:
        mylog("none", f"[Plugins] ⚠ ERROR - TIMEOUT - the plugin {plugin['unique_prefix']} forcefully terminated as timeout reached. Increase TIMEOUT setting and scan interval.")
        return None


# -------------------------------------------------------------------------------
# Executes the plugin command specified in the setting with the function specified as CMD
def execute_plugin(db, all_plugins, plugin):
    sql = db.sql

    # ------- necessary settings check  --------
    set = get_plugin_setting_obj(plugin, "CMD")

    #  handle missing "function":"CMD" setting
    if set is None:
        return

    set_CMD = set["value"]

    # Replace hardcoded /app paths with environment-aware path
    if "/app/front/plugins" in set_CMD:
        set_CMD = set_CMD.replace("/app/front/plugins", str(pluginsPath))
    if "/app/" in set_CMD:
        set_CMD = set_CMD.replace("/app/", f"{applicationPath}/")

    set = get_plugin_setting_obj(plugin, "RUN_TIMEOUT")

    #  handle missing "function":"<unique_prefix>_TIMEOUT" setting
    if set is None:
        set_RUN_TIMEOUT = 10
    else:
        try:
            set_RUN_TIMEOUT = int(set["value"])
        except (ValueError, TypeError, KeyError) as e:
            mylog("none", [f"[Plugins] ⚠ ERROR converting timeout for {plugin['unique_prefix']}: {e}, value was: {set.get('value')}"])
            set_RUN_TIMEOUT = 10

    #  Prepare custom params
    params = []

    if "params" in plugin:
        for param in plugin["params"]:
            tempParam = plugin_param(param, plugin, db)

            if tempParam.resolved is None:
                mylog("none", f'[Plugins] The parameter "name":"{tempParam.name}" for "value": {tempParam.value} was resolved as None')

            else:
                # params.append( [param["name"], resolved] )
                params.append([tempParam.name, tempParam.resolved])

                if tempParam.multiplyTimeout:
                    set_RUN_TIMEOUT = set_RUN_TIMEOUT * tempParam.paramValuesCount

                    mylog("debug", f'[Plugins] The parameter "name":"{param["name"]}" will multiply timeout {tempParam.paramValuesCount}x. Total timeout: {set_RUN_TIMEOUT}s')

    mylog("debug", f"[Plugins] Timeout: {set_RUN_TIMEOUT}")

    # build SQL query parameters to insert into the DB
    sqlParams = []

    # script
    if plugin["data_source"] == "script":
        # ------- prepare params --------
        # prepare command from plugin settings, custom parameters
        command = resolve_wildcards_arr(set_CMD.split(), params)

        # Execute command
        mylog("verbose", f"[Plugins] Executing: {set_CMD}")
        mylog("debug", f"[Plugins] Resolved : {command}")

        # Using ThreadPoolExecutor to handle concurrent subprocesses
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(run_plugin, command, set_RUN_TIMEOUT, plugin)
            ]  # Submit the command as a future

            for future in as_completed(futures):
                output = future.result()  # Get the output or error
                if output is not None:
                    mylog("verbose", [f"[Plugins] Output: {output}"])

        # Initialize newLines
        newLines = []

        # Create the file path
        file_dir = logPath + "/plugins"
        file_prefix = f"last_result.{plugin['unique_prefix']}"

        # Decode files, rename them, and get the list of files, this will return all files starting with the prefix, even if they are not encoded
        files_to_process = decode_and_rename_files(file_dir, file_prefix)

        for filename in files_to_process:
            full_path = os.path.join(file_dir, filename)

            mylog("debug", [f'[Plugins] Processing file "{full_path}"'])

            # Open the decrypted file and process its contents
            with open(full_path, "r") as f:
                newLines = f.read().split("\n")

                # if the script produced some output, clean it up to ensure it's the correct format
                # cleanup - select only lines containing a separator to filter out unnecessary data
                newLines = list(filter(lambda x: "|" in x, newLines))

                # Store e.g. Node_1 from last_result.<prefix>.encoded.Node_1.1.log
                tmp_SyncHubNodeName = ""
                if len(filename.split(".")) > 3:
                    tmp_SyncHubNodeName = filename.split(".")[2]

                for line in newLines:
                    columns = line.split("|")
                    # There have to be 9 or 13 columns
                    if len(columns) not in [9, 13]:
                        mylog("none", f"[Plugins] Wrong number of input values, must be 9 or 13, got {len(columns)} from: {line}")
                        continue  # Skip lines with incorrect number of columns

                    # Common part of the SQL parameters
                    base_params = [
                        0,  # "Index" placeholder
                        plugin[
                            "unique_prefix"
                        ],  # "Plugin" column value from the plugin dictionary
                        columns[0],  # "Object_PrimaryID" value from columns list
                        columns[1],  # "Object_SecondaryID" value from columns list
                        "null",  # Placeholder for "DateTimeCreated" column
                        columns[2],  # "DateTimeChanged" value from columns list
                        columns[3],  # "Watched_Value1" value from columns list
                        columns[4],  # "Watched_Value2" value from columns list
                        columns[5],  # "Watched_Value3" value from columns list
                        columns[6],  # "Watched_Value4" value from columns list
                        "not-processed",  # "Status" column (placeholder)
                        columns[7],  # "Extra" value from columns list
                        "null",  # Placeholder for "UserData" column
                        columns[8],  # "ForeignKey" value from columns list
                        tmp_SyncHubNodeName,  # Sync Hub Node name
                    ]

                    # Extend the common part with the additional values if there are 13 columns
                    if len(columns) == 13:
                        base_params.extend(
                            [
                                columns[9],  # "HelpVal1" value from columns list
                                columns[10],  # "HelpVal2" value from columns list
                                columns[11],  # "HelpVal3" value from columns list
                                columns[12],  # "HelpVal4" value from columns list
                            ]
                        )
                    elif len(columns) == 9:
                        # add padding
                        base_params.extend(
                            [
                                "null",  # "HelpVal1"
                                "null",  # "HelpVal2"
                                "null",  # "HelpVal3"
                                "null",  # "HelpVal4"
                            ]
                        )

                    # Create a tuple containing values to be inserted into the database.
                    # Each value corresponds to a column in the table in the order of the columns.
                    # must match the Plugins_Objects and Plugins_Events database tables and can be used as input for the plugin_object_class.

                    # Append the final parameters to sqlParams
                    sqlParams.append(tuple(base_params))

            # keep current instance log file, delete all from other nodes
            if filename != "last_result.log" and os.path.exists(full_path):
                os.remove(full_path)  # DEBUG:TODO uncomment 🐛
                mylog("verbose", f"[Plugins] Processed and deleted file: {full_path} ")

    # app-db-query
    if plugin["data_source"] == "app-db-query":
        # replace single quotes wildcards
        q = set_CMD.replace("{s-quote}", "'")

        # Execute command
        mylog("verbose", f"[Plugins] Executing: {q}")

        # set_CMD should contain a SQL query
        arr = db.get_sql_array(q)

        for row in arr:
            # There has to be always 9 or 13 columns
            if len(row) in [9, 13] and row[0] not in ["", "null"]:
                # Create a base tuple containing values to be inserted into the database.
                # Each value corresponds to a column in the table in the order of the columns.
                # Must match the Plugins_Objects and Plugins_Events database tables and can be used as input for the plugin_object_class.
                base_params = [
                    0,  # "Index" placeholder
                    plugin["unique_prefix"],  # "Plugin" plugin dictionary
                    row[0],  # "Object_PrimaryID" row
                    handle_empty(
                        row[1]
                    ),  # "Object_SecondaryID" column after handling empty values
                    "null",  # Placeholder "DateTimeCreated" column
                    row[2],  # "DateTimeChanged" row
                    row[3],  # "Watched_Value1" row
                    row[4],  # "Watched_Value2" row
                    handle_empty(
                        row[5]
                    ),  # "Watched_Value3" column after handling empty values
                    handle_empty(
                        row[6]
                    ),  # "Watched_Value4" column after handling empty values
                    "not-processed",  # "Status" column (placeholder)
                    row[7],  # "Extra" row
                    "null",  # Placeholder "UserData" column
                    row[8],  # "ForeignKey" row
                    "null",  # Sync Hub Node name - Only supported with scripts
                ]

                # Extend the base tuple with additional values if there are 13 columns
                if len(row) == 13:
                    base_params.extend(
                        [
                            row[9],  # "HelpVal1" row
                            row[10],  # "HelpVal2" row
                            row[11],  # "HelpVal3" row
                            row[12],  # "HelpVal4" row
                        ]
                    )
                else:
                    # add padding
                    base_params.extend(
                        [
                            "null",  # "HelpVal1"
                            "null",  # "HelpVal2"
                            "null",  # "HelpVal3"
                            "null",  # "HelpVal4"
                        ]
                    )

                # Append the final parameters to sqlParams
                sqlParams.append(tuple(base_params))
            else:
                mylog("none", "[Plugins] Skipped invalid sql result")

    # app-db-query
    if plugin["data_source"] == "sqlite-db-query":
        # replace single quotes wildcards
        # set_CMD should contain a SQL query
        q = set_CMD.replace("{s-quote}", "'")

        # Execute command
        mylog("verbose", f"[Plugins] Executing: {q}")

        # ------- necessary settings check  --------
        set = get_plugin_setting_obj(plugin, "DB_PATH")

        #  handle missing "function":"DB_PATH" setting
        if set is None:
            mylog("none", "[Plugins] ⚠ ERROR: DB_PATH setting for plugin type sqlite-db-query missing.")
            return

        fullSqlitePath = set["value"]

        #  try attaching the sqlite DB
        try:
            sql.execute(
                "ATTACH DATABASE '" + fullSqlitePath + "' AS EXTERNAL_" + plugin["unique_prefix"]
            )
            arr = db.get_sql_array(q)
            sql.execute("DETACH DATABASE EXTERNAL_" + plugin["unique_prefix"])

        except sqlite3.Error as e:
            mylog("none", f"[Plugins] ⚠ ERROR: DB_PATH setting ({fullSqlitePath}) for plugin {plugin['unique_prefix']}. Did you mount it correctly?")
            mylog("none", f"[Plugins] ⚠ ERROR: ATTACH DATABASE failed with SQL ERROR: {e}")
            return

        for row in arr:
            # There has to be always 9 or 13 columns
            if len(row) in [9, 13] and row[0] not in ["", "null"]:
                # Create a base tuple containing values to be inserted into the database.
                # Each value corresponds to a column in the table in the order of the columns.
                # Must match the Plugins_Objects and Plugins_Events database tables and can be used as input for the plugin_object_class.
                base_params = [
                    0,  # "Index" placeholder
                    plugin["unique_prefix"],  # "Plugin"
                    row[0],  # "Object_PrimaryID"
                    handle_empty(row[1]),  # "Object_SecondaryID"
                    "null",  # "DateTimeCreated" column (null placeholder)
                    row[2],  # "DateTimeChanged"
                    row[3],  # "Watched_Value1"
                    row[4],  # "Watched_Value2"
                    handle_empty(row[5]),  # "Watched_Value3"
                    handle_empty(row[6]),  # "Watched_Value4"
                    "not-processed",  # "Status" column (placeholder)
                    row[7],  # "Extra"
                    "null",  # "UserData" column (null placeholder)
                    row[8],  # "ForeignKey"
                    "null",  # Sync Hub Node name - Only supported with scripts
                ]

                # Extend the base tuple with additional values if there are 13 columns
                if len(row) == 13:
                    base_params.extend(
                        [
                            row[9],  # "HelpVal1"
                            row[10],  # "HelpVal2"
                            row[11],  # "HelpVal3"
                            row[12],  # "HelpVal4"
                        ]
                    )
                else:
                    # add padding
                    base_params.extend(
                        [
                            "null",  # "HelpVal1"
                            "null",  # "HelpVal2"
                            "null",  # "HelpVal3"
                            "null",  # "HelpVal4"
                        ]
                    )

                # Append the final parameters to sqlParams
                sqlParams.append(tuple(base_params))
            else:
                mylog("none", "[Plugins] Skipped invalid sql result")

    # check if the subprocess / SQL query failed / there was no valid output
    if len(sqlParams) == 0:
        mylog("none", f'[Plugins] No output received from the plugin "{plugin["unique_prefix"]}"')

    else:
        mylog("verbose", f"[Plugins] SUCCESS for {plugin['unique_prefix']} received {len(sqlParams)} entries")
        # mylog('debug',   ['[Plugins] sqlParam entries: ', sqlParams])

        # create objects
        process_plugin_events(db, plugin, sqlParams)

        # update API endpoints
        endpoints = [
            "plugins_events",
            "plugins_objects",
            "plugins_history",
            "appevents",
        ]

        # check if we need to update devices api endpoint as well to prevent long user waits on Loading...
        userUpdatedDevices = UserEventsQueueInstance().has_update_devices()

        mylog("verbose", f"[Plugins] Should I update API (userUpdatedDevices): {userUpdatedDevices}")

        if userUpdatedDevices:
            endpoints += ["devices"]

        update_api(db, all_plugins, True, endpoints, userUpdatedDevices)

    return


# -------------------------------------------------------------------------------
# Check if watched values changed for the given plugin
def process_plugin_events(db, plugin, plugEventsArr):
    sql = db.sql

    # Access the connection from the DB instance
    conn = db.sql_connection

    pluginPref = plugin["unique_prefix"]

    mylog("verbose", f"[Plugins] Processing        : {pluginPref}")

    try:
        # Begin a transaction
        with conn:
            pluginObjects = []
            pluginEvents = []

            #  Create plugin objects from existing database entries
            plugObjectsArr = db.get_sql_array(
                "SELECT * FROM Plugins_Objects where Plugin = '" + str(pluginPref) + "'"
            )

            for obj in plugObjectsArr:
                pluginObjects.append(plugin_object_class(plugin, obj))

            # create plugin objects from events - will be processed to find existing objects
            for eve in plugEventsArr:
                pluginEvents.append(plugin_object_class(plugin, eve))

            mylog("debug", f"[Plugins] Existing objects from Plugins_Objects: {len(pluginObjects)}")
            mylog("debug", f"[Plugins] Logged events from the plugin run    : {len(pluginEvents)}")

            #  Loop thru all current events and update the status to "exists" if the event matches an existing object
            index = 0
            for tmpObjFromEvent in pluginEvents:
                #  compare hash of the IDs for uniqueness
                if any(x.idsHash == tmpObjFromEvent.idsHash for x in pluginObjects):
                    pluginEvents[index].status = "exists"
                index += 1

            # Loop thru events and check if the ones that exist have changed in the watched columns
            # if yes update status accordingly
            index = 0
            for tmpObjFromEvent in pluginEvents:
                if tmpObjFromEvent.status == "exists":
                    #  compare hash of the changed watched columns for uniqueness - make sure you compare the values with the same idsHash before checking watchedHash
                    if any(
                        x.idsHash == tmpObjFromEvent.idsHash and x.watchedHash != tmpObjFromEvent.watchedHash
                        for x in pluginObjects
                    ):
                        pluginEvents[index].status = "watched-changed"

                    else:
                        pluginEvents[index].status = "watched-not-changed"
                index += 1

            # Loop thru events and check if previously available objects are missing
            for tmpObj in pluginObjects:
                isMissing = True

                for tmpObjFromEvent in pluginEvents:
                    if tmpObj.idsHash == tmpObjFromEvent.idsHash:
                        isMissing = False

                if isMissing:
                    # if wasn't missing before, mark as changed
                    if tmpObj.status != "missing-in-last-scan":
                        tmpObj.changed = timeNowUTC()
                        tmpObj.status = "missing-in-last-scan"
                    # mylog('debug', [f'[Plugins] Missing from last scan (PrimaryID | SecondaryID): {tmpObj.primaryId} | {tmpObj.secondaryId}'])

            # Merge existing plugin objects with newly discovered ones and update existing ones with new values
            for tmpObjFromEvent in pluginEvents:
                # set "new" status for new objects and append
                if tmpObjFromEvent.status == "not-processed":
                    # This is a new object as it was not discovered as "exists" previously
                    tmpObjFromEvent.status = "new"

                    pluginObjects.append(tmpObjFromEvent)
                # update data of existing objects
                else:
                    index = 0
                    for plugObj in pluginObjects:
                        # find corresponding object for the event and merge
                        if plugObj.idsHash == tmpObjFromEvent.idsHash:
                            pluginObjects[index] = combine_plugin_objects(
                                plugObj, tmpObjFromEvent
                            )

                        index += 1

            # Update the DB
            # ----------------------------
            # Update the Plugin_Objects
            # Create lists to hold the data for bulk insertion
            objects_to_insert = []
            events_to_insert = []
            history_to_insert = []
            objects_to_update = []

            # only generate events that we want to be notified on (we only need to do this once as all plugObj have the same prefix)
            statuses_to_report_on = get_setting_value(pluginPref + "_REPORT_ON")

            for plugObj in pluginObjects:
                #  keep old createdTime time if the plugObj already was created before
                createdTime = (
                    plugObj.changed if plugObj.status == "new" else plugObj.created
                )
                #  19 values without Index
                values = (
                    plugObj.pluginPref,
                    plugObj.primaryId,
                    plugObj.secondaryId,
                    createdTime,
                    plugObj.changed,
                    plugObj.watched1,
                    plugObj.watched2,
                    plugObj.watched3,
                    plugObj.watched4,
                    plugObj.status,
                    plugObj.extra,
                    plugObj.userData,
                    plugObj.foreignKey,
                    plugObj.syncHubNodeName,
                    plugObj.helpVal1,
                    plugObj.helpVal2,
                    plugObj.helpVal3,
                    plugObj.helpVal4,
                    plugObj.objectGUID,
                )

                if plugObj.status == "new":
                    objects_to_insert.append(values)
                else:
                    objects_to_update.append(
                        values + (plugObj.index,)
                    )  # Include index for UPDATE

                if plugObj.status in statuses_to_report_on:
                    events_to_insert.append(values)

                # combine all DB insert and update events into one for history
                history_to_insert.append(values)

            mylog("debug", f"[Plugins] pluginEvents      count: {len(pluginEvents)}")
            mylog("debug", f"[Plugins] pluginObjects     count: {len(pluginObjects)}")

            mylog("debug", f"[Plugins] events_to_insert  count: {len(events_to_insert)}")
            mylog("debug", f"[Plugins] history_to_insert count: {len(history_to_insert)}")
            mylog("debug", f"[Plugins] objects_to_insert count: {len(objects_to_insert)}")
            mylog("debug", f"[Plugins] objects_to_update count: {len(objects_to_update)}")

            mylog("trace", f"[Plugins] objects_to_update: {objects_to_update}")
            mylog("trace", f"[Plugins] events_to_insert: {events_to_insert}")
            mylog("trace", f"[Plugins] history_to_insert: {history_to_insert}")

            logEventStatusCounts("pluginEvents", pluginEvents)
            logEventStatusCounts("pluginObjects", pluginObjects)

            # Bulk insert objects
            if objects_to_insert:
                sql.executemany(
                    """
                    INSERT INTO Plugins_Objects
                    ("Plugin", "Object_PrimaryID", "Object_SecondaryID", "DateTimeCreated",
                    "DateTimeChanged", "Watched_Value1", "Watched_Value2", "Watched_Value3",
                    "Watched_Value4", "Status", "Extra", "UserData", "ForeignKey", "SyncHubNodeName",
                    "HelpVal1", "HelpVal2", "HelpVal3", "HelpVal4",
                    "ObjectGUID")
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    objects_to_insert,
                )

            # Bulk update objects
            if objects_to_update:
                sql.executemany(
                    """
                    UPDATE Plugins_Objects
                    SET "Plugin" = ?, "Object_PrimaryID" = ?, "Object_SecondaryID" = ?, "DateTimeCreated" = ?,
                        "DateTimeChanged" = ?, "Watched_Value1" = ?, "Watched_Value2" = ?, "Watched_Value3" = ?,
                        "Watched_Value4" = ?, "Status" = ?, "Extra" = ?, "UserData" = ?, "ForeignKey" = ?, "SyncHubNodeName" = ?,
                        "HelpVal1" = ?, "HelpVal2" = ?, "HelpVal3" = ?, "HelpVal4" = ?,
                        "ObjectGUID" = ?
                    WHERE "Index" = ?
                    """,
                    objects_to_update,
                )

            # Bulk insert events
            if events_to_insert:
                sql.executemany(
                    """
                    INSERT INTO Plugins_Events
                    ("Plugin", "Object_PrimaryID", "Object_SecondaryID", "DateTimeCreated",
                    "DateTimeChanged", "Watched_Value1", "Watched_Value2", "Watched_Value3",
                    "Watched_Value4", "Status", "Extra", "UserData", "ForeignKey", "SyncHubNodeName",
                    "HelpVal1", "HelpVal2", "HelpVal3", "HelpVal4",
                    "ObjectGUID")
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    events_to_insert,
                )

            # Bulk insert history entries
            if history_to_insert:
                sql.executemany(
                    """
                    INSERT INTO Plugins_History
                    ("Plugin", "Object_PrimaryID", "Object_SecondaryID", "DateTimeCreated",
                    "DateTimeChanged", "Watched_Value1", "Watched_Value2", "Watched_Value3",
                    "Watched_Value4", "Status", "Extra", "UserData", "ForeignKey", "SyncHubNodeName",
                    "HelpVal1", "HelpVal2", "HelpVal3", "HelpVal4",
                    "ObjectGUID")
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    history_to_insert,
                )

            # Commit changes to the database
            db.commitDB()

    except Exception as e:
        # Rollback the transaction in case of an error
        conn.rollback()
        mylog("none", f"[Plugins] ⚠ ERROR: {e}")
        raise e

    # Perform database table mapping if enabled for the plugin
    if len(pluginEvents) > 0 and "mapped_to_table" in plugin:
        # Initialize an empty list to store SQL parameters.
        sqlParams = []

        # Get the database table name from the 'mapped_to_table' key in the 'plugin' dictionary.
        dbTable = plugin["mapped_to_table"]

        # Log a debug message indicating the mapping of objects to the database table.
        mylog("debug", f"[Plugins] Mapping objects to database table: {dbTable}")

        # Initialize lists to hold mapped column names, columnsStr, and valuesStr for SQL query.
        mappedCols = []
        columnsStr = ""
        valuesStr = ""

        # Loop through the 'database_column_definitions' in the 'plugin' dictionary to collect mapped columns.
        # Build the columnsStr and valuesStr for the SQL query.
        for clmn in plugin["database_column_definitions"]:
            if "mapped_to_column" in clmn:
                mappedCols.append(clmn)

                columnsStr = f'{columnsStr}, "{clmn["mapped_to_column"]}"'
                valuesStr = f"{valuesStr}, ?"

        # Remove the first ',' from columnsStr and valuesStr.
        if len(columnsStr) > 0:
            columnsStr = columnsStr[1:]
            valuesStr = valuesStr[1:]

        # Map the column names to plugin object event values and create a list of tuples 'sqlParams'.
        for plgEv in pluginEvents:
            tmpList = []

            for col in mappedCols:
                if col["column"] == "Index":
                    tmpList.append(plgEv.index)
                elif col["column"] == "Plugin":
                    tmpList.append(plgEv.pluginPref)
                elif col["column"] == "Object_PrimaryID":
                    tmpList.append(plgEv.primaryId)
                elif col["column"] == "Object_SecondaryID":
                    tmpList.append(plgEv.secondaryId)
                elif col["column"] == "DateTimeCreated":
                    tmpList.append(plgEv.created)
                elif col["column"] == "DateTimeChanged":
                    tmpList.append(plgEv.changed)
                elif col["column"] == "Watched_Value1":
                    tmpList.append(plgEv.watched1)
                elif col["column"] == "Watched_Value2":
                    tmpList.append(plgEv.watched2)
                elif col["column"] == "Watched_Value3":
                    tmpList.append(plgEv.watched3)
                elif col["column"] == "Watched_Value4":
                    tmpList.append(plgEv.watched4)
                elif col["column"] == "UserData":
                    tmpList.append(plgEv.userData)
                elif col["column"] == "Extra":
                    tmpList.append(plgEv.extra)
                elif col["column"] == "Status":
                    tmpList.append(plgEv.status)
                elif col["column"] == "SyncHubNodeName":
                    tmpList.append(plgEv.syncHubNodeName)
                elif col["column"] == "HelpVal1":
                    tmpList.append(plgEv.helpVal1)
                elif col["column"] == "HelpVal2":
                    tmpList.append(plgEv.helpVal2)
                elif col["column"] == "HelpVal3":
                    tmpList.append(plgEv.helpVal3)
                elif col["column"] == "HelpVal4":
                    tmpList.append(plgEv.helpVal4)

                # Check if there's a default value specified for this column in the JSON.
                if (
                    "mapped_to_column_data" in col and "value" in col["mapped_to_column_data"]
                ):
                    tmpList.append(col["mapped_to_column_data"]["value"])

            # Append the mapped values to the list 'sqlParams' as a tuple.
            sqlParams.append(tuple(tmpList))

        # Generate the SQL INSERT query using the collected information.
        q = f"INSERT OR IGNORE INTO {dbTable} ({columnsStr}) VALUES ({valuesStr})"

        # Log a debug message showing the generated SQL query for mapping.
        mylog("debug", f"[Plugins] SQL query for mapping: {q}")
        mylog("debug", f"[Plugins] SQL sqlParams for mapping: {sqlParams}")

        # Execute the SQL query using 'sql.executemany()' and the 'sqlParams' list of tuples.
        # This will insert multiple rows into the database in one go.
        sql.executemany(q, sqlParams)

        db.commitDB()

        # perform scan if mapped to CurrentScan table
        if dbTable == "CurrentScan":
            updateState(
                "Process scan: True", None, None, None, None, True
            )  # set processScan = True in the appState

    db.commitDB()

    return


# -------------------------------------------------------------------------------
class plugin_object_class:
    def __init__(self, plugin, objDbRow):
        self.index = objDbRow[0]
        self.pluginPref = objDbRow[1]
        self.primaryId = objDbRow[2]
        self.secondaryId = objDbRow[3]
        self.created = objDbRow[4]  # can be null
        self.changed = objDbRow[5]  # never null (data coming from plugin)
        self.watched1 = objDbRow[6]
        self.watched2 = objDbRow[7]
        self.watched3 = objDbRow[8]
        self.watched4 = objDbRow[9]
        self.status = objDbRow[10]
        self.extra = objDbRow[11]
        self.userData = objDbRow[12]
        self.foreignKey = objDbRow[13]
        self.syncHubNodeName = objDbRow[14]
        self.helpVal1 = objDbRow[15]
        self.helpVal2 = objDbRow[16]
        self.helpVal3 = objDbRow[17]
        self.helpVal4 = objDbRow[18]
        self.objectGUID = generate_deterministic_guid(
            self.pluginPref, self.primaryId, self.secondaryId
        )

        # Check if self.status is valid
        if self.status not in [
            "exists",
            "watched-changed",
            "watched-not-changed",
            "new",
            "not-processed",
            "missing-in-last-scan",
        ]:
            raise ValueError(
                f"Invalid status value for plugin object ({self.pluginPref}|{self.primaryId}|{self.watched1}) invalid status: {self.status} on objDbRow:",
                objDbRow,
            )

        self.idsHash = str(hash(str(self.primaryId) + str(self.secondaryId)))
        # self.idsHash      = str(self.primaryId) + str(self.secondaryId)

        self.watchedClmns = []
        self.watchedIndxs = []

        setObj = get_plugin_setting_obj(plugin, "WATCH")

        # hash for comapring watched value changes
        indexNameColumnMapping = [
            (6, "Watched_Value1"),
            (7, "Watched_Value2"),
            (8, "Watched_Value3"),
            (9, "Watched_Value4"),
        ]

        if setObj is not None:
            self.watchedClmns = setObj["value"]

            for clmName in self.watchedClmns:
                for mapping in indexNameColumnMapping:
                    if clmName == mapping[1]:
                        self.watchedIndxs.append(mapping[0])

        tmp = ""
        for indx in self.watchedIndxs:
            tmp += str(objDbRow[indx])

        self.watchedHash = str(hash(tmp))

    def __repr__(self):
        attrs = vars(self)
        return (
            "<PluginObject " + ", ".join(f"{k}={v!r}" for k, v in attrs.items()) + ">"
        )
