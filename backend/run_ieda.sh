#!/bin/bash
# iEDA 后端全流程脚本 - PicoRV32 on SKY130
# 硅迹开源 (SiliconTrace Open)
#
# 基于 iEDA sky130_gcd 参考设计改编
# 使用 HD（高密度）标准单元库

set -e

#=============================================
## 路径设置
#=============================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
IEDA_ROOT="$HOME/iEDA"
IEDA_SCRIPT_DIR="$IEDA_ROOT/scripts/design/sky130_gcd"
FOUNDRY_DIR="$IEDA_ROOT/scripts/foundry/sky130"
IEDA_BIN="$IEDA_SCRIPT_DIR/iEDA"

#=============================================
## 设计参数
#=============================================
export DESIGN_TOP="${DESIGN_TOP:-picorv32}"
if [ -n "${RESULT_DIR:-}" ]; then
    :
elif [ "$DESIGN_TOP" = "picorv32" ]; then
    RESULT_DIR="$ARTIFACTS_DIR/backend"
else
    RESULT_DIR="$ARTIFACTS_DIR/backend/$DESIGN_TOP"
fi
mkdir -p "$RESULT_DIR/report" "$RESULT_DIR/feature" "$RESULT_DIR/cts" "$RESULT_DIR/sta" "$RESULT_DIR/rt"

export CONFIG_DIR="$SCRIPT_DIR/config"
export FOUNDRY_DIR="$FOUNDRY_DIR"
export RESULT_DIR="$RESULT_DIR"
export TCL_SCRIPT_DIR="$IEDA_SCRIPT_DIR/script"

export CUSTOM_TCL_DIR="$SCRIPT_DIR/tcl"
export NETLIST_FILE="${NETLIST_FILE:-$ARTIFACTS_DIR/synthesis/${DESIGN_TOP}_netlist.v}"
export SDC_FILE="${SDC_FILE:-$ARTIFACTS_DIR/synthesis/${DESIGN_TOP}.sdc}"

DESIGN_CONFIG="${DESIGN_CONFIG:-$PROJECT_ROOT/rtl/$DESIGN_TOP/backend.env}"
if [ -f "$DESIGN_CONFIG" ]; then
    # Per-design defaults are ordinary shell assignments. Existing environment
    # variables still take precedence when the config uses ${VAR:=default}.
    source "$DESIGN_CONFIG"
fi

TARGET_CORE_UTILIZATION="${TARGET_CORE_UTILIZATION:-0.40}"
CORE_MARGIN_UM="${CORE_MARGIN_UM:-20}"
MIN_CORE_SIDE_UM="${MIN_CORE_SIDE_UM:-380}"
MAX_CORE_SIDE_UM="${MAX_CORE_SIDE_UM:-900}"
TAPCELL_DISTANCE="${TAPCELL_DISTANCE:-14}"
PL_TARGET_DENSITY="${PL_TARGET_DENSITY:-}"
CTS_ROUTING_LAYERS="${CTS_ROUTING_LAYERS:-}"
CTS_MAX_FANOUT="${CTS_MAX_FANOUT:-}"
CTS_CLUSTER_SIZE="${CTS_CLUSTER_SIZE:-}"
CTS_MAX_LENGTH="${CTS_MAX_LENGTH:-}"
CTS_LEVEL_MAX_FANOUT="${CTS_LEVEL_MAX_FANOUT:-}"
BOTTOM_ROUTING_LAYER="${BOTTOM_ROUTING_LAYER:-met1}"
TOP_ROUTING_LAYER="${TOP_ROUTING_LAYER:-met5}"
SKIP_SETUP_WHEN_HOLD_MEETS_TIMING="${SKIP_SETUP_WHEN_HOLD_MEETS_TIMING:-1}"
EXPORT_KICAD="${EXPORT_KICAD:-1}"
RT_FULL_PA_ITER="${RT_FULL_PA_ITER:-0}"
RT_FULL_DR_ITER="${RT_FULL_DR_ITER:-0}"
RT_DR_REPEAT="${RT_DR_REPEAT:-1}"
RT_DR_STOP_AFTER_BOXES="${RT_DR_STOP_AFTER_BOXES:-}"
ROUTE_INPUT_STAGE="${ROUTE_INPUT_STAGE:-timing}"
CLEAN_BACKEND_RESULTS="${CLEAN_BACKEND_RESULTS:-1}"
STOP_AFTER_STEP="${STOP_AFTER_STEP:-}"
PDN_MET1_GRID_WIDTH="${PDN_MET1_GRID_WIDTH:-0.48}"
PDN_MET4_STRIPE_WIDTH="${PDN_MET4_STRIPE_WIDTH:-1.60}"
PDN_MET4_STRIPE_PITCH="${PDN_MET4_STRIPE_PITCH:-27.14}"
PDN_MET4_STRIPE_OFFSET="${PDN_MET4_STRIPE_OFFSET:-13.57}"
PDN_MET5_STRIPE_WIDTH="${PDN_MET5_STRIPE_WIDTH:-1.60}"
PDN_MET5_STRIPE_PITCH="${PDN_MET5_STRIPE_PITCH:-27.20}"
PDN_MET5_STRIPE_OFFSET="${PDN_MET5_STRIPE_OFFSET:-13.60}"
PDN_ENABLE="${PDN_ENABLE:-1}"
PDN_ENABLE_GRID="${PDN_ENABLE_GRID:-1}"
PDN_ENABLE_STRIPES="${PDN_ENABLE_STRIPES:-1}"

export PDN_ENABLE
export PDN_ENABLE_GRID
export PDN_MET1_GRID_WIDTH
export PDN_MET4_STRIPE_WIDTH
export PDN_MET4_STRIPE_PITCH
export PDN_MET4_STRIPE_OFFSET
export PDN_MET5_STRIPE_WIDTH
export PDN_MET5_STRIPE_PITCH
export PDN_MET5_STRIPE_OFFSET
export PDN_ENABLE_STRIPES
export TAPCELL_DISTANCE

estimate_cell_area() {
    local pdk_lib="$FOUNDRY_DIR/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
    yosys -p "read_verilog $NETLIST_FILE; hierarchy -top $DESIGN_TOP; stat -liberty $pdk_lib" 2>/dev/null \
        | awk '/Chip area for module/ {print $NF; exit}'
}

configure_floorplan() {
    local cell_area core_side die_side core_lo core_hi
    cell_area="$(estimate_cell_area)"
    if [ -z "$cell_area" ]; then
        echo "警告: 无法估算单元面积，回退到保守 floorplan"
        export DIE_AREA="0.0 0.0 500.0 500.0"
        export CORE_AREA="20.0 20.0 480.0 480.0"
        return
    fi

    core_side="$(awk -v area="$cell_area" -v util="$TARGET_CORE_UTILIZATION" \
        -v min_side="$MIN_CORE_SIDE_UM" -v max_side="$MAX_CORE_SIDE_UM" '
        BEGIN {
            side = sqrt(area / util)
            if (side < min_side) side = min_side
            if (side > max_side) side = max_side
            side = int((side + 4.999) / 5.0) * 5
            printf "%.1f\n", side
        }')"

    die_side="$(awk -v core_side="$core_side" -v margin="$CORE_MARGIN_UM" '
        BEGIN { printf "%.1f\n", core_side + 2.0 * margin }')"

    core_lo="$(awk -v margin="$CORE_MARGIN_UM" '
        BEGIN { printf "%.1f\n", margin }')"

    core_hi="$(awk -v core_side="$core_side" -v margin="$CORE_MARGIN_UM" '
        BEGIN { printf "%.1f\n", core_side + margin }')"

    export DIE_AREA="0.0 0.0 ${die_side} ${die_side}"
    export CORE_AREA="${core_lo} ${core_lo} ${core_hi} ${core_hi}"

    echo "估算标准单元面积: ${cell_area} um^2"
    echo "目标核心利用率: ${TARGET_CORE_UTILIZATION}"
    echo "自动 floorplan: DIE=${DIE_AREA}, CORE=${CORE_AREA}"
}

prepare_placement_config() {
    local src="$CONFIG_DIR/pl_default_config.json"

    # Allow pre-set PL_CONFIG to override (e.g., for custom Nesterov params)
    if [ -n "${PL_CONFIG:-}" ] && [ -f "$PL_CONFIG" ]; then
        echo "Using custom PL config: $PL_CONFIG"
        return
    fi

    if [ -z "$PL_TARGET_DENSITY" ]; then
        export PL_CONFIG="$src"
        return
    fi

    local dst="$RESULT_DIR/pl_config.json"
    python3 - "$src" "$dst" "$PL_TARGET_DENSITY" <<'PY'
import json
import sys

src, dst, density_raw = sys.argv[1:4]
try:
    density = float(density_raw)
except ValueError as exc:
    raise SystemExit(f"invalid PL_TARGET_DENSITY={density_raw!r}") from exc
if not 0.05 <= density <= 0.95:
    raise SystemExit(f"PL_TARGET_DENSITY={density_raw!r} outside supported range 0.05..0.95")

with open(src, "r", encoding="utf-8") as file:
    config = json.load(file)
config["PL"]["GP"]["Density"]["target_density"] = density
with open(dst, "w", encoding="utf-8") as file:
    json.dump(config, file, indent=4)
    file.write("\n")
PY
    export PL_CONFIG="$dst"
    echo "Placement target_density: ${PL_TARGET_DENSITY} ($PL_CONFIG)"
}

prepare_cts_config() {
    local src="$CONFIG_DIR/cts_default_config.json"

    if [ -z "$CTS_ROUTING_LAYERS$CTS_MAX_FANOUT$CTS_CLUSTER_SIZE$CTS_MAX_LENGTH$CTS_LEVEL_MAX_FANOUT" ]; then
        export CTS_CONFIG="$src"
        return
    fi

    local dst="$RESULT_DIR/cts_config.json"
    python3 - "$src" "$dst" "$CTS_ROUTING_LAYERS" "$CTS_MAX_FANOUT" \
        "$CTS_CLUSTER_SIZE" "$CTS_MAX_LENGTH" "$CTS_LEVEL_MAX_FANOUT" <<'PY'
import json
import sys

src, dst, routing_layers, max_fanout, cluster_size, max_length, level_max_fanout = sys.argv[1:8]

with open(src, "r", encoding="utf-8") as file:
    config = json.load(file)

if routing_layers:
    try:
        layers = [int(item.strip()) for item in routing_layers.split(",") if item.strip()]
    except ValueError as exc:
        raise SystemExit(f"invalid CTS_ROUTING_LAYERS={routing_layers!r}") from exc
    if not layers:
        raise SystemExit("CTS_ROUTING_LAYERS must contain at least one layer")
    config["routing_layer"] = layers

if max_fanout:
    try:
        fanout = int(max_fanout)
    except ValueError as exc:
        raise SystemExit(f"invalid CTS_MAX_FANOUT={max_fanout!r}") from exc
    config["max_fanout"] = str(fanout)

if cluster_size:
    try:
        cluster = int(cluster_size)
    except ValueError as exc:
        raise SystemExit(f"invalid CTS_CLUSTER_SIZE={cluster_size!r}") from exc
    config["cluster_size"] = cluster

if max_length:
    try:
        length = float(max_length)
    except ValueError as exc:
        raise SystemExit(f"invalid CTS_MAX_LENGTH={max_length!r}") from exc
    config["max_length"] = str(int(length) if length.is_integer() else length)

if level_max_fanout:
    try:
        fanouts = [int(item.strip()) for item in level_max_fanout.split(",") if item.strip()]
    except ValueError as exc:
        raise SystemExit(f"invalid CTS_LEVEL_MAX_FANOUT={level_max_fanout!r}") from exc
    if not fanouts:
        raise SystemExit("CTS_LEVEL_MAX_FANOUT must contain at least one fanout")
    config["level_max_fanout"] = fanouts

with open(dst, "w", encoding="utf-8") as file:
    json.dump(config, file, indent=4)
    file.write("\n")
PY
    export CTS_CONFIG="$dst"
    echo "CTS config: $CTS_CONFIG"
}

clean_backend_results() {
    [ "$CLEAN_BACKEND_RESULTS" = "1" ] || return

    rm -f "$RESULT_DIR"/iFP_result.def \
          "$RESULT_DIR"/iPL_result.def "$RESULT_DIR"/iPL_result.v \
          "$RESULT_DIR"/iCTS_result.def "$RESULT_DIR"/iCTS_result.v \
          "$RESULT_DIR"/iTO_drv_result.def "$RESULT_DIR"/iTO_drv_result.v \
          "$RESULT_DIR"/iTO_hold_result.def "$RESULT_DIR"/iTO_hold_result.v \
          "$RESULT_DIR"/iTO_setup_result.def "$RESULT_DIR"/iTO_setup_result.v \
          "$RESULT_DIR"/iRT_result.def "$RESULT_DIR"/iRT_result.v \
          "$RESULT_DIR"/iRT_partial.def "$RESULT_DIR"/iRT_partial.v \
          "$RESULT_DIR"/final_design.def "$RESULT_DIR"/final_design.v \
          "$RESULT_DIR"/"${DESIGN_TOP}.gds2" \
          "$RESULT_DIR"/"${DESIGN_TOP}_netlist.v" \
          "$RESULT_DIR"/pl_config.json \
          "$RESULT_DIR"/cts_config.json
    rm -rf "$RESULT_DIR"/rt/*
}

maybe_stop_after() {
    local step="$1"
    [ "$STOP_AFTER_STEP" = "$step" ] || return 0

    echo ""
    echo "STOP_AFTER_STEP=$step，按请求停止在该阶段之后。"
    exit 0
}

run_sta_check() {
    local input_def="$1"
    export INPUT_DEF="$input_def"
    "$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iSTA.tcl" >/tmp/ieda_sta_check.log 2>&1
}

timing_tns_clean() {
    local rpt="$RESULT_DIR/sta/${DESIGN_TOP}.rpt"
    if [ ! -f "$rpt" ] && [ "$DESIGN_TOP" = "picorv32" ]; then
        rpt="$RESULT_DIR/sta/picorv32.rpt"
    fi
    if [ ! -f "$rpt" ]; then
        return 1
    fi

    awk -F'|' '
        function trim(s) {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
            return s
        }
        NF >= 4 {
            type = trim($3)
            tns = trim($4)
            if ((type == "max" || type == "min") && tns ~ /^-?[0-9.]+$/) {
                if (type == "max" && tns != "0.000") bad=1
                if (type == "min" && tns != "0.000") bad=1
                seen[type]=1
            }
        }
        END {
            if (!seen["max"] || !seen["min"] || bad) exit 1
        }
    ' "$rpt"
}

select_routing_input_def() {
    case "$ROUTE_INPUT_STAGE" in
        cts)
            printf '%s\n' "$RESULT_DIR/iCTS_result.def"
            ;;
        timing)
            printf '%s\n' "$TIMING_OPT_DEF"
            ;;
        hold)
            printf '%s\n' "$RESULT_DIR/iTO_hold_result.def"
            ;;
        setup)
            printf '%s\n' "$RESULT_DIR/iTO_setup_result.def"
            ;;
        *)
            echo "错误: ROUTE_INPUT_STAGE=$ROUTE_INPUT_STAGE 无效，应为 cts/timing/hold/setup" >&2
            exit 1
            ;;
    esac
}

parse_route_drc_violations() {
    local log_file="$1"
    [ -f "$log_file" ] || return 1

    awk '
        /\|[[:space:]]*within_net[[:space:]]*\|/ {
            section=1
            next
        }
        /\|[[:space:]]*among_net[[:space:]]*\|/ {
            section=1
            next
        }
        section && /\|[[:space:]]*Total[[:space:]]*\|/ {
            last=""
            split($0, fields, "|")
            for (i in fields) {
                value=fields[i]
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
                if (value ~ /^[0-9]+$/) {
                    last=value
                }
            }
            if (last != "") {
                total += last
                section=0
            }
        }
        END {
            print total + 0
        }
    ' "$log_file"
}

write_route_status() {
    local status="$1"
    local detail="$2"
    local drc_count="${3:-}"

    {
        printf 'status=%s\n' "$status"
        printf 'detail=%s\n' "$detail"
        if [ -n "$drc_count" ]; then
            printf 'route_drc_violations=%s\n' "$drc_count"
        fi
    } > "$ROUTE_STATUS_FILE"
}

refresh_route_status() {
    local drc_count=""
    if [ -f "$RESULT_DIR/rt/rt.log" ]; then
        drc_count="$(parse_route_drc_violations "$RESULT_DIR/rt/rt.log" || true)"
    fi

    if [ -n "$drc_count" ] && [ "$drc_count" -gt 0 ]; then
        if [ -f "$RESULT_DIR/iRT_result.def" ] && [ ! -f "$RESULT_DIR/iRT_partial.def" ]; then
            cp "$RESULT_DIR/iRT_result.def" "$RESULT_DIR/iRT_partial.def"
        fi
        if [ -f "$RESULT_DIR/iRT_result.v" ] && [ ! -f "$RESULT_DIR/iRT_partial.v" ]; then
            cp "$RESULT_DIR/iRT_result.v" "$RESULT_DIR/iRT_partial.v"
        fi
        write_route_status "failed" "Routing completed with ${drc_count} DRC violations" "$drc_count"
        return
    fi

    if [ -f "$ROUTE_STATUS_FILE" ] && grep -q '^status=success$' "$ROUTE_STATUS_FILE" && [ ! -f "$RESULT_DIR/iRT_result.def" ]; then
        write_route_status "failed" "Routing reported success but did not generate iRT_result.def" "$drc_count"
    elif [ ! -f "$ROUTE_STATUS_FILE" ] && [ ! -f "$RESULT_DIR/iRT_result.def" ]; then
        write_route_status "failed" "Routing did not complete or did not generate iRT_result.def" "$drc_count"
    fi
}

forward_rt_knob() {
    local short_name="$1"
    local full_name="$2"
    if [ -n "${!short_name:-}" ] && [ -z "${!full_name:-}" ]; then
        export "$full_name=${!short_name}"
    fi
}

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
echo "设计顶层: $DESIGN_TOP"
echo "结果目录: $RESULT_DIR"

clean_backend_results
configure_floorplan
prepare_placement_config
prepare_cts_config

# 复制网表到结果目录供 iEDA 使用
cp "$NETLIST_FILE" "$RESULT_DIR/${DESIGN_TOP}_netlist.v"

#=============================================
## 步骤 1: 布局规划 (Floorplan)
#=============================================
echo ""
echo "[1/10] 运行布局规划 (iFP)..."
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iFP.tcl"
echo "布局规划完成 ✓"
maybe_stop_after "floorplan"

#=============================================
## 步骤 2: 全局布局 (Placement)
#=============================================
echo ""
echo "[2/10] 运行全局布局 (iPL)..."
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iPL.tcl"
echo "全局布局完成 ✓"
maybe_stop_after "placement"

#=============================================
## 步骤 3: 时钟树综合 (CTS)
#=============================================
echo ""
echo "[3/10] 运行时钟树综合 (iCTS)..."
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iCTS.tcl"
echo "时钟树综合完成 ✓"
maybe_stop_after "cts"

#=============================================
## 步骤 4: 驱动/扇出修复 (iTO DRV)
#=============================================
echo ""
echo "[4/10] 运行驱动/扇出修复 (iTO DRV)..."
export INPUT_DEF="$RESULT_DIR/iCTS_result.def"
export OUTPUT_DEF="$RESULT_DIR/iTO_drv_result.def"
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iTO_drv.tcl"
echo "驱动/扇出修复完成 ✓"
maybe_stop_after "ito_drv"

#=============================================
## 步骤 5: Hold 优化
#=============================================
echo ""
echo "[5/10] 运行 Hold 优化 (iTO Hold)..."
export INPUT_DEF="$RESULT_DIR/iTO_drv_result.def"
export OUTPUT_DEF="$RESULT_DIR/iTO_hold_result.def"
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iTO_hold.tcl"
echo "Hold 优化完成 ✓"
maybe_stop_after "ito_hold"

#=============================================
## 步骤 6: Setup 优化
#=============================================
echo ""
TIMING_OPT_DEF="$RESULT_DIR/iTO_hold_result.def"
if [ "$SKIP_SETUP_WHEN_HOLD_MEETS_TIMING" = "1" ]; then
    echo "[6/10] 检查 Hold 优化后时序..."
    run_sta_check "$RESULT_DIR/iTO_hold_result.def"
    if timing_tns_clean; then
        echo "Hold 结果的 setup/hold TNS 已清零，跳过 Setup 优化 ✓"
    else
        echo "[6/10] 运行 Setup 优化 (iTO Setup)..."
        export INPUT_DEF="$RESULT_DIR/iTO_hold_result.def"
        export OUTPUT_DEF="$RESULT_DIR/iTO_setup_result.def"
        "$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iTO_setup.tcl"
        echo "Setup 优化完成 ✓"
        TIMING_OPT_DEF="$RESULT_DIR/iTO_setup_result.def"
    fi
else
    echo "[6/10] 运行 Setup 优化 (iTO Setup)..."
    export INPUT_DEF="$RESULT_DIR/iTO_hold_result.def"
    export OUTPUT_DEF="$RESULT_DIR/iTO_setup_result.def"
    "$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iTO_setup.tcl"
    echo "Setup 优化完成 ✓"
    TIMING_OPT_DEF="$RESULT_DIR/iTO_setup_result.def"
fi
maybe_stop_after "ito_setup"

#=============================================
## 步骤 7: 布线 (Routing)
#=============================================
echo ""
echo "[7/10] 运行布线 (iRT)..."
ROUTE_STATUS_FILE="$RESULT_DIR/rt/route_status.txt"
ROUTING_INPUT_DEF="$(select_routing_input_def)"
if [ ! -f "$ROUTING_INPUT_DEF" ]; then
    echo "错误: routing 输入 DEF 不存在: $ROUTING_INPUT_DEF" >&2
    exit 1
fi
export INPUT_DEF="$ROUTING_INPUT_DEF"
export OUTPUT_DEF="$RESULT_DIR/iRT_result.def"
export BOTTOM_ROUTING_LAYER
export TOP_ROUTING_LAYER
echo "布线输入阶段: ${ROUTE_INPUT_STAGE} ($INPUT_DEF)"
echo "布线层范围: ${BOTTOM_ROUTING_LAYER}-${TOP_ROUTING_LAYER}"
export SILICONTRACE_RT_FULL_PA_ITER="$RT_FULL_PA_ITER"
export SILICONTRACE_RT_FULL_DR_ITER="$RT_FULL_DR_ITER"
export SILICONTRACE_RT_DR_REPEAT="$RT_DR_REPEAT"
export SILICONTRACE_RT_DR_STOP_AFTER_BOXES="$RT_DR_STOP_AFTER_BOXES"
forward_rt_knob RT_PA_MAX_CANDIDATE_POINT_NUM SILICONTRACE_RT_PA_MAX_CANDIDATE_POINT_NUM
forward_rt_knob RT_PA_FIXED_RECT_SCALE SILICONTRACE_RT_PA_FIXED_RECT_SCALE
forward_rt_knob RT_PA_ROUTED_RECT_SCALE SILICONTRACE_RT_PA_ROUTED_RECT_SCALE
forward_rt_knob RT_PA_VIOLATION_SCALE SILICONTRACE_RT_PA_VIOLATION_SCALE
forward_rt_knob RT_PA_SIZE SILICONTRACE_RT_PA_SIZE
forward_rt_knob RT_PA_SCHEDULE_INTERVAL SILICONTRACE_RT_PA_SCHEDULE_INTERVAL
forward_rt_knob RT_PA_MAX_ROUTED_TIMES SILICONTRACE_RT_PA_MAX_ROUTED_TIMES
forward_rt_knob RT_PA_MAX_CANDIDATE_PATCH_NUM SILICONTRACE_RT_PA_MAX_CANDIDATE_PATCH_NUM
forward_rt_knob RT_TA_FIXED_RECT_SCALE SILICONTRACE_RT_TA_FIXED_RECT_SCALE
forward_rt_knob RT_TA_ROUTED_RECT_SCALE SILICONTRACE_RT_TA_ROUTED_RECT_SCALE
forward_rt_knob RT_TA_VIOLATION_SCALE SILICONTRACE_RT_TA_VIOLATION_SCALE
forward_rt_knob RT_TA_SCHEDULE_INTERVAL SILICONTRACE_RT_TA_SCHEDULE_INTERVAL
forward_rt_knob RT_TA_MAX_ROUTED_TIMES SILICONTRACE_RT_TA_MAX_ROUTED_TIMES
forward_rt_knob RT_DR_FIXED_RECT_SCALE SILICONTRACE_RT_DR_FIXED_RECT_SCALE
forward_rt_knob RT_DR_ROUTED_RECT_SCALE SILICONTRACE_RT_DR_ROUTED_RECT_SCALE
forward_rt_knob RT_DR_VIOLATION_SCALE SILICONTRACE_RT_DR_VIOLATION_SCALE
forward_rt_knob RT_DR_SIZE SILICONTRACE_RT_DR_SIZE
forward_rt_knob RT_DR_SCHEDULE_INTERVAL SILICONTRACE_RT_DR_SCHEDULE_INTERVAL
forward_rt_knob RT_DR_MAX_ROUTED_TIMES SILICONTRACE_RT_DR_MAX_ROUTED_TIMES
forward_rt_knob RT_DR_MAX_CANDIDATE_PATCH_NUM SILICONTRACE_RT_DR_MAX_CANDIDATE_PATCH_NUM
forward_rt_knob RT_BLOCKAGES SILICONTRACE_RT_BLOCKAGES
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iRT.tcl" || true
unset OUTPUT_DEF
unset SILICONTRACE_RT_FULL_PA_ITER
unset SILICONTRACE_RT_FULL_DR_ITER
unset SILICONTRACE_RT_DR_REPEAT
unset SILICONTRACE_RT_DR_STOP_AFTER_BOXES
refresh_route_status
if [ -f "$RESULT_DIR/iRT_result.def" ]; then
    if [ -f "$ROUTE_STATUS_FILE" ] && grep -q '^status=success$' "$ROUTE_STATUS_FILE"; then
        echo "布线完成 ✓ (DRC=0)"
        RT_SUCCESS=true
    else
        DRC_COUNT="$(grep '^route_drc_violations=' "$ROUTE_STATUS_FILE" 2>/dev/null | cut -d= -f2 || echo '?')"
        echo "布线完成，但有 DRC violations: $DRC_COUNT"
        echo "routed DEF 已保存到 $RESULT_DIR/iRT_result.def，继续 STA/GDS（仅用于调试/展示，不代表 clean closure）..."
        RT_SUCCESS=false
    fi
else
    echo "布线失败，未生成 routed DEF"
    echo "继续使用优化后的布局结果进行 STA/GDS 导出..."
    RT_SUCCESS=false
fi

#=============================================
## 步骤 8: 静态时序分析 (STA)
#=============================================
echo ""
echo "[8/10] 运行静态时序分析 (iSTA)..."
# 根据布线结果选择输入 DEF（即使 DRC>0，routed DEF 仍可用于 STA）
if [ -f "$RESULT_DIR/iRT_result.def" ]; then
    export INPUT_DEF="$RESULT_DIR/iRT_result.def"
else
    export INPUT_DEF="$TIMING_OPT_DEF"
fi
"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iSTA.tcl"
echo "静态时序分析完成 ✓"

#=============================================
## 步骤 9: 生成 GDSII 文本
#=============================================
echo ""
echo "[9/10] 生成 GDSII 文本..."
if [ -f "$RESULT_DIR/iRT_result.def" ]; then
    export INPUT_DEF="$RESULT_DIR/iRT_result.def"
else
    export INPUT_DEF="$TIMING_OPT_DEF"
fi
if [ -f "$SCRIPT_DIR/tcl/run_def_to_gds.tcl" ]; then
    "$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_def_to_gds.tcl" && echo "GDSII 文本生成完成 ✓" || echo "GDSII 生成失败"
else
    echo "GDSII 转换脚本不存在，跳过"
fi

#=============================================
## 步骤 10: 导出 KiCad 工程
#=============================================
echo ""
echo "[10/10] 导出 KiCad 工程..."
if [ "$EXPORT_KICAD" = "1" ] && [ "$DESIGN_TOP" = "picorv32" ]; then
    python3 "$SCRIPT_DIR/export_kicad.py"
    echo "KiCad 工程导出完成 ✓"
else
    echo "当前设计为 $DESIGN_TOP，跳过 PicoRV32 KiCad 测试载板导出"
fi

echo ""
echo "=========================================="
if [ "$RT_SUCCESS" = true ]; then
    echo " 全流程完成！"
else
    echo " 全流程完成，但 routing 未通过 DRC！"
fi
echo "=========================================="
echo "结果文件："
ls -la "$RESULT_DIR"/*.def 2>/dev/null || echo "  (无 DEF 文件)"
ls -la "$RESULT_DIR"/*.v 2>/dev/null || echo "  (无 Verilog 文件)"
ls -la "$RESULT_DIR"/sta/ 2>/dev/null || echo "  (无 STA 报告)"
if [ "$DESIGN_TOP" = "picorv32" ]; then
    ls -la "$ARTIFACTS_DIR"/kicad/picorv32_test_board/ 2>/dev/null || echo "  (无 KiCad 工程)"
fi

if [ "$RT_SUCCESS" != true ]; then
    exit 1
fi
