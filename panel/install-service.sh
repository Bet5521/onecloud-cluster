#!/bin/bash
# OneCloud Cluster Panel - systemd 服务
# 复制到 /etc/systemd/system/ 后启用

cat > /etc/systemd/system/onecloud-panel.service << 'EOF'
[Unit]
Description=OneCloud Cluster Control Panel
After=network.target

[Service]
Type=simple
WorkingDirectory=/mnt/sd/edge-01/panel
ExecStart=/usr/bin/python3 /mnt/sd/edge-01/panel/app.py
Restart=on-failure
RestartSec=5
Environment=PANEL_CONFIG=/mnt/sd/edge-01/panel/config.json
Environment=PANEL_PORT=9000
Environment=PANEL_HOST=0.0.0.0
LimitNOFILE=4096
MemoryMax=128M

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable onecloud-panel
systemctl start onecloud-panel

echo "[✓] Panel service 已启动"
echo "    访问: http://$(hostname -I | awk '{print $1}'):9000"
