#!/usr/bin/env bash

echo "---------------------------------------------------------"
echo "[INSTALL]            Run install_dependencies.debian12.sh"
echo "---------------------------------------------------------"

# ❗ IMPORTANT - if you modify this file modify the root Dockerfile as well ❗

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
    echo "requirements.txt not found at ${REQUIREMENTS_FILE}. Please ensure the repository root is available." >&2
    exit 1
fi

# Check if script is run as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root. Please use 'sudo'."
    exit 1
fi

# Install dependencies
apt-get install -y \
    tini snmp ca-certificates curl libwww-perl arp-scan perl apt-utils cron sudo gettext-base \
    nginx-light php php-cgi php-fpm php-sqlite3 php-curl sqlite3 dnsutils net-tools  \
    python3 python3-dev python3-psutil iproute2 nmap fping python3-pip zip usbutils traceroute nbtscan avahi-daemon avahi-utils openrc build-essential git

# alternate dependencies
sudo apt-get install nginx nginx-core mtr php-fpm php8.2-fpm php-cli php8.2 php8.2-sqlite3 -y
sudo phpenmod -v 8.2 sqlite3

# setup virtual python environment so we can use pip3 to install packages
apt-get install python3-venv -y
python3 -m venv /opt/venv
# Shell check doesn't recognize source command because it's not in the repo, it is in the system at runtime
# shellcheck disable=SC1091
source /opt/venv/bin/activate

update-alternatives --install /usr/bin/python python /usr/bin/python3 10

#  install packages thru pip3
pip3 install -r "${REQUIREMENTS_FILE}"
