#!/usr/bin/env python

import os
import sys
import requests
import json
import base64


# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from utils.plugin_utils import get_plugins_configs, decode_and_rename_files  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from utils.crypto_utils import encrypt_data  # noqa: E402 [flake8 lint suppression]
from messaging.in_app import write_notification  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
from database import get_temp_db_connection  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
lggr = Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'SYNC'

# Define the current path and log file paths
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)


def main():
    mylog('verbose', [f'[{pluginName}] In script'])

    # Retrieve configuration settings
    plugins_to_sync = get_setting_value('SYNC_plugins')
    api_token = get_setting_value('API_TOKEN')
    encryption_key = get_setting_value('SYNC_encryption_key')
    hub_url = get_setting_value('SYNC_hub_url')
    node_name = get_setting_value('SYNC_node_name')
    send_devices = get_setting_value('SYNC_devices')
    pull_nodes = get_setting_value('SYNC_nodes')

    # variables to determine operation mode
    is_hub  = False
    is_node = False

    # Check if api_token set
    if not api_token:
        mylog('verbose', [f'[{pluginName}] ⚠ ERROR api_token not defined - quitting.'])
        return -1

    #  check if this is a hub or a node
    if len(hub_url) > 0 and (send_devices or plugins_to_sync):
        is_node = True
        mylog('verbose', [f'[{pluginName}] Mode 1: PUSH (NODE) - This is a NODE as SYNC_hub_url, SYNC_devices or SYNC_plugins are set'])
    if len(pull_nodes) > 0:
        is_hub = True
        mylog('verbose', [f'[{pluginName}] Mode 2: PULL (HUB) - This is a HUB as SYNC_nodes is set'])

    # Mode 1: PUSH/SEND (NODE)
    if is_node:
        # PUSHING/SENDING Plugins

        # Get all plugin configurations
        all_plugins = get_plugins_configs(False)

        mylog('verbose', [f'[{pluginName}] plugins_to_sync {plugins_to_sync}'])

        for plugin in all_plugins:
            pref = plugin["unique_prefix"]

            index = 0
            if pref in plugins_to_sync:
                index += 1
                mylog('verbose', [f'[{pluginName}] synching "{pref}" ({index}/{len(plugins_to_sync)})'])

                # Construct the file path for the plugin's last_result.log file
                file_path = f"{LOG_PATH}/last_result.{pref}.log"

                if os.path.exists(file_path):
                    # Read the content of the log file
                    with open(file_path, 'r') as f:
                        file_content = f.read()

                        mylog('verbose', [f'[{pluginName}] Sending file_content: "{file_content}"'])

                        # encrypt and send data to the hub
                        send_data(api_token, file_content, encryption_key, file_path, node_name, pref, hub_url)

                else:
                    mylog('verbose', [f'[{pluginName}] {file_path} not found'])

        # PUSHING/SENDING devices
        if send_devices:

            file_path = f"{INSTALL_PATH}/api/table_devices.json"
            pref = 'SYNC'

            if os.path.exists(file_path):
                # Read the content of the log file
                with open(file_path, 'r') as f:
                    file_content = f.read()

                    mylog('verbose', [f'[{pluginName}] Sending file_content: "{file_content}"'])
                    send_data(api_token, file_content, encryption_key, file_path, node_name, pref, hub_url)
        else:
            mylog('verbose', [f'[{pluginName}] SYNC_hub_url not defined, skipping posting "Devices" data'])
    else:
        mylog('verbose', [f'[{pluginName}] SYNC_hub_url not defined, skipping posting "Plugins" and "Devices" data'])

    # Mode 2: PULL/GET (HUB)

    # PULLING DEVICES
    file_prefix = 'last_result'

    # pull data from nodes if specified
    if is_hub:
        for node_url in pull_nodes:
            response_json = get_data(api_token, node_url)

            # Extract node_name and base64 data
            node_name = response_json.get('node_name', 'unknown_node')
            data_base64 = response_json.get('data_base64', '')

            # Decode base64 data
            decoded_data = base64.b64decode(data_base64)

            # Create log file name using node name
            log_file_name = f'{file_prefix}.{node_name}.log'

            # Write decoded data to log file
            with open(os.path.join(LOG_PATH, log_file_name), 'wb') as log_file:
                log_file.write(decoded_data)

            message = f'[{pluginName}] Device data from node "{node_name}" written to {log_file_name}'
            mylog('verbose', [message])
            if lggr.isAbove('verbose'):
                write_notification(message, 'info', timeNowUTC())

    # Process any received data for the Device DB table (ONLY JSON)
    # Create the file path

    # Get all "last_result" files from the sync folder, decode, rename them, and get the list of files
    files_to_process = decode_and_rename_files(LOG_PATH, file_prefix)

    if len(files_to_process) > 0:

        mylog('verbose', [f'[{pluginName}] Mode 3: RECEIVE (HUB) - This is a HUB as received data found'])

        # Connect to the App database
        conn = get_temp_db_connection()
        cursor = conn.cursor()

        # Collect all unique devMac values from the JSON files
        unique_mac_addresses = set()
        device_data = []

        mylog('verbose', [f'[{pluginName}] Devices files to process: "{files_to_process}"'])

        for file_name in files_to_process:

            # only process received .log files, skipping the one logging the progress of this plugin
            if file_name != 'last_result.log':
                mylog('verbose', [f'[{pluginName}] Processing: "{file_name}"'])

                # make sure the file has the correct name (e.g last_result.encoded.Node_1.1.log) to skip any otehr plugin files
                if len(file_name.split('.')) > 2:
                    # Extract node name from either last_result.decoded.Node_1.1.log or last_result.Node_1.log
                    parts = file_name.split('.')
                    # If decoded/encoded file, node name is at index 2; otherwise at index 1
                    syncHubNodeName = parts[2] if 'decoded' in file_name or 'encoded' in file_name else parts[1]

                    file_path = f"{LOG_PATH}/{file_name}"

                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        for device in data['data']:
                            if device['devMac'] not in unique_mac_addresses:
                                device['devSyncHubNode'] = syncHubNodeName
                                unique_mac_addresses.add(device['devMac'])
                                device_data.append(device)

                    # Rename the file to "processed_" + current name
                    new_file_name = f"processed_{file_name}"
                    new_file_path = os.path.join(LOG_PATH, new_file_name)

                    # Overwrite if the new file already exists
                    if os.path.exists(new_file_path):
                        os.remove(new_file_path)

                    os.rename(file_path, new_file_path)

        if len(device_data) > 0:
            # Retrieve existing devMac values from the Devices table
            placeholders = ', '.join('?' for _ in unique_mac_addresses)
            cursor.execute(f'SELECT devMac FROM Devices WHERE devMac IN ({placeholders})', tuple(unique_mac_addresses))
            existing_mac_addresses = set(row[0] for row in cursor.fetchall())

            # insert devices into the last_result.log and thus CurrentScan table to manage state
            for device in device_data:
                # only insert devices taht were online and skip the root node to prevent IP flipping on the hub
                if device['devPresentLastScan'] == 1 and str(device['devMac']).lower() != 'internet':
                    plugin_objects.add_object(
                        primaryId   = device['devMac'],
                        secondaryId = device['devLastIP'],
                        watched1    = device['devName'],
                        watched2    = device['devVendor'],
                        watched3    = device['devSyncHubNode'],
                        watched4    = device['devGUID'],
                        extra       = '',
                        foreignKey  = device['devGUID'])

            # Filter out existing devices
            new_devices = [device for device in device_data if device['devMac'] not in existing_mac_addresses]

            #  Remove 'rowid' key if it exists
            for device in new_devices:
                device.pop('rowid', None)
                device.pop('devStatus', None)

            mylog('verbose', [f'[{pluginName}] All devices: "{len(device_data)}"'])
            mylog('verbose', [f'[{pluginName}] New devices: "{len(new_devices)}"'])

            # Prepare the insert statement
            if new_devices:

                # creating insert statement, removing 'rowid', 'devStatus' as handled on the target and devStatus is resolved on the fly
                columns = ', '.join(k for k in new_devices[0].keys() if k not in ['rowid', 'devStatus'])
                placeholders = ', '.join('?' for k in new_devices[0] if k not in ['rowid', 'devStatus'])
                sql = f'INSERT INTO Devices ({columns}) VALUES ({placeholders})'

                # Extract values for the new devices
                values = [tuple(device.values()) for device in new_devices]

                mylog('verbose', [f'[{pluginName}] Inserting Devices SQL   : "{sql}"'])
                mylog('verbose', [f'[{pluginName}] Inserting Devices VALUES: "{values}"'])

                # Use executemany for batch insertion
                cursor.executemany(sql, values)

                message = f'[{pluginName}] Inserted "{len(new_devices)}" new devices'

                mylog('verbose', [message])
                write_notification(message, 'info', timeNowUTC())

        # Commit and close the connection
        conn.commit()
        conn.close()

        # log result
        plugin_objects.write_result_file()

    return 0


# ------------------------------------------------------------------
# Data retrieval methods
api_endpoints = [
    "/sync",  # New Python-based endpoint
]


# send data to the HUB
def send_data(api_token, file_content, encryption_key, file_path, node_name, pref, hub_url):
    """Send encrypted data to HUB, preferring /sync endpoint and falling back to PHP version."""
    encrypted_data = encrypt_data(file_content, encryption_key)
    mylog('verbose', [f'[{pluginName}] Sending encrypted_data: "{encrypted_data}"'])

    data = {
        'data': encrypted_data,
        'file_path': file_path,
        'plugin': pref,
        'node_name': node_name
    }
    headers = {'Authorization': f'Bearer {api_token}'}

    for endpoint in api_endpoints:

        final_endpoint = hub_url + endpoint

        try:
            response = requests.post(final_endpoint, data=data, headers=headers, timeout=5)
            mylog('verbose', [f'[{pluginName}] Tried endpoint: {final_endpoint}, status: {response.status_code}'])

            if response.status_code == 200:
                message = f'[{pluginName}] Data for "{file_path}" sent successfully via {final_endpoint}'
                mylog('verbose', [message])
                write_notification(message, 'info', timeNowUTC())
                return True

        except requests.RequestException as e:
            mylog('verbose', [f'[{pluginName}] Error calling {final_endpoint}: {e}'])

    # If all endpoints fail
    message = f'[{pluginName}] Failed to send data for "{file_path}" via all endpoints'
    mylog('verbose', [message])
    write_notification(message, 'alert', timeNowUTC())
    return False


# get data from the nodes to the HUB
def get_data(api_token, node_url):
    """Get data from NODE, preferring /sync endpoint and falling back to PHP version."""
    mylog('verbose', [f'[{pluginName}] Getting data from node: "{node_url}"'])
    headers = {'Authorization': f'Bearer {api_token}'}

    for endpoint in api_endpoints:

        final_endpoint = node_url + endpoint

        try:
            response = requests.get(final_endpoint, headers=headers, timeout=5)
            mylog('verbose', [f'[{pluginName}] Tried endpoint: {final_endpoint}, status: {response.status_code}'])

            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    message = f'[{pluginName}] Failed to parse JSON from {final_endpoint}'
                    mylog('verbose', [message])
                    write_notification(message, 'alert', timeNowUTC())
                    return ""
        except requests.RequestException as e:
            mylog('verbose', [f'[{pluginName}] Error calling {final_endpoint}: {e}'])

    # If all endpoints fail
    message = f'[{pluginName}] Failed to get data from "{node_url}" via all endpoints'
    mylog('verbose', [message])
    write_notification(message, 'alert', timeNowUTC())
    return ""


if __name__ == '__main__':
    main()
