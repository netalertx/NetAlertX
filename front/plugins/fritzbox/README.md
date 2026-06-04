## Overview

The Fritz!Box plugin queries connected devices from a Fritz!Box router using the **TR-064** protocol (Technical Report 064), a standardized interface for managing DSL routers and home network devices. This plugin discovers all network-connected devices and reports their MAC addresses, IP addresses, hostnames, and connection types to NetAlertX.

TR-064 is a UPnP-based protocol that provides programmatic access to Fritz!Box configuration and status information. Unlike web scraping, it offers a stable, documented API that works across Fritz!Box models.

### Features

- **Device Discovery**: Automatically detects all connected devices (WiFi 2.4GHz, WiFi 5GHz, Ethernet)
- **Real-time Status**: Reports active connection status for each device
- **Guest WiFi Monitoring**: Optional synthetic Access Point device to track guest network status
- **Flexible Filtering**: Choose to report only active devices or include disconnected devices in Fritz!Box memory
- **Secure Connection**: Supports both HTTP and HTTPS with configurable SSL verification

> [!TIP]
> TR-064 is typically enabled by default on Fritz!Box routers. If you encounter connection issues, check that it hasn't been disabled in your Fritz!Box settings under **Home Network > Network > Network Settings > Allow access for applications**.

### Quick Setup Guide

To set up the plugin correctly:

1. **Enable TR-064 on Fritz!Box** (usually already enabled):
   - Log in to your Fritz!Box web interface (typically `fritz.box` or `192.168.178.1`)
   - Navigate to: **Home Network > Network > Network Settings**
   - Ensure **"Allow access for applications"** is checked
   - Note: Some models show this as **"Allow remote access"** - enable both HTTP and HTTPS

2. **Configure Plugin in NetAlertX**:
   - Head to **Settings** > **Fritz!Box Plugin**
   - Set the required settings (see below)
   - Choose run mode: **schedule** (recommended, runs every 5 minutes)

#### Required Settings

- **Fritz!Box Host** (`FRITZBOX_HOST`): Hostname or IP address of your Fritz!Box
  - Default: `fritz.box`
  - Alternative: `192.168.178.1` (or your Fritz!Box's IP)

- **TR-064 Port** (`FRITZBOX_PORT`): Port for TR-064 protocol
  - Default: `49443` (HTTPS). Use `49000` if HTTPS is disabled

- **Username** (`FRITZBOX_USER`): Fritz!Box username
  - Can be empty for some models when accessing from local network
  - For newer models, use an admin username

- **Password** (`FRITZBOX_PASS`): Fritz!Box password
  - Required: Your Fritz!Box admin password

#### Optional Settings

- **Use HTTPS** (`FRITZBOX_USE_TLS`): Enable secure HTTPS connection (default: `true`)
  - Recommended for security
  - Requires port `49443` instead of `49000`

- **Report Guest WiFi** (`FRITZBOX_REPORT_GUEST`): Create Access Point device for guest WiFi (default: `false`)
  - When enabled, adds a synthetic "Guest WiFi Network" device to your device list
  - Device appears only when guest WiFi is active
  - Useful for monitoring guest network status

- **Guest WiFi Service** (`FRITZBOX_GUEST_SERVICE`): Which WLANConfiguration service is the guest network (default: `3`)
  - Fritz!Box typically uses `1` for 2.4GHz, `2` for 5GHz, `3` for guest WiFi
  - Only relevant when **Report Guest WiFi** is enabled
  - Change this if your Fritz!Box uses a non-standard configuration

- **Active Devices Only** (`FRITZBOX_ACTIVE_ONLY`): Report only connected devices (default: `true`)
  - When enabled, only currently connected devices appear
  - When disabled, includes all devices stored in Fritz!Box memory (even if disconnected)

### Usage

1. Head to **Settings** > **Fritz!Box** to configure the plugin
2. Set **When to run** to **schedule** (recommended) or **once** for manual testing
3. The plugin will run every 5 minutes by default (configurable via **Schedule** setting)
4. View discovered devices in the **Devices** page
5. Check logs at `/tmp/log/plugins/script.FRITZBOX.log` for troubleshooting

### Device Information Reported

The plugin reports the following information for each device:

| Field | Description | Mapped To |
|-------|-------------|-----------|
| **MAC Address** | Device hardware address (normalized format) | `devMac` |
| **IP Address** | Current IPv4 address | `devLastIP` |
| **Hostname** | Device name from Fritz!Box | `devName` |
| **Connection Status** | "Active" or "Inactive" | Plugin table only (not mapped to device fields) |
| **Interface Type** | WiFi / LAN / Guest Network | `devType` |

### Guest WiFi Feature

When **Report Guest WiFi** is enabled and guest WiFi is active on your Fritz!Box:

- A synthetic device named **"Guest WiFi Network"** appears in your device list
- Device Type: **Access Point**
- MAC Address: Locally-administered synthetic MAC derived from Fritz!Box MAC (e.g., `02:a1:b2:c3:d4:e5`)
- Status: Only appears when guest WiFi is enabled

This allows you to:
- Monitor when guest WiFi is active
- Set up notifications when guest network is enabled/disabled
- Track guest network status alongside other network devices

> [!NOTE]
> The guest WiFi device is synthetic (not a real physical device). It's created by the plugin to represent the guest network state.

### Troubleshooting

#### Connection Refused / Timeout Errors

**Symptoms**: Plugin logs show "Failed to connect to Fritz!Box" or timeout errors

**Solutions**:
1. Verify Fritz!Box is reachable:
   ```bash
   ping fritz.box
   # or
   ping 192.168.178.1
   ```

2. Check TR-064 is enabled:
   - Fritz!Box web interface > **Home Network > Network > Network Settings**
   - Enable **"Allow access for applications"**

3. Verify correct port:
   - HTTP: Port `49000`
   - HTTPS: Port `49443`
   - Match **Use HTTPS** setting with port

4. Check firewall rules (if NetAlertX runs in Docker):
   - Ensure container can reach Fritz!Box network
   - Use host IP instead of `fritz.box` if DNS resolution fails

#### Authentication Failed

**Symptoms**: "Authentication error" or "Invalid credentials"

**Solutions**:
1. Verify password is correct
2. Try leaving **Username** empty (some models allow this from local network)
3. Create a dedicated user in Fritz!Box:
   - **System > Fritz!Box Users > Add User**
   - Grant network access permissions
4. For newer Fritz!OS versions, ensure user has **"Access from home network"** permission

#### No Devices Found

**Symptoms**: Plugin runs successfully but reports 0 devices

**Solutions**:
1. Check **Active Devices Only** setting:
   - If enabled, only connected devices appear
   - Disable to see all devices in Fritz!Box memory
2. Verify devices are actually connected to Fritz!Box
3. Check Fritz!Box web interface > **Home Network > Mesh** to see devices
4. Increase log level to `verbose` and check `/tmp/log/plugins/script.FRITZBOX.log`

#### Guest WiFi Not Detected

**Symptoms**: Guest WiFi enabled but no Access Point device appears

**Solutions**:
1. Ensure **Report Guest WiFi** is enabled
2. Guest WiFi must be **active** (not just configured)
3. Some Fritz!Box models don't expose guest network via TR-064
4. Check plugin logs for "Guest WiFi active" message

### Limitations

- **Active-only filtering**: When `FRITZBOX_ACTIVE_ONLY` is enabled, the plugin only reports currently connected devices. Disconnected devices stored in Fritz!Box memory are ignored.

- **Guest WiFi synthetic device**: The guest WiFi Access Point is a synthetic device created by the plugin. Its MAC address is derived from the Fritz!Box MAC and doesn't represent a physical device.

- **Model differences**: Some Fritz!Box models may not expose all TR-064 services (e.g., guest WiFi detection). The plugin degrades gracefully if services are unavailable.

- **IPv6 support**: Currently reports IPv4 addresses only. IPv6 support may be added in future versions.

- **Device type detection**: Interface type (WiFi/LAN) is reported, but detailed device categorization (smartphone, laptop, etc.) is handled by NetAlertX's device type detection, not this plugin.

### Technical Details

**Protocol**: TR-064 (Technical Report 064) - UPnP-based device management protocol

**Library**: [fritzconnection](https://github.com/kbr/fritzconnection) >= 1.15.1

**Services Used**:
- `FritzHosts`: Device discovery and information
- `WLANConfiguration`: Guest WiFi status detection
- `DeviceInfo`: Fritz!Box MAC address retrieval

**Execution Schedule**: Default every 5 minutes (configurable via cron syntax)

**Timeout**: 60 seconds (configurable via `RUN_TIMEOUT`)

### Notes

- **Performance**: TR-064 queries typically complete in under 2 seconds, even with many devices
- **Security**: Passwords are stored in NetAlertX's configuration database and not logged
- **Compatibility**: Tested with Fritz!Box models running Fritz!OS 7.x and 8.x
- **Dependencies**: Requires `fritzconnection` Python library (automatically installed via requirements.txt)

### Version

- **Version**: 1.0.0
- **Author**: [@sebingel](https://github.com/sebingel)
- **Release Date**: April 2026

### Support

For issues, questions, or feature requests:
- NetAlertX GitHub: [https://github.com/netalertx/NetAlertX](https://github.com/netalertx/NetAlertX)
- Fritz!Box TR-064 Documentation: [https://avm.de/service/schnittstellen/](https://avm.de/service/schnittstellen/)
