#!/usr/bin/env python3
"""港股行情数据查询工具。

使用 akshare 库获取港股历史K线数据及指数数据，支持新浪数据源。
本模块为港股专用工具，位于 tools/hk_stock/ 目录下，覆盖港股个股（5位数字代码，
如 00700 腾讯控股）及港股指数（如 HSI 恒生指数、CES100 恒生科技指数）。

改进说明：
1. 增加重试机制（最多3次重试）
2. 增加延迟机制（避免频繁请求）
3. 优化错误处理和日志输出

Usage:
    {py} tools/hk_stock/stock_quote.py --code 00700
    {py} tools/hk_stock/stock_quote.py --code 00700 --start 20260101 --end 20260710
    {py} tools/hk_stock/stock_quote.py --code 00700 --adjust qfq
    {py} tools/hk_stock/stock_quote.py --index HSI
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

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

# ---------------------------------------------------------------------------
# 导入 akshare
# ---------------------------------------------------------------------------
try:
    import akshare as ak
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 akshare 库: {e}。请运行: pip install akshare",
        "meta": {"tool": "stock_quote_hk", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# ---------------------------------------------------------------------------
# 默认日期范围
# ---------------------------------------------------------------------------
_DEFAULT_DAYS = 30


def _default_start() -> str:
    return (datetime.now() - timedelta(days=_DEFAULT_DAYS)).strftime("%Y%m%d")


def _default_end() -> str:
    return datetime.now().strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# 重试机制
# ---------------------------------------------------------------------------

def safe_api_call(func, api_name: str, max_retries: int = 3, delay: float = 2.0):
    """安全的API调用封装，支持重试机制。

    Args:
        func: API调用函数
        api_name: API接口名称（用于日志）
        max_retries: 最大重试次数
        delay: 重试间隔秒数

    Returns:
        DataFrame或None
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
                raise Exception(f"获取港股数据失败（已重试{max_retries}次）: {e}")
    return None


# ---------------------------------------------------------------------------
# 数据获取函数
# ---------------------------------------------------------------------------

def get_hk_hist(symbol: str, start_date: str = None, end_date: str = None,
                adjust: str = "qfq", period: str = "daily"):
    """获取港股历史K线数据。

    Args:
        symbol: 港股代码（5位数字字符串）
        start_date: 开始日期（YYYYMMDD格式）
        end_date: 结束日期（YYYYMMDD格式）
        adjust: 复权类型（""未复权 / "qfq"前复权 / "hfq"后复权）
        period: 周期类型（新浪接口仅支持日线）

    Returns:
        dict: 包含历史K线数据的字典
    """
    if not start_date:
        start_date = _default_start()
    if not end_date:
        end_date = _default_end()

    # 补齐5位代码
    symbol = symbol.zfill(5)

    try:
        # 使用新浪接口（东方财富接口网络连接不稳定）
        api_name = f"ak.stock_hk_daily(symbol='{symbol}', adjust='{adjust}')"
        print(f"正在获取港股数据 - API: {api_name}", file=sys.stderr)

        df = safe_api_call(
            lambda: ak.stock_hk_daily(symbol=symbol, adjust=adjust),
            api_name,
            max_retries=3,
            delay=2.0
        )

        # 新浪接口返回的数据格式
        # 列名: ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        # date列是datetime.date对象

        # 将datetime.date转换为字符串格式（YYYY-MM-DD）
        df['date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))

        # 筛选日期范围（日期格式为YYYY-MM-DD，需要转换为YYYYMMDD比较）
        df = df[(df['date'].str.replace('-', '') >= start_date) &
                (df['date'].str.replace('-', '') <= end_date)]

        # 转换为标准格式
        records = []
        for _, row in df.iterrows():
            record = {
                "date": str(row['date']),
                "open": float(row['open']) if row.get('open') else None,
                "high": float(row['high']) if row.get('high') else None,
                "low": float(row['low']) if row.get('low') else None,
                "close": float(row['close']) if row.get('close') else None,
                "volume": float(row['volume']) if row.get('volume') else None,
                "amount": float(row['amount']) if row.get('amount') else None,
            }
            records.append(record)

        print(f"✓ 数据获取成功 - 共{len(records)}条记录", file=sys.stderr)

        return {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "adjust": adjust,
            "period": period,
            "count": len(records),
            "data": records
        }

    except Exception as e:
        raise Exception(f"获取港股历史数据失败: {e}")


def get_hk_index(symbol: str, start_date: str = None, end_date: str = None):
    """获取港股指数历史数据。

    Args:
        symbol: 指数代码（如"HSI"恒生指数，"CES100"恒生科技）
        start_date: 开始日期（YYYYMMDD格式）
        end_date: 结束日期（YYYYMMDD格式）

    Returns:
        dict: 包含指数历史数据的字典
    """
    if not start_date:
        start_date = _default_start()
    if not end_date:
        end_date = _default_end()

    try:
        df = ak.stock_hk_index_daily_sina(symbol=symbol)

        # 筛选日期范围
        df["日期"] = df["日期"].astype(str)
        df = df[(df["日期"] >= start_date) & (df["日期"] <= end_date)]

        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["日期"]),
                "open": float(row["开盘"]) if row.get("开盘") else None,
                "high": float(row["最高"]) if row.get("最高") else None,
                "low": float(row["最低"]) if row.get("最低") else None,
                "close": float(row["收盘"]) if row.get("收盘") else None,
                "volume": float(row["成交量"]) if row.get("成交量") else None,
            })

        return {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "count": len(records),
            "data": records
        }

    except Exception as e:
        raise Exception(f"获取港股指数数据失败: {e}")


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


def cmd_momentum(code, peers, auto_peers=False):
    """--momentum: 计算个股动量与技术面指标。

    Args:
        code: 港股代码（5 位数字）。
        peers: 板块成分 250 日涨幅百分比列表（或 None）。
        auto_peers: 为 True 且 peers 为空时尝试自动生成板块截面（港股暂无数据源，
            返回 unavailable 提示，仍需手动 --peers）。
    """
    start = (datetime.now() - timedelta(days=_MOMENTUM_LOOKBACK_DAYS)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")
    peers_source = None
    if auto_peers:
        if sector_screen is None:
            peers_source = "sector_unavailable"
        else:
            try:
                info = sector_screen.compute_peers_for_stock(code, market="hk")
                if info.get("status") == "unavailable":
                    peers_source = info.get("note", "港股板块截面不可用")
                    peers = None
            except Exception as e:
                peers_source = f"sector_error:{e}"
    try:
        raw = get_hk_hist(code, start, end, "qfq", "daily")
        rows = sorted(raw["data"], key=lambda r: r.get("date"))
        closes = [float(r["close"]) for r in rows if r.get("close") is not None]
        volumes = [float(r["volume"]) if r.get("volume") is not None else 0.0 for r in rows]
        out = _momentum_from_series(closes, volumes, peers)
        if peers_source is not None:
            out["peers_source"] = peers_source
        output = {
            "success": True,
            "data": out,
            "meta": {
                "tool": "stock_quote_hk",
                "command": "momentum",
                "code": code,
                "market": "hk",
                "start_date": start,
                "end_date": end,
                "adjust": "qfq",
                "timestamp": datetime.now().isoformat(),
            },
        }
        print(json.dumps(output, ensure_ascii=False, default=str))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"获取动量指标失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_quote_hk", "command": "momentum", "code": code,
                     "timestamp": datetime.now().isoformat()},
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 处理逻辑
# ---------------------------------------------------------------------------

def cmd_code(code, start, end, adjust, period):
    """--code: 获取港股历史K线。"""
    if not code:
        print(json.dumps({
            "success": False,
            "error": "请提供港股代码，例如: --code 00700",
            "meta": {"tool": "stock_quote_hk", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        data = get_hk_hist(code, start, end, adjust, period)
        output = {
            "success": True,
            "data": data,
            "meta": {
                "tool": "stock_quote_hk",
                "command": "code",
                "code": code,
                "market": "hk",
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_quote_hk", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_index(symbol, start, end):
    """--index: 获取港股指数历史数据。"""
    if not symbol:
        print(json.dumps({
            "success": False,
            "error": "请提供指数代码，例如: --index HSI",
            "meta": {"tool": "stock_quote_hk", "command": "index", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        data = get_hk_index(symbol, start, end)
        output = {
            "success": True,
            "data": data,
            "meta": {
                "tool": "stock_quote_hk",
                "command": "index",
                "symbol": symbol,
                "market": "hk",
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_quote_hk", "command": "index", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="港股行情数据查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --code 00700                        # 获取腾讯控股最近30天数据
  %(prog)s --code 00700 --start 20260101       # 指定开始日期
  %(prog)s --code 00700 --adjust hfq           # 后复权
  %(prog)s --code 00700 --period weekly        # 周线数据
  %(prog)s --index HSI                         # 获取恒生指数数据
  %(prog)s --index CES100                      # 获取恒生科技指数数据

复权参数:
  未复权: 不指定 --adjust
  前复权: --adjust qfq (默认)
  后复权: --adjust hfq

周期参数:
  日线: --period daily (默认)
  周线: --period weekly
  月线: --period monthly
        """)

    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="港股代码（5位数字，如00700）")
    parser.add_argument("--index", type=str, default=None, metavar="SYMBOL",
                        help="港股指数代码（如HSI恒生指数，CES100恒生科技）")
    parser.add_argument("--start", type=str, default=None, metavar="DATE",
                        help=f"开始日期（YYYYMMDD格式，默认{_DEFAULT_DAYS}天前）")
    parser.add_argument("--end", type=str, default=None, metavar="DATE",
                        help="结束日期（YYYYMMDD格式，默认今天）")
    parser.add_argument("--adjust", type=str, default="qfq",
                        choices=["", "qfq", "hfq"],
                        help="复权类型: 空=未复权, qfq=前复权(默认), hfq=后复权")
    parser.add_argument("--period", type=str, default="daily",
                        choices=["daily", "weekly", "monthly"],
                        help="周期类型: daily=日线(默认), weekly=周线, monthly=月线")
    parser.add_argument("--momentum", action="store_true",
                        help="计算动量与技术面指标（250日涨幅/SMR百分位/RSI50/MA50/MA200）")
    parser.add_argument("--peers", type=str, default=None, metavar="PCTS",
                        help="同板块成分250日涨幅百分比列表（逗号分隔，如 20.5,-3.2,55），"
                             "用于计算 SMR 同板块百分位")
    parser.add_argument("--auto-peers", action="store_true",
                        help="尝试自动生成板块截面（A股经申万成分；港股暂无数据源，"
                             "需手动 --peers）")

    args = parser.parse_args()

    # --momentum 需配合 --code 使用
    if args.momentum:
        if not args.code:
            parser.print_help()
            print("\n错误: --momentum 需配合 --code 使用", file=sys.stderr)
            sys.exit(1)
        cmd_momentum(args.code, _parse_peers(args.peers), args.auto_peers)
        return

    # 确保至少一个操作
    if not args.code and not args.index:
        parser.print_help()
        print("\n错误: 请指定 --code 或 --index", file=sys.stderr)
        sys.exit(1)

    if args.code:
        cmd_code(args.code, args.start, args.end, args.adjust, args.period)
    elif args.index:
        cmd_index(args.index, args.start, args.end)


if __name__ == "__main__":
    main()
