#!/usr/bin/env python3
"""A 股质量筛选工具 — 输出 quality-screen 所需的 7 条指标数据。

本模块位于 tools/a_share/ 目录下，专门用于 A 股上市公司的质量筛选，
计算巴菲特/芒格/段永平/李录价值投资框架的 7 条去劣指标。

使用 akshare 库获取财务数据，计算巴菲特/芒格/段永平/李录价值投资框架的 7 条去劣指标。

Usage:
    {py} tools/a_share/stock_screen.py --code 300502
    {py} tools/a_share/stock_screen.py --code 300502,600519,000858
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime

try:
    import akshare as ak
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 akshare 库: {e}。请运行: pip install akshare",
        "meta": {"tool": "stock_screen", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# ---------------------------------------------------------------------------
# 导入本地缓存模块（tools/common/a_stock_cache.py）
# ---------------------------------------------------------------------------
# 将项目根目录加入 sys.path，使本工具以独立脚本方式运行时也能导入 tools.common 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.common import a_stock_cache  # noqa: E402 - 需在 sys.path 设置之后导入

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def get_latest_quarter_date() -> str:
    """获取最近的季度末日期字符串。

    返回格式为 8 位 YYYYMMDD（如 20260630）。该函数供外部调用方及测试
    使用；本工具内部已改为通过 a_stock_cache 读取最新季度数据。
    """
    now = datetime.now()
    y, m = now.year, now.month
    if m <= 3:
        return f"{y - 1}1231"
    elif m <= 6:
        return f"{y}0331"
    elif m <= 9:
        return f"{y}0630"
    else:
        return f"{y}0930"


def get_exchange_info(code: str) -> dict:
    """根据股票代码判断交易所和板块。

    A股代码规则：
    - 60xxxx: 上海主板
    - 00xxxx: 深圳主板（含原中小板002xxx）
    - 30xxxx: 创业板
    - 688xxx: 科创板
    """
    code = code.zfill(6)
    
    if code.startswith("60"):
        return {
            "exchange": "上海证券交易所",
            "board": "主板",
            "exchange_short": "沪",
            "board_short": "主板"
        }
    elif code.startswith("00"):
        return {
            "exchange": "深圳证券交易所",
            "board": "主板",
            "exchange_short": "深",
            "board_short": "主板"
        }
    elif code.startswith("30"):
        return {
            "exchange": "深圳证券交易所",
            "board": "创业板",
            "exchange_short": "深",
            "board_short": "创业板"
        }
    elif code.startswith("688"):
        return {
            "exchange": "上海证券交易所",
            "board": "科创板",
            "exchange_short": "沪",
            "board_short": "科创板"
        }
    else:
        return {
            "exchange": "未知",
            "board": "未知",
            "exchange_short": "",
            "board_short": ""
        }


def get_ipo_info(code: str) -> dict:
    """获取IPO信息（上市日期、上市地等，走本地缓存）。"""
    try:
        df = a_stock_cache.get_ipo_info(code)
        
        result = {
            "listing_date": None,
            "exchange": None,
            "ipo_price": None,
            "issue_pe": None
        }
        
        for _, row in df.iterrows():
            item = row.get("item", "")
            value = row.get("value", "")
            
            if "上市日期" in item:
                result["listing_date"] = str(value)
            elif "上市地" in item:
                result["exchange"] = str(value)
            elif "发行价" in item:
                result["ipo_price"] = _safe_float(value)
            elif "发行市盈率" in item:
                result["issue_pe"] = _safe_float(value)
        
        return result
        
    except Exception as e:
        return {
            "listing_date": None,
            "exchange": None,
            "ipo_price": None,
            "issue_pe": None,
            "error": str(e)
        }


def _safe_float(val):
    """安全转为 float，NaN/None 转为 None。"""
    if val is None:
        return None
    try:
        v = float(val)
        if v != v:  # NaN check
            return None
        return v
    except (ValueError, TypeError):
        return None


def _year_labels(columns) -> list:
    """从 DataFrame 列名中提取年份标签。"""
    years = set()
    for col in columns:
        if col in ("选项", "指标"):
            continue
        # 提取 YYYYMMDD 格式的年份
        col_str = str(col)
        if col_str.endswith("1231"):
            years.add(col_str[:4])
    return sorted(years, reverse=True)


# ---------------------------------------------------------------------------
# 核心计算函数
# ---------------------------------------------------------------------------

def calc_roe(data: dict) -> dict:
    """计算 10 年平均 ROE。

    注意：stock_financial_abstract 返回的数据中，
    "净资产收益率(ROE)" 在 "常用指标" 分类下有年度数据。
    """
    roe_key = None
    # 优先查找 "净资产收益率(ROE)"
    for k in data:
        if "净资产收益率(ROE)" == k or "净资产收益率" in k and "ROE" in k:
            roe_key = k
            break

    # 如果没找到，尝试其他变体
    if not roe_key:
        for k in data:
            if "净资产收益率" in k and "扣除非经常" not in k:
                roe_key = k
                break

    if not roe_key or roe_key not in data:
        return {"value": None, "note": "未找到 ROE 数据"}

    values = {}
    roe_data = data[roe_key]

    for col, val in roe_data.items():
        # 跳过非年份列
        col_str = str(col)
        if not col_str.isdigit() and not col_str.startswith("20") and not col_str.startswith("19"):
            continue

        v = _safe_float(val)
        if v is not None:
            year = col_str[:4]
            # 只取年报数据（12月31日）
            if col_str.endswith("1231") or len(col_str) == 4:
                values[year] = v

    # 取最近10年的年报数据（2015-2025）
    recent_data = {y: v for y, v in values.items() if int(y) >= 2015}

    if not recent_data:
        return {"value": None, "note": "ROE 数据不足"}

    avg = round(sum(recent_data.values()) / len(recent_data), 2)
    return {
        "value": avg,
        "annual": recent_data,
        "years": len(recent_data),
        "note": f"{len(recent_data)}年平均值"
    }


def calc_gross_margin(data: dict) -> dict:
    """计算长期毛利率均值。"""
    # 找毛利率
    gm_key = None
    for k in data:
        if "毛利率" in k and k != "销售成本率":
            gm_key = k
            break

    if not gm_key or gm_key not in data:
        return {"value": None, "note": "未找到毛利率数据"}

    values = {}
    for col, val in data[gm_key].items():
        v = _safe_float(val)
        if v is not None:
            year = str(col)[:4]
            values[year] = v

    annual_data = {y: v for y, v in values.items() if int(y) >= 2015}

    if not annual_data:
        return {"value": None, "note": "毛利率数据不足"}

    avg = round(sum(annual_data.values()) / len(annual_data), 2)
    return {
        "value": avg,
        "annual": annual_data,
        "years": len(annual_data),
        "note": f"{len(annual_data)}年平均值"
    }


def calc_net_margin(data: dict) -> dict:
    """计算长期净利率均值。"""
    nm_key = None
    for k in data:
        if "销售净利率" in k:
            nm_key = k
            break
        elif "净利率" in k and "毛利率" not in k:
            nm_key = k

    if not nm_key or nm_key not in data:
        return {"value": None, "note": "未找到净利率数据"}

    values = {}
    for col, val in data[nm_key].items():
        v = _safe_float(val)
        if v is not None:
            year = str(col)[:4]
            values[year] = v

    annual_data = {y: v for y, v in values.items() if int(y) >= 2015}

    if not annual_data:
        return {"value": None, "note": "净利率数据不足"}

    avg = round(sum(annual_data.values()) / len(annual_data), 2)
    return {
        "value": avg,
        "annual": annual_data,
        "years": len(annual_data),
        "note": f"{len(annual_data)}年平均值"
    }


def calc_ocf_to_net_profit(data: dict) -> dict:
    """计算经营现金流/净利润比率（5 年均值）。"""
    ocf_key = None
    ni_key = None

    for k in data:
        if "经营现金流量净额" in k:
            ocf_key = k
        elif k == "净利润":
            ni_key = k

    if not ocf_key or not ni_key:
        # 尝试找每股经营现金流 / 基本每股收益来计算比率
        return {"value": None, "note": "需要经营现金流和净利润数据"}

    ocf_data = {}
    for col, val in data[ocf_key].items():
        v = _safe_float(val)
        if v is not None:
            ocf_data[str(col)[:4]] = v

    ni_data = {}
    for col, val in data[ni_key].items():
        v = _safe_float(val)
        if v is not None:
            ni_data[str(col)[:4]] = v

    ratios = {}
    for year in ocf_data:
        if year in ni_data and ni_data[year] and ni_data[year] != 0:
            ratios[year] = round(ocf_data[year] / ni_data[year], 2)

    # 近5年
    recent = {y: v for y, v in ratios.items() if int(y) >= 2021}

    if not recent:
        return {"value": None, "note": "OCF/NI 数据不足"}

    avg = round(sum(recent.values()) / len(recent), 2)
    return {
        "value": avg,
        "annual": recent,
        "years": len(recent),
        "note": f"{len(recent)}年平均值"
    }


def calc_debt_ratio(data: dict) -> dict:
    """计算资产负债率。"""
    dr_key = None
    for k in data:
        if "资产负债率" in k:
            dr_key = k
            break

    if not dr_key or dr_key not in data:
        return {"value": None, "note": "未找到资产负债率数据"}

    values = {}
    for col, val in data[dr_key].items():
        v = _safe_float(val)
        if v is not None:
            year = str(col)[:4]
            values[year] = v

    recent = {y: v for y, v in values.items() if int(y) >= 2021}

    if not recent:
        return {"value": None, "note": "数据不足"}

    latest = list(recent.values())[0] if recent else None
    avg = round(sum(recent.values()) / len(recent), 2) if recent else None
    return {
        "value": latest,
        "average": avg,
        "annual": recent,
        "note": f"最新: {latest}%, 平均: {avg}%"
    }


def calc_interest_coverage(code: str) -> dict:
    """利息覆盖倍数（EBIT/利息费用）。

    使用 stock_financial_report_sina 获取利润表数据，
    计算利息覆盖倍数 = (利润总额 + 财务费用) / 财务费用。

    注意：部分公司可能没有单独披露利息费用，
    这种情况下用财务费用近似代替。
    """
    try:
        # 获取利润表数据（走本地缓存）
        df = a_stock_cache.get_income_statement_sina(code)

        if df.empty:
            return {"value": None, "note": "未获取到利润表数据"}

        # 查找最近一期的数据（第一行通常是最新）
        latest_row = df.iloc[0]

        # 尝试获取相关字段
        # EBIT ≈ 利润总额 + 利息费用（或财务费用）
        # 如果没有利息费用，用财务费用代替

        profit_total = None  # 利润总额
        finance_cost = None  # 财务费用
        interest_expense = None  # 利息费用

        # 遍历列名查找相关字段
        for col in df.columns:
            if "利润总额" in col:
                profit_total = _safe_float(latest_row.get(col))
            elif "财务费用" in col and "利息" not in col:
                finance_cost = _safe_float(latest_row.get(col))
            elif "利息费用" in col or "利息支出" in col:
                interest_expense = _safe_float(latest_row.get(col))

        # 优先使用利息费用，如果没有则使用财务费用
        interest = interest_expense if interest_expense else finance_cost

        if profit_total is None or interest is None or interest == 0:
            return {
                "value": None,
                "note": "缺少利润总额或利息费用数据",
                "profit_total": profit_total,
                "interest_expense": interest_expense,
                "finance_cost": finance_cost
            }

        # EBIT = 利润总额 + 利息费用
        ebit = profit_total + interest
        coverage = round(ebit / interest, 2)

        return {
            "value": coverage,
            "ebit": ebit,
            "interest": interest,
            "note": f"EBIT={ebit:.2f}, 利息={interest:.2f}, 覆盖倍数={coverage}"
        }

    except Exception as e:
        return {"value": None, "note": f"计算利息覆盖倍数失败: {e}"}


def calc_share_dilution(code: str, parsed: dict = None) -> dict:
    """计算总股本变化（5 年膨胀比例）。

    方法：通过净资产和每股净资产推算股本
    公式：股本 = 净资产 / 每股净资产

    注意：
    1. 推算数据可能存在误差，需从年报核实
    2. 股本增长原因需手动区分（并购/增发/回购等）
    3. 只判断"非并购原因的股本膨胀"
    """
    if not parsed:
        return {
            "value": None,
            "note": "缺少财务数据，无法推算股本"
        }

    # 查找净资产和每股净资产指标
    net_assets_key = None
    eps_net_key = None

    for k in parsed:
        if "股东权益合计" in k or "净资产合计" in k:
            net_assets_key = k
        elif k == "每股净资产" or "每股净资产_期末股数" in k:
            eps_net_key = k

    if not net_assets_key or not eps_net_key:
        return {
            "value": None,
            "note": "缺少净资产或每股净资产数据"
        }

    # 获取当前股本（最新年度）
    # 找到最新的年度数据（通常是第一个年份列）
    year_cols = [col for col in parsed[net_assets_key].keys()
                 if str(col).endswith("1231") or len(str(col)) == 4]
    year_cols.sort(reverse=True)  # 降序排列，最新的在最前

    if not year_cols:
        return {
            "value": None,
            "note": "未找到年度数据"
        }

    latest_year = str(year_cols[0])
    # 5年前的年份（2021年）
    five_years_ago = "20211231"

    # 尝试获取数据
    try:
        # 最新股本
        latest_net_assets = _safe_float(parsed[net_assets_key].get(latest_year))
        latest_eps_net = _safe_float(parsed[eps_net_key].get(latest_year))

        if latest_net_assets is None or latest_eps_net is None or latest_eps_net == 0:
            return {
                "value": None,
                "note": f"最新年度({latest_year[:4]})数据缺失或无效"
            }

        latest_shares = latest_net_assets / latest_eps_net

        # 5年前股本
        old_net_assets = _safe_float(parsed[net_assets_key].get(five_years_ago))
        old_eps_net = _safe_float(parsed[eps_net_key].get(five_years_ago))

        if old_net_assets is None or old_eps_net is None or old_eps_net == 0:
            # 如果5年前数据缺失，尝试使用4年前或上市初年数据
            old_year = None
            for col in year_cols:
                year = int(str(col)[:4])
                if year >= 2017:  # 至少要有3年以上数据
                    old_year = str(col)
                    break

            if old_year:
                old_net_assets = _safe_float(parsed[net_assets_key].get(old_year))
                old_eps_net = _safe_float(parsed[eps_net_key].get(old_year))
                five_years_ago = old_year
            else:
                return {
                    "value": None,
                    "note": "历史股本数据不足（需要至少3年数据）"
                }

        old_shares = old_net_assets / old_eps_net

        # 计算膨胀比例
        dilution_ratio = ((latest_shares - old_shares) / old_shares) * 100

        # 判断是否超过20%
        if dilution_ratio > 20:
            result = {
                "value": round(dilution_ratio, 2),
                "latest_shares": round(latest_shares, 0),
                "old_shares": round(old_shares, 0),
                "latest_year": latest_year[:4],
                "old_year": five_years_ago[:4],
                "note": f"股本膨胀{dilution_ratio:.2f}%（需核实是否为并购原因）"
            }
        else:
            result = {
                "value": round(dilution_ratio, 2),
                "latest_shares": round(latest_shares, 0),
                "old_shares": round(old_shares, 0),
                "latest_year": latest_year[:4],
                "old_year": five_years_ago[:4],
                "note": f"股本膨胀{dilution_ratio:.2f}%（未超过20%阈值）"
            }

        return result

    except Exception as e:
        return {
            "value": None,
            "note": f"股本计算失败: {e}"
        }


# ---------------------------------------------------------------------------
# 单只股票筛选
# ---------------------------------------------------------------------------

def screen_stock(code: str) -> dict:
    """对单只股票执行 7 条指标筛选。"""
    code = code.zfill(6)

    # 1. 获取基本信息（优先本地缓存）
    try:
        stocks = a_stock_cache.get_code_name_list()
        stock_row = [s for s in stocks if s["code"] == code]
        stock_name = stock_row[0]["name"] if stock_row else ""
    except Exception:
        stock_name = ""

    # 2. 获取交易所和板块信息
    exchange_info = get_exchange_info(code)

    # 3. 获取IPO信息（上市日期）
    ipo_info = get_ipo_info(code)

    # 4. 获取业绩报表信息（行业字段，优先本地缓存）
    industry = ""
    try:
        industry_map = a_stock_cache.get_industry_map()
        info = industry_map.get(code)
        if info:
            industry = str(info.get("industry", ""))
    except Exception:
        pass

    # 5. 获取财务摘要数据（走本地缓存）
    try:
        df = a_stock_cache.get_financial_abstract(code)
    except Exception as e:
        return {
            "success": False,
            "error": f"获取财务数据失败: {e}",
            "meta": {"code": code, "timestamp": datetime.now().isoformat()}
        }

    # 解析数据
    parsed = {}
    for _, row in df.iterrows():
        indicator = row["指标"]
        parsed[indicator] = {}
        for col in df.columns:
            if col in ("选项", "指标"):
                continue
            parsed[indicator][str(col)] = row[col]

    # 4. 计算 7 条指标
    roe = calc_roe(parsed)
    gross_margin = calc_gross_margin(parsed)
    net_margin = calc_net_margin(parsed)
    ocf_to_ni = calc_ocf_to_net_profit(parsed)
    debt_ratio = calc_debt_ratio(parsed)
    interest_coverage = calc_interest_coverage(code)  # 传入股票代码
    dilution = calc_share_dilution(code, parsed)  # 传入代码和解析数据

    # 5. 自由现金流（5 年累计）
    # 从经营现金流中推算
    fcf_data = {"value": None, "note": "需从现金流量表详细数据计算"}
    ocf_key = None
    for k in parsed:
        if "经营现金流量" in k and "净额" in k:
            ocf_key = k
            break
    if ocf_key and ocf_key in parsed:
        ocf_values = []
        for col, val in parsed[ocf_key].items():
            v = _safe_float(val)
            if v is not None and str(col).endswith("1231"):
                ocf_values.append(v)
        if ocf_values:
            total_ocf = sum(ocf_values[-5:]) if len(ocf_values) >= 5 else sum(ocf_values)
            fcf_data = {
                "value": total_ocf,
                "note": f"5年累计经营现金流: {total_ocf:.2f}（不含资本开支）",
                "ocf_annual": ocf_values[-5:] if len(ocf_values) >= 5 else ocf_values
            }

    # 6. 数据窗口检查
    # 根据ROE年数判断数据充足性
    data_years = roe.get("years", 0)
    data_window = {
        "years": data_years,
        "status": "数据充足",
        "note": ""
    }
    if data_years < 5:
        data_window["status"] = "数据窗口较短"
        data_window["note"] = f"仅有{data_years}年数据，建议谨慎解读指标"
    elif data_years < 10:
        data_window["status"] = "数据基本充足"
        data_window["note"] = f"{data_years}年数据，可做基本判断"
    else:
        data_window["status"] = "数据充足"
        data_window["note"] = f"{data_years}年数据，指标可靠性高"

    # 7. 计算上市年限
    listing_years = None
    if ipo_info.get("listing_date"):
        try:
            listing_date = datetime.strptime(ipo_info["listing_date"], "%Y-%m-%d")
            listing_years = round((datetime.now() - listing_date).days / 365.25, 1)
        except Exception:
            pass

    return {
        "success": True,
        "data": {
            "code": code,
            "name": stock_name,
            "exchange": exchange_info["exchange"],
            "board": exchange_info["board"],
            "exchange_short": exchange_info["exchange_short"],
            "board_short": exchange_info["board_short"],
            "listing_date": ipo_info.get("listing_date"),
            "listing_years": listing_years,
            "ipo_price": ipo_info.get("ipo_price"),
            "industry": industry,
            "data_window": data_window,
            "screening": {
                "1_ROE": roe,
                "2_FCF": fcf_data,
                "3_interest_coverage": interest_coverage,
                "4_gross_margin": gross_margin,
                "5_ocf_to_net_profit": ocf_to_ni,
                "6_net_margin": net_margin,
                "7_share_dilution": dilution,
                "debt_ratio": debt_ratio,
            }
        },
        "meta": {
            "tool": "stock_screen",
            "code": code,
            "cache": a_stock_cache.get_financial_status(),
            "timestamp": datetime.now().isoformat()
        }
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A 股质量筛选工具 — 7 条去劣指标计算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --code 300502              # 单只股票
  %(prog)s --code 300502,600519,000858  # 多只股票用逗号分隔

7 条指标:
  ① 10年平均ROE
  ② 5年累计自由现金流
  ③ 利息覆盖倍数
  ④ 长期毛利率均值
  ⑤ 经营现金流/净利润 (5年均值)
  ⑥ 长期净利率均值
  ⑦ 5年总股本膨胀
        """)

    parser.add_argument("--code", type=str, required=True, metavar="CODE",
                        help="股票代码，多只股票用逗号分隔 (必填)")

    args = parser.parse_args()
    codes = [c.strip() for c in args.code.split(",")]

    try:
        results = []
        for code in codes:
            result = screen_stock(code)
            results.append(result)

        output = {
            "success": True,
            "data": results,
            "meta": {
                "tool": "stock_screen",
                "code_count": len(codes),
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False, default=str))

    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"筛选过程失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {
                "tool": "stock_screen",
                "timestamp": datetime.now().isoformat()
            }
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
