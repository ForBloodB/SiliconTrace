#!/bin/bash
# Yosys 综合运行脚本
# 硅迹开源 (SiliconTrace Open)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
RESULT_DIR="$ARTIFACTS_DIR/synthesis"

# 加载环境变量
source ~/.eda_env

echo "=========================================="
echo " 硅迹开源 - Yosys 综合"
echo "=========================================="

# 创建结果目录
mkdir -p "$RESULT_DIR"

# 检查 PDK
PDK_LIB="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
if [ ! -f "$PDK_LIB" ]; then
    echo "错误: SKY130 标准单元库未找到: $PDK_LIB"
    exit 1
fi

# 从模板生成实际的综合脚本（替换 PDK 路径）
echo "生成综合脚本..."
sed \
    -e "s|__PDK_LIB_PATH__|$PDK_LIB|g" \
    -e "s|__SYNTH_OUT_DIR__|$RESULT_DIR|g" \
    "$SCRIPT_DIR/synth.ys" > "$SCRIPT_DIR/synth_actual.ys"

# 运行综合
echo "开始综合 PicoRV32..."
cd "$SCRIPT_DIR"
yosys -s synth_actual.ys -q

# 修复网表中 iEDA 无法解析的复杂拼接赋值
echo "修复网表语法..."
python3 "$PROJECT_ROOT/scripts/yosys2ieda/fix_netlist.py" \
    "$RESULT_DIR/picorv32_netlist.v" \
    "$RESULT_DIR/picorv32_netlist.v"

# 复制 SDC 约束到结果目录
cp "$SCRIPT_DIR/constraints/picorv32.sdc" "$RESULT_DIR/picorv32.sdc"

echo "综合完成！"
echo "结果文件："
ls -la "$RESULT_DIR"/
