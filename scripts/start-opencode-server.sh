#!/bin/bash
# ============================================================
# OpenCode WSL Server 启动脚本
# 用法：在 WSL 内运行：bash start-opencode-server.sh
# ============================================================

PASSWORD=${OPENCODE_SERVER_PASSWORD:-"opencode-kid2025"}
PORT=${OPENCODE_SERVER_PORT:-4096}

echo "========================================"
echo "  OpenCode WSL Server"
echo "========================================"
echo ""

# 确保 IPv6 已禁用（避免网络问题）
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1 > /dev/null 2>&1

# 获取 WSL IP
WSL_IP=$(hostname -I | awk '{print $1}')
echo "  WSL IP:    $WSL_IP"
echo "  Port:      $PORT"
echo "  Password:  $PASSWORD"
echo ""
echo "  桌面应用连接地址:  http://${WSL_IP}:${PORT}"
echo "  本地连接地址:      http://localhost:${PORT}"
echo "========================================"
echo ""

# 启动服务器
OPENCODE_SERVER_PASSWORD="$PASSWORD" opencode serve --hostname 0.0.0.0 --port "$PORT"
