#!/usr/bin/env python

import os
import sys
from pytz import timezone

# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from const import logPath # noqa: E402, E261 [flake8 lint suppression]
from plugin_helper import Plugin_Objects # noqa: E402, E261 [flake8 lint suppression]
from logger import mylog, Logger # noqa: E402, E261 [flake8 lint suppression]
from helper import get_setting_value # noqa: E402, E261 [flake8 lint suppression]

import conf # noqa: E402, E261 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = '<unique_prefix>'

# Define the current path and log file paths
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)


def main():
    mylog('verbose', [f'[{pluginName}] In script'])

    # Retrieve configuration settings
    some_setting = get_setting_value('SYNC_plugins')

    mylog('verbose', [f'[{pluginName}] some_setting value {some_setting}'])

    # retrieve data
    device_data = get_device_data(some_setting)

    #  Process the data into native application tables
    if len(device_data) > 0:

        # insert devices into the lats_result.log
        # make sure the below mapping is mapped in config.json, for example:
        # "database_column_definitions": [
        # {
        #   "column": "objectPrimaryId",     <--------- the value I save into primaryId
        #   "mapped_to_column": "scanMac",   <--------- gets inserted into the CurrentScan DB
        #                                               table column scanMac
        #
        for device in device_data:
            plugin_objects.add_object(
                primaryId   = device['mac_address'],
                secondaryId = device['ip_address'],
                watched1    = device['hostname'],
                watched2    = device['vendor'],
                watched3    = device['device_type'],
                watched4    = device['last_seen'],
                extra       = '',
                foreignKey  = device['mac_address']
                # helpVal1  = "Something1",  # Optional Helper values to be passed for mapping into the app
                # helpVal2  = "Something1",  # If you need to use even only 1, add the remaining ones too
                # helpVal3  = "Something1",  # and set them to 'null'. Check the the docs for details:
                # helpVal4  = "Something1",  # https://docs.netalertx.com/PLUGINS_DEV
            )

        mylog('verbose', [f'[{pluginName}] New entries: "{len(device_data)}"'])

    # log result
    plugin_objects.write_result_file()

    return 0


#  retrieve data
def get_device_data(some_setting):

    device_data = []

    # do some processing, call exteranl APIs, and return a device_data list
    #  ...
    #
    # Sample data for testing purposes, you can adjust the processing in main() as needed
    # ... before adding it to the plugin_objects.add_object(...)
    device_data = [
        {
            'device_id': 'device1',
            'mac_address': '00:11:22:33:44:55',
            'ip_address': '192.168.1.2',
            'hostname': 'iPhone 12',
            'vendor': 'Apple Inc.',
            'device_type': 'Smartphone',
            'last_seen': '2024-06-27 10:00:00',
            'port': '1',
            'network_id': 'network1'
        },
        {
            'device_id': 'device2',
            'mac_address': '00:11:22:33:44:66',
            'ip_address': '192.168.1.3',
            'hostname': 'Moto G82',
            'vendor': 'Motorola Inc.',
            'device_type': 'Laptop',
            'last_seen': '2024-06-27 10:05:00',
            'port': '',
            'network_id': 'network1'
        }
    ]

    # Return the data to be detected by the main application
    return device_data


if __name__ == '__main__':
    main()
