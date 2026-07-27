#!/usr/bin/env python3
"""美股股票信息查询工具（yfinance 版本）。

使用 yfinance 库获取美股上市公司的实时行情、历史K线、财务数据等信息。

数据来源：
- Yahoo Finance（实时行情、历史K线、财务数据）

功能模块：
1. 个股实时行情与估值指标获取
2. 美股三大指数历史日线（纳斯达克、道琼斯、标普500）
3. 个股历史K线数据（自动前复权）
4. 完整财务报表（利润表、资产负债表、现金流量表）
5. 分红拆股、机构持仓、分析师评级

优势：
- 免费、无需 token、无需积分
- 底层接口稳定，时区处理专业
- 比 akshare 封装更原生

Usage:
    {py} tools/stock_us_yfinance.py --realtime AAPL
    {py} tools/stock_us_yfinance.py --index
    {py} tools/stock_us_yfinance.py --daily AAPL --start 2025-01-01 --end 2026-07-27
    {py} tools/stock_us_yfinance.py --financial AAPL
    {py} tools/stock_us_yfinance.py --extra AAPL
"""

import argparse
import json
import sys
import time
import traceback
import warnings
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

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
        "meta": {"tool": "stock_us_yfinance", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

try:
    import pandas as pd
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 pandas 库: {e}。请运行: pip install pandas",
        "meta": {"tool": "stock_us_yfinance", "timestamp": datetime.now().isoformat()}
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
                "meta": {"tool": "stock_us_yfinance", "timestamp": datetime.now().isoformat()}
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
                "tool": "stock_us_yfinance",
                "api": "yf.Ticker.info",
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "meta": {"tool": "stock_us_yfinance", "timestamp": datetime.now().isoformat()}
        }


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
            "tool": "stock_us_yfinance",
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
                "meta": {"tool": "stock_us_yfinance", "timestamp": datetime.now().isoformat()}
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
                "tool": "stock_us_yfinance",
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
            "meta": {"tool": "stock_us_yfinance", "timestamp": datetime.now().isoformat()}
        }


def get_stock_financial_statements(symbol: str) -> Dict[str, Any]:
    """获取个股完整财务报表。

    包括：年度/季度利润表、年度/季度资产负债表、年度/季度现金流量表

    Args:
        symbol: 美股代码，如 "AAPL"

    Returns:
        dict: 包含完整财务数据的字典
    """
    print(f"正在获取美股财务数据 - 代码: {symbol}", file=sys.stderr)
    
    result = {
        "success": True,
        "symbol": symbol,
        "data": {},
        "meta": {
            "tool": "stock_us_yfinance",
            "api": "yf.Ticker.*",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    try:
        # 实例化股票对象
        api_name = f"yf.Ticker('{symbol}')"
        stock = safe_api_call(lambda: yf.Ticker(symbol), api_name)
        
        # 1. 年度利润表
        try:
            print("  获取年度利润表...", file=sys.stderr)
            api_name = "stock.income_stmt"
            income_year = safe_api_call(lambda: stock.income_stmt, api_name)
            
            if income_year is not None and not income_year.empty:
                result["data"]["年度利润表"] = {
                    "count": len(income_year),
                    "columns": list(income_year.columns),
                    "index": list(income_year.index)[:10]  # 只取前10个科目
                }
                print(f"    ✓ 获取成功，科目数: {len(income_year)}", file=sys.stderr)
            else:
                result["data"]["年度利润表"] = {"count": 0, "error": "未获取到数据"}
        except Exception as e:
            result["data"]["年度利润表"] = {"error": str(e)}
            print(f"    ✗ 获取失败: {e}", file=sys.stderr)
        
        # 2. 季度利润表
        try:
            print("  获取季度利润表...", file=sys.stderr)
            api_name = "stock.quarterly_income_stmt"
            income_qtr = safe_api_call(lambda: stock.quarterly_income_stmt, api_name)
            
            if income_qtr is not None and not income_qtr.empty:
                result["data"]["季度利润表"] = {"count": len(income_qtr)}
                print(f"    ✓ 获取成功，科目数: {len(income_qtr)}", file=sys.stderr)
            else:
                result["data"]["季度利润表"] = {"count": 0, "error": "未获取到数据"}
        except Exception as e:
            result["data"]["季度利润表"] = {"error": str(e)}
        
        # 3. 年度资产负债表
        try:
            print("  获取年度资产负债表...", file=sys.stderr)
            api_name = "stock.balance_sheet"
            balance_year = safe_api_call(lambda: stock.balance_sheet, api_name)
            
            if balance_year is not None and not balance_year.empty:
                result["data"]["年度资产负债表"] = {
                    "count": len(balance_year),
                    "columns": list(balance_year.columns),
                    "index": list(balance_year.index)[:10]
                }
                print(f"    ✓ 获取成功，科目数: {len(balance_year)}", file=sys.stderr)
            else:
                result["data"]["年度资产负债表"] = {"count": 0, "error": "未获取到数据"}
        except Exception as e:
            result["data"]["年度资产负债表"] = {"error": str(e)}
        
        # 4. 季度资产负债表
        try:
            print("  获取季度资产负债表...", file=sys.stderr)
            api_name = "stock.quarterly_balance_sheet"
            balance_qtr = safe_api_call(lambda: stock.quarterly_balance_sheet, api_name)
            
            if balance_qtr is not None and not balance_qtr.empty:
                result["data"]["季度资产负债表"] = {"count": len(balance_qtr)}
                print(f"    ✓ 获取成功", file=sys.stderr)
            else:
                result["data"]["季度资产负债表"] = {"count": 0, "error": "未获取到数据"}
        except Exception as e:
            result["data"]["季度资产负债表"] = {"error": str(e)}
        
        # 5. 年度现金流量表
        try:
            print("  获取年度现金流量表...", file=sys.stderr)
            api_name = "stock.cashflow"
            cash_year = safe_api_call(lambda: stock.cashflow, api_name)
            
            if cash_year is not None and not cash_year.empty:
                result["data"]["年度现金流量表"] = {
                    "count": len(cash_year),
                    "columns": list(cash_year.columns),
                    "index": list(cash_year.index)[:10]
                }
                print(f"    ✓ 获取成功，科目数: {len(cash_year)}", file=sys.stderr)
            else:
                result["data"]["年度现金流量表"] = {"count": 0, "error": "未获取到数据"}
        except Exception as e:
            result["data"]["年度现金流量表"] = {"error": str(e)}
        
        # 6. 季度现金流量表
        try:
            print("  获取季度现金流量表...", file=sys.stderr)
            api_name = "stock.quarterly_cashflow"
            cash_qtr = safe_api_call(lambda: stock.quarterly_cashflow, api_name)
            
            if cash_qtr is not None and not cash_qtr.empty:
                result["data"]["季度现金流量表"] = {"count": len(cash_qtr)}
                print(f"    ✓ 获取成功", file=sys.stderr)
            else:
                result["data"]["季度现金流量表"] = {"count": 0, "error": "未获取到数据"}
        except Exception as e:
            result["data"]["季度现金流量表"] = {"error": str(e)}
        
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
    
    return result


def get_stock_extra_data(symbol: str) -> Dict[str, Any]:
    """获取个股额外财务数据。

    包括：分红历史、拆股历史、机构持股、分析师评级

    Args:
        symbol: 美股代码，如 "AAPL"

    Returns:
        dict: 包含额外财务数据的字典
    """
    print(f"正在获取美股额外数据 - 代码: {symbol}", file=sys.stderr)
    
    result = {
        "success": True,
        "symbol": symbol,
        "data": {},
        "meta": {
            "tool": "stock_us_yfinance",
            "api": "yf.Ticker.*",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    try:
        # 实例化股票对象
        api_name = f"yf.Ticker('{symbol}')"
        stock = safe_api_call(lambda: yf.Ticker(symbol), api_name)
        
        # 1. 分红历史
        try:
            print("  获取分红历史...", file=sys.stderr)
            api_name = "stock.dividends"
            div_df = safe_api_call(lambda: stock.dividends, api_name)
            
            if div_df is not None and not div_df.empty:
                result["data"]["分红历史"] = {
                    "count": len(div_df),
                    "latest": div_df.iloc[-1] if len(div_df) > 0 else None,
                    "total_years": len(div_df.resample('YE').count())
                }
                print(f"    ✓ 获取成功，分红次数: {len(div_df)}", file=sys.stderr)
            else:
                result["data"]["分红历史"] = {"count": 0, "note": "无分红记录"}
        except Exception as e:
            result["data"]["分红历史"] = {"error": str(e)}
        
        # 2. 拆股历史
        try:
            print("  获取拆股历史...", file=sys.stderr)
            api_name = "stock.splits"
            split_df = safe_api_call(lambda: stock.splits, api_name)
            
            if split_df is not None and not split_df.empty:
                result["data"]["拆股历史"] = {
                    "count": len(split_df),
                    "latest": split_df.iloc[-1] if len(split_df) > 0 else None
                }
                print(f"    ✓ 获取成功，拆股次数: {len(split_df)}", file=sys.stderr)
            else:
                result["data"]["拆股历史"] = {"count": 0, "note": "无拆股记录"}
        except Exception as e:
            result["data"]["拆股历史"] = {"error": str(e)}
        
        # 3. 机构持股
        try:
            print("  获取机构持股...", file=sys.stderr)
            api_name = "stock.institutional_holders"
            holders = safe_api_call(lambda: stock.institutional_holders, api_name)
            
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
        
        # 4. 分析师评级
        try:
            print("  获取分析师评级...", file=sys.stderr)
            api_name = "stock.recommendations"
            recommendations = safe_api_call(lambda: stock.recommendations, api_name)
            
            if recommendations is not None and not recommendations.empty:
                result["data"]["分析师评级"] = {
                    "count": len(recommendations),
                    "latest": recommendations.iloc[-1].to_dict() if len(recommendations) > 0 else None
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
        description="美股股票信息查询工具（yfinance 版本）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    {py} tools/stock_us_yfinance.py --realtime AAPL
    {py} tools/stock_us_yfinance.py --index
    {py} tools/stock_us_yfinance.py --daily AAPL --start 2025-01-01 --end 2026-07-27
    {py} tools/stock_us_yfinance.py --financial AAPL
    {py} tools/stock_us_yfinance.py --extra AAPL
    {py} tools/stock_us_yfinance.py --all AAPL
        """
    )
    
    parser.add_argument("--realtime", type=str, help="获取个股实时行情（美股代码，如 AAPL、TSLA、MSFT）")
    parser.add_argument("--index", action="store_true", help="获取美股三大指数历史日线")
    parser.add_argument("--daily", type=str, help="获取个股历史K线（美股代码）")
    parser.add_argument("--financial", type=str, help="获取个股完整财务报表（美股代码）")
    parser.add_argument("--extra", type=str, help="获取个股额外数据（分红、机构、评级）")
    parser.add_argument("--all", type=str, help="获取所有数据（美股代码）")
    parser.add_argument("--start", type=str, help="开始日期（格式：YYYY-MM-DD，默认一年前）")
    parser.add_argument("--end", type=str, help="结束日期（格式：YYYY-MM-DD，默认今天）")
    parser.add_argument("--no-adjust", action="store_true", help="不复权（默认前复权）")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出")
    
    args = parser.parse_args()
    
    # 如果没有提供任何参数，显示帮助信息
    if not any([args.realtime, args.index, args.daily, args.financial, args.extra, args.all]):
        parser.print_help()
        sys.exit(0)
    
    # 设置输出格式
    output_json = args.json
    auto_adjust = not args.no_adjust
    
    try:
        # 1. 获取实时行情
        if args.realtime or args.all:
            symbol = args.realtime or args.all
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
        
        # 2. 获取三大指数
        if args.index or args.all:
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
        
        # 3. 获取历史K线
        if args.daily or args.all:
            symbol = args.daily or args.all
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
        
        # 4. 获取财务数据
        if args.financial or args.all:
            symbol = args.financial or args.all
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
        
        # 5. 获取额外数据
        if args.extra or args.all:
            symbol = args.extra or args.all
            result = get_stock_extra_data(symbol)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"\n【{symbol} 额外数据】")
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
            "meta": {"tool": "stock_us_yfinance", "timestamp": datetime.now().isoformat()}
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()