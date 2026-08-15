#!/usr/bin/env python3
"""港股数据本地缓存模块测试（tests/common/test_hk_stock_cache.py）。

测试 tools/common/hk_stock_cache.py 的缓存逻辑，全程 mock akshare，不联网：

1. TTL 命中：新鲜缓存不触发 API 调用（状态 hit）
2. TTL 过期：触发刷新并覆写缓存（状态 refresh）
3. force_refresh：强制刷新
4. 损坏 CSV 回退：解析失败视为缓存缺失，重新拉取并覆写
5. 原子写：无 .tmp 残留
6. 刷新失败（双源均失败）+ 有旧缓存：降级返回旧缓存（状态 stale）
7. 刷新失败（双源均失败）+ 无缓存：返回硬编码兜底列表
8. 双源回退：新浪主源失败时自动使用东财备源
9. 英文名称字段提取与缓存回读

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


def _fake_sina_spot_df() -> pd.DataFrame:
    """构造模拟的 ak.stock_hk_spot() 返回值（新浪字段，含英文名称）。

    Returns:
        含中文/英文名称与行情的 DataFrame。
    """
    return pd.DataFrame({
        "代码": ["00700", "00388", "09988"],
        "中文名称": ["腾讯控股", "香港交易所", "阿里巴巴－Ｗ"],
        "英文名称": ["TENCENT", "HKEX", "BABA-W"],
        "最新价": [439.0, 300.0, 120.0],
    })


def _fake_em_spot_df() -> pd.DataFrame:
    """构造模拟的 ak.stock_hk_spot_em() 返回值（东财字段）。

    Returns:
        含名称与行情的 DataFrame。
    """
    return pd.DataFrame({
        "代码": ["00700", "00388"],
        "名称": ["腾讯控股", "香港交易所"],
        "最新价": [439.0, 300.0],
    })


def _fake_hk_financial_df() -> pd.DataFrame:
    """构造模拟的 ak.stock_financial_hk_analysis_indicator_em 返回值。

    Returns:
        含两期财务分析指标的 DataFrame。
    """
    return pd.DataFrame([
        {"SECUCODE": "00700.HK", "SECURITY_CODE": "00700",
         "SECURITY_NAME_ABBR": "腾讯控股", "REPORT_DATE": "2023-12-31",
         "ROE_AVG": 28.15, "GROSS_PROFIT_RATIO": 52.55,
         "NET_PROFIT_RATIO": 18.91, "HOLDER_PROFIT": 115200000000.0},
        {"SECUCODE": "00700.HK", "SECURITY_CODE": "00700",
         "SECURITY_NAME_ABBR": "腾讯控股", "REPORT_DATE": "2022-12-31",
         "ROE_AVG": 30.50, "GROSS_PROFIT_RATIO": 50.10,
         "NET_PROFIT_RATIO": 20.05, "HOLDER_PROFIT": 188200000000.0},
    ])


def _fake_hk_report_df() -> pd.DataFrame:
    """构造模拟的 ak.stock_financial_hk_report_em 返回值。

    Returns:
        含两期利润表数据的 DataFrame。
    """
    return pd.DataFrame([
        {"报告日期": "2023-12-31", "营业收入": 609015000000.0,
         "净利润": 115200000000.0},
        {"报告日期": "2022-12-31", "营业收入": 554552000000.0,
         "净利润": 188200000000.0},
    ])


class BaseHkCacheTestCase(unittest.TestCase):
    """公共测试基类：将缓存文件与 akshare 全部重定向到临时目录/mock。"""

    def setUp(self) -> None:
        """准备隔离的临时缓存目录并 mock akshare。"""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = self.tmp_dir.name

        self.patchers = [
            patch.object(hk_stock_cache, "CODE_CACHE_FILE",
                         Path(self.tmp_path) / "stock_code.csv"),
            patch.object(hk_stock_cache, "FINANCIAL_DIR",
                         Path(self.tmp_path) / "financial"),
            patch.object(hk_stock_cache, "STOCK_CACHE_TTL_DAYS", 7),
            patch.object(hk_stock_cache, "FINANCIAL_TTL_DAYS", 7),
            patch.object(hk_stock_cache, "ak", MagicMock()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        # 配置模拟 akshare 接口
        hk_stock_cache.ak.stock_hk_spot.return_value = _fake_sina_spot_df()
        hk_stock_cache.ak.stock_hk_spot_em.return_value = _fake_em_spot_df()
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.return_value = _fake_hk_financial_df()
        hk_stock_cache.ak.stock_financial_hk_report_em.return_value = _fake_hk_report_df()

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
            {"code": "00700", "name": "腾讯控股", "name_en": "TENCENT", "market": "hk"},
            {"code": "00388", "name": "香港交易所", "name_en": "HKEX", "market": "hk"},
        ]
        hk_stock_cache._write_code_csv(records)


class TestHkCodeNameList(BaseHkCacheTestCase):
    """港股代码/名称列表缓存逻辑测试。"""

    def test_hit_uses_cache_without_api(self) -> None:
        """新鲜缓存命中时零 API 调用。"""
        self._seed_code_cache()
        hk_stock_cache.ak.stock_hk_spot.reset_mock()
        hk_stock_cache.ak.stock_hk_spot_em.reset_mock()

        records = hk_stock_cache.get_hk_code_name_list()

        self.assertEqual(hk_stock_cache.get_hk_code_name_status(), "hit")
        hk_stock_cache.ak.stock_hk_spot.assert_not_called()
        hk_stock_cache.ak.stock_hk_spot_em.assert_not_called()
        self.assertEqual(len(records), 2)
        # 英文名称字段应正确回读
        self.assertEqual(records[0]["name_en"], "TENCENT")

    def test_expired_cache_triggers_refresh(self) -> None:
        """过期缓存触发刷新并覆写为 API 全量数据。"""
        self._seed_code_cache()
        self._backdate_file(hk_stock_cache.CODE_CACHE_FILE)
        hk_stock_cache.ak.stock_hk_spot.reset_mock()

        records = hk_stock_cache.get_hk_code_name_list()

        self.assertEqual(hk_stock_cache.get_hk_code_name_status(), "refresh")
        hk_stock_cache.ak.stock_hk_spot.assert_called_once()
        self.assertEqual(len(records), 3)
        self.assertIn({"code": "09988", "name": "阿里巴巴－Ｗ", "name_en": "BABA-W", "market": "hk"},
                      records)
        # 本地缓存文件已覆写
        cached = hk_stock_cache._read_code_csv()
        self.assertEqual(len(cached), 3)

    def test_force_refresh_ignores_fresh_cache(self) -> None:
        """force_refresh 跳过新鲜缓存直接刷新。"""
        self._seed_code_cache()
        hk_stock_cache.ak.stock_hk_spot.reset_mock()

        records = hk_stock_cache.get_hk_code_name_list(force_refresh=True)

        self.assertEqual(hk_stock_cache.get_hk_code_name_status(), "refresh")
        hk_stock_cache.ak.stock_hk_spot.assert_called_once()
        self.assertEqual(len(records), 3)

    def test_corrupt_csv_falls_back_to_api(self) -> None:
        """损坏的缓存 CSV 视为缓存缺失，重新拉取并覆写。"""
        with open(hk_stock_cache.CODE_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write("foo,bar\n1,2\n")
        hk_stock_cache.ak.stock_hk_spot.reset_mock()

        records = hk_stock_cache.get_hk_code_name_list()

        self.assertEqual(hk_stock_cache.get_hk_code_name_status(), "refresh")
        hk_stock_cache.ak.stock_hk_spot.assert_called_once()
        self.assertEqual(len(records), 3)
        cached = hk_stock_cache._read_code_csv()
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 3)

    def test_atomic_write_leaves_no_tmp(self) -> None:
        """原子写入后无 .tmp 临时文件残留。"""
        self._seed_code_cache()
        tmp_path = hk_stock_cache.CODE_CACHE_FILE.with_suffix(
            hk_stock_cache.CODE_CACHE_FILE.suffix + ".tmp")
        self.assertFalse(tmp_path.exists())
        self.assertTrue(hk_stock_cache.CODE_CACHE_FILE.exists())

    def test_refresh_failure_uses_stale_cache(self) -> None:
        """双源刷新失败且有旧缓存时降级返回旧缓存（stale），不覆盖优质数据。"""
        self._seed_code_cache()
        self._backdate_file(hk_stock_cache.CODE_CACHE_FILE)
        # 新浪与东财均失败
        hk_stock_cache.ak.stock_hk_spot.side_effect = RuntimeError("新浪限流")
        hk_stock_cache.ak.stock_hk_spot_em.side_effect = RuntimeError("东财断连")

        records = hk_stock_cache.get_hk_code_name_list()

        self.assertEqual(hk_stock_cache.get_hk_code_name_status(), "stale")
        # 返回旧缓存的 2 条数据，而非硬编码兜底
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["code"], "00700")
        # 旧缓存文件未被覆盖
        cached = hk_stock_cache._read_code_csv()
        self.assertEqual(len(cached), 2)

    def test_no_cache_and_fetch_failure_returns_fallback(self) -> None:
        """双源失败且无缓存时返回硬编码兜底列表（含已修正的名称）。"""
        hk_stock_cache.ak.stock_hk_spot.side_effect = RuntimeError("新浪限流")
        hk_stock_cache.ak.stock_hk_spot_em.side_effect = RuntimeError("东财断连")

        records = hk_stock_cache.get_hk_code_name_list()

        self.assertEqual(hk_stock_cache.get_hk_code_name_status(), "stale")
        self.assertEqual(len(records), len(hk_stock_cache.MAJOR_HK_STOCKS))
        codes = [r["code"] for r in records]
        self.assertIn("00700", codes)
        # 核实修正后的硬编码名称（00241 阿里健康 / 00669 创科实业 / 09988 阿里巴巴-W）
        by_code = {r["code"]: r["name"] for r in records}
        self.assertEqual(by_code["00241"], "阿里健康")
        self.assertEqual(by_code["00669"], "创科实业")
        self.assertEqual(by_code["09988"], "阿里巴巴-W")

    def test_dual_source_fallback_to_em(self) -> None:
        """新浪主源失败时自动使用东财备源。"""
        self._backdate_file(hk_stock_cache.CODE_CACHE_FILE) if hk_stock_cache.CODE_CACHE_FILE.exists() else None
        hk_stock_cache.ak.stock_hk_spot.side_effect = RuntimeError("新浪限流")
        hk_stock_cache.ak.stock_hk_spot_em.reset_mock()

        records = hk_stock_cache.get_hk_code_name_list()

        self.assertEqual(hk_stock_cache.get_hk_code_name_status(), "refresh")
        hk_stock_cache.ak.stock_hk_spot_em.assert_called_once()
        # 东财源返回 2 条
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["code"], "00700")


class TestHkFinancialCache(BaseHkCacheTestCase):
    """港股财务数据缓存逻辑测试（get_financial_indicators / get_financial_report）。"""

    def test_indicators_hit_uses_cache(self) -> None:
        """新鲜财务指标缓存命中时零 API 调用，数值正确回读。"""
        # 首次调用写入缓存
        df = hk_stock_cache.get_financial_indicators("00700")
        self.assertEqual(hk_stock_cache.get_financial_status(), "refresh")
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.reset_mock()

        df2 = hk_stock_cache.get_financial_indicators("00700")

        self.assertEqual(hk_stock_cache.get_financial_status(), "hit")
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.assert_not_called()
        self.assertEqual(len(df2), 2)
        self.assertEqual(df2.iloc[0]["ROE_AVG"], 28.15)

    def test_indicators_expired_triggers_refresh(self) -> None:
        """过期财务指标缓存触发刷新并覆写。"""
        # 首次写入后回退 mtime 模拟过期
        hk_stock_cache.get_financial_indicators("00700")
        cache_file = hk_stock_cache._financial_cache_file("00700", "indicators", "年度")
        self._backdate_file(cache_file)
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.reset_mock()

        df = hk_stock_cache.get_financial_indicators("00700")

        self.assertEqual(hk_stock_cache.get_financial_status(), "refresh")
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.assert_called_once()
        self.assertEqual(len(df), 2)

    def test_indicators_force_refresh(self) -> None:
        """force_refresh 跳过新鲜缓存直接刷新。"""
        hk_stock_cache.get_financial_indicators("00700")
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.reset_mock()

        hk_stock_cache.get_financial_indicators("00700", force_refresh=True)

        self.assertEqual(hk_stock_cache.get_financial_status(), "refresh")
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.assert_called_once()

    def test_indicators_refresh_failure_uses_stale_cache(self) -> None:
        """刷新失败（限流）时降级返回旧缓存并标注 stale。"""
        hk_stock_cache.get_financial_indicators("00700")
        cache_file = hk_stock_cache._financial_cache_file("00700", "indicators", "年度")
        self._backdate_file(cache_file)
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.side_effect = RuntimeError("限流")

        df = hk_stock_cache.get_financial_indicators("00700")

        self.assertEqual(hk_stock_cache.get_financial_status(), "stale")
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["ROE_AVG"], 28.15)

    def test_indicators_no_cache_and_failure_raises(self) -> None:
        """无缓存且刷新失败时抛出 RuntimeError。"""
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.side_effect = RuntimeError("断连")
        with self.assertRaises(RuntimeError):
            hk_stock_cache.get_financial_indicators("00700")

    def test_indicators_empty_data_uses_stale_or_raises(self) -> None:
        """API 返回空 DataFrame 时：有旧缓存则降级 stale，无缓存则抛异常。"""
        hk_stock_cache.get_financial_indicators("00700")
        cache_file = hk_stock_cache._financial_cache_file("00700", "indicators", "年度")
        self._backdate_file(cache_file)
        hk_stock_cache.ak.stock_financial_hk_analysis_indicator_em.return_value = pd.DataFrame()

        df = hk_stock_cache.get_financial_indicators("00700")
        self.assertEqual(hk_stock_cache.get_financial_status(), "stale")
        self.assertEqual(len(df), 2)

    def test_report_hit_and_refresh(self) -> None:
        """报表缓存：新鲜命中零调用，过期刷新覆写。"""
        df = hk_stock_cache.get_financial_report("00700", "利润表")
        self.assertEqual(hk_stock_cache.get_financial_status(), "refresh")
        self.assertEqual(len(df), 2)
        hk_stock_cache.ak.stock_financial_hk_report_em.reset_mock()

        df2 = hk_stock_cache.get_financial_report("00700", "利润表")
        self.assertEqual(hk_stock_cache.get_financial_status(), "hit")
        hk_stock_cache.ak.stock_financial_hk_report_em.assert_not_called()
        self.assertEqual(len(df2), 2)

        # 过期触发刷新
        cache_file = hk_stock_cache._financial_cache_file("00700", "利润表", "年度")
        self._backdate_file(cache_file)
        hk_stock_cache.ak.stock_financial_hk_report_em.reset_mock()
        hk_stock_cache.get_financial_report("00700", "利润表")
        self.assertEqual(hk_stock_cache.get_financial_status(), "refresh")
        hk_stock_cache.ak.stock_financial_hk_report_em.assert_called_once()


class TestHkSpotDataframe(BaseHkCacheTestCase):
    """港股 spot 行情拉取逻辑测试。"""

    def test_spot_prefers_sina(self) -> None:
        """spot 拉取优先使用新浪主源。"""
        df = hk_stock_cache.get_hk_spot_dataframe()
        self.assertIsNotNone(df)
        hk_stock_cache.ak.stock_hk_spot.assert_called_once()
        hk_stock_cache.ak.stock_hk_spot_em.assert_not_called()

    def test_spot_falls_back_to_em(self) -> None:
        """新浪失败时 spot 回退到东财备源。"""
        hk_stock_cache.ak.stock_hk_spot.side_effect = RuntimeError("新浪限流")
        df = hk_stock_cache.get_hk_spot_dataframe()
        self.assertIsNotNone(df)
        hk_stock_cache.ak.stock_hk_spot_em.assert_called_once()
        self.assertEqual(len(df), 2)

    def test_spot_both_fail_raises(self) -> None:
        """双源均失败时抛出 RuntimeError。"""
        hk_stock_cache.ak.stock_hk_spot.side_effect = RuntimeError("新浪限流")
        hk_stock_cache.ak.stock_hk_spot_em.side_effect = RuntimeError("东财断连")
        with self.assertRaises(RuntimeError):
            hk_stock_cache.get_hk_spot_dataframe()

    def test_spot_row_lookup(self) -> None:
        """按代码在 spot 中查找单只股票。"""
        df = hk_stock_cache.get_hk_spot_dataframe()
        row = hk_stock_cache.get_hk_spot_row(df, "00700")
        self.assertIsNotNone(row)
        self.assertEqual(row["中文名称"], "腾讯控股")
        row_missing = hk_stock_cache.get_hk_spot_row(df, "99999")
        self.assertIsNone(row_missing)


if __name__ == "__main__":
    unittest.main()
