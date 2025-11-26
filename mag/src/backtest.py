#!/usr/bin/env python3
"""
回测模块 - 基于历史数据模拟交易
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from src.database import MagDatabase
from src.config import MagConfig


class BacktestEngine:
    """回测引擎"""

    def __init__(self, db: MagDatabase, config: MagConfig):
        self.db = db
        self.config = config

    def run_backtest(self, coin: str, start_date: str, end_date: str,
                    personality: str, initial_capital: float = 10000.0) -> Dict:
        """
        执行回测

        Args:
            coin: 币种
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            personality: 性格类型
                - conservative: 高稳健型
                - aggressive: 高风险型
                - middle_a: 中间型-a
                - middle_b: 中间型-b
                - middle_c: 中间型-c
                - middle_d: 中间型-d
            initial_capital: 初始资金（美元）

        Returns:
            回测结果字典
        """
        # 初始化账户
        cash = initial_capital  # 现金
        position = 0.0  # 持仓数量

        # 交易记录
        trades = []

        # 最大回撤追踪
        peak_value = initial_capital  # 资金峰值
        max_drawdown = 0.0  # 最大回撤百分比

        # 获取所有节点（关键节点 + 特殊节点）
        nodes = self._get_all_nodes(coin, start_date, end_date)

        if not nodes:
            return {
                'success': False,
                'error': f'未找到 {coin} 在 {start_date} 至 {end_date} 的节点数据'
            }

        # 按日期遍历节点
        for node in nodes:
            date = node['date']
            node_type = node['node_type']
            price = node['price']  # 谢林点价格

            # 跳过没有价格的节点
            if price is None or price == 0:
                continue

            # 根据节点类型和性格决定操作
            action = self._get_action(node, personality, position > 0)

            if not action:
                continue

            # 执行交易
            trade_result = self._execute_trade(
                action, cash, position, price, initial_capital
            )

            if trade_result and trade_result['amount'] > 0:
                cash = trade_result['cash_after']
                position = trade_result['position_after']

                # 计算当前总资产
                current_value = cash + position * price

                # 更新峰值和最大回撤
                if current_value > peak_value:
                    peak_value = current_value
                else:
                    # 计算当前回撤
                    drawdown = (current_value - peak_value) / peak_value * 100
                    if drawdown < max_drawdown:
                        max_drawdown = drawdown

                trades.append({
                    'date': date,
                    'node_type': node_type,
                    'action': action,
                    'price': price,
                    'amount': trade_result['amount'],
                    'cash_before': trade_result['cash_before'],
                    'position_before': trade_result['position_before'],
                    'cash_after': trade_result['cash_after'],
                    'position_after': trade_result['position_after'],
                    'total_value': current_value
                })

        # 计算最终收益
        if not trades:
            final_value = initial_capital
        else:
            last_trade = trades[-1]
            final_value = last_trade['total_value']

        profit = final_value - initial_capital
        profit_rate = (profit / initial_capital) * 100

        return {
            'success': True,
            'coin': coin,
            'start_date': start_date,
            'end_date': end_date,
            'personality': personality,
            'initial_capital': initial_capital,
            'final_value': final_value,
            'profit': profit,
            'profit_rate': profit_rate,
            'max_drawdown': max_drawdown,  # 最大回撤（负数百分比）
            'final_cash': cash,
            'final_position': position,
            'trades': trades
        }

    def _get_all_nodes(self, coin: str, start_date: str, end_date: str) -> List[Dict]:
        """获取时间范围内的所有节点"""
        import sqlite3

        # 直接从 analysis_results 表获取关键节点，JOIN coin_daily_data 获取更多字段
        with sqlite3.connect(self.db.db_path) as conn:
            key_nodes_query = """
                SELECT
                    a.date, a.coin, a.node_type, a.current_offchain_index,
                    c.break_index, a.quality_rating, a.final_percentage,
                    c.phase_type, c.phase_days, c.is_us_stock, c.is_dragon_leader,
                    c.shelin_point, a.reference_node_date
                FROM analysis_results a
                LEFT JOIN coin_daily_data c ON a.date = c.date AND a.coin = c.coin
                WHERE a.coin = ? AND a.date >= ? AND a.date <= ?
                ORDER BY a.date
            """
            cursor = conn.execute(key_nodes_query, (coin, start_date, end_date))
            key_nodes = cursor.fetchall()

            # 获取特殊节点
            special_nodes_query = """
                SELECT date, node_type, offchain_index, break_index
                FROM special_nodes
                WHERE coin = ? AND date >= ? AND date <= ?
                ORDER BY date
            """
            cursor = conn.execute(special_nodes_query, (coin, start_date, end_date))
            special_nodes = cursor.fetchall()

        # 合并节点并获取价格
        all_nodes = []

        for node in key_nodes:
            date, coin_name, node_type, offchain_index, break_index, quality, final_pct, \
                phase_type, phase_days, is_us_stock, is_dragon_leader, shelin_point, ref_date = node

            # 获取谢林点价格
            price = shelin_point if shelin_point else self._get_price(coin, date)

            # 构建符合 MagAdvisor.get_structured_advice() 期望格式的数据
            all_nodes.append({
                'coin': coin_name,
                'date': date,
                'node_type': node_type,
                'offchain_index': offchain_index,
                'break_index': break_index,
                'quality_rating': quality,
                'final_percentage': final_pct,
                'price': price,
                'is_key_node': True,
                # MagAdvisor 需要的字段
                'current_offchain_index': offchain_index,
                'reference_node_date': ref_date,
                'coin_data': {
                    'phase_type': phase_type,
                    'phase_days': phase_days,
                    'is_us_stock': is_us_stock,
                    'is_dragon_leader': is_dragon_leader,
                    'shelin_point': shelin_point
                }
            })

        for node in special_nodes:
            date = node[0]
            price = self._get_price(coin, date)
            all_nodes.append({
                'coin': coin,
                'date': date,
                'node_type': node[1],
                'offchain_index': node[2],
                'break_index': node[3],
                'quality_rating': None,
                'final_percentage': None,
                'price': price,
                'is_key_node': False
            })

        # 按日期排序
        all_nodes.sort(key=lambda x: x['date'])

        return all_nodes

    def _get_price(self, coin: str, date: str) -> Optional[float]:
        """获取谢林点价格"""
        import sqlite3

        with sqlite3.connect(self.db.db_path) as conn:
            query = """
                SELECT shelin_point
                FROM coin_daily_data
                WHERE coin = ? AND date = ?
            """
            cursor = conn.execute(query, (coin, date))
            result = cursor.fetchone()

            if result and result[0] is not None:
                return float(result[0])

        return None

    def _get_action(self, node: Dict, personality: str, has_position: bool) -> Optional[str]:
        """
        根据节点类型和性格决定操作（使用 MagAdvisor 生成建议）

        Returns:
            'buy_full': 全仓买入
            'buy_30': 买入30%
            'buy_20': 买入20%
            'buy_40': 买入40%
            'buy_all_remaining': 买入剩余全部
            'sell_50': 卖出50%
            'sell_all': 全部卖出
            None: 不操作
        """
        from src.advisor import MagAdvisor

        # 对于关键节点，使用 MagAdvisor 生成结构化建议
        if node['is_key_node']:
            # 需要添加 break_200_count 字段
            node['break_200_count'] = self._count_break_200_before(node['coin'], node['date'])
            actions = MagAdvisor.get_structured_advice(node)
            return actions.get(personality)

        # 对于特殊节点，使用 MagAdvisor.get_structured_special_advice()
        else:
            actions = MagAdvisor.get_structured_special_advice(node)
            return actions.get(personality)

    def _count_break_200_before(self, coin: str, date: str) -> int:
        """统计当前日期之前的 break_200 次数"""
        import sqlite3

        # 查询当前节点之前的 break_200 次数（从 analysis_results 表查询）
        with sqlite3.connect(self.db.db_path) as conn:
            query = """
                SELECT COUNT(*)
                FROM analysis_results
                WHERE coin = ? AND date < ? AND node_type = 'break_200'
            """
            cursor = conn.execute(query, (coin, date))
            result = cursor.fetchone()

            if result and result[0] is not None:
                return result[0]

        return 0

    def _execute_trade(self, action: str, cash: float, position: float,
                      price: float, initial_capital: float) -> Optional[Dict]:
        """
        执行交易

        Returns:
            交易结果字典或None（如果无法执行）
        """
        cash_before = cash
        position_before = position

        if action == 'buy_full':
            # 全仓买入
            amount = cash / price
            cash = 0
            position += amount

        elif action == 'buy_30':
            # 买入30% - 基于当前账户价值
            current_value = cash + position * price
            buy_value = current_value * 0.3
            if buy_value > cash:
                buy_value = cash
            amount = buy_value / price
            cash -= buy_value
            position += amount

        elif action == 'buy_20':
            # 买入20% - 基于当前账户价值
            current_value = cash + position * price
            buy_value = current_value * 0.2
            if buy_value > cash:
                buy_value = cash
            amount = buy_value / price
            cash -= buy_value
            position += amount

        elif action == 'buy_40':
            # 买入40% - 基于当前账户价值
            current_value = cash + position * price
            buy_value = current_value * 0.4
            if buy_value > cash:
                buy_value = cash
            amount = buy_value / price
            cash -= buy_value
            position += amount

        elif action == 'buy_all_remaining':
            # 买入剩余全部现金
            amount = cash / price
            cash = 0
            position += amount

        elif action == 'sell_50':
            # 卖出50%
            amount = position * 0.5
            cash += amount * price
            position -= amount

        elif action == 'sell_all':
            # 全部卖出
            amount = position
            cash += amount * price
            position = 0

        else:
            return None

        return {
            'amount': amount,
            'cash_before': cash_before,
            'position_before': position_before,
            'cash_after': cash,
            'position_after': position
        }
