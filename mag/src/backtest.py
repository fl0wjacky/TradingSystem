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

            if trade_result:
                cash = trade_result['cash_after']
                position = trade_result['position_after']

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
                    'total_value': cash + position * price
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
            'final_cash': cash,
            'final_position': position,
            'trades': trades
        }

    def _get_all_nodes(self, coin: str, start_date: str, end_date: str) -> List[Dict]:
        """获取时间范围内的所有节点"""
        import sqlite3

        # 获取关键节点和分析结果（包含质量评级）
        with sqlite3.connect(self.db.db_path) as conn:
            key_nodes_query = """
                SELECT
                    k.date, k.node_type, k.offchain_index, k.break_index,
                    a.quality_rating, a.final_percentage
                FROM key_nodes k
                LEFT JOIN analysis_results a ON k.date = a.date AND k.coin = a.coin
                WHERE k.coin = ? AND k.date >= ? AND k.date <= ?
                ORDER BY k.date
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
            date = node[0]
            # 获取谢林点价格
            price = self._get_price(coin, date)
            all_nodes.append({
                'coin': coin,
                'date': date,
                'node_type': node[1],
                'offchain_index': node[2],
                'break_index': node[3],
                'quality_rating': node[4],
                'final_percentage': node[5],
                'price': price,
                'is_key_node': True
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
        根据节点类型和性格决定操作

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
        node_type = node['node_type']
        offchain_index = node['offchain_index']

        # 获取质量评级（对于关键节点）
        quality = self._get_quality(node) if node['is_key_node'] else None

        # 中间型-a 特殊处理
        if personality == 'middle_a':
            # 判断是否是美股/BTC/龙头币（这里假设都适用，实际需要从数据库查询）
            # 场外指数 > 1000：全仓
            if node_type == 'offchain_above_1000':
                return 'buy_full'
            # 场外指数 < 1000：清仓
            elif node_type == 'offchain_below_1000':
                return 'sell_all' if has_position else None
            # 退场期第1天：根据场外指数判断
            elif node_type == 'exit_phase_day1':
                if offchain_index >= 1000:
                    return 'buy_full'
                else:
                    return 'sell_all' if has_position else None
            # 质量修正：减仓
            elif node_type == 'quality_warning_entry':
                return 'sell_50' if has_position else None
            else:
                return None

        # 高稳健型
        elif personality == 'conservative':
            if node_type == 'enter_phase_day1':
                if quality == '优质':
                    return 'buy_full'
                elif quality == '一般':
                    return 'buy_30'
            elif node_type == 'break_200':
                # 第1次爆破跌200（需要从node获取次数）
                if self._is_first_break_200(node):
                    return 'sell_all' if has_position else None
            elif node_type == 'exit_phase_day1':
                return 'sell_all' if has_position else None
            elif node_type == 'quality_warning_entry':
                return 'sell_50' if has_position else None

        # 高风险型
        elif personality == 'aggressive':
            if node_type == 'break_0':
                if quality == '劣质':
                    return 'buy_40'
                elif quality == '一般':
                    return 'buy_20'
            elif node_type == 'exit_phase_day1':
                return 'sell_all' if has_position else None
            elif node_type == 'quality_warning_entry':
                return 'sell_50' if has_position else None

        # 中间型-b
        elif personality == 'middle_b':
            if node_type == 'enter_phase_day1':
                if quality == '优质':
                    return 'buy_full'
                elif quality == '一般':
                    return 'buy_30'
            elif node_type == 'exit_phase_day1':
                return 'sell_all' if has_position else None
            elif node_type == 'quality_warning_entry':
                return 'sell_50' if has_position else None

        # 中间型-c
        elif personality == 'middle_c':
            if node_type == 'enter_phase_day1':
                if quality == '优质':
                    return 'buy_full'
                elif quality == '一般':
                    return 'buy_30'
            elif node_type == 'break_200':
                # 第2次及以上 且 负值
                if not self._is_first_break_200(node) and self._is_negative_quality(node):
                    return 'sell_all' if has_position else None
            elif node_type == 'exit_phase_day1':
                return 'sell_all' if has_position else None
            elif node_type == 'quality_warning_entry':
                return 'sell_50' if has_position else None

        # 中间型-d
        elif personality == 'middle_d':
            if node_type == 'break_0':
                if quality == '劣质':
                    return 'buy_40'
                elif quality == '一般':
                    return 'buy_20'
            elif node_type == 'enter_phase_day1':
                return 'buy_all_remaining'
            elif node_type == 'offchain_below_1500':
                return 'sell_50' if has_position else None
            elif node_type == 'exit_phase_day1':
                return 'sell_all' if has_position else None
            elif node_type == 'quality_warning_entry':
                return 'sell_50' if has_position else None

        return None

    def _get_quality(self, node: Dict) -> Optional[str]:
        """获取节点的质量评级"""
        # 直接从节点数据中返回（已在_get_all_nodes中查询）
        return node.get('quality_rating')

    def _is_first_break_200(self, node: Dict) -> bool:
        """判断是否是第1次爆破跌200"""
        import sqlite3

        # 查询当前节点之前的 break_200 次数
        with sqlite3.connect(self.db.db_path) as conn:
            query = """
                SELECT COUNT(*)
                FROM key_nodes
                WHERE coin = ? AND date < ? AND node_type = 'break_200'
            """
            cursor = conn.execute(query, (node['coin'], node['date']))
            result = cursor.fetchone()

            if result and result[0] is not None:
                count = result[0]
                # 如果之前没有 break_200，则当前是第1次
                return count == 0

        return True  # 默认认为是第1次

    def _is_negative_quality(self, node: Dict) -> bool:
        """判断质量是否为负值"""
        # 直接从节点数据中获取 final_percentage
        final_percentage = node.get('final_percentage')

        if final_percentage is not None:
            return final_percentage < 0

        return False

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
            # 买入30%
            buy_value = initial_capital * 0.3
            if buy_value > cash:
                buy_value = cash
            amount = buy_value / price
            cash -= buy_value
            position += amount

        elif action == 'buy_20':
            # 买入20%
            buy_value = initial_capital * 0.2
            if buy_value > cash:
                buy_value = cash
            amount = buy_value / price
            cash -= buy_value
            position += amount

        elif action == 'buy_40':
            # 买入40%
            buy_value = initial_capital * 0.4
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
