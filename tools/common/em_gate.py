#!/usr/bin/env python3
"""东方财富请求闸门（跨进程全局限流 / 封禁短路 / transport hook）。

背景
    仓库经 akshare 调用东方财富网（``*.eastmoney.com``）接口，东财以**出口 IP**
    做全局限流：高频或并发访问会触发 HTTP 403 或 ``RemoteDisconnected``，且封禁
    期间继续重试会延长封禁。仓库的多子代理技能会并行启动多个独立 Python 进程，
    进程内限流器完全失效，导致 N 倍 QPS 叠加——这是子代理场景下的常态。

设计要点（与《AKShare东方财富反爬限流改进方案.md》§1~§2 对齐）
    1. **锁粒度 = 单个 HTTP 请求**（非逻辑调用）：akshare 内部翻页会连发多次
       请求，按请求粒度持锁才能让翻页也被节流，因此不需要可重入锁；
    2. **锁内只做节奏 sleep**（≤ ``EM_GATE_MAX_HOLD_SECONDS``），**不做退避重试**：
       否则一个进程重试会长时间占锁，其余 N-1 个进程全线阻塞；等待量超硬上限时
       立即还锁，锁外短退避后重取；
    3. **transport hook 注入点 = ``requests.sessions.Session.request``**：它是
       ``requests.get`` 与显式 ``Session`` 的唯一汇聚点，patch 此处才能 100%
       覆盖 akshare 内部 1125 处裸调与 19 处 ``Session``；hook 异常透明——非东财
       请求原样透传、不改变返回类型、不吞业务异常，且 ``install()`` 幂等；
    4. **封禁短路**：识别 HTTP 403 / ``RemoteDisconnected`` / 「Remote end closed
       connection」文本 → **绝不重试**，仅累加 ``consecutive_ban`` 与 ``totals.ban``；
    5. **状态跨进程共享**： ``data/.locks/em_gate_state.json``（锁内写 + ``os.replace``
       原子替换），跨进程互斥用 ``filelock``（不手写 fcntl/msvcrt）。

范围说明
    本模块为方案 P0 的「闸门骨架 + 降级语义」：跨进程锁 / 最小间隔 + 抖动 /
    滑窗预算 / 封禁短路 / transport hook / 观测子命令 / **统一降级载荷**
    （§3.4：闸门拒绝一律输出 ``success=false`` + ``meta.gate`` + 可执行
    ``fallback_cmd``，绝不伪造 ``success=true``；工具侧漏改亦有进程级兜底）。
    步骤 4（P1 首项）另落地**熔断器**：连续封禁达 ``EM_GATE_CIRCUIT_THRESHOLD``
    即打开熔断（冷却窗口 ``EM_GATE_CIRCUIT_COOLDOWN_MIN`` 分钟内一律拒绝、
    **不取锁**），冷却到期后转入**半开**态并放行**唯一一个探测位**——探测成功
    即关闭熔断，探测再被封禁则立即重开冷却。步骤 5（P1 次项）另落地**请求指纹
    与代理策略**：东财请求统一注入 ``User-Agent`` / ``Referer`` /
    ``Connection: keep-alive``（**不覆盖调用方显式 headers**）；
    ``EM_GATE_BYPASS_PROXY=1`` 时东财请求剥离 ``HTTP(S)_PROXY`` 直连；若该次
    尝试因**连接类错误**失败（**非**封禁信号）则剥离代理**直连重试一次**。
    步骤 6（P2 首项）另落地**主机回退链**（方案 §2.5）：``push2his`` / ``push2``
    连续出现 ``_HOST_FAIL_THRESHOLD`` 次**连接类错误**（**非**封禁信号）即切
    ``push2delay.eastmoney.com`` 并写 ``host_degraded_until = now + 600s``，
    降级期内**直接改走回退主机**（不再每次先失败一次）；**封禁信号不触发回退**
    （全站级，换主机无用），仅打断连续计数。步骤 6 加固另落地**东财请求强制
    IPv4**（``EM_GATE_FORCE_IPV4=1``，默认开）：东财部分主机组的 IPv6 路径在
    实测中不可用（TCP/TLS 均成功、请求发出后服务端回空响应 → 表现为
    ``RemoteDisconnected``，会被误判为**封禁信号**进而触发熔断），故在受管控
    请求内把 urllib3 的地址族选择限定为 ``AF_INET``；**非东财请求与东财以外的
    所有调用完全不受影响**（线程局部开关，仅包裹本次受管控调用）。
    步骤 7（P2 次项）另落地**监控加固**（方案 §9「监控 ``em_gate report``」）：
    ``report`` 输出**全量行数与扫描行数分离**（``log.total_lines`` /
    ``log.scanned`` / ``log.truncated``）——修正原先把**尾部截断计数**当作
    总量的误导语义；补齐与 ``status`` 对齐的**预算 / 熔断相位**；并给出可直接
    判读的 ``health`` 判定（``ok`` / ``warn`` / ``critical`` + ``reasons``）。

    本模块**不 import akshare**（保持轻量：patch ``requests`` 即已覆盖 akshare），
    且 **import 期无任何副作用**（不改配置、不建目录、不 patch）。

Usage:
    {py} tools/common/em_gate.py status     # 观测当前预算/闸门状态
    {py} tools/common/em_gate.py report     # 汇总指标日志与累计计数
    {py} tools/common/em_gate.py reset      # 清空状态（滑窗/封禁计数/熔断）
    {py} -m pytest tests/common/test_em_gate.py -q
"""

from __future__ import annotations

import argparse
import functools
import json
import logging
import os
import random
import re
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

try:  # 环境变量加载：缺失时降级为「只读系统环境」
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失分支
    load_dotenv = None  # type: ignore[assignment]

try:
    import requests
except ImportError:  # pragma: no cover - requests 是 akshare/yfinance 传递依赖
    requests = None  # type: ignore[assignment]

try:  # 跨进程文件锁：方案要求用 filelock，禁止手写 fcntl/msvcrt
    from filelock import FileLock
    from filelock import Timeout as _FileLockTimeout
except ImportError:  # pragma: no cover - 依赖缺失分支（安装后即恢复）
    FileLock = None  # type: ignore[assignment]
    _FileLockTimeout = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# 项目根目录（本文件位于 tools/common/ 下，上溯三层即根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_dotenv() -> None:
    """加载项目根目录 ``.env``（不覆盖已有系统环境变量）。

    ``override=False`` 保证显式设置的环境变量（含测试内 monkeypatch）
    优先于 ``.env`` 文件，便于测试与临时覆盖。
    """
    if load_dotenv is None:
        return
    load_dotenv(_PROJECT_ROOT / ".env", override=False)


# 读取 .env：仅读环境变量，不建目录、不 patch、不改配置（import 期零副作用）
_load_dotenv()


# ---------------------------------------------------------------------------
# 配置读取（沿用 fx_rate.py 顶部的 _parse_*_env 范式）
# ---------------------------------------------------------------------------
def _parse_int_env(var_name: str, default: int) -> int:
    """从环境变量读取整数配置，非法值或缺失时回退默认值。

    Args:
        var_name: 环境变量名。
        default: 默认值（解析失败时使用）。

    Returns:
        解析后的整数。
    """
    raw = os.getenv(var_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        # 允许 ".env" 中带行尾注释已被 dotenv 剥离；此处仍做一次 strip
        return int(raw.strip())
    except (TypeError, ValueError):
        logger.warning("[env] %s 配置值 %r 非法，使用默认值 %s", var_name, raw, default)
        return default


def _parse_float_env(var_name: str, default: float) -> float:
    """从环境变量读取浮点配置，非法值或缺失时回退默认值。

    Args:
        var_name: 环境变量名。
        default: 默认值（解析失败时使用）。

    Returns:
        解析后的浮点数。
    """
    raw = os.getenv(var_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        logger.warning("[env] %s 配置值 %r 非法，使用默认值 %s", var_name, raw, default)
        return default


def _parse_bool_env(var_name: str, default: bool) -> bool:
    """从环境变量读取布尔配置（``0/false/no/off`` 为假，其余为真）。

    Args:
        var_name: 环境变量名。
        default: 默认值（缺失时使用）。

    Returns:
        解析后的布尔值。
    """
    raw = os.getenv(var_name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _parse_path_env(var_name: str, default: str) -> Path:
    """从环境变量读取路径配置，相对路径按项目根目录解析。

    Args:
        var_name: 环境变量名。
        default: 默认相对路径（相对项目根目录）。

    Returns:
        绝对路径 ``Path``（仅解析，不创建目录）。
    """
    raw = os.getenv(var_name)
    text = raw.strip() if raw and raw.strip() else default
    path = Path(text)
    return path if path.is_absolute() else (_PROJECT_ROOT / path)


@dataclass(frozen=True)
class GateConfig:
    """东财闸门配置（一次性从环境变量解析，可由 ``_reload_config()`` 刷新）。

    Attributes:
        enabled: 总开关，``False`` 时完全退化为改造前行为。
        min_interval: 两次东财请求的最小间隔（秒）。
        jitter_max: 随机抖动上限（秒），避免固定周期指纹。
        lock_timeout: 取锁超时（秒），超时抛 ``EmGateTimeout``。
        max_hold_seconds: 单请求在锁内最大停留（秒），超出则还锁退避重取。
        budget_per_min: 每分钟请求预算。
        budget_per_5min: 每 5 分钟请求预算。
        circuit_threshold: 连续封禁信号阈值，达到即打开熔断。
        circuit_cooldown_min: 熔断冷却时长（分钟）；到期后转入半开单探测。
        bypass_proxy: 是否对东财剥离代理（步骤 5 已实装）。实现上把 ``http`` /
            ``https`` 置为空串以压过 requests 的 env 代理合并（传 ``{}`` 会被
            ``setdefault`` 回填，等于没绕过）。
        host_fallback: 是否启用主机回退链（步骤 6 已实装）。
        force_ipv4: 东财请求是否**强制 IPv4**（步骤 6 加固）。开启时把 urllib3 的
            地址族选择限定为 ``AF_INET``，规避东财部分主机组 IPv6 路径不可用导致的
            ``RemoteDisconnected``（会被误判为封禁信号）；仅作用于受管控的东财请求。
        state_file: 跨进程状态文件路径。
        lock_file: 跨进程锁文件路径。
        log_file: 指标日志（jsonl）路径。
    """

    enabled: bool = True
    min_interval: float = 1.2
    jitter_max: float = 1.0
    lock_timeout: float = 60.0
    max_hold_seconds: float = 8.0
    budget_per_min: int = 60
    budget_per_5min: int = 150
    circuit_threshold: int = 3
    circuit_cooldown_min: int = 30
    bypass_proxy: bool = True
    host_fallback: bool = True
    force_ipv4: bool = True
    state_file: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "data/.locks/em_gate_state.json"
    )
    lock_file: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "data/.locks/em_gate.lock"
    )
    log_file: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "data/logs/em_gate.jsonl"
    )

    @classmethod
    def from_env(cls) -> "GateConfig":
        """按方案 §5 配置组从环境变量构造配置对象。

        Returns:
            ``GateConfig`` 实例（路径类配置一律解析为绝对路径）。
        """
        return cls(
            enabled=_parse_bool_env("EM_GATE_ENABLED", True),
            min_interval=_parse_float_env("EM_GATE_MIN_INTERVAL", 1.2),
            jitter_max=_parse_float_env("EM_GATE_JITTER_MAX", 1.0),
            lock_timeout=_parse_float_env("EM_GATE_LOCK_TIMEOUT", 60.0),
            max_hold_seconds=_parse_float_env("EM_GATE_MAX_HOLD_SECONDS", 8.0),
            budget_per_min=_parse_int_env("EM_GATE_BUDGET_PER_MIN", 60),
            budget_per_5min=_parse_int_env("EM_GATE_BUDGET_PER_5MIN", 150),
            circuit_threshold=_parse_int_env("EM_GATE_CIRCUIT_THRESHOLD", 3),
            circuit_cooldown_min=_parse_int_env("EM_GATE_CIRCUIT_COOLDOWN_MIN", 30),
            bypass_proxy=_parse_bool_env("EM_GATE_BYPASS_PROXY", True),
            host_fallback=_parse_bool_env("EM_GATE_HOST_FALLBACK", True),
            force_ipv4=_parse_bool_env("EM_GATE_FORCE_IPV4", True),
            state_file=_parse_path_env(
                "EM_GATE_STATE_FILE", "data/.locks/em_gate_state.json"
            ),
            lock_file=_parse_path_env("EM_GATE_LOCK_FILE", "data/.locks/em_gate.lock"),
            log_file=_parse_path_env("EM_GATE_LOG_FILE", "data/logs/em_gate.jsonl"),
        )


# 模块级配置单例（import 期解析，但不产生任何文件系统副作用）
_CONFIG: GateConfig = GateConfig.from_env()

# 滑窗长度（秒）：与 §0.1 预算口径一致；测试可临时改小以加速验证
_WINDOW_MIN_SECONDS = 60.0
_WINDOW_5MIN_SECONDS = 300.0

# 锁内等待量超过硬上限时，锁外退避步长（秒）：防止长占锁
_LONG_WAIT_BACKOFF = 0.2

# 进程内线程互斥：filelock 实例不可重入，同进程多线程需先过本锁
_LOCAL_LOCK = threading.Lock()

# Session.request 的原始实现（install() 装载时记录，供幂等/还原使用）
_ORIGINAL_SESSION_REQUEST: Optional[Callable[..., Any]] = None

# --- 东财请求强制 IPv4（步骤 6 加固）----------------------------------------
# urllib3 的地址族选择钩子（原始实现，install() 装载时记录，供幂等/还原使用）
_ORIGINAL_ALLOWED_GAI_FAMILY: Optional[Callable[[], int]] = None
# 线程局部开关：仅当本次为**受管控的东财请求**时置位，故非东财调用零影响
_FORCE_IPV4_LOCAL = threading.local()

# 降级元信息在业务异常上的附加属性名
GATE_META_ATTR = "em_gate"


def _scoped_allowed_gai_family() -> int:
    """urllib3 地址族钩子的线程局部包装（东财请求可能被限定为 IPv4）。

    仅当本线程正处在受管控的东财请求内（``_FORCE_IPV4_LOCAL.active`` 为真）时返回
    ``AF_INET``，其余情况一律交还原实现——从而**不影响新浪 / 巨潮 / yfinance 等
    任何非东财请求**。

    Returns:
        ``socket.AF_INET`` 或 urllib3 原实现的返回值。
    """
    if getattr(_FORCE_IPV4_LOCAL, "active", False):
        return socket.AF_INET
    if _ORIGINAL_ALLOWED_GAI_FAMILY is not None:
        return _ORIGINAL_ALLOWED_GAI_FAMILY()
    return socket.AF_UNSPEC


def _install_force_ipv4_hook() -> bool:
    """装载 urllib3 地址族钩子（幂等）。

    ``urllib3.util.connection.create_connection()`` 内部以模块全局名调用
    ``allowed_gai_family()`` 并把它作为 ``family`` 传给 ``socket.getaddrinfo``，
    因此 patch 该属性即为官方支持的地址族选择点。

    Returns:
        True 表示钩子已装载（或此前已装载）；urllib3 不可用时返回 False。
    """
    global _ORIGINAL_ALLOWED_GAI_FAMILY
    if _ORIGINAL_ALLOWED_GAI_FAMILY is not None:
        return True  # 幂等：重复调用不叠加包装
    try:
        from urllib3.util import connection as _u3_connection
    except ImportError:  # pragma: no cover - urllib3 为 requests 必装传递依赖
        logger.warning("[em_gate] urllib3 不可用，跳过强制 IPv4 钩子装载")
        return False
    _ORIGINAL_ALLOWED_GAI_FAMILY = _u3_connection.allowed_gai_family
    _u3_connection.allowed_gai_family = _scoped_allowed_gai_family
    return True


def _restore_force_ipv4_hook() -> None:
    """还原 urllib3 地址族钩子（总开关关闭时调用，保证完全退化）。"""
    global _ORIGINAL_ALLOWED_GAI_FAMILY
    if _ORIGINAL_ALLOWED_GAI_FAMILY is None:
        return
    try:
        from urllib3.util import connection as _u3_connection

        _u3_connection.allowed_gai_family = _ORIGINAL_ALLOWED_GAI_FAMILY
    except ImportError:  # pragma: no cover - 运行期不会发生
        pass
    _ORIGINAL_ALLOWED_GAI_FAMILY = None


def _reload_config() -> GateConfig:
    """按当前环境变量重新解析配置（供测试与运行期切换配置使用）。

    Returns:
        刷新后的 ``GateConfig``。
    """
    global _CONFIG
    _CONFIG = GateConfig.from_env()
    return _CONFIG


# ---------------------------------------------------------------------------
# 异常类型：闸门拒绝一律为 EmGateError 子类，便于调用方统一捕获降级
# ---------------------------------------------------------------------------
class EmGateError(RuntimeError):
    """东财闸门异常基类。"""


class EmGateTimeout(EmGateError):
    """取锁超时（``EM_GATE_LOCK_TIMEOUT`` 内未取得跨进程锁）。"""


class EmCircuitOpen(EmGateError):
    """熔断拒绝：冷却窗口内，或半开探测位已被其他请求占用。"""


class EmGateBudgetExhausted(EmGateError):
    """滑窗预算不足（分钟 / 5 分钟预算已用尽）。"""


# ---------------------------------------------------------------------------
# 降级语义（方案 §3.4）：闸门拒绝 → 统一 success=false 载荷 + 可执行替代命令
# ---------------------------------------------------------------------------
# 异常类型 → 降级载荷 ``meta.gate`` 取值（顺序敏感：具体类型在前）
_GATE_CODE_BY_TYPE: Tuple[Tuple[type, str], ...] = (
    (EmCircuitOpen, "circuit_open"),
    (EmGateTimeout, "gate_timeout"),
    (EmGateBudgetExhausted, "budget_exhausted"),
    (EmGateError, "gate_error"),
)

# 闸门拒绝的文本标记：本模块抛出的异常消息一律含这些前缀，使异常被工具 /
# akshare / 缓存层 catch 后转成字符串时仍可判定为闸门拒绝（而非业务错误）。
_GATE_MESSAGE_MARKERS: Tuple[str, ...] = ("东财闸门", "东方财富拒绝请求")

# 进程内最近一次闸门拒绝快照（供进程退出兜底输出统一降级载荷）
_LAST_REJECTION: Optional[Dict[str, Any]] = None

# 闸门拒绝快照有效期（秒）：超期后不再作为进程退出兜底的依据
_REJECTION_TTL_S = 300.0


# ---------------------------------------------------------------------------
# 异常分类（自 fx_rate.py 迁出：_is_transient / _is_ban_signal）
# ---------------------------------------------------------------------------
def is_transient(exc: BaseException) -> bool:
    """判断异常是否为可重试的瞬时网络异常。

    仅 ``requests`` 网络类异常（连接中断、超时、代理错误等）视为瞬时；
    非网络异常（如 KeyError、参数错误）不重试。

    Args:
        exc: 捕获到的异常。

    Returns:
        True 表示可重试的瞬时网络异常。
    """
    if requests is None:
        return False
    return isinstance(exc, requests.exceptions.RequestException)


def is_ban_signal(exc: BaseException) -> bool:
    """判断异常是否为服务端封禁（限流拉黑）信号。

    东财对高频调用会临时封禁 IP，典型表现为 ``RemoteDisconnected``（连接被
    服务端直接断开）。封禁期间重试毫无意义且会延长封禁时长，因此识别到该信号
    时必须立即放弃重试、直接降级到备用源。判定范围（方案 §2.1）：
    HTTP 403、``RemoteDisconnected``、异常文本含「Remote end closed connection」。

    Args:
        exc: 捕获到的异常。

    Returns:
        True 表示疑似服务端封禁信号。
    """
    if requests is None:
        return False
    # RemoteDisconnected 是 ConnectionError 子类，需在通用网络异常判定前识别；
    # 该异常也可能被裸抛出（未经 requests 包装），故不局限于 ConnectionError 分支
    try:
        from http.client import RemoteDisconnected
    except ImportError:  # pragma: no cover - 标准库模块，理论上不会缺失
        RemoteDisconnected = None  # type: ignore[assignment, misc]
    if RemoteDisconnected is not None and isinstance(exc, RemoteDisconnected):
        return True
    # 回退：异常消息文本匹配（覆盖被 requests 包装但保留原文的场景）
    if "Remote end closed connection" in str(exc):
        return True
    # HTTP 403 通常也表示服务端拒绝（限流/风控）
    if isinstance(exc, requests.exceptions.HTTPError):
        if getattr(exc.response, "status_code", None) == 403:
            return True
    return False


def is_connection_error(exc: BaseException) -> bool:
    """判断异常是否为「连接类错误」（可安全改为直连重试）。

    步骤 5 的「代理失败 → 直连重试」仅对本类错误生效（方案 §9 P1）。判定
    **必须先排除封禁信号**：``RemoteDisconnected`` 同属 ``ConnectionError``，
    但它表示服务端拉黑——换直连无用且加重惩罚（方案 §10.3 禁止对封禁重试）。

    Args:
        exc: 捕获到的异常。

    Returns:
        True 表示属于可直连重试的连接类错误。
    """
    if is_ban_signal(exc):
        return False
    if requests is not None and isinstance(
        exc,
        (
            requests.exceptions.ProxyError,
            requests.exceptions.ConnectionError,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.Timeout,
        ),
    ):
        return True
    # 裸 socket / OS 级连接错误（未经 requests 包装）
    return isinstance(exc, (ConnectionError, TimeoutError))


# ---------------------------------------------------------------------------
# 闸门拒绝判定与统一降级载荷（方案 §3.4）
# ---------------------------------------------------------------------------
def is_gate_error(exc: BaseException) -> bool:
    """判断异常是否为「闸门拒绝」（而非业务错误）。

    判定依据（任一命中即视为闸门拒绝）：
    ① 异常本身是 ``EmGateError`` 子类；
    ② 异常上带有闸门标注（``guarded`` 附加的 ``em_gate`` 元信息，如封禁信号）；
    ③ 异常消息含闸门标记文本——覆盖「闸门异常被工具 / akshare / 缓存层 catch
       后转成字符串再包装」的情形（此时类型信息已丢失，仅剩消息文本）。

    Args:
        exc: 捕获到的异常。

    Returns:
        True 表示属于闸门拒绝，应按方案 §3.4 输出统一降级载荷。
    """
    if isinstance(exc, EmGateError):
        return True
    meta = getattr(exc, GATE_META_ATTR, None)
    if isinstance(meta, dict) and meta.get("gate") == "ban_signal":
        return True
    return any(marker in str(exc) for marker in _GATE_MESSAGE_MARKERS)


def gate_code(exc: Optional[BaseException] = None) -> str:
    """解析降级载荷中的 ``meta.gate`` 取值。

    Args:
        exc: 闸门拒绝异常；为 None 时取进程内最近一次拒绝快照。

    Returns:
        ``circuit_open`` / ``gate_timeout`` / ``budget_exhausted`` /
        ``gate_error`` / ``ban_signal`` / ``error``。
    """
    if exc is None:
        if _LAST_REJECTION is not None:
            return str(_LAST_REJECTION.get("gate") or "gate_error")
        return "gate_error"
    for exc_type, code in _GATE_CODE_BY_TYPE:
        if isinstance(exc, exc_type):
            return code
    meta = getattr(exc, GATE_META_ATTR, None)
    if isinstance(meta, dict) and meta.get("gate") == "ban_signal":
        return "ban_signal"
    return "gate_error" if is_gate_error(exc) else "error"


def _record_rejection(error: BaseException) -> None:
    """记录进程内最近一次闸门拒绝（不打印、不改变控制流）。

    Args:
        error: 闸门拒绝异常。
    """
    global _LAST_REJECTION
    _LAST_REJECTION = {
        "gate": gate_code(error),
        "message": str(error),
        "ts": time.time(),
        "reported": False,
    }


def _has_fresh_rejection() -> bool:
    """判断是否存在「尚未输出」且在有效期内的闸门拒绝记录。

    Returns:
        True 表示进程退出兜底仍需输出降级载荷。
    """
    if _LAST_REJECTION is None or _LAST_REJECTION.get("reported"):
        return False
    return (time.time() - float(_LAST_REJECTION.get("ts") or 0.0)) <= _REJECTION_TTL_S


def degraded_payload(
    exc: Optional[BaseException] = None,
    *,
    tool: str,
    fallback_cmd: str = "",
    stale: bool = True,
    cache_age_days: Optional[int] = None,
) -> Dict[str, Any]:
    """构造方案 §3.4 的统一降级载荷（**禁止伪造 ``success=true``**）。

    Args:
        exc: 闸门拒绝异常；为 None 时使用进程内最近一次拒绝快照。
        tool: 工具标识（写入 ``meta.tool``）。
        fallback_cmd: 可直接执行的替代命令（降级必须自带出路）。
        stale: 数据是否可能过期（缓存降级时为 True）。
        cache_age_days: 本地缓存数据龄（天）；未知时为 None。

    Returns:
        含 ``success`` / ``error`` / ``meta`` 的字典。
    """
    if exc is not None:
        detail = str(exc)
        code = gate_code(exc)
    else:
        snapshot = _LAST_REJECTION or {}
        detail = str(snapshot.get("message") or "闸门拒绝")
        code = str(snapshot.get("gate") or "gate_error")
    # 统一错误文案前缀（对齐方案 §3.4 示例「东财闸门拒绝：熔断冷却中（剩余 24 分钟）」）
    error = detail if detail.startswith("东财闸门") else f"东财闸门拒绝：{detail}"
    return {
        "success": False,
        "error": error,
        "meta": {
            "tool": tool,
            "gate": code,
            "stale": stale,
            "cache_age_days": cache_age_days,
            "fallback_cmd": fallback_cmd,
            "timestamp": datetime.now().isoformat(),
        },
    }


def emit_rejection(
    exc: Optional[BaseException] = None,
    *,
    tool: str,
    fallback_cmd: str = "",
    stale: bool = True,
    cache_age_days: Optional[int] = None,
    stream: Any = None,
) -> bool:
    """闸门拒绝时输出统一降级载荷（方案 §3.4）；非闸门拒绝不做任何输出。

    Args:
        exc: 捕获到的异常；为 None 时按进程内最近一次拒绝快照判定。
        tool: 工具标识。
        fallback_cmd: 可直接执行的替代命令。
        stale: 数据是否可能过期。
        cache_age_days: 本地缓存数据龄（天）。
        stream: 输出流（默认 ``sys.stderr``，与各工具既有错误输出一致）。

    Returns:
        True 表示已输出降级载荷（调用方应停止重试并按 ``fallback_cmd`` 换源）。
    """
    if exc is not None:
        if not is_gate_error(exc):
            return False
    elif not _has_fresh_rejection():
        return False
    payload = degraded_payload(
        exc,
        tool=tool,
        fallback_cmd=fallback_cmd,
        stale=stale,
        cache_age_days=cache_age_days,
    )
    print(
        json.dumps(payload, ensure_ascii=False),
        file=stream if stream is not None else sys.stderr,
    )
    if _LAST_REJECTION is not None:
        _LAST_REJECTION["reported"] = True
    return True


# ---------------------------------------------------------------------------
# host 过滤：仅 ``*.eastmoney.com``（含 .com.cn）进入闸门
# ---------------------------------------------------------------------------
_EM_HOST_RE = re.compile(r"(^|\.)eastmoney\.com(\.cn)?$")


def _extract_host(url: Any) -> str:
    """从 URL 中提取主机名（小写，无端口）。

    Args:
        url: 完整 URL 或主机名。

    Returns:
        主机名（解析失败时返回空串）。
    """
    if not isinstance(url, str) or not url:
        return ""
    try:
        host = urlsplit(url if "//" in url else f"//{url}").hostname or ""
    except ValueError:  # pragma: no cover - 极端畸形 URL
        return ""
    return host.lower()


def is_em_url(url: Any) -> bool:
    """判断 URL 是否属于东方财富域名（host 白名单）。

    Args:
        url: 请求 URL。

    Returns:
        True 表示需要进入闸门（东财主域或其子域）。
    """
    host = _extract_host(url)
    return bool(host) and bool(_EM_HOST_RE.search(host))


# ---------------------------------------------------------------------------
# 主机回退链（方案 §2.5 / §9 P2）
# ---------------------------------------------------------------------------
#: 主主机 → 回退主机（``push2delay`` 字段与时间字段兼容，代价是数据延迟）
_HOST_FALLBACK_MAP: Dict[str, str] = {
    "push2his.eastmoney.com": "push2delay.eastmoney.com",
    "push2.eastmoney.com": "push2delay.eastmoney.com",
}

#: 触发回退所需的**连续**连接类错误次数（**非**封禁信号；方案 §2.5）
_HOST_FAIL_THRESHOLD = 2

#: 回退窗口时长（秒）：期内直接走回退主机，不再试死主机（方案 §2.5：10 分钟）
_HOST_DEGRADED_SECONDS = 600.0


def _fallback_host(host: str) -> Optional[str]:
    """返回主主机对应的回退主机。

    Args:
        host: 主机名（大小写不敏感）。

    Returns:
        回退主机名；无映射返回 None。
    """
    return _HOST_FALLBACK_MAP.get((host or "").lower())


def _swap_host(url: Any, new_host: str) -> Any:
    """把 URL 的主机替换为 ``new_host``（保持 scheme / path / query 不变）。

    Args:
        url: 原始 URL（非字符串原样返回）。
        new_host: 目标主机名。

    Returns:
        替换主机后的 URL。
    """
    if not isinstance(url, str) or not new_host:
        return url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return url
    return urlunsplit(
        (parts.scheme, new_host, parts.path, parts.query, parts.fragment)
    )


def _pick_fallback_host(
    config: GateConfig, state: Dict[str, Any], url: Any, now: float
) -> Optional[str]:
    """判定本次请求是否应改走回退主机（方案 §2.5）。

    仅在「开关开启 + 处于降级窗口内 + 当前主主机有映射」时才改写；窗口到期后
    自然回到主主机（无需显式恢复），由下一次请求给出新的 ``hot_host``。

    Args:
        config: 当前配置（读取 ``host_fallback`` 开关）。
        state: 锁内读到的权威状态。
        url: 请求 URL。
        now: 当前时间戳。

    Returns:
        需改写的回退主机名；无需改写返回 None。
    """
    if not config.host_fallback:
        return None
    if float(state.get("host_degraded_until") or 0.0) <= now:
        return None
    host = _extract_host(url)
    fallback = _fallback_host(host)
    return fallback if fallback and fallback != host else None


def _update_host_health(
    state: Dict[str, Any],
    url: Any,
    exc: Optional[BaseException],
    *,
    ban: bool,
    enabled: bool,
    degraded: bool,
    now: float,
) -> Optional[str]:
    """按本次结果维护主机健康度（方案 §2.5）。

    - **封禁信号**：不触发回退（全站级，换主机无用），但会打断「连续连接类错误」；
    - **连接类错误**（非封禁，主主机）：连续计数 +1，达 ``_HOST_FAIL_THRESHOLD`` 即切
      回退主机、写 ``host_degraded_until``、``totals.degraded`` +1，并清零连续计数；
    - **连接类错误**（非封禁，且本次已在回退主机上）：连续计数达阈值即**放弃降级窗口**
      回主主机——回退主机自身也连不上时，把请求钉在死主机上 10 分钟是有害的；
    - **其余结果**（成功 / 业务错误）：清零连续计数。

    ``hot_host`` 仅在本函数触发回退时改写为回退主机（其余情况由 ``_record_outcome``
    按实际请求主机维护）。

    Args:
        state: 锁内读到的权威状态（原地修改）。
        url: 请求 URL。
        exc: 业务异常（成功时为 None）。
        ban: 本次是否为封禁信号（含 hook 判定的 HTTP 403）。
        enabled: 主机回退开关（关闭时**完全不动**主机状态，避免留下假的降级标记）。
        degraded: 本次请求是否由降级窗口改写到了回退主机。
        now: 当前时间戳。

    Returns:
        本次触发的回退主机名；未触发返回 None。
    """
    if not enabled:
        return None
    host = _extract_host(url)

    if ban:
        state["host_fail_count"] = 0  # 封禁不回退，但打断连续计数
        return None

    if exc is None or not is_connection_error(exc):
        state["host_fail_count"] = 0
        return None

    fails = int(state.get("host_fail_count", 0)) + 1
    if fails < max(1, _HOST_FAIL_THRESHOLD):
        state["host_fail_count"] = fails
        return None

    if degraded:
        # 回退主机自身连续连接失败 → 放弃降级窗口回主主机，避免长时间钉在死主机上
        state["host_fail_count"] = 0
        state["host_degraded_until"] = 0.0
        logger.warning(
            "[em_gate] 回退主机 %s 连续 %s 次连接类错误，**放弃降级窗口**回主主机：%s",
            host,
            fails,
            exc,
        )
        return None

    fallback = _fallback_host(host)
    if not fallback:
        state["host_fail_count"] = fails
        return None  # 无映射主机不回退（该计数留待下一台主主机判断）

    state["host_fail_count"] = 0
    state["host_degraded_until"] = now + _HOST_DEGRADED_SECONDS
    state["hot_host"] = fallback
    totals = state.setdefault("totals", {})
    totals["degraded"] = int(totals.get("degraded", 0) or 0) + 1
    logger.warning(
        "[em_gate] 连续 %s 次连接类错误（非封禁），主机回退 %s → %s（%.0fs 内直走回退主机）：%s",
        fails,
        host,
        fallback,
        _HOST_DEGRADED_SECONDS,
        type(exc).__name__,
    )
    return fallback


# ---------------------------------------------------------------------------
# 跨进程状态文件（schema 见方案 §2.2；熔断相关字段预留占位）
# ---------------------------------------------------------------------------
def _default_state() -> Dict[str, Any]:
    """构造默认状态结构（方案 §2.2 schema）。

    Returns:
        状态字典；``hot_host`` 为**最近一次实际请求主机**（降级期内即回退主机），
        ``host_fail_count`` 为「连续连接类错误」计数（成功 / 封禁均清零）。
    """
    return {
        "last_request_ts": 0.0,
        "recent_ts": [],
        "consecutive_ban": 0,
        "circuit_open_until": 0.0,
        "half_open_probe_used": False,
        "hot_host": "",
        "host_degraded_until": 0.0,
        "host_fail_count": 0,
        "totals": {"calls": 0, "ban": 0, "stale": 0, "degraded": 0},
    }


def _read_state(path: Path) -> Dict[str, Any]:
    """读取跨进程状态文件（只读；缺失或损坏时回落默认状态）。

    Args:
        path: 状态文件路径。

    Returns:
        状态字典（缺失字段由默认值补齐，保证向前兼容）。
    """
    state = _default_state()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return state
    except OSError as exc:  # pragma: no cover - 权限/IO 异常
        logger.warning("[em_gate] 读取状态文件失败（按默认状态处理）：%s", exc)
        return state
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("[em_gate] 状态文件损坏（按默认状态处理）：%s", path)
        return state
    if isinstance(loaded, dict):
        state.update(loaded)
    return state


def _write_state(state: Dict[str, Any], path: Path) -> None:
    """原子写入状态文件（先写 ``.tmp`` 再 ``os.replace``）。

    沿用 ``a_stock_cache`` 既有范式，避免并发写坏状态。

    Args:
        state: 待写入的状态字典。
        path: 状态文件路径（父目录不存在时自动创建）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def _append_log(log_file: Path, record: Dict[str, Any]) -> None:
    """追加一行指标日志到 jsonl（失败静默降级，绝不影响业务请求）。

    Args:
        log_file: 指标日志路径。
        record: 指标记录（每请求一行）。
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - 磁盘/权限异常
        logger.warning("[em_gate] 指标日志写入失败（已忽略）：%s", exc)


# ---------------------------------------------------------------------------
# 滑窗预算计算
# ---------------------------------------------------------------------------
def _prune_recent(recent: List[float], now: float) -> List[float]:
    """裁剪滑窗时间戳（仅保留最大窗口内的记录，升序）。

    Args:
        recent: 历史请求时间戳列表。
        now: 当前时间戳。

    Returns:
        裁剪并升序排序后的时间戳列表。
    """
    horizon = now - max(_WINDOW_MIN_SECONDS, _WINDOW_5MIN_SECONDS)
    return sorted(ts for ts in recent if ts > horizon)


def _window_count(recent: List[float], window: float, now: float) -> int:
    """统计滑窗内（严格晚于 ``now - window``）的请求次数。

    Args:
        recent: 升序时间戳列表。
        window: 窗口长度（秒）。
        now: 当前时间戳。

    Returns:
        窗口内请求次数。
    """
    return sum(1 for ts in recent if ts > now - window)


def _window_wait(recent: List[float], window: float, budget: int, now: float) -> float:
    """计算滑窗预算约束所需的等待秒数（方案 §2.3 步骤 4）。

    窗口内已有 ≥ ``budget`` 次请求时，需等待窗口内最早的那一次滑出窗口，
    请求数才会回落到预算之内。

    Args:
        recent: 升序时间戳列表。
        window: 窗口长度（秒）。
        budget: 窗口内允许的最大请求数。
        now: 当前时间戳。

    Returns:
        需要等待的秒数（0 表示无滑窗约束）。
    """
    if budget <= 0 or window <= 0:
        return 0.0
    in_window = [ts for ts in recent if ts > now - window]
    if len(in_window) < budget:
        return 0.0
    oldest = in_window[-budget]  # 倒数第 budget 个即窗口内最早的一次
    return max(0.0, oldest + window - now)


def _compute_wait(config: GateConfig, recent: List[float], now: float) -> float:
    """计算本次请求在锁内的「节奏 sleep」时长。

    由三项取最大：① 最小间隔 + 随机抖动（抗固定周期指纹）；② 分钟滑窗约束；
    ③ 5 分钟滑窗约束。

    Args:
        config: 闸门配置。
        recent: 升序时间戳列表。
        now: 当前时间戳。

    Returns:
        锁内需 sleep 的秒数。
    """
    base = max(0.0, config.min_interval) + random.uniform(
        0.0, max(0.0, config.jitter_max)
    )
    return max(
        base,
        _window_wait(recent, _WINDOW_MIN_SECONDS, config.budget_per_min, now),
        _window_wait(recent, _WINDOW_5MIN_SECONDS, config.budget_per_5min, now),
    )


# ---------------------------------------------------------------------------
# 熔断器（方案 §2.3 / §9 P1）：连续封禁 → 冷却窗口 → 半开单探测
# ---------------------------------------------------------------------------
# 熔断相位（``status`` 输出与放行判据共用同一口径）
_CIRCUIT_CLOSED = "closed"
_CIRCUIT_OPEN = "open"
_CIRCUIT_HALF_OPEN = "half_open"


def _circuit_phase(state: Dict[str, Any], now: float) -> str:
    """派生熔断相位。

    ``circuit_open_until`` 为 0 表示从未熔断或已完全恢复（``closed``）；
    尚未到期为冷却中（``open``）；已到期但还没拿到探测结果为半开
    （``half_open``）——半开态允许放行**一个**探测请求以验证是否已解封。

    Args:
        state: 跨进程状态字典。
        now: 当前时间戳。

    Returns:
        ``"closed"`` / ``"open"`` / ``"half_open"`` 之一。
    """
    until = float(state.get("circuit_open_until") or 0.0)
    if until <= 0:
        return _CIRCUIT_CLOSED
    if now < until:
        return _CIRCUIT_OPEN
    return _CIRCUIT_HALF_OPEN


def _circuit_reject_reason(state: Dict[str, Any], now: float) -> Optional[str]:
    """判定当前熔断是否应直接拒绝（锁外快速路径与锁内二次校验共用）。

    Args:
        state: 跨进程状态字典。
        now: 当前时间戳。

    Returns:
        拒绝原因（人类可读）；None 表示放行（``closed``，或 ``half_open``
        且探测位空闲）。
    """
    phase = _circuit_phase(state, now)
    if phase == _CIRCUIT_OPEN:
        until = float(state.get("circuit_open_until") or 0.0)
        return f"熔断冷却中（剩余 {max(0, int(until - now))} 秒）"
    if phase == _CIRCUIT_HALF_OPEN and state.get("half_open_probe_used"):
        return "熔断半开探测进行中（探测位已被占用），本请求暂不放行"
    return None


def _raise_circuit_open(reason: str, url: str) -> None:
    """抛出 ``EmCircuitOpen``（消息含闸门标记，供 §3.4 降级判定）。

    Args:
        reason: 拒绝原因。
        url: 请求 URL。

    Raises:
        EmCircuitOpen: 恒抛出。
    """
    raise EmCircuitOpen(f"东财闸门拒绝：{reason}：{url}")


def _open_circuit(
    state: Dict[str, Any], now: float, config: GateConfig, reason: str
) -> None:
    """打开熔断：写入冷却截止时刻并复位探测位。

    Args:
        state: 跨进程状态字典（就地修改）。
        now: 当前时间戳。
        config: 闸门配置（提供冷却时长）。
        reason: 触发原因（仅用于日志）。
    """
    state["circuit_open_until"] = now + max(
        0.0, float(config.circuit_cooldown_min)
    ) * 60.0
    state["half_open_probe_used"] = False
    logger.warning(
        "[em_gate] 熔断打开（%s）：冷却 %s 分钟，期内东财请求一律拒绝（不取锁）",
        reason,
        config.circuit_cooldown_min,
    )


def _close_circuit(state: Dict[str, Any], reason: str) -> None:
    """关闭熔断：清零冷却时刻与连续封禁计数，并复位探测位。

    Args:
        state: 跨进程状态字典（就地修改）。
        reason: 触发原因（仅用于日志）。
    """
    state["circuit_open_until"] = 0.0
    state["half_open_probe_used"] = False
    state["consecutive_ban"] = 0
    logger.info("[em_gate] 熔断关闭（%s）", reason)


def _claim_probe_locked(
    state: Dict[str, Any], now: float, config: GateConfig, url: str
) -> bool:
    """锁内二次校验熔断，并在半开态占位探测位。

    占位后立即落盘，使其余进程在同一冷却周期内不再空转排队（方案 §1 要点 3）。

    Args:
        state: 跨进程状态字典（就地修改）。
        now: 当前时间戳。
        config: 闸门配置。
        url: 请求 URL（仅用于异常消息）。

    Returns:
        True 表示本次请求被放行为半开探测位。

    Raises:
        EmCircuitOpen: 熔断冷却中，或探测位已被其他进程占用。
    """
    reason = _circuit_reject_reason(state, now)
    if reason is not None:
        _raise_circuit_open(reason, url)
    if _circuit_phase(state, now) != _CIRCUIT_HALF_OPEN:
        return False
    state["half_open_probe_used"] = True
    _write_state(state, config.state_file)
    logger.info("[em_gate] 熔断半开：本请求作为唯一探测位放行")
    return True


@dataclass(frozen=True)
class BudgetReport:
    """预算 / 闸门状态报告（``check_budget()`` 返回值，方案 §2.1）。

    Attributes:
        allowed: 当前是否允许发起东财请求。
        reason: 判定原因（人类可读）。
        circuit: 熔断相位，"closed" / "open" / "half_open"。
        remaining_min: 分钟预算剩余额度。
        remaining_5min: 5 分钟预算剩余额度。
        last_request_ago_s: 距上次东财请求的秒数；从未请求过时为 None。
    """

    allowed: bool
    reason: str
    circuit: str
    remaining_min: int
    remaining_5min: int
    last_request_ago_s: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        """转换为 JSON 兼容字典（``status`` 子命令输出用）。

        Returns:
            扁平字典（键与方案 §3.3 一致）。
        """
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "circuit": self.circuit,
            "remaining_min": self.remaining_min,
            "remaining_5min": self.remaining_5min,
            "last_request_ago_s": self.last_request_ago_s,
        }


def check_budget() -> BudgetReport:
    """编排层预算预检（只读快照，**不取锁**，便于编排器快速自检）。

    Returns:
        ``BudgetReport``：含 allowed / reason / circuit / 剩余额度 / 上次请求间隔。
    """
    config = _CONFIG
    now = time.time()
    if not config.enabled:
        # 总开关关闭：不设任何限制（完全退化为改造前行为）
        return BudgetReport(
            allowed=True,
            reason="EM_GATE_ENABLED=0，闸门已关闭，不做任何限制",
            circuit="closed",
            remaining_min=config.budget_per_min,
            remaining_5min=config.budget_per_5min,
            last_request_ago_s=None,
        )

    state = _read_state(config.state_file)
    recent = _prune_recent(
        [float(ts) for ts in (state.get("recent_ts") or [])], now
    )
    remaining_min = max(0, config.budget_per_min - _window_count(recent, _WINDOW_MIN_SECONDS, now))
    remaining_5min = max(
        0, config.budget_per_5min - _window_count(recent, _WINDOW_5MIN_SECONDS, now)
    )
    # 熔断相位：与 _before_request 共用同一派生函数，保证 status 与放行判据一致
    circuit = _circuit_phase(state, now)
    circuit_until = float(state.get("circuit_open_until") or 0.0)

    last_ts = float(state.get("last_request_ts") or 0.0)
    last_ago: Optional[float] = max(0.0, now - last_ts) if last_ts > 0 else None

    if FileLock is None:
        # filelock 缺失是**硬阻塞**：闸门取不了跨进程锁，``_before_request`` 会一律抛
        # ``EmGateError``。必须在此如实反映——否则编排层按 CLAUDE.md「并发前置」
        # 读到 allowed=True 会误判「可并发」，随后所有东财调用集体被拒。
        reason = "filelock 未安装，闸门无法取锁，东财请求将被拒绝（可执行 pip install filelock）"
        allowed = False
    elif circuit == _CIRCUIT_OPEN:
        reason = f"熔断冷却中（剩余 {max(0, int(circuit_until - now))} 秒）"
        allowed = False
    elif circuit == _CIRCUIT_HALF_OPEN and state.get("half_open_probe_used"):
        reason = "熔断半开探测进行中（探测位已被占用），暂不放行"
        allowed = False
    elif remaining_min <= 0:
        reason = f"分钟预算已用尽（{config.budget_per_min} 次/分钟）"
        allowed = False
    elif remaining_5min <= 0:
        reason = f"5 分钟预算已用尽（{config.budget_per_5min} 次/5 分钟）"
        allowed = False
    else:
        reason = "预算充足"
        allowed = True

    return BudgetReport(
        allowed=allowed,
        reason=reason,
        circuit=circuit,
        remaining_min=remaining_min,
        remaining_5min=remaining_5min,
        last_request_ago_s=last_ago,
    )


# ---------------------------------------------------------------------------
# 加锁协议（方案 §2.3）：取锁 → 节奏 sleep → 请求 → 回写状态 → 释放锁
# ---------------------------------------------------------------------------
@dataclass
class _GateToken:
    """一次受控请求的令牌（持锁至响应/异常后由 ``_after_request`` 释放）。

    Attributes:
        url: 请求 URL。
        lock_ts: 取得跨进程锁的时刻（用于验证「任一时刻至多一个请求在途」）。
        request_ts: 节奏 sleep 结束、请求被放行的时刻。
        slept: 锁内节奏 sleep 的实际时长（秒）。
        lock: filelock 实例（``None`` 表示闸门关闭，未取锁）。
        local_locked: 是否持有进程内线程锁。
        released_ts: 锁释放时刻（``_release_token`` 填充，供测试做重叠检测）。
        is_probe: 本次请求是否为熔断半开态的**唯一探测位**。
        degraded_host: 主机回退期内应改写的回退主机（未降级为 None）。
    """

    url: str
    lock_ts: float
    request_ts: float
    slept: float
    lock: Any = None
    local_locked: bool = False
    released_ts: Optional[float] = None
    is_probe: bool = False
    degraded_host: Optional[str] = None


def _after_request(
    url: str,
    token: _GateToken,
    exc: Optional[BaseException],
    *,
    forced_ban: bool = False,
    proxy_retry: bool = False,
) -> None:
    """退出闸门：回写状态与指标 → 释放锁（**绝不向业务抛出异常**）。

    Args:
        url: 请求 URL。
        token: ``_before_request`` 返回的令牌。
        exc: 业务异常（无异常时为 None）；封禁信号会累加计数。
        forced_ban: 由 hook 判定的封禁（如响应体为 HTTP 403 但未抛异常）。
        proxy_retry: 本次是否为「代理失败后的直连重试」（仅用于指标标注）。
    """
    try:
        if _CONFIG.enabled and token.lock is not None:
            _record_outcome(
                url, token, exc, forced_ban=forced_ban, proxy_retry=proxy_retry
            )
    except Exception as log_exc:  # noqa: BLE001  闸门自身异常不得影响业务请求
        logger.warning("[em_gate] 状态回写失败（已忽略）：%s", log_exc)
    finally:
        _release_token(token)


def _release_token(token: _GateToken) -> None:
    """释放令牌持有的锁（filelock → 进程内线程锁）并记录释放时刻。

    Args:
        token: 待释放的令牌。
    """
    if token.lock is not None:
        try:
            token.lock.release()
        except Exception as exc:  # noqa: BLE001  释放失败不应影响业务请求
            logger.warning("[em_gate] 释放跨进程锁失败（已忽略）：%s", exc)
    # 先释放文件锁再释放线程锁，保证同进程后续线程能看到最新的状态文件
    token.released_ts = time.time()
    if token.local_locked:
        try:
            _LOCAL_LOCK.release()
        except RuntimeError:  # pragma: no cover - 重复释放的兜底
            logger.warning("[em_gate] 进程内线程锁重复释放（已忽略）")
        token.local_locked = False


def _record_outcome(
    url: str,
    token: _GateToken,
    exc: Optional[BaseException],
    *,
    forced_ban: bool,
    proxy_retry: bool = False,
) -> None:
    """锁内回写状态文件：滑窗、计数、封禁短路标记、指标日志。

    Args:
        url: 请求 URL。
        token: 本次请求令牌（提供节奏 sleep 时长）。
        exc: 业务异常（无异常时为 None）。
        forced_ban: hook 判定的封禁（HTTP 403 响应但无异常抛出）。
        proxy_retry: 本次是否为「代理失败后的直连重试」。
    """
    config = _CONFIG
    now = time.time()
    state = _read_state(config.state_file)

    # 1) 滑窗：追加本次时间戳并裁剪（> 最大窗口的记录丢弃）
    recent = _prune_recent([float(ts) for ts in (state.get("recent_ts") or [])], now)
    recent.append(now)
    state["recent_ts"] = sorted(recent)
    state["last_request_ts"] = now
    state["hot_host"] = _extract_host(url) or state.get("hot_host") or ""

    # 2) 异常分类：封禁信号 → 累加计数（绝不重试）；成功 → 清零连续封禁计数
    totals = state.get("totals") or {}
    totals["calls"] = int(totals.get("calls", 0)) + 1
    ban = forced_ban or (exc is not None and is_ban_signal(exc))
    if ban:
        state["consecutive_ban"] = int(state.get("consecutive_ban", 0)) + 1
        totals["ban"] = int(totals.get("ban", 0)) + 1
        logger.warning(
            "[em_gate] 疑似东财封禁信号（连续第 %s 次），**放弃重试**：%s",
            state["consecutive_ban"],
            exc if exc is not None else "HTTP 403",
        )
        # 熔断触发：半开探测再被封禁 → 立即重开；普通请求 → 连续封禁达阈值才开
        if token.is_probe:
            _open_circuit(state, now, config, "半开探测仍被封禁")
        elif state["consecutive_ban"] >= max(1, int(config.circuit_threshold)):
            _open_circuit(
                state, now, config, f"连续封禁达 {config.circuit_threshold} 次"
            )
    elif token.is_probe:
        # 探测位未收到封禁信号 → 视为已恢复，关闭熔断并清零连续计数
        _close_circuit(state, "半开探测成功")
    elif exc is None:
        state["consecutive_ban"] = 0
    state["totals"] = totals

    # 2.5) 主机回退（方案 §2.5）：连续连接类错误（**非**封禁）达阈值即切回退主机
    _update_host_health(
        state,
        url,
        exc,
        ban=ban,
        enabled=config.host_fallback,
        degraded=token.degraded_host is not None,
        now=now,
    )

    # 3) 原子写回状态 + 追加一行指标日志
    _write_state(state, config.state_file)
    _append_log(
        config.log_file,
        {
            "ts": now,
            "host": _extract_host(url),
            "url": str(url),
            "wait_s": round(token.slept, 3),
            "status": "ban" if ban else ("error" if exc is not None else "ok"),
            "error": type(exc).__name__ if exc is not None else None,
            "circuit": _circuit_phase(state, now),
            "probe": bool(token.is_probe),
            "proxy_retry": bool(proxy_retry),
            "degraded_host": token.degraded_host,
        },
    )


def _before_request(url: str) -> _GateToken:
    """进入闸门：取跨进程锁 → 滑窗/节奏 sleep → 返回令牌（锁在响应后释放）。

    锁内仅做节奏 sleep，不做任何退避重试；等待量超过 ``EM_GATE_MAX_HOLD_SECONDS``
    时立即还锁，锁外短退避后重取，避免长占锁阻塞其他进程。

    Args:
        url: 请求 URL（仅东财 URL 会走到此处）。

    Returns:
        ``_GateToken``（须由 ``_after_request`` 释放）。

    Raises:
        EmGateError: filelock 缺失。
        EmGateTimeout: 在 ``EM_GATE_LOCK_TIMEOUT`` 内未取得跨进程锁。
        EmCircuitOpen: 熔断冷却中，或半开探测位已被占用（**不取锁**直接拒绝）。
    """
    config = _CONFIG
    now = time.time()
    if not config.enabled:
        # 总开关关闭：不取锁、不 sleep、不计数，完全退化为原行为
        return _GateToken(url=url, lock_ts=now, request_ts=now, slept=0.0)

    # 熔断短路发生在取锁**之前**（方案 §1 设计要点 3）：冷却期内 N 个进程
    # 无需排队等一把注定失败的锁。此处为无锁读，可能读到略旧状态，
    # 故锁内还会做一次权威二次校验。
    pre_reason = _circuit_reject_reason(_read_state(config.state_file), now)
    if pre_reason is not None:
        _raise_circuit_open(pre_reason, url)

    if FileLock is None:
        raise EmGateError(
            "filelock 未安装，无法启用东财请求闸门（可执行 pip install filelock）"
        )

    deadline = time.time() + max(0.0, config.lock_timeout)
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise EmGateTimeout(
                f"东财闸门取锁超时（{config.lock_timeout}s）：{url}"
            )
        # 进程内线程互斥：filelock 实例不可重入，先过本地锁再抢跨进程锁
        if not _LOCAL_LOCK.acquire(timeout=remaining):
            raise EmGateTimeout(
                f"东财闸门取锁超时（{config.lock_timeout}s）：{url}"
            )

        lock = None
        local_locked = True
        transferred = False
        try:
            lock = FileLock(str(config.lock_file))
            try:
                lock.acquire(timeout=max(0.0, deadline - time.time()))
            except Exception as acquire_exc:  # noqa: BLE001  区分超时与真实错误
                if _FileLockTimeout is not None and isinstance(
                    acquire_exc, _FileLockTimeout
                ):
                    raise EmGateTimeout(
                        f"东财闸门取锁超时（{config.lock_timeout}s）：{url}"
                    ) from acquire_exc
                raise EmGateError(f"东财闸门取锁失败：{acquire_exc}") from acquire_exc

            lock_ts = time.time()
            state = _read_state(config.state_file)
            # 锁内权威校验：熔断相位可能在排队等锁期间被其他进程改写
            reason = _circuit_reject_reason(state, lock_ts)
            if reason is not None:
                _raise_circuit_open(reason, url)
            recent = _prune_recent(
                [float(ts) for ts in (state.get("recent_ts") or [])], lock_ts
            )
            wait = _compute_wait(config, recent, lock_ts)

            if wait > config.max_hold_seconds:
                # 等待量超过锁内硬上限：立刻还锁，锁外短退避后重取（防长占锁）
                lock.release()
                lock = None
                _LOCAL_LOCK.release()
                local_locked = False
                time.sleep(_LONG_WAIT_BACKOFF)
                continue

            if wait > 0:
                time.sleep(wait)
            grant_ts = time.time()
            # 半开态占位唯一探测位（立即落盘，其余进程即刻可见）
            is_probe = _claim_probe_locked(state, grant_ts, config, url)
            # 主机回退（方案 §2.5）：降级窗口内改走回退主机，不再试死主机
            degraded_host = _pick_fallback_host(config, state, url, grant_ts)
            transferred = True
            return _GateToken(
                url=url,
                lock_ts=lock_ts,
                request_ts=grant_ts,
                slept=grant_ts - lock_ts,
                lock=lock,
                local_locked=True,
                is_probe=is_probe,
                degraded_host=degraded_host,
            )
        finally:
            # 未成功移交令牌（异常或长等待还锁分支）时，确保锁不泄漏
            if not transferred:
                if lock is not None:
                    try:
                        lock.release()
                    except Exception as release_exc:  # noqa: BLE001
                        logger.warning(
                            "[em_gate] 释放跨进程锁失败（已忽略）：%s", release_exc
                        )
                if local_locked:
                    try:
                        _LOCAL_LOCK.release()
                    except RuntimeError:  # pragma: no cover - 兜底
                        pass


def _enter_gate(url: str) -> _GateToken:
    """进入闸门；被拒绝时记录降级快照后原样抛出（§3.4 的判定依据）。

    Args:
        url: 请求 URL。

    Returns:
        ``_GateToken``（由 ``_after_request`` 释放）。

    Raises:
        EmGateError: 原样透出 ``_before_request`` 的闸门拒绝。
    """
    try:
        return _before_request(url)
    except EmGateError as exc:
        _record_rejection(exc)
        raise


# ---------------------------------------------------------------------------
# 请求指纹与代理策略（方案 §2.3 步骤 5 / §9 P1）
# ---------------------------------------------------------------------------
#: 统一 UA：东财对 python-requests 默认 UA 更敏感，统一为浏览器指纹
_EM_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

#: 统一指纹：UA + Referer（quote.eastmoney.com 为东财行情页）+ keep-alive
_EM_FINGERPRINT: Dict[str, str] = {
    "User-Agent": _EM_UA,
    "Referer": "https://quote.eastmoney.com/",
    "Connection": "keep-alive",
}

#: 直连代理参数：``http`` / ``https`` 显式置空串以**压过** requests
#: ``merge_environment_settings`` 的 ``setdefault`` 合并——传 ``{}`` 会把
#: ``HTTP(S)_PROXY`` 回填进来，等于没绕过。
_DIRECT_PROXIES: Dict[str, str] = {"http": "", "https": ""}


def apply_fingerprint(kwargs: Dict[str, Any]) -> None:
    """向请求参数注入统一指纹（**不覆盖调用方显式 headers**）。

    Args:
        kwargs: 传给 ``Session.request`` 的关键字参数（原地修改）。
    """
    headers = dict(kwargs.get("headers") or {})
    existing = {str(key).lower() for key in headers}
    for key, value in _EM_FINGERPRINT.items():
        if key.lower() not in existing:  # 调用方显式指定者优先，闸门只补空缺
            headers[key] = value
    kwargs["headers"] = headers


def apply_proxy_bypass(kwargs: Dict[str, Any], *, force: bool = False) -> bool:
    """剥离东财请求的代理（``EM_GATE_BYPASS_PROXY=1``）。

    Args:
        kwargs: 传给 ``Session.request`` 的关键字参数（原地修改）。
        force: 为 True 时即使调用方显式指定代理也剥离（代理失败后的直连重试）。

    Returns:
        是否实际改写了 ``proxies``。
    """
    if kwargs.get("proxies") and not force:  # 显式代理：尊重调用方，不覆盖
        return False
    kwargs["proxies"] = dict(_DIRECT_PROXIES)
    return True


def _should_retry_direct(exc: BaseException, *, stripped: bool) -> bool:
    """是否应「剥离代理直连重试一次」。

    Args:
        exc: 本次尝试抛出的异常。
        stripped: 本次尝试是否**已经**剥离代理（已直连则重试无意义）。

    Returns:
        True 表示应直连重试。
    """
    if stripped or is_ban_signal(exc):
        return False  # 已直连 / 封禁信号（§10.3 禁止对封禁做任何重试）
    return is_connection_error(exc)


def _dispatch_gated(
    orig: Callable[..., Any],
    session: Any,
    method: str,
    url: Any,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    *,
    strip_proxy: bool,
    force_strip: bool = False,
    proxy_retry: bool = False,
) -> Any:
    """执行一次受闸门管控的东财请求（含指纹注入与代理策略）。

    重试走**完整闸门**（重新取锁 + 重新节奏间隔），绝不在锁内重试（方案 §1 要点 2）。
    主机回退（方案 §2.5）在取锁后按令牌的 ``degraded_host`` 改写 URL，日志记实际主机。
    ``EM_GATE_FORCE_IPV4=1`` 时，本次调用内把地址族限定为 IPv4（步骤 6 加固）。

    Args:
        orig: ``Session.request`` 的原始实现。
        session: 调用方 Session 实例。
        method: HTTP 方法。
        url: 请求 URL。
        args: ``Session.request`` 的位置参数。
        kwargs: ``Session.request`` 的关键字参数（原地注入指纹 / 代理）。
        strip_proxy: 本次是否剥离代理。
        force_strip: 强制剥离（忽略调用方显式代理）。
        proxy_retry: 本次是否为「代理失败后的直连重试」（仅用于指标标注）。

    Returns:
        ``orig`` 的返回值（响应对象）。
    """
    apply_fingerprint(kwargs)
    if strip_proxy:
        apply_proxy_bypass(kwargs, force=force_strip)

    token = _enter_gate(str(url))
    # 主机回退（方案 §2.5）：降级窗口内改走回退主机；日志记录**实际**请求 URL
    effective_url = (
        _swap_host(url, token.degraded_host) if token.degraded_host else url
    )
    exc: Optional[BaseException] = None
    resp: Any = None
    # 强制 IPv4（步骤 6 加固）：仅本次受管控的东财调用内置位，嵌套调用保留外层状态
    prev_ipv4 = getattr(_FORCE_IPV4_LOCAL, "active", False)
    if _CONFIG.force_ipv4:
        _FORCE_IPV4_LOCAL.active = True
    try:
        resp = orig(session, method, effective_url, *args, **kwargs)
        return resp
    except BaseException as err:  # noqa: BLE001  异常需先归类再原样抛出
        exc = err
        raise
    finally:
        _FORCE_IPV4_LOCAL.active = prev_ipv4
        # 403 响应（无异常抛出）同样计入封禁短路
        forced_ban = resp is not None and getattr(resp, "status_code", None) == 403
        _after_request(
            str(effective_url),
            token,
            exc,
            forced_ban=forced_ban,
            proxy_retry=proxy_retry,
        )


# ---------------------------------------------------------------------------
# transport hook（方案 §2.4）：包装 Session.request + host 过滤
# ---------------------------------------------------------------------------
def _make_patched_request(orig: Callable[..., Any]) -> Callable[..., Any]:
    """构造 ``Session.request`` 的包装函数（host 过滤 + 闸门 + 异常透明）。

    代理策略（方案 §9 P1）：``EM_GATE_BYPASS_PROXY=1``（默认）时东财请求一律
    剥离代理直连；否则尊重环境 / 调用方代理，但若该次尝试因**连接类错误**失败
    （**非**封禁信号）则剥离代理**直连重试一次**。

    Args:
        orig: ``requests.sessions.Session.request`` 的原始实现。

    Returns:
        包装后的请求函数；非东财请求零改动透传，不改变返回类型、不吞异常。
    """

    @functools.wraps(orig)
    def wrapper(self: Any, method: str, url: Any, *args: Any, **kwargs: Any) -> Any:
        """host 过滤后的请求入口：仅东财请求经闸门。"""
        # 非东财请求 / 闸门关闭：原样透传（零侵入、不计预算、不取锁、不动 headers）
        if not _CONFIG.enabled or not is_em_url(url):
            return orig(self, method, url, *args, **kwargs)

        strip_proxy = bool(_CONFIG.bypass_proxy)
        try:
            return _dispatch_gated(
                orig, self, method, url, args, kwargs,
                strip_proxy=strip_proxy,
            )
        except BaseException as err:  # noqa: BLE001  仅「代理失败」需改直连重试
            if not _should_retry_direct(err, stripped=strip_proxy):
                raise
            logger.warning(
                "[em_gate] 连接类错误（疑似代理不可用），剥离代理直连重试一次：%s", err
            )
            return _dispatch_gated(
                orig, self, method, url, args, kwargs,
                strip_proxy=True, force_strip=True, proxy_retry=True,
            )

    wrapper._em_gate_patched = True  # type: ignore[attr-defined]  幂等标记
    return wrapper


def install() -> None:
    """装载 host 过滤 transport hook（幂等；各工具 ``main()`` 首行调用）。

    注入点为 ``requests.sessions.Session.request``——``requests.get/post`` 与显式
    ``Session`` 的唯一汇聚点，patch 此处即可 100% 覆盖 akshare 内部所有裸调。
    ``EM_GATE_ENABLED=0`` 时**不 patch**（并还原此前装载的包装），完全退化为
    改造前行为。
    """
    if requests is None:
        logger.warning("[em_gate] requests 未安装，跳过 transport hook 装载")
        return

    global _ORIGINAL_SESSION_REQUEST
    session_cls = requests.sessions.Session
    current = session_cls.request

    if not _CONFIG.enabled:
        # 总开关关闭：若此前已装载则还原原函数，保证完全退化
        if getattr(current, "_em_gate_patched", False) and (
            _ORIGINAL_SESSION_REQUEST is not None
        ):
            session_cls.request = _ORIGINAL_SESSION_REQUEST
        _restore_force_ipv4_hook()
        return

    # 强制 IPv4 钩子（步骤 6 加固）：仅在东财请求内生效（线程局部开关）
    if _CONFIG.force_ipv4:
        _install_force_ipv4_hook()
    else:
        _restore_force_ipv4_hook()

    if getattr(current, "_em_gate_patched", False):
        return  # 幂等：重复调用不叠加包装

    _ORIGINAL_SESSION_REQUEST = current
    session_cls.request = _make_patched_request(current)


def is_active() -> bool:
    """闸门是否**实际生效**（总开关启用且 transport hook 已装载）。

    供业务层判断是否让位自己的进程内限流器：闸门已在传输层强制
    **跨进程**最小间隔，再叠一层进程内 sleep 属双重节流；而闸门未生效
    （未 ``install()`` 或 ``EM_GATE_ENABLED=0``）时，业务层**必须**保留
    原有节流，否则退化为无节流裸调。

    Returns:
        True 表示东财请求的节流已由闸门承担。
    """
    return bool(_CONFIG.enabled) and _ORIGINAL_SESSION_REQUEST is not None


# ---------------------------------------------------------------------------
# 进程级降级兜底：保证「闸门拒绝」在任何工具中都输出统一载荷（方案 §3.4）
# ---------------------------------------------------------------------------
# install_cli() 写入的工具标识与替代命令
_CLI_TOOL = "unknown"
_CLI_FALLBACK_CMD = ""

# 进程级兜底是否已安装（sys.exit / sys.excepthook 各只包装一次）
_CLI_HOOKS_INSTALLED = False
_ORIGINAL_SYS_EXIT: Optional[Callable[..., Any]] = None
_ORIGINAL_EXCEPTHOOK: Optional[Callable[..., Any]] = None

# 标的代码形态：A股 6 位 / 港股 5 位（避免误取日期、期数等纯数字参数）
_SYMBOL_RE = re.compile(r"^\d{5,6}$")


def _guess_symbol(argv: Optional[List[str]] = None) -> Optional[str]:
    """从命令行参数中提取标的代码（供 fallback_cmd 渲染为可直接执行的命令）。

    Args:
        argv: 参数列表（默认取 ``sys.argv[1:]``）。

    Returns:
        首个 5~6 位纯数字参数；未找到时为 None。
    """
    for token in argv if argv is not None else sys.argv[1:]:
        text = str(token).strip()
        if _SYMBOL_RE.match(text):
            return text
    return None


def _render_fallback_cmd(template: str, symbol: Optional[str] = None) -> str:
    """渲染 fallback_cmd 模板中的 ``{symbol}`` 占位符。

    Args:
        template: 含 ``{symbol}`` 的命令模板（不含占位符时原样返回）。
        symbol: 标的代码；为 None 时自动从命令行参数解析。

    Returns:
        可直接执行的命令字符串；解析不到标的时代之以 ``<代码>``。
    """
    if "{symbol}" not in template:
        return template
    return template.replace("{symbol}", symbol or _guess_symbol() or "<代码>")


def _gate_aware_exit(code: Any = None) -> Any:
    """``sys.exit`` 兜底：闸门拒绝被内层 ``except`` 吞掉后仍输出统一降级载荷。

    Args:
        code: 原 ``sys.exit`` 的退出码。

    Returns:
        原 ``sys.exit`` 的返回值（必定抛出 ``SystemExit``）。
    """
    try:
        # 仅当存在尚未上报的闸门拒绝快照时才输出（幂等，不重复打印）
        emit_rejection(None, tool=_CLI_TOOL, fallback_cmd=_CLI_FALLBACK_CMD)
    except Exception as exc:  # noqa: BLE001  兜底逻辑绝不阻断进程退出
        logger.warning("[em_gate] 退出兜底输出失败（已忽略）：%s", exc)
    return _ORIGINAL_SYS_EXIT(code if code is not None else 0)


def _gate_excepthook(exc_type: type, exc: BaseException, tb: Any) -> None:
    """``sys.excepthook`` 兜底：未捕获的闸门拒绝输出统一降级载荷。

    Args:
        exc_type: 异常类型。
        exc: 异常实例。
        tb: traceback 对象。
    """
    handled = False
    try:
        handled = emit_rejection(exc, tool=_CLI_TOOL, fallback_cmd=_CLI_FALLBACK_CMD)
    except Exception as hook_exc:  # noqa: BLE001  兜底逻辑绝不掩盖原异常
        logger.warning("[em_gate] 未捕获异常兜底输出失败（已忽略）：%s", hook_exc)
    if not handled:
        _ORIGINAL_EXCEPTHOOK(exc_type, exc, tb)


def install_cli(*, tool: str, fallback_cmd: str = "") -> None:
    """装载 transport hook + 进程级降级兜底（各业务工具 ``main()`` 首行调用）。

    与 ``install()`` 的差别：除 host 过滤 hook 外，另装两个「漏改也不失守」的
    进程级兜底，保证闸门拒绝在任何工具中都输出方案 §3.4 的统一载荷：
    ① ``sys.excepthook``：闸门异常未被捕获（工具未包 try/except）时；
    ② ``sys.exit`` 包装：闸门异常被内层 ``except`` 吞掉、工具自行以失败退出时。

    Args:
        tool: 工具标识（写入降级载荷 ``meta.tool``）。
        fallback_cmd: 替代命令模板，``{symbol}`` 由命令行参数解析后替换。
    """
    install()

    global _CLI_TOOL, _CLI_FALLBACK_CMD, _CLI_HOOKS_INSTALLED
    global _ORIGINAL_SYS_EXIT, _ORIGINAL_EXCEPTHOOK

    _CLI_TOOL = tool
    _CLI_FALLBACK_CMD = _render_fallback_cmd(fallback_cmd)
    if not _CONFIG.enabled or _CLI_HOOKS_INSTALLED:
        # 总开关关闭：不装兜底（完全退化为改造前行为）；重复调用不叠加包装
        return

    _ORIGINAL_SYS_EXIT = sys.exit
    _ORIGINAL_EXCEPTHOOK = sys.excepthook
    sys.exit = _gate_aware_exit
    sys.excepthook = _gate_excepthook
    _CLI_HOOKS_INSTALLED = True


# ---------------------------------------------------------------------------
# 业务层接口（方案 §2.1）：guarded / call
# ---------------------------------------------------------------------------
def guarded(
    fn: Optional[Callable[..., Any]] = None,
    *,
    api: Optional[str] = None,
    cache_first: Optional[Callable[[], Any]] = None,
) -> Any:
    """业务层包装器：缓存优先 → 预算预检 → 调用 → 封禁短路 → 降级标注。

    支持 ``@guarded`` 与 ``@guarded(api="xxx", cache_first=...)`` 两种用法。
    业务侧接入见方案 §4 迁移清单（``stock_equity`` / ``a_stock_cache`` /
    ``sector_screen``）。本包装器**不重试**——封禁信号只做分类标注后原样抛出，
    由上层决定「直接降级」还是「短退避重试一次」。

    Args:
        fn: 被包装的可调用对象；省略时返回装饰器。
        api: 调用标识（用于异常标注与降级提示），默认取 ``fn.__name__``。
        cache_first: 无参可调用对象；返回非 None 时直接作为结果返回
            （缓存优先：不取锁、不计预算、不发请求）。

    Returns:
        包装后的可调用对象（签名与原函数一致）。

    Raises:
        EmGateBudgetExhausted: 预算已用尽（编排层应改走缓存或备用源）。
        原始业务异常原样抛出（封禁信号不重试，异常上附加 ``em_gate`` 元信息）。
    """

    def _decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        """为一具体可调用对象生成包装函数。"""
        api_name = api or getattr(func, "__name__", "callable")

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """缓存优先 → 预算预检 → 调用（封禁信号不重试）。"""
            if cache_first is not None:
                cached = cache_first()
                if cached is not None:
                    return cached  # 缓存命中：不触网，闸门零开销

            if _CONFIG.enabled:
                report = check_budget()
                if not report.allowed:
                    rejection = EmGateBudgetExhausted(
                        f"东财闸门拒绝 [{api_name}]：{report.reason}"
                    )
                    _record_rejection(rejection)
                    raise rejection

            try:
                return func(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001  需分类后原样抛出
                # 降级标注：在异常上挂载闸门元信息，便于上层生成降级 JSON
                meta = {
                    "api": api_name,
                    "gate": "ban_signal" if is_ban_signal(exc) else "error",
                    "retried": False,
                }
                try:
                    setattr(exc, GATE_META_ATTR, meta)
                except (AttributeError, TypeError):  # pragma: no cover - 个别异常不可挂属性
                    pass
                raise

        return wrapper

    if fn is None:
        return _decorate
    return _decorate(fn)


def call(
    method: str = "GET",
    url: str = "",
    *,
    api: str = "",
    cache_first: Optional[Callable[[], Any]] = None,
    timeout: Optional[float] = None,
    **kwargs: Any,
) -> Any:
    """经闸门执行一次 HTTP 请求（返回 ``requests.Response``）。

    自动确保 transport hook 已装载（``install()`` 幂等）；封禁信号（HTTP 403）
    **绝不重试**，直接抛出带 ``response`` 的 ``HTTPError``，使 ``is_ban_signal``
    可识别并交由上层降级。

    Args:
        method: HTTP 方法。
        url: 请求 URL。
        api: 调用标识（仅用于日志）。
        cache_first: 无参可调用对象；返回非 None 时直接返回（不触网）。
        timeout: 请求超时（秒）。
        **kwargs: 透传给 ``requests.request`` 的参数。

    Returns:
        ``requests.Response``。

    Raises:
        EmGateBudgetExhausted: 预算已用尽。
        EmGateError: ``requests`` 未安装。
        requests.exceptions.HTTPError: HTTP 403（封禁信号，不重试）。
    """
    if cache_first is not None:
        cached = cache_first()
        if cached is not None:
            return cached

    if requests is None:
        raise EmGateError("requests 未安装，无法发起东财请求")

    if _CONFIG.enabled:
        report = check_budget()
        if not report.allowed:
            rejection = EmGateBudgetExhausted(f"东财闸门拒绝 [{api or url}]：{report.reason}")
            _record_rejection(rejection)
            raise rejection
        install()  # 幂等：确保传输层 hook 已装载，避免漏改即失守

    response = requests.request(method, url, timeout=timeout, **kwargs)
    # 403 = 服务端封禁信号：立即抛出（绝不重试），交由上层降级到备用源
    if getattr(response, "status_code", None) == 403:
        raise requests.exceptions.HTTPError(
            f"东方财富拒绝请求（HTTP 403，封禁信号，不重试）：{url}",
            response=response,
        )
    return response


# ---------------------------------------------------------------------------
# CLI 子命令：status / report / reset（观测与运维，方案 §2.1 / §3.3）
# ---------------------------------------------------------------------------
def _meta(command: str) -> Dict[str, Any]:
    """构造 CLI 输出的 meta 段（统一工具标识与配置快照）。

    Args:
        command: 子命令名。

    Returns:
        meta 字典。
    """
    return {
        "tool": "em_gate",
        "command": command,
        "enabled": _CONFIG.enabled,
        "min_interval": _CONFIG.min_interval,
        "jitter_max": _CONFIG.jitter_max,
        "budget_per_min": _CONFIG.budget_per_min,
        "budget_per_5min": _CONFIG.budget_per_5min,
        "state_file": str(_CONFIG.state_file),
        "lock_file": str(_CONFIG.lock_file),
        "log_file": str(_CONFIG.log_file),
        # 熔断执行逻辑自步骤 4（P1）起生效：冷却窗口 + 半开单探测
        "circuit_enforced": True,
        "circuit_threshold": _CONFIG.circuit_threshold,
        "circuit_cooldown_min": _CONFIG.circuit_cooldown_min,
        # 请求指纹与代理策略自步骤 5（P1）起生效：UA / Referer / keep-alive + 代理剥离
        "fingerprint_enforced": True,
        "bypass_proxy": _CONFIG.bypass_proxy,
        # 主机回退链自步骤 6（P2）起生效：连接类错误 ×2 → push2delay
        "host_fallback": _CONFIG.host_fallback,
        "host_degraded_seconds": _HOST_DEGRADED_SECONDS,
        "force_ipv4": _CONFIG.force_ipv4,
        # filelock 可用性：缺失时闸门无法取锁，status 的 allowed 一律为 False
        "filelock_available": FileLock is not None,
        "timestamp": datetime.now().isoformat(),
    }


def cmd_status() -> Dict[str, Any]:
    """``status`` 子命令：输出闸门当前状态（方案 §3.3）。

    Returns:
        含 ``success`` / ``data``（扁平状态）/ ``meta`` 的字典。
    """
    report = check_budget()
    state = _read_state(_CONFIG.state_file)
    data = report.as_dict()
    data["consecutive_ban"] = int(state.get("consecutive_ban", 0) or 0)
    data["circuit_open_until"] = float(state.get("circuit_open_until") or 0.0)
    data["half_open_probe_used"] = bool(state.get("half_open_probe_used"))
    data["hot_host"] = state.get("hot_host") or ""
    data["host_degraded_until"] = float(state.get("host_degraded_until") or 0.0)
    data["host_fail_count"] = int(state.get("host_fail_count", 0) or 0)
    data["totals"] = state.get("totals") or {}
    return {"success": True, "data": data, "meta": _meta("status")}


def _health_verdict(
    *,
    enabled: bool,
    circuit: str,
    consecutive_ban: int,
    threshold: int,
    degraded: int,
    ban: int,
    host_degraded: bool,
    truncated: bool,
    scanned: int,
    total_lines: int,
) -> Dict[str, Any]:
    """给出闸门健康判定（方案 §9 P2「监控 ``em_gate report``」）。

    ``report`` 的原始计数需人工解读才能判断"能否开工"，本函数把它收敛为一个
    可直接读用的三档结论：``critical`` > ``warn`` > ``ok``（取最高级别），
    并在 ``reasons`` 中逐条给出人类可读依据。编排层在"并行起 N 个 Agent"之前
    只读 ``health.level`` 即可决策：``critical`` 改串行或延后盘后、``warn``
    降额并优先走缓存、``ok`` 正常并行。

    Args:
        enabled: 闸门总开关是否开启。
        circuit: 当前熔断相位（``closed`` / ``open`` / ``half_open``）。
        consecutive_ban: 连续封禁信号计数。
        threshold: 熔断阈值（``EM_GATE_CIRCUIT_THRESHOLD``）。
        degraded: 累计主机降级次数。
        ban: 统计范围内被判为封禁的请求数。
        host_degraded: 当前是否处于主机降级窗口内。
        truncated: 日志统计是否仅覆盖尾部片段。
        scanned: 实际参与统计的日志行数。
        total_lines: 日志文件总行数。

    Returns:
        含 ``level``（``ok`` / ``warn`` / ``critical``）与 ``reasons``（列表）的字典。
    """
    # 总开关关闭时不做任何限制，等效"改造前行为"，故恒为 ok
    if not enabled:
        return {"level": "ok", "reasons": ["闸门未启用（EM_GATE_ENABLED=0）"]}

    reasons: List[str] = []
    degraded_window = bool(host_degraded)
    if circuit != "closed":
        reasons.append(f"熔断相位={circuit}（冷却期内东财请求一律被拒）")
    if consecutive_ban > 0:
        reasons.append(f"连续封禁信号 {consecutive_ban} 次（阈值 {threshold}）")
    if degraded_window:
        reasons.append("主机降级窗口生效中（东财请求已改走回退主机）")
    if degraded > 0:
        reasons.append(f"累计主机降级 {degraded} 次")
    if ban > 0:
        reasons.append(f"统计范围内封禁 {ban} 次")
    if truncated:
        # 截断本身不是故障，但必须显式提示，避免把尾部计数误读为总量
        reasons.append(
            f"统计仅覆盖尾部 {scanned}/{total_lines} 行（--limit 0 可全量扫描）"
        )

    if circuit != "closed":
        level = "critical"
    elif consecutive_ban > 0 or degraded_window or degraded > 0 or ban > 0:
        level = "warn"
    else:
        level = "ok"
    return {"level": level, "reasons": reasons}


def cmd_report(limit: int = 200) -> Dict[str, Any]:
    """``report`` 子命令：汇总累计计数、熔断相位与指标日志（监控入口）。

    与 ``status`` 互补：``status`` 面向**瞬时相位与预算余量**，``report`` 面向
    **累计计数与日志聚合**，并额外给出可直接判读的 ``health`` 判定。

    Args:
        limit: 读取指标日志的尾部行数上限；``0`` 表示全量扫描（不截断）。

    Returns:
        含预算/熔断相位、状态累计计数、日志聚合与健康判定的字典。
    """
    state = _read_state(_CONFIG.state_file)
    by_status: Dict[str, int] = {}
    by_host: Dict[str, int] = {}
    events: List[Dict[str, Any]] = []

    try:
        with _CONFIG.log_file.open("r", encoding="utf-8") as handle:
            all_lines = handle.readlines()
    except FileNotFoundError:
        all_lines = []
    except OSError as exc:  # pragma: no cover - 权限/IO 异常
        logger.warning("[em_gate] 读取指标日志失败：%s", exc)
        all_lines = []

    total_lines = len(all_lines)
    # limit<=0 视为全量扫描；否则仅扫描尾部片段，并在输出中标记 truncated
    scanned_lines = all_lines if limit <= 0 else all_lines[-limit:]
    scanned = 0
    unparsable = 0
    for raw in scanned_lines:
        try:
            record = json.loads(raw)
        except (ValueError, TypeError):
            unparsable += 1
            continue
        scanned += 1
        status = record.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        host = record.get("host", "")
        by_host[host] = by_host.get(host, 0) + 1
        events.append(record)

    now = time.time()
    totals = state.get("totals") or {}
    # 相位/预算与 status 子命令共用同一实现，避免两处口径漂移
    data: Dict[str, Any] = dict(check_budget().as_dict())
    consecutive_ban = int(state.get("consecutive_ban", 0) or 0)
    host_degraded_until = float(state.get("host_degraded_until") or 0.0)
    data.update(
        {
            "totals": totals,
            "consecutive_ban": consecutive_ban,
            "circuit_open_until": float(state.get("circuit_open_until") or 0.0),
            "half_open_probe_used": bool(state.get("half_open_probe_used")),
            "hot_host": state.get("hot_host") or "",
            "host_degraded_until": host_degraded_until,
            "log": {
                "total_lines": total_lines,
                "scanned": scanned,
                "truncated": scanned < total_lines,
                "scan_limit": limit,
                "unparsable": unparsable,
                # 兼容既有键：lines 恒等于 scanned（此前恒等于尾部行数）
                "lines": scanned,
                "by_status": by_status,
                "by_host": by_host,
                "recent_events": events[-10:],
            },
        }
    )
    ban = int(by_status.get("ban", 0) or 0)
    data["ban_rate"] = round(ban / scanned, 4) if scanned else 0.0
    data["health"] = _health_verdict(
        enabled=_CONFIG.enabled,
        circuit=str(data.get("circuit", "closed")),
        consecutive_ban=consecutive_ban,
        threshold=_CONFIG.circuit_threshold,
        degraded=int(totals.get("degraded", 0) or 0),
        ban=ban,
        host_degraded=host_degraded_until > now,
        truncated=data["log"]["truncated"],
        scanned=scanned,
        total_lines=total_lines,
    )
    return {"success": True, "data": data, "meta": _meta("report")}


def cmd_reset(purge_log: bool = False) -> Dict[str, Any]:
    """``reset`` 子命令：清空跨进程状态（滑窗 / 封禁计数 / 熔断占位字段）。

    Args:
        purge_log: 为 True 时同时删除指标日志（默认仅清状态、保留日志）。

    Returns:
        含是否删除状态文件与指标日志的字典。
    """
    removed_state = False
    try:
        _CONFIG.state_file.unlink()
        removed_state = True
    except FileNotFoundError:
        removed_state = False
    except OSError as exc:  # pragma: no cover - 权限/IO 异常
        return {
            "success": False,
            "error": f"删除状态文件失败：{exc}",
            "meta": _meta("reset"),
        }

    removed_log = False
    if purge_log:
        try:
            _CONFIG.log_file.unlink()
            removed_log = True
        except FileNotFoundError:
            removed_log = False
        except OSError as exc:  # pragma: no cover - 权限/IO 异常
            logger.warning("[em_gate] 删除指标日志失败（已忽略）：%s", exc)

    return {
        "success": True,
        "data": {"removed_state": removed_state, "removed_log": removed_log},
        "meta": _meta("reset"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """命令行入口。

    Args:
        argv: 参数列表（默认取 ``sys.argv[1:]``，便于测试注入）。

    Returns:
        进程退出码（0 表示成功）。
    """
    # Windows GBK 控制台兼容：保证 JSON 中的中文可正常输出
    if sys.stdout.encoding and sys.stdout.encoding.upper() not in ("UTF-8", "UTF8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover - 非标准流
            pass

    parser = argparse.ArgumentParser(
        prog="em_gate",
        description="东方财富请求闸门：跨进程全局限流 / 预算观测 / 状态运维",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s status            # 查看熔断/预算/上次请求间隔（编排层「第 0 步自检」）
  %(prog)s report            # 汇总累计计数、熔断相位与健康判定
  %(prog)s report --limit 0  # 全量扫描日志（不截断统计）
  %(prog)s reset             # 清空状态（滑窗、封禁计数、熔断占位字段）

配置（.env）:
  EM_GATE_ENABLED / EM_GATE_MIN_INTERVAL / EM_GATE_JITTER_MAX /
  EM_GATE_BUDGET_PER_MIN / EM_GATE_BUDGET_PER_5MIN / EM_GATE_LOCK_TIMEOUT /
  EM_GATE_MAX_HOLD_SECONDS / EM_GATE_STATE_FILE / EM_GATE_LOCK_FILE / EM_GATE_LOG_FILE
""",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="输出闸门当前状态（JSON）")
    rep = sub.add_parser("report", help="汇总状态计数与指标日志（JSON）")
    rep.add_argument(
        "--limit",
        type=int,
        default=200,
        help="读取日志尾部行数上限（0=全量扫描，不截断统计）",
    )
    rst = sub.add_parser("reset", help="清空跨进程状态文件")
    rst.add_argument(
        "--purge-log", action="store_true", help="同时删除指标日志（默认保留日志）"
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "status":
        output = cmd_status()
    elif args.command == "report":
        output = cmd_report(limit=args.limit)
    elif args.command == "reset":
        output = cmd_reset(purge_log=args.purge_log)
    else:
        parser.print_help()
        return 0

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output.get("success", False) else 1


if __name__ == "__main__":
    sys.exit(main())