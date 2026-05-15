#!/usr/bin/env python
# Based on the work of https://github.com/leiweibau/Pi.Alert

import requests
from requests.exceptions import SSLError, Timeout, RequestException
import sys
import os
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value   # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'WEBMON'

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

mylog('verbose', [f'[{pluginName}] In script'])


def main():

    values = get_setting_value('WEBMON_urls_to_check')

    mylog('verbose', [f'[{pluginName}] Checking URLs: {values}'])

    if len(values) > 0:
        plugin_objects = Plugin_Objects(RESULT_FILE)
        # plugin_objects = service_monitoring(values.urls.split('=')[1].split(','), plugin_objects)
        plugin_objects = service_monitoring(values, plugin_objects)
        plugin_objects.write_result_file()
    else:
        return


def check_services_health(site):

    mylog('verbose', [f'[{pluginName}] Checking {site}'])

    urllib3.disable_warnings(InsecureRequestWarning)

    try:
resp = requests.get(site, verify=True, timeout=get_setting_value('WEBMON_RUN_TIMEOUT'), headers={"User-Agent": "NetAler
        latency = resp.elapsed.total_seconds()
        status = resp.status_code
    except SSLError:
        status = 495  # SSL Certificate Error (non-standard, but more meaningful than 503)
        latency = 99999
        mylog('debug', [f'[{pluginName}] SSL error while checking {site}'])
    except Timeout:
        status = 504  # Gateway Timeout
        latency = 99999
        mylog('debug', [f'[{pluginName}] Timeout while checking {site}'])
    except RequestException as e:
        status = 520  # Web server is returning an unknown error (Cloudflare-style)
        latency = 99999
        mylog('debug', [f'[{pluginName}] Request error while checking {site}: {e}'])
    except Exception as e:
        status = 500  # Internal Server Error (fallback)
        latency = 99999
        mylog('debug', [f'[{pluginName}] Unexpected error while checking {site}: {e}'])

    mylog('verbose', [f'[{pluginName}] Result for {site} (status|latency) : {status}|{latency}'])

    return status, latency


def service_monitoring(urls, plugin_objects):
    for site in urls:
        status, latency = check_services_health(site)
        plugin_objects.add_object(
            primaryId=site,
            secondaryId='null',
            watched1=status,
            watched2=latency,
            watched3='null',
            watched4='null',
            extra='null',
            foreignKey='null'
        )
    return plugin_objects


if __name__ == '__main__':
    sys.exit(main())
