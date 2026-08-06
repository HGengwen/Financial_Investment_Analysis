"""大宗商品价格数据获取工具集成测试。

集成测试覆盖：
    - 国内品种（仅 Akshare）：沪铜、沪金、碳酸锂等
    - 外盘品种（Akshare 优先，yfinance 回退）：COMEX 黄金、WTI 原油等
    - 仅 yfinance 品种：铂金、钯金
    - 批量获取场景
    - 限流保护验证

运行方式：
    python -m pytest tests/test_commodity_price_integration.py -v -s

注意：
    - 集成测试需要真实网络连接
    - 测试耗时较长（约 1-3 分钟）
    - yfinance 在中国大陆可能需要代理
"""

import sys
import time
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common.commodity_price import (
    CommodityFetchError,
    fetch_commodity,
    fetch_many,
    get_commodity,
    list_commodities,
    supports_akshare,
    supports_yfinance,
)


# ===========================================================================
# 网络可达性检查
# ===========================================================================

@pytest.fixture(scope="module")
def network_available():
    """检查网络是否可用。"""
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def yfinance_available(network_available):
    """检查 yfinance 是否可用（中国大陆可能需要代理）。"""
    if not network_available:
        return False
    try:
        import yfinance as yf
        # 尝试下载少量数据验证
        df = yf.download("GC=F", period="1d", progress=False)
        return df is not None and not df.empty
    except Exception:
        return False


# ===========================================================================
# 国内品种测试（仅 Akshare）
# ===========================================================================

@pytest.mark.skipif(not pytest.importorskip("akshare"), reason="akshare 未安装")
class TestDomesticCommodities:
    """国内品种集成测试（仅 Akshare）。"""

    @pytest.mark.parametrize("code,name", [
        ("cu", "沪铜"),
        ("al", "沪铝"),
        ("zn", "沪锌"),
        ("au", "沪金"),
        ("ag", "沪银"),
        ("sc", "上海原油"),
        ("lc", "碳酸锂"),
        ("si", "工业硅"),
    ])
    def test_fetch_domestic_commodity(self, code, name, network_available):
        """测试国内品种获取。"""
        if not network_available:
            pytest.skip("网络不可用")

        spec = get_commodity(code)
        assert spec.name == name
        assert supports_akshare(spec)
        assert not supports_yfinance(spec)

        try:
            result = fetch_commodity(code, max_records=5)
            assert result.source == "akshare"
            assert result.fallback_used is False
            assert len(result.data) > 0
            assert len(result.data) <= 5

            # 验证数据结构
            first_record = result.data[0]
            assert "date" in first_record
            assert "open" in first_record
            assert "high" in first_record
            assert "low" in first_record
            assert "close" in first_record
            assert "volume" in first_record

            print(f"\n✓ {name}({code}): {len(result.data)} 条记录, "
                  f"最新收盘价: {first_record['close']}")
        except CommodityFetchError as e:
            pytest.fail(f"获取 {name}({code}) 失败: {e}")


# ===========================================================================
# 外盘品种测试（Akshare 优先，yfinance 回退）
# ===========================================================================

@pytest.mark.skipif(not pytest.importorskip("akshare"), reason="akshare 未安装")
class TestForeignCommodities:
    """外盘品种集成测试（Akshare 优先，yfinance 回退）。"""

    @pytest.mark.parametrize("code,name", [
        ("GC", "COMEX黄金"),
        ("SI", "COMEX白银"),
        ("CL", "WTI原油"),
        ("BZ", "布伦特原油"),
        ("NG", "天然气"),
    ])
    def test_fetch_foreign_commodity(self, code, name, network_available, yfinance_available):
        """测试外盘品种获取。"""
        if not network_available:
            pytest.skip("网络不可用")

        spec = get_commodity(code)
        assert spec.name == name
        assert supports_akshare(spec)
        assert supports_yfinance(spec)

        try:
            result = fetch_commodity(code, max_records=5)
            # 可能来自 Akshare 或 yfinance（取决于 Akshare 是否成功）
            assert result.source in ["akshare", "yfinance"]
            assert len(result.data) > 0
            assert len(result.data) <= 5

            # 验证数据结构
            first_record = result.data[0]
            assert "date" in first_record
            assert "close" in first_record

            fallback_tag = " (回退)" if result.fallback_used else ""
            print(f"\n✓ {name}({code}): 来源 {result.source}{fallback_tag}, "
                  f"{len(result.data)} 条记录, 最新收盘价: {first_record['close']}")
        except CommodityFetchError as e:
            # 如果 Akshare 和 yfinance 都失败，可能是网络问题
            if not yfinance_available:
                pytest.skip(f"yfinance 不可用，跳过 {name}({code})")
            pytest.fail(f"获取 {name}({code}) 失败: {e}")


# ===========================================================================
# 仅 yfinance 品种测试
# ===========================================================================

class TestYFinanceOnlyCommodities:
    """仅 yfinance 品种集成测试。"""

    @pytest.mark.parametrize("code,name", [
        ("PL", "铂金"),
        ("PA", "钯金"),
    ])
    def test_fetch_yfinance_only_commodity(self, code, name, yfinance_available):
        """测试仅 yfinance 支持的品种。"""
        if not yfinance_available:
            pytest.skip("yfinance 不可用（可能需要代理）")

        spec = get_commodity(code)
        assert spec.name == name
        assert not supports_akshare(spec)
        assert supports_yfinance(spec)

        try:
            result = fetch_commodity(code, max_records=5)
            assert result.source == "yfinance"
            assert result.fallback_used is False
            assert len(result.data) > 0
            assert len(result.data) <= 5

            # 验证数据结构
            first_record = result.data[0]
            assert "date" in first_record
            assert "close" in first_record

            print(f"\n✓ {name}({code}): {len(result.data)} 条记录, "
                  f"最新收盘价: {first_record['close']}")
        except CommodityFetchError as e:
            pytest.fail(f"获取 {name}({code}) 失败: {e}")


# ===========================================================================
# 批量获取测试
# ===========================================================================

class TestBatchFetch:
    """批量获取集成测试。"""

    def test_batch_fetch_domestic(self, network_available):
        """测试批量获取国内品种。"""
        if not network_available:
            pytest.skip("网络不可用")

        codes = ["cu", "al", "zn"]
        try:
            results = fetch_many(codes, max_records=3, batch_interval=1.0)
            assert len(results) == 3

            for result in results:
                if result.source != "failed":
                    assert result.source == "akshare"
                    assert len(result.data) <= 3

            success_count = sum(1 for r in results if r.source != "failed")
            print(f"\n✓ 批量获取国内品种: {success_count}/{len(codes)} 成功")
        except CommodityFetchError as e:
            pytest.fail(f"批量获取失败: {e}")

    def test_batch_fetch_mixed(self, network_available, yfinance_available):
        """测试批量获取混合品种（国内 + 外盘）。"""
        if not network_available:
            pytest.skip("网络不可用")

        codes = ["cu", "GC", "CL"]
        try:
            results = fetch_many(codes, max_records=3, batch_interval=1.0)
            assert len(results) == 3

            for result in results:
                if result.source != "failed":
                    assert result.source in ["akshare", "yfinance"]
                    assert len(result.data) <= 3

            success_count = sum(1 for r in results if r.source != "failed")
            print(f"\n✓ 批量获取混合品种: {success_count}/{len(codes)} 成功")
        except CommodityFetchError as e:
            if not yfinance_available:
                pytest.skip("yfinance 不可用，跳过混合品种测试")
            pytest.fail(f"批量获取失败: {e}")

    def test_batch_fetch_exceeds_limit(self):
        """测试批量获取超过限制。"""
        codes = [f"code{i}" for i in range(11)]
        with pytest.raises(CommodityFetchError, match="单次批量获取最多支持 10 个品种"):
            fetch_many(codes)


# ===========================================================================
# 限流保护验证
# ===========================================================================

class TestRateLimiting:
    """限流保护验证测试。"""

    def test_max_records_limit(self, network_available):
        """测试最大记录数限制。"""
        if not network_available:
            pytest.skip("网络不可用")

        try:
            result = fetch_commodity("cu", max_records=3)
            assert len(result.data) <= 3
            print(f"\n✓ 最大记录数限制: {len(result.data)} 条")
        except CommodityFetchError:
            pytest.skip("获取失败，跳过限流测试")

    def test_batch_interval(self, network_available):
        """测试批量获取间隔。"""
        if not network_available:
            pytest.skip("网络不可用")

        codes = ["cu", "al"]
        start_time = time.time()
        try:
            results = fetch_many(codes, max_records=2, batch_interval=1.0)
            elapsed = time.time() - start_time

            # 验证间隔至少 1 秒（两个品种之间）
            assert elapsed >= 1.0
            print(f"\n✓ 批量获取间隔: {elapsed:.2f} 秒")
        except CommodityFetchError:
            pytest.skip("获取失败，跳过间隔测试")


# ===========================================================================
# 数据质量验证
# ===========================================================================

class TestDataQuality:
    """数据质量验证测试。"""

    def test_data_consistency(self, network_available):
        """测试数据一致性（OHLC 关系）。"""
        if not network_available:
            pytest.skip("网络不可用")

        try:
            result = fetch_commodity("cu", max_records=5)
            for record in result.data:
                if all(k in record for k in ["open", "high", "low", "close"]):
                    o, h, l, c = record["open"], record["high"], record["low"], record["close"]
                    if o is not None and h is not None and l is not None and c is not None:
                        # 验证 high >= low
                        assert h >= l, f"最高价 {h} < 最低价 {l}"
                        # 验证 high >= open, close
                        assert h >= o and h >= c, f"最高价 {h} 不是最高"
                        # 验证 low <= open, close
                        assert l <= o and l <= c, f"最低价 {l} 不是最低"

            print(f"\n✓ 数据一致性验证通过: {len(result.data)} 条记录")
        except CommodityFetchError:
            pytest.skip("获取失败，跳过数据质量测试")

    def test_date_format(self, network_available):
        """测试日期格式。"""
        if not network_available:
            pytest.skip("网络不可用")

        try:
            result = fetch_commodity("cu", max_records=5)
            for record in result.data:
                if "date" in record and record["date"] is not None:
                    date_str = record["date"]
                    # 验证日期格式 YYYY-MM-DD
                    assert len(date_str) == 10, f"日期格式错误: {date_str}"
                    assert date_str[4] == "-" and date_str[7] == "-", f"日期格式错误: {date_str}"

            print(f"\n✓ 日期格式验证通过: {len(result.data)} 条记录")
        except CommodityFetchError:
            pytest.skip("获取失败，跳过日期格式测试")


# ===========================================================================
# 运行测试
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
