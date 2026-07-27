"""
Tavily 搜索工具测试
====================

测试阿里云百炼 Tavily MCP 搜索工具的功能。

测试内容:
1. 基本搜索功能
2. 结果格式验证（title、url、content 三个字段）
3. 错误处理

用法:
python tests/test_tavily_search.py
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.tavily_search import tavily_search, print_results


async def test_basic_search():
    """测试基本搜索功能。"""
    print("\n" + "="*60)
    print("测试1: 基本搜索功能")
    print("="*60)
    
    query = "黄金价格 2026年走势"
    print(f"\n搜索关键词: {query}")
    
    try:
        results = await tavily_search(query, max_results=3)
        
        # 验证结果格式
        assert isinstance(results, list), "结果应该是列表"
        assert len(results) <= 3, "结果数量应该 <= 3"
        
        for idx, result in enumerate(results, 1):
            print(f"\n【结果 {idx}】")
            print(f"标题: {result.get('title', '(无)')}")
            print(f"链接: {result.get('url', '(无)')}")
            print(f"内容: {result.get('content', '(无)')[:100]}...")
            
            # 验证字段存在
            assert "title" in result, "缺少 title 字段"
            assert "url" in result, "缺少 url 字段"
            assert "content" in result, "缺少 content 字段"
        
        print("\n✅ 测试通过: 基本搜索功能正常")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


async def test_result_format():
    """测试结果格式验证。"""
    print("\n" + "="*60)
    print("测试2: 结果格式验证")
    print("="*60)
    
    query = "紫金矿业 最新财报"
    print(f"\n搜索关键词: {query}")
    
    try:
        results = await tavily_search(query, max_results=2)
        
        print(f"\n返回结果数: {len(results)}")
        
        for idx, result in enumerate(results, 1):
            print(f"\n【结果 {idx}】")
            print(f"标题长度: {len(result.get('title', ''))}")
            print(f"链接长度: {len(result.get('url', ''))}")
            print(f"内容长度: {len(result.get('content', ''))}")
            
            # 验证字段类型
            assert isinstance(result.get("title", ""), str), "title 应该是字符串"
            assert isinstance(result.get("url", ""), str), "url 应该是字符串"
            assert isinstance(result.get("content", ""), str), "content 应该是字符串"
            
            # 验证字段非空（至少有一个字段有内容）
            has_content = any([
                result.get("title"),
                result.get("url"),
                result.get("content")
            ])
            assert has_content, "至少有一个字段应该有内容"
        
        print("\n✅ 测试通过: 结果格式正确")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


async def test_print_results():
    """测试结果打印功能。"""
    print("\n" + "="*60)
    print("测试3: 结果打印功能")
    print("="*60)
    
    # 创建测试数据（适配新的返回格式）
    test_result = {
        "success": True,
        "query": "测试关键词",
        "max_results": 2,
        "results": [
            {
                "title": "测试标题1",
                "url": "https://example.com/1",
                "content": "这是测试内容1，用于验证打印功能。"
            },
            {
                "title": "测试标题2",
                "url": "https://example.com/2",
                "content": "这是测试内容2，用于验证打印功能。"
            }
        ]
    }
    
    print("\n打印测试结果:")
    print_results(test_result)
    
    print("\n✅ 测试通过: 结果打印功能正常")
    return True


async def test_empty_results():
    """测试空结果处理。"""
    print("\n" + "="*60)
    print("测试4: 空结果处理")
    print("="*60)
    
    # 测试打印空结果（适配新的返回格式）
    test_result = {
        "success": True,
        "query": "测试关键词",
        "max_results": 0,
        "results": []
    }
    
    print("\n打印空结果:")
    print_results(test_result)
    
    print("\n✅ 测试通过: 空结果处理正常")
    return True


async def run_tests():
    """运行所有测试。"""
    print("\n" + "="*60)
    print("Tavily 搜索工具测试")
    print("="*60)
    
    tests = [
        ("基本搜索功能", test_basic_search),
        ("结果格式验证", test_result_format),
        ("结果打印功能", test_print_results),
        ("空结果处理", test_empty_results),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试异常: {test_name} - {e}")
            results.append((test_name, False))
    
    # 打印测试总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
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
    # Windows 平台 asyncio 策略调整
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        exit_code = asyncio.run(run_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试异常退出: {e}")
        sys.exit(1)