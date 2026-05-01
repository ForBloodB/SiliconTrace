#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Cleaning generated artifacts..."

rm -rf "$PROJECT_ROOT/artifacts"
rm -rf "$PROJECT_ROOT/synthesis/results"
rm -rf "$PROJECT_ROOT/backend/result"
rm -rf "$PROJECT_ROOT/temp"

echo "Clean complete."
