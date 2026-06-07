#!/bin/bash
# 获取 GitHub 的真实 IP 并写入 WSL hosts
echo "Fetching real IPs via Cloudflare DNS..."

GITHUB_IP=$(curl -4 -s 'https://1.1.1.1/dns-query?name=github.com&type=A' -H 'accept: application/dns-json' | python3 -c "import sys,json; d=json.load(sys.stdin); [print(a['data']) for a in d.get('Answer',[]) if a.get('type')==1]" 2>/dev/null | head -1)
RAW_IP=$(curl -4 -s 'https://1.1.1.1/dns-query?name=raw.githubusercontent.com&type=A' -H 'accept: application/dns-json' | python3 -c "import sys,json; d=json.load(sys.stdin); [print(a['data']) for a in d.get('Answer',[]) if a.get('type')==1]" 2>/dev/null | head -1)
OBJ_IP=$(curl -4 -s 'https://1.1.1.1/dns-query?name=objects.githubusercontent.com&type=A' -H 'accept: application/dns-json' | python3 -c "import sys,json; d=json.load(sys.stdin); [print(a['data']) for a in d.get('Answer',[]) if a.get('type')==1]" 2>/dev/null | head -1)

echo "github.com: $GITHUB_IP"
echo "raw.githubusercontent.com: $RAW_IP"
echo "objects.githubusercontent.com: $OBJ_IP"

# Add to /etc/hosts in WSL
sudo sed -i '/github/d' /etc/hosts 2>/dev/null
echo "$GITHUB_IP github.com" | sudo tee -a /etc/hosts
echo "$RAW_IP raw.githubusercontent.com" | sudo tee -a /etc/hosts  
echo "$OBJ_IP objects.githubusercontent.com" | sudo tee -a /etc/hosts

echo "---"
echo "WSL hosts updated. Testing..."
curl -4 -s -o /dev/null -w 'github.com: %{http_code} %{time_total}s\n' --connect-timeout 5 https://github.com
curl -4 -s -o /dev/null -w 'raw: %{http_code} %{time_total}s\n' --connect-timeout 5 https://raw.githubusercontent.com
