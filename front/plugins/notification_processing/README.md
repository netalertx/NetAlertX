# Notifications User Guide

## Overview

This guide explains how the notification system works, including its dependencies, available notification types, and device-specific overrides.

## Notification Dependencies

The notification system relies on event data from devices and plugins. For notifications to function correctly:

- Devices must have alerts enabled in their settings.
- The notification processor uses the `NTFPRCS_INCLUDED_SECTIONS` setting to determine which types of notifications to send.
- Device-specific settings can override global notification rules.

## Notification Types

The following notification types are available based on the `NTFPRCS_INCLUDED_SECTIONS` setting:

### `new_devices`
- Notifies when a new device is detected on the network.
- Only sent if `new_devices` is enabled in `NTFPRCS_INCLUDED_SECTIONS`.

### `down_devices`
- Notifies when a device goes offline.
- The device must have **Alert Down** enabled in its settings.
- The notification is only sent if the device has not reconnected within the configured time window of `NTFPRCS_alert_down_time`.

### `down_reconnected`
- Notifies when a device that was previously reported as down reconnects.
- The device must have **Alert Down** enabled.

### `events`
- Notifies about specific events triggered by a device.
- The device must have **Alert Events** enabled in its settings.
- Includes events:
  - `Connected`, `Down Reconnected`, `Disconnected`,`IP Changed`
- you can exclude devices with a custom where condition via the `NTFPRCS_event_condition` setting

### `plugins`
- Notifies when an event is triggered by a plugin.
- These notifications depend on the plugin's configuration of the `watchedValue1-4` values and the `<plugin>_REPORT_ON` settings.

## Device-Specific Overrides

Certain notifications can be disabled per device:

### Alert Events Disabled
- If a device has **Alert Events** disabled, it will not receive notifications for general events (`events` section).
- This does not affect notifications for `down_devices`, `down_reconnected`, or `new_devices`.

### Alert Down Disabled
- If a device has **Alert Down** disabled, it will not receive notifications when it goes offline (`down_devices`) or reconnects (`down_reconnected`).

## Usage

- Review the **Settings** page to configure which notification types should be enabled.
- Ensure that device-specific alert settings align with your requirements.

For additional details, check the [Notifications Guide](/docs/NOTIFICATIONS.md).

