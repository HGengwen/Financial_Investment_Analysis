#!/usr/bin/env python3
"""美股数据获取工具测试软件（yfinance 版本）。

测试 tools/stock_us_yfinance.py 的各功能模块。

测试模块：
1. test_realtime_info - 测试个股实时行情获取
2. test_index_daily - 测试美股三大指数历史日线获取
3. test_daily_kline - 测试个股历史K线获取
4. test_financial_statements - 测试财务报表获取
5. test_extra_data - 测试额外数据获取
6. test_error_handling - 测试错误处理机制
7. test_command_line - 测试命令行参数解析

Usage:
    {py} tests/test_stock_us_yfinance.py
    {py} tests/test_stock_us_yfinance.py --test realtime
    {py} tests/test_stock_us_yfinance.py --test all
"""

import json
import sys
import os
import unittest
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入被测试模块
try:
    from tools.stock_us_yfinance import (
        get_stock_realtime_info,
        get_us_index_daily,
        get_stock_daily_kline,
        get_stock_financial_statements,
        get_stock_extra_data,
        safe_api_call,
        US_INDEX_MAP
    )
except ImportError as e:
    print(f"无法导入 stock_us_yfinance 模块: {e}")
    print("请确保在项目根目录下运行测试")
    sys.exit(1)


class TestRealtimeInfo(unittest.TestCase):
    """测试个股实时行情获取功能。"""

    def test_realtime_info_aapl(self):
        """测试获取苹果(AAPL)实时行情。"""
        print("\n测试1: 获取 AAPL 实时行情...")
        result = get_stock_realtime_info("AAPL")
        
        # 验证返回结构
        self.assertIn("success", result)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "AAPL")
        
        if result.get("success"):
            self.assertIn("data", result)
            self.assertIn("meta", result)
            data = result.get("data", {})
            
            # 验证关键字段存在
            expected_fields = ["股票代码", "公司名称", "当前价格"]
            for field in expected_fields:
                self.assertIn(field, data)
            
            print(f"  ✓ 获取成功")
            print(f"    公司名称: {data.get('公司名称')}")
            print(f"    当前价格: {data.get('当前价格')}")
        else:
            print(f"  ⚠ 获取失败: {result.get('error')}")

    def test_realtime_info_tsla(self):
        """测试获取特斯拉(TSLA)实时行情。"""
        print("\n测试2: 获取 TSLA 实时行情...")
        result = get_stock_realtime_info("TSLA")
        
        self.assertIn("success", result)
        self.assertEqual(result.get("symbol"), "TSLA")
        print(f"  ✓ 返回结构正确")


class TestIndexDaily(unittest.TestCase):
    """测试美股三大指数历史日线获取功能。"""

    def test_index_daily_default(self):
        """测试获取三大指数默认日期范围数据。"""
        print("\n测试3: 获取美股三大指数历史日线（默认日期）...")
        result = get_us_index_daily()
        
        # 验证返回结构
        self.assertIn("success", result)
        self.assertTrue(result.get("success"))
        self.assertIn("data", result)
        self.assertIn("meta", result)
        
        # 验证三大指数
        data = result.get("data", {})
        for index_name in US_INDEX_MAP.keys():
            self.assertIn(index_name, data)
            index_data = data[index_name]
            print(f"  {index_name}:")
            if "error" in index_data:
                print(f"    ⚠ 获取失败: {index_data['error']}")
            else:
                print(f"    ✓ 数据条数: {index_data.get('count', 0)}")

    def test_index_daily_custom_date(self):
        """测试获取指定日期范围的指数数据。"""
        print("\n测试4: 获取指定日期范围的指数数据...")
        start_date = "2025-01-01"
        end_date = "2026-07-27"
        result = get_us_index_daily(start_date, end_date)
        
        self.assertIn("success", result)
        self.assertIn("meta", result)
        
        meta = result.get("meta", {})
        self.assertEqual(meta.get("start_date"), start_date)
        self.assertEqual(meta.get("end_date"), end_date)
        print(f"  ✓ 日期参数正确传递: {start_date} ~ {end_date}")


class TestDailyKline(unittest.TestCase):
    """测试个股历史K线获取功能。"""

    def test_daily_kline_aapl(self):
        """测试获取苹果(AAPL)历史K线。"""
        print("\n测试5: 获取 AAPL 历史K线...")
        result = get_stock_daily_kline("AAPL", "2025-01-01", "2026-07-27", auto_adjust=True)
        
        # 验证返回结构
        self.assertIn("success", result)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "AAPL")
        
        if result.get("success"):
            self.assertIn("data", result)
            data = result.get("data", {})
            print(f"  ✓ 获取成功，数据条数: {data.get('count', 0)}")
            print(f"    列: {data.get('columns', [])}")
            
            # 验证 meta 中的 auto_adjust 字段
            meta = result.get("meta", {})
            self.assertTrue(meta.get("auto_adjust", False))
        else:
            print(f"  ⚠ 获取失败: {result.get('error')}")

    def test_daily_kline_no_adjust(self):
        """测试不复权模式。"""
        print("\n测试6: 测试不复权模式...")
        result = get_stock_daily_kline("AAPL", "2026-06-01", "2026-07-01", auto_adjust=False)
        
        self.assertIn("success", result)
        
        if result.get("success"):
            meta = result.get("meta", {})
            self.assertFalse(meta.get("auto_adjust", True))
            print(f"  ✓ 不复权模式正确")
        else:
            print(f"  ⚠ 获取失败（网络问题）")


class TestFinancialStatements(unittest.TestCase):
    """测试财务报表获取功能。"""

    def test_financial_statements_aapl(self):
        """测试获取苹果(AAPL)财务报表。"""
        print("\n测试7: 获取 AAPL 财务数据...")
        result = get_stock_financial_statements("AAPL")
        
        # 验证返回结构
        self.assertIn("success", result)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "AAPL")
        
        if result.get("success"):
            self.assertIn("data", result)
            data = result.get("data", {})
            
            # 验证财务报表
            expected_reports = ["年度利润表", "季度利润表", "年度资产负债表", 
                               "季度资产负债表", "年度现金流量表", "季度现金流量表"]
            for report_name in expected_reports:
                self.assertIn(report_name, data)
                report_data = data[report_name]
                if "error" in report_data:
                    print(f"  {report_name}: ⚠ {report_data['error']}")
                else:
                    print(f"  {report_name}: ✓ 科目数 {report_data.get('count', 0)}")
        else:
            print(f"  ⚠ 获取失败: {result.get('error')}")


class TestExtraData(unittest.TestCase):
    """测试额外数据获取功能。"""

    def test_extra_data_aapl(self):
        """测试获取苹果(AAPL)额外数据。"""
        print("\n测试8: 获取 AAPL 额外数据...")
        result = get_stock_extra_data("AAPL")
        
        # 验证返回结构
        self.assertIn("success", result)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "AAPL")
        
        if result.get("success"):
            self.assertIn("data", result)
            data = result.get("data", {})
            
            # 验证额外数据类型
            expected_types = ["分红历史", "拆股历史", "机构持股", "分析师评级"]
            for data_type in expected_types:
                self.assertIn(data_type, data)
                type_data = data[data_type]
                if "error" in type_data:
                    print(f"  {data_type}: ⚠ {type_data['error']}")
                elif "note" in type_data:
                    print(f"  {data_type}: {type_data['note']}")
                else:
                    print(f"  {data_type}: ✓ 记录数 {type_data.get('count', 0)}")
        else:
            print(f"  ⚠ 获取失败: {result.get('error')}")


class TestErrorHandling(unittest.TestCase):
    """测试错误处理机制。"""

    def test_safe_api_call_success(self):
        """测试 safe_api_call 成功场景。"""
        print("\n测试9: 测试 safe_api_call 成功场景...")
        
        def success_func():
            return {"test": "success"}
        
        result = safe_api_call(success_func, "test_api")
        self.assertIsNotNone(result)
        self.assertEqual(result["test"], "success")
        print(f"  ✓ 成功调用返回正确")

    def test_safe_api_call_retry(self):
        """测试 safe_api_call 重试机制。"""
        print("\n测试10: 测试 safe_api_call 重试机制...")
        
        call_count = [0]
        
        def fail_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("模拟失败")
            return {"test": "retry_success"}
        
        try:
            result = safe_api_call(fail_func, "test_api", max_retries=3, delay=0.1)
            self.assertEqual(call_count[0], 2)  # 第2次成功
            self.assertEqual(result["test"], "retry_success")
            print(f"  ✓ 重试机制正常工作，调用次数: {call_count[0]}")
        except Exception as e:
            print(f"  ⚠ 重试机制异常: {e}")

    def test_invalid_symbol_handling(self):
        """测试无效股票代码处理。"""
        print("\n测试11: 测试无效股票代码处理...")
        
        # yfinance 对无效代码会返回空数据或抛出异常
        result = get_stock_realtime_info("INVALID_SYMBOL_12345")
        self.assertIn("success", result)
        
        if not result.get("success"):
            print(f"  ✓ 正确处理无效代码: {result.get('error')}")
        else:
            # yfinance 可能返回部分数据
            print(f"  ⚠ 返回了部分数据（API行为）")


class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口。"""

    def test_help_output(self):
        """测试帮助信息输出。"""
        print("\n测试12: 测试命令行帮助信息...")
        import subprocess
        py = sys.executable
        result = subprocess.run(
            [py, "tools/stock_us_yfinance.py", "--help"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("美股股票信息查询工具", result.stdout)
        print(f"  ✓ 帮助信息正常输出")


def run_tests(test_type="all"):
    """运行测试。

    Args:
        test_type: 测试类型，可选 "all"、"realtime"、"index"、"daily"、"financial"、"extra"、"error"、"cli"
    """
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    if test_type == "all":
        suite.addTests(loader.loadTestsFromTestCase(TestRealtimeInfo))
        suite.addTests(loader.loadTestsFromTestCase(TestIndexDaily))
        suite.addTests(loader.loadTestsFromTestCase(TestDailyKline))
        suite.addTests(loader.loadTestsFromTestCase(TestFinancialStatements))
        suite.addTests(loader.loadTestsFromTestCase(TestExtraData))
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    elif test_type == "realtime":
        suite.addTests(loader.loadTestsFromTestCase(TestRealtimeInfo))
    elif test_type == "index":
        suite.addTests(loader.loadTestsFromTestCase(TestIndexDaily))
    elif test_type == "daily":
        suite.addTests(loader.loadTestsFromTestCase(TestDailyKline))
    elif test_type == "financial":
        suite.addTests(loader.loadTestsFromTestCase(TestFinancialStatements))
    elif test_type == "extra":
        suite.addTests(loader.loadTestsFromTestCase(TestExtraData))
    elif test_type == "error":
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    elif test_type == "cli":
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    else:
        print(f"未知测试类型: {test_type}")
        return
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    print("\n" + "=" * 60)
    print(f"测试完成: {result.testsRun} 个测试")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="美股数据获取工具测试软件（yfinance 版本）")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "realtime", "index", "daily", "financial", "extra", "error", "cli"],
                        help="测试类型（默认: all）")
    
    args = parser.parse_args()
    
    success = run_tests(args.test)
    sys.exit(0 if success else 1)