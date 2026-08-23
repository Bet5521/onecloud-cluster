#!/bin/bash
# ============================================================
# OneCloud Cluster - 统一安装部署脚本 (setup.sh)
# 功能: 端口冲突检测 / 多选批量安装 / U盘自动挂载 / SD卡自动挂载
# 用法: sudo bash setup.sh
# ============================================================
set -u

# ---- 颜色 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ---- 日志 ----
log_info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()    { echo -e "\n${BLUE}${BOLD}==> $*${NC}"; }
log_success() { echo -e "${GREEN}${BOLD}✓ $*${NC}"; }

# ---- 全局配置 ----
DATA_DIR="/mnt/sd/srv"          # 数据根目录(优先 SD 卡)
[ -d /mnt/sd ] || DATA_DIR="/opt/onecloud/srv"
COMPOSE_DIR="${DATA_DIR}"       # docker-compose 目录
TZ="Asia/Shanghai"
PUID=1000
PGID=1000
