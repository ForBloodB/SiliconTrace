#!/bin/bash
# 全流程自动化脚本
# 硅迹开源 (SiliconTrace Open)
# 功能: RTL → Yosys综合 → iEDA后端(FP/PL/CTS/RT/STA) → GDSII

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "=========================================="
echo " 硅迹开源 - 全流程自动化"
echo "=========================================="

# 步骤 1: Yosys 综合
echo ""
echo "===== 步骤 1: Yosys 综合 ====="
cd "$PROJECT_ROOT/synthesis"
bash run_synth.sh

# 步骤 2: iEDA 后端流程
echo ""
echo "===== 步骤 2: iEDA 后端流程 ====="
cd "$PROJECT_ROOT/backend"
bash run_ieda.sh

echo ""
echo "=========================================="
echo " 全流程完成！"
echo "=========================================="
