# OneCloud Cluster 项目问题检测报告

> 检测时间：2026-08-23
> 检测范围：全项目（scripts/、panel/、inventory/、node-*/、docs/）
> 检测方式：静态代码审查 + 配置一致性比对

---

## 一、问题统计

| 严重级别 | 数量 | 说明 |
|---------|------|------|
| 🔴 严重 | 4  | 安全风险、语法错误，可能导致功能失效或被攻击 |
| 🟡 中等 | 11 | 配置不一致、缺失检查，影响可维护性 |
| 🟢 轻微 | 7  | 命名/风格问题，不影响运行 |

---

## 二、🔴 严重问题（建议立即修复）

### S1. panel/app.py — 无认证的远程命令执行接口

- **文件**：[panel/app.py](file:///d:/TRAE_APPS/oneclound_ws1608/panel/app.py) 第 187-205 行
- **问题**：`/api/exec` 接口允许在任意节点执行任意 shell 命令，且面板无任何认证机制。任何能访问 9000 端口的人均可远程执行命令。
- **风险**：攻击者可绕过危险命令黑名单（如使用 `find . -exec rm -rf {} \;`、`; rm -rf /`、Base64 编码等方式）。
- **修改建议**：
  1. 为面板添加 Basic Auth 或 Token 认证（Flask-HTTPAuth）
  2. 将危险命令过滤改为**白名单**机制，只允许预定义的安全命令
  3. 添加操作审计日志
  ```python
  from flask_httpauth import HTTPBasicAuth
  auth = HTTPBasicAuth()
  
  @auth.verify_password
  def verify_password(username, password):
      return username == os.environ.get("PANEL_USER", "admin") and \
             password == os.environ.get("PANEL_PASS", "changeme")
  
  @app.route("/api/exec", methods=["POST"])
  @auth.login_required
  def exec_command():
      ...
  ```

### S2. install-services.sh — mihomo 版本日志语法错误

- **文件**：[scripts/install-services.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/install-services.sh) 第 51 行
- **问题**：括号不匹配，存在多余的 `)`：
  ```bash
  log_info "mihomo 版本: $(which mihomo) -v 2>&1 | head -1 || echo 'ok')"
  ```
  `$(which mihomo)` 已闭合，后面的 `-v 2>&1 | head -1 || echo 'ok')` 多了一个 `)`，导致命令替换范围错误。
- **修改建议**：
  ```bash
  log_info "mihomo 版本: $(mihomo -v 2>&1 | head -1 || echo 'unknown')"
  ```

### S3. bootstrap.sh — 未安装 Docker 却尝试迁移

- **文件**：[scripts/bootstrap.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/bootstrap.sh) 第 65-68 行、第 109-137 行
- **问题**：第 65-68 行的 `apt install` 安装了 `wireguard-tools wireguard-dkms` 等基础工具，但**没有安装 Docker**。然而第 109-137 行却执行 Docker 数据迁移逻辑，会因 Docker 不存在而失败或产生无效配置。
- **修改建议**：
  ```bash
  # 在第 5 步 apt install 后添加 Docker 安装
  log_info "安装 Docker..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable --now docker
  apt-mark hold docker.io  # 锁定版本
  ```

### S4. bootstrap.sh — hosts 文件包含不存在的节点

- **文件**：[scripts/bootstrap.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/bootstrap.sh) 第 181 行
- **问题**：
  ```bash
  192.168.1.104  wk-backup-04 backup-04.lan
  ```
  集群只有 3 个节点（wk-edge-01、wk-iot-02、wk-storage-03），但 hosts 配置中包含不存在的 `wk-backup-04`，与 inventory/nodes.yaml 不一致。
- **修改建议**：删除第 181 行，或改为由变量驱动：
  ```bash
  cat >> /etc/hosts << EOF
  192.168.1.101  wk-edge-01 edge-01.lan
  192.168.1.102  wk-iot-02 iot-02.lan
  192.168.1.103  wk-storage-03 storage-03.lan
  EOF
  ```

---

## 三、🟡 中等问题（影响一致性/可维护性）

### M1. nodes.yaml — services 列表缺少 ariang

- **文件**：[inventory/nodes.yaml](file:///d:/TRAE_APPS/oneclound_ws1608/inventory/nodes.yaml) 第 45 行
- **问题**：
  ```yaml
  services: [syncthing, verysync, aria2, cupsd, cups-web]
  ```
  缺少 `ariang` 服务。而 [services.yaml](file:///d:/TRAE_APPS/oneclound_ws1608/inventory/services.yaml) 和 [panel/config.json](file:///d:/TRAE_APPS/oneclound_ws1608/panel/config.json) 中均已包含 ariang。
- **修改建议**：
  ```yaml
  services: [syncthing, verysync, aria2, ariang, cupsd, cups-web]
  ```

### M2. health-check.sh — 缺少 ariang/clash/panel 的检查

- **文件**：[scripts/health-check.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/health-check.sh)
- **问题**：未检查以下已注册服务：
  - `ariang`（端口 6880，wk-storage-03）
  - `clash/mihomo`（端口 9090，wk-edge-01）
  - `panel`（端口 9000，wk-edge-01）
- **修改建议**：在对应节点检查段添加：
  ```bash
  # NODE-01 末尾添加
  check_port 192.168.1.101 9090 "Clash API"
  check_port 192.168.1.101 9000 "Panel"
  
  # NODE-03 末尾添加
  check_container 192.168.1.103 "AriaNg" "ariang"
  check_port 192.168.1.103 6880 "AriaNg Web"
  ```

### M3. Home Assistant 镜像不一致

- **涉及文件**：
  - [scripts/setup.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/setup.sh) install_homeassistant：`ghcr.io/home-assistant/home-assistant:stable`
  - [inventory/services.yaml](file:///d:/TRAE_APPS/oneclound_ws1608/inventory/services.yaml) 第 83 行：`ghcr.io/adyoull/ha-armv7:latest`
  - [node-wk-iot-02/docker-compose.yml](file:///d:/TRAE_APPS/oneclound_ws1608/node-wk-iot-02/docker-compose.yml) 第 5 行：`${HA_IMAGE}`
- **问题**：三处定义使用了三个不同的镜像。玩客云是 ARMv7 架构，官方 `home-assistant:stable` 可能没有 armv7 tag。
- **修改建议**：统一使用一个镜像并写入 .env.example：
  ```bash
  # .env.example
  HA_IMAGE=ghcr.io/adyoull/ha-armv7:latest
  ```
  setup.sh 中也改为读取环境变量或使用同一镜像。

### M4. CUPS 镜像不一致

- **涉及文件**：
  - [scripts/setup.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/setup.sh) install_cupsd：主用 `olbat/cupsd:latest`，备选 `ousia/cupsd:armhf`
  - [node-wk-storage-03/docker-compose.yml](file:///d:/TRAE_APPS/oneclound_ws1608/node-wk-storage-03/docker-compose.yml) 第 75 行：`ousia/cupsd:armhf`
  - [inventory/services.yaml](file:///d:/TRAE_APPS/oneclound_ws1608/inventory/services.yaml) 第 168 行：`ousia/cupsd:armhf`
- **修改建议**：setup.sh 中统一使用 `ousia/cupsd:armhf`：
  ```bash
  docker run -d --name cupsd \
      --restart unless-stopped \
      -p 631:631 \
      -e TZ=$TZ \
      -e ADMIN_USER="$cups_user" \
      -e ADMIN_PASSWORD="$cups_pass" \
      -v "${DATA_DIR}/cupsd/config:/etc/cups" \
      ousia/cupsd:armhf
  ```

### M5. cups-web 端口映射不一致

- **涉及文件**：
  - [node-wk-storage-03/docker-compose.yml](file:///d:/TRAE_APPS/oneclound_ws1608/node-wk-storage-03/docker-compose.yml) 第 108 行：`"632:80"`（容器内 80）
  - [scripts/setup.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/setup.sh) install_cups_web：`-p 632:632`（容器内 632）
- **问题**：docker-compose 映射到容器 80 端口，setup.sh 映射到容器 632 端口。若镜像监听 80，setup.sh 的映射会失效。
- **修改建议**：统一为 `-p 632:80`。

### M6. 角色命名不一致

- **涉及文件**：
  - [inventory/nodes.yaml](file:///d:/TRAE_APPS/oneclound_ws1608/inventory/nodes.yaml)：`role: edge-gateway` / `iot-core` / `storage-sync`
  - [panel/config.json](file:///d:/TRAE_APPS/oneclound_ws1608/panel/config.json)：`role: edge` / `iot` / `storage`
- **修改建议**：统一使用一种命名风格，推荐使用 panel/config.json 的简短形式，并更新 nodes.yaml：
  ```yaml
  role: edge      # 而非 edge-gateway
  role: iot        # 而非 iot-core
  role: storage    # 而非 storage-sync
  ```

### M7. cloudflared command 缺少 --no-autoupdate

- **文件**：[node-wk-edge-01/docker-compose.yml](file:///d:/TRAE_APPS/oneclound_ws1608/node-wk-edge-01/docker-compose.yml) 第 9 行
- **问题**：
  ```yaml
  command: tunnel run
  ```
  缺少 `--no-autoupdate` 参数，容器会自动更新可能导致不稳定。而 setup.sh 中正确使用了 `tunnel --no-autoupdate run`。
- **修改建议**：
  ```yaml
  command: tunnel --no-autoupdate run
  ```

### M8. memos 端口变量化不彻底

- **文件**：[node-wk-edge-01/docker-compose.yml](file:///d:/TRAE_APPS/oneclound_ws1608/node-wk-edge-01/docker-compose.yml) 第 78-81 行
- **问题**：
  ```yaml
  environment:
    - MEMOS_PORT=${MEMOS_PORT}    # 使用变量
  ports:
    - "5230:5230"                 # 硬编码，不跟随变量
  ```
- **修改建议**：
  ```yaml
  ports:
    - "${MEMOS_PORT}:${MEMOS_PORT}"
  ```

### M9. wireguard-setup.sh — 结尾变量引用错误

- **文件**：[scripts/wireguard-setup.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/wireguard-setup.sh) 第 124 行
- **问题**：
  ```bash
  log_warn "  1. 将 ${NAME}-wg0.conf 复制到对应节点 /etc/wireguard/wg0.conf"
  ```
  `${NAME}` 此时为循环最后一次的值（wk-storage-03），提示信息会产生误导，让用户以为只处理 storage-03 的配置。
- **修改建议**：
  ```bash
  log_warn "  1. 将各节点的 *-wg0.conf 复制到对应节点 /etc/wireguard/wg0.conf"
  ```

### M10. backup.sh — config 类型备份通配符路径问题

- **文件**：[scripts/backup.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/backup.sh) 第 93-96 行
- **问题**：
  ```bash
  backup_remote $NODE_IP "/mnt/sd/srv/*/docker-compose.yml" "config-$NODE_IP" "docker-compose"
  ```
  `backup_remote` 函数内执行 `ssh "test -e $REMOTE_PATH"`，通配符 `*` 在 `test -e` 中不会被展开，导致检查始终失败并跳过备份。
- **修改建议**：对通配符路径使用 `ls` 或 `compgen` 检查：
  ```bash
  backup_remote() {
      ...
      if ssh -o ConnectTimeout=5 "root@${NODE_IP}" "ls $REMOTE_PATH >/dev/null 2>&1"; then
          ...
  ```

### M11. install-services.sh — cd 后未返回原目录

- **文件**：[scripts/install-services.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/install-services.sh) 第 112-129 行
- **问题**：`start_edge`/`start_iot`/`start_storage` 函数执行 `cd /mnt/sd/srv/wk-edge-01` 后不返回。配合 `set -euo pipefail`，若 `docker-compose up -d` 失败会直接退出脚本，后续函数无法执行。
- **修改建议**：使用子 shell 或 pushd/popd：
  ```bash
  start_edge() {
      log_info "启动 NODE-01 Docker 服务..."
      (cd /mnt/sd/srv/wk-edge-01 && docker-compose up -d)
      docker ps --format "table {{.Names}}\t{{.Status}}"
  }
  ```

---

## 四、🟢 轻微问题（建议优化）

### L1. docker-compose version 字段已弃用

- **文件**：三个 docker-compose.yml 均使用 `version: "3.8"`
- **说明**：Docker Compose V2 已弃用 version 字段，可安全删除该行。
- **修改建议**：删除 `version: "3.8"` 行。

### L2. deploy.sh — NODE_ROLE 变量命名误导

- **文件**：[scripts/deploy.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/deploy.sh) 第 71 行
- **问题**：第三字段实际是节点名（如 wk-edge-01），但变量名为 `NODE_ROLE`。
- **修改建议**：重命名为 `NODE_SUFFIX` 或 `NODE_DIR_NAME`。

### L3. panel/install-service.sh — 变量名误导

- **文件**：[panel/install-service.sh](file:///d:/TRAE_APPS/oneclound_ws1608/panel/install-service.sh) 第 7 行
- **问题**：`PANEL_SERVICE` 实际指向 config.json，并非服务。
- **修改建议**：重命名为 `PANEL_CONFIG`。

### L4. panel/app.py — 危险命令过滤可被绕过

- **文件**：[panel/app.py](file:///d:/TRAE_APPS/oneclound_ws1608/panel/app.py) 第 199-202 行
- **问题**：黑名单方式可被绕过，例如 `rm  -rf`（多空格）、`rm -r -f`、`find / -delete` 等。
- **修改建议**：见 S1，建议改为白名单机制。

### L5. bootstrap.sh — 分区创建后缺少 partprobe

- **文件**：[scripts/bootstrap.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/bootstrap.sh) 第 97-100 行
- **问题**：`parted mkpart` 后直接 `mkfs.ext4`，部分系统内核未及时识别新分区。
- **修改建议**：在 `parted` 后添加：
  ```bash
  partprobe "$SD_PATH" 2>/dev/null || true
  sleep 2
  ```

### L6. node-wk-iot-02 — HA_ALLOWED_HOSTS 非标准变量

- **文件**：[node-wk-iot-02/docker-compose.yml](file:///d:/TRAE_APPS/oneclound_ws1608/node-wk-iot-02/docker-compose.yml) 第 14 行
- **问题**：`ALLOWED_HOSTS` 并非 Home Assistant 官方支持的环境变量，配置无效。
- **修改建议**：删除该行，改为在 HA 的 `configuration.yaml` 中配置 `http.use_x_forwarded_for`。

### L7. setup.sh — xiaomusic 解压路径假设

- **文件**：[scripts/setup.sh](file:///d:/TRAE_APPS/oneclound_ws1608/scripts/setup.sh) install_xiaomusic
- **问题**：`tar xz -C /tmp` 后直接 `mv /tmp/xiaomusic`，假定压缩包内顶层文件名为 `xiaomusic`。若实际结构不同会失败。
- **修改建议**：解压后用 `find` 定位二进制：
  ```bash
  curl -sL "$url" | tar xz -C /tmp
  BIN_PATH=$(find /tmp -name "xiaomusic" -type f | head -1)
  [ -n "$BIN_PATH" ] && mv "$BIN_PATH" /usr/local/bin/
  ```

---

## 五、修复优先级建议

| 优先级 | 问题编号 | 建议修复时间 |
|--------|---------|-------------|
| P0 紧急 | S1（无认证远程执行） | 立即 |
| P1 高 | S2、S3、S4 | 1 天内 |
| P2 中 | M1-M11 | 1 周内 |
| P3 低 | L1-L7 | 下次迭代 |

---

## 六、总结

项目整体结构清晰、模块化程度高，运维脚本功能完善。主要问题集中在：

1. **安全层面**：控制面板缺少认证（S1），是最需要优先处理的问题
2. **一致性层面**：镜像名、端口、角色命名在多文件间不统一（M3-M8）
3. **健壮性层面**：部分脚本缺少错误处理和路径检查（S2、M10、M11）

建议按优先级逐步修复，并在修复后重新运行 `test_validate.py` 验证。

---

*报告生成工具：静态代码审查 · GLM-5.2*
