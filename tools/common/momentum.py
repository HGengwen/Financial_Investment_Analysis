#!/usr/bin/env python3
"""动量与技术面指标纯计算模块（阶段三）。

本模块位于 tools/common/ 下，为 `stock_quote --momentum` 提供**与数据源无关的纯计算
核心**，供 A 股 / 港股 / 美股三市场行情工具复用。所有函数仅依赖数值序列
（价格/成交量），不发起任何网络请求，因此可完全离线开发与单元测试。

覆盖技能文件「动量与市场共识」维度所需计算：
- 250 日 SMR 相对强度（同板块百分位排名，维度④主指标）
- RSI(50) 中期动量（维度④备选指标）
- MA50 / MA200 及量能（技术面止损校验，独立否决项）

输出 `tech` 子结构字段名与打分引擎 `trend_tech_screen.TechData` 精确对齐
（`close_above_ma50` / `close_above_ma200` / `volume_above_1_5x`），可直接喂给打分引擎。

Usage:
    from tools.common import momentum

    # 由行情工具传入收盘价序列与成交量序列
    res = momentum.compute_momentum(closes, volumes, peer_pcts=peer_pcts)
    # res["smr_percentile"]  # 同板块百分位（0-100）
    # res["tech"]            # {"close_above_ma50": bool, ...}
"""

from __future__ import annotations

from typing import List, Optional, Union

_NUM = Union[int, float, None]


def sma(closes: List[_NUM], window: int) -> List[Optional[float]]:
    """计算简单移动平均（SMA），前 window-1 个位置为 None。

    Args:
        closes: 收盘价序列（按时间升序）。
        window: 移动平均窗口（如 50 / 200）。

    Returns:
        长度与 closes 相同的 SMA 列表；靠近开头无法凑满窗口的位置为 None。
    """
    n = len(closes)
    if n == 0 or window <= 0:
        return [None] * n
    result: List[Optional[float]] = [None] * n
    running: float = 0.0
    for i, price in enumerate(closes):
        if price is None:
            continue
        running += float(price)
        if i >= window:
            prev = closes[i - window]
            if prev is not None:
                running -= float(prev)
        if i >= window - 1:
            result[i] = running / window
    return result


def rsi(closes: List[_NUM], period: int = 14) -> Optional[float]:
    """计算当前（最新一期）RSI，采用 Wilder 平滑算法（主流软件口径）。

    RSI = 100 - 100 / (1 + RS)，其中 RS = 平均涨幅 / 平均跌幅。

    Args:
        closes: 收盘价序列（按时间升序）。
        period: RSI 周期（技能文件动量备选指标用 50）。

    Returns:
        最新一期 RSI（0-100）；数据不足一周期+1 个样本时返回 None。
    """
    if period <= 0:
        return None
    n = len(closes)
    if n < period + 1:
        return None
    changes = [float(closes[i]) - float(closes[i - 1]) for i in range(1, n)
               if closes[i] is not None and closes[i - 1] is not None]
    if len(changes) < period:
        return None
    gains = [max(d, 0.0) for d in changes]
    losses = [max(-d, 0.0) for d in changes]
    # Wilder 平滑：先取初始 SMA，再按当前涨跌幅滚动平滑
    avg_gain: float = sum(gains[:period]) / period
    avg_loss: float = sum(losses[:period]) / period
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def pct_change(closes: List[_NUM], period: int) -> Optional[float]:
    """计算最近 period 期涨跌幅（百分比）。

    Args:
        closes: 收盘价序列（按时间升序）。
        period: 回溯期数（如 250 日）。

    Returns:
        涨跌幅百分比；数据不足或基准价为 0 时返回 None。
    """
    n = len(closes)
    if n <= period:
        return None
    past, latest = closes[-(period + 1)], closes[-1]
    if past is None or latest is None or float(past) == 0.0:
        return None
    return (float(latest) - float(past)) / float(past) * 100.0


def percentile_rank(peer_scores: List[float], own_score: float) -> Optional[float]:
    """计算 own_score 在 peer_scores 板块截面中的百分位（0-100，越大越强）。

    Args:
        peer_scores: 同板块所有成分的得分（如 250 日涨幅）。
        own_score: 个股自身得分。

    Returns:
        百分位数值（等于或低于 own_score 的成分占比）；peer_scores 为空时返回 None。
    """
    if not peer_scores:
        return None
    below = sum(1 for s in peer_scores if s <= own_score)
    return below / len(peer_scores) * 100.0


def avg_volume(volumes: List[_NUM], lookback: int = 20) -> Optional[float]:
    """计算成交量近 lookback 期均值（用于放量判断的基准）。

    Args:
        volumes: 成交量序列（按时间升序）。
        lookback: 回看期数。

    Returns:
        近 lookback 期日均量；数据不足时返回 None。
    """
    window = volumes[-lookback:]
    nums = [float(v) for v in window if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def tech_check(closes: List[_NUM], volumes: List[_NUM],
               ma50_window: int = 50, ma200_window: int = 200,
               vol_mult: float = 1.5) -> dict:
    """技术面止损校验布尔项，与打分引擎 TechData 字段对齐。

    - close_above_ma50：现价是否位于 50 日均线上方
    - close_above_ma200：现价是否位于 200 日均线上方
    - volume_above_1_5x：当日量能是否放量（> 近 20 日均量的 vol_mult 倍）

    Args:
        closes: 收盘价序列。
        volumes: 成交量序列。
        ma50_window: 50 日均线窗口。
        ma200_window: 200 日均线窗口。
        vol_mult: 放量阈值倍数。

    Returns:
        tech 字典（字段名与 trend_tech_screen.TechData 对齐）；对应数据不足时为 None。
    """
    ma50 = sma(closes, ma50_window)
    ma200 = sma(closes, ma200_window)
    close = closes[-1]
    close_above_ma50 = None
    close_above_ma200 = None
    if close is not None:
        if ma50[-1] is not None:
            close_above_ma50 = bool(float(close) >= float(ma50[-1]))
        if ma200[-1] is not None:
            close_above_ma200 = bool(float(close) >= float(ma200[-1]))

    volume_above_1_5x = None
    if volumes and len(volumes) >= 2 and volumes[-1] is not None:
        ref = avg_volume(volumes[:-1], lookback=20)
        if ref is not None and ref > 0.0:
            volume_above_1_5x = bool(float(volumes[-1]) >= vol_mult * float(ref))

    return {
        "close_above_ma50": close_above_ma50,
        "close_above_ma200": close_above_ma200,
        "volume_above_1_5x": volume_above_1_5x,
    }


def compute_momentum(closes: List[_NUM], volumes: Optional[List[_NUM]] = None,
                     uplift_period: int = 250, rsi_period: int = 50,
                     peer_pcts: Optional[List[float]] = None) -> dict:
    """汇总计算动量与技术面指标（`stock_quote --momentum` 的计算核心）。

    Args:
        closes: 收盘价序列（需覆盖 uplift_period+1 个样本以计算 250 日涨幅）。
        volumes: 成交量序列（可选，缺省则技术面量能项为 None）。
        uplift_period: 相对强度回溯期（默认 250）。
        rsi_period: RSI 周期（技能文件取 50）。
        peer_pcts: 同板块所有成分的 250 日涨幅列表（可选；提供则计算 SMR 百分位）。

    Returns:
        汇总字典，含 close / ma50 / ma200 / rsi50 / return_250d_pct /
        smr_percentile / tech。数据不足的字段为 None，不抛异常。
    """
    ma50 = sma(closes, 50)
    ma200 = sma(closes, 200)
    return_250d = pct_change(closes, uplift_period)

    smr_percentile = None
    if peer_pcts:
        if return_250d is not None:
            smr_percentile = percentile_rank(peer_pcts, return_250d)
        else:
            smr_percentile = percentile_rank(peer_pcts, float("-inf"))

    tech = tech_check(closes, volumes or [])

    return {
        "close": float(closes[-1]) if closes and closes[-1] is not None else None,
        "ma50": ma50[-1] if ma50 else None,
        "ma200": ma200[-1] if ma200 else None,
        "rsi50": rsi(closes, rsi_period),
        "return_250d_pct": return_250d,
        "smr_percentile": smr_percentile,
        "tech": tech,
    }