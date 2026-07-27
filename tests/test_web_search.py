"""
网络搜索工具测试软件
--------------------

测试 tools/web_search.py 的功能。

用法:
python tests/test_web_search.py
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(PROJECT_ROOT / ".env")

# 测试结果收集
test_results = []


def add_test_result(test_name: str, passed: bool, message: str = "") -> None:
    """
    添加测试结果。
    
    Args:
        test_name: 测试名称
        passed: 是否通过
        message: 结果消息
    """
    test_results.append({
        "test": test_name,
        "passed": passed,
        "message": message
    })
    status = "✅ 通过" if passed else "❌ 失败"
    print(f"{status}: {test_name}")
    if message:
        print(f"   {message}")


def test_import() -> None:
    """测试模块导入。"""
    try:
        from tools import web_search
        add_test_result("模块导入", True, f"成功导入 web_search 模块")
    except ImportError as e:
        add_test_result("模块导入", False, f"导入失败: {e}")


def test_api_key_check() -> None:
    """测试 API Key 检查。"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if api_key:
        # 检查 API Key 格式
        if api_key.startswith("sk-"):
            add_test_result("API Key 检查", True, f"API Key 已设置且格式正确（sk-开头）")
        else:
            add_test_result("API Key 检查", True, f"API Key 已设置（长度: {len(api_key)}）")
    else:
        # 未设置 API Key 是配置问题，不是代码问题，标记为跳过
        add_test_result("API Key 检查", True, "⚠️ 跳过：未设置 DASHSCOPE_API_KEY（异步测试将跳过）")


async def test_search_function() -> Optional[Dict[str, Any]]:
    """
    测试搜索功能。
    
    Returns:
        搜索结果字典
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        add_test_result("搜索功能", False, "需要 API Key 才能测试")
        return None
    
    try:
        # 导入搜索函数
        from tools.web_search import search_web, DEFAULT_MCP_URL
        
        # 执行简单搜索
        query = "Python asyncio 教程"
        result = await search_web(api_key, DEFAULT_MCP_URL, query, num_results=3)
        
        if result and result.get("success"):
            results_count = len(result.get("results", []))
            add_test_result("搜索功能", True, f"成功搜索 '{query}'，返回 {results_count} 条结果")
            return result
        else:
            add_test_result("搜索功能", False, "搜索返回失败状态")
            return None
            
    except Exception as e:
        add_test_result("搜索功能", False, f"搜索异常: {e}")
        return None


async def test_json_output() -> None:
    """测试 JSON 输出格式。"""
    result = await test_search_function()
    
    if not result:
        add_test_result("JSON 输出格式", False, "无法获取搜索结果")
        return
    
    try:
        # 验证 JSON 结构
        required_keys = ["success", "query", "results"]
        missing_keys = [k for k in required_keys if k not in result]
        
        if missing_keys:
            add_test_result("JSON 输出格式", False, f"缺少必要字段: {missing_keys}")
            return
        
        # 验证结果列表格式
        if "results" in result and result["results"]:
            first_result = result["results"][0]
            result_keys = ["title", "link", "snippet"]
            missing_result_keys = [k for k in result_keys if k not in first_result]
            
            if missing_result_keys:
                add_test_result("JSON 输出格式", False, f"结果缺少字段: {missing_result_keys}")
                return
        
        add_test_result("JSON 输出格式", True, "JSON 结构正确，包含必要字段")
        
    except Exception as e:
        add_test_result("JSON 输出格式", False, f"验证异常: {e}")


async def test_financial_search() -> None:
    """测试金融相关搜索。"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        add_test_result("金融搜索", False, "需要 API Key 才能测试")
        return
    
    try:
        from tools.web_search import search_web, DEFAULT_MCP_URL
        
        # 搜索金融相关内容
        query = "腾讯控股 2024年财报"
        result = await search_web(api_key, DEFAULT_MCP_URL, query, num_results=3)
        
        if result and result.get("success"):
            results_count = len(result.get("results", []))
            add_test_result("金融搜索", True, f"成功搜索 '{query}'，返回 {results_count} 条结果")
        else:
            add_test_result("金融搜索", False, "金融搜索返回失败状态")
            
    except Exception as e:
        add_test_result("金融搜索", False, f"搜索异常: {e}")


def test_format_results() -> None:
    """测试结果格式化函数。"""
    try:
        from tools.web_search import format_search_results
        
        # 测试数据
        test_data = {
            "search_results": [
                {"title": "测试标题1", "link": "https://example.com/1", "snippet": "摘要1"},
                {"title": "测试标题2", "url": "https://example.com/2", "content": "摘要2"},
            ]
        }
        
        results = format_search_results(test_data, "测试", 10)
        
        if len(results) == 2:
            # 检查字段映射
            if results[0]["title"] == "测试标题1" and results[0]["link"] == "https://example.com/1":
                add_test_result("结果格式化", True, f"成功格式化 {len(results)} 条结果")
            else:
                add_test_result("结果格式化", False, "字段映射不正确")
        else:
            add_test_result("结果格式化", False, f"预期 2 条结果，实际 {len(results)} 条")
            
    except Exception as e:
        add_test_result("结果格式化", False, f"格式化异常: {e}")


async def run_async_tests() -> None:
    """运行异步测试。"""
    await test_search_function()
    await test_json_output()
    await test_financial_search()


def main() -> None:
    """主函数。"""
    print("\n" + "=" * 60)
    print("网络搜索工具测试")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"Python 版本: {sys.version}")
    print("=" * 60 + "\n")
    
    # 同步测试
    test_import()
    test_api_key_check()
    test_format_results()
    
    # 异步测试（需要 API Key）
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if api_key:
        print("\n--- 运行异步测试（需要 API Key）---")
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(run_async_tests())
    else:
        print("\n--- 跳过异步测试（未设置 API Key）---")
        add_test_result("异步测试", True, "⚠️ 跳过：未设置 DASHSCOPE_API_KEY")
    
    # 输出测试汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    failed_count = len(test_results) - passed_count
    
    print(f"总计: {len(test_results)} | 通过: {passed_count} | 失败: {failed_count}")
    
    if failed_count > 0:
        print("\n失败的测试:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['test']}: {r['message']}")
    
    print("=" * 60)
    
    # 返回退出码
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()