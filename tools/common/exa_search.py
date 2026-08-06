"""
Exa 搜索工具（Exa.ai，原 Metaphor Search）
==========================================

本工具通过 Exa.ai 语义搜索引擎 API 实现网络信息搜索，
返回结构化搜索结果（标题、URL、正文/摘要、发布时间）。

功能特点:
1. 使用 HTTP API 调用 Exa.ai（x-api-key 认证），无需 SDK。
2. 支持检索速度档位（instant/fast/auto/deep-lite/deep）。
3. 支持 Autoprompt 自动优化查询词。
4. 支持正文提取（text）与高亮摘要（highlights）两种内容模式。
5. 返回结构化数据：title、url、published_date、content。
6. 支持命令行调用和模块导入两种方式。
7. 从 .env 文件读取 API Key。

依赖库:
pip install requests python-dotenv

用法:
python tools/common/exa_search.py "搜索关键词"
python tools/common/exa_search.py "煤化工行业报告" --max-results 8
python tools/common/exa_search.py "紫金矿业 2025年报" --type deep
python tools/common/exa_search.py "黄金价格走势" --json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ExaSearch")

# 加载环境变量（从项目根目录的 .env 文件）
# 本文件位于 tools/common/ 下，需向上 3 层到达项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ==================== 配置常量 ====================

# Exa API 根地址
API_BASE_URL = "https://api.exa.ai"

# 搜索端点
SEARCH_ENDPOINT = "/search"

# 检索速度档位（type 参数）
SEARCH_TYPE_MAP = {
    "instant": "instant",      # ~250ms，实时聊天
    "fast": "fast",            # ~450ms，普通问答
    "auto": "auto",            # ~1s，通用业务（默认）
    "deep-lite": "deep-lite",  # ~4s，轻度调研
    "deep": "deep",            # 4-40s，深度调研
}

# 默认参数
DEFAULT_MAX_RESULTS = 5
DEFAULT_TYPE = "auto"
DEFAULT_MAX_CHARACTERS = 2000


# ==================== 核心搜索逻辑 ====================

def search_exa(
    query: str,
    api_key: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_type: str = DEFAULT_TYPE,
    use_autoprompt: bool = True,
    max_characters: int = DEFAULT_MAX_CHARACTERS,
    use_highlights: bool = False,
    timeout: int = 60,
) -> Optional[Dict[str, Any]]:
    """调用 Exa /search 接口执行语义搜索。

    Args:
        query: 搜索关键词。
        api_key: Exa API Key。
        max_results: 返回结果数量（1-10）。
        search_type: 检索速度档位（instant/fast/auto/deep-lite/deep）。
        use_autoprompt: 是否开启 Autoprompt 自动优化查询词。
        max_characters: 内容提取的最大字符数。
        use_highlights: 使用 highlights 高亮摘要模式（Token 更省）而非全文 text 模式。
        timeout: 请求超时秒数（deep 档位耗时较长）。

    Returns:
        包含搜索结果的结构化字典，失败返回 None。
    """
    # 校验 API Key
    if not api_key:
        logger.error("未提供 Exa API Key，无法执行搜索")
        return None

    # 校验检索档位
    if search_type not in SEARCH_TYPE_MAP:
        logger.warning(f"未知检索档位: {search_type}，回退到 auto")
        search_type = "auto"

    # 构建请求体
    payload: Dict[str, Any] = {
        "query": query,
        "numResults": max_results,
        "type": search_type,
        "useAutoprompt": use_autoprompt,
    }

    # 内容模式：highlights 高亮摘要 或 text 全文
    if use_highlights:
        payload["contents"] = {
            "highlights": {"max_characters": max_characters}
        }
    else:
        payload["contents"] = {
            "text": {"maxCharacters": max_characters}
        }

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    url = f"{API_BASE_URL}{SEARCH_ENDPOINT}"
    logger.info(f"正在搜索: '{query}' (type={search_type}, num={max_results})")

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except Exception as e:
        logger.error(f"请求 Exa API 失败: {e}")
        return None

    # 错误处理
    if resp.status_code != 200:
        logger.error(f"Exa API 返回错误状态: {resp.status_code}")
        try:
            error_body = resp.json()
            logger.error(f"错误详情: {json.dumps(error_body, ensure_ascii=False)[:500]}")
        except Exception:
            logger.error(f"响应内容: {resp.text[:500]}")
        return None

    # 解析响应
    try:
        data = resp.json()
    except ValueError as e:
        logger.error(f"解析 Exa 响应失败: {e}")
        return None

    results = parse_results(data, query)

    return {
        "success": True,
        "query": query,
        "max_results": max_results,
        "search_type": search_type,
        "results": results,
        "raw": data,
    }


def parse_results(data: Dict[str, Any], query: str) -> List[Dict[str, str]]:
    """解析 Exa /search 响应为标准结果列表。

    Args:
        data: Exa API 返回的 JSON 字典。
        query: 搜索关键词（用于日志）。

    Returns:
        标准化的搜索结果列表，每项含 title、url、published_date、content。
    """
    results: List[Dict[str, str]] = []
    raw_results = data.get("results", []) or []

    for item in raw_results:
        # highlights 模式返回 highlights 列表，text 模式返回 text 字段
        content = ""
        if item.get("text"):
            content = item["text"]
        elif item.get("highlights"):
            highlights = item["highlights"]
            if isinstance(highlights, list):
                content = "\n".join(str(h) for h in highlights if h)
            else:
                content = str(highlights)

        # 发布时间字段
        published_date = item.get("publishedDate") or item.get("published_date") or ""

        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "published_date": str(published_date) if published_date else "",
            "content": content,
        })

    logger.info(f"解析完成，共 {len(results)} 条结果")
    return results


# ==================== 输出展示 ====================

def print_results(result: Dict[str, Any], output_json: bool = False) -> None:
    """打印搜索结果。

    Args:
        result: 搜索结果字典。
        output_json: 是否输出 JSON 格式。
    """
    if output_json:
        # 去除 raw 字段，仅输出可读结果
        output = {k: v for k, v in result.items() if k != "raw"}
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    print("\n" + "=" * 60)
    print(f"搜索关键词: {result['query']}")
    print(f"检索档位: {result['search_type']} | 返回结果数: {len(result['results'])}")
    print("=" * 60)

    for i, item in enumerate(result["results"], 1):
        print(f"\n【{i}】 {item['title']}")
        if item["url"]:
            print(f"    链接: {item['url']}")
        if item["published_date"]:
            print(f"    发布时间: {item['published_date']}")
        if item["content"]:
            content_preview = item["content"]
            if len(content_preview) > 300:
                content_preview = content_preview[:300] + "..."
            print(f"    内容: {content_preview}")


# ==================== CLI 入口 ====================

def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="Exa 搜索工具（Exa.ai 语义搜索引擎）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/common/exa_search.py "煤化工行业报告"
  python tools/common/exa_search.py "紫金矿业 2025年报" --max-results 8
  python tools/common/exa_search.py "行业深度报告" --type deep
  python tools/common/exa_search.py "黄金价格走势" --highlights --json

环境变量:
  EXA_API_KEY  Exa API Key（必需，申请地址: https://dashboard.exa.ai/api-keys）
        """,
    )

    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS,
                        help=f"返回结果数量（默认: {DEFAULT_MAX_RESULTS}）")
    parser.add_argument("--type", default=DEFAULT_TYPE,
                        choices=list(SEARCH_TYPE_MAP.keys()),
                        help=f"检索速度档位（默认: {DEFAULT_TYPE}）")
    parser.add_argument("--no-autoprompt", action="store_true",
                        help="关闭 Autoprompt 自动优化查询词（默认开启）")
    parser.add_argument("--max-characters", type=int, default=DEFAULT_MAX_CHARACTERS,
                        help=f"内容提取最大字符数（默认: {DEFAULT_MAX_CHARACTERS}）")
    parser.add_argument("--highlights", action="store_true",
                        help="使用 highlights 高亮摘要模式（Token 更省）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--api-key", help="Exa API Key（优先使用环境变量）")

    args = parser.parse_args()

    # 获取 API Key
    api_key = args.api_key or os.getenv("EXA_API_KEY")

    if not api_key:
        print("\n错误: 未设置 EXA_API_KEY")
        print("解决方案:")
        print("1. 创建 .env 文件并设置: EXA_API_KEY=your-exa-api-key")
        print("2. 或设置环境变量: set EXA_API_KEY=your-exa-api-key")
        print("3. 或使用命令行参数: --api-key your-exa-api-key")
        print("API Key 申请地址: https://dashboard.exa.ai/api-keys")
        sys.exit(1)

    # 执行搜索
    result = search_exa(
        query=args.query,
        api_key=api_key,
        max_results=args.max_results,
        search_type=args.type,
        use_autoprompt=not args.no_autoprompt,
        max_characters=args.max_characters,
        use_highlights=args.highlights,
    )

    if not result:
        logger.error("搜索失败，未获取到结果")
        sys.exit(1)

    print_results(result, args.json)


# ==================== 模块导入接口 ====================

def exa_search(query: str, max_results: int = 5,
               search_type: str = DEFAULT_TYPE,
               use_highlights: bool = False,
               max_characters: int = DEFAULT_MAX_CHARACTERS) -> List[Dict[str, str]]:
    """Exa 搜索模块接口（同步）。

    Args:
        query: 搜索关键词。
        max_results: 最大返回结果数。
        search_type: 检索速度档位（instant/fast/auto/deep-lite/deep）。
        use_highlights: 使用 highlights 高亮摘要模式。
        max_characters: 内容提取最大字符数。

    Returns:
        List[Dict[str, str]]: 搜索结果列表，每项含 title、url、published_date、content。
        失败时返回空列表。

    Example:
        >>> from tools.common.exa_search import exa_search
        >>> results = exa_search("黄金价格走势", max_results=3)
        >>> for r in results:
        ...     print(f"标题: {r['title']}")
        ...     print(f"链接: {r['url']}")
        ...     print(f"内容: {r['content'][:100]}...")
    """
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ValueError("未找到有效的 EXA_API_KEY，请在 .env 文件中配置")

    result = search_exa(
        query=query,
        api_key=api_key,
        max_results=max_results,
        search_type=search_type,
        use_highlights=use_highlights,
        max_characters=max_characters,
    )

    if result and result.get("success"):
        return result.get("results", [])
    else:
        return []


if __name__ == "__main__":
    main()
