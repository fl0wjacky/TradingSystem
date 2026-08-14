#!/bin/bash
# Mag 解析巡检:比对笔记预期数据条目与实际解析,揪出漏解析的行
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 src/audit_parse.py "$@"
