# NetAlertX and Docker Compose

> [!WARNING]
> ⚠️ **Important:** The docker-compose has recently changed. Carefully read the [Migration guide](https://docs.netalertx.com/MIGRATION/?h=migrat#12-migration-from-netalertx-v25524) for detailed instructions.

Great care is taken to ensure NetAlertX meets the needs of everyone while being flexible enough for anyone. This document outlines how you can configure your docker-compose. There are many settings, so we recommend using the Baseline Docker Compose as-is, or modifying it for your system.Good care is taken to ensure NetAlertX meets the needs of everyone while being flexible enough for anyone. This document outlines how you can configure your docker-compose. There are many settings, so we recommend using the Baseline Docker Compose as-is, or modifying it for your system.

> [!NOTE]
> The container needs to run in `network_mode:"host"` to access Layer 2 networking such as arp, nmap and others. Due to lack of support for this feature, Windows host is not a supported operating system.

## Baseline Docker Compose

There is one baseline for NetAlertX. That's the default security-enabled official distribution.

```yaml
services:
  netalertx:
  #use an environmental variable to set host networking mode if needed
    container_name: netalertx                       # The name when you docker contiainer ls
    image: ghcr.io/netalertx/netalertx:latest
    network_mode: ${NETALERTX_NETWORK_MODE:-host}   # Use host networking for ARP scanning and other services

    read_only: true                                 # Make the container filesystem read-only
    cap_drop:                                       # Drop all capabilities for enhanced security
      - ALL
    cap_add:                                        # Add only the necessary capabilities
      - NET_ADMIN                                   # Required for ARP scanning
      - NET_RAW                                     # Required for raw socket operations
      - NET_BIND_SERVICE                            # Required to bind to privileged ports (nbtscan)
      - CHOWN                                       # Required for root-entrypoint to chown /data + /tmp before dropping privileges
      - SETUID                                      # Required for root-entrypoint to switch to non-root user
      - SETGID                                      # Required for root-entrypoint to switch to non-root group
    sysctls:                                        # ARP flux mitigation (reduces duplicate/ambiguous ARP behavior on host networking)
      net.ipv4.conf.all.arp_ignore: 1
      net.ipv4.conf.all.arp_announce: 2

    volumes:
      - type: volume                                # Persistent Docker-managed named volume for config + database
        source: netalertx_data
        target: /data                               # `/data/config` and `/data/db` live inside this mount
        read_only: false

    # Example custom local folder called /home/user/netalertx_data
    # - type: bind
    #   source: /home/user/netalertx_data
    #   target: /data
    #   read_only: false
    # ... or use the alternative format
    # - /home/user/netalertx_data:/data:rw

      - type: bind                                  # Bind mount for timezone consistency
        source: /etc/localtime
        target: /etc/localtime
        read_only: true

      # Mount your DHCP server file into NetAlertX for a plugin to access
      # - path/on/host/to/dhcp.file:/resources/dhcp.file

    # tmpfs mount consolidates writable state for a read-only container and improves performance
    # uid/gid default to the service user (NETALERTX_UID/GID, default 20211)
    # mode=1700 grants rwx------ permissions to the runtime user only
    tmpfs:
      # Comment out to retain logs between container restarts - this has a server performance impact.
      - "/tmp:uid=${NETALERTX_UID:-20211},gid=${NETALERTX_GID:-20211},mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"

      # Retain logs - comment out tmpfs /tmp if you want to retain logs between container restarts
      # Please note if you remove the /tmp mount, you must create and maintain sub-folder mounts.
      # - /path/on/host/log:/tmp/log
      # - "/tmp/api:uid=${NETALERTX_UID:-20211},gid=${NETALERTX_GID:-20211},mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"
      # - "/tmp/nginx:uid=${NETALERTX_UID:-20211},gid=${NETALERTX_GID:-20211},mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"
      # - "/tmp/run:uid=${NETALERTX_UID:-20211},gid=${NETALERTX_GID:-20211},mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"

    environment:
      LISTEN_ADDR: ${LISTEN_ADDR:-0.0.0.0}                   # Listen for connections on all interfaces
      PORT: ${PORT:-20211}                                   # Application port
      GRAPHQL_PORT: ${GRAPHQL_PORT:-20212}                   # GraphQL API port (passed into APP_CONF_OVERRIDE at runtime)
  #    NETALERTX_DEBUG: ${NETALERTX_DEBUG:-0}                 # 0=kill all services and restart if any dies. 1 keeps running dead services.
  #    PUID: 20211                             # Runtime PUID override, set to 0 to run as root
  #    PGID: 20211                             # Runtime PGID override

    # Resource limits to prevent resource exhaustion
    mem_limit: 2048m            # Maximum memory usage
    mem_reservation: 1024m      # Soft memory limit
    cpu_shares: 512             # Relative CPU weight for CPU contention scenarios
    pids_limit: 512             # Limit the number of processes/threads to prevent fork bombs
    logging:
      options:
        max-size: "10m"         # Rotate log files after they reach 10MB
        max-file: "3"           # Keep a maximum of 3 log files

    # Always restart the container unless explicitly stopped
    restart: unless-stopped

volumes:                        # Persistent volume for configuration and database storage
  netalertx_data:
```

Run or re-run it:

```sh
docker compose up --force-recreate
```

> [!TIP]
> Runtime UID/GID: The image ships with a service user `netalertx` (UID/GID 20211) and a readonly lock owner also at 20211 for 004/005 immutability. If you override the runtime user (compose `user:` or `NETALERTX_UID/GID` vars), ensure your `/data` volume and tmpfs mounts use matching `uid/gid` so startup checks and writable paths succeed.

### Customize with Environmental Variables

You can override the default settings by passing environmental variables to the `docker compose up` command.

**Example using a single variable:**

This command runs NetAlertX on port 8080 instead of the default 20211.

```sh
PORT=8080 docker compose up
```

**Example using all available variables:**

This command demonstrates overriding all primary environmental variables: running with host networking, on port 20211, GraphQL on 20212, and listening on all IPs.

```sh
NETALERTX_NETWORK_MODE=host \
LISTEN_ADDR=0.0.0.0 \
PORT=20211 \
GRAPHQL_PORT=20212 \
NETALERTX_DEBUG=0 \
docker compose up
```

## `docker-compose.yaml` Modifications

### Modification 1: Use a Local Folder (Bind Mount)

By default, the baseline compose file uses a single named volume (netalertx_data) mounted at `/data`. This single-volume layout is preferred because NetAlertX manages both configuration and the database under `/data` (for example, `/data/config` and `/data/db`) via its web UI. Using one named volume simplifies permissions and portability: Docker manages the storage and NetAlertX manages the files inside `/data`.

A two-volume layout that mounts `/data/config` and `/data/db` separately (for example, `netalertx_config` and `netalertx_db`) is supported for backward compatibility and some advanced workflows, but it is an abnormal/legacy layout and not recommended for new deployments.

However, if you prefer to have direct, file-level access to your configuration for manual editing, a "bind mount" is a simple alternative. This tells Docker to use a specific folder from your computer (the "host") inside the container.

**How to make the change:**

1. Choose a location on your computer. For example, `/local_data_dir`.

2. Create the subfolders: `mkdir -p /local_data_dir/config` and `mkdir -p /local_data_dir/db`.

3. Edit your `docker-compose.yml` and find the `volumes:` section (the one *inside* the `netalertx:` service).

4. Comment out (add a `#` in front) or delete the `type: volume` blocks for `netalertx_config` and `netalertx_db`.

5. Add new lines pointing to your local folders.

**Before (Using Named Volumes - Preferred):**

```yaml
...
    volumes:
      - netalertx_config:/data/config:rw #short-form volume (no /path is a short volume)
      - netalertx_db:/data/db:rw
...
```

**After (Using a Local Folder / Bind Mount):**
Make sure to replace `/local_data_dir` with your actual path. The format is `<path_on_your_computer>:<path_inside_container>:<options>`.

```yaml
...
    volumes:
#      - netalertx_config:/data/config:rw
#      - netalertx_db:/data/db:rw
      - /local_data_dir/config:/data/config:rw
      - /local_data_dir/db:/data/db:rw
...
```

Now, any files created by NetAlertX in `/data/config` will appear in your `/local_data_dir/config` folder.

This same method works for mounting other things, like custom plugins or enterprise NGINX files, as shown in the commented-out examples in the baseline file.

### Example 2: External `.env` File for Paths

This method is useful for keeping your paths and other settings separate from your main compose file, making it more portable.

**`docker-compose.yml` changes:**

```yaml
...
services:
  netalertx:
    environment:
      - PORT=${PORT}
      - GRAPHQL_PORT=${GRAPHQL_PORT}

...
```

**`.env` file contents:**

```sh
PORT=20211
NETALERTX_NETWORK_MODE=host
LISTEN_ADDR=0.0.0.0
GRAPHQL_PORT=20212
```

Run with: `sudo docker-compose --env-file /path/to/.env up`

### Example 3: Docker Swarm

This is for deploying on a Docker Swarm cluster. The key differences from the baseline are the removal of `network_mode:` from the service, and the addition of `deploy:` and `networks:` blocks at both the service and top-level.

Here are the *only* changes you need to make to the baseline compose file to make it Swarm-compatible.

```yaml
services:
  netalertx:
    ...
    #    network_mode: ${NETALERTX_NETWORK_MODE:-host} # <-- DELETE THIS LINE
    ...

    # 2. ADD a 'networks:' block INSIDE the service to connect to the external host network.
    networks:
      - outside
    # 3. ADD a 'deploy:' block to manage the service as a swarm replica.
    deploy:
      mode: replicated
      replicas: 1
      restart_policy:
        condition: on-failure


# 4. ADD a new top-level 'networks:' block at the end of the file to define 'outside' as the external 'host' network.
networks:
  outside:
    external:
      name: "host"
```
