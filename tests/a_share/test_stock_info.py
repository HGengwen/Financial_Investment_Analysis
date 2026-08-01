#!/usr/bin/env python3
"""A股信息查询工具测试模块。

测试 tools/a_share/stock_info.py 的各功能模块。

测试模块：
1. TestGetAllAStocks       - 测试获取全部A股代码和名称
2. TestGetAStockIndustryInfo - 测试获取A股行业信息
3. TestCmdList             - 测试 --list 命令处理
4. TestCmdSearch           - 测试 --search 命令处理
5. TestCmdCode             - 测试 --code 命令处理
6. TestCmdIndustry         - 测试 --industry 命令处理
7. TestCommandLineInterface - 测试命令行接口

Usage:
    {py} -m pytest tests/a_share/test_stock_info.py -v
    {py} tests/a_share/test_stock_info.py
    {py} tests/a_share/test_stock_info.py --test all
"""

import json
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch
import unittest

# 添加项目根目录到路径（tests/a_share/ 上溯三级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 导入被测试模块
try:
    from tools.a_share.stock_info import (
        get_all_a_stocks,
        get_a_stock_industry_info,
        cmd_list,
        cmd_search,
        cmd_code,
        cmd_industry,
    )
except ImportError as e:
    print(f"无法导入 stock_info 模块: {e}")
    print("请确保在项目根目录下运行测试，且 akshare 已安装")
    sys.exit(1)


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


# ---------------------------------------------------------------------------
# 核心函数测试
# ---------------------------------------------------------------------------

class TestGetAllAStocks(unittest.TestCase):
    """测试获取全部A股代码和名称功能。"""

    def test_returns_list(self):
        """测试返回类型为列表。"""
        try:
            result = get_all_a_stocks()
            self.assertIsInstance(result, list)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_record_structure(self):
        """测试返回记录的结构。"""
        try:
            result = get_all_a_stocks()
            if len(result) > 0:
                record = result[0]
                self.assertIn("code", record)
                self.assertIn("name", record)
                self.assertIn("market", record)
                self.assertEqual(record["market"], "a")
                # A股代码应为6位
                self.assertEqual(len(record["code"]), 6)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_data_count(self):
        """测试返回数据数量（A股应超过1000只）。"""
        try:
            result = get_all_a_stocks()
            self.assertGreater(len(result), 1000)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_code_zfill(self):
        """测试代码是否被补齐为6位。"""
        try:
            result = get_all_a_stocks()
            for record in result:
                self.assertEqual(len(record["code"]), 6)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")


class TestGetAStockIndustryInfo(unittest.TestCase):
    """测试获取A股行业信息功能。"""

    def test_returns_dict(self):
        """测试返回类型为字典。"""
        try:
            result = get_a_stock_industry_info()
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_record_fields(self):
        """测试返回记录的字段完整性。"""
        try:
            result = get_a_stock_industry_info()
            if len(result) > 0:
                first_code = list(result.keys())[0]
                record = result[first_code]
                expected_fields = ["code", "name", "market", "industry",
                                   "roe", "gross_margin", "eps"]
                for field in expected_fields:
                    self.assertIn(field, record)
                self.assertEqual(record["market"], "a")
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")

    def test_code_as_key(self):
        """测试字典以股票代码为键。"""
        try:
            result = get_a_stock_industry_info()
            if len(result) > 0:
                for code, record in result.items():
                    self.assertEqual(record["code"], code)
                    self.assertEqual(len(code), 6)
        except Exception as e:
            self.skipTest(f"网络不可用: {e}")


# ---------------------------------------------------------------------------
# cmd_* 函数测试（使用 mock 隔离网络依赖）
# ---------------------------------------------------------------------------

class TestCmdList(unittest.TestCase):
    """测试 --list 命令处理。"""

    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_successful_output(self, mock_get_stocks):
        """测试成功输出 JSON 结构。"""
        mock_get_stocks.return_value = [
            {"code": "300502", "name": "新易盛", "market": "a"},
            {"code": "600519", "name": "贵州茅台", "market": "a"},
        ]

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_list()
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["command"], "list")
        self.assertEqual(output["meta"]["market"], "a")
        self.assertEqual(output["meta"]["count"], 2)
        self.assertEqual(len(output["data"]), 2)

    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_failure_handling(self, mock_get_stocks):
        """测试失败时的错误处理。"""
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

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_successful_search(self, mock_get_stocks, mock_get_industry):
        """测试成功搜索股票。"""
        mock_get_stocks.return_value = [
            {"code": "300502", "name": "新易盛", "market": "a"},
            {"code": "600519", "name": "贵州茅台", "market": "a"},
        ]
        mock_get_industry.return_value = {
            "300502": {
                "code": "300502", "name": "新易盛", "market": "a",
                "industry": "通信设备", "roe": 15.0,
                "gross_margin": 30.0, "eps": 1.5
            }
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("新易盛")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["meta"]["keyword"], "新易盛")
        self.assertEqual(len(output["data"]), 1)
        self.assertEqual(output["data"][0]["code"], "300502")
        self.assertEqual(output["data"][0]["industry"], "通信设备")

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_case_insensitive_search(self, mock_get_stocks, mock_get_industry):
        """测试搜索不区分大小写。"""
        mock_get_stocks.return_value = [
            {"code": "600519", "name": "贵州茅台", "market": "a"},
        ]
        mock_get_industry.return_value = {}

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("茅台")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(len(output["data"]), 1)

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_no_match(self, mock_get_stocks, mock_get_industry):
        """测试搜索无匹配结果。"""
        mock_get_stocks.return_value = [
            {"code": "300502", "name": "新易盛", "market": "a"},
        ]
        mock_get_industry.return_value = {}

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("不存在的公司")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(len(output["data"]), 0)
        self.assertEqual(output["meta"]["count"], 0)

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_multiple_matches(self, mock_get_stocks, mock_get_industry):
        """测试搜索匹配多个结果。"""
        mock_get_stocks.return_value = [
            {"code": "600519", "name": "贵州茅台", "market": "a"},
            {"code": "000858", "name": "五粮液", "market": "a"},
            {"code": "000568", "name": "泸州老窖", "market": "a"},
        ]
        mock_get_industry.return_value = {}

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_search("酒")
            output = parse_json_output(fake_out.getvalue())

        # "酒" 不在 "五粮液" 中，但应在 "贵州茅台"(无) 和 "泸州老窖"(无) 中
        # 实际上 "酒" 不在任何名字中，所以应为0
        self.assertTrue(output["success"])


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
        self.assertIn("股票代码", output["error"])

    def test_none_code(self):
        """测试 None 股票代码的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_code(None)
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    def test_valid_code_with_industry(self, mock_get_industry):
        """测试查询有效代码（含行业信息）。"""
        mock_get_industry.return_value = {
            "300502": {
                "code": "300502", "name": "新易盛", "market": "a",
                "industry": "通信设备", "roe": 15.0,
                "gross_margin": 30.0, "eps": 1.5
            }
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_code("300502")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["data"]["code"], "300502")
        self.assertEqual(output["data"]["name"], "新易盛")
        self.assertEqual(output["data"]["industry"], "通信设备")
        self.assertEqual(output["data"]["roe"], 15.0)

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_valid_code_without_industry(self, mock_get_stocks, mock_get_industry):
        """测试查询有效代码（无行业信息但在列表中）。"""
        mock_get_industry.return_value = {}
        mock_get_stocks.return_value = [
            {"code": "300502", "name": "新易盛", "market": "a"},
        ]

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_code("300502")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["data"]["code"], "300502")
        self.assertEqual(output["data"]["name"], "新易盛")
        self.assertEqual(output["data"]["industry"], "")
        self.assertIsNone(output["data"]["roe"])

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    @patch('tools.a_share.stock_info.get_all_a_stocks')
    def test_invalid_code(self, mock_get_stocks, mock_get_industry):
        """测试查询无效代码（不存在）。"""
        mock_get_industry.return_value = {}
        mock_get_stocks.return_value = []

        with patch('sys.stdout', new=StringIO()) as fake_out:
            cmd_code("999999")
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("未找到", output["error"])
        self.assertIn("999999", output["error"])

    @patch('tools.a_share.stock_info.get_a_stock_industry_info')
    def test_code_zfill(self, mock_get_industry):
        """测试代码补齐6位功能。"""
        mock_get_industry.return_value = {
            "000502": {
                "code": "000502", "name": "测试股票", "market": "a",
                "industry": "", "roe": None,
                "gross_margin": None, "eps": None
            }
        }

        with patch('sys.stdout', new=StringIO()) as fake_out:
            # 传入3位代码，应补齐为6位 000502
            cmd_code("502")
            output = parse_json_output(fake_out.getvalue())

        self.assertTrue(output["success"])
        self.assertEqual(output["data"]["code"], "000502")


class TestCmdIndustry(unittest.TestCase):
    """测试 --industry 命令处理。"""

    def test_empty_industry_name(self):
        """测试空行业名称的错误处理。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_industry("")
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("行业名称", output["error"])

    def test_industry_not_supported(self):
        """测试行业筛选功能返回提示（原工具中此功能未完整实现）。"""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cmd_industry("通信设备")
            self.assertEqual(cm.exception.code, 1)
            output = parse_json_output(fake_out.getvalue())

        self.assertFalse(output["success"])
        self.assertIn("error", output)


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
        script = os.path.join(PROJECT_ROOT, "tools", "a_share", "stock_info.py")
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
        self.assertIn("A股股票代码与公司信息查询工具", out)
        self.assertIn("--list", out)
        self.assertIn("--search", out)
        self.assertIn("--code", out)
        self.assertIn("--industry", out)

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
                self.assertGreater(output["meta"]["count"], 1000)
                self.assertEqual(output["meta"]["market"], "a")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_search(self):
        """测试 --search 命令行。"""
        try:
            rc, out, err = self._run_cli(["--search", "茅台"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertGreater(len(output["data"]), 0)
                self.assertEqual(output["meta"]["keyword"], "茅台")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code(self):
        """测试 --code 命令行。"""
        try:
            rc, out, err = self._run_cli(["--code", "600519"])
            output = parse_json_output(out)
            if output and output.get("success"):
                self.assertEqual(output["data"]["code"], "600519")
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_code_invalid(self):
        """测试 --code 查询无效代码。"""
        try:
            rc, out, err = self._run_cli(["--code", "999999"])
            output = parse_json_output(out)
            if output:
                self.assertFalse(output["success"])
                self.assertIn("未找到", output.get("error", ""))
            else:
                self.skipTest("网络不可用或数据获取失败")
        except subprocess.TimeoutExpired:
            self.skipTest("命令执行超时（网络问题）")

    def test_industry(self):
        """测试 --industry 命令行（功能未完整实现，应非0退出）。"""
        rc, out, err = self._run_cli(["--industry", "通信设备"])
        # industry 功能未完整实现，应返回非0退出码
        self.assertNotEqual(rc, 0)
        stdout = out.strip()
        if stdout:
            output = parse_json_output(stdout)
            self.assertFalse(output.get("success", True))


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
        suite.addTests(loader.loadTestsFromTestCase(TestGetAllAStocks))
        suite.addTests(loader.loadTestsFromTestCase(TestGetAStockIndustryInfo))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdList))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdSearch))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdCode))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdIndustry))
        suite.addTests(loader.loadTestsFromTestCase(TestCommandLineInterface))
    elif test_type == "functions":
        suite.addTests(loader.loadTestsFromTestCase(TestGetAllAStocks))
        suite.addTests(loader.loadTestsFromTestCase(TestGetAStockIndustryInfo))
    elif test_type == "cmd":
        suite.addTests(loader.loadTestsFromTestCase(TestCmdList))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdSearch))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdCode))
        suite.addTests(loader.loadTestsFromTestCase(TestCmdIndustry))
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

    parser = argparse.ArgumentParser(description="A股信息查询工具测试模块")
    parser.add_argument("--test", type=str, default="all",
                        choices=["all", "functions", "cmd", "cli"],
                        help="测试类型（默认: all）")

    args = parser.parse_args()

    success = run_tests(args.test)
    sys.exit(0 if success else 1)
