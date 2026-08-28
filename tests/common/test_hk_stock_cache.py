#!/usr/bin/env python3
"""港股财务报表与员工数据本地缓存模块测试（tests/common/test_hk_stock_cache.py）。

测试 tools/common/hk_stock_cache.py 的缓存逻辑，全程 mock akshare，不联网：

1. 长表透视：东财港股长表（每行一个科目×报告期）正确透视为 {报告期: {科目: 金额}}
2. TTL 命中：新鲜缓存不触发 API 调用（状态 hit）
3. TTL 过期：触发刷新并原子覆写缓存（状态 refresh）
4. stale 降级：刷新失败但存在旧缓存时返回旧数据（状态 stale）
5. 无缓存且刷新失败：抛出 RuntimeError
6. 员工数：返回员工字段时取到值；接口异常时标注缺口不抛异常
7. 员工数 akshare 未安装：返回缺口说明

Usage:
    {py} -m pytest tests/common/test_hk_stock_cache.py -v
    {py} tests/common/test_hk_stock_cache.py
"""

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
    from tools.common import hk_stock_cache
except ImportError as e:
    print(f"无法导入 hk_stock_cache 模块: {e}")
    sys.exit(1)


def _fake_long_tbl() -> pd.DataFrame:
    """构造东财港股报表长表（每行一个科目×报告期）。

    Returns:
        含 REPORT_DATE/STD_ITEM_NAME/AMOUNT 三列的长表 DataFrame。
    """
    return pd.DataFrame({
        "REPORT_DATE": ["2025-12-31"] * 2 + ["2024-12-31"] * 2,
        "STD_ITEM_NAME": ["存货", "应付账款", "存货", "应付账款"],
        "AMOUNT": [530000000.0, 121127000000.0, 440000000.0, 118712000000.0],
    })


def _fake_employee_df() -> pd.DataFrame:
    """构造雪球港股员工数返回 DataFrame（item/value 列）。"""
    return pd.DataFrame({"item": ["上市地点", "员工总数"], "value": ["香港", 105416.0]})


class BaseHkCacheTestCase(unittest.TestCase):
    """公共测试基类：将缓存目录与 akshare 全部重定向到临时目录/mock。"""

    def setUp(self) -> None:
        """准备隔离的临时缓存目录并 mock akshare。"""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = self.tmp_dir.name

        self.patchers = [
            patch.object(hk_stock_cache, "FINANCIAL_DIR", Path(self.tmp_path)),
            patch.object(hk_stock_cache, "HK_FINANCIAL_TTL_DAYS", 7),
            patch.object(hk_stock_cache, "ak", MagicMock()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _backdate_file(self, name: str, days: int = 8) -> None:
        """将缓存文件 mtime 回退指定天数，模拟过期。

        Args:
            name: 缓存文件名（如 00700_资产负债表.json）。
            days: 回退天数（默认 8 天，超过默认 TTL 7 天）。
        """
        fpath = Path(self.tmp_path) / name
        old_ts = time.time() - days * 86400
        os.utime(fpath, (old_ts, old_ts))

    def _seed_report_cache(self, name: str = "00700_资产负债表.json") -> None:
        """写入一份旧版报表缓存（内含 2 个报告期的存货科目）。"""
        data = {
            "20251231": {"存货": 530000000.0, "应付账款": 121127000000.0},
            "20241231": {"存货": 440000000.0, "应付账款": 118712000000.0},
        }
        hk_stock_cache._atomic_write_json(data, Path(self.tmp_path) / name)


class TestLongToMap(BaseHkCacheTestCase):
    """东财港股报表长表透视测试。"""

    def test_long_to_map_pivots_by_period(self) -> None:
        """长表按 报告期×科目 去重累积。"""
        result = hk_stock_cache._long_to_map(_fake_long_tbl())
        self.assertEqual(set(result.keys()), {"20251231", "20241231"})
        self.assertEqual(result["20251231"]["存货"], 530000000.0)
        self.assertEqual(result["20251231"]["应付账款"], 121127000000.0)
        self.assertEqual(result["20241231"]["存货"], 440000000.0)

    def test_long_to_map_empty_df(self) -> None:
        """空 DataFrame 返回空 dict 不抛异常。"""
        self.assertEqual(hk_stock_cache._long_to_map(pd.DataFrame()), {})


class TestFinancialReport(BaseHkCacheTestCase):
    """三大报表缓存逻辑测试。"""

    def test_hit_uses_cache_without_api(self) -> None:
        """新鲜缓存命中时零 API 调用。"""
        self._seed_report_cache()
        hk_stock_cache.ak.reset_mock()

        stmt = hk_stock_cache.get_financial_report("00700", "资产负债表")

        self.assertEqual(hk_stock_cache.get_financial_status("资产负债表"), "hit")
        hk_stock_cache.ak.stock_financial_hk_report_em.assert_not_called()
        self.assertEqual(stmt["20251231"]["存货"], 530000000.0)

    def test_refresh_fetches_and_overwrites(self) -> None:
        """过期/缺失缓存触发刷新并覆写为接口数据。"""
        hk_stock_cache.ak.stock_financial_hk_report_em.return_value = _fake_long_tbl()

        stmt = hk_stock_cache.get_financial_report("00700", "资产负债表")

        self.assertEqual(hk_stock_cache.get_financial_status("资产负债表"), "refresh")
        hk_stock_cache.ak.stock_financial_hk_report_em.assert_called_once()
        self.assertEqual(stmt["20251231"]["应付账款"], 121127000000.0)
        # 缓存文件已原子覆写
        self.assertTrue((Path(self.tmp_path) / "00700_资产负债表.json").exists())

    def test_expired_cache_triggers_refresh(self) -> None:
        """过期缓存触发刷新。"""
        self._seed_report_cache()
        self._backdate_file("00700_资产负债表.json")
        hk_stock_cache.ak.stock_financial_hk_report_em.return_value = _fake_long_tbl()

        hk_stock_cache.get_financial_report("00700", "资产负债表")

        self.assertEqual(hk_stock_cache.get_financial_status("资产负债表"), "refresh")
        hk_stock_cache.ak.stock_financial_hk_report_em.assert_called_once()

    def test_stale_returns_old_cache_when_refresh_fails(self) -> None:
        """刷新失败但存在旧缓存时降级返回旧数据。"""
        self._seed_report_cache()
        self._backdate_file("00700_资产负债表.json")
        hk_stock_cache.ak.stock_financial_hk_report_em.side_effect = ConnectionError("东财接口超时")

        stmt = hk_stock_cache.get_financial_report("00700", "资产负债表")

        self.assertEqual(hk_stock_cache.get_financial_status("资产负债表"), "stale")
        self.assertEqual(stmt["20241231"]["存货"], 440000000.0)

    def test_raise_without_cache_when_fetch_fails(self) -> None:
        """无缓存且刷新失败时抛出异常。"""
        hk_stock_cache.ak.stock_financial_hk_report_em.side_effect = ConnectionError("东财接口超时")
        with self.assertRaises(ConnectionError):
            hk_stock_cache.get_financial_report("00700", "资产负债表")


class TestEmployeeCount(BaseHkCacheTestCase):
    """港股员工数获取测试。"""

    def test_employee_value_extracted(self) -> None:
        """返回含员工总数字段时取到值。"""
        hk_stock_cache.ak.stock_individual_basic_info_hk_xq.return_value = _fake_employee_df()
        result = hk_stock_cache.get_employee_count("00700")
        self.assertEqual(result["value"], 105416)
        self.assertEqual(result["note"], "雪球")

    def test_employee_missing_field(self) -> None:
        """接口返回无员工字段时标注缺口。"""
        df = pd.DataFrame({"item": ["上市地点"], "value": ["香港"]})
        hk_stock_cache.ak.stock_individual_basic_info_hk_xq.return_value = df
        result = hk_stock_cache.get_employee_count("00700")
        self.assertIsNone(result["value"])
        self.assertIn("未返回员工字段", result["note"])

    def test_employee_exception_marks_gap(self) -> None:
        """接口抛异常时标注缺口不抛异常。"""
        hk_stock_cache.ak.stock_individual_basic_info_hk_xq.side_effect = KeyError("token")
        result = hk_stock_cache.get_employee_count("00700")
        self.assertIsNone(result["value"])
        self.assertIn("KeyError", result["note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)