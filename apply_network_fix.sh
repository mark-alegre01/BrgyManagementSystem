#!/bin/bash
# ==============================================================================
# Barangay System - Persistent Network Fix
# Runs on every boot to ensure correct routing.
# ==============================================================================

WIFI_IFACE="wlan0"

# Auto-detect Ethernet interface instead of hardcoding to br0
ETH_IFACE=$(ip route show default 2>/dev/null | grep -v "wlan0" | awk '{print $5}' | head -n 1)
if [ -z "$ETH_IFACE" ]; then
    for iface in end0 eth0 enp1s0 enp2s0 br0; do
        if ip link show "$iface" >/dev/null 2>&1; then
            ETH_IFACE="$iface"
            break
        fi
    done
fi

HOTSPOT_IP="10.42.0.1"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a /var/log/brgy_network.log; }

log "=== Barangay Network Fix Starting ==="

# 1. Ensure wlan0 is up
ip link set dev $WIFI_IFACE up
sleep 1

# 2. Remove any stray LAN IP from wlan0 (e.g. 192.168.1.x should NOT be on wlan0)
STRAY_IPS=$(ip addr show $WIFI_IFACE | grep 'inet ' | grep -v "$HOTSPOT_IP" | awk '{print $2}')
for IP in $STRAY_IPS; do
    log "Removing stray IP $IP from $WIFI_IFACE..."
    ip addr del "$IP" dev $WIFI_IFACE 2>/dev/null
done

# 3. Make sure wlan0 has ONLY the hotspot IP
if ! ip addr show $WIFI_IFACE | grep -q "$HOTSPOT_IP"; then
    log "Adding hotspot IP $HOTSPOT_IP to $WIFI_IFACE..."
    ip addr add "$HOTSPOT_IP/24" dev $WIFI_IFACE
fi

# 4. Remove any wrong default route via wlan0
WRONG_ROUTES=$(ip route show default dev $WIFI_IFACE)
if [ -n "$WRONG_ROUTES" ]; then
    log "Removing wrong default route via $WIFI_IFACE..."
    ip route del default dev $WIFI_IFACE 2>/dev/null
fi

# 5. Make sure default route goes through $ETH_IFACE (the real internet interface)
if [ -n "$ETH_IFACE" ]; then
    DEFAULT_ROUTE=$(ip route show default dev "$ETH_IFACE" 2>/dev/null | head -1)
    if [ -z "$DEFAULT_ROUTE" ]; then
        # lost its default route — try to get it back via DHCP
        log "No default route via $ETH_IFACE — requesting DHCP..."
        dhclient "$ETH_IFACE" 2>/dev/null &
        sleep 3
    fi
else
    log "Warning: No ethernet interface found."
fi

log "Current default routes:"
ip route show default | tee -a /var/log/brgy_network.log

# 6. Enable IP forwarding (for internet sharing to WiFi clients)
echo 1 > /proc/sys/net/ipv4/ip_forward

# 7. Set up iptables NAT (internet sharing from ETH_IFACE to wlan0)
if [ -n "$ETH_IFACE" ]; then
    iptables -t nat -F
    iptables -F FORWARD
    iptables -t nat -A POSTROUTING -o $ETH_IFACE -j MASQUERADE
    iptables -A FORWARD -i $ETH_IFACE -o $WIFI_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i $WIFI_IFACE -o $ETH_IFACE -j ACCEPT
    log "iptables NAT rules applied using $ETH_IFACE."
fi

# 8. Force-release wlan0 from NetworkManager, then restart hostapd and dnsmasq
log "Releasing wlan0 from NetworkManager..."
nmcli dev set $WIFI_IFACE managed no 2>/dev/null || true
sleep 2

systemctl restart dnsmasq
sleep 1
# Give hostapd a clean start
systemctl stop hostapd 2>/dev/null
sleep 2
systemctl start hostapd
sleep 3

HOSTAPD_STATUS=$(systemctl is-active hostapd)
log "hostapd status: $HOSTAPD_STATUS"

if [ "$HOSTAPD_STATUS" = "active" ]; then
    log "=== SUCCESS: Barangay_System_WiFi is broadcasting ==="
else
    log "=== ERROR: hostapd failed to start. Check: journalctl -u hostapd ==="
fi
