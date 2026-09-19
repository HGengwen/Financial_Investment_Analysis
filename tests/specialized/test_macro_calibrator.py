#!/usr/bin/env python3
"""Unit tests for macro_calibrator.py 宏观三表硬编码 + stage 判定查表。

覆盖 P2-1 / P2-2 / P2-3 交付物的核心验收标准：
1. 美林四档枚举与四表主键统一（决策 D2）
2. 四张表逐格值与框架第五部分·四（行 687-747）一致（决策 D3/D4/D5）
3. summary() 聚合字段完整（rate/econ/merrill 三子表 + peg_interval/cash_floor/single_cap）
4. stage 枚举护栏（非法值抛 ValueError，列出合法枚举）
5. JSON 可序列化（json.loads 往返一致）
6. CLI stage 子命令退出码（合法=0，非法=1）
7. calibrate 三棒纯函数（PEG 判定顺序 / 现金下限 / 单只上限三档）与 validation 可审计
8. calibrate CLI（显式 --stage 与 --from-data、输入校验非零退出）
"""

import argparse
import io
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

# 注入项目根，使 tools 包可被导入（跨平台动态注入）。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import tools.specialized.macro_calibrator as mc
from tools.specialized.macro_calibrator import (
    STAGE_ENUM,
    STAGE_COORD_MAP,
    RATE_TABLE,
    ECON_TABLE,
    MERRILL_TABLE,
    CALIBRATE_PEG,
    CALIBRATE_CASH_FLOOR,
    CALIBRATE_SINGLE_CAP,
    STAKE_TIER_ENUM,
    PEG_RED_FLAG_THRESHOLD,
    rate_stage,
    econ_stage,
    merrill_stage,
    summary,
    calibrate_peg,
    calibrate_cash,
    calibrate_single,
    calibrate,
    cmd_calibrate,
    classify_rate_stage,
    classify_econ_stage,
    fetch_macro_indicators,
    _parse_date,
    _parse_month_cn,
    _parse_month_int,
    _to_float_or_none,
)

# 脚本绝对路径，用于 CLI 冒烟测试。
_SCRIPT_PATH = _PROJECT_ROOT / "tools" / "specialized" / "macro_calibrator.py"

# ---------------------------------------------------------------------------
# 期望表（逐格字面量，独立于实现，供全量一致性断言）
# ---------------------------------------------------------------------------

_EXPECTED_STAGE_ENUM = ("衰退", "复苏", "过热", "滞胀")

_EXPECTED_COORD = {
    "衰退": {"rate_env": "降息启动（临时按1.0）", "econ_cycle": "衰退档（收紧）"},
    "复苏": {"rate_env": "低利率（放宽至1.5）", "econ_cycle": "中性/复苏档（基准）"},
    "过热": {"rate_env": "加息（收紧至1.0）", "econ_cycle": "过热档（收紧）"},
    "滞胀": {"rate_env": "高利率+信用收缩（0.8）", "econ_cycle": "滞胀档（最紧）"},
}

_EXPECTED_RATE = {
    "衰退": {
        "rate_env": "降息启动（临时按1.0）",
        "peg_interval": [1.0],
        "peg_undervalue": None,
        "peg_overvalue": None,
        "note": "盈利下行+信用收缩主导，估值先杀后抬；宽信用实质落地（信贷脉冲转正）前临时按1.0",
    },
    "复苏": {
        "rate_env": "低利率（放宽至1.5）",
        "peg_interval": [1.2, 1.5],
        "peg_undervalue": "<1.2",
        "peg_overvalue": ">1.5 减仓，>2 绝对透支清机动仓",
        "note": "降息/低利率周期，放宽档",
    },
    "过热": {
        "rate_env": "加息（收紧至1.0）",
        "peg_interval": [0.8, 1.0],
        "peg_undervalue": "<0.7",
        "peg_overvalue": ">1.2",
        "note": "加息/高利率周期，收紧档；0.7~0.8 为低估上沿与合理下沿之间空档，不主动加仓",
    },
    "滞胀": {
        "rate_env": "高利率+信用收缩（0.8）",
        "peg_interval": [0.8],
        "peg_undervalue": None,
        "peg_overvalue": None,
        "note": "较加息档 0.8~1.0 更紧，合理买入上限下探至 0.8；PEG≥0.8 即不新建仓",
    },
}

_EXPECTED_ECON = {
    "衰退": {
        "econ_cycle": "衰退档（收紧）",
        "cash_floor": "30%~40% 或更高",
        "single_init": "≤8%",
        "single_verified": "≤12%",
        "single_absolute": "≤15%",
        "industry_cap": "≤30%",
    },
    "复苏": {
        "econ_cycle": "中性/复苏档（基准）",
        "cash_floor": "10%~20%（估值分位>80%时提高至20%~30%）",
        "single_init": "≤10%",
        "single_verified": "≤15%",
        "single_absolute": "≤20%",
        "industry_cap": "≤40%",
    },
    "过热": {
        "econ_cycle": "过热档（收紧）",
        "cash_floor": "≥25%",
        "single_init": "≤8%",
        "single_verified": "≤12%",
        "single_absolute": "≤15%",
        "industry_cap": "≤25%",
    },
    "滞胀": {
        "econ_cycle": "滞胀档（最紧）",
        "cash_floor": "≥40%",
        "single_init": "≤6%",
        "single_verified": "≤10%",
        "single_absolute": "≤12%",
        "industry_cap": "≤20%",
    },
}

_EXPECTED_MERRILL = {
    "衰退": {
        "rate_credit": "降息启动、信用收缩",
        "style": "防御、低波成长优先",
        "peg_ceiling": 1.0,
        "peg_ceiling_note": "临时收紧",
        "cash_floor": "30%~40%",
        "single_cap_verified": "≤12%",
    },
    "复苏": {
        "rate_credit": "低利率、信用扩张初期",
        "style": "成长/顺周期优先",
        "peg_ceiling": 1.5,
        "peg_ceiling_note": "放宽",
        "cash_floor": "10%~20%",
        "single_cap_verified": "≤15%",
    },
    "过热": {
        "rate_credit": "加息、信用扩张见顶",
        "style": "周期/价值优先",
        "peg_ceiling": 1.0,
        "peg_ceiling_note": "收紧",
        "cash_floor": "≥25%",
        "single_cap_verified": "≤12%",
    },
    "滞胀": {
        "rate_credit": "高利率、信用收缩",
        "style": "现金/防御为主",
        "peg_ceiling": 0.8,
        "peg_ceiling_note": "最紧",
        "cash_floor": "≥40%",
        "single_cap_verified": "≤10%",
    },
}

_EXPECTED_CALIBRATE_PEG = {
    "衰退": {"peg_ceiling": 1.0, "peg_under": None, "peg_over": None},
    "复苏": {"peg_ceiling": 1.5, "peg_under": 1.2, "peg_over": 1.5},
    "过热": {"peg_ceiling": 1.0, "peg_under": 0.7, "peg_over": 1.2},
    "滞胀": {"peg_ceiling": 0.8, "peg_under": None, "peg_over": None},
}

_EXPECTED_CALIBRATE_CASH = {"衰退": 30.0, "复苏": 10.0, "过热": 25.0, "滞胀": 40.0}

_EXPECTED_CALIBRATE_SINGLE = {
    "衰退": {"initial": 8.0, "verified": 12.0, "absolute": 15.0, "industry_cap": 30.0},
    "复苏": {"initial": 10.0, "verified": 15.0, "absolute": 20.0, "industry_cap": 40.0},
    "过热": {"initial": 8.0, "verified": 12.0, "absolute": 15.0, "industry_cap": 25.0},
    "滞胀": {"initial": 6.0, "verified": 10.0, "absolute": 12.0, "industry_cap": 20.0},
}


class TestStageEnum(unittest.TestCase):
    """美林四档枚举与四表主键统一（决策 D2）。"""

    def test_stage_enum_values(self):
        """枚举恰为中文四档，顺序固定。"""
        self.assertEqual(STAGE_ENUM, _EXPECTED_STAGE_ENUM)

    def test_all_tables_share_stage_keys(self):
        """四张表主键均与 STAGE_ENUM 完全一致（零换算直查）。"""
        keys = set(STAGE_ENUM)
        self.assertEqual(set(STAGE_COORD_MAP.keys()), keys)
        self.assertEqual(set(RATE_TABLE.keys()), keys)
        self.assertEqual(set(ECON_TABLE.keys()), keys)
        self.assertEqual(set(MERRILL_TABLE.keys()), keys)


class TestStageCoordMap(unittest.TestCase):
    """表 D：宏观阶段坐标换算关系逐格一致。"""

    def test_coord_map_matches_spec(self):
        self.assertEqual(STAGE_COORD_MAP, _EXPECTED_COORD)


class TestRateTable(unittest.TestCase):
    """表 A：利率环境 → PEG 参数逐格一致（含 null 位，决策 D3）。"""

    def test_rate_table_matches_spec(self):
        self.assertEqual(RATE_TABLE, _EXPECTED_RATE)

    def test_none_for_unspecified_stages(self):
        """衰退/滞胀的低估、高估阈值未显式给出，保留 None 不臆造。"""
        for stage in ("衰退", "滞胀"):
            self.assertIsNone(RATE_TABLE[stage]["peg_undervalue"])
            self.assertIsNone(RATE_TABLE[stage]["peg_overvalue"])

    def test_single_element_interval_for_upper_only_stages(self):
        """衰退/滞胀 PEG 区间仅上限，单元素列表。"""
        self.assertEqual(RATE_TABLE["衰退"]["peg_interval"], [1.0])
        self.assertEqual(RATE_TABLE["滞胀"]["peg_interval"], [0.8])


class TestEconTable(unittest.TestCase):
    """表 B：经济周期 → 现金仓位与个股上限逐格一致（决策 D4/D5）。"""

    def test_econ_table_matches_spec(self):
        self.assertEqual(ECON_TABLE, _EXPECTED_ECON)

    def test_cash_floor_kept_as_original_string(self):
        """cash_floor 保留框架原文字符串，不做数值解析（决策 D5）。"""
        self.assertEqual(ECON_TABLE["衰退"]["cash_floor"], "30%~40% 或更高")
        self.assertEqual(ECON_TABLE["复苏"]["cash_floor"],
                         "10%~20%（估值分位>80%时提高至20%~30%）")
        self.assertEqual(ECON_TABLE["滞胀"]["cash_floor"], "≥40%")


class TestMerrillTable(unittest.TestCase):
    """表 C：美林时钟矩阵逐格一致。"""

    def test_merrill_table_matches_spec(self):
        self.assertEqual(MERRILL_TABLE, _EXPECTED_MERRILL)

    def test_peg_ceiling_is_numeric(self):
        """peg_ceiling 为数值型（float），peg_ceiling_note 为口径备注。"""
        self.assertIsInstance(MERRILL_TABLE["滞胀"]["peg_ceiling"], float)
        self.assertEqual(MERRILL_TABLE["滞胀"]["peg_ceiling_note"], "最紧")


class TestSummary(unittest.TestCase):
    """summary() 聚合三表输出完整参数表（验收标准 1）。"""

    def test_summary_contains_all_keys(self):
        """四档均输出顶层四个字段与三类子表行。"""
        required_top = {"stage", "rate_stage", "econ_stage",
                        "merrill_stage", "peg_interval", "cash_floor", "single_cap"}
        for stage in STAGE_ENUM:
            result = summary(stage)
            self.assertEqual(set(result.keys()), required_top)
            self.assertEqual(result["stage"], stage)

    def test_summary_aggregation_fields(self):
        """聚合字段来源正确：PEG 区间取表 A，现金与单只取表 B。"""
        r = summary("过热")
        self.assertEqual(r["peg_interval"], RATE_TABLE["过热"]["peg_interval"])
        self.assertEqual(r["cash_floor"], ECON_TABLE["过热"]["cash_floor"])
        # single_cap 取「验证后」档（决策 D4）
        self.assertEqual(r["single_cap"], ECON_TABLE["过热"]["single_verified"])

    def test_single_cap_equals_verified(self):
        """四档 single_cap 均等于表 B 的 single_verified（决策 D4）。"""
        for stage in STAGE_ENUM:
            self.assertEqual(summary(stage)["single_cap"],
                             ECON_TABLE[stage]["single_verified"])

    def test_sub_rows_have_no_stage_key(self):
        """summary 子表行为纯表行，对齐方案 4.3 schema（stage 顶层统一回显）。"""
        r = summary("复苏")
        self.assertNotIn("stage", r["rate_stage"])
        self.assertNotIn("stage", r["econ_stage"])
        self.assertNotIn("stage", r["merrill_stage"])


class TestStageValidation(unittest.TestCase):
    """stage 枚举护栏（验收标准 5）。"""

    def test_invalid_stage_raises_and_lists_valid(self):
        """非法 stage 抛 ValueError，并列出合法枚举。"""
        with self.assertRaises(ValueError) as ctx:
            summary("扩张")
        self.assertIn("合法枚举", str(ctx.exception))
        for valid in STAGE_ENUM:
            self.assertIn(valid, str(ctx.exception))

    def test_empty_stage_raises(self):
        with self.assertRaises(ValueError):
            rate_stage("")


class TestJsonSerializable(unittest.TestCase):
    """JSON 可解析（验收标准 4）。"""

    def test_summary_json_roundtrip(self):
        """summary 四档结果 json.dumps 后 json.loads 往返一致。"""
        for stage in STAGE_ENUM:
            result = summary(stage)
            dumped = json.dumps(result, ensure_ascii=False, indent=2)
            self.assertEqual(json.loads(dumped), result)


class TestCli(unittest.TestCase):
    """CLI stage 子命令退出码（验收标准 6）。"""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        """以当前解释器运行 CLI 脚本，捕获输出与退出码。"""
        env = dict(os.environ, PYTHONUTF8="1")
        return subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def test_cli_stage_valid_returns_zero(self):
        """合法 stage 退出码 0，且 stdout 为可解析 JSON。"""
        proc = self._run_cli("stage", "--stage", "复苏")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["stage"], "复苏")

    def test_cli_stage_invalid_returns_nonzero(self):
        """非法 stage 退出码非 0（枚举护栏）。"""
        proc = self._run_cli("stage", "--stage", "扩张")
        self.assertNotEqual(proc.returncode, 0)


# ---------------------------------------------------------------------------
# P2-2 新增：数值解析 / 缓存三态 / 软判定 / data CLI
# ---------------------------------------------------------------------------

def _make_indicator(value=None, status="ok", trend=None, unit="%"):
    """构造 P2-2 指标条目（测试用轻量工厂）。"""
    return {"value": value, "unit": unit, "as_of": "2026-08", "source": "akshare",
            "status": status, "trend": trend}


class TestParseHelpers(unittest.TestCase):
    """日期/月份/数值解析工具（P2-2 纯函数）。"""

    def test_to_float_or_none_valid(self):
        self.assertEqual(_to_float_or_none("1.5"), 1.5)
        self.assertEqual(_to_float_or_none(2), 2.0)

    def test_to_float_or_none_invalid(self):
        self.assertIsNone(_to_float_or_none(None))
        self.assertIsNone(_to_float_or_none(""))
        self.assertIsNone(_to_float_or_none("abc"))
        self.assertIsNone(_to_float_or_none(float("nan")))

    def test_parse_date(self):
        key, label = _parse_date("2026-09-14")
        self.assertEqual(key, datetime(2026, 9, 14))
        self.assertEqual(label, "2026-09-14")

    def test_parse_month_cn(self):
        key, label = _parse_month_cn("2026年08月份")
        self.assertEqual(key, (2026, 8))
        self.assertEqual(label, "2026-08")

    def test_parse_month_int(self):
        key, label = _parse_month_int("202604")
        self.assertEqual(key, (2026, 4))
        self.assertEqual(label, "2026-04")

    def test_parse_month_int_invalid(self):
        key, label = _parse_month_int("垃圾")
        self.assertIsNone(key)
        self.assertEqual(label, "垃圾")


class TestClassifyRateStage(unittest.TestCase):
    """利率阶段软判定（决策 D1：无数值阈值，可审计）。"""

    def _indicators(self, trend=None, credit=None, cn_value=1.68):
        indicators = {"cn_10y_yield": _make_indicator(cn_value, trend=trend)}
        if credit is not None:
            indicators["credit_impulse"] = _make_indicator(credit, unit="比率")
        return indicators

    def test_insufficient_when_cn10y_missing(self):
        result = classify_rate_stage({})
        self.assertEqual(result["stage"], "数据不足")
        self.assertTrue(result["manual_review"])

    def test_down_trend_is_low_rate(self):
        result = classify_rate_stage(self._indicators(trend="down", credit=0.1))
        self.assertEqual(result["stage"], "降息/低利率")

    def test_flat_trend_is_neutral(self):
        result = classify_rate_stage(self._indicators(trend="flat", credit=0.1))
        self.assertEqual(result["stage"], "中性")

    def test_up_trend_is_high_rate(self):
        result = classify_rate_stage(self._indicators(trend="up", credit=0.1))
        self.assertEqual(result["stage"], "加息/高利率")

    def test_up_trend_with_credit_contraction_is_stagflation(self):
        result = classify_rate_stage(self._indicators(trend="up", credit=-0.1))
        self.assertEqual(result["stage"], "高利率+信用收缩（滞胀）")

    def test_result_carry_audit_fields(self):
        result = classify_rate_stage(self._indicators(trend="down", credit=0.1))
        self.assertIn("confidence", result)
        self.assertIn("basis", result)
        self.assertTrue(result["manual_review"])


class TestClassifyEconStage(unittest.TestCase):
    """经济阶段（美林四档）软判定（决策 D1）。"""

    def _indicators(self, credit=None, pmi=None, rate_trend=None):
        indicators = {}
        if credit is not None:
            indicators["credit_impulse"] = _make_indicator(credit, unit="比率")
        if pmi is not None:
            indicators["pmi_manufacturing"] = _make_indicator(pmi, unit="点")
        if rate_trend is not None:
            indicators["cn_10y_yield"] = _make_indicator(1.68, trend=rate_trend)
        return indicators

    def test_insufficient_when_credit_missing(self):
        self.assertEqual(classify_econ_stage({})["stage"], "数据不足")

    def test_stagflation_on_triple_signal(self):
        indicators = self._indicators(credit=-0.1, pmi=49.0, rate_trend="up")
        self.assertEqual(classify_econ_stage(indicators)["stage"], "滞胀")

    def test_recession_on_credit_and_pmi(self):
        indicators = self._indicators(credit=-0.1, pmi=49.0, rate_trend="down")
        self.assertEqual(classify_econ_stage(indicators)["stage"], "衰退")

    def test_recession_on_credit_only(self):
        indicators = self._indicators(credit=-0.1)
        self.assertEqual(classify_econ_stage(indicators)["stage"], "衰退")

    def test_recovery_on_credit_and_pmi(self):
        indicators = self._indicators(credit=0.1, pmi=51.0)
        self.assertEqual(classify_econ_stage(indicators)["stage"], "复苏")

    def test_recovery_on_credit_only(self):
        indicators = self._indicators(credit=0.1)
        self.assertEqual(classify_econ_stage(indicators)["stage"], "复苏")

    def test_result_carry_audit_fields(self):
        indicators = self._indicators(credit=-0.1, pmi=49.0)
        result = classify_econ_stage(indicators)
        self.assertIn("confidence", result)
        self.assertIn("basis", result)
        self.assertTrue(result["manual_review"])


class TestFetchMacroIndicators(unittest.TestCase):
    """缓存三态 hit / refresh / stale（无网络，mock 断言）。"""

    def _snapshot(self, ok=True):
        indicators = {"cn_10y_yield": _make_indicator(1.68 if ok else None,
                                                      status="ok" if ok else "insufficient")}
        return {"data_ts": "2026-09-15", "indicators": indicators,
                "source": "akshare", "degraded": not ok}

    def test_hit_when_fresh(self):
        data = self._snapshot()
        with mock.patch.object(mc, "_is_cache_fresh", return_value=True), \
                mock.patch.object(mc, "_read_cache", return_value=data):
            result = fetch_macro_indicators()
        self.assertEqual(result["cache_status"], "hit")

    def test_refresh_writes_cache(self):
        data = self._snapshot()
        with mock.patch.object(mc, "_is_cache_fresh", return_value=False), \
                mock.patch.object(mc, "_fetch_fresh", return_value=data), \
                mock.patch.object(mc, "_atomic_write_json") as write:
            result = fetch_macro_indicators()
        self.assertEqual(result["cache_status"], "refresh")
        write.assert_called_once_with(data, mc._MACRO_CACHE_FILE)

    def test_stale_on_refresh_failure(self):
        stale = self._snapshot()
        with mock.patch.object(mc, "_is_cache_fresh", return_value=False), \
                mock.patch.object(mc, "_fetch_fresh", side_effect=RuntimeError("boom")), \
                mock.patch.object(mc, "_read_cache", return_value=stale):
            result = fetch_macro_indicators()
        self.assertEqual(result["cache_status"], "stale")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["source"], "cache_stale")

    def test_raises_without_cache_on_refresh_failure(self):
        with mock.patch.object(mc, "_is_cache_fresh", return_value=False), \
                mock.patch.object(mc, "_fetch_fresh", side_effect=RuntimeError("boom")), \
                mock.patch.object(mc, "_read_cache", return_value=None):
            with self.assertRaises(RuntimeError):
                fetch_macro_indicators()

    def test_raises_when_all_indicators_fail_and_no_cache(self):
        all_fail = self._snapshot(ok=False)
        with mock.patch.object(mc, "_is_cache_fresh", return_value=False), \
                mock.patch.object(mc, "_fetch_fresh", return_value=all_fail), \
                mock.patch.object(mc, "_read_cache", return_value=None):
            with self.assertRaises(RuntimeError):
                fetch_macro_indicators()


class TestDataCli(unittest.TestCase):
    """data 子命令 CLI 冒烟（不触发网络）。"""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONUTF8="1")
        return subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def test_cli_data_help_returns_zero(self):
        proc = self._run_cli("data", "--help")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("--no-cache", proc.stdout)


# ---------------------------------------------------------------------------
# P2-3 新增：calibrate 三棒纯函数 / 常量表 / validation / CLI
# ---------------------------------------------------------------------------

class TestCalibrateTables(unittest.TestCase):
    """三张校准数值常量表逐格一致（P2-3 决策 D2/D3/D4）。"""

    def test_calibrate_peg_matches_spec(self):
        self.assertEqual(CALIBRATE_PEG, _EXPECTED_CALIBRATE_PEG)

    def test_calibrate_cash_matches_spec(self):
        self.assertEqual(CALIBRATE_CASH_FLOOR, _EXPECTED_CALIBRATE_CASH)

    def test_calibrate_single_matches_spec(self):
        self.assertEqual(CALIBRATE_SINGLE_CAP, _EXPECTED_CALIBRATE_SINGLE)

    def test_tier_enum_and_red_flag_constant(self):
        self.assertEqual(STAKE_TIER_ENUM, ("initial", "verified", "absolute"))
        self.assertEqual(PEG_RED_FLAG_THRESHOLD, 2.0)

    def test_all_tables_share_stage_keys(self):
        """三张 P2-3 常量表主键均与 STAGE_ENUM 一致。"""
        keys = set(STAGE_ENUM)
        self.assertEqual(set(CALIBRATE_PEG.keys()), keys)
        self.assertEqual(set(CALIBRATE_CASH_FLOOR.keys()), keys)
        self.assertEqual(set(CALIBRATE_SINGLE_CAP.keys()), keys)


class TestCalibratePeg(unittest.TestCase):
    """PEG 校准判定顺序（方案 3.3）与红线阈值。"""

    def test_recovery_undervalue(self):
        self.assertEqual(calibrate_peg("复苏", 1.0)["verdict"], "低估（可加仓）")

    def test_recovery_reasonable(self):
        self.assertEqual(calibrate_peg("复苏", 1.3)["verdict"], "合理买入")

    def test_overheat_reasonable_upper_boundary(self):
        # 过热：ceiling=1.0，over=1.2；1.1 落于 (1.0, 1.2] → 合理偏贵持有。
        self.assertEqual(calibrate_peg("过热", 1.1)["verdict"], "合理偏贵（持有不加仓）")

    def test_overheat_overvalue(self):
        self.assertEqual(calibrate_peg("过热", 1.4)["verdict"], "高估（减机动仓）")

    def test_recession_no_over_threshold_exceeds_ceiling(self):
        # 衰退无 under/over，PEG>1.0 即不新建仓。
        self.assertEqual(calibrate_peg("衰退", 1.5)["verdict"], "超出合理上限（不新建仓）")

    def test_recession_within_ceiling(self):
        self.assertEqual(calibrate_peg("衰退", 0.8)["verdict"], "合理买入")

    def test_stagflation_exceeds_ceiling(self):
        self.assertEqual(calibrate_peg("滞胀", 0.9)["verdict"], "超出合理上限（不新建仓）")

    def test_stagflation_reasonable(self):
        self.assertEqual(calibrate_peg("滞胀", 0.7)["verdict"], "合理买入")

    def test_red_flag_strictly_greater_than_two(self):
        self.assertTrue(calibrate_peg("复苏", 2.5)["red_flag"])
        self.assertFalse(calibrate_peg("复苏", 2.0)["red_flag"])

    def test_compare_string_carries_comparison(self):
        """compare 字段用于 validation 可审计，非空且含箭头。"""
        self.assertIn("→", calibrate_peg("复苏", 1.3)["compare"])

    def test_invalid_stage_raises(self):
        with self.assertRaises(ValueError):
            calibrate_peg("扩张", 1.0)

    def test_non_positive_peg_raises(self):
        with self.assertRaises(ValueError):
            calibrate_peg("复苏", 0)
        with self.assertRaises(ValueError):
            calibrate_peg("复苏", -1.0)


class TestCalibrateCash(unittest.TestCase):
    """现金下限与达标判定（方案 3.4）。"""

    def test_floor_values(self):
        self.assertEqual(calibrate_cash("衰退", 0)["cash_floor_min"], 30.0)
        self.assertEqual(calibrate_cash("复苏", 0)["cash_floor_min"], 10.0)
        self.assertEqual(calibrate_cash("过热", 0)["cash_floor_min"], 25.0)
        self.assertEqual(calibrate_cash("滞胀", 0)["cash_floor_min"], 40.0)

    def test_ok_when_above_floor(self):
        self.assertTrue(calibrate_cash("复苏", 15.0)["cash_ok"])
        self.assertEqual(calibrate_cash("复苏", 15.0)["cash_gap"], 5.0)

    def test_not_ok_when_below_floor(self):
        result = calibrate_cash("过热", 10.0)
        self.assertFalse(result["cash_ok"])
        self.assertEqual(result["cash_gap"], -15.0)

    def test_equality_counts_as_ok(self):
        result = calibrate_cash("滞胀", 40.0)
        self.assertTrue(result["cash_ok"])
        self.assertEqual(result["cash_gap"], 0.0)

    def test_original_cash_floor_string_preserved(self):
        self.assertEqual(calibrate_cash("复苏", 15.0)["cash_floor"],
                         ECON_TABLE["复苏"]["cash_floor"])

    def test_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            calibrate_cash("复苏", -1.0)
        with self.assertRaises(ValueError):
            calibrate_cash("复苏", 100.1)


class TestCalibrateSingle(unittest.TestCase):
    """单只上限三档与超限判定（方案 3.5，决策 D4）。"""

    def test_default_tier_is_verified(self):
        self.assertEqual(calibrate_single("复苏", 0)["single_cap_value"], 15.0)
        self.assertEqual(calibrate_single("复苏", 0)["single_cap_upper"], "≤15%")

    def test_initial_tier_maps_to_single_init(self):
        # 回归：tier="initial" 不得再拼接成不存在的 single_initial 列（KeyError 修复）。
        result = calibrate_single("过热", 0, tier="initial")
        self.assertEqual(result["single_cap_value"], 8.0)
        self.assertEqual(result["single_cap_upper"], "≤8%")

    def test_absolute_tier(self):
        result = calibrate_single("滞胀", 0, tier="absolute")
        self.assertEqual(result["single_cap_value"], 12.0)
        self.assertEqual(result["single_cap_upper"], "≤12%")

    def test_all_tiers_present_in_single_caps(self):
        caps = calibrate_single("衰退", 0)["single_caps"]
        self.assertEqual(caps, {
            "initial": "≤8%",
            "verified": "≤12%",
            "absolute": "≤15%",
        })

    def test_industry_cap(self):
        self.assertEqual(calibrate_single("复苏", 0)["industry_cap"], "≤40%")
        self.assertEqual(calibrate_single("滞胀", 0)["industry_cap"], "≤20%")

    def test_over_limit_detection(self):
        result = calibrate_single("过热", 20.0, tier="initial")
        self.assertFalse(result["single_cap_ok"])
        self.assertEqual(result["single_cap_gap"], -12.0)

    def test_invalid_tier_raises(self):
        with self.assertRaises(ValueError):
            calibrate_single("复苏", 0, tier="unknown")


class TestCalibrate(unittest.TestCase):
    """顶层 calibrate() 聚合与 validation 可审计（决策 D6）。"""

    def test_top_level_structure(self):
        result = calibrate("复苏", 1.3, 15.0, 12.0)
        for key in ("stage", "peg", "current_cash", "single_stake",
                    "stake_tier", "calibrated_peg_verdict", "cash_floor",
                    "single_cap_upper", "validation"):
            self.assertIn(key, result)

    def test_validation_is_auditable(self):
        result = calibrate("复苏", 1.3, 15.0, 12.0)
        v = result["validation"]
        self.assertEqual(v["stage_source"], "explicit")
        self.assertEqual(v["inputs"]["stake_tier"], "verified")
        self.assertIn("RATE_TABLE", v["rate_source"])
        self.assertIn("ECON_TABLE", v["econ_source"])
        self.assertIn("→", v["peg_compare"])
        self.assertIn("→", v["cash_compare"])
        self.assertIn("→", v["single_compare"])

    def test_recovery_note_issued(self):
        result = calibrate("复苏", 1.3, 15.0, 12.0)
        self.assertIn("估值分位", result["validation"]["note"])

    def test_no_note_for_other_stages(self):
        self.assertEqual(calibrate("过热", 1.0, 25.0, 10.0)["validation"]["note"], "")

    def test_json_serializable(self):
        result = calibrate("滞胀", 0.7, 40.0, 6.0, tier="initial")
        self.assertEqual(json.loads(json.dumps(result, ensure_ascii=False)), result)


class TestCalibrateCli(unittest.TestCase):
    """calibrate 子命令 CLI 冒烟：显式 stage / 输入校验 / 缓存软判定。"""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONUTF8="1")
        return subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def test_cli_calibrate_valid_returns_zero(self):
        proc = self._run_cli("calibrate", "--stage", "复苏", "--peg", "1.3",
                             "--current-cash", "15", "--single-stake", "12")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["stage"], "复苏")
        self.assertEqual(data["stake_tier"], "verified")
        self.assertEqual(data["calibrated_peg_verdict"]["verdict"], "合理买入")

    def test_cli_calibrate_negative_peg_returns_nonzero(self):
        proc = self._run_cli("calibrate", "--stage", "复苏", "--peg", "-1",
                             "--current-cash", "15", "--single-stake", "12")
        self.assertNotEqual(proc.returncode, 0)

    def test_cli_calibrate_invalid_pct_returns_nonzero(self):
        proc = self._run_cli("calibrate", "--stage", "复苏", "--peg", "1.3",
                             "--current-cash", "101", "--single-stake", "12")
        self.assertNotEqual(proc.returncode, 0)

    def test_cli_calibrate_initial_tier_returns_zero(self):
        """回归：tier=initial 不再触发 single_initial 列名 KeyError。"""
        proc = self._run_cli("calibrate", "--stage", "过热", "--peg", "1.4",
                             "--current-cash", "10", "--single-stake", "20",
                             "--stake-tier", "initial")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["single_cap_upper"], "≤8%")


class TestCmdCalibrateSoftInfer(unittest.TestCase):
    """cmd_calibrate 的 --from-data 软判定改写（进程内，mock 缓存）。"""

    def _namespace(self, **kwargs):
        base = {"stage": None, "from_data": False, "peg": 1.3,
                "current_cash": 15.0, "single_stake": 12.0, "stake_tier": "verified"}
        base.update(kwargs)
        return argparse.Namespace(**base)

    def test_soft_infer_marks_stage_source_and_manual_review(self):
        cached = {"indicators": {"credit_impulse": _make_indicator(0.1, unit="比率")}}
        with mock.patch.object(mc, "_read_cache", return_value=cached), \
                mock.patch.object(mc, "classify_econ_stage",
                                  return_value={"stage": "复苏"}), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = cmd_calibrate(self._namespace(from_data=True))
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["validation"]["stage_source"], "soft_infer")
        self.assertTrue(data["validation"]["manual_review"])
        self.assertIn("软判定", data["validation"]["note"])

    def test_soft_infer_invalid_stage_returns_nonzero(self):
        cached = {"indicators": {"credit_impulse": _make_indicator(0.1, unit="比率")}}
        with mock.patch.object(mc, "_read_cache", return_value=cached), \
                mock.patch.object(mc, "classify_econ_stage",
                                  return_value={"stage": "数据不足"}), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            code = cmd_calibrate(self._namespace(from_data=True))
        self.assertNotEqual(code, 0)

    def test_no_cache_returns_nonzero(self):
        """--from-data 但缓存缺失时非零退出（不触发网络刷新）。"""
        with mock.patch.object(mc, "_read_cache", return_value=None), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            code = cmd_calibrate(self._namespace(from_data=True))
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()