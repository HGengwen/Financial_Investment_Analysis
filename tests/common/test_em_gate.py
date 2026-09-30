"""东方财富请求闸门（``tools/common/em_gate.py``）单元测试。

覆盖方案 §7 测试矩阵中属于 P0 骨架（本子任务）范围的用例，全程**不联网**，
跨进程锁 / 状态 / 日志文件全部隔离到 ``tmp_path``：

1. 跨进程限流：``multiprocessing``（spawn）起 3 个独立进程 × 各 3 次放行
   → 相邻放行间隔 ≥ 最小间隔，且持锁区间互不重叠（任一时刻至多一个在途）
2. 最小间隔 + 抖动：相邻放行间隔落在 ``[min_interval, min_interval + jitter]``
3. 滑窗预算：分钟 / 5 分钟窗口用尽后阻塞放行，``check_budget()`` 判定 allowed=False
4. 封禁短路：``RemoteDisconnected`` / HTTP 403 → **绝不重试**，``consecutive_ban``
   与 ``totals.ban`` 累加；异常原样抛出（hook 不吞异常）
5. host 过滤：非东财 URL 完全透传（不取锁、不计预算、状态文件不产生）
6. 开关回退：``EM_GATE_ENABLED=0`` → 不 patch、不限流、``check_budget`` 恒放行
7. ``guarded``：缓存优先 → 预算预检 → 封禁不重试 + 异常挂载降级元信息
8. CLI：``status`` / ``report`` / ``reset`` 子命令可用；``import em_gate`` 无文件副作用
9. 降级语义（方案 §3.4）：``gate_code`` / ``is_gate_error`` 判定、统一载荷结构、
   ``install_cli`` 的进程级兜底（``sys.exit`` / ``sys.excepthook`` 各路径均输出
   ``success=false`` + ``meta.gate`` + ``fallback_cmd``，且幂等不重复打印）
10. 主机回退链（方案 §2.5）与东财请求强制 IPv4（``EM_GATE_FORCE_IPV4``，步骤 6 加固）：
   连续连接类错误 → 切回退主机 / 回退主机自身失败 → 放弃降级窗口；强制 IPv4
   仅作用于东财请求（非东财维持 urllib3 原地址族）。

运行方式：
    python -m pytest tests/common/test_em_gate.py -q
    python -m pytest tests/common/test_em_gate.py -q -s   # 打印多进程实测时间戳
"""

import json
import multiprocessing
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common import em_gate  # noqa: E402
from tools.common.em_gate import GateConfig  # noqa: E402

try:
    import requests  # noqa: E402
except ImportError:  # pragma: no cover - requests 为必装传递依赖
    requests = None  # type: ignore[assignment]

# 测试用 URL：东财与新浪（后者用于验证 host 过滤的透传行为）
_EM_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_EM_URL_403 = "https://push2.eastmoney.com/api/qt/ulist.np/get"
_SINA_URL = "https://hq.sinajs.cn/list=sh600519"


# ---------------------------------------------------------------------------
# 测试基础设施：配置隔离
# ---------------------------------------------------------------------------
def _base_env(tmp_path: Path, **overrides: Any) -> Dict[str, str]:
    """构造隔离到临时目录的闸门环境变量（默认开启、间隔小、抖动 0）。

    Args:
        tmp_path: pytest 提供的临时目录。
        **overrides: 需要覆盖的环境变量键值（值可为 int/float/str）。

    Returns:
        环境变量字典（值为字符串）。
    """
    env = {
        "EM_GATE_ENABLED": "1",
        "EM_GATE_MIN_INTERVAL": "0.10",
        "EM_GATE_JITTER_MAX": "0.0",
        "EM_GATE_LOCK_TIMEOUT": "20",
        "EM_GATE_MAX_HOLD_SECONDS": "8",
        "EM_GATE_BUDGET_PER_MIN": "1000",
        "EM_GATE_BUDGET_PER_5MIN": "1000",
        "EM_GATE_STATE_FILE": str(tmp_path / "state.json"),
        "EM_GATE_LOCK_FILE": str(tmp_path / "em_gate.lock"),
        "EM_GATE_LOG_FILE": str(tmp_path / "em_gate.jsonl"),
    }
    env.update({key: str(value) for key, value in overrides.items()})
    return env


@pytest.fixture()
def gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """将闸门配置重定向到 ``tmp_path``，用例结束后恢复真实配置。

    Yields:
        可调用对象 ``configure(**overrides) -> GateConfig``。
    """
    original: GateConfig = em_gate._CONFIG

    def configure(**overrides: Any) -> GateConfig:
        """把测试环境变量写入进程环境并刷新模块配置。

        Args:
            **overrides: 覆盖项（如 ``EM_GATE_BUDGET_PER_MIN="3"``）。

        Returns:
            刷新后的 ``GateConfig``（其 state/lock/log 均位于 tmp_path）。
        """
        for key, value in _base_env(tmp_path, **overrides).items():
            monkeypatch.setenv(key, value)
        return em_gate._reload_config()

    yield configure
    # 恢复真实配置（monkeypatch 的环境变量回滚发生在本 fixture 之后，故显式恢复）
    em_gate._CONFIG = original


@pytest.fixture(autouse=True)
def _restore_session_request():
    """自动清理：``install()`` 的 patch 是**进程级全局**，用例结束必须还原。

    若不还原，``requests.sessions.Session.request`` 的包装会在同一 pytest 进程内
    对**后续所有测试模块**生效（产生额外节流、写盘与状态污染），故每个用例后
    一律恢复原函数。
    """
    original = requests.sessions.Session.request
    yield
    requests.sessions.Session.request = original
    # 强制 IPv4 钩子同样是**进程级全局**（patch 在 urllib3.util.connection 上），
    # 且线程局部开关跨用例残留会影响后续模块，故一并还原。
    em_gate._restore_force_ipv4_hook()
    em_gate._FORCE_IPV4_LOCAL.active = False


def _release(url: str = _EM_URL, times: int = 1, sink: List[Any] = None) -> List[Any]:
    """经闸门放行 ``times`` 次（取锁 → 节奏 sleep → 回写状态 → 释放锁）。

    Args:
        url: 请求 URL。
        times: 放行次数。
        sink: 令牌收集列表；为 None 时内部新建。

    Returns:
        每次放行的 ``_GateToken`` 列表。
    """
    tokens: List[Any] = sink if sink is not None else []
    for _ in range(times):
        token = em_gate._before_request(url)
        tokens.append(token)
        em_gate._after_request(url, token, None)
    return tokens


def _read_state(cfg: GateConfig) -> Dict[str, Any]:
    """读取测试用状态文件。

    Args:
        cfg: 当前闸门配置（提供 state_file 路径）。

    Returns:
        状态字典。
    """
    return json.loads(cfg.state_file.read_text(encoding="utf-8"))


def _make_fake_send(status_code: int, exc: BaseException = None):
    """构造 ``Session.send`` 的假实现（避免真实网络 I/O）。

    Args:
        status_code: 要返回的 HTTP 状态码。
        exc: 非空时改为抛出该异常（模拟连接被服务端断开）。

    Returns:
        签名为 ``(self, request, **kwargs)`` 的假实现。
    """

    def _fake_send(self: Any, request: Any, **kwargs: Any) -> Any:
        """返回构造好的 Response，或抛出指定异常。"""
        if exc is not None:
            raise exc
        response = requests.Response()
        response.status_code = status_code
        response._content = b'{"data": "ok"}'
        response.url = request.url
        response.request = request
        return response

    return _fake_send


# ---------------------------------------------------------------------------
# 1. 异常分类与 host 过滤（纯函数）
# ---------------------------------------------------------------------------
def test_is_ban_signal_and_transient_classification() -> None:
    """封禁信号与瞬时异常的判定边界（方案 §2.1 迁出逻辑）。"""
    from http.client import RemoteDisconnected

    # RemoteDisconnected（连接被服务端直接断开）→ 封禁信号
    remote = RemoteDisconnected("Remote end closed connection without response")
    assert em_gate.is_ban_signal(remote) is True
    # 裸 RemoteDisconnected 不是 RequestException：瞬时判定只覆盖 requests 异常
    assert em_gate.is_transient(remote) is False

    # 文本回退匹配（被 requests 包装但保留原文）
    wrapped = requests.exceptions.ConnectionError("Remote end closed connection")
    assert em_gate.is_ban_signal(wrapped) is True

    # HTTP 403 → 封禁信号；HTTP 500 → 仅瞬时异常
    response_403 = requests.Response()
    response_403.status_code = 403
    http_403 = requests.exceptions.HTTPError("403 Client Error", response=response_403)
    assert em_gate.is_ban_signal(http_403) is True

    timeout = requests.exceptions.Timeout("read timeout")
    assert em_gate.is_ban_signal(timeout) is False
    assert em_gate.is_transient(timeout) is True

    # 非网络异常：既不重试也不计封禁
    assert em_gate.is_transient(ValueError("bad param")) is False
    assert em_gate.is_ban_signal(KeyError("字段缺失")) is False


def test_is_em_url_host_filter() -> None:
    """host 白名单：仅 ``*.eastmoney.com``（含 .com.cn）进入闸门。"""
    assert em_gate.is_em_url(_EM_URL) is True
    assert em_gate.is_em_url("https://push2delay.eastmoney.com/api/qt/stock/get") is True
    assert em_gate.is_em_url("http://datacenter-web.eastmoney.com/api/data/v1/get") is True
    assert em_gate.is_em_url("https://quote.eastmoney.com.cn/x") is True
    # 非东财与伪装域名一律透传
    assert em_gate.is_em_url(_SINA_URL) is False
    assert em_gate.is_em_url("https://www.baidu.com/s?wd=1") is False
    assert em_gate.is_em_url("https://eastmoney.com.evil.com/x") is False
    assert em_gate.is_em_url("https://noteastmoney.com/x") is False
    assert em_gate.is_em_url("") is False


# ---------------------------------------------------------------------------
# 2. 最小间隔 + 抖动
# ---------------------------------------------------------------------------
def test_min_interval_and_jitter(gate, monkeypatch: pytest.MonkeyPatch) -> None:
    """相邻放行间隔 ≥ 最小间隔，且抖动项确实参与间隔计算。

    抖动验证采用「可复现注入 + 真实随机统计」双路径：注入固定抽样值可精确断言
    「锁内 sleep = 最小间隔 + 抖动」；真实随机抽样则断言间隔出现明显离散。
    """
    cfg = gate(EM_GATE_MIN_INTERVAL="0.12", EM_GATE_JITTER_MAX="0.25")
    real_uniform = em_gate.random.uniform
    draws: List[Any] = []

    def fake_uniform(low: float, high: float) -> float:
        """固定抖动抽样值，使间隔可被精确断言。"""
        draws.append((low, high))
        return 0.2

    monkeypatch.setattr(em_gate.random, "uniform", fake_uniform)
    tokens = _release(times=2)

    # 每次请求都重新抖动抽样，且抽样区间为 [0, jitter_max]
    assert draws == [(0.0, cfg.jitter_max)] * 2
    for token in tokens:
        # 锁内 sleep = 最小间隔 + 抖动（+ 状态文件 I/O 开销，容差 0.3s）
        assert (
            cfg.min_interval + 0.2 - 0.02
            <= token.slept
            <= cfg.min_interval + 0.2 + 0.3
        )
    grants = [token.request_ts for token in tokens]
    gaps = [later - earlier for earlier, later in zip(grants, grants[1:])]
    assert min(gaps) >= cfg.min_interval - 0.02

    # 抖动关闭（抽样恒为 0）：锁内 sleep 不含随机项
    monkeypatch.setattr(em_gate.random, "uniform", lambda low, high: 0.0)
    zero_jitter = _release(times=2)
    assert max(token.slept for token in zero_jitter) <= cfg.min_interval + 0.3

    # 真实随机抖动：抽样值离散 → 锁内 sleep 出现明显离散（jitter_max=0.6）
    monkeypatch.setattr(em_gate.random, "uniform", real_uniform)
    gate(EM_GATE_MIN_INTERVAL="0.05", EM_GATE_JITTER_MAX="0.6")
    real_tokens = _release(times=6)
    spread = max(token.slept for token in real_tokens) - min(
        token.slept for token in real_tokens
    )
    assert spread > 0.1, f"抖动未生效（slept 离散度仅 {spread:.3f}s）"


# ---------------------------------------------------------------------------
# 3. 滑窗预算
# ---------------------------------------------------------------------------
def test_minute_window_budget_blocks(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """分钟预算用尽：``check_budget`` 拒绝，且下一次放行被滑窗阻塞。"""
    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_BUDGET_PER_MIN="3")
    # 窗口长度改小以加速测试（默认 60s / 300s，口径不变）
    monkeypatch.setattr(em_gate, "_WINDOW_MIN_SECONDS", 1.2)
    monkeypatch.setattr(em_gate, "_WINDOW_5MIN_SECONDS", 3.0)

    _release(times=3)
    report = em_gate.check_budget()
    assert report.allowed is False
    assert report.remaining_min == 0
    assert "分钟预算" in report.reason

    start = time.time()
    _release(times=1)
    elapsed = time.time() - start
    # 第 4 次需等待窗口内最早一次滑出窗口（≈1.2s），证明预算真正阻塞而非仅告警
    assert elapsed >= 0.9, f"预算未生效，第 4 次仅耗时 {elapsed:.3f}s"


def test_5min_window_budget_blocks(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """5 分钟预算用尽：同样拒绝并阻塞（分钟窗口不构成约束时）。"""
    gate(
        EM_GATE_MIN_INTERVAL="0",
        EM_GATE_JITTER_MAX="0",
        EM_GATE_BUDGET_PER_MIN="1000",
        EM_GATE_BUDGET_PER_5MIN="3",
    )
    monkeypatch.setattr(em_gate, "_WINDOW_MIN_SECONDS", 1.0)
    monkeypatch.setattr(em_gate, "_WINDOW_5MIN_SECONDS", 3.0)  # 放宽以留建窗耗时余量

    t_first = time.time()  # 第 1 次时间戳（第 4 次须等它滑出 5 分钟窗口）
    _release(times=3)
    report = em_gate.check_budget()
    assert report.allowed is False
    assert report.remaining_5min == 0
    assert "5 分钟预算" in report.reason

    start = time.time()
    # 建窗（连续 3 次写状态文件）耗时会计入窗口年龄，故先确认用例前提仍成立
    assert start - t_first < em_gate._WINDOW_5MIN_SECONDS - 0.3, "建窗过慢，前提不成立"
    _release(times=1)
    elapsed = time.time() - start
    # 语义断言：应等时长 = 窗口长度 - 第 1 次时间戳已流逝的部分（不用绝对秒数）
    expected = em_gate._WINDOW_5MIN_SECONDS - (start - t_first)
    assert elapsed >= expected - 0.2, (
        f"5 分钟预算未生效：应等 {expected:.3f}s，实等 {elapsed:.3f}s"
    )


# ---------------------------------------------------------------------------
# 4. 封禁短路（绝不重试）
# ---------------------------------------------------------------------------
def test_hook_records_ban_signal_and_does_not_swallow(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """传输层封禁信号：异常原样抛出、``consecutive_ban`` 与 ``totals.ban`` 累加。"""
    from http.client import RemoteDisconnected

    cfg = gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0")
    em_gate.install()
    signal = RemoteDisconnected("Remote end closed connection without response")
    monkeypatch.setattr(
        requests.sessions.Session, "send", _make_fake_send(200, exc=signal)
    )

    session = requests.Session()
    with pytest.raises(RemoteDisconnected) as excinfo:
        session.get(_EM_URL)
    # 异常透明：原异常对象未被替换或包装
    assert excinfo.value is signal

    state = _read_state(cfg)
    assert state["consecutive_ban"] == 1
    assert state["totals"]["ban"] == 1
    assert state["totals"]["calls"] == 1
    # 指标日志：每请求一行，状态标 ban
    log_lines = cfg.log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 1
    assert json.loads(log_lines[0])["status"] == "ban"


def test_hook_counts_403_response_as_ban(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTTP 403 响应（无异常抛出）同样计入封禁短路，且响应体不被改写。"""
    cfg = gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0")
    em_gate.install()
    monkeypatch.setattr(requests.sessions.Session, "send", _make_fake_send(403))

    response = requests.Session().get(_EM_URL_403)
    assert response.status_code == 403
    assert response.json() == {"data": "ok"}  # 响应体原样，未被闸门改写

    state = _read_state(cfg)
    assert state["consecutive_ban"] == 1
    assert state["totals"]["ban"] == 1


def test_guarded_never_retries_ban_signal(gate) -> None:
    """``guarded`` 对封禁信号**不重试**，并在异常上挂载降级元信息。"""
    from http.client import RemoteDisconnected

    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0")
    calls: List[float] = []

    def flaky() -> str:
        """模拟被东财封禁的业务调用（每次调用即失败）。"""
        calls.append(time.time())
        raise RemoteDisconnected("Remote end closed connection without response")

    wrapped = em_gate.guarded(flaky, api="stock_quote")
    with pytest.raises(RemoteDisconnected) as excinfo:
        wrapped()

    assert len(calls) == 1, "封禁信号必须短路，绝不重试"
    meta = getattr(excinfo.value, em_gate.GATE_META_ATTR)
    assert meta["api"] == "stock_quote"
    assert meta["gate"] == "ban_signal"
    assert meta["retried"] is False
    # 单次封禁未达 EM_GATE_CIRCUIT_THRESHOLD（默认 3）→ 熔断仍为 closed
    assert em_gate.check_budget().circuit == "closed"


# ---------------------------------------------------------------------------
# 5. host 过滤：非东财完全透传
# ---------------------------------------------------------------------------
def test_hook_passes_through_non_eastmoney(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """非东财请求零改动透传：不取锁、不计预算、不产生状态文件。"""
    cfg = gate()
    em_gate.install()
    monkeypatch.setattr(requests.sessions.Session, "send", _make_fake_send(200))

    session = requests.Session()
    response = session.get(_SINA_URL)
    assert response.status_code == 200
    assert not cfg.state_file.exists(), "非东财请求不得写入闸门状态"
    assert not cfg.lock_file.exists(), "非东财请求不得取锁"

    # 东财请求才会进入闸门并记账
    session.get(_EM_URL)
    assert _read_state(cfg)["totals"]["calls"] == 1
    assert _read_state(cfg)["hot_host"] == "push2his.eastmoney.com"


def test_install_is_idempotent_and_disabled_is_zero_intrusion(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install()`` 幂等；``EM_GATE_ENABLED=0`` 时完全不 patch 且不限流。"""
    cfg = gate()
    em_gate.install()
    patched = requests.sessions.Session.request
    assert getattr(patched, "_em_gate_patched", False) is True

    em_gate.install()
    assert requests.sessions.Session.request is patched, "install() 必须幂等，不叠加包装"

    # 总开关关闭：还原原始函数（完全退化为改造前行为）
    gate(EM_GATE_ENABLED="0")
    em_gate.install()
    assert getattr(requests.sessions.Session.request, "_em_gate_patched", False) is False

    report = em_gate.check_budget()
    assert report.allowed is True
    assert report.remaining_min == cfg.budget_per_min
    assert "EM_GATE_ENABLED=0" in report.reason

    # 关闭状态下即便仍走被包装函数（其他用例可能已装载），也不限流、不记账
    monkeypatch.setattr(requests.sessions.Session, "send", _make_fake_send(200))
    session = requests.Session()
    assert session.get(_SINA_URL).status_code == 200
    em_gate.install()  # 开关关闭时再次装载仍不 patch
    assert getattr(requests.sessions.Session.request, "_em_gate_patched", False) is False
    assert not cfg.state_file.exists()


# ---------------------------------------------------------------------------
# 6. guarded：缓存优先 + 预算预检
# ---------------------------------------------------------------------------
def test_guarded_cache_first_and_budget_precheck(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``guarded``：缓存命中不触网；预算用尽抛 ``EmGateBudgetExhausted``。"""
    gate(
        EM_GATE_MIN_INTERVAL="0",
        EM_GATE_JITTER_MAX="0",
        EM_GATE_BUDGET_PER_MIN="1",
    )
    monkeypatch.setattr(em_gate, "_WINDOW_MIN_SECONDS", 2.0)
    monkeypatch.setattr(em_gate, "_WINDOW_5MIN_SECONDS", 4.0)

    def must_not_call() -> str:
        """缓存命中时不允许被执行。"""
        raise AssertionError("缓存命中不应调用真实取数函数")

    cached = em_gate.guarded(
        must_not_call, api="stock_quote", cache_first=lambda: {"cached": True}
    )
    assert cached() == {"cached": True}

    def job() -> str:
        """模拟业务取数函数。"""
        return "net"

    _release(times=1)  # 用尽分钟预算（=1）
    with pytest.raises(em_gate.EmGateBudgetExhausted):
        em_gate.guarded(job, api="stock_quote")()
    # 未命中缓存时仍受预算保护（缓存缺失 + 预算不足 → 拒绝而非硬打）
    with pytest.raises(em_gate.EmGateBudgetExhausted):
        em_gate.call("GET", _EM_URL)


def test_call_raises_typed_error_on_403(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``call`` 遇 HTTP 403 抛带 response 的 ``HTTPError``（绝不重试）。"""
    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0")
    monkeypatch.setattr(requests.sessions.Session, "send", _make_fake_send(403))

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        em_gate.call("GET", _EM_URL_403, api="stock_quote")
    assert em_gate.is_ban_signal(excinfo.value) is True


# ---------------------------------------------------------------------------
# 7. 跨进程限流（真实多进程）
# ---------------------------------------------------------------------------
def _mp_worker(env: Dict[str, str], project_root: str, out_file: str, times: int) -> None:
    """子进程入口：经闸门放行 ``times`` 次并记录持锁区间。

    必须为模块级函数（multiprocessing spawn 需按引用 pickle）。

    Args:
        env: 闸门环境变量（隔离到临时目录）。
        project_root: 项目根目录（注入 sys.path，保证子进程可 import）。
        out_file: 本进程采集结果输出文件。
        times: 放行次数。
    """
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.update(env)

    from tools.common import em_gate as gate_module

    gate_module._reload_config()
    records: List[Dict[str, Any]] = []
    for _ in range(times):
        token = gate_module._before_request(_EM_URL)
        gate_module._after_request(_EM_URL, token, None)
        records.append(
            {
                "pid": os.getpid(),
                "lock_ts": token.lock_ts,
                "request_ts": token.request_ts,
                "released_ts": token.released_ts,
            }
        )
    Path(out_file).write_text(json.dumps(records), encoding="utf-8")


def test_multiprocess_requests_are_serialized(tmp_path: Path) -> None:
    """3 个独立进程 × 各 3 次：相邻放行间隔 ≥ 最小间隔，且持锁区间互不重叠。"""
    min_interval = 0.15
    env = _base_env(
        tmp_path,
        EM_GATE_MIN_INTERVAL=str(min_interval),
        EM_GATE_JITTER_MAX="0",
        EM_GATE_LOCK_TIMEOUT="60",
    )
    ctx = multiprocessing.get_context("spawn")
    out_files = [str(tmp_path / f"mp_{index}.json") for index in range(3)]
    processes = [
        ctx.Process(
            target=_mp_worker, args=(env, str(_PROJECT_ROOT), out_file, 3)
        )
        for out_file in out_files
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=180)
        assert process.exitcode == 0, f"子进程异常退出：exitcode={process.exitcode}"

    records: List[Dict[str, Any]] = []
    for out_file in out_files:
        records.extend(json.loads(Path(out_file).read_text(encoding="utf-8")))
    assert len(records) == 9, f"应有 9 次放行，实际 {len(records)}"

    records.sort(key=lambda item: item["lock_ts"])
    grants = sorted(item["request_ts"] for item in records)
    gaps = [later - earlier for earlier, later in zip(grants, grants[1:])]
    print(
        f"\n[多进程实测] {len(records)} 次放行，进程数={len({r['pid'] for r in records})}，"
        f"相邻放行最小间隔={min(gaps):.4f}s（要求 ≥ {min_interval}s），"
        f"最大间隔={max(gaps):.4f}s"
    )
    for record in records[:4]:
        print(
            f"  pid={record['pid']} lock_ts={record['lock_ts']:.4f} "
            f"grant_ts={record['request_ts']:.4f} released_ts={record['released_ts']:.4f}"
        )

    # 断言 1：相邻放行间隔 ≥ 最小间隔（留 20ms 时钟粒度容差）
    assert min(gaps) >= min_interval - 0.02, f"相邻间隔不足：{min(gaps):.4f}s"

    # 断言 2：任一时刻至多 1 个东财请求在途 → 持锁区间互不重叠
    previous_release: float = None
    for record in records:
        assert record["released_ts"] >= record["request_ts"]
        if previous_release is not None:
            assert record["lock_ts"] >= previous_release - 0.005, (
                f"持锁区间重叠：{record['lock_ts']:.4f} < {previous_release:.4f}"
            )
        previous_release = record["released_ts"]


# ---------------------------------------------------------------------------
# 8. CLI 与 import 副作用
# ---------------------------------------------------------------------------
def _run_cli(tmp_path: Path, *args: str) -> Dict[str, Any]:
    """子进程执行 ``em_gate`` CLI 并解析 JSON 输出。

    Args:
        tmp_path: 临时目录（提供隔离的状态/锁/日志路径）。
        *args: CLI 参数（如 ``"status"``）。

    Returns:
        解析后的 JSON 字典。
    """
    env = dict(os.environ)
    env.update(_base_env(tmp_path))
    proc = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "tools/common/em_gate.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_PROJECT_ROOT),
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, f"CLI 失败：{proc.stderr}"
    return json.loads(proc.stdout)


def test_cli_status_report_reset(tmp_path: Path) -> None:
    """CLI：``status`` 输出 §3.3 字段；``report`` / ``reset`` 均可正常执行。"""
    status = _run_cli(tmp_path, "status")
    assert status["success"] is True
    assert {
        "circuit",
        "last_request_ago_s",
        "remaining_min",
        "remaining_5min",
        "allowed",
    } <= set(status["data"])
    # 闸门默认开启且无历史请求 → 允许且额度为满
    assert status["data"]["allowed"] is True
    assert status["data"]["last_request_ago_s"] is None
    # 熔断器自步骤 4（P1）起生效：冷却窗口 + 半开单探测
    assert status["meta"]["circuit_enforced"] is True
    assert status["data"]["circuit"] == "closed"

    report = _run_cli(tmp_path, "report", "--limit", "50")
    assert report["success"] is True
    assert report["data"]["totals"]["calls"] == 0

    reset = _run_cli(tmp_path, "reset")
    assert reset["success"] is True
    assert reset["data"]["removed_state"] is False  # 此前无状态文件


def test_import_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    """``import em_gate`` 无副作用：不建目录、不建文件、不 patch requests。"""
    nested = tmp_path / "nested"
    env = dict(os.environ)
    env.update(
        {
            "EM_GATE_STATE_FILE": str(nested / "state.json"),
            "EM_GATE_LOCK_FILE": str(nested / "em_gate.lock"),
            "EM_GATE_LOG_FILE": str(nested / "em_gate.jsonl"),
        }
    )
    code = (
        "import requests, tools.common.em_gate as m;"
        "print(int(getattr(requests.sessions.Session.request, '_em_gate_patched', False)),"
        " m._CONFIG.state_file)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_PROJECT_ROOT),
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, f"import 失败：{proc.stderr}"
    assert proc.stdout.startswith("0 "), "import 期不得 patch Session.request"
    assert not nested.exists(), "import 期不得创建锁/状态目录"


# ---------------------------------------------------------------------------
# 9. 降级语义（方案 §3.4）：统一载荷 / 判定 / 进程级兜底
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _restore_gate_cli_state():
    """自动清理：降级语义涉及的进程级状态（``sys.exit`` / ``excepthook`` / 拒绝快照）。

    ``install_cli()`` 会包装 ``sys.exit`` 与 ``sys.excepthook``（进程级全局），
    若不还原会污染同一 pytest 进程内的后续用例与 pytest 自身的退出路径。
    """
    original_exit = sys.exit
    original_hook = sys.excepthook
    original_rejection = em_gate._LAST_REJECTION
    original_installed = em_gate._CLI_HOOKS_INSTALLED
    original_config = em_gate._CONFIG
    yield
    sys.exit = original_exit
    sys.excepthook = original_hook
    em_gate._LAST_REJECTION = original_rejection
    em_gate._CLI_HOOKS_INSTALLED = original_installed
    em_gate._CONFIG = original_config


def test_gate_code_mapping() -> None:
    """异常类型 → ``meta.gate`` 取值映射（方案 §3.4）。"""
    assert em_gate.gate_code(em_gate.EmCircuitOpen("东财闸门拒绝：熔断冷却中")) == "circuit_open"
    assert em_gate.gate_code(em_gate.EmGateTimeout("东财闸门取锁超时")) == "gate_timeout"
    assert (
        em_gate.gate_code(em_gate.EmGateBudgetExhausted("东财闸门拒绝：预算"))
        == "budget_exhausted"
    )
    assert em_gate.gate_code(em_gate.EmGateError("东财闸门故障")) == "gate_error"


def test_is_gate_error_covers_wrapped_message_and_rejects_business_error() -> None:
    """闸门拒绝判定：类型 / 标注 / 被包装成字符串的消息三条路径。"""
    wrapped = RuntimeError(
        "EastMoney: 东财闸门取锁超时（60.0s）：https://push2his.eastmoney.com/x"
    )
    assert em_gate.is_gate_error(wrapped) is True  # 类型信息丢失后仍可判定
    assert em_gate.is_gate_error(RuntimeError("KeyError: 'ROE'")) is False
    assert em_gate.is_gate_error(ValueError("未知指标")) is False

    ban = RuntimeError("HTTP 403")
    setattr(ban, em_gate.GATE_META_ATTR, {"api": "x", "gate": "ban_signal", "retried": False})
    assert em_gate.is_gate_error(ban) is True
    assert em_gate.gate_code(ban) == "ban_signal"


def test_degraded_payload_matches_plan_shape() -> None:
    """降级载荷结构与方案 §3.4 逐字段一致，且绝不伪造 success=true。"""
    payload = em_gate.degraded_payload(
        em_gate.EmCircuitOpen("东财闸门拒绝：熔断冷却中（剩余 24 分钟）"),
        tool="stock_quote",
        fallback_cmd="python tools/a_share/stock_quote.py --code 600519 --source sina",
        cache_age_days=3,
    )
    assert payload["success"] is False
    assert payload["error"] == "东财闸门拒绝：熔断冷却中（剩余 24 分钟）"
    meta = payload["meta"]
    assert meta["gate"] == "circuit_open"
    assert meta["stale"] is True
    assert meta["cache_age_days"] == 3
    assert meta["fallback_cmd"] == "python tools/a_share/stock_quote.py --code 600519 --source sina"
    assert meta["tool"] == "stock_quote"


def test_emit_rejection_only_for_gate_rejections(capsys: pytest.CaptureFixture) -> None:
    """非闸门异常不输出任何内容；闸门拒绝输出单行统一载荷 JSON。"""
    assert em_gate.emit_rejection(RuntimeError("普通业务错误"), tool="t") is False
    assert capsys.readouterr().err == ""

    handled = em_gate.emit_rejection(
        em_gate.EmGateTimeout("东财闸门取锁超时（1s）"), tool="t", fallback_cmd="python x.py"
    )
    assert handled is True
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["success"] is False
    assert payload["meta"]["gate"] == "gate_timeout"
    assert payload["meta"]["fallback_cmd"] == "python x.py"


def test_enter_gate_records_rejection_snapshot(gate) -> None:
    """``_enter_gate`` 在拒绝时记录进程内快照（进程级兜底的判定依据）。"""
    gate(EM_GATE_LOCK_TIMEOUT="0")  # 取锁超时 0s → 立即 EmGateTimeout
    with pytest.raises(em_gate.EmGateTimeout):
        em_gate._enter_gate(_EM_URL)
    assert em_gate._has_fresh_rejection() is True
    assert em_gate.gate_code() == "gate_timeout"


def test_render_fallback_cmd_substitutes_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    """``{symbol}`` 占位符按命令行参数渲染；解析不到时退化为 ``<代码>``。"""
    monkeypatch.setattr(sys, "argv", ["stock_quote.py", "--code", "600519"])
    assert em_gate._render_fallback_cmd("cmd --code {symbol}") == "cmd --code 600519"

    # 8 位日期、3 位期数均不是标的代码（形态白名单：5~6 位纯数字）
    monkeypatch.setattr(sys, "argv", ["stock_quote.py", "--start", "20260101", "--periods", "5"])
    assert em_gate._render_fallback_cmd("cmd --code {symbol}") == "cmd --code <代码>"
    assert em_gate._render_fallback_cmd("no-placeholder") == "no-placeholder"


def test_install_cli_degrades_on_sys_exit(
    gate, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """闸门拒绝被内层 except 吞掉后，``sys.exit`` 兜底仍输出统一载荷（幂等）。"""
    gate()
    monkeypatch.setattr(sys, "argv", ["stock_financial.py", "--code", "600519"])
    em_gate.install_cli(tool="stock_financial", fallback_cmd="python x.py --code {symbol}")
    em_gate._record_rejection(em_gate.EmGateTimeout("东财闸门取锁超时（1s）"))

    with pytest.raises(SystemExit) as excinfo:
        sys.exit(1)
    assert excinfo.value.code == 1
    lines = [line for line in capsys.readouterr().err.strip().splitlines() if line]
    payload = json.loads(lines[-1])
    assert payload["success"] is False
    assert payload["meta"]["gate"] == "gate_timeout"
    assert payload["meta"]["fallback_cmd"] == "python x.py --code 600519"

    # 幂等：同一次拒绝只输出一次，再次退出不再重复打印
    with pytest.raises(SystemExit):
        sys.exit(1)
    assert capsys.readouterr().err == ""


def test_install_cli_disabled_installs_no_hooks(gate) -> None:
    """``EM_GATE_ENABLED=0`` 时不装任何进程级兜底（完全退化为改造前行为）。"""
    original_exit = sys.exit
    original_hook = sys.excepthook
    gate(EM_GATE_ENABLED="0")
    em_gate.install_cli(tool="t", fallback_cmd="x")
    assert sys.exit is original_exit
    assert sys.excepthook is original_hook
    assert em_gate._CLI_HOOKS_INSTALLED is False


def test_filelock_missing_raises_gate_error_not_attribute_error(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """filelock 缺失时受管控请求抛 ``EmGateError``（**非** AttributeError），并带可执行降级命令。

    回归守卫：``_before_request`` 内的 ``FileLock is None`` 检查若被移除，
    这里会退化为 ``AttributeError: 'NoneType' object has no attribute ...``，
    且 ``is_gate_error`` 不再成立 → 工具层的统一降级载荷失效。
    """
    gate()
    monkeypatch.setattr(em_gate, "FileLock", None)
    monkeypatch.setattr(em_gate, "_FileLockTimeout", None)

    with pytest.raises(em_gate.EmGateError) as excinfo:
        em_gate._before_request("https://push2his.eastmoney.com/api/qt/stock/kline/get")

    assert not isinstance(excinfo.value, AttributeError)
    assert em_gate.is_gate_error(excinfo.value)
    assert em_gate.gate_code(excinfo.value) == "gate_error"
    assert "filelock" in str(excinfo.value)

    payload = em_gate.degraded_payload(
        excinfo.value, tool="stock_quote", fallback_cmd="python x.py --code {symbol}"
    )
    assert payload["success"] is False
    assert payload["meta"]["gate"] == "gate_error"
    assert payload["meta"]["fallback_cmd"] == "python x.py --code {symbol}"


def test_status_reports_not_allowed_when_filelock_missing(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """filelock 缺失时 ``check_budget().allowed`` 必须为 ``False``（预检不得谎报可放行）。

    否则编排层按 CLAUDE.md「并发前置」读到 ``data.allowed=True`` 会误判可并发，
    随后所有东财调用集体被拒——预检快照与 ``_before_request`` 放行判据不一致。
    """
    gate()
    assert em_gate.check_budget().allowed is True  # 前提：filelock 正常时放行

    monkeypatch.setattr(em_gate, "FileLock", None)
    report = em_gate.check_budget()
    assert report.allowed is False
    assert report.reason.startswith("filelock 未安装")
    # 熔断相位与预算剩余仍如实反映真实状态（不被 filelock 分支掩盖或谎报为 0）
    assert report.circuit == "closed"
    assert report.remaining_min > 0

    status = em_gate.cmd_status()
    assert status["data"]["allowed"] is False
    assert status["data"]["reason"].startswith("filelock 未安装")
    assert status["meta"]["filelock_available"] is False


# ---------------------------------------------------------------------------
# 13. 熔断器：冷却窗口 + 半开单探测（方案 §2.3 / §9 P1）
# ---------------------------------------------------------------------------
_CIRCUIT_ENV: Dict[str, str] = {
    "EM_GATE_MIN_INTERVAL": "0",
    "EM_GATE_JITTER_MAX": "0",
    "EM_GATE_CIRCUIT_THRESHOLD": "3",
    "EM_GATE_CIRCUIT_COOLDOWN_MIN": "30",
}


def _seed_state(cfg: GateConfig, **fields: Any) -> None:
    """直接改写测试状态文件（构造熔断等前置状态）。

    Args:
        cfg: 当前闸门配置（提供 state_file 路径）。
        **fields: 需要覆盖的状态字段。
    """
    state = em_gate._read_state(cfg.state_file)
    state.update(fields)
    em_gate._write_state(state, cfg.state_file)


def _ban_once(url: str = _EM_URL) -> None:
    """经闸门放行一次并回写一个封禁信号（累加 ``consecutive_ban``）。

    Args:
        url: 请求 URL。
    """
    from http.client import RemoteDisconnected

    token = em_gate._before_request(url)
    em_gate._after_request(
        url, token, RemoteDisconnected("Remote end closed connection")
    )


def test_circuit_opens_after_threshold_and_rejects_without_lock(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """连续 3 次封禁 → 打开熔断；第 4 次**不取锁**直接抛 ``EmCircuitOpen``。"""
    cfg = gate(**_CIRCUIT_ENV)

    acquisitions: List[int] = []
    real_lock = em_gate.FileLock

    def _spy_lock(path: str) -> Any:
        """记录取锁次数后转发真实 FileLock 构造。"""
        acquisitions.append(1)
        return real_lock(path)

    monkeypatch.setattr(em_gate, "FileLock", _spy_lock)

    for _ in range(3):
        _ban_once()
    state = _read_state(cfg)
    assert state["consecutive_ban"] == 3
    assert state["circuit_open_until"] > time.time(), "达阈值应打开熔断"
    assert state["half_open_probe_used"] is False

    taken = len(acquisitions)
    with pytest.raises(em_gate.EmCircuitOpen) as excinfo:
        em_gate._before_request(_EM_URL)
    assert len(acquisitions) == taken, "熔断短路必须发生在取锁之前"
    assert "东财闸门" in str(excinfo.value)  # 消息含闸门标记，供 §3.4 降级判定
    assert em_gate.gate_code(excinfo.value) == "circuit_open"

    report = em_gate.check_budget()
    assert report.allowed is False
    assert report.circuit == "open"
    assert "熔断冷却中" in report.reason


def test_half_open_probe_is_single_and_closes_circuit(gate) -> None:
    """冷却到期 → 半开：只放行 1 个探测位；探测成功即关闭熔断。"""
    cfg = gate(**_CIRCUIT_ENV)
    # 模拟冷却窗口已到期（直接改写状态文件，避免真实等待 30 分钟）
    _seed_state(cfg, circuit_open_until=time.time() - 1.0, consecutive_ban=3)

    report = em_gate.check_budget()
    assert report.circuit == "half_open"
    assert report.allowed is True, "半开态应放行一个探测位"

    probe = em_gate._before_request(_EM_URL)
    assert probe.is_probe is True
    assert _read_state(cfg)["half_open_probe_used"] is True, "探测位占位须立即落盘"

    # 探测位唯一：同一冷却周期内其余请求被拒
    with pytest.raises(em_gate.EmCircuitOpen) as excinfo:
        em_gate._before_request(_EM_URL)
    assert em_gate.gate_code(excinfo.value) == "circuit_open"
    assert "半开探测进行中" in str(excinfo.value)
    assert em_gate.check_budget().allowed is False

    em_gate._after_request(_EM_URL, probe, None)
    state = _read_state(cfg)
    assert state["circuit_open_until"] == 0.0, "探测成功应关闭熔断"
    assert state["half_open_probe_used"] is False
    assert state["consecutive_ban"] == 0
    assert em_gate.check_budget().circuit == "closed"


def test_half_open_probe_reban_reopens_circuit(gate) -> None:
    """半开探测再被封禁 → 立即重开冷却（不必重新累计到阈值）。"""
    cfg = gate(**_CIRCUIT_ENV)
    _seed_state(cfg, circuit_open_until=time.time() - 1.0, consecutive_ban=1)

    probe = em_gate._before_request(_EM_URL)
    assert probe.is_probe is True
    from http.client import RemoteDisconnected

    em_gate._after_request(
        _EM_URL, probe, RemoteDisconnected("Remote end closed connection")
    )

    state = _read_state(cfg)
    assert state["consecutive_ban"] == 2
    assert state["circuit_open_until"] > time.time(), "探测失败应立即重开冷却"
    assert state["half_open_probe_used"] is False
    assert em_gate.check_budget().circuit == "open"


def test_transient_error_never_opens_circuit(gate) -> None:
    """非封禁的瞬时错误不计入连续封禁、也不打开熔断（防误判，方案 §8）。"""
    cfg = gate(**_CIRCUIT_ENV)
    for _ in range(5):
        token = em_gate._before_request(_EM_URL)
        em_gate._after_request(
            _EM_URL, token, requests.exceptions.Timeout("read timeout")
        )

    state = _read_state(cfg)
    assert state["consecutive_ban"] == 0
    assert state["circuit_open_until"] == 0.0
    assert em_gate.check_budget().circuit == "closed"


def test_circuit_is_bypassed_when_gate_disabled(gate) -> None:
    """``EM_GATE_ENABLED=0``：熔断态亦不生效（零侵入回退基线）。"""
    cfg = gate(EM_GATE_ENABLED="0")
    _seed_state(cfg, circuit_open_until=time.time() + 3600, consecutive_ban=9)

    token = em_gate._before_request(_EM_URL)
    assert token.is_probe is False
    assert token.lock is None, "闸门关闭时不得取锁"

    em_gate._after_request(_EM_URL, token, None)
    state = _read_state(cfg)
    assert state["consecutive_ban"] == 9, "闸门关闭时不回写状态"


def test_is_active_tracks_install_and_switch(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``is_active()``：未 ``install()`` 或总开关关闭时为 False。"""
    monkeypatch.setattr(em_gate, "_ORIGINAL_SESSION_REQUEST", None)
    gate(EM_GATE_ENABLED="1")
    assert em_gate.is_active() is False

    em_gate.install()
    assert em_gate.is_active() is True

    gate(EM_GATE_ENABLED="0")
    assert em_gate.is_active() is False


def test_cli_status_exposes_circuit_fields(tmp_path: Path) -> None:
    """``status`` 暴露熔断相位与冷却截止时刻，编排层据此改串行或延后盘后。"""
    status = _run_cli(tmp_path, "status")
    assert status["meta"]["circuit_enforced"] is True
    assert status["meta"]["circuit_threshold"] >= 1
    assert status["meta"]["circuit_cooldown_min"] >= 1
    assert status["data"]["circuit"] == "closed"
    assert status["data"]["circuit_open_until"] == 0.0
    assert status["data"]["half_open_probe_used"] is False


# ---------------------------------------------------------------------------
# 6. 请求指纹与代理策略（步骤 5 / 方案 §7 矩阵）
# ---------------------------------------------------------------------------
def _capture_request(record: List[Dict[str, Any]]):
    """构造记录实际 headers / kwargs 的假 ``Session.send``（避免真实网络 I/O）。

    ``Session.request`` 会把注入的 headers 并入 PreparedRequest，故指纹须从
    ``request.headers`` 读取；``proxies`` 则保留在 send 的 kwargs 中；
    实际 URL（可被主机回退改写）从 ``request.url`` 读取。

    Args:
        record: 收集列表，每项形如 ``{"url": ..., "headers": ..., "kwargs": ...}``。

    Returns:
        签名为 ``(self, request, **kwargs)`` 的假实现。
    """

    def _fake_send(self: Any, request: Any, **kwargs: Any) -> Any:
        """记录本次请求的实际 URL / headers / send kwargs 后返回 200。"""
        record.append({
            "url": request.url,
            "headers": dict(request.headers),
            "kwargs": kwargs,
        })
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"data": "ok"}'
        response.url = request.url
        response.request = request
        return response

    return _fake_send


def test_is_connection_error_classification() -> None:
    """连接类错误判定边界：**封禁信号必须排除**（§10.3 禁止对封禁重试）。"""
    from http.client import RemoteDisconnected

    # 封禁信号同属 ConnectionError，但判定必须返回 False（否则会改直连重试）
    assert (
        em_gate.is_connection_error(
            requests.exceptions.ConnectionError("Remote end closed connection")
        )
        is False
    )
    assert (
        em_gate.is_connection_error(
            RemoteDisconnected("Remote end closed connection without response")
        )
        is False
    )
    # 真连接类错误：代理不可用 / 连接超时 / 裸 socket 连接错误
    assert (
        em_gate.is_connection_error(
            requests.exceptions.ProxyError("Cannot connect to proxy")
        )
        is True
    )
    assert em_gate.is_connection_error(requests.exceptions.ConnectTimeout("t")) is True
    assert em_gate.is_connection_error(ConnectionError("connection reset")) is True
    # 非连接类：业务错误 / HTTP 状态错误（4xx 不等于连接失败）
    assert em_gate.is_connection_error(ValueError("bad param")) is False
    assert em_gate.is_connection_error(requests.exceptions.HTTPError("404")) is False


def test_fingerprint_injected_and_explicit_headers_kept(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """东财请求注入 UA / Referer / keep-alive，且**不覆盖**调用方显式 headers。"""
    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0")
    em_gate.install()
    seen: List[Dict[str, Any]] = []
    monkeypatch.setattr(requests.sessions.Session, "send", _capture_request(seen))

    requests.Session().get(_EM_URL)
    headers = seen[0]["headers"]
    assert headers["User-Agent"] == em_gate._EM_UA
    assert headers["Referer"] == "https://quote.eastmoney.com/"
    assert headers["Connection"] == "keep-alive"

    # 调用方显式指定者优先：闸门只补空缺，不覆盖
    requests.Session().get(
        _EM_URL,
        headers={"User-Agent": "my-agent", "Referer": "https://example.com/"},
    )
    explicit = seen[1]["headers"]
    assert explicit["User-Agent"] == "my-agent"
    assert explicit["Referer"] == "https://example.com/"
    assert explicit["Connection"] == "keep-alive"  # 未指定者仍被补齐

    # 非东财：连指纹都不注入（零侵入）
    requests.Session().get(_SINA_URL)
    assert "Referer" not in seen[2]["headers"]


def test_proxy_bypass_for_eastmoney_only(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``EM_GATE_BYPASS_PROXY=1``：东财剥离代理直连，非东财代理设置不变。"""
    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_BYPASS_PROXY="1")
    em_gate.install()
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:8888")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    seen: List[Dict[str, Any]] = []
    monkeypatch.setattr(requests.sessions.Session, "send", _capture_request(seen))

    session = requests.Session()
    session.get(_EM_URL)
    session.get(_SINA_URL)

    # 东财：http/https 显式置空串以压过 env 代理合并（传 {} 会被 setdefault 回填）
    # 注：proxies 还会多一个 ``em_gate_bypass`` 键——``EM_GATE_BYPASS_PROXY`` 末 6 字符
    # 恰为 ``_proxy``，被 urllib ``getproxies_environment`` 误当作「em_gate_bypass 方案
    # 的代理」注入；该键名不是 URL scheme，``select_proxy`` 永不选中，无功能影响。
    em_proxies = seen[0]["kwargs"]["proxies"]
    assert em_proxies["http"] == "" and em_proxies["https"] == ""
    assert not requests.utils.select_proxy(_EM_URL, em_proxies), "东财必须真实直连"
    # 非东财：零注入，env 代理照常生效（透传语义不变）
    assert seen[1]["kwargs"]["proxies"]["https"] == "http://127.0.0.1:8888"


def test_proxy_failure_retries_direct_once(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``EM_GATE_BYPASS_PROXY=0``：代理连接失败 → 剥离代理**直连重试一次**。"""
    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_BYPASS_PROXY="0"
    )
    em_gate.install()
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    attempts: List[Dict[str, Any]] = []

    def _fake_send(self: Any, request: Any, **kwargs: Any) -> Any:
        """首次经代理失败（ProxyError），第二次直连成功。"""
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise requests.exceptions.ProxyError("Cannot connect to proxy")
        return _make_fake_send(200)(self, request, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "send", _fake_send)
    response = requests.Session().get(_EM_URL)

    assert response.status_code == 200
    assert len(attempts) == 2, "代理连接失败必须直连重试一次（且仅一次）"
    assert attempts[0]["proxies"]["https"] == "http://127.0.0.1:8888"
    assert attempts[1]["proxies"]["https"] == ""
    assert not requests.utils.select_proxy(_EM_URL, attempts[1]["proxies"])

    state = _read_state(cfg)
    assert state["totals"]["calls"] == 2, "重试同样走完整闸门（重新取锁 + 节奏）"
    assert state["consecutive_ban"] == 0, "连接类错误不计入封禁（§8 误判缓解）"
    records = [
        json.loads(line)
        for line in cfg.log_file.read_text(encoding="utf-8").strip().splitlines()
    ]
    assert [record["proxy_retry"] for record in records] == [False, True]
    assert [record["status"] for record in records] == ["error", "ok"]


def test_ban_signal_is_never_retried_direct(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """封禁信号**绝不**直连重试（方案 §10.3）：一次即抛，仅累加封禁计数。"""
    from http.client import RemoteDisconnected

    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_BYPASS_PROXY="0"
    )
    em_gate.install()
    signal = RemoteDisconnected("Remote end closed connection without response")
    attempts: List[Dict[str, Any]] = []

    def _fake_send(self: Any, request: Any, **kwargs: Any) -> Any:
        """每次调用都以封禁信号失败。"""
        attempts.append(kwargs)
        raise signal

    monkeypatch.setattr(requests.sessions.Session, "send", _fake_send)
    with pytest.raises(RemoteDisconnected) as excinfo:
        requests.Session().get(_EM_URL)

    assert excinfo.value is signal, "异常透明：不得被包装或替换"
    assert len(attempts) == 1, "封禁是全站级的，换直连无用 → 绝不重试"
    state = _read_state(cfg)
    assert state["consecutive_ban"] == 1
    assert state["totals"]["ban"] == 1


# ---------------------------------------------------------------------------
# 7. 主机回退链（方案 §2.5 / §7 矩阵「主机回退」行）
# ---------------------------------------------------------------------------
#: 主主机 / 回退主机（与 em_gate._HOST_FALLBACK_MAP 对齐）
_HIS_HOST = "push2his.eastmoney.com"
_DELAY_HOST = "push2delay.eastmoney.com"


def _conn_error():
    """构造「连接类错误」（**非**封禁信号）。"""
    return requests.exceptions.ConnectionError("connection reset by peer")


def _install_conn_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """让所有请求都以连接类错误失败。"""
    monkeypatch.setattr(
        requests.sessions.Session, "send", _make_fake_send(200, _conn_error())
    )


def _call_expecting_error(times: int = 1) -> List[str]:
    """发起 ``times`` 次必然失败的东财请求，返回捕获到的异常名列表。

    Args:
        times: 发起的请求次数。

    Returns:
        每次请求的异常类名列表。
    """
    names: List[str] = []
    for _ in range(times):
        with pytest.raises(requests.exceptions.ConnectionError):
            requests.Session().get(_EM_URL)
        names.append("ConnectionError")
    return names


def test_host_fallback_after_two_connection_errors(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """连续 2 次连接类错误 → 切 push2delay 并写降级窗口；期内直走回退主机。"""
    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_HOST_FALLBACK="1"
    )
    em_gate.install()
    _install_conn_error(monkeypatch)
    session = requests.Session()

    _call_expecting_error(times=1)
    assert _read_state(cfg)["host_degraded_until"] == 0.0, "第 1 次不应回退"
    assert _read_state(cfg)["host_fail_count"] == 1

    _call_expecting_error(times=1)
    state = _read_state(cfg)
    assert state["host_degraded_until"] > time.time(), "第 2 次应写降级窗口"
    assert state["hot_host"] == _DELAY_HOST
    assert state["host_fail_count"] == 0, "触发后连续计数归零"
    assert state["totals"]["degraded"] == 1

    # 第 3 次：降级期内**不再试死主机**，直接走回退主机（path 不变）
    seen: List[Dict[str, Any]] = []
    monkeypatch.setattr(requests.sessions.Session, "send", _capture_request(seen))
    assert session.get(_EM_URL).status_code == 200
    assert em_gate._extract_host(seen[0]["url"]) == _DELAY_HOST
    assert seen[0]["url"].startswith("https://")
    assert seen[0]["url"].endswith("/api/qt/stock/kline/get"), "path/query 不得被改写"

    records = [
        json.loads(line)
        for line in cfg.log_file.read_text(encoding="utf-8").strip().splitlines()
    ]
    assert records[2]["host"] == _DELAY_HOST, "日志须记**实际**主机"
    assert records[2]["degraded_host"] == _DELAY_HOST
    assert records[2]["status"] == "ok"


def test_host_fallback_window_expired_uses_primary(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """降级窗口到期后自动回到主主机（无需外部干预）。"""
    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_HOST_FALLBACK="1"
    )
    em_gate.install()
    # 状态文件尚未由任何请求创建，须先用默认状态初始化（避免 FileNotFoundError）
    state = em_gate._default_state()
    state["host_degraded_until"] = time.time() - 1.0  # 已过期
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_file.write_text(json.dumps(state), encoding="utf-8")

    seen: List[Dict[str, Any]] = []
    monkeypatch.setattr(requests.sessions.Session, "send", _capture_request(seen))
    requests.Session().get(_EM_URL)
    assert em_gate._extract_host(seen[0]["url"]) == _HIS_HOST


def test_ban_signal_does_not_trigger_host_fallback(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """封禁信号**不触发回退**（全站级，换主机无用），且打断连接错误计数。"""
    from http.client import RemoteDisconnected

    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_HOST_FALLBACK="1"
    )
    em_gate.install()
    signal = RemoteDisconnected("Remote end closed connection without response")
    monkeypatch.setattr(
        requests.sessions.Session, "send", _make_fake_send(200, signal)
    )
    session = requests.Session()

    for _ in range(2):
        with pytest.raises(RemoteDisconnected):
            session.get(_EM_URL)

    state = _read_state(cfg)
    assert state["host_degraded_until"] == 0.0, "封禁不回退"
    assert state["host_fail_count"] == 0
    assert state["totals"]["degraded"] == 0

    seen: List[Dict[str, Any]] = []
    monkeypatch.setattr(requests.sessions.Session, "send", _capture_request(seen))
    session.get(_EM_URL)
    assert em_gate._extract_host(seen[0]["url"]) == _HIS_HOST, "仍走原主机"


def test_host_fail_streak_reset_by_success(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """「连续」语义：成功会打断连接类错误计数，不累计成回退。"""
    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_HOST_FALLBACK="1"
    )
    em_gate.install()
    monkeypatch.setattr(
        requests.sessions.Session, "send", _make_fake_send(200, _conn_error())
    )
    _call_expecting_error(times=1)
    assert _read_state(cfg)["host_fail_count"] == 1

    # 中间夹一次成功 → 计数清零，故紧随其后的一次失败不应触发回退
    monkeypatch.setattr(requests.sessions.Session, "send", _make_fake_send(200))
    requests.Session().get(_EM_URL)
    assert _read_state(cfg)["host_fail_count"] == 0

    monkeypatch.setattr(
        requests.sessions.Session, "send", _make_fake_send(200, _conn_error())
    )
    _call_expecting_error(times=1)
    state = _read_state(cfg)
    assert state["host_fail_count"] == 1
    assert state["host_degraded_until"] == 0.0, "非连续，不得回退"


def test_host_fallback_disabled_by_config(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``EM_GATE_HOST_FALLBACK=0``：连接类错误连发也不改写主机。"""
    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_HOST_FALLBACK="0"
    )
    em_gate.install()
    _install_conn_error(monkeypatch)
    session = requests.Session()

    for _ in range(3):
        with pytest.raises(requests.exceptions.ConnectionError):
            session.get(_EM_URL)
    assert _read_state(cfg)["host_degraded_until"] == 0.0

    seen: List[Dict[str, Any]] = []
    monkeypatch.setattr(requests.sessions.Session, "send", _capture_request(seen))
    session.get(_EM_URL)
    assert em_gate._extract_host(seen[0]["url"]) == _HIS_HOST


def test_fallback_host_own_failure_abandons_degraded_window(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """回退主机自身连续连接失败 → 放弃降级窗口回主主机（不钉在死主机上 10 分钟）。"""
    cfg = gate(
        EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_HOST_FALLBACK="1"
    )
    em_gate.install()
    # 预置「已在降级窗口内」的状态（模拟上一轮已触发回退且本机回退主机不可达）
    preseed = em_gate._default_state()
    preseed["host_degraded_until"] = time.time() + 600.0
    preseed["hot_host"] = _DELAY_HOST
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_file.write_text(json.dumps(preseed), encoding="utf-8")

    _install_conn_error(monkeypatch)
    session = requests.Session()

    # 第 1 次：已改写到回退主机，但回退主机也连不上 → 仅计数，窗口先保留
    with pytest.raises(requests.exceptions.ConnectionError):
        session.get(_EM_URL)
    state = _read_state(cfg)
    assert state["host_fail_count"] == 1
    assert state["host_degraded_until"] > time.time(), "第 1 次不应放弃降级"

    # 第 2 次：回退主机连续 2 次连不上 → 放弃降级窗口，回主主机重新评估
    with pytest.raises(requests.exceptions.ConnectionError):
        session.get(_EM_URL)
    state = _read_state(cfg)
    assert state["host_degraded_until"] == 0.0, "回退主机连不上须放弃降级窗口"
    assert state["host_fail_count"] == 0
    assert state["totals"]["degraded"] == 0, "放弃降级不计入 degraded"

    # 第 3 次：窗口已撤 → 请求回到主主机
    seen: List[Dict[str, Any]] = []
    monkeypatch.setattr(requests.sessions.Session, "send", _capture_request(seen))
    session.get(_EM_URL)
    assert em_gate._extract_host(seen[0]["url"]) == _HIS_HOST


# ---------------------------------------------------------------------------
# 10. 东财请求强制 IPv4（步骤 6 加固；EM_GATE_FORCE_IPV4）
# ---------------------------------------------------------------------------
def _capture_gai_family(monkeypatch: pytest.MonkeyPatch, sink: List[Any]) -> None:
    """拦截 ``socket.getaddrinfo``：记录 ``(host, family)`` 后抛错（不产生真实 DNS / 网络）。

    Args:
        monkeypatch: pytest 的 monkeypatch。
        sink: 记录列表，元素为 ``(host, family)``。
    """

    def _fake_gai(host: str, port: int, family: int = 0, *args: Any, **kwargs: Any):
        """记录请求的地址族后立即失败，避免真实 DNS 解析。"""
        sink.append((host, family))
        raise OSError("getaddrinfo blocked in unit test")

    monkeypatch.setattr(socket, "getaddrinfo", _fake_gai)


def test_force_ipv4_applies_to_eastmoney_only(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``EM_GATE_FORCE_IPV4=1``：东财请求限定 ``AF_INET``，非东财请求维持原地址族。"""
    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_FORCE_IPV4="1")
    em_gate.install()
    assert em_gate._ORIGINAL_ALLOWED_GAI_FAMILY is not None, "开启时应装载钩子"
    expected = em_gate._ORIGINAL_ALLOWED_GAI_FAMILY()

    seen: List[Any] = []
    _capture_gai_family(monkeypatch, seen)

    with pytest.raises(requests.exceptions.ConnectionError):
        requests.Session().get(_EM_URL)
    assert seen, "东财请求应走到 DNS 解析"
    assert all(fam == socket.AF_INET for _, fam in seen), f"东财须限定 IPv4：{seen}"
    assert getattr(em_gate._FORCE_IPV4_LOCAL, "active", False) is False, "调用后须复位"

    # 非东财：闸门透传，地址族必须与 urllib3 原实现一致（零影响）
    seen.clear()
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.Session().get(_SINA_URL)
    assert seen, "非东财请求应走到 DNS 解析"
    assert all(fam == expected for _, fam in seen), f"非东财不得被改写：{seen}"


def test_force_ipv4_disabled_by_config(
    gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``EM_GATE_FORCE_IPV4=0``：不装载钩子，东财请求维持 urllib3 默认地址族。"""
    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_FORCE_IPV4="0")
    em_gate.install()
    assert em_gate._ORIGINAL_ALLOWED_GAI_FAMILY is None, "关闭时不应装载钩子"

    from urllib3.util import connection as _u3_connection

    expected = _u3_connection.allowed_gai_family()
    seen: List[Any] = []
    _capture_gai_family(monkeypatch, seen)
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.Session().get(_EM_URL)
    assert all(fam == expected for _, fam in seen), f"关闭时须维持默认地址族：{seen}"


def test_force_ipv4_hook_restored_when_gate_disabled(gate) -> None:
    """``EM_GATE_ENABLED=0`` → 还原 IPv4 钩子，完全退化为改造前行为。"""
    gate(EM_GATE_MIN_INTERVAL="0", EM_GATE_JITTER_MAX="0", EM_GATE_FORCE_IPV4="1")
    em_gate.install()
    assert em_gate._ORIGINAL_ALLOWED_GAI_FAMILY is not None

    gate(EM_GATE_ENABLED="0")
    em_gate.install()
    assert em_gate._ORIGINAL_ALLOWED_GAI_FAMILY is None, "总开关关闭须还原钩子"

# ---------------------------------------------------------------------------
# 14. report 监控加固（步骤 7 / 方案 §9 P2）
# ---------------------------------------------------------------------------
def _write_log(cfg: GateConfig, *statuses: str, host: str = _HIS_HOST) -> None:
    """向指标日志追加若干条**合法**记录（复用 ``_append_log`` 保证字段口径一致）。

    Args:
        cfg: 当前闸门配置（提供 ``log_file`` 路径）。
        *statuses: 每条记录的 ``status`` 字段（``ok`` / ``ban`` / ``error``）。
        host: 记录中的 ``host`` 字段（默认主主机）。
    """
    for index, status in enumerate(statuses):
        em_gate._append_log(
            cfg.log_file,
            {
                "ts": time.time() + index,
                "host": host,
                "url": _EM_URL,
                "wait_s": 0.0,
                "status": status,
                "error": "" if status == "ok" else status,
                "circuit": "closed",
                "probe": False,
                "proxy_retry": False,
                "degraded_host": False,
            },
        )


def _append_raw_log(cfg: GateConfig, *raw_lines: str) -> None:
    """向指标日志追加**原始文本行**（用于构造不可解析行 / 空行）。

    Args:
        cfg: 当前闸门配置（提供 ``log_file`` 路径）。
        *raw_lines: 逐行原文（不含换行符）。
    """
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
    with cfg.log_file.open("a", encoding="utf-8") as handle:
        for line in raw_lines:
            handle.write(line + "\n")


def _report_env() -> Dict[str, str]:
    """report 类用例的公共环境覆盖：关闭节流与抖动，避免无谓 sleep。

    Returns:
        覆盖项字典。
    """
    return {"EM_GATE_MIN_INTERVAL": "0", "EM_GATE_JITTER_MAX": "0"}


def test_report_log_scan_and_truncation_semantics(gate) -> None:
    """``log`` 截断语义：``limit>0`` 仅扫描尾部并标记 truncated；``limit=0`` 全量。"""
    cfg = gate(**_report_env())
    _write_log(cfg, "ok", "ok", "ok", "ok", "ok")

    log = em_gate.cmd_report(limit=3)["data"]["log"]
    assert log["total_lines"] == 5
    assert log["scanned"] == 3
    assert log["truncated"] is True
    assert log["scan_limit"] == 3
    assert log["lines"] == log["scanned"] == 3  # 兼容键恒等于实际扫描数

    full = em_gate.cmd_report(limit=0)["data"]["log"]
    assert full["total_lines"] == 5
    assert full["scanned"] == 5
    assert full["truncated"] is False
    assert full["lines"] == 5


def test_report_counts_unparsable_lines_separately(gate) -> None:
    """不可解析行计入 ``unparsable``，**不**混入 ``scanned`` / ``by_status``。"""
    cfg = gate(**_report_env())
    _write_log(cfg, "ok", "ban")
    _append_raw_log(cfg, "{不是合法 JSON}", "")

    log = em_gate.cmd_report(limit=0)["data"]["log"]
    assert log["total_lines"] == 4
    assert log["scanned"] == 2
    assert log["unparsable"] == 2
    assert log["by_status"] == {"ok": 1, "ban": 1}
    assert len(log["recent_events"]) == 2


def test_report_ban_rate_is_ratio_over_scanned(gate) -> None:
    """``ban_rate`` 的分母是**实际扫描行数**（``scanned``），而非总行数。"""
    cfg = gate(**_report_env())
    _write_log(cfg, "ok", "ban", "ok", "ok")

    assert em_gate.cmd_report(limit=0)["data"]["ban_rate"] == 0.25
    # 仅扫描尾部 2 行（均为 ok）→ 分母 2、分子 0
    assert em_gate.cmd_report(limit=2)["data"]["ban_rate"] == 0.0

    # 空日志：分母为 0 → 除零守卫，归零而非抛错
    gate(EM_GATE_LOG_FILE=str(cfg.log_file.parent / "empty.jsonl"))
    assert em_gate.cmd_report(limit=0)["data"]["ban_rate"] == 0.0


def test_report_health_ok_when_clean(gate) -> None:
    """日志与状态均干净时：``health.level == "ok"`` 且无 reasons。"""
    cfg = gate(**_report_env())
    _write_log(cfg, "ok", "ok")

    health = em_gate.cmd_report(limit=0)["data"]["health"]
    assert health["level"] == "ok"
    assert health["reasons"] == []


def test_report_health_warn_on_ban_below_threshold(gate) -> None:
    """有封禁但未达阈值（熔断仍 closed）→ ``warn``，理由含「封禁」。"""
    cfg = gate(**_report_env())
    _write_log(cfg, "ok", "ban")

    data = em_gate.cmd_report(limit=0)["data"]
    assert data["circuit"] == "closed"
    assert data["health"]["level"] == "warn"
    assert any("封禁" in reason for reason in data["health"]["reasons"])


def test_report_health_surfaces_truncation_reason(gate) -> None:
    """尾部截断必须显式提示（``reasons`` 含「尾部」），但截断本身不构成 warn。"""
    cfg = gate(**_report_env())
    _write_log(cfg, "ok", "ok", "ok", "ok", "ok", "ok")

    data = em_gate.cmd_report(limit=2)["data"]
    assert data["log"]["truncated"] is True
    assert data["health"]["level"] == "ok"  # 截断非故障，仅提示
    assert any(
        "尾部" in reason and "2/6" in reason for reason in data["health"]["reasons"]
    )


def test_report_health_critical_when_circuit_open(gate) -> None:
    """熔断相位非 closed → ``critical``（优先级最高）。"""
    cfg = gate(**_CIRCUIT_ENV)
    _seed_state(cfg, circuit_open_until=time.time() + 600, consecutive_ban=3)

    data = em_gate.cmd_report(limit=0)["data"]
    assert data["circuit"] == "open"
    assert data["health"]["level"] == "critical"
    assert any("熔断" in reason for reason in data["health"]["reasons"])


def test_report_and_status_share_one_budget_snapshot(gate) -> None:
    """``report`` 与 ``status`` 的相位/预算字段逐字段一致（同一 ``check_budget`` 口径）。"""
    gate(EM_GATE_BUDGET_PER_MIN="5", EM_GATE_BUDGET_PER_5MIN="9")

    report = em_gate.cmd_report(limit=0)["data"]
    status = em_gate.cmd_status()["data"]
    for key in ("circuit", "allowed", "reason", "remaining_min", "remaining_5min"):
        assert report[key] == status[key], f"{key} 口径漂移：report={report[key]}"
