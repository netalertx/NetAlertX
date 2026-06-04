#!/usr/bin/env python3
import os
import sys
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../server'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../plugins'))

from plugin_helper import Plugin_Objects, mylog, handleEmpty, is_mac
from helper import get_setting_value
from const import logPath

pluginName = 'KEALSS'
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

plugin_objects = Plugin_Objects(RESULT_FILE)


def main():
    try:
        url = get_setting_value(f'{pluginName}_URL')
        user = get_setting_value(f'{pluginName}_USER')
        password = get_setting_value(f'{pluginName}_PASS')
        timeout = get_setting_value(f'{pluginName}_RUN_TIMEOUT')

        mylog('verbose', [f'[{pluginName}] Querying Kea API at {url}'])

        payload = {'command': 'lease4-get-all', 'service': ['dhcp4']}

        response = requests.post(url, json=payload, auth=(user, password), timeout=max(1, timeout - 1))
        response.raise_for_status()
        data = response.json()

        count = 0
        for entry in data:
            text = entry.get('text', '[API provided no text]')
            # Result: 0 (success), 1 (error), or 3 (empty).
            if entry['result'] == 0:
                leases = entry['arguments']['leases']
                for lease in leases:
                    mac = lease['hw-address']                    
                    state = lease['state']
                    if is_mac(mac):
                        plugin_objects.add_object(
                            primaryId   = mac,
                            secondaryId = lease['ip-address'],
                            # Active or not, similar to watched1 of DHCPLSS plugin
                            watched1    = state == 0, 
                            watched2    = lease['hostname'],
                            watched3    = None,
                            # Default (or assigned) (0), declined (1), expired-reclaimed (2), released (3), and registered (4)).
                            watched4    = state,
                            extra       = None,
                            foreignKey  = mac
                        )
                        count += 1
                plugin_objects.write_result_file()

                mylog('verbose', [f'[{pluginName}] Kea API response: {text}'])
                mylog('verbose', [f'[{pluginName}] Successfully imported {count} devices reported by Kea API'])
            elif entry['result'] == 1:
                mylog('none', [f'[{pluginName}] ⚠ ERROR: Kea API indicated error: {text}'])
            elif entry['result'] == 3:
                mylog('verbose', [f'[{pluginName}] Kea API indicates no entries found: {text}'])


    except Exception as e:
        mylog('none', [f'[{pluginName}] ⚠ ERROR: {str(e)}'])



if __name__ == '__main__':
    main()
