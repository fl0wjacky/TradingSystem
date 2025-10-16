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
        output.append("=" * 60)
        output.append(f"币种：{coin}")
        output.append(f"日期：{date}")
        output.append(f"当前状态：{phase_type}第{phase_days}天")
        output.append("-" * 60)

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
        us_corr = analysis_result['us_stock_correction']
        break_corr = analysis_result.get('break_index_correction', 0)
        approaching_corr = analysis_result.get('approaching_correction', 0)

        calculation_parts = [f"基础涨幅 {base_change:+.1f}%"]
        if phase_corr != 0:
            calculation_parts.append(f"相变修正 {phase_corr:+.1f}%")
        if us_corr != 0:
            calculation_parts.append(f"美股修正 {us_corr:+.1f}%")
        if break_corr != 0:
            calculation_parts.append(f"爆破指数修正 {break_corr:+.1f}%")
        if approaching_corr != 0:
            calculation_parts.append(f"逼近修正 {approaching_corr:+.1f}%")

        output.append(f"场外指数变化：{' + '.join(calculation_parts)} = {final_pct:+.1f}%")
        output.append(f"判定结果：【{quality}{phase_type}】")
        output.append("-" * 60)

        # 分级建议
        output.append("分级建议：")
        output.append("")

        advice = MagAdvisor._get_tiered_advice(quality, phase_type, coin, coin_data)
        for line in advice:
            output.append(f"  {line}")

        output.append("=" * 60)
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
    def _get_tiered_advice(quality: str, phase_type: str, coin: str, coin_data: Dict) -> list:
        """
        生成分级建议
        """
        advice = []

        if phase_type == '进场期':
            if quality == '优质':
                advice.extend([
                    "▸ 高稳健型：",
                    "  - 分批建仓主流币种（建议3-5批，每批20%-25%）",
                    "  - 设置紧密止损（-5%~-8%）",
                    "  - 优先配置BTC/ETH等核心资产",
                    "",
                    "▸ 高风险型：",
                    "  - 主流币重仓配置（可达60%-70%总仓位）",
                    "  - 山寨币适度分配（20%-30%）",
                    "  - 设置动态加码机制和追踪止损",
                    "  - 密切关注场外指数和爆破指数变化",
                    "",
                    "▸ 中间型：",
                    "  - 建立基线仓位（40%-50%）",
                    "  - 逐节点上涨后追加配置",
                    "  - 实时风控，设置分级止盈点",
                    "  - 保持30%现金应对回调"
                ])
            elif quality == '一般':
                advice.extend([
                    "▸ 高稳健型：",
                    "  - 小仓位试探（10%-15%）",
                    "  - 严格止损（-3%~-5%）",
                    "  - 等待更明确信号",
                    "",
                    "▸ 高风险型：",
                    "  - 可适度建仓（30%-40%）",
                    "  - 分批进场，预留加码空间",
                    "  - 设置较严格的止损",
                    "",
                    "▸ 中间型：",
                    "  - 观望为主，可小仓位（10%-20%）",
                    "  - 等待场外指数突破1000后再加仓",
                    "  - 灵活应对，保持大部分现金"
                ])
            else:  # 劣质
                advice.extend([
                    "▸ 高稳健型：",
                    "  - 【不建议入场】",
                    "  - 继续观望，等待更优质机会",
                    "",
                    "▸ 高风险型：",
                    "  - 极小仓位试探（<10%）",
                    "  - 超短线思路，快进快出",
                    "  - 严格止损（-2%~-3%）",
                    "",
                    "▸ 中间型：",
                    "  - 【不建议入场】",
                    "  - 观察后续数据变化"
                ])

        else:  # 退场期
            if quality == '优质':
                advice.extend([
                    "▸ 所有类型：",
                    "  - 【立即止盈】分批平仓（建议2-3批）",
                    "  - 优先减持山寨币和小市值币种",
                    "  - 核心仓位可留20%-30%观察",
                    "  - 转移至稳定币或现金",
                    "  - 不建议开新仓位"
                ])
            elif quality == '一般':
                advice.extend([
                    "▸ 高稳健型：",
                    "  - 减仓至30%以下",
                    "  - 提高现金比例",
                    "",
                    "▸ 高风险型：",
                    "  - 减持50%以上仓位",
                    "  - 保留核心资产观察",
                    "",
                    "▸ 中间型：",
                    "  - 减仓至40%-50%",
                    "  - 持续关注场外指数，跌破1000立即清仓"
                ])
            else:  # 劣质
                advice.extend([
                    "▸ 所有类型：",
                    "  - 【警惕】退场信号较弱，可能横盘震荡",
                    "  - 建议降低仓位至50%以下",
                    "  - 等待更明确的退场信号",
                    "  - 设置保护性止损"
                ])

        return advice
