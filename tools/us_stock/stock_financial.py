#!/usr/bin/env python3
"""美股财务数据查询工具（yfinance 版本）。

本模块位于 tools/us_stock/ 目录下，专门用于获取美股上市公司的
财务报表与额外财务数据，是美股数据工具集的财务分析入口。

使用 yfinance 库获取美股上市公司的财务数据。

功能模块：
1. 完整财务报表（年度/季度利润表、资产负债表、现金流量表）
2. 分红拆股历史（分红记录、拆股记录）
3. 机构持仓（机构持股数据）
4. 分析师评级（推荐评级）

数据来源：
- Yahoo Finance（yfinance 库）

优势：
- 免费、无需 token、无需积分
- 底层接口稳定，时区处理专业
- 比 akshare 封装更原生

Usage:
    {py} tools/us_stock/stock_financial.py --financials AAPL
    {py} tools/us_stock/stock_financial.py --dividends AAPL
    {py} tools/us_stock/stock_financial.py --holders AAPL
    {py} tools/us_stock/stock_financial.py --analyst AAPL
    {py} tools/us_stock/stock_financial.py --all AAPL --json
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
        "meta": {"tool": "stock_financial", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

try:
    import pandas as pd
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 pandas 库: {e}。请运行: pip install pandas",
        "meta": {"tool": "stock_financial", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# 导入本地缓存模块（tools/common/us_stock_cache.py）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.common import us_stock_cache  # noqa: E402 - 需在 sys.path 设置之后导入


# ---------------------------------------------------------------------------
# 重试机制
# ---------------------------------------------------------------------------

def safe_api_call(func, api_name: str, max_retries: int = 3, delay: float = 2.0) -> Any:
    """安全的API调用封装，支持重试机制。

    Args:
        func: API调用函数。
        api_name: API接口名称（用于日志）。
        max_retries: 最大重试次数。
        delay: 重试间隔秒数。

    Returns:
        API调用结果。

    Raises:
        Exception: 重试次数耗尽后抛出异常。
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
                print(f"⚠ 尝试 {attempt + 1}/{max_retries} 失败 - {error_type},"
                      f" 等待 {delay} 秒后重试...", file=sys.stderr)
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

def get_stock_financial_statements(symbol: str) -> Dict[str, Any]:
    """获取个股完整财务报表（优先本地缓存）。

    包括：年度/季度利润表、年度/季度资产负债表、年度/季度现金流量表。
    功能逻辑与原 stock_us_yfinance.py 中 get_stock_financial_statements 相同；
    数据经 tools/common/us_stock_cache.py 本地缓存，yfinance 限流时降级返回。

    Args:
        symbol: 美股代码，如 "AAPL"。

    Returns:
        dict: 包含完整财务数据的字典。
    """
    print(f"正在获取美股财务数据 - 代码: {symbol}", file=sys.stderr)

    result = {
        "success": True,
        "symbol": symbol,
        "data": {},
        "meta": {
            "tool": "stock_financial",
            "api": "yf.Ticker.*",
            "cache": "unknown",
            "timestamp": datetime.now().isoformat()
        }
    }

    data = us_stock_cache.get_financial_statements(symbol)
    result["meta"]["cache"] = us_stock_cache.get_financial_status()
    if data is None:
        result["success"] = False
        result["error"] = "获取美股财务报表失败（yfinance 不可用且无本地缓存）"
        return result
    result["data"] = data

    return result


def get_stock_dividends_splits(symbol: str) -> Dict[str, Any]:
    """获取个股分红拆股历史（优先本地缓存）。

    包括：分红历史记录、拆股历史记录。
    功能逻辑与原 stock_us_yfinance.py 中 get_stock_extra_data 的
    分红与拆股部分相同；数据经 tools/common/us_stock_cache.py 本地缓存。

    Args:
        symbol: 美股代码，如 "AAPL"。

    Returns:
        dict: 包含分红拆股历史数据的字典。
    """
    print(f"正在获取美股分红拆股历史 - 代码: {symbol}", file=sys.stderr)

    result = {
        "success": True,
        "symbol": symbol,
        "data": {},
        "meta": {
            "tool": "stock_financial",
            "api": "yf.Ticker.dividends/splits",
            "cache": "unknown",
            "timestamp": datetime.now().isoformat()
        }
    }

    data = us_stock_cache.get_dividends_splits(symbol)
    result["meta"]["cache"] = us_stock_cache.get_financial_status()
    if data is None:
        result["success"] = False
        result["error"] = "获取美股分红拆股失败（yfinance 不可用且无本地缓存）"
        return result
    result["data"] = data

    return result


def get_stock_holders(symbol: str) -> Dict[str, Any]:
    """获取个股机构持仓数据。

    功能逻辑与原 stock_us_yfinance.py 中 get_stock_extra_data 的
    机构持股部分相同。

    Args:
        symbol: 美股代码，如 "AAPL"。

    Returns:
        dict: 包含机构持仓数据的字典。
    """
    print(f"正在获取美股机构持仓 - 代码: {symbol}", file=sys.stderr)

    result = {
        "success": True,
        "symbol": symbol,
        "data": {},
        "meta": {
            "tool": "stock_financial",
            "api": "yf.Ticker.institutional_holders",
            "timestamp": datetime.now().isoformat()
        }
    }

    try:
        # 实例化股票对象
        api_name = f"yf.Ticker('{symbol}')"
        stock = safe_api_call(lambda: yf.Ticker(symbol), api_name)

        # 机构持股
        try:
            print("  获取机构持股...", file=sys.stderr)
            api_name = "stock.institutional_holders"
            holders = safe_api_call(
                lambda: stock.institutional_holders, api_name)

            if holders is not None and not holders.empty:
                result["data"]["机构持股"] = {
                    "count": len(holders),
                    "top_holder": holders.iloc[0].to_dict() if len(holders) > 0 else None
                }
                print(f"    ✓ 获取成功，机构数: {len(holders)}", file=sys.stderr)
            else:
                result["data"]["机构持股"] = {"count": 0, "note": "无机构持股数据"}
        except Exception as e:
            result["data"]["机构持股"] = {"error": str(e)}

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


def get_stock_analyst_ratings(symbol: str) -> Dict[str, Any]:
    """获取个股分析师评级数据。

    功能逻辑与原 stock_us_yfinance.py 中 get_stock_extra_data 的
    分析师评级部分相同。

    Args:
        symbol: 美股代码，如 "AAPL"。

    Returns:
        dict: 包含分析师评级数据的字典。
    """
    print(f"正在获取美股分析师评级 - 代码: {symbol}", file=sys.stderr)

    result = {
        "success": True,
        "symbol": symbol,
        "data": {},
        "meta": {
            "tool": "stock_financial",
            "api": "yf.Ticker.recommendations",
            "timestamp": datetime.now().isoformat()
        }
    }

    try:
        # 实例化股票对象
        api_name = f"yf.Ticker('{symbol}')"
        stock = safe_api_call(lambda: yf.Ticker(symbol), api_name)

        # 分析师评级
        try:
            print("  获取分析师评级...", file=sys.stderr)
            api_name = "stock.recommendations"
            recommendations = safe_api_call(
                lambda: stock.recommendations, api_name)

            if recommendations is not None and not recommendations.empty:
                result["data"]["分析师评级"] = {
                    "count": len(recommendations),
                    "latest": recommendations.iloc[-1].to_dict()
                    if len(recommendations) > 0 else None
                }
                print(f"    ✓ 获取成功，评级数: {len(recommendations)}", file=sys.stderr)
            else:
                result["data"]["分析师评级"] = {"count": 0, "note": "无分析师评级数据"}
        except Exception as e:
            result["data"]["分析师评级"] = {"error": str(e)}

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

def main():
    """主程序入口。"""
    parser = argparse.ArgumentParser(
        description="美股财务数据查询工具（yfinance 版本）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    {py} tools/us_stock/stock_financial.py --financials AAPL
    {py} tools/us_stock/stock_financial.py --dividends AAPL
    {py} tools/us_stock/stock_financial.py --holders AAPL
    {py} tools/us_stock/stock_financial.py --analyst AAPL
    {py} tools/us_stock/stock_financial.py --all AAPL --json
        """
    )

    parser.add_argument("--financials", type=str,
                        help="获取个股完整财务报表（美股代码，如 AAPL、MSFT）")
    parser.add_argument("--dividends", type=str,
                        help="获取个股分红拆股历史（美股代码）")
    parser.add_argument("--holders", type=str,
                        help="获取个股机构持仓（美股代码）")
    parser.add_argument("--analyst", type=str,
                        help="获取个股分析师评级（美股代码）")
    parser.add_argument("--all", type=str,
                        help="获取所有财务数据（美股代码）")
    parser.add_argument("--json", action="store_true",
                        help="以JSON格式输出")

    args = parser.parse_args()

    # 如果没有提供任何参数，显示帮助信息
    if not any([args.financials, args.dividends, args.holders,
                args.analyst, args.all]):
        parser.print_help()
        sys.exit(0)

    # 设置输出格式
    output_json = args.json

    try:
        # 1. 获取财务报表
        if args.financials or args.all:
            symbol = args.financials or args.all
            result = get_stock_financial_statements(symbol)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"\n【{symbol} 财务数据】")
                for name, data in result.get("data", {}).items():
                    if "error" in data:
                        print(f"  {name}: ✗ {data['error']}")
                    else:
                        print(f"  {name}: ✓ 科目数 {data.get('count', 0)}")

        # 2. 获取分红拆股历史
        if args.dividends or args.all:
            symbol = args.dividends or args.all
            result = get_stock_dividends_splits(symbol)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"\n【{symbol} 分红拆股历史】")
                for name, data in result.get("data", {}).items():
                    if "error" in data:
                        print(f"  {name}: ✗ {data['error']}")
                    elif "note" in data:
                        print(f"  {name}: {data['note']}")
                    else:
                        print(f"  {name}: ✓ 记录数 {data.get('count', 0)}")

        # 3. 获取机构持仓
        if args.holders or args.all:
            symbol = args.holders or args.all
            result = get_stock_holders(symbol)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"\n【{symbol} 机构持仓】")
                for name, data in result.get("data", {}).items():
                    if "error" in data:
                        print(f"  {name}: ✗ {data['error']}")
                    elif "note" in data:
                        print(f"  {name}: {data['note']}")
                    else:
                        print(f"  {name}: ✓ 记录数 {data.get('count', 0)}")

        # 4. 获取分析师评级
        if args.analyst or args.all:
            symbol = args.analyst or args.all
            result = get_stock_analyst_ratings(symbol)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"\n【{symbol} 分析师评级】")
                for name, data in result.get("data", {}).items():
                    if "error" in data:
                        print(f"  {name}: ✗ {data['error']}")
                    elif "note" in data:
                        print(f"  {name}: {data['note']}")
                    else:
                        print(f"  {name}: ✓ 记录数 {data.get('count', 0)}")

    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "meta": {"tool": "stock_financial", "timestamp": datetime.now().isoformat()}
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
