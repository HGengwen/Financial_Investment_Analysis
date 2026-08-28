#!/usr/bin/env python3
"""美股财务报表本地缓存模块（美股财务数据缓存）。

本模块位于 tools/common/ 目录下，为美股工具（stock_financial 等）提供
三大报表（利润表/资产负债表/现金流量表）的本地 JSON 缓存，对齐
a_stock_cache / hk_stock_cache 的 hit → refresh → stale 模式：

- 缓存新鲜 → 直接读本地（状态 hit）；
- 缓存缺失/过期 → 调用 yfinance 拉取并原子覆写缓存（状态 refresh）；
- 刷新失败且存在旧缓存 → 降级返回旧数据（状态 stale）；
- 刷新失败且无缓存 → 抛出异常。

背景：yfinance 对频繁请求返回 429 限流，对财报做本地缓存以避免封禁。

yfinance 三张报表为 DataFrame（index=科目英文名，columns=报告期），
本模块统一转成 {报告期(YYYY-MM-DD): {科目: 值}} 的 dict 便于 JSON 落盘。

Usage:
    from tools.common import us_stock_cache

    # 获取利润表/资产负债表/现金流量表
    stmt = us_stock_cache.get_statement("AAPL", "income")

    # 最近一次缓存状态（hit / refresh / stale）
    status = us_stock_cache.get_financial_status("income")
"""

import re
from datetime import datetime
from pathlib import Path

import json
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失时降级为不读取 .env
    load_dotenv = None

try:  # pragma: no cover - 刷新缓存时才需要
    import pandas as pd
except ImportError:
    pd = None

try:  # pragma: no cover - 刷新缓存时才需要 yfinance
    import yfinance as yf
except ImportError:
    yf = None


# ---------------------------------------------------------------------------
# 路径与配置常量
# ---------------------------------------------------------------------------

# 工作区根目录（本文件位于 tools/common/，向上 3 层到达项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 美股财务缓存目录（per-stock 文件）
FINANCIAL_DIR: Path = _PROJECT_ROOT / "data" / "us_stock" / "financial"

# 最近一次报表缓存状态（hit/refresh/stale）
_financial_status: dict[str, str] = {}


def _load_dotenv() -> None:
    """从项目根目录 .env 加载环境变量（若已安装 python-dotenv）。"""
    if load_dotenv is not None:
        load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _parse_int_env(var_name: str, default: int) -> int:
    """从环境变量读取整数配置，非法值或缺失时回退默认值。

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

# 美股财务缓存有效期（天），.env 可配置
US_FINANCIAL_TTL_DAYS: int = _parse_int_env("US_FINANCIAL_TTL_DAYS", 7)

# 重定向 yfinance 的 cookie/tz 缓存到项目内目录，避免写入用户目录
# 受限环境（沙箱）默认目录不可写时会失败，重定向可规避并保持可移植。
try:
    from yfinance.cache import set_cache_location as _set_yf_cache
    _YF_CACHE_DIR = (FINANCIAL_DIR.parent / "yf_cache")
    _set_yf_cache(str(_YF_CACHE_DIR))
except Exception:  # noqa: BLE001 - 配置失效不影响后续功能
    pass

# yfinance 报表科目 → 缓存键
STATEMENT_MAP = {
    "income": "income_stmt",
    "balance": "balance_sheet",
    "cashflow": "cashflow",
}


# ---------------------------------------------------------------------------
# 通用缓存工具函数
# ---------------------------------------------------------------------------

def _is_cache_fresh(cache_file: Path, ttl_days: int) -> bool:
    """判断缓存文件是否在 TTL 有效期之内。

    Args:
        cache_file: 缓存文件路径。
        ttl_days: 有效期天数。

    Returns:
        新鲜（未过期）返回 True；文件不存在或已过期返回 False。
    """
    if not cache_file.exists():
        return False
    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
    return (datetime.now() - mtime).days < ttl_days


def _read_json(cache_file: Path) -> dict | None:
    """读取财务缓存 JSON 文件；缺失或损坏时返回 None。

    Args:
        cache_file: 缓存文件路径。

    Returns:
        解析后的 dict；失败返回 None。
    """
    if not cache_file.exists():
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _atomic_write_json(obj: dict, cache_file: Path) -> None:
    """原子写入 JSON 缓存：先写 .tmp 再 os.replace，避免并发写坏缓存。

    Args:
        obj: 待写入的 dict。
        cache_file: 目标缓存文件路径。
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
    with open(tmp_file, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp_file, cache_file)


def _norm_report_date(val) -> str | None:
    """将报告期值规整为 'YYYY-MM-DD' 字符串。

    Args:
        val: 报告期（datetime / pandas Timestamp / 字符串）。

    Returns:
        'YYYY-MM-DD'；无法解析时返回 None。
    """
    if val is None:
        return None
    if pd is not None and isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})[-\/]?(\d{2})[-\/]?(\d{2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{mo}-{d}"
    return s[:10]


def _stmt_to_map(df, value_col: str = "value") -> dict:
    """将 yfinance 报表 DataFrame 转为 {报告期: {科目: 值}}。

    yfinance 三张报表：index=科目英文名，columns=报告期日期。

    Args:
        df: yfinance 报表 DataFrame。
        value_col: 未使用参数（保留占位以统一签名）。

    Returns:
        {报告期(YYYY-MM-DD): {科目: 值}}。
    """
    result: dict = {}
    if df is None:
        return result
    for date_col in df.columns:
        rd = _norm_report_date(date_col)
        if rd is None:
            continue
        sub = {}
        for item, v in df[date_col].items():
            val = v
            try:
                if pd is not None and pd.notna(val) and val is not None:
                    val = float(val)
            except (TypeError, ValueError):
                pass
            if val is not None and str(val) not in ("nan", "None"):
                sub[str(item)] = val
        if sub:
            result[rd] = sub
    return result


def _get_financial_json(symbol: str, cache_key: str, fetch_map_fn, ttl_days: int) -> dict:
    """通用财务缓存访问（hit → refresh → stale）。

    Args:
        symbol: 美股代码（如 'AAPL'）。
        cache_key: 缓存文件名后缀（income/balance/cashflow）。
        fetch_map_fn: 无参函数，返回 {报告期: {科目: 值}}。
        ttl_days: 缓存有效期天数。

    Returns:
        财务科目字典（= fetch_map_fn 结果）。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    global _financial_status
    fpath = FINANCIAL_DIR / f"{symbol}_{cache_key}.json"

    if _is_cache_fresh(fpath, ttl_days):
        data = _read_json(fpath)
        if data is not None:
            _financial_status[cache_key] = "hit"
            return data
    try:
        data = fetch_map_fn()
        _atomic_write_json(data, fpath)
        _financial_status[cache_key] = "refresh"
        return data
    except Exception:
        data = _read_json(fpath)
        if data is not None:
            _financial_status[cache_key] = "stale"
            return data
        raise


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------

def get_statement(symbol: str, stmt_key: str) -> dict:
    """获取美股三大报表之一（利润表/资产负债表/现金流量表）。

    Args:
        symbol: 美股代码（如 'AAPL'）。
        stmt_key: 报表键：'income' / 'balance' / 'cashflow'。

    Returns:
        {报告期(YYYY-MM-DD): {科目: 值}}。

    Raises:
        RuntimeError: yfinance 未安装、未知报表键或拉取失败且无缓存。
    """
    if yf is None:
        raise RuntimeError("yfinance 未安装，无法获取美股报表")
    attr = STATEMENT_MAP.get(stmt_key)
    if attr is None:
        raise RuntimeError(f"未知报表键: {stmt_key}，可选 income/balance/cashflow")

    symbol = symbol.upper()

    def _fetch():
        stock = yf.Ticker(symbol)
        data = _stmt_to_map(getattr(stock, attr))
        if not data:
            # yfinance 在无 crumb/网络异常时静默返回空报表，须视为失败
            # 以免将空 dict 写入缓存而长期驻留
            raise RuntimeError("yfinance 返回空报表，无法获取财务数据")
        return data

    return _get_financial_json(symbol, stmt_key, _fetch, US_FINANCIAL_TTL_DAYS)


def get_financial_status(cache_key: str) -> str:
    """返回某类美股财务数据最近一次访问的缓存状态。

    Args:
        cache_key: 报表键（income/balance/cashflow）。

    Returns:
        "hit" / "refresh" / "stale" / "unknown"。
    """
    return _financial_status.get(cache_key, "unknown")