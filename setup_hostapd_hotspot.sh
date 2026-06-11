#!/bin/bash
# ==============================================================================
# Barangay Management System - Hostapd AP Setup Script
# ==============================================================================
# This script sets up the Orange Pi as a Standalone Router using hostapd + dnsmasq.
# It will broadcast "Barangay_System_WiFi" (password: barangay123) and assign
# the Orange Pi the static IP 10.42.0.1.

if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] Please run this script with sudo:"
  echo "sudo ./setup_hostapd_hotspot.sh"
  exit
fi

WIFI_IFACE="wlan0"
ETH_IFACE="end0" # Default ethernet on Orange Pi 3B / similar boards

echo "=================================================="
echo " Configuring Standalone Router Mode (Hostapd)"
echo "=================================================="

# 1. Stop services before configuration
echo "[INFO] Stopping services..."
systemctl stop hostapd
systemctl stop dnsmasq

# 2. Tell NetworkManager to ignore wlan0 so it doesn't fight hostapd
echo "[INFO] Configuring NetworkManager to ignore $WIFI_IFACE..."
cat <<EOF > /etc/NetworkManager/conf.d/10-ignore-wlan0.conf
[keyfile]
unmanaged-devices=interface-name:$WIFI_IFACE
EOF
systemctl restart NetworkManager

# 3. Unmask and enable hostapd
systemctl unmask hostapd 2>/dev/null
systemctl enable hostapd

# 4. Configure a static IP for wlan0
echo "[INFO] Setting static IP 10.42.0.1 for $WIFI_IFACE..."
ip link set dev $WIFI_IFACE up
ip addr flush dev $WIFI_IFACE
ip addr add 10.42.0.1/24 dev $WIFI_IFACE

# Make it persistent via systemd-networkd or interfaces file
cat <<EOF > /etc/network/interfaces.d/wlan0-ap
auto $WIFI_IFACE
iface $WIFI_IFACE inet static
    address 10.42.0.1
    netmask 255.255.255.0
EOF

# 5. Configure DHCP server (dnsmasq)
echo "[INFO] Configuring DHCP (dnsmasq)..."
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null
cat <<EOF > /etc/dnsmasq.conf
interface=$WIFI_IFACE
bind-interfaces
dhcp-range=10.42.0.10,10.42.0.100,255.255.255.0,24h
domain=local
address=/brgysicosico.local/10.42.0.1
EOF

# 6. Configure Access Point (hostapd)
echo "[INFO] Configuring WiFi Hotspot (hostapd)..."
cat <<EOF > /etc/hostapd/hostapd.conf
interface=$WIFI_IFACE
driver=nl80211
country_code=PH
ssid=Barangay_System_WiFi
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=barangay123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
EOF

# Point hostapd to this configuration
sed -i 's|^#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd

# 7. Enable IP Forwarding (Internet Sharing)
echo "[INFO] Enabling Internet Sharing (NAT)..."
sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/g' /etc/sysctl.conf
sysctl -p

# 8. Configure Firewall (iptables) to share internet from ethernet to WiFi
iptables -t nat -F
iptables -t nat -A POSTROUTING -o $ETH_IFACE -j MASQUERADE
iptables -A FORWARD -i $ETH_IFACE -o $WIFI_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i $WIFI_IFACE -o $ETH_IFACE -j ACCEPT
netfilter-persistent save

# 9. Start Services
echo "[INFO] Starting services..."
systemctl restart dnsmasq
systemctl restart hostapd

echo "=========================================================="
echo " SUCCESS! Standalone Router Mode Configured."
echo "=========================================================="
echo " Network Name (SSID): Barangay_System_WiFi"
echo " Password           : barangay123"
echo " Orange Pi IP       : 10.42.0.1"
echo "=========================================================="
echo " NOTE: If the hotspot doesn't appear, run:"
echo " sudo reboot"
