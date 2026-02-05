#!/usr/bin/env bash

# Copyright (c) 2021-2026 community-scripts ORG
# Author: jokob-sk
# License: MIT | https://github.com/community-scripts/ProxmoxVE/raw/main/LICENSE
# Source: https://github.com/netalertx/NetAlertX

# shellcheck disable=SC1091  # FUNCTIONS_FILE_PATH is provided by build.func

# Load all available functions (from core.func + tools.func)
# shellcheck disable=SC1090
source /dev/stdin <<< "$FUNCTIONS_FILE_PATH"

color
verb_ip6
catch_errors
setting_up_container
network_check
update_os

# ============================================================================
msg_info "Installing Dependencies"
$STD apt-get install -y \
    nginx \
    sqlite3 \
    dnsutils \
    net-tools \
    mtr \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    iproute2 \
    nmap \
    fping \
    zip \
    usbutils \
    traceroute \
    nbtscan \
    avahi-daemon \
    avahi-utils \
    build-essential \
    git \
    curl \
    wget \
    arp-scan \
    perl \
    libwww-perl \
    apt-utils \
    cron \
    sudo \
    ca-certificates \
    tini \
    snmp \
    libcap2-bin \
    gettext-base
msg_ok "Installed Dependencies"

msg_info "Setting up PHP 8.4"
PHP_VERSION="8.4" PHP_MODULE="cgi,fpm,sqlite3,curl,gd,mbstring,xml,intl,zip" setup_php
msg_ok "PHP 8.4 setup complete"

# ============================================================================
msg_info "Cloning NetAlertX Repository"
INSTALL_DIR="/app"
# Default repository if not specified
REPO_URL="${REPO_URL:-https://github.com/netalertx/NetAlertX.git}"
# Ensure directory is empty
rm -rf "$INSTALL_DIR"
git clone "$REPO_URL" "$INSTALL_DIR/" --quiet
cd "$INSTALL_DIR" || exit

# Remove symlink placeholders from the repository to ensure they become persistent directories
rm -rf api log db config

# Create a /data symlink as a fail-safe for application hardcoded paths
if [ ! -e /data ]; then
  ln -s /app /data
fi

# Create buildtimestamp if it doesn't exist
if [ ! -f "$INSTALL_DIR/front/buildtimestamp.txt" ]; then
  date +%s > "$INSTALL_DIR/front/buildtimestamp.txt"
fi
msg_ok "Cloned NetAlertX Repository"

# ============================================================================
msg_info "Installing Python Dependencies"
# Python venv creation
python3 -m venv /opt/netalertx-env
# shellcheck disable=SC1091
source /opt/netalertx-env/bin/activate
$STD python -m pip install --upgrade pip
if [ -f "${INSTALL_DIR:-/app}/install/proxmox/requirements.txt" ]; then
    $STD python -m pip install -r "${INSTALL_DIR:-/app}/install/proxmox/requirements.txt"
fi
deactivate
msg_ok "Installed Python Dependencies"

# ============================================================================
msg_info "Applying Security Capabilities"
# Dynamically find binary paths as they can vary between /usr/bin and /usr/sbin
BINARY_NMAP=$(command -v nmap)
BINARY_ARPSCAN=$(command -v arp-scan)
BINARY_NBTSCAN=$(command -v nbtscan)
BINARY_TRACEROUTE=$(command -v traceroute)
BINARY_PYTHON=$(readlink -f /opt/netalertx-env/bin/python)

[[ -n "$BINARY_NMAP" ]] && setcap cap_net_raw,cap_net_admin+eip "$BINARY_NMAP" || true
[[ -n "$BINARY_ARPSCAN" ]] && setcap cap_net_raw,cap_net_admin+eip "$BINARY_ARPSCAN" || true
[[ -n "$BINARY_NBTSCAN" ]] && setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip "$BINARY_NBTSCAN" || true
[[ -n "$BINARY_TRACEROUTE" ]] && setcap cap_net_raw,cap_net_admin+eip "$BINARY_TRACEROUTE" || true
[[ -n "$BINARY_PYTHON" ]] && setcap cap_net_raw,cap_net_admin+eip "$BINARY_PYTHON" || true
msg_ok "Security capabilities applied"
msg_ok "Installed Python Dependencies"

# ============================================================================
msg_info "Configuring NGINX"

# Set default port
PORT="${PORT:-20211}"

# Remove default NGINX site
if [ -L /etc/nginx/sites-enabled/default ]; then
  rm /etc/nginx/sites-enabled/default
elif [ -f /etc/nginx/sites-enabled/default ]; then
  mv /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default.bkp_netalertx
fi

# Create web directory and symbolic link
mkdir -p /var/www/html
ln -sfn "${INSTALL_DIR}/front" /var/www/html/netalertx

# Create symlinks in /tmp as well for double fail-safe (some PHP modules use /tmp/api)
mkdir -p /app/api /app/log
ln -sfn /app/api /tmp/api
ln -sfn /app/log /tmp/log

# Copy and configure NGINX config
mkdir -p "${INSTALL_DIR}/config"
cp "${INSTALL_DIR}/install/proxmox/netalertx.conf" "${INSTALL_DIR}/config/netalertx.conf"

# Update port in NGINX config
sed -i "s/listen 20211;/listen ${PORT};/g" "${INSTALL_DIR}/config/netalertx.conf"

# Create symbolic link to NGINX configuration
ln -sfn "${INSTALL_DIR}/config/netalertx.conf" /etc/nginx/conf.d/netalertx.conf

# Detect PHP-FPM socket and update NGINX config
PHP_FPM_SOCKET=$(find /run/php/ -name "php*-fpm.sock" | head -n 1)
if [[ -n "$PHP_FPM_SOCKET" ]]; then
  msg_info "Detected PHP-FPM socket: $PHP_FPM_SOCKET"
  sed -i "s|unix:/var/run/php/php-fpm.sock;|unix:$PHP_FPM_SOCKET;|g" /etc/nginx/conf.d/netalertx.conf
else
  msg_warn "Could not detect PHP-FPM socket path automatically"
fi

# Enable and start NGINX
systemctl enable nginx
systemctl restart nginx
msg_ok "Configured NGINX"

# ============================================================================
msg_info "Creating Directory Structure"

# Create persistent directories
mkdir -p "${INSTALL_DIR}/log/plugins" "${INSTALL_DIR}/api"

# Set permissions FIRST so www-data can create files (Fixes Turn 499)
chown -R www-data:www-data "${INSTALL_DIR}/log" "${INSTALL_DIR}/api"
chmod -R ug+rwX "${INSTALL_DIR}/log" "${INSTALL_DIR}/api"

# Create log and API files as www-data user
sudo -u www-data touch ${INSTALL_DIR}/log/{app.log,execution_queue.log,app_front.log,app.php_errors.log,stderr.log,stdout.log,db_is_locked.log}
sudo -u www-data touch ${INSTALL_DIR}/api/user_notifications.json

msg_ok "Created Directory Structure"

# Create missing __init__.py files for Python package recognition
touch "${INSTALL_DIR}/front/__init__.py"
touch "${INSTALL_DIR}/front/plugins/__init__.py"

# ============================================================================
msg_info "Setting up Database and Configuration"

# Copy starter database and config files
mkdir -p "${INSTALL_DIR}/config" "${INSTALL_DIR}/db"
cp -u "${INSTALL_DIR}/back/app.conf" "${INSTALL_DIR}/config/app.conf"
cp -u "${INSTALL_DIR}/back/app.db" "${INSTALL_DIR}/db/app.db"

# Sync timezone from system
LXC_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo "UTC")
if [[ -n "$LXC_TZ" ]]; then
  msg_info "Syncing Timezone: $LXC_TZ"
  sed -i "s|TIMEZONE.*=.*|TIMEZONE = '$LXC_TZ'|g" "${INSTALL_DIR}/config/app.conf"
  # Also update PHP's fallbacks if necessary (NetAlertX uses the one from app.conf mostly)
fi

# Set permissions
chgrp -R www-data "$INSTALL_DIR"
# NetAlertX needs write access to front/ for some features, and broad access to /app
chmod -R a+rwx "$INSTALL_DIR"
chown -R www-data:www-data "${INSTALL_DIR}/db/app.db"

# Configure sudoers for www-data (Needed for Init Checks & Tools)
msg_info "Configuring Sudoers"
cat > /etc/sudoers.d/netalertx <<EOF
www-data ALL=(ALL) NOPASSWD: /usr/bin/nmap, /usr/sbin/arp-scan, /usr/bin/nbtscan, /usr/bin/traceroute, /opt/netalertx-env/bin/python, /usr/bin/python3
EOF
chmod 440 /etc/sudoers.d/netalertx
msg_ok "Sudoers configured"

msg_ok "Database and Configuration Ready"

# ============================================================================
msg_info "Starting PHP-FPM"
systemctl enable php8.4-fpm
systemctl start php8.4-fpm
msg_ok "Started PHP-FPM"

# ============================================================================
msg_info "Configuring NetAlertX Service"

# Detect server IP
SERVER_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
if [ -z "${SERVER_IP}" ]; then
  SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
if [ -z "${SERVER_IP}" ]; then
  SERVER_IP="127.0.0.1"
fi

# Create startup script
cat > "$INSTALL_DIR/start.netalertx.sh" <<EOF
#!/usr/bin/env bash

# NetAlertX environment variables
export NETALERTX_CONFIG=/app/config
export NETALERTX_LOG=/app/log
export NETALERTX_DATA=/app
export NETALERTX_API=/app/api
export NETALERTX_TMP=/app
export PORT=${PORT}
export NETALERTX_TMP=/app
export PORT=${PORT}
export PYTHONPATH=/app

# Ensure package structure exists (Self-healing)
touch /app/front/__init__.py
touch /app/front/plugins/__init__.py

# Activate the virtual python environment
source /opt/netalertx-env/bin/activate

echo -e "--------------------------------------------------------------------------"
echo -e "Starting NetAlertX - navigate to http://${SERVER_IP}:${PORT}"
echo -e "--------------------------------------------------------------------------"

# Start the NetAlertX python script
cd /app
python server/
EOF

chmod +x "$INSTALL_DIR/start.netalertx.sh"

# Create systemd service
cat > /etc/systemd/system/netalertx.service <<EOF
[Unit]
Description=NetAlertX Service
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
ExecStart=/app/start.netalertx.sh
WorkingDirectory=/app
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# NetAlertX environment variables
Environment=NETALERTX_CONFIG=/app/config
Environment=NETALERTX_LOG=/app/log
Environment=NETALERTX_DATA=/app
Environment=NETALERTX_API=/app/api
Environment=NETALERTX_TMP=/app
Environment=PORT=${PORT}
Environment=PYTHONPATH=/app

# Create runtime directory in tmpfs for systemd-managed volatile files
RuntimeDirectory=netalertx
RuntimeDirectoryMode=0750

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable netalertx.service
systemctl start netalertx.service

# Verify service is running
if systemctl is-active --quiet netalertx.service; then
  msg_ok "NetAlertX Service Started Successfully"
else
  msg_error "NetAlertX Service Failed to Start"
  systemctl status netalertx.service --no-pager -l
  exit 1
fi

# ============================================================================
msg_info "Checking Hardware Vendor Database"
OUI_FILE="/usr/share/arp-scan/ieee-oui.txt"

if [ ! -f "$OUI_FILE" ]; then
  msg_info "Updating Hardware Vendor Database"
  if [ -f "${INSTALL_DIR}/back/update_vendors.sh" ]; then
    $STD "${INSTALL_DIR}/back/update_vendors.sh"
    msg_ok "Updated Hardware Vendor Database"
  else
    msg_warn "update_vendors.sh not found, skipping"
  fi
else
  msg_ok "Hardware Vendor Database Already Present"
fi

# ============================================================================
msg_info "Cleaning up"
motd_ssh
customize
cleanup_lxc
