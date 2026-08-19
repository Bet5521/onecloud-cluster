#!/bin/bash
# 下载 mihomo (Clash Meta) 二进制 - ARMv7
# 从 GitHub Releases 获取最新 armv7 版本

MIHOMO_VERSION=$(curl -sL https://api.github.com/repos/MetaCubeX/mihomo/releases/latest \
    | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')

echo "[*] 最新版本: $MIHOMO_VERSION"

URL="https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VERSION}/mihomo-linux-armv7-${MIHOMO_VERSION}.gz"
echo "[*] 下载: $URL"

curl -sL "$URL" | gunzip > /usr/local/bin/mihomo
chmod +x /usr/local/bin/mihomo

echo "[✓] 安装成功: $(/usr/local/bin/mihomo -v)"
