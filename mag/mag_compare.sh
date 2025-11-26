#!/bin/bash

# 检查参数
if [ $# -ne 2 ]; then
    echo "用法: ./mag_compare.sh <开始日期> <结束日期>"
    echo ""
    echo "参数说明:"
    echo "  开始日期: YYYY-MM-DD 格式"
    echo "  结束日期: YYYY-MM-DD 格式"
    echo ""
    echo "示例:"
    echo "  ./mag_compare.sh 2025-06-14 2025-11-22"
    echo ""
    echo "功能:"
    echo "  对 BTC、ETH、BNB、SOL、DOGE 五种币种进行回测"
    echo "  使用六种策略：高稳健型、高风险型、中间型-a/b/c/d"
    echo "  生成对比表格并计算各策略平均收益率"
    exit 1
fi

# 回测配置
START_DATE="$1"
END_DATE="$2"
COINS=("BTC" "ETH" "BNB" "SOL" "DOGE")
PERSONALITIES=("conservative" "aggressive" "middle_a" "middle_b" "middle_c" "middle_d")

# 临时文件目录
TMP_DIR="/tmp/mag_backtest_$$"
mkdir -p "$TMP_DIR"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================================================"
echo "MAG 回测系统 - 多币种多策略对比"
echo "======================================================================================================"
echo "回测期间: $START_DATE 至 $END_DATE"
echo "初始资金: \$10,000.00"
echo ""
echo "正在运行回测..."
echo ""

# 获取数组索引的函数
get_index() {
    local coin=$1
    local personality=$2
    local coin_idx=0
    local pers_idx=0

    for i in "${!COINS[@]}"; do
        if [[ "${COINS[$i]}" == "$coin" ]]; then
            coin_idx=$i
            break
        fi
    done

    for i in "${!PERSONALITIES[@]}"; do
        if [[ "${PERSONALITIES[$i]}" == "$personality" ]]; then
            pers_idx=$i
            break
        fi
    done

    echo $((coin_idx * ${#PERSONALITIES[@]} + pers_idx))
}

# 使用普通数组存储结果（兼容 bash 3.x）
results=()  # 存储收益率
drawdowns=()  # 存储最大回撤
total_results=$((${#COINS[@]} * ${#PERSONALITIES[@]}))
for ((i=0; i<total_results; i++)); do
    results+=("")
    drawdowns+=("")
done

# 运行所有回测
total=$((${#COINS[@]} * ${#PERSONALITIES[@]}))
current=0

for coin in "${COINS[@]}"; do
    # 显示分析进度（用 \r 可覆盖）
    printf "\r%-70s" "▸ 正在分析 $coin 数据..."
    ./mag_reanalyze.sh "$START_DATE" "$END_DATE" "$coin" > "$TMP_DIR/${coin}_analyze.txt" 2>&1

    for personality in "${PERSONALITIES[@]}"; do
        current=$((current + 1))
        # 动态更新进度（覆盖前一行）
        printf "\r%-70s" "▸ 进度: $current/$total [$coin - $personality]"

        # 运行回测并保存到临时文件
        result_file="$TMP_DIR/${coin}_${personality}.txt"
        ./mag_backtest.sh "$coin" "$START_DATE" "$END_DATE" "$personality" > "$result_file" 2>&1

        # 提取收益率和最大回撤（从文件中读取）
        profit_rate=$(grep "收益率:" "$result_file" | head -1 | awk '{print $2}')
        max_drawdown=$(grep "最大回撤:" "$result_file" | head -1 | awk '{print $2}')

        # 存储结果
        idx=$(get_index "$coin" "$personality")
        results[$idx]="$profit_rate"
        drawdowns[$idx]="$max_drawdown"

        # 调试输出（可选）
        # echo "DEBUG: $coin-$personality -> idx=$idx, rate=$profit_rate, dd=$max_drawdown" >> "$TMP_DIR/debug.log"
    done
done

echo ""
echo ""

# 生成收益率表格
echo "======================================================================================================"
echo "回测结果汇总表 (收益率 %)"
echo "======================================================================================================"
echo ""

# 表头
printf "%-10s" "币种"
for personality in "${PERSONALITIES[@]}"; do
    case $personality in
        conservative) printf "%-17s" "高稳健型" ;;
        aggressive)   printf "%-17s" "高风险型" ;;
        middle_a)     printf "%-17s" "中间型-a" ;;
        middle_b)     printf "%-17s" "中间型-b" ;;
        middle_c)     printf "%-17s" "中间型-c" ;;
        middle_d)     printf "%-17s" "中间型-d" ;;
    esac
done
echo ""
echo "-------------------------------------------------------------------------------------------------------"

# 表格内容
for coin in "${COINS[@]}"; do
    printf "%-10s" "$coin"

    for personality in "${PERSONALITIES[@]}"; do
        idx=$(get_index "$coin" "$personality")
        profit_rate="${results[$idx]}"

        # 格式化收益率并着色
        if [[ -n "$profit_rate" && "$profit_rate" != "" ]]; then
            # 移除 % 号和 + 号
            rate_value="${profit_rate//[%+]/}"

            # 根据正负值着色
            if [[ "$rate_value" =~ ^- ]]; then
                # 负数 - 红色
                printf "${RED}%-17s${NC}" "$profit_rate"
            elif [[ "$rate_value" == "0.00" || "$rate_value" == "-0.00" ]]; then
                # 零 - 黄色
                printf "${YELLOW}%-17s${NC}" "$profit_rate"
            else
                # 正数 - 绿色
                printf "${GREEN}%-17s${NC}" "$profit_rate"
            fi
        else
            printf "%-17s" "N/A"
        fi
    done
    echo ""
done

echo "======================================================================================================"
echo ""
echo ""

# 生成最大回撤表格
echo "======================================================================================================"
echo "最大回撤汇总表 (%)"
echo "======================================================================================================"
echo ""

# 表头
printf "%-10s" "币种"
for personality in "${PERSONALITIES[@]}"; do
    case $personality in
        conservative) printf "%-17s" "高稳健型" ;;
        aggressive)   printf "%-17s" "高风险型" ;;
        middle_a)     printf "%-17s" "中间型-a" ;;
        middle_b)     printf "%-17s" "中间型-b" ;;
        middle_c)     printf "%-17s" "中间型-c" ;;
        middle_d)     printf "%-17s" "中间型-d" ;;
    esac
done
echo ""
echo "-------------------------------------------------------------------------------------------------------"

# 表格内容
for coin in "${COINS[@]}"; do
    printf "%-10s" "$coin"

    for personality in "${PERSONALITIES[@]}"; do
        idx=$(get_index "$coin" "$personality")
        max_drawdown="${drawdowns[$idx]}"

        # 格式化回撤并着色（回撤都是负数，越小（绝对值越大）越差）
        if [[ -n "$max_drawdown" && "$max_drawdown" != "" ]]; then
            # 移除 % 号
            dd_value="${max_drawdown//%/}"

            # 计算绝对值（避免 awk 双重负号语法错误）
            dd_abs=$(awk "BEGIN {v=$dd_value; print (v < 0 ? -v : v)}")
            if (( $(awk "BEGIN {print ($dd_abs > 15)}") )); then
                # 回撤超过15% - 红色
                printf "${RED}%-17s${NC}" "$max_drawdown"
            elif (( $(awk "BEGIN {print ($dd_abs > 10)}") )); then
                # 回撤10-15% - 黄色
                printf "${YELLOW}%-17s${NC}" "$max_drawdown"
            else
                # 回撤小于10% - 绿色
                printf "${GREEN}%-17s${NC}" "$max_drawdown"
            fi
        else
            printf "%-17s" "N/A"
        fi
    done
    echo ""
done

echo "======================================================================================================"
echo ""

# 计算每种性格的统计数据
echo "各策略统计:"
echo "------------------------------------------------------------------------------------------------------"

for personality in "${PERSONALITIES[@]}"; do
    total_rate=0
    total_dd=0
    count_rate=0
    count_dd=0

    for coin in "${COINS[@]}"; do
        idx=$(get_index "$coin" "$personality")
        profit_rate="${results[$idx]}"
        max_drawdown="${drawdowns[$idx]}"

        # 统计收益率
        if [[ -n "$profit_rate" && "$profit_rate" != "" ]]; then
            rate_value="${profit_rate//[%+]/}"
            total_rate=$(awk "BEGIN {print $total_rate + $rate_value}")
            count_rate=$((count_rate + 1))
        fi

        # 统计回撤
        if [[ -n "$max_drawdown" && "$max_drawdown" != "" ]]; then
            dd_value="${max_drawdown//%/}"
            total_dd=$(awk "BEGIN {print $total_dd + $dd_value}")
            count_dd=$((count_dd + 1))
        fi
    done

    if [[ $count_rate -gt 0 && $count_dd -gt 0 ]]; then
        avg_rate=$(awk "BEGIN {printf \"%.2f\", $total_rate / $count_rate}")
        avg_dd=$(awk "BEGIN {printf \"%.2f\", $total_dd / $count_dd}")

        # 格式化输出
        case $personality in
            conservative) label="高稳健型" ;;
            aggressive)   label="高风险型" ;;
            middle_a)     label="中间型-a" ;;
            middle_b)     label="中间型-b" ;;
            middle_c)     label="中间型-c" ;;
            middle_d)     label="中间型-d" ;;
        esac

        # 着色收益率
        if [[ "$avg_rate" =~ ^- ]]; then
            rate_colored="${RED}%+.2f%%${NC}"
        elif [[ "$avg_rate" == "0.00" || "$avg_rate" == "-0.00" ]]; then
            rate_colored="${YELLOW}%+.2f%%${NC}"
        else
            rate_colored="${GREEN}%+.2f%%${NC}"
        fi

        # 着色回撤（避免 awk 双重负号语法错误）
        dd_abs=$(awk "BEGIN {v=$avg_dd; print (v < 0 ? -v : v)}")
        if (( $(awk "BEGIN {print ($dd_abs > 15)}") )); then
            dd_colored="${RED}%.2f%%${NC}"
        elif (( $(awk "BEGIN {print ($dd_abs > 10)}") )); then
            dd_colored="${YELLOW}%.2f%%${NC}"
        else
            dd_colored="${GREEN}%.2f%%${NC}"
        fi

        printf "  %-15s 平均收益: $rate_colored    平均回撤: $dd_colored\n" "$label" "$avg_rate" "$avg_dd"
    fi
done

echo "======================================================================================================"

# 清理临时目录
rm -rf "$TMP_DIR"
