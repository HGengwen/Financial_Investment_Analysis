#!/usr/bin/env python3
"""A股数据本地缓存模块测试（tests/common/test_a_stock_cache.py）。

测试 tools/common/a_stock_cache.py 的缓存逻辑，全程 mock akshare，不联网：

1. TTL 命中：新鲜缓存不触发 API 调用（状态 hit）
2. TTL 过期：触发刷新并覆写缓存（状态 refresh）
3. force_refresh：强制刷新
4. 损坏 CSV 回退：解析失败视为缓存缺失，重新拉取并覆写
5. 原子写：无 .tmp 残留
6. 季度回退逻辑与全部失败时的 RuntimeError
7. 刷新失败：降级返回旧缓存（状态 stale）
8. 无缓存且刷新失败时抛出异常

Usage:
    {py} -m pytest tests/common/test_a_stock_cache.py -v
    {py} tests/common/test_a_stock_cache.py
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
    from tools.common import a_stock_cache
except ImportError as e:
    print(f"无法导入 a_stock_cache 模块: {e}")
    sys.exit(1)


def _fake_code_name_df() -> pd.DataFrame:
    """构造模拟的 stock_info_a_code_name 返回值。

    Returns:
        含 code/name 两列的 DataFrame。
    """
    return pd.DataFrame({
        "code": ["000001", "300502", "600519"],
        "name": ["平安银行", "新易盛", "贵州茅台"],
    })


def _fake_yjbb_df() -> pd.DataFrame:
    """构造模拟的 stock_yjbb_em 返回值（含行业字段）。

    Returns:
        含业绩报表字段的 DataFrame。
    """
    return pd.DataFrame({
        "股票代码": ["000001", "300502", "600519"],
        "股票简称": ["平安银行", "新易盛", "贵州茅台"],
        "所处行业": ["银行", "通信设备", "白酒"],
        "净资产收益率": [10.5, 15.0, 25.0],
        "销售毛利率": [None, 30.0, 90.0],
        "每股收益": [1.2, 1.5, 30.0],
    })


def _fake_ipo_df() -> pd.DataFrame:
    """构造模拟的 ak.stock_ipo_info 返回值。

    Returns:
        含 item/value 两列的 IPO 信息 DataFrame。
    """
    return pd.DataFrame([
        {"item": "上市日期", "value": "2016-03-15"},
        {"item": "上市地", "value": "深圳证券交易所"},
        {"item": "发行价", "value": "23.48"},
        {"item": "发行市盈率", "value": "22.99"},
    ])


def _fake_abstract_df() -> pd.DataFrame:
    """构造模拟的 ak.stock_financial_abstract 返回值。

    Returns:
        含"指标"列与报告期列的财务摘要 DataFrame。
    """
    return pd.DataFrame({
        "选项": [""] * 3,
        "指标": ["净资产收益率(ROE)", "毛利率", "销售净利率"],
        "20231231": [15.5, 30.2, 20.1],
        "20221231": [14.3, 28.8, 18.5],
    })


def _fake_income_statement_df() -> pd.DataFrame:
    """构造模拟的 ak.stock_financial_report_sina 返回值（利润表）。

    Returns:
        含利润表字段的 DataFrame。
    """
    return pd.DataFrame([
        {"报告日期": "2023-12-31", "利润总额": 120000000.0,
         "财务费用": 3000000.0, "利息费用": 2000000.0},
        {"报告日期": "2022-12-31", "利润总额": 100000000.0,
         "财务费用": 2500000.0, "利息费用": 1500000.0},
    ])


class BaseCacheTestCase(unittest.TestCase):
    """公共测试基类：将缓存文件与 akshare 全部重定向到临时目录/mock。"""

    def setUp(self) -> None:
        """准备隔离的临时缓存目录并 mock akshare。

        关键指标阈值（_INDUSTRY_MIN_ROWS 等）压低为 0，使小规模假数据可通过校验。
        """
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = self.tmp_dir.name

        self.patchers = [
            patch.object(a_stock_cache, "CODE_CACHE_FILE",
                         Path(self.tmp_path) / "stock_code.csv"),
            patch.object(a_stock_cache, "INDUSTRY_CACHE_FILE",
                         Path(self.tmp_path) / "stock_industry.csv"),
            patch.object(a_stock_cache, "FINANCIAL_DIR",
                         Path(self.tmp_path) / "financial"),
            patch.object(a_stock_cache, "STOCK_CACHE_TTL_DAYS", 7),
            patch.object(a_stock_cache, "FINANCIAL_TTL_DAYS", 7),
            patch.object(a_stock_cache, "IPO_TTL_DAYS", 90),
            patch.object(a_stock_cache, "_INDUSTRY_MIN_ROWS", 0),
            patch.object(a_stock_cache, "_INDUSTRY_MIN_VALID", 0),
            patch.object(a_stock_cache, "ak", MagicMock()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        # 配置模拟 akshare 接口
        a_stock_cache.ak.stock_info_a_code_name.return_value = _fake_code_name_df()
        a_stock_cache.ak.stock_yjbb_em.return_value = _fake_yjbb_df()
        a_stock_cache.ak.stock_ipo_info.return_value = _fake_ipo_df()
        a_stock_cache.ak.stock_financial_abstract.return_value = _fake_abstract_df()
        a_stock_cache.ak.stock_financial_report_sina.return_value = _fake_income_statement_df()

    def _backdate_file(self, path: str, days: int = 8) -> None:
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
            {"code": "000001", "name": "平安银行", "market": "a"},
            {"code": "600519", "name": "贵州茅台", "market": "a"},
        ]
        a_stock_cache._write_code_csv(records)

    def _seed_industry_cache(self) -> None:
        """写入一份行业缓存（2 条记录，与 API 全量 3 条不同）。"""
        industry_map = {
            "000001": {"code": "000001", "name": "平安银行", "market": "a",
                       "industry": "银行", "roe": 10.5, "gross_margin": None,
                       "eps": 1.2, "quarter": "20260331"},
            "300502": {"code": "300502", "name": "新易盛", "market": "a",
                       "industry": "通信设备", "roe": 15.0, "gross_margin": 30.0,
                       "eps": 1.5, "quarter": "20260331"},
        }
        a_stock_cache._write_industry_csv(industry_map, "20260331")


class TestCodeNameList(BaseCacheTestCase):
    """代码/名称列表缓存逻辑测试。"""

    def test_hit_uses_cache_without_api(self) -> None:
        """新鲜缓存命中时零 API 调用。"""
        self._seed_code_cache()
        a_stock_cache.ak.stock_info_a_code_name.reset_mock()

        records = a_stock_cache.get_code_name_list()

        self.assertEqual(a_stock_cache.get_code_name_status(), "hit")
        a_stock_cache.ak.stock_info_a_code_name.assert_not_called()
        # 返回旧缓存中的 2 条数据
        self.assertEqual(len(records), 2)
        self.assertIn({"code": "000001", "name": "平安银行", "market": "a"}, records)

    def test_expired_cache_triggers_refresh(self) -> None:
        """过期缓存触发刷新并覆写为 API 全量数据。"""
        self._seed_code_cache()
        self._backdate_file(a_stock_cache.CODE_CACHE_FILE)
        a_stock_cache.ak.stock_info_a_code_name.reset_mock()

        records = a_stock_cache.get_code_name_list()

        self.assertEqual(a_stock_cache.get_code_name_status(), "refresh")
        a_stock_cache.ak.stock_info_a_code_name.assert_called_once()
        # 刷新后缓存为 API 返回的 3 条全量数据
        self.assertEqual(len(records), 3)
        self.assertIn({"code": "300502", "name": "新易盛", "market": "a"}, records)
        # 本地缓存文件已覆写
        cached = a_stock_cache._read_code_csv()
        self.assertEqual(len(cached), 3)

    def test_force_refresh_ignores_fresh_cache(self) -> None:
        """force_refresh 跳过新鲜缓存直接刷新。"""
        self._seed_code_cache()
        a_stock_cache.ak.stock_info_a_code_name.reset_mock()

        records = a_stock_cache.get_code_name_list(force_refresh=True)

        self.assertEqual(a_stock_cache.get_code_name_status(), "refresh")
        a_stock_cache.ak.stock_info_a_code_name.assert_called_once()
        self.assertEqual(len(records), 3)

    def test_corrupt_csv_falls_back_to_api(self) -> None:
        """损坏的缓存 CSV 视为缓存缺失，重新拉取并覆写。"""
        # 写入可解析但缺少必需列的无效 CSV
        with open(a_stock_cache.CODE_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write("foo,bar\n1,2\n")
        a_stock_cache.ak.stock_info_a_code_name.reset_mock()

        records = a_stock_cache.get_code_name_list()

        self.assertEqual(a_stock_cache.get_code_name_status(), "refresh")
        a_stock_cache.ak.stock_info_a_code_name.assert_called_once()
        self.assertEqual(len(records), 3)
        # 缓存已覆写为合法数据
        cached = a_stock_cache._read_code_csv()
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 3)

    def test_atomic_write_leaves_no_tmp(self) -> None:
        """原子写入后无 .tmp 临时文件残留。"""
        self._seed_code_cache()
        tmp_path = a_stock_cache.CODE_CACHE_FILE.with_suffix(
            a_stock_cache.CODE_CACHE_FILE.suffix + ".tmp")
        self.assertFalse(tmp_path.exists())
        self.assertTrue(a_stock_cache.CODE_CACHE_FILE.exists())

    def test_refresh_failure_uses_stale_cache(self) -> None:
        """刷新失败（限流/断连）时降级返回旧缓存并标注 stale。"""
        self._seed_code_cache()
        self._backdate_file(a_stock_cache.CODE_CACHE_FILE)
        a_stock_cache.ak.stock_info_a_code_name.side_effect = RuntimeError("限流")

        records = a_stock_cache.get_code_name_list()

        self.assertEqual(a_stock_cache.get_code_name_status(), "stale")
        # 返回旧缓存的 2 条数据
        self.assertEqual(len(records), 2)

    def test_no_cache_and_fetch_failure_raises(self) -> None:
        """无缓存且刷新失败时抛出异常。"""
        a_stock_cache.ak.stock_info_a_code_name.side_effect = RuntimeError("断连")
        with self.assertRaises(RuntimeError):
            a_stock_cache.get_code_name_list()


class TestIndustryMap(BaseCacheTestCase):
    """行业业绩数据缓存逻辑测试。"""

    def test_industry_hit_uses_cache(self) -> None:
        """新鲜行业缓存命中时零 API 调用，数值正确回读。"""
        self._seed_industry_cache()
        a_stock_cache.ak.stock_yjbb_em.reset_mock()

        result = a_stock_cache.get_industry_map()

        self.assertEqual(a_stock_cache.get_industry_status(), "hit")
        a_stock_cache.ak.stock_yjbb_em.assert_not_called()
        self.assertEqual(result["300502"]["industry"], "通信设备")
        self.assertEqual(result["300502"]["roe"], 15.0)
        # 空值（销售毛利率=None）写读往返后仍为 None，而非 "nan"
        self.assertIsNone(result["000001"]["gross_margin"])
        # quarter 字段正确回读
        self.assertEqual(result["300502"]["quarter"], "20260331")

    def test_industry_quarter_fallback(self) -> None:
        """季度回退：前两个候选失败时使用第三个候选季度。"""
        calls = []

        def side_effect(**kwargs):
            """前两次候选季度抛错，第三次成功。"""
            date = kwargs["date"]
            calls.append(date)
            if len(calls) < 3:
                raise RuntimeError("季度数据不可用")
            return _fake_yjbb_df()

        a_stock_cache.ak.stock_yjbb_em.side_effect = side_effect

        result = a_stock_cache.get_industry_map()

        self.assertEqual(a_stock_cache.get_industry_status(), "refresh")
        self.assertEqual(len(calls), 3)
        # 命中的季度为最后一次成功调用的候选季度
        self.assertEqual(result["300502"]["quarter"], calls[-1])

    def test_industry_all_quarter_fail_raises_without_cache(self) -> None:
        """全部季度候选失败且无缓存时抛出 RuntimeError。"""
        a_stock_cache.ak.stock_yjbb_em.side_effect = RuntimeError("全部失败")
        with self.assertRaises(RuntimeError):
            a_stock_cache.get_industry_map()

    def test_industry_refresh_failure_uses_stale_cache(self) -> None:
        """行业缓存刷新失败时降级返回旧缓存并标注 stale。"""
        self._seed_industry_cache()
        self._backdate_file(a_stock_cache.INDUSTRY_CACHE_FILE)
        a_stock_cache.ak.stock_yjbb_em.side_effect = RuntimeError("限流")

        result = a_stock_cache.get_industry_map()

        self.assertEqual(a_stock_cache.get_industry_status(), "stale")
        self.assertEqual(result["300502"]["industry"], "通信设备")
        self.assertEqual(len(result), 2)

    def test_industry_refresh_overwrites_cache(self) -> None:
        """过期行业缓存刷新后覆写为 API 全量数据。"""
        self._seed_industry_cache()
        self._backdate_file(a_stock_cache.INDUSTRY_CACHE_FILE)
        a_stock_cache.ak.stock_yjbb_em.reset_mock()

        result = a_stock_cache.get_industry_map()

        self.assertEqual(a_stock_cache.get_industry_status(), "refresh")
        a_stock_cache.ak.stock_yjbb_em.assert_called_once()
        # 刷新后为 API 返回的 3 条数据
        self.assertEqual(len(result), 3)
        self.assertEqual(result["600519"]["industry"], "白酒")


class TestAFinancialCache(BaseCacheTestCase):
    """A 股财务数据缓存逻辑测试
    （get_ipo_info / get_financial_abstract / get_income_statement_sina）。
    """

    def test_ipo_info_hit_uses_cache(self) -> None:
        """新鲜 IPO 缓存命中时零 API 调用，数据正确回读。"""
        df = a_stock_cache.get_ipo_info("300502")
        self.assertEqual(a_stock_cache.get_financial_status(), "refresh")
        a_stock_cache.ak.stock_ipo_info.reset_mock()

        df2 = a_stock_cache.get_ipo_info("300502")

        self.assertEqual(a_stock_cache.get_financial_status(), "hit")
        a_stock_cache.ak.stock_ipo_info.assert_not_called()
        self.assertEqual(len(df2), 4)

    def test_ipo_info_expired_triggers_refresh(self) -> None:
        """过期 IPO 缓存触发刷新并覆写。"""
        a_stock_cache.get_ipo_info("300502")
        cache_file = a_stock_cache._financial_cache_file("300502", "ipo")
        # IPO TTL 为 90 天，需回退超过 90 天才会过期
        self._backdate_file(cache_file, days=91)
        a_stock_cache.ak.stock_ipo_info.reset_mock()

        df = a_stock_cache.get_ipo_info("300502")

        self.assertEqual(a_stock_cache.get_financial_status(), "refresh")
        a_stock_cache.ak.stock_ipo_info.assert_called_once()
        self.assertEqual(len(df), 4)

    def test_ipo_info_refresh_failure_uses_stale_cache(self) -> None:
        """IPO 刷新失败（限流）时降级返回旧缓存并标注 stale。"""
        a_stock_cache.get_ipo_info("300502")
        cache_file = a_stock_cache._financial_cache_file("300502", "ipo")
        # IPO TTL 为 90 天，需回退超过 90 天才会过期
        self._backdate_file(cache_file, days=91)
        a_stock_cache.ak.stock_ipo_info.side_effect = RuntimeError("限流")

        df = a_stock_cache.get_ipo_info("300502")

        self.assertEqual(a_stock_cache.get_financial_status(), "stale")
        self.assertEqual(len(df), 4)

    def test_ipo_info_no_cache_and_failure_raises(self) -> None:
        """IPO 无缓存且刷新失败时抛出 RuntimeError。"""
        a_stock_cache.ak.stock_ipo_info.side_effect = RuntimeError("断连")
        with self.assertRaises(RuntimeError):
            a_stock_cache.get_ipo_info("300502")

    def test_abstract_hit_uses_cache(self) -> None:
        """新鲜财务摘要缓存命中时零 API 调用，指标列正确回读。"""
        df = a_stock_cache.get_financial_abstract("300502")
        self.assertEqual(a_stock_cache.get_financial_status(), "refresh")
        a_stock_cache.ak.stock_financial_abstract.reset_mock()

        df2 = a_stock_cache.get_financial_abstract("300502")

        self.assertEqual(a_stock_cache.get_financial_status(), "hit")
        a_stock_cache.ak.stock_financial_abstract.assert_not_called()
        self.assertIn("指标", df2.columns)
        self.assertEqual(len(df2), 3)

    def test_abstract_force_refresh(self) -> None:
        """force_refresh 跳过新鲜财务摘要缓存直接刷新。"""
        a_stock_cache.get_financial_abstract("300502")
        a_stock_cache.ak.stock_financial_abstract.reset_mock()

        a_stock_cache.get_financial_abstract("300502", force_refresh=True)

        self.assertEqual(a_stock_cache.get_financial_status(), "refresh")
        a_stock_cache.ak.stock_financial_abstract.assert_called_once()

    def test_income_statement_hit_uses_cache(self) -> None:
        """新鲜利润表缓存命中时零 API 调用。"""
        df = a_stock_cache.get_income_statement_sina("300502")
        self.assertEqual(a_stock_cache.get_financial_status(), "refresh")
        a_stock_cache.ak.stock_financial_report_sina.reset_mock()

        df2 = a_stock_cache.get_income_statement_sina("300502")

        self.assertEqual(a_stock_cache.get_financial_status(), "hit")
        a_stock_cache.ak.stock_financial_report_sina.assert_not_called()
        self.assertEqual(len(df2), 2)

    def test_income_statement_expired_triggers_refresh(self) -> None:
        """过期利润表缓存触发刷新并覆写。"""
        a_stock_cache.get_income_statement_sina("300502")
        cache_file = a_stock_cache._financial_cache_file("300502", "利润表")
        self._backdate_file(cache_file)
        a_stock_cache.ak.stock_financial_report_sina.reset_mock()

        a_stock_cache.get_income_statement_sina("300502")

        self.assertEqual(a_stock_cache.get_financial_status(), "refresh")
        a_stock_cache.ak.stock_financial_report_sina.assert_called_once()


if __name__ == "__main__":
    unittest.main()
