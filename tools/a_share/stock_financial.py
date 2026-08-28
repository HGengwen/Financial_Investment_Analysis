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
    {py} tools/a_share/stock_financial.py --code 300502 --advanced 合同负债
    {py} tools/a_share/stock_financial.py --code 300502 --advanced 合同负债,存货,研发费用,存货周转天数,员工总数
"""

import argparse
import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

# 注入项目根目录到 sys.path，使 `from tools.common import ...` 在 CLI 直接运行时可用
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# 导入 akshare 与 A股财务缓存
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

try:
    from tools.common import a_stock_cache
except ImportError:
    a_stock_cache = None  # 缓存层缺失时降级为不缓存，仅直连接口

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
    """获取原始财务摘要数据。"""
    df = ak.stock_financial_abstract(symbol=symbol)
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
# 高级科目（trend-tech-screen 阶段二新增）
#
# 来源映射：每个高级科目 → (报表缓存函数, 精确列名或 None=模糊)
# 员工数走 employee_count（标注缺口）；应付账款周转天数由资产负债表推算。
# ---------------------------------------------------------------------------

#: 高级科目 → (缓存访问函数名, 科目精确列名或 None)
ADVANCED_SOURCES = {
    "合同负债": ("get_balance_sheet", "合同负债"),
    "存货": ("get_balance_sheet", "存货"),
    "开发支出": ("get_balance_sheet", "开发支出"),
    "无形资产": ("get_balance_sheet", "无形资产"),
    "应付账款": ("get_balance_sheet", "应付账款"),
    "应付票据及应付账款": ("get_balance_sheet", "应付票据及应付账款"),
    "预付款项": ("get_balance_sheet", "预付款项"),
    "研发费用": ("get_income_statement_sina", "研发费用"),
    "营业成本": ("get_income_statement_sina", "营业成本"),
    "支付给职工现金": ("get_cash_flow", "支付给职工以及为职工支付的现金"),
    "购建固定资产现金": ("get_cash_flow", "购建固定资产"),
    "存货周转天数": ("get_analysis_indicator", "存货周转天数(天)"),
    "应收账款周转天数": ("get_analysis_indicator", "应收账款周转天数(天)"),
}

_ASR_FUNCS = {}

#: 缓存访问函数名 → a_stock_cache 内部缓存键（用于回读缓存状态）
_FUNC_TO_CACHE_KEY = {
    "get_balance_sheet": "balance_sheet",
    "get_income_statement_sina": "income_statement",
    "get_cash_flow": "cash_flow",
    "get_analysis_indicator": "analysis_indicator",
}


def _get_asr_func(name: str):
    """惰性获取缓存层函数（仅在首次调用时解析一次）。

    Args:
        name: a_stock_cache 中的函数名。

    Returns:
        可调用对象；不可用时返回 None。
    """
    if name not in _ASR_FUNCS:
        _ASR_FUNCS[name] = getattr(a_stock_cache, name, None) if a_stock_cache else None
    return _ASR_FUNCS[name]


def _find_col(stmt: dict, col: str):
    """从 {日期: {科目: 值}} 中按精确/模糊列名提取该科目各期序列。

    Args:
        stmt: 报表科目字典。
        col: 科目名（精确或模糊子串）。

    Returns:
        {日期: 值}；未匹配到任何列时返回 None。
    """
    if not stmt:
        return None
    seen = {}
    for period, sub in stmt.items():
        for k, v in sub.items():
            seen.setdefault(k, {})[period] = v
    exact = seen.get(col)
    if exact:
        return exact
    for k, v in seen.items():
        if col in k:
            return v
    return None


def _get_employee_result(code: str) -> dict:
    """获取员工数，统一返回带 note 的结构（A 股无可靠接口时标注缺口）。

    Args:
        code: 6 位股票代码。

    Returns:
        {"value": 员工数或 None, "note": 来源/缺口说明}。
    """
    func = _get_asr_func("employee_count")
    if func is None:
        return {"value": None, "note": "财务缓存层不可用"}
    return func(code)


def get_advanced_indicators(code: str, names) -> dict:
    """从缓存报表层获取高级科目（同报表只拉取一次，复用缓存）。

    员工数/应付账款周转天数等无直接接口的科目统一标注缺口，不静默使用错误数据。

    Args:
        code: 6 位股票代码。
        names: 需获取的高级科目名列表。

    Returns:
        {科目: {日期: 值}}；无直接接口或未匹配到返回 {"note": ...}；
        并在键 "_cache" 附带各报表缓存状态（hit/refresh/stale）。
    """
    result: dict = {}
    by_src: dict = {}
    for name in names:
        if name in ADVANCED_SOURCES:
            fn, col = ADVANCED_SOURCES[name]
            by_src.setdefault(fn, []).append((name, col))
        elif name in ("员工总数", "员工人数", "员工"):
            result[name] = _get_employee_result(code)
        elif name == "应付账款周转天数":
            result[name] = {"note": "应付账款周转天数无直接接口，可用应付账款/营业成本自行推算"}
        else:
            result[name] = {"note": f"未知高级科目: {name}"}

    for fn, items in by_src.items():
        func = _get_asr_func(fn)
        if func is None:
            for n, _ in items:
                result[n] = {"note": "财务缓存层不可用 (a_stock_cache 未导入)"}
            continue
        try:
            stmt = func(code)
        except Exception as e:  # noqa: BLE001
            for n, _ in items:
                result[n] = {"note": f"获取失败: {type(e).__name__}"}
            continue
        for n, col in items:
            series = _find_col(stmt, col)
            result[n] = series if series is not None else {"note": f"报表中未找到科目: {col}"}

    # 附带各报表缓存状态（hit/refresh/stale）
    status_fn = getattr(a_stock_cache, "get_financial_status", None) if a_stock_cache else None
    if status_fn:
        result["_cache"] = {_FUNC_TO_CACHE_KEY.get(fn, fn):
                            status_fn(_FUNC_TO_CACHE_KEY.get(fn, fn))
                            for fn in by_src}
    return result


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
  %(prog)s --code 300502 --advanced 合同负债,存货,研发费用,员工总数

可用指标: ROE, 毛利率, 净利率, 经营现金流, 净利润, 资产负债率,
          基本每股收益, 每股经营现金流, 每股净资产, 期间费用率
          all - 显示全部原始指标
          --advanced 高级科目（详见 --help）
        """)

    parser.add_argument("--code", type=str, required=True, metavar="CODE",
                        help="股票代码 (必填)")
    parser.add_argument("--indicator", type=str, default=None, metavar="INDICATOR",
                        help='指标名称或 "all" (默认显示关键指标)')
    parser.add_argument("--advanced", type=str, default=None, metavar="SUBJECT",
                        help="获取高级科目（trend-tech-screen 阶段二）。可用科目: 合同负债, 存货, "
                             "开发支出, 无形资产, 应付账款, 应付票据及应付账款, 预付款项, 研发费用, "
                             "营业成本, 支付给职工现金, 购建固定资产现金, 存货周转天数, "
                             "应收账款周转天数, 应付账款周转天数, 员工总数。逗号分隔，缺失科目标注缺口不阻断")

    args = parser.parse_args()
    code = args.code.zfill(6)

    if args.advanced:
        requested = [x.strip() for x in args.advanced.split(",") if x.strip()]
        adv = get_advanced_indicators(code, requested)
        output = {
            "success": True,
            "data": {"advanced": adv},
            "meta": {
                "tool": "stock_financial",
                "code": code,
                "command": "advanced",
                "subjects": requested,
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False, default=str))
        return

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

            # 获取业绩报表中的最新数据
            from datetime import datetime as dt
            now = dt.now()
            y, m = now.year, now.month
            if m <= 3:
                q_date = f"{y-1}1231"
            elif m <= 6:
                q_date = f"{y}0331"
            elif m <= 9:
                q_date = f"{y}0630"
            else:
                q_date = f"{y}0930"

            industry_info = {}
            try:
                yjbb = ak.stock_yjbb_em(date=q_date)
                sub = yjbb[yjbb["股票代码"] == code]
                if not sub.empty:
                    row = sub.iloc[0]
                    industry_info = {
                        "行业": row.get("所处行业", ""),
                        "ROE_latest": float(row.get("净资产收益率", 0)) if row.get("净资产收益率") else None,
                        "毛利率_latest": float(row.get("销售毛利率", 0)) if row.get("销售毛利率") else None,
                        "每股收益_latest": float(row.get("每股收益", 0)) if row.get("每股收益") else None,
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
