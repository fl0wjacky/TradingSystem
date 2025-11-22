#!/usr/bin/env python3
"""
回测功能测试脚本 - 创建测试数据并运行回测
"""
import sqlite3
from src.database import MagDatabase
from src.config import MagConfig
from src.backtest import BacktestEngine


def create_test_data(db: MagDatabase):
    """创建测试数据"""
    with sqlite3.connect(db.db_path) as conn:
        # 清空数据库
        conn.execute("DELETE FROM coin_daily_data")
        conn.execute("DELETE FROM key_nodes")
        conn.execute("DELETE FROM special_nodes")
        conn.commit()

        # 插入测试的谢林点数据
        test_prices = [
            ('2025-10-01', 'BTC', 60000.0),
            ('2025-10-02', 'BTC', 61000.0),  # 进场期第1天
            ('2025-10-03', 'BTC', 62000.0),
            ('2025-10-04', 'BTC', 63000.0),
            ('2025-10-05', 'BTC', 64000.0),
            ('2025-10-06', 'BTC', 65000.0),
            ('2025-10-07', 'BTC', 66000.0),
            ('2025-10-08', 'BTC', 64000.0),  # 爆破跌200
            ('2025-10-09', 'BTC', 63000.0),
            ('2025-10-10', 'BTC', 62000.0),
        ]

        for date, coin, price in test_prices:
            conn.execute("""
                INSERT INTO coin_daily_data (date, coin, shelin_point, offchain_index)
                VALUES (?, ?, ?, ?)
            """, (date, coin, price, 1000))  # offchain_index设为1000
        conn.commit()

        # 插入关键节点
        # 1. 进场期第1天 - 优质
        conn.execute("""
            INSERT INTO key_nodes (
                date, coin, node_type, offchain_index, break_index,
                quality_rating, final_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('2025-10-02', 'BTC', 'enter_phase_day1', 1000, 0, '优质', 6.5))

        # 2. 爆破跌200
        conn.execute("""
            INSERT INTO key_nodes (
                date, coin, node_type, offchain_index, break_index,
                quality_rating, final_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('2025-10-08', 'BTC', 'break_200', 1000, -200, '一般', 0.0))

        conn.commit()

    print("✓ 测试数据已创建")


def main():
    """主函数"""
    config = MagConfig()
    db = MagDatabase(config.db_path)

    print("创建测试数据...")
    create_test_data(db)

    print("\n测试回测功能 - 高稳健型")
    print("="*80)
    engine = BacktestEngine(db, config)

    result = engine.run_backtest(
        coin='BTC',
        start_date='2025-10-01',
        end_date='2025-10-10',
        personality='conservative',
        initial_capital=10000.0
    )

    if result['success']:
        print(f"\n币种: {result['coin']}")
        print(f"回测期间: {result['start_date']} 至 {result['end_date']}")
        print(f"性格类型: {result['personality']}")
        print(f"初始资金: ${result['initial_capital']:,.2f}")
        print(f"\n最终资金: ${result['final_value']:,.2f}")
        print(f"利润: ${result['profit']:,.2f}")
        print(f"收益率: {result['profit_rate']:+.2f}%")

        if result['trades']:
            print(f"\n共执行 {len(result['trades'])} 笔交易:")
            for trade in result['trades']:
                print(f"  {trade['date']}: {trade['action']} @ ${trade['price']:.2f}")
    else:
        print(f"\n❌ 回测失败: {result['error']}")

    db.close()


if __name__ == '__main__':
    main()
