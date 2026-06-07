#!/bin/bash
# 一键添加所有 GitHub 相关域名的可用 IP 到 WSL hosts

echo "=== Fixing GitHub hosts ==="

# 清理旧条目
sed -i '/github/d' /etc/hosts

# raw.githubusercontent.com — 已验证 185.199.108.133
echo "185.199.108.133 raw.githubusercontent.com" >> /etc/hosts

# objects.githubusercontent.com — 同 CDN
echo "185.199.108.133 objects.githubusercontent.com" >> /etc/hosts

# github.com — 已验证 140.82.112.4  
echo "140.82.112.4 github.com" >> /etc/hosts

# api.github.com — 同样网段
echo "140.82.112.4 api.github.com" >> /etc/hosts

# camo, avatars 等
for host in github.githubassets.com avatars.githubusercontent.com user-images.githubusercontent.com; do
    echo "185.199.108.133 $host" >> /etc/hosts
done

echo "Hosts updated:"
grep -i github /etc/hosts

echo "=== Testing ==="
curl -4 -s -o /dev/null -w 'github.com: %{http_code} %{time_total}s\n' --connect-timeout 8 https://github.com
curl -4 -s -o /dev/null -w 'raw: %{http_code} %{time_total}s\n' --connect-timeout 8 https://raw.githubusercontent.com
curl -4 -s -o /dev/null -w 'objects: %{http_code} %{time_total}s\n' --connect-timeout 8 https://objects.githubusercontent.com
curl -4 -s -o /dev/null -w 'api: %{http_code} %{time_total}s\n' --connect-timeout 8 https://api.github.com

echo "=== Ready to download ==="
