#!/usr/bin/env python3
"""Unit tests for governance_data.py 管理层 20 分制评分工具。

覆盖 P3-4 管理层 20 分制契约（§6 验收标准）：
1. 诚信否决任一击中即放弃（总分无效，score_breakdown 为空）
2. 20 分满分与三档边界（15/14/10/9/20）
3. 子项权重逐项可复现（数值阈值 + 定性档位 + 布尔扣分）
4. 输入越界/非法档位 fail-fast 拒绝
5. 输出 JSON 可解析、字段齐备
6. CLI 子命令 management 输出 JSON、非法输入退出码 1、纯否决路径可用
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

#: 项目根目录（本文件位于 tests/specialized/，向上三级回到工作区根目录）。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.specialized.governance_data import (  # noqa: E402
    CAPITALIZATION_THRESHOLD,
    DISCOUNT_FLOOR,
    DISCOUNT_RANGE_NOTE,
    DISCOUNT_RATE_ADJ_BPS,
    DISCOUNT_RATE_ADJ_RANGE_BPS,
    DISCOUNT_TABLE,
    DIVIDEND_HIGH_THRESHOLD,
    DIVIDEND_MID_THRESHOLD,
    ENV_RISK_VALUES,
    ESG_NOTE,
    ESG_SOURCE,
    ESG_TIME_SENSITIVITY_NOTE,
    ITEM_LABELS,
    NEW_PRODUCT_HIGH_THRESHOLD,
    NEW_PRODUCT_MID_THRESHOLD,
    NOTE,
    PLEDGE_WARNING_THRESHOLD,
    POSITION_CAP_BASE_DEFAULT,
    POSITION_CAP_DOWNGRADE_PCT,
    QUALITY_VALUES,
    RD_INTENSITY_THRESHOLD,
    RD_PERSONNEL_HIGH_THRESHOLD,
    RD_PERSONNEL_MID_THRESHOLD,
    RESEARCH_DIMENSIONS,
    RESEARCH_ITEM_LABELS,
    RESEARCH_NOTE,
    RESEARCH_SOURCE,
    RESEARCH_SUBITEM_MAX,
    RESEARCH_TIME_SENSITIVITY_NOTE,
    SOURCE,
    STRANDED_EXTRA_DISCOUNT,
    TRANSITION_VALUES,
    TURNOVER_MID_THRESHOLD,
    TURNOVER_HIGH_THRESHOLD,
    VETO_FLAGS,
    build_esg_result,
    build_governance_result,
    build_research_result,
)

#: 满分输入基准（三维全满 = 20 分）。
FULL_INPUT = {
    "fulfillment_rate": 80.0,
    "dividend_payout_ratio": 35.0,
    "financing": "优",
    "buyback": "优",
    "pledge_ratio": 20.0,
    "core_focus": "优",
    "strategy_exec": "优",
    "industry_cog": "优",
    "turnover_rate": 5.0,
    "equity_incentive": "优",
    "insider_abnormal": False,
}


def _score(**overrides):
    """以满分输入为基准，合并覆盖项后执行评分，返回结果字典。"""
    payload = dict(FULL_INPUT)
    payload.update(overrides)
    return build_governance_result(**payload)


#: 科研转化满分输入基准（8+8+4 = 20 分）。
RESEARCH_FULL_INPUT = {
    "rd_intensity": 18.0,
    "rd_intensity_rising": True,
    "capitalization_rate": 12.0,
    "rd_personnel_ratio": 32.0,
    "patent_quality": "优",
    "new_product_revenue_ratio": 25.0,
    "commercialization_cycle": "优",
    "project_milestone": "优",
    "roic": 16.0,
    "wacc": 8.0,
    "incremental_roic": 19.0,
}


def _rscore(**overrides):
    """以科研转化满分输入为基准，合并覆盖项后执行评分，返回结果字典。"""
    payload = dict(RESEARCH_FULL_INPUT)
    payload.update(overrides)
    return build_research_result(**payload)


def _escore(**overrides):
    """以高环境风险输入为基准，合并覆盖项后执行 ESG 折价，返回结果字典。"""
    payload = {"env_risk_level": "高"}
    payload.update(overrides)
    return build_esg_result(**payload)


class TestConstants(unittest.TestCase):
    """常量表自洽：档位词表、否决键、三维满分、口径来源。"""

    def test_quality_values(self):
        self.assertEqual(QUALITY_VALUES, ("优", "中", "差"))

    def test_veto_flags_keys(self):
        self.assertEqual(
            set(VETO_FLAGS),
            {"fulfillment_rate", "guidance_misstatement", "attribution_habit",
             "regulatory_filing", "financial_fraud"},
        )

    def test_source(self):
        self.assertEqual(SOURCE, "框架第3步·支柱三")

    def test_dimension_max_total_20(self):
        r = _score()
        dims = r["score_breakdown"]
        self.assertEqual(dims["shareholder_treatment"]["max"], 7)
        self.assertEqual(dims["strategy_execution"]["max"], 7)
        self.assertEqual(dims["stability_incentive"]["max"], 6)
        self.assertEqual(
            dims["shareholder_treatment"]["max"]
            + dims["strategy_execution"]["max"]
            + dims["stability_incentive"]["max"],
            20,
        )


class TestIntegrityVeto(unittest.TestCase):
    """诚信否决任一击中即放弃，total 无效、score_breakdown 为空。"""

    def test_fulfillment_rate_below_50_veto(self):
        r = _score(fulfillment_rate=49.9)
        self.assertTrue(r["integrity_veto"])
        self.assertEqual(r["integrity_veto_reasons"], ["fulfillment_rate"])
        self.assertIsNone(r["total"])
        self.assertEqual(r["verdict"], "放弃")
        self.assertEqual(r["score_breakdown"], {})

    def test_fulfillment_rate_equal_50_not_veto(self):
        r = _score(fulfillment_rate=50.0)
        self.assertFalse(r["integrity_veto"])
        self.assertEqual(r["integrity_veto_reasons"], [])
        self.assertIsNotNone(r["total"])

    def test_guidance_misstatement_veto(self):
        r = _score(guidance_misstatement=True)
        self.assertTrue(r["integrity_veto"])
        self.assertEqual(r["integrity_veto_reasons"], ["guidance_misstatement"])
        self.assertIsNone(r["total"])

    def test_attribution_habit_veto(self):
        r = _score(attribution_habit=True)
        self.assertEqual(r["integrity_veto_reasons"], ["attribution_habit"])
        self.assertIsNone(r["total"])

    def test_regulatory_filing_veto(self):
        r = _score(regulatory_filing=True)
        self.assertEqual(r["integrity_veto_reasons"], ["regulatory_filing"])
        self.assertIsNone(r["total"])

    def test_financial_fraud_veto(self):
        r = _score(financial_fraud=True)
        self.assertEqual(r["integrity_veto_reasons"], ["financial_fraud"])
        self.assertIsNone(r["total"])
        self.assertEqual(r["verdict"], "放弃")

    def test_multiple_veto_reasons(self):
        r = _score(guidance_misstatement=True, financial_fraud=True,
                   regulatory_filing=True)
        self.assertTrue(r["integrity_veto"])
        self.assertEqual(
            r["integrity_veto_reasons"],
            ["guidance_misstatement", "regulatory_filing", "financial_fraud"],
        )
        self.assertIsNone(r["total"])
        self.assertEqual(r["score_breakdown"], {})


class TestFullAndVerdictBoundaries(unittest.TestCase):
    """20 分满分与三档边界（>=15 重仓 / 10~14 观察 / <10 放弃）。"""

    def test_full_score_20_heavy_position(self):
        r = _score()
        self.assertFalse(r["integrity_veto"])
        self.assertEqual(r["total"], 20)
        self.assertEqual(r["verdict"], "重仓")
        self.assertEqual(r["position_note"], "管理层评分≥15，可重仓")

    def test_total_15_heavy_position(self):
        r = _score(core_focus="中", strategy_exec="中", industry_cog="中",
                   financing="中")
        self.assertEqual(r["total"], 15)
        self.assertEqual(r["verdict"], "重仓")

    def test_total_14_watch(self):
        r = _score(core_focus="中", strategy_exec="中", industry_cog="中",
                   financing="中", buyback="中")
        self.assertEqual(r["total"], 14)
        self.assertEqual(r["verdict"], "观察")
        self.assertIn("≤5%", r["position_note"])

    def test_total_10_watch(self):
        r = _score(core_focus="差", strategy_exec="差", industry_cog="差",
                   financing="差", pledge_ratio=60.0)
        self.assertEqual(r["total"], 10)
        self.assertEqual(r["verdict"], "观察")

    def test_total_9_give_up(self):
        r = _score(core_focus="差", strategy_exec="差", industry_cog="差",
                   financing="差", buyback="差")
        self.assertEqual(r["total"], 9)
        self.assertEqual(r["verdict"], "放弃")
        self.assertEqual(r["position_note"], "管理层评分<10，放弃")


class TestSubItemScoring(unittest.TestCase):
    """子项权重逐项可复现（数值阈值 + 定性档位 + 布尔扣分）。"""

    def _item_score(self, dimension, key, **overrides):
        r = _score(**overrides)
        return r["score_breakdown"][dimension]["items"][key]["score"]

    def test_dividend_thresholds(self):
        cases = {30.0: 2, 29.9: 1, 15.0: 1, 14.9: 0, 0.0: 0, 100.0: 2}
        for rate, expected in cases.items():
            self.assertEqual(
                self._item_score("shareholder_treatment",
                                 "dividend_payout_ratio",
                                 dividend_payout_ratio=rate),
                expected,
                rate,
            )

    def test_financing_quality(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("shareholder_treatment", "financing",
                                 financing=value),
                expected,
                value,
            )

    def test_buyback_quality(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("shareholder_treatment", "buyback",
                                 buyback=value),
                expected,
                value,
            )

    def test_pledge_thresholds(self):
        cases = {0.0: 1, 50.0: 1, 50.1: 0, 100.0: 0}
        for rate, expected in cases.items():
            self.assertEqual(
                self._item_score("shareholder_treatment", "pledge_ratio",
                                 pledge_ratio=rate),
                expected,
                rate,
            )

    def test_core_focus_quality(self):
        for value, expected in (("优", 3), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("strategy_execution", "core_focus",
                                 core_focus=value),
                expected,
                value,
            )

    def test_strategy_exec_quality(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("strategy_execution", "strategy_exec",
                                 strategy_exec=value),
                expected,
                value,
            )

    def test_industry_cog_quality(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("strategy_execution", "industry_cog",
                                 industry_cog=value),
                expected,
                value,
            )

    def test_turnover_thresholds(self):
        cases = {0.0: 2, 9.9: 2, 10.0: 1, 19.9: 1, 20.0: 0, 100.0: 0}
        for rate, expected in cases.items():
            self.assertEqual(
                self._item_score("stability_incentive", "turnover_rate",
                                 turnover_rate=rate),
                expected,
                rate,
            )

    def test_equity_incentive_quality(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("stability_incentive", "equity_incentive",
                                 equity_incentive=value),
                expected,
                value,
            )

    def test_insider_abnormal_bool(self):
        self.assertEqual(
            self._item_score("stability_incentive", "insider_abnormal",
                             insider_abnormal=False),
            2,
        )
        self.assertEqual(
            self._item_score("stability_incentive", "insider_abnormal",
                             insider_abnormal=True),
            0,
        )


class TestInputValidation(unittest.TestCase):
    """非法输入 fail-fast 拒绝（数值越界/非数值/非法档位/布尔误用）。"""

    def test_fulfillment_rate_out_of_range(self):
        for bad in (-1.0, 100.1):
            with self.assertRaises(ValueError):
                _score(fulfillment_rate=bad)

    def test_fulfillment_rate_non_numeric(self):
        with self.assertRaises(ValueError):
            _score(fulfillment_rate="abc")

    def test_dividend_rate_out_of_range(self):
        for bad in (-0.1, 100.1, True):
            with self.assertRaises(ValueError):
                _score(dividend_payout_ratio=bad)

    def test_pledge_rate_out_of_range(self):
        for bad in (-1.0, 101.0):
            with self.assertRaises(ValueError):
                _score(pledge_ratio=bad)

    def test_turnover_rate_out_of_range(self):
        for bad in (-1.0, 100.1):
            with self.assertRaises(ValueError):
                _score(turnover_rate=bad)

    def test_invalid_quality_rejected(self):
        for bad in ("良好", "一般", "", None):
            with self.assertRaises(ValueError):
                _score(core_focus=bad)

    def test_missing_scoring_input_rejected(self):
        with self.assertRaises(ValueError):
            build_governance_result(fulfillment_rate=80.0)

    def test_insider_abnormal_requires_bool(self):
        with self.assertRaises(ValueError):
            _score(insider_abnormal=None)
        with self.assertRaises(ValueError):
            _score(insider_abnormal="否")


class TestJSONOutput(unittest.TestCase):
    """输出 JSON 可解析，字段齐全、类型正确。"""

    def test_normal_json_fields(self):
        r = _score(as_of="2026-09-15")
        payload = json.loads(json.dumps(r, ensure_ascii=False))
        self.assertEqual(payload["task"], "management")
        self.assertFalse(payload["integrity_veto"])
        self.assertEqual(payload["integrity_veto_reasons"], [])
        self.assertIsInstance(payload["total"], int)
        self.assertEqual(payload["verdict"], "重仓")
        self.assertEqual(payload["data_as_of"], "2026-09-15")
        self.assertEqual(payload["source"], SOURCE)
        self.assertEqual(payload["time_sensitivity_note"],
                         r["time_sensitivity_note"])
        self.assertEqual(payload["note"], NOTE)
        self.assertIn("input", payload)
        self.assertEqual(payload["input"]["as_of"], "2026-09-15")
        self.assertEqual(
            set(payload["score_breakdown"]),
            {"shareholder_treatment", "strategy_execution", "stability_incentive"},
        )

    def test_veto_json_fields(self):
        r = _score(financial_fraud=True, as_of="2026-09-15")
        payload = json.loads(json.dumps(r, ensure_ascii=False))
        self.assertTrue(payload["integrity_veto"])
        self.assertIsNone(payload["total"])
        self.assertEqual(payload["verdict"], "放弃")
        self.assertEqual(payload["score_breakdown"], {})

    def test_data_as_of_null_when_absent(self):
        r = _score()
        self.assertIsNone(r["data_as_of"])

    def test_item_labels_present(self):
        r = _score()
        items = r["score_breakdown"]["shareholder_treatment"]["items"]
        self.assertEqual(items["dividend_payout_ratio"]["label"], "分红历史")
        self.assertEqual(items["pledge_ratio"]["label"], "大股东质押率")
        self.assertEqual(items["pledge_ratio"]["max"], 1)


class TestCLI(unittest.TestCase):
    """CLI 入口：management 子命令输出 JSON、非法输入退出码 1、纯否决可用。"""

    _TOOL = str(_PROJECT_ROOT / "tools" / "specialized" /
                "governance_data.py")

    def test_cli_valid_json(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "management",
             "--fulfillment-rate", "80",
             "--dividend-payout-ratio", "35",
             "--financing", "优", "--buyback", "优", "--pledge-ratio", "20",
             "--core-focus", "优", "--strategy-exec", "优", "--industry-cog", "优",
             "--turnover-rate", "5", "--equity-incentive", "优",
             "--as-of", "2026-09-15"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["total"], 20)
        self.assertEqual(payload["verdict"], "重仓")

    def test_cli_veto_only_path(self):
        # 仅命中否决项即可放弃，无需提供评分项（评分项 argparse 均非必填）。
        out = subprocess.run(
            [sys.executable, self._TOOL, "management", "--financial-fraud"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertTrue(payload["integrity_veto"])
        self.assertIsNone(payload["total"])
        self.assertEqual(payload["verdict"], "放弃")

    def test_cli_invalid_quality_exit_code(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "management",
             "--fulfillment-rate", "80",
             "--dividend-payout-ratio", "35",
             "--financing", "优", "--buyback", "优", "--pledge-ratio", "20",
             "--core-focus", "良好",
             "--strategy-exec", "优", "--industry-cog", "优",
             "--turnover-rate", "5", "--equity-incentive", "优"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn("非法", out.stdout)

    def test_cli_invalid_rate_exit_code(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "management",
             "--fulfillment-rate", "80",
             "--dividend-payout-ratio", "101",
             "--financing", "优", "--buyback", "优", "--pledge-ratio", "20",
             "--core-focus", "优", "--strategy-exec", "优", "--industry-cog", "优",
             "--turnover-rate", "5", "--equity-incentive", "优"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn("错误", out.stdout)


class TestResearchConstants(unittest.TestCase):
    """科研转化常量表自洽：三维满分合计 20、口径来源、子项权重键一致。"""

    def test_dimension_max_total_20(self):
        self.assertEqual(RESEARCH_DIMENSIONS["rd_input"]["max"], 8)
        self.assertEqual(RESEARCH_DIMENSIONS["rd_output"]["max"], 8)
        self.assertEqual(RESEARCH_DIMENSIONS["capital_return"]["max"], 4)
        self.assertEqual(
            RESEARCH_DIMENSIONS["rd_input"]["max"]
            + RESEARCH_DIMENSIONS["rd_output"]["max"]
            + RESEARCH_DIMENSIONS["capital_return"]["max"],
            20,
        )

    def test_source(self):
        self.assertEqual(RESEARCH_SOURCE, "框架第3步·支柱三（科研转化评估清单）")

    def test_subitem_max_keys_match_dimensions(self):
        all_keys = set()
        for meta in RESEARCH_DIMENSIONS.values():
            all_keys.update(meta["items"])
        self.assertEqual(set(RESEARCH_SUBITEM_MAX), all_keys)

    def test_item_labels_keys_match_dimensions(self):
        all_keys = set()
        for meta in RESEARCH_DIMENSIONS.values():
            all_keys.update(meta["items"])
        self.assertEqual(set(RESEARCH_ITEM_LABELS), all_keys)


class TestResearchFullAndVerdictBoundaries(unittest.TestCase):
    """科研转化满分与三档边界（>=15 重仓 / 10~14 观察 / <10 放弃）。"""

    def test_full_score_20_heavy_position(self):
        r = _rscore()
        self.assertEqual(r["total"], 20)
        self.assertEqual(r["verdict"], "重仓")
        self.assertEqual(r["position_note"], "科研转化评分≥15，可重仓")

    def test_total_15_heavy_position(self):
        r = _rscore(rd_intensity_rising=False, patent_quality="中",
                    new_product_revenue_ratio=15.0,
                    commercialization_cycle="中", project_milestone="中")
        self.assertEqual(r["total"], 15)
        self.assertEqual(r["verdict"], "重仓")

    def test_total_14_watch(self):
        r = _rscore(rd_intensity_rising=False, patent_quality="差",
                    new_product_revenue_ratio=15.0,
                    commercialization_cycle="中", project_milestone="中")
        self.assertEqual(r["total"], 14)
        self.assertEqual(r["verdict"], "观察")
        self.assertIn("≤5%", r["position_note"])

    def test_total_10_watch(self):
        r = _rscore(rd_intensity=14.0, rd_personnel_ratio=15.0,
                    patent_quality="差", new_product_revenue_ratio=5.0,
                    commercialization_cycle="中")
        self.assertEqual(r["total"], 10)
        self.assertEqual(r["verdict"], "观察")

    def test_total_9_give_up(self):
        r = _rscore(rd_intensity=14.0, rd_personnel_ratio=15.0,
                    patent_quality="差", new_product_revenue_ratio=5.0,
                    commercialization_cycle="差")
        self.assertEqual(r["total"], 9)
        self.assertEqual(r["verdict"], "放弃")
        self.assertEqual(r["position_note"], "科研转化评分<10，放弃")


class TestResearchSubItemScoring(unittest.TestCase):
    """科研转化子项权重逐项可复现（数值阈值 + 定性档位 + 严格大于）。"""

    def _item_score(self, dimension, key, **overrides):
        r = _rscore(**overrides)
        return r["score_breakdown"][dimension]["items"][key]["score"]

    def test_rd_intensity_thresholds(self):
        self.assertEqual(
            self._item_score("rd_input", "rd_intensity",
                             rd_intensity=14.9, rd_intensity_rising=True),
            0,
        )
        self.assertEqual(
            self._item_score("rd_input", "rd_intensity",
                             rd_intensity=15.0, rd_intensity_rising=False),
            2,
        )
        self.assertEqual(
            self._item_score("rd_input", "rd_intensity",
                             rd_intensity=15.0, rd_intensity_rising=True),
            3,
        )

    def test_capitalization_thresholds(self):
        for rate, expected in ((0.0, 2), (29.9, 2), (30.0, 0), (100.0, 0)):
            self.assertEqual(
                self._item_score("rd_input", "capitalization_rate",
                                 capitalization_rate=rate),
                expected,
                rate,
            )

    def test_rd_personnel_thresholds(self):
        cases = {0.0: 0, 14.9: 0, 15.0: 1, 29.9: 1, 30.0: 3, 100.0: 3}
        for rate, expected in cases.items():
            self.assertEqual(
                self._item_score("rd_input", "rd_personnel_ratio",
                                 rd_personnel_ratio=rate),
                expected,
                rate,
            )

    def test_new_product_thresholds(self):
        cases = {0.0: 0, 9.9: 0, 10.0: 1, 19.9: 1, 20.0: 2, 100.0: 2}
        for rate, expected in cases.items():
            self.assertEqual(
                self._item_score("rd_output", "new_product_revenue_ratio",
                                 new_product_revenue_ratio=rate),
                expected,
                rate,
            )

    def test_patent_quality(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("rd_output", "patent_quality",
                                 patent_quality=value),
                expected,
                value,
            )

    def test_commercialization_cycle(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("rd_output", "commercialization_cycle",
                                 commercialization_cycle=value),
                expected,
                value,
            )

    def test_project_milestone(self):
        for value, expected in (("优", 2), ("中", 1), ("差", 0)):
            self.assertEqual(
                self._item_score("rd_output", "project_milestone",
                                 project_milestone=value),
                expected,
                value,
            )

    def test_roic_vs_wacc_strictly_greater(self):
        self.assertEqual(
            self._item_score("capital_return", "roic_vs_wacc",
                             roic=16.0, wacc=16.0),
            0,
        )
        self.assertEqual(
            self._item_score("capital_return", "roic_vs_wacc",
                             roic=16.0, wacc=15.99),
            2,
        )
        self.assertEqual(
            self._item_score("capital_return", "roic_vs_wacc",
                             roic=-5.0, wacc=-10.0),
            2,
        )

    def test_incremental_vs_roic_strictly_greater(self):
        self.assertEqual(
            self._item_score("capital_return", "incremental_vs_roic",
                             roic=16.0, incremental_roic=16.0),
            0,
        )
        self.assertEqual(
            self._item_score("capital_return", "incremental_vs_roic",
                             roic=16.0, incremental_roic=16.01),
            2,
        )
        self.assertEqual(
            self._item_score("capital_return", "incremental_vs_roic",
                             roic=-5.0, incremental_roic=-3.0),
            2,
        )


class TestResearchCapitalPassthrough(unittest.TestCase):
    """资本回报数值透传降级：缺省 0 分 + warning，允许负值，无诚信否决字段。"""

    def test_missing_roic_warning_and_zero(self):
        r = _rscore(roic=None, wacc=None, incremental_roic=None)
        items = r["score_breakdown"]["capital_return"]["items"]
        self.assertEqual(items["roic_vs_wacc"]["score"], 0)
        self.assertEqual(items["incremental_vs_roic"]["score"], 0)
        self.assertEqual(r["score_breakdown"]["capital_return"]["score"], 0)
        self.assertEqual(r["total"], 16)
        self.assertIn("未提供 ROIC", r["warning"][0])

    def test_missing_wacc_warning(self):
        r = _rscore(wacc=None)
        items = r["score_breakdown"]["capital_return"]["items"]
        self.assertEqual(items["roic_vs_wacc"]["score"], 0)
        self.assertEqual(items["incremental_vs_roic"]["score"], 2)
        self.assertEqual(r["score_breakdown"]["capital_return"]["score"], 2)
        self.assertTrue(any("未提供 WACC" in w for w in r["warning"]))

    def test_missing_incremental_warning(self):
        r = _rscore(incremental_roic=None)
        items = r["score_breakdown"]["capital_return"]["items"]
        self.assertEqual(items["roic_vs_wacc"]["score"], 2)
        self.assertEqual(items["incremental_vs_roic"]["score"], 0)
        self.assertEqual(r["score_breakdown"]["capital_return"]["score"], 2)
        self.assertTrue(any("未提供增量 ROIC" in w for w in r["warning"]))

    def test_negative_values_allowed(self):
        r = _rscore(roic=-5.0, wacc=-10.0, incremental_roic=-3.0)
        self.assertEqual(r["warning"], [])
        self.assertEqual(r["score_breakdown"]["capital_return"]["score"], 4)
        self.assertEqual(r["total"], 20)

    def test_no_integrity_veto_field(self):
        r = _rscore()
        self.assertNotIn("integrity_veto", r)
        self.assertNotIn("integrity_veto_reasons", r)


class TestResearchInputValidation(unittest.TestCase):
    """科研转化非法输入 fail-fast 拒绝（数值越界/非数值/非法档位/缺失）。"""

    def test_rd_intensity_out_of_range(self):
        for bad in (-1.0, 100.1):
            with self.assertRaises(ValueError):
                _rscore(rd_intensity=bad)

    def test_rd_intensity_non_numeric(self):
        with self.assertRaises(ValueError):
            _rscore(rd_intensity="abc")

    def test_capitalization_out_of_range(self):
        for bad in (-0.1, 100.1):
            with self.assertRaises(ValueError):
                _rscore(capitalization_rate=bad)

    def test_rd_personnel_out_of_range(self):
        for bad in (-1.0, 100.1):
            with self.assertRaises(ValueError):
                _rscore(rd_personnel_ratio=bad)

    def test_new_product_out_of_range(self):
        for bad in (-0.1, 100.1):
            with self.assertRaises(ValueError):
                _rscore(new_product_revenue_ratio=bad)

    def test_invalid_quality_rejected(self):
        for bad in ("良好", "一般", "", None):
            with self.assertRaises(ValueError):
                _rscore(patent_quality=bad)

    def test_missing_scoring_input_rejected(self):
        with self.assertRaises(ValueError):
            build_research_result()


class TestResearchJSONOutput(unittest.TestCase):
    """科研转化输出 JSON 可解析、字段齐全、无诚信否决字段。"""

    def test_json_fields(self):
        r = _rscore(as_of="2026-09-16")
        payload = json.loads(json.dumps(r, ensure_ascii=False))
        self.assertEqual(payload["task"], "research")
        self.assertEqual(payload["total"], 20)
        self.assertEqual(payload["verdict"], "重仓")
        self.assertEqual(payload["data_as_of"], "2026-09-16")
        self.assertEqual(payload["source"], RESEARCH_SOURCE)
        self.assertEqual(payload["note"], RESEARCH_NOTE)
        self.assertEqual(payload["time_sensitivity_note"],
                         RESEARCH_TIME_SENSITIVITY_NOTE)
        self.assertIsInstance(payload["warning"], list)
        self.assertNotIn("integrity_veto", payload)
        self.assertNotIn("integrity_veto_reasons", payload)
        self.assertEqual(
            set(payload["score_breakdown"]),
            {"rd_input", "rd_output", "capital_return"},
        )
        self.assertIn("input", payload)
        self.assertEqual(payload["input"]["as_of"], "2026-09-16")

    def test_data_as_of_null_when_absent(self):
        r = _rscore()
        self.assertIsNone(r["data_as_of"])

    def test_item_labels_present(self):
        r = _rscore()
        self.assertEqual(
            r["score_breakdown"]["rd_input"]["items"]["rd_intensity"]["label"],
            "研发强度及逐年提升",
        )
        self.assertEqual(
            r["score_breakdown"]["capital_return"]["items"]["roic_vs_wacc"]["label"],
            "ROIC > WACC",
        )


class TestResearchCLI(unittest.TestCase):
    """CLI 入口：research 子命令输出 JSON、缺省降级 warning、非法输入退出码 1。"""

    _TOOL = str(_PROJECT_ROOT / "tools" / "specialized" /
                "governance_data.py")

    def test_cli_valid_json(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "research",
             "--rd-intensity", "18", "--rd-intensity-rising",
             "--capitalization-rate", "12", "--rd-personnel-ratio", "32",
             "--patent-quality", "优", "--new-product-revenue-ratio", "25",
             "--commercialization-cycle", "优", "--project-milestone", "优",
             "--roic", "16", "--wacc", "8", "--incremental-roic", "19",
             "--as-of", "2026-09-16"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["total"], 20)
        self.assertEqual(payload["verdict"], "重仓")
        self.assertNotIn("integrity_veto", payload)

    def test_cli_missing_capital_return_warning(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "research",
             "--rd-intensity", "18", "--rd-intensity-rising",
             "--capitalization-rate", "12", "--rd-personnel-ratio", "32",
             "--patent-quality", "优", "--new-product-revenue-ratio", "25",
             "--commercialization-cycle", "优", "--project-milestone", "优"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertTrue(payload["warning"])
        self.assertEqual(payload["score_breakdown"]["capital_return"]["score"], 0)
        self.assertEqual(payload["total"], 16)

    def test_cli_invalid_quality_exit_code(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "research",
             "--rd-intensity", "18",
             "--capitalization-rate", "12", "--rd-personnel-ratio", "32",
             "--patent-quality", "良好", "--new-product-revenue-ratio", "25",
             "--commercialization-cycle", "优", "--project-milestone", "优",
             "--roic", "16", "--wacc", "8", "--incremental-roic", "19"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn("非法", out.stdout)

    def test_cli_invalid_rate_exit_code(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "research",
             "--rd-intensity", "101",
             "--capitalization-rate", "12", "--rd-personnel-ratio", "32",
             "--patent-quality", "优", "--new-product-revenue-ratio", "25",
             "--commercialization-cycle", "优", "--project-milestone", "优",
             "--roic", "16", "--wacc", "8", "--incremental-roic", "19"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn("错误", out.stdout)


class TestEsgConstants(unittest.TestCase):
    """ESG 折价常量表自洽（档位词表、确定值、区间、口径来源）。"""

    def test_env_risk_values(self):
        self.assertEqual(ENV_RISK_VALUES, ("高", "低"))

    def test_transition_values(self):
        self.assertEqual(TRANSITION_VALUES, ("明确", "无"))

    def test_discount_table_keys(self):
        self.assertEqual(
            set(DISCOUNT_TABLE),
            {("高", "无"), ("高", "明确"), ("低", "无"), ("低", "明确")},
        )

    def test_discount_table_values(self):
        self.assertEqual(DISCOUNT_TABLE[("高", "无")], 0.85)
        self.assertEqual(DISCOUNT_TABLE[("高", "明确")], 0.95)
        self.assertEqual(DISCOUNT_TABLE[("低", "无")], 1.00)
        self.assertEqual(DISCOUNT_TABLE[("低", "明确")], 1.00)

    def test_discount_coefficients(self):
        self.assertEqual(DISCOUNT_FLOOR, 0.80)
        self.assertEqual(STRANDED_EXTRA_DISCOUNT, 0.05)

    def test_discount_rate_constants(self):
        self.assertEqual(DISCOUNT_RATE_ADJ_BPS, 150)
        self.assertEqual(DISCOUNT_RATE_ADJ_RANGE_BPS, (100, 200))

    def test_position_cap_constants(self):
        self.assertEqual(POSITION_CAP_DOWNGRADE_PCT, 5.0)
        self.assertEqual(POSITION_CAP_BASE_DEFAULT, 20.0)

    def test_source(self):
        self.assertEqual(ESG_SOURCE,
                         "框架第4步·ESG/环境风险的估值折价 + 第3步·支柱三 ESG 补充检查")


class TestEsgDiscount(unittest.TestCase):
    """折价系数三通道——折扣判定表 6 行 + 搁浅下限 0.80。"""

    def test_high_no_pathway_no_stranded(self):
        r = _escore(transition_pathway="无")
        self.assertEqual(r["discount_factor"], 0.85)
        self.assertEqual(r["discount_pct"], 15.0)

    def test_high_with_pathway_no_stranded(self):
        r = _escore(transition_pathway="明确")
        self.assertEqual(r["discount_factor"], 0.95)
        self.assertEqual(r["discount_pct"], 5.0)

    def test_low_no_stranded(self):
        r = _escore(env_risk_level="低")
        self.assertEqual(r["discount_factor"], 1.0)
        self.assertEqual(r["discount_pct"], 0.0)

    def test_high_no_pathway_stranded_floor(self):
        r = _escore(transition_pathway="无", stranded_asset=True)
        self.assertEqual(r["discount_factor"], 0.80)
        self.assertEqual(r["discount_pct"], 20.0)

    def test_high_with_pathway_stranded(self):
        r = _escore(transition_pathway="明确", stranded_asset=True)
        self.assertEqual(r["discount_factor"], 0.90)
        self.assertEqual(r["discount_pct"], 10.0)

    def test_low_stranded(self):
        r = _escore(env_risk_level="低", stranded_asset=True)
        self.assertEqual(r["discount_factor"], 0.95)
        self.assertEqual(r["discount_pct"], 5.0)

    def test_discount_range_note(self):
        self.assertEqual(_escore()["discount_range"], DISCOUNT_RANGE_NOTE)
        self.assertIsNone(_escore(env_risk_level="低")["discount_range"])


class TestEsgDiscountRate(unittest.TestCase):
    """搁浅资产贴现率上调：命中 +150bp 回显区间，未命中 0 与空区间。"""

    def test_stranded_bps(self):
        r = _escore(stranded_asset=True)
        self.assertEqual(r["discount_rate_adj_bps"], 150)
        self.assertEqual(r["discount_rate_adj_range_bps"], [100, 200])

    def test_not_stranded_bps(self):
        r = _escore()
        self.assertEqual(r["discount_rate_adj_bps"], 0)
        self.assertEqual(r["discount_rate_adj_range_bps"], [])


class TestEsgPositionCap(unittest.TestCase):
    """仓位上限下调：高环境风险或评级尾部任一命中 -5pct，不叠加。"""

    def test_high_env_downgrade(self):
        r = _escore()
        self.assertEqual(r["position_cap_downgrade"], 5.0)
        self.assertEqual(r["position_cap_base"], 20.0)
        self.assertEqual(r["position_cap_after"], 15.0)

    def test_esg_tail_alone_downgrade(self):
        r = _escore(env_risk_level="低", esg_tail=True)
        self.assertEqual(r["discount_factor"], 1.0)  # 估值不折价
        self.assertEqual(r["position_cap_downgrade"], 5.0)
        self.assertEqual(r["position_cap_after"], 15.0)

    def test_high_and_tail_not_stacked(self):
        r = _escore(esg_tail=True)
        self.assertEqual(r["position_cap_downgrade"], 5.0)
        self.assertNotEqual(r["position_cap_downgrade"], 10.0)

    def test_low_no_tail_no_downgrade(self):
        r = _escore(env_risk_level="低")
        self.assertEqual(r["position_cap_downgrade"], 0.0)
        self.assertEqual(r["position_cap_after"], 20.0)

    def test_custom_base(self):
        r = _escore(position_cap_base=15.0)
        self.assertEqual(r["position_cap_base"], 15.0)
        self.assertEqual(r["position_cap_after"], 10.0)


class TestEsgInputValidation(unittest.TestCase):
    """ESG 非法输入 fail-fast 拒绝。"""

    def test_env_risk_level_required(self):
        with self.assertRaises(TypeError):
            build_esg_result()

    def test_env_risk_level_invalid(self):
        for bad in ("中", "无", "", None, "high"):
            with self.assertRaises(ValueError):
                _escore(env_risk_level=bad)

    def test_transition_pathway_invalid(self):
        for bad in ("有", "部分", "", None):
            with self.assertRaises(ValueError):
                _escore(transition_pathway=bad)

    def test_position_cap_base_out_of_range(self):
        for bad in (-0.1, 100.1):
            with self.assertRaises(ValueError):
                _escore(position_cap_base=bad)

    def test_position_cap_base_non_numeric(self):
        with self.assertRaises(ValueError):
            _escore(position_cap_base="abc")


class TestEsgJSONOutput(unittest.TestCase):
    """ESG 输出 JSON 可解析、字段齐全，无 verdict/score_breakdown。"""

    def test_json_fields(self):
        r = _escore(transition_pathway="无", stranded_asset=True, esg_tail=True,
                    as_of="2026-09-16")
        payload = json.loads(json.dumps(r, ensure_ascii=False))
        self.assertEqual(payload["task"], "esg")
        self.assertEqual(payload["discount_factor"], 0.8)
        self.assertEqual(payload["discount_rate_adj_bps"], 150)
        self.assertIsInstance(payload["discount_rate_adj_range_bps"], list)
        self.assertEqual(payload["position_cap_downgrade"], 5.0)
        self.assertEqual(payload["data_as_of"], "2026-09-16")
        self.assertEqual(payload["source"], ESG_SOURCE)
        self.assertEqual(payload["note"], ESG_NOTE)
        self.assertEqual(payload["time_sensitivity_note"], ESG_TIME_SENSITIVITY_NOTE)
        self.assertNotIn("verdict", payload)
        self.assertNotIn("score_breakdown", payload)
        self.assertNotIn("integrity_veto", payload)

    def test_data_as_of_null_when_absent(self):
        r = _escore()
        self.assertIsNone(r["data_as_of"])

    def test_flags_reflected(self):
        r = _escore(stranded_asset=True, esg_tail=True)
        self.assertTrue(r["stranded_asset_triggered"])
        self.assertTrue(r["esg_tail_triggered"])


class TestEsgCLI(unittest.TestCase):
    """CLI 入口：esg 子命令输出 JSON、非法档位/数值退出码。"""

    _TOOL = str(_PROJECT_ROOT / "tools" / "specialized" /
                "governance_data.py")

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, self._TOOL, "esg", *args],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )

    def test_cli_valid_json(self):
        out = self._run("--env-risk-level", "高", "--transition-pathway", "无",
                        "--stranded-asset", "--esg-tail",
                        "--position-cap-base", "20", "--as-of", "2026-09-16")
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["discount_factor"], 0.8)
        self.assertEqual(payload["discount_rate_adj_bps"], 150)
        self.assertEqual(payload["position_cap_after"], 15.0)

    def test_cli_env_risk_level_required(self):
        out = self._run("--transition-pathway", "无")
        self.assertNotEqual(out.returncode, 0)

    def test_cli_invalid_env_exit_code(self):
        out = self._run("--env-risk-level", "中")
        self.assertEqual(out.returncode, 1)
        self.assertIn("非法", out.stdout)

    def test_cli_invalid_base_exit_code(self):
        out = self._run("--env-risk-level", "高", "--position-cap-base", "101")
        self.assertEqual(out.returncode, 1)
        self.assertIn("错误", out.stdout)


if __name__ == "__main__":
    unittest.main()