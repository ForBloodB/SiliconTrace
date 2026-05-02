#!/bin/bash
# Route-only iRT probe runner for PicoRV32 convergence experiments.

set -euo pipefail

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat <<'EOF'
Usage:
  PROBE_NAME=dr_routed4_stop25 RT_DR_ROUTED_RECT_SCALE=4 backend/run_irt_probe.sh

Environment:
  DESIGN_TOP                 Design name, defaults to picorv32.
  PROBE_NAME                 Probe suffix under artifacts/backend_probe_${PROBE_NAME}.
  RESULT_DIR                 Override probe result directory.
  SOURCE_RESULT_DIR          Existing backend result directory to read INPUT_DEF from.
  INPUT_DEF                  DEF to route, defaults to SOURCE_RESULT_DIR/iTO_hold_result.def.
  RT_DR_STOP_AFTER_BOXES     Detailed-router early stop, defaults to 25.
  RT_BLOCKAGES               Semicolon-separated layer:llx,lly,urx,ury[:exceptpgnet] specs.
  RT_* / SILICONTRACE_RT_*   Routing experiment knobs forwarded to iRT.
  STRICT_SUCCESS=1           Return non-zero unless route_status.txt says success.
EOF
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"
IEDA_ROOT="$HOME/iEDA"
IEDA_SCRIPT_DIR="$IEDA_ROOT/scripts/design/sky130_gcd"
FOUNDRY_DIR_DEFAULT="$IEDA_ROOT/scripts/foundry/sky130"
IEDA_BIN="$IEDA_SCRIPT_DIR/iEDA"

export DESIGN_TOP="${DESIGN_TOP:-picorv32}"

DESIGN_CONFIG="${DESIGN_CONFIG:-$PROJECT_ROOT/rtl/$DESIGN_TOP/backend.env}"
if [ -f "$DESIGN_CONFIG" ]; then
    source "$DESIGN_CONFIG"
fi

if [ -z "${SOURCE_RESULT_DIR:-}" ]; then
    if [ "$DESIGN_TOP" = "picorv32" ]; then
        SOURCE_RESULT_DIR="$ARTIFACTS_DIR/backend"
    else
        SOURCE_RESULT_DIR="$ARTIFACTS_DIR/backend/$DESIGN_TOP"
    fi
fi

PROBE_NAME="${PROBE_NAME:-${DESIGN_TOP}_$(date +%Y%m%d_%H%M%S)}"
RESULT_DIR="${RESULT_DIR:-$ARTIFACTS_DIR/backend_probe_$PROBE_NAME}"
INPUT_DEF="${INPUT_DEF:-$SOURCE_RESULT_DIR/iTO_hold_result.def}"

export CONFIG_DIR="${CONFIG_DIR:-$SCRIPT_DIR/config}"
export FOUNDRY_DIR="${FOUNDRY_DIR:-$FOUNDRY_DIR_DEFAULT}"
export RESULT_DIR
export CUSTOM_TCL_DIR="${CUSTOM_TCL_DIR:-$SCRIPT_DIR/tcl}"
export TCL_SCRIPT_DIR="${TCL_SCRIPT_DIR:-$IEDA_SCRIPT_DIR/script}"
export NETLIST_FILE="${NETLIST_FILE:-$ARTIFACTS_DIR/synthesis/${DESIGN_TOP}_netlist.v}"
export SDC_FILE="${SDC_FILE:-$ARTIFACTS_DIR/synthesis/${DESIGN_TOP}.sdc}"
export INPUT_DEF
export OUTPUT_DEF="${OUTPUT_DEF:-$RESULT_DIR/iRT_result.def}"
export BOTTOM_ROUTING_LAYER="${BOTTOM_ROUTING_LAYER:-met1}"
export TOP_ROUTING_LAYER="${TOP_ROUTING_LAYER:-met5}"

export SILICONTRACE_RT_FULL_PA_ITER="${SILICONTRACE_RT_FULL_PA_ITER:-${RT_FULL_PA_ITER:-0}}"
export SILICONTRACE_RT_FULL_DR_ITER="${SILICONTRACE_RT_FULL_DR_ITER:-${RT_FULL_DR_ITER:-0}}"
export SILICONTRACE_RT_DR_REPEAT="${SILICONTRACE_RT_DR_REPEAT:-${RT_DR_REPEAT:-1}}"
export SILICONTRACE_RT_DR_STOP_AFTER_BOXES="${SILICONTRACE_RT_DR_STOP_AFTER_BOXES:-${RT_DR_STOP_AFTER_BOXES:-25}}"

forward_knob() {
    local short_name="$1"
    local full_name="$2"
    if [ -n "${!short_name:-}" ] && [ -z "${!full_name:-}" ]; then
        export "$full_name=${!short_name}"
    fi
}

forward_knob RT_TA_FIXED_RECT_SCALE SILICONTRACE_RT_TA_FIXED_RECT_SCALE
forward_knob RT_PA_MAX_CANDIDATE_POINT_NUM SILICONTRACE_RT_PA_MAX_CANDIDATE_POINT_NUM
forward_knob RT_PA_FIXED_RECT_SCALE SILICONTRACE_RT_PA_FIXED_RECT_SCALE
forward_knob RT_PA_ROUTED_RECT_SCALE SILICONTRACE_RT_PA_ROUTED_RECT_SCALE
forward_knob RT_PA_VIOLATION_SCALE SILICONTRACE_RT_PA_VIOLATION_SCALE
forward_knob RT_PA_SIZE SILICONTRACE_RT_PA_SIZE
forward_knob RT_PA_SCHEDULE_INTERVAL SILICONTRACE_RT_PA_SCHEDULE_INTERVAL
forward_knob RT_PA_MAX_ROUTED_TIMES SILICONTRACE_RT_PA_MAX_ROUTED_TIMES
forward_knob RT_PA_MAX_CANDIDATE_PATCH_NUM SILICONTRACE_RT_PA_MAX_CANDIDATE_PATCH_NUM
forward_knob RT_TA_ROUTED_RECT_SCALE SILICONTRACE_RT_TA_ROUTED_RECT_SCALE
forward_knob RT_TA_VIOLATION_SCALE SILICONTRACE_RT_TA_VIOLATION_SCALE
forward_knob RT_TA_SCHEDULE_INTERVAL SILICONTRACE_RT_TA_SCHEDULE_INTERVAL
forward_knob RT_TA_MAX_ROUTED_TIMES SILICONTRACE_RT_TA_MAX_ROUTED_TIMES
forward_knob RT_DR_FIXED_RECT_SCALE SILICONTRACE_RT_DR_FIXED_RECT_SCALE
forward_knob RT_DR_ROUTED_RECT_SCALE SILICONTRACE_RT_DR_ROUTED_RECT_SCALE
forward_knob RT_DR_VIOLATION_SCALE SILICONTRACE_RT_DR_VIOLATION_SCALE
forward_knob RT_DR_SIZE SILICONTRACE_RT_DR_SIZE
forward_knob RT_DR_SCHEDULE_INTERVAL SILICONTRACE_RT_DR_SCHEDULE_INTERVAL
forward_knob RT_DR_MAX_ROUTED_TIMES SILICONTRACE_RT_DR_MAX_ROUTED_TIMES
forward_knob RT_DR_MAX_CANDIDATE_PATCH_NUM SILICONTRACE_RT_DR_MAX_CANDIDATE_PATCH_NUM
forward_knob RT_BLOCKAGES SILICONTRACE_RT_BLOCKAGES

for path in "$IEDA_BIN" "$NETLIST_FILE" "$SDC_FILE" "$INPUT_DEF"; do
    if [ ! -e "$path" ]; then
        echo "Missing required file: $path" >&2
        exit 1
    fi
done

mkdir -p "$RESULT_DIR/report" "$RESULT_DIR/feature" "$RESULT_DIR/rt"

echo "iRT probe: $PROBE_NAME"
echo "design: $DESIGN_TOP"
echo "input DEF: $INPUT_DEF"
echo "result dir: $RESULT_DIR"
echo "routing layers: $BOTTOM_ROUTING_LAYER-$TOP_ROUTING_LAYER"
echo "stop after boxes: ${SILICONTRACE_RT_DR_STOP_AFTER_BOXES:-}"
if [ -n "${SILICONTRACE_RT_BLOCKAGES:-}" ]; then
    echo "route blockages: $SILICONTRACE_RT_BLOCKAGES"
fi

"$IEDA_BIN" -script "$SCRIPT_DIR/tcl/run_iRT.tcl"

ROUTE_STATUS_FILE="$RESULT_DIR/rt/route_status.txt"
if [ -f "$ROUTE_STATUS_FILE" ]; then
    echo ""
    cat "$ROUTE_STATUS_FILE"
fi

if [ "${STRICT_SUCCESS:-0}" = "1" ]; then
    grep -q '^status=success$' "$ROUTE_STATUS_FILE"
fi
