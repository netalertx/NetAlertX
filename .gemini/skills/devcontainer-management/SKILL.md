---
name: devcontainer-management
description: Guide for identifying, managing, and running commands within the NetAlertX development container. Use this when asked to run commands, testing, setup scripts, or troubleshoot container issues.
---

# Devcontainer Management

When starting a session or performing tasks requiring the runtime environment, you must identify and use the active development container.

## Finding the Container

Run `docker ps` to list running containers. Look for an image name containing `vsc-netalertx` or similar.

```bash
docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}" | grep netalertx
```

- **If no container is found:** Inform the user. You cannot run integration tests or backend logic without it.
- **If multiple containers are found:** Ask the user to clarify which one to use (e.g., provide the Container ID).

## Running Commands in the Container

Prefix commands with `docker exec <CONTAINER_ID>` to run them inside the environment. Use the scripts in `/services/` to control backend and other processes.

```bash
docker exec <CONTAINER_ID> bash /workspaces/NetAlertX/.devcontainer/scripts/setup.sh
```

*Note: This script wipes `/tmp` ramdisks, ensures `/data`, `/data/config`, `/data/db` exist, and restarts services (python server, cron, php-fpm, nginx) by symlinking and running `/entrypoint.sh` (`install/production-filesystem/entrypoint.d/`). By default it does **not** delete existing database or config content - `entrypoint.d/25-first-run-db.sh` and `20-first-run-config.sh` only wipe them when `ALWAYS_FRESH_INSTALL=true` is set in the environment (default: unset/`false`, so content is preserved).*

*`setup.sh` runs `/entrypoint.sh` inside a detached, backgrounded `while true` restart loop, not as a one-shot invocation - a devcontainer has no Docker restart-policy equivalent, so this outer loop reruns `entrypoint.sh` itself if it ever fully exits (a signal, a crash of the whole script). It is not a general per-service restart mechanism: in `NETALERTX_DEBUG=1` mode (the devcontainer default), `entrypoint.sh`'s own inner service monitor self-heals an unexpected `python3` crash specifically - if `nginx`, `php-fpm`, or `crond` dies, debug mode just logs a warning and leaves it dead, since neither loop restarts those. If the backend dies and stays dead, check `entrypoint.sh`'s monitor first; if any other service dies and stays dead, you do need to rerun `setup.sh` by hand.*

```
