#!/bin/bash
# Biometric Server Wrapper
# This script starts the Barangay Management System.

# Get the absolute path of the project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CORE_DIR="$PROJECT_DIR/core"

# --- Clear stale ESP32 IP cache files ---
# These files store the last known ESP32 IP address. On a fresh boot the ESP32
# will announce its new IP via the heartbeat endpoint, so any old cached value
# from a previous session could point to a wrong address and delay discovery.
echo " Clearing stale ESP32 IP cache..."
rm -f "$PROJECT_DIR/.esp32_ip"
rm -f "$PROJECT_DIR/.esp32_heartbeat_ip"
echo " ESP32 IP cache cleared."


echo "=================================================="
echo " Starting Barangay Management System "
echo "=================================================="
echo "Project Path: $PROJECT_DIR"

# Run the Django server (0.0.0.0 = listen on all interfaces, including LAN)
./venv/bin/python manage.py runserver 0.0.0.0:8001
