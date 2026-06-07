#!/bin/bash
# 测试 objects.githubusercontent.com 可用 IP
for ip in 185.199.108.133 185.199.109.133 185.199.110.133 185.199.111.133; do
    code=$(curl -4 -k -s -H 'Host: objects.githubusercontent.com' -o /dev/null -w '%{http_code}' --connect-timeout 3 "https://$ip/" 2>/dev/null)
    echo "$ip: $code"
    if [ "$code" = "200" ]; then
        echo "FOUND: $ip"
        sed -i '/objects.githubusercontent.com/d' /etc/hosts
        echo "$ip objects.githubusercontent.com" >> /etc/hosts
        exit 0
    fi
done
echo "No working IP for objects"
exit 1
