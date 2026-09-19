#!/usr/bin/env python3
"""治理数据评分工具（governance_data）：管理层 20 分制 + 科研转化 20 分制 + ESG 折价。

本工具将《中长期价值成长（GARP）投资框架》第 3 步·支柱三的两套 20 分制、
以及第 4 步·ESG/环境风险的估值折价下沉为可执行命令，禁止 LLM 心算。

- ``management`` 输入：诚信否决闸门（兑现率 + 业绩预告/归因习惯/监管立案/财务造假 4 个
  布尔标志）+ 对待股东 / 战略执行力 / 稳定性与激励三个维度的评分项（客观数值 +
  定性档位 + 布尔标志）。
- ``management`` 输出：JSON，核心字段 ``integrity_veto / total / verdict
  （重仓/观察/放弃）/ score_breakdown``，附 ``data_as_of`` 时效回显与口径来源标注。
- ``management`` 判定顺序固定：
  1. 诚信否决闸门前置：任一命中即 ``integrity_veto=true``、``total=null``、
     ``verdict=放弃``，不进入 20 分制求和。
  2. 20 分制三维求和：对待股东 7 + 战略执行力 7 + 稳定性与激励 6 = 20。
  3. 三档判定：total>=15 重仓；10<=total<15 观察（单只上限<=5%，不重仓）；
     total<10 放弃。
- ``research`` 输入：研发投入（研发强度+逐年提升/资本化率/研发人员占比）+
  研发产出（专利质量/新产品收入占比/产品化周期/项目节点）+ 资本回报
  （现状 ROIC / WACC / 增量 ROIC，数值透传引用 P1-1/P1-2/P1-3）。
- ``research`` 输出：JSON，核心字段 ``total / verdict（重仓/观察/放弃）/
  score_breakdown``，附 ``warning`` 缺省降级提示、``data_as_of`` 与口径来源；
  **无诚信否决闸门**（诚信否决属 ``management`` 专属）。资本回报维度不重算 ROIC，
  以调用方传入的数值做「ROIC > WACC」「增量 ROIC > 存量 ROIC」严格大于判定。
- ``esg`` 输入：环境风险等级（高/低，必填）+ 转型路径（明确/无，缺省无）+
  搁浅资产标志 + ESG 评级尾部标志 + 仓位上限基线（缺省 20%）。
- ``esg`` 输出：JSON，核心字段 ``discount_factor / discount_pct /
  discount_rate_adj_bps / position_cap_downgrade`` 三通道折价修正量，附
  ``data_as_of`` 时效回显与口径来源；无 ``verdict``/``score_breakdown``
  （非评分制）。折价值在基本面估值之上叠加使用，由 P4-5/P4-6 技能编排收口。
- 关键边界：
  * 7+7+6 / 8+8+4 三维权重与 >=15/10 阈值是静态标签（框架明示长期适用）；
  * 各评分项的「取值判定」是时变项（兑现率/分红率/质押率/离职率/研发强度/
    新产品占比/ROIC 系列数值及否决事实，随财报/公告动态变化），本工具
    **不检索、不判定事实真伪、不固化事实**，仅透传调用方传入的 ``--as-of``
    （评分数据截止日期）并对给定电平值做确定性评分；
  * 实时取证交由 P3-7（annual_report_parser 治理字段）与技能编排承接；
  * 费雪补充与 ESG 补充均为定性参考，不计入 20 分制，仅在 ``note`` 提示其存在；
  * 「管理层 + 科研转化两套都须>=15」的合成由 P4-4 技能编排承担，本工具只输出
    单套 verdict。
- 非法档位或数值越界：打印错误并返回非零退出码，拒绝判分（fail-fast，不猜）。

用法（示例）:
    python tools/specialized/governance_data.py management \
        --fulfillment-rate 72.0 \
        --dividend-payout-ratio 35.0 --financing 优 --buyback 优 --pledge-ratio 28.0 \
        --core-focus 优 --strategy-exec 优 --industry-cog 优 \
        --turnover-rate 7.0 --equity-incentive 优 \
        --as-of 2026-09-15

    python tools/specialized/governance_data.py management --financial-fraud

    python tools/specialized/governance_data.py research \
        --rd-intensity 18.0 --rd-intensity-rising \
        --capitalization-rate 12.0 --rd-personnel-ratio 32.0 \
        --patent-quality 优 --new-product-revenue-ratio 25.0 \
        --commercialization-cycle 优 --project-milestone 优 \
        --roic 16.0 --wacc 8.0 --incremental-roic 19.0 \
        --as-of 2026-09-16

    python tools/specialized/governance_data.py esg \
        --env-risk-level 高 --transition-pathway 无 \
        --stranded-asset --esg-tail --position-cap-base 20.0 \
        --as-of 2026-09-16
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 定性档位词表（唯一合法取值范围）
# ---------------------------------------------------------------------------

#: 定性档位统一词表（优/中/差）。
QUALITY_VALUES: Tuple[str, ...] = ("优", "中", "差")

# ---------------------------------------------------------------------------
# 诚信否决闸门（不计分，命中即放弃/清仓）
# ---------------------------------------------------------------------------

#: 5 个否决项键名 -> 中文标签（键名即输出 integrity_veto_reasons 的取值）。
VETO_FLAGS: Dict[str, str] = {
    "fulfillment_rate": "年报\"说到做到\"兑现率<50%",
    "guidance_misstatement": "业绩预告重大失真",
    "attribution_habit": "归因习惯异常",
    "regulatory_filing": "监管立案",
    "financial_fraud": "财务造假实锤",
}

#: 兑现率否决阈值（<50 一票否决）。
FULFILLMENT_VETO_THRESHOLD: float = 50.0

# ---------------------------------------------------------------------------
# 20 分制三维权重（唯一权威 = 框架第 3 步·支柱三；子项分值为本任务固化）
# ---------------------------------------------------------------------------

#: 维度 -> (中文名, 满分, 子项键序列)。
DIMENSION_SCORES: Dict[str, Dict[str, Any]] = {
    "shareholder_treatment": {
        "label": "对待股东",
        "max": 7,
        "items": ("dividend_payout_ratio", "financing", "buyback", "pledge_ratio"),
    },
    "strategy_execution": {
        "label": "战略执行力",
        "max": 7,
        "items": ("core_focus", "strategy_exec", "industry_cog"),
    },
    "stability_incentive": {
        "label": "稳定性与激励",
        "max": 6,
        "items": ("turnover_rate", "equity_incentive", "insider_abnormal"),
    },
}

#: 子项键名 -> 中文标签。
ITEM_LABELS: Dict[str, str] = {
    "dividend_payout_ratio": "分红历史",
    "financing": "融资记录",
    "buyback": "回购行为",
    "pledge_ratio": "大股东质押率",
    "core_focus": "聚焦主业",
    "strategy_exec": "核心战略落地",
    "industry_cog": "行业格局认知深度",
    "turnover_rate": "核心团队稳定性",
    "equity_incentive": "股权激励合理性",
    "insider_abnormal": "内部人增减持异常",
}

#: 子项键名 -> 满分（§5.3 已确认权重）。
SUBITEM_MAX: Dict[str, int] = {
    "dividend_payout_ratio": 2,
    "financing": 2,
    "buyback": 2,
    "pledge_ratio": 1,
    "core_focus": 3,
    "strategy_exec": 2,
    "industry_cog": 2,
    "turnover_rate": 2,
    "equity_incentive": 2,
    "insider_abnormal": 2,
}

#: 数值阈值切点（左闭右开，§9.C 已确认）。
#: 分红率 [30,100]/[15,30)/[0,15)。
DIVIDEND_HIGH_THRESHOLD: float = 30.0
DIVIDEND_MID_THRESHOLD: float = 15.0

#: 大股东质押率 [0,50]/(50,100]。
PLEDGE_WARNING_THRESHOLD: float = 50.0

#: 核心团队离职率 [0,10)/[10,20)/[20,100]。
TURNOVER_MID_THRESHOLD: float = 10.0
TURNOVER_HIGH_THRESHOLD: float = 20.0

#: 口径来源（可追溯）。
SOURCE: str = "框架第3步·支柱三"

#: 时效警示（恒定，评分为时变输入）。
TIME_SENSITIVITY_NOTE: str = (
    "管理层评分为时变输入，结论仅对数据截止日期有效，须以最新财报/公告复核"
)

#: 补充检查提示（恒定，不计入 20 分制）。
NOTE: str = (
    "费雪补充（销售组织/管理层持股≥3%）与 ESG 补充为定性参考，不计入 20 分制"
)

#: 否决命中时的退档说明（恒定）。
VETO_POSITION_NOTE: str = "诚信否决命中，直接放弃或清仓，总分无效"


# ---------------------------------------------------------------------------
# 科研转化 20 分制（P3-5，8+8+4；无诚信否决闸门）
# ---------------------------------------------------------------------------

#: 科研转化三维度 -> (中文名, 满分, 子项键序列)。
RESEARCH_DIMENSIONS: Dict[str, Dict[str, Any]] = {
    "rd_input": {
        "label": "研发投入“质”与“量”",
        "max": 8,
        "items": ("rd_intensity", "capitalization_rate", "rd_personnel_ratio"),
    },
    "rd_output": {
        "label": "研发产出效率",
        "max": 8,
        "items": ("patent_quality", "new_product_revenue_ratio",
                  "commercialization_cycle", "project_milestone"),
    },
    "capital_return": {
        "label": "资本回报效率",
        "max": 4,
        "items": ("roic_vs_wacc", "incremental_vs_roic"),
    },
}

#: 科研子项键名 -> 中文标签。
RESEARCH_ITEM_LABELS: Dict[str, str] = {
    "rd_intensity": "研发强度及逐年提升",
    "capitalization_rate": "资本化审慎",
    "rd_personnel_ratio": "研发人员占比",
    "patent_quality": "发明专利数量与质量",
    "new_product_revenue_ratio": "新产品收入占比",
    "commercialization_cycle": "技术产品化周期",
    "project_milestone": "重大科研项目节点推进",
    "roic_vs_wacc": "ROIC > WACC",
    "incremental_vs_roic": "增量资本回报率 > 存量 ROIC",
}

#: 科研子项键名 -> 满分（§9.A 已确认权重：研发投入 3+2+3；研发产出 2+2+2+2；
#: 资本回报 2+2）。
RESEARCH_SUBITEM_MAX: Dict[str, int] = {
    "rd_intensity": 3,
    "capitalization_rate": 2,
    "rd_personnel_ratio": 3,
    "patent_quality": 2,
    "new_product_revenue_ratio": 2,
    "commercialization_cycle": 2,
    "project_milestone": 2,
    "roic_vs_wacc": 2,
    "incremental_vs_roic": 2,
}

#: 数值阈值切点（左闭右开，§9.B 已确认）。
#: 研发强度 [15,100]；资本化率 [0,30)/[30,100]；研发人员占比 [30,100]/[15,30)/[0,15)；
#: 新产品收入占比 [20,100]/[10,20)/[0,10)；资本回报两项为严格大于（>）。
RD_INTENSITY_THRESHOLD: float = 15.0
CAPITALIZATION_THRESHOLD: float = 30.0
RD_PERSONNEL_HIGH_THRESHOLD: float = 30.0
RD_PERSONNEL_MID_THRESHOLD: float = 15.0
NEW_PRODUCT_HIGH_THRESHOLD: float = 20.0
NEW_PRODUCT_MID_THRESHOLD: float = 10.0

#: 科研转化口径来源（可追溯）。
RESEARCH_SOURCE: str = "框架第3步·支柱三（科研转化评估清单）"

#: 科研转化时效警示（恒定）。
RESEARCH_TIME_SENSITIVITY_NOTE: str = (
    "科研转化评分为时变输入，结论仅对数据截止日期有效，须以最新财报/公告复核"
)

#: 科研转化补充说明（恒定，不计分）。
RESEARCH_NOTE: str = (
    "科技股专用科研转化单套 20 分制；与管理层 20 分制「两套都须≥15」的合成由 "
    "P4-4 技能编排承担；研发费用加回估值调整见 P1-6 adjusted-peg"
)


# ---------------------------------------------------------------------------
# ESG 环境风险估值折价（P3-6，无评分制，输出三通道折价修正量）
# ---------------------------------------------------------------------------

#: 环境风险等级词表（高/低）。
ENV_RISK_VALUES: Tuple[str, ...] = ("高", "低")

#: 转型路径词表（明确/无）。
TRANSITION_VALUES: Tuple[str, ...] = ("明确", "无")

#: 折扣系数基表：(环境风险等级, 有意转型路径) -> 基础折价系数。
#: 低环境风险=1.00（不折价）；高+明确转型=0.95（折价 5%）；高+无转型=0.85（8.5 折）。
DISCOUNT_TABLE: Dict[Tuple[str, str], float] = {
    ("高", "无"): 0.85,
    ("高", "明确"): 0.95,
    ("低", "无"): 1.00,
    ("低", "明确"): 1.00,
}

#: 搁浅资产额外折价（在基础折扣上再减）。
STRANDED_EXTRA_DISCOUNT: float = 0.05

#: 折价系数下限（框架「8~9 折」区间下限 8 折）。
DISCOUNT_FLOOR: float = 0.80

#: 搁浅资产贴现率上调默认值（bp，取框架「1~2pct」中值 1.5pct）。
DISCOUNT_RATE_ADJ_BPS: int = 150

#: 搁浅资产贴现率上调权威区间（bp）。
DISCOUNT_RATE_ADJ_RANGE_BPS: Tuple[int, int] = (100, 200)

#: 高环境风险行业折价来源区间备注（回显）。
DISCOUNT_RANGE_NOTE: str = "0.80~0.90"

#: 仓位上限下调百分点（框架「绝对上限 20%~15%」）。
POSITION_CAP_DOWNGRADE_PCT: float = 5.0

#: 仓位上限基线默认值（%，框架单只绝对上限 20%）。
POSITION_CAP_BASE_DEFAULT: float = 20.0

#: ESG 折价口径来源（可追溯）。
ESG_SOURCE: str = "框架第4步·ESG/环境风险的估值折价 + 第3步·支柱三 ESG 补充检查"

#: ESG 折价时效警示（恒定）。
ESG_TIME_SENSITIVITY_NOTE: str = (
    "ESG 环境风险折价基于数据截止日期的事实输入，评级/转型/搁浅资产判定须以最新公开信息复核"
)

#: ESG 折价使用边界提示（恒定）。
ESG_NOTE: str = (
    "折价在基本面估值之上叠加使用；DCF 需在本工具给出的贴现率上调基础上重算；"
    "仓位上限下调为单只绝对上限的降档动作"
)


def _assert_research_weights() -> None:
    """校验科研三维子项权重和恰等于其满分（8/8/4），且键与标签/满分表一致。

    防御常量手写笔误，确保运行时科研三维总分恒为 20，且 score_breakdown 逐项可复现。

    Raises:
        AssertionError: 任一维度子项权重和与其满分不符，或子项键表不自洽时抛出。
    """
    expected = {"rd_input": 8, "rd_output": 8, "capital_return": 4}
    all_item_keys: set = set()
    for dim, meta in RESEARCH_DIMENSIONS.items():
        items = meta["items"]
        weight_sum = sum(RESEARCH_SUBITEM_MAX[key] for key in items)
        assert weight_sum == expected[dim], (
            f"{dim} 子项权重和 {weight_sum} != {expected[dim]}")
        assert meta["max"] == expected[dim], (
            f"{dim} 满分 {meta['max']} != {expected[dim]}")
        all_item_keys.update(items)

    assert set(RESEARCH_SUBITEM_MAX) == all_item_keys, (
        "RESEARCH_SUBITEM_MAX 与 RESEARCH_DIMENSIONS 子项键不一致")
    assert set(RESEARCH_ITEM_LABELS) == all_item_keys, (
        "RESEARCH_ITEM_LABELS 与 RESEARCH_DIMENSIONS 子项键不一致")
    assert sum(expected.values()) == 20, "科研三维度满分和须为 20"


#: 导入时即执行科研三维权重自检，确保规则表完整、自洽。
_assert_research_weights()


def _assert_dimension_weights() -> None:
    """校验三维子项权重和恰等于其满分（7/7/6），且子项键与标签/满分表一致。

    防御常量手写笔误，确保运行时三维总分恒为 20，且 score_breakdown 逐项可复现。

    Raises:
        AssertionError: 任一维度子项权重和与其满分不符，或子项键表不自洽时抛出。
    """
    expected = {"shareholder_treatment": 7, "strategy_execution": 7,
                "stability_incentive": 6}
    all_item_keys: set = set()
    for dim, meta in DIMENSION_SCORES.items():
        items = meta["items"]
        weight_sum = sum(SUBITEM_MAX[key] for key in items)
        assert weight_sum == expected[dim], (
            f"{dim} 子项权重和 {weight_sum} != {expected[dim]}")
        assert meta["max"] == expected[dim], (
            f"{dim} 满分 {meta['max']} != {expected[dim]}")
        all_item_keys.update(items)

    assert set(SUBITEM_MAX) == all_item_keys, "SUBITEM_MAX 与 DIMENSION_SCORES 子项键不一致"
    assert set(ITEM_LABELS) == all_item_keys, "ITEM_LABELS 与 DIMENSION_SCORES 子项键不一致"
    assert sum(expected.values()) == 20, "三维度满分和须为 20"


#: 导入时即执行三维权重自检，确保规则表完整、自洽。
_assert_dimension_weights()


# ---------------------------------------------------------------------------
# 输入校验与评分辅助
# ---------------------------------------------------------------------------

def _parse_rate(value: Any, name: str, *, required: bool = True) -> Optional[float]:
    """解析并校验 0~100 的百分数数值输入。

    Args:
        value: 待校验的数值（None 视为未提供）。
        name: 数值项中文名（用于错误提示）。
        required: 是否必须提供（为 True 且 value 为 None 时抛错）。

    Returns:
        Optional[float]: 解析后的 float；value 为 None 且非必须时返回 None。

    Raises:
        ValueError: 值为布尔、非数值、NaN/Inf，或超出 0~100 区间时抛出。
    """
    if value is None:
        if required:
            raise ValueError(f"缺少必要评分输入：{name}")
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} 须为 0~100 的数值，不能为布尔值")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 须为 0~100 的数值") from exc
    if math.isnan(parsed) or math.isinf(parsed):
        raise ValueError(f"{name} 须为 0~100 的数值，不能为 NaN/Inf")
    if parsed < 0.0 or parsed > 100.0:
        raise ValueError(f"{name} 须在 0~100 之间")
    return parsed


def _validate_quality(value: Any, name: str) -> str:
    """校验定性档位须在 优/中/差 词表内（fail-fast，非法即抛错）。

    Args:
        value: 待校验的档位值。
        name: 评分项中文名（用于错误提示）。

    Returns:
        str: 校验通过的档位值（即原值）。

    Raises:
        ValueError: 档位值不在 QUALITY_VALUES 内时抛出。
    """
    if value not in QUALITY_VALUES:
        raise ValueError(f"非法档位「{value}」，{name} 可选 {list(QUALITY_VALUES)}")
    return value


def _validate_enum(value: Any, name: str, values: Tuple[str, ...]) -> str:
    """校验枚举值须在给定词表内（fail-fast，非法即抛错）。

    Args:
        value: 待校验的枚举值。
        name: 评分项中文名（用于错误提示）。
        values: 合法取值词表。

    Returns:
        str: 校验通过的枚举值（即原值）。

    Raises:
        ValueError: 值不在 ``values`` 内时抛出。
    """
    if value not in values:
        raise ValueError(f"非法档位「{value}」，{name} 可选 {list(values)}")
    return value


def _score_qual(value: str, full: int, mid: int) -> int:
    """按 优=满 / 中=mid / 差=0 映射定性档位分值。

    Args:
        value: 定性档位（优/中/差）。
        full: 满档分值。
        mid: 中档分值。

    Returns:
        int: 档位对应分值。
    """
    if value == "优":
        return full
    if value == "中":
        return mid
    return 0  # 差


def _score_dividend(rate: float) -> int:
    """分红历史计分：[30,100]=2；[15,30)=1；[0,15)=0。"""
    if rate >= DIVIDEND_HIGH_THRESHOLD:
        return 2
    if rate >= DIVIDEND_MID_THRESHOLD:
        return 1
    return 0


def _score_pledge(rate: float) -> int:
    """大股东质押率计分：[0,50]=1；>50=0（预警）。"""
    return 1 if rate <= PLEDGE_WARNING_THRESHOLD else 0


def _score_turnover(rate: float) -> int:
    """核心团队离职率计分：[0,10)=2；[10,20)=1；[20,100]=0。"""
    if rate < TURNOVER_MID_THRESHOLD:
        return 2
    if rate < TURNOVER_HIGH_THRESHOLD:
        return 1
    return 0


def _parse_percent_unbounded(value: Any, name: str) -> Optional[float]:
    """解析允许负值的百分数数值输入（用于 ROIC/WACC/增量 ROIC）。

    与 ``_parse_rate`` 的区别：不套用 0~100 硬边界（ROIC / 增量 ROIC 可为负），
    仍拒绝布尔/非数值/NaN/Inf。

    Args:
        value: 待校验的数值（None 视为未提供）。
        name: 数值项中文名（用于错误提示）。

    Returns:
        Optional[float]: 解析后的 float；value 为 None 时返回 None。

    Raises:
        ValueError: 值为布尔、非数值、NaN/Inf 时抛出。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} 须为数值，不能为布尔值")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 须为数值") from exc
    if math.isnan(parsed) or math.isinf(parsed):
        raise ValueError(f"{name} 须为数值，不能为 NaN/Inf")
    return parsed


def _score_rd_intensity(rd_intensity: float, rising: bool) -> int:
    """研发强度及逐年提升计分：≥15% 且提升=3；≥15% 未提升=2；<15%=0。"""
    if rd_intensity < RD_INTENSITY_THRESHOLD:
        return 0
    return 3 if rising else 2


def _score_capitalization(rate: float) -> int:
    """资本化审慎计分：[0,30)=2；[30,100]=0。"""
    return 2 if rate < CAPITALIZATION_THRESHOLD else 0


def _score_rd_personnel(rate: float) -> int:
    """研发人员占比计分：[30,100]=3；[15,30)=1；[0,15)=0。"""
    if rate >= RD_PERSONNEL_HIGH_THRESHOLD:
        return 3
    if rate >= RD_PERSONNEL_MID_THRESHOLD:
        return 1
    return 0


def _score_new_product(rate: float) -> int:
    """新产品收入占比计分：[20,100]=2；[10,20)=1；[0,10)=0。"""
    if rate >= NEW_PRODUCT_HIGH_THRESHOLD:
        return 2
    if rate >= NEW_PRODUCT_MID_THRESHOLD:
        return 1
    return 0


# ---------------------------------------------------------------------------
# 核心判定
# ---------------------------------------------------------------------------

def build_governance_result(
    *,
    fulfillment_rate: Optional[float] = None,
    guidance_misstatement: bool = False,
    attribution_habit: bool = False,
    regulatory_filing: bool = False,
    financial_fraud: bool = False,
    dividend_payout_ratio: Optional[float] = None,
    financing: Optional[str] = None,
    buyback: Optional[str] = None,
    pledge_ratio: Optional[float] = None,
    core_focus: Optional[str] = None,
    strategy_exec: Optional[str] = None,
    industry_cog: Optional[str] = None,
    turnover_rate: Optional[float] = None,
    equity_incentive: Optional[str] = None,
    insider_abnormal: Optional[bool] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """对单个管理层评估输入执行「诚信前置否决 + 20 分制三维求和 + 三档判定」。

    判定顺序固定：
    1. 解析兑现率（可选，若提供则须 0~100），据此与 4 个布尔标志一同判定诚信否决。
    2. 任一否决命中 -> ``integrity_veto=true``、``total=null``、``verdict=放弃``、
       ``score_breakdown={}``，不进入 20 分制求和。
    3. 否则校验并解析全部评分输入（缺失/越界/非法档位均 fail-fast）。
    4. 三维求和得出 ``total``，按 >=15 / 10~14 / <10 判定 verdict。

    Args:
        fulfillment_rate: 年报"说到做到"兑现率（%，0~100）。可选；<50 时否决。
        guidance_misstatement: 是否业绩预告重大失真（可选，默认 False）。
        attribution_habit: 是否归因习惯异常（可选，默认 False）。
        regulatory_filing: 是否监管立案（可选，默认 False）。
        financial_fraud: 是否财务造假实锤（可选，默认 False）。
        dividend_payout_ratio: 分红率（%，0~100，否决未命中时必填）。
        financing: 融资记录档位（优/中/差，否决未命中时必填）。
        buyback: 回购行为档位（优/中/差，否决未命中时必填）。
        pledge_ratio: 大股东质押率（%，0~100，否决未命中时必填）。
        core_focus: 聚焦主业档位（优/中/差，否决未命中时必填）。
        strategy_exec: 核心战略落地档位（优/中/差，否决未命中时必填）。
        industry_cog: 行业格局认知深度档位（优/中/差，否决未命中时必填）。
        turnover_rate: 核心团队离职率（%，0~100，否决未命中时必填）。
        equity_incentive: 股权激励合理性档位（优/中/差，否决未命中时必填）。
        insider_abnormal: 内部人增减持是否异常（True=异常，False=无异常；否决未命中时必填）。
        as_of: 评分数据截止日期（可选，仅透传，不参与判定）。

    Returns:
        Dict[str, Any]: §3.3 顶层输出对象（含 integrity_veto/total/verdict/
        score_breakdown 等）。

    Raises:
        ValueError: 数值越界/非数值、档位非法，或否决未命中时缺少必要评分输入。
    """
    # 原始输入回显（flag 布尔化，其余原样透传）。
    input_payload: Dict[str, Any] = {
        "fulfillment_rate": fulfillment_rate,
        "guidance_misstatement": bool(guidance_misstatement),
        "attribution_habit": bool(attribution_habit),
        "regulatory_filing": bool(regulatory_filing),
        "financial_fraud": bool(financial_fraud),
        "dividend_payout_ratio": dividend_payout_ratio,
        "financing": financing,
        "buyback": buyback,
        "pledge_ratio": pledge_ratio,
        "core_focus": core_focus,
        "strategy_exec": strategy_exec,
        "industry_cog": industry_cog,
        "turnover_rate": turnover_rate,
        "equity_incentive": equity_incentive,
        "insider_abnormal": insider_abnormal,
        "as_of": as_of,
    }

    # 步骤①：诚信否决闸门（兑现率为可选否决项，其余为布尔标志）。
    fulfillment = _parse_rate(fulfillment_rate, "兑现率", required=False)
    veto_reasons: List[str] = []
    if fulfillment is not None and fulfillment < FULFILLMENT_VETO_THRESHOLD:
        veto_reasons.append("fulfillment_rate")
    if guidance_misstatement:
        veto_reasons.append("guidance_misstatement")
    if attribution_habit:
        veto_reasons.append("attribution_habit")
    if regulatory_filing:
        veto_reasons.append("regulatory_filing")
    if financial_fraud:
        veto_reasons.append("financial_fraud")

    if veto_reasons:
        return {
            "task": "management",
            "integrity_veto": True,
            "integrity_veto_reasons": veto_reasons,
            "total": None,
            "verdict": "放弃",
            "position_note": VETO_POSITION_NOTE,
            "score_breakdown": {},
            "data_as_of": as_of,
            "time_sensitivity_note": TIME_SENSITIVITY_NOTE,
            "note": NOTE,
            "source": SOURCE,
            "input": input_payload,
        }

    # 步骤②：否决未命中，校验并解析全部评分输入（fail-fast）。
    dividend = _parse_rate(dividend_payout_ratio, "分红率")
    pledge = _parse_rate(pledge_ratio, "大股东质押率")
    turnover = _parse_rate(turnover_rate, "核心团队离职率")

    financing = _validate_quality(financing, "融资记录")
    buyback = _validate_quality(buyback, "回购行为")
    core_focus = _validate_quality(core_focus, "聚焦主业")
    strategy_exec = _validate_quality(strategy_exec, "核心战略落地")
    industry_cog = _validate_quality(industry_cog, "行业格局认知深度")
    equity_incentive = _validate_quality(equity_incentive, "股权激励合理性")

    if not isinstance(insider_abnormal, bool):
        raise ValueError("内部人增减持异常须为布尔值（True=异常，False=无异常）")

    # 各维度子项打分（确定性规则，无 LLM 临场判断）。
    shareholder_items: Dict[str, Dict[str, Any]] = {
        "dividend_payout_ratio": {
            "label": ITEM_LABELS["dividend_payout_ratio"],
            "score": _score_dividend(dividend),
            "max": SUBITEM_MAX["dividend_payout_ratio"],
            "value": dividend,
        },
        "financing": {
            "label": ITEM_LABELS["financing"],
            "score": _score_qual(financing, 2, 1),
            "max": SUBITEM_MAX["financing"],
            "value": financing,
        },
        "buyback": {
            "label": ITEM_LABELS["buyback"],
            "score": _score_qual(buyback, 2, 1),
            "max": SUBITEM_MAX["buyback"],
            "value": buyback,
        },
        "pledge_ratio": {
            "label": ITEM_LABELS["pledge_ratio"],
            "score": _score_pledge(pledge),
            "max": SUBITEM_MAX["pledge_ratio"],
            "value": pledge,
        },
    }

    strategy_items: Dict[str, Dict[str, Any]] = {
        "core_focus": {
            "label": ITEM_LABELS["core_focus"],
            "score": _score_qual(core_focus, 3, 1),
            "max": SUBITEM_MAX["core_focus"],
            "value": core_focus,
        },
        "strategy_exec": {
            "label": ITEM_LABELS["strategy_exec"],
            "score": _score_qual(strategy_exec, 2, 1),
            "max": SUBITEM_MAX["strategy_exec"],
            "value": strategy_exec,
        },
        "industry_cog": {
            "label": ITEM_LABELS["industry_cog"],
            "score": _score_qual(industry_cog, 2, 1),
            "max": SUBITEM_MAX["industry_cog"],
            "value": industry_cog,
        },
    }

    stability_items: Dict[str, Dict[str, Any]] = {
        "turnover_rate": {
            "label": ITEM_LABELS["turnover_rate"],
            "score": _score_turnover(turnover),
            "max": SUBITEM_MAX["turnover_rate"],
            "value": turnover,
        },
        "equity_incentive": {
            "label": ITEM_LABELS["equity_incentive"],
            "score": _score_qual(equity_incentive, 2, 1),
            "max": SUBITEM_MAX["equity_incentive"],
            "value": equity_incentive,
        },
        "insider_abnormal": {
            "label": ITEM_LABELS["insider_abnormal"],
            "score": 0 if insider_abnormal else SUBITEM_MAX["insider_abnormal"],
            "max": SUBITEM_MAX["insider_abnormal"],
            "value": insider_abnormal,
        },
    }

    shareholder_score = sum(item["score"] for item in shareholder_items.values())
    strategy_score = sum(item["score"] for item in strategy_items.values())
    stability_score = sum(item["score"] for item in stability_items.values())
    total = shareholder_score + strategy_score + stability_score

    # 步骤③：三档判定。
    if total >= 15:
        verdict = "重仓"
        position_note = "管理层评分≥15，可重仓"
    elif total >= 10:
        verdict = "观察"
        position_note = "管理层评分10~14，部分不达标，观察仓（单只上限≤5%），不重仓"
    else:
        verdict = "放弃"
        position_note = "管理层评分<10，放弃"

    score_breakdown: Dict[str, Dict[str, Any]] = {
        "shareholder_treatment": {
            "score": shareholder_score,
            "max": DIMENSION_SCORES["shareholder_treatment"]["max"],
            "items": shareholder_items,
        },
        "strategy_execution": {
            "score": strategy_score,
            "max": DIMENSION_SCORES["strategy_execution"]["max"],
            "items": strategy_items,
        },
        "stability_incentive": {
            "score": stability_score,
            "max": DIMENSION_SCORES["stability_incentive"]["max"],
            "items": stability_items,
        },
    }

    return {
        "task": "management",
        "integrity_veto": False,
        "integrity_veto_reasons": [],
        "total": total,
        "verdict": verdict,
        "position_note": position_note,
        "score_breakdown": score_breakdown,
        "data_as_of": as_of,
        "time_sensitivity_note": TIME_SENSITIVITY_NOTE,
        "note": NOTE,
        "source": SOURCE,
        "input": input_payload,
    }


def build_research_result(
    *,
    rd_intensity: Optional[float] = None,
    rd_intensity_rising: bool = False,
    capitalization_rate: Optional[float] = None,
    rd_personnel_ratio: Optional[float] = None,
    patent_quality: Optional[str] = None,
    new_product_revenue_ratio: Optional[float] = None,
    commercialization_cycle: Optional[str] = None,
    project_milestone: Optional[str] = None,
    roic: Optional[float] = None,
    wacc: Optional[float] = None,
    incremental_roic: Optional[float] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """对单个科研转化输入执行「8+8+4 三维求和 + 三档判定」。

    判定顺序固定（无诚信否决闸门）：
    1. 解析研发投入/研发产出全部必填评分输入（缺失/越界/非法档位 fail-fast）。
    2. 解析资本回报引用数值（现状 ROIC / WACC / 增量 ROIC，允许负值）；
       ROIC 缺省、或 WACC/增量 ROIC 缺省 → 对应子项按 0 分计并追加 warning
       （纯计算工具「不猜、标注缺口」，不报错退出）。
    3. 三维求和得出 ``total``，按 >=15 / 10~14 / <10 判定 verdict。

    Args:
        rd_intensity: 研发强度（%，0~100，必填）。
        rd_intensity_rising: 研发强度是否逐年提升（可选，默认 False）。
        capitalization_rate: 研发支出资本化率（%，0~100，必填）。
        rd_personnel_ratio: 研发人员占比（%，0~100，必填）。
        patent_quality: 发明专利数量与质量档位（优/中/差，必填）。
        new_product_revenue_ratio: 新产品收入占比（%，0~100，必填）。
        commercialization_cycle: 技术产品化周期档位（优/中/差，必填）。
        project_milestone: 重大科研项目节点推进档位（优/中/差，必填）。
        roic: 存量 ROIC（%，可为负；缺省时资本回报两项均 0 分 + warning）。
        wacc: WACC（%，缺省时「ROIC > WACC」0 分 + warning）。
        incremental_roic: 增量 ROIC（%，可为负；缺省时「增量 > 存量」0 分 + warning）。
        as_of: 评分数据截止日期（可选，仅透传，不参与判定）。

    Returns:
        Dict[str, Any]: §3.3 顶层输出对象（含 total/verdict/score_breakdown/
        warning 等，无 integrity_veto 字段）。

    Raises:
        ValueError: 研发投入/产出必填项缺失或越界/非数值、档位非法。
    """
    input_payload: Dict[str, Any] = {
        "rd_intensity": rd_intensity,
        "rd_intensity_rising": bool(rd_intensity_rising),
        "capitalization_rate": capitalization_rate,
        "rd_personnel_ratio": rd_personnel_ratio,
        "patent_quality": patent_quality,
        "new_product_revenue_ratio": new_product_revenue_ratio,
        "commercialization_cycle": commercialization_cycle,
        "project_milestone": project_milestone,
        "roic": roic,
        "wacc": wacc,
        "incremental_roic": incremental_roic,
        "as_of": as_of,
    }

    # 步骤①：研发投入/产出必填项（缺失/越界/非法档位 fail-fast）。
    rd_intensity_val = _parse_rate(rd_intensity, "研发强度")
    capitalization = _parse_rate(capitalization_rate, "资本化率")
    rd_personnel = _parse_rate(rd_personnel_ratio, "研发人员占比")
    new_product = _parse_rate(new_product_revenue_ratio, "新产品收入占比")

    patent_quality_v = _validate_quality(patent_quality, "发明专利数量与质量")
    commercialization_v = _validate_quality(commercialization_cycle,
                                            "技术产品化周期")
    project_milestone_v = _validate_quality(project_milestone,
                                            "重大科研项目节点推进")

    # 步骤②：资本回报引用数值（允许负值；缺省降级为 0 分 + warning）。
    roic_val = _parse_percent_unbounded(roic, "存量 ROIC")
    wacc_val = _parse_percent_unbounded(wacc, "WACC")
    incremental_val = _parse_percent_unbounded(incremental_roic, "增量 ROIC")

    warnings: List[str] = []
    if roic_val is None:
        roic_vs_wacc_score = 0
        incremental_vs_roic_score = 0
        warnings.append("未提供 ROIC，资本回报维度无法判定，两项均按 0 分计")
    else:
        if wacc_val is None:
            roic_vs_wacc_score = 0
            warnings.append("未提供 WACC，无法判定「ROIC > WACC」，该项按 0 分计")
        elif roic_val > wacc_val:
            roic_vs_wacc_score = 2
        else:
            roic_vs_wacc_score = 0

        if incremental_val is None:
            incremental_vs_roic_score = 0
            warnings.append(
                "未提供增量 ROIC，无法判定「增量资本回报率 > 存量 ROIC」，该项按 0 分计")
        elif incremental_val > roic_val:
            incremental_vs_roic_score = 2
        else:
            incremental_vs_roic_score = 0

    # 步骤③：各维度子项打分（确定性规则，无 LLM 临场判断）。
    rd_input_items: Dict[str, Dict[str, Any]] = {
        "rd_intensity": {
            "label": RESEARCH_ITEM_LABELS["rd_intensity"],
            "score": _score_rd_intensity(rd_intensity_val,
                                         bool(rd_intensity_rising)),
            "max": RESEARCH_SUBITEM_MAX["rd_intensity"],
            "value": rd_intensity_val,
            "rising": bool(rd_intensity_rising),
        },
        "capitalization_rate": {
            "label": RESEARCH_ITEM_LABELS["capitalization_rate"],
            "score": _score_capitalization(capitalization),
            "max": RESEARCH_SUBITEM_MAX["capitalization_rate"],
            "value": capitalization,
        },
        "rd_personnel_ratio": {
            "label": RESEARCH_ITEM_LABELS["rd_personnel_ratio"],
            "score": _score_rd_personnel(rd_personnel),
            "max": RESEARCH_SUBITEM_MAX["rd_personnel_ratio"],
            "value": rd_personnel,
        },
    }

    rd_output_items: Dict[str, Dict[str, Any]] = {
        "patent_quality": {
            "label": RESEARCH_ITEM_LABELS["patent_quality"],
            "score": _score_qual(patent_quality_v, 2, 1),
            "max": RESEARCH_SUBITEM_MAX["patent_quality"],
            "value": patent_quality_v,
        },
        "new_product_revenue_ratio": {
            "label": RESEARCH_ITEM_LABELS["new_product_revenue_ratio"],
            "score": _score_new_product(new_product),
            "max": RESEARCH_SUBITEM_MAX["new_product_revenue_ratio"],
            "value": new_product,
        },
        "commercialization_cycle": {
            "label": RESEARCH_ITEM_LABELS["commercialization_cycle"],
            "score": _score_qual(commercialization_v, 2, 1),
            "max": RESEARCH_SUBITEM_MAX["commercialization_cycle"],
            "value": commercialization_v,
        },
        "project_milestone": {
            "label": RESEARCH_ITEM_LABELS["project_milestone"],
            "score": _score_qual(project_milestone_v, 2, 1),
            "max": RESEARCH_SUBITEM_MAX["project_milestone"],
            "value": project_milestone_v,
        },
    }

    capital_return_items: Dict[str, Dict[str, Any]] = {
        "roic_vs_wacc": {
            "label": RESEARCH_ITEM_LABELS["roic_vs_wacc"],
            "score": roic_vs_wacc_score,
            "max": RESEARCH_SUBITEM_MAX["roic_vs_wacc"],
            "value": {"roic": roic_val, "wacc": wacc_val},
        },
        "incremental_vs_roic": {
            "label": RESEARCH_ITEM_LABELS["incremental_vs_roic"],
            "score": incremental_vs_roic_score,
            "max": RESEARCH_SUBITEM_MAX["incremental_vs_roic"],
            "value": {"incremental_roic": incremental_val, "roic": roic_val},
        },
    }

    rd_input_score = sum(item["score"] for item in rd_input_items.values())
    rd_output_score = sum(item["score"] for item in rd_output_items.values())
    capital_return_score = sum(item["score"]
                               for item in capital_return_items.values())
    total = rd_input_score + rd_output_score + capital_return_score

    # 步骤④：三档判定（无诚信否决，直接按总分）。
    if total >= 15:
        verdict = "重仓"
        position_note = "科研转化评分≥15，可重仓"
    elif total >= 10:
        verdict = "观察"
        position_note = "科研转化评分10~14，部分不达标，观察仓（单只上限≤5%），不重仓"
    else:
        verdict = "放弃"
        position_note = "科研转化评分<10，放弃"

    score_breakdown: Dict[str, Dict[str, Any]] = {
        "rd_input": {
            "score": rd_input_score,
            "max": RESEARCH_DIMENSIONS["rd_input"]["max"],
            "items": rd_input_items,
        },
        "rd_output": {
            "score": rd_output_score,
            "max": RESEARCH_DIMENSIONS["rd_output"]["max"],
            "items": rd_output_items,
        },
        "capital_return": {
            "score": capital_return_score,
            "max": RESEARCH_DIMENSIONS["capital_return"]["max"],
            "items": capital_return_items,
        },
    }

    return {
        "task": "research",
        "total": total,
        "verdict": verdict,
        "position_note": position_note,
        "score_breakdown": score_breakdown,
        "warning": warnings,
        "data_as_of": as_of,
        "time_sensitivity_note": RESEARCH_TIME_SENSITIVITY_NOTE,
        "note": RESEARCH_NOTE,
        "source": RESEARCH_SOURCE,
        "input": input_payload,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_management(args: argparse.Namespace) -> int:
    """执行 ``management`` 子命令：单次管理层评分并打印 JSON，非法输入返回非零。

    Args:
        args: argparse 解析后的命名空间。

    Returns:
        int: 退出码（0 成功，1 输入非法）。
    """
    try:
        result = build_governance_result(
            fulfillment_rate=args.fulfillment_rate,
            guidance_misstatement=args.guidance_misstatement,
            attribution_habit=args.attribution_habit,
            regulatory_filing=args.regulatory_filing,
            financial_fraud=args.financial_fraud,
            dividend_payout_ratio=args.dividend_payout_ratio,
            financing=args.financing,
            buyback=args.buyback,
            pledge_ratio=args.pledge_ratio,
            core_focus=args.core_focus,
            strategy_exec=args.strategy_exec,
            industry_cog=args.industry_cog,
            turnover_rate=args.turnover_rate,
            equity_incentive=args.equity_incentive,
            insider_abnormal=args.insider_abnormal,
            as_of=args.as_of,
        )
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_research(args: argparse.Namespace) -> int:
    """执行 ``research`` 子命令：单次科研转化评分并打印 JSON，非法输入返回非零。

    Args:
        args: argparse 解析后的命名空间。

    Returns:
        int: 退出码（0 成功，1 输入非法）。
    """
    try:
        result = build_research_result(
            rd_intensity=args.rd_intensity,
            rd_intensity_rising=args.rd_intensity_rising,
            capitalization_rate=args.capitalization_rate,
            rd_personnel_ratio=args.rd_personnel_ratio,
            patent_quality=args.patent_quality,
            new_product_revenue_ratio=args.new_product_revenue_ratio,
            commercialization_cycle=args.commercialization_cycle,
            project_milestone=args.project_milestone,
            roic=args.roic,
            wacc=args.wacc,
            incremental_roic=args.incremental_roic,
            as_of=args.as_of,
        )
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_esg_result(
    *,
    env_risk_level: str,
    transition_pathway: str = "无",
    stranded_asset: bool = False,
    esg_tail: bool = False,
    position_cap_base: Optional[float] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """对单个 ESG 环境风险折价输入执行三通道确定性计算。

    判定顺序固定（无评分制、无诚信否决、无 verdict）：
    1. 校验环境风险等级（必填，高/低）与转型路径（明确/无，缺省无）；
       校验仓位上限基线（0~100，缺省 20.0）。
    2. 通道一：依 ``DISCOUNT_TABLE`` 取基础折价系数，搁浅资产命中时再减
       ``STRANDED_EXTRA_DISCOUNT`` 且下限 ``DISCOUNT_FLOOR``，得出
       ``discount_factor`` 与 ``discount_pct``。
    3. 通道二：搁浅资产命中 -> ``discount_rate_adj_bps=150`` 并回显区间
       ``[100, 200]``；未命中 -> 0 与空区间。
    4. 通道三：高环境风险 或 评级尾部 任一命中 -> ``position_cap_downgrade=5.0``，
       叠加不重复；否则 0。据此算 ``position_cap_after``。

    Args:
        env_risk_level: 环境风险等级（高/低，必填）。
        transition_pathway: 转型路径（明确/无，可选，默认 无）。
        stranded_asset: 是否面临搁浅资产风险（可选，默认 False）。
        esg_tail: ESG 评级是否处于行业尾部/最低档（可选，默认 False）。
        position_cap_base: 单只仓位上限基线（%，0~100；可选，默认 20.0）。
        as_of: 数据截止日期（可选，仅透传，不参与判定）。

    Returns:
        Dict[str, Any]: §3.3 顶层输出对象（含三通道折价字段与时效/口径标注）。

    Raises:
        ValueError: 环境风险等级/转型路径非法，或仓位上限基线越界/非数值。
    """
    input_payload: Dict[str, Any] = {
        "env_risk_level": env_risk_level,
        "transition_pathway": transition_pathway,
        "stranded_asset": bool(stranded_asset),
        "esg_tail": bool(esg_tail),
        "position_cap_base": position_cap_base
        if position_cap_base is not None else POSITION_CAP_BASE_DEFAULT,
        "as_of": as_of,
    }

    # 步骤①：档位与数值校验（fail-fast）。
    env = _validate_enum(env_risk_level, "环境风险等级", ENV_RISK_VALUES)
    pathway = _validate_enum(transition_pathway, "转型路径", TRANSITION_VALUES)
    cap_base = _parse_rate(
        position_cap_base if position_cap_base is not None
        else POSITION_CAP_BASE_DEFAULT,
        "仓位上限基线",
    )

    # 步骤②：通道一——估值折价系数。
    base_factor = DISCOUNT_TABLE[(env, pathway)]
    if stranded_asset:
        discount_factor = round(
            max(DISCOUNT_FLOOR, base_factor - STRANDED_EXTRA_DISCOUNT), 2)
    else:
        discount_factor = round(base_factor, 2)
    discount_pct = round((1.0 - discount_factor) * 100.0, 2)
    discount_range = DISCOUNT_RANGE_NOTE if env == "高" else None

    # 步骤③：通道二——搁浅资产贴现率上调。
    if stranded_asset:
        discount_rate_adj_bps = DISCOUNT_RATE_ADJ_BPS
        discount_rate_adj_range_bps = list(DISCOUNT_RATE_ADJ_RANGE_BPS)
    else:
        discount_rate_adj_bps = 0
        discount_rate_adj_range_bps = []

    # 步骤④：通道三——仓位上限下调（高环境风险 或 评级尾部 任一命中，不叠加）。
    if env == "高" or esg_tail:
        position_cap_downgrade = POSITION_CAP_DOWNGRADE_PCT
    else:
        position_cap_downgrade = 0.0
    position_cap_after = round(cap_base - position_cap_downgrade, 2)

    return {
        "task": "esg",
        "discount_factor": discount_factor,
        "discount_pct": discount_pct,
        "discount_range": discount_range,
        "discount_rate_adj_bps": discount_rate_adj_bps,
        "discount_rate_adj_range_bps": discount_rate_adj_range_bps,
        "position_cap_base": round(cap_base, 2),
        "position_cap_after": position_cap_after,
        "position_cap_downgrade": position_cap_downgrade,
        "esg_tail_triggered": bool(esg_tail),
        "stranded_asset_triggered": bool(stranded_asset),
        "env_risk_level": env,
        "transition_pathway": pathway,
        "data_as_of": as_of,
        "time_sensitivity_note": ESG_TIME_SENSITIVITY_NOTE,
        "note": ESG_NOTE,
        "source": ESG_SOURCE,
        "input": input_payload,
    }


def cmd_esg(args: argparse.Namespace) -> int:
    """执行 ``esg`` 子命令：单次 ESG 折价计算并打印 JSON，非法输入返回非零。

    Args:
        args: argparse 解析后的命名空间。

    Returns:
        int: 退出码（0 成功，1 输入非法）。
    """
    try:
        result = build_esg_result(
            env_risk_level=args.env_risk_level,
            transition_pathway=args.transition_pathway,
            stranded_asset=args.stranded_asset,
            esg_tail=args.esg_tail,
            position_cap_base=args.position_cap_base,
            as_of=args.as_of,
        )
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="治理数据评分工具：管理层 20 分制（诚信前置 + 7+7+6）"
                    " + 科研转化 20 分制（8+8+4）"
                    " + ESG 环境风险折价（第4步）"
                    "（框架第3步·支柱三 + 第4步）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.replace("{py}", "python"),
    )
    sub = parser.add_subparsers(dest="command")

    mp = sub.add_parser(
        "management", help="单次管理层评分（诚信前置 + 7+7+6，输出 JSON）")

    # 诚信否决闸门（兑现率为可选数值，其余为布尔标志）。
    mp.add_argument("--fulfillment-rate", type=float, default=None,
                    help="年报承诺兑现率（%%，0~100），<50 一票否决")
    mp.add_argument("--guidance-misstatement", action="store_true",
                    help="业绩预告重大失真（命中即否决）")
    mp.add_argument("--attribution-habit", action="store_true",
                    help="归因习惯异常（命中即否决）")
    mp.add_argument("--regulatory-filing", action="store_true",
                    help="监管立案（命中即否决）")
    mp.add_argument("--financial-fraud", action="store_true",
                    help="财务造假实锤（命中即否决）")

    # 对待股东（7 分）。
    mp.add_argument("--dividend-payout-ratio", type=float, default=None,
                    help="分红率（%%，0~100）")
    mp.add_argument("--financing", default=None,
                    help="融资记录：优/中/差")
    mp.add_argument("--buyback", default=None,
                    help="回购行为：优/中/差")
    mp.add_argument("--pledge-ratio", type=float, default=None,
                    help="大股东质押率（%%，0~100）")

    # 战略执行力（7 分）。
    mp.add_argument("--core-focus", default=None,
                    help="聚焦主业：优/中/差")
    mp.add_argument("--strategy-exec", default=None,
                    help="核心战略落地：优/中/差")
    mp.add_argument("--industry-cog", default=None,
                    help="行业格局认知深度：优/中/差")

    # 稳定性与激励（6 分）。
    mp.add_argument("--turnover-rate", type=float, default=None,
                    help="核心团队离职率（%%，0~100）")
    mp.add_argument("--equity-incentive", default=None,
                    help="股权激励合理性：优/中/差")
    mp.add_argument("--insider-abnormal", action="store_true",
                    help="内部人增减持异常（存在异常 → 预警扣分）")

    # 时效。
    mp.add_argument("--as-of", default=None,
                    help="评分数据截止日期（可选，仅透传）")

    rp = sub.add_parser(
        "research", help="单次科研转化评分（8+8+4，输出 JSON，无诚信否决）")

    # 研发投入（8 分）。
    rp.add_argument("--rd-intensity", type=float, default=None,
                    help="研发强度（%%，0~100）")
    rp.add_argument("--rd-intensity-rising", action="store_true",
                    help="研发强度逐年提升（命中加档）")
    rp.add_argument("--capitalization-rate", type=float, default=None,
                    help="研发支出资本化率（%%，0~100）")
    rp.add_argument("--rd-personnel-ratio", type=float, default=None,
                    help="研发人员占比（%%，0~100）")

    # 研发产出（8 分）。
    rp.add_argument("--patent-quality", default=None,
                    help="发明专利数量与质量：优/中/差")
    rp.add_argument("--new-product-revenue-ratio", type=float, default=None,
                    help="新产品收入占比（%%，0~100）")
    rp.add_argument("--commercialization-cycle", default=None,
                    help="技术产品化周期：优/中/差")
    rp.add_argument("--project-milestone", default=None,
                    help="重大科研项目节点推进：优/中/差")

    # 资本回报（4 分，数值透传引用 P1-1/P1-2/P1-3）。
    rp.add_argument("--roic", type=float, default=None,
                    help="存量 ROIC（%%，可为负，透传自 P1-1 roic）")
    rp.add_argument("--wacc", type=float, default=None,
                    help="WACC（%%，透传自 P1-3 wacc）")
    rp.add_argument("--incremental-roic", type=float, default=None,
                    help="增量 ROIC（%%，可为负，透传自 P1-2 incremental-roic）")

    # 时效。
    rp.add_argument("--as-of", default=None,
                    help="评分数据截止日期（可选，仅透传）")

    ep = sub.add_parser(
        "esg", help="单次 ESG 环境风险折价（三通道修正量，输出 JSON）")

    ep.add_argument("--env-risk-level", required=True,
                    help="环境风险等级：高/低（必填）")
    ep.add_argument("--transition-pathway", default="无",
                    help="转型路径：明确/无（缺省 无）")
    ep.add_argument("--stranded-asset", action="store_true",
                    help="是否面临搁浅资产风险（命中贴现率上调）")
    ep.add_argument("--esg-tail", action="store_true",
                    help="ESG 评级是否处于行业尾部/最低档（命中降仓位）")
    ep.add_argument("--position-cap-base", type=float, default=None,
                    help="单只仓位上限基线（%%，0~100，缺省 20）")
    ep.add_argument("--as-of", default=None,
                    help="数据截止日期（可选，仅透传）")

    args = parser.parse_args()

    if args.command == "management":
        return cmd_management(args)

    if args.command == "research":
        return cmd_research(args)

    if args.command == "esg":
        return cmd_esg(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())