#!/usr/bin/env python3
"""美股个股实时行情与估值指标查询工具（美股信息查询模块）。

本模块位于 tools/us_stock/ 目录下，专门用于查询美股上市公司的
实时行情与估值指标，是美股数据工具集的核心行情查询入口。

使用 yfinance 库获取美股上市公司的实时行情、估值指标等信息。

数据来源：
- Yahoo Finance（实时行情、估值指标）

功能：
- 获取个股实时行情与估值指标（PE、PB、市值、股息率、Beta、ROE、ROA等）

优势：
- 免费、无需 token、无需积分
- 底层接口稳定，时区处理专业

Usage:
    {py} tools/us_stock/stock_info.py --realtime AAPL
    {py} tools/us_stock/stock_info.py --realtime MSFT --json
    {py} tools/us_stock/stock_info.py --realtime GOOGL

美股历史K线、财务报表等功能请使用: tools/stock_us_yfinance.py
"""

import argparse
import json
import sys
import time
import traceback
import warnings
from datetime import datetime
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
        "meta": {"tool": "stock_info", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)


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

def get_stock_realtime_info(symbol: str) -> Dict[str, Any]:
    """获取个股实时行情与估值指标。

    Args:
        symbol: 美股代码，如 "AAPL"、"TSLA"、"MSFT"

    Returns:
        dict: 包含实时行情和估值指标数据的字典
    """
    print(f"正在获取美股实时行情 - 代码: {symbol}", file=sys.stderr)

    try:
        # 实例化股票对象
        api_name = f"yf.Ticker('{symbol}')"
        stock = safe_api_call(lambda: yf.Ticker(symbol), api_name)

        # 获取实时信息
        api_name = f"stock.info"
        info = safe_api_call(lambda: stock.info, api_name)

        if info is None:
            return {
                "success": False,
                "error": "未获取到数据",
                "symbol": symbol,
                "meta": {"tool": "stock_info", "timestamp": datetime.now().isoformat()}
            }

        # 提取关键实时字段
        realtime_data = {
            "股票代码": symbol,
            "公司名称": info.get("longName"),
            "当前价格": info.get("currentPrice"),
            "开盘价": info.get("open"),
            "最高价": info.get("dayHigh"),
            "最低价": info.get("dayLow"),
            "昨日收盘价": info.get("previousClose"),
            "成交量": info.get("volume"),
            "市值": info.get("marketCap"),
            "市盈率TTM": info.get("trailingPE"),
            "市净率PB": info.get("priceToBook"),
            "52周最高": info.get("fiftyTwoWeekHigh"),
            "52周最低": info.get("fiftyTwoWeekLow"),
            "股息率": info.get("dividendYield"),
            "Beta系数": info.get("beta"),
            "ROE": info.get("returnOnEquity"),
            "ROA": info.get("returnOnAssets"),
            "流通市值": info.get("floatShares"),
            "总股本": info.get("sharesOutstanding")
        }

        return {
            "success": True,
            "symbol": symbol,
            "data": realtime_data,
            "raw_info": info,  # 保留原始数据
            "meta": {
                "tool": "stock_info",
                "api": "yf.Ticker.info",
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "meta": {"tool": "stock_info", "timestamp": datetime.now().isoformat()}
        }


# ---------------------------------------------------------------------------
# CLI 处理逻辑
# ---------------------------------------------------------------------------

def cmd_realtime(symbol: str, output_json: bool = False) -> None:
    """--realtime: 获取个股实时行情与估值指标。

    Args:
        symbol: 美股代码，如 "AAPL"
        output_json: 是否以 JSON 格式输出
    """
    if not symbol:
        print(json.dumps({
            "success": False,
            "error": "请提供美股代码，例如: --realtime AAPL",
            "meta": {"tool": "stock_info", "command": "realtime", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        result = get_stock_realtime_info(symbol)
        if output_json:
            # 移除 raw_info 以减少输出量
            if "raw_info" in result:
                del result["raw_info"]
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            if result.get("success"):
                print(f"\n【{symbol} 实时行情与估值指标】")
                data = result.get("data", {})
                for key, value in data.items():
                    print(f"  {key}: {value}")
            else:
                print(f"✗ 获取实时行情失败: {result.get('error')}")
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "realtime", "timestamp": datetime.now().isoformat()}
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """主程序入口。"""
    parser = argparse.ArgumentParser(
        description="美股个股实时行情与估值指标查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --realtime AAPL                  # 获取苹果实时行情
  %(prog)s --realtime MSFT --json           # 以JSON格式输出
  %(prog)s --realtime GOOGL                 # 获取谷歌实时行情

美股历史K线、财务报表等功能请使用: stock_us_yfinance.py
        """)

    parser.add_argument("--realtime", type=str, default=None, metavar="SYMBOL",
                        help="获取个股实时行情与估值指标（美股代码，如 AAPL、TSLA、MSFT）")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.realtime:
        parser.print_help()
        print("\n错误: 请指定至少一个操作", file=sys.stderr)
        sys.exit(1)

    if args.realtime:
        cmd_realtime(args.realtime, args.json)


if __name__ == "__main__":
    main()
