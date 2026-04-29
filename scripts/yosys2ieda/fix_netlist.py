#!/usr/bin/env python3
"""
修复 Yosys 网表中 iEDA 无法解析的语法
硅迹开源 (SiliconTrace Open)

功能：将复杂的拼接赋值语句展开为逐位赋值
  assign { a[3], a[2:0] } = { b, c[1], c[0] };
  =>
  assign a[3] = b;
  assign a[2] = c[1];
  assign a[1] = c[0];
  assign a[0] = <padding>;
"""

import re
import sys


def expand_bit_range(token):
    """将 a[3:0] 展开为 [a[3], a[2], a[1], a[0]]，a[5] 保持不变"""
    m = re.match(r'(.+?)\[(\d+):(\d+)\]', token.strip())
    if m:
        name = m.group(1)
        hi = int(m.group(2))
        lo = int(m.group(3))
        if hi >= lo:
            return [f"{name}[{i}]" for i in range(hi, lo - 1, -1)]
        else:
            return [f"{name}[{i}]" for i in range(hi, lo + 1, 1)]
    return [token.strip()]


def split_concat_items(raw):
    """按逗号分割拼接项，但忽略括号内的逗号"""
    items = []
    depth = 0
    current = ""
    for ch in raw:
        if ch == '[':
            depth += 1
            current += ch
        elif ch == ']':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        items.append(current.strip())
    return items


def expand_concat_assign(line):
    """展开单条拼接赋值语句"""
    m = re.match(r'\s*assign\s+\{(.+\})\s*=\s*\{(.+\})\s*;', line)
    if not m:
        return [line]

    lhs_raw = m.group(1).rstrip('}').strip()
    rhs_raw = m.group(2).rstrip('}').strip()

    lhs_items = split_concat_items(lhs_raw)
    rhs_items = split_concat_items(rhs_raw)

    # 展开位范围
    lhs_bits = []
    for item in lhs_items:
        lhs_bits.extend(expand_bit_range(item))

    rhs_bits = []
    for item in rhs_items:
        rhs_bits.extend(expand_bit_range(item))

    if len(lhs_bits) != len(rhs_bits):
        # 位宽不匹配，保持原样
        return [line]

    result = []
    for l, r in zip(lhs_bits, rhs_bits):
        result.append(f"  assign {l} = {r};\n")
    return result


def fix_netlist(input_file, output_file):
    with open(input_file, 'r') as f:
        lines = f.readlines()

    output = []
    changed = 0
    for line in lines:
        if 'assign {' in line and '} = {' in line:
            expanded = expand_concat_assign(line)
            if len(expanded) > 1:
                changed += 1
                output.extend(expanded)
            else:
                output.append(line)
        else:
            output.append(line)

    with open(output_file, 'w') as f:
        f.writelines(output)

    print(f"修复完成: 展开了 {changed} 条拼接赋值 -> {output_file}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python fix_netlist.py <input.v> <output.v>")
        sys.exit(1)
    fix_netlist(sys.argv[1], sys.argv[2])
