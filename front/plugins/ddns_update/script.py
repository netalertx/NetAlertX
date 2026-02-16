#!/usr/bin/env python

import os
import argparse
import sys
import subprocess

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, check_IP_format  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'DDNS'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():

    mylog('verbose', [f'[{pluginName}] In script'])

    parser = argparse.ArgumentParser(description='Check internet connectivity and IP')

    parser.add_argument('prev_ip', action="store", help="Previous IP address to compare against the current IP")
    parser.add_argument('DDNS_UPDATE_URL', action="store", help="URL for updating Dynamic DNS (DDNS)")
    parser.add_argument('DDNS_USER', action="store", help="Username for Dynamic DNS (DDNS) authentication")
    parser.add_argument('DDNS_PASSWORD', action="store", help="Password for Dynamic DNS (DDNS) authentication")
    parser.add_argument('DDNS_DOMAIN', action="store", help="Dynamic DNS (DDNS) domain name")

    values = parser.parse_args()

    PREV_IP         = values.prev_ip.split('=')[1]
    DDNS_UPDATE_URL = values.DDNS_UPDATE_URL.split('=')[1]
    DDNS_USER       = values.DDNS_USER.split('=')[1]
    DDNS_PASSWORD   = values.DDNS_PASSWORD.split('=')[1]
    DDNS_DOMAIN     = values.DDNS_DOMAIN.split('=')[1]

    # perform the new IP lookup and DDNS tasks if enabled
    ddns_update(DDNS_UPDATE_URL, DDNS_USER, DDNS_PASSWORD, DDNS_DOMAIN, PREV_IP)

    mylog('verbose', [f'[{pluginName}] Finished '])

    return 0


# ===============================================================================
# INTERNET IP CHANGE
# ===============================================================================
def ddns_update(DDNS_UPDATE_URL, DDNS_USER, DDNS_PASSWORD, DDNS_DOMAIN, PREV_IP):

    # Update DDNS record if enabled and IP is different
    # Get Dynamic DNS IP

    mylog('verbose', [f'[{pluginName}]    Retrieving Dynamic DNS IP'])
    dns_IP = get_dynamic_DNS_IP(DDNS_DOMAIN)

    # Check Dynamic DNS IP
    if dns_IP == "" or dns_IP == "0.0.0.0" :
        mylog('none', [f'[{pluginName}]     Error retrieving Dynamic DNS IP'])

    mylog('none', [f'[{pluginName}]    ', dns_IP])

    # Check DNS Change
    if dns_IP != PREV_IP :
        mylog('none', [f'[{pluginName}]     Updating Dynamic DNS IP'])
        message = set_dynamic_DNS_IP(DDNS_UPDATE_URL, DDNS_USER, DDNS_PASSWORD, DDNS_DOMAIN)
        mylog('none', [f'[{pluginName}]        ', message])

    # plugin_objects = Plugin_Objects(RESULT_FILE)
    # plugin_objects.add_object(
    #     primaryId   = 'internet',       # MAC (Device Name)
    #     secondaryId = new_internet_IP,  # IP Address
    #     watched1    = f'Previous IP: {PREV_IP}',
    #     watched2    = '',
    #     watched3    = '',
    #     watched4    = '',
    #     extra       = f'Previous IP: {PREV_IP}',
    #     foreignKey  = 'internet')

    # plugin_objects.write_result_file()


# -------------------------------------------------------------------------------
def get_dynamic_DNS_IP(DDNS_DOMAIN):

    # Using supplied DNS server
    dig_args = ['dig', '+short', DDNS_DOMAIN]

    try:
        # try runnning a subprocess
        dig_output = subprocess.check_output(dig_args, universal_newlines=True)
        mylog('none', [f'[{pluginName}] DIG output :', dig_output])
    except subprocess.CalledProcessError as e:
        # An error occured, handle it
        mylog('none', [f'[{pluginName}] ⚠ ERROR - ', e.output])
        dig_output = ''  # probably no internet

    # Check result is an IP
    IP = check_IP_format(dig_output)

    # Handle invalid response
    if IP == '':
        IP = '0.0.0.0'

    return IP


# -------------------------------------------------------------------------------
def set_dynamic_DNS_IP(DDNS_UPDATE_URL, DDNS_USER, DDNS_PASSWORD, DDNS_DOMAIN):
    try:
        # try runnning a subprocess
        # Update Dynamic IP
        curl_output = subprocess.check_output([
            'curl',
            '-s',
            DDNS_UPDATE_URL + 'username=' + DDNS_USER + '&password=' + DDNS_PASSWORD + '&hostname=' + DDNS_DOMAIN],
            universal_newlines=True)
    except subprocess.CalledProcessError as e:
        # An error occured, handle it
        mylog('none', [f'[{pluginName}] ⚠ ERROR - ', e.output])
        curl_output = ""

    return curl_output


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
