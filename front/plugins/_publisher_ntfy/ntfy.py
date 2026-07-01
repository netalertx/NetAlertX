#!/usr/bin/env python

import json
import os
import re
import sys
import requests
from base64 import b64encode

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

import conf  # noqa: E402 [flake8 lint suppression]
from const import confFileName, logPath  # noqa: E402 [flake8 lint suppression]
from plugin_helper import Plugin_Objects, handleEmpty  # noqa: E402 [flake8 lint suppression]
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

pluginName = 'NTFY'

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
        response_text, response_status_code = send(notification["HTML"], notification["Text"])

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
def check_config():
    if get_setting_value('NTFY_HOST') == '' or get_setting_value('NTFY_TOPIC') == '':
        return False
    else:
        return True


# -------------------------------------------------------------------------------
def send(html, text):

    response_text = ''
    response_status_code = ''

    # settings
    token = get_setting_value('NTFY_TOKEN')
    user = get_setting_value('NTFY_USER')
    pwd = get_setting_value('NTFY_PASSWORD')
    verify_ssl = get_setting_value('NTFY_VERIFY_SSL')
    custom_header_name = get_setting_value('NTFY_CUSTOMHEADER_NAME')
    custom_header_value = get_setting_value('NTFY_CUSTOMHEADER_VALUE')
    # Strip a leading '?' so both "p_token=..." and "?p_token=..." work; requests
    # adds the '?' itself, and a leading one would produce a broken "??" in the URL.
    url_query_string = get_setting_value('NTFY_URL_QUERY_STRING').lstrip('?')

    # prepare request headers
    headers = {
        "Title": "NetAlertX Notification",
        "Actions": "view, Open Dashboard, " + get_setting_value('REPORT_DASHBOARD_URL'),
        "Priority": get_setting_value('NTFY_PRIORITY'),
        "Tags": "warning"
    }

    # if token or username and password are set generate hash and update header
    if token != '':
        headers["Authorization"] = "Bearer {}".format(token)
    elif user != "" and pwd != "":
        # Generate hash for basic auth
        basichash = b64encode(bytes(user + ':' + pwd, "utf-8")).decode("ascii")
        # add authorization header with hash
        headers["Authorization"] = "Basic {}".format(basichash)

    # Optional custom header, e.g. to authenticate through a reverse proxy / tunnel
    # (Pangolin, Tailscale, ...) sitting in front of the ntfy instance. Skip it if it
    # would clobber a built-in header (e.g. Authorization) so ntfy auth stays intact.
    if custom_header_name != '' and custom_header_value != '':
        if custom_header_name.lower() in {k.lower() for k in headers}:
            mylog('none', [f'[{pluginName}] ⚠ Custom header "{custom_header_name}" collides with a built-in header; skipping it.'])
        else:
            headers[custom_header_name] = custom_header_value

    # call NTFY service
    try:
        response = requests.post("{}/{}".format(
            get_setting_value('NTFY_HOST'),
            get_setting_value('NTFY_TOPIC')),
            data    = text,
            headers = headers,
            params  = url_query_string if url_query_string != '' else None,
            verify  = verify_ssl,
            timeout = get_setting_value('NTFY_RUN_TIMEOUT')
        )

        response_status_code = response.status_code

        # Check if the request was successful (status code 200)
        if response_status_code == 200:
            response_text = response.text  # This captures the response body/message
        else:
            response_text = json.dumps(response.text)

    except requests.exceptions.RequestException as e:
        # The exception message embeds the request URL, which may include a secret
        # query string (e.g. a proxy token). Redact the query part before it is
        # logged and persisted to the plugin result file / shown in the UI.
        error_text = str(e)
        if url_query_string != '':
            error_text = re.sub(r'(\?)\S+', r'\1<redacted>', error_text)

        mylog('none', [f'[{pluginName}] ⚠ ERROR: ', error_text])

        response_text = error_text

        return response_text, response_status_code

    return response_text, response_status_code


if __name__ == '__main__':
    sys.exit(main())
