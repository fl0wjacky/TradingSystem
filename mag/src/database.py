"""
数据库操作模块
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class MagDatabase:
    def __init__(self, db_path: str = "mag_data.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 主数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coin_daily_data (
                    date TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    phase_type TEXT,  -- 进场期/退场期
                    phase_days INTEGER,
                    offchain_index INTEGER,
                    break_index INTEGER,
                    shelin_point REAL,
                    is_dragon_leader INTEGER DEFAULT 0,  -- 1为龙头币，0为否
                    is_us_stock INTEGER DEFAULT 0,  -- 1为美股纳指，0为否
                    is_approaching INTEGER DEFAULT 0,  -- 1为逼近状态，0为否
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, coin)
                )
            """)

            # 关键节点记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS key_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    node_type TEXT NOT NULL,  -- break_200, break_0, enter_phase, exit_phase
                    offchain_index INTEGER,
                    break_index INTEGER,
                    phase_type TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 分析结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    node_type TEXT,
                    reference_node_date TEXT,
                    reference_offchain_index REAL,
                    current_offchain_index INTEGER,
                    change_percentage REAL,
                    phase_correction REAL DEFAULT 0,
                    us_stock_correction REAL DEFAULT 0,
                    break_index_correction REAL DEFAULT 0,
                    final_percentage REAL,
                    quality_rating TEXT,  -- 优质/一般/劣质
                    benchmark_chain_status TEXT,  -- 对标链状态
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 特殊关键节点表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS special_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    node_type TEXT NOT NULL,  -- quality_warning_entry, quality_warning_exit, break_above_200,
                                               -- offchain_above_1000, offchain_below_1000, approaching
                    description TEXT,
                    offchain_index INTEGER,
                    break_index INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, coin, node_type)
                )
            """)

            conn.commit()

    def insert_or_update_coin_data(self, data: Dict):
        """插入或更新币种数据（同日期同币种会覆盖）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO coin_daily_data
                (date, coin, phase_type, phase_days, offchain_index, break_index,
                 shelin_point, is_dragon_leader, is_us_stock, is_approaching)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['date'],
                data['coin'],
                data.get('phase_type'),
                data.get('phase_days'),
                data.get('offchain_index'),
                data.get('break_index'),
                data.get('shelin_point'),
                data.get('is_dragon_leader', 0),
                data.get('is_us_stock', 0),
                data.get('is_approaching', 0)
            ))
            conn.commit()

    def get_coin_data(self, coin: str, date: str) -> Optional[Dict]:
        """获取特定币种特定日期的数据"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE coin = ? AND date = ?
            """, (coin, date))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_coin_history(self, coin: str, limit: int = 100) -> List[Dict]:
        """获取币种历史数据（按日期倒序）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE coin = ?
                ORDER BY date DESC
                LIMIT ?
            """, (coin, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_date_data(self) -> List[Dict]:
        """获取最新日期的所有币种数据"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE date = (SELECT MAX(date) FROM coin_daily_data)
                ORDER BY
                    CASE
                        WHEN coin = 'BTC' THEN 1
                        WHEN is_dragon_leader = 1 THEN 2
                        WHEN is_us_stock = 1 THEN 3
                        ELSE 4
                    END,
                    coin
            """)
            return [dict(row) for row in cursor.fetchall()]

    def find_last_break_200_node(self, coin: str, before_date: str) -> Optional[Tuple[str, int]]:
        """查找最近一次爆破指数跌破200的节点（返回日期和场外指数）"""
        history = self.get_coin_history(coin, limit=100)

        prev_break = None
        for i, record in enumerate(history):
            if record['date'] >= before_date:
                continue

            current_break = record['break_index']
            if current_break is None:
                continue

            # 找到跌破200的那一天
            if prev_break is not None and prev_break >= 200 and current_break < 200:
                # 需要插值计算
                next_record = history[i-1] if i > 0 else None
                if next_record:
                    interpolated = self._interpolate_offchain_index(
                        next_record['offchain_index'],
                        record['offchain_index'],
                        next_record['break_index'],
                        record['break_index'],
                        200
                    )
                    return (record['date'], interpolated)
                return (record['date'], record['offchain_index'])

            prev_break = current_break

        return None

    def find_last_break_0_node(self, coin: str, before_date: str) -> Optional[Tuple[str, int]]:
        """查找最近一次爆破指数负转正的节点（返回日期和场外指数）"""
        history = self.get_coin_history(coin, limit=100)

        prev_break = None
        for i, record in enumerate(history):
            if record['date'] >= before_date:
                continue

            current_break = record['break_index']
            if current_break is None:
                continue

            # 找到负转正的那一天
            if prev_break is not None and prev_break < 0 and current_break >= 0:
                # 需要插值计算
                next_record = history[i-1] if i > 0 else None
                if next_record:
                    interpolated = self._interpolate_offchain_index(
                        next_record['offchain_index'],
                        record['offchain_index'],
                        next_record['break_index'],
                        record['break_index'],
                        0
                    )
                    return (record['date'], interpolated)
                return (record['date'], record['offchain_index'])

            prev_break = current_break

        return None

    def find_last_phase_node(self, coin: str, phase_type: str, before_date: str) -> Optional[Tuple[str, int]]:
        """查找最近一次进场期/退场期第一天的节点"""
        history = self.get_coin_history(coin, limit=100)

        for record in history:
            if record['date'] >= before_date:
                continue

            if record['phase_type'] == phase_type and record['phase_days'] == 1:
                return (record['date'], record['offchain_index'])

        return None

    def _interpolate_offchain_index(self, off1: int, off2: int,
                                   break1: int, break2: int,
                                   target_break: int) -> int:
        """插值法计算爆破指数在临界值时的场外指数"""
        if break1 == break2:
            return off1

        ratio = (target_break - break1) / (break2 - break1)
        interpolated = off1 + (off2 - off1) * ratio
        return round(interpolated)

    def save_analysis_result(self, result: Dict):
        """保存分析结果"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO analysis_results
                (date, coin, node_type, reference_node_date, reference_offchain_index,
                 current_offchain_index, change_percentage, phase_correction,
                 us_stock_correction, break_index_correction, approaching_correction,
                 final_percentage, quality_rating, benchmark_chain_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['date'],
                result['coin'],
                result.get('node_type'),
                result.get('reference_node_date'),
                result.get('reference_offchain_index'),
                result['current_offchain_index'],
                result.get('change_percentage', 0),
                result.get('phase_correction', 0),
                result.get('us_stock_correction', 0),
                result.get('break_index_correction', 0),
                result.get('approaching_correction', 0),
                result['final_percentage'],
                result['quality_rating'],
                result.get('benchmark_chain_status', '')
            ))
            conn.commit()

    def get_dragon_leaders(self, date: str) -> List[Dict]:
        """获取某日的龙头币列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE date = ? AND is_dragon_leader = 1
            """, (date,))
            return [dict(row) for row in cursor.fetchall()]

    def get_previous_day_data(self, coin: str, current_date: str) -> Optional[Dict]:
        """
        获取指定币种在指定日期前一天的数据
        使用实际日期查询，不依赖数组索引
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE coin = ? AND date < ?
                ORDER BY date DESC
                LIMIT 1
            """, (coin, current_date))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_next_day_data(self, coin: str, current_date: str) -> Optional[Dict]:
        """
        获取指定币种在指定日期后一天的数据
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE coin = ? AND date > ?
                ORDER BY date ASC
                LIMIT 1
            """, (coin, current_date))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_crossing_node(self, coin: str, before_date: str,
                          threshold: int, cross_direction: str) -> Optional[Tuple[str, int]]:
        """
        查找爆破指数跨越临界值的节点

        Args:
            coin: 币种名称
            before_date: 在此日期之前查找
            threshold: 临界值 (200 或 0)
            cross_direction: 'down' (跌破) 或 'up' (升破)

        Returns:
            (日期, 插值后的场外指数) 或 None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 获取before_date之前的所有数据，按日期倒序
            cursor.execute("""
                SELECT date, offchain_index, break_index
                FROM coin_daily_data
                WHERE coin = ? AND date < ?
                ORDER BY date DESC
            """, (coin, before_date))

            records = [dict(row) for row in cursor.fetchall()]

            if len(records) < 2:
                return None

            # 遍历查找跨越点
            for i in range(len(records) - 1):
                current = records[i]
                previous = records[i + 1]

                if current['break_index'] is None or previous['break_index'] is None:
                    continue

                # 检测跨越
                crossed = False
                if cross_direction == 'down':
                    # 跌破: 前一天 >= threshold, 当天 < threshold
                    if previous['break_index'] >= threshold and current['break_index'] < threshold:
                        crossed = True
                elif cross_direction == 'up':
                    # 升破: 前一天 < threshold, 当天 >= threshold
                    if previous['break_index'] < threshold and current['break_index'] >= threshold:
                        crossed = True

                if crossed:
                    # 插值计算
                    interpolated = self._interpolate_offchain_index(
                        previous['offchain_index'],
                        current['offchain_index'],
                        previous['break_index'],
                        current['break_index'],
                        threshold
                    )
                    return (current['date'], interpolated)

            return None

    def delete_analysis_results(self, start_date: str, end_date: str) -> int:
        """删除指定日期范围的分析结果和特殊节点，返回删除数量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 删除分析结果
            cursor.execute("""
                DELETE FROM analysis_results
                WHERE date >= ? AND date <= ?
            """, (start_date, end_date))
            deleted_analysis = cursor.rowcount

            # 删除特殊节点
            cursor.execute("""
                DELETE FROM special_nodes
                WHERE date >= ? AND date <= ?
            """, (start_date, end_date))
            deleted_special = cursor.rowcount

            conn.commit()
            return deleted_analysis + deleted_special

    def get_data_in_range(self, start_date: str, end_date: str) -> List[Dict]:
        """获取指定日期范围内的所有币种数据"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE date >= ? AND date <= ?
                ORDER BY date ASC, coin ASC
            """, (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]

    def insert_special_node(self, date: str, coin: str, node_type: str,
                           description: str, offchain_index: int = None,
                           break_index: int = None):
        """插入特殊关键节点（重复则忽略）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO special_nodes
                (date, coin, node_type, description, offchain_index, break_index)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date, coin, node_type, description, offchain_index, break_index))
            conn.commit()

    def get_special_nodes(self, coin: str = None, limit: int = 100) -> List[Dict]:
        """获取特殊关键节点列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if coin:
                cursor.execute("""
                    SELECT * FROM special_nodes
                    WHERE coin = ?
                    ORDER BY date DESC
                    LIMIT ?
                """, (coin, limit))
            else:
                cursor.execute("""
                    SELECT * FROM special_nodes
                    ORDER BY date DESC, coin
                    LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_data_since_phase_start(self, coin: str, current_date: str,
                                         phase_type: str, max_count: int = 7) -> List[Dict]:
        """
        获取从本阶段开始（进场期/退场期第1天）到当前日期的数据

        Args:
            coin: 币种
            current_date: 当前日期
            phase_type: 阶段类型（进场期/退场期）
            max_count: 最多获取多少条记录

        Returns:
            按日期正序排列的数据列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 找到本阶段第1天的日期
            cursor.execute("""
                SELECT date FROM coin_daily_data
                WHERE coin = ? AND date <= ? AND phase_type = ? AND phase_days = 1
                ORDER BY date DESC
                LIMIT 1
            """, (coin, current_date, phase_type))

            row = cursor.fetchone()
            if not row:
                return []

            phase_start_date = row['date']

            # 获取从phase_start_date到current_date的所有数据
            cursor.execute("""
                SELECT * FROM coin_daily_data
                WHERE coin = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
                LIMIT ?
            """, (coin, phase_start_date, current_date, max_count))

            return [dict(row) for row in cursor.fetchall()]

    def has_quality_warning_in_section(self, coin: str, section_start_date: str,
                                       current_date: str, node_type: str) -> bool:
        """
        检查指定小节内是否已经存在质量修正节点

        Args:
            coin: 币种
            section_start_date: 小节起始日期
            current_date: 当前日期
            node_type: 节点类型（quality_warning_entry 或 quality_warning_exit）

        Returns:
            如果已存在返回True，否则返回False
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM special_nodes
                WHERE coin = ?
                  AND node_type = ?
                  AND date >= ?
                  AND date <= ?
            """, (coin, node_type, section_start_date, current_date))
            count = cursor.fetchone()[0]
            return count > 0
