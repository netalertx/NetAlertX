# Troubleshooting Common Issues

> [!TIP]
> Before troubleshooting, ensure you have set the correct [Debugging and LOG_LEVEL](./DEBUG_TIPS.md).

---

## Docker Container Doesn't Start

Initial setup issues are often caused by **missing permissions** or **incorrectly mapped volumes**. Always double-check your `docker run` or `docker-compose.yml` against the [official setup guide](./DOCKER_INSTALLATION.md) before proceeding.

### Permissions

Make sure your [file permissions](./FILE_PERMISSIONS.md) are correctly set:

* If you encounter AJAX errors, cannot write to the database, or see an empty screen, check that permissions are correct and review the logs under `/tmp/log`.
* To fix permission issues with the database, update the owner and group of `app.db` as described in the [File Permissions guide](./FILE_PERMISSIONS.md).

### Container Restarts / Crashes

* Check the logs for details. Often, required settings are missing.
* For more detailed troubleshooting, see [Debug and Troubleshooting Tips](./DEBUG_TIPS.md).
* To observe errors directly, run the container in the foreground instead of `-d`:

```bash
docker run --rm -it <your_image>
```

---

## Docker Container Starts, But the Application Misbehaves

If the container starts but the app shows unexpected behavior, the cause is often **data corruption**, **incorrect configuration**, or **unexpected input data**.

### Continuous "Loading..." Screen

A misconfigured application may display a persistent `Loading...` dialog. This is usually caused by the backend failing to start.

**Steps to troubleshoot:**

1. Check **Maintenance → Logs** for exceptions.
2. If no exception is visible, check the Portainer logs.
3. Start the container in the foreground to observe exceptions.
4. Enable `trace` or `debug` logging for detailed output (see [Debug Tips](./DEBUG_TIPS.md)).
5. Verify that `GRAPHQL_PORT` is correctly configured.
6. Check browser logs (press `F12`):

   * **Console tab** → refresh the page
   * **Network tab** → refresh the page

If you are unsure how to resolve errors, provide screenshots or log excerpts in your issue report or Discord discussion.

---

### Common Configuration Issues

#### Incorrect `SCAN_SUBNETS`

If `SCAN_SUBNETS` is misconfigured, you may see only a few devices in your device list after a scan. See the [Subnets Documentation](./SUBNETS.md) for proper configuration.

#### Duplicate Devices and Notifications

* Devices are identified by their **MAC address**.
* If a device's MAC changes, it will be treated as a new device, triggering notifications.
* Prevent this by adjusting your device configuration for Android, iOS, or Windows. See the [Random MACs Guide](./RANDOM_MAC.md).

#### Unable to Resolve Host

* Ensure `SCAN_SUBNETS` uses the correct mask and `--interface`.
* Refer to the [Subnets Documentation](./SUBNETS.md) for detailed guidance.

#### Invalid JSON Errors

* Follow the steps in [Invalid JSON Errors Debug Help](./DEBUG_INVALID_JSON.md).

#### Sudo Execution Fails (e.g., on arpscan on Raspberry Pi 4)

Error:

```
sudo: unexpected child termination condition: 0
```

**Resolution**:

```bash
wget ftp.us.debian.org/debian/pool/main/libs/libseccomp/libseccomp2_2.5.3-2_armhf.deb
sudo dpkg -i libseccomp2_2.5.3-2_armhf.deb
```

> ⚠️ The link may break over time. Check [Debian Packages](https://packages.debian.org/sid/armhf/libseccomp2/download) for the latest version.

#### Only Router and Own Device Show Up

* Verify the subnet and interface in `SCAN_SUBNETS`.
* On devices with multiple Ethernet ports, you may need to change `eth0` to the correct interface.

#### Losing Settings or Devices After Update

* Ensure `/data/db` and `/data/config` are mapped to persistent storage.
* Without persistent volumes, these folders are recreated on every update.
* See [Docker Volumes Setup](./DOCKER_COMPOSE.md) for proper configuration.

#### Application Performance Issues

Slowness can be caused by:

* Incorrect settings (causing app restarts) → check `app.log`.
* Too many background processes → disable unnecessary scanners.
* Long scans → limit the number of scanned devices.
* Excessive disk operations or failing maintenance plugins.

> See [Performance Tips](./PERFORMANCE.md) for detailed optimization steps.


#### IP flipping

With `ARPSCAN` scans some devices might flip IP addresses after each scan triggering false notifications. This is because some devices respond to broadcast calls and thus different IPs after scans are logged.

See how to prevent IP flipping in the [ARPSCAN plugin guide](/front/plugins/arp_scan/README.md).

Alternatively adjust your [notification settings](./NOTIFICATIONS.md) to prevent false positives by filtering out events or devices.

#### Multiple NICs on Same Host Reporting Same IP

On systems with multiple NICs (like a Proxmox server), each NIC has its own MAC address. Sometimes NetAlertX can incorrectly assign the same IP to all NICs, causing false device mappings. This is due to the way ARP responses are handled by the OS and cannot be overridden directly in NetAlertX.

**Resolution (Linux-based systems, e.g., Proxmox):**

Run the following commands on the host to fix ARP behavior:

```bash
sudo sysctl -w net.ipv4.conf.all.arp_ignore=1
sudo sysctl -w net.ipv4.conf.all.arp_announce=2
```

This ensures each NIC responds correctly to ARP requests and prevents NetAlertX from misassigning IPs.

> For setups with multiple interfaces on the same switch, consider [workflows](./WORKFLOWS.md), [device exclusions](./NOTIFICATIONS.md), or [dummy devices](./DEVICE_MANAGEMENT.md) as additional workarounds.
> See [Feature Requests](https://github.com/netalertx/netalertx/issues) for reporting edge cases.


