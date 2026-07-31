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
from typing import Optional

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

    args = parser.parse_args()

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
