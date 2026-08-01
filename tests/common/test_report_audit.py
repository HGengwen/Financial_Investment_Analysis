#!/usr/bin/env python3
"""
研究报告数据抽检工具测试软件

测试目标：
    1. 数据点提取功能测试（Markdown 表格、KV 行、特殊格式）
    2. 随机抽样功能测试（比例、数量限制、可重复性）
    3. 准出/打回判决测试（通过、警告、不通过场景）
    4. 边界条件测试（空输入、异常数据、特殊字符）
    5. 辅助函数测试（数字清洗、标签验证、偏差计算）

运行方式：
    python tests/common/test_report_audit.py
"""

import sys
import os
import json
import tempfile
from decimal import Decimal

# 添加项目根目录到路径
# 本文件位于 tests/common/ 下，需向上 2 层到达项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.common.report_audit import (
    extract_data_points,
    sample_points,
    render_verdict,
    _clean_num,
    _is_valid_label,
    _pct_diff,
    _parse_md_tables,
)


# ============================================================
# 测试数据
# ============================================================

MOCK_REPORT_MD = """
# 腾讯控股投资研究报告

## 财务数据摘要

### 核心财务指标

| 指标         | 2024Q1  | 2023Q4  | 2023Q1  |
|-------------|---------|---------|---------|
| 营业收入(亿) | 1,595   | 1,554   | 1,500   |
| 净利润(亿)   | 426     | 394     | 258     |
| 毛利率       | 45%     | 43%     | 42%     |
| ROE         | 12.5%   | 11.8%   | 8.2%    |

### 估值指标

PE：18.8x
PB：3.5x
市值：~3.5万亿港元

收入：1,595亿元 ✅
  - macrotrends: 1,598亿元
  - stockanalysis: 1,592亿元
  - 误差: 0.3%

净利润：426亿元 ⚠️ 数据存在差异
  - macrotrends: 426亿元（GAAP）
  - stockanalysis: 450亿元（Non-GAAP）
  - 误差: 5.6% — 原因：会计口径不同

## 业务分析

游戏收入：42.5亿美元
金融科技：18.9亿美元
广告收入：15.6亿美元
"""

MOCK_VERDICT_RESULTS_PASS = [
    {
        "id": 1,
        "label": "营业收入",
        "reported_value": 1595,
        "unit": "亿",
        "fetched_value": 1598,
        "fetched_source": "macrotrends",
        "fetched_value2": 1592,
        "fetched_source2": "stockanalysis",
    },
    {
        "id": 2,
        "label": "净利润",
        "reported_value": 426,
        "unit": "亿",
        "fetched_value": 426,
        "fetched_source": "macrotrends",
    },
]

MOCK_VERDICT_RESULTS_FAIL = [
    {
        "id": 1,
        "label": "营业收入",
        "reported_value": 1595,
        "unit": "亿",
        "fetched_value": 1400,  # 偏差 >1%
        "fetched_source": "macrotrends",
        "fetched_value2": 1400,  # 第二来源也偏差 >1%
        "fetched_source2": "stockanalysis",
    },
    {
        "id": 2,
        "label": "净利润",
        "reported_value": 426,
        "unit": "亿",
        "fetched_value": 400,  # 偏差 >1%
        "fetched_source": "macrotrends",
        "fetched_value2": 400,  # 第二来源也偏差 >1%
        "fetched_source2": "stockanalysis",
    },
]

MOCK_VERDICT_RESULTS_WARN = [
    {
        "id": 1,
        "label": "营业收入",
        "reported_value": 1595,
        "unit": "亿",
        "fetched_value": 1598,  # 通过（偏差0.19%）
        "fetched_source": "macrotrends",
        "fetched_value2": 1500,  # 不通过（偏差5.96%）
        "fetched_source2": "stockanalysis",
    },
]


# ============================================================
# 测试函数
# ============================================================

def test_clean_num():
    """测试数字清洗功能"""
    print("\n" + "=" * 80)
    print("  测试 1: 数字清洗功能")
    print("=" * 80)

    test_cases = [
        ("1,595", 1595.0),
        ("1，595", 1595.0),  # 中文逗号
        ("42.5", 42.5),
        ("18.8x", None),  # 包含非数字字符
        ("", None),
        ("  ", None),
    ]

    passed = 0
    failed = 0

    for input_str, expected in test_cases:
        result = _clean_num(input_str)

        if expected is None:
            if result is None:
                print(f"  ✅ PASS: _clean_num('{input_str}') = None")
                passed += 1
            else:
                print(f"  ❌ FAIL: _clean_num('{input_str}') = {result} (期望: None)")
                failed += 1
        else:
            if result == expected:
                print(f"  ✅ PASS: _clean_num('{input_str}') = {result}")
                passed += 1
            else:
                print(f"  ❌ FAIL: _clean_num('{input_str}') = {result} (期望: {expected})")
                failed += 1

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_is_valid_label():
    """测试标签验证功能"""
    print("\n" + "=" * 80)
    print("  测试 2: 标签验证功能")
    print("=" * 80)

    valid_labels = [
        "营业收入",
        "净利润",
        "毛利率",
        "ROE",
        "市值",
        "PE Ratio",
    ]

    invalid_labels = [
        "",  # 空字符串
        "1",  # 太短
        "2024",  # 纯年份
        "+56%",  # 增速符号
        "**收入**",  # Markdown 标记
        "来源",  # 无意义标签
        "备注",  # 无意义标签
    ]

    passed = 0
    failed = 0

    for label in valid_labels:
        if _is_valid_label(label):
            print(f"  ✅ PASS: '{label}' 是有效标签")
            passed += 1
        else:
            print(f"  ❌ FAIL: '{label}' 应该是有效标签")
            failed += 1

    for label in invalid_labels:
        if not _is_valid_label(label):
            print(f"  ✅ PASS: '{label}' 是无效标签（正确识别）")
            passed += 1
        else:
            print(f"  ❌ FAIL: '{label}' 应该是无效标签")
            failed += 1

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_pct_diff():
    """测试百分比偏差计算"""
    print("\n" + "=" * 80)
    print("  测试 3: 百分比偏差计算")
    print("=" * 80)

    test_cases = [
        (1595, 1598, 0.00188),  # 约0.19%
        (1595, 1400, 0.1223),   # 约12.23%
        (100, 100, 0.0),        # 无偏差
        (0, 0, 0.0),            # 都为0
    ]

    passed = 0
    failed = 0

    for reported, fetched, expected_approx in test_cases:
        result = _pct_diff(reported, fetched)

        # 允许误差 0.001（0.1%）
        if abs(result - expected_approx) < 0.001:
            print(f"  ✅ PASS: 偏差({reported}, {fetched}) = {result:.4f}")
            passed += 1
        else:
            print(f"  ❌ FAIL: 偏差({reported}, {fetched}) = {result:.4f} (期望约 {expected_approx:.4f})")
            failed += 1

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_parse_md_tables():
    """测试 Markdown 表格解析"""
    print("\n" + "=" * 80)
    print("  测试 4: Markdown 表格解析")
    print("=" * 80)

    lines = MOCK_REPORT_MD.split('\n')

    try:
        results = _parse_md_tables(lines)

        if len(results) > 0:
            print(f"  ✅ PASS: 成功解析 {len(results)} 个表格数据点")

            # 检查第一个数据点是否包含预期字段
            if len(results) > 0:
                first = results[0]
                if len(first) == 6:  # (row_label, col_header, value, unit, lineno, raw)
                    print(f"  ✅ PASS: 数据点格式正确")
                    print(f"     示例: {first[0]} · {first[1]} = {first[2]} {first[3]}")
                    return True
                else:
                    print(f"  ❌ FAIL: 数据点格式不正确（期望 6 个字段，实际 {len(first)}）")
                    return False
        else:
            print(f"  ❌ FAIL: 未解析到任何表格数据点")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: 表格解析异常")
        print(f"     错误: {e}")
        return False


def test_extract_data_points():
    """测试数据点提取功能"""
    print("\n" + "=" * 80)
    print("  测试 5: 数据点提取功能")
    print("=" * 80)

    try:
        points = extract_data_points(MOCK_REPORT_MD)

        if len(points) > 0:
            print(f"  ✅ PASS: 成功提取 {len(points)} 个数据点")

            # 检查数据点结构
            required_fields = ['id', 'label', 'reported_value', 'unit', 'raw_text', 'line_number']
            all_valid = True

            for p in points[:5]:  # 检查前5个
                missing = [f for f in required_fields if f not in p]
                if missing:
                    print(f"  ❌ FAIL: 数据点缺少字段: {missing}")
                    all_valid = False

            if all_valid:
                print(f"  ✅ PASS: 所有数据点结构完整")

                # 检查是否包含预期数据
                labels = [p['label'] for p in points]
                print(f"  ✅ PASS: 提取的数据标签示例: {labels[:5]}")
                return True
            else:
                return False
        else:
            print(f"  ❌ FAIL: 未提取到任何数据点")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: 数据点提取异常")
        print(f"     错误: {e}")
        return False


def test_sample_points():
    """测试随机抽样功能"""
    print("\n" + "=" * 80)
    print("  测试 6: 随机抽样功能")
    print("=" * 80)

    # 提取数据点
    points = extract_data_points(MOCK_REPORT_MD)

    if len(points) < 10:
        print(f"  ⚠️  跳过: 数据点数量不足（需要至少10个，实际 {len(points)}）")
        return None

    # 测试默认比例（15%）
    sampled_15 = sample_points(points, ratio=0.15, seed=42)

    expected_count = max(3, min(30, int(len(points) * 0.15)))

    if len(sampled_15) >= 3 and len(sampled_15) <= 30:
        print(f"  ✅ PASS: 抽样数量正确（{len(sampled_15)} 个，期望 {expected_count} 个）")
    else:
        print(f"  ❌ FAIL: 抽样数量不正确（{len(sampled_15)} 个，期望 {expected_count} 个）")
        return False

    # 测试可重复性（相同种子应产生相同结果）
    sampled_repeat = sample_points(points, ratio=0.15, seed=42)

    if sampled_15 == sampled_repeat:
        print(f"  ✅ PASS: 相同种子产生相同结果（可重复）")
    else:
        print(f"  ❌ FAIL: 相同种子产生不同结果（不可重复）")
        return False

    # 测试不同比例
    sampled_20 = sample_points(points, ratio=0.20, seed=42)

    if len(sampled_20) >= len(sampled_15):
        print(f"  ✅ PASS: 更高比例产生更多样本（{len(sampled_20)} vs {len(sampled_15)}）")
    else:
        print(f"  ❌ FAIL: 比例逻辑异常")
        return False

    return True


def test_render_verdict_pass():
    """测试准出场景（所有数据通过核验）"""
    print("\n" + "=" * 80)
    print("  测试 7: 准出判决（所有数据通过）")
    print("=" * 80)

    try:
        result = render_verdict(MOCK_VERDICT_RESULTS_PASS, report_name="测试报告")

        if result['verdict'] == 'PASS':
            print(f"  ✅ PASS: 准出判决正确")
            print(f"     通过: {result['pass_count']}, 失败: {result['fail_count']}")
            return True
        else:
            print(f"  ❌ FAIL: 判决错误（期望 PASS，实际 {result['verdict']}）")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: 判决异常")
        print(f"     错误: {e}")
        return False


def test_render_verdict_fail():
    """测试打回场景（数据核验不通过）"""
    print("\n" + "=" * 80)
    print("  测试 8: 打回判决（数据不通过）")
    print("=" * 80)

    try:
        result = render_verdict(MOCK_VERDICT_RESULTS_FAIL, report_name="测试报告")

        if result['verdict'] == 'FAIL':
            print(f"  ✅ PASS: 打回判决正确")
            print(f"     通过: {result['pass_count']}, 失败: {result['fail_count']}")
            print(f"     失败项数: {len(result['fail_items'])}")
            return True
        else:
            print(f"  ❌ FAIL: 判决错误（期望 FAIL，实际 {result['verdict']}）")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: 判决异常")
        print(f"     错误: {e}")
        return False


def test_render_verdict_warn():
    """测试警告场景（两来源结果不一致）"""
    print("\n" + "=" * 80)
    print("  测试 9: 警告场景（两来源不一致）")
    print("=" * 80)

    try:
        result = render_verdict(MOCK_VERDICT_RESULTS_WARN, report_name="测试报告")

        # 警告不计入失败，所以应该是 PASS
        if result['verdict'] == 'PASS' and result['warn_count'] > 0:
            print(f"  ✅ PASS: 警告处理正确")
            print(f"     通过: {result['pass_count']}, 警告: {result['warn_count']}")
            return True
        else:
            print(f"  ❌ FAIL: 警告处理异常")
            print(f"     判决: {result['verdict']}, 警告数: {result['warn_count']}")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: 判决异常")
        print(f"     错误: {e}")
        return False


def test_boundary_conditions():
    """测试边界条件"""
    print("\n" + "=" * 80)
    print("  测试 10: 边界条件测试")
    print("=" * 80)

    # 测试空输入
    try:
        empty_points = extract_data_points("")
        if len(empty_points) == 0:
            print(f"  ✅ PASS: 空输入返回空列表")
        else:
            print(f"  ❌ FAIL: 空输入返回非空列表")
            return False
    except Exception as e:
        print(f"  ❌ FAIL: 空输入异常: {e}")
        return False

    # 测试无表格的纯文本
    try:
        text_only = "这是一段普通文本，没有表格和数字。"
        points = extract_data_points(text_only)
        if len(points) == 0:
            print(f"  ✅ PASS: 纯文本返回空列表")
        else:
            print(f"  ⚠️  注意: 纯文本返回了 {len(points)} 个数据点（可能是 KV 行匹配）")
    except Exception as e:
        print(f"  ❌ FAIL: 纯文本异常: {e}")
        return False

    # 测试异常数字
    try:
        result = _clean_num("abc")
        if result is None:
            print(f"  ✅ PASS: 异常数字返回 None")
        else:
            print(f"  ❌ FAIL: 异常数字未返回 None")
            return False
    except Exception as e:
        print(f"  ❌ FAIL: 异常数字处理异常: {e}")
        return False

    # 测试超大数字
    try:
        big_num = _clean_num("999999999999999")
        if big_num == 999999999999999:
            print(f"  ✅ PASS: 大数字处理正确")
        else:
            print(f"  ❌ FAIL: 大数字处理错误")
            return False
    except Exception as e:
        print(f"  ❌ FAIL: 大数字处理异常: {e}")
        return False

    return True


def test_integration():
    """集成测试：完整工作流"""
    print("\n" + "=" * 80)
    print("  测试 11: 集成测试（完整工作流）")
    print("=" * 80)

    try:
        # 步骤1: 提取数据点
        points = extract_data_points(MOCK_REPORT_MD)
        print(f"  [步骤1] 提取数据点: {len(points)} 个")

        # 步骤2: 随机抽样
        sampled = sample_points(points, ratio=0.15, seed=42)
        print(f"  [步骤2] 随机抽样: {len(sampled)} 个")

        # 步骤3: 模拟核验（填充 fetched_value）
        results = []
        for p in sampled[:3]:  # 只核验前3个
            results.append({
                'id': p['id'],
                'label': p['label'],
                'reported_value': p['reported_value'],
                'unit': p['unit'],
                'fetched_value': p['reported_value'],  # 模拟完全一致
                'fetched_source': 'test_source',
            })

        # 步骤4: 判决
        verdict = render_verdict(results, report_name="集成测试")
        print(f"  [步骤3-4] 核验判决: {verdict['verdict']}")

        if verdict['verdict'] == 'PASS':
            print(f"  ✅ PASS: 集成测试通过")
            return True
        else:
            print(f"  ❌ FAIL: 集成测试失败")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: 集成测试异常")
        print(f"     错误: {e}")
        return False


# ============================================================
# 主测试流程
# ============================================================

def main():
    """运行所有测试"""
    from datetime import datetime

    print("\n" + "=" * 80)
    print("  研究报告数据抽检工具 - 测试套件")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    results = {
        "数字清洗": test_clean_num(),
        "标签验证": test_is_valid_label(),
        "偏差计算": test_pct_diff(),
        "表格解析": test_parse_md_tables(),
        "数据点提取": test_extract_data_points(),
        "随机抽样": test_sample_points(),
        "准出判决": test_render_verdict_pass(),
        "打回判决": test_render_verdict_fail(),
        "警告处理": test_render_verdict_warn(),
        "边界条件": test_boundary_conditions(),
        "集成测试": test_integration(),
    }

    # 输出测试总结
    print("\n" + "=" * 80)
    print("  测试总结")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⏭️  SKIP"
        print(f"  {status}  {test_name}")

    print(f"\n  总计: {passed} 通过, {failed} 失败, {skipped} 跳过")

    if failed == 0:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️  有 {failed} 个测试失败")

    print("\n" + "=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
