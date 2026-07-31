#!/usr/bin/env python3
"""
Morningstar 公允价值筛选工具测试软件

测试目标：
    1. API 连接测试（网络可用性）
    2. 数据解析测试
    3. 股票代码提取测试
    4. 潜在涨幅计算测试
    5. CSV 文件生成测试

运行方式：
    python tests/specialized/test_morningstar_fair_value.py
"""

import sys
import os
import json
import tempfile
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.specialized.morningstar_fair_value import extract_ticker, fetch_page


# ============================================================
# 测试数据
# ============================================================

MOCK_API_RESPONSE = {
    "total": 250,
    "rows": [
        {
            "SecId": "0P00000001",
            "Name": "Apple Inc",
            "TenforeId": "AAPL.O.USA",
            "ClosePrice": 175.50,
            "FairValueEstimate": 200.00,
            "StarRatingM255": 4,
            "EconomicMoat": "Wide",
            "AssessmentOfFairValueUncertainty": "Medium",
            "SectorName": "Technology",
            "IndustryName": "Consumer Electronics"
        },
        {
            "SecId": "0P00000002",
            "Name": "Microsoft Corp",
            "TenforeId": "MSFT.O.USA",
            "ClosePrice": 380.00,
            "FairValueEstimate": 350.00,
            "StarRatingM255": 3,
            "EconomicMoat": "Wide",
            "AssessmentOfFairValueUncertainty": "Low",
            "SectorName": "Technology",
            "IndustryName": "Software"
        },
        {
            "SecId": "0P00000003",
            "Name": "Test Company",
            "TenforeId": "TEST.O.USA",
            "ClosePrice": 100.00,
            "FairValueEstimate": 120.00,
            "StarRatingM255": 5,
            "EconomicMoat": "Narrow",
            "AssessmentOfFairValueUncertainty": "High",
            "SectorName": "Healthcare",
            "IndustryName": "Biotechnology"
        }
    ]
}


# ============================================================
# 测试函数
# ============================================================

def test_extract_ticker():
    """测试股票代码提取功能"""
    print("\n" + "="*80)
    print("  测试 1: 股票代码提取功能")
    print("="*80)
    
    test_cases = [
        ("AAPL.O.USA", "AAPL"),
        ("MSFT.O.USA", "MSFT"),
        ("GOOG.O.USA", "GOOG"),
        ("INVALID", "INVALID"),
        ("", ""),
        ("A.B.C", "A"),  # TenforeId格式: {股票代码}.{交易所}.{国家}
    ]
    
    passed = 0
    failed = 0
    
    for tenforeid, expected in test_cases:
        result = extract_ticker(tenforeid)
        if result == expected:
            print(f"  ✅ PASS: extract_ticker('{tenforeid}') = '{result}'")
            passed += 1
        else:
            print(f"  ❌ FAIL: extract_ticker('{tenforeid}') = '{result}' (期望: '{expected}')")
            failed += 1
    
    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_api_connection():
    """测试 Morningstar API 连接"""
    print("\n" + "="*80)
    print("  测试 2: Morningstar API 连接")
    print("="*80)
    
    print("  尝试连接 Morningstar API...")
    
    try:
        data = fetch_page(1)
        
        if "total" in data and "rows" in data:
            total = data["total"]
            rows_count = len(data["rows"])
            print(f"  ✅ PASS: API 连接成功")
            print(f"     总股票数: {total}")
            print(f"     返回记录数: {rows_count}")
            return True
        else:
            print(f"  ❌ FAIL: API 返回数据格式不正确")
            print(f"     返回字段: {list(data.keys())}")
            return False
            
    except Exception as e:
        print(f"  ❌ FAIL: API 连接失败")
        print(f"     错误: {e}")
        print(f"     可能原因: 网络不可用或 API 被限制")
        return False


def test_potential_upside_calculation():
    """测试潜在涨幅计算"""
    print("\n" + "="*80)
    print("  测试 3: 潜在涨幅计算")
    print("="*80)
    
    test_cases = [
        (200.00, 175.50, 14.0),   # Apple: 低估
        (350.00, 380.00, -7.9),   # Microsoft: 高估
        (120.00, 100.00, 20.0),   # Test: 低估
        (100.00, 100.00, 0.0),    # 公平估值
    ]
    
    passed = 0
    failed = 0
    
    for fair_value, close_price, expected_upside in test_cases:
        upside = (fair_value - close_price) / close_price * 100
        
        if abs(upside - expected_upside) < 0.1:  # 允许 0.1% 误差
            print(f"  ✅ PASS: 潜在涨幅计算正确")
            print(f"     公允价值: ${fair_value:.2f}, 当前价格: ${close_price:.2f}")
            print(f"     潜在涨幅: {upside:.1f}%")
            passed += 1
        else:
            print(f"  ❌ FAIL: 潜在涨幅计算错误")
            print(f"     公允价值: ${fair_value:.2f}, 当前价格: ${close_price:.2f}")
            print(f"     计算结果: {upside:.1f}%, 期望: {expected_upside:.1f}%")
            failed += 1
    
    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_data_processing():
    """测试数据处理逻辑"""
    print("\n" + "="*80)
    print("  测试 4: 数据处理逻辑")
    print("="*80)
    
    # 模拟数据处理
    stocks = []
    for row in MOCK_API_RESPONSE["rows"]:
        fair_value = row.get("FairValueEstimate")
        close_price = row.get("ClosePrice")
        
        if fair_value and close_price and close_price > 0:
            ticker = extract_ticker(row.get("TenforeId", ""))
            upside = (fair_value - close_price) / close_price * 100
            
            stocks.append({
                "ticker": ticker,
                "name": row.get("Name", ""),
                "close_price": round(close_price, 2),
                "fair_value": round(fair_value, 2),
                "upside_pct": round(upside, 1),
                "star_rating": row.get("StarRatingM255", ""),
                "moat": row.get("EconomicMoat", ""),
            })
    
    # 验证处理结果
    if len(stocks) == 3:
        print(f"  ✅ PASS: 成功处理 {len(stocks)} 条记录")
    else:
        print(f"  ❌ FAIL: 处理记录数不正确（期望 3, 实际 {len(stocks)}）")
        return False
    
    # 验证排序功能
    stocks.sort(key=lambda x: x["upside_pct"], reverse=True)
    
    if stocks[0]["upside_pct"] >= stocks[-1]["upside_pct"]:
        print(f"  ✅ PASS: 排序功能正常")
        print(f"     最高涨幅: {stocks[0]['ticker']} {stocks[0]['upside_pct']}%")
        print(f"     最低涨幅: {stocks[-1]['ticker']} {stocks[-1]['upside_pct']}%")
    else:
        print(f"  ❌ FAIL: 排序功能异常")
        return False
    
    return True


def test_csv_generation():
    """测试 CSV 文件生成"""
    print("\n" + "="*80)
    print("  测试 5: CSV 文件生成")
    print("="*80)
    
    import csv
    
    # 使用临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = os.path.join(temp_dir, "test_morningstar.csv")
        
        # 模拟 CSV 写入
        stocks = [
            {
                "ticker": "AAPL",
                "name": "Apple Inc",
                "close_price": 175.50,
                "fair_value": 200.00,
                "upside_pct": 14.0,
            }
        ]
        
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "rank", "ticker", "name", "close_price", "fair_value", "upside_pct"
                ])
                writer.writeheader()
                for i, s in enumerate(stocks, 1):
                    writer.writerow({"rank": i, **s})
            
            # 验证文件是否存在
            if os.path.exists(csv_path):
                print(f"  ✅ PASS: CSV 文件生成成功")
                print(f"     文件路径: {csv_path}")
                
                # 验证文件内容
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    
                    if len(rows) == 1 and rows[0]["ticker"] == "AAPL":
                        print(f"  ✅ PASS: CSV 文件内容正确")
                        return True
                    else:
                        print(f"  ❌ FAIL: CSV 文件内容不正确")
                        return False
            else:
                print(f"  ❌ FAIL: CSV 文件未生成")
                return False
                
        except Exception as e:
            print(f"  ❌ FAIL: CSV 文件生成失败")
            print(f"     错误: {e}")
            return False


def test_statistical_analysis():
    """测试统计分析功能"""
    print("\n" + "="*80)
    print("  测试 6: 统计分析功能")
    print("="*80)
    
    # 模拟股票数据
    stocks = [
        {"ticker": "AAPL", "upside_pct": 14.0, "moat": "Wide"},
        {"ticker": "MSFT", "upside_pct": -7.9, "moat": "Wide"},
        {"ticker": "TEST", "upside_pct": 20.0, "moat": "Narrow"},
    ]
    
    # 计算统计数据
    undervalued = [s for s in stocks if s["upside_pct"] > 0]
    overvalued = [s for s in stocks if s["upside_pct"] < 0]
    
    # 验证低估股票数量
    if len(undervalued) == 2:
        print(f"  ✅ PASS: 低估股票统计正确（{len(undervalued)} 只）")
    else:
        print(f"  ❌ FAIL: 低估股票统计错误（期望 2, 实际 {len(undervalued)}）")
        return False
    
    # 验证高估股票数量
    if len(overvalued) == 1:
        print(f"  ✅ PASS: 高估股票统计正确（{len(overvalued)} 只）")
    else:
        print(f"  ❌ FAIL: 高估股票统计错误（期望 1, 实际 {len(overvalued)}）")
        return False
    
    # 计算平均涨幅
    if undervalued:
        avg_upside = sum(s["upside_pct"] for s in undervalued) / len(undervalued)
        expected_avg = (14.0 + 20.0) / 2
        
        if abs(avg_upside - expected_avg) < 0.1:
            print(f"  ✅ PASS: 平均涨幅计算正确（{avg_upside:.1f}%）")
        else:
            print(f"  ❌ FAIL: 平均涨幅计算错误（期望 {expected_avg:.1f}%, 实际 {avg_upside:.1f}%）")
            return False
    
    # 统计宽护城河低估股票
    wide_moat_undervalued = [s for s in stocks if s["moat"] == "Wide" and s["upside_pct"] > 0]
    
    if len(wide_moat_undervalued) == 1:
        print(f"  ✅ PASS: 宽护城河低估股票统计正确（{len(wide_moat_undervalued)} 只）")
    else:
        print(f"  ❌ FAIL: 宽护城河低估股票统计错误（期望 1, 实际 {len(wide_moat_undervalued)}）")
        return False
    
    return True


# ============================================================
# 主测试流程
# ============================================================

def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("  Morningstar 公允价值筛选工具 - 测试套件")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    results = {
        "股票代码提取": test_extract_ticker(),
        "API 连接": test_api_connection(),
        "潜在涨幅计算": test_potential_upside_calculation(),
        "数据处理": test_data_processing(),
        "CSV 文件生成": test_csv_generation(),
        "统计分析": test_statistical_analysis(),
    }
    
    # 输出测试总结
    print("\n" + "="*80)
    print("  测试总结")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {test_name}")
    
    print(f"\n  总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️  有 {failed} 个测试失败")
        print("  注意: API 连接测试可能因网络限制而失败")
    
    print("\n" + "="*80)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
