#!/bin/bash

# 回测脚本
# 用法: ./mag_backtest.sh <币种> <开始日期> <结束日期> <性格类型>
# 示例: ./mag_backtest.sh BTC 2025-10-01 2025-11-22 conservative

if [ $# -ne 4 ]; then
    echo "用法: $0 <币种> <开始日期> <结束日期> <性格类型>"
    echo ""
    echo "参数说明:"
    echo "  币种: BTC, ETH, SOL 等"
    echo "  开始日期: YYYY-MM-DD 格式"
    echo "  结束日期: YYYY-MM-DD 格式"
    echo "  性格类型: conservative, aggressive, middle_a, middle_b, middle_c, middle_d"
    echo ""
    echo "性格类型说明:"
    echo "  conservative  - 高稳健型（优质进场期第1天进场，第1次爆破跌200出场）"
    echo "  aggressive    - 高风险型（退场期劣质建仓，退场期第1天出场）"
    echo "  middle_a      - 中间型-a（仅适用美股/BTC/龙头币，场外指数>1000全仓）"
    echo "  middle_b      - 中间型-b（懒人型，优质进场期第1天进场，退场期第1天出场）"
    echo "  middle_c      - 中间型-c（性价比型，优质进场期第1天进场，第2次及以上负值出场）"
    echo "  middle_d      - 中间型-d（a8资金，退场期劣质建仓+进场期完成建仓，场外指数<1500获利了结）"
    echo ""
    echo "示例:"
    echo "  $0 BTC 2025-10-01 2025-11-22 conservative"
    exit 1
fi

python3 -m src.mag_backtest "$1" "$2" "$3" "$4"
