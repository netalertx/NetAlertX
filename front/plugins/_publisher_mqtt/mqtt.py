#!/usr/bin/env python

import json
import os
import sys
from datetime import datetime
import time
import re
import paho.mqtt.client as mqtt
# from paho.mqtt import client as mqtt_client
# from paho.mqtt import CallbackAPIVersion as mqtt_CallbackAPIVersion
import hashlib
from pytz import timezone


# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

# NetAlertX modules
import conf  # noqa: E402 [flake8 lint suppression]
from const import confFileName, logPath  # noqa: E402 [flake8 lint suppression]
from utils.plugin_utils import getPluginObject  # noqa: E402 [flake8 lint suppression]
from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, bytes_to_string, \
    sanitize_string, normalize_string  # noqa: E402 [flake8 lint suppression]
from database import DB, get_device_stats  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from models.notification_instance import NotificationInstance  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'MQTT'

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)
# Create an MD5 hash object
md5_hash = hashlib.md5()


# globals
mqtt_sensors                = []
mqtt_connected_to_broker    = False
mqtt_client                 = None  # mqtt client
topic_root                  = get_setting_value('MQTT_topic_root')


def main():

    mylog('verbose', [f'[{pluginName}](publisher) In script'])

    # Check if basic config settings supplied
    if not check_config():
        return

    # Create a database connection
    db = DB()  # instance of class DB
    db.open()

    mqtt_start(db)
    mqtt_client.disconnect()

    plugin_objects.write_result_file()


# -----------------------------------------------------------------------------
# MQTT
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
def check_config():
    """
    Checks whether the MQTT configuration settings are properly set.

    Returns:
        bool: True if all required MQTT settings
              ('MQTT_BROKER', 'MQTT_PORT')
              are non-empty;
              False otherwise. Logs a verbose error message
              if any setting is missing.
    """
    if get_setting_value('MQTT_BROKER') == '' or get_setting_value('MQTT_PORT') == '':
        mylog('verbose', [f'[Check Config] ⚠ ERROR: MQTT service not set up \
            correctly. Check your {confFileName} MQTT_BROKER and MQTT_PORT variables.'])
        return False
    else:
        return True


# -----------------------------------------------------------------------------
# Sensor configs are tracking which sensors in NetAlertX exist
# and if a config has changed
class sensor_config:
    def __init__(self,
                 deviceId,
                 deviceName,
                 sensorType,
                 sensorName,
                 icon,
                 mac):
        """
        Initialize the sensor_config object with provided parameters.
        Sets up sensor configuration and generates necessary MQTT topics
        and messages based on the sensor type.
        """
        # Assign initial attributes
        self.deviceId        = deviceId
        self.deviceName      = deviceName
        self.sensorType      = sensorType
        self.sensorName      = sensorName
        self.icon            = icon
        self.mac             = mac
        self.model           = deviceName
        self.hash            = ''
        self.state_topic     = ''
        self.json_attr_topic = ''
        self.topic           = ''
        self.message         = {}  # Initialize message as an empty dictionary
        self.unique_id       = ''

        # Call helper functions to initialize the message, generate a hash,
        # and handle plugin object
        self.initialize_message()
        self.generate_hash()
        self.handle_plugin_object()

    def initialize_message(self):
        """
        Initialize the MQTT message payload based on the sensor type.
        This method handles sensors of types:
        - 'timestamp'
        - 'binary_sensor'
        - 'sensor'
        - 'device_tracker'
        """
        # Ensure self.message is initialized as a dictionary
        # if not already done
        if not isinstance(self.message, dict):
            self.message = {}

        # Handle sensors with a 'timestamp' device class
        if self.sensorName in ['last_connection', 'first_connection']:
            self.message.update({
                "device_class": "timestamp"
            })

        # Handle 'binary_sensor' or 'sensor' types
        if self.sensorType in ['binary_sensor', 'sensor']:
            self.topic          = f'homeassistant/{self.sensorType}/{self.deviceId}/{self.sensorName}/config'
            self.state_topic    = f'{topic_root}/{self.sensorType}/{self.deviceId}/state'
            self.unique_id      = f'{self.deviceId}_sensor_{self.sensorName}'

            # Update the message dictionary, expanding it without overwriting
            self.message.update({
                "name": self.sensorName,
                "state_topic": self.state_topic,
                "value_template": f"{{{{value_json.{self.sensorName}}}}}",
                "unique_id": self.unique_id,
                "device": {
                    "identifiers": [f"{self.deviceId}_sensor"],
                    "manufacturer": "NetAlertX",
                    "name": self.deviceName
                },
                "icon": f'mdi:{self.icon}'
            })

        # Handle 'device_tracker' sensor type
        elif self.sensorType == 'device_tracker':
            self.topic           = f'homeassistant/device_tracker/{self.deviceId}/config'
            self.state_topic     = f'{topic_root}/device_tracker/{self.deviceId}/state'
            self.json_attr_topic = f'{topic_root}/device_tracker/{self.deviceId}/attributes'
            self.unique_id       = f'{self.deviceId}_{self.sensorType}_{self.sensorName}'

            # Construct the message dictionary for device_tracker
            self.message = {
                "state_topic": self.state_topic,
                "json_attributes_topic": self.json_attr_topic,
                "name": self.sensorName,
                "payload_home": 'home',
                "payload_not_home": 'away',
                "unique_id": self.unique_id,
                "icon": f'mdi:{self.icon}',
                "device": {
                    "identifiers": [f"{self.deviceId}_sensor", self.unique_id],
                    "manufacturer": "NetAlertX",
                    "model": self.model or "Unknown",  # Use model if available, else set to 'Unknown'
                    "name": self.deviceName
                }
            }

    def generate_hash(self):
        """
        Generate an MD5 hash based on the combined string of deviceId, deviceName, sensorType, sensorName, and icon.
        This hash will uniquely identify the sensor configuration.
        """
        # Concatenate all relevant attributes into a single string
        input_string = f"{self.deviceId}{self.deviceName}{self.sensorType}{self.sensorName}{self.icon}"
        md5_hash = hashlib.md5()  # Initialize the MD5 hash object
        md5_hash.update(input_string.encode('utf-8'))  # Update hash with input string
        self.hash = md5_hash.hexdigest()  # Store the hex representation of the hash

    def handle_plugin_object(self):
        """
        Fetch the plugin object from the system based on the generated hash. If the object exists, it logs that the sensor is
        already known. If not, it marks the sensor as new and logs relevant information.
        """
        # Retrieve the plugin object based on the sensor's hash
        plugObj = getPluginObject({"Plugin": "MQTT", "Watched_Value3": self.hash})

        # Check if the plugin object is new
        if not plugObj:
            self.isNew = True
            mylog('verbose', [f"[{pluginName}] New sensor entry (name|mac|hash) : ({self.deviceName}|{self.mac}|{self.hash}"])
        else:
            device_name = plugObj.get("Watched_Value1", "Unknown")
            mylog('verbose', [f"[{pluginName}] Existing, skip Device Name: {device_name}"])
            self.isNew = False

        # Store the sensor configuration in global plugin_objects
        self.store_plugin_object()

    def store_plugin_object(self):
        """
        Store the sensor configuration in the global plugin_objects, which tracks sensors based on a unique combination
        of attributes including deviceId, sensorName, hash, and MAC.
        """

        # Add the sensor to the global plugin_objects
        plugin_objects.add_object(
            primaryId=self.deviceId,
            secondaryId=self.sensorName,
            watched1=self.deviceName,
            watched2=self.sensorType,
            watched3=self.hash,
            watched4=self.mac,
            extra=f"{self.deviceId}{self.deviceName}{self.sensorType}{self.sensorName}{self.icon}",
            foreignKey=self.mac
        )


# -------------------------------------------------------------------------------

def publish_mqtt(mqtt_client, topic, message):
    """
    Publishes a message to an MQTT topic using the provided MQTT client.
    If the message is not a string, it is converted to a JSON-formatted string.
    The function retrieves the desired QoS level from settings and logs the publishing process.
    If the client is not connected to the broker, the function logs an error and aborts.
    It attempts to publish the message, retrying until the publish status indicates success.
    Args:
        mqtt_client: The MQTT client instance used to publish the message.
        topic (str): The MQTT topic to publish to.
        message (Any): The message payload to send. Non-string messages are converted to JSON.
    Returns:
        bool: True if the message was published successfully, False if not connected to the broker.
    """
    status = 1

    # convert anything but a simple string to json
    if not isinstance(message, str):
        message = json.dumps(message).replace("'", '"')

    qos = get_setting_value('MQTT_QOS')

    mylog('debug', [f"[{pluginName}] Sending MQTT topic: {topic}",
                    f"[{pluginName}] Sending MQTT message: {message}"])
    # mylog('verbose', [f"[{pluginName}] get_setting_value('MQTT_QOS'): {qos}"])

    if not mqtt_connected_to_broker:
        mylog('minimal', [f"[{pluginName}] ⚠ ERROR: Not connected to broker, aborting."])
        return False

    while status != 0:

        # mylog('verbose', [f"[{pluginName}]  mqtt_client.publish "])
        # mylog('verbose', [f"[{pluginName}]  mqtt_client.is_connected(): {mqtt_client.is_connected()} "])

        result = mqtt_client.publish(
            topic=topic,
            payload=message,
            qos=qos,
            retain=True,
        )

        status = result[0]

        # mylog('verbose', [f"[{pluginName}] status: {status}"])
        # mylog('verbose', [f"[{pluginName}] result: {result}"])

        if status != 0:
            mylog('debug', [f"[{pluginName}] Waiting to reconnect to MQTT broker"])
            time.sleep(0.1)
    return True


# ------------------------------------------------------------------------------
# Create a generic device for overal stats
def create_generic_device(mqtt_client, deviceId, deviceName):

    create_sensor(mqtt_client, deviceId, deviceName, 'sensor', 'online', 'wifi-check')
    create_sensor(mqtt_client, deviceId, deviceName, 'sensor', 'down', 'wifi-cancel')
    create_sensor(mqtt_client, deviceId, deviceName, 'sensor', 'all', 'wifi')
    create_sensor(mqtt_client, deviceId, deviceName, 'sensor', 'archived', 'wifi-lock')
    create_sensor(mqtt_client, deviceId, deviceName, 'sensor', 'new', 'wifi-plus')
    create_sensor(mqtt_client, deviceId, deviceName, 'sensor', 'unknown', 'wifi-alert')


# ------------------------------------------------------------------------------
# Register sensor config on the broker
def create_sensor(mqtt_client, deviceId, deviceName, sensorType, sensorName, icon, mac=""):

    #  check previous configs
    sensorConfig = sensor_config(deviceId, deviceName, sensorType, sensorName, icon, mac)

    # Create the HA sensor config if a new device is discovered
    if sensorConfig.isNew:

        # add the sensor to the global list to keep track of succesfully added sensors
        if publish_mqtt(mqtt_client, sensorConfig.topic, sensorConfig.message):
            # hack - delay adding to the queue in case the process is
            # restarted and previous publish processes aborted
            # (it takes ~2s to update a sensor config on the broker)
            time.sleep(get_setting_value('MQTT_DELAY_SEC'))
            mqtt_sensors.append(sensorConfig)

    return sensorConfig


# -----------------------------------------------------------------------------
def mqtt_create_client():

    # attempt reconnections on failure, ref https://www.emqx.com/en/blog/how-to-use-mqtt-in-python
    FIRST_RECONNECT_DELAY = 1
    RECONNECT_RATE = 2
    MAX_RECONNECT_COUNT = 12
    MAX_RECONNECT_DELAY = 60

    mytransport = 'tcp'  # or 'websockets'

    def on_disconnect(mqtt_client, userdata, rc, properties=None, *args):

        mylog('verbose', [f"[{pluginName}] MQTT disconnected: reasonCode={rc}"])

        global mqtt_connected_to_broker

        mylog('verbose', [f"[{pluginName}]         Connection terminated, reason_code: {rc}"])
        reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
        while reconnect_count < MAX_RECONNECT_COUNT:
            mylog('verbose', [f"[{pluginName}]         Reconnecting in {reconnect_delay} seconds..."])
            time.sleep(reconnect_delay)

            try:
                mqtt_client.reconnect()
                mqtt_connected_to_broker = True     # Signal connection
                mylog('verbose', [f"[{pluginName}]         Reconnected successfully"])
                return
            except Exception as err:
                mylog('verbose', [f"[{pluginName}]         {err} Reconnect failed. Retrying..."])

            reconnect_delay *= RECONNECT_RATE
            reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
            reconnect_count += 1

        mqtt_connected_to_broker = False

    def on_connect(mqtt_client, userdata, flags, rc, properties):

        global mqtt_connected_to_broker

        # REF: Good docu on reason codes: https://www.emqx.com/en/blog/mqtt5-new-features-reason-code-and-ack
        if rc == 0:
            mylog('verbose', [f"[{pluginName}]         Connected to broker"])
            mqtt_connected_to_broker = True     # Signal connection
        else:
            mylog('verbose', [f"[{pluginName}]         Connection failed, reason_code: {rc}"])
            mqtt_connected_to_broker = False

    global mqtt_client
    global mqtt_connected_to_broker

    # Paho will be soon not supporting V1 anymore, so this really should not be a user choice to start with
    # This code now uses V2 by default
    # Ref: https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html

    if get_setting_value('MQTT_VERSION') == 3:
        version = mqtt.MQTTv311
    else:
        version = mqtt.MQTTv5

    # we now hardcode the client id into here.
    # TODO: Add config for client id (atm, we use a fixed client id,
    # so only one instance of NetAlertX can connect to the broker at any given time)
    # If you intend to run multiple instances simultaneously, make sure to set unique client IDs for each instance.
    mqtt_client = mqtt.Client(
        client_id='netalertx',
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        transport=mytransport,
        protocol=version)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect

    if get_setting_value('MQTT_TLS'):
        mqtt_client.tls_set()

    mqtt_client.username_pw_set(username=get_setting_value('MQTT_USER'), password=get_setting_value('MQTT_PASSWORD'))
    err_code = mqtt_client.connect(host=get_setting_value('MQTT_BROKER'), port=get_setting_value('MQTT_PORT'))
    if (err_code == mqtt.MQTT_ERR_SUCCESS):
        # We (prematurely) set the connection state to connected
        # the callback may be delayed
        mqtt_connected_to_broker = True
    # the client connects but connect callbacks will be called async and there may be a waiting time
    # Mosquitto works straight away
    # EMQX has a delay and does not update in loop below, so we cannot rely on it, we wait 1 sec
    time.sleep(1)
    mqtt_client.loop_start()

    return mqtt_client


# -----------------------------------------------------------------------------
def mqtt_start(db):

    global mqtt_client

    if not mqtt_connected_to_broker:
        mqtt_client = mqtt_create_client()

    deviceName      = get_setting_value('MQTT_DEVICE_NAME')
    deviceId        = get_setting_value('MQTT_DEVICE_ID')

    # General stats

    # Create a generic device for overal stats
    if get_setting_value('MQTT_SEND_STATS'):
        # Create a new device representing overall stats
        create_generic_device(mqtt_client, deviceId, deviceName)

        # Get the data
        row = get_device_stats(db)

        # Publish (wrap into {} and remove last ',' from above)
        publish_mqtt(
            mqtt_client,
            f"{topic_root}/sensor/{deviceId}/state",
            {
                "online": row[0],
                "down": row[1],
                "all": row[2],
                "archived": row[3],
                "new": row[4],
                "unknown": row[5]
            }
        )

    #  Notifications
    if get_setting_value('MQTT_SEND_NOTIFICATIONS'):
        publish_notifications(db, mqtt_client)

    # Generate device-specific MQTT messages if enabled
    if get_setting_value('MQTT_SEND_DEVICES'):

        # Specific devices processing

        # Get all devices
        devices = db.read(get_setting_value('MQTT_DEVICES_SQL').replace('{s-quote}', "'"))

        sec_delay = len(devices) * int(get_setting_value('MQTT_DELAY_SEC')) * 5

        mylog('verbose', [f"[{pluginName}]         Estimated delay: ", (sec_delay), 's ', '(', round(sec_delay / 60, 1), 'min)'])

        for device in devices:

            # # debug statement START 🔻
            # if 'Moto' not in device["devName"]:
            #     mylog('none', [f"[{pluginName}]  ALERT - ⚠⚠⚠⚠ DEBUGGING ⚠⚠⚠⚠ - this should not be in uncommented in production"])
            #     continue
            # # debug statement END   🔺

            # Create devices in Home Assistant - send config messages
            deviceId        = 'mac_' + device["devMac"].replace(" ", "").replace(":", "_").lower()
            # Normalize the string and remove unwanted characters
            devDisplayName = re.sub('[^a-zA-Z0-9-_\\s]', '', normalize_string(device["devName"]))

            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'sensor', 'last_ip', 'ip-network', device["devMac"])
            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'sensor', 'mac_address', 'folder-key-network', device["devMac"])
            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'sensor', 'is_new', 'bell-alert-outline', device["devMac"])
            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'sensor', 'vendor', 'cog', device["devMac"])
            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'sensor', 'first_connection', 'calendar-start', device["devMac"])
            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'sensor', 'last_connection', 'calendar-end', device["devMac"])

            # handle device_tracker
            # IMPORTANT: shared payload - device_tracker attributes and individual sensors
            devJson = {
                "last_ip": device["devLastIP"],
                "is_new": str(device["devIsNew"]),
                "alert_down": str(device["devAlertDown"]),
                "vendor": sanitize_string(device["devVendor"]),
                "mac_address": str(device["devMac"]),
                "model": devDisplayName,
                "last_connection": prepTimeStamp(str(device["devLastConnection"])),
                "first_connection": prepTimeStamp(str(device["devFirstConnection"])),
                "sync_node": device["devSyncHubNode"],
                "group": device["devGroup"],
                "location": device["devLocation"],
                "network_parent_mac": device["devParentMAC"],
                "network_parent_name": next((dev["devName"] for dev in devices if dev["devMac"] == device["devParentMAC"]), "")
            }

            # bulk update device sensors in home assistant
            publish_mqtt(mqtt_client, sensorConfig.state_topic, devJson)  # REQUIRED, DON'T DELETE

            #  create and update is_present sensor
            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'binary_sensor', 'is_present', 'wifi', device["devMac"])
            publish_mqtt(
                mqtt_client,
                sensorConfig.state_topic,
                {
                    "is_present": to_binary_sensor(str(device["devPresentLastScan"]))
                }
            )

            # handle device_tracker
            sensorConfig = create_sensor(mqtt_client, deviceId, devDisplayName, 'device_tracker', 'is_home', 'home', device["devMac"])

            # <away|home> are only valid states
            state = 'away'
            if to_binary_sensor(str(device["devPresentLastScan"])) == "ON":
                state = 'home'

            publish_mqtt(mqtt_client, sensorConfig.state_topic, state)

            # publish device_tracker attributes
            publish_mqtt(mqtt_client, sensorConfig.json_attr_topic, devJson)


# ---------------------------------------------------------------------
# Publish webhook-style notifications via MQTT
# ---------------------------------------------------------------------
def publish_notifications(db, mqtt_client):
    """
    Gather pending notifications and publish a single JSON payload via MQTT
    that mirrors the webhook structure.
    Only runs if MQTT_SEND_NOTIFICATIONS is enabled.
    """

    # Ensure MQTT client is connected
    if not mqtt_connected_to_broker:
        mylog('minimal', [f"[{pluginName}] ⚠ ERROR: Not connected to broker, aborting notification publish."])
        return False

    notifications = NotificationInstance(db).getNew() or []
    if not notifications:
        mylog('debug', [f"[{pluginName}] No new notifications to publish via MQTT."])
        return False

    for notification in notifications:
        # Use pre-built JSON payload if available in the 'JSON' column
        payload_str = notification["JSON"]
        if payload_str:
            try:
                payload = json.loads(payload_str)  # Deserialize JSON string
            except Exception as e:
                mylog('minimal', [f"[{pluginName}] ⚠ ERROR decoding JSON for notification GUID {notification['GUID']}: {e}"])
                continue  # skip this notification
        else:
            # fallback generic payload (like webhook does)
            payload = {
                "username": "NetAlertX",
                "text": "There are new notifications",
                "attachments": [{
                    "title": "NetAlertX Notifications",
                    "title_link": get_setting_value('REPORT_DASHBOARD_URL'),
                    "text": notification["Text"] or notification["HTML"] or ""
                }]
            }

        # Optional: attach meta info
        payload["_meta"] = {
            "published_at": timeNowUTC(),
            "source": "NetAlertX",
            "notification_GUID": notification["GUID"]
        }

        # Publish to a single MQTT topic safely
        topic = f"{topic_root}/notifications/all"
        mylog('debug', [f"[{pluginName}] Publishing notification GUID {notification['GUID']} to MQTT topic {topic}"])
        try:
            publish_mqtt(mqtt_client, topic, payload)
        except Exception as e:
            mylog('minimal', [f"[{pluginName}] ⚠ ERROR publishing MQTT notification GUID {notification['GUID']}: {e}"])

    return True


# =============================================================================
# Home Assistant UTILs
# =============================================================================
def to_binary_sensor(input):
    """
    Converts various input types to a binary sensor state ("ON" or "OFF") for Home Assistant.
    """
    if isinstance(input, (int, float)) and input >= 1:
        return "ON"
    elif isinstance(input, bool) and input:
        return "ON"
    elif isinstance(input, str) and input == "1":
        return "ON"
    elif isinstance(input, bytes) and bytes_to_string(input) == "1":
        return "ON"
    return "OFF"


#  -------------------------------------
# Convert to format that is interpretable by Home Assistant
def prepTimeStamp(datetime_str):
    try:
        # Attempt to parse the input string to ensure it's a valid datetime
        parsed_datetime = datetime.fromisoformat(datetime_str)

        # If the parsed datetime is naive (i.e., does not contain timezone info), add UTC timezone
        if parsed_datetime.tzinfo is None:
            parsed_datetime = conf.tz.localize(parsed_datetime)

    except ValueError:
        mylog('verbose', [f"[{pluginName}]  Timestamp conversion failed of string '{datetime_str}'"])
        # Use the current time if the input format is invalid
        parsed_datetime = timeNowUTC(as_string=False)

    # Convert to the required format with 'T' between date and time and ensure the timezone is included
    return parsed_datetime.isoformat()  # This will include the timezone offset


#  -------------INIT---------------------
if __name__ == '__main__':
    sys.exit(main())
