#!/usr/bin/env python3
"""动量与技术面指标纯计算模块（阶段三）。

本模块位于 tools/common/ 下，为 `stock_quote --momentum` 提供**与数据源无关的纯计算
核心**，供 A 股 / 港股 / 美股三市场行情工具复用。所有函数仅依赖数值序列
（价格/成交量），不发起任何网络请求，因此可完全离线开发与单元测试。

覆盖技能文件「动量与市场共识」维度所需计算：
- 250 日 SMR 相对强度（同板块百分位排名，维度④主指标）
- RSI(50) 中期动量（维度④备选指标）
- MA50 / MA200 及量能（技术面止损校验，独立否决项）
- ATR(14) 与动态止损价（GARP 框架「第三部分·五」高波动科技股动态跟踪止损）

输出 `tech` 子结构字段名与打分引擎 `trend_tech_screen.TechData` 精确对齐
（`close_above_ma50` / `close_above_ma200` / `volume_above_1_5x`），可直接喂给打分引擎。

Usage:
    from tools.common import momentum

    # 由行情工具传入收盘价序列与成交量序列
    res = momentum.compute_momentum(closes, volumes, peer_pcts=peer_pcts)
    # res["smr_percentile"]  # 同板块百分位（0-100）
    # res["tech"]            # {"close_above_ma50": bool, ...}

    # ATR 动态止损（供 stock_quote --momentum 与 P4-6 风控编排复用）
    atr14 = momentum.atr(highs, lows, closes)
    stop = momentum.stop_price(highs, lows, closes, entry_price=100.0)
    # stop == {"atr14": ..., "stop_price": ..., "stop_pct": ...}
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


def _true_range(high: _NUM, low: _NUM, prev_close: _NUM) -> Optional[float]:
    """计算单根 K 线的真实波幅（TR）。

    TR 定义为当日振幅与两个跳空幅度三者的最大值：
    ``max(最高−最低, |最高−昨收|, |最低−昨收|)``。

    Args:
        high: 当日最高价。
        low: 当日最低价。
        prev_close: 前一根 K 线收盘价（昨收）。

    Returns:
        真实波幅（float）；任一输入为 None 时返回 None。
    """
    if None in (high, low, prev_close):
        return None
    return max(float(high) - float(low),
               abs(float(high) - float(prev_close)),
               abs(float(low) - float(prev_close)))


def _atr_raw(highs: List[_NUM], lows: List[_NUM], closes: List[_NUM],
             period: int = 14, method: str = "wilder") -> Optional[float]:
    """计算当前（最新一期）ATR 的全精度值（不做四舍五入）。

    与 ``atr()`` 的区别在于返回未经 ``round`` 的原始浮点值，供 ``stop_price()``
    在计算止损价时复用，避免「先 round ATR 再乘倍数」带来的中间舍入误差。

    Args:
        highs: 最高价序列（按时间升序）。
        lows: 最低价序列（按时间升序）。
        closes: 收盘价序列（按时间升序；同时用于「昨收」计算）。
        period: ATR 周期（默认 14）。
        method: 平滑方法，'wilder'（默认）或 'sma'。

    Returns:
        全精度 ATR（float）；数据不足或方法非法时返回 None。
    """
    n = len(highs)
    if period <= 0 or n < period + 1:
        return None

    trs: List[float] = []
    for i in range(1, n):
        tr = _true_range(highs[i], lows[i], closes[i - 1])
        if tr is not None:
            trs.append(tr)

    if len(trs) < period:
        return None

    if method == "sma":
        return sum(trs[-period:]) / period
    if method != "wilder":
        # 仅支持 'wilder' 与 'sma' 两种口径，其余静默降级
        return None

    # Wilder 平滑：初始简单平均 + 递归平滑
    avg = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        avg = (avg * (period - 1) + trs[i]) / period
    return avg


def atr(highs: List[_NUM], lows: List[_NUM], closes: List[_NUM],
        period: int = 14, method: str = "wilder") -> Optional[float]:
    """计算当前（最新一期）ATR（平均真实波幅）。

    逐根计算 TR 后，按所选方法平滑：

    - ``'wilder'``（默认，行业标准）：初始为前 ``period`` 个 TR 的简单平均，
      之后按 ``(avg×(period−1)+tr)/period`` 递归平滑（与 Wilder/主流软件一致）。
    - ``'sma'``：最近 ``period`` 个 TR 的简单平均（框架字面「平均真实波幅」）。

    Args:
        highs: 最高价序列（按时间升序）。
        lows: 最低价序列（按时间升序）。
        closes: 收盘价序列（按时间升序；同时用于「昨收」计算）。
        period: ATR 周期（默认 14）。
        method: 平滑方法，'wilder'（默认）或 'sma'。

    Returns:
        最新一期 ATR（float，2 位小数）；数据不足或方法非法时返回 None。
    """
    raw = _atr_raw(highs, lows, closes, period=period, method=method)
    return None if raw is None else round(raw, 2)


def stop_price(highs: List[_NUM], lows: List[_NUM], closes: List[_NUM],
               entry_price: float, multiplier: float = 2.0,
               period: int = 14, method: str = "wilder") -> dict:
    """计算 ATR 动态止损价与止损幅度。

    止损价 = 买入价 − multiplier × ATR(period)；
    止损幅度 = (买入价 − 止损价) / 买入价 × 100。

    注意本函数仅输出「原始」止损幅度，不做 20% 底仓容忍度封顶，也不做
    8%~10% 硬止损与仓位状态分档——该类判断由上层编排（P4-6）完成。

    Args:
        highs: 最高价序列（按时间升序）。
        lows: 最低价序列（按时间升序）。
        closes: 收盘价序列（按时间升序）。
        entry_price: 买入价。
        multiplier: ATR 倍数（框架取 2~3，默认 2.0）。
        period: ATR 周期（默认 14）。
        method: 平滑方法，'wilder'（默认）或 'sma'。

    Returns:
        dict: 仅含 ``{'atr14', 'stop_price', 'stop_pct'}`` 三字段（2 位小数）；
              数据不足或非法输入时对应字段为 None。
    """
    raw_atr = _atr_raw(highs, lows, closes, period=period, method=method)
    atr14 = None if raw_atr is None else round(raw_atr, 2)

    # 护栏：非法输入静默降级为 None，不抛异常
    if raw_atr is None or entry_price is None or float(entry_price) <= 0 \
            or multiplier is None or float(multiplier) <= 0:
        return {"atr14": atr14, "stop_price": None, "stop_pct": None}

    entry = float(entry_price)
    mult = float(multiplier)
    # 用全精度 ATR 计算止损价，最后才 round，避免中间舍入误差
    stop = round(entry - mult * raw_atr, 2)
    stop_pct = round((entry - stop) / entry * 100, 2)
    return {"atr14": atr14, "stop_price": stop, "stop_pct": stop_pct}