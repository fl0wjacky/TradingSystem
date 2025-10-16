#!/usr/bin/env python3
"""
测试场景：进场期内多次跨越200的情况
"""
from src.database import MagDatabase
from src.analyzer import MagAnalyzer
from rich.console import Console

console = Console()

# 创建测试数据库
db = MagDatabase("test_multiple_break.db")
analyzer = MagAnalyzer(db)

console.print("\n[bold cyan]=" * 35)
console.print("[bold cyan]测试场景：进场期内多次跌破200[/bold cyan]")
console.print("[bold cyan]=" * 35 + "\n")

# 构造测试数据
test_data = [
    # 进场期第1天 - 节点1
    {
        'date': '2025-10-01',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 1,
        'offchain_index': 900,
        'break_index': 150,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    # 进场期第2-4天，爆破上升
    {
        'date': '2025-10-02',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 2,
        'offchain_index': 950,
        'break_index': 180,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    {
        'date': '2025-10-03',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 3,
        'offchain_index': 1000,
        'break_index': 210,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    {
        'date': '2025-10-04',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 4,
        'offchain_index': 1050,
        'break_index': 250,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    # 进场期第5天，首次跌破200 - 节点2
    {
        'date': '2025-10-05',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 5,
        'offchain_index': 1020,
        'break_index': 180,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    # 进场期第6-8天，爆破再次上升
    {
        'date': '2025-10-06',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 6,
        'offchain_index': 1060,
        'break_index': 190,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    {
        'date': '2025-10-07',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 7,
        'offchain_index': 1100,
        'break_index': 215,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    {
        'date': '2025-10-08',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 8,
        'offchain_index': 1120,
        'break_index': 230,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
    # 进场期第9天，第二次跌破200 - 节点3
    {
        'date': '2025-10-09',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 9,
        'offchain_index': 1090,
        'break_index': 190,
        'shelin_point': None,
        'is_dragon_leader': 0,
        'is_us_stock': 0
    },
]

# 录入测试数据
console.print("[yellow]正在录入测试数据...[/yellow]\n")
for data in test_data:
    db.insert_or_update_coin_data(data)
    console.print(f"  {data['date']}: 进场期第{data['phase_days']}天, 场外={data['offchain_index']}, 爆破={data['break_index']}")

console.print("\n[green]✓ 测试数据录入完成[/green]\n")

# 分析3个关键节点
console.print("[bold cyan]" + "=" * 70)
console.print("[bold cyan]分析结果：[/bold cyan]")
console.print("[bold cyan]" + "=" * 70 + "\n")

# 节点1: 进场期第1天
console.print("[bold yellow]节点1: 2025-10-01 - 进场期第1天[/bold yellow]")
result1 = analyzer.analyze_coin('TEST', '2025-10-01')
if result1:
    console.print(f"  参考节点: {result1['reference_node_date']}")
    console.print(f"  参考场外指数: {result1['reference_offchain_index']}")
    console.print(f"  当前场外指数: {result1['current_offchain_index']}")
    console.print(f"  涨幅: {result1['final_percentage']:.1f}%")
    console.print(f"  质量: {result1['quality_rating']}")
else:
    console.print("  [red]未检测到关键节点（可能缺少历史数据）[/red]")

console.print()

# 节点2: 首次跌破200
console.print("[bold yellow]节点2: 2025-10-05 - 首次跌破200[/bold yellow]")
console.print("  期望: 应该与节点1(10-01)对比，展示第1小节质量")
result2 = analyzer.analyze_coin('TEST', '2025-10-05')
if result2:
    console.print(f"  参考节点: {result2['reference_node_date']}")
    console.print(f"  参考场外指数: {result2['reference_offchain_index']:.0f}")
    console.print(f"  当前场外指数: {result2['current_offchain_index']}")
    console.print(f"  涨幅: {result2['final_percentage']:.1f}%")
    console.print(f"  质量: {result2['quality_rating']}")

    if result2['reference_node_date'] == '2025-10-01':
        console.print("  [green]✓ 正确！与进场期第1天对比[/green]")
    else:
        console.print(f"  [red]✗ 错误！应该与2025-10-01对比，实际与{result2['reference_node_date']}对比[/red]")
else:
    console.print("  [red]未检测到关键节点[/red]")

console.print()

# 节点3: 第二次跌破200
console.print("[bold yellow]节点3: 2025-10-09 - 第二次跌破200[/bold yellow]")
console.print("  期望: 应该与节点2(10-05)对比，展示第2小节质量")
result3 = analyzer.analyze_coin('TEST', '2025-10-09')
if result3:
    console.print(f"  参考节点: {result3['reference_node_date']}")
    console.print(f"  参考场外指数: {result3['reference_offchain_index']:.0f}")
    console.print(f"  当前场外指数: {result3['current_offchain_index']}")
    console.print(f"  涨幅: {result3['final_percentage']:.1f}%")
    console.print(f"  质量: {result3['quality_rating']}")

    if result3['reference_node_date'] == '2025-10-05':
        console.print("  [green]✓ 正确！与首次跌破200对比[/green]")
    else:
        console.print(f"  [red]✗ 错误！应该与2025-10-05对比，实际与{result3['reference_node_date']}对比[/red]")
else:
    console.print("  [red]未检测到关键节点[/red]")

console.print("\n" + "=" * 70)
console.print("[bold green]测试完成！[/bold green]")
console.print("=" * 70 + "\n")

# 清理
import os
if os.path.exists("test_multiple_break.db"):
    os.remove("test_multiple_break.db")
    console.print("[dim]已清理测试数据库[/dim]\n")
