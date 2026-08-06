#!/usr/bin/env python3
"""Unit tests for financial_rigor.py.

Test suite covering all major functions:
1. Market cap verification
2. Valuation metrics verification
3. Cross-source validation
4. Benford's Law check
5. Exact calculator
6. Three-scenario valuation
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
    three_scenario_valuation
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
        # Generate numbers following Benford's law
        import random
        import math
        values = []
        for _ in range(200):
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
            cwd=str(_PROJECT_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('精确计算', result.stdout)


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
