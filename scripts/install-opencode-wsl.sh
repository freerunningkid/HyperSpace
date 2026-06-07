#!/bin/bash
# ============================================================
# OpenCode WSL 手动安装脚本
# 前置：/tmp/opencode-linux-x64.tar.gz 已下载完毕
# ============================================================

set -e

TARBALL="/tmp/opencode-linux-x64.tar.gz"
INSTALL_DIR="$HOME/.opencode/bin"

if [ ! -f "$TARBALL" ]; then
    echo "ERROR: $TARBALL 不存在，请先下载"
    exit 1
fi

echo "安装 OpenCode CLI 到 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"

# 解压
TMPDIR=$(mktemp -d)
tar -xzf "$TARBALL" -C "$TMPDIR"
mv "$TMPDIR/opencode" "$INSTALL_DIR/opencode"
chmod 755 "$INSTALL_DIR/opencode"
rm -rf "$TMPDIR" "$TARBALL"

# 添加到 PATH
if ! grep -q '.opencode/bin' ~/.bashrc 2>/dev/null; then
    echo '' >> ~/.bashrc
    echo '# OpenCode' >> ~/.bashrc
    echo 'export PATH=$HOME/.opencode/bin:$PATH' >> ~/.bashrc
fi

# 立即生效
export PATH="$INSTALL_DIR:$PATH"

echo ""
echo "=========================================="
echo "  OpenCode 安装完成！"
echo "  Version: $($INSTALL_DIR/opencode --version)"
echo "  路径:    $INSTALL_DIR/opencode"
echo "=========================================="
echo ""
echo "下次启动 shell 时 PATH 自动生效，或执行："
echo "  source ~/.bashrc"
