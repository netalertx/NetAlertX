#!/usr/bin/env python
import json
import os
import sys
import requests

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

import conf  # noqa: E402 [flake8 lint suppression]
from const import confFileName, logPath  # noqa: E402 [flake8 lint suppression]
from plugin_helper import Plugin_Objects, handleEmpty  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, hide_string  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from models.notification_instance import NotificationInstance  # noqa: E402 [flake8 lint suppression]
from database import DB  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'PUSHSAFER'

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():

    mylog('verbose', [f'[{pluginName}](publisher) In script'])

    # Check if basic config settings supplied
    if check_config() is False:
        mylog('none', [f'[{pluginName}] ⚠ ERROR: Publisher notification gateway not set up correctly. Check your {confFileName} {pluginName}_* variables.'])
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
        response_text, response_status_code = send(notification["Text"])

        # Log result
        plugin_objects.add_object(
            primaryId   = pluginName,
            secondaryId = timeNowUTC(),
            watched1    = notification["GUID"],
            watched2    = handleEmpty(response_text),
            watched3    = response_status_code,
            watched4    = 'null',
            extra       = 'null',
            foreignKey  = notification["GUID"]
        )

    plugin_objects.write_result_file()


# -------------------------------------------------------------------------------
def send(text):

    response_text = ''
    response_status_code = ''

    token = get_setting_value('PUSHSAFER_TOKEN')

    mylog('verbose', [f'[{pluginName}] PUSHSAFER_TOKEN: "{hide_string(token)}"'])

    try:
        url = 'https://www.pushsafer.com/api'
        post_fields = {
            "t" : 'NetAlertX Message',
            "m" : text,
            "s" : 11,
            "v" : 3,
            "i" : 148,
            "c" : '#ef7f7f',
            "d" : 'a',
            "u" : get_setting_value('REPORT_DASHBOARD_URL'),
            "ut" : 'Open NetAlertX',
            "k" : token,
        }
        response = requests.post(url, data=post_fields, timeout=get_setting_value("PUSHSAFER_RUN_TIMEOUT"))
        response_status_code = response.status_code

        # Check if the request was successful (status code 200)
        if response_status_code == 200:
            response_text = response.text  # This captures the response body/message
        else:
            response_text = json.dumps(response.text)

    except requests.exceptions.RequestException as e:
        mylog('none', [f'[{pluginName}] ⚠ ERROR: ', e])

        response_text = e

        return response_text, response_status_code

    return response_text, response_status_code


# -------------------------------------------------------------------------------
def check_config():
    if get_setting_value('PUSHSAFER_TOKEN') == 'ApiKey':
        return False
    else:
        return True


#  -------------------------------------------------------
if __name__ == '__main__':
    sys.exit(main())
