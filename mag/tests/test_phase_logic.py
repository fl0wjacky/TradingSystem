#!/usr/bin/env python3
"""
测试进退场期的基础涨幅和相变修正逻辑
"""
from src.analyzer import MagAnalyzer
from src.database import MagDatabase

def test_enter_phase_logic():
    """测试进场期逻辑"""
    db = MagDatabase()
    analyzer = MagAnalyzer(db)

    print("=== 测试1: 进场期基础涨幅 ===")

    # 场外指数从1000变到1100，涨幅应为+10%
    change1, corr1 = analyzer._calculate_change_percentage(1000, 1100, '进场期')
    print(f"进场期 1000→1100: 基础涨幅={change1:.1f}%, 相变修正={corr1:.1f}%")
    assert abs(change1 - 10.0) < 0.01, f"应为+10%, 实际为{change1:.1f}%"
    assert corr1 == 0, "不跨越1000，相变修正应为0"

    # 场外指数从1100变到1000，涨幅应为-9.09%
    change2, corr2 = analyzer._calculate_change_percentage(1100, 1000, '进场期')
    print(f"进场期 1100→1000: 基础涨幅={change2:.1f}%, 相变修正={corr2:.1f}%")
    assert change2 < 0, "应为负值"
    assert corr2 == 0, "不跨越1000，相变修正应为0"

    print("✓ 进场期基础涨幅测试通过\n")


def test_exit_phase_logic():
    """测试退场期逻辑"""
    db = MagDatabase()
    analyzer = MagAnalyzer(db)

    print("=== 测试2: 退场期基础涨幅 ===")

    # 场外指数从1000变到1100，涨幅应为-10%（反向）
    change1, corr1 = analyzer._calculate_change_percentage(1000, 1100, '退场期')
    print(f"退场期 1000→1100: 基础涨幅={change1:.1f}%, 相变修正={corr1:.1f}%")
    assert abs(change1 - (-10.0)) < 0.01, f"应为-10%, 实际为{change1:.1f}%"
    assert corr1 == 0, "不跨越1000，相变修正应为0"

    # 场外指数从1100变到1000，涨幅应为+9.09%（反向）
    change2, corr2 = analyzer._calculate_change_percentage(1100, 1000, '退场期')
    print(f"退场期 1100→1000: 基础涨幅={change2:.1f}%, 相变修正={corr2:.1f}%")
    assert change2 > 0, "应为正值"
    assert corr2 == 0, "不跨越1000，相变修正应为0"

    print("✓ 退场期基础涨幅测试通过\n")


def test_enter_phase_correction():
    """测试进场期相变修正"""
    db = MagDatabase()
    analyzer = MagAnalyzer(db)

    print("=== 测试3: 进场期相变修正 ===")

    # 从900→1100，跨越1000向上，应+5%
    change1, corr1 = analyzer._calculate_change_percentage(900, 1100, '进场期')
    print(f"进场期 900→1100: 基础涨幅={change1:.1f}%, 相变修正={corr1:.1f}%")
    assert abs(change1 - 22.22) < 0.1, "基础涨幅计算错误"
    assert corr1 == 5, f"跨越1000向上，应为+5%, 实际为{corr1:.1f}%"

    # 从1100→900，跨越1000向下，应-5%
    change2, corr2 = analyzer._calculate_change_percentage(1100, 900, '进场期')
    print(f"进场期 1100→900: 基础涨幅={change2:.1f}%, 相变修正={corr2:.1f}%")
    assert change2 < 0, "基础涨幅应为负"
    assert corr2 == -5, f"跨越1000向下，应为-5%, 实际为{corr2:.1f}%"

    print("✓ 进场期相变修正测试通过\n")


def test_exit_phase_correction():
    """测试退场期相变修正"""
    db = MagDatabase()
    analyzer = MagAnalyzer(db)

    print("=== 测试4: 退场期相变修正 ===")

    # 从900→1100，跨越1000向上，应-5%（退场期反向）
    change1, corr1 = analyzer._calculate_change_percentage(900, 1100, '退场期')
    print(f"退场期 900→1100: 基础涨幅={change1:.1f}%, 相变修正={corr1:.1f}%")
    assert change1 < 0, "退场期基础涨幅应为负（反向）"
    assert corr1 == -5, f"退场期跨越1000向上，应为-5%, 实际为{corr1:.1f}%"

    # 从1100→900，跨越1000向下，应+5%（退场期反向）
    change2, corr2 = analyzer._calculate_change_percentage(1100, 900, '退场期')
    print(f"退场期 1100→900: 基础涨幅={change2:.1f}%, 相变修正={corr2:.1f}%")
    assert change2 > 0, "退场期基础涨幅应为正（反向）"
    assert corr2 == 5, f"退场期跨越1000向下，应为+5%, 实际为{corr2:.1f}%"

    print("✓ 退场期相变修正测试通过\n")


if __name__ == "__main__":
    print("开始测试进退场期逻辑...\n")

    try:
        test_enter_phase_logic()
        test_exit_phase_logic()
        test_enter_phase_correction()
        test_exit_phase_correction()

        print("\n✅ 所有测试通过！")
        print("\n总结规则:")
        print("1. 进场期：场外指数↑→涨幅为正，场外指数↓→涨幅为负")
        print("2. 退场期：场外指数↑→涨幅为负，场外指数↓→涨幅为正（完全相反）")
        print("3. 进场期相变：<1000→>=1000 +5%，>=1000→<1000 -5%")
        print("4. 退场期相变：<1000→>=1000 -5%，>=1000→<1000 +5%（完全相反）")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
