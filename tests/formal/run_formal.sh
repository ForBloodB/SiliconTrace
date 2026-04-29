#!/bin/bash
# 形式验证运行脚本
# 硅迹开源 (SiliconTrace Open)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo " 硅迹开源 - 形式验证"
echo "=========================================="

# 检查 SymbiYosys
if ! command -v sby &> /dev/null; then
    echo "错误: SymbiYosys 未安装"
    echo "安装方法: pip install symbiyosys"
    exit 1
fi

# 运行 BMC (有界模型检验)
echo ""
echo "运行 BMC 验证..."
cd "$SCRIPT_DIR"
sby -f picorv32.sby bmc

echo ""
echo "=========================================="
echo " 形式验证完成"
echo "=========================================="
