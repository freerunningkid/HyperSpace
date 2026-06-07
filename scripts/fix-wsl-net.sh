#!/bin/bash
# 永久修复 WSL DNS + IPv6

# DNS
echo -e "nameserver 8.8.8.8\nnameserver 223.5.5.5" | sudo tee /etc/resolv.conf > /dev/null

# IPv6 持久禁用
if ! grep -q "disable_ipv6" /etc/sysctl.conf 2>/dev/null; then
    echo "net.ipv6.conf.all.disable_ipv6 = 1" | sudo tee -a /etc/sysctl.conf > /dev/null
    echo "net.ipv6.conf.default.disable_ipv6 = 1" | sudo tee -a /etc/sysctl.conf > /dev/null
fi
sudo sysctl -p > /dev/null 2>&1

echo "=== DNS ==="
cat /etc/resolv.conf
echo "=== IPv6 ==="
sysctl net.ipv6.conf.all.disable_ipv6
echo "=== Test GitHub ==="
curl -4 -s --connect-timeout 10 -o /dev/null -w 'HTTP: %{http_code}\n' https://github.com
echo "=== Test raw ==="
curl -4 -s --connect-timeout 10 -o /dev/null -w 'HTTP: %{http_code}\n' https://raw.githubusercontent.com
