#!/usr/bin/env bash

# 🛑 Important: This is only used for the bare-metal install 🛑
# Update /install/start.debian12.sh in most cases is preferred

echo "---------------------------------------------------------"
echo "[INSTALL]                         Run install.debian12.sh"
echo "---------------------------------------------------------"

# Set environment variables
INSTALL_DIR=/app  # Specify the installation directory here

# Check if script is run as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root. Please use 'sudo'."
    exit 1
fi

# Prepare the environment
apt-get update
apt-get install sudo -y

# Install Git
apt-get install -y git

# Clean the directory
rm -R ${INSTALL_DIR:?}/

# Clone the application repository
git clone https://github.com/netalertx/NetAlertX "$INSTALL_DIR/"

# Check for buildtimestamp.txt existence, otherwise create it
if [ ! -f $INSTALL_DIR/front/buildtimestamp.txt ]; then
  date +%s > $INSTALL_DIR/front/buildtimestamp.txt
fi

# Start NetAlertX
chmod +x "$INSTALL_DIR/install/debian12/start.debian12.sh"
"$INSTALL_DIR/install/debian12/start.debian12.sh"
