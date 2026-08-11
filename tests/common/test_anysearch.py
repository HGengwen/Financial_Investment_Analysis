"""
AnySearch 搜索工具测试
=====================

测试 AnySearch 工具的功能。

测试内容:
1. 限速器（RateLimiter）初始化与限流机制
2. 搜索客户端（AnySearchClient）初始化与上下文管理
3. tag 别名映射（_normalize_tag）
4. 结果格式化输出（ResultFormatter）
5. Markdown 报告导出
6. 标准化结果列表转换
7. 常量配置正确性
8. 模块导入接口（需要真实 API Key，可跳过）
9. 命令行参数解析
10. 错误处理

用法:
python tests/common/test_anysearch.py
python tests/common/test_anysearch.py --skip-live  # 跳过需要真实凭证的在线测试
"""

import argparse
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

# 添加项目根目录到 Python 路径
# 本文件位于 tests/common/ 下，需向上 3 层到达项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.common.anysearch import (
    API_BASE_URL,
    API_SEARCH_PATH,
    DEFAULT_COUNT,
    DEFAULT_FORMAT,
    DEFAULT_LANGUAGE,
    DEFAULT_QPS,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONE,
    ERROR_CODE_MAP,
    AnySearchClient,
    RateLimiter,
    ResultFormatter,
    TAG_ALIASES,
    anysearch,
    export_to_markdown,
    format_results_to_list,
    print_results,
)


# ==================== 测试用样本数据 ====================

# 模拟 API 完整成功响应
SAMPLE_SUCCESS_RESPONSE = {
    "code": 0,
    "message": "success",
    "request_id": "test-request-id-12345",
    "data": {
        "results": [
            {
                "title": "紫金矿业发布2026年上半年业绩预告",
                "url": "http://www.cnr.cn/jingji/example1.htm",
                "snippet": "紫金矿业发布2026年上半年业绩预告",
                "content": "7月9日，紫金矿业发布公告称，预计2026年半年度归属于上市公司股东的净利润约391亿元，同比增加约158亿元，增幅约68%。",
            },
            {
                "title": "紫金矿业(601899)财务摘要",
                "url": "https://vip.stock.finance.sina.com.cn/example2.phtml",
                "snippet": "紫金矿业 上海 601899",
                "content": "净资产收益率_扣除非经常损益 24.79%\n总资产净利率 6.28%",
            },
        ],
        "metadata": {
            "total_results": 2,
            "search_time_ms": 946,
        },
    },
}

# 模拟 API 业务错误响应（code != 0）
SAMPLE_BUSINESS_ERROR_RESPONSE = {
    "code": 401,
    "message": "invalid_api_key",
    "request_id": "test-error-request-id",
}

# 模拟空结果响应
SAMPLE_EMPTY_RESPONSE = {
    "code": 0,
    "message": "success",
    "request_id": "test-empty-request-id",
    "data": {
        "results": [],
        "metadata": {
            "total_results": 0,
            "search_time_ms": 120,
        },
    },
}


# ==================== 限速器测试 ====================


def test_rate_limiter_init() -> bool:
    """测试限速器初始化。"""
    print("\n" + "=" * 60)
    print("测试1: 限速器初始化")
    print("=" * 60)

    try:
        # 默认 QPS
        limiter = RateLimiter()
        assert limiter.max_qps == DEFAULT_QPS, f"默认 QPS 应为 {DEFAULT_QPS}"
        assert limiter.min_interval > 0, "最小间隔应大于 0"

        # 自定义 QPS
        limiter = RateLimiter(max_qps=10)
        assert limiter.max_qps == 10
        assert abs(limiter.min_interval - 0.1) < 0.001, \
            f"最小间隔应为 0.1 秒，实际: {limiter.min_interval}"

        # QPS=0 不限流
        limiter = RateLimiter(max_qps=0)
        assert limiter.min_interval == 0.0, "QPS=0 时空闲间隔应为 0"

        print(f"  默认 QPS: {DEFAULT_QPS}")
        print(f"  默认最小间隔: {1.0 / DEFAULT_QPS:.4f} 秒")
        print(f"  自定义 QPS=10 最小间隔: 0.1000 秒")
        print(f"  QPS=0 不限流: min_interval=0.0")

        print("\n✅ 测试通过: 限速器初始化正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_rate_limiter_wait() -> bool:
    """测试限速器等待功能。"""
    print("\n" + "=" * 60)
    print("测试2: 限速器等待功能")
    print("=" * 60)

    try:
        import time as time_module

        # QPS=10 意味着最小间隔 0.1 秒
        limiter = RateLimiter(max_qps=10)

        # 第一次请求应立即返回
        start = time_module.monotonic()
        limiter.wait()
        elapsed_first = time_module.monotonic() - start
        assert elapsed_first < 0.05, f"首次请求应立即返回，实际耗时 {elapsed_first:.3f}s"

        # 第二次请求应等待约 0.1 秒
        start = time_module.monotonic()
        limiter.wait()
        elapsed_second = time_module.monotonic() - start
        assert elapsed_second >= 0.09, \
            f"第二次请求应等待约 0.1 秒，实际等待 {elapsed_second:.3f}s"

        print(f"  QPS: 10")
        print(f"  最小间隔: {limiter.min_interval:.4f} 秒")
        print(f"  首次请求耗时: {elapsed_first * 1000:.1f} ms")
        print(f"  第二次请求等待: {elapsed_second * 1000:.1f} ms")

        print("\n✅ 测试通过: 限速器等待功能正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_rate_limiter_thread_safety() -> bool:
    """测试限速器线程安全性。"""
    print("\n" + "=" * 60)
    print("测试3: 限速器线程安全性")
    print("=" * 60)

    try:
        import threading
        import time as time_module

        limiter = RateLimiter(max_qps=100)
        results: list[float] = []

        def worker() -> None:
            """工作线程。"""
            for _ in range(5):
                limiter.wait()
                results.append(time_module.monotonic())

        # 创建多个线程
        threads = [threading.Thread(target=worker) for _ in range(3)]

        start_time = time_module.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time_module.monotonic() - start_time

        # 15 次请求，QPS=100，应该很快完成
        assert total_time < 0.5, f"15 次请求耗时 {total_time:.3f}s 过长"
        assert len(results) == 15, f"应有 15 次记录，实际: {len(results)}"

        print(f"  线程数: 3，每线程 5 次请求")
        print(f"  总请求数: {len(results)}")
        print(f"  总耗时: {total_time:.3f} 秒")

        print("\n✅ 测试通过: 限速器线程安全")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 客户端测试 ====================


def test_client_init() -> bool:
    """测试客户端初始化。"""
    print("\n" + "=" * 60)
    print("测试4: 客户端初始化")
    print("=" * 60)

    try:
        # 带 API Key
        client = AnySearchClient(api_key="sk-test-key")
        assert client.api_key == "sk-test-key", "API Key 应正确保存"
        assert client.base_url == API_BASE_URL, f"base_url 应为 {API_BASE_URL}"
        assert client.qps == DEFAULT_QPS, f"QPS 应为 {DEFAULT_QPS}"
        assert client.timeout == DEFAULT_TIMEOUT, f"timeout 应为 {DEFAULT_TIMEOUT}"
        assert "Authorization" in client.session.headers, "应设置 Authorization 头"
        assert client.session.headers["Authorization"] == "Bearer sk-test-key"
        assert client.session.headers["Content-Type"] == "application/json"
        client.close()

        # 匿名调用（无 API Key）
        client = AnySearchClient()
        assert client.api_key == "", "匿名调用时 api_key 应为空"
        assert "Authorization" not in client.session.headers, "匿名时不应设置 Authorization"
        client.close()

        # 自定义参数
        client = AnySearchClient(
            api_key="sk-test",
            base_url="https://custom.api.com/",
            qps=5,
            timeout=15,
        )
        assert client.base_url == "https://custom.api.com", "应去除尾部斜杠"
        assert client.qps == 5
        assert client.timeout == 15
        client.close()

        print(f"  API Key: sk-test-key")
        print(f"  Base URL: {API_BASE_URL}")
        print(f"  QPS: {DEFAULT_QPS}")
        print(f"  Timeout: {DEFAULT_TIMEOUT}s")
        print(f"  匿名模式: 不设置 Authorization 头")
        print(f"  自定义 base_url 去尾斜杠: https://custom.api.com")

        print("\n✅ 测试通过: 客户端初始化正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_client_context_manager() -> bool:
    """测试客户端上下文管理器。"""
    print("\n" + "=" * 60)
    print("测试5: 客户端上下文管理器")
    print("=" * 60)

    try:
        with AnySearchClient(api_key="sk-test") as client:
            assert isinstance(client, AnySearchClient)
            assert client.api_key == "sk-test"
        # 退出后 session 应已关闭（不抛异常即通过）

        print(f"  with 语句正常进入和退出")
        print(f"  退出后自动调用 close()")

        print("\n✅ 测试通过: 上下文管理器正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_normalize_tag() -> bool:
    """测试 tag 别名映射。"""
    print("\n" + "=" * 60)
    print("测试6: tag 别名映射")
    print("=" * 60)

    try:
        # 别名映射
        assert AnySearchClient._normalize_tag("code") == "code.doc"
        assert AnySearchClient._normalize_tag("legal") == "legal.case"
        assert AnySearchClient._normalize_tag("finance") == "finance.fundamental"
        assert AnySearchClient._normalize_tag("Finance") == "finance.fundamental", "应支持大小写不敏感"
        assert AnySearchClient._normalize_tag("paper") == "academic.search"

        # 完整官方 tag 原样返回
        assert AnySearchClient._normalize_tag("code.doc") == "code.doc"
        assert AnySearchClient._normalize_tag("legal.case") == "legal.case"
        assert AnySearchClient._normalize_tag("finance.quote") == "finance.quote"

        # 空值处理
        assert AnySearchClient._normalize_tag(None) is None
        assert AnySearchClient._normalize_tag("") is None

        # 未知 tag 原样返回
        assert AnySearchClient._normalize_tag("unknown.tag") == "unknown.tag"

        print(f"  别名 code → {TAG_ALIASES['code']}")
        print(f"  别名 legal → {TAG_ALIASES['legal']}")
        print(f"  别名 finance → {TAG_ALIASES['finance']}")
        print(f"  大小写不敏感: Finance → finance.fundamental")
        print(f"  完整 tag 原样返回: code.doc → code.doc")
        print(f"  空值返回 None")
        print(f"  未知 tag 原样返回")

        print("\n✅ 测试通过: tag 别名映射正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


@patch("tools.common.anysearch.requests.Session.post")
def test_search_success(mock_post: MagicMock) -> bool:
    """测试搜索成功（Mock API 调用）。"""
    print("\n" + "=" * 60)
    print("测试7: 搜索成功（Mock）")
    print("=" * 60)

    try:
        # Mock 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_SUCCESS_RESPONSE
        mock_post.return_value = mock_response

        client = AnySearchClient(api_key="sk-test", qps=100)
        result = client.search("测试查询", max_results=5)

        # 验证返回结构
        assert result["code"] == 0, "code 应为 0"
        assert result["message"] == "success"
        assert "request_id" in result
        assert "data" in result
        assert "results" in result["data"]
        assert len(result["data"]["results"]) == 2
        assert result["data"]["metadata"]["total_results"] == 2

        # 验证请求调用参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        # 第一个位置参数是 URL
        assert call_args[0][0] == f"{API_BASE_URL}{API_SEARCH_PATH}", "URL 应正确"
        # json 参数应包含 query 和 max_results
        payload = call_args[1]["json"]
        assert payload["query"] == "测试查询"
        assert payload["max_results"] == 5
        assert payload["zone"] == DEFAULT_ZONE
        assert payload["language"] == DEFAULT_LANGUAGE

        client.close()

        print(f"  请求 URL: {API_BASE_URL}{API_SEARCH_PATH}")
        print(f"  查询词: 测试查询")
        print(f"  返回结果数: {len(result['data']['results'])}")
        print(f"  请求 ID: {result['request_id']}")

        print("\n✅ 测试通过: 搜索成功（Mock）")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


@patch("tools.common.anysearch.requests.Session.post")
def test_search_with_tag(mock_post: MagicMock) -> bool:
    """测试带 tag 的搜索（验证别名映射进入 payload）。"""
    print("\n" + "=" * 60)
    print("测试8: 带 tag 的搜索（Mock）")
    print("=" * 60)

    try:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_SUCCESS_RESPONSE
        mock_post.return_value = mock_response

        client = AnySearchClient(api_key="sk-test", qps=100)
        client.search("FastAPI 教程", tag="code", params={"library": "fastapi"})

        # 验证 payload 中的 tag 已被映射为官方 tag
        payload = mock_post.call_args[1]["json"]
        assert payload["tag"] == "code.doc", f"tag 应映射为 code.doc，实际: {payload['tag']}"
        assert payload["params"] == {"library": "fastapi"}

        client.close()

        print(f"  输入 tag: code（别名）")
        print(f"  映射后 tag: {payload['tag']}")
        print(f"  扩展参数: {payload['params']}")

        print("\n✅ 测试通过: 带 tag 的搜索正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


@patch("tools.common.anysearch.requests.Session.post")
def test_search_simple(mock_post: MagicMock) -> bool:
    """测试简化搜索返回标准化列表（Mock）。"""
    print("\n" + "=" * 60)
    print("测试9: 简化搜索返回标准化列表（Mock）")
    print("=" * 60)

    try:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_SUCCESS_RESPONSE
        mock_post.return_value = mock_response

        client = AnySearchClient(api_key="sk-test", qps=100)
        results = client.search_simple("测试查询")

        assert isinstance(results, list), "结果应为列表"
        assert len(results) == 2, f"应有 2 条结果，实际: {len(results)}"

        # 验证字段
        first = results[0]
        assert "title" in first
        assert "url" in first
        assert "snippet" in first
        assert "content" in first
        assert first["title"] == "紫金矿业发布2026年上半年业绩预告"
        assert first["url"] == "http://www.cnr.cn/jingji/example1.htm"

        client.close()

        for idx, r in enumerate(results, 1):
            print(f"\n  【结果 {idx}】")
            print(f"  标题: {r['title']}")
            print(f"  链接: {r['url']}")

        print("\n✅ 测试通过: 简化搜索正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


@patch("tools.common.anysearch.requests.Session.post")
def test_search_business_error(mock_post: MagicMock) -> bool:
    """测试业务错误处理（code != 0）。"""
    print("\n" + "=" * 60)
    print("测试10: 业务错误处理（Mock）")
    print("=" * 60)

    try:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_BUSINESS_ERROR_RESPONSE
        mock_post.return_value = mock_response

        client = AnySearchClient(api_key="sk-test", qps=100)

        try:
            client.search("测试查询")
            assert False, "应抛出 ValueError"
        except ValueError as e:
            assert "invalid_api_key" in str(e), f"错误信息应包含 invalid_api_key，实际: {e}"
            print(f"  预期的错误: {e}")

        client.close()

        print("\n✅ 测试通过: 业务错误处理正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


@patch("tools.common.anysearch.requests.Session.post")
def test_search_http_error(mock_post: MagicMock) -> bool:
    """测试 HTTP 错误处理（状态码非 200）。"""
    print("\n" + "=" * 60)
    print("测试11: HTTP 错误处理（Mock）")
    print("=" * 60)

    try:
        # 模拟 429 错误
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "rate_limit_exceeded"}
        mock_post.return_value = mock_response

        client = AnySearchClient(api_key="sk-test", qps=100)

        try:
            client.search("测试查询")
            assert False, "应抛出 ValueError"
        except ValueError as e:
            assert "429" in str(e), f"错误信息应包含 429，实际: {e}"
            assert "rate_limit_exceeded" in str(e), \
                f"错误信息应包含 error_id，实际: {e}"
            print(f"  预期的错误: {e}")

        client.close()

        print("\n✅ 测试通过: HTTP 错误处理正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 格式化器测试 ====================


def test_formatter_success() -> bool:
    """测试成功响应的格式化输出。"""
    print("\n" + "=" * 60)
    print("测试12: 成功响应格式化输出")
    print("=" * 60)

    try:
        formatter = ResultFormatter(max_snippet_length=200, max_content_length=300)
        output = formatter.format_search_results(SAMPLE_SUCCESS_RESPONSE)

        assert isinstance(output, str), "输出应为字符串"
        assert "AnySearch 搜索结果" in output, "应包含标题"
        assert "结果总数: 2" in output, "应包含结果总数"
        assert "搜索耗时: 946 ms" in output, "应包含搜索耗时"
        assert "test-request-id-12345" in output, "应包含请求 ID"
        assert "紫金矿业发布2026年上半年业绩预告" in output, "应包含第一条结果标题"
        assert "[摘要]" in output, "应包含摘要标记"
        assert "[正文]" in output, "应包含正文标记"

        print(output[:500] + "\n... (输出截断)")

        print("\n✅ 测试通过: 成功响应格式化正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_formatter_truncate() -> bool:
    """测试文本截断功能。"""
    print("\n" + "=" * 60)
    print("测试13: 文本截断功能")
    print("=" * 60)

    try:
        # 短文本不截断
        short_text = "短文本"
        assert ResultFormatter._truncate(short_text, 100) == "短文本"

        # 长文本截断并添加省略号
        long_text = "A" * 150
        result = ResultFormatter._truncate(long_text, 100)
        assert len(result) == 103, f"截断后长度应为 103（100+省略号），实际: {len(result)}"
        assert result.endswith("..."), "应以省略号结尾"

        # 空文本返回 "无"
        assert ResultFormatter._truncate("", 100) == "无"
        assert ResultFormatter._truncate(None, 100) == "无"

        # 刚好等于最大长度不截断
        exact_text = "B" * 100
        assert ResultFormatter._truncate(exact_text, 100) == exact_text

        print(f"  短文本: {ResultFormatter._truncate(short_text, 100)}")
        print(f"  长文本截断后长度: {len(result)}")
        print(f"  空文本: {ResultFormatter._truncate('', 100)}")
        print(f"  等于最大长度: 不截断")

        print("\n✅ 测试通过: 文本截断正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_formatter_empty() -> bool:
    """测试空结果格式化。"""
    print("\n" + "=" * 60)
    print("测试14: 空结果格式化")
    print("=" * 60)

    try:
        formatter = ResultFormatter()
        output = formatter.format_search_results(SAMPLE_EMPTY_RESPONSE)

        assert "结果总数: 0" in output, "应显示结果数为 0"
        assert "未找到匹配的搜索结果" in output, "应提示未找到结果"

        print(output)

        print("\n✅ 测试通过: 空结果格式化正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== Markdown 导出测试 ====================


def test_export_markdown() -> bool:
    """测试 Markdown 报告导出。"""
    print("\n" + "=" * 60)
    print("测试15: Markdown 报告导出")
    print("=" * 60)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, "test_report.md")
            saved_path = export_to_markdown(
                SAMPLE_SUCCESS_RESPONSE, tmp_path, query="紫金矿业 财报"
            )

            assert saved_path == tmp_path, "返回的保存路径应与输入一致"
            assert os.path.exists(tmp_path), "文件应已创建"

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "# AnySearch 搜索报告" in content, "应包含标题"
            assert "紫金矿业 财报" in content, "应包含搜索词"
            assert "结果数**: 2" in content, "应包含结果数"
            assert "紫金矿业发布2026年上半年业绩预告" in content, "应包含结果标题"
            assert "http://www.cnr.cn" in content, "应包含链接"
            assert "---" in content, "应包含分隔线"

            print(f"  报告保存路径: {saved_path}")
            print(f"  报告大小: {os.path.getsize(tmp_path)} 字节")
            print("\n  报告预览（前 300 字符）:")
            print("  " + content[:300])

        print("\n✅ 测试通过: Markdown 报告导出正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_export_markdown_auto_mkdir() -> bool:
    """测试 Markdown 导出时自动创建目录。"""
    print("\n" + "=" * 60)
    print("测试16: Markdown 导出自动创建目录")
    print("=" * 60)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 嵌套目录不存在
            nested_path = os.path.join(tmp_dir, "sub1", "sub2", "report.md")
            saved_path = export_to_markdown(SAMPLE_SUCCESS_RESPONSE, nested_path)

            assert os.path.exists(saved_path), "文件应已创建（含嵌套目录）"

            print(f"  嵌套路径: {nested_path}")
            print(f"  自动创建目录: 成功")

        print("\n✅ 测试通过: 自动创建目录正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 标准化结果转换测试 ====================


def test_format_results_to_list() -> bool:
    """测试 API 响应转换为标准化结果列表。"""
    print("\n" + "=" * 60)
    print("测试17: 标准化结果列表转换")
    print("=" * 60)

    try:
        results = format_results_to_list(SAMPLE_SUCCESS_RESPONSE)

        assert isinstance(results, list), "结果应为列表"
        assert len(results) == 2, f"应有 2 条结果，实际: {len(results)}"

        # 验证第一条结果字段
        first = results[0]
        assert "title" in first
        assert "url" in first
        assert "snippet" in first
        assert "content" in first
        assert first["title"] == "紫金矿业发布2026年上半年业绩预告"
        assert first["url"] == "http://www.cnr.cn/jingji/example1.htm"

        # 测试空结果
        empty_results = format_results_to_list(SAMPLE_EMPTY_RESPONSE)
        assert empty_results == [], "空响应应返回空列表"

        # 测试 data 为 null
        null_results = format_results_to_list({"data": None})
        assert null_results == [], "data 为 null 时应返回空列表"

        # 测试 data 缺失
        missing_results = format_results_to_list({})
        assert missing_results == [], "data 缺失时应返回空列表"

        for idx, r in enumerate(results, 1):
            print(f"\n  【结果 {idx}】")
            print(f"  标题: {r['title']}")
            print(f"  链接: {r['url']}")

        print("\n✅ 测试通过: 标准化结果列表转换正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 打印结果测试 ====================


def test_print_results_text() -> bool:
    """测试文本格式打印结果。"""
    print("\n" + "=" * 60)
    print("测试18: 文本格式打印结果")
    print("=" * 60)

    try:
        print("\n  --- 文本格式输出预览 ---")
        print_results(SAMPLE_SUCCESS_RESPONSE, output_json=False)
        print("  --- 预览结束 ---")

        print("\n✅ 测试通过: 文本格式打印正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_print_results_json() -> bool:
    """测试 JSON 格式打印结果。"""
    print("\n" + "=" * 60)
    print("测试19: JSON 格式打印结果")
    print("=" * 60)

    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_results(SAMPLE_SUCCESS_RESPONSE, output_json=True)
        json_output = buffer.getvalue()

        # 验证输出是有效 JSON
        parsed = json.loads(json_output)
        assert isinstance(parsed, dict), "JSON 输出应为字典"
        assert "code" in parsed
        assert "data" in parsed

        print(f"  JSON 输出长度: {len(json_output)} 字符")
        print(f"  顶层字段: {list(parsed.keys())}")
        print(f"  结果数: {parsed['data']['metadata']['total_results']}")

        print("\n✅ 测试通过: JSON 格式打印正常")
        return True

    except json.JSONDecodeError as e:
        print(f"\n❌ 测试失败: JSON 解析错误 - {e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 常量配置测试 ====================


def test_constants() -> bool:
    """测试常量配置正确性。"""
    print("\n" + "=" * 60)
    print("测试20: 常量配置")
    print("=" * 60)

    try:
        # API 端点
        assert API_BASE_URL == "https://api.anysearch.com"
        assert API_SEARCH_PATH == "/v1/search"

        # 默认值
        assert DEFAULT_QPS == 20
        assert DEFAULT_COUNT == 10
        assert DEFAULT_ZONE == "cn"
        assert DEFAULT_LANGUAGE == "zh-CN"
        assert DEFAULT_FORMAT == "json"
        assert DEFAULT_TIMEOUT == 30

        # tag 别名映射关键项
        assert TAG_ALIASES["code"] == "code.doc"
        assert TAG_ALIASES["legal"] == "legal.case"
        assert TAG_ALIASES["finance"] == "finance.fundamental"
        assert TAG_ALIASES["general"] == "general.general"
        assert TAG_ALIASES["github"] == "code.snippet"

        # 错误码映射
        assert 402 in ERROR_CODE_MAP
        assert 401 in ERROR_CODE_MAP
        assert 429 in ERROR_CODE_MAP
        assert "daily_free_quota_exhausted" in ERROR_CODE_MAP[402]
        assert "invalid_api_key" in ERROR_CODE_MAP[401]
        assert "rate_limit_exceeded" in ERROR_CODE_MAP[429]

        print(f"  API_BASE_URL: {API_BASE_URL}")
        print(f"  API_SEARCH_PATH: {API_SEARCH_PATH}")
        print(f"  DEFAULT_QPS: {DEFAULT_QPS}")
        print(f"  DEFAULT_COUNT: {DEFAULT_COUNT}")
        print(f"  DEFAULT_ZONE: {DEFAULT_ZONE}")
        print(f"  DEFAULT_LANGUAGE: {DEFAULT_LANGUAGE}")
        print(f"  DEFAULT_FORMAT: {DEFAULT_FORMAT}")
        print(f"  DEFAULT_TIMEOUT: {DEFAULT_TIMEOUT}")
        print(f"  TAG_ALIASES 数量: {len(TAG_ALIASES)}")
        print(f"  ERROR_CODE_MAP 数量: {len(ERROR_CODE_MAP)}")

        print("\n✅ 测试通过: 常量配置正确")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 模块导入接口测试（需要真实凭证） ====================


def test_module_interface_live(skip_live: bool) -> bool:
    """测试模块导入接口（在线搜索，需要真实 API Key）。

    Args:
        skip_live: 是否跳过在线测试。
    """
    print("\n" + "=" * 60)
    print("测试21: 模块导入接口（在线搜索）")
    print("=" * 60)

    if skip_live:
        print("\n  [跳过] 已指定 --skip-live 参数")
        print("\n✅ 测试通过: 已跳过在线测试")
        return True

    api_key = os.getenv("ANYSEARCH_API_KEY", "")
    if not api_key:
        print("\n  [跳过] 未配置 ANYSEARCH_API_KEY 环境变量")
        print("  设置 .env 文件中的 ANYSEARCH_API_KEY 后可运行在线测试")
        print("  （匿名模式也可调用，但额度极少）")
        print("\n✅ 测试通过: 已跳过未配置凭证的在线测试")
        return True

    try:
        print(f"\n  使用 API Key: {api_key[:8]}*** 进行在线搜索")
        results = anysearch("黄金价格", max_results=3)

        assert isinstance(results, list), "结果应为列表"
        assert len(results) <= 3, f"结果数应 <= 3，实际: {len(results)}"

        for idx, r in enumerate(results, 1):
            print(f"\n  【结果 {idx}】")
            print(f"  标题: {r.get('title', '(无)')}")
            print(f"  链接: {r.get('url', '(无)')}")
            snippet = r.get("snippet", "")
            if snippet:
                print(f"  摘要: {snippet[:100]}...")

        print("\n✅ 测试通过: 在线搜索正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 命令行入口测试 ====================


def test_cli_help() -> bool:
    """测试命令行帮助信息。"""
    print("\n" + "=" * 60)
    print("测试22: 命令行帮助信息")
    print("=" * 60)

    try:
        # 通过子进程调用 --help，验证不抛异常
        import subprocess

        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "common" / "anysearch.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"--help 应返回 0，实际: {result.returncode}"
        assert "AnySearch" in result.stdout, "应包含工具名称"
        assert "搜索关键词" in result.stdout, "应包含参数说明"
        assert "--tag" in result.stdout, "应包含 --tag 参数"
        assert "--export" in result.stdout, "应包含 --export 参数"
        assert "示例" in result.stdout, "应包含示例"

        print(f"  返回码: {result.returncode}")
        print(f"  输出长度: {len(result.stdout)} 字符")
        print(f"  包含关键信息: AnySearch / 搜索关键词 / --tag / --export / 示例")

        print("\n✅ 测试通过: 命令行帮助信息正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 主测试运行器 ====================


def run_tests(skip_live: bool = False) -> int:
    """运行所有测试。

    Args:
        skip_live: 是否跳过需要真实凭证的在线测试。

    Returns:
        退出码: 0 表示全部通过，1 表示部分失败。
    """
    print("\n" + "=" * 60)
    print("AnySearch 搜索工具测试")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"跳过在线测试: {skip_live}")

    tests = [
        ("限速器初始化", test_rate_limiter_init),
        ("限速器等待功能", test_rate_limiter_wait),
        ("限速器线程安全", test_rate_limiter_thread_safety),
        ("客户端初始化", test_client_init),
        ("客户端上下文管理器", test_client_context_manager),
        ("tag 别名映射", test_normalize_tag),
        ("搜索成功（Mock）", test_search_success),
        ("带 tag 搜索（Mock）", test_search_with_tag),
        ("简化搜索（Mock）", test_search_simple),
        ("业务错误处理（Mock）", test_search_business_error),
        ("HTTP 错误处理（Mock）", test_search_http_error),
        ("成功响应格式化", test_formatter_success),
        ("文本截断功能", test_formatter_truncate),
        ("空结果格式化", test_formatter_empty),
        ("Markdown 报告导出", test_export_markdown),
        ("Markdown 自动创建目录", test_export_markdown_auto_mkdir),
        ("标准化结果列表转换", test_format_results_to_list),
        ("文本格式打印", test_print_results_text),
        ("JSON 格式打印", test_print_results_json),
        ("常量配置", test_constants),
        ("模块导入接口（在线）", lambda: test_module_interface_live(skip_live)),
        ("命令行帮助信息", test_cli_help),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试异常: {test_name} - {e}")
            results.append((test_name, False))

    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AnySearch 搜索工具测试")
    parser.add_argument("--skip-live", action="store_true",
                        help="跳过需要真实凭证的在线测试")
    args = parser.parse_args()

    try:
        exit_code = run_tests(skip_live=args.skip_live)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试异常退出: {e}")
        sys.exit(1)
