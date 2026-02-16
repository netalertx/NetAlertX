#!/usr/bin/env python

import json
import subprocess
import os
import sys

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

import conf  # noqa: E402 [flake8 lint suppression]
from const import confFileName, logPath  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from models.notification_instance import NotificationInstance  # noqa: E402 [flake8 lint suppression]
from database import DB  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value("TIMEZONE"))

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

pluginName = "APPRISE"

LOG_PATH = logPath + "/plugins"
RESULT_FILE = os.path.join(LOG_PATH, f"last_result.{pluginName}.log")


def main():
    mylog("verbose", [f"[{pluginName}](publisher) In script"])

    # Check if basic config settings supplied
    if check_config() is False:
        mylog("none", f"[{pluginName}] ⚠ ERROR: Publisher notification gateway not set up correctly. Check your {confFileName} {pluginName}_* variables.")
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
        result = send(notification["HTML"], notification["Text"])

        # Log result
        plugin_objects.add_object(
            primaryId   = pluginName,
            secondaryId = timeNowUTC(),
            watched1    = notification["GUID"],
            watched2    = result,
            watched3    = 'null',
            watched4    = 'null',
            extra       = 'null',
            foreignKey  = notification["GUID"]
        )

    plugin_objects.write_result_file()


# -------------------------------------------------------------------------------
def check_config():
    if get_setting_value("APPRISE_HOST") == "" or (
        get_setting_value("APPRISE_URL") == "" and get_setting_value("APPRISE_TAG") == ""
    ):
        return False
    else:
        return True


# -------------------------------------------------------------------------------
def send(html, text):
    payloadData = ""
    result = ""

    # limit = 1024 * 1024  # 1MB limit (1024 bytes * 1024 bytes = 1MB)
    limit = get_setting_value("APPRISE_SIZE")

    #  truncate size
    if get_setting_value("APPRISE_PAYLOAD") == "html":
        if len(html) > limit:
            payloadData = html[:limit] + "<h1>(text was truncated)</h1>"
        else:
            payloadData = html
    if get_setting_value("APPRISE_PAYLOAD") == "text":
        if len(text) > limit:
            payloadData = text[:limit] + " (text was truncated)"
        else:
            payloadData = text

    # Define Apprise compatible payload (https://github.com/caronc/apprise-api#stateless-solution)

    target_key = "tag" if get_setting_value("APPRISE_TARGETTYPE") == "tag" else "urls"
    target_value = (
        get_setting_value("APPRISE_TAG")
        if target_key == "tag"
        else get_setting_value("APPRISE_URL")
    )

    _json_payload = {
        target_key: target_value,
        "title": "NetAlertX Notifications",
        "format": get_setting_value("APPRISE_PAYLOAD"),
        "body": payloadData,
    }

    try:
        # try runnning a subprocess
        p = subprocess.Popen(
            [
                "curl",
                "-i",
                "-X",
                "POST",
                "-H",
                "Content-Type:application/json",
                "-d",
                json.dumps(_json_payload),
                get_setting_value("APPRISE_HOST"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        stdout, stderr = p.communicate()

        # write stdout and stderr into .log files for debugging if needed
        # Log the stdout and stderr
        mylog("debug", [stdout, stderr])

        # log result
        result = stdout

    except subprocess.CalledProcessError as e:
        # An error occurred, handle it
        mylog("none", [e.output])

        # log result
        result = e.output

    return result


if __name__ == "__main__":
    sys.exit(main())
