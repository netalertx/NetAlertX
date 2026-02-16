#!/usr/bin/env python

import json
import subprocess
import os
import sys
import hashlib
import hmac

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])


import conf  # noqa: E402 [flake8 lint suppression]
from const import logPath, confFileName  # noqa: E402 [flake8 lint suppression]
from plugin_helper import Plugin_Objects, handleEmpty  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, write_file  # noqa: E402 [flake8 lint suppression]
from models.notification_instance import NotificationInstance  # noqa: E402 [flake8 lint suppression]
from database import DB  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'WEBHOOK'

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
        response_stdout, response_stderr = send(
            notification["Text"],
            notification["HTML"],
            notification["JSON"]
        )

        # Log result
        plugin_objects.add_object(
            primaryId   = pluginName,
            secondaryId = timeNowUTC(),
            watched1    = notification["GUID"],
            watched2    = handleEmpty(response_stdout),
            watched3    = handleEmpty(response_stderr),
            watched4    = 'null',
            extra       = 'null',
            foreignKey  = notification["GUID"]
        )

    plugin_objects.write_result_file()


# -------------------------------------------------------------------------------
def check_config():
    if get_setting_value('WEBHOOK_URL') == '':
        return False
    else:
        return True


# -------------------------------------------------------------------------------
def send(text_data, html_data, json_data):

    response_stderr = ''
    response_stdout = ''

    # limit = 1024 * 1024  # 1MB limit (1024 bytes * 1024 bytes = 1MB)
    limit         = get_setting_value('WEBHOOK_SIZE')
    payloadType   = get_setting_value('WEBHOOK_PAYLOAD')
    endpointUrl   = get_setting_value('WEBHOOK_URL')
    secret        = get_setting_value('WEBHOOK_SECRET')
    requestMethod = get_setting_value('WEBHOOK_REQUEST_METHOD')

    # use data type based on specified payload type
    if payloadType == 'json':
        # In this code, the truncate_json function is used to recursively traverse the JSON object
        # and remove nodes that exceed the size limit. It checks the size of each node's JSON representation
        # using json.dumps and includes only the nodes that are within the limit.
        json_str = json.dumps(json_data)

        if len(json_str) <= limit:
            payloadData = json_data
        else:
            def truncate_json(obj):
                if isinstance(obj, dict):
                    return {
                        key: truncate_json(value)
                        for key, value in obj.items()
                        if len(json.dumps(value)) <= limit
                    }
                elif isinstance(obj, list):
                    return [
                        truncate_json(item)
                        for item in obj
                        if len(json.dumps(item)) <= limit
                    ]
                else:
                    return obj

            payloadData = truncate_json(json_data)
    if payloadType == 'html':
        if len(html_data) > limit:
            payloadData = html_data[:limit] + " <h1>(text was truncated)</h1>"
        else:
            payloadData = html_data
    if payloadType == 'text':
        if len(text_data) > limit:
            payloadData = text_data[:limit] + " (text was truncated)"
        else:
            payloadData = text_data

    # Define slack-compatible payload
    if payloadType == 'text':
        _json_payload = {"text": payloadData}
    else:
        _json_payload = {
            "username": "NetAlertX",
            "text": "There are new notifications",
            "attachments": [{
                "title": "NetAlertX Notifications",
                "title_link": get_setting_value('REPORT_DASHBOARD_URL'),
                "text": payloadData
            }]
        }

    # DEBUG - Write the json payload into a log file for debugging
    write_file(logPath + '/webhook_payload.json', json.dumps(_json_payload))

    # Using the Slack-Compatible Webhook endpoint for Discord so that the same payload can be used for both
    #  Consider: curl has the ability to load in data to POST from a file + piping
    if (endpointUrl.startswith('https://discord.com/api/webhooks/') and not endpointUrl.endswith("/slack")):
        _WEBHOOK_URL = f"{endpointUrl}/slack"
        curlParams = ["curl", "-i", "-H", "Content-Type:application/json", "-d", json.dumps(_json_payload), _WEBHOOK_URL]
    else:
        _WEBHOOK_URL = endpointUrl
        curlParams = ["curl", "-i", "-X", requestMethod , "-H", "Content-Type:application/json", "-d", json.dumps(_json_payload), _WEBHOOK_URL]

    # Add HMAC signature if configured
    if (secret != ''):
        h = hmac.new(secret.encode("UTF-8"), json.dumps(_json_payload, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
        curlParams.insert(4, "-H")
        curlParams.insert(5, f"X-Webhook-Signature: sha256={h}")

    try:
        # Execute CURL call
        mylog('debug', [f'[{pluginName}] curlParams: ', curlParams])
        result = subprocess.run(curlParams, capture_output=True, text=True)

        response_stderr = result.stderr
        response_stdout = result.stdout

        # Write stdout and stderr into .log files for debugging if needed
        mylog('debug', [f'[{pluginName}] stdout: ', response_stdout])
        mylog('debug', [f'[{pluginName}] stderr: ', response_stderr])

    except subprocess.CalledProcessError as e:
        # An error occurred, handle it
        mylog('none', [f'[{pluginName}] ⚠ ERROR: ', e.output])

        response_stderr = e.output

    return response_stdout, response_stderr


# -------------------------------------------------------
if __name__ == '__main__':
    sys.exit(main())
