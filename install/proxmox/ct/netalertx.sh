#!/usr/bin/env bash

# Copyright (c) 2021-2026 community-scripts ORG
# Author: JVKeller

# License: GPL 3.0 | NetAlertX | https://github.com/netalertx/NetAlertX/blob/main/LICENSE.txt
# Source: https://github.com/netalertx/NetAlertX

# License: MIT | ProxmoxVE | https://github.com/community-scripts/ProxmoxVE/raw/main/LICENSE
# Source: https://github.com/ProxmoxVE

# Import main orchestrator
source <(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/misc/build.func)

# Application Configuration
APP="NetAlertX"
var_tags="network;monitoring;security"
var_cpu="2"
var_ram="2048"
var_disk="10"
# Container Type & OS
var_os="debian"
var_version="13"
var_unprivileged="1"  
# Standard initialization
header_info "$APP"
variables
color
catch_errors

# Support running from a mirror/fork
if [[ -n "${REPOS_URL}" ]]; then
  # Inject exports and override the installer URL surgically.
  # This pattern matches the exact curl -fsSL call in build.func
  export_header="export REPOS_URL=${REPOS_URL}; export REPO_URL=${REPO_URL}; export REPO_BRANCH=${REPO_BRANCH};"
  original_func=$(declare -f build_container)
  modified_func=$(echo "$original_func" | sed "s|bash -c \"\$(curl -fsSL [^\"]*)|bash -c \"${export_header} \$(curl -fsSL ${REPOS_URL}/install/proxmox/install/\${var_install}-install.sh)|g")
  eval "$modified_func"
fi

# Define local installer path for testing
LOCAL_INSTALLER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../install/${NSAPP:-netalertx}-install.sh"

# Override build_container to use local install script if available
if [[ -f "$LOCAL_INSTALLER" ]]; then
  msg_info "Using local installer from $LOCAL_INSTALLER"
  original_func=$(declare -f build_container)
  export_header="export REPOS_URL=${REPOS_URL}; export REPO_URL=${REPO_URL}; export REPO_BRANCH=${REPO_BRANCH};"
  replacement="${export_header} pct push \"\$CTID\" \"$LOCAL_INSTALLER\" /root/install.sh && lxc-attach -n \"\$CTID\" -- bash /root/install.sh"
  eval "$(echo "$original_func" | sed "s|lxc-attach.*install/\${var_install}.sh.*|$replacement|")"
fi

# Export variables to ensure they're passed to the installation script
export NSAPP APP var_os var_version var_cpu var_ram var_disk var_unprivileged PORT VERBOSE REPO_URL REPO_BRANCH REPOS_URL

# Support verbose logging
if [[ "${VERBOSE:-no}" == "yes" ]]; then
  set -x
  STD=""
fi

# Automatically detect bridge if vmbr0 is missing
if ! ip link show vmbr0 >/dev/null 2>&1 || [[ "$(cat /sys/class/net/vmbr0/bridge/bridge_id 2>/dev/null)" == "" ]]; then
  # Get List of Bridges using multiple methods
  # shellcheck disable=SC2207,SC2010  # Working pattern for bridge detection
  # We include vmbr0 in the search now to avoid errors if it exists but failed the strict check
  BRIDGES=($(ip -o link show type bridge | awk -F': ' '{print $2}') $(ls /sys/class/net 2>/dev/null | grep vmbr || true))
  # Remove duplicates
  # shellcheck disable=SC2207  # Working pattern for deduplication
  BRIDGES=($(echo "${BRIDGES[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))
  
  if [ ${#BRIDGES[@]} -eq 0 ]; then
    # Fallback to pvesh if available
    if command -v pvesh >/dev/null 2>&1; then
      # shellcheck disable=SC2207,SC2046  # Working pattern for pvesh output
      BRIDGES=($(pvesh get /nodes/$(hostname)/network --type bridge --output-format json | grep -oP '"iface":"\K[^"]+'))
    fi
  fi

  if [ ${#BRIDGES[@]} -eq 0 ]; then
    msg_error "No network bridges (vmbr) detected. Please create a Linux Bridge in Proxmox first."
    exit 1
  elif [ ${#BRIDGES[@]} -eq 1 ]; then
    export var_bridge="${BRIDGES[0]}"
    msg_info "Using detected bridge: ${var_bridge}"
  else
    # Multiple bridges found, let the user pick
    BRIDGE_MENU=()
    for b in "${BRIDGES[@]}"; do
      BRIDGE_MENU+=("$b" "Network Bridge")
    done
    # shellcheck disable=SC2155  # Standard whiptail pattern
    export var_bridge=$(whiptail --title "Select Network Bridge" --menu "vmbr0 not found. Please select a valid bridge:" 15 60 5 "${BRIDGE_MENU[@]}" 3>&1 1>&2 2>&3)
    if [ -z "$var_bridge" ]; then
      msg_error "No bridge selected. Aborting."
      exit 1
    fi
  fi
fi

function update_script() {
  header_info
  check_container_storage
  check_container_resources

  if [[ ! -d /app ]]; then
    msg_error "No ${APP} Installation Found!"
    exit 1
  fi

  msg_info "Stopping ${APP} Service"
  systemctl stop netalertx.service
  msg_ok "Stopped ${APP} Service"

  msg_info "Updating ${APP}"
  cd /app || exit 1
  # Get current branch (default to main if detection fails)
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
  
  # Ensure clean state before pulling from the detected branch
  git fetch origin "${BRANCH}" || exit 1
  git reset --hard "origin/${BRANCH}" || exit 1
  msg_ok "Updated ${APP} (Branch: ${BRANCH})"

  msg_info "Updating Python Dependencies"
  # shellcheck disable=SC1091  # venv activation script
  source /opt/netalertx-env/bin/activate
  # Suppress pip output unless verbose
  $STD pip install -r install/proxmox/requirements.txt || exit 1
  deactivate
  msg_ok "Updated Python Dependencies"

  msg_info "Applying System Optimizations"
  mkdir -p /etc/sysctl.d
  cat <<EOF > /etc/sysctl.d/99-arp-fix.conf
net.ipv4.conf.all.arp_ignore = 1
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.default.arp_ignore = 1
net.ipv4.conf.default.arp_announce = 2
EOF
  sysctl -p /etc/sysctl.d/99-arp-fix.conf 2>/dev/null || true
  msg_ok "System optimizations applied"

  msg_info "Starting ${APP} Service"
  systemctl start netalertx.service
  msg_ok "Started ${APP} Service"

  msg_ok "Update Complete"
  exit
}

# Start the container creation workflow
start

# Build the container with selected configuration
build_container

# Set container description/notes in Proxmox UI
description

# Display success message
msg_ok "Completed successfully!\n"

echo -e "${CREATING}${GN}${APP} setup has been successfully initialized!${CL}"
echo -e "${INFO}${YW} Access it using the following URL:${CL}"
echo -e "${TAB}${GATEWAY}${BGN}http://${IP}:${PORT:-20211}${CL}"
echo -e "${INFO}${YW} Service Management:${CL}"
echo -e "${TAB}systemctl status netalertx.service${CL}"
