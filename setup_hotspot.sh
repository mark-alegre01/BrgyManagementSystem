#!/bin/bash
# ==============================================================================
# Barangay Management System - Hotspot Setup Script for Orange Pi
# ==============================================================================
# This script configures the Orange Pi to broadcast its own WiFi network.
# This ensures a flawless, permanent connection with the ESP32 (at 10.42.0.1)
# while allowing you to plug in an Ethernet cable for global internet access.

if [ "$EUID" -ne 0 ]; then
  echo "Please run this script with sudo:"
  echo "sudo ./setup_hotspot.sh"
  exit
fi

echo "=================================================="
echo " Setting up Barangay System WiFi Hotspot"
echo "=================================================="

# 1. Check if nmcli is installed
if ! command -v nmcli &> /dev/null; then
    echo "[ERROR] NetworkManager (nmcli) could not be found. Please install it."
    exit 1
fi

# 2. Get the WiFi interface name (usually wlan0, but sometimes wlx...)
WIFI_IFACE=$(nmcli -t -f DEVICE,TYPE device | grep 802-11-wireless | cut -d: -f1 | head -n 1)

if [ -z "$WIFI_IFACE" ]; then
    echo "[ERROR] No WiFi hardware found on this device!"
    exit 1
fi

echo "[INFO] Found WiFi interface: $WIFI_IFACE"

# 3. Clean up any existing hotspot with the same name
if nmcli con show "Barangay_System_WiFi" &> /dev/null; then
    echo "[INFO] Removing old hotspot configuration..."
    nmcli con delete "Barangay_System_WiFi"
fi

# 4. Create the hotspot connection
# Using ipv4.method shared turns the Orange Pi into a router (NAT + DHCP).
# It will assign itself 10.42.0.1 by default.
echo "[INFO] Creating new hotspot connection..."
nmcli con add type wifi ifname $WIFI_IFACE con-name "Barangay_System_WiFi" autoconnect yes ssid "Barangay_System_WiFi"
nmcli con modify "Barangay_System_WiFi" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
nmcli con modify "Barangay_System_WiFi" wifi-sec.key-mgmt wpa-psk
nmcli con modify "Barangay_System_WiFi" wifi-sec.psk "barangay123"

# 5. Bring up the hotspot
echo "[INFO] Starting Hotspot..."
if nmcli con up "Barangay_System_WiFi"; then
    echo ""
    echo "=========================================================="
    echo " SUCCESS! Hotspot Created."
    echo "=========================================================="
    echo " Network Name (SSID): Barangay_System_WiFi"
    echo " Password           : barangay123"
    echo " Orange Pi IP       : 10.42.0.1"
    echo "=========================================================="
    echo ""
    echo "NEXT STEPS:"
    echo "1. Plug an Ethernet cable into the Orange Pi for internet."
    echo "2. Connect your laptop to 'Barangay_System_WiFi'."
    echo "3. Restart your ESP32, connect to its 'ESP32-Setup' portal,"
    echo "   and enter 'Barangay_System_WiFi' / 'barangay123'."
else
    echo "[ERROR] Failed to start hotspot. Your WiFi adapter might not support AP mode."
fi
