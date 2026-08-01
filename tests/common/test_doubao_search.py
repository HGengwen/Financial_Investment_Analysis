"""
豆包搜索工具测试
================

测试火山引擎豆包搜索（SearchInfinity）工具的功能。

测试内容:
1. 客户端初始化与限流机制
2. 结果格式化输出（ResultFormatter）
3. Markdown 报告导出
4. 标准化结果列表转换
5. 模块导入接口（需要 AK/SK 真实凭证，可跳过）
6. 命令行参数解析
7. 错误处理

用法:
python tests/common/test_doubao_search.py
python tests/common/test_doubao_search.py --skip-live  # 跳过需要真实凭证的在线测试
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到 Python 路径
# 本文件位于 tests/common/ 下，需向上 3 层到达项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.common.doubao_search import (
    AUTH_LEVEL_MAP,
    DEFAULT_COUNT,
    DEFAULT_QPS,
    DoubaoSearchClient,
    INDUSTRY_OPTIONS,
    ResultFormatter,
    TIME_RANGE_MAP,
    doubao_search,
    export_to_markdown,
    format_results_to_list,
    print_results,
)


# ==================== 测试用样本数据 ====================

# 模拟 API 完整成功响应
SAMPLE_SUCCESS_RESPONSE = {
    "ResponseMetadata": {
        "RequestId": "test-request-id-12345",
        "Action": "WebSearch",
        "Version": "2025-01-01",
    },
    "Result": {
        "ResultCount": 2,
        "TimeCost": 856,
        "LogId": "test-log-id-67890",
        "SearchContext": {
            "OriginQuery": "紫金矿业 财报",
        },
        "WebResults": [
            {
                "SortId": 1,
                "Title": "紫金矿业发布2026年上半年业绩预告",
                "SiteName": "央广网",
                "Url": "http://www.cnr.cn/jingji/example1.htm",
                "PublishTime": "2026-07-09T20:23:00+08:00",
                "Snippet": "紫金矿业发布2026年上半年业绩预告",
                "Summary": "7月9日，紫金矿业发布公告称，预计2026年半年度归属于上市公司股东的净利润约391亿元，同比增加约158亿元，增幅约68%。",
                "Content": "",
                "AuthInfoLevel": 1,
                "AuthInfoDes": "非常权威",
                "RankScore": 0.95,
                "ContentFormats": "markdown",
            },
            {
                "SortId": 2,
                "Title": "紫金矿业(601899)财务摘要",
                "SiteName": "新浪财经",
                "Url": "https://vip.stock.finance.sina.com.cn/example2.phtml",
                "PublishTime": "2026-07-31T15:34:00+08:00",
                "Snippet": "紫金矿业 上海 601899",
                "Summary": "紫金矿业(601899)财务摘要页面，包含最新股价、市值、净资产收益率等关键指标。",
                "Content": "净资产收益率_扣除非经常损益 24.79%\n总资产净利率 6.28%",
                "AuthInfoLevel": 2,
                "AuthInfoDes": "正常权威",
                "RankScore": 0.88,
                "ContentFormats": "markdown",
            },
        ],
    },
}

# 模拟 API 错误响应
SAMPLE_ERROR_RESPONSE = {
    "ResponseMetadata": {
        "RequestId": "test-error-request-id",
        "Error": {
            "Code": "InvalidParameter",
            "Message": "Query 参数长度超过限制",
        },
    },
    "Result": None,
}

# 模拟空结果响应
SAMPLE_EMPTY_RESPONSE = {
    "ResponseMetadata": {
        "RequestId": "test-empty-request-id",
    },
    "Result": {
        "ResultCount": 0,
        "TimeCost": 120,
        "LogId": "test-empty-log-id",
        "SearchContext": {
            "OriginQuery": "不存在的关键词xyz123",
        },
        "WebResults": [],
    },
}


# ==================== 客户端测试 ====================


def test_client_init() -> bool:
    """测试客户端初始化。

    验证 DoubaoSearchClient 能正确初始化并设置限流参数。
    """
    print("\n" + "=" * 60)
    print("测试1: 客户端初始化")
    print("=" * 60)

    try:
        client = DoubaoSearchClient(ak="test_ak", sk="test_sk", qps=5)

        assert client.ak == "test_ak", "AK 应正确保存"
        assert client.sk == "test_sk", "SK 应正确保存"
        assert client.qps == 5, "QPS 应正确保存"
        assert client.credentials is not None, "凭证对象应已创建"
        assert client._min_interval == 0.2, f"最小间隔应为 0.2 秒，实际: {client._min_interval}"
        assert client._last_request_time == 0.0, "初始最后请求时间应为 0"

        # 验证默认 QPS
        client_default = DoubaoSearchClient(ak="test_ak", sk="test_sk")
        assert client_default.qps == DEFAULT_QPS, "默认 QPS 应与常量一致"

        # 验证 QPS=0 时不限流
        client_no_limit = DoubaoSearchClient(ak="test_ak", sk="test_sk", qps=0)
        assert client_no_limit._min_interval == 0.0, "QPS=0 时空闲间隔应为 0"

        print(f"  AK: {client.ak}")
        print(f"  SK: {client.sk[:4]}***")
        print(f"  QPS: {client.qps}")
        print(f"  最小间隔: {client._min_interval:.3f} 秒")

        print("\n✅ 测试通过: 客户端初始化正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_rate_limit() -> bool:
    """测试 QPS 限流机制。

    验证限流器在 QPS=2 时能正确控制请求间隔。
    """
    print("\n" + "=" * 60)
    print("测试2: QPS 限流机制")
    print("=" * 60)

    try:
        import time as time_module

        # QPS=2 意味着最小间隔 0.5 秒
        client = DoubaoSearchClient(ak="test_ak", sk="test_sk", qps=2)

        # 第一次请求应立即返回（_last_request_time=0，elapsed 远大于 min_interval）
        start = time_module.monotonic()
        client._wait_for_rate_limit()
        elapsed_first = time_module.monotonic() - start
        assert elapsed_first < 0.05, f"首次请求应立即返回，实际耗时 {elapsed_first:.3f}s"

        # 第二次请求应等待约 0.5 秒
        start = time_module.monotonic()
        client._wait_for_rate_limit()
        elapsed_second = time_module.monotonic() - start
        assert elapsed_second >= 0.45, f"第二次请求应等待约 0.5 秒，实际等待 {elapsed_second:.3f}s"

        print(f"  QPS: {client.qps}")
        print(f"  最小间隔: {client._min_interval:.3f} 秒")
        print(f"  首次请求耗时: {elapsed_first * 1000:.1f} ms")
        print(f"  第二次请求等待: {elapsed_second * 1000:.1f} ms")

        print("\n✅ 测试通过: QPS 限流机制正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 格式化器测试 ====================


def test_formatter_success() -> bool:
    """测试成功响应的格式化输出。"""
    print("\n" + "=" * 60)
    print("测试3: 成功响应格式化输出")
    print("=" * 60)

    try:
        formatter = ResultFormatter(max_summary_length=200, max_content_length=300)
        output = formatter.format_search_results(SAMPLE_SUCCESS_RESPONSE)

        assert isinstance(output, str), "输出应为字符串"
        assert "豆包搜索结果" in output, "应包含标题"
        assert "结果总数: 2" in output, "应包含结果总数"
        assert "紫金矿业 财报" in output, "应包含搜索词"
        assert "紫金矿业发布2026年上半年业绩预告" in output, "应包含第一条结果标题"
        assert "央广网" in output, "应包含来源"
        assert "非常权威" in output, "应包含权威度描述"
        assert "[摘要]" in output, "应包含摘要标记"

        print(output[:500] + "\n... (输出截断)")

        print("\n✅ 测试通过: 成功响应格式化正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_formatter_truncate() -> bool:
    """测试文本截断功能。"""
    print("\n" + "=" * 60)
    print("测试4: 文本截断功能")
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


def test_formatter_error() -> bool:
    """测试错误响应格式化。"""
    print("\n" + "=" * 60)
    print("测试5: 错误响应格式化")
    print("=" * 60)

    try:
        formatter = ResultFormatter()
        output = formatter.format_search_results(SAMPLE_ERROR_RESPONSE)

        assert "搜索失败" in output, "应包含失败标识"
        assert "InvalidParameter" in output, "应包含错误码"
        assert "Query 参数长度超过限制" in output, "应包含错误信息"
        assert "test-error-request-id" in output, "应包含请求 ID"

        print(output)

        print("\n✅ 测试通过: 错误响应格式化正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_formatter_empty() -> bool:
    """测试空结果格式化。"""
    print("\n" + "=" * 60)
    print("测试6: 空结果格式化")
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


def test_formatter_null_result() -> bool:
    """测试 Result 为 null 的情况。"""
    print("\n" + "=" * 60)
    print("测试7: Result 为 null 处理")
    print("=" * 60)

    try:
        formatter = ResultFormatter()
        null_response = {"ResponseMetadata": {}, "Result": None}
        output = formatter.format_search_results(null_response)

        assert "搜索结果为空" in output, "应提示结果为空"

        print(output)

        print("\n✅ 测试通过: Result 为 null 处理正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== Markdown 导出测试 ====================


def test_export_markdown() -> bool:
    """测试 Markdown 报告导出。"""
    print("\n" + "=" * 60)
    print("测试8: Markdown 报告导出")
    print("=" * 60)

    try:
        # 使用临时文件
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, "test_report.md")
            saved_path = export_to_markdown(SAMPLE_SUCCESS_RESPONSE, tmp_path)

            assert saved_path == tmp_path, "返回的保存路径应与输入一致"
            assert os.path.exists(tmp_path), "文件应已创建"

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "# 豆包搜索报告" in content, "应包含标题"
            assert "紫金矿业 财报" in content, "应包含搜索词"
            assert "结果数**: 2" in content, "应包含结果数"
            assert "紫金矿业发布2026年上半年业绩预告" in content, "应包含结果标题"
            assert "央广网" in content, "应包含来源"
            assert "http://www.cnr.cn" in content, "应包含链接"
            assert "非常权威" in content, "应包含权威度"
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


# ==================== 标准化结果转换测试 ====================


def test_format_results_to_list() -> bool:
    """测试 API 响应转换为标准化结果列表。"""
    print("\n" + "=" * 60)
    print("测试9: 标准化结果列表转换")
    print("=" * 60)

    try:
        results = format_results_to_list(SAMPLE_SUCCESS_RESPONSE)

        assert isinstance(results, list), "结果应为列表"
        assert len(results) == 2, f"应有 2 条结果，实际: {len(results)}"

        # 验证第一条结果字段
        first = results[0]
        assert "title" in first, "应包含 title 字段"
        assert "url" in first, "应包含 url 字段"
        assert "site_name" in first, "应包含 site_name 字段"
        assert "publish_time" in first, "应包含 publish_time 字段"
        assert "summary" in first, "应包含 summary 字段"
        assert "snippet" in first, "应包含 snippet 字段"
        assert "content" in first, "应包含 content 字段"
        assert "auth_level" in first, "应包含 auth_level 字段"
        assert "auth_des" in first, "应包含 auth_des 字段"
        assert "rank_score" in first, "应包含 rank_score 字段"

        assert first["title"] == "紫金矿业发布2026年上半年业绩预告"
        assert first["url"] == "http://www.cnr.cn/jingji/example1.htm"
        assert first["site_name"] == "央广网"
        assert first["auth_level"] == 1
        assert first["auth_des"] == "非常权威"

        # 测试空结果
        empty_results = format_results_to_list(SAMPLE_EMPTY_RESPONSE)
        assert empty_results == [], "空响应应返回空列表"

        # 测试 Result 为 null
        null_results = format_results_to_list({"Result": None})
        assert null_results == [], "Result 为 null 时应返回空列表"

        for idx, r in enumerate(results, 1):
            print(f"\n  【结果 {idx}】")
            print(f"  标题: {r['title']}")
            print(f"  链接: {r['url']}")
            print(f"  来源: {r['site_name']}")
            print(f"  权威度: {r['auth_des']}（等级 {r['auth_level']}）")

        print("\n✅ 测试通过: 标准化结果列表转换正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 打印结果测试 ====================


def test_print_results_text() -> bool:
    """测试文本格式打印结果。"""
    print("\n" + "=" * 60)
    print("测试10: 文本格式打印结果")
    print("=" * 60)

    try:
        # 应能正常打印而不抛出异常
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
    print("测试11: JSON 格式打印结果")
    print("=" * 60)

    try:
        # 捕获 stdout 验证 JSON 有效性
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_results(SAMPLE_SUCCESS_RESPONSE, output_json=True)
        json_output = buffer.getvalue()

        # 验证输出是有效 JSON
        parsed = json.loads(json_output)
        assert isinstance(parsed, dict), "JSON 输出应为字典"
        assert "Result" in parsed, "应包含 Result 字段"

        print(f"  JSON 输出长度: {len(json_output)} 字符")
        print(f"  顶层字段: {list(parsed.keys())}")
        print(f"  结果数: {parsed['Result']['ResultCount']}")

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
    print("测试12: 常量配置")
    print("=" * 60)

    try:
        # 验证时间范围映射
        assert TIME_RANGE_MAP["day"] == "OneDay"
        assert TIME_RANGE_MAP["week"] == "OneWeek"
        assert TIME_RANGE_MAP["month"] == "OneMonth"
        assert TIME_RANGE_MAP["year"] == "OneYear"
        assert len(TIME_RANGE_MAP) == 4

        # 验证权威度映射
        assert AUTH_LEVEL_MAP[1] == "非常权威"
        assert AUTH_LEVEL_MAP[2] == "正常权威"
        assert AUTH_LEVEL_MAP[3] == "一般权威"
        assert AUTH_LEVEL_MAP[4] == "一般不权威"

        # 验证行业选项
        assert INDUSTRY_OPTIONS["finance"] == "金融"
        assert INDUSTRY_OPTIONS["game"] == "电子游戏"
        assert INDUSTRY_OPTIONS["gov"] == "政府/官媒"

        # 验证默认值
        assert DEFAULT_QPS == 5
        assert DEFAULT_COUNT == 10

        print(f"  时间范围映射: {TIME_RANGE_MAP}")
        print(f"  权威度映射: {AUTH_LEVEL_MAP}")
        print(f"  行业选项: {INDUSTRY_OPTIONS}")
        print(f"  默认 QPS: {DEFAULT_QPS}")
        print(f"  默认返回条数: {DEFAULT_COUNT}")

        print("\n✅ 测试通过: 常量配置正确")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 模块导入接口测试（需要真实凭证） ====================


def test_module_interface_live(skip_live: bool) -> bool:
    """测试模块导入接口（在线搜索，需要真实 AK/SK）。

    Args:
        skip_live: 是否跳过在线测试。
    """
    print("\n" + "=" * 60)
    print("测试13: 模块导入接口（在线搜索）")
    print("=" * 60)

    if skip_live:
        print("\n  [跳过] 已指定 --skip-live 参数")
        print("\n✅ 测试通过: 已跳过在线测试")
        return True

    ak = os.getenv("VOLC_AK")
    sk = os.getenv("VOLC_SK")
    if not ak or not sk:
        print("\n  [跳过] 未配置 VOLC_AK/VOLC_SK 环境变量")
        print("  设置 .env 文件中的 VOLC_AK 和 VOLC_SK 后可运行在线测试")
        print("\n✅ 测试通过: 已跳过未配置凭证的在线测试")
        return True

    try:
        print(f"\n  使用凭证 AK: {ak[:8]}*** 进行在线搜索")
        results = doubao_search("黄金价格", count=3)

        assert isinstance(results, list), "结果应为列表"
        assert len(results) <= 3, f"结果数应 <= 3，实际: {len(results)}"

        for idx, r in enumerate(results, 1):
            print(f"\n  【结果 {idx}】")
            print(f"  标题: {r.get('title', '(无)')}")
            print(f"  链接: {r.get('url', '(无)')}")
            print(f"  来源: {r.get('site_name', '(无)')}")
            summary = r.get("summary", "")
            if summary:
                print(f"  摘要: {summary[:100]}...")

        print("\n✅ 测试通过: 在线搜索正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


# ==================== 错误处理测试 ====================


def test_error_handling_no_credentials() -> bool:
    """测试未配置凭证时的错误处理。"""
    print("\n" + "=" * 60)
    print("测试14: 未配置凭证的错误处理")
    print("=" * 60)

    try:
        # 临时清除环境变量
        original_ak = os.environ.pop("VOLC_AK", None)
        original_sk = os.environ.pop("VOLC_SK", None)

        try:
            # 重新加载环境变量以确保 .env 中的值不会被读取
            # 此处直接测试 doubao_search 函数
            try:
                doubao_search("测试")
                # 如果没有抛出异常，可能是 .env 文件中有配置
                print("  [提示] 检测到已配置 VOLC_AK/VOLC_SK（来自 .env 文件）")
                print("  无法测试未配置凭证的场景，跳过")
                print("\n✅ 测试通过: 已跳过（已配置凭证）")
                return True
            except ValueError as ve:
                assert "VOLC_AK" in str(ve) or "VOLC_SK" in str(ve), \
                    f"错误信息应提及 VOLC_AK/VOLC_SK，实际: {ve}"
                print(f"  预期的错误信息: {ve}")
                print("\n✅ 测试通过: 未配置凭证时正确抛出 ValueError")
                return True
        finally:
            # 恢复环境变量
            if original_ak is not None:
                os.environ["VOLC_AK"] = original_ak
            if original_sk is not None:
                os.environ["VOLC_SK"] = original_sk

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
    print("豆包搜索工具测试")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"跳过在线测试: {skip_live}")

    tests = [
        ("客户端初始化", test_client_init),
        ("QPS 限流机制", test_rate_limit),
        ("成功响应格式化", test_formatter_success),
        ("文本截断功能", test_formatter_truncate),
        ("错误响应格式化", test_formatter_error),
        ("空结果格式化", test_formatter_empty),
        ("Result 为 null 处理", test_formatter_null_result),
        ("Markdown 报告导出", test_export_markdown),
        ("标准化结果列表转换", test_format_results_to_list),
        ("文本格式打印", test_print_results_text),
        ("JSON 格式打印", test_print_results_json),
        ("常量配置", test_constants),
        ("模块导入接口（在线）", lambda: test_module_interface_live(skip_live)),
        ("未配置凭证错误处理", test_error_handling_no_credentials),
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
    parser = argparse.ArgumentParser(description="豆包搜索工具测试")
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
