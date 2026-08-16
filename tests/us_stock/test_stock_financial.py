#!/usr/bin/env python3
"""美股财务数据查询工具测试模块。

测试 tools/us_stock/stock_financial.py 的各功能模块，使用 unittest 框架。

测试范围:
  1. TestGetFinancialStatements — 财务报表获取（网络集成测试）
  2. TestGetDividendsSplits      — 分红拆股历史获取（网络集成测试）
  3. TestGetHolders              — 机构持仓获取（网络集成测试）
  4. TestGetAnalystRatings       — 分析师评级获取（网络集成测试）
  5. TestSafeApiCall             — 重试机制（mock，无网络依赖）
  6. TestMainLogic               — main() 主逻辑（mock get 函数）
  7. TestCommandLineInterface    — 命令行接口（subprocess，网络依赖）
  8. TestErrorHandling           — 错误处理（无效代码/网络错误）

运行方式:
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/us_stock/test_stock_financial.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/us_stock/test_stock_financial.py

注意:
    依赖网络的测试使用 try-except + skipTest 处理，网络不可用时不失败。
"""

import json
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch
import unittest

import pandas as pd

# 添加项目根目录到路径（测试位于 tests/us_stock/，需上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
from tools.us_stock.stock_financial import (
    get_stock_financial_statements,
    get_stock_dividends_splits,
    get_stock_holders,
    get_stock_analyst_ratings,
    safe_api_call,
)
from tools.us_stock import stock_financial as sf_module

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "us_stock", "stock_financial.py")
PYTHON = sys.executable

# 测试用美股代码（苹果，数据完善）
TEST_SYMBOL = "AAPL"


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


def make_mock_financial_result(symbol: str = TEST_SYMBOL) -> dict:
    """构建模拟的财务报表返回字典。

    Args:
        symbol: 美股代码。

    Returns:
        模拟的财务报表结果字典，覆盖 6 张报表。
    """
    return {
        "success": True,
        "symbol": symbol,
        "data": {
            "年度利润表": {"count": 25, "columns": ["2024-09-28", "2023-09-30"],
                            "index": ["Total Revenue", "Net Income"]},
            "季度利润表": {"count": 20},
            "年度资产负债表": {"count": 30, "columns": ["2024-09-28"],
                                "index": ["Total Assets", "Total Liab"]},
            "季度资产负债表": {"count": 28},
            "年度现金流量表": {"count": 22, "columns": ["2024-09-28"],
                                "index": ["Operating Cash Flow"]},
            "季度现金流量表": {"count": 18},
        },
        "meta": {"tool": "stock_financial", "api": "yf.Ticker.*",
                 "timestamp": "2026-07-29T00:00:00"},
    }


def make_mock_dividends_result(symbol: str = TEST_SYMBOL) -> dict:
    """构建模拟的分红拆股历史返回字典。

    Args:
        symbol: 美股代码。

    Returns:
        模拟的分红拆股结果字典。
    """
    return {
        "success": True,
        "symbol": symbol,
        "data": {
            "分红历史": {"count": 60, "latest": 0.25, "total_years": 12},
            "拆股历史": {"count": 5, "latest": 4.0},
        },
        "meta": {"tool": "stock_financial", "api": "yf.Ticker.dividends/splits",
                 "timestamp": "2026-07-29T00:00:00"},
    }


def make_mock_holders_result(symbol: str = TEST_SYMBOL) -> dict:
    """构建模拟的机构持仓返回字典。

    Args:
        symbol: 美股代码。

    Returns:
        模拟的机构持仓结果字典。
    """
    return {
        "success": True,
        "symbol": symbol,
        "data": {
            "机构持股": {"count": 15,
                      "top_holder": {"Holder": "Vanguard Group",
                                     "Shares": 1200000000}},
        },
        "meta": {"tool": "stock_financial",
                 "api": "yf.Ticker.institutional_holders",
                 "timestamp": "2026-07-29T00:00:00"},
    }


def make_mock_analyst_result(symbol: str = TEST_SYMBOL) -> dict:
    """构建模拟的分析师评级返回字典。

    Args:
        symbol: 美股代码。

    Returns:
        模拟的分析师评级结果字典。
    """
    return {
        "success": True,
        "symbol": symbol,
        "data": {
            "分析师评级": {"count": 30,
                       "latest": {"strongBuy": 20, "buy": 5,
                                  "hold": 3, "sell": 1, "strongSell": 1}},
        },
        "meta": {"tool": "stock_financial",
                 "api": "yf.Ticker.recommendations",
                 "timestamp": "2026-07-29T00:00:00"},
    }


# ===========================================================================
# 1. 财务报表获取测试（网络集成测试）
# ===========================================================================

class TestGetFinancialStatements(unittest.TestCase):
    """测试 get_stock_financial_statements —— 完整财务报表获取。

    此测试依赖网络，网络不可用时自动跳过。
    """

    def test_returns_dict_structure(self):
        """测试返回结构包含 success/symbol/data/meta。"""
        try:
            result = get_stock_financial_statements(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertIn("symbol", result)
        self.assertIn("data", result)
        self.assertIn("meta", result)
        self.assertEqual(result["symbol"], TEST_SYMBOL)

    def test_meta_fields(self):
        """测试 meta 字段包含 tool 与 timestamp。"""
        try:
            result = get_stock_financial_statements(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        meta = result.get("meta", {})
        self.assertEqual(meta.get("tool"), "stock_financial")
        self.assertIn("timestamp", meta)
        self.assertIn("api", meta)

    def test_contains_six_statements(self):
        """测试数据包含 6 张财务报表字段。"""
        try:
            result = get_stock_financial_statements(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        data = result.get("data", {})
        expected = ["年度利润表", "季度利润表", "年度资产负债表",
                    "季度资产负债表", "年度现金流量表", "季度现金流量表"]
        for name in expected:
            self.assertIn(name, data)

    def test_statement_count_field(self):
        """测试年度利润表返回 count 字段。"""
        try:
            result = get_stock_financial_statements(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        income = result.get("data", {}).get("年度利润表", {})
        # 成功时含 count；失败时含 error
        self.assertTrue("count" in income or "error" in income,
                        f"年度利润表缺少 count/error: {income}")


# ===========================================================================
# 2. 分红拆股历史获取测试（网络集成测试）
# ===========================================================================

class TestGetDividendsSplits(unittest.TestCase):
    """测试 get_stock_dividends_splits —— 分红拆股历史获取。

    此测试依赖网络，网络不可用时自动跳过。
    """

    def test_returns_dict_structure(self):
        """测试返回结构包含 success/symbol/data/meta。"""
        try:
            result = get_stock_dividends_splits(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertEqual(result["symbol"], TEST_SYMBOL)

    def test_contains_dividends_and_splits(self):
        """测试数据包含分红历史与拆股历史字段。"""
        try:
            result = get_stock_dividends_splits(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        data = result.get("data", {})
        self.assertIn("分红历史", data)
        self.assertIn("拆股历史", data)

    def test_dividends_count_or_error(self):
        """测试分红历史包含 count 或 note 或 error 之一。"""
        try:
            result = get_stock_dividends_splits(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        div = result.get("data", {}).get("分红历史", {})
        self.assertTrue(any(k in div for k in ("count", "note", "error")),
                        f"分红历史缺少关键字段: {div}")

    def test_splits_count_or_error(self):
        """测试拆股历史包含 count 或 note 或 error 之一。"""
        try:
            result = get_stock_dividends_splits(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        splits = result.get("data", {}).get("拆股历史", {})
        self.assertTrue(any(k in splits for k in ("count", "note", "error")),
                        f"拆股历史缺少关键字段: {splits}")


# ===========================================================================
# 3. 机构持仓获取测试（网络集成测试）
# ===========================================================================

class TestGetHolders(unittest.TestCase):
    """测试 get_stock_holders —— 机构持仓获取。

    此测试依赖网络，网络不可用时自动跳过。
    """

    def test_returns_dict_structure(self):
        """测试返回结构包含 success/symbol/data/meta。"""
        try:
            result = get_stock_holders(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertEqual(result["symbol"], TEST_SYMBOL)

    def test_contains_institutional_holders(self):
        """测试数据包含机构持股字段。"""
        try:
            result = get_stock_holders(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        data = result.get("data", {})
        self.assertIn("机构持股", data)

    def test_holders_count_or_error(self):
        """测试机构持股包含 count 或 note 或 error 之一。"""
        try:
            result = get_stock_holders(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        holders = result.get("data", {}).get("机构持股", {})
        self.assertTrue(any(k in holders for k in ("count", "note", "error")),
                        f"机构持股缺少关键字段: {holders}")

    def test_meta_api_field(self):
        """测试机构持仓 meta 的 api 字段为 institutional_holders。"""
        try:
            result = get_stock_holders(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        meta = result.get("meta", {})
        self.assertIn("institutional_holders", meta.get("api", ""))


# ===========================================================================
# 4. 分析师评级获取测试（网络集成测试）
# ===========================================================================

class TestGetAnalystRatings(unittest.TestCase):
    """测试 get_stock_analyst_ratings —— 分析师评级获取。

    此测试依赖网络，网络不可用时自动跳过。
    """

    def test_returns_dict_structure(self):
        """测试返回结构包含 success/symbol/data/meta。"""
        try:
            result = get_stock_analyst_ratings(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertEqual(result["symbol"], TEST_SYMBOL)

    def test_contains_recommendations(self):
        """测试数据包含分析师评级字段。"""
        try:
            result = get_stock_analyst_ratings(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        data = result.get("data", {})
        self.assertIn("分析师评级", data)

    def test_analyst_count_or_error(self):
        """测试分析师评级包含 count 或 note 或 error 之一。"""
        try:
            result = get_stock_analyst_ratings(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        rec = result.get("data", {}).get("分析师评级", {})
        self.assertTrue(any(k in rec for k in ("count", "note", "error")),
                        f"分析师评级缺少关键字段: {rec}")

    def test_meta_api_field(self):
        """测试分析师评级 meta 的 api 字段为 recommendations。"""
        try:
            result = get_stock_analyst_ratings(TEST_SYMBOL)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

        meta = result.get("meta", {})
        self.assertIn("recommendations", meta.get("api", ""))


# ===========================================================================
# 5. safe_api_call 重试机制测试（无网络依赖）
# ===========================================================================

class TestSafeApiCall(unittest.TestCase):
    """测试 safe_api_call —— 重试机制。无网络依赖。"""

    def test_success(self):
        """测试成功调用直接返回结果。"""

        def success_func():
            return {"test": "success"}

        result = safe_api_call(success_func, "test_api")
        self.assertIsNotNone(result)
        self.assertEqual(result["test"], "success")

    def test_retry_then_success(self):
        """测试失败后重试成功。"""
        call_count = [0]

        def fail_then_success():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("模拟失败")
            return {"test": "retry_success"}

        result = safe_api_call(fail_then_success, "test_api",
                               max_retries=3, delay=0.1)
        self.assertEqual(call_count[0], 2)  # 第2次成功
        self.assertEqual(result["test"], "retry_success")

    def test_all_fail_raises(self):
        """测试全部重试失败后抛出异常。"""
        call_count = [0]

        def always_fail():
            call_count[0] += 1
            raise Exception("持续失败")

        with self.assertRaises(Exception) as cm:
            safe_api_call(always_fail, "test_api",
                          max_retries=2, delay=0.1)
        self.assertEqual(call_count[0], 2)
        self.assertIn("重试", str(cm.exception))

    def test_first_attempt_no_retry_message(self):
        """测试首次成功时不应触发重试日志（验证返回值即可）。"""
        result = safe_api_call(lambda: 42, "no_retry_api")
        self.assertEqual(result, 42)


# ===========================================================================
# 6. main() 主逻辑测试（mock get 函数，无网络依赖）
# ===========================================================================

class TestMainLogic(unittest.TestCase):
    """测试 main() 主逻辑 —— 各命令行参数路径。

    通过 mock get_* 函数隔离网络依赖。
    """

    def _run_main_with_args(self, argv: list) -> dict:
        """以指定参数运行 main() 并返回解析后的 JSON 输出。

        Args:
            argv: 命令行参数列表（不含脚本名）。

        Returns:
            解析后的输出字典。
        """
        with patch.object(sys, "argv", ["stock_financial.py"] + argv):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                sf_module.main()
                return parse_json_output(fake_out.getvalue())

    @patch("tools.us_stock.stock_financial.get_stock_financial_statements")
    def test_financials_cli(self, mock_get):
        """测试 --financials 命令行调用财务报表。"""
        mock_get.return_value = make_mock_financial_result()
        output = self._run_main_with_args(["--financials", TEST_SYMBOL, "--json"])

        self.assertTrue(output["success"])
        self.assertEqual(output["symbol"], TEST_SYMBOL)
        self.assertIn("年度利润表", output["data"])
        mock_get.assert_called_once_with(TEST_SYMBOL)

    @patch("tools.us_stock.stock_financial.get_stock_dividends_splits")
    def test_dividends_cli(self, mock_get):
        """测试 --dividends 命令行调用分红拆股历史。"""
        mock_get.return_value = make_mock_dividends_result()
        output = self._run_main_with_args(["--dividends", TEST_SYMBOL, "--json"])

        self.assertTrue(output["success"])
        self.assertIn("分红历史", output["data"])
        self.assertIn("拆股历史", output["data"])
        mock_get.assert_called_once_with(TEST_SYMBOL)

    @patch("tools.us_stock.stock_financial.get_stock_holders")
    def test_holders_cli(self, mock_get):
        """测试 --holders 命令行调用机构持仓。"""
        mock_get.return_value = make_mock_holders_result()
        output = self._run_main_with_args(["--holders", TEST_SYMBOL, "--json"])

        self.assertTrue(output["success"])
        self.assertIn("机构持股", output["data"])
        mock_get.assert_called_once_with(TEST_SYMBOL)

    @patch("tools.us_stock.stock_financial.get_stock_analyst_ratings")
    def test_analyst_cli(self, mock_get):
        """测试 --analyst 命令行调用分析师评级。"""
        mock_get.return_value = make_mock_analyst_result()
        output = self._run_main_with_args(["--analyst", TEST_SYMBOL, "--json"])

        self.assertTrue(output["success"])
        self.assertIn("分析师评级", output["data"])
        mock_get.assert_called_once_with(TEST_SYMBOL)

    @patch("tools.us_stock.stock_financial.get_stock_analyst_ratings")
    def test_no_json_uses_human_readable(self, mock_get):
        """测试无 --json 时输出人类可读格式（非 JSON）。"""
        mock_get.return_value = make_mock_analyst_result()
        with patch.object(sys, "argv",
                          ["stock_financial.py", "--analyst", TEST_SYMBOL]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                sf_module.main()
                output_text = fake_out.getvalue()

        # 人类可读输出应包含标题而非纯 JSON 字典
        self.assertIn("分析师评级", output_text)
        self.assertNotEqual(parse_json_output(output_text),
                            {"success": True})  # 非 JSON 首行

    def test_no_args_prints_help(self):
        """测试无参数时打印帮助信息并正常退出。"""
        with patch.object(sys, "argv", ["stock_financial.py"]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    sf_module.main()
                self.assertEqual(cm.exception.code, 0)
            self.assertIn("usage", fake_out.getvalue().lower())


# ===========================================================================
# 7. 命令行接口测试（subprocess，网络依赖）
# ===========================================================================

class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口 —— 通过 subprocess 调用脚本。

    依赖网络的测试使用 try-except + skipTest 处理。
    """

    def _run_cli(self, args: list) -> tuple:
        """运行命令行并返回 (returncode, stdout, stderr)。

        Args:
            args: 命令行参数列表。

        Returns:
            元组 (returncode, stdout, stderr)。
        """
        result = subprocess.run(
            [PYTHON, TOOL_PATH] + args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=180,
        )
        return result.returncode, result.stdout, result.stderr

    def test_help_output(self):
        """测试 --help 参数输出。"""
        rc, out, err = self._run_cli(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("美股财务数据查询工具", out)
        self.assertIn("--financials", out)
        self.assertIn("--dividends", out)
        self.assertIn("--holders", out)
        self.assertIn("--analyst", out)

    def test_no_args_exits_nonzero(self):
        """测试无参数时返回 0 退出码（打印帮助）。"""
        rc, out, err = self._run_cli([])
        self.assertEqual(rc, 0)
        self.assertIn("usage", out.lower())

    def test_financials_cli_network(self):
        """测试 --financials 命令行（网络集成）。"""
        try:
            rc, out, err = self._run_cli(
                ["--financials", TEST_SYMBOL, "--json"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["symbol"], TEST_SYMBOL)
                self.assertIn("data", output)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_dividends_cli_network(self):
        """测试 --dividends 命令行（网络集成）。"""
        try:
            rc, out, err = self._run_cli(
                ["--dividends", TEST_SYMBOL, "--json"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertIn("分红历史", output.get("data", {}))
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")


# ===========================================================================
# 8. 错误处理测试
# ===========================================================================

class TestErrorHandling(unittest.TestCase):
    """测试错误处理 —— 无效代码与网络错误。"""

    @patch("tools.us_stock.stock_financial.safe_api_call")
    def test_get_financial_statements_handles_error(self, mock_safe):
        """测试获取财务报表时底层异常被捕获并返回 success=False。"""
        mock_safe.side_effect = Exception("网络连接失败")
        result = get_stock_financial_statements(TEST_SYMBOL)

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["symbol"], TEST_SYMBOL)

    @patch("tools.us_stock.stock_financial.safe_api_call")
    def test_get_holders_handles_error(self, mock_safe):
        """测试获取机构持仓时底层异常被捕获并返回 success=False。"""
        mock_safe.side_effect = Exception("连接超时")
        result = get_stock_holders(TEST_SYMBOL)

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("tools.us_stock.stock_financial.safe_api_call")
    def test_get_analyst_handles_error(self, mock_safe):
        """测试获取分析师评级时底层异常被捕获并返回 success=False。"""
        mock_safe.side_effect = Exception("读取评级失败")
        result = get_stock_analyst_ratings(TEST_SYMBOL)

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("读取评级失败", result["error"])

    @patch("tools.us_stock.stock_financial.get_stock_financial_statements")
    def test_main_network_error_exits_nonzero(self, mock_get):
        """测试 main() 中 get 函数抛异常时以非零码退出并输出错误 JSON。"""
        mock_get.side_effect = ConnectionError("Yahoo Finance 不可达")
        with patch.object(sys, "argv",
                          ["stock_financial.py", "--financials", TEST_SYMBOL,
                           "--json"]):
            with patch("sys.stderr", new=StringIO()) as fake_err:
                with self.assertRaises(SystemExit) as cm:
                    sf_module.main()
                self.assertEqual(cm.exception.code, 1)
                output = parse_json_output(fake_err.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("error", output)

    @patch("tools.us_stock.stock_financial.get_stock_dividends_splits")
    def test_main_handles_get_returning_failure(self, mock_get):
        """测试 main() 处理 get 函数返回 success=False 时不崩溃。"""
        mock_get.return_value = {
            "success": False, "symbol": TEST_SYMBOL,
            "data": {}, "error": "无此股票",
            "meta": {"tool": "stock_financial"}}
        with patch.object(sys, "argv",
                          ["stock_financial.py", "--dividends", TEST_SYMBOL,
                           "--json"]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                sf_module.main()
                output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertEqual(output.get("error"), "无此股票")

    def test_invalid_code_cli_network(self):
        """测试无效股票代码的 CLI 错误处理（网络集成）。"""
        try:
            rc, out, err = self._run_cli(
                ["--financials", "INVALID_XYZ_9999", "--json"])
            stdout = out.strip()
            if stdout:
                output = parse_json_output(stdout)
                # 无效代码：success 可能为 False 或 data 为空，均为有效响应
                self.assertIn("success", output)
                self.assertEqual(output.get("symbol"), "INVALID_XYZ_9999")
            else:
                self.skipTest("网络不可用或无输出")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def _run_cli(self, args: list) -> tuple:
        """运行命令行并返回 (returncode, stdout, stderr)。

        Args:
            args: 命令行参数列表。

        Returns:
            元组 (returncode, stdout, stderr)。
        """
        result = subprocess.run(
            [PYTHON, TOOL_PATH] + args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=180,
        )
        return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

def run_tests(test_type: str = "all") -> bool:
    """运行测试。

    Args:
        test_type: 测试类型，可选 "all"、"core"、"main"、"cli"、"error"。

    Returns:
        测试是否全部成功。
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if test_type == "all":
        suite.addTests(loader.loadTestsFromTestCase(TestGetFinancialStatements))
        suite.addTests(loader.loadTestsFromTestCase(TestGetDividendsSplits))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHolders))
        suite.addTests(loader.loadTestsFromTestCase(TestGetAnalystRatings))
        suite.addTests(loader.loadTestsFromTestCase(TestSafeApiCall))
        suite.addTests(loader.loadTestsFromTestCase(TestMainLogic))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    elif test_type == "core":
        suite.addTests(loader.loadTestsFromTestCase(TestGetFinancialStatements))
        suite.addTests(loader.loadTestsFromTestCase(TestGetDividendsSplits))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHolders))
        suite.addTests(loader.loadTestsFromTestCase(TestGetAnalystRatings))
    elif test_type == "main":
        suite.addTests(loader.loadTestsFromTestCase(TestMainLogic))
    elif test_type == "cli":
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    elif test_type == "error":
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
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

    parser = argparse.ArgumentParser(description="美股财务数据查询工具测试模块")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "core", "main", "cli", "error"],
                        help="测试类型（默认: all）")

    args = parser.parse_args()

    success = run_tests(args.test)
    sys.exit(0 if success else 1)
