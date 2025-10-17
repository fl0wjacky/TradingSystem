"""
核心分析算法模块
包括：关键节点检测、插值计算、对标链验证、质量判定
"""
from typing import Dict, Optional, Tuple, List
from src.database import MagDatabase


class MagAnalyzer:
    def __init__(self, db: MagDatabase):
        self.db = db

    def analyze_coin(self, coin: str, date: str) -> Optional[Dict]:
        """
        分析单个币种，判断是否处于关键节点并生成建议
        """
        coin_data = self.db.get_coin_data(coin, date)
        if not coin_data:
            return None

        # 检测是否为关键节点
        node_info = self._detect_key_node(coin, coin_data)
        if not node_info:
            return None  # 不在关键节点，无需分析

        # 找到参考节点并计算场外指数差值
        reference = self._find_reference_node(coin, date, node_info['node_type'])
        if not reference:
            return None  # 无法找到参考节点

        # 参考节点的类型（从返回值中获取，表示它是以什么身份被选中的）
        ref_node_type = reference.get('node_type', '')

        # 计算当前场外指数（如果是爆破跨越节点，使用插值）
        current_offchain_index = coin_data['offchain_index']
        if node_info['node_type'] in ['break_200', 'break_0']:
            # 需要插值计算跨越阈值时的场外指数
            previous_data = self.db.get_previous_day_data(coin, date)
            if previous_data:
                threshold = 200 if node_info['node_type'] == 'break_200' else 0
                current_offchain_index = self.db._interpolate_offchain_index(
                    previous_data['offchain_index'],
                    coin_data['offchain_index'],
                    previous_data['break_index'],
                    coin_data['break_index'],
                    threshold
                )

        # 计算涨幅百分比（需要传入phase_type以判断进退场期）
        change_pct, phase_correction = self._calculate_change_percentage(
            reference['offchain_index'],
            current_offchain_index,
            coin_data['phase_type']
        )

        # 检查对标链状态并应用修正
        us_stock_correction = 0
        benchmark_status = self._check_benchmark_chain(coin, date, coin_data)

        # 如果美股在退场期，给予-10%修正
        if 'us_stock' in benchmark_status and benchmark_status['us_stock']['phase_type'] == '退场期':
            if coin_data['phase_type'] == '进场期':
                us_stock_correction = -10

        # 爆破指数修正
        break_index_correction = self._calculate_break_index_correction(
            node_info['node_type'],
            coin_data.get('break_index', 0)
        )

        # 逼近修正：当前节点有逼近标记时，应用-5%修正
        approaching_correction = 0
        if coin_data.get('is_approaching', 0) == 1:
            approaching_correction = -5

        # 计算最终百分比
        final_pct = change_pct + phase_correction + us_stock_correction + break_index_correction + approaching_correction

        # 质量评级
        quality_rating = self._get_quality_rating(final_pct)

        # 构建分析结果
        result = {
            'date': date,
            'coin': coin,
            'node_type': node_info['node_type'],
            'reference_node_date': reference['date'],
            'reference_node_type': ref_node_type,  # 参考节点的类型
            'reference_offchain_index': reference['offchain_index'],
            'current_offchain_index': current_offchain_index,  # 使用插值后的值
            'change_percentage': change_pct,
            'phase_correction': phase_correction,
            'us_stock_correction': us_stock_correction,
            'break_index_correction': break_index_correction,
            'approaching_correction': approaching_correction,
            'final_percentage': final_pct,
            'quality_rating': quality_rating,
            'benchmark_chain_status': str(benchmark_status),
            'coin_data': coin_data,
            'benchmark_details': benchmark_status
        }

        # 保存分析结果到数据库
        self.db.save_analysis_result(result)

        return result

    def _detect_key_node(self, coin: str, coin_data: Dict) -> Optional[Dict]:
        """
        检测是否为4种关键节点之一：
        1. 进场期第一天
        2. 退场期第一天
        3. 爆破指数跌破200
        4. 爆破指数负转正

        重构版本：使用日期查询而非数组索引，支持乱序和缺失日期
        """
        current_date = coin_data['date']
        phase_days = coin_data.get('phase_days')
        break_index = coin_data.get('break_index')

        # 检测进场期第一天
        if coin_data['phase_type'] == '进场期' and phase_days == 1:
            return {'node_type': 'enter_phase_day1'}

        # 检测退场期第一天
        if coin_data['phase_type'] == '退场期' and phase_days == 1:
            return {'node_type': 'exit_phase_day1'}

        # 检测爆破指数跨越节点（使用实际前一天的数据）
        previous_data = self.db.get_previous_day_data(coin, current_date)

        if previous_data and break_index is not None:
            prev_break = previous_data.get('break_index')

            if prev_break is not None:
                # 检测跌破200
                if prev_break >= 200 and break_index < 200:
                    return {'node_type': 'break_200'}

                # 检测负转正
                if prev_break < 0 and break_index >= 0:
                    return {'node_type': 'break_0'}

        return None

    def _find_reference_node(self, coin: str, current_date: str,
                           node_type: str) -> Optional[Dict]:
        """
        根据节点类型找到对应的参考节点

        重构版本：使用新的 find_crossing_node 方法，支持乱序和缺失日期
        返回: {'date': 日期, 'offchain_index': 场外指数, 'node_type': 节点类型}
        """
        # 进场期第一天：对比最近的爆破跌破200或前一次进场期第一天
        if node_type == 'enter_phase_day1':
            break_200_node = self.db.find_crossing_node(coin, current_date, 200, 'down')
            enter_node = self.db.find_last_phase_node(coin, '进场期', current_date)

            # 选择时间更近的
            candidates = []
            if break_200_node:
                candidates.append({'date': break_200_node[0],
                                 'offchain_index': break_200_node[1],
                                 'node_type': 'break_200'})
            if enter_node:
                candidates.append({'date': enter_node[0],
                                 'offchain_index': enter_node[1],
                                 'node_type': 'enter_phase_day1'})

            if candidates:
                # 返回日期最近的
                return max(candidates, key=lambda x: x['date'])

        # 退场期第一天：对比最近的爆破负转正或前一次退场期第一天
        elif node_type == 'exit_phase_day1':
            break_0_node = self.db.find_crossing_node(coin, current_date, 0, 'up')
            exit_node = self.db.find_last_phase_node(coin, '退场期', current_date)

            candidates = []
            if break_0_node:
                candidates.append({'date': break_0_node[0],
                                 'offchain_index': break_0_node[1],
                                 'node_type': 'break_0'})
            if exit_node:
                candidates.append({'date': exit_node[0],
                                 'offchain_index': exit_node[1],
                                 'node_type': 'exit_phase_day1'})

            if candidates:
                return max(candidates, key=lambda x: x['date'])

        # 爆破指数跌破200：对比上一个重要节点
        # 逻辑：每次跌破200标志着一个小节的结束，需要与小节起点对比
        elif node_type == 'break_200':
            candidates = []

            # 候选1: 上一次跌破200的节点
            last_break_200 = self.db.find_crossing_node(coin, current_date, 200, 'down')
            if last_break_200:
                candidates.append({'date': last_break_200[0],
                                 'offchain_index': last_break_200[1],
                                 'node_type': 'break_200'})

            # 候选2: 本周期的进场期第1天
            enter_node = self.db.find_last_phase_node(coin, '进场期', current_date)
            if enter_node:
                candidates.append({'date': enter_node[0],
                                 'offchain_index': enter_node[1],
                                 'node_type': 'enter_phase_day1'})

            # 返回日期最近的（即当前小节的起点）
            if candidates:
                return max(candidates, key=lambda x: x['date'])

        # 爆破指数负转正：对比上一个重要节点
        # 逻辑：退场期也是分小节的，每次负转正标志着一个小节的结束
        elif node_type == 'break_0':
            candidates = []

            # 候选1: 上一次负转正的节点
            last_break_0 = self.db.find_crossing_node(coin, current_date, 0, 'up')
            if last_break_0:
                candidates.append({'date': last_break_0[0],
                                 'offchain_index': last_break_0[1],
                                 'node_type': 'break_0'})

            # 候选2: 本周期的退场期第1天
            exit_node = self.db.find_last_phase_node(coin, '退场期', current_date)
            if exit_node:
                candidates.append({'date': exit_node[0],
                                 'offchain_index': exit_node[1],
                                 'node_type': 'exit_phase_day1'})

            # 返回日期最近的（即当前小节的起点）
            if candidates:
                return max(candidates, key=lambda x: x['date'])

        return None

    def _calculate_change_percentage(self, ref_index: float,
                                    current_index: int,
                                    phase_type: str) -> Tuple[float, float]:
        """
        计算场外指数变化百分比，并应用相变修正

        规则：
        1. 基础涨幅：
           - 进场期：场外指数变高→正，变低→负
           - 退场期：场外指数变高→负，变低→正（反向）

        2. 相变修正：
           - 进场期：从<1000→>=1000，+5%；从>=1000→<1000，-5%
           - 退场期：从<1000→>=1000，-5%；从>=1000→<1000，+5%（反向）

        返回：(基础涨幅百分比, 相变修正值)
        """
        if ref_index == 0:
            return (0, 0)

        # 基础涨幅
        raw_change = ((current_index - ref_index) / ref_index) * 100

        # 根据进退场期调整符号
        if phase_type == '进场期':
            base_change = raw_change
        else:  # 退场期
            base_change = -raw_change  # 反向

        # 相变修正：如果跨越1000
        phase_correction = 0
        if (ref_index < 1000 <= current_index) or (current_index < 1000 <= ref_index):
            # 判断是向上跨越还是向下跨越
            is_upward = current_index > ref_index

            if phase_type == '进场期':
                # 进场期：向上跨越+5%，向下跨越-5%
                phase_correction = 5 if is_upward else -5
            else:  # 退场期
                # 退场期：向上跨越-5%，向下跨越+5%（反向）
                phase_correction = -5 if is_upward else 5

        return (base_change, phase_correction)

    def _check_benchmark_chain(self, coin: str, date: str,
                              coin_data: Dict) -> Dict:
        """
        检查对标链状态：美股 → BTC → 龙头币
        """
        benchmark_status = {}

        # 如果是BTC或美股，不需要检查对标链
        if coin == 'BTC' or coin_data.get('is_us_stock'):
            return benchmark_status

        # 获取美股数据
        us_stock = self.db.get_coin_data('NASDAQ', date)
        if us_stock:
            benchmark_status['us_stock'] = {
                'phase_type': us_stock['phase_type'],
                'offchain_index': us_stock['offchain_index']
            }

        # 获取BTC数据
        btc_data = self.db.get_coin_data('BTC', date)
        if btc_data:
            benchmark_status['btc'] = {
                'phase_type': btc_data['phase_type'],
                'offchain_index': btc_data['offchain_index']
            }

        # 如果是小币，还需要检查龙头币
        if not coin_data.get('is_dragon_leader') and coin != 'BTC':
            dragon_leaders = self.db.get_dragon_leaders(date)
            if dragon_leaders:
                benchmark_status['dragon_leaders'] = [
                    {
                        'coin': d['coin'],
                        'phase_type': d['phase_type'],
                        'offchain_index': d['offchain_index']
                    }
                    for d in dragon_leaders
                ]

        return benchmark_status

    def _calculate_break_index_correction(self, node_type: str,
                                          break_index: int) -> float:
        """
        爆破指数修正规则：
        - 进场期第一天 且 爆破指数>200: -2.5%
        - 退场期第一天 且 爆破指数<0: -2.5%
        """
        if node_type == 'enter_phase_day1' and break_index > 200:
            return -2.5
        elif node_type == 'exit_phase_day1' and break_index < 0:
            return -2.5
        return 0

    def _get_quality_rating(self, final_percentage: float) -> str:
        """
        根据最终百分比判定质量等级
        > 5%: 优质
        -5% ~ 5%: 一般
        < -5%: 劣质
        """
        if final_percentage > 5:
            return '优质'
        elif final_percentage >= -5:
            return '一般'
        else:
            return '劣质'

    def check_benchmark_chain_pass(self, coin: str, date: str) -> bool:
        """
        验证对标链是否通过
        小币：美股进场 AND BTC进场 AND 龙头币进场
        """
        coin_data = self.db.get_coin_data(coin, date)
        if not coin_data:
            return False

        # BTC和美股始终通过
        if coin == 'BTC' or coin_data.get('is_us_stock'):
            return True

        # 龙头币只需检查美股和BTC
        if coin_data.get('is_dragon_leader'):
            us_stock = self.db.get_coin_data('NASDAQ', date)
            btc_data = self.db.get_coin_data('BTC', date)

            if not us_stock or not btc_data:
                return False

            return (us_stock['phase_type'] == '进场期' and
                   btc_data['phase_type'] == '进场期')

        # 小币：需要全链通过
        us_stock = self.db.get_coin_data('NASDAQ', date)
        btc_data = self.db.get_coin_data('BTC', date)
        dragon_leaders = self.db.get_dragon_leaders(date)

        if not us_stock or not btc_data:
            return False

        # 检查美股和BTC
        if us_stock['phase_type'] != '进场期' or btc_data['phase_type'] != '进场期':
            return False

        # 检查所有龙头币
        if not dragon_leaders:
            return False

        for leader in dragon_leaders:
            if leader['phase_type'] != '进场期':
                return False

        return True
