#!/bin/bash
# WireGuard 密钥生成脚本
# 运行一次生成 server 密钥和 peer 配置

WG_DIR="$(dirname "$0")/config"
mkdir -p "$WG_DIR"

cd "$WG_DIR"

echo "[*] 生成 WireGuard Server 密钥..."
if [ ! -f server_private.key ]; then
    wg genkey > server_private.key
    chmod 600 server_private.key
    wg pubkey < server_private.key > server_public.key
    chmod 600 server_public.key
    echo "Server Public Key:  $(cat server_public.key)"
else
    echo "[!] Server 密钥已存在, 跳过"
fi

echo "[*] 生成 Peer 密钥..."
for peer in 01 02 03; do
    if [ ! -f "peer${peer}_private.key" ]; then
        wg genkey > "peer${peer}_private.key"
        chmod 600 "peer${peer}_private.key"
        wg pubkey < "peer${peer}_private.key" > "peer${peer}_public.key"
        chmod 600 "peer${peer}_public.key"
        echo "Peer${peer} Public:  $(cat peer${peer}_public.key)"
    fi
done

echo "[*] 生成 wg0.conf..."
cat > wg0.conf << EOF
[Interface]
Address = 10.8.0.101/32
ListenPort = 51820
PrivateKey = $(cat server_private.key)

# DNS 路由到 AdGuard
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# 允许 WireGuard 入站
PostUp = iptables -A INPUT -p udp --dport 51820 -j ACCEPT
PostDown = iptables -D INPUT -p udp --dport 51820 -j ACCEPT

EOF

echo "[✓] WireGuard 密钥和基础配置已生成在 $WG_DIR"
echo ""
echo "请将各 peer 的 Public Key 填入其他节点的 wg0.conf"