# Device Management

The Main Info section is where most of the device identifiable information is stored and edited. Some of the information is autodetected via various plugins. Initial values for most of the fields can be specified in the `NEWDEV` plugin.

> [!NOTE]
>
> You can multi-edit devices by selecting them in the main Devices view, from the Mainetence section, or via the CSV Export functionality under Maintenance. More info can be found in the [Devices Bulk-editing docs](./DEVICES_BULK_EDITING.md).


 ![Main Info](./img/DEVICE_MANAGEMENT/DeviceManagement_MainInfo.png)

## Main Info

  - **MAC**: MAC addres of the device. Not editable, unless creating a new dummy device.
  - **Last IP**: IP addres of the device. Not editable, unless creating a new dummy device.
  - **Name**: Friendly device name. Autodetected via various 🆎 Name discovery [plugins](https://docs.netalertx.com/PLUGINS). The app attaches `(IP match)` if the name is discovered via an IP match and not MAC match which could mean the name could be incorrect as IPs might change.
  - **Icon**: Partially autodetected. Select an existing or [add a custom icon](./ICONS.md). You can also auto-apply the same icon on all devices of the same type.
  - **Owner**: Device owner (The list is self-populated with existing owners and you can add custom values).
  - **Type**: Select a device type from the dropdown list (`Smartphone`, `Tablet`,
      `Laptop`, `TV`, `router`, etc.) or add a new device type. If you want the device to act as a **Network device** (and be able to be a network node in the Network view), select a type under Network Devices or add a new Network Device type in Settings. More information can be found in the [Network Setup docs](./NETWORK_TREE.md).
  - **Vendor**: The manufacturing vendor. Automatically updated by NetAlertX when empty or unknown, can be edited.
  - **Group**: Select a group (`Always on`, `Personal`, `Friends`, etc.) or type
      your own Group name.
  - **Location**: Select the location, usually a room, where the device is located (`Kitchen`, `Attic`, `Living room`, etc.) or add a custom Location.
  - **Comments**: Add any comments for the device, such as a serial number, or maintenance information.

> [!NOTE]
>
> Please note the above usage of the fields are only suggestions. You can use most of these fields for other purposes, such as storing the network interface, company owning a device, or similar.

## Dummy devices

You can create dummy devices from the Devices listing screen.

![Create Dummy Device](./img/DEVICE_MANAGEMENT/Devices_CreateDummyDevice.png)

The **MAC** field and the **Last IP** field will then become editable.

![Save Dummy Device](./img/DEVICE_MANAGEMENT/DeviceEdit_SaveDummyDevice.png)


## Dummy or Manually Created Device Status

You can control a dummy device’s status either via `ICMP` (automatic) or the `Force Status` field (manual). Choose based on whether the device is real and how important **data hygiene** is.

### `ICMP` (Real Devices)

Use a real IP that responds to ping so status is updated automatically.

### `Force Status` (Best for Data Hygiene)

Manually set the status when the device is not reachable or is purely logical.
This keeps your data clean and avoids fake IPs.

### Loopback IP (`127.0.0.1`, `0.0.0.0`)

Use when you want the device to always appear online via `ICMP`.
Note this simulates reachability and introduces artificial data. This approach might be preferred, if you want to filter and distinguish dummy devices based on IP when filtering your asset lists.


## Copying data from an existing device.

To speed up device population you can also copy data from an existing device. This can be done from the **Tools** tab on the Device details.

## Field Locking (Preventing Plugin Overwrites)

![Field source and locks](./img/DEVICE_MANAGEMENT/field_sources_and_locks.png)

NetAlertX allows you to "lock" specific device fields to prevent plugins from automatically overwriting your custom values. This is useful when you've manually corrected information that might be discovered differently by discovery plugins.

### Quick Start

1. Open a device for editing
2. Click the **lock button** (🔒) next to any tracked field
3. The field is now protected—plugins cannot change it until you unlock it

### See Also

- **For Users:** [Quick Reference - Device Field Lock/Unlock](DEVICE_FIELD_LOCK.md) - How to use field locking
- **For Developers:** [API Device Field Lock Documentation](API_DEVICE_FIELD_LOCK.md) - Technical API reference
- **For Plugin Developers:** [Plugin Field Configuration (SET_ALWAYS/SET_EMPTY)](PLUGINS_DEV_CONFIG.md) - Configure which fields plugins can update


