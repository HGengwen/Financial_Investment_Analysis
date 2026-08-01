"""
豆包搜索工具（火山引擎 SearchInfinity）
======================================

本工具通过火山引擎联网搜索 API（豆包搜索）实现网络信息搜索，
作为阿里云百炼 WebSearch/Tavily 的备选方案，返回结构化搜索结果。

功能特点:
1. 使用火山引擎 TOP 网关 AK/SK 鉴权（SignatureV4 签名）。
2. 支持 Web 搜索、时间范围过滤、站点过滤、行业类型搜索。
3. 返回结构化数据：标题、链接、摘要、正文、权威度等。
4. 支持命令行调用和模块导入两种方式。
5. 支持导出 Markdown 格式搜索报告。
6. 内置客户端 QPS 限流，避免触发服务端 429 限流。

依赖库:
pip install volcengine python-dotenv requests

用法:
python tools/common/doubao_search.py "搜索关键词"
python tools/common/doubao_search.py "紫金矿业 财报" --count 10
python tools/common/doubao_search.py "黄金价格走势" --json
python tools/common/doubao_search.py "腾讯控股" --finance --export
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
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request
from volcengine.Credentials import Credentials

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DoubaoSearch")

# 加载环境变量（从项目根目录的 .env 文件）
# 本文件位于 tools/common/ 下，需向上 3 层到达项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ==================== 配置常量 ====================

# 火山引擎 TOP 网关 API 端点（AK/SK 鉴权方式）
API_HOST = "mercury.volcengineapi.com"
API_PATH = "/"
API_ACTION = "WebSearch"
API_VERSION = "2025-01-01"
API_SERVICE = "volc_torchlight_api"
API_REGION = "cn-beijing"
API_SCHEMA = "https"

# 默认 QPS 限流（火山引擎联网搜索账号维度默认 5 QPS）
DEFAULT_QPS = 5

# 默认返回结果数
DEFAULT_COUNT = 10

# 时间范围简写到 API 枚举值的映射
TIME_RANGE_MAP = {
    "day": "OneDay",
    "week": "OneWeek",
    "month": "OneMonth",
    "year": "OneYear",
}

# 权威度等级枚举值到中文描述的映射
AUTH_LEVEL_MAP = {
    1: "非常权威",
    2: "正常权威",
    3: "一般权威",
    4: "一般不权威",
}

# 行业类型选项
INDUSTRY_OPTIONS = {
    "finance": "金融",
    "game": "电子游戏",
    "gov": "政府/官媒",
}


# ==================== 搜索客户端 ====================


class DoubaoSearchClient:
    """豆包搜索客户端，封装火山引擎联网搜索 API 的鉴权与调用。

    通过火山引擎 IAM 的 AK/SK 进行 SignatureV4 签名认证，
    调用 TOP 网关 WebSearch 接口获取搜索结果。
    内置客户端 QPS 限流，避免触发服务端 429 限流错误。

    Attributes:
        ak: 火山引擎 Access Key ID。
        sk: 火山引擎 Secret Access Key。
        credentials: 签名凭证对象。
        qps: 允许的最大每秒请求数。
    """

    def __init__(self, ak: str, sk: str, qps: int = DEFAULT_QPS) -> None:
        """初始化搜索客户端。

        Args:
            ak: 火山引擎 Access Key ID。
            sk: 火山引擎 Secret Access Key。
            qps: 最大每秒请求数，默认 5（火山引擎账号维度默认限流）。
        """
        self.ak = ak
        self.sk = sk
        self.qps = qps
        # 创建签名凭证，指定服务名和区域
        self.credentials = Credentials(ak, sk, API_SERVICE, API_REGION)
        # QPS 限流相关属性
        self._min_interval = 1.0 / qps if qps > 0 else 0.0
        self._last_request_time: float = 0.0
        self._rate_lock = threading.Lock()

    def _wait_for_rate_limit(self) -> None:
        """根据 QPS 限流策略等待，确保请求间隔不小于最小间隔。

        使用线程锁保证多线程场景下的限流正确性。
        当距离上次请求的时间间隔不足时，自动睡眠等待。
        """
        if self._min_interval <= 0:
            return

        with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                wait_time = self._min_interval - elapsed
                time.sleep(wait_time)
            self._last_request_time = time.monotonic()

    def _build_signed_request(
        self, query_params: dict[str, str], body: dict[str, Any]
    ) -> Request:
        """构建并签名 HTTP 请求。

        使用火山引擎 SignatureV4 算法对请求进行签名，
        确保请求的合法性和不可篡改性。

        Args:
            query_params: URL 查询参数（Action、Version 等）。
            body: 请求体数据（搜索参数）。

        Returns:
            签名后的 Request 对象，包含认证头信息。
        """
        r = Request()
        r.set_shema(API_SCHEMA)  # 注意：SDK 方法名拼写为 set_shema
        r.set_method("POST")
        r.set_host(API_HOST)
        r.set_path(API_PATH)
        r.set_connection_timeout(10)
        r.set_socket_timeout(10)
        r.set_headers({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        r.set_query(query_params)
        r.set_body(json.dumps(body))
        # 执行 SignatureV4 签名，签名结果写入请求头
        SignerV4.sign(r, self.credentials)
        return r

    def web_search(
        self,
        query: str,
        count: int = DEFAULT_COUNT,
        time_range: Optional[str] = None,
        need_content: bool = False,
        need_url: bool = True,
        sites: Optional[str] = None,
        block_hosts: Optional[str] = None,
        auth_info_level: int = 0,
        query_rewrite: bool = False,
        content_formats: str = "markdown",
        industry: Optional[str] = None,
    ) -> dict[str, Any]:
        """执行 Web 搜索并返回结果。

        调用火山引擎联网搜索 API，获取与搜索词相关的网页搜索结果。

        Args:
            query: 搜索关键词，1~100 个字符（过长会截断）。
            count: 返回结果条数，最多 50 条，默认 10 条。
            time_range: 时间范围过滤，可选值：
                - "day": 1 天内
                - "week": 1 周内
                - "month": 1 月内
                - "year": 1 年内
                - 自定义日期范围如 "2024-01-01..2025-01-01"
            need_content: 是否仅返回有正文的结果，默认 False。
            need_url: 是否仅返回有原文链接的结果，默认 True。
            sites: 指定搜索站点范围，多个站点用 "|" 分隔，最多 20 个。
                示例: "sse.com.cn|szse.cn"
            block_hosts: 指定屏蔽的站点，多个用 "|" 分隔，最多 5 个。
            auth_info_level: 权威度限制，0 不限制，1 仅非常权威。
            query_rewrite: 是否开启 Query 改写（会增加搜索耗时）。
            content_formats: 正文返回格式，"text" 或 "markdown"。
            industry: 行业类型搜索，可选 "finance"/"game"/"gov"。

        Returns:
            API 完整响应的 JSON 字典，包含 ResponseMetadata 和 Result。

        Raises:
            RuntimeError: 当 AK/SK 未配置时抛出。
            requests.RequestException: 当 HTTP 请求失败时抛出。
        """
        # 构造 TOP 网关查询参数
        query_params = {
            "Action": API_ACTION,
            "Version": API_VERSION,
        }

        # 构造请求体
        body: dict[str, Any] = {
            "Query": query,
            "SearchType": "web",
            "Count": count,
        }

        # 构造过滤条件
        filter_obj: dict[str, Any] = {
            "NeedContent": need_content,
            "NeedUrl": need_url,
        }
        if sites:
            filter_obj["Sites"] = sites
        if block_hosts:
            filter_obj["BlockHosts"] = block_hosts
        if auth_info_level > 0:
            filter_obj["AuthInfoLevel"] = auth_info_level
        body["Filter"] = filter_obj

        # 时间范围（支持简写映射或直接传入 API 枚举值/日期范围）
        if time_range:
            body["TimeRange"] = TIME_RANGE_MAP.get(time_range, time_range)

        # Query 改写控制
        body["QueryControl"] = {"QueryRewrite": query_rewrite}

        # 正文格式
        body["ContentFormats"] = content_formats

        # 行业类型搜索
        if industry:
            body["Industry"] = industry

        # 签名并发送请求
        self._wait_for_rate_limit()
        signed_req = self._build_signed_request(query_params, body)

        # 构造完整 URL（查询参数直接拼接到 URL 中，确保与签名一致）
        url = f"{API_SCHEMA}://{API_HOST}{API_PATH}?{urlencode(query_params)}"

        response = requests.post(
            url=url,
            headers=signed_req.headers,
            data=signed_req.body,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


# ==================== 结果格式化输出 ====================


class ResultFormatter:
    """搜索结果格式化输出器。

    将 API 返回的 JSON 结果格式化为可读的终端文本输出，
    支持控制摘要/正文的显示长度。

    Attributes:
        max_summary_length: 摘要最大显示字符数。
        max_content_length: 正文最大显示字符数。
    """

    # 终端分隔线
    SEPARATOR = "=" * 70
    SUB_SEPARATOR = "-" * 70

    def __init__(
        self, max_summary_length: int = 500, max_content_length: int = 800
    ) -> None:
        """初始化格式化输出器。

        Args:
            max_summary_length: 摘要截断长度，默认 500 字符。
            max_content_length: 正文截断长度，默认 800 字符。
        """
        self.max_summary_length = max_summary_length
        self.max_content_length = max_content_length

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        """截断文本到指定长度，并添加省略号。

        Args:
            text: 原始文本。
            max_length: 最大字符数。

        Returns:
            截断后的文本，超出部分用 "..." 替代。
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
        # 检查 API 层面错误
        metadata = response.get("ResponseMetadata", {})
        error = metadata.get("Error")
        if error:
            return self._format_error(metadata, error)

        result = response.get("Result")
        if not result:
            return f"{self.SEPARATOR}\n搜索结果为空（Result 为 null）\n{self.SEPARATOR}"

        # 格式化搜索概要信息
        lines: list[str] = []
        lines.append(self.SEPARATOR)
        lines.append("  豆包搜索结果")
        lines.append(self.SEPARATOR)
        lines.append(f"  结果总数: {result.get('ResultCount', 0)}")
        lines.append(f"  搜索耗时: {result.get('TimeCost', '未知')} ms")
        lines.append(f"  日志 ID : {result.get('LogId', '未知')}")

        # 搜索上下文
        search_context = result.get("SearchContext", {})
        origin_query = search_context.get("OriginQuery", "未知")
        lines.append(f"  搜索词 : {origin_query}")
        lines.append(self.SEPARATOR)

        # 格式化每条搜索结果
        web_results = result.get("WebResults", [])
        if not web_results:
            lines.append("\n  未找到匹配的搜索结果。\n")
            return "\n".join(lines)

        for item in web_results:
            lines.append(self._format_web_item(item))
            lines.append("")

        return "\n".join(lines)

    def _format_web_item(self, item: dict[str, Any]) -> str:
        """格式化单条 Web 搜索结果。

        Args:
            item: 单条搜索结果字典（WebItem 结构）。

        Returns:
            格式化后的单条结果字符串。
        """
        sort_id = item.get("SortId", "?")
        title = item.get("Title", "无标题")
        site_name = item.get("SiteName", "未知来源")
        url = item.get("Url", "无链接")
        publish_time = item.get("PublishTime", "未知时间")
        snippet = item.get("Snippet", "")
        summary = item.get("Summary", "")
        content = item.get("Content", "")
        auth_level = item.get("AuthInfoLevel", 0)
        auth_des = item.get("AuthInfoDes", "未知")
        rank_score = item.get("RankScore", 0)
        content_formats = item.get("ContentFormats", "")

        lines: list[str] = []
        lines.append(self.SUB_SEPARATOR)
        lines.append(f"  [{sort_id}] {title}")
        lines.append(self.SUB_SEPARATOR)
        lines.append(f"  来源     : {site_name}")
        lines.append(f"  链接     : {url}")
        lines.append(f"  发布时间 : {publish_time}")
        lines.append(f"  权威度   : {auth_des}（等级 {auth_level}）")
        lines.append(f"  相关性   : {rank_score}")

        if content_formats:
            lines.append(f"  正文格式 : {content_formats}")

        # 摘要（推荐用于大模型场景，500~1000 字）
        if summary:
            lines.append(f"\n  [摘要]\n  {self._truncate(summary, self.max_summary_length)}")
        elif snippet:
            # 如果没有摘要，显示简短片段
            lines.append(f"\n  [片段]\n  {self._truncate(snippet, 200)}")

        # 正文内容（如果返回了正文）
        if content:
            lines.append(f"\n  [正文]\n  {self._truncate(content, self.max_content_length)}")

        return "\n".join(lines)

    def _format_error(self, metadata: dict, error: dict) -> str:
        """格式化错误信息。

        Args:
            metadata: 响应元数据。
            error: 错误信息字典。

        Returns:
            格式化后的错误信息字符串。
        """
        lines: list[str] = []
        lines.append(self.SEPARATOR)
        lines.append("  搜索失败 - API 返回错误")
        lines.append(self.SEPARATOR)
        lines.append(f"  请求 ID : {metadata.get('RequestId', '未知')}")
        lines.append(f"  错误码  : {error.get('Code', '未知')}")
        lines.append(f"  错误信息: {error.get('Message', '未知')}")
        lines.append(self.SEPARATOR)
        return "\n".join(lines)


def export_to_markdown(
    response: dict[str, Any], save_path: str = "search_report.md"
) -> str:
    """将搜索结果导出为 Markdown 报告文件。

    Args:
        response: API 返回的 JSON 字典。
        save_path: 保存路径，默认 "search_report.md"。

    Returns:
        保存的文件路径。
    """
    result = response.get("Result", {})
    web_results = result.get("WebResults", [])
    search_context = result.get("SearchContext", {})
    origin_query = search_context.get("OriginQuery", "未知")

    md_lines: list[str] = []
    md_lines.append("# 豆包搜索报告\n")
    md_lines.append(f"- **搜索词**: {origin_query}")
    md_lines.append(f"- **结果数**: {result.get('ResultCount', 0)}")
    md_lines.append(f"- **耗时**: {result.get('TimeCost', '未知')} ms")
    md_lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append("---\n")

    for item in web_results:
        sort_id = item.get("SortId", "?")
        title = item.get("Title", "无标题")
        site_name = item.get("SiteName", "未知")
        url = item.get("Url", "")
        publish_time = item.get("PublishTime", "未知")
        summary = item.get("Summary", "无摘要")
        auth_des = item.get("AuthInfoDes", "未知")

        md_lines.append(f"## {sort_id}. {title}\n")
        md_lines.append(f"- **来源**: {site_name}")
        md_lines.append(f"- **链接**: [{url}]({url})")
        md_lines.append(f"- **发布时间**: {publish_time}")
        md_lines.append(f"- **权威度**: {auth_des}\n")
        md_lines.append(f"> {summary}\n")
        md_lines.append("---\n")

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return save_path


def format_results_to_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    """将 API 响应转换为标准化的结果列表。

    用于模块导入场景，提供统一的 title/url/summary 字段格式，
    与项目其他搜索工具（web_search、tavily_search）保持一致。

    Args:
        response: API 返回的 JSON 字典。

    Returns:
        标准化的搜索结果列表，每项包含以下字段：
        - title: 标题
        - url: 链接
        - site_name: 来源站点名
        - publish_time: 发布时间
        - summary: 摘要
        - snippet: 片段
        - content: 正文（如有）
        - auth_level: 权威度等级
        - auth_des: 权威度描述
        - rank_score: 相关性评分
    """
    # 处理 Result 为 None 的情况（API 错误或空响应）
    result = response.get("Result") or {}
    web_results = result.get("WebResults", []) or []

    formatted: list[dict[str, Any]] = []
    for item in web_results:
        formatted.append({
            "title": item.get("Title", "无标题"),
            "url": item.get("Url", ""),
            "site_name": item.get("SiteName", ""),
            "publish_time": item.get("PublishTime", ""),
            "summary": item.get("Summary", ""),
            "snippet": item.get("Snippet", ""),
            "content": item.get("Content", ""),
            "auth_level": item.get("AuthInfoLevel", 0),
            "auth_des": item.get("AuthInfoDes", ""),
            "rank_score": item.get("RankScore", 0),
        })

    return formatted


def print_results(
    response: dict[str, Any],
    output_json: bool = False,
    max_summary_length: int = 500,
    max_content_length: int = 800,
) -> None:
    """打印搜索结果。

    Args:
        response: API 响应字典。
        output_json: 是否输出 JSON 格式。
        max_summary_length: 摘要最大显示字符数。
        max_content_length: 正文最大显示字符数。
    """
    if output_json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        formatter = ResultFormatter(
            max_summary_length=max_summary_length,
            max_content_length=max_content_length,
        )
        print(formatter.format_search_results(response))


# ==================== 模块导入接口 ====================


def doubao_search(
    query: str,
    count: int = DEFAULT_COUNT,
    time_range: Optional[str] = None,
    industry: Optional[str] = None,
    auth_info_level: int = 0,
    need_content: bool = False,
    sites: Optional[str] = None,
    block_hosts: Optional[str] = None,
    content_formats: str = "markdown",
) -> list[dict[str, Any]]:
    """豆包搜索模块接口。

    提供与项目其他搜索工具一致的调用方式，从 .env 读取凭证，
    返回标准化的搜索结果列表。

    Args:
        query: 搜索关键词，1~100 个字符。
        count: 返回结果条数，最多 50 条，默认 10 条。
        time_range: 时间范围过滤，可选 "day"/"week"/"month"/"year"
            或自定义日期范围 "2024-01-01..2025-01-01"。
        industry: 行业类型搜索，可选 "finance"/"game"/"gov"。
        auth_info_level: 权威度限制，0 不限制，1 仅非常权威。
        need_content: 是否仅返回有正文的结果，默认 False。
        sites: 指定搜索站点范围，多个站点用 "|" 分隔，最多 20 个。
        block_hosts: 指定屏蔽的站点，多个用 "|" 分隔，最多 5 个。
        content_formats: 正文返回格式，"text" 或 "markdown"。

    Returns:
        标准化的搜索结果列表，每项包含 title、url、site_name、
        publish_time、summary、snippet、content、auth_level、
        auth_des、rank_score 字段。

    Raises:
        ValueError: 当未配置 VOLC_AK 或 VOLC_SK 时抛出。

    Example:
        >>> from tools.common.doubao_search import doubao_search
        >>> results = doubao_search("紫金矿业 财报", count=5)
        >>> for r in results:
        ...     print(f"标题: {r['title']}")
        ...     print(f"链接: {r['url']}")
        ...     print(f"摘要: {r['summary'][:100]}...")
    """
    ak = os.getenv("VOLC_AK")
    sk = os.getenv("VOLC_SK")
    if not ak or not sk:
        raise ValueError("未找到有效的 VOLC_AK 或 VOLC_SK，请在 .env 文件中配置")

    # 读取 QPS 限流配置（可选）
    qps_str = os.getenv("VOLC_QPS", str(DEFAULT_QPS))
    try:
        qps = int(qps_str)
        if qps <= 0:
            qps = DEFAULT_QPS
    except ValueError:
        qps = DEFAULT_QPS

    client = DoubaoSearchClient(ak=ak, sk=sk, qps=qps)
    response = client.web_search(
        query=query,
        count=count,
        time_range=time_range,
        industry=industry,
        auth_info_level=auth_info_level,
        need_content=need_content,
        need_url=True,
        sites=sites,
        block_hosts=block_hosts,
        content_formats=content_formats,
    )

    return format_results_to_list(response)


# ==================== 命令行入口 ====================


def _build_client_from_env() -> DoubaoSearchClient:
    """从环境变量构建搜索客户端。

    Returns:
        初始化后的 DoubaoSearchClient 实例。

    Raises:
        SystemExit: 当 AK/SK 未配置时退出程序。
    """
    ak = os.getenv("VOLC_AK")
    sk = os.getenv("VOLC_SK")

    if not ak or not sk:
        print("\n错误: 未在 .env 文件中找到 VOLC_AK 或 VOLC_SK 配置。")
        print("解决方案:")
        print("1. 在项目根目录创建 .env 文件并添加:")
        print("   VOLC_AK=你的AccessKeyID")
        print("   VOLC_SK=你的SecretAccessKey")
        print("   VOLC_QPS=5  # 可选，QPS 限流")
        print("2. 或使用命令行参数: --ak xxx --sk xxx")
        sys.exit(1)

    # 读取 QPS 限流配置（可选，默认 5）
    qps_str = os.getenv("VOLC_QPS", str(DEFAULT_QPS))
    try:
        qps = int(qps_str)
        if qps <= 0:
            print(f"[警告] VOLC_QPS={qps} 无效，已使用默认值 {DEFAULT_QPS}。")
            qps = DEFAULT_QPS
    except ValueError:
        print(f"[警告] VOLC_QPS={qps_str} 不是有效整数，已使用默认值 {DEFAULT_QPS}。")
        qps = DEFAULT_QPS

    return DoubaoSearchClient(ak=ak, sk=sk, qps=qps)


def main() -> None:
    """命令行主入口函数。

    解析命令行参数，构建客户端，执行搜索，输出结果，
    可选导出 Markdown 报告。
    """
    parser = argparse.ArgumentParser(
        description="豆包搜索工具（火山引擎 SearchInfinity）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/common/doubao_search.py "紫金矿业 财报"
  python tools/common/doubao_search.py "黄金价格走势 2026" --count 10
  python tools/common/doubao_search.py "腾讯控股" --json
  python tools/common/doubao_search.py "A股 半年报" --finance --export
  python tools/common/doubao_search.py "新规" --time-range month --sites gov.cn

环境变量（在 .env 文件中配置）:
  VOLC_AK   火山引擎 Access Key ID（必需）
  VOLC_SK   火山引擎 Secret Access Key（必需）
  VOLC_QPS  QPS 限流（可选，默认 5）
        """,
    )

    parser.add_argument("query", help="搜索关键词（1~100 字符）")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help=f"返回结果条数（1~50，默认 {DEFAULT_COUNT}）")
    parser.add_argument("--time-range", choices=list(TIME_RANGE_MAP.keys()),
                        help="时间范围过滤: day/week/month/year")
    parser.add_argument("--sites", help="指定搜索站点，多个用 | 分隔")
    parser.add_argument("--block-hosts", help="屏蔽站点，多个用 | 分隔")
    parser.add_argument("--auth-level", type=int, choices=[0, 1], default=0,
                        help="权威度限制: 0=不限制, 1=仅非常权威")
    parser.add_argument("--industry", choices=list(INDUSTRY_OPTIONS.keys()),
                        help="行业类型: finance/game/gov")
    parser.add_argument("--need-content", action="store_true",
                        help="仅返回有正文的结果")
    parser.add_argument("--content-format", choices=["text", "markdown"],
                        default="markdown", help="正文返回格式（默认 markdown）")
    parser.add_argument("--query-rewrite", action="store_true",
                        help="开启 Query 改写（增加搜索耗时）")
    parser.add_argument("--finance", action="store_true",
                        help="财经定向搜索快捷选项（等同于 --industry finance --auth-level 1）")
    parser.add_argument("--ak", help="火山引擎 AK（覆盖 .env 配置）")
    parser.add_argument("--sk", help="火山引擎 SK（覆盖 .env 配置）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--export", action="store_true",
                        help="导出 Markdown 报告到 reports/ 目录")
    parser.add_argument("--export-path", help="自定义导出路径")

    args = parser.parse_args()

    # 构建客户端（命令行参数优先于环境变量）
    if args.ak and args.sk:
        client = DoubaoSearchClient(ak=args.ak, sk=args.sk)
    else:
        client = _build_client_from_env()

    # 处理财经快捷选项
    industry = args.industry
    auth_level = args.auth_level
    if args.finance:
        industry = industry or "finance"
        auth_level = max(auth_level, 1)

    logger.info(f'正在搜索: "{args.query}" ...')

    try:
        response = client.web_search(
            query=args.query,
            count=args.count,
            time_range=args.time_range,
            industry=industry,
            auth_info_level=auth_level,
            need_content=args.need_content,
            need_url=True,
            sites=args.sites,
            block_hosts=args.block_hosts,
            content_formats=args.content_format,
            query_rewrite=args.query_rewrite,
        )
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "未知"
        resp_text = e.response.text if e.response is not None else ""
        print(f"\n[错误] HTTP {status_code}: {e}")
        if resp_text:
            print(f"[响应] {resp_text[:500]}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"\n[错误] 网络请求失败: {e}")
        sys.exit(1)

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
        default_path = reports_dir / f"doubao_search_{safe_query}_{timestamp}.md"
        save_path = args.export_path or str(default_path)
        export_to_markdown(response, save_path)
        print(f"\n[成功] 报告已保存至: {save_path}")


if __name__ == "__main__":
    main()
