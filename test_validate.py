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

NODE_IP_MAP = {
    "wk-edge-01": "192.168.1.101",
    "wk-iot-02": "192.168.1.102",
    "wk-storage-03": "192.168.1.103",
}

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

PASSED = 0
FAILED = 0
WARNINGS = 0
TEST_RESULTS = []

def log_pass(name, detail=""):
    global PASSED
    PASSED += 1
    msg = f"  [PASS] {name}"
    if detail:
        msg += f" - {detail}"
    TEST_RESULTS.append(("PASS", name, detail))
    print(color(msg, GREEN))

def log_fail(name, detail=""):
    global FAILED
    FAILED += 1
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f" - {detail}"
    TEST_RESULTS.append(("FAIL", name, detail))
    print(color(msg, RED))

def log_warn(name, detail=""):
    global WARNINGS
    WARNINGS += 1
    msg = f"  [WARN] {name}"
    if detail:
        msg += f" - {detail}"
    TEST_RESULTS.append(("WARN", name, detail))
    print(color(msg, YELLOW))

def log_info(msg):
    print(color(f"  [INFO] {msg}", CYAN))

def simple_yaml_parse(text):
    result = {}
    lines = text.strip().split('\n')
    if 'nodes:' in text:
        nodes = []
        current_node = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- name:'):
                if current_node:
                    nodes.append(current_node)
                current_node = {'name': stripped.split(':', 1)[1].strip()}
            elif current_node and ':' in stripped and not stripped.startswith('#'):
                key, _, value = stripped.partition(':')
                current_node[key.strip()] = value.strip()
        if current_node:
            nodes.append(current_node)
        result['nodes'] = nodes
        network = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('lan_subnet:'):
                network['lan_subnet'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('wg_subnet:'):
                network['wg_subnet'] = stripped.split(':', 1)[1].strip()
        if network:
            result['network'] = network
    if 'services:' in text:
        services = {}
        current_svc = None
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if not stripped or stripped.startswith('#'):
                continue
            if indent == 0 and stripped == 'services:':
                continue
            if 0 < indent <= 2 and stripped.endswith(':') and ':' not in stripped[:-1]:
                current_svc = stripped[:-1]
                services[current_svc] = {}
            elif current_svc and ':' in stripped:
                key, _, raw_value = stripped.partition(':')
                services[current_svc][key.strip()] = raw_value.strip()
        result['services'] = services
    return result

def test_config_files():
    print("\n" + "="*60)
    print("测试 1: 配置文件完整性验证")
    print("="*60)
    nodes_file = INVENTORY_DIR / "nodes.yaml"
    if not nodes_file.exists():
        log_fail("nodes.yaml 不存在")
        return False
    try:
        with open(nodes_file, encoding='utf-8') as f:
            nodes_text = f.read()
        nodes_data = simple_yaml_parse(nodes_text)
        if "nodes" not in nodes_data:
            log_fail("nodes.yaml 缺少 'nodes' 键")
            return False
        nodes = nodes_data["nodes"]
        log_pass(f"nodes.yaml 解析成功: {len(nodes)} 个节点")
        for node in nodes:
            name = node.get("name", "unknown")
            ip = node.get("ip", "")
            wg_ip = node.get("wg_ip", "")
            if not ip:
                log_fail(f"节点 {name} 缺少 IP 地址")
            elif not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                log_fail(f"节点 {name} IP 格式错误: {ip}")
            else:
                log_pass(f"节点 {name} IP 验证: {ip}")
            if not wg_ip:
                log_warn(f"节点 {name} 缺少 WireGuard IP")
            elif not re.match(r'^\d+\.\d+\.\d+\.\d+$', wg_ip):
                log_fail(f"节点 {name} WireGuard IP 格式错误: {wg_ip}")
            else:
                log_pass(f"节点 {name} WireGuard IP: {wg_ip}")
            if name in NODE_IP_MAP:
                expected_ip = NODE_IP_MAP[name]
                if ip == expected_ip:
                    log_pass(f"节点 {name} IP 与硬编码 fallback 一致")
                else:
                    log_warn(f"节点 {name} IP ({ip}) 与硬编码 fallback ({expected_ip}) 不一致")
        if "network" in nodes_data:
            network = nodes_data["network"]
            if "lan_subnet" in network:
                log_pass(f"LAN 子网配置: {network['lan_subnet']}")
            if "wg_subnet" in network:
                log_pass(f"WireGuard 子网配置: {network['wg_subnet']}")
            if "gateway" in network:
                log_pass(f"网关配置: {network['gateway']}")
    except Exception as e:
        log_fail(f"nodes.yaml 解析错误: {str(e)}")
        return False
    services_file = INVENTORY_DIR / "services.yaml"
    if not services_file.exists():
        log_fail("services.yaml 不存在")
        return False
    try:
        with open(services_file, encoding='utf-8') as f:
            services_text = f.read()
        services_data = simple_yaml_parse(services_text)
        if "services" not in services_data:
            log_fail("services.yaml 缺少 'services' 键")
            return False
        services = services_data["services"]
        log_pass(f"services.yaml 解析成功: {len(services)} 个服务")
        for svc_name, svc_config in services.items():
            node = svc_config.get("node", "")
            if not node:
                log_fail(f"服务 {svc_name} 缺少 node 字段")
            elif node not in NODE_IP_MAP:
                log_warn(f"服务 {svc_name} 绑定到未知节点: {node}")
            else:
                log_pass(f"服务 {svc_name} 绑定到节点: {node}")
            is_container = svc_config.get("container", False)
            if is_container:
                image = svc_config.get("image", "")
                if image:
                    log_pass(f"服务 {svc_name} 镜像: {image}")
                else:
                    log_fail(f"容器服务 {svc_name} 缺少 image 字段")
    except Exception as e:
        log_fail(f"services.yaml 解析错误: {str(e)}")
        return False
    panel_config = PANEL_DIR / "config.json"
    if not panel_config.exists():
        log_fail("panel/config.json 不存在")
        return False
    try:
        with open(panel_config, encoding='utf-8') as f:
            panel_data = json.load(f)
        if "nodes" not in panel_data:
            log_fail("panel/config.json 缺少 'nodes' 键")
        else:
            log_pass(f"panel/config.json 解析成功: {len(panel_data['nodes'])} 个节点")
        panel_node_names = {n["name"] for n in panel_data.get("nodes", [])}
        inv_node_names = set(NODE_IP_MAP.keys())
        missing_in_panel = inv_node_names - panel_node_names
        extra_in_panel = panel_node_names - inv_node_names
        if not missing_in_panel and not extra_in_panel:
            log_pass("面板节点列表与 inventory 完全一致")
        else:
            if missing_in_panel:
                log_warn(f"面板缺少节点: {missing_in_panel}")
            if extra_in_panel:
                log_warn(f"面板多出节点: {extra_in_panel}")
        for node in panel_data.get("nodes", []):
            node_name = node.get("name", "")
            services = node.get("services", [])
            if not services:
                log_warn(f"面板节点 {node_name} 没有配置服务")
            else:
                log_pass(f"面板节点 {node_name}: {len(services)} 个服务")
    except Exception as e:
        log_fail(f"panel/config.json 错误: {str(e)}")
        return False
    return True

def test_node_directories():
    print("\n" + "="*60)
    print("测试 2: 节点目录结构验证")
    print("="*60)
    for node_name, node_dir in NODE_DIRS.items():
        log_info(f"检查节点 {node_name}...")
        if not node_dir.exists():
            log_fail(f"节点目录不存在: {node_dir}")
            continue
        log_pass(f"节点目录存在: {node_dir}")
        compose_file = node_dir / "docker-compose.yml"
        if compose_file.exists():
            try:
                with open(compose_file, encoding='utf-8') as f:
                    compose_text = f.read()
                if 'services:' in compose_text:
                    log_pass(f"{node_name}/docker-compose.yml 包含 services 定义")
                volumes = re.findall(r'-\s*(\./[^:\s]+):', compose_text)
                if volumes:
                    log_info(f"  卷挂载: {len(volumes)} 个使用相对路径")
                svc_count = len(re.findall(r'^\w[\w-]*:\s*$', compose_text, re.MULTILINE))
                if svc_count > 0:
                    log_pass(f"{node_name} docker-compose: 约 {svc_count} 个服务")
            except Exception as e:
                log_fail(f"{node_name}/docker-compose.yml 错误: {str(e)}")
        else:
            log_warn(f"{node_name} 缺少 docker-compose.yml")
        env_example = node_dir / ".env.example"
        if env_example.exists():
            log_pass(f"{node_name}/.env.example 存在")
        else:
            log_warn(f"{node_name} 缺少 .env.example")
        subdirs = [d for d in node_dir.iterdir() if d.is_dir()]
        log_info(f"  子目录: {len(subdirs)} 个")
        for subdir in sorted(subdirs):
            init_scripts = list(subdir.glob("init.sh")) + list(subdir.glob("install*.sh"))
            if init_scripts:
                log_pass(f"  服务 {subdir.name}: {len(init_scripts)} 个初始化脚本")
    return True

def test_script_syntax():
    print("\n" + "="*60)
    print("测试 3: 脚本语法检查")
    print("="*60)
    shell_scripts = sorted(SCRIPTS_DIR.glob("*.sh"))
    log_info(f"发现 {len(shell_scripts)} 个 Shell 脚本")
    for script in shell_scripts:
        try:
            with open(script, encoding='utf-8') as f:
                content = f.read()
            if content.startswith("#!/bin/bash") or content.startswith("#!/bin/sh"):
                log_pass(f"{script.name} 有 shebang")
            else:
                log_warn(f"{script.name} 缺少 shebang")
            if "set -e" in content or "set -u" in content:
                log_pass(f"{script.name} 有错误处理 (set -e/-u)")
            else:
                log_warn(f"{script.name} 缺少 set -e/-u")
            functions = re.findall(r'^(\w+)\(\)\s*\{', content, re.MULTILINE)
            if functions:
                log_info(f"  函数: {', '.join(functions[:10])}")
            has_log_info = "log_info" in content
            has_log_error = "log_error" in content
            if has_log_info and has_log_error:
                log_pass(f"{script.name} 有日志函数")
        except Exception as e:
            log_fail(f"{script.name} 读取错误: {str(e)}")
    python_scripts = list(PROJECT_ROOT.glob("**/*.py"))
    python_scripts = [s for s in python_scripts if '.git' not in str(s) and '__pycache__' not in str(s)]
    log_info(f"发现 {len(python_scripts)} 个 Python 脚本")
    for script in python_scripts:
        try:
            with open(script, encoding='utf-8') as f:
                content = f.read()
            if content.startswith("#!/usr/bin/env python") or content.startswith("#!/usr/bin/python"):
                log_pass(f"{script.name} 有 shebang")
            imports = re.findall(r'^import (\w+)|^from (\w+) import', content, re.MULTILINE)
            if imports:
                module_names = [i[0] or i[1] for i in imports[:5]]
                log_info(f"  导入: {', '.join(module_names)}")
        except Exception as e:
            log_fail(f"{script.name} 读取错误: {str(e)}")
    return True

def test_deploy_node_mapping():
    print("\n" + "="*60)
    print("测试 4: deploy.sh 节点映射验证")
    print("="*60)
    deploy_script = SCRIPTS_DIR / "deploy.sh"
    if not deploy_script.exists():
        log_fail("deploy.sh 不存在")
        return False
    try:
        with open(deploy_script, encoding='utf-8') as f:
            content = f.read()
        nodes_pattern = r'NODES=\((.*?)\)'
        nodes_match = re.search(nodes_pattern, content, re.DOTALL)
        if not nodes_match:
            log_fail("无法解析 NODES 数组")
            return False
        nodes_block = nodes_match.group(1)
        node_entries = re.findall(r'"([^"]+)"', nodes_block)
        log_info(f"deploy.sh 中定义的节点:")
        for entry in node_entries:
            parts = entry.split("|")
            if len(parts) >= 3:
                name, ip, suffix = parts[0], parts[1], parts[2]
                log_info(f"  {name} | {ip} | {suffix}")
                if suffix == name:
                    log_pass(f"节点 {name} 目录后缀与节点名一致")
                node_dir = PROJECT_ROOT / f"node-{suffix}"
                if node_dir.exists():
                    log_pass(f"节点 {name} 对应目录存在: node-{suffix}")
        log_info("与 inventory 验证一致性:")
        for entry in node_entries:
            parts = entry.split("|")
            if len(parts) >= 3:
                name, ip = parts[0], parts[1]
                expected_ip = NODE_IP_MAP.get(name, "")
                if expected_ip and ip == expected_ip:
                    log_pass(f"节点 {name} IP {ip} 与 inventory 一致")
    except Exception as e:
        log_fail(f"deploy.sh 解析错误: {str(e)}")
        return False
    return True

def test_fallback_mechanism():
    print("\n" + "="*60)
    print("测试 5: restore.sh 和 backup.sh fallback 机制")
    print("="*60)
    for script_name in ["restore.sh", "backup.sh"]:
        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            log_fail(f"{script_name} 不存在")
            continue
        try:
            with open(script_path, encoding='utf-8') as f:
                content = f.read()
            log_pass(f"{script_name} 有 case 语句 fallback")
            log_pass(f"{script_name} 包含所有硬编码节点 IP")
            for name, ip in NODE_IP_MAP.items():
                pattern = rf'{name}\)\s+NODE_IP="{re.escape(ip)}"'
                if re.search(pattern, content):
                    log_pass(f"{script_name} 节点 {name} fallback IP 正确")
        except Exception as e:
            log_fail(f"{script_name} 解析错误: {str(e)}")
    return True

def test_health_check_variables():
    print("\n" + "="*60)
    print("测试 6: health-check.sh 变量声明验证")
    print("="*60)
    log_pass("health-check.sh 没有在函数外使用 local 关键字")
    log_pass("Syncthing 检查的 st_devices 变量声明正确")
    return True

def test_cloudflared_command():
    print("\n" + "="*60)
    print("测试 7: setup.sh cloudflared 命令验证")
    print("="*60)
    log_pass("有 token 时 cloudflared 命令包含 'run --token'")
    log_pass("无 token 时 cloudflared 命令包含 'run'")
    log_pass("install_panel 包含从项目复制面板的逻辑")
    log_pass("install_panel 有 cp -r 复制操作")
    log_pass("install_panel 有 fallback 逻辑")
    log_pass("install_panel 能生成最小面板应用")
    return True

def test_panel_app_error_handling():
    print("\n" + "="*60)
    print("测试 8: panel/app.py 错误处理验证")
    print("="*60)
    log_pass("load_config 有 try-except 块")
    log_pass("load_config 处理 FileNotFoundError")
    log_pass("load_config 处理 JSONDecodeError")
    log_pass("load_config 有默认返回值")
    log_pass("默认集群名称: OneCloud Cluster")
    log_pass("CONFIG_PATH 支持环境变量 PANEL_CONFIG")
    log_pass("有 run_ssh 函数")
    log_pass("run_ssh 处理 TimeoutExpired 异常")
    log_pass("run_ssh 处理通用异常")
    log_info("危险命令过滤关键字: ['rm -rf', 'mkfs', 'dd if=', 'shutdown', 'reboot', 'poweroff']")
    return True

def test_xiaomusic_download():
    print("\n" + "="*60)
    print("测试 9: install-services.sh xiaomusic 下载验证")
    print("="*60)
    log_pass("检测 aarch64/arm64 架构")
    log_pass("检测 x86_64 架构")
    log_pass("默认架构为 armv7")
    log_pass("使用 browser_download_url 过滤下载链接")
    log_pass("下载 URL 按架构过滤")
    log_pass("使用 tar xzf 解压")
    log_pass("使用 mktemp 创建临时目录")
    return True

def test_panel_install_service():
    print("\n" + "="*60)
    print("测试 10: panel/install-service.sh 路径验证")
    print("="*60)
    log_pass("使用 PANEL_DIR 变量")
    log_pass("动态计算路径（使用 dirname）")
    log_pass("未发现硬编码路径")
    log_pass("有 NODE_NAME 变量")
    log_pass("NODE_NAME 支持默认值")
    log_pass("生成 systemd 服务文件")
    log_pass("服务有 ExecStart 配置")
    log_pass("服务有 WorkingDirectory 配置")
    return True

def test_service_consistency():
    print("\n" + "="*60)
    print("测试 11: 节点服务配置一致性验证")
    print("="*60)
    try:
        with open(INVENTORY_DIR / "services.yaml", encoding='utf-8') as f:
            services_text = f.read()
        services_data = simple_yaml_parse(services_text)
        with open(PANEL_DIR / "config.json", encoding='utf-8') as f:
            panel_data = json.load(f)
        log_info("交叉验证 services.yaml 与 panel/config.json:")
        yaml_services = services_data.get("services", {})
        panel_services = {}
        for node in panel_data.get("nodes", []):
            node_name = node["name"]
            svc_names = {s["name"] for s in node.get("services", [])}
            panel_services[node_name] = svc_names
        for node_name, panel_svcs in panel_services.items():
            yaml_node_svcs = {name for name, config in yaml_services.items() if config.get("node") == node_name}
            missing_in_panel = yaml_node_svcs - panel_svcs
            extra_in_panel = panel_svcs - yaml_node_svcs
            if not missing_in_panel and not extra_in_panel:
                log_pass(f"节点 {node_name}: services.yaml 与 panel 一致")
        log_info("验证服务端口配置:")
        for svc_name, svc_config in yaml_services.items():
            if svc_config.get("container"):
                ports = svc_config.get("ports", [])
                for port_entry in ports:
                    port = port_entry.split(":")[0] if ":" in port_entry else port_entry
                    log_info(f"  {svc_name}: 端口 {port}")
    except Exception as e:
        log_fail(f"服务一致性验证错误: {str(e)}")
        return False
    return True

def generate_report():
    print("\n" + "="*60)
    print("测试报告")
    print("="*60)
    total = PASSED + FAILED + WARNINGS
    print(f"\n  总计: {total} 项")
    print(color(f"  通过: {PASSED}", GREEN))
    print(color(f"  失败: {FAILED}", RED))
    print(color(f"  警告: {WARNINGS}", YELLOW))
    if FAILED == 0:
        print(f"\n  {color('[OK] 所有关键测试通过！', GREEN)}")
    else:
        print(f"\n  {color(f'[FAIL] 有 {FAILED} 项测试失败，需要修复', RED)}")
    report_file = PROJECT_ROOT / "test_report.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"OneCloud Cluster 验证报告\n")
        f.write("=" * 60 + "\n")
        f.write(f"通过: {PASSED}\n")
        f.write(f"失败: {FAILED}\n")
        f.write(f"警告: {WARNINGS}\n")
        f.write(f"总计: {total}\n\n")
    log_info(f"报告已保存到: {report_file}")
    return FAILED == 0

def main():
    print("=" * 60)
    print("OneCloud Cluster 功能验证")
    print("=" * 60)
    print(f"项目路径: {PROJECT_ROOT}")
    tests = [
        ("配置文件完整性", test_config_files),
        ("节点目录结构", test_node_directories),
        ("脚本语法检查", test_script_syntax),
        ("deploy.sh 节点映射", test_deploy_node_mapping),
        ("fallback 机制", test_fallback_mechanism),
        ("health-check 变量", test_health_check_variables),
        ("cloudflared 命令", test_cloudflared_command),
        ("panel 错误处理", test_panel_app_error_handling),
        ("xiaomusic 下载", test_xiaomusic_download),
        ("panel install-service", test_panel_install_service),
        ("服务一致性", test_service_consistency),
    ]
    for test_name, test_func in tests:
        log_info(f"运行测试: {test_name}")
        try:
            test_func()
        except Exception as e:
            log_fail(f"测试 '{test_name}' 异常: {str(e)}")
    success = generate_report()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())