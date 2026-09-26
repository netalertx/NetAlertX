# 🔌 Plugins

NetAlertX supports additional plugins to extend its functionality, each with its own settings and options. Plugins can be loaded via the General -> `LOADED_PLUGINS` setting. For custom plugin development, refer to the [Plugin development guide](./PLUGINS_DEV.md).

>[!NOTE]
> Please check this [Plugins debugging guide](./DEBUG_PLUGINS.md) and the corresponding Plugin documentation in the below table if you are facing issues.

## ⚡ Quick start

> [!TIP]
> You can load additional Plugins via the General -> `LOADED_PLUGINS` setting. You need to save the settings for the new plugins to load (cache/page reload may be necessary).
> ![Loaded plugins settings](./img/PLUGINS/enable_plugin.gif)

1. Pick your `🔍 dev scanner` plugin (e.g. `ARPSCAN` or `NMAPDEV`), or import devices into the application with an `📥 importer` plugin. (See **Enabling plugins** below)
2. Pick a `▶️ publisher` plugin, if you want to send notifications. If you don't see a publisher you'd like to use, look at the  [📚_publisher_apprise](https://docs.netalertx.com/PLUGINS_OVERVIEW/?h=APPRISE#available-plugins) plugin which is a proxy for over 80 notification services.
3. Setup your [Network topology diagram](./NETWORK_TREE.md)
4. Fine-tune [Notifications](./NOTIFICATIONS.md)
5. Setup [Workflows](./WORKFLOWS.md)
6. [Backup your setup](./BACKUPS.md)
7. Contribute and [Create custom plugins](./PLUGINS_DEV.md)


## Plugin types

| Plugin type    | Icon | Description                                                               | When to run                         | Required | Data source [?](./PLUGINS_DEV.md) |
| -------------- | ---- | ------------------------------------------------------------------------- | ----------------------------------- | -------- | ------------------------------------- |
| publisher      | ▶️   | Sending notifications to services.                                       | `on_notification`                   | ✖        | Script                                |
| dev scanner    | 🔍   | On-network scanner discovering devices without a 3rd party service       | `schedule`                          | ✖        | Script / SQLite DB                    |
| name discovery | 🆎   | Discovers names of devices via various protocols.                        | `before_name_updates`, `schedule`   | ✖        | Script                                |
| importer       | 📥   | Importing devices from another service.                                  | `schedule`                          | ✖        | Script / SQLite DB                    |
| system         | ⚙    | Providing core system functionality.                                     | `schedule` / always on              | ✖/✔      | Script / Template                     |
| other          | ♻    | Other plugins                                                            | misc                                | ✖        | Script / Template                     |

## Features

| Icon | Description                                                    |
| ---- | -------------------------------------------------------------- |
| 🖧    | Auto-imports the network topology diagram                     |
| 🔄    | Has the option to sync some data back into the plugin source |


## Available Plugins

Device-detecting plugins insert values into the `CurrentScan` database table.  The plugins that are not required are safe to ignore, however, it makes sense to have at least some device-detecting plugins enabled, such as `ARPSCAN` or `NMAPDEV`.

The **Plugin docs** links below open each plugin's README rendered as part of this site (see the [Plugins reference](./plugins/index.md) section) - generated automatically from `server/plugins/<name>/README.md`.

| ID              | Plugin docs                                                                                                      | Type     | Description                               | Features | Required |
| --------------- | ------------------------------------------------------------------------------------------------------------------ | -------- | ----------------------------------------- | -------- | -------- |
| `APPRISE`       | [_publisher_apprise](plugins/_publisher_apprise.md)          | ▶️       | Apprise notification proxy                |          |          |
| `ARPSCAN`       | [arp_scan](plugins/arp_scan.md)                               | 🔍       | ARP-scan on current network               |          |          |
| `AVAHISCAN`     | [avahi_scan](plugins/avahi_scan.md)                           | 🆎       | Avahi (mDNS-based) name resolution        |          |          |
| `ASUSWRT`       | [asuswrt_import](plugins/asuswrt_import.md)                   | 📥       | Import connected devices from AsusWRT     |          |          |
| `CSVBCKP`       | [csv_backup](plugins/csv_backup.md)                           | ⚙        | CSV devices backup                        |          |          |
| `CUSTPROP`      | [custom_props](plugins/custom_props.md)                       | ⚙        | Managing custom device properties values  |          | Yes      |
| `DBCLNP`        | [db_cleanup](plugins/db_cleanup.md)                           | ⚙        | Database cleanup                          |          | Yes\*    |
| `DDNS`          | [ddns_update](plugins/ddns_update.md)                         | ⚙        | DDNS update                               |          |          |
| `DHCPLSS`       | [dhcp_leases](plugins/dhcp_leases.md)                         | 📥/🆎   | Import devices from DHCP leases           |          |          |
| `DHCPSRVS`      | [dhcp_servers](plugins/dhcp_servers.md)                       | ♻        | DHCP servers                              |          |          |
| `DIGSCAN`       | [dig_scan](plugins/dig_scan.md)                               | 🆎       | Dig (DNS) Name resolution                 |          |          |
| `DOCKERDISC`    | [dockerdisc](plugins/dockerdisc.md)                           | ♻        | Enriches known Docker hosts with their running containers |          |          |
| `FREEBOX`       | [freebox](plugins/freebox.md)                                  |📥/♻/🆎  | Pull data and names from Freebox/Iliadbox |          |          |
| `FRITZBOX`      | [fritzbox](plugins/fritzbox.md)                                | 📥       | Fritz!Box device scanner via TR-064       |          |          |
| `ICMP`          | [icmp_scan](plugins/icmp_scan.md)                             | ♻        | ICMP (ping) status checker                |          |          |
| `INTRNT`        | [internet_ip](plugins/internet_ip.md)                         | 🔍       | Internet IP scanner                       |          |          |
| `INTRSPD`       | [internet_speedtest](plugins/internet_speedtest.md)           | ♻        | Internet speed test                       |          |          |
| `IPNEIGH`       | [ipneigh](plugins/ipneigh.md)                                  | 🔍       | Scan ARP (IPv4) and NDP (IPv6) tables     |          |          |
| `KEALSS`        | [kea_api](plugins/kea_api.md)                                  | 📥/🆎     | Pull lease data from the Kea DHCP API   |          |          |
| `LUCIRPC`       | [luci_import](plugins/luci_import.md)                         | 📥       | Import connected devices from OpenWRT     |          |          |
| `MAINT`         | [maintenance](plugins/maintenance.md)                          | ⚙        | Maintenance of logs, etc.                 |          |          |
| `MQTT`          | [_publisher_mqtt](plugins/_publisher_mqtt.md)                | ▶️       | MQTT for syncing to Home Assistant         |          |          |
| `MTSCAN`        | [mikrotik_scan](plugins/mikrotik_scan.md)                    | 🔍       | Mikrotik device import & sync              |          |          |
| `NBTSCAN`       | [nbtscan_scan](plugins/nbtscan_scan.md)                       | 🆎       | Nbtscan (NetBIOS-based) name resolution   |          |          |
| `NEWDEV`        | [newdev_template](plugins/newdev_template.md)                 | ⚙        | New device template                       |          | Yes      |
| `NMAP`          | [nmap_scan](plugins/nmap_scan.md)                             | ♻        | Nmap port scanning & discovery            |          |          |
| `NMAPDEV`       | [nmap_dev_scan](plugins/nmap_dev_scan.md)                    | 🔍       | Nmap dev scan on current network           |          |          |
| `NSLOOKUP`      | [nslookup_scan](plugins/nslookup_scan.md)                     | 🆎       | NSLookup (DNS-based) name resolution      |          |          |
| `NTFPRCS`       | [notification_processing](plugins/notification_processing.md) | ⚙        | Notification processing                   |          | Yes      |
| `NTFY`          | [_publisher_ntfy](plugins/_publisher_ntfy.md)                | ▶️       | NTFY notifications                        |          |          |
| `OMDSDN`        | [omada_sdn_imp](plugins/omada_sdn_imp.md)                    | 📥/🆎 ❌  | UNMAINTAINED use `OMDSDNOPENAPI`        | 🖧 🔄    |          |
| `OMDSDNOPENAPI` | [omada_sdn_openapi](plugins/omada_sdn_openapi.md)            | 📥/🆎    | OMADA TP-Link import via OpenAPI          | 🖧       |          |
| `PIHOLE`        | [pihole_scan](plugins/pihole_scan.md)                         | 🆎/📥 | Pi-hole device import & sync               |          |          |
| `PIHOLEAPI`     | [pihole_api_scan](plugins/pihole_api_scan.md)                 | 🆎/📥 | Pi-hole device import & sync via API v6+   |          |          |
| `PIHOLEMON`     | [pihole_monitor](plugins/pihole_monitor.md)                   | 🆎/📥 | Blocked-query anomaly detection (includes primary and secondary DNS import from Pi-hole) |          |          |
| `PUSHSAFER`     | [_publisher_pushsafer](plugins/_publisher_pushsafer.md)      | ▶️       | Pushsafer notifications                   |          |          |
| `PUSHOVER`      | [_publisher_pushover](plugins/_publisher_pushover.md)        | ▶️       | Pushover notifications                    |          |          |
| `RSTIMPRT`      | [rest_import](plugins/rest_import.md)                        | 📥/🆎   | Import via a REST API endpoint             |  🖧      |          |
| `SETPWD`        | [set_password](plugins/set_password.md)                       | ⚙        | Set password                              |          | Yes      |
| `SMTP`          | [_publisher_email](plugins/_publisher_email.md)              | ▶️       | Email notifications                       |          |          |
| `SNMPDSC`       | [snmp_discovery](plugins/snmp_discovery.md)                   | 🔍/📥    | SNMP device import & sync                 |          |          |
| `SYNC`          | [sync](plugins/sync.md)                                      | ⚙/📥     | Sync & import from NetAlertX instances    | 🖧 🔄    | Yes      |
| `TELEGRAM`      | [_publisher_telegram](plugins/_publisher_telegram.md)        | ▶️       | Telegram notifications                    |          |          |
| `UI`            | [ui_settings](plugins/ui_settings.md)                         | ♻        | UI specific settings                      |          | Yes      |
| `UNFIMP`        | [unifi_import](plugins/unifi_import.md)                       | 📥/🆎 | UniFi device import & sync                  | 🖧       |          |
| `UNIFIAPI`      | [unifi_api_import](plugins/unifi_api_import.md)               | 📥/🆎 | UniFi device import (SM API, multi-site)   |           |         |
| `VNDRPDT`       | [vendor_update](plugins/vendor_update.md)                     | ⚙        | Vendor database update                    |          |          |
| `WEBHOOK`       | [_publisher_webhook](plugins/_publisher_webhook.md)          | ▶️       | Webhook notifications                     |          |          |
| `WEBMON`        | [website_monitor](plugins/website_monitor.md)                 | ♻        | Website down monitoring                   |          |          |
| `WIFICANARY`    | [wificanary](plugins/wificanary.md)                            | ♻        | Passive WiFi rogue-AP / evil-twin detection |          |          |
| `WOL`           | [wake_on_lan](plugins/wake_on_lan.md)                        | ♻        | Automatic wake-on-lan                     |          |          |


> \* The database cleanup plugin (`DBCLNP`) is not _required_ but the app will become unusable after a while if not executed.
> ❌ marked for removal/unmaintained - looking for help
> ⌚It's recommended to use the same schedule interval for all plugins responsible for discovering new devices.



## Enabling plugins

Plugins can be enabled via Settings, and can be disabled as needed.

1. Research which plugin you'd like to use, enable `DISCOVER_PLUGINS` and load the required plugins in Settings via the `LOADED_PLUGINS` setting.
1. Save the changes and review the Settings of the newly loaded plugins.
1. Change the `<prefix>_RUN` Setting to the recommended or custom value as per the documentation of the given setting
    - If using `schedule` on a `🔍 dev scanner` plugin, make sure the schedules are the same across all `🔍 dev scanner` plugins

### Disabling, Unloading and Ignoring plugins

1. Change the `<prefix>_RUN` Setting to `disabled` if you want to disable the plugin, but keep the settings
1. (Important) Save the settings
1. (Optional) If you want to speed up the application, you can unload the plugin by unselecting it in the `LOADED_PLUGINS` setting (plugins have to be disabled first - see above steps).
    - Careful, once you save the Settings Unloaded plugin settings will be lost (old `app.conf` files are kept in the `/config` folder)
1. You can completely ignore plugins by placing a `ignore_plugin` file into the plugin directory. Ignored plugins won't show up in the `LOADED_PLUGINS` setting.

## 🆕 Developing new custom plugins

If you want to develop a custom plugin, please read this [Plugin development guide](./PLUGINS_DEV.md).
