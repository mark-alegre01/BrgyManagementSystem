#!/bin/bash
# ==============================================================================
# Barangay Management System — Startup Script
# ==============================================================================
# The Orange Pi Zero 3 runs as a dual-network node:
#   wlan0 → Barangay_System_WiFi hotspot at 10.42.0.1 (for ESP32)
#   end0  → LAN cable to ISP router (for resident web app via Tailscale)
# ==============================================================================

# Get the absolute path of the project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=================================================="
echo " Starting Barangay Management System             "
echo "=================================================="
echo " Project Path : $PROJECT_DIR"

# --- Clear stale ESP32 IP cache files ---
# These files store the last known ESP32 IP address. On a fresh boot the ESP32
# will announce its new IP via the heartbeat endpoint, so any old cached value
# from a previous session could point to a wrong address and delay discovery.
echo " Clearing stale ESP32 IP cache..."
rm -f "$PROJECT_DIR/.esp32_ip"
rm -f "$PROJECT_DIR/.esp32_heartbeat_ip"
echo " ESP32 IP cache cleared."

# --- Show network interfaces for reference ---
echo "--------------------------------------------------"
HOTSPOT_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
LAN_IP=$(ip addr show end0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)

if [ -n "$HOTSPOT_IP" ]; then
  echo " Hotspot (wlan0) : $HOTSPOT_IP  <-- ESP32 connects here"
else
  echo " Hotspot (wlan0) : NOT UP  <-- Run setup_hostapd_hotspot.sh first!"
fi

if [ -n "$LAN_IP" ]; then
  echo " Internet (end0) : $LAN_IP  <-- Resident web app (via Tailscale)"
else
  echo " Internet (end0) : NOT UP  <-- Check LAN cable connection"
fi
echo "--------------------------------------------------"

# Run the Django server on all interfaces (serves both hotspot and LAN)
echo " Starting Django on 0.0.0.0:8001 ..."
./venv/bin/python manage.py runserver 0.0.0.0:8001
