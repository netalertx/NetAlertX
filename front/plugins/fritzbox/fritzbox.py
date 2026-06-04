#!/usr/bin/env python

import os
import sys
from pytz import timezone

# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from const import logPath  # noqa: E402, E261 [flake8 lint suppression]
from plugin_helper import Plugin_Objects, normalize_mac  # noqa: E402, E261 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402, E261 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402, E261 [flake8 lint suppression]
from utils.crypto_utils import string_to_fake_mac  # noqa: E402, E261 [flake8 lint suppression]
from fritzconnection import FritzConnection  # noqa: E402, E261 [flake8 lint suppression]
from fritzconnection.lib.fritzhosts import FritzHosts  # noqa: E402, E261 [flake8 lint suppression]

import conf  # noqa: E402, E261 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'FRITZBOX'

INTERFACE_MAP = {
    '802.11': 'WiFi',
    'Ethernet': 'LAN',
}

# Define the current path and log file paths
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)


def get_fritzbox_connection(host, port, user, password, use_tls):
    """
    Create FritzConnection with error handling.
    Returns: FritzConnection object or None on failure
    """
    try:
        mylog('verbose', [f'[{pluginName}] Attempting connection to {host}:{port} (TLS: {use_tls})'])

        fc = FritzConnection(
            address=host,
            port=port,
            user=user,
            password=password,
            use_tls=use_tls,
            timeout=10,
        )

        mylog('verbose', [f'[{pluginName}] Successfully connected to Fritz!Box'])
        mylog('verbose', [f'[{pluginName}] Model: {fc.modelname}, Software: {fc.system_version}'])

        return fc
    except Exception as e:
        mylog('none', [f'[{pluginName}] ⚠ ERROR: Failed to connect to Fritz!Box: {e}'])
        mylog('none', [f'[{pluginName}] Check host ({host}), port ({port}), and credentials'])
        mylog('none', [f'[{pluginName}] Ensure TR-064 is enabled in Fritz!Box settings'])
        return None


def get_connected_devices(fc, active_only):
    """
    Query all hosts from Fritz!Box via FritzHosts service.
    Use get_hosts_info() for count, then get_generic_host_entry(index) for each.
    Filter by NewActive status if active_only=True.
    Returns: List of device dictionaries
    """
    devices = []

    try:
        hosts = FritzHosts(fc)
        host_count = hosts.host_numbers

        mylog('verbose', [f'[{pluginName}] Found {host_count} total hosts in Fritz!Box'])

        for index in range(host_count):
            try:
                host_info = hosts.get_generic_host_entry(index)

                # Extract relevant fields
                mac_address = host_info.get('NewMACAddress', '')
                ip_address = host_info.get('NewIPAddress', '')
                hostname = host_info.get('NewHostName', '')
                active = host_info.get('NewActive', 0)
                interface_type = host_info.get('NewInterfaceType', 'Unknown')

                # Skip if active_only and device is not active
                if active_only and not active:
                    continue

                # Skip entries without MAC address
                if not mac_address:
                    continue

                # Normalize MAC address
                mac_address = normalize_mac(mac_address)

                # Map interface type to readable format
                interface_display = interface_type
                for key, value in INTERFACE_MAP.items():
                    if key in interface_type:
                        interface_display = value
                        break

                # Build device dictionary
                device = {
                    'mac_address': mac_address,
                    'ip_address': ip_address if ip_address else '',
                    'hostname': hostname if hostname else 'Unknown',
                    'active_status': 'Active' if active else 'Inactive',
                    'interface_type': interface_display
                }

                devices.append(device)
                mylog('verbose', [f'[{pluginName}] Device: {mac_address} ({hostname}) - {ip_address} - {interface_display}'])

            except Exception as e:
                mylog('minimal', [f'[{pluginName}] Warning: Failed to get host entry {index}: {e}'])
                continue

        mylog('verbose', [f'[{pluginName}] Processed {len(devices)} devices'])

    except Exception as e:
        mylog('none', [f'[{pluginName}] ⚠ ERROR: Failed to query devices: {e}'])

    return devices


def check_guest_wifi_status(fc, guest_service_num):
    """
    Query a specific WLANConfiguration service for guest network status.
    Returns: Dict with active status and interface info
    """
    guest_info = {
        'active': False,
        'ssid': 'Guest WiFi',
        'interface': 'Guest Network'
    }

    try:
        service = f'WLANConfiguration{guest_service_num}'
        result = fc.call_action(service, 'GetInfo')
        status = result.get('NewEnable', False)
        ssid = result.get('NewSSID', '')

        if status:
            guest_info['active'] = True
            guest_info['ssid'] = ssid if ssid else 'Guest WiFi'
            mylog('verbose', [f'[{pluginName}] Guest WiFi active on service {guest_service_num}: {guest_info["ssid"]}'])
        else:
            mylog('verbose', [f'[{pluginName}] Guest WiFi service {guest_service_num} is disabled'])

    except Exception as e:
        mylog('minimal', [f'[{pluginName}] Warning: Failed to query WLANConfiguration{guest_service_num}: {e}'])

    return guest_info


def create_guest_wifi_device(fc):
    """
    Create a synthetic device entry for guest WiFi.
    Derives a deterministic fake MAC from the Fritz!Box hardware MAC address.
    Falls back to a fixed sentinel string if the MAC cannot be retrieved.
    Returns: Device dictionary
    """
    try:
        fritzbox_mac = fc.call_action('DeviceInfo:1', 'GetInfo').get('NewMACAddress', '')
        guest_mac = string_to_fake_mac(normalize_mac(fritzbox_mac) if fritzbox_mac else 'FRITZBOX_GUEST')

        device = {
            'mac_address': guest_mac,
            'ip_address': '',
            'hostname': 'Guest WiFi Network',
            'active_status': 'Active',
            'interface_type': 'Access Point'
        }

        mylog('verbose', [f'[{pluginName}] Created guest WiFi device: {guest_mac}'])
        return device

    except Exception as e:
        mylog('minimal', [f'[{pluginName}] Warning: Failed to create guest WiFi device: {e}'])
        return None


def main():
    mylog('verbose', [f'[{pluginName}] In script'])

    # Retrieve configuration settings
    host = get_setting_value('FRITZBOX_HOST')
    port = get_setting_value('FRITZBOX_PORT')
    user = get_setting_value('FRITZBOX_USER')
    password = get_setting_value('FRITZBOX_PASS')
    use_tls = get_setting_value('FRITZBOX_USE_TLS')
    report_guest = get_setting_value('FRITZBOX_REPORT_GUEST')
    guest_service = get_setting_value('FRITZBOX_GUEST_SERVICE')
    active_only = get_setting_value('FRITZBOX_ACTIVE_ONLY')

    mylog('verbose', [f'[{pluginName}] Settings: host={host}, port={port}, use_tls={use_tls}, active_only={active_only}'])

    # Create Fritz!Box connection
    fc = get_fritzbox_connection(host, port, user, password, use_tls)

    if not fc:
        mylog('none', [f'[{pluginName}] ⚠ ERROR: Could not establish connection to Fritz!Box'])
        mylog('none', [f'[{pluginName}] Plugin will return empty results'])
        plugin_objects.write_result_file()
        return 1

    # Retrieve device data
    device_data = get_connected_devices(fc, active_only)

    # Check guest WiFi if enabled
    if report_guest:
        guest_status = check_guest_wifi_status(fc, guest_service)
        if guest_status['active']:
            guest_device = create_guest_wifi_device(fc)
            if guest_device:
                device_data.append(guest_device)

    # Process the data into native application tables
    if device_data:
        for device in device_data:
            plugin_objects.add_object(
                primaryId=device['mac_address'],
                secondaryId=device['ip_address'],
                watched1=device['hostname'],
                watched2=device['active_status'],
                watched3=device['interface_type'],
                watched4='',
                extra='',
                foreignKey=device['mac_address']
            )

        mylog('verbose', [f'[{pluginName}] Successfully processed {len(device_data)} devices'])
    else:
        mylog('minimal', [f'[{pluginName}] No devices found'])

    # Log result
    plugin_objects.write_result_file()

    return 0


if __name__ == '__main__':
    sys.exit(main())
