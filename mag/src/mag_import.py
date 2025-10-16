#!/usr/bin/env python3
"""
Mag数据导入工具
支持手动录入和批量导入
"""
import sys
import csv
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from rich.panel import Panel

from src.database import MagDatabase
from src.notion_scraper import NotionScraper

console = Console()


def manual_input():
    """手动录入单条数据"""
    console.print(Panel.fit(
        "[bold cyan]Mag 手动录入工具[/bold cyan]\n"
        "[dim]请按提示输入币种数据[/dim]",
        border_style="cyan"
    ))

    try:
        # 输入日期
        date_str = Prompt.ask("\n[cyan]日期[/cyan] (格式: 2025-10-14)", default=datetime.now().strftime("%Y-%m-%d"))

        # 输入币种
        coin = Prompt.ask("[cyan]币种名称[/cyan] (如: BTC, ETH)").upper()

        # 输入场外指数
        offchain_index = IntPrompt.ask("[cyan]场外指数[/cyan]")

        # 输入爆破指数
        break_index = IntPrompt.ask("[cyan]爆破指数[/cyan] (可为负数)")

        # 输入进退场期类型
        phase_type = Prompt.ask("[cyan]进退场期[/cyan]", choices=["进场期", "退场期"])

        # 输入天数
        phase_days = IntPrompt.ask(f"[cyan]{phase_type}第几天[/cyan]")

        # 可选：谢林点
        shelin_input = Prompt.ask("[cyan]谢林点[/cyan] (可选，直接回车跳过)", default="")
        shelin_point = float(shelin_input) if shelin_input else None

        # 可选：是否龙头币
        is_dragon = Prompt.ask("[cyan]是否龙头币[/cyan]", choices=["y", "n"], default="n")
        is_dragon_leader = 1 if is_dragon == "y" else 0

        # 可选：是否美股
        is_stock = Prompt.ask("[cyan]是否美股[/cyan]", choices=["y", "n"], default="n")
        is_us_stock = 1 if is_stock == "y" else 0

        # 构建数据
        coin_data = {
            'date': date_str,
            'coin': coin,
            'phase_type': phase_type,
            'phase_days': phase_days,
            'offchain_index': offchain_index,
            'break_index': break_index,
            'shelin_point': shelin_point,
            'is_dragon_leader': is_dragon_leader,
            'is_us_stock': is_us_stock
        }

        # 显示预览
        console.print("\n[bold]数据预览：[/bold]")
        table = Table(show_header=True)
        table.add_column("字段")
        table.add_column("值")
        for key, value in coin_data.items():
            table.add_row(key, str(value))
        console.print(table)

        # 确认保存
        confirm = Prompt.ask("\n[yellow]确认保存?[/yellow]", choices=["y", "n"], default="y")
        if confirm == "y":
            db = MagDatabase()
            db.insert_or_update_coin_data(coin_data)
            console.print(f"\n[green]✓[/green] 数据已保存！")

            # 询问是否继续录入
            continue_input = Prompt.ask("[cyan]继续录入?[/cyan]", choices=["y", "n"], default="n")
            if continue_input == "y":
                manual_input()
        else:
            console.print("[yellow]已取消[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]已取消录入[/yellow]")
    except Exception as e:
        console.print(f"\n[red]错误: {str(e)}[/red]")


def batch_import_csv(csv_file: str):
    """从CSV文件批量导入"""
    console.print(f"[cyan]正在导入 CSV 文件: {csv_file}[/cyan]")

    try:
        db = MagDatabase()
        imported = 0
        errors = []

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # 从第2行开始（第1行是标题）
                try:
                    coin_data = {
                        'date': row['date'],
                        'coin': row['coin'].upper(),
                        'phase_type': row['phase_type'],
                        'phase_days': int(row['phase_days']),
                        'offchain_index': int(row['offchain_index']),
                        'break_index': int(row['break_index']),
                        'shelin_point': float(row['shelin_point']) if row.get('shelin_point') and row['shelin_point'] else None,
                        'is_dragon_leader': int(row.get('is_dragon_leader', 0)),
                        'is_us_stock': int(row.get('is_us_stock', 0))
                    }

                    db.insert_or_update_coin_data(coin_data)
                    imported += 1
                    console.print(f"[dim]第{row_num}行: {coin_data['coin']} - 成功[/dim]")

                except Exception as e:
                    errors.append(f"第{row_num}行: {str(e)}")

        console.print(f"\n[green]✓[/green] 成功导入 {imported} 条数据")
        if errors:
            console.print(f"[yellow]⚠[/yellow] {len(errors)} 条数据导入失败：")
            for err in errors[:5]:  # 只显示前5个错误
                console.print(f"  [red]{err}[/red]")

    except FileNotFoundError:
        console.print(f"[red]错误：文件不存在 - {csv_file}[/red]")
    except Exception as e:
        console.print(f"[red]错误: {str(e)}[/red]")


def batch_import_json(json_file: str):
    """从JSON文件批量导入"""
    console.print(f"[cyan]正在导入 JSON 文件: {json_file}[/cyan]")

    try:
        db = MagDatabase()
        imported = 0
        errors = []

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 支持两种格式：
        # 1. 数组格式：[{coin_data}, {coin_data}, ...]
        # 2. 对象格式：{date: [{coin_data}, ...]}

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = []
            for date_key, coins in data.items():
                if isinstance(coins, list):
                    items.extend(coins)
        else:
            raise Exception("不支持的JSON格式")

        for idx, item in enumerate(items, start=1):
            try:
                coin_data = {
                    'date': item['date'],
                    'coin': item['coin'].upper(),
                    'phase_type': item['phase_type'],
                    'phase_days': int(item['phase_days']),
                    'offchain_index': int(item['offchain_index']),
                    'break_index': int(item['break_index']),
                    'shelin_point': float(item['shelin_point']) if item.get('shelin_point') else None,
                    'is_dragon_leader': int(item.get('is_dragon_leader', 0)),
                    'is_us_stock': int(item.get('is_us_stock', 0))
                }

                db.insert_or_update_coin_data(coin_data)
                imported += 1
                console.print(f"[dim]第{idx}条: {coin_data['coin']} - 成功[/dim]")

            except Exception as e:
                errors.append(f"第{idx}条: {str(e)}")

        console.print(f"\n[green]✓[/green] 成功导入 {imported} 条数据")
        if errors:
            console.print(f"[yellow]⚠[/yellow] {len(errors)} 条数据导入失败：")
            for err in errors[:5]:
                console.print(f"  [red]{err}[/red]")

    except FileNotFoundError:
        console.print(f"[red]错误：文件不存在 - {json_file}[/red]")
    except json.JSONDecodeError:
        console.print(f"[red]错误：JSON格式错误[/red]")
    except Exception as e:
        console.print(f"[red]错误: {str(e)}[/red]")


def create_csv_template():
    """创建CSV模板文件"""
    template_file = "mag_import_template.csv"

    with open(template_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'coin', 'phase_type', 'phase_days', 'offchain_index',
                        'break_index', 'shelin_point', 'is_dragon_leader', 'is_us_stock'])
        writer.writerow(['2025-10-14', 'BTC', '退场期', '4', '682', '31', '110000', '0', '0'])
        writer.writerow(['2025-10-14', 'ETH', '退场期', '4', '613', '25', '3900', '1', '0'])

    console.print(f"[green]✓[/green] CSV模板已创建: {template_file}")


def create_json_template():
    """创建JSON模板文件"""
    template_file = "mag_import_template.json"

    template_data = [
        {
            "date": "2025-10-14",
            "coin": "BTC",
            "phase_type": "退场期",
            "phase_days": 4,
            "offchain_index": 682,
            "break_index": 31,
            "shelin_point": 110000.0,
            "is_dragon_leader": 0,
            "is_us_stock": 0
        },
        {
            "date": "2025-10-14",
            "coin": "ETH",
            "phase_type": "退场期",
            "phase_days": 4,
            "offchain_index": 613,
            "break_index": 25,
            "shelin_point": 3900.0,
            "is_dragon_leader": 1,
            "is_us_stock": 0
        }
    ]

    with open(template_file, 'w', encoding='utf-8') as f:
        json.dump(template_data, f, ensure_ascii=False, indent=2)

    console.print(f"[green]✓[/green] JSON模板已创建: {template_file}")


def batch_import_html(html_file: str):
    """从浮墨笔记 HTML 导出文件批量导入"""
    console.print(f"[cyan]正在导入浮墨笔记 HTML 文件: {html_file}[/cyan]")

    try:
        # 读取 HTML 文件
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 解析 HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # 查找所有 memo 块
        memo_blocks = soup.find_all('div', class_='memo')
        console.print(f"[dim]找到 {len(memo_blocks)} 条笔记[/dim]")

        db = MagDatabase()
        scraper = NotionScraper("")  # 只用于解析,不需要 URL

        total_imported = 0
        total_errors = []
        memo_count = 0

        for memo in memo_blocks:
            try:
                # 提取时间戳
                time_div = memo.find('div', class_='time')
                if not time_div:
                    continue

                timestamp = time_div.get_text(strip=True)

                # 提取内容
                content_div = memo.find('div', class_='content')
                if not content_div:
                    continue

                # 获取所有 <p> 标签的文本
                paragraphs = content_div.find_all('p')
                text_lines = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]

                # 检查是否包含 #Mag 标签
                if not text_lines or '#Mag' not in text_lines[0]:
                    continue

                memo_count += 1

                # 查找日期行(如 "10.14")
                date_line = None
                for line in text_lines[1:5]:  # 日期通常在前几行
                    if re.match(r'^\d{1,2}\.\d{1,2}$', line):
                        date_line = line
                        break

                if not date_line:
                    console.print(f"[yellow]警告: 笔记 {timestamp} 未找到日期行[/yellow]")
                    continue

                # 拼接所有文本内容
                raw_data = '\n'.join(text_lines)

                # 使用现有的解析器解析数据
                coin_data_list = scraper.parse_data(raw_data)

                if coin_data_list:
                    console.print(f"\n[cyan]笔记时间: {timestamp}[/cyan]")
                    console.print(f"[dim]解析到 {len(coin_data_list)} 个币种[/dim]")

                    # 导入数据
                    for coin_data in coin_data_list:
                        try:
                            db.insert_or_update_coin_data(coin_data)
                            total_imported += 1
                            console.print(f"  [dim]{coin_data['date']} - {coin_data['coin']} - 成功[/dim]")
                        except Exception as e:
                            error_msg = f"{coin_data.get('date', '?')} - {coin_data.get('coin', '?')}: {str(e)}"
                            total_errors.append(error_msg)
                else:
                    console.print(f"[yellow]警告: 笔记 {timestamp} ({date_line}) 未解析到数据[/yellow]")

            except Exception as e:
                total_errors.append(f"笔记解析失败: {str(e)}")

        console.print(f"\n[green]✓[/green] 处理了 {memo_count} 条 #Mag 笔记")
        console.print(f"[green]✓[/green] 成功导入 {total_imported} 条币种数据")

        if total_errors:
            console.print(f"\n[yellow]⚠[/yellow] {len(total_errors)} 条数据导入失败：")
            for err in total_errors[:10]:  # 只显示前10个错误
                console.print(f"  [red]{err}[/red]")
            if len(total_errors) > 10:
                console.print(f"  [dim]... 还有 {len(total_errors) - 10} 个错误[/dim]")

    except FileNotFoundError:
        console.print(f"[red]错误：文件不存在 - {html_file}[/red]")
    except Exception as e:
        console.print(f"[red]错误: {str(e)}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


def main():
    """主入口"""
    if len(sys.argv) < 2:
        console.print("""
[bold cyan]Mag 数据导入工具[/bold cyan]

用法:
  python3 mag_import.py manual              # 手动录入
  python3 mag_import.py csv <file.csv>      # CSV批量导入
  python3 mag_import.py json <file.json>    # JSON批量导入
  python3 mag_import.py html <file.html>    # 浮墨笔记HTML导入
  python3 mag_import.py template csv        # 创建CSV模板
  python3 mag_import.py template json       # 创建JSON模板

示例:
  python3 mag_import.py manual
  python3 mag_import.py csv data.csv
  python3 mag_import.py json data.json
  python3 mag_import.py html flow的笔记.html
  python3 mag_import.py template csv
        """)
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "manual":
        manual_input()

    elif command == "csv":
        if len(sys.argv) < 3:
            console.print("[red]错误：请指定CSV文件路径[/red]")
            sys.exit(1)
        batch_import_csv(sys.argv[2])

    elif command == "json":
        if len(sys.argv) < 3:
            console.print("[red]错误：请指定JSON文件路径[/red]")
            sys.exit(1)
        batch_import_json(sys.argv[2])

    elif command == "html":
        if len(sys.argv) < 3:
            console.print("[red]错误：请指定HTML文件路径[/red]")
            sys.exit(1)
        batch_import_html(sys.argv[2])

    elif command == "template":
        if len(sys.argv) < 3:
            console.print("[red]错误：请指定模板类型 (csv/json)[/red]")
            sys.exit(1)
        format_type = sys.argv[2].lower()
        if format_type == "csv":
            create_csv_template()
        elif format_type == "json":
            create_json_template()
        else:
            console.print("[red]错误：不支持的模板类型，请使用 csv 或 json[/red]")

    else:
        console.print(f"[red]错误：未知命令 '{command}'[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
