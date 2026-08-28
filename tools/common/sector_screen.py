#!/usr/bin/env python3
"""A股板块（行业）SMR 截面数据模块（阶段三）。

为 `stock_quote --momentum` 自动生成 250 日 SMR 同板块截面（--peers），避免手动
传参并对全部 A 股（5000+）全量拉取：给定个股代码，经申万一级行业成分
（`sw_index_first_info` + `index_component_sw`，一次性构建全市场"代码→申万一级行业"
映射并缓存，覆盖率远高于东财行业缓存的当季已披露口径）查得其"所处行业"，取同行业
其他成分，批量拉取 250 日涨幅形成截面，并本地缓存整截面（hit→refresh→stale 模式）。

- 板块口径：同板块 = 同"所处行业"，非全市场（技能文件允许"全市场或同板块"）。
- 批量：板块截面一次拉取、多家复用，单只成分拉取失败跳过不阻断。
- 缓存：`data/a_share/sector/{行业}.json`，TTL 默认 7 天，过期刷新失败降级旧缓存。

Usage:
    from tools.common import sector_screen

    info = sector_screen.compute_peers_for_stock("300502")
    # info = {"industry": ..., "pcts": [..250日涨幅%..], "status": "hit"}
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 注入项目根目录到 sys.path，使 `from tools.common import a_stock_cache` 可用
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    import akshare as ak
except ImportError:  # akshare 缺失时降级（拉取不可用，缓存读取仍可用）
    ak = None

try:
    from tools.common import a_stock_cache
except ImportError:
    a_stock_cache = None

#: SMR 截面数据目录（数据/市场/sector）
_DATA_DIR = Path(os.environ.get("DATA_DIR", str(_PROJECT_ROOT / "data")))
_SECTOR_DIR = _DATA_DIR / "a_share" / "sector"

#: 截面缓存有效天数（过期为未新鲜，刷新失败降级旧缓存）
_SECTOR_TTL_DAYS = 7

#: 单只成分拉取的回溯自然日（250 日涨幅 + 足够缓冲）
_PEER_LOOKBACK_DAYS = 420

#: 单批截面成分数量上限（控制拉取耗时；行业成分超过时取前 N）
_DEFAULT_MAX_MEMBERS = 40

#: 拉取失败容忍上限（有效成分低于该比例视为整批失败 → stale 降级）
_MIN_VALID_RATIO = 0.5

#: 进程内申万行业映射缓存（避免连续调用重复构建 31 个行业）
_sw_map_cache: Optional[dict] = None


def _build_sw_map() -> dict:
    """一次性构建全市场"股票代码→申万一级行业"映射。

    遍历 `sw_index_first_info()` 返回的申万一级行业，对每个行业调
    `index_component_sw(symbol)` 取成分，累积为 {6位代码: 一级行业名}。单个行业
    拉取失败仅跳过不阻断；整体失败返回空映射（由调用方降级到东财行业缓存）。

    Returns:
        全市场代码→申万一级行业名映射；构建失败返回空 dict。
    """
    if ak is None:
        return {}
    try:
        sectors = ak.sw_index_first_info()
    except Exception:
        return {}
    if sectors is None or sectors.empty or \
            "行业代码" not in sectors.columns or "行业名称" not in sectors.columns:
        return {}
    result: Dict[str, str] = {}
    for _, row in sectors.iterrows():
        sector_code = str(row["行业代码"]).split(".")[0]
        industry = str(row["行业名称"]).strip()
        try:
            comp_df = ak.index_component_sw(symbol=sector_code)
        except Exception:
            continue  # 单行业失败跳过，不阻断整体
        if comp_df is None or comp_df.empty or "证券代码" not in comp_df.columns:
            continue
        for code in comp_df["证券代码"].astype(str).tolist():
            result[code.zfill(6)] = industry
    return result


def _load_sw_map(force_refresh: bool = False) -> dict:
    """按 hit→refresh→stale 模式加载申万行业映射（代码→一级行业）。

    优先返回进程内缓存；其次文件缓存（新鲜则直接返回）；否则构建全市场映射并原子
    写入缓存文件（`data/a_share/sector/sw_industry_map.json`）。构建失败时降级返回
    旧缓存（stale）或空映射。

    Args:
        force_refresh: 强制刷新（忽略新鲜缓存）。

    Returns:
        代码→申万一级行业名映射；不可得返回空 dict。
    """
    global _sw_map_cache
    if not force_refresh and _sw_map_cache is not None:
        return _sw_map_cache

    file = _SECTOR_DIR / "sw_industry_map.json"
    cached: dict = {}
    if file.exists():
        try:
            cached = json.loads(file.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, OSError):
            cached = {}
        if not force_refresh and _is_fresh(file) and cached.get("map"):
            _sw_map_cache = cached["map"]
            return cached["map"]

    # 需要刷新：构建全市场映射
    built = _build_sw_map()
    if built:
        data = {"asof": date.today().isoformat(), "map": built}
        try:
            _SECTOR_DIR.mkdir(parents=True, exist_ok=True)
            tmp = file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, file)
        except OSError:
            pass  # 写缓存失败不影响本次返回
        _sw_map_cache = built
        return built

    # 构建失败：降级返回旧缓存（stale）或空
    _sw_map_cache = cached.get("map") or {} if isinstance(cached, dict) else {}
    return _sw_map_cache


def get_industry_of_stock(code: str) -> Optional[str]:
    """查询个股所属行业（申万一级行业优先，东财行业缓存兜底）。

    Args:
        code: 6 位 A 股代码。

    Returns:
        行业名称；未找到返回 None。
    """
    zcode = code.zfill(6)
    sw_map = _load_sw_map()
    industry = sw_map.get(zcode)
    if industry:
        return industry
    if a_stock_cache is None:
        return None
    rec = a_stock_cache.get_industry_map().get(zcode)
    return rec.get("industry") if rec else None


def get_sector_members(industry: str, exclude_code: Optional[str] = None) -> List[str]:
    """获取同行业成分代码列表（申万行业映射优先，东财行业缓存兜底）。

    Args:
        industry: 行业名称（申万一级行业名）。
        exclude_code: 需排除的个股代码（通常为查询个股本身）。

    Returns:
        同行业其余成分的代码列表；行业不存在返回空列表。
    """
    zcode = exclude_code.zfill(6) if exclude_code else None
    sw_map = _load_sw_map()
    members = [code for code, ind in sw_map.items()
               if ind == industry and code != zcode]
    if members:
        return members
    if a_stock_cache is None:
        return []
    industry_map = a_stock_cache.get_industry_map()
    return [code for code, rec in industry_map.items()
            if rec.get("industry") == industry and code != zcode]


def _sina_symbol(code: str) -> Optional[str]:
    """A 股代码转新浪前缀符号（sh/sz/bj）。

    Args:
        code: 6 位 A 股代码。

    Returns:
        带市场前缀的符号；无法识别前缀（如 9/1/2/5/7）返回 None。
    """
    z = code.zfill(6)
    if z.startswith(("60", "688")):
        return f"sh{z}"
    if z.startswith(("00", "30")):
        return f"sz{z}"
    if z.startswith(("4", "8")):
        return f"bj{z}"
    return None


def _pct_from_closes(closes: List[float]) -> Optional[float]:
    """由收盘价序列计算 250 日涨跌幅百分比（前复权）。

    Args:
        closes: 升序收盘价（含足够回溯，最好 >251 个）。

    Returns:
        250 日涨跌幅百分比；数据不足或基准为 0 返回 None。
    """
    if len(closes) < 2:
        return None
    ref = closes[-251] if len(closes) > 251 else closes[0]  # 250 日涨幅基准
    if ref == 0.0:
        return None
    return (closes[-1] - ref) / ref * 100.0


def fetch_peer_pct_250d(code: str) -> Optional[float]:
    """拉取单只成分的 250 日涨跌幅（百分比，前复权）。

    双源策略（规避东财批量拉取限流）：新浪 `stock_zh_a_daily` 优先（深沪稳定），
    失败回退东财 `stock_zh_a_hist`。单只失败返回 None 不影响整批。

    Args:
        code: 6 位 A 股代码。

    Returns:
        250 日涨跌幅百分比；数据不足或拉取失败返回 None。
    """
    if ak is None:
        return None
    start = (datetime.now() - timedelta(days=_PEER_LOOKBACK_DAYS)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")

    closes: Optional[List[float]] = None
    # 源1：新浪（优先，深沪稳定，批量不易限流）
    sina_sym = _sina_symbol(code)
    if sina_sym:
        try:
            df = ak.stock_zh_a_daily(symbol=sina_sym, start_date=start,
                                     end_date=end, adjust="qfq")
            if df is not None and not df.empty and "close" in df.columns:
                closes = [float(v) for v in df["close"].dropna().tolist()]
        except Exception:
            closes = None  # 新浪失败则回退东财
    # 源2：东财回退
    if not closes:
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start, end_date=end, adjust="qfq")
            if df is not None and not df.empty and "close" in df.columns:
                closes = [float(v) for v in df["close"].dropna().tolist()]
        except Exception:
            closes = None
    return _pct_from_closes(closes) if closes else None


# ---------------------------------------------------------------------------
# 本地缓存（hit → refresh → stale）
# ---------------------------------------------------------------------------

def _sector_file(industry: str) -> Path:
    """由行业名映射到缓存文件（中文行业名 -> hash 前缀，避免路径问题）。"""
    digest = hashlib.md5(industry.encode("utf-8")).hexdigest()[:12]
    return _SECTOR_DIR / f"{digest}.json"


def _read_cached(industry: str) -> Optional[dict]:
    """读取行业截面缓存；缺失/损坏返回 None。"""
    file = _sector_file(industry)
    if not file.exists():
        return None
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _is_fresh(file: Path) -> bool:
    """按 mtime 判断缓存是否新鲜。"""
    if not file.exists():
        return False
    age_days = (time.time() - file.stat().st_mtime) / 86400.0
    return age_days <= _SECTOR_TTL_DAYS


def _atomic_write(industry: str, data: dict) -> None:
    """原子写入截面缓存（先写临时文件再替换）。"""
    _SECTOR_DIR.mkdir(parents=True, exist_ok=True)
    file = _sector_file(industry)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, file)


def get_sector_peers(industry: str, max_members: int = _DEFAULT_MAX_MEMBERS,
                     force_refresh: bool = False) -> dict:
    """获取行业截面各成分 250 日涨幅（带缓存）。

    截面按"全行业成分（含查询股自身）"口径缓存，保证缓存纯行业级、跨查询股稳定；
    SMR 百分位将股自身计入板块（own 即板块一员，符合"同板块百分位"口径）。

    Args:
        industry: 行业名称。
        max_members: 单批截面成分数量上限。
        force_refresh: 强制刷新（忽略新鲜缓存）。

    Returns:
        dict: {industry, asof, status(hit/refresh/stale), peers: {code: pct},
        skipped}, peers 为 250 日涨幅百分位映射。
    """
    members = get_sector_members(industry)[:max_members]
    file = _sector_file(industry)
    cached = _read_cached(industry)

    if not force_refresh and cached and _is_fresh(file):
        cached.update({"status": "hit", "industry": industry,
                       "members_total": len(get_sector_members(industry))})
        return cached

    # 刷新：批量拉取各成分 250 日涨幅
    peers: Dict[str, float] = {}
    skipped = 0
    for code in members:
        if ak is None:
            break
        pct = fetch_peer_pct_250d(code)
        if pct is not None:
            peers[code] = round(pct, 4)
        else:
            skipped += 1

    total = len(members)
    ok = len(peers)
    # 有效成分比例过低（或全失败）视为整批拉取失败 → 降级旧缓存或返回空截面
    low_coverage = total > 0 and ok < _MIN_VALID_RATIO * total
    if low_coverage or ok == 0:
        if cached:
            cached.update({"status": "stale", "industry": industry})
            return cached
        return {"industry": industry, "asof": date.today().isoformat(),
                "status": "refresh", "peers": {}, "skipped": skipped,
                "members_total": total,
                "note": "截面成分有效比例过低，无法生成 peers"}

    data = {"industry": industry,
            "asof": date.today().isoformat(),
            "peers": peers,
            "skipped": skipped,
            "members_total": total}
    _atomic_write(industry, data)
    data["status"] = "refresh"
    return data


#: 港/美股暂无可用的公开板块成分数据源（已实测验证）。
#: 港股：akshare 无恒生行业成分接口；美股：yfinance 已移除 ETF holdings。
#: 提供统一分发入口但返回 unavailable，为将来接入外部成分源保留接口。
_MARKET_UNAVAILABLE_NOTE = {
    "hk": "港股板块成分暂无公开数据源（akshare 无恒生行业成分接口），"
          "SMR 自动截面不可用，请使用手动 --peers",
    "us": "美股板块成分暂无稳定公开数据源（yfinance 已移除 ETF holdings 等成分接口），"
          "SMR 自动截面不可用，请使用手动 --peers",
}


def compute_peers_for_stock(code: str, market: str = "a",
                            max_members: int = _DEFAULT_MAX_MEMBERS) -> dict:
    """组合入口：由个股自动生成 SMR 板块截面 peers。

    按市场分发：A 股经申万一级行业成分自动生成；港股/美股因无公开成分数据源
    返回 unavailable（`pcts=None`），保留手动 `--peers` 作为唯一途径。

    Args:
        code: 股票代码（A 股 6 位；市场为 hk/us 时仅用于标识，不做映射）。
        market: 市场标识，取值 "a"（A股）/ "hk"（港股）/ "us"（美股）。
        max_members: 截面成分数量上限。

    Returns:
        dict: {industry, pcts(250日涨幅列表), status, count, skipped, note?}。

    Raises:
        RuntimeError: A 股无法确定个股所属行业时。
    """
    if market == "hk":
        return {"industry": None, "pcts": None, "status": "unavailable",
                "count": 0, "skipped": 0, "note": _MARKET_UNAVAILABLE_NOTE["hk"]}
    if market == "us":
        return {"industry": None, "pcts": None, "status": "unavailable",
                "count": 0, "skipped": 0, "note": _MARKET_UNAVAILABLE_NOTE["us"]}
    industry = get_industry_of_stock(code)
    if not industry:
        raise RuntimeError(f"未找到个股 {code} 的行业归属（行业缓存无该股）")
    res = get_sector_peers(industry, max_members=max_members)
    return {
        "industry": industry,
        "pcts": list(res["peers"].values()),
        "status": res["status"],
        "count": len(res["peers"]),
        "skipped": res.get("skipped", 0),
    }