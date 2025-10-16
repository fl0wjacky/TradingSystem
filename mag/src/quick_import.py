#!/usr/bin/env python3
"""
快捷手工录入工具
适用于 Claude Code 环境，不需要交互式输入

使用方法：
  直接编辑脚本中的 data_to_import 列表，然后运行
"""
from src.database import MagDatabase
from rich.console import Console
from rich.table import Table

console = Console()

# ===================================================================
# 在这里编辑要录入的数据
# ===================================================================
data_to_import = [
    # 示例1: BTC
    {
        'date': '2025-10-03',
        'coin': 'BTC',
        'phase_type': '进场期',
        'phase_days': 2,
        'offchain_index': 1180,
        'break_index': 240,
        'shelin_point': None,  # 可选，没有就填 None
        'is_dragon_leader': 0,  # 1=龙头币，0=非龙头币
        'is_us_stock': 0        # 1=美股，0=非美股
    },
    # 示例2: ETH
    {
        'date': '2025-10-03',
        'coin': 'ETH',
        'phase_type': '进场期',
        'phase_days': 2,
        'offchain_index': 1070,
        'break_index': 185,
        'shelin_point': 3850,
        'is_dragon_leader': 1,
        'is_us_stock': 0
    },
    # 继续添加更多数据...
]
# ===================================================================

def main():
    db = MagDatabase()

    console.print("\n[bold cyan]═══════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]  Mag 快捷录入工具[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]\n")

    if not data_to_import:
        console.print("[yellow]⚠️  data_to_import 列表为空，请先编辑脚本添加数据[/yellow]")
        return

    # 显示将要录入的数据
    table = Table(title="待录入数据", show_header=True, header_style="bold magenta")
    table.add_column("日期", style="cyan")
    table.add_column("币种", style="green")
    table.add_column("相位", style="yellow")
    table.add_column("场外指数", justify="right")
    table.add_column("爆破指数", justify="right")

    for data in data_to_import:
        table.add_row(
            data['date'],
            data['coin'],
            f"{data['phase_type']}第{data['phase_days']}天",
            str(data['offchain_index']),
            str(data['break_index'])
        )

    console.print(table)
    console.print()

    # 开始录入
    success_count = 0
    for data in data_to_import:
        try:
            db.insert_or_update_coin_data(data)
            console.print(f"[green]✓[/green] 已录入: {data['date']} - {data['coin']}")
            success_count += 1
        except Exception as e:
            console.print(f"[red]✗[/red] 录入失败: {data['date']} - {data['coin']}: {e}")

    console.print(f"\n[bold green]录入完成！[/bold green] 成功录入 [bold]{success_count}[/bold] 条数据\n")

    # 提示后续操作
    console.print("[bold cyan]后续操作：[/bold cyan]")
    console.print("  1. 查看数据: [yellow]sqlite3 mag_data.db 'SELECT * FROM coin_daily_data ORDER BY date DESC LIMIT 10'[/yellow]")
    console.print("  2. 分析数据: [yellow]python3 mag_reanalyze.py <日期>[/yellow]")
    console.print("  3. 或直接运行: [yellow]python3 mag_system.py[/yellow]\n")

if __name__ == "__main__":
    main()
