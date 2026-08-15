#!/usr/bin/env python3
"""港股股票代码列表本地缓存模块（港股数据缓存）。

本模块位于 tools/common/ 目录下，为港股数据工具（stock_info 等）提供
「代码/名称列表」的本地 CSV 缓存，并封装全市场 spot 行情的实时拉取
（双源回退），避免每次查询都调用 akshare 拉取全量港股列表（约 2800 只）。

设计要点：
- 缓存文件位于工作区根目录 data/hk_stock/ 下
- 数据源双源回退：
    1. 新浪财经 ak.stock_hk_spot() —— 主源（实测稳定，2797 只）
    2. 东方财富 ak.stock_hk_spot_em() —— 备源（网络恢复时互补）
    3. 硬编码主要港股列表 —— 最后兜底
- 列表缓存 TTL：复用 .env 的 STOCK_CACHE_TTL_DAYS（默认 7 天）
- 列表缓存：TTL + miss 双触发刷新；刷新失败降级返回旧缓存（stale）
- 行情数据（spot）不缓存，保持实时性，仅做单次拉取封装
- 原子写（.tmp + os.replace）、损坏 CSV 回退，与 A 股 a_stock_cache 同模式

Usage:
    from tools.common import hk_stock_cache

    # 获取全部港股代码与名称（优先本地缓存）
    stocks = hk_stock_cache.get_hk_code_name_list()

    # 实时拉取一次全市场 spot 行情（不缓存）
    df = hk_stock_cache.get_hk_spot_dataframe()

    # 读取最近一次列表缓存状态（hit / refresh / stale）
    status = hk_stock_cache.get_hk_code_name_status()
"""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失时降级为不读取 .env
    load_dotenv = None

try:
    import akshare as ak
except ImportError:  # pragma: no cover - 仅刷新缓存时才需要 akshare
    ak = None


# ---------------------------------------------------------------------------
# 路径与配置常量
# ---------------------------------------------------------------------------

# 工作区根目录（本文件位于 tools/common/，向上 3 层到达项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 港股缓存目录与缓存文件
CACHE_DIR = _PROJECT_ROOT / "data" / "hk_stock"
CODE_CACHE_FILE = CACHE_DIR / "stock_code.csv"

# 默认缓存有效期（天），复用 .env 的 STOCK_CACHE_TTL_DAYS
_DEFAULT_TTL_DAYS = 7


def _load_dotenv() -> None:
    """从项目根目录 .env 加载环境变量（若已安装 python-dotenv）。"""
    if load_dotenv is not None:
        load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _parse_int_env(var_name: str, default: int) -> int:
    """从环境变量读取整数配置，非法值或缺失时回退到默认值。

    Args:
        var_name: 环境变量名。
        default: 解析失败时使用的默认值。

    Returns:
        解析后的整数。
    """
    raw = os.getenv(var_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


_load_dotenv()

# 缓存有效期（天），.env 可配置
STOCK_CACHE_TTL_DAYS: int = _parse_int_env("STOCK_CACHE_TTL_DAYS", _DEFAULT_TTL_DAYS)

# 最近一次列表缓存访问状态：hit / refresh / stale
_code_status: str = "unknown"


# ---------------------------------------------------------------------------
# 硬编码兜底列表（最后兜底数据源）
# ---------------------------------------------------------------------------
# 经真实 spot 数据核实修正：00241 为阿里健康（非阿里巴巴-SW）、
# 00669 为创科实业（非中国创新投资）、09988 为阿里巴巴-W。

MAJOR_HK_STOCKS: list[dict] = [
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
    {"code": "00241", "name": "阿里健康", "market": "hk"},
    {"code": "00388", "name": "香港交易所", "market": "hk"},
    {"code": "00669", "name": "创科实业", "market": "hk"},
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
    {"code": "09988", "name": "阿里巴巴-W", "market": "hk"},
    {"code": "00666", "name": "瑞浦兰钧", "market": "hk"},
]


# ---------------------------------------------------------------------------
# 通用工具函数
# ---------------------------------------------------------------------------

def _is_cache_fresh(cache_file: Path, ttl_days: int | None = None) -> bool:
    """判断缓存文件是否在 TTL 有效期之内。

    Args:
        cache_file: 缓存文件路径。
        ttl_days: 有效期（天）；为 None 时使用列表缓存默认 TTL。

    Returns:
        新鲜（未过期）返回 True；文件不存在或已过期返回 False。
    """
    if not cache_file.exists():
        return False
    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
    age = datetime.now() - mtime
    ttl = ttl_days if ttl_days is not None else STOCK_CACHE_TTL_DAYS
    return age.days < ttl


def _atomic_write_csv(df: pd.DataFrame, cache_file: Path) -> None:
    """原子写入 CSV：先写 .tmp 临时文件再 os.replace，避免并发写坏缓存。

    Args:
        df: 待写入的 DataFrame。
        cache_file: 目标缓存文件路径。
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
    df.to_csv(tmp_file, index=False, encoding="utf-8-sig")
    os.replace(tmp_file, cache_file)


# ---------------------------------------------------------------------------
# spot 数据源拉取（新浪主源 → 东财备源）
# ---------------------------------------------------------------------------

def _fetch_spot_from_sina() -> pd.DataFrame:
    """从新浪财经接口拉取全市场港股 spot 行情。

    Returns:
        新浪 spot DataFrame。

    Raises:
        RuntimeError: akshare 未安装或接口调用失败。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取港股数据。请运行: pip install akshare")
    return ak.stock_hk_spot()


def _fetch_spot_from_em() -> pd.DataFrame:
    """从东方财富接口拉取全市场港股 spot 行情（备源）。

    Returns:
        东财 spot DataFrame。

    Raises:
        RuntimeError: 接口调用失败。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取港股数据。请运行: pip install akshare")
    return ak.stock_hk_spot_em()


def get_hk_spot_dataframe() -> pd.DataFrame:
    """实时拉取一次全市场港股 spot 行情（不缓存）。

    按优先级尝试：新浪主源 → 东财备源。两个数据源列名不同，
    调用方需通过 get_hk_spot_row 的字段动态适配逻辑提取数据。

    Returns:
        全市场 spot DataFrame。

    Raises:
        RuntimeError: 两个数据源均获取失败。
    """
    last_error: Exception | None = None
    for fetch in (_fetch_spot_from_sina, _fetch_spot_from_em):
        try:
            df = fetch()
            if df is not None and not df.empty:
                return df
        except Exception as e:  # noqa: BLE001 - 数据源逐个重试，需捕获所有异常
            last_error = e
            continue
    raise RuntimeError(f"港股 spot 数据获取失败（新浪与东方财富均不可用）: {last_error}")


def get_hk_spot_row(df: pd.DataFrame, code: str) -> pd.Series | None:
    """从 spot DataFrame 中按代码查找单只股票（多字段名动态适配）。

    新浪与东财接口的代码列名可能不同（代码/code/symbol/股票代码），
    此处逐一尝试。

    Args:
        df: spot DataFrame。
        code: 港股代码（5 位，如 "00700"）。

    Returns:
        匹配的行；未找到时返回 None。
    """
    code_column = None
    for col in ("代码", "code", "symbol", "股票代码"):
        if col in df.columns:
            code_column = col
            break
    if code_column is None:
        return None
    target = df[df[code_column].astype(str).str.strip() == code]
    if target.empty:
        return None
    return target.iloc[0]


# ---------------------------------------------------------------------------
# 港股代码/名称列表（本地缓存）
# ---------------------------------------------------------------------------

def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """从 spot DataFrame 提取代码/名称记录（含英文名称，如存在）。

    Args:
        df: spot DataFrame（新浪或东财）。

    Returns:
        记录列表 [{"code", "name", "name_en", "market"}, ...]。
    """
    code_column = None
    name_column = None
    name_en_column = None
    for col in ("代码", "code", "symbol", "股票代码"):
        if col in df.columns:
            code_column = col
            break
    for col in ("中文名称", "名称", "name", "股票简称"):
        if col in df.columns:
            name_column = col
            break
    for col in ("英文名称", "name_en", "enname"):
        if col in df.columns:
            name_en_column = col
            break

    if code_column is None or name_column is None:
        raise RuntimeError(f"港股 spot 数据缺少代码/名称列: {list(df.columns)}")

    records = []
    for _, row in df.iterrows():
        code = str(row[code_column]).strip()
        name = str(row[name_column]).strip()
        if code and name:
            record = {
                "code": code,
                "name": name,
                "market": "hk",
            }
            if name_en_column is not None:
                name_en = str(row[name_en_column]).strip()
                if name_en:
                    record["name_en"] = name_en
            records.append(record)
    return records


def _fetch_hk_code_name_list() -> list[dict]:
    """拉取全部港股代码与名称（spot 主源 → 东财备源）。

    Returns:
        记录列表 [{"code", "name", "name_en", "market"}, ...]。

    Raises:
        RuntimeError: 两个 spot 数据源均失败。
    """
    # 尝试 spot 接口（主源/备源），全部失败时抛出
    df = get_hk_spot_dataframe()
    records = _df_to_records(df)
    if not records:
        raise RuntimeError("港股 spot 数据为空")
    return records


def _read_code_csv() -> list[dict] | None:
    """从缓存文件读取全部港股代码与名称。

    Returns:
        记录列表；缓存缺失或解析失败返回 None。
    """
    try:
        df = pd.read_csv(CODE_CACHE_FILE, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
        records = []
        for _, row in df.iterrows():
            record = {
                "code": str(row["code"]).strip(),
                "name": str(row["name"]).strip(),
                "market": "hk",
            }
            if "name_en" in row and str(row["name_en"]).strip():
                record["name_en"] = str(row["name_en"]).strip()
            records.append(record)
        return records if records else None
    except Exception:
        return None


def _write_code_csv(records: list[dict]) -> None:
    """将港股代码/名称记录原子写入缓存文件。

    Args:
        records: [{"code", "name", "name_en", "market"}, ...] 记录列表。
    """
    rows = []
    for rec in records:
        rows.append({
            "code": rec["code"],
            "name": rec["name"],
            "name_en": rec.get("name_en", ""),
            "market": rec["market"],
        })
    _atomic_write_csv(pd.DataFrame(rows), CODE_CACHE_FILE)


def get_hk_code_name_list(force_refresh: bool = False) -> list[dict]:
    """获取全部港股代码与名称（优先本地缓存）。

    查询顺序：
    1. 缓存新鲜且未强制刷新 → 直接读本地（状态 hit）；
    2. 缓存缺失/过期/损坏 → 拉取全量并原子覆写缓存（状态 refresh）；
    3. 刷新失败但存在旧缓存 → 降级返回旧数据（状态 stale）；
    4. 刷新失败且无缓存 → 返回硬编码兜底列表（避免中断调用）。

    Args:
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        记录列表 [{"code", "name", "name_en", "market"}, ...]。
    """
    global _code_status
    if not force_refresh and _is_cache_fresh(CODE_CACHE_FILE):
        cached = _read_code_csv()
        if cached is not None:
            _code_status = "hit"
            return cached
    try:
        records = _fetch_hk_code_name_list()
        _write_code_csv(records)
        _code_status = "refresh"
        return records
    except Exception:
        # 刷新失败（限流/断连）时优先降级返回旧缓存，避免覆盖优质数据
        cached = _read_code_csv()
        if cached is not None:
            _code_status = "stale"
            return cached
        # 无缓存时返回硬编码兜底列表，保证工具不中断
        _code_status = "stale"
        return [dict(item) for item in MAJOR_HK_STOCKS]


def get_hk_code_name_status() -> str:
    """返回最近一次港股列表访问的缓存状态。

    Returns:
        "hit"（缓存命中）/ "refresh"（拉取刷新）/ "stale"（旧缓存降级）。
    """
    return _code_status


# ---------------------------------------------------------------------------
# 港股财务数据（本地缓存）
# ---------------------------------------------------------------------------

# 财务数据缓存目录（按股票分文件，避免大文件全量读写）
FINANCIAL_DIR = CACHE_DIR / "financial"

# 财务数据缓存有效期（天），.env 可配置（HK_FINANCIAL_TTL_DAYS，默认 7 天）
_DEFAULT_FINANCIAL_TTL_DAYS = 7
FINANCIAL_TTL_DAYS: int = _parse_int_env("HK_FINANCIAL_TTL_DAYS", _DEFAULT_FINANCIAL_TTL_DAYS)

# 最近一次财务缓存访问状态：hit / refresh / stale
_financial_status: str = "unknown"


def _financial_cache_file(code: str, kind: str, indicator: str) -> Path:
    """生成港股财务数据缓存文件路径。

    Args:
        code: 港股代码（5 位数字字符串）。
        kind: 数据种类（"indicators" 或报表类型，如 "利润表"）。
        indicator: 指标类型（"年度" / "报告期"）。

    Returns:
        对应的缓存文件路径。
    """
    return FINANCIAL_DIR / f"{code}_{kind}_{indicator}.csv"


def _read_financial_df(cache_file: Path) -> pd.DataFrame | None:
    """从缓存文件读取财务数据 DataFrame。

    Args:
        cache_file: 缓存文件路径。

    Returns:
        DataFrame；缓存缺失或解析失败返回 None。
    """
    try:
        df = pd.read_csv(cache_file, encoding="utf-8-sig")
        return df if not df.empty else None
    except Exception:
        return None


def _fetch_financial_indicators_df(code: str, indicator: str) -> pd.DataFrame:
    """拉取港股财务分析指标原始 DataFrame（不缓存）。

    Args:
        code: 港股代码（5 位数字字符串）。
        indicator: 指标类型（"年度" / "报告期"）。

    Returns:
        财务指标 DataFrame。

    Raises:
        RuntimeError: akshare 未安装或接口调用失败。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取港股财务数据。请运行: pip install akshare")
    return ak.stock_financial_hk_analysis_indicator_em(symbol=code, indicator=indicator)


def _fetch_financial_report_df(code: str, report_type: str, indicator: str) -> pd.DataFrame:
    """拉取港股三大报表原始 DataFrame（不缓存）。

    Args:
        code: 港股代码（5 位数字字符串）。
        report_type: 报表类型（"利润表" / "资产负债表" / "现金流量表"）。
        indicator: 指标类型（"年度" / "报告期"）。

    Returns:
        报表 DataFrame。

    Raises:
        RuntimeError: akshare 未安装或接口调用失败。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取港股财务数据。请运行: pip install akshare")
    return ak.stock_financial_hk_report_em(stock=code, symbol=report_type, indicator=indicator)


def get_financial_indicators(code: str, indicator: str = "年度",
                             force_refresh: bool = False) -> pd.DataFrame:
    """获取港股财务分析指标（优先本地缓存）。

    查询顺序：
    1. 缓存新鲜且未强制刷新 → 直接读本地（状态 hit）；
    2. 缓存缺失/过期/损坏 → 拉取并原子覆写缓存（状态 refresh）；
    3. 刷新失败但存在旧缓存 → 降级返回旧数据（状态 stale）；
    4. 刷新失败且无缓存 → 抛出 RuntimeError（无兜底数据可用）。

    Args:
        code: 港股代码（5 位数字字符串）。
        indicator: 指标类型（"年度" / "报告期"）。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        财务指标原始 DataFrame。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    global _financial_status
    cache_file = _financial_cache_file(code, "indicators", indicator)
    if not force_refresh and _is_cache_fresh(cache_file, FINANCIAL_TTL_DAYS):
        cached = _read_financial_df(cache_file)
        if cached is not None:
            _financial_status = "hit"
            return cached
    try:
        df = _fetch_financial_indicators_df(code, indicator)
        if df is None or df.empty:
            raise RuntimeError(f"港股 {code} 财务指标数据为空")
        _atomic_write_csv(df, cache_file)
        _financial_status = "refresh"
        return df
    except Exception:
        # 刷新失败（限流/断连）时优先降级返回旧缓存
        cached = _read_financial_df(cache_file)
        if cached is not None:
            _financial_status = "stale"
            return cached
        _financial_status = "stale"
        raise


def get_financial_report(code: str, report_type: str, indicator: str = "年度",
                         force_refresh: bool = False) -> pd.DataFrame:
    """获取港股三大报表数据（优先本地缓存）。

    Args:
        code: 港股代码（5 位数字字符串）。
        report_type: 报表类型（"利润表" / "资产负债表" / "现金流量表"）。
        indicator: 指标类型（"年度" / "报告期"）。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        报表原始 DataFrame。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    global _financial_status
    cache_file = _financial_cache_file(code, report_type, indicator)
    if not force_refresh and _is_cache_fresh(cache_file, FINANCIAL_TTL_DAYS):
        cached = _read_financial_df(cache_file)
        if cached is not None:
            _financial_status = "hit"
            return cached
    try:
        df = _fetch_financial_report_df(code, report_type, indicator)
        if df is None or df.empty:
            raise RuntimeError(f"港股 {code} {report_type}数据为空")
        _atomic_write_csv(df, cache_file)
        _financial_status = "refresh"
        return df
    except Exception:
        # 刷新失败（限流/断连）时优先降级返回旧缓存
        cached = _read_financial_df(cache_file)
        if cached is not None:
            _financial_status = "stale"
            return cached
        _financial_status = "stale"
        raise


def get_financial_status() -> str:
    """返回最近一次港股财务数据访问的缓存状态。

    Returns:
        "hit"（缓存命中）/ "refresh"（拉取刷新）/ "stale"（旧缓存降级）。
    """
    return _financial_status
