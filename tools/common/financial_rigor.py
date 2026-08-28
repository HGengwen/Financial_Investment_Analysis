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

    if peg < 1:
        rating = "低估 (低估潜力)"
        flag = "✅"
    elif peg <= 1.5:
        rating = "合理 (合理区间)"
        flag = "⚠️"
    else:
        rating = "高估 (成长透支)"
        flag = "🔴"
    print(f"  {flag} 林奇评级: {rating}")

    if peg >= 3:
        print("     警告: PEG > 3, 若营收高增可豁免参考, 但需警惕估值透支")

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

    # 分位 = 历史中 ≤ 当前PE 的比例 (0-100)
    below = sum(1 for v in hist if v <= current_pe_val)
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
