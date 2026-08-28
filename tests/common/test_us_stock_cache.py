#!/usr/bin/env python3
"""美股财务报表本地缓存模块测试（tests/common/test_us_stock_cache.py）。

测试 tools/common/us_stock_cache.py 的缓存逻辑，全程 mock yfinance，不联网：

1. 报表透视：yfinance 报表 DataFrame 转为 {报告期: {科目: 值}}
2. TTL 命中：新鲜缓存不触发 yfinance 调用（状态 hit）
3. TTL 过期：触发刷新并原子覆写缓存（状态 refresh）
4. stale 降级：刷新失败但存在旧缓存时返回旧数据（状态 stale）
5. 空报表检测：yfinance 返回空 DataFrame 时视为失败，不写入无效缓存
6. 无缓存且刷新失败：抛出异常

Usage:
    {py} -m pytest tests/common/test_us_stock_cache.py -v
    {py} tests/common/test_us_stock_cache.py
"""

import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
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


def _fake_income_stmt() -> pd.DataFrame:
    """构造模拟的 yfinance 利润表 DataFrame（index=科目英文，columns=报告期）。"""
    return pd.DataFrame(
        {
            datetime(2025, 9, 28): {
                "Gross Profit": 118007560000.0,
                "Research Development": 33622000000.0,
                "Total Revenue": 411293000000.0,
            },
            datetime(2024, 9, 28): {
                "Gross Profit": 104577417000.0,
                "Research Development": 31377000000.0,
                "Total Revenue": 391035000000.0,
            },
        }
    )


class BaseUsCacheTestCase(unittest.TestCase):
    """公共测试基类：将缓存目录与 yfinance 全部重定向到临时目录/mock。"""

    def setUp(self) -> None:
        """准备隔离的临时缓存目录并 mock yfinance。"""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = self.tmp_dir.name

        self.patchers = [
            patch.object(us_stock_cache, "FINANCIAL_DIR", Path(self.tmp_path)),
            patch.object(us_stock_cache, "US_FINANCIAL_TTL_DAYS", 7),
            patch.object(us_stock_cache, "yf", MagicMock()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        # 配置模拟 yfinance Ticker
        self.ticker = MagicMock()
        us_stock_cache.yf.Ticker.return_value = self.ticker

    def _backdate_file(self, name: str, days: int = 8) -> None:
        """将缓存文件 mtime 回退指定天数，模拟过期。

        Args:
            name: 缓存文件名（如 AAPL_income.json）。
            days: 回退天数（默认 8 天，超过默认 TTL 7 天）。
        """
        fpath = Path(self.tmp_path) / name
        old_ts = time.time() - days * 86400
        os.utime(fpath, (old_ts, old_ts))

    def _seed_statement_cache(self, name: str = "AAPL_income.json") -> None:
        """写入一份含 2 个报告期毛利的旧版缓存。"""
        data = {
            "2025-09-28": {"Gross Profit": 118007560000.0},
            "2024-09-28": {"Gross Profit": 104577417000.0},
        }
        us_stock_cache._atomic_write_json(data, Path(self.tmp_path) / name)


class TestStmtToMap(BaseUsCacheTestCase):
    """yfinance 报表透视测试。"""

    def test_stmt_to_map_converts_periods(self) -> None:
        """报表 DataFrame 转为 {报告期: {科目: 值}} 并规整日期。"""
        result = us_stock_cache._stmt_to_map(_fake_income_stmt())
        self.assertEqual(set(result.keys()), {"2025-09-28", "2024-09-28"})
        self.assertEqual(result["2025-09-28"]["Gross Profit"], 118007560000.0)
        self.assertEqual(result["2025-09-28"]["Research Development"], 33622000000.0)

    def test_stmt_to_map_empty_df(self) -> None:
        """空 DataFrame 返回空 dict。"""
        self.assertEqual(us_stock_cache._stmt_to_map(pd.DataFrame()), {})


class TestGetStatement(BaseUsCacheTestCase):
    """三大报表缓存逻辑测试。"""

    def test_hit_uses_cache_without_yf(self) -> None:
        """新鲜缓存命中时零 yfinance 调用。"""
        self._seed_statement_cache()
        us_stock_cache.yf.Ticker.reset_mock()

        stmt = us_stock_cache.get_statement("AAPL", "income")

        self.assertEqual(us_stock_cache.get_financial_status("income"), "hit")
        us_stock_cache.yf.Ticker.assert_not_called()
        self.assertEqual(stmt["2025-09-28"]["Gross Profit"], 118007560000.0)

    def test_refresh_fetches_and_overwrites(self) -> None:
        """缺失缓存触发 yfinance 刷新并原子覆写。"""
        self.ticker.income_stmt = _fake_income_stmt()

        stmt = us_stock_cache.get_statement("AAPL", "income")

        self.assertEqual(us_stock_cache.get_financial_status("income"), "refresh")
        us_stock_cache.yf.Ticker.assert_called_once_with("AAPL")
        self.assertEqual(stmt["2024-09-28"]["Total Revenue"], 391035000000.0)
        self.assertTrue((Path(self.tmp_path) / "AAPL_income.json").exists())

    def test_stale_returns_old_cache_when_refresh_fails(self) -> None:
        """刷新失败但存在旧缓存时降级返回旧数据。"""
        self._seed_statement_cache()
        self._backdate_file("AAPL_income.json")
        self.ticker.income_stmt = None  # None 触发 _stmt_to_map 空结果 → 视为失败

        stmt = us_stock_cache.get_statement("AAPL", "income")

        self.assertEqual(us_stock_cache.get_financial_status("income"), "stale")
        self.assertEqual(stmt["2024-09-28"]["Gross Profit"], 104577417000.0)

    def test_empty_statement_raises_and_not_cached(self) -> None:
        """yfinance 返回空报表时视为失败，不写入无效缓存。"""
        # 无缓存文件存在时，空报表应抛异常且不落盘
        self.ticker.income_stmt = pd.DataFrame()
        with self.assertRaises(RuntimeError):
            us_stock_cache.get_statement("AAPL", "income")
        self.assertFalse((Path(self.tmp_path) / "AAPL_income.json").exists())

    def test_raise_without_cache_when_fetch_fails(self) -> None:
        """无缓存且刷新失败时抛出异常。"""
        self.ticker.income_stmt = pd.DataFrame()
        with self.assertRaises(RuntimeError):
            us_stock_cache.get_statement("AAPL", "balance")


if __name__ == "__main__":
    unittest.main(verbosity=2)