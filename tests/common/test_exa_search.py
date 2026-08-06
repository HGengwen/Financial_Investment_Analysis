"""
Exa 搜索工具测试
=================

测试 tools/common/exa_search.py 的功能，参考 test_tavily_search.py 的结构。

测试内容:
1. parse_results 结果解析（mock 数据，无网络依赖）
2. print_results 打印功能（mock 数据）
3. 错误处理（mock requests 失败）
4. 网络集成测试（可选，未配置 EXA_API_KEY 时跳过）

用法:
python tests/common/test_exa_search.py
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根目录到 Python 路径
# 本文件位于 tests/common/ 下，需向上 3 层到达项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from tools.common.exa_search import (
    search_exa,
    parse_results,
    print_results,
    exa_search,
    SEARCH_TYPE_MAP,
    DEFAULT_MAX_RESULTS,
    API_BASE_URL,
    SEARCH_ENDPOINT,
)


# ===========================================================================
# 辅助函数：构建 mock 数据
# ===========================================================================

def make_mock_search_response() -> dict:
    """构建模拟的 Exa /search 成功响应。

    Returns:
        模拟的 Exa API 响应字典（text 模式）。
    """
    return {
        "requestId": "mock-request-id",
        "autopromptString": "mock autoprompt",
        "results": [
            {
                "title": "紫金矿业2025年年报披露",
                "url": "https://example.com/zijin-2025",
                "publishedDate": "2026-03-15T00:00:00.000Z",
                "author": "测试作者",
                "text": "紫金矿业2025年实现营业收入4353亿元，归母净利润197亿元，同比增长显著。"
                       "公司持续加大矿产资源勘探开发力度。",
            },
            {
                "title": "紫金矿业 2025年财报分析",
                "url": "https://example.com/zijin-analysis",
                "publishedDate": "2026-03-20T00:00:00.000Z",
                "text": "机构分析认为紫金矿业铜金双轮驱动战略成效显著。",
            },
            {
                "title": "无发布时间的结果",
                "url": "https://example.com/no-date",
                "text": "这条结果没有发布时间字段。",
            },
        ],
    }


def make_mock_highlights_response() -> dict:
    """构建模拟的 Exa /search 高亮摘要响应。

    Returns:
        模拟的 Exa API 响应字典（highlights 模式）。
    """
    return {
        "results": [
            {
                "title": "黄金价格2026年走势分析",
                "url": "https://example.com/gold-2026",
                "publishedDate": "2026-07-01T00:00:00.000Z",
                "highlights": [
                    "黄金价格在2026年创出新高",
                    "央行持续增持黄金储备",
                ],
            },
        ],
    }


# ===========================================================================
# 1. parse_results 测试（无网络依赖）
# ===========================================================================

class TestParseResults(unittest.TestCase):
    """测试 parse_results 函数。"""

    def test_returns_list(self):
        """测试返回类型为列表。"""
        result = parse_results(make_mock_search_response(), "测试查询")
        self.assertIsInstance(result, list)

    def test_result_count(self):
        """测试结果数量与响应一致。"""
        result = parse_results(make_mock_search_response(), "测试查询")
        self.assertEqual(len(result), 3)

    def test_fields_present(self):
        """测试每项包含 title、url、published_date、content 字段。"""
        result = parse_results(make_mock_search_response(), "测试查询")
        for item in result:
            self.assertIn("title", item)
            self.assertIn("url", item)
            self.assertIn("published_date", item)
            self.assertIn("content", item)

    def test_text_content_extracted(self):
        """测试 text 模式内容提取。"""
        result = parse_results(make_mock_search_response(), "测试查询")
        self.assertIn("营业收入4353亿元", result[0]["content"])

    def test_highlights_content_extracted(self):
        """测试 highlights 模式内容提取（列表合并）。"""
        result = parse_results(make_mock_highlights_response(), "测试查询")
        self.assertEqual(len(result), 1)
        self.assertIn("黄金价格在2026年创出新高", result[0]["content"])
        self.assertIn("央行持续增持黄金储备", result[0]["content"])

    def test_published_date_extracted(self):
        """测试发布时间提取。"""
        result = parse_results(make_mock_search_response(), "测试查询")
        self.assertEqual(result[0]["published_date"], "2026-03-15T00:00:00.000Z")

    def test_missing_published_date(self):
        """测试缺失发布时间时为空字符串。"""
        result = parse_results(make_mock_search_response(), "测试查询")
        self.assertEqual(result[2]["published_date"], "")

    def test_empty_results(self):
        """测试空结果列表。"""
        result = parse_results({"results": []}, "测试查询")
        self.assertEqual(result, [])

    def test_missing_results_key(self):
        """测试响应缺少 results 键时返回空列表。"""
        result = parse_results({}, "测试查询")
        self.assertEqual(result, [])


# ===========================================================================
# 2. print_results 测试（无网络依赖）
# ===========================================================================

class TestPrintResults(unittest.TestCase):
    """测试 print_results 函数。"""

    def make_test_result(self) -> dict:
        """构建测试用结果字典。"""
        return {
            "success": True,
            "query": "测试关键词",
            "max_results": 2,
            "search_type": "auto",
            "results": [
                {
                    "title": "测试标题1",
                    "url": "https://example.com/1",
                    "published_date": "2026-01-01",
                    "content": "这是测试内容1，用于验证打印功能。",
                },
                {
                    "title": "测试标题2",
                    "url": "",
                    "published_date": "",
                    "content": "",
                },
            ],
        }

    def test_print_text_mode(self):
        """测试文本模式打印不抛异常。"""
        result = self.make_test_result()
        with patch("sys.stdout"):
            print_results(result, output_json=False)

    def test_print_json_mode(self):
        """测试 JSON 模式打印不抛异常且含 results。"""
        result = self.make_test_result()
        with patch("sys.stdout") as mock_stdout:
            print_results(result, output_json=True)
            # 验证 JSON 输出内容包含查询关键词
            call_args = str(mock_stdout.write.call_args_list)
            self.assertIn("测试关键词", call_args)


# ===========================================================================
# 3. search_exa 错误处理测试（mock requests，无网络依赖）
# ===========================================================================

class TestSearchExa(unittest.TestCase):
    """测试 search_exa 函数的错误处理。"""

    def test_missing_api_key(self):
        """测试未传 API Key 时返回 None。"""
        with patch("tools.common.exa_search.requests.post") as mock_post:
            result = search_exa("测试", api_key="")
            self.assertIsNone(result)
            mock_post.assert_not_called()

    def test_http_error(self):
        """测试 HTTP 错误状态返回 None。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("tools.common.exa_search.requests.post",
                   return_value=mock_resp) as mock_post:
            result = search_exa("测试", api_key="test-key")
            self.assertIsNone(result)
            mock_post.assert_called_once()

    def test_rate_limit_error(self):
        """测试 429 限流错误返回 None。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch("tools.common.exa_search.requests.post",
                   return_value=mock_resp):
            result = search_exa("测试", api_key="test-key")
            self.assertIsNone(result)

    def test_network_error(self):
        """测试网络异常返回 None。"""
        with patch("tools.common.exa_search.requests.post",
                   side_effect=Exception("Connection failed")):
            result = search_exa("测试", api_key="test-key")
            self.assertIsNone(result)

    def test_success_response(self):
        """测试成功响应返回结构化结果。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = make_mock_search_response()
        with patch("tools.common.exa_search.requests.post",
                   return_value=mock_resp) as mock_post:
            result = search_exa("紫金矿业", api_key="test-key", max_results=3)

            self.assertIsNotNone(result)
            self.assertTrue(result["success"])
            self.assertEqual(result["query"], "紫金矿业")
            self.assertEqual(len(result["results"]), 3)

            # 验证请求体参数
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            self.assertEqual(payload["query"], "紫金矿业")
            self.assertEqual(payload["numResults"], 3)
            self.assertEqual(payload["type"], "auto")
            self.assertTrue(payload["useAutoprompt"])
            self.assertIn("text", payload["contents"])

            # 验证认证头
            headers = call_args.kwargs["headers"]
            self.assertEqual(headers["x-api-key"], "test-key")

    def test_highlights_mode_payload(self):
        """测试 highlights 模式请求体。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = make_mock_highlights_response()
        with patch("tools.common.exa_search.requests.post",
                   return_value=mock_resp) as mock_post:
            result = search_exa("黄金", api_key="test-key", use_highlights=True)

            self.assertIsNotNone(result)
            payload = mock_post.call_args.kwargs["json"]
            self.assertIn("highlights", payload["contents"])

    def test_invalid_search_type_fallback(self):
        """测试非法检索档位回退到 auto。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = make_mock_search_response()
        with patch("tools.common.exa_search.requests.post",
                   return_value=mock_resp) as mock_post:
            result = search_exa("测试", api_key="test-key", search_type="invalid")

            self.assertIsNotNone(result)
            self.assertEqual(result["search_type"], "auto")
            payload = mock_post.call_args.kwargs["json"]
            self.assertEqual(payload["type"], "auto")


# ===========================================================================
# 4. 网络集成测试（可选，需配置 EXA_API_KEY）
# ===========================================================================

class TestIntegration(unittest.TestCase):
    """测试真实网络搜索（需配置 EXA_API_KEY，未配置时跳过）。"""

    def setUp(self):
        """检查 API Key 是否配置。"""
        self.api_key = os.getenv("EXA_API_KEY")
        if not self.api_key:
            self.skipTest("未配置 EXA_API_KEY，跳过网络集成测试")

    def test_real_search(self):
        """测试真实搜索返回结果。"""
        result = search_exa("黄金价格 2026年走势", api_key=self.api_key,
                            max_results=2, search_type="fast")
        self.assertIsNotNone(result)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["results"]), 0)

    def test_module_interface(self):
        """测试模块导入接口。"""
        results = exa_search("紫金矿业 最新财报", max_results=2,
                             search_type="fast")
        self.assertIsInstance(results, list)
        if results:
            self.assertIn("title", results[0])
            self.assertIn("url", results[0])


# ===========================================================================
# 测试入口
# ===========================================================================

def run_tests(test_type: str = "all") -> bool:
    """运行测试。

    Args:
        test_type: 测试类型，可选 "all"、"unit"、"integration"。

    Returns:
        测试是否全部成功。
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if test_type in ("all", "unit"):
        suite.addTests(loader.loadTestsFromTestCase(TestParseResults))
        suite.addTests(loader.loadTestsFromTestCase(TestPrintResults))
        suite.addTests(loader.loadTestsFromTestCase(TestSearchExa))
    if test_type in ("all", "integration"):
        suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    elif test_type not in ("all", "unit", "integration"):
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

    parser = argparse.ArgumentParser(description="Exa 搜索工具测试模块")
    parser.add_argument("--test", type=str, default="unit",
                        choices=["all", "unit", "integration"],
                        help="测试类型（默认: unit，不依赖网络）")

    args = parser.parse_args()

    success = run_tests(args.test)
    sys.exit(0 if success else 1)
