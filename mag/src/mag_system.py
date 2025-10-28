#!/usr/bin/env python3
"""
Mag现货提示系统 - 主程序
"""
import sys
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich import print as rprint

from src.database import MagDatabase
from src.notion_scraper import NotionScraper
from src.analyzer import MagAnalyzer
from src.advisor import MagAdvisor


console = Console()


def parse_arguments():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Mag 现货提示系统 - 基于场外体系的智能交易分析',
        add_help=False  # 禁用默认的 -h，因为我们在 shell 脚本中处理了
    )

    parser.add_argument('notion_url', nargs='?', default=None,
                       help='Notion 数据链接')
    parser.add_argument('--firecrawl-key', dest='firecrawl_key',
                       help='临时覆盖 Firecrawl API key')
    parser.add_argument('--notion-token', dest='notion_token',
                       help='临时覆盖 Notion API token')
    parser.add_argument('--show-config', action='store_true',
                       help='显示配置状态')

    return parser.parse_args()


def main():
    """主程序入口"""
    from src.config import config, mag_config

    # 解析命令行参数
    args = parse_arguments()

    console.print(Panel.fit(
        "[bold cyan]Mag 现货提示系统 v1.0[/bold cyan]\n"
        "[dim]基于场外体系的智能交易分析[/dim]",
        border_style="cyan"
    ))

    # 加载配置文件
    config.load_from_env()
    mag_config.load_from_yaml()

    # 从命令行参数覆盖配置
    if args.firecrawl_key or args.notion_token:
        config.override_from_args(
            firecrawl_key=args.firecrawl_key,
            notion_token=args.notion_token
        )

    # 如果只是显示配置，则显示后退出
    if args.show_config:
        config.show_status()
        mag_config.show_config()
        sys.exit(0)

    # 获取Notion URL
    notion_url = args.notion_url

    if not notion_url:
        console.print("\n[yellow]请输入Notion数据链接：[/yellow]", end="")
        notion_url = input().strip()

    if not notion_url:
        console.print("[red]错误：未提供数据链接[/red]")
        sys.exit(1)

    # 初始化数据库和分析器（传入配置）
    db = MagDatabase()
    analyzer = MagAnalyzer(db, mag_config)

    try:
        # 1. 抓取并解析 Notion 数据
        console.print()
        scraper = NotionScraper(notion_url)

        # 使用降级策略获取数据
        raw_data = scraper.fetch_data()

        # 解析数据
        console.print("\n[cyan]正在解析数据...[/cyan]")
        coin_data_list = scraper.parse_data(raw_data)

        console.print(f"[green]✓[/green] 成功抓取 {len(coin_data_list)} 个币种数据\n")

        # 2. 存储数据
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task2 = progress.add_task("[cyan]正在存储数据到数据库...", total=len(coin_data_list))
            for coin_data in coin_data_list:
                db.insert_or_update_coin_data(coin_data)
                progress.update(task2, advance=1)

        console.print(f"[green]✓[/green] 数据存储完成\n")

        # 3. 分析关键节点
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task3 = progress.add_task("[cyan]正在分析关键节点...", total=len(coin_data_list))
            analysis_results = []

            for coin_data in coin_data_list:
                result = analyzer.analyze_coin(coin_data['coin'], coin_data['date'])
                if result:
                    analysis_results.append(result)
                progress.update(task3, advance=1)

    except Exception as e:
        console.print(f"\n[red]错误：{str(e)}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    # 5. 输出分析结果
    console.print("\n" + "=" * 70)
    console.print("[bold green]分析完成！[/bold green]")
    console.print("=" * 70 + "\n")

    if not analysis_results:
        console.print("[yellow]未检测到关键节点，当前无需操作建议。[/yellow]")
        console.print("[dim]系统会在币种进入关键节点时自动提示。[/dim]\n")
    else:
        console.print(f"[bold cyan]检测到 {len(analysis_results)} 个关键节点：[/bold cyan]\n")

        for i, result in enumerate(analysis_results, 1):
            # 生成建议
            advice = MagAdvisor.generate_advice(result)

            # 根据质量评级设置颜色
            quality = result['quality_rating']
            if quality == '优质':
                color = "green"
            elif quality == '一般':
                color = "yellow"
            else:
                color = "red"

            console.print(Panel(
                advice,
                title=f"[{color}]关键节点 #{i} - {result['coin']}[/{color}]",
                border_style=color
            ))
            console.print()

    # 显示特殊关键节点列表（仅当天）
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]特殊关键节点列表（当天）：[/bold cyan]")
    console.print("=" * 70 + "\n")

    # 获取当天日期
    latest_data = db.get_latest_date_data()
    if latest_data:
        current_date = latest_data[0]['date']

        # 获取所有特殊节点并过滤出当天的
        all_special_nodes = db.get_special_nodes(limit=100)
        special_nodes = [node for node in all_special_nodes if node['date'] == current_date]

        if special_nodes:
            # 按类型分组
            node_types_cn = {
                'approaching': '提示逼近',
                'quality_warning_entry': '进场期质量修正',
                'quality_warning_exit': '退场期质量修正',
                'break_above_200': '爆破指数超200',
                'offchain_above_1000': '场外指数超1000',
                'offchain_below_1000': '场外指数跌破1000'
            }

            for node in special_nodes:
                node_type_cn = node_types_cn.get(node['node_type'], node['node_type'])
                console.print(f"[cyan]{node['date']}[/cyan] - [yellow]{node['coin']}[/yellow] - {node_type_cn}")
                console.print(f"  {node['description']}")
                console.print()
        else:
            console.print(f"[dim]{current_date} 暂无特殊关键节点[/dim]\n")
    else:
        console.print("[dim]暂无数据[/dim]\n")

    # 显示数据概览
    console.print("\n[bold]数据概览：[/bold]")
    latest_data = db.get_latest_date_data()
    if latest_data:
        date = latest_data[0]['date']
        console.print(f"  日期: {date}")
        console.print(f"  币种数量: {len(latest_data)}")

        # 统计进退场
        enter_count = sum(1 for d in latest_data if d['phase_type'] == '进场期')
        exit_count = sum(1 for d in latest_data if d['phase_type'] == '退场期')
        console.print(f"  进场期: {enter_count} 个  |  退场期: {exit_count} 个")

    console.print("\n[dim]数据已保存至 mag_data.db[/dim]\n")


if __name__ == "__main__":
    main()
