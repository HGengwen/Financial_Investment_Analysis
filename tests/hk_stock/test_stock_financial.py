#!/usr/bin/env python3
"""港股财务指标查询工具测试模块。

测试 tools/hk_stock/stock_financial.py 的各功能模块，使用 unittest 框架。

测试范围:
  1. TestFinancialFieldMap       — 字段映射与关键指标常量定义
  2. TestGetHkFinancialIndicators — 财务指标获取核心函数（mock 数据）
  3. TestMainLogic                — main() 主逻辑（mock get_hk_financial_indicators）
  4. TestCommandLineInterface     — 命令行接口（subprocess，网络依赖）
  5. TestErrorHandling            — 错误处理（无效代码/网络错误）

运行方式:
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/hk_stock/test_stock_financial.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/hk_stock/test_stock_financial.py

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

# 添加项目根目录到路径（测试位于 tests/hk_stock/，需上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
from tools.hk_stock.stock_financial import (
    get_hk_financial_indicators,
    safe_api_call,
    cmd_financial,
    _FINANCIAL_FIELD_MAP,
    _KEY_INDICATORS,
)
from tools.hk_stock import stock_financial as sf_module

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "hk_stock", "stock_financial.py")
PYTHON = sys.executable


# ---------------------------------------------------------------------------
# 辅助函数：构建 mock 数据
# ---------------------------------------------------------------------------

def make_mock_financial_df() -> pd.DataFrame:
    """构建模拟的港股财务分析指标 DataFrame。

    模拟 ak.stock_financial_hk_analysis_indicator_em 返回的结构，
    包含 _KEY_INDICATORS 中所有关键字段及若干辅助字段。

    Returns:
        模拟的港股财务分析指标 DataFrame，含两期（2023、2022）数据。
    """
    return pd.DataFrame([
        {
            "SECUCODE": "00700.HK",
            "SECURITY_CODE": "00700",
            "SECURITY_NAME_ABBR": "腾讯控股",
            "ORG_CODE": "org001",
            "REPORT_DATE": "2023-12-31",
            "DATE_TYPE_CODE": "001",
            "PER_NETCASH_OPERATE": 12.34,
            "PER_OI": 25.67,
            "BPS": 28.50,
            "BASIC_EPS": 15.80,
            "DILUTED_EPS": 15.70,
            "OPERATE_INCOME": 609015000000.0,  # 约 6090.15 亿
            "OPERATE_INCOME_YOY": 9.82,
            "GROSS_PROFIT": 320000000000.0,
            "GROSS_PROFIT_YOY": 8.50,
            "HOLDER_PROFIT": 115200000000.0,  # 约 1152 亿
            "HOLDER_PROFIT_YOY": -36.69,
            "GROSS_PROFIT_RATIO": 52.55,
            "EPS_TTM": 16.10,
            "OPERATE_INCOME_QOQ": 5.20,
            "NET_PROFIT_RATIO": 18.91,
            "ROE_AVG": 28.15,
            "GROSS_PROFIT_QOQ": 3.10,
            "ROA": 15.20,
            "HOLDER_PROFIT_QOQ": -10.5,
            "ROE_YEARLY": 30.50,
            "ROIC_YEARLY": 20.10,
            "TAX_EBT": 8.90,
            "OCF_SALES": 32.40,
            "DEBT_ASSET_RATIO": 45.60,
            "CURRENT_RATIO": 1.25,
            "CURRENTDEBT_DEBT": 30.00,
            "START_DATE": "2023-01-01",
            "FISCAL_YEAR": "2023-12-31",
            "CURRENCY": "CNY",
            "IS_CNY_CODE": "1",
        },
        {
            "SECUCODE": "00700.HK",
            "SECURITY_CODE": "00700",
            "SECURITY_NAME_ABBR": "腾讯控股",
            "ORG_CODE": "org001",
            "REPORT_DATE": "2022-12-31",
            "DATE_TYPE_CODE": "001",
            "PER_NETCASH_OPERATE": 10.50,
            "PER_OI": 22.30,
            "BPS": 24.80,
            "BASIC_EPS": 13.50,
            "DILUTED_EPS": 13.40,
            "OPERATE_INCOME": 554552000000.0,  # 约 5545.52 亿
            "OPERATE_INCOME_YOY": -1.00,
            "GROSS_PROFIT": 295000000000.0,
            "GROSS_PROFIT_YOY": 5.00,
            "HOLDER_PROFIT": 188200000000.0,  # 约 1882 亿
            "HOLDER_PROFIT_YOY": -16.00,
            "GROSS_PROFIT_RATIO": 53.20,
            "EPS_TTM": 14.50,
            "OPERATE_INCOME_QOQ": 2.10,
            "NET_PROFIT_RATIO": 33.94,
            "ROE_AVG": 27.50,
            "GROSS_PROFIT_QOQ": 1.50,
            "ROA": 14.80,
            "HOLDER_PROFIT_QOQ": -8.0,
            "ROE_YEARLY": 29.10,
            "ROIC_YEARLY": 18.50,
            "TAX_EBT": 7.50,
            "OCF_SALES": 28.50,
            "DEBT_ASSET_RATIO": 47.20,
            "CURRENT_RATIO": 1.30,
            "CURRENTDEBT_DEBT": 28.50,
            "START_DATE": "2022-01-01",
            "FISCAL_YEAR": "2022-12-31",
            "CURRENCY": "CNY",
            "IS_CNY_CODE": "1",
        },
    ])


def make_mock_financial_df_with_nan() -> pd.DataFrame:
    """构建包含 NaN 值的模拟财务指标 DataFrame。

    Returns:
        包含 NaN 值的模拟 DataFrame，用于测试空值处理逻辑。
    """
    return pd.DataFrame([{
        "SECUCODE": "00700.HK",
        "SECURITY_CODE": "00700",
        "SECURITY_NAME_ABBR": "腾讯控股",
        "ORG_CODE": "org001",
        "REPORT_DATE": "2023-12-31",
        "DATE_TYPE_CODE": "001",
        "PER_NETCASH_OPERATE": float("nan"),
        "PER_OI": float("nan"),
        "BPS": 28.50,
        "BASIC_EPS": 15.80,
        "DILUTED_EPS": 15.70,
        "OPERATE_INCOME": float("nan"),
        "OPERATE_INCOME_YOY": float("nan"),
        "GROSS_PROFIT": 320000000000.0,
        "GROSS_PROFIT_YOY": 8.50,
        "HOLDER_PROFIT": float("nan"),
        "HOLDER_PROFIT_YOY": float("nan"),
        "GROSS_PROFIT_RATIO": float("nan"),
        "EPS_TTM": 16.10,
        "OPERATE_INCOME_QOQ": 5.20,
        "NET_PROFIT_RATIO": float("nan"),
        "ROE_AVG": float("nan"),
        "GROSS_PROFIT_QOQ": 3.10,
        "ROA": 15.20,
        "HOLDER_PROFIT_QOQ": -10.5,
        "ROE_YEARLY": 30.50,
        "ROIC_YEARLY": 20.10,
        "TAX_EBT": 8.90,
        "OCF_SALES": float("nan"),
        "DEBT_ASSET_RATIO": float("nan"),
        "CURRENT_RATIO": float("nan"),
        "CURRENTDEBT_DEBT": 30.00,
        "START_DATE": "2023-01-01",
        "FISCAL_YEAR": "2023-12-31",
        "CURRENCY": "CNY",
        "IS_CNY_CODE": "1",
    }])


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
# 1. 字段映射与关键指标常量测试
# ===========================================================================

class TestFinancialFieldMap(unittest.TestCase):
    """测试 _FINANCIAL_FIELD_MAP 与 _KEY_INDICATORS 常量定义。

    无网络依赖。
    """

    def test_field_map_is_dict(self):
        """测试字段映射是字典类型。"""
        self.assertIsInstance(_FINANCIAL_FIELD_MAP, dict)

    def test_field_map_contains_key_fields(self):
        """测试字段映射包含7条去劣指标相关的关键字段。"""
        required_fields = [
            "ROE_AVG", "ROE_YEARLY",
            "GROSS_PROFIT_RATIO", "NET_PROFIT_RATIO",
            "OCF_SALES", "DEBT_ASSET_RATIO", "CURRENT_RATIO",
            "HOLDER_PROFIT", "OPERATE_INCOME",
            "BASIC_EPS", "DILUTED_EPS", "BPS",
            "PER_NETCASH_OPERATE", "REPORT_DATE", "SECURITY_NAME_ABBR",
        ]
        for field in required_fields:
            self.assertIn(field, _FINANCIAL_FIELD_MAP,
                          f"字段映射缺少关键字段: {field}")

    def test_field_map_values_are_chinese(self):
        """测试字段映射的值为中文说明。"""
        self.assertEqual(_FINANCIAL_FIELD_MAP["ROE_AVG"], "平均净资产收益率(%)")
        self.assertEqual(_FINANCIAL_FIELD_MAP["GROSS_PROFIT_RATIO"], "毛利率(%)")
        self.assertEqual(_FINANCIAL_FIELD_MAP["NET_PROFIT_RATIO"], "净利率(%)")
        self.assertEqual(_FINANCIAL_FIELD_MAP["DEBT_ASSET_RATIO"], "资产负债率(%)")

    def test_key_indicators_is_list(self):
        """测试关键指标列表是列表类型。"""
        self.assertIsInstance(_KEY_INDICATORS, list)

    def test_key_indicators_contains_all_required(self):
        """测试关键指标列表包含7条去劣指标所需全部字段。"""
        # 7条去劣指标所需的核心字段
        required_indicators = [
            "ROE_AVG", "GROSS_PROFIT_RATIO", "NET_PROFIT_RATIO",
            "OCF_SALES", "DEBT_ASSET_RATIO", "CURRENT_RATIO",
            "HOLDER_PROFIT", "OPERATE_INCOME",
        ]
        for ind in required_indicators:
            self.assertIn(ind, _KEY_INDICATORS,
                          f"关键指标列表缺少: {ind}")

    def test_key_indicators_all_in_field_map(self):
        """测试关键指标列表中所有字段都在字段映射中有中文说明。"""
        for field in _KEY_INDICATORS:
            self.assertIn(field, _FINANCIAL_FIELD_MAP,
                          f"关键指标 {field} 未在字段映射中定义")


# ===========================================================================
# 2. get_hk_financial_indicators 测试（使用 mock 数据，无网络依赖）
# ===========================================================================

class TestGetHkFinancialIndicators(unittest.TestCase):
    """测试 get_hk_financial_indicators 函数 —— 财务指标获取核心逻辑。

    通过 mock safe_api_call 隔离网络依赖。
    """

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_returns_dict(self, mock_safe_call):
        """测试返回类型为字典。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        self.assertIsInstance(result, dict)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_result_structure(self, mock_safe_call):
        """测试返回字典包含必要结构字段。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        for key in ("code", "indicator", "count", "data", "fields"):
            self.assertIn(key, result, f"返回结果缺少字段: {key}")

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_default_indicator_is_yearly(self, mock_safe_call):
        """测试默认指标类型为"年度"。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        self.assertEqual(result["indicator"], "年度")

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_indicator_report_period(self, mock_safe_call):
        """测试指定 indicator="报告期" 时正确传递。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700", indicator="报告期")
        self.assertEqual(result["indicator"], "报告期")

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_code_zfill_to_5_digits(self, mock_safe_call):
        """测试代码补齐 5 位（"700" -> "00700"）。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("700")
        self.assertEqual(result["code"], "00700")

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_code_already_5_digits(self, mock_safe_call):
        """测试已经是 5 位的代码保持不变。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        self.assertEqual(result["code"], "00700")

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_count_matches_data_length(self, mock_safe_call):
        """测试 count 字段等于 data 列表长度。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        self.assertEqual(result["count"], len(result["data"]))
        self.assertEqual(result["count"], 2)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_records_sorted_by_report_date_desc(self, mock_safe_call):
        """测试记录按 REPORT_DATE 降序排列（最新在前）。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        dates = [r["REPORT_DATE"] for r in result["data"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        # 第一条应为最新
        self.assertEqual(result["data"][0]["REPORT_DATE"], "2023-12-31")
        self.assertEqual(result["data"][1]["REPORT_DATE"], "2022-12-31")

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_record_contains_key_indicator_fields(self, mock_safe_call):
        """测试每条记录包含所有关键指标字段。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        for field in _KEY_INDICATORS:
            self.assertIn(field, first_record,
                          f"记录缺少关键指标字段: {field}")

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_record_has_fields_chinese_map(self, mock_safe_call):
        """测试每条记录包含 _fields 中文字段映射。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertIn("_fields", first_record)
        self.assertIsInstance(first_record["_fields"], dict)
        # _fields 应覆盖所有关键指标
        for field in _KEY_INDICATORS:
            self.assertIn(field, first_record["_fields"])

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_roe_avg_value_correct(self, mock_safe_call):
        """测试 ROE_AVG（平均净资产收益率）值正确并保留 2 位小数。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertEqual(first_record["ROE_AVG"], 28.15)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_gross_profit_ratio_value_correct(self, mock_safe_call):
        """测试 GROSS_PROFIT_RATIO（毛利率）值正确。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertEqual(first_record["GROSS_PROFIT_RATIO"], 52.55)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_net_profit_ratio_value_correct(self, mock_safe_call):
        """测试 NET_PROFIT_RATIO（净利率）值正确。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertEqual(first_record["NET_PROFIT_RATIO"], 18.91)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_debt_asset_ratio_value_correct(self, mock_safe_call):
        """测试 DEBT_ASSET_RATIO（资产负债率）值正确。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertEqual(first_record["DEBT_ASSET_RATIO"], 45.60)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_current_ratio_value_correct(self, mock_safe_call):
        """测试 CURRENT_RATIO（流动比率）值正确。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertEqual(first_record["CURRENT_RATIO"], 1.25)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_holder_profit_to_yi(self, mock_safe_call):
        """测试 HOLDER_PROFIT（归母净利润）转换为亿元（/1e8）。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        # 原始值 115200000000.0 → 1152.0 亿
        self.assertEqual(first_record["HOLDER_PROFIT"], 1152.0)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_operate_income_to_yi(self, mock_safe_call):
        """测试 OPERATE_INCOME（营业总收入）转换为亿元（/1e8）。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        # 原始值 609015000000.0 → 6090.15 亿
        self.assertEqual(first_record["OPERATE_INCOME"], 6090.15)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_string_field_type(self, mock_safe_call):
        """测试字符串类型字段（如 SECURITY_NAME_ABBR）转为 str。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertIsInstance(first_record["SECURITY_NAME_ABBR"], str)
        self.assertEqual(first_record["SECURITY_NAME_ABBR"], "腾讯控股")
        self.assertIsInstance(first_record["REPORT_DATE"], str)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_percentage_rounded_to_2(self, mock_safe_call):
        """测试百分比/比率字段保留 2 位小数。"""
        # 构造带多位小数的原始数据
        df = make_mock_financial_df().copy()
        df.loc[0, "ROE_AVG"] = 28.15456789
        df.loc[0, "GROSS_PROFIT_RATIO"] = 52.559999
        mock_safe_call.return_value = df

        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        self.assertEqual(first_record["ROE_AVG"], 28.15)
        self.assertEqual(first_record["GROSS_PROFIT_RATIO"], 52.56)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_nan_values_become_none(self, mock_safe_call):
        """测试 NaN 值被转换为 None。"""
        mock_safe_call.return_value = make_mock_financial_df_with_nan()
        result = get_hk_financial_indicators("00700")
        first_record = result["data"][0]
        # NaN 字段应为 None
        self.assertIsNone(first_record["ROE_AVG"])
        self.assertIsNone(first_record["GROSS_PROFIT_RATIO"])
        self.assertIsNone(first_record["NET_PROFIT_RATIO"])
        self.assertIsNone(first_record["OCF_SALES"])
        self.assertIsNone(first_record["DEBT_ASSET_RATIO"])
        self.assertIsNone(first_record["CURRENT_RATIO"])
        # 大额数值 NaN 也应为 None
        self.assertIsNone(first_record["HOLDER_PROFIT"])
        self.assertIsNone(first_record["OPERATE_INCOME"])
        # 非空字段保留
        self.assertIsNotNone(first_record["ROE_YEARLY"])
        self.assertEqual(first_record["ROE_YEARLY"], 30.50)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_empty_dataframe(self, mock_safe_call):
        """测试空 DataFrame 时的返回结构。"""
        mock_safe_call.return_value = pd.DataFrame()
        result = get_hk_financial_indicators("00700")
        self.assertEqual(result["code"], "00700")
        self.assertEqual(result["indicator"], "年度")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["data"], [])
        self.assertIn("note", result)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_none_dataframe(self, mock_safe_call):
        """测试返回 None 时的空数据处理。"""
        mock_safe_call.return_value = None
        result = get_hk_financial_indicators("00700")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["data"], [])
        self.assertIn("note", result)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_fields_map_in_result(self, mock_safe_call):
        """测试返回结果中的 fields 是完整字段映射。"""
        mock_safe_call.return_value = make_mock_financial_df()
        result = get_hk_financial_indicators("00700")
        self.assertEqual(result["fields"], _FINANCIAL_FIELD_MAP)

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_api_called_with_correct_args(self, mock_safe_call):
        """测试 safe_api_call 被调用（间接验证 akshare 接口被调用）。"""
        mock_safe_call.return_value = make_mock_financial_df()
        get_hk_financial_indicators("00700", indicator="报告期")
        self.assertTrue(mock_safe_call.called)
        # 第一个参数是 callable，第二个是 api_name（字符串）
        args, kwargs = mock_safe_call.call_args
        self.assertEqual(len(args), 2)
        self.assertIsInstance(args[1], str)
        self.assertIn("stock_financial_hk_analysis_indicator_em", args[1])


# ===========================================================================
# 3. main() 主逻辑测试（mock get_hk_financial_indicators，无网络依赖）
# ===========================================================================

class TestMainLogic(unittest.TestCase):
    """测试 main() 主逻辑 —— --financial 与 --indicator 路径。

    通过 mock get_hk_financial_indicators 隔离网络依赖。
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
                sf_module.main()
                return parse_json_output(fake_out.getvalue())

    @patch("tools.hk_stock.stock_financial.get_hk_financial_indicators")
    def test_financial_default_yearly(self, mock_get):
        """测试 --financial 默认使用年度指标。"""
        mock_get.return_value = {
            "code": "00700", "indicator": "年度",
            "count": 2, "data": [], "fields": {},
        }
        output = self._run_main_with_args(["--financial", "00700"])

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["command"], "financial")
        self.assertEqual(output["meta"]["code"], "00700")
        self.assertEqual(output["meta"]["indicator"], "年度")
        self.assertEqual(output["meta"]["market"], "hk")
        # 默认调用时 indicator 参数应为 "年度"
        mock_get.assert_called_once_with("00700", "年度")

    @patch("tools.hk_stock.stock_financial.get_hk_financial_indicators")
    def test_financial_indicator_report_period(self, mock_get):
        """测试 --financial --indicator 报告期。"""
        mock_get.return_value = {
            "code": "00700", "indicator": "报告期",
            "count": 4, "data": [], "fields": {},
        }
        output = self._run_main_with_args(
            ["--financial", "00700", "--indicator", "报告期"])

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["indicator"], "报告期")
        mock_get.assert_called_once_with("00700", "报告期")

    @patch("tools.hk_stock.stock_financial.get_hk_financial_indicators")
    def test_financial_code_zfill(self, mock_get):
        """测试代码补齐 5 位。"""
        mock_get.return_value = {
            "code": "00700", "indicator": "年度",
            "count": 0, "data": [], "fields": {},
        }
        output = self._run_main_with_args(["--financial", "700"])

        self.assertEqual(output["meta"]["code"], "00700")
        # 传给 get_hk_financial_indicators 的 code 应是补齐后的
        args, _ = mock_get.call_args
        self.assertEqual(args[0], "00700")

    @patch("tools.hk_stock.stock_financial.get_hk_financial_indicators")
    def test_financial_data_in_output(self, mock_get):
        """测试输出包含完整 data 字段。"""
        mock_get.return_value = {
            "code": "00700", "indicator": "年度",
            "count": 1,
            "data": [{"REPORT_DATE": "2023-12-31", "ROE_AVG": 28.15}],
            "fields": {"ROE_AVG": "平均净资产收益率(%)"}
        }
        output = self._run_main_with_args(["--financial", "00700"])

        self.assertTrue(output["success"])
        self.assertIn("data", output["data"])
        self.assertEqual(output["data"]["count"], 1)
        self.assertEqual(output["data"]["data"][0]["ROE_AVG"], 28.15)

    def test_no_args_exits_with_error(self):
        """测试无参数时退出且非零退出码。"""
        with patch.object(sys, "argv", ["stock_financial.py"]):
            with patch("sys.stderr", new=StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    sf_module.main()
                self.assertEqual(cm.exception.code, 1)


# ===========================================================================
# 4. 命令行接口测试（subprocess，网络依赖）
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
        self.assertIn("港股财务指标查询工具", out)
        self.assertIn("--financial", out)
        self.assertIn("--indicator", out)

    def test_no_args(self):
        """测试无参数时返回非零退出码。"""
        rc, out, err = self._run_cli([])
        self.assertNotEqual(rc, 0)

    def test_financial_yearly(self):
        """测试 --financial 00700 命令行（年度指标，网络依赖）。"""
        try:
            rc, out, err = self._run_cli(["--financial", "00700"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["command"], "financial")
                self.assertEqual(output["meta"]["code"], "00700")
                self.assertEqual(output["meta"]["indicator"], "年度")
                self.assertEqual(output["meta"]["market"], "hk")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_financial_report_period(self):
        """测试 --financial --indicator 报告期 命令行（网络依赖）。"""
        try:
            rc, out, err = self._run_cli(
                ["--financial", "00700", "--indicator", "报告期"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["indicator"], "报告期")
                self.assertEqual(output["meta"]["code"], "00700")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_data_contains_financial_fields(self):
        """测试返回数据包含 ROE_AVG 等核心财务字段（网络依赖）。"""
        try:
            rc, out, err = self._run_cli(["--financial", "00700"])
            output = parse_json_output(out)
            if not (output and output.get("success")):
                self.skipTest("网络不可用或数据获取失败")

            self.assertGreater(output["data"]["count"], 0)
            first_record = output["data"]["data"][0]
            # 核心财务字段应存在（值可能为 None）
            for field in ["ROE_AVG", "GROSS_PROFIT_RATIO", "NET_PROFIT_RATIO",
                          "DEBT_ASSET_RATIO", "CURRENT_RATIO", "OCF_SALES",
                          "HOLDER_PROFIT", "OPERATE_INCOME",
                          "BASIC_EPS", "BPS", "REPORT_DATE"]:
                self.assertIn(field, first_record)
            # 应包含中文字段映射
            self.assertIn("_fields", first_record)
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")


# ===========================================================================
# 5. 错误处理测试
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

    @patch("tools.hk_stock.stock_financial.safe_api_call")
    def test_network_error_in_get_indicators(self, mock_safe_call):
        """测试 get_hk_financial_indicators 网络错误抛出异常。"""
        mock_safe_call.side_effect = Exception("获取港股数据失败（已重试3次）: Connection failed")
        with self.assertRaises(Exception) as cm:
            get_hk_financial_indicators("00700")
        self.assertIn("获取港股财务指标失败", str(cm.exception))

    @patch("tools.hk_stock.stock_financial.get_hk_financial_indicators")
    def test_main_handles_error(self, mock_get):
        """测试 main() 捕获异常并输出错误 JSON。"""
        mock_get.side_effect = Exception("网络连接失败")
        output, code = self._run_main_with_args(["--financial", "00700"])

        self.assertEqual(code, 1)
        self.assertFalse(output["success"])
        self.assertIn("error", output)
        self.assertIn("网络连接失败", output["error"])
        self.assertEqual(output["meta"]["command"], "financial")

    @patch("tools.hk_stock.stock_financial.get_hk_financial_indicators")
    def test_main_error_includes_detail_traceback(self, mock_get):
        """测试错误输出包含 detail 字段（traceback）。"""
        mock_get.side_effect = ValueError("解析异常")
        output, code = self._run_main_with_args(["--financial", "00700"])

        self.assertEqual(code, 1)
        self.assertFalse(output["success"])
        self.assertIn("detail", output)
        self.assertIn("ValueError", output["detail"])

    def test_invalid_code_cli(self):
        """测试无效股票代码的 CLI 错误处理（网络依赖）。

        注意：港股工具的 safe_api_call 会将重试日志输出到 stderr，
        导致 stderr 可能混合日志文本与错误 JSON。此处先尝试整体解析，
        失败则提取最后一行（错误 JSON 通常在末尾）重试解析。
        """
        try:
            rc, out, err = self._run_cli(["--financial", "99999"])
            stdout = out.strip()
            stderr = err.strip()
            if stdout:
                output = parse_json_output(stdout)
                if output.get("success"):
                    # 无效代码会返回 count=0 的空数据（成功响应）
                    self.assertEqual(output["meta"]["code"], "99999")
                    self.assertEqual(output["data"]["count"], 0)
                elif "success" in output:
                    self.assertFalse(output["success"])
                else:
                    self.skipTest("无法解析 stdout 输出")
            elif stderr:
                # stderr 可能混合重试日志与错误 JSON，先整体尝试
                output = parse_json_output(stderr)
                if "success" not in output:
                    # 整体解析失败，尝试提取最后一行（错误 JSON 在末尾）
                    last_line = stderr.splitlines()[-1].strip() if stderr else ""
                    output = parse_json_output(last_line)
                if "success" in output:
                    self.assertFalse(output["success"])
                else:
                    self.skipTest("网络不可用或无法解析错误响应")
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
        suite.addTests(loader.loadTestsFromTestCase(TestFinancialFieldMap))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkFinancialIndicators))
        suite.addTests(loader.loadTestsFromTestCase(TestMainLogic))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
        suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    elif test_type == "core":
        suite.addTests(loader.loadTestsFromTestCase(TestFinancialFieldMap))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkFinancialIndicators))
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

    parser = argparse.ArgumentParser(description="港股财务指标查询工具测试模块")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "core", "main", "cli", "error"],
                        help="测试类型（默认: all）")

    args = parser.parse_args()

    success = run_tests(args.test)
    sys.exit(0 if success else 1)
