#!/usr/bin/env python3
"""港股财务指标查询工具（港股财务数据模块）。

本模块位于 tools/hk_stock/ 目录下，专门用于查询港股上市公司的
财务分析指标数据，是港股数据工具集的财务分析入口。

使用 akshare 库的 stock_financial_hk_analysis_indicator_em 接口获取港股公司的
历年财务分析指标，包括 ROE、毛利率、净利率、现金流等关键指标。

支持两种指标类型：
  - 年度（默认）：按年度组织财务指标
  - 报告期：按报告期组织财务指标

改进说明：
1. 增加重试机制（最多3次重试），应对东方财富接口不稳定问题
2. 增加延迟机制（避免频繁请求）
3. 优化错误处理和日志输出
4. 大额数值（净利润、营业收入）转换为亿元单位便于阅读

Usage:
    {py} tools/hk_stock/stock_financial.py --financial 00700
    {py} tools/hk_stock/stock_financial.py --financial 00700 --indicator 报告期
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime

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
        "meta": {"tool": "stock_financial", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# 导入本地缓存模块（tools/common/hk_stock_cache.py）
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
# 港股财务指标
# ---------------------------------------------------------------------------

# 财务指标字段映射（东方财富英文字段名 -> 中文含义）
_FINANCIAL_FIELD_MAP = {
    "SECUCODE": "股票代码(带HK后缀)",
    "SECURITY_CODE": "股票代码(不带HK后缀)",
    "SECURITY_NAME_ABBR": "股票名称",
    "ORG_CODE": "ORG_CODE",
    "REPORT_DATE": "报告日期",
    "DATE_TYPE_CODE": "报告日期类型",
    "PER_NETCASH_OPERATE": "每股经营现金流(元)",
    "PER_OI": "每股营业收入(元)",
    "BPS": "每股净资产(元)",
    "BASIC_EPS": "基本每股收益(元)",
    "DILUTED_EPS": "稀释每股收益(元)",
    "OPERATE_INCOME": "营业总收入(元)",
    "OPERATE_INCOME_YOY": "营业总收入同比增长(%)",
    "GROSS_PROFIT": "毛利润(元)",
    "GROSS_PROFIT_YOY": "毛利润同比增长(%)",
    "HOLDER_PROFIT": "归母净利润(元)",
    "HOLDER_PROFIT_YOY": "归母净利润同比增长(%)",
    "GROSS_PROFIT_RATIO": "毛利率(%)",
    "EPS_TTM": "TTM每股收益(元)",
    "OPERATE_INCOME_QOQ": "营业总收入滚动环比增长(%)",
    "NET_PROFIT_RATIO": "净利率(%)",
    "ROE_AVG": "平均净资产收益率(%)",
    "GROSS_PROFIT_QOQ": "毛利润滚动环比增长(%)",
    "ROA": "总资产净利率(%)",
    "HOLDER_PROFIT_QOQ": "归母净利润滚动环比增长(%)",
    "ROE_YEARLY": "年化净资产收益率(%)",
    "ROIC_YEARLY": "年化投资回报率(%)",
    "TAX_EBT": "所得税/利润总额(%)",
    "OCF_SALES": "经营现金流/营业收入(%)",
    "DEBT_ASSET_RATIO": "资产负债率(%)",
    "CURRENT_RATIO": "流动比率(倍)",
    "CURRENTDEBT_DEBT": "流动负债/总负债(%)",
    "START_DATE": "START_DATE",
    "FISCAL_YEAR": "年结日",
    "CURRENCY": "CURRENCY",
    "IS_CNY_CODE": "IS_CNY_CODE",
}

# 7条去劣指标所需的关键字段
_KEY_INDICATORS = [
    "REPORT_DATE", "SECURITY_NAME_ABBR",
    "ROE_AVG", "ROE_YEARLY",
    "GROSS_PROFIT_RATIO",
    "NET_PROFIT_RATIO",
    "OCF_SALES",
    "HOLDER_PROFIT", "OPERATE_INCOME",
    "BASIC_EPS", "DILUTED_EPS",
    "BPS",
    "PER_NETCASH_OPERATE",
    "DEBT_ASSET_RATIO",
    "CURRENT_RATIO",
]


def get_hk_financial_indicators(code: str, indicator: str = "年度") -> dict:
    """获取港股财务分析指标（东方财富接口）。

    使用 ak.stock_financial_hk_analysis_indicator_em() 获取港股公司的
    历年财务分析指标，包括ROE、毛利率、净利率、现金流等关键指标。

    Args:
        code: 港股代码（5位数字字符串，如"00700"）
        indicator: 指标类型，"年度" 或 "报告期"，默认"年度"

    Returns:
        dict: 包含财务指标数据的字典
    """
    # 补齐5位代码
    code = code.zfill(5)

    try:
        # 通过本地缓存获取原始 DataFrame
        df = hk_stock_cache.get_financial_indicators(code, indicator)

        if df is None or df.empty:
            return {
                "code": code,
                "indicator": indicator,
                "count": 0,
                "data": [],
                "note": "未获取到财务数据"
            }

        # 提取关键财务指标，按年份组织
        records = []
        for _, row in df.iterrows():
            record = {}
            for field in _KEY_INDICATORS:
                value = row.get(field)
                if field in ["HOLDER_PROFIT", "OPERATE_INCOME"]:
                    # 大额数值转换为亿元
                    if value is not None and not pd.isna(value):
                        record[field] = round(float(value) / 1e8, 2)
                    else:
                        record[field] = None
                elif field in ["ROE_AVG", "ROE_YEARLY", "GROSS_PROFIT_RATIO",
                               "NET_PROFIT_RATIO", "OCF_SALES", "DEBT_ASSET_RATIO",
                               "CURRENT_RATIO", "ROA", "ROIC_YEARLY",
                               "OPERATE_INCOME_YOY", "HOLDER_PROFIT_YOY"]:
                    # 百分比/比率字段
                    if value is not None and not pd.isna(value):
                        record[field] = round(float(value), 2)
                    else:
                        record[field] = None
                else:
                    record[field] = str(value) if value is not None and not pd.isna(value) else None

            # 添加中文字段名说明
            record["_fields"] = {
                field: _FINANCIAL_FIELD_MAP.get(field, field)
                for field in _KEY_INDICATORS
            }

            records.append(record)

        # 按报告日期排序（最新在前）
        records.sort(key=lambda x: x.get("REPORT_DATE", ""), reverse=True)

        print(f"✓ 财务指标获取成功 - 共{len(records)}期数据", file=sys.stderr)

        return {
            "code": code,
            "indicator": indicator,
            "count": len(records),
            "data": records,
            "fields": _FINANCIAL_FIELD_MAP
        }

    except Exception as e:
        raise Exception(f"获取港股财务指标失败: {e}")


# ---------------------------------------------------------------------------
# CLI 处理逻辑
# ---------------------------------------------------------------------------

def cmd_financial(code: str, indicator: str = "年度") -> None:
    """--financial: 获取港股财务分析指标。

    Args:
        code: 港股代码（5位数字字符串）
        indicator: 指标类型，"年度" 或 "报告期"
    """
    if not code:
        print(json.dumps({
            "success": False,
            "error": "请提供港股代码，例如: --financial 00700",
            "meta": {"tool": "stock_financial", "command": "financial", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    # 补齐5位
    code = code.zfill(5)

    try:
        result = get_hk_financial_indicators(code, indicator)
        output = {
            "success": True,
            "data": result,
            "meta": {
                "tool": "stock_financial",
                "command": "financial",
                "code": code,
                "indicator": indicator,
                "market": "hk",
                "cache": hk_stock_cache.get_financial_status(),
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_financial", "command": "financial", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main() -> None:
    """命令行入口：解析参数并分发到对应的命令处理函数。"""
    parser = argparse.ArgumentParser(
        description="港股财务指标查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --financial 00700     # 获取腾讯控股年度财务指标
  %(prog)s --financial 00700 --indicator 报告期  # 获取报告期财务指标
        """)

    parser.add_argument("--financial", type=str, default=None, metavar="CODE",
                        help="获取港股财务分析指标（5位代码，如00700）")
    parser.add_argument("--indicator", type=str, default="年度", metavar="TYPE",
                        help="指标类型：年度（默认）或 报告期")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.financial:
        parser.print_help()
        print("\n错误: 请指定至少一个操作（--financial）", file=sys.stderr)
        sys.exit(1)

    cmd_financial(args.financial, args.indicator)


if __name__ == "__main__":
    main()
