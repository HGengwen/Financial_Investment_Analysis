"""
Tavily 搜索工具（阿里云百炼 MCP）
==================================

本工具通过阿里云百炼 Tavily MCP 服务实现网络信息搜索，
返回标题、URL、内容三个字段。

功能特点:
1. 使用 MCP 协议连接阿里云百炼 Tavily 服务。
2. 返回结构化数据：title、url、content。
3. 支持命令行调用和模块导入。
4. 从 .env 文件读取 API Key。

依赖库:
pip install mcp python-dotenv

用法:
python tools/tavily_search.py "搜索关键词"

# 基本用法
python tools/tavily_search.py "黄金价格走势 2026年"

# 指定结果数量
python tools/tavily_search.py "紫金矿业 2025年报" --max-results 10

# JSON 格式输出
python tools/tavily_search.py "紫金矿业 ROE" --json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any, List

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TavilySearch")

# 加载环境变量（从项目根目录的 .env 文件）
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 常量配置
DEFAULT_MCP_URL = "https://dashscope.aliyuncs.com/api/v1/mcps/tavily-ai/sse"
DEFAULT_MAX_RESULTS = 5


@asynccontextmanager
async def mcp_server_context(api_key: str, mcp_url: str) -> AsyncGenerator[ClientSession, None]:
    """
    MCP 服务器连接上下文管理器。
    
    负责建立 SSE 连接、初始化 MCP 会话，并在退出时自动清理资源。
    
    Args:
        api_key: 阿里云百炼 API Key
        mcp_url: MCP 服务端点 URL
        
    Yields:
        ClientSession: MCP 客户端会话
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    
    logger.info(f"正在连接服务端点: {mcp_url}")
    
    try:
        async with sse_client(mcp_url, headers=headers) as (read_stream, write_stream):
            logger.info("SSE 连接成功，正在初始化 MCP 会话...")
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                logger.info("MCP 会话初始化完成。")
                yield session
    except Exception as e:
        logger.error(f"连接 MCP 服务器失败: {e}")
        raise


async def search_with_tavily(
    api_key: str,
    mcp_url: str,
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS
) -> Optional[Dict[str, Any]]:
    """
    使用 Tavily MCP 服务进行搜索。
    
    Args:
        api_key: 阿里云百炼 API Key
        mcp_url: MCP 服务端点 URL
        query: 搜索关键词
        max_results: 返回结果数量
        
    Returns:
        搜索结果字典，失败返回 None
    """
    async with mcp_server_context(api_key, mcp_url) as session:
        # 1. 获取可用工具列表
        logger.info("正在获取工具列表...")
        tools_result = await session.list_tools()
        tools = tools_result.tools
        
        if not tools:
            logger.error("未找到任何可用工具。")
            return None

        logger.info(f"发现 {len(tools)} 个工具。")
        
        # 2. 查找搜索工具
        search_tool_name = next(
            (t.name for t in tools if "search" in t.name.lower()), 
            None
        )
        
        if not search_tool_name:
            if tools:
                search_tool_name = tools[0].name
                logger.warning(f"未找到明确的搜索工具，尝试使用第一个工具: {search_tool_name}")
            else:
                logger.error("无法确定搜索工具。")
                return None
        
        logger.info(f"使用工具: {search_tool_name}")

        # 3. 调用工具执行搜索
        logger.info(f"正在搜索: '{query}' ...")
        
        try:
            # 配置搜索参数
            arguments = {
                "query": query,
                "search_depth": "advanced",      # 高级搜索，内容质量更高
                "max_results": max_results,     # 控制返回结果数量
                "include_raw_content": True,    # 开启 raw_content 字段
                "include_answer": False,        # 不需要综合摘要
            }
            
            result: CallToolResult = await session.call_tool(
                name=search_tool_name,
                arguments=arguments
            )
        except Exception as e:
            logger.error(f"调用工具失败: {e}")
            return None

        # 4. 提取结果
        if result.isError:
            logger.error("搜索返回错误状态。")
        
        # 提取文本内容
        text_parts = []
        for content in result.content:
            if content.type == "text":
                text_parts.append(content.text)
            elif content.type == "image":
                logger.info(f"[图片内容] (Base64 data length: {len(content.data)})")
        
        if not text_parts:
            return None
        
        # 5. 解析并格式化结果
        raw_result = "\n".join(text_parts)
        
        # 调试：打印原始返回数据
        logger.info(f"原始返回数据长度: {len(raw_result)}")
        logger.debug(f"原始返回数据: {raw_result[:500]}...")
        
        # 解析文本格式结果
        formatted_results = parse_text_results(raw_result)
        
        return {
            "success": True,
            "query": query,
            "max_results": max_results,
            "results": formatted_results,
            "raw_text": raw_result
        }


def parse_text_results(text: str) -> List[Dict[str, str]]:
    """
    解析 Tavily 返回的文本格式搜索结果。
    
    Args:
        text: Tavily 返回的文本格式搜索结果
        
    Returns:
        格式化后的搜索结果列表，每项包含 title、url、content
    """
    results = []
    current_result = {}
    
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 检查是否是字段标记
        if line.startswith("Title:"):
            # 如果已有结果，保存它
            if current_result and current_result.get("title"):
                results.append(current_result)
            current_result = {
                "title": line[6:].strip(),
                "url": "",
                "content": ""
            }
        elif line.startswith("URL:"):
            if current_result:
                current_result["url"] = line[4:].strip()
        elif line.startswith("Content:"):
            if current_result:
                current_result["content"] = line[8:].strip()
        elif current_result:
            # 如果当前有结果，将内容追加到 content 字段
            if current_result.get("content"):
                current_result["content"] += " " + line
    
    # 添加最后一个结果
    if current_result and current_result.get("title"):
        results.append(current_result)
    
    return results


def print_results(result: Dict[str, Any], output_json: bool = False) -> None:
    """
    打印搜索结果。
    
    Args:
        result: 搜索结果字典
        output_json: 是否输出 JSON 格式
    """
    if output_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print(f"搜索关键词: {result['query']}")
        print(f"返回结果数: {len(result['results'])}")
        print("=" * 60)
        
        for i, item in enumerate(result['results'], 1):
            print(f"\n【{i}】 {item['title']}")
            if item['url']:
                print(f"    链接: {item['url']}")
            if item['content']:
                # 显示前200字符
                content_preview = item['content'][:200] + "..." if len(item['content']) > 200 else item['content']
                print(f"    内容: {content_preview}")


async def main_async(query: str, api_key: str, max_results: int, output_json: bool) -> Optional[Dict[str, Any]]:
    """
    异步主函数。
    
    Args:
        query: 搜索关键词
        api_key: API Key
        max_results: 结果数量
        output_json: 是否输出 JSON 格式
        
    Returns:
        搜索结果字典
    """
    mcp_url = os.getenv("Tavily_MCP_BASE_URL", DEFAULT_MCP_URL)
    
    result = await search_with_tavily(api_key, mcp_url, query, max_results)
    
    if result:
        print_results(result, output_json)
    
    return result


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="Tavily 搜索工具（阿里云百炼 MCP）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/tavily_search.py "黄金价格走势 2026年"
  python tools/tavily_search.py "紫金矿业 2025年报" --max-results 10
  python tools/tavily_search.py "腾讯控股 股价" --json

环境变量:
  DASHSCOPE_API_KEY  阿里云百炼 API Key（必需）
  MCP_BASE_URL       MCP 服务端点（可选）
        """
    )
    
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS, 
                        help=f"返回结果数量（默认: {DEFAULT_MAX_RESULTS}）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--api-key", help="阿里云百炼 API Key（优先使用环境变量）")
    
    args = parser.parse_args()
    
    # 获取 API Key
    api_key = args.api_key or os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        print("\n错误: 未设置 DASHSCOPE_API_KEY")
        print("解决方案:")
        print("1. 创建 .env 文件并设置: DASHSCOPE_API_KEY=sk-your-api-key")
        print("2. 或设置环境变量:")
        print("   Windows: set DASHSCOPE_API_KEY=sk-your-api-key")
        print("   Linux/Mac: export DASHSCOPE_API_KEY='sk-your-api-key'")
        print("3. 或使用命令行参数: --api-key sk-your-api-key")
        sys.exit(1)
    
    # Windows 平台 asyncio 策略调整
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main_async(args.query, api_key, args.max_results, args.json))
    except KeyboardInterrupt:
        print("\n搜索已取消。")
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# 提供模块导入接口
async def tavily_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Tavily 搜索模块接口。
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数（1-20）
        
    Returns:
        List[Dict[str, str]]: 搜索结果列表，每项包含 title、url、content
        
    Example:
        >>> import asyncio
        >>> from tools.tavily_search import tavily_search
        >>> 
        >>> async def main():
        ...     results = await tavily_search("黄金价格走势", max_results=3)
        ...     for r in results:
        ...         print(f"标题: {r['title']}")
        ...         print(f"链接: {r['url']}")
        ...         print(f"内容: {r['content'][:100]}...")
        >>> 
        >>> asyncio.run(main())
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未找到有效的 DASHSCOPE_API_KEY，请在 .env 文件中配置")
    
    mcp_url = os.getenv("Tavily_MCP_BASE_URL", DEFAULT_MCP_URL)
    result = await search_with_tavily(api_key, mcp_url, query, max_results)
    
    if result and result.get("success"):
        return result.get("results", [])
    else:
        return []