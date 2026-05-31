#!/bin/bash
cat << 'EOF' > /etc/rc.local
#!/bin/bash
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -o end0 -j MASQUERADE
iptables -A FORWARD -i end0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i wlan0 -o end0 -j ACCEPT
exit 0
EOF
chmod +x /etc/rc.local
/etc/rc.local
echo "Internet routing installed permanently and started!"
