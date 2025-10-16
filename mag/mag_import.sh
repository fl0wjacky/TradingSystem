#!/bin/bash
# Mag 数据导入工具启动脚本
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 src/mag_import.py "$@"
