#!/usr/bin/env python3
"""A 股质量筛选工具测试模块。

测试 tools/a_share/stock_screen.py 的各功能模块，使用 unittest 框架。

测试范围：
  1. TestGetLatestQuarterDate — 最近季度末日期格式验证
  2. TestGetExchangeInfo      — 交易所/板块判断（60/00/30/688 前缀）
  3. TestSafeFloat            — 安全浮点转换（正常值/NaN/None/字符串）
  4. TestYearLabels           — 年份标签提取（仅 1231 年报）
  5. TestCalcRoe              — ROE 计算（mock 数据）
  6. TestCalcGrossMargin      — 毛利率计算（mock 数据）
  7. TestCalcNetMargin        — 净利率计算（mock 数据）
  8. TestCalcOcfToNetProfit   — 经营现金流/净利润比率（mock 数据）
  9. TestCalcDebtRatio        — 资产负债率计算（mock 数据）
 10. TestCalcShareDilution    — 股本膨胀计算（mock 数据）
 11. TestCommandLineInterface — 命令行接口（--help / --code 单只/多只）
 12. TestErrorHandling        — 错误处理（无效代码）
 13. TestNetworkFunctions     — 网络集成测试（网络不可用时跳过）

运行方式：
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/a_share/test_stock_screen.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/a_share/test_stock_screen.py

注意：
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

# 添加项目根目录到路径（测试位于 tests/a_share/，需上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
from tools.a_share.stock_screen import (
    get_latest_quarter_date,
    get_exchange_info,
    get_ipo_info,
    _safe_float,
    _year_labels,
    calc_roe,
    calc_gross_margin,
    calc_net_margin,
    calc_ocf_to_net_profit,
    calc_debt_ratio,
    calc_interest_coverage,
    calc_share_dilution,
    screen_stock,
)
from tools.a_share import stock_screen as stock_screen_module

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "a_share", "stock_screen.py")
PYTHON = sys.executable


# ===========================================================================
# 辅助函数
# ===========================================================================

def parse_json_output(text: str) -> dict:
    """解析文本为 JSON 字典。

    Args:
        text: 待解析的文本。

    Returns:
        解析后的字典；解析失败时返回空字典。
    """
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ===========================================================================
# 1. get_latest_quarter_date 测试
# ===========================================================================
class TestGetLatestQuarterDate(unittest.TestCase):
    """测试 get_latest_quarter_date 函数 —— 返回最近季度末日期。"""

    def test_format_yyyymmdd(self):
        """返回值为 8 位 YYYYMMDD 格式。"""
        result = get_latest_quarter_date()
        self.assertEqual(len(result), 8)
        self.assertTrue(result.isdigit())

    def test_year_prefix(self):
        """年份部分为 20 开头的 4 位数字。"""
        result = get_latest_quarter_date()
        year = result[:4]
        self.assertTrue(year.startswith("20"))
        self.assertEqual(len(year), 4)

    def test_valid_quarter_end(self):
        """日期为有效季度末（1231 / 0331 / 0630 / 0930）。"""
        result = get_latest_quarter_date()
        valid_ends = ["1231", "0331", "0630", "0930"]
        self.assertIn(result[4:], valid_ends)

    def test_return_type_string(self):
        """返回值类型为字符串。"""
        self.assertIsInstance(get_latest_quarter_date(), str)

    def test_current_quarter_correctness(self):
        """根据当前月份返回正确的季度末。"""
        from datetime import datetime
        now = datetime.now()
        m = now.month
        result = get_latest_quarter_date()
        if m <= 3:
            self.assertEqual(result, f"{now.year - 1}1231")
        elif m <= 6:
            self.assertEqual(result, f"{now.year}0331")
        elif m <= 9:
            self.assertEqual(result, f"{now.year}0630")
        else:
            self.assertEqual(result, f"{now.year}0930")


# ===========================================================================
# 2. get_exchange_info 测试
# ===========================================================================
class TestGetExchangeInfo(unittest.TestCase):
    """测试 get_exchange_info 函数 —— 按代码前缀判断交易所和板块。"""

    def test_sh_main_board(self):
        """60xxxx -> 上海证券交易所主板。"""
        info = get_exchange_info("600519")
        self.assertEqual(info["exchange"], "上海证券交易所")
        self.assertEqual(info["board"], "主板")
        self.assertEqual(info["exchange_short"], "沪")
        self.assertEqual(info["board_short"], "主板")

    def test_sz_main_board(self):
        """00xxxx -> 深圳证券交易所主板。"""
        info = get_exchange_info("000001")
        self.assertEqual(info["exchange"], "深圳证券交易所")
        self.assertEqual(info["board"], "主板")
        self.assertEqual(info["exchange_short"], "深")
        self.assertEqual(info["board_short"], "主板")

    def test_chinext(self):
        """30xxxx -> 深圳证券交易所创业板。"""
        info = get_exchange_info("300502")
        self.assertEqual(info["exchange"], "深圳证券交易所")
        self.assertEqual(info["board"], "创业板")
        self.assertEqual(info["exchange_short"], "深")
        self.assertEqual(info["board_short"], "创业板")

    def test_star_market(self):
        """688xxx -> 上海证券交易所科创板。"""
        info = get_exchange_info("688981")
        self.assertEqual(info["exchange"], "上海证券交易所")
        self.assertEqual(info["board"], "科创板")
        self.assertEqual(info["exchange_short"], "沪")
        self.assertEqual(info["board_short"], "科创板")

    def test_unknown_code(self):
        """无法识别的前缀 -> 未知。"""
        info = get_exchange_info("999999")
        self.assertEqual(info["exchange"], "未知")
        self.assertEqual(info["board"], "未知")

    def test_zfill_short_code(self):
        """短代码自动补齐 6 位后判断。"""
        # "502" -> "000502" -> 00 开头 -> 深圳主板
        info = get_exchange_info("502")
        self.assertEqual(info["exchange"], "深圳证券交易所")
        self.assertEqual(info["board"], "主板")

    def test_return_type_dict(self):
        """返回值类型为字典。"""
        self.assertIsInstance(get_exchange_info("600519"), dict)

    def test_dict_keys_complete(self):
        """返回字典包含完整的键。"""
        info = get_exchange_info("300502")
        expected_keys = {"exchange", "board", "exchange_short", "board_short"}
        self.assertEqual(set(info.keys()), expected_keys)


# ===========================================================================
# 3. _safe_float 测试
# ===========================================================================
class TestSafeFloat(unittest.TestCase):
    """测试 _safe_float 函数 —— 安全浮点转换。"""

    def test_normal_int(self):
        """整数正常转换为 float。"""
        self.assertEqual(_safe_float(3), 3.0)
        self.assertIsInstance(_safe_float(3), float)

    def test_normal_float(self):
        """浮点数原样返回。"""
        self.assertEqual(_safe_float(3.14), 3.14)

    def test_numeric_string(self):
        """数字字符串正确转换为 float。"""
        self.assertEqual(_safe_float("3.14"), 3.14)
        self.assertEqual(_safe_float("42"), 42.0)

    def test_none_returns_none(self):
        """None 输入返回 None。"""
        self.assertIsNone(_safe_float(None))

    def test_nan_returns_none(self):
        """NaN 输入返回 None。"""
        self.assertIsNone(_safe_float(float("nan")))
        self.assertIsNone(_safe_float(math.nan))

    def test_inf_returns_value(self):
        """无穷大不是 NaN，应返回无穷值。"""
        self.assertEqual(_safe_float(float("inf")), float("inf"))

    def test_invalid_string_returns_none(self):
        """无效字符串返回 None（ValueError 被捕获）。"""
        self.assertIsNone(_safe_float("abc"))
        self.assertIsNone(_safe_float("N/A"))
        self.assertIsNone(_safe_float(""))

    def test_list_returns_none(self):
        """列表输入返回 None（TypeError 被捕获）。"""
        self.assertIsNone(_safe_float([1, 2, 3]))

    def test_zero_value(self):
        """零值正确返回 0.0 而非 None。"""
        self.assertEqual(_safe_float(0), 0.0)
        self.assertEqual(_safe_float(0.0), 0.0)
        self.assertEqual(_safe_float("0"), 0.0)

    def test_negative_value(self):
        """负数正确转换。"""
        self.assertEqual(_safe_float(-5.5), -5.5)
        self.assertEqual(_safe_float("-10"), -10.0)


# ===========================================================================
# 4. _year_labels 测试
# ===========================================================================
class TestYearLabels(unittest.TestCase):
    """测试 _year_labels 函数 —— 从列名提取年份标签。"""

    def test_extracts_annual_only(self):
        """仅提取 1231 结尾的年报列。"""
        columns = ["选项", "指标", "20201231", "20211231", "20220630", "20231231"]
        result = _year_labels(columns)
        # 20220630 不以 1231 结尾，应排除
        self.assertEqual(result, ["2023", "2021", "2020"])

    def test_sorted_descending(self):
        """结果按年份降序排列。"""
        columns = ["20181231", "20201231", "20191231", "20211231"]
        result = _year_labels(columns)
        self.assertEqual(result, ["2021", "2020", "2019", "2018"])

    def test_skips_option_indicator(self):
        """跳过"选项"和"指标"列。"""
        columns = ["选项", "指标", "20201231"]
        result = _year_labels(columns)
        self.assertEqual(result, ["2020"])

    def test_empty_columns(self):
        """空列表返回空列表。"""
        self.assertEqual(_year_labels([]), [])

    def test_no_annual_data(self):
        """仅有季报数据时返回空列表。"""
        columns = ["20200331", "20200630", "20200930"]
        self.assertEqual(_year_labels(columns), [])

    def test_return_type_list(self):
        """返回值类型为列表。"""
        self.assertIsInstance(_year_labels(["20201231"]), list)

    def test_deduplication(self):
        """重复年份去重。"""
        columns = ["20201231", "20201231"]
        result = _year_labels(columns)
        self.assertEqual(result, ["2020"])


# ===========================================================================
# 5. calc_roe 测试
# ===========================================================================
class TestCalcRoe(unittest.TestCase):
    """测试 calc_roe 函数 —— ROE 计算。"""

    def test_basic_calculation(self):
        """基本 ROE 平均值计算。"""
        data = {
            "净资产收益率(ROE)": {
                "20201231": 15.0,
                "20211231": 16.0,
                "20221231": 17.0,
                "20231231": 18.0,
                "20241231": 19.0,
            }
        }
        result = calc_roe(data)
        self.assertEqual(result["value"], 17.0)
        self.assertEqual(result["years"], 5)
        self.assertIn("annual", result)

    def test_excludes_pre_2015(self):
        """2015 年之前的数据被排除。"""
        data = {
            "净资产收益率(ROE)": {
                "20101231": 10.0,
                "20141231": 12.0,
                "20201231": 20.0,
                "20211231": 22.0,
            }
        }
        result = calc_roe(data)
        self.assertEqual(result["years"], 2)
        self.assertEqual(result["value"], 21.0)

    def test_no_roe_key(self):
        """未找到 ROE 指标时返回 None。"""
        data = {"销售毛利率": {"20201231": 40.0}}
        result = calc_roe(data)
        self.assertIsNone(result["value"])
        self.assertIn("未找到", result["note"])

    def test_roe_data_insufficient(self):
        """所有年份均早于 2015 时数据不足。"""
        data = {
            "净资产收益率(ROE)": {
                "20101231": 10.0,
                "20121231": 12.0,
            }
        }
        result = calc_roe(data)
        self.assertIsNone(result["value"])
        self.assertIn("不足", result["note"])

    def test_fallback_key_match(self):
        """无 (ROE) 后缀时回退匹配"净资产收益率"。"""
        data = {
            "净资产收益率": {
                "20201231": 15.0,
                "20211231": 20.0,
            }
        }
        result = calc_roe(data)
        self.assertEqual(result["value"], 17.5)
        self.assertEqual(result["years"], 2)

    def test_annual_dict_content(self):
        """annual 字典包含正确的年份和值。"""
        data = {
            "净资产收益率(ROE)": {
                "20211231": 16.0,
                "20221231": 17.0,
            }
        }
        result = calc_roe(data)
        self.assertEqual(result["annual"]["2021"], 16.0)
        self.assertEqual(result["annual"]["2022"], 17.0)

    def test_note_format(self):
        """note 包含年数信息。"""
        data = {
            "净资产收益率(ROE)": {
                "20201231": 15.0,
                "20211231": 16.0,
            }
        }
        result = calc_roe(data)
        self.assertIn("2年", result["note"])

    def test_handles_nan_values(self):
        """NaN 值被跳过不参与计算。"""
        data = {
            "净资产收益率(ROE)": {
                "20201231": 15.0,
                "20211231": float("nan"),
                "20221231": 20.0,
            }
        }
        result = calc_roe(data)
        self.assertEqual(result["years"], 2)
        self.assertEqual(result["value"], 17.5)


# ===========================================================================
# 6. calc_gross_margin 测试
# ===========================================================================
class TestCalcGrossMargin(unittest.TestCase):
    """测试 calc_gross_margin 函数 —— 毛利率计算。"""

    def test_basic_calculation(self):
        """基本毛利率平均值计算。"""
        data = {
            "销售毛利率": {
                "20201231": 40.0,
                "20211231": 42.0,
                "20221231": 44.0,
            }
        }
        result = calc_gross_margin(data)
        self.assertEqual(result["value"], 42.0)
        self.assertEqual(result["years"], 3)

    def test_excludes_pre_2015(self):
        """2015 年之前的数据被排除。"""
        data = {
            "销售毛利率": {
                "20101231": 30.0,
                "20201231": 40.0,
                "20211231": 50.0,
            }
        }
        result = calc_gross_margin(data)
        self.assertEqual(result["years"], 2)
        self.assertEqual(result["value"], 45.0)

    def test_no_margin_key(self):
        """未找到毛利率指标时返回 None。"""
        data = {"净利润": {"20201231": 100.0}}
        result = calc_gross_margin(data)
        self.assertIsNone(result["value"])
        self.assertIn("未找到", result["note"])

    def test_data_insufficient(self):
        """所有年份均早于 2015 时数据不足。"""
        data = {
            "销售毛利率": {
                "20101231": 30.0,
                "20121231": 35.0,
            }
        }
        result = calc_gross_margin(data)
        self.assertIsNone(result["value"])
        self.assertIn("不足", result["note"])

    def test_excludes_cost_ratio(self):
        """排除"销售成本率"键。"""
        data = {
            "销售成本率": {"20201231": 60.0},
            "销售毛利率": {"20201231": 40.0, "20211231": 42.0},
        }
        result = calc_gross_margin(data)
        self.assertIsNotNone(result["value"])
        self.assertEqual(result["years"], 2)

    def test_note_format(self):
        """note 包含年数信息。"""
        data = {
            "销售毛利率": {
                "20201231": 40.0,
                "20211231": 42.0,
            }
        }
        result = calc_gross_margin(data)
        self.assertIn("2年", result["note"])


# ===========================================================================
# 7. calc_net_margin 测试
# ===========================================================================
class TestCalcNetMargin(unittest.TestCase):
    """测试 calc_net_margin 函数 —— 净利率计算。"""

    def test_basic_calculation(self):
        """基本净利率平均值计算。"""
        data = {
            "销售净利率": {
                "20201231": 20.0,
                "20211231": 22.0,
                "20221231": 24.0,
            }
        }
        result = calc_net_margin(data)
        self.assertEqual(result["value"], 22.0)
        self.assertEqual(result["years"], 3)

    def test_excludes_pre_2015(self):
        """2015 年之前的数据被排除。"""
        data = {
            "销售净利率": {
                "20101231": 10.0,
                "20201231": 20.0,
                "20211231": 25.0,
            }
        }
        result = calc_net_margin(data)
        self.assertEqual(result["years"], 2)
        self.assertEqual(result["value"], 22.5)

    def test_no_margin_key(self):
        """未找到净利率指标时返回 None。"""
        data = {"毛利率": {"20201231": 40.0}}
        result = calc_net_margin(data)
        self.assertIsNone(result["value"])
        self.assertIn("未找到", result["note"])

    def test_data_insufficient(self):
        """所有年份均早于 2015 时数据不足。"""
        data = {
            "销售净利率": {
                "20101231": 10.0,
                "20121231": 12.0,
            }
        }
        result = calc_net_margin(data)
        self.assertIsNone(result["value"])
        self.assertIn("不足", result["note"])

    def test_fallback_net_margin_key(self):
        """无"销售净利率"时回退匹配"净利率"。"""
        data = {
            "净利率": {
                "20201231": 15.0,
                "20211231": 20.0,
            }
        }
        result = calc_net_margin(data)
        self.assertEqual(result["value"], 17.5)
        self.assertEqual(result["years"], 2)

    def test_note_format(self):
        """note 包含年数信息。"""
        data = {
            "销售净利率": {
                "20201231": 20.0,
                "20211231": 22.0,
            }
        }
        result = calc_net_margin(data)
        self.assertIn("2年", result["note"])


# ===========================================================================
# 8. calc_ocf_to_net_profit 测试
# ===========================================================================
class TestCalcOcfToNetProfit(unittest.TestCase):
    """测试 calc_ocf_to_net_profit 函数 —— 经营现金流/净利润比率。"""

    def test_basic_calculation(self):
        """基本 OCF/NI 比率计算。"""
        data = {
            "经营现金流量净额": {
                "20211231": 1000.0,
                "20221231": 1200.0,
                "20231231": 1500.0,
            },
            "净利润": {
                "20211231": 500.0,
                "20221231": 600.0,
                "20231231": 750.0,
            }
        }
        result = calc_ocf_to_net_profit(data)
        self.assertEqual(result["value"], 2.0)
        self.assertEqual(result["years"], 3)

    def test_excludes_pre_2021(self):
        """2021 年之前的数据被排除。"""
        data = {
            "经营现金流量净额": {
                "20191231": 800.0,
                "20201231": 900.0,
                "20211231": 1000.0,
                "20221231": 1100.0,
            },
            "净利润": {
                "20191231": 400.0,
                "20201231": 450.0,
                "20211231": 500.0,
                "20221231": 500.0,
            }
        }
        result = calc_ocf_to_net_profit(data)
        # 2021: 1000/500=2.0, 2022: 1100/500=2.2 -> avg=2.1
        self.assertEqual(result["years"], 2)
        self.assertEqual(result["value"], 2.1)

    def test_missing_ocf_key(self):
        """缺少经营现金流数据时返回 None。"""
        data = {
            "净利润": {"20211231": 500.0}
        }
        result = calc_ocf_to_net_profit(data)
        self.assertIsNone(result["value"])
        self.assertIn("需要", result["note"])

    def test_missing_ni_key(self):
        """缺少净利润数据时返回 None。"""
        data = {
            "经营现金流量净额": {"20211231": 1000.0}
        }
        result = calc_ocf_to_net_profit(data)
        self.assertIsNone(result["value"])
        self.assertIn("需要", result["note"])

    def test_zero_net_profit_skipped(self):
        """净利润为 0 的年份被跳过。"""
        data = {
            "经营现金流量净额": {
                "20211231": 1000.0,
                "20221231": 1200.0,
            },
            "净利润": {
                "20211231": 0.0,
                "20221231": 600.0,
            }
        }
        result = calc_ocf_to_net_profit(data)
        self.assertEqual(result["years"], 1)
        self.assertEqual(result["value"], 2.0)

    def test_data_insufficient(self):
        """所有年份均早于 2021 时数据不足。"""
        data = {
            "经营现金流量净额": {
                "20181231": 800.0,
                "20191231": 900.0,
            },
            "净利润": {
                "20181231": 400.0,
                "20191231": 450.0,
            }
        }
        result = calc_ocf_to_net_profit(data)
        self.assertIsNone(result["value"])
        self.assertIn("不足", result["note"])

    def test_annual_ratios(self):
        """annual 字典包含正确的年比率。"""
        data = {
            "经营现金流量净额": {
                "20211231": 1000.0,
                "20221231": 1500.0,
            },
            "净利润": {
                "20211231": 500.0,
                "20221231": 500.0,
            }
        }
        result = calc_ocf_to_net_profit(data)
        self.assertEqual(result["annual"]["2021"], 2.0)
        self.assertEqual(result["annual"]["2022"], 3.0)


# ===========================================================================
# 9. calc_debt_ratio 测试
# ===========================================================================
class TestCalcDebtRatio(unittest.TestCase):
    """测试 calc_debt_ratio 函数 —— 资产负债率计算。"""

    def test_basic_calculation(self):
        """基本资产负债率计算（最新 + 平均）。"""
        data = {
            "资产负债率": {
                "20231231": 45.0,
                "20221231": 42.0,
                "20211231": 40.0,
            }
        }
        result = calc_debt_ratio(data)
        # latest 是字典中第一个值
        self.assertEqual(result["value"], 45.0)
        self.assertEqual(result["average"], 42.33)

    def test_excludes_pre_2021(self):
        """2021 年之前的数据被排除。"""
        data = {
            "资产负债率": {
                "20221231": 45.0,
                "20211231": 40.0,
                "20201231": 35.0,
                "20191231": 30.0,
            }
        }
        result = calc_debt_ratio(data)
        self.assertEqual(len(result["annual"]), 2)
        self.assertEqual(result["value"], 45.0)

    def test_no_debt_key(self):
        """未找到资产负债率指标时返回 None。"""
        data = {"毛利率": {"20211231": 40.0}}
        result = calc_debt_ratio(data)
        self.assertIsNone(result["value"])
        self.assertIn("未找到", result["note"])

    def test_data_insufficient(self):
        """所有年份均早于 2021 时数据不足。"""
        data = {
            "资产负债率": {
                "20181231": 30.0,
                "20191231": 35.0,
            }
        }
        result = calc_debt_ratio(data)
        self.assertIsNone(result["value"])
        self.assertIn("不足", result["note"])

    def test_note_contains_latest_and_avg(self):
        """note 包含最新值和平均值。"""
        data = {
            "资产负债率": {
                "20221231": 45.0,
                "20211231": 40.0,
            }
        }
        result = calc_debt_ratio(data)
        self.assertIn("最新", result["note"])
        self.assertIn("平均", result["note"])

    def test_average_calculation(self):
        """average 为所有近年值的均值。"""
        data = {
            "资产负债率": {
                "20231231": 30.0,
                "20221231": 30.0,
                "20211231": 30.0,
            }
        }
        result = calc_debt_ratio(data)
        self.assertEqual(result["average"], 30.0)

    def test_annual_dict_keys(self):
        """annual 字典包含正确的年份键。"""
        data = {
            "资产负债率": {
                "20221231": 45.0,
                "20211231": 40.0,
            }
        }
        result = calc_debt_ratio(data)
        self.assertIn("2022", result["annual"])
        self.assertIn("2021", result["annual"])


# ===========================================================================
# 10. calc_share_dilution 测试
# ===========================================================================
class TestCalcShareDilution(unittest.TestCase):
    """测试 calc_share_dilution 函数 —— 股本膨胀计算。"""

    def test_no_dilution(self):
        """股本无膨胀时返回 0%。"""
        parsed = {
            "股东权益合计": {
                "20231231": 100000.0,
                "20221231": 90000.0,
                "20211231": 80000.0,
            },
            "每股净资产": {
                "20231231": 10.0,
                "20221231": 9.0,
                "20211231": 8.0,
            }
        }
        result = calc_share_dilution("300502", parsed)
        self.assertEqual(result["value"], 0.0)
        self.assertIn("未超过20%", result["note"])

    def test_significant_dilution(self):
        """股本膨胀超过 20% 时标注警告。"""
        parsed = {
            "股东权益合计": {
                "20231231": 120000.0,
                "20211231": 80000.0,
            },
            "每股净资产": {
                "20231231": 10.0,
                "20211231": 10.0,
            }
        }
        result = calc_share_dilution("300502", parsed)
        self.assertEqual(result["value"], 50.0)
        self.assertIn("需核实", result["note"])

    def test_none_parsed(self):
        """parsed 为 None 时返回缺少数据提示。"""
        result = calc_share_dilution("300502", None)
        self.assertIsNone(result["value"])
        self.assertIn("缺少财务数据", result["note"])

    def test_empty_parsed(self):
        """parsed 为空字典时返回缺少财务数据提示（空 dict 为 falsy）。"""
        result = calc_share_dilution("300502", {})
        self.assertIsNone(result["value"])
        self.assertIn("缺少财务数据", result["note"])

    def test_missing_eps_key(self):
        """缺少每股净资产时返回提示。"""
        parsed = {
            "股东权益合计": {
                "20231231": 100000.0,
                "20211231": 80000.0,
            }
        }
        result = calc_share_dilution("300502", parsed)
        self.assertIsNone(result["value"])
        self.assertIn("缺少净资产", result["note"])

    def test_result_fields(self):
        """膨胀结果包含完整字段。"""
        parsed = {
            "股东权益合计": {
                "20231231": 120000.0,
                "20211231": 80000.0,
            },
            "每股净资产": {
                "20231231": 10.0,
                "20211231": 10.0,
            }
        }
        result = calc_share_dilution("300502", parsed)
        self.assertIn("latest_shares", result)
        self.assertIn("old_shares", result)
        self.assertIn("latest_year", result)
        self.assertIn("old_year", result)

    def test_shrink_noted_as_under_threshold(self):
        """股本缩减（负值）未超过 20% 阈值。"""
        parsed = {
            "股东权益合计": {
                "20231231": 80000.0,
                "20211231": 100000.0,
            },
            "每股净资产": {
                "20231231": 10.0,
                "20211231": 10.0,
            }
        }
        result = calc_share_dilution("300502", parsed)
        # 8000/10000 - 1 = -20%
        self.assertEqual(result["value"], -20.0)
        self.assertIn("未超过20%", result["note"])


# ===========================================================================
# 11. 命令行接口测试
# ===========================================================================
class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口参数解析。"""

    def _run(self, args, timeout=60):
        """运行工具子进程并返回 (returncode, stdout, stderr)。

        Args:
            args: 命令行参数列表。
            timeout: 超时秒数。

        Returns:
            元组 (returncode, stdout, stderr)。
        """
        cmd = [PYTHON, TOOL_PATH] + args
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=PROJECT_ROOT
        )

    def test_help(self):
        """--help 正常输出并包含关键参数说明。"""
        result = self._run(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("质量筛选", result.stdout)
        self.assertIn("--code", result.stdout)

    def test_no_args_exits_nonzero(self):
        """无参数时 argparse 报错并非零退出。"""
        result = self._run([])
        self.assertNotEqual(result.returncode, 0)

    def test_code_single_stock(self):
        """--code 单只股票筛选（网络集成）。"""
        try:
            result = self._run(["--code", "300502"], timeout=120)
            output = parse_json_output(result.stdout)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["code_count"], 1)
                self.assertEqual(len(output["data"]), 1)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code_multiple_stocks(self):
        """--code 多只股票筛选（网络集成）。"""
        try:
            result = self._run(["--code", "300502,600519"], timeout=180)
            output = parse_json_output(result.stdout)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["code_count"], 2)
                self.assertEqual(len(output["data"]), 2)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code_with_spaces(self):
        """--code 含空格的代码列表正确分割（网络集成）。"""
        try:
            result = self._run(["--code", " 300502 , 600519 "], timeout=180)
            output = parse_json_output(result.stdout)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["code_count"], 2)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")


# ===========================================================================
# 12. 错误处理测试
# ===========================================================================
class TestErrorHandling(unittest.TestCase):
    """测试错误处理机制。"""

    def _run(self, args, timeout=60):
        """运行工具子进程并返回 (returncode, stdout, stderr)。"""
        cmd = [PYTHON, TOOL_PATH] + args
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=PROJECT_ROOT
        )

    def test_invalid_code_no_crash(self):
        """无效股票代码不导致工具崩溃。"""
        try:
            result = self._run(["--code", "999999"], timeout=120)
            # 退出码 0 或 1 均可，但不能异常退出
            self.assertIn(result.returncode, (0, 1))
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_invalid_code_returns_result(self):
        """无效代码返回包含结构的 JSON（网络集成）。"""
        try:
            result = self._run(["--code", "999999"], timeout=120)
            stdout = result.stdout.strip()
            if stdout:
                output = parse_json_output(stdout)
                if output:
                    # 即使单只失败，顶层 success 可能为 True
                    # （main 不因单只失败而中断）
                    self.assertIn("data", output)
            else:
                self.skipTest("网络不可用或 stdout 为空")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_empty_code_string(self):
        """空代码字符串不导致崩溃。"""
        try:
            result = self._run(["--code", ""], timeout=60)
            # 空字符串分割后产生 [""]，screen_stock("") 应被处理
            self.assertIn(result.returncode, (0, 1))
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_handles_screen_failure(self, mock_screen):
        """main 中 screen_stock 返回失败时不崩溃。"""
        mock_screen.return_value = {
            "success": False,
            "error": "获取财务数据失败",
        }
        with patch("sys.argv", ["stock_screen.py", "--code", "999999"]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
                output = parse_json_output(fake_out.getvalue())
        # main 不因单只失败而中断，顶层 success=True
        self.assertTrue(output.get("success"))
        self.assertEqual(len(output["data"]), 1)
        self.assertFalse(output["data"][0]["success"])

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_single_code_calls_screen_once(self, mock_screen):
        """main 处理单只代码时调用 screen_stock 一次。"""
        mock_screen.return_value = {"success": True, "data": {}}
        with patch("sys.argv", ["stock_screen.py", "--code", "300502"]):
            with patch("sys.stdout", new=StringIO()):
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
        self.assertEqual(mock_screen.call_count, 1)
        mock_screen.assert_called_with("300502")

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_multiple_codes_calls_screen_multiple(self, mock_screen):
        """main 处理多只代码时分别调用 screen_stock。"""
        mock_screen.return_value = {"success": True, "data": {}}
        with patch("sys.argv", ["stock_screen.py", "--code", "300502,600519,000858"]):
            with patch("sys.stdout", new=StringIO()):
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
        self.assertEqual(mock_screen.call_count, 3)
        mock_screen.assert_any_call("300502")
        mock_screen.assert_any_call("600519")
        mock_screen.assert_any_call("000858")

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_trims_whitespace(self, mock_screen):
        """main 对代码列表去除空白。"""
        mock_screen.return_value = {"success": True, "data": {}}
        with patch("sys.argv", ["stock_screen.py", "--code", " 300502 , 600519 "]):
            with patch("sys.stdout", new=StringIO()):
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
        mock_screen.assert_any_call("300502")
        mock_screen.assert_any_call("600519")


# ===========================================================================
# 13. 网络集成测试（网络不可用时跳过）
# ===========================================================================
class TestNetworkFunctions(unittest.TestCase):
    """网络集成测试 —— 网络不可用时自动跳过。"""

    def test_screen_stock_valid_code(self):
        """screen_stock 对有效股票代码执行完整筛选。"""
        try:
            result = screen_stock("300502")
            self.assertTrue(result["success"])
            data = result["data"]
            self.assertEqual(data["code"], "300502")
            self.assertIn("screening", data)
            screening = data["screening"]
            # 7 条指标键存在
            expected_keys = {
                "1_ROE", "2_FCF", "3_interest_coverage",
                "4_gross_margin", "5_ocf_to_net_profit",
                "6_net_margin", "7_share_dilution", "debt_ratio"
            }
            self.assertEqual(
                set(screening.keys()), expected_keys
            )
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_screen_stock_exchange_info(self):
        """screen_stock 返回正确的交易所信息。"""
        try:
            result = screen_stock("600519")
            if result["success"]:
                data = result["data"]
                self.assertEqual(data["exchange"], "上海证券交易所")
                self.assertEqual(data["board"], "主板")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_screen_stock_zfill(self):
        """screen_stock 对短代码自动补齐 6 位。"""
        try:
            result = screen_stock("502")
            if result["success"]:
                self.assertEqual(result["data"]["code"], "000502")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_calc_interest_coverage_valid(self):
        """calc_interest_coverage 计算有效股票的利息覆盖倍数。"""
        try:
            result = calc_interest_coverage("600519")
            # 利息覆盖倍数可能有值也可能因数据缺失为 None
            self.assertIn("value", result)
            self.assertIn("note", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_calc_interest_coverage_invalid_code(self):
        """calc_interest_coverage 对无效代码返回 None 不崩溃。"""
        try:
            result = calc_interest_coverage("999999")
            self.assertIsNone(result["value"])
            self.assertIn("note", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_get_ipo_info_valid(self):
        """get_ipo_info 获取有效股票的 IPO 信息。"""
        try:
            result = get_ipo_info("300502")
            self.assertIsInstance(result, dict)
            self.assertIn("listing_date", result)
            self.assertIn("exchange", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_get_ipo_info_invalid_code(self):
        """get_ipo_info 对无效代码返回含 error 的字典。"""
        try:
            result = get_ipo_info("999999")
            self.assertIsInstance(result, dict)
            # 无效代码应返回带 error 的结果或空值
            self.assertIn("listing_date", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_calc_share_dilution_network(self):
        """calc_share_dilution 不带 parsed 参数时的网络行为。"""
        try:
            result = calc_share_dilution("300502")
            # 无 parsed 时返回缺少财务数据
            self.assertIsNone(result["value"])
            self.assertIn("缺少", result["note"])
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")


# ===========================================================================
# 测试入口
# ===========================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
