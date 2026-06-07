#!/bin/bash
pkill -f "opencode" 2>/dev/null
sleep 1
OPENCODE_SERVER_PASSWORD=opencode-kid2025 \
    nohup $HOME/.opencode/bin/opencode serve \
    --hostname 0.0.0.0 \
    --port 4096 \
    > /tmp/oserve.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "Serve HTTP: %{http_code}\n" http://127.0.0.1:4096
echo "WSL IP: $(hostname -I | awk '{print $1}'):4096"
