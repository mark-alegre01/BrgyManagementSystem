#!/bin/bash
cat << 'EOF' > /etc/rc.local
#!/bin/bash
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -o end0 -j MASQUERADE
iptables -A FORWARD -i end0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i wlan0 -o end0 -j ACCEPT
rm -f /etc/resolv.conf
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf
systemctl restart dnsmasq
exit 0
EOF
chmod +x /etc/rc.local
/etc/rc.local
echo "Internet routing installed permanently and started!"
