## Overview

A plugin allowing for importing devices from a UniFi controller. The plugin also tries to import the network map.

### Usage

Specify the following settings in the Settings section of NetAlertX:

- `UNFIMP_username` - Username used to log in the UNIFI controller.
- `UNFIMP_password` - Password used to log in the UNIFI controller.
- `UNFIMP_host` - Host URL or IP address where the UNIFI controller is hosted (excluding `http://`)
- `UNFIMP_sites` - Name of the sites (usually 'default', check the URL in your UniFi controller UI if unsure. The site id is in the following part of the URL: `https://192.168.1.1:8443/manage/site/this-is-the-site-id/settings/`).
- `UNFIMP_protocol` - https:// or http://
- `UNFIMP_port` - Usually `8443`, `8843`, or `443` (UPSTREAM BUG: Setting `UNFIMP_version='UDMP-unifiOS'` will force `443` see [#1524](https://github.com/netalertx/NetAlertX/issues/1524) or switch to the `UNIFIAPI` plugin)
- `UNFIMP_version` - see below table for details


#### Config overview

|   Controller                                           |      `UNFIMP_version`     | `UNFIMP_port`                        |
| ------------------------------------------------------ | ------------------------- | ------------------------------------ |
| Cloud Gateway Ultra / UCK cloudkey V2 plus (v4.0.18)   |      `UDMP-unifiOS`       | `443`  (BUG: always forced)          |
| Docker hosted                                          |      `v5`                 | `8443` (usually)                     |

### Notes

- It is recommended to create a read-only user in your UniFi controller