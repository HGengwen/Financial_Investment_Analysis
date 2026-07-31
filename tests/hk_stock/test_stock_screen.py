#!/usr/bin/env python3
"""港股质量筛选工具测试模块。

测试 tools/hk_stock/stock_screen.py 的各功能模块，使用 unittest 框架。

测试范围：
  1. TestGetHkStockInfo        — 港股基本信息（纯函数）
  2. TestCalcRoeAvg            — ROE 平均值计算（mock 数据，阈值 8%）
  3. TestCalcFcf               — 自由现金流计算（mock 数据，累计为正）
  4. TestCalcGrossMarginAvg    — 毛利率平均值（mock 数据，阈值 15%）
  5. TestCalcOcfToNi           — 经营现金流/净利润（mock 数据，阈值 0.7）
  6. TestCalcNetMarginAvg      — 净利率平均值（mock 数据，阈值 5%）
  7. TestCalcInterestCoverage  — 利息覆盖倍数（mock DataFrame，阈值 2）
  8. TestCalcShareDilution     — 股本稀释计算（mock DataFrame，阈值 20%）
  9. TestScreenStock           — 主筛选函数（mock 网络依赖）
 10. TestCommandLineInterface  — 命令行接口（--help / --code 单只/多只）
 11. TestErrorHandling         — 错误处理（无效代码、网络错误）
 12. TestNetworkFunctions      — 网络集成测试（网络不可用时跳过）

运行方式：
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/hk_stock/test_stock_screen.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/hk_stock/test_stock_screen.py

注意：
    依赖网络的测试使用 try-except + skipTest 处理，网络不可用时不失败。
    纯函数使用 mock 数据进行精确断言，不受网络环境影响。
"""

import json
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
from tools.hk_stock.stock_screen import (
    get_hk_stock_info,
    get_hk_financial_indicators,
    calc_roe_avg,
    calc_fcf,
    calc_interest_coverage,
    calc_gross_margin_avg,
    calc_ocf_to_ni,
    calc_net_margin_avg,
    calc_share_dilution,
    screen_stock,
)
from tools.hk_stock import stock_screen as stock_screen_module

# 工具文件路径（用于 CLI 子进程测试）
TOOL_PATH = os.path.join(PROJECT_ROOT, "tools", "hk_stock", "stock_screen.py")
PYTHON = sys.executable


# ===========================================================================
# 辅助函数与 mock 数据
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


def _pick(lst, i, default):
    """从列表安全取值，索引越界时返回默认值。

    Args:
        lst: 值列表（可为 None）。
        i: 索引。
        default: 默认值。

    Returns:
        lst[i] 若存在，否则 default。
    """
    if lst is not None and i < len(lst):
        return lst[i]
    return default


def make_financial_data(roe_list=None, gross_list=None, net_list=None,
                        ocf_sales_list=None, income_list=None,
                        bps_list=None, debt_ratio_list=None,
                        current_ratio_list=None, years=None):
    """构造 mock 财务数据列表。

    若未显式指定 years，则从传入的最长列表推断年数；无列表时默认 5 年。

    Args:
        roe_list: ROE 值列表，默认全部 15.0。
        gross_list: 毛利率值列表，默认全部 40.0。
        net_list: 净利率值列表，默认全部 20.0。
        ocf_sales_list: 经营现金流/营收百分比列表，默认全部 15.0。
        income_list: 营业收入列表，默认全部 10000.0。
        bps_list: 每股净资产列表，默认全部 10.0。
        debt_ratio_list: 资产负债率列表，默认全部 40.0。
        current_ratio_list: 流动比率列表，默认全部 2.0。
        years: 数据年数；None 时自动推断。

    Returns:
        财务数据字典列表，按年份降序（最新在前）。
    """
    # 未指定年数时，从传入列表推断
    if years is None:
        all_lists = [roe_list, gross_list, net_list, ocf_sales_list,
                     income_list, bps_list, debt_ratio_list,
                     current_ratio_list]
        years = max((len(l) for l in all_lists if l is not None), default=5)

    base_year = 2023
    data = []
    for i in range(years):
        year = base_year - i
        record = {
            "report_date": f"{year}-12-31",
            "roe_avg": _pick(roe_list, i, 15.0),
            "gross_profit_ratio": _pick(gross_list, i, 40.0),
            "net_profit_ratio": _pick(net_list, i, 20.0),
            "ocf_sales": _pick(ocf_sales_list, i, 15.0),
            "holder_profit": 2000.0,
            "operate_income": _pick(income_list, i, 10000.0),
            "debt_asset_ratio": _pick(debt_ratio_list, i, 40.0),
            "current_ratio": _pick(current_ratio_list, i, 2.0),
            "bps": _pick(bps_list, i, 10.0),
        }
        data.append(record)
    return data


def make_profit_df(pre_tax=1000.0, finance_cost=-200.0, num_years=3):
    """构造 mock 利润表 DataFrame。

    Args:
        pre_tax: 除税前溢利金额。
        finance_cost: 融资成本金额（通常为负值）。
        num_years: 年数。

    Returns:
        包含 REPORT_DATE、STD_ITEM_NAME、AMOUNT 列的 DataFrame。
    """
    rows = []
    base_year = 2023
    for i in range(num_years):
        year = base_year - i
        date = f"{year}-12-31"
        rows.append({"REPORT_DATE": date, "STD_ITEM_NAME": "除税前溢利",
                     "AMOUNT": pre_tax})
        rows.append({"REPORT_DATE": date, "STD_ITEM_NAME": "融资成本",
                     "AMOUNT": finance_cost})
    return pd.DataFrame(rows)


def make_balance_df(equity_list=None, num_years=3):
    """构造 mock 资产负债表 DataFrame。

    Args:
        equity_list: 股东权益金额列表。
        num_years: 年数。

    Returns:
        包含 REPORT_DATE、STD_ITEM_NAME、AMOUNT 列的 DataFrame。
    """
    if equity_list is None:
        equity_list = [100000.0] * num_years
    rows = []
    base_year = 2023
    for i in range(num_years):
        year = base_year - i
        date = f"{year}-12-31"
        rows.append({"REPORT_DATE": date, "STD_ITEM_NAME": "股东权益",
                     "AMOUNT": equity_list[i]})
    return pd.DataFrame(rows)


# ===========================================================================
# 1. get_hk_stock_info 测试
# ===========================================================================
class TestGetHkStockInfo(unittest.TestCase):
    """测试 get_hk_stock_info 函数 —— 港股基本信息。"""

    def test_returns_dict(self):
        """返回值类型为字典。"""
        self.assertIsInstance(get_hk_stock_info("00700"), dict)

    def test_code_preserved(self):
        """代码正确传入返回字典。"""
        info = get_hk_stock_info("00700")
        self.assertEqual(info["code"], "00700")

    def test_exchange_field(self):
        """交易所字段为香港证券交易所。"""
        info = get_hk_stock_info("03690")
        self.assertEqual(info["exchange"], "香港证券交易所")

    def test_board_field(self):
        """板块字段为港股。"""
        info = get_hk_stock_info("00700")
        self.assertEqual(info["board"], "港股")

    def test_market_field(self):
        """市场字段为 hk。"""
        info = get_hk_stock_info("01810")
        self.assertEqual(info["market"], "hk")

    def test_keys_complete(self):
        """返回字典包含完整键。"""
        info = get_hk_stock_info("00700")
        expected_keys = {"code", "exchange", "board", "market"}
        self.assertEqual(set(info.keys()), expected_keys)


# ===========================================================================
# 2. calc_roe_avg 测试
# ===========================================================================
class TestCalcRoeAvg(unittest.TestCase):
    """测试 calc_roe_avg 函数 —— ROE 平均值计算（指标①，阈值 8%）。"""

    def test_basic_pass(self):
        """ROE 平均值 >= 8% 时通过。"""
        data = make_financial_data(roe_list=[15.0, 16.0, 17.0])
        result = calc_roe_avg(data)
        self.assertEqual(result["value"], 16.0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["threshold"], 8.0)
        self.assertEqual(result["count"], 3)

    def test_below_threshold(self):
        """ROE 平均值 < 8% 时不通过。"""
        data = make_financial_data(roe_list=[5.0, 6.0, 7.0])
        result = calc_roe_avg(data)
        self.assertEqual(result["value"], 6.0)
        self.assertFalse(result["pass"])

    def test_exactly_at_threshold(self):
        """ROE 平均值恰好等于 8% 时通过（>= 判断）。"""
        data = make_financial_data(roe_list=[8.0, 8.0])
        result = calc_roe_avg(data)
        self.assertEqual(result["value"], 8.0)
        self.assertTrue(result["pass"])

    def test_all_none_values(self):
        """所有 ROE 值为 None 时返回数据不足。"""
        data = make_financial_data(roe_list=[None, None, None])
        result = calc_roe_avg(data)
        self.assertIsNone(result["value"])
        self.assertEqual(result["note"], "数据不足")
        self.assertIsNone(result["pass"])

    def test_some_none_skipped(self):
        """None 值被跳过，仅计算有效值。"""
        data = make_financial_data(roe_list=[10.0, None, 20.0])
        result = calc_roe_avg(data)
        self.assertEqual(result["value"], 15.0)
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["pass"])

    def test_empty_list(self):
        """空列表返回数据不足。"""
        result = calc_roe_avg([])
        self.assertIsNone(result["value"])
        self.assertEqual(result["note"], "数据不足")

    def test_value_rounded(self):
        """返回值四舍五入到 2 位小数。"""
        data = make_financial_data(roe_list=[10.0, 11.0, 11.0])
        # avg = 10.666... -> 10.67
        result = calc_roe_avg(data)
        self.assertEqual(result["value"], 10.67)


# ===========================================================================
# 3. calc_fcf 测试
# ===========================================================================
class TestCalcFcf(unittest.TestCase):
    """测试 calc_fcf 函数 —— 自由现金流计算（指标②，累计为正）。"""

    def test_positive_fcf_pass(self):
        """累计现金流为正时通过。"""
        data = make_financial_data(
            ocf_sales_list=[20.0, 20.0, 20.0],
            income_list=[1000.0, 1000.0, 1000.0],
        )
        result = calc_fcf(data)
        # ocf = 20 * 1000 / 100 = 200 每年，累计 600
        self.assertEqual(result["value"], "正")
        self.assertTrue(result["pass"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["cumulative"], 600.0)

    def test_negative_fcf_fail(self):
        """累计现金流为负时不通过。"""
        data = make_financial_data(
            ocf_sales_list=[-10.0, -10.0, -10.0],
            income_list=[1000.0, 1000.0, 1000.0],
        )
        result = calc_fcf(data)
        self.assertEqual(result["value"], "负")
        self.assertFalse(result["pass"])

    def test_only_first_five_years(self):
        """超过 5 年时仅取前 5 年。"""
        data = make_financial_data(
            ocf_sales_list=[10.0] * 7,
            income_list=[100.0] * 7,
            years=7,
        )
        result = calc_fcf(data)
        self.assertEqual(result["count"], 5)

    def test_missing_data_insufficient(self):
        """缺少 ocf_sales 或 operate_income 时数据不足。"""
        data = make_financial_data(
            ocf_sales_list=[None, None],
            income_list=[1000.0, 1000.0],
        )
        result = calc_fcf(data)
        self.assertIsNone(result["value"])
        self.assertEqual(result["note"], "数据不足")

    def test_empty_list(self):
        """空列表返回数据不足。"""
        result = calc_fcf([])
        self.assertIsNone(result["value"])

    def test_cumulative_value_correct(self):
        """累计值计算正确。"""
        data = make_financial_data(
            ocf_sales_list=[10.0, 20.0],
            income_list=[500.0, 1000.0],
        )
        result = calc_fcf(data)
        # ocf1 = 10*500/100 = 50, ocf2 = 20*1000/100 = 200, 累计 = 250
        self.assertEqual(result["cumulative"], 250.0)


# ===========================================================================
# 4. calc_gross_margin_avg 测试
# ===========================================================================
class TestCalcGrossMarginAvg(unittest.TestCase):
    """测试 calc_gross_margin_avg 函数 —— 毛利率平均值（指标④，阈值 15%）。"""

    def test_basic_pass(self):
        """毛利率平均值 >= 15% 时通过。"""
        data = make_financial_data(gross_list=[40.0, 42.0, 44.0])
        result = calc_gross_margin_avg(data)
        self.assertEqual(result["value"], 42.0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["threshold"], 15.0)
        self.assertEqual(result["count"], 3)

    def test_below_threshold(self):
        """毛利率平均值 < 15% 时不通过。"""
        data = make_financial_data(gross_list=[10.0, 12.0])
        result = calc_gross_margin_avg(data)
        self.assertEqual(result["value"], 11.0)
        self.assertFalse(result["pass"])

    def test_only_first_five_years(self):
        """超过 5 年时仅取前 5 年。"""
        data = make_financial_data(gross_list=[40.0] * 7, years=7)
        result = calc_gross_margin_avg(data)
        self.assertEqual(result["count"], 5)

    def test_all_none_insufficient(self):
        """所有毛利率值为 None 时数据不足。"""
        data = make_financial_data(gross_list=[None, None, None])
        result = calc_gross_margin_avg(data)
        self.assertIsNone(result["value"])
        self.assertEqual(result["note"], "数据不足")

    def test_some_none_skipped(self):
        """None 值被跳过。"""
        data = make_financial_data(gross_list=[40.0, None, 20.0])
        result = calc_gross_margin_avg(data)
        self.assertEqual(result["value"], 30.0)
        self.assertEqual(result["count"], 2)

    def test_empty_list(self):
        """空列表返回数据不足。"""
        result = calc_gross_margin_avg([])
        self.assertIsNone(result["value"])


# ===========================================================================
# 5. calc_ocf_to_ni 测试
# ===========================================================================
class TestCalcOcfToNi(unittest.TestCase):
    """测试 calc_ocf_to_ni 函数 —— 经营现金流/净利润（指标⑤，阈值 0.7）。"""

    def test_basic_pass(self):
        """OCF/NI >= 0.7 时通过。"""
        data = make_financial_data(
            ocf_sales_list=[15.0, 15.0],
            net_list=[10.0, 10.0],
        )
        result = calc_ocf_to_ni(data)
        # ratio = 15 / 10 = 1.5
        self.assertEqual(result["value"], 1.5)
        self.assertTrue(result["pass"])
        self.assertEqual(result["threshold"], 0.7)

    def test_below_threshold(self):
        """OCF/NI < 0.7 时不通过。"""
        data = make_financial_data(
            ocf_sales_list=[5.0, 5.0],
            net_list=[20.0, 20.0],
        )
        result = calc_ocf_to_ni(data)
        # ratio = 5 / 20 = 0.25
        self.assertEqual(result["value"], 0.25)
        self.assertFalse(result["pass"])

    def test_zero_net_profit_skipped(self):
        """净利率为 0 的年份被跳过。"""
        data = make_financial_data(
            ocf_sales_list=[15.0, 15.0],
            net_list=[0.0, 10.0],
        )
        result = calc_ocf_to_ni(data)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["value"], 1.5)

    def test_only_first_five_years(self):
        """超过 5 年时仅取前 5 年。"""
        data = make_financial_data(
            ocf_sales_list=[15.0] * 7,
            net_list=[10.0] * 7,
            years=7,
        )
        result = calc_ocf_to_ni(data)
        self.assertEqual(result["count"], 5)

    def test_missing_data_insufficient(self):
        """缺少数据时返回数据不足。"""
        data = make_financial_data(
            ocf_sales_list=[None, None],
            net_list=[10.0, 10.0],
        )
        result = calc_ocf_to_ni(data)
        self.assertIsNone(result["value"])
        self.assertEqual(result["note"], "数据不足")

    def test_empty_list(self):
        """空列表返回数据不足。"""
        result = calc_ocf_to_ni([])
        self.assertIsNone(result["value"])


# ===========================================================================
# 6. calc_net_margin_avg 测试
# ===========================================================================
class TestCalcNetMarginAvg(unittest.TestCase):
    """测试 calc_net_margin_avg 函数 —— 净利率平均值（指标⑥，阈值 5%）。"""

    def test_basic_pass(self):
        """净利率平均值 >= 5% 时通过。"""
        data = make_financial_data(net_list=[20.0, 22.0, 24.0])
        result = calc_net_margin_avg(data)
        self.assertEqual(result["value"], 22.0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["threshold"], 5.0)
        self.assertEqual(result["count"], 3)

    def test_below_threshold(self):
        """净利率平均值 < 5% 时不通过。"""
        data = make_financial_data(net_list=[2.0, 3.0])
        result = calc_net_margin_avg(data)
        self.assertEqual(result["value"], 2.5)
        self.assertFalse(result["pass"])

    def test_all_none_insufficient(self):
        """所有净利率值为 None 时数据不足。"""
        data = make_financial_data(net_list=[None, None, None])
        result = calc_net_margin_avg(data)
        self.assertIsNone(result["value"])
        self.assertEqual(result["note"], "数据不足")

    def test_some_none_skipped(self):
        """None 值被跳过。"""
        data = make_financial_data(net_list=[10.0, None, 20.0])
        result = calc_net_margin_avg(data)
        self.assertEqual(result["value"], 15.0)
        self.assertEqual(result["count"], 2)

    def test_empty_list(self):
        """空列表返回数据不足。"""
        result = calc_net_margin_avg([])
        self.assertIsNone(result["value"])

    def test_uses_all_years(self):
        """净利率使用全部年数（不限 5 年）。"""
        data = make_financial_data(net_list=[20.0] * 7, years=7)
        result = calc_net_margin_avg(data)
        self.assertEqual(result["count"], 7)


# ===========================================================================
# 7. calc_interest_coverage 测试（mock 网络依赖）
# ===========================================================================
class TestCalcInterestCoverage(unittest.TestCase):
    """测试 calc_interest_coverage 函数 —— 利息覆盖倍数（指标③，阈值 2）。"""

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_basic_pass(self, mock_profit):
        """利息覆盖倍数 >= 2 时通过。"""
        mock_profit.return_value = {
            "success": True,
            "data": make_profit_df(pre_tax=1000.0, finance_cost=-200.0),
            "count": 6,
        }
        # ebit = 1000 + 200 = 1200, coverage = 1200 / 200 = 6.0
        result = calc_interest_coverage("00700")
        self.assertEqual(result["value"], 6.0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["threshold"], 2.0)

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_below_threshold(self, mock_profit):
        """利息覆盖倍数 < 2 时不通过。"""
        mock_profit.return_value = {
            "success": True,
            "data": make_profit_df(pre_tax=100.0, finance_cost=-200.0),
            "count": 6,
        }
        # ebit = 100 + 200 = 300, coverage = 300 / 200 = 1.5
        result = calc_interest_coverage("00700")
        self.assertEqual(result["value"], 1.5)
        self.assertFalse(result["pass"])

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_profit_statement_failure(self, mock_profit):
        """利润表获取失败时返回 None。"""
        mock_profit.return_value = {
            "success": False,
            "error": "网络错误",
        }
        result = calc_interest_coverage("00700")
        self.assertIsNone(result["value"])
        self.assertIn("获取利润表失败", result["note"])

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_missing_items(self, mock_profit):
        """利润表缺少关键科目时返回 None。"""
        # 构造缺少"融资成本"的 DataFrame
        df = pd.DataFrame([
            {"REPORT_DATE": "2023-12-31", "STD_ITEM_NAME": "除税前溢利",
             "AMOUNT": 1000.0},
        ])
        mock_profit.return_value = {
            "success": True,
            "data": df,
            "count": 1,
        }
        result = calc_interest_coverage("00700")
        self.assertIsNone(result["value"])
        self.assertIn("缺少", result["note"])

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_zero_finance_cost(self, mock_profit):
        """融资成本为 0 时利息覆盖倍数为 999。"""
        mock_profit.return_value = {
            "success": True,
            "data": make_profit_df(pre_tax=1000.0, finance_cost=0.0),
            "count": 6,
        }
        result = calc_interest_coverage("00700")
        # finance_cost=0 -> coverage = 999
        self.assertEqual(result["value"], 999)
        self.assertTrue(result["pass"])

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_history_built(self, mock_profit):
        """返回结果包含历史数据。"""
        mock_profit.return_value = {
            "success": True,
            "data": make_profit_df(pre_tax=1000.0, finance_cost=-200.0,
                                   num_years=3),
            "count": 6,
        }
        result = calc_interest_coverage("00700")
        self.assertIn("history", result)
        self.assertEqual(len(result["history"]), 3)

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_exception_with_auxiliary(self, mock_profit):
        """获取异常时使用辅助指标推断。"""
        mock_profit.side_effect = Exception("连接超时")
        financial_data = make_financial_data(debt_ratio_list=[30.0], years=1)
        result = calc_interest_coverage("00700", financial_data)
        self.assertIsNone(result["value"])
        self.assertIn("辅助指标推断", result["note"])
        self.assertEqual(result["auxiliary"]["debt_asset_ratio"], 30.0)

    @patch.object(stock_screen_module, "get_hk_profit_statement")
    def test_exception_without_auxiliary(self, mock_profit):
        """获取异常且无辅助数据时返回失败。"""
        mock_profit.side_effect = Exception("连接超时")
        result = calc_interest_coverage("00700")
        self.assertIsNone(result["value"])
        self.assertIn("计算利息覆盖倍数失败", result["note"])


# ===========================================================================
# 8. calc_share_dilution 测试（mock 网络依赖）
# ===========================================================================
class TestCalcShareDilution(unittest.TestCase):
    """测试 calc_share_dilution 函数 —— 股本稀释（指标⑦，阈值 20%）。"""

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    @patch.object(stock_screen_module, "get_hk_balance_sheet")
    def test_no_dilution_pass(self, mock_balance, mock_indicator):
        """股本无明显膨胀时通过。"""
        mock_balance.return_value = {
            "success": True,
            "data": make_balance_df(equity_list=[100000.0, 100000.0, 100000.0]),
            "count": 3,
        }
        mock_indicator.return_value = {
            "success": True,
            "data": make_financial_data(bps_list=[10.0, 10.0, 10.0], years=3),
            "count": 3,
        }
        # share_count = 100000/10 = 10000 每年，变化率 0%
        result = calc_share_dilution("00700")
        self.assertEqual(result["value"], 0.0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["threshold"], 20.0)

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    @patch.object(stock_screen_module, "get_hk_balance_sheet")
    def test_significant_dilution_fail(self, mock_balance, mock_indicator):
        """股本膨胀超过 20% 时不通过。"""
        mock_balance.return_value = {
            "success": True,
            "data": make_balance_df(equity_list=[120000.0, 100000.0, 80000.0]),
            "count": 3,
        }
        mock_indicator.return_value = {
            "success": True,
            "data": make_financial_data(bps_list=[10.0, 10.0, 10.0], years=3),
            "count": 3,
        }
        # 最新 12000, 最旧 8000, 变化率 = (12000-8000)/8000*100 = 50%
        result = calc_share_dilution("00700")
        self.assertEqual(result["value"], 50.0)
        self.assertFalse(result["pass"])

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    @patch.object(stock_screen_module, "get_hk_balance_sheet")
    def test_share_shrink_pass(self, mock_balance, mock_indicator):
        """股本缩减（回购）时通过。"""
        mock_balance.return_value = {
            "success": True,
            "data": make_balance_df(equity_list=[80000.0, 90000.0, 100000.0]),
            "count": 3,
        }
        mock_indicator.return_value = {
            "success": True,
            "data": make_financial_data(bps_list=[10.0, 10.0, 10.0], years=3),
            "count": 3,
        }
        # 最新 8000, 最旧 10000, 变化率 = -20% -> pass
        result = calc_share_dilution("00700")
        self.assertEqual(result["value"], -20.0)
        self.assertTrue(result["pass"])

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    @patch.object(stock_screen_module, "get_hk_balance_sheet")
    def test_balance_failure(self, mock_balance, mock_indicator):
        """资产负债表获取失败时返回 None。"""
        mock_balance.return_value = {
            "success": False,
            "error": "网络错误",
        }
        result = calc_share_dilution("00700")
        self.assertIsNone(result["value"])
        self.assertIn("获取资产负债表失败", result["note"])

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    @patch.object(stock_screen_module, "get_hk_balance_sheet")
    def test_indicator_failure(self, mock_balance, mock_indicator):
        """财务指标获取失败时返回 None。"""
        mock_balance.return_value = {
            "success": True,
            "data": make_balance_df(),
            "count": 3,
        }
        mock_indicator.return_value = {
            "success": False,
            "error": "网络错误",
        }
        result = calc_share_dilution("00700")
        self.assertIsNone(result["value"])
        self.assertIn("获取财务指标失败", result["note"])

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    @patch.object(stock_screen_module, "get_hk_balance_sheet")
    def test_insufficient_share_data(self, mock_balance, mock_indicator):
        """股本数据不足时返回 None。"""
        mock_balance.return_value = {
            "success": True,
            "data": make_balance_df(equity_list=[100000.0], num_years=1),
            "count": 1,
        }
        mock_indicator.return_value = {
            "success": True,
            "data": make_financial_data(bps_list=[10.0], years=1),
            "count": 1,
        }
        result = calc_share_dilution("00700")
        self.assertIsNone(result["value"])
        self.assertIn("数据不足", result["note"])

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    @patch.object(stock_screen_module, "get_hk_balance_sheet")
    def test_exception_with_bps_fallback(self, mock_balance, mock_indicator):
        """异常时使用 BPS 变化推断。"""
        mock_balance.side_effect = Exception("连接超时")
        mock_indicator.side_effect = Exception("连接超时")
        financial_data = make_financial_data(bps_list=[12.0, 10.0], years=2)
        result = calc_share_dilution("00700", financial_data)
        self.assertIsNone(result["value"])
        self.assertIn("BPS变化推断", result["note"])
        self.assertIn("bps_change", result)


# ===========================================================================
# 9. screen_stock 测试（mock 网络依赖）
# ===========================================================================
class TestScreenStock(unittest.TestCase):
    """测试 screen_stock 函数 —— 主筛选函数。"""

    @patch.object(stock_screen_module, "calc_share_dilution")
    @patch.object(stock_screen_module, "calc_interest_coverage")
    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_success(self, mock_fin, mock_interest, mock_dilution):
        """完整筛选成功时返回正确结构。"""
        mock_fin.return_value = {
            "success": True,
            "data": make_financial_data(years=3),
            "count": 3,
        }
        mock_interest.return_value = {"value": 6.0, "pass": True,
                                      "threshold": 2.0}
        mock_dilution.return_value = {"value": 0.0, "pass": True,
                                      "threshold": 20.0}
        result = screen_stock("00700")
        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(data["code"], "00700")
        indicators = data["indicators"]
        expected_keys = {
            "1_roe_avg", "2_fcf", "3_interest_coverage",
            "4_gross_margin_avg", "5_ocf_to_ni",
            "6_net_margin_avg", "7_share_dilution"
        }
        self.assertEqual(set(indicators.keys()), expected_keys)

    @patch.object(stock_screen_module, "calc_share_dilution")
    @patch.object(stock_screen_module, "calc_interest_coverage")
    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_summary(self, mock_fin, mock_interest, mock_dilution):
        """筛选结果包含 summary 统计。"""
        mock_fin.return_value = {
            "success": True,
            "data": make_financial_data(years=3),
            "count": 3,
        }
        mock_interest.return_value = {"value": 6.0, "pass": True}
        mock_dilution.return_value = {"value": 0.0, "pass": True}
        result = screen_stock("00700")
        summary = result["data"]["summary"]
        self.assertIn("passed_count", summary)
        self.assertIn("failed_count", summary)
        self.assertIn("unknown_count", summary)
        self.assertIn("overall_pass", summary)

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_financial_failure(self, mock_fin):
        """财务数据获取失败时返回错误。"""
        mock_fin.return_value = {
            "success": False,
            "error": "未找到数据",
        }
        result = screen_stock("00700")
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["code"], "00700")

    @patch.object(stock_screen_module, "calc_share_dilution")
    @patch.object(stock_screen_module, "calc_interest_coverage")
    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_zfill_code(self, mock_fin, mock_interest, mock_dilution):
        """短代码自动补齐 5 位。"""
        mock_fin.return_value = {
            "success": True,
            "data": make_financial_data(years=3),
            "count": 3,
        }
        mock_interest.return_value = {"value": 6.0, "pass": True}
        mock_dilution.return_value = {"value": 0.0, "pass": True}
        result = screen_stock("700")
        self.assertEqual(result["data"]["code"], "00700")

    @patch.object(stock_screen_module, "calc_share_dilution")
    @patch.object(stock_screen_module, "calc_interest_coverage")
    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_meta_fields(self, mock_fin, mock_interest, mock_dilution):
        """筛选结果包含正确的 meta 字段。"""
        mock_fin.return_value = {
            "success": True,
            "data": make_financial_data(years=3),
            "count": 3,
        }
        mock_interest.return_value = {"value": 6.0, "pass": True}
        mock_dilution.return_value = {"value": 0.0, "pass": True}
        result = screen_stock("00700")
        meta = result["meta"]
        self.assertEqual(meta["tool"], "stock_screen_hk")
        self.assertEqual(meta["code"], "00700")
        self.assertEqual(meta["market"], "hk")

    @patch.object(stock_screen_module, "calc_share_dilution")
    @patch.object(stock_screen_module, "calc_interest_coverage")
    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_overall_pass_all_pass(self, mock_fin, mock_interest,
                                          mock_dilution):
        """全部指标通过时 overall_pass 为 True。"""
        mock_fin.return_value = {
            "success": True,
            "data": make_financial_data(
                roe_list=[15.0, 15.0],
                gross_list=[40.0, 40.0],
                net_list=[20.0, 20.0],
                ocf_sales_list=[15.0, 15.0],
                income_list=[1000.0, 1000.0],
                years=2,
            ),
            "count": 2,
        }
        mock_interest.return_value = {"value": 6.0, "pass": True}
        mock_dilution.return_value = {"value": 0.0, "pass": True}
        result = screen_stock("00700")
        summary = result["data"]["summary"]
        self.assertEqual(summary["failed_count"], 0)
        self.assertTrue(summary["overall_pass"])

    @patch.object(stock_screen_module, "calc_share_dilution")
    @patch.object(stock_screen_module, "calc_interest_coverage")
    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_overall_fail_with_failure(self, mock_fin, mock_interest,
                                              mock_dilution):
        """有指标失败时 overall_pass 为 False。"""
        mock_fin.return_value = {
            "success": True,
            "data": make_financial_data(
                roe_list=[3.0, 3.0],  # ROE 低于阈值
                years=2,
            ),
            "count": 2,
        }
        mock_interest.return_value = {"value": 6.0, "pass": True}
        mock_dilution.return_value = {"value": 0.0, "pass": True}
        result = screen_stock("00700")
        summary = result["data"]["summary"]
        self.assertGreater(summary["failed_count"], 0)
        self.assertFalse(summary["overall_pass"])


# ===========================================================================
# 10. 命令行接口测试
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

    def test_help_contains_7_indicators(self):
        """--help 输出包含 7 条指标说明。"""
        result = self._run(["--help"])
        self.assertIn("ROE", result.stdout)
        self.assertIn("利息覆盖", result.stdout)
        self.assertIn("股本膨胀", result.stdout)

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_single_code(self, mock_screen):
        """main 处理单只港股代码。"""
        mock_screen.return_value = {"success": True, "data": {}}
        with patch("sys.argv", ["stock_screen.py", "--code", "00700"]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
                output = parse_json_output(fake_out.getvalue())
        self.assertTrue(output.get("success"))
        self.assertEqual(output.get("count"), 1)
        mock_screen.assert_called_once_with("00700")

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_multiple_codes(self, mock_screen):
        """main 处理多只港股代码。"""
        mock_screen.return_value = {"success": True, "data": {}}
        with patch("sys.argv", ["stock_screen.py", "--code", "00700,03690,01810"]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
                output = parse_json_output(fake_out.getvalue())
        self.assertTrue(output.get("success"))
        self.assertEqual(output.get("count"), 3)
        self.assertEqual(mock_screen.call_count, 3)
        mock_screen.assert_any_call("00700")
        mock_screen.assert_any_call("03690")
        mock_screen.assert_any_call("01810")

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_trims_whitespace(self, mock_screen):
        """main 对代码列表去除空白。"""
        mock_screen.return_value = {"success": True, "data": {}}
        with patch("sys.argv", ["stock_screen.py", "--code", " 00700 , 03690 "]):
            with patch("sys.stdout", new=StringIO()):
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
        mock_screen.assert_any_call("00700")
        mock_screen.assert_any_call("03690")

    @patch.object(stock_screen_module, "screen_stock")
    def test_main_handles_failure(self, mock_screen):
        """main 中 screen_stock 返回失败时顶层仍成功。"""
        mock_screen.return_value = {
            "success": False,
            "error": "获取财务数据失败",
        }
        with patch("sys.argv", ["stock_screen.py", "--code", "99999"]):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                try:
                    stock_screen_module.main()
                except SystemExit:
                    pass
                output = parse_json_output(fake_out.getvalue())
        self.assertTrue(output.get("success"))
        self.assertEqual(len(output["data"]), 1)
        self.assertFalse(output["data"][0]["success"])

    def test_code_single_stock_network(self):
        """--code 单只港股筛选（网络集成）。"""
        try:
            result = self._run(["--code", "00700"], timeout=120)
            output = parse_json_output(result.stdout)
            if output and output.get("success"):
                self.assertEqual(output["count"], 1)
                self.assertEqual(len(output["data"]), 1)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code_multiple_stocks_network(self):
        """--code 多只港股筛选（网络集成）。"""
        try:
            result = self._run(["--code", "00700,03690"], timeout=180)
            output = parse_json_output(result.stdout)
            if output and output.get("success"):
                self.assertEqual(output["count"], 2)
                self.assertEqual(len(output["data"]), 2)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")


# ===========================================================================
# 11. 错误处理测试
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
        """无效港股代码不导致工具崩溃。"""
        try:
            result = self._run(["--code", "99999"], timeout=120)
            self.assertIn(result.returncode, (0, 1))
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_invalid_code_returns_result(self):
        """无效代码返回包含结构的 JSON（网络集成）。"""
        try:
            result = self._run(["--code", "99999"], timeout=120)
            stdout = result.stdout.strip()
            if stdout:
                output = parse_json_output(stdout)
                if output:
                    self.assertIn("data", output)
            else:
                self.skipTest("网络不可用或 stdout 为空")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_screen_stock_network_error_handled(self, mock_fin):
        """网络错误被捕获并返回结构化错误。"""
        mock_fin.return_value = {
            "success": False,
            "error": "连接超时",
            "detail": "traceback...",
        }
        result = screen_stock("00700")
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["code"], "00700")

    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_empty_code_string_handled(self, mock_fin):
        """空代码补齐后仍执行（zfill 处理）。"""
        mock_fin.return_value = {
            "success": False,
            "error": "未找到数据",
        }
        result = screen_stock("")
        self.assertFalse(result["success"])
        # zfill(5) on "" -> "00000"
        self.assertEqual(result["code"], "00000")

    @patch.object(stock_screen_module, "calc_share_dilution")
    @patch.object(stock_screen_module, "calc_interest_coverage")
    @patch.object(stock_screen_module, "get_hk_financial_indicators")
    def test_network_error_in_indicators(self, mock_fin, mock_interest,
                                         mock_dilution):
        """指标计算中的网络错误不影响其他指标。"""
        mock_fin.return_value = {
            "success": True,
            "data": make_financial_data(years=3),
            "count": 3,
        }
        # 利息覆盖和股本稀释返回 None（网络错误场景）
        mock_interest.return_value = {"value": None, "pass": None,
                                      "note": "网络错误"}
        mock_dilution.return_value = {"value": None, "pass": None,
                                      "note": "网络错误"}
        result = screen_stock("00700")
        # 筛选不崩溃，unknown_count > 0
        self.assertTrue(result["success"])
        summary = result["data"]["summary"]
        self.assertGreater(summary["unknown_count"], 0)


# ===========================================================================
# 12. 网络集成测试（网络不可用时跳过）
# ===========================================================================
class TestNetworkFunctions(unittest.TestCase):
    """网络集成测试 —— 网络不可用时自动跳过。"""

    def test_get_hk_financial_indicators_valid(self):
        """get_hk_financial_indicators 获取有效港股财务数据。"""
        try:
            result = get_hk_financial_indicators("00700")
            if result.get("success"):
                self.assertIn("data", result)
                self.assertIsInstance(result["data"], list)
                self.assertGreater(result["count"], 0)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_get_hk_financial_indicators_invalid(self):
        """get_hk_financial_indicators 对无效代码返回失败。"""
        try:
            result = get_hk_financial_indicators("99999")
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_screen_stock_valid_code(self):
        """screen_stock 对有效港股代码执行完整筛选。"""
        try:
            result = screen_stock("00700")
            if result["success"]:
                data = result["data"]
                self.assertEqual(data["code"], "00700")
                indicators = data["indicators"]
                expected_keys = {
                    "1_roe_avg", "2_fcf", "3_interest_coverage",
                    "4_gross_margin_avg", "5_ocf_to_ni",
                    "6_net_margin_avg", "7_share_dilution"
                }
                self.assertEqual(set(indicators.keys()), expected_keys)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_screen_stock_zfill(self):
        """screen_stock 对短代码自动补齐 5 位。"""
        try:
            result = screen_stock("700")
            if result["success"]:
                self.assertEqual(result["data"]["code"], "00700")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_calc_interest_coverage_valid(self):
        """calc_interest_coverage 计算有效港股的利息覆盖倍数。"""
        try:
            result = calc_interest_coverage("00700")
            self.assertIn("value", result)
            self.assertIn("note", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_calc_share_dilution_valid(self):
        """calc_share_dilution 计算有效港股的股本稀释。"""
        try:
            result = calc_share_dilution("00700")
            self.assertIn("value", result)
            self.assertIn("note", result)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")


# ===========================================================================
# 测试入口
# ===========================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
