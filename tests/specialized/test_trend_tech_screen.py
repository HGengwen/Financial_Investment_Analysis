#!/usr/bin/env python3
"""Unit tests for trend_tech_screen.py 打分引擎。

覆盖 mid-trend-tech-screen 阶段一新增的评分引擎骨架：
1. 五维加权打分（技能文件 A/B/C 示例精确复现）
2. 地缘二维修正矩阵系数
3. 技术面止损校验（独立否决：红牌/预警/通过）
4. 评级映射边界
5. 批量两轮（行业景气一致性 ±2）
6. Markdown 报告生成
"""

import sys
import unittest
from pathlib import Path

# Add project root to path for imports (dynamic, cross-platform)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.specialized.trend_tech_screen import (
    CYCLE_WEIGHTS,
    GEO_FACTOR,
    DEFAULT_CYCLE,
    R8_MAX_SCORE,
    R8_COMPONENTS,
    parse_r8,
    r8_eval,
    downgrade_rating,
    score_company,
    tech_check,
    batch_score,
    build_markdown,
    GeoEval,
    TechData,
)


def _mk_geo(x: str = "高", y: str = "高") -> GeoEval:
    """构造地缘二维评估对象."""
    return GeoEval(x=x, y=y)


def _mk_tech(above200=True, above50=True, volume=False) -> TechData:
    """构造技术面数据对象."""
    return TechData(close_above_ma200=above200, close_above_ma50=above50,
                    volume_above_15x=volume)


def _mk_r8(comm=0.0, space=0.0, endorse=0.0, patent=0.0, mgmt=0.0) -> dict:
    """构造 R8 在研项目五子分数 dict."""
    return {
        "商业化确定性": comm,
        "市场空间": space,
        "外部背书": endorse,
        "专利验证": patent,
        "管理层一致性": mgmt,
    }


class TestCycleWeights(unittest.TestCase):
    """Test 周期权重配置（五维合计为 100，需求爆发/技术跃迁配对制）。"""

    def test_default_cycle_is_boom(self):
        """默认周期为需求爆发期."""
        self.assertEqual(DEFAULT_CYCLE, "需求爆发期")

    def test_boom_weights_sum_100(self):
        """需求爆发期五维权重合计 100."""
        self.assertEqual(sum(CYCLE_WEIGHTS["需求爆发期"].values()), 100)

    def test_tech_jump_weights_sum_100(self):
        """技术跃迁期五维权重合计 100."""
        self.assertEqual(sum(CYCLE_WEIGHTS["技术跃迁期"].values()), 100)

    def test_boom_pairs(self):
        """需求爆发期：景气 42 / 研发 18（配对调整）。"""
        w = CYCLE_WEIGHTS["需求爆发期"]
        self.assertEqual(w["a"], 42)
        self.assertEqual(w["b"], 18)

    def test_tech_jump_pairs(self):
        """技术跃迁期：景气 28 / 研发 32（配对调整）。"""
        w = CYCLE_WEIGHTS["技术跃迁期"]
        self.assertEqual(w["a"], 28)
        self.assertEqual(w["b"], 32)


class TestGeoMatrix(unittest.TestCase):
    """Test 地缘二维修正矩阵系数."""

    def test_high_high_premium(self):
        """国产化率高 × 海外对冲高 → 1.10 韧性溢价."""
        self.assertEqual(GEO_FACTOR["高"]["高"], 1.10)

    def test_high_mid(self):
        """高 × 中 → 1.00."""
        self.assertEqual(GEO_FACTOR["高"]["中"], 1.00)

    def test_mid_low(self):
        """中 × 低 → 0.65."""
        self.assertEqual(GEO_FACTOR["中"]["低"], 0.65)

    def test_low_low(self):
        """低 × 低 → 0.40 禁用级."""
        self.assertEqual(GEO_FACTOR["低"]["低"], 0.40)


class TestTechCheck(unittest.TestCase):
    """Test 技术面止损校验（独立否决，最高优先级）。"""

    def test_red_when_below_ma200(self):
        """破 200 日均线 → 红牌."""
        self.assertEqual(tech_check(_mk_tech(above200=False)), "red")

    def test_warning_when_below_ma50_with_volume(self):
        """破 50 日均线且放量 → 预警."""
        self.assertEqual(tech_check(_mk_tech(above50=False, volume=True)), "warning")

    def test_pass_when_below_ma50_no_volume(self):
        """破 50 日均线但未放量 → 通过（仅探测，不触发）. """
        self.assertEqual(tech_check(_mk_tech(above50=False, volume=False)), "pass")

    def test_pass_when_healthy(self):
        """均线之上 → 通过."""
        self.assertEqual(tech_check(_mk_tech()), "pass")


class TestScoreSkillExamples(unittest.TestCase):
    """Test 技能文件 A/B/C 示例精确复现（阶段一验收标准）。"""

    def test_company_a(self):
        """A 公司：101 × 1.10 = 111 分 S 级."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(), "需求爆发期")
        self.assertAlmostEqual(r.base_total, 101.0, places=1)
        self.assertAlmostEqual(r.final_score, 111.0, places=0)
        self.assertEqual(r.rating, "S")

    def test_company_b(self):
        """B 公司：82 × 1.00 = 82 分 S 级."""
        r = score_company("B", {"a": 25, "b": 33, "c": 10, "d": 6, "e": 8},
                          _mk_geo("高", "中"), _mk_tech(), "需求爆发期")
        self.assertAlmostEqual(r.base_total, 82.0, places=1)
        self.assertAlmostEqual(r.final_score, 82.0, places=1)
        self.assertEqual(r.rating, "S")

    def test_company_c(self):
        """C 公司：40 × 0.65 = 26 分 C 级."""
        r = score_company("C", {"a": 15, "b": 10, "c": 6, "d": 5, "e": 4},
                          _mk_geo("中", "低"), _mk_tech(), "需求爆发期")
        self.assertAlmostEqual(r.base_total, 40.0, places=1)
        self.assertAlmostEqual(r.final_score, 26.0, places=1)
        self.assertEqual(r.rating, "C")


class TestTechVeto(unittest.TestCase):
    """Test 技术面否决：红牌/预警对 S/A 级强制降级."""

    def test_red_card_downgrade_s_to_c(self):
        """S 级破 200 日线 → 强制降 C."""
        r = score_company("B", {"a": 25, "b": 33, "c": 10, "d": 6, "e": 8},
                          _mk_geo("高", "中"), _mk_tech(above200=False), "需求爆发期")
        self.assertEqual(r.tech_verdict, "red")
        self.assertEqual(r.rating, "C")

    def test_warning_downgrade_s_to_b(self):
        """S 级破 50 日线且放量 → 降 B."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(above50=False, volume=True),
                          "需求爆发期")
        self.assertEqual(r.tech_verdict, "warning")
        self.assertEqual(r.rating, "B")

    def test_pass_keeps_rating(self):
        """技术面通过 → 评级不变 (S)."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(), "需求爆发期")
        self.assertEqual(r.tech_verdict, "pass")
        self.assertEqual(r.rating, "S")

    def test_c_level_not_subject_to_tech(self):
        """C 级不执行技术面否决（tech_verdict 保持 pass）."""
        r = score_company("C", {"a": 15, "b": 10, "c": 6, "d": 5, "e": 4},
                          _mk_geo("中", "低"), _mk_tech(above200=False), "需求爆发期")
        self.assertEqual(r.tech_verdict, "pass")
        self.assertEqual(r.rating, "C")


class TestRatingBoundaries(unittest.TestCase):
    """Test 评级映射边界阈值（用高×中系数 1.00，排除地缘影响）。"""

    def test_rating_boundaries(self):
        """80/65/50/49 分别对应 S/A/B/C。"""
        base = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0}
        geo = _mk_geo("高", "中")  # 系数 1.00
        self.assertEqual(score_company("x1", {**base, "a": 80}, geo, None).rating, "S")
        self.assertEqual(score_company("x2", {**base, "a": 65}, geo, None).rating, "A")
        self.assertEqual(score_company("x3", {**base, "a": 50}, geo, None).rating, "B")
        self.assertEqual(score_company("x4", {**base, "a": 49}, geo, None).rating, "C")


class TestMissingDim(unittest.TestCase):
    """Test 缺失科目不阻断打分."""

    def test_missing_dim_note(self):
        """缺失维度按 0 分并记录 note."""
        r = score_company("x", {"a": 10}, _mk_geo("高", "高"), None)
        self.assertEqual(r.dims["b"], 0.0)
        self.assertTrue(any("数据缺失" in n for n in r.notes))


class TestInvalidCycle(unittest.TestCase):
    """Test 非法周期抛 ValueError."""

    def test_unknown_cycle(self):
        """非法周期应抛 ValueError."""
        with self.assertRaises(ValueError):
            score_company("x", {"a": 1}, _mk_geo("高", "高"), None, "不存在的周期")


class TestBatchScore(unittest.TestCase):
    """Test 批量两轮打分（行业景气一致性 ±2）. """

    def _items(self):
        """构造两行业批次：光模块 100% 通过、AI算力 <30% 通过."""
        return [
            # 光模块：2 家均高分 S → 通过率 100% → +2
            {"name": "D1", "industry": "光模块", "dims": {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
             "geo": {"x": "高", "y": "高"},
             "tech": {"close_above_ma200": True, "close_above_ma50": True, "volume_above_1_5x": False}},
            {"name": "D2", "industry": "光模块", "dims": {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
             "geo": {"x": "高", "y": "高"},
             "tech": {"close_above_ma200": True, "close_above_ma50": True, "volume_above_1_5x": False}},
            # AI算力：3 家全 C 级 → 通过率 0% → -2
            {"name": "X1", "industry": "AI算力", "dims": {"a": 15, "b": 10, "c": 6, "d": 5, "e": 4},
             "geo": {"x": "中", "y": "低"},
             "tech": {"close_above_ma200": True, "close_above_ma50": True, "volume_above_1_5x": False}},
            {"name": "X2", "industry": "AI算力", "dims": {"a": 15, "b": 10, "c": 6, "d": 5, "e": 4},
             "geo": {"x": "中", "y": "低"},
             "tech": {"close_above_ma200": True, "close_above_ma50": True, "volume_above_1_5x": False}},
            {"name": "X3", "industry": "AI算力", "dims": {"a": 15, "b": 10, "c": 6, "d": 5, "e": 4},
             "geo": {"x": "中", "y": "低"},
             "tech": {"close_above_ma200": True, "close_above_ma50": True, "volume_above_1_5x": False}},
        ]

    def test_sector_pass_rate_plus2(self):
        """光模块通过率 100% → 集体 +2（base 101 → 103，final 113.3 S）。"""
        out = batch_score(self._items())
        d1 = next(r for r in out["results"] if r["name"] == "D1")
        self.assertAlmostEqual(d1["base_total"], 103.0, places=1)
        self.assertTrue(any("行业景气一致性" in n and "+2" in n for n in d1["notes"]))

    def test_sector_fail_rate_minus2(self):
        """AI算力通过率 <30% → 集体 -2（base 40 → 38，final 24.7 C）。"""
        out = batch_score(self._items())
        x1 = next(r for r in out["results"] if r["name"] == "X1")
        self.assertAlmostEqual(x1["base_total"], 38.0, places=1)
        self.assertTrue(any("行业景气一致性" in n and "-2" in n for n in x1["notes"]))

    def test_industry_pass_rates_reported(self):
        """返回的行业通过率正确."""
        out = batch_score(self._items())
        rates = out["industry_pass_rates"]
        self.assertEqual(rates["光模块"], 100.0)
        self.assertEqual(rates["AI算力"], 0.0)


class TestR8(unittest.TestCase):
    """Test R8 在研项目商业化潜力评分卡.

    规则：总分>=8→+5 奖励；6<=总分<8→+3 奖励；总分<0→评级下调一级。
    """

    def test_r8_max_components(self):
        """R8 满分 10 分，且含 5 个子项."""
        self.assertEqual(R8_MAX_SCORE, 10.0)
        self.assertEqual(len(R8_COMPONENTS), 5)

    def test_parse_r8_defaults_missing(self):
        """缺失子项按 0 分处理."""
        comps = parse_r8({"商业化确定性": 4})
        self.assertEqual(comps["商业化确定性"], 4.0)
        self.assertEqual(comps["市场空间"], 0.0)
        self.assertEqual(comps["专利验证"], 0.0)

    def test_parse_r8_none_empty(self):
        """None 传入 → 空 dict."""
        self.assertEqual(parse_r8(None), {})

    def test_r8_eval_high_boundary(self):
        """总分>=8 → +5 奖励."""
        info = r8_eval(_mk_r8(comm=4, space=2, endorse=2, patent=1, mgmt=1))
        self.assertEqual(info["score"], 10.0)
        self.assertEqual(info["bonus"], 5.0)
        self.assertEqual(info["verdict"], "high")
        self.assertFalse(info["risk"])

    def test_r8_eval_mid_boundary(self):
        """总分 6-8 → +3 奖励."""
        info = r8_eval(_mk_r8(comm=2, space=2, endorse=2))
        self.assertEqual(info["score"], 6.0)
        self.assertEqual(info["bonus"], 3.0)
        self.assertEqual(info["verdict"], "mid")

    def test_r8_eval_none_no_bonus(self):
        """总分<6 → 无奖励."""
        info = r8_eval(_mk_r8(comm=2))
        self.assertEqual(info["bonus"], 0.0)
        self.assertEqual(info["verdict"], "none")

    def test_r8_eval_risk(self):
        """总分<0 → 触发风险警告."""
        info = r8_eval(_mk_r8(comm=-3, space=-2, mgmt=-2))
        self.assertTrue(info["risk"])
        self.assertEqual(info["bonus"], 0.0)

    def test_r8_high_adds_bonus_to_final(self):
        """R8>=8：最终得分 = (101 + 5) × 1.10 = 116.6."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(), "需求爆发期",
                          _mk_r8(comm=4, space=2, endorse=2, patent=1, mgmt=1))
        self.assertEqual(r.r8_bonus, 5.0)
        self.assertAlmostEqual(r.final_score, 116.6, places=1)
        self.assertAlmostEqual(r.base_total, 101.0, places=1)

    def test_r8_mid_adds_bonus(self):
        """R8 6-8 分：最终得分 = (101 + 3) × 1.10 = 114.4."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(), "需求爆发期",
                          _mk_r8(comm=2, space=2, endorse=2))
        self.assertEqual(r.r8_bonus, 3.0)
        self.assertAlmostEqual(r.final_score, 114.4, places=1)

    def test_r8_risk_downgrades_rating(self):
        """R8<0：S 级降为 A 级."""
        r = score_company("B", {"a": 25, "b": 33, "c": 10, "d": 6, "e": 8},
                          _mk_geo("高", "中"), _mk_tech(), "需求爆发期",
                          _mk_r8(comm=-3, space=-2, mgmt=-2))
        self.assertTrue(r.r8_risk)
        self.assertEqual(r.rating, "A")  # 82 分 S → 沿途下调一级 → A
        self.assertTrue(any("在研项目风险警告" in n for n in r.notes))

    def test_r8_none_unchanged(self):
        """未传 R8 → 不影响原始五维打分（回归保护）."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(), "需求爆发期")
        self.assertEqual(r.r8_bonus, 0.0)
        self.assertAlmostEqual(r.final_score, 111.0, places=0)

    def test_r8_batch_risk_downgrade(self):
        """批量第二轮：R8<0 仍触发评级下调一级."""
        items = [{
            "name": "R1", "industry": "光模块",
            "dims": {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
            "geo": {"x": "高", "y": "高"},
            "tech": {"close_above_ma200": True, "close_above_ma50": True, "volume_above_1_5x": False},
            "r8": _mk_r8(comm=-3, space=-2, mgmt=-2),
        }]
        out = batch_score(items)
        r1 = out["results"][0]
        self.assertTrue(r1["r8_risk"])
        self.assertIn(r1["rating"], ("A",))  # 111 分 S → 降一级 → A

    def test_r8_eval_exact_8_boundary(self):
        """精确 8 整分：归入 high 档 → +5 奖励."""
        info = r8_eval(_mk_r8(comm=4, space=2, endorse=2))
        self.assertEqual(info["score"], 8.0)
        self.assertEqual(info["bonus"], 5.0)
        self.assertEqual(info["verdict"], "high")
        self.assertFalse(info["risk"])

    def test_r8_eval_just_below_8(self):
        """7.99 分（紧邻 8 整下沿）：归入 mid 档 → +3 奖励."""
        info = r8_eval(_mk_r8(comm=4, space=2, endorse=1.99))
        self.assertEqual(info["bonus"], 3.0)
        self.assertEqual(info["verdict"], "mid")
        self.assertTrue(info["score"] < 8.0)

    def test_r8_eval_exact_6_boundary(self):
        """精确 6 整分：归入 mid 档（>=6 而非 >=8）→ +3 奖励."""
        info = r8_eval(_mk_r8(comm=2, space=2, endorse=2, patent=0, mgmt=0))
        self.assertEqual(info["score"], 6.0)
        self.assertEqual(info["bonus"], 3.0)
        self.assertEqual(info["verdict"], "mid")

    def test_r8_eval_just_below_6(self):
        """5.99 分（紧邻 6 整下沿）：无奖励且不触发风险."""
        info = r8_eval(_mk_r8(comm=4, space=1.99))
        self.assertEqual(info["bonus"], 0.0)
        self.assertEqual(info["verdict"], "none")
        self.assertFalse(info["risk"])

    def test_r8_eval_exact_0_boundary(self):
        """精确 0 整分：无奖励、无风险（risk 仅为 score<0）."""
        info = r8_eval(_mk_r8())
        self.assertEqual(info["score"], 0.0)
        self.assertEqual(info["bonus"], 0.0)
        self.assertFalse(info["risk"])

    def test_r8_eval_just_below_0(self):
        """-0.01 分（紧邻 0 整下沿）：触发风险警告."""
        info = r8_eval(_mk_r8(comm=-0.01))
        self.assertTrue(info["risk"])
        self.assertIn("在研项目风险警告", info["note"])

    def test_downgrade_rating(self):
        """评级下调一级边界：S→A, A→B, B→C, C→C."""
        self.assertEqual(downgrade_rating("S"), "A")
        self.assertEqual(downgrade_rating("A"), "B")
        self.assertEqual(downgrade_rating("B"), "C")
        self.assertEqual(downgrade_rating("C"), "C")

    def test_markdown_contains_r8_section(self):
        """报告包含 R8 评分卡栏目."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(), "需求爆发期",
                          _mk_r8(comm=4, space=2, endorse=2, patent=1, mgmt=1))
        md = build_markdown(r, "2026-08-25")
        self.assertIn("在研项目评分卡（R8）", md)
        self.assertIn("商业化确定性", md)
        self.assertIn("+5 分奖励", md)


class TestBuildMarkdown(unittest.TestCase):
    """Test Markdown 报告生成."""

    def test_markdown_contains_key_fields(self):
        """报告包含公司名、评级、反证清单."""
        r = score_company("A", {"a": 40, "b": 27, "c": 13, "d": 17, "e": 4},
                          _mk_geo("高", "高"), _mk_tech(), "需求爆发期")
        md = build_markdown(r, "2026-08-25")
        self.assertIn("公司：A", md)
        self.assertIn("S 级", md)
        self.assertIn("反证清单", md)
        self.assertIn("季度订单增速", md)


def run_tests():
    """运行全部测试."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for tc in (TestCycleWeights, TestGeoMatrix, TestTechCheck, TestScoreSkillExamples,
               TestTechVeto, TestRatingBoundaries, TestMissingDim, TestInvalidCycle,
               TestBatchScore, TestR8, TestBuildMarkdown):
        suite.addTests(loader.loadTestsFromTestCase(tc))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("测试摘要 (Test Summary)")
    print("=" * 70)
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n[OK] All tests passed!")
    else:
        print("\n[FAILED] Some tests failed, please check the errors above")

    return result.wasSuccessful()


if __name__ == "__main__":
    import os
    os.chdir(_PROJECT_ROOT)
    success = run_tests()
    sys.exit(0 if success else 1)