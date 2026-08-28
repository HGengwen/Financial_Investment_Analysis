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

Usage:
    {py} tools/hk_stock/stock_info.py --list
    {py} tools/hk_stock/stock_info.py --search 腾讯
    {py} tools/hk_stock/stock_info.py --code 00700
    {py} tools/hk_stock/stock_info.py --hot

财务指标查询请使用: tools/hk_stock/stock_financial.py
"""

import argparse
import json
import os
import re
import subprocess
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
        dict: 包含港股基本信息和实时行情的字典；未找到时返回 None
    """
    try:
        # 使用新浪接口获取港股实时行情（东方财富接口经常被限流）
        api_name = "ak.stock_hk_spot()"
        print(f"正在获取港股实时行情 - API: {api_name}", file=sys.stderr)

        df = safe_api_call(ak.stock_hk_spot, api_name, max_retries=3, delay=2.0)

        # 新浪接口字段名映射（可能与东方财富接口不同）
        # 新浪接口常见字段：['序号', '代码', '名称', '最新价', '涨跌额', '涨跌幅',
        #                   '今开', '昨收', '最高', '最低', '成交量', '成交额', ...]
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
# 市值与研报覆盖（阶段三任务2：总市值 + 研报/机构覆盖）
# ---------------------------------------------------------------------------

def get_hk_valuation(code):
    """获取港股总市值（单位：亿港元，百度历史估值接口 `stock_hk_valuation_baidu`）。

    港股流通市值接口（百度）不支持，故仅提供总市值，流通市值按缺口标注。

    Args:
        code: 5 位港股代码。

    Returns:
        dict: {"market_cap", "currency", "unit", "gap"}。
    """
    code = code.zfill(5)
    result = {"market_cap": None, "currency": "HKD", "unit": "亿港元", "gap": {}}
    try:
        df = ak.stock_hk_valuation_baidu(symbol=code, indicator="总市值")
        if df is not None and not df.empty and "value" in df.columns:
            value = df["value"].dropna()
            if len(value):
                result["market_cap"] = float(value.iloc[-1])
    except Exception:
        result["gap"]["market_cap"] = "百度港股估值接口获取失败"
    return result


def _extract_institutions(texts):
    """从文本列表中正则抽取机构名（如 某某证券/某某投行），去重保序。

    仅匹配以"证券/投行"结尾的机构名（券商/投行是研报覆盖的核心信号），
    避免"资本/研究/国际"等财经高频词造成的误匹配。

    Args:
        texts: 待匹配文本列表（标题/站点/摘要等）。

    Returns:
        list: 去重后的机构名（按首次出现顺序）。
    """
    if not texts:
        return []
    pattern = re.compile(r"[\u4e00-\u9fa5]{2,8}(?:证券|投行)")
    seen = []
    for text in texts:
        if not text:
            continue
        for match in pattern.findall(text):
            if match not in seen:
                seen.append(match)
    return seen


def get_hk_coverage(code, name=""):
    """港股研报/机构覆盖（半自动，doubao 搜索统计，标注缺口）。

    通过 subprocess 调用 `tools/common/doubao_search.py --finance --json`，
    从结果标题/站点/摘要中正则抽取机构名去重计数，作为机构覆盖的近似。

    Args:
        code: 5 位港股代码。
        name: 公司名称（用于更精准的搜索关键词）。

    Returns:
        dict: {"total_results", "coverage_institutions", "coverage_count", "gap"}。
    """
    code = code.zfill(5)
    proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(proj, "tools", "common", "doubao_search.py")
    query = f"{name} 研报 覆盖" if name else f"{code} 港股 研报 覆盖"
    try:
        proc = subprocess.run(
            [sys.executable, script, query, "--finance", "--json", "--count", "20"],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=proj,
        )
    except Exception as e:
        return {"total_results": 0, "coverage_institutions": [],
                "coverage_count": 0, "gap": {"coverage": f"doubao 调用失败: {e}"}}
    if proc.returncode != 0:
        return {"total_results": 0, "coverage_institutions": [],
                "coverage_count": 0, "gap": {"coverage": f"doubao 非零退出({proc.returncode})"}}
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return {"total_results": 0, "coverage_institutions": [],
                "coverage_count": 0, "gap": {"coverage": "doubao 输出非 JSON"}}
    web_results = (data.get("Result") or {}).get("WebResults") or []
    texts = []
    for item in web_results:
        texts.append(str(item.get("Title", "")))
        texts.append(str(item.get("SiteName", "")))
        texts.append(str(item.get("Summary", "")))
    institutions = _extract_institutions(texts)
    return {"total_results": len(web_results),
            "coverage_institutions": institutions,
            "coverage_count": len(institutions),
            "gap": {}}


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


def cmd_profile(code):
    """--profile: 查询港股完整画像（实时行情 + 总市值 + 研报/机构覆盖）。"""
    if not code:
        print(json.dumps({
            "success": False,
            "error": "请提供港股代码，例如: --profile 00700",
            "meta": {"tool": "stock_info_hk", "command": "profile",
                     "timestamp": datetime.now().isoformat()}
        }, ensure_ascii=False))
        sys.exit(1)

    code = code.zfill(5)
    try:
        info = get_hk_stock_info(code) or {}
        valuation = get_hk_valuation(code)
        name = info.get("name", "")
        coverage = get_hk_coverage(code, name)
        data = dict(info)
        data["market_cap"] = valuation["market_cap"]
        data["valuation_gap"] = valuation["gap"] or None
        data["coverage"] = coverage
        output = {
            "success": True,
            "data": data,
            "meta": {
                "tool": "stock_info_hk",
                "command": "profile",
                "code": code,
                "market": "hk",
                "timestamp": datetime.now().isoformat()
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"画像查询失败: {e}",
            "detail": traceback.format_exc(),
            "meta": {"tool": "stock_info_hk", "command": "profile",
                     "timestamp": datetime.now().isoformat()}
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
  %(prog)s --profile 00700       # 查询完整画像(市值+研报覆盖)
  %(prog)s --hot                 # 获取港股人气热度榜

财务指标查询请使用: tools/hk_stock/stock_financial.py
        """)

    parser.add_argument("--list", action="store_true", help="列出全部港股代码和名称")
    parser.add_argument("--search", type=str, default=None, metavar="KEYWORD",
                        help="按名称关键词搜索港股")
    parser.add_argument("--code", type=str, default=None, metavar="CODE",
                        help="查询单只港股详细信息（5位代码，如00700）")
    parser.add_argument("--profile", type=str, default=None, metavar="CODE",
                        help="查询完整画像（实时行情+总市值+研报/机构覆盖）")
    parser.add_argument("--hot", action="store_true", help="获取港股人气热度榜")

    args = parser.parse_args()

    # 确保至少一个操作
    if not args.list and not args.search and not args.code and not args.hot \
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
    elif args.hot:
        cmd_hot()


if __name__ == "__main__":
    main()
