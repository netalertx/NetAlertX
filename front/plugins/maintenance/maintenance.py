#!/usr/bin/env python

import os
import sys
from collections import deque

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from messaging.in_app import remove_old  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'MAINT'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():

    mylog('verbose', [f'[{pluginName}] In script'])

    MAINT_LOG_LENGTH = int(get_setting_value('MAINT_LOG_LENGTH'))
    MAINT_NOTI_LENGTH = int(get_setting_value('MAINT_NOTI_LENGTH'))

    logFiles = ["app.log", "nginx-error.log", "stdout.log"]

    # Check if set
    if MAINT_LOG_LENGTH != 0:

        for fileEntry in logFiles:

            mylog('verbose', [f'[{pluginName}] Cleaning file'])

            logFile = logPath + "/" + fileEntry

            mylog('verbose', [f'[{pluginName}] {fileEntry} size BEFORE: {os.path.getsize(logFile)}'])

            # Using a deque to efficiently keep the last N lines
            lines_to_keep = deque(maxlen=MAINT_LOG_LENGTH)

            with open(logFile, 'r') as file:
                # Read lines from the file and store the last N lines
                for line in file:
                    lines_to_keep.append(line)

            with open(logFile, 'w') as file:
                # Write the last N lines back to the file
                file.writelines(lines_to_keep)

            mylog('verbose', [f'[{pluginName}] {fileEntry} size AFTER: {os.path.getsize(logFile)}'])

            mylog('verbose', [f'[{pluginName}] Cleanup of {fileEntry} finished'])

    # Check if set
    if MAINT_NOTI_LENGTH != 0:
        mylog('verbose', [f'[{pluginName}] Cleaning in-app notification history'])
        remove_old(MAINT_NOTI_LENGTH)

    # Delete processed sync artefact files older than 24 hours.
    # These are created by the SYNC plugin (Mode 3) when it renames received
    # device JSON files to processed_*.log after processing. They have no value
    # once processed and are not cleaned up anywhere else.
    _PROCESSED_MAX_AGE_SECS = 24 * 3600
    now = timeNowUTC(as_string=False).timestamp()
    deleted = 0
    for fname in os.listdir(LOG_PATH):
        if fname.startswith('processed_') and fname.endswith('.log'):
            fpath = os.path.join(LOG_PATH, fname)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > _PROCESSED_MAX_AGE_SECS:
                os.remove(fpath)
                deleted += 1
    mylog('verbose', [f'[{pluginName}] Deleted {deleted} processed sync artefact file(s) from {LOG_PATH}'])

    return 0


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
