#!/bin/bash
# NetAlertX Devcontainer Setup Script
#
# This script forcefully resets all runtime state for a single-user devcontainer.
# It is intentionally idempotent: every run wipes and recreates all relevant folders,
# symlinks, and files, so the environment is always fresh and predictable.
#
# - No conditional logic: everything is (re)created, overwritten, or reset unconditionally.
# - No security hardening: this is for disposable, local dev use only.
# - No checks for existing files, mounts, or processes—just do the work.
#
# If you add new runtime files or folders, add them to the creation/reset section below.
#
# Do not add if-then logic or error handling for missing/existing files. Simplicity is the goal.


SOURCE_DIR=${SOURCE_DIR:-/workspaces/NetAlertX}
PY_SITE_PACKAGES="${VIRTUAL_ENV:-/opt/venv}/lib/python3.14/site-packages"

LOG_FILES=(
  LOG_APP
  LOG_APP_FRONT
  LOG_STDERR
  LOG_EXECUTION_QUEUE
  LOG_APP_PHP_ERRORS
  LOG_IP_CHANGES
  LOG_CRON
  LOG_REPORT_OUTPUT_TXT
  LOG_REPORT_OUTPUT_HTML
  LOG_REPORT_OUTPUT_JSON
  LOG_DB_IS_LOCKED
  LOG_NGINX_ERROR
)
sudo chmod 666 /var/run/docker.sock 2>/dev/null || true
sudo chown "$(id -u)":"$(id -g)" /workspaces
sudo chmod 755 /workspaces

killall php-fpm83 nginx crond python3 2>/dev/null || true

# Mount ramdisks for volatile data
sudo mount -t tmpfs -o size=100m,mode=0777 tmpfs /tmp/log 2>/dev/null || true
sudo mount -t tmpfs -o size=50m,mode=0777 tmpfs /tmp/api 2>/dev/null || true
sudo mount -t tmpfs -o size=50m,mode=0777 tmpfs /tmp/run 2>/dev/null || true
sudo mount -t tmpfs -o size=50m,mode=0777 tmpfs /tmp/nginx 2>/dev/null || true

sudo chmod 777 /tmp/log /tmp/api /tmp/run /tmp/nginx

# Create critical subdirectories immediately after tmpfs mount
sudo install -d -m 777 /tmp/run/tmp
sudo install -d -m 777 /tmp/log/plugins


sudo rm -rf /entrypoint.d
sudo ln -s "${SOURCE_DIR}/install/production-filesystem/entrypoint.d" /entrypoint.d

sudo rm -rf /services
sudo ln -s "${SOURCE_DIR}/install/production-filesystem/services" /services

sudo rm -rf "${NETALERTX_APP}"
sudo ln -s "${SOURCE_DIR}/" "${NETALERTX_APP}"

for dir in "${NETALERTX_DATA}" "${NETALERTX_CONFIG}" "${NETALERTX_DB}"; do
  sudo install -d -m 777 "${dir}"
done

for dir in \
  "${SYSTEM_SERVICES_RUN_LOG}" \
  "${SYSTEM_SERVICES_ACTIVE_CONFIG}" \
  "${NETALERTX_PLUGINS_LOG}" \
  "${SYSTEM_SERVICES_RUN_TMP}" \
  "/tmp/nginx/client_body" \
  "/tmp/nginx/proxy" \
  "/tmp/nginx/fastcgi" \
  "/tmp/nginx/uwsgi" \
  "/tmp/nginx/scgi"; do
  sudo install -d -m 777 "${dir}"
done


for var in "${LOG_FILES[@]}"; do
  path=${!var}
  dir=$(dirname "${path}")
  sudo install -d -m 777 "${dir}"
  touch "${path}"
done

printf '0\n' | sudo tee "${LOG_DB_IS_LOCKED}" >/dev/null
sudo chmod 777 "${LOG_DB_IS_LOCKED}"

sudo pkill -f python3 2>/dev/null || true

sudo chown -R "${NETALERTX_USER}:${NETALERTX_GROUP}" "${NETALERTX_APP}"
date +%s | sudo tee "${NETALERTX_FRONT}/buildtimestamp.txt" >/dev/null

sudo chmod 755 "${NETALERTX_APP}"

sudo chmod +x /entrypoint.sh

# entrypoint.sh kills everything and exits if any one service dies (e.g. the
# backend crashing after exhausting its DB-lock retries - see server/db/retry.py).
# In production, Docker's restart policy brings the container back; a
# devcontainer has no equivalent, so this loop plays that role here -
# otherwise a crash leaves the whole dev environment dead until someone
# notices and reruns this script by hand.
#
# Redirected to LOG_STDERR rather than left on this docker-exec session's
# own stdout: once this synchronous `setup.sh` call returns, that inherited
# stdout has no reliable reader for anything the detached loop prints
# afterward - entrypoint.sh's own banner/monitor messages and (via
# start-backend.sh) the backend's actual crash traceback both land here now,
# interleaved in the order they actually happened.
setsid bash -c '
  while true; do
    bash /entrypoint.sh
    echo "[setup.sh] entrypoint.sh exited - restarting in 2s"
    sleep 2
  done
' >>"${LOG_STDERR:-/tmp/log/stderr.log}" 2>&1 &
sleep 1

echo "Development $(git rev-parse --short=8 HEAD)" | sudo tee "${NETALERTX_APP}/.VERSION" >/dev/null



