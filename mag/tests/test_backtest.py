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


def _seed_kline(db: MagDatabase):
    """写入真实 K 线：中间价 (开+收)/2 与谢林点不同，且 10-08 这天故意缺 K 线"""
    with sqlite3.connect(db.db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kline_data (
                date TEXT NOT NULL, coin TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                PRIMARY KEY (date, coin))
        """)
        for day in range(1, 11):
            if day == 8:
                continue  # 爆破跌200 当天无 K 线 -> 该节点应被跳过
            d = f'2025-10-{day:02d}'
            o, c = 50000.0 + day * 1000, 52000.0 + day * 1000   # 中间价 = 51000 + day*1000
            conn.execute("INSERT INTO kline_data VALUES (?, 'BTC', ?, ?, ?, ?)",
                         (d, o, c + 500, o - 500, c))
        conn.commit()


def test_backtest_kline_price():
    """K 线模式：以 (开+收)/2 成交、无 K 线日期的节点跳过、按日估值输出资金曲线"""
    fd, tmp_path = tempfile.mkstemp(suffix='.db', prefix='mag_test_')
    os.close(fd)
    try:
        db = MagDatabase(tmp_path)
        _seed_test_data(db)
        _seed_kline(db)
        engine = BacktestEngine(db, MagConfig())
        r = engine.run_backtest('BTC', '2025-09-01', '2025-12-31', 'conservative',
                                initial_capital=10000.0, price_source='kline')
        assert r['success'], r.get('error')
        assert r['price_source'] == 'kline'
        # 区间收窄到有 K 线的日期
        assert (r['start_date'], r['end_date']) == ('2025-10-01', '2025-10-10')
        # 10-02 进场按中间价 53000 成交，而非谢林点 61000
        assert len(r['trades']) == 1, r['trades']
        t = r['trades'][0]
        assert t['date'] == '2025-10-02' and t['action'] == 'buy_full'
        assert abs(t['price'] - 53000.0) < 1e-6
        # 10-08 无 K 线，爆破跌200 的清仓被跳过 -> 期末仍持仓，按 10-10 中间价 61000 估值
        assert r['final_position'] > 0
        assert len(r['equity']) == 9 and r['equity'][-1][0] == '2025-10-10'
        assert abs(r['final_value'] - 10000.0 / 53000.0 * 61000.0) < 1e-6
        assert abs((r['final_value'] - 10000.0) - r['profit']) < 1e-6
        assert r['max_drawdown'] <= 0
        print("✓ K 线模式回测测试通过")
        print(f"  成交价: {t['price']:,.0f}  期末: ${r['final_value']:,.2f}  收益率: {r['profit_rate']:+.2f}%")
    finally:
        os.remove(tmp_path)


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
    test_backtest_kline_price()
