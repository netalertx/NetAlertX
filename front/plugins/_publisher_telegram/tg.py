#!/usr/bin/env python

import subprocess
import os
import sys
import json

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

import conf  # noqa: E402 [flake8 lint suppression]
from const import confFileName, logPath  # noqa: E402 [flake8 lint suppression]
from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from models.notification_instance import NotificationInstance  # noqa: E402 [flake8 lint suppression]
from database import DB  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'TELEGRAM'

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():
    mylog('verbose', [f'[{pluginName}](publisher) In script'])

    # Check if basic config settings supplied
    if check_config() is False:
        mylog('none', [
            f'[{pluginName}] ⚠ ERROR: Publisher notification gateway not set up correctly. Check your {confFileName} {pluginName}_* variables.'])
        return

    # Create a database connection
    db = DB()  # instance of class DB
    db.open()

    # Initialize the Plugin obj output file
    plugin_objects = Plugin_Objects(RESULT_FILE)

    # Create a NotificationInstance instance
    notifications = NotificationInstance(db)

    # Retrieve new notifications
    new_notifications = notifications.getNew()

    # Process the new notifications (see the Notifications DB table for structure or check the /php/server/query_json.php?file=table_notifications.json endpoint)
    for notification in new_notifications:
        # Send notification
        result = send(notification["Text"])

        # Log result
        plugin_objects.add_object(
            primaryId=pluginName,
            secondaryId=timeNowUTC(),
            watched1=notification["GUID"],
            watched2=result,
            watched3='null',
            watched4='null',
            extra='null',
            foreignKey=notification["GUID"]
        )

    plugin_objects.write_result_file()


# -------------------------------------------------------------------------------
def check_config():
    return True


# -------------------------------------------------------------------------------
def send(text):
    """
    Send a Telegram notification.
    """
    limit = get_setting_value('TELEGRAM_SIZE')

    # Ensure the final payload, including the truncation marker,
    # never exceeds TELEGRAM_SIZE.
    truncation_marker = " (text was truncated)"
    if len(text) > limit:
        payload_data = text[:max(0, limit - len(truncation_marker))] + truncation_marker
    else:
        payload_data = text

    payload = json.dumps({
        "chat_id": get_setting_value('TELEGRAM_HOST'),
        "text": payload_data,
        "disable_notification": False
    })

    cmd = [
        "curl",
        "--location",

        # Prevent curl from hanging indefinitely.
        # Both values are intentionally below RUN_TIMEOUT.
        "--connect-timeout", "10",
        "--max-time", "20",

        f"https://api.telegram.org/bot{get_setting_value('TELEGRAM_URL')}/sendMessage",
        "--header",
        "Content-Type: application/json",
        "--data",
        payload,
    ]
.
    mylog("debug", ["Executing: Telegram sendMessage", "--data <json>"])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

        mylog("debug", [proc.stdout])

        return proc.stdout

    except OSError as e:
        mylog("none", [str(e)])
        return str(e)


if __name__ == '__main__':
    sys.exit(main())
