#!/usr/bin/env python3
"""A股财务指标查询工具（A股财务数据模块）。

本模块位于 tools/a_share/ 目录下，专门用于查询 A 股上市公司的
财务指标数据，是 A 股数据工具集的财务分析入口。

使用 akshare 库获取 A 股上市公司的财务指标数据。

所有模式的输出结构统一为:
    {
        "success": true,
        "data": {
            "indicators": {指标名: {报告期: 值}},
        },
        "meta": {...}
    }

Usage:
    {py} tools/a_share/stock_financial.py --code 300502
    {py} tools/a_share/stock_financial.py --code 300502 --indicator all
    {py} tools/a_share/stock_financial.py --code 300502 --indicator ROE
    {py} tools/a_share/stock_financial.py --code 300502 --indicator 毛利率,净利率
"""

import argparse
import json
import os
import re
import sys
import traceback
from datetime import datetime

# ---------------------------------------------------------------------------
# 导入 akshare
# ---------------------------------------------------------------------------
try:
    import akshare as ak
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 akshare 库: {e}。请运行: pip install akshare",
        "meta": {"tool": "stock_financial", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# ---------------------------------------------------------------------------
# 导入本地缓存模块（tools/common/a_stock_cache.py）
# ---------------------------------------------------------------------------
# 将项目根目录加入 sys.path，使本工具以独立脚本方式运行时也能导入 tools.common 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.common import a_stock_cache  # noqa: E402 - 需在 sys.path 设置之后导入

# ---------------------------------------------------------------------------
# 关键财务指标映射（中文名 -> 英文标识）
# ---------------------------------------------------------------------------
KEY_INDICATORS = {
    "ROE": "净资产收益率(ROE)",
    "毛利率": "毛利率",
    "净利率": "销售净利率",
    "经营现金流": "经营现金流量净额",
    "净利润": "净利润",
    "扣非净利润": "扣非净利润",
    "营业总收入": "营业总收入",
    "营业成本": "营业成本",
    "资产负债率": "资产负债率",
    "基本每股收益": "基本每股收益",
    "每股经营现金流": "每股经营现金流",
    "每股净资产": "每股净资产",
    "归母净利润": "归母净利润",
    "总资产报酬率": "总资产报酬率(ROA)",
    "期间费用率": "期间费用率",
    "经营现金流/净利润": None,  # 计算得出
    "自由现金流": None,  # 计算得出
}

# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

def get_raw_data(symbol: str):
    """获取原始财务摘要数据（走本地缓存）。"""
    df = a_stock_cache.get_financial_abstract(symbol)
    return df


def parse_financial_data(df) -> dict:
    """将 DataFrame 解析为结构化字典。

    返回:
    {
        "指标名": {
            "20251231": value,
            "20241231": value,
            ...
        },
        ...
    }
    """
    result = {}
    for _, row in df.iterrows():
        indicator = row["指标"]
        result[indicator] = {}
        for col in df.columns:
            if col in ("选项", "指标"):
                continue
            # 提取年份标签
            year_label = str(col)
            val = row[col]
            if val is None or (isinstance(val, float) and val != val):  # NaN 检查
                continue
            if isinstance(val, float):
                val = round(val, 4)
            elif isinstance(val, (int,)):
                val = val
            result[indicator][year_label] = val
    return result


def extract_key_indicators(parsed: dict) -> dict:
    """从全量数据中提取关键指标。"""
    indicators = {}
    for eng_name, cn_name in KEY_INDICATORS.items():
        if cn_name is None:
            indicators[eng_name] = None  # 标记为计算值
        elif cn_name in parsed:
            indicators[eng_name] = parsed[cn_name]
        else:
            # 模糊匹配
            matched = None
            for key in parsed:
                if cn_name in key:
                    matched = parsed[key]
                    break
            indicators[eng_name] = matched

    # 计算经营现金流/净利润
    if indicators.get("经营现金流") and indicators.get("净利润"):
        ocf = indicators["经营现金流"]
        ni = indicators["净利润"]
        ratios = {}
        for year in ocf:
            if year in ni and ni[year] and ni[year] != 0:
                ratios[year] = round(ocf[year] / ni[year], 4)
        indicators["经营现金流/净利润"] = ratios if ratios else None

    # 计算自由现金流 = 经营现金流 - 资本开支（用购建固定资产等支付的现金）
    # 注意：stock_financial_abstract 不直接包含"购建固定资产支付的现金"
    # 这里标记为需要额外数据
    indicators["自由现金流"] = {"note": "需从现金流量表详细数据计算"}

    return indicators


def format_yearly_data(data: dict) -> dict:
    """将指标数据格式化为每年一条记录的简洁形式。"""
    # 获取所有年份
    all_years = set()
    for indicator_name, values in data.items():
        if isinstance(values, dict):
            for year in values:
                all_years.add(year)

    # 只保留年末（1231）数据用于年度对比
    year_end_data = sorted([y for y in all_years if y.endswith("1231")], reverse=True)

    formatted = {}
    for ind_name, values in data.items():
        if not isinstance(values, dict):
            formatted[ind_name] = values
            continue
        formatted[ind_name] = {}
        for year in year_end_data:
            if year in values:
                formatted[ind_name][year[:4]] = values[year]

    return formatted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A 股财务指标查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --code 300502                    # 全部关键财务指标
  %(prog)s --code 300502 --indicator ROE     # 仅 ROE
  %(prog)s --code 300502 --indicator 毛利率,净利率  # 多个指标
  %(prog)s --code 300502 --indicator all     # 全部原始指标

可用指标: ROE, 毛利率, 净利率, 经营现金流, 净利润, 资产负债率,
          基本每股收益, 每股经营现金流, 每股净资产, 期间费用率
          all - 显示全部原始指标
        """)

    parser.add_argument("--code", type=str, required=True, metavar="CODE",
                        help="股票代码 (必填)")
    parser.add_argument("--indicator", type=str, default=None, metavar="INDICATOR",
                        help='指标名称或 "all" (默认显示关键指标)')

    args = parser.parse_args()
    code = args.code.zfill(6)

    try:
        df = get_raw_data(code)
        parsed = parse_financial_data(df)

        if args.indicator == "all":
            # 输出全部原始数据（统一 data.indicators 结构）
            output = {
                "success": True,
                "data": {
                    "indicators": parsed,
                },
                "meta": {
                    "tool": "stock_financial",
                    "code": code,
                    "indicator": "all",
                    "indicator_count": len(parsed),
                    "cache": a_stock_cache.get_financial_status(),
                    "timestamp": datetime.now().isoformat()
                }
            }
        elif args.indicator:
            # 输出指定指标
            requested = [x.strip() for x in args.indicator.split(",")]
            result = {}
            for name in requested:
                # 在映射中查找
                matched_key = None  # 初始化，避免未匹配时 UnboundLocalError
                for eng_name, cn_name in KEY_INDICATORS.items():
                    if name in (eng_name, cn_name) or name == cn_name:
                        matched_key = eng_name
                        break
                if matched_key and matched_key in parsed:
                    result[name] = parsed[matched_key]
                elif name in parsed:
                    result[name] = parsed[name]
                else:
                    # 模糊匹配
                    for key in parsed:
                        if name in key:
                            result[name] = parsed[key]
                            break
                    else:
                        result[name] = {"note": f"未找到指标: {name}"}

            output = {
                "success": True,
                "data": {
                    "indicators": result,
                },
                "meta": {
                    "tool": "stock_financial",
                    "code": code,
                    "indicator": args.indicator,
                    "cache": a_stock_cache.get_financial_status(),
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            # 默认：输出关键指标
            key_data = extract_key_indicators(parsed)
            formatted = format_yearly_data(key_data)

            # 附加一些最近的单个值
            if "毛利率" in formatted and formatted["毛利率"]:
                latest_years = sorted(formatted["毛利率"].keys(), reverse=True)
                if latest_years:
                    latest = latest_years[0]
                    latest_gross = formatted["毛利率"][latest]
                else:
                    latest_gross = None
            else:
                latest_gross = None

            # 获取业绩报表中的最新数据（优先本地缓存）
            industry_info = {}
            try:
                industry_map = a_stock_cache.get_industry_map()
                info = industry_map.get(code)
                if info:
                    industry_info = {
                        "行业": info.get("industry", ""),
                        "ROE_latest": info.get("roe"),
                        "毛利率_latest": info.get("gross_margin"),
                        "每股收益_latest": info.get("eps"),
                    }
            except Exception:
                pass

            output = {
                "success": True,
                "data": {
                    "indicators": formatted,
                    "latest_quarter": industry_info
                },
                "meta": {
                    "tool": "stock_financial",
                    "code": code,
                    "indicator": "key_metrics",
                    "timestamp": datetime.now().isoformat()
                }
            }

        print(json.dumps(output, ensure_ascii=False, default=str))

    except Exception as e:
        error_msg = str(e)
        if "Connection" in error_msg or "RemoteDisconnected" in error_msg:
            error_msg = f"网络连接失败，请检查网络: {e}"
        elif "code" not in error_msg and "symbol" not in error_msg:
            error_msg = f"获取财务数据失败: {e}"

        print(json.dumps({
            "success": False,
            "error": error_msg,
            "detail": traceback.format_exc(),
            "meta": {
                "tool": "stock_financial",
                "code": code,
                "timestamp": datetime.now().isoformat()
            }
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
