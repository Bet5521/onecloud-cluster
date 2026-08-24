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

GREEN = "92"
RED = "91"
YELLOW = "93"
CYAN = "96"

# ============ 简易 YAML 解析器 ============
def simple_yaml_parse(text: str) -> Dict[str, Any]:
    """简易 YAML 解析器，支持本项目使用的 YAML 结构"""
    result = {}
    lines = text.strip().split('\n')
    
    # 处理 nodes.yaml 格式
    if 'nodes:' in text:
        nodes = []
        current_node = None
        in_services = False
        
        for line in lines:
            stripped = line.strip()
            
            # 节点定义开始
            if stripped.startswith('- name:'):
                if current_node:
                    nodes.append(current_node)
                current_node = {'name': stripped.split(':', 1)[1].strip()}
                in_services = False
            
            # 节点属性
            elif current_node and ':' in stripped and not stripped.startswith('#'):
                key, _, value = stripped.partition(':')
                key = key.strip()
                value = value.strip()
                
                # 处理列表值
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip() for v in value[1:-1].split(',')]
                elif value == '':
                    # 可能是嵌套结构
                    pass
                
                if current_node is not None and not in_services:
                    current_node[key] = value
            
            # services 列表
            if 'services:' in stripped and stripped.startswith('services:'):
                services_str = stripped.split(':', 1)[1].strip()
                if services_str.startswith('[') and services_str.endswith(']'):
                    current_node['services'] = [s.strip() for s in services_str[1:-1].split(',')]
                    in_services = True
        
        if current_node:
            nodes.append(current_node)
        
        result['nodes'] = nodes
        
        # 提取 network 配置
        network = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('lan_subnet:'):
                network['lan_subnet'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('wg_subnet:'):
                network['wg_subnet'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('gateway:'):
                network['gateway'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('dns:'):
                dns_val = stripped.split(':', 1)[1].strip()
                if dns_val.startswith('[') and dns_val.endswith(']'):
                    network['dns'] = [v.strip() for v in dns_val[1:-1].split(',')]
                else:
                    network['dns'] = dns_val
        if network:
            result['network'] = network
    
    # 处理 services.yaml 格式
    elif 'services:' in text:
        services = {}
        current_service = None
        
        for line in lines:
            stripped = line.strip()
            
            # 跳过注释和空行
            if not stripped or stripped.startswith('#'):
                continue
            
            # 服务名称（首层键）
            if ':' in stripped and not stripped.startswith(' '):
                if current_service is not None:
                    services[current_service['name']] = current_service
                current_service = {'name': stripped.split(':', 1)[0].strip()}
            
            # 服务属性
            elif current_service and ':' in stripped:
                key, _, value = stripped.partition(':')
                key = key.strip()
                value = value.strip()
                
                if value.startswith('[') and value.endswith(']'):
                    # 解析列表值
                    value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(',')]
                elif value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.lower() == 'null' or value.lower() == '~':
                    value = None
                
                current_service[key] = value
        
        if current_service:
            services[current_service['name']] = current_service
        
        result['services'] = services
    
    return result

# ============ 测试结果收集 ============
TEST_RESULTS = []  # (status, name, detail)
PASSED = 0
FAILED = 0
WARNINGS = 0

def log_pass(msg):
    global PASSED
    PASSED += 1
    TEST_RESULTS.append(("PASS", msg, ""))
    print(f"  {color('[PASS]', GREEN)} {msg}")

def log_fail(msg):
    global FAILED
    FAILED += 1
    TEST_RESULTS.append(("FAIL", msg, ""))
    print(f"  {color('[FAIL]', RED)} {msg}")

def log_warn(msg):
    global WARNINGS
    WARNINGS += 1
    TEST_RESULTS.append(("WARN", msg, ""))
    print(f"  {color('[WARN]', YELLOW)} {msg}")

def log_info(msg):
    print(f"    {color('[*]', CYAN)} {msg}")

# ============ 测试 1: 配置文件完整性 ============
def test_config_files():
    """验证所有配置文件是否存在"""
    print("\n" + "="*60)
    print("测试 1: 配置文件完整性")
    print("="*60)
    
    config_files = [
        INVENTORY_DIR / "nodes.yaml",
        INVENTORY_DIR / "services.yaml",
        PANEL_DIR / "config.json",
    ]
    
    all_ok = True
    for f in config_files:
        if f.exists():
            log_pass(f"{f.name} 存在")
        else:
            log_fail(f"{f.name} 不存在")
            all_ok = False
    
    return all_ok

# ============ 测试 2: 节点目录结构 ============
def test_node_directories():
    """验证节点目录结构"""
    print("\n" + "="*60)
    print("测试 2: 节点目录结构")
    print("="*60)
    
    all_ok = True
    for name, path in NODE_DIRS.items():
        if not path.exists():
            log_fail(f"{name} 目录不存在")
            all_ok = False
            continue
        log_pass(f"{name} 目录存在")
        
        # 检查 docker-compose.yml
        dc = path / "docker-compose.yml"
        if dc.exists():
            log_pass(f"  {name}/docker-compose.yml 存在")
        else:
            log_fail(f"  {name}/docker-compose.yml 不存在")
            all_ok = False
        
        # 检查 .env 文件
        env = path / ".env"
        if env.exists():
            log_pass(f"  {name}/.env 存在")
        else:
            log_warn(f"  {name}/.env 不存在（可能使用默认值）")
    
    return all_ok

# ============ 测试 3: 脚本语法检查 ============
def test_script_syntax():
    """验证所有脚本语法正确"""
    print("\n" + "="*60)
    print("测试 3: 脚本语法检查")
    print("="*60)
    
    all_ok = True
    scripts = [
        "deploy.sh", "bootstrap.sh", "setup.sh",
        "health-check.sh", "backup.sh", "restore.sh",
        "install-services.sh", "wireguard-setup.sh",
    ]
    
    for script in scripts:
        sp = SCRIPTS_DIR / script
        if not sp.exists():
            log_fail(f"{script} 不存在")
            all_ok = False
            continue
        
        # 检查基本结构
        content = sp.read_text(encoding='utf-8')
        
        # 检查 shebang
        if content.startswith('#!/usr/bin/env bash') or content.startswith('#!/bin/bash'):
            log_pass(f"{script}: shebang 正确")
        else:
            log_warn(f"{script}: 缺少 shebang 或使用了非标准 shebang")
        
        # 检查括号匹配
        open_braces = content.count('{')
        close_braces = content.count('}')
        if open_braces == close_braces:
            log_pass(f"{script}: 花括号匹配")
        else:
            log_fail(f"{script}: 花括号不匹配 ({{={open_braces}, }}={close_braces})")
            all_ok = False
        
        # 检查反引号
        backticks = content.count('`')
        if backticks % 2 == 0:
            log_pass(f"{script}: 反引号匹配")
        else:
            log_fail(f"{script}: 反引号不匹配 ({backticks})")
            all_ok = False
        
        # 检查常见的语法错误模式
        if '\r\n' in content:
            log_warn(f"{script}: 包含 CRLF 换行符（建议使用 LF）")
        
        # 检查未闭合的引号
        single_quotes = 0
        in_single = False
        for c in content:
            if c == "'" and not in_single:
                in_single = True
                single_quotes += 1
            elif c == "'" and in_single:
                in_single = False
        
        double_quotes = 0
        in_double = False
        for c in content:
            if c == '"' and not in_double:
                in_double = True
                double_quotes += 1
            elif c == '"' and in_double:
                in_double = False
        
        if single_quotes % 2 == 0:
            log_pass(f"{script}: 单引号匹配")
        else:
            log_fail(f"{script}: 单引号不匹配")
            all_ok = False
        
        if double_quotes % 2 == 0:
            log_pass(f"{script}: 双引号匹配")
        else:
            log_fail(f"{script}: 双引号不匹配")
            all_ok = False
    
    return all_ok

# ============ 测试 4: deploy.sh 节点映射 ============
def test_deploy_node_mapping():
    """验证 deploy.sh 中节点目录映射正确"""
    print("\n" + "="*60)
    print("测试 4: deploy.sh 节点映射")
    print("="*60)
    
    deploy = SCRIPTS_DIR / "deploy.sh"
    if not deploy.exists():
        log_fail("deploy.sh 不存在")
        return False
    
    content = deploy.read_text(encoding='utf-8')
    
    # 检查节点目录映射
    expected_mappings = {
        "wk-edge-01": "node-wk-edge-01",
        "wk-iot-02": "node-wk-iot-02",
        "wk-storage-03": "node-wk-storage-03",
    }
    
    all_ok = True
    for node_name, dir_name in expected_mappings.items():
        if dir_name in content:
            log_pass(f"{node_name} -> {dir_name} 映射正确")
        else:
            log_fail(f"{node_name} -> {dir_name} 映射不存在")
            all_ok = False
    
    return all_ok

# ============ 测试 5: fallback 机制 ============
def test_fallback_mechanism():
    """验证脚本中的 fallback 机制"""
    print("\n" + "="*60)
    print("测试 5: fallback 机制验证")
    print("="*60)
    
    all_ok = True
    
    # 检查 backup.sh 和 restore.sh 的 IP fallback
    for script_name in ["backup.sh", "restore.sh"]:
        sp = SCRIPTS_DIR / script_name
        if not sp.exists():
            log_fail(f"{script_name} 不存在")
            all_ok = False
            continue
        
        content = sp.read_text(encoding='utf-8')
        
        # 检查是否有 IP fallback 逻辑
        if 'NODE_IP_MAP' in content or 'fallback' in content.lower():
            log_pass(f"{script_name}: 有 IP fallback 机制")
        else:
            log_warn(f"{script_name}: 未检测到明显的 IP fallback 机制")
        
        # 检查是否使用硬编码 IP
        for ip in ['192.168.1.101', '192.168.1.102', '192.168.1.103']:
            if ip in content:
                log_info(f"  {script_name}: 包含硬编码 IP {ip}")
    
    # 检查 deploy.sh 的 docker compose fallback
    deploy = SCRIPTS_DIR / "deploy.sh"
    if deploy.exists():
        content = deploy.read_text(encoding='utf-8')
        if 'docker-compose' in content and ('docker compose' in content or 'docker-compose' in content):
            log_pass("deploy.sh: 有 docker-compose/docker compose fallback")
    
    return all_ok

# ============ 测试 6: health-check 变量检查 ============
def test_health_check_variables():
    """验证 health-check.sh 变量声明"""
    print("\n" + "="*60)
    print("测试 6: health-check.sh 变量检查")
    print("="*60)
    
    script = SCRIPTS_DIR / "health-check.sh"
    if not script.exists():
        log_fail("health-check.sh 不存在")
        return False
    
    content = script.read_text(encoding='utf-8')
    
    all_ok = True
    
    # 检查是否有 'local' 关键字在函数外使用
    lines = content.split('\n')
    in_function = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('function ') or stripped.startswith('function'):
            in_function = True
        elif stripped.startswith('}'):
            in_function = False
        elif 'local ' in stripped and not in_function:
            log_fail(f"health-check.sh: 'local' 在函数外使用: {stripped}")
            all_ok = False
    
    if all_ok:
        log_pass("health-check.sh: 变量作用域正确")
    
    return all_ok

# ============ 测试 7: cloudflared 命令参数 ============
def test_cloudflared_command():
    """验证 cloudflared 命令参数"""
    print("\n" + "="*60)
    print("测试 7: cloudflared 命令参数")
    print("="*60)
    
    all_ok = True
    
    # 检查 setup.sh
    setup = SCRIPTS_DIR / "setup.sh"
    if setup.exists():
        content = setup.read_text(encoding='utf-8')
        if 'cloudflared' in content:
            # 检查是否有 'run' 参数
            if 'tunnel --no-autoupdate run' in content or 'tunnel run' in content:
                log_pass("setup.sh: cloudflared 有 'run' 参数")
            else:
                log_warn("setup.sh: cloudflared 可能缺少 'run' 参数")
            
            # 检查是否有 token 相关逻辑
            if 'token' in content.lower():
                log_pass("setup.sh: cloudflared 有 token 逻辑")
    
    # 检查 docker-compose.yml
    for name, path in NODE_DIRS.items():
        dc = path / "docker-compose.yml"
        if dc.exists():
            content = dc.read_text(encoding='utf-8')
            if 'cloudflared' in content:
                if 'tunnel --no-autoupdate run' in content:
                    log_pass(f"{name}/docker-compose.yml: cloudflared 命令正确")
                else:
                    log_warn(f"{name}/docker-compose.yml: cloudflared 命令可能不完整")
    
    return all_ok

# ============ 测试 8: panel/app.py 错误处理 ============
def test_panel_app_error_handling():
    """验证 panel/app.py 错误处理"""
    print("\n" + "="*60)
    print("测试 8: panel/app.py 错误处理验证")
    print("="*60)
    
    app_file = PANEL_DIR / "app.py"
    if not app_file.exists():
        log_fail("panel/app.py 不存在")
        return False
    
    try:
        with open(app_file, encoding='utf-8') as f:
            content = f.read()
        
        # 检查 load_config 函数
        load_config = re.search(
            r'def load_config\(\):(.*?)(?=\ndef|\Z)',
            content, re.DOTALL
        )
        if not load_config:
            log_fail("未找到 load_config 函数")
            return False
        
        func_body = load_config.group(1)
        
        # 检查 try-except
        if 'try:' in func_body and 'except' in func_body:
            log_pass("load_config 有 try-except 错误处理")
        else:
            log_fail("load_config 缺少 try-except 错误处理")
        
        # 检查 FileNotFoundError
        if 'FileNotFoundError' in func_body:
            log_pass("load_config 处理 FileNotFoundError")
        
        # 检查 JSONDecodeError
        if 'JSONDecodeError' in func_body:
            log_pass("load_config 处理 JSONDecodeError")
        
        # 检查默认返回值
        if 'cluster_name' in func_body and 'nodes' in func_body:
            log_pass("load_config 有默认返回值")
        
        # 验证默认集群名称
        default_match = re.search(r'"cluster_name":\s*"([^"]+)"', func_body)
        if default_match:
            cluster_name = default_match.group(1)
            log_pass(f"默认集群名称: {cluster_name}")
        
        # 检查 CONFIG_PATH 使用环境变量
        config_env = re.search(
            r'CONFIG_PATH\s*=\s*.*os\.environ\.get\("PANEL_CONFIG"',
            content
        )
        if config_env:
            log_pass("CONFIG_PATH 使用环境变量 PANEL_CONFIG")
        else:
            log_warn("CONFIG_PATH 可能未使用环境变量")
        
        # 检查 run_ssh 函数
        if 'def run_ssh' in content:
            log_pass("有 run_ssh 函数")
        
        # 检查异常处理
        if 'except subprocess.TimeoutExpired' in content:
            log_pass("run_ssh 处理 TimeoutExpired 异常")
        
        if 'except Exception as e' in content:
            log_pass("run_ssh 处理通用异常")
        
        # 检查危险命令过滤
        dangerous_keywords = ['rm -rf', 'mkfs', 'dd if=', 'shutdown', 'reboot', 'poweroff']
        dangerous_found = [kw for kw in dangerous_keywords if kw in content]
        if dangerous_found:
            log_info(f"  危险命令过滤包含: {dangerous_found}")
        
        if 'dangerous' in content.lower() and 'for d in dangerous' in content:
            log_pass("exec_command 有危险命令过滤")
    
    except Exception as e:
        log_fail(f"panel/app.py 验证异常: {str(e)}")
        return False
    
    return True

# ============ 测试 9: install-services.sh xiaomusic 下载 ============
def test_xiaomusic_download():
    """验证 install-services.sh xiaomusic 下载逻辑"""
    print("\n" + "="*60)
    print("测试 9: install-services.sh xiaomusic 下载验证")
    print("="*60)
    
    script = SCRIPTS_DIR / "install-services.sh"
    if not script.exists():
        log_fail("install-services.sh 不存在")
        return False
    
    try:
        with open(script, encoding='utf-8') as f:
            content = f.read()
        
        # 检查 install_xiaomusic 函数
        func_match = re.search(
            r'install_xiaomusic\(\)\s*\n?\{([\s\S]*?)\n\}',
            content
        )
        if not func_match:
            log_fail("未找到 install_xiaomusic 函数")
            return False
        
        func_body = func_match.group(1)
        
        # 检查架构检测
        if 'aarch64|arm64' in func_body:
            log_pass("架构检测 aarch64/arm64")
        
        if 'x86_64' in func_body:
            log_pass("架构检测 x86_64")
        
        # 检查架构变量
        if 'arch="armv7' in func_body or 'arch = "armv7' in func_body:
            log_pass("默认架构为 armv7")
        
        # 检查下载 URL 处理
        if 'browser_download_url' in func_body:
            log_pass("使用 browser_download_url 处理下载链接")
        
        if 'grep.*linux.*arch' in func_body or re.search(r'grep.*linux.*arch', func_body):
            log_pass("下载 URL 按架构过滤")
        
        # 检查解压逻辑
        if 'tar xzf' in func_body:
            log_pass("使用 tar xzf 解压")
        
        # 检查临时目录创建
        if 'mktemp -d' in func_body:
            log_pass("使用 mktemp 创建临时目录")
    
    except Exception as e:
        log_fail(f"install-services.sh 验证异常: {str(e)}")
        return False
    
    return True

# ============ 测试 10: panel/install-service.sh 动态路径 ============
def test_panel_install_service():
    """验证 panel/install-service.sh 路径变量化"""
    print("\n" + "="*60)
    print("测试 10: panel/install-service.sh 验证")
    print("="*60)
    
    script = PANEL_DIR / "install-service.sh"
    if not script.exists():
        log_fail("panel/install-service.sh 不存在")
        return False
    
    try:
        with open(script, encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否使用变量
        if 'PANEL_DIR=' in content:
            log_pass("使用 PANEL_DIR 变量")
        
        # 检查路径变量化
        if 'dirname' in content:
            log_pass("路径使用变量化（使用 dirname）")
        else:
            log_warn("可能未使用路径变量化")
        
        # 检查是否包含硬编码路径
        hardcoded_patterns = [
            r'/mnt/sd/edge-01/panel',
            r'/mnt/sd/wk-edge/panel',
            r'/opt/onecloud/panel',
        ]
        has_hardcoded = False
        for pattern in hardcoded_patterns:
            if re.search(pattern, content):
                has_hardcoded = True
                log_fail(f"存在硬编码路径: {pattern}")
        
        if not has_hardcoded:
            log_pass("无硬编码路径")
        
        # 检查 systemd 服务创建
        if 'systemd/system' in content:
            log_pass("创建 systemd 服务文件")
        
        if 'ExecStart' in content:
            log_pass("服务有 ExecStart 配置")
        
        if 'WorkingDirectory' in content:
            log_pass("服务有 WorkingDirectory 配置")
    
    except Exception as e:
        log_fail(f"panel/install-service.sh 验证异常: {str(e)}")
        return False
    
    return True

# ============ 测试 11: 服务一致性检查 ============
def test_service_consistency():
    """验证节点配置与服务定义一致性"""
    print("\n" + "="*60)
    print("测试 11: 节点配置与服务定义一致性验证")
    print("="*60)
    
    try:
        # 读取 services.yaml
        with open(INVENTORY_DIR / "services.yaml", encoding='utf-8') as f:
            services_text = f.read()
        services_data = simple_yaml_parse(services_text)
        
        # 读取 panel config.json
        with open(PANEL_DIR / "config.json", encoding='utf-8') as f:
            panel_data = json.load(f)
        
        # 交叉验证
        log_info("交叉验证 services.yaml 和 panel/config.json:")
        
        yaml_services = services_data.get("services", {})
        panel_services = {}
        
        for node in panel_data.get("nodes", []):
            node_name = node["name"]
            svc_names = {s["name"] for s in node.get("services", [])}
            panel_services[node_name] = svc_names
        
        for node_name, panel_svcs in panel_services.items():
            yaml_node_svcs = {
                name for name, config in yaml_services.items()
                if config.get("node") == node_name
            }
            
            missing_in_panel = yaml_node_svcs - panel_svcs
            extra_in_panel = panel_svcs - yaml_node_svcs
            
            if not missing_in_panel and not extra_in_panel:
                log_pass(f"节点 {node_name}: services.yaml 与 panel 一致")
            else:
                if missing_in_panel:
                    log_warn(f"节点 {node_name}: panel 缺少服务 {missing_in_panel}")
                if extra_in_panel:
                    log_warn(f"节点 {node_name}: panel 多余服务 {extra_in_panel}")
        
        # 验证端口映射
        log_info("验证服务端口映射:")
        for svc_name, svc_config in yaml_services.items():
            if svc_config.get("container"):
                ports = svc_config.get("ports", [])
                for port_entry in ports:
                    port = port_entry.split(":")[0] if ":" in port_entry else port_entry
                    log_info(f"  {svc_name}: 端口 {port}")
    
    except Exception as e:
        log_fail(f"服务一致性验证异常: {str(e)}")
        return False
    
    return True

# ============ 测试 12: 功能清单与代码一致性 ============
def test_feature_consistency():
    """验证所有功能清单文件与代码实现的一致性"""
    print("\n" + "="*60)
    print("测试 12: 功能清单与代码一致性验证")
    print("="*60)
    
    all_ok = True
    
    # 1. 检查 services.yaml 定义的每个服务是否在对应节点的 docker-compose.yml 中存在
    print("\n  1.1 services.yaml vs docker-compose.yml:")
    try:
        with open(INVENTORY_DIR / "services.yaml", encoding='utf-8') as f:
            services_text = f.read()
        services_data = simple_yaml_parse(services_text)
        yaml_services = services_data.get("services", {})
        
        for svc_name, svc_config in yaml_services.items():
            node_name = svc_config.get("node", "")
            if not node_name:
                continue
            node_dir = NODE_DIRS.get(node_name)
            if not node_dir:
                log_warn(f"  服务 {svc_name} 的节点 {node_name} 目录不存在")
                continue
            
            dc_file = node_dir / "docker-compose.yml"
            if not dc_file.exists():
                log_warn(f"  节点 {node_name} 的 docker-compose.yml 不存在")
                continue
            
            dc_content = dc_file.read_text(encoding='utf-8')
            if svc_name in dc_content:
                log_pass(f"  {svc_name} 在 {node_name}/docker-compose.yml 中定义")
            else:
                log_warn(f"  {svc_name} 在 services.yaml 中定义但未在 {node_name}/docker-compose.yml 中找到")
    except Exception as e:
        log_fail(f"  services.yaml 验证异常: {str(e)}")
        all_ok = False
    
    # 2. 检查 README.md 中描述的功能是否都有对应实现
    print("\n  1.2 README.md 功能描述验证:")
    readme = PROJECT_ROOT / "README.md"
    if readme.exists():
        readme_content = readme.read_text(encoding='utf-8')
        # 检查关键功能关键词
        feature_keywords = [
            ("AdGuard Home", "adguard"),
            ("Docker", "docker"),
            ("WireGuard", "wireguard"),
            ("cloudflared", "cloudflared"),
            ("Memos", "memos"),
            ("Syncthing", "syncthing"),
            ("Aria2", "aria2"),
            ("Ariang", "ariang"),
            ("CUPS", "cups"),
            ("Home Assistant", "homeassistant"),
        ]
        for feature, keyword in feature_keywords:
            if feature.lower() in readme_content.lower():
                # 检查是否有对应实现
                has_impl = False
                for name, path in NODE_DIRS.items():
                    dc = path / "docker-compose.yml"
                    if dc.exists() and keyword in dc.read_text(encoding='utf-8').lower():
                        has_impl = True
                        break
                if has_impl:
                    log_pass(f"  {feature}: README 有描述，代码有实现")
                else:
                    log_warn(f"  {feature}: README 有描述，但代码中未找到实现")
    else:
        log_warn("  README.md 不存在，跳过")
    
    # 3. 检查 architecture.md 中描述的架构与实际节点目录一致
    print("\n  1.3 architecture.md 架构描述验证:")
    arch = PROJECT_ROOT / "architecture.md"
    if arch.exists():
        arch_content = arch.read_text(encoding='utf-8')
        for node_name in NODE_DIRS:
            if node_name in arch_content:
                log_pass(f"  节点 {node_name} 在 architecture.md 中描述")
            else:
                log_warn(f"  节点 {node_name} 未在 architecture.md 中提及")
    else:
        log_warn("  architecture.md 不存在，跳过")
    
    # 4. 检查 .env.example 与各节点 .env 的变量一致性
    print("\n  1.4 .env 变量一致性验证:")
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        env_example_vars = set()
        with open(env_example, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    var_name = line.split('=')[0].strip()
                    env_example_vars.add(var_name)
        
        for node_name, node_dir in NODE_DIRS.items():
            env_file = node_dir / ".env"
            if env_file.exists():
                node_env_vars = set()
                with open(env_file, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            var_name = line.split('=')[0].strip()
                            node_env_vars.add(var_name)
                
                missing = env_example_vars - node_env_vars
                extra = node_env_vars - env_example_vars
                if missing:
                    log_warn(f"  {node_name}/.env 缺少变量: {missing}")
                if extra:
                    log_info(f"  {node_name}/.env 额外变量: {extra}")
                if not missing and not extra:
                    log_pass(f"  {node_name}/.env 变量与 .env.example 一致")
    else:
        log_warn("  .env.example 不存在，跳过")
    
    return all_ok

# ============ 测试执行 ============
def run_tests():
    """执行所有测试"""
    print("=" * 60)
    print("OneCloud Cluster 功能验证")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    
    # 收集所有测试
    tests = [
        ("配置文件完整性", test_config_files),
        ("节点目录结构", test_node_directories),
        ("脚本语法检查", test_script_syntax),
        ("deploy.sh 节点映射", test_deploy_node_mapping),
        ("fallback 机制", test_fallback_mechanism),
        ("health-check 变量检查", test_health_check_variables),
        ("cloudflared 命令参数", test_cloudflared_command),
        ("panel 错误处理", test_panel_app_error_handling),
        ("xiaomusic 下载", test_xiaomusic_download),
        ("panel install-service", test_panel_install_service),
        ("服务一致性", test_service_consistency),
        ("功能清单一致性", test_feature_consistency),
    ]
    
    for test_name, test_func in tests:
        log_info(f"执行测试: {test_name}")
        try:
            test_func()
        except Exception as e:
            log_fail(f"测试 '{test_name}' 异常: {str(e)}")
    
    # 生成报告
    generate_report()
    
    success = FAILED == 0
    return success

# ============ 报告生成 ============
def generate_report():
    """生成测试报告"""
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)
    
    total = PASSED + FAILED + WARNINGS
    
    print(f"\n  总计: {total} 项")
    print(color(f"  通过: {PASSED}", GREEN))
    print(color(f"  失败: {FAILED}", RED))
    print(color(f"  警告: {WARNINGS}", YELLOW))
    
    if FAILED == 0:
        print(f"\n  {color('✓ 所有测试通过！', GREEN)}")
    else:
        print(f"\n  {color(f'✗ 有 {FAILED} 项测试失败，需要修复', RED)}")
    
    # 列出警告
    warnings = [(name, detail) for status, name, detail in TEST_RESULTS if status == "WARN"]
    if warnings:
        print(f"\n  警告列表 ({len(warnings)} 项):")
        for name, detail in warnings:
            print(f"    - {name}")
            if detail:
                print(f"      {detail}")
    
    # 列出失败
    failures = [(name, detail) for status, name, detail in TEST_RESULTS if status == "FAIL"]
    if failures:
        print(f"\n  失败列表 ({len(failures)} 项):")
        for name, detail in failures:
            print(f"    - {name}")
            if detail:
                print(f"      {detail}")
    
    # 保存报告
    report_file = PROJECT_ROOT / "test_report.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("OneCloud Cluster 测试报告\n")
        f.write("=" * 60 + "\n")
        f.write(f"通过: {PASSED}\n")
        f.write(f"失败: {FAILED}\n")
        f.write(f"警告: {WARNINGS}\n")
        f.write(f"总计: {total}\n\n")
        
        f.write("详细信息:\n")
        f.write("-" * 60 + "\n")
        for status, name, detail in TEST_RESULTS:
            f.write(f"[{status}] {name}")
            if detail:
                f.write(f" - {detail}")
            f.write("\n")
    
    log_info(f"报告已保存到: {report_file}")
    
    return FAILED == 0

# ============ 主入口 ============
def main():
    print("=" * 60)
    print("OneCloud Cluster 功能验证脚本")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    
    # 执行所有测试
    success = run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()nv.example 一致\")\n    else:\n        log_warn(\"  .env.example 不存在，跳过\")\n    \n    return all_ok\n\n# ============ 测试执行 ============\ndef run_tests():\n    \"\"\"执行所有测试\"\"\"\n    print(\"=\" * 60)\n    print(\"OneCloud Cluster 功能验证\")\n    print(\"=\" * 60)\n    print(f\"项目根目录: {PROJECT_ROOT}\")\n    \n    # 收集所有测试\n    tests = [\n        (\"配置文件完整性\", test_config_files),\n        (\"节点目录结构\", test_node_directories),\n        (\"脚本语法检查\", test_script_syntax),\n        (\"deploy.sh 节点映射\", test_deploy_node_mapping),\n        (\"fallback 机制\", test_fallback_mechanism),\n        (\"health-check 变量检查\", test_health_check_variables),\n        (\"cloudflared 命令参数\", test_cloudflared_command),\n        (\"panel 错误处理\", test_panel_app_error_handling),\n        (\"xiaomusic 下载\", test_xiaomusic_download),\n        (\"panel install-service\", test_panel_install_service),\n        (\"服务一致性\", test_service_consistency),\n        (\"功能清单一致性\", test_feature_consistency),\n    ]\n    \n    for test_name, test_func in tests:\n        log_info(f\"执行测试: {test_name}\")\n        try:\n            test_func()\n        except Exception as e:\n            log_fail(f\"测试 '{test_name}' 异常: {str(e)}\")\n    \n    # 生成报告\n    generate_report()\n    \n    success = FAILED == 0\n    return success\n\n# ============ 报告生成 ============\ndef generate_report():\n    \"\"\"生成测试报告\"\"\"\n    print(\"\\n\" + \"=\" * 60)\n    print(\"测试报告\")\n    print(\"=\" * 60)\n    \n    total = PASSED + FAILED + WARNINGS\n    \n    print(f\"\\n  总计: {total} 项\")\n    print(color(f\"  通过: {PASSED}\", GREEN))\n    print(color(f\"  失败: {FAILED}\", RED))\n    print(color(f\"  警告: {WARNINGS}\", YELLOW))\n    \n    if FAILED == 0:\n        print(f\"\\n  {color('✓ 所有测试通过！', GREEN)}\")\n    else:\n        print(f\"\\n  {color(f'✗ 有 {FAILED} 项测试失败，需要修复', RED)}\")\n    \n    # 列出警告\n    warnings = [(name, detail) for status, name, detail in TEST_RESULTS if status == \"WARN\"]\n    if warnings:\n        print(f\"\\n  警告列表 ({len(warnings)} 项):\")\n        for name, detail in warnings:\n            print(f\"    - {name}\")\n            if detail:\n                print(f\"      {detail}\")\n    \n    # 列出失败\n    failures = [(name, detail) for status, name, detail in TEST_RESULTS if status == \"FAIL\"]\n    if failures:\n        print(f\"\\n  失败列表 ({len(failures)} 项):\")\n        for name, detail in failures:\n            print(f\"    - {name}\")\n            if detail:\n                print(f\"      {detail}\")\n    \n    # 保存报告\n    report_file = PROJECT_ROOT / \"test_report.txt\"\n    with open(report_file, \"w\", encoding=\"utf-8\") as f:\n        f.write(\"OneCloud Cluster 测试报告\\n\")\n        f.write(\"=\" * 60 + \"\\n\")\n        f.write(f\"通过: {PASSED}\\n\")\n        f.write(f\"失败: {FAILED}\\n\")\n        f.write(f\"警告: {WARNINGS}\\n\")\n        f.write(f\"总计: {total}\\n\\n\")\n        \n        f.write(\"详细信息:\\n\")\n        f.write(\"-\" * 60 + \"\\n\")\n        for status, name, detail in TEST_RESULTS:\n            f.write(f\"[{status}] {name}\")\n            if detail:\n                f.write(f\" - {detail}\")\n            f.write(\"\\n\")\n    \n    log_info(f\"报告已保存到: {report_file}\")\n    \n    return FAILED == 0\n\n# ============ 主入口 ============\ndef main():\n    print(\"=\" * 60)\n    print(\"OneCloud Cluster 功能验证脚本\")\n    print(\"=\" * 60)\n    print(f\"项目根目录: {PROJECT_ROOT}\")\n    \n    # 执行所有测试\n    success = run_tests()\n    \n    sys.exit(0 if success else 1)\n\nif __name__ == \"__main__\":\n    main()\n"}]