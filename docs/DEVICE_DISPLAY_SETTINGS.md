# Device Display Settings

This set of settings allows you to group Devices under different views. The Archived toggle allows you to exclude a Device from most listings and notifications.


![Display settings](./img/DEVICE_MANAGEMENT/DeviceDetails_DisplaySettings.png)


## Status Colors

| Icon      | Status                 | Image                                                                 | Description                                                                                   |
|-----------|------------------------|-----------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| <i class="fa-solid fa-plug"></i>     | Online (Green)         | ![Status color - online](./img/DEVICE_MANAGEMENT/device_management_status_online.png) | A device that is no longer marked as a "New Device".                                 |
| <i class="fa-solid fa-plug"></i>       | New (Green)            | ![Status color - new online](./img/DEVICE_MANAGEMENT/device_management_status_new_online.png) | A newly discovered device that is online and is still marked as a "New Device".  |
| <i class="fa-solid fa-plug-circle-exclamation"></i>   | Online (Orange)        | ![Status color - flapping online](./img/DEVICE_MANAGEMENT/device_management_status_flapping_online.png) | The device is online, but unstable and flapping (3 status changes in the last hour).     |
| <i class="fa-solid fa-xmark"></i>      | New (Grey)             | ![Status color - new offline](./img/DEVICE_MANAGEMENT/device_management_status_new_offline.png) | Same as "New (Green)" but the device is now offline.                            |
| <i class="fa-solid fa-box-archive"></i>  | New (Grey)             | ![Status color - new archived](./img/DEVICE_MANAGEMENT/device_management_status_archived_new.png) | Same as "New (Green)" but the device is now offline and archived.                            |
| <i class="fa-solid fa-xmark"></i>      | Offline (Grey)         | ![Status color - offline](./img/DEVICE_MANAGEMENT/device_management_status_offline.png) | A device that was not detected online in the last scan.                             |
| <i class="fa-solid fa-box-archive"></i> | Archived (Grey)         | ![Status color - archived](./img/DEVICE_MANAGEMENT/device_management_status_archived.png) | A device that was not detected online in the last scan.                             |
| <i class="fa-solid fa-moon"></i>       | Sleeping (Aqua)        | ![Status color - sleeping](./img/DEVICE_MANAGEMENT/device_management_status_sleeping.png) | A device with **Can Sleep** enabled that has gone offline within the `NTFPRCS_sleep_time` window. No down alert is fired while the device is in this state. See [Notifications](./NOTIFICATIONS.md#device-settings). |
| <i class="fa-solid fa-triangle-exclamation"></i>       | Down (Red)             | ![Status color - down](./img/DEVICE_MANAGEMENT/device_management_status_down.png)   | A device marked as "Alert Down" and offline for the duration set in `NTFPRCS_alert_down_time`.|


See also [Notification guide](./NOTIFICATIONS.md).