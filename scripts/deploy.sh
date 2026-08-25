#!/bin/bash
# ============================================================
# 配置分发脚本 (deploy.sh)
# 将项目配置 rsync 到各节点
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 默认节点列表
# 格式: 节点名|IP|目录后缀(node-<suffix>)
NODES=(
    "wk-edge-01|192.168.1.101|wk-edge-01"
    "wk-iot-02|192.168.1.102|wk-iot-02"
    "wk-storage-03|192.168.1.103|wk-storage-03"
)

usage() {
    cat << EOF
用法: $0 [选项]

选项:
  -n, --node NAME    指定节点名称 (如 wk-edge-01)
  -a, --all          分发到所有节点 (默认)
  -t, --test         仅测试连接, 不分发
  -d, --dry-run      显示将要传输的内容, 不实际传输
  -h, --help         显示帮助

示例:
  $0                      # 分发所有节点
  $0 -n wk-edge-01        # 仅分发到边缘网关
  $0 -t                   # 测试所有节点 SSH 连接
  $0 -d                   # 预览将传输的文件
EOF
}

DRY_RUN=""
TEST_ONLY=false
TARGET_NODES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--node)  TARGET_NODES+=("$2"); shift 2 ;;
        -a|--all)   TARGET_NODES=(); shift ;;
        -t|--test)  TEST_ONLY=true; shift ;;
        -d|--dry-run) DRY_RUN="--dry-run"; shift ;;
        -h|--help)  usage; exit 0 ;;
        *) log_error "未知选项: $1"; usage; exit 1 ;;
    esac
done

echo ""
echo "=========================================="
echo "  OneCloud Cluster - Config Deploy"
echo "=========================================="
echo ""

deploy_node() {
    local NODE_NAME=$1
    local NODE_IP=$2
    local NODE_ROLE=$3
    local NODE_SRC="${PROJECT_DIR}/node-${NODE_ROLE}"
    local REMOTE_BASE="/mnt/sd/srv/${NODE_NAME}"

    echo "--- $NODE_NAME ($NODE_IP) ---"

    # 测试 SSH 连接
    if ! ssh -o ConnectTimeout=5 "root@${NODE_IP}" "echo ok" &>/dev/null; then
        log_error "无法连接到 $NODE_NAME ($NODE_IP)"
        return 1
    fi
    log_info "SSH 连接成功: $NODE_NAME"

    if [ "$TEST_ONLY" = true ]; then
        return 0
    fi

    # 确保远程目录存在
    ssh "root@${NODE_IP}" "mkdir -p ${REMOTE_BASE}/{cloudflared,adguard/{work,conf},wireguard/config,clash,memos,homeassistant,piwigo/{config,gallery},xiaomusic,migpt,typecho,syncthing/{config,data},verysync,aria2/{config,downloads},cupsd/{config,printers,spool},cups-web,panel,gitea}"

    # 分发配置文件
    if [ -d "$NODE_SRC" ]; then
        log_info "分发 ${NODE_SRC} → ${NODE_IP}:${REMOTE_BASE}"
        rsync -avz $DRY_RUN \
            --exclude '*.bak' --exclude '*.old' \
            --exclude '.git' --exclude '__pycache__' \
            "${NODE_SRC}/" "root@${NODE_IP}:${REMOTE_BASE}/"
    else
        log_warn "本地未找到 $NODE_SRC, 跳过"
    fi

    # 分发脚本和文档到公共位置
    if [ "$DRY_RUN" != "--dry-run" ]; then
        ssh "root@${NODE_IP}" "mkdir -p /mnt/sd/scripts /mnt/sd/docs /mnt/sd/inventory"
        rsync -avz $DRY_RUN "${SCRIPT_DIR}/" "root@${NODE_IP}:/mnt/sd/scripts/"
        rsync -avz $DRY_RUN "${PROJECT_DIR}/docs/" "root@${NODE_IP}:/mnt/sd/docs/"
        rsync -avz $DRY_RUN "${PROJECT_DIR}/inventory/" "root@${NODE_IP}:/mnt/sd/inventory/"
    fi

    log_info "$NODE_NAME 完成 ✓"
    echo ""
}

if [ ${#TARGET_NODES[@]} -eq 0 ]; then
    TARGET_NODES=("${NODES[@]}")
fi

for NODE in "${TARGET_NODES[@]}"; do
    IFS='|' read -r NAME IP ROLE <<< "$NODE"
    deploy_node "$NAME" "$IP" "$ROLE" || true
done

echo "=========================================="
log_info "分发完成"
echo "==========================================\\033[0m'\n\nlog_info() { echo -e \"${GREEN}[INFO]${NC} $*\"; }\nlog_warn() { echo -e \"${YELLOW}[WARN]${NC} $*\"; }\nlog_error() { echo -e \"${RED}[ERROR]${NC} $*\"; }\n\n# \u9ed8\u8ba4\u8282\u70b9\u5217\u8868\n# \u683c\u5f0f: \u8282\u70b9\u540d|IP|\u76ee\u5f55\u540e\u7f00(node-<suffix>)\nNODES=(\n    \"wk-edge-01|192.168.1.101|wk-edge-01\"\n    \"wk-iot-02|192.168.1.102|wk-iot-02\"\n    \"wk-storage-03|192.168.1.103|wk-storage-03\"\n)\n\nusage() {\n    cat << EOF\n\u7528\u6cd5: $0 [\u9009\u9879]\n\n\u9009\u9879:\n  -n, --node NAME    \u6307\u5b9a\u8282\u70b9\u540d\u79f0 (\u5982 wk-edge-01)\n  -a, --all          \u5206\u53d1\u5230\u6240\u6709\u8282\u70b9 (\u9ed8\u8ba4)\n  -t, --test         \u4ec5\u6d4b\u8bd5\u8fde\u63a5, \u4e0d\u5206\u53d1\n  -d, --dry-run      \u663e\u793a\u5c06\u8981\u4f20\u8f93\u7684\u5185\u5bb9, \u4e0d\u5b9e\u9645\u4f20\u8f93\n  -h, --help         \u663e\u793a\u5e2e\u52a9\n\n\u793a\u4f8b:\n  $0                      # \u5206\u53d1\u6240\u6709\u8282\u70b9\n  $0 -n wk-edge-01        # \u4ec5\u5206\u53d1\u5230\u8fb9\u7f18\u7f51\u5173\n  $0 -t                   # \u6d4b\u8bd5\u6240\u6709\u8282\u70b9 SSH \u8fde\u63a5\n  $0 -d                   # \u9884\u89c8\u5c06\u4f20\u8f93\u7684\u6587\u4ef6\nEOF\n}\n\nDRY_RUN=\"\"\nTEST_ONLY=false\nTARGET_NODES=()\n\nwhile [[ $# -gt 0 ]]; do\n    case \"$1\" in\n        -n|--node)  TARGET_NODES+=(\"$2\"); shift 2 ;;\n        -a|--all)   TARGET_NODES=(); shift ;;\n        -t|--test)  TEST_ONLY=true; shift ;;\n        -d|--dry-run) DRY_RUN=\"--dry-run\"; shift ;;\n        -h|--help)  usage; exit 0 ;;\n        *) log_error \"\u672a\u77e5\u9009\u9879: $1\"; usage; exit 1 ;;\n    esac\ndone\n\necho \"\"\necho \"==========================================\"\necho \"  OneCloud Cluster - Config Deploy\"\necho \"==========================================\"\necho \"\"\n\ndeploy_node() {\n    local NODE_NAME=$1\n    local NODE_IP=$2\n    local NODE_ROLE=$3\n    local NODE_SRC=\"${PROJECT_DIR}/node-${NODE_ROLE}\"\n    local REMOTE_BASE=\"/mnt/sd/srv/${NODE_NAME}\"\n\n    echo \"--- $NODE_NAME ($NODE_IP) ---\"\n\n    # \u6d4b\u8bd5 SSH \u8fde\u63a5\n    if ! ssh -o ConnectTimeout=5 \"root@${NODE_IP}\" \"echo ok\" &>/dev/null; then\n        log_error \"\u65e0\u6cd5\u8fde\u63a5\u5230 $NODE_NAME ($NODE_IP)\"\n        return 1\n    fi\n    log_info \"SSH \u8fde\u63a5\u6210\u529f: $NODE_NAME\"\n\n    if [ \"$TEST_ONLY\" = true ]; then\n        return 0\n    fi\n\n    # \u786e\u4fdd\u8fdc\u7a0b\u76ee\u5f55\u5b58\u5728\n    ssh \"root@${NODE_IP}\" \"mkdir -p ${REMOTE_BASE}/{cloudflared,adguard/{work,conf},wireguard/config,clash,memos,homeassistant,piwigo/{config,gallery},xiaomusic,migpt,typecho,syncthing/{config,data},verysync,aria2/{config,downloads},cupsd/{config,printers,spool},cups-web,panel,gitea}\"\n\n    # \u5206\u53d1\u914d\u7f6e\u6587\u4ef6\n    if [ -d \"$NODE_SRC\" ]; then\n        log_info \"\u5206\u53d1 ${NODE_SRC} \u2192 ${NODE_IP}:${REMOTE_BASE}\"\n        rsync -avz $DRY_RUN \\\n            --exclude '*.bak' --exclude '*.old' \\\n            --exclude '.git' --exclude '__pycache__' \\\n            \"${NODE_SRC}/\" \"root@${NODE_IP}:${REMOTE_BASE}/\"\n    else\n        log_warn \"\u672c\u5730\u672a\u627e\u5230 $NODE_SRC, \u8df3\u8fc7\"\n    fi\n\n    # \u5206\u53d1\u811a\u672c\u548c\u6587\u6863\u5230\u516c\u5171\u4f4d\u7f6e\n    if [ \"$DRY_RUN\" != \"--dry-run\" ]; then\n        ssh \"root@${NODE_IP}\" \"mkdir -p /mnt/sd/scripts /mnt/sd/docs /mnt/sd/inventory\"\n        rsync -avz $DRY_RUN \"${SCRIPT_DIR}/\" \"root@${NODE_IP}:/mnt/sd/scripts/\"\n        rsync -avz $DRY_RUN \"${PROJECT_DIR}/docs/\" \"root@${NODE_IP}:/mnt/sd/docs/\"\n        rsync -avz $DRY_RUN \"${PROJECT_DIR}/inventory/\" \"root@${NODE_IP}:/mnt/sd/inventory/\"\n    fi\n\n    log_info \"$NODE_NAME \u5b8c\u6210 \u2713\"\n    echo \"\"\n}\n\nif [ ${#TARGET_NODES[@]} -eq 0 ]; then\n    TARGET_NODES=(\"${NODES[@]}\")\nfi\n\nfor NODE in \"${TARGET_NODES[@]}\"; do\n    IFS='|' read -r NAME IP ROLE <<< \"$NODE\"\n    deploy_node \"$NAME\" \"$IP\" \"$ROLE\" || true\ndone\n\necho \"==========================================\"\nlog_info \"\u5206\u53d1\u5b8c\u6210\"\necho \"==========================================\""}]