#!/usr/bin/env python3
"""A 股行情数据查询工具（沪深京市场）。

使用 akshare 库获取 A 股历史行情数据，支持东方财富和新浪两个数据源。
本模块为 A 股专用工具，位于 tools/a_share/ 目录下，覆盖沪市（60/688 开头）、
深市（00/30 开头）及北交所（4/8 开头）股票。

Usage:
    {py} tools/a_share/stock_quote.py --code 300502
    {py} tools/a_share/stock_quote.py --code 300502 --start 20260101 --end 20260710
    {py} tools/a_share/stock_quote.py --code 300502 --adjust qfq
    {py} tools/a_share/stock_quote.py --code 300502 --source sina
    {py} tools/a_share/stock_quote.py --realtime 300502   # 实时行情快照
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

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
# 默认日期范围
# ---------------------------------------------------------------------------
_DEFAULT_DAYS = 30


def _default_start() -> str:
    return (datetime.now() - timedelta(days=_DEFAULT_DAYS)).strftime("%Y%m%d")


def _default_end() -> str:
    return datetime.now().strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# 数据获取函数
# ---------------------------------------------------------------------------

def get_quote_eastmoney(symbol: str, start_date: str, end_date: str, adjust: str = "") -> dict:
    """从东方财富获取历史行情。"""
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )
    if df.empty:
        return {"records": [], "count": 0}

    # 统一列名为英文
    column_map = {
        "日期": "date",
        "股票代码": "code",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "change_pct",
        "涨跌额": "change",
        "换手率": "turnover",
    }
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    # 成交量转换为手，成交额转换为元
    records = []
    for _, row in df.iterrows():
        r = {}
        for col in df.columns:
            val = row[col]
            if isinstance(val, float):
                # 成交量单位是股，转换为手
                if col == "volume":
                    val = round(val / 100, 2)
                elif col in ("amount",):
                    val = round(val, 2)
                elif col in ("amplitude", "change_pct", "turnover"):
                    val = round(val, 2)
            r[col] = val
        records.append(r)

    return {"records": records, "count": len(records)}


def _ensure_sina_symbol(code: str) -> str:
    """为新浪接口添加交易所前缀。

    Args:
        code: 6 位股票代码，不足位前补零。

    Returns:
        带交易所前缀的新浪代码：sh（沪市 60/688）、sz（深市 00/30）、
        bj（北交所 4/8）。无法识别前缀时返回补零后的原代码。
    """
    code = code.zfill(6)
    if code.startswith("6"):
        return f"sh{code}"
    elif code.startswith("0") or code.startswith("3"):
        return f"sz{code}"
    elif code.startswith("4") or code.startswith("8"):
        return f"bj{code}"
    return code


def get_quote_sina(symbol: str, start_date: str, end_date: str, adjust: str = "") -> dict:
    """从新浪获取历史行情。"""
    sina_symbol = _ensure_sina_symbol(symbol)
    df = ak.stock_zh_a_daily(
        symbol=sina_symbol,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )
    if df.empty:
        return {"records": [], "count": 0}

    column_map = {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
        "outstanding_share": "outstanding_share",
        "turnover": "turnover",
    }
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    records = []
    for _, row in df.iterrows():
        r = {}
        for col in df.columns:
            val = row[col]
            if isinstance(val, float):
                if col == "volume":
                    val = round(val / 100, 2)  # 股 -> 手
                elif col in ("outstanding_share",):
                    val = round(val / 10000, 2)  # 股 -> 万股
                elif col == "turnover":
                    val = round(val, 4)
                else:
                    val = round(val, 2)
            # 日期转字符串
            if col == "date" and hasattr(val, "strftime"):
                val = val.strftime("%Y-%m-%d")
            r[col] = val
        records.append(r)

    return {"records": records, "count": len(records)}


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
        code: 6 位 A 股代码。
        peers: 板块成分 250 日涨幅百分比列表（或 None）。
        auto_peers: 为 True 且 peers 为空时，经 sector_screen 自动生成同板块截面。
    """
    # 优先手动 --peers；否则按需经行业缓存自动生成 SMR 板块截面
    peers_source = None
    industry = None
    if auto_peers:
        if sector_screen is None:
            peers_source = "sector_unavailable"
        else:
            try:
                info = sector_screen.compute_peers_for_stock(code)
                peers = info["pcts"] or None
                industry = info["industry"]
                peers_source = (f"sector:{info['status']}"
                                f"({info['count']}成分,跳过{info.get('skipped', 0)})")
            except RuntimeError as e:
                peers_source = f"sector_error:{e}"

    start = (datetime.now() - timedelta(days=_MOMENTUM_LOOKBACK_DAYS)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")
    try:
        # 优先东方财富（默认主力源），失败回退新浪
        try:
            result = get_quote_eastmoney(code, start, end, "qfq")
        except Exception:
            result = get_quote_sina(code, start, end, "qfq")
        rows = sorted(result["records"], key=lambda r: r.get("date"))
        closes = [float(r["close"]) for r in rows if r.get("close") is not None]
        volumes = [float(r["volume"]) if r.get("volume") is not None else 0.0 for r in rows]
        out = _momentum_from_series(closes, volumes, peers)
        meta = {
            "tool": "stock_quote",
            "command": "momentum",
            "code": code,
            "market": "a_share",
            "start_date": start,
            "end_date": end,
            "adjust": "qfq",
            "timestamp": datetime.now().isoformat(),
            "peers_source": peers_source,
            "peers_industry": industry,
        }
        if not peers and peers_source is not None:
            out["note"] = (out.get("note", "") + f"；{peers_source}").strip("；")
        output = {"success": True, "data": out, "meta": meta}
        print(json.dumps(output, ensure_ascii=False, default=str))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"获取动量指标失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_quote", "command": "momentum", "code": code,
                     "timestamp": datetime.now().isoformat()},
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# A 股指数行情（--index）
# ---------------------------------------------------------------------------

#: 常见 A 股指数名称（供 --index 参考，接口亦接受未列出的名称）
_INDEX_NAMES = ("上证指数", "深证成指", "创业板指", "科创50", "沪深300")


def get_index_daily(symbol, start_date=None, end_date=None):
    """获取 A 股指数历史日线（东方财富 stock_zh_index_daily_em）。

    Args:
        symbol: 指数名称，如 "上证指数"、"创业板指"。
        start_date: 开始日期（YYYYMMDD），默认不限。
        end_date: 结束日期（YYYYMMDD），默认不限。

    Returns:
        dict: 含 records（date/open/high/low/close/volume/amount，按日期升序）
        与 count 的字典；无数据返回空 records。
    """
    df = ak.stock_zh_index_daily_em(symbol=symbol)
    if df is None or df.empty:
        return {"records": [], "count": 0}
    df = df.copy()
    # 日期列统一为字符串并升序
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").reset_index(drop=True)
    # 日期范围过滤（YYYY-MM-DD -> YYYYMMDD 比较）
    if start_date:
        df = df[df["date"].str.replace("-", "") >= start_date]
    if end_date:
        df = df[df["date"].str.replace("-", "") <= end_date]

    records = []
    for _, row in df.iterrows():
        rec = {}
        for col in df.columns:
            val = row[col]
            if isinstance(val, float):
                rec[col] = round(val, 2)
            else:
                rec[col] = val
        records.append(rec)
    return {"records": records, "count": len(records)}


def cmd_index(symbol, start, end):
    """--index: 获取 A 股指数历史日线行情。

    Args:
        symbol: 指数名称。
        start: 开始日期（YYYYMMDD）。
        end: 结束日期（YYYYMMDD）。
    """
    try:
        result = get_index_daily(symbol, start or _default_start(), end or _default_end())
        output = {
            "success": True,
            "data": result["records"],
            "meta": {
                "tool": "stock_quote",
                "command": "index",
                "index": symbol,
                "market": "a_share",
                "start_date": start,
                "end_date": end,
                "count": result["count"],
                "timestamp": datetime.now().isoformat(),
            },
        }
        print(json.dumps(output, ensure_ascii=False, default=str))
    except Exception as e:
        error_msg = f"获取指数行情失败: {e}"
        if "Connection" in str(e) or "RemoteDisconnected" in str(e):
            error_msg = "获取指数行情失败: 网络连接失败 (东方财富不可达)"
        print(json.dumps({
            "success": False,
            "error": error_msg,
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_quote", "command": "index", "index": symbol,
                     "timestamp": datetime.now().isoformat()},
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 实时行情快照（--realtime）
# ---------------------------------------------------------------------------

#: 新浪全市场快照代码列前缀（sh-沪 / sz-深 / bj-北交），匹配前需剥离
_SPOT_PREFIX_RE = r"^(sh|sz|bj)"


def cmd_realtime(code: str) -> None:
    """--realtime: 获取 A 股单只股票实时快照（新浪全市场快照按代码过滤）。

    东财 push2 实时接口（stock_bid_ask_em / stock_zh_a_spot_em）在中国大陆
    网络下连接不稳定（RemoteDisconnected），故以新浪 stock_zh_a_spot 为主源。

    Args:
        code: 6 位 A 股代码（不足位自动补零）。
    """
    try:
        print("正在获取全市场实时快照（新浪，约 10-20 秒）...", file=sys.stderr)
        df = ak.stock_zh_a_spot()
        code6 = code.zfill(6)
        # 新浪代码列形如 sz300502 / sh600000 / bj920000，剥离前缀后精确匹配
        df = df.copy()
        df["代码"] = df["代码"].astype(str).str.replace(_SPOT_PREFIX_RE, "", regex=True)
        row = df[df["代码"] == code6]
        if row.empty:
            raise RuntimeError(f"实时快照中未找到代码 {code6}（可能已退市或代码有误）")
        rec = row.iloc[0]

        data = {
            "code": code6,
            "name": rec.get("名称"),
            "price": float(rec.get("最新价")),      # 最新成交价（元）
            "change": float(rec.get("涨跌额")),      # 涨跌额（元）
            "change_pct": float(rec.get("涨跌幅")),  # 涨跌幅（%）
            "prev_close": float(rec.get("昨收")),    # 昨收（元）
            "open": float(rec.get("今开")),          # 今开（元）
            "high": float(rec.get("最高")),          # 当日最高（元）
            "low": float(rec.get("最低")),           # 当日最低（元）
            "volume": float(rec.get("成交量")),      # 成交量（股）
            "amount": float(rec.get("成交额")),      # 成交额（元）
            "quote_time": str(rec.get("时间戳")),    # 新浪行情时间（HH:MM:SS）
        }
        meta = {
            "tool": "stock_quote",
            "command": "realtime",
            "market": "a_share",
            "source": "sina",
            "snapshot_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().isoformat(),
        }
        print(json.dumps({"success": True, "data": data, "meta": meta}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"获取实时行情失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_quote", "command": "realtime", "code": code,
                     "timestamp": datetime.now().isoformat()},
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A 股行情数据查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --code 300502                           # 近30日行情
  %(prog)s --code 300502 --start 20260101 --end 20260710  # 指定日期范围
  %(prog)s --code 300502 --adjust qfq              # 前复权
  %(prog)s --code 300502 --source sina             # 使用新浪数据源
  %(prog)s --index 上证指数                        # 上证指数日线行情
        """)

    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="股票代码")
    parser.add_argument("--index", type=str, default=None, metavar="INDEX",
                        help='指数名称（如 上证指数/创业板指/沪深300）')
    parser.add_argument("--start", type=str, default=None, metavar="YYYYMMDD",
                        help=f"开始日期 (默认 {_DEFAULT_DAYS} 天前)")
    parser.add_argument("--end", type=str, default=None, metavar="YYYYMMDD",
                        help="结束日期 (默认今天)")
    parser.add_argument("--adjust", type=str, default="", metavar="ADJUST",
                        choices=["", "qfq", "hfq"],
                        help='复权方式: ""-不复权, qfq-前复权, hfq-后复权 (默认不复权)')
    parser.add_argument("--source", type=str, default="eastmoney", metavar="SOURCE",
                        choices=["eastmoney", "sina"],
                        help='数据源: eastmoney-东方财富, sina-新浪 (默认 eastmoney)')
    parser.add_argument("--momentum", action="store_true",
                        help="计算动量与技术面指标（250日涨幅/SMR百分位/RSI50/MA50/MA200）")
    parser.add_argument("--realtime", type=str, default=None, nargs="?",
                        const="__flag__", metavar="CODE",
                        help="获取实时行情快照（新浪全市场快照，含最新价/涨跌幅/昨收/今开/最高/最低）。"
                             "用法: --realtime 300502 或 --realtime --code 300502")
    parser.add_argument("--peers", type=str, default=None, metavar="PCTS",
                        help="同板块成分250日涨幅百分比列表（逗号分隔，如 20.5,-3.2,55），"
                             "用于计算 SMR 同板块百分位")
    parser.add_argument("--auto-peers", action="store_true",
                        help="自动生成 SMR 板块截面：经行业缓存取同行业成分，"
                             "批量拉取其 250 日涨幅作为 --peers（优于手动传参）")

    args = parser.parse_args()

    if args.momentum:
        if not args.code:
            parser.print_help()
            print("\n错误: --momentum 需配合 --code 使用", file=sys.stderr)
            sys.exit(1)
        cmd_momentum(args.code.zfill(6), _parse_peers(args.peers), args.auto_peers)
        return

    if args.realtime is not None:
        code = args.realtime if args.realtime != "__flag__" else args.code
        if not code:
            parser.print_help()
            print("\n错误: --realtime 需提供代码（--realtime 300502 或 --realtime --code 300502）",
                  file=sys.stderr)
            sys.exit(1)
        cmd_realtime(code.zfill(6))
        return

    # 确保至少指定一个查询目标
    if not args.code and not args.index:
        parser.print_help()
        print("\n错误: 请指定 --code 或 --index", file=sys.stderr)
        sys.exit(1)

    start = args.start or _default_start()
    end = args.end or _default_end()

    if args.index and not args.code:
        cmd_index(args.index, start, end)
        return

    code = args.code.zfill(6)

    # Helper: try both sources with fallback
    def fetch_with_fallback():
        errors = []
        # Try primary source first
        if args.source == "eastmoney":
            try:
                return get_quote_eastmoney(code, start, end, args.adjust)
            except Exception as e:
                errors.append(f"EastMoney: {e}")
        # Fallback to Sina
        try:
            return get_quote_sina(code, start, end, args.adjust)
        except Exception as e:
            errors.append(f"Sina: {e}")
        # All failed
        raise RuntimeError(" | ".join(errors))

    try:
        result = fetch_with_fallback()
        output = {
            "success": True,
            "data": result["records"],
            "meta": {
                "tool": "stock_quote",
                "source": args.source,
                "code": code,
                "start_date": start,
                "end_date": end,
                "adjust": args.adjust or "none",
                "count": result["count"],
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False, default=str))

    except Exception as e:
        error_msg = str(e)
        if "Connection" in error_msg or "RemoteDisconnected" in error_msg:
            error_msg = f"网络连接失败 (EastMoney/Sina均不可达)"
        print(json.dumps({
            "success": False,
            "error": f"获取行情失败: {error_msg}",
            "detail": traceback.format_exc(),
            "meta": {
                "tool": "stock_quote",
                "code": code,
                "timestamp": datetime.now().isoformat()
            }
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
