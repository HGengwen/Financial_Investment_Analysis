#!/usr/bin/env python3
"""美股股票信息查询工具。

使用 akshare 库获取美股上市公司的实时行情、历史K线等信息。

数据来源：
- 东方财富（实时行情、历史K线）

功能模块：
1. 个股实时行情获取
2. 美股三大指数历史日线（纳斯达克、道琼斯、标普500）
3. 个股历史日线K线数据（前复权）

Usage:
    {py} tools/stock_info_us.py --realtime AAPL
    {py} tools/stock_info_us.py --index
    {py} tools/stock_info_us.py --daily AAPL --start 20250101 --end 20260727
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timedelta

try:
    import pandas as pd
except ImportError:
    pd = None

# ---------------------------------------------------------------------------
# 尝试导入 akshare（提供友好的错误提示）
# ---------------------------------------------------------------------------
try:
    import akshare as ak
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 akshare 库: {e}。请运行: pip install akshare",
        "meta": {"tool": "stock_info_us", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)


# ---------------------------------------------------------------------------
# 股票代码映射缓存
# ---------------------------------------------------------------------------
_CODE_MAPPING_CACHE = None


def get_code_mapping():
    """获取美股代码与东方财富内部代码的映射关系。

    Returns:
        dict: {标准代码: 东方财富代码} 映射字典
    """
    global _CODE_MAPPING_CACHE
    
    if _CODE_MAPPING_CACHE is not None:
        return _CODE_MAPPING_CACHE
    
    print("正在获取美股代码映射表...", file=sys.stderr)
    
    try:
        # 获取所有美股实时行情数据
        df = ak.stock_us_spot_em()
        
        if df is None or df.empty:
            print("⚠ 未获取到美股代码映射数据", file=sys.stderr)
            return {}
        
        # 构建映射字典
        _CODE_MAPPING_CACHE = {}
        
        # 东方财富代码格式：105.AAPL
        for _, row in df.iterrows():
            em_code = row.get("代码", "")
            name = row.get("名称", "")
            
            # 从东方财富代码中提取标准代码
            if "." in str(em_code):
                standard_code = str(em_code).split(".")[-1]
                _CODE_MAPPING_CACHE[standard_code.upper()] = em_code
        
        print(f"✓ 已缓存 {len(_CODE_MAPPING_CACHE)} 个美股代码映射", file=sys.stderr)
        return _CODE_MAPPING_CACHE
        
    except Exception as e:
        print(f"⚠ 获取代码映射失败: {e}", file=sys.stderr)
        return {}


def standard_to_em_code(standard_code: str) -> str:
    """将标准美股代码转换为东方财富代码格式。

    Args:
        standard_code: 标准美股代码，如 "AAPL"

    Returns:
        str: 东方财富代码，如 "105.AAPL"
    """
    mapping = get_code_mapping()
    em_code = mapping.get(standard_code.upper())
    
    if em_code:
        return em_code
    
    # 如果映射中没有，尝试构造常见格式
    # 东方财富美股代码格式通常为：市场编号.股票代码
    # 常见市场编号：105（纳斯达克）、106（纽交所）
    return f"105.{standard_code.upper()}"


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
                raise Exception(f"获取美股数据失败（已重试{max_retries}次）: {e}")
    return None


# ---------------------------------------------------------------------------
# 数据获取函数
# ---------------------------------------------------------------------------

def get_us_realtime_quote(symbol: str) -> dict:
    """获取美股个股实时行情。

    Args:
        symbol: 美股代码，如 "AAPL"、"TSLA"、"MSFT"

    Returns:
        dict: 包含实时行情数据的字典
    """
    print(f"正在获取美股实时行情 - 代码: {symbol}", file=sys.stderr)
    
    try:
        # 获取所有美股实时行情
        api_name = f"ak.stock_us_spot_em()"
        df = safe_api_call(lambda: ak.stock_us_spot_em(), api_name)
        
        if df is None or df.empty:
            return {"success": False, "error": "未获取到数据"}
        
        # 查找指定股票
        em_code = standard_to_em_code(symbol)
        row = df[df["代码"] == em_code]
        
        if row.empty:
            # 尝试直接搜索标准代码
            row = df[df["代码"].str.contains(symbol.upper(), na=False)]
        
        if row.empty:
            return {
                "success": False,
                "error": f"未找到股票代码: {symbol}",
                "symbol": symbol
            }
        
        result = {
            "success": True,
            "symbol": symbol,
            "data": row.iloc[0].to_dict(),
            "meta": {
                "tool": "stock_info_us",
                "api": "stock_us_spot_em",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "meta": {"tool": "stock_info_us", "timestamp": datetime.now().isoformat()}
        }


def get_us_index_daily(start_date: str = None, end_date: str = None) -> dict:
    """获取美股三大指数历史日线数据。

    包括：纳斯达克综合指数(^IXIC)、道琼斯工业指数(^DJI)、标普500指数(^GSPC)

    Args:
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"

    Returns:
        dict: 包含三大指数历史数据的字典
    """
    print("正在获取美股三大指数历史日线", file=sys.stderr)
    
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    
    index_map = {
        "纳斯达克综合指数": "^IXIC",
        "道琼斯工业指数": "^DJI",
        "标普500指数": "^GSPC"
    }
    
    result = {
        "success": True,
        "data": {},
        "meta": {
            "tool": "stock_info_us",
            "api": "stock_us_hist",
            "start_date": start_date,
            "end_date": end_date,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    for name, code in index_map.items():
        try:
            print(f"  获取 {name} ({code})...", file=sys.stderr)
            api_name = f"ak.stock_us_hist(symbol='{code}', period='daily', start_date='{start_date}', end_date='{end_date}')"
            df = safe_api_call(
                lambda: ak.stock_us_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date),
                api_name
            )
            
            if df is not None and not df.empty:
                result["data"][name] = {
                    "code": code,
                    "count": len(df),
                    "latest": df.iloc[-1].to_dict() if len(df) > 0 else {},
                    "columns": list(df.columns)
                }
                print(f"    ✓ 获取成功，数据条数: {len(df)}", file=sys.stderr)
            else:
                result["data"][name] = {"code": code, "count": 0, "error": "未获取到数据"}
                print(f"    ✗ 未获取到数据", file=sys.stderr)
                
        except Exception as e:
            result["data"][name] = {"code": code, "error": str(e)}
            print(f"    ✗ 获取失败: {e}", file=sys.stderr)
    
    return result


def get_us_stock_daily(symbol: str, start_date: str = None, end_date: str = None, adjust: str = "qfq") -> dict:
    """获取美股个股历史日线K线数据。

    Args:
        symbol: 美股代码，如 "AAPL"
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"
        adjust: 复权类型，"qfq"前复权、"hfq"后复权、""不复权

    Returns:
        dict: 包含历史K线数据的字典
    """
    print(f"正在获取美股历史K线 - 代码: {symbol}", file=sys.stderr)
    
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    
    try:
        # 转换为东方财富代码格式
        em_code = standard_to_em_code(symbol)
        
        api_name = f"ak.stock_us_hist(symbol='{em_code}', period='daily', start_date='{start_date}', end_date='{end_date}', adjust='{adjust}')"
        df = safe_api_call(
            lambda: ak.stock_us_hist(symbol=em_code, period="daily", start_date=start_date, end_date=end_date, adjust=adjust),
            api_name
        )
        
        if df is None or df.empty:
            return {
                "success": False,
                "error": "未获取到数据",
                "symbol": symbol,
                "meta": {"tool": "stock_info_us", "timestamp": datetime.now().isoformat()}
            }
        
        return {
            "success": True,
            "symbol": symbol,
            "data": {
                "count": len(df),
                "columns": list(df.columns),
                "latest": df.iloc[-1].to_dict() if len(df) > 0 else {},
                "earliest": df.iloc[0].to_dict() if len(df) > 0 else {}
            },
            "meta": {
                "tool": "stock_info_us",
                "api": "stock_us_hist",
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "meta": {"tool": "stock_info_us", "timestamp": datetime.now().isoformat()}
        }


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

def main():
    """主程序入口。"""
    parser = argparse.ArgumentParser(
        description="美股股票信息查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    {py} tools/stock_info_us.py --realtime AAPL
    {py} tools/stock_info_us.py --index
    {py} tools/stock_info_us.py --daily AAPL --start 20250101 --end 20260727
        """
    )
    
    parser.add_argument("--realtime", type=str, help="获取个股实时行情（美股代码，如 AAPL、TSLA、MSFT）")
    parser.add_argument("--index", action="store_true", help="获取美股三大指数历史日线")
    parser.add_argument("--daily", type=str, help="获取个股历史K线（美股代码）")
    parser.add_argument("--start", type=str, help="开始日期（格式：YYYYMMDD，默认一年前）")
    parser.add_argument("--end", type=str, help="结束日期（格式：YYYYMMDD，默认今天）")
    parser.add_argument("--adjust", type=str, default="qfq", choices=["qfq", "hfq", ""], help="复权类型（qfq前复权/hfq后复权/空不复权，默认qfq）")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出")
    
    args = parser.parse_args()
    
    # 如果没有提供任何参数，显示帮助信息
    if not any([args.realtime, args.index, args.daily]):
        parser.print_help()
        sys.exit(0)
    
    # 设置输出格式
    output_json = args.json
    
    try:
        # 1. 获取实时行情
        if args.realtime:
            result = get_us_realtime_quote(args.realtime)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                if result.get("success"):
                    print(f"\n【{args.realtime} 美股实时行情】")
                    data = result.get("data", {})
                    for key, value in data.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"✗ 获取实时行情失败: {result.get('error')}")
        
        # 2. 获取三大指数
        if args.index:
            result = get_us_index_daily(args.start, args.end)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("\n【美股三大指数历史日线】")
                for name, data in result.get("data", {}).items():
                    if "error" in data:
                        print(f"  {name}: ✗ {data['error']}")
                    else:
                        print(f"  {name}: ✓ 数据条数 {data.get('count', 0)}")
        
        # 3. 获取历史K线
        if args.daily:
            result = get_us_stock_daily(args.daily, args.start, args.end, args.adjust)
            if output_json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                if result.get("success"):
                    print(f"\n【{args.daily} 历史K线】")
                    data = result.get("data", {})
                    print(f"  数据条数: {data.get('count', 0)}")
                    print(f"  列: {', '.join(data.get('columns', []))}")
                    latest = data.get("latest", {})
                    if latest:
                        print(f"  最新数据:")
                        for key, value in latest.items():
                            print(f"    {key}: {value}")
                else:
                    print(f"✗ 获取历史K线失败: {result.get('error')}")
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "meta": {"tool": "stock_info_us", "timestamp": datetime.now().isoformat()}
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()