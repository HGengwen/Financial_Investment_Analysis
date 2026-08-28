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
# 市值与研报覆盖（阶段三任务2：总市值/流通市值 + 机构覆盖度/研报数）
# ---------------------------------------------------------------------------

def _to_float(value):
    """安全转 float，失败返回 None。

    Args:
        value: 待转换值。

    Returns:
        float 或 None。
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_a_valuation(code):
    """获取 A 股总市值/流通市值（单位：亿元人民币）。

    总市值优先取百度历史估值接口（`stock_zh_valuation_baidu`，返回最近一日，
    可靠且覆盖 5000+）；流通市值取东方财富个股信息接口（`stock_individual_info_em`，
    东财偶发断连，失败时相应字段置 None 并在 gap 标注缺口，不阻断整体返回）。

    Args:
        code: 6 位 A 股代码。

    Returns:
        dict: {"market_cap", "float_market_cap", "currency", "unit", "gap"}。
    """
    code = code.zfill(6)
    result = {
        "market_cap": None,
        "float_market_cap": None,
        "currency": "CNY",
        "unit": "亿元",
        "gap": {},
    }
    # 源1：百度总市值（主源，可靠）
    try:
        df = ak.stock_zh_valuation_baidu(symbol=code, indicator="总市值")
        if df is not None and not df.empty and "value" in df.columns:
            result["market_cap"] = _to_float(df["value"].dropna().iloc[-1])
    except Exception:
        result["gap"]["market_cap"] = "百度估值接口获取失败"
    # 源2：东财个股信息（含总市值/流通市值；东财不稳定，失败不影响主流程）
    try:
        df = ak.stock_individual_info_em(symbol=code)
        if df is not None and not df.empty and "item" in df.columns:
            item_map = dict(zip(df["item"], df["value"]))
            result["float_market_cap"] = _to_float(item_map.get("流通市值"))
            # 百度缺失时用东财总市值兜底
            if result["market_cap"] is None:
                result["market_cap"] = _to_float(item_map.get("总市值"))
    except Exception:
        result["gap"]["float_market_cap"] = "东财个股信息接口获取失败"
    return result


def _pick_column(df, *names):
    """从 DataFrame 中按候选列名取第一个存在的列名。

    Args:
        df: pandas DataFrame。
        names: 候选列名。

    Returns:
        存在的列名；均不存在时返回 None。
    """
    for name in names:
        if name in df.columns:
            return name
    return None


def _summarize_reports(df):
    """研报列表汇总（纯函数，可单测）。

    Args:
        df: `stock_research_report_em` 返回的 DataFrame（含 机构/报告名称/日期/近一月个股研报数）。

    Returns:
        dict: {"total_reports", "unique_orgs", "orgs", "latest_date",
               "latest_title", "last_month_reports"}。
    """
    result = {
        "total_reports": int(len(df)) if df is not None else 0,
        "unique_orgs": None,
        "orgs": [],
        "latest_date": None,
        "latest_title": None,
        "last_month_reports": None,
    }
    if df is None:
        return result

    org_col = _pick_column(df, "机构", "institution", "org")
    if org_col:
        orgs = [str(v).strip() for v in df[org_col].dropna() if str(v).strip()]
        result["orgs"] = list(dict.fromkeys(orgs))  # 去重保序
        result["unique_orgs"] = len(result["orgs"])
    else:
        result["unique_orgs"] = None

    date_col = _pick_column(df, "日期", "date")
    if date_col and len(df):
        first = df[date_col].dropna()
        if len(first):
            result["latest_date"] = str(first.iloc[0])

    title_col = _pick_column(df, "报告名称", "title")
    if title_col and len(df):
        first = df[title_col].dropna()
        if len(first):
            result["latest_title"] = str(first.iloc[0])

    month_col = _pick_column(df, "近一月个股研报数", "last_month_reports")
    if month_col:
        nums = []
        for v in df[month_col].dropna():
            num = _to_float(v)
            if num is not None:
                nums.append(num)
        if nums:
            result["last_month_reports"] = int(sum(nums))
    return result


def get_a_coverage(code):
    """获取 A 股机构覆盖度/研报数（东财个股研报接口 `stock_research_report_em`）。

    Args:
        code: 6 位 A 股代码。

    Returns:
        dict: 研报统计；接口失败时返回带 error/gap 的字典。
    """
    code = code.zfill(6)
    try:
        df = ak.stock_research_report_em(symbol=code)
    except Exception as e:
        return {
            "total_reports": 0, "unique_orgs": None, "orgs": [],
            "latest_date": None, "latest_title": None, "last_month_reports": None,
            "error": f"研报接口获取失败: {e}", "gap": True,
        }
    return _summarize_reports(df)


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


def cmd_profile(code):
    """--profile: 查询个股完整画像（基本信息 + 市值 + 机构覆盖/研报数）。"""
    if not code:
        print(json.dumps({
            "success": False,
            "error": "请提供股票代码，例如: --profile 300502",
            "meta": {"tool": "stock_info", "command": "profile",
                     "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        code = code.zfill(6)
        industry_map = get_a_stock_industry_info()
        info = industry_map.get(code, {})
        valuation = get_a_valuation(code)
        coverage = get_a_coverage(code)
        data = dict(info)
        data["market_cap"] = valuation["market_cap"]
        data["float_market_cap"] = valuation["float_market_cap"]
        data["valuation_gap"] = valuation["gap"] or None
        data["coverage"] = coverage
        output = {
            "success": True,
            "data": data,
            "meta": {
                "tool": "stock_info",
                "command": "profile",
                "code": code,
                "market": "a",
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"画像查询失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info", "command": "profile",
                     "timestamp": datetime.now().isoformat()}
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
  %(prog)s --profile 300502                  # 查询完整画像(市值+研报覆盖)
  %(prog)s --industry 通信设备                # 按行业筛选

港股查询请使用: stock_info_hk.py
        """)

    parser.add_argument("--list", action="store_true", help="列出全部 A 股代码和名称")
    parser.add_argument("--search", type=str, default=None, metavar="KEYWORD",
                        help="按名称关键词搜索股票")
    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="查询单只股票详细信息")
    parser.add_argument("--profile", type=str, default=None, metavar="CODE",
                        help="查询完整画像（基本信息+市值+机构覆盖/研报数）")
    parser.add_argument("--industry", type=str, default=None, metavar="INDUSTRY",
                        help="按行业名称筛选股票")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.list and not args.search and not args.code and not args.industry \
            and not args.profile:
        parser.print_help()
        print("\n错误: 请指定至少一个操作", file=sys.stderr)
        sys.exit(1)

    if args.list:
        cmd_list()
    elif args.search:
        cmd_search(args.search)
    elif args.code:
        cmd_code(args.code)
    elif args.profile:
        cmd_profile(args.profile)
    elif args.industry:
        cmd_industry(args.industry)


if __name__ == "__main__":
    main()
