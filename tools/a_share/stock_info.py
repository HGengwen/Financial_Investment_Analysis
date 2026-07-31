#!/usr/bin/env python3
"""A股股票代码与公司信息查询工具（A股信息查询模块）。

本模块位于 tools/a_share/ 目录下，专门用于查询 A 股上市公司的
代码、名称、行业等基本信息，是 A 股数据工具集的核心查询入口。

使用 akshare 库获取 A 股上市公司的代码、名称、行业等信息。

Usage:
    {py} tools/a_share/stock_info.py --list
    {py} tools/a_share/stock_info.py --search 新易盛
    {py} tools/a_share/stock_info.py --code 300502
    {py} tools/a_share/stock_info.py --industry 通信设备

港股查询请使用: tools/stock_info_hk.py
"""

import argparse
import json
import sys
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
        "meta": {"tool": "stock_info", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# ---------------------------------------------------------------------------
# A股数据获取函数
# ---------------------------------------------------------------------------

def get_all_a_stocks():
    """获取全部 A 股代码和名称。"""
    df = ak.stock_info_a_code_name()
    records = []
    for _, row in df.iterrows():
        records.append({
            "code": str(row["code"]).zfill(6),
            "name": str(row["name"]).strip(),
            "market": "a"
        })
    return records


def get_a_stock_industry_info():
    """获取A股股票行业信息（从最新业绩报表提取）。

    尝试最近的季度数据，如果数据不完整则回退到上一个季度。
    """
    now = datetime.now()
    year = now.year
    month = now.month

    # 按优先顺序生成日期列表（最近的季度 -> 前一个季度 -> ...）
    date_candidates = []
    if month <= 3:
        # 当前Q1，尝试 Q4去年、Q3去年
        date_candidates = [f"{year-1}1231", f"{year-1}0930", f"{year-1}0630"]
    elif month <= 6:
        # 当前Q2，尝试 Q1当年、Q4去年、Q3去年
        date_candidates = [f"{year}0331", f"{year-1}1231", f"{year-1}0930"]
    elif month <= 9:
        # 当前Q3，尝试 Q2当年、Q1当年、Q4去年
        date_candidates = [f"{year}0630", f"{year}0331", f"{year-1}1231"]
    else:
        # 当前Q4，尝试 Q3当年、Q2当年、Q1当年
        date_candidates = [f"{year}0930", f"{year}0630", f"{year}0331"]

    for date_str in date_candidates:
        try:
            df = ak.stock_yjbb_em(date=date_str)
            # 检查数据是否有效：至少有1000行且行业字段有数据
            if len(df) > 1000:
                # 检查是否有行业数据
                有行业数据 = df[df["所处行业"].notna() & (df["所处行业"] != "")]
                if len(有行业数据) > 100:
                    # 数据有效，使用此日期
                    break
        except Exception:
            continue

    result = {}
    for _, row in df.iterrows():
        code = str(row["股票代码"]).zfill(6)
        result[code] = {
            "code": code,
            "name": str(row.get("股票简称", "")).strip(),
            "market": "a",
            "industry": str(row.get("所处行业", "")).strip(),
            "roe": float(row.get("净资产收益率", 0)) if row.get("净资产收益率") else None,
            "gross_margin": float(row.get("销售毛利率", 0)) if row.get("销售毛利率") else None,
            "eps": float(row.get("每股收益", 0)) if row.get("每股收益") else None,
        }
    return result


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
        matched = []

        # 搜索A股
        industry_map = get_a_stock_industry_info()
        all_a_stocks = get_all_a_stocks()
        for s in all_a_stocks:
            if keyword.upper() in s["name"].upper():
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

        output = {
            "success": True,
            "data": matched,
            "meta": {
                "tool": "stock_info",
                "command": "search",
                "keyword": keyword,
                "market": "a",
                "count": len(matched),
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
        # A股查询
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
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            # 尝试在全部列表中找到
            all_stocks = get_all_a_stocks()
            found = [s for s in all_stocks if s["code"] == code]
            if found:
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

港股查询请使用: stock_info_hk.py
        """)

    parser.add_argument("--list", action="store_true", help="列出全部 A 股代码和名称")
    parser.add_argument("--search", type=str, default=None, metavar="KEYWORD",
                        help="按名称关键词搜索股票")
    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="查询单只股票详细信息")
    parser.add_argument("--industry", type=str, default=None, metavar="INDUSTRY",
                        help="按行业名称筛选股票")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.list and not args.search and not args.code and not args.industry:
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


if __name__ == "__main__":
    main()
