#!/bin/bash
# ============================================================
# OpenCode 完整安装脚本 (WSL)
# 1. 下载 Linux CLI 包
# 2. 下载 Windows Desktop 包（保存到 Windows 临时目录）
# 3. 安装 Linux CLI
# 4. 写入进度日志
# ============================================================

set -e

LOG="/tmp/opencode-install-progress.log"
INSTALL_DIR="$HOME/.opencode/bin"
LINUX_URL="https://github.com/anomalyco/opencode/releases/download/v1.15.13/opencode-linux-x64.tar.gz"
DESKTOP_URL="https://github.com/anomalyco/opencode/releases/download/v1.15.13/opencode-desktop-win-x64.exe"
LINUX_OUT="/tmp/opencode-linux-x64.tar.gz"
DESKTOP_OUT="/mnt/d/临时/opencode-desktop-win-x64.exe"

echo "$(date '+%H:%M:%S') 开始下载..." | tee "$LOG"

# 下载 Linux CLI
echo "$(date '+%H:%M:%S') 下载 Linux CLI 包..." | tee -a "$LOG"
curl -4 -L -o "$LINUX_OUT" --connect-timeout 30 --retry 3 --max-time 1800 \
    -w "\n$(date '+%H:%M:%S') Linux CLI 下载完成: %{size_download} bytes, %{time_total}s\n" \
    "$LINUX_URL" 2>&1 | tee -a "$LOG"

LINUX_SIZE=$(stat -c%s "$LINUX_OUT" 2>/dev/null || echo 0)
echo "$(date '+%H:%M:%S') Linux: ${LINUX_SIZE} bytes" | tee -a "$LOG"

# 下载 Desktop App
echo "$(date '+%H:%M:%S') 下载 Desktop App..." | tee -a "$LOG"
curl -4 -L -o "$DESKTOP_OUT" --connect-timeout 30 --retry 3 --max-time 3600 \
    -w "\n$(date '+%H:%M:%S') Desktop 下载完成: %{size_download} bytes, %{time_total}s\n" \
    "$DESKTOP_URL" 2>&1 | tee -a "$LOG"

DESKTOP_SIZE=$(stat -c%s "$DESKTOP_OUT" 2>/dev/null || echo 0)
echo "$(date '+%H:%M:%S') Desktop: ${DESKTOP_SIZE} bytes" | tee -a "$LOG"

# 安装 Linux CLI
echo "$(date '+%H:%M:%S') 安装 OpenCode CLI..." | tee -a "$LOG"
mkdir -p "$INSTALL_DIR"
TMPDIR=$(mktemp -d)
tar -xzf "$LINUX_OUT" -C "$TMPDIR"
mv "$TMPDIR/opencode" "$INSTALL_DIR/opencode"
chmod 755 "$INSTALL_DIR/opencode"
rm -rf "$TMPDIR" "$LINUX_OUT"

# PATH
if ! grep -q '.opencode/bin' ~/.bashrc 2>/dev/null; then
    echo '' >> ~/.bashrc
    echo '# OpenCode' >> ~/.bashrc
    echo 'export PATH=$HOME/.opencode/bin:$PATH' >> ~/.bashrc
fi

export PATH="$INSTALL_DIR:$PATH"
VERSION=$($INSTALL_DIR/opencode --version 2>&1 || echo "unknown")
echo "$(date '+%H:%M:%S') ✓ 全部完成！" | tee -a "$LOG"
echo "  CLI: $VERSION" | tee -a "$LOG"
echo "  CLI: $INSTALL_DIR/opencode" | tee -a "$LOG"
echo "  Desktop: D:\\临时\\opencode-desktop-win-x64.exe" | tee -a "$LOG"
