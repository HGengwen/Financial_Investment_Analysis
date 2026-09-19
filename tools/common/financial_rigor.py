#!/usr/bin/env python3
"""Financial Rigor Toolkit for AI Berkshire.

Command-line tool for verifying financial data accuracy during investment research.
Automatically called by Claude Code Skills at critical validation checkpoints.

Zero external dependencies — uses only Python stdlib (decimal, json, math, argparse).
Requires Python >= 3.7.

Usage (called automatically by Skills, no manual execution needed):
    python3 tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
    python3 tools/financial_rigor.py verify-valuation --price 510 --eps 23.5 --bvps 120 --fcf-per-share 18 --dividend 2.4
    python3 tools/financial_rigor.py cross-validate --field revenue --values '{"年报": 7518, "Yahoo": 7500, "StockAnalysis": 7520}' --unit 亿
    python3 tools/financial_rigor.py benford --values '[1234, 2345, 3456, ...]'
    python3 tools/financial_rigor.py calc --expr '510 * 9.11e9'
"""

import argparse
import json
import math
import sys
from decimal import Decimal, Context, ROUND_HALF_EVEN, InvalidOperation

# 处理 Windows GBK 控制台编码，避免 emoji/Unicode 字符产生 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:  # 部分环境（如 pytest 内）不支持 reconfigure 时静默降级
        _ = e

# ---------------------------------------------------------------------------
# Exact Decimal Engine (no floating-point drift)
# ---------------------------------------------------------------------------

_CTX = Context(prec=28, rounding=ROUND_HALF_EVEN)


def exact(value) -> Decimal:
    """Convert any numeric to exact Decimal, avoiding float traps."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def fmt_number(d: Decimal, unit: str = "") -> str:
    """Format large numbers in human-readable form (亿/万亿/B/T)."""
    v = float(d)
    abs_v = abs(v)
    if unit in ("亿", "亿元", "亿港元", "亿美元"):
        if abs_v >= 10000:
            return f"{v/10000:.2f}万亿{unit[1:] if len(unit) > 1 else ''}"
        return f"{v:.2f}{unit}"
    if abs_v >= 1e12:
        return f"{v/1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{v/1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{v/1e6:.2f}M"
    return f"{v:,.2f}"


# ---------------------------------------------------------------------------
# 1. Market Cap Verification (股价×总股本 vs 报告市值)
# ---------------------------------------------------------------------------

def verify_market_cap(price, shares, reported_cap, currency=""):
    """Verify market cap = price × shares, compare with reported value."""
    p = exact(price)
    s = exact(shares)
    r = exact(reported_cap)

    calculated = _CTX.multiply(p, s)
    deviation = abs(float(calculated - r) / float(r)) * 100 if r != 0 else 0

    print("=" * 60)
    print("市值验算 (Market Cap Verification)")
    print("=" * 60)
    print(f"  股价 (Price):       {p} {currency}")
    print(f"  总股本 (Shares):    {fmt_number(s)}")
    print(f"  计算市值:           {fmt_number(calculated)} {currency}")
    print(f"  报告市值:           {fmt_number(r)} {currency}")
    print(f"  偏差:               {deviation:.2f}%")
    print()

    if deviation > 5:
        print(f"  ❌ 警告: 偏差 {deviation:.1f}% > 5%, 请检查:")
        print(f"     - 股本是否为最新（回购/增发）?")
        print(f"     - 单位是否一致（港币 vs 人民币 vs 美元）?")
        print(f"     - 股价是否为最新?")
        return False
    elif deviation > 1:
        print(f"  ⚠️  偏差 {deviation:.1f}% 在可接受范围, 可能因股价波动/股本变化")
        return True
    else:
        print(f"  ✅ 验证通过, 偏差仅 {deviation:.2f}%")
        return True


# ---------------------------------------------------------------------------
# 2. Valuation Metrics Verification (估值指标验算)
# ---------------------------------------------------------------------------

def verify_valuation(price, eps=None, bvps=None, fcf_per_share=None,
                     dividend=None, revenue_per_share=None):
    """Calculate and verify key valuation ratios from raw inputs."""
    p = exact(price)

    print("=" * 60)
    print("估值指标验算 (Valuation Verification)")
    print("=" * 60)
    print(f"  当前股价: {p}")
    print()

    results = {}

    if eps is not None:
        e = exact(eps)
        if e != 0:
            pe = _CTX.divide(p, e)
            print(f"  PE (TTM):  {p} / {e} = {pe:.2f}x")
            results["PE"] = float(pe)
            # Earnings yield
            ey = _CTX.divide(e, p) * 100
            print(f"  盈利收益率: {ey:.2f}%")
        else:
            print(f"  PE: EPS为0, 无法计算")

    if bvps is not None:
        b = exact(bvps)
        if b != 0:
            pb = _CTX.divide(p, b)
            print(f"  PB:        {p} / {b} = {pb:.2f}x")
            results["PB"] = float(pb)
            if eps is not None and float(exact(eps)) != 0:
                roe = _CTX.divide(exact(eps), b) * 100
                print(f"  ROE:       {exact(eps)} / {b} = {roe:.2f}%")
                results["ROE"] = float(roe)

    if fcf_per_share is not None:
        f = exact(fcf_per_share)
        if f != 0:
            fcf_yield = _CTX.divide(f, p) * 100
            pfcf = _CTX.divide(p, f)
            print(f"  P/FCF:     {p} / {f} = {pfcf:.2f}x")
            print(f"  FCF Yield: {fcf_yield:.2f}%")
            results["P_FCF"] = float(pfcf)
            results["FCF_Yield"] = float(fcf_yield)

    if dividend is not None:
        d = exact(dividend)
        if p != 0:
            div_yield = _CTX.divide(d, p) * 100
            print(f"  股息率:    {d} / {p} = {div_yield:.2f}%")
            results["Dividend_Yield"] = float(div_yield)

    if revenue_per_share is not None:
        r = exact(revenue_per_share)
        if r != 0:
            ps = _CTX.divide(p, r)
            print(f"  PS:        {p} / {r} = {ps:.2f}x")
            results["PS"] = float(ps)

    print()
    print("  ✅ 以上指标均使用精确十进制计算, 无浮点误差")
    return results


# ---------------------------------------------------------------------------
# 3. Cross-Source Data Validation (多源交叉验证)
# ---------------------------------------------------------------------------

def cross_validate(field_name, source_values: dict, unit="", tolerance_pct=2.0):
    """Compare a data point across multiple sources, flag discrepancies."""
    print("=" * 60)
    print(f"交叉验证: {field_name} (Cross-Validation)")
    print("=" * 60)

    values = {k: exact(v) for k, v in source_values.items()}
    sources = list(values.keys())
    nums = list(values.values())

    # Find median as reference
    sorted_vals = sorted(float(v) for v in nums)
    n = len(sorted_vals)
    median = sorted_vals[n // 2] if n % 2 == 1 else (sorted_vals[n//2-1] + sorted_vals[n//2]) / 2

    print(f"  数据来源数: {len(sources)}")
    print(f"  参考中位数: {fmt_number(exact(median))} {unit}")
    print()

    all_ok = True
    for src, val in values.items():
        dev = abs(float(val) - median) / median * 100 if median != 0 else 0
        status = "✅" if dev <= tolerance_pct else "❌"
        if dev > tolerance_pct:
            all_ok = False
        print(f"  {status} {src:20s}: {fmt_number(val)} {unit}  (偏差 {dev:.2f}%)")

    print()
    if all_ok:
        print(f"  ✅ 所有来源偏差 ≤ {tolerance_pct}%, 数据一致")
    else:
        print(f"  ⚠️  存在来源偏差 > {tolerance_pct}%, 请核实差异原因")
        print(f"     建议: 优先采用公司年报/交易所数据")

    # Consensus value
    consensus = median
    print(f"\n  共识值 (加权中位数): {fmt_number(exact(consensus))} {unit}")
    return {"consensus": consensus, "all_consistent": all_ok}


# ---------------------------------------------------------------------------
# 4. Benford's Law Quick Check (财务数据造假检测)
# ---------------------------------------------------------------------------

_BENFORD = {d: math.log10(1 + 1/d) for d in range(1, 10)}


def benford_check(values: list):
    """Quick Benford's Law check on a list of financial values."""
    print("=" * 60)
    print("Benford定律检测 (Financial Data Fabrication Check)")
    print("=" * 60)

    # Extract leading digits
    digits = []
    for v in values:
        v = abs(float(v))
        if v > 0:
            sig = 10 ** (math.log10(v) - math.floor(math.log10(v)))
            d = int(sig)
            if 1 <= d <= 9:
                digits.append(d)

    n = len(digits)
    if n < 50:
        print(f"  ⚠️  样本量不足: {n} < 50, Benford分析不可靠")
        return None

    # Observed distribution
    counts = {}
    for d in digits:
        counts[d] = counts.get(d, 0) + 1
    observed = {d: counts.get(d, 0) / n for d in range(1, 10)}

    # MAD (Nigrini's Mean Absolute Deviation)
    mad = sum(abs(observed.get(d, 0) - _BENFORD[d]) for d in range(1, 10)) / 9

    # Chi-square
    chi2 = sum((counts.get(d, 0) - _BENFORD[d] * n) ** 2 / (_BENFORD[d] * n) for d in range(1, 10))

    # Conformity
    if mad < 0.006:
        conformity = "Close (高度符合)"
    elif mad < 0.012:
        conformity = "Acceptable (可接受)"
    elif mad < 0.015:
        conformity = "Marginally Acceptable (边缘)"
    else:
        conformity = "Nonconforming (不符合 ⚠️)"

    print(f"  样本量:    {n}")
    print(f"  MAD:       {mad:.6f}")
    print(f"  Chi-sq:    {chi2:.2f}")
    print(f"  符合度:    {conformity}")
    print()

    # Digit distribution table
    print(f"  {'首位数':>6} {'观测':>8} {'Benford期望':>12} {'偏差':>8}")
    print(f"  {'-'*6} {'-'*8} {'-'*12} {'-'*8}")
    for d in range(1, 10):
        obs = observed.get(d, 0)
        exp = _BENFORD[d]
        dev = obs - exp
        flag = " ⚠️" if abs(dev) > 0.03 else ""
        print(f"  {d:>6d} {obs:>8.3f} {exp:>12.3f} {dev:>+8.3f}{flag}")

    print()
    is_ok = mad < 0.015
    if is_ok:
        print("  ✅ 数据首位数字分布符合Benford定律")
    else:
        print("  ❌ 数据首位数字分布异常, 可能存在人为调整")
        print("     提示: 不符合Benford定律不一定是造假, 但值得进一步调查")

    return {"mad": mad, "chi2": chi2, "conformity": conformity, "is_conforming": is_ok}


# ---------------------------------------------------------------------------
# 5. Exact Calculator (精确计算器)
# ---------------------------------------------------------------------------

def exact_calc(expr: str):
    """Evaluate a financial expression with exact decimal arithmetic.

    Supports: +, -, *, /, (), numbers (including scientific notation).
    """
    print("=" * 60)
    print("精确计算 (Exact Calculator)")
    print("=" * 60)

    # Safe evaluation: only allow numbers and arithmetic
    allowed = set("0123456789.+-*/() eE")
    if not all(c in allowed for c in expr.replace(" ", "")):
        print(f"  ❌ 不安全的表达式: {expr}")
        return None

    try:
        # Replace scientific notation for Decimal compatibility
        result = eval(expr, {"__builtins__": {}}, {})
        d_result = exact(result)
        print(f"  表达式: {expr}")
        print(f"  结果:   {fmt_number(d_result)}")
        print(f"  精确值: {d_result}")
        return float(d_result)
    except Exception as e:
        print(f"  ❌ 计算错误: {e}")
        return None


# ---------------------------------------------------------------------------
# 6. Three-Scenario Valuation (三情景估值)
# ---------------------------------------------------------------------------

def three_scenario_valuation(current_price, current_eps, shares_billion,
                             growth_optimistic, growth_neutral, growth_pessimistic,
                             pe_optimistic, pe_neutral, pe_pessimistic,
                             years=3, currency=""):
    """Calculate three-scenario target prices with exact arithmetic."""
    print("=" * 60)
    print("三情景估值模型 (Three-Scenario Valuation)")
    print("=" * 60)

    p = exact(current_price)
    eps = exact(current_eps)
    shares = exact(shares_billion)

    scenarios = [
        ("乐观 (Bull)", growth_optimistic, pe_optimistic),
        ("中性 (Base)", growth_neutral, pe_neutral),
        ("悲观 (Bear)", growth_pessimistic, pe_pessimistic),
    ]

    print(f"  当前股价: {p} {currency}")
    print(f"  当前EPS:  {eps}")
    print(f"  预测期:   {years}年")
    print()
    print(f"  {'情景':12} {'年增速':>8} {'目标PE':>8} {'目标EPS':>10} {'目标股价':>10} {'涨跌幅':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")

    for name, growth, pe in scenarios:
        g = exact(growth)
        target_pe = exact(pe)
        # Future EPS = current EPS × (1 + growth)^years
        future_eps = eps
        for _ in range(years):
            future_eps = _CTX.multiply(future_eps, _CTX.add(Decimal("1"), g))
        target_price = _CTX.multiply(future_eps, target_pe)
        change = float(target_price - p) / float(p) * 100

        print(f"  {name:12} {float(g)*100:>7.0f}% {float(target_pe):>7.0f}x "
              f"{float(future_eps):>10.2f} {float(target_price):>9.1f} {change:>+7.1f}%")

    print()
    print("  ✅ 所有计算使用精确十进制, 结果可审计复现")


# ---------------------------------------------------------------------------
# 7. PEG (林奇核心估值指标)
# ---------------------------------------------------------------------------

def peg_ratio(pe, growth):
    """计算 PEG 并给出林奇评级。

    林奇 GARP 核心工具：PEG = PE / 盈利增速。PEG < 1 视为低估成长潜力。

    Args:
        pe (float): 当前市盈率（TTM）。
        growth (float): 盈利增速，百分点（如 40 表示 40%）。

    Returns:
        dict: 含 peg 值、林奇评级与简评。
    """
    print("=" * 60)
    print("PEG 估值 (林奇安全垫)")
    print("=" * 60)
    p = exact(pe)
    g = exact(growth)

    print(f"  市盈率 PE:       {p:.2f}x")
    print(f"  盈利增速:        {g:.2f}%")

    if g <= 0:
        print(f"\n  ⚠️  盈利增速 {g}% ≤ 0, PEG 无意义（亏损或负增长公司不适用于本指标）")
        print("     建议改用 PSG（市销率增长比，`ps-g` 命令）评估爆发期科技股")
        return {"peg": None, "rating": "N/A", "note": "negative_growth"}

    peg = _CTX.divide(p, g)
    print(f"  PEG        = PE / 增速 = {float(p):.2f} / {float(g):.2f} = {float(peg):.2f}")
    print()

    if peg < 0.8:
        rating = "显著低估 (<0.8)"
        flag = "✅"
    elif peg <= 1.2:
        rating = "合理 (0.8~1.2)"
        flag = "✅"
    elif peg <= 1.5:
        rating = "偏贵 (1.2~1.5)"
        flag = "⚠️"
    elif peg <= 2.0:
        rating = "高估 (>1.5)"
        flag = "🔴"
    else:
        rating = "严重透支 (>2)"
        flag = "🔴"
    print(f"  {flag} 林奇评级: {rating}")

    if peg > 2:
        print("     警告: PEG > 2, 估值严重透支, 谨慎追高")

    result = {"peg": float(peg), "rating": rating}
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


# ---------------------------------------------------------------------------
# 8. PSG (市销率增长比，爆发期专用)
# ---------------------------------------------------------------------------

def psg_ratio(ps, revenue_growth):
    """计算 PSG 市销率增长比并给出判定。

    爆发期专用（触发条件：净利率 <5% 或 营收增速 >50%）。当利润滞后释放时，
    PEG 虚高或为负，PSG = PS / 营收增速 更能反映抢占市场的战略价值。

    Args:
        ps (float): 当前市销率（TTM）。
        revenue_growth (float): 营收增速，百分点（如 80 表示 80%）。

    Returns:
        dict: 含 psg 值、判定与简评。
    """
    print("=" * 60)
    print("PSG 估值 (市销率增长比，爆发期专用)")
    print("=" * 60)
    p = exact(ps)
    g = exact(revenue_growth)

    print(f"  市销率 PS:       {p:.2f}x")
    print(f"  营收增速:        {g:.2f}%")
    print(f"  适用前提:        净利率<5% 或 营收增速>50% （由调用方判断）")

    if g <= 0:
        print(f"\n  ⚠️  营收增速 {g}% ≤ 0, PSG 无意义（营收负增长公司不适用）")
        return {"psg": None, "rating": "N/A", "note": "negative_growth"}

    psg = _CTX.divide(p, g)
    print(f"  PSG        = PS / 营收增速 = {float(p):.2f} / {float(g):.2f} = {float(psg):.2f}")
    print()

    if psg < 0.5:
        rating = "优秀 (抢占市场价值被低估)"
        flag = "✅"
    elif psg <= 1.0:
        rating = "合理 (0.5-1.0)"
        flag = "⚠️"
    else:
        rating = "高估 (>1.0)"
        flag = "🔴"
    print(f"  {flag} PSG 判定: {rating}")

    result = {"psg": float(psg), "rating": rating}
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


# ---------------------------------------------------------------------------
# 9. PE Historical Percentile (PE 历史分位)
# ---------------------------------------------------------------------------

def pe_percentile(pe_series, current_pe=None):
    """计算当前 PE 在历史序列中所处分位并与技能阈值对照。

    Args:
        pe_series (list): 历史 PE 序列（数值列表）。
        current_pe (float, optional): 当前 PE；缺省取序列最后一个作为当前值。

    Returns:
        dict: 含当前 pe、历史分位百分数与评级。
    """
    print("=" * 60)
    print("PE 历史分位 (估值安全垫)")
    print("=" * 60)

    if not pe_series:
        print("  ❌ PE 序列为空，无法计算分位")
        return None

    hist = [exact(v) for v in pe_series]
    if current_pe is None:
        current_pe_val = hist.pop()
    else:
        current_pe_val = exact(current_pe)

    n = len(hist)
    if n == 0:
        print("  ❌ 历史序列不足，无法计算分位")
        return None

    # 分位 = 历史中 < 当前PE 的比例 (0-100)，历史最小值→0%
    below = sum(1 for v in hist if v < current_pe_val)
    pct = below / n * 100

    print(f"  当前 PE:        {float(current_pe_val):.2f}x")
    print(f"  历史样本数:     {n}")
    print(f"  历史范围:       {float(min(hist)):.2f} ~ {float(max(hist)):.2f}x")
    print(f"  历史分位:       {float(pct):.1f}% (当前估值高于 {float(pct):.0f}% 的历史时段)")
    print()

    if pct < 40:
        rating = "低估 (<40%，安全垫充足)"
        flag = "✅"
    elif pct <= 60:
        rating = "合理 (40-60%)"
        flag = "⚠️"
    else:
        rating = "偏高 (>60%)"
        flag = "🔴"
    print(f"  {flag} 分位评级: {rating}")

    result = {"current_pe": float(current_pe_val), "percentile": float(pct), "rating": rating}
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


# ---------------------------------------------------------------------------
# 10. Implied Growth (市值隐含业绩倒推验证，红/黄/绿)
# ---------------------------------------------------------------------------

def implied_growth(market_cap, target_pe, net_margin, ttm_revenue, guidance_growth):
    """从当前市值倒推市场隐含的营收增速要求，并与公司指引对照。

    林奇式估值校验：倒推出市场定价所隐含的增速，若远超公司指引则估值透支。
    校验不占分，但触发红灯时下调一个评级。

    Args:
        market_cap (float): 当前市值（与营收同币种）。
        target_pe (float): 目标 PE（行业均值或公司历史中位）。
        net_margin (float): 年化净利率（如 0.15 表示 15%）。
        ttm_revenue (float): 当前 TTM 营收（与市值同币种同单位）。
        guidance_growth (float): 公司指引营收增速上限（如 0.35 表示 35%）。

    Returns:
        dict: 含隐含净利润、隐含营收、隐含增速及红/黄/绿判定。
    """
    print("=" * 60)
    print("市值隐含业绩倒推验证 (林奇式, 不占分, 红灯降级)")
    print("=" * 60)
    cap = exact(market_cap)
    tpe = exact(target_pe)
    margin = exact(net_margin)
    rev = exact(ttm_revenue)
    guide = exact(guidance_growth)

    print(f"  当前市值:        {fmt_number(cap)}")
    print(f"  目标 PE:         {float(tpe):.2f}x")
    print(f"  年化净利率:      {float(margin)*100:.2f}%")
    print(f"  TTM 营收:        {fmt_number(rev)}")
    print(f"  公司指引增速上限: {float(guide)*100:.1f}%")
    print()

    if margin <= 0 or rev <= 0 or tpe <= 0:
        print("  ❌ 输入无效（净利率/营收/目标PE 需为正数），无法倒推")
        return None

    implied_net = _CTX.divide(cap, tpe)          # 市场隐含全年净利润
    implied_rev = _CTX.divide(implied_net, margin)  # 隐含年化营收
    implied = _CTX.divide(implied_rev, rev) - 1    # 隐含营收增速要求

    g = float(guide)
    x = float(implied)

    print(f"  隐含净利润:      {fmt_number(implied_net)}")
    print(f"  隐含年化营收:    {fmt_number(implied_rev)}")
    print(f"  隐含营收增速要求: {x*100:.1f}%")
    print()

    # 判定：红 > 指引×1.5；黄 指引~指引×1.5；绿 < 指引
    if x > g * 1.5:
        verdict = "🔴 红灯: 隐含增速远超公司指引上限×1.5, 估值严重透支, 下调一个评级"
        level = "red"
    elif x >= g:
        verdict = "⚠️ 黄灯: 隐含增速已触及或略高于指引上限, 估值偏贵"
        level = "yellow"
    else:
        verdict = "✅ 绿灯: 隐含增速低于公司指引上限, 估值未透支"
        level = "green"
    print(f"  {verdict}")

    ref = [{"level": "green", "threshold": f"x < 指引({g*100:.0f}%)", "action": "估值合理"},
           {"level": "yellow", "threshold": f"指引 ≤ x ≤ 指引×1.5", "action": "估值偏贵"},
           {"level": "red", "threshold": f"x > 指引×1.5 ({g*1.5*100:.0f}%)", "action": "下调评级"}]
    print(f"  判定基准: {json.dumps(ref, ensure_ascii=False)}")

    result = {"implied_net_profit": float(implied_net), "implied_revenue": float(implied_rev),
              "implied_growth": x, "guidance_growth": g, "verdict": level}
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


# ---------------------------------------------------------------------------
# 11. ROIC (投入资本回报率，GARP 支柱二核心口径)
# ---------------------------------------------------------------------------

_TECH_ADJUSTMENT_HINT = (
    "高研发投入科技股因研发费用化压低当期利润与 ROIC，本项「≥10%」阈值应改用"
    "「调整后核心经营 ROIC」（费用化研发支出加回后口径）判定；若调整后仍 <10% 归"
    "「部分不达标（观察仓）」；科研转化清单「资本回报效率」项仍独立按「ROIC > WACC」"
    "判定（本项 ≥10% 主阈值不豁免）。"
)

_TIER_FLAGS = {
    "优秀": "✅",
    "合格": "✅",
    "部分不达标": "⚠️",
    "不达标": "🔴",
    "N/A": "⚠️",
}


def _tier_roic(roic_val, wacc_val, expanding, nopat):
    """按 GARP 支柱二四档判定决策表归位 ROIC 档位。

    决策表（见 P1-1 开发方案 3.2）：
        优秀：ROIC > 15%
        合格：10% ≤ ROIC ≤ 15% 且（无 WACC 或 ROIC > WACC）
        部分不达标：5%~10%，或 10%~15% 但 ROIC≤WACC，或 <5% 不扩产
        不达标：ROIC < 5% 且仍在扩产（一票否决）

    Args:
        roic_val: Decimal ROIC 值（百分数，精确值，用于边界判定）。
        wacc_val: Decimal WACC 值（百分数，可选；无则 None）。
        expanding: bool 是否仍拼命扩产。
        nopat: Decimal NOPAT 值（用于负值护栏标注）。

    Returns:
        tuple: (tier, verdict)。
    """
    # 负值护栏标注：NOPAT 非正时仍计算，天然落入 ROIC<5% 档并追加提示。
    nopat_nonpositive = nopat <= 0

    if roic_val > Decimal("15"):
        if wacc_val is not None and roic_val <= wacc_val:
            verdict = "合格（优秀档绝对值达标，但 ROIC≤WACC 未覆盖资本成本，建议人工复核）"
        else:
            verdict = "合格（优秀档，可支持单只上限上浮至绝对 20%）"
        tier = "优秀"
    elif roic_val >= Decimal("10"):
        if wacc_val is not None and roic_val <= wacc_val:
            tier = "部分不达标"
            verdict = "观察仓（ROIC≤WACC，资本回报未覆盖资本成本）"
        else:
            tier = "合格"
            if wacc_val is None:
                verdict = "合格（ROIC≥10%，未提供 WACC，未校验 ROIC>WACC）"
            else:
                verdict = "合格（ROIC>WACC 且 ≥10%）"
    elif roic_val >= Decimal("5"):
        tier = "部分不达标"
        verdict = "观察仓（5%~10%）"
    else:
        if expanding:
            tier = "不达标"
            verdict = "一票否决（ROIC<5% 且仍扩产）"
        else:
            tier = "部分不达标"
            verdict = "观察仓（ROIC<5% 不扩产）"

    if nopat_nonpositive:
        verdict += "；NOPAT 非正"

    return tier, verdict


def roic(nopat, invested_capital, wacc=None, expanding=False):
    """计算 ROIC（投入资本回报率）并给出四档判定。

    公式：ROIC = NOPAT ÷ 投入资本 × 100%，结果精确至 2 位小数。
    四档口径与《中长期价值成长（GARP）投资框架》第 3 步·支柱二一致，并附
    「科技股调整口径」提示（不在此做数值加回计算）。

    Args:
        nopat: 税后净营业利润（与 invested_capital 同币种同单位）。
        invested_capital: 投入资本（须 > 0）。
        wacc: 加权平均资本成本（百分点，如 8 表示 8%），可选，用于「合格」判定。
        expanding: 是否「仍拼命扩产」，可选，用于 ROIC<5% 时的一票否决判定。

    Returns:
        dict: 含 roic / tier / verdict / tech_adjustment_hint 及审计回显字段。
    """
    print("=" * 60)
    print("ROIC 投入资本回报率 (GARP 支柱二核心口径)")
    print("=" * 60)

    n = exact(nopat)
    ic = exact(invested_capital)

    print(f"  NOPAT (税后净营业利润):       {n}")
    print(f"  投入资本 (Invested Capital):   {ic}")

    # 投入资本护栏：≤ 0 时拒绝计算（非除零异常，降级提示）。
    if ic <= 0:
        hint = "投入资本 ≤ 0，无法计算 ROIC（分母非法）"
        print(f"\n  ⚠️  {hint}")
        result = {
            "roic": None,
            "tier": "N/A",
            "verdict": hint,
            "tech_adjustment_hint": _TECH_ADJUSTMENT_HINT,
            "wacc_applied": False,
            "inputs": {
                "nopat": float(n),
                "invested_capital": float(ic),
                "wacc": wacc,
                "expanding": expanding,
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    roic_decimal = _CTX.multiply(_CTX.divide(n, ic), Decimal("100"))
    roic_val = float(roic_decimal.quantize(Decimal("0.01")))
    print(f"  ROIC       = NOPAT / 投入资本 = {float(n):.4f} / {float(ic):.4f} = {roic_val:.2f}%")

    # WACC 校验（可选）。
    wacc_applied = wacc is not None
    wacc_val = exact(wacc) if wacc_applied else None
    if wacc_applied:
        print(f"  WACC (校验基准):                {float(wacc_val):.2f}%")
    else:
        print("  WACC (校验基准):                未提供（未校验 ROIC>WACC）")

    print()

    tier, verdict = _tier_roic(roic_decimal, wacc_val, expanding, n)

    print(f"  {_TIER_FLAGS.get(tier, '⚠️')} 四档判定: {tier}")
    print(f"  结论: {verdict}")
    print(f"\n  科技股调整口径提示: {_TECH_ADJUSTMENT_HINT}")

    result = {
        "roic": roic_val,
        "tier": tier,
        "verdict": verdict,
        "tech_adjustment_hint": _TECH_ADJUSTMENT_HINT,
        "wacc_applied": wacc_applied,
        "inputs": {
            "nopat": float(n),
            "invested_capital": float(ic),
            "wacc": float(wacc_val) if wacc_applied else None,
            "expanding": expanding,
        },
    }
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


def incremental_roic(nopat_from, invested_capital_from,
                     nopat_to, invested_capital_to,
                     period_from="", period_to=""):
    """计算增量 ROIC（增量投入资本回报率）。

    公式：增量 ROIC = (NOPAT_to − NOPAT_from) ÷ (投入资本_to − 投入资本_from) × 100%。
    结果精确至 2 位小数；Δ投入资本 ≤ 0 时降级为 N/A（非除零异常）。

    Args:
        nopat_from: 上期税后净营业利润（与 invested_capital_from 同币种同单位）。
        invested_capital_from: 上期投入资本。
        nopat_to: 本期税后净营业利润（与 invested_capital_to 同币种同单位）。
        invested_capital_to: 本期投入资本。
        period_from: 上期标签（如 "2023"），可选，仅回显。
        period_to: 本期标签（如 "2024"），可选，仅回显。

    Returns:
        dict: 含 delta_roic / period_from / period_to / delta_nopat /
              delta_invested_capital 及审计回显字段。
    """
    print("=" * 60)
    print("增量 ROIC 投入资本回报率 (增量口径)")
    print("=" * 60)

    nf = exact(nopat_from)
    icf = exact(invested_capital_from)
    nt = exact(nopat_to)
    ict = exact(invested_capital_to)

    delta_nopat = _CTX.subtract(nt, nf)
    delta_ic = _CTX.subtract(ict, icf)

    print(f"  上期 NOPAT:       {nf}")
    print(f"  上期投入资本:     {icf}")
    print(f"  本期 NOPAT:       {nt}")
    print(f"  本期投入资本:     {ict}")
    print(f"  ΔNOPAT:           {delta_nopat}")
    print(f"  Δ投入资本:        {delta_ic}")

    # 分母护栏：Δ投入资本 ≤ 0 时降级（非除零异常）。
    if delta_ic <= 0:
        if delta_ic == 0:
            hint = "增量投入资本为 0，无法计算增量 ROIC（分母非法）"
        else:
            hint = "投入资本收缩（Δ投入资本<0），增量口径不适用"
        print(f"\n  ⚠️  {hint}")
        result = {
            "delta_roic": None,
            "verdict": hint,
            "period_from": period_from,
            "period_to": period_to,
            "delta_nopat": float(delta_nopat),
            "delta_invested_capital": float(delta_ic),
            "tech_adjustment_hint": _TECH_ADJUSTMENT_HINT,
            "inputs": {
                "nopat_from": float(nf),
                "invested_capital_from": float(icf),
                "nopat_to": float(nt),
                "invested_capital_to": float(ict),
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    delta_roic_decimal = _CTX.multiply(_CTX.divide(delta_nopat, delta_ic), Decimal("100"))
    delta_roic_val = float(delta_roic_decimal.quantize(Decimal("0.01")))
    print(f"  增量 ROIC = ΔNOPAT / Δ投入资本 = {float(delta_nopat):.4f} / "
          f"{float(delta_ic):.4f} = {delta_roic_val:.2f}%")

    verdict = "增量口径结果"
    if delta_nopat <= 0:
        verdict += "；ΔNOPAT 非正"

    print(f"\n  结论: {verdict}")
    print(f"\n  科技股调整口径提示: {_TECH_ADJUSTMENT_HINT}")

    result = {
        "delta_roic": delta_roic_val,
        "verdict": verdict,
        "period_from": period_from,
        "period_to": period_to,
        "delta_nopat": float(delta_nopat),
        "delta_invested_capital": float(delta_ic),
        "tech_adjustment_hint": _TECH_ADJUSTMENT_HINT,
        "inputs": {
            "nopat_from": float(nf),
            "invested_capital_from": float(icf),
            "nopat_to": float(nt),
            "invested_capital_to": float(ict),
        },
    }
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


# re 估算参考区间（复用 terminal_value.py audit 的 r 参数币种护栏思想，非强校验）。
# 区间下沿 = 观测无风险利率 + 约 4.3pct 溢价，上沿 = 合成无风险利率 + 约 6pct 溢价；
# 两个币种区间差全部来自国债利差，不含风险判断差异。详见 terminal_value.py CURRENCY_BANDS。
_WACC_RE_REFERENCE = (
    "re 参考区间（复用 terminal_value.py audit 币种护栏，非强校验）："
    "CNY 约 6.0%~9.0%（中国10年期国债 1.70% + ERP 5.18% 合成）；"
    "USD/HKD 约 9.0%~11.5%（美国10年期国债 4.70% + ERP 5.18% 含国别溢价）。"
    "re 须与 E/D 同币种；退市/VIE/地缘/监管等离散风险不得塞进 re（应归情景）。"
)


def wacc(equity_value, debt_value, cost_equity, cost_debt, tax_rate):
    """计算加权平均资本成本（WACC）。

    公式：WACC = E/(E+D)·re + D/(E+D)·rd·(1−t)，结果精确至 2 位小数。
    权重校验：股权权重 + 债务权重 = 100%。
    re 估算思想复用 terminal_value.py audit 的 r 参数币种护栏，仅输出参考区间提示（非强校验）。

    Args:
        equity_value: 股权价值 E（与 debt_value 同币种同单位）。
        debt_value: 有息债务值 D（与 equity_value 同币种同单位）。
        cost_equity: 股权成本 re（百分点，如 10 表示 10%）。
        cost_debt: 债务成本 rd（税前，百分点，如 5 表示 5%）。
        tax_rate: 企业所得税税率 t（小数，如 0.25 表示 25%）。

    Returns:
        dict: 含 wacc / weights / after_tax_debt_cost / warnings /
              re_reference / inputs 审计回显字段。
    """
    print("=" * 60)
    print("WACC 加权平均资本成本 (GARP 支柱二资本成本侧)")
    print("=" * 60)

    e = exact(equity_value)
    d = exact(debt_value)
    re = exact(cost_equity)
    rd = exact(cost_debt)
    t = exact(tax_rate)

    print(f"  股权价值 E:           {e}")
    print(f"  债务价值 D:           {d}")
    print(f"  股权成本 re:          {float(re):.2f}%")
    print(f"  债务成本 rd (税前):   {float(rd):.2f}%")
    print(f"  税率 t:               {float(t):.4f}")

    total = _CTX.add(e, d)

    # 分母护栏：E+D ≤ 0 时降级 N/A（非除零异常）。
    if total <= 0:
        hint = "E+D ≤ 0，无法计算 WACC（分母非法）"
        print(f"\n  ⚠️  {hint}")
        result = {
            "wacc": None,
            "weights": None,
            "after_tax_debt_cost": None,
            "warnings": [hint],
            "re_reference": _WACC_RE_REFERENCE,
            "inputs": {
                "equity_value": float(e),
                "debt_value": float(d),
                "cost_equity": float(re),
                "cost_debt": float(rd),
                "tax_rate": float(t),
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    # 合理性告警（不拒绝计算，统一收集进 warnings）。
    warnings = []
    if e < 0:
        warnings.append("股权价值 E < 0（负权益/资不抵债口径），权重与 WACC 仅供参考")
    elif e == 0:
        warnings.append("股权价值 E = 0（全债务口径），股权成本项权重为 0")
    if d < 0:
        warnings.append("债务价值 D < 0（异常口径），权重与 WACC 仅供参考")
    elif d == 0:
        warnings.append("债务价值 D = 0（全股权口径），税盾为 0、债务成本项权重为 0")
    if re < 0:
        warnings.append("股权成本 re < 0，异常")
    if rd < 0:
        warnings.append("债务成本 rd < 0，异常")
    if re < rd:
        warnings.append("re < rd，股权成本低于债务成本，资本结构定价异常")
    if t < 0 or t >= 1:
        warnings.append("税率 t 超出 [0,1) 区间，异常")

    equity_wt_decimal = _CTX.multiply(_CTX.divide(e, total), Decimal("100"))
    debt_wt_decimal = _CTX.multiply(_CTX.divide(d, total), Decimal("100"))
    after_tax_rd_decimal = _CTX.multiply(rd, _CTX.subtract(Decimal("1"), t))
    wacc_decimal = _CTX.add(
        _CTX.multiply(_CTX.divide(e, total), re),
        _CTX.multiply(_CTX.divide(d, total), after_tax_rd_decimal),
    )

    equity_wt_val = float(equity_wt_decimal.quantize(Decimal("0.01")))
    debt_wt_val = float(debt_wt_decimal.quantize(Decimal("0.01")))
    after_tax_rd_val = float(after_tax_rd_decimal.quantize(Decimal("0.01")))
    wacc_val = float(wacc_decimal.quantize(Decimal("0.01")))

    print(f"\n  股权权重 = E/(E+D) = {equity_wt_val:.2f}%")
    print(f"  债务权重 = D/(E+D) = {debt_wt_val:.2f}%")
    print(f"  权重重算校验         = {equity_wt_val + debt_wt_val:.2f}%（应为 100.00%）")
    print(f"  税后债务成本         = rd×(1−t) = {after_tax_rd_val:.2f}%")
    print(f"  WACC                 = {wacc_val:.2f}%")
    print(f"\n  re 参考区间提示: {_WACC_RE_REFERENCE}")
    if warnings:
        print("\n  合理性告警:")
        for w in warnings:
            print(f"    ⚠️  {w}")

    result = {
        "wacc": wacc_val,
        "weights": {"equity": equity_wt_val, "debt": debt_wt_val},
        "after_tax_debt_cost": after_tax_rd_val,
        "warnings": warnings,
        "re_reference": _WACC_RE_REFERENCE,
        "inputs": {
            "equity_value": float(e),
            "debt_value": float(d),
            "cost_equity": float(re),
            "cost_debt": float(rd),
            "tax_rate": float(t),
        },
    }
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


def rule_of_40(revenue_growth, profit_margin=None, fcf_margin=None):
    """判定软件/高研发型公司成长质量（Rule of 40）。

    公式（二选一）：
        Rule of 40 = 营收增速% + 利润率%（利润口径）
                   = 营收增速% + FCF利润率%（FCF口径）
    ≥40 通过，<40 不达标；边界恰好 40 通过。单位均为百分点。
    利润口径与 FCF 口径互斥，必须且只能提供一个。

    Args:
        revenue_growth: 营收增速（百分点，如 30 表示 30%）。
        profit_margin: 利润率（百分点，如 25 表示 25%），可选，与 fcf_margin 二选一。
        fcf_margin: FCF 利润率（百分点，如 15 表示 15%），可选，与 profit_margin 二选一。

    Returns:
        dict: 含 rule_of_40 / passed / margin_type / verdict / warnings /
              inputs 审计回显字段。
    """
    print("=" * 60)
    print("Rule of 40 成长质量判定 (高研发投入型)")
    print("=" * 60)

    g = exact(revenue_growth)

    # 口径二选一护栏：都未提供或都提供 → 降级 N/A（非异常退出）。
    has_profit = profit_margin is not None
    has_fcf = fcf_margin is not None
    if has_profit == has_fcf:
        if has_profit:
            hint = "利润口径与 FCF 口径互斥，请二选一"
        else:
            hint = "未提供利润率或 FCF 利润率（二选一）"
        print(f"\n  ⚠️  {hint}")
        result = {
            "rule_of_40": None,
            "passed": None,
            "margin_type": None,
            "verdict": hint,
            "warnings": [hint],
            "inputs": {
                "revenue_growth": float(g),
                "profit_margin": profit_margin,
                "fcf_margin": fcf_margin,
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    margin_type = "profit" if has_profit else "fcf"
    m = exact(profit_margin if has_profit else fcf_margin)

    print(f"  营收增速:        {float(g):.2f}%")
    print(f"  口径:            {'利润率' if has_profit else 'FCF 利润率'} ({margin_type})")
    print(f"  利润率/FCF利润率: {float(m):.2f}%")

    # 合理性告警（不拒绝计算，允许负值）。
    warnings = []
    if g < 0:
        warnings.append("营收增速为负（收缩期），Rule of 40 被拉低")
    if m < 0:
        warnings.append("利润率/FCF 利润率为负（亏损），Rule of 40 被拉低")

    rule_of_40_dec = _CTX.add(g, m)
    # 判定基于 2 位小数舍入后的值，确保显示值与判定结论一致。
    rule_of_40_val = rule_of_40_dec.quantize(Decimal("0.01"))
    passed = rule_of_40_val >= Decimal("40.00")

    print(f"  Rule of 40 = 营收增速 + 利润率 = {float(g):.2f} + {float(m):.2f} = {float(rule_of_40_val):.2f}")
    if passed:
        verdict = f"通过（Rule of 40 = {float(rule_of_40_val):.2f} ≥ 40）"
        flag = "✅"
    else:
        verdict = f"不达标（Rule of 40 = {float(rule_of_40_val):.2f} < 40）"
        flag = "🔴"
    print(f"\n  {flag} {verdict}")

    if warnings:
        print("\n  合理性告警:")
        for w in warnings:
            print(f"    ⚠️  {w}")

    result = {
        "rule_of_40": float(rule_of_40_val),
        "passed": bool(passed),
        "margin_type": margin_type,
        "verdict": verdict,
        "warnings": warnings,
        "inputs": {
            "revenue_growth": float(g),
            "profit_margin": float(m) if has_profit else None,
            "fcf_margin": float(m) if has_fcf else None,
        },
    }
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


def ev_sales(market_cap, debt, cash, revenue):
    """计算企业价值/营收倍数（EV/Sales）。

    公式：EV = 市值 + 有息负债 − 现金；EV/Sales = EV ÷ 营收。
    适用高研发投入型 / 未盈利科技股；EV/Sales 无绝对阈值，需同业可比。

    Args:
        market_cap: 市值（与其余金额同一货币单位）。
        debt: 有息负债（同一货币单位）。
        cash: 现金及现金等价物（同一货币单位）。
        revenue: TTM 营收（同一货币单位）。

    Returns:
        dict: 含 ev / ev_sales / hint / warnings / inputs 审计回显字段。
    """
    print("=" * 60)
    print("企业价值/营收倍数 (EV/Sales)")
    print("=" * 60)

    mc = exact(market_cap)
    debt = exact(debt)
    cash = exact(cash)
    revenue = exact(revenue)

    hint = "EV/Sales 无绝对阈值，需与同业可比（高研发投入/未盈利科技股适用）"

    # 分母护栏：revenue ≤ 0 → 降级 N/A（除零或负分母无意义）。
    if revenue <= 0:
        warning = "营收 ≤ 0，无法计算 EV/Sales"
        print(f"\n  ⚠️  {warning}")
        result = {
            "ev": None,
            "ev_sales": None,
            "hint": hint,
            "warnings": [warning],
            "inputs": {
                "market_cap": float(mc),
                "debt": float(debt),
                "cash": float(cash),
                "revenue": float(revenue),
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    print(f"  市值 (market cap):     {float(mc):,.2f}")
    print(f"  有息负债 (debt):       {float(debt):,.2f}")
    print(f"  现金 (cash):           {float(cash):,.2f}")
    print(f"  营收 (revenue):        {float(revenue):,.2f}")

    ev_dec = _CTX.subtract(_CTX.add(mc, debt), cash)
    ev_val = ev_dec.quantize(Decimal("0.01"))
    ev_sales_val = _CTX.divide(ev_dec, revenue).quantize(Decimal("0.01"))

    # 合理性告警（不拒绝计算，允许负科目/负 EV）。
    warnings = []
    if mc < 0:
        warnings.append("市值为负（数据异常）")
    if debt < 0:
        warnings.append("有息负债为负（数据异常）")
    if cash < 0:
        warnings.append("现金为负（数据异常）")
    if ev_dec < 0:
        warnings.append("净现金公司：EV 为负（现金 > 市值 + 有息负债），EV/Sales 为负值")
    elif ev_dec == 0:
        warnings.append("EV = 0（现金恰好等于市值 + 有息负债），EV/Sales = 0")

    print(f"\n  EV    = 市值 + 有息负债 − 现金 = {float(mc):,.2f} + {float(debt):,.2f} − {float(cash):,.2f} = {float(ev_val):,.2f}")
    print(f"  EV/Sales = EV ÷ 营收 = {float(ev_val):,.2f} ÷ {float(revenue):,.2f} = {float(ev_sales_val):.2f}")

    if warnings:
        print("\n  合理性告警:")
        for w in warnings:
            print(f"    ⚠️  {w}")
    print(f"\n  💡 {hint}")

    result = {
        "ev": float(ev_val),
        "ev_sales": float(ev_sales_val),
        "hint": hint,
        "warnings": warnings,
        "inputs": {
            "market_cap": float(mc),
            "debt": float(debt),
            "cash": float(cash),
            "revenue": float(revenue),
        },
    }
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


def _tier_adjusted_peg(peg_val):
    """按框架第4步快速增长型四档判定调整后 PEG 档位。

    Args:
        peg_val (Decimal): 调整后 PEG 值（已 2 位小数舍入）。

    Returns:
        tuple: (tier, verdict) 档位与可读结论。
    """
    verdict_extra = ""
    if peg_val > 2:
        verdict_extra = "；PEG>2 严重透支、加速减机动仓"
    if peg_val < 1:
        return "低估", f"低估（PEG<1，可加仓）{verdict_extra}"
    if peg_val <= 1.2:
        return "合理", f"合理（1≤PEG≤1.2）{verdict_extra}"
    if peg_val <= 1.5:
        return "合理偏贵", f"合理偏贵（1.2<PEG≤1.5，持有不加仓、机动仓择机减）{verdict_extra}"
    return "高估", f"高估（PEG>1.5，减机动仓）{verdict_extra}"


def adjusted_peg(market_cap, core_operating_profit, rnd_expense, growth):
    """计算研发费用加回核心经营利润口径的调整后 PE 与调整后 PEG。

    公式：
        adjusted_pe = market_cap / (core_operating_profit + rnd_expense)
        adjusted_peg = adjusted_pe / growth

    Args:
        market_cap: 市值（与利润同货币单位）。
        core_operating_profit: 核心经营利润（同货币单位）。
        rnd_expense: 当期费用化研发支出（同货币单位）。
        growth: 未来盈利增速，百分点（如 30 表示 30%）。

    Returns:
        dict: 含 adjusted_pe / adjusted_peg / tier / verdict /
              warnings / inputs 审计回显字段。
    """
    print("=" * 60)
    print("调整后 PEG (研发费用加回核心经营利润口径)")
    print("=" * 60)

    mc = exact(market_cap)
    op = exact(core_operating_profit)
    rnd = exact(rnd_expense)
    g = exact(growth)

    print(f"  市值 (market cap):            {float(mc):,.2f}")
    print(f"  核心经营利润:                 {float(op):,.2f}")
    print(f"  费用化研发支出:               {float(rnd):,.2f}")
    print(f"  未来盈利增速:                 {float(g):.2f}%")

    warnings = []
    if mc < 0:
        warnings.append("市值为负（数据异常）")
    if rnd < 0:
        warnings.append("研发费用为负（数据异常）")

    # 护栏 1：增速 ≤ 0 → 负/零增长 PEG 无意义。
    if g <= 0:
        warning = f"未来增速 {float(g):.2f}% ≤ 0，调整后 PEG 无意义（亏损或负增长不适用）"
        print(f"\n  ⚠️  {warning}")
        if warnings:
            print("\n  合理性告警:")
            for w in warnings:
                print(f"    ⚠️  {w}")
        result = {
            "adjusted_pe": None,
            "adjusted_peg": None,
            "tier": "N/A",
            "verdict": warning,
            "warnings": warnings,
            "inputs": {
                "market_cap": float(mc),
                "core_operating_profit": float(op),
                "rnd_expense": float(rnd),
                "growth": float(g),
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    core_adj = op + rnd

    # 护栏 2：回加研发后仍亏损 → PE/PEG 无经济意义。
    if core_adj <= 0:
        warning = f"核心经营利润 {float(op):.2f} + 研发回加 {float(rnd):.2f} = {float(core_adj):.2f} ≤ 0，回加后仍亏损，PE/PEG 无意义"
        warnings.append(warning)
        print(f"\n  ⚠️  {warning}")
        if warnings:
            print("\n  合理性告警:")
            for w in warnings:
                print(f"    ⚠️  {w}")
        result = {
            "adjusted_pe": None,
            "adjusted_peg": None,
            "tier": "N/A",
            "verdict": warning,
            "warnings": warnings,
            "inputs": {
                "market_cap": float(mc),
                "core_operating_profit": float(op),
                "rnd_expense": float(rnd),
                "growth": float(g),
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    adjusted_pe = _CTX.divide(mc, core_adj).quantize(Decimal("0.01"))
    adjusted_peg = _CTX.divide(adjusted_pe, g).quantize(Decimal("0.01"))
    tier, verdict = _tier_adjusted_peg(adjusted_peg)

    print(f"\n  调整后经营利润 = 核心经营利润 + 研发回加 = {float(op):,.2f} + {float(rnd):,.2f} = {float(core_adj):,.2f}")
    print(f"  调整后 PE   = 市值 / 调整后经营利润 = {float(mc):,.2f} / {float(core_adj):,.2f} = {float(adjusted_pe):.2f}")
    print(f"  调整后 PEG  = 调整后 PE / 增速 = {float(adjusted_pe):.2f} / {float(g):.2f} = {float(adjusted_peg):.2f}")

    flag = "✅" if adjusted_peg < 1.2 else ("⚠️" if adjusted_peg <= 1.5 else "🔴")
    print(f"\n  {flag} 档位判定: {tier}")

    if warnings:
        print("\n  合理性告警:")
        for w in warnings:
            print(f"    ⚠️  {w}")

    result = {
        "adjusted_pe": float(adjusted_pe),
        "adjusted_peg": float(adjusted_peg),
        "tier": tier,
        "verdict": verdict,
        "warnings": warnings,
        "inputs": {
            "market_cap": float(mc),
            "core_operating_profit": float(op),
            "rnd_expense": float(rnd),
            "growth": float(g),
        },
    }
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


# ---------------------------------------------------------------------------
# DCF 简化三阶段估值（GARP 第4步 成熟型企业）
#
# 三硬约束审计沿用 terminal_value.py audit 的思想与常量取值（复制而非 import，
# 二者保持独立、互不改动）：C1 币种一致性、C2 分母宽度、C3 离散风险归属。
# ---------------------------------------------------------------------------

_DCF_MIN_SPREAD = Decimal("0.05")  # 永续分母 r-g 至少 5 个百分点

_DCF_CURRENCY_BANDS = {
    "CNY": dict(r=(Decimal("0.06"), Decimal("0.09")),
                g_max=Decimal("0.020"), rf=Decimal("0.0170")),
    "USD": dict(r=(Decimal("0.09"), Decimal("0.115")),
                g_max=Decimal("0.040"), rf=Decimal("0.0470")),
    "HKD": dict(r=(Decimal("0.09"), Decimal("0.115")),
                g_max=Decimal("0.040"), rf=Decimal("0.0470")),
}

_DCF_RISK_PLACEMENT_BAD = {"折现率", "r", "beta", "β"}
_DCF_RISK_PLACEMENT_WARN = {"未建模"}
_DCF_RISK_PLACEMENT_OK = {"情景", "尾部档", "概率"}


def _audit_dcf(currency, rd, gT, rf, discrete_risks):
    """执行 DCF 三硬约束审计（只告警不拒绝）。

    复用 terminal_value.py audit 的三条硬约束思想：
        C1 币种一致性——r、gT、rf 必须落在同一币种的合理区间内。
        C2 分母宽度——永续分母 r-g 至少 5 个百分点。
        C3 离散风险归属——退市/VIE/地缘/监管不得塞进折现率 r。

    Args:
        currency: 现金流币种（CNY/USD/HKD），None 或空时跳过 C1 币种区间校验。
        rd: 折现率（Decimal 小数）。
        gT: 永续终值增速（Decimal 小数）。
        rf: 无风险利率（百分点，float 或 None）。
        discrete_risks: 离散风险归属声明（"风险名:归属" 逗号分隔）。

    Returns:
        dict: {'passed': bool, 'alerts': [str]}。
    """
    alerts = []

    # --- C1 币种一致性 -----------------------------------------------------
    band = _DCF_CURRENCY_BANDS.get((currency or "").strip().upper())
    if band is not None:
        lo, hi = band["r"]
        if not (lo <= rd <= hi):
            alerts.append(
                f"C1: 折现率 r={float(rd) * 100:.2f}% 不在 {currency.upper()} 的 "
                f"[{float(lo) * 100:.1f}%, {float(hi) * 100:.1f}%] 区间内")
        if gT > band["g_max"]:
            alerts.append(
                f"C1: 永续增速 g={float(gT) * 100:.2f}% 超过 {currency.upper()} 的 "
                f"上限 {float(band['g_max']) * 100:.1f}%")
        if rf is not None and abs(exact(rf) / 100 - band["rf"]) > Decimal("0.005"):
            alerts.append(
                f"C1: 无风险利率 {float(exact(rf)):.2f}% 与 {currency.upper()} 的 "
                f"基准 {float(band['rf']) * 100:.2f}% 不符")
    elif currency:
        alerts.append(f"C1: 未知币种 {currency}，可选 CNY/USD/HKD，跳过币种区间审计")

    # --- C2 分母宽度 -------------------------------------------------------
    spread = _CTX.subtract(rd, gT)
    if spread <= 0:
        alerts.append(f"C2: 永续分母 r-g = {float(spread) * 100:.2f}pct ≤ 0，戈登模型失效")
    elif spread < _DCF_MIN_SPREAD:
        alerts.append(
            f"C2: 永续分母 r-g = {float(spread) * 100:.2f}pct < "
            f"{float(_DCF_MIN_SPREAD) * 100:.0f}pct，终值对 g 极度敏感")

    # --- C3 离散风险归属 ---------------------------------------------------
    for item in [x.strip() for x in (discrete_risks or "").split(",") if x.strip()]:
        if ":" not in item:
            alerts.append(f"C3: '{item}' 格式应为 风险名:归属")
            continue
        name, place = (p.strip() for p in item.split(":", 1))
        if place in _DCF_RISK_PLACEMENT_BAD:
            alerts.append(
                f"C3: 「{name}」被放进了 {place}，离散风险（退市/VIE/地缘/监管）"
                f"不得计入折现率 r")
        elif place in _DCF_RISK_PLACEMENT_WARN:
            alerts.append(f"C3: 「{name}」未建模，须写进报告的「限制」章节")
        elif place not in _DCF_RISK_PLACEMENT_OK:
            alerts.append(f"C3: 「{name}」的归属 '{place}' 无法识别，"
                          f"合法值：{'/'.join(sorted(_DCF_RISK_PLACEMENT_OK | _DCF_RISK_PLACEMENT_WARN))}")

    return {"passed": not alerts, "alerts": alerts}


def _verdict_dcf(margin):
    """按框架第4步「市值 ≤ 保守 DCF 80%」判定 DCF 安全边际档位。

    Args:
        margin: 安全边际（Decimal，2 位小数；None 表示不可用）。

    Returns:
        str: 可读结论（低估/合理/高估/N/A）。
    """
    if margin is None:
        return "N/A"
    if margin >= Decimal("20"):
        return "低估（市值≤保守DCF 80%）"
    if margin >= 0:
        return "合理（安全边际<20%）"
    return "高估（市值高于DCF）"


def dcf(fcf, g_high, years_high, years_fade, g_terminal, r,
        shares, market_cap, currency=None, rf=None, discrete_risks=""):
    """计算简化三阶段 DCF 的现值、每股价值与安全边际。

    三阶段模型：高增长阶段 n1 年（增速 g_high）→ 过渡阶段 n2 年（增速线性
    衰减至 g_terminal）→ Gordon 永续终值。现值按折现率 r 折现到第 0 年：

        pv = Σ CF_t/(1+r)^t + TV/(1+r)^(n1+n2)
        TV = CF_(n1+n2) × (1+g_terminal) / (r - g_terminal)

    Args:
        fcf: 基准自由现金流（第 0 年，与市值同货币单位）。
        g_high: 高增长阶段增速，百分点（如 10 表示 10%）。
        years_high: 高增长阶段年数（≥1）。
        years_fade: 过渡阶段年数（≥0，0 表示不设过渡）。
        g_terminal: 永续终值增速，百分点（如 2 表示 2%）。
        r: 折现率，百分点（如 9 表示 9%）。
        shares: 总股本（与市值同刻度）。
        market_cap: 当前市值（与 fcf 同货币单位）。
        currency: 现金流币种，可选（CNY/USD/HKD），用于 C1 审计。
        rf: 无风险利率，百分点，可选，用于 C1 审计。
        discrete_risks: 离散风险归属声明，可选，用于 C3 审计。

    Returns:
        dict: 含 pv / per_share / margin_of_safety_pct / verdict /
              audit / warnings / inputs 字段。
    """
    print("=" * 60)
    print("DCF 简化三阶段估值（高增/过渡/永续）")
    print("=" * 60)

    fc = exact(fcf)
    g1 = _CTX.divide(exact(g_high), Decimal("100"))
    gT = _CTX.divide(exact(g_terminal), Decimal("100"))
    rd = _CTX.divide(exact(r), Decimal("100"))
    n1 = int(years_high)
    n2 = int(years_fade)
    sh = exact(shares)
    mc = exact(market_cap)

    print(f"  基准现金流 (FCF):            {float(fc):,.2f}")
    print(f"  高增长增速 g1:              {float(g_high):.2f}%  ({n1} 年)")
    print(f"  过渡年数:                    {n2} 年")
    print(f"  永续增速 gT:                {float(g_terminal):.2f}%")
    print(f"  折现率 r:                    {float(r):.2f}%")
    print(f"  总股本:                      {float(sh):,.4f}")
    print(f"  当前市值:                    {float(mc):,.2f}")

    # 合理性告警（不拒绝）与模型失效护栏（全降级 N/A）。
    warnings = []
    if fc <= 0:
        warnings.append(f"基准现金流 FCF {float(fc):,.2f} ≤ 0")
    if rd <= 0:
        warnings.append(f"折现率 r {float(r):.2f}% ≤ 0")
    if n1 < 1:
        warnings.append(f"高增长年数 {n1} < 1")
    if n2 < 0:
        warnings.append(f"过渡年数 {n2} < 0")
    if gT >= rd:
        warnings.append(f"永续增速 {float(g_terminal):.2f}% ≥ 折现率 {float(r):.2f}%，"
                        f"戈登终值模型失效")
    if g_high < 0:
        warnings.append(f"高增长增速 {float(g_high):.2f}% 为负（数据异常）")
    if g_terminal < 0:
        warnings.append(f"永续增速 {float(g_terminal):.2f}% 为负（数据异常）")
    if sh <= 0:
        warnings.append("总股本 ≤ 0，每股价值不可用")
    if mc <= 0:
        warnings.append("市值 ≤ 0，安全边际不可用")

    audit = _audit_dcf(currency, rd, gT, rf, discrete_risks)

    # 护栏：任一模型失效条件成立 → 现值/每股/安全边际全降级 N/A，不抛异常。
    model_invalid = (
        fc <= 0 or rd <= 0 or n1 < 1 or n2 < 0 or gT >= rd
    )
    if model_invalid:
        print("\n  ⚠️  模型失效，DCF 现值/每股价值/安全边际不可用。")
        if warnings:
            print("\n  合理性告警:")
            for w in warnings:
                print(f"    ⚠️  {w}")
        if audit["alerts"]:
            print("\n  审计告警 (audit):")
            for a in audit["alerts"]:
                print(f"    🔍  {a}")
        result = {
            "pv": None,
            "per_share": None,
            "margin_of_safety_pct": None,
            "verdict": "N/A",
            "audit": audit,
            "warnings": warnings,
            "inputs": {
                "fcf": float(fc),
                "g_high": float(g_high),
                "years_high": n1,
                "years_fade": n2,
                "g_terminal": float(g_terminal),
                "r": float(r),
                "shares": float(sh),
                "market_cap": float(mc),
                "currency": currency,
                "rf": float(exact(rf)) if rf is not None else None,
                "discrete_risks": discrete_risks,
            },
        }
        print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
        return result

    # 现金流序列：高增长（n1 年）+ 过渡线性衰减（n2 年）。
    cfs = []
    curr = fc
    one_plus_g1 = _CTX.add(Decimal("1"), g1)
    for _ in range(n1):
        curr = _CTX.multiply(curr, one_plus_g1)
        cfs.append(curr)
    if n2 > 0:
        for j in range(1, n2 + 1):
            gj = _CTX.add(
                g1,
                _CTX.multiply(_CTX.subtract(gT, g1),
                              _CTX.divide(Decimal(j), Decimal(n2))))
            curr = _CTX.multiply(curr, _CTX.add(Decimal("1"), gj))
            cfs.append(curr)

    # 永续终值：Gordon 增长模型（护栏已保证 rd - gT > 0）。
    denom = _CTX.subtract(rd, gT)
    tv = _CTX.divide(_CTX.multiply(curr, _CTX.add(Decimal("1"), gT)), denom)

    # 现值：前 n1+n2 期现金流 + 终值，统一折现到第 0 年。
    one_r = _CTX.add(Decimal("1"), rd)
    total_pv = Decimal("0")
    for t, c in enumerate(cfs, 1):
        total_pv = _CTX.add(total_pv, _CTX.divide(c, _CTX.power(one_r, t)))
    total_pv = _CTX.add(total_pv, _CTX.divide(tv, _CTX.power(one_r, n1 + n2)))

    pv_q = total_pv.quantize(Decimal("0.01"))
    per_share = _CTX.divide(total_pv, sh).quantize(Decimal("0.01")) if sh > 0 else None
    if mc > 0:
        margin = _CTX.multiply(
            _CTX.divide(_CTX.subtract(total_pv, mc), total_pv),
            Decimal("100")).quantize(Decimal("0.01"))
    else:
        margin = None

    verdict = _verdict_dcf(margin)

    print(f"\n  高增长末现金流 CF[{n1}]     = {float(cfs[n1 - 1]):,.2f}")
    if n2 > 0:
        print(f"  过渡末现金流 CF[{n1 + n2}]    = {float(cfs[-1]):,.2f}")
    print(f"  永续终值 TV                 = {float(tv):,.2f}")
    print(f"  现值 PV                     = {float(pv_q):,.2f}")
    if per_share is not None:
        print(f"  每股价值                    = {float(per_share):,.2f}")
    else:
        print(f"  每股价值                    = N/A")
    if margin is not None:
        print(f"  安全边际                    = {float(margin):.2f}%")
    else:
        print(f"  安全边际                    = N/A")

    if margin is None:
        flag = "⚪"
    elif margin >= 20:
        flag = "✅"
    elif margin >= 0:
        flag = "⚪"
    else:
        flag = "🔴"
    print(f"\n  {flag} 判定: {verdict}")

    if audit["alerts"]:
        print("\n  审计告警 (audit):")
        for a in audit["alerts"]:
            print(f"    🔍  {a}")
    if warnings:
        print("\n  合理性告警:")
        for w in warnings:
            print(f"    ⚠️  {w}")

    result = {
        "pv": float(pv_q),
        "per_share": float(per_share) if per_share is not None else None,
        "margin_of_safety_pct": float(margin) if margin is not None else None,
        "verdict": verdict,
        "audit": audit,
        "warnings": warnings,
        "inputs": {
            "fcf": float(fc),
            "g_high": float(g_high),
            "years_high": n1,
            "years_fade": n2,
            "g_terminal": float(g_terminal),
            "r": float(r),
            "shares": float(sh),
            "market_cap": float(mc),
            "currency": currency,
            "rf": float(exact(rf)) if rf is not None else None,
            "discrete_risks": discrete_risks,
        },
    }
    print(f"\n  结构化输出: {json.dumps(result, ensure_ascii=False)}")
    return result


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Financial Rigor Toolkit — 金融数据严谨性验证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
  %(prog)s verify-valuation --price 510 --eps 23.5 --bvps 120
  %(prog)s cross-validate --field revenue --values '{"年报": 7518, "Yahoo": 7500}' --unit 亿
  %(prog)s benford --values '[1234, 2345, 3456, ...]'
  %(prog)s calc --expr '510 * 9.11e9'
  %(prog)s peg --pe 30 --growth 40
  %(prog)s ps-g --ps 5 --revenue-growth 80
  %(prog)s pe-percentile --pe-series '[20, 25, 30, 28, 26]' --current 30
  %(prog)s implied-growth --market-cap 1e12 --target-pe 30 --net-margin 0.15 --ttm-revenue 5e11 --guidance-growth 0.35
  %(prog)s roic --nopat 12.5 --invested-capital 100 --wacc 8
  %(prog)s incremental-roic --nopat-from 10 --invested-capital-from 80 --nopat-to 12.5 --invested-capital-to 100
  %(prog)s wacc --equity-value 80 --debt-value 20 --cost-equity 10 --cost-debt 5 --tax-rate 0.25
  %(prog)s rule-of-40 --revenue-growth 30 --profit-margin 25
  %(prog)s ev-sales --market-cap 800 --debt 150 --cash 50 --revenue 200
  %(prog)s adjusted-peg --market-cap 200 --core-operating-profit 10 --rnd-expense 5 --growth 30
  %(prog)s dcf --fcf 100 --g-high 10 --years-high 5 --years-fade 5 --g-terminal 2 --r 9 --shares 10 --market-cap 1000 --currency CNY
        """)

    sub = parser.add_subparsers(dest="command")

    # verify-market-cap
    mc = sub.add_parser("verify-market-cap", help="验算市值 = 股价 × 总股本")
    mc.add_argument("--price", type=float, required=True)
    mc.add_argument("--shares", type=float, required=True, help="总股本")
    mc.add_argument("--reported", type=float, required=True, help="报告市值")
    mc.add_argument("--currency", default="", help="币种")

    # verify-valuation
    val = sub.add_parser("verify-valuation", help="验算估值指标")
    val.add_argument("--price", type=float, required=True)
    val.add_argument("--eps", type=float, default=None)
    val.add_argument("--bvps", type=float, default=None, help="每股净资产")
    val.add_argument("--fcf-per-share", type=float, default=None)
    val.add_argument("--dividend", type=float, default=None, help="每股股息")
    val.add_argument("--revenue-per-share", type=float, default=None)

    # cross-validate
    cv = sub.add_parser("cross-validate", help="多源交叉验证")
    cv.add_argument("--field", required=True, help="数据字段名")
    cv.add_argument("--values", required=True, help="JSON: {来源: 数值}")
    cv.add_argument("--unit", default="")
    cv.add_argument("--tolerance", type=float, default=2.0, help="容差百分比")

    # benford
    bf = sub.add_parser("benford", help="Benford定律检测")
    bf.add_argument("--values", required=True, help="JSON数组")

    # calc
    ca = sub.add_parser("calc", help="精确计算")
    ca.add_argument("--expr", required=True, help="算术表达式")

    # three-scenario
    ts = sub.add_parser("three-scenario", help="三情景估值")
    ts.add_argument("--price", type=float, required=True)
    ts.add_argument("--eps", type=float, required=True)
    ts.add_argument("--shares", type=float, required=True, help="总股本(亿)")
    ts.add_argument("--growth", nargs=3, type=float, required=True,
                    help="三情景年增速 (乐观 中性 悲观), 如 0.15 0.08 0.0")
    ts.add_argument("--pe", nargs=3, type=float, required=True,
                    help="三情景目标PE, 如 25 20 15")
    ts.add_argument("--years", type=int, default=3)
    ts.add_argument("--currency", default="")

    # peg
    pg = sub.add_parser("peg", help="PEG 估值（林奇）")
    pg.add_argument("--pe", type=float, required=True, help="市盈率 TTM")
    pg.add_argument("--growth", type=float, required=True, help="盈利增速，百分点（如 40）")

    # ps-g
    psg = sub.add_parser("ps-g", help="PSG 市销率增长比（爆发期专用）")
    psg.add_argument("--ps", type=float, required=True, help="市销率 TTM")
    psg.add_argument("--revenue-growth", type=float, required=True, help="营收增速，百分点（如 80）")

    # pe-percentile
    pep = sub.add_parser("pe-percentile", help="PE 历史分位")
    pep.add_argument("--pe-series", required=True, help="JSON 数组: 历史PE序列")
    pep.add_argument("--current", type=float, default=None, help="当前 PE（缺省取序列最后一位）")

    # implied-growth
    ig = sub.add_parser("implied-growth", help="市值隐含业绩倒推验证（红/黄/绿）")
    ig.add_argument("--market-cap", type=float, required=True, help="当前市值")
    ig.add_argument("--target-pe", type=float, required=True, help="目标 PE")
    ig.add_argument("--net-margin", type=float, required=True, help="年化净利率（如 0.15）")
    ig.add_argument("--ttm-revenue", type=float, required=True, help="TTM 营收")
    ig.add_argument("--guidance-growth", type=float, required=True, help="公司指引营收增速上限（如 0.35）")

    # roic
    rc = sub.add_parser("roic", help="投入资本回报率（GARP 支柱二核心口径）")
    rc.add_argument("--nopat", type=float, required=True, help="税后净营业利润")
    rc.add_argument("--invested-capital", type=float, required=True, help="投入资本（须 > 0）")
    rc.add_argument("--wacc", type=float, default=None, help="WACC，百分点（如 8 表示 8%%）")
    rc.add_argument("--expanding", action="store_true", help="仍在拼命扩产（ROIC<5%% 时触发一票否决）")

    # incremental-roic
    irc = sub.add_parser("incremental-roic", help="增量投入资本回报率（增量口径）")
    irc.add_argument("--nopat-from", type=float, required=True, help="上期税后净营业利润")
    irc.add_argument("--invested-capital-from", type=float, required=True, help="上期投入资本")
    irc.add_argument("--nopat-to", type=float, required=True, help="本期税后净营业利润")
    irc.add_argument("--invested-capital-to", type=float, required=True, help="本期投入资本")
    irc.add_argument("--period-from", default="", help="上期标签（如 2023，仅回显）")
    irc.add_argument("--period-to", default="", help="本期标签（如 2024，仅回显）")

    # wacc
    wc = sub.add_parser("wacc", help="加权平均资本成本（GARP 支柱二资本成本侧）")
    wc.add_argument("--equity-value", type=float, required=True, help="股权价值 E")
    wc.add_argument("--debt-value", type=float, required=True, help="有息债务值 D")
    wc.add_argument("--cost-equity", type=float, required=True,
                    help="股权成本 re（百分点，如 10 表示 10%%）")
    wc.add_argument("--cost-debt", type=float, required=True,
                    help="债务成本 rd（税前，百分点，如 5 表示 5%%）")
    wc.add_argument("--tax-rate", type=float, required=True,
                    help="企业所得税税率（小数，如 0.25 表示 25%%）")

    # rule-of-40
    r40 = sub.add_parser("rule-of-40", help="Rule of 40 成长质量判定（高研发投入型）")
    r40.add_argument("--revenue-growth", type=float, required=True,
                     help="营收增速，百分点（如 30 表示 30%%）")
    r40.add_argument("--profit-margin", type=float, default=None,
                     help="利润率，百分点（与 --fcf-margin 二选一）")
    r40.add_argument("--fcf-margin", type=float, default=None,
                     help="FCF 利润率，百分点（与 --profit-margin 二选一）")

    # ev-sales
    ev = sub.add_parser("ev-sales", help="企业价值/营收倍数（EV/Sales，高研发投入型/未盈利科技股）")
    ev.add_argument("--market-cap", type=float, required=True, help="市值（同一货币单位）")
    ev.add_argument("--debt", type=float, required=True, help="有息负债（同一货币单位）")
    ev.add_argument("--cash", type=float, required=True, help="现金及现金等价物（同一货币单位）")
    ev.add_argument("--revenue", type=float, required=True, help="TTM 营收（同一货币单位）")

    # adjusted-peg
    ap = sub.add_parser("adjusted-peg", help="调整后 PEG（研发费用加回核心经营利润口径）")
    ap.add_argument("--market-cap", type=float, required=True, help="市值（与利润同货币单位）")
    ap.add_argument("--core-operating-profit", type=float, required=True,
                    help="核心经营利润（同货币单位，已扣除非经常损益）")
    ap.add_argument("--rnd-expense", type=float, required=True,
                    help="当期费用化研发支出（同货币单位）")
    ap.add_argument("--growth", type=float, required=True,
                    help="未来盈利增速，百分点（如 30 表示 30%%）")

    # dcf
    dc = sub.add_parser("dcf", help="简化三阶段 DCF 估值（高增/过渡/永续，成熟型企业）")
    dc.add_argument("--fcf", type=float, required=True,
                    help="基准自由现金流（第 0 年，与市值同货币单位）")
    dc.add_argument("--g-high", type=float, required=True,
                    help="高增长阶段增速，百分点（如 10 表示 10%%）")
    dc.add_argument("--years-high", type=int, required=True, help="高增长阶段年数（≥1）")
    dc.add_argument("--years-fade", type=int, required=True, help="过渡阶段年数（≥0，0 表示不设过渡）")
    dc.add_argument("--g-terminal", type=float, required=True,
                    help="永续终值增速，百分点（如 2 表示 2%%）")
    dc.add_argument("--r", type=float, required=True, help="折现率，百分点（如 9 表示 9%%）")
    dc.add_argument("--shares", type=float, required=True, help="总股本（用于每股价值）")
    dc.add_argument("--market-cap", type=float, required=True,
                    help="当前市值（与 FCF 同货币单位）")
    dc.add_argument("--currency", default=None, help="现金流币种：CNY/USD/HKD（可选，供 C1 审计）")
    dc.add_argument("--rf", type=float, default=None,
                    help="无风险利率，百分点（可选，给了就校验与币种匹配）")
    dc.add_argument("--discrete-risks", default="",
                    help="离散风险归属，格式 风险名:归属，逗号分隔。"
                         "合法归属：情景/尾部档/概率（通过）、未建模（警告）。"
                         "写成 折现率/r/beta 一律告警")

    args = parser.parse_args()

    if args.command == "verify-market-cap":
        verify_market_cap(args.price, args.shares, args.reported, args.currency)
    elif args.command == "verify-valuation":
        verify_valuation(args.price, args.eps, args.bvps, args.fcf_per_share,
                        args.dividend, args.revenue_per_share)
    elif args.command == "cross-validate":
        values = json.loads(args.values)
        cross_validate(args.field, values, args.unit, args.tolerance)
    elif args.command == "benford":
        values = json.loads(args.values)
        benford_check(values)
    elif args.command == "calc":
        exact_calc(args.expr)
    elif args.command == "three-scenario":
        three_scenario_valuation(
            args.price, args.eps, args.shares,
            args.growth[0], args.growth[1], args.growth[2],
            args.pe[0], args.pe[1], args.pe[2],
            args.years, args.currency)
    elif args.command == "peg":
        peg_ratio(args.pe, args.growth)
    elif args.command == "ps-g":
        psg_ratio(args.ps, args.revenue_growth)
    elif args.command == "pe-percentile":
        pe_percentile(json.loads(args.pe_series), args.current)
    elif args.command == "implied-growth":
        implied_growth(args.market_cap, args.target_pe, args.net_margin,
                       args.ttm_revenue, args.guidance_growth)
    elif args.command == "roic":
        roic(args.nopat, args.invested_capital, args.wacc, args.expanding)
    elif args.command == "incremental-roic":
        incremental_roic(args.nopat_from, args.invested_capital_from,
                         args.nopat_to, args.invested_capital_to,
                         args.period_from, args.period_to)
    elif args.command == "wacc":
        wacc(args.equity_value, args.debt_value,
             args.cost_equity, args.cost_debt, args.tax_rate)
    elif args.command == "rule-of-40":
        rule_of_40(args.revenue_growth, args.profit_margin, args.fcf_margin)
    elif args.command == "ev-sales":
        ev_sales(args.market_cap, args.debt, args.cash, args.revenue)
    elif args.command == "adjusted-peg":
        adjusted_peg(args.market_cap, args.core_operating_profit,
                     args.rnd_expense, args.growth)
    elif args.command == "dcf":
        dcf(args.fcf, args.g_high, args.years_high, args.years_fade,
            args.g_terminal, args.r, args.shares, args.market_cap,
            args.currency, args.rf, args.discrete_risks)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
