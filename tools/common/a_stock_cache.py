#!/usr/bin/env python3
"""A股股票代码与行业数据本地缓存模块（A股数据缓存）。

本模块位于 tools/common/ 目录下，为 A 股数据工具（stock_info、stock_screen、
stock_financial 等）提供「代码/名称列表」与「最新季度业绩数据」的本地 CSV 缓存，
避免每次查询都调用 akshare API 拉取全量数据（约 5700 行），从而：

1. 提升查询效率 —— 缓存命中时零网络调用，纯本地读取；
2. 规避 akshare 限流 —— 大幅减少对 stock_info_a_code_name / stock_yjbb_em
   的调用次数（akshare 的 RemoteDisconnected 即服务端封禁信号）。

设计要点：
- 缓存文件位于工作区根目录 data/a_share/ 下（与 .env 同级）
- TTL 判定：以缓存文件 mtime 判断是否过期（默认 7 天，.env 的
  STOCK_CACHE_TTL_DAYS 可配置）
- TTL + miss 双触发刷新：
    - 缓存新鲜 → 直接读本地（状态 hit）
    - 缓存缺失/过期 → 拉取全量并原子覆写缓存（状态 refresh）
    - 刷新失败（限流/断连）→ 降级返回旧缓存并标注 stale
- 原子写：先写 .tmp 临时文件再 os.replace，避免并发写坏缓存
- 损坏回退：CSV 解析失败视为缓存缺失，重新拉取并覆写

Usage:
    from tools.common import a_stock_cache

    # 获取全部 A 股代码与名称（默认走缓存）
    stocks = a_stock_cache.get_code_name_list()

    # 获取行业/ROE/毛利率/EPS 映射（按股票代码为键）
    industry_map = a_stock_cache.get_industry_map()

    # 强制刷新缓存
    stocks = a_stock_cache.get_code_name_list(force_refresh=True)

    # 读取最近一次缓存状态（hit / refresh / stale）
    status = a_stock_cache.get_code_name_status()
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

# A 股缓存目录与缓存文件
CACHE_DIR = _PROJECT_ROOT / "data" / "a_share"
CODE_CACHE_FILE = CACHE_DIR / "stock_code.csv"
INDUSTRY_CACHE_FILE = CACHE_DIR / "stock_industry.csv"

# 默认缓存有效期（天），可通过 .env 的 STOCK_CACHE_TTL_DAYS 配置
_DEFAULT_TTL_DAYS = 7

# 行业数据有效性阈值（与 stock_info.py 原逻辑保持一致）
_INDUSTRY_MIN_ROWS = 1000  # 全市场业绩报表至少 1000 行
_INDUSTRY_MIN_VALID = 100  # 至少 100 只股票有行业字段


def _load_dotenv() -> None:
    """从项目根目录 .env 加载环境变量（若已安装 python-dotenv）。

    本文件位于 tools/common/ 下，需向上 3 层到达项目根目录。
    """
    if load_dotenv is not None:
        load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _parse_int_env(var_name: str, default: int) -> int:
    """从环境变量读取整数配置，非法值或缺失时回退到默认值。

    遵循「配置失败不影响功能」原则：遇到空串、非数字等一律回退 default，
    避免 .env 笔误导致工具无法运行。

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

# 最近一次缓存访问状态：hit（缓存命中）/ refresh（拉取刷新）/ stale（旧缓存降级）
_code_status: str = "unknown"
_industry_status: str = "unknown"


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


def _to_float_or_none(value) -> float | None:
    """将 CSV 单元格值转换为 float，空值/非法值转换为 None。

    Args:
        value: 原始单元格值（可能为 None、空字符串或数字字符串）。

    Returns:
        可转换的 float；否则返回 None。
    """
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in ("nan", "none"):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 代码/名称列表
# ---------------------------------------------------------------------------

def _read_code_csv() -> list[dict] | None:
    """从缓存文件读取全部 A 股代码与名称。

    Returns:
        记录列表 [{"code", "name", "market"}, ...]；缓存缺失或解析失败返回 None。
    """
    try:
        df = pd.read_csv(CODE_CACHE_FILE, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
        records = []
        for _, row in df.iterrows():
            records.append({
                "code": str(row["code"]).zfill(6),
                "name": str(row["name"]).strip(),
                "market": "a",
            })
        # 空文件视为损坏，返回 None 触发重新拉取
        return records if records else None
    except Exception:
        return None


def _write_code_csv(records: list[dict]) -> None:
    """将代码/名称记录原子写入缓存文件。

    Args:
        records: [{"code", "name", "market"}, ...] 记录列表。
    """
    _atomic_write_csv(pd.DataFrame(records), CODE_CACHE_FILE)


def _fetch_code_name_list() -> list[dict]:
    """调用 akshare 拉取全部 A 股代码与名称。

    Returns:
        记录列表 [{"code", "name", "market"}, ...]。

    Raises:
        RuntimeError: akshare 未安装、接口调用失败或返回空列表。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取 A 股列表。请运行: pip install akshare")
    df = ak.stock_info_a_code_name()
    records = []
    for _, row in df.iterrows():
        records.append({
            "code": str(row["code"]).zfill(6),
            "name": str(row["name"]).strip(),
            "market": "a",
        })
    if not records:
        raise RuntimeError("akshare 返回的 A 股列表为空")
    return records


def get_code_name_list(force_refresh: bool = False) -> list[dict]:
    """获取全部 A 股代码与名称（优先本地缓存）。

    查询顺序：
    1. 缓存新鲜且未强制刷新 → 直接读本地（状态 hit）；
    2. 缓存缺失/过期/损坏 → 拉取全量并原子覆写缓存（状态 refresh）；
    3. 刷新失败但存在旧缓存 → 降级返回旧数据（状态 stale）；
    4. 刷新失败且无缓存 → 向上抛出异常。

    Args:
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        记录列表 [{"code", "name", "market"}, ...]。
    """
    global _code_status
    if not force_refresh and _is_cache_fresh(CODE_CACHE_FILE):
        cached = _read_code_csv()
        if cached is not None:
            _code_status = "hit"
            return cached
    try:
        records = _fetch_code_name_list()
        _write_code_csv(records)
        _code_status = "refresh"
        return records
    except Exception:
        # 刷新失败（限流/断连）时降级返回旧缓存
        cached = _read_code_csv()
        if cached is not None:
            _code_status = "stale"
            return cached
        raise


def get_code_name_status() -> str:
    """返回最近一次代码列表访问的缓存状态。

    Returns:
        "hit"（缓存命中）/ "refresh"（拉取刷新）/ "stale"（旧缓存降级）。
    """
    return _code_status


# ---------------------------------------------------------------------------
# 行业业绩数据
# ---------------------------------------------------------------------------

def _fetch_industry_data() -> tuple[dict, str]:
    """调用 akshare 拉取最新有效季度的业绩报表（行业/ROE/毛利率/EPS）。

    按优先顺序尝试最近 3 个季度末日期，取第一个通过有效性校验
    （>1000 行且 >100 只股票有行业字段）的数据。

    Returns:
        二元组 (结果字典, 命中的季度字符串)。
        结果字典键为 6 位股票代码，值为
        {"code", "name", "market", "industry", "roe", "gross_margin", "eps", "quarter"}。

    Raises:
        RuntimeError: 全部候选季度均获取失败。
    """
    now = datetime.now()
    year, month = now.year, now.month

    # 按优先顺序生成季度末日期列表（最近的季度 -> 前一个季度 -> ...）
    if month <= 3:
        date_candidates = [f"{year - 1}1231", f"{year - 1}0930", f"{year - 1}0630"]
    elif month <= 6:
        date_candidates = [f"{year}0331", f"{year - 1}1231", f"{year - 1}0930"]
    elif month <= 9:
        date_candidates = [f"{year}0630", f"{year}0331", f"{year - 1}1231"]
    else:
        date_candidates = [f"{year}0930", f"{year}0630", f"{year}0331"]

    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取行业数据。请运行: pip install akshare")

    last_error: Exception | None = None
    for date_str in date_candidates:
        try:
            df = ak.stock_yjbb_em(date=date_str)
            if len(df) > _INDUSTRY_MIN_ROWS:
                # 检查行业字段是否有足够有效数据
                valid = df[df["所处行业"].notna() & (df["所处行业"] != "")]
                if len(valid) > _INDUSTRY_MIN_VALID:
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
                            "quarter": date_str,
                        }
                    return result, date_str
        except Exception as e:  # noqa: BLE001 - 季度候选逐个重试，需捕获所有异常
            last_error = e
            continue
    raise RuntimeError(f"全部季度业绩数据获取失败: {date_candidates}；最近错误: {last_error}")


def _read_industry_csv() -> dict[str, dict] | None:
    """从缓存文件读取行业业绩映射。

    Returns:
        以股票代码为键的行业数据字典；缓存缺失或解析失败时返回 None。
    """
    try:
        df = pd.read_csv(INDUSTRY_CACHE_FILE, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
        # 兼容旧版本缓存：缺失 quarter 列时补空
        if "quarter" not in df.columns:
            df["quarter"] = ""
        result = {}
        for _, row in df.iterrows():
            code = str(row["code"]).zfill(6)
            result[code] = {
                "code": code,
                "name": str(row["name"]).strip(),
                "market": "a",
                "industry": str(row["industry"]).strip(),
                "roe": _to_float_or_none(row["roe"]),
                "gross_margin": _to_float_or_none(row["gross_margin"]),
                "eps": _to_float_or_none(row["eps"]),
                "quarter": str(row["quarter"]).strip(),
            }
        # 空文件视为损坏，返回 None 触发重新拉取
        return result if result else None
    except Exception:
        return None


def _write_industry_csv(industry_map: dict[str, dict], quarter: str) -> None:
    """将行业业绩映射原子写入缓存文件。

    Args:
        industry_map: 以股票代码为键的行业数据字典。
        quarter: 命中的季度字符串（如 "20260331"）。
    """
    rows = []
    for code, rec in industry_map.items():
        rows.append({
            "code": code,
            "name": rec["name"],
            "industry": rec["industry"],
            "roe": rec["roe"],
            "gross_margin": rec["gross_margin"],
            "eps": rec["eps"],
            "quarter": quarter,
        })
    _atomic_write_csv(pd.DataFrame(rows), INDUSTRY_CACHE_FILE)


def get_industry_map(force_refresh: bool = False) -> dict[str, dict]:
    """获取最新季度行业业绩映射（优先本地缓存）。

    查询顺序与 get_code_name_list 相同（hit → refresh → stale）。

    Args:
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        以 6 位股票代码为键的行业数据字典。
    """
    global _industry_status
    if not force_refresh and _is_cache_fresh(INDUSTRY_CACHE_FILE):
        cached = _read_industry_csv()
        if cached is not None:
            _industry_status = "hit"
            return cached
    try:
        industry_map, quarter = _fetch_industry_data()
        _write_industry_csv(industry_map, quarter)
        _industry_status = "refresh"
        return industry_map
    except Exception:
        # 刷新失败（限流/断连）时降级返回旧缓存
        cached = _read_industry_csv()
        if cached is not None:
            _industry_status = "stale"
            return cached
        raise


def get_industry_status() -> str:
    """返回最近一次行业数据访问的缓存状态。

    Returns:
        "hit"（缓存命中）/ "refresh"（拉取刷新）/ "stale"（旧缓存降级）。
    """
    return _industry_status


# ---------------------------------------------------------------------------
# A股财务数据（本地缓存）
# ---------------------------------------------------------------------------

# 财务数据缓存目录（按股票分文件，避免大文件全量读写）
FINANCIAL_DIR = CACHE_DIR / "financial"

# 财务数据缓存有效期（天），.env 可配置
_DEFAULT_FINANCIAL_TTL_DAYS = 7  # 财务摘要/利润表（季报披露节奏）
_DEFAULT_IPO_TTL_DAYS = 90       # IPO 信息（上市后永不变，长 TTL 仅作自愈兜底）
FINANCIAL_TTL_DAYS: int = _parse_int_env("A_FINANCIAL_TTL_DAYS", _DEFAULT_FINANCIAL_TTL_DAYS)
IPO_TTL_DAYS: int = _parse_int_env("A_IPO_TTL_DAYS", _DEFAULT_IPO_TTL_DAYS)

# 最近一次财务缓存访问状态：hit / refresh / stale
_financial_status: str = "unknown"


def _financial_cache_file(code: str, kind: str) -> Path:
    """生成 A 股财务数据缓存文件路径。

    Args:
        code: 股票代码（6 位数字字符串）。
        kind: 数据种类（"ipo" / "abstract" / "利润表"）。

    Returns:
        对应的缓存文件路径。
    """
    return FINANCIAL_DIR / f"{code}_{kind}.csv"


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


def _fetch_ipo_df(code: str) -> pd.DataFrame:
    """拉取 A 股 IPO 信息原始 DataFrame（不缓存）。

    Args:
        code: 股票代码（6 位数字字符串）。

    Returns:
        IPO 信息 DataFrame。

    Raises:
        RuntimeError: akshare 未安装或接口调用失败。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取 A 股 IPO 信息。请运行: pip install akshare")
    return ak.stock_ipo_info(stock=code)


def _fetch_financial_abstract_df(symbol: str) -> pd.DataFrame:
    """拉取 A 股财务摘要原始 DataFrame（不缓存）。

    Args:
        symbol: 股票代码（6 位数字字符串）。

    Returns:
        财务摘要 DataFrame。

    Raises:
        RuntimeError: akshare 未安装或接口调用失败。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取 A 股财务摘要。请运行: pip install akshare")
    return ak.stock_financial_abstract(symbol=symbol)


def _fetch_income_statement_df(code: str) -> pd.DataFrame:
    """拉取 A 股利润表原始 DataFrame（新浪接口，不缓存）。

    Args:
        code: 股票代码（6 位数字字符串）。

    Returns:
        利润表 DataFrame。

    Raises:
        RuntimeError: akshare 未安装或接口调用失败。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取 A 股利润表。请运行: pip install akshare")
    return ak.stock_financial_report_sina(stock=code, symbol="利润表")


def _cached_financial_df(cache_file: Path, ttl_days: int, fetch_func, force_refresh: bool) -> pd.DataFrame:
    """财务数据通用缓存读取逻辑（hit → refresh → stale）。

    Args:
        cache_file: 缓存文件路径。
        ttl_days: 有效期（天）。
        fetch_func: 无参拉取函数，返回原始 DataFrame。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        财务数据原始 DataFrame。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    global _financial_status
    if not force_refresh and _is_cache_fresh(cache_file, ttl_days):
        cached = _read_financial_df(cache_file)
        if cached is not None:
            _financial_status = "hit"
            return cached
    try:
        df = fetch_func()
        if df is None or df.empty:
            raise RuntimeError(f"财务数据为空: {cache_file.name}")
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


def get_ipo_info(code: str, force_refresh: bool = False) -> pd.DataFrame:
    """获取 A 股 IPO 信息（上市日期/发行价等，优先本地缓存）。

    Args:
        code: 股票代码（6 位数字字符串）。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        IPO 信息原始 DataFrame。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    return _cached_financial_df(
        _financial_cache_file(code, "ipo"), IPO_TTL_DAYS,
        lambda: _fetch_ipo_df(code), force_refresh)


def get_financial_abstract(symbol: str, force_refresh: bool = False) -> pd.DataFrame:
    """获取 A 股财务摘要（优先本地缓存）。

    Args:
        symbol: 股票代码（6 位数字字符串）。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        财务摘要原始 DataFrame。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    return _cached_financial_df(
        _financial_cache_file(symbol, "abstract"), FINANCIAL_TTL_DAYS,
        lambda: _fetch_financial_abstract_df(symbol), force_refresh)


def get_income_statement_sina(code: str, force_refresh: bool = False) -> pd.DataFrame:
    """获取 A 股利润表（新浪接口，优先本地缓存）。

    Args:
        code: 股票代码（6 位数字字符串）。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        利润表原始 DataFrame。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    return _cached_financial_df(
        _financial_cache_file(code, "利润表"), FINANCIAL_TTL_DAYS,
        lambda: _fetch_income_statement_df(code), force_refresh)


def get_financial_status() -> str:
    """返回最近一次 A 股财务数据访问的缓存状态。

    Returns:
        "hit"（缓存命中）/ "refresh"（拉取刷新）/ "stale"（旧缓存降级）。
    """
    return _financial_status
