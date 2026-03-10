# Performance Optimization Guide

There are several ways to improve the application's performance. The application has been tested on a range of devices, from Raspberry Pi 4 units to NAS and NUC systems. If you are running the application on a lower-end device, fine-tuning the performance settings can significantly improve the user experience.

## Common Causes of Slowness

Performance issues are usually caused by:

* **Incorrect settings** – The app may restart unexpectedly. Check `app.log` under **Maintenance → Logs** for details.
* **Too many background processes** – Disable unnecessary scanners.
* **Long scan durations** – Limit the number of scanned devices.
* **Excessive disk operations** – Optimize scanning and logging settings.
* **Maintenance plugin failures** – If cleanup tasks fail, performance can degrade over time.

The application performs regular maintenance and database cleanup. If these tasks are failing, you will see slowdowns.

### Database and Log File Size

A large database or oversized log files can impact performance. You can check database and table sizes on the **Maintenance** page.

![DB size check](./img/PERFORMANCE/db_size_check.png)

> [!NOTE]
>
> * For **~100 devices**, the database should be around **50 MB**.
> * No table should exceed **10,000 rows** in a healthy system.
> * Actual values vary based on network activity and plugin settings.

---

## Maintenance Plugins

Two plugins help maintain the system’s performance:

### **1. Database Cleanup (DBCLNP)**

* Handles database maintenance and cleanup.
* See the [DB Cleanup Plugin Docs](/front/plugins/db_cleanup/README.md).
* Ensure it’s not failing by checking logs.
* Adjust the schedule (`DBCLNP_RUN_SCHD`) and timeout (`DBCLNP_RUN_TIMEOUT`) if necessary.

### **2. Maintenance (MAINT)**

* Cleans logs and performs general maintenance tasks.
* See the [Maintenance Plugin Docs](/front/plugins/maintenance/README.md).
* Verify proper operation via logs.
* Adjust the schedule (`MAINT_RUN_SCHD`) and timeout (`MAINT_RUN_TIMEOUT`) if needed.

---

## Database Performance Tuning

The application automatically maintains database performance as data accumulates. However, you can adjust settings to balance CPU usage, disk usage, and responsiveness.

### **WAL Size Tuning (Storage vs. CPU Tradeoff)**

The SQLite Write-Ahead Log (WAL) is a temporary file that grows during normal operation. On systems with constrained resources (NAS, Raspberry Pi), controlling WAL size is important.

**Setting:** **`PRAGMA_JOURNAL_SIZE_LIMIT`** (default: **50 MB**)

| Setting | Effect | Use Case |
|---------|--------|----------|
| **10–20 MB** | Smaller storage footprint; more frequent disk operations | NAS with SD card (storage priority) |
| **50 MB** (default) | Balanced; recommended for most setups | General use |
| **75–100 MB** | Smoother performance; larger WAL on disk | High-speed NAS or servers |

**Recommendation:** For NAS devices with SD cards, leave at default (50 MB) or increase slightly (75 MB). Avoid very low values (< 10 MB) as they cause frequent disk thrashing and CPU spikes.

### **Automatic Cleanup**

The DB cleanup plugin (`DBCLNP`) automatically optimizes query performance and trims old data:

- **Deletes old events** – Controlled by `DAYS_TO_KEEP_EVENTS` (default: 90 days)
- **Trims plugin history** – Keeps recent entries only (controlled by `PLUGINS_KEEP_HIST`)
- **Optimizes queries** – Updates database statistics so queries remain fast

**If cleanup fails**, performance degrades quickly. Check **Maintenance → Logs** for errors. If you see frequent failures, increase the timeout (`DBCLNP_RUN_TIMEOUT`).

---

## Scan Frequency and Coverage

Frequent scans increase resource usage, network traffic, and database read/write cycles.

### **Optimizations**

* **Increase scan intervals** (`<PLUGIN>_RUN_SCHD`) on busy networks or low-end hardware.
* **Increase timeouts** (`<PLUGIN>_RUN_TIMEOUT`) to avoid plugin failures.
* **Reduce subnet size** – e.g., use `/24` instead of `/16` to reduce scan load.

Some plugins also include options to limit which devices are scanned. If certain plugins consistently run long, consider narrowing their scope.

For example, the **ICMP plugin** allows scanning only IPs that match a specific regular expression.

---

## Storing Temporary Files in Memory

On devices with slower I/O, you can improve performance by storing temporary files (and optionally the database) in memory using `tmpfs`.

> [!WARNING]
> Storing the **database** in `tmpfs` is generally discouraged. Use this only if device data and historical records are not required to persist. If needed, you can pair this setup with the `SYNC` plugin to store important persistent data on another node. See the [Plugins docs](./PLUGINS.md) for details.

Using `tmpfs` reduces disk writes and speeds up I/O, but **all data stored in memory will be lost on restart**.

Below is an optimized `docker-compose.yml` snippet using non-persistent logs, API data, and DB:

```yaml
services:
  netalertx:
    container_name: netalertx
    # Use this line for the stable release
    image: "ghcr.io/netalertx/netalertx:latest"
    # Or use this line for the latest development build
    # image: "ghcr.io/netalertx/netalertx-dev:latest"
    network_mode: "host"
    restart: unless-stopped

    cap_drop:       # Drop all capabilities for enhanced security
      - ALL
    cap_add:        # Re-add necessary capabilities
      - NET_RAW
      - NET_ADMIN
      - NET_BIND_SERVICE
      - CHOWN
      - SETUID
      - SETGID

    volumes:
      - ${APP_FOLDER}/netalertx/config:/data/config
      - /etc/localtime:/etc/localtime:ro

    tmpfs:
      # All writable runtime state resides under /tmp; comment out to persist logs between restarts
      - "/tmp:uid=20211,gid=20211,mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"
      - "/data/db:uid=20211,gid=20211,mode=1700"  # ⚠ You will lose historical data on restart

    environment:
      - PORT=${PORT}
      - APP_CONF_OVERRIDE=${APP_CONF_OVERRIDE}
```
