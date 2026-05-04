#!/bin/bash
# Yosys 综合运行脚本
# 硅迹开源 (SiliconTrace Open)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
RESULT_DIR="$ARTIFACTS_DIR/synthesis"
DESIGN_TOP="${DESIGN_TOP:-picorv32}"
RTL_FILE="${RTL_FILE:-$PROJECT_ROOT/rtl/$DESIGN_TOP/$DESIGN_TOP.v}"
RTL_FILES="${RTL_FILES:-$RTL_FILE}"
SDC_TEMPLATE="${SDC_TEMPLATE:-$SCRIPT_DIR/constraints/$DESIGN_TOP.sdc}"
SYNTH_PDK="${SYNTH_PDK:-sky130}"
SYNTH_SUFFIX="${SYNTH_SUFFIX:-}"
if [ -n "$SYNTH_SUFFIX" ]; then
    NETLIST_OUT="$RESULT_DIR/${DESIGN_TOP}_${SYNTH_SUFFIX}_netlist.v"
    JSON_OUT="$RESULT_DIR/${DESIGN_TOP}_${SYNTH_SUFFIX}_netlist.json"
else
    NETLIST_OUT="$RESULT_DIR/${DESIGN_TOP}_netlist.v"
    JSON_OUT="$RESULT_DIR/${DESIGN_TOP}_netlist.json"
fi

# 加载环境变量；没有本地配置时使用 volare 默认目录
if [ -f "$HOME/.eda_env" ]; then
    source "$HOME/.eda_env"
fi
PDK_ROOT="${PDK_ROOT:-$HOME/.volare}"
GF180_PDK_ROOT="${GF180_PDK_ROOT:-$HOME/.local/share/pdk/gf180mcuD}"

echo "=========================================="
echo " 硅迹开源 - Yosys 综合"
echo "=========================================="

# 创建结果目录
mkdir -p "$RESULT_DIR"

case "$SYNTH_PDK" in
    sky130)
        PDK_LIB="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
        PDK_NAME="SKY130"
        ;;
    gf180)
        PDK_LIB="${GF180_LIB:-$GF180_PDK_ROOT/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_1v80.lib}"
        PDK_NAME="GF180"
        ;;
    *)
        echo "错误: SYNTH_PDK=$SYNTH_PDK 无效，应为 sky130 或 gf180"
        exit 1
        ;;
esac

if [ ! -f "$PDK_LIB" ]; then
    echo "错误: $PDK_NAME 标准单元库未找到: $PDK_LIB"
    exit 1
fi
if [ ! -f "$SDC_TEMPLATE" ]; then
    echo "错误: SDC 文件不存在: $SDC_TEMPLATE"
    exit 1
fi

expand_rtl_files() {
    local file
    shopt -s nullglob
    for pattern in $RTL_FILES; do
        for file in $pattern; do
            printf '%s\n' "$file"
        done
    done
    shopt -u nullglob
}

RTL_FILE_LIST="$(expand_rtl_files)"
if [ -z "$RTL_FILE_LIST" ]; then
    echo "错误: RTL 文件不存在: $RTL_FILES"
    exit 1
fi

extract_clock_period() {
    local sdc_file="$1"
    local period=""

    if command -v tclsh >/dev/null 2>&1; then
        period="$(SDC_TEMPLATE_FOR_TCL="$sdc_file" tclsh <<'TCL' 2>/dev/null || true
set sdc_file $::env(SDC_TEMPLATE_FOR_TCL)

proc emit_period {period} {
    if {[regexp {^[0-9]+([.][0-9]+)?$} $period]} {
        puts $period
        exit 0
    }
}

proc get_ports {args} { return "" }
proc get_clocks {args} { return "" }
proc all_inputs {} { return "" }
proc all_outputs {} { return "" }
proc current_design {} { return "" }
proc create_clock {args} {
    set idx [lsearch -exact $args "-period"]
    if {$idx >= 0 && ($idx + 1) < [llength $args]} {
        emit_period [lindex $args [expr {$idx + 1}]]
    }
    return ""
}
proc unknown {cmd args} { return "" }

if {[catch {source $sdc_file}]} {
    exit 1
}
if {[info exists clk_period]} {
    emit_period $clk_period
}
exit 1
TCL
)"
        if [ -n "$period" ]; then
            printf '%s\n' "$period"
            return 0
        fi
    fi

    awk '
        {
            sub(/[[:space:]]*#.*/, "")
            if ($0 ~ /\\[[:space:]]*$/) {
                sub(/\\[[:space:]]*$/, "")
                line = line " " $0
                next
            }
            line = line " " $0
        }
        line != "" {
            if (line ~ /^[[:space:]]*set[[:space:]]+clk_period[[:space:]]+[0-9.]+/) {
                split(line, fields, /[[:space:]]+/)
                print fields[3]
                exit
            }
            if (line ~ /create_clock/) {
                split(line, fields, /[[:space:]]+/)
                for (i = 1; i <= length(fields); i++) {
                    if (fields[i] == "-period" && (i + 1) <= length(fields) && fields[i + 1] !~ /^\$/) {
                        print fields[i + 1]
                        exit
                    }
                }
            }
            line = ""
        }
    ' "$sdc_file"
}

# 从 SDC 提取时钟周期，并给综合留一点物理实现余量
CLK_PERIOD_NS="${CLK_PERIOD_NS:-$(extract_clock_period "$SDC_TEMPLATE" || true)}"

if [ -z "$CLK_PERIOD_NS" ]; then
    echo "警告: 无法从 SDC 提取时钟周期，使用默认 10.0ns"
    CLK_PERIOD_NS="10.0"
fi

ABC_DELAY_TARGET_PS="$(awk -v period_ns="$CLK_PERIOD_NS" '
    BEGIN {
        target_ps = period_ns * 1000.0 * 0.90
        if (target_ps < 1000.0) {
            target_ps = 1000.0
        }
        printf "%.0f\n", target_ps
    }
')"

echo "PDK: ${PDK_NAME}"
echo "标准单元库: ${PDK_LIB}"
echo "时钟周期: ${CLK_PERIOD_NS}ns"
echo "ABC 目标延时: ${ABC_DELAY_TARGET_PS}ps"
echo "设计顶层: ${DESIGN_TOP}"
echo "RTL 文件:"
printf '  %s\n' $RTL_FILE_LIST
echo "SDC 模板: ${SDC_TEMPLATE}"

# 从模板生成实际的综合脚本（替换 PDK 路径）
echo "生成综合脚本..."
RTL_READ_FILE="$SCRIPT_DIR/synth_rtl_files.ys"
printf 'read_verilog %s\n' $RTL_FILE_LIST > "$RTL_READ_FILE"
sed \
    -e "s|__PDK_LIB_PATH__|$PDK_LIB|g" \
    -e "/__READ_RTL_FILES__/r $RTL_READ_FILE" \
    -e "/__READ_RTL_FILES__/d" \
    -e "s|__DESIGN_TOP__|$DESIGN_TOP|g" \
    -e "s|__SYNTH_NETLIST_OUT__|$NETLIST_OUT|g" \
    -e "s|__SYNTH_JSON_OUT__|$JSON_OUT|g" \
    -e "s|__ABC_DELAY_TARGET_PS__|$ABC_DELAY_TARGET_PS|g" \
    "$SCRIPT_DIR/synth.ys" > "$SCRIPT_DIR/synth_actual.ys"

# 运行综合
echo "开始综合 ${DESIGN_TOP}..."
cd "$SCRIPT_DIR"
yosys -s synth_actual.ys -q

# 修复网表中 iEDA 无法解析的复杂拼接赋值
echo "修复网表语法..."
python3 "$PROJECT_ROOT/scripts/yosys2ieda/fix_netlist.py" \
    "$NETLIST_OUT" \
    "$NETLIST_OUT"

# 复制 SDC 约束到结果目录
if [ -n "$SYNTH_SUFFIX" ]; then
    cp "$SDC_TEMPLATE" "$RESULT_DIR/${DESIGN_TOP}_${SYNTH_SUFFIX}.sdc"
else
    cp "$SDC_TEMPLATE" "$RESULT_DIR/${DESIGN_TOP}.sdc"
fi

echo "综合完成！"
echo "结果文件："
ls -la "$RESULT_DIR"/
