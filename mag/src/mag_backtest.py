#!/usr/bin/env python3
"""
回测命令行工具
"""
import sys
from src.database import MagDatabase
from src.config import MagConfig
from src.backtest import BacktestEngine


def print_backtest_result(result: dict):
    """格式化打印回测结果"""
    if not result['success']:
        print(f"❌ 回测失败: {result['error']}")
        return

    # 打印基本信息
    print("\n" + "="*100)
    print(f"币种: {result['coin']}")
    print(f"回测期间: {result['start_date']} 至 {result['end_date']}")
    print(f"性格类型: {result['personality']}")
    print(f"初始资金: ${result['initial_capital']:,.2f}")
    print("="*100)

    # 打印收益情况
    print(f"\n最终资金: ${result['final_value']:,.2f}")
    print(f"利润: ${result['profit']:,.2f}")
    print(f"收益率: {result['profit_rate']:+.2f}%")
    print(f"最大回撤: {result['max_drawdown']:.2f}%")
    print(f"最终现金: ${result['final_cash']:,.2f}")
    print(f"最终持仓: {result['final_position']:.8f} {result['coin']}")

    # 打印交易记录
    if result['trades']:
        print(f"\n共执行 {len(result['trades'])} 笔交易:")
        print("-"*100)
        print(f"{'日期':<12} {'节点类型':<20} {'操作':<15} {'价格':<12} {'数量':<15} {'剩余资金':<15} {'账户价值':<15}")
        print("-"*100)

        # 节点类型中文映射
        node_type_map = {
            'enter_phase_day1': '进场期第1天',
            'exit_phase_day1': '退场期第1天',
            'break_200': '爆破跌破200',
            'break_0': '爆破负转正',
            'offchain_above_1000': '场外指数超1000',
            'offchain_below_1000': '场外指数跌破1000',
            'offchain_below_1500': '场外指数跌破1500',
            'quality_warning_entry': '进场期质量修正'
        }

        # 操作类型映射
        action_map = {
            'buy_full': '全仓买入',
            'buy_30': '买入30%',
            'buy_20': '买入20%',
            'buy_40': '买入40%',
            'buy_all_remaining': '买入剩余全部',
            'sell_50': '卖出50%',
            'sell_all': '全部卖出'
        }

        for trade in result['trades']:
            node_type_text = node_type_map.get(trade['node_type'], trade['node_type'])
            action_text = action_map.get(trade['action'], trade['action'])

            print(f"{trade['date']:<12} "
                  f"{node_type_text:<20} "
                  f"{action_text:<15} "
                  f"${trade['price']:<11,.2f} "
                  f"{trade['amount']:<15.8f} "
                  f"${trade['cash_after']:<14,.2f} "
                  f"${trade['total_value']:<14,.2f}")

        print("-"*100)
    else:
        print("\n⚠️  期间内没有执行任何交易")

    print()


def main():
    """主函数"""
    if len(sys.argv) != 5:
        print("用法: python3 -m src.mag_backtest <币种> <开始日期> <结束日期> <性格类型>")
        print()
        print("参数说明:")
        print("  币种: BTC, ETH, SOL 等")
        print("  开始日期: YYYY-MM-DD 格式")
        print("  结束日期: YYYY-MM-DD 格式")
        print("  性格类型: conservative, aggressive, middle_a, middle_b, middle_c, middle_d")
        print()
        print("示例:")
        print("  python3 -m src.mag_backtest BTC 2025-10-01 2025-11-22 conservative")
        sys.exit(1)

    coin = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    personality = sys.argv[4]

    # 验证性格类型
    valid_personalities = ['conservative', 'aggressive', 'middle_a', 'middle_b', 'middle_c', 'middle_d']
    if personality not in valid_personalities:
        print(f"❌ 错误: 性格类型必须是以下之一: {', '.join(valid_personalities)}")
        sys.exit(1)

    # 初始化
    config = MagConfig()
    db = MagDatabase(config.db_path)
    engine = BacktestEngine(db, config)

    # 执行回测
    print(f"\n开始回测 {coin} ({start_date} 至 {end_date}) - {personality}...")
    result = engine.run_backtest(coin, start_date, end_date, personality)

    # 打印结果
    print_backtest_result(result)


if __name__ == '__main__':
    main()
