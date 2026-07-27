#!/usr/bin/env python3
"""A 股行情数据查询工具。

使用 akshare 库获取 A 股历史行情数据，支持东方财富和新浪两个数据源。

Usage:
    {py} tools/stock_quote.py --code 300502
    {py} tools/stock_quote.py --code 300502 --start 20260101 --end 20260710
    {py} tools/stock_quote.py --code 300502 --adjust qfq
    {py} tools/stock_quote.py --code 300502 --source sina
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timedelta

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
    """为新浪接口添加交易所前缀。"""
    code = code.zfill(6)
    if code.startswith("6"):
        return f"sh{code}"
    elif code.startswith("0") or code.startswith("3"):
        return f"sz{code}"
    elif code.startswith("4"):
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
        """)

    parser.add_argument("--code", type=str, required=True, metavar="CODE",
                        help="股票代码 (必填)")
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

    args = parser.parse_args()

    code = args.code.zfill(6)
    start = args.start or _default_start()
    end = args.end or _default_end()

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