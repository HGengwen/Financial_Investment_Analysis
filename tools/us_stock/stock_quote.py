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
"""

import argparse
import json
import sys
import time
import traceback
import warnings
from datetime import datetime, timedelta
from typing import Any, Dict

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
    parser.add_argument("--index", action="store_true", help="获取美股三大指数历史日线")
    parser.add_argument("--start", type=str, help="开始日期（格式：YYYY-MM-DD，默认一年前）")
    parser.add_argument("--end", type=str, help="结束日期（格式：YYYY-MM-DD，默认今天）")
    parser.add_argument("--no-adjust", action="store_true", help="不复权（默认前复权）")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出")

    args = parser.parse_args()

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
