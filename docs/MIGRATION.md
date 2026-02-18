# Migration

When upgrading from older versions of NetAlertX (or PiAlert by jokob-sk), follow the migration steps below to ensure your data and configuration are properly transferred.

> [!TIP]
> It's always important to have a [backup strategy](./BACKUPS.md) in place.

## Migration scenarios

- You are running PiAlert (by jokob-sk)
  → [Read the 1.1 Migration from PiAlert to NetAlertX `v25.5.24`](#11-migration-from-pialert-to-netalertx-v25524)

- You are running NetAlertX (by jokob-sk) `25.5.24` or older
  → [Read the 1.2 Migration from NetAlertX `v25.5.24`](#12-migration-from-netalertx-v25524)

- You are running NetAlertX (by jokob-sk) (`v25.6.7` to `v25.10.1`)
  → [Read the 1.3 Migration from NetAlertX `v25.10.1`](#13-migration-from-netalertx-v25101)

- You are running NetAlertX (by jokob-sk) (`v25.11.29`)
  → [Read the 1.4 Migration from NetAlertX `v25.11.29`](#14-migration-from-netalertx-v251129)


### 1.0 Manual Migration

You can migrate data manually, for example by exporting and importing devices using the [CSV import](./DEVICES_BULK_EDITING.md) method.


### 1.1 Migration from PiAlert to NetAlertX `v25.5.24`

#### STEPS:

The application will automatically migrate the database, configuration, and all device information.
A banner message will appear at the top of the web UI reminding you to update your Docker mount points.

1. Stop the container
2. [Back up your setup](./BACKUPS.md)
3. Update the Docker file mount locations in your `docker-compose.yml` or docker run command (See below **New Docker mount locations**).
4. Rename the DB and conf files to `app.db` and `app.conf` and place them in the appropriate location.
5. Start the container


> [!TIP]
> If you have trouble accessing past backups, config or database files you can copy them into the newly mapped directories, for example by running this command in the container:  `cp -r /data/config /home/pi/pialert/config/old_backup_files`. This should create a folder in the `config` directory called `old_backup_files` containing all the files in that location. Another approach is to map the old location and the new one at the same time to copy things over.

#### New Docker mount locations

The internal application path in the container has changed from `/home/pi/pialert` to `/app`. Update your volume mounts as follows:

 | Old mount point | New mount point |
 |----------------------|---------------|
 | `/home/pi/pialert/config` | `/data/config` |
 | `/home/pi/pialert/db` | `/data/db` |


 If you were mounting files directly, please note the file names have changed:

 | Old file name | New file name |
 |----------------------|---------------|
 | `pialert.conf` | `app.conf` |
 | `pialert.db` | `app.db` |


> [!NOTE]
> The application automatically creates symlinks from the old database and config locations to the new ones, so data loss should not occur. Read the [backup strategies](./BACKUPS.md) guide to backup your setup.


#### Examples

Examples of docker files with the new mount points.

##### Example 1: Mapping folders

###### Old docker-compose.yml

```yaml
services:
  pialert:
    container_name: pialert
    # use the below line if you want to test the latest dev image
    # image: "ghcr.io/jokob-sk/netalertx-dev:latest"
    image: "jokobsk/pialert:latest"
    network_mode: "host"
    restart: unless-stopped
    volumes:
      - /local_data_dir/config:/home/pi/pialert/config
      - /local_data_dir/db:/home/pi/pialert/db
      # (optional) useful for debugging if you have issues setting up the container
      - /local_data_dir/logs:/home/pi/pialert/front/log
    environment:
      - TZ=Europe/Berlin
      - PORT=20211
```

###### New docker-compose.yml

```yaml
services:
  netalertx:                                  # 🆕 This has changed
    container_name: netalertx                 # 🆕 This has changed
    image: "ghcr.io/jokob-sk/netalertx:25.5.24"         # 🆕 This has changed
    network_mode: "host"
    restart: unless-stopped
    volumes:
      - /local_data_dir/config:/data/config         # 🆕 This has changed
      - /local_data_dir/db:/data/db                 # 🆕 This has changed
      # (optional) useful for debugging if you have issues setting up the container
      - /local_data_dir/logs:/tmp/log        # 🆕 This has changed
    environment:
      - TZ=Europe/Berlin
      - PORT=20211
```


##### Example 2: Mapping files

> [!NOTE]
> The recommendation is to map folders as in Example 1, map files directly only when needed.

###### Old docker-compose.yml

```yaml
services:
  pialert:
    container_name: pialert
    # use the below line if you want to test the latest dev image
    # image: "ghcr.io/jokob-sk/netalertx-dev:latest"
    image: "jokobsk/pialert:latest"
    network_mode: "host"
    restart: unless-stopped
    volumes:
      - /local_data_dir/config/pialert.conf:/home/pi/pialert/config/pialert.conf
      - /local_data_dir/db/pialert.db:/home/pi/pialert/db/pialert.db
      # (optional) useful for debugging if you have issues setting up the container
      - /local_data_dir/logs:/home/pi/pialert/front/log
    environment:
      - TZ=Europe/Berlin
      - PORT=20211
```

###### New docker-compose.yml

```yaml
services:
  netalertx:                                  # 🆕 This has changed
    container_name: netalertx                 # 🆕 This has changed
    image: "ghcr.io/jokob-sk/netalertx:25.5.24"         # 🆕 This has changed
    network_mode: "host"
    restart: unless-stopped
    volumes:
      - /local_data_dir/config/app.conf:/data/config/app.conf # 🆕 This has changed
      - /local_data_dir/db/app.db:/data/db/app.db             # 🆕 This has changed
      # (optional) useful for debugging if you have issues setting up the container
      - /local_data_dir/logs:/tmp/log                  # 🆕 This has changed
    environment:
      - TZ=Europe/Berlin
      - PORT=20211
```


### 1.2 Migration from NetAlertX `v25.5.24`

Versions before `v25.10.1` require an intermediate migration through `v25.5.24` to ensure database compatibility. Skipping this step may cause compatibility issues due to database schema changes introduced after `v25.5.24`.

#### STEPS:

1. Stop the container
2. [Back up your setup](./BACKUPS.md)
3. Upgrade to `v25.5.24` by pinning the release version (See Examples below)
4. Start the container and verify everything works as expected.
5. Stop the container
6. Upgrade to `v25.10.1` by pinning the release version (See Examples below)
7. Start the container and verify everything works as expected.

#### Examples

Examples of docker files with the tagged version.

##### Example 1: Mapping folders

###### docker-compose.yml changes

```yaml
services:
  netalertx:
    container_name: netalertx
    image: "ghcr.io/jokob-sk/netalertx:25.5.24"         # 🆕 This is important
    network_mode: "host"
    restart: unless-stopped
    volumes:
      - /local_data_dir/config:/data/config
      - /local_data_dir/db:/data/db
      # (optional) useful for debugging if you have issues setting up the container
      - /local_data_dir/logs:/tmp/log
    environment:
      - TZ=Europe/Berlin
      - PORT=20211
```

```yaml
services:
  netalertx:
    container_name: netalertx
    image: "ghcr.io/jokob-sk/netalertx:25.10.1"         # 🆕 This is important
    network_mode: "host"
    restart: unless-stopped
    volumes:
      - /local_data_dir/config:/data/config
      - /local_data_dir/db:/data/db
      # (optional) useful for debugging if you have issues setting up the container
      - /local_data_dir/logs:/tmp/log
    environment:
      - TZ=Europe/Berlin
      - PORT=20211
```

### 1.3 Migration from NetAlertX `v25.10.1`

Starting from `v25.10.1`, the container uses a [more secure, read-only runtime environment](./SECURITY_FEATURES.md), which requires all writable paths (e.g., logs, API cache, temporary data) to be mounted as `tmpfs` or permanent writable volumes, with sufficient access [permissions](./FILE_PERMISSIONS.md). The data location has also hanged from `/app/db` and `/app/config` to `/data/db` and `/data/config`. See detailed steps below.

#### STEPS:

1. Stop the container
2. [Back up your setup](./BACKUPS.md)
3. Upgrade to `v25.10.1` by pinning the release version (See the example below)

```yaml
services:
  netalertx:
    container_name: netalertx
    image: "ghcr.io/jokob-sk/netalertx:25.10.1"         # 🆕 This is important
    network_mode: "host"
    restart: unless-stopped
    volumes:
      - /local_data_dir/config:/app/config
      - /local_data_dir/db:/app/db
      # (optional) useful for debugging if you have issues setting up the container
      - /local_data_dir/logs:/tmp/log
    environment:
      - TZ=Europe/Berlin
      - PORT=20211
```

4. Start the container and verify everything works as expected.
5. Stop the container.
6. Update the `docker-compose.yml` as per example below.

```yaml
services:
  netalertx:
    container_name: netalertx
    image: "ghcr.io/jokob-sk/netalertx:25.11.29"  # 🆕 This has changed
    network_mode: "host"
    cap_drop:                # 🆕 New line
      - ALL                  # 🆕 New line
    cap_add:                 # 🆕 New line
      - NET_RAW              # 🆕 New line
      - NET_ADMIN            # 🆕 New line
      - NET_BIND_SERVICE     # 🆕 New line
    restart: unless-stopped
    volumes:
      - /local_data_dir:/data  # 🆕 This folder contains your /db and /config directories and the parent changed from /app to /data
      # Ensuring the timezone is the same as on the server - make sure also the TIMEZONE setting is configured
      - /etc/localtime:/etc/localtime:ro    # 🆕 New line
    environment:
      - PORT=20211
    # 🆕 New "tmpfs" section START 🔽
    tmpfs:
      # All writable runtime state resides under /tmp; comment out to persist logs between restarts
      - "/tmp:uid=20211,gid=20211,mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"
    # 🆕 New "tmpfs" section END  🔼
```
7. Perform a one-off migration to the latest `netalertx` image and `20211` user.

> [!NOTE]
> The examples below assumes your `/config` and `/db` folders are stored in `local_data_dir`.
> Replace this path with your actual configuration directory. `netalertx` is the container name, which might differ from your setup.

**Automated approach**:

Run the container with the `--user "0"` parameter. Please note, some systems will require the manual approach below.

```sh
docker run -it --rm --name netalertx --user "0" \
  -v /local_data_dir/config:/app/config \
  -v /local_data_dir/db:/app/db \
  -v /local_data_dir:/data \
  --tmpfs /tmp:uid=20211,gid=20211,mode=1700 \
  ghcr.io/jokob-sk/netalertx:latest
```

Stop the container and run it as you would normally.

**Manual approach**:

Use the manual approach if the Automated approach fails. Execute the below commands:

```bash
sudo chown -R 20211:20211 /local_data_dir
sudo chmod -R a+rwx /local_data_dir
```

8. Start the container and verify everything works as expected.
9. Check the [Permissions -> Writable-paths](https://docs.netalertx.com/FILE_PERMISSIONS/#writable-paths) what directories to mount if you'd like to access the API or log files.


### 1.4 Migration from NetAlertX `v25.11.29`

As per user feedback, we’ve re-introduced the ability to control which user the application runs as via the `PUID` and `PGID` environment variables. This required additional changes to the container to safely handle permission adjustments at runtime.

#### STEPS:

1. Stop the container
2. [Back up your setup](./BACKUPS.md)
3. Stop the container
4. Update the `docker-compose.yml` as per example below.

```yaml
services:
  netalertx:
    container_name: netalertx
    image: "ghcr.io/netalertx/netalertx"
    network_mode: "host"
    cap_drop:
      - ALL
    cap_add:
      - NET_RAW
      - NET_ADMIN
      - NET_BIND_SERVICE
      - CHOWN                # 🆕 New line
      - SETUID               # 🆕 New line
      - SETGID               # 🆕 New line
    restart: unless-stopped
    volumes:
      - /local_data_dir:/data
      # Ensuring the timezone is the same as on the server - make sure also the TIMEZONE setting is configured
      - /etc/localtime:/etc/localtime:ro
    environment:
      - PORT=20211
      # - PUID=0    # New optional variable to run as root
      # - GUID=100  # New optional variable to run as root
    tmpfs:
      # All writable runtime state resides under /tmp; comment out to persist logs between restarts
      - "/tmp:uid=20211,gid=20211,mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"
```

5. If you use a custom `PUID` (e.g. `0`) and `GUID` (e.g. `100`) make sure you also update the `tmpfs` ownership, e.g. `/tmp:uid=0,gid=100...`
6. Start the container and verify everything works as expected.
7. If running a reverse proxy review the [Reverse proxy documentation](./REVERSE_PROXY.md) as a new `BACKEND_API_URL` setting was added.
