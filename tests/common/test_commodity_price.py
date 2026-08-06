"""大宗商品价格数据获取工具单元测试。

测试覆盖：
    - 商品注册表配置查询
    - Akshare 数据获取器（mock）
    - yfinance 数据获取器（mock）
    - 主调度器策略（Akshare 优先、yfinance 回退）
    - 批量获取限流保护
    - CLI 入口

运行方式：
    python -m pytest tests/test_commodity_price.py -v
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common.commodity_price import (
    CommodityCategory,
    CommodityFetchError,
    CommoditySpec,
    FetchResult,
    _build_index,
    _COMMODITY_INDEX,
    _COMMODITY_REGISTRY,
    _fetch_akshare,
    _fetch_yfinance,
    _filter_by_date_range,
    _normalize_foreign_hist,
    _normalize_main_sina,
    _normalize_yfinance,
    cmd_fetch,
    cmd_list,
    fetch_commodity,
    fetch_many,
    get_commodity,
    list_commodities,
    supports_akshare,
    supports_yfinance,
)


# ===========================================================================
# 商品注册表测试
# ===========================================================================

class TestCommodityRegistry:
    """商品注册表配置测试。"""

    def test_registry_not_empty(self):
        """注册表不为空。"""
        assert len(_COMMODITY_REGISTRY) > 0

    def test_registry_has_18_commodities(self):
        """注册表包含 18 个品种。"""
        assert len(_COMMODITY_REGISTRY) == 18

    def test_no_duplicate_codes(self):
        """商品 code 无重复。"""
        codes = [spec.code for spec in _COMMODITY_REGISTRY]
        assert len(codes) == len(set(codes))

    def test_build_index_success(self):
        """构建索引成功。"""
        index = _build_index(_COMMODITY_REGISTRY)
        assert len(index) == 18
        assert "cu" in index
        assert "GC" in index

    def test_build_index_duplicate_raises(self):
        """重复 code 抛出 ValueError。"""
        specs = [
            CommoditySpec(code="cu", name="沪铜", category=CommodityCategory.NON_FERROUS_METAL,
                          currency="CNY", akshare_api=None, akshare_symbol="cu0"),
            CommoditySpec(code="cu", name="沪铜2", category=CommodityCategory.NON_FERROUS_METAL,
                          currency="CNY", akshare_api=None, akshare_symbol="cu0"),
        ]
        with pytest.raises(ValueError, match="商品 code 重复"):
            _build_index(specs)

    def test_get_commodity_success(self):
        """获取商品规格成功。"""
        spec = get_commodity("cu")
        assert spec.code == "cu"
        assert spec.name == "沪铜"
        assert spec.currency == "CNY"

    def test_get_commodity_unknown_raises(self):
        """未知商品 code 抛出 KeyError。"""
        with pytest.raises(KeyError, match="未知商品 code"):
            get_commodity("unknown")

    def test_list_commodities_all(self):
        """列出全部商品。"""
        specs = list_commodities()
        assert len(specs) == 18

    def test_list_commodities_by_category(self):
        """按类别列出商品。"""
        specs = list_commodities(CommodityCategory.NON_FERROUS_METAL)
        assert len(specs) == 6
        assert all(s.category == CommodityCategory.NON_FERROUS_METAL for s in specs)

    def test_supports_akshare(self):
        """判断是否支持 Akshare。"""
        cu = get_commodity("cu")
        assert supports_akshare(cu) is True

        pl = get_commodity("PL")
        assert supports_akshare(pl) is False

    def test_supports_yfinance(self):
        """判断是否支持 yfinance。"""
        cu = get_commodity("cu")
        assert supports_yfinance(cu) is False

        gc = get_commodity("GC")
        assert supports_yfinance(gc) is True

        pl = get_commodity("PL")
        assert supports_yfinance(pl) is True


# ===========================================================================
# 数据规范化测试
# ===========================================================================

class TestDataNormalization:
    """数据规范化测试。"""

    def test_normalize_main_sina_empty(self):
        """空 DataFrame 规范化。"""
        df = pd.DataFrame()
        result = _normalize_main_sina(df, "CNY")
        assert result.empty
        assert "source" in result.columns
        assert result["source"].iloc[0] == "akshare" if not result.empty else True

    def test_normalize_main_sina_with_data(self):
        """有数据的 DataFrame 规范化。"""
        df = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-02"],
            "开盘价": [100.0, 101.0],
            "最高价": [102.0, 103.0],
            "最低价": [99.0, 100.0],
            "收盘价": [101.0, 102.0],
            "成交量": [1000, 1100],
        })
        result = _normalize_main_sina(df, "CNY")
        assert len(result) == 2
        assert result["source"].iloc[0] == "akshare"
        assert result["currency"].iloc[0] == "CNY"
        assert result["open"].iloc[0] == 100.0

    def test_normalize_foreign_hist_empty(self):
        """外盘历史空 DataFrame 规范化。"""
        df = pd.DataFrame()
        result = _normalize_foreign_hist(df, "USD")
        assert result.empty

    def test_normalize_foreign_hist_with_data(self):
        """外盘历史有数据规范化。"""
        df = pd.DataFrame({
            "日期": ["2025-01-01"],
            "开盘价": [2000.0],
            "最高价": [2010.0],
            "最低价": [1990.0],
            "收盘价": [2005.0],
            "成交量": [5000],
        })
        result = _normalize_foreign_hist(df, "USD")
        assert len(result) == 1
        assert result["source"].iloc[0] == "akshare"
        assert result["currency"].iloc[0] == "USD"

    def test_normalize_yfinance_empty(self):
        """yfinance 空 DataFrame 规范化。"""
        df = pd.DataFrame()
        result = _normalize_yfinance(df, "USD")
        assert result.empty

    def test_normalize_yfinance_with_data(self):
        """yfinance 有数据规范化。"""
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2025-01-01"]),
            "Open": [2000.0],
            "High": [2010.0],
            "Low": [1990.0],
            "Close": [2005.0],
            "Volume": [5000],
        })
        result = _normalize_yfinance(df, "USD")
        assert len(result) == 1
        assert result["source"].iloc[0] == "yfinance"
        assert result["currency"].iloc[0] == "USD"

    def test_normalize_yfinance_multiindex_columns(self):
        """yfinance MultiIndex 列规范化。"""
        arrays = [["Open", "High", "Low", "Close", "Volume"], ["GC=F", "GC=F", "GC=F", "GC=F", "GC=F"]]
        tuples = list(zip(*arrays))
        index = pd.MultiIndex.from_tuples(tuples)
        df = pd.DataFrame([[2000.0, 2010.0, 1990.0, 2005.0, 5000]],
                          index=pd.to_datetime(["2025-01-01"]), columns=index)
        df.index.name = "Date"
        result = _normalize_yfinance(df, "USD")
        assert len(result) == 1
        assert result["open"].iloc[0] == 2000.0


# ===========================================================================
# 日期过滤测试
# ===========================================================================

class TestDateFilter:
    """日期过滤测试。"""

    def test_filter_by_date_range_empty(self):
        """空 DataFrame 过滤。"""
        df = pd.DataFrame()
        result = _filter_by_date_range(df, "20250101", "20250131")
        assert result.empty

    def test_filter_by_date_range_with_data(self):
        """有数据过滤。"""
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01", "2025-01-15", "2025-02-01"]),
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000, 1100, 1200],
        })
        result = _filter_by_date_range(df, "20250101", "20250131")
        assert len(result) == 2
        assert result["date"].iloc[0] == pd.Timestamp("2025-01-01")
        assert result["date"].iloc[1] == pd.Timestamp("2025-01-15")

    def test_filter_by_date_range_no_start(self):
        """无起始日期过滤。"""
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01", "2025-01-15", "2025-02-01"]),
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000, 1100, 1200],
        })
        result = _filter_by_date_range(df, None, "20250115")
        assert len(result) == 2

    def test_filter_by_date_range_no_end(self):
        """无结束日期过滤。"""
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01", "2025-01-15", "2025-02-01"]),
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000, 1100, 1200],
        })
        result = _filter_by_date_range(df, "20250115", None)
        assert len(result) == 2


# ===========================================================================
# Akshare 获取器测试（mock）
# ===========================================================================

class TestAkshareFetcher:
    """Akshare 数据获取器测试。"""

    @patch("tools.common.commodity_price.ak")
    def test_fetch_shfe_futures_success(self, mock_ak):
        """上期所期货获取成功。"""
        mock_df = pd.DataFrame({
            "日期": ["2025-01-01"],
            "开盘价": [100.0],
            "最高价": [102.0],
            "最低价": [99.0],
            "收盘价": [101.0],
            "成交量": [1000],
        })
        mock_ak.futures_main_sina.return_value = mock_df

        spec = get_commodity("cu")
        result = _fetch_akshare(spec, "20250101", "20250101")
        assert len(result) == 1
        assert result["source"].iloc[0] == "akshare"

    @patch("tools.common.commodity_price.ak")
    def test_fetch_foreign_futures_success(self, mock_ak):
        """外盘期货获取成功。"""
        mock_df = pd.DataFrame({
            "日期": ["2025-01-01"],
            "开盘价": [2000.0],
            "最高价": [2010.0],
            "最低价": [1990.0],
            "收盘价": [2005.0],
            "成交量": [5000],
        })
        mock_ak.futures_foreign_hist.return_value = mock_df

        spec = get_commodity("GC")
        result = _fetch_akshare(spec, "20250101", "20250101")
        assert len(result) == 1
        assert result["source"].iloc[0] == "akshare"

    @patch("tools.common.commodity_price.ak")
    def test_fetch_max_records_limit(self, mock_ak):
        """最大记录数限制。"""
        mock_df = pd.DataFrame({
            "日期": [f"2025-01-{i:02d}" for i in range(1, 21)],
            "开盘价": [100.0] * 20,
            "最高价": [102.0] * 20,
            "最低价": [99.0] * 20,
            "收盘价": [101.0] * 20,
            "成交量": [1000] * 20,
        })
        mock_ak.futures_main_sina.return_value = mock_df

        spec = get_commodity("cu")
        result = _fetch_akshare(spec, max_records=10)
        assert len(result) == 10


# ===========================================================================
# yfinance 获取器测试（mock）
# ===========================================================================

class TestYFinanceFetcher:
    """yfinance 数据获取器测试。"""

    @patch("tools.common.commodity_price.yf")
    def test_fetch_success(self, mock_yf):
        """yfinance 获取成功。"""
        mock_df = pd.DataFrame({
            "Date": pd.to_datetime(["2025-01-01"]),
            "Open": [2000.0],
            "High": [2010.0],
            "Low": [1990.0],
            "Close": [2005.0],
            "Volume": [5000],
        })
        mock_yf.download.return_value = mock_df

        spec = get_commodity("GC")
        result = _fetch_yfinance(spec, "2025-01-01", "2025-01-01")
        assert len(result) == 1
        assert result["source"].iloc[0] == "yfinance"

    @patch("tools.common.commodity_price.yf")
    def test_fetch_empty_raises(self, mock_yf):
        """yfinance 返回空数据抛出异常。"""
        mock_yf.download.return_value = pd.DataFrame()

        spec = get_commodity("GC")
        with pytest.raises(CommodityFetchError, match="yfinance 返回空数据"):
            _fetch_yfinance(spec, "2025-01-01", "2025-01-01")

    @patch("tools.common.commodity_price.yf")
    def test_fetch_max_records_limit(self, mock_yf):
        """最大记录数限制。"""
        mock_df = pd.DataFrame({
            "Date": pd.to_datetime([f"2025-01-{i:02d}" for i in range(1, 21)]),
            "Open": [2000.0] * 20,
            "High": [2010.0] * 20,
            "Low": [1990.0] * 20,
            "Close": [2005.0] * 20,
            "Volume": [5000] * 20,
        })
        mock_yf.download.return_value = mock_df

        spec = get_commodity("GC")
        result = _fetch_yfinance(spec, max_records=10)
        assert len(result) == 10


# ===========================================================================
# 主调度器测试
# ===========================================================================

class TestMainFetcher:
    """主调度器测试。"""

    @patch("tools.common.commodity_price._fetch_akshare")
    def test_fetch_akshare_success(self, mock_fetch):
        """Akshare 获取成功。"""
        mock_df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01"]),
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [101.0],
            "volume": [1000],
            "source": ["akshare"],
            "currency": ["CNY"],
        })
        mock_fetch.return_value = mock_df

        result = fetch_commodity("cu")
        assert result.source == "akshare"
        assert result.fallback_used is False
        assert len(result.data) == 1

    @patch("tools.common.commodity_price._fetch_yfinance")
    @patch("tools.common.commodity_price._fetch_akshare")
    def test_fetch_akshare_fails_yfinance_fallback(self, mock_ak, mock_yf):
        """Akshare 失败，yfinance 回退成功。"""
        mock_ak.side_effect = Exception("Akshare 失败")
        mock_df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01"]),
            "open": [2000.0],
            "high": [2010.0],
            "low": [1990.0],
            "close": [2005.0],
            "volume": [5000],
            "source": ["yfinance"],
            "currency": ["USD"],
        })
        mock_yf.return_value = mock_df

        result = fetch_commodity("GC")
        assert result.source == "yfinance"
        assert result.fallback_used is True

    @patch("tools.common.commodity_price._fetch_yfinance")
    @patch("tools.common.commodity_price._fetch_akshare")
    def test_fetch_both_fail_raises(self, mock_ak, mock_yf):
        """两个数据源均失败抛出异常。"""
        mock_ak.side_effect = Exception("Akshare 失败")
        mock_yf.side_effect = Exception("yfinance 失败")

        with pytest.raises(CommodityFetchError, match="所有数据源均获取失败"):
            fetch_commodity("GC")

    def test_fetch_unknown_code_raises(self):
        """未知商品 code 抛出异常。"""
        with pytest.raises(KeyError):
            fetch_commodity("unknown")

    @patch("tools.common.commodity_price._fetch_yfinance")
    def test_fetch_yfinance_only(self, mock_yf):
        """仅 yfinance 支持的品种。"""
        mock_df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-01"]),
            "open": [1000.0],
            "high": [1010.0],
            "low": [990.0],
            "close": [1005.0],
            "volume": [1000],
            "source": ["yfinance"],
            "currency": ["USD"],
        })
        mock_yf.return_value = mock_df

        result = fetch_commodity("PL")
        assert result.source == "yfinance"
        assert result.fallback_used is False


# ===========================================================================
# 批量获取测试
# ===========================================================================

class TestBatchFetcher:
    """批量获取测试。"""

    @patch("tools.common.commodity_price.fetch_commodity")
    def test_fetch_many_success(self, mock_fetch):
        """批量获取成功。"""
        mock_fetch.return_value = FetchResult(
            code="cu", name="沪铜", source="akshare",
            data=[{"date": "2025-01-01", "close": 100.0}],
            fallback_used=False, message="成功",
        )

        results = fetch_many(["cu", "al"], batch_interval=0)
        assert len(results) == 2
        assert all(r.source == "akshare" for r in results)

    def test_fetch_many_exceeds_limit_raises(self):
        """批量获取超过限制抛出异常。"""
        codes = [f"code{i}" for i in range(11)]
        with pytest.raises(CommodityFetchError, match="单次批量获取最多支持 10 个品种"):
            fetch_many(codes)

    @patch("tools.common.commodity_price.fetch_commodity")
    def test_fetch_many_partial_failure(self, mock_fetch):
        """批量获取部分失败。"""
        def side_effect(code, *args, **kwargs):
            if code == "cu":
                return FetchResult(code="cu", name="沪铜", source="akshare",
                                   data=[], fallback_used=False, message="成功")
            raise CommodityFetchError("获取失败")

        mock_fetch.side_effect = side_effect

        results = fetch_many(["cu", "unknown"], batch_interval=0)
        assert len(results) == 2
        assert results[0].source == "akshare"
        assert results[1].source == "failed"


# ===========================================================================
# CLI 入口测试
# ===========================================================================

class TestCLI:
    """CLI 入口测试。"""

    def test_cmd_list(self):
        """--list 命令。"""
        output = cmd_list()
        assert output["success"] is True
        assert len(output["data"]) == 4  # 4 个类别
        assert output["meta"]["total_count"] == 18

    @patch("tools.common.commodity_price.fetch_commodity")
    def test_cmd_fetch_single(self, mock_fetch):
        """--code 单品种命令。"""
        mock_fetch.return_value = FetchResult(
            code="cu", name="沪铜", source="akshare",
            data=[{"date": "2025-01-01", "close": 100.0}],
            fallback_used=False, message="成功",
        )

        output = cmd_fetch("cu")
        assert output["success"] is True
        assert output["data"]["code"] == "cu"
        assert output["data"]["source"] == "akshare"

    @patch("tools.common.commodity_price.fetch_many")
    def test_cmd_fetch_batch(self, mock_fetch_many):
        """--code 多品种命令。"""
        mock_fetch_many.return_value = [
            FetchResult(code="cu", name="沪铜", source="akshare",
                        data=[], fallback_used=False, message="成功"),
            FetchResult(code="al", name="沪铝", source="akshare",
                        data=[], fallback_used=False, message="成功"),
        ]

        output = cmd_fetch("cu,al")
        assert output["success"] is True
        assert output["data"]["batch"] is True
        assert len(output["data"]["results"]) == 2

    def test_cmd_fetch_empty_code(self):
        """--code 空值。"""
        output = cmd_fetch("")
        assert output["success"] is False
        assert "请提供商品代码" in output["error"]


# ===========================================================================
# 运行测试
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
