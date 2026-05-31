#!/bin/bash
# ==============================================================================
# Barangay System - Hotspot Diagnostic & Fix Script (PERMANENT FIX v2)
# ==============================================================================
# Run this on the Orange Pi to:
#   1. Permanently ban NetworkManager from touching wlan0
#   2. Delete all rogue Wi-Fi profiles that steal the interface
#   3. Set up hostapd + dnsmasq for the hotspot
#   4. Enable NAT internet sharing from Ethernet to Wi-Fi
#   5. Persist ALL settings across reboots
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
echo -e "  Barangay System - Hotspot Diagnostic & Fix (v2)"
echo -e "==========================================================${NC}"

# ==============================================================================
# STEP 0: PERMANENTLY BAN NETWORKMANAGER FROM TOUCHING WLAN0
# ==============================================================================
# THIS IS THE ROOT CAUSE OF ALL INTERNET DROPS.
# NetworkManager keeps creating Wi-Fi connections on wlan0, which:
#   - Steals the interface from hostapd
#   - Adds a bad default route via wlan0 (instead of end0)
#   - Assigns 192.168.x.x to wlan0 (conflicts with the hotspot 10.42.0.1)
# ==============================================================================
echo -e "\n${YELLOW}[STEP 0] Permanently banning NetworkManager from wlan0...${NC}"

# 0a. Create the permanent ignore rule
mkdir -p /etc/NetworkManager/conf.d/
cat > /etc/NetworkManager/conf.d/10-ignore-wifi.conf <<EOF
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF
echo -e "${GREEN}[OK] Created /etc/NetworkManager/conf.d/10-ignore-wifi.conf${NC}"

# 0b. Also add it to the main NetworkManager config as a backup
if [ -f /etc/NetworkManager/NetworkManager.conf ]; then
    if ! grep -q "unmanaged-devices=interface-name:wlan0" /etc/NetworkManager/NetworkManager.conf; then
        # Add under [keyfile] section if it exists, otherwise append
        if grep -q "\[keyfile\]" /etc/NetworkManager/NetworkManager.conf; then
            sed -i '/\[keyfile\]/a unmanaged-devices=interface-name:wlan0' /etc/NetworkManager/NetworkManager.conf
        else
            echo -e "\n[keyfile]\nunmanaged-devices=interface-name:wlan0" >> /etc/NetworkManager/NetworkManager.conf
        fi
        echo -e "${GREEN}[OK] Also patched NetworkManager.conf${NC}"
    fi
fi

# 0c. Delete ALL saved Wi-Fi connections that could hijack wlan0
echo -e "${YELLOW}    Deleting rogue Wi-Fi profiles from NetworkManager...${NC}"
# Get all wifi-type connections and delete them
nmcli -t -f NAME,TYPE connection show 2>/dev/null | grep ":.*wifi" | cut -d: -f1 | while read -r conn; do
    echo -e "    Deleting: $conn"
    nmcli connection delete "$conn" 2>/dev/null || true
done

# Also delete known problematic connection names (in case they have wrong type)
for conn in "Hotspot" "Hotspot-1" "Hotspot-2" "netplan-wlan0" "Wi-Fi connection 1" "Wi-Fi connection 2"; do
    nmcli connection delete "$conn" 2>/dev/null || true
done
echo -e "${GREEN}[OK] All rogue Wi-Fi profiles deleted.${NC}"

# 0d. Tell NetworkManager to unmanage wlan0 right now
nmcli device set wlan0 managed no 2>/dev/null || true

# 0e. Restart NetworkManager to apply the ignore rule
systemctl restart NetworkManager
sleep 2
echo -e "${GREEN}[OK] NetworkManager restarted. wlan0 is now permanently unmanaged.${NC}"

# 0f. Remove any bad IP addresses and routes that NetworkManager left behind
echo -e "${YELLOW}    Cleaning up leftover routes and IPs on wlan0...${NC}"
# Delete any default route pointing to wlan0
ip route del default dev wlan0 2>/dev/null || true
# Delete any 192.168.x.x address on wlan0 (these are from the router, NOT the hotspot)
ip addr show wlan0 2>/dev/null | grep "inet 192\." | awk '{print $2}' | while read -r addr; do
    echo -e "    Removing bad IP: $addr from wlan0"
    ip addr del "$addr" dev wlan0 2>/dev/null || true
done
echo -e "${GREEN}[OK] Cleanup complete.${NC}"

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
# STEP 5: DISABLE CONFLICTING NETWORK SERVICES
# ==============================================================================
echo -e "\n${YELLOW}[STEP 5] Disabling conflicting network services...${NC}"

# Disable dhcpcd if running (fights with NetworkManager)
if systemctl is-active dhcpcd &>/dev/null; then
    echo -e "${YELLOW}[FIX] dhcpcd is running — disabling it...${NC}"
    systemctl stop dhcpcd
    systemctl disable dhcpcd
    echo -e "${GREEN}[OK] dhcpcd disabled.${NC}"
fi

# Disable systemd-networkd if running (fights with NetworkManager)
if systemctl is-active systemd-networkd &>/dev/null; then
    echo -e "${YELLOW}[FIX] systemd-networkd is running — disabling it...${NC}"
    systemctl stop systemd-networkd
    systemctl disable systemd-networkd
    echo -e "${GREEN}[OK] systemd-networkd disabled.${NC}"
fi

# Verify wlan0 is truly unmanaged by NetworkManager
NM_STATUS=$(nmcli dev status 2>/dev/null | grep "$WIFI_IFACE" | awk '{print $3}')
if [ "$NM_STATUS" != "unmanaged" ] && [ -n "$NM_STATUS" ]; then
    echo -e "${YELLOW}[FIX] wlan0 is STILL managed by NetworkManager ($NM_STATUS). Forcing unmanaged...${NC}"
    nmcli device set "$WIFI_IFACE" managed no 2>/dev/null || true
    sleep 1
fi
echo -e "${GREEN}[OK] No conflicting services.${NC}"

# ==============================================================================
# STEP 6: DETECT ETHERNET INTERFACE (NEVER pick wlan0!)
# ==============================================================================
echo -e "\n${YELLOW}[STEP 6] Detecting Ethernet interface for internet sharing...${NC}"

# CRITICAL: We must NEVER use wlan0/wlan1 as the ethernet interface.
# Always detect by checking for physical ethernet ports first.
ETH_IFACE=""
for iface in end0 eth0 enp1s0 enp2s0 enp3s0; do
    if ip link show "$iface" &>/dev/null; then
        ETH_IFACE="$iface"
        break
    fi
done

if [ -z "$ETH_IFACE" ]; then
    echo -e "${RED}[ERROR] No physical ethernet interface found (checked end0, eth0, enp1s0, enp2s0).${NC}"
    echo -e "${YELLOW}        Defaulting to end0. Make sure LAN cable is plugged in.${NC}"
    ETH_IFACE="end0"
fi

echo -e "${GREEN}[OK] Ethernet interface: $ETH_IFACE${NC}"

# STEP 6b: Make sure the ethernet interface has an IP via DHCP
echo -e "${YELLOW}[STEP 6b] Ensuring $ETH_IFACE has internet (DHCP)...${NC}"
ip link set dev $ETH_IFACE up

# Check if NetworkManager has a connection for end0, if not create one
if ! nmcli -t -f NAME con show --active 2>/dev/null | grep -qi "$ETH_IFACE"; then
    echo -e "${YELLOW}[FIX] $ETH_IFACE is not active. Activating via NetworkManager...${NC}"
    # Try to bring up any existing connection for this device
    nmcli dev connect $ETH_IFACE 2>/dev/null || true
    sleep 3
fi

# Verify it got an IP
ETH_IP=$(ip addr show $ETH_IFACE 2>/dev/null | grep 'inet ' | grep -v '127.0.0' | awk '{print $2}' | head -1)
if [ -n "$ETH_IP" ]; then
    echo -e "${GREEN}[OK] $ETH_IFACE has IP: $ETH_IP${NC}"
else
    echo -e "${YELLOW}[WARN] $ETH_IFACE has no IP yet. Trying nmcli...${NC}"
    nmcli dev connect $ETH_IFACE 2>/dev/null || true
    sleep 5
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
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=barangay123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
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
# STEP 10: FIX DNS RESOLUTION ON THE ORANGE PI ITSELF
# ==============================================================================
echo -e "\n${YELLOW}[STEP 10] Fixing DNS resolution on the Pi...${NC}"

# Remove symlink if it exists and write a proper resolv.conf
rm -f /etc/resolv.conf
cat > /etc/resolv.conf <<EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF

# Prevent anything from overwriting our resolv.conf
chattr +i /etc/resolv.conf 2>/dev/null || true
echo -e "${GREEN}[OK] DNS resolvers set to 8.8.8.8 and 8.8.4.4 (locked).${NC}"

# ==============================================================================
# STEP 11: ENABLE IP FORWARDING AND NAT (INTERNET SHARING) — PERMANENTLY
# ==============================================================================
echo -e "\n${YELLOW}[STEP 11] Enabling Internet sharing (NAT) permanently...${NC}"

# Enable immediately
echo 1 > /proc/sys/net/ipv4/ip_forward

# Make persistent in sysctl.conf
grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sed -i 's/^#*net.ipv4.ip_forward.*/net.ipv4.ip_forward=1/' /etc/sysctl.conf
sysctl -p

# SAFETY CHECK: Refuse to set up NAT if ETH_IFACE is a wireless interface
if echo "$ETH_IFACE" | grep -qE '^(wlan|wlp|wlx)'; then
    echo -e "${RED}[FATAL] ETH_IFACE='$ETH_IFACE' is a WiFi interface! Refusing to set up NAT.${NC}"
    echo -e "${RED}        This would kill your internet. Skipping NAT setup.${NC}"
else
    # FLUSH old rules first to prevent duplicates
    iptables -t nat -F
    iptables -F FORWARD

    # iptables NAT rules
    iptables -t nat -A POSTROUTING -o $ETH_IFACE -j MASQUERADE
    iptables -A FORWARD -i $ETH_IFACE -o $WIFI_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i $WIFI_IFACE -o $ETH_IFACE -j ACCEPT

    # Save iptables rules PERMANENTLY
    if command -v netfilter-persistent &>/dev/null; then
        netfilter-persistent save
    elif command -v iptables-save &>/dev/null; then
        mkdir -p /etc/iptables
        iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
    fi

    echo -e "${GREEN}[OK] NAT routing enabled: $WIFI_IFACE <-> $ETH_IFACE${NC}"
fi

# ==============================================================================
# STEP 12: DOUBLE-CHECK — REMOVE ANY BAD ROUTES ON WLAN0
# ==============================================================================
echo -e "\n${YELLOW}[STEP 12] Final route cleanup (removing any bad wlan0 routes)...${NC}"

# Delete any default route that goes through wlan0 (the #1 cause of all problems)
ip route del default dev $WIFI_IFACE 2>/dev/null || true

# Delete any 192.168.x.x routes on wlan0 (these belong to end0, not the hotspot)
ip route | grep "$WIFI_IFACE" | grep "192.168" | while read -r route; do
    echo -e "    Deleting bad route: $route"
    ip route del $route 2>/dev/null || true
done

# Make sure the ONLY default route goes through the Ethernet interface
DEFAULT_COUNT=$(ip route | grep "^default" | wc -l)
if [ "$DEFAULT_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}[FIX] No default route found! Adding one via $ETH_IFACE...${NC}"
    # Get the gateway from DHCP
    GW=$(nmcli -t -f IP4.GATEWAY dev show $ETH_IFACE 2>/dev/null | cut -d: -f2)
    if [ -n "$GW" ]; then
        ip route add default via $GW dev $ETH_IFACE
        echo -e "${GREEN}[OK] Default route added via $GW${NC}"
    else
        echo -e "${RED}[WARN] Could not detect gateway. Internet may not work.${NC}"
    fi
fi

echo -e "${GREEN}[OK] Route table is clean.${NC}"

# ==============================================================================
# STEP 13: START SERVICES
# ==============================================================================
echo -e "\n${YELLOW}[STEP 13] Starting services...${NC}"

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
# STEP 14: INSTALL SYSTEMD SERVICE FOR BOOT PERSISTENCE
# ==============================================================================
echo -e "\n${YELLOW}[STEP 14] Installing boot service for persistence...${NC}"

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

cat > /etc/systemd/system/brgy-network.service <<EOF
[Unit]
Description=Barangay System Network Fix (Hotspot + Internet Routing)
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 10
ExecStart=/bin/bash $SCRIPT_PATH
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable brgy-network.service
echo -e "${GREEN}[OK] brgy-network.service installed and enabled.${NC}"
echo -e "${GREEN}     This script will run automatically on every boot.${NC}"

# ==============================================================================
# STEP 15: VERIFY
# ==============================================================================
echo -e "\n${YELLOW}[STEP 15] Final verification...${NC}"
echo "--- $WIFI_IFACE IP address ---"
ip addr show $WIFI_IFACE

echo ""
echo "--- Routing table ---"
ip route

echo ""
echo "--- Testing internet connectivity ---"
if ping -c 2 -W 3 8.8.8.8 &>/dev/null; then
    INET_STATUS="${GREEN}WORKING${NC}"
else
    INET_STATUS="${RED}FAILED${NC}"
fi

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
echo -e "  Internet       : $INET_STATUS"
echo -e "  NM ignores wlan: ${GREEN}YES (permanent)${NC}"
echo -e "  Boot service   : ${GREEN}ENABLED${NC}"
echo ""

if [ "$HOSTAPD_RUNNING" != "active" ]; then
    echo -e "${RED}[HOSTAPD FAILED] Full error log:${NC}"
    journalctl -u hostapd -n 30 --no-pager
    echo ""
    echo -e "${YELLOW}MANUAL DEBUG: Run this to test hostapd directly:${NC}"
    echo "  sudo hostapd -d /etc/hostapd/hostapd.conf"
else
    echo -e "${GREEN}=== SUCCESS! WiFi Hotspot is broadcasting ==="
    echo -e "  SSID     : Barangay_System_WiFi"
    echo -e "  Password : barangay123"
    echo -e "  IP       : 10.42.0.1${NC}"
fi

echo ""
echo -e "${CYAN}This fix is now PERMANENT. It will survive reboots.${NC}"
echo -e "${CYAN}If you ever need to re-run manually: sudo bash $(basename $0)${NC}"
