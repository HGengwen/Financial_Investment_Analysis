#!/usr/bin/env python3
"""美股个股实时行情、估值指标与代码列表查询工具（美股信息查询模块）。

本模块位于 tools/us_stock/ 目录下，用于查询美股上市公司的实时行情、
估值指标，以及通过 NASDAQ 官方列表（本地缓存）进行代码/名称查询。

使用 yfinance 库获取美股上市公司的实时行情、估值指标等信息。

数据来源：
- Yahoo Finance（实时行情、估值指标）
- NASDAQ Trader 官方列表（代码/名称/交易所，经 tools/common/us_stock_cache.py
  本地缓存，TTL 默认 7 天）

功能：
- 获取个股实时行情与估值指标（PE、PB、市值、股息率、Beta、ROE、ROA等）
- --list / --search / --code：基于本地缓存的代码与名称查询
- 限流降级：yfinance 接口失败（HTTP 429/断连）时，估值指标从本地
  慢变字段缓存（TTL 默认 1 天）降级返回

优势：
- 免费、无需 token、无需积分
- 底层接口稳定，时区处理专业

Usage:
    {py} tools/us_stock/stock_info.py --realtime AAPL
    {py} tools/us_stock/stock_info.py --realtime MSFT --json
    {py} tools/us_stock/stock_info.py --list
    {py} tools/us_stock/stock_info.py --search Apple
    {py} tools/us_stock/stock_info.py --code BRK.B
    {py} tools/us_stock/stock_info.py --refresh

美股历史K线、财务报表等功能请使用: tools/stock_us_yfinance.py
"""

import argparse
import json
import os
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
# 导入本地缓存模块（tools/common/us_stock_cache.py）
# ---------------------------------------------------------------------------
# 将项目根目录加入 sys.path，使本工具以独立脚本方式运行时也能导入 tools.common 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.common import us_stock_cache  # noqa: E402 - 需在 sys.path 设置之后导入


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

def _extract_realtime_data(info: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """从 yfinance info 字典中提取关键实时行情与估值指标字段。

    Args:
        info: yf.Ticker(symbol).info 返回的原始字典。
        symbol: 美股代码。

    Returns:
        包含关键字段的字典（键为中文名）。
    """
    return {
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


def _slow_fields_from_info(info: Dict[str, Any]) -> Dict[str, Any]:
    """从 info 字典提取慢变字段子集（供本地缓存）。

    Args:
        info: yf.Ticker(symbol).info 返回的原始字典。

    Returns:
        慢变字段子集（键为中文名）。
    """
    return {
        "公司名称": info.get("longName"),
        "市值": info.get("marketCap"),
        "流通市值": info.get("floatShares"),
        "总股本": info.get("sharesOutstanding"),
        "市盈率TTM": info.get("trailingPE"),
        "市净率PB": info.get("priceToBook"),
        "股息率": info.get("dividendYield"),
        "Beta系数": info.get("beta"),
        "ROE": info.get("returnOnEquity"),
        "ROA": info.get("returnOnAssets"),
        "52周最高": info.get("fiftyTwoWeekHigh"),
        "52周最低": info.get("fiftyTwoWeekLow"),
    }


def get_stock_realtime_info(symbol: str) -> Dict[str, Any]:
    """获取个股实时行情与估值指标。

    正常路径：实时调用 yf.Ticker(symbol).info，成功后顺带刷新慢变字段缓存。
    降级路径：info 调用失败（限流 429/断连，已重试 3 次）时，从本地慢变
    字段缓存取估值指标拼装返回（meta.cache = "stale"），价格字段为 null；
    无缓存可用时才返回失败。

    Args:
        symbol: 美股代码，如 "AAPL"、"TSLA"、"MSFT"

    Returns:
        dict: 包含实时行情和估值指标数据的字典
    """
    print(f"正在获取美股实时行情 - 代码: {symbol}", file=sys.stderr)

    # 尝试实时获取
    try:
        # 实例化股票对象
        api_name = f"yf.Ticker('{symbol}')"
        stock = safe_api_call(lambda: yf.Ticker(symbol), api_name)

        # 获取实时信息
        api_name = "stock.info"
        info = safe_api_call(lambda: stock.info, api_name)

        if info is None:
            raise RuntimeError("未获取到数据")

        realtime_data = _extract_realtime_data(info, symbol)

        # 顺带刷新慢变字段缓存（供后续限流降级使用）
        try:
            us_stock_cache.update_slow_fields(symbol, _slow_fields_from_info(info))
        except Exception:
            # 缓存更新失败不影响主流程
            pass

        return {
            "success": True,
            "symbol": symbol,
            "data": realtime_data,
            "raw_info": info,  # 保留原始数据
            "meta": {
                "tool": "stock_info",
                "api": "yf.Ticker.info",
                "cache": "hit",
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        # 降级路径：尝试从慢变字段缓存恢复估值指标
        slow_fields = us_stock_cache.get_slow_fields(symbol)
        if slow_fields is not None:
            data = {
                "股票代码": symbol,
                "公司名称": slow_fields.get("公司名称"),
                "当前价格": None,
                "开盘价": None,
                "最高价": None,
                "最低价": None,
                "昨日收盘价": None,
                "成交量": None,
                "市值": slow_fields.get("市值"),
                "市盈率TTM": slow_fields.get("市盈率TTM"),
                "市净率PB": slow_fields.get("市净率PB"),
                "52周最高": slow_fields.get("52周最高"),
                "52周最低": slow_fields.get("52周最低"),
                "股息率": slow_fields.get("股息率"),
                "Beta系数": slow_fields.get("Beta系数"),
                "ROE": slow_fields.get("ROE"),
                "ROA": slow_fields.get("ROA"),
                "流通市值": slow_fields.get("流通市值"),
                "总股本": slow_fields.get("总股本"),
            }
            return {
                "success": True,
                "symbol": symbol,
                "data": data,
                "meta": {
                    "tool": "stock_info",
                    "api": "cache_degraded",
                    "cache": "stale",
                    "note": "yfinance 实时接口暂不可用，估值指标来自本地缓存（价格字段为空）",
                    "timestamp": datetime.now().isoformat()
                }
            }

        # 无缓存可用时返回失败
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


def cmd_list(output_json: bool = False) -> None:
    """--list: 列出全部美股代码与名称。

    Args:
        output_json: 是否以 JSON 格式输出。
    """
    try:
        stocks = us_stock_cache.get_us_code_name_list()
        output = {
            "success": True,
            "data": stocks,
            "meta": {
                "tool": "stock_info",
                "command": "list",
                "market": "us",
                "count": len(stocks),
                "cache": us_stock_cache.get_us_code_name_status(),
                "timestamp": datetime.now().isoformat()
            }
        }
        if output_json:
            print(json.dumps(output, ensure_ascii=False))
        else:
            print(f"\n【美股代码列表（共 {len(stocks)} 只）】")
            for s in stocks[:20]:
                print(f"  {s['symbol']:>10}  {s['name']}")
            if len(stocks) > 20:
                print(f"  ... 共 {len(stocks)} 只，使用 --list --json 查看全部")
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"获取美股列表失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "list", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_search(keyword: str, output_json: bool = False) -> None:
    """--search: 按代码或名称关键词搜索美股。

    Args:
        keyword: 搜索关键词（支持代码/名称）。
        output_json: 是否以 JSON 格式输出。
    """
    if not keyword:
        print(json.dumps({
            "success": False,
            "error": "请提供搜索关键词，例如: --search Apple",
            "meta": {"tool": "stock_info", "command": "search", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        matched = us_stock_cache.search_us_stocks(keyword)
        output = {
            "success": True,
            "data": matched,
            "meta": {
                "tool": "stock_info",
                "command": "search",
                "keyword": keyword,
                "market": "us",
                "count": len(matched),
                "cache": us_stock_cache.get_us_code_name_status(),
                "timestamp": datetime.now().isoformat()
            }
        }
        if output_json:
            print(json.dumps(output, ensure_ascii=False))
        else:
            print(f"\n【搜索美股: {keyword}】共 {len(matched)} 条匹配")
            for s in matched[:20]:
                print(f"  {s['symbol']:>10}  {s['name']}")
            if len(matched) > 20:
                print(f"  ... 共 {len(matched)} 条，使用 --search {keyword} --json 查看全部")
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"搜索失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "search", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_code(symbol: str, output_json: bool = False) -> None:
    """--code: 查询单只美股代码与名称（含交易所信息）。

    Args:
        symbol: 美股代码，如 "AAPL"、"BRK.B"。
        output_json: 是否以 JSON 格式输出。
    """
    if not symbol:
        print(json.dumps({
            "success": False,
            "error": "请提供美股代码，例如: --code AAPL",
            "meta": {"tool": "stock_info", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        symbol_upper = symbol.strip().upper()
        stocks = us_stock_cache.get_us_code_name_list()
        found = [s for s in stocks if s["symbol"].upper() == symbol_upper]
        if found:
            output = {
                "success": True,
                "data": found[0],
                "meta": {
                    "tool": "stock_info",
                    "command": "code",
                    "symbol": symbol_upper,
                    "market": "us",
                    "cache": us_stock_cache.get_us_code_name_status(),
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            output = {
                "success": False,
                "error": f"未找到美股代码 {symbol_upper}",
                "meta": {
                    "tool": "stock_info",
                    "command": "code",
                    "symbol": symbol_upper,
                    "market": "us",
                    "timestamp": datetime.now().isoformat()
                }
            }
        if output_json or not output["success"]:
            print(json.dumps(output, ensure_ascii=False))
        else:
            print(f"\n【美股代码查询】")
            for key, value in output["data"].items():
                print(f"  {key}: {value}")
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"查询失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_refresh(output_json: bool = False) -> None:
    """--refresh: 强制刷新本地美股列表缓存。

    Args:
        output_json: 是否以 JSON 格式输出。
    """
    try:
        us_stock_cache.get_us_code_name_list(force_refresh=True)
        output = {
            "success": True,
            "data": {"cache": us_stock_cache.get_us_code_name_status()},
            "meta": {
                "tool": "stock_info",
                "command": "refresh",
                "market": "us",
                "timestamp": datetime.now().isoformat()
            }
        }
        if output_json:
            print(json.dumps(output, ensure_ascii=False))
        else:
            print(f"\n【美股列表缓存刷新完成】状态: {output['data']['cache']}")
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"刷新失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "refresh", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """主程序入口。"""
    parser = argparse.ArgumentParser(
        description="美股个股实时行情、估值指标与代码列表查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --realtime AAPL                  # 获取苹果实时行情
  %(prog)s --realtime MSFT --json           # 以JSON格式输出
  %(prog)s --list                           # 列出全部美股（本地缓存）
  %(prog)s --search Apple                   # 按名称搜索美股
  %(prog)s --code BRK.B                     # 查询单只美股代码信息
  %(prog)s --refresh                        # 强制刷新本地列表缓存

美股历史K线、财务报表等功能请使用: stock_us_yfinance.py
        """)

    parser.add_argument("--realtime", type=str, default=None, metavar="SYMBOL",
                        help="获取个股实时行情与估值指标（美股代码，如 AAPL、TSLA、MSFT）")
    parser.add_argument("--list", action="store_true", help="列出全部美股代码与名称")
    parser.add_argument("--search", type=str, default=None, metavar="KEYWORD",
                        help="按代码或名称关键词搜索美股")
    parser.add_argument("--code", type=str, default=None, metavar="SYMBOL",
                        help="查询单只美股代码与名称（如 AAPL、BRK.B）")
    parser.add_argument("--refresh", action="store_true", help="强制刷新本地美股列表缓存")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.realtime and not args.list and not args.search and not args.code and not args.refresh:
        parser.print_help()
        print("\n错误: 请指定至少一个操作", file=sys.stderr)
        sys.exit(1)

    if args.realtime:
        cmd_realtime(args.realtime, args.json)
    elif args.list:
        cmd_list(args.json)
    elif args.search:
        cmd_search(args.search, args.json)
    elif args.code:
        cmd_code(args.code, args.json)
    elif args.refresh:
        cmd_refresh(args.json)


if __name__ == "__main__":
    main()
