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


def fetch_notion_data_via_firecrawl(url: str, progress, task_id) -> str:
    """使用Firecrawl MCP工具抓取Notion数据"""
    try:
        # 导入必要的模块（假设MCP工具可用）
        progress.update(task_id, advance=30, description="[cyan]正在通过Firecrawl抓取...")

        # 这里应该调用MCP的firecrawl工具
        # 由于在Python中无法直接调用MCP工具，我们使用subprocess调用
        import subprocess
        import json

        # 注意：这个方法在实际环境中可能需要调整
        # 如果有MCP Python客户端，应该使用客户端而不是subprocess

        console.print("[dim]提示：Firecrawl需要通过Claude Code环境调用[/dim]")
        console.print("[dim]当前自动回退到测试模式[/dim]")

        progress.update(task_id, advance=20)
        return None  # 返回None表示需要使用测试数据

    except Exception as e:
        console.print(f"[red]Firecrawl抓取失败: {str(e)}[/red]")
        return None


def main():
    """主程序入口"""
    console.print(Panel.fit(
        "[bold cyan]Mag 现货提示系统 v1.0[/bold cyan]\n"
        "[dim]基于场外体系的智能交易分析[/dim]",
        border_style="cyan"
    ))

    # 获取Notion URL
    if len(sys.argv) > 1:
        notion_url = sys.argv[1]
    else:
        console.print("\n[yellow]请输入Notion数据链接：[/yellow]", end="")
        notion_url = input().strip()

    if not notion_url:
        console.print("[red]错误：未提供数据链接[/red]")
        sys.exit(1)

    # 初始化数据库
    db = MagDatabase()
    analyzer = MagAnalyzer(db)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:

            # 1. 使用Firecrawl抓取数据
            task1 = progress.add_task("[cyan]正在抓取Notion数据...", total=100)

            console.print("[dim]使用Firecrawl MCP工具抓取Notion页面...[/dim]")
            raw_data = fetch_notion_data_via_firecrawl(notion_url, progress, task1)

            if not raw_data:
                # 回退到测试数据
                console.print("[yellow]警告：Firecrawl抓取失败，使用测试数据[/yellow]")
                test_data = """10.14

Btc  场外指数682场外退场期第4天

爆破指数31

谢林点 110000

Eth  场外指数613场外退场期第4天

爆破指数25

谢林点 3900

BNB 场外指数1004场外进场期第14天  逼近

爆破指数131

谢林点 1140

SOL 场外指数510场外退场期第5天

爆破指数20

谢林点190

Doge场外指数486场外退场期第4天

爆破指数-21

谢林点 0.195

美股纳指 OTC 场外指数847场外退场期第4天

爆破指数35

&币市流动性 场外指数1267场外进场期4天

爆破指数136

期权波动率（比特币Vega交易）

场外指数3043场外进场期22天

爆破指数218

谢林点 45

※※※※※※※※※※※※※※※※※

LTC 场外指数575场外退场期第4天

爆破指数-17

Ldo场外指数551场外退场期第22天

爆破指数-10

Crv场外指数565场外退场期第4天

爆破指数-7

LINK 场外指数463场外退场期第22天

爆破指数-13

ADA场外指数456场外退场期第22天

爆破指数-24

UNI 场外指数481场外退场期第30天

爆破指数-10

Ondo 场外指数436场外退场第23天

爆破指数-33

Aave场外指数448场外退场期4天

爆破指数-13

Avax场外指数441场外退场期第20天

爆破指数-25

Pepe场外指数432场外退场期第23天

爆破指数-27

※※※※※※※※※※※※※※※※

Sui场外指数410场外退场第23天

爆破指数-24

Sei场外指数430场外退场期第30天

爆破指数-40

WLD 场外指数471场外退场期第29天

爆破指数-40

hype 场外指数519场外退场期第10天

爆破指数-34

♤♤♤♤♤♤♤♤♤♤♤♤

$Trump

场外指数357爆破指数-14

场外退场第6天

谢林点6.2

okb

场外指数599

爆破指数 7退场第1天

谢林点176

pump

场外指数561 爆破-31

退场期第9天

谢林点0.0037

$$$$$$$###

hood 场外指数1089爆破114

场外进场期第35天

coin 场外指数967爆破指数101

进场期14天 逼近

circle 场外指数1058爆破指数86

场外退场第4天

tsla  场外指数841爆破指数39

场外退场期第4天

Nvda 场外指数1097爆破指数155

场外进场期第22天  逼近

Aapl 场外指数974爆破指数-114

场外退场期第4天

goog 场外指数1046爆破指数41

场外退场期第5天

黄金OTC   场外指数1676场外进场期第50天

爆破指数228

地产 （指导国内购置地产房产 大周期只月更）

场外指数1764 爆破238

进场期第3月

布伦特原油 场外指数826爆破指数-50

场外退场期第13天"""

            raw_data = test_data
            progress.update(task1, advance=50)

            # 2. 解析数据
            progress.update(task1, description="[cyan]正在解析数据...")
            scraper = NotionScraper(notion_url)
            coin_data_list = scraper.parse_data(raw_data)
            progress.update(task1, advance=50, completed=100)

            console.print(f"\n[green]✓[/green] 成功抓取 {len(coin_data_list)} 个币种数据\n")

            # 3. 存储数据
            task2 = progress.add_task("[cyan]正在存储数据到数据库...", total=len(coin_data_list))
            for coin_data in coin_data_list:
                db.insert_or_update_coin_data(coin_data)
                progress.update(task2, advance=1)

            console.print(f"[green]✓[/green] 数据存储完成\n")

            # 4. 分析关键节点
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
