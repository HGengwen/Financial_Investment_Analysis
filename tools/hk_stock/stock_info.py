#!/usr/bin/env python3
"""港股股票信息查询工具（港股信息查询模块）。

本模块位于 tools/hk_stock/ 目录下，专门用于查询港股上市公司的
代码、名称、实时行情、热度榜等信息，是港股数据工具集的核心查询入口。

使用 akshare 库获取港股上市公司的代码、名称、实时行情等信息。

改进说明：
1. 增加重试机制（最多3次重试）
2. 增加延迟机制（避免频繁请求）
3. 优化错误处理和日志输出
4. 支持东方财富和新浪两种数据源
5. 代码/名称列表本地缓存（data/hk_stock/stock_code.csv，TTL 默认 7 天），
   搜索支持中英文名称双匹配，避免每次查询重复拉取全量列表

Usage:
    {py} tools/hk_stock/stock_info.py --list
    {py} tools/hk_stock/stock_info.py --search 腾讯
    {py} tools/hk_stock/stock_info.py --search Tencent
    {py} tools/hk_stock/stock_info.py --code 00700
    {py} tools/hk_stock/stock_info.py --hot
    {py} tools/hk_stock/stock_info.py --refresh

财务指标查询请使用: tools/hk_stock/stock_financial.py
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime

# ---------------------------------------------------------------------------
# 尝试导入 akshare（提供友好的错误提示）
# ---------------------------------------------------------------------------
try:
    import akshare as ak
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 akshare 库: {e}。请运行: pip install akshare",
        "meta": {"tool": "stock_info_hk", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# ---------------------------------------------------------------------------
# 导入本地缓存模块（tools/common/hk_stock_cache.py）
# ---------------------------------------------------------------------------
# 将项目根目录加入 sys.path，使本工具以独立脚本方式运行时也能导入 tools.common 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.common import hk_stock_cache  # noqa: E402 - 需在 sys.path 设置之后导入

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

def get_all_hk_stocks():
    """获取全部港股代码和名称。

    优先从本地缓存读取（data/hk_stock/stock_code.csv，TTL 默认 7 天），
    缓存缺失或过期时自动通过 hk_stock_cache 刷新（新浪主源 → 东财备源
    → 硬编码兜底列表），避免每次查询都调用 akshare 拉取全量列表。

    Returns:
        list: 包含港股代码和名称的列表
    """
    return hk_stock_cache.get_hk_code_name_list()


def get_hk_stock_info(code: str) -> dict:
    """获取单只港股基本信息和实时行情。

    行情数据实时拉取一次全市场 spot（不缓存，保持实时性），
    按代码在结果中提取单只股票。

    Args:
        code: 港股代码（5位数字字符串，如"00700"）

    Returns:
        dict: 包含港股基本信息和实时行情的字典；未找到时返回 None
    """
    try:
        df = hk_stock_cache.get_hk_spot_dataframe()
        row = hk_stock_cache.get_hk_spot_row(df, code)

        if row is None:
            return None

        # 动态获取字段值（支持多种字段名，兼容新浪/东财列名差异）
        def get_field(row, *field_names):
            """从多可能字段名中获取值"""
            for field in field_names:
                if field in row.index:
                    return row.get(field)
            return None

        name = get_field(row, '中文名称', '名称', 'name', '股票简称')
        price = get_field(row, '最新价', 'price', 'close')
        change_pct = get_field(row, '涨跌幅', 'change_pct', '涨跌幅(%)')
        change = get_field(row, '涨跌额', 'change', '涨跌')
        volume = get_field(row, '成交量', 'volume')
        amount = get_field(row, '成交额', 'amount', '成交金额')
        high = get_field(row, '最高', 'high')
        low = get_field(row, '最低', 'low')
        open_price = get_field(row, '今开', 'open', '开盘价')
        pre_close = get_field(row, '昨收', 'pre_close', '昨日收盘价')

        return {
            "code": code,
            "name": str(name).strip() if name else "",
            "market": "hk",
            "price": float(price) if price else None,
            "change_pct": float(change_pct) if change_pct else None,
            "change": float(change) if change else None,
            "volume": float(volume) if volume else None,
            "amount": float(amount) if amount else None,
            "high": float(high) if high else None,
            "low": float(low) if low else None,
            "open": float(open_price) if open_price else None,
            "pre_close": float(pre_close) if pre_close else None,
        }
    except Exception as e:
        raise Exception(f"获取港股信息失败: {e}")


def get_hk_hot_stocks():
    """获取港股人气热度榜。

    Returns:
        list: 包含热门港股的列表
    """
    try:
        df = ak.stock_hk_hot_rank_em()
        records = []
        for _, row in df.iterrows():
            records.append({
                "rank": int(row.get("序号", 0)) if row.get("序号") else None,
                "code": str(row.get("代码", "")).strip(),
                "name": str(row.get("股票名称", "")).strip(),
                "price": float(row.get("最新价", 0)) if row.get("最新价") else None,
                "change_pct": float(row.get("涨跌幅", 0)) if row.get("涨跌幅") else None,
            })
        return records
    except Exception as e:
        raise Exception(f"获取港股热度榜失败: {e}")


# ---------------------------------------------------------------------------
# CLI 处理逻辑
# ---------------------------------------------------------------------------

def cmd_list():
    """--list: 列出全部港股。"""
    try:
        records = get_all_hk_stocks()
        output = {
            "success": True,
            "data": records,
            "meta": {
                "tool": "stock_info_hk",
                "command": "list",
                "market": "hk",
                "count": len(records),
                "cache": hk_stock_cache.get_hk_code_name_status(),
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info_hk", "command": "list", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_search(keyword):
    """--search: 按名称关键词搜索港股。

    搜索流程：从本地缓存获取全部港股列表 → 中英文名称双匹配关键词
    → 一次实时拉取全市场 spot 行情 → 提取所有匹配股票的行情数据。
    从原有的「1 + N 次全量 spot 拉取」优化为「1 次」（N 为匹配数量）。
    """
    if not keyword:
        print(json.dumps({
            "success": False,
            "error": "请提供搜索关键词，例如: --search 腾讯",
            "meta": {"tool": "stock_info_hk", "command": "search", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        # 1. 从本地缓存获取全部港股列表（不触发全量 spot 拉取）
        all_hk_stocks = get_all_hk_stocks()

        # 2. 中英文名称双匹配（不区分大小写）
        keyword_upper = keyword.upper()
        matched = []
        for s in all_hk_stocks:
            name = s.get("name", "")
            name_en = s.get("name_en", "")
            if keyword_upper in name.upper() or keyword_upper in name_en.upper():
                matched.append(s)

        # 3. 一次拉取全市场 spot 行情，提取所有匹配股票的实时数据
        matched_with_quote = []
        try:
            df = hk_stock_cache.get_hk_spot_dataframe()
            for s in matched:
                row = hk_stock_cache.get_hk_spot_row(df, s["code"])
                if row is not None:
                    info = _extract_spot_row(row, s["code"])
                    if info is not None:
                        matched_with_quote.append(info)
                        continue
                # spot 中无此代码时回退基础记录
                matched_with_quote.append(s)
        except Exception:
            # 行情拉取失败时回退基础记录（不中断搜索）
            matched_with_quote = matched

        output = {
            "success": True,
            "data": matched_with_quote,
            "meta": {
                "tool": "stock_info_hk",
                "command": "search",
                "keyword": keyword,
                "market": "hk",
                "count": len(matched_with_quote),
                "cache": hk_stock_cache.get_hk_code_name_status(),
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info_hk", "command": "search", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def _extract_spot_row(row, code: str) -> dict:
    """从单行 spot 数据提取实时行情字段。

    Args:
        row: spot 数据行。
        code: 港股代码（5 位）。

    Returns:
        包含代码/名称/行情的字典。
    """
    # 动态获取字段值（支持多种字段名，兼容新浪/东财列名差异）
    def get_field(row, *field_names):
        """从多可能字段名中获取值"""
        for field in field_names:
            if field in row.index:
                return row.get(field)
        return None

    name = get_field(row, '中文名称', '名称', 'name', '股票简称')
    price = get_field(row, '最新价', 'price', 'close')
    change_pct = get_field(row, '涨跌幅', 'change_pct', '涨跌幅(%)')
    change = get_field(row, '涨跌额', 'change', '涨跌')
    volume = get_field(row, '成交量', 'volume')
    amount = get_field(row, '成交额', 'amount', '成交金额')
    high = get_field(row, '最高', 'high')
    low = get_field(row, '最低', 'low')
    open_price = get_field(row, '今开', 'open', '开盘价')
    pre_close = get_field(row, '昨收', 'pre_close', '昨日收盘价')

    return {
        "code": code,
        "name": str(name).strip() if name else "",
        "market": "hk",
        "price": float(price) if price else None,
        "change_pct": float(change_pct) if change_pct else None,
        "change": float(change) if change else None,
        "volume": float(volume) if volume else None,
        "amount": float(amount) if amount else None,
        "high": float(high) if high else None,
        "low": float(low) if low else None,
        "open": float(open_price) if open_price else None,
        "pre_close": float(pre_close) if pre_close else None,
    }


def cmd_code(code):
    """--code: 查询单只港股详细信息。"""
    if not code:
        print(json.dumps({
            "success": False,
            "error": "请提供港股代码，例如: --code 00700",
            "meta": {"tool": "stock_info_hk", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    # 补齐5位
    code = code.zfill(5)

    try:
        # 触达列表缓存（命中时零 API），使 meta.cache 状态有意义
        get_all_hk_stocks()
        info = get_hk_stock_info(code)
        if info:
            output = {
                "success": True,
                "data": info,
                "meta": {
                    "tool": "stock_info_hk",
                    "command": "code",
                    "code": code,
                    "market": "hk",
                    "cache": hk_stock_cache.get_hk_code_name_status(),
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            output = {
                "success": False,
                "error": f"未找到港股代码 {code}",
                "meta": {
                    "tool": "stock_info_hk",
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
            "meta": {"tool": "stock_info_hk", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_hot():
    """--hot: 获取港股人气热度榜。"""
    try:
        records = get_hk_hot_stocks()
        output = {
            "success": True,
            "data": records,
            "meta": {
                "tool": "stock_info_hk",
                "command": "hot",
                "market": "hk",
                "count": len(records),
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info_hk", "command": "hot", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="港股股票信息查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --list                # 列出全部港股
  %(prog)s --search 腾讯          # 按名称搜索港股
  %(prog)s --code 00700          # 查询腾讯控股实时行情
  %(prog)s --hot                 # 获取港股人气热度榜

财务指标查询请使用: tools/hk_stock/stock_financial.py
        """)

    parser.add_argument("--list", action="store_true", help="列出全部港股代码和名称")
    parser.add_argument("--search", type=str, default=None, metavar="KEYWORD",
                        help="按名称关键词搜索港股（支持中英文名称匹配）")
    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="查询单只港股详细信息（5位代码，如00700）")
    parser.add_argument("--hot", action="store_true", help="获取港股人气热度榜")
    parser.add_argument("--refresh", action="store_true", help="强制刷新本地港股列表缓存")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.list and not args.search and not args.code and not args.hot and not args.refresh:
        parser.print_help()
        print("\n错误: 请指定至少一个操作", file=sys.stderr)
        sys.exit(1)

    if args.refresh:
        # 强制刷新列表缓存（单独使用或与其他命令组合使用）
        hk_stock_cache.get_hk_code_name_list(force_refresh=True)
        print(json.dumps({
            "success": True,
            "data": {"cache": hk_stock_cache.get_hk_code_name_status()},
            "meta": {
                "tool": "stock_info_hk",
                "command": "refresh",
                "market": "hk",
                "timestamp": datetime.now().isoformat()
            }
        }, ensure_ascii=False))
    elif args.list:
        cmd_list()
    elif args.search:
        cmd_search(args.search)
    elif args.code:
        cmd_code(args.code)
    elif args.hot:
        cmd_hot()


if __name__ == "__main__":
    main()
