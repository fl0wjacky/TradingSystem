#!/usr/bin/env python3
"""
Mag 重新分析工具
用于补录数据后，重新分析历史日期的关键节点
"""
import sys
from datetime import datetime, timedelta
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.prompt import Prompt

from src.database import MagDatabase
from src.analyzer import MagAnalyzer
from src.advisor import MagAdvisor

console = Console()


def reanalyze_date_range(start_date: str, end_date: str, coins: list = None, verbose: bool = False):
    """
    重新分析指定日期范围的数据

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        coins: 指定币种列表，None表示所有币种
        verbose: 是否显示详细分析结果
    """
    from src.config import mag_config

    # 加载配置
    mag_config.load_from_yaml()

    db = MagDatabase()
    analyzer = MagAnalyzer(db, mag_config)
    advisor = MagAdvisor()

    console.print(Panel.fit(
        f"[bold cyan]Mag 重新分析工具[/bold cyan]\n"
        f"[dim]日期范围: {start_date} 至 {end_date}[/dim]",
        border_style="cyan"
    ))

    # 删除该日期范围的旧分析结果
    console.print(f"\n[yellow]正在删除旧的分析结果...[/yellow]")
    deleted_count = db.delete_analysis_results(start_date, end_date)
    console.print(f"[green]✓[/green] 已删除 {deleted_count} 条旧分析结果\n")

    # 获取日期范围内的所有数据
    all_data = db.get_data_in_range(start_date, end_date)

    if not all_data:
        console.print("[yellow]警告：指定日期范围内没有数据[/yellow]")
        return

    # 按日期分组
    data_by_date = {}
    for record in all_data:
        date = record['date']
        if date not in data_by_date:
            data_by_date[date] = []
        data_by_date[date].append(record)

    # 按日期排序
    sorted_dates = sorted(data_by_date.keys())

    console.print(f"[cyan]找到 {len(sorted_dates)} 个日期, {len(all_data)} 条数据记录[/cyan]\n")

    # 逐日分析
    analysis_results = []
    total_analyzed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:

        task = progress.add_task("[cyan]正在分析...", total=len(all_data))

        for date in sorted_dates:
            records = data_by_date[date]

            for record in records:
                coin = record['coin']

                # 如果指定了币种列表，跳过不在列表中的
                if coins and coin not in coins:
                    progress.update(task, advance=1)
                    continue

                # 分析
                result = analyzer.analyze_coin(coin, date)

                if result:
                    analysis_results.append(result)
                    total_analyzed += 1

                progress.update(task, advance=1)

    # 显示结果
    console.print(f"\n[green]✓[/green] 分析完成！")
    console.print(f"  总记录数: {len(all_data)}")
    console.print(f"  检测到关键节点: {total_analyzed} 个\n")

    # 获取该日期范围内的特殊节点
    all_special_nodes = db.get_special_nodes(limit=1000)
    special_nodes_in_range = [
        node for node in all_special_nodes
        if start_date <= node['date'] <= end_date
    ]

    # 如果指定了币种，过滤特殊节点
    if coins:
        special_nodes_in_range = [
            node for node in special_nodes_in_range
            if node['coin'] in coins
        ]

    # 合并节点列表
    if analysis_results or special_nodes_in_range:
        console.print(f"[bold cyan]节点列表：[/bold cyan]\n")

        # 关键节点类型翻译
        node_type_map = {
            'enter_phase_day1': '进场期第1天',
            'exit_phase_day1': '退场期第1天',
            'break_200': '爆破跌破200',
            'break_0': '爆破负转正'
        }

        # 特殊节点类型翻译
        special_node_type_map = {
            'approaching': '提示逼近',
            'quality_warning_entry': '进场期质量修正',
            'quality_warning_exit': '退场期质量修正',
            'break_above_200': '爆破指数超200',
            'offchain_above_1000': '场外指数超1000',
            'offchain_below_1000': '场外指数跌破1000'
        }

        # 合并所有节点（关键节点 + 特殊节点）
        all_nodes = []

        # 添加关键节点
        for result in analysis_results:
            all_nodes.append({
                'type': 'key',
                'date': result['date'],
                'coin': result['coin'],
                'data': result
            })

        # 添加特殊节点
        for node in special_nodes_in_range:
            all_nodes.append({
                'type': 'special',
                'date': node['date'],
                'coin': node['coin'],
                'data': node
            })

        # 按日期和币种排序
        all_nodes.sort(key=lambda x: (x['date'], x['coin']))

        # 显示所有节点
        for i, node in enumerate(all_nodes, 1):
            if node['type'] == 'key':
                # 关键节点
                result = node['data']
                quality = result['quality_rating']
                if quality == '优质':
                    color = "green"
                elif quality == '一般':
                    color = "yellow"
                else:
                    color = "red"

                # 翻译当前节点类型
                node_type_text = node_type_map.get(result['node_type'], result['node_type'])

                # 翻译参考节点类型
                ref_node_type = result.get('reference_node_type', '')
                ref_node_type_text = node_type_map.get(ref_node_type, ref_node_type) if ref_node_type else ''

                # 构建显示文本
                display_parts = [
                    f"[{color}]{i}. {result['date']}[/{color}]",
                    f"[bold]{result['coin']}[/bold]"
                ]

                # 显示对比关系：参考节点 → 当前节点
                if ref_node_type_text:
                    display_parts.append(f"{ref_node_type_text} → {node_type_text}")
                else:
                    display_parts.append(node_type_text)

                # 使用小节描述替代"质量"
                section_desc = result.get('section_desc', '')
                if section_desc:
                    display_parts.append(
                        f"预测{section_desc}: [{color}]{quality}[/{color}] ({result['final_percentage']:+.1f}%)"
                    )
                else:
                    display_parts.append(
                        f"质量: [{color}]{quality}[/{color}] ({result['final_percentage']:+.1f}%)"
                    )

                console.print("  " + " - ".join(display_parts))

                # 如果是详细模式，显示完整分析
                if verbose:
                    console.print(f"\n[dim]{'─' * 70}[/dim]")
                    advice = advisor.generate_advice(result)
                    console.print(advice)
                    console.print(f"[dim]{'─' * 70}[/dim]\n")

            else:
                # 特殊节点
                special_node = node['data']
                # 直接使用 description 字段显示完整信息
                node_description = special_node.get('description', special_node['node_type'])

                # 特殊节点用黄色显示
                display_parts = [
                    f"[yellow]{i}. {special_node['date']}[/yellow]",
                    f"[bold]{special_node['coin']}[/bold]",
                    node_description
                ]

                # 对于逼近节点，添加"质量劣化"标识
                if special_node['node_type'] == 'approaching':
                    display_parts.append("[red]质量劣化[/red]")
                elif special_node['node_type'] in ['quality_warning_entry', 'quality_warning_exit']:
                    display_parts.append("[red]质量下降[/red]")

                console.print("  " + " - ".join(display_parts))

    console.print()


def main():
    """主入口"""
    if len(sys.argv) < 2:
        console.print("""
[bold cyan]Mag 重新分析工具[/bold cyan]

用法:
  python3 mag_reanalyze.py <start_date> [end_date] [options] [coins...]

参数:
  start_date  - 开始日期 (YYYY-MM-DD)
  end_date    - 结束日期 (可选，默认为开始日期)
  -v, --verbose - 显示详细分析结果和建议
  coins       - 指定币种 (可选，多个币种用空格分隔)

示例:
  # 重新分析单个日期的所有币种
  python3 mag_reanalyze.py 2025-10-14

  # 重新分析单个日期并显示详细结果
  python3 mag_reanalyze.py 2025-10-14 -v

  # 重新分析日期范围的所有币种
  python3 mag_reanalyze.py 2025-10-10 2025-10-15

  # 重新分析日期范围并显示详细结果
  python3 mag_reanalyze.py 2025-10-10 2025-10-15 -v

  # 重新分析日期范围的指定币种
  python3 mag_reanalyze.py 2025-10-10 2025-10-15 BTC ETH

  # 重新分析所有历史数据
  python3 mag_reanalyze.py 2025-01-01 2025-12-31
        """)
        sys.exit(0)

    # 检查 verbose 选项
    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    args = [arg for arg in sys.argv[1:] if arg not in ['-v', '--verbose']]

    if not args:
        console.print("[red]错误：请至少指定开始日期[/red]")
        sys.exit(1)

    start_date = args[0]

    # 解析参数
    if len(args) >= 2 and args[1].count('-') == 2:
        # 第二个参数是日期
        end_date = args[1]
        coins = args[2:] if len(args) > 2 else None
    else:
        # 第二个参数不是日期，作为币种
        end_date = start_date
        coins = args[1:] if len(args) > 1 else None

    # 验证日期格式
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        console.print("[red]错误：日期格式不正确，请使用 YYYY-MM-DD 格式[/red]")
        sys.exit(1)

    # 执行重新分析
    try:
        reanalyze_date_range(start_date, end_date, coins, verbose)
    except Exception as e:
        console.print(f"\n[red]错误：{str(e)}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
