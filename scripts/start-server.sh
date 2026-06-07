#!/bin/bash
# Kill old server
pkill -f "opencode serve" 2>/dev/null
sleep 1

# Start server
nohup env OPENCODE_SERVER_PASSWORD=opencode-kid2025 \
    $HOME/.opencode/bin/opencode serve \
    --hostname 0.0.0.0 \
    --port 4096 \
    > /tmp/opencode-server.log 2>&1 &

sleep 3

# Verify
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4096 2>/dev/null)
echo "Server: HTTP $code"
echo "IP: $(hostname -I | awk '{print $1}'):4096"
echo "Password: opencode-kid2025"
