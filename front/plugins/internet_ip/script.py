#!/usr/bin/env python

import os
import time
import argparse
import sys
import subprocess
import re

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger, append_line_to_file  # noqa: E402 [flake8 lint suppression]
from helper import check_IP_format, get_setting_value  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'INTRNT'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

no_internet_ip = '0.0.0.0'


def main():

    mylog('verbose', [f'[{pluginName}] In script'])

    parser = argparse.ArgumentParser(description='Check internet connectivity and IP')

    parser.add_argument('prev_ip', action="store", help="Previous IP address to compare against the current IP")
    parser.add_argument('DIG_GET_IP_ARG', action="store", help="Arguments for the 'dig' command to retrieve the IP address")  # unused

    values = parser.parse_args()

    PREV_IP         = values.prev_ip.split('=')[1]
    DIG_GET_IP_ARG  = get_setting_value("INTRNT_DIG_GET_IP_ARG")

    new_internet_IP = no_internet_ip

    mylog('verbose', [f'[{pluginName}] INTRNT_DIG_GET_IP_ARG: ', DIG_GET_IP_ARG])

    # METHOD 1: dig
    # perform the new IP lookup N times specified by the INTRNT_TRIES setting

    INTRNT_RETRIES  = get_setting_value("INTRNT_RETRIES")
    retries_needed  = 0

    for i in range(INTRNT_RETRIES + 1):

        new_internet_IP, cmd_output = check_internet_IP(PREV_IP, DIG_GET_IP_ARG)

        if new_internet_IP == no_internet_ip:
            time.sleep(1 * i)  # Exponential backoff strategy
        else:
            retries_needed = i
            break

    # METHOD 2: curl
    if new_internet_IP == no_internet_ip:
        new_internet_IP, cmd_output = fallback_check_ip()
        mylog('verbose', [f'[{pluginName}] Curl Fallback (new_internet_IP|cmd_output): {new_internet_IP} | {cmd_output}'])

    #  logging
    append_line_to_file(logPath + '/IP_changes.log', '[' + str(timeNowUTC()) + ']\t' + new_internet_IP + '\n')

    plugin_objects = Plugin_Objects(RESULT_FILE)

    plugin_objects.add_object(
        primaryId   = 'internet',       # MAC (Device Name)
        secondaryId = new_internet_IP,  # IP Address
        watched1    = f'Previous IP: {PREV_IP}',
        watched2    = cmd_output.replace('\n', ''),
        watched3    = retries_needed,
        watched4    = 'Gateway',
        extra       = f'Previous IP: {PREV_IP}',
        foreignKey  = 'internet'
    )

    plugin_objects.write_result_file()

    mylog('verbose', [f'[{pluginName}] Finished '])

    return 0


# ===============================================================================
# INTERNET IP CHANGE
# ===============================================================================
def check_internet_IP(PREV_IP, DIG_GET_IP_ARG):

    # Get internet IP
    mylog('verbose', [f'[{pluginName}] - Retrieving internet IP'])
    internet_IP, cmd_output = get_internet_IP(DIG_GET_IP_ARG)

    mylog('verbose', [f'[{pluginName}]  Current internet_IP : {internet_IP}'])

    # Check previously stored IP
    previous_IP = no_internet_ip

    if PREV_IP is not None and len(PREV_IP) > 0 :
        previous_IP = PREV_IP

    mylog('verbose', [f'[{pluginName}]          previous_IP : {previous_IP}'])

    return internet_IP, cmd_output


# -------------------------------------------------------------------------------
def get_internet_IP(DIG_GET_IP_ARG):

    cmd_output = ''

    # Using 'dig'
    dig_args = ['dig', '+short'] + DIG_GET_IP_ARG.strip().split()
    try:
        cmd_output = subprocess.check_output(dig_args, universal_newlines=True)
        mylog('verbose', [f'[{pluginName}]  DIG result : {cmd_output}'])
    except subprocess.CalledProcessError as e:
        mylog('verbose', [e.output])
        cmd_output = ''  # no internet

    # Check result is an IP
    IP = check_IP_format(cmd_output)

    # Handle invalid response
    if IP == '':
        IP = no_internet_ip

    return IP, cmd_output


# -------------------------------------------------------------------------------
def fallback_check_ip():
    """Fallback mechanism using `curl ifconfig.me/ip`."""
    try:
        cmd_output = subprocess.check_output(['curl', '-s', 'ifconfig.me/ip'], text=True).strip()
        if cmd_output and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", cmd_output):
            mylog('verbose', [f'[{pluginName}] Fallback IP retrieved via curl: {cmd_output}'])
            return cmd_output, f'Fallback via curl: "{cmd_output}"'
        else:
            mylog('verbose', [f'[{pluginName}] Invalid IP received from fallback'])
            return no_internet_ip, f'Fallback via curl failed: "{cmd_output}"'
    except Exception as e:
        mylog('none', [f'[{pluginName}] Fallback curl exception: {e}'])
        return no_internet_ip, f'Fallback via curl exception: "{e}"'


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
