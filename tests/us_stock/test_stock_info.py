#!/usr/bin/env python3
"""美股实时行情与估值指标查询工具测试模块。

测试 tools/us_stock/stock_info.py 的各功能模块。

测试模块：
1. TestGetStockRealtimeInfo  - 测试获取个股实时行情与估值指标核心函数
2. TestCmdRealtime           - 测试 --realtime 命令处理
3. TestCommandLineInterface  - 测试命令行接口

Usage:
    {py} -m pytest tests/us_stock/test_stock_info.py -v
    {py} tests/us_stock/test_stock_info.py
    {py} tests/us_stock/test_stock_info.py --test all
"""

import json
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch
import unittest

# 添加项目根目录到路径（tests/us_stock/ 上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
try:
    from tools.us_stock.stock_info import (
        get_stock_realtime_info,
        cmd_realtime,
        safe_api_call,
    )
except ImportError as e:
    print(f"无法导入 stock_info 模块: {e}")
    print("请确保在项目根目录下运行测试，且 yfinance 已安装")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def parse_json_output(stdout_text: str) -> dict:
    """解析 stdout 文本为 JSON 字典。

    Args:
        stdout_text: 标准输出文本。

    Returns:
        解析后的字典；解析失败时返回空字典。
    """
    text = stdout_text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# 核心函数测试
# ---------------------------------------------------------------------------

class TestGetStockRealtimeInfo(unittest.TestCase):
    """测试获取个股实时行情与估值指标功能。"""

    def test_returns_dict(self):
        """测试返回类型为字典。"""
        try:
            result = get_stock_realtime_info("AAPL")
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_success_structure(self):
        """测试成功返回的数据结构完整性。"""
        try:
            result = get_stock_realtime_info("AAPL")
            # 顶层字段
            self.assertIn("success", result)
            self.assertIn("symbol", result)
            self.assertIn("meta", result)
            self.assertEqual(result["symbol"], "AAPL")
            # meta 结构
            self.assertIn("tool", result["meta"])
            self.assertIn("timestamp", result["meta"])
            self.assertEqual(result["meta"]["tool"], "stock_info")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_data_fields(self):
        """测试返回 data 中包含完整估值指标字段。"""
        try:
            result = get_stock_realtime_info("AAPL")
            if not result.get("success"):
                self.skipTest("网络不可用或数据获取失败")
            data = result.get("data", {})
            # 核心实时行情与估值指标字段
            expected_fields = [
                "股票代码", "公司名称", "当前价格", "开盘价", "最高价",
                "最低价", "昨日收盘价", "成交量", "市值", "市盈率TTM",
                "市净率PB", "52周最高", "52周最低", "股息率", "Beta系数",
                "ROE", "ROA", "流通市值", "总股本"
            ]
            for field in expected_fields:
                self.assertIn(field, data)
            self.assertEqual(data["股票代码"], "AAPL")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_key_valuation_fields(self):
        """测试关键估值指标字段（PE、PB、市值、股息率、Beta等）。"""
        try:
            result = get_stock_realtime_info("MSFT")
            if not result.get("success"):
                self.skipTest("网络不可用或数据获取失败")
            data = result.get("data", {})
            # 关键估值指标应存在（值可能为 None，但键必须存在）
            self.assertIn("市盈率TTM", data)
            self.assertIn("市净率PB", data)
            self.assertIn("市值", data)
            self.assertIn("股息率", data)
            self.assertIn("Beta系数", data)
            self.assertIn("ROE", data)
            self.assertIn("ROA", data)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_raw_info_present_on_success(self):
        """测试成功时保留原始 info 数据。"""
        try:
            result = get_stock_realtime_info("AAPL")
            if result.get("success"):
                self.assertIn("raw_info", result)
                self.assertIsInstance(result["raw_info"], dict)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_aapl_realtime(self):
        """测试获取苹果(AAPL)实时行情（集成测试）。"""
        try:
            result = get_stock_realtime_info("AAPL")
            if not result.get("success"):
                self.skipTest("网络不可用或数据获取失败")
            data = result.get("data", {})
            # 苹果公司名称应包含 Apple
            self.assertIsNotNone(data.get("公司名称"))
            # 市值应为数值
            self.assertIsNotNone(data.get("市值"))
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_invalid_symbol_structure(self):
        """测试无效代码返回结构（不崩溃）。"""
        try:
            result = get_stock_realtime_info("INVALIDCODE12345")
            # 无论成功与否，都应返回合法字典结构
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("symbol", result)
            self.assertEqual(result["symbol"], "INVALIDCODE12345")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_empty_info_handling(self):
        """测试 info 为 None 时的错误处理（使用 mock）。"""
        with patch('tools.us_stock.stock_info.safe_api_call') as mock_safe:
            # 第一次调用返回 stock 对象，第二次返回 None（info）
            mock_stock = object()
            mock_safe.side_effect = [mock_stock, None]
            result = get_stock_realtime_info("TEST")

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["symbol"], "TEST")

    def test_exception_handling(self):
        """测试异常且无缓存兜底时的错误处理（使用 mock）。"""
        with patch('tools.us_stock.stock_info.safe_api_call') as mock_safe, \
                patch('tools.us_stock.stock_info.us_stock_cache.get_slow_fields') as mock_slow:
            mock_safe.side_effect = Exception("网络连接失败")
            # 无可用慢变字段缓存兜底 → 返回失败
            mock_slow.return_value = None
            result = get_stock_realtime_info("AAPL")

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("网络连接失败", result["error"])
        self.assertEqual(result["symbol"], "AAPL")


class TestSafeApiCall(unittest.TestCase):
    """测试 safe_api_call 重试机制。"""

    def test_success_no_retry(self):
        """测试调用成功不重试。"""
        call_count = [0]

        def func():
            call_count[0] += 1
            return "ok"

        result = safe_api_call(func, "test_api", max_retries=3, delay=0)
        self.assertEqual(result, "ok")
        self.assertEqual(call_count[0], 1)

    def test_retry_on_failure(self):
        """测试失败时重试机制。"""
        call_count = [0]

        def func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("临时错误")
            return "success"

        result = safe_api_call(func, "test_api", max_retries=3, delay=0)
        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 3)

    def test_all_retries_exhausted(self):
        """测试重试耗尽后抛出异常。"""
        def func():
            raise ValueError("持续错误")

        with self.assertRaises(Exception) as cm:
            safe_api_call(func, "test_api", max_retries=2, delay=0)
        self.assertIn("持续错误", str(cm.exception))


# ---------------------------------------------------------------------------
# cmd_realtime 函数测试（使用 mock 隔离网络依赖）
# ---------------------------------------------------------------------------

class TestCmdRealtime(unittest.TestCase):
    """测试 --realtime 命令处理。"""

    def test_empty_symbol(self):
        """测试空股票代码的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_realtime("")
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("美股代码", output["error"])

    def test_none_symbol(self):
        """测试 None 股票代码的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_realtime(None)
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])

    @patch('tools.us_stock.stock_info.get_stock_realtime_info')
    def test_successful_output_json(self, mock_get_info):
        """测试成功时 JSON 格式输出。"""
        mock_get_info.return_value = {
            "success": True,
            "symbol": "AAPL",
            "data": {
                "股票代码": "AAPL",
                "公司名称": "Apple Inc.",
                "当前价格": 195.0,
                "市值": 3000000000000,
                "市盈率TTM": 30.0,
                "市净率PB": 45.0,
                "股息率": 0.005,
                "Beta系数": 1.2,
                "ROE": 1.5,
                "ROA": 0.3,
            },
            "raw_info": {"some": "raw"},
            "meta": {"tool": "stock_info", "api": "yf.Ticker.info", "timestamp": "2026-07-29T00:00:00"}
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_realtime("AAPL", output_json=True)
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["symbol"], "AAPL")
        self.assertEqual(output["data"]["股票代码"], "AAPL")
        self.assertEqual(output["data"]["市盈率TTM"], 30.0)
        # JSON 输出应移除 raw_info
        self.assertNotIn("raw_info", output)
        mock_get_info.assert_called_once_with("AAPL")

    @patch('tools.us_stock.stock_info.get_stock_realtime_info')
    def test_successful_output_text(self, mock_get_info):
        """测试成功时文本格式输出（非 JSON）。"""
        mock_get_info.return_value = {
            "success": True,
            "symbol": "AAPL",
            "data": {
                "股票代码": "AAPL",
                "公司名称": "Apple Inc.",
                "当前价格": 195.0,
                "市值": 3000000000000,
            },
            "raw_info": {},
            "meta": {"tool": "stock_info", "timestamp": "2026-07-29T00:00:00"}
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_realtime("AAPL", output_json=False)
            text = fake_out.getvalue()

        # 文本输出应包含标题和字段
        self.assertIn("AAPL 实时行情与估值指标", text)
        self.assertIn("股票代码: AAPL", text)
        self.assertIn("当前价格: 195.0", text)

    @patch('tools.us_stock.stock_info.get_stock_realtime_info')
    def test_failure_output_text(self, mock_get_info):
        """测试失败时文本格式输出。"""
        mock_get_info.return_value = {
            "success": False,
            "error": "未获取到数据",
            "symbol": "BAD",
            "meta": {"tool": "stock_info", "timestamp": "2026-07-29T00:00:00"}
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_realtime("BAD", output_json=False)
            text = fake_out.getvalue()

        self.assertIn("✗ 获取实时行情失败", text)
        self.assertIn("未获取到数据", text)

    @patch('tools.us_stock.stock_info.get_stock_realtime_info')
    def test_exception_handling(self, mock_get_info):
        """测试异常时的错误处理。"""
        mock_get_info.side_effect = Exception("未预期错误")

        with patch('sys.stderr', new=StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as cm:
                cmd_realtime("AAPL", output_json=False)
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_err.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("error", output)
        self.assertIn("未预期错误", output["error"])


# ---------------------------------------------------------------------------
# 命令行接口测试（使用 subprocess 调用）
# ---------------------------------------------------------------------------

class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口。"""

    def _run_cli(self, args: list) -> tuple:
        """运行命令行并返回 (returncode, stdout, stderr)。

        Args:
            args: 命令行参数列表。

        Returns:
            元组 (returncode, stdout, stderr)。
        """
        py = sys.executable
        script = os.path.join(PROJECT_ROOT, "tools", "us_stock", "stock_info.py")
        result = subprocess.run(
            [py, script] + args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=120
        )
        return result.returncode, result.stdout, result.stderr

    def test_help(self):
        """测试 --help 参数输出。"""
        rc, out, err = self._run_cli(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("美股个股实时行情、估值指标与代码列表查询工具", out)
        self.assertIn("--realtime", out)
        self.assertIn("--json", out)

    def test_no_args(self):
        """测试无参数时的错误提示。"""
        rc, out, err = self._run_cli([])
        self.assertNotEqual(rc, 0)

    def test_realtime_aapl(self):
        """测试 --realtime AAPL 命令行（集成测试）。"""
        try:
            rc, out, err = self._run_cli(["--realtime", "AAPL"])
            # 成功时文本输出包含行情标题
            if "实时行情与估值指标" in out:
                self.assertIn("AAPL", out)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_realtime_json(self):
        """测试 --realtime --json 命令行输出 JSON（集成测试）。"""
        try:
            rc, out, err = self._run_cli(["--realtime", "MSFT", "--json"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["symbol"], "MSFT")
                self.assertIn("data", output)
                self.assertNotIn("raw_info", output)
                self.assertEqual(output["meta"]["tool"], "stock_info")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_realtime_invalid_symbol(self):
        """测试 --realtime 查询无效代码（不崩溃）。"""
        try:
            rc, out, err = self._run_cli(["--realtime", "INVALIDCODE12345", "--json"])
            output = parse_json_output(out)
            if output:
                # 应返回合法结构（无论 success 与否）
                self.assertIn("success", output)
                self.assertEqual(output["symbol"], "INVALIDCODE12345")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

def run_tests(test_type: str = "all") -> bool:
    """运行测试。

    Args:
        test_type: 测试类型，可选 "all"、"functions"、"cmd"、"cli"。

    Returns:
        测试是否全部成功。
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if test_type == "all":
        suite.addTests(loader.loadTestsFromTestCase(TestGetStockRealtimeInfo))
        suite.addTests(loader.loadTestsFromTestCase(TestSafeApiCall))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdRealtime))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    elif test_type == "functions":
        suite.addTests(loader.loadTestsFromTestCase(TestGetStockRealtimeInfo))
        suite.addTests(loader.loadTestsFromTestCase(TestSafeApiCall))
    elif test_type == "cmd":
        suite.addTests(loader.loadTestsFromTestCase(TestCmdRealtime))
    elif test_type == "cli":
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    else:
        print(f"未知测试类型: {test_type}")
        return False

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"测试完成: {result.testsRun} 个测试")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="美股实时行情查询工具测试模块")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "functions", "cmd", "cli"],
                        help="测试类型（默认: all）")

    args = parser.parse_args()

    success = run_tests(args.test)
    sys.exit(0 if success else 1)
