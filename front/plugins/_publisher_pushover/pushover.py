#!/usr/bin/env python3
import conf
from const import logPath
from pytz import timezone

import os
import sys
import json
import requests

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects, handleEmpty  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, hide_string  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from models.notification_instance import NotificationInstance  # noqa: E402 [flake8 lint suppression]
from database import DB  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value("TIMEZONE"))

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

pluginName = "PUSHOVER"

LOG_PATH = logPath + "/plugins"
RESULT_FILE = os.path.join(LOG_PATH, f"last_result.{pluginName}.log")


def main():
    mylog("verbose", f"[{pluginName}](publisher) In script")

    # Check if basic config settings supplied
    if not validate_config():
        mylog("none", f"[{pluginName}] ⚠ ERROR: Publisher not set up correctly. Check your {pluginName}_* variables.",)
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

    # Process the new notifications
    for notification in new_notifications:
        # Send notification
        response_text, response_status_code = send(notification["Text"])

        # Log result
        plugin_objects.add_object(
            primaryId=pluginName,
            secondaryId=timeNowUTC(),
            watched1=notification["GUID"],
            watched2=handleEmpty(response_text),
            watched3=response_status_code,
            watched4="null",
            extra="null",
            foreignKey=notification["GUID"],
        )

    plugin_objects.write_result_file()


def send(text):
    response_text = ""
    response_status_code = ""

    user_key = get_setting_value("PUSHOVER_USER_KEY")
    app_token = get_setting_value("PUSHOVER_APP_TOKEN")
    device_name = (
        None
        if get_setting_value("PUSHOVER_DEVICE_NAME") == "DEVICE_NAME"
        else get_setting_value("PUSHOVER_DEVICE_NAME")
    )

    mylog("verbose", f'[{pluginName}] PUSHOVER_USER_KEY: "{hide_string(user_key)}"')
    mylog("verbose", f'[{pluginName}] PUSHOVER_APP_TOKEN: "{hide_string(app_token)}"')

    data = {"token": app_token, "user": user_key, "message": text}
    # Add device_name to the data dictionary only if it is not None
    if device_name:
        data["device"] = device_name

    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data=data)

        # Update response_status_code with the actual status code from the response
        response_status_code = response.status_code

        # Check if the request was successful (status code 200)
        if response_status_code == 200:
            response_text = response.text  # This captures the response body/message
        else:
            response_text = json.dumps(response.text)

    except requests.exceptions.RequestException as e:
        mylog("none", f"[{pluginName}] ⚠ ERROR: {e}")
        response_text = str(e)

    return response_text, response_status_code


def validate_config():
    user_key = get_setting_value("PUSHOVER_USER_KEY")
    app_token = get_setting_value("PUSHOVER_APP_TOKEN")

    return user_key != "USER_KEY" and app_token != "APP_TOKEN"


if __name__ == "__main__":
    sys.exit(main())
