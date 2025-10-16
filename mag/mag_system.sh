#!/bin/bash
# Mag 系统主程序启动脚本
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 src/mag_system.py "$@"
