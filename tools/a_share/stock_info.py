#!/usr/bin/env python3
"""A股股票代码与公司信息查询工具（A股信息查询模块）。

本模块位于 tools/a_share/ 目录下，专门用于查询 A 股上市公司的
代码、名称、行业等基本信息，是 A 股数据工具集的核心查询入口。

数据获取策略：优先从本地缓存（data/a_share/ 下的 CSV，由 tools/common/
a_stock_cache.py 管理）读取代码/名称与最新季度行业数据；仅当缓存缺失、
过期或本地未命中时才调用 akshare 刷新缓存，从而减少 API 调用、规避限流。

Usage:
    {py} tools/a_share/stock_info.py --list
    {py} tools/a_share/stock_info.py --search 新易盛
    {py} tools/a_share/stock_info.py --code 300502
    {py} tools/a_share/stock_info.py --industry 通信设备
    {py} tools/a_share/stock_info.py --refresh

港股查询请使用: tools/stock_info_hk.py
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime

# ---------------------------------------------------------------------------
# 导入本地缓存模块（tools/common/a_stock_cache.py）
# ---------------------------------------------------------------------------
# 将项目根目录加入 sys.path，使本工具以独立脚本方式运行时也能导入 tools.common 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.common import a_stock_cache  # noqa: E402 - 需在 sys.path 设置之后导入

# ---------------------------------------------------------------------------
# A股数据获取函数（基于本地缓存，减少 API 调用）
# ---------------------------------------------------------------------------

def get_all_a_stocks():
    """获取全部 A 股代码和名称。

    优先从本地缓存读取，缓存缺失或过期时自动通过 a_stock_cache 刷新。
    """
    return a_stock_cache.get_code_name_list()


def get_a_stock_industry_info():
    """获取A股股票行业信息（从最新业绩报表提取）。

    优先从本地缓存读取，缓存缺失或过期时自动通过 a_stock_cache 刷新，
    继承原逻辑的 3 季度回退与有效性校验（>1000 行且 >100 只股票有行业数据）。
    """
    return a_stock_cache.get_industry_map()


# ---------------------------------------------------------------------------
# CLI 处理逻辑
# ---------------------------------------------------------------------------

def cmd_list():
    """--list: 列出全部 A 股。"""
    try:
        records = get_all_a_stocks()
        output = {
            "success": True,
            "data": records,
            "meta": {
                "tool": "stock_info",
                "command": "list",
                "market": "a",
                "count": len(records),
                "cache": a_stock_cache.get_code_name_status(),
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"获取股票列表失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "list", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def _build_matched(keyword, stocks, industry_map):
    """在股票列表中按名称关键词匹配，并附带行业信息。

    Args:
        keyword: 搜索关键词。
        stocks: 股票记录列表 [{"code", "name", "market"}, ...]。
        industry_map: 以股票代码为键的行业信息字典。

    Returns:
        匹配结果列表。
    """
    matched = []
    keyword_upper = keyword.upper()
    for s in stocks:
        if keyword_upper in s["name"].upper():
            info = industry_map.get(s["code"], {})
            matched.append({
                "code": s["code"],
                "name": s["name"],
                "market": "a",
                "industry": info.get("industry", ""),
                "roe": info.get("roe"),
                "gross_margin": info.get("gross_margin"),
                "eps": info.get("eps"),
            })
    return matched


def cmd_search(keyword):
    """--search: 按名称关键词搜索A股。"""
    if not keyword:
        print(json.dumps({
            "success": False,
            "error": "请提供搜索关键词，例如: --search 新易盛",
            "meta": {"tool": "stock_info", "command": "search", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        # 搜索A股（优先本地缓存）
        industry_map = get_a_stock_industry_info()
        all_a_stocks = get_all_a_stocks()
        matched = _build_matched(keyword, all_a_stocks, industry_map)

        # miss 双触发：本地查不到时强制刷新一次缓存后再查（新IPO/改名股自愈）
        if not matched:
            all_a_stocks = get_all_a_stocks(force_refresh=True)
            industry_map = get_a_stock_industry_info(force_refresh=True)
            matched = _build_matched(keyword, all_a_stocks, industry_map)

        output = {
            "success": True,
            "data": matched,
            "meta": {
                "tool": "stock_info",
                "command": "search",
                "keyword": keyword,
                "market": "a",
                "count": len(matched),
                "cache": a_stock_cache.get_code_name_status(),
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"搜索失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "search", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_code(code):
    """--code: 查询单只A股股票详细信息。"""
    if not code:
        print(json.dumps({
            "success": False,
            "error": "请提供股票代码，例如: --code 300502",
            "meta": {"tool": "stock_info", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        # A股查询（优先本地缓存）
        code = code.zfill(6)  # A股补齐6位
        industry_map = get_a_stock_industry_info()
        info = industry_map.get(code)

        if info:
            output = {
                "success": True,
                "data": info,
                "meta": {
                    "tool": "stock_info",
                    "command": "code",
                    "code": code,
                    "market": "a",
                    "cache": a_stock_cache.get_industry_status(),
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            # 尝试在全部列表中找到
            all_stocks = get_all_a_stocks()
            found = [s for s in all_stocks if s["code"] == code]

            # miss 双触发：本地查不到时强制刷新一次缓存后再查（新IPO/改名股自愈）
            if not found:
                industry_map = get_a_stock_industry_info(force_refresh=True)
                info = industry_map.get(code)
                all_stocks = get_all_a_stocks(force_refresh=True)
                found = [s for s in all_stocks if s["code"] == code]

            if info:
                output = {
                    "success": True,
                    "data": info,
                    "meta": {
                        "tool": "stock_info",
                        "command": "code",
                        "code": code,
                        "market": "a",
                        "cache": a_stock_cache.get_industry_status(),
                        "timestamp": datetime.now().isoformat()
                    }
                }
            elif found:
                output = {
                    "success": True,
                    "data": {
                        "code": code,
                        "name": found[0]["name"],
                        "market": "a",
                        "industry": "",
                        "roe": None,
                        "gross_margin": None,
                        "eps": None,
                    },
                    "meta": {
                        "tool": "stock_info",
                        "command": "code",
                        "code": code,
                        "market": "a",
                        "cache": a_stock_cache.get_code_name_status(),
                        "timestamp": datetime.now().isoformat()
                    }
                }
            else:
                output = {
                    "success": False,
                    "error": f"未找到股票代码 {code}",
                    "meta": {
                        "tool": "stock_info",
                        "command": "code",
                        "code": code,
                        "market": "a",
                        "cache": a_stock_cache.get_code_name_status(),
                        "timestamp": datetime.now().isoformat()
                    }
                }

        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"查询失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "code", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def cmd_industry(industry_name):
    """--industry: 按行业筛选（仅支持A股）。"""
    if not industry_name:
        print(json.dumps({
            "success": False,
            "error": "请提供行业名称，例如: --industry 通信设备",
            "meta": {"tool": "stock_info", "command": "industry", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps({
        "success": False,
        "error": "行业筛选功能暂仅支持A股，港股行业数据需从其他渠道获取",
        "meta": {"tool": "stock_info", "command": "industry", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)


def cmd_refresh():
    """--refresh: 强制刷新本地 A 股代码/名称与行业数据缓存。"""
    try:
        start = time.time()
        code_records = a_stock_cache.get_code_name_list(force_refresh=True)
        industry_map = a_stock_cache.get_industry_map(force_refresh=True)
        elapsed = round(time.time() - start, 2)
        output = {
            "success": True,
            "data": {
                "stock_code": {
                    "count": len(code_records),
                    "cache_file": str(a_stock_cache.CODE_CACHE_FILE),
                },
                "stock_industry": {
                    "count": len(industry_map),
                    "cache_file": str(a_stock_cache.INDUSTRY_CACHE_FILE),
                },
            },
            "meta": {
                "tool": "stock_info",
                "command": "refresh",
                "market": "a",
                "elapsed_seconds": elapsed,
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"刷新缓存失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "refresh", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A股股票代码与公司信息查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --list                           # 列出全部 A 股
  %(prog)s --search 新易盛                   # 在A股中搜索
  %(prog)s --code 300502                     # 查询A股股票
  %(prog)s --industry 通信设备                # 按行业筛选
  %(prog)s --refresh                        # 强制刷新本地缓存

港股查询请使用: stock_info_hk.py
        """)

    parser.add_argument("--list", action="store_true", help="列出全部 A 股代码和名称")
    parser.add_argument("--search", type=str, default=None, metavar="KEYWORD",
                        help="按名称关键词搜索股票")
    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="查询单只股票详细信息")
    parser.add_argument("--industry", type=str, default=None, metavar="INDUSTRY",
                        help="按行业名称筛选股票")
    parser.add_argument("--refresh", action="store_true",
                        help="强制刷新本地 A 股代码/名称与行业数据缓存")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.list and not args.search and not args.code and not args.industry and not args.refresh:
        parser.print_help()
        print("\n错误: 请指定至少一个操作", file=sys.stderr)
        sys.exit(1)

    if args.list:
        cmd_list()
    elif args.search:
        cmd_search(args.search)
    elif args.code:
        cmd_code(args.code)
    elif args.industry:
        cmd_industry(args.industry)
    elif args.refresh:
        cmd_refresh()


if __name__ == "__main__":
    main()
