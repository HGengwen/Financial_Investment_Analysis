"""
AnySearch 搜索工具（全域结构化搜索基础设施）
==========================================

本工具通过 AnySearch API 实现网络信息搜索，作为阿里云百炼 WebSearch、
Tavily、火山引擎豆包搜索的并行方案，返回结构化搜索结果。

功能特点:
1. 使用 AnySearch REST API（POST /v1/search）进行搜索。
2. 支持 23 大垂直领域专属数据库定向检索（代码、法律、金融、学术等）。
3. 支持区域（cn/intl）与语言（zh-CN/en）切换。
4. 返回结构化数据：标题、链接、摘要、清洗后正文。
5. 支持命令行调用和模块导入两种方式。
6. 支持导出 Markdown 格式搜索报告。
7. 内置客户端 QPS 限流（线程安全），避免触发服务端 429。
8. 支持匿名调用（无 API Key），但额度极少，建议注册账号。

依赖库:
pip install requests python-dotenv

用法:
python tools/common/anysearch.py "搜索关键词"
python tools/common/anysearch.py "紫金矿业 财报" --count 10
python tools/common/anysearch.py "黄金价格走势" --json
python tools/common/anysearch.py "腾讯控股" --tag finance.fundamental --export
python tools/common/anysearch.py "民法典 判例" --tag legal.case
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AnySearch")

# 加载环境变量（从项目根目录的 .env 文件）
# 本文件位于 tools/common/ 下，需向上 3 层到达项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ==================== 配置常量 ====================

# AnySearch API 端点
API_BASE_URL = "https://api.anysearch.com"
API_SEARCH_PATH = "/v1/search"

# 默认 QPS 限流（AnySearch 注册账号每日 1000 次免费额度，不限 QPS，
# 但为避免突发流量触发 429，客户端默认限制为 20 QPS）
DEFAULT_QPS = 20

# 默认返回结果数
DEFAULT_COUNT = 10

# 默认搜索区域与语言
DEFAULT_ZONE = "cn"
DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_FORMAT = "json"

# 默认请求超时时间（秒）
DEFAULT_TIMEOUT = 30

# 垂直领域 Tag 分类映射（常用快捷别名 → 官方 tag）
# 完整 tag 列表参见官方文档，此处仅提供常用快捷映射
TAG_ALIASES = {
    # 通用
    "general": "general.general",
    # 学术
    "academic": "academic.search",
    "paper": "academic.search",
    "preprint": "academic.preprint",
    # 代码
    "code": "code.doc",
    "doc": "code.doc",
    "snippet": "code.snippet",
    "github": "code.snippet",
    # 金融
    "finance": "finance.fundamental",
    "stock": "finance.quote",
    "quote": "finance.quote",
    "fundamental": "finance.fundamental",
    "calendar": "finance.calendar",
    "macro": "finance.macro",
    # 法律
    "legal": "legal.case",
    "case": "legal.case",
    "statute": "legal.statute",
    "legislation": "legal.legislation",
    # 专利
    "patent": "ip.global",
    "ip": "ip.global",
    # 安全
    "vuln": "security.vuln",
    "cve": "security.vuln",
    "threat": "security.intel",
    # 其他
    "agriculture": "agriculture.agriculture",
    "energy": "energy.energy",
    "health": "health.health",
    "travel": "travel.flight",
    "social": "social_media.social",
}

# HTTP 错误码到中文说明的映射
ERROR_CODE_MAP = {
    402: {
        "daily_free_quota_exhausted": "匿名 IP 当日免费额度耗尽",
        "user_daily_quota_exhausted": "注册账号每日免费额度用完，次日 0 点重置",
    },
    401: {"invalid_api_key": "API 密钥不存在/禁用/格式错误"},
    429: {"rate_limit_exceeded": "调用频率超限"},
    504: {"extract_timeout": "网页内容抓取超时"},
    403: {"private_capability_not_enabled": "当前 Key 无权限使用付费垂直数据库"},
}


# ==================== 限速器 ====================


class RateLimiter:
    """基于时间窗口的 QPS 限速器。

    通过记录上次请求时间，确保请求间隔不小于 1/QPS 秒。
    线程安全，支持多线程场景下的限流。

    Attributes:
        max_qps: 最大每秒查询数。
        min_interval: 最小请求间隔（秒），等于 1/max_qps。
    """

    def __init__(self, max_qps: int = DEFAULT_QPS) -> None:
        """初始化限速器。

        Args:
            max_qps: 最大每秒查询数，默认 20。
        """
        self.max_qps = max_qps
        self.min_interval = 1.0 / max_qps if max_qps > 0 else 0.0
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """等待直到可以发送下一个请求。

        根据距离上次请求的时间间隔，自动睡眠补足最小间隔。
        使用线程锁保证多线程场景下的限流正确性。
        """
        if self.min_interval <= 0:
            return

        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)
            self._last_request_time = time.monotonic()


# ==================== 搜索客户端 ====================


class AnySearchClient:
    """AnySearch API 客户端。

    封装 AnySearch REST API 调用，内置 QPS 限流功能。

    Attributes:
        api_key: API 密钥（可为空，匿名调用）。
        base_url: API 基础 URL。
        qps: 最大每秒请求数。
        timeout: 请求超时时间（秒）。
        rate_limiter: 限速器实例。
        session: HTTP 会话（requests.Session）。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = API_BASE_URL,
        qps: int = DEFAULT_QPS,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """初始化搜索客户端。

        Args:
            api_key: API 密钥，为空则匿名调用（额度极少）。
            base_url: API 基础 URL，默认 https://api.anysearch.com。
            qps: 最大每秒请求数，默认 20。
            timeout: 请求超时时间（秒），默认 30。
        """
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.qps = qps
        self.timeout = timeout
        self.rate_limiter = RateLimiter(qps)
        self.session = requests.Session()

        # 设置默认请求头
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.headers.update(headers)

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_COUNT,
        tag: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        zone: str = DEFAULT_ZONE,
        language: str = DEFAULT_LANGUAGE,
        format: str = DEFAULT_FORMAT,
    ) -> dict[str, Any]:
        """执行搜索请求，返回完整 API 响应。

        Args:
            query: 搜索关键词或自然语言问题（建议不超过 300 字符）。
            max_results: 返回结果数量（1-20），默认 10。
            tag: 垂直领域标签，如 "code.doc"、"legal.case"、"finance.fundamental"，
                支持快捷别名（见 TAG_ALIASES），不填则通用全网搜索。
            params: tag 扩展筛选参数，如 {"library": "golang"}、{"ticker": "AAPL"}。
            zone: 区域，"cn" 国内 / "intl" 国际，默认 cn。
            language: 语言，"zh-CN" / "en"，默认 zh-CN。
            format: 返回格式，"json" / "markdown"，默认 json。

        Returns:
            API 完整响应的 JSON 字典，结构如下：
            {
                "code": 0,
                "message": "success",
                "request_id": "...",
                "data": {
                    "results": [{"title", "url", "snippet", "content"}],
                    "metadata": {"total_results", "search_time_ms"}
                }
            }

        Raises:
            ValueError: 当 API 返回业务错误（code != 0）时抛出。
            requests.RequestException: 当 HTTP 请求失败时抛出。
        """
        # 参数规范化：tag 别名映射
        normalized_tag = self._normalize_tag(tag)

        # 构建请求体
        payload: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "zone": zone,
            "language": language,
            "format": format,
        }
        if normalized_tag:
            payload["tag"] = normalized_tag
        if params:
            payload["params"] = params

        # 限速等待
        self.rate_limiter.wait()

        # 发送请求
        url = f"{self.base_url}{API_SEARCH_PATH}"
        response = self.session.post(url, json=payload, timeout=self.timeout)

        # 检查 HTTP 状态码
        if response.status_code != 200:
            self._raise_http_error(response)

        # 解析响应
        result = response.json()

        # 检查业务错误
        if result.get("code") != 0:
            error_msg = result.get("message", "未知错误")
            raise ValueError(f"搜索失败: {error_msg}")

        return result

    def search_simple(
        self,
        query: str,
        max_results: int = DEFAULT_COUNT,
        tag: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        zone: str = DEFAULT_ZONE,
        language: str = DEFAULT_LANGUAGE,
        format: str = DEFAULT_FORMAT,
    ) -> list[dict[str, Any]]:
        """简化版搜索，返回标准化结果列表。

        与 search() 参数一致，但返回值简化为标准化字典列表，
        便于模块间调用。

        Args:
            参数与 search() 相同，参见 search() 文档。

        Returns:
            标准化搜索结果列表，每项包含以下字段：
            - title: 标题
            - url: 链接
            - snippet: 简短摘要
            - content: 清洗后的完整正文（专供 LLM 读取）

        Raises:
            ValueError: 当 API 返回业务错误时抛出。
            requests.RequestException: 当 HTTP 请求失败时抛出。
        """
        response = self.search(
            query=query,
            max_results=max_results,
            tag=tag,
            params=params,
            zone=zone,
            language=language,
            format=format,
        )

        # 提取并标准化结果
        results = []
        for item in response.get("data", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "content": item.get("content", ""),
            })

        return results

    @staticmethod
    def _normalize_tag(tag: Optional[str]) -> Optional[str]:
        """将 tag 别名映射为官方 tag。

        支持传入快捷别名（如 "code"、"legal"）或完整官方 tag
        （如 "code.doc"、"legal.case"），统一输出官方 tag。

        Args:
            tag: 原始 tag 或别名。

        Returns:
            映射后的官方 tag，输入为空则返回 None。
        """
        if not tag:
            return None
        # 先查别名映射，找不到则原样返回（允许直接传官方 tag）
        return TAG_ALIASES.get(tag.lower(), tag)

    @staticmethod
    def _raise_http_error(response: requests.Response) -> None:
        """根据 HTTP 错误响应抛出带中文说明的异常。

        Args:
            response: 错误响应对象。

        Raises:
            ValueError: 带中文说明的错误异常。
        """
        status_code = response.status_code
        error_map = ERROR_CODE_MAP.get(status_code, {})
        error_id = ""
        try:
            error_body = response.json()
            error_id = error_body.get("error", "") or error_body.get("message", "")
        except Exception:
            error_body = {"raw": response.text[:500]}

        # 查找中文说明
        cn_desc = error_map.get(error_id, "")
        error_detail = f"HTTP {status_code}"
        if error_id:
            error_detail += f" [{error_id}]"
        if cn_desc:
            error_detail += f" - {cn_desc}"

        raise ValueError(f"搜索失败: {error_detail} | 响应: {error_body}")

    def close(self) -> None:
        """关闭 HTTP 会话，释放连接资源。"""
        self.session.close()

    def __enter__(self) -> "AnySearchClient":
        """支持 with 上下文管理器。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文时自动关闭会话。"""
        self.close()


# ==================== 结果格式化输出 ====================


class ResultFormatter:
    """搜索结果格式化输出器。

    将 API 返回的 JSON 结果格式化为可读的终端文本输出，
    支持控制摘要/正文的显示长度。

    Attributes:
        max_snippet_length: 摘要最大显示字符数。
        max_content_length: 正文最大显示字符数。
    """

    SEPARATOR = "=" * 70
    SUB_SEPARATOR = "-" * 70

    def __init__(
        self,
        max_snippet_length: int = 500,
        max_content_length: int = 800,
    ) -> None:
        """初始化格式化输出器。

        Args:
            max_snippet_length: 摘要截断长度，默认 500 字符。
            max_content_length: 正文截断长度，默认 800 字符。
        """
        self.max_snippet_length = max_snippet_length
        self.max_content_length = max_content_length

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        """截断文本到指定长度，并添加省略号。

        Args:
            text: 原始文本。
            max_length: 最大字符数。

        Returns:
            截断后的文本，超出部分用 "..." 替代；空文本返回 "无"。
        """
        if not text:
            return "无"
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def format_search_results(self, response: dict[str, Any]) -> str:
        """将完整 API 响应格式化为可读字符串。

        Args:
            response: API 返回的 JSON 字典。

        Returns:
            格式化后的多行字符串，可直接打印输出。
        """
        lines: list[str] = []
        lines.append(self.SEPARATOR)
        lines.append("  AnySearch 搜索结果")
        lines.append(self.SEPARATOR)

        # 顶层元信息
        request_id = response.get("request_id", "未知")
        lines.append(f"  请求 ID: {request_id}")

        # 数据层
        data = response.get("data", {})
        metadata = data.get("metadata", {})
        total = metadata.get("total_results", 0)
        search_time = metadata.get("search_time_ms", "未知")
        lines.append(f"  结果总数: {total}")
        lines.append(f"  搜索耗时: {search_time} ms")
        lines.append(self.SEPARATOR)

        # 结果列表
        results = data.get("results", [])
        if not results:
            lines.append("\n  未找到匹配的搜索结果。\n")
            return "\n".join(lines)

        for idx, item in enumerate(results, 1):
            lines.append(self._format_item(idx, item))
            lines.append("")

        return "\n".join(lines)

    def _format_item(self, idx: int, item: dict[str, Any]) -> str:
        """格式化单条搜索结果。

        Args:
            idx: 序号（从 1 开始）。
            item: 单条搜索结果字典。

        Returns:
            格式化后的单条结果字符串。
        """
        title = item.get("title", "无标题")
        url = item.get("url", "无链接")
        snippet = item.get("snippet", "")
        content = item.get("content", "")

        lines: list[str] = []
        lines.append(self.SUB_SEPARATOR)
        lines.append(f"  [{idx}] {title}")
        lines.append(self.SUB_SEPARATOR)
        lines.append(f"  链接: {url}")

        # 摘要
        if snippet:
            lines.append(f"\n  [摘要]\n  {self._truncate(snippet, self.max_snippet_length)}")

        # 正文（清洗后的完整内容）
        if content:
            lines.append(f"\n  [正文]\n  {self._truncate(content, self.max_content_length)}")

        return "\n".join(lines)


# ==================== Markdown 报告导出 ====================


def export_to_markdown(
    response: dict[str, Any],
    save_path: str,
    query: str = "",
) -> str:
    """将搜索结果导出为 Markdown 报告文件。

    Args:
        response: API 返回的 JSON 字典。
        save_path: 保存路径。
        query: 搜索关键词（用于报告头部），可选。

    Returns:
        保存的文件路径。
    """
    data = response.get("data", {})
    metadata = data.get("metadata", {})
    results = data.get("results", [])
    request_id = response.get("request_id", "未知")

    md_lines: list[str] = []
    md_lines.append("# AnySearch 搜索报告\n")
    if query:
        md_lines.append(f"- **搜索词**: {query}")
    md_lines.append(f"- **请求 ID**: {request_id}")
    md_lines.append(f"- **结果数**: {metadata.get('total_results', 0)}")
    md_lines.append(f"- **搜索耗时**: {metadata.get('search_time_ms', '未知')} ms")
    md_lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append("---\n")

    for idx, item in enumerate(results, 1):
        title = item.get("title", "无标题")
        url = item.get("url", "")
        snippet = item.get("snippet", "无摘要")
        content = item.get("content", "")

        md_lines.append(f"## {idx}. {title}\n")
        md_lines.append(f"- **链接**: [{url}]({url})")
        md_lines.append(f"- **摘要**: {snippet}\n")
        if content:
            # 正文较长，用引用块包裹，截断到 2000 字符
            truncated = content[:2000] + "..." if len(content) > 2000 else content
            md_lines.append(f"> {truncated}\n")
        md_lines.append("---\n")

    # 确保目录存在
    save_dir = os.path.dirname(save_path)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return save_path


# ==================== 打印与转换工具函数 ====================


def format_results_to_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    """将 API 响应转换为标准化的结果列表。

    用于模块导入场景，提供统一的 title/url/snippet/content 字段格式，
    与项目其他搜索工具（doubao_search、web_search、tavily_search）保持一致。

    Args:
        response: API 返回的 JSON 字典。

    Returns:
        标准化的搜索结果列表，每项包含 title、url、snippet、content 字段。
    """
    data = response.get("data", {}) or {}
    results = data.get("results", []) or []

    formatted: list[dict[str, Any]] = []
    for item in results:
        formatted.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", ""),
            "content": item.get("content", ""),
        })

    return formatted


def print_results(
    response: dict[str, Any],
    output_json: bool = False,
    max_snippet_length: int = 500,
    max_content_length: int = 800,
) -> None:
    """打印搜索结果。

    Args:
        response: API 响应字典。
        output_json: 是否输出 JSON 格式。
        max_snippet_length: 摘要最大显示字符数。
        max_content_length: 正文最大显示字符数。
    """
    if output_json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        formatter = ResultFormatter(
            max_snippet_length=max_snippet_length,
            max_content_length=max_content_length,
        )
        print(formatter.format_search_results(response))


# ==================== 模块导入接口 ====================


def anysearch(
    query: str,
    max_results: int = DEFAULT_COUNT,
    tag: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
    zone: str = DEFAULT_ZONE,
    language: str = DEFAULT_LANGUAGE,
    format: str = DEFAULT_FORMAT,
) -> list[dict[str, Any]]:
    """AnySearch 模块接口。

    提供与项目其他搜索工具一致的调用方式，从 .env 读取配置，
    返回标准化的搜索结果列表。支持匿名调用（无 API Key 时）。

    Args:
        query: 搜索关键词（建议不超过 300 字符）。
        max_results: 返回结果数量（1-20），默认 10。
        tag: 垂直领域标签或快捷别名，如 "code"、"legal"、"finance.fundamental"。
            完整别名列表见 TAG_ALIASES，不填则通用全网搜索。
        params: tag 扩展筛选参数，如 {"library": "golang"}。
        zone: 区域，"cn" / "intl"，默认 cn。
        language: 语言，"zh-CN" / "en"，默认 zh-CN。
        format: 返回格式，"json" / "markdown"，默认 json。

    Returns:
        标准化的搜索结果列表，每项包含 title、url、snippet、content 字段。

    Raises:
        ValueError: 当 API 返回业务错误时抛出。
        requests.RequestException: 当 HTTP 请求失败时抛出。

    Example:
        >>> from tools.common.anysearch import anysearch
        >>> results = anysearch("紫金矿业 财报", max_results=5)
        >>> for r in results:
        ...     print(f"标题: {r['title']}")
        ...     print(f"链接: {r['url']}")
        ...     print(f"摘要: {r['snippet'][:100]}...")
    """
    api_key = os.getenv("ANYSEARCH_API_KEY", "")
    base_url = os.getenv("ANYSEARCH_BASE_URL", API_BASE_URL)

    # 读取 QPS 限流配置（可选）
    qps_str = os.getenv("ANYSEARCH_MAX_QPS", str(DEFAULT_QPS))
    try:
        qps = int(qps_str)
        if qps <= 0:
            qps = DEFAULT_QPS
    except ValueError:
        qps = DEFAULT_QPS

    # 读取超时配置（可选）
    timeout_str = os.getenv("ANYSEARCH_REQUEST_TIMEOUT", str(DEFAULT_TIMEOUT))
    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            timeout = DEFAULT_TIMEOUT
    except ValueError:
        timeout = DEFAULT_TIMEOUT

    # 读取默认值配置（可选，命令行参数优先）
    if max_results == DEFAULT_COUNT:
        env_max = os.getenv("ANYSEARCH_DEFAULT_MAX_RESULTS")
        if env_max:
            try:
                max_results = int(env_max)
            except ValueError:
                pass
    if zone == DEFAULT_ZONE:
        zone = os.getenv("ANYSEARCH_DEFAULT_ZONE", DEFAULT_ZONE)
    if language == DEFAULT_LANGUAGE:
        language = os.getenv("ANYSEARCH_DEFAULT_LANGUAGE", DEFAULT_LANGUAGE)
    if format == DEFAULT_FORMAT:
        format = os.getenv("ANYSEARCH_DEFAULT_FORMAT", DEFAULT_FORMAT)

    with AnySearchClient(
        api_key=api_key,
        base_url=base_url,
        qps=qps,
        timeout=timeout,
    ) as client:
        return client.search_simple(
            query=query,
            max_results=max_results,
            tag=tag,
            params=params,
            zone=zone,
            language=language,
            format=format,
        )


# ==================== 命令行入口 ====================


def _build_client_from_env() -> AnySearchClient:
    """从环境变量构建搜索客户端。

    Returns:
        初始化后的 AnySearchClient 实例（api_key 可能为空，匿名调用）。
    """
    api_key = os.getenv("ANYSEARCH_API_KEY", "")
    base_url = os.getenv("ANYSEARCH_BASE_URL", API_BASE_URL)

    qps_str = os.getenv("ANYSEARCH_MAX_QPS", str(DEFAULT_QPS))
    try:
        qps = int(qps_str)
        if qps <= 0:
            print(f"[警告] ANYSEARCH_MAX_QPS={qps} 无效，已使用默认值 {DEFAULT_QPS}。")
            qps = DEFAULT_QPS
    except ValueError:
        print(f"[警告] ANYSEARCH_MAX_QPS={qps_str} 不是有效整数，已使用默认值 {DEFAULT_QPS}。")
        qps = DEFAULT_QPS

    timeout_str = os.getenv("ANYSEARCH_REQUEST_TIMEOUT", str(DEFAULT_TIMEOUT))
    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            timeout = DEFAULT_TIMEOUT
    except ValueError:
        timeout = DEFAULT_TIMEOUT

    if not api_key:
        print("[提示] 未配置 ANYSEARCH_API_KEY，将使用匿名模式（额度极少）。")
        print("       注册免费账号可获每日 1000 次额度：")
        print("       https://anysearch.com/console/api-keys")

    return AnySearchClient(api_key=api_key, base_url=base_url, qps=qps, timeout=timeout)


def main() -> None:
    """命令行主入口函数。

    解析命令行参数，构建客户端，执行搜索，输出结果，
    可选导出 Markdown 报告。
    """
    parser = argparse.ArgumentParser(
        description="AnySearch 搜索工具（全域结构化搜索）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例:
  python tools/common/anysearch.py "紫金矿业 财报"
  python tools/common/anysearch.py "黄金价格走势 2026" --count 10
  python tools/common/anysearch.py "腾讯控股" --json
  python tools/common/anysearch.py "A股 半年报" --tag finance --export
  python tools/common/anysearch.py "民法典 民间借贷" --tag legal.case
  python tools/common/anysearch.py "FastAPI 教程" --tag code --zone intl

常用 tag 快捷别名:
  {', '.join(list(TAG_ALIASES.keys())[:15])}...

环境变量（在 .env 文件中配置）:
  ANYSEARCH_API_KEY              API 密钥（可选，不填则匿名调用）
  ANYSEARCH_BASE_URL             API 基础 URL（默认 {API_BASE_URL}）
  ANYSEARCH_MAX_QPS              QPS 限流（默认 {DEFAULT_QPS}）
  ANYSEARCH_DEFAULT_MAX_RESULTS  默认返回结果数（默认 {DEFAULT_COUNT}）
  ANYSEARCH_DEFAULT_ZONE         默认区域（默认 {DEFAULT_ZONE}）
  ANYSEARCH_DEFAULT_LANGUAGE     默认语言（默认 {DEFAULT_LANGUAGE}）
  ANYSEARCH_DEFAULT_FORMAT       默认格式（默认 {DEFAULT_FORMAT}）
  ANYSEARCH_REQUEST_TIMEOUT      请求超时秒数（默认 {DEFAULT_TIMEOUT}）
        """,
    )

    parser.add_argument("query", help="搜索关键词（建议不超过 300 字符）")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help=f"返回结果条数（1-20，默认 {DEFAULT_COUNT}）")
    parser.add_argument("--tag", help="垂直领域标签或快捷别名（如 code/legal/finance）")
    parser.add_argument("--params", help='扩展参数 JSON，如 \'{{"library":"golang"}}\'')
    parser.add_argument("--zone", choices=["cn", "intl"], default=DEFAULT_ZONE,
                        help=f"搜索区域（默认 {DEFAULT_ZONE}）")
    parser.add_argument("--language", choices=["zh-CN", "en"], default=DEFAULT_LANGUAGE,
                        help=f"语言（默认 {DEFAULT_LANGUAGE}）")
    parser.add_argument("--format", choices=["json", "markdown"], default=DEFAULT_FORMAT,
                        help=f"返回格式（默认 {DEFAULT_FORMAT}）")
    parser.add_argument("--api-key", help="API Key（覆盖 .env 配置）")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON 格式")
    parser.add_argument("--export", action="store_true",
                        help="导出 Markdown 报告到 reports/ 目录")
    parser.add_argument("--export-path", help="自定义导出路径")

    args = parser.parse_args()

    # 构建客户端（命令行参数优先于环境变量）
    if args.api_key:
        client = AnySearchClient(api_key=args.api_key)
    else:
        client = _build_client_from_env()

    # 解析扩展参数 JSON
    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"[错误] --params JSON 解析失败: {e}")
            sys.exit(1)

    logger.info(f'正在搜索: "{args.query}" ...')

    try:
        response = client.search(
            query=args.query,
            max_results=args.count,
            tag=args.tag,
            params=params,
            zone=args.zone,
            language=args.language,
            format=args.format,
        )
    except ValueError as e:
        print(f"\n[错误] {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"\n[错误] 网络请求失败: {e}")
        sys.exit(1)
    finally:
        client.close()

    # 打印结果
    print_results(response, output_json=args.json)

    # 导出 Markdown 报告
    if args.export:
        reports_dir = PROJECT_ROOT / "reports"
        reports_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 对查询关键词做简单清理作为文件名一部分
        safe_query = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in args.query[:20]
        )
        default_path = reports_dir / f"anysearch_{safe_query}_{timestamp}.md"
        save_path = args.export_path or str(default_path)
        export_to_markdown(response, save_path, query=args.query)
        print(f"\n[成功] 报告已保存至: {save_path}")


if __name__ == "__main__":
    main()
