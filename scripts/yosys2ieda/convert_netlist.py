#!/usr/bin/env python3
"""
Yosys → iEDA 网表转换脚本
硅迹开源 (SiliconTrace Open)

功能：
1. 将 Yosys 输出的 JSON 网表转换为 iEDA 可读的格式
2. 提取时序约束信息
3. 生成 iEDA 配置文件
"""

import json
import sys
import os
import re
from pathlib import Path


def parse_yosys_json(json_file):
    """解析 Yosys JSON 网表"""
    with open(json_file, 'r') as f:
        data = json.load(f)

    modules = {}
    for name, module in data.get('modules', {}).items():
        modules[name] = {
            'ports': {},
            'cells': [],
            'nets': []
        }

        # 提取端口
        for port_name, port_info in module.get('ports', {}).items():
            modules[name]['ports'][port_name] = {
                'direction': port_info.get('direction', 'input'),
                'bits': port_info.get('bits', [])
            }

        # 提取单元
        for cell_name, cell_info in module.get('cells', {}).items():
            modules[name]['cells'].append({
                'name': cell_name,
                'type': cell_info.get('type', ''),
                'port_directions': cell_info.get('port_directions', {}),
                'connections': cell_info.get('connections', {})
            })

    return modules


def convert_to_ieda_format(modules, output_dir):
    """转换为 iEDA 格式"""
    os.makedirs(output_dir, exist_ok=True)

    for module_name, module_data in modules.items():
        # 生成端口列表
        ports_file = os.path.join(output_dir, f'{module_name}_ports.tcl')
        with open(ports_file, 'w') as f:
            f.write(f"# {module_name} 端口定义\n")
            for port_name, port_info in module_data['ports'].items():
                f.write(f"create_port -name {port_name} -direction {port_info['direction']}\n")

        # 生成单元列表
        cells_file = os.path.join(output_dir, f'{module_name}_cells.tcl')
        with open(cells_file, 'w') as f:
            f.write(f"# {module_name} 单元实例\n")
            for cell in module_data['cells']:
                f.write(f"create_cell -name {cell['name']} -lib_cell {cell['type']}\n")


def extract_sdc_from_verilog(verilog_file, output_sdc):
    """从 Verilog 文件提取基本时序约束"""
    with open(verilog_file, 'r') as f:
        content = f.read()

    # 查找时钟端口
    clock_ports = re.findall(r'input\s+(?:\[[\d:]+\]\s+)?(\w*clk\w*)', content, re.IGNORECASE)

    with open(output_sdc, 'w') as f:
        f.write("# 自动生成的 SDC 约束\n")
        f.write("# 硅迹开源 (SiliconTrace Open)\n\n")

        for clk in clock_ports:
            f.write(f"create_clock -name {clk} -period 10.0 [get_ports {clk}]\n")

        f.write("\n# 输入延迟\n")
        f.write("set_input_delay -clock clk -max 2.0 [all_inputs]\n")
        f.write("set_input_delay -clock clk -min 1.0 [all_inputs]\n")

        f.write("\n# 输出延迟\n")
        f.write("set_output_delay -clock clk -max 2.0 [all_outputs]\n")
        f.write("set_output_delay -clock clk -min 1.0 [all_outputs]\n")


def main():
    if len(sys.argv) < 3:
        print("用法: python convert_netlist.py <yosys_json> <output_dir>")
        sys.exit(1)

    json_file = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"转换网表: {json_file}")
    print(f"输出目录: {output_dir}")

    # 解析网表
    modules = parse_yosys_json(json_file)

    # 转换格式
    convert_to_ieda_format(modules, output_dir)

    print("转换完成！")


if __name__ == '__main__':
    main()
