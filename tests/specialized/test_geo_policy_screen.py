#!/usr/bin/env python3
"""Unit tests for geo_policy_screen.py 三维交叉矩阵 + 国产化率四档判定工具。

覆盖 P3-1 三维交叉矩阵契约：
1. 三维档位词表合法性（越界拒绝，不行归档的灰色地带）
2. 11 条显式命中：六行场景判定 + 赛道两分法
3. 25 条未列组合归档：archived=true 且 archive_from 回显原组合
4. 36 组合全覆盖自检（无重复、无遗漏）
5. 结果可 JSON 序列化（dataclass asdict）

覆盖 P3-2 国产化率四档契约：
6. 四档边界（<5 / [5,20) / [20,50) / [50,100]）
7. 任意行业名可判定（判定只依赖 rate）
8. 战略卡脖子例外精确触发
9. 半导体设备示例可复现
10. 输出可 JSON 序列化
"""

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
from unittest import mock

# Add project root to path for imports (dynamic, cross-platform)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.specialized.geo_policy_screen import (
    CHOKE_POINT_ACTION_HINT,
    FALLBACK_MAP,
    FUND_VALUES,
    GEO_VALUES,
    LOCALIZATION_SOURCE,
    LOCALIZATION_TIERS,
    MATRIX_ROWS,
    POLICY_VALUES,
    ROW_META,
    SCAN_DISCLAIMER,
    SCAN_NOTE,
    SEMICONDUCTOR_COHORTS,
    STRUCTURED_SOURCE_NOTE,
    _normalize_source,
    build_examples,
    localize,
    scan,
    screen,
)

#: 模块级缓存目录隔离（scan 单元测试不得污染真实 data/geo_policy/）。
_CACHE_TMP = None
_PATCHER = None


def setUpModule():
    """将 scan 缓存目录整体重定向到临时目录，测试结束后自动清理。"""
    global _CACHE_TMP, _PATCHER
    _CACHE_TMP = tempfile.TemporaryDirectory()
    _PATCHER = mock.patch(
        "tools.specialized.geo_policy_screen.SCAN_CACHE_DIR",
        Path(_CACHE_TMP.name))
    _PATCHER.start()


def tearDownModule():
    """停止缓存目录补丁并清理临时目录。"""
    global _CACHE_TMP, _PATCHER
    if _PATCHER is not None:
        _PATCHER.stop()
        _PATCHER = None
    if _CACHE_TMP is not None:
        _CACHE_TMP.cleanup()
        _CACHE_TMP = None


class TestVocabLegalValues(unittest.TestCase):
    """三维档位词表为离散合法取值，越界即拒绝。"""

    def test_geo_values(self):
        self.assertEqual(GEO_VALUES, ("高", "中", "低"))

    def test_policy_values(self):
        self.assertEqual(POLICY_VALUES, ("高", "中", "低"))

    def test_fund_values(self):
        self.assertEqual(
            FUND_VALUES, ("有直接注资", "有专项子基金", "有覆盖", "无覆盖"))

    def test_invalid_geo_rejected(self):
        with self.assertRaises(ValueError):
            screen("超高", "高", "有直接注资")

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            screen("高", "非常", "有直接注资")

    def test_invalid_fund_rejected(self):
        with self.assertRaises(ValueError):
            screen("高", "高", "注资")

    def test_invalid_all_rejected_without_archive(self):
        """越界组合不得进入归档，必须直接抛错。"""
        for combo in (("", "", ""), ("高", "", "有覆盖"), ("", "低", "")):
            with self.assertRaises(ValueError):
                screen(*combo)


class TestFullCoverage(unittest.TestCase):
    """36 组合（3×3×4）自检：显式与归档无重复、无遗漏。"""

    def test_11_exact_rows(self):
        self.assertEqual(len(MATRIX_ROWS), 11)

    def test_25_fallback(self):
        self.assertEqual(len(FALLBACK_MAP), 25)

    def test_no_overlap(self):
        self.assertTrue(set(MATRIX_ROWS).isdisjoint(set(FALLBACK_MAP)))

    def test_full_coverage_36(self):
        all_combos = set(product(GEO_VALUES, POLICY_VALUES, FUND_VALUES))
        self.assertEqual(
            set(MATRIX_ROWS) | set(FALLBACK_MAP), all_combos)
        self.assertEqual(len(all_combos), 36)


class TestSixRowsExactHit(unittest.TestCase):
    """六行场景（框架第 0 步·0.3）各取一条显式命中，校验结论与赛道两分法。"""

    def test_row1_optimal(self):
        r = screen("高", "高", "有直接注资")
        self.assertEqual(r.row_index, 1)
        self.assertEqual(r.matrix_row, "最优场景")
        self.assertEqual(r.track_type, "地缘倒逼型")
        self.assertFalse(r.archived)

    def test_row2_suboptimal(self):
        r = screen("高", "中", "有专项子基金")
        self.assertEqual(r.row_index, 2)
        self.assertEqual(r.matrix_row, "次优场景")
        self.assertEqual(r.track_type, "地缘倒逼型")
        self.assertFalse(r.archived)

    def test_row3_latent(self):
        r = screen("中", "高", "有覆盖")
        self.assertEqual(r.row_index, 3)
        self.assertEqual(r.matrix_row, "潜伏场景")
        self.assertEqual(r.track_type, "地缘倒逼型")
        self.assertFalse(r.archived)

    def test_row4_high_risk(self):
        r = screen("高", "低", "无覆盖")
        self.assertEqual(r.row_index, 4)
        self.assertEqual(r.matrix_row, "高风险/回避")
        self.assertEqual(r.track_type, "地缘倒逼型")
        self.assertFalse(r.archived)

    def test_row5_policy_driven(self):
        r = screen("低", "高", "有直接注资")
        self.assertEqual(r.row_index, 5)
        self.assertEqual(r.matrix_row, "政策驱动型增量创造")
        self.assertEqual(r.track_type, "政策资本驱动型")
        self.assertFalse(r.archived)

    def test_row6_avoid(self):
        r = screen("低", "低", "无覆盖")
        self.assertEqual(r.row_index, 6)
        self.assertEqual(r.matrix_row, "回避")
        self.assertEqual(r.track_type, "回避")
        self.assertFalse(r.archived)


class TestTrackTypeMapping(unittest.TestCase):
    """赛道两分法：行 1~4 地缘倒逼型、行 5 政策资本驱动型、行 6 回避。"""

    def test_track_type_by_row(self):
        expected = {1: "地缘倒逼型", 2: "地缘倒逼型", 3: "地缘倒逼型",
                    4: "地缘倒逼型", 5: "政策资本驱动型", 6: "回避"}
        for row, track_type in expected.items():
            self.assertEqual(ROW_META[row]["track_type"], track_type, row)


class TestFallbackArchiving(unittest.TestCase):
    """25 条未列组合一律按更审慎相邻档归档并回显。"""

    def test_all_fallback_archived(self):
        for combo, (row, _note) in FALLBACK_MAP.items():
            r = screen(*combo)
            self.assertTrue(r.archived, combo)
            self.assertEqual(r.row_index, row, combo)
            self.assertEqual(
                r.archive_from, f"{combo[0]}/{combo[1]}/{combo[2]}", combo)

    def test_high_mid_covered_archives_to_row4(self):
        """框架点名的高/中/有覆盖 → 更审慎相邻档 = 高风险/回避（行 4）。"""
        r = screen("高", "中", "有覆盖")
        self.assertTrue(r.archived)
        self.assertEqual(r.row_index, 4)


class TestJSONSerialization(unittest.TestCase):
    """结果可 JSON 序列化，且关键字段齐备。"""

    def test_exact_json_serializable(self):
        r = screen("高", "高", "有直接注资", as_of="2026-09-15", basis="单元测试")
        payload = asdict(r)
        self.assertIsNotNone(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(payload["input"]["as_of"], "2026-09-15")
        self.assertEqual(payload["input"]["basis"], "单元测试")

    def test_fallback_json_serializable(self):
        r = screen("高", "中", "有覆盖")
        payload = asdict(r)
        self.assertIsNotNone(json.dumps(payload, ensure_ascii=False))
        self.assertTrue(payload["archived"])
        self.assertEqual(payload["archive_from"], "高/中/有覆盖")

    def test_time_sensitive_always_true(self):
        for combo, _ in list(FALLBACK_MAP.items())[:5]:
            self.assertTrue(screen(*combo).time_sensitive)


class TestCLI(unittest.TestCase):
    """CLI 入口：screen 子命令输出 JSON、非法档位退出码 1。"""

    def test_cli_valid_json(self):
        out = subprocess.run(
            [sys.executable, str(_PROJECT_ROOT / "tools" / "specialized" /
                                 "geo_policy_screen.py"),
             "screen", "--geo", "高", "--policy", "高", "--fund", "有直接注资"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["row_index"], 1)

    def test_cli_invalid_exit_code(self):
        out = subprocess.run(
            [sys.executable, str(_PROJECT_ROOT / "tools" / "specialized" /
                                 "geo_policy_screen.py"),
             "screen", "--geo", "超高", "--policy", "高", "--fund", "有覆盖"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn("非法", out.stdout)


class TestLocalizationTierNames(unittest.TestCase):
    """四档中文名与框架一致，且常量自洽。"""

    def test_tier_names(self):
        self.assertEqual(
            {i: t["tier"] for i, t in LOCALIZATION_TIERS.items()},
            {1: "过早", 2: "突破期", 3: "加速投资期", 4: "替代空间收窄"},
        )

    def test_source_constant(self):
        self.assertEqual(LOCALIZATION_SOURCE, "框架第1步")


class TestLocalizationBoundaries(unittest.TestCase):
    """四档边界：<5 / [5,20) / [20,50) / [50,100]。"""

    def test_boundary_classification(self):
        cases = {
            0.0: 1,
            4.999: 1,
            5.0: 2,
            19.999: 2,
            20.0: 3,
            49.999: 3,
            50.0: 4,
            100.0: 4,
        }
        for rate, expected_index in cases.items():
            result = localize("任意行业", rate)
            self.assertEqual(result.tier_index, expected_index, rate)

    def test_boundary_value_5_in_breakthrough(self):
        self.assertEqual(localize("x", 5.0).tier, "突破期")

    def test_boundary_value_20_in_acceleration(self):
        self.assertEqual(localize("x", 20.0).tier, "加速投资期")

    def test_boundary_value_50_in_narrowing(self):
        self.assertEqual(localize("x", 50.0).tier, "替代空间收窄")


class TestLocalizationArbitraryIndustry(unittest.TestCase):
    """判定只依赖 rate，不依赖行业名，天然支持任意行业/领域。"""

    def test_same_rate_same_tier_regardless_industry(self):
        industries = ["半导体设备", "光伏逆变器", "高端数控机床", "创新药", "GPU"]
        for industry in industries:
            result = localize(industry, 35.0)
            self.assertEqual(result.industry, industry)
            self.assertEqual(
                (result.tier, result.tier_index, result.phase, result.action_hint),
                ("加速投资期", 3, "加速投资期", "订单放量"),
            )


class TestStrategicChokePoint(unittest.TestCase):
    """战略卡脖子例外仅 rate<5 且 flag=true 时生效。"""

    def test_choke_point_true_under_5(self):
        result = localize("光刻设备", 0.8, strategic_choke_point=True)
        self.assertTrue(result.choke_point_applied)
        self.assertEqual(result.action_hint, CHOKE_POINT_ACTION_HINT)
        self.assertEqual(result.tier_index, 1)

    def test_choke_point_false_under_5(self):
        result = localize("某冷门环节", 3.0, strategic_choke_point=False)
        self.assertFalse(result.choke_point_applied)
        self.assertEqual(result.action_hint, "观察不建仓")

    def test_choke_point_ignored_at_or_above_5(self):
        result = localize("突破期环节", 8.0, strategic_choke_point=True)
        self.assertFalse(result.choke_point_applied)
        self.assertNotEqual(result.action_hint, CHOKE_POINT_ACTION_HINT)
        self.assertEqual(result.tier_index, 2)


class TestLocalizationValidation(unittest.TestCase):
    """非法输入 fail-fast 拒绝，不落档。"""

    def test_empty_industry_rejected(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError):
                localize(bad, 10.0)

    def test_rate_out_of_range_rejected(self):
        for bad in (-1.0, 100.1, "abc", True):
            with self.assertRaises(ValueError):
                localize("任意行业", bad)


class TestSemiconductorExamples(unittest.TestCase):
    """半导体设备示例可复现框架第 1 步四梯队表。"""

    def test_build_examples_reproducible(self):
        payload = build_examples()
        self.assertEqual(payload["source"], LOCALIZATION_SOURCE)
        self.assertEqual(payload["industry_example"], "半导体设备")
        cohorts = payload["cohorts"]
        self.assertEqual(len(cohorts), len(SEMICONDUCTOR_COHORTS))
        self.assertEqual(
            [c["cohort"] for c in cohorts],
            ["第一梯队（已成熟）", "第二梯队（主力增量）",
             "第三梯队（高弹性）", "光刻（战略卡脖子）"],
        )
        self.assertEqual(cohorts[0]["rate_range"], "50%~90%")
        self.assertEqual(cohorts[0]["tier"], "替代空间收窄")
        self.assertEqual(cohorts[1]["rate_range"], "30%~40%")
        self.assertEqual(cohorts[1]["tier"], "加速投资期")
        self.assertEqual(cohorts[2]["rate_range"], "5%~20%")
        self.assertEqual(cohorts[2]["tier"], "突破期")
        self.assertEqual(cohorts[3]["rate_range"], "<1%")
        self.assertEqual(cohorts[3]["tier"], "过早")
        self.assertTrue(cohorts[3]["choke_point"])

    def test_examples_json_serializable(self):
        self.assertIsNotNone(json.dumps(build_examples(), ensure_ascii=False))


class TestLocalizationJSONSerialization(unittest.TestCase):
    """结果可 JSON 序列化，字段齐备。"""

    def test_localize_json_serializable(self):
        result = localize("量测检测", 12.5, strategic_choke_point=True,
                          as_of="2026-09-15", basis="单元测试")
        payload = asdict(result)
        self.assertIsNotNone(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(payload["tier"], "突破期")
        self.assertEqual(payload["tier_index"], 2)
        self.assertTrue(payload["time_sensitive"])
        self.assertEqual(payload["input"]["as_of"], "2026-09-15")
        self.assertEqual(payload["input"]["basis"], "单元测试")


class TestLocalizationCLI(unittest.TestCase):
    """CLI 入口：localize/examples 子命令输出 JSON、非法 rate 退出码 1。"""

    _TOOL = str(_PROJECT_ROOT / "tools" / "specialized" /
                "geo_policy_screen.py")

    def test_cli_localize_valid_json(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "localize",
             "--industry", "量测检测", "--localization-rate", "12.5"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["tier"], "突破期")

    def test_cli_localize_invalid_rate_exit_code(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "localize",
             "--industry", "x", "--localization-rate", "abc"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn("错误", out.stdout)

    def test_cli_examples_valid_json(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "examples"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(len(json.loads(out.stdout)["cohorts"]), 4)


class TestScanOutputFields(unittest.TestCase):
    """scan 顶层输出强制字段齐备（§3.3，不判档）。"""

    def _anysearch_ok(self, query):
        return [{"title": "出口管制清单", "url": "https://example.com/geo",
                 "snippet": "示例来源摘要", "content": "示例正文"}]

    def test_mandatory_fields_present(self):
        result = scan(
            industry="半导体",
            search_inject={"anysearch": self._anysearch_ok,
                           "doubao_search": None, "exa_search": None},
            now=datetime(2026, 9, 15, 10, 0, 0),
        )
        for field in ("task", "query", "data_as_of", "retrieved_at",
                      "degraded", "degraded_reason", "structured_source",
                      "disclaimer", "note", "dimensions", "snapshot_example"):
            self.assertIn(field, result, field)

    def test_constant_fields(self):
        result = scan(
            industry="半导体",
            search_inject={"anysearch": self._anysearch_ok,
                           "doubao_search": None, "exa_search": None},
            now=datetime(2026, 9, 15, 10, 0, 0),
        )
        self.assertEqual(result["task"], "scan")
        self.assertEqual(result["query"], {"industry": "半导体", "fund": None})
        self.assertEqual(result["data_as_of"], "2026-09-15")
        self.assertEqual(result["retrieved_at"], "2026-09-15T10:00:00")
        self.assertFalse(result["degraded"])
        self.assertIsNone(result["degraded_reason"])
        self.assertEqual(result["disclaimer"], SCAN_DISCLAIMER)
        self.assertEqual(result["note"], SCAN_NOTE)
        self.assertEqual(result["structured_source"], {
            "probed": True, "available": False, "note": STRUCTURED_SOURCE_NOTE})

    def test_dimension_structure(self):
        result = scan(
            industry="半导体",
            search_inject={"anysearch": self._anysearch_ok,
                           "doubao_search": None, "exa_search": None},
            now=datetime(2026, 9, 15, 10, 0, 0),
        )
        dims = result["dimensions"]
        self.assertEqual(len(dims), 1)
        self.assertEqual(dims[0]["dimension"], "geopolitical_risk")
        self.assertEqual(dims[0]["label"], "地缘政治风险")
        self.assertEqual(dims[0]["input_value"], "半导体")
        self.assertEqual(dims[0]["retrieval_status"], "ok")
        self.assertGreater(dims[0]["source_count"], 0)
        self.assertEqual(dims[0]["sources"][0]["source_tool"], "anysearch")


class TestScanInputValidation(unittest.TestCase):
    """scan 输入校验：industry/fund 至少一个，且须非空字符串。"""

    def test_both_missing_rejected(self):
        with self.assertRaises(ValueError):
            scan()

    def test_empty_string_rejected(self):
        inject = {"anysearch": None, "doubao_search": None, "exa_search": None}
        with self.assertRaises(ValueError):
            scan(industry="   ", search_inject=inject)
        with self.assertRaises(ValueError):
            scan(fund="", search_inject=inject)

    def test_non_string_rejected(self):
        with self.assertRaises(ValueError):
            scan(industry=123, search_inject={})


class TestScanSearchBranches(unittest.TestCase):
    """scan 四分支降级语义：首选成功 / 回退 / 全失败空缓存 / 全失败缓存命中。"""

    NOW = datetime(2026, 9, 15, 12, 0, 0)

    def setUp(self):
        # 单元测试隔离缓存目录，避免污染真实 data/geo_policy/ 且互不串扰。
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        patcher = mock.patch(
            "tools.specialized.geo_policy_screen.SCAN_CACHE_DIR",
            Path(self._tmpdir.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _ok_search(tool_results):
        def _fn(_query):
            return tool_results
        return _fn

    def test_preferred_success_not_degraded(self):
        result = scan(
            industry="半导体",
            search_inject={
                "anysearch": self._ok_search([
                    {"title": "t", "url": "https://a.com", "snippet": "s"}]),
                "doubao_search": None,
                "exa_search": None,
            },
            now=self.NOW,
        )
        self.assertFalse(result["degraded"])
        self.assertEqual(result["dimensions"][0]["retrieval_status"], "ok")

    def test_fallback_success_marks_degraded(self):
        result = scan(
            industry="半导体",
            search_inject={
                "anysearch": self._ok_search([]),
                "doubao_search": self._ok_search([
                    {"title": "d", "url": "https://b.com", "summary": "s"}]),
                "exa_search": None,
            },
            now=self.NOW,
        )
        self.assertTrue(result["degraded"])
        self.assertEqual(result["dimensions"][0]["retrieval_status"], "partial")
        self.assertEqual(
            result["dimensions"][0]["sources"][0]["source_tool"], "doubao_search")

    def test_all_failed_empty_cache(self):
        result = scan(
            industry="半导体",
            search_inject={"anysearch": None, "doubao_search": None,
                           "exa_search": None},
            now=self.NOW,
        )
        self.assertTrue(result["degraded"])
        self.assertEqual(result["dimensions"][0]["retrieval_status"], "failed")
        self.assertEqual(result["dimensions"][0]["source_count"], 0)

    def test_all_failed_cache_hit(self):
        # 先写入一份实时缓存，再让实时检索全失败触发回退。
        scan(
            industry="半导体",
            search_inject={
                "anysearch": self._ok_search([
                    {"title": "缓存前", "url": "https://cache.com",
                     "snippet": "c"}]),
                "doubao_search": None,
                "exa_search": None,
            },
            now=self.NOW,
        )
        result = scan(
            industry="半导体",
            search_inject={"anysearch": None, "doubao_search": None,
                           "exa_search": None},
            now=self.NOW,
        )
        self.assertTrue(result["degraded"])
        self.assertEqual(
            result["dimensions"][0]["retrieval_status"], "ok")
        self.assertEqual(
            result["dimensions"][0]["sources"][0]["source_tool"], "cache")


class TestScanNormalization(unittest.TestCase):
    """scan 来源归一化为六字段：title/url/snippet/published_at/source_tool。"""

    def test_anysearch_priority_snippet(self):
        raw = {"title": "t", "url": "u", "snippet": "片段", "content": "正文"}
        normalized = _normalize_source(raw, "anysearch")
        self.assertEqual(normalized["title"], "t")
        self.assertEqual(normalized["url"], "u")
        self.assertEqual(normalized["snippet"], "片段")
        self.assertIsNone(normalized["published_at"])
        self.assertEqual(normalized["source_tool"], "anysearch")

    def test_doubao_map_summary_and_publish_time(self):
        raw = {"title": "t", "url": "u", "summary": "摘要",
               "publish_time": "2026-09-01"}
        normalized = _normalize_source(raw, "doubao_search")
        self.assertEqual(normalized["snippet"], "摘要")
        self.assertEqual(normalized["published_at"], "2026-09-01")

    def test_exa_map_content_and_published_date(self):
        raw = {"title": "t", "url": "u", "content": "正文",
               "published_date": "2026-08-01"}
        normalized = _normalize_source(raw, "exa_search")
        self.assertEqual(normalized["snippet"], "正文")
        self.assertEqual(normalized["published_at"], "2026-08-01")

    def test_snippet_truncated_at_500(self):
        raw = {"title": "t", "url": "u", "snippet": "x" * 600}
        normalized = _normalize_source(raw, "anysearch")
        self.assertEqual(len(normalized["snippet"]), 503)
        self.assertTrue(normalized["snippet"].endswith("..."))


class TestScanJSONSerialization(unittest.TestCase):
    """scan 输出可 JSON 序列化（离线 mock，不依赖网络）。"""

    def test_scan_json_serializable(self):
        result = scan(
            industry="半导体",
            search_inject={
                "anysearch": lambda _q: [{"title": "t", "url": "u",
                                          "snippet": "s"}]},
            now=datetime(2026, 9, 15, 10, 0, 0),
        )
        payload = json.loads(json.dumps(result, ensure_ascii=False))
        self.assertEqual(payload["task"], "scan")
        self.assertIn("dimensions", payload)
        self.assertEqual(payload["dimensions"][0]["dimension"],
                         "geopolitical_risk")


class TestScanCLI(unittest.TestCase):
    """CLI 入口：scan 子命令双缺参数退出码 1（离线，无网络依赖）。"""

    _TOOL = str(_PROJECT_ROOT / "tools" / "specialized" /
                "geo_policy_screen.py")

    def test_cli_scan_both_missing_exit_code(self):
        out = subprocess.run(
            [sys.executable, self._TOOL, "scan"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn("错误", out.stdout)


if __name__ == "__main__":
    unittest.main()