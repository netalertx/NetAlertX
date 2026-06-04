## Overview

A plugin allowing for importing devices from the Kea DHCP API.  
https://www.isc.org/kea/

And specifically:
https://kea.readthedocs.io/en/kea-2.6.3/api.html#lease4-get-all


### Usage

To enable the API, first you want to add something like this to your main kea configuration (this is for debian 13):

```json
    "control-socket": {
        "socket-type": "unix",
        "socket-name": "/run/kea/kea4-ctrl-socket"
    },
    
    "hooks-libraries": [
        {
            "library": "/usr/lib/x86_64-linux-gnu/kea/hooks/libdhcp_lease_cmds.so"
        }
    ],
```

    
And you need to install kea-ctrl-agent, with a config that looks something like this:
    
```json
{
"Control-agent": {
    "http-host": "127.0.0.1",
    "http-port": 8000,

    "authentication": {
        "type": "basic",
        "realm": "Kea Control Agent",
        "directory": "/etc/kea",
        "clients": [
            {
                "user": "kea-api",
                "password-file": "kea-api-password"
            }
        ]
    },
    "control-sockets": {
        "dhcp4": {
            "socket-type": "unix",
            "socket-name": "/run/kea/kea4-ctrl-socket"
        }
    },
    "loggers": [
    {
        "name": "kea-ctrl-agent",
        "output-options": [
            {
                "output": "stdout",
                "pattern": "%-5p %m\n"
            }
        ],
        "severity": "INFO",
        "debuglevel": 0
    }
  ]
}
}
```

You will need to configure the plugin with the URL to the API, and the username and password configured above (from kea-api-password file in the example)


#### Required Settings

These settings are required, besides the common device scanner settings:

- **Kea Control Agent URL** (`KEALSS_URL`): The full URL, including port number, to the Kea API.
  - Default: `http://127.0.0.1:8000`
  - This mirrors what you set up in the kea-ctrl-agent configuration.

- **Basic Auth Username** (`KEALSS_USER`): The user to use for authenticating with the Kea API. 
  - Default: `kea-api`
  - This mirrors what you set up in the kea-ctrl-agent configuration.

- **Basic Auth Password** (`KEALSS_PASS`): The password to use for authenticating with the Kea API. 
  - This mirrors what you set up in the kea-ctrl-agent configuration.
  - When using a password file, it should be the content of the password file.


### Notes

- This was tested on a basic Debian 13 install.
- When you install kea-ctrl-agent, it should ask you about creating a password.
- It's possible to run kea-ctrl-agent without password, but it's not recommended and at the moment we don't support that.
- I may provide some minimal support, if you ask nicely :)

- Version: 1.0.0
- Author: `void-spark`
- Release Date: `11/05/2026`
