#!/bin/bash
# Mag 系统主程序启动脚本

# 显示帮助信息
show_help() {
    cat << EOF
Mag 现货提示系统 v1.0

用法:
  ./mag_system.sh [notion_url]
  ./mag_system.sh -h|--help

参数:
  notion_url    - Notion数据链接（可选，如不提供将提示输入）

选项:
  -h, --help    - 显示此帮助信息

功能说明:
  从Notion页面抓取币种数据，自动分析关键节点并给出交易建议

  支持的币种：BTC、ETH、BNB、SOL、DOGE、XRP等主流币种和山寨币
  分析内容：场外指数、进退场期、爆破指数、对标链状态等

示例:
  # 直接提供Notion链接
  ./mag_system.sh https://notion.so/your-page-id

  # 交互式输入链接
  ./mag_system.sh

  # 显示帮助
  ./mag_system.sh --help

EOF
}

# 检查帮助参数
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# 运行主程序
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 src/mag_system.py "$@"
