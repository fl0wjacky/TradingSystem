#!/bin/bash
# Mag 重新分析工具启动脚本
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 src/mag_reanalyze.py "$@"
