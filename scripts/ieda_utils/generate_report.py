#!/usr/bin/env python3
"""
iEDA 报告生成脚本
硅迹开源 (SiliconTrace Open)

功能：
1. 解析 STA 报告
2. 生成时序分析摘要
3. 生成功耗分析摘要
4. 输出可视化数据
"""

import re
import sys
import os
import json


def parse_sta_report(report_file):
    """解析 STA 报告"""
    timing_data = {
        'setup': {'paths': [], 'slack': None},
        'hold': {'paths': [], 'slack': None},
        'summary': {}
    }

    with open(report_file, 'r') as f:
        content = f.read()

    # 解析建立时间路径
    setup_paths = re.findall(
        r'Startpoint:\s+(\w+)\s+Endpoint:\s+(\w+).*?slack \(MET\):\s+([\d.]+)',
        content, re.DOTALL
    )

    for start, end, slack in setup_paths:
        timing_data['setup']['paths'].append({
            'start': start,
            'end': end,
            'slack': float(slack)
        })

    return timing_data


def parse_power_report(report_file):
    """解析功耗报告"""
    power_data = {
        'total_power': 0,
        'internal_power': 0,
        'switching_power': 0,
        'leakage_power': 0
    }

    with open(report_file, 'r') as f:
        content = f.read()

    # 解析总功耗
    total_match = re.search(r'Total\s+Power\s*:\s*([\d.]+)\s*(\w+)', content)
    if total_match:
        power_data['total_power'] = float(total_match.group(1))
        power_data['unit'] = total_match.group(2)

    return power_data


def generate_summary(timing_data, power_data, output_file):
    """生成摘要报告"""
    with open(output_file, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("硅迹开源 - 设计分析报告\n")
        f.write("=" * 60 + "\n\n")

        # 时序摘要
        f.write("一、时序分析\n")
        f.write("-" * 40 + "\n")
        if timing_data['setup']['paths']:
            worst_slack = min(p['slack'] for p in timing_data['setup']['paths'])
            f.write(f"建立时间余量 (WNS): {worst_slack:.3f} ns\n")
            f.write(f"建立时间路径数: {len(timing_data['setup']['paths'])}\n")
        else:
            f.write("未找到时序路径\n")

        f.write("\n二、功耗分析\n")
        f.write("-" * 40 + "\n")
        if power_data['total_power']:
            f.write(f"总功耗: {power_data['total_power']:.3f} {power_data.get('unit', 'W')}\n")
        else:
            f.write("未找到功耗数据\n")

        f.write("\n三、设计统计\n")
        f.write("-" * 40 + "\n")
        f.write("待添加...\n")


def main():
    if len(sys.argv) < 4:
        print("用法: python generate_report.py <sta_report> <power_report> <output_file>")
        sys.exit(1)

    sta_file = sys.argv[1]
    power_file = sys.argv[2]
    output_file = sys.argv[3]

    print(f"解析 STA 报告: {sta_file}")
    timing_data = parse_sta_report(sta_file)

    print(f"解析功耗报告: {power_file}")
    power_data = parse_power_report(power_file)

    print(f"生成摘要: {output_file}")
    generate_summary(timing_data, power_data, output_file)

    print("报告生成完成！")


if __name__ == '__main__':
    main()
