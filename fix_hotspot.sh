#!/bin/bash
# ==============================================================================
# Barangay System - Hotspot Diagnostic & Fix Script
# ==============================================================================
# Run this on the Orange Pi to diagnose WHY the hotspot is not broadcasting,
# then automatically apply the correct fix.
#
# Usage: sudo ./fix_hotspot.sh
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Please run with sudo: sudo ./fix_hotspot.sh${NC}"
  exit 1
fi

echo -e "${CYAN}=========================================================="
echo -e "  Barangay System - Hotspot Diagnostic & Fix"
echo -e "==========================================================${NC}"

# ==============================================================================
# STEP 1: DETECT THE ACTUAL WIFI INTERFACE NAME
# ==============================================================================
echo -e "\n${YELLOW}[STEP 1] Detecting WiFi interface name...${NC}"

# Show all network interfaces
echo "--- All interfaces found: ---"
ip link show | grep -E "^[0-9]+:" | awk '{print $2}' | sed 's/://'

# Try to find the WiFi interface
WIFI_IFACE=$(iw dev 2>/dev/null | awk '$1=="Interface"{print $2}' | head -n 1)

if [ -z "$WIFI_IFACE" ]; then
    # Fallback: try common names
    for iface in wlan0 wlan1 wlx0 wlp2s0; do
        if ip link show "$iface" &>/dev/null; then
            WIFI_IFACE="$iface"
            break
        fi
    done
fi

if [ -z "$WIFI_IFACE" ]; then
    echo -e "${RED}[FATAL] No WiFi interface detected!"
    echo -e "        Your Orange Pi may not have a WiFi chip or it is disabled.${NC}"
    echo ""
    echo "Try running: lsusb  (to check for USB WiFi adapter)"
    echo "Try running: lspci  (to check for PCIe WiFi adapter)"
    exit 1
fi

echo -e "${GREEN}[OK] WiFi interface found: $WIFI_IFACE${NC}"

# ==============================================================================
# STEP 2: CHECK IF INTERFACE SUPPORTS AP MODE
# ==============================================================================
echo -e "\n${YELLOW}[STEP 2] Checking if $WIFI_IFACE supports Access Point (AP) mode...${NC}"

AP_SUPPORT=$(iw phy 2>/dev/null | grep -A 10 "Supported interface modes" | grep "AP")
if [ -z "$AP_SUPPORT" ]; then
    echo -e "${RED}[FATAL] Your WiFi chip does NOT support AP mode!"
    echo -e "        hostapd will NEVER work with this hardware.${NC}"
    echo ""
    echo "SOLUTION: Buy a USB WiFi adapter that supports AP mode."
    echo "          Recommended: TP-Link TL-WN823N or any Realtek RTL8188/RTL8192"
    exit 1
fi
echo -e "${GREEN}[OK] AP mode is supported.${NC}"

# ==============================================================================
# STEP 3: CHECK RFKILL (HARDWARE/SOFTWARE BLOCK)
# ==============================================================================
echo -e "\n${YELLOW}[STEP 3] Checking rfkill (radio blocks)...${NC}"
rfkill list all
SOFT_BLOCKED=$(rfkill list all | grep -i "Soft blocked: yes")
HARD_BLOCKED=$(rfkill list all | grep -i "Hard blocked: yes")

if [ -n "$HARD_BLOCKED" ]; then
    echo -e "${RED}[FATAL] WiFi is HARDWARE BLOCKED. Check physical WiFi switch on device.${NC}"
    exit 1
fi

if [ -n "$SOFT_BLOCKED" ]; then
    echo -e "${YELLOW}[FIX] WiFi is soft-blocked. Unblocking...${NC}"
    rfkill unblock wifi
    rfkill unblock all
    echo -e "${GREEN}[OK] Unblocked.${NC}"
else
    echo -e "${GREEN}[OK] No rfkill blocks.${NC}"
fi

# ==============================================================================
# STEP 4: CHECK HOSTAPD SERVICE STATUS
# ==============================================================================
echo -e "\n${YELLOW}[STEP 4] Checking hostapd status...${NC}"

if ! command -v hostapd &>/dev/null; then
    echo -e "${RED}[ERROR] hostapd is NOT installed!${NC}"
    echo -e "${YELLOW}[FIX] Installing hostapd and dnsmasq...${NC}"
    apt-get update -qq
    apt-get install -y hostapd dnsmasq iptables-persistent
    echo -e "${GREEN}[OK] Installed.${NC}"
else
    echo -e "${GREEN}[OK] hostapd is installed.${NC}"
fi

# Check if masked
MASKED=$(systemctl status hostapd 2>&1 | grep -i "masked")
if [ -n "$MASKED" ]; then
    echo -e "${YELLOW}[FIX] hostapd is MASKED. Unmasking...${NC}"
    systemctl unmask hostapd
    echo -e "${GREEN}[OK] Unmasked.${NC}"
fi

# Show hostapd status
echo "--- hostapd service status ---"
systemctl status hostapd --no-pager -l 2>&1 | tail -20

# ==============================================================================
# STEP 5: CHECK NETWORKMANAGER CONFLICT
# ==============================================================================
echo -e "\n${YELLOW}[STEP 5] Checking NetworkManager conflict with $WIFI_IFACE...${NC}"

NM_MANAGING=$(nmcli dev status 2>/dev/null | grep "$WIFI_IFACE" | grep -v unmanaged)
if [ -n "$NM_MANAGING" ]; then
    echo -e "${YELLOW}[FIX] NetworkManager is managing $WIFI_IFACE — this conflicts with hostapd!${NC}"
    echo "      Telling NetworkManager to ignore $WIFI_IFACE..."
    mkdir -p /etc/NetworkManager/conf.d/
    cat > /etc/NetworkManager/conf.d/10-ignore-wifi.conf <<EOF
[keyfile]
unmanaged-devices=interface-name:$WIFI_IFACE
EOF
    systemctl restart NetworkManager
    sleep 2
    echo -e "${GREEN}[OK] NetworkManager will now ignore $WIFI_IFACE.${NC}"
else
    echo -e "${GREEN}[OK] NetworkManager is not interfering.${NC}"
fi

# ==============================================================================
# STEP 6: DETECT ETHERNET INTERFACE
# ==============================================================================
echo -e "\n${YELLOW}[STEP 6] Detecting Ethernet interface for internet sharing...${NC}"
ETH_IFACE=$(ip route | grep default | awk '{print $5}' | head -n 1)

if [ -z "$ETH_IFACE" ]; then
    # Fallback: try common names
    for iface in end0 eth0 enp1s0 enp2s0; do
        if ip link show "$iface" &>/dev/null; then
            ETH_IFACE="$iface"
            break
        fi
    done
fi

if [ -z "$ETH_IFACE" ]; then
    echo -e "${YELLOW}[WARN] No ethernet interface found. Internet sharing will be skipped.${NC}"
    echo "       Make sure LAN cable is plugged in before running this script."
    ETH_IFACE="end0"
else
    echo -e "${GREEN}[OK] Ethernet interface: $ETH_IFACE${NC}"
fi

# ==============================================================================
# STEP 7: WRITE CORRECT HOSTAPD CONFIG
# ==============================================================================
echo -e "\n${YELLOW}[STEP 7] Writing correct hostapd configuration...${NC}"

cat > /etc/hostapd/hostapd.conf <<EOF
interface=$WIFI_IFACE
driver=nl80211
ssid=Barangay_System_WiFi
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=barangay123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

echo -e "${GREEN}[OK] hostapd.conf written with interface=$WIFI_IFACE${NC}"

# Make sure /etc/default/hostapd points to our config
if [ -f /etc/default/hostapd ]; then
    # Remove old DAEMON_CONF lines and add correct one
    sed -i '/^DAEMON_CONF/d' /etc/default/hostapd
    sed -i '/^#DAEMON_CONF/d' /etc/default/hostapd
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd
    echo -e "${GREEN}[OK] /etc/default/hostapd updated.${NC}"
fi

# ==============================================================================
# STEP 8: SET STATIC IP ON WIFI INTERFACE
# ==============================================================================
echo -e "\n${YELLOW}[STEP 8] Setting static IP 10.42.0.1 on $WIFI_IFACE...${NC}"

ip link set dev $WIFI_IFACE up
sleep 1
ip addr flush dev $WIFI_IFACE
ip addr add 10.42.0.1/24 dev $WIFI_IFACE
echo -e "${GREEN}[OK] IP set.${NC}"

# ==============================================================================
# STEP 9: CONFIGURE DNSMASQ (DHCP SERVER)
# ==============================================================================
echo -e "\n${YELLOW}[STEP 9] Configuring dnsmasq DHCP...${NC}"

# Stop dnsmasq if it is fighting with systemd-resolved on port 53
systemctl stop dnsmasq 2>/dev/null
systemctl disable systemd-resolved 2>/dev/null
systemctl stop systemd-resolved 2>/dev/null

# Check if port 53 is already occupied
PORT53=$(ss -tlnp | grep ':53')
if [ -n "$PORT53" ]; then
    echo -e "${YELLOW}[WARN] Port 53 is in use. Killing the occupant...${NC}"
    fuser -k 53/tcp 2>/dev/null
    fuser -k 53/udp 2>/dev/null
fi

# Back up original
[ -f /etc/dnsmasq.conf ] && cp /etc/dnsmasq.conf /etc/dnsmasq.conf.bak

cat > /etc/dnsmasq.conf <<EOF
# Barangay System DHCP Config
interface=$WIFI_IFACE
bind-interfaces
except-interface=lo
dhcp-range=10.42.0.10,10.42.0.100,255.255.255.0,24h
domain=local
address=/brgysicosico.local/10.42.0.1
# Prevent dnsmasq from touching /etc/resolv.conf
no-resolv
server=8.8.8.8
server=8.8.4.4
EOF

echo -e "${GREEN}[OK] dnsmasq configured.${NC}"

# ==============================================================================
# STEP 10: ENABLE IP FORWARDING AND NAT (INTERNET SHARING)
# ==============================================================================
echo -e "\n${YELLOW}[STEP 10] Enabling Internet sharing (NAT)...${NC}"

# Enable immediately
echo 1 > /proc/sys/net/ipv4/ip_forward

# Make persistent
grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sed -i 's/^#*net.ipv4.ip_forward.*/net.ipv4.ip_forward=1/' /etc/sysctl.conf
sysctl -p

# iptables NAT rules
iptables -t nat -F
iptables -F FORWARD
iptables -t nat -A POSTROUTING -o $ETH_IFACE -j MASQUERADE
iptables -A FORWARD -i $ETH_IFACE -o $WIFI_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i $WIFI_IFACE -o $ETH_IFACE -j ACCEPT

# Save iptables rules
if command -v netfilter-persistent &>/dev/null; then
    netfilter-persistent save
elif command -v iptables-save &>/dev/null; then
    iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
fi

echo -e "${GREEN}[OK] NAT routing enabled: $WIFI_IFACE <-> $ETH_IFACE${NC}"

# ==============================================================================
# STEP 11: START SERVICES
# ==============================================================================
echo -e "\n${YELLOW}[STEP 11] Starting services...${NC}"

systemctl enable hostapd
systemctl enable dnsmasq

systemctl restart dnsmasq
sleep 1
echo "--- dnsmasq status ---"
systemctl status dnsmasq --no-pager -l | tail -10

systemctl restart hostapd
sleep 3
echo "--- hostapd status ---"
systemctl status hostapd --no-pager -l | tail -20

# ==============================================================================
# STEP 12: VERIFY
# ==============================================================================
echo -e "\n${YELLOW}[STEP 12] Final verification...${NC}"
echo "--- $WIFI_IFACE IP address ---"
ip addr show $WIFI_IFACE

HOSTAPD_RUNNING=$(systemctl is-active hostapd)
DNSMASQ_RUNNING=$(systemctl is-active dnsmasq)

echo ""
echo -e "${CYAN}=========================================================="
echo -e "  RESULT SUMMARY"
echo -e "==========================================================${NC}"
echo -e "  WiFi Interface : ${GREEN}$WIFI_IFACE${NC}"
echo -e "  Ethernet       : ${GREEN}$ETH_IFACE${NC}"
echo -e "  hostapd        : $([ "$HOSTAPD_RUNNING" = "active" ] && echo -e "${GREEN}RUNNING${NC}" || echo -e "${RED}FAILED${NC}")"
echo -e "  dnsmasq        : $([ "$DNSMASQ_RUNNING" = "active" ] && echo -e "${GREEN}RUNNING${NC}" || echo -e "${RED}FAILED${NC}")"
echo ""

if [ "$HOSTAPD_RUNNING" != "active" ]; then
    echo -e "${RED}[HOSTAPD FAILED] Full error log:${NC}"
    journalctl -u hostapd -n 30 --no-pager
    echo ""
    echo -e "${YELLOW}MANUAL DEBUG: Run this to test hostapd directly:${NC}"
    echo "  sudo hostapd -d /etc/hostapd/hostapd.conf"
else
    echo -e "${GREEN}=== SUCCESS! WiFi Hotspot should now be broadcasting ==="
    echo -e "  SSID     : Barangay_System_WiFi"
    echo -e "  Password : barangay123"
    echo -e "  IP       : 10.42.0.1${NC}"
fi

echo ""
echo -e "${CYAN}If the hotspot STILL doesn't appear, run this debug command:${NC}"
echo "  sudo hostapd -d /etc/hostapd/hostapd.conf"
echo "  (It will print the EXACT error causing the failure)"
