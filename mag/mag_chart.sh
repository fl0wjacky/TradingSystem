#!/bin/bash
# Mag 标的可视化页面生成脚本 -> 生成 mag_chart.html
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 src/gen_chart.py "$@"
