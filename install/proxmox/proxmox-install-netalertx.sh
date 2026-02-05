#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting
set -u
# Consider failures in a pipeline
set -o pipefail
# Safe IFS
IFS=$' \t\n'

# 🛑 Important: This is only used for the bare-metal install 🛑
# Colors (guarded)
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  RESET='\e[0m'
  GREEN='\e[1;38;5;2m'
  RED='\e[31m'
else
  RESET=''; GREEN=''; RED=''
fi

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[UPDATING]                          ${RESET}Making sure the system is up to date"
printf "%b\n" "--------------------------------------------------------------------------"

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Running proxmox-install-netalertx.sh"
printf "%b\n" "--------------------------------------------------------------------------"

# Set environment variables
INSTALL_DIR=/app  # default installation directory

# DO NOT CHANGE ANYTHING BELOW THIS LINE!
INSTALLER_DIR="$INSTALL_DIR/install/proxmox"
CONF_FILE=app.conf
DB_FILE=app.db
NGINX_CONF_FILE=netalertx.conf
WEB_UI_DIR=/var/www/html/netalertx
NGINX_CONFIG=/etc/nginx/conf.d/$NGINX_CONF_FILE
OUI_FILE="/usr/share/arp-scan/ieee-oui.txt"
FILEDB=$INSTALL_DIR/db/$DB_FILE
# DO NOT CHANGE ANYTHING ABOVE THIS LINE!

# Check if script is run as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root."
    exit 1
fi

# Interactive confirmation: warn about overwriting/removing existing installation and NGINX config
if [ -z "${NETALERTX_ASSUME_YES:-}" ] && [ -z "${ASSUME_YES:-}" ] && [ -z "${NETALERTX_FORCE:-}" ]; then
    printf "%b\n" "------------------------------------------------------------------------"
    printf "%b\n" "${RED}[WARNING]              ${RESET}This script should be run on a fresh server"
    printf "%b\n" "${RED}[WARNING]              ${RESET}This script will install NetAlertX and will:"
    printf "%b\n" "${RED}[WARNING]              ${RESET}• Update OS with apt-get update/upgrade"
    printf "%b\n" "${RED}[WARNING]              ${RESET}• Overwrite existing files under ${INSTALL_DIR}  "
    printf "%b\n" "${RED}[WARNING]              ${RESET}• Wipe any existing database"
    printf "%b\n" "${RED}[WARNING]              ${RESET}• Wipe/Set up NGINX configuration under /etc/nginx"
    printf "%b\n" "${RED}[WARNING]              ${RESET}• Set up systemd services."
    read -r -p "Proceed with installation? [y/N]: " _reply
    case "${_reply}" in
        y|Y|yes|YES) ;;
        *) echo "Aborting by user choice."; exit 1;;
    esac
else
     printf "%b\n" "--------------------------------------------------------------------------"
     printf "%b\n" "${GREEN}[INSTALLING]       ${RESET}Non-interactive mode detected; proceeding without confirmation."
     printf "%b\n" "--------------------------------------------------------------------------"
fi

# Getting up to date
apt-get update -y
apt-get upgrade -y

# Prompt for HTTP port (default 20211) with countdown fallback
DEFAULT_PORT=20211
if [ -z "${NETALERTX_ASSUME_YES:-}" ] && [ -z "${ASSUME_YES:-}" ] && [ -z "${NETALERTX_FORCE:-}" ]; then
  printf "%b\n" "--------------------------------------------------------------------------"
  # Countdown-based prompt
  _entered_port=""
  for _sec in 10 9 8 7 6 5 4 3 2 1; do
    printf "\rEnter HTTP port for NetAlertX [${DEFAULT_PORT}] (auto-continue in %2ds): " "${_sec}"
    if read -t 1 -r _entered_port; then
      break
    fi
  done
  printf "\n"
  if [ -z "${_entered_port}" ]; then
    PORT="${DEFAULT_PORT}"
  elif printf '%s' "${_entered_port}" | grep -Eq '^[0-9]+$' && [ "${_entered_port}" -ge 1 ] && [ "${_entered_port}" -le 65535 ]; then
    PORT="${_entered_port}"
  else
    printf "%b\n" "${RED}[WARNING]              ${RESET}Invalid port. Falling back to ${DEFAULT_PORT}"
    PORT="${DEFAULT_PORT}"
  fi
else
  PORT="${PORT-}"; PORT="${PORT:-${DEFAULT_PORT}}"
fi
export PORT

# Detect primary server IP
SERVER_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
if [ -z "${SERVER_IP}" ]; then
  SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
if [ -z "${SERVER_IP}" ]; then
  SERVER_IP="127.0.0.1"
fi
export SERVER_IP

# Making sure the system is clean
if [ -d "$INSTALL_DIR" ]; then
  printf "%b\n" "Removing existing directory: $INSTALL_DIR"
  rm -rf "$INSTALL_DIR"
fi

# 1. INSTALL SYSTEM DEPENDENCIES & ADD PHP REPOSITORY
printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Installing system dependencies"
printf "%b\n" "--------------------------------------------------------------------------"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
# software-properties-common is not available and not needed
apt-get install -y --no-install-recommends \
    ca-certificates lsb-release curl gnupg

# Detect OS
# Shell check doesn't recognize source command because it's not in the repo, it is in the system at runtime
# shellcheck disable=SC1091
. /etc/os-release
OS_ID="${ID:-}"
OS_VER="${VERSION_ID:-}"

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Detected OS: ${OS_ID} ${OS_VER}"
printf "%b\n" "--------------------------------------------------------------------------"

if
  [ "${OS_ID}" = "ubuntu" ] && printf '%s' "${OS_VER}" | grep -q '^24'; then
  # Ubuntu 24.x typically ships PHP 8.3; add ondrej/php PPA and set 8.4
  printf "%b\n" "--------------------------------------------------------------------------"
  printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Ubuntu 24 detected - enabling ondrej/php PPA for PHP 8.4"
  printf "%b\n" "--------------------------------------------------------------------------"
  apt-get install -y --no-install-recommends software-properties-common || true
  add-apt-repository ppa:ondrej/php -y
  apt update -y
elif
  [ "${OS_ID}" = "debian" ] && printf '%s' "${OS_VER}" | grep -q '^13'; then
  printf "%b\n" "--------------------------------------------------------------------------"
  printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Debian 13 detected - using built-in PHP 8.4"
  printf "%b\n" "--------------------------------------------------------------------------"
fi

apt-get install -y --no-install-recommends \
    tini snmp ca-certificates curl libwww-perl arp-scan perl apt-utils cron sudo \
    php8.4 php8.4-cgi php8.4-fpm php8.4-sqlite3 php8.4-curl sqlite3 dnsutils net-tools mtr \
    python3 python3-dev iproute2 nmap fping python3-pip zip usbutils traceroute nbtscan \
    avahi-daemon avahi-utils build-essential git gnupg2 lsb-release \
    debian-archive-keyring python3-venv

if
  [ "${OS_ID}" = "ubuntu" ] && printf '%s' "${OS_VER}" | grep -q '^24'; then  # Set PHP 8.4 as the default alternatives where applicable
  update-alternatives --set php /usr/bin/php8.4 || true
  systemctl enable php8.4-fpm || true
  systemctl restart php8.4-fpm || true
fi

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]              ${RESET}Setting up NGINX - Might take a minute!"
printf "%b\n" "--------------------------------------------------------------------------"

apt-get install -y nginx

# Enable and start nginx
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable nginx || true
    systemctl restart nginx || true
fi

# 3. CLONE OR UPDATE APPLICATION REPOSITORY
printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Cloning application repository and setup"
printf "%b\n" "--------------------------------------------------------------------------"

mkdir -p "$INSTALL_DIR"
git clone https://github.com/netalertx/NetAlertX.git "$INSTALL_DIR/"

if [ ! -f "$INSTALL_DIR/front/buildtimestamp.txt" ]; then
  date +%s > "$INSTALL_DIR/front/buildtimestamp.txt"
fi

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[FINISHED]                          ${RESET}NetAlertX Installation complete"
printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[CONFIGURATION]                       ${RESET}Configuring the web server"
printf "%b\n" "--------------------------------------------------------------------------"

# Stop any existing NetAlertX python server process (narrow pattern)
pkill -f "^python(3)?\s+.*${INSTALL_DIR}/server/?$" 2>/dev/null || true

# 4. SET UP PYTHON VIRTUAL ENVIRONMENT & DEPENDENCIES
printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Setting up Python environment"
printf "%b\n" "--------------------------------------------------------------------------"
python3 -m venv /opt/netalertx-env
# Shell check doesn't recognize source command because it's not in the repo, it is in the system at runtime
# shellcheck disable=SC1091
source /opt/netalertx-env/bin/activate
python -m pip install --upgrade pip
python -m pip install -r "${INSTALLER_DIR}/requirements.txt"

# Backup default NGINX site just in case
if [ -L /etc/nginx/sites-enabled/default ] ; then
  rm /etc/nginx/sites-enabled/default
elif [ -f /etc/nginx/sites-enabled/default ]; then
  mv /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default.bkp_netalertx
fi

# Clear existing directories and files
if [ -d "$WEB_UI_DIR" ]; then
   printf "%b\n" "--------------------------------------------------------------------------"
   printf "%b\n" "${GREEN}[CHECKING]                          ${RESET}Removing existing NetAlertX web-UI"
   printf "%b\n" "--------------------------------------------------------------------------"
   rm -R "$WEB_UI_DIR"
fi

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[CHECKING]                          ${RESET}Removing existing NetAlertX NGINX config"
printf "%b\n" "--------------------------------------------------------------------------"
rm "$NGINX_CONFIG" 2>/dev/null || true

# Create web directory if it doesn't exist
mkdir -p /var/www/html

# create symbolic link to the installer directory
ln -sfn "${INSTALL_DIR}/front" "$WEB_UI_DIR"

# Copy NGINX configuration to NetAlertX config directory
cp "${INSTALLER_DIR}/${NGINX_CONF_FILE}" "${INSTALL_DIR}/config/${NGINX_CONF_FILE}"

# Use selected port (may be default 20211)
if [ -n "${PORT-}" ]; then
   printf "%b\n" "--------------------------------------------------------------------------"
   printf "%b\n" "Setting webserver to port ($PORT)"
   printf "%b\n" "--------------------------------------------------------------------------"
   # Update the template to reflect the right port
   sed -i "s/listen 20211;/listen ${PORT};/g" "${INSTALL_DIR}/config/${NGINX_CONF_FILE}"
   # Warn if port is already in use
   if ss -ltn | awk '{print $4}' | grep -q ":${PORT}$"; then
     printf "%b\n" "--------------------------------------------------------------------------"
     printf "%b\n" "${RED}[WARNING]                         ${RESET}Port ${PORT} appears in use. NGINX may fail to bind."
     printf "%b\n" "--------------------------------------------------------------------------"
   fi
fi

# Create symbolic link to NGINX configuration coming with NetAlertX
ln -sfn "${INSTALL_DIR}/config/${NGINX_CONF_FILE}" "${NGINX_CONFIG}"

# Run the hardware vendors update at least once
printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[VENDORS UPDATE]                        ${RESET}Run the hardware vendors update"
printf "%b\n" "--------------------------------------------------------------------------"

# Check if ieee-oui.txt or ieee-iab.txt exist
if [ -f "$OUI_FILE" ]; then
   printf "%b\n" "--------------------------------------------------------------------------"
   printf "%b\n" "The file ieee-oui.txt exists. Skipping update_vendors.sh..."
   printf "%b\n" "--------------------------------------------------------------------------"
else
   printf "%b\n" "--------------------------------------------------------------------------"
   printf "%b\n" "The file ieee-oui.txt does not exist. Running update_vendors..."
   printf "%b\n" "--------------------------------------------------------------------------"

  # Run the update_vendors.sh script
  if [ -f "${INSTALL_DIR}/back/update_vendors.sh" ]; then
    "${INSTALL_DIR}/back/update_vendors.sh"
  else
     printf "%b\n" "--------------------------------------------------------------------------"
     printf "%b\n" "             update_vendors.sh script not found in $INSTALL_DIR."
     printf "%b\n" "--------------------------------------------------------------------------"
  fi
fi

# Create persistent log and API directories
printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Creating persistent log and API directories"
printf "%b\n" "--------------------------------------------------------------------------"

# Create directory structure
mkdir -p "${INSTALL_DIR}/log/plugins" "${INSTALL_DIR}/api"

# Create log and API files as www-data user to ensure correct ownership
sudo -u www-data touch ${INSTALL_DIR}/log/{app.log,execution_queue.log,app_front.log,app.php_errors.log,stderr.log,stdout.log,db_is_locked.log}
sudo -u www-data touch ${INSTALL_DIR}/api/user_notifications.json

# Set final permissions for all created files and directories
chown -R www-data:www-data "${INSTALL_DIR}/log" "${INSTALL_DIR}/api"
chmod -R ug+rwX "${INSTALL_DIR}/log" "${INSTALL_DIR}/api"

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Setting up DB and CONF files"
printf "%b\n" "--------------------------------------------------------------------------"

# Copy starter $DB_FILE and $CONF_FILE
mkdir -p "${INSTALL_DIR}/config" "${INSTALL_DIR}/db"
cp -u "${INSTALL_DIR}/back/${CONF_FILE}" "${INSTALL_DIR}/config/${CONF_FILE}"
cp -u "${INSTALL_DIR}/back/${DB_FILE}" "${FILEDB}"

printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[CONFIGURING]                          ${RESET}Setting File Permissions"
printf "%b\n" "--------------------------------------------------------------------------"
# Restrict wide permissions; allow owner/group access
chgrp -R www-data "$INSTALL_DIR"
chmod -R ug+rwX,o-rwx "$INSTALL_DIR"
chmod -R ug+rwX,o-rwx "$WEB_UI_DIR"
# chmod -R ug+rwX "$INSTALL_DIR/log" "$INSTALL_DIR/config"
chown -R www-data:www-data "$FILEDB" 2>/dev/null || true

# start PHP
printf "%b\n" "--------------------------------------------------------------------------"
printf "%b\n" "${GREEN}[STARTING]                          ${RESET}Starting PHP and NGINX"
printf "%b\n" "--------------------------------------------------------------------------"
/etc/init.d/php8.4-fpm start
nginx -t || {
  printf "%b\n" "--------------------------------------------------------------------------"
  printf "%b\n" "${RED}[ERROR]                         ${RESET}NGINX config test failed!"
  printf "%b\n" "--------------------------------------------------------------------------"; exit 1; }
/etc/init.d/nginx start

# Make a start script
cat > "$INSTALL_DIR/start.netalertx.sh" << EOF
#!/usr/bin/env bash

# NetAlertX environment variables
export NETALERTX_CONFIG=/app/config
export NETALERTX_LOG=/app/log
export NETALERTX_DATA=/app
export NETALERTX_API=/app/api
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

# Install and manage systemd service if available, otherwise fallback to direct start
if command -v systemctl >/dev/null 2>&1; then
  printf "%b\n" "--------------------------------------------------------------------------"
  printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Setting up systemd service"
  printf "%b\n" "--------------------------------------------------------------------------"

cat > /etc/systemd/system/netalertx.service << 'EOF'
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

# Reload systemd and enable/start service
systemctl daemon-reload
systemctl enable netalertx.service
systemctl start netalertx.service
systemctl restart nginx

  # Verify service is running
  if systemctl is-active --quiet netalertx.service; then
    printf "%b\n" "--------------------------------------------------------------------------"
    printf "%b\n" "${GREEN}[SUCCESS]                 ${RESET}NetAlertX service started successfully"
    printf "%b\n" "--------------------------------------------------------------------------"
  else
    printf "%b\n" "--------------------------------------------------------------------------"
    printf "%b\n" "${RED}[WARNING]                 ${RESET}NetAlertX service may not have started properly"
    printf "%b\n" "--------------------------------------------------------------------------"
    systemctl status netalertx.service --no-pager -l
  fi
else
  printf "%b\n" "--------------------------------------------------------------------------"
  printf "%b\n" "${GREEN}[INSTALLING]                          ${RESET}Starting NetAlertX (no systemd)"
  printf "%b\n" "--------------------------------------------------------------------------"
  "$INSTALL_DIR/start.netalertx.sh" &
fi

echo -e "--------------------------------------------------------------------------"
echo -e "${GREEN}[Service]     🚀 Starting app - navigate to http://${SERVER_IP}:${PORT}"
echo -e "--------------------------------------------------------------------------"
