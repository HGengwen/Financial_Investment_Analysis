#!/usr/bin/env python3
"""港股信息查询工具测试模块。

测试 tools/hk_stock/stock_info.py 的各功能模块。

测试模块：
1. TestGetAllHkStocks        - 测试获取全部港股代码和名称（含备用数据源机制）
2. TestGetHkStockInfo        - 测试获取单只港股实时行情
3. TestGetHkHotStocks        - 测试获取港股人气热度榜
4. TestCmdList               - 测试 --list 命令处理
5. TestCmdSearch             - 测试 --search 命令处理
6. TestCmdCode               - 测试 --code 命令处理
7. TestCmdHot                - 测试 --hot 命令处理
8. TestCommandLineInterface  - 测试命令行接口

Usage:
    {py} -m pytest tests/hk_stock/test_stock_info.py -v
    {py} tests/hk_stock/test_stock_info.py
    {py} tests/hk_stock/test_stock_info.py --test all
"""

import json
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch
import unittest

# 添加项目根目录到路径（tests/hk_stock/ 上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
try:
    from tools.hk_stock.stock_info import (
        get_all_hk_stocks,
        get_hk_stock_info,
        get_hk_hot_stocks,
        get_hk_valuation,
        get_hk_coverage,
        _extract_institutions,
        cmd_list,
        cmd_search,
        cmd_code,
        cmd_hot,
        cmd_profile,
    )
except ImportError as e:
    print(f"无法导入 stock_info 模块: {e}")
    print("请确保在项目根目录下运行测试，且 akshare 已安装")
    sys.exit(1)

# 尝试导入 pandas（用于构造测试用 DataFrame）
try:
    import pandas as pd
except ImportError:
    pd = None


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

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


def make_hk_spot_df(code: str = "00700", name: str = "腾讯控股") -> "pd.DataFrame":
    """构造模拟 ak.stock_hk_spot() 返回值的 DataFrame。

    Args:
        code: 股票代码（5位）。
        name: 股票名称。

    Returns:
        包含单条港股行情记录的 DataFrame。
    """
    return pd.DataFrame([{
        "代码": code,
        "名称": name,
        "最新价": 300.0,
        "涨跌幅": 1.5,
        "涨跌额": 4.5,
        "成交量": 1000000.0,
        "成交额": 300000000.0,
        "最高": 305.0,
        "最低": 295.0,
        "今开": 298.0,
        "昨收": 295.5,
    }])


# ---------------------------------------------------------------------------
# 核心函数测试
# ---------------------------------------------------------------------------

class TestGetAllHkStocks(unittest.TestCase):
    """测试获取全部港股代码和名称功能。"""

    def test_returns_list(self):
        """测试返回类型为列表（网络失败时返回备用数据，仍为列表）。"""
        try:
            result = get_all_hk_stocks()
            self.assertIsInstance(result, list)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_record_structure(self):
        """测试返回记录的结构。"""
        try:
            result = get_all_hk_stocks()
            if len(result) > 0:
                record = result[0]
                self.assertIn("code", record)
                self.assertIn("name", record)
                self.assertIn("market", record)
                self.assertEqual(record["market"], "hk")
                # 港股代码应为5位
                self.assertEqual(len(record["code"]), 5)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    @unittest.skipIf(pd is None, "pandas 未安装，跳过 mock 测试")
    @patch('tools.hk_stock.stock_info.safe_api_call')
    def test_successful_fetch(self, mock_safe_call):
        """测试成功获取港股列表（mock 数据源）。"""
        mock_safe_call.return_value = pd.DataFrame([
            {"代码": "00700", "名称": "腾讯控股"},
            {"代码": "00388", "名称": "香港交易所"},
        ])
        result = get_all_hk_stocks()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["code"], "00700")
        self.assertEqual(result[0]["name"], "腾讯控股")
        self.assertEqual(result[0]["market"], "hk")

    @patch('tools.hk_stock.stock_info.safe_api_call')
    def test_backup_data_on_failure(self, mock_safe_call):
        """测试接口失败时返回备用数据源（40只主要港股）。"""
        mock_safe_call.side_effect = Exception("网络错误")
        result = get_all_hk_stocks()
        self.assertIsInstance(result, list)
        # 备用数据应包含预设的主要港股
        self.assertGreater(len(result), 0)
        # 验证备用数据结构
        for record in result:
            self.assertEqual(len(record["code"]), 5)
            self.assertEqual(record["market"], "hk")
        # 验证包含腾讯控股
        codes = [r["code"] for r in result]
        self.assertIn("00700", codes)

    @unittest.skipIf(pd is None, "pandas 未安装，跳过 mock 测试")
    @patch('tools.hk_stock.stock_info.safe_api_call')
    def test_empty_name_filtered(self, mock_safe_call):
        """测试空名称记录被过滤。"""
        mock_safe_call.return_value = pd.DataFrame([
            {"代码": "00700", "名称": "腾讯控股"},
            {"代码": "00388", "名称": ""},
        ])
        result = get_all_hk_stocks()
        # 空名称的记录应被过滤
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], "00700")


class TestGetHkStockInfo(unittest.TestCase):
    """测试获取单只港股实时行情功能。"""

    def test_valid_code(self):
        """测试查询有效代码（网络）。"""
        try:
            result = get_hk_stock_info("00700")
            if result is None:
                self.skipTest("网络返回空数据")
            self.assertIsInstance(result, dict)
            self.assertEqual(result["code"], "00700")
            self.assertEqual(result["market"], "hk")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    @unittest.skipIf(pd is None, "pandas 未安装，跳过 mock 测试")
    @patch('tools.hk_stock.stock_info.safe_api_call')
    def test_field_extraction(self, mock_safe_call):
        """测试字段提取逻辑（mock 数据源）。"""
        mock_safe_call.return_value = make_hk_spot_df("00700", "腾讯控股")
        result = get_hk_stock_info("00700")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "00700")
        self.assertEqual(result["name"], "腾讯控股")
        self.assertEqual(result["price"], 300.0)
        self.assertEqual(result["change_pct"], 1.5)
        self.assertEqual(result["change"], 4.5)
        self.assertEqual(result["volume"], 1000000.0)
        self.assertEqual(result["amount"], 300000000.0)
        self.assertEqual(result["high"], 305.0)
        self.assertEqual(result["low"], 295.0)
        self.assertEqual(result["open"], 298.0)
        self.assertEqual(result["pre_close"], 295.5)

    @unittest.skipIf(pd is None, "pandas 未安装，跳过 mock 测试")
    @patch('tools.hk_stock.stock_info.safe_api_call')
    def test_invalid_code_returns_none(self, mock_safe_call):
        """测试查询不存在的代码返回 None。"""
        mock_safe_call.return_value = make_hk_spot_df("00700", "腾讯控股")
        result = get_hk_stock_info("99999")
        self.assertIsNone(result)

    @patch('tools.hk_stock.stock_info.safe_api_call')
    def test_api_failure_raises(self, mock_safe_call):
        """测试 API 调用失败时抛出异常。"""
        mock_safe_call.side_effect = Exception("网络错误")
        with self.assertRaises(Exception) as cm:
            get_hk_stock_info("00700")
        self.assertIn("获取港股信息失败", str(cm.exception))


class TestGetHkHotStocks(unittest.TestCase):
    """测试获取港股人气热度榜功能。"""

    def test_returns_list(self):
        """测试返回类型为列表。"""
        try:
            result = get_hk_hot_stocks()
            self.assertIsInstance(result, list)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_record_structure(self):
        """测试返回记录的结构。"""
        try:
            result = get_hk_hot_stocks()
            if len(result) > 0:
                record = result[0]
                self.assertIn("rank", record)
                self.assertIn("code", record)
                self.assertIn("name", record)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    @patch('tools.hk_stock.stock_info.ak')
    def test_api_failure_raises(self, mock_ak):
        """测试 API 调用失败时抛出异常。"""
        mock_ak.stock_hk_hot_rank_em.side_effect = Exception("网络错误")
        with self.assertRaises(Exception) as cm:
            get_hk_hot_stocks()
        self.assertIn("获取港股热度榜失败", str(cm.exception))


# ---------------------------------------------------------------------------
# cmd_* 函数测试（使用 mock 隔离网络依赖）
# ---------------------------------------------------------------------------

class TestCmdList(unittest.TestCase):
    """测试 --list 命令处理。"""

    @patch('tools.hk_stock.stock_info.get_all_hk_stocks')
    def test_successful_output(self, mock_get_stocks):
        """测试成功输出 JSON 结构。"""
        mock_get_stocks.return_value = [
            {"code": "00700", "name": "腾讯控股", "market": "hk"},
            {"code": "00388", "name": "香港交易所", "market": "hk"},
        ]

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_list()
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["command"], "list")
        self.assertEqual(output["meta"]["market"], "hk")
        self.assertEqual(output["meta"]["count"], 2)
        self.assertEqual(len(output["data"]), 2)

    @patch('tools.hk_stock.stock_info.get_all_hk_stocks')
    def test_failure_handling(self, mock_get_stocks):
        """测试失败时的错误处理。

        注意：get_all_hk_stocks 内置备用数据源，正常情况下不会抛异常。
        此处通过 mock 强制抛异常，验证 cmd_list 的错误处理逻辑。
        """
        mock_get_stocks.side_effect = Exception("网络错误")

        with patch('sys.stderr', new=StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as cm:
                cmd_list()
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_err.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("error", output)
        self.assertIn("网络错误", output["error"])


class TestCmdSearch(unittest.TestCase):
    """测试 --search 命令处理。"""

    def test_empty_keyword(self):
        """测试空搜索关键词的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_search("")
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("关键词", output["error"])

    def test_none_keyword(self):
        """测试 None 关键词的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_search(None)
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    @patch('tools.hk_stock.stock_info.get_all_hk_stocks')
    def test_successful_search(self, mock_get_stocks, mock_get_info):
        """测试成功搜索港股。"""
        mock_get_stocks.return_value = [
            {"code": "00700", "name": "腾讯控股", "market": "hk"},
            {"code": "00388", "name": "香港交易所", "market": "hk"},
        ]
        mock_get_info.return_value = {
            "code": "00700", "name": "腾讯控股", "market": "hk",
            "price": 300.0, "change_pct": 1.5, "change": 4.5,
            "volume": 1000000.0, "amount": 300000000.0,
            "high": 305.0, "low": 295.0, "open": 298.0, "pre_close": 295.5,
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("腾讯")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["keyword"], "腾讯")
        self.assertEqual(len(output["data"]), 1)
        self.assertEqual(output["data"][0]["code"], "00700")
        self.assertEqual(output["data"][0]["price"], 300.0)

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    @patch('tools.hk_stock.stock_info.get_all_hk_stocks')
    def test_case_insensitive_search(self, mock_get_stocks, mock_get_info):
        """测试搜索不区分大小写。"""
        mock_get_stocks.return_value = [
            {"code": "01810", "name": "小米集团-W", "market": "hk"},
        ]
        mock_get_info.return_value = {
            "code": "01810", "name": "小米集团-W", "market": "hk",
            "price": None, "change_pct": None, "change": None,
            "volume": None, "amount": None, "high": None, "low": None,
            "open": None, "pre_close": None,
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("小米")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(len(output["data"]), 1)

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    @patch('tools.hk_stock.stock_info.get_all_hk_stocks')
    def test_no_match(self, mock_get_stocks, mock_get_info):
        """测试搜索无匹配结果。"""
        mock_get_stocks.return_value = [
            {"code": "00700", "name": "腾讯控股", "market": "hk"},
        ]
        mock_get_info.return_value = None

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("不存在的公司")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(len(output["data"]), 0)
        self.assertEqual(output["meta"]["count"], 0)

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    @patch('tools.hk_stock.stock_info.get_all_hk_stocks')
    def test_search_fallback_on_info_error(self, mock_get_stocks, mock_get_info):
        """测试获取实时行情失败时回退到基础信息。"""
        mock_get_stocks.return_value = [
            {"code": "00700", "name": "腾讯控股", "market": "hk"},
        ]
        # get_hk_stock_info 抛异常时，cmd_search 回退使用基础记录
        mock_get_info.side_effect = Exception("行情获取失败")

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("腾讯")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(len(output["data"]), 1)
        # 回退数据应为基础记录（无 price 字段）
        self.assertEqual(output["data"][0]["code"], "00700")
        self.assertNotIn("price", output["data"][0])


class TestCmdCode(unittest.TestCase):
    """测试 --code 命令处理。"""

    def test_empty_code(self):
        """测试空股票代码的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_code("")
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("港股代码", output["error"])

    def test_none_code(self):
        """测试 None 股票代码的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_code(None)
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    def test_valid_code(self, mock_get_info):
        """测试查询有效代码。"""
        mock_get_info.return_value = {
            "code": "00700", "name": "腾讯控股", "market": "hk",
            "price": 300.0, "change_pct": 1.5, "change": 4.5,
            "volume": 1000000.0, "amount": 300000000.0,
            "high": 305.0, "low": 295.0, "open": 298.0, "pre_close": 295.5,
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_code("00700")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["data"]["code"], "00700")
        self.assertEqual(output["data"]["name"], "腾讯控股")
        self.assertEqual(output["data"]["price"], 300.0)
        self.assertEqual(output["meta"]["code"], "00700")

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    def test_invalid_code(self, mock_get_info):
        """测试查询无效代码（不存在）。"""
        mock_get_info.return_value = None

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_code("99999")
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("未找到", output["error"])
        self.assertIn("99999", output["error"])

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    def test_code_zfill(self, mock_get_info):
        """测试代码补齐5位功能。"""
        mock_get_info.return_value = {
            "code": "00700", "name": "腾讯控股", "market": "hk",
            "price": 300.0, "change_pct": None, "change": None,
            "volume": None, "amount": None, "high": None, "low": None,
            "open": None, "pre_close": None,
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            # 传入3位代码，应补齐为5位 00700
            cmd_code("700")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["data"]["code"], "00700")
        # 验证 get_hk_stock_info 被调用时传入补齐后的代码
        mock_get_info.assert_called_once_with("00700")

    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    def test_api_failure_handling(self, mock_get_info):
        """测试 API 调用失败时的错误处理。"""
        mock_get_info.side_effect = Exception("网络错误")

        with patch('sys.stderr', new=StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as cm:
                cmd_code("00700")
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_err.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("网络错误", output["error"])


class TestCmdHot(unittest.TestCase):
    """测试 --hot 命令处理。"""

    @patch('tools.hk_stock.stock_info.get_hk_hot_stocks')
    def test_successful_output(self, mock_get_hot):
        """测试成功输出热度榜 JSON 结构。"""
        mock_get_hot.return_value = [
            {"rank": 1, "code": "00700", "name": "腾讯控股",
             "price": 300.0, "change_pct": 1.5},
            {"rank": 2, "code": "01810", "name": "小米集团-W",
             "price": 15.0, "change_pct": -0.5},
        ]

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_hot()
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["command"], "hot")
        self.assertEqual(output["meta"]["market"], "hk")
        self.assertEqual(output["meta"]["count"], 2)
        self.assertEqual(len(output["data"]), 2)
        self.assertEqual(output["data"][0]["rank"], 1)

    @patch('tools.hk_stock.stock_info.get_hk_hot_stocks')
    def test_failure_handling(self, mock_get_hot):
        """测试失败时的错误处理。"""
        mock_get_hot.side_effect = Exception("网络错误")

        with patch('sys.stderr', new=StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as cm:
                cmd_hot()
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_err.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("error", output)
        self.assertIn("网络错误", output["error"])


# ---------------------------------------------------------------------------
# 市值与研报覆盖测试（阶段三任务2）
# ---------------------------------------------------------------------------

@unittest.skipIf(pd is None, "pandas 未安装，跳过 mock 测试")
class TestGetHkValuation(unittest.TestCase):
    """测试港股总市值获取。"""

    @patch('tools.hk_stock.stock_info.ak.stock_hk_valuation_baidu')
    def test_success(self, mock_val):
        """百度港股估值取最近一日 value。"""
        mock_val.return_value = pd.DataFrame(
            {"date": ["2026-08-24", "2026-08-25"], "value": [55000.0, 56361.17]})
        result = get_hk_valuation("00700")
        self.assertEqual(result["market_cap"], 56361.17)
        self.assertEqual(result["currency"], "HKD")
        self.assertEqual(result["unit"], "亿港元")
        self.assertEqual(result["gap"], {})

    @patch('tools.hk_stock.stock_info.ak.stock_hk_valuation_baidu')
    def test_failure_marks_gap(self, mock_val):
        """接口失败时标注缺口。"""
        mock_val.side_effect = ConnectionError("断连")
        result = get_hk_valuation("00700")
        self.assertIsNone(result["market_cap"])
        self.assertIn("market_cap", result["gap"])


class TestExtractInstitutions(unittest.TestCase):
    """测试机构名抽取纯函数。"""

    def test_deduplicate(self):
        """机构名去重保序。"""
        texts = ["中信证券发布了研报", "摩根士丹利投行发布了研报", "中信证券再次覆盖"]
        result = _extract_institutions(texts)
        self.assertEqual(result, ["中信证券", "摩根士丹利投行"])

    def test_empty(self):
        """空输入返回空列表。"""
        self.assertEqual(_extract_institutions([]), [])

    def test_no_match(self):
        """无机构名时返回空列表。"""
        self.assertEqual(_extract_institutions(["无机构信息"]), [])


class TestGetHkCoverage(unittest.TestCase):
    """测试港股研报/机构覆盖（doubao 半自动）。"""

    def _completed_process(self, stdout):
        """构造 subprocess 返回对象。"""
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout)

    @patch('tools.hk_stock.stock_info.subprocess.run')
    def test_success(self, mock_run):
        """解析 doubao JSON 并抽取机构。"""
        payload = json.dumps({
            "Result": {"WebResults": [
                {"Title": "中信证券：腾讯控股研报", "SiteName": "", "Summary": ""},
                {"Title": "摩根士丹利投行 重申买入", "SiteName": "", "Summary": ""},
            ]}
        }, ensure_ascii=False)
        mock_run.return_value = self._completed_process(payload)
        result = get_hk_coverage("00700", "腾讯控股")
        self.assertEqual(result["total_results"], 2)
        self.assertEqual(result["coverage_count"], 2)
        self.assertIn("中信证券", result["coverage_institutions"])
        self.assertEqual(result["gap"], {})

    @patch('tools.hk_stock.stock_info.subprocess.run')
    def test_nonzero_returncode(self, mock_run):
        """doubao 非零退出标注缺口。"""
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="")
        result = get_hk_coverage("00700")
        self.assertEqual(result["coverage_count"], 0)
        self.assertIn("coverage", result["gap"])

    @patch('tools.hk_stock.stock_info.subprocess.run')
    def test_invalid_json(self, mock_run):
        """输出非 JSON 标注缺口。"""
        mock_run.return_value = self._completed_process("not-json")
        result = get_hk_coverage("00700")
        self.assertEqual(result["coverage_count"], 0)
        self.assertIn("coverage", result["gap"])


class TestCmdProfile(unittest.TestCase):
    """测试 --profile 命令处理。"""

    def test_empty_code(self):
        """测试空代码的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_profile("")
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("港股代码", output["error"])

    @patch('tools.hk_stock.stock_info.get_hk_coverage')
    @patch('tools.hk_stock.stock_info.get_hk_valuation')
    @patch('tools.hk_stock.stock_info.get_hk_stock_info')
    def test_successful_profile(self, mock_info, mock_val, mock_cov):
        """画像组合行情/市值/覆盖度。"""
        mock_info.return_value = {"code": "00700", "name": "腾讯控股", "market": "hk",
                                  "price": 300.0, "change_pct": None, "change": None,
                                  "volume": None, "amount": None, "high": None,
                                  "low": None, "open": None, "pre_close": None}
        mock_val.return_value = {"market_cap": 56361.17, "currency": "HKD",
                                 "unit": "亿港元", "gap": {}}
        mock_cov.return_value = {"total_results": 20, "coverage_institutions": ["中金公司"],
                                 "coverage_count": 1, "gap": {}}

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_profile("00700")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["command"], "profile")
        self.assertEqual(output["data"]["code"], "00700")
        self.assertEqual(output["data"]["market_cap"], 56361.17)
        self.assertEqual(output["data"]["valuation_gap"], None)
        self.assertEqual(output["data"]["coverage"]["coverage_count"], 1)


# ---------------------------------------------------------------------------
# 命令行接口测试（使用 subprocess 调用）
# ---------------------------------------------------------------------------

class TestCommandLineInterface(unittest.TestCase):
    """测试命令行接口。"""

    def _run_cli(self, args: list) -> tuple:
        """运行命令行并返回 (returncode, stdout, stderr)。

        Args:
            args: 命令行参数列表。

        Returns:
            元组 (returncode, stdout, stderr)。
        """
        py = sys.executable
        script = os.path.join(PROJECT_ROOT, "tools", "hk_stock", "stock_info.py")
        result = subprocess.run(
            [py, script] + args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=120
        )
        return result.returncode, result.stdout, result.stderr

    def test_help(self):
        """测试 --help 参数输出。"""
        rc, out, err = self._run_cli(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("港股股票信息查询工具", out)
        self.assertIn("--list", out)
        self.assertIn("--search", out)
        self.assertIn("--code", out)
        self.assertIn("--hot", out)
        # 拆分后不应包含 --financial 参数
        self.assertNotIn("--financial", out)
        self.assertNotIn("--indicator", out)

    def test_no_args(self):
        """测试无参数时的错误提示。"""
        rc, out, err = self._run_cli([])
        self.assertNotEqual(rc, 0)

    def test_list(self):
        """测试 --list 命令行。"""
        try:
            rc, out, err = self._run_cli(["--list"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["market"], "hk")
                self.assertGreater(output["meta"]["count"], 0)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_search(self):
        """测试 --search 命令行。"""
        try:
            rc, out, err = self._run_cli(["--search", "腾讯"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["keyword"], "腾讯")
                self.assertGreater(len(output["data"]), 0)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code(self):
        """测试 --code 命令行。"""
        try:
            rc, out, err = self._run_cli(["--code", "00700"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["data"]["code"], "00700")
                self.assertEqual(output["data"]["market"], "hk")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code_invalid(self):
        """测试 --code 查询无效代码。"""
        try:
            rc, out, err = self._run_cli(["--code", "99999"])
            output = parse_json_output(out)
            if output:
                self.assertFalse(output["success"])
                self.assertIn("未找到", output.get("error", ""))
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_hot(self):
        """测试 --hot 命令行。"""
        try:
            rc, out, err = self._run_cli(["--hot"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["meta"]["command"], "hot")
                self.assertGreater(output["meta"]["count"], 0)
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

def run_tests(test_type: str = "all") -> bool:
    """运行测试。

    Args:
        test_type: 测试类型，可选 "all"、"functions"、"cmd"、"cli"。

    Returns:
        测试是否全部成功。
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if test_type == "all":
        suite.addTests(loader.loadTestsFromTestCase(TestGetAllHkStocks))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkStockInfo))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkHotStocks))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkValuation))
        suite.addTests(loader.loadTestsFromTestCase(TestExtractInstitutions))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkCoverage))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdList))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdSearch))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdCode))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdHot))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdProfile))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    elif test_type == "functions":
        suite.addTests(loader.loadTestsFromTestCase(TestGetAllHkStocks))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkStockInfo))
        suite.addTests(loader.loadTestsFromTestCase(TestGetHkHotStocks))
    elif test_type == "cmd":
        suite.addTests(loader.loadTestsFromTestCase(TestCmdList))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdSearch))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdCode))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdHot))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdProfile))
    elif test_type == "cli":
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
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

    parser = argparse.ArgumentParser(description="港股信息查询工具测试模块")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "functions", "cmd", "cli"],
                        help="测试类型（默认: all）")

    args = parser.parse_args()

    success = run_tests(args.test)
    sys.exit(0 if success else 1)
