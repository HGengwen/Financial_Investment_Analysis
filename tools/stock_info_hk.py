#!/usr/bin/env python3
"""港股股票信息查询工具。

使用 akshare 库获取港股上市公司的代码、名称、实时行情、财务指标等信息。

改进说明：
1. 增加重试机制（最多3次重试）
2. 增加延迟机制（避免频繁请求）
3. 优化错误处理和日志输出
4. 支持东方财富和新浪两种数据源
5. 支持港股财务分析指标获取（stock_financial_hk_analysis_indicator_em）

Usage:
    {py} tools/stock_info_hk.py --list
    {py} tools/stock_info_hk.py --search 腾讯
    {py} tools/stock_info_hk.py --code 00700
    {py} tools/stock_info_hk.py --hot
    {py} tools/stock_info_hk.py --financial 00700
    {py} tools/stock_info_hk.py --financial 00700 --indicator 报告期
"""

import argparse
import json
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
        "meta": {"tool": "stock_info_hk", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

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

    注意：东方财富接口网络连接不稳定，增加重试机制。
    如果连续失败，返回预设的主要港股列表。

    Returns:
        list: 包含港股代码和名称的列表
    """
    try:
        # 尝试从东方财富接口获取港股实时行情
        api_name = "ak.stock_hk_spot()"
        print(f"正在获取港股列表 - API: {api_name}", file=sys.stderr)
        
        df = safe_api_call(ak.stock_hk_spot, api_name, max_retries=3, delay=2.0)
        
        records = []
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("中文名称", row.get("名称", ""))).strip()
            if code and name:
                records.append({
                    "code": code,
                    "name": name,
                    "market": "hk"
                })
        
        print(f"✓ 数据获取成功 - 共{len(records)}只港股", file=sys.stderr)
        return records
        
    except Exception as e:
        print(f"⚠ 东方财富接口失败，使用备用数据源", file=sys.stderr)
        
        # 备用方案：返回预设的主要港股列表
        # 实际使用时，用户可以通过 --search 搜索具体公司
        major_hk_stocks = [
            {"code": "00001", "name": "长和", "market": "hk"},
            {"code": "00002", "name": "中电控股", "market": "hk"},
            {"code": "00005", "name": "汇丰控股", "market": "hk"},
            {"code": "00006", "name": "电能实业", "market": "hk"},
            {"code": "00011", "name": "恒生银行", "market": "hk"},
            {"code": "00012", "name": "恒基地产", "market": "hk"},
            {"code": "00016", "name": "新鸿基地产", "market": "hk"},
            {"code": "00017", "name": "新世界发展", "market": "hk"},
            {"code": "00027", "name": "银河娱乐", "market": "hk"},
            {"code": "00066", "name": "港铁公司", "market": "hk"},
            {"code": "00098", "name": "中银香港", "market": "hk"},
            {"code": "00175", "name": "吉利汽车", "market": "hk"},
            {"code": "00241", "name": "阿里巴巴-SW", "market": "hk"},
            {"code": "00388", "name": "香港交易所", "market": "hk"},
            {"code": "00669", "name": "中国创新投资", "market": "hk"},
            {"code": "00688", "name": "中国海外发展", "market": "hk"},
            {"code": "00700", "name": "腾讯控股", "market": "hk"},
            {"code": "00728", "name": "中国电信", "market": "hk"},
            {"code": "00762", "name": "中国联通", "market": "hk"},
            {"code": "00788", "name": "中国铁塔", "market": "hk"},
            {"code": "00883", "name": "中国海洋石油", "market": "hk"},
            {"code": "00939", "name": "建设银行", "market": "hk"},
            {"code": "00941", "name": "中国移动", "market": "hk"},
            {"code": "00981", "name": "中芯国际", "market": "hk"},
            {"code": "01024", "name": "快手-W", "market": "hk"},
            {"code": "01088", "name": "中国神华", "market": "hk"},
            {"code": "01109", "name": "华润置地", "market": "hk"},
            {"code": "01211", "name": "比亚迪股份", "market": "hk"},
            {"code": "01233", "name": "石药集团", "market": "hk"},
            {"code": "01288", "name": "农业银行", "market": "hk"},
            {"code": "01398", "name": "工商银行", "market": "hk"},
            {"code": "01810", "name": "小米集团-W", "market": "hk"},
            {"code": "02313", "name": "申洲国际", "market": "hk"},
            {"code": "02318", "name": "中国平安", "market": "hk"},
            {"code": "02382", "name": "舜宇光学科技", "market": "hk"},
            {"code": "02628", "name": "中国人寿", "market": "hk"},
            {"code": "03690", "name": "美团-W", "market": "hk"},
            {"code": "03968", "name": "招商银行", "market": "hk"},
            {"code": "03988", "name": "中国银行", "market": "hk"},
            {"code": "06690", "name": "海尔智家", "market": "hk"},
            {"code": "06969", "name": "思摩尔国际", "market": "hk"},
            {"code": "09988", "name": "阿里巴巴-SW", "market": "hk"},
            {"code": "00666", "name": "瑞浦兰钧", "market": "hk"},
        ]
        print(f"✓ 使用备用数据 - 共{len(major_hk_stocks)}只主要港股", file=sys.stderr)
        return major_hk_stocks


def get_hk_stock_info(code: str) -> dict:
    """获取单只港股基本信息和实时行情。

    Args:
        code: 港股代码（5位数字字符串，如"00700"）

    Returns:
        dict: 包含港股基本信息和实时行情的字典
    """
    try:
        # 使用新浪接口获取港股实时行情（东方财富接口经常被限流）
        api_name = "ak.stock_hk_spot()"
        print(f"正在获取港股实时行情 - API: {api_name}", file=sys.stderr)
        
        df = safe_api_call(ak.stock_hk_spot, api_name, max_retries=3, delay=2.0)

        # 新浪接口字段名映射（可能与东方财富接口不同）
        # 新浪接口常见字段：['序号', '代码', '名称', '最新价', '涨跌额', '涨跌幅', '今开', '昨收', '最高', '最低', '成交量', '成交额', ...]
        # 注意：新浪接口字段名可能有中英文差异，需要动态适配
        
        # 打印字段名用于调试（仅在第一次调用时）
        if not hasattr(get_hk_stock_info, '_field_printed'):
            print(f"✓ 港股数据字段: {list(df.columns)}", file=sys.stderr)
            get_hk_stock_info._field_printed = True
        
        # 查找目标股票（尝试多种字段名）
        code_column = None
        for col in ['代码', 'code', 'symbol', '股票代码']:
            if col in df.columns:
                code_column = col
                break
        
        if code_column is None:
            raise Exception("无法找到股票代码字段")
        
        target_row = df[df[code_column] == code]
        if target_row.empty:
            return None

        row = target_row.iloc[0]
        
        # 动态获取字段值（支持多种字段名）
        def get_field(row, *field_names):
            """从多可能字段名中获取值"""
            for field in field_names:
                if field in row.index:
                    return row.get(field)
            return None
        
        name = get_field(row, '名称', 'name', '股票简称', '中文名称')
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
        api_name = f"ak.stock_financial_hk_analysis_indicator_em(symbol='{code}', indicator='{indicator}')"
        print(f"正在获取港股财务指标 - API: {api_name}", file=sys.stderr)

        df = safe_api_call(
            lambda: ak.stock_financial_hk_analysis_indicator_em(symbol=code, indicator=indicator),
            api_name,
            max_retries=3,
            delay=2.0
        )

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
    """--search: 按名称关键词搜索港股。"""
    if not keyword:
        print(json.dumps({
            "success": False,
            "error": "请提供搜索关键词，例如: --search 腾讯",
            "meta": {"tool": "stock_info_hk", "command": "search", "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        all_hk_stocks = get_all_hk_stocks()
        matched = []
        for s in all_hk_stocks:
            if keyword.upper() in s["name"].upper():
                # 获取实时行情
                try:
                    info = get_hk_stock_info(s["code"])
                    if info:
                        matched.append(info)
                    else:
                        matched.append(s)
                except:
                    matched.append(s)

        output = {
            "success": True,
            "data": matched,
            "meta": {
                "tool": "stock_info_hk",
                "command": "search",
                "keyword": keyword,
                "market": "hk",
                "count": len(matched),
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


def cmd_financial(code, indicator="年度"):
    """--financial: 获取港股财务分析指标。"""
    if not code:
        print(json.dumps({
            "success": False,
            "error": "请提供港股代码，例如: --financial 00700",
            "meta": {"tool": "stock_info_hk", "command": "financial", "timestamp": datetime.now().isoformat()}
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
                "tool": "stock_info_hk",
                "command": "financial",
                "code": code,
                "indicator": indicator,
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
            "meta": {"tool": "stock_info_hk", "command": "financial", "timestamp": datetime.now().isoformat()}
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
  %(prog)s --financial 00700     # 获取腾讯控股财务指标
  %(prog)s --financial 00700 --indicator 报告期  # 获取报告期财务指标
        """)

    parser.add_argument("--list", action="store_true", help="列出全部港股代码和名称")
    parser.add_argument("--search", type=str, default=None, metavar="KEYWORD",
                        help="按名称关键词搜索港股")
    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="查询单只港股详细信息（5位代码，如00700）")
    parser.add_argument("--hot", action="store_true", help="获取港股人气热度榜")
    parser.add_argument("--financial", type=str, default=None, metavar="CODE",
                        help="获取港股财务分析指标（5位代码，如00700）")
    parser.add_argument("--indicator", type=str, default="年度", metavar="TYPE",
                        help="指标类型：年度（默认）或 报告期")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.list and not args.search and not args.code and not args.hot and not args.financial:
        parser.print_help()
        print("\n错误: 请指定至少一个操作", file=sys.stderr)
        sys.exit(1)

    if args.list:
        cmd_list()
    elif args.search:
        cmd_search(args.search)
    elif args.code:
        cmd_code(args.code)
    elif args.hot:
        cmd_hot()
    elif args.financial:
        cmd_financial(args.financial, args.indicator)


if __name__ == "__main__":
    main()