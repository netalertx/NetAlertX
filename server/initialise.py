import os
from pytz import timezone, all_timezones, UnknownTimeZoneError
from cron_converter import Cron
from pathlib import Path
import datetime
import json
import shutil
import re
import uuid

# Register NetAlertX libraries
import conf
from const import fullConfPath, fullConfFolder, default_tz
from helper import getBuildTimeStampAndVersion, collect_lang_strings, updateSubnets, generate_random_string
from utils.datetime_utils import timeNowUTC
from app_state import updateState
from logger import mylog
from api import update_api
from scheduler import schedule_class
from plugin import plugin_manager, print_plugin_info
from utils.plugin_utils import get_plugins_configs, get_set_value_for_init
from messaging.in_app import write_notification

# ===============================================================================
# Initialise user defined values
# ===============================================================================

# -------------------------------------------------------------------------------
# Import user values
# Check config dictionary


# -------------------------------------------------------------------------------
# managing application settings, ensuring SQL safety for user input, and updating internal configuration lists
def ccd(
    key,
    default,
    config_dir,
    name,
    inputtype,
    options,
    group,
    events=None,
    desc="",
    setJsonMetadata=None,
    overrideTemplate=None,
    forceDefault=False,
    overriddenByEnv=0,
    all_plugins=[],
):
    if events is None:
        events = []
    if setJsonMetadata is None:
        setJsonMetadata = {}
    if overrideTemplate is None:
        overrideTemplate = {}

    # Use default initialization value
    result = default

    # Use existing value if already supplied, otherwise default value is used
    if forceDefault is False and key in config_dir:
        result = config_dir[key]

    # Single quotes might break SQL queries, replacing them
    if inputtype == "text":
        result = result.replace("'", "{s-quote}")

    # Add to config_dir and update plugin value if overridden by environment
    if overriddenByEnv == 1:
        config_dir[key] = result
        for plugin in all_plugins:
            pref = plugin["unique_prefix"]

            for set in plugin["settings"]:
                setFunction = set["function"]
                # Setting code name / key
                plugKey = pref + "_" + setFunction

                if plugKey == key:
                    set["value"] = result

    #  prepare SQL for DB update
    # Create the tuples
    sql_safe_tuple = (
        key,
        name,
        desc,
        str(inputtype),
        options,
        str(result),
        group,
        str(events),
        overriddenByEnv,
    )
    settings_tuple = (
        key,
        name,
        desc,
        inputtype,
        options,
        result,
        group,
        str(events),
        overriddenByEnv,
    )

    # Update or append the tuples in the lists
    conf.mySettingsSQLsafe = update_or_append(
        conf.mySettingsSQLsafe, sql_safe_tuple, key
    )
    conf.mySettings = update_or_append(conf.mySettings, settings_tuple, key)

    # Save metadata in dummy setting if not a metadata key
    if "__metadata" not in key:
        metadata_tuple = (
            f"{key}__metadata",
            "metadata name",
            "metadata desc",
            '{"dataType":"json", "elements": [{"elementType" : "textarea", "elementOptions" : [{"readonly": "true"}] ,"transformers": []}]}',
            "[]",
            json.dumps(setJsonMetadata),
            group,
            "[]",
            overriddenByEnv,
        )
        conf.mySettingsSQLsafe = update_or_append(
            conf.mySettingsSQLsafe, metadata_tuple, f"{key}__metadata"
        )
        conf.mySettings = update_or_append(
            conf.mySettings, metadata_tuple, f"{key}__metadata"
        )

    return result


# -------------------------------------------------------------------------------
# Function to find and update the existing key in the list
def update_or_append(settings_list, item_tuple, key):
    if settings_list is None:
        settings_list = []

    for index, item in enumerate(settings_list):
        if item[0] == key:
            mylog("trace", ["[Import Config] OLD TUPLE  : ", item])
            # Keep values marked as "_KEEP_" in existing entries
            updated_tuple = tuple(
                new_val if new_val != "_KEEP_" else old_val
                for old_val, new_val in zip(item, item_tuple)
            )
            mylog("trace", ["[Import Config] NEW TUPLE  : ", updated_tuple])
            settings_list[index] = updated_tuple
            mylog("trace", ["[Import Config] FOUND key : ", key])
            return settings_list

    # Append the item only if no values are "_KEEP_"
    if "_KEEP_" not in item_tuple:
        settings_list.append(item_tuple)
        mylog("trace", ["[Import Config] ADDED key : ", key])
    else:
        mylog("none", ["[Import Config] Skipped saving _KEEP_ for key : ", key])

    return settings_list


# -------------------------------------------------------------------------------


def importConfigs(pm, db, all_plugins):
    sql = db.sql

    # get config file name
    config_file = Path(fullConfPath)

    # Only import file if the file was modifed since last import.
    # this avoids time zone issues as we just compare the previous timestamp to the current time stamp

    # rename settings that have changed names due to code cleanup and migration to plugins
    # renameSettings(config_file)

    fileModifiedTime = os.path.getmtime(config_file)

    mylog("debug", ["[Import Config] checking config file "])
    mylog("debug", ["[Import Config] lastImportedConfFile     :", conf.lastImportedConfFile],)
    mylog("debug", ["[Import Config] fileModifiedTime         :", fileModifiedTime])

    if (fileModifiedTime == conf.lastImportedConfFile) and all_plugins is not None:
        mylog("debug", ["[Import Config] skipping config file import"])
        return pm, all_plugins, False

    # Header
    updateState("Import config", showSpinner=True)

    # remove all plugin language strings
    sql.execute("DELETE FROM Plugins_Language_Strings;")
    db.commitDB()

    mylog("debug", ["[Import Config] importing config file"])
    conf.mySettings = []  # reset settings
    conf.mySettingsSQLsafe = []  # same as above but safe to be passed into a SQL query

    # User values loaded from now
    c_d = read_config_file(config_file)

    # Import setting if found in the dictionary

    # General
    # ----------------------------------------
    # ccd(key, default, config_dir, name, inputtype, options, group, events=[], desc = "", regex = "", setJsonMetadata = {}, overrideTemplate = {})

    conf.LOADED_PLUGINS = ccd(
        "LOADED_PLUGINS",
        [],
        c_d,
        "Loaded plugins",
        '{"dataType":"array","elements":[{"elementType":"select","elementHasInputValue":1,"elementOptions":[{"multiple":"true","ordeable":"true"}],"transformers":[]},{"elementType":"button","elementOptions":[{"sourceSuffixes":[]},{"separator":""},{"cssClasses":"col-xs-12"},{"onClick":"selectChange(this)"},{"getStringKey":"Gen_Change"}],"transformers":[]}]}',  # noqa: E501
        "[]",
        "General",
    )
    conf.DISCOVER_PLUGINS = ccd(
        "DISCOVER_PLUGINS",
        True,
        c_d,
        "Discover plugins",
        """{"dataType": "boolean","elements": [{"elementType": "input","elementOptions": [{ "type": "checkbox" }],"transformers": []}]}""",
        "[]",
        "General",
    )
    conf.SCAN_SUBNETS = ccd(
        "SCAN_SUBNETS",
        ["192.168.1.0/24 --interface=eth1", "192.168.1.0/24 --interface=eth0"],
        c_d,
        "Subnets to scan",
        """{"dataType": "array","elements": [{"elementType": "input","elementOptions": [{"placeholder": "192.168.1.0/24 --interface=eth1"},{"suffix": "_in"},{"cssClasses": "col-sm-10"},{"prefillValue": "null"}],"transformers": []},{"elementType": "button","elementOptions": [{"sourceSuffixes": ["_in"]},{"separator": ""},{"cssClasses": "col-xs-12"},{"onClick": "addList(this, false)"},{"getStringKey": "Gen_Add"}],"transformers": []},{"elementType": "select","elementHasInputValue": 1,"elementOptions": [{"multiple": "true"},{"readonly": "true"},{"editable": "true"}],"transformers": []},{"elementType": "button","elementOptions": [{"sourceSuffixes": []},{"separator": ""},{"cssClasses": "col-xs-6"},{"onClick": "removeAllOptions(this)"},{"getStringKey": "Gen_Remove_All"}],"transformers": []},{"elementType": "button","elementOptions": [{"sourceSuffixes": []},{"separator": ""},{"cssClasses": "col-xs-6"},{"onClick": "removeFromList(this)"},{"getStringKey": "Gen_Remove_Last"}],"transformers": []}]}""",   # noqa: E501 - inline JSON
        "[]",
        "General",
    )
    conf.LOG_LEVEL = ccd(
        "LOG_LEVEL",
        "verbose",
        c_d,
        "Log verboseness",
        '{"dataType":"string", "elements": [{"elementType" : "select", "elementOptions" : [] ,"transformers": []}]}',
        "['none', 'minimal', 'verbose', 'debug', 'trace']",
        "General",
    )
    conf.TIMEZONE = ccd(
        "TIMEZONE",
        default_tz,
        c_d,
        "Time zone",
        '{"dataType":"string", "elements": [{"elementType" : "input", "elementOptions" : [] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.PLUGINS_KEEP_HIST = ccd(
        "PLUGINS_KEEP_HIST",
        250,
        c_d,
        "Keep history entries",
        '{"dataType":"integer", "elements": [{"elementType" : "input", "elementOptions" : [{"type": "number"}] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.REPORT_DASHBOARD_URL = ccd(
        "REPORT_DASHBOARD_URL",
        "update_REPORT_DASHBOARD_URL_setting",
        c_d,
        "NetAlertX URL",
        '{"dataType":"string", "elements": [{"elementType" : "input", "elementOptions" : [] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.BACKEND_API_URL = ccd(
        "BACKEND_API_URL",
        "/server",
        c_d,
        "API URL",
        '{"dataType":"string", "elements": [{"elementType" : "input", "elementOptions" : [] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.DAYS_TO_KEEP_EVENTS = ccd(
        "DAYS_TO_KEEP_EVENTS",
        90,
        c_d,
        "Delete events days",
        '{"dataType":"integer", "elements": [{"elementType" : "input", "elementOptions" : [{"type": "number"}] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.HRS_TO_KEEP_NEWDEV = ccd(
        "HRS_TO_KEEP_NEWDEV",
        0,
        c_d,
        "Keep new devices for",
        '{"dataType":"integer", "elements": [{"elementType" : "input", "elementOptions" : [{"type": "number"}] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.HRS_TO_KEEP_OFFDEV = ccd(
        "HRS_TO_KEEP_OFFDEV",
        0,
        c_d,
        "Keep offline devices for",
        '{"dataType":"integer", "elements": [{"elementType" : "input", "elementOptions" : [{"type": "number"}] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.CLEAR_NEW_FLAG = ccd(
        "CLEAR_NEW_FLAG",
        0,
        c_d,
        "Clear new flag",
        '{"dataType":"integer", "elements": [{"elementType" : "input", "elementOptions" : [{"type": "number"}] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.REFRESH_FQDN = ccd(
        "REFRESH_FQDN",
        False,
        c_d,
        "Refresh FQDN",
        """{"dataType": "boolean","elements": [{"elementType": "input","elementOptions": [{ "type": "checkbox" }],"transformers": []}]}""",
        "[]",
        "General",
    )
    conf.API_CUSTOM_SQL = ccd(
        "API_CUSTOM_SQL",
        "SELECT * FROM Devices WHERE devPresentLastScan = 0",
        c_d,
        "Custom endpoint",
        '{"dataType":"string", "elements": [{"elementType" : "input", "elementOptions" : [] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.VERSION = ccd(
        "VERSION",
        "",
        c_d,
        "Version",
        '{"dataType":"string", "elements": [{"elementType" : "input", "elementOptions" : [{ "readonly": "true" }] ,"transformers": []}]}',
        "",
        "General",
    )
    conf.NETWORK_DEVICE_TYPES = ccd(
        "NETWORK_DEVICE_TYPES",
        [
            "AP",
            "Access Point",
            "Gateway",
            "Firewall",
            "Hypervisor",
            "Powerline",
            "Switch",
            "WLAN",
            "PLC",
            "Router",
            "USB LAN Adapter",
            "USB WIFI Adapter",
            "internet",
        ],
        c_d,
        "Network device types",
        '{"dataType":"array","elements":[{"elementType":"input","elementOptions":[{"placeholder":"Enter value"},{"suffix":"_in"},{"cssClasses":"col-sm-10"},{"prefillValue":"null"}],"transformers":[]},{"elementType":"button","elementOptions":[{"sourceSuffixes":["_in"]},{"separator":""},{"cssClasses":"col-xs-12"},{"onClick":"addList(this,false)"},{"getStringKey":"Gen_Add"}],"transformers":[]},{"elementType":"select",	"elementHasInputValue":1,"elementOptions":[{"multiple":"true"},{"readonly":"true"},{"editable":"true"}],"transformers":[]},{"elementType":"button","elementOptions":[{"sourceSuffixes":[]},{"separator":""},{"cssClasses":"col-xs-6"},{"onClick":"removeAllOptions(this)"},{"getStringKey":"Gen_Remove_All"}],"transformers":[]},{"elementType":"button","elementOptions":[{"sourceSuffixes":[]},{"separator":""},{"cssClasses":"col-xs-6"},{"onClick":"removeFromList(this)"},{"getStringKey":"Gen_Remove_Last"}],"transformers":[]}]}',   # noqa: E501 - inline JSON
        "[]",
        "General",
    )
    conf.GRAPHQL_PORT = ccd(
        "GRAPHQL_PORT",
        20212,
        c_d,
        "GraphQL port",
        '{"dataType":"integer", "elements": [{"elementType" : "input", "elementOptions" : [{"type": "number"}] ,"transformers": []}]}',
        "[]",
        "General",
    )
    conf.API_TOKEN = ccd(
        "API_TOKEN",
        "t_" + generate_random_string(20),
        c_d,
        "API token",
        '{"dataType": "string","elements": [{"elementType": "input","elementHasInputValue": 1,"elementOptions": [{ "cssClasses": "col-xs-12" }],"transformers": []},{"elementType": "button","elementOptions": [{ "getStringKey": "Gen_Generate" },{ "customParams": "API_TOKEN" },{ "onClick": "generateApiToken(this, 20)" },{ "cssClasses": "col-xs-12" }],"transformers": []}]}',   # noqa: E501 - inline JSON
        "[]",
        "General",
    )
    conf.SYNC_node_name = ccd(
        "SYNC_node_name",
        "NAX-" + str(uuid.uuid4()).split('-')[0],
        c_d,
        "Sync node name",
        '{"dataType": "string","elements": [{"elementType": "input","elementHasInputValue": 1,"elementOptions": [{ "cssClasses": "col-xs-12" }],"transformers": []},{"elementType": "button","elementOptions": [{ "getStringKey": "Gen_Generate" },{ "customParams": "SYNC_node_name" },{ "onClick": "generateNaxNodeName(this)" },{ "cssClasses": "col-xs-12" }],"transformers": []}]}',   # noqa: E501 - inline JSON
        "[]",
        "General",
    )

    # UI
    conf.UI_LANG = ccd(
        "UI_LANG",
        "English (en_us)",
        c_d,
        "Language Interface",
        '{"dataType":"string", "elements": [{"elementType" : "select", "elementOptions" : [] ,"transformers": []}]}',
        "['English (en_us)', 'Arabic (ar_ar)', 'Catalan (ca_ca)', 'Czech (cs_cz)', 'German (de_de)', 'Spanish (es_es)', 'Farsi (fa_fa)', 'French (fr_fr)', 'Italian (it_it)', 'Japanese (ja_jp)', 'Norwegian (nb_no)', 'Polish (pl_pl)', 'Portuguese (pt_br)', 'Portuguese (pt_pt)', 'Russian (ru_ru)', 'Swedish (sv_sv)', 'Turkish (tr_tr)', 'Ukrainian (uk_ua)', 'Vietnamese (vi_vn)', 'Chinese (zh_cn)']",   # noqa: E501 - inline JSON
        "UI",
    )

    #  Init timezone in case it changed and handle invalid values
    try:
        if conf.TIMEZONE not in all_timezones:
            raise UnknownTimeZoneError(f"Invalid timezone: {conf.TIMEZONE}")
        conf.tz = timezone(conf.TIMEZONE)
    except UnknownTimeZoneError:
        conf.tz = timezone(default_tz)  # Init Default
        conf.TIMEZONE = ccd(
            "TIMEZONE", conf.tz, c_d, "_KEEP_", "_KEEP_", "[]", "General"
        )
        mylog("none", [f"[Config] Invalid timezone '{conf.TIMEZONE}', defaulting to {default_tz}."],)

    # TODO cleanup later ----------------------------------------------------------------------------------
    # init all time values as we have timezone - all this shoudl be moved into plugin/plugin settings
    conf.time_started = timeNowUTC(as_string=False)
    conf.plugins_once_run = False

    # timestamps of last execution times
    conf.startTime = conf.time_started
    now_minus_24h = conf.time_started - datetime.timedelta(hours=24)

    # set these times to the past to force the first run
    conf.last_scan_run = now_minus_24h
    conf.last_version_check = now_minus_24h

    # TODO cleanup later ----------------------------------------------------------------------------------

    # reset schedules
    conf.mySchedules = []

    # Format and prepare the list of subnets
    conf.userSubnets = updateSubnets(conf.SCAN_SUBNETS)

    # Plugins START
    # -----------------

    # necessary_plugins = ['UI', 'CUSTPROP', 'CLOUD' ,'DBCLNP', 'INTRNT','MAINT','NEWDEV', 'SETPWD', 'SYNC', 'VNDRPDT', 'WORKFLOWS']
    necessary_plugins = [
        "UI",
        "CUSTPROP",
        "DBCLNP",
        "INTRNT",
        "MAINT",
        "NEWDEV",
        "SETPWD",
        "SYNC",
        "VNDRPDT",
        "WORKFLOWS",
    ]
    # make sure necessary plugins are loaded
    conf.LOADED_PLUGINS += [
        plugin for plugin in necessary_plugins if plugin not in conf.LOADED_PLUGINS
    ]

    all_plugins = get_plugins_configs(conf.DISCOVER_PLUGINS)

    mylog("none", ["[Config] Plugins: Number of all plugins (including not loaded): ", len(all_plugins),],)

    plugin_indexes_to_remove = []
    all_plugins_prefixes = []  # to init the LOADED_PLUGINS setting with correct options
    loaded_plugins_prefixes = []  # to init the LOADED_PLUGINS setting with correct initially selected values

    #  handle plugins
    index = 0
    for plugin in all_plugins:
        # Header on the frontend and the app_state.json
        updateState(f"Check plugin ({index}/{len(all_plugins)})")

        index += 1

        pref = plugin["unique_prefix"]

        all_plugins_prefixes.append(pref)

        # The below lines are used to determine if the plugin should be loaded, or skipped based on user settings (conf.LOADED_PLUGINS)
        # ...or based on if is already enabled, or if the default configuration loads the plugin (RUN function != disabled )

        # get run value (computationally expensive)
        plugin_run = get_set_value_for_init(plugin, c_d, "RUN")

        # only include loaded plugins, and the ones that are enabled
        if (
            pref in conf.LOADED_PLUGINS or plugin_run != "disabled" or plugin_run is None
        ):
            print_plugin_info(plugin, ["display_name", "description"])

            stringSqlParams = []

            # collect plugin level language strings
            stringSqlParams = collect_lang_strings(plugin, pref, stringSqlParams)

            for set in plugin["settings"]:
                setFunction = set["function"]
                # Setting code name / key
                key = pref + "_" + setFunction

                # set.get() - returns None if not found, set["options"] raises error
                #  ccd(key, default, config_dir, name, inputtype, options, group, events=[], desc = "", setJsonMetadata = {}):
                v = ccd(
                    key,
                    set["default_value"],
                    c_d,
                    set["name"][0]["string"],
                    set["type"],
                    str(set.get("options", [])),
                    group=pref,
                    events=set.get("events"),
                    desc=set["description"][0]["string"],
                    setJsonMetadata=set,
                )

                # Save the user defined value into the object
                set["value"] = v

                # Now check for popupForm inside elements → elementOptions
                elements = set.get("type", {}).get("elements", [])
                for element in elements:
                    for option in element.get("elementOptions", []):
                        if "popupForm" in option:
                            for popup_entry in option["popupForm"]:
                                popup_pref = (
                                    key + "_popupform_" + popup_entry.get("function", "")
                                )
                                stringSqlParams = collect_lang_strings(
                                    popup_entry, popup_pref, stringSqlParams
                                )

                # Collect settings related language strings
                # Creates an entry with key, for example ARPSCAN_CMD_name
                stringSqlParams = collect_lang_strings(
                    set, pref + "_" + set["function"], stringSqlParams
                )

            # Collect column related language strings
            for clmn in plugin.get("database_column_definitions", []):
                # Creates an entry with key, for example ARPSCAN_Object_PrimaryID_name
                stringSqlParams = collect_lang_strings(
                    clmn, pref + "_" + clmn.get("column", ""), stringSqlParams
                )

            #  bulk-import language strings
            sql.executemany(
                """INSERT INTO Plugins_Language_Strings ("Language_Code", "String_Key", "String_Value", "Extra") VALUES (?, ?, ?, ?)""",
                stringSqlParams,
            )

        else:
            # log which plugins to remove
            index_to_remove = 0
            for plugin in all_plugins:
                if plugin["unique_prefix"] == pref:
                    break
                index_to_remove += 1

            plugin_indexes_to_remove.append(index_to_remove)

    # remove plugin at index_to_remove from list
    # Sort the list of indexes in descending order to avoid index shifting issues
    plugin_indexes_to_remove.sort(reverse=True)
    for indx in plugin_indexes_to_remove:
        pref = all_plugins[indx]["unique_prefix"]
        mylog("none", [f"[Config] ⛔ Unloading {pref}"])
        all_plugins.pop(indx)

    # all_plugins has now only initialized plugins, get all prefixes
    for plugin in all_plugins:
        pref = plugin["unique_prefix"]
        loaded_plugins_prefixes.append(pref)

    # save the newly discovered plugins as options and default values
    conf.LOADED_PLUGINS = ccd(
        "LOADED_PLUGINS",
        loaded_plugins_prefixes,
        c_d,
        "_KEEP_",
        "_KEEP_",
        str(sorted(all_plugins_prefixes)),
        "General",
    )

    mylog("none", ["[Config] Number of Plugins to load: ", len(loaded_plugins_prefixes)])
    mylog("none", ["[Config] Plugins to load: ", loaded_plugins_prefixes])

    conf.plugins_once_run = False

    # -----------------
    # HANDLE APP_CONF_OVERRIDE via app_conf_override.json

    app_conf_override_path = fullConfFolder + "/app_conf_override.json"

    if os.path.exists(app_conf_override_path):
        with open(app_conf_override_path, "r") as f:
            try:
                # Load settings_override from the JSON file
                settings_override = json.load(f)

                # Loop through settings_override dictionary
                for setting_name, value in settings_override.items():
                    # Ensure the value is treated as a string and passed directly
                    if isinstance(value, str) is False:
                        value = str(value)

                    # Log the value being passed
                    # ccd(key, default, config_dir, name, inputtype, options, group, events=None, desc="", setJsonMetadata=None, overrideTemplate=None, forceDefault=False)
                    mylog("verbose", [f"[Config] Setting override {setting_name} with value: {value}"],)
                    ccd(
                        setting_name,
                        value,
                        c_d,
                        "_KEEP_",
                        "_KEEP_",
                        "_KEEP_",
                        "_KEEP_",
                        None,
                        "_KEEP_",
                        None,
                        None,
                        True,
                        1,
                        all_plugins,
                    )

            except json.JSONDecodeError:
                mylog("none", [f"[Config] [ERROR] Setting override decoding JSON from {app_conf_override_path}"],)
    else:
        mylog("debug", [f"[Config] File {app_conf_override_path} does not exist."])

    # setup execution schedules AFTER OVERRIDE handling

    # mylog('verbose', [f"[Config] c_d {c_d}"])

    for plugin in all_plugins:
        # Setup schedules
        run_val = get_set_value_for_init(plugin, c_d, "RUN")
        run_sch = get_set_value_for_init(plugin, c_d, "RUN_SCHD")

        # mylog('verbose', [f"[Config] pref {plugin["unique_prefix"]} run_val {run_val} run_sch {run_sch} "])

        if run_val == "schedule":
            newSchedule = Cron(run_sch).schedule(
                start_date=timeNowUTC(as_string=False)
            )
            conf.mySchedules.append(
                schedule_class(
                    plugin["unique_prefix"], newSchedule, newSchedule.next(), False
                )
            )

    # mylog('verbose', [f"[Config] conf.mySchedules {conf.mySchedules}"])

    # -----------------
    # HANDLE APP was upgraded message - clear cache

    # Check if app was upgraded

    buildTimestamp, new_version = getBuildTimeStampAndVersion()
    prev_version = conf.VERSION if conf.VERSION != '' else "unknown"

    mylog('debug', [f"[Config] buildTimestamp | prev_version | .VERSION file: '{buildTimestamp}|{prev_version}|{new_version}'"])

    if str(prev_version) != str(new_version):

        mylog('none', ['[Config] App upgraded 🚀'])

        # ccd(key, default, config_dir, name, inputtype, options, group, events=None, desc="", setJsonMetadata=None, overrideTemplate=None, forceDefault=False)
        ccd('VERSION', new_version , c_d, '_KEEP_', '_KEEP_', '_KEEP_', '_KEEP_', None, "_KEEP_", None, None, True)

        write_notification(
            f"""[Upgrade]: App upgraded from <code>{prev_version}</code> to \
            <code>{new_version}</code> 🚀 Please clear the cache: \
            <ol> <li>Click OK below</li>  \
            <li>Clear the browser cache (shift + browser refresh button)</li> \
            <li> Clear app cache with the <i class="fa-solid fa-rotate"></i> (reload) button in the header</li>\
            <li>Go to Settings and click Save</li> </ol>\
            Check out new features and what has changed in the \
            <a href="https://github.com/jokob-sk/NetAlertX/releases" target="_blank">📓 release notes</a>.""",
            'interrupt',
            timeNowUTC()
        )

    # -----------------
    # Initialization finished, update DB and API endpoints

    # Insert settings into the DB
    sql.execute("DELETE FROM Settings")
    # mylog('debug', [f"[Config] conf.mySettingsSQLsafe  : '{conf.mySettingsSQLsafe}'"])
    sql.executemany(
        """INSERT INTO Settings ("setKey", "setName", "setDescription", "setType", "setOptions",
          "setValue", "setGroup", "setEvents", "setOverriddenByEnv" ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        conf.mySettingsSQLsafe,
    )

    db.commitDB()

    #  update only the settings datasource
    update_api(db, all_plugins, True, ["settings"])

    # run plugins that are modifying the config
    pm = plugin_manager(db, all_plugins)
    pm.clear_cache()
    pm.run_plugin_scripts("before_config_save")

    # Used to determine the next import
    conf.lastImportedConfFile = os.path.getmtime(config_file)

    # updateState(newState (text),
    #             settingsSaved = None (timestamp),
    #             settingsImported = None (timestamp),
    #             showSpinner = False (1/0),
    #             graphQLServerStarted = 1 (1/0))
    updateState("Config imported", conf.lastImportedConfFile, conf.lastImportedConfFile, False, 1, None, None, new_version, buildTimestamp)

    msg = '[Config] Imported new settings config'
    mylog('minimal', msg)

    # front end app log loggging
    write_notification(msg, 'info', timeNowUTC())

    return pm, all_plugins, True


# -------------------------------------------------------------------------------
def read_config_file(filename):
    """
    retuns dict on the config file key:value pairs
    """
    mylog("minimal", "[Config] reading config file")
    # load the variables from .conf file
    code = compile(filename.read_text(), filename.name, "exec")
    confDict = {}  # config dictionary
    exec(code, {"__builtins__": {}}, confDict)
    return confDict


# -------------------------------------------------------------------------------
# DEPRECATE soonest after 10/10/2024
# 🤔Idea/TODO: Check and compare versions/timestamps and only perform a replacement if config/version older than...
replacements = {
    r"\bREPORT_TO\b": "SMTP_REPORT_TO",
    r"\bSYNC_api_token\b": "API_TOKEN",
    r"\bAPI_TOKEN=\'\'": f"API_TOKEN='t_{generate_random_string(20)}'",
    r"\bSYNC_node_name=\'\'": f"SYNC_node_name='NAX-{str(uuid.uuid4()).split('-')[0]}'",
    # Detect SMTP_PASS='anything' BUT not starting with base64:
    r"SMTP_PASS='(?!base64:)([^']*)'": r"SMTP_PASS='base64:\1'",
}


def renameSettings(config_file):
    # Check if the file contains any of the old setting code names
    contains_old_settings = False

    # Open the original config_file for reading
    with open(
        str(config_file), "r"
    ) as original_file:  # Convert config_file to a string
        for line in original_file:
            # Use regular expressions with word boundaries to check for the old setting code names
            if any(re.search(key, line) for key in replacements.keys()):
                mylog("debug", f"[Config] Old setting names found in line: ({line})")
                contains_old_settings = True
                break  # Exit the loop if any old setting is found

    # If the file contains old settings, proceed with renaming and backup
    if contains_old_settings:
        # Create a backup file with the suffix "_old_setting_names" and timestamp
        timestamp = timeNowUTC(as_string=False).strftime("%Y%m%d%H%M%S")
        backup_file = f"{config_file}_old_setting_names_{timestamp}.bak"

        mylog("debug", f"[Config] Old setting names will be replaced and a backup ({backup_file}) of the config created.",)

        shutil.copy(str(config_file), backup_file)  # Convert config_file to a string

        # Open the original config_file for reading and create a temporary file for writing
        with (
            open(str(config_file), "r") as original_file,
            open(str(config_file) + "_temp", "w") as temp_file,
        ):  # Convert config_file to a string
            for line in original_file:
                # Use regular expressions with word boundaries for replacements
                for key, value in replacements.items():
                    line = re.sub(key, value, line)

                # Write the modified line to the temporary file
                temp_file.write(line)

        # Close both files
        original_file.close()
        temp_file.close()

        # Replace the original config_file with the temporary file
        shutil.move(
            str(config_file) + "_temp", str(config_file)
        )  # Convert config_file to a string

    else:
        mylog("debug", "[Config] No old setting names found in the file. No changes made.")
