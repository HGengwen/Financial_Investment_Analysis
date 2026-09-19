#!/usr/bin/env python3
"""Unit tests for terminal_value.py（P5-1 补缺 G-1）。

覆盖对象：tools/common/terminal_value.py
  1. 8 个核心纯函数：exit_pe / irr_from_terminal / rescale_irr / weighted_stats /
     evaluate / summarize / load_companies / warn_spread
  2. cmd_audit 三条硬约束分支：C1 币种一致性 / C2 分母宽度 / C3 离散风险归属
  3. 常量护栏：MIN_SPREAD / CURRENCY_BANDS / RISK_PLACEMENT_OK / _BAD / _WARN

测试风格：与 tests/ 目录既有惯例一致——unittest.TestCase + StringIO 重定向，
不依赖网络、不写缓存、不修改 tools/ 代码。

口径说明（与实现严格对齐）：
  - CURRENCY_BANDS["CNY"] = r∈[0.06,0.09]，g_max=0.02（基准档），乐观档另放宽 1pct 至 0.03。
    故「C1 通过」的合法 g 组合须满足 基准档 ≤0.02 且 max(g) ≤0.03，本文件用
    (0.005, 0.020, 0.030) 作为 C1 合法基准组。
  - warn_spread(0.05) == ""（0.05 恰在下限，不算「⚠窄」）。
  - summarize 的 ratio = (mean - rf*100) / sd，mean/sd 单位为百分点。
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# Add project root to path for imports (dynamic, cross-platform)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common import terminal_value as tv  # noqa: E402

# C1 合法的 g 组合（CNY：基准 0.020 ≤ g_max 0.02，乐观 0.030 ≤ g_max+0.01）
G_OK = "0.005,0.020,0.030"


class TestExitPe(unittest.TestCase):
    """exit_pe(roic, g, r) 永续增长终值 PE。"""

    def test_positive_spread(self) -> None:
        """正常分母：PE = 派息率 / (r-g)。"""
        # roic=0.20, g=0.04, r=0.10 → 留存=0.20, 分子=0.80, 分母=0.06
        pe, ret, num, spread = tv.exit_pe(0.20, 0.04, 0.10)
        self.assertAlmostEqual(spread, 0.06)
        self.assertAlmostEqual(ret, 0.20)
        self.assertAlmostEqual(num, 0.80)
        self.assertAlmostEqual(pe, 0.80 / 0.06)

    def test_zero_growth(self) -> None:
        """g=0 → 留存 0、分子 1、PE = 1/r。"""
        pe, ret, num, spread = tv.exit_pe(0.20, 0.0, 0.10)
        self.assertAlmostEqual(ret, 0.0)
        self.assertAlmostEqual(num, 1.0)
        self.assertAlmostEqual(pe, 1.0 / 0.10)

    def test_spread_zero_returns_none(self) -> None:
        """r == g → 分母为 0，模型失效，pe=None。"""
        pe, ret, num, spread = tv.exit_pe(0.20, 0.10, 0.10)
        self.assertIsNone(pe)
        self.assertAlmostEqual(spread, 0.0)

    def test_spread_negative_returns_none(self) -> None:
        """g > r → 分母为负，模型失效，pe=None。"""
        pe, *_ = tv.exit_pe(0.20, 0.12, 0.10)
        self.assertIsNone(pe)

    def test_equal_roic_g_gives_zero_pe(self) -> None:
        """g == roic → 留存 1、分子 0 → PE = 0。"""
        pe, ret, num, _ = tv.exit_pe(0.20, 0.20, 0.25)
        self.assertAlmostEqual(ret, 1.0)
        self.assertAlmostEqual(num, 0.0)
        self.assertAlmostEqual(pe, 0.0)

    def test_higher_roic_raises_numerator(self) -> None:
        """同 spread 下 roic 越高 → 留存越低 → 分子越高。"""
        _, _, num_low, _ = tv.exit_pe(0.10, 0.03, 0.09)
        _, _, num_high, _ = tv.exit_pe(0.30, 0.03, 0.09)
        self.assertGreater(num_high, num_low)


class TestIrrFromTerminal(unittest.TestCase):
    """irr_from_terminal(profit_2036, mcap, pe, years, payout)。"""

    def test_double_money_ten_years(self) -> None:
        """10 年总倍数翻倍 → 几何年化 = 2^(1/10)-1。"""
        irr = tv.irr_from_terminal(200, 100, 1, years=10, payout=0.0)
        self.assertAlmostEqual(irr, 2 ** 0.1 - 1, places=10)

    def test_payout_adds_linearly(self) -> None:
        """payout 直接线性加在几何回报上（报告口径，不复利）。"""
        base = tv.irr_from_terminal(150, 100, 1, years=10, payout=0.0)
        with_pay = tv.irr_from_terminal(150, 100, 1, years=10, payout=0.05)
        self.assertAlmostEqual(with_pay - base, 0.05)

    def test_shorter_years_raises_irr(self) -> None:
        """同总倍数下，年限越短年化越高。"""
        long = tv.irr_from_terminal(200, 100, 1, years=10, payout=0.0)
        short = tv.irr_from_terminal(200, 100, 1, years=5, payout=0.0)
        self.assertGreater(short, long)

    def test_loss_case(self) -> None:
        """终值市值低于今日市值 → 负 IRR。"""
        irr = tv.irr_from_terminal(50, 100, 1, years=10, payout=0.0)
        self.assertLess(irr, 0.0)


class TestRescaleIrr(unittest.TestCase):
    """rescale_irr(irr_base, pe_base, pe_new, k, years)。"""

    def test_same_pe_returns_base(self) -> None:
        """退出倍数不变 → IRR 恒等。"""
        self.assertAlmostEqual(tv.rescale_irr(0.09, 20, 20, 0.0), 0.09, places=10)

    def test_higher_pe_raises_irr(self) -> None:
        """退出倍数上调 → IRR 上升。"""
        base = tv.rescale_irr(0.09, 20, 20, 0.0)
        higher = tv.rescale_irr(0.09, 20, 30, 0.0)
        self.assertGreater(higher, base)

    def test_k_has_no_effect_when_pe_unchanged(self) -> None:
        """退出倍数不变时，k 在复利项内外相互抵消 → IRR 恒等。"""
        self.assertAlmostEqual(tv.rescale_irr(0.09, 20, 20, 0.03), 0.09, places=10)

    def test_k_dampens_pe_driven_gain(self) -> None:
        """k 在复利项内扣除：PE 上调时 k 越大资本利得被摊薄越多。

        差异 = k * (1 - (PE_new/PE_base)^(1/years))，故 PE 上调时差异为负。
        """
        no_k = tv.rescale_irr(0.09, 20, 25, 0.0)
        with_k = tv.rescale_irr(0.09, 20, 25, 0.03)
        ratio_root = (25 / 20) ** 0.1
        self.assertAlmostEqual(with_k - no_k, 0.03 * (1.0 - ratio_root))
        self.assertLess(with_k, no_k)


class TestWeightedStats(unittest.TestCase):
    """weighted_stats(values, probs) 概率加权期望与标准差。"""

    def test_mean(self) -> None:
        mean, _ = tv.weighted_stats([1, 2], [0.5, 0.5])
        self.assertAlmostEqual(mean, 1.5)

    def test_sd_zero_for_constant(self) -> None:
        _, sd = tv.weighted_stats([5, 5], [0.5, 0.5])
        self.assertAlmostEqual(sd, 0.0)

    def test_sd_positive_for_spread(self) -> None:
        _, sd = tv.weighted_stats([0, 10], [0.5, 0.5])
        self.assertAlmostEqual(sd, 5.0)

    def test_skewed_weights(self) -> None:
        mean, _ = tv.weighted_stats([1, 6], [0.9, 0.1])
        self.assertAlmostEqual(mean, 1.5)


class TestEvaluate(unittest.TestCase):
    """evaluate(spec, r, g_shift, years) 三档退出 PE / IRR。"""

    SPEC = dict(roic=0.20, g=(0.015, 0.030, 0.040),
                p=(0.35, 0.50, 0.15), irr10=(0.3, 9.3, 15.4), k=0.020)

    def test_three_rows_labels(self) -> None:
        rows = tv.evaluate(self.SPEC, 0.10)
        self.assertEqual([row["label"] for row in rows], ["悲观", "基准", "乐观"])

    def test_g_applies_g_shift(self) -> None:
        rows = tv.evaluate(self.SPEC, 0.10, g_shift=-0.01)
        self.assertAlmostEqual(rows[1]["g"], 0.030 - 0.01)

    def test_rows_carry_required_keys(self) -> None:
        rows = tv.evaluate(self.SPEC, 0.10)
        for row in rows:
            self.assertIn("pe", row)
            self.assertIn("irr", row)
            self.assertIn("retention", row)
            self.assertIn("spread", row)

    def test_no_shift_base_pe_is_finite(self) -> None:
        rows = tv.evaluate(self.SPEC, 0.10, g_shift=0.0)
        self.assertIsNotNone(rows[1]["pe"])

    def test_extreme_g_makes_optimistic_invalid(self) -> None:
        """乐观档 g 超过 r → 该档 pe 为 None（模型失效）。"""
        bad = dict(roic=0.5, g=(0.03, 0.09, 0.105), p=(0.3, 0.4, 0.3),
                   irr10=(1.0, 5.0, 9.0), k=0.0)
        rows = tv.evaluate(bad, 0.10)
        self.assertIsNone(rows[2]["pe"])
        self.assertIsNone(rows[2]["irr"])


class TestSummarize(unittest.TestCase):
    """summarize(rows, probs, rf)：期望 IRR / 标准差 / 风险调整后回报。"""

    PROBS = [0.5, 0.3, 0.2]

    @staticmethod
    def _rows():
        return [
            dict(label="悲观", g=0.0, pe=10.0, irr=0.02, retention=0.0,
                 numerator=1.0, spread=0.1),
            dict(label="基准", g=0.0, pe=10.0, irr=0.06, retention=0.0,
                 numerator=1.0, spread=0.1),
            dict(label="乐观", g=0.0, pe=10.0, irr=0.10, retention=0.0,
                 numerator=1.0, spread=0.1),
        ]

    def test_mean(self) -> None:
        mean, _, _ = tv.summarize(self._rows(), self.PROBS, 0.02)
        self.assertAlmostEqual(mean, 0.02 * 0.5 + 0.06 * 0.3 + 0.10 * 0.2)

    def test_none_when_any_irr_missing(self) -> None:
        """任一档失效 → 三项全部不可用。"""
        rows = self._rows()
        rows[1]["irr"] = None
        mean, sd, ratio = tv.summarize(rows, self.PROBS, 0.02)
        self.assertIsNone(mean)
        self.assertIsNone(sd)
        self.assertIsNone(ratio)

    def test_ratio_scales_rf_to_percent(self) -> None:
        """ratio = (mean - rf*100) / sd（rf 由小数换算为百分点）。"""
        rows = self._rows()
        mean, sd, ratio = tv.summarize(rows, self.PROBS, 0.02)
        exp_mean, exp_sd = tv.weighted_stats([r["irr"] for r in rows], self.PROBS)
        self.assertAlmostEqual(mean, exp_mean)
        self.assertAlmostEqual(sd, exp_sd)
        self.assertIsNotNone(ratio)
        self.assertAlmostEqual(ratio, (exp_mean - 2.0) / exp_sd)

    def test_ratio_none_when_sd_zero(self) -> None:
        """三档 IRR 相同 → sd=0 → ratio 不可计算（None）。"""
        rows = self._rows()
        for row in rows:
            row["irr"] = 0.05
        mean, sd, ratio = tv.summarize(rows, self.PROBS, 0.02)
        self.assertAlmostEqual(sd, 0.0)
        self.assertIsNone(ratio)


class TestLoadCompanies(unittest.TestCase):
    """load_companies(path)：JSON 载入，缺 path 返回 PRESET。"""

    def test_empty_path_returns_preset(self) -> None:
        self.assertEqual(tv.load_companies(""), tv.PRESET)

    def test_none_path_returns_preset(self) -> None:
        self.assertEqual(tv.load_companies(None), tv.PRESET)

    def test_json_load_converts_types(self) -> None:
        """g/p/irr10 由 list 转为 tuple，roic 保持数值。"""
        payload = {"X": {"roic": 0.2, "g": [0.01, 0.02, 0.03],
                         "p": [0.3, 0.5, 0.2], "irr10": [1, 2, 3], "k": 0.01}}
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            os.close(fd)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            out = tv.load_companies(path)
            self.assertEqual(out["X"]["roic"], 0.2)
            self.assertEqual(tuple(out["X"]["g"]), (0.01, 0.02, 0.03))
            self.assertEqual(tuple(out["X"]["irr10"]), (1, 2, 3))
        finally:
            os.remove(path)

    def test_absent_k_defaults_to_zero(self) -> None:
        payload = {"X": {"roic": 0.2, "g": [0, 0, 0], "p": [1, 0, 0], "irr10": [1, 2, 3]}}
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            os.close(fd)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            out = tv.load_companies(path)
            self.assertEqual(out["X"]["k"], 0.0)
        finally:
            os.remove(path)


class TestWarnSpread(unittest.TestCase):
    """warn_spread(spread) 分母宽度体检标记。"""

    def test_nonpositive_invalid(self) -> None:
        self.assertEqual(tv.warn_spread(0.0), "✗失效")
        self.assertEqual(tv.warn_spread(-0.01), "✗失效")

    def test_below_min_spread_narrow(self) -> None:
        self.assertEqual(tv.warn_spread(0.02), "⚠窄")

    def test_at_min_spread_not_flagged(self) -> None:
        """0.05 恰在下限，按 spread < MIN_SPREAD 判定 → 不打标。"""
        self.assertEqual(tv.warn_spread(0.05), "")

    def test_above_min_spread_ok(self) -> None:
        self.assertEqual(tv.warn_spread(0.06), "")


class TestConstants(unittest.TestCase):
    """MIN_SPREAD / CURRENCY_BANDS / 风险归属常量护栏。"""

    def test_min_spread_value(self) -> None:
        self.assertEqual(tv.MIN_SPREAD, 0.05)

    def test_currency_bands_have_required_keys(self) -> None:
        self.assertIn("CNY", tv.CURRENCY_BANDS)
        self.assertIn("USD", tv.CURRENCY_BANDS)
        for band in tv.CURRENCY_BANDS.values():
            for key in ("r", "g_max", "rf", "note"):
                self.assertIn(key, band)

    def test_currency_bands_ranges_ordered(self) -> None:
        for band in tv.CURRENCY_BANDS.values():
            self.assertLess(band["r"][0], band["r"][1])

    def test_risk_placement_sets(self) -> None:
        self.assertIn("情景", tv.RISK_PLACEMENT_OK)
        self.assertIn("尾部档", tv.RISK_PLACEMENT_OK)
        self.assertIn("折现率", tv.RISK_PLACEMENT_BAD)
        self.assertIn("beta", tv.RISK_PLACEMENT_BAD)
        self.assertIn("未建模", tv.RISK_PLACEMENT_WARN)

    def test_bad_and_ok_disjoint(self) -> None:
        self.assertFalse(tv.RISK_PLACEMENT_OK & tv.RISK_PLACEMENT_BAD)


class _AuditRunner:
    """cmd_audit 的可测封装：构造 args 命名空间并捕获 stdout/stderr。"""

    @staticmethod
    def build(**over):
        base = dict(currency="CNY", r=0.08, roic=0.20, g=G_OK,
                    rf=None, beta=1.0, beta_justification=None,
                    discrete_risks="", upside_only=False)
        base.update(over)
        return type("Args", (), base)()

    def run(self, **over):
        """执行一次 cmd_audit，返回 (退出码, stdout, stderr)。"""
        args = self.build(**over)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = tv.cmd_audit(args)
        return code, out.getvalue(), err.getvalue()


class TestAudit(unittest.TestCase):
    """cmd_audit 三条硬约束分支（C1 币种 / C2 分母宽度 / C3 离散风险归属）。"""

    def setUp(self) -> None:
        self.runner = _AuditRunner()

    def test_pass_all(self) -> None:
        """三条硬约束全过 → 退出码 0 且打印【准出】。"""
        code, out, _ = self.runner.run()
        self.assertEqual(code, 0)
        self.assertIn("【准出】", out)

    def test_c1_r_out_of_band_fails(self) -> None:
        code, out, _ = self.runner.run(r=0.12)
        self.assertEqual(code, 1)
        self.assertIn("C1", out)

    def test_c1_g_above_max_fails(self) -> None:
        """基准档 g 超过币种上限（CNY 0.02）→ C1 不通过。"""
        code, out, _ = self.runner.run(r=0.09, g="0.01,0.03,0.04")
        self.assertEqual(code, 1)
        self.assertIn("C1", out)

    def test_c1_rf_mismatch_fails(self) -> None:
        """--rf 与币种基准 Rf 偏差 >0.5pct → C1 不通过。"""
        code, out, _ = self.runner.run(rf=0.12)
        self.assertEqual(code, 1)
        self.assertIn("C1", out)

    def test_c1_rf_within_tolerance_passes(self) -> None:
        """--rf 偏差 ≤0.5pct 容忍。"""
        code, _, _ = self.runner.run(rf=0.020)
        self.assertEqual(code, 0)

    def test_c2_g_equals_r_invalid(self) -> None:
        """任一分母 ≤0 → C2 不通过。"""
        code, out, _ = self.runner.run(r=0.10, g="0.10,0.10,0.10")
        self.assertEqual(code, 1)
        self.assertIn("C2", out)

    def test_c2_narrow_without_upside_only_fails(self) -> None:
        """r 取下沿 0.06 时分母跌破 5pct，未声明 --upside-only → C2 打回。"""
        code, out, _ = self.runner.run(r=0.06)
        self.assertEqual(code, 1)
        self.assertIn("C2", out)

    def test_c2_narrow_with_upside_only_warns(self) -> None:
        """同一组合加 --upside-only → 降级为警告，整体准出。"""
        code, out, _ = self.runner.run(r=0.06, upside_only=True)
        self.assertEqual(code, 0)
        self.assertIn("⚠", out)
        self.assertIn("【准出】", out)

    def test_c3_beta_deviation_requires_justification(self) -> None:
        code, out, _ = self.runner.run(beta=1.1, beta_justification=None)
        self.assertEqual(code, 1)
        self.assertIn("C3", out)

    def test_c3_beta_justified_passes(self) -> None:
        code, _, _ = self.runner.run(beta=1.1, beta_justification="自下而上基本面β")
        self.assertEqual(code, 0)

    def test_c3_risk_in_discount_fails(self) -> None:
        """离散风险被放进折现率 → C3 打回。"""
        code, out, _ = self.runner.run(discrete_risks="退市:折现率")
        self.assertEqual(code, 1)
        self.assertIn("C3", out)

    def test_c3_risk_in_scenario_passes(self) -> None:
        code, out, _ = self.runner.run(discrete_risks="退市:情景")
        self.assertEqual(code, 0)
        self.assertIn("退市 → 情景", out)

    def test_c3_risk_unmodeled_warns_only(self) -> None:
        """归属「未建模」→ 仅警告，不阻断准出。"""
        code, out, _ = self.runner.run(discrete_risks="断供:未建模")
        self.assertEqual(code, 0)
        self.assertIn("⚠", out)

    def test_c3_malformed_risk_item_fails(self) -> None:
        code, out, _ = self.runner.run(discrete_risks="没冒号")
        self.assertEqual(code, 1)
        self.assertIn("C3", out)

    def test_c3_unknown_placement_fails(self) -> None:
        code, out, _ = self.runner.run(discrete_risks="退市:随便写")
        self.assertEqual(code, 1)
        self.assertIn("C3", out)

    def test_unknown_currency_exits_one(self) -> None:
        """未知币种 → 直接退出码 1，提示写 stderr。"""
        code, _, err = self.runner.run(currency="EUR")
        self.assertEqual(code, 1)
        self.assertIn("未知币种", err)


class TestCli(unittest.TestCase):
    """CLI 层 smoke test：子命令在合法输入下返回 0。"""

    def test_cmd_pe_smoke(self) -> None:
        args = type("Args", (), dict(roic=0.2, g=0.04, r=0.10))()
        with redirect_stdout(io.StringIO()):
            code = tv.cmd_pe(args)
        self.assertEqual(code, 0)

    def test_cmd_pe_invalid_model_returns_one(self) -> None:
        """分母 ≤0 → cmd_pe 返回 1（模型失效）。"""
        args = type("Args", (), dict(roic=0.2, g=0.12, r=0.10))()
        with redirect_stdout(io.StringIO()):
            code = tv.cmd_pe(args)
        self.assertEqual(code, 1)

    def test_cmd_irr_smoke(self) -> None:
        args = type("Args", (), dict(profit=200.0, mcap=100.0, pe=1.0,
                                     years=10, payout=0.0))()
        with redirect_stdout(io.StringIO()):
            code = tv.cmd_irr(args)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
