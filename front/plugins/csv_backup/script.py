#!/usr/bin/env python

import os
import argparse
import sys
import csv

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value   # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
from database import get_temp_db_connection  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'CSVBCKP'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():

    # the script expects a parameter in the format of devices=device1,device2,...
    parser = argparse.ArgumentParser(description='Export devices data to CSV')
    parser.add_argument('overwrite', action="store", help="Specify 'TRUE' to overwrite an existing file, or 'FALSE' to create a new file")
    parser.add_argument('location', action="store", help="The directory where the CSV file will be saved")
    values = parser.parse_args()

    overwrite = values.overwrite.split('=')[1]

    if (overwrite.upper() == "TRUE"):
        overwrite = True
    else:
        overwrite = False

    mylog('verbose', ['[CSVBCKP] In script'])

    # Connect to the App database
    conn = get_temp_db_connection()
    cursor = conn.cursor()

    # Execute your SQL query
    cursor.execute("SELECT * FROM Devices")

    # Get column names
    columns = [desc[0] for desc in cursor.description]

    if overwrite:
        filename = 'devices.csv'
    else:
        timestamp = timeNowUTC(as_string=False).strftime('%Y%m%d%H%M%S')
        filename = f'devices_{timestamp}.csv'

    fullPath = os.path.join(values.location.split('=')[1], filename)

    mylog('verbose', ['[CSVBCKP] Writing file ', fullPath])

    # Create a CSV file in the specified location
    with open(fullPath, 'w', newline='') as csvfile:
        # Initialize the CSV writer
        csv_writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)

        # Wrap the header values in double quotes and write the header row
        csv_writer.writerow(['"' + col + '"' for col in columns])

        # Fetch and write data rows
        for row in cursor.fetchall():
            # Wrap each value in double quotes and write the row
            csv_writer.writerow(['"' + str(value) + '"' for value in row])

    # Close the database connection
    conn.close()

    # Open the CSV file for reading
    with open(fullPath, 'r') as file:
        data = file.read()

    # Replace all occurrences of """ with "
    data = data.replace('"""', '"')

    # Open the CSV file for writing
    with open(fullPath, 'w') as file:
        file.write(data)

    return 0


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
