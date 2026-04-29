#!/bin/bash
# iEDA 后端全流程脚本 - PicoRV32 on SKY130
# 硅迹开源 (SiliconTrace Open)
#
# 基于 iEDA sky130_gcd 参考设计改编
# 使用 HD（高密度）标准单元库

#=============================================
## 路径设置
#=============================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IEDA_ROOT="$HOME/iEDA"
IEDA_SCRIPT_DIR="$IEDA_ROOT/scripts/design/sky130_gcd"
FOUNDRY_DIR="$IEDA_ROOT/scripts/foundry/sky130"
IEDA_BIN="$IEDA_SCRIPT_DIR/iEDA"

# 结果目录
RESULT_DIR="$SCRIPT_DIR/result"
mkdir -p "$RESULT_DIR/report" "$RESULT_DIR/feature" "$RESULT_DIR/cts" "$RESULT_DIR/sta" "$RESULT_DIR/rt"

#=============================================
## 设计参数
#=============================================
export CONFIG_DIR="$SCRIPT_DIR/config"
export FOUNDRY_DIR="$FOUNDRY_DIR"
export RESULT_DIR="$RESULT_DIR"
export TCL_SCRIPT_DIR="$IEDA_SCRIPT_DIR/script"

export DESIGN_TOP="picorv32"
export CUSTOM_TCL_DIR="$SCRIPT_DIR/tcl"
export NETLIST_FILE="$PROJECT_ROOT/synthesis/results/picorv32_netlist.v"
export SDC_FILE="$PROJECT_ROOT/synthesis/constraints/picorv32.sdc"

# PicoRV32: 500um x 500um die, 10um margin
export DIE_AREA="0.0 0.0 500.0 500.0"
export CORE_AREA="10.0 10.0 490.0 490.0"

#=============================================
## 检查输入文件
#=============================================
echo "=========================================="
echo " 硅迹开源 - iEDA 后端流程"
echo "=========================================="

for f in "$NETLIST_FILE" "$SDC_FILE" "$IEDA_BIN"; do
    if [ ! -e "$f" ]; then
        echo "错误: 文件不存在: $f"
        exit 1
    fi
done

echo "网表文件: $NETLIST_FILE"
echo "SDC 文件: $SDC_FILE"
echo "结果目录: $RESULT_DIR"

# 复制网表到结果目录供 iEDA 使用
cp "$NETLIST_FILE" "$RESULT_DIR/picorv32_netlist.v"

#=============================================
## 步骤 1: 布局规划 (Floorplan)
#=============================================
echo ""
echo "[1/6] 运行布局规划 (iFP)..."
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iFP.tcl"
echo "布局规划完成 ✓"

#=============================================
## 步骤 2: 全局布局 (Placement)
#=============================================
echo ""
echo "[2/6] 运行全局布局 (iPL)..."
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iPL.tcl"
echo "全局布局完成 ✓"

#=============================================
## 步骤 3: 时钟树综合 (CTS)
#=============================================
echo ""
echo "[3/6] 运行时钟树综合 (iCTS)..."
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iCTS.tcl"
echo "时钟树综合完成 ✓"

#=============================================
## 步骤 4: 布线 (Routing)
#=============================================
echo ""
echo "[4/6] 运行布线 (iRT)..."
if "$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iRT.tcl"; then
    echo "布线完成 ✓"
    RT_SUCCESS=true
else
    echo "布线有 DRC 违例，使用 CTS 结果继续..."
    RT_SUCCESS=false
fi

#=============================================
## 步骤 5: 静态时序分析 (STA)
#=============================================
echo ""
echo "[5/6] 运行静态时序分析 (iSTA)..."
# 根据布线结果选择输入 DEF
if [ "$RT_SUCCESS" = true ] && [ -f "$RESULT_DIR/iRT_result.def" ]; then
    export INPUT_DEF="$RESULT_DIR/iRT_result.def"
else
    export INPUT_DEF="$RESULT_DIR/iCTS_result.def"
fi
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iSTA.tcl"
echo "静态时序分析完成 ✓"

#=============================================
## 步骤 6: 生成 GDSII 文本
#=============================================
echo ""
echo "[6/6] 生成 GDSII 文本..."
if [ "$RT_SUCCESS" = true ] && [ -f "$RESULT_DIR/iRT_result.def" ]; then
    "$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_def_to_gds.tcl"
    echo "GDSII 文本生成完成 ✓"
else
    echo "跳过 GDSII 生成（布线未完成）"
fi

echo ""
echo "=========================================="
echo " 全流程完成！"
echo "=========================================="
echo "结果文件："
ls -la "$RESULT_DIR"/*.def 2>/dev/null || echo "  (无 DEF 文件)"
ls -la "$RESULT_DIR"/*.v 2>/dev/null || echo "  (无 Verilog 文件)"
ls -la "$RESULT_DIR"/sta/ 2>/dev/null || echo "  (无 STA 报告)"
