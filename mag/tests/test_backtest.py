#!/usr/bin/env python3
"""
回测功能测试 - 使用独立临时数据库，不影响真实的 mag_data.db
"""
import os
import sqlite3
import tempfile

from src.database import MagDatabase
from src.config import MagConfig
from src.backtest import BacktestEngine


def _seed_test_data(db: MagDatabase):
    """向（全新的临时）数据库写入回测所需的测试数据"""
    with sqlite3.connect(db.db_path) as conn:
        # 谢林点价格序列（offchain_index 统一设为 1000）
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
            conn.execute(
                """
                INSERT INTO coin_daily_data (date, coin, shelin_point, offchain_index)
                VALUES (?, ?, ?, ?)
                """,
                (date, coin, price, 1000),
            )

        # 关键节点：进场期第1天、爆破跌200
        conn.execute(
            """
            INSERT INTO key_nodes (date, coin, node_type, offchain_index, break_index, phase_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ('2025-10-02', 'BTC', 'enter_phase_day1', 1000, 0, '进场期'),
        )
        conn.execute(
            """
            INSERT INTO key_nodes (date, coin, node_type, offchain_index, break_index, phase_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ('2025-10-08', 'BTC', 'break_200', 1000, -200, '进场期'),
        )

        # 分析结果：含质量评级与最终涨幅
        conn.execute(
            """
            INSERT INTO analysis_results (date, coin, node_type, final_percentage, quality_rating)
            VALUES (?, ?, ?, ?, ?)
            """,
            ('2025-10-02', 'BTC', 'enter_phase_day1', 6.5, '优质'),
        )
        conn.execute(
            """
            INSERT INTO analysis_results (date, coin, node_type, final_percentage, quality_rating)
            VALUES (?, ?, ?, ?, ?)
            """,
            ('2025-10-08', 'BTC', 'break_200', 0.0, '一般'),
        )
        conn.commit()


def test_backtest_conservative():
    """高稳健型回测：在临时数据库上运行，校验返回结构与数值一致性"""
    fd, tmp_path = tempfile.mkstemp(suffix='.db', prefix='mag_test_')
    os.close(fd)
    try:
        # 全新临时库：MagDatabase 初始化时自动建表，绝不触碰真实 mag_data.db
        db = MagDatabase(tmp_path)
        config = MagConfig()  # 仅提供修正参数；回测引擎只读 db.db_path
        _seed_test_data(db)

        engine = BacktestEngine(db, config)
        result = engine.run_backtest(
            coin='BTC',
            start_date='2025-10-01',
            end_date='2025-10-10',
            personality='conservative',
            initial_capital=10000.0,
        )

        # 基本结构
        assert result['success'], f"回测失败: {result.get('error')}"
        assert result['coin'] == 'BTC'
        assert result['initial_capital'] == 10000.0
        assert isinstance(result['trades'], list)

        # 数值一致性（profit/profit_rate 与 final_value 的恒等关系）
        assert abs((result['final_value'] - result['initial_capital']) - result['profit']) < 1e-6
        assert abs(result['profit'] / result['initial_capital'] * 100 - result['profit_rate']) < 1e-6

        print("✓ 回测测试通过")
        print(f"  最终资金: ${result['final_value']:,.2f}  收益率: {result['profit_rate']:+.2f}%")
        print(f"  交易笔数: {len(result['trades'])}")
    finally:
        os.remove(tmp_path)


if __name__ == '__main__':
    test_backtest_conservative()
