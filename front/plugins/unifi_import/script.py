#!/usr/bin/env python
# Inspired by https://github.com/stevehoek/Pi.Alert

from __future__ import unicode_literals
import os
import json
import sys
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from pyunifi.controller import Controller


# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects, rmBadChars, is_typical_router_ip, is_mac  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, normalize_string   # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'UNFIMP'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')
LOCK_FILE = os.path.join(LOG_PATH, f'full_run.{pluginName}.lock')

urllib3.disable_warnings(InsecureRequestWarning)


def main():

    mylog('verbose', [f'[{pluginName}] In script'])

    # init global variables
    global UNIFI_USERNAME, UNIFI_PASSWORD, UNIFI_HOST, UNIFI_SITES, PORT, VERIFYSSL, VERSION, FULL_IMPORT

    # parse output
    plugin_objects = Plugin_Objects(RESULT_FILE)

    UNIFI_USERNAME  = get_setting_value("UNFIMP_username")
    UNIFI_PASSWORD  = get_setting_value("UNFIMP_password")
    UNIFI_HOST      = get_setting_value("UNFIMP_host")
    UNIFI_SITES     = get_setting_value("UNFIMP_sites")
    PORT            = get_setting_value("UNFIMP_port")
    VERIFYSSL       = get_setting_value("UNFIMP_verifyssl")
    VERSION         = get_setting_value("UNFIMP_version")
    FULL_IMPORT     = get_setting_value("UNFIMP_fullimport")

    plugin_objects = get_entries(plugin_objects)

    plugin_objects.write_result_file()

    mylog('verbose', [f'[{pluginName}] Scan finished, found {len(plugin_objects)} devices'])


# .............................................
def get_entries(plugin_objects: Plugin_Objects) -> Plugin_Objects:
    global VERIFYSSL

    # check if the full run must be run:
    lock_file_value = read_lock_file()
    perform_full_run = check_full_run_state(FULL_IMPORT, lock_file_value)

    mylog('verbose', [f'[{pluginName}] sites: {UNIFI_SITES}'])

    if (VERIFYSSL.upper() == "TRUE"):
        VERIFYSSL = True
    else:
        VERIFYSSL = False

    # mylog('verbose', [f'[{pluginName}] sites: {sites}'])

    for site in UNIFI_SITES:

        mylog('verbose', [f'[{pluginName}] site: {site}'])

        c = Controller(
            UNIFI_HOST,
            UNIFI_USERNAME,
            UNIFI_PASSWORD,
            port=PORT,
            version=VERSION,
            ssl_verify=VERIFYSSL,
            site_id=site)

        online_macs = set()
        processed_macs = []

        mylog('verbose', [f'[{pluginName}] Get Online Devices'])

        # Collect details for online clients
        collect_details(
            device_type={'cl': ''},
            devices=c.get_clients(),
            online_macs=online_macs,
            processed_macs=processed_macs,
            plugin_objects=plugin_objects,
            device_label='client',
            device_vendor="",
            force_import=True  # These are online clients, force import
        )

        mylog('verbose', [f'[{pluginName}] Found {len(plugin_objects)} Online Devices'])

        mylog('verbose', [f'[{pluginName}] Identify Unifi Devices'])

        # Collect details for Unifi devices
        collect_details(
            device_type={
                'udm': 'Router',
                'usg': 'Router',
                'usw': 'Switch',
                'uap': 'AP'
            },
            devices=c.get_aps(),
            online_macs=online_macs,
            processed_macs=processed_macs,
            plugin_objects=plugin_objects,
            device_label='ap',
            device_vendor="Ubiquiti Networks Inc.",
            force_import=perform_full_run
        )

        mylog('verbose', [f'[{pluginName}] Found {len(plugin_objects)} Unifi Devices'])

        # Collect details for users
        collect_details(
            device_type={'user': ''},
            devices=c.get_users(),
            online_macs=online_macs,
            processed_macs=processed_macs,
            plugin_objects=plugin_objects,
            device_label='user',
            device_vendor="",
            force_import=perform_full_run
        )

        mylog('verbose', [f'[{pluginName}] Found {len(plugin_objects)} Users'])

    mylog('verbose', [f'[{pluginName}] check if Lock file needs to be modified'])
    set_lock_file_value(FULL_IMPORT, lock_file_value)

    mylog('verbose', [f'[{pluginName}] Found {len(plugin_objects)} Clients overall'])

    return plugin_objects


# -----------------------------------------------------------------------------
def collect_details(device_type, devices, online_macs, processed_macs, plugin_objects, device_label, device_vendor, force_import):
    for device in devices:
        mylog('verbose', [f'{json.dumps(device)}'])

        # try extracting variables from the json
        name = get_name(get_unifi_val(device, 'name'), get_unifi_val(device, 'hostname'))
        ipTmp = get_ip(get_unifi_val(device, 'lan_ip'), get_unifi_val(device, 'last_ip'), get_unifi_val(device, 'fixed_ip'), get_unifi_val(device, 'ip'))
        macTmp = device['mac']

        # continue only if valid MAC address
        if is_mac(macTmp):
            status = 1 if macTmp in online_macs else device.get('state', 0)
            deviceType = device_type.get(device.get('type'), '')
            parentMac = get_parent_mac(get_unifi_val(device, 'uplink_mac'), get_unifi_val(device, 'ap_mac'), get_unifi_val(device, 'sw_mac'))

            # override parent MAC if this is a router
            if parentMac == 'null' and is_typical_router_ip(ipTmp):
                parentMac = 'internet'

            # Add object only if not processed
            if macTmp not in processed_macs and (status == 1 or force_import is True):
                plugin_objects.add_object(
                    primaryId=macTmp,
                    secondaryId=ipTmp,
                    watched1=normalize_string(name),
                    watched2=get_unifi_val(device, 'oui', device_vendor),
                    watched3=deviceType,
                    watched4=status,
                    extra=get_unifi_val(device, 'connection_network_name', ''),
                    foreignKey="",
                    helpVal1=parentMac,
                    helpVal2=get_port(get_unifi_val(device, 'sw_port'), get_unifi_val(device, 'uplink_remote_port')),
                    helpVal3=device_label,
                    helpVal4="",
                )
                processed_macs.append(macTmp)
        else:
            mylog('verbose', [f'[{pluginName}] Skipping, not a valid MAC address: {macTmp}'])


# -----------------------------------------------------------------------------
def get_unifi_val(obj, key, default='null'):
    if isinstance(obj, dict):
        if key in obj and obj[key] not in ['', 'None', None]:
            return obj[key]
        for k, v in obj.items():
            if isinstance(v, dict):
                result = get_unifi_val(v, key, default)
                if result not in ['', 'None', None, 'null']:
                    return result

    mylog('trace', [f'[{pluginName}] Value not found for key "{key}" in obj "{json.dumps(obj)}"'])
    return default


# -----------------------------------------------------------------------------
def get_name(*names: str) -> str:
    for name in names:
        if name and name != 'null':
            return rmBadChars(name)
    return 'null'


# -----------------------------------------------------------------------------
def get_parent_mac(*macs: str) -> str:
    for mac in macs:
        if mac and mac != 'null':
            return mac
    return 'null'


# -----------------------------------------------------------------------------
def get_port(*ports: str) -> str:
    for port in ports:
        if port and port != 'null':
            return port
    return 'null'


# -----------------------------------------------------------------------------
def get_ip(*ips: str) -> str:
    for ip in ips:
        if ip and ip != 'null':
            return ip
    return '0.0.0.0'


# -----------------------------------------------------------------------------
def set_lock_file_value(config_value: str, lock_file_value: bool) -> None:

    mylog('verbose', [f'[{pluginName}] Lock Params: config_value={config_value}, lock_file_value={lock_file_value}'])
    # set lock if 'once' is set and the lock is not set
    if config_value == 'once' and lock_file_value is False:
        out = 1
    # reset lock if not 'once' is set and the lock is present
    elif config_value != 'once' and lock_file_value is True:
        out = 0
    else:
        mylog('verbose', [f'[{pluginName}] No change on lock file needed'])
        return

    mylog('verbose', [f'[{pluginName}] Setting lock value for "full import" to {out}'])
    with open(LOCK_FILE, 'w') as lock_file:
        lock_file.write(str(out))


# -----------------------------------------------------------------------------
def read_lock_file() -> bool:

    try:
        with open(LOCK_FILE, 'r') as lock_file:
            return bool(int(lock_file.readline()))
    except (FileNotFoundError, ValueError):
        return False


# -----------------------------------------------------------------------------
def check_full_run_state(config_value: str, lock_file_value: bool) -> bool:
    if config_value == 'always' or (config_value == 'once' and lock_file_value is False):
        mylog('verbose', [f'[{pluginName}] Full import needs to be done: config_value: {config_value} and lock_file_value: {lock_file_value}'])
        return True
    else:
        mylog('verbose', [f'[{pluginName}] Full import NOT needed: config_value: {config_value} and lock_file_value: {lock_file_value}'])
        return False


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
