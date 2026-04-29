#!/bin/bash
# 清理脚本
# 硅迹开源 (SiliconTrace Open)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "清理生成文件..."

# 清理综合结果
rm -rf "$PROJECT_ROOT/synthesis/results/"*

# 清理后端结果
rm -rf "$PROJECT_ROOT/backend/floorplan/"*.def
rm -rf "$PROJECT_ROOT/backend/placement/"*.def
rm -rf "$PROJECT_ROOT/backend/cts/"*.def
rm -rf "$PROJECT_ROOT/backend/routing/"*.def
rm -rf "$PROJECT_ROOT/backend/sta/"*.rpt
rm -rf "$PROJECT_ROOT/backend/converted/"*

# 清理 GDSII
rm -rf "$PROJECT_ROOT/backend/gdsii/"*.gds

echo "清理完成！"
