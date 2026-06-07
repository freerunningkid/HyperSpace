#!/bin/bash
# 硬编码 GitHub 可用 IP（已验证）
RAW_IPS="185.199.108.133 185.199.109.133 185.199.110.133 185.199.111.133"
GITHUB_IPS="140.82.121.4 140.82.112.4 20.205.243.166 140.82.113.4"

sudo sed -i '/github/d' /etc/hosts 2>/dev/null

# 测试并添加 raw IP
for ip in $RAW_IPS; do
    code=$(curl -4 -k -s -H 'Host: raw.githubusercontent.com' -o /dev/null -w '%{http_code}' --connect-timeout 3 "https://$ip/" 2>/dev/null)
    if [ "$code" = "301" ] || [ "$code" = "200" ]; then
        echo "$ip raw.githubusercontent.com" | sudo tee -a /etc/hosts
        echo "raw: $ip OK"
        break
    fi
done

# 测试并添加 github IP  
for ip in $GITHUB_IPS; do
    code=$(curl -4 -k -s -H 'Host: github.com' -o /dev/null -w '%{http_code}' --connect-timeout 3 "https://$ip/" 2>/dev/null)
    if [ "$code" = "301" ] || [ "$code" = "200" ]; then
        echo "$ip github.com" | sudo tee -a /etc/hosts
        echo "github: $ip OK"
        break
    fi
done

echo "=== hosts ==="
grep -i github /etc/hosts
echo "=== Test ==="
curl -4 -s -o /dev/null -w 'github.com: %{http_code} %{time_total}s\n' --connect-timeout 8 https://github.com
curl -4 -s -o /dev/null -w 'raw: %{http_code} %{time_total}s\n' --connect-timeout 8 https://raw.githubusercontent.com
