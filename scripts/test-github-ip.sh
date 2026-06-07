#!/bin/bash
for ip in 140.82.112.4 140.82.113.4 140.82.114.4 20.205.243.166 20.207.73.82 140.82.121.3 140.82.118.4; do
    code=$(curl -4 -k -s -H 'Host: github.com' -o /dev/null -w '%{http_code}' --connect-timeout 3 "https://$ip/" 2>/dev/null)
    echo "$ip: $code"
    if [ "$code" = "301" ] || [ "$code" = "200" ]; then
        echo "FOUND WORKING IP: $ip"
        sudo sed -i '/github.com/d' /etc/hosts
        echo "$ip github.com" | sudo tee -a /etc/hosts
        break
    fi
done
