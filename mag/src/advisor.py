"""
分级建议输出模块
"""
from typing import Dict


class MagAdvisor:
    @staticmethod
    def generate_advice(analysis_result: Dict) -> str:
        """
        根据分析结果生成分级操作建议
        """
        coin = analysis_result['coin']
        date = analysis_result['date']
        coin_data = analysis_result['coin_data']
        quality = analysis_result['quality_rating']
        final_pct = analysis_result['final_percentage']
        phase_type = coin_data['phase_type']
        phase_days = coin_data['phase_days']
        current_index = analysis_result['current_offchain_index']  # 使用插值后的场外指数

        # 构建输出文本
        output = []
        output.append("=" * 42)
        output.append(f"币种：{coin}")
        output.append(f"日期：{date}")
        output.append(f"当前状态：{phase_type}第{phase_days}天")
        output.append("-" * 42)

        # 对标链分析
        benchmark = analysis_result['benchmark_details']
        benchmark_text = MagAdvisor._format_benchmark_status(benchmark, coin_data)
        output.append(f"对标链分析：{benchmark_text}")

        # 关键节点对比
        ref_date = analysis_result['reference_node_date']
        ref_index = analysis_result['reference_offchain_index']

        # 当前节点的类型
        current_node_type_text = MagAdvisor._get_node_type_text(analysis_result['node_type'])

        # 参考节点的类型（如果有的话）
        ref_node_type = analysis_result.get('reference_node_type', '')
        ref_node_type_text = MagAdvisor._get_node_type_text(ref_node_type) if ref_node_type else ''

        # 构建对比信息
        ref_info = f"{ref_index:.0f} ({ref_date}"
        if ref_node_type_text:
            ref_info += f", {ref_node_type_text}"
        ref_info += ")"

        output.append(f"关键节点对比：{ref_info} → {current_index} ({date}, {current_node_type_text})")

        # 详细计算
        base_change = analysis_result['change_percentage']
        phase_corr = analysis_result['phase_correction']
        divergence_corr = analysis_result.get('divergence_correction', 0)
        divergence_details = analysis_result.get('divergence_details', {})
        break_corr = analysis_result.get('break_index_correction', 0)
        approaching_corr = analysis_result.get('approaching_correction', 0)

        calculation_parts = [f"基础涨幅 {base_change:+.1f}%"]
        if phase_corr != 0:
            calculation_parts.append(f"相变修正 {phase_corr:+.1f}%")

        # 对标链背离修正（展开详情）
        if divergence_corr != 0:
            divergence_items = []
            for coin_name, detail in divergence_details.items():
                divergence_items.append(f"{coin_name}{detail['weight']:+.1f}%")
            divergence_text = f"对标链背离({', '.join(divergence_items)})"
            calculation_parts.append(divergence_text)

        if break_corr != 0:
            calculation_parts.append(f"爆破指数修正 {break_corr:+.1f}%")
        if approaching_corr != 0:
            calculation_parts.append(f"逼近修正 {approaching_corr:+.1f}%")

        output.append(f"场外指数变化：{' + '.join(calculation_parts)} = {final_pct:+.1f}%")

        # 显示小节信息
        section_desc = analysis_result.get('section_desc', '')
        if section_desc:
            # 将描述改为"预测"形式，使用最终百分比
            output.append(f"预测{section_desc}：{quality}（{final_pct:+.1f}%）")
        else:
            output.append(f"判定结果：【{quality}{phase_type}】")
        output.append("-" * 42)

        # 分级建议（只有在有建议时才显示）
        node_type = analysis_result.get('node_type')
        advice = MagAdvisor._get_tiered_advice(
            quality, phase_type, coin, coin_data, node_type, analysis_result
        )

        if advice:  # 只有当有建议时才显示分级建议部分
            output.append("分级建议：")
            output.append("")
            for line in advice:
                output.append(f"  {line}")

        output.append("=" * 42)
        output.append("")

        return "\n".join(output)

    @staticmethod
    def _format_benchmark_status(benchmark: Dict, coin_data: Dict) -> str:
        """格式化对标链状态"""
        parts = []

        # 美股状态
        if 'us_stock' in benchmark:
            us = benchmark['us_stock']
            parts.append(f"美股{us['phase_type']}")

        # BTC状态
        if 'btc' in benchmark:
            btc = benchmark['btc']
            parts.append(f"BTC {btc['phase_type']}")

        # 龙头币状态
        if 'dragon_leaders' in benchmark:
            leaders = benchmark['dragon_leaders']
            enter_count = sum(1 for d in leaders if d['phase_type'] == '进场期')
            parts.append(f"龙头币 {enter_count}/{len(leaders)} 进场期")

        if not parts:
            if coin_data.get('is_us_stock'):
                return "顶层参考指标"
            elif coin_data['coin'] == 'BTC':
                return "核心基准币种"
            else:
                return "数据不足"

        return "、".join(parts)

    @staticmethod
    def _get_node_type_text(node_type: str) -> str:
        """节点类型转文本"""
        mapping = {
            'enter_phase_day1': '进场期第一天',
            'exit_phase_day1': '退场期第一天',
            'break_200': '爆破指数跌破200',
            'break_0': '爆破指数负转正'
        }
        return mapping.get(node_type, node_type)

    @staticmethod
    def _get_tiered_advice(quality: str, phase_type: str, coin: str,
                          coin_data: Dict, node_type: str, analysis_result: Dict) -> list:
        """
        基于当前节点类型和质量生成分级建议（新版本）

        只在满足特定条件时显示相应性格类型的建议，其它情况完全不显示该类型。

        6种性格类型：
        1. 高稳健型：进场期第1天优质建仓 → 第1次爆破跌200清仓
        2. 高风险型：退场期爆破负转正劣质建仓 → 退场期第1天清仓
        3. 中间型-a：场外指数 > 1000 建仓，< 1000 清仓（美股/BTC/龙头币）
        4. 中间型-b：进场期第1天优质建仓 → 退场期第1天清仓（低精力成本）
        5. 中间型-c：进场期第1天优质建仓 → 第2次及以上爆破跌200负值清仓（高性价比）
        6. 中间型-d：退场期爆破负转正劣质建仓 + 进场期第1天建仓完毕 →
                      爆破跌200时1500-1000止盈 → 退场期第1天清仓（a8资金）
        """
        advice = []
        offchain_index = coin_data.get('offchain_index', 0)
        break_200_count = analysis_result.get('break_200_count', 0)
        final_percentage = analysis_result.get('final_percentage', 0)

        # 用于收集有建议的性格类型
        has_advice = False

        # ========== 高稳健型 ==========
        conservative_advice = []

        if node_type == 'enter_phase_day1' and quality == '优质':
            # 进场期第1天且质量优质 → 建仓
            conservative_advice.extend([
                "▸ 高稳健型：",
                "  - 【建仓】进场期第1天，质量优质",
                "  - 建议分批建仓（3-5批，每批15%-20%）",
                "  - 设置紧密止损（-5%~-8%）",
                "  - 第1次爆破跌200时清仓"
            ])
            has_advice = True

        elif node_type == 'break_200' and break_200_count == 1:
            # 进场期第1次爆破跌200 → 清仓
            conservative_advice.extend([
                "▸ 高稳健型：",
                "  - 【清仓】进场期第1次爆破跌破200",
                "  - 立即清仓，转移至稳定币/现金",
                "  - 等待下一次进场期第1天优质建仓机会"
            ])
            has_advice = True

        elif node_type == 'exit_phase_day1':
            # 退场期第1天 → 清仓
            conservative_advice.extend([
                "▸ 高稳健型：",
                "  - 【清仓】退场期第1天",
                "  - 立即清仓，转移至稳定币/现金"
            ])
            has_advice = True

        if conservative_advice:
            advice.extend(conservative_advice)
            advice.append("")

        # ========== 高风险型 ==========
        aggressive_advice = []

        if node_type == 'break_0' and phase_type == '退场期' and quality == '劣质':
            # 退场期爆破负转正且质量劣质 → 分批建仓
            aggressive_advice.extend([
                "▸ 高风险型：",
                "  - 【分批建仓】退场期爆破负转正，质量劣质",
                "  - 分批建仓（建议3-5批）",
                "  - 设置追踪止损",
                "  - 退场期第1天清仓"
            ])
            has_advice = True

        elif node_type == 'exit_phase_day1':
            # 退场期第1天 → 清仓
            aggressive_advice.extend([
                "▸ 高风险型：",
                "  - 【清仓】退场期第1天",
                "  - 立即清仓，转移至稳定币/现金"
            ])
            has_advice = True

        if aggressive_advice:
            advice.extend(aggressive_advice)
            advice.append("")

        # ========== 中间型-a（美股/BTC/龙头币）==========
        # 只在退场期第1天显示，且必须是美股/BTC/龙头币
        # 其它时候通过特殊操作节点（offchain_above_1000/below_1000）显示
        middle_a_advice = []

        # 判断是否是美股/BTC/龙头币
        is_us_stock = coin_data.get('is_us_stock', False)
        is_btc = coin == 'BTC'
        is_dragon_leader = coin in ['ETH', 'BNB', 'SOL', 'DOGE']
        is_middle_a_target = is_us_stock or is_btc or is_dragon_leader

        # 只在退场期第1天显示
        if node_type == 'exit_phase_day1' and is_middle_a_target:
            if offchain_index < 1000:
                middle_a_advice.extend([
                    "▸ 中间型-a(美股/BTC/龙头币): 清仓"
                ])
            else:
                middle_a_advice.extend([
                    "▸ 中间型-a(美股/BTC/龙头币): 建仓"
                ])
            has_advice = True

        if middle_a_advice:
            advice.extend(middle_a_advice)
            advice.append("")

        # ========== 中间型-b（低精力成本）==========
        middle_b_advice = []

        if node_type == 'enter_phase_day1' and quality == '优质':
            # 进场期第1天且质量优质 → 建仓
            middle_b_advice.extend([
                "▸ 中间型-b（低精力成本）：",
                "  - 【建仓】进场期第1天，质量优质",
                "  - 建立基础仓位（30%-40%）",
                "  - 退场期第1天清仓"
            ])
            has_advice = True

        elif node_type == 'exit_phase_day1':
            # 退场期第1天 → 清仓
            middle_b_advice.extend([
                "▸ 中间型-b（低精力成本）：",
                "  - 【清仓】退场期第1天",
                "  - 立即清仓，转移至稳定币/现金"
            ])
            has_advice = True

        if middle_b_advice:
            advice.extend(middle_b_advice)
            advice.append("")

        # ========== 中间型-c（高性价比）==========
        middle_c_advice = []

        if node_type == 'enter_phase_day1' and quality == '优质':
            # 进场期第1天且质量优质 → 建仓
            middle_c_advice.extend([
                "▸ 中间型-c（高性价比）：",
                "  - 【建仓】进场期第1天，质量优质",
                "  - 建立仓位（30%-40%）",
                "  - 跟踪爆破跌200的场外指数变化"
            ])
            has_advice = True

        elif node_type == 'break_200' and break_200_count >= 2 and final_percentage < 0:
            # 进场期第2次或以上爆破跌200且质量为负 → 清仓
            middle_c_advice.extend([
                "▸ 中间型-c（高性价比）：",
                f"  - 【清仓】第{break_200_count}次爆破跌200，质量为负（{final_percentage:+.1f}%）",
                "  - 场外指数下降，建议清仓",
                "  - 转移至稳定币/现金"
            ])
            has_advice = True

        elif node_type == 'exit_phase_day1':
            # 退场期第1天 → 清仓
            middle_c_advice.extend([
                "▸ 中间型-c（高性价比）：",
                "  - 【清仓】退场期第1天",
                "  - 立即清仓，转移至稳定币/现金"
            ])
            has_advice = True

        if middle_c_advice:
            advice.extend(middle_c_advice)
            advice.append("")

        # ========== 中间型-d（a8资金）==========
        middle_d_advice = []

        if node_type == 'break_0' and phase_type == '退场期' and quality == '劣质':
            # 退场期爆破负转正且质量劣质 → 分批建仓
            middle_d_advice.extend([
                "▸ 中间型-d（a8资金）：",
                "  - 【分批建仓】退场期爆破负转正，质量劣质",
                "  - 分批建仓（建议3-5批）",
                "  - 场外指数1500-1000区间分批止盈"
            ])
            has_advice = True

        elif node_type == 'enter_phase_day1':
            # 进场期第1天 → 建仓完毕
            middle_d_advice.extend([
                "▸ 中间型-d（a8资金）：",
                "  - 【建仓完毕】进场期第1天",
                "  - 完成建仓操作",
                "  - 场外指数1500-1000区间分批止盈"
            ])
            has_advice = True

        elif node_type == 'break_200':
            # 进场期爆破跌200 → 根据场外指数判断
            if 1000 < offchain_index < 1500:
                middle_d_advice.extend([
                    "▸ 中间型-d（a8资金）：",
                    f"  - 场外指数：{offchain_index}",
                    "  - 【分批止盈】场外指数在1500-1000区间",
                    "  - 建议分3-5批止盈"
                ])
                has_advice = True
            # 场外指数 > 1500 或 < 1000 时，不显示中间型d

        elif node_type == 'exit_phase_day1':
            # 退场期第1天 → 清仓
            middle_d_advice.extend([
                "▸ 中间型-d（a8资金）：",
                "  - 【清仓】退场期第1天",
                "  - 立即清仓，转移至稳定币/现金"
            ])
            has_advice = True

        if middle_d_advice:
            advice.extend(middle_d_advice)
            advice.append("")

        # 如果没有任何建议，返回空列表（不显示分级建议部分）
        if not has_advice:
            return []

        return advice

    @staticmethod
    def generate_special_advice(special_node_data: Dict) -> str:
        """
        为特殊操作节点生成简化建议（无质量评级，只有操作提示）

        处理的特殊节点：
        - offchain_above_1000: 中间型a建仓（仅美股/BTC/龙头币）
        - offchain_below_1000: 中间型a清仓（仅美股/BTC/龙头币）
        - offchain_below_1500: 中间型d分批止盈
        """
        coin = special_node_data.get('coin')
        date = special_node_data.get('date')
        node_type = special_node_data.get('node_type')
        offchain_index = special_node_data.get('offchain_index', 0)
        break_index = special_node_data.get('break_index', 0)
        description = special_node_data.get('description', '')

        # 判断是否是美股/BTC/龙头币（从数据库获取）
        from src.database import MagDatabase
        db = MagDatabase()
        coin_info = db.get_coin_data(coin, date)

        is_us_stock = coin_info.get('is_us_stock', False) if coin_info else False
        is_btc = coin == 'BTC'
        is_dragon_leader = coin in ['ETH', 'BNB', 'SOL', 'DOGE']
        is_middle_a_target = is_us_stock or is_btc or is_dragon_leader

        # 收集建议内容
        advice_lines = []

        if node_type == 'offchain_above_1000':
            # 中间型a：建仓（仅美股/BTC/龙头币）
            if is_middle_a_target:
                advice_lines.append("▸ 中间型-a(美股/BTC/龙头币): 建仓")

        elif node_type == 'offchain_below_1000':
            # 中间型a：清仓（仅美股/BTC/龙头币）
            if is_middle_a_target:
                advice_lines.append("▸ 中间型-a(美股/BTC/龙头币): 清仓")

        elif node_type == 'offchain_below_1500':
            # 中间型d：分批止盈
            advice_lines.extend([
                "▸ 中间型-d（a8资金）：",
                f"  - 场外指数：{offchain_index}",
                "  - 【开始分批止盈】场外指数跌破1500",
                "  - 在1500-1000区间分批减仓",
                "  - 建议分3-5批止盈"
            ])

        # 如果没有任何建议，返回空字符串
        if not advice_lines:
            return ""

        # 构建完整输出
        output = []
        output.append("=" * 42)
        output.append(f"币种：{coin}")
        output.append(f"日期：{date}")
        output.append(f"特殊节点：{description}")
        output.append("-" * 42)
        output.append("分级建议：")
        output.append("")
        output.extend(advice_lines)
        output.append("=" * 42)
        output.append("")

        return "\n".join(output)
