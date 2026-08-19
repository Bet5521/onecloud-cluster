#!/bin/bash
# xiaomusic 安装脚本 - ARMv7 原生二进制
# 从 GitHub Releases 获取

XMUSIC_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$XMUSIC_DIR/downloads" "$XMUSIC_DIR/cache" "$XMUSIC_DIR/session"

# 下载二进制
LATEST=$(curl -sL https://api.github.com/repos/hanxi/xiaomusic/releases/latest \
    | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')

echo "[*] 最新版本: $LATEST"

# 查找 armv7 构建的下载链接
URL=$(curl -sL https://api.github.com/repos/hanxi/xiaomusic/releases/latest \
    | grep "browser_download_url.*linux.*arm" \
    | head -1 | sed -E 's/.*"([^"]+)".*/\1/')

if [ -z "$URL" ]; then
    echo "[!] 未找到 armv7 版本, 请手动下载"
    echo "[*] 访问: https://github.com/hanxi/xiaomusic/releases"
    exit 1
fi

echo "[*] 下载: $URL"
curl -sL "$URL" -o /usr/local/bin/xiaomusic
chmod +x /usr/local/bin/xiaomusic

echo "[✓] xiaomusic 安装成功"
/usr/local/bin/xiaomusic -h 2>&1 | head -5
