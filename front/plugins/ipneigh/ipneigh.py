#!/usr/bin/env python

import os
import sys
import subprocess
from pytz import timezone
from functools import reduce

# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value   # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'IPNEIGH'

# Define the current path and log file paths
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)


def main():
    mylog('verbose', [f'[{pluginName}] In script'])

    # Retrieve configuration settings
    SCAN_SUBNETS = get_setting_value('SCAN_SUBNETS')

    mylog('verbose', [f'[{pluginName}] SCAN_SUBNETS value: {SCAN_SUBNETS}'])

    # Extract interfaces from SCAN_SUBNETS
    interfaces = ','.join(
        entry.split('--interface=')[-1].strip() for entry in SCAN_SUBNETS if '--interface=' in entry
    )

    mylog('verbose', [f'[{pluginName}] Interfaces value: "{interfaces}"'])

    # retrieve data
    raw_neighbors = get_neighbors(interfaces)

    neighbors = parse_neighbors(raw_neighbors)

    #  Process the data into native application tables
    if len(neighbors) > 0:

        for device in neighbors:
            plugin_objects.add_object(
                primaryId   = device['mac'],
                secondaryId = device['ip'],
                watched4    = device['last_seen'],

                # The following are always unknown
                watched1    = device['hostname'],     # don't use these --> handleEmpty(device['hostname']),
                watched2    = device['vendor'],       # don't use these --> handleEmpty(device['vendor']),
                watched3    = device['device_type'],  # don't use these --> handleEmpty(device['device_type']),
                extra       = '',
                foreignKey  = ""  # device['mac']
                # helpVal1  = "Something1",  # Optional Helper values to be passed for mapping into the app
                # helpVal2  = "Something1",  # If you need to use even only 1, add the remaining ones too
                # helpVal3  = "Something1",  # and set them to 'null'. Check the the docs for details:
                # helpVal4  = "Something1",  # https://docs.netalertx.com/PLUGINS_DEV
            )

        mylog('verbose', [f'[{pluginName}] New entries: "{len(neighbors)}"'])

    # log result
    plugin_objects.write_result_file()

    return 0


def parse_neighbors(raw_neighbors: list[str]):
    neighbors = []
    for line in raw_neighbors:
        if "lladdr" in line and "REACHABLE" in line:
            # Known data
            fields = line.split()

            if not is_multicast(fields[0]):
                # mylog('verbose', [f'[{pluginName}] adding ip {fields[0]}"'])
                neighbor = {}
                neighbor['ip'] = fields[0]
                neighbor['mac'] = fields[2]
                neighbor['last_seen'] = timeNowUTC()

                # Unknown data
                neighbor['hostname'] = '(unknown)'
                neighbor['vendor'] = '(unknown)'
                neighbor['device_type'] = '(unknown)'

                neighbors.append(neighbor)

    return neighbors


def is_multicast(ip):
    prefixes = ['ff', '224', '231', '232', '233', '234', '238', '239']
    return reduce(lambda acc, prefix: acc or ip.startswith(prefix), prefixes, False)


#  retrieve data
def get_neighbors(interfaces):

    results = []

    for interface in interfaces.split(","):
        try:

            # Ping all IPv6 devices in multicast to trigger NDP

            mylog('verbose', [f'[{pluginName}] Pinging on interface: "{interface}"'])
            command = f"ping ff02::1%{interface} -c 2".split()
            subprocess.run(command)
            mylog('verbose', [f'[{pluginName}] Pinging completed: "{interface}"'])

            # Check the neighbourhood tables

            mylog('verbose', [f'[{pluginName}] Scanning interface: "{interface}"'])
            command = f"ip neighbor show nud all dev {interface}".split()
            output = subprocess.check_output(command, universal_newlines=True)
            results += output.split("\n")

            mylog('verbose', [f'[{pluginName}] Scanning interface succeded: "{interface}"'])
        except subprocess.CalledProcessError as e:
            # An error occurred, handle it
            error_type = type(e).__name__  # Capture the error type
            mylog('verbose', [f'[{pluginName}] Scanning interface failed: "{interface}" ({error_type})'])

    return results


if __name__ == '__main__':
    main()
