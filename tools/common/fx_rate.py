#!/usr/bin/env python3
"""国际主要货币汇率数据获取工具。

以 Akshare 为主数据源、yfinance 为备选数据源，获取国际主要货币对的市场
浮动汇率（盘面 K 线）。为避免触发数据源服务端限流，本工具严格限制获取
记录数，并实现获取操作的自动回退措施：

限流保护设计：
    - 单次获取默认最多返回 10 条记录（MAX_RECORDS_PER_CALL）
    - 硬上限通过 .env 的 FX_MAX_RECORDS_HARD_LIMIT 配置（默认 50），超出自动裁剪并 WARNING
    - Akshare 主路径采用「直连东方财富极小请求」，仅取日期+收盘价两字段、
      最近 10 个交易日，代替 akshare 原生 lmt=50000 的批量大请求
    - 任意两次 API 调用间隔至少 0.5 秒（_MIN_INTERVAL，模块级限流器）
    - 批量获取最多 5 个货币对（MAX_BATCH_SIZE），货币对间间隔至少 1 秒
    - 瞬时网络异常采用指数退避重试（默认 3 次，1/2/4 秒）

数据源策略：
    - Akshare 优先：直连东方财富极小请求，失败（异常/空/区间无数据）时
      自动回退至 yfinance
    - yfinance 兜底：Akshare 全失败时使用，同样受限流与重试保护

Usage:
    {py} tools/common/fx_rate.py --code USDCNY              # 获取最近 10 条
    {py} tools/common/fx_rate.py --code USDCNY,EURUSD       # 批量获取（最多 5 个）
    {py} tools/common/fx_rate.py --list                     # 列出所有支持货币对
    {py} tools/common/fx_rate.py --code USDCNY --start 2026-07-20 --end 2026-08-01
    {py} tools/common/fx_rate.py --code USDCNY --max-records 20
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失时降级为不读取 .env
    load_dotenv = None  # type: ignore[assignment]

try:
    import requests
except ImportError:  # pragma: no cover - requests 是 akshare/yfinance 传递依赖
    requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# 加载环境变量（从项目根目录的 .env 文件）
# 本文件位于 tools/common/ 下，需向上 3 层到达项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _parse_int_env(var_name: str, default: int) -> int:
    """从环境变量读取整数配置，非法值或缺失时回退到默认值。

    遵循「配置失败不影响功能」原则：遇到空串、非数字等一律记录 WARNING
    并使用 default，避免 .env 笔误导致工具无法运行。

    Args:
        var_name: 环境变量名。
        default: 默认值（解析失败时使用）。

    Returns:
        解析后的整数。
    """
    raw = os.getenv(var_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        logger.warning(
            "[env] %s 配置值 %r 非法，使用默认值 %d", var_name, raw, default,
        )
        return default


# ---------------------------------------------------------------------------
# 限流与重试配置（避免高频 / 大请求触发服务端限流）
# ---------------------------------------------------------------------------
# 最小调用间隔（秒）：任意两次 API 调用之间至少间隔 _MIN_INTERVAL 秒
_MIN_INTERVAL = 0.5
# 最大重试次数（不含首次调用）
_MAX_RETRIES = 3
# 指数退避基数（秒）：第 k 次重试等待 _BACKOFF_BASE * 2**k
_BACKOFF_BASE = 1.0
# 小请求拉取条数：Akshare 主路径每次只取最近 10 个交易日数据
_SMALL_LMT = 10
# 单次获取默认最大返回记录数
MAX_RECORDS_PER_CALL = 10
# 单次获取硬上限（可通过 .env 的 FX_MAX_RECORDS_HARD_LIMIT 配置，默认 50），
# 超出时 WARNING 并裁剪到该值，避免触发数据源限流。
_FX_DEFAULT_HARD_LIMIT = 50
MAX_RECORDS_HARD_LIMIT: int = _parse_int_env(
    "FX_MAX_RECORDS_HARD_LIMIT", _FX_DEFAULT_HARD_LIMIT,
)
# 批量获取最大货币对数量
MAX_BATCH_SIZE = 5
# 批量获取时货币对之间的最小间隔（秒）
BATCH_CALL_INTERVAL = 1.0


# ---------------------------------------------------------------------------
# 货币对代码映射表：统一符号 -> 各数据源对应代码
# ---------------------------------------------------------------------------
# - akshare: 东方财富 forex_hist_em 接口的 symbol 参数
# - yfinance: Yahoo Finance 行情代码
#
# 注意：东方财富代码表不提供在岸 USDCNY，故以离岸 USDCNH 作为市场汇率代理。
SYMBOL_MAP: Dict[str, Dict[str, str]] = {
    # ===== 美元兑主要货币 =====
    # 美元/人民币：akshare 用离岸 USDCNH 代理（在岸 USDCNY 不在东财外汇市场代码表）
    "USDCNY": {"akshare": "USDCNH", "yfinance": "CNY=X"},
    "USDCNH": {"akshare": "USDCNH", "yfinance": "CNH=X"},      # 美元/离岸人民币
    "EURUSD": {"akshare": "EURUSD", "yfinance": "EURUSD=X"},   # 欧元/美元
    "GBPUSD": {"akshare": "GBPUSD", "yfinance": "GBPUSD=X"},   # 英镑/美元
    "USDJPY": {"akshare": "USDJPY", "yfinance": "JPY=X"},      # 美元/日元
    "AUDUSD": {"akshare": "AUDUSD", "yfinance": "AUDUSD=X"},   # 澳元/美元
    "USDCAD": {"akshare": "USDCAD", "yfinance": "CAD=X"},      # 美元/加元
    "USDCHF": {"akshare": "USDCHF", "yfinance": "CHF=X"},      # 美元/瑞郎
    "USDHKD": {"akshare": "USDHKD", "yfinance": "HKD=X"},      # 美元/港币

    # ===== 人民币兑主要货币（1 外币 = x 人民币；akshare 以离岸 CNH 代理市场浮动汇率） =====
    "EURCNY": {"akshare": "EURCNH", "yfinance": "EURCNY=X"},   # 欧元/人民币
    "GBPCNY": {"akshare": "GBPCNH", "yfinance": "GBPCNY=X"},   # 英镑/人民币
    "JPYCNY": {"akshare": "JPYCNH", "yfinance": "JPYCNY=X"},   # 日元/人民币
    "AUDCNY": {"akshare": "AUDCNH", "yfinance": "AUDCNY=X"},   # 澳元/人民币
    "CADCNY": {"akshare": "CADCNH", "yfinance": "CADCNY=X"},   # 加元/人民币
    "CHFCNY": {"akshare": "CHFCNH", "yfinance": "CHFCNY=X"},   # 瑞郎/人民币
    "NZDCNY": {"akshare": "NZDCNH", "yfinance": "NZDCNY=X"},   # 纽元/人民币
    "SGDCNY": {"akshare": "SGDCNH", "yfinance": "SGDCNY=X"},   # 新加坡元/人民币

    # ===== 人民币与港币（双向） =====
    "CNYHKD": {"akshare": "CNHHKD", "yfinance": "CNYHKD=X"},   # 人民币/港币（1 人民币 = x 港币）
    "HKDCNY": {"akshare": "HKDCNH", "yfinance": "HKDCNY=X"},   # 港币/人民币（1 港币 = x 人民币）
}


class _RateLimiter:
    """简单的全局最小间隔限流器，避免高频调用触发服务端限流。

    模块级单例 ``_RATE_LIMITER`` 在每次 API 调用前 ``wait()``，
    确保任意两次调用间隔不小于 ``min_interval``。
    """

    def __init__(self, min_interval: float = _MIN_INTERVAL) -> None:
        """初始化限流器。

        Args:
            min_interval: 最小调用间隔（秒）。
        """
        self.min_interval: float = min_interval
        self._last: float = 0.0

    def wait(self) -> None:
        """阻塞至满足最小间隔要求。"""
        elapsed = time.time() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.time()


# 模块级限流器单例
_RATE_LIMITER = _RateLimiter()


def _is_transient(exc: BaseException) -> bool:
    """判断异常是否为可重试的瞬时网络异常。

    仅对 ``requests`` 网络类异常（连接中断、超时、代理错误、5xx 等）重试；
    非网络异常（如无效代码的 KeyError、参数错误）不重试，直接抛出由兜底处理。

    Args:
        exc: 捕获到的异常。

    Returns:
        True 表示可重试的瞬时网络异常。
    """
    if requests is None:
        return False
    # ConnectionError / Timeout / HTTPError / ProxyError 均为 RequestException 子类
    return isinstance(exc, requests.exceptions.RequestException)


def _is_ban_signal(exc: BaseException) -> bool:
    """判断异常是否为服务端封禁（限流拉黑）信号。

    东方财富对高频调用会临时封禁 IP，典型表现为 ``RemoteDisconnected``
    （连接被服务端直接断开）。封禁期间重试毫无意义且会延长封禁时长，
    因此识别到该信号时立即放弃重试、直接回退下一数据源。

    Args:
        exc: 捕获到的异常。

    Returns:
        True 表示疑似服务端封禁信号。
    """
    if requests is None:
        return False
    # RemoteDisconnected 是 ConnectionError 子类，需在通用网络异常判定前识别
    if isinstance(exc, requests.exceptions.ConnectionError):
        # 优先按具体异常类判断（type(exc).__name__ 仅返回 "ConnectionError"，无法识别子类）
        try:
            from http.client import RemoteDisconnected
        except ImportError:  # pragma: no cover - 标准库模块，理论上不会缺失
            RemoteDisconnected = None  # type: ignore[assignment, misc]
        if RemoteDisconnected is not None and isinstance(exc, RemoteDisconnected):
            return True
        # 回退：异常消息文本匹配（覆盖被 requests 包装但保留原文的场景）
        if "Remote end closed connection" in str(exc):
            return True
    # HTTP 403 通常也表示服务端拒绝（限流/风控）
    if isinstance(exc, requests.exceptions.HTTPError):
        if getattr(exc.response, "status_code", None) == 403:
            return True
    return False


def _call_with_retry(
    func: Callable[[], pd.DataFrame], source: str, key: str
) -> pd.DataFrame:
    """对数据源调用执行指数退避重试。

    瞬时网络异常（连接中断、超时等）自动重试；**服务端封禁信号
    （如东方财富 RemoteDisconnected）立即放弃重试**，因为封禁期间
    重试会延长封禁；非瞬时异常立即抛出。

    Args:
        func: 无参可调用对象，返回 DataFrame。
        source: 数据源名称（仅用于日志），如 "akshare"。
        key: 调用标识（仅用于日志），如货币对代码或 ticker。

    Returns:
        数据源返回的 DataFrame。

    Raises:
        非瞬时异常立即抛出；瞬时异常超过最大重试次数后抛出最后一次异常。
    """
    last_exc: Optional[BaseException] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001  需区分瞬时/非瞬时以决定是否重试
            last_exc = exc
            # 非瞬时异常 / 服务端封禁信号 / 已达最大重试次数：直接抛出（由上层兜底处理）
            if (not _is_transient(exc)
                    or _is_ban_signal(exc)
                    or attempt == _MAX_RETRIES):
                if _is_ban_signal(exc):
                    logger.warning(
                        "[%s] %s 疑似被服务端封禁（%s），放弃重试立即回退",
                        key, source, exc,
                    )
                raise
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "[%s] %s 第 %d/%d 次失败：%s，%.1fs 后重试",
                key, source, attempt + 1, _MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
    # 理论上不会到达
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# 轻量直连东方财富小请求（替代 akshare 默认 lmt=50000 的批量大请求）
# ---------------------------------------------------------------------------
def _eastmoney_secid(ak_symbol: str) -> Optional[str]:
    """获取东方财富 secid（``market_code.symbol``）。

    复用 akshare 内部的 ``symbol_market_map`` 做代码映射，
    避免自行维护易失效的市场代码表。

    Args:
        ak_symbol: Akshare 外汇代码，例如 "USDCNH"。

    Returns:
        形如 "133.USDCNH" 的 secid；无法确定时返回 None。
    """
    try:
        from akshare.forex.forex_em import symbol_market_map
    except Exception:  # noqa: BLE001  akshare 缺失或内部结构变更
        return None
    market_code = symbol_market_map.get(ak_symbol)
    if not market_code:
        return None
    return f"{market_code}.{ak_symbol}"


def _eastmoney_hist_small(ak_symbol: str, lmt: int = _SMALL_LMT) -> pd.DataFrame:
    """轻量直连东方财富外汇历史接口（极小请求，避免限流）。

    只请求日期(f51)与收盘价(f53)两个字段、最近 ``lmt`` 个交易日，请求与响应
    体极小，最大程度降低被限流概率；返回仅含 ``日期``/``最新价`` 两列的
    DataFrame，由 ``_normalize_akshare_df`` 统一规范化。无法确定 secid 时
    退回 akshare 原生接口。

    Args:
        ak_symbol: Akshare 外汇代码，例如 "USDCNH"。
        lmt: 拉取的日线条数（最近 ``lmt`` 个交易日）。

    Returns:
        含 ``日期``/``最新价`` 两列的 DataFrame；无数据时返回空 DataFrame。

    Raises:
        requests 网络异常 / KeyError 等：由上层 ``_call_with_retry`` 与兜底处理。
    """
    if requests is None:
        raise RuntimeError("requests 未安装，无法直连东方财富接口")

    secid = _eastmoney_secid(ak_symbol)
    if secid is None:
        # 无法确定 secid，退回 akshare 原生（bulk）接口
        import akshare as ak
        return ak.forex_hist_em(symbol=ak_symbol)

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "klt": "101",
        "fqt": "1",
        "lmt": str(lmt),
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1",
        "fields2": "f51,f53",  # 仅日期 + 收盘价（最新价）
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": 1,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    klines = (data.get("data") or {}).get("klines") or []
    if not klines:
        return pd.DataFrame()

    # 每条 kline 格式："日期,收盘价"
    rows = [item.split(",") for item in klines]
    return pd.DataFrame(rows, columns=["日期", "最新价"])


# ---------------------------------------------------------------------------
# 默认数据源调用实现（延迟导入 + 限流 + 重试）
# ---------------------------------------------------------------------------
def _default_akshare_call(ak_symbol: str) -> pd.DataFrame:
    """Akshare 主数据源默认调用实现（小请求 + 限流 + 重试）。

    采用轻量直连东方财富的小请求（``lmt=_SMALL_LMT``）替代 akshare 原生
    ``lmt=50000`` 的批量大请求，以降低被限流概率；调用前经 ``_RATE_LIMITER``
    限流，瞬时网络异常由 ``_call_with_retry`` 指数退避重试。日期区间过滤由
    调用方在客户端完成。

    Args:
        ak_symbol: Akshare 外汇代码，例如 "USDCNH"。

    Returns:
        原始 DataFrame（最近 ``_SMALL_LMT`` 条日线）。
    """
    _RATE_LIMITER.wait()
    return _call_with_retry(
        lambda: _eastmoney_hist_small(ak_symbol), "akshare", ak_symbol
    )


def _default_yfinance_call(
    yf_ticker: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """yfinance 默认调用实现（兜底数据源，限流 + 重试）。

    Args:
        yf_ticker: yfinance 行情代码，例如 "CNY=X"。
        start_date: 起始日期 "YYYY-MM-DD"。
        end_date: 结束日期 "YYYY-MM-DD"。

    Returns:
        yfinance 返回的原始 DataFrame。
    """
    _RATE_LIMITER.wait()
    import yfinance as yf  # 延迟导入

    return _call_with_retry(
        lambda: yf.download(
            yf_ticker, start=start_date, end=end_date,
            progress=False, auto_adjust=False,
        ),
        "yfinance",
        yf_ticker,
    )


@dataclass
class FetchResult:
    """汇率获取结果（统一数据结构）。

    Attributes:
        symbol: 统一货币对符号，例如 "USDCNY"。
        source: 实际命中的数据源，"akshare" / "yfinance" / "none"。
        success: 是否成功获取数据。
        data: 统一格式后的 DataFrame，包含 ["date", "close"] 两列；
            失败时为 None。
        error: 失败时的错误信息；成功时为 None。
        fetch_time: 获取时间戳字符串。
    """

    symbol: str
    source: str
    success: bool
    data: Optional[pd.DataFrame] = None
    error: Optional[str] = None
    fetch_time: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


class FXFetcher:
    """汇率数据获取器：Akshare 优先，失败回退 yfinance。

    该类封装多数据源获取逻辑，对调用方屏蔽底层差异。
    如需新增数据源，可在 ``_fetch_xxx`` 系列方法中扩展。
    """

    def __init__(
        self,
        symbol_map: Optional[Dict[str, Dict[str, str]]] = None,
        akshare_call: Optional[Callable[[str], pd.DataFrame]] = None,
        yfinance_call: Optional[Callable[[str, str, str], pd.DataFrame]] = None,
    ) -> None:
        """初始化获取器。

        Args:
            symbol_map: 货币对代码映射表；为 None 时使用默认 ``SYMBOL_MAP``。
            akshare_call: Akshare 调用函数，签名 ``(ak_symbol) -> DataFrame``，
                返回该品种全部历史日线（便于测试注入 mock）；
                为 None 时使用默认延迟导入实现。
            yfinance_call: yfinance 调用函数，签名
                ``(yf_ticker, start_date, end_date) -> DataFrame``（便于测试注入 mock）；
                为 None 时使用默认延迟导入实现。
        """
        self.symbol_map: Dict[str, Dict[str, str]] = (
            symbol_map if symbol_map is not None else SYMBOL_MAP
        )
        # 依赖注入：数据源调用函数，默认为延迟导入实现
        self._akshare_call: Callable[[str], pd.DataFrame] = (
            akshare_call if akshare_call is not None else _default_akshare_call
        )
        self._yfinance_call: Callable[[str, str, str], pd.DataFrame] = (
            yfinance_call if yfinance_call is not None else _default_yfinance_call
        )

    # ------------------------------------------------------------------
    # 对外主入口
    # ------------------------------------------------------------------
    def fetch(self, symbol: str, start_date: str, end_date: str) -> FetchResult:
        """获取指定货币对在 [start_date, end_date] 区间的历史汇率。

        Args:
            symbol: 统一货币对符号，例如 "USDCNY"。
            start_date: 起始日期，格式 "YYYY-MM-DD"。
            end_date: 结束日期，格式 "YYYY-MM-DD"。

        Returns:
            ``FetchResult`` 对象，包含数据或错误信息。
        """
        # 1. 校验货币对是否在映射表中
        if symbol not in self.symbol_map:
            return FetchResult(
                symbol=symbol,
                source="none",
                success=False,
                error=f"不支持的货币对符号: {symbol}，请在 SYMBOL_MAP 中添加",
            )

        sources = self.symbol_map[symbol]
        ak_symbol = sources.get("akshare", symbol)
        yf_ticker = sources.get("yfinance", symbol)

        # 2. 优先使用 Akshare
        result = self._fetch_with_akshare(symbol, ak_symbol, start_date, end_date)
        if result.success:
            logger.info("[%s] Akshare 获取成功，共 %d 条记录", symbol, len(result.data))
            return result

        logger.warning(
            "[%s] Akshare 获取失败: %s，尝试 yfinance 回退", symbol, result.error
        )

        # 3. Akshare 失败，回退 yfinance
        result = self._fetch_with_yfinance(symbol, yf_ticker, start_date, end_date)
        if result.success:
            logger.info(
                "[%s] yfinance 回退获取成功，共 %d 条记录", symbol, len(result.data)
            )
            return result

        logger.error("[%s] yfinance 回退也失败: %s", symbol, result.error)
        return result

    # ------------------------------------------------------------------
    # 各数据源获取实现
    # ------------------------------------------------------------------
    def _fetch_with_akshare(
        self, symbol: str, ak_symbol: str, start_date: str, end_date: str
    ) -> FetchResult:
        """通过 Akshare 获取外汇历史K线。

        新版 ``forex_hist_em`` 仅按 symbol 返回全部历史，日期区间过滤在此处
        （客户端）按规范化后的 ``date`` 列完成。

        Args:
            symbol: 统一货币对符号（用于结果标识）。
            ak_symbol: Akshare 对应的外汇代码。
            start_date: 起始日期 "YYYY-MM-DD"。
            end_date: 结束日期 "YYYY-MM-DD"。

        Returns:
            ``FetchResult`` 对象。
        """
        try:
            df = self._akshare_call(ak_symbol)
        except Exception as exc:  # noqa: BLE001  接口失败需捕获所有异常以触发回退
            return FetchResult(
                symbol, "akshare", False, error=f"akshare 调用异常: {exc}"
            )

        if df is None or len(df) == 0:
            return FetchResult(
                symbol, "akshare", False, error="akshare 返回空数据"
            )

        try:
            df = self._normalize_akshare_df(df)
        except Exception as exc:  # noqa: BLE001
            return FetchResult(
                symbol, "akshare", False, error=f"akshare 数据解析异常: {exc}"
            )

        # 客户端按日期区间过滤（ISO 日期可直接字符串比较）
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        df = df.loc[mask].reset_index(drop=True)

        if df.empty:
            return FetchResult(
                symbol,
                "akshare",
                False,
                error=f"akshare 在区间 [{start_date}, {end_date}] 内无数据",
            )

        return FetchResult(symbol, "akshare", True, data=df)

    def _fetch_with_yfinance(
        self, symbol: str, yf_ticker: str, start_date: str, end_date: str
    ) -> FetchResult:
        """通过 yfinance 获取外汇历史K线（兜底数据源）。

        Args:
            symbol: 统一货币对符号（用于结果标识）。
            yf_ticker: yfinance 对应的行情代码。
            start_date: 起始日期 "YYYY-MM-DD"。
            end_date: 结束日期 "YYYY-MM-DD"。

        Returns:
            ``FetchResult`` 对象。
        """
        try:
            df = self._yfinance_call(yf_ticker, start_date, end_date)
        except Exception as exc:  # noqa: BLE001
            return FetchResult(
                symbol, "yfinance", False, error=f"yfinance 调用异常: {exc}"
            )

        if df is None or len(df) == 0:
            return FetchResult(
                symbol, "yfinance", False, error="yfinance 返回空数据"
            )

        try:
            df = self._normalize_yfinance_df(df)
        except Exception as exc:  # noqa: BLE001
            return FetchResult(
                symbol, "yfinance", False, error=f"yfinance 数据解析异常: {exc}"
            )

        if df.empty:
            return FetchResult(
                symbol, "yfinance", False, error="yfinance 解析后数据为空"
            )

        return FetchResult(symbol, "yfinance", True, data=df)

    # ------------------------------------------------------------------
    # 数据规范化：统一为 [date, close] 两列
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_akshare_df(df: pd.DataFrame) -> pd.DataFrame:
        """统一 Akshare 返回的列为 [date, close]，兼容中英文列名。

        Args:
            df: Akshare 原始返回 DataFrame。

        Returns:
            仅含 ``date``、``close`` 两列的 DataFrame。
        """
        # 构造「小写列名 -> 原列名」映射，便于无大小写差异匹配
        cols_lower = {str(c).lower(): c for c in df.columns}

        # 日期列：优先 date / 日期
        date_col = cols_lower.get("date") or cols_lower.get("日期")
        if date_col is None:
            date_col = df.columns[0]  # 退化：取第一列

        # 收盘列：优先 close / 收盘价 / 收盘 / 最新价（东财外汇日K以「最新价」作日收盘）
        close_col = (
            cols_lower.get("close")
            or cols_lower.get("收盘价")
            or cols_lower.get("收盘")
            or cols_lower.get("最新价")
        )
        if close_col is None:
            # 退化：取第 4 列（典型 K 线表 close 位置）
            close_col = df.columns[3] if len(df.columns) > 3 else df.columns[-1]

        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
                "close": pd.to_numeric(df[close_col], errors="coerce"),
            }
        )
        # 去除无法解析的收盘价行
        return out.dropna(subset=["close"]).reset_index(drop=True)

    @staticmethod
    def _normalize_yfinance_df(df: pd.DataFrame) -> pd.DataFrame:
        """统一 yfinance 返回的列为 [date, close]。

        兼容新旧版本 yfinance 的列结构（单层 Index 或 MultiIndex）。

        Args:
            df: yfinance 原始返回 DataFrame。

        Returns:
            仅含 ``date``、``close`` 两列的 DataFrame。
        """
        # 新版 yfinance 对单 ticker 也返回 MultiIndex 列：(Field, Ticker)
        if isinstance(df.columns, pd.MultiIndex):
            close = df["Close"].iloc[:, 0]
        else:
            close = df["Close"]

        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df.index).strftime("%Y-%m-%d"),
                "close": pd.to_numeric(close.values, errors="coerce"),
            }
        )
        return out.dropna(subset=["close"]).reset_index(drop=True)


# ===========================================================================
# 工具级封装：记录数限制 + 批量调度（对齐工作区 commodity_price 风格）
# ===========================================================================

def _enforce_max_records(df: pd.DataFrame, max_records: int) -> pd.DataFrame:
    """将结果裁剪至最多 ``max_records`` 条（取末尾最新记录）。

    Args:
        df: 规范化后的 DataFrame。
        max_records: 最大返回记录数。

    Returns:
        裁剪后的 DataFrame。
    """
    if df is None or df.empty:
        return df
    if len(df) > max_records:
        return df.tail(max_records).reset_index(drop=True)
    return df


def _validate_max_records(max_records: int) -> int:
    """校验并规范化 max_records 参数。

    超过硬上限时**不抛错**，而是记录 WARNING 并裁剪到
    ``MAX_RECORDS_HARD_LIMIT``（由 ``.env`` 的 ``FX_MAX_RECORDS_HARD_LIMIT``
    配置，默认 50），避免因输入超限直接中断流程；同时明确告知用户
    已按阈值裁剪，防止触发数据源限流。

    Args:
        max_records: 请求的最大记录数。

    Returns:
        规范化后的 max_records（介于 1 与 MAX_RECORDS_HARD_LIMIT 之间）。

    Raises:
        ValueError: max_records 类型非法或 < 1。
    """
    if max_records is None:
        return MAX_RECORDS_PER_CALL
    if not isinstance(max_records, int) or isinstance(max_records, bool):
        raise ValueError(f"max_records 必须为整数，当前: {max_records!r}")
    if max_records < 1:
        raise ValueError(f"max_records 必须 >= 1，当前: {max_records}")
    if max_records > MAX_RECORDS_HARD_LIMIT:
        logger.warning(
            "[max_records] 请求 %d 条超过硬上限 %d（由 .env "
            "FX_MAX_RECORDS_HARD_LIMIT 配置），已自动裁剪到上限值；"
            "若需更大数据量请分批获取，或在 .env 中调大上限",
            max_records, MAX_RECORDS_HARD_LIMIT,
        )
        return MAX_RECORDS_HARD_LIMIT
    return max_records


def fetch_rate(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_records: int = MAX_RECORDS_PER_CALL,
) -> FetchResult:
    """获取指定货币对的汇率数据（记录数严格受限）。

    Akshare 优先，失败自动回退 yfinance；结果裁剪至 ``max_records`` 条。

    Args:
        symbol: 统一货币对符号，例如 "USDCNY"。
        start_date: 起始日期 "YYYY-MM-DD"；为 None 时使用近 14 天。
        end_date: 结束日期 "YYYY-MM-DD"；为 None 时使用今天。
        max_records: 最大返回记录数，默认 10；硬上限由 .env 的
            FX_MAX_RECORDS_HARD_LIMIT 配置（默认 50），超过自动裁剪。

    Returns:
        ``FetchResult`` 对象。

    Raises:
        ValueError: max_records 超出合法范围。
    """
    max_records = _validate_max_records(max_records)

    # 默认区间：近 14 天（约 10 个交易日）
    end = end_date or datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start = (datetime.now() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    else:
        start = start_date

    fetcher = FXFetcher()
    result = fetcher.fetch(symbol, start, end)
    if result.success and result.data is not None:
        result.data = _enforce_max_records(result.data, max_records)
    return result


def fetch_many(
    symbols: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_records: int = MAX_RECORDS_PER_CALL,
    batch_interval: float = BATCH_CALL_INTERVAL,
) -> List[FetchResult]:
    """批量获取多个货币对的汇率数据（限流保护）。

    限流保护：
        - 单次最多支持 5 个货币对，超出将抛出异常。
        - 每个货币对获取之间加入间隔延迟。

    Args:
        symbols: 货币对符号列表，长度不得超过 5。
        start_date: 起始日期。
        end_date: 结束日期。
        max_records: 每个货币对最大返回记录数。
        batch_interval: 批量获取时货币对间的间隔秒数。

    Returns:
        ``FetchResult`` 列表，顺序与输入 symbols 一致。

    Raises:
        ValueError: symbols 数量超过 5，或 max_records 非法。
    """
    max_records = _validate_max_records(max_records)
    if len(symbols) > MAX_BATCH_SIZE:
        raise ValueError(
            f"单次批量获取最多支持 {MAX_BATCH_SIZE} 个货币对，"
            f"当前请求 {len(symbols)} 个；请分批调用"
        )

    results: List[FetchResult] = []
    fetcher = FXFetcher()
    # 日期区间仅依赖输入参数，移出循环计算，避免重复计算
    end = end_date or datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start = (datetime.now() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    else:
        start = start_date

    for idx, symbol in enumerate(symbols):
        # 第一个货币对前不延迟；后续货币对之间加入间隔
        if idx > 0 and batch_interval > 0:
            logger.debug("批量获取节流：等待 %.2f 秒后获取 %s", batch_interval, symbol)
            time.sleep(batch_interval)

        result = fetcher.fetch(symbol, start, end)
        if result.success and result.data is not None:
            result.data = _enforce_max_records(result.data, max_records)
        results.append(result)
    return results


# ===========================================================================
# CLI 入口
# ===========================================================================

def _result_to_dict(result: FetchResult) -> Dict[str, Any]:
    """将 FetchResult 序列化为 JSON 兼容字典。"""
    records: List[Dict[str, Any]] = []
    if result.data is not None and not result.data.empty:
        for _, row in result.data.iterrows():
            records.append({"date": row["date"], "close": row["close"]})
    return {
        "symbol": result.symbol,
        "source": result.source,
        "success": result.success,
        "error": result.error,
        "fetch_time": result.fetch_time,
        "record_count": len(records),
        "records": records,
    }


def cmd_list() -> Dict[str, Any]:
    """--list: 列出所有支持的货币对。"""
    symbols = []
    for symbol, sources in SYMBOL_MAP.items():
        symbols.append({
            "symbol": symbol,
            "akshare_code": sources.get("akshare"),
            "yfinance_ticker": sources.get("yfinance"),
        })
    return {
        "success": True,
        "data": symbols,
        "meta": {
            "tool": "fx_rate",
            "command": "list",
            "total_count": len(symbols),
            "timestamp": datetime.now().isoformat(),
        },
    }


def cmd_fetch(
    codes: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_records: int = MAX_RECORDS_PER_CALL,
) -> Dict[str, Any]:
    """--code: 获取货币对汇率数据（单货币对或批量）。"""
    symbol_list = [c.strip().upper() for c in codes.split(",") if c.strip()]

    if not symbol_list:
        return {
            "success": False,
            "error": "请提供货币对代码，例如: --code USDCNY 或 --code USDCNY,EURUSD",
            "meta": {"tool": "fx_rate", "timestamp": datetime.now().isoformat()},
        }

    try:
        # 统一在入口处规范化（裁剪到硬上限），保证 meta 反映实际使用值
        effective_max = _validate_max_records(max_records)
        if len(symbol_list) == 1:
            result = fetch_rate(symbol_list[0], start_date, end_date, effective_max)
            return {
                "success": True,
                "data": _result_to_dict(result),
                "meta": {
                    "tool": "fx_rate",
                    "command": "fetch",
                    "symbol": symbol_list[0],
                    "limit": {"max_records": effective_max,
                              "requested": max_records,
                              "hard_limit": MAX_RECORDS_HARD_LIMIT},
                    "timestamp": datetime.now().isoformat(),
                },
            }
        results = fetch_many(symbol_list, start_date, end_date, effective_max)
        return {
            "success": True,
            "data": {
                "batch": True,
                "results": [_result_to_dict(r) for r in results],
                "total_count": len(results),
            },
            "meta": {
                "tool": "fx_rate",
                "command": "fetch_many",
                "symbols": symbol_list,
                "limit": {"max_records": effective_max,
                          "requested": max_records,
                          "hard_limit": MAX_RECORDS_HARD_LIMIT},
                "timestamp": datetime.now().isoformat(),
            },
        }
    except ValueError as exc:
        return {
            "success": False,
            "error": str(exc),
            "meta": {"tool": "fx_rate", "timestamp": datetime.now().isoformat()},
        }


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="国际主要货币汇率获取工具（Akshare 优先，yfinance 回退）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --code USDCNY                          # 获取最近 10 条
  %(prog)s --code USDCNY,EURUSD,GBPUSD            # 批量获取（最多 5 个）
  %(prog)s --code EURCNY                          # 欧元/人民币
  %(prog)s --list                                 # 列出所有支持货币对
  %(prog)s --code USDCNY --start 2026-07-20 --end 2026-08-01
  %(prog)s --code USDCNY --max-records 20

限流保护:
  - 单次获取默认最多返回 10 条记录（可通过 --max-records 上调，硬上限
    由 .env FX_MAX_RECORDS_HARD_LIMIT 配置，默认 50；超限自动裁剪）
  - Akshare 主路径直连东方财富极小请求，仅取日期+收盘价两字段、最近 10 个交易日
  - 批量获取最多 5 个货币对，货币对间间隔 1 秒
  - 瞬时网络异常指数退避重试（3 次，1/2/4 秒）
""")

    parser.add_argument("--code", type=str, default=None,
                        help="货币对代码，多个用逗号分隔（如 USDCNY,EURUSD）")
    parser.add_argument("--list", action="store_true",
                        help="列出所有支持的货币对")
    parser.add_argument("--start", type=str, default=None,
                        help="起始日期，格式 YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None,
                        help="结束日期，格式 YYYY-MM-DD")
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS_PER_CALL,
                        help="每个货币对最大返回记录数（默认 10，硬上限由 "
                             ".env FX_MAX_RECORDS_HARD_LIMIT 配置，默认 50；"
                             "超过自动裁剪到上限）")

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        output = cmd_list()
    elif args.code:
        output = cmd_fetch(args.code, args.start, args.end, args.max_records)
    else:
        parser.print_help()
        sys.exit(0)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()