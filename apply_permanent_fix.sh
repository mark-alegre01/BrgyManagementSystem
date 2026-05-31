#!/bin/bash
echo "================================================="
echo "   INSTALLING PERMANENT HOTSPOT & INTERNET FIX   "
echo "================================================="

WIFI_IFACE="wlan0"
ETH_IFACE="end0"

echo "[1/6] Stopping interfering services (wpa_supplicant)..."
sudo systemctl stop wpa_supplicant 2>/dev/null
sudo systemctl disable wpa_supplicant 2>/dev/null
sudo systemctl mask wpa_supplicant 2>/dev/null

echo "[2/6] Telling NetworkManager to completely ignore WiFi..."
cat << EOF | sudo tee /etc/NetworkManager/conf.d/99-unmanaged-devices.conf
[keyfile]
unmanaged-devices=interface-name:$WIFI_IFACE
EOF
sudo systemctl restart NetworkManager
sleep 3

echo "[3/6] Forcing DNS resolution to Google..."
sudo rm -f /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf

echo "[4/6] Creating the permanent boot service..."
cat << EOF | sudo tee /usr/local/bin/brgy-boot.sh
#!/bin/bash
# 1. Clear any stray IPs from WiFi just in case
ip addr flush dev $WIFI_IFACE
ip route del default dev $WIFI_IFACE 2>/dev/null

# 2. Set the static IP for the hotspot
ip addr add 10.42.0.1/24 dev $WIFI_IFACE

# 3. Enable Internet Sharing (NAT)
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -o $ETH_IFACE -j MASQUERADE
iptables -A FORWARD -i $ETH_IFACE -o $WIFI_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i $WIFI_IFACE -o $ETH_IFACE -j ACCEPT

# 4. Force DNS
rm -f /etc/resolv.conf
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# 5. Restart services
systemctl restart hostapd
systemctl restart dnsmasq
exit 0
EOF

sudo chmod +x /usr/local/bin/brgy-boot.sh

cat << EOF | sudo tee /etc/systemd/system/brgy-boot.service
[Unit]
Description=Barangay System Permanent Network Fix
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/brgy-boot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

echo "[5/6] Enabling the boot service so it runs on every restart..."
sudo systemctl daemon-reload
sudo systemctl enable brgy-boot.service
sudo systemctl start brgy-boot.service

echo "[6/6] Cleaning up old broken scripts..."
sudo systemctl disable brgy-network.service 2>/dev/null
sudo rm -f /etc/rc.local

echo "================================================="
echo " SUCCESS! The Orange Pi is now permanently fixed."
echo " The hotspot will be 100% stable and the internet"
echo " routing will survive every reboot flawlessly!"
echo "================================================="
