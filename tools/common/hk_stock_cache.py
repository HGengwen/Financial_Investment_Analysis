#!/usr/bin/env python3
"""港股财务报表与员工数据本地缓存模块（港股财务数据缓存）。

本模块位于 tools/common/ 目录下，为港股工具（stock_financial 等）提供
三大报表（资产负债表/利润表/现金流量表）与员工数的本地 JSON 缓存，
对齐 A 股缓存（a_stock_cache）的 hit → refresh → stale 模式：

- 缓存新鲜 → 直接读本地（状态 hit）；
- 缓存缺失/过期 → 拉取东财/雪球接口并原子覆写缓存（状态 refresh）；
- 刷新失败且存在旧缓存 → 降级返回旧数据（状态 stale）；
- 刷新失败且无缓存 → 抛出异常。

背景：东财港股接口在中国大陆连接不稳定，批量模式（10-20 家 × 多科目）
有速率风险，故对报表/员工数做本地缓存以避免封禁。

Usage:
    from tools.common import hk_stock_cache

    # 获取华为报表（资产负债表等），按 报告期 → 科目 组织
    stmt = hk_stock_cache.get_financial_report("00700", "资产负债表")

    # 员工数（雪球，token 失效时标注缺口）
    emp = hk_stock_cache.get_employee_count("00700")

    # 最近一次缓存状态（hit / refresh / stale / unknown）
    status = hk_stock_cache.get_financial_status("资产负债表")
"""

import json
import os
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失时降级为不读取 .env
    load_dotenv = None

try:  # pragma: no cover - 仅刷新缓存时才需要 pandas
    import pandas as pd
except ImportError:
    pd = None

try:  # pragma: no cover - 仅刷新缓存时才需要 akshare
    import akshare as ak
except ImportError:
    ak = None


# ---------------------------------------------------------------------------
# 路径与配置常量
# ---------------------------------------------------------------------------

# 工作区根目录（本文件位于 tools/common/，向上 3 层到达项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 港股财务缓存目录（per-stock 文件）
FINANCIAL_DIR: Path = _PROJECT_ROOT / "data" / "hk_stock" / "financial"

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

# 港股财务缓存有效期（天），.env 可配置
HK_FINANCIAL_TTL_DAYS: int = _parse_int_env("HK_FINANCIAL_TTL_DAYS", 7)


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
    """将报告期值规整为 'YYYYMMDD' 字符串。

    Args:
        val: 报告期（datetime / pandas Timestamp / 字符串）。

    Returns:
        'YYYYMMDD' 字符串；无法解析时返回 None。
    """
    if val is None:
        return None
    if pd is not None and isinstance(val, pd.Timestamp):
        return val.strftime("%Y%m%d")
    if isinstance(val, datetime):
        return val.strftime("%Y%m%d")
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y%m%d")
        except (ValueError, TypeError):
            continue
    return s[:8]


def _long_to_map(df, date_col: str = "REPORT_DATE",
                 item_col: str = "STD_ITEM_NAME",
                 amount_col: str = "AMOUNT") -> dict:
    """将港股东财报表长表透视为 {报告期: {科目: 金额}}。

    东财港股报表接口返回长表（每行一个科目×报告期），需按报告期去重累积。

    Args:
        df: 长表 DataFrame。
        date_col: 报告期列名。
        item_col: 科目名列名。
        amount_col: 金额列名。

    Returns:
        {报告期(YYYYMMDD): {科目: 金额}}。
    """
    result: dict = {}
    if df is None:
        return result
    for _, row in df.iterrows():
        rd = _norm_report_date(row.get(date_col))
        item = row.get(item_col)
        if rd is None or item is None:
            continue
        amt = row.get(amount_col)
        try:
            amt = float(amt)
        except (TypeError, ValueError):
            pass
        result.setdefault(rd, {})[str(item).strip()] = amt
    return result


def _get_financial_json(code: str, cache_key: str, fetch_map_fn, ttl_days: int) -> dict:
    """通用财务缓存访问（hit → refresh → stale）。

    Args:
        code: 5 位港股代码。
        cache_key: 缓存文件名后缀（如 资产负债表）。
        fetch_map_fn: 无参函数，返回 {报告期: {科目: 值}}。
        ttl_days: 缓存有效期天数。

    Returns:
        财务科目字典（= fetch_map_fn 结果）。

    Raises:
        RuntimeError: 无缓存且拉取失败。
    """
    global _financial_status
    fpath = FINANCIAL_DIR / f"{code}_{cache_key}.json"

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

def get_financial_report(code: str, report_type: str) -> dict:
    """获取港股三大报表（资产负债表/利润表/现金流量表）。

    长表接口按「报告期 → 科目 → 金额」透视后可互相独立各期叠加跨度。

    Args:
        code: 港股代码（5 位字符串，如 '00700'）。
        report_type: 报表类型：'资产负债表' / '利润表' / '现金流量表'。

    Returns:
        {报告期(YYYYMMDD): {科目: 金额}}。

    Raises:
        RuntimeError: akshare 未安装或拉取失败且无缓存。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取港股报表")
    code = code.zfill(5)

    def _fetch():
        df = ak.stock_financial_hk_report_em(
            stock=code, symbol=report_type, indicator="年度")
        return _long_to_map(df)

    return _get_financial_json(code, report_type, _fetch, HK_FINANCIAL_TTL_DAYS)


def get_employee_count(code: str) -> dict:
    """获取港股员工总数（雪球接口）。

    雪球接口依赖 xq_a_token cookie，token 失效/接口不稳定时返回缺口
    （{"value": None, "note": 原因}），不静默使用错误数据。

    Args:
        code: 港股代码（5 位字符串，如 '00700'）。

    Returns:
        {"value": 员工数或 None, "note": 来源/缺口说明}。
    """
    if ak is None:
        return {"value": None, "note": "akshare 未安装"}
    code = code.zfill(5)
    try:
        df = ak.stock_individual_basic_info_hk_xq(symbol=code)
        val = None
        for _, row in df.iterrows():
            item = str(row.get("item", "")).strip()
            if item in ("员工总数", "员工人数", "职工人数"):
                try:
                    val = int(float(row.get("value")))
                except (TypeError, ValueError):
                    val = None
                break
        if val is not None:
            return {"value": val, "note": "雪球"}
        return {"value": None, "note": "雪球接口未返回员工字段"}
    except Exception as e:  # noqa: BLE001 - 接口(token)不稳定，统一标注缺口
        return {"value": None,
                "note": f"员工数无可靠接口（{type(e).__name__}），需搜索补充"}


def get_financial_status(cache_key: str) -> str:
    """返回某类港股财务数据最近一次访问的缓存状态。

    Args:
        cache_key: 报表类型或缓存键（如 资产负债表 / 利润表）。

    Returns:
        "hit" / "refresh" / "stale" / "unknown"。
    """
    return _financial_status.get(cache_key, "unknown")