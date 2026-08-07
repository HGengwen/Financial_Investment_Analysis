"""国际货币汇率获取工具单元测试。

测试覆盖：
    - 货币对符号映射表配置
    - Akshare 主路径（成功、中文列名解析、客户端日期过滤）
    - yfinance 回退路径（Akshare 异常/空数据/区间无数据）
    - 双数据源均失败、非法符号拒绝
    - 重试机制（瞬时异常重试、非瞬时不重试、超次数抛出）
    - 极小请求（直连东方财富 klines、最小字段与 lmt 校验）
    - 限流器（间隔不足阻塞补足、间隔足够不阻塞）
    - 记录数限制（默认 10、硬上限 50 校验）
    - 批量获取限流保护（最多 5 个货币对）
    - CLI 入口

运行方式：
    python -m pytest tests/common/test_fx_rate.py -v
"""

import json
import sys
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common.fx_rate import (  # noqa: E402
    MAX_BATCH_SIZE,
    MAX_RECORDS_HARD_LIMIT,
    MAX_RECORDS_PER_CALL,
    SYMBOL_MAP,
    FXFetcher,
    FetchResult,
    _MAX_RETRIES,
    _RateLimiter,
    _call_with_retry,
    _eastmoney_hist_small,
    _enforce_max_records,
    _is_transient,
    _is_ban_signal,
    _parse_int_env,
    _validate_max_records,
    cmd_fetch,
    cmd_list,
    fetch_many,
    fetch_rate,
)
from tools.common import fx_rate as fx_module  # noqa: E402


# ---------------------------------------------------------------------------
# 测试用造数工具
# ---------------------------------------------------------------------------
def make_akshare_df() -> pd.DataFrame:
    """构造模拟的 Akshare 返回数据（英文列名，日期落在测试区间内）。"""
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "open": [7.10, 7.11, 7.12],
            "high": [7.12, 7.13, 7.14],
            "low": [7.09, 7.10, 7.11],
            "close": [7.11, 7.12, 7.10],
        }
    )


def make_akshare_df_cn() -> pd.DataFrame:
    """构造模拟的 Akshare 返回数据（中文列名，含「最新价」），验证兼容性。"""
    return pd.DataFrame(
        {
            "日期": ["2024-01-02", "2024-01-03"],
            "代码": ["USDCNH", "USDCNH"],
            "名称": ["美元兑离岸人民币", "美元兑离岸人民币"],
            "今开": [7.10, 7.11],
            "最新价": [7.11, 7.12],
            "最高": [7.12, 7.13],
            "最低": [7.09, 7.10],
            "振幅": [0.42, 0.42],
        }
    )


def make_akshare_df_wide() -> pd.DataFrame:
    """构造跨大区间的 Akshare 返回数据，用于验证客户端日期过滤。

    数据横跨 2023-12 ~ 2024-02，仅部分落在请求区间 [2024-01-01, 2024-01-31] 内。
    """
    return pd.DataFrame(
        {
            "date": [
                "2023-12-28", "2023-12-29",
                "2024-01-02", "2024-01-03", "2024-01-04",
                "2024-02-01", "2024-02-02",
            ],
            "close": [7.08, 7.09, 7.11, 7.12, 7.10, 7.15, 7.16],
        }
    )


def make_yfinance_df_single() -> pd.DataFrame:
    """构造模拟的 yfinance 返回数据（单层列，旧版）。"""
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame({"Close": [7.11, 7.12]}, index=dates)


def make_yfinance_df_multi() -> pd.DataFrame:
    """构造模拟的 yfinance 返回数据（MultiIndex 列，新版）。"""
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    cols = pd.MultiIndex.from_tuples(
        [("Close", "CNY=X"), ("Open", "CNY=X"), ("High", "CNY=X")]
    )
    return pd.DataFrame(
        [[7.11, 7.10, 7.12], [7.12, 7.11, 7.13]], index=dates, columns=cols
    )


def make_empty_df() -> pd.DataFrame:
    """构造空 DataFrame。"""
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# 符号映射表测试
# ---------------------------------------------------------------------------
class TestSymbolMap:
    """货币对符号映射表测试。"""

    def test_has_nineteen_symbols(self) -> None:
        """映射表包含 19 个货币对。"""
        assert len(SYMBOL_MAP) == 19

    def test_has_expected_symbols(self) -> None:
        """包含预期的主要货币对。"""
        expected = {"USDCNY", "USDCNH", "EURUSD", "GBPUSD", "USDJPY",
                    "AUDUSD", "USDCAD", "USDCHF", "USDHKD",
                    "EURCNY", "GBPCNY", "JPYCNY", "AUDCNY", "CADCNY",
                    "CHFCNY", "NZDCNY", "SGDCNY", "CNYHKD", "HKDCNY"}
        assert set(SYMBOL_MAP.keys()) == expected

    def test_each_symbol_has_both_sources(self) -> None:
        """每个货币对都配置了 akshare 与 yfinance 双源代码。"""
        for symbol, sources in SYMBOL_MAP.items():
            assert "akshare" in sources and sources["akshare"]
            assert "yfinance" in sources and sources["yfinance"]

    def test_usdcny_uses_cnh_proxy(self) -> None:
        """USDCNY 以离岸 USDCNH 作为 akshare 代理。"""
        assert SYMBOL_MAP["USDCNY"]["akshare"] == "USDCNH"
        assert SYMBOL_MAP["USDCNY"]["yfinance"] == "CNY=X"

    def test_cross_rate_symbols_map_to_cnh(self) -> None:
        """人民币交叉汇率以离岸 CNH 代理，yfinance 用对应 CNY=X。"""
        cross_expected = {
            "EURCNY": ("EURCNH", "EURCNY=X"),
            "GBPCNY": ("GBPCNH", "GBPCNY=X"),
            "JPYCNY": ("JPYCNH", "JPYCNY=X"),
            "AUDCNY": ("AUDCNH", "AUDCNY=X"),
            "CADCNY": ("CADCNH", "CADCNY=X"),
            "CHFCNY": ("CHFCNH", "CHFCNY=X"),
            "NZDCNY": ("NZDCNH", "NZDCNY=X"),
            "SGDCNY": ("SGDCNH", "SGDCNY=X"),
        }
        for symbol, (akshare_code, yf_ticker) in cross_expected.items():
            assert SYMBOL_MAP[symbol]["akshare"] == akshare_code, symbol
            assert SYMBOL_MAP[symbol]["yfinance"] == yf_ticker, symbol

    def test_hkd_cross_rates_bidirectional(self) -> None:
        """人民币与港币双向映射正确。"""
        assert SYMBOL_MAP["CNYHKD"]["akshare"] == "CNHHKD"
        assert SYMBOL_MAP["CNYHKD"]["yfinance"] == "CNYHKD=X"
        assert SYMBOL_MAP["HKDCNY"]["akshare"] == "HKDCNH"
        assert SYMBOL_MAP["HKDCNY"]["yfinance"] == "HKDCNY=X"


# ---------------------------------------------------------------------------
# 正向流程
# ---------------------------------------------------------------------------
class TestFetchSuccess:
    """Akshare 成功路径测试。"""

    def test_fetch_success_with_akshare(self) -> None:
        """Akshare 成功时直接返回，不应触发 yfinance 回退。"""
        ak_calls: list = []
        yf_calls: list = []

        def ak_call(sym):
            ak_calls.append(sym)
            return make_akshare_df()

        def yf_call(sym, s, e):
            yf_calls.append((sym, s, e))
            return make_yfinance_df_single()

        fetcher = FXFetcher(akshare_call=ak_call, yfinance_call=yf_call)
        result = fetcher.fetch("USDCNY", "2024-01-01", "2024-01-31")

        assert result.success is True
        assert result.source == "akshare"
        assert result.error is None
        # USDCNY 在映射表中对应 akshare 代码 USDCNH
        assert ak_calls == ["USDCNH"]
        # yfinance 不应被调用
        assert yf_calls == []
        # 数据规范化：两列、行数正确
        assert list(result.data.columns) == ["date", "close"]
        assert len(result.data) == 3
        assert result.data["close"].iloc[0] == pytest.approx(7.11)

    def test_fetch_success_with_akshare_chinese_columns(self) -> None:
        """Akshare 返回中文列名（含「最新价」）时也能正确解析。"""
        fetcher = FXFetcher(
            akshare_call=lambda sym: make_akshare_df_cn(),
            yfinance_call=lambda sym, s, e: make_yfinance_df_single(),
        )
        result = fetcher.fetch("USDCNY", "2024-01-01", "2024-01-31")

        assert result.success is True
        assert result.source == "akshare"
        assert len(result.data) == 2
        # 「最新价」应被识别为收盘价
        assert result.data["close"].iloc[-1] == pytest.approx(7.12)

    def test_akshare_client_side_date_filtering(self) -> None:
        """Akshare 返回全量历史，fetcher 应在客户端按请求区间过滤。"""
        fetcher = FXFetcher(
            akshare_call=lambda sym: make_akshare_df_wide(),
            yfinance_call=lambda sym, s, e: make_yfinance_df_single(),
        )
        result = fetcher.fetch("USDCNY", "2024-01-01", "2024-01-31")

        assert result.success is True
        assert result.source == "akshare"
        # 仅 2024-01-02 / 03 / 04 落在区间内
        assert len(result.data) == 3
        assert list(result.data["date"]) == ["2024-01-02", "2024-01-03", "2024-01-04"]

    def test_akshare_no_data_in_range_returns_error(self) -> None:
        """Akshare 返回的数据不在请求区间内时，应判失败并触发回退。"""
        fetcher = FXFetcher(
            akshare_call=lambda sym: make_akshare_df_wide(),
            yfinance_call=lambda sym, s, e: make_yfinance_df_single(),
        )
        # 请求一个数据中不存在的区间
        result = fetcher.fetch("USDCNY", "2025-01-01", "2025-01-31")

        # akshare 区间内无数据 -> 回退 yfinance -> 成功
        assert result.success is True
        assert result.source == "yfinance"


# ---------------------------------------------------------------------------
# 回退流程
# ---------------------------------------------------------------------------
class TestFallback:
    """yfinance 回退路径测试。"""

    def test_fallback_to_yfinance_when_akshare_raises(self) -> None:
        """Akshare 抛异常时，应自动回退到 yfinance 并成功。"""
        ak_calls: list = []
        yf_calls: list = []

        def ak_call(sym):
            ak_calls.append(sym)
            raise RuntimeError("网络超时")

        def yf_call(sym, s, e):
            yf_calls.append((sym, s, e))
            return make_yfinance_df_single()

        fetcher = FXFetcher(akshare_call=ak_call, yfinance_call=yf_call)
        result = fetcher.fetch("USDCNY", "2024-01-01", "2024-01-31")

        assert result.success is True
        assert result.source == "yfinance"
        # 两端都被调用
        assert len(ak_calls) == 1
        assert len(yf_calls) == 1
        # yfinance 收到的 ticker 应为映射后的 CNY=X
        assert yf_calls[0][0] == "CNY=X"
        assert len(result.data) == 2

    def test_fallback_to_yfinance_when_akshare_returns_empty(self) -> None:
        """Akshare 返回空数据时，也应回退到 yfinance。"""
        fetcher = FXFetcher(
            akshare_call=lambda sym: make_empty_df(),
            yfinance_call=lambda sym, s, e: make_yfinance_df_single(),
        )
        result = fetcher.fetch("EURUSD", "2024-01-01", "2024-01-31")

        assert result.success is True
        assert result.source == "yfinance"

    def test_yfinance_multiindex_columns_normalized(self) -> None:
        """yfinance 新版 MultiIndex 列结构能被正确规范化。"""
        fetcher = FXFetcher(
            akshare_call=lambda sym: make_empty_df(),
            yfinance_call=lambda sym, s, e: make_yfinance_df_multi(),
        )
        result = fetcher.fetch("USDCNY", "2024-01-01", "2024-01-31")

        assert result.success is True
        assert result.source == "yfinance"
        assert list(result.data.columns) == ["date", "close"]
        assert result.data["close"].iloc[0] == pytest.approx(7.11)


# ---------------------------------------------------------------------------
# 双失败场景
# ---------------------------------------------------------------------------
class TestBothFail:
    """双数据源均失败场景测试。"""

    def _raise(self, msg: str):
        """构造一个调用即抛异常的可调用对象（便于闭包复用）。"""
        def _inner(*args, **kwargs):
            raise RuntimeError(msg)
        return _inner

    def test_both_sources_fail_returns_error(self) -> None:
        """两个数据源都失败时，返回失败结果并包含错误信息。"""
        fetcher = FXFetcher(
            akshare_call=self._raise("ak err"),
            yfinance_call=self._raise("yf err"),
        )
        result = fetcher.fetch("USDCNY", "2024-01-01", "2024-01-31")

        assert result.success is False
        assert result.source == "yfinance"  # 最后尝试的是 yfinance
        assert result.data is None
        assert "yfinance 调用异常" in result.error

    def test_both_sources_return_empty(self) -> None:
        """两个数据源都返回空时，返回失败结果。"""
        fetcher = FXFetcher(
            akshare_call=lambda sym: make_empty_df(),
            yfinance_call=lambda sym, s, e: make_empty_df(),
        )
        result = fetcher.fetch("USDCNY", "2024-01-01", "2024-01-31")

        assert result.success is False
        assert result.data is None
        assert "空数据" in result.error


# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------
class TestValidation:
    """参数校验测试。"""

    def test_unsupported_symbol_returns_error(self) -> None:
        """未在映射表中的货币对应直接返回失败，且不调用任何数据源。"""
        ak_calls: list = []
        yf_calls: list = []
        fetcher = FXFetcher(
            akshare_call=lambda sym: (ak_calls.append(sym) or make_akshare_df()),
            yfinance_call=lambda sym, s, e: (yf_calls.append(sym)
                                             or make_yfinance_df_single()),
        )
        result = fetcher.fetch("XXXYYY", "2024-01-01", "2024-01-31")

        assert result.success is False
        assert result.source == "none"
        assert "不支持的货币对" in result.error
        assert ak_calls == []
        assert yf_calls == []

    def test_fetch_result_dataclass_fields(self) -> None:
        """FetchResult 数据类默认字段行为正确。"""
        r = FetchResult(symbol="USDCNY", source="akshare", success=True)
        assert r.data is None
        assert r.error is None
        assert r.fetch_time  # 默认时间戳非空


# ---------------------------------------------------------------------------
# 符号映射覆盖性
# ---------------------------------------------------------------------------
class TestSymbolRouting:
    """映射表所有货币对路由测试。"""

    @pytest.mark.parametrize("symbol", list(SYMBOL_MAP.keys()))
    def test_all_mapped_symbols_can_route(self, symbol: str) -> None:
        """映射表中所有货币对都能正确路由到 akshare（参数化验证）。"""
        fetcher = FXFetcher(
            akshare_call=lambda sym: make_akshare_df(),
            yfinance_call=lambda sym, s, e: make_yfinance_df_single(),
        )
        result = fetcher.fetch(symbol, "2024-01-01", "2024-01-31")
        assert result.success is True
        assert result.source == "akshare"


# ---------------------------------------------------------------------------
# 重试机制（_call_with_retry / _is_transient）
# ---------------------------------------------------------------------------
class TestRetry:
    """重试机制测试。"""

    def test_is_transient_classifies_requests_exceptions(self) -> None:
        """requests 网络异常判为瞬时，普通异常判为非瞬时。"""
        import requests

        assert fx_module._is_transient(
            requests.exceptions.ConnectionError("断开")
        ) is True
        assert fx_module._is_transient(
            requests.exceptions.Timeout("超时")
        ) is True
        # 非网络异常不重试
        assert fx_module._is_transient(KeyError("USDCNY")) is False
        assert fx_module._is_transient(ValueError("参数错")) is False

    def test_call_with_retry_succeeds_after_transient_failures(self) -> None:
        """前几次抛瞬时网络异常、最终成功时，应重试并返回结果。"""
        import requests

        expected = make_akshare_df()
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:  # 前 2 次瞬时失败
                raise requests.exceptions.ConnectionError("断开")
            return expected

        # mock time.sleep 避免真实等待
        with mock.patch("time.sleep"):
            out = fx_module._call_with_retry(flaky, "akshare", "USDCNH")

        assert out is expected
        assert calls["n"] == 3  # 失败 2 次 + 成功 1 次

    def test_call_with_retry_does_not_retry_non_transient(self) -> None:
        """非瞬时异常（如 KeyError）应立即抛出，不重试。"""
        calls = {"n": 0}

        def bad():
            calls["n"] += 1
            raise KeyError("USDCNY")  # 非网络异常

        with mock.patch("time.sleep") as sleep_mock:
            with pytest.raises(KeyError):
                fx_module._call_with_retry(bad, "akshare", "USDCNY")

        assert calls["n"] == 1  # 仅调用一次，未重试
        sleep_mock.assert_not_called()

    def test_call_with_retry_raises_after_max_retries(self) -> None:
        """持续瞬时失败超过最大重试次数后，抛出最后一次异常。"""
        import requests

        calls = {"n": 0}

        def always_fail():
            calls["n"] += 1
            raise requests.exceptions.ConnectionError("持续断开")

        with mock.patch("time.sleep"):
            with pytest.raises(requests.exceptions.ConnectionError):
                fx_module._call_with_retry(always_fail, "akshare", "USDCNH")

        # 首次 + 最大重试次数
        assert calls["n"] == _MAX_RETRIES + 1

    def test_is_ban_signal_detects_remote_disconnected(self) -> None:
        """RemoteDisconnected 应被识别为封禁信号（不重试）。"""
        import requests

        exc = requests.exceptions.ConnectionError(
            "('Connection aborted.', RemoteDisconnected('Remote end closed "
            "connection without response'))"
        )
        assert fx_module._is_ban_signal(exc) is True

    def test_is_ban_signal_detects_403(self) -> None:
        """HTTP 403 应被识别为封禁信号。"""
        import requests

        resp = mock.Mock()
        resp.status_code = 403
        exc = requests.exceptions.HTTPError("403 Forbidden", response=resp)
        assert fx_module._is_ban_signal(exc) is True

    def test_is_ban_signal_false_for_plain_connection_error(self) -> None:
        """普通连接错误（非封禁）不应误判。"""
        import requests

        exc = requests.exceptions.ConnectionError("Connection refused")
        assert fx_module._is_ban_signal(exc) is False

    def test_call_with_retry_skips_retry_on_ban_signal(self) -> None:
        """收到封禁信号时立即抛出，不做任何重试（避免延长封禁）。"""
        import requests

        exc = requests.exceptions.ConnectionError(
            "('Connection aborted.', RemoteDisconnected('Remote end closed "
            "connection without response'))"
        )
        calls = {"n": 0}

        def banned():
            calls["n"] += 1
            raise exc

        with mock.patch("time.sleep") as sleep_mock:
            with pytest.raises(requests.exceptions.ConnectionError):
                fx_module._call_with_retry(banned, "akshare", "USDCNH")

        assert calls["n"] == 1  # 仅调用一次，未重试
        sleep_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 轻量小请求 _eastmoney_hist_small（mock requests.get）
# ---------------------------------------------------------------------------
class TestEastmoneySmallRequest:
    """直连东方财富极小请求测试。"""

    def _fake_eastmoney_response(self):
        """构造模拟的东方财富响应对象（仅日期+收盘价 2 字段 kline）。"""
        klines = ["2024-01-02,7.11", "2024-01-03,7.12"]
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "data": {"code": "USDCNH", "name": "美元兑离岸人民币", "klines": klines}
        }
        return resp

    def test_eastmoney_hist_small_parses_klines(self) -> None:
        """小请求能正确解析东方财富返回的 klines 为两列 DataFrame。"""
        with mock.patch("requests.get", return_value=self._fake_eastmoney_response()):
            df = fx_module._eastmoney_hist_small("USDCNH", lmt=10)

        assert list(df.columns) == ["日期", "最新价"]
        assert len(df) == 2
        assert df["日期"].iloc[0] == "2024-01-02"
        assert df["最新价"].iloc[0] == "7.11"

    def test_eastmoney_hist_small_empty_klines_returns_empty_df(self) -> None:
        """klines 为空时返回空 DataFrame（由上层判失败并触发回退）。"""
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"data": {"code": "USDCNH", "name": "x", "klines": []}}
        with mock.patch("requests.get", return_value=resp):
            df = fx_module._eastmoney_hist_small("USDCNH")
        assert df.empty

    def test_eastmoney_hist_small_requests_minimal_fields(self) -> None:
        """小请求应只请求日期+收盘价两字段、并以小 lmt 传入（最小化请求体）。"""
        captured: dict = {}

        def fake_get(url, params=None, timeout=None):
            captured["params"] = params
            return self._fake_eastmoney_response()

        with mock.patch("requests.get", side_effect=fake_get):
            fx_module._eastmoney_hist_small("USDCNH", lmt=10)

        assert captured["params"]["lmt"] == "10"
        assert captured["params"]["fields2"] == "f51,f53"  # 仅日期+收盘价
        assert captured["params"]["secid"] == "133.USDCNH"


# ---------------------------------------------------------------------------
# 限流器 _RateLimiter
# ---------------------------------------------------------------------------
class TestRateLimiter:
    """限流器测试。"""

    def test_rate_limiter_sleeps_when_called_too_quickly(self) -> None:
        """连续两次调用间隔不足时，应阻塞补足最小间隔。"""
        rl = fx_module._RateLimiter(min_interval=2.0)
        sleep_calls: list = []
        fake_time = [1000.0]

        with mock.patch("time.time", side_effect=lambda: fake_time[0]), \
             mock.patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            rl.wait()           # 首次：无需等待
            fake_time[0] = 1001.0  # 仅过 1s < 2s
            rl.wait()           # 应等待 1s 补足

        # 第二次等待了 (2.0 - 1.0) = 1.0 秒
        assert sleep_calls and abs(sleep_calls[-1] - 1.0) < 1e-6

    def test_rate_limiter_no_sleep_when_enough_time_elapsed(self) -> None:
        """距上次调用已超过最小间隔时，不应阻塞。"""
        rl = fx_module._RateLimiter(min_interval=1.0)
        sleep_calls: list = []
        fake_time = [1000.0]

        with mock.patch("time.time", side_effect=lambda: fake_time[0]), \
             mock.patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            rl.wait()
            fake_time[0] = 1005.0  # 已过 5s >> 1s
            rl.wait()

        assert sleep_calls == []  # 第二次无需等待


# ---------------------------------------------------------------------------
# 记录数限制
# ---------------------------------------------------------------------------
class TestRecordLimits:
    """记录数严格限制测试。"""

    def test_helper_default_is_10(self) -> None:
        """单次获取默认返回 10 条。"""
        assert MAX_RECORDS_PER_CALL == 10

    def test_hard_limit_default_50(self) -> None:
        """默认硬上限为 50（.env 未配或非法时使用）。"""
        assert MAX_RECORDS_HARD_LIMIT >= 10
        # 与默认值一致（测试环境未显式修改 env 时为 50）
        assert MAX_RECORDS_HARD_LIMIT == fx_module._FX_DEFAULT_HARD_LIMIT

    def test_validate_max_records_default(self) -> None:
        """默认值规范化。"""
        assert _validate_max_records(None) == MAX_RECORDS_PER_CALL

    def test_validate_max_records_ok(self) -> None:
        """合法值原样返回。"""
        assert _validate_max_records(20) == 20

    def test_validate_max_records_too_large_clamps(self) -> None:
        """超过硬上限时自动裁剪到硬上限，并记录 WARNING（不抛错）。"""
        too_large = MAX_RECORDS_HARD_LIMIT + 10
        clamped = _validate_max_records(too_large)
        assert clamped == MAX_RECORDS_HARD_LIMIT

    def test_validate_max_records_too_large_warns(self, caplog) -> None:
        """超过硬上限时输出 WARNING 日志，包含提示信息。"""
        import logging
        with caplog.at_level(logging.WARNING, logger="tools.common.fx_rate"):
            clamped = _validate_max_records(MAX_RECORDS_HARD_LIMIT + 99)
        assert clamped == MAX_RECORDS_HARD_LIMIT
        # 日志包含裁剪与配置提示
        text = caplog.text
        assert "超过硬上限" in text or "FX_MAX_RECORDS_HARD_LIMIT" in text

    def test_validate_max_records_non_int(self) -> None:
        """非整数抛出异常。"""
        with pytest.raises(ValueError, match="整数"):
            _validate_max_records("10")

    def test_validate_max_records_bool(self) -> None:
        """布尔值视为非法。"""
        with pytest.raises(ValueError):
            _validate_max_records(True)

    def test_validate_max_records_zero(self) -> None:
        """小于 1 抛出异常。"""
        with pytest.raises(ValueError, match=">= 1"):
            _validate_max_records(0)

    # ------------------------------------------------------------------
    # 环境变量配置解析
    # ------------------------------------------------------------------
    def test_parse_int_env_missing_uses_default(self) -> None:
        """环境变量未设置时返回默认值。"""
        with mock.patch.dict("os.environ", {}, clear=True):
            assert _parse_int_env("FX_MISSING_VAR", 50) == 50

    def test_parse_int_env_empty_uses_default(self) -> None:
        """空串/空白串使用默认值。"""
        for empty in ["", "   "]:
            with mock.patch.dict("os.environ", {"X": empty}, clear=True):
                assert _parse_int_env("X", 50) == 50

    def test_parse_int_env_valid(self) -> None:
        """合法整数正常解析。"""
        with mock.patch.dict("os.environ", {"X": "30"}, clear=True):
            assert _parse_int_env("X", 50) == 30

    def test_parse_int_env_invalid_warns_and_defaults(self, caplog) -> None:
        """非法值 WARNING 并使用默认值（不崩溃）。"""
        import logging
        with caplog.at_level(logging.WARNING, logger="tools.common.fx_rate"):
            with mock.patch.dict("os.environ", {"X": "abc"}, clear=True):
                assert _parse_int_env("X", 50) == 50
        assert "X" in caplog.text
        with mock.patch.dict("os.environ", {"X": "50.5"}, clear=True):
            assert _parse_int_env("X", 50) == 50

    @mock.patch("tools.common.fx_rate.MAX_RECORDS_HARD_LIMIT", 30)
    def test_validate_respects_dynamic_hard_limit(self) -> None:
        """硬上限由配置决定：当前模拟配置为 30 时，100 裁剪为 30。"""
        from tools.common.fx_rate import _validate_max_records as _v2
        # 通过临时替换模块常量来模拟不同配置值
        with mock.patch.object(fx_module, "MAX_RECORDS_HARD_LIMIT", 30):
            assert fx_module._validate_max_records(100) == 30
            assert fx_module._validate_max_records(25) == 25
            assert fx_module._validate_max_records(31) == 30

    def test_enforce_max_records_truncates_tail(self) -> None:
        """超过上限时保留末尾最新记录。"""
        df = pd.DataFrame({"date": [f"2024-01-{i:02d}" for i in range(1, 21)],
                           "close": [float(i) for i in range(1, 21)]})
        out = _enforce_max_records(df, 10)
        assert len(out) == 10
        assert out["date"].iloc[0] == "2024-01-11"

    def test_enforce_max_records_below_limit_unchanged(self) -> None:
        """未超过上限时原样返回。"""
        df = make_akshare_df()
        out = _enforce_max_records(df, 10)
        assert len(out) == 3

    def test_enforce_max_records_empty(self) -> None:
        """空 DataFrame 原样返回。"""
        out = _enforce_max_records(make_empty_df(), 10)
        assert out.empty

    @mock.patch("tools.common.fx_rate.FXFetcher")
    def test_fetch_rate_truncates_to_max_records(self, mock_fetcher_cls) -> None:
        """fetch_rate 将结果裁剪至 max_records 条。"""
        wide = pd.DataFrame({"date": [f"2024-01-{i:02d}" for i in range(1, 21)],
                             "close": [float(i) for i in range(1, 21)]})
        mock_fetcher_cls.return_value.fetch.return_value = FetchResult(
            symbol="USDCNY", source="akshare", success=True, data=wide
        )
        result = fetch_rate("USDCNY", "2024-01-01", "2024-01-31", max_records=5)
        assert result.success is True
        assert len(result.data) == 5

    @mock.patch("tools.common.fx_rate.FXFetcher")
    def test_fetch_rate_clamps_over_limit(self, mock_fetcher_cls) -> None:
        """fetch_rate 对超过硬上限的 max_records 自动裁剪到上限（不抛错、仍调用）。"""
        mock_fetcher_cls.return_value.fetch.return_value = FetchResult(
            symbol="USDCNY", source="akshare", success=True, data=make_akshare_df()
        )
        # 请求 100 条，实际裁剪为 MAX_RECORDS_HARD_LIMIT 且正常返回
        result = fetch_rate("USDCNY", max_records=100)
        assert result.success is True
        # 请求必须被调用
        mock_fetcher_cls.return_value.fetch.assert_called_once()


# ---------------------------------------------------------------------------
# 批量获取限流保护
# ---------------------------------------------------------------------------
class TestBatchFetch:
    """批量获取测试。"""

    def test_batch_size_limit_is_5(self) -> None:
        """批量上限为 5。"""
        assert MAX_BATCH_SIZE == 5

    def test_fetch_many_exceeds_limit_raises(self) -> None:
        """超过 5 个货币对抛出异常。"""
        with pytest.raises(ValueError, match="最多支持 5 个货币对"):
            fetch_many(["USDCNY", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"])

    @mock.patch("tools.common.fx_rate.FXFetcher")
    def test_fetch_many_success(self, mock_fetcher_cls) -> None:
        """批量获取成功，顺序与输入一致。"""
        mock_fetcher_cls.return_value.fetch.return_value = FetchResult(
            symbol="USDCNY", source="akshare", success=True, data=make_akshare_df()
        )
        results = fetch_many(["USDCNY", "EURUSD"], batch_interval=0)
        assert len(results) == 2
        assert all(r.source == "akshare" for r in results)

    @mock.patch("tools.common.fx_rate.FXFetcher")
    def test_fetch_many_respects_interval(self, mock_fetcher_cls) -> None:
        """批量获取时货币对之间应等待 batch_interval 秒。"""
        mock_fetcher_cls.return_value.fetch.return_value = FetchResult(
            symbol="USDCNY", source="akshare", success=True, data=make_akshare_df()
        )
        with mock.patch("time.sleep") as sleep_mock:
            fetch_many(["USDCNY", "EURUSD", "GBPUSD"], batch_interval=1.5)
        # 3 个货币对 -> 2 次间隔
        assert sleep_mock.call_count == 2
        for call in sleep_mock.call_args_list:
            assert call == mock.call(1.5)

    @mock.patch("tools.common.fx_rate.FXFetcher")
    def test_fetch_many_partial_failure(self, mock_fetcher_cls) -> None:
        """批量获取部分失败时，失败项保留错误信息。"""
        def side_effect(symbol, start, end):
            if symbol == "USDCNY":
                return FetchResult(symbol="USDCNY", source="akshare",
                                   success=True, data=make_akshare_df())
            return FetchResult(symbol=symbol, source="none", success=False,
                               error="不支持的货币对符号: XXX")

        mock_fetcher_cls.return_value.fetch.side_effect = side_effect
        results = fetch_many(["USDCNY", "XXX"], batch_interval=0)
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert "不支持的货币对" in results[1].error


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------
class TestCLI:
    """CLI 入口测试。"""

    def test_cmd_list(self) -> None:
        """--list 命令。"""
        output = cmd_list()
        assert output["success"] is True
        assert output["meta"]["total_count"] == len(SYMBOL_MAP)
        assert len(output["data"]) == len(SYMBOL_MAP)

    def test_cmd_fetch_single(self) -> None:
        """--code 单货币对命令。"""
        with mock.patch("tools.common.fx_rate.fetch_rate") as mock_fetch:
            mock_fetch.return_value = FetchResult(
                symbol="USDCNY", source="akshare", success=True,
                data=make_akshare_df(),
            )
            output = cmd_fetch("USDCNY")
        assert output["success"] is True
        assert output["data"]["symbol"] == "USDCNY"
        assert output["data"]["source"] == "akshare"
        assert output["data"]["record_count"] == 3

    def test_cmd_fetch_batch(self) -> None:
        """--code 多货币对命令。"""
        # 注：_result_to_dict 需要规范化后的 [date, close] 两列数据
        norm_df = pd.DataFrame({"date": ["2024-01-02", "2024-01-03"],
                                "close": [7.11, 7.12]})
        with mock.patch("tools.common.fx_rate.fetch_many") as mock_fetch_many:
            mock_fetch_many.return_value = [
                FetchResult(symbol="USDCNY", source="akshare", success=True,
                            data=norm_df),
                FetchResult(symbol="EURUSD", source="yfinance", success=True,
                            data=norm_df),
            ]
            output = cmd_fetch("USDCNY,EURUSD")
        assert output["success"] is True
        assert output["data"]["batch"] is True
        assert len(output["data"]["results"]) == 2

    def test_cmd_fetch_empty_code(self) -> None:
        """--code 空值。"""
        output = cmd_fetch("")
        assert output["success"] is False
        assert "请提供货币对代码" in output["error"]

    def test_cmd_fetch_lowercase_upper(self) -> None:
        """--code 小写输入应转换为大写。"""
        with mock.patch("tools.common.fx_rate.fetch_rate") as mock_fetch:
            mock_fetch.return_value = FetchResult(
                symbol="USDCNY", source="akshare", success=True,
                data=make_akshare_df(),
            )
            output = cmd_fetch("usdcny")
        assert output["data"]["symbol"] == "USDCNY"

    @mock.patch("tools.common.fx_rate.FXFetcher")
    def test_cmd_fetch_over_limit_clamps_succeeds(self, mock_fetcher_cls) -> None:
        """--max-records 超过硬上限时自动裁剪到上限（返回成功，而非错误）。"""
        mock_fetcher_cls.return_value.fetch.return_value = FetchResult(
            symbol="USDCNY", source="akshare", success=True,
            data=make_akshare_df(),
        )
        output = cmd_fetch("USDCNY", max_records=100)
        # 输出成功（不崩溃、不报错）
        assert output["success"] is True
        # meta 中的 max_records 反映实际使用值（已裁剪）
        effective = output["meta"]["limit"]["max_records"]
        assert effective == MAX_RECORDS_HARD_LIMIT


# ---------------------------------------------------------------------------
# 运行测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pytest.main([__file__, "-v"])