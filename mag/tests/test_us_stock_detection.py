#!/usr/bin/env python3
"""
测试美股识别逻辑
"""
from src.notion_scraper import NotionScraper

def test_us_stock_section():
    """测试美股区标志检测"""

    # 测试1: 大宗$美股区后的标的应该被识别为美股
    test_text1 = """10.16
大宗$美股区
COIN
场外指数1200
爆破指数250
场外进场期第1天

HOOD
场外指数1100
爆破指数230
场外进场期第2天
"""

    scraper = NotionScraper("")
    data_list1 = scraper.parse_data(test_text1)

    print("=== 测试1: 美股区标志检测 ===")
    for data in data_list1:
        print(f"{data['coin']}: is_us_stock={data['is_us_stock']}")
        assert data['is_us_stock'] == 1, f"{data['coin']} 应该被标记为美股"
    print("✓ 美股区标志检测成功\n")


def test_exact_match():
    """测试完全匹配逻辑"""

    # 测试2: AAVE不应该被识别为美股（虽然包含AA）
    test_text2 = """10.16
AAVE
场外指数1200
爆破指数250
场外进场期第1天
"""

    scraper = NotionScraper("")
    data_list2 = scraper.parse_data(test_text2)

    print("=== 测试2: 完全匹配逻辑 ===")
    print(f"AAVE: is_us_stock={data_list2[0]['is_us_stock']}")
    assert data_list2[0]['is_us_stock'] == 0, "AAVE 不应该被标记为美股"
    print("✓ AAVE 正确识别为非美股\n")


def test_aapl_exact_match():
    """测试AAPL完全匹配"""

    # 测试3: AAPL应该被识别为美股
    test_text3 = """10.16
AAPL
场外指数1200
爆破指数250
场外进场期第1天
"""

    scraper = NotionScraper("")
    data_list3 = scraper.parse_data(test_text3)

    print("=== 测试3: AAPL完全匹配 ===")
    print(f"AAPL: is_us_stock={data_list3[0]['is_us_stock']}")
    assert data_list3[0]['is_us_stock'] == 1, "AAPL 应该被标记为美股"
    print("✓ AAPL 正确识别为美股\n")


def test_mixed_section():
    """测试混合区域"""

    # 测试4: 美股区后有其他区域
    test_text4 = """10.16
大宗$美股区
COIN
场外指数1200
爆破指数250
场外进场期第1天

大宗其他区
BTC
场外指数1100
爆破指数230
场外进场期第2天
"""

    scraper = NotionScraper("")
    data_list4 = scraper.parse_data(test_text4)

    print("=== 测试4: 混合区域 ===")
    for data in data_list4:
        print(f"{data['coin']}: is_us_stock={data['is_us_stock']}")

    assert data_list4[0]['coin'] == 'COIN' and data_list4[0]['is_us_stock'] == 1, "COIN 应该被标记为美股"
    assert data_list4[1]['coin'] == 'BTC' and data_list4[1]['is_us_stock'] == 0, "BTC 不应该被标记为美股"
    print("✓ 混合区域检测成功\n")


if __name__ == "__main__":
    print("开始测试美股识别逻辑...\n")

    try:
        test_us_stock_section()
        test_exact_match()
        test_aapl_exact_match()
        test_mixed_section()

        print("\n✅ 所有测试通过！")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
