#!/bin/bash
# migpt 安装脚本
# migpt 可能有多种部署方式, 这里提供通用方案

MIGPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$MIGPT_DIR"

echo "[*] migpt 安装提示:"
echo ""
echo "方案 1: 原生 Go 构建 (如果有 armv7 release)"
echo "  从 https://github.com/BytePioneer/migpt 下载 armv7 二进制"
echo "  放到 /usr/local/bin/migpt"
echo ""
echo "方案 2: Python 包 (轻量替代)"
echo "  pip3 install migpt"
echo "  然后 systemd 运行 python3 -m migpt"
echo ""
echo "方案 3: 使用 API 代理 (最简单)"
echo "  用 Flask + requests 写一个简单代理"
echo "  见本目录 proxy.py"
echo ""

# 检查是否已安装
if command -v migpt &>/dev/null; then
    echo "[*] migpt 已安装: $(migpt -v 2>&1 || echo 'unknown version')"
else
    echo "[!] migpt 未安装, 请选择上面的方案"
fi
