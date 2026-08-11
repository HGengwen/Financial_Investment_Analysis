"""
豆包搜索工具（火山引擎 SearchInfinity）
======================================

本工具通过火山引擎联网搜索 API（豆包搜索）实现网络信息搜索，
作为阿里云百炼 WebSearch/Tavily 的备选方案，返回结构化搜索结果。

功能特点:
1. 支持两种服务模式并自动切换：
   - 订阅套餐（Custom 版）：API Key Bearer Token 鉴权，open.feedcoopapi.com
   - 按量计费：AK/SK SignatureV4 签名，mercury.volcengineapi.com
2. 默认优先使用订阅套餐，额度用尽或调用失败时自动回退按量计费。
3. 支持 Web 搜索、时间范围过滤、站点过滤、行业类型搜索。
4. 返回结构化数据：标题、链接、摘要、正文、权威度等。
5. 支持命令行调用和模块导入两种方式。
6. 支持导出 Markdown 格式搜索报告。
7. 内置客户端 QPS 限流，避免触发服务端 429 限流。

依赖库:
pip install volcengine python-dotenv requests

用法:
python tools/common/doubao_search.py "搜索关键词"
python tools/common/doubao_search.py "紫金矿业 财报" --count 10
python tools/common/doubao_search.py "黄金价格走势" --json
python tools/common/doubao_search.py "腾讯控股" --finance --export
python tools/common/doubao_search.py "测试" --mode plan       # 强制仅用订阅套餐
python tools/common/doubao_search.py "测试" --mode payasyougo # 强制仅用按量计费
python tools/common/doubao_search.py "测试" --mode auto       # 自动回退（默认）

环境变量（在 .env 文件中配置）:
  VOLC_API_Key  火山引擎订阅套餐 API Key（订阅套餐模式必需）
  VOLC_AK       火山引擎 Access Key ID（按量计费模式必需）
  VOLC_SK       火山引擎 Secret Access Key（按量计费模式必需）
  VOLC_QPS      QPS 限流（可选，默认 5）
  DOUBAO_MODE   默认服务模式：auto/plan/payasyougo（可选，默认 auto）
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

# 服务模式枚举
MODE_AUTO = "auto"             # 自动：订阅套餐优先，失败回退按量计费
MODE_PLAN = "plan"             # 仅订阅套餐
MODE_PAY_AS_YOU_GO = "payasyougo"  # 仅按量计费
ALL_MODES = (MODE_AUTO, MODE_PLAN, MODE_PAY_AS_YOU_GO)

# 订阅套餐 API 端点（API Key Bearer 鉴权方式）
PLAN_API_HOST = "open.feedcoopapi.com"
PLAN_API_PATH = "/search_api/web_search"

# 按量计费 API 端点（AK/SK SignatureV4 签名鉴权方式）
PAYG_API_HOST = "mercury.volcengineapi.com"
PAYG_API_PATH = "/"
PAYG_API_ACTION = "WebSearch"
PAYG_API_VERSION = "2025-01-01"
PAYG_API_SERVICE = "volc_torchlight_api"
PAYG_API_REGION = "cn-beijing"

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

# 响应中标注实际使用服务模式的自定义字段
_RESPONSE_MODE_FIELD = "_doubao_mode"
_RESPONSE_FALLBACK_FIELD = "_doubao_fallback"


# ==================== 搜索客户端基类 ====================


class _BaseDoubaoClient:
    """豆包搜索客户端基类，封装公共的 QPS 限流与请求体构造逻辑。

    子类需实现 `_send_request` 方法，完成具体的鉴权与 HTTP 调用。
    两种服务模式（订阅套餐 / 按量计费）的请求体结构完全相同，
    差异仅在 URL、鉴权头与凭证，因此可在基类统一构造请求体。

    Attributes:
        qps: 允许的最大每秒请求数。
    """

    def __init__(self, qps: int = DEFAULT_QPS) -> None:
        """初始化基类。

        Args:
            qps: 最大每秒请求数，默认 5。
        """
        self.qps = qps
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

    @staticmethod
    def _build_request_body(
        query: str,
        count: int,
        time_range: Optional[str],
        need_content: bool,
        need_url: bool,
        sites: Optional[str],
        block_hosts: Optional[str],
        auth_info_level: int,
        query_rewrite: bool,
        content_formats: str,
        industry: Optional[str],
    ) -> dict[str, Any]:
        """构造搜索请求体（订阅套餐与按量计费共用）。

        Args:
            见 `web_search` 方法的参数说明。

        Returns:
            符合豆包搜索 API 规范的请求体字典。
        """
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

        return body

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
        """执行 Web 搜索并返回结果（基类统一入口）。

        构造请求体后委托子类 `_send_request` 完成实际 HTTP 调用，
        并在响应中标注服务模式。

        Args:
            query: 搜索关键词，1~100 个字符（过长会截断）。
            count: 返回结果条数，最多 50 条，默认 10 条。
            time_range: 时间范围过滤，可选 "day"/"week"/"month"/"year"
                或自定义日期范围 "2024-01-01..2025-01-01"。
            need_content: 是否仅返回有正文的结果，默认 False。
            need_url: 是否仅返回有原文链接的结果，默认 True。
            sites: 指定搜索站点范围，多个站点用 "|" 分隔，最多 20 个。
            block_hosts: 指定屏蔽的站点，多个用 "|" 分隔，最多 5 个。
            auth_info_level: 权威度限制，0 不限制，1 仅非常权威。
            query_rewrite: 是否开启 Query 改写（会增加搜索耗时）。
            content_formats: 正文返回格式，"text" 或 "markdown"。
            industry: 行业类型搜索，可选 "finance"/"game"/"gov"。

        Returns:
            API 完整响应的 JSON 字典，额外包含 `_doubao_mode` 字段
            标注实际使用的服务模式（plan / payasyougo）。
        """
        body = self._build_request_body(
            query=query,
            count=count,
            time_range=time_range,
            need_content=need_content,
            need_url=need_url,
            sites=sites,
            block_hosts=block_hosts,
            auth_info_level=auth_info_level,
            query_rewrite=query_rewrite,
            content_formats=content_formats,
            industry=industry,
        )

        # 限流后发送请求
        self._wait_for_rate_limit()
        response = self._send_request(body)
        # 标注服务模式，便于上游识别
        response[_RESPONSE_MODE_FIELD] = self.mode_name
        return response

    def _send_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """子类实现：发送 HTTP 请求并返回响应字典。

        Args:
            body: 已构造完成的请求体。

        Returns:
            API 响应的 JSON 字典。
        """
        raise NotImplementedError

    @property
    def mode_name(self) -> str:
        """返回服务模式名称（plan / payasyougo），子类覆盖。"""
        return "base"


# ==================== 订阅套餐客户端 ====================


class _PlanClient(_BaseDoubaoClient):
    """订阅套餐客户端，使用 API Key Bearer Token 鉴权。

    调用 open.feedcoopapi.com 的 web_search 接口，
    鉴权方式为 HTTP Header 中携带 `Authorization: Bearer <api_key>`。

    Attributes:
        api_key: 火山引擎订阅套餐 API Key。
    """

    def __init__(self, api_key: str, qps: int = DEFAULT_QPS) -> None:
        """初始化订阅套餐客户端。

        Args:
            api_key: 火山引擎订阅套餐 API Key。
            qps: 最大每秒请求数，默认 5。
        """
        super().__init__(qps=qps)
        self.api_key = api_key

    @property
    def mode_name(self) -> str:
        """返回服务模式名称。"""
        return MODE_PLAN

    def _build_headers(self) -> dict[str, str]:
        """构建请求头，包含订阅套餐 API Key 的 Bearer 鉴权信息。

        Returns:
            请求头字典，包含 Authorization 与 Content-Type。
        """
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _send_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """发送搜索请求（订阅套餐 Bearer Token 鉴权）。

        Args:
            body: 已构造完成的请求体。

        Returns:
            API 响应的 JSON 字典。

        Raises:
            requests.RequestException: 当 HTTP 请求失败时抛出。
        """
        url = f"{API_SCHEMA}://{PLAN_API_HOST}{PLAN_API_PATH}"
        headers = self._build_headers()
        response = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(body),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


# ==================== 按量计费客户端 ====================


class _PayAsYouGoClient(_BaseDoubaoClient):
    """按量计费客户端，使用 AK/SK SignatureV4 签名鉴权。

    调用火山引擎 TOP 网关 mercury.volcengineapi.com 的 WebSearch 接口，
    鉴权方式为 SignatureV4 签名。

    Attributes:
        ak: 火山引擎 Access Key ID。
        sk: 火山引擎 Secret Access Key。
        credentials: 签名凭证对象。
    """

    def __init__(self, ak: str, sk: str, qps: int = DEFAULT_QPS) -> None:
        """初始化按量计费客户端。

        Args:
            ak: 火山引擎 Access Key ID。
            sk: 火山引擎 Secret Access Key。
            qps: 最大每秒请求数，默认 5。
        """
        super().__init__(qps=qps)
        self.ak = ak
        self.sk = sk
        # 创建签名凭证，指定服务名和区域
        self.credentials = Credentials(ak, sk, PAYG_API_SERVICE, PAYG_API_REGION)

    @property
    def mode_name(self) -> str:
        """返回服务模式名称。"""
        return MODE_PAY_AS_YOU_GO

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
        r.set_host(PAYG_API_HOST)
        r.set_path(PAYG_API_PATH)
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

    def _send_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """发送搜索请求（按量计费 SignatureV4 签名鉴权）。

        Args:
            body: 已构造完成的请求体。

        Returns:
            API 响应的 JSON 字典。

        Raises:
            requests.RequestException: 当 HTTP 请求失败时抛出。
        """
        # 构造 TOP 网关查询参数
        query_params = {
            "Action": PAYG_API_ACTION,
            "Version": PAYG_API_VERSION,
        }
        signed_req = self._build_signed_request(query_params, body)

        # 构造完整 URL（查询参数直接拼接到 URL 中，确保与签名一致）
        url = f"{API_SCHEMA}://{PAYG_API_HOST}{PAYG_API_PATH}?{urlencode(query_params)}"

        response = requests.post(
            url=url,
            headers=signed_req.headers,
            data=signed_req.body,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


# ==================== 统一客户端（自动回退） ====================


class DoubaoSearchClient:
    """豆包搜索统一客户端，自动选用订阅套餐，失败回退按量计费。

    默认行为（mode="auto"）：
    1. 优先使用订阅套餐（VOLC_API_Key）发起请求。
    2. 订阅套餐调用失败（HTTP 异常 / 响应含 Error / 额度耗尽）时，
       自动回退到按量计费（VOLC_AK/VOLC_SK）重试相同查询。
    3. 回退成功时，响应中 `_doubao_fallback=True` 标注发生过回退。

    可通过 `mode` 参数强制仅使用某种模式：
    - `mode="plan"`：仅订阅套餐，不回退。
    - `mode="payasyougo"`：仅按量计费，跳过订阅套餐。

    Attributes:
        mode: 服务模式（auto/plan/payasyougo）。
        plan_client: 订阅套餐客户端（未配置 API Key 时为 None）。
        payg_client: 按量计费客户端（未配置 AK/SK 时为 None）。
        qps: QPS 限流值。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        ak: Optional[str] = None,
        sk: Optional[str] = None,
        qps: int = DEFAULT_QPS,
        mode: str = MODE_AUTO,
    ) -> None:
        """初始化统一客户端。

        凭证未提供时，对应客户端置为 None，调用时按可用性自动跳过。
        例如未配置 api_key 时，auto 模式会直接走按量计费。

        Args:
            api_key: 火山引擎订阅套餐 API Key（可选）。
            ak: 火山引擎 Access Key ID（可选）。
            sk: 火山引擎 Secret Access Key（可选）。
            qps: 最大每秒请求数，默认 5。
            mode: 服务模式，auto/plan/payasyougo，默认 auto。

        Raises:
            ValueError: 当 mode 无效，或所选模式必需的凭证均未配置时抛出。
        """
        if mode not in ALL_MODES:
            raise ValueError(
                f"无效的 mode='{mode}'，可选值: {ALL_MODES}"
            )
        self.mode = mode
        self.qps = qps

        # 初始化订阅套餐客户端
        self.plan_client: Optional[_PlanClient] = None
        if api_key:
            self.plan_client = _PlanClient(api_key=api_key, qps=qps)

        # 初始化按量计费客户端
        self.payg_client: Optional[_PayAsYouGoClient] = None
        if ak and sk:
            self.payg_client = _PayAsYouGoClient(ak=ak, sk=sk, qps=qps)

        # 校验所选模式必需的凭证是否就绪
        if mode == MODE_PLAN and self.plan_client is None:
            raise ValueError(
                "mode='plan' 需要 VOLC_API_Key，但未配置 api_key"
            )
        if mode == MODE_PAY_AS_YOU_GO and self.payg_client is None:
            raise ValueError(
                "mode='payasyougo' 需要 VOLC_AK/VOLC_SK，但未配置 ak/sk"
            )
        if mode == MODE_AUTO and self.plan_client is None and self.payg_client is None:
            raise ValueError(
                "auto 模式需要至少配置一种凭证（VOLC_API_Key 或 VOLC_AK/VOLC_SK）"
            )

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
        """执行 Web 搜索，按策略选用服务模式并自动回退。

        Args:
            query: 搜索关键词，1~100 个字符。
            count: 返回结果条数，最多 50 条，默认 10 条。
            time_range: 时间范围过滤，可选 "day"/"week"/"month"/"year"。
            need_content: 是否仅返回有正文的结果，默认 False。
            need_url: 是否仅返回有原文链接的结果，默认 True。
            sites: 指定搜索站点范围，多个站点用 "|" 分隔。
            block_hosts: 指定屏蔽的站点，多个用 "|" 分隔。
            auth_info_level: 权威度限制，0 不限制，1 仅非常权威。
            query_rewrite: 是否开启 Query 改写。
            content_formats: 正文返回格式，"text" 或 "markdown"。
            industry: 行业类型搜索，可选 "finance"/"game"/"gov"。

        Returns:
            API 完整响应的 JSON 字典，包含 `_doubao_mode` 字段标注
            实际使用的服务模式；若发生回退，含 `_doubao_fallback=True`。

        Raises:
            RuntimeError: 当所有可用模式均失败时抛出，包含两次失败的详情。
        """
        # 按模式分派调用
        if self.mode == MODE_PLAN:
            return self.plan_client.web_search(
                query=query, count=count, time_range=time_range,
                need_content=need_content, need_url=need_url,
                sites=sites, block_hosts=block_hosts,
                auth_info_level=auth_info_level, query_rewrite=query_rewrite,
                content_formats=content_formats, industry=industry,
            )
        if self.mode == MODE_PAY_AS_YOU_GO:
            return self.payg_client.web_search(
                query=query, count=count, time_range=time_range,
                need_content=need_content, need_url=need_url,
                sites=sites, block_hosts=block_hosts,
                auth_info_level=auth_info_level, query_rewrite=query_rewrite,
                content_formats=content_formats, industry=industry,
            )

        # auto 模式：订阅套餐优先，失败回退按量计费
        # 若订阅套餐不可用（未配置），直接走按量计费
        if self.plan_client is None:
            return self._call_payg(
                query=query, count=count, time_range=time_range,
                need_content=need_content, need_url=need_url,
                sites=sites, block_hosts=block_hosts,
                auth_info_level=auth_info_level, query_rewrite=query_rewrite,
                content_formats=content_formats, industry=industry,
                fallback_reason="订阅套餐未配置 API Key",
            )

        # 若按量计费不可用（未配置），直接走订阅套餐（不回退）
        if self.payg_client is None:
            return self.plan_client.web_search(
                query=query, count=count, time_range=time_range,
                need_content=need_content, need_url=need_url,
                sites=sites, block_hosts=block_hosts,
                auth_info_level=auth_info_level, query_rewrite=query_rewrite,
                content_formats=content_formats, industry=industry,
            )

        # 两种凭证都可用：先订阅套餐，失败回退按量计费
        try:
            response = self.plan_client.web_search(
                query=query, count=count, time_range=time_range,
                need_content=need_content, need_url=need_url,
                sites=sites, block_hosts=block_hosts,
                auth_info_level=auth_info_level, query_rewrite=query_rewrite,
                content_formats=content_formats, industry=industry,
            )
            # 检查业务层错误（额度耗尽、鉴权失败等）
            error = (response.get("ResponseMetadata") or {}).get("Error")
            if error:
                # 订阅套餐业务层错误，触发回退
                return self._call_payg(
                    query=query, count=count, time_range=time_range,
                    need_content=need_content, need_url=need_url,
                    sites=sites, block_hosts=block_hosts,
                    auth_info_level=auth_info_level, query_rewrite=query_rewrite,
                    content_formats=content_formats, industry=industry,
                    fallback_reason=(
                        f"订阅套餐返回错误: code={error.get('Code')}, "
                        f"message={error.get('Message')}"
                    ),
                )
            return response
        except requests.RequestException as e:
            # 订阅套餐网络/HTTP 层错误，触发回退
            return self._call_payg(
                query=query, count=count, time_range=time_range,
                need_content=need_content, need_url=need_url,
                sites=sites, block_hosts=block_hosts,
                auth_info_level=auth_info_level, query_rewrite=query_rewrite,
                content_formats=content_formats, industry=industry,
                fallback_reason=f"订阅套餐请求异常: {e}",
            )

    def _call_payg(
        self,
        query: str,
        count: int,
        time_range: Optional[str],
        need_content: bool,
        need_url: bool,
        sites: Optional[str],
        block_hosts: Optional[str],
        auth_info_level: int,
        query_rewrite: bool,
        content_formats: str,
        industry: Optional[str],
        fallback_reason: str,
    ) -> dict[str, Any]:
        """回退到按量计费客户端执行搜索。

        Args:
            query: 搜索关键词。
            count: 返回结果条数。
            time_range: 时间范围过滤。
            need_content: 是否仅返回有正文的结果。
            need_url: 是否仅返回有原文链接的结果。
            sites: 指定搜索站点范围。
            block_hosts: 屏蔽站点。
            auth_info_level: 权威度限制。
            query_rewrite: 是否开启 Query 改写。
            content_formats: 正文返回格式。
            industry: 行业类型。
            fallback_reason: 触发回退的原因描述（用于日志与响应标注）。

        Returns:
            按量计费客户端返回的响应字典，含 `_doubao_fallback=True`
            与 `_doubao_fallback_reason` 字段。

        Raises:
            RuntimeError: 当按量计费客户端未配置或调用失败时抛出。
        """
        if self.payg_client is None:
            raise RuntimeError(
                f"订阅套餐失败且按量计费未配置，无法回退。原因: {fallback_reason}"
            )
        logger.warning(
            f"订阅套餐失败，自动回退按量计费。原因: {fallback_reason}"
        )
        response = self.payg_client.web_search(
            query=query, count=count, time_range=time_range,
            need_content=need_content, need_url=need_url,
            sites=sites, block_hosts=block_hosts,
            auth_info_level=auth_info_level, query_rewrite=query_rewrite,
            content_formats=content_formats, industry=industry,
        )
        # 标注发生过回退
        response[_RESPONSE_FALLBACK_FIELD] = True
        response["_doubao_fallback_reason"] = fallback_reason
        return response


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
        # 标注服务模式与回退状态
        mode = response.get(_RESPONSE_MODE_FIELD, "")
        fallback = response.get(_RESPONSE_FALLBACK_FIELD, False)
        if mode:
            mode_label = {"plan": "订阅套餐", "payasyougo": "按量计费"}.get(
                mode, mode
            )
            mode_suffix = "（已回退）" if fallback else ""
            lines.append(f"  服务模式: {mode_label}{mode_suffix}")
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
    # 标注服务模式
    mode = response.get(_RESPONSE_MODE_FIELD, "")
    if mode:
        mode_label = {"plan": "订阅套餐", "payasyougo": "按量计费"}.get(
            mode, mode
        )
        fallback = response.get(_RESPONSE_FALLBACK_FIELD, False)
        mode_suffix = "（已回退）" if fallback else ""
        md_lines.append(f"- **服务模式**: {mode_label}{mode_suffix}")
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
    自动优先使用订阅套餐，失败回退按量计费，返回标准化结果列表。

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
        ValueError: 当未配置任何豆包搜索凭证时抛出。
        RuntimeError: 当所有可用服务模式均失败时抛出。

    Example:
        >>> from tools.common.doubao_search import doubao_search
        >>> results = doubao_search("紫金矿业 财报", count=5)
        >>> for r in results:
        ...     print(f"标题: {r['title']}")
        ...     print(f"链接: {r['url']}")
        ...     print(f"摘要: {r['summary'][:100]}...")
    """
    client = _build_client_from_env()
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


def _read_qps_from_env() -> int:
    """从环境变量读取 QPS 限流配置。

    Returns:
        QPS 整数值，配置无效时返回默认值。
    """
    qps_str = os.getenv("VOLC_QPS", str(DEFAULT_QPS))
    try:
        qps = int(qps_str)
        if qps <= 0:
            logger.warning(
                f"VOLC_QPS={qps} 无效，已使用默认值 {DEFAULT_QPS}。"
            )
            return DEFAULT_QPS
    except ValueError:
        logger.warning(
            f"VOLC_QPS={qps_str} 不是有效整数，已使用默认值 {DEFAULT_QPS}。"
        )
        return DEFAULT_QPS
    return qps


def _build_client_from_env(mode: Optional[str] = None) -> DoubaoSearchClient:
    """从环境变量构建统一搜索客户端。

    自动读取 VOLC_API_Key（订阅套餐）与 VOLC_AK/VOLC_SK（按量计费），
    按指定模式构建客户端。未配置的凭证对应客户端置为 None。

    Args:
        mode: 服务模式，auto/plan/payasyougo。为 None 时从 DOUBAO_MODE
            环境变量读取，仍未配置则默认 auto。

    Returns:
        初始化后的 DoubaoSearchClient 实例。

    Raises:
        SystemExit: 当所选模式必需的凭证均未配置时退出程序。
    """
    # 解析服务模式
    if mode is None:
        mode = os.getenv("DOUBAO_MODE", MODE_AUTO)
    if mode not in ALL_MODES:
        print(f"\n错误: 无效的 mode='{mode}'，可选值: {ALL_MODES}")
        sys.exit(1)

    api_key = os.getenv("VOLC_API_Key")
    ak = os.getenv("VOLC_AK")
    sk = os.getenv("VOLC_SK")
    qps = _read_qps_from_env()

    # 校验所选模式必需凭证
    if mode == MODE_PLAN and not api_key:
        print("\n错误: mode='plan' 需要在 .env 中配置 VOLC_API_Key。")
        sys.exit(1)
    if mode == MODE_PAY_AS_YOU_GO and (not ak or not sk):
        print("\n错误: mode='payasyougo' 需要在 .env 中配置 VOLC_AK 和 VOLC_SK。")
        sys.exit(1)
    if mode == MODE_AUTO and not api_key and (not ak or not sk):
        print("\n错误: auto 模式需要至少配置一种凭证：")
        print("  - 订阅套餐: VOLC_API_Key")
        print("  - 按量计费: VOLC_AK + VOLC_SK")
        print("请在 .env 文件中配置至少一组凭证。")
        sys.exit(1)

    # 构建客户端
    try:
        return DoubaoSearchClient(
            api_key=api_key,
            ak=ak,
            sk=sk,
            qps=qps,
            mode=mode,
        )
    except ValueError as e:
        print(f"\n错误: {e}")
        sys.exit(1)


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
  python tools/common/doubao_search.py "测试" --mode plan         # 仅订阅套餐
  python tools/common/doubao_search.py "测试" --mode payasyougo   # 仅按量计费
  python tools/common/doubao_search.py "测试" --mode auto         # 自动回退（默认）

环境变量（在 .env 文件中配置）:
  VOLC_API_Key  火山引擎订阅套餐 API Key（订阅套餐模式必需）
  VOLC_AK       火山引擎 Access Key ID（按量计费模式必需）
  VOLC_SK       火山引擎 Secret Access Key（按量计费模式必需）
  VOLC_QPS      QPS 限流（可选，默认 5）
  DOUBAO_MODE   默认服务模式：auto/plan/payasyougo（可选，默认 auto）
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
    parser.add_argument("--mode", choices=list(ALL_MODES), default=MODE_AUTO,
                        help=f"服务模式: auto(默认)/plan/payasyougo")
    parser.add_argument("--ak", help="火山引擎 AK（覆盖 .env 配置，按量计费）")
    parser.add_argument("--sk", help="火山引擎 SK（覆盖 .env 配置，按量计费）")
    parser.add_argument("--api-key", help="订阅套餐 API Key（覆盖 .env 配置）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--export", action="store_true",
                        help="导出 Markdown 报告到 reports/ 目录")
    parser.add_argument("--export-path", help="自定义导出路径")

    args = parser.parse_args()

    # 命令行凭证优先于环境变量
    api_key = args.api_key or os.getenv("VOLC_API_Key")
    ak = args.ak or os.getenv("VOLC_AK")
    sk = args.sk or os.getenv("VOLC_SK")
    qps = _read_qps_from_env()

    # 校验所选模式必需凭证
    if args.mode == MODE_PLAN and not api_key:
        print("\n错误: mode='plan' 需要配置 VOLC_API_Key（.env 或 --api-key）。")
        sys.exit(1)
    if args.mode == MODE_PAY_AS_YOU_GO and (not ak or not sk):
        print("\n错误: mode='payasyougo' 需要配置 VOLC_AK/VOLC_SK（.env 或 --ak/--sk）。")
        sys.exit(1)
    if args.mode == MODE_AUTO and not api_key and (not ak or not sk):
        print("\n错误: auto 模式需要至少配置一种凭证：")
        print("  - 订阅套餐: VOLC_API_Key（.env 或 --api-key）")
        print("  - 按量计费: VOLC_AK + VOLC_SK（.env 或 --ak/--sk）")
        sys.exit(1)

    # 构建客户端
    try:
        client = DoubaoSearchClient(
            api_key=api_key,
            ak=ak,
            sk=sk,
            qps=qps,
            mode=args.mode,
        )
    except ValueError as e:
        print(f"\n错误: {e}")
        sys.exit(1)

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
    except RuntimeError as e:
        # 所有模式均失败
        print(f"\n[错误] {e}")
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
