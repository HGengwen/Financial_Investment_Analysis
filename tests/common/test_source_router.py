#!/usr/bin/env python3
"""数据源路由统一函数（``tools/common/source_router.py``）单元测试。

覆盖方案 §6「替代数据源路由强化」的声明式路由表与通用执行器，全程**不联网**
（所有取数函数均为测试内构造的哨兵函数）：

1. 路由表口径：与方案 §6 逐行一致（种类、优先级、东财受闸标记）
2. 候选源解析：``start_from`` 起点收敛、``limit_to`` 白名单、未知种类 / 未知源报错
3. 执行器：命中首个成功源后**不再调用后续源**、失败回退并留痕、缺 fetcher 记
   ``skipped``、全源失败抛 ``AllSourcesFailed`` 且自带 ``fallback_cmd``
4. 可观测：``RouteOutcome.as_dict()`` / ``describe_routes()`` 结构稳定
5. CLI：``--list`` / ``--source`` 只读输出（不发起网络请求）

运行方式：
    python -m pytest tests/common/test_source_router.py -q
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common import source_router  # noqa: E402


# ---------------------------------------------------------------------------
# 1. 路由表口径（方案 §6 的单一事实来源）
# ---------------------------------------------------------------------------
def test_route_table_matches_plan_section_6() -> None:
    """路由优先级与方案 §6 表格逐行一致（改动即须同步方案）。"""
    expected = {
        "a_share_realtime": ("sina", "eastmoney"),
        "a_share_daily": ("eastmoney", "tencent", "sina"),
        "a_share_code_list": ("exchange", "eastmoney"),
        "a_share_report": ("cninfo", "eastmoney"),
        "hk_quote": ("sina", "eastmoney"),
        "hk_financial": ("eastmoney",),
    }
    assert set(source_router.ROUTES) == set(expected), "路由种类集合与方案不符"
    for kind, priority in expected.items():
        assert source_router.ROUTES[kind].priority == priority, f"{kind} 优先级不符"


def test_every_route_source_is_registered() -> None:
    """路由表引用的每个源都必须在 ``SOURCES`` 登记（防拼写漂移）。"""
    for spec in source_router.ROUTES.values():
        for name in spec.priority:
            assert name in source_router.SOURCES, f"{spec.kind} 引用了未登记的源 {name}"


def test_gated_flag_marks_eastmoney_only() -> None:
    """``gated``（受 em_gate 闸门节流）只对东财为真。"""
    gated = {name for name, spec in source_router.SOURCES.items() if spec.gated}
    assert gated == {"eastmoney"}


def test_hk_financial_has_single_source() -> None:
    """港股财务为东财**唯一源**（方案 §6：无替代 → 必须受闸门保护）。"""
    assert source_router.ROUTES["hk_financial"].priority == ("eastmoney",)
    assert "唯一源" in source_router.ROUTES["hk_financial"].note


# ---------------------------------------------------------------------------
# 2. 候选源解析（纯函数）
# ---------------------------------------------------------------------------
def test_sources_for_returns_full_priority() -> None:
    """无过滤时按优先级原样返回。"""
    assert source_router.sources_for("a_share_daily") == (
        "eastmoney",
        "tencent",
        "sina",
    )


def test_sources_for_start_from_trims_prefix() -> None:
    """``start_from`` 为**起点源（含）**：截掉更高优先级的前缀，其后仍按序回退。"""
    assert source_router.sources_for("a_share_daily", start_from="tencent") == (
        "tencent",
        "sina",
    )
    # 末位起点：只剩自身（等价于"锁定单一源"）
    assert source_router.sources_for("a_share_daily", start_from="sina") == ("sina",)


def test_sources_for_limit_to_filters_whitelist() -> None:
    """``limit_to`` 白名单过滤，保持原相对优先级。"""
    assert source_router.sources_for(
        "a_share_daily", limit_to={"sina", "eastmoney"}
    ) == ("eastmoney", "sina")


def test_sources_for_unknown_kind_raises() -> None:
    """未知数据种类 → ``UnknownRouteError``，且消息列出已登记种类。"""
    with pytest.raises(source_router.UnknownRouteError) as err:
        source_router.sources_for("not_a_kind")
    assert "a_share_daily" in str(err.value), "报错应提示可用种类"


def test_sources_for_start_from_not_in_route_raises() -> None:
    """起点源不属于该路由 → ``UnknownRouteError``（防静默返回全量优先级）。"""
    with pytest.raises(source_router.UnknownRouteError):
        source_router.sources_for("hk_financial", start_from="sina")


# ---------------------------------------------------------------------------
# 3. 执行器：命中、回退、跳过、全失败
# ---------------------------------------------------------------------------
def test_route_returns_first_success_without_calling_later_sources() -> None:
    """命中最高优先级源后**不得**继续调用后续源（避免无谓的额外取数）。"""
    calls: List[str] = []

    def _ok(name: str):
        """构造一个"被调用即记录"的成功取数函数。"""
        def _fetch() -> str:
            calls.append(name)
            return f"data-from-{name}"
        return _fetch

    outcome = source_router.route(
        "a_share_daily",
        {"eastmoney": _ok("eastmoney"), "tencent": _ok("tencent")},
    )
    assert outcome.value == "data-from-eastmoney"
    assert outcome.source == "eastmoney"
    assert outcome.label == "东方财富"
    assert calls == ["eastmoney"], "命中后不应再调用低优先级源"
    assert [item.status for item in outcome.attempts] == ["ok"]


def test_route_falls_back_and_records_attempts() -> None:
    """首源失败 → 回退次源，两种尝试均留痕（供工具写入 ``meta.routing``）。"""
    def _boom() -> Any:
        """模拟东财被封禁（方案 §2.1 的封禁信号形态）。"""
        raise ConnectionError("Remote end closed connection without response")

    outcome = source_router.route(
        "a_share_daily",
        {"eastmoney": _boom, "tencent": lambda: "tx-ok"},
    )
    assert outcome.value == "tx-ok"
    assert outcome.source == "tencent"
    statuses = [(item.source, item.status) for item in outcome.attempts]
    assert statuses == [("eastmoney", "failed"), ("tencent", "ok")]
    assert "ConnectionError" in outcome.attempts[0].error
    assert outcome.attempts[0].elapsed_s >= 0.0


def test_route_marks_missing_fetcher_as_skipped() -> None:
    """未提供 fetcher 的源记为 ``skipped``（本工具未实现该源 ≠ 失败）。"""
    outcome = source_router.route(
        "a_share_daily",
        {"tencent": lambda: "tx-ok"},
    )
    assert outcome.source == "tencent"
    assert [item.status for item in outcome.attempts] == ["skipped", "ok"]
    assert outcome.attempts[0].source == "eastmoney"
    assert "未提供该源" in outcome.attempts[0].error


def test_route_all_failed_raises_with_executable_fallback() -> None:
    """全源失败 → ``AllSourcesFailed``，且**自带可执行替代命令**（方案 §3.4）。"""
    def _boom() -> Any:
        """统一失败桩。"""
        raise TimeoutError("read timeout")

    with pytest.raises(source_router.AllSourcesFailed) as err:
        source_router.route(
            "a_share_daily",
            {
                "eastmoney": _boom,
                "tencent": _boom,
                "sina": _boom,
            },
            params={"code": "600519"},
        )
    exc = err.value
    assert exc.kind == "a_share_daily"
    assert len(exc.attempts) == 3
    assert exc.fallback_cmd == (
        "python tools/a_share/stock_quote.py --code 600519 --source sina"
    ), "替代命令须已渲染出具体代码"
    message = str(exc)
    assert "数据源全部失败" in message and "fallback_cmd=" in message
    assert "TimeoutError" in message


def test_route_empty_candidates_raises_unknown_route() -> None:
    """白名单过滤后无候选源 → ``UnknownRouteError``（而非静默返回空）。"""
    with pytest.raises(source_router.UnknownRouteError):
        source_router.route("hk_financial", {}, limit_to={"sina"})


def test_route_start_from_locks_to_single_source() -> None:
    """``start_from`` 指向末位源 → 只尝试该源（等价"用户锁定数据源"）。"""
    outcome = source_router.route("a_share_daily", {"sina": lambda: "s-ok"}, start_from="sina")
    assert [item.status for item in outcome.attempts] == ["ok"]
    assert outcome.source == "sina"


# ---------------------------------------------------------------------------
# 4. 可观测载荷与路由描述
# ---------------------------------------------------------------------------
def test_outcome_as_dict_shape() -> None:
    """``as_dict()`` 结构稳定（工具 ``meta.routing`` 的契约）。"""
    outcome = source_router.route("hk_quote", {"sina": lambda: [1, 2]})
    payload: Dict[str, Any] = outcome.as_dict()
    assert payload["kind"] == "hk_quote"
    assert payload["source"] == "sina"
    assert payload["label"] == "新浪财经"
    assert isinstance(payload["attempts"], list)
    assert set(payload["attempts"][0]) == {
        "source",
        "label",
        "status",
        "elapsed_s",
        "error",
    }
    assert json.dumps(payload, ensure_ascii=False), "载荷须可直接 JSON 序列化"


def test_describe_routes_covers_every_kind() -> None:
    """``describe_routes()`` 覆盖全部路由，且每项含优先级与源描述。"""
    described = source_router.describe_routes()
    assert len(described) == len(source_router.ROUTES)
    for item in described:
        assert item["kind"] in source_router.ROUTES
        assert item["priority"] == list(source_router.ROUTES[item["kind"]].priority)
        assert len(item["sources"]) == len(item["priority"])
        assert item["note"], "每条路由须有口径说明"


def test_fallback_cmd_rendering_and_missing_template() -> None:
    """``fallback_cmd``：有模板则渲染、无模板返回空串、缺参退回模板原文。"""
    assert source_router.fallback_cmd("a_share_daily", code="300502") == (
        "python tools/a_share/stock_quote.py --code 300502 --source sina"
    )
    # 港股财务无已验证命令模板 → 空串（调用方据此判断"本路由暂无自动出路"）
    assert source_router.fallback_cmd("hk_financial") == ""
    # 参数不全：退回模板原文，至少让调用方看到该用哪条命令
    assert source_router.fallback_cmd("a_share_daily") == (
        "python tools/a_share/stock_quote.py --code {code} --source sina"
    )


# ---------------------------------------------------------------------------
# 5. CLI（只读）
# ---------------------------------------------------------------------------
def test_cli_list_and_source_are_read_only(
    capsys: pytest.CaptureFixture,
) -> None:
    """``--list`` / ``--source`` 输出 JSON 且不发网络请求（纯本地表查询）。"""
    assert source_router.main(["--list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["success"] is True
    assert len(listed["data"]) == len(source_router.ROUTES)

    assert source_router.main(["--source"]) == 0
    sources = json.loads(capsys.readouterr().out)
    assert sources["success"] is True
    assert {item["name"] for item in sources["data"]} == set(source_router.SOURCES)