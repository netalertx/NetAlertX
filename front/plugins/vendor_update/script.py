#!/usr/bin/env python

import os
import sys
import subprocess

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects, handleEmpty  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from const import logPath, applicationPath, NULL_EQUIVALENTS_SQL  # noqa: E402 [flake8 lint suppression]
from scan.device_handling import query_MAC_vendor  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
from database import get_temp_db_connection  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'VNDRPDT'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():

    mylog('verbose', ['[VNDRPDT] In script'])

    # Get newest DB
    update_vendor_database()

    # Resolve missing vendors
    plugin_objects = Plugin_Objects(RESULT_FILE)

    plugin_objects = update_vendors(plugin_objects)

    plugin_objects.write_result_file()

    mylog('verbose', ['[VNDRPDT] Update complete'])

    return 0


# ===============================================================================
# Update device vendors database
# ===============================================================================
def update_vendor_database():

    # Update vendors DB (iab oui)
    mylog('verbose', ['    Updating vendors DB (iab & oui)'])
    update_args = ['sh', applicationPath + '/services/update_vendors.sh']

    # Execute command
    try:
        # try runnning a subprocess safely
        subprocess.check_output(update_args)
    except subprocess.CalledProcessError as e:
        # An error occured, handle it
        mylog('verbose', ['    FAILED: Updating vendors DB, set LOG_LEVEL=debug for more info'])
        mylog('verbose', [e.output])


# ------------------------------------------------------------------------------
# resolve missing vendors
def update_vendors(plugin_objects):

    # Connect to the App SQLite database
    conn = get_temp_db_connection()
    cursor = conn.cursor()

    # Initialize variables
    ignored = 0
    notFound = 0

    mylog('verbose', ['    Searching devices vendor'])

    # Get devices without a vendor
    query = f"""
        SELECT
            devMac,
            devLastIP,
            devName,
            devVendor
        FROM Devices
        WHERE devVendor IN ({NULL_EQUIVALENTS_SQL}) OR devVendor IS NULL
    """
    cursor.execute(query)
    devices = cursor.fetchall()
    conn.commit()

    # Close the database connection
    conn.close()

    # All devices loop
    for device in devices:
        # Search vendor in HW Vendors DB
        vendor = query_MAC_vendor(device[0])
        if vendor == -1 :
            notFound += 1
        elif vendor == -2 :
            ignored += 1
        else :
            plugin_objects.add_object(
                primaryId   = handleEmpty(device[0]),    # MAC (Device Name)
                secondaryId = handleEmpty(device[1]),    # IP Address (always 0.0.0.0)
                watched1    = handleEmpty(vendor),
                watched2    = handleEmpty(device[2]),    # Device name
                watched3    = "",
                watched4    = "",
                extra       = "",
                foreignKey  = handleEmpty(device[0])
            )

    # Print log
    mylog('verbose', ["    Devices Ignored             : ", ignored])
    mylog('verbose', ["    Devices with missing vendor : ", len(devices)])
    mylog('verbose', ["    Vendors Not Found           : ", notFound])
    mylog('verbose', ["    Vendors updated             : ", len(plugin_objects)])

    return plugin_objects


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
