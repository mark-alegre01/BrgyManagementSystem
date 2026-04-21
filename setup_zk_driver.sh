#!/bin/bash

# Configuration
RULE_FILE="/etc/udev/rules.d/99-zkfp.rules"
LIB_PATH="/usr/local/lib/libzkfp.so"
PROJECT_LIB="/home/mharkd/.gemini/antigravity/scratch/BrgyManagementSystem/core/libzkfp.so"

echo "Setting up ZK9500 Driver..."

# 1. Install udev rules
echo "Installing udev rules for device 1b55:0124..."
# We use 1b55:0124 which was detected in lsusb
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1b55", ATTR{idProduct}=="0124", MODE="0666"' | sudo tee $RULE_FILE

# 2. Reload udev
echo "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

# 3. Copy library to /usr/local/lib
if [ -f "$PROJECT_LIB" ]; then
    echo "Copying libzkfp.so to /usr/local/lib..."
    sudo cp "$PROJECT_LIB" "$LIB_PATH"
    sudo chmod 644 "$LIB_PATH"
    sudo ldconfig
    echo "Library installed successfully."
else
    echo "Error: $PROJECT_LIB not found."
    exit 1
fi

echo "------------------------------------------------"
echo "Setup Complete!"
echo "Please UNPLUG and RE-PLUG your ZK9500 device now."
echo "------------------------------------------------"
