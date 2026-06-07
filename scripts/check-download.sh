#!/bin/bash
# 检查下载进度
LINUX="/tmp/opencode-linux-x64.tar.gz"
DESKTOP="/mnt/d/临时/opencode-desktop-win-x64.exe"

echo "=== $(date '+%H:%M:%S') ==="
for f in "$LINUX" "$DESKTOP"; do
    if [ -f "$f" ]; then
        sz=$(stat -c%s "$f" 2>/dev/null)
        mb=$(echo "scale=1; $sz/1048576" | bc 2>/dev/null || echo "?")
        name=$(basename "$f")
        echo "  $name: ${mb}MB"
    else
        echo "  $(basename $f): not started"
    fi
done

# 检查 wget 进程
if ps aux | grep -q '[w]get.*opencode'; then
    echo "  Status: 下载中..."
else
    echo "  Status: 无活动下载"
    # 检查是否已完成
    if [ -f "$LINUX" ] && [ $(stat -c%s "$LINUX") -gt 45000000 ]; then
        echo "  ✓ Linux CLI 下载完成！"
    fi
    if [ -f "$DESKTOP" ] && [ $(stat -c%s "$DESKTOP") -gt 100000000 ]; then
        echo "  ✓ Desktop 下载完成！"
    fi
fi
