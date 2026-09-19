#!/usr/bin/env python3
"""Unit tests for financial_rigor.py.

Test suite covering all major functions:
1. Market cap verification
2. Valuation metrics verification
3. Cross-source validation
4. Benford's Law check
5. Exact calculator
6. Three-scenario valuation
7. PEG / PSG / PE-percentile / Implied-growth (mid-trend-tech-screen 阶段一新增)
"""

import sys
import unittest
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports (dynamic, cross-platform)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common.financial_rigor import (
    exact,
    fmt_number,
    verify_market_cap,
    verify_valuation,
    cross_validate,
    benford_check,
    exact_calc,
    three_scenario_valuation,
    peg_ratio,
    psg_ratio,
    pe_percentile,
    implied_growth,
    roic,
    incremental_roic,
    wacc,
    rule_of_40,
    ev_sales,
    adjusted_peg,
    dcf
)


class TestExactDecimal(unittest.TestCase):
    """Test exact decimal conversion and formatting."""

    def test_exact_from_float(self):
        """Test conversion from float preserves precision."""
        result = exact(3.14159)
        self.assertEqual(result, Decimal('3.14159'))

    def test_exact_from_int(self):
        """Test conversion from int."""
        result = exact(100)
        self.assertEqual(result, Decimal('100'))

    def test_exact_from_decimal(self):
        """Test conversion from Decimal returns same."""
        d = Decimal('123.456')
        result = exact(d)
        self.assertEqual(result, d)

    def test_exact_from_scientific_notation(self):
        """Test conversion from scientific notation."""
        result = exact(1.23e5)
        self.assertEqual(result, Decimal('123000'))

    def test_fmt_number_billions(self):
        """Test formatting billions."""
        result = fmt_number(Decimal('5000000000'))
        self.assertEqual(result, '5.00B')

    def test_fmt_number_millions(self):
        """Test formatting millions."""
        result = fmt_number(Decimal('5000000'))
        self.assertEqual(result, '5.00M')

    def test_fmt_number_yi_unit(self):
        """Test formatting with Chinese unit '亿'."""
        result = fmt_number(Decimal('1500'), '亿')
        self.assertEqual(result, '1500.00亿')

    def test_fmt_number_wan_yi(self):
        """Test formatting with unit '万亿'."""
        result = fmt_number(Decimal('15000'), '亿')
        self.assertEqual(result, '1.50万亿')


class TestMarketCapVerification(unittest.TestCase):
    """Test market cap verification."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_market_cap_correct(self, mock_stdout):
        """Test market cap verification with matching values."""
        result = verify_market_cap(510, 9.11e9, 4.65e12, 'HKD')
        self.assertTrue(result)
        output = mock_stdout.getvalue()
        self.assertIn('验证通过', output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_market_cap_large_deviation(self, mock_stdout):
        """Test market cap verification with large deviation."""
        result = verify_market_cap(510, 9.11e9, 3.0e12, 'HKD')
        self.assertFalse(result)
        output = mock_stdout.getvalue()
        self.assertIn('警告', output)
        self.assertIn('偏差', output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_market_cap_small_deviation(self, mock_stdout):
        """Test market cap verification with small deviation."""
        # 510 * 9.11e9 = 4.6461e12, reported 4.65e12 (deviation ~0.08%)
        result = verify_market_cap(510, 9.11e9, 4.6461e12, 'HKD')
        self.assertTrue(result)
        output = mock_stdout.getvalue()
        self.assertIn('验证通过', output)


class TestValuationVerification(unittest.TestCase):
    """Test valuation metrics verification."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_pe(self, mock_stdout):
        """Test PE calculation."""
        result = verify_valuation(price=510, eps=23.5)
        self.assertIn('PE', result)
        self.assertAlmostEqual(result['PE'], 21.70, places=1)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_pb(self, mock_stdout):
        """Test PB calculation."""
        result = verify_valuation(price=510, bvps=120)
        self.assertIn('PB', result)
        self.assertAlmostEqual(result['PB'], 4.25, places=2)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_roe(self, mock_stdout):
        """Test ROE calculation."""
        result = verify_valuation(price=510, eps=23.5, bvps=120)
        self.assertIn('ROE', result)
        self.assertAlmostEqual(result['ROE'], 19.58, places=1)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_fcf_yield(self, mock_stdout):
        """Test FCF yield calculation."""
        result = verify_valuation(price=510, fcf_per_share=18)
        self.assertIn('FCF_Yield', result)
        self.assertAlmostEqual(result['FCF_Yield'], 3.53, places=1)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_dividend_yield(self, mock_stdout):
        """Test dividend yield calculation."""
        result = verify_valuation(price=510, dividend=2.4)
        self.assertIn('Dividend_Yield', result)
        self.assertAlmostEqual(result['Dividend_Yield'], 0.47, places=2)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_ps(self, mock_stdout):
        """Test PS calculation."""
        result = verify_valuation(price=510, revenue_per_share=150)
        self.assertIn('PS', result)
        self.assertAlmostEqual(result['PS'], 3.4, places=1)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_zero_eps(self, mock_stdout):
        """Test PE calculation with zero EPS."""
        result = verify_valuation(price=510, eps=0)
        self.assertNotIn('PE', result)


class TestCrossValidation(unittest.TestCase):
    """Test cross-source data validation."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_cross_validate_consistent(self, mock_stdout):
        """Test cross-validation with consistent data."""
        source_values = {
            '年报': 7518,
            'Yahoo': 7500,
            'StockAnalysis': 7520
        }
        result = cross_validate('revenue', source_values, '亿')
        self.assertTrue(result['all_consistent'])
        self.assertAlmostEqual(result['consensus'], 7518, places=0)
        output = mock_stdout.getvalue()
        self.assertIn('数据一致', output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_cross_validate_inconsistent(self, mock_stdout):
        """Test cross-validation with inconsistent data."""
        source_values = {
            '年报': 7518,
            'Yahoo': 7000,  # 7% deviation
            'StockAnalysis': 7520
        }
        result = cross_validate('revenue', source_values, '亿')
        self.assertFalse(result['all_consistent'])
        output = mock_stdout.getvalue()
        self.assertIn('偏差', output)


class TestBenfordCheck(unittest.TestCase):
    """Test Benford's Law check."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_benford_check_natural_numbers(self, mock_stdout):
        """Test Benford check with naturally distributed numbers."""
        # Generate numbers following Benford's law (固定种子 + 大样本，MAD 稳定收敛)
        import random
        import math
        random.seed(42)
        values = []
        for _ in range(500):
            # Generate log-uniform distribution
            log_value = random.uniform(0, 5)
            value = 10 ** log_value
            values.append(int(value))

        result = benford_check(values)
        self.assertIsNotNone(result)
        self.assertLess(result['mad'], 0.02)  # Should be relatively close
        output = mock_stdout.getvalue()
        self.assertIn('MAD', output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_benford_check_insufficient_samples(self, mock_stdout):
        """Test Benford check with insufficient samples."""
        result = benford_check([100, 200, 300])
        self.assertIsNone(result)
        output = mock_stdout.getvalue()
        self.assertIn('样本量不足', output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_benford_check_uniform_distribution(self, mock_stdout):
        """Test Benford check with uniform distribution (should not conform)."""
        # Generate numbers with uniform first digit distribution
        import random
        values = []
        for _ in range(500):
            first_digit = random.randint(1, 9)
            value = first_digit * random.randint(100, 999)
            values.append(value)

        result = benford_check(values)
        self.assertIsNotNone(result)
        # Uniform distribution typically has higher MAD
        output = mock_stdout.getvalue()
        self.assertIn('MAD', output)


class TestExactCalculator(unittest.TestCase):
    """Test exact calculator."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_exact_calc_multiplication(self, mock_stdout):
        """Test exact multiplication."""
        result = exact_calc('510 * 9.11e9')
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 4.6461e12, places=6)

    @patch('sys.stdout', new_callable=StringIO)
    def test_exact_calc_division(self, mock_stdout):
        """Test exact division."""
        result = exact_calc('510 / 23.5')
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 21.702, places=3)

    @patch('sys.stdout', new_callable=StringIO)
    def test_exact_calc_complex_expression(self, mock_stdout):
        """Test complex expression."""
        result = exact_calc('(510 + 50) * 2 - 100')
        self.assertIsNotNone(result)
        self.assertEqual(result, 1020)

    @patch('sys.stdout', new_callable=StringIO)
    def test_exact_calc_unsafe_expression(self, mock_stdout):
        """Test unsafe expression should return None."""
        result = exact_calc('510 + print("hello")')
        self.assertIsNone(result)
        output = mock_stdout.getvalue()
        self.assertIn('不安全', output)


class TestThreeScenarioValuation(unittest.TestCase):
    """Test three-scenario valuation model."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_three_scenario_valuation_basic(self, mock_stdout):
        """Test basic three-scenario valuation."""
        three_scenario_valuation(
            current_price=510,
            current_eps=23.5,
            shares_billion=9.11,
            growth_optimistic=0.15,
            growth_neutral=0.08,
            growth_pessimistic=0.0,
            pe_optimistic=25,
            pe_neutral=20,
            pe_pessimistic=15,
            years=3,
            currency='HKD'
        )
        output = mock_stdout.getvalue()
        self.assertIn('乐观', output)
        self.assertIn('中性', output)
        self.assertIn('悲观', output)
        self.assertIn('510', output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_three_scenario_valuation_negative_growth(self, mock_stdout):
        """Test three-scenario valuation with negative growth."""
        three_scenario_valuation(
            current_price=100,
            current_eps=10,
            shares_billion=10,
            growth_optimistic=0.10,
            growth_neutral=0.0,
            growth_pessimistic=-0.10,
            pe_optimistic=20,
            pe_neutral=15,
            pe_pessimistic=10,
            years=3,
            currency='CNY'
        )
        output = mock_stdout.getvalue()
        self.assertIn('乐观', output)
        self.assertIn('悲观', output)


class TestPegRatio(unittest.TestCase):
    """Test PEG calculation (林奇核心指标, mid-trend-tech-screen 阶段一新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_peg_under_valued(self, mock_stdout):
        """Test PEG < 1 → 低估."""
        result = peg_ratio(30, 40)
        self.assertIsNotNone(result['peg'])
        self.assertAlmostEqual(result['peg'], 0.75, places=2)
        self.assertIn('低估', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_peg_fair(self, mock_stdout):
        """Test PEG 0.8~1.2 → 合理."""
        result = peg_ratio(20, 20)
        self.assertAlmostEqual(result['peg'], 1.0, places=2)
        self.assertIn('合理', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_peg_expensive(self, mock_stdout):
        """Test PEG 1.2~1.5 → 偏贵."""
        result = peg_ratio(50, 40)
        self.assertAlmostEqual(result['peg'], 1.25, places=2)
        self.assertIn('偏贵', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_peg_over_valued(self, mock_stdout):
        """Test PEG 1.5~2 → 高估."""
        result = peg_ratio(80, 40)
        self.assertAlmostEqual(result['peg'], 2.0, places=2)
        self.assertIn('高估', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_peg_severely_over_valued(self, mock_stdout):
        """Test PEG > 2 → 严重透支."""
        result = peg_ratio(100, 40)
        self.assertAlmostEqual(result['peg'], 2.5, places=2)
        self.assertIn('严重透支', result['rating'])


class TestPsgRatio(unittest.TestCase):
    """Test PSG calculation (市销率增长比, 爆发期专用, mid-trend-tech-screen 阶段一新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_psg_excellent(self, mock_stdout):
        """Test PSG < 0.5 → 优秀."""
        result = psg_ratio(5, 80)
        self.assertAlmostEqual(result['psg'], 0.0625, places=4)
        self.assertIn('优秀', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_psg_reasonable(self, mock_stdout):
        """Test PSG 0.5~1.0 → 合理."""
        result = psg_ratio(60, 80)
        self.assertAlmostEqual(result['psg'], 0.75, places=2)
        self.assertIn('合理', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_psg_over_valued(self, mock_stdout):
        """Test PSG > 1.0 → 高估."""
        result = psg_ratio(200, 100)
        self.assertAlmostEqual(result['psg'], 2.0, places=2)
        self.assertIn('高估', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_psg_negative_growth(self, mock_stdout):
        """Test 营收负增长 → PSG 无意义."""
        result = psg_ratio(5, -10)
        self.assertIsNone(result['psg'])
        self.assertEqual(result['note'], 'negative_growth')


class TestPePercentile(unittest.TestCase):
    """Test PE historical percentile (mid-trend-tech-screen 阶段一新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_pe_percentile_high(self, mock_stdout):
        """Test 当前 PE 处于历史高位 → >60%."""
        result = pe_percentile([20, 25, 30, 28, 26], 30)
        self.assertAlmostEqual(result['percentile'], 80.0, places=1)
        self.assertIn('偏高', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_pe_percentile_low(self, mock_stdout):
        """Test 当前 PE 处于历史低位 → <40%."""
        result = pe_percentile([20, 30, 40, 50, 60], 25)
        self.assertAlmostEqual(result['percentile'], 20.0, places=1)
        self.assertIn('低估', result['rating'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_pe_percentile_default_current(self, mock_stdout):
        """Test 缺省 current 时取序列最后一位."""
        result = pe_percentile([10, 20, 30])
        self.assertEqual(result['current_pe'], 30)
        # 缺省时当前值从序列末尾 pop 出，历史序列剩 [10,20]，30 高于其 100%
        self.assertAlmostEqual(result['percentile'], 100.0, places=1)


class TestImpliedGrowth(unittest.TestCase):
    """Test 市值隐含业绩倒推验证 (红/黄/绿, mid-trend-tech-screen 阶段一新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_implied_growth_green(self, mock_stdout):
        """Test 隐含增速 < 指引 → 绿灯."""
        result = implied_growth(1e12, 30, 0.15, 5e11, 0.35)
        self.assertEqual(result['verdict'], 'green')
        self.assertLess(result['implied_growth'], 0.35)

    @patch('sys.stdout', new_callable=StringIO)
    def test_implied_growth_yellow(self, mock_stdout):
        """Test 隐含增速 介于指引与 1.5 倍之间 → 黄灯."""
        result = implied_growth(3.2e12, 30, 0.15, 5e11, 0.35)
        self.assertEqual(result['verdict'], 'yellow')

    @patch('sys.stdout', new_callable=StringIO)
    def test_implied_growth_red(self, mock_stdout):
        """Test 隐含增速 > 指引×1.5 → 红灯."""
        result = implied_growth(5e12, 30, 0.15, 5e11, 0.35)
        self.assertEqual(result['verdict'], 'red')

    @patch('sys.stdout', new_callable=StringIO)
    def test_implied_growth_invalid_margin(self, mock_stdout):
        """Test 净利率 ≤ 0 → 返回 None 无法倒推."""
        result = implied_growth(1e12, 30, 0, 5e11, 0.35)
        self.assertIsNone(result)


class TestRoic(unittest.TestCase):
    """Test ROIC 投入资本回报率与四档判定 (GARP 支柱二, P1-1 新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_excellent(self, mock_stdout):
        """ROIC > 15% → 优秀档."""
        result = roic(20, 100)
        self.assertEqual(result['roic'], 20.0)
        self.assertEqual(result['tier'], '优秀')
        self.assertIn('优秀', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_qualified_with_wacc(self, mock_stdout):
        """10%~15% 且 ROIC>WACC → 合格档."""
        result = roic(12.5, 100, wacc=8)
        self.assertEqual(result['roic'], 12.5)
        self.assertEqual(result['tier'], '合格')
        self.assertTrue(result['wacc_applied'])
        self.assertIn('合格', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_qualified_no_wacc(self, mock_stdout):
        """10%~15% 且未提供 WACC → 合格档，未校验 WACC."""
        result = roic(12.5, 100)
        self.assertEqual(result['tier'], '合格')
        self.assertFalse(result['wacc_applied'])
        self.assertIn('未校验', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_between_5_and_10(self, mock_stdout):
        """5%~10% → 部分不达标（观察仓）."""
        result = roic(8, 100)
        self.assertEqual(result['roic'], 8.0)
        self.assertEqual(result['tier'], '部分不达标')
        self.assertIn('5%~10%', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_below_wacc(self, mock_stdout):
        """10%~15% 但 ROIC≤WACC → 审慎归位「部分不达标（观察仓）」."""
        result = roic(12, 100, wacc=15)
        self.assertEqual(result['tier'], '部分不达标')
        self.assertIn('ROIC≤WACC', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_veto_expanding(self, mock_stdout):
        """ROIC<5% 且扩产 → 不达标（一票否决）."""
        result = roic(3, 100, expanding=True)
        self.assertEqual(result['tier'], '不达标')
        self.assertIn('一票否决', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_below_5_not_expanding(self, mock_stdout):
        """ROIC<5% 不扩产 → 部分不达标（观察仓）."""
        result = roic(3, 100, expanding=False)
        self.assertEqual(result['tier'], '部分不达标')
        self.assertIn('不扩产', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_two_decimal_precision(self, mock_stdout):
        """1/3 × 100 → 33.33（精确至 2 位小数）."""
        result = roic(1, 3)
        self.assertEqual(result['roic'], 33.33)
        self.assertEqual(result['tier'], '优秀')

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_zero_denominator(self, mock_stdout):
        """投入资本 ≤ 0 → 拒绝计算，返回 N/A."""
        result = roic(10, 0)
        self.assertIsNone(result['roic'])
        self.assertEqual(result['tier'], 'N/A')
        self.assertIn('投入资本', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_roic_negative_nopat(self, mock_stdout):
        """NOPAT ≤ 0 → 仍计算并落 ROIC<5% 档，追加 NOPAT 非正."""
        result = roic(-5, 100)
        self.assertEqual(result['roic'], -5.0)
        self.assertEqual(result['tier'], '部分不达标')
        self.assertIn('NOPAT 非正', result['verdict'])


class TestIncrementalRoic(unittest.TestCase):
    """Test 增量 ROIC 投入资本回报率 (增量口径, P1-2 新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_incremental_roic_basic(self, mock_stdout):
        """ΔNOPAT=2.5, Δ投入资本=20 → 12.50%."""
        result = incremental_roic(10, 80, 12.5, 100, "2023", "2024")
        self.assertEqual(result['delta_roic'], 12.5)
        self.assertEqual(result['period_from'], '2023')
        self.assertEqual(result['period_to'], '2024')
        self.assertEqual(result['delta_nopat'], 2.5)
        self.assertEqual(result['delta_invested_capital'], 20.0)

    @patch('sys.stdout', new_callable=StringIO)
    def test_incremental_roic_two_decimal(self, mock_stdout):
        """ΔNOPAT=1, Δ投入资本=3 → 33.33（2 位小数）."""
        result = incremental_roic(1, 3, 2, 6)
        self.assertEqual(result['delta_roic'], 33.33)

    @patch('sys.stdout', new_callable=StringIO)
    def test_incremental_roic_zero_delta_ic(self, mock_stdout):
        """Δ投入资本 == 0 → 降级 N/A，非除零异常."""
        result = incremental_roic(10, 100, 12, 100)
        self.assertIsNone(result['delta_roic'])
        self.assertIn('分母非法', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_incremental_roic_negative_delta_ic(self, mock_stdout):
        """Δ投入资本 < 0（投入资本收缩）→ 降级 N/A."""
        result = incremental_roic(12, 100, 10, 80)
        self.assertIsNone(result['delta_roic'])
        self.assertIn('收缩', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_incremental_roic_negative_delta_nopat(self, mock_stdout):
        """Δ投入资本 > 0 且 ΔNOPAT < 0 → 负 delta_roic 并标注."""
        result = incremental_roic(12, 100, 10, 120)
        self.assertEqual(result['delta_roic'], -10.0)
        self.assertIn('ΔNOPAT 非正', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_incremental_roic_has_hint(self, mock_stdout):
        """输出附带科技股调整口径提示."""
        result = incremental_roic(10, 80, 12.5, 100)
        self.assertIn('tech_adjustment_hint', result)
        self.assertIn('研发费用化', result['tech_adjustment_hint'])


class TestWacc(unittest.TestCase):
    """Test 加权平均资本成本 WACC (P1-3 新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_basic(self, mock_stdout):
        """E=80/D=20/re=10/rd=5/t=0.25 → 8.75%，权重 80/20."""
        result = wacc(80, 20, 10, 5, 0.25)
        self.assertEqual(result['wacc'], 8.75)
        self.assertEqual(result['weights'], {'equity': 80.0, 'debt': 20.0})
        self.assertEqual(result['after_tax_debt_cost'], 3.75)
        self.assertEqual(result['warnings'], [])

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_two_decimal_rounding(self, mock_stdout):
        """E=1/D=3/re=10/rd=5/t=0.25 → 5.3125 舍入为 5.31."""
        result = wacc(1, 3, 10, 5, 0.25)
        self.assertEqual(result['wacc'], 5.31)
        self.assertEqual(result['weights']['equity'], 25.0)
        self.assertEqual(result['weights']['debt'], 75.0)

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_weights_sum_to_100(self, mock_stdout):
        """权重重算一致：equity + debt = 100."""
        result = wacc(33, 67, 10, 5, 0.25)
        self.assertAlmostEqual(
            result['weights']['equity'] + result['weights']['debt'], 100.0, places=2)

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_all_equity(self, mock_stdout):
        """全股权 D=0 → wacc=re，提示全股权口径."""
        result = wacc(100, 0, 10, 5, 0.25)
        self.assertEqual(result['wacc'], 10.0)
        self.assertEqual(result['weights'], {'equity': 100.0, 'debt': 0.0})
        self.assertTrue(any('全股权' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_all_debt(self, mock_stdout):
        """全债务 E=0 → wacc=rd×(1−t)，提示全债务口径."""
        result = wacc(0, 100, 10, 5, 0.25)
        self.assertEqual(result['wacc'], 3.75)
        self.assertEqual(result['weights'], {'equity': 0.0, 'debt': 100.0})
        self.assertTrue(any('全债务' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_zero_total(self, mock_stdout):
        """E+D ≤ 0 → 降级 N/A，非除零异常."""
        result = wacc(-10, -10, 10, 5, 0.25)
        self.assertIsNone(result['wacc'])
        self.assertIsNone(result['weights'])
        self.assertIsNone(result['after_tax_debt_cost'])
        self.assertTrue(any('分母非法' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_re_below_rd_warning(self, mock_stdout):
        """re < rd → 计入 warnings，不影响正常计算."""
        result = wacc(80, 20, 4, 5, 0.25)
        self.assertEqual(result['wacc'], 3.95)
        self.assertTrue(any('re < rd' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_tax_out_of_range(self, mock_stdout):
        """税率 t=1.0 → t ≥ 1 判定为异常并提示."""
        result = wacc(80, 20, 10, 5, 1.0)
        self.assertTrue(any('税率 t 超出' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_wacc_has_re_reference(self, mock_stdout):
        """输出附带 re 参考区间提示（复用 audit 币种护栏思想）."""
        result = wacc(80, 20, 10, 5, 0.25)
        self.assertIn('re_reference', result)
        self.assertIn('CNY', result['re_reference'])


class TestRuleOf40(unittest.TestCase):
    """Test Rule of 40 成长质量判定 (P1-4 新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_profit_basic(self, mock_stdout):
        """利润口径 30+25=55 ≥40 → 通过."""
        result = rule_of_40(30, profit_margin=25)
        self.assertEqual(result['rule_of_40'], 55.0)
        self.assertTrue(result['passed'])
        self.assertEqual(result['margin_type'], 'profit')
        self.assertEqual(result['warnings'], [])

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_fcf_boundary(self, mock_stdout):
        """FCF 口径 25+15=40 恰好边界 → 通过."""
        result = rule_of_40(25, fcf_margin=15)
        self.assertEqual(result['rule_of_40'], 40.0)
        self.assertTrue(result['passed'])
        self.assertEqual(result['margin_type'], 'fcf')

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_fail(self, mock_stdout):
        """利润口径 15+10=25 <40 → 不达标."""
        result = rule_of_40(15, profit_margin=10)
        self.assertEqual(result['rule_of_40'], 25.0)
        self.assertFalse(result['passed'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_negative_margin_warning(self, mock_stdout):
        """FCF 负利润率 50+(−15)=35 → 不达标且告警."""
        result = rule_of_40(50, fcf_margin=-15)
        self.assertEqual(result['rule_of_40'], 35.0)
        self.assertFalse(result['passed'])
        self.assertTrue(any('FCF 利润率为负' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_negative_growth_warning(self, mock_stdout):
        """负营收增速 (−10)+20=10 → 不达标且告警."""
        result = rule_of_40(-10, profit_margin=20)
        self.assertEqual(result['rule_of_40'], 10.0)
        self.assertFalse(result['passed'])
        self.assertTrue(any('营收增速为负' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_missing_margin(self, mock_stdout):
        """未提供口径 → 降级 N/A."""
        result = rule_of_40(30)
        self.assertIsNone(result['rule_of_40'])
        self.assertIsNone(result['passed'])
        self.assertIsNone(result['margin_type'])
        self.assertTrue(any('未提供' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_both_margin(self, mock_stdout):
        """利润与 FCF 口径同时提供 → 降级 N/A."""
        result = rule_of_40(30, profit_margin=25, fcf_margin=15)
        self.assertIsNone(result['rule_of_40'])
        self.assertIsNone(result['passed'])
        self.assertTrue(any('互斥' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_two_decimal_rounding(self, mock_stdout):
        """1.234 + 2.345 = 3.579 → 2 位小数舍入为 3.58."""
        result = rule_of_40(1.234, profit_margin=2.345)
        self.assertEqual(result['rule_of_40'], 3.58)

    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_of_40_inputs_echo(self, mock_stdout):
        """审计回显：未启用口径应为 None."""
        result = rule_of_40(30, profit_margin=25)
        self.assertEqual(result['inputs']['profit_margin'], 25.0)
        self.assertIsNone(result['inputs']['fcf_margin'])


class TestEvSales(unittest.TestCase):
    """Test 企业价值/营收倍数 EV/Sales (P1-5 新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_basic(self, mock_stdout):
        """800/150/50/200 → EV=900, EV/Sales=4.5."""
        result = ev_sales(800, 150, 50, 200)
        self.assertEqual(result['ev'], 900.0)
        self.assertEqual(result['ev_sales'], 4.5)
        self.assertEqual(result['warnings'], [])

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_two_decimal_rounding(self, mock_stdout):
        """EV/Sales 除不尽 → 2 位小数舍入."""
        result = ev_sales(100, 0, 0, 30)
        self.assertEqual(result['ev'], 100.0)
        self.assertEqual(result['ev_sales'], 3.33)

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_net_cash_negative_ev(self, mock_stdout):
        """净现金 100/0/150/50 → EV=-50, EV/Sales=-1.0 且告警净现金."""
        result = ev_sales(100, 0, 150, 50)
        self.assertEqual(result['ev'], -50.0)
        self.assertEqual(result['ev_sales'], -1.0)
        self.assertTrue(any('净现金' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_zero_ev(self, mock_stdout):
        """EV=0 现金恰好等于市值+负债 → EV/Sales=0 且告警."""
        result = ev_sales(100, 0, 100, 50)
        self.assertEqual(result['ev'], 0.0)
        self.assertEqual(result['ev_sales'], 0.0)
        self.assertTrue(any('EV = 0' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_zero_revenue(self, mock_stdout):
        """营收=0 → 降级 N/A."""
        result = ev_sales(800, 150, 50, 0)
        self.assertIsNone(result['ev'])
        self.assertIsNone(result['ev_sales'])
        self.assertTrue(any('营收 ≤ 0' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_negative_revenue(self, mock_stdout):
        """营收<0 → 降级 N/A."""
        result = ev_sales(800, 150, 50, -200)
        self.assertIsNone(result['ev'])
        self.assertIsNone(result['ev_sales'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_negative_debt_warning(self, mock_stdout):
        """负有息负债数据异常 → warnings 提示，仍正常计算."""
        result = ev_sales(800, -50, 50, 200)
        self.assertEqual(result['ev'], 700.0)
        self.assertEqual(result['ev_sales'], 3.5)
        self.assertTrue(any('有息负债为负' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_ev_sales_inputs_echo(self, mock_stdout):
        """审计回显四科目与 hint 存在."""
        result = ev_sales(800, 150, 50, 200)
        self.assertEqual(result['inputs']['market_cap'], 800.0)
        self.assertEqual(result['inputs']['debt'], 150.0)
        self.assertEqual(result['inputs']['cash'], 50.0)
        self.assertEqual(result['inputs']['revenue'], 200.0)
        self.assertIn('hint', result)
        self.assertIn('同业可比', result['hint'])


class TestAdjustedPeg(unittest.TestCase):
    """Test 调整后 PEG (研发费用加回核心经营利润口径) (P1-6 新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_basic(self, mock_stdout):
        """200/10/5/30 → adjusted_pe=13.33, adjusted_peg=0.44, tier=低估."""
        result = adjusted_peg(200, 10, 5, 30)
        self.assertEqual(result['adjusted_pe'], 13.33)
        self.assertEqual(result['adjusted_peg'], 0.44)
        self.assertEqual(result['tier'], '低估')
        self.assertEqual(result['warnings'], [])

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_tier_fair(self, mock_stdout):
        """1.0~1.2 → 合理档."""
        result = adjusted_peg(200, 10, 5, 13)
        # 调整后 PE=13.33, PEG=13.33/13=1.03 → 合理
        self.assertEqual(result['tier'], '合理')

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_tier_expensive(self, mock_stdout):
        """1.2~1.5 → 合理偏贵档."""
        result = adjusted_peg(200, 10, 5, 10)
        # 调整后 PE=13.33, PEG=13.33/10=1.33 → 合理偏贵
        self.assertEqual(result['tier'], '合理偏贵')

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_tier_overvalued(self, mock_stdout):
        """>1.5 → 高估档."""
        result = adjusted_peg(200, 10, 5, 8)
        # 调整后 PE=13.33, PEG=13.33/8=1.67 → 高估
        self.assertEqual(result['tier'], '高估')

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_over_2_verdict_hint(self, mock_stdout):
        """PEG>2 → tier 仍为高估，verdict 补充严重透支文案."""
        result = adjusted_peg(200, 10, 5, 5)
        # 调整后 PE=13.33, PEG=13.33/5=2.67 → 高估 + 严重透支提示
        self.assertEqual(result['tier'], '高估')
        self.assertIn('严重透支', result['verdict'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_negative_growth(self, mock_stdout):
        """增速≤0 → 降级 N/A."""
        result = adjusted_peg(200, 10, 5, -5)
        self.assertIsNone(result['adjusted_pe'])
        self.assertIsNone(result['adjusted_peg'])
        self.assertEqual(result['tier'], 'N/A')

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_still_loss(self, mock_stdout):
        """回加后仍亏损 → 降级 N/A."""
        result = adjusted_peg(200, -10, 5, 30)
        self.assertIsNone(result['adjusted_pe'])
        self.assertIsNone(result['adjusted_peg'])
        self.assertEqual(result['tier'], 'N/A')
        self.assertTrue(any('回加后仍亏损' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_negative_rnd_warning(self, mock_stdout):
        """负研发 → warnings 提示，仍正常计算."""
        result = adjusted_peg(200, 15, -5, 30)
        # 调整后 PE=200/10=20.0, PEG=20/30=0.67 → 低估
        self.assertEqual(result['adjusted_pe'], 20.0)
        self.assertEqual(result['tier'], '低估')
        self.assertTrue(any('研发费用为负' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_adjusted_peg_inputs_echo(self, mock_stdout):
        """审计回显四科目存在."""
        result = adjusted_peg(200, 10, 5, 30)
        self.assertEqual(result['inputs']['market_cap'], 200.0)
        self.assertEqual(result['inputs']['core_operating_profit'], 10.0)
        self.assertEqual(result['inputs']['rnd_expense'], 5.0)
        self.assertEqual(result['inputs']['growth'], 30.0)


class TestDcf(unittest.TestCase):
    """Test 简化三阶段 DCF 估值 (P1-7 新增)."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_standard(self, mock_stdout):
        """标准 CNY 样例：pv/per_share/margin/verdict/audit 精确校验."""
        result = dcf(100, 10, 5, 5, 2, 9, 10, 1000, currency='CNY')
        self.assertEqual(result['pv'], 2275.36)
        self.assertEqual(result['per_share'], 227.54)
        self.assertEqual(result['margin_of_safety_pct'], 56.05)
        self.assertEqual(result['verdict'], '低估（市值≤保守DCF 80%）')
        self.assertTrue(result['audit']['passed'])
        self.assertEqual(result['warnings'], [])

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_overvalued(self, mock_stdout):
        """市值 3000 → margin 为负，判定高估."""
        result = dcf(100, 10, 5, 5, 2, 9, 10, 3000)
        self.assertAlmostEqual(result['margin_of_safety_pct'], -31.85, places=2)
        self.assertEqual(result['verdict'], '高估（市值高于DCF）')

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_reasonable_margin(self, mock_stdout):
        """市值 2000 → 0≤margin<20，判定合理（安全边际<20%）."""
        result = dcf(100, 10, 5, 5, 2, 9, 10, 2000)
        self.assertAlmostEqual(result['margin_of_safety_pct'], 12.10, places=2)
        self.assertEqual(result['verdict'], '合理（安全边际<20%）')

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_years_fade_zero(self, mock_stdout):
        """years_fade=0 → 纯两阶段（高增 + 永续）精确校验."""
        result = dcf(100, 10, 5, 0, 2, 9, 10, 1000)
        self.assertEqual(result['pv'], 2039.15)
        self.assertEqual(result['per_share'], 203.92)
        self.assertEqual(result['margin_of_safety_pct'], 50.96)

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_model_invalid_terminal_ge_r(self, mock_stdout):
        """g_terminal ≥ r → 模型失效，现值/每股/边际全降级 N/A."""
        result = dcf(100, 10, 5, 5, 10, 9, 10, 1000)
        self.assertIsNone(result['pv'])
        self.assertIsNone(result['per_share'])
        self.assertIsNone(result['margin_of_safety_pct'])
        self.assertEqual(result['verdict'], 'N/A')
        self.assertTrue(any('戈登终值模型失效' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_fcf_nonpositive(self, mock_stdout):
        """FCF ≤ 0 → 模型失效."""
        result = dcf(0, 10, 5, 5, 2, 9, 10, 1000)
        self.assertIsNone(result['pv'])
        self.assertEqual(result['verdict'], 'N/A')

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_audit_c1_r_out_of_band(self, mock_stdout):
        """r=10 超出 CNY 区间 → C1 告警."""
        result = dcf(100, 10, 5, 5, 2, 10, 10, 1000, currency='CNY')
        self.assertFalse(result['audit']['passed'])
        self.assertTrue(any('C1' in a for a in result['audit']['alerts']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_audit_c1_rf_mismatch(self, mock_stdout):
        """rf=5 与 CNY 基准 1.7 不符 → C1 无风险利率告警."""
        result = dcf(100, 10, 5, 5, 2, 9, 10, 1000, currency='CNY', rf=5)
        self.assertFalse(result['audit']['passed'])
        self.assertTrue(any('无风险利率' in a for a in result['audit']['alerts']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_audit_c2_spread(self, mock_stdout):
        """r-g < 5pct → C2 告警，但模型有效不降级."""
        result = dcf(100, 10, 5, 5, 5, 9, 10, 1000)
        self.assertFalse(result['audit']['passed'])
        self.assertTrue(any('C2' in a for a in result['audit']['alerts']))
        self.assertIsNotNone(result['pv'])

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_audit_c3_risk_placement(self, mock_stdout):
        """离散风险写进折现率 → C3 告警."""
        result = dcf(100, 10, 5, 5, 2, 9, 10, 1000,
                     discrete_risks='退市风险:折现率')
        self.assertFalse(result['audit']['passed'])
        self.assertTrue(any('C3' in a for a in result['audit']['alerts']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_shares_zero(self, mock_stdout):
        """shares=0 → 每股价值 N/A，现值正常."""
        result = dcf(100, 10, 5, 5, 2, 9, 0, 1000)
        self.assertIsNotNone(result['pv'])
        self.assertIsNone(result['per_share'])
        self.assertTrue(any('总股本' in w for w in result['warnings']))

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_market_cap_zero(self, mock_stdout):
        """market_cap=0 → 安全边际 N/A."""
        result = dcf(100, 10, 5, 5, 2, 9, 10, 0)
        self.assertIsNotNone(result['pv'])
        self.assertIsNone(result['margin_of_safety_pct'])
        self.assertEqual(result['verdict'], 'N/A')

    @patch('sys.stdout', new_callable=StringIO)
    def test_dcf_inputs_echo(self, mock_stdout):
        """inputs 回显字段齐全."""
        result = dcf(100, 10, 5, 5, 2, 9, 10, 1000, currency='CNY', rf=2)
        inputs = result['inputs']
        self.assertEqual(inputs['fcf'], 100.0)
        self.assertEqual(inputs['g_high'], 10.0)
        self.assertEqual(inputs['years_high'], 5)
        self.assertEqual(inputs['years_fade'], 5)
        self.assertEqual(inputs['g_terminal'], 2.0)
        self.assertEqual(inputs['r'], 9.0)
        self.assertEqual(inputs['shares'], 10.0)
        self.assertEqual(inputs['market_cap'], 1000.0)
        self.assertEqual(inputs['currency'], 'CNY')
        self.assertEqual(inputs['rf'], 2.0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_valuation_negative_eps(self, mock_stdout):
        """Test valuation with negative EPS."""
        result = verify_valuation(price=510, eps=-10)
        self.assertIn('PE', result)
        self.assertAlmostEqual(result['PE'], -51.0, places=1)

    @patch('sys.stdout', new_callable=StringIO)
    def test_verify_market_cap_zero_shares(self, mock_stdout):
        """Test market cap with zero shares."""
        result = verify_market_cap(510, 0, 0, 'HKD')
        self.assertTrue(result)

    @patch('sys.stdout', new_callable=StringIO)
    def test_cross_validate_single_source(self, mock_stdout):
        """Test cross-validation with single source."""
        source_values = {'年报': 7518}
        result = cross_validate('revenue', source_values, '亿')
        self.assertTrue(result['all_consistent'])
        self.assertEqual(result['consensus'], 7518)


class TestCLI(unittest.TestCase):
    """Test CLI interface (basic smoke tests)."""

    def test_cli_verify_market_cap(self):
        """Test CLI verify-market-cap command."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'verify-market-cap',
             '--price', '510', '--shares', '9.11e9', '--reported', '4.65e12',
             '--currency', 'HKD'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('市值验算', result.stdout)

    def test_cli_verify_valuation(self):
        """Test CLI verify-valuation command."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'verify-valuation',
             '--price', '510', '--eps', '23.5'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('估值指标验算', result.stdout)

    def test_cli_calc(self):
        """Test CLI calc command."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'calc',
             '--expr', '510 * 9.11e9'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('精确计算', result.stdout)

    def test_cli_roic(self):
        """Test CLI roic command (P1-1 新增)."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'roic',
             '--nopat', '12.5', '--invested-capital', '100', '--wacc', '8'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('ROIC 投入资本回报率', result.stdout)
        self.assertIn('合格', result.stdout)

    def test_cli_incremental_roic(self):
        """Test CLI incremental-roic command (P1-2 新增)."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'incremental-roic',
             '--nopat-from', '10', '--invested-capital-from', '80',
             '--nopat-to', '12.5', '--invested-capital-to', '100'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('增量 ROIC 投入资本回报率', result.stdout)

    def test_cli_wacc(self):
        """Test CLI wacc command (P1-3 新增)."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'wacc',
             '--equity-value', '80', '--debt-value', '20',
             '--cost-equity', '10', '--cost-debt', '5', '--tax-rate', '0.25'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('WACC 加权平均资本成本', result.stdout)
        self.assertIn('8.75', result.stdout)

    def test_cli_rule_of_40(self):
        """Test CLI rule-of-40 command (P1-4 新增)."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'rule-of-40',
             '--revenue-growth', '30', '--profit-margin', '25'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('Rule of 40 成长质量判定', result.stdout)
        self.assertIn('55.0', result.stdout)

    def test_cli_ev_sales(self):
        """Test CLI ev-sales command (P1-5 新增)."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'ev-sales',
             '--market-cap', '800', '--debt', '150',
             '--cash', '50', '--revenue', '200'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('企业价值/营收倍数', result.stdout)
        self.assertIn('4.5', result.stdout)

    def test_cli_adjusted_peg(self):
        """Test CLI adjusted-peg command (P1-6 新增)."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'adjusted-peg',
             '--market-cap', '200', '--core-operating-profit', '10',
             '--rnd-expense', '5', '--growth', '30'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('调整后 PEG', result.stdout)
        self.assertIn('0.44', result.stdout)

    def test_cli_dcf(self):
        """Test CLI dcf command (P1-7 新增)."""
        import subprocess
        result = subprocess.run(
            ['python', 'tools/common/financial_rigor.py', 'dcf',
             '--fcf', '100', '--g-high', '10', '--years-high', '5',
             '--years-fade', '5', '--g-terminal', '2', '--r', '9',
             '--shares', '10', '--market-cap', '1000', '--currency', 'CNY'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('DCF 简化三阶段估值', result.stdout)
        self.assertIn('2275.36', result.stdout)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestExactDecimal))
    suite.addTests(loader.loadTestsFromTestCase(TestMarketCapVerification))
    suite.addTests(loader.loadTestsFromTestCase(TestValuationVerification))
    suite.addTests(loader.loadTestsFromTestCase(TestCrossValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestBenfordCheck))
    suite.addTests(loader.loadTestsFromTestCase(TestExactCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestThreeScenarioValuation))
    suite.addTests(loader.loadTestsFromTestCase(TestPegRatio))
    suite.addTests(loader.loadTestsFromTestCase(TestPsgRatio))
    suite.addTests(loader.loadTestsFromTestCase(TestPePercentile))
    suite.addTests(loader.loadTestsFromTestCase(TestImpliedGrowth))
    suite.addTests(loader.loadTestsFromTestCase(TestRoic))
    suite.addTests(loader.loadTestsFromTestCase(TestIncrementalRoic))
    suite.addTests(loader.loadTestsFromTestCase(TestWacc))
    suite.addTests(loader.loadTestsFromTestCase(TestRuleOf40))
    suite.addTests(loader.loadTestsFromTestCase(TestEvSales))
    suite.addTests(loader.loadTestsFromTestCase(TestAdjustedPeg))
    suite.addTests(loader.loadTestsFromTestCase(TestDcf))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestCLI))

    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("测试摘要 (Test Summary)")
    print("=" * 70)
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败，请检查错误信息")

    return result.wasSuccessful()


if __name__ == '__main__':
    import os
    # Change to workspace directory (dynamic, cross-platform)
    os.chdir(_PROJECT_ROOT)

    # Run tests
    success = run_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
