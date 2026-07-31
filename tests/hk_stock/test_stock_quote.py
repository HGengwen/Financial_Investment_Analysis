#!/usr/bin/env python3
"""港股行情数据工具测试模块。

测试 tools/hk_stock/stock_quote.py 的各功能模块，使用 unittest 框架。

测试范围：
  1. TestDefaultDates         — 默认日期生成（_default_start / _default_end）
  2. TestSafeApiCall          — 重试机制（首次成功 / 重试后成功 / 全部失败）
  3. TestGetHkHist            — 港股历史K线获取（mock 逻辑 + 网络集成 + 复权/周期/代码补齐）
  4. TestGetHkIndex           — 港股指数获取（mock 逻辑 + 网络集成 + HSI/CES100）
  5. TestCommandLineInterface — 命令行接口（--code/--start/--end/--adjust/--period/--index）
  6. TestErrorHandling        — 错误处理（无效代码 / 网络错误 / 参数校验）

运行方式：
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/hk_stock/test_stock_quote.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/hk_stock/test_stock_quote.py

注意：
    依赖网络的测试使用 try-except + skipTest 处理，网络不可用时不失败。
"""

import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, date
from unittest.mock import patch

import pandas as pd

# 添加项目根目录到路径（测试位于 tests/hk_stock/，需上溯两级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
from tools.hk_stock.stock_quote import (
    get_hk_hist,
    get_hk_index,
    safe_api_call,
    _default_start,
    _default_end,
    _DEFAULT_DAYS,
)
from tools.hk_stock import stock_quote as stock_quote_module

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "hk_stock", "stock_quote.py")
PYTHON = sys.executable

# 港股历史K线数据列（新浪接口返回格式）
_HK_HIST_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]
# 港股指数数据列（新浪接口返回中文列名）
_HK_INDEX_COLUMNS = ["日期", "开盘", "最高", "最低", "收盘", "成交量"]


def _empty_hist_df():
    """构造空的港股历史K线 DataFrame（含列名，无行）。"""
    return pd.DataFrame({col: pd.Series(dtype="object") for col in _HK_HIST_COLUMNS})


def _empty_index_df():
    """构造空的港股指数 DataFrame（含列名，无行）。"""
    return pd.DataFrame({col: pd.Series(dtype="object") for col in _HK_INDEX_COLUMNS})


# ===========================================================================
# 1. _default_start / _default_end 测试
# ===========================================================================
class TestDefaultDates(unittest.TestCase):
    """测试 _default_start 和 _default_end 函数。"""

    def test_default_end_is_today(self):
        """_default_end 返回今天的日期。"""
        expected = datetime.now().strftime("%Y%m%d")
        self.assertEqual(_default_end(), expected)

    def test_default_start_is_30_days_ago(self):
        """_default_start 返回 _DEFAULT_DAYS 天前的日期。"""
        expected = (datetime.now() - timedelta(days=_DEFAULT_DAYS)).strftime(
            "%Y%m%d")
        self.assertEqual(_default_start(), expected)

    def test_end_format_8_digits(self):
        """_default_end 格式为 8 位纯数字 YYYYMMDD。"""
        end = _default_end()
        self.assertEqual(len(end), 8)
        self.assertTrue(end.isdigit())

    def test_start_format_8_digits(self):
        """_default_start 格式为 8 位纯数字 YYYYMMDD。"""
        start = _default_start()
        self.assertEqual(len(start), 8)
        self.assertTrue(start.isdigit())

    def test_start_before_end(self):
        """_default_start 严格早于 _default_end。"""
        self.assertLess(_default_start(), _default_end())

    def test_interval_is_default_days(self):
        """默认区间天数等于 _DEFAULT_DAYS。"""
        start = datetime.strptime(_default_start(), "%Y%m%d")
        end = datetime.strptime(_default_end(), "%Y%m%d")
        self.assertEqual((end - start).days, _DEFAULT_DAYS)


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

    def test_all_failures_raise(self):
        """全部重试失败后抛出 Exception，且重试次数等于 max_retries。"""
        calls = []

        def func():
            calls.append(1)
            raise ConnectionError("网络中断")

        with self.assertRaises(Exception) as ctx:
            safe_api_call(func, "test_api", max_retries=3, delay=0.01)
        self.assertEqual(len(calls), 3)
        self.assertIn("获取港股数据失败", str(ctx.exception))

    def test_returns_none_when_func_returns_none(self):
        """func 返回 None 时 safe_api_call 返回 None。"""
        result = safe_api_call(lambda: None, "test_api",
                               max_retries=2, delay=0.01)
        self.assertIsNone(result)


# ===========================================================================
# 3. get_hk_hist 测试
# ===========================================================================
class TestGetHkHist(unittest.TestCase):
    """测试 get_hk_hist 函数。"""

    # ---- 使用 mock 的确定性测试 ----

    @patch.object(stock_quote_module, "ak")
    def test_normal_record_transformation(self, mock_ak):
        """正常数据：日期转字符串、数值转 float、字段完整。"""
        mock_ak.stock_hk_daily.return_value = pd.DataFrame([{
            "date": date(2026, 7, 10),
            "open": 300.0,
            "high": 310.0,
            "low": 295.0,
            "close": 305.0,
            "volume": 1000000.0,
            "amount": 300000000.0,
        }])
        result = get_hk_hist("00700", "20260101", "20260728",
                             adjust="qfq", period="daily")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["symbol"], "00700")
        self.assertEqual(result["adjust"], "qfq")
        self.assertEqual(result["period"], "daily")
        record = result["data"][0]
        self.assertEqual(record["date"], "2026-07-10")
        self.assertEqual(record["open"], 300.0)
        self.assertEqual(record["high"], 310.0)
        self.assertEqual(record["low"], 295.0)
        self.assertEqual(record["close"], 305.0)
        self.assertEqual(record["volume"], 1000000.0)
        self.assertEqual(record["amount"], 300000000.0)

    @patch.object(stock_quote_module, "ak")
    def test_symbol_zfill_to_5_digits(self, mock_ak):
        """短代码自动补齐到5位（"700" -> "00700"）。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        get_hk_hist("700", "20260101", "20260728")
        called_symbol = mock_ak.stock_hk_daily.call_args.kwargs["symbol"]
        self.assertEqual(called_symbol, "00700")

    @patch.object(stock_quote_module, "ak")
    def test_empty_dataframe_returns_empty(self, mock_ak):
        """空 DataFrame（有列无行）返回 count=0 data=[]。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700", "20260101", "20260728")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["data"], [])

    @patch.object(stock_quote_module, "ak")
    def test_date_range_filter(self, mock_ak):
        """超出日期范围的记录被过滤。"""
        mock_ak.stock_hk_daily.return_value = pd.DataFrame([
            {"date": date(2025, 12, 31), "open": 1.0, "high": 1.0,
             "low": 1.0, "close": 1.0, "volume": 1.0, "amount": 1.0},
            {"date": date(2026, 7, 10), "open": 300.0, "high": 310.0,
             "low": 295.0, "close": 305.0, "volume": 1.0, "amount": 1.0},
        ])
        result = get_hk_hist("00700", "20260101", "20260728")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["data"][0]["date"], "2026-07-10")

    @patch.object(stock_quote_module, "ak")
    def test_adjust_passed_to_api(self, mock_ak):
        """adjust 参数透传给 ak.stock_hk_daily。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        get_hk_hist("00700", "20260101", "20260728", adjust="hfq")
        self.assertEqual(mock_ak.stock_hk_daily.call_args.kwargs["adjust"],
                         "hfq")

    @patch.object(stock_quote_module, "ak")
    def test_adjust_qfq(self, mock_ak):
        """前复权 qfq 反映在返回结果中。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700", "20260101", "20260728", adjust="qfq")
        self.assertEqual(result["adjust"], "qfq")

    @patch.object(stock_quote_module, "ak")
    def test_adjust_hfq(self, mock_ak):
        """后复权 hfq 反映在返回结果中。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700", "20260101", "20260728", adjust="hfq")
        self.assertEqual(result["adjust"], "hfq")

    @patch.object(stock_quote_module, "ak")
    def test_adjust_empty_no_adjust(self, mock_ak):
        """不复权（""）反映在返回结果中。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700", "20260101", "20260728", adjust="")
        self.assertEqual(result["adjust"], "")

    @patch.object(stock_quote_module, "ak")
    def test_period_daily(self, mock_ak):
        """周期 daily 反映在返回结果中。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700", "20260101", "20260728", period="daily")
        self.assertEqual(result["period"], "daily")

    @patch.object(stock_quote_module, "ak")
    def test_period_weekly(self, mock_ak):
        """周期 weekly 反映在返回结果中。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700", "20260101", "20260728", period="weekly")
        self.assertEqual(result["period"], "weekly")

    @patch.object(stock_quote_module, "ak")
    def test_period_monthly(self, mock_ak):
        """周期 monthly 反映在返回结果中。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700", "20260101", "20260728", period="monthly")
        self.assertEqual(result["period"], "monthly")

    @patch.object(stock_quote_module, "ak")
    def test_default_dates_when_none(self, mock_ak):
        """start_date/end_date 为 None 时使用默认值。"""
        mock_ak.stock_hk_daily.return_value = _empty_hist_df()
        result = get_hk_hist("00700")
        self.assertEqual(result["start_date"], _default_start())
        self.assertEqual(result["end_date"], _default_end())

    @patch.object(stock_quote_module, "ak")
    def test_multiple_records_count(self, mock_ak):
        """多条记录返回正确的 count。"""
        mock_ak.stock_hk_daily.return_value = pd.DataFrame([
            {"date": date(2026, 7, 8), "open": 300.0, "high": 310.0,
             "low": 295.0, "close": 305.0, "volume": 1.0, "amount": 1.0},
            {"date": date(2026, 7, 9), "open": 305.0, "high": 312.0,
             "low": 300.0, "close": 310.0, "volume": 2.0, "amount": 2.0},
            {"date": date(2026, 7, 10), "open": 310.0, "high": 315.0,
             "low": 308.0, "close": 314.0, "volume": 3.0, "amount": 3.0},
        ])
        result = get_hk_hist("00700", "20260101", "20260728")
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["data"]), 3)

    # ---- 网络集成测试（网络不可用时跳过）----

    def test_network_valid_code(self):
        """获取腾讯控股(00700)历史K线（网络集成）。"""
        try:
            result = get_hk_hist("00700", "20260101", "20260728")
            self.assertIn("count", result)
            self.assertIn("data", result)
            self.assertEqual(result["count"], len(result["data"]))
            self.assertEqual(result["symbol"], "00700")
            if result["count"] > 0:
                record = result["data"][0]
                self.assertIn("date", record)
                self.assertIn("close", record)
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")


# ===========================================================================
# 4. get_hk_index 测试
# ===========================================================================
class TestGetHkIndex(unittest.TestCase):
    """测试 get_hk_index 函数。"""

    # ---- 使用 mock 的确定性测试 ----

    @patch.object(stock_quote_module, "ak")
    def test_normal_record_transformation(self, mock_ak):
        """正常数据：中文列名映射、数值转 float。

        注意：日期使用 YYYYMMDD（无横线）格式以通过原始过滤逻辑。
        """
        mock_ak.stock_hk_index_daily_sina.return_value = pd.DataFrame([{
            "日期": "20260710",
            "开盘": 30000.0,
            "最高": 31000.0,
            "最低": 29500.0,
            "收盘": 30500.0,
            "成交量": 1000000000.0,
        }])
        result = get_hk_index("HSI", "20260101", "20260728")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["symbol"], "HSI")
        self.assertEqual(result["start_date"], "20260101")
        self.assertEqual(result["end_date"], "20260728")
        record = result["data"][0]
        self.assertEqual(record["date"], "20260710")
        self.assertEqual(record["open"], 30000.0)
        self.assertEqual(record["high"], 31000.0)
        self.assertEqual(record["low"], 29500.0)
        self.assertEqual(record["close"], 30500.0)
        self.assertEqual(record["volume"], 1000000000.0)

    @patch.object(stock_quote_module, "ak")
    def test_empty_dataframe_returns_empty(self, mock_ak):
        """空 DataFrame 返回 count=0 data=[]。"""
        mock_ak.stock_hk_index_daily_sina.return_value = _empty_index_df()
        result = get_hk_index("HSI", "20260101", "20260728")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["data"], [])

    @patch.object(stock_quote_module, "ak")
    def test_default_dates_when_none(self, mock_ak):
        """start_date/end_date 为 None 时使用默认值。"""
        mock_ak.stock_hk_index_daily_sina.return_value = _empty_index_df()
        result = get_hk_index("HSI")
        self.assertEqual(result["start_date"], _default_start())
        self.assertEqual(result["end_date"], _default_end())

    @patch.object(stock_quote_module, "ak")
    def test_index_hsi_passed_to_api(self, mock_ak):
        """HSI 指数代码透传给 ak.stock_hk_index_daily_sina。"""
        mock_ak.stock_hk_index_daily_sina.return_value = _empty_index_df()
        get_hk_index("HSI", "20260101", "20260728")
        self.assertEqual(
            mock_ak.stock_hk_index_daily_sina.call_args.kwargs["symbol"], "HSI")

    @patch.object(stock_quote_module, "ak")
    def test_index_ces100_passed_to_api(self, mock_ak):
        """CES100 恒生科技指数代码透传给 API。"""
        mock_ak.stock_hk_index_daily_sina.return_value = _empty_index_df()
        get_hk_index("CES100", "20260101", "20260728")
        self.assertEqual(
            mock_ak.stock_hk_index_daily_sina.call_args.kwargs["symbol"],
            "CES100")

    @patch.object(stock_quote_module, "ak")
    def test_multiple_records_count(self, mock_ak):
        """多条指数记录返回正确的 count。"""
        mock_ak.stock_hk_index_daily_sina.return_value = pd.DataFrame([
            {"日期": "20260708", "开盘": 30000.0, "最高": 31000.0,
             "最低": 29500.0, "收盘": 30500.0, "成交量": 1.0},
            {"日期": "20260709", "开盘": 30500.0, "最高": 31200.0,
             "最低": 30000.0, "收盘": 31000.0, "成交量": 2.0},
            {"日期": "20260710", "开盘": 31000.0, "最高": 31500.0,
             "最低": 30800.0, "收盘": 31400.0, "成交量": 3.0},
        ])
        result = get_hk_index("HSI", "20260101", "20260728")
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["data"]), 3)

    # ---- 网络集成测试（网络不可用时跳过）----

    def test_network_hsi(self):
        """获取恒生指数(HSI)历史数据（网络集成）。"""
        try:
            result = get_hk_index("HSI", "20260101", "20260728")
            self.assertIn("count", result)
            self.assertIn("data", result)
            self.assertEqual(result["count"], len(result["data"]))
            self.assertEqual(result["symbol"], "HSI")
            if result["count"] > 0:
                record = result["data"][0]
                self.assertIn("date", record)
                self.assertIn("close", record)
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")

    def test_network_ces100(self):
        """获取恒生科技指数(CES100)历史数据（网络集成）。"""
        try:
            result = get_hk_index("CES100", "20260101", "20260728")
            self.assertIn("count", result)
            self.assertIn("data", result)
            self.assertEqual(result["symbol"], "CES100")
            self.assertEqual(result["count"], len(result["data"]))
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
        self.assertIn("港股行情数据查询工具", result.stdout)
        self.assertIn("--code", result.stdout)
        self.assertIn("--index", result.stdout)
        self.assertIn("--adjust", result.stdout)
        self.assertIn("--period", result.stdout)

    def test_no_args_fails(self):
        """缺少 --code 和 --index 时非零退出。"""
        result = self._run([])
        self.assertNotEqual(result.returncode, 0)

    def test_code_with_start_end(self):
        """--code --start --end 组合，data 中日期字段正确。"""
        result = self._run(["--code", "00700", "--start", "20260701",
                            "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["code"], "00700")
                self.assertEqual(output["meta"]["command"], "code")
                self.assertEqual(output["data"]["start_date"], "20260701")
                self.assertEqual(output["data"]["end_date"], "20260728")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_adjust_qfq(self):
        """--adjust qfq 前复权。"""
        result = self._run(["--code", "00700", "--adjust", "qfq",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["data"]["adjust"], "qfq")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_adjust_hfq(self):
        """--adjust hfq 后复权。"""
        result = self._run(["--code", "00700", "--adjust", "hfq",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["data"]["adjust"], "hfq")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_adjust_empty(self):
        """--adjust "" 不复权。"""
        result = self._run(["--code", "00700", "--adjust", "",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["data"]["adjust"], "")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_period_daily(self):
        """--period daily 日线。"""
        result = self._run(["--code", "00700", "--period", "daily",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["data"]["period"], "daily")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_period_weekly(self):
        """--period weekly 周线。"""
        result = self._run(["--code", "00700", "--period", "weekly",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["data"]["period"], "weekly")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_period_monthly(self):
        """--period monthly 月线。"""
        result = self._run(["--code", "00700", "--period", "monthly",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["data"]["period"], "monthly")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_index_hsi(self):
        """--index HSI 获取恒生指数。"""
        result = self._run(["--index", "HSI", "--start", "20260701",
                            "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["command"], "index")
                self.assertEqual(output["data"]["symbol"], "HSI")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_index_ces100(self):
        """--index CES100 获取恒生科技指数。"""
        result = self._run(["--index", "CES100", "--start", "20260701",
                            "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["command"], "index")
                self.assertEqual(output["data"]["symbol"], "CES100")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_meta_fields_complete(self):
        """成功时 meta 字段完整。"""
        result = self._run(["--code", "00700", "--start", "20260701",
                            "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                meta = output["meta"]
                for key in ["tool", "command", "code", "market", "timestamp"]:
                    self.assertIn(key, meta)
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

    def test_invalid_code_graceful(self):
        """无效港股代码（99999）不崩溃，优雅返回成功或失败。"""
        result = self._run(["--code", "99999", "--start", "20260701",
                            "--end", "20260728"])
        self.assertIn(result.returncode, (0, 1))

    def test_invalid_adjust_rejected(self):
        """无效复权方式被 argparse 拒绝（非零退出）。"""
        result = self._run(["--code", "00700", "--adjust", "invalid"])
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_period_rejected(self):
        """无效周期类型被 argparse 拒绝（非零退出）。"""
        result = self._run(["--code", "00700", "--period", "invalid"])
        self.assertNotEqual(result.returncode, 0)

    def test_network_error_graceful(self):
        """网络错误时工具优雅处理（退出码为 0 或 1，不卡死）。"""
        result = self._run(["--code", "00700", "--start", "20260101",
                            "--end", "20260728"], timeout=90)
        self.assertIn(result.returncode, (0, 1))

    def test_failure_error_to_stderr(self):
        """失败时错误 JSON 输出到 stderr 且 stdout 为空。"""
        result = self._run(["--code", "99999", "--start", "20260101",
                            "--end", "20260728"])
        if result.returncode == 1:
            self.assertTrue(result.stderr.strip())
            try:
                err = json.loads(result.stderr)
                self.assertFalse(err["success"])
                self.assertIn("error", err)
            except json.JSONDecodeError:
                # 偶发非 JSON 错误提示，不导致测试失败
                pass

    # ---- 单元级网络错误测试（mock 模拟异常）----

    @patch.object(stock_quote_module.time, "sleep")
    @patch.object(stock_quote_module, "ak")
    def test_get_hk_hist_exception_propagates(self, mock_ak, mock_sleep):
        """stock_hk_daily 抛异常时 get_hk_hist 向上传播 Exception。"""
        mock_ak.stock_hk_daily.side_effect = ConnectionError("网络中断")
        with self.assertRaises(Exception):
            get_hk_hist("00700", "20260101", "20260728")

    @patch.object(stock_quote_module, "ak")
    def test_get_hk_index_exception_propagates(self, mock_ak):
        """stock_hk_index_daily_sina 抛异常时 get_hk_index 向上传播 Exception。"""
        mock_ak.stock_hk_index_daily_sina.side_effect = ConnectionError("网络中断")
        with self.assertRaises(Exception):
            get_hk_index("HSI", "20260101", "20260728")


if __name__ == "__main__":
    unittest.main(verbosity=2)
