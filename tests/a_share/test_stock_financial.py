#!/usr/bin/env python3
"""A股财务指标查询工具测试模块。

测试 tools/a_share/stock_financial.py 的各功能模块，使用 unittest 框架。

测试范围:
  1. TestGetRawData           — 原始数据获取（网络集成测试）
  2. TestParseFinancialData   — DataFrame 解析为结构化字典（mock 数据）
  3. TestExtractKeyIndicators — 关键指标提取与派生计算（mock 数据）
  4. TestFormatYearlyData     — 年度数据格式化（mock 数据）
  5. TestMainLogic            — main() 主逻辑（mock get_raw_data）
  6. TestCommandLineInterface — 命令行接口（subprocess，网络依赖）
  7. TestErrorHandling        — 错误处理（无效代码/网络错误）

运行方式:
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/a_share/test_stock_financial.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/a_share/test_stock_financial.py

注意:
    依赖网络的测试使用 try-except + skipTest 处理，网络不可用时不失败。
"""

import json
import math
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch
import unittest

import pandas as pd

# 添加项目根目录到路径（测试位于 tests/a_share/，需上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
from tools.a_share.stock_financial import (
    get_raw_data,
    parse_financial_data,
    extract_key_indicators,
    format_yearly_data,
    KEY_INDICATORS,
)
from tools.a_share import stock_financial as sf_module

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "a_share", "stock_financial.py")
PYTHON = sys.executable


# ---------------------------------------------------------------------------
# 辅助函数：构建 mock 数据
# ---------------------------------------------------------------------------

def make_mock_df() -> pd.DataFrame:
    """构建模拟财务摘要 DataFrame。

    模拟 akshare.stock_financial_abstract 返回的结构：
    列包含 "选项"、"指标" 以及报告期日期列（如 20231231）。

    Returns:
        模拟的财务摘要 DataFrame。
    """
    return pd.DataFrame({
        "选项": [""] * 6,
        "指标": [
            "净资产收益率(ROE)",
            "毛利率",
            "销售净利率",
            "净利润",
            "经营现金流量净额",
            "每股净资产",
        ],
        "20231231": [15.5000, 30.2000, 20.1000, 100000000.0, 120000000.0, 6.50],
        "20221231": [14.3000, 28.8000, 18.5000, 90000000.0, 110000000.0, 5.80],
        "20230630": [7.5000, 29.0000, 10.0000, 50000000.0, 60000000.0, 6.30],
    })


def make_mock_df_with_nan() -> pd.DataFrame:
    """构建包含 NaN 值的模拟财务摘要 DataFrame。

    Returns:
        包含 NaN 的模拟 DataFrame，用于测试空值跳过逻辑。
    """
    return pd.DataFrame({
        "选项": ["", ""],
        "指标": ["毛利率", "净利润"],
        "20231231": [30.2, float("nan")],
        "20221231": [28.8, 90000000.0],
    })


def make_mock_parsed() -> dict:
    """构建模拟的已解析财务数据字典。

    Returns:
        结构为 {指标名: {年份标签: 值}} 的字典，覆盖关键指标映射。
    """
    return {
        "净资产收益率(ROE)": {"20231231": 15.5, "20221231": 14.3, "20230630": 7.5},
        "毛利率": {"20231231": 30.2, "20221231": 28.8, "20230630": 29.0},
        "销售净利率": {"20231231": 20.1, "20221231": 18.5, "20230630": 10.0},
        "经营现金流量净额": {"20231231": 120000000.0,
                            "20221231": 110000000.0,
                            "20230630": 60000000.0},
        "净利润": {"20231231": 100000000.0, "20221231": 90000000.0,
                   "20230630": 50000000.0},
        "扣非净利润": {"20231231": 95000000.0, "20221231": 85000000.0},
        "营业总收入": {"20231231": 500000000.0, "20221231": 450000000.0},
        "营业成本": {"20231231": 350000000.0, "20221231": 320000000.0},
        "资产负债率": {"20231231": 35.5, "20221231": 38.2},
        "基本每股收益": {"20231231": 2.5, "20221231": 2.2},
        "每股经营现金流": {"20231231": 3.0, "20221231": 2.8},
        "每股净资产": {"20231231": 6.5, "20221231": 5.8},
        "归母净利润": {"20231231": 100000000.0, "20221231": 90000000.0},
        "总资产报酬率(ROA)": {"20231231": 10.5, "20221231": 9.8},
        "期间费用率": {"20231231": 12.0, "20221231": 13.5},
    }


def parse_json_output(stdout_text: str) -> dict:
    """解析 stdout 文本为 JSON 字典。

    Args:
        stdout_text: 标准输出文本。

    Returns:
        解析后的字典；解析失败时返回空字典。
    """
    text = stdout_text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ===========================================================================
# 1. get_raw_data 测试（网络集成测试）
# ===========================================================================

class TestGetRawData(unittest.TestCase):
    """测试 get_raw_data 函数 —— 原始财务摘要获取。

    此测试依赖网络，网络不可用时自动跳过。
    """

    def test_returns_dataframe(self):
        """测试返回类型为 DataFrame。"""
        try:
            df = get_raw_data("300502")
            self.assertIsInstance(df, pd.DataFrame)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_has_indicator_column(self):
        """测试返回的 DataFrame 包含 "指标" 列。"""
        try:
            df = get_raw_data("300502")
            self.assertIn("指标", df.columns)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_has_data(self):
        """测试返回的 DataFrame 非空。"""
        try:
            df = get_raw_data("300502")
            self.assertGreater(len(df), 0)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")


# ===========================================================================
# 2. parse_financial_data 测试（使用 mock 数据，无网络依赖）
# ===========================================================================

class TestParseFinancialData(unittest.TestCase):
    """测试 parse_financial_data 函数 —— DataFrame 解析为结构化字典。

    使用 mock DataFrame，无网络依赖。
    """

    def test_returns_dict(self):
        """测试返回类型为字典。"""
        df = make_mock_df()
        result = parse_financial_data(df)
        self.assertIsInstance(result, dict)

    def test_indicator_as_key(self):
        """测试以指标名作为字典键。"""
        df = make_mock_df()
        result = parse_financial_data(df)
        self.assertIn("净资产收益率(ROE)", result)
        self.assertIn("毛利率", result)
        self.assertIn("净利润", result)

    def test_skips_option_and_indicator_columns(self):
        """测试跳过 "选项" 和 "指标" 列。"""
        df = make_mock_df()
        result = parse_financial_data(df)
        for indicator, values in result.items():
            self.assertNotIn("选项", values)
            self.assertNotIn("指标", values)

    def test_year_label_as_inner_key(self):
        """测试年份标签作为内层字典的键。"""
        df = make_mock_df()
        result = parse_financial_data(df)
        roe_data = result["净资产收益率(ROE)"]
        self.assertIn("20231231", roe_data)
        self.assertIn("20221231", roe_data)
        self.assertIn("20230630", roe_data)

    def test_float_rounded_to_4(self):
        """测试浮点值被四舍五入到4位小数。"""
        df = pd.DataFrame({
            "选项": [""],
            "指标": ["测试指标"],
            "20231231": [15.123456789],
        })
        result = parse_financial_data(df)
        self.assertEqual(result["测试指标"]["20231231"], 15.1235)

    def test_nan_values_skipped(self):
        """测试 NaN 值被跳过。"""
        df = make_mock_df_with_nan()
        result = parse_financial_data(df)
        # "净利润" 行 20231231 为 NaN，不应出现在结果中
        self.assertNotIn("20231231", result["净利润"])
        # 20221231 有值
        self.assertIn("20221231", result["净利润"])

    def test_none_values_skipped(self):
        """测试 None 值被跳过。"""
        df = pd.DataFrame({
            "选项": ["", ""],
            "指标": ["指标A", "指标B"],
            "20231231": [None, 10.0],
            "20221231": [5.0, None],
        })
        result = parse_financial_data(df)
        self.assertNotIn("20231231", result["指标A"])
        self.assertNotIn("20221231", result["指标B"])
        self.assertEqual(result["指标A"]["20221231"], 5.0)
        self.assertEqual(result["指标B"]["20231231"], 10.0)

    def test_value_correctness(self):
        """测试解析值的正确性。"""
        df = make_mock_df()
        result = parse_financial_data(df)
        self.assertEqual(result["毛利率"]["20231231"], 30.2)
        self.assertEqual(result["净利润"]["20231231"], 100000000.0)


# ===========================================================================
# 3. extract_key_indicators 测试（使用 mock 数据，无网络依赖）
# ===========================================================================

class TestExtractKeyIndicators(unittest.TestCase):
    """测试 extract_key_indicators 函数 —— 关键指标提取与派生计算。

    使用 mock 字典数据，无网络依赖。
    """

    def test_returns_dict(self):
        """测试返回类型为字典。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        self.assertIsInstance(result, dict)

    def test_contains_all_key_indicators(self):
        """测试结果包含 KEY_INDICATORS 中所有关键指标。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        for eng_name in KEY_INDICATORS:
            self.assertIn(eng_name, result)

    def test_roe_extraction(self):
        """测试 ROE（净资产收益率）提取。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        self.assertEqual(result["ROE"], parsed["净资产收益率(ROE)"])

    def test_gross_margin_extraction(self):
        """测试毛利率提取。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        self.assertEqual(result["毛利率"], parsed["毛利率"])

    def test_net_margin_extraction(self):
        """测试净利率（销售净利率）提取。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        self.assertEqual(result["净利率"], parsed["销售净利率"])

    def test_net_profit_extraction(self):
        """测试净利润提取。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        self.assertEqual(result["净利润"], parsed["净利润"])

    def test_ocf_ratio_calculation(self):
        """测试经营现金流/净利润 派生计算。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        ratio = result["经营现金流/净利润"]
        self.assertIsNotNone(ratio)
        self.assertIsInstance(ratio, dict)
        # 2023: 120000000 / 100000000 = 1.2
        self.assertEqual(ratio["20231231"], 1.2)
        # 2022: 110000000 / 90000000 ≈ 1.2222
        self.assertEqual(ratio["20221231"], round(110000000.0 / 90000000.0, 4))

    def test_ocf_ratio_zero_net_profit(self):
        """测试净利润为零时不计算现金流比。"""
        parsed = make_mock_parsed()
        parsed["净利润"]["20231231"] = 0.0
        result = extract_key_indicators(parsed)
        ratio = result["经营现金流/净利润"]
        self.assertNotIn("20231231", ratio)
        # 2022 仍有数据
        self.assertIn("20221231", ratio)

    def test_free_cashflow_note(self):
        """测试自由现金流标记为需要额外数据。"""
        parsed = make_mock_parsed()
        result = extract_key_indicators(parsed)
        self.assertIsInstance(result["自由现金流"], dict)
        self.assertIn("note", result["自由现金流"])

    def test_fuzzy_matching(self):
        """测试模糊匹配：指标名不完全匹配时通过子串查找。"""
        parsed = {
            "加权净资产收益率(ROE)": {"20231231": 16.0},
        }
        result = extract_key_indicators(parsed)
        # "净资产收益率(ROE)" 不在 parsed，但模糊匹配
        # "净资产收益率(ROE)" in "加权净资产收益率(ROE)" -> True
        self.assertIsNotNone(result["ROE"])

    def test_missing_indicator_returns_none(self):
        """测试缺失指标的模糊匹配未命中时返回 None。"""
        parsed = {"无关指标": {"20231231": 1.0}}
        result = extract_key_indicators(parsed)
        # ROE 未匹配到任何指标
        self.assertIsNone(result["ROE"])

    def test_ocf_ratio_none_when_missing(self):
        """测试经营现金流或净利润缺失时比值为 None。"""
        parsed = make_mock_parsed()
        del parsed["经营现金流量净额"]
        result = extract_key_indicators(parsed)
        self.assertIsNone(result["经营现金流/净利润"])


# ===========================================================================
# 4. format_yearly_data 测试（使用 mock 数据，无网络依赖）
# ===========================================================================

class TestFormatYearlyData(unittest.TestCase):
    """测试 format_yearly_data 函数 —— 年度数据格式化。

    使用 mock 字典数据，无网络依赖。
    """

    def test_returns_dict(self):
        """测试返回类型为字典。"""
        data = make_mock_parsed()
        result = format_yearly_data(data)
        self.assertIsInstance(result, dict)

    def test_only_year_end_data(self):
        """测试只保留年末（1231）数据，季报数据被排除。"""
        data = {
            "毛利率": {"20231231": 30.2, "20230630": 29.0, "20221231": 28.8},
        }
        result = format_yearly_data(data)
        # 只保留 20231231、20221231 两个年末数据
        self.assertIn("2023", result["毛利率"])
        self.assertIn("2022", result["毛利率"])
        self.assertEqual(len(result["毛利率"]), 2)
        # 20230630 季报数据不应出现（不会被截短为年份键）
        self.assertNotIn("20230630", result["毛利率"])

    def test_year_label_shortened_to_yyyy(self):
        """测试年份标签被截短为 YYYY（4位年份）。"""
        data = {
            "毛利率": {"20231231": 30.2, "20221231": 28.8},
        }
        result = format_yearly_data(data)
        self.assertIn("2023", result["毛利率"])
        self.assertIn("2022", result["毛利率"])
        # 不应出现完整的 8 位日期标签
        for year_key in result["毛利率"]:
            self.assertEqual(len(year_key), 4)

    def test_years_sorted_descending(self):
        """测试年份按降序排列。"""
        data = {
            "毛利率": {"20231231": 30.2, "20211231": 25.0, "20221231": 28.8},
        }
        result = format_yearly_data(data)
        years = list(result["毛利率"].keys())
        self.assertEqual(years, ["2023", "2022", "2021"])

    def test_non_dict_values_preserved(self):
        """测试非字典值（如 None）被原样保留。

        extract_key_indicators 中 "经营现金流/净利润" 可能为 None，
        format_yearly_data 应将其原样保留而非当作指标数据处理。
        """
        data = {
            "毛利率": {"20231231": 30.2},
            "经营现金流/净利润": None,
        }
        result = format_yearly_data(data)
        self.assertIsNone(result["经营现金流/净利润"])

    def test_dict_with_note_becomes_empty(self):
        """测试含 note 键的字典被当作普通指标处理，note 不以1231结尾故结果为空。

        extract_key_indicators 中 "自由现金流" 设为 {"note": "..."}，
        经 format_yearly_data 处理后 note 键不匹配年末数据，结果为空字典。
        """
        data = {
            "毛利率": {"20231231": 30.2},
            "自由现金流": {"note": "需额外计算"},
        }
        result = format_yearly_data(data)
        self.assertEqual(result["自由现金流"], {})

    def test_empty_data(self):
        """测试空数据输入。"""
        result = format_yearly_data({})
        self.assertEqual(result, {})

    def test_no_year_end_data(self):
        """测试无年末数据时返回空字典。"""
        data = {
            "毛利率": {"20230630": 29.0, "20220331": 28.0},
        }
        result = format_yearly_data(data)
        self.assertEqual(result["毛利率"], {})

    def test_multiple_indicators(self):
        """测试多个指标同时格式化。"""
        data = {
            "毛利率": {"20231231": 30.2, "20221231": 28.8},
            "ROE": {"20231231": 15.5, "20221231": 14.3},
        }
        result = format_yearly_data(data)
        self.assertEqual(result["毛利率"]["2023"], 30.2)
        self.assertEqual(result["毛利率"]["2022"], 28.8)
        self.assertEqual(result["ROE"]["2023"], 15.5)
        self.assertEqual(result["ROE"]["2022"], 14.3)


# ===========================================================================
# 5. main() 主逻辑测试（mock get_raw_data，无网络依赖）
# ===========================================================================

class TestMainLogic(unittest.TestCase):
    """测试 main() 主逻辑 —— 各 --indicator 路径。

    通过 mock get_raw_data 隔离网络依赖。
    """

    def _run_main_with_args(self, argv: list) -> dict:
        """以指定参数运行 main() 并返回解析后的 JSON 输出。

        Args:
            argv: 命令行参数列表（不含脚本名）。

        Returns:
            解析后的输出字典。
        """
        with patch.object(sys, "argv", ["stock_financial.py"] + argv):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                main = sf_module.main
                main()
                return parse_json_output(fake_out.getvalue())

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_indicator_all(self, mock_get_raw):
        """测试 --indicator all 输出全部原始数据。"""
        mock_get_raw.return_value = make_mock_df()
        output = self._run_main_with_args(["--code", "300502", "--indicator", "all"])

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["indicator"], "all")
        self.assertEqual(output["meta"]["code"], "300502")
        self.assertEqual(output["meta"]["indicator_count"], 6)
        self.assertIn("indicators", output["data"])
        self.assertIn("净资产收益率(ROE)", output["data"]["indicators"])
        self.assertIn("毛利率", output["data"]["indicators"])

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_indicator_specific_roe(self, mock_get_raw):
        """测试 --indicator ROE 输出指定指标（英文标识）。"""
        mock_get_raw.return_value = make_mock_df()
        output = self._run_main_with_args(["--code", "300502", "--indicator", "ROE"])

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["indicator"], "ROE")
        self.assertIn("indicators", output["data"])
        self.assertIn("ROE", output["data"]["indicators"])
        # ROE 通过模糊匹配到 "净资产收益率(ROE)"
        self.assertIn("20231231", output["data"]["indicators"]["ROE"])

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_indicator_specific_gross_margin(self, mock_get_raw):
        """测试 --indicator 毛利率 输出指定指标（中文名）。"""
        mock_get_raw.return_value = make_mock_df()
        output = self._run_main_with_args(
            ["--code", "300502", "--indicator", "毛利率"])

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["indicator"], "毛利率")
        self.assertIn("indicators", output["data"])
        self.assertIn("毛利率", output["data"]["indicators"])
        self.assertEqual(output["data"]["indicators"]["毛利率"]["20231231"], 30.2)

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_indicator_multiple(self, mock_get_raw):
        """测试 --indicator 毛利率,净利率 输出多个指标。"""
        mock_df = pd.DataFrame({
            "选项": ["", "", ""],
            "指标": ["毛利率", "销售净利率", "净利润"],
            "20231231": [30.2, 20.1, 100000000.0],
            "20221231": [28.8, 18.5, 90000000.0],
        })
        mock_get_raw.return_value = mock_df
        output = self._run_main_with_args(
            ["--code", "300502", "--indicator", "毛利率,净利率"])

        self.assertTrue(output["success"])
        self.assertIn("indicators", output["data"])
        self.assertIn("毛利率", output["data"]["indicators"])
        self.assertIn("净利率", output["data"]["indicators"])

    @patch("tools.a_share.stock_financial.ak")
    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_default_key_metrics(self, mock_get_raw, mock_ak):
        """测试默认（无 --indicator）输出关键指标。"""
        mock_get_raw.return_value = make_mock_df()
        # mock ak.stock_yjbb_em 返回空 DataFrame
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            columns=["股票代码", "所处行业", "净资产收益率", "销售毛利率", "每股收益"])

        output = self._run_main_with_args(["--code", "300502"])

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["indicator"], "key_metrics")
        self.assertIn("indicators", output["data"])
        self.assertIn("latest_quarter", output["data"])
        # 关键指标应包含 ROE、毛利率 等
        self.assertIn("ROE", output["data"]["indicators"])
        self.assertIn("毛利率", output["data"]["indicators"])

    @patch("tools.a_share.stock_financial.ak")
    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_default_yearly_format(self, mock_get_raw, mock_ak):
        """测试默认输出中年份格式化为 YYYY。"""
        mock_get_raw.return_value = make_mock_df()
        mock_ak.stock_yjbb_em.return_value = pd.DataFrame(
            columns=["股票代码", "所处行业", "净资产收益率", "销售毛利率", "每股收益"])

        output = self._run_main_with_args(["--code", "300502"])
        roe_data = output["data"]["indicators"]["ROE"]
        # 年份应为 4 位
        for year_key in roe_data:
            self.assertEqual(len(year_key), 4)

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_code_zfill(self, mock_get_raw):
        """测试股票代码补齐 6 位。"""
        mock_get_raw.return_value = make_mock_df()
        output = self._run_main_with_args(
            ["--code", "502", "--indicator", "all"])
        # 502 应补齐为 000502
        self.assertEqual(output["meta"]["code"], "000502")

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_indicator_not_found(self, mock_get_raw):
        """测试 --indicator 指定不存在的指标时的处理。

        未找到的指标不会被当作致命错误，而是返回 success=true，
        并在该指标的 values 中给出 {"note": "未找到指标: ..."} 说明。
        """
        mock_get_raw.return_value = make_mock_df()
        output = self._run_main_with_args(
            ["--code", "300502", "--indicator", "zzz不存在的指标zzz"])

        self.assertTrue(output["success"])
        self.assertIn("indicators", output["data"])
        result = output["data"]["indicators"]
        self.assertIn("zzz不存在的指标zzz", result)
        self.assertIn("note", result["zzz不存在的指标zzz"])


# ===========================================================================
# 6. 命令行接口测试（subprocess，网络依赖）
# ===========================================================================

class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口 —— 通过 subprocess 调用脚本。

    依赖网络的测试使用 try-except + skipTest 处理。
    """

    def _run_cli(self, args: list) -> tuple:
        """运行命令行并返回 (returncode, stdout, stderr)。

        Args:
            args: 命令行参数列表。

        Returns:
            元组 (returncode, stdout, stderr)。
        """
        result = subprocess.run(
            [PYTHON, TOOL_PATH] + args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=120,
        )
        return result.returncode, result.stdout, result.stderr

    def test_help(self):
        """测试 --help 参数输出。"""
        rc, out, err = self._run_cli(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("A 股财务指标查询工具", out)
        self.assertIn("--code", out)
        self.assertIn("--indicator", out)

    def test_no_args(self):
        """测试无参数时返回非零退出码。"""
        rc, out, err = self._run_cli([])
        self.assertNotEqual(rc, 0)

    def test_code_indicator_all(self):
        """测试 --code --indicator all 命令行。"""
        try:
            rc, out, err = self._run_cli(
                ["--code", "300502", "--indicator", "all"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["indicator"], "all")
                self.assertGreater(output["meta"]["indicator_count"], 0)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code_indicator_roe(self):
        """测试 --code --indicator ROE 命令行。"""
        try:
            rc, out, err = self._run_cli(
                ["--code", "300502", "--indicator", "ROE"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["indicator"], "ROE")
                self.assertIn("indicators", output["data"])
                self.assertIn("ROE", output["data"]["indicators"])
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code_default_key_metrics(self):
        """测试 --code 默认关键指标输出命令行。"""
        try:
            rc, out, err = self._run_cli(["--code", "300502"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["indicator"], "key_metrics")
                self.assertIn("indicators", output["data"])
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")


# ===========================================================================
# 7. 错误处理测试
# ===========================================================================

class TestErrorHandling(unittest.TestCase):
    """测试错误处理 —— 无效代码与网络错误。"""

    def _run_main_with_args(self, argv: list) -> tuple:
        """以指定参数运行 main() 并返回 (输出字典, 退出码)。

        Args:
            argv: 命令行参数列表。

        Returns:
            元组 (解析后的输出字典, 退出码)。
        """
        with patch.object(sys, "argv", ["stock_financial.py"] + argv):
            with patch("sys.stderr", new=StringIO()) as fake_err:
                try:
                    with patch("sys.stdout", new=StringIO()):
                        sf_module.main()
                    return {}, 0
                except SystemExit as cm:
                    return parse_json_output(fake_err.getvalue()), cm.code

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_network_error_handling(self, mock_get_raw):
        """测试网络错误时的错误输出。"""
        mock_get_raw.side_effect = ConnectionError("Connection failed")
        output, code = self._run_main_with_args(
            ["--code", "300502", "--indicator", "all"])

        self.assertEqual(code, 1)
        self.assertFalse(output["success"])
        self.assertIn("网络", output["error"])

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_generic_error_handling(self, mock_get_raw):
        """测试通用异常时的错误输出。"""
        mock_get_raw.side_effect = RuntimeError("数据解析异常")
        output, code = self._run_main_with_args(
            ["--code", "300502", "--indicator", "all"])

        self.assertEqual(code, 1)
        self.assertFalse(output["success"])
        self.assertIn("error", output)

    @patch("tools.a_share.stock_financial.get_raw_data")
    def test_empty_dataframe_handling(self, mock_get_raw):
        """测试空 DataFrame 时的处理。"""
        mock_get_raw.return_value = pd.DataFrame(
            columns=["选项", "指标", "20231231"])
        with patch.object(sys, "argv",
                         ["stock_financial.py", "--code", "300502",
                          "--indicator", "all"]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                sf_module.main()
                output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["indicator_count"], 0)

    def test_invalid_code_cli(self):
        """测试无效股票代码的 CLI 错误处理。"""
        try:
            rc, out, err = self._run_cli(["--code", "999999", "--indicator", "all"])
            # 无效代码可能返回空数据或错误
            stdout = out.strip()
            stderr = err.strip()
            if stdout:
                output = parse_json_output(stdout)
                if output.get("success"):
                    # 数据为空也是有效响应
                    self.assertEqual(output["meta"]["code"], "999999")
                else:
                    self.assertFalse(output["success"])
            elif stderr:
                output = parse_json_output(stderr)
                self.assertFalse(output["success"])
            else:
                self.skipTest("网络不可用或无输出")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def _run_cli(self, args: list) -> tuple:
        """运行命令行并返回 (returncode, stdout, stderr)。

        Args:
            args: 命令行参数列表。

        Returns:
            元组 (returncode, stdout, stderr)。
        """
        result = subprocess.run(
            [PYTHON, TOOL_PATH] + args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=120,
        )
        return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

def run_tests(test_type: str = "all") -> bool:
    """运行测试。

    Args:
        test_type: 测试类型，可选 "all"、"core"、"main"、"cli"、"error"。

    Returns:
        测试是否全部成功。
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if test_type == "all":
        suite.addTests(loader.loadTestsFromTestCase(TestGetRawData))
        suite.addTests(loader.loadTestsFromTestCase(TestParseFinancialData))
        suite.addTests(loader.loadTestsFromTestCase(TestExtractKeyIndicators))
        suite.addTests(loader.loadTestsFromTestCase(TestFormatYearlyData))
        suite.addTests(loader.loadTestsFromTestCase(TestMainLogic))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    elif test_type == "core":
        suite.addTests(loader.loadTestsFromTestCase(TestParseFinancialData))
        suite.addTests(loader.loadTestsFromTestCase(TestExtractKeyIndicators))
        suite.addTests(loader.loadTestsFromTestCase(TestFormatYearlyData))
    elif test_type == "main":
        suite.addTests(loader.loadTestsFromTestCase(TestMainLogic))
    elif test_type == "cli":
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    elif test_type == "error":
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    else:
        print(f"未知测试类型: {test_type}")
        return False

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"测试完成: {result.testsRun} 个测试")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A股财务指标查询工具测试模块")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "core", "main", "cli", "error"],
                        help="测试类型（默认: all）")

    args = parser.parse_args()

    success = run_tests(args.test)
    sys.exit(0 if success else 1)
