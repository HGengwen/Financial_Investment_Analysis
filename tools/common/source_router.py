#!/usr/bin/env python3
"""数据源路由统一函数（《AKShare东方财富反爬限流改进方案.md》§6）。

背景
    A股 / 港股各工具的「主源失败 → 备源」逻辑此前**分散在各自文件内**（如
    ``stock_quote.py`` 的 ``fetch_with_fallback()`` 局内闭包、``stock_info.py``
    的「百度总市值 → 东财」拼接、``stock_equity.py`` 的「巨潮 → 东财」双源）。
    分散实现有三个后果：① 优先级口径无法统一维护，改一处漏一处；② 调用方拿不到
    「这笔数据究竟来自哪个源」的结构化证据；③ 全源失败时只能抛裸异常，
    拿不到方案 §3.4 要求的**可执行替代命令**。

    本模块把「哪种数据优先用哪个源」收敛为**声明式路由表 + 一个通用执行器**。

设计约束
    1. **不改业务返回结构**：本模块只负责「按优先级依次尝试、返回首个成功结果」。
       各源的**字段集差异由各源自己的解析函数负责**（东财日线含涨跌幅 / 换手率，
       腾讯日线仅含 OHLC + 成交量，新浪日线含 ``outstanding_share``），调用方
       据 ``RouteOutcome.source`` 判断字段完整性——这与此前「源不同则字段不同」的
       既有契约一致，不引入新的结构变更。
    2. **不做节流**：节流是 ``em_gate`` 的职责（方案 §3.6「节流交给闸门，脚本层
       不再自行 sleep」）；本模块只做选源与回退，避免双重节流。
    3. **不新增依赖、import 期无副作用**（不建目录、不读配置、不发网络请求）。

与 em_gate 的分层
    ``em_gate`` 是**传输层**（跨进程锁 / 限流 / 熔断 / 主机回退），本模块是
    **业务层选源**。故本模块单向依赖「东财源受闸门保护」这一事实（仅以
    ``SourceSpec.gated`` 标注），**不反向 import em_gate**，``em_gate`` 也不
    import 本模块，避免层次倒置。

Usage:
    from tools.common import source_router

    outcome = source_router.route(
        "a_share_daily",
        {"eastmoney": lambda: fetch_em(), "tencent": lambda: fetch_tx()},
        start_from="eastmoney",
    )
    records = outcome.value              # 首个成功结果
    meta["routing"] = outcome.as_dict()  # 逐源尝试记录，供审计

    python tools/common/source_router.py --list   # 列出全部路由（单一事实来源）
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

logger = logging.getLogger("source_router")

__all__ = [
    "AllSourcesFailed",
    "ROUTES",
    "SOURCES",
    "RouteAttempt",
    "RouteOutcome",
    "RouteSpec",
    "SourceSpec",
    "UnknownRouteError",
    "describe_routes",
    "fallback_cmd",
    "route",
    "sources_for",
]

#: 单条失败信息的最大字符数（写入 ``RouteAttempt.error``，防日志被长 traceback 撑爆）
_MAX_ERROR_CHARS = 200


# ---------------------------------------------------------------------------
# 静态描述：源清单与路由表（优先级只在此处定义）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceSpec:
    """单个数据源的静态描述。

    Attributes:
        name: 源标识（``fetchers`` 字典的键、路由表 ``priority`` 的元素）。
        label: 人类可读名称（报告与日志展示用）。
        gated: 是否东方财富域名——为 True 时该源的请求由 ``em_gate`` 闸门节流。
        note: 备注（如「唯一源，无替代」），用于自检与文档一致性核对。
    """

    name: str
    label: str
    gated: bool
    note: str = ""


@dataclass(frozen=True)
class RouteSpec:
    """某类数据的路由定义（方案 §6 的「显式优先级路由」）。

    Attributes:
        kind: 数据种类标识（``route()`` 的第一个参数）。
        priority: 有序源列表，**索引越小优先级越高**。
        note: 该路由的口径说明（引用方案 §6 的依据）。
        cmd_template: 全源失败时渲染 ``fallback_cmd`` 的模板；无已验证命令时为空串。
    """

    kind: str
    priority: Tuple[str, ...]
    note: str
    cmd_template: str = ""


#: 全部已知数据源。新增源时只在此处登记，路由表即可引用。
SOURCES: Dict[str, SourceSpec] = {
    "eastmoney": SourceSpec(
        "eastmoney", "东方财富", True, "受 em_gate 闸门节流；方案定位为降级备胎"
    ),
    "sina": SourceSpec("sina", "新浪财经", False, "不受闸门节流，独立于东财风控"),
    "tencent": SourceSpec("tencent", "腾讯证券", False, "不受闸门节流"),
    "exchange": SourceSpec(
        "exchange", "交易所官网（上交所/深交所/北交所）", False, "权威源，方案 §6 列为第一优先"
    ),
    "cninfo": SourceSpec("cninfo", "巨潮资讯", False, "法定信息披露平台，独立于东财"),
    "baidu": SourceSpec("baidu", "百度股市通", False, "不受闸门节流"),
}

#: 显式优先级路由表（方案 §6「替代数据源路由强化」逐行对应）。
ROUTES: Dict[str, RouteSpec] = {
    "a_share_realtime": RouteSpec(
        kind="a_share_realtime",
        priority=("sina", "eastmoney"),
        note="A股实时行情：新浪全市场快照优先，东财为备胎（方案 §6「已实现」，此处收敛为声明式）",
        cmd_template="python tools/a_share/stock_quote.py --realtime {code}",
    ),
    "a_share_daily": RouteSpec(
        kind="a_share_daily",
        priority=("eastmoney", "tencent", "sina"),
        note="A股日线：东财 → 腾讯 → 新浪（腾讯回退为方案 §6「新增腾讯回退」落地项）",
        cmd_template="python tools/a_share/stock_quote.py --code {code} --source sina",
    ),
    "a_share_code_list": RouteSpec(
        kind="a_share_code_list",
        priority=("exchange", "eastmoney"),
        note="全 A 代码列表：交易所官网优先，东财兜底（方案 §6「现状已是交易所官网，保持」）",
    ),
    "a_share_report": RouteSpec(
        kind="a_share_report",
        priority=("cninfo", "eastmoney"),
        note="财报 / 股东：巨潮资讯优先，东财兜底（方案 §6「现状已双源」）",
    ),
    "hk_quote": RouteSpec(
        kind="hk_quote",
        priority=("sina", "eastmoney"),
        note="港股行情：新浪优先，东财备胎（方案 §6「现状已实现」）",
    ),
    "hk_financial": RouteSpec(
        kind="hk_financial",
        priority=("eastmoney",),
        note="港股财务：东财为**唯一源**（无替代）→ 必须受闸门保护并延长 TTL（方案 §6）",
    ),
}


# ---------------------------------------------------------------------------
# 结果与异常：让「过了哪些源、为什么失败」可被审计
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteAttempt:
    """单次源尝试的记录。

    Attributes:
        source: 源标识。
        label: 源的人类可读名称（失败日志与报告直接可用）。
        status: ``ok``（成功）/ ``failed``（已尝试但抛错）/ ``skipped``（无 fetcher 或被过滤）。
        elapsed_s: 该次尝试耗时（秒）；``skipped`` 时为 0。
        error: 失败原因（``异常类型: 消息``，已截断）。
    """

    source: str
    label: str
    status: str
    elapsed_s: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        """该源是否成功返回数据。"""
        return self.status == "ok"

    def as_dict(self) -> Dict[str, Any]:
        """转换为 JSON 兼容字典（写入工具 ``meta.routing.attempts``）。"""
        return {
            "source": self.source,
            "label": self.label,
            "status": self.status,
            "elapsed_s": round(self.elapsed_s, 3),
            "error": self.error,
        }


@dataclass(frozen=True)
class RouteOutcome:
    """一次成功路由的结果。

    Attributes:
        kind: 数据种类。
        source: 实际命中的源标识。
        label: 命中源的人类可读名称。
        value: 该源的返回数据（结构由该源自身决定）。
        attempts: 逐源尝试记录（含命中项与先前失败项）。
    """

    kind: str
    source: str
    label: str
    value: Any
    attempts: Tuple[RouteAttempt, ...]

    def as_dict(self) -> Dict[str, Any]:
        """可观测载荷：供工具写入 ``meta.routing``，使「数据来自哪个源」有据可查。"""
        return {
            "kind": self.kind,
            "source": self.source,
            "label": self.label,
            "attempts": [attempt.as_dict() for attempt in self.attempts],
        }


class UnknownRouteError(KeyError):
    """路由表中不存在该数据种类，或指定了不在优先级列表中的源。"""


class AllSourcesFailed(RuntimeError):
    """所有候选源均失败（方案 §3.4：降级必须自带可执行的替代命令）。

    Attributes:
        kind: 数据种类。
        attempts: 逐源尝试记录。
        fallback_cmd: 可直接执行的替代命令；无已验证命令时为空串。
    """

    def __init__(
        self,
        kind: str,
        attempts: Tuple[RouteAttempt, ...],
        fallback_cmd_text: str,
    ) -> None:
        """组装带尝试摘要与替代命令的异常消息。

        Args:
            kind: 数据种类。
            attempts: 逐源尝试记录。
            fallback_cmd_text: 已渲染的替代命令。
        """
        self.kind = kind
        self.attempts = attempts
        self.fallback_cmd = fallback_cmd_text
        detail = "; ".join(
            f"{item.source}={item.error or item.status}" for item in attempts
        )
        message = f"数据源全部失败：kind={kind}（{detail}）"
        if fallback_cmd_text:
            message += f"；fallback_cmd={fallback_cmd_text}"
        super().__init__(message)


# ---------------------------------------------------------------------------
# 路由查询与执行
# ---------------------------------------------------------------------------


def _spec(kind: str) -> RouteSpec:
    """取路由定义。

    Args:
        kind: 数据种类。

    Returns:
        对应的 ``RouteSpec``。

    Raises:
        UnknownRouteError: 路由表中无该种类。
    """
    try:
        return ROUTES[kind]
    except KeyError as exc:
        known = ", ".join(sorted(ROUTES))
        raise UnknownRouteError(
            f"未知数据种类 {kind!r}；已登记：{known}"
        ) from exc


def sources_for(
    kind: str,
    *,
    start_from: str = "",
    limit_to: Optional[Iterable[str]] = None,
) -> Tuple[str, ...]:
    """按优先级返回候选源序列（纯函数，供测试与工具预检）。

    Args:
        kind: 数据种类。
        start_from: 从该源开始（**含**该源），用于「用户显式指定起点源」场景；
            为空串表示从最高优先级开始。指定的源不在优先级列表中时抛错。
        limit_to: 白名单过滤（None 表示不过滤）。

    Returns:
        候选源元组（可能为空，表示无可用候选）。

    Raises:
        UnknownRouteError: 未知 kind，或 ``start_from`` 不在该路由的优先级列表中。
    """
    spec = _spec(kind)
    order: List[str] = list(spec.priority)
    if start_from:
        if start_from not in order:
            raise UnknownRouteError(
                f"源 {start_from!r} 不属于路由 {kind!r}（优先级：{list(spec.priority)}）"
            )
        order = order[order.index(start_from):]
    if limit_to is not None:
        allowed = set(limit_to)
        order = [name for name in order if name in allowed]
    return tuple(order)


def fallback_cmd(kind: str, **params: Any) -> str:
    """按路由模板渲染可执行的替代命令（方案 §3.4）。

    Args:
        kind: 数据种类。
        **params: 模板占位符取值（如 ``code="600519"``）。

    Returns:
        渲染后的命令；该路由无已验证命令模板、或参数不全时返回已渲染的部分 /
        空串（调用方应据此判断「本路由暂无自动出路」）。
    """
    template = _spec(kind).cmd_template
    if not template:
        return ""
    try:
        return template.format(**params)
    except KeyError:
        # 参数不全：退回模板原文，至少让调用方看到"该用哪条命令"
        return template


def route(
    kind: str,
    fetchers: Mapping[str, Callable[[], Any]],
    *,
    start_from: str = "",
    limit_to: Optional[Iterable[str]] = None,
    tool: str = "",
    params: Optional[Mapping[str, Any]] = None,
) -> RouteOutcome:
    """按显式优先级依次尝试各源，返回**首个成功结果**。

    Args:
        kind: 数据种类（``ROUTES`` 的键）。
        fetchers: 源标识 → 无参取数函数。未提供的源记为 ``skipped``
            （该源在此工具中未实现，属正常情况而非失败）。
        start_from: 起点源（含）；用于「用户以 ``--source`` 显式指定起点」场景，
            指定后**仍按路由表后续优先级回退**。空串表示从最高优先级开始。
        limit_to: 候选源白名单（None 表示不过滤）。
        tool: 工具标识（写入异常消息，便于定位调用方）。
        params: ``fallback_cmd`` 模板参数（如 ``{"code": "600519"}``）。

    Returns:
        ``RouteOutcome``：含命中源、数据与逐源尝试记录。

    Raises:
        UnknownRouteError: 未知 kind / 源不属于该路由 / 过滤后无候选源。
        AllSourcesFailed: 所有候选源均失败（异常自带 ``fallback_cmd``）。
    """
    order = sources_for(kind, start_from=start_from, limit_to=limit_to)
    if not order:
        raise UnknownRouteError(
            f"路由 {kind!r} 筛选后无候选源（start_from={start_from!r}, "
            f"limit_to={list(limit_to) if limit_to is not None else None}）"
        )

    attempts: List[RouteAttempt] = []
    for name in order:
        spec = SOURCES.get(name) or SourceSpec(name, name, False)
        fetcher = fetchers.get(name)
        if fetcher is None:
            # 该工具未实现此源：记为 skipped（不是失败），并继续下一个候选
            attempts.append(
                RouteAttempt(name, spec.label, "skipped", 0.0, "本工具未提供该源")
            )
            continue

        started = time.perf_counter()
        try:
            value = fetcher()
        except Exception as exc:  # noqa: BLE001 - 逐源兜底是路由器的职责
            elapsed = time.perf_counter() - started
            error = f"{type(exc).__name__}: {exc}"[:_MAX_ERROR_CHARS]
            attempts.append(RouteAttempt(name, spec.label, "failed", elapsed, error))
            logger.warning(
                "[source_router] %s 源 %s 失败（%.2fs），尝试下一候选：%s",
                kind,
                name,
                elapsed,
                error,
            )
            continue

        attempts.append(
            RouteAttempt(name, spec.label, "ok", time.perf_counter() - started)
        )
        if len(attempts) > 1:
            logger.info(
                "[source_router] %s 经 %s 回退后由 %s 提供数据",
                kind,
                ",".join(item.source for item in attempts[:-1]),
                name,
            )
        return RouteOutcome(
            kind=kind,
            source=name,
            label=spec.label,
            value=value,
            attempts=tuple(attempts),
        )

    # 全源失败：按 §3.4 抛出**自带可执行替代命令**的异常，禁止静默降级
    raise AllSourcesFailed(
        kind,
        tuple(attempts),
        fallback_cmd(kind, **dict(params or {})),
    )


def describe_routes() -> List[Dict[str, Any]]:
    """输出全部路由定义（单一事实来源，供自检与文档一致性核对）。

    Returns:
        路由列表，每项含 kind / priority / 各源描述 / 口径说明 / 替代命令模板。
    """
    described: List[Dict[str, Any]] = []
    for spec in ROUTES.values():
        described.append(
            {
                "kind": spec.kind,
                "priority": list(spec.priority),
                "sources": [
                    {
                        "name": name,
                        "label": (SOURCES.get(name) or SourceSpec(name, name, False)).label,
                        "gated": (SOURCES.get(name) or SourceSpec(name, name, False)).gated,
                        "note": (SOURCES.get(name) or SourceSpec(name, name, False)).note,
                    }
                    for name in spec.priority
                ],
                "note": spec.note,
                "fallback_cmd": spec.cmd_template,
            }
        )
    return described


def main(argv: Optional[List[str]] = None) -> int:
    """命令行入口：仅提供只读的路由表查看（不改任何数据、不发任何请求）。

    Args:
        argv: 参数列表（默认取 ``sys.argv[1:]``）。

    Returns:
        进程退出码（0 表示成功）。
    """
    parser = argparse.ArgumentParser(
        prog="source_router",
        description="数据源路由统一函数：列出各数据种类的显式优先级（方案 §6）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --list          # 列出全部路由与源描述（JSON）
  %(prog)s --source        # 仅列出源清单（JSON）

说明：本命令为**只读**，不发起任何网络请求。
""",
    )
    parser.add_argument("--list", action="store_true", help="列出全部路由（JSON）")
    parser.add_argument("--source", action="store_true", help="仅列出源清单（JSON）")
    args = parser.parse_args(argv)

    if args.source:
        payload: Dict[str, Any] = {
            "success": True,
            "data": [
                {
                    "name": spec.name,
                    "label": spec.label,
                    "gated": spec.gated,
                    "note": spec.note,
                }
                for spec in SOURCES.values()
            ],
        }
    else:
        payload = {"success": True, "data": describe_routes()}

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())