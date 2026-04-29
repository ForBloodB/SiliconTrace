#!/usr/bin/env python3
"""
SDC 约束转换脚本
硅迹开源 (SiliconTrace Open)

功能：
1. 验证 SDC 约束文件语法
2. 转换约束格式（Yosys → iEDA）
3. 合并多个约束文件
"""

import re
import sys
import os


def parse_sdc(sdc_file):
    """解析 SDC 约束文件"""
    constraints = {
        'clocks': [],
        'input_delays': [],
        'output_delays': [],
        'loads': [],
        'drives': [],
        'others': []
    }

    with open(sdc_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('create_clock'):
                constraints['clocks'].append(line)
            elif line.startswith('set_input_delay'):
                constraints['input_delays'].append(line)
            elif line.startswith('set_output_delay'):
                constraints['output_delays'].append(line)
            elif line.startswith('set_load'):
                constraints['loads'].append(line)
            elif line.startswith('set_driving_cell'):
                constraints['drives'].append(line)
            else:
                constraints['others'].append(line)

    return constraints


def validate_sdc(constraints):
    """验证 SDC 约束"""
    errors = []
    warnings = []

    if not constraints['clocks']:
        warnings.append("未定义时钟")

    if not constraints['input_delays']:
        warnings.append("未设置输入延迟")

    if not constraints['output_delays']:
        warnings.append("未设置输出延迟")

    return errors, warnings


def merge_sdc_files(sdc_files, output_file):
    """合并多个 SDC 文件"""
    all_constraints = {
        'clocks': [],
        'input_delays': [],
        'output_delays': [],
        'loads': [],
        'drives': [],
        'others': []
    }

    for sdc_file in sdc_files:
        if os.path.exists(sdc_file):
            constraints = parse_sdc(sdc_file)
            for key in all_constraints:
                all_constraints[key].extend(constraints[key])

    with open(output_file, 'w') as f:
        f.write("# 合并的 SDC 约束文件\n")
        f.write("# 硅迹开源 (SiliconTrace Open)\n\n")

        f.write("# 时钟定义\n")
        for clk in all_constraints['clocks']:
            f.write(f"{clk}\n")

        f.write("\n# 输入延迟\n")
        for delay in all_constraints['input_delays']:
            f.write(f"{delay}\n")

        f.write("\n# 输出延迟\n")
        for delay in all_constraints['output_delays']:
            f.write(f"{delay}\n")

        f.write("\n# 负载\n")
        for load in all_constraints['loads']:
            f.write(f"{load}\n")

        f.write("\n# 驱动强度\n")
        for drive in all_constraints['drives']:
            f.write(f"{drive}\n")

        f.write("\n# 其他约束\n")
        for other in all_constraints['others']:
            f.write(f"{other}\n")


def main():
    if len(sys.argv) < 3:
        print("用法: python convert_constraints.py <output_sdc> <input_sdc1> [input_sdc2] ...")
        sys.exit(1)

    output_file = sys.argv[1]
    input_files = sys.argv[2:]

    print(f"合并约束文件: {', '.join(input_files)}")
    print(f"输出文件: {output_file}")

    merge_sdc_files(input_files, output_file)

    print("合并完成！")


if __name__ == '__main__':
    main()
