#!/usr/bin/env python3
"""A股板块（行业）SMR 截面模块测试。

测试 tools/common/sector_screen.py：行业归属查询、同行成分、单只成分 250 日涨幅
拉取、截面缓存（hit/refresh/stale）、以及组合入口 compute_peers_for_stock。

所有网络依赖通过 mock 隔离，可在无网络环境稳定运行（离线可全绿）。

运行方式:
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/common/test_sector_screen.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/common/test_sector_screen.py
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from tools.common import sector_screen

#: 东财行业缓存里常用的股票-行业映射（测试桩，兜底数据源）
_INDUSTRY_MAP = {
    "000001": {"industry": "银行"},
    "600000": {"industry": "银行"},
    "300502": {"industry": "通信设备"},
    "300503": {"industry": "通信设备"},
}

#: 申万一级行业映射（代码→行业名，测试桩，主数据源）
_SW_MAP = {
    "000001": "银行",
    "600000": "银行",
    "300502": "通信设备",
    "300503": "通信设备",
}


def _close_df(n: int = 300, base: float = 10.0, step: float = 0.1) -> pd.DataFrame:
    """构造含 close 列的伪日线 DataFrame（升序）。"""
    return pd.DataFrame({"close": [base + step * i for i in range(n)]})


class BaseSectorTestCase(unittest.TestCase):
    """隔离缓存目录的基础测试用例。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sector_test_")
        self._patches = [
            patch.object(sector_screen, "_SECTOR_DIR", Path(self.tmp) / "sector"),
            patch.object(sector_screen.a_stock_cache, "get_industry_map",
                         return_value=dict(_INDUSTRY_MAP)),
            patch.object(sector_screen, "_load_sw_map",
                         return_value=dict(_SW_MAP)),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(self._teardown)

    def _teardown(self) -> None:
        for p in reversed(self._patches):
            p.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _backdate_cache(self, industry: str, days: int) -> None:
        """将某行业缓存文件 mtime 拨回 days 天（模拟过期）。"""
        file = sector_screen._sector_file(industry)
        if file.exists():
            old = time.time() - days * 86400.0
            os.utime(file, (old, old))


class TestIndustryLookup(BaseSectorTestCase):
    """行业归属与同行成分查询。"""

    def test_get_industry_of_stock_found(self) -> None:
        """命中行业缓存返回行业名。"""
        self.assertEqual(sector_screen.get_industry_of_stock("300502"), "通信设备")
        self.assertEqual(sector_screen.get_industry_of_stock("000001"), "银行")

    def test_get_industry_of_stock_missing(self) -> None:
        """缓存在未收录的股票返回 None。"""
        self.assertIsNone(sector_screen.get_industry_of_stock("999999"))

    def test_get_sector_members_excludes_self(self) -> None:
        """同行成分排除查询个股自身。"""
        members = sector_screen.get_sector_members("通信设备", exclude_code="300502")
        self.assertEqual(members, ["300503"])

    def test_get_sector_members_keeps_others(self) -> None:
        """未排除时返回同行业全部成分。"""
        members = sector_screen.get_sector_members("银行", exclude_code=None)
        self.assertEqual(sorted(members), ["000001", "600000"])


class TestFetchPeerPct(BaseSectorTestCase):
    """单只成分 250 日涨幅拉取。"""

    def test_fetch_peer_pct_250d(self) -> None:
        """250 日涨幅 = (最新 - 251日前基准)/基准（新浪源优先）。"""
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          return_value=_close_df(300)):
            pct = sector_screen.fetch_peer_pct_250d("300503")
        ref = 10.0 + 0.1 * 49      # closes[-251] = 索引 49
        last = 10.0 + 0.1 * 299    # closes[-1]
        self.assertAlmostEqual(pct, (last - ref) / ref * 100.0, places=4)

    def test_fetch_peer_pct_insufficient_data(self) -> None:
        """close 数据不足 2 个返回 None。"""
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          return_value=pd.DataFrame({"close": [1.0]})):
            self.assertIsNone(sector_screen.fetch_peer_pct_250d("300503"))

    def test_fetch_peer_pct_error_returns_none(self) -> None:
        """两源均抛异常时不抛错，返回 None（单只跳过）。"""
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          side_effect=ConnectionError("新浪中断")), \
             patch.object(sector_screen.ak, "stock_zh_a_hist",
                          side_effect=ConnectionError("东财中断")):
            self.assertIsNone(sector_screen.fetch_peer_pct_250d("300503"))

    def test_sina_symbol_prefix(self) -> None:
        """A 股代码转新浪前缀符号。"""
        self.assertEqual(sector_screen._sina_symbol("600519"), "sh600519")
        self.assertEqual(sector_screen._sina_symbol("688981"), "sh688981")
        self.assertEqual(sector_screen._sina_symbol("000001"), "sz000001")
        self.assertEqual(sector_screen._sina_symbol("300503"), "sz300503")
        self.assertEqual(sector_screen._sina_symbol("830799"), "bj830799")
        self.assertIsNone(sector_screen._sina_symbol("999999"))

    def test_fetch_peer_falls_back_to_eastmoney(self) -> None:
        """新浪失败时回退东财源计算涨幅。"""
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          side_effect=ConnectionError("新浪中断")), \
             patch.object(sector_screen.ak, "stock_zh_a_hist",
                          return_value=_close_df(300)):
            pct = sector_screen.fetch_peer_pct_250d("300503")
        ref = 10.0 + 0.1 * 49
        last = 10.0 + 0.1 * 299
        self.assertAlmostEqual(pct, (last - ref) / ref * 100.0, places=4)


class TestSectorPeers(BaseSectorTestCase):
    """截面批量拉取与缓存（hit/refresh/stale）。"""

    def _patch_ok(self):
        """返回新浪日线可用 mock（含 close 的开盘价序列）。"""
        return patch.object(sector_screen.ak, "stock_zh_a_daily",
                            return_value=_close_df(300))

    def test_refresh_generates_and_caches(self) -> None:
        """首次拉取生成截面（全行业含自身）并写缓存，status=refresh。"""
        with self._patch_ok():
            res = sector_screen.get_sector_peers("通信设备")
        self.assertEqual(res["status"], "refresh")
        # 通信设备成分 300502 + 300503（含查询股自身，缓存纯行业级）
        self.assertEqual(sorted(res["peers"].keys()), sorted(["300502", "300503"]))
        # 已写缓存文件
        self.assertTrue(sector_screen._sector_file("通信设备").exists())

    def test_hit_returns_cached(self) -> None:
        """新鲜缓存命中时不再调用接口，status=hit。"""
        with self._patch_ok():
            sector_screen.get_sector_peers("通信设备")
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          side_effect=AssertionError("不应再次调用接口")) as mock_daily:
            res = sector_screen.get_sector_peers("通信设备")
            mock_daily.assert_not_called()
        self.assertEqual(res["status"], "hit")
        self.assertEqual(res["peers"]["300503"] > 0, True)

    def test_stale_returns_old_cache_on_failure(self) -> None:
        """缓存过期且刷新失败时降级返回旧缓存，status=stale。"""
        with self._patch_ok():
            sector_screen.get_sector_peers("通信设备")
        self._backdate_cache("通信设备", days=10)
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          side_effect=ConnectionError("新浪失败")), \
             patch.object(sector_screen.ak, "stock_zh_a_hist",
                          side_effect=ConnectionError("东财失败")):
            res = sector_screen.get_sector_peers("通信设备")
        self.assertEqual(res["status"], "stale")
        self.assertIn("peers", res)

    def test_empty_sector_without_cache_returns_empty(self) -> None:
        """无旧缓存且刷新无有效成分时返回空截面 + note，不抛错。"""
        with patch.object(sector_screen.a_stock_cache, "get_industry_map",
                          return_value={"300502": {"industry": "通信设备"}}):
            with patch.object(sector_screen.ak, "stock_zh_a_daily",
                              return_value=pd.DataFrame()):
                res = sector_screen.get_sector_peers("通信设备")
        self.assertEqual(res["peers"], {})
        self.assertIn("note", res)

    def test_empty_sector_fallbacks_to_cninfo(self) -> None:
        """申万映射无该行业时回退到东财行业缓存取成分。"""
        with patch.object(sector_screen, "_load_sw_map", return_value={}):
            members = sector_screen.get_sector_members("通信设备",
                                                       exclude_code="300502")
        self.assertEqual(members, ["300503"])


class TestComputePeersForStock(BaseSectorTestCase):
    """组合入口测试。"""

    def test_compute_peers_for_stock_ok(self) -> None:
        """由个股自动生成截面 pcts（含自身）与行业。"""
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          return_value=_close_df(300)):
            info = sector_screen.compute_peers_for_stock("300502")
        self.assertEqual(info["industry"], "通信设备")
        self.assertEqual(len(info["pcts"]), 2)  # 同行业全部成分（含自身）
        self.assertIn(info["status"], ("hit", "refresh"))

    def test_compute_peers_unknown_industry_raises(self) -> None:
        """行业缓存无该股时抛 RuntimeError。"""
        with self.assertRaises(RuntimeError):
            sector_screen.compute_peers_for_stock("999999")

    def test_market_hk_unavailable(self) -> None:
        """港股市场分发返回 unavailable（暂无公开成分数据源）。"""
        info = sector_screen.compute_peers_for_stock("00700", market="hk")
        self.assertEqual(info["status"], "unavailable")
        self.assertIsNone(info["pcts"])
        self.assertEqual(info["count"], 0)
        self.assertIn("港股", info["note"])
        self.assertIn("--peers", info["note"])

    def test_market_us_unavailable(self) -> None:
        """美股市场分发返回 unavailable（暂无公开成分数据源）。"""
        info = sector_screen.compute_peers_for_stock("AAPL", market="us")
        self.assertEqual(info["status"], "unavailable")
        self.assertIsNone(info["pcts"])
        self.assertEqual(info["count"], 0)
        self.assertIn("美股", info["note"])
        self.assertIn("--peers", info["note"])

    def test_market_default_is_a_share(self) -> None:
        """默认市场分发走 A 股申万逻辑（行业缓存命中）。"""
        with patch.object(sector_screen.ak, "stock_zh_a_daily",
                          return_value=_close_df(300)):
            self.assertEqual(sector_screen.compute_peers_for_stock("300502")["industry"],
                             "通信设备")


class TestSwMapBuild(unittest.TestCase):
    """申万一级行业映射构建与缓存。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sector_sw_")
        self.patch_dir = patch.object(sector_screen, "_SECTOR_DIR",
                                      Path(self.tmp) / "sector")
        self.patch_dir.start()
        global_saved = sector_screen._sw_map_cache
        sector_screen._sw_map_cache = None
        self._saved = global_saved
        self.addCleanup(self._teardown)

    def _teardown(self) -> None:
        sector_screen._sw_map_cache = self._saved
        self.patch_dir.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _first_info_df(self):
        """模拟 sw_index_first_info 返回的一级行业表。"""
        return pd.DataFrame({
            "行业代码": ["801080.SI", "801880.SI"],
            "行业名称": ["电子", "通信"],
        })

    def test_build_sw_map_iterates_sectors(self) -> None:
        """遍历各行业成分构建全市场映射（含 .SI 后缀剥离、代码补零）。"""
        def fake_component(symbol: str):
            if symbol == "801080":
                return pd.DataFrame({"证券代码": ["000021", "300502"]})
            return pd.DataFrame({"证券代码": ["300503"]})

        with patch.object(sector_screen.ak, "sw_index_first_info",
                          return_value=self._first_info_df()), \
             patch.object(sector_screen.ak, "index_component_sw",
                          side_effect=fake_component):
            sw_map = sector_screen._build_sw_map()
        self.assertEqual(sw_map.get("300502"), "电子")
        self.assertEqual(sw_map.get("000021"), "电子")
        self.assertEqual(sw_map.get("300503"), "通信")

    def test_build_sw_map_skips_failing_sector(self) -> None:
        """单个行业成分接口失败时跳过，不阻断整体。"""
        def fake_component(symbol: str):
            if symbol == "801080":
                raise ConnectionError("行业接口异常")
            return pd.DataFrame({"证券代码": ["300503"]})

        with patch.object(sector_screen.ak, "sw_index_first_info",
                          return_value=self._first_info_df()), \
             patch.object(sector_screen.ak, "index_component_sw",
                          side_effect=fake_component):
            sw_map = sector_screen._build_sw_map()
        self.assertEqual(sw_map, {"300503": "通信"})

    def test_load_sw_map_writes_and_reads_file(self) -> None:
        """首次加载构建并写缓存文件，二次直接读文件（不再构建）。"""
        with patch.object(sector_screen, "_build_sw_map",
                          return_value={"300502": "电子"}):
            first = sector_screen._load_sw_map()
        # 写入了缓存文件
        file = sector_screen._SECTOR_DIR / "sw_industry_map.json"
        self.assertTrue(file.exists())
        self.assertEqual(first, {"300502": "电子"})
        # 模拟新进程清空进程内缓存 → 二次读文件命中，不再调用构建
        sector_screen._sw_map_cache = None
        with patch.object(sector_screen, "_build_sw_map",
                          side_effect=AssertionError("不应再次构建")):
            second = sector_screen._load_sw_map()
        self.assertEqual(second, {"300502": "电子"})

    def test_load_sw_map_stale_on_refresh_failure(self) -> None:
        """强制刷新且构建失败时降级返回旧缓存文件内容。"""
        with patch.object(sector_screen, "_build_sw_map",
                          return_value={"300502": "电子"}):
            sector_screen._load_sw_map()
        sector_screen._sw_map_cache = None
        with patch.object(sector_screen, "_build_sw_map", return_value={}):
            stale = sector_screen._load_sw_map(force_refresh=True)
        self.assertEqual(stale, {"300502": "电子"})

    def test_load_sw_map_empty_on_akshare_missing(self) -> None:
        """akshare 不可用时返回空映射。"""
        with patch.object(sector_screen, "ak", None):
            with patch.object(sector_screen, "_build_sw_map", return_value={}):
                self.assertEqual(sector_screen._load_sw_map(), {})


def run_tests():
    """以 unittest 方式运行全部测试。"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (TestIndustryLookup, TestFetchPeerPct, TestSectorPeers,
                TestComputePeersForStock, TestSwMapBuild):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run_tests()