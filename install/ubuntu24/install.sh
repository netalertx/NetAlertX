#!/usr/bin/env bash

# 🛑 Important: This is only used for the bare-metal install 🛑

echo "---------------------------------------------------------"
echo "[INSTALL] Starting NetAlertX installation for Ubuntu"
echo "---------------------------------------------------------"
echo
echo "This script will install NetAlertX on your Ubuntu system."
echo "It will clone the repository, set up necessary files, and start the application."
echo "Please ensure you have a stable internet connection."
echo "---------------------------------------------------------"

# DO NOT CHANGE ANYTHING BELOW THIS LINE!
INSTALL_DIR=/app
INSTALL_SYSTEM_NAME=ubuntu24
INSTALLER_DIR=${INSTALL_DIR}/install/$INSTALL_SYSTEM_NAME
REQUIREMENTS_FILE=${INSTALL_DIR}/requirements.txt
CONF_FILE=app.conf
DB_FILE=app.db
NGINX_CONF_FILE=netalertx.conf
WEB_UI_DIR=/var/www/html/netalertx
NGINX_CONFIG_FILE=/etc/nginx/conf.d/$NGINX_CONF_FILE
OUI_FILE="/usr/share/arp-scan/ieee-oui.txt" # Define the path to ieee-oui.txt and ieee-iab.txt
FILEDB=${INSTALL_DIR}/db/${DB_FILE}
PHPVERSION="8.3"
VENV_DIR="/opt/netalertx-python"
GITHUB_REPO="https://github.com/jokob-sk/NetAlertX"
SYSTEMD_UNIT_FILE="/etc/systemd/system/netalertx.service"
SYSTEMD_UNIT_DEFAULTS="/etc/default/netalertx"
ALWAYS_FRESH_INSTALL=false  # Set to true to always reset /config and /db on each install
# DO NOT CHANGE ANYTHING ABOVE THIS LINE!


# Check if script is run as root
if [[ $EUID -ne 0 ]]; then
    echo "[INSTALL] This script must be run as root. Please use 'sudo'."
    exit 1
fi

# Install sudo if not present
echo "---------------------------------------------------------"
echo "[INSTALL] Starting NetAlertX installation for Ubuntu"
echo "---------------------------------------------------------"
echo

apt-get update -y
echo "[INSTALL] Making sure sudo is installed"
apt-get install sudo -y

echo "---------------------------------------------------------"
echo "[INSTALL] Installing dependencies"
echo "---------------------------------------------------------"
echo

# Install core dependencies
apt-get install -y --no-install-recommends \
  git \
  tini ca-certificates curl libwww-perl perl apt-utils cron build-essential \
  sqlite3 net-tools \
  python3 python3-venv python3-dev python3-psutil python3-pip

# Install plugin dependencies
apt-get install -y --no-install-recommends \
  dnsutils mtr arp-scan snmp iproute2 nmap fping zip usbutils traceroute nbtscan avahi-daemon avahi-utils

# nginx-core install nginx and nginx-common as dependencies
apt-get install -y --no-install-recommends \
  nginx-core \
  php${PHPVERSION} php${PHPVERSION}-sqlite3 php php-fpm php-cgi php${PHPVERSION}-fpm php-fpm php-sqlite3 php-curl php-cli
# make sure sqlite is activated
phpenmod -v ${PHPVERSION} sqlite3


echo "---------------------------------------------------------"
echo "[INSTALL] Stopping any NGINX web server and components"
echo "          (There may be errors stopping services, that's OK)"
echo "---------------------------------------------------------"
echo
# stopping nginx for setup
systemctl stop nginx
# stopping netalertx for setup
systemctl stop netalertx
# in case and older setup is running, kill it
pkill -f "python ${INSTALL_DIR}/server"
# stopping php fpm
systemctl stop php${PHPVERSION}-fpm


echo "---------------------------------------------------------"
echo "[INSTALL] Downloading NetAlertX repository"
echo "---------------------------------------------------------"
echo

# Clean the directory, ask for confirmation
if [ -d "${INSTALL_DIR}" ]; then
  echo "The installation directory exists. Removing it to ensure a clean install."
  echo "Are you sure you want to continue? This will delete all existing files in ${INSTALL_DIR}."
  echo "This will include ALL YOUR SETTINGS AND DATABASE! (if there are any)"
  echo
  echo "Type:"
  echo " - 'install' to continue and DELETE ALL!"
  echo " - 'update' to just update from GIT (keeps your db and settings)"
  echo " - 'start' to do nothing, leave install as-is (just run the start script)"
  if [ "$1" == "install" ] || [ "$1" == "update" ] || [ "$1" == "start" ]; then
    confirmation=$1
  else
    read -rp "Enter your choice: " confirmation
  fi
  if [ "$confirmation" == "install" ]; then
    # Ensure INSTALL_DIR is safe to wipe
    if [ -n "${INSTALL_DIR}" ] && [ "${INSTALL_DIR}" != "" ] && [ "${INSTALL_DIR}" != "/" ] && [ "${INSTALL_DIR}" != "." ] && [ -d "${INSTALL_DIR}" ]; then
      echo "Removing existing installation..."

      # Unmount only if mountpoints exist
      mountpoint -q "${INSTALL_DIR}/api" && umount "${INSTALL_DIR}/api" 2>/dev/null
      mountpoint -q "${INSTALL_DIR}/front" && umount "${INSTALL_DIR}/front" 2>/dev/null

      # Remove all contents safely
      rm -rf -- "${INSTALL_DIR:?}"/* "${INSTALL_DIR}"/.[!.]* "${INSTALL_DIR}"/..?* 2>/dev/null

      # Re-clone repository
      git clone "${GITHUB_REPO}" "${INSTALL_DIR}/"
    else
      echo "[INSTALL] INSTALL_DIR is not set, is root, or is invalid. Aborting for safety."
      exit 1
    fi
  elif [ "$confirmation" == "update" ]; then
    echo "[INSTALL] Updating the existing installation..."
    cd "${INSTALL_DIR}" || { echo "[INSTALL] Failed to change directory to ${INSTALL_DIR}"; exit 1; }
    # In case there were changes, stash them
    git stash -q
    git pull
    echo "[INSTALL] If there were any local changes, they have been >>STASHED<<"
    echo "[INSTALL] You can recover them with 'git stash pop' in ${INSTALL_DIR}"
    echo
  elif [ "$confirmation" == "start" ]; then
    echo "[INSTALL] Continuing without changes."
  else
    echo "[INSTALL] Installation aborted."
    exit 1
  fi
else
  git clone https://github.com/jokob-sk/NetAlertX "${INSTALL_DIR}/"
fi


echo "---------------------------------------------------------"
echo "[INSTALL] Setting up Python environment"
echo "---------------------------------------------------------"
echo
# update-alternatives --install /usr/bin/python python /usr/bin/python3 10
python3 -m venv "${VENV_DIR}"
# Shell check doesn't recognize source command because it's not in the repo, it is in the system at runtime
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
  echo "[INSTALL] requirements.txt not found at ${REQUIREMENTS_FILE}"
  exit 1
fi

pip3 install -r "${REQUIREMENTS_FILE}" || {
  echo "[INSTALL] Failed to install Python dependencies"
  exit 1
}


# We now should have all dependencies and files in place
# We can now configure the web server and start the application

cd "${INSTALLER_DIR}" || { echo "[INSTALL] Failed to change directory to ${INSTALLER_DIR}"; exit 1; }


# Check for buildtimestamp.txt existence, otherwise create it
if [ ! -f "${INSTALL_DIR}/front/buildtimestamp.txt" ]; then
  date +%s > "${INSTALL_DIR}/front/buildtimestamp.txt"
fi


# if custom variables not set we do not need to do anything
if [ -n "${TZ}" ]; then
  FILECONF=${INSTALL_DIR}/config/${CONF_FILE}
  if [ -f "$FILECONF" ]; then
    sed -i -e "s|Europe/Berlin|${TZ}|g" "${INSTALL_DIR}/config/${CONF_FILE}"
  else
    sed -i -e "s|Europe/Berlin|${TZ}|g" "${INSTALL_DIR}/back/${CONF_FILE}.bak"
  fi
fi


echo "---------------------------------------------------------"
echo "[INSTALL] Setting up the web server"
echo "---------------------------------------------------------"
echo


echo "[INSTALL] Updating the existing installation..."

# Remove default NGINX site if it is symlinked, or backup it otherwise
if [ -L /etc/nginx/sites-enabled/default ] ; then
  echo "[INSTALL] Disabling default NGINX site, removing sym-link in /etc/nginx/sites-enabled"
  rm /etc/nginx/sites-enabled/default
elif [ -f /etc/nginx/sites-enabled/default ]; then
  echo "[INSTALL] Disabling default NGINX site, moving config to /etc/nginx/sites-available"
  mv /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default.bkp_netalertx
fi

# Clear existing directories and files
if [ -d $WEB_UI_DIR ]; then
  echo "[INSTALL] Removing existing NetAlertX web-UI"
  rm -R $WEB_UI_DIR
fi

echo "[INSTALL] Removing existing NetAlertX NGINX config"
rm "${NGINX_CONFIG_FILE}" 2>/dev/null || true

# create symbolic link to the install directory
ln -s ${INSTALL_DIR}/front $WEB_UI_DIR
# create symbolic link to NGINX configuration coming with NetAlertX
ln -s "${INSTALLER_DIR}/$NGINX_CONF_FILE" ${NGINX_CONFIG_FILE}

# Use user-supplied port if set
if [ -n "${PORT}" ]; then
  echo "[INSTALL] Setting webserver to user-supplied port (${PORT})"
  sed -i 's/listen 20211/listen '"${PORT}"'/g' "${NGINX_CONFIG_FILE}"
else
  PORT=20211
fi

# Change web interface address if set
if [ -n "${LISTEN_ADDR}" ]; then
  echo "[INSTALL] Setting webserver to user-supplied address (${LISTEN_ADDR})"
  sed -i -e 's/listen /listen '"${LISTEN_ADDR}":'/g' "${NGINX_CONFIG_FILE}"
else
  LISTEN_ADDR="0.0.0.0"
fi

# Change php version
echo "[INSTALL] Setting PHP version to ${PHPVERSION}"
sed -i 's#unix:/run/php/php8.3-fpm.sock#unix:/run/php/php'"${PHPVERSION}"'-fpm.sock#ig' ${NGINX_CONFIG_FILE}

# Run the hardware vendors update at least once
echo "[INSTALL] Run the hardware vendors update"

# Check if ieee-oui.txt or ieee-iab.txt exist
if [ -f "${OUI_FILE}" ]; then
  echo "[INSTALL] The file ieee-oui.txt exists. Skipping update_vendors.sh..."
else
  echo "[INSTALL] The file ieee-oui.txt does not exist. Running update_vendors..."

  # Run the update_vendors.sh script
  if [ -f "${SYSTEM_SERVICES}/update_vendors.sh" ]; then
    "${SYSTEM_SERVICES}/update_vendors.sh"
  else
    echo "[INSTALL] update_vendors.sh script not found in ${SYSTEM_SERVICES}."
  fi
fi

echo "---------------------------------------------------------"
echo "[INSTALL] Create log and api mounts"
echo "---------------------------------------------------------"
echo

echo "[INSTALL] Cleaning up old mounts if any"
umount "${INSTALL_DIR}/log"
umount "${INSTALL_DIR}/api"

echo "[INSTALL] Creating log and api folders if they don't exist"
mkdir -p "${INSTALL_DIR}/log" "${INSTALL_DIR}/api"

echo "[INSTALL] Mounting log and api folders as tmpfs"
mount -t tmpfs -o noexec,nosuid,nodev tmpfs "${INSTALL_DIR}/log"
mount -t tmpfs -o noexec,nosuid,nodev tmpfs "${INSTALL_DIR}/api"


# Create log files if they don't exist
echo "[INSTALL] Creating log files if they don't exist"
touch "${INSTALL_DIR}"/log/{app.log,execution_queue.log,app_front.log,app.php_errors.log,stderr.log,stdout.log,db_is_locked.log}
touch "${INSTALL_DIR}"/api/user_notifications.json
# Create plugins sub-directory if it doesn't exist in case a custom log folder is used
mkdir -p "${INSTALL_DIR}"/log/plugins


# DANGER ZONE: ALWAYS_FRESH_INSTALL
if [ "${ALWAYS_FRESH_INSTALL}" = true ]; then
  echo "[INSTALL] ❗ ALERT /db and /config folders are cleared because the ALWAYS_FRESH_INSTALL is set to: ${ALWAYS_FRESH_INSTALL}❗"
  # Delete content of "/config/"
  rm -rf "${INSTALL_DIR}/config/"*

  # Delete content of "/db/"
  rm -rf "${INSTALL_DIR}/db/"*
fi

echo "[INSTALL] Copy starter ${DB_FILE} and ${CONF_FILE} if they don't exist"

# Copy starter ${DB_FILE} and ${CONF_FILE} if they don't exist
cp -u "${INSTALL_DIR}/back/${CONF_FILE}" "${INSTALL_DIR}/config/${CONF_FILE}"
cp -u "${INSTALL_DIR}/back/${DB_FILE}" "$FILEDB"

echo "[INSTALL] Fixing permissions after copied starter config & DB"

if [ -f "$FILEDB" ]; then
    chown -R www-data:www-data "$FILEDB"
fi
chown root:www-data "${INSTALL_DIR}"/api/user_notifications.json
chgrp -R www-data "${INSTALL_DIR}"
chmod -R u+rwx,g+rwx,o=rx "$WEB_UI_DIR"
chmod -R u+rwx,g+rwx,o=rx "${INSTALL_DIR}"
chmod -R u+rwX,g+rwX,o=rX "${INSTALL_DIR}/log"
chmod -R u+rwX,g+rwX,o=rX "${INSTALL_DIR}/config"

# Check if buildtimestamp.txt doesn't exist
if [ ! -f "${INSTALL_DIR}/front/buildtimestamp.txt" ]; then
    # Create buildtimestamp.txt
    date +%s > "${INSTALL_DIR}/front/buildtimestamp.txt"
fi

# start PHP and nginx
systemctl start php${PHPVERSION}-fpm || { echo "[INSTALL] Failed to start php${PHPVERSION}-fpm"; exit 1; }
nginx -t || { echo "[INSTALL] nginx config test failed"; exit 1; }
systemctl start nginx || { echo "[INSTALL] Failed to start nginx"; exit 1; }


echo "---------------------------------------------------------"
echo "[INSTALL] Installation complete"
echo "---------------------------------------------------------"
echo

# Export all variables to /etc/default/netalertx file for use by the systemd service
env_vars=( "INSTALL_SYSTEM_NAME" "INSTALLER_DIR" "INSTALL_DIR" "PHPVERSION" "VIRTUAL_ENV" "PATH" )
printf "" > "${SYSTEMD_UNIT_DEFAULTS}"
for var in "${env_vars[@]}"; do
  echo "$var=${!var}" >> "${SYSTEMD_UNIT_DEFAULTS}"
done


echo "---------------------------------------------------------"
echo "[INSTALL] Starting netalertx service"
echo "---------------------------------------------------------"
echo

# Create systemd service
cp "${INSTALLER_DIR}/netalertx.service" "${SYSTEMD_UNIT_FILE}" || { echo "[INSTALL] Failed to copy systemd service file"; exit 1; }
# Adjust our path to the correct python in virtualenv
echo "[INSTALL] Setting up systemd unit"
sed -i 's|ExecStart=/usr/bin/python3|ExecStart='"${VIRTUAL_ENV}"'/bin/python3|ig' "/${SYSTEMD_UNIT_FILE}" || { echo "[INSTALL] Failed to setup systemd service file"; exit 1; }

systemctl daemon-reload || { echo "[INSTALL] Failed to reload systemd daemon"; exit 1; }
systemctl enable netalertx || { echo "[INSTALL] Failed to enable NetAlertX service"; exit 1; }
systemctl start netalertx || { echo "[INSTALL] Failed to start NetAlertX service"; exit 1; }
echo "[INSTALL] 🚀 Starting app - navigate to your <server IP>:${PORT}"
