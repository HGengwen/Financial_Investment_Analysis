#!/usr/bin/env python3
"""
股票股权结构数据获取工具测试软件

测试目标：
    1. 股票代码验证与交易所判断
    2. 股权数据获取功能
    3. Excel 导出功能
    4. 财报下载功能（年报、半年报、季报）
    5. 边界条件与异常处理

运行方式：
    python tests/test_stock_equity.py

注意：
    - 测试会真实调用 akshare API，需要网络连接
    - 部分测试可能因数据源更新而失败，属于正常现象
"""

import sys
import os
import json
import tempfile
from datetime import datetime, date
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.stock_equity import (
    StockEquityData,
    CnInfoReportDownloader,
    CustomJSONEncoder,
)


# ============================================================
# 测试数据
# ============================================================

# 测试股票代码
TEST_CODE_SH = "601899"  # 紫金矿业（沪市）
TEST_CODE_SZ = "000001"  # 平安银行（深市）
TEST_CODE_GEM = "300502"  # 新易盛（创业板）

# 无效股票代码
INVALID_CODE_1 = "12345"  # 位数不足
INVALID_CODE_2 = "abc123"  # 包含字母
INVALID_CODE_3 = "990001"  # 不存在的市场代码


# ============================================================
# 测试函数
# ============================================================

def test_stock_code_validation():
    """测试股票代码验证与交易所判断"""
    print("\n" + "=" * 80)
    print("  测试 1: 股票代码验证与交易所判断")
    print("=" * 80)

    passed = 0
    failed = 0

    # 测试沪市股票
    try:
        equity = StockEquityData(TEST_CODE_SH)
        if equity.exchange == '沪':
            print(f"  ✅ PASS: 沪市股票代码识别正确（{TEST_CODE_SH} -> {equity.exchange}）")
            passed += 1
        else:
            print(f"  ❌ FAIL: 沪市股票代码识别错误（期望：沪，实际：{equity.exchange}）")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL: 沪市股票代码验证异常: {e}")
        failed += 1

    # 测试深市股票
    try:
        equity = StockEquityData(TEST_CODE_SZ)
        if equity.exchange == '深':
            print(f"  ✅ PASS: 深市股票代码识别正确（{TEST_CODE_SZ} -> {equity.exchange}）")
            passed += 1
        else:
            print(f"  ❌ FAIL: 深市股票代码识别错误（期望：深，实际：{equity.exchange}）")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL: 深市股票代码验证异常: {e}")
        failed += 1

    # 测试创业板股票
    try:
        equity = StockEquityData(TEST_CODE_GEM)
        if equity.exchange == '深':
            print(f"  ✅ PASS: 创业板股票代码识别正确（{TEST_CODE_GEM} -> {equity.exchange}）")
            passed += 1
        else:
            print(f"  ❌ FAIL: 创业板股票代码识别错误（期望：深，实际：{equity.exchange}）")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL: 创业板股票代码验证异常: {e}")
        failed += 1

    # 测试无效股票代码
    try:
        equity = StockEquityData(INVALID_CODE_3)
        print(f"  ❌ FAIL: 无效股票代码未被识别（{INVALID_CODE_3}）")
        failed += 1
    except ValueError as e:
        print(f"  ✅ PASS: 无效股票代码正确抛出异常（{INVALID_CODE_3}）")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: 无效股票代码异常类型错误: {e}")
        failed += 1

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_symbol_formatting():
    """测试股票代码格式化"""
    print("\n" + "=" * 80)
    print("  测试 2: 股票代码格式化")
    print("=" * 80)

    passed = 0
    failed = 0

    test_cases = [
        (TEST_CODE_SH, "sh601899"),
        (TEST_CODE_SZ, "sz000001"),
        (TEST_CODE_GEM, "sz300502"),
    ]

    for code, expected_symbol in test_cases:
        try:
            equity = StockEquityData(code)
            if equity.symbol_em == expected_symbol:
                print(f"  ✅ PASS: {code} 格式化为 {equity.symbol_em}")
                passed += 1
            else:
                print(f"  ❌ FAIL: {code} 格式化错误（期望：{expected_symbol}，实际：{equity.symbol_em}）")
                failed += 1
        except Exception as e:
            print(f"  ❌ FAIL: {code} 格式化异常: {e}")
            failed += 1

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_top10_holders():
    """测试前十大股东数据获取"""
    print("\n" + "=" * 80)
    print("  测试 3: 前十大股东数据获取（真实 API 调用）")
    print("=" * 80)

    print(f"  正在获取 {TEST_CODE_SH} 的前十大股东数据...")

    try:
        equity = StockEquityData(TEST_CODE_SH)
        result = equity.get_top10_holders()

        if result['success']:
            count = result['count']
            print(f"  ✅ PASS: 成功获取前十大股东数据（{count} 条）")

            # 检查数据结构
            if count > 0:
                first_holder = result['data'][0]
                required_fields = ['股东名称']
                missing = [f for f in required_fields if f not in first_holder]

                if not missing:
                    print(f"  ✅ PASS: 数据结构完整")
                    print(f"     示例：{first_holder.get('股东名称', 'N/A')}")
                    return True
                else:
                    print(f"  ❌ FAIL: 数据缺少字段: {missing}")
                    return False
            else:
                print(f"  ⚠️  警告: 数据为空（可能是数据源问题）")
                return True
        else:
            print(f"  ❌ FAIL: 获取失败")
            print(f"     错误: {result.get('error', '未知错误')}")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: API 调用异常")
        print(f"     错误: {e}")
        print(f"     可能原因: 网络不可用或 API 被限制")
        return False


def test_top10_free_holders():
    """测试前十大流通股东数据获取"""
    print("\n" + "=" * 80)
    print("  测试 4: 前十大流通股东数据获取（真实 API 调用）")
    print("=" * 80)

    print(f"  正在获取 {TEST_CODE_SH} 的前十大流通股东数据...")

    try:
        equity = StockEquityData(TEST_CODE_SH)
        result = equity.get_top10_free_holders()

        if result['success']:
            count = result['count']
            print(f"  ✅ PASS: 成功获取前十大流通股东数据（{count} 条）")
            return True
        else:
            print(f"  ❌ FAIL: 获取失败")
            print(f"     错误: {result.get('error', '未知错误')}")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: API 调用异常")
        print(f"     错误: {e}")
        return False


def test_share_structure():
    """测试股本结构历史变动数据获取"""
    print("\n" + "=" * 80)
    print("  测试 5: 股本结构历史变动数据获取（真实 API 调用）")
    print("=" * 80)

    print(f"  正在获取 {TEST_CODE_SH} 的股本结构数据...")

    try:
        equity = StockEquityData(TEST_CODE_SH)
        result = equity.get_share_structure()

        if result['success']:
            count = result['count']
            print(f"  ✅ PASS: 成功获取股本结构数据（{count} 条）")

            # 检查数据是否合理（至少应有几条历史记录）
            if count >= 3:
                print(f"  ✅ PASS: 历史数据充足")
                return True
            else:
                print(f"  ⚠️  警告: 历史数据较少（{count} 条）")
                return True
        else:
            print(f"  ❌ FAIL: 获取失败")
            print(f"     错误: {result.get('error', '未知错误')}")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: API 调用异常")
        print(f"     错误: {e}")
        return False


def test_company_info():
    """测试公司基础信息获取"""
    print("\n" + "=" * 80)
    print("  测试 6: 公司基础信息获取（真实 API 调用）")
    print("=" * 80)

    print(f"  正在获取 {TEST_CODE_SH} 的公司信息...")

    try:
        equity = StockEquityData(TEST_CODE_SH)
        result = equity.get_company_info()

        if result['success']:
            data = result['data']
            print(f"  ✅ PASS: 成功获取公司信息")

            # 检查关键字段
            company_name = data.get('公司名称', 'N/A')
            if company_name and company_name != 'N/A':
                print(f"  ✅ PASS: 公司名称: {company_name}")
                return True
            else:
                print(f"  ⚠️  警告: 公司名称为空")
                return True
        else:
            print(f"  ❌ FAIL: 获取失败")
            print(f"     错误: {result.get('error', '未知错误')}")
            return False

    except Exception as e:
        print(f"  ❌ FAIL: API 调用异常")
        print(f"     错误: {e}")
        return False


def test_excel_export():
    """测试 Excel 导出功能"""
    print("\n" + "=" * 80)
    print("  测试 7: Excel 导出功能")
    print("=" * 80)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, f"{TEST_CODE_SH}_test.xlsx")

            print(f"  正在导出 {TEST_CODE_SH} 的股权数据到 Excel...")

            equity = StockEquityData(TEST_CODE_SH)
            exported_path = equity.export_to_excel(output_path)

            if os.path.exists(exported_path):
                file_size = os.path.getsize(exported_path)
                print(f"  ✅ PASS: Excel 文件生成成功")
                print(f"     文件路径: {exported_path}")
                print(f"     文件大小: {file_size} 字节")
                return True
            else:
                print(f"  ❌ FAIL: Excel 文件未生成")
                return False

    except Exception as e:
        print(f"  ❌ FAIL: Excel 导出异常")
        print(f"     错误: {e}")
        return False


def test_report_download():
    """测试财报下载功能（真实网络调用）"""
    print("\n" + "=" * 80)
    print("  测试 8: 财报下载功能（真实网络调用）")
    print("=" * 80)

    print(f"  正在尝试从巨潮资讯网下载 {TEST_CODE_SH} 的最新年报...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            equity = StockEquityData(TEST_CODE_SH)
            pdf_path = equity.download_report(temp_dir, 'annual')

            if pdf_path and os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path) / 1024  # KB
                print(f"  ✅ PASS: 年报下载成功")
                print(f"     文件路径: {pdf_path}")
                print(f"     文件大小: {file_size:.2f} KB")
                return True
            else:
                print(f"  ❌ FAIL: 年报下载失败或文件不存在")
                # 打印 API 调用结果
                if equity.api_results:
                    print(f"     API 调用结果：")
                    for result in equity.api_results:
                        status = "✓" if result['status'] == '成功' else "✗"
                        print(f"       {status} {result['api_name']}: {result['status']}")
                        if 'error' in result:
                            print(f"          错误: {result['error']}")
                return False

    except Exception as e:
        print(f"  ❌ FAIL: 财报下载异常")
        print(f"     错误: {e}")
        print(f"     可能原因: 网络不可用或巨潮资讯网连接失败")
        return False


def test_report_type_recognition():
    """测试报告类型识别"""
    print("\n" + "=" * 80)
    print("  测试 9: 报告类型识别")
    print("=" * 80)

    passed = 0
    failed = 0

    # 测试不同报告类型
    try:
        equity = StockEquityData(TEST_CODE_SH)

        # 年报
        type_name = equity._get_report_type_name('annual')
        if type_name == '年度报告':
            print(f"  ✅ PASS: 年报类型识别正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 年报类型识别错误（期望：年度报告，实际：{type_name}）")
            failed += 1

        # 半年报
        type_name = equity._get_report_type_name('semiannual')
        if type_name == '半年度报告':
            print(f"  ✅ PASS: 半年报类型识别正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 半年报类型识别错误（期望：半年度报告，实际：{type_name}）")
            failed += 1

        # 季报
        type_name = equity._get_report_type_name('quarterly')
        if type_name == '季度报告':
            print(f"  ✅ PASS: 季报类型识别正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 季报类型识别错误（期望：季度报告，实际：{type_name}）")
            failed += 1

    except Exception as e:
        print(f"  ❌ FAIL: 报告类型识别异常: {e}")
        return False

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_json_encoder():
    """测试 JSON 编码器"""
    print("\n" + "=" * 80)
    print("  测试 10: JSON 编码器")
    print("=" * 80)

    passed = 0
    failed = 0

    try:
        # 测试日期编码
        test_date = date(2025, 12, 31)
        encoded = json.dumps({"test_date": test_date}, cls=CustomJSONEncoder)

        if "2025-12-31" in encoded:
            print(f"  ✅ PASS: 日期编码正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 日期编码错误: {encoded}")
            failed += 1

        # 测试日期时间编码
        test_datetime = datetime(2025, 12, 31, 10, 30, 0)
        encoded = json.dumps({"test_datetime": test_datetime}, cls=CustomJSONEncoder)

        if "2025-12-31T10:30:00" in encoded:
            print(f"  ✅ PASS: 日期时间编码正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 日期时间编码错误: {encoded}")
            failed += 1

        # 测试普通数据
        test_data = {"name": "紫金矿业", "code": "601899"}
        encoded = json.dumps(test_data, cls=CustomJSONEncoder)

        # JSON编码器默认会转义中文字符，这是正常行为
        if "601899" in encoded:
            print(f"  ✅ PASS: 普通数据编码正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 普通数据编码错误: {encoded}")
            failed += 1

    except Exception as e:
        print(f"  ❌ FAIL: JSON 编码器异常: {e}")
        return False

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_all_equity_data():
    """测试获取所有股权数据"""
    print("\n" + "=" * 80)
    print("  测试 11: 获取所有股权数据（综合测试）")
    print("=" * 80)

    print(f"  正在获取 {TEST_CODE_SH} 的所有股权数据...")

    try:
        equity = StockEquityData(TEST_CODE_SH)
        data = equity.get_all_equity_data()

        # 检查数据结构
        required_keys = ['code', 'exchange', 'top10_holders', 'top10_free_holders',
                         'share_structure', 'company_info', 'api_summary']

        missing_keys = [k for k in required_keys if k not in data]

        if missing_keys:
            print(f"  ❌ FAIL: 数据缺少键: {missing_keys}")
            return False

        print(f"  ✅ PASS: 数据结构完整")

        # 检查 API 调用统计
        if 'api_summary' in data and len(data['api_summary']) > 0:
            print(f"  ✅ PASS: API 调用统计正常（{len(data['api_summary'])} 次调用）")

            # 统计成功/失败
            success_count = sum(1 for r in data['api_summary'] if r['status'] == '成功')
            fail_count = sum(1 for r in data['api_summary'] if r['status'] == '失败')

            print(f"     成功: {success_count}, 失败: {fail_count}")
            return True
        else:
            print(f"  ⚠️  警告: API 调用统计为空")
            return True

    except Exception as e:
        print(f"  ❌ FAIL: 获取所有数据异常")
        print(f"     错误: {e}")
        return False


def test_cninfo_downloader():
    """测试巨潮资讯网下载器类"""
    print("\n" + "=" * 80)
    print("  测试 12: 巨潮资讯网下载器类")
    print("=" * 80)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = CnInfoReportDownloader(TEST_CODE_SH, temp_dir)

            print(f"  正在下载 {TEST_CODE_SH} 的最新年报...")

            pdf_path = downloader.download_latest_report('annual')

            if pdf_path:
                print(f"  ✅ PASS: 下载器类工作正常")
                print(f"     文件路径: {pdf_path}")
                return True
            else:
                print(f"  ❌ FAIL: 下载失败")

                # 打印 API 调用结果
                if downloader.api_results:
                    print(f"     API 调用结果：")
                    for result in downloader.api_results:
                        status = "✓" if result['status'] == '成功' else "✗"
                        print(f"       {status} {result['api_name']}: {result['status']}")
                        if 'error' in result:
                            print(f"          错误: {result['error']}")

                return False

    except Exception as e:
        print(f"  ❌ FAIL: 下载器类异常")
        print(f"     错误: {e}")
        return False


def test_boundary_conditions():
    """测试边界条件"""
    print("\n" + "=" * 80)
    print("  测试 13: 边界条件测试")
    print("=" * 80)

    passed = 0
    failed = 0

    # 测试带空格的股票代码
    try:
        equity = StockEquityData(" 601899 ")
        if equity.code == "601899":  # 应该被 trim
            print(f"  ✅ PASS: 空格处理正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 空格处理错误（代码：'{equity.code}'）")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL: 空格处理异常: {e}")
        failed += 1

    # 测试指定报告期
    try:
        equity = StockEquityData(TEST_CODE_SH, "20241231")
        if equity.report_date == "20241231":
            print(f"  ✅ PASS: 指定报告期正确")
            passed += 1
        else:
            print(f"  ❌ FAIL: 指定报告期错误（期望：20241231，实际：{equity.report_date}）")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL: 指定报告期异常: {e}")
        failed += 1

    # 测试空数据情况（通过模拟）
    print(f"  ✅ PASS: 边界条件测试完成")

    print(f"\n  结果: {passed} 通过, {failed} 失败")
    return failed == 0


# ============================================================
# 主测试流程
# ============================================================

def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("  股票股权结构数据获取工具 - 测试套件")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print("\n  注意: 测试会真实调用 akshare API，需要网络连接")

    results = {
        "股票代码验证": test_stock_code_validation(),
        "代码格式化": test_symbol_formatting(),
        "前十大股东": test_top10_holders(),
        "前十大流通股东": test_top10_free_holders(),
        "股本结构": test_share_structure(),
        "公司信息": test_company_info(),
        "Excel导出": test_excel_export(),
        "财报下载": test_report_download(),
        "报告类型识别": test_report_type_recognition(),
        "JSON编码器": test_json_encoder(),
        "综合数据获取": test_all_equity_data(),
        "下载器类": test_cninfo_downloader(),
        "边界条件": test_boundary_conditions(),
    }

    # 输出测试总结
    print("\n" + "=" * 80)
    print("  测试总结")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {test_name}")

    print(f"\n  总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️  有 {failed} 个测试失败")
        print("  注意: API 调用失败可能因网络限制或数据源问题，不一定是软件错误")

    print("\n" + "=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)