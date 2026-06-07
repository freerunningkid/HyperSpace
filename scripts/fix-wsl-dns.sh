#!/bin/bash
cat > /etc/wsl.conf << 'EOF'
[network]
generateResolvConf = false
EOF

cat > /etc/resolv.conf << 'EOF'
nameserver 8.8.8.8
nameserver 223.5.5.5
EOF

echo "DNS fixed:"
cat /etc/resolv.conf
echo "---"
curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 https://raw.githubusercontent.com && echo "GitHub OK" || echo "GitHub FAILED"
