#!/usr/bin/env python

import os
import sys
import speedtest
import subprocess
import json

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
from const import logPath, NATIVE_SPEEDTEST_PATH  # noqa: E402 [flake8 lint suppression]
# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'INTRSPD'

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():

    mylog('verbose', [f"[{pluginName}] In script"])

    plugin_objects = Plugin_Objects(RESULT_FILE)
    speedtest_result = run_speedtest()
    plugin_objects.add_object(
        primaryId   = 'Speedtest',
        secondaryId = timeNowUTC(),
        watched1    = speedtest_result['download_speed'],
        watched2    = speedtest_result['upload_speed'],
        watched3    = speedtest_result['full_json'],
        watched4    = 'null',
        extra       = 'null',
        foreignKey  = 'null'
    )
    plugin_objects.write_result_file()


def run_speedtest():
    native_path = NATIVE_SPEEDTEST_PATH
    mylog('verbose', [f"[{pluginName}] Using native binary path: {native_path}"])
    if os.path.exists(native_path):
        mylog('verbose', [f"[{pluginName}] Native speedtest binary detected, using it."])
        try:
            timeout = get_setting_value('INTRSPD_RUN_TIMEOUT')

            cmd = [native_path, "--format=json", "--accept-license", "--accept-gdpr"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    download_speed = round(data['download']['bandwidth'] * 8 / 10**6, 2)
                    upload_speed = round(data['upload']['bandwidth'] * 8 / 10**6, 2)
                except (json.JSONDecodeError, KeyError, TypeError) as parse_error:
                    mylog('none', [f"[{pluginName}] Failed to parse native JSON: {parse_error}"])
                    # Fall through to baseline fallback
                else:
                    mylog('verbose', [f"[{pluginName}] Native Result (down|up): {download_speed} Mbps|{upload_speed} Mbps"])
                    return {
                        'download_speed': download_speed,
                        'upload_speed': upload_speed,
                        'full_json': result.stdout.strip()
                    }

        except subprocess.TimeoutExpired:
            mylog('none', [f"[{pluginName}] Native speedtest timed out, falling back to baseline."])
        except Exception as e:
            mylog('none', [f"[{pluginName}] Error running native speedtest: {e!s}, falling back to baseline."])

    # Baseline fallback
    try:
        st = speedtest.Speedtest(secure=True)
        st.get_best_server()
        download_speed = round(st.download() / 10**6, 2)
        upload_speed = round(st.upload() / 10**6, 2)
        mylog('verbose', [f"[{pluginName}] Baseline Result (down|up): {download_speed} Mbps|{upload_speed} Mbps"])
        return {
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'full_json': json.dumps(st.results.dict())
        }
    except Exception as e:
        mylog('verbose', [f"[{pluginName}] Error running speedtest: {str(e)}"])
        return {
            'download_speed': -1,
            'upload_speed': -1,
            'full_json': json.dumps({"error": str(e)})
        }


if __name__ == '__main__':
    sys.exit(main())
