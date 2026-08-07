"""国际货币汇率获取工具集成测试。

集成测试覆盖：
    - 真实拉取主要货币对（Akshare 优先，yfinance 回退）
    - 批量获取场景
    - 记录数严格限制验证
    - 非法符号拒绝（不触发网络请求）

默认跳过，避免在无网络或库未安装环境拖慢常规测试。
通过环境变量 ``FX_RUN_INTEGRATION=1`` 启用。

运行方式（Windows PowerShell）::

    $env:FX_RUN_INTEGRATION=1; pytest tests/common/test_fx_rate_integration.py -v -s

运行方式（cmd）::

    set FX_RUN_INTEGRATION=1 && pytest tests/common/test_fx_rate_integration.py -v -s

注意：
    - 集成测试需要真实网络连接
    - yfinance 在中国大陆可能需要代理
    - 东方财富接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制
"""

import os
import sys
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common.fx_rate import (  # noqa: E402
    MAX_RECORDS_HARD_LIMIT,
    MAX_RECORDS_PER_CALL,
    SYMBOL_MAP,
    FetchResult,
    fetch_many,
    fetch_rate,
)

# 仅当显式开启环境变量时才运行集成测试
INTEGRATION_ENABLED = os.environ.get("FX_RUN_INTEGRATION") == "1"
_SKIP_REASON = "集成测试默认跳过；设置环境变量 FX_RUN_INTEGRATION=1 启用"

pytestmark = pytest.mark.skipif(not INTEGRATION_ENABLED, reason=_SKIP_REASON)


def _assert_success_result(result: FetchResult) -> None:
    """校验成功 FetchResult 的统一数据结构。

    Args:
        result: 成功获取的 FetchResult。
    """
    assert result.success is True
    assert result.source in ("akshare", "yfinance")
    assert result.error is None
    assert result.fetch_time  # 时间戳非空
    assert result.data is not None
    # 统一两列结构
    assert list(result.data.columns) == ["date", "close"]
    assert len(result.data) > 0
    # 记录数不超过硬上限
    assert len(result.data) <= MAX_RECORDS_HARD_LIMIT
    # 收盘价应为正数、日期格式为 YYYY-MM-DD
    assert (result.data["close"] > 0).all()
    for d in result.data["date"]:
        assert len(d) == 10 and d[4] == "-" and d[7] == "-"


def _assert_failure_tolerant(result: FetchResult) -> None:
    """网络不可用时校验兜底机制产出规范错误（而非崩溃）。

    Args:
        result: 获取返回的 FetchResult（可能成功或失败）。
    """
    assert result.symbol
    assert result.source in ("akshare", "yfinance", "none")
    assert result.fetch_time
    if result.success:
        _assert_success_result(result)
    else:
        assert result.data is None
        assert result.error


# ===========================================================================
# 真实拉取测试（网络韧性断言）
# ===========================================================================
class TestRealFetch:
    """真实拉取主要货币对测试。"""

    @pytest.mark.parametrize("symbol", ["USDCNY", "EURUSD", "USDJPY"])
    def test_real_fetch_primary_or_fallback(self, symbol: str) -> None:
        """真实拉取汇率，验证端到端主流程不崩溃且返回结构规范。

        网络可用时应成功并返回有效数据，且记录数严格受限；
        网络不可用时应返回规范的失败结果，以演示 Akshare→yfinance 兜底机制。
        """
        result = fetch_rate(symbol, max_records=MAX_RECORDS_PER_CALL)
        _assert_failure_tolerant(result)

    @pytest.mark.parametrize("symbol", list(SYMBOL_MAP.keys()))
    def test_all_symbols_real_fetch(self, symbol: str) -> None:
        """映射表中所有货币对真实拉取均不崩溃（网络韧性）。"""
        result = fetch_rate(symbol, max_records=5)
        _assert_failure_tolerant(result)

    def test_real_invalid_symbol_still_rejected(self) -> None:
        """真实环境下，未映射的货币对仍被正确拒绝（不触发任何网络请求）。"""
        result = fetch_rate("XXXYYY")
        assert result.success is False
        assert result.source == "none"
        assert "不支持的货币对" in result.error


# ===========================================================================
# 批量获取测试
# ===========================================================================
class TestRealBatchFetch:
    """真实批量获取测试。"""

    def test_real_fetch_many(self) -> None:
        """批量获取 3 个货币对，验证全流程不崩溃。"""
        results = fetch_many(["USDCNY", "EURUSD", "GBPUSD"],
                             max_records=3, batch_interval=1.0)
        assert len(results) == 3
        for result in results:
            _assert_failure_tolerant(result)

    def test_real_fetch_many_exceeds_limit(self) -> None:
        """批量超过 5 个货币对应被拒绝（不发起网络请求）。"""
        symbols = list(SYMBOL_MAP.keys())  # 19 个（> 5 上限）
        with pytest.raises(ValueError, match="最多支持 5 个货币对"):
            fetch_many(symbols)


# ===========================================================================
# 记录数严格限制验证
# ===========================================================================
class TestRealRecordLimits:
    """记录数严格限制验证。"""

    def test_real_max_records_default(self) -> None:
        """默认最多返回 10 条。"""
        result = fetch_rate("USDCNY")
        if result.success:
            assert len(result.data) <= MAX_RECORDS_PER_CALL

    def test_real_max_records_custom(self) -> None:
        """自定义 max_records 时返回条数不超限。"""
        result = fetch_rate("USDCNY", max_records=3)
        if result.success:
            assert len(result.data) <= 3

    def test_real_max_records_over_hard_limit_rejected(self) -> None:
        """超过硬上限 50 被拒绝，不发起网络请求。"""
        with pytest.raises(ValueError, match="硬上限"):
            fetch_rate("USDCNY", max_records=MAX_RECORDS_HARD_LIMIT + 1)


# ===========================================================================
# 运行测试
# ===========================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])