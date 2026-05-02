#!/usr/bin/env python3
"""
硅迹开源 - AI 交互式控制台 v2
全流程可视化 + RTL/封装导入 + 实时日志
"""

import os
import sys
import json
import subprocess
import threading
import time
import shutil
import shlex
import uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# ============================================================
# 路径配置
# ============================================================
PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IEDA_BIN = os.environ.get('IEDA_BIN', os.path.expanduser('~/iEDA/scripts/design/sky130_gcd/iEDA'))
PDK_ROOT = os.environ.get('PDK_ROOT', os.path.expanduser('~/.volare'))
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, 'artifacts')
SYNTH_RESULT_DIR = os.path.join(ARTIFACTS_DIR, 'synthesis')
BACKEND_RESULT_DIR = os.path.join(ARTIFACTS_DIR, 'backend')
BACKEND_STA_DIR = os.path.join(BACKEND_RESULT_DIR, 'sta')
KICAD_RESULT_DIR = os.path.join(ARTIFACTS_DIR, 'kicad', 'picorv32_test_board')
TEMP_DIR = os.path.join(ARTIFACTS_DIR, 'temp')
UPLOAD_DIR = os.path.join(PROJECT_ROOT, 'uploads')
RTL_DIR = os.path.join(PROJECT_ROOT, 'rtl')
FOOTPRINT_DIR = os.path.join(PROJECT_ROOT, 'kicad/footprints')
SYMBOL_DIR = os.path.join(PROJECT_ROOT, 'kicad/symbols')

os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, 'rtl'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, 'packages'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, 'footprints'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, 'symbols'), exist_ok=True)

# ============================================================
# 全局状态
# ============================================================
logs = []
flow_state = {
    'current_step': 'idle',
    'steps': {
        'synthesis': {'status': 'pending', 'name': 'Yosys 综合', 'tool': 'Yosys', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
        'floorplan': {'status': 'pending', 'name': 'Floorplan', 'tool': 'iEDA iFP', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
        'placement': {'status': 'pending', 'name': 'Placement', 'tool': 'iEDA iPL', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
        'cts': {'status': 'pending', 'name': 'CTS', 'tool': 'iEDA iCTS', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
        'routing': {'status': 'pending', 'name': 'Routing', 'tool': 'iEDA iRT', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
        'sta': {'status': 'pending', 'name': 'STA', 'tool': 'iEDA iSTA', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
        'gdsii': {'status': 'pending', 'name': 'GDSII', 'tool': 'iEDA GDS', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
        'kicad': {'status': 'pending', 'name': 'KiCad 导出', 'tool': 'KiCad', 'progress': 0, 'output': None, 'error': None, 'start': None, 'end': None},
    },
    'tools': {
        'yosys': {'name': 'Yosys', 'version': 'checking...', 'status': 'unknown', 'path': 'yosys'},
        'ieda': {'name': 'iEDA', 'version': 'checking...', 'status': 'unknown', 'path': IEDA_BIN},
        'kicad': {'name': 'KiCad', 'version': 'checking...', 'status': 'unknown', 'path': 'kicad'},
        'pdk': {'name': 'SKY130 PDK', 'version': 'checking...', 'status': 'unknown', 'path': PDK_ROOT},
        'volare': {'name': 'Volare', 'version': 'checking...', 'status': 'unknown', 'path': 'volare'},
    },
    'current_rtl': None,
    'current_design': 'picorv32',
    'running': False,
}
state_lock = threading.Lock()

# ============================================================
# 日志系统
# ============================================================
def add_log(message, level='info', step=None):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {'timestamp': timestamp, 'level': level, 'message': message, 'step': step}
    logs.append(log_entry)
    print(f"[{timestamp}] [{level}] {message}")
    return log_entry

def route_status_path():
    return os.path.join(BACKEND_RESULT_DIR, 'rt', 'route_status.txt')

def route_completed():
    status_file = route_status_path()
    if not os.path.exists(status_file):
        return False
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            return 'status=success' in f.read()
    except OSError:
        return False

def get_backend_input_def(prefer_route=True):
    routed_def = os.path.join(BACKEND_RESULT_DIR, 'iRT_result.def')
    setup_def = os.path.join(BACKEND_RESULT_DIR, 'iTO_setup_result.def')
    hold_def = os.path.join(BACKEND_RESULT_DIR, 'iTO_hold_result.def')
    cts_def = os.path.join(BACKEND_RESULT_DIR, 'iCTS_result.def')
    if prefer_route and route_completed() and os.path.exists(routed_def):
        return routed_def
    if os.path.exists(setup_def):
        return setup_def
    if os.path.exists(hold_def):
        return hold_def
    return cts_def

def shell_quote(value):
    return shlex.quote(str(value))

def backend_env_exports(extra=None):
    ieda_root = os.path.expanduser('~/iEDA')
    ieda_script_dir = os.path.join(ieda_root, 'scripts', 'design', 'sky130_gcd')
    foundry_dir = os.path.join(ieda_root, 'scripts', 'foundry', 'sky130')
    env = {
        'CONFIG_DIR': os.path.join(PROJECT_ROOT, 'backend', 'config'),
        'FOUNDRY_DIR': foundry_dir,
        'RESULT_DIR': BACKEND_RESULT_DIR,
        'TCL_SCRIPT_DIR': os.path.join(ieda_script_dir, 'script'),
        'DESIGN_TOP': 'picorv32',
        'CUSTOM_TCL_DIR': os.path.join(PROJECT_ROOT, 'backend', 'tcl'),
        'NETLIST_FILE': os.path.join(SYNTH_RESULT_DIR, 'picorv32_netlist.v'),
        'SDC_FILE': os.path.join(SYNTH_RESULT_DIR, 'picorv32.sdc'),
        'DIE_AREA': os.environ.get('DIE_AREA', '0.0 0.0 500.0 500.0'),
        'CORE_AREA': os.environ.get('CORE_AREA', '20.0 20.0 480.0 480.0'),
    }
    if extra:
        env.update(extra)
    return ' '.join(f'export {key}={shell_quote(value)};' for key, value in env.items())

def ieda_cmd(tcl_script, extra_env=None):
    return (
        f'cd {shell_quote(PROJECT_ROOT)} && '
        f'{backend_env_exports(extra_env)} '
        f'{shell_quote(IEDA_BIN)} -script {shell_quote(tcl_script)}'
    )

# ============================================================
# 工具链检测
# ============================================================
def detect_tools():
    """检测 EDA 工具链状态"""
    tools = flow_state['tools']

    # Yosys
    try:
        r = subprocess.run(['yosys', '-V'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            tools['yosys']['status'] = 'ok'
            tools['yosys']['version'] = r.stdout.strip().split('\n')[0]
        else:
            tools['yosys']['status'] = 'error'
    except:
        tools['yosys']['status'] = 'missing'

    # iEDA
    if os.path.isfile(IEDA_BIN) and os.access(IEDA_BIN, os.X_OK):
        tools['ieda']['status'] = 'ok'
        tools['ieda']['version'] = 'installed'
    else:
        tools['ieda']['status'] = 'missing'

    # KiCad
    try:
        r = subprocess.run(['kicad-cli', 'version'], capture_output=True, text=True, timeout=5)
        tools['kicad']['status'] = 'ok'
        tools['kicad']['version'] = r.stdout.strip() if r.stdout else 'installed'
    except:
        tools['kicad']['status'] = 'missing'

    # PDK
    if os.path.isdir(os.path.join(PDK_ROOT, 'sky130A')):
        tools['pdk']['status'] = 'ok'
        tools['pdk']['version'] = 'sky130A'
    else:
        tools['pdk']['status'] = 'missing'

    # Volare
    try:
        r = subprocess.run(['volare', 'version'], capture_output=True, text=True, timeout=5)
        tools['volare']['status'] = 'ok'
        tools['volare']['version'] = r.stdout.strip()
    except:
        tools['volare']['status'] = 'missing'

    add_log("工具链检测完成", 'info')

# ============================================================
# 命令执行
# ============================================================
def run_command(cmd, cwd=None, step=None):
    global flow_state
    if cwd is None:
        cwd = PROJECT_ROOT

    with state_lock:
        if step and step in flow_state['steps']:
            flow_state['steps'][step]['status'] = 'running'
            flow_state['steps'][step]['start'] = datetime.now().isoformat()
            flow_state['current_step'] = step

    add_log(f"$ {cmd}", 'cmd', step)

    try:
        process = subprocess.Popen(
            cmd, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1
        )

        output_lines = []
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                output_lines.append(line)
                add_log(line, 'output', step)

        process.wait()

        with state_lock:
            if step and step in flow_state['steps']:
                flow_state['steps'][step]['end'] = datetime.now().isoformat()
                if process.returncode == 0:
                    flow_state['steps'][step]['status'] = 'done'
                    flow_state['steps'][step]['progress'] = 100
                else:
                    flow_state['steps'][step]['status'] = 'warning'
                flow_state['steps'][step]['output'] = output_lines[-20:] if output_lines else []

        if process.returncode == 0:
            add_log(f"命令完成 (返回码: {process.returncode})", 'success', step)
        else:
            add_log(f"命令完成 (返回码: {process.returncode})", 'warning', step)

        return {'success': process.returncode == 0, 'returncode': process.returncode, 'output': output_lines}
    except Exception as e:
        add_log(f"错误: {str(e)}", 'error', step)
        with state_lock:
            if step and step in flow_state['steps']:
                flow_state['steps'][step]['status'] = 'error'
                flow_state['steps'][step]['error'] = str(e)
        return {'success': False, 'error': str(e)}

# ============================================================
# EDA 流程函数
# ============================================================
def run_synthesis(rtl_file=None):
    """运行 Yosys 综合"""
    with state_lock:
        flow_state['running'] = True
        flow_state['steps']['synthesis']['status'] = 'running'
        flow_state['steps']['synthesis']['start'] = datetime.now().isoformat()
        flow_state['current_step'] = 'synthesis'

    add_log("━━━ [1/8] Yosys 综合 ━━━━━━━━━━━━━━━━━━━━━━━", 'header', 'synthesis')
    add_log("工具: Yosys (开源综合工具)", 'info', 'synthesis')
    add_log("输入: RTL Verilog 源码", 'info', 'synthesis')
    add_log("输出: 门级网表 (.v) + 约束 (.sdc)", 'info', 'synthesis')
    add_log("", 'info', 'synthesis')

    add_log("步骤 1.1: 读取 RTL 源码", 'info', 'synthesis')
    add_log("步骤 1.2: 逻辑综合 (proc, opt, flatten)", 'info', 'synthesis')
    add_log("步骤 1.3: 寄存器文件展开 (memory_map)", 'info', 'synthesis')
    add_log("步骤 1.4: 技术映射 (techmap, dfflibmap, abc)", 'info', 'synthesis')
    add_log("步骤 1.5: 后处理 (fix_netlist.py 修复复杂赋值)", 'info', 'synthesis')
    add_log("", 'info', 'synthesis')

    result = run_command('bash synthesis/run_synth.sh', step='synthesis')

    with state_lock:
        if result.get('success'):
            flow_state['steps']['synthesis']['progress'] = 100
            flow_state['steps']['synthesis']['status'] = 'done'
            add_log("综合完成!", 'success', 'synthesis')
        else:
            flow_state['steps']['synthesis']['status'] = 'error'
            add_log("综合失败", 'error', 'synthesis')
        flow_state['running'] = False

    return result

def run_floorplan():
    """运行 Floorplan"""
    with state_lock:
        flow_state['running'] = True
    add_log("━━━ [2/8] Floorplan (布局规划) ━━━━━━━━━━━━━━", 'header', 'floorplan')
    add_log("工具: iEDA iFP (布局规划引擎)", 'info', 'floorplan')
    add_log("功能: 创建芯片布局区域、电源网络、IO 端口", 'info', 'floorplan')
    add_log("", 'info', 'floorplan')
    add_log("步骤 2.1: 初始化流程配置", 'info', 'floorplan')
    add_log("步骤 2.2: 读取 LEF/DEF 库文件", 'info', 'floorplan')
    add_log("步骤 2.3: 读取综合网表", 'info', 'floorplan')
    add_log("步骤 2.4: 创建布局区域 (1000um x 1000um)", 'info', 'floorplan')
    add_log("步骤 2.5: 设置电源网络 (VDD/VSS)", 'info', 'floorplan')
    add_log("步骤 2.6: 放置 IO 端口和 Tap 单元", 'info', 'floorplan')
    add_log("", 'info', 'floorplan')

    os.makedirs(os.path.join(BACKEND_RESULT_DIR, 'report'), exist_ok=True)
    os.makedirs(os.path.join(BACKEND_RESULT_DIR, 'rt'), exist_ok=True)
    os.makedirs(os.path.join(BACKEND_RESULT_DIR, 'sta'), exist_ok=True)

    cmd = ieda_cmd('backend/tcl/run_iFP.tcl')
    result = run_command(cmd, step='floorplan')

    with state_lock:
        if os.path.exists(os.path.join(BACKEND_RESULT_DIR, 'iFP_result.def')):
            flow_state['steps']['floorplan']['status'] = 'done'
            flow_state['steps']['floorplan']['progress'] = 100
            add_log("Floorplan 完成!", 'success', 'floorplan')
        else:
            flow_state['steps']['floorplan']['status'] = 'error'
        flow_state['running'] = False
    return result

def run_placement():
    """运行 Placement"""
    with state_lock:
        flow_state['running'] = True
    add_log("━━━ [3/8] Placement (布局) ━━━━━━━━━━━━━━━━━━", 'header', 'placement')
    add_log("工具: iEDA iPL (布局引擎)", 'info', 'placement')
    add_log("功能: 将标准单元放置到布局区域内", 'info', 'placement')
    add_log("", 'info', 'placement')
    add_log("步骤 3.1: 读取 Floorplan DEF", 'info', 'placement')
    add_log("步骤 3.2: 全局布局 (Nesterov 方法)", 'info', 'placement')
    add_log("步骤 3.3: 详细布局", 'info', 'placement')
    add_log("步骤 3.4: 插入填充单元 (Filler)", 'info', 'placement')
    add_log("", 'info', 'placement')

    cmd = ieda_cmd('backend/tcl/run_iPL.tcl')
    result = run_command(cmd, step='placement')

    with state_lock:
        if os.path.exists(os.path.join(BACKEND_RESULT_DIR, 'iPL_result.def')):
            flow_state['steps']['placement']['status'] = 'done'
            flow_state['steps']['placement']['progress'] = 100
            add_log("Placement 完成!", 'success', 'placement')
        flow_state['running'] = False
    return result

def run_cts():
    """运行 CTS"""
    with state_lock:
        flow_state['running'] = True
    add_log("━━━ [4/8] CTS (时钟树综合) ━━━━━━━━━━━━━━━━━", 'header', 'cts')
    add_log("工具: iEDA iCTS (时钟树引擎)", 'info', 'cts')
    add_log("功能: 构建平衡的时钟分配网络", 'info', 'cts')
    add_log("", 'info', 'cts')
    add_log("步骤 4.1: 读取 Placement DEF", 'info', 'cts')
    add_log("步骤 4.2: 构建时钟树", 'info', 'cts')
    add_log("步骤 4.3: 插入时钟缓冲器", 'info', 'cts')
    add_log("步骤 4.4: 时钟树平衡", 'info', 'cts')
    add_log("", 'info', 'cts')

    cmd = ieda_cmd('backend/tcl/run_iCTS.tcl')
    result = run_command(cmd, step='cts')

    with state_lock:
        if os.path.exists(os.path.join(BACKEND_RESULT_DIR, 'iCTS_result.def')):
            flow_state['steps']['cts']['status'] = 'done'
            flow_state['steps']['cts']['progress'] = 100
            add_log("CTS 完成!", 'success', 'cts')
        flow_state['running'] = False
    return result

def run_routing():
    """运行 Routing"""
    with state_lock:
        flow_state['running'] = True
    add_log("━━━ [5/8] Routing (布线) ━━━━━━━━━━━━━━━━━━━", 'header', 'routing')
    add_log("工具: iEDA iRT (布线引擎)", 'info', 'routing')
    add_log("功能: 完成信号线的物理连接", 'info', 'routing')
    add_log("", 'info', 'routing')
    add_log("步骤 5.1: 读取优化后的 DEF", 'info', 'routing')
    add_log("步骤 5.2: 初始化布线器 (met1-met5, 4线程)", 'info', 'routing')
    add_log("步骤 5.3: 全局布线 (Global Routing)", 'info', 'routing')
    add_log("步骤 5.4: 详细布线 (Detailed Routing)", 'info', 'routing')
    add_log("步骤 5.5: DRC 检查和修复", 'info', 'routing')
    add_log("", 'info', 'routing')

    input_def = get_backend_input_def(prefer_route=False)
    cmd = ieda_cmd('backend/tcl/run_iRT.tcl', {'INPUT_DEF': input_def})
    result = run_command(cmd, step='routing')

    with state_lock:
        if route_completed() and os.path.exists(os.path.join(BACKEND_RESULT_DIR, 'iRT_result.def')):
            flow_state['steps']['routing']['status'] = 'done'
            flow_state['steps']['routing']['progress'] = 100
        else:
            flow_state['steps']['routing']['status'] = 'warning'
            add_log("Routing 未完成，请查看 artifacts/backend/rt/rt.log；当前使用 iTO_setup 结果继续", 'warning', 'routing')
        flow_state['running'] = False
    return result

def run_sta():
    """运行 STA"""
    with state_lock:
        flow_state['running'] = True
    add_log("━━━ [6/8] STA (静态时序分析) ━━━━━━━━━━━━━━━", 'header', 'sta')
    add_log("工具: iEDA iSTA (时序分析引擎)", 'info', 'sta')
    add_log("功能: 检查设计是否满足时序约束", 'info', 'sta')
    add_log("", 'info', 'sta')
    add_log("步骤 6.1: 读取 DEF", 'info', 'sta')
    add_log("步骤 6.2: 加载 Liberty 时序库", 'info', 'sta')
    add_log("步骤 6.3: 建立时序图", 'info', 'sta')
    add_log("步骤 6.4: 计算路径延迟", 'info', 'sta')
    add_log("步骤 6.5: 生成时序报告", 'info', 'sta')
    add_log("", 'info', 'sta')

    input_def = get_backend_input_def(prefer_route=True)

    cmd = ieda_cmd('backend/tcl/run_iSTA.tcl', {'INPUT_DEF': input_def})
    result = run_command(cmd, step='sta')

    with state_lock:
        flow_state['steps']['sta']['status'] = 'done'
        flow_state['steps']['sta']['progress'] = 100
        add_log("STA 完成!", 'success', 'sta')
        flow_state['running'] = False
    return result

def run_gdsii():
    """生成 GDSII"""
    with state_lock:
        flow_state['running'] = True
    add_log("━━━ [7/8] GDSII (物理版图) ━━━━━━━━━━━━━━━━━", 'header', 'gdsii')
    add_log("工具: iEDA GDS 转换器", 'info', 'gdsii')
    add_log("功能: 生成制造用 GDSII 物理版图文件", 'info', 'gdsii')
    add_log("", 'info', 'gdsii')
    add_log("步骤 7.1: 读取最终 DEF", 'info', 'gdsii')
    add_log("步骤 7.2: 转换为 GDSII 格式", 'info', 'gdsii')
    add_log("", 'info', 'gdsii')

    input_def = get_backend_input_def(prefer_route=True)

    cmd = ieda_cmd('backend/tcl/run_def_to_gds.tcl', {'INPUT_DEF': input_def})
    result = run_command(cmd, step='gdsii')

    with state_lock:
        if os.path.exists(os.path.join(BACKEND_RESULT_DIR, 'picorv32.gds2')):
            flow_state['steps']['gdsii']['status'] = 'done'
            flow_state['steps']['gdsii']['progress'] = 100
            add_log("GDSII 生成完成!", 'success', 'gdsii')
        flow_state['running'] = False
    return result

def run_full_flow():
    """运行完整流程"""
    with state_lock:
        for s in flow_state['steps']:
            flow_state['steps'][s]['status'] = 'pending'
            flow_state['steps'][s]['progress'] = 0
            flow_state['steps'][s]['output'] = None
            flow_state['steps'][s]['error'] = None

    add_log("╔══════════════════════════════════════════════╗", 'header')
    add_log("║    硅迹开源 - RTL → GDSII → KiCad 全流程       ║", 'header')
    add_log("╚══════════════════════════════════════════════╝", 'header')
    add_log("", 'info')

    steps = [
        ("Yosys 综合", run_synthesis),
        ("Floorplan", run_floorplan),
        ("Placement", run_placement),
        ("CTS", run_cts),
        ("Routing", run_routing),
        ("STA", run_sta),
        ("GDSII", run_gdsii),
        ("KiCad", run_kicad_check),
    ]

    for name, func in steps:
        result = func()
        if not result.get('success') and name not in ["Routing"]:
            add_log(f"步骤 {name} 失败，流程中止", 'error')
            return result

    add_log("", 'info')
    add_log("╔══════════════════════════════════════════════╗", 'success')
    add_log("║    全流程完成!                                 ║", 'success')
    add_log("╚══════════════════════════════════════════════╝", 'success')
    return {'success': True}

def run_kicad_check():
    """导出并检查 KiCad 文件"""
    with state_lock:
        flow_state['running'] = True
    add_log("━━━ [8/8] KiCad 工程导出 ━━━━━━━━━━━━━━━━━━━", 'header', 'kicad')
    add_log("工具: SiliconTrace KiCad Exporter", 'info', 'kicad')
    add_log("功能: 生成可复现的 KiCad 工程、局部库和引脚映射", 'info', 'kicad')
    add_log("", 'info', 'kicad')

    cmd = f'cd {shell_quote(PROJECT_ROOT)} && python3 backend/export_kicad.py'
    result = run_command(cmd, step='kicad')

    files = {
        '工程': os.path.join(KICAD_RESULT_DIR, 'picorv32_test_board.kicad_pro'),
        '原理图': os.path.join(KICAD_RESULT_DIR, 'picorv32_test_board.kicad_sch'),
        'PCB Layout': os.path.join(KICAD_RESULT_DIR, 'picorv32_test_board.kicad_pcb'),
        'KiCad 符号库': os.path.join(KICAD_RESULT_DIR, 'symbols', 'kicad.kicad_sym'),
        'Power 符号库': os.path.join(KICAD_RESULT_DIR, 'symbols', 'power.kicad_sym'),
        'QFN-48 封装': os.path.join(KICAD_RESULT_DIR, 'footprints.pretty', 'QFN-48_7x7mm_P0.5mm.kicad_mod'),
        '引脚映射': os.path.join(KICAD_RESULT_DIR, 'pin_map.csv'),
        '导出清单': os.path.join(KICAD_RESULT_DIR, 'manifest.json'),
    }
    all_ok = result.get('success', False)
    for name, path in files.items():
        full_path = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
        rel_path = os.path.relpath(full_path, PROJECT_ROOT)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            add_log(f"  ✓ {name}: {rel_path} ({size} bytes)", 'success', 'kicad')
        else:
            add_log(f"  ✗ {name}: {rel_path} (不存在)", 'error', 'kicad')
            all_ok = False

    with state_lock:
        flow_state['steps']['kicad']['status'] = 'done' if all_ok else 'error'
        flow_state['steps']['kicad']['progress'] = 100
        flow_state['running'] = False
    return {'success': all_ok}

# ============================================================
# RTL / 封装导入
# ============================================================
def import_rtl(file_path, design_name=None):
    """导入 RTL 设计"""
    add_log("━━━ 导入 RTL 设计 ━━━━━━━━━━━━━━━━━━━━━━━━━", 'header')

    if not os.path.exists(file_path):
        add_log(f"文件不存在: {file_path}", 'error')
        return {'success': False, 'error': 'File not found'}

    # 确定设计名称
    if design_name is None:
        design_name = Path(file_path).stem

    # 复制到 rtl 目录
    dest_dir = os.path.join(RTL_DIR, design_name)
    os.makedirs(dest_dir, exist_ok=True)

    if os.path.isfile(file_path):
        dest_file = os.path.join(dest_dir, os.path.basename(file_path))
        shutil.copy2(file_path, dest_file)
        add_log(f"已复制: {file_path} → {dest_file}", 'success')
    elif os.path.isdir(file_path):
        for f in os.listdir(file_path):
            if f.endswith('.v') or f.endswith('.sv') or f.endswith('.vh'):
                src = os.path.join(file_path, f)
                dst = os.path.join(dest_dir, f)
                shutil.copy2(src, dst)
                add_log(f"已复制: {src} → {dst}", 'success')

    # 更新当前设计
    with state_lock:
        flow_state['current_rtl'] = dest_dir
        flow_state['current_design'] = design_name

    add_log(f"RTL 设计已导入: {design_name}", 'success')
    add_log(f"目录: {dest_dir}", 'info')
    return {'success': True, 'design': design_name, 'path': dest_dir}

def import_footprint(file_path):
    """导入芯片封装"""
    add_log("━━━ 导入芯片封装 ━━━━━━━━━━━━━━━━━━━━━━━━━", 'header')

    if not os.path.exists(file_path):
        add_log(f"文件不存在: {file_path}", 'error')
        return {'success': False, 'error': 'File not found'}

    filename = os.path.basename(file_path)
    dest = os.path.join(FOOTPRINT_DIR, filename)
    shutil.copy2(file_path, dest)
    add_log(f"已复制: {file_path} → {dest}", 'success')

    # 验证文件
    with open(dest, 'r') as f:
        content = f.read()
    if '(footprint' in content or '(module' in content:
        add_log("封装文件格式验证通过", 'success')
    else:
        add_log("警告: 文件可能不是有效的 KiCad 封装", 'warning')

    return {'success': True, 'path': dest}

def import_symbol(file_path):
    """导入原理图符号"""
    add_log("━━━ 导入原理图符号 ━━━━━━━━━━━━━━━━━━━━━━━━", 'header')

    if not os.path.exists(file_path):
        add_log(f"文件不存在: {file_path}", 'error')
        return {'success': False, 'error': 'File not found'}

    filename = os.path.basename(file_path)
    dest = os.path.join(SYMBOL_DIR, filename)
    shutil.copy2(file_path, dest)
    add_log(f"已复制: {file_path} → {dest}", 'success')

    # 验证文件
    with open(dest, 'r') as f:
        content = f.read()
    if '(kicad_symbol' in content or '(symbol' in content:
        add_log("符号文件格式验证通过", 'success')
    else:
        add_log("警告: 文件可能不是有效的 KiCad 符号", 'warning')

    return {'success': True, 'path': dest}

def list_uploaded_files():
    """列出已上传的文件"""
    files = {'rtl': [], 'packages': []}
    for category in ['rtl', 'packages']:
        dir_path = os.path.join(UPLOAD_DIR, category)
        if os.path.isdir(dir_path):
            for f in os.listdir(dir_path):
                full_path = os.path.join(dir_path, f)
                files[category].append({
                    'name': f,
                    'size': os.path.getsize(full_path),
                    'time': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                })
    return files

# ============================================================
# Web API
# ============================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.json
    cmd = data.get('command', '').strip().lower()
    if not cmd:
        return jsonify({'error': '请输入命令'}), 400

    add_log(f"用户命令: {cmd}", 'info')

    command_map = {
        '综合': run_synthesis, 'synthesis': run_synthesis, 'yosys': run_synthesis,
        'floorplan': run_floorplan, 'fp': run_floorplan, '布局规划': run_floorplan,
        'placement': run_placement, 'pl': run_placement, '布局': run_placement,
        'cts': run_cts, '时钟树': run_cts, 'clock tree': run_cts,
        'routing': run_routing, 'rt': run_routing, '布线': run_routing,
        'sta': run_sta, '时序分析': run_sta, 'timing': run_sta,
        'gdsii': run_gdsii, 'gds': run_gdsii,
        '全流程': run_full_flow, 'full flow': run_full_flow, 'run all': run_full_flow, 'rtl2gds': run_full_flow,
        'kicad': run_kicad_check, 'check kicad': run_kicad_check, 'export kicad': run_kicad_check,
        'status': lambda: {'success': True}, '状态': lambda: {'success': True},
    }

    func = None
    for key, f in command_map.items():
        if key in cmd:
            func = f
            break

    if func is None:
        return jsonify({'error': f'未识别的命令: {cmd}', 'available': list(command_map.keys())})

    if flow_state['running']:
        return jsonify({'error': '有命令正在执行，请等待完成'})

    thread = threading.Thread(target=func, daemon=True)
    thread.start()
    return jsonify({'success': True, 'message': f'命令已提交: {cmd}'})

@app.route('/api/upload/rtl', methods=['POST'])
def api_upload_rtl():
    """上传 RTL 文件"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    # 保存文件
    filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, 'rtl', filename)
    file.save(save_path)

    design_name = request.form.get('design_name', Path(file.filename).stem)

    # 导入
    result = import_rtl(save_path, design_name)
    return jsonify(result)

@app.route('/api/upload/package', methods=['POST'])
def api_upload_package():
    """上传封装/符号文件"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, 'packages', filename)
    file.save(save_path)

    file_type = request.form.get('type', 'footprint')

    if file_type == 'footprint':
        result = import_footprint(save_path)
    elif file_type == 'symbol':
        result = import_symbol(save_path)
    else:
        result = import_footprint(save_path)

    return jsonify(result)

@app.route('/api/upload/mcp', methods=['POST'])
def api_upload_mcp():
    """MCP 交互上传接口"""
    data = request.json
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400

    action = data.get('action')
    file_type = data.get('type')  # rtl, footprint, symbol
    content = data.get('content')  # 文件内容 (base64 或文本)
    filename = data.get('filename')
    design_name = data.get('design_name')

    if not all([action, file_type, content, filename]):
        return jsonify({'error': '缺少必要参数: action, type, content, filename'}), 400

    # 解码内容
    import base64
    try:
        if data.get('encoding') == 'base64':
            file_content = base64.b64decode(content)
        else:
            file_content = content.encode('utf-8')
    except Exception as e:
        return jsonify({'error': f'内容解码失败: {str(e)}'}), 400

    # 保存文件
    save_path = os.path.join(UPLOAD_DIR, file_type + 's' if file_type != 'rtl' else 'rtl', filename)
    with open(save_path, 'wb') as f:
        f.write(file_content)

    # 执行操作
    if action == 'import':
        if file_type == 'rtl':
            result = import_rtl(save_path, design_name)
        elif file_type == 'footprint':
            result = import_footprint(save_path)
        elif file_type == 'symbol':
            result = import_symbol(save_path)
        else:
            return jsonify({'error': f'未知类型: {file_type}'}), 400
    else:
        return jsonify({'error': f'未知操作: {action}'}), 400

    return jsonify(result)

@app.route('/api/files')
def api_files():
    """列出已上传文件"""
    return jsonify(list_uploaded_files())

@app.route('/api/designs')
def api_designs():
    """列出所有可用的 RTL 设计"""
    designs = []
    rtl_dir = os.path.join(PROJECT_ROOT, 'rtl')
    if os.path.isdir(rtl_dir):
        for d in os.listdir(rtl_dir):
            full_path = os.path.join(rtl_dir, d)
            if os.path.isdir(full_path):
                v_files = [f for f in os.listdir(full_path) if f.endswith('.v') or f.endswith('.sv')]
                if v_files:
                    designs.append({
                        'name': d,
                        'path': full_path,
                        'files': v_files,
                        'is_current': d == flow_state['current_design']
                    })
    return jsonify({'designs': designs, 'current': flow_state['current_design']})

@app.route('/api/design/switch', methods=['POST'])
def api_design_switch():
    """切换当前设计"""
    data = request.json
    design_name = data.get('design')
    if not design_name:
        return jsonify({'error': '请指定设计名称'}), 400

    design_dir = os.path.join(PROJECT_ROOT, 'rtl', design_name)
    if not os.path.isdir(design_dir):
        return jsonify({'error': f'设计不存在: {design_name}'}), 404

    with state_lock:
        flow_state['current_design'] = design_name
        flow_state['current_rtl'] = design_dir
        # 重置流程状态
        for s in flow_state['steps']:
            flow_state['steps'][s]['status'] = 'pending'
            flow_state['steps'][s]['progress'] = 0
            flow_state['steps'][s]['output'] = None
            flow_state['steps'][s]['error'] = None

    add_log(f"已切换到设计: {design_name}", 'info')
    return jsonify({'success': True, 'design': design_name})

@app.route('/api/output_files')
def api_output_files():
    """列出后端生成的所有输出文件"""
    files = {
        'synthesis': [],
        'backend': [],
        'sta': [],
        'kicad': []
    }

    # 综合结果
    synth_dir = SYNTH_RESULT_DIR
    if os.path.isdir(synth_dir):
        for f in os.listdir(synth_dir):
            fp = os.path.join(synth_dir, f)
            files['synthesis'].append({
                'name': f,
                'size': os.path.getsize(fp),
                'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                'type': os.path.splitext(f)[1]
            })

    # 后端结果
    result_dir = BACKEND_RESULT_DIR
    if os.path.isdir(result_dir):
        for f in os.listdir(result_dir):
            fp = os.path.join(result_dir, f)
            if os.path.isfile(fp):
                files['backend'].append({
                    'name': f,
                    'size': os.path.getsize(fp),
                    'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                    'type': os.path.splitext(f)[1]
                })

    # STA 报告
    sta_dir = BACKEND_STA_DIR
    if os.path.isdir(sta_dir):
        for f in os.listdir(sta_dir):
            fp = os.path.join(sta_dir, f)
            if os.path.isfile(fp):
                files['sta'].append({
                    'name': f,
                    'size': os.path.getsize(fp),
                    'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                    'type': os.path.splitext(f)[1]
                })

    # KiCad 文件
    generated_kicad_root = os.path.join(ARTIFACTS_DIR, 'kicad')
    if os.path.isdir(generated_kicad_root):
        for root, _, names in os.walk(generated_kicad_root):
            for f in names:
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    files['kicad'].append({
                        'name': f,
                        'path': os.path.relpath(root, PROJECT_ROOT),
                        'size': os.path.getsize(fp),
                        'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                        'type': os.path.splitext(f)[1]
                    })

    for subdir, key in [('kicad/test_board', 'kicad'), ('kicad/symbols', 'kicad'), ('kicad/footprints', 'kicad')]:
        d = os.path.join(PROJECT_ROOT, subdir)
        if os.path.isdir(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp):
                    files[key].append({
                        'name': f,
                        'path': subdir,
                        'size': os.path.getsize(fp),
                        'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                        'type': os.path.splitext(f)[1]
                    })

    return jsonify(files)

@app.route('/api/file_content/<path:filepath>')
def api_file_content(filepath):
    """读取文件内容 (仅限文本文件)"""
    full_path = os.path.join(PROJECT_ROOT, filepath)
    if not os.path.exists(full_path):
        return jsonify({'error': '文件不存在'}), 404

    # 安全检查：只允许读取项目目录下的文件
    if not os.path.abspath(full_path).startswith(os.path.abspath(PROJECT_ROOT)):
        return jsonify({'error': '禁止访问'}), 403

    # 检查文件大小
    size = os.path.getsize(full_path)
    if size > 5 * 1024 * 1024:  # 5MB 限制
        return jsonify({'error': '文件过大，请直接下载查看'}), 400

    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({
            'path': filepath,
            'size': size,
            'content': content
        })
    except Exception as e:
        return jsonify({'error': f'读取失败: {str(e)}'}), 500

@app.route('/api/file_download/<path:filepath>')
def api_file_download(filepath):
    """下载文件"""
    full_path = os.path.join(PROJECT_ROOT, filepath)
    if not os.path.exists(full_path):
        return jsonify({'error': '文件不存在'}), 404

    if not os.path.abspath(full_path).startswith(os.path.abspath(PROJECT_ROOT)):
        return jsonify({'error': '禁止访问'}), 403

    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/api/state')
def api_state():
    """获取完整状态"""
    with state_lock:
        state = {
            'current_step': flow_state['current_step'],
            'running': flow_state['running'],
            'current_design': flow_state['current_design'],
            'steps': {},
            'tools': flow_state['tools'],
        }
        for k, v in flow_state['steps'].items():
            state['steps'][k] = {
                'name': v['name'],
                'tool': v['tool'],
                'status': v['status'],
                'progress': v['progress'],
                'error': v['error'],
            }
    return jsonify(state)

@app.route('/api/logs')
def api_logs():
    since = request.args.get('since', 0, type=int)
    return jsonify(logs[since:])

@app.route('/api/logs/stream')
def api_logs_stream():
    def generate():
        last = 0
        while True:
            if len(logs) > last:
                for log in logs[last:]:
                    yield f"data: {json.dumps(log)}\n\n"
                last = len(logs)
            time.sleep(0.3)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/tools')
def api_tools():
    detect_tools()
    return jsonify(flow_state['tools'])

@app.route('/api/help')
def api_help():
    return jsonify({
        'commands': {
            '综合/synthesis/yosys': '运行 Yosys 综合，RTL → 门级网表',
            'floorplan/fp/布局规划': '运行 iEDA Floorplan，创建芯片布局',
            'placement/pl/布局': '运行 iEDA Placement，放置标准单元',
            'cts/时钟树': '运行 iEDA CTS，时钟树综合',
            'routing/rt/布线': '运行 iEDA Routing，信号布线',
            'sta/时序分析': '运行 iEDA STA，静态时序分析',
            'gdsii/gds': '生成 GDSII 物理版图',
            '全流程/full flow': '运行完整 RTL→GDSII→KiCad 流程',
            'kicad': '导出 KiCad 工程并检查生成文件',
            'status/状态': '查看项目状态',
        },
        'upload': {
            'rtl': 'POST /api/upload/rtl - 上传 RTL 文件',
            'package': 'POST /api/upload/package - 上传封装/符号',
            'mcp': 'POST /api/upload/mcp - MCP 交互上传',
        }
    })

# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    add_log("╔══════════════════════════════════════════════╗", 'header')
    add_log("║    硅迹开源 - AI 交互式控制台 v2              ║", 'header')
    add_log("╚══════════════════════════════════════════════╝", 'header')
    add_log(f"项目目录: {PROJECT_ROOT}", 'info')
    add_log(f"iEDA 路径: {IEDA_BIN}", 'info')
    add_log(f"PDK 路径: {PDK_ROOT}", 'info')

    detect_tools()

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
