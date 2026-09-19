#!/usr/bin/env python3
"""宏观校准引擎（macro-calibrator）——GARP 框架宏观三表硬编码 + stage 判定查表。

本模块是《中长期价值成长（GARP）投资框架》第五部分·四「宏观环境适配」的
**数据结构权威载体**，将框架正文（行 687-747）的三张参数表 + 一张坐标换算表
逐格硬编码为 Python 字典，并提供按「美林四档」主键（衰退 / 复苏 / 过热 / 滞胀）
直接查表、零换算、零心算的纯函数接口。

定位：Phase 2「宏观校准引擎」第一棒 + 第二棒 + 第三棒（P2-1 + P2-2 + P2-3）。
- 三表权威数据结构 + stage 枚举/查表核心（P2-1，纯函数，零网络）；
- `data` 子命令：经 akshare 拉取宏观指标（10Y 国债收益率 / PMI / CPI / PPI /
  社融增量 / 新增信贷）并落地缓存（data/macro/），输出指标快照与利率/经济阶段
  软判定（P2-2）；
- `calibrate` 子命令：输入标的 PEG / 现金仓位 / 单只占比，按「美林四档」输出
  宏观校准后的 PEG 判定、现金下限、单只上限与可审计 validation（P2-3，纯查表 +
  精确数值比较，默认零网络）。

本模块**不实现「宏信号 → stage」的数值阈值硬判定**（框架正文只给定性规则、未给
显式阈值；软判定结果一律附 manual_review=true，属非权威启发式、可人工覆盖）。

Note:
    所有参数均来自硬编码字典取值，禁止 LLM 心算或公式推导。权威口径唯一来源为
    框架第五部分·四（行 687-747），本模块不臆造框架未显式给出的数值（一律 None）。

用法（示例）:
    {py} tools/specialized/macro_calibrator.py stage --stage 复苏
    {py} tools/specialized/macro_calibrator.py stage --stage 滞胀 --markdown
    {py} tools/specialized/macro_calibrator.py data
    {py} tools/specialized/macro_calibrator.py data --no-cache
    {py} tools/specialized/macro_calibrator.py calibrate --stage 复苏 --peg 1.3 --current-cash 15 --single-stake 12
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失时降级为不读取 .env
    load_dotenv = None

try:
    import akshare as ak
except ImportError:  # pragma: no cover - 仅刷新数据时才需要 akshare
    ak = None

# ---------------------------------------------------------------------------
# 宏观阶段枚举（美林四档，中文规范值）
# ---------------------------------------------------------------------------

#: 美林四档规范枚举（与框架原文一致，直接用于查表与输出）
STAGE_ENUM: tuple[str, ...] = ("衰退", "复苏", "过热", "滞胀")

# ---------------------------------------------------------------------------
# 表 D：宏观阶段坐标换算关系（权威 = 框架行 687-694）
# ---------------------------------------------------------------------------

#: 美林四档 → 利率环境（表一锚）与经济周期档（表二锚）的坐标换算。
#: 利率环境是估值参数锚，经济周期是仓位参数锚。
STAGE_COORD_MAP: dict[str, dict[str, str]] = {
    "衰退": {"rate_env": "降息启动（临时按1.0）", "econ_cycle": "衰退档（收紧）"},
    "复苏": {"rate_env": "低利率（放宽至1.5）", "econ_cycle": "中性/复苏档（基准）"},
    "过热": {"rate_env": "加息（收紧至1.0）", "econ_cycle": "过热档（收紧）"},
    "滞胀": {"rate_env": "高利率+信用收缩（0.8）", "econ_cycle": "滞胀档（最紧）"},
}

# ---------------------------------------------------------------------------
# 表 A：利率环境 → PEG 参数（权威 = 框架表一 行 700-704 + 行 713 滞胀收紧）
# ---------------------------------------------------------------------------

#: 利率/PEG 参数表，主键统一为美林四档（决策 D2）。
#: peg_interval 用 list[float]：2 元素=闭区间；1 元素=仅上限（框架未显式下限）。
#: 「衰退」「滞胀」的低估/高估阈值框架未显式给出，一律 None 不臆造（决策 D3）。
RATE_TABLE: dict[str, dict[str, object]] = {
    "衰退": {
        "rate_env": "降息启动（临时按1.0）",
        "peg_interval": [1.0],
        "peg_undervalue": None,
        "peg_overvalue": None,
        "note": "盈利下行+信用收缩主导，估值先杀后抬；宽信用实质落地（信贷脉冲转正）前临时按1.0",
    },
    "复苏": {
        "rate_env": "低利率（放宽至1.5）",
        "peg_interval": [1.2, 1.5],
        "peg_undervalue": "<1.2",
        "peg_overvalue": ">1.5 减仓，>2 绝对透支清机动仓",
        "note": "降息/低利率周期，放宽档",
    },
    "过热": {
        "rate_env": "加息（收紧至1.0）",
        "peg_interval": [0.8, 1.0],
        "peg_undervalue": "<0.7",
        "peg_overvalue": ">1.2",
        "note": "加息/高利率周期，收紧档；0.7~0.8 为低估上沿与合理下沿之间空档，不主动加仓",
    },
    "滞胀": {
        "rate_env": "高利率+信用收缩（0.8）",
        "peg_interval": [0.8],
        "peg_undervalue": None,
        "peg_overvalue": None,
        "note": "较加息档 0.8~1.0 更紧，合理买入上限下探至 0.8；PEG≥0.8 即不新建仓",
    },
}

# ---------------------------------------------------------------------------
# 表 B：经济周期 → 现金仓位与个股上限（权威 = 框架表二 行 719-723 + 行 729-730）
# ---------------------------------------------------------------------------

#: 经济/仓位参数表，主键统一为美林四档（决策 D2）。
#: cash_floor 保留框架原文字符串，不做数值解析（决策 D5）。
#: single_init / single_verified / single_absolute 为「初始 / 验证后 / 绝对」三档。
ECON_TABLE: dict[str, dict[str, str]] = {
    "衰退": {
        "econ_cycle": "衰退档（收紧）",
        "cash_floor": "30%~40% 或更高",
        "single_init": "≤8%",
        "single_verified": "≤12%",
        "single_absolute": "≤15%",
        "industry_cap": "≤30%",
    },
    "复苏": {
        "econ_cycle": "中性/复苏档（基准）",
        "cash_floor": "10%~20%（估值分位>80%时提高至20%~30%）",
        "single_init": "≤10%",
        "single_verified": "≤15%",
        "single_absolute": "≤20%",
        "industry_cap": "≤40%",
    },
    "过热": {
        "econ_cycle": "过热档（收紧）",
        "cash_floor": "≥25%",
        "single_init": "≤8%",
        "single_verified": "≤12%",
        "single_absolute": "≤15%",
        "industry_cap": "≤25%",
    },
    "滞胀": {
        "econ_cycle": "滞胀档（最紧）",
        "cash_floor": "≥40%",
        "single_init": "≤6%",
        "single_verified": "≤10%",
        "single_absolute": "≤12%",
        "industry_cap": "≤20%",
    },
}

# ---------------------------------------------------------------------------
# 表 C：美林时钟矩阵（权威 = 框架行 736-741）
# ---------------------------------------------------------------------------

#: 美林时钟 + 信用周期 → 框架参数快速对照表，主键为美林四档。
#: peg_ceiling 用 float（数值型上限），peg_ceiling_note 为口径备注（放宽/收紧等）。
MERRILL_TABLE: dict[str, dict[str, object]] = {
    "衰退": {
        "rate_credit": "降息启动、信用收缩",
        "style": "防御、低波成长优先",
        "peg_ceiling": 1.0,
        "peg_ceiling_note": "临时收紧",
        "cash_floor": "30%~40%",
        "single_cap_verified": "≤12%",
    },
    "复苏": {
        "rate_credit": "低利率、信用扩张初期",
        "style": "成长/顺周期优先",
        "peg_ceiling": 1.5,
        "peg_ceiling_note": "放宽",
        "cash_floor": "10%~20%",
        "single_cap_verified": "≤15%",
    },
    "过热": {
        "rate_credit": "加息、信用扩张见顶",
        "style": "周期/价值优先",
        "peg_ceiling": 1.0,
        "peg_ceiling_note": "收紧",
        "cash_floor": "≥25%",
        "single_cap_verified": "≤12%",
    },
    "滞胀": {
        "rate_credit": "高利率、信用收缩",
        "style": "现金/防御为主",
        "peg_ceiling": 0.8,
        "peg_ceiling_note": "最紧",
        "cash_floor": "≥40%",
        "single_cap_verified": "≤10%",
    },
}

# ---------------------------------------------------------------------------
# P2-3：宏观校准数值常量表（权威 = 框架第五部分·四 + 第三部分·仓位）
#   - CALIBRATE_PEG：PEG 校准阈值（方案 3.2，逐格落盘来源行号）
#   - CALIBRATE_CASH_FLOOR：现金下限数值（方案 3.4）
#   - CALIBRATE_SINGLE_CAP：单只上限三档 + 行业上限（方案 3.5）
# ---------------------------------------------------------------------------

#: PEG 校准数值阈值表（权威 = 框架表一行 700-704 + 行 712/713 + 美林矩阵行 736-741）。
#: peg_ceiling 为「合理买入上限」（= RATE_TABLE peg_interval 末元素）；peg_under /
#: peg_over 为低估 / 高估阈值（float | None；None 表示框架未显式给出，不臆造）。
CALIBRATE_PEG: dict[str, dict[str, float | None]] = {
    # 行 738/746：衰退期降息启动但盈利下行+信用收缩主导，估值先杀后抬，临时按 1.0。
    "衰退": {"peg_ceiling": 1.0, "peg_under": None, "peg_over": None},
    # 行 703-704/739：降息/低利率周期，放宽档；<1.2 低估、>1.5 减仓、>2 绝对透支。
    "复苏": {"peg_ceiling": 1.5, "peg_under": 1.2, "peg_over": 1.5},
    # 行 701/740：加息/高利率周期，收紧档；<0.7 低估、0.7~0.8 空档不主动加仓、>1.2 高估。
    "过热": {"peg_ceiling": 1.0, "peg_under": 0.7, "peg_over": 1.2},
    # 行 712-713/741：滞胀（高利率+信用收缩）较加息档更紧，上限下探至 0.8。
    "滞胀": {"peg_ceiling": 0.8, "peg_under": None, "peg_over": None},
}

#: 现金下限数值表（权威 = 框架行 721/729/730/748）。
#: 取各阶段现金下限的最小值用于达标判定（单位：占总资产 %）。
CALIBRATE_CASH_FLOOR: dict[str, float] = {
    "衰退": 30.0,  # 行721/738：30%~40% 或更高
    "复苏": 10.0,  # 行721/748：常态 10%~20%
    "过热": 25.0,  # 行730/740：≥25%
    "滞胀": 40.0,  # 行729/741：≥40%
}

#: 单只上限三档 + 单一行业上限数值表（权威 = 框架行 722/729/730 + 行 461）。
#: 单位均为「占总资产 %」，tier 枚举见 STAKE_TIER_ENUM。
CALIBRATE_SINGLE_CAP: dict[str, dict[str, float]] = {
    "衰退": {"initial": 8.0, "verified": 12.0, "absolute": 15.0, "industry_cap": 30.0},
    "复苏": {"initial": 10.0, "verified": 15.0, "absolute": 20.0, "industry_cap": 40.0},
    "过热": {"initial": 8.0, "verified": 12.0, "absolute": 15.0, "industry_cap": 25.0},
    "滞胀": {"initial": 6.0, "verified": 10.0, "absolute": 12.0, "industry_cap": 20.0},
}

#: 单只上限档位枚举（与 --stake-tier 一致；默认 verified，对齐 P2-1 summary 决策 D4）。
STAKE_TIER_ENUM: tuple[str, ...] = ("initial", "verified", "absolute")

#: tier 枚举 → ECON_TABLE 单只档位列名（initial→single_init 等，避免列名歧义）。
_TIER_KEY_MAP: dict[str, str] = {
    "initial": "single_init",
    "verified": "single_verified",
    "absolute": "single_absolute",
}

#: PEG 严重透支红线（权威 = 框架行 706/712，不因降息取消）；严格大于才触发。
PEG_RED_FLAG_THRESHOLD: float = 2.0

#: 校准阈值的框架来源行号（供 validation 可审计复现，逐格落盘）。
#: peg / cash 行号分别对应 CALIBRATE_PEG / CALIBRATE_CASH_FLOOR。
_CALIBRATE_PEG_SOURCE: dict[str, str] = {
    "衰退": "行738/746", "复苏": "行704/739", "过热": "行702/740", "滞胀": "行713/741",
}
_CALIBRATE_CASH_SOURCE: dict[str, str] = {
    "衰退": "行721/738", "复苏": "行721/748", "过热": "行730/740", "滞胀": "行729/741",
}
_CALIBRATE_SINGLE_SOURCE: str = "行722/729/730 + 行461"

# ---------------------------------------------------------------------------
# P2-2：宏观数据缓存与 akshare 拉取（路径 / TTL / 工具函数）
# ---------------------------------------------------------------------------

#: 工作区根目录（本文件位于 tools/specialized/，向上 3 层到达项目根）。
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

#: 宏观数据缓存目录与单文件快照（方案决策 D4）。
_MACRO_CACHE_DIR: Path = _PROJECT_ROOT / "data" / "macro"
_MACRO_CACHE_FILE: Path = _MACRO_CACHE_DIR / "macro_snapshot.json"

#: 默认缓存有效期（天），可由 .env 的 MACRO_CACHE_TTL_DAYS 覆盖。
_DEFAULT_TTL_DAYS: int = 7

#: 各指标缺失时生成的搜索提示关键词（供人工用搜索五工具补数，方案决策 D3）。
_SEARCH_HINT_MAP: dict[str, str] = {
    "cn_10y_yield": "中国 10 年期国债收益率 最新",
    "pmi_manufacturing": "中国 制造业 PMI 最新",
    "cpi_yoy": "中国 CPI 同比 最新",
    "ppi_yoy": "中国 PPI 同比 最新",
    "social_financing_increment": "中国 社会融资规模增量 最新",
    "credit_impulse": "中国 信贷脉冲 社融 TTM 同比",
}


def _load_dotenv() -> None:
    """从工作区根目录 .env 加载环境变量（若已安装 python-dotenv）。

    本文件位于 tools/specialized/ 下，需向上 3 层到达项目根目录。
    """
    if load_dotenv is not None:
        load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _parse_int_env(var_name: str, default: int) -> int:
    """从环境变量读取整数配置，缺失或非法时回退到默认值。

    遵循「配置失败不影响功能」原则，避免 .env 笔误导致工具无法运行。

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

#: 宏观缓存有效期（天），.env 可配置（缺省 7）。
MACRO_CACHE_TTL_DAYS: int = _parse_int_env("MACRO_CACHE_TTL_DAYS", _DEFAULT_TTL_DAYS)


def _is_cache_fresh(cache_file: Path) -> bool:
    """判断缓存文件是否在宏观 TTL 有效期之内。

    Args:
        cache_file: 缓存文件路径。

    Returns:
        文件存在且未过期返回 True；缺失或已过期返回 False。
    """
    if not cache_file.exists():
        return False
    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
    return (datetime.now() - mtime).days < MACRO_CACHE_TTL_DAYS


def _read_cache() -> dict | None:
    """读取宏观快照缓存 JSON；缺失或损坏时返回 None。

    Returns:
        解析后的快照 dict；失败返回 None。
    """
    if not _MACRO_CACHE_FILE.exists():
        return None
    try:
        with open(_MACRO_CACHE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _atomic_write_json(obj: dict, cache_file: Path) -> None:
    """原子写入 JSON 缓存：先写 .tmp 再 os.replace，避免并发写坏。

    Args:
        obj: 待写入的 dict。
        cache_file: 目标缓存文件路径。
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
    with open(tmp_file, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp_file, cache_file)


def _to_float_or_none(value: object) -> float | None:
    """将单元格值转换为 float，空值 / 非法值 / NaN 转换为 None。

    Args:
        value: 原始单元格值（可能为 None、空串、数字字符串或 NaN）。

    Returns:
        可转换的 float；否则返回 None。
    """
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN 判定
        return None
    text = str(value).strip()
    if text == "" or text.lower() in ("nan", "none"):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _indicator(value: float | None, unit: str, as_of: str | None,
               source: str, status: str = "ok", trend: str | None = None) -> dict:
    """构造统一结构的指标快照条目。

    Args:
        value: 指标数值（None 表示缺失）。
        unit: 单位。
        as_of: 数据截止日期/月份（None 表示缺失）。
        source: 数据来源标识。
        status: ok / stale / insufficient。
        trend: 趋势方向（up / down / flat / unknown），软判定启发式输入。

    Returns:
        统一字段的指标 dict。
    """
    return {
        "value": value,
        "unit": unit,
        "as_of": as_of,
        "source": source,
        "status": status,
        "trend": trend,
    }


def _parse_date(raw: object) -> tuple[datetime | None, str]:
    """解析 YYYY-MM-DD 日期列，返回 (可比较键, 规范字符串)。

    Args:
        raw: 日期单元格（str 或 pandas Timestamp）。

    Returns:
        (datetime, "YYYY-MM-DD")；解析失败返回 (None, 原文)。
    """
    text = str(raw).strip()
    try:
        dt = datetime.strptime(text[:10], "%Y-%m-%d")
        return dt, dt.strftime("%Y-%m-%d")
    except ValueError:
        return None, text


def _parse_month_cn(raw: object) -> tuple[tuple[int, int] | None, str]:
    """解析「YYYY年MM月份」中文月份列，返回 (可比较键, 规范字符串)。

    Args:
        raw: 月份单元格（如「2026年08月份」）。

    Returns:
        ((年, 月), "YYYY-MM")；解析失败返回 (None, 原文)。
    """
    text = str(raw).strip()
    match = re.search(r"(\d{4})年(\d{1,2})月", text)
    if not match:
        return None, text
    year, month = int(match.group(1)), int(match.group(2))
    return (year, month), f"{year:04d}-{month:02d}"


def _parse_month_int(raw: object) -> tuple[tuple[int, int] | None, str]:
    """解析 YYYYMM 整数/字符串月份列，返回 (可比较键, 规范字符串)。

    Args:
        raw: 月份单元格（如 202604 或 "202604"）。

    Returns:
        ((年, 月), "YYYY-MM")；解析失败返回 (None, 原文)。
    """
    text = str(raw).strip()
    match = re.match(r"^(\d{4})(\d{2})$", text)
    if not match:
        return None, text
    year, month = int(match.group(1)), int(match.group(2))
    return (year, month), f"{year:04d}-{month:02d}"


def _fetch_cn_10y() -> dict:
    """拉取 10 年期国债收益率并计算近 6 月趋势方向（软判定启发式）。

    Returns:
        cn_10y_yield 指标 dict，含 value / as_of / trend。
    """
    df = ak.bond_zh_us_rate()
    points = []
    for _, row in df.iterrows():
        value = _to_float_or_none(row.get("中国国债收益率10年"))
        key, label = _parse_date(row.get("日期"))
        if key is None or value is None:
            continue
        points.append((key, value, label))
    points.sort(key=lambda p: p[0])

    if not points:
        return _indicator(None, "%", None, "akshare", "insufficient")

    latest = points[-1]
    # 找约 180 天前最接近的参照点，计算首尾方向。
    target = latest[0] - timedelta(days=180)
    anchor = None
    for point in points:
        if point[0] <= target:
            anchor = point
        else:
            break

    if anchor is None:
        trend = "unknown"
    else:
        diff = latest[1] - anchor[1]
        # 10bp（0.1 个百分点）为抗噪声最小方向阈值。
        # 注意：此阈值为实现层启发式，非框架显式参数，标记 manual_review。
        trend = "up" if diff > 0.10 else "down" if diff < -0.10 else "flat"

    return _indicator(round(latest[1], 4), "%", latest[2], "akshare", "ok", trend)


def _fetch_monthly_cn(ak_fn, value_col: str, unit: str) -> dict:
    """按中文月份列取最新有效行，构造月度指标。

    Args:
        ak_fn: akshare 接口函数。
        value_col: 取值列名。
        unit: 指标单位。

    Returns:
        月度指标 dict；无有效值时返回 status=insufficient。
    """
    df = ak_fn()
    best_key = None
    best_value = None
    best_label = None
    for _, row in df.iterrows():
        key, label = _parse_month_cn(row.get("月份"))
        value = _to_float_or_none(row.get(value_col))
        if key is None or value is None:
            continue
        if best_key is None or key > best_key:
            best_key, best_value, best_label = key, value, label

    if best_value is None:
        return _indicator(None, unit, None, "akshare", "insufficient")

    return _indicator(round(best_value, 4), unit, best_label, "akshare", "ok")


def _fetch_social_financing() -> tuple[dict, dict]:
    """拉取社融增量序列，产出增量最新值与派生信贷脉冲（TTM 同比）。

    信贷脉冲 = TTM(近 12 月社融增量滚动和) / 上年同期 TTM - 1，程序精确计算、
    公式落盘，属精确算术而非 LLM 心算（方案决策 D7）。序列不足 24 月时
    信贷脉冲标 insufficient。

    Returns:
        (social_financing_increment, credit_impulse) 两个指标 dict。
    """
    df = ak.macro_china_shrzgm()
    points = []
    for _, row in df.iterrows():
        value = _to_float_or_none(row.get("社会融资规模增量"))
        key, label = _parse_month_int(row.get("月份"))
        if key is None or value is None:
            continue
        points.append((key, value, label))
    points.sort(key=lambda p: p[0])

    increment = _indicator(None, "亿元", None, "akshare", "insufficient")
    impulse = _indicator(None, "比率", None, "derived(akshare)", "insufficient")

    if not points:
        return increment, impulse

    latest = points[-1]
    increment = _indicator(round(latest[1], 4), "亿元", latest[2], "akshare", "ok")

    if len(points) < 24:
        impulse = _indicator(None, "比率", latest[2], "derived(akshare)",
                             "insufficient")
        impulse["note"] = f"社融序列仅 {len(points)} 月有效点，不足 24 月，无法计算 TTM 同比"
        return increment, impulse

    recent = points[-24:]
    ttm_cur = sum(p[1] for p in recent[12:])
    ttm_prev = sum(p[1] for p in recent[:12])
    if ttm_prev == 0:
        impulse = _indicator(None, "比率", latest[2], "derived(akshare)",
                             "insufficient")
        impulse["note"] = "上年同期 TTM 为 0，无法计算同比"
        return increment, impulse

    ratio = ttm_cur / ttm_prev - 1.0
    impulse = _indicator(round(ratio, 6), "比率", latest[2], "derived(akshare)", "ok")
    impulse["formula"] = "credit_impulse = TTM(近12月社融增量) / 上年同期TTM - 1"
    impulse["ttm_cur"] = round(ttm_cur, 2)
    impulse["ttm_prev"] = round(ttm_prev, 2)
    return increment, impulse


def _fetch_new_financial_credit() -> dict | None:
    """拉取新增信贷「当月-同比增长」作为信贷脉冲交叉线索（辅助，非必需）。

    Returns:
        交叉线索 dict {value, as_of}；接口失败或无有效值返回 None。
    """
    try:
        df = ak.macro_china_new_financial_credit()
    except Exception:
        return None

    best = None
    for _, row in df.iterrows():
        value = _to_float_or_none(row.get("当月-同比增长"))
        key, label = _parse_month_int(row.get("月份"))
        if key is None or value is None:
            continue
        if best is None or key > best[0]:
            best = (key, label, value)

    if best is None:
        return None
    return {"value": round(best[2], 4), "as_of": best[1]}


def _fetch_fresh() -> dict:
    """执行一次完整宏观指标拉取，单指标失败仅标 insufficient 不整体中断。

    Returns:
        数据快照 dict（data_ts / indicators / search_hints / source / degraded）。

    Raises:
        RuntimeError: akshare 未安装。
    """
    if ak is None:
        raise RuntimeError("akshare 未安装，无法拉取宏观指标。请运行: pip install akshare")

    indicators: dict[str, dict] = {}

    # 10 年期国债收益率（含趋势方向）。
    try:
        indicators["cn_10y_yield"] = _fetch_cn_10y()
    except Exception:
        indicators["cn_10y_yield"] = _indicator(None, "%", None, "akshare", "insufficient")

    # PMI / CPI / PPI（月度，取最新有效行）。
    for key, ak_fn, value_col, unit in (
        ("pmi_manufacturing", ak.macro_china_pmi, "制造业-指数", "点"),
        ("cpi_yoy", ak.macro_china_cpi, "全国-同比增长", "%"),
        ("ppi_yoy", ak.macro_china_ppi, "当月同比增长", "%"),
    ):
        try:
            indicators[key] = _fetch_monthly_cn(ak_fn, value_col, unit, key)
        except Exception:
            indicators[key] = _indicator(None, unit, None, "akshare", "insufficient")

    # 社融增量 + 派生信贷脉冲（同一份序列）。
    try:
        increment, impulse = _fetch_social_financing()
        indicators["social_financing_increment"] = increment
        indicators["credit_impulse"] = impulse
    except Exception:
        indicators["social_financing_increment"] = _indicator(
            None, "亿元", None, "akshare", "insufficient")
        indicators["credit_impulse"] = _indicator(
            None, "比率", None, "derived(akshare)", "insufficient")

    # 新增信贷交叉线索（辅助，失败不影响 degraded）。
    cross_check = _fetch_new_financial_credit()
    if cross_check is not None:
        indicators["credit_impulse"]["cross_check"] = cross_check

    # 汇总缺失指标，生成搜索提示。
    search_hints = []
    degraded = False
    for key, item in indicators.items():
        if item.get("status") != "ok":
            degraded = True
            search_hints.append(_SEARCH_HINT_MAP.get(key, key))

    return {
        "data_ts": datetime.now().strftime("%Y-%m-%d"),
        "indicators": indicators,
        "search_hints": search_hints,
        "source": "akshare+search_hint" if degraded else "akshare",
        "degraded": degraded,
    }


def fetch_macro_indicators(force_refresh: bool = False) -> dict:
    """拉取并缓存宏观指标，返回结构化数据快照（hit → refresh → stale）。

    Args:
        force_refresh: True 时跳过缓存有效期检查，强制刷新（对应 --no-cache）。

    Returns:
        数据快照 dict，含 data_ts / indicators / search_hints / source /
        degraded / cache_status。

    Raises:
        RuntimeError: 刷新失败且无可降级的旧缓存。
    """
    if not force_refresh and _is_cache_fresh(_MACRO_CACHE_FILE):
        cached = _read_cache()
        if cached is not None:
            cached["cache_status"] = "hit"
            return cached

    try:
        data = _fetch_fresh()
        # 任一指标都未成功拉取时视为整体刷新失败，降级旧缓存而非覆盖为全空。
        if not any(item.get("status") == "ok" for item in data["indicators"].values()):
            raise RuntimeError("全部宏观指标拉取失败")
        _atomic_write_json(data, _MACRO_CACHE_FILE)
        data["cache_status"] = "refresh"
        return data
    except Exception:
        cached = _read_cache()
        if cached is not None:
            cached["cache_status"] = "stale"
            cached["degraded"] = True
            cached["source"] = "cache_stale"
            return cached
        raise


def classify_rate_stage(indicators: dict) -> dict:
    """基于框架定性规则对利率阶段做软判定（无数值阈值）。

    判定仅依据框架行 709「以国债收益率趋势判断利率阶段」与行 701-703 三档、
    行 712 滞胀特殊档。所用「近 6 月首尾方向 + 10bp 噪声阈值」为实现层最小
    启发式，非框架显式参数，一律 manual_review=true、confidence=低，可人工覆盖。

    Args:
        indicators: fetch_macro_indicators 返回的 indicators 子表。

    Returns:
        {stage, confidence, basis, manual_review}；数据不足时 stage=「数据不足」。
    """
    base = {"stage": "数据不足", "confidence": "低", "basis": "", "manual_review": True}

    item = indicators.get("cn_10y_yield")
    if item is None or item.get("status") != "ok" or item.get("value") is None:
        base["basis"] = "10Y 国债收益率缺失，无法判断利率趋势（框架行709）"
        return base

    trend = item.get("trend")
    if trend not in ("up", "down", "flat"):
        base["basis"] = "10Y 国债收益率趋势参照点不足，无法判断利率阶段（框架行709）"
        return base

    # 滞胀特判：利率上行 + 信用收缩（信贷脉冲为负），见框架行 712。
    credit = indicators.get("credit_impulse")
    credit_contracting = (credit is not None and credit.get("status") == "ok"
                          and credit.get("value") is not None and credit["value"] < 0)
    if trend == "up" and credit_contracting:
        return {
            "stage": "高利率+信用收缩（滞胀）",
            "confidence": "低",
            "basis": "10Y 国债收益率近 6 月上行 + 信贷脉冲为负（信用收缩），判定为滞胀利率档（框架行712，非权威启发式）",
            "manual_review": True,
        }

    trend_cn = {"up": "上行", "down": "下行", "flat": "横盘"}[trend]
    row = {"up": "701", "down": "703", "flat": "702"}[trend]
    stage = {"up": "加息/高利率", "down": "降息/低利率", "flat": "中性"}[trend]
    return {
        "stage": stage,
        "confidence": "低",
        "basis": f"10Y 国债收益率近 6 月趋势{trend_cn}，判定为利率阶段 {stage}（框架行709/行{row}，非权威启发式）",
        "manual_review": True,
    }


def classify_econ_stage(indicators: dict) -> dict:
    """基于框架定性规则对经济阶段（美林四档）做软判定（无数值阈值）。

    主锚为信贷脉冲正负（信用周期，框架行 744「信用周期定总仓位」），辅以
    PMI 荣枯线 50（通用宏观共识口径，非框架显式参数，仅作低置信启发式）与
    利率趋势。判定一律 manual_review=true、confidence=低，可以人工覆盖。

    Args:
        indicators: fetch_macro_indicators 返回的 indicators 子表。

    Returns:
        {stage, confidence, basis, manual_review}；数据不足时 stage=「数据不足」。
    """
    base = {"stage": "数据不足", "confidence": "低", "basis": "", "manual_review": True}

    credit = indicators.get("credit_impulse")
    if credit is None or credit.get("status") != "ok" or credit.get("value") is None:
        base["basis"] = "信贷脉冲缺失，无法判断信用周期与美林阶段（框架行744）"
        return base

    pmi = indicators.get("pmi_manufacturing")
    pmi_ok = pmi is not None and pmi.get("status") == "ok" and pmi.get("value") is not None
    pmi_weak = pmi_ok and pmi["value"] < 50.0  # 荣枯线下方，景气收缩（通用共识，非框架参数）

    rate_trend = None
    rate_item = indicators.get("cn_10y_yield")
    if rate_item is not None and rate_item.get("status") == "ok":
        rate_trend = rate_item.get("trend")

    if credit["value"] < 0:
        # 信用收缩成立。
        if pmi_weak and rate_trend == "up":
            return {
                "stage": "滞胀",
                "confidence": "低",
                "basis": "信用收缩(信贷脉冲<0)+盈利/景气下行(PMI<50)+利率上行，符合滞胀三杀（框架行712/728，非权威启发式）",
                "manual_review": True,
            }
        if pmi_weak:
            return {
                "stage": "衰退",
                "confidence": "低",
                "basis": "信用收缩(信贷脉冲<0)+盈利/景气下行(PMI<50)，命中衰退两信号（框架行726）；利率见顶拐头待人工确认",
                "manual_review": True,
            }
        return {
            "stage": "衰退",
            "confidence": "低",
            "basis": "信用收缩(信贷脉冲<0)成立，但景气信号不足以交叉印证，按信用周期主锚倾向衰退（框架行726/744，非权威启发式）",
            "manual_review": True,
        }

    # 信用扩张（信贷脉冲 >= 0）。
    if pmi_ok and pmi["value"] >= 50.0:
        basis = "信用扩张(信贷脉冲>=0)+景气扩张(PMI>=50)，符合复苏窗口（框架行745/748，非权威启发式）"
        if rate_trend == "up":
            basis += "；利率上行或接近过热，需人工判断信用是否见顶（框架行729）"
        return {"stage": "复苏", "confidence": "低", "basis": basis, "manual_review": True}

    return {
        "stage": "复苏",
        "confidence": "低",
        "basis": "信用扩张(信贷脉冲>=0)成立，景气信号待确认，倾向复苏初期（框架行745，非权威启发式）",
        "manual_review": True,
    }


def _validate_stage(stage: str) -> str:
    """校验并返回规范化宏观测阶段（美林四档）。

    Args:
        stage: 美林阶段，须为 STAGE_ENUM 之一（衰退/复苏/过热/滞胀）。

    Returns:
        str: 规范化后的中文阶段（即输入本身，若合法）。

    Raises:
        ValueError: stage 非 STAGE_ENUM 之一时抛出，并提示合法枚举。
    """
    if stage not in STAGE_ENUM:
        raise ValueError(f"非法 stage：{stage!r}，合法枚举：{' / '.join(STAGE_ENUM)}")
    return stage


def _validate_tier(tier: str) -> str:
    """校验并返回规范化的单只上限档位（initial/verified/absolute）。

    Args:
        tier: 单只上限档位，须为 STAKE_TIER_ENUM 之一。

    Returns:
        str: 规范化后的档位（即输入本身，若合法）。

    Raises:
        ValueError: tier 非 STAKE_TIER_ENUM 之一时抛出，并提示合法枚举。
    """
    if tier not in STAKE_TIER_ENUM:
        raise ValueError(f"非法 stake_tier：{tier!r}，合法枚举：{' / '.join(STAKE_TIER_ENUM)}")
    return tier


def _validate_positive(name: str, value: float) -> float:
    """校验正值输入（严格 > 0，NaN 视为非法）。

    Args:
        name: 字段中文名（用于报错提示）。
        value: 待校验数值。

    Returns:
        float: 原值（合法时）。

    Raises:
        ValueError: 数值非 > 0（含 NaN）时抛出。
    """
    if not value > 0:
        raise ValueError(f"非法 {name}：{value}，须 > 0")
    return value


def _validate_percent(name: str, value: float) -> float:
    """校验占比输入是否落在 [0, 100]（单位：占总资产 %）。

    Args:
        name: 字段中文名（用于报错提示）。
        value: 待校验数值。

    Returns:
        float: 原值（合法时）。

    Raises:
        ValueError: 数值非 [0, 100]（含 NaN）时抛出。
    """
    if not (0.0 <= value <= 100.0):
        raise ValueError(f"非法 {name}：{value}，须在 0~100 之间（占总资产 %）")
    return value


def rate_stage(stage: str) -> dict:
    """返回给定美林阶段的利率/PEG 参数表（表 A 对应行）。

    Args:
        stage: 美林阶段，须为 STAGE_ENUM 之一（衰退/复苏/过热/滞胀）。

    Returns:
        dict: RATE_TABLE 对应行 + 回显字段「stage」（中文阶段名）。

    Raises:
        ValueError: stage 非法时抛出。
    """
    stage = _validate_stage(stage)
    return {"stage": stage, **RATE_TABLE[stage]}


def econ_stage(stage: str) -> dict:
    """返回给定美林阶段的经济周期/仓位参数表（表 B 对应行）。

    Args:
        stage: 美林阶段，须为 STAGE_ENUM 之一（衰退/复苏/过热/滞胀）。

    Returns:
        dict: ECON_TABLE 对应行 + 回显字段「stage」（中文阶段名）。

    Raises:
        ValueError: stage 非法时抛出。
    """
    stage = _validate_stage(stage)
    return {"stage": stage, **ECON_TABLE[stage]}


def merrill_stage(stage: str) -> dict:
    """返回给定美林阶段的美林时钟矩阵参数表（表 C 对应行）。

    Args:
        stage: 美林阶段，须为 STAGE_ENUM 之一（衰退/复苏/过热/滞胀）。

    Returns:
        dict: MERRILL_TABLE 对应行 + 回显字段「stage」（中文阶段名）。

    Raises:
        ValueError: stage 非法时抛出。
    """
    stage = _validate_stage(stage)
    return {"stage": stage, **MERRILL_TABLE[stage]}


def summary(stage: str) -> dict:
    """聚合三表输出给定美林阶段的完整参数表。

    Args:
        stage: 美林阶段，须为 STAGE_ENUM 之一（衰退/复苏/过热/滞胀）。

    Returns:
        dict: 顶层含「stage」回显与三类子表行（rate_stage / econ_stage /
            merrill_stage），并给出聚合字段 peg_interval / cash_floor /
            single_cap。子表行为纯表行（不含 stage 键），对齐方案 4.3 schema。

    Raises:
        ValueError: stage 非法时抛出。
    """
    stage = _validate_stage(stage)

    # 复用三子函数并剥离其回显的 stage 键，使子表行对齐 4.3 纯表行结构。
    rate_row = {k: v for k, v in rate_stage(stage).items() if k != "stage"}
    econ_row = {k: v for k, v in econ_stage(stage).items() if k != "stage"}
    merrill_row = {k: v for k, v in merrill_stage(stage).items() if k != "stage"}

    econ = ECON_TABLE[stage]
    return {
        "stage": stage,
        "rate_stage": rate_row,
        "econ_stage": econ_row,
        "merrill_stage": merrill_row,
        # 聚合字段：PEG 区间取表 A；现金下限与单只上限取表 B（验证后档，决策 D4）。
        "peg_interval": RATE_TABLE[stage]["peg_interval"],
        "cash_floor": econ["cash_floor"],
        "single_cap": econ["single_verified"],
    }


def calibrate_peg(stage: str, peg: float) -> dict:
    """按宏观阶段输出 PEG 校准 verdict（程序精确数值比较）。

    判定规则见方案 3.3：低估 → 合理买入 → 高估/合理偏贵/超出上限；
    全局红线 PEG > 2 附加 red_flag（框架行 706/712，不因降息取消）。

    Args:
        stage: 美林四档（衰退/复苏/过热/滞胀）。
        peg: 标的当前调整后 PEG（须 > 0）。

    Returns:
        dict: verdict / peg_interval / peg_ceiling / peg_under /
            peg_over / red_flag 与 compare（比较过程字符串，供 validation）。

    Raises:
        ValueError: stage 非法或 peg 非正数。
    """
    stage = _validate_stage(stage)
    _validate_positive("peg", peg)

    row = CALIBRATE_PEG[stage]
    ceiling = row["peg_ceiling"]
    under = row["peg_under"]
    over = row["peg_over"]

    if under is not None and peg < under:
        verdict = "低估（可加仓）"
        compare = f"{peg} < {under} → {verdict}"
    elif peg <= ceiling:
        verdict = "合理买入"
        compare = (f"{under} <= {peg} <= {ceiling} → {verdict}"
                   if under is not None else f"{peg} <= {ceiling} → {verdict}")
    elif over is not None and peg > over:
        verdict = "高估（减机动仓）"
        compare = f"{peg} > {over} → {verdict}"
    elif over is not None and ceiling < peg <= over:
        verdict = "合理偏贵（持有不加仓）"
        compare = f"{ceiling} < {peg} <= {over} → {verdict}"
    else:
        # 衰退/滞胀档：框架未给高估阈值，PEG 超上限即不新建仓。
        verdict = "超出合理上限（不新建仓）"
        compare = f"{peg} > {ceiling} → {verdict}"

    return {
        "verdict": verdict,
        "peg_interval": RATE_TABLE[stage]["peg_interval"],
        "peg_ceiling": ceiling,
        "peg_under": under,
        "peg_over": over,
        "red_flag": peg > PEG_RED_FLAG_THRESHOLD,
        "compare": compare,
    }


def calibrate_cash(stage: str, current_cash: float) -> dict:
    """按宏观阶段输出现金下限与达标判定。

    Args:
        stage: 美林四档（衰退/复苏/过热/滞胀）。
        current_cash: 当前现金占总资产百分比（0~100）。

    Returns:
        dict: cash_floor（原文口径）/ cash_floor_min / cash_ok /
            cash_gap 与 compare。

    Raises:
        ValueError: stage 非法或现金占比越界。
    """
    stage = _validate_stage(stage)
    _validate_percent("current_cash", current_cash)

    floor = CALIBRATE_CASH_FLOOR[stage]
    ok = current_cash >= floor
    gap = current_cash - floor
    sign = "+" if gap > 0 else ""
    compare = f"{current_cash} >= {floor} → {'达标' if ok else '未达标'}（{sign}{gap}）"

    return {
        "cash_floor": ECON_TABLE[stage]["cash_floor"],
        "cash_floor_min": floor,
        "cash_ok": ok,
        "cash_gap": gap,
        "compare": compare,
    }


def calibrate_single(stage: str, single_stake: float,
                     tier: str = "verified") -> dict:
    """按宏观阶段输出单只上限与超限判定。

    Args:
        stage: 美林四档（衰退/复苏/过热/滞胀）。
        single_stake: 当前标的占总资产百分比（0~100）。
        tier: 单只上限档位（initial/verified/absolute），默认 verified。

    Returns:
        dict: single_cap_upper（当前档原文）/ single_cap_value /
            single_cap_ok / single_cap_gap / single_caps（三档明细）/
            industry_cap 与 compare。

    Raises:
        ValueError: stage / tier 非法或单只占比越界。
    """
    stage = _validate_stage(stage)
    tier = _validate_tier(tier)
    _validate_percent("single_stake", single_stake)

    econ = ECON_TABLE[stage]
    cap = CALIBRATE_SINGLE_CAP[stage][tier]
    ok = single_stake <= cap
    gap = cap - single_stake
    sign = "+" if gap > 0 else ""
    compare = f"{single_stake} <= {cap} → {'未超限' if ok else '超限'}（{sign}{gap}）"

    return {
        "single_cap_upper": econ[_TIER_KEY_MAP[tier]],
        "single_cap_value": cap,
        "single_cap_ok": ok,
        "single_cap_gap": gap,
        "single_caps": {
            "initial": econ["single_init"],
            "verified": econ["single_verified"],
            "absolute": econ["single_absolute"],
        },
        "industry_cap": econ["industry_cap"],
        "compare": compare,
    }


def calibrate(stage: str, peg: float, current_cash: float,
              single_stake: float, tier: str = "verified") -> dict:
    """聚合 PEG / 现金 / 单只三类校准，返回含 validation 的完整结论。

    Args:
        stage: 美林四档（衰退/复苏/过热/滞胀）。
        peg: 标的当前调整后 PEG（> 0）。
        current_cash: 当前现金占总资产百分比（0~100）。
        single_stake: 当前标的占总资产百分比（0~100）。
        tier: 单只上限档位，默认 verified。

    Returns:
        dict: 顶层回显输入与三类校准结论 + 可审计 validation（stage_source
            默认为 explicit，CLI 的 --from-data 可改写为 soft_infer）。

    Raises:
        ValueError: 任一输入非法（stage/tier 枚举、PEG 非正、占比越界）。
    """
    peg_result = calibrate_peg(stage, peg)
    cash_result = calibrate_cash(stage, current_cash)
    single_result = calibrate_single(stage, single_stake, tier)

    peg_compare = peg_result.pop("compare")
    cash_compare = cash_result.pop("compare")
    single_compare = single_result.pop("compare")

    note = ""
    if stage == "复苏":
        note = ("复苏档现金下限在估值分位>80%时提高至20%~30%，本工具未引入分位输入，"
                "请人工复核（框架行721/748）")

    validation = {
        "stage_source": "explicit",
        "inputs": {
            "stage": stage,
            "peg": peg,
            "current_cash": current_cash,
            "single_stake": single_stake,
            "stake_tier": tier,
        },
        "rate_source": f"RATE_TABLE['{stage}']（框架{_CALIBRATE_PEG_SOURCE[stage]}）",
        "econ_source": (f"ECON_TABLE['{stage}']（现金框架{_CALIBRATE_CASH_SOURCE[stage]}；"
                        f"单只{_CALIBRATE_SINGLE_SOURCE}）"),
        "peg_compare": peg_compare,
        "cash_compare": cash_compare,
        "single_compare": single_compare,
        "note": note,
    }

    return {
        "stage": stage,
        "peg": peg,
        "current_cash": current_cash,
        "single_stake": single_stake,
        "stake_tier": tier,
        "calibrated_peg_verdict": peg_result,
        **cash_result,
        **single_result,
        "validation": validation,
    }


def _build_markdown(result: dict) -> str:
    """将 summary 结果渲染为人类可读 Markdown 表。

    Args:
        result: summary() 返回的完整参数表。

    Returns:
        str: Markdown 文本（含三张子表与聚合字段摘要）。
    """
    stage = result["stage"]
    lines = [f"## 宏观校准参数表 —— {stage}", ""]

    # 表 A：利率 → PEG 参数
    rate = result["rate_stage"]
    lines += [
        "### （一）利率环境 → PEG 参数",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| 利率环境 | {rate['rate_env']} |",
        f"| PEG 合理买入区间 | {rate['peg_interval']} |",
        f"| 低估（可加仓） | {rate['peg_undervalue']} |",
        f"| 高估（减机动仓） | {rate['peg_overvalue']} |",
        f"| 备注 | {rate['note']} |",
        "",
    ]

    # 表 B：经济周期 → 现金仓位与个股上限
    econ = result["econ_stage"]
    lines += [
        "### （二）经济周期 → 现金仓位与个股上限",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| 经济周期档 | {econ['econ_cycle']} |",
        f"| 现金仓位 | {econ['cash_floor']} |",
        f"| 单只个股上限（初始） | {econ['single_init']} |",
        f"| 单只个股上限（验证后） | {econ['single_verified']} |",
        f"| 单只个股上限（绝对） | {econ['single_absolute']} |",
        f"| 单一行业上限 | {econ['industry_cap']} |",
        "",
    ]

    # 表 C：美林时钟矩阵
    merrill = result["merrill_stage"]
    lines += [
        "### （三）美林时钟 + 信用周期矩阵",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| 利率/信用特征 | {merrill['rate_credit']} |",
        f"| 风格倾向 | {merrill['style']} |",
        f"| PEG 合理买入上限 | {merrill['peg_ceiling']}（{merrill['peg_ceiling_note']}） |",
        f"| 现金仓位 | {merrill['cash_floor']} |",
        f"| 单只上限（验证后） | {merrill['single_cap_verified']} |",
        "",
    ]

    # 聚合字段摘要
    lines += [
        "### 汇总字段",
        "",
        f"- PEG 合理买入区间：`{result['peg_interval']}`",
        f"- 现金仓位下限：`{result['cash_floor']}`",
        f"- 单只上限（验证后）：`{result['single_cap']}`",
    ]
    return "\n".join(lines)


def cmd_stage(args: argparse.Namespace) -> int:
    """`stage` 子命令：按 stage 输出完整参数表（JSON，可选 Markdown）。

    Args:
        args: 已解析的命令行命名空间，含 --stage 与 --markdown。

    Returns:
        int: 0 表示成功，1 表示 stage 非法。
    """
    try:
        result = summary(args.stage)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    # 默认仅打印 JSON；--markdown 时在 JSON 后追加人类可读 Markdown。
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.markdown:
        print()
        print(_build_markdown(result))
    return 0


def cmd_data(args: argparse.Namespace) -> int:
    """`data` 子命令：拉取宏观指标并输出利率/经济阶段软判定。

    Args:
        args: 已解析的命令行命名空间，含 --no-cache。

    Returns:
        int: 0 表示成功，1 表示刷新失败且无可降级旧缓存。
    """
    try:
        data = fetch_macro_indicators(force_refresh=args.no_cache)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1

    indicators = data["indicators"]
    # 组装 4.3 最终 schema：顶层 data_ts / rate_stage / econ_stage /
    # indicators / source / degraded / cache_status（+ search_hints，决策 D3）。
    output = {
        "data_ts": data["data_ts"],
        "rate_stage": classify_rate_stage(indicators),
        "econ_stage": classify_econ_stage(indicators),
        "indicators": indicators,
        "source": data["source"],
        "degraded": data["degraded"],
        "cache_status": data["cache_status"],
    }
    if "search_hints" in data:
        output["search_hints"] = data["search_hints"]

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    """`calibrate` 子命令：按宏观 stage 校准 PEG / 现金 / 单只上限。

    Args:
        args: 已解析命名空间，含 --stage/--from-data（二选一）、--peg、
            --current-cash、--single-stake、--stake-tier。

    Returns:
        int: 0 成功；1 输入非法或 --from-data 缓存不可用。
    """
    stage_source = "explicit"
    stage = args.stage

    if args.from_data:
        cached = _read_cache()
        if cached is None or "indicators" not in cached:
            print("❌ 未找到宏观数据缓存，无法 --from-data 带入 stage；"
                  "请先运行 data 子命令或显式指定 --stage")
            return 1
        inferred = classify_econ_stage(cached["indicators"])
        stage = inferred.get("stage")
        if stage not in STAGE_ENUM:
            print(f"❌ 缓存软判定 stage 不可用（{stage}），请显式指定 --stage")
            return 1
        stage_source = "soft_infer"

    try:
        result = calibrate(stage, args.peg, args.current_cash,
                           args.single_stake, args.stake_tier)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    if stage_source == "soft_infer":
        result["validation"]["stage_source"] = "soft_infer"
        result["validation"]["manual_review"] = True
        base_note = result["validation"]["note"]
        suffix = "stage 来自 P2-2 软判定（manual_review=true），建议人工确认后定稿"
        result["validation"]["note"] = f"{base_note}；{suffix}" if base_note else suffix

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    """CLI 入口。

    Returns:
        int: 0 成功，非 0 失败。
    """
    parser = argparse.ArgumentParser(
        description="宏观校准引擎（macro-calibrator）——GARP 框架宏观三表硬编码 + stage 查表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.replace("{py}", "python"),
    )
    sub = parser.add_subparsers(dest="command")

    st = sub.add_parser("stage", help="按美林四档输出完整宏观参数表")
    st.add_argument(
        "--stage",
        required=True,
        help=f"美林阶段，枚举：{' / '.join(STAGE_ENUM)}",
    )
    st.add_argument(
        "--markdown",
        action="store_true",
        help="在 JSON 之外追加打印人类可读 Markdown 表",
    )

    da = sub.add_parser("data", help="拉取宏观指标并输出利率/经济阶段软判定")
    da.add_argument(
        "--no-cache",
        action="store_true",
        help="跳过缓存有效期检查，强制从 akshare 刷新并覆写缓存",
    )

    ca = sub.add_parser("calibrate", help="按宏观 stage 校准 PEG / 现金 / 单只上限")
    src = ca.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--stage",
        help=f"美林阶段，枚举：{' / '.join(STAGE_ENUM)}（与 --from-data 二选一）",
    )
    src.add_argument(
        "--from-data",
        action="store_true",
        help="从 data 缓存软判定自动带入 stage（不触发网络刷新）",
    )
    ca.add_argument(
        "--peg",
        type=float,
        required=True,
        help="标的当前调整后 PEG（> 0）",
    )
    ca.add_argument(
        "--current-cash",
        type=float,
        required=True,
        help="当前现金占总资产百分比（0~100）",
    )
    ca.add_argument(
        "--single-stake",
        type=float,
        required=True,
        help="当前标的占总资产百分比（0~100）",
    )
    ca.add_argument(
        "--stake-tier",
        default="verified",
        choices=STAKE_TIER_ENUM,
        help=f"单只上限档位（默认 verified）：{' / '.join(STAKE_TIER_ENUM)}",
    )

    args = parser.parse_args()

    if args.command == "stage":
        return cmd_stage(args)
    if args.command == "data":
        return cmd_data(args)
    if args.command == "calibrate":
        return cmd_calibrate(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())