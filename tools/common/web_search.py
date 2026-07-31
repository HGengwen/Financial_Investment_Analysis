"""
网络信息搜索工具
------------------

本工具通过阿里云百炼 WebSearch MCP 服务实现网络信息搜索,
替代 Anthropic 的 WebSearch 服务（在中国大陆被地域封锁）。

功能特点:
1. 使用 MCP 协议连接阿里云百炼 WebSearch 服务。
2. 支持通过环境变量或命令行参数配置 API Key。
3. 支持 JSON 格式输出搜索结果。
4. 支持指定搜索结果数量。

依赖库:
pip install mcp python-dotenv

用法:
python tools/web_search.py "搜索关键词" [--num N] [--json]
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
logger = logging.getLogger("WebSearch")

# 加载环境变量（从项目根目录的 .env 文件）
# 注意：本文件位于 tools/common/ 下，需向上 3 层到达项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 常量配置
DEFAULT_MCP_URL = "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse"
DEFAULT_NUM_RESULTS = 5


@asynccontextmanager
async def mcp_server_context(api_key: str, mcp_url: str) -> AsyncGenerator[ClientSession, None]:
    """
    MCP 服务器连接上下文管理器。
    
    负责建立 SSE 连接、初始化 MCP 会话,并在退出时自动清理资源。
    
    Args:
        api_key: 阿里云百炼 API Key
        mcp_url: MCP服务端点URL
        
    Yields:
        ClientSession: MCP 客户端会话
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    
    logger.info(f"正在连接服务端点: {mcp_url}")
    
    try:
        async with sse_client(mcp_url, headers=headers) as (read_stream, write_stream):
            logger.info("SSE 连接成功,正在初始化 MCP 会话...")
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                logger.info("MCP 会话初始化完成。")
                yield session
    except Exception as e:
        logger.error(f"连接 MCP 服务器失败: {e}")
        raise


async def search_web(
    api_key: str, 
    mcp_url: str, 
    query: str,
    num_results: int = DEFAULT_NUM_RESULTS
) -> Optional[Dict[str, Any]]:
    """
    使用 WebSearch MCP 服务进行搜索。
    
    Args:
        api_key: 阿里云百炼 API Key
        mcp_url: MCP服务端点URL
        query: 搜索关键词
        num_results: 返回结果数量
        
    Returns:
        搜索结果字典,失败返回None
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
                logger.warning(f"未找到明确的搜索工具,尝试使用第一个工具: {search_tool_name}")
            else:
                logger.error("无法确定搜索工具。")
                return None
        
        logger.info(f"使用工具: {search_tool_name}")

        # 3. 调用工具执行搜索
        logger.info(f"正在搜索: '{query}' ...")
        
        try:
            result: CallToolResult = await session.call_tool(
                name=search_tool_name,
                arguments={"query": query}
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
        
        try:
            # 尝试解析 JSON
            data = json.loads(raw_result)
            
            # 调试：打印解析后的数据结构
            logger.info(f"解析后数据类型: {type(data)}")
            if isinstance(data, dict):
                logger.info(f"数据字段: {list(data.keys())}")
            
            # 格式化为标准输出格式
            formatted_results = format_search_results(data, query, num_results)
            
            return {
                "success": True,
                "query": query,
                "num_results": num_results,
                "results": formatted_results,
                "raw_data": data
            }
        except json.JSONDecodeError:
            # 如果不是 JSON,直接返回文本
            return {
                "success": True,
                "query": query,
                "num_results": num_results,
                "results": [{
                    "title": "搜索结果",
                    "link": "",
                    "snippet": raw_result[:500]
                }],
                "raw_text": raw_result
            }


def format_search_results(data: Dict[str, Any], query: str, num_results: int) -> List[Dict[str, str]]:
    """
    格式化搜索结果为标准格式。
    
    Args:
        data: 原始搜索结果数据
        query: 搜索关键词
        num_results: 结果数量限制
        
    Returns:
        格式化后的搜索结果列表
    """
    results = []
    
    # 根据阿里云百炼返回的数据结构解析
    # 数据结构可能为: {"pages": [...]} 或 {"search_results": [...]} 或 {"results": [...]} 或直接列表
    search_items = []
    
    if isinstance(data, list):
        search_items = data
    elif "pages" in data:
        # 阿里云百炼 WebSearch 返回格式
        search_items = data["pages"]
    elif "search_results" in data:
        search_items = data["search_results"]
    elif "results" in data:
        search_items = data["results"]
    elif "web_pages" in data:
        search_items = data["web_pages"]
    
    # 限制结果数量
    search_items = search_items[:num_results]
    
    for item in search_items:
        result = {
            "title": item.get("title", item.get("name", "无标题")),
            "link": item.get("url", item.get("link", item.get("href", ""))),
            "snippet": item.get("snippet", item.get("content", item.get("description", ""))),
            "hostname": item.get("hostname", "")
        }
        results.append(result)
    
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
            if item['link']:
                print(f"    链接: {item['link']}")
            if item['snippet']:
                print(f"    摘要: {item['snippet'][:200]}...")


async def main_async(query: str, api_key: str, num_results: int, output_json: bool) -> Optional[Dict[str, Any]]:
    """
    异步主函数。
    
    Args:
        query: 搜索关键词
        api_key: API Key
        num_results: 结果数量
        output_json: 是否输出 JSON 格式
        
    Returns:
        搜索结果字典
    """
    mcp_url = os.getenv("WebSearch_MCP_BASE_URL", DEFAULT_MCP_URL)
    
    result = await search_web(api_key, mcp_url, query, num_results)
    
    if result:
        print_results(result, output_json)
    
    return result


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="网络信息搜索工具（阿里云百炼 WebSearch MCP）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/web_search.py "腾讯控股 股价"
  python tools/web_search.py "中际旭创 ROE" --num 10
  python tools/web_search.py "贵州茅台 年报 2024" --json

环境变量:
  DASHSCOPE_API_KEY  阿里云百炼 API Key（必需）
  MCP_BASE_URL       MCP 服务端点（可选）
        """
    )
    
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--num", type=int, default=DEFAULT_NUM_RESULTS, 
                        help=f"返回结果数量（默认: {DEFAULT_NUM_RESULTS}）")
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
        asyncio.run(main_async(args.query, api_key, args.num, args.json))
    except KeyboardInterrupt:
        print("\n搜索已取消。")
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
