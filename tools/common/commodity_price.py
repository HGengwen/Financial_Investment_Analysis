#!/usr/bin/env python3
"""大宗商品价格数据获取工具。

基于 Akshare（首选）与 yfinance（回退）获取主要大宗商品行情数据，
覆盖有色金属、贵金属、能源化工、新能源小金属四大类别。

限流保护设计：
    - 单次获取最多返回 10 条记录（MAX_RECORDS_PER_CALL）
    - 默认时间窗口 14 天（RECORD_WINDOW_DAYS），约 10 个交易日
    - yfinance 请求间隔至少 2 秒（MIN_REQUEST_INTERVAL）
    - 批量获取时品种间间隔 1 秒（BATCH_CALL_INTERVAL）
    - 批量获取最多 10 个品种（MAX_BATCH_SIZE）

数据源策略：
    - 国内品种（上期所/广期所）：仅 Akshare 支持
    - 外盘品种（COMEX、WTI、布伦特等）：Akshare 优先，yfinance 回退
    - 铂金/钯金：仅 yfinance 支持

Usage:
    {py} tools/common/commodity_price.py --code cu              # 获取沪铜
    {py} tools/common/commodity_price.py --code GC              # 获取 COMEX 黄金
    {py} tools/common/commodity_price.py --code cu,GC,CL        # 批量获取
    {py} tools/common/commodity_price.py --list                 # 列出所有支持品种
    {py} tools/common/commodity_price.py --code cu --start 2025-01-01 --end 2025-07-31
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 尝试导入 akshare（提供友好的错误提示）
# ---------------------------------------------------------------------------
try:
    import akshare as ak
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 akshare 库: {e}。请运行: pip install akshare",
        "meta": {"tool": "commodity_price", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)

# ---------------------------------------------------------------------------
# 尝试导入 yfinance（提供友好的错误提示）
# ---------------------------------------------------------------------------
try:
    import yfinance as yf
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"无法导入 yfinance 库: {e}。请运行: pip install yfinance",
        "meta": {"tool": "commodity_price", "timestamp": datetime.now().isoformat()}
    }, ensure_ascii=False))
    sys.exit(1)


# ===========================================================================
# 商品配置注册表
# ===========================================================================

class CommodityCategory(str, Enum):
    """大宗商品类别枚举。"""

    NON_FERROUS_METAL = "有色金属"        # 铜、铝、锌、铅、镍、锡等
    PRECIOUS_METAL = "贵金属"             # 黄金、白银、铂金、钯金
    ENERGY = "能源化工"                   # 原油、天然气、燃料油
    NEW_ENERGY_METAL = "新能源小金属"     # 碳酸锂、稀土、多晶硅


class AkshareApiType(str, Enum):
    """Akshare 接口类型枚举。"""

    SHFE_FUTURES = "shfe_futures"          # 上期所主力合约
    FOREIGN_FUTURES = "foreign_futures"    # 外盘期货历史


@dataclass(frozen=True)
class CommoditySpec:
    """单个商品品种的配置规格。

    Attributes:
        code: 商品唯一编码（如 "cu" 表示沪铜）。
        name: 商品中文名称（如 "沪铜"）。
        category: 商品所属类别。
        currency: 计价货币（"CNY" 人民币 / "USD" 美元）。
        akshare_api: Akshare 接口类型；为 None 表示 Akshare 不支持该品种。
        akshare_symbol: Akshare 接口所需的 symbol 参数。
        yfinance_ticker: yfinance 接口所需的 ticker；为 None 表示 yfinance 不支持。
        exchange: 交易所或市场名称。
        remark: 备注信息。
    """

    code: str
    name: str
    category: CommodityCategory
    currency: str
    akshare_api: Optional[AkshareApiType]
    akshare_symbol: str
    yfinance_ticker: Optional[str] = None
    exchange: str = ""
    remark: str = ""


# 商品注册表：所有受支持品种的统一配置
_COMMODITY_REGISTRY: List[CommoditySpec] = [
    # ===== 有色金属（上期所 SHFE，主力连续合约，人民币计价） =====
    CommoditySpec(
        code="cu", name="沪铜", category=CommodityCategory.NON_FERROUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="cu0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪铜主力连续合约",
    ),
    CommoditySpec(
        code="al", name="沪铝", category=CommodityCategory.NON_FERROUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="al0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪铝主力连续合约",
    ),
    CommoditySpec(
        code="zn", name="沪锌", category=CommodityCategory.NON_FERROUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="zn0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪锌主力连续合约",
    ),
    CommoditySpec(
        code="pb", name="沪铅", category=CommodityCategory.NON_FERROUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="pb0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪铅主力连续合约",
    ),
    CommoditySpec(
        code="ni", name="沪镍", category=CommodityCategory.NON_FERROUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="ni0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪镍主力连续合约",
    ),
    CommoditySpec(
        code="sn", name="沪锡", category=CommodityCategory.NON_FERROUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="sn0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪锡主力连续合约",
    ),
    # ===== 贵金属（上期所 + COMEX 外盘） =====
    CommoditySpec(
        code="au", name="沪金", category=CommodityCategory.PRECIOUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="au0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪金主力连续合约",
    ),
    CommoditySpec(
        code="ag", name="沪银", category=CommodityCategory.PRECIOUS_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="ag0", yfinance_ticker=None, exchange="SHFE",
        remark="上期所沪银主力连续合约",
    ),
    CommoditySpec(
        code="GC", name="COMEX黄金", category=CommodityCategory.PRECIOUS_METAL,
        currency="USD", akshare_api=AkshareApiType.FOREIGN_FUTURES,
        akshare_symbol="GC", yfinance_ticker="GC=F", exchange="COMEX",
        remark="纽约商品交易所黄金期货，Akshare 优先，yfinance 回退",
    ),
    CommoditySpec(
        code="SI", name="COMEX白银", category=CommodityCategory.PRECIOUS_METAL,
        currency="USD", akshare_api=AkshareApiType.FOREIGN_FUTURES,
        akshare_symbol="SI", yfinance_ticker="SI=F", exchange="COMEX",
        remark="纽约商品交易所白银期货，Akshare 优先，yfinance 回退",
    ),
    CommoditySpec(
        code="PL", name="铂金", category=CommodityCategory.PRECIOUS_METAL,
        currency="USD", akshare_api=None,
        akshare_symbol="", yfinance_ticker="PL=F", exchange="NYMEX",
        remark="Akshare 无稳定接口，仅 yfinance 可获取",
    ),
    CommoditySpec(
        code="PA", name="钯金", category=CommodityCategory.PRECIOUS_METAL,
        currency="USD", akshare_api=None,
        akshare_symbol="", yfinance_ticker="PA=F", exchange="NYMEX",
        remark="Akshare 无稳定接口，仅 yfinance 可获取",
    ),
    # ===== 能源化工（上海原油 + 外盘 WTI/布伦特） =====
    CommoditySpec(
        code="sc", name="上海原油", category=CommodityCategory.ENERGY,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="sc0", yfinance_ticker=None, exchange="INE",
        remark="上海国际能源交易中心原油期货",
    ),
    CommoditySpec(
        code="CL", name="WTI原油", category=CommodityCategory.ENERGY,
        currency="USD", akshare_api=AkshareApiType.FOREIGN_FUTURES,
        akshare_symbol="CL", yfinance_ticker="CL=F", exchange="NYMEX",
        remark="美国西德克萨斯中质原油，Akshare 优先，yfinance 回退",
    ),
    CommoditySpec(
        code="BZ", name="布伦特原油", category=CommodityCategory.ENERGY,
        currency="USD", akshare_api=AkshareApiType.FOREIGN_FUTURES,
        akshare_symbol="BZ", yfinance_ticker="BZ=F", exchange="ICE",
        remark="伦敦洲际交易所布伦特原油，Akshare 优先，yfinance 回退",
    ),
    CommoditySpec(
        code="NG", name="天然气", category=CommodityCategory.ENERGY,
        currency="USD", akshare_api=AkshareApiType.FOREIGN_FUTURES,
        akshare_symbol="NG", yfinance_ticker="NG=F", exchange="NYMEX",
        remark="美国天然气期货，Akshare 优先，yfinance 回退",
    ),
    # ===== 新能源小金属（广期所 GFEX） =====
    CommoditySpec(
        code="lc", name="碳酸锂", category=CommodityCategory.NEW_ENERGY_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="lc0", yfinance_ticker=None, exchange="GFEX",
        remark="广州期货交易所碳酸锂主力连续合约",
    ),
    CommoditySpec(
        code="si", name="工业硅", category=CommodityCategory.NEW_ENERGY_METAL,
        currency="CNY", akshare_api=AkshareApiType.SHFE_FUTURES,
        akshare_symbol="si0", yfinance_ticker=None, exchange="GFEX",
        remark="广州期货交易所工业硅主力连续合约",
    ),
]


def _build_index(registry: List[CommoditySpec]) -> Dict[str, CommoditySpec]:
    """根据注册表构建 code -> spec 的索引字典。"""
    index: Dict[str, CommoditySpec] = {}
    for spec in registry:
        if spec.code in index:
            raise ValueError(f"商品 code 重复: {spec.code}")
        index[spec.code] = spec
    return index


_COMMODITY_INDEX: Dict[str, CommoditySpec] = _build_index(_COMMODITY_REGISTRY)


def get_commodity(code: str) -> CommoditySpec:
    """按商品 code 查询商品规格。"""
    if code not in _COMMODITY_INDEX:
        raise KeyError(
            f"未知商品 code: {code}，支持的商品: {list(_COMMODITY_INDEX.keys())}"
        )
    return _COMMODITY_INDEX[code]


def list_commodities(
    category: Optional[CommodityCategory] = None,
) -> List[CommoditySpec]:
    """列出注册表中的商品规格。"""
    if category is None:
        return list(_COMMODITY_REGISTRY)
    return [spec for spec in _COMMODITY_REGISTRY if spec.category == category]


def supports_akshare(spec: CommoditySpec) -> bool:
    """判断指定商品是否可通过 Akshare 获取。"""
    return spec.akshare_api is not None and bool(spec.akshare_symbol)


def supports_yfinance(spec: CommoditySpec) -> bool:
    """判断指定商品是否可通过 yfinance 获取。"""
    return spec.yfinance_ticker is not None and bool(spec.yfinance_ticker)


# ===========================================================================
# 数据获取器
# ===========================================================================

# 规范化输出列名
NORMALIZED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


class CommodityFetchError(Exception):
    """商品行情数据获取失败的统一异常。"""


@dataclass
class FetchResult:
    """单次商品行情获取的结果。

    Attributes:
        code: 商品 code。
        name: 商品中文名。
        source: 实际数据来源（"akshare" 或 "yfinance"）。
        data: 行情数据列表（字典格式）。
        fallback_used: 是否使用了回退数据源。
        message: 附加说明信息。
    """

    code: str
    name: str
    source: str
    data: List[Dict[str, Any]]
    fallback_used: bool
    message: str = ""


# ---------------------------------------------------------------------------
# Akshare 数据获取
# ---------------------------------------------------------------------------

def _normalize_main_sina(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    """规范化 futures_main_sina 接口返回的 DataFrame。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS + ["source", "currency"])

    df = df.copy()
    # 中文列名 -> 英文列名映射
    column_map = {
        "日期": "date", "date": "date",
        "开盘价": "open", "开盘": "open", "open": "open",
        "最高价": "high", "最高": "high", "high": "high",
        "最低价": "low", "最低": "low", "low": "low",
        "收盘价": "close", "收盘": "close", "close": "close",
        "成交量": "volume", "volume": "volume",
    }
    df.columns = [column_map.get(str(c).strip(), str(c).strip().lower())
                  for c in df.columns]

    keep_cols = [c for c in NORMALIZED_COLUMNS if c in df.columns]
    result = df[keep_cols].copy()

    for col in NORMALIZED_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA

    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    result["source"] = "akshare"
    result["currency"] = currency
    return result[NORMALIZED_COLUMNS + ["source", "currency"]]


def _normalize_foreign_hist(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    """规范化 futures_foreign_hist 接口返回的 DataFrame。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS + ["source", "currency"])

    df = df.copy()
    column_map = {
        "日期": "date", "开盘价": "open", "最高价": "high",
        "最低价": "low", "收盘价": "close", "成交量": "volume",
    }
    df.columns = [column_map.get(str(c).strip(), str(c).strip().lower()) for c in df.columns]

    keep_cols = [c for c in NORMALIZED_COLUMNS if c in df.columns]
    result = df[keep_cols].copy()

    for col in NORMALIZED_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA

    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    result["source"] = "akshare"
    result["currency"] = currency
    return result[NORMALIZED_COLUMNS + ["source", "currency"]]


def _normalize_yfinance(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    """规范化 yfinance 返回的 DataFrame。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS + ["source", "currency"])

    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [str(c).strip().lower() for c in df.columns]

    if "adj close" in df.columns:
        df = df.drop(columns=["adj close"])

    df.reset_index(inplace=True)
    if "date" not in df.columns:
        first_col = df.columns[0]
        df.rename(columns={first_col: "date"}, inplace=True)

    keep_cols = [c for c in NORMALIZED_COLUMNS if c in df.columns]
    result = df[keep_cols].copy()

    for col in NORMALIZED_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA

    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    result["source"] = "yfinance"
    result["currency"] = currency
    return result[NORMALIZED_COLUMNS + ["source", "currency"]]


def _filter_by_date_range(df: pd.DataFrame,
                          start_date: Optional[str],
                          end_date: Optional[str]) -> pd.DataFrame:
    """在本地按日期区间过滤 DataFrame。"""
    if df is None or df.empty:
        return df

    result = df.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.dropna(subset=["date"])

    if start_date is not None:
        start_ts = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        if pd.notna(start_ts):
            result = result[result["date"] >= start_ts]
    if end_date is not None:
        end_ts = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
        if pd.notna(end_ts):
            result = result[result["date"] <= end_ts]

    return result.sort_values("date").reset_index(drop=True)


def _fetch_akshare(spec: CommoditySpec,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   max_records: int = 10) -> pd.DataFrame:
    """通过 Akshare 获取商品行情数据。

    Args:
        spec: 商品规格。
        start_date: 起始日期，格式 "YYYYMMDD" 或 "YYYY-MM-DD"。
        end_date: 结束日期，格式同上。
        max_records: 最大返回记录数。

    Returns:
        规范化的 DataFrame。
    """
    # 日期格式转换
    def normalize_date(d: Optional[str]) -> Optional[str]:
        if d is None:
            return None
        return d.replace("-", "").replace("/", "").strip()

    ak_start = normalize_date(start_date)
    ak_end = normalize_date(end_date)

    # 默认区间：近 14 天（约 10 个交易日）
    if ak_end is None:
        ak_end = pd.Timestamp.now().strftime("%Y%m%d")
    if ak_start is None:
        ak_start = (pd.Timestamp.now() - pd.Timedelta(days=14)).strftime("%Y%m%d")

    logger.info("Akshare: 获取 %s(%s), symbol=%s, %s~%s",
                spec.name, spec.code, spec.akshare_symbol, ak_start, ak_end)

    if spec.akshare_api == AkshareApiType.SHFE_FUTURES:
        df = ak.futures_main_sina(
            symbol=spec.akshare_symbol,
            start_date=ak_start,
            end_date=ak_end,
        )
        df = _normalize_main_sina(df, spec.currency)
    elif spec.akshare_api == AkshareApiType.FOREIGN_FUTURES:
        # futures_foreign_hist 不支持日期参数，获取全量后本地过滤
        df = ak.futures_foreign_hist(symbol=spec.akshare_symbol)
        df = _normalize_foreign_hist(df, spec.currency)
        df = _filter_by_date_range(df, ak_start, ak_end)
    else:
        raise CommodityFetchError(f"不支持的 Akshare 接口类型: {spec.akshare_api}")

    # 兜底：取末尾 N 条
    if len(df) > max_records:
        df = df.tail(max_records).reset_index(drop=True)

    return df


# yfinance 请求节流：两次请求之间的最小间隔（秒）
_yf_last_request_time: float = 0.0
YF_MIN_REQUEST_INTERVAL: float = 2.0


def _yf_throttle() -> None:
    """yfinance 请求前等待，确保与上次请求间隔足够。"""
    global _yf_last_request_time
    if _yf_last_request_time <= 0:
        return
    elapsed = time.monotonic() - _yf_last_request_time
    if elapsed < YF_MIN_REQUEST_INTERVAL:
        wait = YF_MIN_REQUEST_INTERVAL - elapsed
        logger.debug("yfinance 限流保护：等待 %.2f 秒", wait)
        time.sleep(wait)


def _fetch_yfinance(spec: CommoditySpec,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    max_records: int = 10) -> pd.DataFrame:
    """通过 yfinance 获取商品行情数据。

    Args:
        spec: 商品规格。
        start_date: 起始日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"。
        end_date: 结束日期，格式同上。
        max_records: 最大返回记录数。

    Returns:
        规范化的 DataFrame。
    """
    global _yf_last_request_time

    # 日期格式转换
    def normalize_date(d: Optional[str]) -> Optional[str]:
        if d is None:
            return None
        cleaned = d.replace("-", "").replace("/", "").strip()
        if len(cleaned) != 8:
            return None
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"

    yf_start = normalize_date(start_date)
    yf_end = normalize_date(end_date)

    # 默认区间：近 14 天
    if yf_end is None:
        yf_end = pd.Timestamp.now().strftime("%Y-%m-%d")
    if yf_start is None:
        yf_start = (pd.Timestamp.now() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")

    logger.info("yfinance: 获取 %s(%s), ticker=%s, %s~%s",
                spec.name, spec.code, spec.yfinance_ticker, yf_start, yf_end)

    # 限流保护
    _yf_throttle()

    try:
        df = yf.download(
            spec.yfinance_ticker,
            start=yf_start,
            end=yf_end,
            progress=False,
            auto_adjust=False,
        )
    except Exception as exc:
        raise CommodityFetchError(f"yfinance 获取失败: {exc}") from exc
    finally:
        _yf_last_request_time = time.monotonic()

    if df is None or df.empty:
        raise CommodityFetchError(f"yfinance 返回空数据: {spec.name}({spec.code})")

    df = _normalize_yfinance(df, spec.currency)

    # 兜底：取末尾 N 条
    if len(df) > max_records:
        df = df.tail(max_records).reset_index(drop=True)

    return df


# ===========================================================================
# 主调度器
# ===========================================================================

def fetch_commodity(code: str,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    max_records: int = 10) -> FetchResult:
    """获取指定商品的行情数据。

    优先尝试 Akshare，失败且商品支持 yfinance 时回退到 yfinance。

    Args:
        code: 商品 code（如 "cu"、"GC"）。
        start_date: 起始日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"。
        end_date: 结束日期，格式同上。
        max_records: 最大返回记录数，默认 10。

    Returns:
        FetchResult 对象，包含数据及来源信息。

    Raises:
        CommodityFetchError: 商品未配置任何数据源，或所有数据源均失败。
    """
    spec = get_commodity(code)

    # 第一步：尝试 Akshare
    if supports_akshare(spec):
        try:
            df = _fetch_akshare(spec, start_date, end_date, max_records)
            if df is not None and not df.empty:
                data_list = df.to_dict(orient="records")
                # 转换日期为字符串
                for item in data_list:
                    if "date" in item and pd.notna(item["date"]):
                        item["date"] = str(item["date"])[:10]
                    # 转换 NaN 为 None
                    for k, v in item.items():
                        if pd.isna(v):
                            item[k] = None
                return FetchResult(
                    code=spec.code, name=spec.name,
                    source="akshare", data=data_list,
                    fallback_used=False,
                    message="Akshare 获取成功",
                )
            logger.warning("Akshare 返回空数据: %s", spec.code)
        except Exception as exc:
            logger.warning("Akshare 获取 %s 失败，尝试回退: %s", spec.code, exc)

    # 第二步：尝试 yfinance 回退
    if supports_yfinance(spec):
        try:
            df = _fetch_yfinance(spec, start_date, end_date, max_records)
            if df is not None and not df.empty:
                fallback = supports_akshare(spec)
                base_msg = ("yfinance 回退获取成功" if fallback else "yfinance 直接获取成功")
                data_list = df.to_dict(orient="records")
                for item in data_list:
                    if "date" in item and pd.notna(item["date"]):
                        item["date"] = str(item["date"])[:10]
                    for k, v in item.items():
                        if pd.isna(v):
                            item[k] = None
                return FetchResult(
                    code=spec.code, name=spec.name,
                    source="yfinance", data=data_list,
                    fallback_used=fallback,
                    message=base_msg,
                )
            logger.warning("yfinance 返回空数据: %s", spec.code)
        except Exception as exc:
            logger.warning("yfinance 获取 %s 失败: %s", spec.code, exc)

    # 两个数据源均失败
    raise CommodityFetchError(
        f"商品 {spec.name}({spec.code}) 所有数据源均获取失败"
    )


def fetch_many(codes: List[str],
               start_date: Optional[str] = None,
               end_date: Optional[str] = None,
               max_records: int = 10,
               batch_interval: float = 1.0) -> List[FetchResult]:
    """批量获取多个商品的行情数据。

    限流保护：
        - 单次最多支持 10 个品种，超出将抛出异常。
        - 每个品种获取之间加入间隔延迟。

    Args:
        codes: 商品 code 列表，长度不得超过 10。
        start_date: 起始日期。
        end_date: 结束日期。
        max_records: 每个商品最大返回记录数。
        batch_interval: 批量获取时品种间的间隔秒数。

    Returns:
        FetchResult 列表，顺序与输入 codes 一致。

    Raises:
        CommodityFetchError: codes 数量超过 10。
    """
    MAX_BATCH_SIZE = 10
    if len(codes) > MAX_BATCH_SIZE:
        raise CommodityFetchError(
            f"单次批量获取最多支持 {MAX_BATCH_SIZE} 个品种，"
            f"当前请求 {len(codes)} 个；请分批调用"
        )

    results: List[FetchResult] = []
    for idx, code in enumerate(codes):
        # 第一个品种前不延迟；后续品种之间加入间隔
        if idx > 0 and batch_interval > 0:
            logger.debug("批量获取节流：等待 %.2f 秒后获取下一个品种 %s",
                         batch_interval, code)
            time.sleep(batch_interval)

        try:
            results.append(fetch_commodity(code, start_date, end_date, max_records))
        except CommodityFetchError as exc:
            logger.error("批量获取 %s 失败: %s", code, exc)
            try:
                name = get_commodity(code).name
            except KeyError:
                name = code
            results.append(FetchResult(
                code=code, name=name,
                source="failed", data=[],
                fallback_used=False, message=str(exc),
            ))
    return results


# ===========================================================================
# CLI 入口
# ===========================================================================

def cmd_list() -> Dict[str, Any]:
    """--list: 列出所有支持的商品品种。"""
    categories_data = []
    for category in CommodityCategory:
        specs = list_commodities(category)
        category_data = {
            "category": category.value,
            "count": len(specs),
            "commodities": []
        }
        for spec in specs:
            category_data["commodities"].append({
                "code": spec.code,
                "name": spec.name,
                "currency": spec.currency,
                "exchange": spec.exchange,
                "akshare": supports_akshare(spec),
                "yfinance": supports_yfinance(spec),
                "remark": spec.remark,
            })
        categories_data.append(category_data)

    return {
        "success": True,
        "data": categories_data,
        "meta": {
            "tool": "commodity_price",
            "command": "list",
            "total_count": sum(c["count"] for c in categories_data),
            "timestamp": datetime.now().isoformat()
        }
    }


def cmd_fetch(codes: str,
              start_date: Optional[str] = None,
              end_date: Optional[str] = None,
              max_records: int = 10) -> Dict[str, Any]:
    """--code: 获取商品行情数据。"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]

    if not code_list:
        return {
            "success": False,
            "error": "请提供商品代码，例如: --code cu 或 --code cu,GC,CL",
            "meta": {"tool": "commodity_price", "timestamp": datetime.now().isoformat()}
        }

    try:
        if len(code_list) == 1:
            result = fetch_commodity(code_list[0], start_date, end_date, max_records)
            return {
                "success": True,
                "data": {
                    "code": result.code,
                    "name": result.name,
                    "source": result.source,
                    "fallback_used": result.fallback_used,
                    "message": result.message,
                    "records": result.data,
                    "record_count": len(result.data),
                },
                "meta": {
                    "tool": "commodity_price",
                    "command": "fetch",
                    "code": result.code,
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            results = fetch_many(code_list, start_date, end_date, max_records)
            return {
                "success": True,
                "data": {
                    "batch": True,
                    "results": [
                        {
                            "code": r.code,
                            "name": r.name,
                            "source": r.source,
                            "fallback_used": r.fallback_used,
                            "message": r.message,
                            "records": r.data,
                            "record_count": len(r.data),
                        }
                        for r in results
                    ],
                    "total_count": len(results),
                },
                "meta": {
                    "tool": "commodity_price",
                    "command": "fetch_many",
                    "codes": code_list,
                    "timestamp": datetime.now().isoformat()
                }
            }
    except CommodityFetchError as exc:
        return {
            "success": False,
            "error": str(exc),
            "meta": {"tool": "commodity_price", "timestamp": datetime.now().isoformat()}
        }


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="大宗商品价格数据获取工具（Akshare 优先，yfinance 回退）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --code cu                              # 获取沪铜
  %(prog)s --code GC                              # 获取 COMEX 黄金
  %(prog)s --code cu,GC,CL                        # 批量获取多个品种
  %(prog)s --list                                 # 列出所有支持品种
  %(prog)s --code cu --start 2025-01-01 --end 2025-07-31

限流保护:
  - 单次获取最多返回 10 条记录（可通过 --max-records 调整）
  - 默认时间窗口 14 天（约 10 个交易日）
  - 批量获取时品种间间隔 1 秒
  - 批量获取最多 10 个品种
""")

    parser.add_argument("--code", type=str, default=None,
                        help="商品代码，多个用逗号分隔（如 cu,GC,CL）")
    parser.add_argument("--list", action="store_true",
                        help="列出所有支持的商品品种")
    parser.add_argument("--start", type=str, default=None,
                        help="起始日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--end", type=str, default=None,
                        help="结束日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--max-records", type=int, default=10,
                        help="每个品种最大返回记录数（默认 10）")

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        output = cmd_list()
    elif args.code:
        output = cmd_fetch(args.code, args.start, args.end, args.max_records)
    else:
        parser.print_help()
        sys.exit(0)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
