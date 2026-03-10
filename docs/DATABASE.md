
# A high-level description of the database structure

 An overview of the most important database tables as well as an detailed overview of the Devices table. The MAC address is used as a foreign key in most cases.

## Devices database table

| Field Name              | Description | Sample Value |
|-------------------------|-------------|--------------|
| `devMac`               | MAC address of the device. | `00:1A:2B:3C:4D:5E` |
| `devName`              | Name of the device. | `iPhone 12` |
| `devOwner`             | Owner of the device. | `John Doe` |
| `devType`              | Type of the device (e.g., phone, laptop, etc.). If set to a network type (e.g., switch), it will become selectable as a Network Parent Node. | `Laptop` |
| `devVendor`            | Vendor/manufacturer of the device. | `Apple` |
| `devFavorite`          | Whether the device is marked as a favorite. | `1` |
| `devGroup`             | Group the device belongs to. | `Home Devices` |
| `devComments`          | User comments or notes about the device. | `Used for work purposes` |
| `devFirstConnection`   | Timestamp of the device's first connection. | `2025-03-22 12:07:26+11:00` |
| `devLastConnection`    | Timestamp of the device's last connection. | `2025-03-22 12:07:26+11:00` |
| `devLastIP`            | Last known IP address of the device. | `192.168.1.5` |
| `devStaticIP`          | Whether the device has a static IP address. | `0` |
| `devScan`              | Whether the device should be scanned. | `1` |
| `devLogEvents`         | Whether events related to the device should be logged. | `0` |
| `devAlertEvents`       | Whether alerts should be generated for events. | `1` |
| `devAlertDown`         | Whether an alert should be sent when the device goes down. | `0` |
| `devCanSleep`          | Whether the device can enter a sleep window. When `1`, offline periods within the `NTFPRCS_sleep_time` window are shown as **Sleeping** instead of **Down** and no down alert is fired. | `0` |
| `devSkipRepeated`      | Whether to skip repeated alerts for this device. | `1` |
| `devLastNotification`  | Timestamp of the last notification sent for this device. | `2025-03-22 12:07:26+11:00` |
| `devPresentLastScan`   | Whether the device was present during the last scan. | `1` |
| `devIsNew`             | Whether the device is marked as new. | `0` |
| `devLocation`          | Physical or logical location of the device. | `Living Room` |
| `devIsArchived`        | Whether the device is archived. | `0` |
| `devParentMAC`         | MAC address of the parent device (if applicable) to build the [Network Tree](./NETWORK_TREE.md). | `00:1A:2B:3C:4D:5F` |
| `devParentPort`        | Port of the parent device to which this device is connected. | `Port 3` |
| `devIcon`              | [Icon](./ICONS.md) representing the device. The value is a base64-encoded SVG or Font Awesome HTML tag. | `PHN2ZyB...` |
| `devGUID`              | Unique identifier for the device. | `a2f4b5d6-7a8c-9d10-11e1-f12345678901` |
| `devSite`              | Site or location where the device is registered. | `Office` |
| `devSSID`              | SSID of the Wi-Fi network the device is connected to. | `HomeNetwork` |
| `devSyncHubNode`       | The NetAlertX node ID used for synchronization between NetAlertX instances. | `node_1` |
| `devSourcePlugin`      | Source plugin that discovered the device. | `ARPSCAN` |
| `devCustomProps`       | [Custom properties](./CUSTOM_PROPERTIES.md) related to the device. The value is a base64-encoded JSON object. | `PHN2ZyB...` |
| `devFQDN`              | Fully qualified domain name. | `raspberrypi.local` |
| `devParentRelType`     | The type of relationship between the current device and it's parent node. By default, selecting `nic` will hide it from lists. | `nic` |
| `devReqNicsOnline`     | If all NICs are required to be online to mark teh current device online. | `0` |

> [!NOTE]
> `DevicesView` extends the `Devices` table with two computed fields that are never persisted:
> - `devIsSleeping` (`1` when `devCanSleep=1`, device is offline, and `devLastConnection` is within the `NTFPRCS_sleep_time` window).
> - `devFlapping` (`1` when the device has changed state more than the flap threshold times in the trailing window).
> - `devStatus` — derived string: `On-line`, `Sleeping`, `Down`, or `Off-line`.


To understand how values of these fields influuence application behavior, such as Notifications or Network topology, see also:

- [Device Management](./DEVICE_MANAGEMENT.md)
- [Network Tree Topology Setup](./NETWORK_TREE.md)
- [Notifications](./NOTIFICATIONS.md)


## Other Tables overview

  | Table name | Description  | Sample data |
  |----------------------|----------------------| ----------------------|
  | CurrentScan | Result of the current scan | ![Screen1][screen1]  |
  | Devices     | The main devices database that also contains the Network tree mappings. If `ScanCycle` is set to `0` device is not scanned. | ![Screen2][screen2]  |
  | Events | Used to collect connection/disconnection events. | ![Screen4][screen4]  |
  | Online_History   | Used to display the `Device presence` chart  | ![Screen6][screen6]  |
  | Parameters       | Used to pass values between the frontend and backend. | ![Screen7][screen7]  |
  | Plugins_Events   | For capturing events exposed by a plugin via the `last_result.log` file. If unique then saved into the `Plugins_Objects` table. Entries are deleted once processed and stored in the `Plugins_History` and/or `Plugins_Objects` tables.  | ![Screen10][screen10]  |
  | Plugins_History  | History of all entries from the `Plugins_Events` table | ![Screen11][screen11]  |
  | Plugins_Language_Strings  | Language strings collected from the plugin `config.json` files used for string resolution in the frontend. | ![Screen12][screen12]  |
  | Plugins_Objects  | Unique objects detected by individual plugins. | ![Screen13][screen13]  |
  | Sessions  | Used to display sessions in the charts | ![Screen15][screen15]  |
  | Settings  | Database representation of the sum of all settings from `app.conf` and plugins coming from `config.json` files. | ![Screen16][screen16]  |



  [screen1]: ./img/DATABASE/CurrentScan.png
  [screen2]: ./img/DATABASE/Devices.png
  [screen4]: ./img/DATABASE/Events.png
  [screen6]: ./img/DATABASE/Online_History.png
  [screen7]: ./img/DATABASE/Parameters.png
  [screen10]: ./img/DATABASE/Plugins_Events.png
  [screen11]: ./img/DATABASE/Plugins_History.png
  [screen12]: ./img/DATABASE/Plugins_Language_Strings.png
  [screen13]: ./img/DATABASE/Plugins_Objects.png
  [screen15]: ./img/DATABASE/Sessions.png
  [screen16]: ./img/DATABASE/Settings.png

