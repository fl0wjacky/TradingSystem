#!/bin/bash

# Mag API 启动脚本

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 进入项目根目录
cd "$SCRIPT_DIR"

echo "=============================="
echo "  Mag API Server"
echo "=============================="
echo ""
echo "启动地址: http://127.0.0.1:8888"
echo "API文档:  http://127.0.0.1:8888/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=============================="
echo ""

# 启动 FastAPI 服务
python3 -m uvicorn src.api:app --host 127.0.0.1 --port 8888 --reload
