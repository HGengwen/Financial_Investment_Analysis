#!/usr/bin/env python3
"""港股质量筛选工具 — 输出 quality-screen 所需的 7 条指标数据。

使用 akshare 库获取港股财务数据，计算巴菲特/芒格/段永平/李录价值投资框架的 7 条去劣指标。
本模块为港股质量筛选工具的 hk_stock 包内副本，功能与 tools/stock_screen_hk.py 完全一致。

Usage:
    {py} tools/hk_stock/stock_screen.py --code 00700
    {py} tools/hk_stock/stock_screen.py --code 00700,03690,01810
"""

import argparse
import json
import sys
import traceback
from datetime import datetime

try:
    import akshare as ak
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 akshare 库: {e}。请运行: pip install akshare",
        "meta": {"tool": "stock_screen_hk", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# ---------------------------------------------------------------------------
# 数据获取函数
# ---------------------------------------------------------------------------

def get_hk_financial_indicators(code: str, indicator: str = "年度") -> dict:
    """获取港股财务指标数据。

    Args:
        code: 港股代码（5位数字字符串）
        indicator: 指标类型，"年度" 或 "报告期"

    Returns:
        包含财务指标数据的字典
    """
    try:
        # 使用东方财富港股财务分析接口
        df = ak.stock_financial_hk_analysis_indicator_em(symbol=code, indicator=indicator)

        if df.empty:
            return {"success": False, "error": f"未找到港股 {code} 的财务数据"}

        # 转换为列表格式
        records = []
        for _, row in df.iterrows():
            record = {
                "report_date": str(row.get("REPORT_DATE", "")),
                "roe_avg": float(row.get("ROE_AVG", 0)) if row.get("ROE_AVG") else None,
                "gross_profit_ratio": float(row.get("GROSS_PROFIT_RATIO", 0)) if row.get("GROSS_PROFIT_RATIO") else None,
                "net_profit_ratio": float(row.get("NET_PROFIT_RATIO", 0)) if row.get("NET_PROFIT_RATIO") else None,
                "ocf_sales": float(row.get("OCF_SALES", 0)) if row.get("OCF_SALES") else None,
                "holder_profit": float(row.get("HOLDER_PROFIT", 0)) if row.get("HOLDER_PROFIT") else None,
                "operate_income": float(row.get("OPERATE_INCOME", 0)) if row.get("OPERATE_INCOME") else None,
                "debt_asset_ratio": float(row.get("DEBT_ASSET_RATIO", 0)) if row.get("DEBT_ASSET_RATIO") else None,
                "current_ratio": float(row.get("CURRENT_RATIO", 0)) if row.get("CURRENT_RATIO") else None,
                "bps": float(row.get("BPS", 0)) if row.get("BPS") else None,
            }
            records.append(record)

        return {
            "success": True,
            "data": records,
            "count": len(records)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取港股财务数据失败: {e}",
            "detail": traceback.format_exc()
        }


def get_hk_stock_info(code: str) -> dict:
    """获取港股基本信息（名称、交易所等）。

    Args:
        code: 港股代码（5位数字字符串）

    Returns:
        包含港股基本信息的字典
    """
    return {
        "code": code,
        "exchange": "香港证券交易所",
        "board": "港股",
        "market": "hk"
    }


def get_hk_profit_statement(code: str, indicator: str = "年度") -> dict:
    """获取港股利润表数据（用于计算利息覆盖倍数）。

    Args:
        code: 港股代码（5位数字字符串）
        indicator: 指标类型，"年度" 或 "报告期"

    Returns:
        包含利润表数据的字典
    """
    try:
        df = ak.stock_financial_hk_report_em(stock=code, symbol="利润表", indicator=indicator)

        if df.empty:
            return {"success": False, "error": f"未找到港股 {code} 的利润表数据"}

        return {
            "success": True,
            "data": df,
            "count": len(df)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取港股利润表失败: {e}",
            "detail": traceback.format_exc()
        }


def get_hk_balance_sheet(code: str, indicator: str = "年度") -> dict:
    """获取港股资产负债表数据（用于计算股本变化）。

    Args:
        code: 港股代码（5位数字字符串）
        indicator: 指标类型，"年度" 或 "报告期"

    Returns:
        包含资产负债表数据的字典
    """
    try:
        df = ak.stock_financial_hk_report_em(stock=code, symbol="资产负债表", indicator=indicator)

        if df.empty:
            return {"success": False, "error": f"未找到港股 {code} 的资产负债表数据"}

        return {
            "success": True,
            "data": df,
            "count": len(df)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取港股资产负债表失败: {e}",
            "detail": traceback.format_exc()
        }


# ---------------------------------------------------------------------------
# 7条去劣指标计算函数
# ---------------------------------------------------------------------------

def calc_roe_avg(financial_data: list) -> dict:
    """计算ROE平均值（指标①）。

    Args:
        financial_data: 财务数据列表

    Returns:
        包含ROE平均值和判断结果的字典
    """
    roe_values = [r["roe_avg"] for r in financial_data if r.get("roe_avg") is not None]

    if not roe_values:
        return {
            "value": None,
            "note": "数据不足",
            "pass": None
        }

    # 计算平均值
    avg_roe = sum(roe_values) / len(roe_values)

    # 判断是否通过（阈值8%）
    passed = avg_roe >= 8.0

    return {
        "value": round(avg_roe, 2),
        "count": len(roe_values),
        "pass": passed,
        "threshold": 8.0
    }


def calc_fcf(financial_data: list) -> dict:
    """计算自由现金流（指标②）。

    注意：港股财务数据中经营现金流/营业收入（OCF_SALES）为百分比，
    需要乘以营业收入得到经营现金流，再减去资本开支得到自由现金流。

    Args:
        financial_data: 财务数据列表

    Returns:
        包含FCF判断结果的字典
    """
    # 取最近5年数据
    recent_data = financial_data[:5] if len(financial_data) >= 5 else financial_data

    fcf_values = []
    for r in recent_data:
        if r.get("ocf_sales") and r.get("operate_income"):
            # 经营现金流 = 经营现金流/营业收入 * 营业收入
            ocf = r["ocf_sales"] * r["operate_income"] / 100
            fcf_values.append(ocf)

    if not fcf_values:
        return {
            "value": None,
            "note": "数据不足",
            "pass": None
        }

    # 累计自由现金流（简化处理，假设资本开支已包含）
    cumulative_fcf = sum(fcf_values)

    # 判断是否通过（累计FCF为正）
    passed = cumulative_fcf > 0

    return {
        "value": "正" if passed else "负",
        "cumulative": round(cumulative_fcf, 2),
        "count": len(fcf_values),
        "pass": passed
    }


def calc_interest_coverage(code: str, financial_data: list = None) -> dict:
    """计算利息覆盖倍数（指标③）。

    从港股利润表中获取税前利润和融资成本，计算利息覆盖倍数。
    公式：利息覆盖倍数 = EBIT / 利息支出
           EBIT = 税前利润 + 融资成本

    Args:
        code: 港股代码（5位数字字符串）
        financial_data: 财务数据列表（可选，用于辅助判断）

    Returns:
        包含利息覆盖倍数判断结果的字典
    """
    try:
        # 获取利润表数据
        profit_result = get_hk_profit_statement(code, indicator="年度")

        if not profit_result.get("success"):
            return {
                "value": None,
                "note": f"获取利润表失败: {profit_result.get('error')}",
                "pass": None
            }

        df_profit = profit_result["data"]

        # 提取最近年度数据
        latest_report = df_profit["REPORT_DATE"].max()
        df_latest = df_profit[df_profit["REPORT_DATE"] == latest_report]

        # 提取关键科目
        pre_tax_profit_row = df_latest[df_latest["STD_ITEM_NAME"] == "除税前溢利"]
        finance_cost_row = df_latest[df_latest["STD_ITEM_NAME"] == "融资成本"]

        if pre_tax_profit_row.empty or finance_cost_row.empty:
            return {
                "value": None,
                "note": "利润表中缺少税前利润或融资成本数据",
                "pass": None
            }

        pre_tax_profit = pre_tax_profit_row["AMOUNT"].values[0]
        finance_cost = abs(finance_cost_row["AMOUNT"].values[0])  # 融资成本通常为负值

        # 计算EBIT和利息覆盖倍数
        ebit = pre_tax_profit + finance_cost
        interest_coverage = ebit / finance_cost if finance_cost != 0 else 999

        # 判断是否通过（阈值2倍）
        passed = bool(interest_coverage >= 2.0)

        # 提取多年数据（用于趋势分析）
        coverage_history = []
        for report_date in sorted(df_profit["REPORT_DATE"].unique(), reverse=True)[:5]:
            df_year = df_profit[df_profit["REPORT_DATE"] == report_date]
            pre_tax_row = df_year[df_year["STD_ITEM_NAME"] == "除税前溢利"]
            finance_row = df_year[df_year["STD_ITEM_NAME"] == "融资成本"]

            if not pre_tax_row.empty and not finance_row.empty:
                pre_tax = pre_tax_row["AMOUNT"].values[0]
                finance = abs(finance_row["AMOUNT"].values[0])
                ebit_val = pre_tax + finance
                coverage_val = ebit_val / finance if finance != 0 else 999
                coverage_history.append({
                    "year": str(report_date)[:10],
                    "interest_coverage": round(coverage_val, 2)
                })

        return {
            "value": round(interest_coverage, 2),
            "ebit": round(ebit, 2),
            "finance_cost": round(finance_cost, 2),
            "pass": passed,
            "threshold": 2.0,
            "history": coverage_history,
            "note": f"EBIT={ebit/1e9:.2f}亿, 利息支出={finance_cost/1e9:.2f}亿"
        }

    except Exception as e:
        # 如果获取失败，尝试使用辅助指标推断
        if financial_data and len(financial_data) > 0:
            recent_data = financial_data[0]
            debt_ratio = recent_data.get("debt_asset_ratio")
            current_ratio = recent_data.get("current_ratio")

            # 使用资产负债率作为辅助判断
            estimated_pass = debt_ratio < 50.0 if debt_ratio else None

            return {
                "value": None,
                "note": f"从利润表获取数据失败，使用辅助指标推断: {e}",
                "estimated_pass": estimated_pass,
                "auxiliary": {
                    "debt_asset_ratio": debt_ratio,
                    "current_ratio": current_ratio
                },
                "pass": None
            }

        return {
            "value": None,
            "note": f"计算利息覆盖倍数失败: {e}",
            "pass": None
        }


def calc_gross_margin_avg(financial_data: list) -> dict:
    """计算毛利率平均值（指标④）。

    Args:
        financial_data: 财务数据列表

    Returns:
        包含毛利率平均值和判断结果的字典
    """
    # 取最近5年数据
    recent_data = financial_data[:5] if len(financial_data) >= 5 else financial_data

    gross_margin_values = [r["gross_profit_ratio"] for r in recent_data if r.get("gross_profit_ratio") is not None]

    if not gross_margin_values:
        return {
            "value": None,
            "note": "数据不足",
            "pass": None
        }

    # 计算平均值
    avg_gross_margin = sum(gross_margin_values) / len(gross_margin_values)

    # 判断是否通过（阈值15%）
    passed = avg_gross_margin >= 15.0

    return {
        "value": round(avg_gross_margin, 2),
        "count": len(gross_margin_values),
        "pass": passed,
        "threshold": 15.0
    }


def calc_ocf_to_ni(financial_data: list) -> dict:
    """计算经营现金流/净利润（指标⑤）。

    Args:
        financial_data: 财务数据列表

    Returns:
        包含OCF/NI平均值和判断结果的字典
    """
    # 取最近5年数据
    recent_data = financial_data[:5] if len(financial_data) >= 5 else financial_data

    ratios = []
    for r in recent_data:
        if r.get("ocf_sales") and r.get("net_profit_ratio") and r["net_profit_ratio"] != 0:
            # 经营现金流/净利润 = (OCF_SALES * 营业收入) / (净利率 * 营业收入)
            #                   = OCF_SALES / 净利率
            ratio = r["ocf_sales"] / r["net_profit_ratio"]
            ratios.append(ratio)

    if not ratios:
        return {
            "value": None,
            "note": "数据不足",
            "pass": None
        }

    # 计算平均值
    avg_ratio = sum(ratios) / len(ratios)

    # 判断是否通过（阈值0.7）
    passed = avg_ratio >= 0.7

    return {
        "value": round(avg_ratio, 2),
        "count": len(ratios),
        "pass": passed,
        "threshold": 0.7
    }


def calc_net_margin_avg(financial_data: list) -> dict:
    """计算净利率平均值（指标⑥）。

    Args:
        financial_data: 财务数据列表

    Returns:
        包含净利率平均值和判断结果的字典
    """
    net_margin_values = [r["net_profit_ratio"] for r in financial_data if r.get("net_profit_ratio") is not None]

    if not net_margin_values:
        return {
            "value": None,
            "note": "数据不足",
            "pass": None
        }

    # 计算平均值
    avg_net_margin = sum(net_margin_values) / len(net_margin_values)

    # 判断是否通过（阈值5%）
    passed = avg_net_margin >= 5.0

    return {
        "value": round(avg_net_margin, 2),
        "count": len(net_margin_values),
        "pass": passed,
        "threshold": 5.0
    }


def calc_share_dilution(code: str, financial_data: list = None) -> dict:
    """计算股本稀释比例（指标⑦）。

    从资产负债表获取股东权益，结合每股净资产（BPS）推算股本数量，
    计算股本变化率。
    公式：股本数量 = 股东权益 / 每股净资产

    Args:
        code: 港股代码（5位数字字符串）
        financial_data: 财务数据列表（可选，包含BPS）

    Returns:
        包含股本稀释比例和判断结果的字典
    """
    try:
        # 获取资产负债表数据
        balance_result = get_hk_balance_sheet(code, indicator="年度")

        if not balance_result.get("success"):
            return {
                "value": None,
                "note": f"获取资产负债表失败: {balance_result.get('error')}",
                "pass": None
            }

        df_balance = balance_result["data"]

        # 获取财务指标（包含每股净资产）
        indicator_result = get_hk_financial_indicators(code, indicator="年度")

        if not indicator_result.get("success"):
            return {
                "value": None,
                "note": f"获取财务指标失败: {indicator_result.get('error')}",
                "pass": None
            }

        financial_indicators = indicator_result["data"]

        # 计算每年的股本数量
        share_capital_history = []

        for i, row in enumerate(financial_indicators[:5]):  # 取最近5年
            report_date = row.get("report_date")
            bps = row.get("bps")  # 每股净资产

            # 从资产负债表获取股东权益
            df_year = df_balance[df_balance["REPORT_DATE"].str[:10] == report_date[:10]]
            equity_row = df_year[df_year["STD_ITEM_NAME"] == "股东权益"]

            if not equity_row.empty and bps:
                equity = equity_row["AMOUNT"].values[0]
                # 股本数量 = 股东权益 / 每股净资产
                share_count = equity / bps if bps != 0 else None

                if share_count:
                    share_capital_history.append({
                        "year": report_date[:10],
                        "equity": round(equity, 2),
                        "bps": round(bps, 2),
                        "share_count": round(share_count, 0)
                    })

        if len(share_capital_history) < 2:
            return {
                "value": None,
                "note": "股本数据不足，无法计算变化率",
                "share_capital_history": share_capital_history,
                "pass": None
            }

        # 计算股本变化率
        # 最新的股本
        latest_share = share_capital_history[0]["share_count"]
        # 5年前的股本
        oldest_share = share_capital_history[-1]["share_count"]

        # 股本变化率 = (当前股本 - 5年前股本) / 5年前股本
        share_change_rate = (latest_share - oldest_share) / oldest_share * 100 if oldest_share != 0 else None

        # 判断是否通过（阈值20%，非并购原因的股本膨胀）
        # 股本减少（回购）或小幅增加（<20%）为通过
        passed = bool(share_change_rate <= 20.0) if share_change_rate is not None else None

        return {
            "value": round(share_change_rate, 2) if share_change_rate is not None else None,
            "latest_share_count": latest_share,
            "oldest_share_count": oldest_share,
            "pass": passed,
            "threshold": 20.0,
            "history": share_capital_history,
            "note": f"股本从{oldest_share/1e8:.2f}亿股变化到{latest_share/1e8:.2f}亿股（{share_change_rate:.2f}%）" if share_change_rate is not None else "无法计算股本变化率"
        }

    except Exception as e:
        # 如果获取失败，尝试使用BPS变化推算
        if financial_data and len(financial_data) >= 2:
            recent_bps = financial_data[0].get("bps")
            oldest_bps = financial_data[-1].get("bps")

            if recent_bps and oldest_bps:
                bps_change = (recent_bps - oldest_bps) / oldest_bps * 100 if oldest_bps != 0 else None

                return {
                    "value": None,
                    "note": f"从资产负债表获取数据失败，使用BPS变化推断: {e}",
                    "bps_change": round(bps_change, 2) if bps_change is not None else None,
                    "pass": None
                }

        return {
            "value": None,
            "note": f"计算股本稀释失败: {e}",
            "pass": None
        }


# ---------------------------------------------------------------------------
# 主筛选函数
# ---------------------------------------------------------------------------

def screen_stock(code: str) -> dict:
    """对单只港股执行7条去劣指标筛选。

    Args:
        code: 港股代码（5位数字字符串）

    Returns:
        包含筛选结果的字典
    """
    # 补齐代码为5位
    code = code.zfill(5)

    # 获取基本信息
    stock_info = get_hk_stock_info(code)

    # 获取财务数据
    financial_result = get_hk_financial_indicators(code, indicator="年度")

    if not financial_result.get("success"):
        return {
            "success": False,
            "error": financial_result.get("error", "获取财务数据失败"),
            "code": code,
            "meta": {
                "tool": "stock_screen_hk",
                "timestamp": datetime.now().isoformat()
            }
        }

    financial_data = financial_result["data"]

    # 计算7条指标
    roe_result = calc_roe_avg(financial_data)
    fcf_result = calc_fcf(financial_data)
    interest_result = calc_interest_coverage(code, financial_data)  # 需要传入code
    gross_margin_result = calc_gross_margin_avg(financial_data)
    ocf_ni_result = calc_ocf_to_ni(financial_data)
    net_margin_result = calc_net_margin_avg(financial_data)
    dilution_result = calc_share_dilution(code, financial_data)  # 需要传入code

    # 统计通过数量
    results = [roe_result, fcf_result, interest_result, gross_margin_result, ocf_ni_result, net_margin_result, dilution_result]
    passed_count = sum(1 for r in results if r.get("pass") is True)
    failed_count = sum(1 for r in results if r.get("pass") is False)
    unknown_count = sum(1 for r in results if r.get("pass") is None)

    # 整体判断（如果有任何指标失败，则不通过）
    overall_pass = failed_count == 0

    return {
        "success": True,
        "data": {
            "code": code,
            "stock_info": stock_info,
            "financial_data": financial_data,
            "indicators": {
                "1_roe_avg": roe_result,
                "2_fcf": fcf_result,
                "3_interest_coverage": interest_result,
                "4_gross_margin_avg": gross_margin_result,
                "5_ocf_to_ni": ocf_ni_result,
                "6_net_margin_avg": net_margin_result,
                "7_share_dilution": dilution_result
            },
            "summary": {
                "passed_count": passed_count,
                "failed_count": failed_count,
                "unknown_count": unknown_count,
                "overall_pass": overall_pass
            }
        },
        "meta": {
            "tool": "stock_screen_hk",
            "code": code,
            "market": "hk",
            "timestamp": datetime.now().isoformat()
        }
    }


# ---------------------------------------------------------------------------
# CLI 处理逻辑
# ---------------------------------------------------------------------------

def cmd_screen(codes: str):
    """--code: 对多只港股执行筛选。"""
    code_list = [c.strip() for c in codes.split(",")]

    results = []
    for code in code_list:
        result = screen_stock(code)
        results.append(result)

    output = {
        "success": True,
        "data": results,
        "count": len(results),
        "meta": {
            "tool": "stock_screen_hk",
            "command": "screen",
            "timestamp": datetime.now().isoformat()
        }
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="港股质量筛选工具 — 7 条去劣指标计算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --code 00700              # 单只港股
  %(prog)s --code 00700,03690,01810  # 多只港股用逗号分隔

7 条指标:
  ① 10年平均ROE
  ② 5年累计自由现金流
  ③ 利息覆盖倍数
  ④ 长期毛利率均值
  ⑤ 经营现金流/净利润 (5年均值)
  ⑥ 长期净利率均值
  ⑦ 5年总股本膨胀

注意:
  港股财务数据通常不直接提供利息支出和股本变化，
  指标③和⑦需要从年报手动核实。
        """)

    parser.add_argument("--code", type=str, required=True, metavar="CODE",
                        help="港股代码，多只港股用逗号分隔 (必填)")

    args = parser.parse_args()

    if args.code:
        cmd_screen(args.code)


if __name__ == "__main__":
    main()
