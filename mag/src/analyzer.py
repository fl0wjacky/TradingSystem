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

        # 检测并保存特殊关键节点
        self._detect_special_nodes(coin, date, coin_data)

        # 检测是否为关键节点
        node_info = self._detect_key_node(coin, coin_data)
        if not node_info:
            return None  # 不在关键节点，无需分析

        # 找到参考节点并计算场外指数差值
        reference = self._find_reference_node(coin, date, node_info['node_type'])
        if not reference:
            return None  # 无法找到参考节点

        # 识别当前小节
        section_num, section_desc, section_pct = self._identify_section(
            coin, date, coin_data['phase_type'], reference, node_info['node_type']
        )

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

        # 检查对标链状态（用于展示）
        benchmark_status = self._check_benchmark_chain(coin, date, coin_data)

        # 计算对标链背离修正
        divergence_correction, divergence_details = self._calculate_benchmark_divergence_correction(
            coin, date, coin_data
        )

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
        final_pct = change_pct + phase_correction + divergence_correction + break_index_correction + approaching_correction

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
            'divergence_correction': divergence_correction,
            'divergence_details': divergence_details,
            'break_index_correction': break_index_correction,
            'approaching_correction': approaching_correction,
            'final_percentage': final_pct,
            'quality_rating': quality_rating,
            'benchmark_chain_status': str(benchmark_status),
            'coin_data': coin_data,
            'benchmark_details': benchmark_status,
            # 小节信息
            'section_num': section_num,
            'section_desc': section_desc,
            'section_pct': section_pct
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
        返回对标链信息，用于展示
        """
        benchmark_status = {}

        # 如果是美股，不需要检查对标链
        if coin_data.get('is_us_stock'):
            return benchmark_status

        # 获取美股数据
        us_stock = self.db.get_coin_data('NASDAQ', date)
        if us_stock:
            benchmark_status['us_stock'] = {
                'phase_type': us_stock['phase_type'],
                'offchain_index': us_stock['offchain_index']
            }

        # 如果不是BTC，获取BTC数据
        if coin != 'BTC':
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

    def _calculate_benchmark_divergence_correction(self, coin: str, date: str,
                                                   coin_data: Dict) -> Tuple[float, Dict]:
        """
        计算对标链背离修正

        扣分权重：
        - 纳指背离：-10分
        - BTC背离：-5分
        - ETH背离：-2.5分
        - BNB背离：-1.5分
        - SOL背离：-1分
        - DOGE背离：-0.5分

        背离定义：当前币种阶段与对标币种阶段不一致

        返回：(总扣分, 背离详情字典)
        """
        current_phase = coin_data.get('phase_type')
        total_correction = 0
        divergence_details = {}

        # 龙头币影响力权重
        dragon_weights = {
            'ETH': -2.5,
            'BNB': -1.5,
            'SOL': -1.0,
            'DOGE': -0.5
        }

        # 美股纳指（所有币种都需要检查，除了美股自己）
        if not coin_data.get('is_us_stock'):
            us_stock = self.db.get_coin_data('NASDAQ', date)
            if us_stock and us_stock['phase_type'] != current_phase:
                total_correction += -10
                divergence_details['NASDAQ'] = {
                    'weight': -10,
                    'phase': us_stock['phase_type']
                }

        # BTC（除了BTC和美股，其他都需要检查）
        if coin != 'BTC' and not coin_data.get('is_us_stock'):
            btc_data = self.db.get_coin_data('BTC', date)
            if btc_data and btc_data['phase_type'] != current_phase:
                total_correction += -5
                divergence_details['BTC'] = {
                    'weight': -5,
                    'phase': btc_data['phase_type']
                }

        # 龙头币（只有小币需要检查）
        if not coin_data.get('is_dragon_leader') and coin != 'BTC' and not coin_data.get('is_us_stock'):
            dragon_leaders = self.db.get_dragon_leaders(date)
            for leader in dragon_leaders:
                leader_coin = leader['coin']
                leader_phase = leader['phase_type']

                if leader_phase != current_phase and leader_coin in dragon_weights:
                    weight = dragon_weights[leader_coin]
                    total_correction += weight
                    divergence_details[leader_coin] = {
                        'weight': weight,
                        'phase': leader_phase
                    }

        return (total_correction, divergence_details)

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

    def _identify_section(self, coin: str, date: str, phase_type: str,
                         reference: Dict, current_node_type: str) -> Tuple[int, str, float]:
        """
        识别当前是第几小节，并返回小节描述和质量百分比

        进场期：
        - 第1小节（进场期质量）：进场期第1天 → 第1次爆破跌200（或直接到退场期第1天）
        - 第2+小节（波动展开质量）：第N次爆破跌200 → 第N+1次爆破跌200（或退场期第1天）

        退场期：
        - 第1小节（退场期质量）：退场期第1天 → 第1次爆破跌0（或直接到进场期第1天）
        - 第2+小节（退场期波动展开质量）：第N次爆破跌0 → 第N+1次爆破跌0（或进场期第1天）

        Args:
            coin: 币种
            date: 当前日期
            phase_type: 阶段类型（进场期/退场期）
            reference: 参考节点信息
            current_node_type: 当前节点类型

        Returns:
            (小节编号, 小节描述, 小节质量百分比)
        """

        # 获取当前币种数据
        coin_data = self.db.get_coin_data(coin, date)
        if not coin_data:
            return (1, '', 0.0)

        # 计算小节的场外指数变化百分比
        section_change_pct, _ = self._calculate_change_percentage(
            reference['offchain_index'],
            coin_data['offchain_index'],
            phase_type
        )

        if phase_type == '进场期':
            # 判断是第几小节：根据当前节点类型
            if current_node_type == 'enter_phase_day1':
                # 当前节点是进场期第1天 → 预测第1小节
                section_num = 1
                section_desc = "进场期第1小节质量"
            elif current_node_type == 'break_200':
                # 当前节点是爆破跌200 → 当前是第N次爆破跌200，预测第N+1小节
                count = self._count_break_200_since_enter(coin, date)
                section_num = count + 1
                section_desc = f"进场期第{section_num}小节质量"
            else:
                section_num = 1
                section_desc = "进场期第1小节质量"

        else:  # 退场期
            if current_node_type == 'exit_phase_day1':
                # 当前节点是退场期第1天 → 预测第1小节
                section_num = 1
                section_desc = "退场期第1小节质量"
            elif current_node_type == 'break_0':
                # 当前节点是爆破负转正 → 当前是第N次爆破负转正，预测第N+1小节
                count = self._count_break_0_since_exit(coin, date)
                section_num = count + 1
                section_desc = f"退场期第{section_num}小节质量"
            else:
                section_num = 1
                section_desc = "退场期第1小节质量"

        return (section_num, section_desc, section_change_pct)

    def _count_break_200_since_enter(self, coin: str, current_date: str) -> int:
        """计算从最近的进场期第1天开始到current_date有多少次爆破跌200"""
        # 找到最近的进场期第1天
        enter_node = self.db.find_last_phase_node(coin, '进场期', current_date)
        if not enter_node:
            return 1

        enter_date = enter_node[0]

        # 获取从enter_date到current_date之间的所有数据
        history = self.db.get_coin_history(coin, limit=100)

        count = 0
        prev_break = None
        for record in reversed(history):
            if record['date'] < enter_date:
                continue
            if record['date'] > current_date:
                break

            current_break = record.get('break_index')
            if current_break is None:
                prev_break = current_break
                continue

            # 检测跌破200
            if prev_break is not None and prev_break >= 200 and current_break < 200:
                count += 1

            prev_break = current_break

        return count

    def _count_break_0_since_exit(self, coin: str, current_date: str) -> int:
        """计算从最近的退场期第1天开始到current_date有多少次爆破负转正"""
        # 找到最近的退场期第1天
        exit_node = self.db.find_last_phase_node(coin, '退场期', current_date)
        if not exit_node:
            return 1

        exit_date = exit_node[0]

        # 获取从exit_date到current_date之间的所有数据
        history = self.db.get_coin_history(coin, limit=100)

        count = 0
        prev_break = None
        for record in reversed(history):
            if record['date'] < exit_date:
                continue
            if record['date'] > current_date:
                break

            current_break = record.get('break_index')
            if current_break is None:
                prev_break = current_break
                continue

            # 检测负转正（从负数到0或正数）
            if prev_break is not None and prev_break < 0 and current_break >= 0:
                count += 1

            prev_break = current_break

        return count

    def _find_current_section_start_date(self, coin: str, current_date: str, phase_type: str) -> Optional[str]:
        """
        找到当前小节的起始日期

        进场期：最近的进场期第1天或爆破跌200
        退场期：最近的退场期第1天或爆破负转正

        Returns:
            小节起始日期，如果找不到返回None
        """
        # 先检查当前日期是否本身就是小节起点
        current_data = self.db.get_coin_data(coin, current_date)
        if not current_data:
            return None

        # 检查当前日期是否是阶段第1天
        if current_data['phase_days'] == 1:
            return current_date

        # 检查当前日期是否是爆破跨越节点
        previous_data = self.db.get_previous_day_data(coin, current_date)
        if previous_data:
            prev_break = previous_data.get('break_index')
            current_break = current_data.get('break_index')

            if prev_break is not None and current_break is not None:
                # 进场期：检查是否跌破200
                if phase_type == '进场期' and prev_break >= 200 and current_break < 200:
                    return current_date

                # 退场期：检查是否负转正
                if phase_type == '退场期' and prev_break < 0 and current_break >= 0:
                    return current_date

        # 当前日期不是小节起点，找之前的小节起点
        candidates = []

        if phase_type == '进场期':
            # 找最近的进场期第1天
            enter_node = self.db.find_last_phase_node(coin, '进场期', current_date)
            if enter_node:
                candidates.append(enter_node[0])

            # 找最近的爆破跌200
            break_200_node = self.db.find_crossing_node(coin, current_date, 200, 'down')
            if break_200_node:
                candidates.append(break_200_node[0])

        else:  # 退场期
            # 找最近的退场期第1天
            exit_node = self.db.find_last_phase_node(coin, '退场期', current_date)
            if exit_node:
                candidates.append(exit_node[0])

            # 找最近的爆破负转正
            break_0_node = self.db.find_crossing_node(coin, current_date, 0, 'up')
            if break_0_node:
                candidates.append(break_0_node[0])

        if not candidates:
            return None

        # 返回最近的日期（即当前小节的起点）
        return max(candidates)

    def _detect_special_nodes(self, coin: str, date: str, coin_data: Dict):
        """
        检测并保存特殊关键节点

        特殊节点类型：
        1. quality_warning_entry: 进场期质量修正（头7次更新爆破指数未破200且均值下降）
        2. quality_warning_exit: 退场期质量修正（头7次更新爆破指数未跌破0）
        3. break_above_200: 爆破指数超过200
        4. offchain_above_1000: 场外指数超过1000
        5. offchain_below_1000: 场外指数跌破1000
        6. approaching: 提示逼近
        """
        phase_type = coin_data.get('phase_type')
        offchain_index = coin_data.get('offchain_index', 0)
        break_index = coin_data.get('break_index', 0)
        is_approaching = coin_data.get('is_approaching', 0)
        is_us_stock = coin_data.get('is_us_stock', 0)

        # 检查周期：币种7次，美股14次
        check_count = 14 if is_us_stock else 7

        # 1. 提示逼近
        if is_approaching == 1:
            self.db.insert_special_node(
                date, coin, 'approaching',
                f"{phase_type}提示逼近 - 场外指数：{offchain_index}，爆破指数：{break_index}",
                offchain_index, break_index
            )

        # 2. 场外指数超过1000（从小于1000到大于等于1000）
        prev_data = self.db.get_previous_day_data(coin, date)
        if prev_data:
            prev_offchain = prev_data.get('offchain_index', 0)
            prev_break = prev_data.get('break_index', 0)

            if prev_offchain < 1000 <= offchain_index:
                self.db.insert_special_node(
                    date, coin, 'offchain_above_1000',
                    f"场外指数超1000 - 场外指数：{offchain_index}，爆破指数：{break_index}",
                    offchain_index, break_index
                )

            # 3. 场外指数跌破1000（从大于等于1000到小于1000）
            if prev_offchain >= 1000 > offchain_index:
                self.db.insert_special_node(
                    date, coin, 'offchain_below_1000',
                    f"场外指数跌破1000 - 场外指数：{offchain_index}，爆破指数：{break_index}",
                    offchain_index, break_index
                )

            # 4. 爆破指数超过200（从小于200到大于等于200）
            if prev_break < 200 <= break_index:
                self.db.insert_special_node(
                    date, coin, 'break_above_200',
                    f"爆破指数超200 - 场外指数：{offchain_index}，爆破指数：{break_index}",
                    offchain_index, break_index
                )

        # 5. 进场期质量修正检查（按小节计数）
        if phase_type == '进场期':
            # 找到当前小节的起始日期
            section_start_date = self._find_current_section_start_date(coin, date, '进场期')

            if section_start_date:
                # 检查本小节是否已经触发过质量修正
                already_warned = self.db.has_quality_warning_in_section(
                    coin, section_start_date, date, 'quality_warning_entry'
                )

                if not already_warned:
                    # 获取从小节起始到当前日期的所有数据
                    history = self.db.get_coin_history(coin, limit=100)
                    section_data = [
                        record for record in history
                        if section_start_date <= record['date'] <= date
                    ]

                    # 如果刚好是小节的第7次（或第14次）更新
                    if len(section_data) == check_count:
                        # 检查是否有任何一次爆破指数超过200
                        has_break_200 = any(d.get('break_index', 0) >= 200 for d in section_data)

                        # 计算爆破指数的移动平均趋势
                        break_indices = [d.get('break_index', 0) for d in section_data if d.get('break_index') is not None]

                        if len(break_indices) >= 2:
                            # 简单判断：前半部分平均值 vs 后半部分平均值
                            mid = len(break_indices) // 2
                            first_half_avg = sum(break_indices[:mid]) / mid
                            second_half_avg = sum(break_indices[mid:]) / (len(break_indices) - mid)

                            is_declining = second_half_avg < first_half_avg

                            # 如果未破200且均值下降
                            if not has_break_200 and is_declining:
                                self.db.insert_special_node(
                                    date, coin, 'quality_warning_entry',
                                    f"进场期第{check_count}次更新 - 爆破指数未破200且均值下降 - 质量下降",
                                    offchain_index, break_index
                                )

        # 6. 退场期质量修正检查（按小节计数）
        if phase_type == '退场期':
            # 找到当前小节的起始日期
            section_start_date = self._find_current_section_start_date(coin, date, '退场期')

            if section_start_date:
                # 检查本小节是否已经触发过质量修正
                already_warned = self.db.has_quality_warning_in_section(
                    coin, section_start_date, date, 'quality_warning_exit'
                )

                if not already_warned:
                    # 获取从小节起始到当前日期的所有数据
                    history = self.db.get_coin_history(coin, limit=100)
                    section_data = [
                        record for record in history
                        if section_start_date <= record['date'] <= date
                    ]

                    # 如果刚好是小节的第7次（或第14次）更新
                    if len(section_data) == check_count:
                        # 检查是否有任何一次爆破指数跌破0
                        has_break_0 = any(d.get('break_index', 0) < 0 for d in section_data)

                        # 如果未跌破0
                        if not has_break_0:
                            self.db.insert_special_node(
                                date, coin, 'quality_warning_exit',
                                f"退场期第{check_count}次更新 - 爆破指数未跌破0 - 质量下降",
                                offchain_index, break_index
                            )
