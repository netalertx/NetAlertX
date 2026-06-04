import os
import json
from collections import namedtuple
import conf
from logger import mylog
from utils.crypto_utils import decrypt_data
from const import pluginsPath, apiPath
from helper import (
    get_file_content,
    get_setting_value,
    setting_value_to_python_type,
)

module_name = "Plugin utils"


# -------------------------------------------------------------------------------
def logEventStatusCounts(objName, pluginEvents):
    status_counts = {}  # Dictionary to store counts for each status

    for event in pluginEvents:
        status = event.status
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts[status] = 1

    for status, count in status_counts.items():
        mylog("debug", [f'[{module_name}] In {objName} there are {count} events with the status "{status}" '],)


# -------------------------------------------------------------------------------
def print_plugin_info(plugin, elements=["display_name"]):
    mylog("verbose", [f"[{module_name}] ---------------------------------------------"])

    for el in elements:
        res = get_plugin_string(plugin, el)
        mylog("verbose", [f"[{module_name}] ", el, ": ", res])


# -------------------------------------------------------------------------------
# Gets the whole setting object
def get_plugin_setting_obj(plugin, function_key):
    result = None

    for set in plugin["settings"]:
        if set["function"] == function_key:
            result = set

    # if result == None:
    #     mylog('debug', [f'[{module_name}] Setting with "function":"', function_key, '" is missing in plugin: ', get_plugin_string(plugin, 'display_name')])

    return result


# -------------------------------------------------------------------------------
# Gets the setting value for a plugin from the default JSON
def get_plugin_setting_value(plugin, function_key):
    result = None

    for set in plugin["settings"]:
        if set["function"] == function_key:
            result = set

    # if result == None:
    #     mylog('debug', [f'[{module_name}] Setting with "function":"', function_key, '" is missing in plugin: ', get_plugin_string(plugin, 'display_name')])

    return result


# -------------------------------------------------------------------------------
# Get localized string value on the top JSON depth, not recursive
def get_plugin_string(props, el):
    result = ""

    if el in props["localized"]:
        for val in props[el]:
            if val["language_code"] == "en_us":
                result = val["string"]

        if result == "":
            result = "en_us string missing"

    else:
        result = props[el]

    return result


# -------------------------------------------------------------------------------
#  generates a comma separated list of values from a list (or a string representing a list)
def list_to_csv(arr):
    tmp = ""
    arrayItemStr = ""

    mylog("debug", f"[{module_name}] Flattening the below array")
    mylog("debug", arr)
    mylog("debug", f"[{module_name}] isinstance(arr, list) : {isinstance(arr, list)} | isinstance(arr, str) : {isinstance(arr, str)}",)

    if isinstance(arr, str):
        tmpStr = (
            arr.replace("[", "").replace("]", "").replace("'", "")
        )  # removing brackets and single quotes (not allowed)

        if "," in tmpStr:
            # Split the string into a list and trim whitespace
            cleanedStr = [tmpSubStr.strip() for tmpSubStr in tmpStr.split(",")]

            # Join the list elements using a comma
            result_string = ",".join(cleanedStr)
        else:
            result_string = tmpStr

        return result_string

    elif isinstance(arr, list):
        for arrayItem in arr:
            # only one column flattening is supported
            if isinstance(arrayItem, list):
                arrayItemStr = (
                    str(arrayItem[0]).replace("'", "").strip()
                )  # removing single quotes - not allowed
            else:
                # is string already
                arrayItemStr = arrayItem

            tmp += f"{arrayItemStr},"

        tmp = tmp[:-1]  # Remove last comma ','

        mylog("debug", f"[{module_name}] Flattened array: {tmp}")

        return tmp

    else:
        mylog("none", f"[{module_name}] ⚠ ERROR Could not convert array: {arr}")


# -------------------------------------------------------------------------------
# Combine plugin objects, keep user-defined values, created time, changed time if nothing changed and the index
def combine_plugin_objects(old, new):
    new.userData = old.userData
    new.index = old.index
    new.created = old.created

    # Keep changed time if nothing changed
    if new.status in ["watched-not-changed"]:
        new.changed = old.changed

    #  return the new object, with some of the old values
    return new


# -------------------------------------------------------------------------------
# Replace {wildcars} with parameters
def resolve_wildcards_arr(commandArr, params):
    mylog("debug", [f"[{module_name}] Pre-Resolved CMD: "] + commandArr)

    for param in params:
        # mylog('debug', ['[Plugins] key     : {', param[0], '}'])
        # mylog('debug', ['[Plugins] resolved: ', param[1]])

        i = 0

        for comPart in commandArr:
            commandArr[i] = comPart.replace(
                "{" + str(param[0]) + "}", str(param[1])
            ).replace("{s-quote}", "'")

            i += 1

    return commandArr


# -------------------------------------------------------------------------------
# Function to extract layer number from "execution_order"
def get_layer(plugin):
    order = plugin.get("execution_order", "Layer_N")
    if order == "Layer_N":
        return float("inf")  # Treat as the last layer if "execution_order" is missing
    return int(order.split("_")[1])


# -------------------------------------------------------------------------------
def get_plugins_configs(loadAll):
    pluginsList = []  # Create an empty list to store plugin configurations
    pluginsListSorted = []  # Sorted by "execution_order" : "Layer_0" first, Layer_N last

    # Get a list of top-level directories in the specified pluginsPath
    dirs = next(os.walk(pluginsPath))[1]

    # Sort the directories list if needed
    dirs.sort()  # This will sort the directories alphabetically

    # Loop through each directory (plugin folder) in dirs
    for d in dirs:
        # Check if the directory name does not start with "__" to skip python cache
        if not d.startswith("__"):
            # Check if the 'ignore_plugin' file exists in the plugin folder
            ignore_plugin_path = os.path.join(pluginsPath, d, "ignore_plugin")
            if not os.path.isfile(ignore_plugin_path):
                # Construct the path to the config.json file within the plugin folder
                config_path = os.path.join(pluginsPath, d, "config.json")

                try:
                    plugJson = json.loads(get_file_content(config_path))

                    # Only load plugin if needed
                    # Fetch the list of enabled plugins from the config, default to an empty list if not set
                    enabledPlugins = getattr(conf, "LOADED_PLUGINS", [])

                    # Load all plugins if `loadAll` is True, the plugin is in the enabled list,
                    # or no specific plugins are enabled (enabledPlugins is empty)
                    if (
                        loadAll or plugJson["unique_prefix"] in enabledPlugins or enabledPlugins == []
                    ):
                        # Load the contents of the config.json file as a JSON object and append it to pluginsList
                        pluginsList.append(plugJson)

                except (FileNotFoundError, json.JSONDecodeError):
                    # Handle the case when the file is not found or JSON decoding fails
                    mylog("none", f"[{module_name}] ⚠ ERROR - JSONDecodeError or FileNotFoundError for file {config_path}")
                except Exception as e:
                    mylog("none", f"[{module_name}] ⚠ ERROR - Exception for file {config_path}: {str(e)}")

    # Sort pluginsList based on "execution_order"
    pluginsListSorted = sorted(pluginsList, key=get_layer)

    return pluginsListSorted  # Return the sorted list of plugin configurations


# -------------------------------------------------------------------------------
def custom_plugin_decoder(pluginDict):
    return namedtuple("X", pluginDict.keys())(*pluginDict.values())


# -------------------------------------------------------------------------------
# Handle empty value
def handle_empty(value):
    if value == "" or value is None:
        value = "null"

    return value


# -------------------------------------------------------------------------------
# Get and return a plugin object based on key-value pairs
# keyValues example: getPluginObject({"plugin":"MQTT", "watchedValue4":"someValue"})
def getPluginObject(keyValues):
    plugins_objects = apiPath + "table_plugins_objects.json"

    try:
        with open(plugins_objects, "r") as json_file:
            data = json.load(json_file)

            objectEntries = data.get("data", [])

            for item in objectEntries:
                # Initialize a flag to check if all key-value pairs match
                all_match = True

                for key, value in keyValues.items():
                    if item.get(key) != value:
                        all_match = False
                        break  # No need to continue checking if one pair doesn't match

                if all_match:
                    return item

            mylog("verbose", f"[{module_name}] 💬 INFO - Object not found {json.dumps(keyValues)} ")

            return {}

    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        # Handle the case when the file is not found, JSON decoding fails, or data is not in the expected format
        mylog("verbose", f"[{module_name}] ⚠ ERROR - JSONDecodeError or FileNotFoundError for file {plugins_objects}")

        return {}


# ------------------------------------------------------------------
# decode any encoded last_result files
def decode_and_rename_files(file_dir, file_prefix):
    """
    Decodes and renames files in the specified directory if they are encrypted.
    Returns a list of files to be processed and the Sync Hub Node name.
    """
    # Initialize the list of files to be processed and Sync Hub Node name
    files_to_process = []

    # key to decrypt data if SYNC loaded and key available
    encryption_key = None
    if "SYNC" in get_setting_value("LOADED_PLUGINS"):
        encryption_key = get_setting_value("SYNC_encryption_key")

    # Check for files starting with the specified prefix
    matching_files = [f for f in os.listdir(file_dir) if f.startswith(file_prefix)]

    for filename in matching_files:
        # Create the full file path
        file_path = os.path.join(file_dir, filename)

        # Check if the file exists
        if os.path.exists(file_path):
            # Check if the file name contains "encoded"
            if ".encoded." in filename and encryption_key:
                # Decrypt the entire file
                with open(file_path, "r+") as f:
                    encrypted_data = f.read()
                    decrypted_data = decrypt_data(encrypted_data, encryption_key)

                    # Write the decrypted data back to the file
                    f.seek(0)
                    f.write(decrypted_data)
                    f.truncate()

                    # Rename the file e.g. from last_result.encoded.Node_1.1.log to last_result.decoded.Node_1.1.log
                    new_filename = filename.replace(".encoded.", ".decoded.")
                    os.rename(file_path, os.path.join(file_dir, new_filename))

                    files_to_process.append(new_filename)

            else:
                files_to_process.append(filename)
        else:
            mylog("debug", [f"[Plugins] The file {file_path} does not exist"])

    return files_to_process


# ------------------------------------------------------------------
# Retrieve the value for a plugin's setting, prioritizing user-defined values over defaults.
def get_set_value_for_init(plugin, c_d, setting_key):
    """
    Retrieve the value for a plugin's setting, prioritizing user-defined values over defaults.

    Args:
        plugin (str): The name or identifier of the plugin.
        pref (str): Prefix for user-defined settings (e.g., plugin identifier prefix).
        c_d (dict): Dictionary containing user-defined settings.
        setting_key (str): The key for the setting to fetch (default is 'RUN').

    Returns:
        Any: The value for the specified setting, converted to an appropriate Python type.
    """

    pref = plugin["unique_prefix"]

    # Step 1: Initialize the setting value as an empty string
    setting_value = ""

    # Step 2: Get the default setting object for the plugin's specified key
    setting_obj = get_plugin_setting_obj(plugin, setting_key)

    if setting_obj is not None:
        # Retrieve the type and default value from the setting object
        set_type = setting_obj.get("type")  # Lowercase 'type'
        set_value = setting_obj.get("default_value")

        # Convert the value to the appropriate Python type
        setting_value = setting_value_to_python_type(set_type, set_value)

    # Step 3: Check for user-defined setting value in the dictionary
    user_key = f"{pref}_{setting_key}"
    if user_key in c_d:
        setting_value = c_d[user_key]

    # Return the final setting value
    return setting_value
