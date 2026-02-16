import pytz
from pytz import all_timezones
import sys
import os
import re
import base64
import json

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')

sys.path.append(f"{INSTALL_PATH}/front/plugins")
sys.path.append(f'{INSTALL_PATH}/server')

from logger import mylog  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from const import default_tz, fullConfPath  # noqa: E402 [flake8 lint suppression]


# -------------------------------------------------------------------------------
def read_config_file():
    """
    retuns dict on the config file key:value pairs
    config_dir[key]
    """

    filename = fullConfPath

    print('[plugin_helper] reading config file')

    # load the variables from .conf
    with open(filename, "r") as file:
        code = compile(file.read(), filename, "exec")

    confDict = {}  # config dictionary
    exec(code, {"__builtins__": {}}, confDict)
    return confDict


configFile = read_config_file()
timeZoneSetting = configFile.get('TIMEZONE', default_tz)
if timeZoneSetting not in all_timezones:
    timeZoneSetting = default_tz
timeZone = pytz.timezone(timeZoneSetting)


# -------------------------------------------------------------------
# Sanitizes plugin output
def handleEmpty(input):
    if not input:
        return 'null'
    else:
        # Validate and sanitize message content
        # Remove potentially problematic characters in string
        if isinstance(input, str):
            input = re.sub(r'[^\x00-\x7F]+', ' ', input)
            input = input.replace('\n', '')  # Removing new lines
        return input


# -------------------------------------------------------------------
# Sanitizes string
def rmBadChars(input):

    input = handleEmpty(input)
    input = input.replace("'", '_')  # Removing ' (single quotes)

    return input


# -------------------------------------------------------------------
# check if this is a router IP
def is_typical_router_ip(ip_address):
    # List of common default gateway IP addresses
    common_router_ips = [
        "192.168.0.1", "192.168.1.1", "192.168.1.254", "192.168.0.254",
        "10.0.0.1", "10.1.1.1", "192.168.2.1", "192.168.10.1", "192.168.11.1",
        "192.168.100.1", "192.168.101.1", "192.168.123.254", "192.168.223.1",
        "192.168.31.1", "192.168.8.1", "192.168.254.254", "192.168.50.1",
        "192.168.3.1", "192.168.4.1", "192.168.5.1", "192.168.9.1",
        "192.168.15.1", "192.168.16.1", "192.168.20.1", "192.168.30.1",
        "192.168.42.1", "192.168.62.1", "192.168.178.1", "192.168.1.1",
        "192.168.1.254", "192.168.0.1", "192.168.0.10", "192.168.0.100",
        "192.168.0.254"
    ]

    return ip_address in common_router_ips


# -------------------------------------------------------------------
# Check if a valid MAC address
def is_mac(input):
    input_str = str(input).lower().strip()  # Convert to string and lowercase so non-string values won't raise errors

    # Full MAC (6 octets) e.g. aa:bb:cc:dd:ee:ff
    full_mac_re = re.compile(r"^[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\1[0-9a-f]{2}){4}$")

    # Wildcard prefix format: exactly 3 octets followed by a trailing '*' component
    # Examples: aa:bb:cc:*
    wildcard_re = re.compile(r"^[0-9a-f]{2}[-:]?[0-9a-f]{2}[-:]?[0-9a-f]{2}[-:]?\*$")

    if full_mac_re.match(input_str) or wildcard_re.match(input_str):
        return True

    # If it's not a MAC address or allowed wildcard pattern, log the input
    mylog('verbose', [f'[is_mac] not a MAC: {input_str}'])

    return False


# -------------------------------------------------------------------
def decodeBase64(inputParamBase64):

    # Printing the input list to check its content.
    mylog('debug', ['[Plugins] Helper base64 input: ', input])
    print('[Plugins] Helper base64 input: ')
    print(input)

    # Extract the base64-encoded subnet information from the first element
    # The format of the element is assumed to be like 'param=b<base64-encoded-data>'.
    # Printing the extracted base64-encoded information.
    mylog('debug', ['[Plugins] Helper base64 inputParamBase64: ', inputParamBase64])

    # Decode the base64-encoded subnet information to get the actual subnet information in ASCII format.
    result = base64.b64decode(inputParamBase64).decode('ascii')

    # Print the decoded subnet information.
    mylog('debug', ['[Plugins] Helper base64 result: ', result])

    return result


# -------------------------------------------------------------------
def decode_settings_base64(encoded_str, convert_types=True):
    """
    Decodes a base64-encoded JSON list of settings into a dict.

    Each setting entry format:
        [group, key, type, value]

    Example:
        [
            ["group", "name", "string", "Home - local"],
            ["group", "base_url", "string", "https://..."],
            ["group", "api_version", "integer", "2"],
            ["group", "verify_ssl", "boolean", "False"]
        ]

    Returns:
        {
            "name": "Home - local",
            "base_url": "https://...",
            "api_version": 2,
            "verify_ssl": False
        }
    """
    decoded_json = base64.b64decode(encoded_str).decode("utf-8")
    settings_list = json.loads(decoded_json)

    settings_dict = {}
    for _, key, _type, value in settings_list:
        if convert_types:
            _type_lower = _type.lower()
            if _type_lower == "boolean":
                settings_dict[key] = value.lower() == "true"
            elif _type_lower == "integer":
                settings_dict[key] = int(value)
            elif _type_lower == "float":
                settings_dict[key] = float(value)
            else:
                settings_dict[key] = value
        else:
            settings_dict[key] = value

    return settings_dict


# -------------------------------------------------------------------
def normalize_mac(mac):
    """
    normalize a mac address to the standard format with colon separators.
    for example, "AA-BB-CC-DD-EE-FF" will be normalized to "aa:bb:cc:dd:ee:ff".
    wildcard mac addresses like "AA:BB:CC:*" will be normalized to "aa:bb:cc:*".

    :param mac: the mac address to normalize.
    :return: the normalized mac address (lowercase).
    """
    s = str(mac).strip().lower()

    if s == "internet":
        return "internet"

    # determine separator if present, prefer colon, then hyphen
    if ':' in s:
        parts = s.split(':')
    elif '-' in s:
        parts = s.split('-')
    else:
        # no explicit separator; attempt to split every two chars
        parts = [s[i:i + 2] for i in range(0, len(s), 2)]

    normalized_parts = []
    for part in parts:
        part = part.strip()
        if part == '*':
            normalized_parts.append('*')
        else:
            # ensure two hex digits
            normalized_parts.append(part.zfill(2))

    # use colon as canonical separator
    return ':'.join(normalized_parts)


# -------------------------------------------------------------------
class Plugin_Object:
    """
    Plugin_Object class to manage one object introduced by the plugin.
    An object typically is a device but could also be a website or something
    else that is monitored by the plugin.
    """

    def __init__(
        self,
        primaryId="",
        secondaryId="",
        watched1="",
        watched2="",
        watched3="",
        watched4="",
        extra="",
        foreignKey="",
        helpVal1="",
        helpVal2="",
        helpVal3="",
        helpVal4="",
    ):
        self.pluginPref = ""
        self.primaryId = primaryId
        self.secondaryId = secondaryId
        self.created = timeNowUTC()
        self.changed = ""
        self.watched1 = watched1
        self.watched2 = watched2
        self.watched3 = watched3
        self.watched4 = watched4
        self.status = ""
        self.extra = extra
        self.userData = ""
        self.foreignKey = foreignKey
        self.helpVal1 = helpVal1 or ""
        self.helpVal2 = helpVal2 or ""
        self.helpVal3 = helpVal3 or ""
        self.helpVal4 = helpVal4 or ""

    def write(self):
        """
        Write the object details as a string in the
        format required to write the result file.
        """
        line = "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}\n".format(
            self.primaryId,
            self.secondaryId,
            self.created,
            self.watched1,
            self.watched2,
            self.watched3,
            self.watched4,
            self.extra,
            self.foreignKey,
            self.helpVal1,
            self.helpVal2,
            self.helpVal3,
            self.helpVal4
        )
        return line


class Plugin_Objects:
    """
    Plugin_Objects is the class that manages and holds all the objects created by the plugin.
    It contains a list of Plugin_Object instances.
    And can write the required result file.
    """

    def __init__(self, result_file):
        self.result_file = result_file
        self.objects = []

    def add_object(
        self,
        primaryId="",
        secondaryId="",
        watched1="",
        watched2="",
        watched3="",
        watched4="",
        extra="",
        foreignKey="",
        helpVal1="",
        helpVal2="",
        helpVal3="",
        helpVal4="",
    ):
        self.objects.append(
            Plugin_Object(
                primaryId,
                secondaryId,
                watched1,
                watched2,
                watched3,
                watched4,
                extra,
                foreignKey,
                helpVal1,
                helpVal2,
                helpVal3,
                helpVal4
            )
        )

    def write_result_file(self):
        with open(self.result_file, mode="w") as fp:
            for obj in self.objects:
                fp.write(obj.write())

    def __add__(self, other):
        if isinstance(other, Plugin_Objects):
            new_objects = self.objects + other.objects
            new_result_file = self.result_file  # You might want to adjust this
            new_instance = Plugin_Objects(new_result_file)
            new_instance.objects = new_objects
            return new_instance
        else:
            raise TypeError("Unsupported operand type for +")

    def __len__(self):
        return len(self.objects)
