#!/bin/bash
echo "Testing github.com IPs..."
for ip in 140.82.121.3 140.82.121.4 140.82.112.3 140.82.113.3 140.82.113.4 140.82.114.3 140.82.114.4 140.82.116.4 140.82.118.4 20.200.245.247 20.205.243.166 4.208.26.197; do
    code=$(curl -4 -k -s -H 'Host: github.com' -o /dev/null -w '%{http_code}' --connect-timeout 2 "https://$ip/" 2>/dev/null)
    echo "  $ip: $code"
    if [ "$code" = "301" ] || [ "$code" = "200" ] || [ "$code" = "302" ]; then
        echo "  >>> FOUND: $ip"
    fi
done
