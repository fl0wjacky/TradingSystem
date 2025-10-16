#!/usr/bin/env python3
"""
测试逼近修正功能
"""
from src.database import MagDatabase
from src.analyzer import MagAnalyzer
from src.advisor import MagAdvisor

def test_approaching_detection():
    """测试逼近关键字检测"""
    from src.notion_scraper import NotionScraper

    # 测试文本1: 包含逼近关键字 (使用格式1)
    test_text1 = """10.16
BTC 场外指数1200场外进场期第1天
爆破指数250
逼近
"""

    scraper = NotionScraper("")
    try:
        data_list1 = scraper.parse_data(test_text1)
        print("=== 测试1: 包含逼近关键字 ===")
        print(f"解析的币种: {data_list1[0]['coin']}")
        print(f"检测到 is_approaching: {data_list1[0].get('is_approaching')}")
        assert data_list1[0].get('is_approaching') == 1, f"应该检测到逼近关键字, 但检测值为 {data_list1[0].get('is_approaching')}"
        print("✓ 逼近关键字检测成功\n")
    except Exception as e:
        print(f"测试1失败: {e}\n")
        # 尝试格式2
        test_text1b = """10.16
BTC
场外指数1200
爆破指数250
场外进场期第1天
逼近
"""
        data_list1 = scraper.parse_data(test_text1b)
        print("=== 测试1b: 包含逼近关键字 (格式3) ===")
        print(f"解析的币种: {data_list1[0]['coin']}")
        print(f"检测到 is_approaching: {data_list1[0].get('is_approaching')}")
        assert data_list1[0].get('is_approaching') == 1, f"应该检测到逼近关键字, 但检测值为 {data_list1[0].get('is_approaching')}"
        print("✓ 逼近关键字检测成功\n")

    # 测试文本2: 不包含逼近关键字
    test_text2 = """10.16
BTC
场外指数1200
爆破指数250
场外进场期第1天
"""

    data_list2 = scraper.parse_data(test_text2)

    print("=== 测试2: 不包含逼近关键字 ===")
    print(f"解析的币种: {data_list2[0]['coin']}")
    print(f"检测到 is_approaching: {data_list2[0].get('is_approaching')}")
    assert data_list2[0].get('is_approaching') == 0, "不应该检测到逼近关键字"
    print("✓ 无逼近关键字检测成功\n")


def test_approaching_correction():
    """测试逼近修正计算"""
    db = MagDatabase()
    analyzer = MagAnalyzer(db)
    advisor = MagAdvisor()

    # 先插入一个参考节点（2025-10-15，进场期第1天，无逼近）
    ref_data = {
        'date': '2025-10-15',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 1,
        'offchain_index': 1000,
        'break_index': 250,
        'is_dragon_leader': 0,
        'is_us_stock': 0,
        'is_approaching': 0
    }
    db.insert_or_update_coin_data(ref_data)

    # 插入当前节点（2025-10-16，爆破指数跌破200，有逼近）
    # 前一天爆破指数>200, 今天<200
    prev_data = {
        'date': '2025-10-16',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 2,
        'offchain_index': 1050,
        'break_index': 210,
        'is_dragon_leader': 0,
        'is_us_stock': 0,
        'is_approaching': 0
    }
    db.insert_or_update_coin_data(prev_data)

    current_data = {
        'date': '2025-10-17',
        'coin': 'TEST',
        'phase_type': '进场期',
        'phase_days': 3,
        'offchain_index': 1100,
        'break_index': 180,
        'is_dragon_leader': 0,
        'is_us_stock': 0,
        'is_approaching': 1  # 有逼近标记
    }
    db.insert_or_update_coin_data(current_data)

    # 分析
    result = analyzer.analyze_coin('TEST', '2025-10-17')

    print("=== 测试3: 逼近修正计算 ===")
    if result:
        print(f"币种: {result['coin']}")
        print(f"日期: {result['date']}")
        print(f"节点类型: {result['node_type']}")
        print(f"基础涨幅: {result['change_percentage']:.1f}%")
        print(f"逼近修正: {result.get('approaching_correction', 0):.1f}%")
        print(f"最终百分比: {result['final_percentage']:.1f}%")
        print()

        # 验证逼近修正
        assert result.get('approaching_correction', 0) == -5, "逼近修正应该是-5%"
        print("✓ 逼近修正应用成功\n")

        # 显示完整建议
        print("=== 完整分析结果 ===")
        advice = advisor.generate_advice(result)
        print(advice)
    else:
        print("未检测到关键节点")

    # 清理测试数据
    db.delete_analysis_results('2025-10-15', '2025-10-17')


if __name__ == "__main__":
    print("开始测试逼近修正功能...\n")

    try:
        # 测试1: 逼近关键字检测
        test_approaching_detection()

        # 测试2: 逼近修正计算
        test_approaching_correction()

        print("\n✅ 所有测试通过！")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
