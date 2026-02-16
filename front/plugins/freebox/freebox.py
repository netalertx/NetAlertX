#!/usr/bin/env python

import os
import sys
from pytz import timezone
import asyncio
from datetime import datetime
from pathlib import Path
from typing import cast
import socket
import aiofreepybox
from aiofreepybox import Freepybox
from aiofreepybox.api.lan import Lan
from aiofreepybox.exceptions import NotOpenError, AuthorizationError

# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC, DATETIME_PATTERN  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value("TIMEZONE"))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'FREEBOX'

# Define the current path and log file paths
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)

device_type_map = {
    "workstation": "PC",
    "laptop": "Laptop",
    "smartphone": "Smartphone",
    "tablet": "Tablet",
    "printer": "Printer",
    "vg_console": "Game Console",
    "television": "SmartTV",
    "nas": "NAS",
    "ip_camera": "IP Camera",
    "ip_phone": "Phone",
    "freebox_player": "TV Decoder",
    "freebox_hd": "TV Decoder",
    "freebox_crystal": "TV Decoder",
    "freebox_mini": "TV Decoder",
    "freebox_delta": "Gateway",
    "freebox_one": "Gateway",
    "freebox_wifi": "Gateway",
    "freebox_pop": "AP",
    "networking_device": "Router",
    "multimedia_device": "TV Decoder",
    "car": "House Appliance",
    "watch": "Clock",
    "light": "Domotic",
    "outlet": "Domotic",
    "appliances": "House Appliance",
    "thermostat": "Domotic",
    "shutter": "Domotic",
    "other": "(Unknown)",
}


def map_device_type(type: str):
    try:
        return device_type_map[type]
    except KeyError:
        # This device type has not been mapped yet
        mylog("minimal", [f"[{pluginName}] Unknown device type: {type}"])
        return device_type_map["other"]


async def get_device_data(api_version: int, api_address: str, api_port: int):
    # ensure existence of db path
    config_base = Path(os.getenv("NETALERTX_CONFIG", "/data/config"))
    data_dir = config_base / "freeboxdb"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Instantiate Freepybox class using default application descriptor
    # and custom token_file location
    fbx = Freepybox(
        app_desc={
            "app_id": "netalertx",
            "app_name": "NetAlertX",
            "app_version": aiofreepybox.__version__,
            "device_name": socket.gethostname(),
        },
        api_version="v" + str(api_version),
        data_dir=data_dir,
    )

    # Connect to the freebox
    # Be ready to authorize the application on the Freebox if you run this
    # for the first time
    try:
        await fbx.open(host=api_address, port=api_port)
    except NotOpenError as e:
        mylog("verbose", [f"[{pluginName}] Error connecting to freebox: {e}"])
    except AuthorizationError as e:
        mylog("verbose", [f"[{pluginName}] Auth error: {str(e)}"])

    # get also info of the freebox itself
    config = await fbx.system.get_config()
    freebox = await cast(Lan, fbx.lan).get_config()
    hosts = await cast(Lan, fbx.lan).get_hosts_list()
    assert config is not None
    assert freebox is not None
    freebox["mac"] = config["mac"]
    freebox["operator"] = config["model_info"]["net_operator"]

    # Close the freebox session
    await fbx.close()

    return freebox, hosts


def main():
    mylog("verbose", [f"[{pluginName}] In script"])

    # Retrieve configuration settings
    api_settings = {
        "api_address": get_setting_value("FREEBOX_address"),
        "api_version": get_setting_value("FREEBOX_api_version"),
        "api_port": get_setting_value("FREEBOX_api_port"),
    }

    mylog("verbose", [f"[{pluginName}] Settings: {api_settings}"])

    # retrieve data
    loop = asyncio.new_event_loop()
    freebox, hosts = loop.run_until_complete(get_device_data(**api_settings))
    loop.close()

    mylog("verbose", [freebox])
    mylog("verbose", [hosts])

    plugin_objects.add_object(
        primaryId=freebox["mac"],
        secondaryId=freebox["ip"],
        watched1=freebox["name"],
        watched2=freebox["operator"],
        watched3="Gateway",
        watched4=timeNowUTC(),
        extra="",
        foreignKey=freebox["mac"],
    )
    for host in hosts:
        # Check if 'l3connectivities' exists and is a list
        if "l3connectivities" in host and isinstance(host["l3connectivities"], list):
            for ip in [ip for ip in host["l3connectivities"] if ip.get("reachable")]:
                mac: str = host.get("l2ident", {}).get("id", "(unknown)")
                if mac != '(unknown)':
                    plugin_objects.add_object(
                        primaryId=mac,
                        secondaryId=ip.get("addr", "0.0.0.0"),
                        watched1=host.get("primary_name", "(unknown)"),
                        watched2=host.get("vendor_name", "(unknown)"),
                        watched3=map_device_type(host.get("host_type", "")),
                        watched4=datetime.fromtimestamp(ip.get("last_time_reachable", 0)).strftime(DATETIME_PATTERN),
                        extra="",
                        foreignKey=mac,
                    )
        else:
            # Optional: Log or handle hosts without 'l3connectivities'
            mylog("verbose", [f"[{pluginName}] Host missing 'l3connectivities': {host}"])

    # commit result
    plugin_objects.write_result_file()

    return 0


if __name__ == "__main__":
    main()
