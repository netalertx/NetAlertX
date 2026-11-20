---
name: netalertx-idempotent-setup
description: Reprovision and reset the devcontainer environment. Use this when asked to re-run startup, reprovision, setup devcontainer, fix permissions, or reset runtime state.
---

# Devcontainer Setup

The setup script forcefully resets all *runtime* state (services, tmpfs ramdisks, symlinks, log files) unconditionally on every run. Persistent DB/config content under `/data` is the one exception - it's preserved by default; see step 7 below.

## Command

```bash
/workspaces/NetAlertX/.devcontainer/scripts/setup.sh
```

## What It Does

1. Kills all services (php-fpm, nginx, crond, python3)
2. Mounts tmpfs ramdisks for `/tmp/log`, `/tmp/api`, `/tmp/run`, `/tmp/nginx`
3. Creates critical subdirectories
4. Links `/entrypoint.d` and `/app` symlinks
5. Creates `/data`, `/data/config`, `/data/db` directories
6. Creates all log files
7. Runs `/entrypoint.sh` to start services, inside a detached `while true` restart loop (not a one-shot call) - a devcontainer has no Docker restart-policy equivalent, so this loop self-heals a later service crash. By default this **preserves** existing DB/config content; `entrypoint.d/25-first-run-db.sh` and `20-first-run-config.sh` only wipe them when `ALWAYS_FRESH_INSTALL=true` is set in the environment. If the backend dies and stays dead, check `entrypoint.sh`'s own service monitor first (it self-heals an unexpected `python3` crash even in `NETALERTX_DEBUG=1` mode) before assuming `setup.sh` needs to be rerun by hand.
8. Writes version to `.VERSION`

## When to Use

- After modifying setup scripts
- After container rebuild
- When environment is in broken state
- To pick up a database/config reset done another way (setup.sh itself won't reset them - see step 7)

## Philosophy

Runtime state (services, tmpfs, symlinks, logs) has no conditional logic - everything is recreated unconditionally, every run. DB/config are the one deliberate exception, gated behind `ALWAYS_FRESH_INSTALL`. If something in runtime state doesn't work, run setup again.
