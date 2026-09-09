#!/usr/bin/env python3
"""美股行情数据工具。

使用 yfinance 库获取美股个股历史K线数据及美股三大指数历史日线数据。

功能模块：
1. 个股历史K线数据（前复权/不复权，支持日期范围）
2. 美股三大指数历史日线（纳斯达克 ^IXIC、道琼斯 ^DJI、标普500 ^GSPC）

数据来源：
- Yahoo Finance（yfinance 库，免费、无需 token）

本模块从 tools/stock_us_yfinance.py 拆分而来，专注美股行情数据获取，
对应原文件的 --daily 和 --index 功能。

Usage:
    {py} tools/us_stock/stock_quote.py --daily AAPL
    {py} tools/us_stock/stock_quote.py --daily AAPL --start 2025-01-01 --end 2026-07-27
    {py} tools/us_stock/stock_quote.py --daily AAPL --no-adjust
    {py} tools/us_stock/stock_quote.py --index
    {py} tools/us_stock/stock_quote.py --index --start 2025-01-01 --end 2026-07-27
    {py} tools/us_stock/stock_quote.py --realtime AAPL   # 实时行情快照
"""

import argparse
import json
import sys
import time
import traceback
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# 注入项目根目录到 sys.path，使 `from tools.common import momentum` 在 CLI 直接运行时可用
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from tools.common import momentum as _momentum
except ImportError:  # momentum 模块缺失时降级（--momentum 命令不可用，其余命令不受影响）
    _momentum = None

try:
    from tools.common import sector_screen
except ImportError:  # sector_screen 缺失时 --auto-peers 不可用，其余不受影响
    sector_screen = None

# 忽略警告
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# 尝试导入 yfinance（提供友好的错误提示）
# ---------------------------------------------------------------------------
try:
    import yfinance as yf
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 yfinance 库: {e}。请运行: pip install yfinance",
        "meta": {"tool": "stock_quote", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

try:
    import pandas as pd
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 pandas 库: {e}。请运行: pip install pandas",
        "meta": {"tool": "stock_quote", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)


# ---------------------------------------------------------------------------
# 全局配置
# ---------------------------------------------------------------------------

# 美股三大指数代码映射
US_INDEX_MAP = {
    "纳斯达克综合指数": "^IXIC",
    "道琼斯工业平均指数": "^DJI",
    "标普500指数": "^GSPC"
}


# ---------------------------------------------------------------------------
# 重试机制
# ---------------------------------------------------------------------------

def safe_api_call(func, api_name: str, max_retries: int = 3, delay: float = 2.0) -> Any:
    """安全的API调用封装，支持重试机制。

    Args:
        func: API调用函数
        api_name: API接口名称（用于日志）
        max_retries: 最大重试次数
        delay: 重试间隔秒数

    Returns:
        API调用结果
    """
    for attempt in range(max_retries):
        try:
            result = func()
            if attempt > 0:
                print(f"✓ 重试成功 - 尝试 {attempt + 1}/{max_retries}", file=sys.stderr)
            return result
        except Exception as e:
            error_type = type(e).__name__
            if attempt < max_retries - 1:
                print(f"⚠ 尝试 {attempt + 1}/{max_retries} 失败 - {error_type}, 等待 {delay} 秒后重试...", file=sys.stderr)
                time.sleep(delay)
            else:
                print(f"✗ API调用失败 - {api_name}", file=sys.stderr)
                print(f"  错误类型: {error_type}", file=sys.stderr)
                print(f"  错误信息: {e}", file=sys.stderr)
                raise Exception(f"获取美股数据失败（已重试{max_retries}次）: {e}")
    return None


# ---------------------------------------------------------------------------
# 数据获取函数
# ---------------------------------------------------------------------------

def get_us_index_daily(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """获取美股三大指数历史日线数据。

    Args:
        start_date: 开始日期，格式 "YYYY-MM-DD"
        end_date: 结束日期，格式 "YYYY-MM-DD"

    Returns:
        dict: 包含三大指数历史数据的字典
    """
    print("正在获取美股三大指数历史日线", file=sys.stderr)

    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    result = {
        "success": True,
        "data": {},
        "meta": {
            "tool": "stock_quote",
            "api": "yf.download",
            "start_date": start_date,
            "end_date": end_date,
            "timestamp": datetime.now().isoformat()
        }
    }

    for index_name, ticker in US_INDEX_MAP.items():
        try:
            print(f"  获取 {index_name} ({ticker})...", file=sys.stderr)
            api_name = f"yf.download('{ticker}', start='{start_date}', end='{end_date}')"
            df = safe_api_call(
                lambda: yf.download(
                    tickers=ticker,
                    start=start_date,
                    end=end_date,
                    interval="1d",
                    auto_adjust=True,  # 自动前复权
                    progress=False
                ),
                api_name
            )

            if df is not None and not df.empty:
                # 处理多级列名问题
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                result["data"][index_name] = {
                    "ticker": ticker,
                    "count": len(df),
                    "columns": list(df.columns),
                    "latest": df.iloc[-1].to_dict() if len(df) > 0 else {},
                    "earliest": df.iloc[0].to_dict() if len(df) > 0 else {}
                }
                print(f"    ✓ 获取成功，数据条数: {len(df)}", file=sys.stderr)
            else:
                result["data"][index_name] = {"ticker": ticker, "count": 0, "error": "未获取到数据"}
                print(f"    ✗ 未获取到数据", file=sys.stderr)

        except Exception as e:
            result["data"][index_name] = {"ticker": ticker, "error": str(e)}
            print(f"    ✗ 获取失败: {e}", file=sys.stderr)

    return result


def get_stock_daily_kline(symbol: str, start_date: str = None, end_date: str = None,
                           auto_adjust: bool = True) -> Dict[str, Any]:
    """获取个股历史日线K线数据。

    Args:
        symbol: 美股代码，如 "AAPL"
        start_date: 开始日期，格式 "YYYY-MM-DD"
        end_date: 结束日期，格式 "YYYY-MM-DD"
        auto_adjust: 是否自动前复权，默认 True

    Returns:
        dict: 包含历史K线数据的字典
    """
    print(f"正在获取美股历史K线 - 代码: {symbol}", file=sys.stderr)

    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        api_name = f"yf.download('{symbol}', start='{start_date}', end='{end_date}')"
        df = safe_api_call(
            lambda: yf.download(
                tickers=symbol,
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=auto_adjust,  # 前复权（消除分红、拆股影响）
                progress=False
            ),
            api_name
        )

        if df is None or df.empty:
            return {
                "success": False,
                "error": "未获取到数据",
                "symbol": symbol,
                "meta": {"tool": "stock_quote", "timestamp": datetime.now().isoformat()}
            }

        # 处理多级列名问题
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return {
            "success": True,
            "symbol": symbol,
            "data": {
                "count": len(df),
                "columns": list(df.columns),
                "latest": df.iloc[-1].to_dict() if len(df) > 0 else {},
                "earliest": df.iloc[0].to_dict() if len(df) > 0 else {}
            },
            "raw_data": df,  # 保留原始 DataFrame
            "meta": {
                "tool": "stock_quote",
                "api": "yf.download",
                "start_date": start_date,
                "end_date": end_date,
                "auto_adjust": auto_adjust,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "meta": {"tool": "stock_quote", "timestamp": datetime.now().isoformat()}
        }


# ---------------------------------------------------------------------------
# 动量与技术面指标（--momentum）
# ---------------------------------------------------------------------------

#: 动量计算所需回溯（自然日）。250日涨幅 + MA200 需 ~260 个交易日，约折合 400 自然日。
_MOMENTUM_LOOKBACK_DAYS = 400


def _momentum_from_series(closes, volumes, peers):
    """由收盘价/成交量序列计算动量与技术面指标（纯计算，便于单测）。

    Args:
        closes: 收盘价序列（按时间升序，最新在末尾）。
        volumes: 成交量序列（与 closes 对齐，可为空/缺失）。
        peers: 同板块成分 250 日涨幅百分比列表（SMR 截面；None 表示不提供）。

    Returns:
        可 JSON 序列化的动量指标字典；数据不足字段为 None，不抛异常。
    """
    if _momentum is None:
        return {"error": "momentum 模块未安装，无法计算动量指标"}
    m = _momentum.compute_momentum(
        closes, volumes or None, uplift_period=250, rsi_period=50, peer_pcts=peers)
    ret = {
        "close": m["close"],
        "return_250d_pct": round(m["return_250d_pct"], 2) if m["return_250d_pct"] is not None else None,
        "smr_percentile": round(m["smr_percentile"], 2) if m["smr_percentile"] is not None else None,
        "rsi50": round(m["rsi50"], 2) if m["rsi50"] is not None else None,
        "ma50": round(m["ma50"], 4) if m["ma50"] is not None else None,
        "ma200": round(m["ma200"], 4) if m["ma200"] is not None else None,
        "tech": m["tech"],
        "data_points": len(closes),
    }
    if not peers:
        ret["note"] = "未提供板块截面(--peers)，smr_percentile 为 None"
    return ret


def _extract_series_from_df(df):
    """从 yfinance 历史K线 DataFrame 中提取升序收盘价/成交量序列。

    Args:
        df: yf.download 返回的 DataFrame（含 Close/Volume 列）。

    Returns:
        (closes, volumes) 二元组；列为空时返回空列表。
    """
    def _col(df, *names):
        for n in names:
            if n in df.columns:
                return df[n]
        return None
    closes_col = _col(df, "Close", "close")
    vols_col = _col(df, "Volume", "volume")
    closes = [float(v) for v in closes_col.dropna().tolist()] if closes_col is not None else []
    volumes = ([float(v) if v == v else 0.0 for v in vols_col.tolist()]
               if vols_col is not None else [])
    return closes, volumes


def _parse_peers(raw):
    """解析 --peers 参数（逗号分隔的百分数列表）。

    Args:
        raw: 原始字符串，如 "20.5,-3.2,55"；None 或空串返回 None。

    Returns:
        浮点列表或 None。
    """
    if not raw:
        return None
    parsed = [float(x) for x in raw.split(",") if x.strip()]
    return parsed or None


def cmd_momentum(symbol, peers, auto_peers=False):
    """--momentum: 计算个股动量与技术面指标。

    Args:
        symbol: 美股代码（如 AAPL）。
        peers: 板块成分 250 日涨幅百分比列表（或 None）。
        auto_peers: 为 True 且 peers 为空时尝试自动生成板块截面（美股暂无稳定数据源，
            返回 unavailable 提示，仍需手动 --peers）。
    """
    start = (datetime.now() - timedelta(days=_MOMENTUM_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    peers_source = None
    if auto_peers:
        if sector_screen is None:
            peers_source = "sector_unavailable"
        else:
            try:
                info = sector_screen.compute_peers_for_stock(symbol, market="us")
                if info.get("status") == "unavailable":
                    peers_source = info.get("note", "美股板块截面不可用")
                    peers = None
            except Exception as e:
                peers_source = f"sector_error:{e}"
    try:
        result = get_stock_daily_kline(symbol, start, end, auto_adjust=True)
        if not result.get("success"):
            raise RuntimeError(result.get("error", "获取历史K线失败"))
        closes, volumes = _extract_series_from_df(result["raw_data"])
        out = _momentum_from_series(closes, volumes, peers)
        if peers_source is not None:
            out["peers_source"] = peers_source
        output = {
            "success": True,
            "data": out,
            "meta": {
                "tool": "stock_quote",
                "command": "momentum",
                "symbol": symbol,
                "market": "us",
                "start_date": start,
                "end_date": end,
                "auto_adjust": True,
                "timestamp": datetime.now().isoformat(),
            },
        }
        print(json.dumps(output, ensure_ascii=False, default=str))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"获取动量指标失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_quote", "command": "momentum", "symbol": symbol,
                     "timestamp": datetime.now().isoformat()},
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 实时行情快照（--realtime）
# ---------------------------------------------------------------------------

def _realtime_from_sina(symbol: str) -> Dict[str, Any]:
    """新浪美股单只实时行情兜底源。

    yfinance（Yahoo）在中国大陆网络下常被 403 地域风控拦截，此时回退到新浪
    hq.sinajs.cn 单只行情接口（与 A股/港股新浪行情同源，大陆可达，秒级返回）。
    注意：新浪美股行情存在约 15 分钟延迟，meta.source 会标注 "sina" 以提示。

    Args:
        symbol: 美股代码（如 AAPL）。

    Returns:
        标准 data 字典；失败返回 None。
    """
    import requests as _req

    code = symbol.strip().upper().replace(".", "-").replace("$", "-")
    url = f"https://hq.sinajs.cn/list=gb_{code.lower()}"
    try:
        resp = _req.get(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }, timeout=10)
        resp.encoding = "gbk"
        text = resp.text.strip()
        if "hq_str_gb_" not in text or '"' not in text:
            return None
        raw = text.split('"')[1]
        parts = raw.split(",")
        if len(parts) < 11 or not parts[1]:
            return None

        def _f(idx: int) -> Optional[float]:
            """安全取浮点字段。"""
            try:
                v = float(parts[idx])
                return v if v == v else None  # 排除 NaN
            except (ValueError, IndexError):
                return None

        price = _f(1)
        prev_close = _f(6)
        open_ = _f(5)
        high = max(x for x in (_f(7), _f(8)) if x is not None) if (_f(7) or _f(8)) else None
        low = min(x for x in (_f(7), _f(8)) if x is not None) if (_f(7) or _f(8)) else None
        volume = _f(10)
        change = (price - prev_close) if (price is not None and prev_close) else None
        change_pct = (change / prev_close * 100) if (change is not None and prev_close) else None
        return {
            "symbol": symbol,
            "name": parts[0] or symbol,
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "prev_close": prev_close,
            "open": open_,
            "high": high,
            "low": low,
            "volume": volume,
            "amount": None,  # 新浪美股接口未提供稳定成交额字段
            "quote_time": parts[3] or None,  # 北京时间
        }
    except Exception:
        return None


def cmd_realtime(symbol: str) -> None:
    """--realtime: 获取美股单只实时行情快照。

    双数据源策略：
    1. 首选 yfinance（Yahoo Finance，.info 的 regularMarket 系列实时字段）；
    2. 失败时回退新浪 hq.sinajs.cn 单只行情接口（大陆可达，延迟约 15 分钟，
       输出 meta.source=sina 提示）。

    输出结构与 A 股 --realtime 对齐（无成交额字段时 amount 置 None）。

    Args:
        symbol: 美股代码（如 AAPL）。
    """
    source = "yfinance"
    try:
        # yfinance 默认将 cookie/时区缓存写入系统用户缓存目录（AppData），
        # 在受限沙箱环境中会被拒绝。此处重定向到项目内 data/ 可写目录，
        # 必须在任何 yfinance 请求前调用（进程级单例，一次生效）。
        _cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "us_yfinance_cache"
        _cache_dir.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(_cache_dir))
        from tools.us_stock import stock_info as us_info
        result = us_info.get_stock_realtime_info(symbol)
        if not result.get("success"):
            raise RuntimeError(result.get("error", "获取实时行情失败"))
        raw = result.get("raw_info") or {}
        base = result["data"]
        price = raw.get("regularMarketPrice") or base.get("当前价格")
        prev_close = raw.get("regularMarketPreviousClose") or base.get("昨日收盘价")
        change = raw.get("regularMarketChange")
        change_pct = raw.get("regularMarketChangePercent")
        # 缺涨跌幅字段时由价格推算（除零保护）
        if change is None and price is not None and prev_close:
            change = price - prev_close
        if change_pct is None and price is not None and prev_close:
            change_pct = (change / prev_close * 100) if prev_close else None
        quote_ts = raw.get("regularMarketTime")  # Unix epoch（美东时间）
        quote_time = (datetime.fromtimestamp(quote_ts).strftime("%Y-%m-%d %H:%M:%S")
                      if quote_ts else None)
        data = {
            "symbol": symbol,
            "name": base.get("公司名称"),
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "prev_close": prev_close,
            "open": raw.get("regularMarketOpen") or base.get("开盘价"),
            "high": raw.get("regularMarketDayHigh") or base.get("最高价"),
            "low": raw.get("regularMarketDayLow") or base.get("最低价"),
            "volume": raw.get("regularMarketVolume") or base.get("成交量"),
            "amount": None,  # yfinance 无成交额字段
            "quote_time": quote_time,
        }
        if data["price"] is None:
            raise RuntimeError("yfinance 未返回价格，尝试新浪兜底源")
    except Exception:
        # 回退新浪单只接口（大陆网络下 Yahoo 常被 403 拦截）
        data = _realtime_from_sina(symbol)
        if data is None:
            print(json.dumps({
                "success": False,
                "error": "获取实时行情失败: yfinance 与新浪源均不可用",
                "detail": traceback.format_exc(),
                "meta": {"tool": "stock_quote", "command": "realtime", "symbol": symbol,
                         "timestamp": datetime.now().isoformat()},
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        source = "sina"
    meta = {
        "tool": "stock_quote",
        "command": "realtime",
        "market": "us",
        "source": source,
        "snapshot_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": datetime.now().isoformat(),
    }
    if source == "sina":
        meta["note"] = "新浪美股行情延迟约 15 分钟，非实时盘口"
    print(json.dumps({"success": True, "data": data, "meta": meta}, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

def main():
    """主程序入口。"""
    parser = argparse.ArgumentParser(
        description="美股行情数据工具（历史K线、三大指数）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    {py} tools/us_stock/stock_quote.py --daily AAPL
    {py} tools/us_stock/stock_quote.py --daily AAPL --start 2025-01-01 --end 2026-07-27
    {py} tools/us_stock/stock_quote.py --daily AAPL --no-adjust
    {py} tools/us_stock/stock_quote.py --index
    {py} tools/us_stock/stock_quote.py --index --start 2025-01-01 --end 2026-07-27
        """
    )

    parser.add_argument("--daily", type=str, help="获取个股历史K线（美股代码，如 AAPL、MSFT）")
    parser.add_argument("--realtime", type=str, default=None, nargs="?",
                        const="__flag__", metavar="SYMBOL",
                        help="获取美股实时行情快照（yfinance，含最新价/涨跌幅/昨收/今开/最高/最低）。"
                             "用法: --realtime AAPL 或 --realtime --daily AAPL")
    parser.add_argument("--index", action="store_true", help="获取美股三大指数历史日线")
    parser.add_argument("--momentum", action="store_true",
                        help="计算动量与技术面指标（需配合 --daily）")
    parser.add_argument("--peers", type=str, default=None, metavar="PCTS",
                        help="同板块成分250日涨幅百分比列表（逗号分隔，如 20.5,-3.2,55），"
                             "用于计算 SMR 同板块百分位")
    parser.add_argument("--auto-peers", action="store_true",
                        help="尝试自动生成板块截面（A股经申万成分；美股暂无稳定数据源，"
                             "需手动 --peers）")
    parser.add_argument("--start", type=str, help="开始日期（格式：YYYY-MM-DD，默认一年前）")
    parser.add_argument("--end", type=str, help="结束日期（格式：YYYY-MM-DD，默认今天）")
    parser.add_argument("--no-adjust", action="store_true", help="不复权（默认前复权）")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出")

    args = parser.parse_args()

    # --momentum 需配合 --daily 使用
    if args.momentum:
        if not args.daily:
            parser.print_help()
            print("\n错误: --momentum 需配合 --daily 使用", file=sys.stderr)
            sys.exit(1)
        cmd_momentum(args.daily, _parse_peers(args.peers), args.auto_peers)
        return

    # --realtime 优先处理（可单独使用，或配合 --daily）
    if args.realtime is not None:
        symbol = args.realtime if args.realtime != "__flag__" else args.daily
        if not symbol:
            parser.print_help()
            print("\n错误: --realtime 需提供代码（--realtime AAPL 或 --realtime --daily AAPL）",
                  file=sys.stderr)
            sys.exit(1)
        cmd_realtime(symbol)
        return

    # 如果没有提供任何参数，显示帮助信息
    if not any([args.index, args.daily]):
        parser.print_help()
        sys.exit(0)

    # 设置输出格式
    output_json = args.json
    auto_adjust = not args.no_adjust

    try:
        # 1. 获取三大指数
        if args.index:
            result = get_us_index_daily(args.start, args.end)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print("\n【美股三大指数历史日线】")
                for name, data in result.get("data", {}).items():
                    if "error" in data:
                        print(f"  {name}: ✗ {data['error']}")
                    else:
                        print(f"  {name}: ✓ 数据条数 {data.get('count', 0)}")

        # 2. 获取历史K线
        if args.daily:
            symbol = args.daily
            result = get_stock_daily_kline(symbol, args.start, args.end, auto_adjust)
            if output_json:
                if "raw_data" in result:
                    del result["raw_data"]
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                if result.get("success"):
                    print(f"\n【{symbol} 历史K线】")
                    data = result.get("data", {})
                    print(f"  数据条数: {data.get('count', 0)}")
                    print(f"  复权: {'前复权' if auto_adjust else '不复权'}")
                    print(f"  列: {', '.join(data.get('columns', []))}")
                else:
                    print(f"✗ 获取历史K线失败: {result.get('error')}")

    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "meta": {"tool": "stock_quote", "timestamp": datetime.now().isoformat()}
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
