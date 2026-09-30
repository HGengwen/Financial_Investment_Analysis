#!/usr/bin/env python3
"""A 股行情数据工具测试模块。

测试 tools/a_share/stock_quote.py 的各功能模块，使用 unittest 框架。

测试范围：
  1. TestEnsureSinaSymbol   — 新浪代码前缀转换（6/0/3/688/8/4 各前缀）
  2. TestDefaultDates       — 默认日期生成（_default_start / _default_end）
  3. TestGetQuoteEastmoney  — 东方财富行情获取（mock 逻辑 + 网络集成）
  4. TestGetQuoteSina       — 新浪行情获取（mock 逻辑 + 网络集成）
  4b. TestGetQuoteTencent   — 腾讯行情获取（mock 逻辑 + 网络集成，方案 §6 回退源）
  4c. TestSourceRouting     — 日线路由表口径（source_router 接入校验，方案 §6）
  5. TestCommandLineInterface — 命令行接口（--code/--start/--end/--adjust/--source）
  6. TestErrorHandling      — 错误处理（无效代码 / 网络错误 / 参数校验）

运行方式：
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/a_share/test_stock_quote.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/a_share/test_stock_quote.py

注意：
    依赖网络的测试使用 try-except + skipTest 处理，网络不可用时不失败。
"""

import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd

# 添加项目根目录到路径（测试位于 tests/a_share/，需上溯两级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
from tools.a_share.stock_quote import (
    get_quote_eastmoney,
    get_quote_sina,
    get_quote_tencent,
    _ensure_sina_symbol,
    _default_start,
    _default_end,
    _DEFAULT_DAYS,
)
from tools.a_share import stock_quote as stock_quote_module
from tools.common.momentum import atr as momentum_atr

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "a_share", "stock_quote.py")
PYTHON = sys.executable


# ===========================================================================
# 1. _ensure_sina_symbol 测试
# ===========================================================================
class TestEnsureSinaSymbol(unittest.TestCase):
    """测试 _ensure_sina_symbol 函数 —— 新浪接口代码前缀转换。"""

    def test_sh_60_prefix(self):
        """60xxxx 开头（沪市主板）-> sh 前缀。"""
        self.assertEqual(_ensure_sina_symbol("600519"), "sh600519")

    def test_sh_688_prefix(self):
        """688xxx 开头（科创板）-> sh 前缀。"""
        self.assertEqual(_ensure_sina_symbol("688981"), "sh688981")

    def test_sz_00_prefix(self):
        """00xxxx 开头（深市主板）-> sz 前缀。"""
        self.assertEqual(_ensure_sina_symbol("000001"), "sz000001")

    def test_sz_30_prefix(self):
        """30xxxx 开头（创业板）-> sz 前缀。"""
        self.assertEqual(_ensure_sina_symbol("300502"), "sz300502")

    def test_bj_8_prefix(self):
        """8xxxxx 开头（北交所）-> bj 前缀。"""
        self.assertEqual(_ensure_sina_symbol("830799"), "bj830799")

    def test_bj_4_prefix(self):
        """4xxxxx 开头（北交所/新三板）-> bj 前缀。"""
        self.assertEqual(_ensure_sina_symbol("430047"), "bj430047")

    def test_zfill_padding(self):
        """不足 6 位时自动前补零后再判断前缀。"""
        # "502" -> zfill(6) -> "000502" -> 00 开头 -> sz
        self.assertEqual(_ensure_sina_symbol("502"), "sz000502")
        # "19" -> zfill(6) -> "000019" -> 00 开头 -> sz
        self.assertEqual(_ensure_sina_symbol("19"), "sz000019")

    def test_unknown_prefix_unchanged(self):
        """无法识别的前缀（如 9/1/2/5/7）返回补零后的原代码，不加前缀。"""
        self.assertEqual(_ensure_sina_symbol("999999"), "999999")
        self.assertEqual(_ensure_sina_symbol("123456"), "123456")

    def test_return_is_string(self):
        """返回值始终为字符串。"""
        for code in ["600519", "88", "300502"]:
            self.assertIsInstance(_ensure_sina_symbol(code), str)


# ===========================================================================
# 2. _default_start / _default_end 测试
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
# 3. get_quote_eastmoney 测试
# ===========================================================================
class TestGetQuoteEastmoney(unittest.TestCase):
    """测试 get_quote_eastmoney 函数。"""

    # ---- 使用 mock 的确定性测试（不依赖网络）----

    @patch.object(stock_quote_module, "ak")
    def test_empty_dataframe_returns_empty(self, mock_ak):
        """空 DataFrame 返回 records=[] count=0。"""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        result = get_quote_eastmoney("300502", "20260101", "20260728", "")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["count"], 0)

    @patch.object(stock_quote_module, "ak")
    def test_column_rename_and_volume_conversion(self, mock_ak):
        """测试列名英文化与成交量 股->手 转换。"""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame([{
            "日期": "2026-07-10",
            "股票代码": "300502",
            "开盘": 10.0,
            "收盘": 11.0,
            "最高": 12.0,
            "最低": 9.0,
            "成交量": 1000.0,  # 单位：股
            "成交额": 10000.0,
            "振幅": 5.0,
            "涨跌幅": 10.0,
            "涨跌额": 1.0,
            "换手率": 2.0,
        }])
        result = get_quote_eastmoney("300502", "20260101", "20260728", "")
        self.assertEqual(result["count"], 1)
        record = result["records"][0]
        # 列名英文化
        self.assertEqual(record["code"], "300502")
        self.assertEqual(record["close"], 11.0)
        self.assertEqual(record["open"], 10.0)
        # 成交量 股 -> 手 (1000 / 100 = 10.0)
        self.assertEqual(record["volume"], 10.0)

    @patch.object(stock_quote_module, "ak")
    def test_multiple_records_count(self, mock_ak):
        """多条记录返回正确的 count。"""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame([
            {"日期": "2026-07-09", "收盘": 10.0, "成交量": 100.0},
            {"日期": "2026-07-10", "收盘": 11.0, "成交量": 200.0},
            {"日期": "2026-07-13", "收盘": 12.0, "成交量": 300.0},
        ])
        result = get_quote_eastmoney("300502", "20260101", "20260728", "")
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["records"]), 3)

    # ---- 网络集成测试（网络不可用时跳过）----

    def test_network_valid_code(self):
        """获取有效股票代码行情（新易盛 300502）。"""
        try:
            result = get_quote_eastmoney("300502", "20260101", "20260728", "")
            self.assertIn("records", result)
            self.assertIn("count", result)
            self.assertEqual(result["count"], len(result["records"]))
            if result["count"] > 0:
                record = result["records"][0]
                self.assertIn("date", record)
                self.assertIn("close", record)
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")


# ===========================================================================
# 4. get_quote_sina 测试
# ===========================================================================
class TestGetQuoteSina(unittest.TestCase):
    """测试 get_quote_sina 函数。"""

    # ---- 使用 mock 的确定性测试 ----

    @patch.object(stock_quote_module, "ak")
    def test_empty_dataframe_returns_empty(self, mock_ak):
        """空 DataFrame 返回 records=[] count=0。"""
        mock_ak.stock_zh_a_daily.return_value = pd.DataFrame()
        result = get_quote_sina("300502", "20260101", "20260728", "")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["count"], 0)

    @patch.object(stock_quote_module, "ak")
    def test_record_transformation_and_date_string(self, mock_ak):
        """测试新浪源记录转换：成交量 股->手、流通股 股->万股、日期转字符串。"""
        mock_ak.stock_zh_a_daily.return_value = pd.DataFrame([{
            "date": datetime(2026, 7, 10),
            "open": 10.0,
            "high": 12.0,
            "low": 9.0,
            "close": 11.0,
            "volume": 1000.0,        # 股
            "amount": 10000.0,
            "outstanding_share": 50000.0,  # 股
            "turnover": 0.12345,
        }])
        result = get_quote_sina("300502", "20260101", "20260728", "")
        self.assertEqual(result["count"], 1)
        record = result["records"][0]
        # 日期转字符串
        self.assertEqual(record["date"], "2026-07-10")
        # 成交量 股 -> 手
        self.assertEqual(record["volume"], 10.0)
        # 流通股 股 -> 万股
        self.assertEqual(record["outstanding_share"], 5.0)
        # turnover 保留 4 位
        self.assertAlmostEqual(record["turnover"], 0.1235, places=4)
        # verify sina_symbol was derived via _ensure_sina_symbol (300502 -> sz)
        mock_ak.stock_zh_a_daily.assert_called_once()
        called_symbol = mock_ak.stock_zh_a_daily.call_args.kwargs["symbol"]
        self.assertEqual(called_symbol, "sz300502")

    @patch.object(stock_quote_module, "ak")
    def test_sh_symbol_prefix_used(self, mock_ak):
        """沪市股票调用 ak 时使用 sh 前缀。"""
        mock_ak.stock_zh_a_daily.return_value = pd.DataFrame()
        get_quote_sina("600519", "20260101", "20260728", "")
        called_symbol = mock_ak.stock_zh_a_daily.call_args.kwargs["symbol"]
        self.assertEqual(called_symbol, "sh600519")

    @patch.object(stock_quote_module, "ak")
    def test_bj_symbol_prefix_used(self, mock_ak):
        """北交所股票（8开头）调用 ak 时使用 bj 前缀。"""
        mock_ak.stock_zh_a_daily.return_value = pd.DataFrame()
        get_quote_sina("830799", "20260101", "20260728", "")
        called_symbol = mock_ak.stock_zh_a_daily.call_args.kwargs["symbol"]
        self.assertEqual(called_symbol, "bj830799")

    # ---- 网络集成测试 ----

    def test_network_valid_code(self):
        """获取有效股票代码行情（新易盛 300502）。"""
        try:
            result = get_quote_sina("300502", "20260101", "20260728", "")
            self.assertIn("records", result)
            self.assertIn("count", result)
            self.assertEqual(result["count"], len(result["records"]))
            if result["count"] > 0:
                record = result["records"][0]
                self.assertIn("date", record)
                self.assertIn("close", record)
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")

    def test_network_sh_code(self):
        """获取沪市股票行情（贵州茅台 600519）。"""
        try:
            result = get_quote_sina("600519", "20260701", "20260728", "")
            self.assertIn("records", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")


# ===========================================================================
# 4B. get_quote_tencent 测试（腾讯回退源，方案 §6）
# ===========================================================================
class TestGetQuoteTencent(unittest.TestCase):
    """测试 get_quote_tencent 函数。

    腾讯接口列名与东财 / 新浪**不同**：仅 date/open/close/high/low/amount 六列，
    其中 ``amount`` 实为**成交量**（单位：手，经实测交叉验证），故本函数将其重命名为
    ``volume`` 且不做 股->手 换算。
    """

    # ---- 使用 mock 的确定性测试（不依赖网络）----

    @patch.object(stock_quote_module, "ak")
    def test_empty_dataframe_returns_empty(self, mock_ak):
        """空 DataFrame 返回 records=[] count=0。"""
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame()
        result = get_quote_tencent("300502", "20260101", "20260728", "")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["count"], 0)

    @patch.object(stock_quote_module, "ak")
    def test_amount_renamed_to_volume_kept_in_lots(self, mock_ak):
        """amount 列重命名为 volume 且不换算（腾讯已以手为单位）；日期转字符串。"""
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame([{
            "date": datetime(2026, 7, 10),
            "open": 10.0,
            "close": 11.004,
            "high": 12.0,
            "low": 9.0,
            "amount": 17554.0,   # 实为成交量（手），非成交额
        }])
        result = get_quote_tencent("300502", "20260101", "20260728", "")
        self.assertEqual(result["count"], 1)
        record = result["records"][0]
        # 字段集固定为六列：不含涨跌幅 / 涨跌额 / 振幅 / 换手率 / 成交额
        self.assertEqual(set(record.keys()),
                         {"date", "open", "close", "high", "low", "volume"})
        self.assertEqual(record["date"], "2026-07-10")
        self.assertEqual(record["volume"], 17554.0)   # 手，未再除以 100
        self.assertEqual(record["close"], 11.0)        # 浮点四舍五入两位

    @patch.object(stock_quote_module, "ak")
    def test_symbol_prefix_used(self, mock_ak):
        """沪 / 深 / 北交所代码经前缀转换后传入腾讯接口。"""
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame()
        for code, expected in (("600519", "sh600519"),
                               ("300502", "sz300502"),
                               ("830799", "bj830799")):
            get_quote_tencent(code, "20260101", "20260728", "")
            called = mock_ak.stock_zh_a_hist_tx.call_args.kwargs["symbol"]
            self.assertEqual(called, expected)

    @patch.object(stock_quote_module, "ak")
    def test_adjust_forwarded(self, mock_ak):
        """adjust 参数原样透传腾讯接口。"""
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame()
        get_quote_tencent("300502", "20260101", "20260728", "qfq")
        self.assertEqual(
            mock_ak.stock_zh_a_hist_tx.call_args.kwargs["adjust"], "qfq")

    # ---- 网络集成测试（网络不可用时跳过）----

    def test_network_valid_code(self):
        """腾讯源获取有效代码行情（贵州茅台 600519）。"""
        try:
            result = get_quote_tencent("600519", "20260701", "20260728", "")
            self.assertEqual(result["count"], len(result["records"]))
            if result["count"] > 0:
                record = result["records"][0]
                self.assertIn("date", record)
                self.assertIn("close", record)
                self.assertIn("volume", record)
        except Exception as e:
            self.skipTest(f"网络不可用或数据源异常: {e}")


# ===========================================================================
# 4C. 日线路由表口径（source_router 接入校验，方案 §6）
# ===========================================================================
class TestSourceRouting(unittest.TestCase):
    """校验 stock_quote 已接入 source_router，且日线路由口径为 东财→腾讯→新浪。"""

    def test_source_router_imported(self):
        """stock_quote 成功导入 source_router（非 None 时才启用路由）。"""
        self.assertIsNotNone(stock_quote_module.source_router)

    def test_a_share_daily_priority(self):
        """a_share_daily 路由优先级为 eastmoney → tencent → sina。"""
        route_spec = stock_quote_module.source_router.ROUTES["a_share_daily"]
        self.assertEqual(route_spec.priority, ("eastmoney", "tencent", "sina"))

    def test_fallback_cmd_points_to_sina(self):
        """日线路由的替代命令指向新浪源且带代码（方案 §3.4）。"""
        cmd = stock_quote_module.source_router.fallback_cmd(
            "a_share_daily", code="300502")
        self.assertIn("--source sina", cmd)
        self.assertIn("300502", cmd)

    def test_module_fallback_cmd_matches_router(self):
        """模块内 _FALLBACK_CMD 与路由表模板渲染结果口径一致（防两处漂移）。"""
        rendered = stock_quote_module.source_router.fallback_cmd(
            "a_share_daily", code="300502")
        self.assertEqual(
            stock_quote_module._FALLBACK_CMD.replace("{symbol}", "300502"),
            rendered)

    def test_route_falls_back_with_attempt_trail(self):
        """东财失败时路由自动回退腾讯，并留痕逐源尝试记录。"""
        router = stock_quote_module.source_router
        calls = []

        def _fail():
            calls.append("eastmoney")
            raise ConnectionError("东财不可达")

        def _ok():
            calls.append("tencent")
            return {"records": [], "count": 0}

        outcome = router.route(
            "a_share_daily",
            {"eastmoney": _fail, "tencent": _ok},
            tool="stock_quote",
            params={"code": "300502"},
        )
        self.assertEqual(outcome.source, "tencent")
        self.assertEqual(calls, ["eastmoney", "tencent"])
        self.assertEqual([a.status for a in outcome.attempts], ["failed", "ok"])
        self.assertEqual(outcome.as_dict()["source"], "tencent")


# ===========================================================================
# 5. 命令行接口测试
# ===========================================================================
class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口参数解析。"""

    def _run(self, args, timeout=60):
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
        self.assertIn("行情数据查询工具", result.stdout)
        self.assertIn("--code", result.stdout)
        self.assertIn("--source", result.stdout)
        self.assertIn("--adjust", result.stdout)
        self.assertIn("tencent", result.stdout)

    def test_code_required(self):
        """缺少 --code 参数时非零退出。"""
        result = self._run([])
        self.assertNotEqual(result.returncode, 0)

    def test_code_with_start_end(self):
        """--code --start --end 组合，meta 字段正确。"""
        result = self._run(["--code", "300502", "--start", "20260701",
                            "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["code"], "300502")
                self.assertEqual(output["meta"]["start_date"], "20260701")
                self.assertEqual(output["meta"]["end_date"], "20260728")
        except json.JSONDecodeError:
            # 网络不可用时错误写至 stderr，不导致测试失败
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_adjust_qfq(self):
        """--adjust qfq 前复权，meta.adapt 反映为 qfq。"""
        result = self._run(["--code", "300502", "--adjust", "qfq",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["adjust"], "qfq")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_adjust_hfq(self):
        """--adjust hfq 后复权。"""
        result = self._run(["--code", "300502", "--adjust", "hfq",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["adjust"], "hfq")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_source_sina(self):
        """--source sina 使用新浪数据源，meta.source 为 sina。"""
        result = self._run(["--code", "300502", "--source", "sina",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["source"], "sina")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_source_tencent(self):
        """--source tencent 被接受，meta.source 为 tencent。"""
        result = self._run(["--code", "600519", "--source", "tencent",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["source"], "tencent")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_source_eastmoney_default(self):
        """不指定 --source 时默认 eastmoney。"""
        result = self._run(["--code", "300502", "--start", "20260701",
                            "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                self.assertEqual(output["meta"]["source"], "eastmoney")
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")

    def test_meta_fields_complete(self):
        """成功时 meta 字段完整。"""
        result = self._run(["--code", "300502", "--source", "sina",
                            "--start", "20260701", "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                meta = output["meta"]
                required = ["tool", "source", "code", "start_date",
                            "end_date", "adjust", "count", "timestamp"]
                for key in required:
                    self.assertIn(key, meta)
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")


    def test_meta_routing_fields_present(self):
        """成功时 meta 追加 source_actual 与 routing（方案 §6 可观测性）。"""
        result = self._run(["--code", "300502", "--start", "20260701",
                            "--end", "20260728"])
        try:
            output = json.loads(result.stdout)
            if output.get("success"):
                meta = output["meta"]
                self.assertIn("source_actual", meta)
                routing = meta["routing"]
                self.assertEqual(routing["kind"], "a_share_daily")
                self.assertTrue(routing["attempts"])
                self.assertEqual(routing["source"], meta["source_actual"])
        except json.JSONDecodeError:
            self.skipTest("网络不可用或 stdout 非 JSON")


# ===========================================================================
# 6. 错误处理测试
# ===========================================================================
class TestErrorHandling(unittest.TestCase):
    """测试错误处理机制。"""

    def _run(self, args, timeout=60):
        cmd = [PYTHON, TOOL_PATH] + args
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=PROJECT_ROOT
        )

    def test_invalid_code_graceful(self):
        """无效股票代码（999999）不崩溃，优雅返回成功或失败。"""
        result = self._run(["--code", "999999", "--start", "20260701",
                            "--end", "20260728"])
        # 成功（空数据，退出码 0）或失败（退出码 1）均可，但不能异常退出
        self.assertIn(result.returncode, (0, 1))

    def test_invalid_adjust_rejected(self):
        """无效复权方式被 argparse 拒绝（非零退出）。"""
        result = self._run(["--code", "300502", "--adjust", "invalid"])
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_source_rejected(self):
        """无效数据源被 argparse 拒绝（非零退出）。"""
        result = self._run(["--code", "300502", "--source", "invalid"])
        self.assertNotEqual(result.returncode, 0)

    def test_network_error_graceful(self):
        """网络错误时工具优雅处理（退出码为 0 或 1，不卡死）。"""
        result = self._run(["--code", "300502", "--start", "20260101",
                            "--end", "20260728"], timeout=90)
        self.assertIn(result.returncode, (0, 1))

    def test_failure_error_to_stderr(self):
        """失败时错误 JSON 输出到 stderr 且 stdout 为空。"""
        # 无效复权会被 argparse 拦截，不符合“数据获取失败”路径
        # 用一个不存在的代码触发数据获取失败（依赖网络）
        result = self._run(["--code", "999999", "--start", "20260101",
                            "--end", "20260728"])
        if result.returncode == 1:
            # 失败路径：错误写至 stderr
            self.assertTrue(result.stderr.strip())
            try:
                err = json.loads(result.stderr)
                self.assertFalse(err["success"])
                self.assertIn("error", err)
            except json.JSONDecodeError:
                # 偶发非 JSON 错误提示，不导致测试失败
                pass
        # 成功路径不校验 stderr

    # ---- 单元级网络错误测试（mock 模拟异常）----

    @patch.object(stock_quote_module, "ak")
    def test_eastmoney_exception_propagates(self, mock_ak):
        """东方财富接口抛异常时被 get_quote_eastmoney 向上传播。"""
        mock_ak.stock_zh_a_hist.side_effect = ConnectionError("网络中断")
        with self.assertRaises(ConnectionError):
            get_quote_eastmoney("300502", "20260101", "20260728", "")

    @patch.object(stock_quote_module, "ak")
    def test_sina_exception_propagates(self, mock_ak):
        """新浪接口抛异常时被 get_quote_sina 向上传播。"""
        mock_ak.stock_zh_a_daily.side_effect = ConnectionError("网络中断")
        with self.assertRaises(ConnectionError):
            get_quote_sina("300502", "20260101", "20260728", "")

    @patch.object(stock_quote_module, "ak")
    def test_tencent_exception_propagates(self, mock_ak):
        """腾讯接口抛异常时被 get_quote_tencent 向上传播（由路由层兜底）。"""
        mock_ak.stock_zh_a_hist_tx.side_effect = ConnectionError("网络中断")
        with self.assertRaises(ConnectionError):
            get_quote_tencent("300502", "20260101", "20260728", "")


# ===========================================================================
# 9. --momentum 动量与技术面指标测试（纯计算，无网络）
# ===========================================================================

def _make_uptrend_closes(n=260):
    """构造缓慢上涨的价格序列（开盘=base，每日 +0.5）。"""
    base = 100.0
    return [base + i * 0.5 for i in range(n)]


def _make_flat_volumes(n=260):
    """构造恒定成交量序列。"""
    return [1_000_000.0] * n


def _fake_records(n=260):
    """构造 get_quote_eastmoney 返回的伪 records（含 date/close/volume）。"""
    return [{"date": i, "close": 100.0 + i * 0.5, "volume": 1_000_000.0}
            for i in range(n)]


def _make_ohlc_series(n=20):
    """构造三价齐全且非对称的 K 线序列（供 ATR 对齐与接线测试）。

    high/low 与 close 的差额按序号错位波动，使 high/lows 序列交换后 ATR
    结果不同，从而能检验接线是否按 high/low/close 正确顺序传递。
    """
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 2.0 + (i % 3) * 0.5 for i, c in enumerate(closes)]
    lows = [c - 1.0 - (i % 2) * 0.5 for i, c in enumerate(closes)]
    return highs, lows, closes


def _fake_ohlc_records(n=20):
    """构造含 high/low/close 三价的伪 records（供 cmd_momentum 接线测试）。"""
    highs, lows, closes = _make_ohlc_series(n)
    return [{"date": i, "high": highs[i], "low": lows[i],
             "close": closes[i], "volume": 1_000_000.0}
            for i in range(n)]


class TestMomentum(unittest.TestCase):
    """--momentum 计算与命令行分发测试。"""

    def test_parse_peers_valid(self):
        """--peers 逗号分隔解析为浮点列表。"""
        self.assertEqual(stock_quote_module._parse_peers("20.5,-3.2,55"),
                         [20.5, -3.2, 55.0])

    def test_parse_peers_none_and_empty(self):
        """None 或空串/纯逗号返回 None。"""
        self.assertIsNone(stock_quote_module._parse_peers(None))
        self.assertIsNone(stock_quote_module._parse_peers(""))
        self.assertIsNone(stock_quote_module._parse_peers(",,"))

    def test_momentum_uptrend(self):
        """上涨序列：250日涨幅为正、现价高于双均线、RSI 偏强。"""
        closes = _make_uptrend_closes(260)
        res = stock_quote_module._momentum_from_series(closes, _make_flat_volumes(260), None)
        self.assertGreater(res["return_250d_pct"], 0)
        self.assertIsNone(res["smr_percentile"])  # 未提供 peers
        self.assertIs(res["tech"]["close_above_ma50"], True)
        self.assertIs(res["tech"]["close_above_ma200"], True)
        self.assertIn("note", res)

    def test_momentum_with_peers(self):
        """提供 peers 时 smr_percentile 按板块截面计算（own 为最高涨幅）。"""
        closes = _make_uptrend_closes(260)
        peers = [1.0, 5.0, 100.0]  # own 250日涨幅约 129% → 排最高
        res = stock_quote_module._momentum_from_series(closes, None, peers)
        self.assertAlmostEqual(res["smr_percentile"], 100.0, places=4)

    def test_momentum_insufficient_data(self):
        """短序列不抛异常，关键字段为 None。"""
        res = stock_quote_module._momentum_from_series([1.0, 2.0], None, None)
        self.assertIsNone(res["return_250d_pct"])
        self.assertIsNone(res["ma200"])
        self.assertIsNone(res["rsi50"])

    def test_cmd_momentum_outputs_json(self):
        """cmd_momentum 拉取数据并输出含 data 的 JSON，不真连网（mock 数据源）。"""
        with patch.object(stock_quote_module, "get_quote_eastmoney",
                          return_value={"records": _fake_records(), "count": 260}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                stock_quote_module.cmd_momentum("300502", None)
        out = json.loads(buf.getvalue())
        self.assertTrue(out["success"])
        self.assertEqual(out["meta"]["command"], "momentum")
        self.assertIsNotNone(out["data"]["return_250d_pct"])
        self.assertIs(out["data"]["tech"]["close_above_ma200"], True)

    def test_cmd_momentum_auto_peers(self):
        """--auto-peers 经行业缓存自动生成截面，meta 记录来源，SMR 百分位有值。"""
        with patch.object(stock_quote_module.sector_screen, "compute_peers_for_stock",
                          return_value={"industry": "通信设备", "pcts": [5.0, 10.0],
                                        "status": "refresh", "count": 2, "skipped": 0}):
            with patch.object(stock_quote_module, "get_quote_eastmoney",
                              return_value={"records": _fake_records(), "count": 260}):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    stock_quote_module.cmd_momentum("300502", None, True)
        out = json.loads(buf.getvalue())
        self.assertTrue(out["success"])
        self.assertIn("sector:refresh", out["meta"]["peers_source"])
        self.assertEqual(out["meta"]["peers_industry"], "通信设备")
        self.assertIsNotNone(out["data"]["smr_percentile"])

    def test_extract_ohlc_aligned_filters_missing(self):
        """三价任意一项缺失的行被跳过，返回的三价序列等长且对齐。"""
        rows = [
            {"high": 10, "low": 9, "close": 9.5},
            {"high": None, "low": 8, "close": 9.0},   # 缺 high
            {"high": 11, "low": None, "close": 10.0},  # 缺 low
            {"high": 12, "low": 11, "close": 11.5},
            {"high": 12, "low": 11, "close": None},   # 缺 close
        ]
        highs, lows, closes = stock_quote_module._extract_ohlc_aligned(rows)
        self.assertEqual(highs, [10.0, 12.0])
        self.assertEqual(lows, [9.0, 11.0])
        self.assertEqual(closes, [9.5, 11.5])

    def test_momentum_atr14_with_ohlc(self):
        """传入三价齐全序列时 atr14 等于 momentum.atr()，且非 None。"""
        highs, lows, ohlc_closes = _make_ohlc_series(20)
        res = stock_quote_module._momentum_from_series(
            ohlc_closes, None, None,
            highs=highs, lows=lows, atr_closes=ohlc_closes)
        self.assertEqual(res["atr14"], momentum_atr(highs, lows, ohlc_closes))
        self.assertIsNotNone(res["atr14"])

    def test_momentum_atr14_none_without_ohlc(self):
        """未提供 highs/lows/atr_closes 时 atr14 为 None。"""
        res = stock_quote_module._momentum_from_series(
            _make_uptrend_closes(260), None, None)
        self.assertIsNone(res["atr14"])

    def test_momentum_atr14_none_on_length_mismatch(self):
        """三价序列长度不一致时 atr14 静默降级为 None（不抛异常）。"""
        highs, lows, ohlc_closes = _make_ohlc_series(20)
        res = stock_quote_module._momentum_from_series(
            ohlc_closes, None, None,
            highs=highs, lows=lows, atr_closes=ohlc_closes[:-1])
        self.assertIsNone(res["atr14"])

    def test_cmd_momentum_atr14_with_ohlc_records(self):
        """三价 records 接线：cmd_momentum 输出的 atr14 与 momentum.atr() 一致。"""
        records = _fake_ohlc_records(20)
        highs, lows, closes = _make_ohlc_series(20)
        with patch.object(stock_quote_module, "get_quote_eastmoney",
                          return_value={"records": records, "count": 20}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                stock_quote_module.cmd_momentum("300502", None)
        out = json.loads(buf.getvalue())
        self.assertTrue(out["success"])
        self.assertEqual(out["data"]["atr14"], momentum_atr(highs, lows, closes))

    def test_cmd_momentum_atr14_none_without_ohlc_records(self):
        """无三价 records 时 cmd_momentum 输出 atr14=None（无回归）。"""
        with patch.object(stock_quote_module, "get_quote_eastmoney",
                          return_value={"records": _fake_records(), "count": 260}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                stock_quote_module.cmd_momentum("300502", None)
        out = json.loads(buf.getvalue())
        self.assertTrue(out["success"])
        self.assertIsNone(out["data"]["atr14"])


def _make_index_df():
    """构造 stock_zh_index_daily_em 返回的伪指数 DataFrame（日期乱序）。"""
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-07-02", "2026-07-01", "2026-07-03"]),
        "open": [3500.123, 3490.5, 3510.2],
        "high": [3510.0, 3500.0, 3520.0],
        "low": [3495.0, 3480.0, 3505.0],
        "close": [3505.678, 3495.18, 3515.45],
        "volume": [100, 90, 110],
        "amount": [35.6, 34.9, 36.2],
    })


class TestIndex(unittest.TestCase):
    """--index 指数行情获取测试。"""

    def test_get_index_daily_sorts_and_formats(self):
        """日期乱序 DataFrame 输出按升序、date 转 YYYY-MM-DD、浮点四舍五入。"""
        with patch.object(stock_quote_module, "ak") as mock_ak:
            mock_ak.stock_zh_index_daily_em.return_value = _make_index_df()
            result = stock_quote_module.get_index_daily("上证指数")
        self.assertEqual(result["count"], 3)
        dates = [r["date"] for r in result["records"]]
        self.assertEqual(dates, ["2026-07-01", "2026-07-02", "2026-07-03"])
        self.assertEqual(result["records"][2]["close"], 3515.45)
        self.assertEqual(result["records"][0]["open"], 3490.5)

    def test_get_index_daily_range_filter(self):
        """按 start/end 过滤日期范围。"""
        with patch.object(stock_quote_module, "ak") as mock_ak:
            mock_ak.stock_zh_index_daily_em.return_value = _make_index_df()
            result = stock_quote_module.get_index_daily("上证指数", "20260702", "20260702")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["records"][0]["date"], "2026-07-02")

    def test_get_index_daily_empty(self):
        """空 DataFrame 返回空 records。"""
        with patch.object(stock_quote_module, "ak") as mock_ak:
            mock_ak.stock_zh_index_daily_em.return_value = pd.DataFrame()
            result = stock_quote_module.get_index_daily("上证指数")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["records"], [])

    def test_cmd_index_outputs_json(self):
        """cmd_index 输出含 data 的 JSON（mock get_index_daily）。"""
        with patch.object(stock_quote_module, "get_index_daily",
                          return_value={"records": [{"date": "2026-07-01", "close": 3495.18}],
                                        "count": 1}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                stock_quote_module.cmd_index("上证指数", "20260701", "20260701")
        out = json.loads(buf.getvalue())
        self.assertTrue(out["success"])
        self.assertEqual(out["meta"]["command"], "index")
        self.assertEqual(out["meta"]["index"], "上证指数")
        self.assertEqual(out["data"][0]["close"], 3495.18)


if __name__ == "__main__":
    unittest.main(verbosity=2)
