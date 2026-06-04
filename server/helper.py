"""Colection of generic functions to support NetAlertX"""

import io
import sys
import datetime
import os
import re
import unicodedata
import subprocess
import json
import requests
import base64
import hashlib
import random
import string
import ipaddress

import conf
from const import applicationPath, fullConfPath, fullDbPath, dbPath, confPath, apiPath
from logger import mylog, logResult

# Register NetAlertX directories using runtime configuration
INSTALL_PATH = applicationPath


# -------------------------------------------------------------------------------
# File system permission handling
# -------------------------------------------------------------------------------
# check RW access of DB and config file
def checkPermissionsOK():
    # global confR_access, confW_access, dbR_access, dbW_access

    confR_access = os.access(fullConfPath, os.R_OK)
    confW_access = os.access(fullConfPath, os.W_OK)
    dbR_access = os.access(fullDbPath, os.R_OK)
    dbW_access = os.access(fullDbPath, os.W_OK)

    mylog("none", ["\n"])
    mylog("none", "The backend restarted (started). If this is unexpected check https://bit.ly/NetAlertX_debug for troubleshooting tips.")
    mylog("none", ["\n"])
    mylog("none", ["Permissions check (All should be True)"])
    mylog("none", ["------------------------------------------------"])
    mylog("none", ["  ", confPath, " | ", " READ  | ", confR_access])
    mylog("none", ["  ", confPath, " | ", " WRITE | ", confW_access])
    mylog("none", ["  ", dbPath, "       | ", " READ  | ", dbR_access])
    mylog("none", ["  ", dbPath, "       | ", " WRITE | ", dbW_access])
    mylog("none", ["------------------------------------------------"])

    # return dbR_access and dbW_access and confR_access and confW_access
    return (confR_access, dbR_access)


# -------------------------------------------------------------------------------
def initialiseFile(pathToCheck, defaultFile):
    # if file not readable (missing?) try to copy over the backed-up (default) one
    if str(os.access(pathToCheck, os.R_OK)) == "False":
        mylog("none", ["[Setup] (" + pathToCheck + ") file is not readable or missing. Trying to copy over the default one."],)
        try:
            # try runnning a subprocess
            p = subprocess.Popen(
                ["cp", defaultFile, pathToCheck],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            stdout, stderr = p.communicate()

            if str(os.access(pathToCheck, os.R_OK)) == "False":
                mylog("none", "[Setup] ⚠ ERROR copying (" + defaultFile + ") to (" + pathToCheck + "). Ensure Read & Write access to the parent directory.")
            else:
                mylog("none", ["[Setup] (" + defaultFile + ") copied over successfully to (" + pathToCheck + ")."],)

            # write stdout and stderr into .log files for debugging if needed
            logResult(stdout, stderr)  # TO-DO should be changed to mylog

        except subprocess.CalledProcessError as e:
            # An error occured, handle it
            mylog("none", ["[Setup] ⚠ ERROR copying (" + defaultFile + "). Make sure the app has Read & Write access to " + pathToCheck],)
            mylog("none", [e.output])


# -------------------------------------------------------------------------------
def filePermissions():
    # check and initialize .conf
    (confR_access, dbR_access) = checkPermissionsOK()  # Initial check

    if confR_access is False:
        initialiseFile(fullConfPath, f"{INSTALL_PATH}/back/app.conf")

    # check and initialize .db
    if dbR_access is False:
        initialiseFile(fullDbPath, f"{INSTALL_PATH}/back/app.db")


# -------------------------------------------------------------------------------
# File manipulation methods
# -------------------------------------------------------------------------------
# -------------------------------------------------------------------------------
def get_file_content(path):
    f = open(path, "r")
    content = f.read()
    f.close()

    return content


# -------------------------------------------------------------------------------
def write_file(pPath, pText):
    # Convert pText to a string if it's a dictionary
    if isinstance(pText, dict):
        pText = json.dumps(pText)

    # Convert pText to a string if it's a list
    if isinstance(pText, list):
        for item in pText:
            write_file(pPath, item)

    else:
        # Write the text using the correct Python version
        if sys.version_info < (3, 0):
            file = io.open(pPath, mode="w", encoding="utf-8")
            file.write(pText.decode("unicode_escape"))
            file.close()
        else:
            file = open(pPath, "w", encoding="utf-8")
            if pText is None:
                pText = ""
            file.write(pText)
            file.close()


# -------------------------------------------------------------------------------
# Setting methods
# -------------------------------------------------------------------------------

SETTINGS_CACHE = {}
SETTINGS_LASTCACHEDATE = 0
SETTINGS_SECONDARYCACHE = {}


# -------------------------------------------------------------------------------
#  Return whole setting touple
def get_setting(key):
    """
    Retrieve the full setting tuple (dictionary) for a given key from the JSON settings file.

    - Uses a cache to avoid re-reading the file if it hasn't changed.
    - Loads settings from `table_settings.json` located at `apiPath`.
    - Returns `None` if the key is not found or the file cannot be read.

    Args:
        key (str): The key of the setting to retrieve.

    Returns:
        dict | None: The setting dictionary for the key, or None if not found.
    """
    global SETTINGS_LASTCACHEDATE, SETTINGS_CACHE, SETTINGS_SECONDARYCACHE

    settingsFile = apiPath + "table_settings.json"
    try:
        fileModifiedTime = os.path.getmtime(settingsFile)
    except FileNotFoundError:
        mylog("none", [f"[Settings] ⚠ File not found: {settingsFile}"])
        return None

    mylog("trace", f"[Import table_settings.json] checking table_settings.json file SETTINGS_LASTCACHEDATE: {SETTINGS_LASTCACHEDATE} fileModifiedTime: {fileModifiedTime}")

    # Use cache if file hasn't changed
    if fileModifiedTime == SETTINGS_LASTCACHEDATE and SETTINGS_CACHE:
        mylog("trace", ["[Import table_settings.json] using cached version"])
        return SETTINGS_CACHE.get(key)

    # invalidate CACHE
    SETTINGS_CACHE = {}
    SETTINGS_SECONDARYCACHE = {}

    # Load JSON and populate cache
    try:
        with open(settingsFile, "r") as json_file:
            data = json.load(json_file)
            SETTINGS_CACHE = {item["setKey"]: item for item in data.get("data", [])}
    except json.JSONDecodeError:
        mylog("none", [f"[Settings] ⚠ JSON decode error in file {settingsFile}"])
        return None
    except ValueError as e:
        mylog("none", [f"[Settings] ⚠ Value error: {e} in file {settingsFile}"])
        return None

    # Only update file date when we successfully parsed the file
    SETTINGS_LASTCACHEDATE = fileModifiedTime

    if key not in SETTINGS_CACHE:
        mylog("verbose", [f"[Settings] INFO - setting_missing - {key} not in {settingsFile}"],)
        return None

    return SETTINGS_CACHE[key]


# -------------------------------------------------------------------------------
#  Return setting value
def get_setting_value(key, default=""):
    """
    Retrieve a setting value from configuration.

    - First checks if `conf.mySettings` is populated and contains the key.
    - Falls back to `get_setting(key)` if not found.
    - Converts the raw stored value into the correct Python type
      using `setting_value_to_python_type`.

    Args:
        key (str): The setting key to look up.
        default (Any): Value to return when the key is not found. Defaults
            to "" for backwards compatibility with call sites that already
            treat an empty string as "missing".

    Returns:
        Any: The Python-typed setting value, or `default` if not found.
    """

    # Returns default if not found
    value = default

    # lookup key in secondary cache
    if key in SETTINGS_SECONDARYCACHE:
        return SETTINGS_SECONDARYCACHE[key]
    # Prefer conf.mySettings if available
    if hasattr(conf, "mySettings") and conf.mySettings:
        # conf.mySettings is a list of tuples, find by key (tuple[0])
        for item in conf.mySettings:
            if item[0] == key:
                set_type = item[3]  # type
                set_value = item[5]  # value
                if isinstance(set_value, (list, dict)):
                    value = setting_value_to_python_type(set_type, set_value)
                else:
                    value = setting_value_to_python_type(set_type, str(set_value))

                SETTINGS_SECONDARYCACHE[key] = value

                return value

    # Otherwise fall back to retrieve from json
    setting = get_setting(key)

    if setting is not None:
        # mylog('none', [f'[SETTINGS] setting json:{json.dumps(setting)}'])

        set_type = "Error: Not handled"
        set_value = "Error: Not handled"

        set_value = setting[
            "setValue"
        ]  # Setting value (Value (upper case) = user overridden default_value)
        set_type = setting[
            "setType"
        ]  # Setting type  # lower case "type" - default json value vs uppper-case "setType" (= from user defined settings)

        value = setting_value_to_python_type(set_type, set_value)
        SETTINGS_SECONDARYCACHE[key] = value

    return value


# -------------------------------------------------------------------------------
#  Convert the setting value to the corresponding python type
def setting_value_to_python_type(set_type, set_value):
    value = "----not processed----"

    # "type": {"dataType":"array", "elements": [{"elementType" : "select", "elementOptions" : [{"multiple":"true"}] ,"transformers": []}]}

    setTypJSN = json.loads(str(set_type).replace('"', '"').replace("'", '"'))

    # Handle different types of settings based on set_type dictionary
    dataType = setTypJSN.get("dataType", "")
    elements = setTypJSN.get("elements", [])

    # Ensure there's at least one element in the elements list
    if not elements:
        mylog("none", [f"[HELPER] No elements provided in set_type: {set_type} "])
        return value

    # Find the first element where elementHasInputValue is 1
    element_with_input_value = next(
        (elem for elem in elements if elem.get("elementHasInputValue") == 1), None
    )

    # If no such element is found, use the last element
    if element_with_input_value is None:
        element_with_input_value = elements[-1]

    elementType = element_with_input_value.get("elementType", "")
    elementOptions = element_with_input_value.get("elementOptions", [])
    transformers = element_with_input_value.get("transformers", [])

    # Convert value based on dataType and elementType
    if dataType == "string" and elementType in [
        "input",
        "select",
        "textarea",
        "datatable",
    ]:
        value = reverseTransformers(str(set_value), transformers)

    elif dataType == "integer" and (elementType == "input" or elementType == "select"):
        # handle storing/retrieving boolean values as 1/0
        if set_value.lower() not in ["true", "false"] and isinstance(set_value, str):
            value = int(set_value)

        elif isinstance(set_value, bool):
            value = 1 if set_value else 0

        elif isinstance(set_value, str):
            value = 1 if set_value.lower() == "true" else 0

        else:
            value = int(set_value)

    # boolean handling
    elif dataType == "boolean" and elementType == "input":
        value = set_value.lower() in ["true", "1"]

    # array handling
    elif dataType == "array" and elementType == "select":
        if isinstance(set_value, str):
            try:
                value = json.loads(set_value.replace("'", "\""))

            except json.JSONDecodeError as e:
                mylog("none", [f"[setting_value_to_python_type] Error decoding JSON object: {e}"],)
                mylog("none", [set_value])
                value = []

        elif isinstance(set_value, list):
            value = set_value

        # Always apply transformers (base64, etc.) to array entries
        value = reverseTransformers(value, transformers)

    elif dataType == 'object' and elementType == 'input':
        if isinstance(set_value, str):
            try:
                value = reverseTransformers(json.loads(set_value), transformers)
            except json.JSONDecodeError as e:
                mylog("none", [f"[setting_value_to_python_type] Error decoding JSON object: {e}"],)
                mylog("none", [{set_value}])
                value = {}

        elif isinstance(set_value, dict):
            value = set_value

    elif (
        dataType == "string" and elementType == "input" and any(opt.get("readonly") == "true" for opt in elementOptions)
    ):
        value = reverseTransformers(str(set_value), transformers)

    elif (
        dataType == "string" and elementType == "input" and any(opt.get("type") == "password" for opt in elementOptions) and "sha256" in transformers
    ):
        value = hashlib.sha256(set_value.encode()).hexdigest()

    if value == "----not processed----":
        mylog("none", [f"[HELPER] ⚠ ERROR not processed set_type:  {set_type} "])
        mylog("none", [f"[HELPER] ⚠ ERROR not processed set_value: {set_value} "])

    return value


# -------------------------------------------------------------------------------
# Environment helper
def get_env_setting_value(key, default=None):
    """Return a typed value from environment variable if present.

    - Parses booleans (1/0, true/false, yes/no, on/off).
    - Tries to parse ints and JSON literals where sensible.
    - Returns `default` when env var is not set.
    """
    val = os.environ.get(key)
    if val is None:
        return default

    v = val.strip()
    # Booleans
    low = v.lower()
    if low in ("1", "true", "yes", "on"):
        return True
    if low in ("0", "false", "no", "off"):
        return False

    # Integer
    try:
        if re.fullmatch(r"-?\d+", v):
            return int(v)
    except Exception:
        pass

    # JSON-like (list/object/true/false/null/number)
    try:
        return json.loads(v)
    except Exception:
        # Fallback to raw string
        return v


# -------------------------------------------------------------------------------
def updateSubnets(scan_subnets):
    """
    Normalize scan subnet input into a list of subnets.

    Parameters:
        scan_subnets (str or list): A single subnet string or a list of subnet strings.

    Returns:
        list: A list containing all subnets. If a single subnet is provided, it is returned as a single-element list.
    """
    subnets = []

    # multiple interfaces
    if isinstance(scan_subnets, list):
        for interface in scan_subnets:
            subnets.append(interface)
    # one interface only
    else:
        subnets.append(scan_subnets)

    return subnets


# -------------------------------------------------------------------------------
# Reverse transformed values if needed
def reverseTransformers(val, transformers):
    """
    Reverse applied transformers on a value or list of values.

    This function iterates through a list of transformers and reverses
    them where possible. Currently supports:

    - "base64": Decodes a Base64-encoded string prefixed with 'base64:'.
    - "sha256": Logs a warning since SHA256 is irreversible.

    Args:
        val (str or list): The value or list of values to reverse-transform.
        transformers (list): List of transformers applied in order.

    Returns:
        str or list: The value(s) after reversing applicable transformers.

    Notes:
        - If 'val' is a list, each element is processed individually.
        - Invalid Base64 strings are returned unchanged.
        - Transformers are applied in the order given in the list.
    """
    def reverse_transformers(value, transformers):
        for transformer in transformers:
            if transformer == "base64":
                if isinstance(value, str):
                    value = base64.b64decode(value).decode("utf-8")
            elif transformer == "prefix|base64":
                if isinstance(value, str) and value.startswith("base64:"):
                    encoded_part = value[7:]
                    value = base64.b64decode(encoded_part).decode("utf-8")
                else:
                    mylog("none", ["[reverseTransformers] invalid base64 value format. Try re-saving Settings."])
            elif transformer == "sha256":
                mylog("none", ["[reverseTransformers] sha256 is irreversible"])
            # Add more transformer handling here if needed
        return value

    if isinstance(val, list):
        return [reverse_transformers(item, transformers) for item in val]
    else:
        return reverse_transformers(val, transformers)


# -------------------------------------------------------------------------------
# IP validation methods
# -------------------------------------------------------------------------------
# -------------------------------------------------------------------------------
def checkIPV4(ip):
    """Define a function to validate an Ip address"""
    ipRegex = r"^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$"

    if re.search(ipRegex, ip):
        return True
    else:
        return False


# -------------------------------------------------------------------------------
def check_IP_format(pIP):
    # check if TCP communication error ocurred
    if "communications error to" in pIP:
        return ""

    # Check IP format
    IPv4SEG = r"(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])"
    IPv4ADDR = r"(?:(?:" + IPv4SEG + r"\.){3,3}" + IPv4SEG + r")"
    IP = re.search(IPv4ADDR, pIP)

    # Return empty if not IP
    if IP is None:
        return ""

    # Return IP
    return IP.group(0)


# -------------------------------------------------------------------------------
# String manipulation methods
# -------------------------------------------------------------------------------


# -------------------------------------------------------------------------------
def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


# -------------------------------------------------------------------------------
def extract_between_strings(text, start, end):
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start))
    if start_index != -1 and end_index != -1:
        return text[start_index + len(start) : end_index]
    else:
        return ""


# -------------------------------------------------------------------------------


def bytes_to_string(value):
    # if value is of type bytes, convert to string
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return value


# -------------------------------------------------------------------------------


def if_byte_then_to_str(input):
    if isinstance(input, bytes):
        input = input.decode("utf-8")
        input = bytes_to_string(re.sub(r"[^a-zA-Z0-9-_\s]", "", str(input)))
    return input


# -------------------------------------------------------------------------------
def hide_email(email):
    m = email.split("@")

    if len(m) == 2:
        return f"{m[0][0]}{'*' * (len(m[0]) - 2)}{m[0][-1] if len(m[0]) > 1 else ''}@{m[1]}"

    return email


# -------------------------------------------------------------------------------
def hide_string(input_string):
    if len(input_string) < 3:
        return input_string  # Strings with 2 or fewer characters remain unchanged
    else:
        return input_string[0] + "*" * (len(input_string) - 2) + input_string[-1]


# -------------------------------------------------------------------------------
def removeDuplicateNewLines(text):
    if "\n\n\n" in text:
        return removeDuplicateNewLines(text.replace("\n\n\n", "\n\n"))
    else:
        return text


# -------------------------------------------------------------------------------
def sanitize_string(input):
    if isinstance(input, bytes):
        input = input.decode("utf-8")
    input = bytes_to_string(re.sub(r"[^a-zA-Z0-9-_\s]", "", str(input)))
    return input


# -------------------------------------------------------------------------------
# Function to normalize the string and remove diacritics
def normalize_string(text):
    # Normalize the text to 'NFD' to separate base characters and diacritics
    if not isinstance(text, str):
        text = str(text)
    normalized_text = unicodedata.normalize("NFD", text)
    # Filter out diacritics and unwanted characters
    return "".join(c for c in normalized_text if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------------------------
# MAC and IP helper methods
# -------------------------------------------------------------------------------

# -------------------------------------------------------------------------------------------
def generate_mac_links(html, deviceUrl):
    p = re.compile(r"(?:[0-9a-fA-F]:?){12}")

    MACs = re.findall(p, html)

    for mac in MACs:
        html = html.replace(
            "<td>" + mac + "</td>",
            '<td><a href="' + deviceUrl + mac + '">' + mac + "</a></td>",
        )

    return html


# -------------------------------------------------------------------------------
def extract_mac_addresses(text):
    mac_pattern = r"([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})"
    mac_addresses = re.findall(mac_pattern, text)
    return mac_addresses


# -------------------------------------------------------------------------------
def extract_ip_addresses(text):
    ip_pattern = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
    ip_addresses = re.findall(ip_pattern, text)
    return ip_addresses


# -------------------------------------------------------------------------------
# Helper function to determine if a MAC address is random
def is_random_mac(mac):
    """Determine if a MAC address is random, respecting user-defined prefixes not to mark as random."""

    # Validate input
    if not mac or len(mac) < 2:
        return False

    # Check if second character matches "2", "6", "A", "E" (case insensitive)
    is_random = mac[1].upper() in ["2", "6", "A", "E"]

    # Check against user-defined non-random MAC prefixes
    if is_random:
        not_random_prefixes = get_setting_value("UI_NOT_RANDOM_MAC")
        for prefix in not_random_prefixes:
            if mac.upper().startswith(prefix.upper()):
                is_random = False
                break
    return is_random


# -------------------------------------------------------------------------------
# Helper function to calculate number of children
def get_number_of_children(mac, devices):
    # Count children by checking devParentMAC for each device
    return sum(
        1 for dev in devices if dev.get("devParentMAC", "").strip() == mac.strip()
    )


# -------------------------------------------------------------------------------
# Function to convert IP to a long integer
def format_ip_long(ip_address):
    try:
        # Check if it's an IPv6 address
        if ":" in ip_address:
            ip = ipaddress.IPv6Address(ip_address)
        else:
            # Assume it's an IPv4 address
            ip = ipaddress.IPv4Address(ip_address)
        return int(ip)
    except ValueError:
        # Return a default error value if IP is invalid
        return -1


# -------------------------------------------------------------------------------
# JSON methods
# -------------------------------------------------------------------------------


# -------------------------------------------------------------------------------
def isJsonObject(value):
    return isinstance(value, dict)


# -------------------------------------------------------------------------------
def add_json_list(row, list):
    new_row = []
    for column in row:
        column = bytes_to_string(column)

        new_row.append(column)

    list.append(new_row)

    return list


# -------------------------------------------------------------------------------
# Checks if the object has a __dict__ attribute. If it does, it assumes that it's an instance of a class and serializes its attributes dynamically.
class NotiStrucEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__dict__"):
            # If the object has a '__dict__', assume it's an instance of a class
            return obj.__dict__
        return super().default(obj)


# -------------------------------------------------------------------------------
# Get language strings from plugin JSON
def collect_lang_strings(json, pref, stringSqlParams):
    for prop in json["localized"]:
        for language_string in json[prop]:
            stringSqlParams.append(
                (
                    str(language_string["language_code"]),
                    str(pref + "_" + prop),
                    str(language_string["string"]),
                    "",
                )
            )

    return stringSqlParams


# -------------------------------------------------------------------------------
# Get the value from the buildtimestamp.txt and initialize it if missing
def getBuildTimeStampAndVersion():
    """
    Retrieves the build timestamp and version from files within the
    application directory. Initializes them if missing.

    Returns:
        tuple: (int buildTimestamp, str version)
    """
    files_defaults = [
        ('front/buildtimestamp.txt', '0'),
        ('.VERSION', 'unknown')
    ]

    results = []

    for filename, default in files_defaults:
        path = os.path.join(applicationPath, filename)
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(default)

        with open(path, 'r') as f:
            content = f.read().strip() or default
            # Convert buildtimestamp to int, leave version as string
            value = int(content) if filename.endswith('buildtimestamp.txt') else content
            results.append(value)

    return tuple(results)


# -------------------------------------------------------------------------------
def checkNewVersion():
    mylog("debug", ["[Version check] Checking if new version available"])

    buildTimestamp, _version = getBuildTimeStampAndVersion()

    try:
        response = requests.get(
            "https://api.github.com/repos/jokob-sk/NetAlertX/releases", timeout=5
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        text = response.text
    except requests.exceptions.RequestException:
        mylog("minimal", ["[Version check] ⚠ ERROR: Couldn't check for new release."])
        return False

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        mylog("minimal", ["[Version check] ⚠ ERROR: Invalid JSON response from GitHub."])
        return False

    # make sure we received a valid response and not an API rate limit exceeded message
    if data and isinstance(data, list) and "published_at" in data[0]:
        dateTimeStr = data[0]["published_at"]
        releaseTimestamp = int(
            datetime.datetime.strptime(dateTimeStr, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        )

        if releaseTimestamp > buildTimestamp + 600:
            mylog('none', ["[Version check] New version of the container available!"])
            return True
        else:
            mylog("none", ["[Version check] Running the latest version."])
    else:
        mylog("minimal", ["[Version check] ⚠ ERROR: Received unexpected response from GitHub."],)

    return False


# -------------------------------------------------------------------------------
class noti_obj:
    def __init__(self, json, text, html):
        self.json = json
        self.text = text
        self.html = html
