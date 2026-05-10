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
import queue
import mimetypes
import signal
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

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
AI_FLOW_UPLOAD_DIR = os.path.join(ARTIFACTS_DIR, 'ai_flow_uploads')
UPLOAD_DIR = os.path.join(PROJECT_ROOT, 'uploads')
RTL_DIR = os.path.join(PROJECT_ROOT, 'rtl')
FOOTPRINT_DIR = os.path.join(PROJECT_ROOT, 'kicad/footprints')
SYMBOL_DIR = os.path.join(PROJECT_ROOT, 'kicad/symbols')

os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(AI_FLOW_UPLOAD_DIR, exist_ok=True)
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
        'openroad': {'name': 'OpenROAD', 'version': 'checking...', 'status': 'unknown', 'path': 'openroad'},
        'sta': {'name': 'OpenSTA', 'version': 'checking...', 'status': 'unknown', 'path': 'sta'},
        'librelane': {'name': 'LibreLane', 'version': 'checking...', 'status': 'unknown', 'path': 'python3 -m librelane'},
        'kicad': {'name': 'KiCad', 'version': 'checking...', 'status': 'unknown', 'path': 'kicad'},
        'pdk': {'name': 'SKY130 PDK', 'version': 'checking...', 'status': 'unknown', 'path': PDK_ROOT},
        'volare': {'name': 'Volare', 'version': 'checking...', 'status': 'unknown', 'path': 'volare'},
    },
    'current_rtl': None,
    'current_design': 'picorv32',
    'running': False,
}
state_lock = threading.Lock()
ai_flow_runs = {}
ai_flow_lock = threading.Lock()
ai_flow_thread = threading.local()

def current_ai_flow_run_id():
    return getattr(ai_flow_thread, 'run_id', None)

def ai_flow_cancel_requested(run_id):
    if not run_id:
        return False
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        return bool(run and run.get('cancel_requested'))

def set_ai_flow_current_process(run_id, process):
    if not run_id:
        return
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if run is not None:
            run['current_process'] = process

def terminate_process(process):
    if not process or process.poll() is not None:
        return
    try:
        if os.name != 'nt':
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()
    except Exception:
        try:
            process.terminate()
        except Exception:
            pass

def kill_process(process):
    if not process or process.poll() is not None:
        return
    try:
        if os.name != 'nt':
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
    except Exception:
        try:
            process.kill()
        except Exception:
            pass

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

    # OpenROAD
    openroad_candidates = [
        os.path.join(PROJECT_ROOT, 'artifacts', 'tools', 'openroad-2024', 'bin', 'openroad'),
        os.path.join(PROJECT_ROOT, 'artifacts', 'tools', 'openroad-env', 'bin', 'openroad'),
        os.path.join(PROJECT_ROOT, 'artifacts', 'librelane', 'bin', 'openroad'),
        shutil.which('openroad') or 'openroad',
    ]
    openroad_path = next((p for p in openroad_candidates if p and os.path.exists(p)), openroad_candidates[-1])
    tools['openroad']['path'] = openroad_path
    try:
        r = subprocess.run([openroad_path, '-version'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            tools['openroad']['status'] = 'ok'
            tools['openroad']['version'] = (r.stdout or r.stderr).strip().split('\n')[0] or 'installed'
        else:
            tools['openroad']['status'] = 'error'
    except:
        tools['openroad']['status'] = 'missing'

    # OpenSTA
    sta_candidates = [
        os.path.join(PROJECT_ROOT, 'artifacts', 'tools', 'openroad-2024', 'bin', 'sta'),
        os.path.join(PROJECT_ROOT, 'artifacts', 'tools', 'openroad-env', 'bin', 'sta'),
        shutil.which('sta') or 'sta',
    ]
    sta_path = next((p for p in sta_candidates if p and os.path.exists(p)), sta_candidates[-1])
    tools['sta']['path'] = sta_path
    try:
        r = subprocess.run([sta_path, '-version'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            tools['sta']['status'] = 'ok'
            tools['sta']['version'] = (r.stdout or r.stderr).strip().split('\n')[0] or 'installed'
        else:
            tools['sta']['status'] = 'error'
    except:
        tools['sta']['status'] = 'missing'

    # LibreLane
    librelane_python = shutil.which('python3') or 'python3'
    try:
        r = subprocess.run(
            [librelane_python, '-c', 'import librelane; print(getattr(librelane, "__version__", "installed"))'],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            tools['librelane']['status'] = 'ok'
            tools['librelane']['version'] = r.stdout.strip().split('\n')[0] or 'installed'
        else:
            tools['librelane']['status'] = 'missing'
    except:
        tools['librelane']['status'] = 'missing'

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
        r = subprocess.run(['volare', '--version'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            tools['volare']['status'] = 'ok'
            tools['volare']['version'] = r.stdout.strip().split('\n')[0]
        else:
            tools['volare']['status'] = 'error'
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
    ai_run_id = current_ai_flow_run_id()

    with state_lock:
        if step and step in flow_state['steps']:
            flow_state['steps'][step]['status'] = 'running'
            flow_state['steps'][step]['start'] = datetime.now().isoformat()
            flow_state['current_step'] = step

    add_log(f"$ {cmd}", 'cmd', step)

    try:
        popen_kwargs = {}
        if os.name != 'nt':
            popen_kwargs['start_new_session'] = True
        process = subprocess.Popen(
            cmd, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1,
            **popen_kwargs
        )
        set_ai_flow_current_process(ai_run_id, process)

        output_lines = []
        cancelled = False
        for line in iter(process.stdout.readline, ''):
            if ai_flow_cancel_requested(ai_run_id):
                cancelled = True
                terminate_process(process)
                break
            line = line.strip()
            if line:
                output_lines.append(line)
                add_log(line, 'output', step)

        if ai_flow_cancel_requested(ai_run_id):
            cancelled = True
            terminate_process(process)
        try:
            process.wait(timeout=5 if cancelled else None)
        except subprocess.TimeoutExpired:
            kill_process(process)
            process.wait()

        with state_lock:
            if step and step in flow_state['steps']:
                flow_state['steps'][step]['end'] = datetime.now().isoformat()
                if cancelled:
                    flow_state['steps'][step]['status'] = 'cancelled'
                elif process.returncode == 0:
                    flow_state['steps'][step]['status'] = 'done'
                    flow_state['steps'][step]['progress'] = 100
                else:
                    flow_state['steps'][step]['status'] = 'warning'
                flow_state['steps'][step]['output'] = output_lines[-20:] if output_lines else []

        if cancelled:
            add_log("命令已被用户终止", 'warning', step)
            return {'success': False, 'cancelled': True, 'returncode': process.returncode, 'output': output_lines}
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
    finally:
        set_ai_flow_current_process(ai_run_id, None)

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
# AI Flow 工作流执行
# ============================================================
AI_FLOW_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-5.5')

AI_FLOW_STAGE_LABELS = {
    'synthesis': 'Yosys 综合',
    'floorplan': 'Floorplan',
    'placement': 'Placement',
    'cts': 'CTS',
    'routing': 'Routing',
    'sta': 'STA',
    'gdsii': 'GDSII',
    'kicad': 'KiCad 导出',
    'full_flow': '全流程',
    'custom_ai': '自定义 AI',
}

AI_FLOW_BACKEND_STAGES = {'floorplan', 'placement', 'cts', 'routing', 'sta', 'gdsii', 'kicad', 'full_flow'}
AI_CONTEXT_TEXT_LIMIT = 200 * 1024
AI_CONTEXT_TOTAL_LIMIT = 600 * 1024
AI_CONTEXT_MAX_ATTACHMENTS = 8

AI_FLOW_STAGE_CONTEXTS = {
    'synthesis': '综合阶段将 RTL Verilog 转换为门级网表和约束文件，重点关注顶层模块、时钟复位、综合约束、网表可读性和后端兼容性。',
    'floorplan': 'Floorplan 阶段定义 die/core 区域、电源网络、IO/宏单元约束和初始布局边界，重点关注面积利用率、电源完整性和后续放置可行性。',
    'placement': 'Placement 阶段放置标准单元并优化初始时序/拥塞，重点关注单元密度、拥塞热点、合法化和后续 CTS 风险。',
    'cts': 'CTS 阶段构建时钟树并插入缓冲器，重点关注 skew、latency、时钟负载和 hold/setup 风险。',
    'routing': 'Routing 阶段完成全局/详细布线，重点关注 DRC、拥塞、未连接网络、天线效应和可签核性。',
    'sta': 'STA 阶段进行静态时序分析，重点关注 setup/hold slack、关键路径、时钟定义和约束覆盖率。',
    'gdsii': 'GDSII 阶段将最终版图数据导出为制造版图，重点关注最终 DEF/ODB 来源、层映射、文件完整性和签核前检查。',
    'kicad': 'KiCad 导出阶段生成板级验证工程、符号、封装和引脚映射，重点关注引脚一致性、封装匹配和工程可打开性。',
    'full_flow': '全流程阶段串联 RTL 综合、后端实现、版图导出和 KiCad 产物，重点关注阶段依赖、失败传播和最终可用文件。',
    'custom_ai': '自定义 AI 节点只做上下文分析，不执行 EDA 命令；适合做设计解释、报告总结、异常诊断或下一步建议。',
}

AI_FLOW_STATUS_TEXT = {
    'pending': '等待中',
    'ai-pre': 'AI 运行前规划',
    'running-command': 'EDA 命令运行中',
    'ai-post': 'AI 运行后总结',
    'done': '完成',
    'warning': '警告',
    'error': '错误',
    'cancelled': '已终止',
}

def ai_flow_card_summary(text, limit=180):
    clean = ' '.join(str(text or '').replace('\r', '\n').split())
    if not clean:
        return ''
    if len(clean) <= limit:
        return clean
    return clean[:limit - 1].rstrip() + '…'

def ai_flow_stage_meta():
    return {
        'synthesis': {'label': AI_FLOW_STAGE_LABELS['synthesis'], 'func': run_synthesis},
        'floorplan': {'label': AI_FLOW_STAGE_LABELS['floorplan'], 'func': run_floorplan},
        'placement': {'label': AI_FLOW_STAGE_LABELS['placement'], 'func': run_placement},
        'cts': {'label': AI_FLOW_STAGE_LABELS['cts'], 'func': run_cts},
        'routing': {'label': AI_FLOW_STAGE_LABELS['routing'], 'func': run_routing},
        'sta': {'label': AI_FLOW_STAGE_LABELS['sta'], 'func': run_sta},
        'gdsii': {'label': AI_FLOW_STAGE_LABELS['gdsii'], 'func': run_gdsii},
        'kicad': {'label': AI_FLOW_STAGE_LABELS['kicad'], 'func': run_kicad_check},
        'full_flow': {'label': AI_FLOW_STAGE_LABELS['full_flow'], 'func': run_full_flow},
        'custom_ai': {'label': AI_FLOW_STAGE_LABELS['custom_ai'], 'func': None},
    }

def collect_output_files_data():
    files = {
        'synthesis': [],
        'backend': [],
        'sta': [],
        'kicad': [],
        'openroad': []
    }

    if os.path.isdir(SYNTH_RESULT_DIR):
        for f in os.listdir(SYNTH_RESULT_DIR):
            fp = os.path.join(SYNTH_RESULT_DIR, f)
            if os.path.isfile(fp):
                files['synthesis'].append({
                    'name': f,
                    'size': os.path.getsize(fp),
                    'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                    'type': os.path.splitext(f)[1]
                })

    if os.path.isdir(BACKEND_RESULT_DIR):
        for f in os.listdir(BACKEND_RESULT_DIR):
            fp = os.path.join(BACKEND_RESULT_DIR, f)
            if os.path.isfile(fp):
                files['backend'].append({
                    'name': f,
                    'size': os.path.getsize(fp),
                    'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                    'type': os.path.splitext(f)[1]
                })

    if os.path.isdir(BACKEND_STA_DIR):
        for f in os.listdir(BACKEND_STA_DIR):
            fp = os.path.join(BACKEND_STA_DIR, f)
            if os.path.isfile(fp):
                files['sta'].append({
                    'name': f,
                    'size': os.path.getsize(fp),
                    'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                    'type': os.path.splitext(f)[1]
                })

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

    librelane_root = os.path.join(ARTIFACTS_DIR, 'librelane')
    openroad_keep_ext = {'.def', '.odb', '.gds', '.gds2', '.json', '.rpt', '.log', '.drc', '.v', '.sdc', '.spef', '.lef'}
    if os.path.isdir(librelane_root):
        for root, _, names in os.walk(librelane_root):
            for f in names:
                fp = os.path.join(root, f)
                if not os.path.isfile(fp):
                    continue
                ext = os.path.splitext(f)[1].lower()
                rel = os.path.relpath(fp, PROJECT_ROOT)
                if ext not in openroad_keep_ext and '/final/' not in rel.replace('\\', '/'):
                    continue
                try:
                    files['openroad'].append({
                        'name': f,
                        'path': os.path.relpath(root, PROJECT_ROOT),
                        'size': os.path.getsize(fp),
                        'time': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                        'type': os.path.splitext(f)[1]
                    })
                except OSError:
                    continue

    return files

def normalize_output_files(files):
    default_roots = {
        'synthesis': 'artifacts/synthesis',
        'backend': 'artifacts/backend',
        'sta': 'artifacts/backend/sta',
        'kicad': 'artifacts/kicad',
        'openroad': 'artifacts/librelane',
    }
    normalized = []
    for category, entries in files.items():
        for item in entries:
            rel_dir = item.get('path') or default_roots.get(category, '')
            rel_path = os.path.join(rel_dir, item['name']).replace('\\', '/')
            normalized.append({
                'category': category,
                'name': item.get('name'),
                'path': rel_path,
                'size': item.get('size', 0),
                'time': item.get('time'),
                'type': item.get('type', ''),
            })
    return normalized

def output_snapshot():
    return {item['path']: item for item in normalize_output_files(collect_output_files_data())}

def file_signature(item):
    return (item.get('size'), item.get('time'))

def stage_file_match(stage, item):
    if stage == 'full_flow':
        return True
    category = item.get('category')
    name = (item.get('name') or '').lower()
    path = (item.get('path') or '').lower()
    if category == 'openroad' and stage in AI_FLOW_BACKEND_STAGES:
        if stage == 'sta':
            return 'sta' in path or 'timing' in name or name.endswith('.rpt') or name.endswith('.json')
        if stage == 'gdsii':
            return name.endswith('.gds') or name.endswith('.gds2') or '/final/' in path.replace('\\', '/')
        return True
    if stage == 'synthesis':
        return category == 'synthesis'
    if stage == 'floorplan':
        return category == 'backend' and ('ifp' in name or 'floorplan' in name)
    if stage == 'placement':
        return category == 'backend' and ('ipl' in name or 'placement' in name)
    if stage == 'cts':
        return category == 'backend' and ('icts' in name or 'cts' in name)
    if stage == 'routing':
        return category == 'backend' and ('irt' in name or 'route' in name or 'routing' in name)
    if stage == 'sta':
        return category == 'sta' or ('ista' in name or 'timing' in name or 'sta' in path)
    if stage == 'gdsii':
        return category == 'backend' and (name.endswith('.gds') or name.endswith('.gds2') or 'gds' in name)
    if stage == 'kicad':
        return category == 'kicad'
    return False

def generated_files_for_stage(stage, before, after):
    changed = []
    for path, item in after.items():
        if not stage_file_match(stage, item):
            continue
        if path not in before or file_signature(before[path]) != file_signature(item):
            changed.append(item)
    if changed:
        return sorted(changed, key=lambda f: (f['category'], f['path']))
    existing = [item for item in after.values() if stage_file_match(stage, item)]
    return sorted(existing, key=lambda f: (f['category'], f['path']))

def rel_project_path(path):
    try:
        return os.path.relpath(path, PROJECT_ROOT).replace('\\', '/')
    except ValueError:
        return str(path).replace('\\', '/')

def is_within_directory(path, directory):
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(directory)]) == os.path.abspath(directory)
    except ValueError:
        return False

def context_file_item(category, full_path, source='project'):
    return {
        'id': f"{source}:{rel_project_path(full_path)}",
        'source': source,
        'category': category,
        'name': os.path.basename(full_path),
        'path': rel_project_path(full_path),
        'size': os.path.getsize(full_path),
        'time': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
        'type': os.path.splitext(full_path)[1],
        'mime': mimetypes.guess_type(full_path)[0] or 'application/octet-stream',
    }

def collect_ai_context_files():
    groups = {
        'rtl': [],
        'synthesis': [],
        'backend': [],
        'sta': [],
        'kicad': [],
        'openroad': [],
        'docs': [],
        'uploads': [],
    }

    for root_dir, category in [(RTL_DIR, 'rtl'), (os.path.join(PROJECT_ROOT, 'docs'), 'docs')]:
        if os.path.isdir(root_dir):
            for root, _, names in os.walk(root_dir):
                for name in names:
                    full_path = os.path.join(root, name)
                    if os.path.isfile(full_path):
                        try:
                            groups[category].append(context_file_item(category, full_path))
                        except OSError:
                            continue

    for name in ['README.md', 'USAGE.md', 'TASK_BOARD.md']:
        full_path = os.path.join(PROJECT_ROOT, name)
        if os.path.isfile(full_path):
            groups['docs'].append(context_file_item('docs', full_path))

    output_files = normalize_output_files(collect_output_files_data())
    for item in output_files:
        full_path = os.path.join(PROJECT_ROOT, item['path'])
        if os.path.isfile(full_path) and item['category'] in groups:
            try:
                groups[item['category']].append(context_file_item(item['category'], full_path, 'generated'))
            except OSError:
                continue

    if os.path.isdir(AI_FLOW_UPLOAD_DIR):
        for root, _, names in os.walk(AI_FLOW_UPLOAD_DIR):
            for name in names:
                full_path = os.path.join(root, name)
                if os.path.isfile(full_path):
                    try:
                        groups['uploads'].append(context_file_item('uploads', full_path, 'upload'))
                    except OSError:
                        continue

    for category in groups:
        seen = {}
        for item in groups[category]:
            seen[item['path']] = item
        groups[category] = sorted(seen.values(), key=lambda item: item['path'])
    return groups

def resolve_context_attachment(attachment):
    source = str(attachment.get('source') or 'project')
    path = str(attachment.get('path') or '').strip().replace('\\', '/')
    if not path:
        return None
    full_path = os.path.abspath(os.path.join(PROJECT_ROOT, path))
    if source == 'upload':
        if not is_within_directory(full_path, AI_FLOW_UPLOAD_DIR):
            return None
    else:
        if not is_within_directory(full_path, PROJECT_ROOT):
            return None
    if not os.path.isfile(full_path):
        return None
    try:
        return context_file_item(attachment.get('category') or source, full_path, source)
    except OSError:
        return None

def read_context_file_excerpt(item, remaining_budget):
    full_path = os.path.abspath(os.path.join(PROJECT_ROOT, item['path']))
    size = item.get('size') or os.path.getsize(full_path)
    meta = f"{item['path']} ({size} bytes, {item.get('mime') or item.get('type') or 'unknown'})"
    if remaining_budget <= 0:
        return f"[文件仅摘要] {meta}\n"
    if size > AI_CONTEXT_TEXT_LIMIT:
        return f"[文件过大，仅摘要] {meta}\n"
    try:
        with open(full_path, 'rb') as f:
            data = f.read(min(size, remaining_budget, AI_CONTEXT_TEXT_LIMIT) + 1)
        if b'\x00' in data[:1024]:
            return f"[二进制文件，仅摘要] {meta}\n"
        text = data.decode('utf-8', errors='replace')
        if len(text.encode('utf-8', errors='ignore')) > remaining_budget:
            text = text.encode('utf-8', errors='ignore')[:remaining_budget].decode('utf-8', errors='ignore')
        return f"[文件] {meta}\n{text}\n"
    except Exception as exc:
        return f"[文件读取失败] {meta}: {exc}\n"

def build_node_file_context(node):
    sections = []
    total_used = 0
    attachments = node.get('attachments') or []
    if node.get('stage_context_enabled', True):
        sections.append(f"[阶段说明] {AI_FLOW_STAGE_CONTEXTS.get(node.get('type'), '')}")
    custom_context = (node.get('custom_context') or '').strip()
    if custom_context:
        sections.append(f"[自定义上下文]\n{custom_context[:10000]}")
    for attachment in attachments[:AI_CONTEXT_MAX_ATTACHMENTS]:
        item = resolve_context_attachment(attachment)
        if not item:
            sections.append(f"[附件不可用] {attachment.get('path') or attachment.get('name') or 'unknown'}")
            continue
        excerpt = read_context_file_excerpt(item, AI_CONTEXT_TOTAL_LIMIT - total_used)
        total_used += len(excerpt.encode('utf-8', errors='ignore'))
        sections.append(excerpt)
    return '\n\n'.join(section for section in sections if section)

def current_design_name():
    with state_lock:
        return flow_state.get('current_design') or 'picorv32'

def openroad_script_for_design(design):
    if design == 'picorv32':
        return 'scripts/run_picorv32_librelane.sh'
    if design == 'serv':
        return 'scripts/run_serv_librelane.sh'
    return None

def run_openroad_flow_for_ai(run_id):
    design = current_design_name()
    script = openroad_script_for_design(design)
    if not script:
        return {
            'success': False,
            'warning': True,
            'output': [f'OpenROAD/LibreLane mode only supports picorv32 and serv in this UI; current design is {design}.'],
        }
    script_path = os.path.join(PROJECT_ROOT, script)
    if not os.path.isfile(script_path):
        return {'success': False, 'warning': True, 'output': [f'OpenROAD/LibreLane 脚本不存在: {script}']}
    librelane_check = subprocess.run(['/usr/bin/python3', '-c', 'import librelane'], capture_output=True, text=True)
    if librelane_check.returncode != 0:
        return {
            'success': False,
            'warning': True,
            'output': ['当前环境无法 import librelane，OpenROAD/LibreLane 流程未执行。请先安装 LibreLane/OpenROAD 工具链。'],
        }
    tag = f"ai_flow_{run_id[:12]}"
    add_log(f"OpenROAD/LibreLane 流程: {design} ({tag})", 'info')
    return run_command(f'bash {shell_quote(script)} {shell_quote(tag)}', step='full_flow')

def ai_flow_event(run_id, event, payload=None):
    payload = payload or {}
    data = {
        'event': event,
        'timestamp': datetime.now().isoformat(),
        **payload,
    }
    subscribers = []
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if not run:
            return data
        run['events'].append(data)
        run['updated_at'] = data['timestamp']
        subscribers = list(run.get('subscribers', []))
    for subscriber in subscribers:
        subscriber.put(data)
    return data

def mark_ai_flow_run_cancelled(run_id, message='用户终止工作流'):
    node_events = []
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if not run:
            return
        run['cancel_requested'] = True
        run['status'] = 'cancelled'
        run['finished_at'] = datetime.now().isoformat()
        run['updated_at'] = run['finished_at']
        run['current_process'] = None
        for node_id, state in run.get('node_states', {}).items():
            if state.get('status') in ('done', 'warning', 'error', 'cancelled'):
                continue
            state['status'] = 'cancelled'
            state['message'] = message
            state['blocked'] = True
            outputs = state.setdefault('outputs', {'pre': '', 'command': '', 'post': ''})
            if message not in outputs.get('command', ''):
                outputs['command'] = outputs.get('command', '') + f"{message}\n"
            state['summary'] = ai_flow_card_summary(outputs.get('post') or outputs.get('command'))
            state['updated_at'] = run['updated_at']
            node_events.append((node_id, state.get('summary')))
    for node_id, summary in node_events:
        ai_flow_event(run_id, 'node_status', {'node_id': node_id, 'status': 'cancelled', 'message': message})
        ai_flow_event(run_id, 'node_summary', {'node_id': node_id, 'summary': summary or message})
    ai_flow_event(run_id, 'run_cancelled', {'run_id': run_id, 'status': 'cancelled', 'message': message})

def set_ai_flow_node_state(run_id, node_id, **changes):
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if not run:
            return
        state = run['node_states'].setdefault(node_id, {})
        state.update(changes)
        state['updated_at'] = datetime.now().isoformat()

def set_ai_flow_node_summary(run_id, node_id):
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if not run:
            return ''
        state = run['node_states'].setdefault(node_id, {})
        outputs = state.setdefault('outputs', {'pre': '', 'command': '', 'post': ''})
        summary = ai_flow_card_summary(outputs.get('post') or outputs.get('command') or state.get('message'))
        state['summary'] = summary
        state['updated_at'] = datetime.now().isoformat()
    ai_flow_event(run_id, 'node_summary', {'node_id': node_id, 'summary': summary})
    return summary

def append_ai_flow_output(run_id, node_id, section, text):
    if not text:
        return
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if not run:
            return
        outputs = run['node_states'][node_id].setdefault('outputs', {'pre': '', 'command': '', 'post': ''})
        outputs[section] = outputs.get(section, '') + text
    ai_flow_event(run_id, 'ai_delta', {'node_id': node_id, 'section': section, 'delta': text})

def normalize_ai_flow_payload(nodes, edges):
    meta = ai_flow_stage_meta()
    if not isinstance(nodes, list) or not nodes:
        raise ValueError('工作流至少需要一个节点')
    if len(nodes) > 64:
        raise ValueError('工作流节点过多')

    normalized_nodes = []
    seen = set()
    for idx, node in enumerate(nodes):
        node_id = str(node.get('id') or '').strip()
        if not node_id:
            node_id = f"node_{uuid.uuid4().hex[:8]}"
        if node_id in seen:
            raise ValueError(f'重复节点 ID: {node_id}')
        seen.add(node_id)
        node_type = str(node.get('type') or '').strip()
        if node_type not in meta:
            raise ValueError(f'未知节点类型: {node_type}')
        try:
            x = float(node.get('x', 120 + idx * 24))
            y = float(node.get('y', 120 + idx * 24))
        except (TypeError, ValueError):
            x, y = 120 + idx * 24, 120 + idx * 24
        prompt = str(node.get('prompt') or '')[:5000]
        attachments = node.get('attachments') or []
        if not isinstance(attachments, list):
            attachments = []
        normalized_attachments = []
        for attachment in attachments[:AI_CONTEXT_MAX_ATTACHMENTS]:
            if not isinstance(attachment, dict):
                continue
            normalized_attachments.append({
                'source': str(attachment.get('source') or 'project')[:40],
                'category': str(attachment.get('category') or '')[:40],
                'name': str(attachment.get('name') or '')[:160],
                'path': str(attachment.get('path') or '')[:500],
                'type': str(attachment.get('type') or '')[:40],
                'size': attachment.get('size', 0),
            })
        normalized_nodes.append({
            'id': node_id,
            'type': node_type,
            'title': str(node.get('title') or meta[node_type]['label'])[:80],
            'prompt': prompt,
            'custom_context': str(node.get('custom_context') or node.get('customContext') or '')[:10000],
            'stage_context_enabled': bool(node.get('stage_context_enabled', node.get('stageContextEnabled', True))),
            'attachments': normalized_attachments,
            'x': x,
            'y': y,
            'order': int(node.get('order', idx) or idx),
        })

    node_ids = {node['id'] for node in normalized_nodes}
    normalized_edges = []
    for idx, edge in enumerate(edges or []):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get('source') or edge.get('from') or '').strip()
        target = str(edge.get('target') or edge.get('to') or '').strip()
        if source not in node_ids or target not in node_ids:
            raise ValueError('连线包含不存在的节点')
        edge_id = str(edge.get('id') or f"edge_{idx}_{source}_{target}")[:120]
        normalized_edges.append({'id': edge_id, 'source': source, 'target': target})

    return normalized_nodes, normalized_edges

def ai_flow_topological_order(nodes, edges):
    by_id = {node['id']: node for node in nodes}
    indegree = {node['id']: 0 for node in nodes}
    outgoing = {node['id']: [] for node in nodes}
    predecessors = {node['id']: [] for node in nodes}
    seen_edges = set()

    for edge in edges:
        pair = (edge['source'], edge['target'])
        if pair in seen_edges:
            continue
        seen_edges.add(pair)
        outgoing[edge['source']].append(edge['target'])
        predecessors[edge['target']].append(edge['source'])
        indegree[edge['target']] += 1

    def node_sort_key(node_id):
        node = by_id[node_id]
        return (node.get('x', 0), node.get('order', 0), node_id)

    ready = sorted([node_id for node_id, degree in indegree.items() if degree == 0], key=node_sort_key)
    order = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for target in sorted(outgoing[node_id], key=node_sort_key):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort(key=node_sort_key)

    if len(order) != len(nodes):
        raise ValueError('工作流存在环，请删除循环连线后再运行')
    return order, predecessors

def public_ai_flow_run(run):
    return {
        'run_id': run['run_id'],
        'status': run['status'],
        'cancel_requested': bool(run.get('cancel_requested')),
        'created_at': run['created_at'],
        'updated_at': run.get('updated_at'),
        'finished_at': run.get('finished_at'),
        'model': run.get('model'),
        'backend_engine': run.get('backend_engine', 'ieda'),
        'nodes': run.get('nodes', []),
        'edges': run.get('edges', []),
        'order': run.get('order', []),
        'node_states': run.get('node_states', {}),
        'events': run.get('events', []),
        'error': run.get('error'),
    }

def has_active_ai_flow_run():
    with ai_flow_lock:
        return any(run.get('status') in ('queued', 'running', 'cancelling') for run in ai_flow_runs.values())

def get_openai_event_value(event, key, default=None):
    if isinstance(event, dict):
        return event.get(key, default)
    return getattr(event, key, default)

def build_ai_flow_prompt(node, phase, context):
    phase_title = '运行前规划' if phase == 'pre' else '运行后总结'
    return f"""你是 SiliconTrace 的 AI Flow 助手，面向开源数字芯片设计流程。
请使用中文，保持工程判断清晰、简洁、可执行。不要生成 shell 命令，不要改变后端固定 EDA 命令。

当前任务: {phase_title}
当前设计: {context.get('design')}
后端工具: {context.get('backend_engine') or 'ieda'}
流程块: {node.get('title')} ({node.get('type')})
用户提示词:
{node.get('prompt') or '无'}

节点文件与上下文:
{context.get('file_context') or '无'}

上游节点摘要:
{context.get('upstream_summary') or '无'}

命令执行结果:
{context.get('command_summary') or '尚未执行'}

生成文件:
{context.get('files_summary') or '暂无'}

请输出:
1. 对当前阶段最关键的判断。
2. 需要用户注意的风险或下一步。
3. 如果是运行后总结，说明可用产物和异常。"""

def stream_openai_response(run_id, node, section, context):
    phase_label = '运行前规划' if section == 'pre' else '运行后总结'
    if ai_flow_cancel_requested(run_id):
        return {'ok': False, 'cancelled': True, 'message': '用户终止工作流'}
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id) or {}
        openai_config = run.get('openai_config') or {}
    api_key = openai_config.get('api_key') or os.environ.get('OPENAI_API_KEY')
    base_url = openai_config.get('base_url') or os.environ.get('OPENAI_BASE_URL') or os.environ.get('OPENAI_API_BASE')
    model = openai_config.get('model') or os.environ.get('OPENAI_MODEL', AI_FLOW_MODEL)
    if not api_key:
        message = f"OPENAI_API_KEY 未设置，已跳过 AI {phase_label}；EDA 命令会继续执行。\n"
        set_ai_flow_node_state(run_id, node['id'], ai_warning=True, message='OpenAI API Key 未配置')
        append_ai_flow_output(run_id, node['id'], section, message)
        ai_flow_event(run_id, 'ai_done', {'node_id': node['id'], 'section': section, 'warning': True})
        return {'ok': False, 'warning': True, 'message': message}

    try:
        from openai import OpenAI
    except Exception as exc:
        message = f"Python openai SDK 不可用，已跳过 AI {phase_label}: {exc}\n"
        set_ai_flow_node_state(run_id, node['id'], ai_warning=True, message='openai SDK 不可用')
        append_ai_flow_output(run_id, node['id'], section, message)
        ai_flow_event(run_id, 'ai_done', {'node_id': node['id'], 'section': section, 'warning': True})
        return {'ok': False, 'warning': True, 'message': message}

    prompt = build_ai_flow_prompt(node, section, context)
    try:
        client_kwargs = {'api_key': api_key}
        if base_url:
            client_kwargs['base_url'] = base_url
        client = OpenAI(**client_kwargs)
        stream = client.responses.create(
            model=model,
            input=prompt,
            stream=True,
        )
        saw_delta = False
        for event in stream:
            if ai_flow_cancel_requested(run_id):
                append_ai_flow_output(run_id, node['id'], section, f"\nAI {phase_label} 已因用户终止而停止。\n")
                ai_flow_event(run_id, 'ai_done', {'node_id': node['id'], 'section': section, 'cancelled': True})
                return {'ok': False, 'cancelled': True, 'message': '用户终止工作流'}
            event_type = get_openai_event_value(event, 'type', '')
            if event_type == 'response.output_text.delta':
                delta = get_openai_event_value(event, 'delta', '')
                if delta:
                    saw_delta = True
                    append_ai_flow_output(run_id, node['id'], section, delta)
            elif event_type == 'response.completed':
                ai_flow_event(run_id, 'ai_done', {'node_id': node['id'], 'section': section})
            elif event_type == 'error':
                error = get_openai_event_value(event, 'error', 'OpenAI streaming error')
                append_ai_flow_output(run_id, node['id'], section, f"\nAI {phase_label} 出错: {error}\n")
                set_ai_flow_node_state(run_id, node['id'], ai_warning=True, message=str(error))
                ai_flow_event(run_id, 'ai_done', {'node_id': node['id'], 'section': section, 'warning': True})
                return {'ok': False, 'warning': True, 'message': str(error)}
        if not saw_delta:
            append_ai_flow_output(run_id, node['id'], section, f"AI {phase_label} 已完成，但没有返回文本。\n")
        ai_flow_event(run_id, 'ai_done', {'node_id': node['id'], 'section': section})
        return {'ok': True}
    except Exception as exc:
        message = f"AI {phase_label} 调用失败: {exc}\n"
        append_ai_flow_output(run_id, node['id'], section, message)
        set_ai_flow_node_state(run_id, node['id'], ai_warning=True, message=str(exc))
        ai_flow_event(run_id, 'ai_done', {'node_id': node['id'], 'section': section, 'warning': True})
        return {'ok': False, 'warning': True, 'message': message}

def workflow_context_for_node(run, node_id):
    predecessors = run.get('predecessors', {}).get(node_id, [])
    chunks = []
    for pred_id in predecessors:
        pred_state = run['node_states'].get(pred_id, {})
        pred_node = run.get('node_by_id', {}).get(pred_id, {'title': pred_id})
        summary = pred_state.get('outputs', {}).get('post') or pred_state.get('outputs', {}).get('command') or ''
        summary = summary.strip().replace('\r', '')[-1200:]
        if summary:
            chunks.append(f"{pred_node.get('title')}: {summary}")
    return '\n\n'.join(chunks)

def execute_ai_flow_run(run_id):
    ai_flow_thread.run_id = run_id
    try:
        with ai_flow_lock:
            run = ai_flow_runs[run_id]
            if run.get('cancel_requested'):
                run['status'] = 'cancelling'
            else:
                run['status'] = 'running'
            run['updated_at'] = datetime.now().isoformat()
        ai_flow_event(run_id, 'run_started', {'run_id': run_id})
        if ai_flow_cancel_requested(run_id):
            mark_ai_flow_run_cancelled(run_id)
            return

        with ai_flow_lock:
            run = ai_flow_runs[run_id]
            order = list(run['order'])
            backend_engine = run.get('backend_engine', 'ieda')

        for node_id in order:
            if ai_flow_cancel_requested(run_id):
                mark_ai_flow_run_cancelled(run_id)
                return
            with ai_flow_lock:
                run = ai_flow_runs[run_id]
                node = run['node_by_id'][node_id]
                predecessor_ids = run.get('predecessors', {}).get(node_id, [])
                blocked = [
                    pred for pred in predecessor_ids
                    if run['node_states'].get(pred, {}).get('blocked') or run['node_states'].get(pred, {}).get('status') == 'error'
                ]

            if blocked:
                message = 'upstream failed'
                set_ai_flow_node_state(run_id, node_id, status='warning', message=message, blocked=True)
                append_ai_flow_output(run_id, node_id, 'command', f"跳过: {message}\n")
                ai_flow_event(run_id, 'node_status', {'node_id': node_id, 'status': 'warning', 'message': message})
                continue

            add_log(f"AI Flow 节点开始: {node['title']}", 'info', node['type'] if node['type'] != 'full_flow' else None)
            set_ai_flow_node_state(run_id, node_id, status='ai-pre', started_at=datetime.now().isoformat(), message=AI_FLOW_STATUS_TEXT['ai-pre'])
            ai_flow_event(run_id, 'node_status', {'node_id': node_id, 'status': 'ai-pre', 'message': AI_FLOW_STATUS_TEXT['ai-pre']})

            with ai_flow_lock:
                run = ai_flow_runs[run_id]
                upstream_summary = workflow_context_for_node(run, node_id)
                backend_engine = run.get('backend_engine', 'ieda')
            file_context = build_node_file_context(node)

            pre_context = {
                'design': flow_state.get('current_design'),
                'backend_engine': backend_engine,
                'upstream_summary': upstream_summary,
                'file_context': file_context,
            }
            pre_result = stream_openai_response(run_id, node, 'pre', pre_context)
            if pre_result.get('cancelled') or ai_flow_cancel_requested(run_id):
                mark_ai_flow_run_cancelled(run_id)
                return

            before_files = output_snapshot()
            if node['type'] == 'custom_ai':
                result = {'success': True, 'output': ['自定义 AI 节点不执行 EDA 命令。']}
            else:
                if ai_flow_cancel_requested(run_id):
                    mark_ai_flow_run_cancelled(run_id)
                    return
                set_ai_flow_node_state(run_id, node_id, status='running-command', message=AI_FLOW_STATUS_TEXT['running-command'])
                ai_flow_event(run_id, 'node_status', {'node_id': node_id, 'status': 'running-command', 'message': AI_FLOW_STATUS_TEXT['running-command']})
                try:
                    if backend_engine == 'openroad' and node['type'] in AI_FLOW_BACKEND_STAGES:
                        with ai_flow_lock:
                            run = ai_flow_runs[run_id]
                            openroad_done = bool(run.get('openroad_done'))
                            openroad_result = run.get('openroad_result')
                        if openroad_done:
                            result = openroad_result or {'success': True, 'output': ['复用本次 OpenROAD/LibreLane 产物。']}
                        else:
                            result = run_openroad_flow_for_ai(run_id)
                            with ai_flow_lock:
                                run = ai_flow_runs[run_id]
                                run['openroad_done'] = True
                                run['openroad_result'] = result
                    else:
                        meta = ai_flow_stage_meta()[node['type']]
                        func = meta.get('func')
                        result = func() if func else {'success': True, 'output': ['AI-only node']}
                except Exception as exc:
                    result = {'success': False, 'error': str(exc), 'output': []}
                    add_log(f"AI Flow 节点异常: {exc}", 'error', node['type'])
            if result.get('cancelled') or ai_flow_cancel_requested(run_id):
                append_ai_flow_output(run_id, node_id, 'command', '工作流已被用户终止。\n')
                mark_ai_flow_run_cancelled(run_id)
                return
            after_files = output_snapshot()
            generated_files = generated_files_for_stage('full_flow' if backend_engine == 'openroad' and node['type'] in AI_FLOW_BACKEND_STAGES else node['type'], before_files, after_files)

            command_output = result.get('output') or []
            command_tail = '\n'.join(command_output[-40:]) if command_output else result.get('error') or '命令没有返回日志。'
            append_ai_flow_output(run_id, node_id, 'command', command_tail + '\n')

            with state_lock:
                step_state = flow_state['steps'].get(node['type'], {}) if node['type'] != 'full_flow' else {}
                step_status = step_state.get('status')

            command_failed = not result.get('success') and step_status != 'warning' and not result.get('warning')
            command_warning = step_status == 'warning' or bool(result.get('warning'))
            set_ai_flow_node_state(run_id, node_id, files=generated_files, command_result={
                'success': bool(result.get('success')),
                'returncode': result.get('returncode'),
                'error': result.get('error'),
                'step_status': step_status,
                'backend_engine': backend_engine,
            })
            ai_flow_event(run_id, 'command_complete', {
                'node_id': node_id,
                'success': bool(result.get('success')),
                'returncode': result.get('returncode'),
                'error': result.get('error'),
                'step_status': step_status,
                'backend_engine': backend_engine,
            })
            ai_flow_event(run_id, 'node_files', {'node_id': node_id, 'files': generated_files})

            set_ai_flow_node_state(run_id, node_id, status='ai-post', message=AI_FLOW_STATUS_TEXT['ai-post'])
            ai_flow_event(run_id, 'node_status', {'node_id': node_id, 'status': 'ai-post', 'message': AI_FLOW_STATUS_TEXT['ai-post']})
            files_summary = '\n'.join(f"- {f['path']} ({f.get('size', 0)} bytes)" for f in generated_files[:20])
            post_context = {
                'design': flow_state.get('current_design'),
                'backend_engine': backend_engine,
                'upstream_summary': upstream_summary,
                'command_summary': command_tail[-2500:],
                'files_summary': files_summary,
                'file_context': file_context,
            }
            post_result = stream_openai_response(run_id, node, 'post', post_context)
            set_ai_flow_node_summary(run_id, node_id)
            if post_result.get('cancelled') or ai_flow_cancel_requested(run_id):
                mark_ai_flow_run_cancelled(run_id)
                return

            with ai_flow_lock:
                node_state = ai_flow_runs[run_id]['node_states'][node_id]
                ai_warning = node_state.get('ai_warning')

            if command_failed:
                final_status = 'error'
                blocked = True
                message = result.get('error') or 'EDA 命令失败'
            elif command_warning or ai_warning:
                final_status = 'warning'
                blocked = False
                message = step_state.get('error') or node_state.get('message') or '完成但有警告'
            else:
                final_status = 'done'
                blocked = False
                message = AI_FLOW_STATUS_TEXT['done']

            set_ai_flow_node_state(
                run_id,
                node_id,
                status=final_status,
                blocked=blocked,
                message=message,
                finished_at=datetime.now().isoformat(),
            )
            ai_flow_event(run_id, 'node_status', {'node_id': node_id, 'status': final_status, 'message': message})

        if ai_flow_cancel_requested(run_id):
            mark_ai_flow_run_cancelled(run_id)
            return
        with ai_flow_lock:
            run = ai_flow_runs[run_id]
            run['status'] = 'completed'
            run['finished_at'] = datetime.now().isoformat()
            run['updated_at'] = run['finished_at']
        ai_flow_event(run_id, 'run_complete', {'run_id': run_id, 'status': 'completed'})
    except Exception as exc:
        if ai_flow_cancel_requested(run_id):
            mark_ai_flow_run_cancelled(run_id)
            return
        with ai_flow_lock:
            if run_id in ai_flow_runs:
                ai_flow_runs[run_id]['status'] = 'error'
                ai_flow_runs[run_id]['error'] = str(exc)
                ai_flow_runs[run_id]['finished_at'] = datetime.now().isoformat()
        ai_flow_event(run_id, 'run_error', {'run_id': run_id, 'error': str(exc)})
    finally:
        try:
            del ai_flow_thread.run_id
        except AttributeError:
            pass

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

@app.route('/api/ai_flow/run', methods=['POST'])
def api_ai_flow_run():
    data = request.get_json(silent=True) or {}
    backend_engine = str(data.get('backend_engine') or data.get('backendEngine') or 'ieda').lower()
    openai_api_key = str(data.get('openai_api_key') or data.get('openaiApiKey') or '').strip()
    openai_base_url = str(data.get('openai_base_url') or data.get('openaiBaseUrl') or data.get('api_base_url') or '').strip()
    if backend_engine not in ('ieda', 'openroad'):
        return jsonify({'error': f'未知后端工具: {backend_engine}'}), 400
    if len(openai_api_key) > 4096 or len(openai_base_url) > 1024:
        return jsonify({'error': 'OpenAI 配置过长'}), 400
    try:
        nodes, edges = normalize_ai_flow_payload(data.get('nodes') or [], data.get('edges') or [])
        order, predecessors = ai_flow_topological_order(nodes, edges)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    with state_lock:
        eda_running = bool(flow_state.get('running'))
    if eda_running or has_active_ai_flow_run():
        return jsonify({'error': '已有流程正在执行，请等待完成'}), 409

    run_id = uuid.uuid4().hex
    now = datetime.now().isoformat()
    node_by_id = {node['id']: node for node in nodes}
    node_states = {
        node['id']: {
            'status': 'pending',
            'message': '等待中',
            'outputs': {'pre': '', 'command': '', 'post': ''},
            'files': [],
            'summary': '',
            'ai_warning': False,
            'blocked': False,
        }
        for node in nodes
    }

    with ai_flow_lock:
        ai_flow_runs[run_id] = {
            'run_id': run_id,
            'status': 'queued',
            'cancel_requested': False,
            'created_at': now,
            'updated_at': now,
            'finished_at': None,
            'model': os.environ.get('OPENAI_MODEL', AI_FLOW_MODEL),
            'openai_config': {
                'api_key': openai_api_key,
                'base_url': openai_base_url,
                'model': os.environ.get('OPENAI_MODEL', AI_FLOW_MODEL),
            },
            'backend_engine': backend_engine,
            'openroad_done': False,
            'openroad_result': None,
            'nodes': nodes,
            'edges': edges,
            'node_by_id': node_by_id,
            'node_states': node_states,
            'order': order,
            'predecessors': predecessors,
            'events': [],
            'subscribers': [],
            'current_process': None,
            'error': None,
        }

    thread = threading.Thread(target=execute_ai_flow_run, args=(run_id,), daemon=True)
    thread.start()
    return jsonify({'success': True, 'run_id': run_id, 'order': order})

@app.route('/api/ai_flow/runs/<run_id>/cancel', methods=['POST'])
def api_ai_flow_cancel(run_id):
    process = None
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if not run:
            return jsonify({'error': 'run not found'}), 404
        if run.get('status') in ('completed', 'error', 'cancelled'):
            return jsonify({'success': True, 'status': run.get('status')})
        run['cancel_requested'] = True
        run['status'] = 'cancelling'
        run['updated_at'] = datetime.now().isoformat()
        process = run.get('current_process')
    terminate_process(process)
    ai_flow_event(run_id, 'run_cancelling', {'run_id': run_id, 'status': 'cancelling', 'message': '正在终止工作流'})
    return jsonify({'success': True, 'status': 'cancelling'})

@app.route('/api/ai_flow/stream/<run_id>')
def api_ai_flow_stream(run_id):
    def format_sse(event):
        event_name = event.get('event', 'message')
        payload = json.dumps(event, ensure_ascii=False)
        return f"event: {event_name}\ndata: {payload}\n\n"

    def generate():
        subscriber = queue.Queue()
        with ai_flow_lock:
            run = ai_flow_runs.get(run_id)
            if not run:
                error = {'event': 'run_error', 'timestamp': datetime.now().isoformat(), 'run_id': run_id, 'error': 'run not found'}
                yield format_sse(error)
                return
            historical = list(run.get('events', []))
            completed = run.get('status') in ('completed', 'error', 'cancelled')
            if not completed:
                run.setdefault('subscribers', []).append(subscriber)

        for event in historical:
            yield format_sse(event)

        if completed:
            return

        try:
            while True:
                try:
                    event = subscriber.get(timeout=15)
                except queue.Empty:
                    yield ": ping\n\n"
                    continue
                yield format_sse(event)
                if event.get('event') in ('run_complete', 'run_error', 'run_cancelled'):
                    break
        finally:
            with ai_flow_lock:
                run = ai_flow_runs.get(run_id)
                if run and subscriber in run.get('subscribers', []):
                    run['subscribers'].remove(subscriber)

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/ai_flow/runs/<run_id>')
def api_ai_flow_run_snapshot(run_id):
    with ai_flow_lock:
        run = ai_flow_runs.get(run_id)
        if not run:
            return jsonify({'error': 'run not found'}), 404
        snapshot = public_ai_flow_run(run)
    return jsonify(snapshot)

@app.route('/api/ai_flow/context_files', methods=['GET'])
def api_ai_flow_context_files():
    return jsonify({
        'groups': collect_ai_context_files(),
        'stage_contexts': AI_FLOW_STAGE_CONTEXTS,
        'limits': {
            'file_text_bytes': AI_CONTEXT_TEXT_LIMIT,
            'node_total_bytes': AI_CONTEXT_TOTAL_LIMIT,
            'max_attachments': AI_CONTEXT_MAX_ATTACHMENTS,
        }
    })

@app.route('/api/ai_flow/context_files', methods=['POST'])
def api_ai_flow_context_file_upload():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    node_type = secure_filename(str(request.form.get('node_type') or 'common')) or 'common'
    if node_type not in AI_FLOW_STAGE_LABELS:
        node_type = 'common'
    safe_name = secure_filename(file.filename) or f"context_{uuid.uuid4().hex[:8]}.txt"
    filename = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    save_dir = os.path.join(AI_FLOW_UPLOAD_DIR, node_type)
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    file.save(save_path)
    item = context_file_item('uploads', save_path, 'upload')
    return jsonify({'success': True, 'file': item})

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
    return jsonify(collect_output_files_data())
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

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False, threaded=True)
