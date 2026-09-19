#!/usr/bin/env python3
"""政策-资本-地缘三维交叉矩阵 + 国产化率四梯队（geo_policy_screen）判定工具。

本工具将《中长期价值成长（GARP）投资框架》的两处口径下沉为可执行命令，禁止 LLM 心算：

1. 第 0 步·0.3「政策-资本-地缘三维交叉矩阵」六行判定与「赛道两分法」（子命令 ``screen``）。
2. 第 1 步「国产化率位置」四档分层量化（子命令 ``localize``）与半导体设备内置示例
   复现（子命令 ``examples``）。

- ``screen`` 输入：三维档位（地缘倒逼强度 / 政策覆盖度 / 国字号基金介入）。
- ``screen`` 输出：JSON，核心字段 ``row_index / matrix_row / conclusion / track_type``，
  附 ``archived / archive_from / time_sensitive / input`` 回显与口径来源标注。
- ``localize`` 输入：``--industry``（任意行业/领域/环节名，纯透传）+
  ``--localization-rate``（百分数 0~100）+ 可选 ``--strategic-choke-point`` +
  ``--as-of``/``--basis``。判定只依赖数值，不依赖行业名，天然支持任意行业。
- ``localize`` 输出：JSON，核心字段 ``tier / tier_index / phase / action_hint``。
- ``examples`` 输出：框架第 1 步内置的半导体设备三梯队 + 光刻表（回归锚点）。
- ``scan`` 检索框架第 0 步 0.1（地缘政治风险）+ 0.2（政策与国字号基金）的实时来源快照：
  * 输入 ``--industry``（地缘风险维度检索对象）与 ``--fund``（政策基金维度检索对象），
    二者至少填一个、可同时填；
  * 输出强制含 ``data_as_of``（数据截止日期）、``retrieved_at``（检索执行时间）、
    ``snapshot_example``（来源快照示例）与 ``degraded``（降级标注）；
  * ``scan`` 只检索、只呈现来源快照，**不判定风险等级/基金力度、不输出 screen 档位结论**。
- 关键边界：
  * 矩阵规则表与国产化率四档均为静态标签（框架明示长期适用）；
  * 三维档位与国产化率的「取值」是时变项，本工具**不检索、不判定取值真假、不固化数值**，
    仅透传调用方提供的 ``as_of``（判定时点）与 ``basis``（判定依据）；
  * 实时核验由本文件 ``scan`` 子命令承接（P3-3，只检索来源快照，不判档）。
- 未列组合处理：凡未显式列入六行的合法档位组合，一律按 ``FALLBACK_MAP`` 归档到
  「更审慎相邻档」，``archived=true``，不默认放行。

用法（示例）:
    python tools/specialized/geo_policy_screen.py screen \
        --geo 高 --policy 高 --fund 有直接注资 \
        --as-of 2026-09-15 --basis "P3-3 scan 检索结果 + 政策/基金公告"

    python tools/specialized/geo_policy_screen.py localize \
        --industry 量测检测 --localization-rate 12.5 --as-of 2026-09-15

    python tools/specialized/geo_policy_screen.py examples

    python tools/specialized/geo_policy_screen.py scan --industry 半导体

    python tools/specialized/geo_policy_screen.py scan --fund 半导体设备
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# 注入项目根目录到 sys.path，使 `from tools.common.anysearch import ...`
# 等延迟导入在 CLI 直接运行时（python tools/specialized/geo_policy_screen.py scan ...）可用
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# 三维档位词表（唯一合法取值范围）
# ---------------------------------------------------------------------------

#: 地缘倒逼强度合法档位（高/中/低）。
GEO_VALUES: Tuple[str, ...] = ("高", "中", "低")

#: 政策覆盖度合法档位（高/中/低）。
POLICY_VALUES: Tuple[str, ...] = ("高", "中", "低")

#: 国字号基金介入合法档位（四档，自"有直接注资"递减至"无覆盖"）。
FUND_VALUES: Tuple[str, ...] = ("有直接注资", "有专项子基金", "有覆盖", "无覆盖")

# ---------------------------------------------------------------------------
# 六行权威元数据（唯一权威 = 框架第 0 步·0.3，逐字照录）
# ---------------------------------------------------------------------------

#: 六行中文场景名与投资含义、赛道归属。
ROW_META: Dict[int, Dict[str, str]] = {
    1: {
        "matrix_row": "最优场景",
        "conclusion": "替代确定性和节奏均被外部力量锁定",
        "track_type": "地缘倒逼型",
    },
    2: {
        "matrix_row": "次优场景",
        "conclusion": "替代方向明确，但节奏受技术突破制约",
        "track_type": "地缘倒逼型",
    },
    3: {
        "matrix_row": "潜伏场景",
        "conclusion": "制裁尚未落地但概率高，提前布局等待催化",
        "track_type": "地缘倒逼型",
    },
    4: {
        "matrix_row": "高风险/回避",
        "conclusion": "下游被迫替代但国产短期接不住，须先验证承接能力，承接不足则回避",
        "track_type": "地缘倒逼型",
    },
    5: {
        "matrix_row": "政策驱动型增量创造",
        "conclusion": "不以地缘倒逼为门槛，达标与否以政策覆盖+基金介入（支柱五）为准",
        "track_type": "政策资本驱动型",
    },
    6: {
        "matrix_row": "回避",
        "conclusion": "替代节奏完全依赖市场驱动，不确定性过高",
        "track_type": "回避",
    },
}

#: 11 条显式命中：三维组合 -> 行号（严格照录框架六行）。
#: 行 4 政策「低/无」在词表内合并为「低」；行 5 政策「中/高」× 基金「有覆盖/有专项子基金/有直接注资」三档。
MATRIX_ROWS: Dict[Tuple[str, str, str], int] = {
    # 行 1：高 / 高 / 有直接注资
    ("高", "高", "有直接注资"): 1,
    # 行 2：高 / 中 / 有专项子基金
    ("高", "中", "有专项子基金"): 2,
    # 行 3：中 / 高 / 有覆盖
    ("中", "高", "有覆盖"): 3,
    # 行 4：高 / 低 / 无覆盖
    ("高", "低", "无覆盖"): 4,
    # 行 5：低 / (中|高) / (有覆盖|有专项子基金|有直接注资)，共 6 条
    ("低", "中", "有覆盖"): 5,
    ("低", "中", "有专项子基金"): 5,
    ("低", "中", "有直接注资"): 5,
    ("低", "高", "有覆盖"): 5,
    ("低", "高", "有专项子基金"): 5,
    ("低", "高", "有直接注资"): 5,
    # 行 6：低 / 低 / 无覆盖
    ("低", "低", "无覆盖"): 6,
}

#: 25 条未列组合归档映射：三维组合 -> (归档行号, 归档说明)。
#: 归档遵循「不变或降级 + 审慎优先 + 显式映射」三原则，全部纳入单元测试。
FALLBACK_MAP: Dict[Tuple[str, str, str], Tuple[int, str]] = {
    # ---- 地缘倒逼「高」的未列中间组合 ----
    ("高", "高", "有专项子基金"): (2, "基金为专项子基金（低于行1直接注资），政策覆盖自高降为中，落次优场景"),
    ("高", "高", "有覆盖"): (3, "地缘倒逼自高降为中，政策高+基金有覆盖保持不变，落潜伏场景"),
    ("高", "高", "无覆盖"): (4, "政策覆盖自高降为低，基金无覆盖，落高风险/回避"),
    ("高", "中", "有直接注资"): (2, "基金自直接注资降为专项子基金，地缘高+政策中保持不变，落次优场景"),
    ("高", "中", "有覆盖"): (4, "政策自中降为低、基金自覆盖降为无覆盖，落高风险/回避（审慎优先于政策资本驱动型）"),
    ("高", "中", "无覆盖"): (4, "政策自中降为低，基金无覆盖保持不变，落高风险/回避"),
    ("高", "低", "有直接注资"): (4, "基金自直接注资降为无覆盖，地缘高+政策低保持不变，落高风险/回避"),
    ("高", "低", "有专项子基金"): (4, "基金自专项子基金降为无覆盖，地缘高+政策低保持不变，落高风险/回避"),
    ("高", "低", "有覆盖"): (4, "框架点名：政策覆盖低但国字号基金有覆盖→更审慎相邻档为高风险/回避，基金自覆盖降为无覆盖"),
    # ---- 地缘倒逼「中」的未列中间组合 ----
    ("中", "高", "有直接注资"): (5, "地缘尚未落地（中）时保守降为低，政策高+基金直接注资，落政策资本驱动型"),
    ("中", "高", "有专项子基金"): (3, "基金自专项子基金降为有覆盖，地缘中+政策高；非低倒逼保持地缘倒逼型，按更审慎的潜伏场景"),
    ("中", "高", "无覆盖"): (6, "地缘自中降为低、政策自高降为低，基金无覆盖，落回避"),
    ("中", "中", "有直接注资"): (5, "地缘自中降为低，政策中+基金直接注资，落政策资本驱动型"),
    ("中", "中", "有专项子基金"): (5, "地缘自中降为低，政策中+基金专项子基金，落政策资本驱动型"),
    ("中", "中", "有覆盖"): (5, "地缘自中降为低，政策中+基金覆盖，落政策资本驱动型"),
    ("中", "中", "无覆盖"): (6, "地缘自中降为低、政策自中降为低，基金无覆盖，落回避"),
    ("中", "低", "有直接注资"): (6, "地缘自中降为低、基金自直接注资降为无覆盖，政策低，落回避"),
    ("中", "低", "有专项子基金"): (6, "地缘自中降为低、基金自专项子基金降为无覆盖，政策低，落回避"),
    ("中", "低", "有覆盖"): (6, "地缘自中降为低、基金自覆盖降为无覆盖，政策低，落回避"),
    ("中", "低", "无覆盖"): (6, "地缘自中降为低，政策低+基金无覆盖，落回避"),
    # ---- 地缘倒逼「低」的未列中间组合 ----
    ("低", "高", "无覆盖"): (6, "政策自高降为低，基金无覆盖，落回避"),
    ("低", "中", "无覆盖"): (6, "政策自中降为低，基金无覆盖，落回避"),
    ("低", "低", "有直接注资"): (6, "基金自直接注资降为无覆盖，政策低+地缘低，落回避"),
    ("低", "低", "有专项子基金"): (6, "基金自专项子基金降为无覆盖，政策低+地缘低，落回避"),
    ("低", "低", "有覆盖"): (6, "基金自覆盖降为无覆盖，政策低+地缘低，落回避"),
}

#: 关键风险提示（框架 0.3 原文，恒定写入结论旁注）。
RISK_NOTE: str = "国字号基金注资是政策优先序列信号，非买入估值依据；最终决策回到估值与业绩兑现框架"

#: 口径来源（可追溯）。
SOURCE: str = "框架第0步·0.3"

#: 档位时效警示（恒定，档位为时变输入）。
TIME_SENSITIVITY_NOTE: str = "档位为时变输入，结论仅对档位判定时点有效，须以最新数据复核"

# ---------------------------------------------------------------------------
# 国产化率四档（唯一权威 = 框架第 1 步，逐字照录）
# ---------------------------------------------------------------------------

#: 浮点容差，用于消除国产化率经计算传入时的边界浮点误差。
LOCALIZATION_EPS: float = 1e-9

#: 国产化率四档规则表：tier_index -> 档名/阶段/动作/边界（左闭右开，第 4 档含 100）。
#: 边界依据框架第 1 步四档口径 + 半导体设备示例反推（详见 P3-2 开发方案 §2.2）。
LOCALIZATION_TIERS: Dict[int, Dict[str, Any]] = {
    1: {
        "tier": "过早",
        "phase": "不确定性高",
        "action_hint": "观察不建仓",
        "lower": 0.0,
        "upper": 5.0,
    },
    2: {
        "tier": "突破期",
        "phase": "从0到1突破期",
        "action_hint": "高弹性，跟踪/小仓",
        "lower": 5.0,
        "upper": 20.0,
    },
    3: {
        "tier": "加速投资期",
        "phase": "加速投资期",
        "action_hint": "订单放量",
        "lower": 20.0,
        "upper": 50.0,
    },
    4: {
        "tier": "替代空间收窄",
        "phase": "替代空间收窄",
        "action_hint": "转向龙头份额提升与整机放量，不继续押注「从0到1」",
        "lower": 50.0,
        "upper": 100.0,
    },
}

#: 战略卡脖子环节例外动作提示（仅 rate<5 且命中 --strategic-choke-point 时覆盖）。
CHOKE_POINT_ACTION_HINT: str = "战略必争卡脖子环节，高风险高弹性，仅观察/小仓、不重仓（非回避）"

#: 国产化率口径来源（可追溯）。
LOCALIZATION_SOURCE: str = "框架第1步"

#: 国产化率时效警示（恒定，国产化率为时变输入）。
LOCALIZATION_TIME_NOTE: str = "国产化率为时变数据，结论仅对判定时点有效，须以最新数据复核"

#: 国产化率四档边界序列（lower, upper），用于导入时校验常量无手写错位。
LOCALIZATION_BOUNDS: Tuple[Tuple[float, float], ...] = (
    (0.0, 5.0),
    (5.0, 20.0),
    (20.0, 50.0),
    (50.0, 100.0),
)


def _assert_localization_boundaries() -> None:
    """校验国产化率四档边界恰好覆盖 [0, 100] 且无重叠、无缺口。

    防御常量手写笔误，确保运行时任意 0~100 数值均能确定落档，
    且边界归属与 P3-2 开发方案 §2.2（<5 / [5,20) / [20,50) / [50,100]）一致。

    Raises:
        AssertionError: 四档边界存在重叠、缺口或非顺序排列时抛出。
    """
    assert set(LOCALIZATION_TIERS) == {1, 2, 3, 4}, "国产化率档位须为 1~4"

    tiers = [LOCALIZATION_TIERS[i] for i in range(1, 5)]
    boundaries = [(
        float(tier["lower"]),
        float(tier["upper"]),
    ) for tier in tiers]
    assert boundaries == list(LOCALIZATION_BOUNDS), (
        f"国产化率四档边界与 LOCALIZATION_BOUNDS 不一致：{boundaries}")

    # 相邻档边界须首尾相接：前档上界 == 后档下界。
    for prev, curr in zip(boundaries, boundaries[1:]):
        assert abs(prev[1] - curr[0]) < LOCALIZATION_EPS, (
            f"国产化率边界存在缺口或重叠：{prev} -> {curr}")

    tier_names = {tier["tier"] for tier in tiers}
    assert len(tier_names) == 4, "国产化率四档名须唯一"


#: 导入时即执行国产化率四档边界自检，确保规则表完整、连续。
_assert_localization_boundaries()


def _assert_full_coverage() -> None:
    """校验 3×3×4 共 36 组合恰好被显式命中与归档映射全覆盖，无重复、无遗漏。

    该断言在模块导入时执行，用于防御常量手写笔误（如漏写或串写组合），
    确保运行时不会出现「合法档位但查不到结论」的灰色地带。

    Raises:
        AssertionError: 存在重复映射或未覆盖组合时抛出。
    """
    all_combos = set(product(GEO_VALUES, POLICY_VALUES, FUND_VALUES))
    exact = set(MATRIX_ROWS.keys())
    fallback = set(FALLBACK_MAP.keys())

    overlap = exact & fallback
    assert not overlap, f"MATRIX_ROWS 与 FALLBACK_MAP 存在重复映射：{overlap}"

    uncovered = all_combos - exact - fallback
    assert not uncovered, f"存在未覆盖的合法档位组合：{uncovered}"

    expected_total = len(GEO_VALUES) * len(POLICY_VALUES) * len(FUND_VALUES)
    assert len(exact) + len(fallback) == expected_total, (
        f"映射条数不符：显式 {len(exact)} + 归档 {len(fallback)} != {expected_total}")


#: 导入时即执行全覆盖自检，确保映射表完整、无冲突。
_assert_full_coverage()


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class GeoPolicyResult:
    """三维交叉矩阵判定结果（字段对齐开发方案 §3.3）。"""

    row_index: int
    matrix_row: str
    conclusion: str
    track_type: str
    archived: bool
    archive_from: Optional[str]
    time_sensitive: bool
    time_sensitivity_note: str
    risk_note: str
    source: str
    input: Dict[str, Optional[str]]


@dataclass
class LocalizationResult:
    """国产化率四档判定结果（字段对齐 P3-2 开发方案 §3.3）。"""

    industry: str
    localization_rate_pct: float
    tier: str
    tier_index: int
    phase: str
    action_hint: str
    strategic_choke_point: bool
    choke_point_applied: bool
    time_sensitive: bool
    time_sensitivity_note: str
    source: str
    input: Dict[str, Any]


@dataclass
class CohortExample:
    """半导体设备内置梯队示例条目（字段对齐 P3-2 开发方案 §3.4）。"""

    cohort: str
    segments: List[str]
    rate_range: str
    tier: str
    logic: str
    choke_point: bool = False


# ---------------------------------------------------------------------------
# 核心判定
# ---------------------------------------------------------------------------

def _validate(geo: str, policy: str, fund: str) -> None:
    """校验三维档位是否在合法词表内，非法即抛 ValueError（fail-fast，不归档）。

    Args:
        geo: 地缘倒逼强度档位。
        policy: 政策覆盖度档位。
        fund: 国字号基金介入档位。

    Raises:
        ValueError: 任一档位不在合法词表内时抛出，并给出可选值提示。
    """
    if geo not in GEO_VALUES:
        raise ValueError(f"非法地缘倒逼强度档位「{geo}」，可选 {list(GEO_VALUES)}")
    if policy not in POLICY_VALUES:
        raise ValueError(f"非法政策覆盖度档位「{policy}」，可选 {list(POLICY_VALUES)}")
    if fund not in FUND_VALUES:
        raise ValueError(f"非法国字号基金介入档位「{fund}」，可选 {list(FUND_VALUES)}")


def screen(geo: str, policy: str, fund: str,
           as_of: Optional[str] = None, basis: Optional[str] = None) -> GeoPolicyResult:
    """对单个三维档位组合执行矩阵判定与赛道两分法分发。

    判定顺序：
    1. 校验档位合法性（非法直接抛 ValueError，不归档）。
    2. 命中 ``MATRIX_ROWS`` → ``archived=false``，直接取对应行结论。
    3. 否则命中 ``FALLBACK_MAP`` → ``archived=true``，按「更审慎相邻档」归档，
       ``archive_from`` 回显原三维组合。

    Args:
        geo: 地缘倒逼强度（高/中/低）。
        policy: 政策覆盖度（高/中/低）。
        fund: 国字号基金介入（有直接注资/有专项子基金/有覆盖/无覆盖）。
        as_of: 档位判定的数据截止日期（可选，仅透传，不参与判定）。
        basis: 档位判定的依据/来源（可选，仅透传，不参与判定）。

    Returns:
        GeoPolicyResult: 完整判定结果，含赛道两分法 ``track_type`` 与时效警示。

    Raises:
        ValueError: 档位值非法时抛出。
    """
    _validate(geo, policy, fund)

    combo = (geo, policy, fund)
    input_payload = {"geo": geo, "policy": policy, "fund": fund,
                     "as_of": as_of, "basis": basis}

    # 显式命中：直接取行号，无归档。
    exact_row = MATRIX_ROWS.get(combo)
    if exact_row is not None:
        meta = ROW_META[exact_row]
        return GeoPolicyResult(
            row_index=exact_row,
            matrix_row=meta["matrix_row"],
            conclusion=meta["conclusion"],
            track_type=meta["track_type"],
            archived=False,
            archive_from=None,
            time_sensitive=True,
            time_sensitivity_note=TIME_SENSITIVITY_NOTE,
            risk_note=RISK_NOTE,
            source=SOURCE,
            input=input_payload,
        )

    # 未列组合：按更审慎相邻档归档（36 组合全覆盖保证此处必命中）。
    fallback_row, _archive_note = FALLBACK_MAP[combo]
    meta = ROW_META[fallback_row]
    return GeoPolicyResult(
        row_index=fallback_row,
        matrix_row=meta["matrix_row"],
        conclusion=meta["conclusion"],
        track_type=meta["track_type"],
        archived=True,
        archive_from=f"{geo}/{policy}/{fund}",
        time_sensitive=True,
        time_sensitivity_note=TIME_SENSITIVITY_NOTE,
        risk_note=RISK_NOTE,
        source=SOURCE,
        input=input_payload,
    )


# ---------------------------------------------------------------------------
# 国产化率四档核心判定
# ---------------------------------------------------------------------------

#: 半导体设备四梯队内置示例（唯一权威 = 框架第 1 步 §2.5，逐字段照录）。
SEMICONDUCTOR_COHORTS: List[CohortExample] = [
    CohortExample(
        cohort="第一梯队（已成熟）",
        segments=["去胶", "清洗", "刻蚀"],
        rate_range="50%~90%",
        tier="替代空间收窄",
        logic="替代空间收窄，关注龙头份额提升",
    ),
    CohortExample(
        cohort="第二梯队（主力增量）",
        segments=["薄膜沉积", "CMP"],
        rate_range="30%~40%",
        tier="加速投资期",
        logic="已跨过验证门槛，订单放量阶段",
    ),
    CohortExample(
        cohort="第三梯队（高弹性）",
        segments=["涂胶显影", "离子注入", "量测检测"],
        rate_range="5%~20%",
        tier="突破期",
        logic="从\"0到1\"突破带来最大业绩弹性",
    ),
    CohortExample(
        cohort="光刻（战略卡脖子）",
        segments=["光刻设备"],
        rate_range="<1%",
        tier="过早",
        logic="属\"<5%过早\"区间，但为最深卡脖子、政策最强押注环节，仅观察/小仓、不重仓",
        choke_point=True,
    ),
]


def _classify(rate: float) -> Tuple[int, str, str, str]:
    """按国产化率数值精确落档，返回 (tier_index, tier, phase, action_hint)。

    边界归属与 P3-2 开发方案 §2.2 一致：
    ``rate < 5`` 过早、``5 <= rate < 20`` 突破期、
    ``20 <= rate < 50`` 加速投资期、``rate >= 50`` 替代空间收窄。

    Args:
        rate: 国产化率百分数（0~100）。

    Returns:
        Tuple[int, str, str, str]: 档位号、档名、阶段、动作提示。
    """
    if rate < 5.0 - LOCALIZATION_EPS:
        tier_index = 1
    elif rate < 20.0 - LOCALIZATION_EPS:
        tier_index = 2
    elif rate < 50.0 - LOCALIZATION_EPS:
        tier_index = 3
    else:
        tier_index = 4

    meta = LOCALIZATION_TIERS[tier_index]
    return tier_index, meta["tier"], meta["phase"], meta["action_hint"]


def localize(industry: str, localization_rate: float,
             strategic_choke_point: bool = False,
             as_of: Optional[str] = None, basis: Optional[str] = None) -> LocalizationResult:
    """对任意行业/领域的国产化率执行四档分层判定。

    判定只依赖 ``localization_rate`` 数值，不依赖行业名，天然支持「任意行业/领域」。
    战略卡脖子例外仅在 ``rate < 5`` 且 ``strategic_choke_point=True`` 时生效。

    Args:
        industry: 行业/领域/环节名（任意非空文本，纯透传）。
        localization_rate: 国产化率百分数（0~100，可为 int/float）。
        strategic_choke_point: 是否属战略必争卡脖子环节（可选，默认 False）。
        as_of: 国产化率数据截止日期（可选，仅透传，不参与判定）。
        basis: 判定依据/来源（可选，仅透传，不参与判定）。

    Returns:
        LocalizationResult: 完整四档判定结果。

    Raises:
        ValueError: industry 为空，或 localization_rate 非法（非数值或超出 0~100）时。
    """
    if industry is None or not str(industry).strip():
        raise ValueError("行业/领域/环节名不能为空")
    industry = str(industry).strip()

    if isinstance(localization_rate, bool):
        raise ValueError("国产化率须为数值，不能为布尔值")
    try:
        rate = float(localization_rate)
    except (TypeError, ValueError) as exc:
        raise ValueError("国产化率须为 0~100 的数值") from exc

    if rate < 0.0 or rate > 100.0:
        raise ValueError("国产化率须在 0~100 之间")

    tier_index, tier, phase, action_hint = _classify(rate)

    choke_point_applied = False
    if strategic_choke_point and tier_index == 1:
        action_hint = CHOKE_POINT_ACTION_HINT
        choke_point_applied = True

    input_payload = {
        "industry": industry,
        "localization_rate_pct": rate,
        "strategic_choke_point": bool(strategic_choke_point),
        "as_of": as_of,
        "basis": basis,
    }

    return LocalizationResult(
        industry=industry,
        localization_rate_pct=rate,
        tier=tier,
        tier_index=tier_index,
        phase=phase,
        action_hint=action_hint,
        strategic_choke_point=bool(strategic_choke_point),
        choke_point_applied=choke_point_applied,
        time_sensitive=True,
        time_sensitivity_note=LOCALIZATION_TIME_NOTE,
        source=LOCALIZATION_SOURCE,
        input=input_payload,
    )


def build_examples() -> Dict[str, Any]:
    """构建内置半导体设备四梯队示例输出（回归锚点）。

    Returns:
        Dict[str, Any]: 含 source/industry_example/note/cohorts 的示例结构。
    """
    return {
        "source": LOCALIZATION_SOURCE,
        "industry_example": "半导体设备",
        "note": "半导体设备仅作内置示例，本工具判定逻辑不写死半导体；"
                "任意行业通过 localize 子命令按国产化率数值落档。",
        "cohorts": [asdict(c) for c in SEMICONDUCTOR_COHORTS],
    }


# ---------------------------------------------------------------------------
# scan 检索：框架第 0 步·0.1 地缘风险 + 0.2 政策基金 来源快照（P3-3，不判档）
# ---------------------------------------------------------------------------

#: 项目根目录（本文件位于 tools/specialized/，向上三级回到工作区根目录）。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

#: scan 缓存目录（仅实时检索全失败时回退读取）。
SCAN_CACHE_DIR = _PROJECT_ROOT / "data" / "geo_policy"

#: scan 缓存 TTL（小时），超出视为无缓存。
SCAN_CACHE_TTL_HOURS = 24

#: akshare 结构化源探测结论（当前版本未发现稳定结构化接口，不硬编假接口）。
STRUCTURED_SOURCE_NOTE = (
    "akshare 未发现制裁清单/出口管制/政策基金注资额度的直接结构化接口"
)

#: 「不写硬结论」免责声明（恒定写入每份 scan 输出）。
SCAN_DISCLAIMER = (
    "本输出仅为实时检索结果与来源快照，不构成对该行业风险等级或基金力度的判定结论；"
    "最终判断须以最新实时检索与独立研判为准。"
)

#: 操作纪律提示（恒定，指出框架示例非当前事实）。
SCAN_NOTE = (
    "框架第0步·0.1 风险行业表与 0.2 基金名单仅为示例/格式示范，本输出不将其固化为当前事实。"
)

#: 地缘风险检索关键词模板（框架启发，非结论）。
_GEO_QUERY_TEMPLATES: Tuple[str, ...] = (
    "{industry} 实体清单 出口管制",
    "{industry} 制裁 管制清单",
    "{industry} 风险行业 逆全球化",
)

#: 政策基金检索关键词模板（框架启发，非结论）。
_FUND_QUERY_TEMPLATES: Tuple[str, ...] = (
    "{industry_or_fund} 国家产业基金 注资 规模",
    "{industry_or_fund} 大基金 专项子基金 投资额",
)

#: 维度中文标签（输出字段 label 的恒定取值）。
_DIMENSION_LABELS: Dict[str, str] = {
    "geopolitical_risk": "地缘政治风险",
    "policy_fund": "政策与国字号基金",
}


def _probe_structured_sources() -> Dict[str, Any]:
    """探测 akshare 是否有制裁清单/出口管制/政策基金注资额度的结构化接口。

    当前仓库盘点结论：akshare 未提供对应的直接结构化接口，因此返回
    ``available=False``，``scan`` 据此直接走搜索工具实时检索，不硬编假接口。
    未来若 akshare 新增对应接口，仅需在此函数内扩展探测逻辑。

    Returns:
        Dict[str, Any]: ``probed``/``available``/``note`` 三项探测结论。
    """
    return {
        "probed": True,
        "available": False,
        "note": STRUCTURED_SOURCE_NOTE,
    }


def _geo_query_terms(value: str) -> List[str]:
    """生成地缘风险维度的检索关键词列表。

    Args:
        value: 行业/领域名（非空）。

    Returns:
        List[str]: 依模板填充后的检索关键词。
    """
    return [tpl.format(industry=value) for tpl in _GEO_QUERY_TEMPLATES]


def _fund_query_terms(value: str) -> List[str]:
    """生成政策基金维度的检索关键词列表。

    Args:
        value: 行业/领域/基金名（非空）。

    Returns:
        List[str]: 依模板填充后的检索关键词。
    """
    return [tpl.format(industry_or_fund=value) for tpl in _FUND_QUERY_TEMPLATES]


def _normalize_source(
    raw: Dict[str, Any], source_tool: str
) -> Dict[str, Optional[str]]:
    """将任一搜索工具返回的单条结果归一化为统一六字段来源。

    归一化规则（§3.4）：``title``/``url`` 缺省为空串；``snippet`` 优先取
    ``snippet``，回退 ``summary``，再回退 ``content`` 截断；``published_at``
    从 ``publish_time``（doubao）或 ``published_date``（exa）取值，缺失为 None。

    Args:
        raw: 搜索工具返回的单条原始结果字典。
        source_tool: 来源工具名（anysearch/doubao_search/exa_search/cache）。

    Returns:
        Dict[str, Optional[str]]: 归一化后的六字段来源。
    """
    title = str(raw.get("title") or "").strip()
    url = str(raw.get("url") or "").strip()

    snippet = raw.get("snippet") or raw.get("summary") or raw.get("content") or ""
    if not isinstance(snippet, str):
        snippet = str(snippet)
    snippet = snippet.strip()
    if len(snippet) > 500:
        snippet = snippet[:500] + "..."

    published_at = raw.get("publish_time") or raw.get("published_date")
    published_at = str(published_at) if published_at is not None else None

    return {
        "title": title,
        "url": url,
        "snippet": snippet,
        "published_at": published_at,
        "source_tool": source_tool,
    }


def _call_queries(
    fn: Optional[Callable[[str], List[Dict[str, Any]]]],
    query_terms: List[str],
    source_tool: str,
) -> List[Dict[str, Optional[str]]]:
    """按关键词列表调用单个搜索工具并归一化、去重。

    Args:
        fn: 搜索工具可调用对象（接收关键词，返回原始结果列表），可为 None。
        query_terms: 检索关键词列表。
        source_tool: 来源工具名。

    Returns:
        List[Dict[str, Optional[str]]]: 归一化、去重后的来源列表。
    """
    if fn is None:
        return []

    sources: List[Dict[str, Optional[str]]] = []
    seen: set = set()
    for term in query_terms:
        try:
            raw_results = fn(term) or []
        except Exception:
            # 单工具/单关键词异常视为该次检索无结果，交由上层降级。
            continue
        if not isinstance(raw_results, (list, tuple)):
            continue
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            source = _normalize_source(raw, source_tool)
            key = source["url"] or source["title"]
            if not key or key in seen:
                continue
            seen.add(key)
            sources.append(source)
    return sources


def _build_default_search_inject() -> Dict[str, Optional[Callable[[str], List[Dict[str, Any]]]]]:
    """构建真实搜索工具注入映射（延迟导入，避免模块顶层依赖影响既有命令）。

    exa_search 为第三级可选回退，若导入失败则置 None（调用层跳过）。

    Returns:
        Dict[str, Optional[Callable[[str], List[Dict[str, Any]]]]]:
        工具名到可调用对象的映射。
    """
    from tools.common.anysearch import anysearch
    from tools.common.doubao_search import doubao_search

    inject: Dict[str, Optional[Callable[[str], List[Dict[str, Any]]]]] = {
        "anysearch": anysearch,
        "doubao_search": doubao_search,
        "exa_search": None,
    }
    try:
        from tools.common.exa_search import exa_search
        inject["exa_search"] = exa_search
    except Exception:
        inject["exa_search"] = None
    return inject


def _run_search(
    query_terms: List[str],
    dimension: str,
    search_inject: Dict[str, Optional[Callable[[str], List[Dict[str, Any]]]]],
) -> Dict[str, Any]:
    """按工具链顺序编排实时检索：anysearch → doubao → exa（仅地缘维度）。

    Args:
        query_terms: 检索关键词列表。
        dimension: 维度标识（geopolitical_risk / policy_fund）。
        search_inject: 搜索工具注入映射。

    Returns:
        Dict[str, Any]: 含 sources/retrieval_status/degraded/degraded_reason
        的实时检索结果。
    """
    primary = search_inject.get("anysearch")
    sources = _call_queries(primary, query_terms, "anysearch")
    if sources:
        return {
            "sources": sources,
            "retrieval_status": "ok",
            "degraded": False,
            "degraded_reason": None,
        }

    fallback = search_inject.get("doubao_search")
    sources = _call_queries(fallback, query_terms, "doubao_search")
    if sources:
        return {
            "sources": sources,
            "retrieval_status": "partial",
            "degraded": True,
            "degraded_reason": "首选工具 anysearch 失败/空，已回退 doubao_search",
        }

    # exa_search 仅在地缘风险维度作第三级可选回退。
    if dimension == "geopolitical_risk":
        sources = _call_queries(search_inject.get("exa_search"),
                                query_terms, "exa_search")
        if sources:
            return {
                "sources": sources,
                "retrieval_status": "partial",
                "degraded": True,
                "degraded_reason": "首选工具 anysearch 失败/空，已回退 exa_search",
            }

    return {
        "sources": [],
        "retrieval_status": "failed",
        "degraded": True,
        "degraded_reason": "实时检索工具全部失败/空",
    }


def _cache_file_path(dimension: str, query_terms: List[str]) -> Path:
    """生成缓存文件路径（scan_{dimension}_{安全hash}.json）。

    安全 hash 取检索关键词串接后的 SHA-256 前 16 位十六进制。

    Args:
        dimension: 维度标识。
        query_terms: 检索关键词列表。

    Returns:
        Path: 缓存文件路径。
    """
    basis = "|".join(query_terms)
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return SCAN_CACHE_DIR / f"scan_{dimension}_{digest}.json"


def _write_cache(
    dimension: str,
    query_terms: List[str],
    sources: List[Dict[str, Optional[str]]],
    now: datetime,
) -> None:
    """将实时检索结果写入缓存，供未来实时全失败时兜底。

    缓存写入失败（如目录无权限）静默忽略，不影响实时检索主流程。

    Args:
        dimension: 维度标识。
        query_terms: 检索关键词列表。
        sources: 归一化来源列表。
        now: 检索执行时间。
    """
    try:
        SCAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "dimension": dimension,
            "cached_at": now.isoformat(timespec="seconds"),
            "sources": sources,
        }
        _cache_file_path(dimension, query_terms).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def _read_cache(
    dimension: str,
    query_terms: List[str],
    now: datetime,
) -> Optional[Dict[str, Any]]:
    """读取未过期的旧缓存兜底，来源强制标记 source_tool=cache。

    Args:
        dimension: 维度标识。
        query_terms: 检索关键词列表。
        now: 当前时间（用于 TTL 校验）。

    Returns:
        Optional[Dict[str, Any]]: 命中则返回 {cached_at, sources}，否则 None。
    """
    try:
        payload = json.loads(
            _cache_file_path(dimension, query_terms).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not sources:
        return None

    cached_at = payload.get("cached_at")
    try:
        cached_dt = datetime.fromisoformat(cached_at)
    except (TypeError, ValueError):
        return None
    if now - cached_dt > timedelta(hours=SCAN_CACHE_TTL_HOURS):
        return None

    for source in sources:
        source["source_tool"] = "cache"
    return {"cached_at": cached_at, "sources": sources}


def _clean_input(value: Any) -> Optional[str]:
    """校验并清洗单个检索输入（strip 后须非空）。

    Args:
        value: 待校验的输入（None 视为未提供）。

    Returns:
        Optional[str]: 清洗后的非空文本；输入为 None 时返回 None。

    Raises:
        ValueError: 输入为非字符串或 strip 后为空/纯空白时。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("检索输入须为字符串")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("检索输入不能为空或纯空白")
    return cleaned


def _dimension_output(
    dimension: str,
    input_value: str,
    query_terms: List[str],
    retrieval_status: str,
    sources: List[Dict[str, Optional[str]]],
) -> Dict[str, Any]:
    """组装单个维度输出对象（对齐 §3.3 维度结构，不含内部降级字段）。

    Args:
        dimension: 维度标识。
        input_value: 该维度检索对象。
        query_terms: 检索关键词列表。
        retrieval_status: 检索状态（ok/partial/failed）。
        sources: 归一化来源列表。

    Returns:
        Dict[str, Any]: 维度输出对象。
    """
    return {
        "dimension": dimension,
        "label": _DIMENSION_LABELS[dimension],
        "input_value": input_value,
        "query_terms": query_terms,
        "retrieval_status": retrieval_status,
        "source_count": len(sources),
        "sources": sources,
    }


def _snapshot_entries(
    dimension: str,
    sources: List[Dict[str, Optional[str]]],
) -> List[Dict[str, Optional[str]]]:
    """从维度来源抽取至多 2 条示例快照，并附加维度标识。

    Args:
        dimension: 维度标识。
        sources: 归一化来源列表。

    Returns:
        List[Dict[str, Optional[str]]]: snapshot_example 条目（每维度至多 2 条）。
    """
    entries: List[Dict[str, Optional[str]]] = []
    for source in sources[:2]:
        entry: Dict[str, Optional[str]] = {"dimension": dimension}
        entry.update(source)
        entries.append(entry)
    return entries


def _search_dimension(
    dimension: str,
    input_value: str,
    query_terms: List[str],
    search_inject: Dict[str, Optional[Callable[[str], List[Dict[str, Any]]]]],
    now: datetime,
) -> Tuple[Dict[str, Any], bool, Optional[str]]:
    """对单个维度执行实时检索 + 缓存兜底，返回维度对象与降级标记。

    Args:
        dimension: 维度标识（geopolitical_risk / policy_fund）。
        input_value: 该维度检索对象（--industry 或 --fund 的值）。
        query_terms: 检索关键词列表。
        search_inject: 搜索工具注入映射。
        now: 检索执行时间。

    Returns:
        Tuple[Dict[str, Any], bool, Optional[str]]:
        维度输出对象、该维度是否降级、降级原因（未降级为 None）。
    """
    search = _run_search(query_terms, dimension, search_inject)
    sources = search["sources"]

    if search["retrieval_status"] != "failed":
        _write_cache(dimension, query_terms, sources, now)
        return (
            _dimension_output(dimension, input_value, query_terms,
                              search["retrieval_status"], sources),
            search["degraded"],
            search["degraded_reason"],
        )

    cached = _read_cache(dimension, query_terms, now)
    if cached is not None:
        reason = f"实时检索失败，回退旧缓存（cache_as_of={cached['cached_at']}）"
        return (
            _dimension_output(dimension, input_value, query_terms,
                              "ok", cached["sources"]),
            True,
            reason,
        )

    return (
        _dimension_output(dimension, input_value, query_terms, "failed", []),
        True,
        "实时检索与缓存均不可用",
    )


def scan(
    industry: Optional[str] = None,
    fund: Optional[str] = None,
    search_inject: Optional[Dict[str, Optional[Callable[[str], List[Dict[str, Any]]]]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """检索框架第 0 步 0.1 地缘风险 + 0.2 政策基金的实时来源快照（不判档）。

    本函数只检索、只呈现来源快照，不判定风险等级/基金力度，不输出
    ``screen`` 的三维档位结论，落实「不写硬结论」纪律。

    Args:
        industry: 地缘风险维度检索对象（行业/领域名），可选。
        fund: 政策基金维度检索对象（行业/领域/基金名），可选。
        search_inject: 搜索工具注入映射，便于测试离线 mock，缺省为真实工具。
        now: 检索执行时间，可注入以便测试，缺省为当前本地时间。

    Returns:
        Dict[str, Any]: §3.3 顶层输出对象（含 data_as_of/retrieved_at/
        snapshot_example/degraded 等强制字段）。

    Raises:
        ValueError: industry 与 fund 均未提供，或任一为非字符串/纯空白时。
    """
    industry = _clean_input(industry)
    fund = _clean_input(fund)
    if industry is None and fund is None:
        raise ValueError("--industry 与 --fund 至少填一个")

    now = now if now is not None else datetime.now()
    if search_inject is None:
        search_inject = _build_default_search_inject()

    structured_source = _probe_structured_sources()

    dimensions: List[Dict[str, Any]] = []
    snapshot_example: List[Dict[str, Optional[str]]] = []
    degraded_flags: List[bool] = []
    degraded_reasons: List[str] = []

    if industry is not None:
        geo_terms = _geo_query_terms(industry)
        dim, dg, dr = _search_dimension(
            "geopolitical_risk", industry, geo_terms, search_inject, now)
        dimensions.append(dim)
        degraded_flags.append(dg)
        if dr is not None:
            degraded_reasons.append(dr)
        snapshot_example.extend(
            _snapshot_entries("geopolitical_risk", dim["sources"]))

    if fund is not None:
        fund_terms = _fund_query_terms(fund)
        dim, dg, dr = _search_dimension(
            "policy_fund", fund, fund_terms, search_inject, now)
        dimensions.append(dim)
        degraded_flags.append(dg)
        if dr is not None:
            degraded_reasons.append(dr)
        snapshot_example.extend(
            _snapshot_entries("policy_fund", dim["sources"]))

    degraded = any(degraded_flags)
    degraded_reason = "；".join(degraded_reasons) if degraded else None

    return {
        "task": "scan",
        "query": {"industry": industry, "fund": fund},
        "data_as_of": now.date().isoformat(),
        "retrieved_at": now.isoformat(timespec="seconds"),
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "structured_source": structured_source,
        "disclaimer": SCAN_DISCLAIMER,
        "note": SCAN_NOTE,
        "dimensions": dimensions,
        "snapshot_example": snapshot_example,
    }


def cmd_scan(args: argparse.Namespace) -> int:
    """执行 ``scan`` 子命令：检索来源快照并打印 JSON，输入非法返回非零。

    Args:
        args: argparse 解析后的命名空间。

    Returns:
        int: 退出码（0 成功，1 输入非法）。
    """
    try:
        result = scan(args.industry, args.fund)
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    """执行 ``screen`` 子命令：单组合判定并打印 JSON，非法档位返回非零。

    Args:
        args: argparse 解析后的命名空间。

    Returns:
        int: 退出码（0 成功，1 非法档位）。
    """
    try:
        result = screen(args.geo, args.policy, args.fund, args.as_of, args.basis)
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def cmd_localize(args: argparse.Namespace) -> int:
    """执行 ``localize`` 子命令：单点国产化率四档判定并打印 JSON。

    Args:
        args: argparse 解析后的命名空间。

    Returns:
        int: 退出码（0 成功，1 输入非法）。
    """
    try:
        result = localize(
            args.industry,
            args.localization_rate,
            args.strategic_choke_point,
            args.as_of,
            args.basis,
        )
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def cmd_examples(_args: argparse.Namespace) -> int:
    """执行 ``examples`` 子命令：打印内置半导体设备四梯队示例 JSON。

    Args:
        _args: argparse 解析后的命名空间（本子命令无参数，不使用）。

    Returns:
        int: 退出码（0 成功）。
    """
    print(json.dumps(build_examples(), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="政策-资本-地缘三维交叉矩阵 + 国产化率四档判定工具"
                    "（框架第0步·0.3 与 第1步）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.replace("{py}", "python"),
    )
    sub = parser.add_subparsers(dest="command")

    sc = sub.add_parser("screen", help="单组合三维判定（输出 JSON）")
    sc.add_argument("--geo", required=True, help=f"地缘倒逼强度：{'/'.join(GEO_VALUES)}")
    sc.add_argument("--policy", required=True, help=f"政策覆盖度：{'/'.join(POLICY_VALUES)}")
    sc.add_argument("--fund", required=True, help=f"国字号基金介入：{'/'.join(FUND_VALUES)}")
    sc.add_argument("--as-of", default=None, help="档位判定数据截止日期（可选，仅透传）")
    sc.add_argument("--basis", default=None, help="档位判定依据/来源（可选，仅透传）")

    lc = sub.add_parser("localize", help="单点国产化率四档判定（输出 JSON）")
    lc.add_argument("--industry", required=True,
                    help="行业/领域/环节名（任意非空文本，纯透传）")
    lc.add_argument("--localization-rate", required=True,
                    help="国产化率百分数（0~100）")
    lc.add_argument("--strategic-choke-point", action="store_true",
                    help="是否属战略必争卡脖子环节（仅 rate<5 生效）")
    lc.add_argument("--as-of", default=None,
                    help="国产化率数据截止日期（可选，仅透传）")
    lc.add_argument("--basis", default=None,
                    help="判定依据/来源（可选，仅透传）")

    sub.add_parser("examples", help="内置半导体设备四梯队示例（输出 JSON）")

    sn = sub.add_parser("scan", help="检索地缘风险+政策基金来源快照（不判档）")
    sn.add_argument("--industry", default=None,
                    help="地缘风险维度检索对象（行业/领域名）")
    sn.add_argument("--fund", default=None,
                    help="政策基金维度检索对象（行业/领域/基金名）")

    args = parser.parse_args()

    if args.command == "screen":
        return cmd_screen(args)
    if args.command == "localize":
        return cmd_localize(args)
    if args.command == "examples":
        return cmd_examples(args)
    if args.command == "scan":
        return cmd_scan(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())