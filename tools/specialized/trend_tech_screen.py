#!/usr/bin/env python3
"""景气趋势筛选（trend-tech-screen）打分引擎骨架。

融合四位投资大师思想（欧奈尔 CAN SLIM / 林奇 GARP / 郑希全球景气 / 李进产业验证），
实现五维加权打分（满分 100 + 奖励分）+ 地缘政治二维修正（乘数系数）+ 技术面止损校验
（独立否决）+ 评级映射 + 反证清单。

本引擎为"聚合与计算层"（计入项目"禁止 LLM 心算"规范的核心中枢）：
- 输入：各维度的指标得分（由上游 A–F 工具与年报解析器产出），地缘二维评估，技术面数据。
- 输出：结构化 JSON（逐项得分、加权总分、地缘修正后得分、最终评级、反证清单）+ Markdown 报告。

骨架阶段阈值硬编码自技能文件（`research/quality-screen/trend-tech-screen.md技能文件完整修改建议.md`），
后续阶段可改为从技能文件动态读取。

用法（示例）:
    {py} tools/specialized/trend_tech_screen.py score \\
        --name A --cycle 需求爆发期 \\
        --dims '{"a":40,"b":27,"c":13,"d":17,"e":4}' \\
        --geo '{"x":"高","y":"高"}' \\
        --tech '{"close_above_ma200":true,"close_above_ma50":true,"volume_above_1_5x":false}' \\
        --r8 '{"商业化确定性":2,"市场空间":2,"外部背书":2,"专利验证":1,"管理层一致性":1}'

    // 批量两轮计算（行业景气一致性 ±2 分）
    {py} tools/specialized/trend_tech_screen.py batch --input companies.json --cycle 需求爆发期
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# 周期权重配置（含配对制调整，默认"需求爆发期"）
# ---------------------------------------------------------------------------

#: 五维满分（按周期阶段调整权重，①景气②研发③人才④动量⑤估值）
CYCLE_WEIGHTS: Dict[str, Dict[str, int]] = {
    "需求爆发期": {"a": 42, "b": 18, "c": 15, "d": 15, "e": 10},
    "技术跃迁期": {"a": 28, "b": 32, "c": 15, "d": 15, "e": 10},
    "成熟稳定期": {"a": 35, "b": 25, "c": 15, "d": 15, "e": 15},
    "供给受限期": {"a": 35, "b": 25, "c": 15, "d": 15, "e": 10},
}
DEFAULT_CYCLE: str = "需求爆发期"

# 维度中文名（用于输出）
DIM_KEY_CN = {"a": "①景气前瞻", "b": "②研发转化", "c": "③人才密度", "d": "④动量共识", "e": "⑤估值安全垫"}

# ---------------------------------------------------------------------------
# 地缘政治二维修正矩阵（X 国产化率 × Y 海外对冲）
# ---------------------------------------------------------------------------

#: 修正系数 = 国产化率等级[X] × 海外对冲等级[Y]
GEO_FACTOR: Dict[str, Dict[str, float]] = {
    "高": {"高": 1.10, "中": 1.00, "低": 1.00},
    "中": {"高": 0.95, "中": 0.80, "低": 0.65},
    "低": {"高": 0.90, "中": 0.60, "低": 0.40},
}

# ---------------------------------------------------------------------------
# 评级映射
# ---------------------------------------------------------------------------

#: 评级阈值（≥80 S, 65-79 A, 50-64 B, <50 C）
RATING_TABLE: List[tuple] = [
    ("S", 80, "强烈买入"),
    ("A", 65, "配置"),
    ("B", 50, "观察/轻仓"),
    ("C", 0, "回避"),
]
RATING_ORDER = ["S", "A", "B", "C"]


def _rating_for(score: float) -> tuple:
    """根据最终得分映射评级。

    Args:
        score: 地缘修正后的最终得分。

    Returns:
        (等级, 中文描述) 二元组。
    """
    for grade, threshold, desc in RATING_TABLE:
        if score >= threshold:
            return grade, desc
    return "C", RATING_TABLE[-1][2]  # 兜底 C 级


def _desc_for_grade(grade: str) -> str:
    """根据评级代号返回中文描述。

    Args:
        grade: 评级代号（S/A/B/C）。

    Returns:
        str: 评级对应的中文描述。
    """
    for g, _, desc in RATING_TABLE:
        if g == grade:
            return desc
    return "回避"


def downgrade_rating(rating: str) -> str:
    """评级下调一级：S→A, A→B, B→C, C→C（不越过 C 级）。

    Args:
        rating: 当前评级代号。

    Returns:
        str: 下调一级后的评级代号。
    """
    idx = RATING_ORDER.index(rating) if rating in RATING_ORDER else len(RATING_ORDER) - 1
    return RATING_ORDER[min(idx + 1, len(RATING_ORDER) - 1)]


# ---------------------------------------------------------------------------
# R8：在研项目商业化潜力评分卡（科创企业必查，独立奖励分项）
# ---------------------------------------------------------------------------

#: R8 满分（满分 10 分，因各维度允许负分故不设下限）
R8_MAX_SCORE: float = 10.0

#: R8 五维子项（键名与技能评分卡一致）
R8_COMPONENTS: List[str] = [
    "商业化确定性",  # 4 分：客户验证/小批量/最后验证阶段等
    "市场空间",      # 2 分：面向千亿/百亿/细分市场
    "外部背书",      # 2 分：国家重点研发计划/政府资助
    "专利验证",      # 1 分：对应领域专利授权或在审
    "管理层一致性",  # 1 分：管理层是否公开强调为第一优先级
]


def parse_r8(raw: Optional[Dict]) -> Dict[str, float]:
    """解析 R8 输入，返回标准化后的五项子分数。

    --r8 接受五项中文键的 JSON（如 {"商业化确定性":2,"市场空间":2,...}）。
    缺失键或非法值按 0 分处理。

    Args:
        raw: R8 原始输入 dict（可为 None）。

    Returns:
        dict: 标准化后的五维子分数 dict。
    """
    if not raw:
        return {}
    out: Dict[str, float] = {}
    for key in R8_COMPONENTS:
        try:
            out[key] = float(raw.get(key, 0.0))
        except (TypeError, ValueError):
            out[key] = 0.0
    return out


def r8_eval(components: Dict[str, float]) -> Dict:
    """根据 R8 子分数计算总分、奖励分、风险警告。

    使用规则（技能文件口径）：
    - 总分 >= 8 → 额外 +5 分奖励
    - 6 <= 总分 < 8 → 额外 +3 分奖励
    - 总分 < 0 → 触发在研项目风险警告，评级下调一级

    Args:
        components: R8 五项子分数 dict（可为空）。

    Returns:
        dict: {score, bonus, risk, verdict, note}。
    """
    if not components:
        return {"score": 0.0, "bonus": 0.0, "risk": False, "verdict": "none", "note": ""}
    score = sum(components.values())
    if score >= 8:
        bonus, verdict, note = 5.0, "high", "R8 ≥ 8 分：在研项目商业化潜力极强，额外 +5 分奖励"
    elif score >= 6:
        bonus, verdict, note = 3.0, "mid", "R8 6-8 分：在研项目商业化潜力较强，额外 +3 分奖励"
    else:
        bonus, verdict, note = 0.0, "none", ""
    risk = score < 0.0
    if risk:
        note = (note + "；" if note else "") + "R8 < 0 分：触发在研项目风险警告，评级下调一级"
    return {"score": score, "bonus": bonus, "risk": risk, "verdict": verdict, "note": note}


# ---------------------------------------------------------------------------
# 反证清单模板（S/A 级公司专属，动态调仓 + 欧奈尔技术面纪律）
# ---------------------------------------------------------------------------

#: 反证清单模板字段：指标、反证阈值、验证频率、对应大师
COUNTER_ARGUMENT_TEMPLATE: List[dict] = [
    {"indicator": "季度订单增速", "threshold": "连续两个季度 < 20%", "frequency": "每季", "master": "李进"},
    {"indicator": "毛利率", "threshold": "单季跌破 35%", "frequency": "每季", "master": "郑希"},
    {"indicator": "核心团队", "threshold": "任一核心技术人员离职", "frequency": "即时", "master": "郑希"},
    {"indicator": "国产化率进展", "threshold": "连续两季度无进展公告", "frequency": "每季", "master": "郑希"},
    {"indicator": "在研项目商业化潜力(R8)", "threshold": "连续两季无项目进展、R8 跌至 < 0（触发风险降级）", "frequency": "每季", "master": "郑希+李进"},
    {"indicator": "SMR 相对强度", "threshold": "跌破 60% 分位", "frequency": "每月", "master": "欧奈尔"},
    {"indicator": "技术面", "threshold": "跌破 50 日线且放量→降B；跌破 200 日线→清仓", "frequency": "每周", "master": "欧奈尔"},
    {"indicator": "机构覆盖度", "threshold": "连续两季机构减持 > 10%", "frequency": "每季", "master": "欧奈尔"},
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class GeoEval:
    """地缘二维评估：X 国产化率等级、Y 海外对冲有效性等级。"""
    x: str  # 高 / 中 / 低
    y: str  # 高 / 中 / 低


@dataclass
class TechData:
    """技术面数据（用于欧奈尔止损校验，独立否决项）。

    close_above_ma200: 现价是否在 200 日均线上方。
    close_above_ma50: 现价是否在 50 日均线上方。
    volume_above_15x: 当日成交量是否高于均值 1.5 倍（配合破 50 日线判定放量）。
    """
    close_above_ma200: bool = True
    close_above_ma50: bool = True
    volume_above_15x: bool = False


@dataclass
class CompanyResult:
    """单家公司打分结果。"""
    name: str
    cycle: str
    dims: Dict[str, float]
    dims_max: Dict[str, int]
    base_total: float
    geo_factor: float
    final_score: float
    rating: str
    rating_desc: str
    tech_verdict: str  # pass / warning / red
    notes: List[str] = field(default_factory=list)
    counter_arguments: List[dict] = field(default_factory=list)
    # R8：在研项目商业化潜力评分（科创企业必查，独立奖励分项）
    r8_components: Dict[str, float] = field(default_factory=dict)
    r8_score: float = 0.0
    r8_bonus: float = 0.0
    r8_risk: bool = False
    r8_verdict: str = "none"
    r8_max: float = R8_MAX_SCORE


# ---------------------------------------------------------------------------
# 核心计算
# ---------------------------------------------------------------------------

def tech_check(tech: TechData) -> str:
    """执行欧奈尔技术面止损校验（独立否决项）。

    优先级最高，仅对 S/A 级临时评级公司执行：
    - 破 200 日均线 → 红牌（red）：直接清仓/移出关注池，评级强制 C。
    - 破 50 日均线 + 放量 → 预警（warning）：评级降至 B。
    - 否则 → 通过（pass），不改变评级。

    Args:
        tech: 技术面数据。

    Returns:
        'red' / 'warning' / 'pass'。
    """
    if not tech.close_above_ma200:
        return "red"
    if not tech.close_above_ma50 and tech.volume_above_15x:
        return "warning"
    return "pass"


def score_company(name: str, dims: Dict[str, float], geo: GeoEval, tech: Optional[TechData],
                  cycle: str = DEFAULT_CYCLE, r8: Optional[Dict] = None) -> CompanyResult:
    """对单家公司执行五维打分 + 地缘修正 + 技术面否决 + R8 修正 + 评级。

    Args:
        name: 公司名称。
        dims: 五维维度得分 dict（键 a/b/c/d/e，值为含奖励分后的维度得分）。
        geo: 地缘二维评估（X 国产化率 / Y 海外对冲）。
        tech: 技术面数据（可为 None，缺失则不进行否决）。
        cycle: 产业链周期阶段，用于选择权重（默认"需求爆发期"）。
        r8: 在研项目商业化潜力评分（R8 五项子分数 dict，可为 None）。

    Returns:
        CompanyResult：完整打分结果。

    Raises:
        ValueError: cycle 非法或 dims 缺关键维度时抛出。
    """
    if cycle not in CYCLE_WEIGHTS:
        raise ValueError(f"未知周期阶段: {cycle}，可选 {list(CYCLE_WEIGHTS.keys())}")

    weights = CYCLE_WEIGHTS[cycle]
    clean: Dict[str, float] = {}
    notes: List[str] = []

    # 维度得分含奖励分，直接相加（技能文件口径：奖励分并入维度得分后累加）。
    # 仅对负数钳制为 0，不截断到周期上限，避免奖励分被错误删除。
    for key, max_score in weights.items():
        raw = dims.get(key)
        if raw is None:
            clean[key] = 0.0
            notes.append(f"{DIM_KEY_CN[key]} 数据缺失，按 0 分处理，不阻断打分")
        else:
            if float(raw) > max_score:
                notes.append(f"{DIM_KEY_CN[key]} 得分 {raw} > 周期上限 {max_score}（可能含奖励分），视为有效未截断")
            clean[key] = max(0.0, float(raw))

    base_total = sum(clean.values())

    # 在研项目商业化潜力评分（R8，独立奖励分项）：奖励分计入加权基础分
    r8_components = parse_r8(r8)
    r8_info = r8_eval(r8_components)
    r8_bonus = r8_info["bonus"]
    if r8_info["note"]:
        notes.append(r8_info["note"])

    # 地缘修正系数
    geo_factor = GEO_FACTOR.get(geo.x, {}).get(geo.y, 1.0)
    final_score = (base_total + r8_bonus) * geo_factor

    temp_grade, temp_desc = _rating_for(final_score)

    # 技术面否决（仅对临时评级 S/A 执行）
    tech_verdict = "pass"
    rating, rating_desc = temp_grade, temp_desc
    if tech is not None and temp_grade in ("S", "A"):
        tech_verdict = tech_check(tech)
        if tech_verdict == "red":
            rating, rating_desc = "C", "回避（技术面红牌：跌破 200 日均线，强制降级/清仓）"
            notes.append("技术面红牌：已跌破 200 日均线，最高优先级即时生效")
        elif tech_verdict == "warning":
            rating, rating_desc = "B", "观察/轻仓（技术面预警：跌破 50 日均线且放量，降至 B）"
            notes.append("技术面预警：破 50 日均线且放量，评级降至 B")

    # R8 风险警告：得分 < 0 → 评级下调一级（技术面否决之后，仍服从"不越过 C 级"）
    if r8_info["risk"]:
        rating = downgrade_rating(rating)
        rating_desc = _desc_for_grade(rating)
        notes.append("在研项目风险警告：R8 < 0,评级下调一级")

    # 反证清单（仅 S/A/B 生成，C 级为空）
    counter_arguments = []
    if rating in ("S", "A", "B"):
        counter_arguments = [dict(row) for row in COUNTER_ARGUMENT_TEMPLATE]

    return CompanyResult(
        name=name, cycle=cycle, dims=clean, dims_max=dict(weights),
        base_total=base_total, geo_factor=geo_factor, final_score=final_score,
        rating=rating, rating_desc=rating_desc, tech_verdict=tech_verdict,
        notes=notes, counter_arguments=counter_arguments,
        r8_components=r8_components, r8_score=r8_info["score"], r8_bonus=r8_bonus,
        r8_risk=r8_info["risk"], r8_verdict=r8_info["verdict"],
    )


# ---------------------------------------------------------------------------
# 批量两轮计算（行业景气一致性 ±2 分）
# ---------------------------------------------------------------------------

def batch_score(companies: List[Dict], cycle: str = DEFAULT_CYCLE) -> Dict:
    """批量打分，先基础分，再按行业通过率做景气一致性修正。

    行业通过率 >60% 的行业，其公司集体 +2 分；<30% 则集体 -2 分。
    通过率按"基础地缘修正后评级 ≥ B"的口径统计。

    Args:
        companies: 公司输入列表，每项含 dims/geo/tech/name/industry/cycle。
        cycle: 默认周期（单项可覆盖）。

    Returns:
        dict: {results: [...], industry_pass_rates: {...}}。
    """
    results = []
    # 第一轮：基础分
    first = []
    for item in companies:
        r = score_company(
            item["name"], item.get("dims", {}),
            _parse_geo(item.get("geo")),
            _parse_tech(item.get("tech")),
            item.get("cycle", cycle),
            item.get("r8"))
        first.append({"item": item, "result": r})

    # 行业通过率修正（第二轮）
    passes: Dict[str, List[bool]] = {}
    for entry in first:
        ind = entry["item"].get("industry", "")
        passes.setdefault(ind, []).append(entry["result"].rating in ("S", "A", "B"))

    rate_map: Dict[str, float] = {}
    for ind, flags in passes.items():
        rate_map[ind] = sum(flags) / len(flags) * 100 if flags else 0.0

    # 第二轮：行业景气一致性 ±2 分，重算分数/评级（技术面否决保持最高优先级）
    for entry in first:
        ind = entry["item"].get("industry", "")
        rate = rate_map.get(ind, 0.0)
        r = entry["result"]
        adjust = 0.0
        if rate > 60:
            adjust = 2.0
        elif rate < 30:
            adjust = -2.0

        nl = list(r.notes)
        if adjust > 0:
            nl.append(f"行业景气一致性：本行业通过率 {rate:.0f}% > 60%，得分 +2")
        elif adjust < 0:
            nl.append(f"行业景气一致性：本行业通过率 {rate:.0f}% < 30%，得分 -2")

        new_base = r.base_total + adjust
        new_final = (new_base + r.r8_bonus) * r.geo_factor
        tech_verdict = r.tech_verdict

        # 技术面否决最高优先级固化评级
        if tech_verdict == "red":
            new_rating, new_desc = "C", "回避（技术面红牌，强制降级）"
        elif tech_verdict == "warning":
            grade, desc = _rating_for(new_final)
            new_rating, new_desc = ("B", "观察/轻仓（技术面预警）") if grade == "S" else (grade, desc)
        else:
            new_rating, new_desc = _rating_for(new_final)

        # R8 风险警告：得分 < 0 → 评级下调一级（第二轮需重放）
        if r.r8_risk:
            new_rating = downgrade_rating(new_rating)
            new_desc = _desc_for_grade(new_rating)
            if not any("在研项目风险警告" in n for n in nl):
                nl.append("在研项目风险警告：R8 < 0,评级下调一级")

        # 重新生成反证清单（仅 S/A/B）
        counter_arguments = [dict(row) for row in COUNTER_ARGUMENT_TEMPLATE] \
            if new_rating in ("S", "A", "B") else []

        r.base_total = new_base
        r.final_score = new_final
        r.rating, r.rating_desc = new_rating, new_desc
        r.notes = nl
        r.counter_arguments = counter_arguments

    # 返回明细（含行业通过率）
    out = []
    for entry in first:
        r = entry["result"]
        ind = entry["item"].get("industry", "")
        out.append({**asdict(r), "industry": ind, "industry_pass_rate": rate_map.get(ind, 0.0)})

    return {"results": out, "industry_pass_rates": rate_map}


# ---------------------------------------------------------------------------
# Markdown 报告生成
# ---------------------------------------------------------------------------

def build_markdown(r: CompanyResult, today: str) -> str:
    """生成单公司 Markdown 报告文本。

    Args:
        r: 公司打分结果。
        today: 当日日期字符串（YYYY-MM-DD）。

    Returns:
        str: Markdown 报告。
    """
    dim_rows = []
    for key in ("a", "b", "c", "d", "e"):
        dim_rows.append(
            f"| {DIM_KEY_CN[key]} | {r.dims[key]:.1f} | {r.dims_max[key]} |")
    dim_rows_block = "\n".join(dim_rows)

    tech_label = {"pass": "✅ 通过", "warning": "⚠️ 预警降级", "red": "🔴 红牌降级"}.get(r.tech_verdict, r.tech_verdict)

    counter_rows = "\n".join(
        f"| {c['indicator']} | {c['threshold']} | {c['frequency']} | {c['master']} |"
        for c in r.counter_arguments) if r.counter_arguments else "| C 级：不生成反证清单 |"

    notes = "\n".join(f"- {n}" for n in r.notes) if r.notes else "- 无"

    # R8 在研项目评分卡（科创企业必查；无输入则不渲染）
    r8_block = ""
    if r.r8_components:
        r8_rows = "\n".join(
            f"| {k} | {v:.1f} |" for k, v in r.r8_components.items())
        if r.r8_risk:
            verdict_line = "⚠️ R8 < 0：触发在研项目风险警告，评级下调一级"
        elif r.r8_verdict == "high":
            verdict_line = "⭐ R8 ≥ 8：商业化潜力极强，+5 分奖励"
        elif r.r8_verdict == "mid":
            verdict_line = "✅ R8 6-8：商业化潜力较强，+3 分奖励"
        else:
            verdict_line = f"中性：R8 {r.r8_score:.1f} 分，无额外奖励"
        r8_block = f"""\n### 在研项目评分卡（R8）

| 评估维度 | 得分 |
|---|---|
{r8_rows}

**R8 总分**：{r.r8_score:.1f} / {r.r8_max:.0f}
**R8 奖励分**：+{r.r8_bonus:.0f}
{verdict_line}
"""

    return f"""# 📈 景气趋势筛选报告（1-3年配置视角）

**筛选日期**：{today}
**适用框架**：trend-tech-screen（欧奈尔 CAN SLIM + 林奇 GARP + 郑希全球景气 + 李进产业验证）
**产业链周期定位**：{r.cycle}

## 公司：{r.name}

### 五维加权打分

| 维度 | 得分 | 周期上限 |
|---|---|---|
{dim_rows_block}

**加权总分（地缘修正前）**：{r.base_total:.1f} / {sum(r.dims_max.values())}
**地缘修正系数**：× {r.geo_factor:.2f}
**最终得分（地缘修正后）**：**{r.final_score:.1f}**
**{tech_label} | 最终评级：{r.rating} 级（{r.rating_desc}）**
{r8_block}
### 打分备注
{notes}

### 反证清单（{r.name}）
| 跟踪指标 | 反证阈值 | 验证频率 | 对应大师 |
|---|---|---|---|
{counter_rows}
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_geo(raw: dict) -> GeoEval:
    d = raw or {}
    return GeoEval(x=str(d.get("x", "高")), y=str(d.get("y", "高")))


def _parse_tech(raw: Optional[dict]) -> Optional[TechData]:
    if not raw:
        return None
    return TechData(
        close_above_ma200=bool(raw.get("close_above_ma200", True)),
        close_above_ma50=bool(raw.get("close_above_ma50", True)),
        volume_above_15x=bool(raw.get("volume_above_1_5x", False)),
    )


def _default_outdir() -> Path:
    return Path(os.environ.get("WORKSPACE_ROOT", Path(__file__).resolve().parent.parent.parent)) / "reports" / "trend-screen"


def cmd_score(args) -> int:
    """单公司打分命令."""
    dims = args.dims
    geo = _parse_geo(args.geo)
    tech = _parse_tech(args.tech)
    today = date.today().isoformat()

    try:
        result = score_company(args.name, dims, geo, tech, args.cycle, args.r8)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))

    if not args.markdown_only:
        result_json = asdict(result)
        result_json["date"] = today
        out_dir = _default_outdir()
        # 输出 JSON
        json_path = out_dir / f"{args.name}-trend-screen-{today.replace('-', '')}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(result_json, ensure_ascii=False, indent=2), encoding="utf-8")

        # 输出 Markdown
        md = build_markdown(result, today)
        md_path = out_dir / f"{args.name}-trend-screen-{today.replace('-', '')}.md"
        md_path.write_text(md, encoding="utf-8")
        print(f"\n报告已保存：\n  {json_path}\n  {md_path}")
        print(f"\n{md}")
    return 0


def cmd_batch(args) -> int:
    """批量打分命令（两轮：基础分 + 行业景气一致性修正）."""
    raw = json.loads(args.input) if isinstance(args.input, str) and args.input.lstrip().startswith("[") \
        else json.loads(Path(args.input).read_text(encoding="utf-8"))
    today = date.today().isoformat()

    if not isinstance(raw, list):
        print("❌ batch --input 需为公司数组 JSON 或指向 JSON 文件")
        return 1

    out = batch_score(raw, args.cycle)
    print(json.dumps(out, ensure_ascii=False, indent=2))

    out_dir = _default_outdir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out["date"] = today
    json_path = out_dir / f"batch-trend-screen-{today.replace('-', '')}.json"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n批量结果已保存：{json_path}")
    return 0


def main() -> int:
    """CLI 入口."""
    parser = argparse.ArgumentParser(
        description="景气趋势筛选打分引擎（trend-tech-screen）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.replace("{py}", "python"),
    )
    sub = parser.add_subparsers(dest="command")

    sc = sub.add_parser("score", help="单公司五维打分")
    sc.add_argument("--name", required=True, help="公司名称")
    sc.add_argument("--cycle", default=DEFAULT_CYCLE,
                    help=f"产业链周期（默认 {DEFAULT_CYCLE}）")
    sc.add_argument("--dims", required=True,
                    help="JSON: 五维得分 {\"a\":.., \"b\":.., \"c\":.., \"d\":.., \"e\":..}")
    sc.add_argument("--geo", required=True, help="JSON: {\"x\":\"高/中/低\",\"y\":\"高/中/低\"}")
    sc.add_argument("--tech", default=None,
                    help="JSON: {\"close_above_ma200\":bool,\"close_above_ma50\":bool,\"volume_above_1_5x\":bool}")
    sc.add_argument("--r8", default=None,
                    help="JSON: R8 在研项目商业化潜力五子分数（科创企业必查），如 {\"商业化确定性\":2,\"市场空间\":2,\"外部背书\":2,\"专利验证\":1,\"管理层一致性\":1}")
    sc.add_argument("--markdown-only", action="store_true", help="只打印不打分/不落盘")

    bt = sub.add_parser("batch", help="批量两轮打分（行业景气一致性）")
    bt.add_argument("--input", required=True,
                    help="公司数组 JSON 或 JSON 文件路径")
    bt.add_argument("--cycle", default=DEFAULT_CYCLE)

    args = parser.parse_args()

    if args.command == "score":
        args.dims = {k: float(v) for k, v in json.loads(args.dims).items()}
        args.geo = json.loads(args.geo)
        args.tech = json.loads(args.tech) if args.tech else None
        args.r8 = json.loads(args.r8) if args.r8 else None
        return cmd_score(args)
    if args.command == "batch":
        return cmd_batch(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())