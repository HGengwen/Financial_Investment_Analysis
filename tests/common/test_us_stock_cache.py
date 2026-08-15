#!/usr/bin/env python3
"""美股数据本地缓存模块测试（tests/common/test_us_stock_cache.py）。

测试 tools/common/us_stock_cache.py 的缓存逻辑，全程 mock requests / 本地文件，不联网：

列表部分：
1. 管道文件解析：表头顺序、时间戳行过滤、测试股过滤、交易所映射
2. yf_symbol 转换（BRK.B → BRK-B）
3. TTL 命中：新鲜缓存零网络请求（状态 hit）
4. TTL 过期 / force_refresh：触发刷新并覆写（状态 refresh）
5. 多源回退：官网失败 → 备源 API → 镜像
6. 刷新失败 + 有旧缓存：降级返回旧缓存（状态 stale）
7. 刷新失败 + 无缓存：抛 RuntimeError
8. 损坏 CSV：视为缓存缺失重新拉取
9. 原子写：无 .tmp 残留

慢变字段部分：
10. 写入/读取往返：数值字段转 float、字符串字段（公司名称）保真
11. TTL 过期视作无缓存
12. upsert：同 symbol 更新覆盖旧行

Usage:
    {py} -m pytest tests/common/test_us_stock_cache.py -v
    {py} tests/common/test_us_stock_cache.py
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

# 添加项目根目录到路径（tests/common/ 上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

try:
    from tools.common import us_stock_cache
except ImportError as e:
    print(f"无法导入 us_stock_cache 模块: {e}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 样例数据（NASDAQ Trader 管道文件）
# ---------------------------------------------------------------------------

NASDAQ_LIST_TEXT = (
    "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
    "Round Lot Size|ETF|NextShares\n"
    "AAAP|Pacer Barings CLO Market Flex ETF|G|N|N|100|Y|N\n"
    "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
    "TEST|Test Equity|G|Y|N|100|N|N\n"
    "File Creation Time: 2026-08-15 08:00\n"
)

OTHER_LIST_TEXT = (
    "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
    "Test Issue|NASDAQ Symbol\n"
    "BRK.B|Berkshire Hathaway Inc. New Common Stock|N|BRK.B|N|1|N|BRK.B\n"
    "VXX|iPath Series B S&P 500 VIX Short-Term Futures ETN|A|VXX|Y|100|N|VXX\n"
    "File Creation Time: 2026-08-15 08:00\n"
)

NASDAQ_API_TEXT = json.dumps({
    "data": {"rows": [
        {"symbol": "MSFT", "name": "Microsoft Corporation"},
        {"symbol": "GOOGL", "name": "Alphabet Inc."},
    ]},
    "status": {"rCode": 200},
})


def _fake_response(text: str) -> MagicMock:
    """构造模拟的 requests.get 响应对象。

    Args:
        text: 响应体文本。

    Returns:
        模拟响应对象。
    """
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    # JSON 响应（备源 API/镜像）需配置 json()，否则解析时报 TypeError
    if text.lstrip().startswith("{"):
        resp.json.return_value = json.loads(text)
    return resp


def _fake_statements_stock() -> MagicMock:
    """构造模拟的 yf.Ticker 对象（含六张报表）。

    Returns:
        每个报表属性均返回含一行数据的 DataFrame 的 mock 股票对象。
    """
    mock_stock = MagicMock()
    single_row_df = pd.DataFrame({"2024-12-31": [100.0]}, index=["收入"])
    for attr in ("income_stmt", "quarterly_income_stmt", "balance_sheet",
                 "quarterly_balance_sheet", "cashflow", "quarterly_cashflow"):
        setattr(mock_stock, attr, single_row_df.copy())
    return mock_stock


def _fake_dividends_stock() -> MagicMock:
    """构造模拟的 yf.Ticker 对象（含分红/拆股历史）。

    Returns:
        dividends/splits 均为含 DatetimeIndex 的 Series 的 mock 股票对象。
    """
    mock_stock = MagicMock()
    idx = pd.to_datetime(["2024-02-15", "2023-11-10", "2023-08-10"])
    mock_stock.dividends = pd.Series([0.24, 0.24, 0.24], index=idx)
    mock_stock.splits = pd.Series([4.0, 2.0], index=idx[:2])
    return mock_stock


class BaseUsCacheTestCase(unittest.TestCase):
    """公共测试基类：将缓存文件与 requests 全部重定向到临时目录/mock。"""

    def setUp(self) -> None:
        """准备隔离的临时缓存目录并 mock requests。"""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = self.tmp_dir.name

        self.patchers = [
            patch.object(us_stock_cache, "CODE_CACHE_FILE",
                         Path(self.tmp_path) / "stock_code.csv"),
            patch.object(us_stock_cache, "SLOW_FIELDS_FILE",
                         Path(self.tmp_path) / "symbol_info.csv"),
            patch.object(us_stock_cache, "FINANCIAL_DIR",
                         Path(self.tmp_path) / "financial"),
            patch.object(us_stock_cache, "LIST_TTL_DAYS", 7),
            patch.object(us_stock_cache, "SLOW_FIELDS_TTL_DAYS", 1),
            patch.object(us_stock_cache, "FINANCIAL_TTL_DAYS", 7),
            patch.object(us_stock_cache, "DIVIDENDS_TTL_DAYS", 30),
            patch.object(us_stock_cache, "requests", MagicMock()),
            patch.object(us_stock_cache, "yf", MagicMock()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        # 默认：官网下载成功（两次 get：nasdaq + other）
        us_stock_cache.requests.get.side_effect = [
            _fake_response(NASDAQ_LIST_TEXT),
            _fake_response(OTHER_LIST_TEXT),
        ]

    def _backdate_file(self, path: Path, days: int = 8) -> None:
        """将文件 mtime 回退指定天数，模拟缓存过期。

        Args:
            path: 目标文件路径。
            days: 回退天数（默认 8 天，超过默认 TTL 7 天）。
        """
        old_ts = time.time() - days * 86400
        os.utime(path, (old_ts, old_ts))

    def _seed_code_cache(self) -> None:
        """写入一份「旧版」代码列表缓存（2 条记录，与 API 全量 3 条不同）。"""
        records = [
            {"symbol": "AAPL", "name": "Apple Inc.", "yf_symbol": "AAPL",
             "exchange": "NASDAQ", "etf": "N", "market": "us"},
            {"symbol": "MSFT", "name": "Microsoft Corp.", "yf_symbol": "MSFT",
             "exchange": "NASDAQ", "etf": "N", "market": "us"},
        ]
        us_stock_cache._write_code_csv(records)


class TestPipeParsing(unittest.TestCase):
    """NASDAQ Trader 管道文件解析逻辑测试。"""

    def test_parse_nasdaq_list(self) -> None:
        """解析 nasdaqlisted：过滤测试股与时间戳行，交易所固定 NASDAQ。"""
        records = us_stock_cache._parse_pipe_file(
            NASDAQ_LIST_TEXT,
            {"Symbol", "Security Name", "Market Category", "Test Issue",
             "Financial Status", "Round Lot Size", "ETF", "NextShares"},
            exchange_fixed="NASDAQ",
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["symbol"], "AAAP")
        self.assertEqual(records[0]["exchange"], "NASDAQ")
        self.assertEqual(records[0]["etf"], "Y")
        # TEST 测试股应被过滤
        symbols = [r["symbol"] for r in records]
        self.assertNotIn("TEST", symbols)

    def test_parse_other_list_exchange_map(self) -> None:
        """解析 otherlisted：按 Exchange 列映射交易所。"""
        records = us_stock_cache._parse_pipe_file(
            OTHER_LIST_TEXT,
            {"ACT Symbol", "Security Name", "Exchange", "CQS Symbol", "ETF",
             "Round Lot Size", "Test Issue", "NASDAQ Symbol"},
            exchange_fixed=None,
        )
        self.assertEqual(len(records), 2)
        by_symbol = {r["symbol"]: r for r in records}
        self.assertEqual(by_symbol["BRK.B"]["exchange"], "NYSE")
        self.assertEqual(by_symbol["VXX"]["exchange"], "NYSE American")

    def test_parse_bad_header_raises(self) -> None:
        """表头异常时抛出 RuntimeError。"""
        with self.assertRaises(RuntimeError):
            us_stock_cache._parse_pipe_file(
                "foo|bar\n1|2\n",
                {"Symbol", "Security Name"}, exchange_fixed="NASDAQ")

    def test_yf_symbol_conversion(self) -> None:
        """yf_symbol：点号转换为连字符。"""
        records = [{"symbol": "BRK.B", "name": "Berkshire", "exchange": "NYSE", "etf": "N"}]
        rows = us_stock_cache._records_to_cache_rows(records)
        self.assertEqual(rows[0]["yf_symbol"], "BRK-B")
        records2 = [{"symbol": "AAPL", "name": "Apple", "exchange": "NASDAQ", "etf": "N"}]
        self.assertEqual(us_stock_cache._records_to_cache_rows(records2)[0]["yf_symbol"], "AAPL")


class TestUsCodeNameList(BaseUsCacheTestCase):
    """美股代码/名称列表缓存逻辑测试。"""

    def test_refresh_from_nasdaq_trader(self) -> None:
        """官网下载刷新列表（两次 get：nasdaq + other），写缓存。"""
        records = us_stock_cache.get_us_code_name_list(force_refresh=True)

        self.assertEqual(us_stock_cache.get_us_code_name_status(), "refresh")
        self.assertEqual(us_stock_cache.requests.get.call_count, 2)
        self.assertEqual(len(records), 4)  # 3 (nasdaq 有效) + 1 (other 有效)
        # BRK.B 正确解析且 yf_symbol 转换
        brk = [r for r in records if r["symbol"] == "BRK.B"][0]
        self.assertEqual(brk["exchange"], "NYSE")
        self.assertEqual(brk["yf_symbol"], "BRK-B")
        cached = us_stock_cache._read_code_csv()
        self.assertEqual(len(cached), 4)

    def test_hit_uses_cache_without_network(self) -> None:
        """新鲜缓存命中时零网络请求。"""
        self._seed_code_cache()
        us_stock_cache.requests.get.reset_mock()

        records = us_stock_cache.get_us_code_name_list()

        self.assertEqual(us_stock_cache.get_us_code_name_status(), "hit")
        us_stock_cache.requests.get.assert_not_called()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["symbol"], "AAPL")

    def test_expired_cache_triggers_refresh(self) -> None:
        """过期缓存触发官网刷新并覆写。"""
        self._seed_code_cache()
        self._backdate_file(us_stock_cache.CODE_CACHE_FILE)
        us_stock_cache.requests.get.reset_mock()

        records = us_stock_cache.get_us_code_name_list()

        self.assertEqual(us_stock_cache.get_us_code_name_status(), "refresh")
        self.assertEqual(len(records), 4)

    def test_force_refresh_ignores_fresh_cache(self) -> None:
        """force_refresh 跳过新鲜缓存直接刷新。"""
        self._seed_code_cache()
        us_stock_cache.requests.get.reset_mock()

        records = us_stock_cache.get_us_code_name_list(force_refresh=True)

        self.assertEqual(us_stock_cache.get_us_code_name_status(), "refresh")
        us_stock_cache.requests.get.assert_called()
        self.assertEqual(len(records), 4)

    def test_fallback_to_api_when_trader_fails(self) -> None:
        """官网下载失败时回退到备源 API。"""
        # 官网第一次 get 抛异常（整个 trader 源失败），随后备源 API 成功
        us_stock_cache.requests.get.side_effect = [
            RuntimeError("官网不可达"),
            _fake_response(NASDAQ_API_TEXT),
        ]

        records = us_stock_cache.get_us_code_name_list(force_refresh=True)

        self.assertEqual(us_stock_cache.get_us_code_name_status(), "refresh")
        symbols = [r["symbol"] for r in records]
        self.assertIn("MSFT", symbols)
        self.assertIn("GOOGL", symbols)
        # 官网 1 次 + 备源 API 1 次
        self.assertEqual(us_stock_cache.requests.get.call_count, 2)

    def test_refresh_failure_uses_stale_cache(self) -> None:
        """全部数据源失败且有旧缓存时降级返回旧缓存（stale）。"""
        self._seed_code_cache()
        self._backdate_file(us_stock_cache.CODE_CACHE_FILE)
        us_stock_cache.requests.get.side_effect = RuntimeError("全部断连")

        records = us_stock_cache.get_us_code_name_list()

        self.assertEqual(us_stock_cache.get_us_code_name_status(), "stale")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["symbol"], "AAPL")

    def test_no_cache_and_all_fail_raises(self) -> None:
        """无缓存且全部数据源失败时抛出 RuntimeError。"""
        us_stock_cache.requests.get.side_effect = RuntimeError("全部断连")
        with self.assertRaises(RuntimeError):
            us_stock_cache.get_us_code_name_list(force_refresh=True)

    def test_corrupt_csv_falls_back_to_network(self) -> None:
        """损坏的缓存 CSV 视为缓存缺失，重新拉取并覆写。"""
        with open(us_stock_cache.CODE_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write("foo,bar\n1,2\n")

        records = us_stock_cache.get_us_code_name_list()

        self.assertEqual(us_stock_cache.get_us_code_name_status(), "refresh")
        self.assertEqual(len(records), 4)
        cached = us_stock_cache._read_code_csv()
        self.assertEqual(len(cached), 4)

    def test_atomic_write_leaves_no_tmp(self) -> None:
        """原子写入后无 .tmp 临时文件残留。"""
        self._seed_code_cache()
        tmp_path = us_stock_cache.CODE_CACHE_FILE.with_suffix(
            us_stock_cache.CODE_CACHE_FILE.suffix + ".tmp")
        self.assertFalse(tmp_path.exists())
        self.assertTrue(us_stock_cache.CODE_CACHE_FILE.exists())

    def test_search_us_stocks(self) -> None:
        """按名称/代码搜索美股。"""
        self._seed_code_cache()
        matched = us_stock_cache.search_us_stocks("apple")
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["symbol"], "AAPL")


class TestSlowFields(BaseUsCacheTestCase):
    """慢变字段缓存逻辑测试。"""

    def test_update_and_read_roundtrip(self) -> None:
        """写入/读取往返：数值转 float、字符串保真。"""
        us_stock_cache.update_slow_fields("AAPL", {
            "公司名称": "Apple Inc.",
            "市值": 3000000000000,
            "市盈率TTM": 30.5,
            "ROE": 1.5,
        })

        result = us_stock_cache.get_slow_fields("AAPL")

        self.assertIsNotNone(result)
        self.assertEqual(result["公司名称"], "Apple Inc.")
        self.assertEqual(result["市值"], 3000000000000.0)
        self.assertEqual(result["市盈率TTM"], 30.5)
        self.assertEqual(result["ROE"], 1.5)
        # 未写入字段为 None
        self.assertIsNone(result["股息率"])

    def test_missing_symbol_returns_none(self) -> None:
        """查询不存在的代码返回 None。"""
        us_stock_cache.update_slow_fields("AAPL", {"公司名称": "Apple Inc."})
        self.assertIsNone(us_stock_cache.get_slow_fields("MSFT"))

    def test_upsert_overwrites_same_symbol(self) -> None:
        """同 symbol 更新覆盖旧行。"""
        us_stock_cache.update_slow_fields("AAPL", {"市值": 100})
        us_stock_cache.update_slow_fields("AAPL", {"市值": 200})
        # 文件应只有一行 AAPL
        import pandas as pd
        df = pd.read_csv(us_stock_cache.SLOW_FIELDS_FILE)
        self.assertEqual(len(df), 1)
        result = us_stock_cache.get_slow_fields("AAPL")
        self.assertEqual(result["市值"], 200.0)

    def test_expired_slow_fields_returns_none(self) -> None:
        """TTL 过期的慢变字段视作无缓存。"""
        us_stock_cache.update_slow_fields("AAPL", {"市值": 100})
        self._backdate_file(us_stock_cache.SLOW_FIELDS_FILE, days=2)
        self.assertIsNone(us_stock_cache.get_slow_fields("AAPL"))


class TestUsFinancialCache(BaseUsCacheTestCase):
    """美股财务数据缓存逻辑测试
    （get_financial_statements / get_dividends_splits）。
    """

    def setUp(self) -> None:
        """基类 setUp 后配置 yfinance mock。"""
        super().setUp()
        us_stock_cache.yf.Ticker.return_value = _fake_statements_stock()

    def test_statements_hit_uses_cache(self) -> None:
        """新鲜报表缓存命中时零 yfinance 调用，六张报表键齐全。"""
        data = us_stock_cache.get_financial_statements("AAPL")
        self.assertEqual(us_stock_cache.get_financial_status(), "refresh")
        self.assertIn("年度利润表", data)
        self.assertIn("季度现金流量表", data)
        us_stock_cache.yf.Ticker.reset_mock()

        data2 = us_stock_cache.get_financial_statements("AAPL")

        self.assertEqual(us_stock_cache.get_financial_status(), "hit")
        us_stock_cache.yf.Ticker.assert_not_called()
        self.assertEqual(data2["年度利润表"]["count"], 1)

    def test_statements_expired_triggers_refresh(self) -> None:
        """过期报表缓存触发刷新并覆写。"""
        us_stock_cache.get_financial_statements("AAPL")
        cache_file = us_stock_cache._financial_cache_file("AAPL", "statements")
        self._backdate_file(cache_file)
        us_stock_cache.yf.Ticker.reset_mock()

        data = us_stock_cache.get_financial_statements("AAPL")

        self.assertEqual(us_stock_cache.get_financial_status(), "refresh")
        us_stock_cache.yf.Ticker.assert_called_once()
        self.assertEqual(data["年度利润表"]["count"], 1)

    def test_statements_force_refresh(self) -> None:
        """force_refresh 跳过新鲜报表缓存直接刷新。"""
        us_stock_cache.get_financial_statements("AAPL")
        us_stock_cache.yf.Ticker.reset_mock()

        us_stock_cache.get_financial_statements("AAPL", force_refresh=True)

        self.assertEqual(us_stock_cache.get_financial_status(), "refresh")
        us_stock_cache.yf.Ticker.assert_called_once()

    def test_statements_refresh_failure_uses_stale_cache(self) -> None:
        """报表刷新失败（yfinance 限流）时降级返回旧缓存并标注 stale。"""
        us_stock_cache.get_financial_statements("AAPL")
        cache_file = us_stock_cache._financial_cache_file("AAPL", "statements")
        self._backdate_file(cache_file)
        us_stock_cache.yf.Ticker.side_effect = RuntimeError("限流 429")

        data = us_stock_cache.get_financial_statements("AAPL")

        self.assertEqual(us_stock_cache.get_financial_status(), "stale")
        self.assertEqual(data["年度利润表"]["count"], 1)

    def test_statements_no_cache_and_failure_returns_none(self) -> None:
        """报表无缓存且刷新失败时返回 None（调用方降级处理）。"""
        us_stock_cache.yf.Ticker.side_effect = RuntimeError("断连")
        data = us_stock_cache.get_financial_statements("AAPL")
        self.assertIsNone(data)
        self.assertEqual(us_stock_cache.get_financial_status(), "stale")

    def test_dividends_hit_and_refresh(self) -> None:
        """分红拆股缓存：新鲜命中零调用，过期触发刷新。"""
        us_stock_cache.yf.Ticker.return_value = _fake_dividends_stock()
        data = us_stock_cache.get_dividends_splits("AAPL")
        self.assertEqual(us_stock_cache.get_financial_status(), "refresh")
        self.assertEqual(data["分红历史"]["count"], 3)
        self.assertEqual(data["分红历史"]["total_years"], 2)
        self.assertEqual(data["拆股历史"]["count"], 2)
        us_stock_cache.yf.Ticker.reset_mock()

        data2 = us_stock_cache.get_dividends_splits("AAPL")
        self.assertEqual(us_stock_cache.get_financial_status(), "hit")
        us_stock_cache.yf.Ticker.assert_not_called()
        self.assertEqual(data2["分红历史"]["count"], 3)

        # 过期触发刷新
        cache_file = us_stock_cache._financial_cache_file("AAPL", "dividends")
        self._backdate_file(cache_file, days=31)
        us_stock_cache.yf.Ticker.reset_mock()
        us_stock_cache.get_dividends_splits("AAPL")
        self.assertEqual(us_stock_cache.get_financial_status(), "refresh")
        us_stock_cache.yf.Ticker.assert_called_once()

    def test_dividends_no_cache_and_failure_returns_none(self) -> None:
        """分红拆股无缓存且刷新失败时返回 None。"""
        us_stock_cache.yf.Ticker.side_effect = RuntimeError("断连")
        data = us_stock_cache.get_dividends_splits("AAPL")
        self.assertIsNone(data)
        self.assertEqual(us_stock_cache.get_financial_status(), "stale")


if __name__ == "__main__":
    unittest.main()
