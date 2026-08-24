#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OneCloud Cluster 功能验证脚本
模拟检测所有脚本和功能是否可用
不依赖 pyyaml，使用内置解析器验证 YAML
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# ============ 配置 ============
PROJECT_ROOT = Path(__file__).parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
NODE_DIRS = {
    "wk-edge-01": PROJECT_ROOT / "node-wk-edge-01",
    "wk-iot-02": PROJECT_ROOT / "node-wk-iot-02",
    "wk-storage-03": PROJECT_ROOT / "node-wk-storage-03",
}
INVENTORY_DIR = PROJECT_ROOT / "inventory"
PANEL_DIR = PROJECT_ROOT / "panel"

# 节点IP映射（硬编码fallback验证用）
NODE_IP_MAP = {
    "wk-edge-01": "192.168.1.101",
    "wk-iot-02": "192.168.1.102",
    "wk-storage-03": "192.168.1.103",
}

# 颜色支持（Windows兼容）
try:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    HAS_COLOR = True
except:
    HAS_COLOR = False

def color(text, code):
    if HAS_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text

def log_pass(msg):
    print(f"  {color('PASS', 32)} {msg}")

def log_fail(msg):
    print(f"  {color('FAIL', 31)} {msg}")

def log_warn(msg):
    print(f"  {color('WARN', 33)} {msg}")

def log_info(msg):
    print(f"  {color('INFO', 36)} {msg}")

def log_skip(msg):
    print(f"  {color('SKIP', 90)} {msg}")

PASS_COUNT = 0
FAIL_COUNT = 0
WARN_COUNT = 0
SKIP_COUNT = 0

def test_begin(name):
    global PASS_COUNT, FAIL_COUNT, WARN_COUNT, SKIP_COUNT
    PASS_COUNT = FAIL_COUNT = WARN_COUNT = SKIP_COUNT = 0
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")

def test_end():
    total = PASS_COUNT + FAIL_COUNT + WARN_COUNT + SKIP_COUNT
    print(f"  --- {total} 项, {color('PASS', 32)}:{PASS_COUNT} {color('FAIL', 31)}:{FAIL_COUNT} {color('WARN', 33)}:{WARN_COUNT} {color('SKIP', 90)}:{SKIP_COUNT} ---")
    return FAIL_COUNT == 0

# ============ 1. 配置文件完整性 ============

def test_config_files_exist():
    """验证所有必需的配置文件是否存在"""
    test_begin("1: 配置文件完整性")
    all_ok = True

    required_files = [
        ("部署脚本", SCRIPTS_DIR / "deploy.sh"),
        ("安装服务脚本", SCRIPTS_DIR / "install-services.sh"),
        ("备份脚本", SCRIPTS_DIR / "backup.sh"),
        ("恢复脚本", SCRIPTS_DIR / "restore.sh"),
        ("健康检查脚本", SCRIPTS_DIR / "health-check.sh"),
        ("初始化脚本", SCRIPTS_DIR / "setup.sh"),
        ("WireGuard设置", SCRIPTS_DIR / "wireguard-setup.sh"),
        ("面板应用", PANEL_DIR / "app.py"),
        ("面板配置", PANEL_DIR / "config.json"),
        ("面板服务安装", PANEL_DIR / "install-service.sh"),
        ("服务清单", INVENTORY_DIR / "services.yaml"),
        ("节点清单", INVENTORY_DIR / "nodes.yaml"),
        ("Edge节点docker-compose", NODE_DIRS["wk-edge-01"] / "docker-compose.yml"),
        ("IoT节点docker-compose", NODE_DIRS["wk-iot-02"] / "docker-compose.yml"),
        ("Storage节点docker-compose", NODE_DIRS["wk-storage-03"] / "docker-compose.yml"),
    ]

    for name, path in required_files:
        if path.exists():
            log_pass(f"{name}: {path.name}")
            PASS_COUNT += 1
        else:
            log_fail(f"{name}: {path} 不存在")
            FAIL_COUNT += 1
            all_ok = False

    return test_end()

# ============ 2. 节点目录结构 ============

def test_node_directory_structure():
    """验证每个节点目录包含必需的子目录和文件"""
    test_begin("2: 节点目录结构")
    all_ok = True

    for node_name, node_dir in NODE_DIRS.items():
        if not node_dir.exists():
            log_fail(f"{node_name}: 目录不存在")
            FAIL_COUNT += 1
            all_ok = False
            continue

        log_pass(f"{node_name}: 目录存在")
        PASS_COUNT += 1

        # 检查 docker-compose.yml
        dc_file = node_dir / "docker-compose.yml"
        if dc_file.exists():
            log_pass(f"  {node_name}: docker-compose.yml 存在")
            PASS_COUNT += 1
        else:
            log_fail(f"  {node_name}: docker-compose.yml 不存在")
            FAIL_COUNT += 1
            all_ok = False

        # 检查是否有 .env 文件（可选）
        env_file = node_dir / ".env"
        if env_file.exists():
            log_pass(f"  {node_name}: .env 存在")
            PASS_COUNT += 1
        else:
            log_warn(f"  {node_name}: .env 不存在（可选）")
            WARN_COUNT += 1

        # 检查子目录结构
        has_srv_dir = False
        for item in node_dir.iterdir():
            if item.is_dir() and item.name in ["srv", "config", "data"]:
                has_srv_dir = True
                log_pass(f"  {node_name}: 子目录 {item.name} 存在")
                PASS_COUNT += 1

        if not has_srv_dir:
            log_warn(f"  {node_name}: 无 srv/config/data 子目录")
            WARN_COUNT += 1

    return test_end()

# ============ 3. Shell 脚本语法检查 ============

def test_shell_scripts_syntax():
    """检查所有 Shell 脚本的语法正确性（用 bash -n）"""
    test_begin("3: Shell 脚本语法检查")
    all_ok = True

    # 收集所有 .sh 文件
    sh_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 跳过隐藏目录
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.sh'):
                sh_files.append(os.path.join(root, f))

    if not sh_files:
        log_warn("未找到 .sh 文件，跳过语法检查")
        WARN_COUNT += 1
        return test_end()

    for sh_file in sorted(sh_files):
        rel_path = os.path.relpath(sh_file, PROJECT_ROOT)
        try:
            result = subprocess.run(
                ["bash", "-n", sh_file],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                log_pass(f"{rel_path}: 语法正确")
                PASS_COUNT += 1
            else:
                log_fail(f"{rel_path}: 语法错误\n{result.stderr.strip()}")
                FAIL_COUNT += 1
                all_ok = False
        except FileNotFoundError:
            log_skip("bash 不可用，跳过语法检查")
            SKIP_COUNT += 1
            break
        except subprocess.TimeoutExpired:
            log_fail(f"{rel_path}: 超时")
            FAIL_COUNT += 1
            all_ok = False

    return test_end()

# ============ 4. deploy.sh 节点映射 ============

def test_deploy_node_mapping():
    """验证 deploy.sh 中节点名称到目录/IP 的映射"""
    test_begin("4: deploy.sh 节点映射")
    all_ok = True

    deploy_path = SCRIPTS_DIR / "deploy.sh"
    if not deploy_path.exists():
        log_fail("deploy.sh 不存在")
        FAIL_COUNT += 1
        return test_end()

    content = deploy_path.read_text(encoding='utf-8')

    # 检查节点名称映射
    expected_nodes = ["wk-edge-01", "wk-iot-02", "wk-storage-03"]
    for node in expected_nodes:
        if node in content:
            log_pass(f"deploy.sh 包含节点 {node}")
            PASS_COUNT += 1
        else:
            log_fail(f"deploy.sh 缺少节点 {node}")
            FAIL_COUNT += 1
            all_ok = False

    # 检查是否包含目录映射
    mapping_patterns = ["NODE_DIR", "node_dir", "srv/", "/mnt/sd/srv/"]
    for pattern in mapping_patterns:
        if pattern in content:
            log_pass(f"deploy.sh 包含目录映射: {pattern}")
            PASS_COUNT += 1
        else:
            log_warn(f"deploy.sh 可能缺少目录映射: {pattern}")
            WARN_COUNT += 1

    # 检查是否有 IP 映射
    ip_pattern = re.search(r'192\.168\.\d+\.\d+', content)
    if ip_pattern:
        log_pass(f"deploy.sh 包含 IP 映射: {ip_pattern.group()}")
        PASS_COUNT += 1
    else:
        log_warn("deploy.sh 中未检测到 IP 映射")
        WARN_COUNT += 1

    return test_end()

# ============ 5. 回退机制 ============

def test_fallback_mechanisms():
    """检查脚本中是否有 IP 硬编码回退、命令回退等"""
    test_begin("5: 回退机制")
    all_ok = True

    scripts_to_check = [
        ("backup.sh", SCRIPTS_DIR / "backup.sh"),
        ("restore.sh", SCRIPTS_DIR / "restore.sh"),
        ("deploy.sh", SCRIPTS_DIR / "deploy.sh"),
        ("install-services.sh", SCRIPTS_DIR / "install-services.sh"),
        ("health-check.sh", SCRIPTS_DIR / "health-check.sh"),
    ]

    for name, path in scripts_to_check:
        if not path.exists():
            log_skip(f"{name}: 不存在")
            SKIP_COUNT += 1
            continue

        content = path.read_text(encoding='utf-8')

        # 检查是否有 IP 回退（硬编码 IP 作为 fallback）
        has_ip_fallback = "192.168." in content
        if has_ip_fallback:
            log_pass(f"{name}: 包含 IP 回退")
            PASS_COUNT += 1
        else:
            log_warn(f"{name}: 未检测到 IP 回退")
            WARN_COUNT += 1

        # 检查是否有 docker-compose/docker compose 回退
        has_docker_fallback = "docker-compose" in content and "docker compose" in content
        if has_docker_fallback:
            log_pass(f"{name}: 包含 docker 命令回退")
            PASS_COUNT += 1
        else:
            log_warn(f"{name}: 未检测到 docker 命令回退")
            WARN_COUNT += 1

        # 检查是否有管道回退（||）
        has_pipe_fallback = "||" in content
        if has_pipe_fallback:
            log_pass(f"{name}: 包含 || 回退")
            PASS_COUNT += 1
        else:
            log_warn(f"{name}: 未检测到 || 回退")
            WARN_COUNT += 1

    return test_end()

# ============ 6. 服务一致性：services.yaml vs config.json ============

def _parse_yaml_simple(yaml_text: str) -> dict:
    """简易 YAML 解析器，支持基本 key: value 和嵌套结构"""
    result = {}
    lines = yaml_text.split('\n')
    current_key = None
    current_list = []
    in_list = False
    indent_stack = [(-1, result)]

    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip() or stripped.strip().startswith('#'):
            continue

        indent = len(line) - len(line.lstrip())
        content = stripped.strip()

        # 缩进减少时弹出栈
        while indent_stack and indent <= indent_stack[-1][0]:
            indent_stack.pop()

        if not indent_stack:
            indent_stack.append((-1, {}))

        current_dict = indent_stack[-1][1]

        if content.startswith('-'):
            # 列表项
            item = content[1:].strip()
            if item.startswith('{') and item.endswith('}'):
                # 尝试解析内联 dict
                try:
                    inner = json.loads(item.replace("'", '"'))
                    current_list.append(inner)
                except json.JSONDecodeError:
                    current_list.append(item)
            elif ': ' in item:
                # 可能是 key: value 形式的列表项
                parts = item.split(': ', 1)
                current_list.append({parts[0].strip(): parts[1].strip()})
            else:
                current_list.append(item)
            in_list = True
        else:
            if in_list:
                if current_key and current_list:
                    current_dict[current_key] = current_list
                current_list = []
                in_list = False

            if ': ' in content:
                key, value = content.split(': ', 1)
                key = key.strip()
                value = value.strip()
                if value == '' or value == '{}':
                    current_dict[key] = {}
                    indent_stack.append((indent, {}))
                    indent_stack[-1] = (indent, current_dict[key])
                elif value == '[]':
                    current_dict[key] = []
                elif value.lower() == 'true':
                    current_dict[key] = True
                elif value.lower() == 'false':
                    current_dict[key] = False
                elif value.lower() == 'null' or value.lower() == '~':
                    current_dict[key] = None
                else:
                    current_dict[key] = value
                current_key = key
            elif ':' in content and content.endswith(':'):
                key = content.rstrip(':').strip()
                current_dict[key] = {}
                indent_stack.append((indent, current_dict[key]))
                current_key = key

    if in_list and current_key and current_list:
        # Find the right dict
        d = result
        for k in current_key.split('.'):
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                break
        else:
            if isinstance(d, dict):
                d[current_key] = current_list

    return result

def test_service_consistency():
    """验证 services.yaml 和 config.json 中的服务定义是否一致"""
    test_begin("6: 服务一致性 (services.yaml vs config.json)")
    all_ok = True

    services_yaml_path = INVENTORY_DIR / "services.yaml"
    config_json_path = PANEL_DIR / "config.json"

    if not services_yaml_path.exists():
        log_fail("services.yaml 不存在")
        FAIL_COUNT += 1
        return test_end()
    if not config_json_path.exists():
        log_fail("config.json 不存在")
        FAIL_COUNT += 1
        return test_end()

    # 解析 services.yaml
    yaml_text = services_yaml_path.read_text(encoding='utf-8')
    yaml_parsed = _parse_yaml_simple(yaml_text)
    log_pass("services.yaml 解析成功")
    PASS_COUNT += 1

    # 解析 config.json
    try:
        with open(config_json_path, encoding='utf-8') as f:
            config = json.load(f)
        log_pass("config.json 解析成功")
        PASS_COUNT += 1
    except (json.JSONDecodeError, FileNotFoundError) as e:
        log_fail(f"config.json 解析失败: {e}")
        FAIL_COUNT += 1
        return test_end()

    # 获取 services.yaml 中定义的服务名
    yaml_services = {}
    if "services" in yaml_parsed:
        svcs = yaml_parsed["services"]
        if isinstance(svcs, dict):
            yaml_services = svcs
        elif isinstance(svcs, str):
            log_warn(f"services 字段是字符串而非字典: {svcs}")
            WARN_COUNT += 1
    else:
        log_warn("services.yaml 中未找到 services 字段")
        WARN_COUNT += 1

    yaml_service_names = set(yaml_services.keys())
    log_info(f"services.yaml 定义了 {len(yaml_service_names)} 个服务: {sorted(yaml_service_names)}")

    # 获取 config.json 中所有节点定义的服务
    config_service_names = set()
    for node in config.get("nodes", []):
        for svc in node.get("services", []):
            if isinstance(svc, dict) and "name" in svc:
                config_service_names.add(svc["name"])

    log_info(f"config.json 引用了 {len(config_service_names)} 个服务: {sorted(config_service_names)}")

    # 检查一致性
    if yaml_service_names == config_service_names:
        log_pass("services.yaml 和 config.json 服务定义完全一致")
        PASS_COUNT += 1
    else:
        missing_in_config = yaml_service_names - config_service_names
        extra_in_config = config_service_names - yaml_service_names
        if missing_in_config:
            log_warn(f"services.yaml 有但 config.json 缺少: {missing_in_config}")
            WARN_COUNT += 1
        if extra_in_config:
            log_warn(f"config.json 有但 services.yaml 缺少: {extra_in_config}")
            WARN_COUNT += 1

    # 检查单个服务配置
    for node in config.get("nodes", []):
        node_name = node.get("name", "unknown")
        for svc in node.get("services", []):
            svc_name = svc.get("name", "")
            if svc_name in yaml_services:
                yaml_svc = yaml_services[svc_name]
                if isinstance(yaml_svc, dict):
                    # 检查端口一致性
                    yaml_ports = yaml_svc.get("ports", [])
                    if isinstance(yaml_ports, str):
                        yaml_ports = [yaml_ports]
                    svc_ports = svc.get("ports", [])
                    if isinstance(svc_ports, list) and isinstance(yaml_ports, list):
                        if set(str(p) for p in svc_ports) == set(str(p) for p in yaml_ports):
                            log_pass(f"{node_name}/{svc_name}: 端口一致")
                            PASS_COUNT += 1
                        else:
                            log_warn(f"{node_name}/{svc_name}: 端口不一致 (config:{svc_ports} vs yaml:{yaml_ports})")
                            WARN_COUNT += 1

    return test_end()

# ============ 7. Python 文件语法检查 ============

def test_python_syntax():
    """检查所有 Python 文件的语法"""
    test_begin("7: Python 语法检查")
    all_ok = True

    py_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))

    if not py_files:
        log_warn("未找到 .py 文件")
        WARN_COUNT += 1
        return test_end()

    for py_file in sorted(py_files):
        rel_path = os.path.relpath(py_file, PROJECT_ROOT)
        try:
            with open(py_file, encoding='utf-8') as f:
                compile(f.read(), py_file, 'exec')
            log_pass(f"{rel_path}: 语法正确")
            PASS_COUNT += 1
        except SyntaxError as e:
            log_fail(f"{rel_path}: 语法错误: {e}")
            FAIL_COUNT += 1
            all_ok = False

    return test_end()

# ============ 8. Docker Compose 文件验证 ============

def test_docker_compose():
    """验证 docker-compose.yml 文件结构"""
    test_begin("8: Docker Compose 文件验证")
    all_ok = True

    for node_name, node_dir in NODE_DIRS.items():
        dc_file = node_dir / "docker-compose.yml"
        if not dc_file.exists():
            log_skip(f"{node_name}: docker-compose.yml 不存在")
            SKIP_COUNT += 1
            continue

        content = dc_file.read_text(encoding='utf-8')

        # 检查基本结构
        checks = [
            ("services", "services" in content),
            ("version", "version:" in content or "version: " in content),
            ("image", "image:" in content),
            ("container_name", "container_name:" in content),
            ("restart", "restart:" in content),
        ]

        for check_name, result in checks:
            if result:
                log_pass(f"{node_name}: 包含 {check_name}")
                PASS_COUNT += 1
            else:
                log_warn(f"{node_name}: 缺少 {check_name}")
                WARN_COUNT += 1

        # 检查端口映射
        port_matches = re.findall(r'"?(\d+:\d+)"?', content)
        if port_matches:
            log_pass(f"{node_name}: 端口映射 {port_matches}")
            PASS_COUNT += 1
        else:
            log_warn(f"{node_name}: 未检测到端口映射")
            WARN_COUNT += 1

        # 检查卷映射
        if "volumes:" in content or "volumes" in re.findall(r'\bvolumes\b', content):
            log_pass(f"{node_name}: 包含卷映射")
            PASS_COUNT += 1
        else:
            log_warn(f"{node_name}: 未检测到卷映射")
            WARN_COUNT += 1

        # 检查环境变量
        if "environment:" in content:
            log_pass(f"{node_name}: 包含环境变量")
            PASS_COUNT += 1
        else:
            log_warn(f"{node_name}: 未检测到环境变量")
            WARN_COUNT += 1

    return test_end()

# ============ 9. 配置项完整性 ============

def test_config_fields():
    """验证 config.json 的字段完整性"""
    test_begin("9: 配置项完整性")
    all_ok = True

    config_path = PANEL_DIR / "config.json"
    if not config_path.exists():
        log_fail("config.json 不存在")
        FAIL_COUNT += 1
        return test_end()

    try:
        with open(config_path, encoding='utf-8') as f:
            config = json.load(f)
        log_pass("config.json 解析成功")
        PASS_COUNT += 1
    except json.JSONDecodeError as e:
        log_fail(f"config.json 解析失败: {e}")
        FAIL_COUNT += 1
        return test_end()

    # 检查顶层字段
    required_top_fields = ["cluster_name", "version", "nodes"]
    for field in required_top_fields:
        if field in config:
            log_pass(f"config.json 包含顶层字段: {field}")
            PASS_COUNT += 1
        else:
            log_fail(f"config.json 缺少顶层字段: {field}")
            FAIL_COUNT += 1
            all_ok = False

    # 检查节点字段
    for node in config.get("nodes", []):
        node_name = node.get("name", "unknown")
        required_node_fields = ["name", "display_name", "role", "ip", "wg_ip", "color", "services"]
        for field in required_node_fields:
            if field in node:
                log_pass(f"节点 {node_name}: 包含字段 {field}")
                PASS_COUNT += 1
            else:
                log_fail(f"节点 {node_name}: 缺少字段 {field}")
                FAIL_COUNT += 1
                all_ok = False

        # 检查服务字段
        for svc in node.get("services", []):
            svc_name = svc.get("name", "unknown")
            required_svc_fields = ["name", "display", "icon"]
            for field in required_svc_fields:
                if field in svc:
                    log_pass(f"  服务 {svc_name}: 包含字段 {field}")
                    PASS_COUNT += 1
                else:
                    log_warn(f"  服务 {svc_name}: 缺少字段 {field}")
                    WARN_COUNT += 1

    return test_end()

# ============ 10. 脚本完整性和 self-test ============

def test_script_self_test():
    """检查脚本自身是否包含基本的错误处理、日志等"""
    test_begin("10: 脚本完整性检查")
    all_ok = True

    sh_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.sh'):
                sh_files.append(os.path.join(root, f))

    for sh_file in sorted(sh_files):
        rel_path = os.path.relpath(sh_file, PROJECT_ROOT)
        content = Path(sh_file).read_text(encoding='utf-8')

        # 检查 shebang
        if content.startswith('#!'):
            log_pass(f"{rel_path}: 包含 shebang")
            PASS_COUNT += 1
        else:
            log_warn(f"{rel_path}: 缺少 shebang")
            WARN_COUNT += 1

        # 检查 set -e
        if 'set -e' in content:
            log_pass(f"{rel_path}: 包含 set -e")
            PASS_COUNT += 1
        else:
            log_warn(f"{rel_path}: 缺少 set -e")
            WARN_COUNT += 1

        # 检查错误处理
        error_patterns = ['exit', 'echo.*error', 'echo.*fail', '||', 'log_info', 'log_error']
        has_error_handling = any(re.search(pattern, content, re.IGNORECASE) for pattern in error_patterns)
        if has_error_handling:
            log_pass(f"{rel_path}: 包含错误处理")
            PASS_COUNT += 1
        else:
            log_warn(f"{rel_path}: 未检测到错误处理")
            WARN_COUNT += 1

        # 检查函数定义
        if re.search(r'^\w+\s*\(\)', content, re.MULTILINE):
            log_pass(f"{rel_path}: 包含函数定义")
            PASS_COUNT += 1
        else:
            log_warn(f"{rel_path}: 未检测到函数定义")
            WARN_COUNT += 1

    return test_end()

# ============ 11. 安全配置检查 ============

def test_security_config():
    """检查安全相关配置"""
    test_begin("11: 安全配置检查")
    all_ok = True

    # 检查 panel/app.py 的认证
    app_py = PANEL_DIR / "app.py"
    if app_py.exists():
        content = app_py.read_text(encoding='utf-8')
        auth_checks = [
            ("require_auth 装饰器", "require_auth" in content),
            ("Basic Auth 校验", "_check_auth" in content or "basic" in content.lower()),
            ("PANEL_USER/PANEL_PASS", "PANEL_USER" in content and "PANEL_PASS" in content),
            ("命令白名单", "ALLOWED_CMD_PREFIXES" in content),
            ("命令安全校验", "is_command_safe" in content),
            ("CORS 限制", "CORS" in content and "origins" in content),
        ]

        for check_name, result in auth_checks:
            if result:
                log_pass(f"app.py: {check_name}")
                PASS_COUNT += 1
            else:
                log_warn(f"app.py: 缺少 {check_name}")
                WARN_COUNT += 1

    # 检查 WireGuard 密钥权限
    wg_script = SCRIPTS_DIR / "wireguard-setup.sh"
    if wg_script.exists():
        content = wg_script.read_text(encoding='utf-8')
        if 'chmod 600' in content:
            log_pass("wireguard-setup.sh: 包含 chmod 600 权限设置")
            PASS_COUNT += 1
        else:
            log_warn("wireguard-setup.sh: 缺少 chmod 600 权限设置")
            WARN_COUNT += 1

        if 'wg genkey' in content and '>/dev/null' in content:
            log_pass("wireguard-setup.sh: 私钥不输出到终端")
            PASS_COUNT += 1
        else:
            log_warn("wireguard-setup.sh: 私钥可能输出到终端")
            WARN_COUNT += 1

    # 检查 reboot 二次确认
    if 'confirm' in app_py.read_text(encoding='utf-8'):
        log_pass("app.py: 危险操作包含二次确认")
        PASS_COUNT += 1
    else:
        log_warn("app.py: 危险操作缺少二次确认")
        WARN_COUNT += 1

    return test_end()

# ============ 12. 功能清单与代码一致性验证 ============

def test_feature_consistency():
    """验证所有功能清单文件与代码实现的一致性"""
    test_begin("12: 功能清单与代码一致性验证")
    all_ok = True

    # 1. 验证 services.yaml 中定义的服务与 docker-compose.yml 中的服务一致
    log_info("验证 services.yaml 与 docker-compose.yml 一致性:")
    services_yaml_path = INVENTORY_DIR / "services.yaml"
    if services_yaml_path.exists():
        yaml_content = services_yaml_path.read_text(encoding='utf-8')
        yaml_parsed = _parse_yaml_simple(yaml_content)
        yaml_services = yaml_parsed.get("services", {})
        if isinstance(yaml_services, str):
            log_warn(f"services 字段类型是字符串: {yaml_services}")
            WARN_COUNT += 1
            yaml_services = {}

        for node_name, node_dir in NODE_DIRS.items():
            dc_file = node_dir / "docker-compose.yml"
            if not dc_file.exists():
                continue
            dc_content = dc_file.read_text(encoding='utf-8')

            # 提取 docker-compose 中的服务名
            dc_services = re.findall(r'^\s+(\w+):\s*$', dc_content, re.MULTILINE)
            # 也匹配带引号的服务名
            dc_services += re.findall(r'^\s+"(\w+)":\s*$', dc_content, re.MULTILINE)

            # 检查 yaml 中定义的服务是否在 docker-compose 中
            for svc_name in yaml_services:
                if isinstance(svc_name, str) and svc_name in dc_content:
                    log_pass(f"{node_name}: 服务 {svc_name} 在 docker-compose.yml 中")
                    PASS_COUNT += 1
                elif isinstance(svc_name, str):
                    log_warn(f"{node_name}: 服务 {svc_name} 在 docker-compose.yml 中未找到")
                    WARN_COUNT += 1

    # 2. 验证 services.yaml 与 panel/config.json 的服务定义一致
    log_info("验证 services.yaml 与 panel/config.json 一致性:")
    config_json_path = PANEL_DIR / "config.json"
    if config_json_path.exists():
        try:
            with open(config_json_path, encoding='utf-8') as f:
                config = json.load(f)

            for node in config.get("nodes", []):
                node_name = node.get("name", "unknown")
                panel_svcs = set(s.get("name", "") for s in node.get("services", []))

                # 从 yaml 服务名中筛选
                yaml_node_svcs = set()
                for svc_name in yaml_services:
                    if isinstance(svc_name, str):
                        yaml_node_svcs.add(svc_name)

                missing_in_panel = yaml_node_svcs - panel_svcs
                extra_in_panel = panel_svcs - yaml_node_svcs

                if not missing_in_panel and not extra_in_panel:
                    log_pass(f"节点 {node_name}: services.yaml 与 panel 一致")
                    PASS_COUNT += 1
                else:
                    if missing_in_panel:
                        log_warn(f"节点 {node_name}: panel 缺少服务 {missing_in_panel}")
                        WARN_COUNT += 1
                    if extra_in_panel:
                        log_warn(f"节点 {node_name}: panel 多出服务 {extra_in_panel}")
                        WARN_COUNT += 1

            # 验证端口配置
            log_info("验证服务端口配置:")
            for svc_name, svc_config in yaml_services.items():
                if isinstance(svc_config, dict) and svc_config.get("container"):
                    ports = svc_config.get("ports", [])
                    if isinstance(ports, str):
                        ports = [ports]
                    for port_entry in ports:
                        port = port_entry.split(":")[0] if ":" in port_entry else port_entry
                        # 检查端口是否在 docker-compose 中出现
                        found = False
                        for node_dir in NODE_DIRS.values():
                            dc_file = node_dir / "docker-compose.yml"
                            if dc_file.exists() and port in dc_file.read_text(encoding='utf-8'):
                                found = True
                                break
                        if found:
                            log_pass(f"服务 {svc_name}: 端口 {port} 在 docker-compose 中")
                            PASS_COUNT += 1
                        else:
                            log_warn(f"服务 {svc_name}: 端口 {port} 未在 docker-compose 中找到")
                            WARN_COUNT += 1

        except (json.JSONDecodeError, FileNotFoundError) as e:
            log_fail(f"config.json 解析失败: {e}")
            FAIL_COUNT += 1

    # 3. 验证 README.md 中提到的功能是否有代码实现
    log_info("验证 README.md 与代码实现一致性:")
    readme_path = PROJECT_ROOT / "README.md"
    if readme_path.exists():
        readme_content = readme_path.read_text(encoding='utf-8')
        # 提取功能关键词
        feature_keywords = [
            ("deploy.sh", "deploy"),
            ("backup.sh", "backup"),
            ("restore.sh", "restore"),
            ("health-check.sh", "health"),
            ("setup.sh", "setup"),
            ("docker-compose", "docker"),
            ("WireGuard", "wireguard"),
            ("AdGuard", "adguard"),
            ("Home Assistant", "home"),
            ("miGPT", "migpt"),
            ("Clash", "clash"),
            ("AriaNg", "ariang"),
            ("xiaomusic", "xiaomusic"),
            ("webdav", "webdav"),
        ]

        for keyword, search_term in feature_keywords:
            # 在 README 中查找
            in_readme = keyword.lower() in readme_content.lower()
            # 在代码中查找
            in_code = False
            for root, dirs, files in os.walk(PROJECT_ROOT):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', '.git']]
                for f in files:
                    if f.endswith(('.sh', '.py', '.yml', '.yaml', '.json', '.md')):
                        try:
                            file_content = Path(os.path.join(root, f)).read_text(encoding='utf-8', errors='ignore')
                            if search_term.lower() in file_content.lower():
                                in_code = True
                                break
                        except:
                            pass
                if in_code:
                    break

            if in_readme and in_code:
                log_pass(f"{keyword}: README 和代码中都存在")
                PASS_COUNT += 1
            elif in_readme and not in_code:
                log_warn(f"{keyword}: README 中有但代码中未找到实现")
                WARN_COUNT += 1
            elif not in_readme and in_code:
                log_warn(f"{keyword}: 代码中有但 README 中未提及")
                WARN_COUNT += 1
            else:
                log_skip(f"{keyword}: 未在任何地方找到")
                SKIP_COUNT += 1

    # 4. 验证 architecture.md 中的拓扑与实际配置一致
    log_info("验证 architecture.md 与配置一致性:")
    arch_path = PROJECT_ROOT / "architecture.md"
    if arch_path.exists():
        arch_content = arch_path.read_text(encoding='utf-8')
        # 检查节点名称
        for node_name in NODE_IP_MAP:
            if node_name in arch_content:
                log_pass(f"{node_name}: 在 architecture.md 中")
                PASS_COUNT += 1
            else:
                log_warn(f"{node_name}: 未在 architecture.md 中提及")
                WARN_COUNT += 1

        # 检查 IP 地址
        for ip in NODE_IP_MAP.values():
            if ip in arch_content:
                log_pass(f"IP {ip}: 在 architecture.md 中")
                PASS_COUNT += 1
            else:
                log_warn(f"IP {ip}: 未在 architecture.md 中提及")
                WARN_COUNT += 1

    # 5. 验证 .env.example 与 docker-compose 中的环境变量一致
    log_info("验证 .env.example 与 docker-compose 环境变量一致性:")
    for node_name, node_dir in NODE_DIRS.items():
        env_example = node_dir / ".env.example"
        env_file = node_dir / ".env"
        dc_file = node_dir / "docker-compose.yml"

        env_vars = set()
        if env_example.exists():
            for line in env_example.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    env_vars.add(line.split('=')[0].strip())

        if env_file.exists():
            for line in env_file.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    env_vars.add(line.split('=')[0].strip())

        if dc_file.exists() and env_vars:
            dc_content = dc_file.read_text(encoding='utf-8')
            for var in env_vars:
                if var in dc_content or f"${{{var}}}" in dc_content or f"$var" in dc_content:
                    log_pass(f"{node_name}: 环境变量 {var} 在 docker-compose 中引用")
                    PASS_COUNT += 1
                else:
                    log_warn(f"{node_name}: 环境变量 {var} 未在 docker-compose 中引用")
                    WARN_COUNT += 1

    return test_end()

# ============ 主函数 ============

def main():
    print("=" * 60)
    print("OneCloud Cluster 功能验证脚本")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"时间: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}")

    tests = [
        ("配置文件完整性", test_config_files_exist),
        ("节点目录结构", test_node_directory_structure),
        ("Shell 脚本语法检查", test_shell_scripts_syntax),
        ("deploy.sh 节点映射", test_deploy_node_mapping),
        ("回退机制", test_fallback_mechanisms),
        ("服务一致性", test_service_consistency),
        ("Python 语法检查", test_python_syntax),
        ("Docker Compose 文件验证", test_docker_compose),
        ("配置项完整性", test_config_fields),
        ("脚本完整性检查", test_script_self_test),
        ("安全配置检查", test_security_config),
        ("功能清单与代码一致性验证", test_feature_consistency),
    ]

    total_pass = 0
    total_fail = 0
    results = []

    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"运行测试: {test_name}")
        print(f"{'='*60}")
        try:
            ok = test_func()
            if ok:
                total_pass += 1
            else:
                total_fail += 1
            results.append((test_name, ok))
        except Exception as e:
            print(f"  {color('ERROR', 31)} 测试异常: {e}")
            total_fail += 1
            results.append((test_name, False))

    # 汇总
    print(f"\n\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    for name, ok in results:
        status = color("PASS", 32) if ok else color("FAIL", 31)
        print(f"  [{status}] {name}")

    print(f"\n总测试数: {len(tests)}, {color('通过', 32)}: {total_pass}, {color('失败', 31)}: {total_fail}")

    return total_fail == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
