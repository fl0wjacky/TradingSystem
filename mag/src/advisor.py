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

        # 显示小节信息
        section_desc = analysis_result.get('section_desc', '')
        if section_desc:
            # 将描述改为"预测"形式，使用最终百分比
            output.append(f"预测{section_desc}：{quality}（{final_pct:+.1f}%）")
        else:
            output.append(f"判定结果：【{quality}{phase_type}】")
        output.append("-" * 60)

        # 分级建议
        output.append("分级建议：")
        output.append("")

        node_type = analysis_result.get('node_type')
        advice = MagAdvisor._get_tiered_advice(
            quality, phase_type, coin, coin_data, node_type, analysis_result
        )
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
    def _get_tiered_advice(quality: str, phase_type: str, coin: str,
                          coin_data: Dict, node_type: str, analysis_result: Dict) -> list:
        """
        基于当前节点类型和质量生成分级建议

        根据4种性格类型给出建议：
        1. 高稳健型：进场期第1天建仓 → 第1次爆破跌200减仓
        2. 高风险型：爆破指数转正加仓 → 退场期第1天减仓
        3. 中间型-a：场外指数 > 1000 建仓，< 1000 减仓（美股/BTC/龙头币）
        4. 中间型-b：进场期第1天建仓 → 退场期第1天清仓（低精力成本）
        5. 中间型-c：进场期第1天建仓 → 爆破跌200场外指数下降时清仓（高性价比）
        6. 中间型-d：退场期负转正加仓，进场期第1天建仓完毕 → 场外指数1500-1000分批止盈（a8资金）
        """
        advice = []
        offchain_index = coin_data.get('offchain_index', 0)

        # 特殊处理：退场期第1天 - 所有类型清仓
        if node_type == 'exit_phase_day1':
            advice.extend([
                "⚠️  退场期第1天 - 清仓信号",
                "",
                "▸ 所有性格类型：",
                "  - 【立即清仓】转移至稳定币/现金",
                "  - 优先减持山寨币和小市值币种",
                "  - 核心资产BTC/ETH可留少量观察（<20%）",
                "  - 不建议开新仓位",
                "",
                f"当前质量：{quality}（{analysis_result.get('final_percentage', 0):+.1f}%）"
            ])
            return advice

        # 进场期第1天
        if node_type == 'enter_phase_day1':
            advice.append("📈 进场期第1天 - 建仓时机")
            advice.append("")

            advice.extend([
                "▸ 高稳健型：",
                "  - 【建仓】分批建仓（建议3-5批，每批15%-20%）",
                "  - 设置紧密止损（-5%~-8%）",
                "  - 第1次爆破跌200时减仓",
                "",
                "▸ 高风险型：",
                "  - 【观望】等待爆破指数转正后加仓",
                "  - 可小仓位试探（<10%）",
                "",
                "▸ 中间型-a（美股/BTC/龙头币）：",
                f"  - 场外指数：{offchain_index}",
            ])

            if offchain_index > 1000:
                advice.append("  - 【建仓】场外指数>1000，可建仓（20%-30%）")
            else:
                advice.append("  - 【观望】等待场外指数突破1000")

            advice.extend([
                "",
                "▸ 中间型-b（低精力成本）：",
                "  - 【建仓】建立基础仓位（30%-40%）",
                "  - 退场期第1天清仓",
                "",
                "▸ 中间型-c（高性价比）：",
                "  - 【建仓】建立仓位（30%-40%）",
                "  - 跟踪爆破跌200的场外指数变化",
                "",
                "▸ 中间型-d（a8资金）：",
                "  - 【建仓完毕】完成建仓操作",
                "  - 场外指数1500-1000区间分批止盈",
                "  - 退场期第1天清仓"
            ])

        # 爆破指数转正
        elif node_type == 'break_0':
            advice.append("🔥 爆破指数负转正 - 加仓时机")
            advice.append("")

            # 判断当前阶段
            if phase_type == '退场期':
                # 退场期中的爆破负转正
                advice.extend([
                    "▸ 高稳健型：",
                    "  - 【空仓观望】应已在退场期第1天清仓",
                    "  - 如未清仓，立即清仓",
                    "",
                    "▸ 高风险型：",
                    "  - 【评估加仓】如场外指数比上次负转正高，可加仓",
                    "  - 分批加仓，设置追踪止损",
                    "  - 下次退场期第1天或进场期第1天清仓",
                    "",
                    "▸ 中间型-a（美股/BTC/龙头币）：",
                    f"  - 场外指数：{offchain_index}",
                ])

                if offchain_index > 1000:
                    advice.append("  - 【持有】场外指数>1000，维持仓位")
                else:
                    advice.append("  - 【减仓】场外指数<1000，建议减仓")

                advice.extend([
                    "",
                    "▸ 中间型-b（低精力成本）：",
                    "  - 【空仓观望】应已在退场期第1天清仓",
                    "",
                    "▸ 中间型-c（高性价比）：",
                    "  - 【空仓观望】应已在退场期第1天清仓",
                    "",
                    "▸ 中间型-d（a8资金）：",
                    "  - 【评估加仓】如场外指数比上次负转正高，可加仓"
                ])
            else:
                # 进场期中的爆破负转正（理论上不应该出现）
                advice.extend([
                    "▸ 高稳健型：",
                    "  - 【观望】不建议加仓",
                    "",
                    "▸ 高风险型：",
                    "  - 【谨慎】进场期出现负转正异常，建议观望",
                    "",
                    "▸ 中间型-a（美股/BTC/龙头币）：",
                    f"  - 场外指数：{offchain_index}",
                ])

                if offchain_index > 1000:
                    advice.append("  - 【持有】场外指数>1000，维持仓位")
                else:
                    advice.append("  - 【观望】场外指数<1000，观望")

                advice.extend([
                    "",
                    "▸ 中间型-b（低精力成本）：",
                    "  - 【观望】维持现有仓位",
                    "",
                    "▸ 中间型-c（高性价比）：",
                    "  - 【观望】维持现有仓位",
                    "",
                    "▸ 中间型-d（a8资金）：",
                    "  - 【观望】维持仓位"
                ])

        # 爆破指数跌破200
        elif node_type == 'break_200':
            advice.append("⬇️  爆破指数跌破200 - 减仓时机")
            advice.append("")

            advice.extend([
                "▸ 高稳健型：",
                "  - 【减仓】立即减仓（减持30%-50%）",
                "  - 剩余仓位设置止损",
                "",
                "▸ 高风险型：",
                "  - 【观望】可适度减仓（20%-30%）",
                "  - 等待退场期第1天再清仓",
                "",
                "▸ 中间型-a（美股/BTC/龙头币）：",
                f"  - 场外指数：{offchain_index}",
            ])

            if offchain_index > 1000:
                advice.append("  - 【持有】场外指数>1000，可持有")
            else:
                advice.append("  - 【减仓】场外指数<1000，建议减仓")

            advice.extend([
                "",
                "▸ 中间型-b（低精力成本）：",
                "  - 【观望】维持仓位，等待退场期第1天",
                "",
                "▸ 中间型-c（高性价比）：",
                "  - 【评估】如场外指数比前一次跌破200低，清仓",
                "  - 否则持有等待下次信号",
                "",
                "▸ 中间型-d（a8资金）：",
            ])

            if offchain_index > 1500:
                advice.append("  - 【观望】场外指数>1500，持有")
            elif offchain_index > 1000:
                advice.append("  - 【分批止盈】场外指数1500-1000区间，分批减仓")
            else:
                advice.append("  - 【观望】场外指数<1000，持有等待退场期第1天")

        # 通用建议
        advice.append("")
        advice.append(f"当前质量：{quality}（{analysis_result.get('final_percentage', 0):+.1f}%）")

        # 质量修正提示
        if quality == '劣质':
            advice.append("")
            advice.append("⚠️  质量较差，建议及时调整仓位或退出")

        return advice
