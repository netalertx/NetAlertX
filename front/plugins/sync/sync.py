#!/usr/bin/env python

import os
import sys
import requests
import json
import base64
import binascii


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

            if not isinstance(response_json, dict):
                mylog('none', [f'[{pluginName}] Skipping node "{node_url}" due to failed or invalid response'])
                continue

            # Extract node_name and base64 data
            node_name = response_json.get('node_name', 'unknown_node')
            data_base64 = response_json.get('data_base64', '')

            # Decode base64 data
            try:
                decoded_data = base64.b64decode(data_base64)
            except (binascii.Error, ValueError, TypeError) as e:
                mylog('none', [f'[{pluginName}] Skipping node "{node_name}": base64 decode failed for data_base64="{data_base64}": {e}'])
                continue

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

                # Only process sync artifacts:
                #   PUSH mode (decoded): last_result.PLUGIN.decoded.NodeName.N.log (6 parts)
                #   PULL mode:           last_result.NodeName.log                  (3 parts, valid JSON)
                # Local plugin result files (last_result.ARPSCAN.log) are also 3 parts but
                # are pipe-delimited — catch and skip them via the JSONDecodeError guard below.
                parts = file_name.split('.')
                if len(parts) > 2:
                    # PUSH artifacts:
                    #   last_result.PLUGIN.decoded.NodeName.N.log
                    #   last_result.PLUGIN.encoded.NodeName.N.log
                    #
                    # Require BOTH:
                    #   1. decoded/encoded marker
                    #   2. trailing ".<counter>.log" shape
                    #
                    # This prevents PULL filenames like:
                    #   last_result.office.encoded.lab.log
                    # from being incorrectly parsed as PUSH artifacts.
                    is_push_artifact = (
                        ('.decoded.' in file_name or '.encoded.' in file_name) and file_name.rsplit('.', 2)[1].isdigit()
                    )

                    if is_push_artifact:
                        _marker = '.decoded.' if '.decoded.' in file_name else '.encoded.'
                        _, _after = file_name.split(_marker, 1)
                        syncHubNodeName = _after.rsplit('.', 2)[0]
                    else:
                        # PULL artifact:
                        #   last_result.NodeName.log
                        syncHubNodeName = file_name[len('last_result.'):-len('.log')]

                    file_path = f"{LOG_PATH}/{file_name}"

                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        for device in data['data']:
                            device['devMac'] = str(device['devMac']).lower()
                            if device['devMac'].lower() not in unique_mac_addresses:
                                device['devSyncHubNode'] = syncHubNodeName
                                unique_mac_addresses.add(device['devMac'].lower())
                                device_data.append(device)
                    except (json.JSONDecodeError, KeyError):
                        mylog('verbose', [f'[{pluginName}] Skipping "{file_name}" - not a valid sync JSON payload'])
                        continue

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
            existing_mac_addresses = set(row[0].lower() for row in cursor.fetchall())

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

            # Resolve the actual columns that exist in the Devices table once.
            # This automatically excludes computed/virtual fields (e.g. devStatus,
            # devIsSleeping) and 'rowid' without needing a maintained exclusion list.
            cursor.execute("PRAGMA table_info(Devices)")
            db_columns = {row[1] for row in cursor.fetchall()}

            # Filter new devices (MACs not yet known on hub).
            new_devices = [
                device for device in device_data
                if device['devMac'].lower() not in existing_mac_addresses
            ]

            mylog('verbose', [f'[{pluginName}] All devices: "{len(device_data)}"'])
            mylog('verbose', [f'[{pluginName}] New devices: "{len(new_devices)}"'])

            # Determine which devices to write and how, based on SYNC_BEHAVIOR.
            #
            #   copy-new     (default) — INSERT new devices only, using node config.
            #                            Subsequent node changes only update empty hub fields.
            #
            #   carbon-copy            — UPSERT all devices every sync.
            #                            Node is fully authoritative; raw SQL bypasses
            #                            can_overwrite_field(), so ALL hub fields are
            #                            overwritten on every sync, including USER/LOCKED-
            #                            sourced fields. (update_devices_data_from_scan
            #                            respects field locks but is not invoked here;
            #                            see README "carbon-copy" for the contract.)
            #
            #   hub-defaults           — Skip direct INSERT entirely.
            #                            Hub creates new devices via create_new_devices()
            #                            with its own NEWDEV defaults.
            #
            # For copy-new/carbon-copy we insert them here (before the Devices INSERT
            # would pre-seed the table and block create_new_devices()).
            # For hub-defaults, create_new_devices() handles it naturally.

            sync_behavior = get_setting_value('SYNC_BEHAVIOR') or 'copy-new'
            mylog('verbose', [f'[{pluginName}] SYNC_BEHAVIOR: "{sync_behavior}"'])

            if sync_behavior == 'hub-defaults':
                mylog('verbose', [f'[{pluginName}] hub-defaults: skipping direct Devices write; hub pipeline handles new devices and events'])

            else:
                # Fire "New Device" events for genuinely new MACs before the Devices
                # INSERT pre-seeds the table (which would block create_new_devices()).
                if new_devices:
                    now = timeNowUTC()
                    cursor.executemany(
                        """INSERT OR IGNORE INTO Events
                           (eveMac, eveIp, eveDateTime, eveEventType, eveAdditionalInfo, evePendingAlertEmail)
                           VALUES (?, ?, ?, 'New Device', ?, 1)""",
                        [(d['devMac'], d.get('devLastIP', ''), now, d.get('devVendor', ''))
                         for d in new_devices]
                    )
                    mylog('verbose', [f'[{pluginName}] Queued "New Device" events for {len(new_devices)} device(s)'])

                devices_to_write = new_devices if sync_behavior == 'copy-new' else device_data

                if devices_to_write:
                    # Only keep keys that are real DB columns; computed or unknown
                    # fields are silently dropped regardless of the source schema.
                    insert_cols = [k for k in devices_to_write[0].keys() if k in db_columns]
                    columns     = ', '.join(insert_cols)
                    placeholders = ', '.join('?' for _ in insert_cols)

                    if sync_behavior == 'carbon-copy':
                        # UPSERT: on MAC conflict update all columns except devMac and
                        # devPresentLastScan.
                        # devMac is the PRIMARY KEY so it is excluded from the SET clause.
                        # devPresentLastScan is excluded to prevent a node's offline report
                        # from clobbering the hub's own scan result: if a device is online
                        # on the hub network but offline on a node, the raw UPSERT would
                        # flip devPresentLastScan = 0 every sync cycle, triggering
                        # Connected/Disconnected events on each scan and causing the device
                        # to be flagged as Flapping.  Presence is owned by
                        # update_presence_from_CurrentScan(); the carbon-copy path respects
                        # that contract by leaving devPresentLastScan to the normal pipeline.
                        # NOTE: this raw SQL bypasses can_overwrite_field() — ALL other fields
                        # including USER/LOCKED-sourced ones are overwritten. Node is fully
                        # authoritative in this mode.
                        _CARBON_COPY_SKIP = {'devMac', 'devPresentLastScan'}
                        update_cols   = [col for col in insert_cols if col not in _CARBON_COPY_SKIP]
                        update_clause = ', '.join(f'{col}=excluded.{col}' for col in update_cols)
                        sql = (
                            f'INSERT INTO Devices ({columns}) VALUES ({placeholders}) '
                            f'ON CONFLICT(devMac) DO UPDATE SET {update_clause}'
                        )
                    else:
                        # copy-new: skip silently if MAC already exists (race-condition safety).
                        sql = f'INSERT OR IGNORE INTO Devices ({columns}) VALUES ({placeholders})'

                    values = [tuple(device.get(col) for col in insert_cols) for device in devices_to_write]

                    mylog('verbose', [f'[{pluginName}] Devices SQL   : "{sql}"'])
                    mylog('verbose', [f'[{pluginName}] Devices VALUES: "{values}"'])

                    cursor.executemany(sql, values)

                    write_count = len(new_devices) if sync_behavior == 'copy-new' else len(devices_to_write)
                    message = f'[{pluginName}] {sync_behavior}: wrote "{write_count}" device(s) to Devices'
                    mylog('verbose', [message])
                    if lggr.isAbove('verbose'):
                        write_notification(message, 'info', timeNowUTC())

        # Commit and close the connection
        conn.commit()
        conn.close()

        # log result
        plugin_objects.write_result_file()

    return 0


# Data retrieval methods
api_endpoints = [
    "/sync",  # New Python-based endpoint
]


# send data to the HUB
def send_data(api_token, file_content, encryption_key, file_path, node_name, pref, hub_url):
    """
    Sends encrypted plugin output from NODE → HUB.

    Flow:
    1. Encrypt plugin output locally
    2. Build payload (data + metadata)
    3. Try each configured HUB endpoint in order
    4. On success (200) → stop immediately
    5. On failure → log HUB response + continue fallback
    6. If all endpoints fail → alert user
    """

    # STEP 1: Encrypt raw plugin output before transmission
    encrypted_data = encrypt_data(file_content, encryption_key)

    mylog('verbose', [f"[{pluginName}] Encrypted payload prepared type={type(encrypted_data).__name__}"])

    # STEP 2: Build request payload for HUB sync API
    data = {
        'data': encrypted_data,
        'file_path': file_path,
        'plugin': pref,
        'node_name': node_name
    }

    headers = {
        'Authorization': f'Bearer {api_token}'
    }

    # STEP 3: Attempt delivery to each configured endpoint
    for endpoint in api_endpoints:

        final_endpoint = hub_url + endpoint

        try:

            # STEP 4: Send request to HUB sync endpoint
            response = requests.post(
                final_endpoint,
                json=data,
                headers=headers,
                timeout=5
            )

            # STEP 5a: Success path (HUB accepted payload)
            if response.status_code == 200:
                message = (f'[{pluginName}] Sync success for "{file_path}" via {final_endpoint}')
                mylog('verbose', [message])
                if lggr.isAbove('verbose'):
                    write_notification(message, 'info', timeNowUTC())
                return True

            # STEP 5b: HUB returned error (e.g. 500, 400)
            try:
                response_json = response.json()
            except Exception:
                response_json = {}

            # Extract best available error message
            error_msg = (
                response_json.get("error") or response_json.get("message") or response.text
            )

            msg = (f'[{pluginName}] HUB error on {final_endpoint} [{response.status_code}]: {error_msg}')

            mylog('none', [msg])
            write_notification(msg, 'alert', timeNowUTC())

            mylog('verbose', [f'[{pluginName}] Endpoint attempted: {final_endpoint} status={response.status_code}'])

        except requests.RequestException as e:
            # STEP 5c: Network-level failure (timeout, DNS, etc.)
            mylog('verbose', [f'[{pluginName}] Request exception calling {final_endpoint} error={type(e).__name__}: {e}'])

    # STEP 6: All endpoints failed → final fallback alert
    message = (
        f'[{pluginName}] All HUB endpoints failed for "{file_path}"'
    )

    mylog('none', [message])
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
