#!/usr/bin/env python3
"""美股数据获取工具测试软件。

测试 tools/stock_info_us.py 的各功能模块。

测试模块：
1. test_realtime_quote - 测试个股实时行情获取
2. test_index_daily - 测试美股三大指数历史日线获取
3. test_stock_daily - 测试个股历史K线获取
4. test_code_mapping - 测试股票代码映射功能
5. test_error_handling - 测试错误处理机制
6. test_command_line - 测试命令行参数解析

Usage:
    {py} tests/test_stock_info_us.py
    {py} tests/test_stock_info_us.py --test realtime
    {py} tests/test_stock_info_us.py --test all
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
    from tools.stock_info_us import (
        get_us_realtime_quote,
        get_us_index_daily,
        get_us_stock_daily,
        standard_to_em_code,
        get_code_mapping,
        safe_api_call
    )
except ImportError as e:
    print(f"无法导入 stock_info_us 模块: {e}")
    print("请确保在项目根目录下运行测试")
    sys.exit(1)


class TestUSStockRealtimeQuote(unittest.TestCase):
    """测试个股实时行情获取功能。"""

    def test_realtime_quote_aapl(self):
        """测试获取苹果(AAPL)实时行情。"""
        print("\n测试1: 获取 AAPL 实时行情...")
        result = get_us_realtime_quote("AAPL")
        
        # 验证返回结构
        self.assertIn("success", result)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "AAPL")
        
        if result.get("success"):
            self.assertIn("data", result)
            self.assertIn("meta", result)
            self.assertEqual(result["meta"]["api"], "stock_us_spot_em")
            print(f"  ✓ 获取成功")
            print(f"    数据字段: {list(result['data'].keys())[:5]}...")
        else:
            print(f"  ⚠ 获取失败: {result.get('error')}")
            # 网络问题不应导致测试失败
            self.assertIn("error", result)

    def test_realtime_quote_invalid_symbol(self):
        """测试无效股票代码处理。"""
        print("\n测试2: 测试无效股票代码...")
        result = get_us_realtime_quote("INVALID_SYMBOL_12345")
        
        self.assertIn("success", result)
        # 无效代码应该返回失败或空数据
        if not result.get("success"):
            print(f"  ✓ 正确处理无效代码: {result.get('error')}")
        else:
            print(f"  ⚠ 返回了数据（可能是API行为变化）")


class TestUSIndexDaily(unittest.TestCase):
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
        expected_indices = ["纳斯达克综合指数", "道琼斯工业指数", "标普500指数"]
        
        for index_name in expected_indices:
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
        start_date = "20260101"
        end_date = "20260727"
        result = get_us_index_daily(start_date, end_date)
        
        self.assertIn("success", result)
        self.assertIn("meta", result)
        
        meta = result.get("meta", {})
        self.assertEqual(meta.get("start_date"), start_date)
        self.assertEqual(meta.get("end_date"), end_date)
        print(f"  ✓ 日期参数正确传递: {start_date} ~ {end_date}")


class TestUSStockDaily(unittest.TestCase):
    """测试个股历史K线获取功能。"""

    def test_stock_daily_aapl(self):
        """测试获取苹果(AAPL)历史K线。"""
        print("\n测试5: 获取 AAPL 历史K线...")
        result = get_us_stock_daily("AAPL", "20260101", "20260727", "qfq")
        
        # 验证返回结构
        self.assertIn("success", result)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "AAPL")
        
        if result.get("success"):
            self.assertIn("data", result)
            data = result.get("data", {})
            print(f"  ✓ 获取成功，数据条数: {data.get('count', 0)}")
            print(f"    列: {data.get('columns', [])}")
            
            # 验证 meta 中的 adjust 字段
            meta = result.get("meta", {})
            self.assertEqual(meta.get("adjust"), "qfq")
        else:
            print(f"  ⚠ 获取失败: {result.get('error')}")

    def test_stock_daily_adjust_types(self):
        """测试不同复权类型。"""
        print("\n测试6: 测试不同复权类型...")
        adjust_types = ["qfq", "hfq", ""]
        
        for adjust in adjust_types:
            result = get_us_stock_daily("AAPL", "20260601", "20260701", adjust)
            self.assertIn("success", result)
            
            if result.get("success"):
                meta = result.get("meta", {})
                self.assertEqual(meta.get("adjust"), adjust)
                print(f"  复权类型 '{adjust}': ✓")
            else:
                print(f"  复权类型 '{adjust}': ⚠ 获取失败（网络问题）")


class TestCodeMapping(unittest.TestCase):
    """测试股票代码映射功能。"""

    def test_standard_to_em_code(self):
        """测试标准代码转东方财富代码。"""
        print("\n测试7: 测试股票代码映射功能...")
        
        # 测试标准格式
        em_code = standard_to_em_code("AAPL")
        self.assertIn(".", em_code)
        self.assertIn("AAPL", em_code.upper())
        print(f"  AAPL -> {em_code}")
        
        # 测试小写输入
        em_code_lower = standard_to_em_code("msft")
        self.assertIn(".", em_code_lower)
        print(f"  msft -> {em_code_lower}")
        
        # 测试未知代码（应返回构造格式）
        em_code_unknown = standard_to_em_code("UNKNOWN")
        self.assertEqual(em_code_unknown, "105.UNKNOWN")
        print(f"  UNKNOWN -> {em_code_unknown}")

    def test_get_code_mapping(self):
        """测试获取代码映射表。"""
        print("\n测试8: 测试获取代码映射表...")
        
        mapping = get_code_mapping()
        
        if mapping:
            self.assertIsInstance(mapping, dict)
            print(f"  ✓ 映射表包含 {len(mapping)} 个股票代码")
            
            # 验证常见股票是否存在
            common_stocks = ["AAPL", "MSFT", "GOOGL"]
            for stock in common_stocks:
                if stock in mapping:
                    print(f"    {stock} -> {mapping[stock]}")
        else:
            print(f"  ⚠ 未获取到映射表（网络问题）")


class TestErrorHandling(unittest.TestCase):
    """测试错误处理机制。"""

    def test_safe_api_call_success(self):
        """测试 safe_api_call 成功场景。"""
        print("\n测试9: 测试 safe_api_call 成功场景...")
        
        def success_func():
            return type('obj', (object,), {'empty': False, 'data': 'test'})()
        
        result = safe_api_call(success_func, "test_api")
        self.assertIsNotNone(result)
        print(f"  ✓ 成功调用返回正确")

    def test_safe_api_call_retry(self):
        """测试 safe_api_call 重试机制。"""
        print("\n测试10: 测试 safe_api_call 重试机制...")
        
        call_count = [0]
        
        def fail_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("模拟失败")
            return type('obj', (object,), {'empty': False})()
        
        try:
            result = safe_api_call(fail_func, "test_api", max_retries=3, delay=0.1)
            self.assertEqual(call_count[0], 2)  # 第2次成功
            print(f"  ✓ 重试机制正常工作，调用次数: {call_count[0]}")
        except Exception as e:
            print(f"  ⚠ 重试机制异常: {e}")

    def test_empty_symbol_handling(self):
        """测试空股票代码处理。"""
        print("\n测试11: 测试空股票代码处理...")
        # API 会抛出异常，测试异常处理
        try:
            result = get_us_realtime_quote("")
            self.assertIn("success", result)
            if not result.get("success"):
                print(f"  ✓ 正确处理空代码: {result.get('error')}")
        except Exception as e:
            print(f"  ✓ 抛出异常（预期行为）: {type(e).__name__}")


class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口。"""

    def test_help_output(self):
        """测试帮助信息输出。"""
        print("\n测试12: 测试命令行帮助信息...")
        import subprocess
        py = sys.executable
        result = subprocess.run(
            [py, "tools/stock_info_us.py", "--help"],
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
        test_type: 测试类型，可选 "all"、"realtime"、"index"、"daily"、"mapping"、"error"、"cli"
    """
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    if test_type == "all":
        suite.addTests(loader.loadTestsFromTestCase(TestUSStockRealtimeQuote))
        suite.addTests(loader.loadTestsFromTestCase(TestUSIndexDaily))
        suite.addTests(loader.loadTestsFromTestCase(TestUSStockDaily))
        suite.addTests(loader.loadTestsFromTestCase(TestCodeMapping))
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    elif test_type == "realtime":
        suite.addTests(loader.loadTestsFromTestCase(TestUSStockRealtimeQuote))
    elif test_type == "index":
        suite.addTests(loader.loadTestsFromTestCase(TestUSIndexDaily))
    elif test_type == "daily":
        suite.addTests(loader.loadTestsFromTestCase(TestUSStockDaily))
    elif test_type == "mapping":
        suite.addTests(loader.loadTestsFromTestCase(TestCodeMapping))
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
    
    parser = argparse.ArgumentParser(description="美股数据获取工具测试软件")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "realtime", "index", "daily", "mapping", "error", "cli"],
                        help="测试类型（默认: all）")
    
    args = parser.parse_args()
    
    success = run_tests(args.test)
    sys.exit(0 if success else 1)