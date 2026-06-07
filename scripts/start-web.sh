#!/bin/bash
pkill -f "opencode" 2>/dev/null
sleep 1
OPENCODE_SERVER_PASSWORD=opencode-kid2025 \
    nohup $HOME/.opencode/bin/opencode web \
    --hostname 0.0.0.0 \
    --port 4096 \
    > /tmp/oweb.log 2>&1 &
sleep 4
cat /tmp/oweb.log
