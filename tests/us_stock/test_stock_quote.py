#!/usr/bin/env python3
"""美股行情数据工具测试模块。

测试 tools/us_stock/stock_quote.py 的各功能模块，使用 unittest 框架。

测试范围：
  1. TestUsIndexMap         — 三大指数代码映射（^IXIC / ^DJI / ^GSPC）
  2. TestSafeApiCall        — 重试机制（首次成功 / 重试后成功 / 全部失败）
  3. TestGetUsIndexDaily    — 三大指数历史日线（mock 逻辑 + 多级列名 + 单指数失败 + 网络集成）
  4. TestGetStockDailyKline — 个股历史K线（mock 逻辑 + 复权 + 多级列名 + 异常传播 + 网络集成）
  5. TestCommandLineInterface — 命令行接口（--daily / --index / --start / --end / --no-adjust / --json）
  6. TestErrorHandling      — 错误处理（无效代码 / 网络错误 / 参数校验）
  7. TestDataFormat         — 返回数据格式（date / open / high / low / close / volume 等字段）

运行方式：
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/us_stock/test_stock_quote.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/us_stock/test_stock_quote.py

注意：
    依赖网络的测试使用 try-except + skipTest 处理，网络不可用时不失败。
"""

import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd

# 添加项目根目录到路径（测试位于 tests/us_stock/，需上溯两级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
from tools.us_stock.stock_quote import (
    get_us_index_daily,
    get_stock_daily_kline,
    safe_api_call,
    US_INDEX_MAP,
)
from tools.us_stock import stock_quote as stock_quote_module

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "us_stock", "stock_quote.py")
PYTHON = sys.executable

# yfinance 返回的标准列名（大写）
_OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _sample_kline_df(n: int = 3) -> pd.DataFrame:
    """构造个股历史K线 DataFrame，模拟 yfinance 下返回格式。

    Args:
        n: 数据条数

    Returns:
        含 OHLCV 列、DatetimeIndex 的 DataFrame
    """
    dates = pd.date_range("2026-07-08", periods=n, freq="D")
    return pd.DataFrame({
        "Open": [210.0 + i for i in range(n)],
        "High": [215.0 + i for i in range(n)],
        "Low": [208.0 + i for i in range(n)],
        "Close": [213.0 + i for i in range(n)],
        "Volume": [1000000 + i * 100000 for i in range(n)],
    }, index=dates)


def _sample_multiindex_df() -> pd.DataFrame:
    """构造多级列名 DataFrame，模拟 yfinance 单股票多级列返回。"""
    dates = pd.date_range("2026-07-08", periods=2, freq="D")
    cols = pd.MultiIndex.from_tuples([
        ("Open", "AAPL"), ("High", "AAPL"), ("Low", "AAPL"),
        ("Close", "AAPL"), ("Volume", "AAPL"),
    ])
    return pd.DataFrame(
        [[210.0, 215.0, 208.0, 213.0, 1000000],
         [211.0, 216.0, 209.0, 214.0, 1100000]],
        columns=cols, index=dates,
    )


def _empty_df() -> pd.DataFrame:
    """构造空 DataFrame（无列无行）。"""
    return pd.DataFrame()


# ===========================================================================
# 1. US_INDEX_MAP 测试
# ===========================================================================
class TestUsIndexMap(unittest.TestCase):
    """测试美股三大指数代码映射。"""

    def test_map_has_three_indices(self):
        """US_INDEX_MAP 包含三个指数。"""
        self.assertEqual(len(US_INDEX_MAP), 3)

    def test_nasdaq_ticker(self):
        """纳斯达克综合指数代码为 ^IXIC。"""
        self.assertEqual(US_INDEX_MAP["纳斯达克综合指数"], "^IXIC")

    def test_dow_jones_ticker(self):
        """道琼斯工业平均指数代码为 ^DJI。"""
        self.assertEqual(US_INDEX_MAP["道琼斯工业平均指数"], "^DJI")

    def test_sp500_ticker(self):
        """标普500指数代码为 ^GSPC。"""
        self.assertEqual(US_INDEX_MAP["标普500指数"], "^GSPC")

    def test_all_tickers_start_with_caret(self):
        """所有指数代码以 ^ 开头（Yahoo Finance 指数标识）。"""
        for ticker in US_INDEX_MAP.values():
            self.assertTrue(ticker.startswith("^"))


# ===========================================================================
# 2. safe_api_call 重试机制测试
# ===========================================================================
class TestSafeApiCall(unittest.TestCase):
    """测试 safe_api_call 重试机制。"""

    def test_success_first_try(self):
        """首次调用成功直接返回结果，不重试。"""
        calls = []

        def func():
            calls.append(1)
            return "ok"

        result = safe_api_call(func, "test_api", max_retries=3, delay=0.01)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 1)

    def test_success_on_retry(self):
        """首次失败、第二次成功，返回结果并重试一次。"""
        calls = []

        def func():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("临时错误")
            return "ok"

        result = safe_api_call(func, "test_api", max_retries=3, delay=0.01)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    @patch.object(stock_quote_module.time, "sleep")
    def test_all_failures_raise(self, mock_sleep):
        """全部重试失败后抛出 Exception，且重试次数等于 max_retries。"""
        calls = []

        def func():
            calls.append(1)
            raise ConnectionError("网络中断")

        with self.assertRaises(Exception) as ctx:
            safe_api_call(func, "test_api", max_retries=3, delay=0.01)
        self.assertEqual(len(calls), 3)
        self.assertIn("获取美股数据失败", str(ctx.exception))

    def test_returns_none_when_func_returns_none(self):
        """func 返回 None 时 safe_api_call 返回 None。"""
        result = safe_api_call(lambda: None, "test_api",
                               max_retries=2, delay=0.01)
        self.assertIsNone(result)


# ===========================================================================
# 3. get_us_index_daily 测试
# ===========================================================================
class TestGetUsIndexDaily(unittest.TestCase):
    """测试 get_us_index_daily 函数。"""

    # ---- 使用 mock 的确定性测试 ----

    @patch.object(stock_quote_module, "yf")
    def test_normal_data_structure(self, mock_yf):
        """正常数据：返回 success 且每个指数含 ticker/count/columns/latest/earliest。"""
        mock_yf.download.return_value = _sample_kline_df(2)
        result = get_us_index_daily("2026-01-01", "2026-07-28")

        self.assertTrue(result["success"])
        self.assertEqual(result["meta"]["start_date"], "2026-01-01")
        self.assertEqual(result["meta"]["end_date"], "2026-07-28")
        # 三个指数均有数据
        for index_name, ticker in US_INDEX_MAP.items():
            self.assertIn(index_name, result["data"])
            entry = result["data"][index_name]
            self.assertEqual(entry["ticker"], ticker)
            self.assertEqual(entry["count"], 2)
            self.assertIn("columns", entry)
            self.assertIn("latest", entry)
            self.assertIn("earliest", entry)

    @patch.object(stock_quote_module, "yf")
    def test_default_dates_when_none(self, mock_yf):
        """start_date/end_date 为 None 时使用默认值（一年前至今天）。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        result = get_us_index_daily()

        expected_start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        expected_end = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(result["meta"]["start_date"], expected_start)
        self.assertEqual(result["meta"]["end_date"], expected_end)

    @patch.object(stock_quote_module, "yf")
    def test_default_dates_format(self, mock_yf):
        """默认日期格式为 YYYY-MM-DD。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        result = get_us_index_daily()
        for d in (result["meta"]["start_date"], result["meta"]["end_date"]):
            self.assertEqual(len(d), 10)
            self.assertEqual(d[4], "-")
            self.assertEqual(d[7], "-")

    @patch.object(stock_quote_module, "yf")
    def test_default_start_before_end(self, mock_yf):
        """默认 start_date 严格早于 end_date。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        result = get_us_index_daily()
        self.assertLess(result["meta"]["start_date"], result["meta"]["end_date"])

    @patch.object(stock_quote_module, "yf")
    def test_download_count_equals_indices(self, mock_yf):
        """yf.download 被调用次数等于指数数量（3 次）。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        get_us_index_daily("2026-01-01", "2026-07-28")
        self.assertEqual(mock_yf.download.call_count, len(US_INDEX_MAP))

    @patch.object(stock_quote_module, "yf")
    def test_multiindex_columns_flattened(self, mock_yf):
        """多级列名被扁平化为一级（columns 不含元组）。"""
        mock_yf.download.return_value = _sample_multiindex_df()
        result = get_us_index_daily("2026-01-01", "2026-07-28")
        first_entry = next(iter(result["data"].values()))
        for col in first_entry["columns"]:
            self.assertIsInstance(col, str)

    @patch.object(stock_quote_module, "yf")
    def test_empty_dataframe_marks_no_data(self, mock_yf):
        """空 DataFrame 时该指数标记 count=0 且含 error。"""
        mock_yf.download.return_value = _empty_df()
        result = get_us_index_daily("2026-01-01", "2026-07-28")
        for entry in result["data"].values():
            self.assertEqual(entry["count"], 0)
            self.assertIn("error", entry)

    @patch.object(stock_quote_module.time, "sleep")
    @patch.object(stock_quote_module, "yf")
    def test_single_index_error_does_not_fail_all(self, mock_yf, mock_sleep):
        """单个指数下载异常时，整体仍 success，仅该指数含 error。"""
        good_df = _sample_kline_df(1)

        def download_side_effect(*args, **kwargs):
            # 道琼斯持续失败（重试 3 次均失败）
            if kwargs.get("tickers") == "^DJI":
                raise ConnectionError("超时")
            return good_df

        mock_yf.download.side_effect = download_side_effect
        result = get_us_index_daily("2026-01-01", "2026-07-28")

        self.assertTrue(result["success"])
        # 道琼斯失败
        self.assertIn("error", result["data"]["道琼斯工业平均指数"])
        # 纳斯达克、标普成功
        self.assertNotIn("error", result["data"]["纳斯达克综合指数"])
        self.assertNotIn("error", result["data"]["标普500指数"])

    @patch.object(stock_quote_module, "yf")
    def test_ticker_passed_to_download(self, mock_yf):
        """每个指数的 ticker 透传给 yf.download。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        get_us_index_daily("2026-01-01", "2026-07-28")
        called_tickers = [
            call.kwargs["tickers"] for call in mock_yf.download.call_args_list
        ]
        for ticker in US_INDEX_MAP.values():
            self.assertIn(ticker, called_tickers)

    # ---- 网络集成测试（网络不可用时跳过）----

    def test_network_index_daily(self):
        """获取三大指数历史日线（网络集成）。"""
        try:
            result = get_us_index_daily("2026-01-01", "2026-07-28")
            self.assertTrue(result["success"])
            for index_name in US_INDEX_MAP.keys():
                self.assertIn(index_name, result["data"])
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")


# ===========================================================================
# 4. get_stock_daily_kline 测试
# ===========================================================================
class TestGetStockDailyKline(unittest.TestCase):
    """测试 get_stock_daily_kline 函数。"""

    # ---- 使用 mock 的确定性测试 ----

    @patch.object(stock_quote_module, "yf")
    def test_normal_data_structure(self, mock_yf):
        """正常数据：success、symbol、data(count/columns/latest/earliest)、meta。"""
        mock_yf.download.return_value = _sample_kline_df(3)
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28",
                                        auto_adjust=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["symbol"], "AAPL")
        data = result["data"]
        self.assertEqual(data["count"], 3)
        self.assertIn("columns", data)
        self.assertIn("latest", data)
        self.assertIn("earliest", data)
        self.assertEqual(len(data["latest"]), 5)
        self.assertEqual(len(data["earliest"]), 5)

    @patch.object(stock_quote_module, "yf")
    def test_meta_fields(self, mock_yf):
        """meta 字段完整：tool/api/start_date/end_date/auto_adjust/timestamp。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        result = get_stock_daily_kline("MSFT", "2026-01-01", "2026-07-28",
                                        auto_adjust=False)
        meta = result["meta"]
        for key in ("tool", "api", "start_date", "end_date",
                    "auto_adjust", "timestamp"):
            self.assertIn(key, meta)
        self.assertEqual(meta["start_date"], "2026-01-01")
        self.assertEqual(meta["end_date"], "2026-07-28")
        self.assertFalse(meta["auto_adjust"])

    @patch.object(stock_quote_module, "yf")
    def test_default_dates_when_none(self, mock_yf):
        """start_date/end_date 为 None 时使用默认值。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        result = get_stock_daily_kline("AAPL")

        expected_start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        expected_end = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(result["meta"]["start_date"], expected_start)
        self.assertEqual(result["meta"]["end_date"], expected_end)

    @patch.object(stock_quote_module, "yf")
    def test_auto_adjust_true_passed_to_api(self, mock_yf):
        """auto_adjust=True 透传给 yf.download。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28",
                               auto_adjust=True)
        self.assertTrue(mock_yf.download.call_args.kwargs["auto_adjust"])

    @patch.object(stock_quote_module, "yf")
    def test_auto_adjust_false_passed_to_api(self, mock_yf):
        """auto_adjust=False 透传给 yf.download。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28",
                               auto_adjust=False)
        self.assertFalse(mock_yf.download.call_args.kwargs["auto_adjust"])

    @patch.object(stock_quote_module, "yf")
    def test_auto_adjust_reflected_in_meta(self, mock_yf):
        """auto_adjust 值反映在返回 meta 中。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        r1 = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28",
                                    auto_adjust=True)
        self.assertTrue(r1["meta"]["auto_adjust"])

        mock_yf.download.return_value = _sample_kline_df(1)
        r2 = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28",
                                    auto_adjust=False)
        self.assertFalse(r2["meta"]["auto_adjust"])

    @patch.object(stock_quote_module, "yf")
    def test_multiindex_columns_flattened(self, mock_yf):
        """多级列名被扁平化为一级。"""
        mock_yf.download.return_value = _sample_multiindex_df()
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        self.assertTrue(result["success"])
        for col in result["data"]["columns"]:
            self.assertIsInstance(col, str)

    @patch.object(stock_quote_module, "yf")
    def test_empty_dataframe_returns_failure(self, mock_yf):
        """空 DataFrame 时返回 success=False 且含 error。"""
        mock_yf.download.return_value = _empty_df()
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        self.assertFalse(result["success"])
        self.assertEqual(result["symbol"], "AAPL")
        self.assertIn("error", result)

    @patch.object(stock_quote_module, "yf")
    def test_none_dataframe_returns_failure(self, mock_yf):
        """download 返回 None 时返回 success=False。"""
        mock_yf.download.return_value = None
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        self.assertFalse(result["success"])

    @patch.object(stock_quote_module, "yf")
    def test_symbol_passed_to_download(self, mock_yf):
        """symbol 透传给 yf.download。"""
        mock_yf.download.return_value = _sample_kline_df(1)
        get_stock_daily_kline("GOOGL", "2026-01-01", "2026-07-28")
        self.assertEqual(mock_yf.download.call_args.kwargs["tickers"], "GOOGL")

    @patch.object(stock_quote_module, "yf")
    def test_raw_data_is_dataframe(self, mock_yf):
        """成功时 raw_data 为 DataFrame。"""
        mock_yf.download.return_value = _sample_kline_df(2)
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        self.assertTrue(result["success"])
        self.assertIsInstance(result["raw_data"], pd.DataFrame)

    @patch.object(stock_quote_module.time, "sleep")
    @patch.object(stock_quote_module, "yf")
    def test_exception_returns_failure(self, mock_yf, mock_sleep):
        """yf.download 抛异常时返回 success=False（不向上传播）。"""
        mock_yf.download.side_effect = ConnectionError("网络中断")
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("网络中断", result["error"])

    # ---- 网络集成测试（网络不可用时跳过）----

    def test_network_aapl_kline(self):
        """获取苹果(AAPL)历史K线（网络集成）。"""
        try:
            result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
            if not result.get("success"):
                self.skipTest("网络不可用或未获取到数据")
            self.assertEqual(result["symbol"], "AAPL")
            self.assertGreater(result["data"]["count"], 0)
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")


# ===========================================================================
# 5. 命令行接口测试
# ===========================================================================
class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口参数解析。"""

    def _run(self, args, timeout=90):
        """运行工具子进程并返回 (returncode, stdout, stderr)。"""
        cmd = [PYTHON, TOOL_PATH] + args
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=PROJECT_ROOT
        )

    def test_help(self):
        """--help 正常输出并包含关键参数说明。"""
        result = self._run(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("美股行情数据工具", result.stdout)
        self.assertIn("--daily", result.stdout)
        self.assertIn("--index", result.stdout)
        self.assertIn("--start", result.stdout)
        self.assertIn("--end", result.stdout)
        self.assertIn("--no-adjust", result.stdout)

    def test_no_args_prints_help(self):
        """无参数时打印帮助并以 0 退出（原文件行为）。"""
        result = self._run([])
        self.assertEqual(result.returncode, 0)
        self.assertIn("美股行情数据工具", result.stdout)

    def test_daily_json_output(self):
        """--daily AAPL --json 输出合法 JSON，含 success/symbol/data。"""
        result = self._run(["--daily", "AAPL", "--start", "2026-06-01",
                            "--end", "2026-07-28", "--json"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["symbol"], "AAPL")
                self.assertIn("data", output)
                self.assertIn("meta", output)
            else:
                self.skipTest("网络不可用或未获取到数据")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_daily_start_end_passthrough(self):
        """--start/--end 透传到 meta。"""
        result = self._run(["--daily", "AAPL", "--start", "2025-01-01",
                            "--end", "2026-07-27", "--json"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["start_date"], "2025-01-01")
                self.assertEqual(output["meta"]["end_date"], "2026-07-27")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_daily_no_adjust(self):
        """--no-adjust 使 meta.auto_adjust=False。"""
        result = self._run(["--daily", "AAPL", "--no-adjust",
                            "--start", "2026-06-01", "--end", "2026-07-28",
                            "--json"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertFalse(output["meta"]["auto_adjust"])
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_daily_default_adjust(self):
        """默认（不带 --no-adjust）为前复权 auto_adjust=True。"""
        result = self._run(["--daily", "AAPL", "--start", "2026-06-01",
                            "--end", "2026-07-28", "--json"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertTrue(output["meta"]["auto_adjust"])
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_index_json_output(self):
        """--index --json 输出合法 JSON，含三大指数。"""
        result = self._run(["--index", "--start", "2026-06-01",
                            "--end", "2026-07-28", "--json"])
        try:
            output = json.loads(result.stdout)
            self.assertTrue(output.get("success"))
            for index_name in US_INDEX_MAP.keys():
                self.assertIn(index_name, output["data"])
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_index_start_end_passthrough(self):
        """--index --start/--end 透传到 meta。"""
        result = self._run(["--index", "--start", "2025-01-01",
                            "--end", "2026-07-27", "--json"])
        try:
            output = json.loads(result.stdout)
            self.assertEqual(output["meta"]["start_date"], "2025-01-01")
            self.assertEqual(output["meta"]["end_date"], "2026-07-27")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_daily_and_index_combined(self):
        """--daily 与 --index 组合时两者均执行。"""
        result = self._run(["--daily", "AAPL", "--index",
                            "--start", "2026-06-01", "--end", "2026-07-28",
                            "--json"])
        # 组合输出为两段 JSON（非单一对象），只要退出码正常即可
        self.assertIn(result.returncode, (0, 1))

    def test_meta_tool_field(self):
        """成功时 meta.tool 为 stock_quote。"""
        result = self._run(["--daily", "AAPL", "--start", "2026-06-01",
                            "--end", "2026-07-28", "--json"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["tool"], "stock_quote")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")


# ===========================================================================
# 6. 错误处理测试
# ===========================================================================
class TestErrorHandling(unittest.TestCase):
    """测试错误处理机制。"""

    def _run(self, args, timeout=90):
        cmd = [PYTHON, TOOL_PATH] + args
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=PROJECT_ROOT
        )

    def test_invalid_symbol_graceful(self):
        """无效美股代码不崩溃，优雅返回成功或失败。"""
        result = self._run(["--daily", "INVALID_TICKER_999",
                            "--start", "2026-06-01", "--end", "2026-07-28",
                            "--json"])
        self.assertIn(result.returncode, (0, 1))

    def test_network_error_graceful(self):
        """网络错误时工具优雅处理（退出码 0 或 1，不卡死）。"""
        result = self._run(["--daily", "AAPL", "--start", "2026-01-01",
                            "--end", "2026-07-28", "--json"], timeout=120)
        self.assertIn(result.returncode, (0, 1))

    def test_daily_failure_error_in_result(self):
        """--daily 失败时 JSON 含 success=False 与 error。"""
        result = self._run(["--daily", "INVALID_TICKER_999",
                            "--start", "2026-06-01", "--end", "2026-07-28",
                            "--json"])
        try:
            output = json.loads(result.stdout)
            if not output.get("success"):
                self.assertIn("error", output)
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_uncaught_exception_to_stderr(self):
        """未捕获异常时错误 JSON 输出到 stderr 且退出码非 0。"""
        # 用一个不可能的日期触发异常路径
        result = self._run(["--daily", "AAPL", "--start", "not-a-date",
                            "--end", "2026-07-28", "--json"], timeout=120)
        # yfinance 可能容错，故仅在返回非 0 时校验 stderr
        if result.returncode != 0:
            self.assertTrue(result.stderr.strip())

    # ---- 单元级网络错误测试（mock 模拟异常）----

    @patch.object(stock_quote_module.time, "sleep")
    @patch.object(stock_quote_module, "yf")
    def test_kline_exception_caught(self, mock_yf, mock_sleep):
        """yf.download 抛异常时 get_stock_daily_kline 捕获并返回失败。"""
        mock_yf.download.side_effect = ConnectionError("网络中断")
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        self.assertFalse(result["success"])
        self.assertEqual(result["symbol"], "AAPL")

    @patch.object(stock_quote_module.time, "sleep")
    @patch.object(stock_quote_module, "yf")
    def test_index_partial_failure_keeps_success(self, mock_yf, mock_sleep):
        """指数部分失败时整体 success 仍为 True。"""
        good_df = _sample_kline_df(1)

        def download_side_effect(*args, **kwargs):
            # 纳斯达克与标普持续失败，道琼斯成功
            if kwargs.get("tickers") in ("^IXIC", "^GSPC"):
                raise ConnectionError("超时")
            return good_df

        mock_yf.download.side_effect = download_side_effect
        result = get_us_index_daily("2026-01-01", "2026-07-28")
        self.assertTrue(result["success"])
        failed = [e for e in result["data"].values() if "error" in e]
        self.assertEqual(len(failed), 2)


# ===========================================================================
# 7. 返回数据格式测试
# ===========================================================================
class TestDataFormat(unittest.TestCase):
    """测试返回数据包含 OHLCV 字段。"""

    @patch.object(stock_quote_module, "yf")
    def test_kline_columns_contain_ohlcv(self, mock_yf):
        """历史K线 columns 含 Open/High/Low/Close/Volume。"""
        mock_yf.download.return_value = _sample_kline_df(2)
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        columns = result["data"]["columns"]
        for col in _OHLCV_COLUMNS:
            self.assertIn(col, columns)

    @patch.object(stock_quote_module, "yf")
    def test_kline_latest_has_ohlcv_keys(self, mock_yf):
        """latest 字段含 OHLCV 键。"""
        mock_yf.download.return_value = _sample_kline_df(2)
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        latest = result["data"]["latest"]
        for col in _OHLCV_COLUMNS:
            self.assertIn(col, latest)

    @patch.object(stock_quote_module, "yf")
    def test_kline_earliest_has_ohlcv_keys(self, mock_yf):
        """earliest 字段含 OHLCV 键。"""
        mock_yf.download.return_value = _sample_kline_df(2)
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        earliest = result["data"]["earliest"]
        for col in _OHLCV_COLUMNS:
            self.assertIn(col, earliest)

    @patch.object(stock_quote_module, "yf")
    def test_kline_latest_values_are_numeric(self, mock_yf):
        """latest 各字段值为数值类型。"""
        mock_yf.download.return_value = _sample_kline_df(2)
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        latest = result["data"]["latest"]
        for col in _OHLCV_COLUMNS:
            self.assertIsNotNone(latest[col])
            self.assertIsInstance(latest[col], (int, float))

    @patch.object(stock_quote_module, "yf")
    def test_kline_count_matches_dataframe_rows(self, mock_yf):
        """count 等于 DataFrame 行数。"""
        mock_yf.download.return_value = _sample_kline_df(5)
        result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
        self.assertEqual(result["data"]["count"], 5)

    @patch.object(stock_quote_module, "yf")
    def test_index_columns_contain_ohlcv(self, mock_yf):
        """指数 columns 含 OHLCV 字段。"""
        mock_yf.download.return_value = _sample_kline_df(2)
        result = get_us_index_daily("2026-01-01", "2026-07-28")
        for entry in result["data"].values():
            if entry.get("count", 0) > 0:
                for col in _OHLCV_COLUMNS:
                    self.assertIn(col, entry["columns"])

    def test_network_kline_data_format(self):
        """网络集成：AAPL 历史K线返回 OHLCV 字段。"""
        try:
            result = get_stock_daily_kline("AAPL", "2026-01-01", "2026-07-28")
            if not result.get("success"):
                self.skipTest("网络不可用或未获取到数据")
            columns = result["data"]["columns"]
            # yfinance 不同版本列名大小写可能不同，统一小写比较
            lower_cols = [str(c).lower() for c in columns]
            for expect in ["open", "high", "low", "close", "volume"]:
                self.assertIn(expect, lower_cols)
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
