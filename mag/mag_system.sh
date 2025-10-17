#!/bin/bash
# Mag 系统主程序启动脚本

# 显示帮助信息
show_help() {
    cat << EOF
Mag 现货提示系统 v1.0

用法:
  ./mag_system.sh [选项] [notion_url]
  ./mag_system.sh -h|--help

参数:
  notion_url                  - Notion数据链接（可选，如不提供将提示输入）

选项:
  -h, --help                  - 显示此帮助信息
  --firecrawl-key=KEY         - 临时使用指定的 Firecrawl API key
  --notion-token=TOKEN        - 临时使用指定的 Notion API token
  --show-config               - 显示当前配置状态

功能说明:
  从Notion页面抓取币种数据，自动分析关键节点并给出交易建议

  支持的币种：BTC、ETH、BNB、SOL、DOGE、XRP等主流币种和山寨币
  分析内容：场外指数、进退场期、爆破指数、对标链状态等

  数据抓取降级策略（按优先级）：
    1. Firecrawl MCP (Claude Code 环境)
    2. Firecrawl API (需配置 FIRECRAWL_API_KEY)
    3. Notion API (需配置 NOTION_API_TOKEN)
    4. 简单 HTTP 请求 (适用于公开页面)
    5. 测试数据 (最后降级)

配置文件:
  .env                        - 配置文件（不会提交到 Git）
  .env.example                - 配置模板

示例:
  # 使用配置文件中的 API key
  ./mag_system.sh https://notion.so/your-page-id

  # 临时覆盖 Firecrawl API key
  ./mag_system.sh --firecrawl-key=your_key https://notion.so/your-page-id

  # 临时覆盖 Notion API token
  ./mag_system.sh --notion-token=your_token https://notion.so/your-page-id

  # 显示配置状态
  ./mag_system.sh --show-config

  # 交互式输入链接
  ./mag_system.sh

EOF
}

# 检查帮助参数
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# 运行主程序（传递所有参数）
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)" python3 src/mag_system.py "$@"
