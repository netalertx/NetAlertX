# Backing Things Up

> [!NOTE]
> To back up 99% of your configuration, back up at least the `/data/config` folder.
> Database definitions can change between releases, so the safest method is to restore backups using the **same app version** they were taken from, then upgrade incrementally by following the [Migration documentation](./MIGRATION.md).

---

## What to Back Up

There are four key artifacts you can use to back up your NetAlertX configuration:

| File                     | Description                         | Limitations                                                                                                                                          |
| ------------------------ | ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/db/app.db`             | The application database            | Might be in an uncommitted state or corrupted                                                                                                        |
| `/config/app.conf`       | Configuration file                  | Can be overridden using the [`APP_CONF_OVERRIDE`](https://github.com/netalertx/NetAlertX/tree/main/dockerfiles#docker-environment-variables) variable |
| `/config/devices.csv`    | CSV file containing device data     | Does not include historical data                                                                                                                     |
| `/config/workflows.json` | JSON file containing your workflows | N/A                                                                                                                                                  |

---

## Where the Data Lives

Understanding where your data is stored helps you plan your backup strategy.

### Core Configuration

Stored in `/data/config/app.conf`.
This includes settings for:

* Notifications
* Scanning
* Scheduled maintenance
* UI preferences

(See [Settings System](./SETTINGS_SYSTEM.md) for details.)

### Device Data

Stored in `/data/config/devices_<timestamp>.csv` or `/data/config/devices.csv`, created by the [CSV Backup `CSVBCKP` Plugin](https://github.com/netalertx/NetAlertX/tree/main/front/plugins/csv_backup).
Contains:

* Device names, icons, and categories
* Network configuration
* Custom properties

### Historical Data

Stored in `/data/db/app.db` (see [Database Overview](./DATABASE.md)).
Contains:

* Plugin data and historical entries
* Event and notification history
* Device presence history

---

## Backup Strategies

The safest approach is to back up **both** the `/db` and `/config` folders regularly. Tools like [Kopia](https://github.com/kopia/kopia) make this simple and efficient.

If you can only keep a few files, prioritize:

1. The latest `devices_<timestamp>.csv` or `devices.csv`
2. `app.conf`
3. `workflows.json`

You can also download the `app.conf` and `devices.csv` files from the **Maintenance** section:

![Backup and Restore Section in Maintenance](./img/BACKUPS/Maintenance_Backup_Restore.png)

---

## Scenario 1: Full Backup and Restore

**Goal:** Full recovery of your configuration and data.

### 💾 What to Back Up

* `/data/db/app.db` (uncorrupted)
* `/data/config/app.conf`
* `/data/config/workflows.json`

### 📥 How to Restore

Map these files into your container as described in the [Setup documentation](./DOCKER_INSTALLATION.md).

---

## Scenario 2: Corrupted Database

**Goal:** Recover configuration and device data when the database is lost or corrupted.

### 💾 What to Back Up

* `/data/config/app.conf`
* `/data/config/workflows.json`
* `/data/config/devices_<timestamp>.csv` (rename to `devices.csv` during restore)

### 📥 How to Restore

1. Copy `app.conf` and `workflows.json` into `/data/config/`
2. Rename and place `devices_<timestamp>.csv` → `/data/config/devices.csv`
3. Restore via the **Maintenance** section under *Devices → Bulk Editing*

This recovers nearly all configuration, workflows, and device metadata.

---

## Docker-Based Backup and Restore

For users running NetAlertX via Docker, you can back up or restore directly from your host system — a convenient and scriptable option.

### Full Backup (File-Level)

1. **Stop the container:**

   ```bash
   docker stop netalertx
   ```

2. **Create a compressed archive** of your configuration and database volumes:

   ```bash
   docker run --rm -v local_path/config:/config -v local_path/db:/db alpine tar -cz /config /db > netalertx-backup.tar.gz
   ```

3. **Restart the container:**

   ```bash
   docker start netalertx
   ```

### Restore from Backup

1. **Stop the container:**

   ```bash
   docker stop netalertx
   ```

2. **Restore from your backup file:**

   ```bash
   docker run --rm -i -v local_path/config:/config -v local_path/db:/db alpine tar -C / -xz < netalertx-backup.tar.gz
   ```

3. **Restart the container:**

   ```bash
   docker start netalertx
   ```

> This approach uses a temporary, minimal `alpine` container to access Docker-managed volumes. The `tar` command creates or extracts an archive directly from your host’s filesystem, making it fast, clean, and reliable for both automation and manual recovery.

---

## Summary

* Back up `/data/config` for configuration and devices; `/data/db` for history
* Keep regular backups, especially before upgrades
* For Docker setups, use the lightweight `alpine`-based backup method for consistency and portability
