#!/bin/bash
# verysync (微力同步) 安装脚本
# 微力同步提供了 ARM Linux 版本

VSYNC_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$VSYNC_DIR/temp"

# verysync 官方下载地址 (ARMv7 / armhf)
# 注意: 微力同步可能需要从官网手动下载
# https://www.verysync.com/

echo "[*] verysync 安装说明:"
echo ""
echo "方式 1: 手动下载 (推荐)"
echo "  1. 访问 https://www.verysync.com/download"
echo "  2. 下载 'Linux - ARM' 版本 (.tar.gz)"
echo "  3. 解压: tar xzf verysync-linux-arm.tar.gz"
echo "  4. 复制二进制: cp verysync /usr/local/bin/"
echo "  5. 启动: verysync -c ${VSYNC_DIR}/config.yaml"
echo ""
echo "方式 2: 命令行下载 (如果有直接链接)"
echo "  URL=\"https://www.verysync.com/static/download/verysync-linux-arm.tar.gz\""
echo "  curl -sL \$URL | tar xz -C /tmp"
echo "  cp /tmp/verysync /usr/local/bin/"
echo ""

# 自动检测是否已安装
if command -v verysync &>/dev/null; then
    echo "[✓] verysync 已安装"
    verysync --version 2>&1 || echo "version check not supported"
else
    echo "[!] verysync 未安装, 请使用上面的方式安装"
fi
